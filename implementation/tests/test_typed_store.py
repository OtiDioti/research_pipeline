"""Typed admission over real durable stores, exact history, recovery and backups."""

from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactStore
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import DomainValidationError, RecordEnvelope, RecordReference, Submission
from research_pipeline.scientific import (
    Claim, Evidence, Justification, NamedAssumption, NotTypedContentError, ResearchContext,
    decode_envelope, encode_envelope,
)
from research_pipeline.store import (
    RecordStore, RecordNotFoundError, ReferenceResolutionError, RevisionConflictError,
    StoreClosedError, SubmissionConflictError,
)
from tests.test_store import CREATOR, CONTROLLER, record, request


def context():
    """Declare complete synthetic scope, preserving mathematical text and ordered limits."""
    return ResearchContext("  Does f(x) = x for x ∈ ℝ?  ", ["f(x) = x"], ["f is declared"],
                           [], [], ["x ∈ ℝ"], [], [], ["ε > 0", "N finite"], [],
                           ["N → ∞", "ε → 0"])


def ref(identity, role, kind, revision=1):
    """Name one exact semantic role without consulting a current head."""
    return RecordReference(identity, revision, role, kind)


def claim(context_id="context", context_revision=1):
    """Create provisional local assumptions and explicit unresolved obligations."""
    return Claim("f(x) = x", "synthetic declaration", ["∀ x ∈ ℝ"],
                 ref(context_id, "context", "research_context", context_revision),
                 [NamedAssumption("A", "Use the declared map")], [], ["Assess scope"])


def envelope(identity, value, revision=1):
    """Encode with explicit creation attribution, distinct from submission attribution."""
    return encode_envelope(identity, revision, value, CREATOR)


def typed_graph(artifact):
    """Build ordered forward roles, two routes, self-input and cross-role artifact reuse."""
    scope = ref("context", "context", "research_context")
    route = Justification(scope, [ref("claim-b", "premise", "claim"), ref("claim-a", "premise", "claim")],
                          [NamedAssumption("A", "Local to this route")], "declared conjunction",
                          [ref("claim-a", "conclusion", "claim")], [ref("evidence", "evidence", "evidence")],
                          ["No support assessed"])
    alternative = replace(route, premises=(), method="independent empty-premise route", evidence=())
    evidence = Evidence([artifact], scope, "declared identity", [ref("claim-a", "target_claim", "claim")],
                        "executed and approved (descriptive text only)",
                        [ref("evidence", "input_record", "evidence"), ref("task", "input_record", None)],
                        [artifact], ["declared scope"], "synthetic observation", [], [], "synthetic")
    return [envelope("route", route), envelope("claim-a", claim()), envelope("evidence", evidence),
            envelope("alternative", alternative), envelope("claim-b", claim()), envelope("context", context())]


