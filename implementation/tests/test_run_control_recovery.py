"""Independent-handle/process races, acknowledgment loss and exact backup recovery for control."""

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c, operating_authority as a
from research_pipeline.backup import create_backup, restore_backup
from research_pipeline.store import RecordStore, RevisionConflictError
from tests import run_control_fixtures as f
from tests.test_vault import child_environment


class ControlRecoveryTests(unittest.TestCase):
    """Use real SQLite serialization and explicit synchronization without sleep-based evidence."""

    def setUp(self):
        """Create disposable prepared input shared through independent runtime handles."""
        temporary = TemporaryDirectory(prefix='control-recovery-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / 'runtime'
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        self.request = f.populate(self.store)

    def test_competing_successors_pause_cancel_and_duplicate_delivery(self):
        """Concurrent real writers produce one successor or exactly the same original result."""
        first = f.commit(self.store, self.request)
        for duplicate in (False, True):
            if duplicate:
                current = self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()
                operation = current['transitions'][-1]['envelope']['content']['request']['operation_id']
                prior = self.store.get_run_control_operation(operation, limits=f.LIMITS)
                choices = [f.successor(self.request, prior, 'checkpoint', operation='duplicate')] * 2
            else:
                choices = [f.successor(self.request, first, action) for action in ('pause', 'cancel')]
            barrier = threading.Barrier(2, timeout=10)
            results, failures = [], []

            def writer(index):
                """Use a thread-owned SQLite handle and synchronize immediately before delivery."""
                try:
                    with RecordStore.open(self.root) as store:
                        barrier.wait()
                        results.append(f.commit(store, choices[index]))
                except BaseException as error:
                    failures.append(error)

            threads = [threading.Thread(target=writer, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(30)
                self.assertFalse(thread.is_alive())
            if duplicate:
                self.assertEqual(failures, [])
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0], results[1])
            else:
                self.assertEqual(len(results), 1)
                self.assertEqual(len(failures), 1)
                self.assertIsInstance(failures[0], RevisionConflictError)
        self.assertEqual(len(self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()['pending_obligations']), 3)

    def test_revocation_and_preparation_both_serialization_orders(self):
        """A revocation serialized first denies preparation; preparation first retains historical pending intent."""
        for first_kind in ('revoke', 'prepare'):
            if first_kind == 'prepare':
                self.store.close()
                self.root = self.parent / 'second-runtime'
                self.store = RecordStore.create(self.root, schema_version=3)
                self.addCleanup(self.store.close)
                self.request = f.populate(self.store)
            prior = self.store.get_revision(a.stream_id('synthetic', 'project'), 1)
            binding = a.OperatingBinding(prior.content['decision']['binding'])
            revoked = f.authority.sign(f.authority.decision(binding, revision=2, previous=prior, outcome='revoke', operation='revoke'))
            inserted, attempted = threading.Event(), threading.Event()
            results, failures = {}, {}

            def seam(point):
                """Hold the first writer after actual insertion until the competing BEGIN is attempted."""
                if point == 'after_first_revision' and threading.current_thread().name == first_kind:
                    inserted.set()
                    if not attempted.wait(10):
                        raise AssertionError('competing writer never attempted BEGIN')

            def writer(kind):
                """Record real BEGIN attempts with thread-local independent connections."""
                try:
                    with RecordStore.open(self.root) as store:
                        if kind != first_kind:
                            if not inserted.wait(10):
                                raise AssertionError('first writer never inserted')

                            def trace(sql):
                                """Signal SQLite's actual competing write-lock attempt."""
                                if sql == 'BEGIN IMMEDIATE':
                                    attempted.set()

                            store._connection.set_trace_callback(trace)
                        if kind == 'prepare':
                            results[kind] = f.commit(store, self.request)
                        else:
                            results[kind] = store.commit_operating_decision(revoked, policy=f.authority.policy(),
                                evaluated_at=f.authority.TIME, limits=f.authority.LIMITS)
                except BaseException as error:
                    failures[kind] = error

            threads = [threading.Thread(target=writer, args=(kind,), name=kind) for kind in ('prepare', 'revoke')]
            with patch('research_pipeline.store._fault', seam):
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(30)
                    self.assertFalse(thread.is_alive())
            self.assertNotIn('revoke', failures)
            if first_kind == 'revoke':
                self.assertIsInstance(failures.get('prepare'), c.RunControlPermissionError)
                self.assertIsNone(self.store.head(c.control_id('run')))
            else:
                self.assertEqual(failures, {})
                original = results['prepare']
                self.assertEqual(f.commit(self.store, self.request, policy=None, evaluated_at=None), original)
                inspected = self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()
                self.assertFalse(inspected['ordinary_work_allowed'])
                self.assertEqual(len(inspected['pending_obligations']), 1)

    def test_process_exit_and_checked_close_acknowledgment_loss(self):
        """Actual process exit before/after COMMIT and checked-close loss preserve same-ID recovery."""
        saved = self.parent / 'request.json'
        saved.write_text(c.dumps_request(self.request))
        program = '''
import os, sys
from pathlib import Path
from research_pipeline import run_control as c
from research_pipeline.store import RecordStore
import research_pipeline.store as module
from tests.run_control_fixtures import commit

def fault(point):
    """Exit without cleanup at the selected real persistence boundary."""
    if point == sys.argv[3]:
        os._exit(73)
module._fault = fault
with RecordStore.open(sys.argv[1]) as store:
    commit(store, c.loads_request(Path(sys.argv[2]).read_bytes()))
'''
        for boundary in ('before_metadata', 'after_first_revision', 'after_commit'):
            process = subprocess.run([sys.executable, '-B', '-c', program, str(self.root), str(saved), boundary],
                cwd=self.parent, env=child_environment(), capture_output=True, text=True, timeout=60)
            self.assertEqual(process.returncode, 73, process.stderr)
            with RecordStore.open(self.root) as reopened:
                original = reopened.get_run_control_operation('prepare', limits=f.LIMITS)
                self.assertEqual(original is not None, boundary == 'after_commit')

        class CheckedClose:
            """Lose acknowledgment only after actually closing the SQLite handle."""

            def __init__(self, connection):
                """Retain the real connection for one close."""
                self.connection = connection

            def close(self):
                """Close first; report loss without claiming rollback."""
                self.connection.close()
                raise OSError('synthetic close acknowledgment loss')

        handle = RecordStore.open(self.root)
        self.assertEqual(f.commit(handle, self.request, policy=None, evaluated_at=None), original)
        handle._connection = CheckedClose(handle._connection)
        with self.assertRaises(OSError):
            handle.close()
        handle._connection = None
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.get_run_control_operation('prepare', limits=f.LIMITS), original)

    def test_healthy_backup_exact_restore_preserves_pending(self):
        """Healthy exact restore retains original results and all obligations, without readiness claims."""
        original = f.commit(self.store, self.request)
        cancelled = f.commit(self.store, f.successor(self.request, original, 'cancel'))
        before = self.store.inspect_run_control('run', limits=f.LIMITS)
        backup = self.parent / 'backup'
        create_backup(self.store, backup)
        with restore_backup(backup, self.parent / 'restored') as restored:
            self.assertEqual(restored.inspect_run_control('run', limits=f.LIMITS), before)
            self.assertEqual(restored.get_run_control_operation('prepare', limits=f.LIMITS), original)
            self.assertEqual(restored.get_run_control_operation('cancel', limits=f.LIMITS), cancelled)
            self.assertEqual(f.commit(restored, self.request, policy=None, evaluated_at=None), original)
            self.assertFalse(before.to_dict()['ordinary_work_allowed'])
        for path in backup.rglob('*'):
            if path.is_file():
                self.assertNotIn(f.authority.KEY, path.read_bytes())
