"""Confinement: real bwrap boundaries for agent sessions and for jobs."""
from pathlib import Path
import shutil
import subprocess
import unittest

from research_pipeline import confine
from tests.helpers import remove, temp_project


@unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap is not installed')
class ConfineTest(unittest.TestCase):

    def setUp(self):
        self.root = temp_project()
        for name in ('own', 'shared', 'other', '.research'):
            (self.root / name).mkdir()
        (self.root / 'file.md').write_text('original\n')
        (self.root / '.research' / 'state.json').write_text('{}\n')
        (self.root / 'personal.toml').write_text('secret = 1\n')

    def tearDown(self):
        remove(self.root)

    def execute(self, argv):
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)

    def session(self, script):
        return self.execute(confine.session(['sh', '-c', script], cwd=self.root / 'own',
                                        writable=[self.root / 'own', self.root / 'shared', self.root / 'file.md'],
                                        hidden=[self.root / '.research'], masked=[self.root / 'personal.toml']))

    def job(self, script):
        return self.execute(confine.job(['sh', '-c', script], cwd=self.root / 'own',
                                    read_only=[self.root / 'starting_evidence'], hidden=[self.root / '.research']))

    def test_a_session_writes_only_its_scope(self):
        self.session('echo a > a.txt; echo b > ../shared/b.txt; echo c > ../other/c.txt; '
                     'echo d > ../d.txt; echo edited >> ../file.md; cat ../file.md > read.txt')
        self.assertTrue((self.root / 'own' / 'a.txt').exists())
        self.assertTrue((self.root / 'shared' / 'b.txt').exists())
        self.assertFalse((self.root / 'other' / 'c.txt').exists())
        self.assertFalse((self.root / 'd.txt').exists())
        self.assertIn('edited', (self.root / 'file.md').read_text())  # a single file can be writable
        self.assertIn('original', (self.root / 'own' / 'read.txt').read_text())  # everything else is readable

    def test_hidden_folders_and_masked_files_look_empty(self):
        result = self.session('ls -A ../.research | wc -l; wc -c < ../personal.toml')
        self.assertEqual(result.stdout.split(), ['0', '0'])
        self.assertEqual((self.root / 'personal.toml').read_text(), 'secret = 1\n')  # untouched outside

    def test_tmp_and_processes_are_private_to_a_session(self):
        marker = 'research-pipeline-confine-test'
        result = self.session(f'echo x > /tmp/{marker}; ls /tmp; ps -e -o pid= | wc -l')
        self.assertIn(marker, result.stdout)
        self.assertFalse(list(Path('/tmp').glob(marker)))
        self.assertLess(int(result.stdout.split()[-1]), 10)  # its own process namespace

    def test_a_job_writes_everywhere_except_the_read_only_paths(self):
        result = self.job('echo a > ../other/a.txt; echo b > ../b.txt; echo c > ../starting_evidence/c.txt; '
                          'ls -A ../.research | wc -l; ps -e -o pid= | wc -l')
        self.assertTrue((self.root / 'other' / 'a.txt').exists())
        self.assertTrue((self.root / 'b.txt').exists())
        self.assertFalse((self.root / 'starting_evidence' / 'c.txt').exists())
        self.assertIn('Read-only file system', result.stderr)
        hidden_entries, processes = result.stdout.split()
        self.assertEqual(hidden_entries, '0')
        self.assertLess(int(processes), 10)  # its own process namespace


if __name__ == '__main__':
    unittest.main()
