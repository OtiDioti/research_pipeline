"""Independent source-stage equality/overflow boundaries and protected fresh ownership paths."""

from dataclasses import replace
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_source as s, lifecycle_source_capture as capture
from research_pipeline import run_control as c, reports
from research_pipeline.domain import ArtifactReference, RecordEnvelope, Submission
from research_pipeline.resource_ledger import references
from research_pipeline.snapshot import SnapshotLimits
from research_pipeline.store import RecordStore, SubmissionConflictError
from tests import lifecycle_source_fixtures as f, run_control_fixtures as controls
from tests.test_report_resources import funded
from tests.test_store import record, request as submission


class SourceIndependentBoundsTests(unittest.TestCase):
    """Use real populated source facts to exercise sufficient equality and exactly one-unit overflow."""

    @classmethod
    def setUpClass(cls):
        """Capture scientific bytes and complete relevant resource evidence for meaningful nonzero ceilings."""
        with TemporaryDirectory(prefix='source-bounds-') as temporary:
            with RecordStore.create(Path(temporary) / 'store', schema_version=3) as store:
                original, result = f.populate(store)
                funded(store, private=True, sibling=True)
                artifact = store.put_artifact(b'Bounded scientific evidence.\n')
                store.submit(submission('evidence', [record('selected', artifact_references=[artifact])]))
                request = controls.successor(original, result, 'checkpoint').to_dict()
                request['report']['selection'] = [c.reference('selected', 1, 'report_selection', 'research_context')]
                request['report']['declarations']['objective']['text']['value'] = '𝒜 α "\\\n\t\x00'
                controls.commit(store, c.RunControlRequest(request), policy=None, evaluated_at=None)
                f.commit(store, 'checkpoint')
                cls.doc = store.read_lifecycle_source('checkpoint', limits=f.LIMITS).to_dict(limits=f.LIMITS)

    def test_all_scientific_inventory_and_representation_ceilings(self):
        """Every scientific scalar has a genuine successful equality and a smaller failed value."""
        scientific = self.doc['scientific']
        entries = [capture._strict_json(r['envelope_json'], maximum_depth=65) for r in scientific['records']]
        thresholds = {'max_roots': len(scientific['resolutions']), 'max_records': len(entries),
            'max_references': sum(len(e['record_references']) + len(e['artifact_references']) for e in entries),
            'max_record_bytes': max(max(len(c.canonical(r)), r['fetched_bytes']) for r in scientific['records']),
            'max_metadata_bytes': len(c.canonical(scientific)) + scientific['metadata_fetched_bytes'],
            'max_artifacts': len(scientific['artifacts']),
            'max_file_bytes': max(a['size'] for a in scientific['artifacts']),
            'max_total_bytes': sum(a['size'] for a in scientific['artifacts'])}
        for field, threshold in thresholds.items():
            with self.subTest(field=field):
                exact = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, **{field: threshold}))
                self.assertEqual(s.LifecycleSourceObservation(self.doc, limits=exact).to_dict(limits=exact), self.doc)
                small = replace(exact, scientific=replace(exact.scientific, **{field: threshold-1}))
                with patch.object(s.DetachedSnapshot, '__init__', side_effect=AssertionError('protected snapshot reconstruction')):
                    with self.assertRaises(s.LifecycleSourceLimitError):
                        s.LifecycleSourceObservation(self.doc, limits=small)

    def test_all_resource_projection_ceilings(self):
        """Actual saved project projections meet independent row/reference/byte/work equality boundaries."""
        value = self.doc['resources']
        size = len(c.canonical(value))
        rows = [row for key in ('operations', 'accounts', 'allocations', 'reservations',
                'reservation_usage', 'breaches', 'balances') for row in value[key]]
        thresholds = {'max_accounts': len(value['accounts']), 'max_operations': len(value['operations']),
            'max_rows': len(rows), 'max_references': sum(len(references(item['request'])) for item in value['operations']),
            'max_record_bytes': max(len(c.canonical(row)) for row in rows),
            'max_metadata_bytes': size, 'max_result_bytes': size,
            'max_work_bytes': 256*(size+1)+262144*(len(value['accounts'])+1)*(len(value['operations'])+1)}
        for field, threshold in thresholds.items():
            with self.subTest(field=field):
                exact = replace(f.LIMITS, resources=replace(f.LIMITS.resources, **{field: threshold}))
                s.LifecycleSourceObservation(self.doc, limits=exact)
                small = replace(exact, resources=replace(exact.resources, **{field: threshold-1}))
                with patch('research_pipeline.reports._validate_resources', side_effect=AssertionError('protected ledger replay')):
                    with self.assertRaises(s.LifecycleSourceLimitError):
                        s.LifecycleSourceObservation(self.doc, limits=small)

    def test_outer_artifact_source_and_utf8_input_boundaries(self):
        """Outer inventory and complete source/raw framing boundaries count supplementary Unicode correctly."""
        text = c.canonical(self.doc)
        evidence = self.doc['verified_artifacts']
        for field, threshold in {'max_artifacts': len(evidence), 'max_artifact_bytes': max(a['size'] for a in evidence),
                'max_artifact_total_bytes': sum(a['size'] for a in evidence), 'max_source_bytes': len(text)}.items():
            exact = replace(f.LIMITS, **{field: threshold})
            with self.subTest(field=field):
                s.LifecycleSourceObservation(self.doc, limits=exact)
                with self.assertRaises(s.LifecycleSourceLimitError):
                    s.LifecycleSourceObservation(self.doc, limits=replace(exact, **{field: threshold-1}))
        import json
        raw = json.dumps(self.doc, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        r = len(raw.encode('utf-8'))
        exact = replace(f.LIMITS, max_input_bytes=r, max_work_bytes=8*r+64*len(text))
        self.assertEqual(s.loads_observation(raw, limits=exact)._json, text)
        with patch('research_pipeline.lifecycle_report_binding.json.loads', side_effect=AssertionError('protected raw decode')):
            with self.assertRaises(s.LifecycleSourceLimitError):
                s.loads_observation(raw, limits=replace(exact, max_input_bytes=r-1))
            with self.assertRaises(s.LifecycleSourceLimitError):
                s.loads_observation(raw, limits=replace(exact, max_work_bytes=8*r-1))

    def test_shared_resource_preflight_work_and_scientific_work_sentinels(self):
        """Real SQL raw-byte charges and fixed empty replay overhead reject before shared algorithms."""
        with TemporaryDirectory() as temporary, RecordStore.create(Path(temporary) / 'store', schema_version=3) as store:
            f.populate(store)
            original = self.doc['binding']['transition']['content']['request']['report']['limits']['resources']
            budget = capture._ResourceBudget(f.LIMITS, original)
            budget.preflight(store._connection)
            wr = 256*(budget.bytes+1)+262144
            exact = replace(f.LIMITS, resources=replace(f.LIMITS.resources, max_work_bytes=wr))
            capture._ResourceBudget(exact, original).preflight(store._connection)
            small = replace(exact, resources=replace(exact.resources, max_work_bytes=wr-1))
            with patch('research_pipeline.resource_ledger.validate_ledger', side_effect=AssertionError('protected complete ledger replay')):
                with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'resource replay workspace'):
                    capture._resources(store._connection, 3, self.doc['binding'], small)
            for field, threshold in (('max_rows', budget.rows), ('max_metadata_bytes', budget.bytes)):
                exact = replace(f.LIMITS, resources=replace(f.LIMITS.resources, **{field: threshold}))
                capture._ResourceBudget(exact, original).preflight(store._connection)
                small = replace(exact, resources=replace(exact.resources, **{field: threshold-1}))
                with self.assertRaises(s.LifecycleSourceLimitError):
                    capture._ResourceBudget(small, original).preflight(store._connection)
        original = SnapshotLimits(**self.doc['scientific']['limits'])
        charge = 64*original.max_metadata_bytes+4096
        exact = replace(f.LIMITS, scientific=replace(f.LIMITS.scientific, max_work_bytes=charge))
        effective = capture._ScientificBudget(exact).effective(original)
        self.assertEqual(effective.to_dict(), {name: number if name == 'max_files' else
            min(number, getattr(exact.scientific, name)) for name, number in original.to_dict().items()})
        with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'scientific workspace'):
            capture._ScientificBudget(replace(exact, scientific=replace(exact.scientific, max_work_bytes=charge-1))).effective(original)

    def test_submission_and_source_read_framing_exact_boundaries(self):
        """Actual source event/submission and retained-read charges permit equality and reject a one-byte deficit."""
        data = c.canonical(self.doc).encode('ascii')
        artifact = ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))
        work = capture._Workspace(f.LIMITS)
        event, size = capture._event(self.doc, artifact, f.LIMITS, work)
        _, canonical, _ = capture._submission(event, size, 'checkpoint', f.LIMITS, work)
        exact = replace(f.LIMITS, max_submission_bytes=len(canonical))
        capture._submission(event, size, 'checkpoint', exact, capture._Workspace(exact))
        with patch.object(capture, 'Submission', side_effect=AssertionError('protected submission constructor')):
            with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'source submission framing'):
                small = replace(exact, max_submission_bytes=len(canonical)-1)
                capture._submission(event, size, 'checkpoint', small, capture._Workspace(small))
        charge = 1024*1024+74*len(data)
        exact = replace(f.LIMITS, max_work_bytes=charge)
        retained = capture._Workspace(exact)
        capture._read_work(exact, retained, retained_size=len(data))
        self.assertEqual(retained.used, charge)
        with self.assertRaises(s.LifecycleSourceLimitError):
            retained.reserve_charge(1, 'additional retained wrapper')
        self.assertEqual(retained.used, charge)
        with self.assertRaisesRegex(s.LifecycleSourceLimitError, 'artifact read workspace'):
            small = replace(exact, max_work_bytes=charge-1)
            capture._read_work(small, capture._Workspace(small), retained_size=len(data))


