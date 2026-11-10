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
                                numerical_evidence, parent_overlap, primary_calculation,
                                record_parent_progress, reproduction_driver)


class M3EvidenceTests(unittest.TestCase):
    milestones = {"saving": {"elapsed": 225}, "successor": {"elapsed": 240},
                  "continued_calculation": {"elapsed": 270}}

    def observation(self, elapsed, parameters, command_count):
        return {"elapsed": elapsed, "rows": [IndependentEvidenceTests.row(a) for a in parameters],
                "native_session_id": "primary-native",
                "commands": ["python3 /project/work/parent.py --advance"] * command_count}

    def record(self, progress, observation):
        events = [{"type": "item.completed", "item": {
            "type": "command_execution", "exit_code": 0, "command": command}}
                  for command in observation["commands"]]
        record_parent_progress(progress, elapsed=observation["elapsed"],
            native_session_id=observation["native_session_id"], child_activation="child",
            data=json.dumps({"rows": observation["rows"]}).encode(),
            derivation="Parent derivation", events=events)

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

    def test_delayed_success_creates_a_new_snapshot_without_rewriting_history(self):
        for completion in (261, 280):
            with self.subTest(completion=completion):
                progress = []
                self.record(progress, self.observation(225, [1.01], 1))
                self.record(progress, self.observation(260, [1.01, 1.02], 1))
                self.record(progress, self.observation(completion, [1.01, 1.02], 2))
                self.assertEqual(len(progress), 3)
                self.assertEqual(len(progress[1]["commands"]), 1)
                if completion <= self.milestones["continued_calculation"]["elapsed"]:
                    self.assertEqual(parent_overlap(progress, self.milestones),
                                     (progress[0], progress[-1]))
                else:
                    with self.assertRaisesRegex(AssertionError, "No new parent calculation"):
                        parent_overlap(progress, self.milestones)

    def test_retained_final_021_exposes_compound_status_ambiguity(self):
        # m3-live-b17hs7ld: exact retained observation times, row/command
        # counts and parameter sets. Both successful expansion events use this
        # shell shape; later statements mask the conditional helper's status.
        milestones = {"saving": {"elapsed": 217.24254299699533},
                      "continued_calculation": {"elapsed": 255.90935201799584}}
        initial = [1.0001, 1.001, 1.01, 1.02, 1.03, 1.04, 1.1, 1.2]
        saving = [1.025, 1.035, 1.05]
        successor = [1.0401, 1.0403, 1.08]
        body = ("python3 /run/research-checkpoint-helper.py --check && "
                "python3 /project/work/transition.py && python3 - <<'PY'\n"
                "from pathlib import Path\n"
                "import json\n"
                "p=Path('/project/work/transition_events.jsonl')\n"
                "if p.exists():\n"
                " events=[json.loads(s) for s in p.read_text().splitlines()]\n"
                " print(events)\n"
                " with Path('/run/research-drafts/work/PARENT.md').open('a') as f:\n"
                "  f.write('\\n## Observed child transition\\nStatus and conditional "
                "calculation in one command recorded '+json.dumps(events)+'. "
                "[Event evidence](transition_events.jsonl). Each event expanded "
                "parent.json immediately, before reading the child handoff.\\n')\n"
                "PY\npython3 /run/research-checkpoint-helper.py --check")
        calculation = shlex.join(["/usr/bin/bash", "-lc", body])
        self.assertFalse(primary_calculation(calculation))
        observations = []
        history = ["python3 /run/research-checkpoint-helper.py --check"] * 14
        for elapsed, rows, count in ((217.24255496799742, initial, 14),
                                     (221.26264102300047, initial + saving, 14),
                                     (221.46370552699955, initial + saving, 15),
                                     (231.93375910999748, initial + saving + successor, 16),
                                     (239.58764530799817, initial + saving + successor, 17),
                                     (247.4449976679971, initial + saving + successor, 18)):
            p = self.observation(elapsed, sorted(rows), 0)
            p["commands"] = (history + [calculation] * 4)[:count]
            observations.append(p)
        recorded = []
        for p in observations:
            self.record(recorded, p)
        frozen = json.dumps(recorded)
        with self.assertRaisesRegex(AssertionError, "No new parent calculation"):
            parent_overlap(recorded, milestones)
        self.assertEqual(json.dumps(recorded), frozen)
        self.assertEqual([len(p["commands"]) for p in recorded], [14, 14, 15, 16, 17, 18])
        self.assertEqual([len(p["rows"]) for p in recorded], [8, 11, 11, 14, 14, 14])

    def test_native_exit_status_belongs_to_standalone_calculation(self):
        # Trusted engineering fixtures demonstrate the ambiguity in final-021,
        # then the new standalone contract. No retained agent code runs here.
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / "checkpoint.py").write_text("print('No checkpoint requested.')\n")
            (work / "parent.py").write_text(
                "import subprocess,sys\n"
                "subprocess.run([sys.executable,'calculation.py'],check=True)\n")
            compound = ("python3 checkpoint.py && python3 parent.py --advance && "
                        "python3 - <<'PY'\nprint('Notes')\nPY\n"
                        "python3 checkpoint.py")
            standalone = "python3 parent.py --advance"
            (work / "calculation.py").write_text("raise SystemExit(7)\n")
            for body, success in ((compound, True), (standalone, False)):
                result = subprocess.run(["/bin/bash", "-c", body], cwd=work,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                self.assertEqual(primary_calculation(body), body == standalone)
            (work / "calculation.py").write_text("print(6 * 7)\n")
            result = subprocess.run(["/bin/bash", "-c", standalone], cwd=work,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "42")

    def test_failed_calculations_cannot_corroborate_new_rows(self):
        for body in ("python3 /project/work/parent.py --advance",
                     "python3 /project/work/parent.py --advance && ls /project/work"):
            with self.subTest(body=body):
                progress = []
                self.record(progress, self.observation(225, [1.01], 0))
                record_parent_progress(progress, elapsed=260, native_session_id="primary-native",
                    child_activation="child",
                    data=json.dumps({"rows": [IndependentEvidenceTests.row(a)
                                             for a in (1.01, 1.02)]}).encode(),
                    derivation="Parent derivation", events=[{"type": "item.completed", "item": {
                        "type": "command_execution", "exit_code": 1, "command": body}}])
                self.assertEqual(progress[-1]["commands"], [])
                with self.assertRaisesRegex(AssertionError, "No new parent calculation"):
                    parent_overlap(progress, self.milestones)

    def test_standalone_science_and_parent_reproduction_use_same_trusted_program(self):
        # Only trusted engineering fixture code executes on this test host.
        # The status-driven and reproducible CLI modes share the calculation.
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            script = (
                "import argparse,json,math\nfrom pathlib import Path\n"
                "p=argparse.ArgumentParser();p.add_argument('--a',type=float,nargs='+');"
                "p.add_argument('--output');p.add_argument('--advance',action='store_true');"
                "args=p.parse_args()\n"
                "rows=[]\n"
                "if args.advance:\n"
                " args.output='parent.json'\n"
                " rows=json.loads(Path(args.output).read_text())['rows']\n"
                " args.a=json.loads(Path('status.json').read_text())['reserved_parameters']\n"
                "for a in args.a:\n"
                " reference=2*math.pi/math.sqrt((a-1)*(a+1))\n"
                " approximation=2*math.pi/math.sqrt(2*(a-1))\n"
                " rows.append(dict(a=a,reference=reference,approximation=approximation,"
                "relative_error=abs(approximation/reference-1)))\n"
                "Path(args.output).write_text(json.dumps(dict(rows=rows)))\n")
            (work / "parent.py").write_text(script)
            (work / "status.json").write_text(
                json.dumps({"reserved_parameters": [1.0402, 1.041, 1.2]}))
            subprocess.run([sys.executable, "parent.py", "--a", "1.01", "--output", "parent.json"],
                           cwd=work, check=True, timeout=5)
            before = self.observation(225, [1.01], 1)
            before["rows"] = json.loads((work / "parent.json").read_text())["rows"]
            body = "/usr/bin/python3 parent.py --advance"
            result = subprocess.run(["/bin/bash", "-c", body], cwd=work,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            after = {**before, "elapsed": 230,
                     "rows": json.loads((work / "parent.json").read_text())["rows"],
                     "commands": [*before["commands"], body]}
            self.assertEqual(parent_overlap([before, after], self.milestones), (before, after))
            invocation = {"argv": [sys.executable, str(work / "parent.py"), "--a",
                                  *(str(row["a"]) for row in after["rows"]),
                                  "--output", str(work / "reproduced.json")],
                          "cwd": str(work)}
            subprocess.run([sys.executable, "-c", reproduction_driver([invocation])],
                           cwd=work, check=True, timeout=5)
            self.assertEqual(json.loads((work / "reproduced.json").read_text())["rows"], after["rows"])

    def test_another_primary_native_session_cannot_establish_overlap(self):
        progress = [self.observation(225, [1.01], 1),
                    self.observation(260, [1.01, 1.02], 2)]
        progress[-1]["native_session_id"] = "fresh-primary"
        with self.assertRaisesRegex(AssertionError, "native session changed"):
            parent_overlap(progress, self.milestones)

    def test_changed_or_removed_prior_rows_cannot_establish_overlap(self):
        for change in ("changed", "removed"):
            with self.subTest(change=change):
                progress = [self.observation(225, [1.01], 1),
                            self.observation(260, [1.01, 1.02], 2)]
                if change == "changed":
                    progress[-1]["rows"][0]["reference"] += 1
                else:
                    progress[-1]["rows"].pop(0)
                with self.assertRaisesRegex(AssertionError, "changed prior numerical"):
                    parent_overlap(progress, self.milestones)

    def test_prose_hash_changes_without_new_parameters_cannot_establish_overlap(self):
        progress = [self.observation(225, [1.01], 1),
                    self.observation(260, [1.01], 2)]
        progress[-1].update(sha256="changed", derivation="New explanatory text")
        with self.assertRaisesRegex(AssertionError, "did not extend"):
            parent_overlap(progress, self.milestones)

    def test_documented_skipped_and_other_role_commands_cannot_establish_overlap(self):
        for body in ("cat > rerun.sh <<'SH'\npython3 expand.py\nSH",
                     "cat missing && python3 expand.py\ncat parent.json",
                     "ls missing && python3 expand.py\ncat parent.json",
                     "python3 /run/research-checkpoint-helper.py --check && "
                     "python3 expand.py && python3 - <<'PY'\nprint('data')\nPY\n"
                     "python3 /run/research-checkpoint-helper.py --check",
                     "exit 0 && python3 expand.py",
                     "python3 /run/research-checkpoint-helper.py --check",
                     "python3 /project/work/tasks/child/compute.py",
                     "python3 ../work/tasks/child/compute.py",
                     "python3 /project/work/write_notes.py",
                     "python3 /project/work/tasks/child/parent.py --advance",
                     "python3 ../work/parent.py --advance",
                     "python3 parent.py --advance > notes.md",
                     "python3 parent.py --advance && cat parent.json",
                     "cat > rerun.sh <<'SH'\npython3 parent.py --advance\nSH",
                     "cat parent.json"):
            with self.subTest(body=body):
                before = self.observation(225, [1.01], 1)
                after = self.observation(260, [1.01, 1.02], 1)
                after["commands"].append(shlex.join(["/bin/bash", "-c", body]))
                with self.assertRaisesRegex(AssertionError, "No new parent calculation"):
                    parent_overlap([before, after], self.milestones)

    def test_standalone_calculation_allows_native_shell_wrapper(self):
        for body in ("python3 /project/work/parent.py --advance",
                     "/usr/bin/python3 parent.py --advance",
                     "python3 ./parent.py --advance"):
            for command in (body, shlex.join(["/usr/bin/bash", "-lc", body])):
                with self.subTest(command=command):
                    before = self.observation(225, [1.01], 0)
                    after = self.observation(260, [1.01, 1.02], 0)
                    after["commands"] = [command]
                    self.assertEqual(parent_overlap([before, after], self.milestones),
                                     (before, after))

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

    def observations(self, artifacts=None, *, numerical=("check.json",)):
        artifacts = self.artifacts if artifacts is None else artifacts
        report = self.independent + "/CHECK.md"
        text = "## Numerical observations\n" + "\n".join(f"[Table]({name})" for name in numerical)
        selected = numerical_evidence(self.project, self.independent, artifacts, report, text)
        return independent_observations(self.project, self.independent, selected, self.read)

    def calls(self, observations, commands):
        return observation_invocations(self.project, self.independent, self.artifacts,
                                       observations, commands)

    def test_ancillary_records_do_not_define_or_replace_numerical_evidence(self):
        code = self.write("check.py", "# independent check")
        data = self.write("check.json", {"rows": self.rows})
        # Retained final-015 and final-018 audit shapes, plus ordinary metadata.
        # No sidecar assertion is interpreted as proof; canonical fingerprints
        # and frozen manifests are checked by verification.check_unchanged.
        sidecars = {
            "hashes.json": {"check.py": self.artifacts[code]},
            "reexamination_audit.json": {
                "artifacts": [{"path": "check.py", "sha256": self.artifacts[code],
                               "expected": self.artifacts[code], "matches": True}],
                "coarse_simpson_exact_arithmetic_relative_bias_bound": 1.1e-40},
            "recheck_integrity.json": {"check.py": self.artifacts[code],
                                     "response_manifest_matches": [True]},
            "environment.json": {"method": "Simpson", "versions": {"python": "3.10"}},
            "optional_assertions.json": {"response_manifest_matches": [False],
                                         "unassessed": "not an integrity endorsement"}}
        for name, contents in sidecars.items():
            with self.subTest(name=name):
                self.write(name, contents)
                self.assertEqual(self.observations(), {data: self.rows})
                self.assertEqual(set(self.calls(self.observations(), [
                    "python3 check.py --output check.json"])), {data})
                with self.assertRaisesRegex(AssertionError, "Missing independent observation rows"):
                    self.observations(numerical=(name,))
        # Metadata alongside numerical evidence cannot conceal bad observations.
        self.write("check.json", {"rows": [{**self.rows[0], "reference": 9.0}, self.rows[1]]})
        with self.assertRaisesRegex(AssertionError, "Inconsistent"):
            self.observations()

    def test_report_must_explicitly_identify_accepted_local_numerical_tables(self):
        self.write("check.json", {"rows": self.rows})
        report = self.independent + "/CHECK.md"
        for text, message in (
                ("## Observations\n[Data](check.json)", "section"),
                ("## Numerical observations\nOnly a verbal assertion.", "tables"),
                ("## Numerical observations\n[Data](missing.json)", "link"),
                ("## Numerical observations\n[Data](https://example.org/data.json)", "link"),
                ("## Numerical observations\n[Data](inputs/initial/data.json)", "link"),
                ("## Numerical observations\n[Data](../other/data.json)", "link"),
                ("## Numerical observations\n[Code](check.py)", "link")):
            with self.subTest(text=text):
                with self.assertRaisesRegex(AssertionError, message):
                    numerical_evidence(self.project, self.independent, self.artifacts, report, text)
        (self.project / self.independent / "check.json").unlink()
        with self.assertRaisesRegex(AssertionError, "evidence changed"):
            self.observations()

    def test_selected_numerical_bytes_must_match_accepted_fingerprints(self):
        data = self.write("check.json", {"rows": self.rows})
        accepted = dict(self.artifacts)
        # A scientifically compatible replacement still needs reassessment.
        self.write("check.json", {"rows": self.rows, "method": "replacement"})
        with self.assertRaisesRegex(AssertionError, "evidence changed"):
            self.observations(accepted)
        self.assertEqual(self.observations(), {data: self.rows})

    def test_all_numerical_files_are_checked_including_partitioned_stress(self):
        near = self.write("near.json", {"rows": self.rows[:1]})
        stress = self.write("stress.json", {"rows": self.rows[1:]})
        self.assertEqual(set(self.observations(numerical=("near.json", "stress.json"))), {near, stress})
        self.write("stress.json", {"rows": [{**self.rows[1], "reference": 9.0}]})
        with self.assertRaisesRegex(AssertionError, "Inconsistent"):
            self.observations(numerical=("near.json", "stress.json"))

    def test_missing_malformed_and_unknown_evidence_fail(self):
        for data, message in (({}, "Missing"), ([], "Missing"), ({"rows": []}, "Missing"),
                              ("invalid JSON", "Malformed independent numerical table"),
                              ({"rows": "not a table"}, "Missing"),
                              ({"rows": [None]}, "Malformed"),
                              ({"rows": [self.rows[0]]}, "stress"),
                              ({"rows": [self.rows[1]]}, "near-boundary"),
                              ({"rows": [self.rows[0], self.rows[0]]}, "duplicate"),
                              ({"rows": [{**self.rows[0], "reference": float("nan")}]}, "Malformed"),
                              ({"rows": [{**self.rows[0], "reference": 0}]}, "Inconsistent"),
                              ({"method": "Simpson"}, "Missing")):
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
            self.observations(numerical=("check.json", "other.json"))

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
            for writer in ("cat check.py", "cat > note.md <<'MD'\nSaved note\nMD",
                           "python3 - <<'PY'\nprint('Saved note')\nPY"):
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
        for tail in ("sha256sum check.py", "cat > note.md <<'MD'\nSaved note\nMD",
                     "python3 - <<'PY'\nprint('Saved note')\nPY"):
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

    def test_python_heredoc_authoring_then_direct_check_supplies_provenance(self):
        self.write("helper.py", "# trusted checkpoint fixture\n")
        data = self.write("check.json", {"rows": self.rows})
        script = ("from pathlib import Path\nimport sys\n"
                  "Path('executed').write_text(' '.join(sys.argv[1:]))\n")
        self.write("check.py", script)
        body = ("python3 helper.py --check && python3 - <<'PY'\n"
                "from pathlib import Path\n"
                f"Path('check.py').write_text({script!r})\n"
                "Path('note.md').write_text('python3 check.py --a 9 --output check.json')\n"
                "PY\n"
                "python3 helper.py --check && python3 check.py --a 1.01 1.2 --output check.json")
        result = subprocess.run(["/bin/bash", "-c", body],
                                cwd=self.project / self.independent,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.project / self.independent / "executed").read_text(),
                         "--a 1.01 1.2 --output check.json")
        calls = self.calls(self.observations(), [shlex.join(["/bin/bash", "-c", body])])
        self.assertEqual(calls[data]["argv"][2:], ["--a", "1.01", "1.2", "--output", "check.json"])

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
        self.write("initial_integrity.json", {"check.py": "sidecar assertions are unassessed"})
        initial = self.observations(numerical=("near.json", "stress.json"))
        initial_calls = self.calls(initial, [
            "/usr/bin/bash -lc 'python3 helper.py --check && python3 check.py --a 1.01 --output near.json'",
            "/usr/bin/bash -lc 'python3 check.py --a 1.2 --output stress.json'"])
        targeted = self.write("targeted.json", {"rows": self.rows})
        self.write("recheck_integrity.json", {"response_manifest_matches": [True]})
        self.write("environment.json", {"python": sys.version, "method": "trusted fixture"})
        final = self.observations(numerical=("near.json", "stress.json", "targeted.json"))
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
        with self.assertRaisesRegex(AssertionError, "numerical evidence link"):
            self.observations({}, numerical=("targeted.json",))
