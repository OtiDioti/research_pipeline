"""Execute the exact published product/stdlib private-store CLI example with candidate imports."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class ClaimUseCliExampleTests(unittest.TestCase):
    """The documented program needs neither fixtures, installation nor injected setup."""

    def test_documentation_verbatim(self):
        """Run the delimited program unchanged in a fresh process, retaining failure diagnostics."""
        root = Path(__file__).resolve().parents[2]
        document = (root/'docs/claim-use-cli.md').read_text()
        code = document.split('## Executable private-store example\n', 1)[1].split('```python\n', 1)[1].split('```', 1)[0]
        with TemporaryDirectory(dir='/tmp') as temporary:
            result = subprocess.run([sys.executable, '-B', '-c', code], cwd=temporary,
                env={**os.environ, 'PYTHONPATH': str(root/'implementation/src'), 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout, b'')
