"""Current policy, explicit generic revisions and immutable resource-anchor regression cases."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research_pipeline import run_control as c, operating_authority as a
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore
from tests import run_control_fixtures as f, resource_fixtures as ledger
from tests.test_store import record, request as submission


class ControlPolicyResourceTests(unittest.TestCase):
    """Use real signed decisions and ledger operations; control never repairs or rewrites them."""

    def setUp(self):
        """Create an isolated parent for independent schema and resource scenarios."""
        temporary = TemporaryDirectory(prefix='control-policy-resource-')
        self.addCleanup(temporary.cleanup)
        self.parent, self.serial = Path(temporary.name), 0

    def populated(self, *, schema=3, main=False):
        """Return real synthetic setup or main-research inputs in the requested supported schema."""
        self.serial += 1
        store = RecordStore.create(self.parent / str(self.serial), schema_version=schema)
        self.addCleanup(store.close)
        return store, f.populate(store, main=main)

    def approve(self, store, request, *, scope=None, **updates):
        """Append a real replacement approval and return the request with its exact expected pin."""
        previous = store.get_revision(a.stream_id('synthetic', 'project'), store.head(a.stream_id('synthetic', 'project')))
        binding = a.OperatingBinding(previous.content['decision']['binding'])
        scope = scope or a.OperatingScope(previous.content['decision']['scope'])
        signed = f.authority.sign(f.authority.decision(binding, scope, revision=previous.revision + 1,
            previous=previous, operation='approval-' + str(previous.revision + 1), **updates))
        result = store.commit_operating_decision(signed, policy=f.authority.policy(),
            evaluated_at=updates.get('valid_from', f.authority.TIME), limits=f.authority.LIMITS).to_dict()
        value = request.to_dict()
        value['expected_authority'] = {'reference': result['decision'], 'envelope_digest': result['envelope_digest']}
        value['preparation']['operating_scope'] = scope.to_dict()
        return c.RunControlRequest(value)

    def anchored(self, store, request, *, scope=None, allocation='allocation'):
        """Create exact original resource accounts and attach their immutable declaration anchors."""
        store.create_resource_account(ledger.root_request())
        value = request.to_dict()
        resources = value['preparation']['operating_scope']['resources']
        store.allocate_resources(ledger.allocation('run', 'run', 'project', scope=scope or {
            'type': 'record', 'kind': 'run', 'reference': c.reference('run', 1, 'resource_scope', 'run')},
            purpose_limits=resources['purpose_limits'], allocation_id=allocation))
        for name, identity, kind in (('project_account', 'project', 'project'), ('run_account', 'run', 'run')):
            value['preparation']['allocation'][name] = {'account_id': identity, 'operation_id': 'op_' + identity,
                'anchor': c.reference(identity, 1, 'resource_scope', kind)}
        return c.RunControlRequest(value)

    def ledger_rows(self, store):
        """Snapshot every resource table, including recorded observations and settlements in operations."""
        tables = ('resource_operations', 'resource_accounts', 'resource_allocations', 'resource_record_links', 'resource_reservations')
        return {name: list(store._connection.execute('SELECT * FROM ' + name + ' ORDER BY 1')) for name in tables}

    def test_not_yet_valid_real_approval_and_exact_expectations(self):
        """A real later-valid approval cannot authorize an earlier explicit lifecycle evaluation."""
        store, request = self.populated()
        future = '2026-11-02T13:00:00.000000Z'
        proposed = self.approve(store, request, valid_from=future)
        with self.assertRaisesRegex(c.RunControlPermissionError, 'not_yet_valid'):
            f.commit(store, proposed)
        self.assertIsNone(store.head(c.control_id('run')))
        # The old expected pin fails even when the actual new approval is eligible.
        with self.assertRaisesRegex(c.RunControlPermissionError, 'expected decision'):
            f.commit(store, request, evaluated_at=future)
        self.assertIsNone(store.head(c.obligation_id('prepare')))
        self.assertEqual(f.commit(store, proposed, evaluated_at=future).to_dict()['disposition'], 'prepared')

    def test_unchanged_public_fingerprint_requires_current_key_bytes(self):
        """Withdrawn and wrong keys fail continuation despite unchanged public policy identity."""
        store, request = self.populated()
        prepared = f.commit(store, request)
        paused = f.commit(store, f.successor(request, prepared, 'pause'))
        proposed = f.successor(request, paused, 'continue')
        for key, status in ((None, 'current policy is unavailable'), (b'wrong-disposable-key-bytes-32bytes', 'unauthenticated')):
            policy = f.authority.policy(key=key or f.authority.KEY)
            self.assertEqual(a.policy_fingerprint(policy), a.policy_fingerprint(f.authority.policy()))
            if key is None:
                # External credential withdrawal may invalidate the supplied host
                # object; its unchanged public fields do not restore missing bytes.
                object.__setattr__(policy.credentials[0], 'key', None)
            with self.assertRaisesRegex(c.RunControlPermissionError, status):
                f.commit(store, proposed, policy=policy)
        self.assertEqual(store.head(c.control_id('run')), 2)
        self.assertIsNone(store.head(c.obligation_id('continue')))

    def test_eligible_changed_public_policy_cannot_continue(self):
        """A still-eligible configuration change fails the immutable prepared policy check before pending denial."""
        store, request = self.populated()
        prepared = f.commit(store, request)
        paused = f.commit(store, f.successor(request, prepared, 'pause'))
        policy = f.authority.policy(projects=('project', 'additional-project'))
        eligibility = store.inspect_operating_eligibility('synthetic', 'project', purpose='setup', policy=policy,
            evaluated_at=f.authority.TIME, limits=f.authority.LIMITS)
        self.assertTrue(eligibility.to_dict()['eligible'])
        with self.assertRaisesRegex(c.RunControlPermissionError, 'public policy'):
            f.commit(store, f.successor(request, paused, 'continue'), policy=policy)
        self.assertIsNone(store.head(c.obligation_id('continue')))

    def test_exact_dossier_and_scope_mismatch_leave_no_members(self):
        """Valid but mismatched caller bindings cannot replace the evaluator's exact approved inputs."""
        store, request = self.populated()
        for change in ('digest', 'corpus', 'scope'):
            wire = request.to_dict()
            if change == 'digest':
                wire['expected_authority']['envelope_digest'] = '0' * 64
            elif change == 'corpus':
                wire['preparation']['current_corpus']['revision'] = 2
            else:
                wire['preparation']['operating_scope']['resources']['run_policy']['statement'] = 'Different declaration'
            with self.subTest(change=change), self.assertRaises(c.RunControlPermissionError):
                f.commit(store, c.RunControlRequest(wire))
            self.assertIsNone(store.head(c.control_id('run')))
            self.assertIsNone(store.head(c.obligation_id('prepare')))

    def test_explicit_generic_advance_keeps_original_account_anchors(self):
        """An explicit later generic revision succeeds without moving the prepared resource scope."""
        store, request = self.populated()
        request = self.anchored(store, request)
        prepared = f.commit(store, request)
        before = self.ledger_rows(store)
        store.submit(submission('advance-run', [record('run', 2, 'run', record_references=[
            RecordReference('project', 1, 'project', 'project')])], {'run': 1}))
        checkpoint = f.commit(store, f.successor(request, prepared, 'checkpoint', run_revision=2))
        self.assertEqual(store.get_revision(c.control_id('run'), 2).content['request']['run_revision'], 2)
        self.assertEqual(self.ledger_rows(store), before)
        prepared_wire = store.get_revision(c.control_id('run'), 1).content
        self.assertEqual(prepared_wire['request']['preparation']['allocation']['run_account']['anchor']['revision'], 1)
        with self.assertRaises(c.RunControlStateError):
            f.commit(store, f.successor(request, checkpoint, 'pause', run_revision=1))
        # Both absent and wrong-project linkage reject an explicitly selected later revision.
        store.submit(submission('wrong-project', [record('other-project', kind='project')]))
        for revision, links in ((3, []), (4, [RecordReference('other-project', 1, 'project', 'project')])):
            store.submit(submission('run-' + str(revision), [record('run', revision, 'run', record_references=links)], {'run': revision - 1}))
            with self.assertRaisesRegex(c.RunControlStateError, 'project reference'):
                f.commit(store, f.successor(request, checkpoint, 'pause', run_revision=revision))
        self.assertEqual(self.ledger_rows(store), before)

    def test_spent_reserved_and_uncertain_resource_rows_are_preserved(self):
        """Recorded spending and independent reserved/uncertain closeout liabilities survive all reductions."""
        store, request = self.populated()
        scope = request.to_dict()['preparation']['operating_scope']
        scope['resources']['purpose_limits']['closeout'] = ledger.vector(local_time=4, local_storage=4)
        request = self.approve(store, request, scope=a.OperatingScope(scope))
        request = self.anchored(store, request)
        for identity in ('spent', 'reserved', 'uncertain'):
            store.reserve_resources(ledger.reservation(identity, account='run', purpose='closeout', maxima=ledger.vector(local_time=1)))
        store.observe_resource_usage(ledger.observation('completed', reservation_id='reservation_spent', account_id='run',
            event='authoritative_completion', usage=ledger.vector(local_time=1)))
        store.reconcile_resource_usage(ledger.reconciliation('settled', reservation_id='reservation_spent',
            account_id='run', observation_operation_id='op_completed'))
        store.observe_resource_usage(ledger.observation('lost', reservation_id='reservation_uncertain', account_id='run', event='acknowledgment_loss'))
        inspection = store.inspect_resources(limits=ledger.LIMITS).to_dict()
        closeout = next(item for item in inspection['balances'] if item['account_id'] == 'run' and item['purpose'] == 'closeout')
        time = next(item for item in closeout['dimensions'] if item['dimension_id'] == 'dim_local_time')
        self.assertEqual(time['known_spent'], '1')
        self.assertEqual(time['subtree_reserved'], '2')
        before = self.ledger_rows(store)
        result = f.commit(store, request)
        for action in ('pause', 'stop', 'abandon', 'checkpoint'):
            result = f.commit(store, f.successor(request, result, action), policy=None, evaluated_at=None)
        self.assertEqual(self.ledger_rows(store), before)

    def test_invalid_resource_anchors_and_normalized_rows(self):
        """Controller-only, wrong revision/allocation/parent and damaged normalized rows cannot anchor control."""
        for mode in ('controller', 'revision', 'allocation', 'parent', 'projection'):
            with self.subTest(mode=mode):
                store, request = self.populated()
                scope = None
                if mode == 'controller':
                    scope = ledger.scope('run', 'run')
                if mode == 'revision':
                    store.submit(submission('run2', [record('run', 2, 'run', record_references=[RecordReference('project', 1, 'project', 'project')])], {'run': 1}))
                request = self.anchored(store, request, scope=scope, allocation='wrong' if mode == 'allocation' else 'allocation')
                if mode == 'revision':
                    value = request.to_dict()
                    value['run_revision'] = 2
                    value['preparation']['allocation']['run_account']['anchor']['revision'] = 2
                    request = c.RunControlRequest(value)
                if mode == 'parent':
                    store._connection.execute("UPDATE resource_accounts SET parent_account_id=NULL WHERE account_id='run'")
                if mode == 'projection':
                    store._connection.execute("UPDATE resource_allocations SET purpose_limits_json='{}' WHERE allocation_id='allocation'")
                before = self.ledger_rows(store)
                with self.assertRaises((c.RunControlStateError, c.RunControlIntegrityError)):
                    f.commit(store, request)
                self.assertEqual(self.ledger_rows(store), before)
                self.assertIsNone(store.head(c.control_id('run')))

    def test_schema2_unavailable_success_and_known_account_rejection(self):
        """Schema 2 records explicit resource unavailability and never adopts schema-3 account declarations."""
        store, request = self.populated(schema=2)
        wire = request.to_dict()
        wire['preparation']['allocation']['project_account'] = {'account_id': 'project', 'operation_id': 'op_project',
            'anchor': c.reference('project', 1, 'resource_scope', 'project')}
        with self.assertRaisesRegex(c.RunControlStateError, 'schema 2'):
            f.commit(store, c.RunControlRequest(wire))
        self.assertEqual(f.commit(store, request).to_dict()['disposition'], 'prepared')

    def test_scientific_outcome_and_illegal_terminal_store_transitions(self):
        """Evidence updates cannot silently turn cancellation into scientific success or resume it."""
        store, request = self.populated()
        result = f.commit(store, request)
        stopped = f.commit(store, f.successor(request, result, 'stop'))
        for action in ('stop', 'pause', 'continue'):
            with self.subTest(action=action), self.assertRaises(c.RunControlStateError):
                f.commit(store, f.successor(request, stopped, action, operation='invalid-' + action))
        cancelled = f.commit(store, f.successor(request, stopped, 'cancel'))
        checkpoint = f.successor(request, cancelled, 'checkpoint').to_dict()
        checkpoint['report']['declarations']['outcome']['label'] = 'objective_met'
        with self.assertRaises(c.RunControlStateError):
            f.commit(store, c.RunControlRequest(checkpoint))
        self.assertEqual(store.head(c.control_id('run')), 3)
        self.assertIsNone(store.head(c.obligation_id('checkpoint')))
