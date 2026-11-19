"""Reopening from the web page after the end (PROJECT.md §4): the preparation offered again, its changes and
reverts, the reopening assistant, Reopen, and what a later run does with prepared changes."""

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
            self.assertIn("(COMPLETE)", view["title"])
            self.assertEqual(
                [d["path"] for d in view["documents"]], ["FEEDBACK.md", "starting_evidence/OBJECTIVES.md", "AGENTS.md"]
            )
            self.assertEqual(
                failing(view), ["A file of yours changed since the end", "The Librarian has placed the final work"]
            )
            await shelve_all(harness)
            await harness.settle()
            controls = [control["label"] for control in dashboard.snapshot()["status"]["controls"]]
            self.assertEqual(controls, ["Prepare reopening", "Quit"])
            with self.assertRaisesRegex(SettingsError, "Not ready to reopen: A file of yours changed"):
                await dashboard.start(dashboard.values())
            # Edits: a document saved on the page, new material placed; the program stays open, unalarmed.
            await self.save(dashboard, "FEEDBACK.md", "Check the error bars.")
            (self.root / "data.csv").write_text("t,x\n0,1\n")
            entry = {"path": "data.csv", "folder": "starting_evidence", "description": "One run."}
            await dashboard.prepare("place", {"entries": [entry]})
            view = self.view(dashboard)
            self.assertEqual(
                changes(view),
                [
                    ("FEEDBACK.md", "modified"),
                    ("starting_evidence/FOLDER_CONTENT.md", "modified"),
                    ("starting_evidence/data.csv", "added"),
                ],
            )
            self.assertIn("set aside", view["changes"][2]["revert"])
            await harness.controller._check_human()
            self.assertFalse([line for line in harness.lines if "run again" in line[2]])
            self.assertIn("Prepare reopening on the web page", "\n".join(line[2] for line in harness.lines))
            # Reverting: the new file is set aside (with its index line), a changed one comes back as it was.
            await dashboard.prepare("revert", {"path": "starting_evidence/data.csv"})
            view = self.view(dashboard)
            self.assertEqual(changes(view), [("FEEDBACK.md", "modified")])
            self.assertEqual([item["name"] for item in view["files"]["removed"]], ["data.csv"])
            with self.assertRaisesRegex(ValueError, "not changed since the end"):
                await dashboard.prepare("revert", {"path": "../outside.txt"})
            await dashboard.prepare("discard", {})
            self.assertEqual((changes(self.view(dashboard)), (self.root / "FEEDBACK.md").read_text()), ([], ""))
            # Reopen: the talk-only controller hands over, and the reopening one restarts the primary.
            await self.save(dashboard, "FEEDBACK.md", "## Reopening 1 (2026-11-19)\n\nCheck the error bars.\n")
            self.assertTrue(self.view(dashboard)["ready"])
            await dashboard.start(dashboard.values() | {"max_agents": 5})
            assert harness.task is not None
            await asyncio.wait_for(harness.task, 5)
            self.assertIsNone(dashboard.preparation())
            self.assertFalse((self.root / ".research" / "setup").exists())
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
                self.assertIn("- FEEDBACK.md", message)
                self.assertIn("the section 'Reopening 1 (2026-11-19)' of FEEDBACK.md", message)
                state = reopened.state
                self.assertEqual((state.status, state.reopenings, state.options.max_agents), ("running", 1, 5))
                self.assertFalse(await dashboard.restarted())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_the_reopening_assistant_reads_the_talks_grills_and_writes_this_rounds_feedback(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness)
            activity = harness.controller.activity
            activity.add("primary", "message", "[human] Why 1/3?", sender="human")
            activity.add("primary", "message", "Because the integral of x^2 is x^3/3.")
            dashboard = self.page(harness)
            self.assertTrue(self.view(dashboard)["assistant"]["ideas"])
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
                    "What I want from the reopening": ("ask", {"questions": questions}, "One question first."),
                    "My answers": ("write_feedback", {"text": "Derive the integral of x^n."}, "Wrote it."),
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
            self.assertIn(".research/setup/TALKS.md", session.launch.instructions)
            for tool in ("write_feedback", "write_agents_md", "write_objectives", "place", "ask"):
                self.assertIn(tool, session.launch.mcp["setup"].env["AGENT_TOOLKIT_TOOLS"])
            self.assertIn("The investigation ended: COMPLETE", session.sent[0])
            talks = (self.root / ".research" / "setup" / "TALKS.md").read_text()
            self.assertIn("The human to primary\n\nWhy 1/3?", talks)
            self.assertIn("Because the integral", talks)
            # A later talk is announced with the answers.
            activity.add("reviewer", "message", "[human] Was it checked?", sender="human")
            asked = view["questions"]
            answer = [{"choices": ["x^n"], "other": ""}]
            await dashboard.prepare("answer", {"id": asked["id"], "answers": answer})
            await dashboard.preparing.assistant.wait()
            self.assertIn("talked with the primary or the Reviewer since your last request", session.sent[-1])
            feedback = (self.root / "FEEDBACK.md").read_text()
            self.assertRegex(feedback, r"^## Reopening 1 \(\d{4}-\d\d-\d\d\)\n\nDerive the integral of x\^n\.\n$")
            # Its section is rewritten in place; earlier text stays; AGENTS.md only on request.
            (self.root / "FEEDBACK.md").write_text("Older notes.\n\n" + feedback + "\n## Mine\n\nKeep this.\n")
            await dashboard.prepare("message", {"text": "Rewrite AGENTS.md: cite every source."})
            await dashboard.preparing.assistant.wait()
            self.assertEqual((self.root / "AGENTS.md").read_text(), "Cite every source.\n")
            FakeSession.script = scripted(
                loop, {"shorter": ("write_feedback", {"text": "Only x^3."}, "Shortened.")}, self.results
            )
            await dashboard.prepare("message", {"text": "Make it shorter."})
            await dashboard.preparing.assistant.wait()
            feedback = (self.root / "FEEDBACK.md").read_text()
            self.assertEqual(feedback.count("## Reopening 1"), 1)
            self.assertIn("Only x^3.\n\n## Mine\n\nKeep this.", feedback)
            self.assertTrue(feedback.startswith("Older notes."))
            self.assertTrue(self.view(dashboard)["ready"])
            await dashboard.close()
            await quit_after_the_end(harness)

    async def test_with_the_page_a_later_run_keeps_prepared_changes_waiting_for_reopen(self):
        async with running(self.root, reopen=False) as harness:
            await complete(harness)
            (self.root / "FEEDBACK.md").write_text("Also the error bars.\n")
            await quit_after_the_end(harness)
        async with running(self.root, reopen=False) as harness:
            self.assertEqual(harness.state.status, "complete")
            self.assertNotIn("primary", harness.controller.sessions)
            self.assertEqual(harness.controller.human_changes(), ["FEEDBACK.md"])
            dashboard = self.page(harness)
            self.assertEqual(changes(self.view(dashboard)), [("FEEDBACK.md", "modified")])
            await dashboard.close()
            await quit_after_the_end(harness)
        async with running(self.root) as harness:  # without the page, the change reopens it
            self.assertEqual(harness.state.status, "running")
            self.assertIn("- FEEDBACK.md", harness.session("primary").launch.message)


if __name__ == "__main__":
    unittest.main()
