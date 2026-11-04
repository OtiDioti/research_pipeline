"""Real assessment rollback, serialized admission, direct artifacts and lost acknowledgment."""

from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError
from research_pipeline.store import RecordStore, RevisionConflictError, SubmissionConflictError, StoreBusyError
from research_pipeline.tool_assessment import ToolAssessment
from research_pipeline import tool_assessment_store as bounded
from tests.test_store import request
from tests.test_typed_store import ref
from tests.tool_assessment_fixtures import known
from tests.tool_assessment_store_fixtures import AssessmentCase, assessment, document
from tests.tool_registration_fixtures import declaration, rows, tool


class AssessmentPersistenceRecoveryTests(AssessmentCase):
    """Require real private stores and complete user-table comparisons around failures/retries."""

    def test_direct_artifact_missing_corrupt_and_declared_registered_sizes(self):
        """Direct objects use existing verification and registered-size rollback without touching source bytes."""
        self.seed_release()
        data = b"inert assessment configuration"
        artifact = self.store.put_artifact(data)
        doc = document()
        doc["environment"]["artifacts"] = known([artifact.to_dict()])
        batch = request("missing", [assessment(doc)])
        path = self.object_path(artifact)
        path.unlink()
        self.rejects(batch, ArtifactNotFoundError)
        self.store.put_artifact(data)
        path.chmod(0o600)
        path.write_bytes(b"X" * len(data))
        path.chmod(0o400)
        self.rejects(request("corrupt", [assessment(doc)]), ArtifactIntegrityError)
        path.unlink()
        self.store.put_artifact(data)
        wrong = deepcopy(doc)
        wrong["assessment_id"] = "wrong"
        wrong["environment"]["artifacts"]["value"][0]["size"] += 1
        self.rejects(request("wrong-size", [assessment(wrong)]), ArtifactIntegrityError)
        self.rejects(request("batch-size", [assessment(doc), assessment(wrong)]), ArtifactIntegrityError)
        self.store.submit_typed(request("registered", [assessment(doc)]))
        self.damage("UPDATE artifacts SET size=size+1 WHERE digest=?", (artifact.digest,))
        fresh = deepcopy(doc)
        fresh["assessment_id"] = "fresh"
        self.rejects(request("registered-conflict", [assessment(fresh)]), ArtifactIntegrityError)

    def test_transitive_artifact_loss_does_not_block_metadata_only_history(self):
        """Only direct assessment attachments are verified while reached release/source bytes stay untouched."""
        from tests.test_tool_registration_recovery import with_artifact
        data = b"historical release attachment"
        artifact = self.store.put_artifact(data)
        release = self.seed_release(with_artifact("tool", artifact))
        self.store.submit_typed(request("first", [assessment(document(release=release))]))
        self.object_path(artifact).unlink()
        for revision in (2, 3):
            self.store.submit_typed(request("rev-" + str(revision), [assessment(document(release=release), revision)], {"assessment": revision - 1}))
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("tool", 1)
        self.assertIs(type(self.store.get_typed_revision("assessment", 3)[1]), ToolAssessment)

    def test_faults_rollback_mixed_append_new_identity_and_preserve_orphan_bytes(self):
        """Both existing injection seams roll back every row after objects have been durably staged."""
        release = self.seed_release()
        self.store.submit_typed(request("first", [assessment()]))
        for boundary in ("before_metadata", "after_first_revision"):
            data = (boundary + " inert bytes").encode()
            artifact = self.store.put_artifact(data)
            revised = document()
            revised["environment"]["artifacts"] = known([artifact.to_dict()])
            batch = request(boundary, [assessment(document("new-" + boundary)), assessment(revised, 2)],
                            {"assessment": 1, "new-" + boundary: 0})
            def fail(point):
                """Interrupt exactly the selected production seam within this test's transaction."""
                if point == boundary:
                    raise RuntimeError(boundary)
            before = rows(self.root)
            with patch("research_pipeline.store._fault", side_effect=fail), self.assertRaises(RuntimeError):
                self.store.submit_typed(batch)
            self.assertEqual(rows(self.root), before)
            self.assertEqual(self.store.read_artifact(artifact), data)
            self.assertIsNone(self.store.get_submission(boundary))

    def test_real_thread_owned_handles_have_one_cas_winner(self):
        """Independent thread-owned SQLite handles race on the same immutable assessment successor."""
        self.seed_release()
        self.store.submit_typed(request("first", [assessment()]))
        barrier = threading.Barrier(2)
        outcomes = []
        errors = []
        def compete(name):
            """Open/use/close one handle entirely in its owning thread with a finite barrier."""
            try:
                with RecordStore.open(self.root) as store:
                    batch = request(name, [assessment(document(), 2)], {"assessment": 1})
                    barrier.wait(timeout=10)
                    try:
                        receipt = store.submit_typed(batch)
                        outcomes.append((name, receipt))
                    except RevisionConflictError:
                        outcomes.append((name, None))
            except BaseException as error:
                errors.append(error)
        threads = [threading.Thread(target=compete, args=(name,)) for name in ("one", "two")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(sum(receipt is not None for _, receipt in outcomes), 1)
        self.assertEqual(self.store.head("assessment"), 2)
        after = rows(self.root)
        for name, receipt in outcomes:
            self.assertEqual(self.store.get_submission(name), receipt)
            if receipt is None:
                self.assertFalse(any(row[2] == name for row in after["revisions"]))
        self.assertEqual(len(self.store.audit_events()), 3)

    def test_target_and_predecessor_reads_hold_the_committing_write_lock(self):
        """An attempted competing BEGIN IMMEDIATE remains excluded during actual target/history reads."""
        self.seed_release()
        self.store.submit_typed(request("first", [assessment()]))
        for watched in (("tool", 1), ("assessment", 1)):
            observed = threading.Event()
            attempted = threading.Event()
            result = []
            def competitor():
                """Attempt an immediate competing write only after the watched metadata read begins."""
                try:
                    if not observed.wait(10):
                        raise AssertionError("watched read not reached")
                    connection = sqlite3.connect(self.root / "metadata.sqlite3", timeout=0)
                    try:
                        attempted.set()
                        try:
                            connection.execute("BEGIN IMMEDIATE")
                        except sqlite3.OperationalError as error:
                            result.append(error.sqlite_errorcode & 0xff)
                        else:
                            connection.rollback()
                            result.append("unexpected acquisition")
                    finally:
                        connection.close()
                except BaseException as error:
                    result.append(error)
            original = bounded._Budget.read
            def read(budget, connection, key, reader=None):
                """Observe an actual connection-owned metadata read before permitting commit to proceed."""
                if key == watched:
                    observed.set()
                    if not attempted.wait(10):
                        raise AssertionError("competing write not attempted")
                    worker.join(timeout=10)
                    if worker.is_alive():
                        raise AssertionError("competitor did not finish")
                return original(budget, connection, key, reader)
            worker = threading.Thread(target=competitor)
            worker.start()
            current = self.store.head("assessment")
            with patch.object(bounded._Budget, "read", read):
                self.store.submit_typed(request("locked-" + watched[0], [assessment(document(), current + 1)], {"assessment": current}))
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result, [sqlite3.SQLITE_BUSY])

    def test_process_exit_after_commit_and_original_id_recovery_after_damage(self):
        """A real os._exit loses acknowledgment; a fresh interpreter returns exactly one original commit."""
        self.seed_release()
        artifact = self.store.put_artifact(b"direct inert bytes")
        doc = document()
        doc["environment"]["artifacts"] = known([artifact.to_dict()])
        saved = request("saved-original", [assessment(doc)])
        path = self.parent / "request.json"
        path.write_text(json.dumps(saved.to_dict()))
        path.chmod(0o600)
        source = Path(__file__).resolve().parents[1] / "src"
        env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
        crash = '''import json, os, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
import research_pipeline.store as module
request = Submission.from_dict(json.load(open(sys.argv[2])))
def die(point):
    if point == "after_commit": os._exit(73)
module._fault = die
with RecordStore.open(sys.argv[1]) as store: store.submit_typed(request)
'''
        result = subprocess.run([sys.executable, "-B", "-c", crash, str(self.root), str(path)], cwd=self.parent,
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 73, result.stdout + result.stderr)
        receipt = self.store.get_submission("saved-original")
        self.assertIsNotNone(receipt)
        recover = '''import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
request = Submission.from_dict(json.load(open(sys.argv[2])))
with RecordStore.open(sys.argv[1]) as store:
    receipt = store.submit_typed(request)
    assert receipt == store.get_submission(request.submission_id)
    assert len([e for e in store.audit_events() if e.submission_id == request.submission_id]) == 1
    print(json.dumps(receipt.to_dict(), sort_keys=True))
'''
        def recovery():
            """Reconcile in a new process with exact saved inputs and compare complete metadata."""
            before = rows(self.root)
            result = subprocess.run([sys.executable, "-B", "-c", recover, str(self.root), str(path)], cwd=self.parent,
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), receipt.to_dict())
            self.assertEqual(rows(self.root), before)
        recovery()
        self.store.submit_typed(request("later", [assessment(document(), 2)], {"assessment": 1}))
        self.object_path(artifact).unlink()
        # Preserve canonical generic metadata so reopening remains possible while
        # current fresh typed history/pairing would fail on this historical release.
        self.damage("UPDATE revisions SET content_json='{}' WHERE record_id='tool'")
        recovery()
        self.assertEqual(self.store.get_submission("saved-original"), receipt)

    def test_schema_one_refuses_before_target_artifact_work_and_schema_two_admits(self):
        """New assessment kinds require migration while schema two reuses normal passive admission."""
        from research_pipeline.domain import DomainValidationError
        from tests.legacy import create_legacy
        for version in (1, 2):
            root = self.parent / ("schema-" + str(version))
            handle = create_legacy(root) if version == 1 else RecordStore.create(root, schema_version=version)
            with handle as store:
                batch = request("schema-request", [assessment(), tool(declaration())])
                if version == 1:
                    before = rows(root)
                    with patch.object(RecordStore, "_check_batch", side_effect=AssertionError("fresh targets inspected")), \
                            self.assertRaisesRegex(DomainValidationError, "migration"):
                        store.submit_typed(batch)
                    self.assertEqual(rows(root), before)
                else:
                    store.submit_typed(batch)
                    self.assertEqual(store.head("assessment"), 1)

    def test_preview_does_not_reconcile_or_reserve_and_busy_errors_preserve_rows(self):
        """Preview rejects used IDs; a competing write retains StoreBusyError and no losing effects."""
        self.seed_release()
        batch = request("prepared", [assessment()])
        before = rows(self.root)
        self.assertEqual(self.store._check_prepared_typed(batch).to_dict(), batch.to_dict())
        self.assertEqual(rows(self.root), before)
        receipt = self.store.submit_typed(batch)
        with self.assertRaises(SubmissionConflictError):
            self.store._check_prepared_typed(batch)
        self.assertEqual(self.store.submit_typed(batch), receipt)
        before = rows(self.root)
        other = sqlite3.connect(self.root / "metadata.sqlite3", timeout=0)
        self.addCleanup(other.close)
        other.execute("BEGIN IMMEDIATE")
        try:
            # Preserve the product timeout/error translation; no retry is introduced.
            with self.assertRaises(StoreBusyError):
                self.store.submit_typed(request("busy", [assessment(document("busy"))]))
        finally:
            other.rollback()
        self.assertEqual(rows(self.root), before)
