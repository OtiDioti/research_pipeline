"""Trusted stdio MCP interface, inside the existing research service."""
import asyncio
from contextlib import asynccontextmanager, redirect_stdout, suppress
import io
import math
from pathlib import Path
import re
import time
import uuid

from mcp.server.fastmcp import FastMCP
from pydantic import StrictFloat

from . import checkpoint, jobs, workspace


class Adapter:
    def __init__(self, context, incoming=Path("/run/research-jobs-in"),
                 outgoing=Path("/run/research-jobs-out")):
        self.context, self.incoming, self.outgoing = context, incoming, outgoing
        self.running = {}
        self.admitting = asyncio.Lock()
        self.controlling = asyncio.Lock()
        self.admission_lost = False

    async def supervise(self):
        while True:
            for job in list(self.running.values()):
                job.poll()  # also reap supervisors that just published a terminal result
            await asyncio.sleep(.02)

    async def run(self, argv, cwd, runtime_seconds=None, yield_seconds=1):
        bounded(yield_seconds, 5, "yield_seconds")
        if self.admission_lost:
            raise jobs.JobError("Previous admission is unconfirmed; stop this context and recover ownership.")
        # No queue: another in-flight admission is refused, never silently retried.
        if self.admitting.locked():
            raise jobs.JobError("An admission request is already outstanding; no command launched.")
        async with self.admitting:
            request_id = uuid.uuid4().hex
            request = {**self.context, "request_id": request_id, "argv": argv,
                       "cwd": cwd, "runtime_seconds": runtime_seconds}
            jobs.atomic(self.outgoing / "request.json", request)
            deadline = min(self.context["deadline"], time.monotonic() + 5)
            while time.monotonic() < deadline:
                ack = jobs.read(self.incoming / "ack.json")
                if ack and ack.get("request_id") == request_id:
                    break
                await asyncio.sleep(.02)
            else:
                # Keep intent. A late reservation is reconciled only at service
                # cleanup; do not overwrite it with another admission request.
                self.admission_lost = True
                raise jobs.JobError("Admission acknowledgement unavailable; stop this context and recover ownership.")
            if not ack["accepted"]:
                raise jobs.JobError(ack["error"])
            job = jobs.Worker(ack["job"], self.outgoing)
            self.running[job.record["job_id"]] = job
        return await self.wait(job.record["job_id"], yield_seconds)

    def owned(self, job_id):
        if job_id not in self.running:
            raise jobs.JobError("Unknown job or job belongs to another activation")
        return self.running[job_id]

    def status(self, job_id=None):
        if job_id is not None:
            if job_id in self.running:
                return self.owned(job_id).record
            if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{32}", job_id):
                raise jobs.JobError("Unknown job or job belongs to another activation")
            record = jobs.read(self.incoming / f"{job_id}.json")
            if (record and record.get("job_id") == job_id
                    and (self.context["task_id"] == "primary"
                         or record.get("activation_id") == self.context["activation_id"])):
                return record
            raise jobs.JobError("Unknown job or job belongs to another activation")
        status = jobs.read(self.incoming / "status.json") or {
            "status": "unknown", "budget_report": None,
            "reason": "Controller status unavailable; budget and capacity are unknown. "
                      "Missing telemetry grants no additional allowance."}
        for record in status.get("jobs", []):
            if record["state"] in jobs.ACTIVE:
                record["elapsed_seconds"] = max(0, time.monotonic() - record["admitted_monotonic"])
        return status

    async def wait(self, job_id, seconds):
        bounded(seconds, 5, "bounded_wait_seconds")
        job = self.owned(job_id)
        deadline = time.monotonic() + seconds
        while job.record["state"] in jobs.ACTIVE and time.monotonic() < deadline:
            await asyncio.sleep(.02)
        return job.record

    def cancel(self, job_id):
        job = self.owned(job_id)
        if job.record["state"] in jobs.ACTIVE:
            job.stop("Job cancelled; partial artifacts retained.")
        return job.record

    def draft(self, path, content):
        if time.monotonic() >= self.context["deadline"]:
            raise jobs.JobError("Saving deadline exhausted")
        if not isinstance(content, str) or len(content.encode()) > 256 * 1024:
            raise jobs.JobError("Draft content must be UTF-8 text at most 256 KiB")
        rel = Path(path)
        if (not rel.parts or rel.suffix != ".md" or rel.name == "FOLDER_CONTENT.md"
                or any(p.startswith(".") for p in rel.parts)
                or not workspace.allowed_science(path, self.context["task_id"])):
            raise jobs.JobError("Draft must be scoped scientific Markdown")
        target = workspace.safe_path(Path("/run/research-drafts"), path)
        target.parent.mkdir(parents=True, exist_ok=True)
        workspace.atomic_text(target, content)
        return {"draft": path, "bytes": len(content.encode())}


