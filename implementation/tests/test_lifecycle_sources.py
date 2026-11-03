"""Real coherent source commitment, immutable original recovery and closed detached contracts."""

from copy import deepcopy
from dataclasses import replace, fields
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_source as s, lifecycle_source_capture as capture
from research_pipeline import lifecycle_report_binding as b, run_control as c
from research_pipeline.domain import ArtifactReference, RecordReference
from research_pipeline.store import RecordStore, RecordNotFoundError, SubmissionConflictError
from research_pipeline.artifacts import ArtifactNotFoundError
from tests import lifecycle_source_fixtures as f, run_control_fixtures as controls
from tests import lifecycle_binding_fixtures as bindings, resource_fixtures as resources
from tests.test_report_resources import funded
from tests.test_store import record, request as submission
from tests.test_work_product import manifest
from tests.test_work_product_store import product


class LifecycleSourceTests(unittest.TestCase):
    """Exercise actual source-only durable state without rendering, current authority or admission."""

    def setUp(self):
        """Allocate isolated stores under the caller's disposable temporary directory."""
        temporary = TemporaryDirectory(prefix='lifecycle-source-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.serial = 0

    def store(self, schema=2):
        """Create one supported real schema and its accepted original control preparation."""
        self.serial += 1
        store = RecordStore.create(self.root / str(self.serial), schema_version=schema)
        self.addCleanup(store.close)
        request, result = f.populate(store)
        return store, request, result

    def test_both_schemas_empty_source_identity_and_original_pending_contract(self):
        """Commit empty scientific selections with one event, separate operations, and unchanged obligations."""
        for schema in (2, 3):
            with self.subTest(schema=schema):
                store, request, original = self.store(schema)
                intent = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
                self.assertEqual(intent['state'], 'durable_intent')
                self.assertIsNone(intent['result'])
                result = f.commit(store).to_dict(limits=f.LIMITS)
                saved = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
                self.assertEqual(result['operation_id'], c._identity('run-control-source-', 'prepare'))
                self.assertEqual(len(result['receipt']['revisions']), 1)
                self.assertEqual(result['receipt']['event_id'], saved['scientific']['watermark']['event_id'] + 1)
                self.assertEqual(saved['binding']['preparation'], saved['binding']['transition'])
                self.assertEqual(saved['binding']['transition']['content']['request']['report']['selection'], [])
                self.assertEqual(saved['scientific']['limits'], request.to_dict()['report']['limits']['snapshot'])
                self.assertGreater(saved['observed_at'], request.to_dict()['transitioned_at'])
                self.assertFalse(saved['ordinary_work_allowed'])
                self.assertEqual(saved['qualifications'], s.QUALIFICATIONS)
                self.assertIsNone(store.get_submission(c.report_operation_id('prepare')))
                self.assertIsNone(store.head(c._identity('run-control-output-', 'prepare')))
                self.assertIsNone(store.head('run-report-' + hashlib.sha256(b'run').hexdigest()))
                self.assertEqual(store.get_run_control_operation('prepare', limits=controls.LIMITS).to_dict(), original.to_dict())
                self.assertEqual(len(store.inspect_run_control('run', limits=controls.LIMITS).to_dict()['pending_obligations']), 1)
                state = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
                self.assertEqual((state['state'], state['artifact_verification']), ('committed_source', 'not_checked'))
                self.assertEqual(state['result'], result)
                with self.assertRaises(SubmissionConflictError):
                    store.commit_lifecycle_source('prepare', expected_binding_digest='0'*64, limits=f.LIMITS)

    def test_delayed_original_intent_baseline_later_control_and_settlement(self):
        """Capture an older obligation after cancellation and settlement, retaining saved-note baseline and original intent."""
        store = RecordStore.create(self.root / 'delayed', schema_version=3)
        self.addCleanup(store.close)
        original = controls.populate(store)
        artifact = store.put_artifact(b'Saved note, not an earlier report.\n')
        store.submit_typed(submission('saved-work', [product('saved-note', manifest(artifact))]))
        store.submit(submission('run-two', [record('run', 2, 'run', record_references=[RecordReference('project', 1, 'project', 'project')])], {'run': 1}))
        wire = original.to_dict()
        wire['run_revision'] = 2
        wire['preparation']['start_baseline'] = c.reference('saved-note', 1, 'start_baseline', 'work_product_manifest')
        original = c.RunControlRequest(wire)
        result = controls.commit(store, original)
        funded(store, private=True, sibling=True)
        store.reserve_resources(resources.reservation(maxima=resources.vector(tool_calls=10)))
        store.observe_resource_usage(resources.observation(usage=resources.vector(None, tool_calls=4)))
        older = controls.successor(original, result, 'checkpoint')
        older_wire = older.to_dict()
        older_wire['report']['selection'] = [c.reference('saved-note', 1, 'report_selection', 'work_product_manifest')]
        older_wire['report']['declarations']['objective']['text']['value'] = bindings.NARRATIVE
        older = c.RunControlRequest(older_wire)
        result = controls.commit(store, older, policy=None, evaluated_at=None)
        for action in ('pause', 'stop', 'cancel'):
            proposed = controls.successor(original, result, action).to_dict()
            proposed['report']['declarations']['objective']['text']['value'] = 'Later intent ' + action
            if action == 'cancel':
                proposed['operational_reason']['code'] = 'model_forbidden'
            result = controls.commit(store, c.RunControlRequest(proposed), policy=None, evaluated_at=None)
        store.observe_resource_usage(resources.observation('complete', event='authoritative_completion', usage=resources.vector(tool_calls=7)))
        store.reconcile_resource_usage(resources.reconciliation())
        before = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
        with patch('research_pipeline.run_control_store._authorize', side_effect=AssertionError('current policy')), \
                patch('research_pipeline.reports.render_report', side_effect=AssertionError('renderer')):
            committed = f.commit(store, 'checkpoint').to_dict(limits=f.LIMITS)
        saved = store.read_lifecycle_source('checkpoint', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        self.assertEqual(saved['binding']['transition']['content']['request'], older.to_dict())
        self.assertEqual(saved['baseline'], wire['preparation']['start_baseline'])
        self.assertEqual(saved['binding']['transition']['revision'], 2)
        self.assertEqual(saved['binding']['transition']['content']['request']['run_revision'], 2)
        self.assertEqual(saved['control']['disposition'], 'cancelled')
        self.assertEqual(len(saved['control']['pending_obligations']), 5)
        self.assertEqual(saved['control']['transitions'], before['transitions'])
        self.assertEqual(saved['control']['pending_obligations'], before['pending_obligations'])
        self.assertEqual(saved['resources']['operations'][-1]['request']['kind'], 'reconcile')
        self.assertIn('sibling', [a['account_id'] for a in saved['resources']['accounts']])
        self.assertNotIn('OTHER-PROJECT-SECRET', c.canonical(saved))
        self.assertNotIn('PRIVATE-POLICY-SECRET', c.canonical(saved))
        self.assertEqual([i['receipt']['sequence'] for i in saved['resources']['operations']][:2], [1, 3])
        self.assertEqual(saved['verified_artifacts'], [artifact.to_dict()])
        self.assertEqual(committed['captured_control']['reference']['revision'], 5)
        # An earlier source can be captured after a later one without consuming O.
        self.assertEqual(f.commit(store, 'prepare').to_dict(limits=f.LIMITS)['captured_control']['reference']['revision'], 5)
        self.assertEqual(len(store.inspect_run_control('run', limits=controls.LIMITS).to_dict()['pending_obligations']), 5)

    def test_retry_reopen_later_facts_no_clock_policy_capture_or_artifact_reads(self):
        """Metadata recovery returns immutable original receipt/date even after later facts and missing source bytes."""
        store, request, control_result = self.store()
        result = f.commit(store).to_dict(limits=f.LIMITS)
        root = self.root / str(self.serial)
        controls.commit(store, controls.successor(request, control_result, 'cancel'), policy=None, evaluated_at=None)
        store.close()
        source_path = root / 'objects' / result['source_artifact']['digest']
        source_path.unlink()
        zero = replace(f.LIMITS, max_artifacts=0, max_artifact_total_bytes=0)
        with RecordStore.open(root) as reopened:
            with patch.object(capture, 'datetime', side_effect=AssertionError('clock')), \
                    patch.object(capture, '_resources', side_effect=AssertionError('resource replay')), \
                    patch.object(RecordStore, '_capture_snapshot', side_effect=AssertionError('recapture')), \
                    patch.object(RecordStore, 'read_artifact', side_effect=AssertionError('artifact read')), \
                    patch('research_pipeline.artifacts.ArtifactStore.verify', side_effect=AssertionError('artifact verify')):
                retried = reopened.commit_lifecycle_source('prepare', expected_binding_digest=result['binding_digest'], limits=zero)
                self.assertEqual(retried.to_dict(limits=zero), result)
                self.assertEqual(reopened.get_lifecycle_source_operation('prepare', limits=zero).to_dict(limits=zero), result)
                self.assertEqual(reopened.inspect_lifecycle_source('prepare', limits=zero).to_dict(limits=zero)['result'], result)
            with self.assertRaises(ArtifactNotFoundError):
                reopened.read_lifecycle_source('prepare', limits=f.LIMITS)

    def test_fabricated_binding_and_missing_original_arguments(self):
        """A completely rehashed offline-consistent fabrication cannot replace persisted origin."""
        store, _, _ = self.store()
        inspection = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
        packet = bindings.packet((inspection['transitions'][0]['envelope'], inspection['transitions'][0]['envelope'], inspection['pending_obligations'][0]))
        for name in ('preparation', 'transition'):
            packet[name]['content']['request']['report']['declarations']['objective']['text']['value'] = 'Fabricated offline declaration'
            bindings.reproject(packet, name)
        fabricated = b.LifecycleReportBinding(packet, limits=bindings.LIMITS)
        digest = b.binding_digest(fabricated, limits=bindings.LIMITS)
        with self.assertRaises(SubmissionConflictError):
            store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=f.LIMITS)
        self.assertIsNone(store.get_lifecycle_source_operation('prepare', limits=f.LIMITS))
        self.assertIsNone(store.get_lifecycle_source_operation('absent', limits=f.LIMITS))
        for method in (store.inspect_lifecycle_source, store.read_lifecycle_source):
            with self.assertRaises(RecordNotFoundError):
                method('absent', limits=f.LIMITS)
        with self.assertRaises(RecordNotFoundError):
            store.commit_lifecycle_source('absent', expected_binding_digest='0'*64, limits=f.LIMITS)
        with self.assertRaises(TypeError):
            store.commit_lifecycle_source('prepare', limits=f.LIMITS)
        with self.assertRaises(s.LifecycleSourceArgumentError):
            store.get_lifecycle_source_operation(True, limits=f.LIMITS)

    def test_different_sufficient_caller_budgets_preserve_first_source_bytes(self):
        """A rolled-back capture and successful retry with larger budgets yield identical canonical source bytes."""
        store, _, _ = self.store(3)
        digest = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['binding_digest']
        smaller = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, max_metadata_bytes=2000000))
        instant = datetime.now(timezone.utc)
        before = set((self.root / str(self.serial) / 'objects').iterdir())
        def fault(point):
            """Retain the actual placed source object while rolling back all source metadata."""
            if point == 'after_artifacts':
                raise RuntimeError('capture rolled back')
        with patch.object(capture, 'datetime') as clock:
            clock.now.return_value = instant
            with patch.object(capture, '_fault', fault), self.assertRaises(RuntimeError):
                store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=smaller)
            objects = set((self.root / str(self.serial) / 'objects').iterdir()) - before
            self.assertEqual(len(objects), 1)
            unregistered = objects.pop().read_bytes()
            result = store.commit_lifecycle_source('prepare', expected_binding_digest=digest, limits=f.LIMITS).to_dict(limits=f.LIMITS)
        self.assertEqual(hashlib.sha256(unregistered).hexdigest(), result['source_artifact']['digest'])
        self.assertEqual(store.read_artifact(ArtifactReference(**result['source_artifact'])), unregistered)

    def test_capture_clock_cannot_backdate_and_retry_ignores_it(self):
        """A fresh clock predating actual audit metadata rejects without changing durable intent."""
        store, _, _ = self.store()
        intent = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
        with patch.object(capture, 'datetime') as clock:
            clock.now.return_value = datetime(2000, 1, 1, tzinfo=timezone.utc)
            with self.assertRaises(s.LifecycleSourceStateError):
                store.commit_lifecycle_source('prepare', expected_binding_digest=intent['binding_digest'], limits=f.LIMITS)
        self.assertEqual(store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)['state'], 'durable_intent')


