"""What the stats read from a project, read-only and incrementally: phases, agents, jobs and activity.

The phases' ``state.json`` and the project's ``project.json`` are small and read again
when they change; each activity log (``.research/phases/<N>/activity/<agent>.jsonl``,
the Librarian's ``.research/activity/librarian.jsonl``) is read from where the last
read stopped, and each new tool entry is parsed once (:func:`research_pipeline.stats.calls.call`).
Nothing is written, and no lock is taken, so a project may be read while it runs.
A project made before phases (``.research/state.json``, agents in ``agents/`` at the
top) reads as one phase, phase 1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from research_pipeline.stats.calls import Call, call

LIBRARIAN = "librarian"


@dataclass
class Agent:
    """An agent of a phase, as its state records it."""

    id: str
    phase: int
    role: str
    parent: str | None
    backend: str
    model: str
    status: str
    started: float
    sessions: int
    rejections: int


@dataclass
class Job:
    id: str
    owner: str
    command: str
    cwd: str
    started: float
    ended: float | None
    status: str
    exit_code: int | None


@dataclass
class Entry:
    """An activity entry; ``call`` for tool entries."""

    time: float
    agent: str
    kind: str
    sender: str
    origin: str | None
    text: str
    call: Call | None = None
    tokens: int | None = None
    window: int | None = None


class Log:
    """One activity log, read incrementally."""

    def __init__(self, path: Path):
        self.path = path
        self.offset = 0
        self.entries: list[Entry] = []

    def read(self) -> bool:
        """Read what was appended since the last read; True if anything was."""
        try:
            with open(self.path, "rb") as handle:
                handle.seek(self.offset)
                data = handle.read()
        except OSError:
            return False
        complete = data[: data.rfind(b"\n") + 1]  # a line still being written waits for the next read
        if not complete:
            return False
        self.offset += len(complete)
        for line in complete.decode("utf-8", errors="replace").splitlines():
            try:
                raw = json.loads(line)
            except ValueError:
                continue
            if not isinstance(raw, dict) or "time" not in raw:
                continue
            entry = Entry(
                float(raw["time"]),
                str(raw.get("agent", "")),
                str(raw.get("kind", "")),
                str(raw.get("sender", "self")),
                raw.get("origin"),
                str(raw.get("text", "")),
                tokens=raw.get("tokens"),
                window=raw.get("window"),
            )
            if entry.kind == "tool":
                entry.call = call(raw)
            self.entries.append(entry)
        return True


@dataclass
class Phase:
    number: int
    title: str
    status: str = ""
    ended: float | None = None
    rounds: int = 0
    verdict: str | None = None
    agents: dict[str, Agent] = field(default_factory=dict)
    jobs: list[Job] = field(default_factory=list)
    logs: dict[str, Log] = field(default_factory=dict)

    @property
    def start(self) -> float | None:
        """When its first agent started."""
        return min((agent.started for agent in self.agents.values()), default=None)


class Source:
    """A research project's records, kept current by :meth:`refresh`."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.research = self.root / ".research"
        self.single = not (self.research / "project.json").is_file()  # made before phases
        if self.single and not (self.research / "state.json").is_file():
            raise ValueError(f"{self.root} is not a research project (it has no .research/ records)")
        self.phases: dict[int, Phase] = {}
        self.librarian = Log(self.research / "activity" / f"{LIBRARIAN}.jsonl")
        self._seen: dict[Path, float] = {}  # state files by modification time
        self.version = 0  # bumped whenever anything new was read

    @property
    def name(self) -> str:
        return self.root.name

    def agent_folder(self, phase: int, agent: str) -> str:
        """An agent's folder, relative to the project."""
        return f"agents/{agent}" if self.single else f"phases/{phase}/agents/{agent}"

    def _phase_folder(self, number: int) -> Path:
        """Where phase ``number``'s state.json and activity/ are."""
        return self.research if self.single else self.research / "phases" / str(number)

    def refresh(self) -> None:
        """Read what changed since the last refresh."""
        changed = False
        if self.single:
            self.phases.setdefault(1, Phase(1, ""))
        project = None if self.single else self._json(self.research / "project.json")
        if project is not None:
            for item in project.get("phases", []):
                number = int(item.get("number", 0))
                phase = self.phases.setdefault(number, Phase(number, str(item.get("title") or "")))
                phase.title = str(item.get("title") or phase.title)
                changed = True
        for number, phase in self.phases.items():
            folder = self._phase_folder(number)
            state = self._json(folder / "state.json")
            if state is not None:
                self._load(phase, state)
                changed = True
            for path in sorted((folder / "activity").glob("*.jsonl")):
                if self.single and path.stem == LIBRARIAN:
                    continue
                log = phase.logs.setdefault(path.stem, Log(path))
                changed = log.read() or changed
        changed = self.librarian.read() or changed
        if changed:
            self.version += 1

    def _json(self, path: Path) -> dict | None:
        """The JSON object of ``path`` if it changed since it was last read, else None."""
        try:
            stamp = path.stat().st_mtime
        except OSError:
            return None
        if self._seen.get(path) == stamp:
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # being replaced: read at the next refresh
        self._seen[path] = stamp
        return data if isinstance(data, dict) else None

    @staticmethod
    def _load(phase: Phase, state: dict) -> None:
        phase.status = str(state.get("status") or "")
        phase.ended = state.get("ended")
        phase.rounds = int(state.get("rounds") or 0)
        phase.verdict = state.get("verdict")
        phase.agents = {
            key: Agent(
                key,
                phase.number,
                str(raw.get("role") or "subagent"),
                raw.get("parent"),
                str(raw.get("backend") or ""),
                str(raw.get("model") or ""),
                str(raw.get("status") or ""),
                float(raw.get("started") or 0.0),
                int(raw.get("sessions") or 0),
                int(raw.get("rejections") or 0),
            )
            for key, raw in (state.get("agents") or {}).items()
            if isinstance(raw, dict)
        }
        phase.jobs = [
            Job(
                str(raw.get("id") or key),
                str(raw.get("owner") or ""),
                str(raw.get("command") or ""),
                str(raw.get("cwd") or ""),
                float(raw.get("started") or 0.0),
                raw.get("ended"),
                str(raw.get("status") or ""),
                raw.get("exit_code"),
            )
            for key, raw in (state.get("jobs") or {}).items()
            if isinstance(raw, dict)
        ]


def projects_beside(root: Path) -> list[Path]:
    """The other research projects in the folder that holds ``root``."""
    try:
        siblings = sorted(root.resolve().parent.iterdir())
    except OSError:
        return []
    return [
        path
        for path in siblings
        if path.is_dir()
        and path.resolve() != root.resolve()
        and any((path / ".research" / name).is_file() for name in ("project.json", "state.json"))
    ]
