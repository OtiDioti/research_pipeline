"""Shared test helpers: temporary projects, fake CLI drivers and a controller harness.

The fake drivers (from :mod:`agent_toolkit.testing`) replace a CLI session without any process, so controller tests
exercise every decision (spawning, handoffs, quota, reviews, pauses) quickly and
deterministically. Tests act as the agents: they call tools exactly as the MCP
server would and emit the events a real CLI would.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from agent_toolkit import McpServer
from agent_toolkit.quota import Window
from agent_toolkit.testing import FAKE_DRIVERS, FakeSession, call_tool  # noqa: F401 (used by the tests)

from research_pipeline import controller as controller_module
from research_pipeline.controller import MCP_SERVER, Controller
from research_pipeline.state import Options

#: Temporary projects live here: projects may not live under /tmp (see Project.prepare).
TEST_ROOT = Path.home() / ".cache" / "research-pipeline-tests"


def launch_options(**changes) -> Options:
    """Launch options for tests: explicit CLI choices for the primary and Reviewer, both fake CLIs allowed."""
    return Options(
        **(
            {
                "primary": "codex:gpt-test:high",
                "reviewer": "codex:gpt-test:high",
                "librarian": "codex:gpt-test:high",
                "backends": ["codex", "claude"],
            }
            | changes
        )
    )


def temp_project(question: str = "What is the integral of x^2 on [0, 1]?") -> Path:
    """A fresh project folder with a research question for its first phase; remove it with :func:`remove`."""
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(dir=TEST_ROOT))
    (root / "starting_evidence").mkdir()
    (root / "starting_evidence" / "FOLDER_CONTENT.md").write_text("# Folder contents\n\n")
    (root / "phases" / "1").mkdir(parents=True)
    (root / "phases" / "1" / "OBJECTIVES.md").write_text(question + "\n")
    return root


def remove(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


class QuotaReader:
    """Usage readings set by the test: backend -> remaining % of the short and weekly windows."""

    def __init__(self):
        self.remaining = {"codex": (80.0, 80.0), "claude": (80.0, 80.0)}
        self.fail: set[str] = set()

    def __call__(self, backend: str) -> list[Window]:
        if backend in self.fail:
            raise OSError(f"{backend} usage unreadable")
        short, weekly = self.remaining[backend]
        return [Window(backend, 300, 100 - short, None), Window(backend, 10080, 100 - weekly, None)]


class Harness:
    """A controller running on fake drivers, with helpers to act as its agents."""

    def __init__(self, root: Path, options: Options | None = None, reopen: bool | None = None, phase: int = 1):
        self.root = root
        self.phase = f"phases/{phase}"  # the phase's folder, relative to the project
        self.quota = QuotaReader()
        self.lines: list[tuple[str, str, str]] = []
        self.controller = Controller(
            root,
            options or launch_options(),
            drivers=FAKE_DRIVERS,
            read_quota=self.quota,
            show=lambda *entry: self.lines.append(entry),
            reopen=reopen,
            phase=phase,
        )
        self.task: asyncio.Task | None = None

    @property
    def state(self):
        return self.controller.state

    def session(self, agent_id: str) -> FakeSession:
        session = self.controller.sessions[agent_id]
        assert isinstance(session, FakeSession)  # FAKE_DRIVERS start only fake sessions
        return session

    async def settle(self, rounds: int = 5) -> None:
        """Let queued events and background loops run."""
        for _ in range(rounds):
            await asyncio.sleep(0.02)

    def tools(self, agent_id: str) -> McpServer:
        """The tool server entry of ``agent_id``'s latest session (current, or closed since)."""
        session = next(session for session in reversed(FakeSession.instances) if session.launch.agent == agent_id)
        return session.launch.mcp[MCP_SERVER]

    async def call(self, agent_id: str, tool: str, **args) -> str:
        """Call a tool as ``agent_id``'s latest session would, through the controller's socket; the reply's text."""
        reply = await call_tool(self.tools(agent_id), tool, **args)
        await self.settle()
        return reply["text"]

    async def emit(self, agent_id: str, kind: str, **data) -> None:
        self.session(agent_id).emit(kind, **data)
        await self.settle()

    def write(self, relative: str, text: str = "content\n") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def index(self, folder: str, *entries: str) -> None:
        """Write a FOLDER_CONTENT.md describing ``entries`` in ``folder``."""
        self.write(
            f"{folder}/FOLDER_CONTENT.md",
            "# Folder contents\n\n" + "".join(f"- [{entry}]({entry}) — described.\n" for entry in entries),
        )

    def handoff(self, agent_id: str) -> None:
        folder = "librarian" if agent_id == "librarian" else f"{self.phase}/agents/{agent_id}"
        self.write(f"{folder}/HANDOFF.md", "# Handoff\n\nNext: continue.\n")


async def shelve_all(harness: Harness) -> None:
    """Act as the Librarian: one page linking every pending agent's folder, then shelved for each."""
    pending = list(harness.controller.home.shelving)
    page = "# Work\n\n" + "".join(f"- [{folder}](/{folder}/)\n" for folder in pending)
    assert "Wrote" in await harness.call("librarian", "write_page", path="work.md", text=page)
    index = (harness.root / "library" / "FOLDER_CONTENT.md").read_text()
    if "work.md" not in index:
        await harness.call(
            "librarian", "write_page", path="FOLDER_CONTENT.md", text=index + "- [work.md](work.md) — Work.\n"
        )
    for folder in pending:
        reply = await harness.call("librarian", "shelved", folder=folder)
        assert reply.startswith("Shelved"), reply


async def complete(harness: Harness, shelve: bool = True) -> None:
    """COMPLETE, agreed by the Reviewer; the Librarian shelves the final work (unless not ``shelve``)."""
    phase = harness.phase
    harness.write(f"{phase}/REPORT.md", "# Report\n\nThe integral is 1/3.\n")
    harness.handoff("primary")
    harness.index(f"{phase}/agents/primary", "HANDOFF.md")
    await harness.call("primary", "complete")
    harness.write(f"{phase}/reviews/1.md", "# Review\n\n1. Fine.\n")
    harness.index(f"{phase}/reviews", "1.md")
    harness.handoff("reviewer")
    harness.index(f"{phase}/agents/reviewer", "HANDOFF.md")
    await harness.call("reviewer", "verdict", review="1.md", agree=True)
    if shelve:
        await shelve_all(harness)
    await harness.settle()


async def quit_after_the_end(harness: Harness) -> None:
    """After the end the controller stays open for talks: the human quits (Ctrl+Q), and it exits."""
    harness.controller.shutdown()
    assert harness.task is not None
    await asyncio.wait_for(harness.task, 5)


@asynccontextmanager
async def running(root: Path, options: Options | None = None, reopen: bool | None = None, phase: int = 1):
    """Run a controller of ``phase`` on fake drivers for the duration of the block (``reopen``: see Controller)."""
    saved = (controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL)
    controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL = 0.02, 0.05
    harness = Harness(root, options, reopen, phase)
    harness.task = asyncio.create_task(harness.controller.run())
    try:
        for _ in range(200):
            await asyncio.sleep(0.02)
            ended = harness.controller.lock is not None and harness.controller.state.status in ("complete", "stopped")
            if "primary" in harness.controller.sessions or harness.task.done() or ended:  # ended: talk-only
                break
        if harness.task.done():
            harness.task.result()  # raise the controller's error
        yield harness
    finally:
        if not harness.task.done():
            harness.task.cancel()
        await asyncio.gather(harness.task, return_exceptions=True)
        controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL = saved
