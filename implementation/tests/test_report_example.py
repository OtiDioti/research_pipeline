"""Execute the exact self-contained committed-report guide with candidate-local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ReportExampleTests(unittest.TestCase):
    """Execute capture, publication, original-plan recovery and preserved late-liability history."""

    def test_documented_committed_report_sequence(self):
        """Run the exact guide through publication/navigation/recovery, late usage, settlement and exact restore."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/committed-run-reports.md").read_text()
        program = document.split("## Runnable synthetic committed-report example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
