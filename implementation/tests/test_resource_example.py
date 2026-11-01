"""Execute the exact published resource example with candidate-local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ResourceExampleTests(unittest.TestCase):
    """Keep the published reservation/migration/recovery contract runnable without hidden fixtures."""

    def test_documented_synthetic_reservation_and_migration(self):
        """Execute the complete documentation block, including exact retry and outstanding restore."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/resource-accounting.md").read_text()
        program = document.split("## Runnable synthetic reservation and migration example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
