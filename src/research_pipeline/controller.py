"""The controller: a deterministic program that runs one phase of an investigation (PROJECT.md §3–§7).

It owns the agent tree and makes every operational decision; it never makes a
scientific one. In outline:

- **Sessions.** Each agent has at most one persistent CLI session (a driver from
  the shared package :mod:`agent_toolkit`) inside its confinement. Messages reach agents
  live, during their turn; queued messages are delivered when a session starts.
  An agent keeps its session while it waits (for a review, a verdict, its parent's
  decision, a pause or a quota hold): its context is reset only at the context
  threshold, after the idle limit, or when the controller stops.
- **Tools.** Agents act through the MCP tools of :mod:`research_pipeline.tools`,
  which the controller offers each session through a
  :class:`~agent_toolkit.tools.ToolBridge`; calls are handled by the ``_tool_*`` methods.
- **Handoffs.** At the context threshold an agent is asked to update HANDOFF.md and
  end its turn; its session is then replaced by a fresh one. The request is
  repeated every further 25 points of context; an agent is never killed for it.
  The rules are those every agent controller shares (:mod:`agent_toolkit.handoff`).
- **Idle limit.** A session idle for ``idle_limit`` minutes (58: inside the prompt
  cache's hour) is asked for one turn to update HANDOFF.md, then closes; it closes
  without that turn while its CLI is held or its note is already saved. The
  agent's next input starts a fresh session from the note.
- **Idle and stalled agents.** An agent that ends its turn with nothing running or
  pending for it is nudged once; if it ends its turn idle again without using a
  tool, it has stalled: its parent is told, or the human alerted for the primary,
  or the proposal under review is withdrawn for the Reviewer.
- **Finishing.** The primary proposes COMPLETE or STOP and waits in its session,
  talk-only; the Reviewer examines the proposal's commit; COMPLETE needs its
  agreement, STOP is the primary's decision after the Reviewer's challenge. The
  verdict reaches the primary in the same session; the Reviewer keeps its own.
- **The library.** Accepted and cancelled subagents, and at the end the primary
  and the Reviewer, are shelved: their folders are catalogued and frozen, and the
  Librarian links their work from its pages (:mod:`research_pipeline.librarian`).
  At the end, the controller waits for it before exiting, if it can run.
- **Quota, pause, shutdown, crash.** Per-CLI usage limits pause that CLI's agents;
  the holds come from the shared usage guard
  (:class:`agent_toolkit.quota.Guard`). At a hold each affected agent updates
  HANDOFF.md and waits in its session. A human pause lets working agents finish
  their turn and wait in their sessions, and stops jobs; a shutdown hands every
  agent off and leaves jobs running. After a shutdown or a crash, agents restart
  from their handoffs and running jobs are reattached.
- **After the end.** The controller stays open for talks with the primary and the
  Reviewer (:mod:`research_pipeline.talks`). The phase reopens at a later run if the
  human changed its OBJECTIVES.md since the end; with the web page, only when its
  Reopen asks (``reopen``).
- **Phases.** A project's phases (:mod:`research_pipeline.phases`) share the human's
  files, the library and the Librarian, whose sessions the running phase's controller
  hosts. One phase runs at a time; the human can talk with the primary and the
  Reviewer of any other phase meanwhile. To run another phase (or to reopen this one
  from the web page), :meth:`Controller.hand_over` ends this controller, once the
  phase has ended or is paused, for that phase's.

All state changes happen on one asyncio loop, serialised by one lock: driver
events, tool calls and the background loops never interleave halfway.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import time
from collections.abc import Callable
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from agent_toolkit import CAPABILITIES, DRIVERS, Launch, Session, SessionError, SetupError, Spec, quota
from agent_toolkit.activity import ActivityLog
from agent_toolkit.handoff import HandoffWatch, check_threshold
from agent_toolkit.quota import Guard
from agent_toolkit.records import Busy, atomic_write, exclusive
from agent_toolkit.tools import ToolBridge

from research_pipeline import briefs, phases, prompts
from research_pipeline import jobs as joblib
from research_pipeline.librarian import LIBRARIAN, Librarian
from research_pipeline.phases import NOT_STARTED, Home
from research_pipeline.project import EMPTY_INDEX, INDEX, Project, ProjectError
from research_pipeline.state import ACTIVE, ENDED, FINISHED, Agent, Job, Options, State
from research_pipeline.talks import Talks
from research_pipeline.tools import ROLE_TOOLS, ToolError

#: Seconds between usage-quota reads.
QUOTA_INTERVAL = 120
#: Seconds between checks of jobs, retries and the human's files.
WATCH_INTERVAL = 2
#: Seconds between checks of the human's files.
HUMAN_INTERVAL = 10
#: Delays before restarting an agent whose session failed; after these, the human must resume it.
RETRY_DELAYS = (30, 120, 600)
#: Pending handoff reasons by precedence: a later one replaces an earlier one (it decides what follows the note).
HANDOFF_ORDER = ("idle", "context", "refresh", "quota", "shutdown")
#: Name under which every agent's CLI attaches the controller's MCP tool server.
MCP_SERVER = "research"
#: The agents the human chooses a CLI for at launch; their ids are their roles.
ROLES = ("primary", "reviewer", "librarian")

#: Transcript callback: ``show(kind, agent_id, text)`` with kind 'agent', 'tool', 'notice', 'human', 'controller'
#: or 'alert' (something the human must act on).
Show = Callable[[str, str, str], None]


class Controller:
    """Runs one phase of the investigation in one project folder until it ends or the human shuts it down."""

    def __init__(
        self,
        root: Path,
        options: Options | None = None,
        *,
        phase: int = 1,
        drivers=DRIVERS,
        read_quota: Callable[[str], list[quota.Window]] | None = None,
        show: Show | None = None,
        reopen: bool | None = None,
    ):
        """Run ``phase``; ``options`` override its stored launch options (None: keep them; a first run needs them).

        ``reopen`` decides what a finished phase whose OBJECTIVES.md changed since the
        end does: None reopens it (the command line, without the web page); False
        opens it talk-only, for the web page's reopening; True reopens it (that page's Reopen).

        ``drivers`` and ``read_quota`` (backend name -> usage windows; by default read
        by that backend's driver) can be replaced in tests.
        """
        self.project = Project(root, phase)
        self.launch_options = options
        self.drivers = drivers
        # The limits and the holds come from the state once it is loaded (see _load).
        self.guard = Guard(0, 0, read_quota or (lambda backend: quota.read(self.drivers[backend])))
        self.show: Show = show or (lambda kind, agent, text: None)
        # What each agent said, did and received, for the web app (hidden from agents, like all of .research/):
        # one log per phase, and the Librarian's, which serves them all. Talks reach other phases' logs.
        self.home = Home.load(self.project.home_file)  # what the phases share (loaded again at the start)
        self.activity = ActivityLog(self.project.activity, root=self.project.root)
        self.library_log = ActivityLog(self.project.library_activity, root=self.project.root)
        self.logs = {
            number: ActivityLog(self.project.at(number).activity, root=self.project.root)
            for number in {phase.number for phase in self.home.phases} - {phase}
        } | {phase: self.activity}
        self.state: State = State()
        self.sessions: dict[str, Session] = {}
        self.watches: dict[str, HandoffWatch] = {}  # agent id -> the handoff rules of its current session
        self.idle_since: dict[str, float] = {}  # agent id -> when its session last became idle (monotonic)
        self.processes: dict[str, subprocess.Popen] = {}  # job id -> process started by this controller
        self.bridge = ToolBridge()  # the agents' tools, one offer per session
        self.request: str | None = None  # 'shutdown' once the human asked to exit
        self.lock: asyncio.Lock | None = None
        self.done: asyncio.Event | None = None
        self._human_checked = 0.0
        self._quota_due = 0.0
        self._strays: set[str] = set()  # unexpected top-level entries already reported
        self.librarian = Librarian(self.project, lambda: self.state, lambda: self.home, self._notify, self._commit)
        self.closing = False  # the investigation ended; the Librarian places the final work
        self.talks = Talks(self)  # talk-only sessions with the primary and the Reviewer after the end
        self._reopen_told = False  # the human was told that their changes after the end reopen at the next run
        self.reopen = reopen
        # Every agent tool, by name: the controller's _tool_* methods and the Librarian's (each role sees its own).
        self.handlers: dict[str, Callable] = {
            name.removeprefix("_tool_"): getattr(self, name) for name in dir(self) if name.startswith("_tool_")
        } | self.librarian.handlers()

    # Running ------------------------------------------------------------------------------

    async def run(self) -> int:
        """Run until the investigation ends or the human shuts down; return an exit status."""
        self.lock, self.done = asyncio.Lock(), asyncio.Event()
        self.project.research.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            try:  # held for as long as this controller runs (see research_pipeline.cli.controller_running)
                stack.enter_context(
                    exclusive(self.project.lock_file, "Another controller is already running this project.")
                )
            except Busy as busy:
                raise ProjectError(str(busy)) from None
            self.project.prepare()
            self.home = Home.load(self.project.home_file)
            self.state = self._load()
            await self.bridge.start()
            loops = [asyncio.create_task(self._watch_loop()), asyncio.create_task(self._quota_loop())]
            try:
                async with self.lock:
                    await self._begin()
                await self.done.wait()
            finally:
                for task in loops:
                    task.cancel()
                await asyncio.gather(*loops, return_exceptions=True)
                for agent_id in list(self.sessions):  # after a forced exit, agents restart from handoffs next time
                    await self._close(agent_id)
                await self.talks.close(notes=False)
                await self.bridge.close()
                self._save()
        return 0

    @property
    def windows(self) -> list[quota.Window]:
        """The latest usage readings, for the terminal app."""
        return self.guard.windows

    @property
    def label(self) -> str:
        """One-word state of the investigation, with any quota holds."""
        holds = ", ".join(f"{backend} {hold['kind']}" for backend, hold in self.state.holds.items())
        talks = " (talk only)" if self.state.status in FINISHED else ""
        return self.state.status + talks + (f" (held: {holds})" if holds else "")

    def say(self, text: str) -> None:
        """The human's chat message, for the primary (from the terminal app)."""
        if text.strip():
            asyncio.ensure_future(self._locked(self._say(text)))

    def toggle_pause(self) -> None:
        """Pause a running investigation, or resume a paused one (from the terminal app)."""
        asyncio.ensure_future(self._locked(self._toggle()))

    def shutdown(self) -> None:
        """Hand every agent off cleanly, then stop the controller; jobs keep running (from the terminal app)."""
        self.request = "shutdown"
        asyncio.ensure_future(self._locked(self._shutdown()))

    def release(self) -> None:
        """Resume what only the human may resume while the investigation runs (from the terminal app).

        That is: CLIs held by a weekly or unreadable quota, and agents whose automatic
        retries are exhausted. Unlike the pause toggle, this never stops jobs.
        """
        asyncio.ensure_future(self._locked(self._release()))

    def hand_over(self) -> None:
        """End this controller for another phase's, or for this phase reopened (the web page).

        Only once the phase has ended (its talks then save their notes) or is paused (its
        sessions then save their handoffs, as at a shutdown).
        """
        if self.state.status == "paused":
            self.shutdown()
            return
        if self.state.status not in FINISHED:
            raise ValueError(f"phase {self.project.phase} is {self.state.status}: pause it first")
        self.request = "reopen"
        asyncio.ensure_future(self._locked(self._hand_over()))

    async def _hand_over(self) -> None:
        await self.talks.close()
        assert self.done is not None  # set by run(), within which this runs
        self.done.set()

    def human_changes(self) -> list[str]:
        """The human's files changed since the phase's end, by content (empty before an end)."""
        if self.state.status not in FINISHED:
            return []
        return self.project.human_changes(self.state.human, self.state.end_commit)

    def objectives_changed(self) -> bool:
        """True if the phase's OBJECTIVES.md changed since its end: what reopens it (PROJECT.md §4)."""
        return self.project.relative(self.project.objectives) in self.human_changes()

    async def talk(self, phase: int, agent_id: str, text: str) -> str:
        """The human's ``text`` to the primary or the Reviewer of another phase: a talk (research_pipeline.talks)."""
        if self.lock is None:
            raise ValueError("the investigation is still starting")
        async with self.lock:
            return await self.talks.message_phase(phase, agent_id, text)

    def log(self, agent_id: str) -> ActivityLog:
        """The activity log ``agent_id`` of this phase writes to (the Librarian's is the project's)."""
        return self.library_log if agent_id == LIBRARIAN else self.activity

    @property
    def releasable(self) -> bool:
        """True if something waits for the human's :meth:`release`."""
        return self.state.status == "running" and (
            any(hold["kind"] != "short" for hold in self.state.holds.values())
            or any(
                a.status == "paused" and a.pause_reason == "failure" and a.retry_at is None
                for a in self.state.agents.values()
            )
        )

    # The human's actions on one agent, and live settings (from the web app) ----------------------

    def actions(self, agent: Agent) -> list[str]:
        """What the human may do to ``agent`` now (see :meth:`act`)."""
        if self.state.status in FINISHED:
            return ["message"] if self.talks.open(agent) else []  # talk-only after the end
        if agent.status in ENDED:
            return []
        allowed = [] if agent.status == "submitted" else ["message"]
        if agent.status in (*ACTIVE, "resting") or agent.status == "paused" and agent.pause_reason != "held":
            allowed.append("pause")
        if (
            agent.status == "paused"
            and agent.pause_reason in ("held", "human", "failure")
            and self.state.status == "running"
        ):
            allowed.append("resume")
        if agent.status == "running" and not agent.handoff_reason:
            allowed.append("handoff")
        if agent.role == "subagent":
            allowed.append("cancel")
        return allowed

    async def act(self, action: str, agent_id: str, text: str = "") -> str:
        """The human's ``action`` on one agent: 'message' (``text``), 'pause', 'resume', 'handoff' or 'cancel'.

        Return a confirmation; raise ValueError if it cannot be done now.
        """
        if self.lock is None:
            raise ValueError("the investigation is still starting")
        async with self.lock:
            agent = self.state.agents.get(agent_id)
            if agent is None:
                raise ValueError(f"there is no agent {agent_id}")
            if action not in self.actions(agent):
                raise ValueError(f"{action} is not possible for {agent_id} now ({agent.status})")
            reply = await getattr(self, f"_human_{action}")(agent, text)
            await self._after_change()
            self._save()
            return reply

    async def configure(self, values: dict) -> None:
        """Change settings while the investigation runs.

        'threshold', 'short_limit', 'weekly_limit', 'max_agents' and 'idle_limit'
        (minutes, 0: none) apply at once;
        'primary', 'reviewer' and 'librarian' (BACKEND:MODEL:EFFORT) from that agent's next
        session, 'coding' and 'analysis' (the models the prompt recommends for subagents) from
        each agent's next session, and 'backends' (the CLIs for subagents) from the next spawn.
        Raise ValueError for an invalid value (nothing is changed then).
        """
        if self.lock is None:
            raise ValueError("the investigation is still starting")
        specs = {role: Spec.parse(values[role], role, self.drivers) for role in ROLES if role in values}
        recommended = {
            task: Spec.parse(values[task], task, self.drivers) for task in ("coding", "analysis") if task in values
        }
        if "backends" in values and (not values["backends"] or set(values["backends"]) - set(self.drivers)):
            raise ValueError(f"backends must be some of {', '.join(self.drivers)}")
        threshold = check_threshold(values["threshold"], "the handoff threshold") if "threshold" in values else None
        for name in ("short_limit", "weekly_limit"):
            if name in values and not 0 <= float(values[name]) <= 100:
                raise ValueError(f"{name} must be a percentage from 0 to 100")
        if "max_agents" in values and int(values["max_agents"]) < 2:
            raise ValueError("at least two sessions are needed: the primary and the Reviewer")
        if "idle_limit" in values and float(values["idle_limit"]) < 0:
            raise ValueError("the idle limit must be 0 (none) or a number of minutes")
        async with self.lock:
            options = self.state.options
            if threshold is not None:
                options.threshold = threshold
                for watch in self.watches.values():  # live sessions follow the new threshold at their next reading
                    watch.threshold = threshold
            for name in ("short_limit", "weekly_limit"):
                if name in values:
                    setattr(options, name, float(values[name]))
                    setattr(self.guard, name, float(values[name]))
            if "max_agents" in values:
                options.max_agents = int(values["max_agents"])
            if "idle_limit" in values:
                options.idle_limit = float(values["idle_limit"])
            for role, spec in specs.items():  # its live session, if any, keeps its CLI until it hands off
                setattr(options, role, str(spec))
                if role in self.state.agents:
                    agent = self.state.agents[role]
                    agent.backend, agent.model, agent.effort = spec.backend, spec.model, spec.effort
            for task, spec in recommended.items():  # in the instructions of each agent's next session
                setattr(options, task, str(spec))
            if "backends" in values:
                options.backends = list(values["backends"])
            self.show(
                "controller", "primary", "Settings changed: " + ", ".join(f"{k} = {v}" for k, v in values.items())
            )
            await self._resume_agents({"slots"})
            self._save()

    async def _human_message(self, agent: Agent, text: str) -> str:
        """The human writes to any agent; its parent gets a copy, so their plans stay consistent."""
        if not text.strip():
            raise ValueError("the message is empty")
        self.show("human", agent.id, text)
        if self.talks.open(agent):  # after the end: a talk, which the investigation never sees
            return await self.talks.message(agent, text)
        if self.state.status in FINISHED:
            raise ValueError("the investigation has ended: only the primary and the Reviewer can be talked to")
        delivered = await self._talk(agent, prompts.human_message(text))
        parent = self.state.agents.get(agent.parent or "")
        if parent and parent.status not in ENDED:
            await self._notify(parent, prompts.human_to_child(agent.id, text), sender="human")
        return f"Delivered to {agent.id}." if delivered else f"{agent.id} receives your message when it next works."

    async def _talk(self, agent: Agent, notice: str) -> bool:
        """Deliver the human's ``notice`` now if the agent can answer; True if it was delivered.

        An agent answers in its session whatever it waits for (a review, a pause:
        then talk-only, as spawn and run_job are refused), and a resting agent is
        woken. Otherwise (its CLI is held, it saves its note, or it has no session
        and may not start one) the notice waits for its next turn.
        """
        self._queue(agent, notice, "human")
        if agent.handoff_reason or self._blocked(agent.backend):
            return False
        if agent.id in self.sessions:
            if agent.status == "resting":
                agent.status = "running"
            await self._flush(agent)
        elif agent.status == "resting":
            await self._wake(agent)
        return agent.id in self.sessions and not agent.notices

    async def _human_pause(self, agent: Agent, text: str = "") -> str:
        """Hold one agent: it ends its turn and waits in its session; its subagents and jobs keep working."""
        await self._hold_agent(agent, "held", prompts.paused_by_human())
        self.show("controller", agent.id, "Paused by the human; its subagents and jobs keep working.")
        parent = self.state.agents.get(agent.parent or "")
        if parent and parent.status not in ENDED:
            await self._notify(parent, prompts.human_paused(agent.id))
        return f"{agent.id} ends its turn, then waits until you resume it."

    async def _hold_agent(self, agent: Agent, reason: str, notice: str) -> None:
        """Pause ``agent`` for ``reason``, keeping its session; one in the middle of a turn is asked to end it.

        An agent saving its note finishes that first (its handoff decides what
        becomes of its session); its news waits for it meanwhile.
        """
        session = self.sessions.get(agent.id)
        if session and session.busy and not agent.handoff_reason:
            await session.steer(notice)
            self._record(agent, notice)
        agent.status, agent.pause_reason = "paused", reason

    async def _human_resume(self, agent: Agent, text: str = "") -> str:
        """Resume one agent the human held (or that failed): it continues in its session, or from its handoff."""
        agent.pause_reason, agent.failures, agent.retry_at = "resume", 0, None
        await self._resume_agents({"resume"})
        parent = self.state.agents.get(agent.parent or "")
        if parent and parent.status not in ENDED:
            await self._notify(parent, prompts.human_resumed(agent.id))
        if agent.status == "paused":
            return f"{agent.id} continues as soon as it can run ({agent.pause_reason})."
        return f"{agent.id} resumed."

    async def _human_handoff(self, agent: Agent, text: str = "") -> str:
        """Make one agent continue in a fresh session (e.g. when it seems confused)."""
        await self._request_handoff(agent, "refresh")
        return f"{agent.id} updates HANDOFF.md, then continues in a fresh session."

    async def _human_cancel(self, agent: Agent, text: str = "") -> str:
        """Cancel a subagent, its subagents and their jobs, as its parent's cancel tool does; the parent is told."""
        cancelled = await self._cancel_tree(agent)
        await self.librarian.shelve(cancelled, self._commit(f"human: cancelled {agent.id}"))
        self.show("controller", agent.id, "Cancelled by the human, with its subagents and jobs.")
        parent = self.state.agents.get(agent.parent or "")
        if parent and parent.status not in ENDED:
            await self._notify(parent, prompts.human_cancelled(agent.id), sender="human")
        await self._resume_agents({"slots"})
        return f"Cancelled {agent.id}, its subagents and its jobs."

    async def _locked(self, coroutine) -> None:
        """Run ``coroutine`` under the lock; report (never propagate) an unexpected error."""
        assert self.lock is not None  # set by run(), whose loops are the only callers
        try:
            await self.lock.acquire()
        except asyncio.CancelledError:  # cancelled while waiting (e.g. at the exit): the coroutine never runs
            coroutine.close()
            raise
        try:
            await coroutine
        except Exception as error:
            self.show("controller", "", f"Internal error (the investigation continues): {error!r}")
        finally:
            self.lock.release()

    def _load(self) -> State:
        """Load the phase's stored state, or create it on a first run; apply new launch options.

        The Librarian's record is the project's (every phase shares it); it joins the phase's agents here.
        """
        if self.project.state_file.exists():
            state = State.load(self.project.state_file)
            if self.launch_options:
                state.options = self.launch_options
        else:
            state = State(options=self.launch_options or Options())
        options = state.options
        unknown = set(options.backends) - set(self.drivers)
        try:
            specs = {role: Spec.parse(getattr(options, role), f"--{role}", self.drivers) for role in ROLES}
        except ValueError as error:
            raise ProjectError(str(error)) from None
        if not options.backends:
            raise ProjectError("--backends must name at least one CLI for subagents")
        if unknown:
            raise ProjectError(f"Unknown backend(s): {', '.join(sorted(unknown))}; known: {', '.join(self.drivers)}")
        if options.max_agents < 2:
            raise ProjectError("--max-agents must be at least 2: the primary and the Reviewer.")
        if self.home.librarian is not None:
            state.agents[LIBRARIAN] = self.home.librarian
        for agent_id, spec in specs.items():
            agent = state.agents.setdefault(
                agent_id,
                Agent(
                    agent_id,
                    agent_id,
                    None,
                    spec.backend,
                    spec.model,
                    spec.effort,
                    status="paused" if agent_id == "primary" else "resting",
                    pause_reason="start" if agent_id == "primary" else None,
                ),
            )
            agent.backend, agent.model, agent.effort = spec.backend, spec.model, spec.effort
        self.guard.short_limit, self.guard.weekly_limit = options.short_limit, options.weekly_limit
        self.guard.holds = state.holds  # the guard keeps its holds in the stored state
        self.home.librarian = state.agents[LIBRARIAN]
        if self.home.phase(self.project.phase) is None:  # e.g. a first phase prepared by hand (--no-web)
            self.home.phases.append(phases.Phase(self.project.phase, f"Phase {self.project.phase}"))
        return state

    async def _begin(self) -> None:
        """Start, resume or reopen the phase."""
        state, home, number = self.state, self.home, self.project.phase
        clean = state.status in ("paused", "pausing") or state.status in FINISHED
        for agent in state.agents.values():  # sessions of a previous controller ended with it
            if agent.status in ACTIVE:
                agent.status, agent.pause_reason = "paused", "restart"
            agent.handoff_reason = None
        changed = self.project.uncommitted()
        state.human = state.human or self.project.human_fingerprint()  # changes while off are reported below
        human = self.human_changes()
        switched = home.active is not None and home.active != number  # another phase ran meanwhile
        home.active = number
        primary = state.agents["primary"]
        if not primary.sessions:  # the phase's first run
            self._commit(f"controller: phase {number} started")
            if len(home.phases) > 1:  # the library now serves one more phase
                summary = next(item for item in phases.summaries(self.project, home, state) if item.number == number)
                self._queue(state.agents[LIBRARIAN], prompts.new_phase(summary.line()))
        elif state.status in FINISHED and (not self.objectives_changed() or self.reopen is False):
            if changed:
                self._commit("controller: changes after the end")
            self.closing = bool(home.shelving)  # the Librarian places what was left pending; talks are open
            state.holds.clear()
            await self._check_quota()
            librarian = state.agents[LIBRARIAN]
            if home.shelving and librarian.status == "resting":
                await self._wake(librarian)
            await self._resume_agents()
            self._announce_talks()
            self._save()
            return
        elif state.status in FINISHED:
            await self.talks.discard()
            outcome = state.status.upper()
            self._commit("human: changes before reopening")
            state.status, state.proposal, state.end_commit = "running", None, None
            state.human = self.project.human_fingerprint()  # the notice below reports these changes
            primary.status, primary.pause_reason = "paused", "reopen"
            self._queue(primary, prompts.reopened(outcome, human))
            self.show("controller", "primary", f"Phase {number} reopened after {outcome}.")
        elif clean and changed:
            self._commit("controller: changes made while paused or shut down (by the human or by running jobs)")
            self._announce_changes(changed)
        elif changed:
            self._commit("controller: work recovered after a restart")
        later = [item for item in phases.summaries(self.project, home, state) if item.number > number]
        if switched and primary.sessions and [item for item in later if item.status != NOT_STARTED]:
            self._queue(primary, prompts.later_phases(phases.listing(later)))
        state.status = "running"
        state.holds.clear()  # running again is the human's resume: holds are re-read now
        await self._check_quota()
        await self._resume_agents()
        await self._deliver_queued()
        self._save()

    # Sessions -----------------------------------------------------------------------------

    def _working(self) -> list[Agent]:
        """Agents in the middle of a turn, or saving their note: a pause or shutdown waits for them."""
        return [
            agent
            for agent in self.state.agents.values()
            if agent.id in self.sessions and (self.sessions[agent.id].busy or agent.handoff_reason)
        ]

    def _open(self) -> int:
        """Live sessions counted against the cap, idle ones included; the Librarian's is not counted."""
        return len([agent_id for agent_id in self.sessions if agent_id != LIBRARIAN])

    def _slot_free(self) -> bool:
        """True if another session may start: counted sessions stay below the cap."""
        return self._open() < self.state.options.max_agents

    def _works(self, agent: Agent) -> bool:
        """True if ``agent`` may work now: the investigation runs, or it ended and the Librarian places the rest."""
        return self.state.status == "running" or (self.closing and agent.role == "librarian")

    def _scope(self, agent: Agent) -> tuple[Path, ...]:
        """What the agent's confinement leaves writable (PROJECT.md §2)."""
        scope = [self.project.agent_dir(agent.id)]
        if agent.role == "primary":
            scope += [self.project.phase_dir / INDEX, self.project.status_file, self.project.report]
        elif agent.role == "reviewer":
            scope.append(self.project.reviews)
        return tuple(scope)

    async def _start_session(self, agent: Agent) -> None:
        """Start a fresh session for ``agent``, opening with its task, handoff and pending notices."""
        await self._close(agent.id)
        folder = self.project.agent_dir(agent.id)
        folder.mkdir(parents=True, exist_ok=True)
        if not (folder / INDEX).exists():
            first = "- [TASK.md](TASK.md) — The task from my parent.\n" if (folder / "TASK.md").exists() else ""
            atomic_write(folder / INDEX, EMPTY_INDEX + first, root=self.project.root)
        agent.sessions += 1
        agent.started = time.time()
        notices, agent.notices = agent.notices, []
        if agent.role == "librarian" and self.home.shelving and not notices:  # e.g. after a restart
            notices = [prompts.shelving_pending(self.home.shelving)]
        number = agent.sessions
        tools = self.bridge.offer(
            agent.id,
            ROLE_TOOLS[agent.role],
            lambda tool, args: self._on_tool(agent.id, number, tool, args),
            name=MCP_SERVER,
        )
        launch = Launch(
            agent=agent.id,
            cwd=folder,
            instructions=prompts.instructions(agent, self.project, self.state.options),
            message=prompts.opening(agent, self.project, self.state.options, notices, self._phases()),
            model=agent.model,
            effort=agent.effort,
            tools=CAPABILITIES,
            mcp=tools,
            writable=self._scope(agent),
            hidden=(self.project.research,),
            log=self.project.session_log(agent.id, agent.sessions),
        )
        session = self.drivers[agent.backend](launch, self._on_event)
        self._record(agent, launch.message)
        agent.status, agent.pause_reason, agent.retry_at, agent.handoff_reason = "running", None, None, None
        # A new session's context use is unknown until its CLI reports it.
        agent.nudged, agent.tokens, agent.window = False, None, None
        # Its handoff rules: a context handoff is called off if the CLI compacts below the threshold.
        self.watches[agent.id] = HandoffWatch(
            self.state.options.threshold, folder / "HANDOFF.md", cancel_on_recovery=True
        )
        self.sessions[agent.id] = session
        try:
            await session.start()
        except Exception as error:
            await self._close(agent.id)
            agent.notices = notices + agent.notices
            # Personal setup would load again on every retry: only the human can fix it.
            await self._failed(
                agent, f"{agent.id}: its session could not start: {error}.", retry=not isinstance(error, SetupError)
            )
            return
        self.show("controller", agent.id, f"Session {agent.sessions} started ({agent.spec}).")
        self._save()

    async def _close(self, agent_id: str) -> None:
        """Close an agent's session, if it has one; its status stays (it waits without a session)."""
        self.bridge.withdraw(agent_id)
        self.watches.pop(agent_id, None)
        self.idle_since.pop(agent_id, None)
        session = self.sessions.pop(agent_id, None)
        if session:
            await session.close()

    async def _failed(self, agent: Agent, reason: str, retry: bool = True) -> None:
        """An agent's session ended unexpectedly (it is closed already).

        An agent at work is paused and restarted from its handoff after a delay;
        without ``retry`` (or once the automatic retries are used up) it waits for the
        human's Ctrl+R. One that only waited (resting, submitted, paused) keeps
        waiting: its next input starts a fresh session.
        """
        handoff, agent.handoff_reason = agent.handoff_reason, None
        if agent.status not in ACTIVE:
            self.show("controller", agent.id, f"{reason} It was waiting; its next input starts a fresh session.")
        elif handoff == "idle":
            agent.status = "resting"
        elif handoff == "quota":
            agent.status, agent.pause_reason = "paused", "quota"
        else:
            agent.status, agent.pause_reason = "paused", "failure"
            agent.failures += 1
            if not retry:
                agent.retry_at = None
                self.show("controller", agent.id, f"{reason} Fix this, then press Ctrl+R to retry.")
            elif agent.failures <= len(RETRY_DELAYS):
                delay = RETRY_DELAYS[agent.failures - 1]
                agent.retry_at = time.time() + delay
                self.show("controller", agent.id, f"{reason} Restarting from its handoff in {delay} s.")
            else:
                agent.retry_at = None
                self.show("controller", agent.id, f"{reason} It failed {agent.failures} times: press Ctrl+R to retry.")
        await self._pause_progress()
        self._save()

    async def _resume_agents(self, reasons: set[str | None] | None = None) -> None:
        """Bring paused agents (only those paused for ``reasons``, if given) back to work where they may run now.

        An agent that kept its session continues in it, told why it paused; one at
        the context threshold, or without a session, starts a fresh one if a slot is free.
        """
        state = self.state
        if state.status != "running" and not self.closing:
            return
        order = {"primary": 0, "reviewer": 1, "librarian": 2, "subagent": 3}
        for agent in sorted(state.agents.values(), key=lambda a: (order[a.role], a.sessions)):
            if agent.status != "paused" or (reasons and agent.pause_reason not in reasons) or not self._works(agent):
                continue
            if agent.pause_reason == "held" and not (reasons and "held" in reasons):
                continue  # held by the human on its own: only its own resume restarts it
            pending = self._under_review()
            if agent.role == "reviewer" and not pending and not agent.notices:
                agent.status, agent.pause_reason = "resting", None
                continue
            if agent.role == "librarian" and not self.home.shelving and not agent.notices:
                agent.status, agent.pause_reason = "resting", None
                continue
            if self._blocked(agent.backend):
                agent.pause_reason = "quota"
                continue
            reason, watch = agent.pause_reason, self.watches.get(agent.id)
            if watch is not None and watch.full:  # it waited at the threshold: it continues in a fresh session
                await self._close(agent.id)
            if agent.id in self.sessions:
                assert watch is not None  # a session's watch is added and removed with it
                agent.status, agent.pause_reason = "running", None
                watch.clear()
                notice = prompts.continue_after(reason)
                if notice:
                    self._queue(agent, notice)
                await self._flush(agent)
            elif agent.role != "librarian" and not self._slot_free():
                agent.pause_reason = "slots"
                continue
            else:
                if pending and agent.role == "reviewer" and not any("Review round" in n for n in agent.notices):
                    self._queue(agent, prompts.review_request(**self._review_args()))
                if pending and agent.role == "primary":
                    assert state.proposal is not None  # pending: a proposal is under review
                    self._queue(agent, prompts.talk_only(state.proposal["round"]))
                await self._start_session(agent)
            parent = state.agents.get(agent.parent or "")
            if reason == "quota" and agent.status == "running" and parent and parent.status not in ENDED:
                await self._notify(parent, f"[controller] Subagent {agent.id} has resumed after its quota pause.")

    # Driver events --------------------------------------------------------------------------

    def _on_event(self, session: Session, kind: str, data: dict) -> None:
        """Driver callback: queue the event for handling under the lock, in arrival order."""
        asyncio.ensure_future(self._locked(self._event(session, kind, data)))

    async def _event(self, session: Session, kind: str, data: dict) -> None:
        agent_id = session.launch.agent
        if self.sessions.get(agent_id) is not session:
            return  # from a session that has already been replaced or closed
        agent = self.state.agents[agent_id]
        self.log(agent_id).event(agent_id, kind, data)
        if kind == "text":
            agent.activity = data["text"].strip().splitlines()[0][:200] if data["text"].strip() else agent.activity
            self.show("agent", agent_id, data["text"])
        elif kind == "tool":
            agent.activity, agent.nudged = data["text"][:200], False
            if data.get("server") != MCP_SERVER:  # the controller's own tools are shown when it handles them
                self.show("tool", agent_id, data["text"])
        elif kind == "context":
            await self._context(agent, data.get("tokens"), data.get("window"))
        elif kind == "turn_ended" and data.get("pending"):
            pass  # a message reached the CLI too late for this turn: it runs next; act once the session settles
        elif kind == "turn_ended" and data.get("failed"):
            # A failed turn (e.g. an API outage) restarts the agent from its handoff after a delay.
            await self._close(agent_id)
            await self._failed(agent, f"{agent_id}: its turn failed.")
        elif kind == "turn_ended":
            await self._turn_ended(agent, data.get("text") or "")
            self._save()
        elif kind == "exited":  # sessions the controller closes are gone from self.sessions: this one died
            await self._close(agent_id)
            await self._failed(agent, f"{agent_id}: {data.get('reason', 'its session ended')}.")
        await self._after_change()

    async def _context(self, agent: Agent, tokens: int | None, window: int | None) -> None:
        """New context reading: trigger the handoff at the threshold and repeat it every further 25 points.

        A context handoff is called off if the CLI compacts below the threshold (the agent is not told).
        Context use is only what the session's CLI reports. Until it has reported both tokens and
        window, the fill is unknown and triggers nothing; it is never estimated.
        """
        watch = self.watches.get(agent.id)
        if watch is None:
            return
        action = watch.reading(tokens, window)
        agent.tokens, agent.window = watch.tokens, watch.window
        if action == "request" and agent.status == "running":
            await self._request_handoff(agent, "context", f"{watch.fill:.0%}")
        elif action == "recovered" and agent.handoff_reason == "context":
            agent.handoff_reason = None  # compacted below the threshold: the cycle restarts
            if agent.status == "handing_off":
                agent.status = "running"
        elif action == "remind" and agent.handoff_reason:
            await self._send(agent, prompts.handoff_reminder(f"{watch.fill:.0%}"))

    async def _turn_ended(self, agent: Agent, text: str) -> None:
        """An agent ended its turn (``text`` is its final message)."""
        agent.failures = 0
        watch = self.watches.get(agent.id)
        if watch is not None and watch.unmeasured():
            # Without readings no handoff can be triggered: the agent continues, and the human is told once.
            self.show(
                "alert",
                agent.id,
                f"{agent.id}: its CLI has not reported context use after a full turn, "
                "so its handoffs cannot be triggered in this session.",
            )
        if agent.role == "librarian" and not agent.handoff_reason and self._works(agent):
            notice = self.librarian.turn_ended()  # its page changes are committed
            if notice:
                self._queue(agent, notice)
        if agent.handoff_reason:
            await self._check_handoff(agent)
        elif agent.status != "running" or not self._works(agent):
            return  # it waits (for a verdict, its parent, a pause or a quota hold): its news waits too
        elif agent.notices:
            await self._flush(agent)
        elif agent.role == "reviewer" and not self._under_review():
            agent.status = "resting"  # it answered the human between rounds
        elif agent.role == "librarian" and not self.home.shelving:
            agent.status = "resting"  # nothing is pending: the next request wakes it
        elif self._idle(agent):
            if agent.nudged:  # told it was idle, and it ended its turn idle again without using a tool
                await self._stalled(agent, text)
            else:
                agent.nudged = True
                await self._send(
                    agent,
                    prompts.librarian_nudge(self.home.shelving)
                    if agent.role == "librarian"
                    else prompts.nudge(agent.role, self._awaiting(agent)),
                )

    def _idle(self, agent: Agent) -> bool:
        """True unless the agent is waiting: for a running or paused subagent, a running job or a review."""
        busy_children = [c for c in self.state.children(agent.id) if c.status in ACTIVE or c.status == "paused"]
        waiting = agent.role == "primary" and self._under_review()
        return not busy_children and not self.state.running_jobs(agent.id) and not waiting

    def _awaiting(self, agent: Agent) -> list[str]:
        """The agent's subagents whose submitted results await its decision."""
        return [child.id for child in self.state.children(agent.id) if child.status == "submitted"]

    async def _stalled(self, agent: Agent, text: str) -> None:
        """An idle agent stopped working (PROJECT.md §3, "Waiting, idle and stalled agents"); it keeps its session."""
        last = text.strip() or "(no final message)"
        if agent.role == "subagent":  # its parent decides
            assert agent.parent is not None  # every subagent has one
            self.show("controller", agent.id, "Stalled: its parent is told.")
            await self._notify(self.state.agents[agent.parent], prompts.stalled(agent.id, last))
        elif agent.role == "primary":  # the human's reply continues it
            self.show("alert", "primary", f"The primary has stopped and is waiting for you. Its last message:\n{last}")
        elif agent.role == "librarian":  # the work stays catalogued and frozen; its requests wait
            self.show(
                "alert",
                LIBRARIAN,
                f"The Librarian has stopped with shelving requests pending ({', '.join(self.home.shelving)}). "
                f"Its last message:\n{last}",
            )
            await self._closed(force=True)
        else:  # the Reviewer: without a verdict, the proposal under review is withdrawn
            proposal, self.state.proposal = self.state.proposal, None
            agent.status = "resting"
            if proposal and not proposal.get("reviewed"):
                self._commit(f"reviewer: stalled in round {proposal['round']}; proposal withdrawn")
                self.show(
                    "controller", "reviewer", f"Stalled without a verdict: round {proposal['round']} is withdrawn."
                )
                await self._notify(
                    self.state.agents["primary"], prompts.review_withdrawn(proposal["kind"], proposal["round"])
                )

    # Messages ---------------------------------------------------------------------------------

    def _record(self, agent: Agent, text: str, sender: str = "controller", origin: str | None = None) -> None:
        """Keep a message ``agent`` receives in its activity log (``sender`` as seen from the agent)."""
        self.log(agent.id).add(agent.id, "message", text, sender=sender, origin=origin)

    def _queue(self, agent: Agent, text: str, sender: str = "controller", origin: str | None = None) -> None:
        """Keep a notice for the agent's next delivery (recorded now)."""
        self._record(agent, text, sender, origin)
        agent.notices.append(text)

    async def _send(
        self, agent: Agent, text: str, sender: str = "controller", origin: str | None = None, record: bool = True
    ) -> None:
        """Deliver ``text`` to the agent's session now (into its turn, or starting one), else keep it for later.

        ``sender`` and ``origin`` say who it comes from (see :mod:`agent_toolkit.activity`);
        without ``record`` it was recorded already (queued notices).
        """
        if record:
            self._record(agent, text, sender, origin)
        session = self.sessions.get(agent.id)
        if session is None:
            agent.notices.append(text)
            return
        try:
            await session.send(text)
        except (TimeoutError, SessionError, OSError):
            agent.notices.append(text)
            return
        self.idle_since.pop(agent.id, None)  # a turn runs: the idle clock starts again when it ends
        self.show("notice", agent.id, text)

    async def _notify(self, agent: Agent, text: str, sender: str = "controller", origin: str | None = None) -> None:
        """Queue a notice; deliver it now to an agent at work, wake a resting one (not while paused or handing off)."""
        self._queue(agent, text, sender, origin)
        if not self._works(agent) or agent.handoff_reason:
            return
        if agent.status == "resting":
            await self._wake(agent)
        elif agent.status == "running":
            await self._flush(agent)

    async def _flush(self, agent: Agent) -> None:
        """Send the agent's queued notices into its session, if it has one."""
        if agent.notices and agent.id in self.sessions:
            pending, agent.notices = agent.notices, []
            await self._send(agent, "\n\n".join(pending), record=False)

    async def _flush_running(self, agent: Agent) -> None:
        if agent.status == "running" and not agent.handoff_reason and self._works(agent):
            await self._flush(agent)

    async def _wake(self, agent: Agent) -> None:
        """Bring a waiting agent (resting, or a submitted subagent) back to work with its queued notices.

        It continues in its session if it kept one, else in a fresh session once its CLI and a slot allow.
        """
        agent.status, agent.pause_reason = "paused", "wake"
        await self._resume_agents({"wake"})

    async def _deliver_queued(self) -> None:
        """After a resume or a restart: deliver what queued meanwhile, waking resting agents that received news."""
        for agent in list(self.state.agents.values()):
            if agent.notices and agent.status == "resting":
                await self._wake(agent)
            elif agent.notices:
                await self._flush_running(agent)

    async def _say(self, text: str) -> None:
        """The human's chat message to the primary (see :meth:`_human_message`)."""
        await self._human_message(self.state.agents["primary"], text)
        self._save()

    def _announce_changes(self, paths: list[str]) -> None:
        """Tell the primary, and the owners of changed agent folders, what changed while paused or shut down."""
        notice = prompts.resumed(paths)
        agents = f"{self.project.folder}/agents/"
        owners = {
            path.removeprefix(agents).split("/")[0]
            for path in paths
            if path.startswith(agents) and "/" in path[len(agents) :]
        }
        for agent_id in {"primary", *owners} & set(self.state.agents):
            self._queue(self.state.agents[agent_id], notice)
        self.show(
            "controller", "primary", "Changed while paused (by the human or by running jobs):\n" + "\n".join(paths[:20])
        )

    # Handoffs ---------------------------------------------------------------------------------

    def _noted(self, agent: Agent) -> bool:
        """True if the agent saved its note for a request that has since been settled (e.g. at a quota hold)."""
        watch = self.watches.get(agent.id)
        return bool(watch and watch.reason and not agent.handoff_reason and watch.saved())

    async def _request_handoff(self, agent: Agent, reason: str, detail: str = "") -> None:
        """Ask an agent with a session to update HANDOFF.md and end its turn (an idle one takes a turn for it).

        While one is pending, a reason later in :data:`HANDOFF_ORDER` takes its place:
        it decides what follows the note (see :meth:`_check_handoff`).
        """
        watch = self.watches.get(agent.id)
        if watch is None:
            return
        if agent.handoff_reason:
            if HANDOFF_ORDER.index(reason) > HANDOFF_ORDER.index(agent.handoff_reason):
                agent.handoff_reason = watch.reason = reason
            return
        watch.clear()
        watch.request(reason)
        agent.handoff_reason = reason
        if agent.status == "running":
            agent.status = "handing_off"
        self.show("controller", agent.id, f"Handoff requested ({reason}).")
        await self._send(agent, prompts.handoff_request(reason, detail))

    async def _check_handoff(self, agent: Agent) -> None:
        """At a turn's end during a handoff: once HANDOFF.md is written, close or keep the session.

        A turn that ended without writing it is asked again, up to three times; then
        the handoff goes on anyway, and a successor starts from the existing HANDOFF.md.
        After a context or a forced handoff the agent continues in a fresh session;
        after an idle one it rests without a session; at a quota hold it waits in its
        session (unless its context is at the threshold); at a shutdown the session ends.
        """
        watch = self.watches[agent.id]
        saved = watch.saved()
        if not saved and watch.ask_again():
            await self._send(agent, prompts.HANDOFF_MISSING)
            return
        if not saved:  # it stopped working without updating it: its successor starts from the last one
            self.show("controller", agent.id, "HANDOFF.md was not updated; continuing from the existing one.")
        news = bool(agent.notices)  # news that arrived during the handoff wakes a resting agent (not the below)
        problems = self.project.check_layout(agent)
        if problems:
            self._queue(agent, _layout_notice(problems))
        reason, agent.handoff_reason = agent.handoff_reason, None
        if self._works(agent):  # while paused, the human's edits are committed (and reported) at resume
            self._commit(f"{agent.id}: handoff ({reason})")
        if agent.status == "handing_off":
            agent.status = "running"
        if reason in ("quota", "shutdown") and not watch.full and self.request != "shutdown":
            # It waits in its session (a quota hold, or a shutdown called off) until it may continue.
            if agent.status == "running":
                agent.status, agent.pause_reason = "paused", "quota" if reason == "quota" else "human"
                parent = self.state.agents.get(agent.parent or "")
                if reason == "quota" and parent and parent.status not in ENDED:
                    await self._notify(parent, prompts.quota_paused(agent.id, agent.backend))
            if agent.status == "paused":
                await self._resume_agents({agent.pause_reason})  # at once if nothing holds it any more
            return
        await self._close(agent.id)
        if reason == "idle":
            self.show("controller", agent.id, "Idle: its session closed; its next input starts a fresh one.")
        if agent.status != "running" or self.request == "shutdown":
            return  # it keeps waiting (paused, submitted, resting), now without a session
        if reason == "idle":
            agent.status = "resting"
            if news:
                await self._wake(agent)
        elif self._works(agent) and not self._blocked(agent.backend):
            await self._start_session(agent)
        else:
            agent.status = "paused"
            agent.pause_reason = "quota" if self._blocked(agent.backend) else "human"
            self.show("controller", agent.id, f"Paused ({agent.pause_reason}).")

    async def _idle_out(self, agent: Agent) -> None:
        """A session reached the idle limit: one turn to update HANDOFF.md, then it closes.

        It closes at once while its CLI is held (no turn may run) or its note is
        already saved; the agent's next input starts a fresh session from the note.
        """
        if self._blocked(agent.backend) or self._noted(agent):
            await self._close(agent.id)
            if agent.status == "running":
                agent.status = "resting"
            self.show("controller", agent.id, "Idle: its session closed; its next input starts a fresh one.")
        else:
            await self._request_handoff(agent, "idle", f"{self.state.options.idle_limit:g}")

    # Tools ----------------------------------------------------------------------------------

    async def _on_tool(self, agent_id: str, session: int, tool: str, args: dict) -> str:
        """Handle one tool call from session number ``session`` of ``agent_id`` (only its role's tools reach here)."""
        assert self.lock is not None  # sessions, and so their tools, exist only while run() runs
        async with self.lock:
            caller = self.state.agents[agent_id]
            if agent_id not in self.sessions or caller.sessions != session:
                return "Error: this session has ended; its tools no longer work."
            if caller.status == "submitted":
                return f"Error: your result is with {caller.parent}; end your turn and wait for its decision."
            self.show("tool", agent_id, f"{tool}({_brief(args)})")
            try:
                reply = await self.handlers[tool](caller, **args)
            except ToolError as refusal:
                reply = f"Refused: {refusal}"
            except TypeError as error:
                reply = f"Error: invalid arguments for {tool}: {error}"
            caller.nudged = False
            if caller.notices and caller.status == "running" and self._works(caller):
                reply += "\n\n" + "\n\n".join(caller.notices)  # pending notices ride along with any reply
                caller.notices = []
            await self._after_change()
            self._save()
            return reply

    def _path(self, caller: Agent, path: str, *bases: Path, folder: bool = False) -> Path:
        """Resolve a path an agent gave: absolute, or relative to the first of ``bases`` where it exists.

        ``bases`` default to the agent's folder. The result must be an existing file (or folder,
        if ``folder``) inside the project, and outside ``.research/``, which agents cannot see.
        """
        if not str(path).strip():
            raise ToolError("a path is required")
        given = Path(str(path)).expanduser()
        candidates = (
            [given] if given.is_absolute() else [base / given for base in bases or (self.project.agent_dir(caller.id),)]
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            visible = self.project.inside(resolved) and not resolved.is_relative_to(self.project.research)
            if visible and (resolved.is_dir() if folder else resolved.is_file()):
                return resolved
        raise ToolError(f"{path} is not an existing {'folder' if folder else 'file'} in the project")

    def _child(self, caller: Agent, agent_id: str) -> Agent:
        child = self.state.agents.get(agent_id)
        if child is None or child.parent != caller.id:
            raise ToolError(
                f"{agent_id} is not one of your subagents; yours: "
                + (", ".join(c.id for c in self.state.children(caller.id)) or "none")
            )
        return child

    def _settled(self, caller: Agent) -> None:
        """Refuse to finish while the caller's subagents or jobs still run or await its decision."""
        open_children = [c.id for c in self.state.children(caller.id) if c.status not in ENDED]
        running = [job.id for job in self.state.running_jobs(caller.id)]
        if open_children or running:
            raise ToolError(
                "first settle your subagents (accept, reject or cancel each: "
                f"{', '.join(open_children) or 'none'}) and jobs (wait or cancel: "
                f"{', '.join(running) or 'none'})"
            )

    def _layout_ok(self, caller: Agent) -> None:
        problems = self.project.check_layout(caller)
        if problems:
            raise ToolError(_layout_notice(problems))

    def _under_review(self) -> bool:
        """True while a COMPLETE or STOP proposal awaits the Reviewer's verdict."""
        return bool(self.state.proposal and not self.state.proposal.get("reviewed"))

    def _talk_only(self, caller: Agent) -> None:
        """Refuse new work by a paused agent, or by the primary while its proposal is under review (PROJECT.md §4)."""
        if caller.role == "primary" and self._under_review():
            assert self.state.proposal is not None  # under review
            raise ToolError(
                f"your proposal (round {self.state.proposal['round']}) is with the Reviewer: until its "
                "verdict you may only talk, so spawn and run_job are refused"
            )
        if caller.status == "paused" or self.state.status != "running":
            raise ToolError(
                "you are paused: until you are told to continue you may only talk, so spawn and run_job are refused"
            )

    def _admit(self, backend: str) -> None:
        """Refuse a new session while ``backend`` is held or every slot is taken."""
        if self.state.status != "running":
            raise ToolError(f"the investigation is {self.state.status}; no new work can start now")
        if self._blocked(backend):
            held = self.state.holds[backend]
            raise ToolError(
                f"{backend} agents are temporarily paused by the usage quota ({held['detail']}); "
                "the controller resumes them automatically. Use another backend, or try later"
            )
        if not self._slot_free():
            raise ToolError(
                f"{self._open()}/{self.state.options.max_agents} agent sessions are already open "
                "(idle ones close after the idle limit); no more subagents can be started now"
            )

    async def _tool_spawn(self, caller: Agent, task: str, backend: str, model: str, effort: str, name: str = "") -> str:
        self._talk_only(caller)
        allowed = self.state.options.backends
        if backend not in allowed:
            raise ToolError(f"backend {backend!r} is not allowed; allowed: {', '.join(allowed)}")
        if not model.strip() or not effort.strip():
            raise ToolError(f"a model and an effort are required, e.g. {caller.spec}")
        try:  # the backend's driver must accept the effort (a typo would only fail the session's start)
            Spec(backend, model.strip(), effort.strip()).validate("the subagent", self.drivers)
        except ValueError as error:
            raise ToolError(str(error)) from None
        brief = self._path(caller, task, self.project.agent_dir(caller.id), self.project.root)
        text = brief.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            raise ToolError(f"{task} must be a non-empty Markdown file: the subagent's brief")
        beside = self.project.agents / "subagent" / "TASK.md"  # any subagent's TASK.md: they all sit side by side
        problem = briefs.problem(text, task, beside, self.project.root, self.librarian.by_name())
        if problem:
            raise ToolError(problem)
        self._admit(backend)
        self._continued(caller)
        child = Agent(self._new_id(name), "subagent", caller.id, backend, model.strip(), effort.strip())
        folder = self.project.agent_dir(child.id)
        folder.mkdir(parents=True)
        atomic_write(folder / "TASK.md", text, root=self.project.root)
        self.state.agents[child.id] = child
        await self._start_session(child)
        if child.status != "running":
            return (
                f"Created subagent {child.id}, but its session could not start; the controller retries it or "
                "asks the human."
            )
        return (
            f"Started subagent {child.id} ({child.spec}); its folder is "
            f"{self.project.relative(self.project.agent_dir(child.id))}/. "
            "You will be told when it submits its result; meanwhile, continue any work that does not "
            "depend on it."
        )

    def _continued(self, caller: Agent) -> None:
        """New work by the primary after a STOP challenge means it chose to continue: the STOP lapses."""
        proposal = self.state.proposal
        if caller.role == "primary" and proposal and proposal["kind"] == "stop" and proposal.get("challenged"):
            self.state.proposal = None

    def _index_entry(self, agent: Agent, name: str, description: str) -> None:
        """Describe a file the controller put in an agent's folder, so the agent's index stays complete."""
        index = self.project.agent_dir(agent.id) / INDEX
        text = index.read_text(encoding="utf-8") if index.exists() else EMPTY_INDEX
        if name not in text:
            atomic_write(index, f"{text.rstrip()}\n- [{name}]({name}) — {description}\n", root=self.project.root)

    def _new_id(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "agent"
        base = "agent" if base in ROLES else base
        candidate, number = base, 1
        while candidate in self.state.agents or self.project.agent_dir(candidate).exists():
            number += 1
            candidate = f"{base}-{number}"
        return candidate

    async def _tool_agents(self, caller: Agent) -> str:
        lines = []
        for child in self.state.children(caller.id):
            session = self.sessions.get(child.id)
            status = ("working" if session and session.busy else "idle") if child.status == "running" else child.status
            fill = f", context {child.fill:.0%}" if child.fill is not None else ""
            lines.append(f"- {child.id} ({child.spec}): {status}{fill}. {child.activity}".rstrip())
        return "\n".join(lines) or "You have no subagents."

    async def _tool_message(self, caller: Agent, agent: str, text: str) -> str:
        """Deliver a message to the caller's parent or one of its subagents (PROJECT.md §3, "Messages")."""
        target = self.state.agents.get(agent)
        if target is None or not (target.parent == caller.id or caller.parent == target.id):
            contacts = [c.id for c in self.state.children(caller.id)] + ([caller.parent] if caller.parent else [])
            raise ToolError(
                f"{agent} is neither your parent nor one of your subagents; you can message: "
                + (", ".join(contacts) or "nobody")
            )
        if not text.strip():
            raise ToolError("the message is empty")
        if target.status in ENDED:
            raise ToolError(f"{agent} has ended ({target.status})")
        if target.status == "submitted":
            raise ToolError(f"{agent} has submitted its result: accept it, reject it with feedback, or cancel it")
        notice = prompts.agent_message(caller.id, text)
        await self._notify(target, notice, "parent" if target.parent == caller.id else "child", caller.id)
        self.show("notice", agent, f"from {caller.id}: {text.strip()}")
        if notice in target.notices:  # no running session to take it now
            return f"{agent} has no running session; it receives your message when its next session starts."
        return f"Message delivered to {agent}."

    async def _tool_accept(self, caller: Agent, agent: str) -> str:
        child = self._child(caller, agent)
        if child.status != "submitted":
            raise ToolError(f"{agent} has not submitted a result (it is {child.status})")
        child.status = "accepted"
        await self._close(child.id)
        commit = self._commit(f"{caller.id}: accepted the result of {agent}")
        await self.librarian.shelve([child], commit)
        return f"Accepted the result of {agent}; its folder is now shelved and frozen."

    async def _tool_reject(self, caller: Agent, agent: str, feedback: str) -> str:
        child = self._child(caller, agent)
        if child.status != "submitted":
            raise ToolError(f"{agent} has not submitted a result (it is {child.status})")
        if not feedback.strip():
            raise ToolError("feedback is required: say what is missing or wrong")
        if self.state.status != "running":
            raise ToolError(f"the investigation is {self.state.status}; try again after it resumes")
        child.rejections += 1
        record = self.project.agent_dir(child.id) / "PARENT_FEEDBACK.md"
        previous = record.read_text(encoding="utf-8") if record.exists() else "# Feedback from my parent\n"
        atomic_write(
            record, f"{previous}\n## Rejection {child.rejections}\n\n{feedback.strip()}\n", root=self.project.root
        )
        self._index_entry(child, "PARENT_FEEDBACK.md", "Feedback from my parent on rejected results.")
        self._queue(
            child,
            f"[controller] {caller.id} rejected your result (rejection {child.rejections}): "
            f"{feedback.strip()}\nContinue the task and submit again.",
            "parent",
            caller.id,
        )
        await self._wake(child)  # in its session, if it kept one; an operational hold only delays it
        if child.status == "paused":
            why = (
                "its CLI is paused by the usage quota" if child.pause_reason == "quota" else "every agent slot is taken"
            )
            return (
                f"Rejected the result of {agent}. It will continue with your feedback automatically as soon as "
                f"it can run ({why}; this is temporary). Meanwhile, continue any work that does not depend on "
                "it."
            )
        return f"Rejected the result of {agent}; it continues with your feedback."

    async def _tool_cancel(self, caller: Agent, agent: str) -> str:
        child = self._child(caller, agent)
        if child.status in ENDED:
            raise ToolError(f"{agent} has already ended ({child.status})")
        cancelled = await self._cancel_tree(child)
        await self.librarian.shelve(cancelled, self._commit(f"{caller.id}: cancelled {agent}"))
        await self._resume_agents({"slots"})
        return f"Cancelled {agent}, its subagents and its jobs."

    async def _cancel_tree(self, agent: Agent) -> list[Agent]:
        """Cancel ``agent`` and its open descendants, with their jobs; return those cancelled, deepest first."""
        cancelled = []
        for member in [agent, *self.state.descendants(agent.id)]:
            if member.status in ENDED:
                continue
            await self._close(member.id)
            for job in self.state.running_jobs(member.id):
                await self._stop_job(job)
            member.status, member.handoff_reason = "cancelled", None
            cancelled.append(member)
        return cancelled[::-1]

    async def _tool_run_job(self, caller: Agent, command: str, timeout_seconds: float, cwd: str = "") -> str:
        self._talk_only(caller)
        if self.state.status != "running":
            raise ToolError(f"the investigation is {self.state.status}; jobs cannot start now")
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError):
            raise ToolError("timeout_seconds must be a number of seconds") from None
        if not command.strip() or not timeout > 0:
            raise ToolError("a command and a positive timeout_seconds are required")
        folder = self._path(caller, cwd or ".", self.project.agent_dir(caller.id), self.project.root, folder=True)
        self._continued(caller)
        self.state.job_counter += 1
        job = Job(f"job-{self.state.job_counter}", caller.id, command, str(folder), timeout, time.time())
        try:
            others = [self.project.at(phase.number).phase_dir for phase in self.home.phases]
            read_only = [self.project.evidence, self.project.library, *self.librarian.frozen()] + [
                folder for folder in others if folder != self.project.phase_dir and folder.is_dir()
            ]
            self.processes[job.id] = joblib.start(
                self.project.phase_dir, job, read_only=read_only, hidden=[self.project.research]
            )
        except OSError as error:
            raise ToolError(f"the job could not start: {error}") from None
        self.state.jobs[job.id] = job
        return (
            f"Started {job.id} (timeout {timeout:g} s); output in "
            f"{self.project.relative(self.project.agent_dir(caller.id))}/jobs/{job.id}/. "
            "You will be told when it ends; meanwhile, continue any work that does not depend on it."
        )

    def _job(self, caller: Agent, job_id: str) -> Job:
        job = self.state.jobs.get(job_id)
        if job is None or job.owner != caller.id:
            raise ToolError(f"{job_id} is not one of your jobs")
        return job

    async def _tool_job_status(self, caller: Agent, job: str) -> str:
        return joblib.describe(self.project.phase_dir, self._job(caller, job))

    async def _tool_job_cancel(self, caller: Agent, job: str) -> str:
        record = self._job(caller, job)
        if record.status != "running":
            raise ToolError(f"{job} is not running ({record.status})")
        await self._stop_job(record)
        return joblib.describe(self.project.phase_dir, record)

    async def _stop_job(self, job: Job) -> None:
        """Stop a job's processes and reap the process this controller started, if any."""
        await asyncio.to_thread(joblib.cancel, job)
        process = self.processes.pop(job.id, None)
        if process is not None:
            await asyncio.to_thread(process.wait)

    async def _tool_submit_result(self, caller: Agent, result: str = "RESULT.md") -> str:
        path = self._path(caller, result, self.project.agent_dir(caller.id), self.project.root)
        if not path.read_text(encoding="utf-8", errors="replace").strip():
            raise ToolError(f"{result} must be a non-empty Markdown file")
        self._settled(caller)
        self._layout_ok(caller)
        self._commit(f"{caller.id}: result submitted")
        caller.status = "submitted"
        assert caller.parent is not None  # submit_result is a subagent's tool
        parent = self.state.agents[caller.parent]
        await self._notify(parent, prompts.result_submitted(caller.id, self.project.relative(path)), "child", caller.id)
        return (
            f"Your result was submitted to {caller.parent}. End your turn now and wait: if {caller.parent} "
            "rejects it, its feedback comes to you here."
        )

    async def _propose(self, caller: Agent, kind: str, detail: str) -> str:
        """Submit a COMPLETE or STOP proposal to the Reviewer, who judges the project as committed now.

        The primary waits in its session, talk-only, until the verdict reaches it there.
        """
        if self._under_review():
            assert self.state.proposal is not None  # under review
            raise ToolError(f"your previous proposal (round {self.state.proposal['round']}) is still with the Reviewer")
        self._settled(caller)
        self._layout_ok(caller)
        self.state.rounds += 1
        commit = self._commit(f"primary: proposes {kind.upper()} (round {self.state.rounds})")
        self.state.proposal = {
            "kind": kind,
            "round": self.state.rounds,
            "detail": detail,
            "commit": commit,
            "challenged": False,
            "reviewed": False,
        }
        await self._start_review()
        return (
            f"Your {kind.upper()} proposal is with the Reviewer (round {self.state.rounds}), who judges the project "
            f"as committed now ({(commit or '')[:12]}). End your turn now and wait: the verdict comes to you here. "
            "Until then you may only talk: spawn and run_job are refused."
        )

    async def _tool_complete(self, caller: Agent, report: str = "REPORT.md") -> str:
        path = self._path(caller, report, self.project.phase_dir, self.project.root, self.project.agent_dir(caller.id))
        if not path.read_text(encoding="utf-8", errors="replace").strip():
            raise ToolError(f"{report} must be a non-empty report")
        return await self._propose(caller, "complete", self.project.relative(path))

    async def _tool_stop(self, caller: Agent, reason: str, final: bool = False) -> str:
        if not reason.strip():
            raise ToolError("a reason is required")
        proposal = self.state.proposal
        if final:
            if not (proposal and proposal["kind"] == "stop" and proposal.get("challenged")):
                raise ToolError("the Reviewer must challenge a STOP first: call stop(reason) without final")
            self._settled(caller)
            await self._finish("stopped", reason.strip())
            return "The investigation is stopped."
        return await self._propose(caller, "stop", reason.strip())

    def _review_args(self) -> dict:
        """The current proposal, as :func:`prompts.review_request` takes it."""
        proposal = self.state.proposal
        assert proposal is not None  # called only while a proposal is under review
        return {
            "kind": proposal["kind"],
            "round_": proposal["round"],
            "detail": proposal["detail"],
            "phase": self.project.folder,
            "commit": proposal.get("commit"),
        }

    async def _start_review(self) -> None:
        """Hand the current proposal to the Reviewer: in its session, or in a fresh one once its CLI may run."""
        proposal = self.state.proposal
        assert proposal is not None  # called only once a proposal was made
        self.show("controller", "reviewer", f"Review round {proposal['round']}: {proposal['kind'].upper()}.")
        await self._notify(self.state.agents["reviewer"], prompts.review_request(**self._review_args()))

    async def _tool_verdict(self, caller: Agent, review: str, agree: bool) -> str:
        proposal = self.state.proposal
        if not proposal or proposal.get("reviewed"):
            raise ToolError("there is no proposal awaiting your verdict")
        path = self._path(caller, review, self.project.reviews, self.project.root, self.project.agent_dir(caller.id))
        if not path.is_relative_to(self.project.reviews):
            raise ToolError("the review must be a Markdown file in reviews/")
        self._settled(caller)
        self._layout_ok(caller)
        agree = agree if isinstance(agree, bool) else str(agree).lower() in ("true", "1", "yes")
        proposal["reviewed"], proposal["review"] = True, self.project.relative(path)
        self.state.verdict = "agree" if agree else "disagree"
        self._commit(
            f"reviewer: verdict on {proposal['kind'].upper()} round {proposal['round']} "
            f"({'agree' if agree else 'disagree'})"
        )
        self.show("controller", "reviewer", f"Verdict: {'agree' if agree else 'disagree'} ({proposal['review']}).")
        caller.status = "resting"  # it keeps its session for the next round
        if proposal["kind"] == "complete" and agree:
            await self._finish("complete", f"the Reviewer agreed ({proposal['review']})")
            return "Verdict recorded: the investigation is COMPLETE."
        if proposal["kind"] == "complete":
            self.state.proposal = None
        else:
            proposal["challenged"] = True
        # What the primary changed after proposing: the review does not cover it.
        excluded = [
            self.project.relative(folder) for folder in (self.project.reviews, self.project.agent_dir("reviewer"))
        ]
        changed = (
            self.project.changed_since(proposal["commit"], *excluded, "library", LIBRARIAN)
            if proposal.get("commit")
            else []
        )
        await self._notify(
            self.state.agents["primary"],
            prompts.verdict_delivered(proposal["kind"], proposal["round"], proposal["review"], agree, changed),
        )
        return "Verdict delivered to the primary. End your turn now; a next round comes to you here."

    # Finishing ----------------------------------------------------------------------------------

    async def _finish(self, outcome: str, detail: str) -> None:
        """End the investigation: stop every agent and job but the Librarian, record the outcome and commit.

        The primary's and the Reviewer's folders, and any other ended agent's not shelved yet, are then
        shelved; the controller exits once the Librarian has placed them, or at once if it cannot run.
        """
        state = self.state
        state.status, state.proposal = outcome, None
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        state.outcome = f"{outcome.upper()} on {stamp}: {detail}"
        for agent_id in list(self.sessions):
            if agent_id != LIBRARIAN:
                await self._close(agent_id)
        for agent in state.agents.values():
            if agent.role == "librarian":
                continue
            agent.handoff_reason = None
            if agent.status not in ENDED and agent.role != "reviewer":
                agent.status = "finished" if agent.role == "primary" else "cancelled"
            elif agent.role == "reviewer":
                agent.status = "resting"
        for job in state.running_jobs():
            await self._stop_job(job)
        status_file = self.project.status_file
        text = status_file.read_text(encoding="utf-8") if status_file.exists() else "# Status\n"
        atomic_write(
            status_file,
            f"{text.rstrip()}\n\n## Outcome (recorded by the controller)\n\n{state.outcome}\n",
            root=self.project.root,
        )
        commit = self._commit(f"controller: phase {self.project.phase} {outcome.upper()}")
        state.human = self.project.human_fingerprint()  # changes from now on reopen it at the next run
        state.end_commit, state.ended = commit, time.time()
        self.show("controller", "primary", f"Phase {self.project.phase} is {outcome.upper()}: {detail}")
        final = [
            agent
            for agent in state.agents.values()
            if self.project.agent_dir(agent.id).is_dir()
            and (agent.role in ("primary", "reviewer") or agent.status in ENDED)
            and (
                agent.role in ("primary", "reviewer")
                or self.librarian.folder(agent) not in self.librarian.catalogue.shelves
            )
        ]
        self.closing = True
        await self.librarian.shelve(final, commit)
        self._save()
        await self._closed()

    async def _closed(self, force: bool = False) -> None:
        """After the end: exit once the Librarian placed the final work, or cannot run (``force``: it stalled).

        Requests it leaves pending reach it at the controller's next run.
        """
        librarian = self.state.agents[LIBRARIAN]
        if not self.closing:
            return
        if not force and self.home.shelving and librarian.status != "paused" and not self._blocked(librarian.backend):
            return  # it is placing the final work
        self.closing = False
        await self._close(LIBRARIAN)
        librarian.handoff_reason = None
        if librarian.status in ACTIVE or librarian.status == "paused":
            librarian.status, librarian.pause_reason = "resting", None
        pending = self.home.shelving
        self._commit("controller: the library after the end")  # the catalogue and the Librarian's last notes
        self.show(
            "controller",
            LIBRARIAN,
            f"Shelving requests wait for the next run: {', '.join(pending)}."
            if pending
            else "The library is up to date.",
        )
        self._announce_talks()
        self._save()

    def _announce_talks(self) -> None:
        reopen = (
            "to reopen it or start another phase, use the web page"
            if self.reopen is False
            else f"to reopen it, change {self.project.relative(self.project.objectives)} and run again"
        )
        self.show(
            "controller",
            "primary",
            f"Phase {self.project.phase} has ended ({self.state.status.upper()}). You can still talk with its primary "
            f"(chat box or web page) and its Reviewer (web page), talk-only. Ctrl+Q quits; {reopen}.",
        )

    def _phases(self) -> str:
        """The project's phases, as the primary's opening message lists them."""
        items = phases.summaries(self.project, self.home, self.state)
        current = next((item for item in items if item.number == self.project.phase), None)
        others = [item for item in items if item.number != self.project.phase and item.status != NOT_STARTED]
        return prompts.phases_section(current, phases.listing(others) if others else "")

    # Pause, resume and shutdown ------------------------------------------------------------------

    async def _toggle(self) -> None:
        if (
            self.state.status == "running"
            and not any(a.status in ACTIVE for a in self.state.agents.values())
            and self.releasable
        ):
            await self._release()  # nothing works: "Resume" means lifting what holds the agents
        elif self.state.status == "running":
            await self._pause()
        elif self.state.status in ("pausing", "paused"):
            await self._resume()

    async def _pause(self, reason: str = "pause") -> None:
        """The human's pause, or shutdown; :meth:`_pause_progress` completes it once no agent works.

        At a pause, agents at work end their turn at a clean point and wait in their
        sessions. At a shutdown, every session saves its note first (without a turn
        while its CLI is held, or when its note is saved already), as all sessions end.
        """
        self.state.status = "pausing"
        shutdown = reason == "shutdown"
        self.show(
            "controller",
            "primary",
            "Shutting down: every agent saves its handoff first."
            if shutdown
            else "Pausing: working agents end their turn and wait in their sessions.",
        )
        for agent in list(self.state.agents.values()):
            if shutdown and agent.id in self.sessions and not (self._blocked(agent.backend) or self._noted(agent)):
                await self._request_handoff(agent, "shutdown")
            elif not shutdown and agent.status in ACTIVE:
                await self._hold_agent(agent, "human", prompts.pausing())
            elif agent.status == "paused" and agent.pause_reason == "failure":
                agent.pause_reason = "human"
        await self._pause_progress()

    async def _pause_progress(self) -> None:
        """Complete a pause once no agent works any more: a pause stops the jobs, a shutdown keeps them."""
        state = self.state
        if state.status != "pausing" or self._working():
            return
        shutdown = self.request == "shutdown"
        if shutdown:  # sessions end with the controller; jobs survive it, and the next run reattaches them
            for agent_id in list(self.sessions):
                await self._close(agent_id)
        else:
            for job in state.running_jobs():
                await self._stop_job(job)
                self._queue(
                    state.agents[job.owner],
                    f"[controller] {job.id} was stopped by the human's pause; run it again if it is still needed.",
                )
        state.status = "paused"
        self._commit("controller: shut down by the human" if shutdown else "controller: paused by the human")
        if not shutdown:
            self.show("controller", "primary", "Paused. Agent files may now be edited; press Resume to continue.")
        self._save()
        if shutdown:
            assert self.done is not None  # set by run(), within which this runs
            self.done.set()

    async def _resume(self) -> None:
        """The human's resume: report what changed meanwhile, re-read quota and bring the agents back to work."""
        state = self.state
        self.request = None  # resuming cancels a shutdown still waiting for handoffs (see _check_handoff)
        if state.status == "paused":
            changed = self.project.uncommitted()
            if changed:
                self._commit("controller: changes made while paused (by the human or by running jobs)")
                self._announce_changes(changed)
        state.status = "running"
        self.guard.release()  # the human's resume lifts weekly and unreadable holds: the quota is read again
        self.show("controller", "primary", "Resumed.")
        await self._check_quota()
        await self._resume_agents()
        await self._deliver_queued()
        self._save()

    async def _release(self) -> None:
        """Lift weekly/unreadable quota holds and retry agents whose automatic retries are exhausted."""
        state = self.state
        if state.status != "running":
            return
        self.guard.release()
        for agent in state.agents.values():
            if agent.status == "paused" and agent.pause_reason == "failure" and agent.retry_at is None:
                agent.failures, agent.pause_reason = 0, "retry"
        self.show("controller", "primary", "Released held CLIs and failed agents; re-reading the usage quota.")
        await self._check_quota()
        await self._resume_agents({"quota", "retry", "slots"})
        self._save()

    async def _after_change(self) -> None:
        """Follow-ups once agents may have stopped working: complete a pause, fill free slots, end after the end."""
        await self._pause_progress()
        await self._resume_agents({"slots"})
        await self._closed()

    async def _shutdown(self) -> None:
        """Let every session save its handoff, then end the controller; jobs keep running."""
        if self.state.status in FINISHED:
            await self.talks.close()  # each talk session saves its talk note
            assert self.done is not None  # set by run(), within which this runs
            self.done.set()
        else:  # also while paused: the sessions kept meanwhile save their notes before they end
            await self.talks.close()  # talks with other phases save their notes
            await self._pause("shutdown")

    # Usage quota ---------------------------------------------------------------------------------

    def _blocked(self, backend: str) -> bool:
        """True if agents on ``backend`` must not run: their CLI is held."""
        return backend in self.state.holds

    def _backends_in_use(self) -> set[str]:
        agents = [a for a in self.state.agents.values() if a.status not in ENDED]
        return (
            {a.backend for a in agents}
            | set(self.state.options.backends)
            | {self.state.agents[role].backend for role in ROLES}
        )

    async def _quota_loop(self) -> None:
        while True:
            await asyncio.sleep(WATCH_INTERVAL)
            if time.time() >= self._quota_due:
                readings = await self._read_quota()
                await self._locked(self._apply_quota(readings))

    async def _read_quota(self) -> dict[str, list[quota.Window] | OSError]:
        """Read every CLI in use, outside the lock (probes take seconds)."""
        self._quota_due = time.time() + QUOTA_INTERVAL
        return await asyncio.to_thread(self.guard.read, self._backends_in_use())

    async def _check_quota(self) -> None:
        """Read and apply the quota now (called with the lock held)."""
        await self._apply_quota(await self._read_quota())

    async def _apply_quota(self, readings: dict[str, list[quota.Window] | OSError]) -> None:
        """Hold or release CLIs according to their usage windows (PROJECT.md §6, "Quota")."""
        for change, backend, hold in self.guard.apply(readings):
            if change == "held":
                self.show("controller", "primary", f"Usage quota: {backend} held ({hold['kind']}: {hold['detail']}).")
                await self._hold(backend)
            else:
                self.show("controller", "primary", f"Usage quota: {backend} available again.")
        await self._resume_agents({"quota", "slots"})
        self._save()

    async def _hold(self, backend: str) -> None:
        """Every session ``backend``'s hold affects saves its note (an idle one in a short turn) and waits in it."""
        for agent in list(self.state.agents.values()):
            if agent.id in self.sessions and self._blocked(agent.backend) and not self._noted(agent):
                await self._request_handoff(agent, "quota", backend)

    # Background checks -----------------------------------------------------------------------------

    async def _watch_loop(self) -> None:
        while True:
            await asyncio.sleep(WATCH_INTERVAL)
            await self._locked(self._watch())

    async def _watch(self) -> None:
        """Jobs that ended, failed agents due a retry, idle sessions and the human's files."""
        state, now = self.state, time.time()
        for job in state.running_jobs():
            if joblib.poll(self.project.phase_dir, job, self.processes.get(job.id)):
                self.processes.pop(job.id, None)
                owner = state.agents[job.owner]
                self.show("controller", job.owner, f"{job.id} ended: {job.status}.")
                if owner.status not in ENDED:
                    await self._notify(owner, prompts.job_ended(joblib.describe(self.project.phase_dir, job)))
                self._save()
        for agent in state.agents.values():
            if (
                agent.status == "paused"
                and agent.pause_reason == "failure"
                and agent.retry_at is not None
                and now >= agent.retry_at
            ):
                agent.retry_at = None
                agent.pause_reason = "retry"
                await self._resume_agents({"retry"})
        await self._check_idle()
        await self.talks.check_idle()
        if now >= self._human_checked + HUMAN_INTERVAL:
            self._human_checked = now
            await self._check_human()
        await self._after_change()

    async def _check_idle(self) -> None:
        """Follow how long each session has been idle; close those past the idle limit (see :meth:`_idle_out`)."""
        clock, limit = time.monotonic(), self.state.options.idle_limit * 60
        for agent_id, session in list(self.sessions.items()):
            agent = self.state.agents[agent_id]
            if session.busy or agent.handoff_reason:
                self.idle_since.pop(agent_id, None)
            elif limit and clock - self.idle_since.setdefault(agent_id, clock) >= limit:
                self.idle_since.pop(agent_id, None)
                await self._idle_out(agent)

    async def _check_human(self) -> None:
        """Tell the primary when the human's own files changed (PROJECT.md §6, "Human edits")."""
        current = self.project.human_fingerprint()
        changed = Project.changed(self.state.human, current)
        if changed and self.state.status in FINISHED:  # kept for the next run, which reopens on changed objectives
            if not self._reopen_told and self.reopen is not False and self.objectives_changed():
                self._reopen_told = True  # with the web page, it shows them
                self.show(
                    "alert",
                    "primary",
                    f"The objectives of phase {self.project.phase} changed since its end: talks go on; quit (Ctrl+Q) "
                    "and run again to reopen it.",
                )
        elif changed:
            self.state.human = current
            self.show("controller", "primary", "The human changed: " + ", ".join(changed[:10]))
            await self._notify(self.state.agents["primary"], prompts.human_changed(changed))
            self._save()

    # Persistence ------------------------------------------------------------------------------------

    def _save(self) -> None:
        durable = self.state.options.durable
        self.state.save(self.project.state_file, durable=durable, omit=(LIBRARIAN,))
        self.home.save(self.project.home_file, durable=durable)

    def _commit(self, message: str) -> str | None:
        """Commit the project and return the current commit; changes to the human's files are reported first
        (PROJECT.md §2)."""
        current = self.project.human_fingerprint()
        # After the end, the human's changes are kept for the next run, which reopens on them.
        changed = Project.changed(self.state.human, current) if self.state.status not in FINISHED else []
        primary = self.state.agents["primary"]
        if changed:
            self.state.human = current
            self._queue(primary, prompts.human_changed(changed))
            self.show("controller", "primary", "The human's files changed: " + ", ".join(changed[:10]))
        strays = set(self.project.stray_entries()) - self._strays
        if strays:
            self._strays |= strays
            self._queue(primary, prompts.stray_entries(sorted(strays)))
            self.show("controller", "primary", "Unexpected top-level entries: " + ", ".join(sorted(strays)))
        if primary.notices and primary.status == "running":
            asyncio.ensure_future(self._locked(self._flush_running(primary)))  # after the current step
        self._write_indexes()
        try:
            return self.project.commit(message) or self.project.head()
        except ProjectError as error:
            self.show("controller", "primary", f"Commit failed: {error}")
            return None

    def _write_indexes(self) -> None:
        """Rewrite the agents' index and every agent's jobs index.

        A refused write (such as a symlink an agent or its job left where an index
        belongs, which the controller never writes through) is shown and skipped: it
        must not stop the commit, nor the handoff or result that asked for it.
        """
        writes = [
            lambda: self.project.write_agents_index(list(self.state.agents.values())),
            self.librarian.write_catalog,
            lambda: phases.write_index(self.project, self.home, self.state),
        ]
        writes += [
            lambda owner=owner: joblib.write_index(self.project.phase_dir, owner, list(self.state.jobs.values()))
            for owner in sorted({job.owner for job in self.state.jobs.values()})
        ]
        for write in writes:
            try:
                write()
            except (ValueError, OSError) as error:
                self.show("controller", "primary", f"An index was not written: {error}")


def _layout_notice(problems: list[str]) -> str:
    return "[controller] Fix these layout problems first:\n" + "\n".join(f"- {p}" for p in problems)


def _brief(args: dict) -> str:
    """Tool arguments shortened for the transcript."""
    return ", ".join(f"{key}={str(value)[:60]!r}" for key, value in args.items())
