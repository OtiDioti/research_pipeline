"""Setup-only fixtures for tiny standalone validator processes; no repository-suite recursion."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

VALIDATOR = Path(__file__).resolve().parents[1] / 'scripts' / 'validate.py'
PASSING = '''import unittest
class Example(unittest.TestCase):
    """A disposable successful case."""
    def test_body(self):
        """Prove genuine execution."""
        self.assertEqual(2 + 2, 4)
'''


def load_validator():
    """Load the self-contained script inertly without registering it in sys.modules."""
    spec = importlib.util.spec_from_file_location('isolated_validator', VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CandidateFixture:
    """Build candidate source and external evidence paths without inheriting test methods."""

    def setUp(self):
        """Create a tiny documented package and copy only the production entrypoint."""
        temporary = tempfile.TemporaryDirectory(prefix='validation-case-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / 'candidate'
        self.root.mkdir()
        for name in ('project_description.md', 'README.md', 'AGENTS.md'):
            (self.root / name).write_text('Disposable source.\n')
        package = self.root / 'implementation' / 'src' / 'research_pipeline'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('"""Disposable package."""\n')
        self.tests = self.root / 'implementation' / 'tests'
        self.tests.mkdir()
        (self.tests / '__init__.py').write_text('"""Disposable tests."""\n')
        self.script = self.root / 'implementation' / 'scripts' / 'validate.py'
        self.script.parent.mkdir()
        shutil.copyfile(VALIDATOR, self.script)
        self.write('test_example.py', PASSING)

    def write(self, name, source):
        """Install a fixture test/helper before taking immutable-source snapshots."""
        (self.tests / name).write_text(source)

    def snapshot(self):
        """Record candidate bytes, directories and permission modes without following links."""
        return {str(path.relative_to(self.root)): (path.lstat().st_mode,
                os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None)
                for path in self.root.rglob('*')}

    def command(self, sequential=False, prelude=''):
        """Return a fresh-interpreter command and candidate-local no-bytecode environment."""
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        environment.pop('PYTHONPATH', None)
        if not prelude:
            command = [sys.executable, '-B', str(self.script)]
            if sequential:
                command.append('--sequential')
        else:
            program = '''import importlib.util, sys
spec = importlib.util.spec_from_file_location('fixture_validator', sys.argv[1])
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
''' + prelude + f'\nraise SystemExit(v.run_validation(sys.argv[2], sys.stdout, sequential={sequential!r}))\n'
            command = [sys.executable, '-B', '-c', program, str(self.script), str(self.root)]
        return command, environment

    def validate(self, expected=0, *, sequential=False, prelude='', timeout=30):
        """Run the complete disposable suite and assert status plus source immutability."""
        before = self.snapshot()
        command, environment = self.command(sequential, prelude)
        result = subprocess.run(command, env=environment, cwd=self.parent,
                                capture_output=True, text=True, timeout=timeout)
        output = result.stdout + result.stderr
        self.assertEqual(before, self.snapshot(), 'validator mutated candidate source')
        self.assertEqual(expected, result.returncode, output)
        return output

    def inventories(self, output):
        """Extract comparable full ordered ID inventories and their independently checked hashes."""
        validator = load_validator()
        result = {}
        for line in output.splitlines():
            if line.startswith('Inventory '):
                prefix, encoded = line.split(' ids=', 1)
                name, digest = prefix[len('Inventory '):].split(': sha256=')
                ids = json.loads(encoded)
                self.assertEqual(digest, validator.inventory_digest(ids))
                result[name] = ids
        return result

    def dispositions(self, output):
        """Read the complete per-leaf dispositions independently of unittest count lines."""
        return [json.loads(line[len('Disposition: '):]) for line in output.splitlines()
                if line.startswith('Disposition: ')]


def four_cpu_sample():
    """Exercise concurrent planning with a synthetic A while preserving actual OS affinity.

    Even a one-CPU outer worker can prove process overlap through blocked gates.
    The assigned subset never broadens its inherited mask or changes host limits.
    """
    return '''
actual = sorted(v.os.sched_getaffinity(0))
if not actual:
    raise RuntimeError('overlap fixture needs a nonempty actual CPU mask')
def fixture_sample():
    """Use a subset of real allowed CPUs without altering OS limits."""
    return dict(A=4, allowed=actual, bounds=[('fixture', 4)], limitations=[], observations=[])
v.sample_resources = fixture_sample
'''
