"""Explicit, read-only scientific references. Also runs standalone inside isolation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time


class ReferenceError(ValueError):
    pass


REGISTRY = ".research_pipeline/references.json"
ALIAS = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")


def check_deadline(deadline, on_poll=None):
    if on_poll and (reason := on_poll()):
        from .isolation import RequestedStop
        raise RequestedStop(reason)
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Reference preparation deadline reached")


def ordinary(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ReferenceError(f"Symlinked reference path is unsupported: {path}")
    mode = path.stat().st_mode
    if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
        raise ReferenceError(f"Special reference file is unsupported: {path}")


def load_registry(project):
    path = project / REGISTRY
    if not path.exists() and not path.is_symlink():
        return {"version": 1, "references": {}}
    try:
        ordinary(path)
        if path.stat().st_size > 256 * 1024:
            raise ReferenceError("Reference registry exceeds 256 KiB")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or set(value) != {"version", "references"}
                or type(value["version"]) is not int or value["version"] != 1
                or not isinstance(value["references"], dict)):
            raise ReferenceError("Expected version 1 reference registry with paths only")
        for alias, root in value["references"].items():
            if (not ALIAS.fullmatch(alias) or not isinstance(root, str)
                    or not Path(root).is_absolute() or ".." in Path(root).parts):
                raise ReferenceError(f"Invalid reference alias/path: {alias}")
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReferenceError(f"Cannot load {path}: {exc}") from exc


def validate_reference_root(project, root):
    if ".." in Path(root).parts:
        raise ReferenceError("Parent traversal in reference roots is unsupported")
    project, root = Path(os.path.abspath(project)), Path(os.path.abspath(root))
    ordinary(root)
    if not root.is_dir():
        raise ReferenceError(f"Reference root must be an existing directory: {root}")
    if project.is_relative_to(root) or root.is_relative_to(project):
        raise ReferenceError("Reference and target directories must not overlap")
    return root


def reference_entries(root, deadline=None, on_poll=None):
    """Expose non-hidden root entries, validating every exposed descendant."""
    check_deadline(deadline, on_poll)
    ordinary(root)
    entries = []
    pending = [root]
    while pending:
        check_deadline(deadline, on_poll)
        directory = pending.pop()
        # Poll while enumerating too: os.walk collects a whole directory before
        # yielding, which can itself stall the foreground owner on a large tree.
        with os.scandir(directory) as children:
            for child in children:
                check_deadline(deadline, on_poll)
                if directory == root and child.name.startswith("."):
                    continue
                entry = Path(child.path)
                ordinary(entry)
                if directory == root:
                    entries.append(entry)
                if entry.is_dir():
                    pending.append(entry)
    check_deadline(deadline, on_poll)
    return sorted(entries)


def load_catalog(project, deadline=None, on_poll=None):
    catalog = {}
    check_deadline(deadline, on_poll)
    for alias, name in sorted(load_registry(project)["references"].items()):
        check_deadline(deadline, on_poll)
        record = {"root": name, "path": name, "namespace": f"/references/{alias}",
                  "available": False, "reason": None}
        try:
            root = validate_reference_root(project, name)
            reference_entries(root, deadline, on_poll)
            record["available"] = True
        except TimeoutError:
            raise
        except (OSError, ReferenceError) as exc:
            record["reason"] = f"Reference unavailable; restore or reauthorize its path: {exc}"
        catalog[alias] = record
    check_deadline(deadline, on_poll)
    return catalog


def configure(config, project, session, intake):
    """Refresh on every activation; catalog is outside writable scientific drafts."""
    from . import workspace
    on_poll = (lambda: config.on_poll(research=False)) if config.on_poll else None
    catalog = load_catalog(project, config.deadline, on_poll)
    intake.references = catalog
    mounts, isolated = [], {}
    for alias, record in catalog.items():
        isolated[alias] = {**record, "path": record["namespace"]}
        if record["available"]:
            mounts.append((None, record["namespace"]))
            for entry in reference_entries(Path(record["root"]), config.deadline, on_poll):
                mounts.append((str(entry), f"{record['namespace']}/{entry.name}"))
    config.reference_mounts = tuple(mounts)
    config.reference_catalog = session / "references.json"
    check_deadline(config.deadline, on_poll)
    workspace.atomic_text(config.reference_catalog, json.dumps(isolated, indent=2) + "\n")


def resolve(catalog, alias, relative=".", directory=False):
    if alias not in catalog:
        raise ReferenceError(f"Reference alias is not authorized: {alias}")
    record = catalog[alias]
    if not record["available"]:
        raise ReferenceError(record["reason"])
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or any(p.startswith(".") for p in rel.parts[:1]):
        raise ReferenceError(f"Unsafe or private source-relative path: {relative}")
    root = Path(record["path"])
    path = root / rel
    ordinary(path)
    if not path.is_relative_to(root):
        raise ReferenceError("Path is outside the authorized reference")
    if directory and not path.is_dir():
        raise ReferenceError(f"Expected reference directory: {relative}")
    if not directory and not path.is_file():
        raise ReferenceError(f"Expected reference file: {relative}")
    return record, path


def identity(record, alias, relative):
    return {"alias": alias, "root": record["root"], "path": relative,
            "source_uri": (Path(record["root"]) / relative).as_uri()}


def bound(value, maximum, name):
    if not 1 <= value <= maximum:
        raise ReferenceError(f"{name} must be between 1 and {maximum}")


def browse(catalog, alias, relative_directory=".", max_entries=100, offset=0):
    bound(max_entries, 1000, "max_entries")
    if offset < 0:
        raise ReferenceError("offset must be nonnegative")
    record, path = resolve(catalog, alias, relative_directory, directory=True)
    entries, errors = [], []
    visible = [p for p in sorted(path.iterdir()) if not (
        path == Path(record["path"]) and p.name.startswith("."))]
    for p in visible[offset:offset + max_entries]:
        rel = p.relative_to(record["path"]).as_posix()
        try:
            ordinary(p)
            entries.append({"path": rel, "type": "directory" if p.is_dir() else "file",
                            "bytes": p.stat().st_size if p.is_file() else None})
        except OSError as exc:
            errors.append(f"{rel}: {exc}")
        except ReferenceError as exc:
            errors.append(str(exc))
    more = offset + max_entries < len(visible)
    return {**identity(record, alias, relative_directory), "entries": entries, "errors": errors,
            "truncated": more, "next_offset": offset + max_entries if more else None}


def signature(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def text_lines(path):
    """Stream full UTF-8 contents; reject binary/NUL and unstable observations."""
    ordinary(path)
    if not path.stat().st_mode & 0o444:
        raise ReferenceError(f"Unreadable reference: {path}")
    if path.suffix.lower() == ".pdf":
        raise ReferenceError("Unsupported binary/PDF content; text extraction is not provided")
    with path.open("rb") as stream:
        before = signature(os.fstat(stream.fileno()))
        for number, raw in enumerate(stream, 1):
            if b"\0" in raw:
                raise ReferenceError("Unsupported binary content (NUL byte)")
            yield number, raw, raw.decode("utf-8")
        if before != signature(os.fstat(stream.fileno())) or before != signature(path.stat()):
            raise ReferenceError(f"Reference changed while reading; retry: {path}")


def read_artifact(catalog, alias, relative_path, start_line=1, max_lines=100):
    bound(max_lines, 1000, "max_lines")
    if start_line < 1:
        raise ReferenceError("start_line must be positive")
    record, path = resolve(catalog, alias, relative_path)
    digest, lines, total, clipped = hashlib.sha256(), [], 0, False
    try:
        for number, raw, text in text_lines(path):
            digest.update(raw)
            total = number
            if start_line <= number < start_line + max_lines:
                text = text.rstrip("\r\n")
                clipped |= len(text) > 2000
                lines.append({"line": number, "text": text[:2000]})
    except (OSError, UnicodeError, ReferenceError) as exc:
        raise ReferenceError(f"Cannot read {alias}/{relative_path}: {exc}") from exc
    return {**identity(record, alias, relative_path), "sha256": digest.hexdigest(),
            "lines": lines, "start_line": lines[0]["line"] if lines else None,
            "end_line": lines[-1]["line"] if lines else None, "total_lines": total,
            "truncated": clipped or total >= start_line + max_lines,
            "next_line": start_line + max_lines if total >= start_line + max_lines else None,
            "text_clipped": clipped}


def search(catalog, query, alias=None, max_results=100):
    bound(max_results, 1000, "max_results")
    if not query or len(query) > 1000 or "\n" in query or "\r" in query:
        raise ReferenceError("Query must be a nonempty literal single line of at most 1000 characters")
    if alias is not None and alias not in catalog:
        raise ReferenceError(f"Reference alias is not authorized: {alias}")
    matches, errors, error_count = [], [], 0
    def error(message):
        nonlocal error_count
        error_count += 1
        if len(errors) < 100:
            errors.append(message)
    for name in ([alias] if alias is not None else sorted(catalog)):
        record = catalog[name]
        if not record["available"]:
            error(f"{name}: {record['reason']}")
            continue
        try:
            root = Path(record["path"])
            entries = reference_entries(root)
            for entry in entries:
                paths = (entry,) if entry.is_file() else files(entry, error)
                for path in paths:
                    relative = path.relative_to(root).as_posix()
                    try:
                        for number, _, text in text_lines(path):
                            position = text.find(query)  # Literal, case-sensitive matching.
                            if position >= 0:
                                start = max(0, position - 100)
                                matches.append({**identity(record, name, relative), "line": number,
                                                "excerpt": text[start:start + 500].rstrip("\r\n"),
                                                "excerpt_clipped": start > 0 or len(text) > start + 500})
                                if len(matches) == max_results:
                                    return {"matches": matches, "errors": errors, "error_count": error_count,
                                            "errors_truncated": error_count > len(errors),
                                            "truncated": True, "incomplete": True}
                    except (OSError, UnicodeError, ReferenceError) as exc:
                        error(f"{name}/{relative}: {exc}")
        except (OSError, ReferenceError) as exc:
            error(f"{name}: {exc}")
    return {"matches": matches, "errors": errors, "error_count": error_count,
            "errors_truncated": error_count > len(errors),
            "truncated": False, "incomplete": bool(error_count)}


def files(root, error):
    for base, dirs, names in os.walk(root, followlinks=False, onerror=lambda exc: error(str(exc))):
        dirs.sort()
        for name in sorted(names):
            yield Path(base) / name


def add_read_commands(sub, host=False):
    for action in ("list", "browse", "search", "read"):
        parser = sub.add_parser(action)
        if host:
            parser.add_argument("project", type=Path)
        if action in ("browse", "read"):
            parser.add_argument("alias")
            parser.add_argument("relative", nargs="?" if action == "browse" else None, default=".")
        if action == "browse":
            parser.add_argument("--max-entries", type=int, default=100)
            parser.add_argument("--offset", type=int, default=0)
        if action == "search":
            parser.add_argument("query")
            parser.add_argument("--source", dest="alias")
            parser.add_argument("--max-results", type=int, default=100)
        if action == "read":
            parser.add_argument("--start-line", type=int, default=1)
            parser.add_argument("--max-lines", type=int, default=100)


def dispatch(catalog, args):
    if args.action == "list":
        return {"references": catalog}
    if args.action == "browse":
        return browse(catalog, args.alias, args.relative, args.max_entries, args.offset)
    if args.action == "search":
        return search(catalog, args.query, args.alias, args.max_results)
    return read_artifact(catalog, args.alias, args.relative, args.start_line, args.max_lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only scientific evidence, never operational authority.")
    sub = parser.add_subparsers(dest="action", required=True)
    add_read_commands(sub)
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(Path("/run/research-references.json").read_text(encoding="utf-8"))
        print(json.dumps(dispatch(catalog, args), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
