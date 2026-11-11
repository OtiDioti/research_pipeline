"""Investigation-wide admission, and namespace-local supervision of owned jobs.

The foreground controller alone reserves capacity. Only the trusted adapter sees
the request/result directories; scientific commands run in a nested PID namespace.
No process is started on the controller host by this module.
"""
import importlib.util
from contextlib import nullcontext
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid


class JobError(ValueError):
    pass


ACTIVE = {"reserved", "running", "stopping", "cleanup_unconfirmed"}
# Keep trusted module imports independent of the research cwd and user site.
# PYTHONPATH contains only the runtime/source mounts supplied by the controller.
TRUSTED_PYTHON_FLAGS = ("-P", "-s")
STATUS_JOB_LIMIT = 32


def status_summary(record):
    fields = ("job_id", "task_id", "activation_id", "state", "cleanup_ok", "returncode",
              "admitted_monotonic", "admitted_epoch", "deadline", "elapsed_seconds",
              "configured_runtime_seconds", "requested_runtime_seconds", "effective_runtime_seconds",
              "finished_epoch", "stdout_clipped", "stderr_clipped")
    return {**{k: record[k] for k in fields if k in record},
            "executable": record["argv"][0][:200], "reason": record["reason"][:512]}


def validate_limits(limits, *, defaults=False):
    for key, default in (("job_runtime_seconds", 60), ("max_jobs", 1)):
        if key not in limits and defaults:
            limits[key] = default
        if key not in limits:
            continue  # historical state: migrate only after ownership cleanup
        value = limits[key]
        valid = (type(value) is int and value > 0 if key == "max_jobs" else
                 type(value) in (int, float) and math.isfinite(value) and value > 0)
        if not valid:
            raise JobError(f"Invalid saved {key}: expected a positive "
                           + ("integer" if key == "max_jobs" else "finite runtime"))


def atomic(path, value):
    from .workspace import atomic_text
    atomic_text(path, json.dumps(value, ensure_ascii=True) + "\n")


def read(path):
    try:
        if path.is_symlink() or path.stat().st_size > 256 * 1024:
            return None
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def adapter_mounts():
    """Use the installed Python/MCP runtime, not the researcher's dependencies."""
    spec = importlib.util.find_spec("mcp")
    if spec is None:
        from .isolation import RuntimeUnavailable
        raise RuntimeUnavailable("Controlled jobs require the installed mcp dependency")
    return sorted({sys.base_prefix, sys.prefix, str(Path(spec.origin).parent.parent)})


