"""Measured context policy, adapted from codex_controller/codex_tui/policy.py.

Native int64 last.totalTokens is context length; total is cumulative spending.
The controller's Codex display convention subtracts a 12,000-token baseline
from both length and window (small windows use the raw ratio). No upper clamp:
late observations and checkpoint overshoot must remain visible.
"""
from copy import deepcopy
import time

BASELINE_TOKENS = 12000
THRESHOLD_PERCENT = 55


def counter(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def normalize(usage):
    if not isinstance(usage, dict) or not isinstance(usage.get('last'), dict):
        raise ValueError('Missing native tokenUsage.last')
    length, window = usage['last'].get('totalTokens'), usage.get('modelContextWindow')
    if not counter(length) or not counter(window) or window == 0:
        raise ValueError('Context length/window must be nonnegative/positive native integers')
    baseline = BASELINE_TOKENS if window > BASELINE_TOKENS else 0
    usable_length, usable_window = max(0, length - baseline), window - baseline
    return {'length': length, 'window': window, 'baseline': baseline,
            'usable_length': usable_length, 'usable_window': usable_window,
            'occupancy_percent': 100 * usable_length / usable_window,
            'threshold_reached': 100 * usable_length >= THRESHOLD_PERCENT * usable_window}


def observe(record, params, provenance='native'):
    """Update only the owning context. Injection never updates native spending."""
    if params.get('threadId') != record.get('native_thread_id') or not isinstance(params.get('turnId'), str):
        raise ValueError('Context telemetry ownership/turn identity mismatch')
    usage = deepcopy(params.get('tokenUsage'))
    sample = {'raw': usage, 'thread_id': params['threadId'], 'turn_id': params['turnId'],
              'observed_epoch': time.time(), 'provenance': provenance}
    try:
        sample.update(normalize(usage), status='measured')
    except ValueError as exc:
        sample.update(status='unreliable', error=str(exc))
    record['measurement'] = sample
    record['observation_count'] = record.get('observation_count', 0) + 1
    if provenance == 'native':
        record['native_observation_count'] = record.get('native_observation_count', 0) + 1
        record['native_measurement'] = sample
        record['telemetry'] = usage
        total = usage.get('total') if isinstance(usage, dict) else None
        previous = record.get('cumulative_usage', {})
        if (not isinstance(total, dict) or not counter(total.get('totalTokens'))
                or any(not counter(v) for v in total.values())
                or any(total.get(k, -1) < v for k, v in previous.items())):
            record['accounting_incomplete'] = True
        else:
            record['cumulative_usage'] = total.copy()
    if sample['status'] == 'measured':
        record['maximum_occupancy_percent'] = max(record.get('maximum_occupancy_percent', 0), sample['occupancy_percent'])
        if sample['threshold_reached'] and not record.get('threshold_observation'):
            record['threshold_observation'] = deepcopy(sample)
    return sample


def task_usage(state, task_id):
    records = [r for r in state['contexts'].values() if r['task_id'] == task_id]
    totals = {}
    for record in records:
        for key, value in record.get('cumulative_usage', {}).items():
            totals[key] = totals.get(key, 0) + value
    return {'observed_cumulative': totals, 'complete': bool(records) and all(
        'cumulative_usage' in r and not r.get('accounting_incomplete') for r in records)}
