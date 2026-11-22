"""The project folder: its layout, its phases' folders, the layout check, git commits and the human's files.

A project is an ordinary folder kept in git (PROJECT.md §2). Shared by every phase
are the human's AGENTS.md and starting_evidence/, the library and the Librarian's
folder; each phase has its own folder, ``phases/<N>/``, with the human's
OBJECTIVES.md and the phase's agents, status, report and reviews. A
:class:`Project` is bound to one phase. The controller creates the layout,
commits on every significant event, notices when the human changes their own
files, and checks agents' work against the layout rules before accepting a
handoff, a result or a proposal.

The controller runs git outside any confinement, on a repository agents and
their jobs write, through the shared safe runner (:mod:`agent_toolkit.git`):
hooks, fsmonitor and other programs git could start are off and the controller's
``GIT_*`` variables are ignored, while the human's own git configuration (global
ignore file, default branch, LFS) still applies.
Its own files go through :mod:`agent_toolkit.records`: written atomically, never
through a symlink, and only inside the project.
"""

from __future__ import annotations

import os
from pathlib import Path

from agent_toolkit import git as runner
from agent_toolkit.records import atomic_write

from research_pipeline.state import Agent

#: Top-level entries a project may contain; anything else is reported by the layout check.
TOP_LEVEL = frozenset(
    {
        "AGENTS.md",
        "starting_evidence",
        "library",
        "librarian",
        "phases",
        ".research",
        "FOLDER_CONTENT.md",
        ".git",
        ".gitignore",
    }
)
#: The entries of a phase's folder (``phases/<N>/``).
PHASE_LEVEL = frozenset({"OBJECTIVES.md", "STATUS.md", "REPORT.md", "agents", "reviews", "FOLDER_CONTENT.md"})
#: The human's files shared by every phase (with each phase's OBJECTIVES.md): agents never write them, and the
#: primary is told when they change.
HUMAN = ("AGENTS.md", "starting_evidence")
#: The Librarian's agent id and folder (at the top level: it serves every phase).
LIBRARIAN = "librarian"
#: Document formats that are not Markdown; agent notes must be Markdown (code and data are not flagged).
DOCUMENT_FORMATS = frozenset({".docx", ".doc", ".odt", ".rtf", ".rst", ".org"})
#: Files above this size stay on disk but are not committed.
LARGE = 50 * 1024 * 1024
INDEX = "FOLDER_CONTENT.md"
#: The controller's folder of library/: one catalogue page per shelved agent.
CATALOG_PAGES = "catalog"
GITIGNORE = """# Written by research-pipeline: controller state, environments and caches stay out of git.
.research/
.venv/
venv/
__pycache__/
*.pyc
.ipynb_checkpoints/
"""
ROOT_INDEX = """# Folder contents

- [AGENTS.md](AGENTS.md) — Instructions from the human to every agent (optional).
- [starting_evidence](starting_evidence) — The human's evidence and tools, shared by every phase; read-only for agents.
- [library](library) — The Librarian's pages leading to the finished work of every phase, starting at LIBRARY.md.
- [librarian](librarian) — The Librarian's own folder.
- [phases](phases) — One folder per phase of the investigation: its objectives, agents, status, report and reviews.
"""
PHASE_INDEX = """# Folder contents

- [OBJECTIVES.md](OBJECTIVES.md) — The human's objectives for this phase: the questions to answer, the tasks to perform.
- [STATUS.md](STATUS.md) — Current state of this phase, maintained by its primary researcher.
- [REPORT.md](REPORT.md) — The synthesis submitted with COMPLETE.
- [agents](agents) — One folder per agent: its task, handoff, result and work (frozen once shelved).
- [reviews](reviews) — The Reviewer's reviews.
"""
EMPTY_INDEX = "# Folder contents\n\n"
LIBRARY_INDEX = """# Folder contents

- [LIBRARY.md](LIBRARY.md) — The Librarian's entry page: how the library is organised, and its changes.
- [CATALOG.md](CATALOG.md) — Index of the shelved agents (with their tasks) and the agents at work, by the controller.
- [catalog](catalog) — One page per shelved agent listing its files, kept by the controller.
"""
LIBRARY_START = "# Library\n\nNothing is shelved yet. The Librarian describes the library's organisation here.\n"
#: Top-level folders of projects made before the library: such projects are not migrated (PROJECT.md §6).
LEGACY = ("sources", "tools")
# Commits are made by the controller under this identity; the agent and event go in the message.
IDENTITY = ("research-pipeline", "research-pipeline@localhost")
_EXCLUDE_MARK = "# research-pipeline: large files"


