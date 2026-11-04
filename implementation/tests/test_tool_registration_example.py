"""Execute exactly the self-contained registration guide against candidate-local product modules."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ToolRegistrationExampleTests(unittest.TestCase):
    """Keep the public passive persistence example runnable without tests or live services."""

    def test_registration_block(self):
        """Require real registration, exact history, independent hashes and atomic target refusal."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/tool-releases.md").read_text()
        section = document.split("<!-- tool-registration-example:start -->\n", 1)[1].split("<!-- tool-registration-example:end -->", 1)[0]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
            env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, (
            "Registered Tool and forward implementation manifest: 2 exact revisions, 2 artifact digests.\n"
            "History 1, 2, 3 preserved: same release/new provenance, then independently hashed amendment.\n"
            "Original receipt reconciled; generic child refused without receipt, head or audit effects.\n"
            "Passive persistence only; no tool executed, qualified or permitted.\n"))
