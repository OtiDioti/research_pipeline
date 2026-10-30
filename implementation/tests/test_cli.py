"""Exercise the candidate CLI and observed import behavior in isolated processes."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

IMPLEMENTATION = Path(__file__).resolve().parents[1]
SRC = IMPLEMENTATION / "src"
PACKAGE = SRC / "research_pipeline" / "__init__.py"


class CliTests(unittest.TestCase):
    """Check source-local CLI behavior without relying on an installed distribution."""

    def run_python(self, arguments, cwd, extra_paths=()):
        """Run a bytecode-free interpreter with candidate source first and capture its output."""
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(map(str, (SRC, *extra_paths)))
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-B", *arguments], cwd=cwd, env=environment,
            capture_output=True, text=True, check=False,
        )

    def test_help(self):
        """Explicit and implicit help explain the foundation's actual limits."""
        with tempfile.TemporaryDirectory() as temporary:
            for arguments in ([], ["--help"]):
                with self.subTest(arguments=arguments):
                    result = self.run_python(["-m", "research_pipeline", *arguments], temporary)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("foundation", result.stdout)
                    self.assertIn("research execution is unavailable", result.stdout)
                    self.assertIn("--version", result.stdout)
                    self.assertEqual(result.stderr, "")

    def test_metadata_and_version(self):
        """Version agrees with metadata and metadata declares the bounded packaging contract."""
        metadata = tomllib.loads((IMPLEMENTATION / "pyproject.toml").read_text())
        project = metadata["project"]
        self.assertEqual(project["name"], "theoretical-research-pipeline")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project.get("dependencies", []), [])
        self.assertEqual(project["readme"], "README.md")
        self.assertNotIn("scripts", project)
        self.assertEqual(metadata["build-system"], {
            "requires": ["setuptools>=61"], "build-backend": "setuptools.build_meta",
        })
        self.assertEqual(metadata["tool"]["setuptools"]["packages"]["find"], {
            "where": ["src"], "include": ["research_pipeline", "research_pipeline.*"],
            "namespaces": False,
        })
        with tempfile.TemporaryDirectory() as temporary:
            version = self.run_python(["-m", "research_pipeline", "--version"], temporary)
            identity = self.run_python([
                "-c", "import research_pipeline as p; print(p.__version__); print(p.__file__)",
            ], temporary)
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(identity.returncode, 0, identity.stderr)
        self.assertEqual(version.stderr, "")
        self.assertEqual(version.stdout.strip(), project["version"])
        self.assertEqual(identity.stdout.splitlines(), [project["version"], str(PACKAGE)])

    def test_usage_errors(self):
        """Unknown commands, options, and abbreviations fail with argparse status 2."""
        with tempfile.TemporaryDirectory() as temporary:
            for argument in ("run", "--unknown", "--ver", "--he"):
                with self.subTest(argument=argument):
                    result = self.run_python(["-m", "research_pipeline", argument], temporary)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("usage:", result.stderr)
                    self.assertIn("unrecognized arguments: " + argument, result.stderr)

    def test_competing_package(self):
        """A fake package later on PYTHONPATH cannot mask the candidate source."""
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / "competitor" / "research_pipeline"
            fake.mkdir(parents=True)
            (fake / "__init__.py").write_text("raise RuntimeError('wrong checkout')\n")
            result = self.run_python(
                ["-c", "import research_pipeline; print(research_pipeline.__file__)"],
                temporary, [fake.parent],
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(PACKAGE))
        self.assertEqual(result.stderr, "")

    def test_import_has_no_observed_side_effects(self):
        """Guard writes, processes, and network before fresh import; inspect output and files."""
        program = '''
import contextlib
import io
import json
import os
import sys
attempts = []
def guard(event, arguments):
    """Fail immediately on audited write, process, or network attempts, allowing reads."""
    forbidden = event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn"))
    forbidden = forbidden or event in {
        "os.system", "os.fork", "os.forkpty", "os.posix_spawn", "os.remove",
        "os.rename", "os.mkdir", "os.rmdir", "os.link", "os.symlink", "os.truncate",
        "os.chmod", "os.chown", "os.utime", "os.putenv", "os.unsetenv",
    }
    if event == "open":
        mode, flags = arguments[1:3]
        forbidden = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
    if forbidden:
        attempts.append(event)
        raise RuntimeError("import effect: " + event)
sys.addaudithook(guard)
out, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    import research_pipeline
print(json.dumps({"origin": research_pipeline.__file__, "version": research_pipeline.__version__,
                  "stdout": out.getvalue(), "stderr": err.getvalue(), "attempts": attempts}))
'''
        with tempfile.TemporaryDirectory() as temporary:
            before = list(Path(temporary).rglob("*"))
            result = self.run_python(["-c", program], temporary)
            self.assertEqual(list(Path(temporary).rglob("*")), before)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        observed = json.loads(result.stdout)
        self.assertEqual(observed, {
            "origin": str(PACKAGE), "version": "0.1.0", "stdout": "", "stderr": "", "attempts": [],
        })
