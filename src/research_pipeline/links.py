"""Links in Markdown pages: which files they reach, and which lead nowhere (PROJECT.md §2, "The library").

The Librarian's pages lead to the agents' work with relative links. The
controller checks them: every shelved file must be reachable from a page (a link
to a folder covers everything in it), and no link may lead nowhere. Recognised:
inline links and images (``[text](path)``, ``![alt](path)``), reference
definitions (``[label]: path``) and Obsidian wikilinks (``[[note]]``, resolved
next to the page, from the project root, or by file name as Obsidian does).
Links inside code are not links; external URLs and in-page anchors are ignored.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

_FENCE = re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.M | re.S)
_CODE = re.compile(r"`[^`\n]*`")
_INLINE = re.compile(r"\[(?:[^\]\\\n]|\\.)*\]\(\s*(<[^>\n]*>|[^)\s]+)(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'))?\s*\)")
_REFERENCE = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|\S+)", re.M)
_WIKI = re.compile(r"\[\[([^\]|#\n]*)(?:#[^\]|\n]*)?(?:\|[^\]\n]*)?\]\]")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass
class Report:
    """What a set of pages links to."""

    reached: set[Path] = field(default_factory=set)  # existing files and folders the links lead to
    broken: list[tuple[Path, str]] = field(default_factory=list)  # (page, link) for links that lead nowhere

    def covers(self, path: Path) -> bool:
        """True if ``path`` is linked, or lies in a linked folder."""
        return path in self.reached or any(parent in self.reached for parent in path.parents)


def targets(text: str) -> list[tuple[str, bool]]:
    """The link targets of a Markdown text, each with whether it is a wikilink (code spans and blocks skipped)."""
    text = _CODE.sub("", _FENCE.sub("", text))
    found = [(match.group(1), False) for match in _INLINE.finditer(text)]
    found += [(match.group(1), False) for match in _REFERENCE.finditer(text)]
    found += [(match.group(1), True) for match in _WIKI.finditer(text)]
    return found


def check(pages: Iterable[Path], root: Path, by_name: Callable[[str], list[Path]]) -> Report:
    """Resolve the links of ``pages`` (Markdown files) in the project ``root``.

    ``by_name`` lists the project's files with a given name, for wikilinks that
    name a note rather than a path.
    """
    report = Report()
    for page in pages:
        try:
            text = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target, wiki in targets(text):
            path = _resolve(page, target, wiki, root, by_name)
            if path is None:
                continue  # an external URL or an in-page anchor
            if path.exists():
                report.reached.add(path)
            else:
                report.broken.append((page, target))
    return report


def _resolve(page: Path, target: str, wiki: bool, root: Path, by_name: Callable[[str], list[Path]]) -> Path | None:
    """The path a link leads to (existing or not), or None if it leads outside the files (a URL, an anchor)."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not wiki:
        if not target or target.startswith("#") or _SCHEME.match(target):
            return None
        target = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not target:
            return None
        return _normal(Path(target) if target.startswith("/") else page.parent / target)
    if not target:
        return None  # [[#heading]]: a link within the page
    names = [target] if Path(target).suffix else [target, target + ".md"]
    for name in names:
        for candidate in (page.parent / name, root / name):
            if _normal(candidate).exists():
                return _normal(candidate)
    for name in names:
        if "/" not in name:
            found = by_name(name)
            if found:
                return found[0]
    return _normal(page.parent / names[-1])


def _normal(path: Path) -> Path:
    """``path`` with ``..`` and ``.`` folded, without following symlinks."""
    return Path(os.path.normpath(path))
