"""Exercise the synthetic contract and source-local loader, without physics execution."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_pipeline import fixtures
from research_pipeline.fixtures import (
    FixtureValidationError, load_oscillator_fixture, validate_oscillator_fixture,
)

IMPLEMENTATION = Path(__file__).resolve().parents[1]
SOURCE = IMPLEMENTATION / "src"
FIXTURE = IMPLEMENTATION / "evaluations" / "harmonic_quartic_v1.json"


def record(data, identity):
    """Find the fixture's documented revision-one record for focused mutations."""
    return next(r for r in data["records"] if r["id"] == identity and r["revision"] == 1)


def resolve(data, reference):
    """Follow an exact reference independently of the production validator."""
    return next(r for r in data["records"] if (r["id"], r["revision"]) ==
                (reference["id"], reference["revision"]))


class FixtureTests(unittest.TestCase):
    """Check narrative outcomes, corruption rejection, isolation and observed inertness."""

    def setUp(self):
        """Parse fresh real data for each case, avoiding shared mutable fixtures."""
        self.data = load_oscillator_fixture()

    def test_walkthrough_and_history(self):
        """Follow the whole narrative and retain scoped results through the stopped report."""
        walked = [resolve(self.data, ref) for ref in self.data["walkthrough"]]
        self.assertEqual(walked, self.data["records"])
        report = walked[-1]
        self.assertEqual(report["kind"], "partial_report")
        old = resolve(self.data, report["historical_candidate"])
        new = resolve(self.data, report["pending_candidate"])
        self.assertEqual(old["id"], "candidate-both")
        self.assertEqual(new["derived_from"], report["historical_candidate"])
        self.assertNotEqual(old["id"], new["id"])
        self.assertNotEqual(old["context"], new["context"])
        self.assertEqual(resolve(self.data, old["context"])["coefficient_signs"], ["positive", "negative"])
        self.assertEqual(resolve(self.data, new["context"])["coefficient_signs"], ["positive"])
        self.assertEqual((new["endorsement"], new["review_status"], new["support_use"]),
                         ("none", "pending_review", "requires_applicability_review"))
        self.assertEqual(old["disposition"], "provisional")
        review = resolve(self.data, report["review"])
        issue = resolve(self.data, report["issue"])
        self.assertEqual(review["target"], report["historical_candidate"])
        self.assertEqual(review["context"], old["context"])
        self.assertEqual(issue["review"], report["review"])
        negative = resolve(self.data, review["evidence"][-1])
        self.assertEqual((negative["expected_outcome"], negative["scope"]), ("fail", "negative_full_line"))
        self.assertEqual(negative["argument"], review["argument"])
        self.assertEqual(resolve(self.data, review["argument"])["method"], "translated_trial_state")
        self.assertEqual(review["preserved_scopes"], ["formal_harmonic_moments", "finite_projection"])
        self.assertEqual(report["contexts"], [old["context"], new["context"]])
        self.assertEqual(report["obligations"], old["obligations"] + new["obligations"])
        for candidate in (old, new):
            obligations = [resolve(self.data, ref) for ref in candidate["obligations"]]
            self.assertEqual([o["category"] for o in obligations], ["existence_domain", "approximation", "convergence"])
            self.assertTrue(all(o["context"] == candidate["context"] and o["status"] == "unresolved" for o in obligations))
        self.assertEqual([resolve(self.data, ref)["id"] for ref in report["evidence"]],
                         ["harmonic-check", "basis-check", "negative-check"])
        self.assertEqual([resolve(self.data, ref)["method"] for ref in report["justifications"]],
                         ["analytical", "finite_matrix", "translated_trial_state"])
        self.assertEqual(resolve(self.data, report["followup"])["status"], "proposed_requires_new_specification")
        for quantity in ("usage", "cost", "liability"):
            self.assertEqual(report["resources"][quantity], {"status": "not_measured", "value": None})

    def test_expected_snapshot_projection(self):
        """Assert independent before/after oracles, especially completed task versus support."""
        snapshots = [r for r in self.data["records"] if r["kind"] == "snapshot"]
        projection = [(s["stage"], s["operational_status"], s["work_stage"],
                       s["scientific_disposition"], s["applicability"]) for s in snapshots]
        self.assertEqual(projection, [
            ("baseline", "completed", "exploring", "provisional", "unresolved"),
            ("frozen", "completed", "frozen_candidate", "provisional", "requires_reassessment"),
            ("challenged", "completed", "reconciled", "refuted_within_negative_scope", "negative_full_line_inapplicable"),
            ("partial_stop", "completed", "partial_stop", "provisional_pending_review", "requires_applicability_review"),
        ])
        for snapshot in snapshots:
            self.assertEqual(resolve(self.data, snapshot["task"])["expected_outcome"], "completed")
            self.assertEqual(snapshot["support"], [
                {"type": "analytical", "scope": "formal_harmonic_moments", "applicability": "limited_scope_only"},
                {"type": "numerical", "scope": "finite_projection", "applicability": "limited_scope_only"},
            ])
            self.assertEqual((snapshot["novelty"], snapshot["endorsement"]), ("unassessed", "none"))
        self.assertEqual(snapshots[1]["candidate"], snapshots[2]["candidate"])
        self.assertEqual(snapshots[1]["context"], snapshots[2]["context"])
        self.assertEqual(snapshots[1]["evidence"], snapshots[2]["evidence"][:2])
        self.assertIsNone(snapshots[3]["review"])

    def test_isolation_and_nonmutation(self):
        """Independent loads own their nested values and validation does not alter inputs."""
        other = load_oscillator_fixture()
        before = deepcopy(self.data)
        validate_oscillator_fixture(self.data)
        self.assertEqual(self.data, before)
        self.assertEqual(other, self.data)
        record(self.data, "partial-report")["resources"]["usage"]["value"] = 42
        record(self.data, "candidate-both")["justifications"][0]["revision"] = 99
        self.assertEqual(other, before)
        self.assertEqual(load_oscillator_fixture(), before)

    def test_explanatory_changes_and_explicit_revisions(self):
        """Accept prose edits and exact same-kind revisions without literal file matching."""
        record(self.data, "translated-state")["explanation"] += " Additional human inspection is welcome."
        # Snapshot versions may share one identity; exact revisions still distinguish them.
        for revision, name in enumerate(("baseline", "before-challenge", "after-challenge", "partial-stop"), 1):
            target = record(self.data, name)
            target["id"], target["revision"] = "history", revision
            def rewrite(value):
                """Retarget exact links after a deliberate identity/revision relabeling."""
                if type(value) is dict:
                    if value == {"id": name, "revision": 1}:
                        value.update(id="history", revision=revision)
                    else:
                        for child in value.values():
                            rewrite(child)
                elif type(value) is list:
                    for child in value:
                        rewrite(child)
            rewrite(self.data)
        validate_oscillator_fixture(self.data)

    def test_top_level_and_identity_corruption(self):
        """Reject absent metadata, unsupported versions and malformed identities with locations."""
        mutations = [
            (lambda d: d.pop("schema_version"), "missing.*schema_version"),
            (lambda d: d.pop("fixture_version"), "missing.*fixture_version"),
            (lambda d: d["metadata"].pop("classification"), "metadata.*classification"),
            (lambda d: d.update(schema_version=True), "schema_version"),
            (lambda d: d.update(schema_version=2), "schema_version"),
            (lambda d: d.update(fixture_version="2.0.0"), "fixture_version"),
            (lambda d: d.update(records={}), "records.*list"),
            (lambda d: d.update(walkthrough="seed"), "walkthrough.*list"),
            (lambda d: d["records"].append(deepcopy(d["records"][0])), "duplicate identity/revision"),
            (lambda d: record(d, "context-both").update(id="seed", revision=2), "inconsistent kind"),
            (lambda d: record(d, "seed").update(revision=True), "revision.*positive integer"),
            (lambda d: record(d, "seed").update(id=[]), "id.*string"),
            (lambda d: record(d, "seed").update(question=4), "question.*text"),
            (lambda d: record(d, "seed").update(authorization="real"), "unknown.*authorization"),
            (lambda d: record(d, "seed")["context"].update(revision=99), "context.*dangling exact"),
            (lambda d: record(d, "seed")["context"].update(revision=True), "context.*positive integer"),
            (lambda d: record(d, "seed").update(context={"id": "matrix-task", "revision": 1}), "context.*requires kind"),
            (lambda d: record(d, "seed").update(context="context-both"), "context.*object"),
        ]
        for mutate, reason in mutations:
            with self.subTest(reason=reason):
                data = deepcopy(self.data)
                mutate(data)
                with self.assertRaisesRegex(FixtureValidationError, reason):
                    validate_oscillator_fixture(data)

    def test_provenance_and_authority_corruption(self):
        """Reject live, expert, held-out and independent claims on every execution-bearing kind."""
        for identity in ("harmonic-check", "negative-review", "matrix-task", "after-challenge", "partial-report"):
            for field, value in (("execution", "completed"), ("expert_audited", True), ("held_out", True),
                                 ("classification", "held-out"), ("simulation", False), ("synthetic", False),
                                 ("oracle_statement", "An authentic observation"), ("simulated_role", "Dr. Invented")):
                with self.subTest(identity=identity, field=field):
                    data = deepcopy(self.data)
                    record(data, identity)[field] = value
                    with self.assertRaisesRegex(FixtureValidationError, identity + r".*\." + field):
                        validate_oscillator_fixture(data)
            data = deepcopy(self.data)
            record(data, identity).pop("synthetic")
            with self.assertRaisesRegex(FixtureValidationError, "missing.*synthetic"):
                validate_oscillator_fixture(data)
        for field, value in (("independence", "blind"), ("all_authored_together", False)):
            data = deepcopy(self.data)
            record(data, "negative-review")[field] = value
            with self.assertRaisesRegex(FixtureValidationError, field):
                validate_oscillator_fixture(data)

    def test_scenario_corruption(self):
        """Reject erased obligations/history, scope promotion and inherited review authority."""
        mutations = [
            ("after-challenge", "operational_status", "failed"),
            ("matrix-task", "scope", "full_real_line"),
            ("matrix-task", "expected_outcome", "failed"),
            ("after-challenge", "applicability", "applicable"),
            ("after-challenge", "scientific_disposition", "supported"),
            ("after-challenge", "support", [{"type": "formal", "scope": "full_real_line", "applicability": "applicable"}]),
            ("negative-review", "refuted_scope", "none"),
            ("negative-check", "expected_outcome", "pass"),
            ("candidate-positive", "support_use", "incomplete"),
            ("candidate-positive", "endorsement", "endorsed"),
            ("candidate-positive", "derived_from", None),
            ("candidate-positive", "obligations", []),
            ("context-positive", "coefficient_signs", ["positive", "negative"]),
            ("negative-review", "target", {"id": "candidate-positive", "revision": 1}),
            ("negative-review", "context", {"id": "context-positive", "revision": 1}),
            ("partial-stop", "review", {"id": "negative-review", "revision": 1}),
            ("partial-stop", "outstanding_obligations", record(self.data, "candidate-positive")["obligations"]),
            ("after-challenge", "historical_candidate", None),
            ("partial-report", "contexts", [{"id": "context-positive", "revision": 1}]),
            ("partial-report", "evidence", [{"id": "negative-check", "revision": 1}]),
            ("partial-report", "justifications", [{"id": "translated-state", "revision": 1}]),
            ("partial-report", "obligations", record(self.data, "candidate-positive")["obligations"]),
            ("resonance-question", "status", "answer"),
        ]
        for identity, field, value in mutations:
            with self.subTest(identity=identity, field=field):
                data = deepcopy(self.data)
                record(data, identity)[field] = deepcopy(value)
                with self.assertRaisesRegex(FixtureValidationError, field):
                    validate_oscillator_fixture(data)
        data = deepcopy(self.data)
        record(data, "partial-report")["resources"]["liability"]["value"] = 0
        with self.assertRaisesRegex(FixtureValidationError, r"resources.liability.value"):
            validate_oscillator_fixture(data)

    def test_loader_failures(self):
        """Malformed UTF-8/JSON and ambiguous keys fail with source and useful details."""
        cases = [
            (b'{"schema_version":', "line 1"),
            (b'{"schema_version":1,"schema_version":1}', "duplicate key"),
            (b'{"nested":{"x":1,"x":2}}', "key 'x'.*duplicate"),
            (b'\xff', "utf-8"),
            (b'NaN', "nonfinite"), (b'Infinity', "nonfinite"), (b'-Infinity', "nonfinite"),
            (b'[]', "fixture.*object"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "input.json"
            for payload, reason in cases:
                with self.subTest(payload=payload):
                    source.write_bytes(payload)
                    with self.assertRaisesRegex(FixtureValidationError, reason) as caught:
                        load_oscillator_fixture(source)
                    self.assertIn(str(source), str(caught.exception))
            data = deepcopy(self.data)
            record(data, "negative-check")["execution"] = "performed"
            source.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(FixtureValidationError, "negative-check.*execution") as caught:
                load_oscillator_fixture(source)
            self.assertIn(str(source), str(caught.exception))
            missing = Path(temporary) / "missing.json"
            with self.assertRaises(FileNotFoundError) as caught:
                load_oscillator_fixture(missing)
            self.assertEqual(caught.exception.filename, str(missing))
            with self.assertRaises(IsADirectoryError):
                load_oscillator_fixture(Path(temporary))
            # Deterministic unreadability even when a test process has elevated OS rights.
            with patch.object(Path, "read_text", side_effect=PermissionError(13, "denied", str(source))):
                with self.assertRaises(PermissionError) as caught:
                    load_oscillator_fixture(source)
                self.assertEqual(caught.exception.filename, str(source))
            fake_module = Path(temporary) / "src" / "research_pipeline" / "fixtures.py"
            with patch.object(fixtures, "__file__", str(fake_module)):
                with self.assertRaises(FileNotFoundError) as caught:
                    load_oscillator_fixture()
                self.assertEqual(caught.exception.filename, str(Path(temporary) / "evaluations" / FIXTURE.name))
            self.assertEqual(sorted(p.name for p in Path(temporary).iterdir()), ["input.json"])

    def test_fresh_process_inertness_and_relocation(self):
        """Guard import/load effects from unrelated cwd, including a relocated source tree."""
        program = r'''
import contextlib
import io
import json
import os
from pathlib import Path
import sys
attempts = []
reads = []
def guard(event, arguments):
    """Reject audited effects while allowing local reads and recording fixture opens."""
    forbidden = event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn"))
    forbidden = forbidden or event in {
        "os.system", "os.fork", "os.forkpty", "os.posix_spawn", "os.remove",
        "os.rename", "os.mkdir", "os.rmdir", "os.link", "os.symlink", "os.truncate",
        "os.chmod", "os.chown", "os.utime", "os.putenv", "os.unsetenv",
    }
    if event == "open":
        path, mode, flags = arguments
        forbidden = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if str(path).endswith("harmonic_quartic_v1.json"):
            reads.append(str(path))
    if forbidden:
        attempts.append(event)
        raise RuntimeError("fixture effect: " + event)
sys.addaudithook(guard)
out, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    from research_pipeline import fixtures
    assert Path(fixtures.__file__).resolve() == Path(sys.argv[1]).resolve()
    assert reads == [], "import read fixture data"
    first = fixtures.load_oscillator_fixture()
    second = fixtures.load_oscillator_fixture(sys.argv[2])
    assert first == second and first is not second
    fixtures.validate_oscillator_fixture(first)
assert out.getvalue() == err.getvalue() == ""
assert attempts == []
assert len(reads) == 2
'''
        before_bytes = FIXTURE.read_bytes()
        before_entries = sorted(str(p) for p in IMPLEMENTATION.rglob("*"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relocated = root / "relocated"
            shutil.copytree(SOURCE, relocated / "src")
            (relocated / "evaluations").mkdir()
            shutil.copyfile(FIXTURE, relocated / "evaluations" / FIXTURE.name)
            cwd = root / "unrelated"
            cwd.mkdir()
            for implementation in (IMPLEMENTATION, relocated):
                module = implementation / "src" / "research_pipeline" / "fixtures.py"
                explicit = os.path.relpath(implementation / "evaluations" / FIXTURE.name, cwd)
                environment = os.environ.copy()
                environment["PYTHONPATH"] = str(implementation / "src")
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                entries = sorted(str(p) for p in root.rglob("*"))
                result = subprocess.run([sys.executable, "-B", "-c", program, str(module), explicit],
                                        cwd=cwd, env=environment, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((result.stdout, result.stderr), ("", ""))
                self.assertEqual(sorted(str(p) for p in root.rglob("*")), entries)
            self.assertEqual((relocated / "evaluations" / FIXTURE.name).read_bytes(), before_bytes)
        self.assertEqual(FIXTURE.read_bytes(), before_bytes)
        self.assertEqual(sorted(str(p) for p in IMPLEMENTATION.rglob("*")), before_entries)
