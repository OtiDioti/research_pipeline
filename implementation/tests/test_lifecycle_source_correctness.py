"""Real-store resource chronology and exact saved-baseline scalar regressions."""

from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_source as s, lifecycle_source_capture as capture
from research_pipeline import lifecycle_report_binding as binding, run_control as c
from research_pipeline import resource_ledger as ledger, resources, reports
from research_pipeline.backup import create_backup, restore_backup
from research_pipeline.store import RecordStore, RecordNotFoundError, SubmissionConflictError
from tests import lifecycle_source_fixtures as f, run_control_fixtures as controls
from tests import resource_fixtures as rf
from tests.test_report_resources import funded
from tests.test_store import request as submission
from tests.test_work_product import manifest
from tests.test_work_product_store import product
from tests.test_lifecycle_source_repairs import guarded
from tests.test_vault import restore_directories


SCIENTIFIC = '2026-11-03T08:00:00.000000Z'
TRANSITION = '2026-11-03T08:01:00.000000Z'
CONTROL_COMMIT = '2026-11-03T08:02:00.000000Z'
RESOURCE = '2026-11-03T09:00:00.000000Z'
BETWEEN = '2026-11-03T09:30:00.000000Z'
MAXIMUM = '2026-11-03T10:00:00.000000Z'
LATER = '2026-11-03T10:30:00.000000Z'
METADATA = '2026-11-03T11:00:00.000000Z'


@contextmanager
def clock_at(module, *dates):
    """Patch only a named production clock phase, yielding its exact sampling mock."""
    with patch(module + '.datetime') as clock:
        values = [datetime.fromisoformat(date.replace('Z', '+00:00')) for date in dates]
        if len(values) == 1:
            clock.now.return_value = values[0]
        else:
            clock.now.side_effect = values
        yield clock


@contextmanager
def pure_consumers():
    """Fail on storage, clock, policy or external process/network access by detached validation."""
    with ExitStack() as stack:
        for target in ('research_pipeline.store.RecordStore._transaction',
                       'research_pipeline.run_control_store._authorize',
                       'research_pipeline.resource_ledger._inspect',
                       'subprocess.Popen', 'socket.socket'):
            stack.enter_context(patch(target, side_effect=AssertionError('impure detached consumer')))
        clock = stack.enter_context(patch.object(capture, 'datetime'))
        clock.now.side_effect = AssertionError('detached clock access')
        yield


def rehash(document):
    """Refresh only the outer identity so semantic mutations retain all nested original bytes."""
    document['snapshot_id'] = s._hash({k: v for k, v in document.items() if k != 'snapshot_id'})
    return document


