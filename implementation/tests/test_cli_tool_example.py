"""Execute the delimited Tool CLI guide verbatim using only candidate product imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ToolCliExampleTests(unittest.TestCase):
    """Keep the published private-store mixed commit and recovery example executable."""

    def test_exact_documented_program(self):
        """Run the unchanged delimited code in a fresh candidate interpreter with no fixture injection."""
        root = Path(__file__).resolve().parents[2]
        text = (root / "docs/tool-record-cli.md").read_text()
        section = text.split("<!-- tool-record-cli-example:start -->", 1)[1].split("<!-- tool-record-cli-example:end -->", 1)[0]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("atomic refusal agree", result.stdout)
