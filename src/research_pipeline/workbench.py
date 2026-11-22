"""Every research project of this machine in one web page (``research-pipeline run``): the workbench's list.

Built on :class:`agent_toolkit.web.Workbench`. The list lives in
``~/.config/research_pipeline/`` (``$XDG_CONFIG_HOME`` if set); a project's display
name in its ``.research/name``. Each project selected opens its
:class:`~research_pipeline.web.ResearchDashboard`, which runs its controllers with
the command line's ``runner``. One project works at a time: while one runs (or
pauses on its way), the others can be browsed, set up and talked with, and their
Start or Resume waits.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from agent_toolkit import DRIVERS
from agent_toolkit.records import locked
from agent_toolkit.web import Dashboard, Workbench

from research_pipeline.controller import Controller
from research_pipeline.phases import NOT_STARTED, PHASE_COLOURS, Home, load_state
from research_pipeline.project import Project, ProjectError
from research_pipeline.state import FINISHED, Options
from research_pipeline.web import ResearchDashboard

#: Seconds a project's description read from disk is reused (the page asks twice a second).
FRESH = 2.0
#: States in which a project works.
WORKING = ("running", "pausing")

Runner = Callable[[Controller, ResearchDashboard], Awaitable[int]]


def home() -> Path:
    """Where the workbench keeps its list of projects (and the running server's address)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "research_pipeline"


class ResearchWorkbench(Workbench):
    """The research projects of this machine; each one's dashboard runs its controllers with ``runner``."""

    program = "research_pipeline"
    port = 8780

    def __init__(self, folder: Path, runner: Runner | None = None, drivers=DRIVERS, **controller_options):
        """``runner`` runs one controller to its end (None: nothing runs, e.g. in tests that drive controllers)."""
        super().__init__(folder)
        self.runner, self.drivers, self.controller_options = runner, drivers, controller_options
        self.options: dict[str, Options] = {}  # folder -> the command line's options for it
        self._described: dict[str, tuple[float, dict]] = {}

    def name_file(self, folder: Path) -> Path:
        return Project(folder).name_file

    def check(self, folder: Path) -> None:
        try:
            Project(folder).check_location()
        except ProjectError as error:
            raise ValueError(str(error)) from None

    def open(self, folder: Path) -> Dashboard:
        project = Project(folder)
        options = self.options.get(str(project.root)) or stored(project) or Options()
        dashboard: ResearchDashboard
        dashboard = ResearchDashboard(
            project.root,
            options,
            self.drivers,
            launch=self.launch if self.runner is not None else None,
            others=lambda: self.working(dashboard),
            **self.controller_options,
        )
        return dashboard

    def launch(self, dashboard: ResearchDashboard) -> None:
        """Run the dashboard's controllers; the project moves to the top of the list."""
        self.remember(dashboard.project)
        dashboard.task = asyncio.ensure_future(self._drive(dashboard))

    async def _drive(self, dashboard: ResearchDashboard) -> None:
        """Run the controller, then each one the page hands over to (Start, Reopen, Resume), until the last ends."""
        assert self.runner is not None
        try:
            while dashboard.controller is not None:
                await self.runner(dashboard.controller, dashboard)
                if not await dashboard.restarted():
                    break
        finally:
            dashboard.controller, dashboard.target = None, None  # shown as it was left, until resumed

    def working(self, besides: Dashboard | None = None) -> str:
        """Why work cannot start in another project than ``besides``: the project that works now ('' if none)."""
        for dashboard in self.dashboards.values():
            controller = getattr(dashboard, "controller", None)
            if dashboard is not besides and controller is not None and controller.state.status in WORKING:
                return f"{self.name(dashboard.project)} runs now: pause it first"
        return ""

    def describe(self, folder: Path, dashboard: Dashboard | None) -> dict:
        controller = dashboard.controller if isinstance(dashboard, ResearchDashboard) else None
        if controller is not None and controller.lock is not None:
            return _summary(controller.project.phase, controller.state.status, elsewhere=False)
        key = str(folder)
        stamp, described = self._described.get(key, (0.0, {}))
        if time.monotonic() - stamp > FRESH:
            described = self._stored(folder)
            self._described[key] = (time.monotonic(), described)
        return described

    @staticmethod
    def _stored(folder: Path) -> dict:
        project = Project(folder)
        if not project.started:
            return {"detail": "not started", "status": "waiting"}
        home = Home.load(project.home_file)
        number = home.active or home.latest or 1
        state = load_state(project.at(number))
        return _summary(number, state.status if state else NOT_STARTED, elsewhere=locked(project.lock_file))


def stored(project: Project) -> Options | None:
    """The options the project last ran with (its latest phase's), if it has run."""
    if not project.started:
        return None
    home = Home.load(project.home_file)
    state = load_state(project.at(home.latest or 1)) or load_state(project.at(home.active or 1))
    return state.options if state else None


def _summary(number: int, status: str, elsewhere: bool) -> dict:
    detail = f"phase {number} · {status.upper() if status in FINISHED else status}"
    return {
        "detail": detail + (" · elsewhere" if elsewhere else ""),
        "status": PHASE_COLOURS.get(status, "idle"),
        "running": status in WORKING and not elsewhere,
        "elsewhere": elsewhere,
    }