class TypedStoreTests(unittest.TestCase):
    """Verify complete public outcomes and no partial rows on rejected typed requests."""

    def setUp(self):
        """Allocate a private outside-source runtime and close handles before cleanup."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "typed #? ü"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def metadata(self, root=None):
        """Snapshot every committed table, including canonical requests and artifact metadata."""
        connection = sqlite3.connect(((root or self.root) / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
        try:
            return {name: connection.execute(f"SELECT * FROM {name} ORDER BY 1,2").fetchall()
                    for name in ("identities", "revisions", "record_links", "artifact_links", "artifacts",
                                 "submissions", "audit_events")}
        finally:
            connection.close()

    def child(self, program, *arguments, expected=0):
        """Run checked, bounded fresh candidate-source Python with bytecode disabled."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source),
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def populate(self):
        """Commit a generic completed task followed by a heterogeneous typed graph."""
        self.store.submit(request("task-submit", [record("task", kind="task_specification")]))
        artifact = self.store.put_artifact(b"synthetic identity observations")
        initial = request("typed", typed_graph(artifact))
        receipt = self.store.submit_typed(initial)
        return artifact, initial, receipt

    def rejects(self, submission, error):
        """Require rejection to preserve every row, old revisions, heads and receipts."""
        before = self.metadata()
        old = self.store.get_revision("context", 1)
        with self.assertRaises(error) as caught:
            self.store.submit_typed(submission)
        self.assertEqual(self.metadata(), before)
        self.assertEqual(self.store.get_revision("context", 1), old)
        if isinstance(submission, Submission):
            self.assertIsNone(self.store.get_submission(submission.submission_id))
            existing = {row[0] for row in before["identities"]}
            for item in submission.records:
                if item.record_id not in existing:
                    self.assertIsNone(self.store.head(item.record_id))
        return caught.exception

    def test_graph_append_reopen_and_fresh_process(self):
        """Preserve complete scope/provenance/order and old context links across revisions."""
        artifact, initial, receipt = self.populate()
        self.assertEqual(receipt.provenance, CONTROLLER)
        self.assertEqual(receipt.revisions, tuple((r.record_id, 1) for r in initial.records))
        for item in initial.records:
            stored, value = self.store.get_typed_revision(item.record_id, 1)
            self.assertEqual(stored, item)
            self.assertEqual(value, decode_envelope(item))
            self.assertEqual(stored.provenance, CREATOR)
            changed = stored.content
            changed.clear()
            value.to_dict().clear()
            stored.provenance.details.clear()
            self.assertEqual(self.store.get_typed_revision(item.record_id, 1), (item, decode_envelope(item)))
        self.assertEqual(self.store.get_revision("task", 1).operational_status, "completed")
        self.assertEqual(self.store.get_revision("claim-a", 1).scientific_disposition, "provisional")
        self.assertEqual(self.store.get_typed_revision("evidence", 1)[1].origin, "synthetic")
        self.assertEqual(self.store.get_revision("evidence", 1).artifact_references, (artifact, artifact))
        self.assertEqual([r.relationship for r in self.store.get_revision("route", 1).record_references],
                         ["context", "premise", "premise", "conclusion", "evidence"])
        changed_scope = replace(context(), parameter_regime=("N finite", "ε > 0"), limit_ordering=("ε → 0", "N → ∞"))
        appended = request("append", [envelope("context", changed_scope, 2),
                                      envelope("claim-a", replace(claim(), statement="Still scoped to old context"), 2)],
                           {"context": 1, "claim-a": 1})
        second = self.store.submit_typed(appended)
        events = [e.to_dict() for e in self.store.audit_events()]
        self.assertEqual([e["submission_id"] for e in events], ["task-submit", "typed", "append"])
        self.assertEqual(events[-1]["revisions"], [["context", 2], ["claim-a", 2]])
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        for item in (*initial.records, *appended.records):
            self.assertEqual(self.store.get_typed_revision(item.record_id, item.revision), (item, decode_envelope(item)))
        self.assertEqual(self.store.get_typed_revision("claim-a", 2)[1].context.revision, 1)
        output = self.child('''
import json, sys
from research_pipeline.store import RecordStore
from research_pipeline.domain import Submission
with RecordStore.open(sys.argv[1]) as s:
    requests = [Submission.from_dict(json.loads(a)) for a in sys.argv[2:]]
    print(json.dumps({"values": [[e.to_dict(), v.to_dict()] for r in requests for x in r.records
                                 for e, v in [s.get_typed_revision(x.record_id, x.revision)]],
                      "receipts": [s.submit_typed(r).to_dict() for r in requests],
                      "events": [e.to_dict() for e in s.audit_events()]}))
''', self.root, json.dumps(initial.to_dict()), json.dumps(appended.to_dict()))
        self.assertEqual(json.loads(output), {
            "values": [[r.to_dict(), decode_envelope(r).to_dict()] for r in (*initial.records, *appended.records)],
            "receipts": [receipt.to_dict(), second.to_dict()], "events": events})

    def test_invalid_targets_and_reached_history_are_atomic(self):
        """Reject missing/wrong/untyped/unsupported/incoherent targets, including reached context."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        artifact = self.store.put_artifact(b"target evidence")
        valid_evidence = Evidence([artifact], ref("context", "context", "research_context"), "property", [],
                                  "method", [], [], [], "result", [], [], "unverified")
        seeds = [record("legacy-context"), record("legacy-claim", kind="claim"), record("legacy-evidence", kind="evidence")]
        for identity, value in (("bad-version", context()), ("bad-format", context()), ("malformed", context()),
                                ("incoherent", claim()), ("unsupported-evidence", valid_evidence)):
            item = envelope(identity, value)
            data = item.to_dict()
            if identity in ("bad-version", "unsupported-evidence"):
                data["content"]["version"] = 99
            elif identity == "bad-format":
                data["content"]["format"] = "unknown"
            elif identity == "malformed":
                del data["content"]["question"]
            else:
                data["record_references"] = []
            seeds.append(RecordEnvelope.from_dict(data))
        seeds.extend([envelope("valid-claim", claim()), envelope("reached", claim("legacy-context"))])
        self.store.submit(request("seed", seeds))
        route = Justification(ref("context", "context", "research_context"), [], [], "method",
                              [ref("legacy-claim", "conclusion", "claim")], [], [])
        cases = [claim("missing"), claim("context", 2), claim("legacy-claim"), claim("legacy-context"),
                 claim("bad-version"), claim("bad-format"), claim("malformed"), route]
        for target in ("incoherent", "reached"):
            cases.append(replace(route, conclusions=(ref(target, "conclusion", "claim"),)))
        for target in ("legacy-evidence", "unsupported-evidence"):
            cases.append(replace(route, conclusions=(ref("valid-claim", "conclusion", "claim"),),
                                 evidence=(ref(target, "evidence", "evidence"),)))
        for index, value in enumerate(cases):
            with self.subTest(index=index):
                error = self.rejects(request(f"reject-{index}", [envelope(f"early-{index}", context()),
                                                               envelope(f"new-{index}", value)]), ReferenceResolutionError)
                self.assertIn("target", str(error))
                self.assertIn("@", str(error))
                if index == 3:
                    self.assertIsInstance(error.__cause__, NotTypedContentError)

    def test_generic_inputs_are_not_scientific_edges(self):
        """Accept arbitrary input kinds, but enforce explicit input kind and constrained reuse."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        self.store.submit(request("legacy", [record("legacy-claim", kind="claim"), record("legacy-context"),
                                             record("legacy-evidence", kind="evidence")]))
        artifact = self.store.put_artifact(b"input")
        value = Evidence([artifact], ref("context", "context", "research_context"), "property", [], "method",
                         [], [], [], "result", [], [], "unverified")
        for index, kind in enumerate(("claim", "research_context", "evidence")):
            identity = {"claim": "legacy-claim", "research_context": "legacy-context", "evidence": "legacy-evidence"}[kind]
            for suffix, declared in (("null", None), ("kind", kind)):
                item = envelope(f"input-{index}-{suffix}", replace(value, input_records=(ref(identity, "input_record", declared),)))
                self.store.submit_typed(request(f"submit-{index}-{suffix}", [item]))
                self.assertEqual(self.store.get_typed_revision(item.record_id, 1)[0], item)
        wrong = replace(value, input_records=(ref("legacy-claim", "input_record", "evidence"),))
        self.rejects(request("wrong-input", [envelope("wrong", wrong)]), ReferenceResolutionError)
        shared = replace(value, input_records=(ref("legacy-claim", "input_record", "claim"),),
                         target_claims=(ref("legacy-claim", "target_claim", "claim"),))
        self.rejects(request("shared-role", [envelope("shared", shared)]), ReferenceResolutionError)

    def test_malformed_members_and_artifacts_leave_all_rows_unchanged(self):
        """Reject forged batches, content/link disagreement, stale CAS and unavailable bytes."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        mismatch = envelope("mismatch", claim()).to_dict()
        mismatch["record_references"] = []
        malformed = envelope("malformed", context()).to_dict()
        malformed["content"]["question"] = 7
        unsupported = envelope("unsupported", context()).to_dict()
        unsupported["content"]["version"] = 2
        members = [record("generic"), record("task", kind="task_specification"),
                   RecordEnvelope.from_dict(mismatch), RecordEnvelope.from_dict(malformed),
                   RecordEnvelope.from_dict(unsupported)]
        for index, member in enumerate(members):
            self.rejects(request(f"bad-{index}", [envelope(f"early-{index}", context()), member]), DomainValidationError)
        self.rejects(None, DomainValidationError)
        forged = request("forged", [envelope("forged", context())])
        object.__setattr__(forged.records[0], "provenance", object())
        # Forged values are rejected during defensive reconstruction, before metadata access.
        before = self.metadata()
        with self.assertRaises(DomainValidationError):
            self.store.submit_typed(forged)
        self.assertEqual(self.metadata(), before)
        for corruption in ("empty", "duplicate", "expectations"):
            forged = request("forged-batch", [envelope("forged", context())])
            if corruption == "empty":
                object.__setattr__(forged, "records", ())
            elif corruption == "duplicate":
                object.__setattr__(forged, "records", forged.records * 2)
            else:
                object.__setattr__(forged, "_expected_heads_json", "{}")
            with self.subTest(corruption=corruption), self.assertRaises(DomainValidationError):
                self.store.submit_typed(forged)
            self.assertEqual(self.metadata(), before)
            self.assertIsNone(self.store.head("forged"))
            self.assertIsNone(self.store.get_submission("forged-batch"))
        self.rejects(request("stale", [envelope("early", context()), envelope("context", context(), 2)],
                             {"early": 0, "context": 0}), RevisionConflictError)
        for index, damage in enumerate(("missing", "corrupt")):
            artifact = self.store.put_artifact(damage.encode())
            path = self.root / "objects" / artifact.digest
            if damage == "missing":
                path.unlink()
            else:
                path.chmod(0o600)
                path.write_bytes(b"wrong bytes")
                path.chmod(0o400)
            evidence = Evidence([artifact], ref("context", "context", "research_context"), "property", [],
                                "method", [], [], [], "result", [], [], "synthetic")
            self.rejects(request(f"artifact-{index}", [envelope(f"early-artifact-{index}", context()),
                                                      envelope(f"evidence-{index}", evidence)]),
                         ArtifactNotFoundError if damage == "missing" else ArtifactIntegrityError)

    def test_exact_retry_precedes_all_target_and_artifact_reads(self):
        """Reconcile original receipts after heads advance and direct bytes disappear or corrupt."""
        artifact, initial, receipt = self.populate()
        self.store.submit_typed(request("advance", [envelope("context", context(), 2)], {"context": 1}))
        reordered = initial.to_dict()
        reordered["expected_heads"] = dict(reversed(list(reordered["expected_heads"].items())))
        reordered["records"][0]["content"] = dict(reversed(list(reordered["records"][0]["content"].items())))
        before = self.metadata()
        for damage in ("corrupt", "missing"):
            path = self.root / "objects" / artifact.digest
            if damage == "corrupt":
                path.chmod(0o600)
                path.write_bytes(b"corrupt")
                path.chmod(0o400)
            else:
                path.unlink()
            with patch.object(RecordStore, "_check_batch", side_effect=AssertionError("batch reached")), \
                    patch.object(RecordStore, "_check_scientific_targets", side_effect=AssertionError("targets reached")), \
                    patch.object(ArtifactStore, "verify", side_effect=AssertionError("bytes reached")):
                self.assertEqual(self.store.submit_typed(Submission.from_dict(reordered)).to_dict(), receipt.to_dict())
                for variant in ("order", "content-order", "attribution", "expectation"):
                    changed = initial.to_dict()
                    if variant == "order":
                        changed["records"].reverse()
                    elif variant == "content-order":
                        route = decode_envelope(initial.records[0])
                        changed["records"][0] = envelope("route", replace(route, premises=tuple(reversed(route.premises)))).to_dict()
                    elif variant == "attribution":
                        changed["provenance"]["actor"] = "different"
                    else:
                        changed["expected_heads"]["context"] = 1
                    with self.assertRaises(SubmissionConflictError):
                        self.store.submit_typed(Submission.from_dict(changed))
            self.assertEqual(self.metadata(), before)
            self.assertEqual(self.store.get_submission("typed"), receipt)

    def test_historical_evidence_metadata_and_generic_original_retry(self):
        """New relationships need coherent historical metadata, not transitive byte availability."""
        artifact, initial, _ = self.populate()
        route = envelope("historical-route", decode_envelope(initial.records[0]))
        submission = request("historical-route-submit", [route])
        receipt = self.store.submit_typed(submission)
        (self.root / "objects" / artifact.digest).unlink()
        before = self.metadata()
        with patch.object(RecordStore, "_metadata_envelope", side_effect=AssertionError("target read")):
            self.assertEqual(self.store.submit_typed(submission), receipt)
        self.assertEqual(self.metadata(), before)
        self.store.submit_typed(request("new-route", [envelope("new-route", decode_envelope(route))]))
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("evidence", 1)
        # A generic historical commit is acknowledged, never retroactively certified.
        self.store.submit(request("legacy", [record("legacy")]))
        raw = request("raw-typed", [envelope("raw-claim", claim("legacy"))])
        original = self.store.submit(raw)
        with patch.object(RecordStore, "_check_scientific_targets", side_effect=AssertionError("admission reached")):
            self.assertEqual(self.store.submit_typed(raw), original)
        self.rejects(request("new-invalid", [envelope("new-invalid", claim("legacy"))]), ReferenceResolutionError)

    def test_typed_reads_keep_generic_history_and_direct_artifact_contract(self):
        """Typed reads distinguish missing/generic/unsupported/incoherent data and closed handles."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        unsupported = envelope("unsupported", context()).to_dict()
        unsupported["content"]["version"] = 2
        mismatch = envelope("mismatch", claim()).to_dict()
        mismatch["record_references"] = []
        for item, error in ((record("generic"), NotTypedContentError),
                            (RecordEnvelope.from_dict(unsupported), DomainValidationError),
                            (RecordEnvelope.from_dict(mismatch), DomainValidationError)):
            self.store.submit(request(item.record_id, [item]))
            with self.assertRaises(error):
                self.store.get_typed_revision(item.record_id, 1)
            self.assertEqual(self.store.get_revision(item.record_id, 1), item)
        with self.assertRaises(RecordNotFoundError):
            self.store.get_typed_revision("context", 2)
        artifact = self.store.put_artifact(b"direct attachment")
        evidence = Evidence([artifact], ref("context", "context", "research_context"), "property", [],
                            "method", [], [], [], "result", [], [], "synthetic")
        self.store.submit_typed(request("direct", [envelope("direct", evidence)]))
        path = self.root / "objects" / artifact.digest
        path.chmod(0o600)
        path.write_bytes(b"corruption")
        path.chmod(0o400)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.get_typed_revision("direct", 1)
        self.store.close()
        with self.assertRaises(StoreClosedError):
            self.store.get_typed_revision("context", 1)
        with self.assertRaises(StoreClosedError):
            self.store.submit_typed(request("closed", [envelope("new", context())]))

    def test_independent_handles_cas_and_exact_old_context(self):
        """Independent sampled heads cannot authorize stale writes or rebind old context scope."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        with RecordStore.open(self.root) as other:
            sampled = self.store.head("context")
            self.assertEqual(other.head("context"), sampled)
            other.submit_typed(request("winner", [envelope("context", replace(context(), question="New scope"), 2)],
                                      {"context": sampled}))
            self.rejects(request("loser", [envelope("early", context()), envelope("context", context(), 2)],
                                 {"early": 0, "context": sampled}), RevisionConflictError)
            self.store.submit_typed(request("old-context", [envelope("historical", claim())]))
            self.assertEqual(other.get_typed_revision("historical", 1)[1].context.revision, 1)

    def test_admission_holds_serialized_transaction(self):
        """Coordinate a competing writer while typed target inspection owns the write lock."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        inspecting = threading.Event()
        attempted = threading.Event()
        finished = threading.Event()
        failures = []
        original = RecordStore._check_scientific_targets

        def inspect(store, connection, submission, required):
            """Pause only the foreground admission after BEGIN IMMEDIATE, before metadata insertion."""
            if submission.submission_id == "foreground":
                self.assertTrue(connection.in_transaction)
                inspecting.set()
                self.assertTrue(attempted.wait(5))
                self.assertFalse(finished.is_set())
            return original(store, connection, submission, required)

        def competitor():
            """Attempt an independent head advance precisely when foreground admission is active."""
            try:
                with RecordStore.open(self.root) as other:
                    self.assertTrue(inspecting.wait(5))
                    # Trace runs immediately before SQLite attempts the locked BEGIN.
                    other._connection.set_trace_callback(lambda sql: attempted.set() if sql == "BEGIN IMMEDIATE" else None)
                    other.submit_typed(request("competitor", [envelope("context", context(), 2)], {"context": 1}))
            except BaseException as error:
                failures.append(error)
            finally:
                finished.set()

        thread = threading.Thread(target=competitor)
        with patch.object(RecordStore, "_check_scientific_targets", inspect):
            thread.start()
            try:
                self.store.submit_typed(request("foreground", [envelope("historical", claim())]))
            finally:
                inspecting.set()
                thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(finished.is_set())
        self.assertEqual([e.submission_id for e in self.store.audit_events()], ["scope", "foreground", "competitor"])
        self.assertEqual(self.store.get_typed_revision("historical", 1)[1].context.revision, 1)

    def test_fault_boundaries_and_fresh_process_lost_acknowledgment(self):
        """Typed requests use existing rollback seams and reconcile committed lost acknowledgments."""
        self.store.submit_typed(request("scope", [envelope("context", context())]))
        for boundary in ("before_metadata", "after_first_revision"):
            def fail(point):
                """Raise at the selected existing commit boundary to exercise transaction rollback."""
                if point == boundary:
                    raise RuntimeError(boundary)
            with patch("research_pipeline.store._fault", fail):
                self.rejects(request(boundary, [envelope(boundary, context()), envelope(boundary + "-claim", claim())]), RuntimeError)
        initial = request("lost-ack", [envelope("lost", claim())])
        self.child('''
import json, os, sys
from research_pipeline import store
from research_pipeline.domain import Submission
s = store.RecordStore.open(sys.argv[1])
def die(point):
    """Lose acknowledgment after durable metadata commit."""
    if point == "after_commit":
        os._exit(73)
store._fault = die
s.submit_typed(Submission.from_dict(json.loads(sys.argv[2])))
''', self.root, json.dumps(initial.to_dict()), expected=73)
        receipt = self.store.get_submission("lost-ack")
        self.assertIsNotNone(receipt)
        before = self.metadata()
        result = self.child('''
import json, sys
from research_pipeline.store import RecordStore
from research_pipeline.domain import Submission
with RecordStore.open(sys.argv[1]) as s:
    print(json.dumps(s.submit_typed(Submission.from_dict(json.loads(sys.argv[2]))).to_dict()))
''', self.root, json.dumps(initial.to_dict()))
        self.assertEqual(json.loads(result), receipt.to_dict())
        self.assertEqual(self.metadata(), before)

    def test_backup_preserves_typed_and_generic_requests(self):
        """Existing backup mechanics preserve exact typed history and unsupported generic content."""
        artifact, initial, receipt = self.populate()
        self.store.submit_typed(request("advance", [envelope("context", replace(context(), question="Changed scope"), 2)],
                                        {"context": 1}))
        future = envelope("future", context()).to_dict()
        future["content"]["version"] = 99
        legacy = [record("legacy"), RecordEnvelope.from_dict(future)]
        self.store.submit(request("generic", legacy))
        before = self.metadata()
        destination = self.parent / "backup"
        restored_root = self.parent / "restored"
        info = create_backup(self.store, destination)
        self.assertEqual(inspect_backup(destination), info)
        with restore_backup(destination, restored_root) as restored:
            self.assertEqual(self.metadata(restored_root), before)
            self.assertEqual(restored.audit_events(), self.store.audit_events())
            for identity in ("context", "claim-a", "claim-b", "evidence", "route", "alternative", "task", "legacy", "future"):
                self.assertEqual(restored.history(identity), self.store.history(identity))
            for item in legacy:
                self.assertEqual(restored.get_revision(item.record_id, 1), item)
            with self.assertRaises(DomainValidationError):
                restored.get_typed_revision("future", 1)
            self.assertEqual(restored.submit_typed(initial), receipt)
        result = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as s:
    initial = Submission.from_dict(json.loads(sys.argv[2]))
    print(json.dumps({"values": [[e.to_dict(), v.to_dict()] for r in initial.records
                                 for e, v in [s.get_typed_revision(r.record_id, r.revision)]],
                      "receipt": s.submit_typed(initial).to_dict(),
                      "context2": s.get_typed_revision("context", 2)[0].to_dict()}))
''', restored_root, json.dumps(initial.to_dict()))
        self.assertEqual(json.loads(result), {
            "values": [[r.to_dict(), decode_envelope(r).to_dict()] for r in initial.records],
            "receipt": receipt.to_dict(), "context2": self.store.get_revision("context", 2).to_dict()})
        (restored_root / "objects" / artifact.digest).unlink()
        with RecordStore.open(restored_root) as restored:
            self.assertEqual(restored.submit_typed(initial), receipt)
            self.assertEqual(restored.get_submission("typed"), receipt)
            self.assertEqual(restored.audit_events(), self.store.audit_events())
            with self.assertRaises(ArtifactNotFoundError):
                restored.get_typed_revision("evidence", 1)
        self.assertEqual(self.metadata(restored_root), before)

    def test_documented_persistence_example(self):
        """Execute the actual documented Python block outside source, preventing example drift."""
        document = (Path(__file__).resolve().parents[2] / "docs" / "typed-content.md").read_text()
        section = document.split("## Runnable synthetic persistence example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
