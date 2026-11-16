"""The project folder: its layout, the layout check, git commits and the human's files.

A project is an ordinary folder kept in git (PROJECT.md §2). The controller
creates the top-level layout, commits on every significant event, notices when
the human changes their own files, and checks agents' work against the layout
rules before accepting a handoff, a result or a proposal.

The controller runs git outside any confinement, on a repository agents and
their jobs write, through the shared safe runner (:mod:`agent_sessions.git`):
hooks, fsmonitor and other programs git could start are off, while the human's
own git configuration (global ignore file, default branch, LFS) still applies.
Its own files go through :mod:`agent_sessions.records`: written atomically, never
through a symlink, and only inside the project.
"""
from __future__ import annotations

from pathlib import Path
import os

from agent_sessions import git as runner
from agent_sessions.records import atomic_write

from research_pipeline.state import Agent

#: Top-level entries a project may contain; anything else is reported by the layout check.
TOP_LEVEL = frozenset({'AGENTS.md', 'FEEDBACK.md', 'starting_evidence', 'STATUS.md', 'REPORT.md', 'sources',
                       'tools', 'agents', 'reviews', '.research', 'FOLDER_CONTENT.md', '.git', '.gitignore'})
#: The human's files: agents never write them, and the primary is told when they change.
HUMAN = ('AGENTS.md', 'FEEDBACK.md', 'starting_evidence')
#: Document formats that are not Markdown; agent notes must be Markdown (code and data are not flagged).
DOCUMENT_FORMATS = frozenset({'.docx', '.doc', '.odt', '.rtf', '.rst', '.org'})
#: Files above this size stay on disk but are not committed.
LARGE = 50 * 1024 * 1024
INDEX = 'FOLDER_CONTENT.md'
GITIGNORE = """# Written by research-pipeline: controller state, environments and caches stay out of git.
.research/
.venv/
venv/
__pycache__/
*.pyc
.ipynb_checkpoints/
"""
ROOT_INDEX = """# Folder contents

- [AGENTS.md](AGENTS.md) — Instructions from the human (optional).
- [FEEDBACK.md](FEEDBACK.md) — Feedback from the human.
- [starting_evidence](starting_evidence) — The human's questions, evidence and tools; read-only for agents.
- [STATUS.md](STATUS.md) — Current state of the investigation, maintained by the primary researcher.
- [REPORT.md](REPORT.md) — The synthesis submitted with COMPLETE.
- [sources](sources) — Papers and notes on them, shared by all agents.
- [tools](tools) — Reusable tools made by the agents, each with a README.md.
- [agents](agents) — One folder per agent: its task, handoff, result and work.
- [reviews](reviews) — The Reviewer's reviews.
"""
EMPTY_INDEX = '# Folder contents\n\n'
# Commits are made by the controller under this identity; the agent and event go in the message.
IDENTITY = ('research-pipeline', 'research-pipeline@localhost')
_EXCLUDE_MARK = '# research-pipeline: large files'


class ProjectError(RuntimeError):
    """The project folder cannot be used."""


