"""Execute the exact self-contained offline binding guide with candidate-local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class LifecycleBindingExampleTests(unittest.TestCase):
    """Keep the documented pure cancellation packet executable without test fixtures."""

    def test_documented_offline_example(self):
        """Run the exact guide through every public boundary and its contradictory gate case."""
        root = Path(__file__).resolve().parents[2]
        document = (root / 'docs/lifecycle-report-binding.md').read_text()
        program = document.split('## Runnable offline lifecycle-binding example\n', 1)[1].split('```python\n', 1)[1].split('```', 1)[0]
        result = subprocess.run([sys.executable, '-B', '-c', program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('This proves local intent consistency only', result.stdout)
