"""Offline recovery checks against real Git clones; no inference or resume."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'development/handoff/restore_l5.py'
RUN = '20261113T063709_7f21ba4a'
BRANCH = 'cwi/' + RUN
HEAD = '2e3e7b3e95714e9aa08d84b1d11f7bea01707105'


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='handoff-restore-test-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'project with spaces'
        self.command('git', 'clone', '--quiet', '--shared', str(ROOT), str(self.repo))
        self.pipeline = self.repo / 'coding_pipeline'
        self.command('git', 'clone', '--quiet', '--shared', str(ROOT / 'coding_pipeline'),
                     str(self.pipeline))
        self.original_main = self.git('rev-parse', 'main')

    def command(self, *args, **kwargs):
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, **kwargs).strip()

    def git(self, *args):
        return self.command('git', '-C', str(self.repo), *args)

    def restore(self):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.repo)],
                              capture_output=True, text=True)

    def test_restored_run_is_discoverable_with_owned_unchanged_source(self):
        result = self.restore()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run = self.pipeline / 'logs' / RUN
        state = json.loads((run / 'state.json').read_text())
        self.assertEqual(state['target'], str(self.repo))
        self.assertEqual(state['run_dir'], str(run))
        self.assertEqual(state['worktree'], str(run / 'worktree'))
        self.assertEqual(state['commands'][0][0], sys.executable)
        self.assertEqual((state['status'], state['phase']), ('interrupted', 'final'))
        self.assertEqual(state['last_approved_commit'], HEAD)
        self.assertEqual(state['integration_attempt'], 3)
        self.assertEqual(state['sessions'], {})
        self.assertEqual(self.git('rev-parse', 'main'), self.original_main)
        self.assertEqual(self.git('rev-parse', BRANCH), HEAD)
        self.assertFalse(self.git('status', '--porcelain'))
        for key in ['baseline_test_path', 'final_test_path', 'current_diff_path', 'recovery_path']:
            self.assertTrue((run / state[key]).is_file(), key)
        self.assertTrue(Path(state['final']['results'][0]['output_path']).is_file())
        env = dict(os.environ, PYTHONPATH=str(self.pipeline), PYTHONDONTWRITEBYTECODE='1')
        code = ('import json,sys; from cwi.flow import Pipeline; from cwi.git import _source; '
                'p=Pipeline(); s=p.store(sys.argv[1]).read(); _source(s); '
                'print(json.dumps(p.discover(sys.argv[2])))')
        discovered = json.loads(self.command(sys.executable, '-c', code, RUN, str(self.repo), env=env))
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0]['status'], 'interrupted')
        self.assertTrue(discovered[0]['worktree_exists'])
        self.assertEqual(discovered[0]['head'], HEAD)

    def test_existing_run_is_preserved(self):
        run = self.pipeline / 'logs' / RUN
        run.mkdir(parents=True)
        marker = run / 'operator-notes.txt'
        marker.write_text('preserve existing work\n')
        result = self.restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already exists', result.stderr)
        self.assertEqual(marker.read_text(), 'preserve existing work\n')
        self.assertFalse((run / 'state.json').exists())

    def test_wrong_pipeline_revision_is_refused_before_restoration(self):
        self.command('git', '-C', str(self.pipeline), 'checkout', '--quiet', '--detach',
                     '6c7b4d48d559042f2a4f8d98114ca40c47cd6835')
        result = self.restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pipeline revision', result.stderr)
        self.assertFalse((self.pipeline / 'logs' / RUN).exists())

    def test_dirty_target_is_preserved(self):
        marker = self.repo / 'uncommitted-notes.txt'
        marker.write_text('human work\n')
        result = self.restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('clean', result.stderr)
        self.assertEqual(marker.read_text(), 'human work\n')
        self.assertFalse((self.pipeline / 'logs' / RUN).exists())


if __name__ == '__main__':
    unittest.main()
