"""The project's links stay valid through a whole run (PROJECT.md §2, "Links").

A run on fake CLIs moves text the ways the controller does (a brief from a subfolder to TASK.md, a rejection's
feedback, the objectives into the primary's opening, index lines into the catalogue, the Librarian's pages); then
every Markdown file it left and every message its agents received are read for links that lead nowhere. A change
that moves text without keeping its links fails here, as long as this run exercises it: extend the run with any
new way the controller places text.
"""

import unittest
from pathlib import Path

from research_pipeline import links
from tests.helpers import FakeSession, remove, running, shelve_all, temp_project


def sent(harness, agent_id: str) -> str:
    return "\n".join(harness.session(agent_id).sent)


class LinkAuditTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        remove(self.root)

    def broken_in(self, text: str, folder: Path) -> list[str]:
        """The links of a message read in ``folder`` that lead nowhere (from the root, or from ``folder``)."""
        page = folder / "message.md"  # links resolve as from a file there; nothing is written
        broken = []
        for target, wiki in links.targets(text):
            path = links._resolve(page, target, wiki, self.root, lambda name: [])
            if not wiki and path is not None and not path.exists():
                broken.append(target)
        return broken

    async def test_no_link_of_a_whole_run_leads_nowhere(self):
        (self.root / "phases/1/OBJECTIVES.md").write_text(
            "Fit the data of [the evidence](../../starting_evidence/FOLDER_CONTENT.md).\n"
        )
        async with running(self.root) as harness:
            harness.write("phases/1/agents/primary/NOTATION.md", "# Notation\n")
            harness.write(
                "phases/1/agents/primary/briefs/fit.md",
                "# Fit\n\n## Prior work\n\nUse [the notation](../NOTATION.md) and "
                "[the evidence](/starting_evidence/FOLDER_CONTENT.md).\n",
            )
            reply = await harness.call(
                "primary", "spawn", task="briefs/fit.md", name="fit", backend="codex", model="gpt-test", effort="high"
            )
            self.assertNotIn("Kept as written", reply)
            fit = "phases/1/agents/fit"
            harness.write(f"{fit}/notes.md", "From [the task](/phases/1/agents/fit/TASK.md).\n")
            harness.write(f"{fit}/RESULT.md", "# Result\n\nFitted, see [the notes](/phases/1/agents/fit/notes.md).\n")
            harness.handoff("fit")
            harness.write(  # index lines as agents write them, one without the dash and linking a sibling
                f"{fit}/FOLDER_CONTENT.md",
                "# Folder contents\n\n- [RESULT.md](RESULT.md) answers the brief, from [the notes](notes.md).\n"
                "- [notes.md](notes.md) — Notes.\n- [TASK.md](TASK.md) — The task.\n"
                "- [HANDOFF.md](HANDOFF.md) — The handoff.\n",
            )
            await harness.emit("fit", "turn_ended", text="Done.")
            self.assertNotIn("link convention", sent(harness, "fit"))
            self.assertIn("was submitted", await harness.call("fit", "submit_result"))
            await harness.emit("fit", "turn_ended", text="Submitted.")
            await harness.call("primary", "reject", agent="fit", feedback="Check [the notation](NOTATION.md) first.")
            harness.write(f"{fit}/PARENT_FEEDBACK.md", (self.root / fit / "PARENT_FEEDBACK.md").read_text())
            harness.write(  # the agent's index now names the feedback too
                f"{fit}/FOLDER_CONTENT.md",
                (self.root / fit / "FOLDER_CONTENT.md").read_text()
                + "- [PARENT_FEEDBACK.md](PARENT_FEEDBACK.md) — It.\n",
            )
            self.assertIn("was submitted", await harness.call("fit", "submit_result"))
            await harness.emit("fit", "turn_ended", text="Submitted again.")
            self.assertIn("Accepted", await harness.call("primary", "accept", agent="fit"))
            await shelve_all(harness)
            messages = [
                (text, session.launch.cwd)
                for session in FakeSession.instances
                for text in [session.launch.message, *session.sent]
            ]
        skip = (".research", ".git", "starting_evidence")
        pages = [
            path
            for path in sorted(self.root.rglob("*.md"))
            if not any(part.startswith(".") or part in skip for part in path.relative_to(self.root).parts)
        ]
        self.assertIn(self.root / "library" / "catalog" / "phase-1" / "fit.md", pages)
        broken = links.check(pages, self.root, lambda name: []).broken
        self.assertEqual([(str(page.relative_to(self.root)), target) for page, target in broken], [])
        for text, folder in messages:
            self.assertEqual(self.broken_in(text, folder), [], text[:200])


if __name__ == "__main__":
    unittest.main()
