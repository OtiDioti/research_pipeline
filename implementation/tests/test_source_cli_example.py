"""Execute the exact product/stdlib-only saved Source CLI guide in a fresh candidate interpreter."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tests.test_vault import child_environment


class SourceCliExampleTests(unittest.TestCase):
    """The published program must prepare/save/inspect/submit/recover without fixture injection."""

    def test_documentation_verbatim(self):
        """Extract the delimited code unchanged and preserve all subprocess failure diagnostics."""
        root = Path(__file__).resolve().parents[2]
        document = (root / 'docs/source-capture-cli.md').read_text()
        block = document.split('<!-- source-capture-cli-example:begin -->', 1)[1].split(
            '<!-- source-capture-cli-example:end -->', 1)[0]
        code = block.split('```python\n', 1)[1].split('```', 1)[0]
        with TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, '-B', '-c', code], cwd=temporary,
                env=child_environment(), capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout, b'')
