"""Actual source durability, contention, crash recovery, backups and malformed stored metadata."""

import hashlib
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

from research_pipeline import lifecycle_report_source as s, lifecycle_source_capture as capture
from research_pipeline import run_control as c
from research_pipeline.artifacts import ArtifactIOError, ArtifactIntegrityError, ArtifactNotFoundError
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.store import RecordStore, StoreDatabaseError, StoreClosedError, SubmissionConflictError
from tests import lifecycle_source_fixtures as f, run_control_fixtures as controls, resource_fixtures as resources
from tests.test_run_control_failures import TransactionConnection
from tests.test_report_resources import funded
from tests.test_store import record, request as submission
from tests.test_vault import child_environment


class SourceRecoveryTests(unittest.TestCase):
    """Reconcile real storage outcomes without treating exceptions as proof of rollback or acknowledgment."""

    def setUp(self):
        """Create real schema-three state before each independent fault or concurrency scenario."""
        temporary = TemporaryDirectory(prefix='source-recovery-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / 'runtime'
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        self.request, self.control = f.populate(self.store)
        self.digest = self.store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']

    def commit(self, store=None):
        """Use the same original input on every attempt, without recapturing an inspection first."""
        return (store or self.store).commit_lifecycle_source('prepare', expected_binding_digest=self.digest, limits=f.LIMITS)

    def test_artifact_before_metadata_rollback(self):
        """An actual placed canonical orphan does not create source state or discharge intent."""
        before = set((self.root / 'objects').iterdir())
        def fault(point):
            """Stop after durable object placement but before metadata admission."""
            if point == 'after_artifacts':
                raise RuntimeError('precommit stop')
        with patch.object(capture, '_fault', fault), self.assertRaises(RuntimeError):
            self.commit()
        self.assertGreater(len(set((self.root / 'objects').iterdir()) - before), 0)
        self.assertIsNone(self.store.get_lifecycle_source_operation('prepare', limits=f.LIMITS))
        self.assertEqual(self.store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['state'], 'durable_intent')
        self.assertEqual(len(self.store.inspect_run_control('run', limits=controls.LIMITS).to_dict()['pending_obligations']), 1)
        self.assertEqual(len(self.commit().to_dict(limits=f.LIMITS)['receipt']['revisions']), 1)

    def test_real_sqlite_commit_denial(self):
        """SQLite's actual authorizer denies COMMIT; reopening proves no source metadata committed."""
        def deny(action, first, second, database, trigger):
            """Deny only the actual COMMIT operation, allowing rollback and ordinary SQL."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and first == 'COMMIT' else sqlite3.SQLITE_OK
        self.store._connection.set_authorizer(deny)
        with self.assertRaises(StoreDatabaseError):
            self.commit()
        self.store._connection.set_authorizer(None)
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertIsNone(reopened.get_lifecycle_source_operation('prepare', limits=f.LIMITS))
            self.assertEqual(reopened.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['state'], 'durable_intent')

    def test_real_commit_lost_acknowledgment_and_failed_rollback(self):
        """Real COMMIT survives lost acknowledgment; failed rollback invalidates the handle."""
        self.store._connection = TransactionConnection(self.store._connection, 'committed')
        with self.assertRaises(StoreDatabaseError):
            self.commit()
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            saved = reopened.get_lifecycle_source_operation('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
            self.assertEqual(self.commit(reopened).to_dict(limits=f.LIMITS), saved)
        other = RecordStore.create(self.parent / 'rollback')
        self.addCleanup(other.close)
        f.populate(other)
        digest = other.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']
        other._connection = TransactionConnection(other._connection, 'rollback_failed')
        with self.assertRaises(StoreDatabaseError):
            other.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=f.LIMITS)
        self.assertIsNone(other._connection)
        with self.assertRaises(StoreClosedError):
            other.get_lifecycle_source_operation('prepare', limits=f.LIMITS)
        with RecordStore.open(self.parent / 'rollback') as reopened:
            self.assertIsNone(reopened.get_lifecycle_source_operation('prepare', limits=f.LIMITS))

    def test_store_close_acknowledgment_loss_preserves_source(self):
        """A real closed SQLite handle can lose its acknowledgment without undoing the committed source."""
        saved = self.commit().to_dict(limits=f.LIMITS)
        class CloseAcknowledgment:
            """Delegate a real handle and lose only its first successful close acknowledgment."""
            def __init__(self, connection):
                """Retain the actual SQLite connection and one-shot failure state."""
                self.connection, self.failed = connection, False
            def close(self):
                """Close SQLite before raising; a cleanup retry is harmless."""
                if not self.failed:
                    self.connection.close()
                    self.failed = True
                    raise sqlite3.OperationalError('synthetic close acknowledgment loss')
        self.store._connection = CloseAcknowledgment(self.store._connection)
        with self.assertRaises(sqlite3.OperationalError):
            self.store.close()
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(self.commit(reopened).to_dict(limits=f.LIMITS), saved)
            self.assertEqual(reopened.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['snapshot_id'], saved['snapshot_id'])

    def test_file_directory_sync_and_checked_object_close(self):
        """Actual artifact descriptors fail file sync, directory sync and checked close before metadata commitment."""
        real_sync, real_close = os.fsync, os.close
        for mode in ('file', 'directory', 'close'):
            failed = []
            def synchronize(fd):
                """Fail the requested artifact synchronization barrier on a real descriptor."""
                is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                if not failed and mode in ('file', 'directory') and is_directory == (mode == 'directory'):
                    failed.append(True)
                    raise OSError('synthetic fsync failure')
                return real_sync(fd)
            def close(fd):
                """Close the real regular file, then lose its checked-close acknowledgment once."""
                regular = stat.S_ISREG(os.fstat(fd).st_mode)
                result = real_close(fd)
                if mode == 'close' and regular and not failed:
                    failed.append(True)
                    raise OSError('synthetic object close acknowledgment')
                return result
            with self.subTest(mode=mode), patch('research_pipeline.artifacts.os.fsync', synchronize), \
                    patch('research_pipeline.artifacts.os.close', close), self.assertRaises((ArtifactIOError, OSError)):
                self.commit()
            self.assertTrue(failed)
            self.assertIsNone(self.store.get_lifecycle_source_operation('prepare', limits=f.LIMITS))

    def test_fresh_process_abrupt_exits_at_object_insert_and_commit(self):
        """Fresh processes actually exit after object placement, metadata insertion and COMMIT, then reopen."""
        self.store.close()
        program = '''
import os, sys
from research_pipeline.store import RecordStore
from research_pipeline import lifecycle_source_capture as module
from tests.lifecycle_source_fixtures import LIMITS
root, digest, point = sys.argv[1:]
def fault(boundary):
    """Exit the real child at a deterministic durability boundary."""
    if boundary == point:
        os._exit(71)
module._fault = fault
with RecordStore.open(root) as store:
    store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=LIMITS)
'''
        for point in ('after_artifacts', 'after_insert', 'after_commit'):
            result = subprocess.run([sys.executable, '-B', '-c', program, str(self.root), self.digest, point],
                env=child_environment(), capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 71, result.stdout + result.stderr)
            with RecordStore.open(self.root) as reopened:
                saved = reopened.get_lifecycle_source_operation('prepare', limits=f.LIMITS)
                if point == 'after_commit':
                    self.assertIsNotNone(saved)
                    self.assertEqual(self.commit(reopened).to_dict(limits=f.LIMITS), saved.to_dict(limits=f.LIMITS))
                else:
                    self.assertIsNone(saved)
                self.assertEqual(len(reopened.inspect_run_control('run', limits=controls.LIMITS).to_dict()['pending_obligations']), 1)

    def test_backup_exact_restore_then_damage_metadata_only_recovery(self):
        """Healthy exact restore preserves bytes, receipt and histories; later object damage only breaks verified read."""
        funded(self.store, sibling=True)
        self.store.reserve_resources(resources.reservation())
        saved = self.commit().to_dict(limits=f.LIMITS)
        original = self.store.read_lifecycle_source('prepare', limits=f.LIMITS)._json
        pending = self.store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
        rows = {name: list(self.store._connection.execute('SELECT * FROM ' + name + ' ORDER BY 1')) for name in
            ('submissions', 'revisions', 'record_links', 'artifact_links', 'audit_events', 'resource_operations', 'resource_accounts', 'resource_reservations')}
        info = create_backup(self.store, self.parent / 'backup')
        self.assertEqual(inspect_backup(self.parent / 'backup'), info)
        with restore_backup(self.parent / 'backup', self.parent / 'restored') as restored:
            self.assertEqual(restored.get_lifecycle_source_operation('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS), saved)
            self.assertEqual(restored.read_lifecycle_source('prepare', limits=f.LIMITS)._json, original)
            self.assertEqual(restored.inspect_run_control('run', limits=controls.LIMITS).to_dict(), pending)
            for name, expected in rows.items():
                self.assertEqual(list(restored._connection.execute('SELECT * FROM ' + name + ' ORDER BY 1')), expected)
            path = self.parent / 'restored' / 'objects' / saved['source_artifact']['digest']
            path.chmod(0o600)
            path.write_bytes(b'x' * saved['source_artifact']['size'])
            self.assertEqual(self.commit(restored).to_dict(limits=f.LIMITS), saved)
            with self.assertRaises(ArtifactIntegrityError):
                restored.read_lifecycle_source('prepare', limits=f.LIMITS)
        self.assertEqual(inspect_backup(self.parent / 'backup'), info)

    def test_actual_sql_damage_and_unrelated_original_member(self):
        """Corrupt actual source rows and an unselected member in a required original batch; recovery refuses both."""
        saved = self.commit().to_dict(limits=f.LIMITS)
        sid = saved['operation_id']
        scenarios = (
            ('UPDATE submissions SET fingerprint=? WHERE submission_id=?', ('a'*64, sid)),
            ('UPDATE submissions SET request_json=? WHERE submission_id=?', (sqlite3.Binary(b'{}'), sid)),
            ('UPDATE revisions SET ordinal=? WHERE submission_id=?', (7, sid)),
            ('UPDATE audit_events SET event_type=? WHERE submission_id=?', ('different', sid)),
            ('UPDATE record_links SET target_kind=? WHERE record_id=? AND ordinal=0', ('claim', saved['source_event']['record_id'])),
        )
        for sql, arguments in scenarios:
            with self.subTest(sql=sql):
                connection = self.store._connection
                connection.execute('PRAGMA ignore_check_constraints=ON')
                connection.execute('BEGIN')
                try:
                    connection.execute(sql, arguments)
                    # Use the connection-owned path to inspect real uncommitted
                    # corruption without nesting a public transaction.
                    reader = capture.controls._Reader(self.store, connection, f.LIMITS.control)
                    with self.assertRaises(s.LifecycleSourceIntegrityError), capture._errors():
                        capture._metadata(reader, 'prepare', f.LIMITS, capture._Workspace(f.LIMITS))
                finally:
                    connection.execute('ROLLBACK')
                    connection.execute('PRAGMA ignore_check_constraints=OFF')
        other = RecordStore.create(self.parent / 'unrelated')
        self.addCleanup(other.close)
        other_request, other_result = f.populate(other)
        other.submit(submission('two-members', [record('selected'), record('unselected')]))
        request = controls.successor(other_request, other_result, 'checkpoint').to_dict()
        request['report']['selection'] = [c.reference('selected', 1, 'report_selection', 'research_context')]
        controls.commit(other, c.RunControlRequest(request), policy=None, evaluated_at=None)
        other._connection.execute("UPDATE revisions SET content_json='{}' WHERE record_id='unselected'")
        with self.assertRaises(s.LifecycleSourceIntegrityError):
            f.commit(other, 'checkpoint')

    def test_identical_concurrent_attempts_and_science_resource_control_interleaving(self):
        """Independent actual writers wait behind the coherent source transaction and identical attempts reconcile."""
        funded(self.store)
        entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
        results, failures = {}, []
        def seam(point):
            """Hold the source after resource replay, before scientific collection."""
            if point == 'between_resource_and_scientific':
                entered.set()
                if not release.wait(15):
                    raise AssertionError('source synchronization timeout')
        def source_writer(name):
            """Use a distinct handle to capture or reconcile the same original source."""
            try:
                with RecordStore.open(self.root) as store:
                    results[name] = self.commit(store).to_dict(limits=f.LIMITS)
            except BaseException as error:
                failures.append(error)
        def later_writer():
            """Attempt real scientific, resource and cancellation writes while capture owns its lock."""
            try:
                with RecordStore.open(self.root) as store:
                    def trace(sql):
                        """Signal the attempted real write transaction before SQLite waits."""
                        if sql == 'BEGIN IMMEDIATE':
                            attempted.set()
                    store._connection.set_trace_callback(trace)
                    store.submit(submission('later-science', [record('later-work')]))
                    store.reserve_resources(resources.reservation())
                    controls.commit(store, controls.successor(self.request, self.control, 'cancel'), policy=None, evaluated_at=None)
                    results['later'] = True
            except BaseException as error:
                failures.append(error)
        threads = [threading.Thread(target=source_writer, args=('first',)),
                   threading.Thread(target=later_writer), threading.Thread(target=source_writer, args=('second',))]
        with patch.object(capture, '_fault', seam):
            threads[0].start()
            try:
                self.assertTrue(entered.wait(15))
                threads[1].start()
                threads[2].start()
                self.assertTrue(attempted.wait(15))
                self.assertNotIn('later', results)
            finally:
                release.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(30)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertFalse(failures, failures)
        self.assertEqual(results['first'], results['second'])
        saved = self.store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        self.assertEqual(saved['control']['disposition'], 'prepared')
        self.assertNotIn('later-work', [r['record_id'] for r in saved['scientific']['records']])
        self.assertEqual(saved['resources']['reservations'], [])
        self.assertEqual(self.store.inspect_run_control('run', limits=controls.LIMITS).to_dict()['disposition'], 'cancelled')
