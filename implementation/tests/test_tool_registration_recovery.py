"""Actual Tool commit faults, direct artifacts, serialized CAS and original-ID recovery."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError
from research_pipeline.domain import ArtifactReference
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.store import RecordStore, RevisionConflictError, SubmissionConflictError
from research_pipeline.tool_release import ToolRelease, ToolReleaseValidationError
from tests.test_store import record, request
from tests.test_typed_store import ref
from tests.tool_registration_fixtures import (
    BYTES, ROLES, RegistrationCase, altered, changed, declaration, rows, tool,
)
from tests.tool_release_fixtures import known, rehash


def with_artifact(identity, artifact):
    """Attach one explicit inert dependency artifact to an otherwise remote release."""
    doc = declaration(identity).to_dict()
    doc["reproducibility"]["dependency_artifacts"] = known([artifact.to_dict()])
    return ToolRelease.from_dict(rehash(doc))


class ToolRecoveryTests(RegistrationCase):
    """Observe all durable rows and original receipts after faults and competing writes."""

    def child(self, program, *arguments, expected=0):
        """Run a bounded fresh candidate interpreter outside source, with no bytecode writes."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root), *arguments],
            cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def test_direct_artifact_failures_sizes_and_source_preservation(self):
        """Missing, corrupt and wrong-size direct objects reject atomically; repeated correct pins work."""
        artifacts = self.stage()
        source = self.parent / "source.txt"
        source.write_bytes(BYTES[0])
        release = declaration("local", "local_program", artifacts=True)
        path = self.object_path(artifacts[0])
        path.unlink()
        self.rejects(request("missing", [tool(release)]), ArtifactNotFoundError)
        self.assertEqual(source.read_bytes(), BYTES[0])
        self.store.put_artifact(BYTES[0])
        path.chmod(0o600)
        path.write_bytes(b"X" * len(BYTES[0]))
        path.chmod(0o400)
        self.rejects(request("corrupt", [tool(release)]), ArtifactIntegrityError)
        self.assertEqual(path.read_bytes(), b"X" * len(BYTES[0]))
        path.unlink()
        self.store.put_artifact(BYTES[0])
        wrong = ArtifactReference(artifacts[0].digest, artifacts[0].size + 1)
        self.rejects(request("size", [tool(with_artifact("wrong-size", wrong))]), ArtifactIntegrityError)
        self.rejects(request("batch-size", [tool(with_artifact("correct", artifacts[0])),
                                            tool(with_artifact("wrong", wrong))]), ArtifactIntegrityError)
        doc = release.to_dict()
        doc["reproducibility"]["dependency_artifacts"] = known([wrong.to_dict()])
        with self.assertRaises(ToolReleaseValidationError):
            ToolRelease.from_dict(rehash(doc))
        doc["reproducibility"]["dependency_artifacts"] = known([artifacts[0].to_dict()] * 2)
        repeated = ToolRelease.from_dict(rehash(doc))
        receipt = self.store.submit_typed(request("valid", [tool(repeated), tool(with_artifact("peer", artifacts[0]))]))
        self.assertEqual(receipt.revisions, (("local", 1), ("peer", 1)))
        self.assertEqual(self.store.get_revision("local", 1).artifact_references, artifacts)
        self.assertEqual(source.read_bytes(), BYTES[0])
        for artifact, data in zip(artifacts, BYTES):
            self.assertEqual(self.store.read_artifact(artifact), data)

    def test_registered_size_failure_rolls_back_and_read_checks_bytes_before_codec(self):
        """Registered size conflicts retain artifact errors and typed reads verify selected bytes first."""
        artifact = self.store.put_artifact(b"unchanged object")
        value = with_artifact("tool", artifact)
        self.store.submit_typed(request("first", [tool(value)]))
        self.damage("UPDATE artifacts SET size=? WHERE digest=?", (artifact.size + 1, artifact.digest))
        self.rejects(request("other", [tool(with_artifact("other", artifact))]), ArtifactIntegrityError)
        bad = altered(tool(with_artifact("malformed", artifact)), content={})
        # Restore damage solely to construct the generic inspection fixture.
        self.damage("UPDATE artifacts SET size=? WHERE digest=?", (artifact.size, artifact.digest))
        self.store.submit(request("generic", [bad]))
        self.object_path(artifact).unlink()
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("malformed", 1)
        self.store.put_artifact(b"unchanged object")
        with self.assertRaises(NotTypedContentError):
            self.store.get_typed_revision("malformed", 1)

    def test_rollback_existing_and_new_identities_at_private_seams(self):
        """An interrupted multi-record append removes all metadata effects while staged bytes remain."""
        old = declaration()
        initial = request("initial", [tool(old)])
        receipt = self.store.submit_typed(initial)
        artifact = self.store.put_artifact(b"new unreferenced artifact")
        source = self.parent / "source.txt"
        source.write_bytes(b"source preserved")
        for boundary in ("before_metadata", "after_first_revision"):
            def fail(point):
                """Interrupt the selected existing private seam without altering transaction behavior."""
                if point == boundary:
                    raise RuntimeError(point)
            members = [tool(changed(old, display_name="Amended"), 2), tool(with_artifact("new", artifact))]
            with patch("research_pipeline.store._fault", fail):
                self.rejects(request(boundary, members, {"tool": 1, "new": 0}), RuntimeError)
            self.assertEqual(self.store.head("tool"), 1)
            self.assertEqual(self.store.get_revision("tool", 1), initial.records[0])
            self.assertEqual(self.store.get_submission("initial"), receipt)
            self.assertEqual(self.store.read_artifact(artifact), b"new unreferenced artifact")
            self.assertEqual(source.read_bytes(), b"source preserved")

    def test_independent_handle_cas_race_has_one_winner(self):
        """Two independently opened writers race the same expected head with no loser rows."""
        value = declaration()
        self.store.submit_typed(request("first", [tool(value)]))
        barrier = threading.Barrier(2)
        winners, failures = [], []

        def compete(name):
            """Open inside the owning thread and race one append plus one fresh identity."""
            try:
                with RecordStore.open(self.root) as other:
                    batch = request(name, [tool(changed(value, display_name=name), 2), tool(declaration(name))], {"tool": 1, name: 0})
                    barrier.wait(10)
                    winners.append(other.submit_typed(batch))
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=compete, args=(name,)) for name in ("left", "right")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], RevisionConflictError)
        winner = winners[0].submission_id
        loser = "right" if winner == "left" else "left"
        self.assertIsNone(self.store.head(loser))
        self.assertIsNone(self.store.get_submission(loser))
        self.assertEqual(self.store.head(winner), 1)
        self.assertEqual(self.store.head("tool"), 2)
        self.assertEqual([e.submission_id for e in self.store.audit_events()], ["first", winner])
        self.assertEqual(len(rows(self.root)["revisions"]), 3)

    def test_competing_writer_waits_during_history_inspection(self):
        """Real BEGIN IMMEDIATE serializes predecessor inspection and the competing CAS append."""
        value = declaration()
        for revision in (1, 2):
            self.store.submit_typed(request(f"rev-{revision}", [tool(value, revision)], {"tool": revision - 1}))
        inspecting, attempted, finished = threading.Event(), threading.Event(), threading.Event()
        failures = []
        original = RecordStore._metadata_envelope

        def inspect(store, connection, identity, revision):
            """Pause at an actual predecessor metadata read while the foreground transaction owns the lock."""
            if store is self.store and (identity, revision) == ("tool", 1):
                self.assertTrue(connection.in_transaction)
                inspecting.set()
                self.assertTrue(attempted.wait(10))
                self.assertFalse(finished.is_set())
            return original(store, connection, identity, revision)

        def trace(sql):
            """Observe the competing SQLite BEGIN attempt before it can acquire the held lock."""
            if sql == "BEGIN IMMEDIATE":
                attempted.set()

        def compete():
            """Attempt an exact competing append only after predecessor inspection starts."""
            try:
                with RecordStore.open(self.root) as other:
                    self.assertTrue(inspecting.wait(10))
                    other._connection.set_trace_callback(trace)
                    other.submit_typed(request("competitor", [tool(value, 3)], {"tool": 2}))
            except BaseException as error:
                failures.append(error)
            finally:
                finished.set()

        thread = threading.Thread(target=compete)
        with patch.object(RecordStore, "_metadata_envelope", inspect):
            thread.start()
            try:
                consumer = declaration("consumer", links=[(ROLES[3][0], ref("tool", "child_tool", "tool_release", 2))])
                self.store.submit_typed(request("foreground", [tool(consumer)]))
            finally:
                inspecting.set()
                thread.join(20)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(finished.is_set())
        self.assertEqual([e.submission_id for e in self.store.audit_events()], ["rev-1", "rev-2", "foreground", "competitor"])

    def test_lost_acknowledgment_reopen_and_original_id_after_head_and_byte_changes(self):
        """Actual subprocess exit after COMMIT preserves receipt and retries bypass changed availability."""
        artifact = self.store.put_artifact(b"inert dependency")
        value = with_artifact("tool", artifact)
        initial = request("lost", [tool(value)])
        saved = json.dumps(initial.to_dict())
        self.child('''
import json, os, sys
from research_pipeline import store
from research_pipeline.domain import Submission

def die(point):
    """Exit after durable commit before the caller can receive its acknowledgment."""
    if point == "after_commit":
        os._exit(73)

store._fault = die
with store.RecordStore.open(sys.argv[1]) as handle:
    handle.submit_typed(Submission.from_dict(json.loads(sys.argv[2])))
''', saved, expected=73)
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        receipt = self.store.get_submission("lost")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.revisions, (("tool", 1),))
        self.assertEqual(self.store.history("tool"), initial.records)
        self.assertEqual([e.submission_id for e in self.store.audit_events()], ["lost"])
        self.store.submit_typed(request("advance", [tool(declaration(), 2)], {"tool": 1}))
        path = self.object_path(artifact)
        for mode in ("missing", "corrupt"):
            if mode == "missing":
                path.unlink()
            else:
                path.write_bytes(b"bad")
                path.chmod(0o400)
            before = rows(self.root)
            output = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as handle:
    print(json.dumps(handle.submit_typed(Submission.from_dict(json.loads(sys.argv[2]))).to_dict()))
