"""The library's catalogue: every shelved file, with its agent and commit (PROJECT.md §2, "The library").

Shelving changes no file. The controller lists what a finished agent left in its
folder, freezes the folder and keeps the list here, in
``.research/library.json``, under the folder's path (e.g. ``phases/2/agents/fit``:
agent ids repeat across phases); :func:`render` turns it into ``library/CATALOG.md``,
a short index of the shelved agents (with their tasks) and of the agents at work,
and one page per shelved agent in ``library/catalog/`` listing its files with
their index lines, which agents search. The Librarian's pages must then reach
every catalogued file (see :mod:`research_pipeline.links`); the catalogue's own
pages do not count.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent_toolkit.records import atomic_write

from research_pipeline.project import CATALOG_PAGES, EMPTY_INDEX, INDEX, LARGE, Project

CATALOG = "CATALOG.md"
#: A phase's agent folder, e.g. 'phases/2/agents/fit'.
_AGENT_FOLDER = re.compile(r"phases/(\d+)/agents/([^/]+)")
#: Task titles longer than this are shortened in the catalogue.
_TITLE = 120


@dataclass
class Shelf:
    """One agent's shelved work."""

    folder: str  # the agent's folder, relative to the project
    about: str  # who it is, e.g. 'primary, finished, phase 2'
    commit: str | None  # the commit at shelving
    shelved: float  # when
    files: dict[str, str] = field(default_factory=dict)  # project-relative path -> its index line


class Catalogue:
    """Every shelved agent's files, kept in one JSON file beside the controller's state."""

    def __init__(self, path: Path):
        self.path = path
        self.shelves: dict[str, Shelf] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.shelves = {folder: Shelf(**shelf) for folder, shelf in data.items()}

    def save(self, durable: bool = True) -> None:
        payload = json.dumps({folder: asdict(shelf) for folder, shelf in self.shelves.items()}, indent=1)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, payload, durable=durable)

    def shelve(self, project: Project, folder: Path, about: str, commit: str | None) -> Shelf:
        """Catalogue what ``folder`` holds now (replacing an earlier entry, e.g. after a reopening)."""
        key = project.relative(folder)
        shelf = Shelf(key, about, commit, time.time(), files(project, folder))
        self.shelves[key] = shelf
        return shelf


def files(project: Project, folder: Path) -> dict[str, str]:
    """The files of an agent's folder, each with its index line: what git tracks, and files too large for it.

    What git ignores otherwise (environments, caches) is not part of the work; it stays on disk untouched.
    """
    relative = project.relative(folder)
    listed = set(project.git("ls-files", "-z", "--", relative, check=False).split("\0")) - {""}
    for directory, folders, names in os.walk(folder):
        folders[:] = [name for name in folders if not name.startswith(".")]
        for name in names:
            path = Path(directory) / name
            try:
                if path.stat().st_size > LARGE:
                    listed.add(project.relative(path))
            except OSError:
                continue
    lines: dict[Path, list[str]] = {}
    return {path: _index_line(project.root / path, lines) for path in sorted(listed)}


def _index_line(path: Path, cache: dict[Path, list[str]]) -> str:
    """What the index of ``path``'s folder says about it ('' if nothing)."""
    if path.parent not in cache:
        try:
            cache[path.parent] = (path.parent / INDEX).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            cache[path.parent] = []
    for line in cache[path.parent]:
        if f"[{path.name}]" in line or f"({path.name})" in line:
            return line.split(" — ", 1)[-1].strip() if " — " in line else line.strip("-* ").strip()
    return ""


def page(folder: str) -> str:
    """The catalogue page (relative to ``library/``) of a shelved agent's folder, e.g. 'catalog/phase-2/fit.md'."""
    match = _AGENT_FOLDER.fullmatch(folder)
    if match:
        return f"{CATALOG_PAGES}/phase-{match.group(1)}/{match.group(2)}.md"
    return f"{CATALOG_PAGES}/{folder.replace('/', '-')}.md"


