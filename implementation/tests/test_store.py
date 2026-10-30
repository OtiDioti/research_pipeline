"""Real local SQLite submissions, restart, concurrency and deterministic crash coverage."""

from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactStore, ArtifactIntegrityError, ArtifactNotFoundError
from research_pipeline.domain import (
    ArtifactReference, AuditEvent, CreationProvenance, DomainValidationError,
    RecordEnvelope, RecordReference, Submission, SubmissionReceipt,
)
from research_pipeline.store import (
    RecordStore, RecordNotFoundError, ReferenceResolutionError, RevisionConflictError,
    StoreBusyError, StoreClosedError, StoreDatabaseError, StoreLayoutError, SubmissionConflictError,
)


CREATOR = CreationProvenance("author", "2026-10-30T10:00:00Z", {"source": ["synthetic", {"run": 1}]})
CONTROLLER = CreationProvenance("controller", "2026-10-30T11:00:00Z", {"scope": "local engineering"})


def record(identity="context", revision=1, kind="research_context", **kwargs):
    """Build a non-oscillator graph record with explicit state and attributed nested content."""
    fields = {"content": {"graph": {"vertices": ["a", "b"], "weight": 1.0}, "synthetic": True}, "provenance": CREATOR}
    if kind == "claim":
        fields["scientific_disposition"] = "provisional"
    if kind == "task_specification":
        fields["operational_status"] = "completed"
    fields.update(kwargs)
    return RecordEnvelope(identity, revision, kind, **fields)


def request(identity="submit", records=None, expected=None, provenance=CONTROLLER):
    """Create an explicit batch request, defaulting expectations to initial creation."""
    records = [record()] if records is None else records
    expected = {value.record_id: 0 for value in records} if expected is None else expected
    return Submission(identity, provenance, records, expected)


def graph(artifact):
    """Return all five kinds with forward, self, cyclic and ordered duplicate exact links."""
    edge = RecordReference("evidence", 1, "describes", "evidence")
    return [
        record("claim", kind="claim", record_references=[edge, edge, RecordReference("context", 1, "scope")]),
        record("task", kind="task_specification", record_references=[RecordReference("claim", 1, "output")]),
        record("justification", kind="justification", record_references=[RecordReference("claim", 1, "conclusion")]),
        record("evidence", kind="evidence", artifact_references=[artifact, artifact],
               record_references=[RecordReference("claim", 1, "target"), RecordReference("evidence", 1, "self")]),
        record(),
    ]


