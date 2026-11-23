"""Links in Markdown texts: the project's convention, which files they reach, and what moved text becomes.

Every link in a project's Markdown names its file from the project's root, with a
leading slash (``[the fit](/phases/2/agents/fit/RESULT.md)``), so it leads to the
same file wherever the text is read: in a brief copied to TASK.md, a message, the
catalogue (PROJECT.md §2, "Links"). The one exception is a folder's
FOLDER_CONTENT.md, whose entries name their own files (``[fit.py](fit.py)``).
Text written before the convention keeps its relative links, read from its file's
folder.

The controller checks the Librarian's pages: every shelved file must be reachable
from a page (a link to a folder covers everything in it), and no link may lead
nowhere. Recognised: inline links and images (``[text](path)``, ``![alt](path)``),
reference definitions (``[label]: path``) and Obsidian wikilinks (``[[note]]``,
resolved next to the page, from the project root, or by file name as Obsidian
does). Links inside code are not links; external URLs and in-page anchors are
ignored. :func:`unconventional` finds the links of an agent's text that break the
convention, and :func:`rebase` turns a moved text's relative links into links
from the root.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, unquote

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


@dataclass
class Rebased:
    """A text moved to another folder, and the links in it kept as written although they may not work there."""

    text: str
    nowhere: list[str] = field(default_factory=list)  # reach nothing from either folder
    ambiguous: list[str] = field(default_factory=list)  # reach a different existing file from each folder


def from_root(root: Path, path: Path) -> str:
    """The link to ``path`` (inside the project ``root``), as the convention writes it: ``/phases/…``."""
    return "/" + Path(os.path.relpath(path, root)).as_posix()


def rebase(text: str, source: Path, target: Path, root: Path) -> Rebased:
    """``text``, written in the folder ``source``, made to be read from the folder ``target`` of the project ``root``.

    Each relative link that reaches one existing file or folder, from ``source`` or
    from ``target`` (its author may have written it for the new folder), or the same
    one from both, becomes a link from the root to that file: it then leads there
    wherever the text goes. A link that reaches nothing from either folder, or a
    different file from each, is kept as written and listed for the author. Anchors
    and queries stay; links from the root, wikilinks, URLs and links inside code are
    untouched. A file outside the project is linked relatively from ``target``. The
    folders and the root must be absolute.
    """
    masked = _mask(text)
    spans = {match.span(1) for pattern in (_INLINE, _REFERENCE) for match in pattern.finditer(masked)}
    moved = Rebased("")
    pieces = []
    last = 0
    for start, end in sorted(spans):
        pieces += [text[last:start], _moved(text[start:end], source, target, root, moved)]
        last = end
    moved.text = "".join(pieces) + text[last:]
    return moved


def _moved(link: str, source: Path, target: Path, root: Path, moved: Rebased) -> str:
    """One link target of a text moved from ``source`` to ``target`` (see :func:`rebase`)."""
    bracketed = link.startswith("<") and link.endswith(">")
    inner = link[1:-1].strip() if bracketed else link
    if not inner or inner.startswith(("#", "/")) or _SCHEME.match(inner):
        return link
    cut = min((i for i in (inner.find("#"), inner.find("?")) if i >= 0), default=len(inner))
    path, suffix = inner[:cut], inner[cut:]
    if not path:
        return link
    was, now = _normal(source / unquote(path)), _normal(target / unquote(path))
    reached = [place for place in dict.fromkeys((was, now)) if place.exists()]
    if len(reached) != 1:
        (moved.ambiguous if reached else moved.nowhere).append(inner)
        return link
    file = reached[0]
    written = from_root(root, file) if file.is_relative_to(root) else os.path.relpath(file, target)
    written += "/" if path.endswith("/") and not written.endswith("/") else ""
    written = quote(written, safe="/") if "%" in path else written  # keep the author's encoding
    return f"<{written}{suffix}>" if bracketed or re.search(r"[\s()<>]", written) else written + suffix


def unconventional(text: str, root: Path) -> list[tuple[str, str]]:
    """The links of ``text`` that break the convention, each with why: a relative link, an absolute path into the
    project, or a link from the root that leads nowhere. URLs, anchors, wikilinks and code are left alone."""
    found = []
    for target, wiki in targets(text):
        inner = target.strip().strip("<>").strip()
        if wiki or not inner or inner.startswith("#") or _SCHEME.match(inner):
            continue
        path = unquote(inner.split("#", 1)[0].split("?", 1)[0])
        if not path:
            continue
        if not path.startswith("/"):
            found.append((target, "relative: write it from the project root, with a leading /"))
        elif _normal(root / path.lstrip("/")).exists():
            continue
        elif Path(path).exists():
            if _normal(Path(path)).is_relative_to(root):
                found.append((target, "an absolute path: write it from the project root, with a leading /"))
        else:
            found.append((target, "leads nowhere"))
    return found


def _mask(text: str) -> str:
    """``text`` with code blocks and spans blanked (line breaks kept): its positions are those of ``text``."""

    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return _CODE.sub(blank, _FENCE.sub(blank, text))


def targets(text: str) -> list[tuple[str, bool]]:
    """The link targets of a Markdown text, each with whether it is a wikilink (code spans and blocks skipped)."""
    text = _mask(text)
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
        if not target.startswith("/"):
            return _normal(page.parent / target)
        from_the_root = _normal(root / target.lstrip("/"))  # the convention; an absolute path still works
        return from_the_root if from_the_root.exists() or not Path(target).exists() else _normal(Path(target))
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
