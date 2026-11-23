"""Links in Markdown texts: which files the Librarian's pages reach, and links kept right when a text moves."""

import unittest

from research_pipeline import links
from tests.helpers import remove, temp_project


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.root = temp_project()
        for path in ("agents/fit/notes.md", "agents/fit/code/run.py", "agents/fit/my notes.md", "agents/b/Theory.md"):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text("x\n")
        (self.root / "library").mkdir()

    def tearDown(self):
        remove(self.root)

    def page(self, text: str, name: str = "page.md"):
        path = self.root / "library" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def by_name(self, name: str):
        return sorted(self.root.rglob(name))

    def test_link_forms_and_code(self):
        text = (
            '[a](one.md) ![fig](img/f.png "Figure") [b](<with space.md>) [c](https://example.org) [d](#top)\n'
            "[ref]: refs/r.md\n[[Theory]] [[Theory#Part|shown]]\n"
            "`[no](code.md)`\n```\n[no](fenced.md)\n```\n"
        )
        found = links.targets(text)
        self.assertIn(("one.md", False), found)
        self.assertIn(("img/f.png", False), found)
        self.assertIn(("<with space.md>", False), found)
        self.assertIn(("refs/r.md", False), found)
        self.assertIn(("Theory", True), found)
        self.assertNotIn(("code.md", False), found)
        self.assertNotIn(("fenced.md", False), found)

    def test_a_folder_link_covers_its_files_and_broken_links_are_listed(self):
        page = self.page(
            "[fit](../agents/fit/) [b](../agents/b/Theory.md#eq-3) [gone](../agents/fit/gone.md) "
            "[web](https://example.org) [spaced](../agents/fit/my%20notes.md)\n"
        )
        report = links.check([page], self.root, self.by_name)
        self.assertTrue(report.covers(self.root / "agents/fit/code/run.py"))
        self.assertTrue(report.covers(self.root / "agents/b/Theory.md"))
        self.assertFalse(report.covers(self.root / "agents/b/other.md"))
        self.assertEqual(report.broken, [(page, "../agents/fit/gone.md")])

    def test_wikilinks_resolve_by_path_or_by_name(self):
        page = self.page("[[Theory]] [[agents/fit/notes]] [[Missing]]\n", "sub/page.md")
        report = links.check([page], self.root, self.by_name)
        self.assertTrue(report.covers(self.root / "agents/b/Theory.md"))
        self.assertTrue(report.covers(self.root / "agents/fit/notes.md"))
        self.assertEqual([target for _, target in report.broken], ["Missing"])


class RebaseTest(unittest.TestCase):
    """A brief written in agents/fit/briefs/ and read as agents/child/TASK.md."""

    def setUp(self):
        self.root = temp_project()
        for path in (
            "agents/fit/NOTATION.md",
            "agents/fit/code/run.py",
            "agents/fit/my notes.md",
            "agents/fit/briefs/brief.md",
            "agents/fit/briefs/plan.md",
            "agents/child/plan.md",
            "library/LIBRARY.md",
        ):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text("x\n")
        self.source = self.root / "agents/fit/briefs"
        self.target = self.root / "agents/child"

    def tearDown(self):
        remove(self.root)

    def moved(self, text: str) -> links.Rebased:
        return links.rebase(text, self.source, self.target)

    def test_links_that_work_only_where_written_are_rewritten(self):
        moved = self.moved(
            "See [notation](../NOTATION.md#units), ![code](../code/) "
            "and the [library](../../../library/LIBRARY.md).\n"
            '[ref]: ../code/run.py "The run"\n'
            "[spaced](<../my notes.md>) [encoded](../my%20notes.md)\n"
        )
        self.assertEqual(
            moved.text,
            "See [notation](../fit/NOTATION.md#units), ![code](../fit/code/) "
            "and the [library](../../library/LIBRARY.md).\n"
            '[ref]: ../fit/code/run.py "The run"\n'
            "[spaced](<../fit/my notes.md>) [encoded](../fit/my%20notes.md)\n",
        )
        self.assertEqual((moved.nowhere, moved.ambiguous), ([], []))

    def test_links_written_for_the_new_folder_are_kept(self):
        text = "[notation](../fit/NOTATION.md) [library](../../library/LIBRARY.md)\n"
        moved = self.moved(text)
        self.assertEqual(moved.text, text)
        self.assertEqual((moved.nowhere, moved.ambiguous), ([], []))

    def test_links_that_cannot_be_settled_are_kept_and_listed(self):
        text = "[gone](gone.md) [plan](plan.md#step-2) [figures](figures/)\n"
        moved = self.moved(text)
        self.assertEqual(moved.text, text)
        self.assertEqual(moved.nowhere, ["gone.md", "figures/"])
        self.assertEqual(moved.ambiguous, ["plan.md#step-2"])

    def test_urls_anchors_absolute_paths_wikilinks_and_code_are_untouched(self):
        absolute = self.root / "agents/fit/NOTATION.md"
        text = (
            f"[web](https://example.org/a.md) [top](#top) [abs]({absolute}) [[NOTATION]]\n"
            "`[code](../NOTATION.md)`\n```\n[fenced](../NOTATION.md)\n```\n"
        )
        moved = self.moved(text)
        self.assertEqual(moved.text, text)
        self.assertEqual((moved.nowhere, moved.ambiguous), ([], []))


if __name__ == "__main__":
    unittest.main()