class StoreTests(unittest.TestCase):
    """Exercise public results on real private directories and source-local subprocesses."""

    def setUp(self):
        """Create one disposable store per case and register deterministic handle cleanup."""
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "runtime #? space"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def reopen(self):
        """Replace the test handle using only existing on-disk data."""
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)

    def child(self, program, *arguments, expected=0):
        """Run a bounded fresh interpreter with candidate-first imports and no bytecode writes."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root), *arguments],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def metadata(self):
        """Snapshot all committed relational rows using supplemental read-only inspection."""
        connection = sqlite3.connect((self.root / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
        try:
            return {name: connection.execute(f"SELECT * FROM {name} ORDER BY 1,2").fetchall()
                    for name in ("identities", "revisions", "record_links", "artifacts", "artifact_links", "submissions", "audit_events")}
        finally:
            connection.close()

    def test_graph_roundtrip_restart_and_historical_references(self):
        """Round-trip every field and ordering across append, reopen and a fresh process."""
        artifact = self.store.put_artifact(b"graph adjacency: a -> b")
        records = graph(artifact)
        initial = request(records=records)
        receipt = self.store.submit(initial)
        self.assertEqual(receipt.revisions, tuple((r.record_id, r.revision) for r in records))
        self.assertEqual(receipt.provenance, CONTROLLER)
        for item in records:
            self.assertEqual(self.store.get_revision(item.record_id, 1).to_dict(), item.to_dict())
        appended = record("context", 2, content={"graph": {"vertices": ["a", "b", "c"]}})
        self.store.submit(request("append", [appended], {"context": 1}))
        historical = record("new", record_references=[RecordReference("context", 1, "historical")])
        self.store.submit(request("historical", [historical]))
        self.reopen()
        self.assertEqual(self.store.history("context"), (records[-1], appended))
        self.assertEqual(self.store.get_revision("claim", 1).record_references[-1].revision, 1)
        self.assertEqual(self.store.get_revision("new", 1), historical)
        self.assertEqual(self.store.head("context"), 2)
        self.assertEqual(self.store.get_submission("submit"), receipt)
        self.assertEqual(self.store.submit(initial), receipt)
        self.assertEqual(self.store.read_artifact(artifact), b"graph adjacency: a -> b")
        self.assertEqual([event.event_id for event in self.store.audit_events()], [1, 2, 3])
        output = self.child('''
import json, sys
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps({"history": [r.to_dict() for r in store.history("context")],
                      "claim": store.get_revision("claim", 1).to_dict(),
                      "receipt": store.get_submission("submit").to_dict(),
                      "events": [e.to_dict() for e in store.audit_events()],
                      "bytes": store.read_artifact(store.get_revision("evidence", 1).artifact_references[0]).decode()}))
''')
        observed = json.loads(output)
        self.assertEqual(observed["history"], [records[-1].to_dict(), appended.to_dict()])
        self.assertEqual(observed["claim"], records[0].to_dict())
        self.assertEqual(observed["receipt"], receipt.to_dict())
        self.assertEqual(observed["events"], [e.to_dict() for e in self.store.audit_events()])
        self.assertEqual(observed["bytes"], "graph adjacency: a -> b")
        with RecordStore.create(self.parent / "reversed") as other:
            other.put_artifact(b"graph adjacency: a -> b")
            reversed_records = list(reversed(records))
            reversed_receipt = other.submit(request("reverse", reversed_records))
            self.assertEqual(reversed_receipt.revisions, tuple((r.record_id, 1) for r in reversed_records))
            for item in records:
                self.assertEqual(other.get_revision(item.record_id, 1), item)

    def test_detachment_validation_and_value_serialization(self):
        """Requests and returned values isolate mutable trees and reject malformed batches."""
        content = {"nested": [1, {"value": "original"}]}
        details = {"nested": ["original"]}
        provenance = CreationProvenance("writer", "2026-10-30T12:00:00Z", details)
        values = [record(content=content, provenance=provenance)]
        expected = {"context": 0}
        batch = request(records=values, expected=expected)
        content["nested"][1]["value"] = "changed"
        details["nested"].append("changed")
        values.clear()
        expected["context"] = 12
        batch.expected_heads["context"] = 3
        batch.to_dict()["records"][0]["content"].clear()
        self.assertEqual(Submission.from_dict(batch.to_dict()), batch)
        receipt = self.store.submit(batch)
        self.assertEqual(SubmissionReceipt.from_dict(receipt.to_dict()), receipt)
        event = self.store.audit_events()[0]
        self.assertEqual(AuditEvent.from_dict(event.to_dict()), event)
        receipt.provenance.details.clear()
        event.to_dict()["revisions"].clear()
        exposed = self.store.get_revision("context", 1)
        exposed.content["nested"].clear()
        self.assertEqual(self.store.get_revision("context", 1).content, {"nested": [1, {"value": "original"}]})
        self.assertEqual(self.store.get_revision("context", 1).provenance.details, {"nested": ["original"]})
        with self.assertRaises(FrozenInstanceError):
            receipt.event_id = 99
        for records, heads in (([], {}), ([record(), record()], {"context": 0}), ([record()], {}),
                               ([record()], {"context": 0, "extra": 0}), ([record()], {"context": True}),
                               ([record()], {"context": -1}), ([record()], {"context": 2**63}),
                               ([record()], []), ([{}], {"context": 0})):
            with self.subTest(heads=heads), self.assertRaises(DomainValidationError):
                request(records=records, expected=heads)
        for cls, value in ((Submission, batch), (SubmissionReceipt, receipt), (AuditEvent, event)):
            malformed = value.to_dict()
            malformed["extra"] = 1
            with self.assertRaises(DomainValidationError):
                cls.from_dict(malformed)
        forged = request("forged", [record("forged")])
        object.__setattr__(forged.records[0], "revision", True)
        before = self.metadata()
        with self.assertRaises(DomainValidationError):
            self.store.submit(forged)
        self.assertEqual(self.metadata(), before)
        malformed = record("malformed")
        object.__setattr__(malformed, "record_references", ({},))
        with self.assertRaises(DomainValidationError): request(records=[malformed])
        forged = request("malformed", [record("malformed")])
        object.__setattr__(forged.records[0], "provenance", {})
        with self.assertRaises(DomainValidationError): self.store.submit(forged)
        self.assertEqual(self.metadata(), before)

    def test_idempotency_canonical_types_and_meaningful_order(self):
        """Canonical mappings retry; changed attribution, fields, scalar types and order conflict."""
        artifact = self.store.put_artifact(b"ordered")
        second_artifact = self.store.put_artifact(b"second ordered object")
        ordered = graph(artifact)
        evidence = ordered[3].to_dict()
        evidence["artifact_references"].append(second_artifact.to_dict())
        ordered[3] = RecordEnvelope.from_dict(evidence)
        batch = request(records=ordered)
        receipt = self.store.submit(batch)
        reordered = batch.to_dict()
        reordered["expected_heads"] = dict(reversed(list(reordered["expected_heads"].items())))
        reordered["records"][0]["content"] = dict(reversed(list(reordered["records"][0]["content"].items())))
        self.assertEqual(self.store.submit(Submission.from_dict(reordered)), receipt)
        variants = []
        for change in ("actor", "time", "details", "expected", "content", "link", "records", "references", "artifacts", "nested", "creator"):
            changed = batch.to_dict()
            if change == "actor": changed["provenance"]["actor"] = "different"
            elif change == "time": changed["provenance"]["created_at"] = "2026-10-30T12:00:00Z"
            elif change == "details": changed["provenance"]["details"]["extra"] = True
            elif change == "expected": changed["expected_heads"]["context"] = 1
            elif change == "content": changed["records"][0]["content"]["graph"]["weight"] = 1
            elif change == "link": changed["records"][0]["record_references"][0]["revision"] = 2
            elif change == "records": changed["records"].reverse()
            elif change == "references": changed["records"][0]["record_references"].reverse()
            elif change == "artifacts": changed["records"][3]["artifact_references"].reverse()
            elif change == "nested": changed["records"][0]["content"]["graph"]["vertices"].reverse()
            else: changed["records"][0]["provenance"]["actor"] = "other-creator"
            variants.append(Submission.from_dict(changed))
        for stage in ("initial", "reopened", "advanced"):
            if stage == "reopened": self.reopen()
            if stage == "advanced": self.store.submit(request("advance", [record(revision=2)], {"context": 1}))
            before = self.metadata()
            self.assertEqual(self.store.submit(batch), receipt)
            for changed in variants:
                with self.assertRaises(SubmissionConflictError):
                    self.store.submit(changed)
            self.assertEqual(self.metadata(), before)
        for value in (1, 1.0, True):
            identity = "scalar_" + type(value).__name__
            scalar = request(identity, [record(identity, content={"value": value})])
            result = self.store.submit(scalar)
            expected_text = json.dumps({"fingerprint_version": 1, "submission": scalar.to_dict()}, sort_keys=True,
                                       separators=(",", ":"), ensure_ascii=True, allow_nan=False)
            self.assertEqual(result.fingerprint, hashlib.sha256(expected_text.encode()).hexdigest())
            for other in (1, 1.0, True):
                if type(other) is type(value): continue
                with self.assertRaises(SubmissionConflictError):
                    self.store.submit(request(identity, [record(identity, content={"value": other})]))
        self.assertEqual(len([e for e in self.store.audit_events() if e.submission_id == "submit"]), 1)

    def test_atomic_rejections_preserve_every_table_and_existing_history(self):
        """A valid earlier member never masks invalid later heads, kinds, links or objects."""
        artifact = self.store.put_artifact(b"baseline")
        baseline = request("baseline", graph(artifact))
        self.store.submit(baseline)
        cases = [
            (record("context", 2), {"context": 0}, RevisionConflictError),
            (record("context", 3), {"context": 1}, RevisionConflictError),
            (record("context", 1), {"context": 1}, RevisionConflictError),
            (record("context", 2, "evidence"), {"context": 1}, RevisionConflictError),
            (record("bad", record_references=[RecordReference("absent", 1, "target")]), {"bad": 0}, ReferenceResolutionError),
            (record("bad", record_references=[RecordReference("context", 1, "target", "claim")]), {"bad": 0}, ReferenceResolutionError),
            (record("bad", artifact_references=[ArtifactReference("a" * 64, 1)]), {"bad": 0}, ArtifactNotFoundError),
            (record("bad", artifact_references=[ArtifactReference(artifact.digest, artifact.size + 1)]), {"bad": 0}, ArtifactIntegrityError),
            (record("bad", artifact_references=[artifact, ArtifactReference(artifact.digest, 1)]), {"bad": 0}, ArtifactIntegrityError),
        ]
        for invalid, expected, error in cases:
            with self.subTest(error=error, invalid=invalid):
                batch = request("rejected", [record("valid"), invalid], {"valid": 0, **expected})
                before = self.metadata()
                with self.assertRaises(error): self.store.submit(batch)
                self.assertEqual(self.metadata(), before)
                self.assertIsNone(self.store.get_submission("rejected"))
                self.assertIsNone(self.store.head("valid"))
                self.assertEqual(self.store.get_revision("context", 1), baseline.records[-1])
        bad = request("endorsement", [record("valid"), record("bad", kind="claim")])
        object.__setattr__(bad.records[-1], "scientific_disposition", "supported")
        before = self.metadata()
        with self.assertRaises(DomainValidationError): self.store.submit(bad)
        self.assertEqual(self.metadata(), before)
        path = self.root / "objects" / artifact.digest
        path.chmod(0o600)
        path.write_bytes(b"corrupt!")
        path.chmod(0o400)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.submit(request("corrupt", [record("valid"), record("bad", artifact_references=[artifact])]))
        self.assertEqual(self.metadata(), before)

    def test_independent_handles_relevant_heads_and_bounded_lock(self):
        """Competing expectations conflict, unrelated updates succeed, and locks time out usefully."""
        self.store.submit(request())
        with RecordStore.open(self.root) as other:
            self.assertEqual((self.store.head("context"), other.head("context")), (1, 1))
            self.store.submit(request("winner", [record(revision=2)], {"context": 1}))
            with self.assertRaises(RevisionConflictError):
                other.submit(request("loser", [record(revision=2)], {"context": 1}))
            expected = other.head("context")
            self.store.submit(request("unrelated", [record("other")]))
            other.submit(request("fresh", [record(revision=3)], {"context": expected}))
            self.assertEqual(self.store.head("context"), 3)
        before = self.metadata()
        lock = sqlite3.connect(self.root / "metadata.sqlite3", isolation_level=None)
        try:
            lock.execute("BEGIN IMMEDIATE")
            start = time.monotonic()
            with self.assertRaises(StoreBusyError) as caught:
                self.store.submit(request("locked", [record("locked")]))
            elapsed = time.monotonic() - start
            self.assertGreaterEqual(elapsed, 4.5)
            self.assertLess(elapsed, 8.0)
            self.assertIsInstance(caught.exception.__cause__, sqlite3.OperationalError)
            self.assertEqual(self.metadata(), before)
        finally:
            lock.execute("ROLLBACK")
            lock.close()
        self.store.submit(request("locked", [record("locked")]))
        self.assertEqual(self.store.head("locked"), 1)

    def test_failure_boundaries_rollback_or_acknowledgment(self):
        """Caught errors at real transaction boundaries preserve or commit the whole batch."""
        self.store.submit(request("prior"))
        artifact = self.store.put_artifact(b"retained orphan")
        batch = request("fault", [record("first", artifact_references=[artifact]), record("second")])
        self.assertEqual(self.metadata()["artifacts"], [])
        for boundary in ("before_metadata", "after_first_revision"):
            before = self.metadata()
            original = RuntimeError(boundary)

            def fail(point):
                """Fail precisely at the selected real transaction boundary."""
                if point == boundary: raise original

            with patch("research_pipeline.store._fault", side_effect=fail):
                with self.assertRaises(RuntimeError) as caught: self.store.submit(batch)
            self.assertIs(caught.exception, original)
            self.assertEqual(self.metadata(), before)
            self.assertEqual(self.store.read_artifact(artifact), b"retained orphan")
            self.assertIsNone(self.store.get_submission("fault"))
            self.assertEqual(self.store.history("first"), ())
            self.assertEqual(self.store.history("context"), (record(),))
        before_events = len(self.store.audit_events())

        def lost_ack(point):
            """Raise after SQLite has committed to simulate an ordinary lost acknowledgment."""
            if point == "after_commit": raise RuntimeError("lost acknowledgment")

        with patch("research_pipeline.store._fault", side_effect=lost_ack):
            with self.assertRaisesRegex(RuntimeError, "lost acknowledgment"): self.store.submit(batch)
        self.reopen()
        receipt = self.store.get_submission("fault")
        self.assertIsNotNone(receipt)
        self.assertEqual(self.store.submit(batch), receipt)
        self.assertEqual(len(self.store.audit_events()), before_events + 1)
        self.assertEqual(self.store.history("first"), (batch.records[0],))

    def test_abrupt_exit_recovery_and_original_identity_reconciliation(self):
        """Fresh processes recover hot journals or find full commits at deterministic exits."""
        self.store.submit(request("prior"))
        for index, boundary in enumerate(("before_metadata", "after_first_revision", "after_commit")):
            with self.subTest(boundary=boundary):
                identity = "crash_" + str(index)
                prior_events = len(self.store.audit_events())
                data = ("orphan " + identity).encode()
                artifact = ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))
                # A large first revision forces real page spill, leaving a hot rollback
                # journal on mid-write exit instead of relying only on buffered writes.
                batch = request(identity, [record(identity, content={"large": "x" * 3_000_000}, artifact_references=[artifact]), record(identity + "_second")])
                request_file = self.parent / (identity + ".json")
                request_file.write_text(json.dumps(batch.to_dict()), encoding="utf-8")
                self.child('''
import json, os, sys
from research_pipeline.domain import Submission
import research_pipeline.store as module
store = module.RecordStore.open(sys.argv[1])
store.put_artifact(("orphan " + sys.argv[4]).encode())
def crash(point):
    """Exit abruptly at a selected real storage boundary, bypassing Python cleanup."""
    if point == sys.argv[2]: os._exit(73)
module._fault = crash
store.submit(Submission.from_dict(json.load(open(sys.argv[3]))))
raise AssertionError("fault boundary was not reached")
''', boundary, str(request_file), identity, expected=73)
                if boundary == "after_first_revision":
                    self.assertTrue((self.root / "metadata.sqlite3-journal").exists())
                    self.assertGreater((self.root / "metadata.sqlite3-journal").stat().st_size, 512)
                output = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore, SubmissionConflictError
batch = Submission.from_dict(json.load(open(sys.argv[2])))
with RecordStore.open(sys.argv[1]) as store:
    receipt = store.get_submission(batch.submission_id)
    committed = sys.argv[3] == "after_commit"
    assert (receipt is not None) == committed
    assert store.head(batch.records[0].record_id) == (1 if committed else None)
    assert len(store.audit_events()) == int(sys.argv[4])
    assert store.read_artifact(batch.records[0].artifact_references[0]) == ("orphan " + batch.submission_id).encode()
    assert store.get_revision("context", 1).revision == 1
    recovered = store.submit(batch)
    if committed: assert recovered == receipt
    assert store.submit(batch) == recovered
    changed = batch.to_dict()
    changed["provenance"]["actor"] = "conflicting"
    try: store.submit(Submission.from_dict(changed))
    except SubmissionConflictError: pass
    else: raise AssertionError("conflicting identity accepted")
    assert len(store.audit_events()) == int(sys.argv[4]) + (0 if committed else 1)
    print(json.dumps(recovered.to_dict()))
''', str(request_file), boundary, str(prior_events + (boundary == "after_commit")))
                receipt = SubmissionReceipt.from_dict(json.loads(output))
                self.reopen()
                self.assertEqual(self.store.get_submission(identity), receipt)
                self.assertEqual(self.store.get_revision(identity, 1), batch.records[0])
                self.store.submit(request(identity + "_append", [record(identity, 2)], {identity: 1}))
                self.assertEqual(self.store.submit(batch), receipt)

    def test_later_artifact_damage_keeps_metadata_reconciliation_available(self):
        """Exposure verifies bytes while receipts/retries remain truthful historical metadata."""
        artifact = self.store.put_artifact(b"committed bytes")
        batch = request(records=[record(artifact_references=[artifact])])
        receipt = self.store.submit(batch)
        path = self.root / "objects" / artifact.digest
        before = self.metadata()
        for damage in ("corrupt", "truncated", "symlink", "directory", "missing"):
            if path.is_symlink() or path.is_file(): path.unlink()
            elif path.is_dir(): path.rmdir()
            if damage in ("corrupt", "truncated"):
                path.write_bytes(b"X" * artifact.size if damage == "corrupt" else b"short")
                path.chmod(0o400)
            elif damage == "symlink": path.symlink_to(self.root / "metadata.sqlite3")
            elif damage == "directory": path.mkdir()
            error = ArtifactNotFoundError if damage == "missing" else ArtifactIntegrityError
            for operation in (lambda: self.store.get_revision("context", 1), lambda: self.store.history("context"),
                              lambda: self.store.read_artifact(artifact)):
                with self.assertRaises(error): operation()
            self.assertEqual(self.store.head("context"), 1)
            self.assertEqual(self.store.get_submission("submit"), receipt)
            self.assertEqual(self.store.submit(batch), receipt)
            self.assertEqual(len(self.store.audit_events()), 1)
            self.assertEqual(self.metadata(), before)
        self.reopen()
        self.assertEqual(self.store.submit(batch), receipt)
        self.assertFalse(path.exists())

    def test_layout_schema_gate_and_close_contract(self):
        """Reject unsafe or malformed stores without modifying entries or database bytes."""
        before = self.metadata()
        with self.assertRaises(StoreLayoutError): RecordStore.create(self.root)
        self.assertEqual(self.metadata(), before)
        missing = self.parent / "missing"
        with self.assertRaises(StoreLayoutError): RecordStore.open(missing)
        self.assertFalse(missing.exists())
        standalone = self.parent / "standalone"
        ArtifactStore.create(standalone)
        for operation in (RecordStore.create, RecordStore.open):
            with self.assertRaises(StoreLayoutError): operation(standalone)
        self.assertEqual(sorted(p.name for p in standalone.iterdir()), [".staging", "objects"])
        self.store.close()
        database = self.root / "metadata.sqlite3"
        original = database.read_bytes()
        for mode in ("unknown", "zero", "malformed", "keys", "header", "wal"):
            database.write_bytes(original)
            if mode in ("unknown", "zero", "malformed", "keys", "wal"):
                connection = sqlite3.connect(database)
                if mode == "unknown": connection.execute("PRAGMA user_version=9")
                elif mode == "zero": connection.execute("PRAGMA user_version=0")
                elif mode == "malformed": connection.execute("DROP TABLE record_links")
                elif mode == "keys":
                    connection.execute("DROP TABLE artifacts")
                    connection.execute("CREATE TABLE artifacts(digest TEXT, size INTEGER)")
                else: connection.execute("PRAGMA journal_mode=WAL")
                connection.close()
            else: database.write_bytes(b"not sqlite")
            snapshot = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
            entries = sorted(p.name for p in self.root.iterdir())
            with self.subTest(mode=mode), self.assertRaises(StoreLayoutError): RecordStore.open(self.root)
            self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}, snapshot)
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), entries)
        database.write_bytes(original)
        database.chmod(0o644)
        with self.assertRaises(StoreLayoutError): RecordStore.open(self.root)
        database.chmod(0o600)
        saved = self.parent / "saved"
        database.rename(saved)
        for mode in ("symlink", "directory", "fifo", "missing"):
            if mode == "symlink": database.symlink_to(saved)
            elif mode == "directory": database.mkdir()
            elif mode == "fifo": os.mkfifo(database)
            with self.assertRaises(StoreLayoutError): RecordStore.open(self.root)
            if database.is_dir(): database.rmdir()
            elif database.is_symlink() or database.exists(): database.unlink()
        saved.rename(database)
        self.reopen()
        self.assertIsNone(self.store.head("absent"))
        self.assertIsNone(self.store.get_submission("absent"))
        self.assertEqual(self.store.history("absent"), ())
        with self.assertRaises(RecordNotFoundError): self.store.get_revision("absent", 1)
        for identity in ("../bad", "", True):
            for operation in (self.store.head, self.store.history, self.store.get_submission):
                with self.assertRaises(DomainValidationError): operation(identity)
        with self.assertRaises(DomainValidationError): self.store.get_revision("valid", True)
        self.store.close()
        self.store.close()
        for operation in (lambda: self.store.head("valid"), lambda: self.store.submit(request()),
                          lambda: self.store.history("valid"), lambda: self.store.get_revision("valid", 1),
                          lambda: self.store.get_submission("valid"), self.store.audit_events,
                          lambda: self.store.put_artifact(b"x"), lambda: self.store.read_artifact(ArtifactReference("a" * 64, 0))):
            with self.assertRaises(StoreClosedError): operation()

    def test_effective_settings_foreign_keys_and_inert_imports(self):
        """Observe effective operational settings and real FK enforcement without public SQL."""
        import research_pipeline.store as module
        original = module._connect
        observed = []

        def observe(path):
            """Inspect the real newly configured connection before the handle takes ownership."""
            connection = original(path)
            observed.append(tuple(connection.execute("PRAGMA " + name).fetchone()[0]
                                  for name in ("journal_mode", "synchronous", "foreign_keys", "busy_timeout")))
            connection.execute("BEGIN")
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO artifact_links VALUES ('missing',1,0,'digest',1)")
            finally: connection.execute("ROLLBACK")
            return connection

        with patch("research_pipeline.store._connect", side_effect=observe):
            with RecordStore.open(self.root): pass
        self.assertEqual(observed, [("delete", 3, 1, 5000)])
        self.child('''
import os, sys
phase = "import"
def guard(event, args):
    """Reject mutation/network/process effects during fresh storage module import."""
    if phase != "import": return
    forbidden = event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "sqlite3.connect"))
    forbidden |= event in {"os.mkdir", "os.link", "os.chmod", "os.remove", "os.rename"}
    if event == "open": forbidden |= bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
    if forbidden: raise AssertionError(event)
sys.addaudithook(guard)
from research_pipeline.store import RecordStore
phase = "runtime"
with RecordStore.create("caller-relative") as store:
    assert store.head("absent") is None
''')
        self.assertTrue((self.parent / "caller-relative" / "metadata.sqlite3").is_file())

    def test_commit_artifact_barriers_and_failed_sync_leave_orphan(self):
        """Commit syncs each distinct object and its directory, rejecting a failed barrier."""
        artifact = self.store.put_artifact(b"barrier bytes")
        batch = request(records=[record(artifact_references=[artifact, artifact]), record("other", artifact_references=[artifact])])
        before = self.metadata()
        real_sync = os.fsync
        synchronized = []
        object_inode = (self.root / "objects" / artifact.digest).stat().st_ino
        directory_inode = (self.root / "objects").stat().st_ino

        def observe(descriptor):
            """Record real Python artifact barriers and perform the underlying fsync."""
            synchronized.append(os.fstat(descriptor).st_ino)
            real_sync(descriptor)

        def fail_directory(descriptor):
            """Fail the objects-directory barrier after the verified object's real sync."""
            if os.fstat(descriptor).st_ino == directory_inode:
                raise OSError("injected directory sync failure")
            real_sync(descriptor)

        from research_pipeline.artifacts import ArtifactIOError
        with patch("research_pipeline.artifacts.os.fsync", side_effect=fail_directory):
            with self.assertRaises(ArtifactIOError): self.store.submit(batch)
        self.assertEqual(self.metadata(), before)
        self.assertEqual(self.store.read_artifact(artifact), b"barrier bytes")
        with patch("research_pipeline.artifacts.os.fsync", side_effect=observe):
            receipt = self.store.submit(batch)
        self.assertEqual(synchronized, [object_inode, directory_inode])
        self.assertEqual(self.store.submit(batch), receipt)

    def test_interrupt_rollback_and_unusable_handle_invalidation(self):
        """Preserve Python interruption diagnostics and close when real rollback is denied."""
        import research_pipeline.store as module
        original_connect = module._connect
        connections = []

        def capture(path):
            """Capture a real operational connection solely for test authorizer injection."""
            connection = original_connect(path)
            connections.append(connection)
            return connection

        def deny_rollback(action, argument, second, database, source):
            """Deny rollback on a real connection to exercise handle invalidation."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and argument == "ROLLBACK" else sqlite3.SQLITE_OK

        interruption = KeyboardInterrupt("injected after actual write")

        def interrupt(boundary):
            """Interrupt after the first revision has been written to the live transaction."""
            if boundary == "after_first_revision": raise interruption

        self.store.submit(request("prior"))
        before = self.metadata()
        batch = request("interrupt", [record("first"), record("second")])
        for deny in (False, True):
            with patch("research_pipeline.store._connect", side_effect=capture):
                handle = RecordStore.open(self.root)
            try:
                if deny: connections[-1].set_authorizer(deny_rollback)
                with patch("research_pipeline.store._fault", side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt) as caught: handle.submit(batch)
                self.assertIs(caught.exception, interruption)
                if deny:
                    with self.assertRaises(StoreClosedError): handle.head("context")
                else:
                    self.assertEqual(handle.head("context"), 1)
            finally: handle.close()
            self.assertEqual(self.metadata(), before)
        self.reopen()
        self.assertEqual(self.store.history("first"), ())
        self.store.submit(batch)
        self.assertEqual(self.store.head("first"), 1)

    def test_commit_error_advises_original_identity_reconciliation(self):
        """An actual SQLite commit denial preserves its cause and gives recovery instructions."""
        import research_pipeline.store as module
        original_connect = module._connect
        captured = []

        def capture(path):
            """Retain the configured real connection for a narrow transaction authorizer."""
            connection = original_connect(path)
            captured.append(connection)
            return connection

        def deny_commit(action, argument, second, database, source):
            """Reject only the real COMMIT statement, leaving rollback operational."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and argument == "COMMIT" else sqlite3.SQLITE_OK

        with patch("research_pipeline.store._connect", side_effect=capture):
            handle = RecordStore.open(self.root)
        before = self.metadata()
        try:
            captured[-1].set_authorizer(deny_commit)
            with self.assertRaisesRegex(StoreDatabaseError, "original submission_id") as caught:
                handle.submit(request())
            self.assertIsInstance(caught.exception.__cause__, sqlite3.DatabaseError)
        finally: handle.close()
        self.reopen()
        self.assertIsNone(self.store.get_submission("submit"))
        self.assertEqual(self.metadata(), before)
        self.store.submit(request())

    def test_creation_durability_and_schema_initialization_failure(self):
        """Creation syncs the completed database/root; failed DDL commits no partial schema."""
        import research_pipeline.store as module
        root = self.parent / "new"
        real_sync = os.fsync
        observed = []

        def observe(descriptor):
            """Record synchronization inode/type without replacing filesystem behavior."""
            info = os.fstat(descriptor)
            observed.append((info.st_ino, stat.S_ISREG(info.st_mode)))
            real_sync(descriptor)

        with patch("research_pipeline.store.os.fsync", side_effect=observe):
            with RecordStore.create(root): pass
        self.assertEqual(observed[-2:], [((root / "metadata.sqlite3").stat().st_ino, True), (root.stat().st_ino, False)])
        self.assertEqual(stat.S_IMODE((root / "metadata.sqlite3").stat().st_mode), 0o600)
        incomplete = self.parent / "incomplete"
        with patch("research_pipeline.store._SCHEMA", module._SCHEMA[:2] + ("INVALID SQL",)):
            with self.assertRaises(StoreDatabaseError): RecordStore.create(incomplete)
        self.assertTrue((incomplete / "metadata.sqlite3").exists())
        connection = sqlite3.connect((incomplete / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (0,))
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master").fetchall(), [])
        finally: connection.close()
        with self.assertRaises(StoreLayoutError): RecordStore.open(incomplete)

    def test_unsafe_journals_and_foreign_database_are_refused(self):
        """Unsupported sidecars and foreign ownership fail before recovery can mutate files."""
        database = self.root / "metadata.sqlite3"
        original = database.read_bytes()
        for name in ("metadata.sqlite3-wal", "metadata.sqlite3-shm", "metadata.sqlite3-journal"):
            path = self.root / name
            path.symlink_to(database)
            with self.assertRaises(StoreLayoutError): RecordStore.open(self.root)
            self.assertTrue(path.is_symlink())
            self.assertEqual(database.read_bytes(), original)
            path.unlink()
        real_stat = os.fstat
        inode = database.stat().st_ino

        def foreign(descriptor):
            """Report foreign ownership only for the actual opened database inode."""
            info = real_stat(descriptor)
            if info.st_ino == inode:
                values = list(info)
                values[4] = os.geteuid() + 1
                return os.stat_result(values)
            return info

        with patch("research_pipeline.store.os.fstat", side_effect=foreign):
            with self.assertRaises(StoreLayoutError): RecordStore.open(self.root)
        self.assertEqual(database.read_bytes(), original)

    def test_thread_confinement_and_independent_writer_snapshot(self):
        """A shared SQLite handle rejects cross-thread use; separate readers keep snapshots."""
        self.store.submit(request())
        failures = []

        def misuse():
            """Attempt a metadata read through a handle created on the parent thread."""
            try: self.store.head("context")
            except StoreDatabaseError as error: failures.append(error)

        thread = threading.Thread(target=misuse)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0].__cause__, sqlite3.ProgrammingError)
        self.assertEqual(self.store.head("context"), 1)
        # The writer may insert under RESERVED while the reader holds a SHARED
        # snapshot. DELETE journaling makes its COMMIT wait for that reader.
        started = threading.Event()
        completed = threading.Event()
        errors = []

        def append():
            """Use an independent handle to append while a compound read is active."""
            try:
                with RecordStore.open(self.root) as writer:
                    started.set()
                    writer.submit(request("append", [record(revision=2)], {"context": 1}))
                completed.set()
            except BaseException as error: errors.append(error)

        original_envelope = self.store._envelope
        worker = None

        def reconstruct(connection, record_id, revision):
            """Start a competing real writer after history has established its snapshot."""
            nonlocal worker
            worker = threading.Thread(target=append)
            worker.start()
            self.assertTrue(started.wait(timeout=5))
            self.assertFalse(completed.is_set())
            return original_envelope(connection, record_id, revision)

        with patch.object(self.store, "_envelope", side_effect=reconstruct):
            self.assertEqual(self.store.history("context"), (record(),))
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(completed.is_set())
        self.assertEqual([r.revision for r in self.store.history("context")], [1, 2])
