"""The project folder: layout creation and checks, git commits, the human's files."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_sessions import Spec

from research_pipeline import project as project_module
from research_pipeline.project import Project, ProjectError
from research_pipeline.state import Agent, Options, State
from tests.helpers import remove, temp_project


class ProjectTest(unittest.TestCase):

    def setUp(self):
        self.root = temp_project()
        self.project = Project(self.root)
        self.project.prepare()
        self.agent = Agent('helper', 'subagent', 'primary', 'codex', 'gpt-test', 'high')
        (self.root / 'agents' / 'helper').mkdir()

    def tearDown(self):
        remove(self.root)

    def write(self, relative, text='x\n'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_commits_never_run_hooks_but_keep_the_humans_global_ignore_file(self):
        marker = self.root.parent / f'{self.root.name}-hook-ran'
        self.addCleanup(marker.unlink, missing_ok=True)
        hook = self.root / '.git' / 'hooks' / 'post-commit'  # as a job could plant it
        hook.write_text(f'#!/bin/sh\ntouch {marker}\n')
        hook.chmod(0o755)
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / 'ignore').write_text('*.swp\n')
            (Path(home) / '.gitconfig').write_text(f'[core]\n\texcludesFile = {home}/ignore\n')
            with patch.dict(os.environ, HOME=home):
                self.write('agents/helper/notes.md')
                self.write('agents/helper/notes.md.swp')
                self.project.commit('helper: notes')
        self.assertFalse(marker.exists())
        committed = self.project.git('ls-files').split()
        self.assertIn('agents/helper/notes.md', committed)
        self.assertNotIn('agents/helper/notes.md.swp', committed)
        self.assertEqual(self.project.git('log', '-1', '--format=%an').strip(), 'research-pipeline')

    def test_controller_writes_never_follow_a_symlink(self):
        outside = self.root.parent / f'{self.root.name}-outside.txt'
        outside.write_text('keep\n')
        self.addCleanup(outside.unlink)
        index = self.root / 'agents' / 'FOLDER_CONTENT.md'
        index.unlink(missing_ok=True)
        index.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.project.write_agents_index([self.agent])
        self.assertEqual(outside.read_text(), 'keep\n')

    def test_prepare_creates_layout_and_refuses_bad_locations(self):
        for name in ('STATUS.md', 'REPORT.md', 'FEEDBACK.md', 'FOLDER_CONTENT.md', '.gitignore', '.git'):
            self.assertTrue((self.root / name).exists(), name)
        self.assertEqual(self.project.check_layout(Agent('primary', 'primary', None, 'codex', 'gpt-test', 'high')), [])
        with self.assertRaises(ProjectError):
            Project('/tmp/somewhere').prepare()
        empty = temp_project()
        (empty / 'starting_evidence' / 'RESEARCH_QUESTIONS.md').unlink()
        with self.assertRaises(ProjectError):
            Project(empty).prepare()
        remove(empty)

    def test_layout_check_reports_missing_and_incomplete_indexes(self):
        self.write('agents/helper/notes.md')
        self.assertIn('agents/helper/FOLDER_CONTENT.md is missing', self.project.check_layout(self.agent))
        self.write('agents/helper/FOLDER_CONTENT.md', '- notes.md — notes\n')
        self.write('agents/helper/sub/data.csv')
        problems = self.project.check_layout(self.agent)
        self.assertEqual(problems, ['agents/helper/FOLDER_CONTENT.md does not describe: sub',
                                    'agents/helper/sub/FOLDER_CONTENT.md is missing'])

    def test_layout_check_exemptions_and_formats(self):
        self.write('agents/helper/FOLDER_CONTENT.md', '- draft.docx\n')
        self.write('agents/helper/draft.docx')
        self.write('agents/helper/.venv/lib/x.py')                 # hidden
        self.write('agents/helper/venv/lib/x.py')                  # git-ignored
        self.write('agents/helper/jobs/job-1/stdout.log')          # the controller's job output
        self.write('junk.txt')
        self.write('.obsidian/workspace.json')                     # hidden: the human's editor
        problems = self.project.check_layout(self.agent)
        self.assertEqual(problems, ['agents/helper/draft.docx: notes must be Markdown'])
        self.assertEqual(self.project.stray_entries(), ['junk.txt'])  # reported, never blocking

    def test_commit_skips_large_files(self):
        big = self.root / 'agents' / 'helper' / 'big.bin'
        with open(big, 'wb') as file:
            file.truncate(project_module.LARGE + 1)
        self.write('agents/helper/small.md')
        self.assertIsNotNone(self.project.commit('test: add files'))
        tracked = self.project.git('ls-files')
        self.assertIn('agents/helper/small.md', tracked)
        self.assertNotIn('big.bin', tracked)
        self.assertIn('agents/helper/big.bin', self.project.git('log', '-1', '--format=%B'))
        self.assertIsNone(self.project.commit('test: nothing'))

    def test_human_fingerprint_and_uncommitted(self):
        before = self.project.human_fingerprint()
        self.assertIn('starting_evidence/RESEARCH_QUESTIONS.md', before)
        self.write('AGENTS.md', 'Use SI units.\n')
        self.assertEqual(Project.changed(before, self.project.human_fingerprint()), ['AGENTS.md'])
        self.assertEqual(self.project.uncommitted(), ['AGENTS.md'])

    def test_agents_index_and_inventory(self):
        self.write('agents/helper/TASK.md', '# Verify the quadrature\n\nDetails.\n')
        self.project.write_agents_index([self.agent])
        self.assertIn('helper', (self.root / 'agents' / 'FOLDER_CONTENT.md').read_text())
        self.assertIn('Verify the quadrature', (self.root / 'agents' / 'FOLDER_CONTENT.md').read_text())
        self.assertIn('RESEARCH_QUESTIONS.md', self.project.inventory())


class StateTest(unittest.TestCase):

    def test_round_trip_and_specs(self):
        root = temp_project()
        try:
            state = State(options=Options(primary='claude:opus:high'))
            state.agents['primary'] = Agent('primary', 'primary', None, 'claude', 'opus', 'high', notices=['hi'])
            path = root / 'state.json'
            state.save(path)
            loaded = State.load(path)
            self.assertEqual(loaded.agents['primary'].notices, ['hi'])
            self.assertEqual(loaded.options.primary, 'claude:opus:high')
            self.assertFalse([name for name in os.listdir(root) if name.startswith('.state-')])
        finally:
            remove(root)
        self.assertEqual(Spec.parse('claude:opus:high'), Spec('claude', 'opus', 'high'))
        self.assertEqual(str(Spec.parse(' codex : gpt-test : low ')), 'codex:gpt-test:low')
        for incomplete in ('codex', 'claude:opus', 'codex::high', ':model:high', 'a:b:c:d'):
            with self.assertRaises(ValueError):
                Spec.parse(incomplete)


if __name__ == '__main__':
    unittest.main()
