"""Real-store lifecycle admission, exact recovery, report ownership and bounded metadata failures."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c, operating_authority as a
from research_pipeline import run_control_store as controls
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore, RevisionConflictError, SubmissionConflictError
from tests import run_control_fixtures as f, resource_fixtures as ledger, report_fixtures
from tests.test_store import record, request as submission


class ControlStoreTests(unittest.TestCase):
    """Validate actual SQLite effects and explicit denial without any acknowledgment bypass."""

    def setUp(self):
        """Create one disposable schema-3 store and an authenticated setup request."""
        temporary = TemporaryDirectory(prefix='control-store-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'runtime'
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        self.request = f.populate(self.store)

    def test_lifecycle_order_preemption_and_exact_recovery(self):
        """Later cancellation retains all pending reports and original retries precede current trust/time."""
        first = result = f.commit(self.store, self.request)
        for action in ('checkpoint', 'milestone', 'pause', 'stop', 'cancel', 'checkpoint', 'milestone'):
            proposed = f.successor(self.request, result, action, operation=action + str(result.to_dict()['transition']['revision']))
            result = f.commit(self.store, proposed, policy={'malformed': True}, evaluated_at=None)
        inspection = self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()
        self.assertEqual(inspection['disposition'], 'cancelled')
        self.assertEqual([item['content']['report_revision'] for item in inspection['pending_obligations']], list(range(1, 9)))
        self.assertFalse(inspection['ordinary_work_allowed'])
        self.assertTrue(inspection['recheck_required'])
        for entry in inspection['transitions']:
            self.assertEqual(len(entry['receipt']['revisions']), 2)
            self.assertEqual(entry['receipt']['revisions'][0][1], entry['envelope']['revision'])
            self.assertEqual(entry['receipt']['revisions'][1][1], 1)
        self.assertEqual(f.commit(self.store, self.request, policy=object(), evaluated_at=object()), first)
        changed = c.RunControlRequest({**self.request.to_dict(), 'actor': 'other'})
        with self.assertRaises(SubmissionConflictError):
            f.commit(self.store, changed, policy=None, evaluated_at=None)
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.get_run_control_operation('prepare', limits=f.LIMITS), first)
            self.assertEqual(reopened.inspect_run_control('run', limits=f.LIMITS).to_dict(), inspection)

    def test_selected_run_revision_and_predecessor_conflicts(self):
        """Generic run and control revisions differ and only explicit run advancement is retained."""
        self.store.submit(submission('advance-run', [record('run', 2, 'run', record_references=[RecordReference('project', 1, 'project', 'project')])], {'run': 1}))
        with self.assertRaises(c.RunControlStateError):
            f.commit(self.store, self.request)
        request = c.RunControlRequest({**self.request.to_dict(), 'run_revision': 2})
        result = f.commit(self.store, request)
        self.assertEqual(result.to_dict()['transition']['revision'], 1)
        checkpoint = f.successor(request, result, 'checkpoint', run_revision=2)
        bad = checkpoint.to_dict()
        bad['predecessor']['envelope_digest'] = '0' * 64
        with self.assertRaises(RevisionConflictError):
            f.commit(self.store, c.RunControlRequest(bad))
        advanced = f.commit(self.store, checkpoint)
        with self.assertRaises(RevisionConflictError):
            f.commit(self.store, f.successor(request, result, 'pause'))
        with self.assertRaises(c.RunControlStateError):
            f.commit(self.store, f.successor(request, advanced, 'pause', run_revision=1))

    def test_permission_failures_and_policy_snapshot(self):
        """Current trust withdrawal, wrong key, denied capabilities and invalid times fail closed."""
        for policy, timestamp in ((None, f.authority.TIME), (a.OperatorPolicy('synthetic', []), f.authority.TIME),
                (f.authority.policy(key=b'x' * 32), f.authority.TIME),
                (f.authority.policy(capabilities=[]), f.authority.TIME),
                (f.authority.policy(), f.authority.END), (f.authority.policy(), None),
                ({'invalid': True}, f.authority.TIME)):
            with self.subTest(policy=type(policy).__name__, time=timestamp), self.assertRaises(c.RunControlPermissionError):
                f.commit(self.store, self.request, policy=policy, evaluated_at=timestamp)
            self.assertIsNone(self.store.head(c.control_id('run')))
        seen = []
        original = controls.operating._evaluate_eligibility

        def evaluate(reader, *args, **kwargs):
            """Observe the actual caller-owned write connection and detached policy snapshot."""
            seen.append(reader.connection)
            self.assertTrue(reader.connection.in_transaction)
            return original(reader, *args, **kwargs)

        with patch('research_pipeline.operating_authority_store._evaluate_eligibility', evaluate):
            result = f.commit(self.store, self.request)
        self.assertEqual(seen, [self.store._connection])
        self.assertFalse(result.to_dict()['ordinary_work_allowed'])

    def test_continue_checks_authority_before_pending_gate(self):
        """Continuation checks current credentials first and never succeeds while obligations remain pending."""
        prepared = f.commit(self.store, self.request)
        paused = f.commit(self.store, f.successor(self.request, prepared, 'pause'))
        continuation = f.successor(self.request, paused, 'continue')
        with self.assertRaises(c.RunControlPermissionError):
            f.commit(self.store, continuation, policy=a.OperatorPolicy('synthetic', []))
        with self.assertRaisesRegex(c.RunControlStateError, 'pending'):
            f.commit(self.store, continuation)
        self.assertEqual(self.store.head(c.control_id('run')), 2)
        self.assertEqual(len(self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()['pending_obligations']), 2)

    def test_reductions_never_evaluate_current_authority(self):
        """Expiry, credential withdrawal and unusable time do not prevent metadata-only reductions."""
        result = f.commit(self.store, self.request)
        with patch('research_pipeline.operating_authority_store._evaluate_eligibility', side_effect=AssertionError('no authority evaluation')):
            for action in ('pause', 'stop', 'abandon', 'checkpoint'):
                result = f.commit(self.store, f.successor(self.request, result, action), policy=None, evaluated_at=f.authority.END)
        self.assertEqual(result.to_dict()['disposition'], 'abandoned')
        with self.assertRaises(c.RunControlStateError):
            f.commit(self.store, f.successor(self.request, result, 'continue'))

    def test_generic_typed_import_report_and_authority_reservations(self):
        """All supported fresh write boundaries reject reserved facts while original recovery survives."""
        result = f.commit(self.store, self.request)
        transition, _ = self.store.get_typed_revision(c.control_id('run'), 1)
        identities = [c.control_id('other'), c.obligation_id('other'),
            report_fixtures.report_request().to_dict()['run']['record_id']]
        identities[-1] = controls.reports.manifest_id('run')
        obligation = self.store.get_revision(c.obligation_id('prepare'), 1).content
        identities.append(obligation['report_source_id'])
        for identity in identities:
            with self.subTest(identity=identity), self.assertRaises(c.RunControlStateError):
                self.store.submit(submission('steal-' + identity[:25], [record(identity, kind='event')]))
        for method in (self.store.submit, self.store.submit_typed, self.store._check_prepared_typed):
            with self.assertRaises(c.RunControlStateError):
                method(submission('inject-control', [transition]))
        marker = record('marker', kind='event', content={'format': c.FORMATS[1]})
        with self.assertRaises(c.RunControlStateError):
            self.store.submit(submission('marker', [marker]))
        with patch('research_pipeline.report_capture._fault', side_effect=AssertionError('must reject before capture')):
            with self.assertRaises(c.RunControlStateError):
                self.store.commit_report(report_fixtures.report_request())
        reserved = c.report_operation_id('other')
        binding = f.authority.prepare(self.store, f.authority.scope())
        prior = self.store.get_revision(a.stream_id('synthetic', 'project'), 1)
        signed = f.authority.sign(f.authority.decision(binding, f.authority.scope(), revision=2, previous=prior, operation=reserved))
        with self.assertRaises(c.RunControlStateError):
            self.store.commit_operating_decision(signed, policy=f.authority.policy(), evaluated_at=f.authority.TIME, limits=f.authority.LIMITS)
        self.assertEqual(self.store.get_run_control_operation('prepare', limits=f.LIMITS), result)

    def test_other_submission_conflict_and_fresh_report_collision(self):
        """Original non-lifecycle IDs conflict and existing future source identities cannot be adopted."""
        self.store.submit(submission('prepare', [record('unrelated', kind='event')]))
        with self.assertRaises(SubmissionConflictError):
            f.commit(self.store, self.request)
        new = c.RunControlRequest({**self.request.to_dict(), 'operation_id': 'fresh'})
        source = controls.reports.source_id(c.report_operation_id('fresh'))
        self.store.submit(submission('source-collision', [record(source, kind='event')]))
        with self.assertRaises(c.RunControlStateError):
            f.commit(self.store, new)

    def test_atomic_rollback_and_post_commit_loss(self):
        """Actual insertion fault seams leave zero or both members and same-ID recovery after commit."""
        for boundary in ('before_metadata', 'after_first_revision'):
            def fail(point):
                """Raise at a real store insertion boundary to force rollback."""
                if point == boundary:
                    raise RuntimeError('synthetic interruption')
            with patch('research_pipeline.store._fault', fail), self.assertRaises(RuntimeError):
                f.commit(self.store, self.request)
            self.assertIsNone(self.store.head(c.control_id('run')))
            self.assertIsNone(self.store.head(c.obligation_id('prepare')))
        def lose_acknowledgment(point):
            """Report failure only after the actual transaction committed."""
            if point == 'after_commit':
                raise RuntimeError('lost acknowledgment')

        with patch('research_pipeline.run_control_store._fault', lose_acknowledgment):
            with self.assertRaises(RuntimeError):
                f.commit(self.store, self.request)
        recovered = self.store.get_run_control_operation('prepare', limits=f.LIMITS)
        self.assertEqual(f.commit(self.store, self.request, policy=None, evaluated_at=None), recovered)
        self.assertEqual(len(recovered.to_dict()['receipt']['revisions']), 2)

    def test_empty_limits_and_preconstruction_failure(self):
        """Empty inspection supports zero history budgets and enforces exact independent result bytes."""
        empty_limits = replace(f.LIMITS, max_transitions=0, max_pending_reports=0)
        result = self.store.inspect_run_control('empty', limits=empty_limits)
        size = len(c.dumps_inspection(result))
        self.assertEqual(self.store.inspect_run_control('empty', limits=replace(empty_limits, max_result_bytes=size)), result)
        with patch('research_pipeline.run_control.RunControlInspection', side_effect=AssertionError('must reserve before construction')):
            with self.assertRaises(c.RunControlLimitError):
                self.store.inspect_run_control('empty', limits=replace(empty_limits, max_result_bytes=size - 1))
        with self.assertRaises(c.RunControlLimitError):
            f.commit(self.store, self.request, limits=empty_limits)
        with patch.object(self.store, '_insert_submission', side_effect=AssertionError('receipt must be reserved first')):
            with self.assertRaises(c.RunControlLimitError):
                f.commit(self.store, self.request, limits=replace(f.LIMITS, max_result_bytes=1))
        forged = object.__new__(c.RunControlLimits)
        for name, value in vars(f.LIMITS).items():
            object.__setattr__(forged, name, value)
        object.__setattr__(forged, 'max_transitions', True)
        with patch.object(self.store, '_transaction', side_effect=AssertionError('validate before database')):
            with self.assertRaises(c.RunControlValidationError):
                self.store.inspect_run_control('run', limits=forged)

    def test_stored_damage_and_actual_size_preflight(self):
        """Actual membership, audit, link and stream damage fail explicitly without successful truncation."""
        f.commit(self.store, self.request)
        connection = self.store._connection
        connection.execute('PRAGMA foreign_keys=OFF')
        mutations = [
            ("UPDATE identities SET head=2 WHERE record_id=?", (c.control_id('run'),)),
            ("UPDATE revisions SET ordinal=8 WHERE record_id=?", (c.obligation_id('prepare'),)),
            ("UPDATE audit_events SET provenance_json='{}' WHERE submission_id='prepare'", ()),
            ("DELETE FROM record_links WHERE record_id=? AND ordinal=0", (c.control_id('run'),)),
            ("UPDATE revisions SET content_json='{}' WHERE record_id=?", (c.obligation_id('prepare'),)),
        ]
        for sql, args in mutations:
            connection.execute('SAVEPOINT damage')
            connection.execute(sql, args)
            # Public methods own transactions, so materialize damage and restore it explicitly.
            connection.execute('RELEASE damage')
            try:
                with self.assertRaises(c.RunControlIntegrityError):
                    self.store.inspect_run_control('run', limits=f.LIMITS)
            finally:
                self.store.close()
                # Each damaged scenario receives a fresh real store rather than repairing immutable rows.
                self.root = self.root.parent / ('runtime-' + str(len(list(self.root.parent.iterdir()))))
                self.store = RecordStore.create(self.root, schema_version=3)
                self.addCleanup(self.store.close)
                self.request = f.populate(self.store)
                f.commit(self.store, self.request)
                connection = self.store._connection
                connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute('UPDATE submissions SET request_json=? WHERE submission_id=?', ('x' * (c.SUBMISSION_BYTES + 1), 'prepare'))
        with patch('research_pipeline.run_control_store._stored', side_effect=AssertionError('must reject before decode')):
            with self.assertRaises(c.RunControlLimitError):
                self.store.get_run_control_operation('prepare', limits=f.LIMITS)

    def test_exact_resource_anchors_preserve_ledger(self):
        """Known record-scoped accounts match declarations without resetting existing resource rows."""
        self.store.create_resource_account(ledger.root_request())
        scope = {'type': 'record', 'kind': 'run', 'reference': c.reference('run', 1, 'resource_scope', 'run')}
        declared = self.request.to_dict()['preparation']['operating_scope']['resources']
        self.store.allocate_resources(ledger.allocation('run', 'run', 'project', scope=scope,
            purpose_limits=declared['purpose_limits'], allocation_id='allocation'))
        wire = self.request.to_dict()
        for name, identity, kind in (('project_account', 'project', 'project'), ('run_account', 'run', 'run')):
            wire['preparation']['allocation'][name] = {'account_id': identity, 'operation_id': 'op_' + identity,
                'anchor': c.reference(identity, 1, 'resource_scope', kind)}
        request = c.RunControlRequest(wire)
        self.store.reserve_resources(ledger.reservation('closing', account='run', purpose='closeout',
            maxima=ledger.vector(local_time=1)))
        self.store.observe_resource_usage(ledger.observation('uncertain-closeout', reservation_id='reservation_closing',
            account_id='run', event='acknowledgment_loss'))
        tables = ('resource_operations', 'resource_accounts', 'resource_allocations', 'resource_record_links', 'resource_reservations')
        before = {table: list(self.store._connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')) for table in tables}
        result = f.commit(self.store, request)
        f.commit(self.store, f.successor(request, result, 'cancel'), policy=None, evaluated_at=None)
        after = {table: list(self.store._connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')) for table in tables}
        self.assertEqual(before, after)
        self.assertEqual(len(self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()['pending_obligations']), 2)

    def test_linked_replacement_uses_exact_old_prefix_and_new_allocation(self):
        """A replacement pins an immutable earlier transition and never adopts its allocation or latest head."""
        original = f.commit(self.store, self.request)
        f.commit(self.store, f.successor(self.request, original, 'cancel'))
        self.store.submit(submission('replacement-run', [record('replacement', kind='run',
            record_references=[RecordReference('project', 1, 'project', 'project')])]))
        wire = self.request.to_dict()
        wire.update(run_id='replacement', operation_id='replacement-prepare')
        wire['preparation']['previous_run'] = {'reference': {**original.to_dict()['transition'], 'relationship': 'previous_run'},
            'envelope_digest': original.to_dict()['transition_digest']}
        with self.assertRaises(c.RunControlStateError):
            f.commit(self.store, c.RunControlRequest(wire))
        wire['preparation']['allocation']['allocation_id'] = 'replacement-allocation'
        result = f.commit(self.store, c.RunControlRequest(wire))
        self.assertEqual(result.to_dict()['disposition'], 'prepared')
        self.assertEqual(self.store.inspect_run_control('run', limits=f.LIMITS).to_dict()['disposition'], 'cancelled')
        self.assertEqual(self.store.inspect_run_control('replacement', limits=f.LIMITS).to_dict()['disposition'], 'prepared')

    def test_original_recovery_does_not_require_later_history(self):
        """Damage in a later transition cannot alter valid original-operation recovery of its immutable prefix."""
        original = f.commit(self.store, self.request)
        f.commit(self.store, f.successor(self.request, original, 'checkpoint'))
        self.store._connection.execute('UPDATE revisions SET content_json=? WHERE record_id=? AND revision=2',
            ('{}', c.control_id('run')))
        self.assertEqual(self.store.get_run_control_operation('prepare', limits=f.LIMITS), original)
        self.assertEqual(f.commit(self.store, self.request, policy=object(), evaluated_at=object()), original)
        with self.assertRaises(c.RunControlIntegrityError):
            self.store.inspect_run_control('run', limits=f.LIMITS)

    def test_actor128_real_commit_and_current_policy_snapshot(self):
        """The longest valid actor reaches provenance, and entry policy survives subsequent caller mutation."""
        request = c.RunControlRequest({**self.request.to_dict(), 'actor': 'A' * 128})
        policy = f.authority.policy()
        original = controls.operating._evaluate_eligibility

        def withdraw_caller_policy(reader, *args, **kwargs):
            """Withdraw the original caller object only after commit has snapshotted external trust."""
            object.__setattr__(policy, 'credentials', ())
            return original(reader, *args, **kwargs)

        with patch('research_pipeline.operating_authority_store._evaluate_eligibility', withdraw_caller_policy):
            result = f.commit(self.store, request, policy=policy)
        self.assertEqual(result.to_dict()['receipt']['provenance']['actor'], 'A' * 128)
        self.assertEqual(self.store.get_revision(c.obligation_id('prepare'), 1).provenance.actor, 'A' * 128)
        paused = f.commit(self.store, f.successor(request, result, 'pause'))
        with self.assertRaises(c.RunControlPermissionError):
            f.commit(self.store, f.successor(request, paused, 'continue'), policy=policy)
