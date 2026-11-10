"""Unpaid engineering regressions for the M3 gate's evidence and reproduction."""
from pathlib import Path
import hashlib
import json
import math
import shlex
import subprocess
import sys
import tempfile
import unittest

from tests.test_m3_live import (independent_observations, observation_invocations,
                                parent_overlap, reproduction_driver)


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


class IndependentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.independent = "work/tasks/verifier"
        (self.project / self.independent).mkdir(parents=True)
        self.artifacts = {}
        self.rows = [self.row(a) for a in (1.01, 1.2)]

    @staticmethod
    def row(a):
        reference = 2 * math.pi / math.sqrt((a - 1) * (a + 1))
        approximation = 2 * math.pi / math.sqrt(2 * (a - 1))
        return dict(a=a, reference=reference, approximation=approximation,
                    relative_error=abs(approximation / reference - 1))

    def write(self, name, data):
        rel = self.independent + "/" + name
        text = data if isinstance(data, str) else json.dumps(data)
        (self.project / rel).write_text(text)
        self.artifacts[rel] = hashlib.sha256(text.encode()).hexdigest()
        return rel

    def read(self, rel):
        return (self.project / rel).read_text()

    def observations(self, artifacts=None):
        return independent_observations(self.project, self.independent,
                                        self.artifacts if artifacts is None else artifacts, self.read)

    def calls(self, observations, commands):
        return observation_invocations(self.project, self.independent, self.artifacts,
                                       observations, commands)

    def test_observations_and_linked_hash_map_are_distinct_evidence(self):
        code = self.write("check.py", "# independent check")
        data = self.write("check.json", {"rows": self.rows})
        self.write("evidence_hashes.json", {"check.py": self.artifacts[code]})
        self.assertEqual(self.observations(), {data: self.rows})
        (self.project / code).write_text("changed")
        with self.assertRaisesRegex(AssertionError, "fingerprint mismatch"):
            self.observations()

    def test_all_numerical_files_are_checked_including_partitioned_stress(self):
        near = self.write("near.json", {"rows": self.rows[:1]})
        stress = self.write("stress.json", {"rows": self.rows[1:]})
        self.assertEqual(set(self.observations()), {near, stress})
        self.write("stress.json", {"rows": [{**self.rows[1], "reference": 9.0}]})
        with self.assertRaisesRegex(AssertionError, "Inconsistent"):
            self.observations()

    def test_missing_malformed_and_unknown_evidence_fail(self):
        for data, message in (({}, "Unrecognized"), ({"rows": []}, "Missing"),
                              ({"rows": [self.rows[0]]}, "stress"),
                              ({"rows": [self.rows[1]]}, "near-boundary"),
                              ({"rows": [self.rows[0], self.rows[0]]}, "duplicate"),
                              ({"rows": [{**self.rows[0], "reference": float("nan")}]}, "Malformed"),
                              ({"method": "Simpson"}, "Unrecognized")):
            with self.subTest(data=data):
                self.artifacts.clear()
                self.write("check.json", data)
                with self.assertRaisesRegex(AssertionError, message):
                    self.observations()

    def test_conflicting_tables_fail_even_within_reference_tolerance(self):
        self.write("check.json", {"rows": self.rows})
        self.write("other.json", {"rows": [{**self.rows[0], "relative_error":
                                           self.rows[0]["relative_error"] + 5e-9}]})
        with self.assertRaisesRegex(AssertionError, "Conflicting"):
            self.observations()

    def test_each_observation_needs_unambiguous_executed_linked_code(self):
        data = self.write("check.json", {"rows": self.rows})
        observations = self.observations()
        with self.assertRaisesRegex(AssertionError, "Missing or ambiguous"):
            self.calls(observations, [])
        with self.assertRaisesRegex(AssertionError, "Unlinked"):
            self.calls(observations, ["python3 check.py --output check.json"])
        self.write("check.py", "# independent check")
        calls = self.calls(observations, [
            "python3 check.py --a 1.01 1.2 --output check.json",
            "python3 check.py --a 1.01 1.2 --output check.json"])
        self.assertEqual(calls[data]["argv"][2:], ["--a", "1.01", "1.2", "--output", "check.json"])
        with self.assertRaisesRegex(AssertionError, "Missing or ambiguous"):
            self.calls(observations, ["python3 check.py --a 1.01 --output check.json",
                                      "python3 check.py --a 1.2 --output check.json"])

    def test_heredoc_documentation_is_not_execution_provenance(self):
        self.write("check.py", "from pathlib import Path\nPath('executed').touch()\n")
        self.write("check.json", {"rows": self.rows})
        for redirect, indent in (("<<'SH'", ""), ('<<-"SH"', "\t")):
            with self.subTest(redirect=redirect):
                body = (f"cat > rerun.sh {redirect}\n"
                        f"{indent}python3 check.py --output check.json\n{indent}SH\n")
                # Only trusted fixture code/commands run on the unit-test host.
                result = subprocess.run(["/bin/bash", "-c", body],
                                        cwd=self.project / self.independent, timeout=5)
                self.assertEqual(result.returncode, 0)
                self.assertFalse((self.project / self.independent / "executed").exists())
                with self.assertRaisesRegex(AssertionError, "Missing or ambiguous"):
                    self.calls(self.observations(), [shlex.join(["/bin/bash", "-c", body])])

    def test_documentation_then_genuine_run_uses_only_executed_parameters(self):
        self.write("check.py", "from pathlib import Path\nimport sys\n"
                   "Path('executed').write_text(' '.join(sys.argv[1:]))\n")
        self.write("helper.py", "# trusted checkpoint fixture\n")
        data = self.write("check.json", {"rows": self.rows})
        actual = ["--a", "1.01", "1.2", "--output", "check.json"]
        for prefix in ("", "python3 helper.py --check && "):
            with self.subTest(prefix=prefix):
                body = (prefix + "mkdir -p notes[example] && cat > notes[example]/rerun.sh <<'SH'\n"
                        "python3 check.py --a 9 --output check.json\nSH\n"
                        "python3 check.py --a 1.01 1.2 --output check.json\n"
                        "python3 helper.py --check\n")
                marker = self.project / self.independent / "executed"
                marker.unlink(missing_ok=True)
                result = subprocess.run(["/bin/bash", "-c", body],
                                        cwd=self.project / self.independent, timeout=5)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(marker.read_text(), " ".join(actual))
                calls = self.calls(self.observations(), [shlex.join(["/bin/bash", "-c", body])])
                self.assertEqual(calls[data]["argv"][2:], actual)

    def test_heredoc_prefix_cannot_hide_early_shell_exit(self):
        self.write("check.py", "from pathlib import Path\nPath('executed').touch()\n")
        self.write("check.json", {"rows": self.rows})
        for prefix in ("exit 0", "exec /usr/bin/true", "eval 'exit 0'",
                       "mkdir -p notes && exit 0"):
            for writer in ("cat check.py", "cat > note.md <<'MD'\nSaved note\nMD"):
                with self.subTest(prefix=prefix, writer=writer):
                    body = f"{prefix} && {writer}\npython3 check.py --output check.json\n"
                    result = subprocess.run(["/bin/bash", "-c", body],
                                            cwd=self.project / self.independent,
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse((self.project / self.independent / "executed").exists())
                    with self.assertRaisesRegex(AssertionError, "Missing or ambiguous"):
                        self.calls(self.observations(), [shlex.join(["/bin/bash", "-c", body])])

    def test_skipped_check_then_successful_statement_is_not_execution_provenance(self):
        self.write("check.py", "from pathlib import Path\nPath('executed').touch()\n")
        self.write("check.json", {"rows": self.rows})
        for tail in ("sha256sum check.py", "cat > note.md <<'MD'\nSaved note\nMD"):
            with self.subTest(tail=tail):
                body = ("cat missing-file && python3 check.py --output check.json\n"
                        + tail + "\n")
                result = subprocess.run(["/bin/bash", "-c", body],
                                        cwd=self.project / self.independent,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.project / self.independent / "executed").exists())
                with self.assertRaisesRegex(AssertionError, "Missing or ambiguous"):
                    self.calls(self.observations(), [shlex.join(["/bin/bash", "-c", body])])

    def test_unconditional_and_successful_final_chain_calls_supply_provenance(self):
        self.write("check.py", "from pathlib import Path\nPath('executed').touch()\n")
        data = self.write("check.json", {"rows": self.rows})
        invocation = "python3 check.py --output check.json"
        for body in (f"{invocation}\nsha256sum check.py\n",
                     f"cat check.py && {invocation}\n# trailing comment\n"):
            with self.subTest(body=body):
                marker = self.project / self.independent / "executed"
                marker.unlink(missing_ok=True)
                result = subprocess.run(["/bin/bash", "-c", body],
                                        cwd=self.project / self.independent,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(marker.exists())
                calls = self.calls(self.observations(), [shlex.join(["/bin/bash", "-c", body])])
                self.assertEqual(calls[data]["argv"][2:], ["--output", "check.json"])

    def test_unsupported_shell_structure_cannot_supply_partial_provenance(self):
        self.write("check.py", "# independent fixture")
        self.write("check.json", {"rows": self.rows})
        invocation = "python3 check.py --output check.json"
        for command in (f"if false; then\n{invocation}\nfi",
                        f"cat > rerun.sh <<'SH'\n{invocation}\n",
                        f"cat 'multiline\n{invocation}\ntext'",
                        f"cat 'literal && {invocation}'",
                        f"{invocation}\nif false; then cat absent; fi",
                        f"python3 -V && cat check.py\n{invocation}",
                        f"python3 -V && cat > note.md <<'MD'\nSaved note\nMD\n{invocation}",
                        f"python3 check.py --a [12] --output check.json"):
            with self.subTest(command=command):
                with self.assertRaisesRegex(AssertionError, "Missing or ambiguous"):
                    self.calls(self.observations(), [command])

    def test_separate_targeted_program_and_all_outputs_are_reproduced(self):
        # Trusted fixture programs exercise the actual planning/driver path.
        # Agent-written science is executed only by the live isolation launcher.
        self.write("check.py",
                   "import argparse,json\nfrom pathlib import Path\n"
                   "p=argparse.ArgumentParser();p.add_argument('--output');"
                   "p.add_argument('--a',nargs='+',type=float);args=p.parse_args()\n"
                   f"rows={self.rows!r}\n"
                   "Path(args.output).write_text(json.dumps({'rows':[r for r in rows if r['a'] in args.a]}))\n")
        self.write("reexamine.py", (self.project / self.independent / "check.py").read_text()
                   + "# separately authored targeted check\n")
        near = self.write("near.json", {"rows": self.rows[:1]})
        stress = self.write("stress.json", {"rows": self.rows[1:]})
        initial = self.observations()
        initial_calls = self.calls(initial, [
            "/usr/bin/bash -lc 'python3 helper.py --check && python3 check.py --a 1.01 --output near.json'",
            "/usr/bin/bash -lc 'python3 check.py --a 1.2 --output stress.json'"])
        targeted = self.write("targeted.json", {"rows": self.rows})
        final = self.observations()
        new = {rel: rows for rel, rows in final.items() if rel not in initial}
        targeted_calls = self.calls(new, ["python3 reexamine.py --a 1.01 1.2 --output targeted.json"])
        calls = {**initial_calls, **targeted_calls}
        self.assertEqual(set(calls), {near, stress, targeted})
        invocations, outputs = [], {}
        for index, (rel, call) in enumerate(calls.items()):
            output = self.project / f"repeat-{index}.json"
            argv = list(call["argv"])
            argv[0] = sys.executable
            argv[1] = str(self.project / argv[1].removeprefix("/project/"))
            argv[call["output_index"]] = str(output)
            invocations.append({"argv": argv, "cwd": str(self.project / self.independent)})
            outputs[output] = final[rel]
        result = subprocess.run([sys.executable, "-c", reproduction_driver(invocations)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        for output, expected in outputs.items():
            self.assertEqual(json.loads(output.read_text())["rows"], expected)
        # A second round linking only old observations cannot supply a new test.
        with self.assertRaisesRegex(AssertionError, "near-boundary"):
            self.observations({})
