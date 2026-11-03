"""Real stored control originals and independent wire oracles for offline binding tests."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline import lifecycle_report_binding as b, run_control as c
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore
from tests import run_control_fixtures as controls, report_fixtures as reports
from tests.test_store import record, request as submission
from tests.test_work_product import manifest
from tests.test_work_product_store import product

LIMITS = b.LifecycleReportBindingLimits(max_input_bytes=b.MAX_INPUT_BYTES,
    max_packet_bytes=b.MAX_PACKET_BYTES, max_work_bytes=b.MAX_WORK_BYTES,
    max_nodes=b.MAX_NODES, max_depth=b.MAX_DEPTH)
NARRATIVE = 'Saved \b\f\n\r\t\x00\x1f\x7f "\\ α 𝒜 work'


def canonical(value):
    """Independently encode wire JSON for size and identity expectations."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def counts(value):
    """Return occurrence nodes and container depth for small trusted fixture trees."""
    if type(value) not in (dict, list):
        return 1, 0
    children = value.values() if type(value) is dict else value
    measured = [counts(child) for child in children]
    return 1 + sum(n for n, _ in measured), 1 + max((d for _, d in measured), default=0)


def rehash(packet):
    """Recompute member hashes without validation to exercise substantive contradictions."""
    for name in ('preparation', 'transition', 'obligation'):
        packet[name + '_digest'] = hashlib.sha256(canonical(packet[name]).encode('ascii')).hexdigest()
    return packet


def packet(members):
    """Build a complete packet independently from three complete envelope dictionaries."""
    preparation, transition, obligation = members
    return rehash({'format': 'research_pipeline.lifecycle_report_binding', 'version': 1,
        'preparation': deepcopy(preparation), 'transition': deepcopy(transition), 'obligation': deepcopy(obligation),
        'ordinary_work_allowed': False, 'recheck_required': True})


def reproject(packet, name):
    """Use accepted projections to rebuild a locally valid changed envelope before rehashing."""
    content = packet[name]['content']
    if name == 'obligation':
        packet[name] = c.encode_obligation(c.RunReportObligation(content),
            actor=packet[name]['provenance']['actor']).to_dict()
    else:
        packet[name] = c.encode_transition(c.RunControlTransition(content)).to_dict()
    return rehash(packet)


def captured(*, baseline=True, abandon=False):
    """Capture accepted dictionaries before closing stores, preserving every pending obligation.

    A real note manifest is deliberately not a previous report artifact. Generic
    revisions 2/3 differ from control revisions, and reductions use later dates.
    """
    with TemporaryDirectory(prefix='lifecycle-binding-') as temporary:
        with RecordStore.create(Path(temporary) / 'runtime') as store:
            original = controls.populate(store)
            artifact = store.put_artifact(b'Synthetic saved note, not a report.\n')
            store.submit_typed(submission('saved-work', [product('saved-note', manifest(artifact))]))
            store.submit(submission('run-two', [record('run', 2, 'run',
                record_references=[RecordReference('project', 1, 'project', 'project')])], {'run': 1}))
            wire = original.to_dict()
            wire.update(run_revision=2, actor='A' * 128)
            if baseline:
                wire['preparation']['start_baseline'] = reports.ref('saved-note', 'work_product_manifest', 'start_baseline')
            original = c.RunControlRequest(wire)
            result = controls.commit(store, original)
            store.submit(submission('run-three', [record('run', 3, 'run',
                record_references=[RecordReference('project', 1, 'project', 'project')])], {'run': 2}))
            actions = ('abandon',) if abandon else ('checkpoint', 'milestone', 'pause', 'stop', 'cancel', 'checkpoint')
            for index, action in enumerate(actions, 2):
                report = deepcopy(wire['report'])
                report['selection'] = [reports.ref('saved-note', 'work_product_manifest')]
                report['declarations']['objective'] = reports.text(NARRATIVE)
                report['declarations']['saved_work'] = [{'manifest': reports.ref('saved-note', 'work_product_manifest', 'saved_work'),
                    'description': reports.text('Incomplete saved note'), 'state': 'incomplete'}]
                report['limits']['max_output_total_bytes'] -= index
                proposed = controls.successor(original, result, action, operation=action + str(index),
                    run_revision=3, transitioned_at='2026-11-03T00:00:00.000000Z', report=report)
                changed = proposed.to_dict()
                if action in ('stop', 'cancel'):
                    changed['operational_reason']['code'] = 'resource_limit' if action == 'stop' else 'model_forbidden'
                result = controls.commit(store, c.RunControlRequest(changed), policy=None, evaluated_at=None)
                if action == 'pause':
                    # Continuation still fails at the existing pending gate even
                    # with valid current policy/time; binding changes no store path.
                    continuation = controls.successor(original, result, 'continue')
                    continuation = c.RunControlRequest({**continuation.to_dict(),
                        'run_revision': 3, 'transitioned_at': '2026-11-03T00:00:00.000000Z'})
                    # Do not claim a successful continuation or manufacture a receipt.
                    try:
                        controls.commit(store, continuation, evaluated_at='2026-11-03T00:00:00.000000Z')
                    except c.RunControlStateError as error:
                        if 'zero pending mandatory reports' not in str(error):
                            raise
                    else:
                        raise AssertionError('pending obligations must block continuation')
            inspection = store.inspect_run_control('run', limits=controls.LIMITS).to_dict()
            if len(inspection['pending_obligations']) != len(actions) + 1:
                raise AssertionError('binding fixtures must preserve all pending reports')
            first = inspection['transitions'][0]['envelope']
            members = [(first, entry['envelope'], obligation) for entry, obligation in
                       zip(inspection['transitions'], inspection['pending_obligations'])]
            before = canonical(inspection)
            if canonical(store.inspect_run_control('run', limits=controls.LIMITS).to_dict()) != before:
                raise AssertionError('read-only inspection changed pending facts')
        return members
