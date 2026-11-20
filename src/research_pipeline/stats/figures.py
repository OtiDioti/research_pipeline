"""The numbers and lines of the Stats view, from an :class:`~research_pipeline.stats.analysis.Analysis`.

Each function returns plain values (counts, durations, points over time since the
analysis' start); :mod:`research_pipeline.stats.view` lays them out. The same
functions serve compared projects, so their lines and numbers match.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable

from research_pipeline.stats.analysis import Analysis, Record, concurrent, working

Points = list[list[float]]


def duration(seconds: float | None) -> str:
    """3725 -> '1h 02m'; None -> '–'."""
    if seconds is None:
        return "–"
    total = max(0, round(seconds))
    hours, minutes = divmod(total // 60, 60)
    if hours >= 48:
        return f"{hours // 24}d {hours % 24}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m {total % 60:02d}s" if minutes else f"{total}s"


def share(part: int, whole: int) -> str:
    """'12 of 40 (30%)'."""
    return f"{part} of {whole}" + (f" ({round(100 * part / whole)}%)" if whole else "")


def subagents(analysis: Analysis) -> list[Record]:
    return [record for record in analysis.records.values() if record.parent]


# Spawning -------------------------------------------------------------------------------------


def most_children_at_once(record: Record, analysis: Analysis) -> int:
    spans = [(analysis.records[key].start, analysis.records[key].end) for key in record.children]
    return max((count for _, count in concurrent(spans)), default=0)


def spawned_together(record: Record, analysis: Analysis) -> int:
    """Groups of two or more children started within TOGETHER of each other."""
    from research_pipeline.stats.analysis import TOGETHER

    starts = sorted(analysis.records[key].start for key in record.children)
    groups, size = 0, 1
    for before, after in zip(starts, starts[1:], strict=False):
        if after - before <= TOGETHER:
            size += 1
        else:
            groups, size = groups + (size >= 2), 1
    return groups + (size >= 2)


def chain(record: Record, analysis: Analysis) -> int:
    """The longest run of single children below ``record`` (each the only child of the one above)."""
    length, current = 0, record
    while len(current.children) == 1:
        length, current = length + 1, analysis.records[current.children[0]]
    return length


def links_opened(analysis: Analysis) -> tuple[int, int]:
    given = [opened for record in subagents(analysis) for _, opened in record.links]
    return sum(given), len(given)


# Library ------------------------------------------------------------------------------------


def read_before_spawning(record: Record, analysis: Analysis) -> bool | None:
    """Whether it read the library before its first spawn (None: it spawned nothing)."""
    if not record.children:
        return None
    first = min(analysis.records[key].start for key in record.children)
    return any(touch.time <= first for touch in record.library())


def others_work(record: Record) -> tuple[int, int]:
    """Its reads and runs of other agents' work (not its own, its parent's or its children's): (this phase, earlier)."""
    same = earlier = 0
    for touch in record.touches:
        if touch.kind == "agent" and touch.owner and touch.op in ("read", "run", "list", "search"):
            # Keys carry their phase ('2/fit') in 'all', and for other phases' agents in a phase's scope.
            phase = int(touch.owner.split("/", 1)[0]) if "/" in touch.owner else record.agent.phase
            if phase == record.agent.phase:
                same += 1
            else:
                earlier += 1
    return same, earlier


def shelving_lags(analysis: Analysis) -> list[float]:
    return [item.done - item.requested for item in analysis.shelving if item.done is not None]


# Checking -----------------------------------------------------------------------------------


def reviews(analysis: Analysis):
    return [review for record in analysis.records.values() for review in record.reviews]


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


# Resources ----------------------------------------------------------------------------------


def job_hours(record: Record, end: float) -> float:
    return sum(((job.ended or end) - job.started) for job in record.jobs if job.started) / 3600


def failed_jobs(record: Record) -> int:
    return sum(1 for job in record.jobs if job.status in ("failed", "timeout") or job.exit_code not in (0, None))


# Lines over time ------------------------------------------------------------------------------


def bucket(analysis: Analysis) -> float:
    """The width of a rate's time bucket: about 150 buckets over the span, at least a minute."""
    span = max(60.0, analysis.end - analysis.start)
    return max(60.0, math.ceil(span / 150 / 60) * 60)


def rate(analysis: Analysis, times: list[float]) -> Points:
    """Events per minute over time, in buckets."""
    if not times:
        return []
    width = bucket(analysis)
    counts = [0] * (int((analysis.end - analysis.start) // width) + 1)
    for time in times:
        index = int((time - analysis.start) // width)
        if 0 <= index < len(counts):
            counts[index] += 1
    return [[index * width, count * 60 / width] for index, count in enumerate(counts)]


def cumulative(analysis: Analysis, times: list[float]) -> Points:
    """How many events so far, at each event (and at the end)."""
    if not times:
        return []
    points = [[0.0, 0.0]] + [[time - analysis.start, float(index)] for index, time in enumerate(sorted(times), 1)]
    return points + [[analysis.end - analysis.start, float(len(times))]]


def open_count(analysis: Analysis, spans: list[tuple[float, float]]) -> Points:
    """How many spans are open over time."""
    points = [[0.0, 0.0]] + [[time - analysis.start, float(count)] for time, count in concurrent(spans)]
    return points + [[analysis.end - analysis.start, points[-1][1]]]


def at_work(analysis: Analysis) -> Points:
    return open_count(analysis, working(analysis.records))


def jobs_running(analysis: Analysis) -> Points:
    spans = [(job.started, job.ended or analysis.end) for record in analysis.records.values() for job in record.jobs]
    return open_count(analysis, spans)


def times(analysis: Analysis, pick: Callable[[Record], list[float]]) -> list[float]:
    return [time for record in analysis.records.values() for time in pick(record)]


#: The lines of each chart over time: (chart, line) -> how to draw it from an analysis, and whether it steps.
LINES: dict[tuple[str, str], tuple[Callable[[Analysis], Points], bool]] = {
    ("library", "entry page"): (
        lambda a: cumulative(a, times(a, lambda r: [t.time for t in r.library("library-entry")])),
        True,
    ),
    ("library", "catalogue"): (
        lambda a: cumulative(a, times(a, lambda r: [t.time for t in r.library("catalog")])),
        True,
    ),
    ("library", "Librarian's pages"): (
        lambda a: cumulative(a, times(a, lambda r: [t.time for t in r.library("library-page")])),
        True,
    ),
    ("work", "agents at work"): (at_work, True),
    ("spawns", "subagents started"): (lambda a: cumulative(a, [r.start for r in subagents(a)]), True),
    ("results", "submitted"): (lambda a: cumulative(a, times(a, lambda r: r.submissions)), True),
    ("results", "rejected"): (
        lambda a: cumulative(a, times(a, lambda r: [t for t, tool, _ in r.decisions if tool == "reject"])),
        True,
    ),
    ("review", "reads of a child's work under review"): (
        lambda a: cumulative(a, [t for v in reviews(a) for t in v.read_times]),
        True,
    ),
    ("review", "runs of a child's work under review"): (
        lambda a: cumulative(a, [t for v in reviews(a) for t in v.run_times]),
        True,
    ),
    ("calls", "tool calls"): (
        lambda a: rate(a, [e.time for r in a.records.values() for e in r.entries if e.call]),
        False,
    ),
    ("jobs", "jobs running"): (jobs_running, True),
}
