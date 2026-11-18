"""The web setup before the first start: readiness checks, material, objectives and the setup assistant."""

import asyncio
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from agent_toolkit.testing import turn
from agent_toolkit.web import SettingsError

from research_pipeline import cli
from research_pipeline.project import Project
from research_pipeline.web import ResearchDashboard
from tests.helpers import FAKE_DRIVERS, TEST_ROOT, FakeSession, QuotaReader, call_tool, launch_options, remove


def empty_folder() -> Path:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=TEST_ROOT))


class ReadinessTest(unittest.TestCase):
    def setUp(self):
        self.root = empty_folder()
        self.project = Project(self.root)

    def tearDown(self):
        remove(self.root)

    def test_a_folder_is_ready_with_objectives_no_loose_material_and_described_evidence(self):
        self.assertIn("OBJECTIVES.md is missing", " ".join(self.project.unready()))
        (self.root / "starting_evidence").mkdir()
        (self.root / "starting_evidence" / "OBJECTIVES.md").write_text("  \n")
        (self.root / "paper.pdf").write_text("%PDF")
        problems = " ".join(self.project.unready())
        self.assertIn("is empty", problems)
        self.assertIn("Loose material at the top level, to place in starting_evidence/: paper.pdf", problems)
        self.assertIn("starting_evidence/FOLDER_CONTENT.md is missing", problems)
        (self.root / "starting_evidence" / "OBJECTIVES.md").write_text("# Objectives\n\nFind x.\n")
        (self.root / "paper.pdf").unlink()
        (self.root / "starting_evidence" / "FOLDER_CONTENT.md").write_text("- [OBJECTIVES.md](OBJECTIVES.md) — x\n")
        (self.root / "starting_evidence" / "deep").mkdir()
        (self.root / "starting_evidence" / "deep" / "FOLDER_CONTENT.md").write_text("an archive's own index\n")
        (self.root / "starting_evidence" / "deep" / "raw.txt").write_text("kept as it is")
        self.assertEqual(self.project.unready(), ["starting_evidence/FOLDER_CONTENT.md does not describe: deep."])
        (self.root / "starting_evidence" / "FOLDER_CONTENT.md").write_text(
            "- [OBJECTIVES.md](OBJECTIVES.md) — x\n- [deep](deep) — an archive\n"
        )
        self.assertEqual(self.project.unready(), [])  # deeper folders are the human's own
        # Once an investigation has started, loose files are strays for the primary, not a refusal.
        (self.root / "late.txt").write_text("x")
        self.assertNotEqual(self.project.unready(), [])
        self.project.research.mkdir()
        self.project.state_file.write_text("{}")
        self.assertEqual(self.project.unready(), [])

    def test_without_web_an_unready_folder_is_refused_with_the_hint(self):
        for target in (self.root, self.root / "new"):
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                status = cli.main(["run", str(target), "--no-tui", "--primary", "codex:m:high"])
            self.assertEqual(status, 2)
            self.assertIn("Run with --web to set the folder up", errors.getvalue())
        self.assertFalse((self.root / "new").exists())  # nothing is created without --web


def scripted(loop: asyncio.AbstractEventLoop, answers: dict, results: list):
    """A fake assistant: for a message containing a key of ``answers``, call that tool (or none) and reply.

    What its tool calls return is appended to ``results``.
    """

    def script(session: FakeSession, text: str):
        server = session.launch.mcp["setup"]
        for key, (tool, arguments, reply) in answers.items():
            if key in text:

                def act(tool=tool, arguments=arguments):
                    if tool:
                        future = asyncio.run_coroutine_threadsafe(call_tool(server, tool, **arguments), loop)
                        result = future.result(5)
                        results.append(result)

                return turn(0.1, text=reply, action=act)
        return turn(0.1, text="I did not understand.")

    return script


class PreparationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = empty_folder()
        self.outside = empty_folder()
        FakeSession.reset()
        self.results: list[dict] = []  # what the fake assistant's tool calls returned
        self.quota = QuotaReader()
        self.dashboard = ResearchDashboard(
            self.root,
            launch_options(setup="codex:gpt-test:high"),
            drivers=FAKE_DRIVERS,
            read_quota=self.quota,
        )

    async def asyncTearDown(self):
        if self.dashboard.preparing is not None:
            await self.dashboard.preparing.close()
        remove(self.root)
        remove(self.outside)
        FakeSession.script = None

    def view(self) -> dict:
        view = self.dashboard.preparation()
        assert view is not None
        return view

    async def answered(self) -> dict:
        await self.dashboard.preparing.assistant.wait()  # type: ignore[union-attr]
        return self.view()

    async def test_material_is_added_and_placed_by_hand_and_the_objectives_saved_against_their_version(self):
        (self.outside / "notes.txt").write_text("gaps: 1.1 eV")
        (self.outside / "code").mkdir()
        (self.outside / "code" / "fit.py").write_text("print(1)")
        await self.dashboard.prepare("import", {"paths": [str(self.outside / "notes.txt"), str(self.outside / "code")]})
        upload = self.dashboard.upload("papers/gap.pdf")
        upload.parent.mkdir(parents=True)
        upload.write_text("%PDF")  # the web app writes the body there
        for refused in ("../x", ".hidden", "agents/x", "starting_evidence/x", ""):
            with self.assertRaises(ValueError):
                self.dashboard.upload(refused)
        with self.assertRaisesRegex(ValueError, "exists already"):
            await self.dashboard.prepare("import", {"paths": [str(self.outside / "notes.txt")]})
        view = self.view()
        self.assertEqual(
            {e["path"] for e in view["files"]["entries"] if e["state"] == "loose"}, {"notes.txt", "code", "papers"}
        )
        self.assertFalse(view["ready"])
        # A new folder needs its own description; nothing moves while anything is refused.
        entries = [
            {"path": "notes.txt", "folder": "starting_evidence/notes", "description": "Measured gaps."},
            {"path": "code", "folder": "starting_evidence", "description": "The fitting code, kept whole."},
        ]
        with self.assertRaisesRegex(ValueError, "new folder starting_evidence/notes needs a one-line description"):
            await self.dashboard.prepare("place", {"entries": entries})
        self.assertTrue((self.root / "notes.txt").exists())
        folders = [{"path": "starting_evidence/notes", "description": "Notes on the measurements."}]
        await self.dashboard.prepare("place", {"entries": entries, "folders": folders})
        evidence = self.root / "starting_evidence"
        self.assertEqual((evidence / "notes" / "notes.txt").read_text(), "gaps: 1.1 eV")
        self.assertIn("- [notes](notes) — Notes on the measurements.", (evidence / "FOLDER_CONTENT.md").read_text())
        self.assertIn(
            "- [notes.txt](notes.txt) — Measured gaps.", (evidence / "notes" / "FOLDER_CONTENT.md").read_text()
        )
        placed = {e["path"]: e["description"] for e in self.view()["files"]["entries"] if e["state"] == "placed"}
        self.assertEqual(placed["starting_evidence/code"], "The fitting code, kept whole.")
        self.assertIn("starting_evidence/notes", self.view()["files"]["folders"])
        # The objectives: saved against the version the editor started from.
        document = self.view()["document"]
        await self.dashboard.prepare("save", {"text": "# Objectives\n\nFind the gap.", "version": document["version"]})
        with self.assertRaisesRegex(ValueError, "changed meanwhile"):
            await self.dashboard.prepare("save", {"text": "# Mine", "version": document["version"]})
        self.assertIn("[OBJECTIVES.md]", (evidence / "FOLDER_CONTENT.md").read_text())
        # Start waits for the checks (papers/ is still loose), then starts and keeps nothing of the setup.
        with self.assertRaisesRegex(SettingsError, "Loose material"):
            await self.dashboard.start(self.dashboard.values())
        entry = {"path": "papers", "folder": "starting_evidence", "description": "The papers."}
        await self.dashboard.prepare("place", {"entries": [entry]})
        self.assertTrue(self.view()["ready"])
        await self.dashboard.start(self.dashboard.values())
        self.assertIsNone(self.dashboard.preparation())
        self.assertFalse((self.root / ".research" / "setup").exists())
        self.assertEqual(self.dashboard.options.setup, "codex:gpt-test:high")

    async def test_the_assistant_organises_grills_and_drafts_through_its_tools(self):
        (self.root / "paper.pdf").write_text("%PDF")
        objectives = "# Objectives\n\n## 1. The gap\n\n- Kind: question\n- Statement: What is the gap?\n"
        questions = [
            {
                "question": "Which outcome matters?",
                "header": "Outcome",
                "options": [{"label": "A value", "description": "."}, {"label": "A method", "description": "."}],
            }
        ]
        place = {"entries": [{"path": "paper.pdf", "folder": "starting_evidence", "description": "The paper."}]}
        FakeSession.script = scripted(
            asyncio.get_running_loop(),
            {
                "Place the loose material": ("place", place, "Placed the paper."),
                "Grill me first": ("ask", {"questions": questions}, "A question first."),
                "My answers": ("write_objectives", {"text": objectives}, "Drafted; I chose a single objective."),
            },
            self.results,
        )
        await self.dashboard.prepare("organise", {})
        self.assertEqual(self.view()["assistant"]["state"], "busy")
        with self.assertRaisesRegex(ValueError, "still working"):
            await self.dashboard.prepare("draft", {})
        view = await self.answered()
        self.assertTrue((self.root / "starting_evidence" / "paper.pdf").exists())
        self.assertEqual(
            view["conversation"][-1], view["conversation"][-1] | {"sender": "assistant", "text": "Placed the paper."}
        )
        self.assertIn("starting_evidence/OBJECTIVES.md:\n\n(not written yet)", FakeSession.instances[0].sent[0])
        await self.dashboard.prepare("ideas", {"text": "Band gaps of perovskites.", "grill": True})
        view = await self.answered()
        asked = view["questions"]
        self.assertEqual(asked["items"][0]["options"][1]["label"], "A method")
        with self.assertRaisesRegex(ValueError, "no longer open"):
            await self.dashboard.prepare("answer", {"id": "old", "answers": []})
        answer = [{"choices": ["A value"], "other": "with its error"}]
        await self.dashboard.prepare("answer", {"id": asked["id"], "answers": answer})
        view = await self.answered()
        self.assertIsNone(view["questions"])
        self.assertIn("→ A value; other: with its error", FakeSession.instances[0].sent[-1])
        self.assertEqual(view["document"]["text"], objectives)
        self.assertTrue(view["ready"])
        self.assertEqual(len(FakeSession.instances), 1)  # one session served every request
        # A refused tool call is the agent's to fix: the reply names the problem.
        bad = {"entries": [{"path": "nothing.txt", "folder": "starting_evidence", "description": "x"}]}
        FakeSession.script = scripted(asyncio.get_running_loop(), {"again": ("place", bad, "Tried.")}, self.results)
        await self.dashboard.prepare("message", {"text": "Place it again."})
        await self.answered()
        self.assertTrue(self.results[-1]["error"])
        self.assertIn("not loose material", self.results[-1]["text"])

    async def test_a_quota_limit_or_a_failed_session_leaves_everything_doable_by_hand(self):
        (self.root / "paper.pdf").write_text("%PDF")
        self.quota.remaining["codex"] = (5.0, 80.0)
        with self.assertRaisesRegex(ValueError, "usage quota of codex is at its limit"):
            await self.dashboard.prepare("organise", {})
        await self.dashboard.prepare("assistant", {"spec": "claude:opus-test:high"})
        FakeSession.script = lambda session, text: turn(text="", failed=True)
        await self.dashboard.prepare("organise", {})
        view = await self.answered()
        self.assertEqual(view["assistant"]["state"], "unavailable")
        self.assertIn("could not answer", view["conversation"][-1]["text"])
        entry = {"path": "paper.pdf", "folder": "starting_evidence", "description": "The paper."}
        await self.dashboard.prepare("place", {"entries": [entry]})
        self.assertTrue((self.root / "starting_evidence" / "paper.pdf").exists())

    async def test_a_started_project_has_no_preparation_and_a_restart_keeps_the_conversation(self):
        (self.root / "paper.pdf").write_text("%PDF")
        FakeSession.script = lambda session, text: turn(0.1, text="Hello.")
        await self.dashboard.prepare("message", {"text": "Hi."})
        await self.answered()
        await self.dashboard.preparing.close()  # type: ignore[union-attr]
        again = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS, read_quota=self.quota)
        view = again.preparation()
        assert view is not None
        self.assertEqual([m["text"] for m in view["conversation"]], ["Hi.", "Hello."])
        await again.preparing.close()  # type: ignore[union-attr]
        Project(self.root).research.mkdir(exist_ok=True)
        Project(self.root).state_file.write_text("{}")
        started = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS)
        self.assertIsNone(started.preparation())
        with self.assertRaisesRegex(ValueError, "has started"):
            await started.prepare("rescan", {})
        shutil.rmtree(self.root / ".research")


if __name__ == "__main__":
    unittest.main()
