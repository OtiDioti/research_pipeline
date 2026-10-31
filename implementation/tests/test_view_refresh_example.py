"""Execute the published self-contained continuation verbatim in fresh candidate Python."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class RefreshExampleTests(unittest.TestCase):
    """Documentation is exercised code and cannot rely on test fixtures inside the example."""

    def test_documented_preservation_import_and_stale_conflict(self):
        """Run the exact refresh/source/checkout/preview/saved-proposal/import block without bytecode."""
        root = Path(__file__).resolve().parents[2]
        text = (root / "docs/readable-refresh.md").read_text()
        program = text.split("## Runnable preservation and explicit import example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
