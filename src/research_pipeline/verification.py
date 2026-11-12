"""Freeze explicitly supplied stable scientific evidence for an independent check."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import quote, unquote, urlsplit

from . import workspace


PACKET_FIELDS = ("Claim and scope", "Parent question", "Scientific benefit",
                 "Assumptions and approximation regime", "Sources and artifacts",
                 "Reproduction instructions")
CHECK_FIELDS = ("Claim and scope", "Independent approach", "Observations",
                "Objections and limitations", "Reproduction or analytical evidence")
RESPONSE_FIELDS = ("Response to objections", "Revised claim", "Sources and artifacts",
                   "Reproduction instructions")
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)\)")
PHASES = ("initial", "awaiting_response", "reexamination", "closed")
ASSIGNMENT_FIELDS = ("Objective", "Parent question", "Scientific benefit",
                     "Assumptions", "Requested result", "Artifacts")


def sections(text, fields):
    result = {}
    for field in fields:
        match = re.search(r"^## " + re.escape(field) + r"\s*\n(.+?)(?=\n## |\Z)", text, re.S | re.M)
        if not match or not match[1].strip():
            raise workspace.InputError(f"Missing substantive ## {field}")
        result[field] = match[1].strip()
    return result


def scientific_path(project, rel):
    path = workspace.safe_path(project, rel)
    parts = Path(rel).parts
    if (not parts or Path(rel).name == "FOLDER_CONTENT.md"
            or not (parts[0] in (*workspace.MANAGED, "starting_evidence")
                    or rel in ("AGENTS.md", "HUMAN_FEEDBACK.md", "RESEARCH_STATUS.md"))):
        raise workspace.InputError("Verification input must be scientific, not operational")
    return path


def link_path(project, rel, target):
    url = urlsplit(target)
    if url.scheme or url.netloc or not url.path:
        return None
    link = unquote(url.path)
    if link.startswith("/project/"):
        candidate = Path(link.removeprefix("/project/"))
    elif Path(link).is_absolute():
        raise workspace.InputError("Outside-project verification artifact")
    else:
        candidate = Path(rel).parent / link
    # Relative ../ links are normal Markdown. Validate every lexical component
    # before normalization so a symlink/../ pair cannot conceal traversal.
    cursor = project
    for part in candidate.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise workspace.InputError("Symlinked verification artifact")
    absolute = Path(os.path.abspath(project / candidate))
    if not absolute.is_relative_to(project):
        raise workspace.InputError("Outside-project verification artifact")
    result = absolute.relative_to(project).as_posix()
    scientific_path(project, result)
    return result


def read_bytes(path, deadline):
    """Bounded nonblocking regular-file read, with before/after identity checks."""
    workspace.check_deadline(deadline)
    with workspace.open_regular(path) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > 16 * 1024 * 1024:
            raise workspace.InputError("Verification input must be a regular file at most 16 MiB")
        chunks, size = [], 0
        while True:
            workspace.check_deadline(deadline)
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > 16 * 1024 * 1024:
                raise workspace.InputError("Verification input grew beyond 16 MiB")
            chunks.append(chunk)
        after = os.fstat(stream.fileno())
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or path.lstat() != after):
        raise workspace.InputError("Verification evidence changed during copying")
    return b"".join(chunks)


def prepare_assignment(project, rel, drafts, destination):
    """Keep canonical links anchored; retain recursively linked private drafts."""
    copies = {}

    def rewrite(candidate, text):
        for target in LINK.findall(text):
            dependency = link_path(project, candidate, target)
            if dependency is None:
                continue
            proposed = workspace.safe_path(drafts, dependency)
            if proposed.exists():
                if not workspace.allowed_science(dependency) or proposed.suffix != ".md":
                    raise workspace.InputError("Assignment draft dependencies must be scoped Markdown")
                mapped = f"{destination}/files/{dependency}"
                if dependency not in copies:
                    if len(copies) >= 128:
                        raise workspace.InputError("Too many assignment draft dependencies")
                    blob = read_bytes(proposed, None)
                    copies[dependency] = b""  # break cycles before recursive rewriting
                    copies[dependency] = rewrite(dependency, blob.decode("utf-8")).encode()
                    if sum(map(len, copies.values())) > 64 * 1024 * 1024:
                        raise workspace.InputError("Assignment drafts exceed 64 MiB")
            else:
                with workspace.open_regular(scientific_path(project, dependency)):
                    pass
                mapped = dependency
            url = urlsplit(target)
            suffix = ("?" + url.query if url.query else "") + ("#" + url.fragment if url.fragment else "")
            text = text.replace(f"]({target})", f"](/project/{quote(mapped)}{suffix})")
        return text

    proposed = workspace.safe_path(drafts, rel)
    source = proposed if proposed.exists() else scientific_path(project, rel)
    text = read_bytes(source, None).decode("utf-8")
    content = sections(text, ASSIGNMENT_FIELDS)
    rewritten = rewrite(rel, text)
    # Finish all reads/validation before installing any delegated artifacts.
    workspace.safe_path(project, destination).mkdir(parents=True, exist_ok=True)
    for candidate, blob in copies.items():
        target = workspace.safe_path(project, f"{destination}/files/{candidate}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    return rewritten, content


def freeze(project, rel, drafts, destination, fields, deadline):
    """Copy only explicitly supplied evidence, rebasing notes into a frozen packet."""
    canonical = scientific_path(project, rel)
    if canonical.suffix != ".md":
        raise workspace.InputError("Verification submission must be Markdown")

    def source(candidate):
        original = scientific_path(project, candidate)
        if workspace.allowed_science(candidate, "primary") and Path(candidate).suffix == ".md":
            proposed = workspace.safe_path(drafts, candidate)
            if proposed.exists():
                return proposed
        return original

    data = read_bytes(source(rel), deadline)
    text = data.decode("utf-8")
    content = sections(text, fields)
    supplied = [rel]
    for target in LINK.findall(text):
        candidate = link_path(project, rel, target)
        if candidate is not None and candidate not in supplied:
            supplied.append(candidate)
    if len(supplied) < 2:
        raise workspace.InputError("Verification packet must link reproducible local evidence")
    if len(supplied) > 128:
        raise workspace.InputError("Too many explicitly supplied verification artifacts")
    blobs = {rel: data}
    for candidate in supplied[1:]:
        blobs[candidate] = read_bytes(source(candidate), deadline)
        if sum(map(len, blobs.values())) > 64 * 1024 * 1024:
            raise workspace.InputError("Verification evidence exceeds 64 MiB")
    mapped = {candidate: f"{destination}/files/{candidate}" for candidate in supplied}
    manifest = []
    rewritten = {}
    for candidate, blob in blobs.items():
        original_hash = hashlib.sha256(blob).hexdigest()
        if Path(candidate).suffix == ".md":
            note = blob.decode("utf-8")
            for target in LINK.findall(note):
                dependency = link_path(project, candidate, target)
                if dependency is not None:
                    if dependency not in mapped:
                        raise workspace.InputError(
                            "Include local Markdown dependencies explicitly in the verification submission")
                    note = note.replace(f"]({target})", f"](/project/{mapped[dependency]})")
            blob = note.encode()
        rewritten[mapped[candidate]] = blob
        manifest.append({"source": candidate, "source_sha256": original_hash,
                         "path": mapped[candidate], "sha256": hashlib.sha256(blob).hexdigest()})
    # Recheck every source before writing anything; admission never executes evidence.
    for entry in manifest:
        if hashlib.sha256(read_bytes(source(entry["source"]), deadline)).hexdigest() != entry["source_sha256"]:
            raise workspace.InputError("Verification evidence changed during copying")
    version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    manifest_path = f"{destination}/manifest.json"
    root = workspace.safe_path(project, destination)
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists():
        # A controller can die after installing a packet but before persisting
        # acceptance. Reuse only an identical complete copy; never overwrite it.
        if json.loads(read_bytes(root / "manifest.json", deadline)) != manifest:
            raise workspace.InputError("Uncommitted packet differs; inspect retained evidence while stopped before retrying")
        for path, blob in rewritten.items():
            if read_bytes(workspace.safe_path(project, path), deadline) != blob:
                raise workspace.InputError("Uncommitted verification evidence changed; inspect before recovery")
    else:
        with tempfile.TemporaryDirectory(prefix=".packet-", dir=root.parent) as temp:
            staging = Path(temp) / "packet"
            staging.mkdir()
            for path, blob in rewritten.items():
                workspace.check_deadline(deadline)
                target = staging / Path(path).relative_to(destination)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob)
            workspace.atomic_text(staging / "manifest.json", json.dumps(manifest, indent=2) + "\n")
            workspace.check_deadline(deadline)
            os.replace(staging, root)
    return {"packet": mapped[rel], "manifest": manifest_path, "evidence": manifest,
            "version": version}, content

