"""Secondary context clocks. Explicit monotonic observations; warnings only."""
from .context_usage import counter


def attach(now):
    return {'attached_monotonic': now, 'changed_monotonic': now,
            'length': None, 'warned_interval': 0, 'telemetry_available': False}


def measure(clock, sample, now):
    valid = sample.get('status') == 'measured' and counter(sample.get('length'))
    clock['telemetry_available'] = valid
    if not valid:
        return False
    length = sample['length']
    changed = clock['length'] is not None and length != clock['length']
    if changed:
        clock.update(changed_monotonic=now, warned_interval=0)
    clock['length'] = length
    return changed


def due(clock, interval, now):
    if not clock['telemetry_available']:
        return []
    elapsed = max(0, now - clock['changed_monotonic'])
    multiple = int(elapsed // interval)
    notices = [{'interval_index': n, 'scheduled_seconds': n * interval,
                'elapsed_seconds': elapsed, 'emitted_monotonic': now}
               for n in range(clock['warned_interval'] + 1, multiple + 1)]
    if notices:
        clock['warned_interval'] = multiple
    return notices
