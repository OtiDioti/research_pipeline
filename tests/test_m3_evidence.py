"""Unpaid engineering regressions for the M3 gate's evidence and reproduction."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_m3_live import parent_overlap, reproduction_driver


class M3EvidenceTests(unittest.TestCase):
    milestones = {"saving": {"elapsed": 225}, "successor": {"elapsed": 240},
                  "continued_calculation": {"elapsed": 270}}

    def observation(self, elapsed, parameters, command_count):
        return {"elapsed": elapsed, "rows": [{"a": a} for a in parameters],
                "native_session_id": "primary-native",
                "commands": ["python parent.py"] * command_count}

    def test_updates_only_before_saving_cannot_establish_overlap(self):
        progress = [self.observation(195, [1.01], 1),
                    self.observation(215, [1.01, 1.02], 2),
                    self.observation(225, [1.01, 1.02], 2),
                    self.observation(260, [1.01, 1.02], 2)]
        with self.assertRaisesRegex(AssertionError, "did not extend"):
            parent_overlap(progress, self.milestones)

    def test_updates_after_successor_calculation_cannot_establish_overlap(self):
        progress = [self.observation(225, [1.01], 1),
                    self.observation(280, [1.01, 1.02], 2)]
        with self.assertRaisesRegex(AssertionError, "Missing substantive parent progress"):
            parent_overlap(progress, self.milestones)

    def test_new_science_during_handoff_or_successor_establishes_overlap(self):
        for elapsed in (230, 260):
            with self.subTest(elapsed=elapsed):
                progress = [self.observation(225, [1.01], 1),
                            self.observation(elapsed, [1.01, 1.02], 2)]
                self.assertEqual(parent_overlap(progress, self.milestones), tuple(progress))

    def test_commands_without_new_observations_cannot_establish_overlap(self):
        progress = [self.observation(225, [1.01], 1),
                    self.observation(260, [1.01], 2)]
        with self.assertRaisesRegex(AssertionError, "did not extend"):
            parent_overlap(progress, self.milestones)

    def test_new_observations_require_a_calculation_event_in_the_interval(self):
        progress = [self.observation(225, [1.01], 1),
                    self.observation(260, [1.01, 1.02], 1)]
        with self.assertRaisesRegex(AssertionError, "No new parent calculation"):
            parent_overlap(progress, self.milestones)

    def test_reproduction_preserves_each_tasks_relative_input_paths(self):
        # Trusted fixture code, not agent-written science: exercise the same driver
        # with a different current directory and distinct inputs in both workspaces.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            invocations = []
            for role in ("researcher", "verifier"):
                task = root / role
                (task / "inputs/initial").mkdir(parents=True)
                (task / "inputs/initial/value.txt").write_text(role)
                script = task / "check.py"
                script.write_text(
                    "from pathlib import Path\nimport sys\n"
                    "Path(sys.argv[1]).write_text(Path('inputs/initial/value.txt').read_text())\n")
                invocations.append({"argv": [sys.executable, str(script), str(root / f"{role}.out")],
                                    "cwd": str(task)})
            result = subprocess.run([sys.executable, "-c", reproduction_driver(invocations)],
                                    cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            for role in ("researcher", "verifier"):
                self.assertEqual((root / f"{role}.out").read_text(), role)
