"""Test the real validator on tiny disposable suites, never recursively on this suite."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "validate.py"
PASSING = '''import unittest
class Example(unittest.TestCase):
    """Disposable arithmetic case proving execution."""
    def test_body(self):
        """Emit evidence from inside an executed test."""
        print("FIXTURE BODY EXECUTED", flush=True)
        self.assertEqual(2 + 2, 4)
'''


class ValidatorTests(unittest.TestCase):
    """Use fresh interpreters to isolate candidate package and unittest module caches."""

    def setUp(self):
        """Create a minimal valid root, package, and passing suite for each case."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "candidate"
        self.root.mkdir()
        for name in ("project_description.md", "README.md", "AGENTS.md"):
            (self.root / name).write_text("Required documentation.\n", encoding="utf-8")
        package = self.root / "implementation" / "src" / "research_pipeline"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text('"""Fixture identity."""\n__version__ = "fixture"\n')
        self.tests = self.root / "implementation" / "tests"
        self.tests.mkdir()
        (self.tests / "__init__.py").write_text('"""Fixture tests."""\n')
        self.module = self.tests / "test_example.py"
        self.module.write_text(PASSING)

    def snapshot(self):
        """Record fixture entry types and bytes without following symlinks."""
        result = {}
        for path in sorted(self.root.rglob("*")):
            key = str(path.relative_to(self.root))
            if path.is_symlink():
                result[key] = ("link", os.readlink(path))
            elif path.is_file():
                result[key] = ("file", path.read_bytes())
            else:
                result[key] = ("directory", None)
        return result

    def validate(self, expected=0, script=VALIDATOR, entrypoint=False, prelude=""):
        """Run a fixture validation, assert status and unchanged source, and return diagnostics."""
        before = self.snapshot()
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment.pop("PYTHONPATH", None)
        program = '''
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("fixture_validator", sys.argv[1])
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
'''
        # Only injected fixture roots are validated here: the full suite must not recurse.
        program += prelude + '\nraise SystemExit(validator.run_validation(sys.argv[2], sys.stdout))\n'
        arguments = [str(script)] if entrypoint else ["-c", program, str(script), str(self.root)]
        result = subprocess.run(
            [sys.executable, "-B", *arguments], cwd=self.temporary.name,
            env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(self.snapshot(), before, "validation changed fixture source or directory contents")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, expected, output)
        return output

    def test_passing_suite(self):
        """A successful fixture executes its body and reports candidate origin and counts."""
        output = self.validate()
        self.assertIn("FIXTURE BODY EXECUTED", output)
        self.assertIn("discovered=1 testsRun=1 successful=1", output)
        self.assertIn(str(self.root / "implementation/src/research_pipeline/__init__.py"), output)
        self.assertIn("Source revision: unavailable (", output)

    def test_suite_outcomes(self):
        """Unsuccessful and mixed suites retain precise accounting and useful diagnostics."""
        cases = [
            ("empty", "", 1, "discovered=0 testsRun=0 successful=0"),
            ("skipped", '@unittest.skip("fixture skip")\n', 1, "successful=0 skipped=1"),
            ("expected", "@unittest.expectedFailure\n", 1, "expected_failures=1"),
            ("failure", "self.fail('ordinary failure')", 1, "failures=1 errors=0"),
            ("error", "raise RuntimeError('runtime error')", 1, "failures=0 errors=1"),
            ("syntax", "not valid python !!!", 1, "Discovery error:"),
            ("import", "import nonexistent_fixture_dependency", 1, "Discovery error:"),
            ("unexpected", "@unittest.expectedFailure\n", 1, "unexpected_successes=1"),
            ("subtests", 'with self.subTest(value=1):\n            self.fail("subtest failure")', 1,
             "successful=0 skipped=0 expected_failures=0 failures=1"),
        ]
        for name, body, status, diagnostic in cases:
            with self.subTest(outcome=name):
                if name == "empty":
                    source = ""
                elif name in ("syntax", "import"):
                    source = body
                elif name in ("skipped", "expected", "unexpected"):
                    assertion = "self.fail('expected failure')" if name == "expected" else "self.assertTrue(True)"
                    source = ('import unittest\nclass Example(unittest.TestCase):\n'
                              '    """Fixture outcome."""\n    ' + body +
                              '    def test_body(self):\n        """Exercise decorated outcome."""\n        ' + assertion)
                else:
                    source = ('import unittest\nclass Example(unittest.TestCase):\n'
                              '    """Fixture outcome."""\n    def test_body(self):\n'
                              '        """Exercise requested failure."""\n        ' + body)
                self.module.write_text(source)
                output = self.validate(status)
                self.assertIn(diagnostic, output)
                if name not in ("skipped", "empty"):
                    self.assertIn("test_body" if name not in ("syntax", "import") else "test_example", output)
        self.module.write_text(PASSING + '''
class Mixed(unittest.TestCase):
    """Fixture non-success cases beside a passing case."""
    @unittest.skip("fixture skip")
    def test_skip(self):
        """Never execute this skipped body."""
        self.fail("should be skipped")
    @unittest.expectedFailure
    def test_expected(self):
        """Retain expected failure without counting it as positive coverage."""
        self.fail("expected")
''')
        self.assertIn("discovered=3 testsRun=3 successful=1 skipped=1 expected_failures=1", self.validate())

    def test_missing_tests(self):
        """Missing discovery package marker or entire test directory cannot pass."""
        (self.tests / "__init__.py").unlink()
        self.assertIn("tests did not run", self.validate(1))
        shutil.rmtree(self.tests)
        self.assertIn("Missing test suite", self.validate(1))

    def test_layout_entries(self):
        """Directories and exact Markdown suffixes pass; forbidden files and links fail."""
        (self.root / "extra.md").write_text("allowed")
        (self.root / "directory").mkdir()
        self.validate()
        for name, target in (("bad.txt", None), ("bad.MD", None), ("file.md", "extra.md"),
                             ("directory-link", "directory"), ("dangling.md", "missing"),
                             (".git", "directory")):
            with self.subTest(entry=name):
                path = self.root / name
                if target is None:
                    path.write_text("forbidden")
                else:
                    path.symlink_to(target)
                output = self.validate(1)
                self.assertIn(str(path), output)
                self.assertIn("tests did not run", output)
                path.unlink()
        fifo = self.root / "special.md"
        os.mkfifo(fifo)
        self.assertIn(str(fifo), self.validate(1))
        fifo.unlink()

    def test_required_documents(self):
        """Missing, empty, non-UTF-8, directory, and symlink documents fail with paths."""
        for name in ("project_description.md", "README.md", "AGENTS.md"):
            path = self.root / name
            for kind in ("missing", "empty", "malformed", "directory", "symlink"):
                with self.subTest(document=name, kind=kind):
                    path.unlink()
                    if kind == "empty":
                        path.write_text(" \n\t")
                    elif kind == "malformed":
                        path.write_bytes(b"\xff")
                    elif kind == "directory":
                        path.mkdir()
                    elif kind == "symlink":
                        path.symlink_to(self.module)
                    self.assertIn(str(path), self.validate(1))
                    if path.is_dir():
                        path.rmdir()
                    elif path.exists() or path.is_symlink():
                        path.unlink()
                    path.write_text("restored document")

    def make_git_admin(self, directory):
        """Construct minimal disposable Git administration without commits or Git mutations."""
        directory.mkdir(parents=True)
        (directory / "objects").mkdir()
        (directory / "refs").mkdir()
        (directory / "HEAD").write_text("ref: refs/heads/main\n")

    def test_git_administration(self):
        """Allow normal Git directories and resolver-approved relative and absolute pointers."""
        git = self.root / ".git"
        self.make_git_admin(git)
        self.validate()
        shutil.rmtree(git)
        admin = self.root / "administration" / "worktree"
        self.make_git_admin(admin)
        for target in ("administration/worktree", str(admin)):
            git.write_text(f"gitdir: {target}\n")
            self.validate()
        for pointer in ("", "gitdir: ", "not a pointer", "gitdir: absent", "gitdir: implementation",
                        "gitdir: administration/worktree\nextra"):
            with self.subTest(pointer=pointer):
                git.write_text(pointer)
                self.assertIn("invalid Git pointer", self.validate(1))

    def test_origin_rejection(self):
        """A preloaded foreign package is rejected rather than mistaken for candidate code."""
        prelude = '''
import types
foreign = types.ModuleType("research_pipeline")
foreign.__file__ = "/foreign/research_pipeline/__init__.py"
sys.modules["research_pipeline"] = foreign
'''
        self.assertIn("Import-origin failure", self.validate(1, prelude=prelude))

    def test_discovery_exception(self):
        """A broken load_tests hook produces actionable discovery failure diagnostics."""
        (self.tests / "__init__.py").write_text('''
def load_tests(loader, tests, pattern):
    """Simulate a discovery hook failure."""
    raise RuntimeError("fixture discovery hook failed")
''')
        output = self.validate(1)
        self.assertIn("fixture discovery hook failed", output)
        self.assertIn("Discovery error:", output)

    def test_location_derived_entrypoint(self):
        """A copied real script validates its own fixture from an unrelated working directory."""
        script = self.root / "implementation" / "scripts" / "validate.py"
        script.parent.mkdir()
        shutil.copyfile(VALIDATOR, script)
        self.assertIn("FIXTURE BODY EXECUTED", self.validate(script=script, entrypoint=True))

    def test_unreadable_document(self):
        """Report read failures even on hosts where permission bits cannot deny owner reads."""
        prelude = '''
original_read = validator.Path.read_text
def denied_read(path, *args, **kwargs):
    """Model a required document that the validator cannot read."""
    if path.name == "README.md":
        raise PermissionError("fixture read denied")
    return original_read(path, *args, **kwargs)
validator.Path.read_text = denied_read
'''
        output = self.validate(1, prelude=prelude)
        self.assertIn(str(self.root / "README.md"), output)
        self.assertIn("fixture read denied", output)
        self.assertIn("tests did not run", output)

    def test_operational_failure(self):
        """An inaccessible root returns nonzero with an operational diagnostic."""
        prelude = '''
def denied_listing(path):
    """Model an inaccessible root directory without relying on host permissions."""
    raise PermissionError("fixture listing denied")
validator.Path.iterdir = denied_listing
'''
        self.assertIn("Operational validation error: fixture listing denied",
                      self.validate(1, prelude=prelude))

    def test_discovery_raises(self):
        """Discovery exceptions fail before execution and retain their reason."""
        prelude = '''
def broken_discover(loader, *args, **kwargs):
    """Model a discovery setup failure rather than a failing test body."""
    raise ImportError("fixture discovery setup failed")
validator.unittest.TestLoader.discover = broken_discover
'''
        output = self.validate(1, prelude=prelude)
        self.assertIn("Discovery failure: fixture discovery setup failed", output)
        self.assertIn("tests did not run", output)

    def test_public_options_rejected(self):
        """The production CLI has no alternate-root or bypass controls."""
        for option in ("--root", "--skip-tests"):
            with self.subTest(option=option):
                result = subprocess.run(
                    [sys.executable, "-B", str(VALIDATOR), option],
                    cwd=self.temporary.name, capture_output=True, text=True, check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("unrecognized arguments", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_script_import_is_inert(self):
        """Loading development tooling alone neither validates nor emits output."""
        result = subprocess.run([
            sys.executable, "-B", "-c",
            'import importlib.util; import sys; '
            's = importlib.util.spec_from_file_location("validator", sys.argv[1]); '
            's.loader.exec_module(importlib.util.module_from_spec(s))', str(VALIDATOR),
        ], cwd=self.temporary.name, capture_output=True, text=True, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")
