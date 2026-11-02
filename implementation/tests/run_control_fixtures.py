"""Synthetic authenticated control fixtures with real metadata and explicitly pending reports."""

from research_pipeline import run_control as c, operating_authority as a
from research_pipeline.domain import RecordReference
from research_pipeline.reports import unavailable
from tests import operating_fixtures as authority, report_fixtures as reports
from tests.test_store import record, request as submission

LIMITS = c.RunControlLimits(authority.LIMITS, 1024, 1024, c.RESULT_BYTES)


def populate(store, *, main=False):
    """Store a real dossier, descriptive run and signed approval, returning a complete prepare request."""
    if main:
        authority.short_note(store)
    else:
        authority.empty(store)
    store.submit(submission('generic-run', [record('run', kind='run', record_references=[RecordReference('project', 1, 'project', 'project')])]))
    scope = authority.scope('main_research' if main else 'setup', data=main)
    binding = authority.prepare(store, scope)
    signed = authority.sign(authority.decision(binding, scope))
    result = store.commit_operating_decision(signed, policy=authority.policy(), evaluated_at=authority.TIME, limits=authority.LIMITS)
    value = result.to_dict()
    pin = {'reference': value['decision'], 'envelope_digest': value['envelope_digest']}
    dossier = binding.to_dict()
    report = reports.report_request().to_dict()
    return c.RunControlRequest({'format': 'research_pipeline.run_control_request', 'version': 1,
        'operation_id': 'prepare', 'run_id': 'run', 'run_revision': 1, 'revision': 1, 'predecessor': None,
        'action': 'prepare', 'actor': 'controller', 'transitioned_at': authority.TIME,
        'preparation': {'authority_domain': 'synthetic', 'purpose': scope.to_dict()['purpose'], 'project': dossier['project'],
            **{key: dossier['dossier'][key] for key in ('initial_corpus', 'current_corpus', 'context')},
            'start_baseline': unavailable('No saved initial work was declared.'), 'operating_scope': scope.to_dict(),
            'allocation': {'allocation_id': 'allocation', 'project_account': unavailable('No project account declared.'),
                'run_account': unavailable('No run account declared.')}, 'previous_run': None},
        'expected_authority': pin, 'operational_reason': None,
        'report': {key: report[key] for key in ('selection', 'declarations', 'limits')}})


def commit(store, request, **updates):
    """Commit synthetic evidence with explicit disposable policy/time and independent bounds."""
    options = {'policy': authority.policy(), 'evaluated_at': authority.TIME, 'limits': LIMITS, **updates}
    return store.commit_run_control(request, **options)


def successor(original, result, action, *, operation=None, **updates):
    """Propose a distinct operation at the exact original predecessor with no implicit head selection."""
    value = original.to_dict()
    result = result.to_dict()
    predecessor = {**result['transition'], 'relationship': 'supersedes'}
    value.update(operation_id=operation or action, revision=predecessor['revision'] + 1,
        predecessor={'reference': predecessor, 'envelope_digest': result['transition_digest']}, action=action,
        preparation=None, expected_authority=value['expected_authority'] if action == 'continue' else None,
        operational_reason={'code': 'abandoned' if action == 'abandon' else 'requested', 'detail': 'Explicit synthetic reduction.'}
            if action in ('pause', 'stop', 'cancel', 'abandon') else None)
    value.update(updates)
    return c.RunControlRequest(value)


def seed_checkpoints(store, initial_request, original, count):
    """Build a large valid immutable fixture without repeatedly inspecting every already-tested prefix.

    Each row uses the production contracts, projections, CAS and insertion helper
    in one transaction. This never invents completed reports or a continuation.
    """
    import hashlib
    from research_pipeline import run_control_store as persistence
    from research_pipeline.schema import validate_request_kinds
    result = original
    with store._transaction(write=True) as connection:
        for index in range(count):
            request = successor(initial_request, result, 'checkpoint', operation='seed-' + str(index)).to_dict()
            transition = c.encode_transition(c.RunControlTransition({'format': c.FORMATS[0], 'version': 1,
                'request': request, 'disposition': 'prepared', 'prepared_from': c.reference(c.control_id(request['run_id']), 1, 'prepared_from'),
                'authorization': None, 'obligation': c.reference(c.obligation_id(request['operation_id']), 1, 'required_report')}))
            obligation = c.encode_obligation(c.RunReportObligation(c.obligation_document(transition.content)), actor=request['actor'])
            submitted = persistence._submission(transition, obligation, request)
            canonical = c.canonical({'fingerprint_version': 1, 'submission': submitted.to_dict()})
            validate_request_kinds(submitted, store._schema_version)
            store._check_batch(connection, submitted)
            receipt = store._insert_submission(connection, submitted, canonical, hashlib.sha256(canonical.encode('ascii')).hexdigest())
            result = persistence._result(transition, obligation, receipt, transition.content,
                digests=(c.envelope_digest(transition), c.envelope_digest(obligation)))
    return result
