"""Ordinary project files; human inputs are never written by the controller."""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid
from urllib.parse import unquote, urlsplit


class InputError(ValueError):
    pass


class ProjectBusy(InputError):
    pass


@dataclass
class Intake:
    project: Path
    questions: str
    instructions: str
    inventory: list[dict]
    fingerprints: dict[str, str]
    feedback: str = ""


MANAGED = ("sources", "work", "outputs", "handoffs")
REQUIRED = ("work/PLAN.md", "sources/LITERATURE.md", "outputs/REPORT.md")
ACTIVE_STATES = ("starting", "running", "pausing", "rolling_over")


def task_directory(task_id="primary"):
    if task_id == "primary":
        return "work"
    if not re.fullmatch(r"task-[a-f0-9]{32}", task_id):
        raise InputError("Invalid logical task identity")
    return f"work/tasks/{task_id}"


def writable_directories(task_id="primary"):
    return ("sources", "work", "outputs") if task_id == "primary" else (task_directory(task_id),)


def allowed_science(rel, task_id="primary", protected=()):
    path = Path(rel)
    if rel in protected:
        return False
    if task_id == "primary":
        return (rel == "RESEARCH_STATUS.md" or rel == "handoffs/primary.md"
                or path.parts[0] in ("sources", "outputs")
                or path.parts[0] == "work" and not path.is_relative_to("work/tasks"))
    return (path.is_relative_to(task_directory(task_id))
            and not path.is_relative_to(f"{task_directory(task_id)}/inputs")
            and rel != f"{task_directory(task_id)}/ASSIGNMENT.md"
            or rel == f"handoffs/{task_id}.md")


def handoff_path(task_id="primary"):
    task_directory(task_id)
    return f"handoffs/{task_id}.md"


