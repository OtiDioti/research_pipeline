"""The Librarian and the library (PROJECT.md §2, "The library"), driven through fake CLI sessions.

Shelving catalogues and freezes a finished agent's folder; the Librarian links the
work from its pages, and ``shelved`` is refused until every file is reachable.
"""

import asyncio
import json
import unittest

from research_pipeline.controller import Controller
from research_pipeline.project import ProjectError
from tests.helpers import (
    FAKE_DRIVERS,
    FakeSession,
    launch_options,
    quit_after_the_end,
    remove,
    running,
    shelve_all,
    temp_project,
)


def sent(harness, agent_id: str) -> str:
    """Everything the agent's current session was sent (its opening message included), as one text."""
    session = harness.session(agent_id)
    return "\n".join([session.launch.message, *session.sent])


async def spawn(harness, name: str, parent: str = "primary", backend: str = "codex") -> str:
    harness.write(f"agents/{parent}/brief-{name}.md", f"# Check {name}\n\nDo it.\n")
    reply = await harness.call(
        parent, "spawn", task=f"brief-{name}.md", name=name, backend=backend, model="gpt-test", effort="high"
    )
    assert "Started subagent" in reply, reply
    return reply.split()[2]


async def accept(harness, name: str) -> str:
    """Spawn a subagent that submits a result, and accept it: its work is then shelved."""
    child = await spawn(harness, name)
    harness.write(f"agents/{child}/RESULT.md", "# Result\n\nFound it.\n")
    harness.write(f"agents/{child}/data/table.csv", "1,2\n")
    harness.index(f"agents/{child}/data", "table.csv")
    harness.handoff(child)
    harness.index(f"agents/{child}", "TASK.md", "RESULT.md", "HANDOFF.md", "data")
    assert "submitted" in await harness.call(child, "submit_result")
    assert "Accepted" in await harness.call("primary", "accept", agent=child)
    return child


async def wait_job(harness, reply: str) -> str:
    job = reply.split()[1]
    for _ in range(100):
        await asyncio.sleep(0.05)
        if harness.state.jobs[job].status != "running":
            break
    return harness.state.jobs[job].status


class LibrarianTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        remove(self.root)

    async def propose_and_agree(self, harness):
        harness.write("REPORT.md", "# Report\n\nThe integral is 1/3.\n")
        harness.handoff("primary")
        harness.index("agents/primary", "HANDOFF.md")
        await harness.call("primary", "complete")
        harness.write("reviews/1.md", "# Review\n\n1. Fine.\n")
        harness.index("reviews", "1.md")
        harness.handoff("reviewer")
        harness.index("agents/reviewer", "HANDOFF.md")
        return await harness.call("reviewer", "verdict", review="1.md", agree=True)

    async def test_accepted_work_is_catalogued_and_frozen_and_the_librarian_is_outside_the_cap(self):
        async with running(self.root, launch_options(max_agents=2)) as harness:
            child = await accept(harness, "fit")
            self.assertIn("librarian", harness.controller.sessions)  # started at its first request
            self.assertIn(f"Shelving request: {child}", sent(harness, "librarian"))
            catalogue = json.loads((self.root / ".research" / "library.json").read_text())
            self.assertIn(f"agents/{child}/data/table.csv", catalogue[child]["files"])
            self.assertEqual(catalogue[child]["files"][f"agents/{child}/RESULT.md"], "described.")
            self.assertIn(f"agents/{child}/RESULT.md", (self.root / "library" / "CATALOG.md").read_text())
            await spawn(harness, "next")  # primary and next fill the cap of 2; the Librarian's session is not counted
            for command in (f"echo x > ../{child}/new.txt", "echo x > ../../library/new.md"):
                reply = await harness.call("primary", "run_job", command=command, timeout_seconds=30)
                self.assertEqual(await wait_job(harness, reply), "failed", command)
            self.assertFalse((self.root / "agents" / child / "new.txt").exists())
            self.assertFalse((self.root / "library" / "new.md").exists())
            launch = harness.session("librarian").launch
            self.assertEqual(launch.writable, (self.root / "agents" / "librarian",))
            self.assertIn("You are librarian, the librarian", launch.instructions)
            self.assertNotIn("Doing the science", launch.instructions)

    async def test_write_page_writes_markdown_in_the_library_only(self):
        async with running(self.root) as harness:
            await accept(harness, "fit")
            refusals = {
                "notes.txt": "must end in .md",
                "../agents/x.md": "stays inside",
                "CATALOG.md": "written by the controller",
                ".hidden/x.md": "hidden",
            }
            for path, why in refusals.items():
                self.assertIn(why, await harness.call("librarian", "write_page", path=path, text="# x\n"), path)
            outside = self.root / "agents" / "primary"
            (self.root / "library" / "link").symlink_to(outside)
            self.assertIn("Refused", await harness.call("librarian", "write_page", path="link/x.md", text="# x\n"))
            self.assertFalse((outside / "x.md").exists())
            reply = await harness.call(
                "librarian", "write_page", path="library/topic/a.md", text="[x](../../nowhere.md)"
            )
            self.assertIn("Wrote library/topic/a.md", reply)
            self.assertIn("lead nowhere", reply)
            self.assertIn("Removed", await harness.call("librarian", "write_page", path="topic/a.md", text=""))
            self.assertFalse((self.root / "library" / "topic").exists())

    async def test_shelved_is_refused_until_every_file_is_reachable(self):
        async with running(self.root) as harness:
            child = await accept(harness, "fit")
            reply = await harness.call("librarian", "shelved", agent=child)
            self.assertIn(f"reachable from no page: agents/{child}/RESULT.md", reply)  # CATALOG.md does not count
            await harness.call(
                "librarian", "write_page", path="fits.md", text=f"[result](../agents/{child}/RESULT.md) [x](gone.md)\n"
            )
            reply = await harness.call("librarian", "shelved", agent=child)
            self.assertNotIn(f"no page: agents/{child}/RESULT.md", reply)
            self.assertIn(f"no page: agents/{child}/data/table.csv", reply)
            self.assertIn("leads nowhere: library/fits.md: gone.md", reply)
            self.assertIn("does not describe: fits.md", reply)
            await harness.call("librarian", "write_page", path="fits.md", text=f"[fit](../agents/{child}/)\n")
            index = (self.root / "library" / "FOLDER_CONTENT.md").read_text() + "- [fits.md](fits.md) — Fits.\n"
            await harness.call("librarian", "write_page", path="FOLDER_CONTENT.md", text=index)
            self.assertIn("Nothing else is pending", await harness.call("librarian", "shelved", agent=child))
            self.assertEqual(harness.state.shelving, [])
            self.assertIn(f"librarian: shelved {child}", harness.controller.project.git("log", "--oneline"))
            self.assertIn("no shelving request", await harness.call("librarian", "shelved", agent=child))
            await harness.emit("librarian", "turn_ended", text="Done.")
            self.assertEqual(harness.state.agents["librarian"].status, "resting")
            self.assertNotIn("You ended your turn", sent(harness, "librarian"))

    async def test_turn_end_commits_pages_and_reports_broken_links_once(self):
        async with running(self.root) as harness:
            await accept(harness, "fit")
            await harness.call("librarian", "write_page", path="draft.md", text="[x](missing.md)\n")
            await harness.emit("librarian", "turn_ended", text="")
            self.assertIn("librarian: library pages updated", harness.controller.project.git("log", "--oneline"))
            self.assertEqual(sent(harness, "librarian").count("lead nowhere; fix them"), 1)
            await harness.emit("librarian", "turn_ended", text="")
            self.assertEqual(sent(harness, "librarian").count("lead nowhere; fix them"), 1)

    async def test_an_idle_librarian_with_pending_work_is_nudged_then_alerts_the_human(self):
        async with running(self.root) as harness:
            child = await accept(harness, "fit")
            await harness.emit("librarian", "turn_ended", text="")
            self.assertIn(f"shelving requests are still pending: {child}", sent(harness, "librarian"))
            await harness.emit("librarian", "turn_ended", text="I am unsure.")
            self.assertTrue(any(kind == "alert" and "Librarian has stopped" in text for kind, _, text in harness.lines))
            self.assertEqual(harness.state.shelving, [child])
            self.assertEqual(harness.state.agents["librarian"].status, "running")  # it keeps its session

    async def test_a_cancelled_subtree_is_shelved_deepest_first(self):
        async with running(self.root) as harness:
            child = await spawn(harness, "fit")
            grandchild = await spawn(harness, "deep", parent=child)
            await harness.call("primary", "cancel", agent=child)
            self.assertEqual(harness.state.shelving, [grandchild, child])

    async def test_library_pages_changed_during_a_review_are_not_listed_to_the_primary(self):
        async with running(self.root) as harness:
            await accept(harness, "fit")
            harness.write("REPORT.md", "# Report\n")
            harness.handoff("primary")
            harness.index("agents/primary", "HANDOFF.md", "brief-fit.md")
            self.assertIn("with the Reviewer", await harness.call("primary", "complete"))
            await harness.call("librarian", "write_page", path="LIBRARY.md", text="# Library\n\nBy topic.\n")
            await harness.emit("librarian", "turn_ended", text="")
            harness.write("reviews/1.md", "# Review\n\n1. Missing a check.\n")
            harness.index("reviews", "1.md")
            harness.handoff("reviewer")
            harness.index("agents/reviewer", "HANDOFF.md")
            await harness.call("reviewer", "verdict", review="1.md", agree=False)
            text = "\n".join(harness.session("primary").sent)
            self.assertIn("disagrees with COMPLETE", text)
            self.assertNotIn("library/", text)

    async def test_the_end_waits_for_the_librarian_and_reopening_unfreezes_the_primary(self):
        async with running(self.root) as harness:
            self.assertIn("COMPLETE", await self.propose_and_agree(harness))
            self.assertEqual(list(harness.controller.sessions), ["librarian"])
            self.assertIn(self.root / "agents" / "primary", harness.controller.librarian.frozen())
            await shelve_all(harness)
            await quit_after_the_end(harness)
        (self.root / "FEEDBACK.md").write_text("Continue.\n")  # a change of the human's files reopens it
        async with running(self.root) as harness:
            self.assertEqual(harness.state.status, "running")
            self.assertNotIn(self.root / "agents" / "primary", harness.controller.librarian.frozen())
            self.assertNotIn("librarian", harness.controller.sessions)  # nothing is pending

    async def test_the_end_does_not_wait_for_a_held_librarian_whose_requests_wait_for_the_next_run(self):
        options = launch_options(librarian="claude:opus-test:high")
        async with running(self.root, options) as harness:
            harness.quota.remaining["claude"] = (80.0, 5.0)
            await harness.controller._check_quota()
            await self.propose_and_agree(harness)
            await quit_after_the_end(harness)
            self.assertEqual(harness.state.shelving, ["primary", "reviewer"])
        async with running(self.root, options) as harness:  # talk-only; the hold is read again
            await harness.settle(10)
            self.assertIn("Shelving request: primary", sent(harness, "librarian"))

    async def test_a_librarian_stalling_at_the_end_leaves_its_requests_for_the_next_run(self):
        async with running(self.root) as harness:
            await self.propose_and_agree(harness)
            for _ in range(2):
                await harness.emit("librarian", "turn_ended", text="")
            self.assertNotIn("librarian", harness.controller.sessions)
            await quit_after_the_end(harness)
            self.assertEqual(harness.state.shelving, ["primary", "reviewer"])

    async def test_projects_made_before_the_library_are_refused(self):
        (self.root / "sources").mkdir()
        controller = Controller(self.root, launch_options(), drivers=FAKE_DRIVERS, read_quota=lambda backend: [])
        with self.assertRaises(ProjectError) as raised:
            await controller.run()
        self.assertIn("predates the library", str(raised.exception))

    async def test_launch_needs_the_librarians_cli(self):
        controller = Controller(
            self.root, launch_options(librarian=""), drivers=FAKE_DRIVERS, read_quota=lambda backend: []
        )
        with self.assertRaises(ProjectError) as raised:
            await controller.run()
        self.assertIn("--librarian", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
