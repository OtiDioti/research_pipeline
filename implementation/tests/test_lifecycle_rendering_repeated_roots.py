"""Persisted repeated declarations retain distinct-pin limits and bounded occurrence work."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_rendering as r, lifecycle_report_source as s
from research_pipeline import reports, run_control as c
from research_pipeline.store import RecordStore
from tests import lifecycle_rendering_fixtures as f, lifecycle_source_fixtures as sources
from tests import run_control_fixtures as controls
from tests.report_fixtures import ref, text
from tests.test_store import request as submission
from tests.test_typed_store import claim, context, envelope


def root_limits(count):
    """Change only the caller's distinct scientific pin allowance, retaining every other ceiling."""
    return replace(sources.LIMITS, scientific=replace(sources.LIMITS.scientific, max_roots=count))


def prepare_repeated(store, original_roots=100):
    """Commit 100 attributed results sharing a real typed claim and derive expected categories.

    Return the original request, persisted binding inspection, independently
    assembled categories and first-occurrence pins before source capture.
    """
    original = controls.populate(store).to_dict()
    store.submit_typed(submission('repeated-claim', [envelope('result-context', context()),
        envelope('result-claim', claim('result-context'))]))
    original['report']['limits']['snapshot']['max_roots'] = original_roots
    original['report']['declarations']['results'] = [
        {'statement': text('Attributed result declaration ' + str(index)),
         'supporting_references': [ref('result-claim', 'claim')]}
        for index in range(100)]
    controls.commit(store, c.RunControlRequest(original))
    inspection = store.inspect_lifecycle_source('prepare', limits=sources.LIMITS).to_dict(limits=sources.LIMITS)
    control = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
    preparation = original['preparation']
    scientific = [preparation['project'], ref('run', 'run', 'run')]
    if 'record_id' in preparation['context']:
        scientific.append(preparation['context'])
    scientific.extend(original['report']['selection'])
    scientific.extend(result['supporting_references'][0] for result in original['report']['declarations']['results'])
    categories = {'scientific': scientific,
        'dossier': [preparation['initial_corpus'], preparation['current_corpus']],
        'saved_baseline': [], 'control_history': [control['head']], 'resource_evidence': []}
    pins = list(dict.fromkeys((ref['record_id'], ref['revision'])
        for references in categories.values() for ref in references))
    return original, inspection, categories, pins


