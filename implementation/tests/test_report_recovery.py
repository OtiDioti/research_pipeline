"""Real report transaction contention, process loss, immutable artifact damage and exact restoration."""

import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline import report_capture
from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactIOError
from research_pipeline.backup import create_backup, restore_backup, inspect_backup
from research_pipeline.reports import ReportRequest, dumps_request, render_report, manifest_id, source_id
from research_pipeline.store import RecordStore, RevisionConflictError, StoreClosedError, StoreDatabaseError, SubmissionConflictError
from tests.report_fixtures import report_request, populate, ref
from tests.resource_fixtures import reservation, LIMITS
from tests.test_report_resources import funded
from tests.test_store import record, request
from tests.test_vault import child_environment


class ReportRecoveryTests(unittest.TestCase):
    """Prove coherence and recovery using actual SQLite rows, object bytes and original receipts."""

    def setUp(self):
        """Create an isolated private root for independent handles and child processes."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "store"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_scientific_and_resource_writers_wait_through_capture_and_commit(self):
        """Pause twice around real reads; competing BEGINs cannot enter until the report commits."""
        funded(self.store)
        self.store.submit(request("before-work", [record("work")]))
        before_resource = self.store.reserve_resources(reservation("before"))
        first_read, between, release_first, release_between = (threading.Event() for _ in range(4))
        science_begin, resource_begin = threading.Event(), threading.Event()
        results, failures = {}, []

        def seam(point):
            """Hold the reporting writer at both actual read boundaries until competitors reach BEGIN."""
            if point == "after_first_read":
                first_read.set()
                if not release_first.wait(10):
                    raise AssertionError("first report read was not released")
            if point == "between_resource_and_scientific":
                between.set()
                if not release_between.wait(10):
                    raise AssertionError("report collection was not released")

        def reporter():
            """Commit on a thread-confined independent handle and retain its actual receipt."""
            try:
                with RecordStore.open(self.root) as store:
                    results["report"] = store.commit_report(report_request(selection=[ref("work", "research_context")]))
            except BaseException as error:
                failures.append(error)

        def writer(kind):
            """Signal the real SQLite BEGIN callback, then commit scientific or resource changes."""
            try:
                with RecordStore.open(self.root) as store:
                    def trace(sql):
                        """Signal immediately before the competing BEGIN IMMEDIATE executes."""
                        if sql == "BEGIN IMMEDIATE":
                            (science_begin if kind == "science" else resource_begin).set()
                    store._connection.set_trace_callback(trace)
                    if kind == "science":
                        results[kind] = store.submit(request("after-work", [record("work", 2)], {"work": 1}))
                    else:
                        results[kind] = store.reserve_resources(reservation("after"))
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=reporter), threading.Thread(target=writer, args=("science",)),
                   threading.Thread(target=writer, args=("resource",))]
        with patch.object(report_capture, "_fault", side_effect=seam):
            threads[0].start()
            try:
                self.assertTrue(first_read.wait(10))
                threads[1].start()
                self.assertTrue(science_begin.wait(10))
                release_first.set()
                self.assertTrue(between.wait(10))
                threads[2].start()
                self.assertTrue(resource_begin.wait(10))
                self.assertNotIn("science", results)
                self.assertNotIn("resource", results)
            finally:
                release_first.set()
                release_between.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(15)
        self.assertFalse(failures, failures)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        report_receipt = results["report"].receipt
        self.assertGreater(results["science"].event_id, report_receipt.event_id)
        self.assertGreaterEqual(results["resource"].to_dict()["scientific_watermark_event_id"], report_receipt.event_id)
        saved = self.store.read_report("report_initial").to_dict()
        self.assertEqual(saved["resources"]["resource_sequence"], before_resource.to_dict()["sequence"])
        self.assertEqual(saved["scientific"]["watermark"]["event_id"], report_receipt.event_id - 1)
        self.assertEqual(self.store.head("work"), 2)
        self.assertIn(("work", 1), [(r["record_id"], r["revision"]) for r in saved["scientific"]["records"]])
        self.assertNotIn(("work", 2), [(r["record_id"], r["revision"]) for r in saved["scientific"]["records"]])
        live = self.store.inspect_resources(limits=LIMITS).to_dict()
        self.assertEqual(live["resource_sequence"], saved["resources"]["resource_sequence"] + 1)
        self.assertEqual(len(live["reservations"]), 2)

    def test_identical_operation_and_competing_revision_writers(self):
        """Serialize real competing operations: identical retries agree and a distinct same-revision request loses CAS."""
        for same in (True, False):
            root = self.parent / ("same" if same else "different")
            with RecordStore.create(root) as store:
                populate(store)
            held, release, begun = threading.Event(), threading.Event(), threading.Event()
            results, errors = [], []

            def seam(point):
                """Hold only the first writer inside its acquired report transaction."""
                if point == "after_first_read" and threading.current_thread().name == "first-report":
                    held.set()
                    if not release.wait(10):
                        raise AssertionError("report race release missing")

            def worker(second):
                """Submit a real contender after signaling its SQLite BEGIN attempt."""
                try:
                    with RecordStore.open(root) as store:
                        if second:
                            def trace(sql):
                                """Observe the real competing admission attempt."""
                                if sql == "BEGIN IMMEDIATE":
                                    begun.set()
                            store._connection.set_trace_callback(trace)
                        results.append(store.commit_report(report_request("second" if second and not same else "report_initial")))
                except BaseException as error:
                    errors.append(error)

            first = threading.Thread(target=worker, args=(False,), name="first-report")
            second = threading.Thread(target=worker, args=(True,))
            with patch.object(report_capture, "_fault", side_effect=seam):
                first.start()
                try:
                    self.assertTrue(held.wait(10))
                    second.start()
                    self.assertTrue(begun.wait(10))
                finally:
                    release.set()
                    first.join(15)
                    if second.ident is not None:
                        second.join(15)
            self.assertFalse(first.is_alive() or second.is_alive())
            if same:
                self.assertFalse(errors, errors)
                self.assertEqual(results[0], results[1])
            else:
                self.assertEqual(len(results), 1)
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0], RevisionConflictError)

    def test_real_metadata_failures_orphans_and_lost_acknowledgment(self):
        """Interrupt real artifact placement/insertion and actual COMMIT; reconcile only original IDs."""
        for boundary in ("after_artifacts", "before_metadata", "after_first_revision", "after_commit", "deny_commit", "deny_rollback"):
            with self.subTest(boundary=boundary):
                root = self.parent / boundary
                with RecordStore.create(root) as store:
                    populate(store)
                    initial_count = len(store.audit_events())

                    def fail(point):
                        """Inject a bounded interruption at the actual chosen transaction boundary."""
                        if point == boundary or boundary == "deny_rollback" and point == "after_first_revision":
                            raise KeyboardInterrupt(boundary)

                    def authorizer(action, first, second, database, source):
                        """Deny actual COMMIT or ROLLBACK for uncertainty/handle invalidation cases."""
                        denied = (boundary == "deny_commit" and first == "COMMIT" or boundary == "deny_rollback" and first == "ROLLBACK")
                        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and denied else sqlite3.SQLITE_OK

                    store._connection.set_authorizer(authorizer)
                    error = StoreDatabaseError if boundary == "deny_commit" else KeyboardInterrupt
                    with patch("research_pipeline.store._fault", side_effect=fail), patch.object(report_capture, "_fault", side_effect=fail), self.assertRaises(error):
                        store.commit_report(report_request())
                    if boundary == "deny_rollback":
                        with self.assertRaises(StoreClosedError):
                            store.get_report_operation("report_initial")
                    else:
                        store._connection.set_authorizer(None)
                with RecordStore.open(root) as reopened:
                    original = reopened.get_report_operation("report_initial")
                    self.assertEqual(original is not None, boundary == "after_commit")
                    self.assertEqual(len(reopened.audit_events()), initial_count + int(boundary == "after_commit"))
                    self.assertTrue(list((root / "objects").iterdir()))
                    result = reopened.commit_report(report_request())
                    if original is not None:
                        self.assertEqual(result, original)
                    self.assertEqual(reopened.commit_report(report_request()), result)
                    reopened.read_report("report_initial")

    def test_object_io_and_checked_close_fail_before_metadata(self):
        """Actual object synchronization/close failures leave no report metadata and permit original-ID retry."""
        for failure in ("fsync", "close"):
            root = self.parent / failure
            with RecordStore.create(root) as store:
                populate(store)
                original_close, original_sync = os.close, os.fsync
                triggered = []

                def close(descriptor):
                    """Close the real regular-file descriptor before losing its acknowledgment once."""
                    regular = stat.S_ISREG(os.fstat(descriptor).st_mode)
                    original_close(descriptor)
                    if regular and not triggered:
                        triggered.append(True)
                        raise OSError("synthetic checked object close loss")

                def sync(descriptor):
                    """Fail one actual object file durability barrier without weakening later verification."""
                    if stat.S_ISREG(os.fstat(descriptor).st_mode) and not triggered:
                        triggered.append(True)
                        raise OSError("synthetic full disk")
                    return original_sync(descriptor)

                replacement = close if failure == "close" else sync
                with patch("research_pipeline.artifacts.os." + failure, side_effect=replacement), self.assertRaises((ArtifactIOError, OSError)):
                    store.commit_report(report_request())
                self.assertTrue(triggered)
                self.assertIsNone(store.get_report_operation("report_initial"))
                result = store.commit_report(report_request())
                self.assertEqual(store.get_report_operation("report_initial"), result)

    def test_checked_store_close_damage_and_exact_backup_restore(self):
        """Keep historical objects in backups; metadata retries survive missing/corrupt source and close loss."""
        artifact = self.store.put_artifact(b"historical source")
        self.store.submit(request("evidence-object", [record("work", artifact_references=[artifact])]))
        proposal = report_request(selection=[ref("work", "research_context")])
        result = self.store.commit_report(proposal)
        saved_bytes = render_report(self.store.read_report("report_initial"))
        backup = self.parent / "backup"
        create_backup(self.store, backup)
        inspect_backup(backup)
        with restore_backup(backup, self.parent / "restored") as restored:
            self.assertEqual(restored.commit_report(proposal), result)
            self.assertEqual(render_report(restored.read_report("report_initial")), saved_bytes)
            self.assertEqual(restored.read_artifact(artifact), b"historical source")
        source = result.to_dict()["artifacts"]["source.json"]
        path = self.root / "objects" / source["digest"]
        data = path.read_bytes()
        path.unlink()
        self.assertEqual(self.store.commit_report(proposal), result)
        self.assertEqual(self.store.get_report_operation("report_initial"), result)
        with self.assertRaises(ArtifactNotFoundError):
            self.store.read_report("report_initial")
        path.write_bytes(b"x" * len(data))
        path.chmod(0o600)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.read_report("report_initial")
        self.assertEqual(self.store.commit_report(proposal), result)

        class CheckedClose:
            """Lose acknowledgment only after the real SQLite close completes."""

            def __init__(self, connection):
                """Retain the real committed handle for one checked close."""
                self.connection = connection

            def close(self):
                """Perform actual close, then report acknowledgment loss."""
                self.connection.close()
                raise OSError("checked-close acknowledgment lost")

        self.store._connection = CheckedClose(self.store._connection)
        with self.assertRaises(OSError):
            self.store.close()
        self.store._connection = None
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.commit_report(proposal), result)
            with self.assertRaises(SubmissionConflictError):
                reopened.commit_report(report_request(authors=["different"]))

    def test_abrupt_process_loss_reopens_original_operation(self):
        """Exit a real process before metadata, mid-insertion and after actual SQLite COMMIT."""
        program = '''
import os, sys
from research_pipeline import report_capture, store as store_module
from research_pipeline.reports import loads_request
from research_pipeline.store import RecordStore
store = RecordStore.open(sys.argv[1])
def crash(point):
    """Exit without cleanup at a selected actual persistence boundary."""
    if point == sys.argv[3]:
        os._exit(74)
report_capture._fault = crash
store_module._fault = crash
store.commit_report(loads_request(sys.argv[2]))
'''
        for point in ("after_artifacts", "after_first_revision", "after_commit"):
            root = self.parent / ("process-" + point)
            with RecordStore.create(root) as store:
                populate(store)
            result = subprocess.run([sys.executable, "-B", "-c", program, str(root), dumps_request(report_request()), point],
                                    env=child_environment(), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 74, result.stderr)
            with RecordStore.open(root) as store:
                original = store.get_report_operation("report_initial")
                self.assertEqual(original is not None, point == "after_commit")
                committed = store.commit_report(report_request())
                if original is not None:
                    self.assertEqual(committed, original)
                store.read_report("report_initial")
