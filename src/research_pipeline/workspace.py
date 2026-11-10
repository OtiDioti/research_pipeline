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
from urllib.parse import unquote, urlsplit


class InputError(ValueError):
    pass


@dataclass
class Intake:
    project: Path
    questions: str
    instructions: str
    inventory: list[dict]
    fingerprints: dict[str, str]


MANAGED = ("sources", "work", "outputs")
REQUIRED = ("work/PLAN.md", "sources/LITERATURE.md", "outputs/REPORT.md")


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
    if (project / "AGENTS.md").exists():
        paths.append(project / "AGENTS.md")
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
    regular_tree(project)
    for name in (*MANAGED, "RESEARCH_STATUS.md", "FOLDER_CONTENT.md"):
        if (project / name).exists():
            raise InputError(f"Fresh project required; managed path already exists: {name}")
    # Tool configuration is not scientific input. Do not load project hooks/skills.
    for name in (".codex", ".agents", ".git"):
        if (project / name).exists():
            raise InputError(f"Use a plain research directory without {name}")
    q = project / "starting_evidence/RESEARCH_QUESTIONS.md"
    if not q.is_file():
        raise InputError(f"Required questions file is missing: {q}")

    def read_text(p):
        if not p.is_file() or not p.stat().st_mode & 0o444:
            raise InputError(f"Cannot read supplied input: {p}")
        if p.stat().st_size > 256 * 1024:
            raise InputError(f"Input exceeds 256 KiB prompt limit: {p}")
        try:
            return p.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InputError(f"Cannot read {p}: {exc}") from exc

    questions = read_text(q)
    if not questions.strip():
        raise InputError("RESEARCH_QUESTIONS.md must not be empty")
    instructions = read_text(project / "AGENTS.md") if (project / "AGENTS.md").exists() else ""
    inventory = []
    for p in sorted((project / "starting_evidence").rglob("*")):
        if p.is_file():
            if not p.stat().st_mode & 0o444:
                raise InputError(f"Unreadable starting evidence: {p}")
            inventory.append({"path": str(p.relative_to(project)), "bytes": p.stat().st_size})
    if len(inventory) > 10000:
        raise InputError("More than 10000 evidence files; narrow the starting material")
    return Intake(project, questions, instructions, inventory, fingerprints(project))


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
            raise InputError("Another start holds the project lock") from exc
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
    state["artifact_availability"] = {
        p: (project / p).is_file() and not (project / p).is_symlink() for p in REQUIRED
    }
    atomic_text(project / ".research_pipeline/run.json", json.dumps(state, indent=2) + "\n")
    links = "\n".join(f"- [{p}]({p})" if state["artifact_availability"][p]
                      else f"- `{p}` — not produced." for p in REQUIRED)
    atomic_text(project / "RESEARCH_STATUS.md", f"# Research status\n\n"
                f"State: **{state['state']}**\n\n{state.get('reason', '')}\n\n{links}\n\n"
                "Findings are preliminary: M1 has no independent verifier.\n\n"
                "See `.research_pipeline/run.json` for limits and operational diagnostics.\n")


DESCRIPTIONS = {
    "starting_evidence": "Human-owned scientific inputs (read-only; questions and supplied evidence).",
    "AGENTS.md": "Human-owned project instructions (read-only).",
    "sources": "Retrieved scientific sources and literature assessment.",
    "work": "Scientific plan, derivations, executable scripts and computation data.",
    "outputs": "Research findings and supporting figures.",
    ".research_pipeline": "Private controller status and bounded backend diagnostics.",
    "RESEARCH_STATUS.md": "Operational state and links to current scientific progress.",
    "PLAN.md": "Revisable scientific questions, assumptions and methods.",
    "LITERATURE.md": "Citations, relevance and source access quality.",
    "REPORT.md": "Preliminary findings, evidence, limitations and reproduction instructions.",
    "run.json": "Machine-readable run state, limits and observed outcomes.",
    "backend.jsonl": "Bounded private Codex event stream.",
    "stderr.txt": "Bounded private launcher/backend diagnostics.",
    "run.lock": "Exclusive foreground investigation lock.",
}


def refresh_indexes(project, include_science=True):
    # Walk only managed directories; never follow links made by scientific scripts.
    roots = [project, project / ".research_pipeline"]
    for name in MANAGED if include_science else ():
        if (project / name).is_dir() and not (project / name).is_symlink():
            for base, dirs, _ in os.walk(project / name, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
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
        atomic_text(directory / "FOLDER_CONTENT.md", "\n".join(rows) + "\n")


def validate_deliverables(project):
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
        if "preliminary" not in report.lower():
            failures.append("Report must label unchecked results preliminary")
        if not linked_computation:
            failures.append("Report must link to a local computational artifact (code or data) in work/")
    return failures
