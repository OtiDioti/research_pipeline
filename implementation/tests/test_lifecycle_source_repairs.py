"""Request-derived replay bounds, retained work, and adversarial public source boundaries."""

from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
from itertools import product
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_source as s, lifecycle_source_capture as capture
from research_pipeline import run_control as c, resource_ledger as ledger, resources
from research_pipeline.domain import ArtifactReference
from research_pipeline.store import RecordStore, StoreDatabaseError
from tests import lifecycle_source_fixtures as f, run_control_fixtures as controls
from tests import resource_fixtures as rf
from tests.test_report_resources import funded
from tests.test_store import record, request as submission


def rehash(document):
    """Refresh the outer observation identity after a deliberately inconsistent test mutation."""
    document['snapshot_id'] = s._hash({k: v for k, v in document.items() if k != 'snapshot_id'})
    return document


class GuardedConnection:
    """Delegate real SQLite work while refusing a precisely selected protected payload fetch."""

    def __init__(self, connection, forbidden):
        """Retain the real connection and a SQL/arguments predicate; never intercept scalar preflight."""
        self.connection, self.forbidden = connection, forbidden
        self.reached = False

    def execute(self, sql, parameters=()):
        """Execute permitted SQL unchanged, raising an unswallowed assertion at the protected SELECT."""
        if self.forbidden(' '.join(sql.split()), parameters):
            self.reached = True
            raise AssertionError('protected payload SELECT reached')
        return self.connection.execute(sql, parameters)

    def __getattr__(self, name):
        """Keep transaction and cursor behavior on the underlying real connection."""
        return getattr(self.connection, name)


@contextmanager
def guarded(store, forbidden):
    """Temporarily observe a public operation's actual connection without changing its SQL results."""
    original = store._connection
    wrapper = GuardedConnection(original, forbidden)
    store._connection = wrapper
    try:
        yield wrapper
    finally:
        store._connection = original


class SourceRepairContractsTests(unittest.TestCase):
    """Exercise rehashed and forged detached data through every retained contract entry point."""

    @classmethod
    def setUpClass(cls):
        """Capture real one-byte evidence and delayed control history for exact-type regressions."""
        with TemporaryDirectory() as temporary, RecordStore.create(Path(temporary) / 'store', schema_version=3) as store:
            original, result = f.populate(store)
            funded(store, sibling=True)
            artifact = store.put_artifact(b'x')
            store.submit(submission('evidence', [record('selected', artifact_references=[artifact])]))
            wire = controls.successor(original, result, 'checkpoint').to_dict()
            wire['report']['selection'] = [c.reference('selected', 1, 'report_selection', 'research_context')]
            wire['report']['declarations']['objective']['text']['value'] = '𝒜 α "\\\n\t'
            checkpoint = controls.commit(store, c.RunControlRequest(wire), policy=None, evaluated_at=None)
            f.commit(store, 'checkpoint')
            cls.same = store.inspect_lifecycle_source('checkpoint', limits=f.LIMITS).to_dict(limits=f.LIMITS)
            controls.commit(store, controls.successor(original, checkpoint, 'cancel'), policy=None, evaluated_at=None)
            cls.result = f.commit(store).to_dict(limits=f.LIMITS)
            cls.inspection = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
            cls.doc = store.read_lifecycle_source('checkpoint', limits=f.LIMITS).to_dict(limits=f.LIMITS)

    def consumers(self, cls, suffix, document, *, limits=f.LIMITS, error=s.LifecycleSourceValidationError):
        """Require the same semantic rejection from dictionaries, wire codecs, and forged retained bytes."""
        text = c.canonical(document)
        loads, dumps = getattr(s, 'loads_' + suffix), getattr(s, 'dumps_' + suffix)
        forged = object.__new__(cls)
        object.__setattr__(forged, '_json', text)
        calls = (lambda: cls(document, limits=limits), lambda: cls.from_dict(document, limits=limits),
                 lambda: loads(text, limits=limits), lambda: loads(text.encode('ascii'), limits=limits),
                 lambda: forged.to_dict(limits=limits), lambda: dumps(forged, limits=limits))
        for index, call in enumerate(calls):
            with self.subTest(consumer=index), self.assertRaises(error):
                call()

    def test_supplied_equal_valued_scalars_are_not_integer_contracts(self):
        """Reject boolean/float reference revisions and artifact sizes even when Python equality agrees."""
        for alias in (True, 1.0):
            bad = deepcopy(self.result)
            bad['source_event']['revision'] = alias
            self.consumers(s.LifecycleSourceCommitResult, 'commit_result', bad)
            for field in ('source_bindings', 'verified_artifacts'):
                bad = deepcopy(self.doc)
                if field == 'source_bindings':
                    entry = next(row for row in bad[field] if row['revision'] == 1)
                    entry['revision'] = alias
                else:
                    self.assertEqual(bad[field][0]['size'], 1)
                    bad[field][0]['size'] = alias
                self.consumers(s.LifecycleSourceObservation, 'observation', rehash(bad))
        bad = deepcopy(self.result)
        del bad['source_event']['target_kind']
        self.consumers(s.LifecycleSourceCommitResult, 'commit_result', bad)

    def test_inspection_captured_stream_revision_and_date_cross_links(self):
        """Keep valid same/later captures while refusing unrelated, earlier, or pre-obligation observations."""
        for good in (self.same, self.inspection):
            self.assertEqual(s.LifecycleSourceInspection(good, limits=f.LIMITS).to_dict(limits=f.LIMITS), good)
        for mutation in ('stream', 'revision', 'date'):
            bad = deepcopy(self.same)
            result = bad['result']
            if mutation == 'stream':
                result['captured_control']['reference']['record_id'] = c.control_id('another')
            elif mutation == 'revision':
                result['captured_control']['reference']['revision'] = 1
            else:
                # All local result timestamps remain consistent; only the
                # obligation's required_at establishes the later lower bound.
                date = '2026-01-01T00:00:00.000000Z'
                result['observed_at'] = date
                result['receipt']['provenance']['created_at'] = date
                result['scientific_watermark']['committed_at'] = date
            self.consumers(s.LifecycleSourceInspection, 'inspection', bad)

    def test_fetched_bytes_independent_ceiling_precedes_snapshot_constructor(self):
        """A fresh pair of hashes cannot hide fetched metadata exceeding the caller's record allowance."""
        bad = deepcopy(self.doc)
        scientific = bad['scientific']
        ceiling = max(max(len(c.canonical(row)), row['fetched_bytes']) for row in scientific['records']) + 100
        row = scientific['records'][0]
        scientific['metadata_fetched_bytes'] += ceiling - row['fetched_bytes']
        row['fetched_bytes'] = ceiling
        scientific['snapshot_id'] = s._hash({k: v for k, v in scientific.items() if k != 'snapshot_id'})
        rehash(bad)
        exact = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, max_record_bytes=ceiling))
        self.assertEqual(s.LifecycleSourceObservation(bad, limits=exact).to_dict(limits=exact), bad)
        small = replace(exact, scientific=replace(exact.scientific, max_record_bytes=ceiling-1))
        with patch.object(s.DetachedSnapshot, '__init__', side_effect=AssertionError('protected snapshot constructor')):
            self.consumers(s.LifecycleSourceObservation, 'observation', bad, limits=small, error=s.LifecycleSourceLimitError)
        for scalar in (True, 1.0, 0, 2**63):
            malformed = deepcopy(bad)
            malformed['scientific']['records'][0]['fetched_bytes'] = scalar
            self.consumers(s.LifecycleSourceObservation, 'observation', rehash(malformed))

    def test_request_membership_cannot_be_replaced_by_omitted_projection_rows(self):
        """Derived counts/work reject before accounting, and sufficient budgets still reject missing declarations."""
        bad = deepcopy(self.doc)
        bad['resources']['accounts'] = []
        rehash(bad)
        size = len(c.canonical(bad['resources']))
        old_work = 256*(size+1) + 262144*(len(bad['resources']['operations'])+1)
        for change in ({'max_accounts': 0}, {'max_work_bytes': old_work}):
            limits = replace(f.LIMITS, resources=replace(f.LIMITS.resources, **change))
            with patch.object(ledger, '_admit', side_effect=AssertionError('protected accounting')):
                self.consumers(s.LifecycleSourceObservation, 'observation', bad, limits=limits, error=s.LifecycleSourceLimitError)
        for key, duplicate in product(('accounts', 'allocations', 'reservations', 'reservation_usage', 'balances'),
                                      (False, True)):
            bad = deepcopy(self.doc)
            self.assertTrue(bad['resources'][key])
            if duplicate:
                bad['resources'][key].append(deepcopy(bad['resources'][key][0]))
            else:
                bad['resources'][key].pop()
            with self.subTest(key=key, duplicate=duplicate):
                with patch.object(ledger, '_admit', side_effect=AssertionError('protected accounting')):
                    self.consumers(s.LifecycleSourceObservation, 'observation', rehash(bad))


