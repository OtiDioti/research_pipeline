"""Genuine captured observations and independent accounting for pure rendering tests."""

from dataclasses import replace
import hashlib
import json

from research_pipeline import lifecycle_report_rendering as render, lifecycle_report_source as source
from research_pipeline import run_control as control
from research_pipeline.domain import RecordReference
from research_pipeline.scientific import decode_envelope, encode_envelope
from research_pipeline.reports import unavailable
from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
from tests import resource_fixtures as resources
from tests.report_fixtures import ref, text
from tests.test_assessment_store import mixed_graph, declarations
from tests.test_report_resources import funded
from tests.test_store import record, request as submission, CREATOR
from tests.test_work_product import manifest
from tests.test_work_product_store import product

LIMITS = render.LifecycleRenderLimits(source=sources.LIMITS, max_work_bytes=2**63-1,
    max_output_file_bytes=64*1024*1024, max_output_total_bytes=64*1024*1024)
NARRATIVE = '## authored\n[link](https://invalid/) <script>x</script> [[wiki]] ../source.json "\\\t\x00\u202e𝒜 α'
CHECKPOINT = 'README_md--source_json'
GROUPS = ('objective_scope_context_outcome', 'results_and_recorded_changes',
    'reported_checks_and_unresolved_issues', 'saved_work_jobs_and_gaps',
    'dimensioned_resources_and_stopping_decision', 'saved_prioritized_continuation',
    'inspection_reproduction_and_limitations')


def canonical(value):
    """Use ordinary stdlib canonical JSON as an independent byte-count/output oracle."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def rehash(value):
    """Refresh a synthetic outer digest without repairing any contradictory nested facts."""
    value['snapshot_id'] = hashlib.sha256(canonical({k: v for k, v in value.items() if k != 'snapshot_id'}).encode()).hexdigest()
    return value


def forged(value):
    """Bypass construction to exercise the renderer's mandatory retained-content validation."""
    observation = object.__new__(source.LifecycleSourceObservation)
    object.__setattr__(observation, '_json', value if type(value) is str else canonical(value))
    return observation


def empty(store):
    """Capture and read an initial empty source using its actual persisted original binding."""
    original, result = sources.populate(store)
    sources.commit(store)
    return store.read_lifecycle_source('prepare', limits=sources.LIMITS), original, result


