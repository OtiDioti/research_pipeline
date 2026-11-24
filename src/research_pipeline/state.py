"""Persistent state of one phase of an investigation: its agents, jobs and the controller's decisions.

Each phase's lives in one JSON file, ``.research/phases/<N>/state.json``, rewritten atomically
after every change and forced to disk unless the ``durable`` option is off
(``--no-durable-state``). It holds only what the project files cannot:
which agents exist and what they are doing, which jobs run, what the Reviewer is
examining and which CLIs are held by their usage quota. The science itself stays
in the project's ordinary files. What every phase shares (the list of phases, the
Librarian and its pending requests) is kept apart (:mod:`research_pipeline.phases`).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from agent_toolkit import Spec
from agent_toolkit.handoff import IDLE_LIMIT
from agent_toolkit.records import atomic_write

#: Agent statuses of an agent at work: it always has a live CLI session. Agents in other statuses may keep
#: theirs while they wait (see research_pipeline.controller); every live session occupies one slot.
ACTIVE = frozenset({"running", "handing_off"})
#: Agent statuses after which an agent never runs again (unless its phase is reopened).
ENDED = frozenset({"accepted", "cancelled", "finished"})
#: Phase statuses in which no agent works any more.
FINISHED = frozenset({"complete", "stopped"})


@dataclass
class Options:
    """Launch options, kept so that a later ``run`` resumes with the same settings."""

    primary: str = ""  # BACKEND:MODEL:EFFORT of the primary researcher
    reviewer: str = ""  # BACKEND:MODEL:EFFORT of the final Reviewer
    librarian: str = ""  # BACKEND:MODEL:EFFORT of the Librarian
    setup: str = ""  # BACKEND:MODEL:EFFORT of the setup assistant (web setup, before the first start)
    writer: str = "claude:claude-opus-5-5:high"  # BACKEND:MODEL:EFFORT of the Writer and its checker (reports)
    report_at_end: bool = True  # the Writer writes the phase's report once it ends
    # The models the prompt recommends for subagents' coding and analytical tasks (BACKEND:MODEL:EFFORT)
    coding: str = "claude:claude-opus-5-5:xhigh"
    analysis: str = "codex:gpt-6.1-sol:xhigh"
    backends: list[str] = field(default_factory=list)  # CLIs agents may choose for subagents
    max_agents: int = 6  # live sessions at the same time (idle ones included)
    references: list[str] = field(default_factory=list)  # read-only folders of other projects
    short_limit: float = 15  # % left of a short usage window that pauses a CLI's agents
    weekly_limit: float = 15  # % left of a weekly window that pauses them until the human resumes
    threshold: float = 0.55  # context fill at which an agent is asked to hand off (> 0, <= 0.8)
    idle_limit: float = IDLE_LIMIT  # minutes a session may wait idle before it saves its note and closes
    # (0: never; 58 stays inside the 1 h prompt-cache lifetime)
    durable: bool = True  # force every state write to disk (off: faster on network filesystems)

    @classmethod
    def from_dict(cls, data: dict) -> Options:
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass
class Agent:
    """One logical agent. It keeps its identity and folder across any number of sessions."""

    id: str
    role: str  # 'primary', 'subagent', 'reviewer' or 'librarian'
    parent: str | None  # who spawned it (a subagent's parent); None otherwise
    backend: str
    model: str
    effort: str
    # running | handing_off | paused | submitted | resting | accepted | cancelled | finished
    # ('resting': nothing to do until its next input, e.g. the Reviewer between rounds or the Librarian between
    # shelving requests; a resting, paused or
    # submitted agent may keep its idle session, which closes after the idle limit)
    status: str = "paused"
    pause_reason: str | None = None  # start, human, held, resume, quota, slots, failure, retry, restart, reopen, wake
    sessions: int = 0  # sessions started so far
    started: float | None = None  # when its current (or last) session started
    notices: list[str] = field(default_factory=list)  # controller messages not delivered yet
    handoff_reason: str | None = None  # while saving its note: 'context', 'refresh', 'idle', 'quota' or 'shutdown'
    tokens: int | None = None  # tokens in its current session's context, as its CLI reports them
    window: int | None = None  # that session's context window, as its CLI reports it
    rejections: int = 0  # results its parent rejected
    failures: int = 0  # consecutive unexpected session exits
    retry_at: float | None = None  # when to restart it after a failure
    nudged: bool = False  # told it is idle; ending its turn idle again then means it stalled
    activity: str = ""  # last thing it did, for the terminal app

    @property
    def spec(self) -> Spec:
        return Spec(self.backend, self.model, self.effort)

    @property
    def fill(self) -> float | None:
        """Context fill of the current session, or None while unknown."""
        return self.tokens / self.window if self.tokens is not None and self.window else None


@dataclass
class Job:
    """One computation run by the controller for an agent; it outlives the agent's sessions."""

    id: str
    owner: str  # logical agent that started it
    command: str
    cwd: str
    timeout: float  # seconds
    started: float
    pid: int | None = None  # session leader of the job's processes
    ticks: int | None = None  # its start time in clock ticks, to recognise it after a restart
    status: str = "running"  # running | finished | failed | timeout | cancelled | lost
    exit_code: int | None = None
    ended: float | None = None

    @property
    def deadline(self) -> float:
        return self.started + self.timeout


