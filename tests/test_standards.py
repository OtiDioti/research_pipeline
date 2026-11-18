"""The repository follows the shared development standard (agent_toolkit.standards)."""

import unittest
from pathlib import Path

from agent_toolkit import standards

ROOT = Path(__file__).resolve().parent.parent


class StandardsTest(unittest.TestCase):
    def test_the_repository_follows_the_standard(self):
        self.assertEqual(standards.problems(ROOT), [])


if __name__ == "__main__":
    unittest.main()
