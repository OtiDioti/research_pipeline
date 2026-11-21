"""Phases (PROJECT.md §2, "Phases"): a new phase from the web page, talks with another phase while one runs,
switching phases through a pause, and the notice of later phases, on fake CLIs."""

import asyncio
import unittest

from agent_toolkit.web import SettingsError

from research_pipeline import controller as controller_module
from research_pipeline.controller import Controller
from research_pipeline.phases import Home
from research_pipeline.web import ResearchDashboard
from tests.helpers import (
    FAKE_DRIVERS,
    FakeSession,
    complete,
    launch_options,
    remove,
    running,
    temp_project,
)
from tests.test_talks import talker, talks


def failing(view: dict) -> list[str]:
    return [check["label"] for check in view["checks"] if not check["ok"]]


async def started(controller: Controller) -> asyncio.Task:
    """Run ``controller`` until its primary has a session (or it waits talk-only)."""
    task = asyncio.create_task(controller.run())
    for _ in range(200):
        await asyncio.sleep(0.02)
        if "primary" in controller.sessions or task.done():
            break
    if task.done():
        task.result()
    return task


async def paused(controller: Controller) -> None:
    """The human's pause completes once the agents at work end their turn (as they would when told)."""
    await asyncio.sleep(0.05)
    for session in list(controller.sessions.values()):
        if session.busy:
            session.emit("turn_ended", text="")  # type: ignore[attr-defined]
    for _ in range(100):
        await asyncio.sleep(0.02)
        if controller.state.status == "paused":
            return


async def handed_off(controller: Controller, task: asyncio.Task) -> None:
    """A paused phase hands over: each session asked for its handoff saves it (as its agent would), then it ends."""
    for _ in range(250):
        if task.done():
            break
        for agent_id, session in list(controller.sessions.items()):
            if controller.state.agents[agent_id].handoff_reason and session.busy:
                folder = controller.project.agent_dir(agent_id)
                (folder / "HANDOFF.md").write_text(f"# Handoff\n\n{agent_id}: next, continue.\n")
                session.emit("turn_ended", text="")  # type: ignore[attr-defined]
        await asyncio.sleep(0.02)
    await asyncio.wait_for(task, 5)


class PhasesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()
        self.saved = (controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL)
        controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL = 0.02, 0.05
        self.tasks: list[asyncio.Task] = []

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        controller_module.WATCH_INTERVAL, controller_module.HUMAN_INTERVAL = self.saved
        FakeSession.script = None
        remove(self.root)

    def page(self, harness) -> ResearchDashboard:
        dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS, read_quota=harness.quota)
        dashboard.controller = harness.controller
        return dashboard

    @staticmethod
    def view(dashboard: ResearchDashboard) -> dict:
        view = dashboard.preparation()
        assert view is not None
        return view

    async def save(self, dashboard: ResearchDashboard, path: str, text: str) -> None:
        document = next(d for d in self.view(dashboard)["documents"] if d["path"] == path)
        await dashboard.prepare("save", {"path": path, "text": text, "version": document["version"]})

    async def next_controller(self, dashboard: ResearchDashboard) -> Controller:
        """The controller the page's Start, Reopen or Resume asked for, running."""
        self.assertTrue(await dashboard.restarted())
        controller = dashboard.controller
        assert controller is not None
        self.tasks.append(await started(controller))
        return controller

    async def test_a_new_phase_starts_a_fresh_primary_that_builds_on_an_earlier_one(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness)
            dashboard = self.page(harness)
            sidebar = dashboard.snapshot()["sidebar"]
            self.assertEqual([item["label"] for item in sidebar[0]["items"]], ["1. Phase 1"])
            self.assertEqual(sidebar[0]["items"][0]["detail"], "COMPLETE")
            reply = await dashboard.add("phases")
            self.assertEqual(reply["view"], "prepare")
            view = self.view(dashboard)
            self.assertEqual((view["title"], view["start"]), ("Prepare phase 2: Phase 2", "Start phase 2"))
            self.assertEqual([d["path"] for d in view["documents"]], ["phases/2/OBJECTIVES.md", "AGENTS.md"])
            self.assertEqual(failing(view), ["The objectives are written"])
            self.assertEqual((await dashboard.add("phases"))["view"], "prepare")  # one new phase at a time
            self.assertEqual(len(dashboard._home().phases), 2)
            with self.assertRaisesRegex(SettingsError, "Not ready: The objectives are written"):
                await dashboard.start(dashboard.values())
            await self.save(dashboard, "phases/2/OBJECTIVES.md", "Fit the measured gaps.\n")
            self.assertTrue(self.view(dashboard)["ready"])
            builds_on = next(field for field in dashboard.fields() if field.name == "builds_on")
            self.assertEqual(builds_on.options, ["none", "1"])
            await dashboard.start(dashboard.values() | {"title": "Fit the data", "builds_on": "1"})
            assert harness.task is not None
            await asyncio.wait_for(harness.task, 5)  # the ended phase's controller handed over
        second = await self.next_controller(dashboard)
        self.assertEqual((second.project.phase, second.state.status), (2, "running"))
        opening = second.sessions["primary"].launch.message  # type: ignore[attr-defined]
        self.assertIn("## Objectives of phase 2", opening)
        self.assertIn("Fit the measured gaps.", opening)
        self.assertIn("This is phase 2 of the project, Fit the data (phases/2/).", opening)
        self.assertIn("It builds on phase 1: start from that phase's REPORT.md and STATUS.md (phases/1/).", opening)
        self.assertIn("phase 1, Phase 1 (phases/1/): COMPLETE on", opening)
        self.assertIn("this is phase 2, in phases/2/", second.sessions["primary"].launch.instructions)  # type: ignore[attr-defined]
        self.assertIn(self.root / "phases" / "2" / "STATUS.md", second.sessions["primary"].launch.writable)  # type: ignore[attr-defined]
        self.assertIn(
            "A new phase of the investigation has started: phase 2, Fit the data",
            "\n".join(second.state.agents["librarian"].notices + [s for s in FakeSession.instances[-1].sent]),
        )
        index = (self.root / "phases" / "FOLDER_CONTENT.md").read_text()
        self.assertIn("- [1](1) — Phase 1: COMPLETE on", index)
        self.assertIn("- [2](2) — Fit the data: running. Builds on phase 1.", index)
        items = dashboard.snapshot()["sidebar"][0]["items"]
        self.assertEqual(
            [(item["id"], item["running"], item["selected"]) for item in items],
            [
                ("1", False, False),
                ("2", True, True),
            ],
        )
        # Phase 1's folders are read-only for phase 2's jobs.
        reply = await controller_module.Controller._tool_run_job(
            second, second.state.agents["primary"], command="echo x > ../../../1/STATUS.md", timeout_seconds=30
        )
        self.assertIn("Started", reply)
        for _ in range(250):
            await asyncio.sleep(0.02)
            if second.state.jobs["job-1"].status != "running":
                break
        self.assertEqual(second.state.jobs["job-1"].status, "failed")
        self.assertNotIn("x", (self.root / "phases" / "1" / "STATUS.md").read_text().splitlines())

    async def test_another_phase_can_be_talked_with_while_one_runs_and_switching_goes_through_a_pause(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness)
            dashboard = self.page(harness)
            await dashboard.add("phases")
            await self.save(dashboard, "phases/2/OBJECTIVES.md", "Fit the measured gaps.\n")
            await dashboard.start(dashboard.values())
            assert harness.task is not None
            await asyncio.wait_for(harness.task, 5)
        second = await self.next_controller(dashboard)
        # Phase 1, while phase 2 runs: its graph as it was left, talks with its primary, Reopen waits.
        self.assertEqual(await dashboard.select("phases", "1"), {"view": "graph", "text": ""})
        snapshot = dashboard.snapshot()
        self.assertEqual(snapshot["status"]["state"], "phase 1: complete")
        self.assertEqual(snapshot["status"]["summary"], "")  # the state says it all
        self.assertEqual([c["label"] for c in snapshot["status"]["controls"]], ["Prepare reopening", "Shut down"])
        nodes = {node["id"]: node for node in snapshot["graph"]["nodes"] if node["kind"] == "agent"}
        self.assertEqual((nodes["primary"]["actions"], nodes["librarian"]["actions"]), (["message"], []))
        answer = talker(asyncio.get_running_loop(), [])  # only talk sessions answer: the others are driven here
        FakeSession.script = lambda session, text: answer(session, text) if "-talk-" in str(session.launch.log) else []
        self.assertIn("talk only", await dashboard.act("message", "primary", {"text": "Why 1/3?"}) or "")
        await asyncio.gather(*second.talks.tasks.values())
        [talk] = talks("primary")
        self.assertEqual(talk.launch.cwd, self.root / "phases" / "1" / "agents" / "primary")
        self.assertIn(
            "phase 1 of an autonomous scientific investigation; that phase has ended (COMPLETE)",
            talk.launch.instructions,
        )
        self.assertIn("phases/1/REPORT.md", talk.sent[0])
        history = dashboard.history("primary", 50, None)
        self.assertIn("[human] Why 1/3?", [entry["text"] for entry in history])
        with self.assertRaisesRegex(ValueError, "does not run"):
            await dashboard.act("pause", None, {})
        await self.save(dashboard, "phases/1/OBJECTIVES.md", "Also the error bars.\n")
        self.assertEqual(failing(self.view(dashboard)), ["No other phase runs"])
        with self.assertRaisesRegex(SettingsError, "Not ready: No other phase runs"):
            await dashboard.start(dashboard.values())
        # Pausing phase 2 lets phase 1 reopen; phase 2's sessions save their handoffs first.
        await dashboard.select("phases", "2")
        await dashboard.act("pause", None, {})
        await paused(second)
        self.assertEqual(second.state.status, "paused")
        await dashboard.select("phases", "1")
        self.assertEqual(failing(self.view(dashboard)), [])
        await dashboard.start(dashboard.values())
        await handed_off(second, self.tasks.pop())
        self.assertEqual(second.state.status, "paused")
        first = await self.next_controller(dashboard)
        self.assertEqual((first.project.phase, first.state.status), (1, "running"))
        message = first.sessions["primary"].launch.message  # type: ignore[attr-defined]
        self.assertIn("reopened after it ended (COMPLETE)", message)
        self.assertIn("Since this phase last ran, the investigation went on in later phases:", message)
        self.assertIn("phase 2, Phase 2 (phases/2/): paused; its report: phases/2/REPORT.md", message)
        # Phase 2 is resumed from its handoffs once phase 1 is paused.
        await dashboard.select("phases", "2")
        with self.assertRaisesRegex(ValueError, "phase 1 is running: pause it first"):
            await dashboard.act("resume_phase", None, {})
        first.toggle_pause()
        await paused(first)
        self.assertIn("switching", await dashboard.act("resume_phase", None, {}) or "")
        await handed_off(first, self.tasks.pop())
        again = await self.next_controller(dashboard)
        self.assertEqual((again.project.phase, again.state.status), (2, "running"))
        opening = again.sessions["primary"].launch.message  # type: ignore[attr-defined]
        self.assertIn("primary: next, continue.", opening)  # its handoff
        self.assertNotIn("later phases", opening)  # phase 1 is earlier
        self.assertEqual(Home.load(self.root / ".research" / "project.json").active, 2)

    async def test_a_phase_reopens_only_on_a_change_of_its_objectives_and_the_library_spans_phases(self):
        async with running(self.root) as harness:
            await complete(harness)
            harness.controller.shutdown()
            assert harness.task is not None
            await asyncio.wait_for(harness.task, 5)
        home = Home.load(self.root / ".research" / "project.json")
        self.assertEqual((home.latest, home.shelving), (1, []))
        catalog = (self.root / "library" / "CATALOG.md").read_text()
        self.assertIn(
            "### Phase 1\n\n- [phases/1/agents/primary](catalog/phase-1/primary.md) (primary, finished", catalog
        )
        (self.root / "AGENTS.md").write_text("Cite every source.\n")
        async with running(self.root) as harness:  # without the page: not on AGENTS.md alone
            self.assertEqual(harness.state.status, "complete")
            harness.controller.shutdown()
            assert harness.task is not None
            await asyncio.wait_for(harness.task, 5)
        (self.root / "phases" / "1" / "OBJECTIVES.md").write_text("Also the error bars.\n")
        async with running(self.root) as harness:
            self.assertEqual(harness.state.status, "running")
            message = harness.session("primary").launch.message
            self.assertIn("- phases/1/OBJECTIVES.md", message)
            self.assertIn("- AGENTS.md", message)
            self.assertNotIn("later phases", message)
            self.assertEqual(harness.controller.home.shelving, [])


if __name__ == "__main__":
    unittest.main()
