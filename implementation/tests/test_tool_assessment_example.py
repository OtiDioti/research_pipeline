"""Execute the exact self-contained documented assessment example with local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ToolAssessmentExampleTests(unittest.TestCase):
    """Keep the complete product/stdlib example meaningful and independently executable."""

    def test_exact_marked_block_and_deterministic_output(self):
        """Extract and run the guide verbatim, retaining assertions and failure diagnostics."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/tool-assessments.md").read_text()
        start, end = "<!-- tool-assessment-example:start -->", "<!-- tool-assessment-example:end -->"
        self.assertEqual(document.count(start), 1)
        self.assertEqual(document.count(end), 1)
        block = document.split(start, 1)[1].split(end, 1)[0]
        program = block.split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, "Synthetic assessment round-tripped; contradictory projection refused; no tool executed.\n")
