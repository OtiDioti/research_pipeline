"""Execute the exact product/stdlib-only committed lifecycle source documentation example."""

from pathlib import Path
import subprocess
import sys
import unittest
from tests.test_vault import child_environment


class LifecycleSourceExampleTests(unittest.TestCase):
    """Treat actual candidate-local subprocess execution as evidence, never the Markdown itself."""

    def test_exact_documented_example(self):
        """Run initial capture, later work/settlement, delayed cancelled capture and original reopen recovery."""
        root = Path(__file__).resolve().parents[2]
        doc = (root / 'docs/committed-lifecycle-sources.md').read_text()
        program = doc.split('## Runnable committed-source example\n', 1)[1].split('```python\n', 1)[1].split('```', 1)[0]
        self.assertNotIn('from tests', program)
        self.assertNotIn('import tests', program)
        result = subprocess.run([sys.executable, '-B', '-c', program], cwd=root,
            env=child_environment(), capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('No report output or publication was produced.', result.stdout)
