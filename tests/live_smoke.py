"""Live smoke run (PROJECT.md §9, item 2): a small public investigation through the real CLIs.

Not part of the unit tests: it uses real model sessions and costs usage. Run it with

    uv run python -m tests.live_smoke [--primary codex:gpt-6.1-sol:low] [--reviewer claude:haiku:low]
        [--librarian claude:haiku:low]

It shows spawning across CLIs, a rejected then accepted result, a job, handoffs
forced by a lowered context threshold, a quota pause (a short window of one CLI is
reported exhausted for a minute, on top of the real readings), optionally a human
pause with edits while paused (``--pause-at``), the Reviewer exchange ending in
COMPLETE or STOP, and the Librarian placing the accepted subagent's work and, at
the end, the primary's and the Reviewer's. The science and the agreement are the agents'
own; only the threshold, the idle limit and the one quota reading are artificial.

Waiting agents keep their sessions, and a :class:`Monitor` checks it: the rejected
subagent continues in the session it submitted from, the primary receives the
verdict in the session it proposed from, agents paused by the human or held by the
quota continue in their own sessions, and an idle session closes at the (lowered)
idle limit. The transcript, these checks and a final summary are printed; the
project is kept under ~/.cache for inspection.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import time
from datetime import datetime
from pathlib import Path

from agent_toolkit import DRIVERS, quota

from research_pipeline import controller as controller_module
from research_pipeline.controller import Controller
from research_pipeline.state import Options

ROOT = Path.home() / ".cache" / "research-pipeline-smoke"
QUESTION = """# Research question

Compute the integral I = ∫₀¹ x² e^(−x) dx exactly, and confirm the exact value numerically to at least
10 significant digits with an independent method.
"""
PROCEDURE = """# Instructions for this investigation

This is a short engineering smoke test of the research platform; keep the science brief but rigorous.
Follow this procedure:

1. Derive the exact value yourself.
2. Delegate the numerical confirmation to one subagent with spawn, on backend {sub}, model {sub_model} and
   effort {sub_effort}, asking it to run its computation with run_job.
3. Reject the subagent's first result once, asking it to state the absolute error against your exact value;
   accept its second result if it is sound.
4. Write the phase's RESULT.md and propose complete.
"""


class SimulatedQuota:
    """Real quota readings, except that ``backend``'s short window reads exhausted for ``seconds`` once."""

    def __init__(self, backend: str, after: float, seconds: float):
        self.backend, self.start, self.end = backend, time.time() + after, time.time() + after + seconds

    def __call__(self, backend: str) -> list[quota.Window]:
        windows = quota.read(DRIVERS[backend])
        if backend == self.backend and self.start <= time.time() < self.end:
            print(
                f"[smoke] reporting {backend} short window as exhausted until {self.end - time.time():.0f} s",
                flush=True,
            )
            windows = [w for w in windows if w.weekly] + [quota.Window(backend, 300, 95.0, self.end)]
        return windows


async def human_pause(controller: Controller, at: float) -> None:
    """Pause like the human at ``at`` seconds, edit files while paused, then resume."""
    await asyncio.sleep(at)
    print("[smoke] human pause requested", flush=True)
    controller.toggle_pause()
    for _ in range(600):
        await asyncio.sleep(1)
        if controller.state.status == "paused":
            break
    else:
        print("[smoke] the pause did not complete within 10 minutes", flush=True)
        return
    root = controller.project.root
    objectives = root / "phases" / "1" / "OBJECTIVES.md"
    objectives.write_text(objectives.read_text() + "\nAlso state the value to 12 significant digits in the report.\n")
    status = root / "phases" / "1" / "STATUS.md"
    status.write_text(status.read_text() + "\nHuman note (edited while paused): keep the report short.\n")
    print("[smoke] edited OBJECTIVES.md and STATUS.md while paused; resuming", flush=True)
    controller.toggle_pause()


