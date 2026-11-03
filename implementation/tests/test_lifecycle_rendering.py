"""Offline shared rendering of genuine first-capture source facts and adversarial retained objects."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import fields, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_rendering as r, lifecycle_report_source as s, reports
from research_pipeline.store import RecordStore
from tests import lifecycle_rendering_fixtures as f, lifecycle_source_fixtures as sources
from tests import run_control_fixtures as controls, lifecycle_binding_fixtures as bindings
from research_pipeline import lifecycle_report_binding as binding


class LifecycleRenderingTests(unittest.TestCase):
    """Preserve original facts, exact routes and closed gates without touching an available store."""

    @classmethod
    def setUpClass(cls):
        """Read genuine schema-2/3 sources and remove their stores before any assertion renders them."""
        cls.empty = []
        with TemporaryDirectory(prefix='lifecycle-rendering-') as temporary:
            root = Path(temporary)
            for schema in (2, 3):
                with RecordStore.create(root / str(schema), schema_version=schema) as store:
                    observation, _, _ = f.empty(store)
                    cls.empty.append(observation)
            with RecordStore.create(root / 'delayed', schema_version=3) as store:
                cls.delayed, cls.older = f.delayed(store)
        cls.doc = json.loads(cls.delayed._json)

    def render(self, observation, limits=f.LIMITS):
        """Exercise the full public operation with explicit independent allowances."""
        return r.render_lifecycle_report(observation, limits=limits)

    def assert_machine(self, observation, outputs):
        """Check closed schema, source-derived identities and all exact literal groups in both outputs."""
        doc = json.loads(observation._json)
        machine = json.loads(outputs['continuation.json'])
        self.assertEqual(type(outputs), dict)
        self.assertEqual(set(outputs), {'report.md', 'continuation.json'})
        self.assertTrue(all(type(v) is bytes for v in outputs.values()))
        self.assertEqual(outputs['continuation.json'], (f.canonical(machine) + '\n').encode('ascii'))
        self.assertEqual(set(machine), {'format', 'version', 'identities', 'saved_work', 'groups', 'continuation',
                                      'ordinary_work_allowed', 'recheck_required'})
        self.assertEqual(machine['format'], 'research_pipeline.lifecycle_report_continuation')
        self.assertIs(type(machine['version']), int)
        self.assertEqual(machine['version'], 1)
        self.assertIs(machine['ordinary_work_allowed'], False)
        self.assertIs(machine['recheck_required'], True)
        self.assertEqual(set(machine['groups']), set(f.GROUPS))
        selected = doc['binding']['transition']['content']['request']
        obligation = doc['binding']['obligation']['content']
        self.assertEqual(machine['identities'], {
            'control_operation_id': selected['operation_id'], 'report_operation_id': obligation['report_operation_id'],
            'run': {'record_id': selected['run_id'], 'revision': selected['run_revision'], 'relationship': 'run', 'target_kind': 'run'},
            'report_revision': obligation['report_revision'],
            'source_event': {'record_id': obligation['report_source_id'], 'revision': 1,
                             'relationship': 'lifecycle_report_source', 'target_kind': 'event'},
            'snapshot_id': doc['snapshot_id'], 'scientific_snapshot_id': doc['scientific']['snapshot_id'],
            'binding_digest': doc['binding_digest'], 'transitioned_at': selected['transitioned_at'],
            'observed_at': doc['observed_at'], 'scientific_watermark': doc['scientific']['watermark'],
            'resource_sequence': doc['resources'].get('resource_sequence')})
        markdown = outputs['report.md'].decode('utf-8')
        literal_values = [json.loads(line[4:]) for line in markdown.splitlines() if line.startswith('    ')]
        self.assertEqual(literal_values, [machine['identities']] + [machine['groups'][key] for key in f.GROUPS])
        self.assertEqual(markdown.count('\n## '), 7)
        self.assertIn('structural consistency only', markdown)
        self.assertNotIn('](source.json)', markdown)
        self.assertNotIn('](README.md)', markdown)
        self.assertNotIn('](continuation.json)', markdown)
        self.assertNotIn('reports/runs/', markdown)
        return machine

    def test_empty_both_schemas_and_all_routes(self):
        """An initial empty capture establishes no result and preserves complete inspection membership."""
        for observation in self.empty:
            machine = self.assert_machine(observation, self.render(observation))
            doc = json.loads(observation._json)
            groups = machine['groups']
            self.assertEqual(groups[f.GROUPS[1]]['empty_results'], 'No result was established by this report.')
            self.assertIn(b'\nNo result was established by this report.\n', self.render(observation)['report.md'])
            self.assertEqual(groups[f.GROUPS[0]]['lifecycle'], {'binding': doc['binding'], 'captured_control': doc['control'],
                'selection': [], 'source_qualifications': doc['qualifications']})
            self.assertEqual(groups[f.GROUPS[4]]['resources'], doc['resources'])
            inspection = groups[f.GROUPS[6]]
            self.assertEqual(inspection['source_route'], {'control_operation_id': 'prepare',
                'metadata_method': 'get_lifecycle_source_operation', 'observation_method': 'read_lifecycle_source', 'limits_required': True})
            self.assertEqual(inspection['record_methods'], ['get_revision', 'get_typed_revision'])
            self.assertEqual(inspection['artifact_method'], 'read_artifact')
            self.assertEqual(inspection['record_routes'], [{'record_id': e['record_id'], 'revision': e['revision'],
                'commit': e['commit'], 'membership': b} for e, b in zip(doc['scientific']['records'], doc['source_bindings'])])
            self.assertEqual(inspection['artifact_routes'], [{'digest': a['digest'], 'size': a['size']} for a in doc['scientific']['artifacts']])

    def test_delayed_intent_typed_fields_saved_continuation_and_settlement(self):
        """Render real negative/conditional/disputed records, unknown liabilities and later cancellation faithfully."""
        outputs = self.render(self.delayed)
        machine = self.assert_machine(self.delayed, outputs)
        groups, doc = machine['groups'], self.doc
        declaration = self.older.to_dict()['report']['declarations']
        self.assertEqual(groups[f.GROUPS[0]]['objective'], declaration['objective'])
        lifecycle = groups[f.GROUPS[0]]['lifecycle']
        self.assertEqual(lifecycle['binding'], doc['binding'])
        self.assertEqual(lifecycle['captured_control'], doc['control'])
        self.assertEqual(lifecycle['captured_control']['disposition'], 'cancelled')
        self.assertEqual(len(lifecycle['captured_control']['pending_obligations']), 5)
        self.assertEqual(machine['identities']['run']['revision'], 3)
        self.assertEqual(machine['identities']['report_revision'], 2)
        self.assertLess(machine['identities']['transitioned_at'], machine['identities']['observed_at'])
        self.assertEqual(groups[f.GROUPS[1]]['baseline'], doc['baseline'])
        self.assertEqual(groups[f.GROUPS[1]]['results'], declaration['results'])
        self.assertIsNone(groups[f.GROUPS[1]]['empty_results'])
        self.assertNotIn(b'\nNo result was established by this report.\n', outputs['report.md'])
        self.assertEqual(groups[f.GROUPS[1]]['recorded_changes'], {'unavailable': reports.unavailable(
            'Historical report comparison is unavailable for a lifecycle saved-work baseline.')})
        self.assertEqual(machine['saved_work'], declaration['saved_work'])
        self.assertEqual(machine['continuation'], declaration['continuation'])
        self.assertEqual([v['priority'] for v in machine['continuation']], [2, 7])
        self.assertEqual(groups[f.GROUPS[3]]['declared_outstanding_jobs'], declaration['outstanding_jobs'])
        self.assertIn('termination unavailable', groups[f.GROUPS[3]]['job_inventory_and_termination']['unknown_reason'])
        checks = groups[f.GROUPS[2]]
        self.assertEqual(checks['reported_completed_checks'], declaration['completed_checks'])
        self.assertEqual(checks['unresolved_issues'], declaration['unresolved_issues'])
        typed = {v['record_id']: v for v in checks['exact_typed_assessments_and_states']}
        envelopes = {v['record_id']: json.loads(v['envelope_json']) for v in doc['scientific']['records']}
        for identity in ('evidence', 'review-a', 'review-b', 'issue', 'candidate', f.CHECKPOINT, 'saved-note', 'corpus'):
            self.assertEqual(typed[identity]['saved_typed_fields'], envelopes[identity]['content'])
            for field in ('record_id', 'revision', 'kind', 'operational_status', 'scientific_disposition'):
                self.assertEqual(typed[identity][field], envelopes[identity][field])
        self.assertEqual(typed['evidence']['saved_typed_fields']['origin'], 'unverified')
        self.assertEqual(typed['evidence']['saved_typed_fields']['result'], 'NEGATIVE: property failed')
        self.assertEqual(typed['candidate']['scientific_disposition'], 'provisional')
        self.assertEqual(typed['review-b']['saved_typed_fields']['assessment']['scientific_disposition'], 'disputed')
        self.assertEqual(typed['issue']['saved_typed_fields']['severity'], 'blocking')
        self.assertIn('Saved next action', typed[f.CHECKPOINT]['saved_typed_fields']['purpose'])
        self.assertEqual(typed[f.CHECKPOINT]['saved_typed_fields']['task']['relationship'], 'task')
        self.assertEqual(typed[f.CHECKPOINT]['saved_typed_fields']['build_dependencies'][0]['relationship'], 'build_dependency')
        opaque = {v['record_id']: v for v in checks['unavailable_typed_interpretations']}
        self.assertIn('job', opaque)
        self.assertNotIn('saved_typed_fields', opaque['job'])
        self.assertNotIn('sibling', typed)
        resources = groups[f.GROUPS[4]]['resources']
        self.assertEqual(resources, doc['resources'])
        self.assertEqual(resources['operations'][-1]['request']['kind'], 'reconcile')
        self.assertGreater(resources['operations'][-1]['receipt']['committed_at'], machine['identities']['transitioned_at'])
        self.assertEqual([v['receipt']['sequence'] for v in resources['operations']][:2], [1, 3])
        self.assertIn('sibling', [a['account_id'] for a in resources['accounts']])
        sibling_usage = next(v for v in resources['reservation_usage'] if v['reservation_id'] == 'reservation_sibling-closeout')
        self.assertEqual(sibling_usage['status'], 'unresolved')
        self.assertTrue(all(d['actual_usage'] is None for d in sibling_usage['dimensions']))
        self.assertEqual(machine['continuation'][0]['required_resources']['account_id'], 'run')
        self.assertIsNone(machine['continuation'][1]['required_resources']['value'])
        for private in (b'OTHER-PROJECT-SECRET', b'PRIVATE-POLICY-SECRET'):
            self.assertNotIn(private, outputs['report.md'])
            self.assertNotIn(private, outputs['continuation.json'])
        for key in (f.GROUPS[0], f.GROUPS[5]):
            field = 'admission_and_authority' if key == f.GROUPS[0] else 'authority'
            self.assertEqual(groups[key][field], reports.unavailable(
                'Captured authority is historical; current permission and admission are unavailable.'))

    def test_authored_data_is_inert_and_round_trips(self):
        """Control/Unicode/path/link-like text cannot escape literal framing or choose output names."""
        outputs = self.render(self.delayed)
        machine = self.assert_machine(self.delayed, outputs)
        self.assertEqual(machine['groups'][f.GROUPS[0]]['objective']['text']['value'], f.NARRATIVE)
        markdown = outputs['report.md'].decode()
        active = '\n'.join(line for line in markdown.splitlines() if not line.startswith('    '))
        for hostile in ('https://invalid/', '<script>', '[[wiki]]', '../source.json', f.CHECKPOINT):
            self.assertNotIn(hostile, active)
        for control in ('\x00', '\u202e', '𝒜'):
            self.assertNotIn(control, markdown)
        for escaped in ('\\u0000', '\\u202e', '\\ud835\\udc9c', '\\n', '\\\\', '\\"'):
            self.assertIn(escaped, markdown)

    def test_purity_determinism_and_source_immutability(self):
        """Closed/removed stores and prohibited actual I/O/clock/authority hooks cannot affect bytes."""
        observation = self.delayed
        before = observation._json
        expected = self.render(observation)
        with ExitStack() as stack:
            for target in ('research_pipeline.store.RecordStore._transaction',
                'research_pipeline.store.RecordStore.read_artifact', 'research_pipeline.artifacts.ArtifactStore.verify',
                'research_pipeline.run_control_store._authorize', 'research_pipeline.resource_ledger._inspect',
                'research_pipeline.lifecycle_source_capture.datetime', 'research_pipeline.store.datetime',
                'research_pipeline.resource_ledger.datetime', 'builtins.open', 'os.open', 'os.getenv',
                'os.system', 'subprocess.Popen', 'socket.socket', 'time.time', 'pathlib.Path.open', 'os.stat'):
                stack.enter_context(patch(target, side_effect=AssertionError('impure renderer')))
            for ceiling in (f.LIMITS, replace(f.LIMITS, max_output_file_bytes=30000000,
                    source=replace(f.LIMITS.source, max_submission_bytes=1, max_work_bytes=2**63-1))):
                self.assertEqual(self.render(observation, ceiling), expected)
        self.assertEqual(observation._json, before)
        first = self.render(observation)
        first['report.md'] = b'caller mutation'
        self.assertEqual(self.render(observation), expected)

    def test_real_later_store_changes_leave_detached_bytes_unchanged(self):
        """Actual later cancellation and then removal of the store cannot refresh an earlier capture."""
        with TemporaryDirectory() as temporary:
            with RecordStore.create(Path(temporary)/'store') as store:
                observation, original, result = f.empty(store)
                expected = self.render(observation)
                controls.commit(store, controls.successor(original, result, 'cancel'), policy=None, evaluated_at=None)
                self.assertEqual(self.render(observation), expected)
        self.assertEqual(self.render(observation), expected)

    def test_limits_arguments_and_retained_content_precedence(self):
        """Invalid limits precede public type/content errors, including bypass-mutated exact instances."""
        class Integer(int):
            """An integer-valued subclass is not an ordinary allowance."""
        class String(str):
            """A retained string subclass must not be inspected as canonical input."""
        class Observation(s.LifecycleSourceObservation):
            """A source subclass cannot intercept the exact-type rendering boundary."""
        class Limits(r.LifecycleRenderLimits):
            """A limit subclass cannot add public processing behavior."""
        for invalid in (None, {}, object.__new__(Limits)):
            with self.assertRaises(r.LifecycleRenderArgumentError):
                r.render_lifecycle_report(None, limits=invalid)
        for field in ('max_work_bytes', 'max_output_file_bytes', 'max_output_total_bytes'):
            for value in (True, 1.0, Integer(1), 0, -1, 2**63, 67108865 if field != 'max_work_bytes' else None):
                bad = deepcopy(f.LIMITS)
                object.__setattr__(bad, field, value)
                with self.subTest(field=field, value=value), self.assertRaises(r.LifecycleRenderArgumentError):
                    self.render(None, bad)
            bad = deepcopy(f.LIMITS)
            object.__delattr__(bad, field)
            with self.assertRaises(r.LifecycleRenderArgumentError):
                self.render(None, bad)
        for value in (None, {}, self.delayed._json, object.__new__(Observation)):
            with self.assertRaises(r.LifecycleRenderArgumentError):
                self.render(value)
        for field in fields(sources.LIMITS):
            bad = deepcopy(f.LIMITS)
            nested = getattr(bad.source, field.name)
            if type(nested) is int:
                object.__setattr__(bad.source, field.name, True)
            else:
                scalar = next(item.name for item in fields(nested) if type(getattr(nested, item.name)) is int)
                object.__setattr__(nested, scalar, True)
            with self.subTest(source_field=field.name), self.assertRaises(r.LifecycleRenderArgumentError):
                self.render(None, bad)
        bad = deepcopy(f.LIMITS)
        object.__setattr__(bad.source.control.metadata, 'max_record_bytes', True)
        with self.assertRaises(r.LifecycleRenderArgumentError):
            self.render(None, bad)
        missing = object.__new__(s.LifecycleSourceObservation)
        with self.assertRaises(r.LifecycleRenderValidationError):
            self.render(missing)
        for value in (None, b'{}', {}, 1, String(self.delayed._json)):
            object.__setattr__(missing, '_json', value)
            with self.assertRaises(r.LifecycleRenderValidationError):
                self.render(missing)
        for call in (lambda: r.render_lifecycle_report(self.delayed),
                     lambda: r.render_lifecycle_report(self.delayed, limits=f.LIMITS, result=None)):
            with self.assertRaises(TypeError):
                call()

    def test_strict_wire_and_forged_retained_documents(self):
        """Accepted codecs reject ambiguous malformed wire forms; retained state is independently checked."""
        for data in ('{', '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":"\\ud800"}', '\ud800'):
            with self.subTest(data=repr(data)):
                with self.assertRaises(s.LifecycleSourceValidationError):
                    s.loads_observation(data, limits=sources.LIMITS)
                with self.assertRaises(r.LifecycleRenderValidationError):
                    self.render(f.forged(data))
        for data in (' ' + self.delayed._json, json.dumps(self.doc, ensure_ascii=False), '{}'):
            with self.assertRaises(r.LifecycleRenderValidationError):
                self.render(f.forged(data))
        # Consistent detached data is usable, but its route does not authenticate a store.
        self.assertEqual(self.render(f.forged(self.doc)), self.render(self.delayed))
        with patch.object(s.LifecycleSourceObservation, 'to_dict', side_effect=AssertionError('unbounded public copy')):
            self.assertEqual(self.render(f.forged(self.doc)), self.render(self.delayed))

    def test_rehashed_semantic_contradictions(self):
        """A fresh digest cannot repair contradictory original binding, history, baseline, membership or resources."""
        for mutation in ('binding', 'history', 'baseline', 'watermark', 'membership', 'resource', 'resource_counts', 'alias', 'float_alias'):
            bad = deepcopy(self.doc)
            if mutation == 'binding':
                bad['binding']['transition']['content']['request']['report']['declarations']['objective']['text']['value'] = 'Changed original intent'
                bindings.reproject(bad['binding'], 'transition')
                # The locally valid packet still contradicts captured control history.
                packet = binding.LifecycleReportBinding(bad['binding'], limits=sources.LIMITS.binding)
                bad['binding_digest'] = binding.binding_digest(packet, limits=sources.LIMITS.binding)
            elif mutation == 'history':
                bad['control']['pending_obligations'].pop()
            elif mutation == 'baseline':
                bad['baseline']['record_id'] = f.CHECKPOINT
            elif mutation == 'watermark':
                bad['scientific']['watermark']['event_id'] += 1
                f.rehash(bad['scientific'])
            elif mutation == 'membership':
                entry = next(v for v in bad['source_bindings'] if v['record_id'] == bad['binding']['transition']['record_id']
                             and v['revision'] == bad['binding']['transition']['revision'])
                entry['ordinal'] += 1
            elif mutation == 'resource':
                bad['resources']['operations'][-1]['receipt']['scientific_watermark_event_id'] += 100
            elif mutation == 'resource_counts':
                bad['resources']['accounts'] = []
            else:
                bad['baseline']['revision'] = True if mutation == 'alias' else 1.0
            with self.subTest(mutation=mutation), self.assertRaises(r.LifecycleRenderValidationError):
                self.render(f.forged(f.rehash(bad)))

    def test_implementation_failures_are_not_validation_errors(self):
        """Programming assertions, memory failures and unexpected exceptions retain their original meaning."""
        for error in (AssertionError, MemoryError, RuntimeError):
            with patch.object(s, '_normalize', side_effect=error('sentinel')):
                with self.assertRaises(error):
                    self.render(self.delayed)


    def test_emission_measurement_disagreement_is_an_invariant_failure(self):
        """Unexpected byte-size disagreement never enlarges a limit or returns truncated output."""
        with patch.object(reports, '_serialize_outputs', return_value={'report.md': b'', 'continuation.json': b''}):
            with self.assertRaises(AssertionError):
                self.render(self.empty[0])
        with patch.object(reports, '_serialize_outputs', side_effect=reports.ReportLimitError('unexpected encoding size')):
            with self.assertRaises(AssertionError):
                self.render(self.empty[0])
