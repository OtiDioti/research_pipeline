"""The check of a subagent's brief at spawn: its "Prior work" section (PROJECT.md §3, "Spawning").

Before spawning, an agent looks in the library for what the project already has
on the task. The brief shows it in a section headed "Prior work": the library
pages and finished agents' files the task builds on, linked, or what was
searched for and not found. The section may be empty, but it must be there; and
its links must lead somewhere, read from where the subagent reads the brief:
its TASK.md, in a folder beside the parent's.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from research_pipeline import links

#: The title that opens the section, e.g. "## Prior work" or "# Prior work in the library".
SECTION = "Prior work"
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$", re.M)
#: At most this many broken links are listed in a refusal.
LISTED = 20


def section(text: str) -> str | None:
    """The text of the brief's "Prior work" section, up to the next heading of its level or above; None if absent."""
    text = links.without_code(text)
    headings = list(_HEADING.finditer(text))
    for number, heading in enumerate(headings):
        if heading.group(2).lower().startswith(SECTION.lower()):
            level = len(heading.group(1))
            end = next((later.start() for later in headings[number + 1 :] if len(later.group(1)) <= level), len(text))
            return text[heading.end() : end]
    return None


def problem(text: str, name: str, task: Path, root: Path, by_name: Callable[[str], list[Path]]) -> str | None:
    """Why the brief ``name`` (its ``text``) cannot be spawned, to be read as ``task``; None if it can."""
    prior = section(text)
    if prior is None:
        return (
            f'{name} has no "{SECTION}" section. Every brief needs one: a heading "## {SECTION}" followed by '
            "what the project already has for this task (library pages and finished agents' files, each linked), "
            "or what you searched for and did not find. The section may be empty, but it must be there."
        )
    broken = [target for _, target in links.check_text(prior, task, root, by_name).broken]
    if not broken:
        return None
    library = os.path.relpath(root / "library" / "LIBRARY.md", task.parent)
    listed = "\n".join(f"- {target}" for target in broken[:LISTED])
    more = f"\n- … and {len(broken) - LISTED} more" if len(broken) > LISTED else ""
    return (
        f'links in the "{SECTION}" section of {name} lead nowhere. The subagent reads the brief as its TASK.md, '
        f"in a folder beside yours, so links are relative to that folder (from there, the library's entry page "
        f"is {library}):\n{listed}{more}"
    )