class SourceRepairStoreTests(unittest.TestCase):
    """Use real corrupt SQL and complete public operations to verify preconstruction ordering."""

    def setUp(self):
        """Create disposable store roots; every corruption case gets an independent open runtime."""
        temporary = TemporaryDirectory(prefix='source-repair-')
        self.addCleanup(temporary.cleanup)
        self.parent, self.serial = Path(temporary.name), 0

    def make_store(self, *, funded_accounts=False):
        """Return a prepared real store and authentic digest obtained before any corruption."""
        self.serial += 1
        store = RecordStore.create(self.parent / str(self.serial), schema_version=3)
        self.addCleanup(store.close)
        f.populate(store)
        if funded_accounts:
            funded(store, sibling=True)
        digest = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']
        return store, digest

    def commit(self, store, digest, limits=f.LIMITS):
        """Call the public commitment directly, without a preliminary inspection hiding the tested failure."""
        return store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=limits)

    def assert_pending(self, store):
        """Verify no source metadata/orphan bytes were produced and the original obligation remains pending."""
        self.assertIsNone(store.get_submission(s._identity('prepare')))
        self.assertEqual({path.name for path in (store._artifacts._root / 'objects').iterdir()},
                         {row[0] for row in store._connection.execute('SELECT digest FROM artifacts')})
        self.assertEqual(store._connection.execute("SELECT count(*) FROM revisions WHERE record_id LIKE 'run-control-obligation-%'").fetchone()[0], 1)

    def test_missing_root_and_repeated_links_fail_before_replay_or_target_fetch(self):
        """Deleted normalized rows cannot suppress account/reference charges or authorize request-driven queries."""
        for corruption in ('account', 'links', 'altered-link'):
            store, digest = self.make_store()
            request = rf.root_request().to_dict()
            ref = c.reference('project', 1, 'resource_evidence', 'project')
            request['evidence_references'] = [ref, ref]
            store.create_resource_account(resources.ResourceRequest.from_dict(request))
            if corruption == 'account':
                store._connection.execute('DELETE FROM resource_accounts')
                reduced = replace(f.LIMITS.resources, max_accounts=0)
            else:
                if corruption == 'links':
                    store._connection.execute('DELETE FROM resource_record_links')
                else:
                    store._connection.execute("UPDATE resource_record_links SET relationship='altered' WHERE ordinal=1")
                reduced = replace(f.LIMITS.resources, max_references=2)
            for limits, error in ((replace(f.LIMITS, resources=reduced), s.LifecycleSourceLimitError),
                                  (f.LIMITS, s.LifecycleSourceIntegrityError)):
                with self.subTest(corruption=corruption, error=error):
                    with guarded(store, lambda sql, args: sql.startswith('SELECT i.kind,e.event_id')) as guard:
                        with patch.object(ledger, 'validate_ledger', side_effect=AssertionError('protected shared replay')):
                            with patch.object(ledger, '_admit', side_effect=AssertionError('protected admission')):
                                with self.assertRaisesRegex(error, 'resource'):
                                    self.commit(store, digest, limits)
                    self.assertFalse(guard.reached)
            self.assert_pending(store)

    def test_historical_links_and_creation_membership_before_original_queries(self):
        """Saved-sequence request membership precedes historical target queries and account-map construction."""
        for table in ('resource_record_links', 'resource_accounts', 'resource_allocations', 'resource_reservations'):
            store, digest = self.make_store(funded_accounts=True)
            saved = self.commit(store, digest)
            store._connection.execute('PRAGMA foreign_keys=OFF')
            store._connection.execute('DELETE FROM ' + table)
            store._connection.execute('PRAGMA foreign_keys=ON')
            with guarded(store, lambda sql, args: sql.startswith('SELECT i.kind,a.event_id FROM revisions r LEFT JOIN identities')) as guard:
                with self.assertRaisesRegex(s.LifecycleSourceIntegrityError, 'resource'):
                    store.read_lifecycle_source('prepare', limits=f.LIMITS)
            self.assertFalse(guard.reached)
            # Metadata reconciliation neither replays resources nor opens objects.
            with patch.object(RecordStore, 'read_artifact', side_effect=AssertionError('metadata opened source')):
                self.assertEqual(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS)._json, saved._json)

    def test_historical_scopes_are_validated_at_public_read_boundary(self):
        """Reject malformed root/child TEXT without leaking content, changing intent, or repairing rows."""
        sentinel = 'PRIVATE-INVALID-SCOPE-F006'
        boolean_reference = rf.scope('project', revision=True)
        cases = (
            ('project', '{}'), ('project', 'null'), ('project', '[]'),
            ('project', c.canonical({'type': 'record', 'kind': 'project'})),
            ('project', c.canonical({'type': 'record', 'kind': 'project', 'reference': None})),
            ('project', c.canonical(boolean_reference)),
            ('project', c.canonical({**rf.scope('project'), sentinel: sentinel})),
            ('run', '{}'),
        )
        for account, malformed in cases:
            with self.subTest(account=account, scope=malformed):
                store, digest = self.make_store(funded_accounts=True)
                committed = self.commit(store, digest)
                original = store.read_lifecycle_source('prepare', limits=f.LIMITS)
                result = committed.to_dict(limits=f.LIMITS)
                artifact = ArtifactReference.from_dict(result['source_artifact'])
                source_bytes = store.read_artifact(artifact)
                before = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
                self.assertTrue(before['pending_obligations'])
                self.assertFalse(before['ordinary_work_allowed'])
                self.assertTrue(before['recheck_required'])
                original_scope = store._connection.execute(
                    'SELECT scope_json FROM resource_accounts WHERE account_id=?', (account,)).fetchone()[0]
                # Corrupt the already-open store in autocommit mode so the public
                # read owns its transaction and open-time validation cannot mask it.
                self.assertFalse(store._connection.in_transaction)
                store._connection.execute('UPDATE resource_accounts SET scope_json=? WHERE account_id=?',
                                          (malformed, account))
                self.assertFalse(store._connection.in_transaction)
                with self.assertRaises(s.LifecycleSourceIntegrityError) as failure:
                    store.read_lifecycle_source('prepare', limits=f.LIMITS)
                self.assertEqual(str(failure.exception), 'inconsistent stored source evidence')
                self.assertNotIn(sentinel, str(failure.exception))
                self.assertEqual(store._connection.execute(
                    'SELECT typeof(scope_json),scope_json FROM resource_accounts WHERE account_id=?',
                    (account,)).fetchone(), ('text', malformed))
                recovered = store.get_lifecycle_source_operation('prepare', limits=f.LIMITS)
                self.assertEqual(recovered._json, committed._json)
                self.assertEqual(store.inspect_run_control('run', limits=controls.LIMITS).to_dict(), before)
                store._connection.execute('UPDATE resource_accounts SET scope_json=? WHERE account_id=?',
                                          (original_scope, account))
                restored = store.read_lifecycle_source('prepare', limits=f.LIMITS)
                self.assertEqual(restored._json, original._json)
                self.assertEqual(restored.to_dict(limits=f.LIMITS)['snapshot_id'], result['snapshot_id'])
                self.assertEqual(store.read_artifact(artifact), source_bytes)
                self.assertEqual(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS).to_dict(
                    limits=f.LIMITS)['receipt'], result['receipt'])

    def test_historical_account_read_preserves_real_storage_error(self):
        """Keep SQLite's error cause and rollback when account payload retrieval fails after preflight."""
        store, digest = self.make_store(funded_accounts=True)
        committed = self.commit(store, digest)
        original = store.read_lifecycle_source('prepare', limits=f.LIMITS)

        class FailingAccountConnection(GuardedConnection):
            """Fail the selected payload read once through SQLite itself, delegating rollback normally."""

            def execute(self, sql, parameters=()):
                """Issue a nonexistent-table query at the account fetch; leave all other SQL unchanged."""
                if not self.reached and self.forbidden(' '.join(sql.split()), parameters):
                    self.reached = True
                    return self.connection.execute('SELECT * FROM missing_f006_account_payload')
                return self.connection.execute(sql, parameters)

        connection = FailingAccountConnection(store._connection, lambda sql, args:
            sql.startswith('SELECT a.account_id,a.parent_account_id,a.scope_json FROM resource_accounts'))
        with patch.object(store, '_connection', connection):
            with self.assertRaises(StoreDatabaseError) as failure:
                store.read_lifecycle_source('prepare', limits=f.LIMITS)
            self.assertTrue(connection.reached)
            self.assertIsInstance(failure.exception.__cause__, sqlite3.OperationalError)
            self.assertEqual(failure.exception.__cause__.sqlite_errorcode, sqlite3.SQLITE_ERROR)
            self.assertFalse(connection.in_transaction)
            self.assertEqual(store.read_lifecycle_source('prepare', limits=f.LIMITS)._json, original._json)
        self.assertEqual(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS)._json, committed._json)

    def test_public_read_retains_cumulative_work_through_last_original_receipt(self):
        """Observe real reservations, prove their documented sum, and reject one unit before the final copy."""
        store, digest = self.make_store(funded_accounts=True)
        result = self.commit(store, digest).to_dict(limits=f.LIMITS)
        charges = []
        original = capture._Workspace.reserve_charge
        def observe(work, charge, stage):
            """Delegate every charge unchanged and record only successful cumulative reservations."""
            original(work, charge, stage)
            charges.append((charge, stage, work.used))
        with patch.object(capture._Workspace, 'reserve_charge', observe):
            saved = store.read_lifecycle_source('prepare', limits=f.LIMITS)
        raw = 1024*1024 + 74*result['source_artifact']['size']
        read_index = next(i for i, item in enumerate(charges) if item[1] == 'source artifact read')
        self.assertEqual(charges[read_index][0], raw)
        self.assertEqual(sum(item[0] for item in charges), charges[-1][2])
        self.assertTrue(all(charge % 64 == 0 for charge, stage, _ in charges if stage != 'source artifact read'))
        total, before_io = charges[-1][2], charges[read_index][2]
        self.assertGreater(total, before_io)
        exact = replace(f.LIMITS, max_work_bytes=total)
        self.assertEqual(store.read_lifecycle_source('prepare', limits=exact)._json, saved._json)
        receipt_calls = sum(stage == 'original receipt' for _, stage, _ in charges)
        receipt = capture.SubmissionReceipt
        calls = 0
        def protected_receipt(*args, **kwargs):
            """Permit earlier real receipts but fail if the last unreserved constructor is reached."""
            nonlocal calls
            calls += 1
            if calls == receipt_calls:
                raise AssertionError('protected final original receipt')
            return receipt(*args, **kwargs)
        with patch.object(capture, 'SubmissionReceipt', protected_receipt):
            with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'original receipt workspace'):
                store.read_lifecycle_source('prepare', limits=replace(exact, max_work_bytes=total-1))
        self.assertEqual(calls, receipt_calls-1)
        old_separate = max(before_io, total-raw)
        self.assertLess(old_separate, total)
        with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'workspace'):
            store.read_lifecycle_source('prepare', limits=replace(exact, max_work_bytes=old_separate))
        with patch.object(RecordStore, 'read_artifact', side_effect=AssertionError('protected artifact I/O')):
            with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'artifact read workspace'):
                store.read_lifecycle_source('prepare', limits=replace(exact, max_work_bytes=before_io-1))

    def test_actual_oversized_source_sql_on_every_metadata_consumer(self):
        """Real oversized source TEXT rejects before payload SELECT on get, inspect, retry, and read."""
        for field in ('request_json', 'content_json', 'provenance_json', 'audit_provenance', 'relationship', 'blob'):
            store, digest = self.make_store()
            result = self.commit(store, digest).to_dict(limits=f.LIMITS)
            sid, eid = result['operation_id'], result['source_event']['record_id']
            size = f.LIMITS.control.metadata.max_record_bytes + 1
            text = 'x' * size
            if field in ('request_json', 'blob'):
                text = sqlite3.Binary(b'{}') if field == 'blob' else text
                sql, args = 'UPDATE submissions SET request_json=? WHERE submission_id=?', (text, sid)
                predicate = lambda query, args: query.startswith('SELECT request_json,fingerprint FROM submissions')
            elif field == 'audit_provenance':
                sql, args = 'UPDATE audit_events SET provenance_json=? WHERE submission_id=?', (text, sid)
                predicate = lambda query, args: query.startswith('SELECT event_id,submission_id,event_type,committed_at,provenance_json')
            elif field == 'relationship':
                sql, args = 'UPDATE record_links SET relationship=? WHERE record_id=? AND ordinal=0', (text, eid)
                predicate = lambda query, args: query.startswith('SELECT target_id,target_revision,relationship,target_kind') and args[0] == eid
            else:
                sql, args = 'UPDATE revisions SET ' + field + '=? WHERE record_id=?', (text, eid)
                predicate = lambda query, args: 'r.content_json,r.provenance_json' in query and 'CASE' not in query and args[0] == eid
            store._connection.execute(sql, args)
            consumers = (lambda: self.commit(store, digest),
                lambda: store.get_lifecycle_source_operation('prepare', limits=f.LIMITS),
                lambda: store.inspect_lifecycle_source('prepare', limits=f.LIMITS),
                lambda: store.read_lifecycle_source('prepare', limits=f.LIMITS))
            for index, consume in enumerate(consumers):
                with self.subTest(field=field, consumer=index), guarded(store, predicate) as guard:
                    with patch.object(RecordStore, 'read_artifact', side_effect=AssertionError('protected artifact read')):
                        error = s.LifecycleSourceIntegrityError if field == 'blob' else s.LifecycleSourceLimitError
                        with self.assertRaises(error):
                            consume()
                self.assertFalse(guard.reached)

    def test_oversized_resource_request_receipt_and_projection_before_fetch(self):
        """SQL scalar preflight refuses actual oversized resource TEXT independently of ledger decoding."""
        for table, column in (('resource_operations', 'request_json'), ('resource_operations', 'result_json'),
                              ('resource_accounts', 'scope_json'), ('resource_record_links', 'relationship')):
            store, digest = self.make_store()
            store.create_resource_account(rf.root_request())
            limits = replace(f.LIMITS, resources=replace(f.LIMITS.resources, max_record_bytes=65536))
            store._connection.execute('UPDATE ' + table + ' SET ' + column + '=?', ('x'*65537,))
            def forbidden(sql, args):
                """Refuse only payload retrieval from the corrupt table, allowing all scalar length plans."""
                return sql.startswith('SELECT ') and ' FROM ' + table in sql and 'CASE' not in sql and 'count(' not in sql
            with self.subTest(table=table, column=column), guarded(store, forbidden) as guard:
                with patch.object(ledger, 'validate_ledger', side_effect=AssertionError('protected replay')):
                    with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'resource'):
                        self.commit(store, digest, limits)
            self.assertFalse(guard.reached)
            self.assert_pending(store)

    def test_oversized_fresh_original_and_unselected_batch_member(self):
        """Fresh capture checks stored requests/audit and every original member, including an unselected sibling."""
        for field, committed in product(('request_json', 'content_json', 'provenance_json',
                                         'audit_provenance', 'relationship', 'blob'), (False, True)):
            store, digest = self.make_store()
            # The scientific root project shares this original batch with many
            # records; a new explicit selected/unselected pair also exercises
            # closure-independent original membership verification.
            store.submit(submission('pair', [record('selected'), record('unselected')]))
            original = store.get_run_control_operation('prepare', limits=controls.LIMITS)
            request = controls.successor(c.RunControlRequest(store.get_revision(c.control_id('run'), 1).content['request']), original, 'checkpoint')
            wire = request.to_dict()
            wire['report']['selection'] = [c.reference('selected', 1, 'report_selection', 'research_context')]
            controls.commit(store, c.RunControlRequest(wire), policy=None, evaluated_at=None)
            digest = store.inspect_lifecycle_source('checkpoint', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']
            if committed:
                store.commit_lifecycle_source('checkpoint', expected_binding_digest=digest, limits=f.LIMITS)
            oversized = 'x'*(f.LIMITS.control.metadata.max_record_bytes+1)
            if field == 'request_json':
                sql, args = 'UPDATE submissions SET request_json=? WHERE submission_id=?', (oversized, 'pair')
                forbidden = lambda query, args: query.startswith('SELECT request_json,fingerprint FROM submissions') and args == ('pair',)
            elif field == 'audit_provenance':
                sql, args = 'UPDATE audit_events SET provenance_json=? WHERE submission_id=?', (oversized, 'pair')
                forbidden = lambda query, args: query.startswith('SELECT event_id,submission_id,event_type,committed_at,provenance_json') and args == ('pair',)
            elif field == 'relationship':
                # Use the existing project link on the captured generic run.
                sql, args = "UPDATE record_links SET relationship=? WHERE record_id='run'", (oversized,)
                forbidden = lambda query, args: query.startswith('SELECT target_id,target_revision,relationship,target_kind') and args[0] == 'run'
            else:
                column = 'content_json' if field == 'blob' else field
                text = sqlite3.Binary(b'{}') if field == 'blob' else oversized
                sql, args = 'UPDATE revisions SET ' + column + '=? WHERE record_id=?', (text, 'unselected')
                forbidden = lambda query, args: 'r.content_json,r.provenance_json' in query and 'CASE' not in query and args[0] == 'unselected'
            store._connection.execute(sql, args)
            error = s.LifecycleSourceIntegrityError if field == 'blob' else s.LifecycleSourceLimitError
            with self.subTest(field=field, committed=committed), guarded(store, forbidden) as guard:
                with self.assertRaises(error):
                    if committed:
                        store.read_lifecycle_source('checkpoint', limits=f.LIMITS)
                    else:
                        store.commit_lifecycle_source('checkpoint', expected_binding_digest=digest, limits=f.LIMITS)
            self.assertFalse(guard.reached)
            if not committed:
                self.assertIsNone(store.get_submission(s._identity('checkpoint')))

    def boundary_store(self):
        """Prepare repeated resource references and escaped scientific evidence under initial duplicated intent."""
        store, digest = self.make_store(funded_accounts=True)
        artifact = store.put_artifact(b'xx')
        store.submit(submission('unicode-evidence', [record('selected', content={'nested': {'text': '𝒜 α "\\\n\t'}},
                                                           artifact_references=[artifact])]))
        request = rf.reservation().to_dict()
        reference = c.reference('selected', 1, 'resource_evidence', 'research_context')
        request['evidence_references'] = [reference, reference]
        store.reserve_resources(resources.ResourceRequest.from_dict(request))
        return store, digest

    def capture_metrics(self, store, digest):
        """Delegate a complete capture while observing actual SQL/wrapper sizes and published work formulas."""
        metrics = {'sql_record': 0, 'wr': 0, 'wrappers': [], 'charges': []}
        scan, length = capture._ResourceBudget.scan, capture._length
        preflight, resource = capture._ResourceBudget.preflight, s._resource_preflight
        work = s._ResourceMembership.work
        reserve, charge = capture._Workspace.reserve, capture._Workspace.reserve_charge
        def measured_length(row):
            """Record the exact resource SQL row contribution returned by production type/length validation."""
            size = length(row)
            metrics['sql_record'] = max(metrics['sql_record'], size)
            return size
        def measured_scan(budget, *args, **kwargs):
            """Observe only resource scalar preflight lengths, preserving every original fetch and charge."""
            with patch.object(capture, '_length', measured_length):
                return scan(budget, *args, **kwargs)
        def measured_preflight(budget, connection):
            """Retain the completed budget object so later wrapper measurements remain visible."""
            preflight(budget, connection)
            metrics['budget'] = budget
        def measured_resource(value, limits, original):
            """Observe the complete detached projection after unchanged production authorization."""
            resource(value, limits, original)
            metrics['projection'] = value
        def measured_work(membership, size):
            """Compute the documented request-derived formula independently and delegate its enforcement."""
            required = 256*(size+1)+262144*(len(membership.declarations['accounts'])+1)*(len(membership.operations)+1)
            metrics['wr'] = max(metrics['wr'], required)
            work(membership, size)
        def measured_reserve(workspace, size, stage, *, maximum=None):
            """Record full wrapper framing before the unchanged 64-times reservation."""
            reserve(workspace, size, stage, maximum=maximum)
            metrics['wrappers'].append((stage, size))
        def measured_charge(workspace, amount, stage):
            """Observe successful cumulative charge without changing reservation lifetime."""
            charge(workspace, amount, stage)
            metrics['charges'].append((stage, amount))
        with patch.object(capture._ResourceBudget, 'scan', measured_scan), \
                patch.object(capture._ResourceBudget, 'preflight', measured_preflight), \
                patch.object(s, '_resource_preflight', measured_resource), \
                patch.object(s._ResourceMembership, 'work', measured_work), \
                patch.object(capture._Workspace, 'reserve', measured_reserve), \
                patch.object(capture._Workspace, 'reserve_charge', measured_charge):
            result = self.commit(store, digest).to_dict(limits=f.LIMITS)
        document = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        budget, projection = metrics['budget'], metrics['projection']
        projection_rows = [row for key in ('operations', 'accounts', 'allocations', 'reservations',
            'reservation_usage', 'breaches', 'balances') for row in projection[key]]
        resource_limits = {'max_accounts': len(projection['accounts']), 'max_operations': len(projection['operations']),
            'max_references': sum(len(ledger.references(item['request'])) for item in projection['operations']),
            'max_rows': max(budget.rows, len(projection_rows)),
            'max_record_bytes': max(metrics['sql_record'], *(len(c.canonical(row)) for row in projection_rows)),
            'max_metadata_bytes': budget.bytes + budget.complete_size + len(c.canonical(projection)),
            'max_result_bytes': max(budget.complete_size, len(c.canonical(projection))), 'max_work_bytes': metrics['wr']}
        scientific = document['scientific']
        envelopes = [capture._strict_json(row['envelope_json'], maximum_depth=65) for row in scientific['records']]
        scientific_limits = {'max_roots': len(scientific['resolutions']), 'max_records': len(envelopes),
            'max_references': sum(len(row['record_references'])+len(row['artifact_references']) for row in envelopes),
            'max_record_bytes': max(max(len(c.canonical(row)), row['fetched_bytes']) for row in scientific['records']),
            'max_metadata_bytes': scientific['metadata_fetched_bytes']+len(c.canonical(scientific)),
            'max_artifacts': len(scientific['artifacts']), 'max_file_bytes': 2, 'max_total_bytes': 2,
            'max_work_bytes': 64*min(f.LIMITS.scientific.max_metadata_bytes, scientific['limits']['max_metadata_bytes'])+4096}
        source_size = result['source_artifact']['size']
        wrappers = metrics['wrappers']
        outer_limits = {'max_input_bytes': source_size, 'max_source_bytes': source_size,
            'max_submission_bytes': max(size for stage, size in wrappers if 'submission' in stage or stage == 'source event'),
            'max_result_bytes': max(source_size, *(size for stage, size in wrappers if 'receipt' in stage or stage == 'source result')),
            'max_work_bytes': sum(amount for _, amount in metrics['charges']),
            'max_artifacts': 2, 'max_artifact_bytes': source_size, 'max_artifact_total_bytes': source_size+2}
        self.assertEqual(outer_limits['max_work_bytes'], 1024*1024+64*sum(size for _, size in wrappers))
        return resource_limits, scientific_limits, outer_limits

    def test_complete_capture_resource_equalities_and_one_unit_deficits(self):
        """Every resource allowance covers full request-derived replay, repeated SQL, and complete projection framing."""
        baseline, digest = self.boundary_store()
        thresholds, _, _ = self.capture_metrics(baseline, digest)
        for field, threshold in thresholds.items():
            with self.subTest(field=field):
                store, digest = self.boundary_store()
                exact = replace(f.LIMITS, resources=replace(f.LIMITS.resources, **{field: threshold}))
                small = replace(exact, resources=replace(exact.resources, **{field: threshold-1}))
                target = ('research_pipeline.reports._validate_resources' if field in
                          ('max_record_bytes', 'max_metadata_bytes', 'max_result_bytes') else
                          'research_pipeline.resource_ledger.validate_ledger')
                with patch(target, side_effect=AssertionError('protected resource reconstruction')):
                    with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'resource'):
                        self.commit(store, digest, small)
                self.assert_pending(store)
                result = self.commit(store, digest, exact)
                self.assertEqual(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS)._json, result._json)
                self.assertFalse(result.to_dict(limits=f.LIMITS)['ordinary_work_allowed'])

    def test_complete_capture_scientific_equalities_and_one_unit_deficits(self):
        """Independent scientific closure and artifact bounds succeed through actual source insertion at equality."""
        baseline, digest = self.boundary_store()
        _, thresholds, _ = self.capture_metrics(baseline, digest)
        for field, threshold in thresholds.items():
            with self.subTest(field=field):
                store, digest = self.boundary_store()
                exact = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, **{field: threshold}))
                small = replace(exact, scientific=replace(exact.scientific, **{field: threshold-1}))
                with patch.object(s.DetachedSnapshot, '__init__', side_effect=AssertionError('protected snapshot reconstruction')):
                    with self.assertRaises(s.LifecycleSourceLimitError):
                        self.commit(store, digest, small)
                self.assert_pending(store)
                result = self.commit(store, digest, exact).to_dict(limits=f.LIMITS)
                saved = store.read_lifecycle_source('prepare', limits=f.LIMITS)
                self.assertEqual(saved.to_dict(limits=f.LIMITS)['snapshot_id'], result['snapshot_id'])

    def test_complete_capture_outer_equalities_and_one_unit_deficits(self):
        """Complete escaped source, submissions, result, inventory and cumulative capture work respect equality."""
        baseline, digest = self.boundary_store()
        _, _, thresholds = self.capture_metrics(baseline, digest)
        for field, threshold in thresholds.items():
            with self.subTest(field=field):
                store, digest = self.boundary_store()
                before = list(store._connection.execute('SELECT * FROM revisions ORDER BY record_id,revision'))
                exact = replace(f.LIMITS, **{field: threshold})
                with ExitStack() as guards:
                    guards.enter_context(patch.object(RecordStore, '_insert_submission',
                        side_effect=AssertionError('protected source insertion')))
                    if field in ('max_source_bytes', 'max_result_bytes'):
                        guards.enter_context(patch.object(s.LifecycleSourceObservation, '__init__',
                            side_effect=AssertionError('protected observation constructor')))
                    elif field in ('max_artifact_bytes', 'max_artifact_total_bytes'):
                        guards.enter_context(patch.object(capture, '_event',
                            side_effect=AssertionError('protected source event construction')))
                    elif field == 'max_artifacts':
                        guards.enter_context(patch.object(store._artifacts, 'verify',
                            side_effect=AssertionError('protected evidence artifact read')))
                    elif field == 'max_input_bytes':
                        decoder = capture.binding.json.loads
                        def protected_decode(text, *args, **kwargs):
                            """Permit earlier bounded fragments but refuse the complete unreserved source decode."""
                            if len(text) >= threshold:
                                raise AssertionError('protected source JSON decoder')
                            return decoder(text, *args, **kwargs)
                        guards.enter_context(patch.object(capture.binding.json, 'loads', protected_decode))
                    elif field == 'max_submission_bytes':
                        stored = capture._stored
                        constructor = capture.Submission.__init__
                        def protected_stored(text, *args, **kwargs):
                            """Refuse the maximum original batch's decode while allowing smaller original batches."""
                            if len(text) >= threshold:
                                raise AssertionError('protected original submission decode')
                            return stored(text, *args, **kwargs)
                        def protected_submission(value, submission_id, *args, **kwargs):
                            """Permit original batches but refuse an unreserved new source submission constructor."""
                            if submission_id == s._identity('prepare'):
                                raise AssertionError('protected source submission constructor')
                            constructor(value, submission_id, *args, **kwargs)
                        guards.enter_context(patch.object(capture, '_stored', protected_stored))
                        guards.enter_context(patch.object(capture.Submission, '__init__', protected_submission))
                    else:
                        seam = capture._fault
                        def protected_placement(boundary):
                            """Refuse entry to source placement after all cumulative wrapper reservations."""
                            if boundary == 'before_artifacts':
                                raise AssertionError('protected artifact placement')
                            seam(boundary)
                        guards.enter_context(patch.object(capture, '_fault', protected_placement))
                    with self.assertRaises(s.LifecycleSourceLimitError):
                        self.commit(store, digest, replace(exact, **{field: threshold-1}))
                self.assert_pending(store)
                result = self.commit(store, digest, exact).to_dict(limits=f.LIMITS)
                self.assertEqual(store.read_artifact(ArtifactReference(**result['source_artifact'])),
                                 store.read_lifecycle_source('prepare', limits=f.LIMITS)._json.encode('ascii'))
                after = list(store._connection.execute('SELECT * FROM revisions WHERE submission_id<>? ORDER BY record_id,revision',
                                                       (result['operation_id'],)))
                self.assertEqual(after, before)
                self.assertEqual(len(result['receipt']['revisions']), 1)
                self.assertEqual(len(store.inspect_run_control('run', limits=controls.LIMITS).to_dict()['pending_obligations']), 1)

    def test_public_metadata_result_and_inspection_framing(self):
        """Recovery uses actual receipt framing; complete result/inspection equality never opens artifacts."""
        store, digest = self.boundary_store()
        self.commit(store, digest)
        for method, cls in ((store.get_lifecycle_source_operation, s.LifecycleSourceCommitResult),
                            (store.inspect_lifecycle_source, s.LifecycleSourceInspection)):
            saved = method('prepare', limits=f.LIMITS)
            exact = replace(f.LIMITS, max_result_bytes=len(saved._json))
            with patch.object(RecordStore, 'read_artifact', side_effect=AssertionError('metadata artifact read')):
                self.assertEqual(method('prepare', limits=exact)._json, saved._json)
                with patch.object(cls, '__init__', side_effect=AssertionError('protected final metadata constructor')):
                    with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'framing'):
                        method('prepare', limits=replace(exact, max_result_bytes=len(saved._json)-1))

    def test_empty_schema_three_public_capture_zero_counts_and_fixed_work(self):
        """A complete empty replay permits zero count allowances while charging its actual fixed overhead."""
        store, digest = self.make_store()
        observed = []
        preflight = capture._ResourceBudget.preflight
        def observe(budget, connection):
            """Delegate real empty replay preflight and retain its raw-byte/row plan."""
            preflight(budget, connection)
            observed.append((budget.bytes, budget.rows))
        with patch.object(capture._ResourceBudget, 'preflight', observe):
            self.commit(store, digest)
        raw, rows = observed[0]
        # Detached empty framing has its own fixed term, so include both stages.
        doc = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        required = 256*(max(raw, len(c.canonical(doc['resources'])))+1)+262144
        exact = replace(f.LIMITS, resources=replace(f.LIMITS.resources,
            max_accounts=0, max_operations=0, max_references=0, max_rows=rows, max_work_bytes=required))
        other, digest = self.make_store()
        with patch.object(ledger, 'validate_ledger', side_effect=AssertionError('protected empty replay')):
            with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'resource replay workspace'):
                self.commit(other, digest, replace(exact, resources=replace(exact.resources, max_work_bytes=required-1)))
        self.assert_pending(other)
        self.commit(other, digest, exact)

    def test_scientific_sql_content_and_provenance_before_payload_fetch(self):
        """The scientific caller ceiling rejects oversized selected TEXT before snapshot payload decoding."""
        for column in ('content_json', 'provenance_json'):
            store, digest = self.make_store()
            store.submit(submission('selected', [record('selected')]))
            original = c.RunControlRequest(store.get_revision(c.control_id('run'), 1).content['request'])
            previous = store.get_run_control_operation('prepare', limits=controls.LIMITS)
            wire = controls.successor(original, previous, 'checkpoint').to_dict()
            wire['report']['selection'] = [c.reference('selected', 1, 'report_selection', 'research_context')]
            controls.commit(store, c.RunControlRequest(wire), policy=None, evaluated_at=None)
            digest = store.inspect_lifecycle_source('checkpoint', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']
            limits = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, max_record_bytes=65536))
            store._connection.execute('UPDATE revisions SET ' + column + '=? WHERE record_id=?', ('x'*65537, 'selected'))
            def forbidden(sql, args):
                """Refuse selected scientific payload retrieval while allowing SQL type/length measurement."""
                return 'content_json' in sql and 'CASE' not in sql and 'length(' not in sql and args == ('selected', 1)
            with self.subTest(column=column), guarded(store, forbidden) as guard:
                with patch.object(s.DetachedSnapshot, '__init__', side_effect=AssertionError('protected scientific result')):
                    with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'scientific SQL record'):
                        store.commit_lifecycle_source('checkpoint', expected_binding_digest=digest, limits=limits)
            self.assertFalse(guard.reached)
            self.assertIsNone(store.get_submission(s._identity('checkpoint')))

    def test_resource_metadata_corruption_on_historical_read_and_fresh_declarations(self):
        """Bound historical requests/receipts and reject fresh missing allocation/reservation owners before admission."""
        for table in ('resource_allocations', 'resource_reservations'):
            store, digest = self.make_store(funded_accounts=True)
            store._connection.execute('PRAGMA foreign_keys=OFF')
            store._connection.execute('DELETE FROM ' + table)
            store._connection.execute('PRAGMA foreign_keys=ON')
            with patch.object(ledger, '_admit', side_effect=AssertionError('protected admission')):
                with self.assertRaisesRegex(s.LifecycleSourceIntegrityError, 'resource declaration membership'):
                    self.commit(store, digest)
            self.assert_pending(store)
        for column, blob in product(('request_json', 'result_json'), (False, True)):
            store, digest = self.make_store(funded_accounts=True)
            saved = self.commit(store, digest)
            value = sqlite3.Binary(b'{}') if blob else 'x'*65537
            store._connection.execute('UPDATE resource_operations SET ' + column + '=? WHERE sequence=1', (value,))
            def forbidden(sql, args):
                """Refuse historical original payload retrieval but execute scalar preflight on real SQL."""
                return (' FROM resource_operations' in sql and 'CASE' not in sql and 'count(' not in sql)
            error = s.LifecycleSourceIntegrityError if blob else s.LifecycleSourceLimitError
            with self.subTest(column=column, blob=blob), guarded(store, forbidden) as guard:
                with self.assertRaisesRegex(error, 'resource|storage type'):
                    store.read_lifecycle_source('prepare', limits=f.LIMITS)
            self.assertFalse(guard.reached)
            with patch.object(ledger, 'validate_ledger', side_effect=AssertionError('metadata replay')):
                with patch.object(RecordStore, 'read_artifact', side_effect=AssertionError('metadata artifact read')):
                    self.assertEqual(self.commit(store, digest)._json, saved._json)
                    self.assertEqual(store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['state'],
                                     'committed_source')
