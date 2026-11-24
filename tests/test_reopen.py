"""Reopening a phase from the web page after its end (PROJECT.md §4): the preparation offered again, its changes
and reverts, the reopening assistant, Reopen (only on changed objectives), and what a later run does with them."""

import asyncio
import unittest

from agent_toolkit.web import SettingsError

from research_pipeline.web import ResearchDashboard
from tests.helpers import (
    FAKE_DRIVERS,
    FakeSession,
    complete,
    launch_options,
    quit_after_the_end,
    remove,
    running,
    shelve_all,
    temp_project,
)
from tests.test_setup import scripted


def failing(view: dict) -> list[str]:
    return [check["label"] for check in view["checks"] if not check["ok"]]


def changes(view: dict) -> list[tuple[str, str]]:
    return [(change["path"], change["change"]) for change in view["changes"]]


class ReopenTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()
        self.results: list[dict] = []

    async def asyncTearDown(self):
        FakeSession.script = None
        remove(self.root)

    def page(self, harness) -> ResearchDashboard:
        """The web page of the harness's controller."""
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

    async def test_the_page_prepares_a_reopening_reverts_changes_and_its_reopen_restarts_the_primary(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness, shelve=False)
            dashboard = self.page(harness)
            view = self.view(dashboard)
            self.assertEqual((view["start"], view["ready"]), ("Reopen", False))
            self.assertEqual(view["title"], "Reopen phase 1: Phase 1 (COMPLETE)")
            self.assertEqual([d["path"] for d in view["documents"]], ["phases/1/OBJECTIVES.md", "AGENTS.md"])
            self.assertEqual(
                failing(view),
                ["The phase's objectives changed since its end", "The Librarian has placed the phase's final work"],
            )
            await shelve_all(harness)
            await harness.settle()
            controls = [control["label"] for control in dashboard.snapshot()["status"]["controls"]]
            self.assertEqual(controls, ["Prepare reopening", "Write report", "Project report", "Close"])
            with self.assertRaisesRegex(SettingsError, "Not ready: The phase's objectives changed"):
                await dashboard.start(dashboard.values())
            # Edits: a document saved on the page, new material placed; the program stays open, unalarmed.
            await self.save(dashboard, "AGENTS.md", "Check the error bars.")
            self.assertEqual(failing(self.view(dashboard)), ["The phase's objectives changed since its end"])
            (self.root / "data.csv").write_text("t,x\n0,1\n")
            entry = {"path": "data.csv", "folder": "starting_evidence", "description": "One run."}
            await dashboard.prepare("place", {"entries": [entry]})
            view = self.view(dashboard)
            self.assertEqual(
                changes(view),
                [
                    ("AGENTS.md", "added"),
                    ("starting_evidence/FOLDER_CONTENT.md", "modified"),
                    ("starting_evidence/data.csv", "added"),
                ],
            )
            self.assertIn("set aside", view["changes"][2]["revert"])
            await harness.controller._check_human()
            self.assertFalse([line for line in harness.lines if "run again" in line[2]])
            self.assertIn("use the web page", "\n".join(line[2] for line in harness.lines))
            # Reverting: the new file is set aside (with its index line), a changed one comes back as it was.
            await dashboard.prepare("revert", {"path": "starting_evidence/data.csv"})
            view = self.view(dashboard)
            self.assertEqual(changes(view), [("AGENTS.md", "added")])
            self.assertEqual([item["name"] for item in view["files"]["removed"]], ["data.csv"])
            with self.assertRaisesRegex(ValueError, "not changed since the end"):
                await dashboard.prepare("revert", {"path": "../outside.txt"})
            await dashboard.prepare("discard", {})
            self.assertEqual(changes(self.view(dashboard)), [])
            self.assertFalse((self.root / "AGENTS.md").exists())  # set aside, as it was new since the end
            # Reopen: the talk-only controller hands over, and the reopening one restarts the primary.
            await self.save(dashboard, "phases/1/OBJECTIVES.md", "Also derive the error bars.\n")
            self.assertTrue(self.view(dashboard)["ready"])
            await dashboard.start(dashboard.values() | {"max_agents": 5})
            assert harness.task is not None
            await asyncio.wait_for(harness.task, 5)
            self.assertIsNone(dashboard.preparation())
            self.assertFalse((self.root / ".research" / "setup" / "1").exists())
            self.assertTrue(await dashboard.restarted())
            reopened = dashboard.controller
            assert reopened is not None and reopened is not harness.controller
            task = asyncio.create_task(reopened.run())
            try:
                for _ in range(200):
                    await asyncio.sleep(0.02)
                    if "primary" in reopened.sessions:
                        break
                message = reopened.sessions["primary"].launch.message  # type: ignore[attr-defined]
                self.assertIn("reopened after it ended (COMPLETE)", message)
                self.assertIn("- phases/1/OBJECTIVES.md", message)
                state = reopened.state
                self.assertEqual((state.status, state.options.max_agents), ("running", 5))
                self.assertFalse(await dashboard.restarted())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_the_reopening_assistant_reads_the_talks_grills_and_revises_the_objectives(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness)
            activity = harness.controller.activity
            activity.add("primary", "message", "[human] Why 1/3?", sender="human")
            activity.add("primary", "message", "Because the integral of x^2 is x^3/3.")
            dashboard = self.page(harness)
            self.assertTrue(self.view(dashboard)["assistant"]["ideas"])
            switch = self.view(dashboard)["assistant"]["switch"]
            self.assertEqual((switch["on"], switch["locked"]), (True, False))
            self.assertIn("this phase's primary and Reviewer since its end (2 messages so far)", switch["note"])
            self.assertIn("What the talks settled", self.view(dashboard)["steps"][1]["prompt"])
            questions = [
                {
                    "question": "Extend to which power?",
                    "header": "Scope",
                    "options": [{"label": "x^3", "description": "."}, {"label": "x^n", "description": "."}],
                }
            ]
            loop = asyncio.get_running_loop()
            FakeSession.script = scripted(
                loop,
                {
                    "What I want from the reopened phase": ("ask", {"questions": questions}, "One question first."),
                    "My answers": ("write_objectives", {"text": "Derive the integral of x^n."}, "Wrote it."),
                    "Rewrite AGENTS.md": ("write_agents_md", {"text": "Cite every source."}, "Done."),
                },
                self.results,
            )
            await dashboard.prepare("ideas", {"text": "Generalise the result.", "grill": True})
            assert dashboard.preparing is not None
            await dashboard.preparing.assistant.wait()
            view = self.view(dashboard)
            self.assertFalse(view["assistant"]["ideas"])
            [session] = [s for s in FakeSession.instances if s.launch.agent == "setup"]
            self.assertIn("reopening assistant", session.launch.instructions)
            self.assertIn(".research/setup/1/TALKS.md", session.launch.instructions)
            for tool in ("write_agents_md", "write_objectives", "place", "ask"):
                self.assertIn(tool, session.launch.mcp["setup"].env["AGENT_TOOLKIT_TOOLS"])
            self.assertNotIn("write_feedback", session.launch.mcp["setup"].env["AGENT_TOOLKIT_TOOLS"])
            self.assertIn("Phase 1 ended: COMPLETE", session.sent[0])
            # The first message fixed the switch on, and handed over the talks with it.
            self.assertEqual((view["assistant"]["switch"]["on"], view["assistant"]["switch"]["locked"]), (True, True))
            self.assertIn("The human gives you their talks", "\n".join(session.sent))
            talks = (self.root / ".research" / "setup" / "1" / "TALKS.md").read_text()
            self.assertIn("phase 1 — The human to primary\n\nWhy 1/3?", talks)
            self.assertIn("Because the integral", talks)
            # A later talk is announced with the answers.
            activity.add("reviewer", "message", "[human] Was it checked?", sender="human")
            asked = view["questions"]
            answer = [{"choices": ["x^n"], "other": ""}]
            await dashboard.prepare("answer", {"id": asked["id"], "answers": answer})
            await dashboard.preparing.assistant.wait()
            self.assertIn("talked with the phase's primary or Reviewer since your last request", session.sent[-1])
            objectives = (self.root / "phases" / "1" / "OBJECTIVES.md").read_text()
            self.assertEqual(objectives, "Derive the integral of x^n.\n")
            self.assertTrue(self.view(dashboard)["ready"])
            # AGENTS.md only on request.
            await dashboard.prepare("message", {"text": "Rewrite AGENTS.md: cite every source."})
            await dashboard.preparing.assistant.wait()
            self.assertEqual((self.root / "AGENTS.md").read_text(), "Cite every source.\n")
            await dashboard.close()
            await quit_after_the_end(harness)

    async def test_with_the_page_a_later_run_keeps_prepared_changes_waiting_for_reopen(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness)
            (self.root / "phases" / "1" / "OBJECTIVES.md").write_text("Also the error bars.\n")
            await quit_after_the_end(harness)
        async with running(self.root, reopen=False) as harness:
            self.assertEqual(harness.state.status, "complete")
            self.assertNotIn("primary", harness.controller.sessions)
            self.assertEqual(harness.controller.human_changes(), ["phases/1/OBJECTIVES.md"])
            dashboard = self.page(harness)
            self.assertEqual(changes(self.view(dashboard)), [("phases/1/OBJECTIVES.md", "modified")])
            await dashboard.close()
            await quit_after_the_end(harness)
        async with running(self.root) as harness:  # without the page, the change reopens it
            self.assertEqual(harness.state.status, "running")
            self.assertIn("- phases/1/OBJECTIVES.md", harness.session("primary").launch.message)


if __name__ == "__main__":
    unittest.main()
