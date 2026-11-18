"""The library's catalogue: every shelved file, with its agent and commit (PROJECT.md §2, "The library").

Shelving changes no file. The controller lists what a finished agent left in its
folder, freezes the folder and keeps the list here, in
``.research/library.json``; :func:`render` turns it, with the work still in
progress, into ``library/CATALOG.md``. The Librarian's pages must then reach
every catalogued file (see :mod:`research_pipeline.links`).
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent_toolkit.records import atomic_write

from research_pipeline.project import INDEX, LARGE, Project
from research_pipeline.state import Agent

CATALOG = "CATALOG.md"
_LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")


@dataclass
class Shelf:
    """One agent's shelved work."""

    agent: str
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
            self.shelves = {agent: Shelf(**shelf) for agent, shelf in data.items()}

    def save(self, durable: bool = True) -> None:
        payload = json.dumps({agent: asdict(shelf) for agent, shelf in self.shelves.items()}, indent=1)
        atomic_write(self.path, payload, durable=durable)

    def shelve(self, project: Project, agent_id: str, commit: str | None) -> Shelf:
        """Catalogue what ``agent_id``'s folder holds now (replacing an earlier entry, e.g. after a reopening)."""
        shelf = Shelf(agent_id, commit, time.time(), files(project, agent_id))
        self.shelves[agent_id] = shelf
        return shelf


def files(project: Project, agent_id: str) -> dict[str, str]:
    """The files of an agent's folder, each with its index line: what git tracks, and files too large for it.

    What git ignores otherwise (environments, caches) is not part of the work; it stays on disk untouched.
    """
    folder = project.agent_dir(agent_id)
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


def render(project: Project, catalogue: Catalogue, agents: list[Agent], working: set[str]) -> str:
    """``library/CATALOG.md``: every shelved file by agent, then the work in progress (``working`` agents)."""
    lines = [
        "# Catalogue",
        "",
        "Kept by the controller: every shelved file, by agent, then the work in progress in agents' folders. "
        "The Librarian's pages start at [LIBRARY.md](LIBRARY.md). Shelved folders are frozen: copy a file "
        "into your own folder to change it.",
        "",
        "## Shelved",
        "",
    ]
    roles = {agent.id: agent for agent in agents}
    shelves = sorted(catalogue.shelves.values(), key=lambda shelf: shelf.shelved)
    for shelf in shelves:
        agent = roles.get(shelf.agent)
        about = f"{agent.role}, {agent.status}" if agent else "agent"
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(shelf.shelved))
        commit = f", commit {shelf.commit[:12]}" if shelf.commit else ""
        lines += [f"### [{shelf.agent}](../agents/{shelf.agent}/) — {about}, shelved {when}{commit}", ""]
        lines += [
            f"- [{path}]({_href('../' + path)})" + (f" — {line}" if line else "") for path, line in shelf.files.items()
        ]
        lines.append("")
    if not shelves:
        lines += ["Nothing is shelved yet.", ""]
    lines += ["## Work in progress", ""]
    for agent_id in sorted(working):
        index = project.agent_dir(agent_id) / INDEX
        try:
            entries = index.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            entries = []
        entries = [_rebase(line, agent_id) for line in entries if line.lstrip().startswith(("- ", "* "))]
        lines += [f"### [{agent_id}](../agents/{agent_id}/)", "", *(entries or ["- (nothing indexed yet)"]), ""]
    return "\n".join(lines).rstrip() + "\n"


def _href(target: str) -> str:
    """A link target, in angle brackets if it contains spaces."""
    return f"<{target}>" if " " in target else target


def _rebase(line: str, agent_id: str) -> str:
    """An index line of ``agents/<agent_id>/`` with its relative links made relative to ``library/``."""

    def rebase(match: re.Match) -> str:
        target = match.group(1)
        if target.startswith(("/", "#")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            return match.group(0)
        return f"](../agents/{agent_id}/{target})"

    return _LINK_TARGET.sub(rebase, line)
