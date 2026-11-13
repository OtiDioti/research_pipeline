"""Account-wide weekly reserve, adapted from codex_tui.policy.QuotaBook.

Full reads replace; sparse notifications merge. Each weekly value has its own
age: unrelated notifications cannot renew it. Reset times never grant quota.
"""
from copy import deepcopy
import math
import time

WEEK_MINUTES = 10080
RESERVE_PERCENT = 15
POLL_SECONDS = 30
MAX_AGE_SECONDS = 60  # one missed poll; an operational freshness bound


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def observe(record, payload, *, full, provenance='native', now=None, epoch=None):
    now = time.monotonic() if now is None else now
    epoch = time.time() if epoch is None else epoch
    payload = deepcopy(payload)
    sample = {'raw': payload, 'full': full, 'provenance': provenance,
              'observed_monotonic': now, 'observed_epoch': epoch}
    if provenance == 'native':
        record['native_observation'] = deepcopy(sample)
    record['observation'] = sample
    if payload.get('ordinaryUsageAllowed') is not None:
        record['ordinary_usage_allowed'] = payload.get('ordinaryUsageAllowed')
    if full:
        record['buckets'] = {}
    buckets = record.setdefault('buckets', {})
    by_id = payload.get('rateLimitsByLimitId')
    if not isinstance(by_id, dict) or not by_id:
        bucket = payload.get('rateLimits')
        by_id = {bucket.get('limitId') or 'default': bucket} if isinstance(bucket, dict) else {}
    for key, bucket in by_id.items():
        if (not full and key not in buckets
                and (not isinstance(bucket, dict) or not any(
                    isinstance(bucket.get(p), dict) and bucket[p].get('windowDurationMins') == WEEK_MINUTES
                    for p in ('primary', 'secondary')))):
            # Metadata-only/short-window notices (sometimes without limitId)
            # cannot invalidate or renew an established weekly observation.
            continue
        target = buckets.setdefault(key, {'windows': {}})
        if not isinstance(bucket, dict):
            target['invalid'] = True
            continue
        for position in ('primary', 'secondary'):
            incoming = bucket.get(position)
            if incoming is None:
                continue
            old = target['windows'].get(position, {})
            if not isinstance(incoming, dict):
                target['windows'][position] = {'raw': {}, 'error': 'Invalid native window'}
                continue
            raw = old.get('raw', {})
            # Window position is not its identity. A changed duration replaces it.
            if incoming.get('windowDurationMins', raw.get('windowDurationMins')) != raw.get('windowDurationMins'):
                raw = {}
            raw = {**raw, **{k: v for k, v in incoming.items() if v is not None}}
            window = {**old, 'raw': raw}
            if 'usedPercent' in incoming and incoming['usedPercent'] is not None:
                window.update(observed_monotonic=now, observed_epoch=epoch, provenance=provenance)
            target['windows'][position] = window
    values, complete = [], bool(buckets)
    for key, bucket in buckets.items():
        weekly = []
        for position, window in bucket['windows'].items():
            raw = window['raw']
            if raw.get('windowDurationMins') != WEEK_MINUTES:
                continue
            used = raw.get('usedPercent')
            valid = number(used) and used >= 0 and 'observed_monotonic' in window
            weekly.append(valid)
            if valid:
                remaining = max(0, 100 - used)
                values.append(remaining)
                if remaining <= RESERVE_PERCENT and not record.get('cutoff'):
                    record['cutoff'] = deepcopy({**sample, 'bucket_id': key, 'position': position,
                                                'window': window, 'remaining_percent': remaining})
        complete = complete and bool(weekly) and all(weekly) and not bucket.get('invalid')
    record.update(remaining_percent=min(values) if values else None, complete=complete)
    if full:
        record['preflight_ok'] = complete
        record.pop('read_error', None)
    record['status'] = 'cutoff' if record.get('cutoff') else 'available' if complete else 'unavailable'
    return sample


def admission_error(state, now=None, epoch=None):
    if state.get('admission_block'):
        return state['admission_block']
    record = state.get('quota', {})
    if record.get('cutoff'):
        return 'Weekly quota STOP latched'
    if not record.get('preflight_ok') or not record.get('complete') or record.get('read_error'):
        return 'Required weekly quota telemetry unavailable; research admission refused'
    if record.get('ordinary_usage_allowed') is False:
        return 'Native account telemetry denies ordinary usage; research admission refused'
    if record.get('transport_unavailable'):
        return 'Primary quota transport replacement in progress; research admission refused'
    now = time.monotonic() if now is None else now
    epoch = time.time() if epoch is None else epoch
    for bucket in record['buckets'].values():
        for window in bucket['windows'].values():
            raw = window['raw']
            if raw.get('windowDurationMins') == WEEK_MINUTES:
                reset = raw.get('resetsAt')
                if (now - window.get('observed_monotonic', -math.inf) >= MAX_AGE_SECONDS
                        or number(reset) and reset <= epoch):
                    return 'Required weekly quota observation expired; refresh required'
    return None