class LifecycleRepeatedRootTests(unittest.TestCase):
    """Exercise genuine schema-2/3 sources with more occurrences than their immutable root ceiling."""

    @classmethod
    def setUpClass(cls):
        """Persist and read both schemas at caller/original 100; close stores before codec/render tests."""
        cls.cases = []
        with TemporaryDirectory(prefix='repeated-roots-') as temporary:
            for schema in (2, 3):
                with RecordStore.create(Path(temporary)/str(schema), schema_version=schema) as store:
                    original, inspection, categories, pins = prepare_repeated(store)
                    committed = store.commit_lifecycle_source('prepare',
                        expected_binding_digest=inspection['binding_digest'], limits=root_limits(100))
                    observation = store.read_lifecycle_source('prepare', limits=root_limits(100))
                    cls.cases.append((schema, original, inspection, categories, pins,
                        committed.to_dict(limits=sources.LIMITS), observation))

    def assert_round_trip(self, observation, limits):
        """Verify every detached constructor/codec and the full renderer preserve canonical bytes."""
        wire = observation._json
        document = json.loads(wire)
        self.assertEqual(wire, f.canonical(document))
        self.assertEqual(observation.to_dict(limits=limits), document)
        self.assertEqual(s.dumps_observation(observation, limits=limits), wire)
        for rebuilt in (s.LifecycleSourceObservation(document, limits=limits),
                s.LifecycleSourceObservation.from_dict(document, limits=limits),
                s.loads_observation(wire, limits=limits),
                s.loads_observation(wire.encode('ascii'), limits=limits)):
            self.assertEqual(s.dumps_observation(rebuilt, limits=limits), wire)
        return r.render_lifecycle_report(observation, limits=replace(f.LIMITS, source=limits))

    def assert_capture_denied(self, store, inspection, limits):
        """Require root rejection before snapshot capture with durable pending intent and no source result."""
        before = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
        self.assertEqual(len(before['pending_obligations']), 1)
        with patch.object(store, '_capture_snapshot', side_effect=AssertionError('snapshot capture')):
            with self.assertRaises(s.LifecycleSourceLimitError):
                store.commit_lifecycle_source('prepare',
                    expected_binding_digest=inspection['binding_digest'], limits=limits)
        self.assertIsNone(store.get_lifecycle_source_operation('prepare', limits=sources.LIMITS))
        self.assertEqual(store.inspect_run_control('run', limits=controls.LIMITS).to_dict(), before)
        after = store.inspect_lifecycle_source('prepare', limits=sources.LIMITS).to_dict(limits=sources.LIMITS)
        self.assertEqual(after, inspection)
        self.assertEqual(after['state'], 'durable_intent')
        self.assertIsNone(after['result'])

    def test_persisted_repetitions_and_detached_round_trips(self):
        """Original/caller 100 permits repeated results; exact D and larger callers yield identical outputs."""
        for schema, original, inspection, categories, pins, committed, observation in self.cases:
            with self.subTest(schema=schema):
                doc = json.loads(observation._json)
                self.assertGreater(len(categories['scientific']), 100)
                self.assertLess(len(pins), 100)
                self.assertEqual(doc['root_categories'], categories)
                self.assertEqual(doc['scientific']['resolutions'],
                    [{'record_id': identity, 'revision': revision} for identity, revision in pins])
                self.assertEqual(doc['scientific']['limits']['max_roots'], 100)
                self.assertEqual(doc['binding']['transition']['content']['request'], original)
                self.assertEqual(doc['binding']['obligation'], inspection['obligation'])
                self.assertEqual(doc['binding_digest'], inspection['binding_digest'])
                self.assertEqual(committed['source_artifact'], {
                    'digest': hashlib.sha256(observation._json.encode('ascii')).hexdigest(),
                    'size': len(observation._json)})
                outputs = self.assert_round_trip(observation, root_limits(100))
                self.assertEqual(self.assert_round_trip(observation, root_limits(len(pins))), outputs)
                self.assertEqual(self.assert_round_trip(observation, root_limits(1000)), outputs)
                self.assertEqual(r.render_lifecycle_report(observation, limits=f.LIMITS), outputs)
                self.assertIs(type(outputs), dict)
                self.assertEqual(set(outputs), {'report.md', 'continuation.json'})
                self.assertTrue(all(type(value) is bytes for value in outputs.values()))
                machine = json.loads(outputs['continuation.json'])
                self.assertEqual(outputs['continuation.json'], (f.canonical(machine)+'\n').encode('ascii'))
                self.assertEqual(set(machine), {'format', 'version', 'identities', 'saved_work',
                    'groups', 'continuation', 'ordinary_work_allowed', 'recheck_required'})
                self.assertEqual(machine['format'], 'research_pipeline.lifecycle_report_continuation')
                self.assertIs(type(machine['version']), int)
                self.assertEqual(machine['version'], 1)
                self.assertIs(machine['ordinary_work_allowed'], False)
                self.assertIs(machine['recheck_required'], True)
                self.assertEqual(set(machine['groups']), set(f.GROUPS))
                self.assertEqual(machine['groups'][f.GROUPS[1]]['results'], original['report']['declarations']['results'])
                self.assertEqual(machine['saved_work'], original['report']['declarations']['saved_work'])
                self.assertEqual(machine['continuation'], original['report']['declarations']['continuation'])
                obligation = inspection['obligation']['content']
                self.assertEqual(machine['identities'], {
                    'control_operation_id': 'prepare', 'report_operation_id': obligation['report_operation_id'],
                    'report_revision': obligation['report_revision'], 'run': ref('run', 'run', 'run'),
                    'source_event': ref(obligation['report_source_id'], 'event', 'lifecycle_report_source'),
                    'snapshot_id': doc['snapshot_id'], 'scientific_snapshot_id': doc['scientific']['snapshot_id'],
                    'binding_digest': inspection['binding_digest'], 'transitioned_at': original['transitioned_at'],
                    'observed_at': doc['observed_at'], 'scientific_watermark': doc['scientific']['watermark'],
                    'resource_sequence': doc['resources'].get('resource_sequence')})
                markdown = outputs['report.md'].decode('utf-8')
                literals = [json.loads(line[4:]) for line in markdown.splitlines() if line.startswith('    ')]
                self.assertEqual(literals, [machine['identities']] + [machine['groups'][key] for key in f.GROUPS])
                self.assertEqual(markdown.count('\n## '), 7)

    def test_caller_distinct_boundary_capture_read_and_reconstruction(self):
        """D succeeds throughout; D-1 rejects fresh capture and stored/offline reconstruction before allocation."""
        with TemporaryDirectory(prefix='repeated-caller-') as temporary:
            for schema in (2, 3):
                with self.subTest(schema=schema):
                    with RecordStore.create(Path(temporary)/str(schema), schema_version=schema) as store:
                        _, inspection, _, pins = prepare_repeated(store)
                        exact, small = root_limits(len(pins)), root_limits(len(pins)-1)
                        self.assert_capture_denied(store, inspection, small)
                        store.commit_lifecycle_source('prepare',
                            expected_binding_digest=inspection['binding_digest'], limits=exact)
                        observation = store.read_lifecycle_source('prepare', limits=exact)
                        with patch.object(s, 'DetachedSnapshot', side_effect=AssertionError('reconstruction')):
                            with self.assertRaises(s.LifecycleSourceLimitError):
                                store.read_lifecycle_source('prepare', limits=small)
                    outputs = self.assert_round_trip(observation, exact)
                    self.assertEqual(r.render_lifecycle_report(observation, limits=f.LIMITS), outputs)
                    document = json.loads(observation._json)
                    with patch.object(s, 'DetachedSnapshot', side_effect=AssertionError('reconstruction')):
                        for operation in (
                                lambda: s.LifecycleSourceObservation(document, limits=small),
                                lambda: s.LifecycleSourceObservation.from_dict(document, limits=small),
                                lambda: s.loads_observation(observation._json, limits=small),
                                lambda: observation.to_dict(limits=small),
                                lambda: s.dumps_observation(observation, limits=small)):
                            with self.assertRaises(s.LifecycleSourceLimitError):
                                operation()
                        with self.assertRaises(r.LifecycleRenderLimitError):
                            r.render_lifecycle_report(observation, limits=replace(f.LIMITS, source=small))

    def test_immutable_original_distinct_boundary(self):
        """Separately committed original D/D-1 requests enforce distinct pins even with generous callers."""
        with TemporaryDirectory(prefix='repeated-original-') as temporary:
            for schema, _, _, _, expected_pins, _, _ in self.cases:
                for allowance in (len(expected_pins), len(expected_pins)-1):
                    with self.subTest(schema=schema, original_roots=allowance):
                        with RecordStore.create(Path(temporary)/f'{schema}-{allowance}', schema_version=schema) as store:
                            _, inspection, categories, pins = prepare_repeated(store, allowance)
                            self.assertEqual(pins, expected_pins)
                            self.assertGreater(len(categories['scientific']), allowance)
                            if allowance < len(pins):
                                self.assert_capture_denied(store, inspection, sources.LIMITS)
                                continue
                            sources.commit(store)
                            observation = store.read_lifecycle_source('prepare', limits=sources.LIMITS)
                        self.assert_round_trip(observation, sources.LIMITS)

    def test_occurrence_closure_and_complete_representation_budgets(self):
        """Both walks retain repeated entries, and exact/one-short closure, W3 and output budgets remain effective."""
        for schema, _, _, categories, pins, _, observation in self.cases:
            with self.subTest(schema=schema):
                limits = replace(f.LIMITS, source=root_limits(len(pins)))
                with patch.object(reports, '_closure', wraps=reports._closure) as closure:
                    outputs = r.render_lifecycle_report(observation, limits=limits)
                expected_roots = [categories['scientific'],
                    [ref for name in ('scientific', 'dossier', 'saved_baseline') for ref in categories[name]]]
                self.assertEqual(len(closure.call_args_list), 2)
                for call, roots in zip(closure.call_args_list, expected_roots):
                    self.assertEqual(call.args[0], roots)
                    self.assertEqual(call.kwargs['bounds'][0], len(roots))
                    self.assertGreater(len(roots), len(pins))
                    envelopes = call.args[1]
                    references = sum(len(e.record_references)+len(e.artifact_references) for e in envelopes.values())
                    bounds = (len(roots), len(envelopes), references)
                    self.assertEqual(reports._closure(roots, envelopes, bounds=bounds),
                        reports._closure(roots, envelopes, bounds=call.kwargs['bounds']))
                    for index in range(3):
                        small = tuple(value - (position == index) for position, value in enumerate(bounds))
                        with patch.object(reports, 'pin', side_effect=AssertionError('pending-pin allocation')):
                            with self.assertRaises(reports.ReportLimitError):
                                reports._closure(roots, envelopes, bounds=small)
                counts = f.counters(json.loads(observation._json), outputs, limits)
                for field, threshold in (('max_work_bytes', counts['W3']),
                        ('max_output_file_bytes', max(counts['P'], counts['H'], counts['J'])),
                        ('max_output_total_bytes', counts['P']+counts['H']+counts['J'])):
                    exact = replace(limits, **{field: threshold})
                    self.assertEqual(r.render_lifecycle_report(observation, limits=exact), outputs)
                    with patch.object(reports, '_serialize_outputs', side_effect=AssertionError('output serialization')):
                        with self.assertRaises(r.LifecycleRenderLimitError):
                            r.render_lifecycle_report(observation, limits=replace(exact, **{field: threshold-1}))
