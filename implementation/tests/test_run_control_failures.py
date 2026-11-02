"""Real storage damage, transaction acknowledgment failures and historical guard regressions."""

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import sqlite3
import traceback
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c, run_control_store as module, operating_authority as a
from research_pipeline.store import RecordStore, StoreDatabaseError, StoreClosedError, SubmissionConflictError
from tests import run_control_fixtures as f, report_fixtures
from tests.test_store import record, request as submission


class TransactionConnection:
    """Delegate real SQLite work while failing a selected COMMIT or rollback boundary."""

    def __init__(self, connection, mode):
        """Retain the real handle and the explicit acknowledgment fault mode."""
        self.connection, self.mode = connection, mode

    def __getattr__(self, name):
        """Expose real transaction state and cursors without changing SQLite behavior."""
        return getattr(self.connection, name)

    def execute(self, sql, *args):
        """Fail before COMMIT, after a real COMMIT, or during rollback as requested."""
        if sql == 'COMMIT':
            if self.mode == 'committed':
                self.connection.execute(sql, *args)
            raise sqlite3.OperationalError('synthetic commit acknowledgment error')
        if sql == 'ROLLBACK' and self.mode == 'rollback_failed':
            raise sqlite3.OperationalError('synthetic rollback failure')
        return self.connection.execute(sql, *args)


