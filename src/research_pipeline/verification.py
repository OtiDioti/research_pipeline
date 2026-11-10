"""Version-scoped scientific packets and a single finite verification exchange."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import unquote, urlsplit

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
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
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


def validate_record(task):
    record = task.get("verification")
    if not isinstance(record, dict):
        raise workspace.InputError("Verifier missing verification record")
    if (record.get("phase") not in PHASES or record.get("exchange_limit") != 1
            or type(record.get("response_committed")) is not bool
            or record.get("disposition") not in ("preliminary", "checked", "disputed")
            or not isinstance(record.get("initial"), dict)):
        raise workspace.InputError("Invalid verifier phase or finite exchange allowance")
    if ((record["phase"] == "reexamination" or record.get("response"))
            and not record["response_committed"]):
        raise workspace.InputError("Re-examination requires the committed response")
    if record["phase"] == "reexamination" and not record.get("response"):
        raise workspace.InputError("Missing accepted verification response")
    if record["phase"] == "awaiting_response" and record["response_committed"]:
        raise workspace.InputError("Response allowance already consumed")
    if record["phase"] in ("awaiting_response", "reexamination", "closed") and not record.get("initial_check"):
        raise workspace.InputError("Verification exchange is missing its accepted initial check")
    for key in ("initial", "response"):
        packet = record.get(key)
        if packet:
            prefix = f"{task['workspace']}/inputs/{key}/"
            if (not isinstance(packet.get("evidence"), list) or not packet["evidence"]
                    or not re.fullmatch(r"[a-f0-9]{64}", packet.get("version", ""))):
                raise workspace.InputError("Invalid verification evidence manifest")
            for path in (packet.get("packet"), packet.get("manifest"),
                         *(e.get("path") for e in packet["evidence"])):
                if not isinstance(path, str) or not path.startswith(prefix) or ".." in Path(path).parts:
                    raise workspace.InputError("Invalid frozen verification path")
            if hashlib.sha256(json.dumps(packet["evidence"], sort_keys=True).encode()).hexdigest() != packet["version"]:
                raise workspace.InputError("Invalid verification evidence version")
            for entry in packet["evidence"]:
                if (not isinstance(entry.get("source"), str)
                        or any(not re.fullmatch(r"[a-f0-9]{64}", entry.get(k, ""))
                               for k in ("sha256", "source_sha256"))):
                    raise workspace.InputError("Invalid verification evidence digest")
    for key, name in (("initial_check", "CHECK.md"), ("final_check", "REEXAMINATION.md"),
                      ("closure", "CLOSURE.md")):
        if record.get(key) and record[key] != f"{task['workspace']}/{name}":
            raise workspace.InputError("Invalid verification report path")
        if record.get(key) and not re.fullmatch(r"[a-f0-9]{64}", record.get(key + "_sha256", "")):
            raise workspace.InputError("Invalid accepted verification report digest")
        if record.get(key) and key != "closure":
            artifacts = record.get(key + "_artifacts")
            if not isinstance(artifacts, dict) or not artifacts:
                raise workspace.InputError("Accepted verification report is missing its evidence fingerprints")
            for path, digest in artifacts.items():
                if (not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts
                        or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                    raise workspace.InputError("Invalid accepted verification artifact fingerprint")


def check_unchanged(project, task, deadline=None):
    """A changed accepted packet/report cannot silently inherit an endorsement."""
    validate_record(task)
    record = task["verification"]
    for key in ("initial", "response"):
        packet = record.get(key)
        if not packet:
            continue
        manifest = read_bytes(workspace.safe_path(project, packet["manifest"]), deadline)
        if json.loads(manifest) != packet["evidence"]:
            raise workspace.InputError("Frozen verification manifest changed; reassessment required")
        for entry in packet["evidence"]:
            blob = read_bytes(workspace.safe_path(project, entry["path"]), deadline)
            if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
                raise workspace.InputError("Frozen verification evidence changed; reassessment required")
    for key in ("initial_check", "final_check", "closure"):
        if record.get(key) and workspace.file_digest(workspace.safe_path(project, record[key]), deadline) != record[key + "_sha256"]:
            raise workspace.InputError("Accepted verification report changed; reassessment required")
        if record.get(key) and key != "closure":
            for rel, digest in record[key + "_artifacts"].items():
                if workspace.file_digest(scientific_path(project, rel), deadline) != digest:
                    raise workspace.InputError(
                        f"Accepted verification check artifact changed or missing: {rel}; reassessment required")


def deliver(project, task, deadline=None):
    record = task["verification"]
    check_unchanged(project, task, deadline)
    final = record["phase"] == "reexamination"
    if record["phase"] not in ("initial", "reexamination"):
        raise workspace.InputError("Verification phase is not executable")
    path = f"{task['workspace']}/{'REEXAMINATION.md' if final else 'CHECK.md'}"
    text = workspace.read_input(workspace.safe_path(project, path))
    sections(text, CHECK_FIELDS)
    local = {}
    for target in LINK.findall(text):
        candidate = link_path(project, path, target)
        if candidate is not None:
            artifact = workspace.safe_path(project, candidate)
            if not artifact.is_file():
                raise workspace.InputError(f"Missing verification check artifact: {candidate}")
            local[candidate] = workspace.file_digest(artifact, deadline)
            if not re.fullmatch(r"[a-f0-9]{64}", local[candidate] or ""):
                raise workspace.InputError(f"Missing or invalid verification check artifact: {candidate}")
    if not local:
        raise workspace.InputError("Verification check must link saved evidence or independent check artifacts")
    matches = re.findall(r"^Disposition: (checked|objection|inconclusive)\s*$", text, re.M)
    if len(matches) != 1:
        raise workspace.InputError("Check requires Disposition: checked, objection or inconclusive")
    outcome = matches[0]
    key = "final_check" if final else "initial_check"
    record[key], record[key + "_sha256"] = path, workspace.file_digest(project / path, deadline)
    record[key + "_artifacts"] = local
    record["reviewed_version"] = record["response" if final else "initial"]["version"]
    record["disposition"] = ("checked" if outcome == "checked" else
                             "disputed" if outcome == "objection" or final else "preliminary")
    record["phase"] = "awaiting_response" if outcome == "objection" and not final else "closed"
    task["delivery"] = {"result": path, "handoff": workspace.handoff_path(task["task_id"]),
                        "label": record["disposition"], "version": record["reviewed_version"]}
    return "awaiting_response" if record["phase"] == "awaiting_response" else "completed"
