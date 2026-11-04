"""Execute the separate self-contained passive envelope guide with candidate-local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ToolReleaseEnvelopeExampleTests(unittest.TestCase):
    """Keep the public envelope example independently runnable and meaningfully asserted."""

    def test_exact_envelope_block(self):
        """Run the published block and demand ordered pins, identity round-trip and mismatch rejection."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/tool-releases.md").read_text()
        program = document.split("## Runnable exact passive envelope example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, (
            "envelope scale_tool revision 17: 8 record occurrences, 3 artifact digests\n"
            "record order: supply, supply, source, child, qualification, evidence, issue, source\n"
            "artifact order: implementation, adapter, self-test\n"
            "Content and all three identities round-trip; mismatched projection rejected.\n"
            "Only local consistency: no registration, authentication, qualification or execution.\n"))