class ControlFailureTests(unittest.TestCase):
    """Corrupt disposable metadata only, and prove public recovery never adopts damaged facts."""

    def setUp(self):
        """Allocate a parent for independent real-store scenarios."""
        temporary = TemporaryDirectory(prefix='control-failures-')
        self.addCleanup(temporary.cleanup)
        self.parent, self.serial = Path(temporary.name), 0

    def populated(self):
        """Create independent signed setup inputs for one failure scenario."""
        self.serial += 1
        store = RecordStore.create(self.parent / str(self.serial), schema_version=3)
        self.addCleanup(store.close)
        return store, f.populate(store)

    def historical_insert(self, store, submitted):
        """Seed a valid pre-guard historical batch using existing atomic private insertion helpers."""
        canonical = c.canonical({'fingerprint_version': 1, 'submission': submitted.to_dict()})
        with store._transaction(write=True) as connection:
            store._check_batch(connection, submitted)
            return store._insert_submission(connection, submitted, canonical, hashlib.sha256(canonical.encode('ascii')).hexdigest())

    def test_actual_commit_rollback_and_lost_sqlite_acknowledgment(self):
        """Reopening distinguishes zero members from a real two-member COMMIT whose acknowledgment failed."""
        for mode in ('denied', 'rollback_failed', 'committed'):
            with self.subTest(mode=mode):
                store, request = self.populated()
                root = self.parent / str(self.serial)
                store._connection = TransactionConnection(store._connection, mode)
                with self.assertRaisesRegex(StoreDatabaseError, 'original operation_id prepare'):
                    f.commit(store, request)
                if mode == 'rollback_failed':
                    self.assertIsNone(store._connection)
                    with self.assertRaises(StoreClosedError):
                        store.head('run')
                store.close()
                with RecordStore.open(root) as reopened:
                    count = reopened._connection.execute("SELECT count(*) FROM revisions WHERE submission_id='prepare'").fetchone()[0]
                    self.assertEqual(count, 2 if mode == 'committed' else 0)
                    original = reopened.get_run_control_operation('prepare', limits=f.LIMITS)
                    if mode == 'committed':
                        self.assertEqual(f.commit(reopened, request, policy=None, evaluated_at=None), original)
                    else:
                        self.assertIsNone(original)
                        self.assertEqual(len(f.commit(reopened, request).to_dict()['receipt']['revisions']), 2)

    def test_postcommit_diagnostic_identifies_original_operation(self):
        """Control-owned acknowledgment diagnostics identify recovery without exposing policy or request."""
        store, request = self.populated()

        def fault(point):
            """Lose acknowledgment after actual transaction exit."""
            if point == 'after_commit':
                raise RuntimeError('synthetic acknowledgment loss')

        with patch.object(module, '_fault', fault), self.assertRaises(RuntimeError) as raised:
            f.commit(store, request)
        diagnostic = ''.join(traceback.format_exception(raised.exception))
        self.assertIn('original operation_id prepare', diagnostic)
        self.assertNotIn(f.authority.KEY.decode(), diagnostic)
        self.assertIsNotNone(store.get_run_control_operation('prepare', limits=f.LIMITS))

    def test_stored_types_json_fingerprint_membership_and_provenance(self):
        """Actual SQL type, canonicality, audit, membership and paired-provenance damage fail closed."""
        scenarios = (
            ('content_blob', 'UPDATE revisions SET content_json=? WHERE record_id=?', (sqlite3.Binary(b'{}'), c.obligation_id('prepare'))),
            ('duplicate', 'UPDATE revisions SET content_json=? WHERE record_id=?', ('{"x":1,"x":2}', c.obligation_id('prepare'))),
            ('noncanonical', 'UPDATE revisions SET content_json=? WHERE record_id=?', ('{ "x": 1 }', c.obligation_id('prepare'))),
            ('fingerprint', "UPDATE submissions SET fingerprint=? WHERE submission_id='prepare'", ('a' * 64,)),
            ('member', 'DELETE FROM revisions WHERE record_id=?', (c.obligation_id('prepare'),)),
            ('audit_actor', "UPDATE audit_events SET provenance_json=? WHERE submission_id='prepare'",
                (c.canonical({'actor': 'different', 'created_at': f.authority.TIME, 'details': {}}),)),
            ('audit_type', "UPDATE audit_events SET committed_at=? WHERE submission_id='prepare'", (sqlite3.Binary(b'bad'),)),
            ('link_kind', 'UPDATE record_links SET target_kind=? WHERE record_id=? AND ordinal=0', ('project', c.obligation_id('prepare'))),
        )
        for name, sql, arguments in scenarios:
            with self.subTest(damage=name):
                store, request = self.populated()
                f.commit(store, request)
                store._connection.execute('PRAGMA foreign_keys=OFF')
                store._connection.execute(sql, arguments)
                with self.assertRaises(c.RunControlIntegrityError):
                    store.get_run_control_operation('prepare', limits=f.LIMITS)
                with self.assertRaises(c.RunControlIntegrityError):
                    store.inspect_run_control('run', limits=f.LIMITS)
        store, request = self.populated()
        f.commit(store, request)
        # Make the saved batch and actual obligation agree on the wrong actor;
        # only cross-record provenance, rather than an incidental fingerprint,
        # can certify that the actor belongs to the originating transition.
        raw = store._connection.execute("SELECT request_json FROM submissions WHERE submission_id='prepare'").fetchone()[0]
        saved = c.strict_json(raw, c.SUBMISSION_BYTES)
        obligation = saved['submission']['records'][1]
        obligation['provenance']['actor'] = 'different'
        raw = c.canonical(saved)
        store._connection.execute("UPDATE submissions SET request_json=?,fingerprint=? WHERE submission_id='prepare'",
            (raw, hashlib.sha256(raw.encode()).hexdigest()))
        store._connection.execute('UPDATE revisions SET provenance_json=? WHERE record_id=?',
            (c.canonical(obligation['provenance']), obligation['record_id']))
        with self.assertRaises(c.RunControlIntegrityError):
            store.get_run_control_operation('prepare', limits=f.LIMITS)

    def test_historical_generic_typed_and_authority_reconciliation_before_guards(self):
        """Exact historical requests recover even when their operation namespace is now reserved."""
        store, _ = self.populated()
        reserved = c.report_operation_id('historical')
        generic = submission(reserved, [record('historic', kind='event')])
        original = self.historical_insert(store, generic)
        self.assertEqual(store.submit(generic), original)
        prior = store.get_revision(a.stream_id('synthetic', 'project'), 1)
        binding = a.OperatingBinding(prior.content['decision']['binding'])
        signed = f.authority.sign(f.authority.decision(binding, f.authority.scope(), revision=2, previous=prior,
            operation=c.report_operation_id('historical-authority')))
        submitted = a.submission(signed)
        receipt = self.historical_insert(store, submitted)
        self.assertEqual(store.submit_typed(submitted), receipt)
        result = store.commit_operating_decision(signed, policy=None, evaluated_at=None, limits=f.authority.LIMITS)
        self.assertEqual(result.to_dict()['receipt'], receipt.to_dict())
        with self.assertRaises(SubmissionConflictError):
            store._check_prepared_typed(submitted)

    def test_legacy_retry_precedes_later_managed_identity_collision(self):
        """Uncontrolled legacy reporting works and exact original recovery precedes later ownership guards."""
        store, request = self.populated()
        legacy = report_fixtures.report_request()
        result = store.commit_report(legacy)
        with self.assertRaisesRegex(c.RunControlStateError, 'legacy report stream'):
            f.commit(store, request)
        self.historical_insert(store, submission('historical-marker', [record(c.control_id('run'), kind='event')]))
        with patch('research_pipeline.report_capture._fault', side_effect=AssertionError('no recapture')):
            self.assertEqual(store.commit_report(legacy), result)
        with self.assertRaises(c.RunControlStateError):
            store.commit_report(report_fixtures.report_request('fresh-legacy', revision=2))
