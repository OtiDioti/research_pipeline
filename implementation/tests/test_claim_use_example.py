"""Execute the exact self-contained published claim-use example in fresh candidate Python."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class ClaimUseExampleTests(unittest.TestCase):
    """Documentation is an executable product contract without test-helper imports."""

    def test_documentation_verbatim(self):
        """Run the literal product/stdlib-only block and preserve bounded failure diagnostics."""
        root = Path(__file__).resolve().parents[2]
        document = (root/"docs/claim-use-freshness.md").read_text()
        code = document.split("## Executable synthetic example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        with TemporaryDirectory(dir="/tmp") as temporary:
            result = subprocess.run([sys.executable, "-B", "-c", code], cwd=temporary,
                env={**os.environ, "PYTHONPATH": str(root/"implementation/src"), "PYTHONDONTWRITEBYTECODE": "1"},
                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