class LifecycleSourceCorrectnessTests(unittest.TestCase):
    """Verify independent factual clocks and exact baselines without changing accepted fixtures."""

    def setUp(self):
        """Allocate private disposable stores and restore backup directory modes on cleanup."""
        temporary = TemporaryDirectory(prefix='source-correctness-')
        self.addCleanup(temporary.cleanup)
        self.parent, self.serial = Path(temporary.name), 0
        self.addCleanup(restore_directories, self.parent)

    def prepare(self, *, peak='sibling', saved=False, schema=3):
        """Commit genuine intent, optional saved work and independent dated resource history.

        A private project is interleaved before child/sibling operations. The peak
        belongs to an earlier sequence, and a later cancellation remains pending.
        Returns the live store, original request, latest control result and digest.
        """
        self.serial += 1
        store = RecordStore.create(self.parent / str(self.serial), schema_version=schema)
        self.addCleanup(store.close)
        with clock_at('research_pipeline.store', SCIENTIFIC):
            if saved:
                original = controls.populate(store)
                artifact = store.put_artifact(b'Arbitrary saved note, not a report.\n')
                store.submit_typed(submission('saved-work', [product('saved-note', manifest(artifact))]))
                wire = original.to_dict()
                wire['preparation']['start_baseline'] = c.reference('saved-note', 1, 'start_baseline', 'work_product_manifest')
                wire['report']['selection'] = []
                for field in ('results', 'completed_checks', 'unresolved_issues', 'saved_work', 'outstanding_jobs'):
                    wire['report']['declarations'][field] = []
                original = c.RunControlRequest(wire)
                result = controls.commit(store, original)
            else:
                original, result = f.populate(store)
            if peak is not None:
                dates = [RESOURCE] * 7
                dates[1 if peak == 'private' else 5] = MAXIMUM
                with clock_at('research_pipeline.resource_ledger', *dates) as clock:
                    funded(store, private=True, sibling=True)
                    self.assertEqual(clock.now.call_count, 7)
                with clock_at('research_pipeline.resource_ledger', RESOURCE):
                    store.reserve_resources(rf.reservation(maxima=rf.vector(tool_calls=10)))
                    store.observe_resource_usage(rf.observation(usage=rf.vector(None, tool_calls=4)))
        with clock_at('research_pipeline.store', CONTROL_COMMIT):
            cancel = controls.successor(original, result, 'cancel', transitioned_at=TRANSITION)
            result = controls.commit(store, cancel, policy=None, evaluated_at=None)
        digest = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']
        return store, original, result, digest

    def commit(self, store, digest, date):
        """Capture with one independently sampled source time and a later metadata receipt clock."""
        with clock_at('research_pipeline.lifecycle_source_capture', date) as clock, \
                clock_at('research_pipeline.store', METADATA):
            result = store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=f.LIMITS)
            self.assertEqual(clock.now.call_count, 1)
        return result.to_dict(limits=f.LIMITS)

    def consumers(self, document, *, error=None, limits=f.LIMITS):
        """Exercise six public/bypass paths, requiring canonical identity or the exact error family."""
        text = c.canonical(document)
        forged = object.__new__(s.LifecycleSourceObservation)
        object.__setattr__(forged, '_json', text)
        calls = (lambda: s.LifecycleSourceObservation(document, limits=limits),
                 lambda: s.LifecycleSourceObservation.from_dict(document, limits=limits),
                 lambda: s.loads_observation(text, limits=limits),
                 lambda: s.loads_observation(text.encode('ascii'), limits=limits),
                 lambda: forged.to_dict(limits=limits),
                 lambda: s.dumps_observation(forged, limits=limits))
        with pure_consumers():
            for index, call in enumerate(calls):
                with self.subTest(consumer=index):
                    if error is not None:
                        with self.assertRaises(error):
                            call()
                    else:
                        actual = call()
                        if type(actual) is dict:
                            actual = c.canonical(actual)
                        elif type(actual) is s.LifecycleSourceObservation:
                            actual = actual._json
                        self.assertEqual(actual, text)

    def assert_scientific_control_before(self, store, date):
        """Establish that a rejection cannot be explained by any earlier scientific/control guard."""
        inspection = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
        self.assertLess(inspection['watermark']['committed_at'], date)
        for transition in inspection['transitions']:
            self.assertLess(transition['envelope']['content']['request']['transitioned_at'], date)
            self.assertLess(transition['receipt']['committed_at'], date)
        for (committed_at,) in store._connection.execute('SELECT committed_at FROM audit_events'):
            self.assertLess(committed_at, date)
        return inspection

    def test_fresh_resource_clock_failure_preserves_all_rows_objects_and_pending_intent(self):
        """Reject retained and private-prefix future receipts before placement or insertion, without mutations."""
        for peak in ('sibling', 'private'):
            with self.subTest(peak=peak):
                store, _, _, digest = self.prepare(peak=peak)
                pending = self.assert_scientific_control_before(store, BETWEEN)
                complete = store.inspect_resources(limits=rf.LIMITS).to_dict()
                maximum = max(complete['operations'], key=lambda op: op['receipt']['committed_at'])
                self.assertEqual(maximum['receipt']['committed_at'], MAXIMUM)
                self.assertLess(BETWEEN, MAXIMUM)
                self.assertLess(maximum['receipt']['sequence'], complete['resource_sequence'])
                self.assertEqual(maximum['receipt']['account_id'], peak)
                # The dump includes registrations, submissions and every scientific,
                # control and resource row; object inventory checks placement too.
                before = tuple(store._connection.iterdump())
                objects = sorted((store._artifacts._root / 'objects').iterdir())
                with patch.object(store, 'put_artifact', side_effect=AssertionError('source placement')), \
                        patch.object(store, '_insert_submission', side_effect=AssertionError('source insertion')):
                    with self.assertRaises(s.LifecycleSourceStateError):
                        self.commit(store, digest, BETWEEN)
                self.assertEqual(tuple(store._connection.iterdump()), before)
                self.assertEqual(sorted((store._artifacts._root / 'objects').iterdir()), objects)
                self.assertEqual(store.inspect_run_control('run', limits=controls.LIMITS).to_dict(), pending)
                self.assertEqual(len(pending['pending_obligations']), 2)
                self.assertFalse(pending['ordinary_work_allowed'])
                self.assertTrue(pending['recheck_required'])
                self.assertIsNone(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS))
                self.assertIsNone(store.get_submission(c._identity('run-control-source-', 'prepare')))
                state = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
                self.assertEqual(state['state'], 'durable_intent')
                self.assertIsNone(state['result'])
                with self.assertRaises(RecordNotFoundError):
                    store.read_lifecycle_source('prepare', limits=f.LIMITS)

    def test_real_equality_later_and_detached_resource_chronology(self):
        """Allow genuine equality/later captures; reject only observed_at mutations before retained receipts."""
        for date in (MAXIMUM, LATER):
            store, _, _, digest = self.prepare()
            result = self.commit(store, digest, date)
            doc = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
            self.assertEqual(doc['observed_at'], date)
            self.assertEqual(result['snapshot_id'], doc['snapshot_id'])
            self.assertEqual(result['operation_id'], c._identity('run-control-source-', 'prepare'))
            event = reports.source_id(c.report_operation_id('prepare'))
            self.assertEqual(result['receipt']['revisions'], [[event, 1]])
            self.assertEqual(store.get_submission(result['operation_id']).to_dict(), result['receipt'])
            projection = doc['resources']
            sequences = [item['receipt']['sequence'] for item in projection['operations']]
            self.assertEqual(sequences[:2], [1, 3])
            self.assertEqual(max(item['receipt']['committed_at'] for item in projection['operations']), MAXIMUM)
            self.assertIn('sibling', [item['account_id'] for item in projection['accounts']])
            for secret in ('OTHER-PROJECT-SECRET', 'PRIVATE-POLICY-SECRET'):
                self.assertNotIn(secret, c.canonical(doc))
            self.consumers(doc)
            bad = deepcopy(doc)
            bad['observed_at'] = BETWEEN
            self.assertLess(doc['scientific']['watermark']['committed_at'], BETWEEN)
            for row in doc['scientific']['records']:
                self.assertLess(row['commit']['committed_at'], BETWEEN)
            for row in doc['control']['transitions']:
                self.assertLess(row['receipt']['committed_at'], BETWEEN)
                self.assertLess(row['envelope']['content']['request']['transitioned_at'], BETWEEN)
            self.assertLess(BETWEEN, MAXIMUM)
            self.consumers(rehash(bad), error=s.LifecycleSourceValidationError)
            self.assertEqual(bad['binding'], doc['binding'])
            self.assertEqual(bad['resources'], doc['resources'])

    def test_private_prefix_time_is_not_claimed_by_detached_projection(self):
        """Capture checks omitted private dates, while detached consumers can prove only retained facts."""
        store, _, _, digest = self.prepare(peak='private')
        self.commit(store, digest, MAXIMUM)
        doc = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        self.assertEqual(max(op['receipt']['committed_at'] for op in doc['resources']['operations']), RESOURCE)
        self.assertEqual(set(doc['resources']), {'format', 'version', 'project', 'run', 'resource_sequence',
            'complete_snapshot_id', 'operations', 'accounts', 'allocations', 'reservations',
            'reservation_usage', 'breaches', 'balances', 'scope', 'limits'})
        self.assertNotIn('OTHER-PROJECT-SECRET', c.canonical(doc))
        self.assertNotIn('PRIVATE-POLICY-SECRET', c.canonical(doc))
        self.consumers(doc)
        detached = deepcopy(doc)
        detached['observed_at'] = BETWEEN
        self.consumers(rehash(detached))

    def test_verified_read_checks_private_saved_prefix_but_not_later_operations(self):
        """A locally valid private receipt with a later date fails saved-prefix verification only."""
        store, _, _, digest = self.prepare(peak='private')
        result = self.commit(store, digest, MAXIMUM)
        original = store.read_lifecycle_source('prepare', limits=f.LIMITS)._json
        sequence = result['resource_sequence']
        with clock_at('research_pipeline.resource_ledger', METADATA):
            later = store.observe_resource_usage(rf.observation('later', usage=rf.vector(None, tool_calls=5)))
        self.assertGreater(later.to_dict()['sequence'], sequence)
        self.assertEqual(store.read_lifecycle_source('prepare', limits=f.LIMITS)._json, original)
        row = store._connection.execute('SELECT sequence,result_json FROM resource_operations WHERE operation_id=?', ('private-op',)).fetchone()
        receipt = resources.ResourceReceipt.from_dict(resources.strict_json(row[1])).to_dict()
        self.assertLessEqual(receipt['sequence'], sequence)
        receipt['committed_at'] = LATER
        checked = resources.ResourceReceipt.from_dict(receipt).to_dict()
        self.assertEqual(checked['committed_at'], LATER)
        store._connection.execute('UPDATE resource_operations SET result_json=?,committed_at=? WHERE operation_id=?',
                                  (resources.canonical(checked), LATER, 'private-op'))
        # Both persisted date representations agree, and full ledger validation
        # still succeeds; only chronology against the fixed source is false.
        self.assertEqual(store.get_resource_operation('private-op').to_dict(), checked)
        store.inspect_resources(limits=rf.LIMITS)
        with patch.object(capture, '_resources', side_effect=AssertionError('fresh resource capture')), \
                patch.object(ledger, '_inspect', side_effect=AssertionError('fresh replay')):
            with self.assertRaisesRegex(s.LifecycleSourceIntegrityError, 'predates resource prefix'):
                store.read_lifecycle_source('prepare', limits=f.LIMITS)
            with patch.object(capture, '_resource_originals', side_effect=AssertionError('metadata resource verification')):
                self.assertEqual(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS), result)
                self.assertEqual(store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['result'], result)
                self.assertEqual(store.commit_lifecycle_source('prepare', expected_binding_digest=digest,
                                                             limits=f.LIMITS).to_dict(limits=f.LIMITS), result)

    def test_exact_retry_after_clock_rollback_reopen_and_later_changes(self):
        """Original-ID reconciliation returns fixed dates before recapture, resource, clock or artifact work."""
        store, original, latest, digest = self.prepare()
        result = self.commit(store, digest, MAXIMUM)
        with clock_at('research_pipeline.store', METADATA):
            controls.commit(store, controls.successor(original, latest, 'checkpoint', operation='later-checkpoint',
                transitioned_at=LATER), policy=None, evaluated_at=None)
        with clock_at('research_pipeline.resource_ledger', METADATA):
            store.observe_resource_usage(rf.observation('later', usage=rf.vector(None, tool_calls=5)))
        root = store._artifacts._root
        for reopen in (False, True):
            if reopen:
                store.close()
                store = RecordStore.open(root)
                self.addCleanup(store.close)
            with ExitStack() as stack:
                source_clock = stack.enter_context(clock_at('research_pipeline.lifecycle_source_capture', SCIENTIFIC))
                # Metadata recovery still verifies the saved original binding;
                # only fresh capture and historical resource reads are forbidden.
                for target in ('_resources', '_resource_originals', '_fault'):
                    stack.enter_context(patch.object(capture, target, side_effect=AssertionError('retry recapture')))
                stack.enter_context(patch.object(ledger, '_inspect', side_effect=AssertionError('retry resource replay')))
                stack.enter_context(patch('research_pipeline.run_control_store._authorize', side_effect=AssertionError('retry policy')))
                for target in ('read_artifact', 'put_artifact', '_capture_snapshot'):
                    stack.enter_context(patch.object(store, target, side_effect=AssertionError('retry evidence access')))
                stack.enter_context(patch.object(store._artifacts, 'verify', side_effect=AssertionError('retry artifact verify')))
                recovered = store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=f.LIMITS)
                self.assertEqual(recovered.to_dict(limits=f.LIMITS), result)
                self.assertEqual(source_clock.now.call_count, 0)
                with self.assertRaises(SubmissionConflictError):
                    store.commit_lifecycle_source('prepare', expected_binding_digest='0'*64, limits=f.LIMITS)

    def test_saved_baseline_rejects_bool_and_float_aliases_in_every_consumer(self):
        """Retain arbitrary saved work and binding bytes while rejecting type-coercive redundant revisions."""
        store, _, _, digest = self.prepare(saved=True)
        result = self.commit(store, digest, MAXIMUM)
        doc = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        original = c.canonical(doc)
        binding_bytes = c.canonical(doc['binding'])
        self.assertIs(type(doc['baseline']['revision']), int)
        self.assertEqual(doc['baseline']['record_id'], 'saved-note')
        self.assertEqual(doc['baseline']['target_kind'], 'work_product_manifest')
        self.assertEqual(binding.binding_digest(binding.LifecycleReportBinding(doc['binding'], limits=f.LIMITS.binding),
                                               limits=f.LIMITS.binding), digest)
        self.consumers(doc)
        for alias in (True, 1.0):
            bad = deepcopy(doc)
            bad['baseline']['revision'] = alias
            self.consumers(rehash(bad), error=s.LifecycleSourceValidationError)
            self.assertEqual(c.canonical(bad['binding']), binding_bytes)
            self.assertEqual(bad['binding_digest'], digest)
        self.assertEqual(c.canonical(doc), original)
        self.assertEqual(store.read_lifecycle_source('prepare', limits=f.LIMITS)._json, original)
        self.assertEqual(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS), result)

    def test_nonempty_resource_saved_baseline_work_equality_and_deficits(self):
        """Exercise real 64P construction and 72P codec/retained boundaries before semantic work."""
        store, _, _, digest = self.prepare(saved=True)
        self.commit(store, digest, MAXIMUM)
        doc = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        self.assertTrue(doc['resources']['operations'])
        self.assertEqual(doc['baseline']['record_id'], 'saved-note')
        text = c.canonical(doc)
        size = len(text)
        exact = replace(f.LIMITS, max_work_bytes=64*size, max_source_bytes=size, max_result_bytes=size)
        self.assertEqual(s.LifecycleSourceObservation(doc, limits=exact)._json, text)
        self.assertEqual(s.LifecycleSourceObservation.from_dict(doc, limits=exact)._json, text)
        retained = replace(exact, max_work_bytes=72*size, max_input_bytes=size)
        self.consumers(doc, limits=retained)
        with patch.object(binding.LifecycleReportBinding, '__init__', side_effect=AssertionError('semantic binding')), \
                patch.object(s, '_capture_lower_bound', side_effect=AssertionError('chronology comparison')):
            for constructor in (s.LifecycleSourceObservation, s.LifecycleSourceObservation.from_dict):
                with self.assertRaises(s.LifecycleSourceLimitError):
                    constructor(doc, limits=replace(exact, max_work_bytes=64*size-1))
            forged = object.__new__(s.LifecycleSourceObservation)
            object.__setattr__(forged, '_json', text)
            small = replace(retained, max_work_bytes=72*size-1)
            for data in (text, text.encode('ascii')):
                with self.assertRaises(s.LifecycleSourceLimitError):
                    s.loads_observation(data, limits=small)
            with self.assertRaises(s.LifecycleSourceLimitError):
                forged.to_dict(limits=small)
            with self.assertRaises(s.LifecycleSourceLimitError):
                s.dumps_observation(forged, limits=small)

    def test_empty_schema_three_and_schema_two_unavailability_after_migration(self):
        """Empty prefixes add no date; schema-2 saved sources never query resources, even after migration."""
        for schema in (2, 3):
            store, _, _, digest = self.prepare(peak=None, schema=schema)
            with ExitStack() as stack:
                if schema == 2:
                    stack.enter_context(guarded(store, lambda sql, args: 'resource_' in sql.lower()))
                    stack.enter_context(patch.object(ledger, '_inspect', side_effect=AssertionError('schema-2 replay')))
                result = self.commit(store, digest, CONTROL_COMMIT)
                doc = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
            self.consumers(doc)
            self.assertEqual(doc['baseline'], doc['binding']['preparation']['content']['request']['preparation']['start_baseline'])
            if schema == 3:
                self.assertEqual(doc['resources']['resource_sequence'], 0)
                self.assertEqual(doc['resources']['operations'], [])
            else:
                unavailable = reports.unavailable('Schema 2: resource accounting unavailable; explicit migration to schema 3 is required.')
                self.assertEqual(doc['resources'], unavailable)
                exported = self.parent / 'schema-two-backup'
                create_backup(store, exported)
                with restore_backup(exported, self.parent / 'migrated', target_schema=3,
                                    migration_provenance=rf.PROVENANCE) as migrated:
                    with guarded(migrated, lambda sql, args: 'resource_' in sql.lower()), \
                            patch.object(ledger, '_inspect', side_effect=AssertionError('saved schema-2 replay')):
                        self.assertEqual(migrated.read_lifecycle_source('prepare', limits=f.LIMITS)._json, c.canonical(doc))
                        self.assertEqual(migrated.get_lifecycle_source_operation('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS), result)
