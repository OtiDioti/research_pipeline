"""Execute the exact self-contained readable-view CLI guide against candidate source."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class CliViewExampleTests(unittest.TestCase):
    """Keep documented preservation and selected-byte submission executable without test fixtures."""

    def test_documented_cli_continuation(self):
        """Run the guide verbatim in fresh Python, including offline inspection and stale-CAS conflict."""
        root = Path(__file__).resolve().parents[2]
        text = (root / "docs/readable-view-cli.md").read_text()
        program = text.split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
