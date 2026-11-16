"""Persistent state of one investigation: its agents, jobs and the controller's decisions.

Everything lives in one JSON file, ``.research/state.json``, rewritten atomically
after every change. It holds only what the project files cannot: which agents
exist and what they are doing, which jobs run, what the Reviewer is examining and
which CLIs are held by their usage quota. The science itself stays in the
project's ordinary files.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
import os
from pathlib import Path
import tempfile

#: Agent statuses with a live CLI session; each occupies one concurrency slot.
LIVE = frozenset({'running', 'handing_off'})
#: Agent statuses after which an agent never runs again (unless the investigation is reopened).
ENDED = frozenset({'accepted', 'cancelled', 'finished'})
#: Investigation statuses in which no agent works any more.
FINISHED = frozenset({'complete', 'stopped'})


@dataclass
class Options:
    """Launch options, kept so that a later ``run`` resumes with the same settings."""
    primary: str = 'codex'                  # BACKEND[:MODEL[:EFFORT]] of the primary researcher
    reviewer: str = 'codex'                 # BACKEND[:MODEL[:EFFORT]] of the final Reviewer
    backends: list[str] = field(default_factory=lambda: ['codex'])  # CLIs agents may choose for subagents
    max_agents: int = 4                     # agents with a live session at the same time
    references: list[str] = field(default_factory=list)  # read-only folders of other projects
    short_limit: float = 15                 # % left of a short usage window that pauses a CLI's agents
    weekly_limit: float = 15                # % left of a weekly window that pauses them until the human resumes
    threshold: float = 0.55                 # context fill at which an agent is asked to hand off

    @classmethod
    def from_dict(cls, data: dict) -> Options:
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass(frozen=True)
class Spec:
    """A CLI choice: backend name, optional model and optional reasoning effort."""
    backend: str
    model: str | None = None
    effort: str | None = None

    @classmethod
    def parse(cls, text: str) -> Spec:
        """Parse ``BACKEND[:MODEL[:EFFORT]]``; empty parts mean the CLI's own default."""
        parts = (text.strip().split(':') + ['', ''])[:3]
        if not parts[0]:
            raise ValueError(f'invalid CLI choice {text!r}: expected BACKEND[:MODEL[:EFFORT]]')
        return cls(parts[0], parts[1] or None, parts[2] or None)

    def __str__(self) -> str:
        return ':'.join(part for part in (self.backend, self.model, self.effort) if part)


@dataclass
class Agent:
    """One logical agent. It keeps its identity and folder across any number of sessions."""
    id: str
    role: str                         # 'primary', 'subagent' or 'reviewer'
    parent: str | None                # who spawned it (a subagent's parent); None otherwise
    backend: str
    model: str | None = None
    effort: str | None = None
    # running | handing_off | paused | submitted | resting | accepted | cancelled | finished
    status: str = 'paused'
    pause_reason: str | None = None   # why it is paused: 'start', 'human', 'quota', 'failure', 'restart'
    sessions: int = 0                 # sessions started so far
    notices: list[str] = field(default_factory=list)  # controller messages not delivered yet
    handoff_reason: str | None = None   # while handing off: 'context', 'pause' or 'quota'
    handoff_since: float | None = None  # when the handoff was requested
    handoff_prompts: int = 0             # times it was asked again after ending a turn without handing off
    reminder_at: float | None = None     # context fill at the last handoff request (None: next at the threshold)
    tokens: int | None = None            # tokens in its current session's context, as its CLI reports them
    window: int | None = None            # that session's context window, as its CLI reports it
    rejections: int = 0                  # results its parent rejected
    failures: int = 0                    # consecutive unexpected session exits
    retry_at: float | None = None        # when to restart it after a failure
    nudged: bool = False                 # told once that nothing is running for it
    closing: bool = False                # its session closes when the current turn ends (after a result or verdict)
    activity: str = ''                   # last thing it did, for the terminal app

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
    owner: str                       # logical agent that started it
    command: str
    cwd: str
    timeout: float                   # seconds
    started: float
    pid: int | None = None           # session leader of the job's processes
    ticks: int | None = None         # its start time in clock ticks, to recognise it after a restart
    status: str = 'running'          # running | finished | failed | timeout | cancelled | lost
    exit_code: int | None = None
    ended: float | None = None

    @property
    def deadline(self) -> float:
        return self.started + self.timeout


@dataclass
class State:
    """Everything the controller must remember across restarts."""
    options: Options = field(default_factory=Options)
    status: str = 'running'          # running | pausing | paused | complete | stopped
    agents: dict[str, Agent] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    proposal: dict | None = None     # {'kind': 'complete'|'stop', 'round': n, 'detail': str, 'challenged': bool}
    rounds: int = 0                  # review rounds so far
    holds: dict[str, dict] = field(default_factory=dict)  # backend -> {'kind', 'until', 'detail'}
    human: dict[str, str] = field(default_factory=dict)   # human-owned file -> fingerprint, as last seen
    job_counter: int = 0
    outcome: str | None = None       # how the investigation last ended

    def save(self, path: Path) -> None:
        """Write the state atomically: a crash never leaves a half-written file."""
        data = asdict(self)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='.state-')
        with os.fdopen(handle, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=1)
        os.replace(temporary, path)

    @classmethod
    def load(cls, path: Path) -> State:
        data = json.loads(path.read_text(encoding='utf-8'))
        state = cls(**{key: value for key, value in data.items()
                       if key not in ('options', 'agents', 'jobs') and key in {f.name for f in fields(cls)}})
        state.options = Options.from_dict(data.get('options', {}))
        state.agents = {key: Agent(**value) for key, value in data.get('agents', {}).items()}
        state.jobs = {key: Job(**value) for key, value in data.get('jobs', {}).items()}
        return state

    def children(self, agent_id: str) -> list[Agent]:
        return [agent for agent in self.agents.values() if agent.parent == agent_id]

    def descendants(self, agent_id: str) -> list[Agent]:
        found = []
        for child in self.children(agent_id):
            found += [child, *self.descendants(child.id)]
        return found

    def running_jobs(self, owner: str | None = None) -> list[Job]:
        return [job for job in self.jobs.values()
                if job.status == 'running' and (owner is None or job.owner == owner)]
