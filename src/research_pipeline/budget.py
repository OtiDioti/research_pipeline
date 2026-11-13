"""Read-only observations of shared allocation and emitted model usage."""
from .context_usage import task_usage


def budget_report(state, live=False):
    from .jobs import ACTIVE
    return {'configured_limits': state['limits'],
            'occupied_job_reservations': sum(r['state'] in ACTIVE for r in state['jobs'].values()),
            'logical_allocations': sum(not t.get('released') for t in state['tasks'].values()),
            'model_telemetry': {k: r.get('telemetry') for k, r in state['contexts'].items()},
            'context_occupancy': {k: {name: r.get(name) for name in ('measurement', 'threshold_observation', 'maximum_occupancy_percent')} for k, r in state['contexts'].items()},
            'logical_usage': {k: task_usage(state, k) for k in state['tasks']},
            'account_quota': 'unknown; weekly safeguard requires V0-L3',
            'model_spending': 'unknown; no monetary cap is claimed'}