class JobManager:
    def __init__(self, project, state, save):
        self.project, self.state, self.save = project, state, save
        self.owners = {}

    def configure(self, config, session, owner):
        from .workspace import owner_fields, task_directory
        validate_limits(self.state["limits"], defaults=True)
        config.job_runtime_seconds = self.state["limits"]["job_runtime_seconds"]
        config.max_jobs = self.state["limits"]["max_jobs"]
        root = session / "jobs"
        root.mkdir()
        for name in ("in", "out"):
            (root / name).mkdir()
        identity = {**owner_fields(owner), "task_id": config.task_id}
        context = {**identity, "deadline": config.deadline,
                   "job_runtime_seconds": config.job_runtime_seconds,
                   "workspace": task_directory(config.task_id),
                   "task_workspaces": config.task_workspaces,
                   "frozen_inputs": config.frozen_inputs,
                   "references": [dest for _, dest in config.reference_mounts]}
        config.job_context = root / "context.json"
        atomic(config.job_context, context)
        self.owners[identity["activation_id"]] = {
            "identity": identity, "root": root, "config": config, "last": None}
        self.save()

    def admit(self, owner, request):
        from .isolation import RequestedStop
        guard = owner["config"].launch_guard
        try:
            with guard() if guard else nullcontext():
                return self._admit(owner, request)
        except RequestedStop as exc:
            raise JobError("Saving requested; new scientific jobs are blocked.") from exc

    def _admit(self, owner, request):
        from . import workspace
        config = owner["config"]
        if owner.get("stopped"):
            raise JobError("Owning service stopped; no command launched.")
        if any(request.get(k) != v for k, v in owner["identity"].items()):
            raise JobError("Job activation ownership mismatch")
        if (config.control / "request.json").exists():
            raise JobError("Saving requested; new scientific jobs are blocked.")
        if time.monotonic() >= config.deadline:
            raise JobError("Effective session deadline exhausted; no command launched.")
        records = self.state.setdefault("jobs", {})
        occupied = sum(r["state"] in ACTIVE for r in records.values())
        if occupied >= config.max_jobs:
            raise JobError(f"Job capacity exhausted ({occupied}/{config.max_jobs}); no command launched.")
        argv = request.get("argv")
        if (not isinstance(argv, list) or not argv
                or not all(isinstance(a, str) and a and "\0" not in a for a in argv)):
            raise JobError("Expected a nonempty argv array")
        cwd = request.get("cwd")
        if not isinstance(cwd, str) or not cwd.startswith("/project/"):
            raise JobError("Job cwd must be in the caller's permitted workspace")
        rel = cwd.removeprefix("/project/")
        path = workspace.safe_path(self.project, rel)
        from .workspace import writable_directories
        if not any(Path(rel).is_relative_to(p) for p in writable_directories(config.task_id)):
            raise JobError("Job cwd must be in the caller's permitted workspace")
        excluded = (*config.frozen_inputs, *config.task_workspaces) if config.task_id == "primary" else (
            *config.frozen_inputs, f"work/tasks/{config.task_id}/inputs")
        if any(Path(rel).is_relative_to(p) for p in excluded) or not path.is_dir():
            raise JobError("Job cwd must be an existing writable workspace directory")
        requested = request.get("runtime_seconds")
        runtime = config.job_runtime_seconds if requested is None else requested
        if (type(runtime) not in (int, float) or not math.isfinite(runtime)
                or runtime <= 0 or runtime > config.job_runtime_seconds):
            raise JobError("Requested runtime must be positive and cannot exceed the configured job runtime")
        began = time.monotonic()
        record = {**owner["identity"], "job_id": uuid.uuid4().hex,
                  "argv": argv, "cwd": cwd, "state": "reserved",
                  "admitted_monotonic": began, "admitted_epoch": time.time(),
                  "configured_runtime_seconds": config.job_runtime_seconds,
                  "requested_runtime_seconds": runtime,
                  "deadline": min(config.deadline, began + runtime),
                  "cleanup_ok": False, "reason": "Reserved before launch."}
        record["effective_runtime_seconds"] = max(0, record["deadline"] - began)
        records[record["job_id"]] = record
        self.save()  # reservation is durable before authorizing a launch
        return record

    def poll(self):
        for owner in self.owners.values():
            root = owner["root"]
            changed = False
            for record in self.state.get("jobs", {}).values():
                if record["activation_id"] != owner["identity"]["activation_id"] or record["state"] not in ACTIVE:
                    continue
                result = read(root / "out" / f"{record['job_id']}.json")
                if result and result.get("job_id") == record["job_id"]:
                    # Never accept changed ownership, argv or effective deadline.
                    fields = ("state", "reason", "returncode", "cleanup_ok", "stdout", "stderr",
                              "stdout_clipped", "stderr_clipped", "elapsed_seconds", "finished_epoch")
                    updates = {k: result[k] for k in fields if k in result}
                    changed |= any(record.get(k) != v for k, v in updates.items())
                    record.update(updates)
                    if record["state"] not in ACTIVE and record.get("cleanup_ok") is not True:
                        record["state"] = "cleanup_unconfirmed"
            if changed:
                self.save()
            request = read(root / "out" / "request.json")
            if not request or request.get("request_id") == owner["last"]:
                continue
            request_id = request.get("request_id")
            if not isinstance(request_id, str) or len(request_id) != 32:
                continue
            ack = {"request_id": request_id, "accepted": False}
            try:
                ack.update(accepted=True, job=self.admit(owner, request))
            except (ValueError, OSError) as exc:
                ack.update(accepted=False, error=str(exc))
            owner["last"] = request_id
            atomic(root / "in" / "ack.json", ack)
        # A status snapshot is operational data, not a scientific publication.
        for owner in self.owners.values():
            records = [r for r in self.state.get("jobs", {}).values()
                       if owner["identity"]["task_id"] == "primary"
                       or r["activation_id"] == owner["identity"]["activation_id"]]
            # Keep full, individually readable results outside the bounded list.
            # This also makes retained output available in fresh primary contexts.
            details = owner.setdefault("details", {})
            for record in records:
                if details.get(record["job_id"]) != record:
                    atomic(owner["root"] / "in" / f"{record['job_id']}.json", record)
                    details[record["job_id"]] = record.copy()
            active = [r for r in records if r["state"] in ACTIVE]
            recent = [r for r in reversed(records) if r["state"] not in ACTIVE]
            visible = (active + recent)[:STATUS_JOB_LIMIT]
            snapshot = {"jobs": [status_summary(r) for r in visible],
                "jobs_total": len(records), "jobs_omitted": len(records) - len(visible),
                "active_jobs_omitted": max(0, len(active) - STATUS_JOB_LIMIT),
                "occupied": sum(r["state"] in ACTIVE for r in self.state.get("jobs", {}).values()),
                "max_jobs": self.state["limits"].get("max_jobs", 1)}
            signature = json.dumps(snapshot, sort_keys=True)
            if signature != owner.get("snapshot"):
                atomic(owner["root"] / "in" / "status.json", snapshot)
                owner["snapshot"] = signature

    def owner_stopped(self, activation, cleanup_ok):
        if activation in self.owners:
            self.owners[activation]["stopped"] = True
        self.poll()
        reconcile(self.state, activation, cleanup_ok)
        self.owners.pop(activation, None)
        self.save()