class Monitor:
    """Watches the controller's agents and sessions while it runs, and checks that waiting kept sessions."""

    def __init__(self, controller: Controller):
        self.controller = controller
        self.results: dict[str, bool | None] = {
            name: None
            for name in (
                "rejected subagent continued in its session",
                "primary received the verdict in its proposing session (or its context successor)",
                "agents paused by the human continued in their sessions",
                "quota-held agent continued in its session",
                "an idle session closed at the idle limit",
                "an accepted subagent's work was shelved",
                "the final work was shelved and placed",
            )
        }
        self._seen: dict[str, tuple] = {}  # agent -> (status, pause reason, its session, sessions so far)
        self._proposal: tuple | None = None  # (round, primary's sessions and context handoffs when it proposed)
        self.handoffs = 0  # the primary's context handoffs (the low threshold's own resets)
        self._paused: dict[str, object] = {}  # agent -> its session when the human's pause completed

    def note(self, check: str, ok: bool) -> None:
        if self.results[check] is None or not ok:
            self.results[check] = ok
            print(f"[smoke] check: {check}: {'yes' if ok else 'NO'}", flush=True)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(0.2)
            self.look()

    def look(self) -> None:
        control, state = self.controller, self.controller.state
        for agent in state.agents.values():
            session = control.sessions.get(agent.id)
            before = self._seen.get(agent.id)
            now = (agent.status, agent.pause_reason, session, agent.sessions)
            if before and before[0] == "submitted" and agent.status == "running" and before[2] is not None:
                self.note("rejected subagent continued in its session", session is before[2])
            if before and before[1] == "quota" and agent.status == "running" and before[2] is not None:
                self.note("quota-held agent continued in its session", session is before[2])
            self._seen[agent.id] = now
        proposal, primary = state.proposal, state.agents["primary"]
        if proposal and not proposal.get("reviewed") and self._proposal is None:
            self._proposal = (proposal["round"], primary.sessions - self.handoffs)
        elif (
            self._proposal
            and (state.verdict or state.status in ("complete", "stopped"))
            and (not proposal or proposal.get("reviewed") or proposal["round"] != self._proposal[0])
        ):
            self.note(
                "primary received the verdict in its proposing session (or its context successor)",
                primary.sessions - self.handoffs == self._proposal[1],
            )
            self._proposal = None
        if state.status == "paused" and not self._paused:
            self._paused = dict(control.sessions)
        elif state.status == "running" and self._paused:
            self.note(
                "agents paused by the human continued in their sessions",
                all(
                    control.sessions.get(agent) is session
                    for agent, session in self._paused.items()
                    if agent in control.sessions
                ),
            )
            self._paused = {}

    def shown(self, kind: str, agent: str, text: str) -> None:
        """Follow the transcript: the primary's context handoffs, and idle sessions closing."""
        if kind == "controller" and agent == "primary" and text.startswith("Handoff requested (context)"):
            self.handoffs += 1
        if kind == "controller" and text.startswith("Idle: its session closed"):
            self.note("an idle session closed at the idle limit", True)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", default="codex:gpt-6.1-sol:low", help="BACKEND:MODEL:EFFORT")
    parser.add_argument("--reviewer", default="claude:haiku:low", help="BACKEND:MODEL:EFFORT")
    parser.add_argument("--librarian", default="claude:haiku:low", help="BACKEND:MODEL:EFFORT")
    parser.add_argument("--sub", default="claude", help="backend the subagent must use")
    parser.add_argument("--sub-model", default="haiku")
    parser.add_argument("--sub-effort", default="low")
    parser.add_argument("--threshold", type=float, default=0.06)
    parser.add_argument("--idle-limit", type=float, default=0.5, help="minutes an idle session waits")
    parser.add_argument("--quota-after", type=float, default=240, help="seconds before the simulated quota hold")
    parser.add_argument("--pause-at", type=float, help="seconds before a human pause and resume (default: none)")
    parser.add_argument("--limit", type=float, default=3600, help="seconds before giving up")
    args = parser.parse_args()

    root = ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    (root / "starting_evidence").mkdir(parents=True)
    (root / "starting_evidence" / "FOLDER_CONTENT.md").write_text("# Folder contents\n\n")
    (root / "phases" / "1").mkdir(parents=True)
    (root / "phases" / "1" / "OBJECTIVES.md").write_text(QUESTION)
    (root / "AGENTS.md").write_text(
        PROCEDURE.format(sub=args.sub, sub_model=args.sub_model, sub_effort=args.sub_effort)
    )
    print(f"[smoke] project: {root}", flush=True)

    def show(kind: str, agent: str, text: str) -> None:
        monitor.shown(kind, agent, text)
        marker = {"tool": "·", "notice": "→", "human": "YOU", "controller": "CONTROLLER", "alert": "ALERT"}.get(
            kind, ""
        )
        text = text if len(text) < 1500 else text[:1500] + " […]"
        print(f"[{datetime.now():%H:%M:%S}] {agent} {marker}".rstrip() + f"\n{text.rstrip()}\n", flush=True)

    controller_module.QUOTA_INTERVAL = 20
    options = Options(
        primary=args.primary,
        reviewer=args.reviewer,
        librarian=args.librarian,
        backends=sorted({"codex", "claude"}),
        max_agents=3,
        threshold=args.threshold,
        idle_limit=args.idle_limit,
    )
    controller = Controller(root, options, read_quota=SimulatedQuota(args.sub, args.quota_after, 60), show=show)
    monitor = Monitor(controller)
    watching = asyncio.ensure_future(monitor.run())
    pausing = asyncio.ensure_future(human_pause(controller, args.pause_at)) if args.pause_at else None
    try:
        await asyncio.wait_for(controller.run(), args.limit)
    except TimeoutError:
        print("[smoke] time limit reached: shutting down", flush=True)
    watching.cancel()
    monitor.look()  # the investigation may have ended between two looks
    if pausing:
        pausing.cancel()
    state = controller.state
    print("\n[smoke] ===== SUMMARY =====")
    print(f"status: {state.status}; outcome: {state.outcome}")
    for agent in state.agents.values():
        print(
            f"  {agent.id:20} {str(agent.spec):24} {agent.status:10} sessions={agent.sessions} "
            f"rejections={agent.rejections}"
        )
    for job in state.jobs.values():
        print(f"  {job.id} ({job.owner}): {job.status}, exit {job.exit_code}")
    print(controller.project.git("log", "--oneline"))
    shelved = controller.librarian.catalogue.shelves
    agents = {controller.librarian.folder(agent): agent for agent in state.agents.values()}
    monitor.note("an accepted subagent's work was shelved", any(agents[f].role == "subagent" for f in shelved))
    pending = controller.home.shelving
    monitor.note("the final work was shelved and placed", "phases/1/agents/primary" in shelved and not pending)
    for check, ok in monitor.results.items():
        print(f"  check: {check}: {'not observed' if ok is None else 'yes' if ok else 'NO'}")
    print(f"project kept at {root}")


if __name__ == "__main__":
    if not shutil.which("bwrap"):
        exit("bwrap is required")
    asyncio.run(main())