@dataclass
class State:
    """Everything the controller must remember of one phase across restarts."""

    options: Options = field(default_factory=Options)
    status: str = "running"  # running | pausing | paused | complete | stopped
    agents: dict[str, Agent] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    # {'kind': 'complete'|'stop', 'round': n, 'detail': str, 'commit': the commit under review,
    #  'challenged': bool, 'reviewed': bool} and, once reviewed, 'review': the review's path
    proposal: dict | None = None
    rounds: int = 0  # review rounds so far
    # backend -> {'kind', 'until', 'detail'}, kept by agent_toolkit.quota.Guard ('until': reported reset or None)
    holds: dict[str, dict] = field(default_factory=dict)
    human: dict[str, str] = field(default_factory=dict)  # human-owned file -> fingerprint, as last seen
    job_counter: int = 0
    outcome: str | None = None  # how the phase last ended
    end_commit: str | None = None  # the commit of the last end, whose human files a reopening's changes are against
    ended: float | None = None  # when it last ended (POSIX time): the talks after it are since then
    verdict: str | None = None  # the Reviewer's last verdict: 'agree' or 'disagree'

    def save(self, path: Path, durable: bool = True, omit: tuple[str, ...] = ()) -> None:
        """Write the state atomically, and (``durable``) force it to disk: a crash never leaves a half-written file.

        Agents in ``omit`` are kept elsewhere (the Librarian, which every phase shares).
        """
        data = asdict(self)
        data["agents"] = {key: value for key, value in data["agents"].items() if key not in omit}
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(data, indent=1), durable=durable)

    @classmethod
    def load(cls, path: Path) -> State:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = cls(
            **{
                key: value
                for key, value in data.items()
                if key not in ("options", "agents", "jobs") and key in {f.name for f in fields(cls)}
            }
        )
        state.options = Options.from_dict(data.get("options", {}))
        state.agents = {key: Agent(**value) for key, value in data.get("agents", {}).items()}
        state.jobs = {key: Job(**value) for key, value in data.get("jobs", {}).items()}
        return state

    def children(self, agent_id: str) -> list[Agent]:
        return [agent for agent in self.agents.values() if agent.parent == agent_id]

    def descendants(self, agent_id: str) -> list[Agent]:
        found = []
        for child in self.children(agent_id):
            found += [child, *self.descendants(child.id)]
        return found

    def running_jobs(self, owner: str | None = None) -> list[Job]:
        return [job for job in self.jobs.values() if job.status == "running" and (owner is None or job.owner == owner)]
