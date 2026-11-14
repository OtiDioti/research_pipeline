"""Confinement: a real bwrap boundary leaves only the write scope writable and /tmp private."""
import shutil
import subprocess
import unittest

from research_pipeline import confine
from tests.helpers import remove, temp_project


@unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap is not installed')
class ConfineTest(unittest.TestCase):

    def setUp(self):
        self.root = temp_project()
        for name in ('own', 'shared', 'other'):
            (self.root / name).mkdir()
        (self.root / 'file.md').write_text('original\n')

    def tearDown(self):
        remove(self.root)

    def run_confined(self, script):
        argv = confine.command(['sh', '-c', script],
                               writable=[self.root / 'own', self.root / 'shared', self.root / 'file.md'],
                               cwd=self.root / 'own')
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)

    def test_only_the_write_scope_is_writable(self):
        self.run_confined('echo a > a.txt; echo b > ../shared/b.txt; echo c > ../other/c.txt; '
                          'echo d > ../d.txt; echo edited >> ../file.md; cat ../file.md > read.txt')
        self.assertTrue((self.root / 'own' / 'a.txt').exists())
        self.assertTrue((self.root / 'shared' / 'b.txt').exists())
        self.assertFalse((self.root / 'other' / 'c.txt').exists())
        self.assertFalse((self.root / 'd.txt').exists())
        self.assertIn('edited', (self.root / 'file.md').read_text())  # a single file can be writable
        self.assertIn('original', (self.root / 'own' / 'read.txt').read_text())  # everything is readable

    def test_tmp_and_processes_are_private(self):
        marker = 'research-pipeline-confine-test'
        result = self.run_confined(f'echo x > /tmp/{marker}; ls /tmp; ps -e -o pid= | wc -l')
        self.assertIn(marker, result.stdout)
        self.assertFalse(list(__import__('pathlib').Path('/tmp').glob(marker)))
        self.assertLess(int(result.stdout.split()[-1]), 10)  # its own process namespace


if __name__ == '__main__':
    unittest.main()