class Project:
    """Paths and operations of one project folder."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.evidence = self.root / 'starting_evidence'    # the human's: read-only for agents and their jobs
        self.questions = self.evidence / 'RESEARCH_QUESTIONS.md'
        self.agents = self.root / 'agents'
        self.reviews = self.root / 'reviews'
        self.research = self.root / '.research'           # the controller's: hidden from agents and their jobs
        self.logs = self.research / 'logs'
        self.state_file = self.research / 'state.json'
        self.lock_file = self.research / 'lock'

    def agent_dir(self, agent_id: str) -> Path:
        return self.agents / agent_id

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
        """Create the top-level layout and the git repository; keep everything already there.

        Only a new repository is committed here: in an existing one, changes made while
        the controller was off stay uncommitted, so that the controller can report them.
        """
        if str(self.root).startswith('/tmp/'):
            raise ProjectError('Projects cannot live under /tmp: each agent session has its own private /tmp.')
        if not self.questions.is_file():
            raise ProjectError(f'{self.questions} is missing: write the research questions there first.')
        for folder in (self.root / 'sources', self.root / 'tools', self.agents, self.reviews, self.logs):
            folder.mkdir(parents=True, exist_ok=True)
        for name, text in (('STATUS.md', '# Status\n\nThe investigation has not started yet.\n'),
                           ('REPORT.md', ''), ('FEEDBACK.md', ''), (INDEX, ROOT_INDEX)):
            if not (self.root / name).exists():
                self.write(self.root / name, text)
        for folder in (self.root / 'sources', self.root / 'tools', self.reviews):
            if not (folder / INDEX).exists():
                self.write(folder / INDEX, EMPTY_INDEX)
        ignore = self.root / '.gitignore'
        if not ignore.exists():
            self.write(ignore, GITIGNORE)
        elif '.research/' not in ignore.read_text(encoding='utf-8').split():
            self.write(ignore, ignore.read_text(encoding='utf-8').rstrip('\n') + '\n.research/\n')
        if not (self.root / '.git').exists():  # a new repository starts with the prepared layout; later changes
            self.git('init', '-q')             # stay uncommitted for the controller to report and commit
            self.commit('controller: project prepared')

    def write(self, path: Path, text: str) -> None:
        """Replace a file of the project atomically; never through a symlink, never outside the project."""
        atomic_write(path, text, root=self.root)

    def write_agents_index(self, agents: list[Agent]) -> None:
        """Maintain agents/FOLDER_CONTENT.md: one line per agent, from its task's first line."""
        lines = [EMPTY_INDEX.rstrip('\n'), '']
        for agent in sorted(agents, key=lambda a: a.id):
            task = self.agent_dir(agent.id) / 'TASK.md'
            summary = {'primary': 'Primary researcher.', 'reviewer': 'Final Reviewer.'}.get(agent.role, '')
            if task.is_file():
                summary = next((line.strip('# ').strip() for line in task.read_text(encoding='utf-8').splitlines()
                                if line.strip()), '') or summary
            lines.append(f'- [{agent.id}]({agent.id}) — {agent.role}, {agent.status}. {summary}'.rstrip())
        self.write(self.agents / INDEX, '\n'.join(lines) + '\n')

    def inventory(self, folder: str = 'starting_evidence', limit: int = 200) -> str:
        """List the files of ``folder`` with their sizes, for an agent's opening message."""
        base = self.root / folder
        entries = []
        for path in sorted(base.rglob('*')) if base.is_dir() else []:
            if path.is_file():
                entries.append(f'- {self.relative(path)} ({path.stat().st_size:,} bytes)')
        if len(entries) > limit:
            entries = entries[:limit] + [f'- … and {len(entries) - limit} more files']
        return '\n'.join(entries) or '(none)'

    def stray_entries(self) -> list[str]:
        """Unexpected top-level entries (hidden ones, such as editor or Obsidian files, are ignored).

        Agents cannot write the top level, so strays come from jobs or the human: they are
        reported to the primary, never held against an agent's work.
        """
        return [entry.name for entry in sorted(self.root.iterdir())
                if entry.name not in TOP_LEVEL and not entry.name.startswith('.')]

    def check_layout(self, agent: Agent) -> list[str]:
        """Return the problems the agent should fix in its own scope (PROJECT.md §2); empty when all is well."""
        problems = []
        tops = [self.agent_dir(agent.id), self.root / 'sources', self.root / 'tools']
        if agent.role == 'primary':
            tops.append(self.root)
        elif agent.role == 'reviewer':
            tops.append(self.reviews)
        for top in tops:
            try:  # files may come and go meanwhile (jobs, editors): a vanished path is simply skipped
                if not top.is_dir():
                    continue
                below = self._below(top) if top != self.root else []
                ignored = self._ignored([top, *below, *top.iterdir()])
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
        for path in sorted(top.rglob('*')):
            parts = path.relative_to(top).parts
            if not any(part.startswith('.') for part in parts) and parts[0] != 'jobs':
                found.append(path)
        return found

    def _ignored(self, paths: list[Path]) -> set[Path]:
        """The paths git ignores (virtual environments, caches): they need no index or description."""
        # A trailing slash lets directory patterns such as `venv/` match.
        listing = '\n'.join(f'{path}/' if path.is_dir() else str(path) for path in paths)
        output = self.git('check-ignore', '--stdin', input=listing, check=False)
        return {Path(line.rstrip('/')) for line in output.splitlines()}

    def _index_problems(self, folder: Path, ignored: set[Path]) -> list[str]:
        name = self.relative(folder) if folder != self.root else '.'
        index = folder / INDEX
        # Hidden or ignored entries, the index itself and the controller's job folders need no description.
        entries = [entry for entry in sorted(folder.iterdir()) if not entry.name.startswith('.')
                   and entry.name not in (INDEX, 'jobs') and entry not in ignored]
        problems = [f'{name}/{entry.name}: notes must be Markdown' for entry in entries
                    if entry.is_file() and entry.suffix.lower() in DOCUMENT_FORMATS]
        if folder == self.root:
            entries = [entry for entry in entries if entry.name in TOP_LEVEL]
        if not index.is_file():
            return problems + ([f'{name}/{INDEX} is missing'] if entries else [])
        text = index.read_text(encoding='utf-8', errors='replace')
        missing = [entry.name for entry in entries if entry.name not in text]
        if missing:
            problems.append(f'{name}/{INDEX} does not describe: {", ".join(missing[:10])}')
        return problems

    # Git ------------------------------------------------------------------------------

    def git(self, *args: str, check: bool = True, input: str | None = None) -> str:
        """Run git safely in the project (see the module documentation); return its output.

        Raise ProjectError if it fails and ``check``.
        """
        try:
            return runner.output(self.root, *args, check=check, isolated=False, identity=IDENTITY,
                                 input=None if input is None else input.encode())
        except runner.GitError as error:
            raise ProjectError(f'git {args[0]} failed: {str(error).removeprefix("GIT_ERROR: ")[:300]}') from None

    def uncommitted(self, *paths: str) -> list[str]:
        """Paths with changes since the last commit (optionally only under ``paths``)."""
        output = self.git('status', '--porcelain', '--untracked-files=all', '--', *(paths or ['.']), check=False)
        return [line[3:].strip().strip('"') for line in output.splitlines() if line.strip()]

    def commit(self, message: str) -> str | None:
        """Commit every change except large files; return the new commit, or None if nothing changed."""
        large = self._exclude_large()
        self.git('add', '-A')
        if not self.git('status', '--porcelain', check=False).strip():
            return None
        if large:
            message += '\n\nNot committed (over 50 MB):\n' + '\n'.join(f'- {path}' for path in large)
        self.git('commit', '-q', '--no-verify', '-m', message)
        return self.git('rev-parse', 'HEAD').strip()

    def _exclude_large(self) -> list[str]:
        """Keep files over :data:`LARGE` out of git through the repository's exclude file."""
        large = []
        for directory, folders, files in os.walk(self.root):
            folders[:] = [name for name in folders if name not in ('.git', '.research')]
            for name in files:
                path = Path(directory) / name
                try:
                    if path.stat().st_size > LARGE:
                        large.append(self.relative(path))
                except OSError:
                    continue
        exclude = Path(self.git('rev-parse', '--git-path', 'info/exclude').strip())
        exclude = exclude if exclude.is_absolute() else self.root / exclude
        text = exclude.read_text(encoding='utf-8') if exclude.exists() else ''
        kept = text.split(_EXCLUDE_MARK)[0].rstrip('\n')
        block = '\n'.join([_EXCLUDE_MARK, *('/' + path for path in large)]) if large else ''
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text('\n'.join(filter(None, [kept, block])) + '\n', encoding='utf-8')
        if large:  # files that grew past the limit after an earlier commit
            self.git('rm', '-q', '--cached', '--ignore-unmatch', '--', *large, check=False)
        return large

    # The human's files ----------------------------------------------------------------

    def human_fingerprint(self) -> dict[str, str]:
        """Size and modification time of every human-owned file, to notice changes cheaply."""
        found = {}
        for name in HUMAN:
            path = self.root / name
            for item in ([path] if path.is_file() else sorted(path.rglob('*')) if path.is_dir() else []):
                try:
                    if item.is_file():
                        info = item.stat()
                        found[self.relative(item)] = f'{info.st_size}:{info.st_mtime_ns}'
                except OSError:
                    continue  # e.g. an editor's temporary file that vanished meanwhile
        return found

    @staticmethod
    def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
        """Files added, removed or modified between two fingerprints."""
        return sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