class LifecycleSourceCodecTests(unittest.TestCase):
    """Independent codec ceilings, strict exact types and forged retained state never authenticate persistence."""

    @classmethod
    def setUpClass(cls):
        """Capture actual wire values once for bounded offline semantic and accounting regressions."""
        with TemporaryDirectory(prefix='source-codecs-') as temporary:
            with RecordStore.create(Path(temporary) / 'store') as store:
                f.populate(store)
                cls.result = f.commit(store).to_dict(limits=f.LIMITS)
                cls.observation = store.read_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)
                cls.inspection = store.inspect_lifecycle_source('prepare', limits=f.LIMITS).to_dict(limits=f.LIMITS)

    def test_canonical_codecs_and_exact_workspace_equality(self):
        """Real permitted 64P/72P equality and one-unit overflow precede semantic reconstruction."""
        for cls, doc, dumps, loads in (
            (s.LifecycleSourceObservation, self.observation, s.dumps_observation, s.loads_observation),
            (s.LifecycleSourceCommitResult, self.result, s.dumps_commit_result, s.loads_commit_result),
            (s.LifecycleSourceInspection, self.inspection, s.dumps_inspection, s.loads_inspection)):
            with self.subTest(cls=cls.__name__):
                text = c.canonical(doc)
                p = len(text)
                exact = replace(f.LIMITS, max_work_bytes=64*p, max_result_bytes=p,
                                max_source_bytes=max(p, len(c.canonical(self.observation))))
                obj = cls(doc, limits=exact)
                self.assertNotEqual(obj, cls(doc, limits=exact))
                self.assertNotIn('binding_digest', repr(obj))
                with self.assertRaises(s.LifecycleSourceLimitError):
                    cls(doc, limits=replace(exact, max_work_bytes=64*p-1))
                retained = replace(exact, max_work_bytes=72*p, max_input_bytes=p)
                self.assertEqual(dumps(obj, limits=retained), text)
                self.assertEqual(loads(text.encode(), limits=retained).to_dict(limits=retained), doc)
                with self.assertRaises(s.LifecycleSourceLimitError):
                    dumps(obj, limits=replace(retained, max_work_bytes=72*p-1))
                with self.assertRaises(s.LifecycleSourceLimitError):
                    loads(text, limits=replace(retained, max_input_bytes=p-1))
                with self.assertRaises(s.LifecycleSourceLimitError):
                    cls(doc, limits=replace(f.LIMITS, max_result_bytes=p-1))

    def test_nodes_depth_equality_and_invalid_retained_values(self):
        """Count actual repeated occurrences, reject one-node/depth overflow and bypass-mutated objects."""
        nodes, depth = bindings.counts(self.observation)
        exact = replace(f.LIMITS, max_nodes=nodes, max_depth=depth)
        obj = s.LifecycleSourceObservation(self.observation, limits=exact)
        self.assertEqual(obj.to_dict(limits=exact), self.observation)
        for bad in (replace(exact, max_nodes=nodes-1), replace(exact, max_depth=depth-1)):
            with self.assertRaises(s.LifecycleSourceLimitError):
                s.LifecycleSourceObservation(self.observation, limits=bad)
        for value in (None, b'{}', '{}', ' ' + obj._json):
            forged = object.__new__(s.LifecycleSourceObservation)
            object.__setattr__(forged, '_json', value)
            with self.assertRaises(s.LifecycleSourceValidationError):
                forged.to_dict(limits=f.LIMITS)
        with self.assertRaises(s.LifecycleSourceValidationError):
            object.__new__(s.LifecycleSourceObservation).to_dict(limits=f.LIMITS)
        for text in ('{"format":1,"format":2}', '{"x":NaN}', '"\\ud800"'):
            with self.assertRaises(s.LifecycleSourceValidationError):
                s.loads_observation(text, limits=f.LIMITS)

    def test_mutated_limits_before_payload_and_closed_fields(self):
        """All new scalar ceilings reject bypass mutation before touching untrusted content."""
        for cls, template in ((s.LifecycleSourceLimits, f.LIMITS),
                              (s.LifecycleScientificCaptureLimits, f.LIMITS.scientific),
                              (s.LifecycleResourceCaptureLimits, f.LIMITS.resources)):
            for field in fields(cls):
                if field.name in ('control', 'binding', 'scientific', 'resources'):
                    continue
                bad = replace(template)
                object.__setattr__(bad, field.name, True)
                limits = bad if cls is s.LifecycleSourceLimits else replace(f.LIMITS)
                if cls is not s.LifecycleSourceLimits:
                    object.__setattr__(limits, 'scientific' if cls is s.LifecycleScientificCaptureLimits else 'resources', bad)
                with self.subTest(field=field.name), self.assertRaises(s.LifecycleSourceArgumentError):
                    s.LifecycleSourceObservation(None, limits=limits)
        for change in ('extra', 'version', 'ordinary_work_allowed', 'recheck_required', 'snapshot_id'):
            doc = deepcopy(self.observation)
            doc[change] = False if change == 'recheck_required' else True
            with self.subTest(change=change), self.assertRaises(s.LifecycleSourceValidationError):
                s.LifecycleSourceObservation(doc, limits=f.LIMITS)

    def test_scientific_and_resource_work_equality_before_shared_algorithms(self):
        """Reserve published independent Ws and empty Wr exactly; reject one unit less before protected work."""
        m = self.observation['scientific']['limits']['max_metadata_bytes']
        ws = 64*m+4096
        sufficient = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, max_work_bytes=ws))
        s.LifecycleSourceObservation(self.observation, limits=sufficient)
        with patch.object(s.DetachedSnapshot, '__init__', side_effect=AssertionError('snapshot constructor')):
            with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'scientific workspace'):
                s.LifecycleSourceObservation(self.observation, limits=replace(sufficient,
                    scientific=replace(sufficient.scientific, max_work_bytes=ws-1)))
        size = len(c.canonical(self.observation['resources']))
        wr = 256*(size+1)+262144
        sufficient = replace(f.LIMITS, resources=replace(f.LIMITS.resources, max_work_bytes=wr))
        s.LifecycleSourceObservation(self.observation, limits=sufficient)
        with patch('research_pipeline.reports._validate_resources', side_effect=AssertionError('ledger validation')):
            with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'resource replay workspace'):
                s.LifecycleSourceObservation(self.observation, limits=replace(sufficient,
                    resources=replace(sufficient.resources, max_work_bytes=wr-1)))
