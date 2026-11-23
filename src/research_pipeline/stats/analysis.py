"""The facts behind the Stats view, per agent, from a project's records; deterministic and read-only.

Every access of a tool call (:mod:`research_pipeline.stats.calls`) is resolved to a
project path and attributed to an owner: the agent itself, its parent, one of its
children, another agent, the library (its entry page, the catalogue, the Librarian's
pages), the starting evidence, a phase's own files, or something else. Paths are
attributed by their shape (``phases/<N>/agents/<id>/``, ``library/``, …), so that runs
made with an earlier folder layout are still attributed. From these and the states:
each agent's timeline (at work, idle, its result submitted), the links of its brief
and whether it opened them, the files of its parent it read without being given
them, what its parent read and ran of its work while deciding on it, its library
use, and its resources.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from research_pipeline import links
from research_pipeline.stats.calls import ROOT, Access
from research_pipeline.stats.sources import Agent, Entry, Job, Phase, Source

#: A gap in an agent's activity longer than this (seconds) shows as idle.
IDLE = 600.0
#: Children started within this many seconds of the previous one count as spawned together.
TOGETHER = 600.0
#: An agent's files that are the protocol's, not its work: reading them is not re-reading the work.
PROTOCOL_FILES = frozenset({"RESULT.md", "TASK.md", "FOLDER_CONTENT.md", "HANDOFF.md", "PARENT_FEEDBACK.md"})
#: Statuses after which an agent no longer works.
ENDED = frozenset({"accepted", "cancelled", "finished", "failed", "resting"})
READS = frozenset({"read", "list", "search"})
_AGENT = re.compile(r"(?:^|/)phases/(\d+)/agents/([^/]+)")
_PROJECT = re.compile(r"^\$(\{PROJECT\}|PROJECT)(?=/|$)")
_OLD_AGENT = re.compile(r"^agents/([^/]+)")
#: The places a path can be recognised by, wherever they appear in it.
_ANCHORS = re.compile(r"(?:^|/)(?:phases/(\d+)/)?(agents/[^/]+|library|starting_evidence)(?=/|$)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_PRIOR = re.compile(r"^ {0,3}#{1,6}[ \t]+prior work", re.I | re.M)
_FENCE = re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.M | re.S)


@dataclass
class Touch:
    """A resolved file access by an agent."""

    time: float
    op: str  # 'read', 'run', 'write', 'list', 'search'
    path: str  # relative to the project
    # 'own', 'parent', 'child', 'agent', 'library-entry', 'catalog', 'library-page', 'evidence', 'phase' or 'other'
    kind: str
    owner: str | None  # the owning agent's key, for agents' folders
    job: bool  # from a run_job command


@dataclass
class Review:
    """A child's result between its submission and its parent's decision, and what the parent looked at meanwhile."""

    child: str
    submitted: float
    decided: float | None
    outcome: str  # 'accept', 'reject', 'cancel', or 'pending'
    read_times: list[float] = field(default_factory=list)  # when the parent read, listed or searched the work
    run_times: list[float] = field(default_factory=list)  # when it ran it
    files: set[str] = field(default_factory=set)

    @property
    def reads(self) -> int:
        return len(self.read_times)

    @property
    def runs(self) -> int:
        return len(self.run_times)


@dataclass
class Record:
    """One agent, analysed."""

    key: str
    agent: Agent
    folder: str
    parent: str | None
    children: list[str] = field(default_factory=list)
    depth: int = 0
    entries: list[Entry] = field(default_factory=list)
    touches: list[Touch] = field(default_factory=list)
    end: float = 0.0
    segments: list[tuple[float, float, str]] = field(default_factory=list)
    submissions: list[float] = field(default_factory=list)
    decisions: list[tuple[float, str, str]] = field(default_factory=list)  # its own calls: (time, tool, child id)
    messages_to_parent: int = 0
    links: list[tuple[str, bool]] = field(default_factory=list)  # its brief's links into the project: (path, opened)
    prior_work: bool | None = None  # its brief has a "Prior work" section (None: it has no brief)
    unlinked_parent: list[str] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)  # as a parent
    tools: Counter = field(default_factory=Counter)
    cut: int = 0
    unparsed: int = 0
    max_fill: float | None = None
    jobs: list[Job] = field(default_factory=list)

    @property
    def start(self) -> float:
        """Its first start: the state records the latest (e.g. a reopened primary's), the activity the first."""
        return min([self.agent.started] + [entry.time for entry in self.entries[:1]])

    def library(self, kind: str | None = None) -> list[Touch]:
        kinds = (kind,) if kind else ("library-entry", "catalog", "library-page")
        return [touch for touch in self.touches if touch.kind in kinds and touch.op in READS]


@dataclass
class Shelving:
    """A shelving request to the Librarian and when it was done."""

    folder: str
    requested: float
    done: float | None


@dataclass
class Analysis:
    """A scope of one project, analysed: one phase, or all of them."""

    name: str  # the project's
    scope: str  # a phase number, or 'all'
    start: float
    end: float
    records: dict[str, Record]
    phases: list[Phase]
    shelving: list[Shelving]

    @property
    def calls(self) -> int:
        return sum(sum(record.tools.values()) for record in self.records.values())

    def share(self, attribute: str) -> float:
        """The share of tool calls recorded only in part ('cut') or with an unknown command ('unparsed')."""
        total = self.calls
        return sum(getattr(record, attribute) for record in self.records.values()) / total if total else 0.0


def analyse(source: Source, scope: str) -> Analysis:
    """Analyse ``scope`` of ``source``: a phase number as text, or 'all'."""
    numbers = sorted(source.phases) if scope == "all" else [int(scope)]
    phases = [source.phases[number] for number in numbers if number in source.phases]
    if not phases:
        raise ValueError(f"{source.name} has no phase {scope}")
    many = scope == "all"
    records: dict[str, Record] = {}
    for phase in phases:
        for agent in phase.agents.values():
            key = f"{phase.number}/{agent.id}" if many else agent.id
            parent = (f"{phase.number}/{agent.parent}" if many else agent.parent) if agent.parent else None
            records[key] = Record(key, agent, source.agent_folder(phase.number, agent.id), parent)
            records[key].entries = phase.logs[agent.id].entries if agent.id in phase.logs else []
            records[key].jobs = [job for job in phase.jobs if job.owner == agent.id]
    for record in records.values():
        if record.parent in records:
            records[record.parent].children.append(record.key)
    for record in records.values():
        depth, parent = 0, record.parent
        while parent in records and depth < 50:
            depth, parent = depth + 1, records[parent].parent
        record.depth = depth
    times = [entry.time for record in records.values() for entry in record.entries]
    start = min([record.start for record in records.values()] + times, default=0.0)
    end = max(times + [phase.ended or 0.0 for phase in phases] + [start])
    resolver = _Resolver(source.root)
    for record in records.values():
        _calls(record, records, resolver, many)
    for record in records.values():
        _timeline(record, records, end)
        _brief(record, records, resolver)
    for record in records.values():
        _reviews(record, records)
    shelving = _shelving(source, None if many else numbers[0])
    return Analysis(source.name, scope, start, end, records, phases, shelving)


# Calls and their accesses ---------------------------------------------------------------------


class _Resolver:
    """Turns an access into a project path, remembering which paths exist."""

    def __init__(self, root: Path):
        self.root = root
        self.prefix = str(root) + "/"
        self._exists: dict[str, bool] = {}

    def expand(self, path: str) -> str:
        """``path`` with a leading ``$PROJECT`` (the variable every session and job has) as the project's folder."""
        return _PROJECT.sub(lambda _: self.prefix[:-1], path)

    def exists(self, path: str) -> bool:
        if path not in self._exists:
            self._exists[path] = (self.root / path).exists()
        return self._exists[path]

    def path(self, access: Access, folder: str, phase: int) -> str | None:
        """The project-relative path of ``access`` made by the agent of ``folder``; None if outside the project.

        A path that does not exist (resolved from the wrong folder, as in runs made from the
        project's root or before the phases' layout) is rewritten from its last recognisable
        place: ``…/agents/<id>/x`` becomes ``phases/<N>/agents/<id>/x``, ``…/library/x`` becomes
        ``library/x``.
        """
        relative = self._relative(access, folder)
        if relative is None or self.exists(relative):
            return relative
        anchors = list(_ANCHORS.finditer(relative))
        if not anchors:
            return relative
        last = anchors[-1]
        rest = relative[last.end() :]
        place = last.group(2)
        if place.startswith("agents/"):
            place = f"phases/{last.group(1) or phase}/{place}"
        return place + rest

    def _relative(self, access: Access, folder: str) -> str | None:
        given = self.expand(access.path.strip())
        if not given or given.startswith(("~", "$")) or "://" in given or given == "-":
            return None
        cwd = self.expand(access.cwd) if access.cwd and access.cwd != ROOT else access.cwd
        if cwd == ROOT:
            base = ""
        elif cwd:
            base = cwd if cwd.startswith("/") else posixpath.join(folder, cwd)
        else:
            base = folder
        joined = given if given.startswith("/") else posixpath.join(base, given)
        relative = self._inside(posixpath.normpath(joined))
        if relative is None:
            return None
        if access.cwd is None and not given.startswith("/") and not self.exists(relative):
            alternative = posixpath.normpath(given)  # earlier runs worked from the project's root
            if not alternative.startswith("..") and self.exists(alternative):
                return alternative
        return relative

    def _inside(self, path: str) -> str | None:
        if path.startswith("/"):
            if path == self.prefix[:-1]:
                return ""
            return path[len(self.prefix) :] if path.startswith(self.prefix) else None
        return None if path == ".." or path.startswith("../") else ("" if path == "." else path)


def owner(path: str, phase: int, many: bool) -> tuple[str, str | None]:
    """What ``path`` (project-relative) belongs to: (kind, agent key or None), by its shape."""
    match = _AGENT.search(path)
    if match:
        number, agent = int(match.group(1)), match.group(2)
        return "agent", f"{number}/{agent}" if many or number != phase else agent
    match = _OLD_AGENT.match(path)
    if match:  # the layout before phases: agents/ at the top
        return "agent", f"{phase}/{match.group(1)}" if many else match.group(1)
    if re.search(r"(?:^|/)library/(catalog(/|$)|CATALOG\.md$)", path):
        return "catalog", None
    if re.search(r"(?:^|/)library/LIBRARY\.md$", path):
        return "library-entry", None
    if re.search(r"(?:^|/)library(/|$)", path):
        return "library-page", None
    if re.search(r"(?:^|/)starting_evidence(/|$)", path):
        return "evidence", None
    if path.startswith("phases/"):
        return "phase", None
    return "other", None


def _calls(record: Record, records: dict[str, Record], resolver: _Resolver, many: bool) -> None:
    phase = record.agent.phase
    parent_id = record.agent.parent
    for entry in record.entries:
        if entry.kind == "context" and entry.tokens and entry.window:
            fill = entry.tokens / entry.window
            record.max_fill = fill if record.max_fill is None else max(record.max_fill, fill)
        found = entry.call
        if found is None:
            continue
        record.tools[found.kind] += 1
        record.cut += found.cut
        record.unparsed += 1 if found.unparsed else 0
        if found.kind == "research":
            target = str(found.arguments.get("agent", ""))
            if found.name == "submit_result":
                record.submissions.append(entry.time)
            elif found.name in ("accept", "reject", "cancel") and target:
                record.decisions.append((entry.time, found.name, target))
            elif found.name == "message" and parent_id and target == parent_id:
                record.messages_to_parent += 1
        for access in found.accesses:
            path = resolver.path(access, record.folder, phase)
            if path is None:
                continue
            kind, key = owner(path, phase, many)
            if kind == "agent":
                kind = (
                    "own"
                    if key == record.key
                    else "parent"
                    if key == record.parent
                    else "child"
                    if key in records and records[key].parent == record.key
                    else "agent"
                )
            record.touches.append(Touch(entry.time, access.op, path, kind, key, found.name == "run_job"))


# Timelines ----------------------------------------------------------------------------------


def _timeline(record: Record, records: dict[str, Record], end: float) -> None:
    """At work (activity no more than IDLE apart), idle, and submitted (its result with its parent)."""
    times = sorted(entry.time for entry in record.entries)
    parent = records.get(record.parent) if record.parent else None
    windows = []
    for submitted in record.submissions:
        decided = next(
            (
                time
                for time, _, child in (parent.decisions if parent else [])
                if child == record.agent.id and time >= submitted
            ),
            None,
        )
        windows.append((submitted, decided))
    last = max(times + [record.start] + [decided for _, decided in windows if decided])
    finished = record.agent.status in ENDED or record.agent.status in ("submitted",)
    record.end = last if finished and record.agent.status != "submitted" else max(last, end)
    work: list[tuple[float, float]] = []
    for time in times:
        if work and time - work[-1][1] <= IDLE:
            work[-1] = (work[-1][0], time)
        else:
            work.append((time, time))
    work = [(begin, max(stop, begin + 30.0)) for begin, stop in work]
    segments = [(begin, stop, "working") for begin, stop in work]
    for submitted, decided in windows:
        stop = decided if decided is not None else record.end
        cut = []
        for begin, finish, state in segments:
            if finish <= submitted or begin >= stop:
                cut.append((begin, finish, state))
                continue
            if begin < submitted:
                cut.append((begin, submitted, state))
            if finish > stop:
                cut.append((stop, finish, state))
        segments = cut + [(submitted, max(stop, submitted + 30.0), "submitted")]
    segments.sort()
    filled, cursor = [], record.start
    for begin, finish, state in segments:
        if begin - cursor > 1.0:
            filled.append((cursor, begin, "idle"))
        filled.append((begin, finish, state))
        cursor = max(cursor, finish)
    if record.end - cursor > 1.0 and record.agent.status not in ENDED:
        filled.append((cursor, record.end, "idle"))
    record.segments = filled


def working(records: dict[str, Record]) -> list[tuple[float, float]]:
    """Every agent's stretches at work."""
    return [(begin, end) for record in records.values() for begin, end, state in record.segments if state == "working"]


def concurrent(spans: list[tuple[float, float]]) -> list[tuple[float, int]]:
    """How many of ``spans`` are open over time: [(time, count)], changing at each start or end."""
    marks = sorted(
        [(begin, 1) for begin, _ in spans] + [(end, -1) for _, end in spans], key=lambda mark: (mark[0], mark[1])
    )
    points, count = [], 0
    for time, step in marks:
        count += step
        points.append((time, count))
    return points


# Briefs and the parent's files ----------------------------------------------------------------


def _brief(record: Record, records: dict[str, Record], resolver: _Resolver) -> None:
    """The links of its TASK.md, whether it opened each, and the parent's files it read without a link."""
    if not record.parent:
        return
    try:
        text = (resolver.root / record.folder / "TASK.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    record.prior_work = bool(_PRIOR.search(_FENCE.sub("", text)))
    targets = []
    for target, wiki in links.targets(text):
        target = target.strip().strip("<>")
        if wiki or not target or target.startswith("#") or _SCHEME.match(target):
            continue
        target = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if target.startswith("/") and resolver.exists(target.lstrip("/")):
            target = resolver.prefix + target.lstrip("/")  # a link from the project's root, the convention
        path = resolver.path(Access("read", target, record.folder), "", record.agent.phase) if target else None
        if path is None or path == record.folder or path.startswith(record.folder + "/"):
            continue  # outside the project, or its own folder (e.g. its TASK.md)
        if path not in targets:
            targets.append(path)
    opened = [touch.path for touch in record.touches if touch.op in READS | {"run"}]
    record.links = [(target, any(_under(path, target) for path in opened)) for target in targets]
    parent_reads = sorted(
        {touch.path for touch in record.touches if touch.kind == "parent" and touch.op in READS | {"run"}}
    )
    folder = records[record.parent].folder if record.parent in records else None
    record.unlinked_parent = [
        path for path in parent_reads if path != folder and not any(_under(path, target) for target in targets)
    ]


def _under(path: str, target: str) -> bool:
    return path == target or path.startswith(target.rstrip("/") + "/")


# Reviews by parents ---------------------------------------------------------------------------


def _reviews(record: Record, records: dict[str, Record]) -> None:
    """For each result of each child: what the parent read and ran of the child's work until it decided."""
    for key in record.children:
        child = records[key]
        for submitted in child.submissions:
            decision = next(
                (
                    (time, tool)
                    for time, tool, target in record.decisions
                    if target == child.agent.id and time >= submitted
                ),
                None,
            )
            decided = decision[0] if decision else None
            review = Review(key, submitted, decided, decision[1] if decision else "pending")
            stop = decided if decided is not None else record.end
            for touch in record.touches:
                if touch.owner != key or not submitted <= touch.time <= stop:
                    continue
                if posixpath.basename(touch.path) in PROTOCOL_FILES and posixpath.dirname(touch.path) == child.folder:
                    continue
                if touch.op == "run":
                    review.run_times.append(touch.time)
                elif touch.op in READS:
                    review.read_times.append(touch.time)
                review.files.add(touch.path)
            record.reviews.append(review)


# The Librarian ------------------------------------------------------------------------------

_REQUEST = re.compile(r"Shelving request: the agent of (\S+?)/ ")


def _shelving(source: Source, phase: int | None) -> list[Shelving]:
    """Shelving requests (of ``phase``, or all) and when the Librarian reported each done."""
    found: dict[str, Shelving] = {}
    for entry in source.librarian.entries:
        if entry.kind == "message" and entry.sender == "controller":
            for folder in _REQUEST.findall(entry.text):
                if folder not in found or found[folder].done is not None:
                    found[folder] = Shelving(folder, entry.time, None)
        elif entry.call is not None and entry.call.name == "shelved":
            folder = str(entry.call.arguments.get("folder", "")).strip().strip("/")
            if folder in found and found[folder].done is None:
                found[folder].done = entry.time
    prefix = f"phases/{phase}/" if phase is not None else ""
    return [item for item in found.values() if item.folder.startswith(prefix)]
