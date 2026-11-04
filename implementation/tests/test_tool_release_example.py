"""Execute the exact product/stdlib-only Tool-release guide with candidate-local imports."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_vault import child_environment


class ToolReleaseExampleTests(unittest.TestCase):
    """Keep the published complete local and inaccessible remote examples independently runnable."""

    def test_exact_documented_block_and_identities(self):
        """Run the unchanged guide block and require its concrete hashes and round-trip assertions."""
        root = Path(__file__).resolve().parents[2]
        document = (root / "docs/tool-releases.md").read_text()
        program = document.split("## Runnable local and inaccessible remote example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        self.assertNotIn("from tests", program)
        self.assertNotIn("import tests", program)
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, (
            "local sha256:0f018fcdb8aa347a6f882c4251cf7724cab83043bd9314d8aeb524219078c00e\n"
            "remote sha256:b7658dbc74a391229ffda005cdb33fe75a34700c8202b594540e3e62704067ac\n"
            "adapter sha256:30534f9f87ced3f2ed45ff4ab7b1a9ea9a1ce234b828f221414f7b2d0c1838aa\n"
            "configuration sha256:f9ae32ce018eeb53fbcea26674ce9c63ac5fb68ccb9915e585afcc440ed86753\n"
            "Unknown environment retained; unavailable remote bytes retained; changed label changes release.\n"
            "Both declarations round-trip; no tool was run or qualified.\n"))