class SourceOwnershipTests(unittest.TestCase):
    """Fresh public writers cannot manufacture source ownership; exact historical retries remain first."""

    def setUp(self):
        """Create a controlled run and its reserved source/report/output identities."""
        temporary = TemporaryDirectory(prefix='source-ownership-')
        self.addCleanup(temporary.cleanup)
        self.store = RecordStore.create(Path(temporary.name) / 'store')
        self.addCleanup(self.store.close)
        self.original, self.result = f.populate(self.store)

    def test_fresh_generic_typed_formats_operations_and_reserved_members(self):
        """Every new format, S/O and reserved E/M/X refuses ordinary submission ownership."""
        s_id = c._identity('run-control-source-', 'prepare')
        o_id = c.report_operation_id('prepare')
        e_id = reports.source_id(o_id)
        x_id = c._identity('run-control-output-', 'prepare')
        m_id = reports.manifest_id('run')
        for operation in (s_id, o_id):
            with self.subTest(operation=operation), self.assertRaises(c.RunControlStateError):
                self.store.submit(submission(operation, [record('attempted')]))
        for identity in (e_id, x_id, m_id):
            with self.subTest(identity=identity), self.assertRaises(c.RunControlStateError):
                self.store.submit(submission('attack', [record(identity, kind='event')]))
        for format in s.FORMATS:
            submitted = submission('attack', [record('attempted', kind='event', content={'format': format})])
            with self.subTest(format=format), self.assertRaises(c.RunControlStateError):
                self.store.submit(submitted)
            with self.assertRaises(ValueError):
                self.store.submit_typed(submitted)
        self.assertIsNone(self.store.get_submission(s_id))
        self.assertIsNone(self.store.head(e_id))

    def test_occupied_source_id_conflicts_but_exact_historical_submission_reconciles(self):
        """A real pre-guard generic submission under S is conflict to source APIs and still retries historically."""
        sid = c._identity('run-control-source-', 'other')
        submitted = submission(sid, [record('historical')])
        canonical = c.canonical({'fingerprint_version': 1, 'submission': submitted.to_dict()})
        with self.store._transaction(write=True) as connection:
            self.store._check_batch(connection, submitted)
            receipt = self.store._insert_submission(connection, submitted, canonical, hashlib.sha256(canonical.encode()).hexdigest())
        self.assertEqual(self.store.submit(submitted), receipt)
        for method in (self.store.get_lifecycle_source_operation, self.store.inspect_lifecycle_source, self.store.read_lifecycle_source):
            with self.assertRaises(SubmissionConflictError):
                method('other', limits=f.LIMITS)
        with self.assertRaises(SubmissionConflictError):
            self.store.commit_lifecycle_source('other', expected_binding_digest='0'*64, limits=f.LIMITS)

    def test_source_commit_does_not_open_continuation(self):
        """Source commitment preserves both pending obligations and the current-policy continuation denial."""
        paused = controls.commit(self.store, controls.successor(self.original, self.result, 'pause'), policy=None, evaluated_at=None)
        f.commit(self.store)
        f.commit(self.store, 'pause')
        with self.assertRaisesRegex(c.RunControlStateError, 'zero pending mandatory reports'):
            controls.commit(self.store, controls.successor(self.original, paused, 'continue'))
        self.assertEqual(len(self.store.inspect_run_control('run', limits=controls.LIMITS).to_dict()['pending_obligations']), 2)