def reconcile(state, activation=None, cleanup_ok=True):
    """Only call after the existing service cleanup authority has confirmed stop."""
    for record in state.get("jobs", {}).values():
        if activation is not None and record["activation_id"] != activation:
            continue
        if record["state"] in ACTIVE:
            record.update(state="interrupted" if cleanup_ok else "cleanup_unconfirmed",
                          cleanup_ok=cleanup_ok,
                          reason="Owning service stopped; unfinished work is unknown; inspect partial artifacts."
                          if cleanup_ok else "Previous job cleanup unconfirmed; further admission blocked.")


def observed(state, activation=None):
    records = [r for r in state.get("jobs", {}).values()
               if activation is None or r["activation_id"] == activation]
    return {"command_count": len(records),
            "successful_commands": sum(r["state"] == "completed" and r.get("returncode") == 0
                                       and r.get("cleanup_ok") is True for r in records),
            "failed_commands": [{"command": r["argv"], "reason": r["reason"],
                                 "exit_code": r.get("returncode")}
                                for r in records if r["state"] not in ACTIVE | {"completed"}][:20]}


class RunningJob:
    """Run only inside an owned production service, outside the job PID namespace."""
    def __init__(self, record, context, root=Path("/run/research-jobs-out")):
        self.record, self.root = dict(record), root
        self.process = None
        self.launch_attempted = False
        self.selector = selectors.DefaultSelector()
        self.buffers = {"stdout": bytearray(), "stderr": bytearray()}
        self.info = root / f"{record['job_id']}.info"
        self.context = context

    def launch(self):
        from .isolation import bubblewrap_command
        record, context, root = self.record, self.context, self.root
        local = root / f"{record['job_id']}.context"
        tool_context = read(Path("/run/research-tools.json"))
        atomic(local, {**tool_context, "deadline": record["deadline"], "job_id": record["job_id"]})
        # Persistent dependency scratch is activation-local and still in the role grant.
        scratch = Path("/tmp/research-job-scratch")
        scratch.mkdir(exist_ok=True)
        args = bubblewrap_command(Path("/project"), record["argv"], drafts=Path("/run/research-drafts"),
            control=Path("/run/research-control"), response=Path("/run/research-checkpoint"),
            task_id=context["task_id"], task_workspaces=context["task_workspaces"],
            frozen_inputs=context["frozen_inputs"],
            reference_mounts=[(p, p) for p in context["references"]],
            reference_catalog=Path("/run/research-references.json"),
            tool_context=local)
        # Hide collaboration/checkpoint write endpoints as well as adapter private storage.
        offset = args.index("--chdir")
        args[offset:offset] = ["--bind", str(scratch), "/tmp",
                              "--ro-bind", str(local), "/run/research-job.json",
                              "--tmpfs", "/run/research-checkpoint",
                              "--remount-ro", "/run/research-checkpoint"]
        args[args.index("--chdir") + 1] = record["cwd"]
        info_fd = os.open(self.info, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            args[1:1] = ["--info-fd", str(info_fd)]
            if time.monotonic() >= record["deadline"]:
                self.record.update(state="timed_out", returncode=None, cleanup_ok=True,
                                   reason="Job runtime exhausted during preparation; partial artifacts retained.")
                return
            self.launch_attempted = True
            self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            start_new_session=True, pass_fds=(info_fd,))
            for stream, name in ((self.process.stdout, "stdout"), (self.process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, name)
            self.record.update(state="running", reason="Command running in owned PID namespace.")
        except OSError as exc:
            self.record.update(state="failed", returncode=None, cleanup_ok=True,
                               reason=f"Executable unavailable: {exc}")
        finally:
            os.close(info_fd)
            self.persist()

    def persist(self):
        self.record["elapsed_seconds"] = max(0, time.monotonic() - self.record["admitted_monotonic"])
        for name, data in self.buffers.items():
            self.record[name] = data.decode(errors="replace")
        atomic(self.root / f"{self.record['job_id']}.json", self.record)

    def stop(self, reason, state="cancelled"):
        if self.process and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.finish(state, reason)

    def poll(self):
        if self.record["state"] not in ACTIVE:
            return True
        if time.monotonic() >= self.record["deadline"]:
            self.stop("Job runtime exhausted; partial artifacts retained.", "timed_out")
            return True
        if Path("/run/research-control/request.json").exists():
            self.stop("Saving requested; job stopped; partial artifacts retained.", "interrupted")
            return True
        for key, _ in self.selector.select(0):
            data = os.read(key.fileobj.fileno(), 65536)
            if not data:
                self.selector.unregister(key.fileobj)
            else:
                available = max(0, 8192 - len(self.buffers[key.data]))
                self.buffers[key.data].extend(data[:available])
                self.record[key.data + "_clipped"] = self.record.get(key.data + "_clipped", False) or len(data) > available
        if self.process.poll() is not None:
            code = self.process.returncode
            self.finish("completed" if code == 0 else "failed",
                        "Command completed." if code == 0 else f"Command failed (exit {code}); inspect stderr; executable may be unavailable.")
            return True
        return False

    def finish(self, state, reason):
        if self.process:
            try:
                self.process.wait(timeout=2)
                info = read(self.info)
                # --info-fd identifies the namespace init in the supervisor's PID
                # namespace. A reaped launcher alone is not the capacity condition.
                pid = info.get("child-pid") if info else None
                teardown_deadline = time.monotonic() + .5
                while (type(pid) is int and Path(f"/proc/{pid}").exists()
                       and time.monotonic() < teardown_deadline):
                    time.sleep(.005)
                clean = type(pid) is int and not Path(f"/proc/{pid}").exists()
            except subprocess.TimeoutExpired:
                clean = False
            self.record["returncode"] = self.process.poll()
            for stream in (self.process.stdout, self.process.stderr):
                try:
                    os.set_blocking(stream.fileno(), False)
                    while data := os.read(stream.fileno(), 65536):
                        name = "stdout" if stream is self.process.stdout else "stderr"
                        available = max(0, 8192 - len(self.buffers[name]))
                        self.buffers[name].extend(data[:available])
                        self.record[name + "_clipped"] = self.record.get(name + "_clipped", False) or len(data) > available
                except BlockingIOError:
                    pass
                stream.close()
        else:
            clean = not self.launch_attempted
        if clean:
            # All scientific work has stopped; no timeout may interrupt output
            # finalization and turn a confirmed teardown into a lost supervisor.
            signal.setitimer(signal.ITIMER_REAL, 0)
        self.selector.close()
        if state == "failed" and b"bwrap: execvp " in self.buffers["stderr"]:
            reason = f"Executable unavailable: {self.record['argv'][0]}"
        self.record.update(state=state if clean else "cleanup_unconfirmed", reason=reason if clean else
                           "Previous job cleanup unconfirmed; further admission blocked.",
                           cleanup_ok=clean, finished_epoch=time.time())
        self.persist()


class Worker:
    """A separate trusted supervisor per job; adapter calls cannot delay its timer."""
    def __init__(self, record, root):
        self.record, self.root = dict(record), root
        request = root / f"{record['job_id']}.request"
        atomic(request, record)
        self.process = subprocess.Popen([sys.executable, *TRUSTED_PYTHON_FLAGS, "-m", "research_pipeline.jobs",
                                         "--supervise", str(request)],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)

    def poll(self):
        if self.record["state"] not in ACTIVE:
            self.process.poll()
            return True
        value = read(self.root / f"{self.record['job_id']}.json")
        if value:
            self.record.update(value)
        if self.record["state"] in ACTIVE:
            self.record["elapsed_seconds"] = max(0, time.monotonic() - self.record["admitted_monotonic"])
        if self.process.poll() is not None and self.record["state"] in {"reserved", "running", "stopping"}:
            self.record.update(state="cleanup_unconfirmed", cleanup_ok=False,
                reason="Job supervisor lost; owning-service cleanup required before further admission.")
            atomic(self.root / f"{self.record['job_id']}.json", self.record)
        return self.record["state"] not in ACTIVE

    def stop(self, reason, state="cancelled"):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Do not kill only the immediate parent and claim cleanup.
                self.record.update(state="cleanup_unconfirmed", cleanup_ok=False,
                                   reason="Supervisor cleanup unconfirmed; owning-service cleanup required.")
                atomic(self.root / f"{self.record['job_id']}.json", self.record)
                return
        self.poll()


class JobExpired(Exception):
    pass


class JobCancelled(Exception):
    pass


def supervise(request_path):
    """Private entry point in an existing service, never a controller launcher."""
    record = read(request_path)
    context = read(Path("/run/research-jobs.json"))
    job = RunningJob(record, context, request_path.parent)
    def expire(signum, frame):
        raise JobExpired()
    def cancel(signum, frame):
        raise JobCancelled()
    signal.signal(signal.SIGALRM, expire)
    signal.signal(signal.SIGTERM, cancel)
    signal.setitimer(signal.ITIMER_REAL, max(.001, record["deadline"] - time.monotonic()))
    try:
        job.launch()
        while not job.poll():
            time.sleep(.02)
    except (JobExpired, JobCancelled) as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        job.stop("Job runtime exhausted; partial artifacts retained." if isinstance(exc, JobExpired)
                 else "Job cancelled; partial artifacts retained.",
                 "timed_out" if isinstance(exc, JobExpired) else "cancelled")
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        job.stop(f"Job preparation/execution failed: {type(exc).__name__}: {exc}", "failed")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--supervise":
        raise SystemExit("Private job supervisor requires an owned request")
    supervise(Path(sys.argv[2]))
