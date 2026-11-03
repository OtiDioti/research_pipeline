"""Full-public-operation equality, one-unit deficits and preallocation sentinels for lifecycle rendering."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_rendering as r, lifecycle_report_source as s
from research_pipeline import lifecycle_report_binding as b, reports, run_control as c
from research_pipeline.resource_ledger import references
from research_pipeline.store import RecordStore
from tests import lifecycle_rendering_fixtures as f, lifecycle_source_fixtures as sources
from tests import run_control_fixtures as controls


def tree_counts(value):
    """Independently count repeated JSON values and container depth; keys are not nodes."""
    if type(value) not in (dict, list):
        return 1, 0
    children = value.values() if type(value) is dict else value
    counts = [tree_counts(child) for child in children]
    return 1 + sum(n for n, _ in counts), 1 + max((d for _, d in counts), default=0)


class LifecycleRenderingBoundsTests(unittest.TestCase):
    """Use genuine saved data and independent stdlib lengths, never production sizing as its own oracle."""

    @classmethod
    def setUpClass(cls):
        """Capture populated and both empty resource cases once, closing/removing stores before rendering."""
        cls.empty = []
        with TemporaryDirectory(prefix='render-bounds-') as temporary:
            root = Path(temporary)
            with RecordStore.create(root/'rich', schema_version=3) as store:
                cls.observation, _ = f.delayed(store)
            for schema in (2, 3):
                with RecordStore.create(root/str(schema), schema_version=schema) as store:
                    cls.empty.append(f.empty(store)[0])
        cls.doc = json.loads(cls.observation._json)
        cls.outputs = r.render_lifecycle_report(cls.observation, limits=f.LIMITS)
        cls.counts = f.counters(cls.doc, cls.outputs)

    def render(self, limits=f.LIMITS, observation=None):
        """Run the entire public renderer with caller-supplied source and enclosing ceilings."""
        return r.render_lifecycle_report(self.observation if observation is None else observation, limits=limits)

    def source_boundary(self, exact_source, small_source, *, sentinel=None):
        """Require full-operation equality and a one-unit deficit before an optional protected stage."""
        exact = replace(f.LIMITS, source=exact_source)
        counts = f.counters(self.doc, self.outputs, exact)
        exact = replace(exact, max_work_bytes=counts['W3'])
        self.assertEqual(self.render(exact), self.outputs)
        with ExitStack() as stack:
            if sentinel:
                stack.enter_context(patch(sentinel, side_effect=AssertionError('protected allocation reached')))
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, source=small_source))

    def test_full_render_work_and_output_equalities(self):
        """W3 is the exact full-operation minimum, and every returned/source byte participates in output budgets."""
        n = self.counts
        original_parts = reports._json_parts

        def no_output_parts(value):
            """Allow accepted source resource serialization; reject escaped continuation generation."""
            if type(value) is dict and value.get('format') == 'research_pipeline.lifecycle_report_continuation':
                raise AssertionError('output serialization')
            return original_parts(value)

        for field, threshold in (('max_work_bytes', n['W3']),
                ('max_output_file_bytes', max(n['P'], n['H'], n['J'])),
                ('max_output_total_bytes', n['P']+n['H']+n['J'])):
            exact = replace(f.LIMITS, **{field: threshold})
            self.assertEqual(self.render(exact), self.outputs)
            with patch('research_pipeline.view_plan._literal', side_effect=AssertionError('escape')), \
                    patch.object(reports, '_json_parts', side_effect=no_output_parts):
                with self.assertRaises(r.LifecycleRenderLimitError):
                    self.render(replace(exact, **{field: threshold-1}))

    def test_early_work_stages_precede_protected_allocations(self):
        """W0, W1, W2 and W3 failures stop before parsing, reconstruction, projection and encoding respectively."""
        for stage, target in (('W0', 'research_pipeline.lifecycle_report_source._parse'),
            ('W1', 'research_pipeline.lifecycle_report_source._normalize'),
            ('W2', 'research_pipeline.reports._lifecycle_projection'),
            ('W3', 'research_pipeline.reports._serialize_outputs')):
            with self.subTest(stage=stage), patch(target, side_effect=AssertionError('protected ' + stage)):
                with self.assertRaises(r.LifecycleRenderLimitError):
                    self.render(replace(f.LIMITS, max_work_bytes=self.counts[stage]-1))
                if stage != 'W3':
                    # Equality at an earlier stage reaches the next allocation; it
                    # is not misrepresented as the complete-operation minimum.
                    with self.assertRaises(AssertionError):
                        self.render(replace(f.LIMITS, max_work_bytes=self.counts[stage]))

    def test_input_source_work_and_lexical_gates(self):
        """Independent raw/canonical/node/depth ceilings gate strict parsing and nested normalization."""
        p = self.counts['P']
        nodes, depth = tree_counts(self.doc)
        nested = [json.loads(row['envelope_json']) for row in self.doc['scientific']['records']]
        self.assertGreaterEqual(nodes, max(tree_counts(e)[0] for e in nested))
        self.assertGreaterEqual(depth, max(tree_counts(e)[1] for e in nested))
        for name, threshold, sentinel in (
            ('max_input_bytes', p, 'research_pipeline.lifecycle_report_source._parse'),
            ('max_source_bytes', p, 'research_pipeline.lifecycle_report_source._normalize'),
            ('max_result_bytes', p, 'research_pipeline.lifecycle_report_source._normalize'),
            ('max_work_bytes', 72*p, 'research_pipeline.lifecycle_report_source._observation'),
            ('max_nodes', nodes, 'research_pipeline.lifecycle_report_binding.json.loads'),
            ('max_depth', depth, 'research_pipeline.lifecycle_report_binding.json.loads')):
            with self.subTest(field=name):
                exact = replace(sources.LIMITS, **{name: threshold})
                small = replace(exact, **{name: threshold-1})
                self.source_boundary(exact, small, sentinel=sentinel)
        with patch('research_pipeline.lifecycle_report_binding.json.loads', side_effect=AssertionError('parse')):
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, source=replace(sources.LIMITS, max_work_bytes=8*p-1)))

    def test_binding_limits_through_full_renderer(self):
        """The independent binding codec retains raw, canonical, node/depth and simultaneous 72B charges."""
        packet = self.doc['binding']
        size = len(f.canonical(packet))
        nodes, depth = tree_counts(packet)
        for name, threshold in (('max_input_bytes', size), ('max_packet_bytes', size),
                ('max_work_bytes', 72*size), ('max_nodes', nodes), ('max_depth', depth)):
            with self.subTest(field=name):
                exact = replace(sources.LIMITS, binding=replace(sources.LIMITS.binding, **{name: threshold}))
                small = replace(exact, binding=replace(exact.binding, **{name: threshold-1}))
                self.source_boundary(exact, small)
        small = replace(sources.LIMITS, binding=replace(sources.LIMITS.binding, max_work_bytes=64*size-1))
        with patch.object(b, '_semantics', side_effect=AssertionError('binding domain construction')):
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, source=small))

    def test_scientific_inventory_metadata_and_work_boundaries(self):
        """Full renders honor scientific inventory/fetched bytes and adjust enclosing W3 when M changes."""
        scientific = self.doc['scientific']
        entries = [json.loads(row['envelope_json']) for row in scientific['records']]
        thresholds = {'max_roots': max(len(scientific['resolutions']), len(self.doc['root_categories']['scientific'])),
            'max_records': len(entries),
            'max_references': sum(len(e['record_references']) + len(e['artifact_references']) for e in entries),
            'max_record_bytes': max(max(len(f.canonical(row)), row['fetched_bytes']) for row in scientific['records']),
            'max_metadata_bytes': len(f.canonical(scientific)) + scientific['metadata_fetched_bytes'],
            'max_artifacts': len(scientific['artifacts']), 'max_file_bytes': max(a['size'] for a in scientific['artifacts']),
            'max_total_bytes': sum(a['size'] for a in scientific['artifacts']), 'max_work_bytes': self.counts['Ws']}
        for name, threshold in thresholds.items():
            with self.subTest(field=name):
                exact = replace(sources.LIMITS, scientific=replace(sources.LIMITS.scientific, **{name: threshold}))
                small = replace(exact, scientific=replace(exact.scientific, **{name: threshold-1}))
                # Root occurrences in the scope closure can exceed snapshot's
                # distinct roots. That separate ceiling is exercised at closure.
                sentinel = 'research_pipeline.lifecycle_report_source.DetachedSnapshot' if name != 'max_roots' else None
                self.source_boundary(exact, small, sentinel=sentinel)
        exact = replace(sources.LIMITS, scientific=replace(sources.LIMITS.scientific,
            max_metadata_bytes=thresholds['max_metadata_bytes']))
        adjusted = f.counters(self.doc, self.outputs, replace(f.LIMITS, source=exact))
        self.assertLess(adjusted['W3'], self.counts['W3'])
        with self.assertRaises(r.LifecycleRenderLimitError):
            self.render(replace(f.LIMITS, source=exact, max_work_bytes=adjusted['W3']-1))

    def test_independent_fetched_bytes_and_source_representation(self):
        """Consistent synthetic fetched metadata cannot hide behind smaller retained record encodings."""
        bad = deepcopy(self.doc)
        scientific = bad['scientific']
        ceiling = max(max(len(f.canonical(row)), row['fetched_bytes']) for row in scientific['records']) + 100
        row = scientific['records'][0]
        scientific['metadata_fetched_bytes'] += ceiling - row['fetched_bytes']
        row['fetched_bytes'] = ceiling
        f.rehash(scientific)
        observation = f.forged(f.rehash(bad))
        exact = replace(f.LIMITS, source=replace(sources.LIMITS,
            scientific=replace(sources.LIMITS.scientific, max_record_bytes=ceiling)))
        outputs = self.render(exact, observation)
        self.assertEqual(set(outputs), {'report.md', 'continuation.json'})
        with patch.object(s, 'DetachedSnapshot', side_effect=AssertionError('snapshot')):
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(exact, source=replace(exact.source,
                    scientific=replace(exact.source.scientific, max_record_bytes=ceiling-1))), observation)

    def test_resource_request_derived_bounds(self):
        """Every consumed resource allowance permits equality and rejects a deficit before replay."""
        value = self.doc['resources']
        size = len(f.canonical(value))
        rows = [row for key in ('operations', 'accounts', 'allocations', 'reservations', 'reservation_usage',
            'breaches', 'balances') for row in value[key]]
        thresholds = {'max_accounts': sum(v['request']['kind'] in ('create_account', 'allocate') for v in value['operations']),
            'max_operations': len(value['operations']), 'max_rows': len(rows),
            'max_references': sum(len(references(v['request'])) for v in value['operations']),
            'max_record_bytes': max(len(f.canonical(row)) for row in rows), 'max_metadata_bytes': size,
            'max_result_bytes': size, 'max_work_bytes': self.counts['Wr']}
        for name, threshold in thresholds.items():
            with self.subTest(field=name):
                exact = replace(sources.LIMITS, resources=replace(sources.LIMITS.resources, **{name: threshold}))
                small = replace(exact, resources=replace(exact.resources, **{name: threshold-1}))
                self.source_boundary(exact, small, sentinel='research_pipeline.reports._validate_resources')
        bad = deepcopy(self.doc)
        bad['resources']['accounts'] = []
        # Even a duplicate operation cannot lower the up-front replay reservation.
        bad['resources']['operations'].append(deepcopy(bad['resources']['operations'][0]))
        f.rehash(bad)
        work = f.counters(bad, self.outputs)['Wr']
        with patch.object(s, '_normalize', side_effect=AssertionError('resource reconstruction')):
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, source=replace(sources.LIMITS,
                    resources=replace(sources.LIMITS.resources, max_work_bytes=work-1))), f.forged(bad))

    def test_empty_resource_fixed_overhead_both_schemas(self):
        """Schema-2 unavailable and empty schema-3 resources both reserve replay and full projection overhead."""
        for observation in self.empty:
            doc = json.loads(observation._json)
            outputs = self.render(observation=observation)
            counts = f.counters(doc, outputs)
            self.assertEqual(counts['Wr'], 256*(len(f.canonical(doc['resources']))+1) + 262144)
            exact = replace(f.LIMITS, max_work_bytes=counts['W3'], source=replace(sources.LIMITS,
                resources=replace(sources.LIMITS.resources, max_work_bytes=counts['Wr'])))
            self.assertEqual(self.render(exact, observation), outputs)
            for small in (replace(exact, max_work_bytes=counts['W3']-1),
                replace(exact, source=replace(exact.source,
                    resources=replace(exact.source.resources, max_work_bytes=counts['Wr']-1)))):
                with self.assertRaises(r.LifecycleRenderLimitError):
                    self.render(small, observation)

    def test_control_history_and_outer_artifact_boundaries(self):
        """All consumed control/history and outer evidence ceilings apply independently through rendering."""
        control = self.doc['control']
        envelopes = [v for pair in zip((t['envelope'] for t in control['transitions']), control['pending_obligations']) for v in pair]
        for name, threshold in (('max_result_bytes', len(f.canonical(control))),
                ('max_transitions', len(control['transitions'])), ('max_pending_reports', len(control['pending_obligations']))):
            exact = replace(sources.LIMITS, control=replace(sources.LIMITS.control, **{name: threshold}))
            small = replace(exact, control=replace(exact.control, **{name: threshold-1}))
            self.source_boundary(exact, small)
        for name, threshold in (('max_metadata_bytes', len(f.canonical(control))),
                ('max_record_bytes', max(len(f.canonical(e)) for e in envelopes)),
                ('max_records', len(envelopes)), ('max_history_revisions', len(control['transitions'])),
                ('max_references', sum(len(e['record_references'])+len(e['artifact_references']) for e in envelopes))):
            exact = replace(sources.LIMITS, control=replace(sources.LIMITS.control,
                metadata=replace(sources.LIMITS.control.metadata, **{name: threshold})))
            small = replace(exact, control=replace(exact.control, metadata=replace(exact.control.metadata, **{name: threshold-1})))
            self.source_boundary(exact, small)
        artifacts = self.doc['verified_artifacts']
        for name, threshold in (('max_artifacts', len(artifacts)), ('max_artifact_bytes', max(a['size'] for a in artifacts)),
                ('max_artifact_total_bytes', sum(a['size'] for a in artifacts))):
            exact = replace(sources.LIMITS, **{name: threshold})
            self.source_boundary(exact, replace(exact, **{name: threshold-1}))

    def test_source_is_largest_and_complete_bundle_includes_it(self):
        """The source alone can violate per-file and complete-bundle limits even when both returned files fit."""
        observation = self.empty[0]
        outputs = self.render(observation=observation)
        p = len(observation._json)
        h, j = (len(outputs[k]) for k in ('report.md', 'continuation.json'))
        self.assertGreater(p, max(h, j))
        self.assertEqual(self.render(replace(f.LIMITS, max_output_file_bytes=p,
            max_output_total_bytes=p+h+j), observation), outputs)
        for small in (replace(f.LIMITS, max_output_file_bytes=p-1),
                      replace(f.LIMITS, max_output_total_bytes=p+h+j-1)):
            with patch.object(reports, '_serialize_outputs', side_effect=AssertionError('output construction')):
                with self.assertRaises(r.LifecycleRenderLimitError):
                    self.render(small, observation)

    def test_all_lifecycle_closures_are_bounded_and_projection_repeats_roots(self):
        """Source and presentation traversal always pass bounds; repeated categories preserve their full order."""
        with patch.object(reports, '_closure', wraps=reports._closure) as closure:
            self.assertEqual(self.render(), self.outputs)
        self.assertEqual(len(closure.call_args_list), 2)
        for call in closure.call_args_list:
            self.assertIsNotNone(call.kwargs['bounds'])
        presentation = closure.call_args_list[-1]
        roots = [ref for category in ('scientific', 'dossier', 'saved_baseline') for ref in self.doc['root_categories'][category]]
        self.assertEqual(presentation.args[0], roots)
        self.assertEqual(presentation.kwargs['bounds'][0], len(roots))
        self.assertGreater(len(roots), len({reports.pin(ref) for ref in roots}))
        envelopes = reports._envelopes(self.doc['scientific'])
        reference_count = sum(len(e.record_references)+len(e.artifact_references) for e in envelopes.values())
        with patch.object(reports, 'pin', side_effect=AssertionError('traversal allocation')):
            for bounds in ((len(roots)-1, len(envelopes), reference_count),
                           (len(roots), len(envelopes)-1, reference_count),
                           (len(roots), len(envelopes), reference_count-1)):
                with self.assertRaises(reports.ReportLimitError):
                    reports._closure(roots, envelopes, bounds=bounds)

    def test_original_output_allowances_are_independent_restrictions(self):
        """Genuine newly captured original declarations restrict output even under large caller allowances."""
        serial = 0
        with TemporaryDirectory(prefix='render-original-limits-') as temporary:
            def capture(field, allowance):
                """Commit a real initial request with an explicit original output restriction, then close its store."""
                nonlocal serial
                serial += 1
                with RecordStore.create(Path(temporary)/str(serial)) as store:
                    original = controls.populate(store).to_dict()
                    original['report']['limits'][field] = allowance
                    controls.commit(store, c.RunControlRequest(original))
                    sources.commit(store)
                    return store.read_lifecycle_source('prepare', limits=sources.LIMITS)

            for field in ('max_output_file_bytes', 'max_output_total_bytes'):
                baseline = self.empty[0]
                output = self.render(observation=baseline)
                sizes = [len(baseline._json), *(len(v) for v in output.values())]
                threshold = max(sizes) if field == 'max_output_file_bytes' else sum(sizes)
                # Changing the original allowance changes its retained decimal
                # representation. Re-capture until its independently observed
                # complete size is exact; no expected hashes are regenerated.
                for _ in range(3):
                    observation = capture(field, threshold)
                    output = self.render(observation=observation)
                    sizes = [len(observation._json), *(len(v) for v in output.values())]
                    required = max(sizes) if field == 'max_output_file_bytes' else sum(sizes)
                    if required == threshold:
                        break
                    threshold = required
                self.assertEqual(required, threshold)
                retained = json.loads(observation._json)['binding']['transition']['content']['request']['report']['limits']
                self.assertEqual(retained[field], required)
                small = capture(field, threshold-1)
                with patch.object(reports, '_serialize_outputs', side_effect=AssertionError('escaped output')):
                    with self.assertRaises(r.LifecycleRenderLimitError):
                        self.render(observation=small)

    def test_reservation_inputs_are_checked_before_domain_construction(self):
        """Malformed M/A/O containers and scalar aliases fail safely without unchecked indexing or coercion."""
        for mutation in ('missing_binding', 'binding_list', 'missing_metadata', 'bool_metadata', 'float_metadata',
                         'negative_metadata', 'resources_list', 'operations_dict', 'request_list', 'kind_bool'):
            bad = deepcopy(self.doc)
            if mutation == 'missing_binding':
                del bad['binding']
            elif mutation == 'binding_list':
                bad['binding'] = []
            elif mutation.endswith('metadata'):
                limits = bad['binding']['transition']['content']['request']['report']['limits']['snapshot']
                if mutation == 'missing_metadata':
                    del limits['max_metadata_bytes']
                else:
                    limits['max_metadata_bytes'] = {'bool_metadata': True, 'float_metadata': 1.0, 'negative_metadata': -1}[mutation]
            elif mutation == 'resources_list':
                bad['resources'] = []
            elif mutation == 'operations_dict':
                bad['resources']['operations'] = {}
            elif mutation == 'request_list':
                bad['resources']['operations'][0]['request'] = []
            else:
                bad['resources']['operations'][0]['request']['kind'] = True
            with self.subTest(mutation=mutation), patch.object(s, '_normalize', side_effect=AssertionError('domain construction')):
                with self.assertRaises(r.LifecycleRenderValidationError):
                    self.render(observation=f.forged(bad))

    def test_noncanonical_unicode_raw_and_canonical_sizes_are_independent(self):
        """Preflight separately counts UTF-8 R and escaped ASCII P before rejecting noncanonical retention."""
        raw = json.dumps(self.doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        raw_size, canonical_size = len(raw.encode('utf-8')), len(f.canonical(self.doc))
        self.assertLess(raw_size, canonical_size)
        observation = f.forged(raw)
        with patch.object(s, '_parse', side_effect=AssertionError('parser')):
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, max_work_bytes=4096+8*raw_size-1), observation)
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, source=replace(sources.LIMITS, max_input_bytes=raw_size-1)), observation)
        with patch.object(s, '_normalize', side_effect=AssertionError('canonical reconstruction')):
            with self.assertRaises(r.LifecycleRenderLimitError):
                self.render(replace(f.LIMITS, source=replace(sources.LIMITS,
                    max_input_bytes=raw_size, max_source_bytes=canonical_size-1)), observation)
        with self.assertRaisesRegex(r.LifecycleRenderValidationError, 'noncanonical'):
            self.render(replace(f.LIMITS, source=replace(sources.LIMITS, max_input_bytes=raw_size)), observation)
