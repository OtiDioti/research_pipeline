"""Execute the exact published resource example with candidate-local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ResourceExampleTests(unittest.TestCase):
    """Keep the published usage/settlement/breach/migration contract runnable without hidden fixtures."""

    def test_documented_synthetic_usage_recovery_and_migration(self):
        """Execute partial usage, timeout, recovery, settlement, conservative charge, breach and exact restore."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/resource-accounting.md").read_text()
        program = document.split("## Runnable synthetic usage, recovery and migration example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