def bounded(value, maximum, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise jobs.JobError(f"{name} must be finite and between 0 and {maximum} seconds")


def create_server(adapter):
    @asynccontextmanager
    async def lifespan(server):
        supervisor = asyncio.create_task(adapter.supervise())
        try:
            yield {}
        finally:
            supervisor.cancel()
            with suppress(asyncio.CancelledError):
                await supervisor
            for job in adapter.running.values():
                if job.record["state"] in jobs.ACTIVE:
                    job.stop("Adapter closing; partial artifacts retained.", "interrupted")

    server = FastMCP("research-jobs", lifespan=lifespan)

    @server.tool()
    async def job_run(argv: list[str], cwd: str, runtime_seconds: StrictFloat | None = None,
                      yield_seconds: StrictFloat = 1) -> dict:
        """Run argv in a bounded scientific job. Choose an explicit shell if needed.
        cwd is an absolute /project path in your permitted workspace. No queue.
        Preparation, descendants and tool checks share this job's deadline.
        """
        return await adapter.run(argv, cwd, runtime_seconds, yield_seconds)

    @server.tool()
    async def job_wait(job_id: str, bounded_wait_seconds: StrictFloat = 1) -> dict:
        """Wait at most five seconds; never restarts a job or its allowance."""
        return await adapter.wait(job_id, bounded_wait_seconds)

    @server.tool()
    async def job_status(job_id: str | None = None) -> dict:
        """Investigation budget observation, capacity and up to 32 compact summaries.
        Active jobs first. budget_report is observed_at the controller timestamp,
        refreshed about once a second; it never replenishes or authorizes work.
        Missing status/usage is unknown. Inspection consumes no job slot.
        jobs_omitted reports truncated history. Supply a job_id for full retained
        output; the primary can also read earlier activations' results.
        """
        return adapter.status(job_id)

    @server.tool()
    async def job_cancel(job_id: str) -> dict:
        """Stop the complete owned job tree, preserving partial artifacts."""
        return adapter.cancel(job_id)

    @server.tool()
    async def write_draft(path: str, content: str) -> dict:
        """Save scientific Markdown without admitting a job, including while saving.
        path is project-relative, e.g. handoffs/primary.md or work/PLAN.md.
        The controller publishes drafts after confirmed service cleanup.
        """
        return adapter.draft(path, content)

    @server.tool()
    async def control(action: str = "check", path: str | None = None,
                      parent: str = "primary", target: str | None = None) -> dict:
        """Fixed checkpoint/collaboration actions, without command execution.
        action: check, tasks, acknowledge, delegate, verify, respond, close.
        path: assignment/packet/response/closure Markdown. target: verifier ID.
        """
        if time.monotonic() >= adapter.context["deadline"]:
            raise jobs.JobError("Saving deadline exhausted")
        if action in ("check", "tasks", "acknowledge"):
            args = [] if action == "acknowledge" else ["--" + action]
        elif action in ("delegate", "verify") and path:
            args = ["--" + action, path, "--parent", parent]
        elif action in ("respond", "close") and path and target:
            args = (["--respond", target, "--response", path] if action == "respond" else
                    ["--close-verification", target, "--reason", path])
        else:
            raise jobs.JobError("Invalid fixed control action or missing Markdown path/target")
        # checkpoint.main accepts only these fixed operations; stdout belongs to
        # MCP transport, so never let helper output corrupt protocol framing.
        def invoke():
            output = io.StringIO()
            with redirect_stdout(output):
                code = checkpoint.main(args)
            return {"returncode": code, "message": output.getvalue()}
        if adapter.controlling.locked():
            raise jobs.JobError("A checkpoint/control request is already outstanding")
        async with adapter.controlling:
            return await asyncio.to_thread(invoke)

    return server


def main():
    context = jobs.read(Path("/run/research-jobs.json"))
    if not context:
        raise jobs.JobError("Controlled job activation context unavailable")
    create_server(Adapter(context)).run(transport="stdio")


if __name__ == "__main__":
    main()
