"""The Writer (PROJECT.md §4, "Reports"): reports for the human, checked against the work, on fake CLIs."""

import asyncio
import unittest
from pathlib import Path
from unittest import mock

from agent_toolkit.testing import turn

from research_pipeline.stats.analysis import analyse
from research_pipeline.stats.sources import Source
from research_pipeline.web import ResearchDashboard
from research_pipeline.writer import MAX_ROUNDS
from tests.helpers import FAKE_DRIVERS, FakeSession, call_tool, complete, launch_options, remove, running, temp_project


def script(loop: asyncio.AbstractEventLoop, verdicts: list[str], questions: list[str]):
    """Fake Writers, checkers and talking primaries; every other session is left to the test.

    The Writer asks a primary each of ``questions`` first, then writes, compiles and submits its report; each
    checker gives the next of ``verdicts`` ('clean', or the text of its findings).
    """

    def play(session: FakeSession, text: str):
        agent, server = session.launch.agent, session.launch.mcp.get("research")
        out = Path(session.launch.cwd)

        def call(tool: str, **args) -> dict:
            return asyncio.run_coroutine_threadsafe(call_tool(server, tool, **args), loop).result(5)

        if agent == "primary" and "-talk-" in str(session.launch.log):
            return turn(0.1, text="It is 1/3: the quadrature in my notes agrees to 1e-12.")
        if agent in ("writer", "project-writer"):

            def write():
                if questions:
                    call("ask_primary", phase=1, question=questions.pop(0))
                    return
                if "[human] Thanks" in text:
                    return  # a question for the human, answered without a new report
                (out / "report.tex").write_text(f"\\section{{The integral}} It is $1/3$. % request {len(text)}\n")
                (out / "report.pdf").write_text("%PDF-1.5\n")
                call("submit_report")

            said = "Here is where the report stands."
            return [("text", {"text": said}), *turn(0.1, text=said, action=write)]
        if agent in ("checker", "project-checker"):

            def check():
                verdict = verdicts.pop(0) if verdicts else "clean"
                if verdict == "clean":
                    call("report_clean")
                    return
                checks = out / "checks"
                (checks / "findings.md").write_text(verdict + "\n")
                call("report_findings", file=f"/{out.relative_to(out.parents[1])}/checks/findings.md")

            return turn(0.1, text="Checked.", action=check)
        return []  # the investigation's own agents are driven by the test

    return play


class WriterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()
        self.latex = mock.patch("research_pipeline.writer.shutil.which", return_value="/usr/bin/latexmk")
        self.latex.start()  # the fake Writer compiles nothing: the machine's LaTeX does not matter

    def tearDown(self):
        self.latex.stop()
        FakeSession.script = None
        remove(self.root)

    async def written(self, controller, phase: int | None = 1) -> None:
        task = controller.writers.writers[phase].task
        assert task is not None
        await asyncio.wait_for(task, 10)

    def sessions(self, agent: str) -> list[FakeSession]:
        return [session for session in FakeSession.instances if session.launch.agent == agent]

    async def test_a_phase_that_ends_gets_its_report_written_checked_and_corrected(self):
        loop = asyncio.get_running_loop()
        FakeSession.script = script(loop, ["Section 1 calls the result exact: the work gives 1e-12."], ["How sure?"])
        async with running(self.root, launch_options(report_at_end=True)) as harness:
            self.assertTrue((self.root / "WRITING.md").is_file())  # the starter rules, at the first start
            self.assertIn("[WRITING.md](WRITING.md)", (self.root / "FOLDER_CONTENT.md").read_text())
            await complete(harness)
            controller = harness.controller
            await self.written(controller)
            writer = controller.writers.writers[1]
            report = self.root / "reports" / "phase-1"
            self.assertTrue((report / "report.pdf").is_file())
            self.assertEqual((writer.status, writer.detail), ("idle", "the report of phase 1 is written and checked"))
            # It asked the primary (a talk session), and got the answer as its next request.
            writers = self.sessions("writer")
            self.assertEqual(len(writers), 1)  # one session throughout: it continues with each request
            self.assertIn("[primary of phase 1] It is 1/3", "\n".join(writers[0].sent))
            self.assertIn("The Writer of the reports for the human asks about your work: How sure?", self.talk())
            # The first check found something; the Writer got it, corrected and submitted again; a fresh checker
            # (never the Writer's session) passed it, told what was found before and what the Writer replied.
            checkers = self.sessions("checker")
            self.assertEqual(len(checkers), 2)
            self.assertIn("Section 1 calls the result exact", "\n".join(writers[0].sent))
            self.assertIn("round 2 of at most 3", checkers[1].sent[0])
            self.assertIn(
                "The previous round's findings are in reports/phase-1/checks/findings.md", checkers[1].sent[0]
            )
            self.assertTrue(checkers[0].launch.writable[0].samefile(report / "checks"))
            self.assertTrue(writers[0].launch.writable[0].samefile(report))
            self.assertIn("/WRITING.md", writers[0].launch.instructions)
            self.assertIn("/phases/1/RESULT.md", writers[0].launch.instructions)
            # Committed, listed, and kept in the phase's activity for the page.
            self.assertIn("writer: the report of phase 1", harness.controller.project.git("log", "-1", "--format=%s"))
            self.assertIn("[reports](reports)", (self.root / "FOLDER_CONTENT.md").read_text())
            self.assertIn("[phase-1](phase-1)", (self.root / "reports" / "FOLDER_CONTENT.md").read_text())
            logged = (self.root / ".research" / "phases" / "1" / "activity" / "writer.jsonl").read_text()
            self.assertIn("Here is where the report stands.", logged)
            # The run's statistics count the Writer and its checker as agents of the phase.
            source = Source(self.root)
            source.refresh()
            records = analyse(source, "1").records
            self.assertEqual((records["writer"].agent.sessions, records["checker"].agent.sessions), (1, 2))
            self.assertEqual(records["checker"].parent, "writer")

    def talk(self) -> str:
        return "\n".join(
            "\n".join(session.sent) for session in self.sessions("primary") if "-talk-" in str(session.launch.log)
        )

    async def test_the_page_asks_for_reports_and_talks_with_the_writer(self):
        loop = asyncio.get_running_loop()
        FakeSession.script = script(loop, [], [])
        async with running(self.root) as harness:  # no report at the end: the page asks for it
            await complete(harness)
            dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS)
            dashboard.controller = controller = harness.controller
            labels = [control["label"] for control in dashboard.snapshot()["status"]["controls"]]
            self.assertEqual(labels, ["Prepare reopening", "Write report", "Project report", "Close"])
            self.assertEqual(await dashboard.act("report", None, {}), "The Writer writes the report of phase 1.")
            with self.assertRaisesRegex(ValueError, "still working"):
                await dashboard.act("report", None, {})
            await self.written(controller)
            nodes = {node["id"]: node for node in dashboard.snapshot()["graph"]["nodes"]}
            self.assertEqual((nodes["writer"]["role"], nodes["writer"]["actions"]), ("writer", ["message"]))
            self.assertEqual(nodes["checker"]["parent"], "writer")
            labels = [control["label"] for control in dashboard.snapshot()["status"]["controls"]]
            self.assertEqual(
                labels, ["Prepare reopening", "Update report", "Rewrite report", "Project report", "Close"]
            )
            # The human writes to it from its node: an answer, and no new report.
            self.assertEqual(
                await dashboard.act("message", "writer", {"text": "Thanks, which section?"}), "Sent to the Writer."
            )
            await self.written(controller)
            self.assertEqual(len(self.sessions("checker")), 1)
            self.assertIn("[human] Thanks, which section?", self.sessions("writer")[0].sent[-1])
            # A fresh rewrite, and the project's report, written beside it.
            await dashboard.act("report_fresh", None, {})
            await self.written(controller)
            self.assertIn("Start fresh", self.sessions("writer")[0].sent[-1])
            await dashboard.act("report_project", None, {})
            await self.written(controller, None)
            self.assertTrue((self.root / "reports" / "project" / "report.pdf").is_file())
            history = dashboard.history("project-writer", 50, None)
            self.assertTrue(history and all(entry["agent"] == "project-writer" for entry in history))

    async def test_discrepancies_left_after_the_last_round_go_to_the_human(self):
        loop = asyncio.get_running_loop()
        FakeSession.script = script(loop, ["Still wrong."] * MAX_ROUNDS, [])
        async with running(self.root) as harness:
            await complete(harness)
            await harness.controller.report(1)
            await self.written(harness.controller)
            writer = harness.controller.writers.writers[1]
            self.assertEqual(len(self.sessions("checker")), MAX_ROUNDS)
            self.assertIn(
                "has discrepancies left after 3 checks: see reports/phase-1/checks/findings.md", writer.detail
            )
            self.assertTrue(any(kind == "alert" and "discrepancies left" in text for kind, _, text in harness.lines))

    async def test_without_latex_no_report_is_written_and_the_page_says_why(self):
        async with running(self.root) as harness:
            await complete(harness)
            dashboard = ResearchDashboard(self.root, launch_options(), drivers=FAKE_DRIVERS)
            dashboard.controller = harness.controller
            with mock.patch("research_pipeline.writer.shutil.which", return_value=None):
                controls = {control["label"]: control for control in dashboard.snapshot()["status"]["controls"]}
                self.assertIn("latexmk", controls["Write report"]["waiting"])
                with self.assertRaisesRegex(ValueError, "LaTeX is not installed"):
                    await dashboard.act("report", None, {})
            self.assertFalse((self.root / "reports").exists())

    async def test_a_running_phase_has_no_report_yet_and_its_ids_stay_the_writers(self):
        async with running(self.root) as harness:
            with self.assertRaisesRegex(ValueError, "phase 1 is at work"):
                await harness.controller.report(1)
            self.assertNotEqual(harness.controller._new_id("writer"), "writer")


if __name__ == "__main__":
    unittest.main()
