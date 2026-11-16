"""Usage quota of the agent CLIs: the generic part (PROJECT.md §6, "Quota").

Each CLI reports its usage windows in its own way, so every driver reads its own
(:meth:`research_pipeline.drivers.Session.read_usage`, without any model call).
This module holds what is shared: a :class:`Window` is classified by its length as
short (such as five hours) or weekly, :func:`check` compares its remaining share
with the human's limits, and :func:`exchange` runs the short JSON-lines
conversation that probes need.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import threading
from typing import Callable

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


def read(driver: type) -> list[Window]:
    """Return the usage windows a driver class reads; raise OSError if they cannot be read."""
    try:
        return driver.read_usage()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise OSError(f'cannot read the usage of {driver.backend}: {error}') from None


def check(windows: list[Window], short_limit: float, weekly_limit: float) -> tuple[list[Window], list[Window]]:
    """Return the short and weekly windows whose remaining share is at or below its limit (0 disables)."""
    short = [w for w in windows if not w.weekly and short_limit and w.remaining <= short_limit]
    weekly = [w for w in windows if w.weekly and weekly_limit and w.remaining <= weekly_limit]
    return short, weekly


def exchange(command: list[str], steps: list[tuple[dict, Callable[[dict], bool] | None]],
             env: dict | None = None) -> dict:
    """Send JSON lines to a fresh ``command``, waiting after each for the reply its predicate accepts.

    A step whose predicate is None expects no reply. Return the last accepted
    reply. The process is killed afterwards, or after :data:`TIMEOUT` seconds,
    which ends any pending read.
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
                    raise OSError(f'{command[0]} ended without the expected reply')
            return reply
        finally:
            timer.cancel()
            process.kill()
