"""The workbench: several projects in one page, one at work at a time, each shown as it was left once it stops."""

import asyncio
import fcntl
import shutil
import tempfile
import unittest
from pathlib import Path

from agent_toolkit.web import SettingsError

from research_pipeline import controller as controller_module
from research_pipeline.controller import Controller
from research_pipeline.phases import Home
from research_pipeline.project import Project
from research_pipeline.web import ResearchDashboard
from research_pipeline.workbench import ResearchWorkbench
from tests.helpers import FAKE_DRIVERS, FakeSession, QuotaReader, launch_options, remove, temp_project


def failing(dashboard: ResearchDashboard) -> list[str]:
    view = dashboard.preparation()
    assert view is not None
    return [check["label"] for check in view["checks"] if not check["ok"]]


async def until(condition, rounds: int = 250) -> None:
    for _ in range(rounds):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the condition never held")


class WorkbenchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.first, self.second = temp_project(), temp_project()
        FakeSession.reset()
        self.saved = controller_module.WATCH_INTERVAL
        controller_module.WATCH_INTERVAL = 0.02
        self.runs: list[Path] = []

        async def runner(controller: Controller, dashboard: ResearchDashboard) -> int:
            self.runs.append(dashboard.project)
            return await controller.run()

        self.workbench = ResearchWorkbench(self.home, runner=runner, drivers=FAKE_DRIVERS, read_quota=QuotaReader())

    async def asyncTearDown(self):
        dashboards = [item for item in self.workbench.dashboards.values() if isinstance(item, ResearchDashboard)]
        tasks = [dashboard.task for dashboard in dashboards if dashboard.task is not None]
        for task in tasks:  # forced, as a second Ctrl+C would: the fake agents never save their handoffs
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.workbench.close()
        controller_module.WATCH_INTERVAL = self.saved
        FakeSession.script = None
        for root in (self.first, self.second):
            remove(root)
        shutil.rmtree(self.home)

    async def open(self, root: Path) -> ResearchDashboard:
        self.workbench.options[str(root)] = launch_options()
        dashboard = await self.workbench.select(self.workbench.remember(root))
        assert isinstance(dashboard, ResearchDashboard)
        return dashboard

    async def test_one_project_works_at_a_time_and_a_shut_down_one_is_shown_as_it_was_left(self):
        first = await self.open(self.first)
        self.assertEqual((first.stage, failing(first)), ("setup", []))
        await first.start(first.values())
        await until(lambda: first.controller is not None and "primary" in first.controller.sessions)
        self.assertEqual(self.runs, [first.project])
        listed = {item["path"]: item for item in self.workbench.projects()}
        self.assertEqual(
            (listed[str(first.project)]["running"], listed[str(first.project)]["removable"]), (True, False)
        )
        self.assertEqual(self.workbench.projects()[0]["path"], str(first.project))  # started: on top

        # Meanwhile the other project can be set up, but not started.
        second = await self.open(self.second)
        self.assertEqual(failing(second), ["No other project runs"])
        with self.assertRaisesRegex(SettingsError, "No other project runs"):
            await second.start(second.values())

        # A phase renamed from the sidebar, while it runs.
        await first.rename("phases", "1", "Integrals")
        self.assertEqual(Home.load(Project(self.first).home_file).phases[0].title, "Integrals")
        self.assertIn("Integrals", (self.first / "phases" / "FOLDER_CONTENT.md").read_text())
        self.assertEqual(first.snapshot()["sidebar"][0]["items"][0]["rename"], "Integrals")

        # Shut down from the page: the agents hand off, the project stays shown, read-only, until resumed.
        controller = first.controller
        assert controller is not None
        await first.act("shutdown", None, {})
        await asyncio.sleep(0.1)
        (self.first / "phases" / "1" / "agents" / "primary" / "HANDOFF.md").write_text("# Handoff\n")
        controller.sessions["primary"].emit("turn_ended", text="")  # type: ignore[attr-defined]
        await until(lambda: first.controller is None and first.task is not None and first.task.done())
        self.assertEqual(first.stage, "running")
        snapshot = first.snapshot()
        self.assertEqual([control["action"] for control in snapshot["status"]["controls"]], ["resume_phase"])
        with self.assertRaisesRegex(ValueError, "resume the project first"):
            await first.act("message", "primary", {"text": "Hello?"})
        self.assertEqual(failing(second), [])  # the other project may start now

        # Resuming waits while the other project works.
        await second.start(second.values())
        await until(lambda: second.controller is not None and "primary" in second.controller.sessions)
        resume = first.snapshot()["status"]["controls"][0]
        self.assertIn("runs now: pause it first", resume["waiting"])
        with self.assertRaisesRegex(ValueError, "runs now"):
            await first.act("resume_phase", None, {})

    async def test_a_project_another_process_runs_is_read_only(self):
        Project(self.first).research.mkdir(exist_ok=True)
        Project(self.first).home_file.write_text("{}")
        with open(Project(self.first).lock_file, "w") as lock:  # held like another process's controller holds it
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            first = await self.open(self.first)
            (item,) = self.workbench.projects()
            self.assertEqual((item["elsewhere"], item["running"]), (True, False))
            self.assertTrue(first.elsewhere)
            snapshot = first.snapshot()
            self.assertEqual(snapshot["status"]["controls"], [])
            self.assertIn("another research_pipeline process", snapshot["status"]["summary"])
            with self.assertRaisesRegex(ValueError, "another process"):
                await first.act("message", "primary", {"text": "Hello?"})
            with self.assertRaisesRegex(ValueError, "rename it there"):
                self.workbench.rename(item["id"], "Elsewhere")
        self.assertEqual(self.runs, [])

    async def test_a_project_name_lives_in_the_project(self):
        ident = self.workbench.remember(self.first)
        self.workbench.rename(ident, "Integrals of x²")
        self.assertEqual((self.first / ".research" / "name").read_text(), "Integrals of x²\n")
        self.assertEqual(ResearchWorkbench(self.home).projects()[0]["label"], "Integrals of x²")


if __name__ == "__main__":
    unittest.main()
