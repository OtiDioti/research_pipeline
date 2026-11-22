"""What each agent used, for the web page's graph: the websites and library pages its tool calls reached."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from agent_toolkit.activity import ActivityLog

from research_pipeline.project import INDEX, Project

URL = re.compile(r'https?://[^\s\'"<>)\]]+')
SOURCE = re.compile(r"\blibrary/[\w./-]+")


class Usage:
    """Per agent ('<phase>/<agent>', or the Librarian's id), the sites and the library pages it used."""

    def __init__(self, paths: Project, phases: Iterable[int]):
        """Read what the agents of ``phases`` and the Librarian used so far, from their activity logs."""
        self.root = paths.root
        self.used: dict[str, dict[str, set]] = {}
        for number in phases:
            for entry in ActivityLog(paths.at(number).activity).read(None, limit=200_000):
                self.note(number, entry)
        for entry in ActivityLog(paths.library_activity).read(None, limit=200_000):
            self.note(None, entry)

    def note(self, phase: int | None, entry: dict) -> None:
        """Note the websites and library pages an agent's tool call used (``phase`` None: the Librarian's)."""
        if entry.get("kind") != "tool":
            return
        key = entry["agent"] if phase is None else f"{phase}/{entry['agent']}"
        used = self.used.setdefault(key, {"sites": set(), "pages": set()})
        used["sites"].update(url.rstrip(".,;") for url in URL.findall(entry.get("text", "")))
        for relative in SOURCE.findall(entry.get("text", "")):
            path = Path(self.root) / relative.rstrip(".,;")
            if path.is_file() and path.name != INDEX:
                used["pages"].add(str(path))