''', saved)
            self.assertEqual(json.loads(output), receipt.to_dict())
            self.assertEqual(rows(self.root), before)
            with self.assertRaises(SubmissionConflictError):
                self.store.submit_typed(request("lost", [tool(changed(value, display_name="Changed request"))]))
            with self.assertRaises(NotTypedContentError):
                self.store.submit_typed(request("lost", [altered(tool(value), content={})]))
            self.assertEqual(rows(self.root), before)

    def test_reconciliation_precedes_damaged_target_history_and_generic_original(self):
        """Original acknowledgments survive target loss; generic-origin receipts never certify closure."""
        child = declaration("child")
        self.store.submit_typed(request("child-1", [tool(child)]))
        self.store.submit_typed(request("child-2", [tool(child, 2)], {"child": 1}))
        parent = declaration("parent", links=[(ROLES[3][0], ref("child", "child_tool", "tool_release", 2))])
        initial = request("original", [tool(parent)])
        receipt = self.store.submit_typed(initial)
        self.damage("DELETE FROM revisions WHERE record_id=? AND revision=?", ("child", 1))
        before = rows(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(rows(self.root), before)
        self.rejects(request("fresh-history", [tool(declaration("fresh-history", links=[(ROLES[3][0], ref("parent", "child_tool", "tool_release"))]))]))
        self.damage("DELETE FROM revisions WHERE record_id=? AND revision=?", ("child", 2))
        before = rows(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        with self.assertRaises(SubmissionConflictError):
            self.store.submit_typed(request("original", [tool(changed(parent, display_name="Changed"))]))
        self.assertEqual(rows(self.root), before)
        self.rejects(request("fresh-target", [tool(declaration("fresh-target", links=[(ROLES[3][0], ref("parent", "child_tool", "tool_release"))]))]))
        self.store.submit(request("bad-child", [record("bad-child", kind="tool_release")]))
        generic = declaration("generic", links=[(ROLES[3][0], ref("bad-child", "child_tool", "tool_release"))])
        original = request("generic-original", [tool(generic)])
        acknowledgment = self.store.submit(original)
        before = rows(self.root)
        self.assertEqual(self.store.submit_typed(original), acknowledgment)
        self.assertEqual(rows(self.root), before)
        self.assertEqual(self.store.get_typed_revision("generic", 1)[1], generic)
        self.rejects(request("generic-consumer", [tool(declaration("generic-consumer", links=[(ROLES[3][0], ref("generic", "child_tool", "tool_release"))]))]))
