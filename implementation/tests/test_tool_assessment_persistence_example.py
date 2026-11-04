"""Execute exactly the self-contained public passive persistence guide with candidate imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class AssessmentPersistenceExampleTests(unittest.TestCase):
    """Keep the complete private-store example executable without test fixture imports."""

    def test_exact_guide_block(self):
        """Assert mixed forward commit, reopen/retry and atomic pairing refusal in a fresh interpreter."""
        root = Path(__file__).resolve().parents[2]
        text = (root / "docs/tool-assessment-persistence.md").read_text()
        section = text.split("<!-- tool-assessment-persistence-example:start -->\n", 1)[1].split("<!-- tool-assessment-persistence-example:end -->", 1)[0]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, (
            "Assessment and forward release committed; reopened inspection and original-ID reconciliation agree.\n"
            "Mismatched pairing refused atomically; no permission, qualification or execution established.\n"))