def delayed(store):
    """Capture an older checkpoint after three reductions and independently dated resource settlement.

    Typed negative evidence and disputed assessments coexist with unfinished saved
    work, repeated pins, uncertain jobs, a note baseline and unknown liabilities.
    """
    original = controls.populate(store)
    artifact = store.put_artifact(b'Saved note and incomplete checkpoint; not an earlier report.\n')
    store.submit_typed(submission('baseline', [product('saved-note', manifest(artifact))]))
    for revision in (2, 3):
        store.submit(submission('run-' + str(revision), [record('run', revision, 'run',
            record_references=[RecordReference('project', 1, 'project', 'project')])], {'run': revision-1}))
    wire = original.to_dict()
    wire['run_revision'] = 3
    wire['preparation']['start_baseline'] = ref('saved-note', 'work_product_manifest', 'start_baseline')
    original = control.RunControlRequest(wire)
    result = controls.commit(store, original)
    funded(store, private=True, sibling=True)
    store.reserve_resources(resources.reservation(maxima=resources.vector(tool_calls=10)))
    store.observe_resource_usage(resources.observation(usage=resources.vector(None, tool_calls=4)))
    store.submit(submission('generic-assessments', [e for e in declarations() if e.record_id != 'task'] +
        [record('job', kind='tool_execution', content={'result': 'opaque is not a typed claim'})]))
    graph = mixed_graph(artifact)
    for index, envelope in enumerate(graph):
        if envelope.kind == 'evidence':
            evidence = replace(decode_envelope(envelope), result='NEGATIVE: property failed', origin='unverified',
                uncertainty_details=['Measurement remains uncertain'], failure_details=['Failed synthetic check'])
            graph[index] = encode_envelope(envelope.record_id, 1, evidence, CREATOR)
    store.submit_typed(submission('assessments', graph))
    checkpoint = replace(manifest(artifact), product_kind='checkpoint', title=NARRATIVE,
        purpose='Saved next action: compare assumptions; no execution authorized.',
        task=RecordReference('task', 1, 'task', 'task_specification'),
        run=RecordReference('run', 3, 'run', 'run'),
        build_dependencies=[RecordReference('candidate', 1, 'build_dependency', 'claim')])
    store.submit_typed(submission('save-checkpoint', [product(CHECKPOINT, checkpoint)]))
    older = controls.successor(original, result, 'checkpoint').to_dict()
    older['report']['selection'] = [ref('review-a', 'review'), ref('review-b', 'review'), ref('issue', 'issue')]
    d = older['report']['declarations']
    d['objective'] = text(NARRATIVE)
    d['results'] = [{'statement': text('Conditional negative observation; no unconditional success asserted.'),
        'supporting_references': [ref('candidate', 'claim'), ref('evidence', 'evidence')]}]
    d['completed_checks'] = [{'evidence': ref('evidence', 'evidence', 'reported_evidence'), 'description': text('Reported negative check')}]
    d['unresolved_issues'] = [ref('issue', 'issue', 'unresolved_issue'), text('No resolution asserted')]
    d['saved_work'] = [
        {'manifest': ref(CHECKPOINT, 'work_product_manifest', 'saved_work'), 'description': text('Saved checkpoint'), 'state': 'checkpoint'},
        {'manifest': ref('saved-note', 'work_product_manifest', 'saved_work'), 'description': text('Incomplete note'), 'state': 'incomplete'}]
    d['outstanding_jobs'] = [{'reference': ref('job', 'tool_execution', 'outstanding_job'),
        'description': text('No termination evidence'), 'state': 'uncertain'}]
    d['gaps'] = [text('Unknown actual model usage and job completion')]
    d['continuation'] = [{'priority': priority, 'task': ref('task', 'task_specification', 'task'),
        'checkpoint': ref(CHECKPOINT, 'work_product_manifest', 'checkpoint'),
        'dependencies': [ref('job', 'tool_execution'), ref('candidate', 'claim')],
        'expected_output': text('A saved draft ' + str(priority)), 'required_checks': text('Independent verification'),
        'required_authority': text('Human review required; no permission established'),
        'required_resources': unavailable('No resource estimates saved')} for priority in (2, 7)]
    d['continuation'][0]['required_resources'] = {'account_id': 'run', 'estimates': resources.vector(tool_calls=2)}
    older = control.RunControlRequest(older)
    result = controls.commit(store, older, policy=None, evaluated_at=None)
    for action in ('pause', 'stop', 'cancel'):
        later = controls.successor(original, result, action).to_dict()
        later['report']['declarations']['objective'] = text('Later ' + action + ' intent')
        if action == 'cancel':
            later['operational_reason']['code'] = 'model_forbidden'
        result = controls.commit(store, control.RunControlRequest(later), policy=None, evaluated_at=None)
    store.observe_resource_usage(resources.observation('complete', event='authoritative_completion', usage=resources.vector(tool_calls=7)))
    store.reconcile_resource_usage(resources.reconciliation())
    sources.commit(store, 'checkpoint')
    return store.read_lifecycle_source('checkpoint', limits=sources.LIMITS), older


def counters(value, output, limits=LIMITS):
    """Independently count the prescribed W0–W3 logical representations from JSON and emitted bytes."""
    machine = json.loads(output['continuation.json'])
    p = len(canonical(value))
    b = len(canonical(value['resources']))
    operations = value['resources'].get('operations', [])
    a = sum(item['request']['kind'] in ('create_account', 'allocate') for item in operations)
    m = min(limits.source.scientific.max_metadata_bytes,
        value['binding']['transition']['content']['request']['report']['limits']['snapshot']['max_metadata_bytes'])
    ws, wr = 64*m + 4096, 256*(b+1) + 262144*(a+1)*(len(operations)+1)
    w0 = 4096 + 8*p
    w1 = w0 + 64*p + ws + wr
    w2 = w1 + 256*p + 65536
    i, g = (len(canonical(machine[k])) for k in ('identities', 'groups'))
    c = len(canonical(machine))
    h, j = len(output['report.md']), len(output['continuation.json'])
    w3 = w2 + 8*(i+g+c) + 4*(h+j) + 2*p + 4096
    return dict(P=p, B=b, Ws=ws, Wr=wr, W0=w0, W1=w1, W2=w2, W3=w3, I=i, G=g, C=c, H=h, J=j)
