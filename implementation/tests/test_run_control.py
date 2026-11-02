"""Closed lifecycle documents, exact projections, and pure non-admitting transition rules."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c, operating_authority as a
from research_pipeline.domain import RecordEnvelope, CreationProvenance
from research_pipeline.store import RecordStore
from tests import run_control_fixtures as f
from tests.test_source import dictionaries, at_path


class ControlContractTests(unittest.TestCase):
    """Use real stored pairs to test wire contracts without treating decoding as permission."""

    def setUp(self):
        """Create one disposable prepared stream and all five detached document types."""
        temporary = TemporaryDirectory(prefix='control-contract-')
        self.addCleanup(temporary.cleanup)
        self.store = RecordStore.create(Path(temporary.name) / 'runtime')
        self.addCleanup(self.store.close)
        self.request = f.populate(self.store)
        self.result = f.commit(self.store, self.request)
        self.inspection = self.store.inspect_run_control('run', limits=f.LIMITS)
        wire = self.inspection.to_dict()
        self.transition = RecordEnvelope.from_dict(wire['transitions'][0]['envelope'])
        self.obligation = RecordEnvelope.from_dict(wire['pending_obligations'][0])
        self.values = [(self.request, c.dumps_request, c.loads_request),
            (c.decode_transition(self.transition), c.dumps_transition, c.loads_transition),
            (c.decode_obligation(self.obligation), c.dumps_obligation, c.loads_obligation),
            (self.result, c.dumps_commit_result, c.loads_commit_result),
            (self.inspection, c.dumps_inspection, c.loads_inspection)]

    def test_roundtrips_detachment_and_forgery(self):
        """All values round-trip, detach their input/output, and revalidate exact retained classes."""
        for value, dumps, loads in self.values:
            with self.subTest(type=type(value).__name__):
                self.assertEqual(loads(dumps(value)), value)
                self.assertEqual(loads(json.dumps(value.to_dict()).encode()), value)
                wire = value.to_dict()
                wire['version'] = 7
                self.assertEqual(value.to_dict()['version'], 1)
                forged = object.__new__(type(value))
                object.__setattr__(forged, '_json', '{"version":true}')
                with self.assertRaises(c.RunControlValidationError):
                    dumps(forged)
                derived = type('Unsupported', (type(value),), {'__doc__': 'Unsupported contract subclass.'})
                with self.assertRaises(c.RunControlValidationError):
                    derived(value.to_dict())

    def test_closed_top_level_fields_and_duplicate_keys(self):
        """Every document rejects missing/unknown fields, duplicate keys, and coerced versions."""
        for value, _, loads in self.values:
            wire = value.to_dict()
            for key in (*wire, 'extension'):
                changed = deepcopy(wire)
                if key == 'extension':
                    changed[key] = None
                else:
                    del changed[key]
                with self.subTest(contract=type(value).__name__, key=key), self.assertRaises(c.RunControlValidationError):
                    type(value)(changed)
            with self.assertRaises(c.RunControlValidationError):
                loads('{"version":1,' + c.canonical(wire)[1:])
            for version in (True, '1', 1.0):
                with self.assertRaises(c.RunControlValidationError):
                    type(value)({**wire, 'version': version})

    def test_nested_request_fields_are_closed(self):
        """Each nested request object rejects missing and unknown fields, including nullable fields."""
        wire = self.request.to_dict()
        for path in dictionaries(wire):
            for key in (*at_path(wire, path), 'extension'):
                changed = deepcopy(wire)
                target = at_path(changed, path)
                if key == 'extension':
                    target[key] = None
                else:
                    del target[key]
                with self.subTest(path=path, key=key), self.assertRaises(c.RunControlValidationError):
                    c.RunControlRequest(changed)

    def test_ascii_actor_contract_and_distinct_revisions(self):
        """The existing 128-character identifier actor succeeds; narrative Unicode and coercions reject."""
        wire = self.request.to_dict()
        accepted = c.RunControlRequest({**wire, 'actor': 'a' * 128, 'run_revision': 7})
        self.assertEqual(accepted.to_dict()['revision'], 1)
        self.assertEqual(accepted.to_dict()['run_revision'], 7)
        for actor in ('ü', 'a' * 129, '', 'a b', '-actor', True):
            with self.subTest(actor=actor), self.assertRaises(c.RunControlValidationError):
                c.RunControlRequest({**wire, 'actor': actor})
        for revision in (True, '1', 0, 2**63):
            with self.assertRaises(c.RunControlValidationError):
                c.RunControlRequest({**wire, 'run_revision': revision})
        for stamp in ('2026-11-02T12:00:00Z', '2026-11-02T13:00:00.000000+01:00'):
            with self.assertRaises(c.RunControlValidationError):
                c.RunControlRequest({**wire, 'transitioned_at': stamp})

    def test_projection_and_cross_record_provenance(self):
        """Local obligation decoding allows its own actor; historical pairing requires the originating actor."""
        self.assertEqual(self.transition.provenance, CreationProvenance('controller', f.authority.TIME, {}))
        self.assertEqual(self.obligation.provenance, self.transition.provenance)
        self.assertEqual([ref.relationship for ref in self.transition.record_references],
            ['run', 'project_setup', 'initial_corpus', 'current_corpus', 'operating_decision', 'required_report'])
        self.assertEqual([ref.relationship for ref in self.obligation.record_references], ['run_control'])
        self.assertEqual(self.transition.artifact_references, ())
        self.assertEqual(self.obligation.artifact_references, ())
        altered = c.encode_obligation(c.decode_obligation(self.obligation), actor='different')
        self.assertEqual(c.decode_obligation(altered), c.decode_obligation(self.obligation))
        with self.assertRaises(c.RunControlIntegrityError):
            c.paired_obligation(self.transition.content, self.transition, altered)
        for envelope, decoder in ((self.transition, c.decode_transition), (self.obligation, c.decode_obligation)):
            for field, changed in (('record_id', 'wrong'), ('revision', 2),
                    ('record_references', []), ('provenance', CreationProvenance('other', f.authority.TIME, {'extra': 1}).to_dict())):
                wire = envelope.to_dict()
                wire[field] = changed
                with self.subTest(field=field), self.assertRaises(c.RunControlValidationError):
                    decoder(RecordEnvelope.from_dict(wire))
        self.assertEqual(c.envelope_digest(self.transition), a.envelope_digest(self.transition))

    def test_sorted_declaration_links_and_array_order(self):
        """Sorted object traversal differs from insertion order while repeated array roles remain ordered."""
        one = c.reference('one', 1, 'reported_evidence', 'evidence')
        two = c.reference('two', 1, 'report_selection', 'event')
        self.assertEqual(list(c._declaration_references({'z': [two, one], 'a': one})), [one, two, one])

    def test_every_transition_pair_and_terminal_evidence(self):
        """The pure table covers continuation without bypassing the public pending-report gate."""
        expected = {None: {'prepare': 'prepared'}, 'prepared': {'checkpoint': 'prepared', 'milestone': 'prepared',
            'pause': 'paused', 'stop': 'stopped', 'cancel': 'cancelled', 'abandon': 'abandoned'},
            'paused': {'checkpoint': 'paused', 'milestone': 'paused', 'continue': 'prepared', 'stop': 'stopped',
                'cancel': 'cancelled', 'abandon': 'abandoned'},
            'stopped': {'checkpoint': 'stopped', 'milestone': 'stopped', 'cancel': 'cancelled', 'abandon': 'abandoned'},
            'cancelled': {'checkpoint': 'cancelled', 'milestone': 'cancelled'},
            'abandoned': {'checkpoint': 'abandoned', 'milestone': 'abandoned'}}
        for prior, allowed in expected.items():
            for action in c.ACTIONS:
                with self.subTest(prior=prior, action=action):
                    if action in allowed:
                        self.assertEqual(c.transition_disposition(prior, action), allowed[action])
                    else:
                        with self.assertRaises(c.RunControlStateError):
                            c.transition_disposition(prior, action)
        self.assertEqual([c.capacity(action) for action in ('checkpoint', 'pause', 'stop', 'cancel')], [1021, 1022, 1023, 1024])

    def test_preflight_depth_nodes_escaping_and_bytes(self):
        """Exact canonical escaping is counted before encoding, independently of depth and node limits."""
        for value in ('', '\\"\n', '\x7f', 'é😀', {'a': [None, True, 1]}):
            size = len(c.canonical(value))
            self.assertEqual(c.bounded_size(value, size), size)
            with self.assertRaises(c.RunControlLimitError):
                c.bounded_size(value, size - 1)
        nested = None
        for _ in range(48):
            nested = [nested]
        c.bounded_size(nested, 1000)
        with self.assertRaises(c.RunControlValidationError):
            c.bounded_size([nested], 1000)
        with self.assertRaises(c.RunControlValidationError):
            c.bounded_size([None] * c.JSON_NODES, c.RESULT_BYTES)
        with self.assertRaises(c.RunControlValidationError):
            c.loads_request('{"a":NaN}')
        with patch('research_pipeline.run_control.json.loads', side_effect=AssertionError('must preflight first')):
            with self.assertRaises(c.RunControlLimitError):
                c.loads_request(' ' * (c.REQUEST_BYTES + 1))
        forged = object.__new__(RecordEnvelope)
        object.__setattr__(forged, '_content_json', 'x' * (c.TRANSITION_BYTES + 1))
        object.__setattr__(forged, 'provenance', self.transition.provenance)
        object.__setattr__(forged, 'record_references', ())
        object.__setattr__(forged, 'artifact_references', ())
        for name in ('record_id', 'revision', 'kind', 'operational_status', 'scientific_disposition'):
            object.__setattr__(forged, name, getattr(self.transition, name))
        with patch('research_pipeline.run_control.json.loads', side_effect=AssertionError('must preflight first')):
            with self.assertRaises(c.RunControlLimitError):
                c.decode_transition(forged)

    def test_derived_reference_revisions_reject_boolean_equality(self):
        """Derived-reference equality never allows True to stand in for integer revision one."""
        transition = c.decode_transition(self.transition).to_dict()
        for path in (('obligation',), ('authorization', 'decision', 'reference')):
            changed = deepcopy(transition)
            at_path(changed, path)['revision'] = True
            with self.assertRaises(c.RunControlValidationError):
                c.RunControlTransition(changed)
        changed = c.decode_obligation(self.obligation).to_dict()
        changed['transition']['revision'] = True
        with self.assertRaises(c.RunControlValidationError):
            c.RunReportObligation(changed)
        changed = self.inspection.to_dict()
        changed['head']['revision'] = True
        with self.assertRaises(c.RunControlValidationError):
            c.RunControlInspection(changed)
