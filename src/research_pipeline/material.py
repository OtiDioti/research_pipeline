"""The web setup's deterministic part: material coming into a folder, and its place in starting_evidence/.

Material arrives *loose* at the project's top level: uploaded from the page,
copied from paths on this machine, or put there by hand. Placing it moves each
loose entry into a folder of starting_evidence/ and describes it in one line in
that folder's FOLDER_CONTENT.md; a new folder is described in its parent's. An
entry already at the top of starting_evidence/ but not described there is loose
too, and placing it only adds its line. The person places material by hand on
the page, or the setup assistant submits the same placement through its tool
(:mod:`research_pipeline.assistant`); both go through :func:`place`, which checks
everything before it moves anything. Nothing is ever overwritten.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from research_pipeline.project import EMPTY_INDEX, INDEX, TOP_LEVEL, Project

TARGET = "starting_evidence"
OBJECTIVES_LINE = "The objectives: the questions to answer and the tasks to perform."


@dataclass
class Entry:
    """A file or folder the page shows: loose until placed and described."""

    path: str  # relative to the project
    name: str
    size: int | None
    folder: bool
    state: str  # 'loose' or 'placed'
    description: str


def loose(project: Project) -> list[Path]:
    """Loose entries: unexpected at the top level, or at the top of starting_evidence/ without a description."""
    top = [project.root / name for name in project.stray_entries()]
    return top + (project.undescribed(project.evidence) if project.evidence.is_dir() else [])


def entries(project: Project) -> list[dict]:
    """Every loose entry, then every placed one (the entries of starting_evidence/'s indexed folders)."""
    waiting = {path for path in loose(project)}
    found = [_entry(project, path, "loose", "") for path in sorted(waiting)]
    for folder in project.indexed_folders():
        text = _index_text(folder)
        for path in sorted(folder.iterdir()):
            if path.name.startswith(".") or path.name == INDEX or path in waiting:
                continue
            if (path / INDEX).is_file():
                continue  # an indexed folder lists its own entries
            found.append(_entry(project, path, "placed", _description(text, path.name)))
    return [asdict(entry) for entry in found]


def folders(project: Project) -> list[str]:
    """The folders material can be placed in (relative to the project), starting_evidence/ first."""
    return [project.relative(folder) for folder in project.indexed_folders()] or [TARGET]


def place(project: Project, items: list[dict], new_folders: list[dict]) -> str:
    """Place loose entries: ``items`` are ``{path, folder, description}``, ``new_folders`` ``{path, description}``.

    Every folder created on the way needs its description. Raise ValueError naming every
    problem, before anything moves.
    """
    waiting = {project.relative(path): path for path in loose(project)}
    described = {
        _clean(str(item.get("path") or "")): str(item.get("description") or "").strip() for item in new_folders
    }
    known = {project.relative(folder) for folder in project.indexed_folders()}
    problems, moves, creating, taken = [], [], {}, set()
    for item in items:
        path, folder = _clean(str(item.get("path") or "")), _clean(str(item.get("folder") or TARGET))
        description = str(item.get("description") or "").strip()
        source = waiting.get(path)
        if source is None:
            problems.append(f"{path or '(no path)'}: not loose material (see the list of loose entries)")
            continue
        if not description or "\n" in description:
            problems.append(f"{path}: needs a one-line description")
        if folder != TARGET and not folder.startswith(TARGET + "/") or ".." in Path(folder).parts:
            problems.append(f"{path}: {folder} is not a folder of {TARGET}/")
            continue
        if source.parent == project.evidence and folder != TARGET:
            problems.append(f"{path}: it is in {TARGET}/ already; it only needs its description there")
            continue
        destination = project.root / folder
        if destination.exists() and not (destination / INDEX).is_file() and folder not in known:
            problems.append(f"{path}: {folder} is described as one unit; choose a folder with its own {INDEX}")
            continue
        for parent in [*reversed(Path(folder).parents), Path(folder)]:  # every new folder on the way
            name = str(parent)
            if name.startswith(TARGET + "/") and not (project.root / name).exists() and name not in creating:
                creating[name] = described.get(name, "")
                if not creating[name]:
                    problems.append(f"the new folder {name} needs a one-line description")
        target = destination / source.name
        if source.parent != destination and (target.exists() or str(target) in taken):
            problems.append(f"{path}: {folder}/{source.name} exists already")
        taken.add(str(target))
        moves.append((source, destination, description))
    if problems:
        raise ValueError("; ".join(problems))
    project.evidence.mkdir(exist_ok=True)
    for name, description in creating.items():
        (project.root / name).mkdir()
        _describe(project, project.root / name, None, None)  # its own index, empty for now
        _describe(project, (project.root / name).parent, name.rsplit("/", 1)[1], description)
    for source, destination, description in moves:
        if source.parent != destination:
            shutil.move(source, destination / source.name)
        _describe(project, destination, source.name, description)
    return f"Placed {len(moves)} entr{'y' if len(moves) == 1 else 'ies'} in {TARGET}/."


def write_objectives(project: Project, text: str) -> str:
    """Write starting_evidence/OBJECTIVES.md (the human's editor and the assistant alike), with its index line."""
    project.evidence.mkdir(exist_ok=True)
    project.write(project.objectives, text if text.endswith("\n") or not text else text + "\n")
    _describe(project, project.evidence, project.objectives.name, OBJECTIVES_LINE)
    return f"Wrote {TARGET}/{project.objectives.name}."


def import_paths(project: Project, paths: list[str]) -> str:
    """Copy files or folders of this machine into the project's top level, as loose material."""
    problems, sources = [], []
    for given in paths:
        source = Path(str(given)).expanduser().resolve()
        if not source.exists():
            problems.append(f"{given}: does not exist")
        elif source.is_relative_to(project.root):
            problems.append(f"{given}: is in the project already")
        else:
            try:
                _check_name(project, source.name)
            except ValueError as error:
                problems.append(f"{given}: {error}")
            sources.append(source)
    if problems:
        raise ValueError("; ".join(problems))
    for source in sources:
        if source.is_dir():
            shutil.copytree(source, project.root / source.name, symlinks=True)
        else:
            shutil.copy2(source, project.root / source.name)
    return f"Copied {len(sources)} into the project."


def upload_target(project: Project, path: str) -> Path:
    """Where a file dropped on the page at ``path`` goes: the project's top level, as loose material."""
    relative = Path(path)
    if (
        not path
        or relative.is_absolute()
        or any(part in ("", ".", "..") or part.startswith(".") for part in relative.parts)
    ):
        raise ValueError(f"not a valid name: {path!r}")
    _check_name(project, relative.parts[0], exists_ok=len(relative.parts) > 1)
    return project.root / relative


def _check_name(project: Project, name: str, exists_ok: bool = False) -> None:
    """Refuse a top-level name the project reserves, or (unless ``exists_ok``) one that exists."""
    if name in TOP_LEVEL or name.startswith("."):
        raise ValueError(f"{name} is a name the project reserves")
    if not exists_ok and (project.root / name).exists():
        raise ValueError(f"{name} exists already at the top level")


def _clean(path: str) -> str:
    return path.strip().strip("/")


def _entry(project: Project, path: Path, state: str, description: str) -> Entry:
    folder = path.is_dir()
    return Entry(project.relative(path), path.name, None if folder else path.stat().st_size, folder, state, description)


def _index_text(folder: Path) -> str:
    index = folder / INDEX
    return index.read_text(encoding="utf-8", errors="replace") if index.is_file() else ""


def _description(text: str, name: str) -> str:
    """The description of ``name`` in an index (the text after its link), or ''."""
    for line in text.splitlines():
        if f"[{name}]" in line:
            return re.sub(r"^.*?\]\([^)]*\)\s*[—-]*\s*", "", line).strip()
    return ""


def _describe(project: Project, folder: Path, name: str | None, description: str | None) -> None:
    """Add ``name``'s line to ``folder``'s FOLDER_CONTENT.md, creating the index if needed (None: only create it)."""
    index = folder / INDEX
    text = index.read_text(encoding="utf-8") if index.is_file() else EMPTY_INDEX
    if name is not None and f"[{name}]" not in text:
        link = name.replace(" ", "%20")
        text = (
            text.rstrip("\n")
            + ("\n\n" if text.strip() == EMPTY_INDEX.strip() else "\n")
            + f"- [{name}]({link}) — {description}\n"
        )
    if name is not None or not index.exists():
        project.write(index, text)
