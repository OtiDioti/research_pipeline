"""Talks after the end (PROJECT.md §4): talk-only sessions with the primary and the Reviewer, driven by fake CLIs."""

import asyncio
import unittest

from agent_toolkit.testing import turn

from research_pipeline.web import ResearchDashboard
from tests.helpers import (
    FAKE_DRIVERS,
    FakeSession,
    call_tool,
    launch_options,
    quit_after_the_end,
    remove,
    running,
    shelve_all,
    temp_project,
)

NOTE_REQUESTS = ("Save your talk note", "talk note was not saved")


def talker(loop: asyncio.AbstractEventLoop, fills: list[float]):
    """A fake talk session: it answers every message, saves its talk note when asked, and reports ``fills``."""

    def script(session: FakeSession, text: str):
        server = session.launch.mcp["research"]

        def act():
            if any(request in message for message in [text, *session.delivered] for request in NOTE_REQUESTS):
                note = f"Talked about: {text.splitlines()[-1]}"
                asyncio.run_coroutine_threadsafe(call_tool(server, "write_talk_note", note=note), loop).result(5)

        answer = f"Answer to {text.splitlines()[-1]}"
        return [("text", {"text": answer}), *turn(fills.pop(0) if fills else 0.1, text=answer, action=act)]

    return script


def talks(agent_id: str) -> list[FakeSession]:
    """The talk sessions of ``agent_id``, oldest first."""
    return [s for s in FakeSession.instances if s.launch.agent == agent_id and "-talk-" in str(s.launch.log)]


class TalksTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        FakeSession.script = None
        remove(self.root)

    async def end(self, harness) -> None:
        """COMPLETE, agreed by the Reviewer; the Librarian shelves the final work."""
        harness.write("REPORT.md", "# Report\n\nThe integral is 1/3.\n")
        harness.handoff("primary")
        harness.index("agents/primary", "HANDOFF.md")
        await harness.call("primary", "complete")
        harness.write("reviews/1.md", "# Review\n\n1. Fine.\n")
        harness.index("reviews", "1.md")
        harness.handoff("reviewer")
        harness.index("agents/reviewer", "HANDOFF.md")
        await harness.call("reviewer", "verdict", review="1.md", agree=True)
        await shelve_all(harness)
        await harness.settle()

    async def answered(self, harness, agent_id: str) -> None:
        await asyncio.gather(*harness.controller.talks.tasks.values())
        await harness.settle()

    async def test_after_the_end_the_primary_and_the_reviewer_answer_talk_only(self):
        async with running(self.root) as harness:
            await self.end(harness)
            controller, agents = harness.controller, harness.state.agents
            self.assertEqual([controller.actions(agents[name]) for name in agents], [["message"], ["message"], []])
            FakeSession.script = talker(asyncio.get_running_loop(), [])
            self.assertIn("talk only", await controller.act("message", "primary", "Why 1/3?"))
            await self.answered(harness, "primary")
            [talk] = talks("primary")
            self.assertEqual(talk.launch.writable, ())
            self.assertIn(self.root / ".research", talk.launch.hidden)
            self.assertIn("has ended (COMPLETE)", talk.launch.instructions)
            self.assertIn("Answer from the work", talk.launch.instructions)
            self.assertIn("write_talk_note", talk.launch.mcp["research"].env["AGENT_TOOLKIT_TOOLS"])
            self.assertNotIn("spawn", talk.launch.mcp["research"].env["AGENT_TOOLKIT_TOOLS"])
            for part in ("Your last handoff", "Next: continue.", "REPORT.md", "[human] Why 1/3?"):
                self.assertIn(part, talk.sent[0])
            self.assertIn(("agent", "primary", "Answer to [human] Why 1/3?"), harness.lines)
            controller.say("And the error?")  # the terminal's chat box talks with the primary
            await harness.settle()
            await self.answered(harness, "primary")
            self.assertEqual((len(talks("primary")), talk.sent[-1]), (1, "[human] And the error?"))
            dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS)  # the web page
            dashboard.controller = controller
            snapshot = dashboard.snapshot()
            self.assertEqual([control["label"] for control in snapshot["status"]["controls"]], ["Quit"])
            self.assertIn("has ended", snapshot["status"]["composer"]["label"])
            nodes = {node["id"]: node for node in snapshot["graph"]["nodes"]}
            self.assertEqual((nodes["reviewer"]["actions"], nodes["librarian"]["actions"]), (["message"], []))
            await dashboard.act("message", "reviewer", {"text": "Was it checked?"})
            await self.answered(harness, "reviewer")
            self.assertIn("reviews/1.md", talks("reviewer")[0].sent[0])
            with self.assertRaisesRegex(ValueError, "not possible"):
                await controller.act("message", "librarian", "Hello?")
            self.assertEqual((harness.state.status, agents["primary"].status), ("complete", "finished"))
            self.assertEqual(controller.project.uncommitted(), [])  # nothing was written in the project
            await quit_after_the_end(harness)  # each talk saves its note first
        self.assertIn("Talked about", (self.root / ".research" / "talks" / "primary.md").read_text())

    async def test_a_talk_continues_from_its_note_and_reopening_needs_a_change_of_the_humans_files(self):
        async with running(self.root) as harness:
            await self.end(harness)
            FakeSession.script = talker(asyncio.get_running_loop(), [0.9])  # the first answer fills the context
            await harness.controller.act("message", "primary", "First question?")
            await self.answered(harness, "primary")
            first, second = talks("primary")  # it saved its note and answered in a fresh session
            self.assertIn("Save your talk note", "\n".join(first.delivered))
            self.assertIn("Your talk note from your previous talk session", second.sent[0])
            self.assertIn("[human] First question?", second.sent[0])
            await quit_after_the_end(harness)
        async with running(self.root) as harness:  # nothing changed: talk-only again
            self.assertEqual(harness.state.status, "complete")
            self.assertNotIn("primary", harness.controller.sessions)
            FakeSession.script = talker(asyncio.get_running_loop(), [])
            await harness.controller.act("message", "primary", "Still there?")
            await self.answered(harness, "primary")
            self.assertIn("Talked about", talks("primary")[-1].sent[0])
            await quit_after_the_end(harness)
        (self.root / "FEEDBACK.md").write_text("Also check the error bars.\n")
        FakeSession.script = None
        async with running(self.root) as harness:  # the human's change reopens it; the talks are gone
            self.assertEqual(harness.state.status, "running")
            self.assertIn("reopened after it ended (COMPLETE)", harness.session("primary").launch.message)
            self.assertNotIn("Talked about", harness.session("primary").launch.message)
            self.assertFalse((self.root / ".research" / "talks").exists())

    async def test_changes_after_the_end_wait_for_the_next_run_and_a_held_cli_refuses_talks(self):
        async with running(self.root) as harness:
            await self.end(harness)
            (self.root / "FEEDBACK.md").write_text("More, please.\n")
            for _ in range(2):
                await harness.controller._check_human()
            alerts = [line for line in harness.lines if "run again to reopen" in line[2]]
            self.assertEqual((len(alerts), harness.state.status), (1, "complete"))
            harness.quota.remaining["codex"] = (5.0, 80.0)
            await harness.controller._check_quota()
            with self.assertRaisesRegex(ValueError, "usage quota of codex is held"):
                await harness.controller.act("message", "primary", "Quick question?")
            await quit_after_the_end(harness)


if __name__ == "__main__":
    unittest.main()
