"""Usage quota of the agent CLIs, read without any model call.

Adapted from project_manager's ``quota.py``. Each CLI reports its usage windows
in its own way, so this module holds one small probe per backend
(:data:`PROBES`). Everything else is generic: a :class:`Window` is classified by
its length as short (such as five hours) or weekly, and :func:`check` compares
its remaining share with the human's limits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import subprocess
import threading

from research_pipeline.drivers.claude import clean_environment

#: Windows at least this long count as weekly; shorter ones as short windows.
WEEK_MINUTES = 7 * 24 * 60
#: Seconds a probe may take before it is abandoned.
TIMEOUT = 60


@dataclass(frozen=True)
class Window:
    """One usage window of one backend."""
    backend: str
    minutes: int               # window length
    used: float                # percentage used
    resets_at: float | None    # POSIX time of the next reset, if reported

    @property
    def weekly(self) -> bool:
        return self.minutes >= WEEK_MINUTES

    @property
    def remaining(self) -> float:
        return max(0.0, 100.0 - self.used)

    def __str__(self) -> str:
        return f'{self.backend} {"week" if self.weekly else f"{self.minutes // 60}h"}: {self.remaining:.0f}% left'


def _exchange(command: list[str], steps: list[tuple[dict, object]], env: dict | None = None) -> dict:
    """Send JSON lines to a fresh ``command``, waiting after each for the reply its predicate accepts.

    Return the last accepted reply. The process is killed afterwards, or after
    :data:`TIMEOUT` seconds, which ends any pending read.
    """
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, env=env) as process:
        timer = threading.Timer(TIMEOUT, process.kill)
        timer.start()
        reply = {}
        try:
            for message, accepts in steps:
                process.stdin.write(json.dumps(message) + '\n')
                process.stdin.flush()
                if accepts is None:
                    continue
                for line in process.stdout:
                    try:
                        reply = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(reply, dict) and accepts(reply):
                        break
                else:
                    raise OSError(f'{command[0]} ended without a usage reply')
            return reply
        finally:
            timer.cancel()
            process.kill()


def _codex() -> list[Window]:
    """Read Codex's windows through its app-server (``account/rateLimits/read``)."""
    reply = _exchange(['codex', 'app-server'], [
        ({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'research_pipeline', 'version': '0'}}},
         lambda message: message.get('id') == 1),
        ({'method': 'initialized'}, None),
        ({'id': 2, 'method': 'account/rateLimits/read'}, lambda message: message.get('id') == 2)])
    if 'result' not in reply:
        raise OSError('Codex refused the usage read')
    buckets = (reply['result'].get('rateLimitsByLimitId') or {}).values()
    return [Window('codex', window['windowDurationMins'], float(window['usedPercent']), window.get('resetsAt'))
            for bucket in buckets for window in (bucket.get('primary'), bucket.get('secondary'))
            if isinstance(window, dict) and window.get('windowDurationMins')]


def _claude() -> list[Window]:
    """Read Claude Code's windows with a ``get_usage`` control request to a non-persistent print process."""
    reply = _exchange(['claude', '-p', '--input-format', 'stream-json', '--output-format', 'stream-json',
                       '--verbose', '--no-session-persistence'],
                      [({'type': 'control_request', 'request_id': 'usage', 'request': {'subtype': 'get_usage'}},
                        lambda message: message.get('type') == 'control_response')], env=clean_environment())
    usage = reply.get('response', {}).get('response') or {}
    limits = usage.get('rate_limits') if usage.get('rate_limits_available') else None
    windows = []
    for name, value in (limits or {}).items():
        if (isinstance(value, dict) and isinstance(value.get('utilization'), (int, float))
                and name.startswith(('five_hour', 'seven_day'))):
            resets = value.get('resets_at')
            windows.append(Window('claude', 300 if name.startswith('five_hour') else WEEK_MINUTES,
                                  float(value['utilization']),
                                  datetime.fromisoformat(resets).timestamp() if resets else None))
    return windows


#: Usage probe of each backend that has one; a backend without a probe is not guarded.
PROBES = {'codex': _codex, 'claude': _claude}


def read(backend: str) -> list[Window]:
    """Return the windows of ``backend`` (none if it has no probe); raise OSError if they cannot be read."""
    if backend not in PROBES:
        return []
    try:
        return PROBES[backend]()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise OSError(f'cannot read the usage of {backend}: {error}') from None


def check(windows: list[Window], short_limit: float, weekly_limit: float) -> tuple[list[Window], list[Window]]:
    """Return the short and weekly windows whose remaining share is at or below its limit (0 disables)."""
    short = [w for w in windows if not w.weekly and short_limit and w.remaining <= short_limit]
    weekly = [w for w in windows if w.weekly and weekly_limit and w.remaining <= weekly_limit]
    return short, weekly