def render(project: Project, catalogue: Catalogue, working: dict[str, str]) -> dict[str, str]:
    """The catalogue's files, by path relative to ``library/``: the index ``CATALOG.md``, and a page per shelved agent.

    ``working`` maps the folders of the agents at work to who they are (e.g. 'subagent, running').
    """
    shelves = sorted(catalogue.shelves.values(), key=lambda shelf: shelf.shelved)
    files = {page(shelf.folder): _shelf_page(project, shelf) for shelf in shelves}
    lines = [
        "# Catalogue",
        "",
        "Kept by the controller. The Librarian's pages start at [LIBRARY.md](LIBRARY.md). Below: every shelved agent "
        "with its task, then the agents at work. Each shelved agent's page in "
        f"[{CATALOG_PAGES}/]({CATALOG_PAGES}/{INDEX}) lists its files with their descriptions: search them all at once "
        f"in library/{CATALOG_PAGES}/. Shelved folders are frozen: copy a file into your own folder to change it.",
        "",
        "## Shelved",
        "",
    ]
    phases: dict[str, list[str]] = {}
    for shelf in shelves:
        match = _AGENT_FOLDER.fullmatch(shelf.folder)
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(shelf.shelved))
        task = _task(project, shelf.folder)
        phases.setdefault(f"Phase {match.group(1)}" if match else "Other", []).append(
            f"- [{shelf.folder}]({page(shelf.folder)})"
            + (f" — {task}" if task else "")
            + f" ({shelf.about}; {len(shelf.files)} files; shelved {when})"
        )
    for heading, entries in phases.items():
        lines += [f"### {heading}", "", *entries, ""]
    if not shelves:
        lines += ["Nothing is shelved yet.", ""]
    lines += ["## Work in progress", ""]
    for folder in sorted(working):
        task = _task(project, folder)
        lines.append(
            f"- [{folder}](../{folder}/)" + (f" — {task}" if task else "") + f" ({working[folder]}); its files: "
            f"[{INDEX}](../{folder}/{INDEX})"
        )
    if not working:
        lines.append("Nobody is at work.")
    files[CATALOG] = "\n".join(lines).rstrip() + "\n"
    described = {page(shelf.folder): f"The files of {shelf.folder}." for shelf in shelves}
    tree: dict[str, set[str]] = {CATALOG_PAGES: set()}  # each folder of catalog/ with its entries
    for path in described:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            tree.setdefault("/".join(parts[:depth]), set()).add(parts[depth])
    for folder, names in tree.items():
        entries = [
            f"- [{name}]({name}) — "
            + described.get(f"{folder}/{name}", f"The shelved agents of {name.replace('-', ' ')}, one page each.")
            for name in sorted(names)
        ]
        files[f"{folder}/{INDEX}"] = EMPTY_INDEX + "".join(entry + "\n" for entry in entries)
    return files


def _shelf_page(project: Project, shelf: Shelf) -> str:
    """The catalogue page of one shelved agent: who it is, then each of its files with its index line."""
    up = "../" * page(shelf.folder).count("/") + "../"  # from the page's folder to the project
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(shelf.shelved))
    commit = f", commit {shelf.commit[:12]}" if shelf.commit else ""
    task = _task(project, shelf.folder)
    lines = [
        f"# [{shelf.folder}]({_href(up + shelf.folder + '/')})",
        "",
        f"{shelf.about}; shelved {when}{commit}." + (f" Task: {task}" if task else ""),
        "",
    ]
    lines += [f"- [{path}]({_href(up + path)})" + (f" — {line}" if line else "") for path, line in shelf.files.items()]
    if not shelf.files:
        lines.append("Nothing was shelved from this folder.")
    return "\n".join(lines) + "\n"


def _task(project: Project, folder: str) -> str:
    """The title of the agent's TASK.md (its first heading, or else its first line), '' if it has none."""
    try:
        text = (project.root / folder / "TASK.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = next((line for line in lines if line.startswith("#")), lines[0] if lines else "")
    title = title.lstrip("#").strip()
    return title if len(title) <= _TITLE else title[: _TITLE - 1].rstrip() + "…"


def _href(target: str) -> str:
    """A link target, in angle brackets if it contains spaces."""
    return f"<{target}>" if " " in target else target