@contextmanager
def control_lock(project):
    """Never wait for run.lock while holding this short-lived lock."""
    path = safe_path(project, ".research_pipeline/control.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def owner_fields(state):
    keys = ("run_id", "ownership_nonce") if state.get("schema_version") == 3 else ("run_id", "activation_id", "ownership_nonce")
    result = {k: state[k] for k in keys}
    if any(not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{32}", v)
           for v in result.values()):
        raise InputError("Invalid investigation ownership identifiers")
    return result


def control_paths(project, state):
    owner_fields(state)
    if state.get("schema_version") == 3:
        session = safe_path(project, f".research_pipeline/owners/{state['ownership_nonce']}")
    else:
        session = safe_path(project, f".research_pipeline/sessions/{state['activation_id']}")
    return session, safe_path(project, session.relative_to(project) / "control"), \
        safe_path(project, session.relative_to(project) / "response")


def read_control(path):
    """Untrusted responses must never hang on FIFOs or follow symbolic links."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return None
            raw = stream.read(8193)
        if len(raw) > 8192:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def matching_request(value, state):
    return (isinstance(value, dict) and value.get("version") == 1
            and value.get("reason") in ("pause", "rollover")
            and all(value.get(k) == v for k, v in owner_fields(state).items())
            and isinstance(value.get("request_id"), str)
            and re.fullmatch(r"[a-f0-9]{32}", value["request_id"]) is not None)


def regular_tree(root):
    """Reject links and special files, including links in ancestor directories."""
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise InputError(f"Symlinked path is unsupported: {root}")
    for p in (root, *root.rglob("*")):
        mode = p.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise InputError(f"Symlink or special file is unsupported: {p}")


def fingerprints(project):
    paths = sorted((project / "starting_evidence").rglob("*"))
    for name in ("AGENTS.md", "HUMAN_FEEDBACK.md"):
        if (project / name).exists() or (project / name).is_symlink():
            paths.append(project / name)
    result = {}
    for p in paths:
        if p.is_symlink():
            raise InputError(f"Protected input became a symlink: {p}")
        if p.is_file():
            digest = hashlib.sha256()
            with p.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[str(p.relative_to(project))] = digest.hexdigest()
    return result


def read_intake(project):
    project = Path(os.path.abspath(project))
    if not project.is_dir():
        raise InputError(f"Project directory does not exist: {project}")
    if any(p.is_symlink() for p in (project, *project.parents)):
        raise InputError("Symlinked project ancestors are unsupported")
    regular_tree(project / "starting_evidence")
    for name in (*MANAGED, "RESEARCH_STATUS.md", "FOLDER_CONTENT.md",
                 "AGENTS.md", "HUMAN_FEEDBACK.md", ".research_pipeline"):
        p = project / name
        if p.is_symlink():
            raise InputError(f"Protected or managed path is a symlink: {p}")
        if name in MANAGED and p.exists() and not p.is_dir():
            raise InputError(f"Managed path must be a directory: {p}")
    # Validate controller paths individually. Historical draft trees contain
    # untrusted agent output and are checked only when publishing that batch.
    for rel, directory in ((".research_pipeline", True), (".research_pipeline/sessions", True),
                           (".research_pipeline/run.json", False), (".research_pipeline/run.lock", False)):
        p = safe_path(project, rel)
        if p.exists() and not (p.is_dir() if directory else p.is_file()):
            raise InputError(f"Invalid operational path: {p}")
    # Tool configuration is not scientific input. Do not load project hooks/skills.
    for name in (".codex", ".agents", ".git"):
        if (project / name).exists() or (project / name).is_symlink():
            raise InputError(f"Use a plain research directory without {name}")
    q = project / "starting_evidence/RESEARCH_QUESTIONS.md"
    if not q.is_file():
        raise InputError(f"Required questions file is missing: {q}")

    questions = read_input(q)
    if not questions.strip():
        raise InputError("RESEARCH_QUESTIONS.md must not be empty")
    instructions = read_input(project / "AGENTS.md") if (project / "AGENTS.md").exists() else ""
    feedback = read_input(project / "HUMAN_FEEDBACK.md") if (project / "HUMAN_FEEDBACK.md").exists() else ""
    inventory = []
    for p in sorted((project / "starting_evidence").rglob("*")):
        if p.is_file():
            if not p.stat().st_mode & 0o444:
                raise InputError(f"Unreadable starting evidence: {p}")
            inventory.append({"path": str(p.relative_to(project)), "bytes": p.stat().st_size})
    if len(inventory) > 10000:
        raise InputError("More than 10000 evidence files; narrow the starting material")
    return Intake(project, questions, instructions, inventory, fingerprints(project), feedback)


def read_input(p):
    if p.is_symlink() or not p.is_file() or not p.stat().st_mode & 0o444:
        raise InputError(f"Cannot read supplied input: {p}")
    if p.stat().st_size > 256 * 1024:
        raise InputError(f"Input exceeds 256 KiB prompt limit: {p}")
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError(f"Cannot read {p}: {exc}") from exc


def validate_fresh(project):
    regular_tree(project)
    for name in (*MANAGED, "RESEARCH_STATUS.md", "FOLDER_CONTENT.md", ".research_pipeline/run.json"):
        if (project / name).exists():
            raise InputError(f"Fresh project required; managed path already exists: {name}")


@contextmanager
def acquire_project_lock(project):
    ops = project / ".research_pipeline"
    if ops.is_symlink() or (ops.exists() and not ops.is_dir()):
        raise InputError("Invalid .research_pipeline directory")
    ops.mkdir(mode=0o700, exist_ok=True)
    lock = ops / "run.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProjectBusy("Another controller holds the project lock") from exc
        yield


def atomic_text(path, text):
    if path.is_symlink():
        raise InputError(f"Refusing to replace symlink: {path}")
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_state(project, state):
    if hasattr(state, "persist"):
        state.persist()
        return
    state["artifact_availability"] = {
        p: (project / p).is_file() and not (project / p).is_symlink() for p in REQUIRED
    }
    atomic_text(project / ".research_pipeline/run.json", json.dumps(state, indent=2) + "\n")


def initial_status(project):
    """Create science status once. Operational updates live exclusively in JSON."""
    if (project / "RESEARCH_STATUS.md").exists():
        return
    links = "\n".join(f"- `{p}` — not produced." for p in REQUIRED)
    atomic_text(project / "RESEARCH_STATUS.md", "# Research status\n\n"
                "Investigation initialized; findings remain preliminary.\n\n" + links + "\n\n"
                "See `.research_pipeline/run.json` for limits and operational diagnostics.\n")


DESCRIPTIONS = {
    "starting_evidence": "Human-owned scientific inputs (read-only; questions and supplied evidence).",
    "AGENTS.md": "Human-owned project instructions (read-only).",
    "sources": "Retrieved scientific sources and literature assessment.",
    "work": "Scientific plan, derivations, executable scripts and computation data.",
    "outputs": "Research findings and supporting figures.",
    "handoffs": "Continuation guidance, preserved human edits and proposed reconciliations.",
    "HUMAN_FEEDBACK.md": "Distinct human scientific feedback (read-only to agents).",
    ".research_pipeline": "Private controller status and bounded backend diagnostics.",
    "RESEARCH_STATUS.md": "Operational state and links to current scientific progress.",
    "PLAN.md": "Revisable scientific questions, assumptions and methods.",
    "LITERATURE.md": "Citations, relevance and source access quality.",
    "REPORT.md": "Preliminary findings, evidence, limitations and reproduction instructions.",
    "run.json": "Machine-readable run state, limits and observed outcomes.",
    "backend.jsonl": "Bounded private Codex event stream.",
    "stderr.txt": "Bounded private launcher/backend diagnostics.",
    "run.lock": "Exclusive foreground investigation lock.",
    "control.lock": "Short-lived lock for owner registration and suspension requests.",
}


def refresh_indexes(project, include_science=True, expected=None, task_id=None):
    edited_indexes = {}
    if expected is not None and include_science:
        for rel, digest in science_fingerprints(project, task_id).items():
            if (Path(rel).name == "FOLDER_CONTENT.md"
                    and digest != expected.get(rel)):
                edited_indexes[rel] = preserve_edit(project, project / rel)
    # Walk only managed directories; never follow links made by scientific scripts.
    roots = [project, project / ".research_pipeline"] if task_id in (None, "primary") else []
    managed = MANAGED if task_id is None else (*writable_directories(task_id), *( ("handoffs",) if task_id == "primary" else ()))
    for name in managed if include_science else ():
        if (project / name).is_dir() and not (project / name).is_symlink():
            for base, dirs, _ in os.walk(project / name, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()
                           and not (task_id == "primary" and Path(base) / d == project / "work/tasks")]
                roots.append(Path(base))
    for directory in roots:
        rows = ["# Folder contents", ""]
        for p in sorted(directory.iterdir()):
            if p.name == "FOLDER_CONTENT.md":
                continue
            if p.is_symlink():
                description = "Symbolic link (not followed by the controller)."
            else:
                description = DESCRIPTIONS.get(p.name)
                if not description:
                    if p.is_dir():
                        description = f"Supporting artifacts in {p.name}."
                    elif not p.is_file():
                        description = "Special artifact (not opened by the controller)."
                    elif p.suffix == ".md":
                        try:
                            with p.open(encoding="utf-8") as f:
                                excerpt = f.read(1024)
                                description = next((s.strip().lstrip('#').strip()
                                                    for s in excerpt.splitlines() if s.strip()),
                                                   "Scientific notes.")[:160]
                        except (OSError, UnicodeError):
                            description = "Scientific Markdown artifact."
                    else:
                        description = f"{p.suffix.lstrip('.') or 'Native'} artifact ({p.stat().st_size} bytes)."
            from urllib.parse import quote
            label = p.name.replace("[", "\\[").replace("]", "\\]")
            rows.append(f"- [{label}]({quote(p.name)}) — {description}")
        if directory == project:
            rows.extend(["", "Starting evidence files (read-only):", ""])
            for p in sorted((project / "starting_evidence").rglob("*")):
                if p.is_file() and not p.is_symlink():
                    rel = p.relative_to(project).as_posix()
                    rows.append(f"- [{p.name}]({quote(rel)}) — Supplied scientific input.")
        index = directory / "FOLDER_CONTENT.md"
        rel = index.relative_to(project).as_posix()
        # Preserve human additions before regenerating navigation. Operational
        # indexes are private controller files, not human scientific notes.
        if rel in edited_indexes:
            saved = edited_indexes[rel]
            rows += ["", f"- [Preserved edited index]({os.path.relpath(saved, directory)})"]
        atomic_text(index, "\n".join(rows) + "\n")


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Checkpoint preparation saving deadline reached")


def file_digest(path, deadline=None):
    check_deadline(deadline)
    if path.is_symlink():
        return "symlink"
    if not path.exists():
        return None
    if not path.is_file():
        return "special"
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            check_deadline(deadline)
            chunk = stream.read(64 * 1024)
            check_deadline(deadline)
            if not chunk:
                break
            digest.update(chunk)
    check_deadline(deadline)
    return digest.hexdigest()


def science_fingerprints(project, task_id=None):
    """Never follow scientific symlinks or open special artifacts."""
    paths = ([project / "RESEARCH_STATUS.md", project / "FOLDER_CONTENT.md"]
             if task_id in (None, "primary") else [])
    if task_id is not None:
        paths.append(project / handoff_path(task_id))
    for name in MANAGED if task_id is None else writable_directories(task_id):
        root = project / name
        if root.is_symlink():
            raise InputError(f"Managed directory is a symlink: {name}")
        if root.is_dir():
            for base, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()
                           and not (task_id == "primary" and Path(base) / d == project / "work/tasks")]
                paths.extend(Path(base) / f for f in files if f.lower().endswith(".md"))
    return {p.relative_to(project).as_posix(): file_digest(p)
            for p in paths if p.exists() or p.is_symlink()}


def changed_files(previous, current):
    return sorted(p for p in previous.keys() | current.keys() if previous.get(p) != current.get(p))


def safe_path(project, rel):
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise InputError(f"Unsafe project-relative path: {rel}")
    target = project / p
    if any(parent.is_symlink() for parent in (target, *target.parents)):
        raise InputError(f"Symlinked artifact path: {rel}")
    if not target.resolve().is_relative_to(project):
        raise InputError(f"Outside-project path: {rel}")
    return target


def preserve_edit(project, path):
    text = read_input_unbounded(path)
    directory = safe_path(project, "handoffs/preserved")
    directory.mkdir(parents=True, exist_ok=True)
    saved = directory / f"{path.stem}-{uuid.uuid4().hex}.md"
    atomic_text(saved, f"<!-- Preserved human version: {path.relative_to(project)} -->\n\n{text}")
    return saved


def read_input_unbounded(path, deadline=None):
    check_deadline(deadline)
    if path.is_symlink() or not path.is_file():
        raise InputError(f"Expected regular Markdown file: {path}")
    try:
        chunks = []
        with path.open(encoding="utf-8") as stream:
            while True:
                check_deadline(deadline)
                chunk = stream.read(64 * 1024)
                check_deadline(deadline)
                if not chunk:
                    break
                chunks.append(chunk)
        text = "".join(chunks)
        check_deadline(deadline)
        return text
    except TimeoutError:
        raise
    except (OSError, UnicodeError) as exc:
        raise InputError(f"Cannot read Markdown {path}: {exc}") from exc


def draft_proposals(project, drafts, task_id="primary", protected=()):
    """Validate the complete role-scoped batch before making any replacements."""
    regular_tree(drafts)
    proposals = []
    for draft in sorted(drafts.rglob("*")):
        if not draft.is_file():
            continue
        rel = draft.relative_to(drafts)
        if (draft.suffix != ".md" or draft.name == "FOLDER_CONTENT.md"
                or not allowed_science(rel.as_posix(), task_id, protected)):
            raise InputError(f"Invalid scientific draft destination: {rel}")
        target = safe_path(project, rel)
        if target.exists() and not target.is_file():
            raise InputError(f"Draft destination is not a file: {rel}")
        proposals.append((rel.as_posix(), target, read_input_unbounded(draft)))
    return proposals


def publish_drafts(project, drafts, baseline, external_changes, task_id="primary", protected=()):
    proposals = draft_proposals(project, drafts, task_id, protected)
    conflicts, preserved = [], []
    for rel, target, text in proposals:
        if file_digest(target) != baseline.get(rel):
            proposed = safe_path(project, f"handoffs/proposed/{uuid.uuid4().hex}-{target.name}")
            proposed.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(proposed, f"<!-- Proposed replacement for {rel}; human state preserved. -->\n\n{text}")
            conflicts.append({"path": rel, "proposal": proposed.relative_to(project).as_posix()})
            continue
        if rel in external_changes and target.exists():
            preserved.append(preserve_edit(project, target).relative_to(project).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(target, text)
    return conflicts, preserved


def intake_snapshot(intake):
    return ("# Accepted intake\n\n## Questions\n\n" + intake.questions
            + "\n\n## Project instructions\n\n" + (intake.instructions or "(absent)")
            + "\n\n## Human feedback\n\n" + (intake.feedback or "(absent)") + "\n")


def handoff_fields(task_id="primary"):
    fields = (f"Logical researcher: {task_id}", "## Objective", "## Completed",
              "## Artifacts", "## Assumptions", "## Unresolved", "## Next action")
    if task_id != "primary":
        fields += ("## Parent question", "## Interrupted computation", "## Resume or reconsider")
    return fields


def validate_handoff(project, text, drafts=None, deadline=None, task_id="primary"):
    for field in handoff_fields(task_id):
        check_deadline(deadline)
        if field not in text:
            raise InputError(f"Handoff missing required field: {field}")
        if field.startswith("## "):
            body = text.split(field, 1)[1].split("\n## ", 1)[0].strip()
            if not body:
                raise InputError(f"Handoff field has no content: {field}")
    artifacts = []
    for match in re.finditer(r"\[[^\]]*\]\(([^\s)]+)\)", text):
        check_deadline(deadline)
        target = match.group(1)
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        link = unquote(url.path)
        if link.startswith("/project/"):
            p = safe_path(project, link[len("/project/"):])
        else:
            # Ordinary Markdown links resolve relative to the canonical handoff.
            candidate = Path(os.path.abspath(project / "handoffs" / link))
            if not candidate.is_relative_to(project):
                raise InputError(f"Outside-project handoff link: {link}")
            p = safe_path(project, candidate.relative_to(project))
        rel = p.relative_to(project).as_posix()
        if rel != "RESEARCH_STATUS.md" and (not Path(rel).parts or Path(rel).parts[0] not in MANAGED):
            raise InputError(f"Handoff must reference scientific artifacts: {rel}")
        if drafts is not None and p.suffix == ".md":
            proposed = safe_path(drafts, rel)
            if proposed.exists():
                p = proposed
        if not p.is_file():
            raise InputError(f"Missing handoff artifact: {rel}")
        artifacts.append(rel)
    if not artifacts:
        raise InputError("Handoff must link at least one saved scientific artifact")
    check_deadline(deadline)
    return sorted(set(artifacts))


def commit_checkpoint(project, state, intake, session, accepted_intake=None, task_id="primary"):
    text = read_input_unbounded(project / handoff_path(task_id))
    artifacts = validate_handoff(project, text, task_id=task_id)
    atomic_text(session / "handoff.md", text)
    atomic_text(session / "intake.md", accepted_intake or intake_snapshot(intake))
    checkpoint = {
        "id": state["activation_id"],
        "handoff": (session / "handoff.md").relative_to(project).as_posix(),
        "handoff_sha256": file_digest(session / "handoff.md"),
        "intake": (session / "intake.md").relative_to(project).as_posix(),
        "artifacts": artifacts, "input_fingerprints": intake.fingerprints,
        "science_fingerprints": science_fingerprints(project, task_id),
    }
    # Publish the new reference only after all its files are validated. Keep one
    # previous immutable handoff for a damaged newest checkpoint.
    state["checkpoints"] = ([c for c in state.get("checkpoints", [])
                             if c["id"] != checkpoint["id"]] + [checkpoint])[-2:]
    state["checkpoint"] = checkpoint
    write_state(project, state)
    return checkpoint


def prepare_checkpoint(project, state, intake, session, drafts, baseline, external, deadline=None, task_id="primary"):
    """Confirm saved work before acknowledging; canonical files stay pinned."""
    check_deadline(deadline)
    draft_proposals(project, drafts, task_id, protected_reports(state))
    check_deadline(deadline)
    text = read_input_unbounded(safe_path(drafts, handoff_path(task_id)), deadline)
    artifacts = validate_handoff(project, text, drafts=drafts, deadline=deadline, task_id=task_id)
    references = {str((drafts / handoff_path(task_id)).relative_to(project)):
                  file_digest(drafts / handoff_path(task_id), deadline)}
    for rel in artifacts:
        check_deadline(deadline)
        candidate = safe_path(drafts, rel) if Path(rel).suffix == ".md" else project / rel
        if not candidate.exists():
            candidate = safe_path(project, rel)
        references[str(candidate.relative_to(project))] = file_digest(candidate, deadline)
    check_deadline(deadline)
    atomic_text(session / "prepared-handoff.md", text)
    check_deadline(deadline)
    atomic_text(session / "prepared-intake.md", intake_snapshot(intake))
    check_deadline(deadline)
    metadata = {
        "owner": owner_fields(state), "baseline": baseline, "external_changes": external,
        "input_fingerprints": intake.fingerprints, "references": references,
        "handoff_sha256": file_digest(session / "prepared-handoff.md", deadline),
        "intake_sha256": file_digest(session / "prepared-intake.md", deadline),
    }
    serialized = json.dumps(metadata, indent=2) + "\n"
    check_deadline(deadline)
    atomic_text(session / "prepared.json", serialized)
    check_deadline(deadline)
    state["checkpoint_prepared"] = str((session / "prepared.json").relative_to(project))
    write_state(project, state)
    check_deadline(deadline)


def load_prepared(project, state):
    metadata_path = safe_path(project, state["checkpoint_prepared"])
    metadata = json.loads(read_input_unbounded(metadata_path))
    if not isinstance(metadata, dict) or not isinstance(metadata.get("references"), dict):
        raise InputError("Invalid prepared checkpoint metadata")
    if metadata["owner"] != owner_fields(state):
        raise InputError("Prepared checkpoint ownership mismatch")
    session = metadata_path.parent
    for name, key in (("prepared-handoff.md", "handoff_sha256"),
                      ("prepared-intake.md", "intake_sha256")):
        if file_digest(safe_path(project, (session / name).relative_to(project))) != metadata[key]:
            raise InputError("Prepared checkpoint changed after validation")
    for rel, digest in metadata["references"].items():
        if file_digest(safe_path(project, rel)) != digest:
            raise InputError(f"Prepared artifact changed after validation: {rel}")
    intake = Intake(project, "", "", [], metadata["input_fingerprints"])
    return metadata, session, intake, read_input_unbounded(session / "prepared-intake.md")


def finalize_science(project, state, intake, session, drafts, baseline, external,
                     expected=None, accepted_intake=None, task_id="primary"):
    """Only called after confirmed cleanup, for normal, paused or recovered work."""
    external = sorted(set(external) | set(changed_files(baseline, science_fingerprints(project, task_id))))
    state["external_changes"] = external
    conflicts, preserved = publish_drafts(project, drafts, baseline, external, task_id, protected_reports(state))
    state["pending_reconciliation"] = conflicts
    state["preserved_edits"] = preserved
    published = {p.relative_to(drafts).as_posix() for p in drafts.rglob("*.md")}
    published -= {c["path"] for c in conflicts}
    state["pending_human_changes"] = sorted(
        (set(external) | {c["path"] for c in conflicts}) - published)
    refresh_indexes(project, expected=expected if expected is not None else baseline, task_id=task_id)
    try:
        if any(c["path"] == handoff_path(task_id) for c in conflicts):
            raise InputError("Handoff draft conflicts with a human edit")
        if not (drafts / handoff_path(task_id)).is_file():
            raise InputError("No new handoff draft; previous checkpoint retained")
        commit_checkpoint(project, state, intake, session, accepted_intake, task_id)
        state.pop("checkpoint_error", None)
    except (OSError, InputError) as exc:
        state["checkpoint_error"] = str(exc)
    state["science_fingerprints"] = science_fingerprints(project, task_id)
    return conflicts


def protected_reports(state):
    record = state.get("verification") or {}
    return tuple(record[key] for key in ("initial_check", "final_check", "closure") if record.get(key))


def load_checkpoint(project, state):
    for checkpoint in reversed(state.get("checkpoints", [])):
        try:
            handoff = safe_path(project, checkpoint["handoff"])
            if file_digest(handoff) != checkpoint["handoff_sha256"]:
                continue
            text = read_input_unbounded(handoff)
            # Referenced science can change; missing files are explicitly reported
            # to the researcher rather than silently discarding the handoff.
            safe_path(project, checkpoint["intake"])
            snapshot = read_input_unbounded(project / checkpoint["intake"])
            for rel in checkpoint["artifacts"]:
                safe_path(project, rel)
            return checkpoint, text, snapshot
        except (OSError, InputError, KeyError, TypeError):
            continue
    return None, "", ""


def validate_deliverables(project, labels=("preliminary",)):
    failures = []
    linked_computation = False
    for rel in REQUIRED:
        p = project / rel
        if p.is_symlink() or not p.is_file() or not p.stat().st_size:
            failures.append(f"Missing or empty regular artifact: {rel}")
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"Unreadable artifact {rel}: {exc}")
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            local = (p.parent / unquote(url.path)).resolve()
            if not local.is_relative_to(project) or not local.exists():
                failures.append(f"Broken or outside-project link in {rel}: {target}")
            elif (rel == "outputs/REPORT.md"
                  and local.is_relative_to(project / "work")
                  and local.is_file() and local.suffix.lower() != ".md"):
                linked_computation = True
    # These are structural gates, not a scientific quality or execution certificate.
    if not failures:
        report = (project / "outputs/REPORT.md").read_text()
        if not any(re.search(r"\b" + re.escape(label) + r"\b", report, re.I) for label in labels):
            failures.append("Report must use an explicit scientific status label: " + ", ".join(labels))
        if not linked_computation:
            failures.append("Report must link to a local computational artifact (code or data) in work/")
    return failures
