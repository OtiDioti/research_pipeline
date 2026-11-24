"""What an agent is told about the links in its own Markdown (PROJECT.md §2, "Links").

The convention (:mod:`research_pipeline.links`: links from the project's root) is
asked for by the prompts and checked here, never enforced by a refusal. At the end
of each turn of the primary, a subagent or the Reviewer, the Markdown it may write
(its folder; the primary's phase files; the Reviewer's reviews) changed since its
last check is read, and the links that break the convention (a relative link, an
absolute path into the project, a link from the root that leads nowhere) are listed
for it once, as a notice. Left out: FOLDER_CONTENT.md files (whose entries name
their own files), the controller's TASK.md, PARENT_FEEDBACK.md and MESSAGES.md, hidden folders
and what git ignores (environments, caches). At submit_result every such file is
read, and the list goes with the result to the parent, who decides whether it
matters.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

from research_pipeline import links, prompts
from research_pipeline.project import INDEX, Project

#: The controller's own files at the top of an agent's folder: their links are not the agent's.
CONTROLLER_FILES = ("TASK.md", "PARENT_FEEDBACK.md", "MESSAGES.md")
#: At most this many links in one notice.
LISTED = 30


class LinkCheck:
    """The agents' links of one controller run, checked at the end of their turns and at their results."""

    def __init__(self, project: Project):
        self.project = project
        # Files changed before this controller started were checked by an earlier run, or predate the convention.
        self.started = time.time()
        self.checked: dict[str, float] = {}  # agent id -> when its files were last read
        self.reported: dict[str, set[str]] = {}  # agent id -> the links it was told of

    def found(self, scope: Iterable[Path], since: float = 0.0) -> list[str]:
        """'/path: link (why)' for each link breaking the convention in the Markdown of ``scope`` (files and folders)
        changed since ``since``."""
        root = self.project.root
        found = []
        for name in self.project.files(*(self.project.relative(path) for path in scope)):
            relative = Path(name)
            path = root / relative
            if path.suffix.lower() != ".md" or path.name == INDEX or any(p.startswith(".") for p in relative.parts):
                continue
            if path.name in CONTROLLER_FILES and relative.parent.parent.name == "agents":
                continue
            try:
                if path.stat().st_mtime < since:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found += [f"/{name}: {target} ({why})" for target, why in links.unconventional(text, root)]
        return found

    def turn_ended(self, agent_id: str, scope: Iterable[Path]) -> str | None:
        """After a turn: a notice of the links it has not been told of yet in the files it changed, if any."""
        since = self.checked.get(agent_id, self.started)
        self.checked[agent_id] = time.time()  # before reading: a file written meanwhile is read next time
        reported = self.reported.setdefault(agent_id, set())
        new = [line for line in self.found(scope, since) if line not in reported]
        reported.update(new)
        return prompts.links_to_fix(new[:LISTED], len(new)) if new else None
