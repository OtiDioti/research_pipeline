"""Independent limits, permission failures, actual artifact loss and reserved terminal metadata capacity."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c, operating_authority as a
from research_pipeline.artifacts import ArtifactStore
from research_pipeline.store import RecordStore
from tests import run_control_fixtures as f
from tests.test_store import record, request as submission


class ControlBoundaryTests(unittest.TestCase):
    """Exercise complete real histories rather than fabricated report completion or mocked permission."""

    def setUp(self):
        """Create a disposable parent for independent permission and boundary scenarios."""
        temporary = TemporaryDirectory(prefix='control-boundary-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)

    def test_main_research_artifact_loss_and_historical_reductions(self):
        """Deleted required bytes deny preparation yet cannot block valid recorded reductions or original recovery."""
        root = self.parent / 'main'
        with RecordStore.create(root) as store:
            request = f.populate(store, main=True)
            original = f.commit(store, request)
            for path in (root / 'objects').iterdir():
                if path.is_file():
                    path.unlink()
            with patch.object(ArtifactStore, 'verify', side_effect=AssertionError('reduction must not read artifacts')), \
                    patch.object(ArtifactStore, '_verify_for_commit', side_effect=AssertionError('reduction must not sync artifacts')):
                result = original
                for action in ('pause', 'stop', 'cancel', 'milestone'):
                    result = f.commit(store, f.successor(request, result, action), policy=None, evaluated_at=None)
                self.assertEqual(store.get_run_control_operation('prepare', limits=f.LIMITS), original)
            # A separate fresh run with the same exact approval cannot prepare after actual byte loss.
            from research_pipeline.domain import RecordReference
            store.submit(submission('new-run', [record('second', kind='run', record_references=[RecordReference('project', 1, 'project', 'project')])]))
            wire = request.to_dict()
            wire.update(run_id='second', operation_id='second-prepare')
            with self.assertRaisesRegex(c.RunControlPermissionError, 'artifact_unavailable'):
                f.commit(store, c.RunControlRequest(wire))
            self.assertEqual(result.to_dict()['disposition'], 'cancelled')

    def test_no_decision_wrong_purpose_incomplete_denied_revoked_and_stale(self):
        """Current evaluator statuses fail closed for real stored empty/stale/reduced authority streams."""
        for mode in ('no_decision', 'scope_mismatch', 'incomplete', 'denied', 'revoked', 'stale'):
            with self.subTest(mode=mode), RecordStore.create(self.parent / mode) as store:
                request = f.populate(store)
                wire = request.to_dict()
                prior = store.get_revision(a.stream_id('synthetic', 'project'), 1)
                binding = a.OperatingBinding(prior.content['decision']['binding'])
                if mode == 'no_decision':
                    wire['preparation']['authority_domain'] = 'empty-domain'
                elif mode in ('scope_mismatch', 'incomplete'):
                    wire['preparation']['purpose'] = 'main_research'
                    wire['preparation']['operating_scope'] = f.authority.scope('main_research').to_dict()
                    if mode == 'incomplete':
                        signed = f.authority.sign(f.authority.decision(binding, f.authority.scope('main_research'),
                            revision=2, previous=prior, operation='incomplete-approval'))
                        # Historical generic authority storage remains supported; current
                        # eligibility must independently reject this inadequate dossier.
                        store.submit(a.submission(signed))
                        envelope = a.encode_envelope(signed)
                        wire['expected_authority'] = {'reference': c.reference(envelope.record_id, 2, 'operating_decision', 'decision'),
                            'envelope_digest': a.envelope_digest(envelope)}
                elif mode in ('denied', 'revoked'):
                    reduced = f.authority.sign(f.authority.decision(binding, revision=2, previous=prior,
                        outcome='deny' if mode == 'denied' else 'revoke', operation=mode))
                    store.commit_operating_decision(reduced, policy=f.authority.policy(), evaluated_at=f.authority.TIME, limits=f.authority.LIMITS)
                else:
                    store.submit(submission('new-project-head', [record('project', 2, 'project')], {'project': 1}))
                with self.assertRaisesRegex(c.RunControlPermissionError, mode):
                    f.commit(store, c.RunControlRequest(wire))
                self.assertIsNone(store.head(c.control_id('run')))

    def test_result_and_aggregate_limits_before_construction(self):
        """Original-result equality succeeds, overflow fails before construction, and helpers share allowances."""
        with RecordStore.create(self.parent / 'limits') as store:
            request = f.populate(store)
            original = f.commit(store, request)
            size = len(c.dumps_commit_result(original))
            self.assertEqual(store.get_run_control_operation('prepare', limits=replace(f.LIMITS, max_result_bytes=size)), original)
            with patch('research_pipeline.run_control_store._result', side_effect=AssertionError('result must be reserved first')):
                with self.assertRaises(c.RunControlLimitError):
                    store.get_run_control_operation('prepare', limits=replace(f.LIMITS, max_result_bytes=size - 1))
            for metadata in (replace(f.LIMITS.metadata, max_records=1), replace(f.LIMITS.metadata, max_references=0),
                    replace(f.LIMITS.metadata, max_history_revisions=0), replace(f.LIMITS.metadata, max_metadata_bytes=1)):
                with self.subTest(metadata=metadata), self.assertRaises(c.RunControlLimitError):
                    store.get_run_control_operation('prepare', limits=replace(f.LIMITS, metadata=metadata))
            limits = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, max_result_bytes=1))
            with patch('research_pipeline.operating_authority_store.EligibilityResult', side_effect=AssertionError('authority result must be reserved first')):
                with self.assertRaises(c.RunControlLimitError):
                    # A fresh different logical run ensures original recovery does not short-circuit evaluation.
                    from research_pipeline.domain import RecordReference
                    store.submit(submission('other-run', [record('other', kind='run', record_references=[RecordReference('project', 1, 'project', 'project')])]))
                    wire = request.to_dict()
                    wire.update(operation_id='other-prepare', run_id='other')
                    f.commit(store, c.RunControlRequest(wire), limits=limits)

    def test_reserved_pause_stop_cancel_slots_preserve_all_older_obligations(self):
        """Real 1021-transition history denies routine growth while terminal slots remain available."""
        limits = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, max_records=4096, max_history_revisions=4096, max_references=32768))
        with RecordStore.create(self.parent / 'capacity') as store:
            request = f.populate(store)
            result = f.commit(store, request, limits=limits)
            result = f.seed_checkpoints(store, request, result, 1020)
            with self.assertRaises(c.RunControlLimitError):
                f.commit(store, f.successor(request, result, 'checkpoint', operation='overflow'), limits=limits)
            for action, revision in (('pause', 1022), ('stop', 1023), ('cancel', 1024)):
                result = f.commit(store, f.successor(request, result, action), limits=limits, policy=None, evaluated_at=None)
                self.assertEqual(result.to_dict()['transition']['revision'], revision)
            self.assertEqual(store._connection.execute("SELECT count(*) FROM identities WHERE record_id GLOB 'run-control-obligation-*'").fetchone()[0], 1024)
            self.assertIsNotNone(store.get_revision(c.obligation_id('prepare'), 1))
            self.assertEqual(store.head(c.control_id('run')), 1024)

    def test_inspection_nodes_are_reserved_before_array_construction(self):
        """Complete output fragments enforce their independent node ceiling before the result constructor."""
        with RecordStore.create(self.parent / 'nodes') as store:
            request = f.populate(store)
            result = f.commit(store, request)
            f.commit(store, f.successor(request, result, 'checkpoint'))
            inspected = store.inspect_run_control('run', limits=f.LIMITS)
            _, nodes, _ = c._measure_json(inspected.to_dict(), c.RESULT_BYTES)
            with patch('research_pipeline.run_control.JSON_NODES', nodes):
                self.assertEqual(store.inspect_run_control('run', limits=f.LIMITS), inspected)
            with patch('research_pipeline.run_control.JSON_NODES', nodes - 1), \
                    patch('research_pipeline.run_control.RunControlInspection', side_effect=AssertionError('must preflight output nodes')):
                with self.assertRaises(c.RunControlLimitError):
                    store.inspect_run_control('run', limits=f.LIMITS)
