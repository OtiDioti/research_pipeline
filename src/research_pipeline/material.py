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

The human may also remove any entry (:func:`remove`), loose or placed, without
losing anything: a copy imported from this machine whose original is still there,
unchanged, is deleted (the original stays); anything else is set aside in
.research/removed/ (hidden from agents, ignored by git), from where
:func:`restore` brings it back as loose material. A placed entry loses its line in
its folder's FOLDER_CONTENT.md, and a folder left with nothing else goes too, with
its own line. Imports are recorded (project path and source) in
.research/material/imports.json, so a copy is recognised after it was placed;
that record and the removed material stay after the start.

When a phase that ended is reopened from the page, the human's files changed
since its end can be reverted (:func:`revert`): a file the end's commit has comes
back from it, a new one is set aside like removed material. A phase's objectives
are its own OBJECTIVES.md (:func:`write_objectives`), in its folder.
"""

from __future__ import annotations

import filecmp
import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from research_pipeline.project import EMPTY_INDEX, INDEX, TOP_LEVEL, Project

TARGET = "starting_evidence"


@dataclass
class Entry:
    """A file or folder the page shows: loose until placed and described."""

    path: str  # relative to the project
    name: str
    size: int | None
    folder: bool
    state: str  # 'loose' or 'placed'
    description: str
    removal: str  # what removing it does ('' if it cannot be removed)


def loose(project: Project) -> list[Path]:
    """Loose entries: unexpected at the top level, or at the top of starting_evidence/ without a description."""
    top = [project.root / name for name in project.stray_entries()]
    return top + (project.undescribed(project.evidence) if project.evidence.is_dir() else [])


def entries(project: Project) -> list[dict]:
    """Every loose entry, then every placed one (the entries of starting_evidence/'s indexed folders)."""
    waiting = {path for path in loose(project)}
    imports = _imports(project)
    found = [_entry(project, path, "loose", "", imports) for path in sorted(waiting)]
    for folder in project.indexed_folders():
        text = _index_text(folder)
        for path in sorted(folder.iterdir()):
            if path.name.startswith(".") or path.name == INDEX or path in waiting:
                continue
            if (path / INDEX).is_file():
                continue  # an indexed folder lists its own entries
            found.append(_entry(project, path, "placed", _description(text, path.name), imports))
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
        parts = Path(folder).parts
        if (
            folder != TARGET
            and not folder.startswith(TARGET + "/")
            or any(p == ".." or p.startswith(".") for p in parts)
        ):
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
    imports = _imports(project)
    for source, destination, description in moves:
        if source.parent != destination:
            shutil.move(source, destination / source.name)
            _follow(imports, project.relative(source), project.relative(destination / source.name))
        _describe(project, destination, source.name, description)
    _write_record(project, IMPORTS, imports)
    return f"Placed {len(moves)} entr{'y' if len(moves) == 1 else 'ies'} in {TARGET}/."


def write_objectives(project: Project, text: str) -> str:
    """Write the phase's OBJECTIVES.md (the human's editor and the assistant alike); its folder's index has it."""
    project.create_phase()
    project.write(project.objectives, text if text.endswith("\n") or not text else text + "\n")
    return f"Wrote {project.relative(project.objectives)}."


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
    imports = _imports(project)
    for source in sources:
        if source.is_dir():
            shutil.copytree(source, project.root / source.name, symlinks=True)
        else:
            shutil.copy2(source, project.root / source.name)
        imports[source.name] = str(source)
    _write_record(project, IMPORTS, imports)
    return f"Copied {len(sources)} into the project."


def remove(project: Project, path: str) -> str:
    """Take an entry (``path`` relative to the project, as :func:`entries` lists it) out of the material.

    An imported copy whose original is unchanged is deleted; anything else is set aside
    in .research/removed/. Raise ValueError if ``path`` is not a removable entry.
    """
    path = _clean(path)
    entry = next((item for item in entries(project) if item["path"] == path), None)
    if entry is None or not entry["removal"]:
        raise ValueError(f"{path or '(no path)'}: not removable material (see the list of entries)")
    target, imports = project.root / path, _imports(project)
    source = _source(imports, path)
    original = source is not None and not source.resolve().is_relative_to(project.root.resolve())
    if source is not None and original and _same(target, source):
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        done = f"Deleted the copy of {path}; the original stays at {source}."
    else:
        _set_aside(project, path, None if entry["folder"] else entry["size"], source)
        done = f"Set {path} aside in .research/removed/: restore it from the Removed list."
    for key in [key for key in imports if key == path or key.startswith(path + "/")]:
        del imports[key]
    _write_record(project, IMPORTS, imports)
    _unlist(project, target)
    return done


def _set_aside(project: Project, path: str, size: int | None, source: Path | None = None) -> None:
    """Move ``path`` (relative to the project) into its own slot of .research/removed/, and record it."""
    target, removed = project.root / path, _removed(project)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    slot = next(f"{stamp}-{n}" for n in range(1, 10_000) if not (project.removed / f"{stamp}-{n}").exists())
    (project.removed / slot).mkdir(parents=True)
    folder = target.is_dir() and not target.is_symlink()
    shutil.move(target, project.removed / slot / target.name)
    item = {"id": slot, "path": path, "name": target.name, "size": size, "folder": folder}
    removed.append(item | ({"source": str(source)} if source is not None else {}))
    _write_record(project, REMOVED, removed)


def reverting(project: Project, commit: str | None, existed: bool, path: str) -> str:
    """What reverting the human's file ``path`` to ``commit`` does, in one line ('' : it cannot be reverted).

    ``existed``: the file was there at the end (in the fingerprint taken with ``commit``).
    """
    if not commit:
        return ""
    if _committed(project, commit, path):
        return "It comes back as it was at the end."
    if existed:
        return ""  # too large to be committed: its version at the end was never kept
    return "It is set aside in .research/removed/ (restore it from the Removed list)."


def revert(project: Project, commit: str | None, existed: bool, path: str) -> str:
    """Undo the change of the human's file ``path`` since the end's ``commit`` (see :func:`reverting`)."""
    path = _clean(path)
    if not reverting(project, commit, existed, path):
        raise ValueError(f"{path}: its version at the end was not committed (too large?), so it cannot be reverted")
    assert commit is not None
    if _committed(project, commit, path):
        project.git("checkout", commit, "--", path)
        return f"{path} is back as it was at the end."
    target = project.root / path
    if not target.is_file():
        raise ValueError(f"{path}: not there any more")
    _set_aside(project, path, target.stat().st_size)
    imports = _imports(project)
    if imports.pop(path, None) is not None:
        _write_record(project, IMPORTS, imports)
    _unlist(project, target)
    return f"Set {path} aside in .research/removed/: restore it from the Removed list."


def _committed(project: Project, commit: str, path: str) -> bool:
    return project.git("ls-tree", "--name-only", commit, "--", path, check=False).strip() == path


def restore(project: Project, id: str) -> str:
    """Bring removed material back to the top level as loose material; raise ValueError if it cannot be."""
    removed = _removed(project)
    item = next((item for item in removed if item["id"] == id), None)
    if item is None:
        raise ValueError("nothing removed has this id (it may have been restored already)")
    _check_name(project, item["name"])
    slot = project.removed / item["id"]
    shutil.move(slot / item["name"], project.root / item["name"])
    shutil.rmtree(slot)
    _write_record(project, REMOVED, [other for other in removed if other["id"] != id])
    if item.get("source"):
        imports = _imports(project)
        imports[item["name"]] = item["source"]
        _write_record(project, IMPORTS, imports)
    return f"Restored {item['name']} as loose material."


def removed(project: Project) -> list[dict]:
    """What :func:`remove` set aside, oldest first, as agent_toolkit.web's *removed* entries."""
    return [{key: item[key] for key in ("id", "path", "name", "size", "folder")} for item in _removed(project)]


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


def _entry(project: Project, path: Path, state: str, description: str, imports: dict[str, str]) -> Entry:
    folder, relative = path.is_dir(), project.relative(path)
    source = _source(imports, relative)
    if path == project.objectives:
        removal = ""  # written in the Objectives step, never material
    elif source is not None:
        removal = (
            f"Its copy is deleted if it still matches the original at {source}, which stays there; "
            "otherwise it is set aside in .research/removed/, from where it can be restored."
        )
    else:
        removal = "It is set aside in .research/removed/ (nothing is deleted), from where it can be restored."
    size = None if folder else path.stat().st_size
    return Entry(relative, path.name, size, folder, state, description, removal)


#: The setup's records of material, in .research/ (not in setup/, the assistant's folder, removed at the start).
RECORDS = "material"
IMPORTS = "imports.json"
REMOVED = "removed.json"


def _record(project: Project, name: str, empty):
    """A record in .research/material/ (``empty`` if there is none, or it is unreadable)."""
    try:
        return json.loads((project.research / RECORDS / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty


def _write_record(project: Project, name: str, data) -> None:
    (project.research / RECORDS).mkdir(parents=True, exist_ok=True)
    project.write(project.research / RECORDS / name, json.dumps(data, indent=1) + "\n")


def _imports(project: Project) -> dict[str, str]:
    """Imported copies: their path in the project -> where they were copied from."""
    return _record(project, IMPORTS, {})


def _removed(project: Project) -> list[dict]:
    """Material set aside: ``{id, path, name, size, folder}`` and, for an imported copy, its ``source``."""
    return _record(project, REMOVED, [])


def _source(imports: dict[str, str], path: str) -> Path | None:
    """Where the imported ``path`` (or the file of an imported folder) came from, or None."""
    for key, source in imports.items():
        if path == key or path.startswith(key + "/"):
            return Path(source) / path[len(key) :].lstrip("/")
    return None


def _follow(imports: dict[str, str], old: str, new: str) -> None:
    """Keep the import records of an entry that moved from ``old`` to ``new`` (both project paths)."""
    for key in [key for key in imports if key == old or key.startswith(old + "/")]:
        imports[new + key[len(old) :]] = imports.pop(key)


def _same(copy: Path, original: Path) -> bool:
    """Whether ``copy`` is still byte for byte ``original`` (a folder: the same names, links and contents)."""
    try:
        if copy.is_symlink() or original.is_symlink():
            return copy.is_symlink() and original.is_symlink() and os.readlink(copy) == os.readlink(original)
        if copy.is_dir() and original.is_dir():
            names = sorted(entry.name for entry in copy.iterdir())
            if names != sorted(entry.name for entry in original.iterdir()):
                return False
            return all(_same(copy / name, original / name) for name in names)
        return copy.is_file() and original.is_file() and filecmp.cmp(copy, original, shallow=False)
    except OSError:  # unreadable: keep the copy
        return False


def _unlist(project: Project, path: Path) -> None:
    """Drop a removed entry's line from its folder's index; a folder left empty goes too, with its own line."""
    folder = path.parent
    index = folder / INDEX
    if not folder.is_relative_to(project.evidence) or not index.is_file():
        return  # loose at the top level: no index lists it
    try:
        text = index.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return  # not written by the setup: the human's, left as it is
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines if not (line.lstrip().startswith(("-", "*")) and f"[{path.name}]" in line)]
    if kept != lines:
        project.write(index, "".join(kept))
    if folder == project.evidence or any(entry.name != INDEX for entry in folder.iterdir()):
        return
    if "".join(kept).strip() != EMPTY_INDEX.strip():
        return  # the index says more than its title: the human's, kept
    index.unlink()
    folder.rmdir()
    _unlist(project, folder)


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
