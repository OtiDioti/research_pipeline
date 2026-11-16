"""Shared test helpers: temporary projects, fake CLI drivers and a controller harness.

The fake drivers (from :mod:`agent_sessions.testing`) replace a CLI session without any process, so controller tests
exercise every decision (spawning, handoffs, quota, reviews, pauses) quickly and
deterministically. Tests act as the agents: they call tools exactly as the MCP
server would and emit the events a real CLI would.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import tempfile

from agent_sessions.quota import Window
from agent_sessions.testing import FAKE_DRIVERS, FakeClaude, FakeSession  # noqa: F401 (used by the tests)

from research_pipeline import controller as controller_module
from research_pipeline.controller import Controller
from research_pipeline.state import Options

#: Temporary projects live here: projects may not live under /tmp (see Project.prepare).
TEST_ROOT = Path.home() / '.cache' / 'research-pipeline-tests'


def launch_options(**changes) -> Options:
    """Launch options for tests: explicit CLI choices for the primary and Reviewer, both fake CLIs allowed."""
    return Options(**({'primary': 'codex:gpt-test:high', 'reviewer': 'codex:gpt-test:high',
                       'backends': ['codex', 'claude']} | changes))


def temp_project(question: str = 'What is the integral of x^2 on [0, 1]?') -> Path:
    """A fresh project folder with a research question; remove it with :func:`remove`."""
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(dir=TEST_ROOT))
    (root / 'starting_evidence').mkdir()
    (root / 'starting_evidence' / 'RESEARCH_QUESTIONS.md').write_text(question + '\n')
    return root


def remove(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


class QuotaReader:
    """Usage readings set by the test: backend -> remaining % of the short and weekly windows."""

    def __init__(self):
        self.remaining = {'codex': (80.0, 80.0), 'claude': (80.0, 80.0)}
        self.fail: set[str] = set()

    def __call__(self, backend: str) -> list[Window]:
        if backend in self.fail:
            raise OSError(f'{backend} usage unreadable')
        short, weekly = self.remaining[backend]
        return [Window(backend, 300, 100 - short, None), Window(backend, 10080, 100 - weekly, None)]


class Harness:
    """A controller running on fake drivers, with helpers to act as its agents."""

    def __init__(self, root: Path, options: Options | None = None):
        self.root = root
        self.quota = QuotaReader()
        self.lines: list[tuple[str, str, str]] = []
        self.controller = Controller(root, options or launch_options(), drivers=FAKE_DRIVERS,
                                     read_quota=self.quota, show=lambda *entry: self.lines.append(entry))
        self.task: asyncio.Task | None = None

    @property
    def state(self):
        return self.controller.state

    def session(self, agent_id: str) -> FakeSession:
        return self.controller.sessions[agent_id]

    async def settle(self, rounds: int = 5) -> None:
        """Let queued events and background loops run."""
        for _ in range(rounds):
            await asyncio.sleep(0.02)

    async def call(self, agent_id: str, tool: str, **args) -> str:
        """Call a tool as ``agent_id``'s current session would."""
        request = {'agent': agent_id, 'token': self.controller.tokens.get(agent_id), 'tool': tool, 'args': args}
        reply = await self.controller._tool_request(request)
        await self.settle()
        return reply

    async def emit(self, agent_id: str, kind: str, **data) -> None:
        self.session(agent_id).emit(kind, **data)
        await self.settle()

    def write(self, relative: str, text: str = 'content\n') -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def index(self, folder: str, *entries: str) -> None:
        """Write a FOLDER_CONTENT.md describing ``entries`` in ``folder``."""
        self.write(f'{folder}/FOLDER_CONTENT.md', '# Folder contents\n\n'
                   + ''.join(f'- [{entry}]({entry}) — described.\n' for entry in entries))

    def handoff(self, agent_id: str) -> None:
        self.write(f'agents/{agent_id}/HANDOFF.md', '# Handoff\n\nNext: continue.\n')


@asynccontextmanager
async def running(root: Path, options: Options | None = None):
    """Run a controller on fake drivers for the duration of the block."""
    saved = (controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL)
    controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL = 0.02, 0.05
    harness = Harness(root, options)
    harness.task = asyncio.create_task(harness.controller.run())
    try:
        for _ in range(200):
            await asyncio.sleep(0.02)
            if 'primary' in harness.controller.sessions or harness.task.done():
                break
        if harness.task.done():
            harness.task.result()  # raise the controller's error
        yield harness
    finally:
        if not harness.task.done():
            harness.task.cancel()
        await asyncio.gather(harness.task, return_exceptions=True)
        controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL = saved
