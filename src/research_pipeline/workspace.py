"""Ordinary project files; human inputs are never written by the controller."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import errno
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
    references: dict = field(default_factory=dict)


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
    registry = safe_path(project, ".research_pipeline/references.json")
    if registry.exists():
        paths.append(registry)
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


def read_intake(project, deadline=None, on_poll=None):
    from . import references
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
    catalog = references.load_catalog(project, deadline, on_poll)
    return Intake(project, questions, instructions, inventory, fingerprints(project), feedback, catalog)


def read_input(p):
    if p.is_symlink() or not p.is_file() or not p.stat().st_mode & 0o444:
        raise InputError(f"Cannot read supplied input: {p}")
    if p.stat().st_size > 256 * 1024:
        raise InputError(f"Input exceeds 256 KiB prompt limit: {p}")
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError(f"Cannot read {p}: {exc}") from exc


def validate_fresh(project, preserve_existing=False):
    """Require a new runtime; adopting existing science needs explicit opt-in."""
    regular_tree(project)
    paths = (".research_pipeline/run.json", ".research_pipeline/session",
             ".research_pipeline/sessions", ".research_pipeline/owners",
             ".research_pipeline/checkpoints", ".research_pipeline/contexts", ".research_pipeline/jobs",
             ".research_pipeline/documents", "STOP", "STOP_ACK", "COMPLETE", "COMPLETE_ACK")
    if not preserve_existing:
        paths = (*MANAGED, "RESEARCH_STATUS.md", "FOLDER_CONTENT.md", *paths)
    for name in paths:
        if (project / name).exists():
            raise InputError(f"Fresh project required; managed path already exists: {name}")
    for name in ("RESEARCH_STATUS.md", "FOLDER_CONTENT.md"):
        path = project / name
        if path.exists() and not path.is_file():
            raise InputError(f"Scientific note must be a regular file: {name}")


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
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
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
    "STOP": "Runtime quota STOP explanation; latched until supported explicit resumption.",
    "STOP_ACK": "Matching quota STOP explanation after confirmed cleanup and finalization.",
    "PLAN.md": "Revisable scientific questions, assumptions and methods.",
    "LITERATURE.md": "Citations, relevance and source access quality.",
    "REUSE.md": "Prior source identities, verification qualifications and applicability to this investigation.",
    "references.json": "Explicit reference authorization paths (scientific evidence only).",
    "REPORT.md": "Preliminary findings, evidence, limitations and reproduction instructions.",
    "run.json": "Machine-readable run state, limits and observed outcomes.",
    "backend.jsonl": "Bounded private Codex event stream.",
    "stderr.txt": "Bounded private launcher/backend diagnostics.",
    "run.lock": "Exclusive foreground investigation lock.",
    "control.lock": "Short-lived lock for owner registration and suspension requests.",
}


def refresh_indexes(project, include_science=True, expected=None, task_id=None):
    edited_indexes = {}
    generated = {}
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
                           and not (task_id == "primary" and Path(base) / d == project / "work/tasks")
                           and not (task_id not in (None, "primary") and Path(base) / d == project / task_directory(task_id) / "inputs")]
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
        text = "\n".join(rows) + "\n"
        atomic_text(index, text)
        generated[rel] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return generated


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Checkpoint preparation saving deadline reached")


@contextmanager
def open_regular(path):
    """Pin each ancestor without following links; a replaced FIFO cannot block."""
    path = Path(path).absolute()
    if ".." in path.parts:
        raise InputError(f"Parent traversal in file path: {path}")
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise InputError(f"Expected regular file: {path}")
        yield stream


def file_digest(path, deadline=None):
    check_deadline(deadline)
    digest = hashlib.sha256()
    try:
        with open_regular(path) as stream:
            while True:
                check_deadline(deadline)
                chunk = stream.read(64 * 1024)
                check_deadline(deadline)
                if not chunk:
                    break
                digest.update(chunk)
    except FileNotFoundError:
        return None
    except InputError:
        return "special"
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            return "symlink"
        raise
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
            for base, dirs, files, _ in os.fwalk(root, follow_symlinks=False):
                dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()
                           and not (task_id == "primary" and Path(base) / d == project / "work/tasks")
                           and not (task_id not in (None, "primary") and Path(base) / d == project / task_directory(task_id) / "inputs")]
                paths.extend(Path(base) / f for f in files if f.lower().endswith(".md"))
    result = {p.relative_to(project).as_posix(): file_digest(p) for p in paths}
    return {rel: digest for rel, digest in result.items() if digest is not None}


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
    try:
        chunks = []
        with open_regular(path) as stream:
            while True:
                check_deadline(deadline)
                chunk = stream.read(64 * 1024)
                check_deadline(deadline)
                if not chunk:
                    break
                chunks.append(chunk)
        text = b"".join(chunks).decode("utf-8")
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


def publish_drafts(project, drafts, baseline, external_changes, task_id="primary", protected=(),
                   superseded=(), unresolved=()):
    proposals = draft_proposals(project, drafts, task_id, protected)
    conflicts, preserved = [], []
    for rel, target, text in proposals:
        if rel in superseded:
            continue
        if rel in unresolved or file_digest(target) != baseline.get(rel):
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
            + "\n\n## Human feedback\n\n" + (intake.feedback or "(absent)")
            + "\n\n## Authorized scientific references (evidence only)\n\n"
            + json.dumps(intake.references, ensure_ascii=True, indent=2) + "\n")


def handoff_fields(task_id="primary"):
    fields = (f"Logical researcher: {task_id}", "## Objective", "## Completed",
              "## Artifacts", "## Assumptions", "## Unresolved", "## Next action",
              "## Parent question", "## Phase", "## Role", "## Jobs")
    if task_id != "primary":
        fields += ("## Interrupted computation", "## Resume or reconsider")
    return fields


def validate_handoff(project, text, drafts=None, deadline=None, task_id="primary",
                     task=None, resolve_artifact=None, owned_jobs=()):
    from . import verification
    if task is not None:
        fields = ("Objective", "Parent question", "Phase", "Role", "Jobs")
        if task["role"] == "opponent":
            fields += ("Review history", "Objections")
        sections = verification.sections(text, fields)
        # Quote multiline objectives so their headings remain inside this section.
        if sections["Objective"] != task["objective"].strip():
            sections["Objective"] = "\n".join(
                line.removeprefix("> ") for line in sections["Objective"].splitlines())
        expected = {"Objective": task["objective"], "Parent question": str(task["parent_task"]),
                    "Phase": task["phase"], "Role": task["role"]}
        if any(sections[k] != str(v).strip() for k, v in expected.items()):
            raise InputError("Handoff logical objective/parent/phase/role mismatch")
        if f"Logical researcher: {task_id}" not in text.splitlines():
            raise InputError("Handoff logical identity mismatch")
        for job in owned_jobs:
            if job["job_id"] not in sections["Jobs"]:
                raise InputError("Handoff omits surviving job purpose/reference")
        if owned_jobs and not all(word in sections["Jobs"].lower() for word in ("purpose", "output", "checkpoint", "job_status", "job_wait", "job_cancel")):
            raise InputError("Handoff requires job purpose, outputs/checkpoints and inspection/wait/cancellation guidance")
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
        if target.startswith("document:"):
            if resolve_artifact is None:
                raise InputError("Immutable document resolver unavailable")
            resolve_artifact(target)
            artifacts.append(target)
            continue
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
        if task is not None and rel == handoff_path(task_id):
            # A navigation link to this handoff is harmless, but cannot serve as
            # evidence of saved science or become its own artifact dependency.
            continue
        if rel != "RESEARCH_STATUS.md" and (not Path(rel).parts or Path(rel).parts[0] not in MANAGED):
            raise InputError(f"Handoff must reference scientific artifacts: {rel}")
        if drafts is not None and p.suffix == ".md":
            proposed = safe_path(drafts, rel)
            if proposed.exists():
                p = proposed
        if resolve_artifact is not None:
            resolve_artifact(rel)
        else:
            if not p.is_file():
                raise InputError(f"Missing handoff artifact: {rel}")
            verification.read_bytes(p, deadline)
        artifacts.append(rel)
    if not artifacts:
        raise InputError("Handoff must link at least one saved scientific artifact")
    check_deadline(deadline)
    return sorted(set(artifacts))


def validate_deliverables(project, labels=("preliminary",)):
    failures = []
    linked_computation = False
    reference_catalog = None
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
            path = Path(unquote(url.path))
            if path.is_relative_to("/references"):
                # These are source paths in the scientific namespace, not host
                # paths. Apply the same authorization/path checks as retrieval.
                from . import references
                try:
                    if reference_catalog is None:
                        reference_catalog = references.load_catalog(project)
                    parts = path.relative_to("/references").parts
                    if len(parts) < 2:
                        raise references.ReferenceError("Expected reference alias and file")
                    references.resolve(reference_catalog, parts[0], Path(*parts[1:]))
                except (OSError, ValueError) as exc:
                    failures.append(f"Broken or unavailable reference link in {rel}: {target}: {exc}")
                continue
            local = (p.parent / path).resolve()
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
