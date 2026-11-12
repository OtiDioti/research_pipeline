"""Read-only observations of shared allocation and emitted model usage."""
from .isolation import boot_identity


def budget_report(state, live=False):
    from .jobs import ACTIVE
    return {'configured_limits': state['limits'],
            'occupied_job_reservations': sum(r['state'] in ACTIVE for r in state['jobs'].values()),
            'logical_allocations': sum(not t.get('released') for t in state['tasks'].values()),
            'model_telemetry': {k: r.get('telemetry') for k, r in state['contexts'].items()},
            'context_occupancy': 'Raw native per-context telemetry; automatic measured rollover requires V0-L2',
            'model_spending': 'unknown; no monetary cap is claimed'}
