"""The phases of a project, and what they share (PROJECT.md §2, "Phases").

An investigation is split into numbered phases, each in its own folder
``phases/<N>/`` with its own objectives, primary, Reviewer, subagents, status and
result. One phase runs at a time; any phase can be continued later, and a new
phase starts a fresh primary with access to the knowledge base the earlier ones
built. Shared by every phase are the human's AGENTS.md and starting_evidence/,
the library and the Librarian.

What the phases share is kept in ``.research/project.json`` (:class:`Home`): the
list of phases (number, title, the phase it builds on), the phase the controller
ran last, the Librarian's agent record and its pending shelving requests. Each
phase's own state is its :class:`~research_pipeline.state.State`, in
``.research/phases/<N>/state.json``.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent_toolkit.records import atomic_write

from research_pipeline.project import EMPTY_INDEX, INDEX, Project
from research_pipeline.state import FINISHED, Agent, State

#: A phase's status before its first start.
NOT_STARTED = "not started"


@dataclass
class Phase:
    """One phase of the project, as the human named it."""

    number: int
    title: str
    builds_on: int | None = None  # the earlier phase its primary starts from, if the human chose one
    created: float = 0.0


@dataclass
class Home:
    """What every phase shares: the phases, the phase run last, the Librarian and its pending requests."""

    phases: list[Phase] = field(default_factory=list)
    active: int | None = None  # the phase the controller ran last
    librarian: Agent | None = None
    shelving: list[str] = field(default_factory=list)  # shelved folders awaiting the Librarian, in order

    @classmethod
    def load(cls, path: Path) -> Home:
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        librarian = data.get("librarian")
        return cls(
            phases=[Phase(**phase) for phase in data.get("phases", [])],
            active=data.get("active"),
            librarian=Agent(**librarian) if librarian else None,
            shelving=list(data.get("shelving", [])),
        )

    def save(self, path: Path, durable: bool = True) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(asdict(self), indent=1), durable=durable)

    def phase(self, number: int) -> Phase | None:
        return next((phase for phase in self.phases if phase.number == number), None)

    @property
    def latest(self) -> int | None:
        """The highest phase number, or None before the first."""
        return max((phase.number for phase in self.phases), default=None)

    def add(self, title: str = "", builds_on: int | None = None) -> Phase:
        """Register the next phase (its folder is created by :meth:`Project.create_phase`)."""
        number = (self.latest or 0) + 1
        phase = Phase(number, title.strip() or f"Phase {number}", builds_on, time.time())
        self.phases.append(phase)
        return phase


@dataclass
class Summary:
    """A phase as seen from outside its controller: from the registry and its stored state."""

    number: int
    title: str
    builds_on: int | None
    status: str  # NOT_STARTED, or the phase state's status (running, pausing, paused, complete, stopped)
    outcome: str | None  # how it last ended, if it did
    result: str  # its result, from the project's root (e.g. 'phases/2/RESULT.md')

    @property
    def folder(self) -> str:
        return f"phases/{self.number}"

    def line(self) -> str:
        """One line about the phase, for agents and indexes."""
        builds = f", building on phase {self.builds_on}" if self.builds_on else ""
        state = self.outcome or self.status
        return f"phase {self.number}, {self.title}{builds} ({self.folder}/): {state}"


def load_state(project: Project) -> State | None:
    """The stored state of ``project``'s phase, or None before its first start."""
    return State.load(project.state_file) if project.state_file.is_file() else None


def summaries(project: Project, home: Home, live: State | None = None) -> list[Summary]:
    """Every phase of the registry, in order, with its status read from its stored state.

    ``live``: the state of ``project``'s phase as its controller holds it (fresher than the stored one).
    """
    found = []
    for phase in sorted(home.phases, key=lambda phase: phase.number):
        state = live if live is not None and phase.number == project.phase else load_state(project.at(phase.number))
        found.append(
            Summary(
                phase.number,
                phase.title,
                phase.builds_on,
                state.status if state else NOT_STARTED,
                state.outcome if state else None,
                project.relative(project.at(phase.number).result),
            )
        )
    return found


def listing(items: list[Summary]) -> str:
    """Phases as a Markdown list for an agent: each with its folder, title, state and result."""
    return "\n".join(f"- {item.line()}; its result: {item.result}" for item in items) or "(none)"


def write_index(project: Project, home: Home, live: State | None = None) -> None:
    """``phases/FOLDER_CONTENT.md``: one line per phase, its title and state (the controller keeps it)."""
    lines = [EMPTY_INDEX.rstrip("\n"), ""]
    for item in summaries(project, home, live):
        builds = f" Builds on phase {item.builds_on}." if item.builds_on else ""
        lines.append(f"- [{item.number}]({item.number}) — {item.title}: {item.outcome or item.status}.{builds}")
    project.phases.mkdir(parents=True, exist_ok=True)
    project.write(project.phases / INDEX, "\n".join(lines) + "\n")


#: How the sidebar colours a phase, by status.
PHASE_COLOURS = {
    NOT_STARTED: "waiting",
    "running": "working",
    "pausing": "paused",
    "paused": "paused",
    "complete": "finished",
    "stopped": "cancelled",
}
#: The phases' sidebar section on the web page.
SECTION = "phases"


def sidebar(project: Project, home: Home, live: tuple[int, State] | None, selected: int) -> dict:
    """The web page's 'Phases' section: each phase's state (``live``: the running phase's, fresher than stored)."""
    items = []
    for summary in summaries(project, home):
        status = live[1].status if live is not None and live[0] == summary.number else summary.status
        detail = status.upper() if status in FINISHED else status
        items.append(
            {
                "id": str(summary.number),
                "label": f"{summary.number}. {summary.title}",
                "detail": detail + (f" · builds on {summary.builds_on}" if summary.builds_on else ""),
                "status": PHASE_COLOURS.get(status, "idle"),
                "running": status in ("running", "pausing") and live is not None and live[0] == summary.number,
                "selected": summary.number == selected,
                "rename": summary.title,
            }
        )
    return {"id": SECTION, "title": "Phases", "items": items, "add": {"label": "New phase"}}
