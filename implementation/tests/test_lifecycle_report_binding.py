"""Offline contract and cross-member semantic tests using accepted stored originals."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_binding as b, run_control as c
from research_pipeline.store import RecordStore
from tests import run_control_fixtures as controls
from tests import lifecycle_binding_fixtures as f


class LifecycleBindingTests(unittest.TestCase):
    """Verify pairing and intent without confusing consistency with authentication."""

    @classmethod
    def setUpClass(cls):
        """Obtain real originals once; every tested binding call occurs after store closure."""
        cls.members = f.captured()
        cls.other = f.captured(baseline=False, abandon=True)

    def setUp(self):
        """Give each mutation test an isolated revision-two packet."""
        self.packet = f.packet(self.members[1])

    def reject(self, packet):
        """Require contradictory content to fail all dictionary and external JSON routes."""
        for call in (lambda: b.LifecycleReportBinding(packet, limits=f.LIMITS),
                     lambda: b.LifecycleReportBinding.from_dict(packet, limits=f.LIMITS),
                     lambda: b.loads_binding(f.canonical(packet), limits=f.LIMITS)):
            with self.assertRaises(b.LifecycleReportBindingValidationError):
                call()

    def test_all_real_actions_roundtrip_offline(self):
        """Every accepted action preserves its own intent, dates, revisions and closed gate."""
        for members in self.members + self.other:
            expected = f.packet(members)
            with self.subTest(action=members[1]['content']['request']['action']):
                value = b.bind_lifecycle_report(*members, limits=f.LIMITS)
                text = b.dumps_binding(value, limits=f.LIMITS)
                self.assertEqual(text, f.canonical(expected))
                self.assertEqual(value.to_dict(limits=f.LIMITS), expected)
                self.assertEqual(b.binding_digest(value, limits=f.LIMITS), hashlib.sha256(text.encode()).hexdigest())
                for data in (text, text.encode(), json.dumps(expected, ensure_ascii=False).encode()):
                    self.assertEqual(b.dumps_binding(b.loads_binding(data, limits=f.LIMITS), limits=f.LIMITS), text)
                selected = expected['transition']['content']['request']
                self.assertEqual(expected['obligation']['content']['required_at'], selected['transitioned_at'])
                self.assertEqual(expected['obligation']['content']['report_revision'], selected['revision'])
                self.assertEqual(expected['obligation']['revision'], 1)
                self.assertEqual(expected['preparation'], self.members[0][0] if members in self.members else self.other[0][0])
                self.assertFalse(expected['ordinary_work_allowed'])
                self.assertTrue(expected['recheck_required'])
        self.assertEqual(self.members[-1][1]['content']['disposition'], 'cancelled')
        self.assertNotEqual(self.packet['preparation']['content']['request']['transitioned_at'],
                            self.packet['transition']['content']['request']['transitioned_at'])
        self.assertEqual(self.packet['preparation']['content']['request']['run_revision'], 2)
        self.assertEqual(self.packet['transition']['content']['request']['run_revision'], 3)
        self.assertNotEqual(self.packet['preparation']['content']['request']['report'],
                            self.packet['transition']['content']['request']['report'])

    def test_initial_duplicate_and_mutation_isolation(self):
        """Repeated original envelopes remain complete and isolated from input/output mutation."""
        members = deepcopy(self.members[0])
        self.assertIs(members[0], members[1])
        value = b.bind_lifecycle_report(*members, limits=f.LIMITS)
        before = b.dumps_binding(value, limits=f.LIMITS)
        members[0]['provenance']['actor'] = 'changed'
        detached = value.to_dict(limits=f.LIMITS)
        self.assertEqual(detached['preparation'], detached['transition'])
        detached['transition'].clear()
        self.assertEqual(b.dumps_binding(value, limits=f.LIMITS), before)
        self.assertNotIn('research_pipeline.lifecycle_report_binding"', repr(value))
        self.assertNotEqual(value, b.loads_binding(before, limits=f.LIMITS))
        with self.assertRaises(FrozenInstanceError):
            value._json = '{}'

    def test_no_runtime_hooks(self):
        """All new APIs work with representative persistence, policy, clock and external seams forbidden."""
        hooks = ('research_pipeline.store.RecordStore.get_revision',
                 'research_pipeline.store.RecordStore._transaction',
                 'research_pipeline.store.RecordStore.read_artifact',
                 'research_pipeline.operating_authority_store._evaluate_eligibility',
                 'research_pipeline.report_capture.datetime',
                 'research_pipeline.operating_authority.verify_signature',
                 'research_pipeline.artifacts.ArtifactStore.read', 'socket.socket',
                 'urllib.request.urlopen', 'subprocess.Popen')
        with ExitStack() as stack:
            for name in hooks:
                stack.enter_context(patch(name, side_effect=AssertionError('offline boundary invoked runtime hook')))
            value = b.bind_lifecycle_report(*self.members[1], limits=f.LIMITS)
            value = b.LifecycleReportBinding(value.to_dict(limits=f.LIMITS), limits=f.LIMITS)
            value = b.LifecycleReportBinding.from_dict(value.to_dict(limits=f.LIMITS), limits=f.LIMITS)
            value = b.loads_binding(b.dumps_binding(value, limits=f.LIMITS).encode(), limits=f.LIMITS)
            self.assertEqual(value.to_dict(limits=f.LIMITS), self.packet)
            self.assertEqual(len(b.binding_digest(value, limits=f.LIMITS)), 64)

    def test_top_level_closed_fields_and_numeric_types(self):
        """Every wrapper field is required; unknown fields and numeric coercions fail."""
        for name in self.packet:
            changed = deepcopy(self.packet)
            del changed[name]
            with self.subTest(missing=name):
                self.reject(changed)
        for updates in ({'extra': None}, {'format': 'other'}, {'version': True}, {'version': 1.0},
                        {'version': 2}, {'ordinary_work_allowed': 0}, {'recheck_required': 1},
                        {'ordinary_work_allowed': True}, {'recheck_required': False}):
            with self.subTest(updates=updates):
                self.reject({**self.packet, **updates})

    def test_all_nested_closed_fields(self):
        """Missing/extra keys in every nested object fail, including defaultable envelope fields."""
        paths = []

        def collect(value, path=()):
            """Collect dictionary paths in the small valid packet without retaining mutations."""
            if type(value) is dict:
                paths.append(path)
                for key, child in value.items():
                    collect(child, (*path, key))
            elif type(value) is list:
                for index, child in enumerate(value):
                    collect(child, (*path, index))

        collect(self.packet)
        for path in paths:
            original = self.packet
            for key in path:
                original = original[key]
            for key in (*original, '__extra__'):
                changed = deepcopy(self.packet)
                target = changed
                for part in path:
                    target = target[part]
                if key == '__extra__':
                    target[key] = None
                else:
                    del target[key]
                with self.subTest(path=path, key=key):
                    # One common validation route is sufficient for this exhaustive
                    # grammar matrix; public boundary parity is exercised separately.
                    with self.assertRaises(b.LifecycleReportBindingValidationError):
                        b.LifecycleReportBinding(changed, limits=f.LIMITS)

    def test_digest_pins_each_preparation_and_selected_intent_field(self):
        """Every original preparation and selected report field remains protected by complete hashes."""
        for member, path in (('preparation', ('preparation',)), ('transition', ('report', 'declarations')),
                             ('transition', ('report', 'limits'))):
            request = self.packet[member]['content']['request']
            target = request
            for key in path:
                target = target[key]
            for key in target:
                changed = deepcopy(self.packet)
                destination = changed[member]['content']['request']
                for part in path:
                    destination = destination[part]
                destination[key] = {} if destination[key] is None else None
                with self.subTest(member=member, path=path, key=key):
                    self.reject(changed)
        changed = deepcopy(self.packet)
        changed['transition']['content']['request']['report']['declarations']['objective']['text']['value'] = 'Different valid narrative'
        self.reject(changed)
        changed = deepcopy(self.packet)
        changed['transition']['content']['request']['report']['limits']['max_source_bytes'] -= 1
        self.reject(changed)

    def test_rehashed_pairing_contradictions(self):
        """Recomputed member hashes cannot conceal derived identity, pin, time or selection contradictions."""
        changes = (
            ('obligation', ('content', 'operation_id'), 'other'),
            ('obligation', ('content', 'report_operation_id'), c.report_operation_id('other')),
            ('obligation', ('content', 'report_source_id'), 'other'),
            ('obligation', ('content', 'report_manifest_id'), 'other'),
            ('obligation', ('content', 'run_id'), 'other'),
            ('obligation', ('content', 'run_revision'), 4),
            ('obligation', ('content', 'report_revision'), 3),
            ('obligation', ('content', 'kind'), 'cancel'),
            ('obligation', ('content', 'required_at'), '2026-11-05T12:00:00.000000Z'),
            ('obligation', ('content', 'selection'), []),
            ('obligation', ('provenance', 'actor'), 'other'),
            ('obligation', ('provenance', 'created_at'), '2026-11-05T12:00:00.000000Z'),
            ('transition', ('content', 'prepared_from', 'record_id'), c.control_id('other')),
            ('transition', ('content', 'prepared_from', 'revision'), 2),
            ('transition', ('content', 'obligation', 'record_id'), c.obligation_id('other')),
            ('obligation', ('content', 'transition', 'revision'), 3),
            ('obligation', ('content', 'transition', 'record_id'), c.control_id('other')),
            ('transition', ('content', 'request', 'predecessor', 'envelope_digest'), '0' * 64),
            ('transition', ('content', 'request', 'predecessor', 'reference', 'revision'), 2),
            ('transition', ('content', 'request', 'run_id'), 'other'),
            ('transition', ('content', 'request', 'run_revision'), 1),
            ('transition', ('content', 'request', 'operation_id'), 'prepare'),
            ('transition', ('content', 'request', 'transitioned_at'), '2026-11-01T12:00:00.000000Z'),
            ('transition', ('provenance', 'details'), {'forged': True}),
            ('transition', ('revision',), 3),
            ('transition', ('record_id',), 'other'),
        )
        for member, path, replacement in changes:
            changed = deepcopy(self.packet)
            target = changed[member]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
            with self.subTest(member=member, path=path):
                self.reject(f.rehash(changed))
        for name in ('preparation', 'transition', 'obligation'):
            for links in ([], list(reversed(self.packet[name]['record_references'])),
                          self.packet[name]['record_references'] * 2):
                changed = deepcopy(self.packet)
                changed[name]['record_references'] = links
                self.reject(f.rehash(changed))

    def test_locally_valid_obligation_still_requires_pairing(self):
        """A separately valid obligation's actor, time, selection and run revision must match selected intent."""
        for field, replacement in (('run_revision', 4), ('selection', []),
                                   ('required_at', '2026-11-05T12:00:00.000000Z')):
            changed = deepcopy(self.packet)
            changed['obligation']['content'][field] = replacement
            f.reproject(changed, 'obligation')
            self.reject(changed)
        changed = deepcopy(self.packet)
        changed['obligation']['provenance']['actor'] = 'other'
        f.reproject(changed, 'obligation')
        self.reject(changed)

    def test_original_commitment_and_initial_duplicate(self):
        """Different valid initial bytes fail both the repeated-copy and revision-two predecessor commitment."""
        for members in self.members[:2]:
            changed = f.packet(members)
            changed['preparation']['content']['request']['report']['declarations']['objective']['text']['value'] = 'Alternate preparation'
            f.reproject(changed, 'preparation')
            self.reject(changed)
        changed = deepcopy(self.packet)
        preparation = changed['preparation']['content']['request']['preparation']
        preparation['allocation']['project_account'] = {'account_id': 'project', 'operation_id': 'account',
            'anchor': c.reference('wrong-project', 1, 'resource_scope', 'project')}
        self.reject(f.rehash(changed))

    def test_wholly_consistent_fabrication_is_not_authenticated(self):
        """Consistently rewriting available commitments passes locally without proving persisted facts."""
        changed = deepcopy(self.packet)
        changed['preparation']['content']['request']['report']['declarations']['objective']['text']['value'] = 'Illustrative fabricated intent'
        f.reproject(changed, 'preparation')
        changed['transition']['content']['request']['predecessor']['envelope_digest'] = changed['preparation_digest']
        f.reproject(changed, 'transition')
        self.assertEqual(b.LifecycleReportBinding(changed, limits=f.LIMITS).to_dict(limits=f.LIMITS), changed)
        # Above revision two the omitted predecessor is not the preparation.
        changed = f.packet(self.members[-1])
        changed['preparation']['content']['request']['report']['declarations']['objective']['text']['value'] = 'Another consistent original'
        f.reproject(changed, 'preparation')
        self.assertEqual(b.LifecycleReportBinding(changed, limits=f.LIMITS).to_dict(limits=f.LIMITS), changed)

    def test_continue_local_policy_and_capacity(self):
        """Synthetic continuation checks original policy identity but conveys no persisted success."""
        changed = f.packet(self.members[-1])
        selected = changed['transition']['content']
        selected['request'].update(action='continue', operational_reason=None,
            expected_authority=deepcopy(changed['preparation']['content']['request']['expected_authority']))
        selected.update(disposition='prepared', authorization=deepcopy(changed['preparation']['content']['authorization']))
        selected['authorization']['evaluated_at'] = selected['request']['transitioned_at']
        f.reproject(changed, 'transition')
        changed['obligation']['content'] = c.obligation_document(selected)
        f.reproject(changed, 'obligation')
        b.LifecycleReportBinding(changed, limits=f.LIMITS)
        selected['authorization']['policy_fingerprint'] = 'f' * 64
        # Reproject replaces the envelope, so modify its retained replacement.
        changed['transition']['content']['authorization']['policy_fingerprint'] = 'f' * 64
        f.reproject(changed, 'transition')
        self.reject(changed)
        changed = f.packet(self.members[-1])
        request = changed['transition']['content']['request']
        request['revision'] = c.capacity('checkpoint') + 1
        request['predecessor']['reference']['revision'] = request['revision'] - 1
        f.reproject(changed, 'transition')
        changed['obligation']['content'] = c.obligation_document(changed['transition']['content'])
        f.reproject(changed, 'obligation')
        self.reject(changed)

    def test_actor_and_canonical_timestamp_rules(self):
        """128 ASCII actor characters are accepted; non-ASCII, overflow and normalized-on-read timestamps fail."""
        self.assertEqual(len(self.packet['preparation']['provenance']['actor']), 128)
        for actor in ('A' * 129, 'é', ''):
            changed = deepcopy(self.packet)
            changed['transition']['content']['request']['actor'] = actor
            changed['transition']['provenance']['actor'] = actor
            changed['obligation']['provenance']['actor'] = actor
            self.reject(f.rehash(changed))
        changed = deepcopy(self.packet)
        changed['preparation']['provenance']['created_at'] = '2026-11-02T12:00:00Z'
        self.reject(f.rehash(changed))

    def test_invalid_embedded_allowances_are_content_errors(self):
        """Report-intent limits grant no processing budget and invalid values are validation failures."""
        for field in self.packet['transition']['content']['request']['report']['limits']:
            changed = deepcopy(self.packet)
            changed['transition']['content']['request']['report']['limits'][field] = -1
            self.reject(f.rehash(changed))
        for member, path in (('transition', ('revision',)), ('obligation', ('revision',)),
                             ('transition', ('content', 'version')),
                             ('transition', ('content', 'request', 'version')),
                             ('obligation', ('content', 'version')),
                             ('transition', ('content', 'request', 'run_revision'))):
            for value in (True, 1.0, 0):
                changed = deepcopy(self.packet)
                target = changed[member]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.reject(f.rehash(changed))

    def test_selected_empty_intent_and_declaration_projection(self):
        """Later empty selections and changed declaration references survive only with exact projections."""
        changed = deepcopy(self.packet)
        selected = changed['transition']['content']
        selected['request']['report']['selection'] = []
        selected['request']['report']['declarations']['saved_work'][0]['manifest']['revision'] = 7
        f.reproject(changed, 'transition')
        changed['obligation']['content'] = c.obligation_document(selected)
        f.reproject(changed, 'obligation')
        value = b.LifecycleReportBinding(changed, limits=f.LIMITS)
        self.assertEqual(value.to_dict(limits=f.LIMITS)['obligation']['content']['selection'], [])
        self.assertEqual(value.to_dict(limits=f.LIMITS)['preparation'], self.packet['preparation'])
        # Changing a declaration reference and rehashing is insufficient when its
        # separately projected occurrence retains the old revision.
        changed['transition']['content']['request']['report']['declarations']['saved_work'][0]['manifest']['revision'] = 8
        self.reject(f.rehash(changed))

    def test_all_report_limit_leaf_pins_and_digest_fields(self):
        """Every nested retained report allowance and every member digest is independently checked."""
        limits = self.packet['transition']['content']['request']['report']['limits']
        for name, value in limits.items():
            keys = value if type(value) is dict else (None,)
            for key in keys:
                changed = deepcopy(self.packet)
                target = changed['transition']['content']['request']['report']['limits']
                if key is None:
                    target[name] -= 1
                else:
                    target[name][key] += 1
                with self.subTest(limit=name, key=key):
                    self.reject(changed)
        for member in ('preparation', 'transition', 'obligation'):
            for digest in ('0' * 64, 'A' * 64, '0' * 63, None, 1):
                changed = deepcopy(self.packet)
                changed[member + '_digest'] = digest
                with self.subTest(member=member, digest_type=type(digest)):
                    self.reject(changed)

    def test_pending_store_facts_unchanged_after_offline_binding(self):
        """Reopen real original storage after detached processing and retain pending-report denial."""
        with TemporaryDirectory(prefix='lifecycle-binding-pending-') as temporary:
            root = Path(temporary) / 'runtime'
            with RecordStore.create(root) as store:
                request = controls.populate(store)
                initial = controls.commit(store, request)
                paused = controls.commit(store, controls.successor(request, initial, 'pause'))
                before = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
                preparation = before['transitions'][0]['envelope']
                selected = before['transitions'][1]['envelope']
                obligation = before['pending_obligations'][1]
            value = b.bind_lifecycle_report(preparation, selected, obligation, limits=f.LIMITS)
            b.loads_binding(b.dumps_binding(value, limits=f.LIMITS), limits=f.LIMITS)
            b.LifecycleReportBinding.from_dict(value.to_dict(limits=f.LIMITS), limits=f.LIMITS)
            b.binding_digest(value, limits=f.LIMITS)
            with RecordStore.open(root) as store:
                self.assertEqual(store.inspect_run_control('run', limits=controls.LIMITS).to_dict(), before)
                self.assertEqual(store.get_run_control_operation('prepare', limits=controls.LIMITS), initial)
                self.assertEqual(store.get_run_control_operation('pause', limits=controls.LIMITS), paused)
                with self.assertRaisesRegex(c.RunControlStateError, 'zero pending mandatory reports'):
                    controls.commit(store, controls.successor(request, paused, 'continue'))

    def test_preparation_account_anchors_and_original_lower_bounds(self):
        """Both account anchors and locally reprojected lower-bound contradictions remain checked."""
        for account, identity, kind in (('project_account', 'project', 'project'), ('run_account', 'run', 'run')):
            changed = deepcopy(self.packet)
            allocation = changed['preparation']['content']['request']['preparation']['allocation']
            allocation['project_account'] = {'account_id': 'project', 'operation_id': 'project-account',
                'anchor': c.reference('project', 1, 'resource_scope', 'project')}
            allocation[account] = {'account_id': identity, 'operation_id': 'account-operation',
                'anchor': c.reference('wrong', 1, 'resource_scope', kind)}
            with self.subTest(account=account):
                self.reject(f.rehash(changed))
        for field, value in (('run_revision', 1), ('transitioned_at', '2026-11-01T12:00:00.000000Z')):
            changed = f.packet(self.members[-1])
            changed['transition']['content']['request'][field] = value
            f.reproject(changed, 'transition')
            changed['obligation']['content'] = c.obligation_document(changed['transition']['content'])
            f.reproject(changed, 'obligation')
            self.reject(changed)