class ProjectError(RuntimeError):
    """The project folder cannot be used."""


class Project:
    """Paths and operations of one project folder, bound to one of its phases (``phase``)."""

    def __init__(self, root: Path, phase: int = 1):
        self.root = Path(root).resolve()
        self.evidence = self.root / "starting_evidence"  # the human's: read-only for agents and their jobs
        self.library = self.root / "library"  # the Librarian's pages; read-only for every session and job
        self.librarian = self.root / LIBRARIAN
        self.phases = self.root / "phases"
        self.research = self.root / ".research"  # the controller's: hidden from agents and their jobs
        self.logs = self.research / "logs"
        self.removed = self.research / "removed"  # material the human removed on the setup page
        self.home_file = self.research / "project.json"  # the phases and the Librarian (research_pipeline.phases)
        self.lock_file = self.research / "lock"
        self.library_activity = self.research / "activity"  # the Librarian's activity log
        # The phase's own.
        self.phase = phase
        self.phase_dir = self.phases / str(phase)
        self.objectives = self.phase_dir / "OBJECTIVES.md"  # the human's
        self.status_file = self.phase_dir / "STATUS.md"
        self.report = self.phase_dir / "REPORT.md"
        self.agents = self.phase_dir / "agents"
        self.reviews = self.phase_dir / "reviews"
        self.state_file = self.research / "phases" / str(phase) / "state.json"
        self.activity = self.research / "phases" / str(phase) / "activity"
        self.talks = self.research / "phases" / str(phase) / "talks"

    def at(self, phase: int) -> Project:
        """The same project, bound to ``phase``."""
        return Project(self.root, phase)

    @property
    def folder(self) -> str:
        """The phase's folder, relative to the project (e.g. 'phases/2')."""
        return f"phases/{self.phase}"

    def agent_dir(self, agent_id: str) -> Path:
        return self.librarian if agent_id == LIBRARIAN else self.agents / agent_id

    def session_log(self, agent_id: str, number: int, kind: str = "") -> Path:
        """The CLI log of an agent's session ``number`` (``kind`` e.g. 'talk'); the Librarian's are the project's."""
        name = "-".join(filter(None, [agent_id if agent_id == LIBRARIAN else f"phase{self.phase}-{agent_id}", kind]))
        return self.logs / f"{name}-{number}.jsonl"

    def relative(self, path: Path) -> str:
        return str(Path(path).resolve().relative_to(self.root))

    def inside(self, path: Path) -> bool:
        try:
            Path(path).resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    # Layout ---------------------------------------------------------------------------

    def prepare(self) -> None:
        """Create the layout (the top level and the phase's folder) and the git repository; keep what is there.

        Only a new repository is committed here: in an existing one, changes made while
        the controller was off stay uncommitted, so that the controller can report them.
        """
        problems = self.unready()
        if problems:
            raise ProjectError(" ".join(problems))
        self.create_phase()
        for folder in (self.library, self.librarian, self.agents, self.reviews, self.logs):
            folder.mkdir(parents=True, exist_ok=True)
        for path, text in (
            (self.status_file, f"# Status\n\nPhase {self.phase} has not started yet.\n"),
            (self.report, ""),
            (self.root / INDEX, ROOT_INDEX),
            (self.library / "LIBRARY.md", LIBRARY_START),
            (self.library / INDEX, LIBRARY_INDEX),
            (self.reviews / INDEX, EMPTY_INDEX),
            (self.librarian / INDEX, EMPTY_INDEX),
        ):
            if not path.exists():
                self.write(path, text)
        ignore = self.root / ".gitignore"
        if not ignore.exists():
            self.write(ignore, GITIGNORE)
        elif ".research/" not in ignore.read_text(encoding="utf-8").split():
            self.write(ignore, ignore.read_text(encoding="utf-8").rstrip("\n") + "\n.research/\n")
        if not (self.root / ".git").exists():  # a new repository starts with the prepared layout; later changes
            self.git("init", "-q")  # stay uncommitted for the controller to report and commit
            self.commit("controller: project prepared")

    def check_location(self) -> None:
        """Refuse a folder under /tmp: each agent session has its own private /tmp."""
        if str(self.root).startswith("/tmp/"):
            raise ProjectError("Projects cannot live under /tmp: each agent session has its own private /tmp.")

    def create_phase(self) -> None:
        """Create the phase's folder with its index and an OBJECTIVES.md to write (kept if they exist)."""
        self.phase_dir.mkdir(parents=True, exist_ok=True)
        for path, text in ((self.phase_dir / INDEX, PHASE_INDEX), (self.objectives, "")):
            if not path.exists():
                self.write(path, text)

    @property
    def name_file(self) -> Path:
        """Where the web page keeps the project's display name (the folder's own name never changes)."""
        return self.research / "name"

    @property
    def name(self) -> str:
        """The project's display name: the one given on the web page, else its folder's."""
        try:
            return self.name_file.read_text(encoding="utf-8").strip() or self.root.name
        except OSError:
            return self.root.name

    @property
    def started(self) -> bool:
        """True once an investigation has started here, in any phase (it has stored state)."""
        return self.home_file.exists()

    @property
    def phase_started(self) -> bool:
        """True once this phase has started (it has stored state)."""
        return self.state_file.exists()

    def unready(self) -> list[str]:
        """What keeps the folder from being a project, as sentences (empty: it is ready; PROJECT.md §2).

        Every phase needs a non-empty OBJECTIVES.md in its folder, and the project no legacy
        layout. Before the first start it also needs no loose material at the top level, and
        every entry at the top of starting_evidence/ described (see :meth:`evidence_problems`);
        the web setup makes a folder ready (docs/SETUP.md).
        """
        self.check_location()
        legacy = [name for name in LEGACY if (self.root / name).exists()]
        if legacy:
            return [
                f"This project predates the library (it has {' and '.join(f'{name}/' for name in legacy)}) "
                "and is not migrated: start a new project, with what it needs in starting_evidence/."
            ]
        problems = []
        if not self.objectives.is_file():
            problems.append(f"{self.objectives} is missing: write the objectives (questions or tasks) there first.")
        elif not self.objectives.read_text(encoding="utf-8", errors="replace").strip():
            problems.append(f"{self.objectives} is empty: write the objectives (questions or tasks) there first.")
        if not self.started:
            loose = self.stray_entries()
            if loose:
                problems.append(f"Loose material at the top level, to place in starting_evidence/: {', '.join(loose)}.")
            problems += self.evidence_problems()
        return problems

    def indexed_folders(self) -> list[Path]:
        """starting_evidence/ and, below it, every folder with its own FOLDER_CONTENT.md: where material is placed.

        A folder without one (e.g. a code repository) is described as one unit by its parent.
        """
        found, pending = [], [self.evidence] if self.evidence.is_dir() else []
        while pending:
            folder = pending.pop(0)
            found.append(folder)
            pending += [
                sub
                for sub in sorted(folder.iterdir())
                if sub.is_dir() and not sub.name.startswith(".") and (sub / INDEX).is_file()
            ]
        return found

    def undescribed(self, folder: Path) -> list[Path]:
        """The entries of an indexed folder its FOLDER_CONTENT.md does not mention (hidden entries need none)."""
        index = folder / INDEX
        text = index.read_text(encoding="utf-8", errors="replace") if index.is_file() else ""
        return [
            entry
            for entry in sorted(folder.iterdir())
            if not entry.name.startswith(".") and entry.name != INDEX and f"[{entry.name}]" not in text
        ]

    def evidence_problems(self) -> list[str]:
        """Entries at the top of starting_evidence/ that its FOLDER_CONTENT.md does not describe.

        Deeper folders are the human's own (an archived run may keep its index byte for byte);
        those the setup creates are described as material is placed in them.
        """
        missing = self.undescribed(self.evidence) if self.evidence.is_dir() else []
        if not missing:
            return []
        if not (self.evidence / INDEX).is_file():
            return [f"starting_evidence/{INDEX} is missing: it describes each entry in one line."]
        return [f"starting_evidence/{INDEX} does not describe: {', '.join(entry.name for entry in missing)}."]

    def write(self, path: Path, text: str) -> None:
        """Replace a file of the project atomically; never through a symlink, never outside the project."""
        atomic_write(path, text, root=self.root)

    def write_agents_index(self, agents: list[Agent]) -> None:
        """Maintain the phase's agents/FOLDER_CONTENT.md: one line per agent, from its task's first line."""
        lines = [EMPTY_INDEX.rstrip("\n"), ""]
        for agent in sorted((a for a in agents if a.id != LIBRARIAN), key=lambda a: a.id):
            task = self.agent_dir(agent.id) / "TASK.md"
            summary = {
                "primary": "Primary researcher.",
                "reviewer": "Final Reviewer.",
                "librarian": "Keeps the library's pages.",
            }.get(agent.role, "")
            if task.is_file():
                summary = (
                    next(
                        (
                            line.strip("# ").strip()
                            for line in task.read_text(encoding="utf-8").splitlines()
                            if line.strip()
                        ),
                        "",
                    )
                    or summary
                )
            lines.append(f"- [{agent.id}]({agent.id}) — {agent.role}, {agent.status}. {summary}".rstrip())
        self.write(self.agents / INDEX, "\n".join(lines) + "\n")

    def inventory(self, folder: str = "starting_evidence", limit: int = 200) -> str:
        """List the files of ``folder`` with their sizes, for an agent's opening message."""
        base = self.root / folder
        entries = []
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if path.is_file():
                entries.append(f"- {self.relative(path)} ({path.stat().st_size:,} bytes)")
        if len(entries) > limit:
            entries = entries[:limit] + [f"- … and {len(entries) - limit} more files"]
        return "\n".join(entries) or "(none)"

    def stray_entries(self) -> list[str]:
        """Unexpected top-level entries (hidden ones, such as editor or Obsidian files, are ignored).

        Agents cannot write the top level, so strays come from jobs or the human: they are
        reported to the primary, never held against an agent's work.
        """
        return [
            entry.name
            for entry in sorted(self.root.iterdir())
            if entry.name not in TOP_LEVEL and not entry.name.startswith(".")
        ]

    def check_layout(self, agent: Agent) -> list[str]:
        """Return the problems the agent should fix in its own scope (PROJECT.md §2); empty when all is well."""
        problems = []
        tops = [self.agent_dir(agent.id)]
        if agent.role == "primary":
            tops.append(self.phase_dir)
        elif agent.role == "reviewer":
            tops.append(self.reviews)
        elif agent.role == "librarian":
            tops.append(self.library)
        for top in tops:
            try:  # files may come and go meanwhile (jobs, editors): a vanished path is simply skipped
                if not top.is_dir():
                    continue
                below = self._below(top) if top != self.phase_dir else []
                ignored = self._ignored([top, *below, *top.iterdir()])
                if top == self.library:  # the controller's own folder of library/: no index line needed
                    ignored.add(self.library / CATALOG_PAGES)
                for folder in [top, *(path for path in below if path.is_dir())]:
                    if not (folder in ignored or any(parent in ignored for parent in folder.parents)):
                        problems += self._index_problems(folder, ignored)
            except OSError:
                continue
        return problems[:30]

    @staticmethod
    def _below(top: Path) -> list[Path]:
        """Everything under ``top`` an agent maintains: not hidden and not the controller's job output."""
        found = []
        for path in sorted(top.rglob("*")):
            parts = path.relative_to(top).parts
            if not any(part.startswith(".") for part in parts) and parts[0] != "jobs":
                found.append(path)
        return found

    def _ignored(self, paths: list[Path]) -> set[Path]:
        """The paths git ignores (virtual environments, caches): they need no index or description."""
        # A trailing slash lets directory patterns such as `venv/` match.
        listing = "\n".join(f"{path}/" if path.is_dir() else str(path) for path in paths)
        output = self.git("check-ignore", "--stdin", input=listing, check=False)
        return {Path(line.rstrip("/")) for line in output.splitlines()}

    def _index_problems(self, folder: Path, ignored: set[Path]) -> list[str]:
        name = self.relative(folder)
        index = folder / INDEX
        # Hidden or ignored entries, the index itself and the controller's job folders need no description.
        entries = [
            entry
            for entry in sorted(folder.iterdir())
            if not entry.name.startswith(".") and entry.name not in (INDEX, "jobs") and entry not in ignored
        ]
        problems = [
            f"{name}/{entry.name}: notes must be Markdown"
            for entry in entries
            if entry.is_file() and entry.suffix.lower() in DOCUMENT_FORMATS
        ]
        if folder == self.phase_dir:  # the primary maintains the index of these; the rest is the human's or others'
            entries = [entry for entry in entries if entry.name in PHASE_LEVEL]
        if not index.is_file():
            return problems + ([f"{name}/{INDEX} is missing"] if entries else [])
        text = index.read_text(encoding="utf-8", errors="replace")
        missing = [entry.name for entry in entries if entry.name not in text]
        if missing:
            problems.append(f"{name}/{INDEX} does not describe: {', '.join(missing[:10])}")
        return problems

    # Git ------------------------------------------------------------------------------

    def git(self, *args: str, check: bool = True, input: str | None = None) -> str:
        """Run git safely in the project (see the module documentation); return its output.

        Raise ProjectError if it fails and ``check``.
        """
        try:
            return runner.output(
                self.root,
                *args,
                check=check,
                isolated=False,
                identity=IDENTITY,
                input=None if input is None else input.encode(),
            )
        except runner.GitError as error:
            raise ProjectError(f"git {args[0]} failed: {str(error).removeprefix('GIT_ERROR: ')[:300]}") from None

    def uncommitted(self, *paths: str) -> list[str]:
        """Paths with changes since the last commit (optionally only under ``paths``)."""
        output = self.git("status", "--porcelain", "--untracked-files=all", "--", *(paths or ["."]), check=False)
        return [line[3:].strip().strip('"') for line in output.splitlines() if line.strip()]

    def files(self) -> list[str]:
        """Every file git tracks or would add (tracked, or untracked and not ignored), relative to the root."""
        output = self.git("ls-files", "-z", "--cached", "--others", "--exclude-standard", check=False)
        return [path for path in output.split("\0") if path]

    def commit(self, message: str) -> str | None:
        """Commit every change except large files; return the new commit, or None if nothing changed."""
        large = self._exclude_large()
        self.git("add", "-A")
        if not self.git("status", "--porcelain", check=False).strip():
            return None
        if large:
            message += "\n\nNot committed (over 50 MB):\n" + "\n".join(f"- {path}" for path in large)
        self.git("commit", "-q", "--no-verify", "-m", message)
        return self.head()

    def head(self) -> str:
        """The current commit."""
        return self.git("rev-parse", "HEAD").strip()

    def changed_since(self, commit: str, *excluded: str) -> list[str]:
        """Paths committed differently since ``commit``, except under ``excluded`` folders."""
        output = self.git(
            "diff", "--name-only", commit, "HEAD", "--", ".", *(f":(exclude){path}" for path in excluded), check=False
        )
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _exclude_large(self) -> list[str]:
        """Keep files over :data:`LARGE` out of git through the repository's exclude file."""
        large = []
        for directory, folders, files in os.walk(self.root):
            folders[:] = [name for name in folders if name not in (".git", ".research")]
            for name in files:
                path = Path(directory) / name
                try:
                    if path.stat().st_size > LARGE:
                        large.append(self.relative(path))
                except OSError:
                    continue
        exclude = Path(self.git("rev-parse", "--git-path", "info/exclude").strip())
        exclude = exclude if exclude.is_absolute() else self.root / exclude
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        kept = text.split(_EXCLUDE_MARK)[0].rstrip("\n")
        block = "\n".join([_EXCLUDE_MARK, *("/" + path for path in large)]) if large else ""
        try:  # jobs can write .git: like every controller file, never through a symlink nor outside the project
            self.write(exclude, "\n".join(filter(None, [kept, block])) + "\n")
        except ValueError as error:
            raise ProjectError(f"could not update the exclude file: {error}") from None
        if large:  # files that grew past the limit after an earlier commit
            self.git("rm", "-q", "--cached", "--ignore-unmatch", "--", *large, check=False)
        return large

    # The human's files ----------------------------------------------------------------

    def human_fingerprint(self) -> dict[str, str]:
        """Size and modification time of every file of the human's for this phase, to notice changes cheaply."""
        found = {}
        for path in [*(self.root / name for name in HUMAN), self.objectives]:
            for item in [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []:
                try:
                    if item.is_file():
                        info = item.stat()
                        found[self.relative(item)] = f"{info.st_size}:{info.st_mtime_ns}"
                except OSError:
                    continue  # e.g. an editor's temporary file that vanished meanwhile
        return found

    @staticmethod
    def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
        """Files added, removed or modified between two fingerprints."""
        return sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))

    def human_changes(self, baseline: dict[str, str], commit: str | None) -> list[str]:
        """The human's files changed since ``baseline`` (their fingerprint at ``commit``), by content.

        A file whose fingerprint changed but whose content is that of ``commit`` again
        (e.g. reverted) is not a change. A file not in ``commit`` (new, or too large to be
        committed) counts by its fingerprint. Without ``commit``, fingerprints alone decide.
        """
        candidates = Project.changed(baseline, self.human_fingerprint())
        if not commit or not candidates:
            return candidates
        differing = self.git("diff", "--name-only", commit, "--", *candidates, check=False).split("\n")
        committed = self.git("ls-tree", "-r", "--name-only", commit, "--", *candidates, check=False).split("\n")
        return [path for path in candidates if path in differing or path not in committed]
