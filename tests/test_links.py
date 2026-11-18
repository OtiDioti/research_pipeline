"""Links in the Librarian's pages: which files they reach, and which lead nowhere."""

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


if __name__ == "__main__":
    unittest.main()
