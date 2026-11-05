"""Execute the literal schema-7 product/stdlib example in a fresh candidate interpreter."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class SupportContextExampleTests(unittest.TestCase):
    """The published synthetic example must work without importing test helpers."""

    def test_documentation_verbatim(self):
        """Run the unchanged documented block, retaining bounded subprocess failure diagnostics."""
        root = Path(__file__).resolve().parents[2]
        document = (root/"docs/claim-use-freshness.md").read_text()
        code = document.split("## Executable schema-7 support-context example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        with TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, "-B", "-c", code], cwd=temporary,
                env={**os.environ, "PYTHONPATH": str(root/"implementation/src"), "PYTHONDONTWRITEBYTECODE": "1"},
                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
