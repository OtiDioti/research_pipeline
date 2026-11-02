"""Run the exact self-contained published synthetic authority example with candidate imports."""

from pathlib import Path
import subprocess
import sys
import unittest
from tests.test_vault import child_environment


class OperatingExampleTests(unittest.TestCase):
    """The guide must work in a fresh process without test fixtures as runtime dependencies."""

    def test_published_example(self):
        """Execute incomplete setup, captured short note, approval, reduction and original recovery verbatim."""
        root = Path(__file__).resolve().parents[2]
        text = (root / "docs/operating-authority.md").read_text()
        program = text.split("## Runnable synthetic example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
            env=child_environment(), capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
