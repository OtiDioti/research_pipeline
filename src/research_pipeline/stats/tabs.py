"""The tabs of the Stats view (Library, Spawning, Checking, Resources, Comparison) and its overview strip.

Built from an :class:`~research_pipeline.stats.analysis.Analysis` and the compared
projects' analyses, with the numbers and lines of :mod:`research_pipeline.stats.figures`,
as the items agent_toolkit's Stats view draws (its docs/web-app.md, "The Stats view").
"""

from __future__ import annotations

from collections import Counter

from research_pipeline.stats import figures
from research_pipeline.stats.analysis import Analysis, Record
from research_pipeline.stats.figures import duration, share

ALL = "all"


def label(analysis: Analysis) -> str:
    return f"{analysis.name} ({'all phases' if analysis.scope == ALL else f'phase {analysis.scope}'})"


def overview(analysis: Analysis) -> list[tuple[str, str, str]]:
    """The key numbers: (label, value, note)."""
    children = figures.subagents(analysis)
    opened, given = figures.links_opened(analysis)
    reviews = figures.reviews(analysis)
    span = [value for _, value in figures.at_work(analysis)]
    return [
        ("Subagents", str(len(children)), f"deepest level {max((r.depth for r in children), default=0)}"),
        ("Most at work at once", str(int(max(span, default=0))), "agents active together"),
        (
            "Library reads",
            str(sum(len(r.library()) for r in analysis.records.values())),
            "entry page, catalogue, pages",
        ),
        ("Brief links opened", share(opened, given), "links in TASK.md the child opened"),
        (
            "Parent's files read unlinked",
            str(sum(len(r.unlinked_parent) for r in children)),
            "by children, not linked in their brief",
        ),
        ("Results rejected", share(sum(v.outcome == "reject" for v in reviews), len(reviews)), "of results submitted"),
        (
            "Reads of work under review",
            str(sum(v.reads for v in reviews)),
            f"and {sum(v.runs for v in reviews)} runs, by parents",
        ),
        ("Tool calls", str(analysis.calls), f"{sum(len(r.jobs) for r in analysis.records.values())} jobs"),
    ]


# Tabs -----------------------------------------------------------------------------------------


def _series(title: str, unit: str, chart: str, main: Analysis, others: list[Analysis], note: str = "") -> dict:
    lines = []
    for analysis in [main, *others]:
        for (name_chart, name), (draw, step) in figures.LINES.items():
            if name_chart == chart:
                lines.append(
                    {
                        "name": name,
                        "run": None if analysis is main else label(analysis),
                        "step": step,
                        "points": draw(analysis),
                    }
                )
    return {"type": "series", "title": title, "unit": unit, "note": note, "series": lines}


def _numbers(title: str, items: list[tuple[str, str]], note: str = "") -> dict:
    return {
        "type": "numbers",
        "title": title,
        "note": note,
        "items": [{"label": label, "value": value} for label, value in items],
    }


def _table(title: str, columns: list[tuple[str, str, bool]], rows: list[dict], note: str = "") -> dict:
    return {
        "type": "table",
        "title": title,
        "note": note,
        "rows": rows,
        "columns": [{"key": key, "label": label, "numeric": numeric} for key, label, numeric in columns],
    }


def yes(value: bool | None) -> str:
    return "–" if value is None else "yes" if value else "no"


def _since(record: Record, time: float | None) -> str:
    return "–" if time is None else duration(time - record.start)


def library(main: Analysis, others: list[Analysis]) -> dict:
    records = list(main.records.values())
    spawners = [r for r in records if r.children]
    briefs = [r for r in records if r.prior_work is not None]
    lags = figures.shelving_lags(main)
    same, earlier = (sum(figures.others_work(r)[index] for r in records) for index in (0, 1))
    numbers = _numbers(
        "Library use",
        [
            ("Entry page reads", str(sum(len(r.library("library-entry")) for r in records))),
            ("Catalogue reads", str(sum(len(r.library("catalog")) for r in records))),
            ("Librarian's page reads", str(sum(len(r.library("library-page")) for r in records))),
            ("Agents that never read it", share(sum(not r.library() for r in records), len(records))),
            (
                "Read it before spawning",
                share(sum(bool(figures.read_before_spawning(r, main)) for r in spawners), len(spawners)),
            ),
            ("Briefs with Prior work", share(sum(bool(r.prior_work) for r in briefs), len(briefs))),
            ("Reads of others' work", f"{same} this phase, {earlier} earlier"),
            (
                "Shelved by the Librarian",
                f"{len(lags)} of {len(main.shelving)}, median {duration(figures.median(lags))}",
            ),
        ],
    )
    rows = []
    for r in records:
        reads = r.library()
        same_r, earlier_r = figures.others_work(r)
        rows.append(
            {
                "agent": r.key,
                "role": r.agent.role,
                "entry": len(r.library("library-entry")),
                "catalog": len(r.library("catalog")),
                "pages": len(r.library("library-page")),
                "first": _since(r, min((t.time for t in reads), default=None)),
                "before": yes(figures.read_before_spawning(r, main)),
                "others": same_r + earlier_r,
                "prior": yes(r.prior_work),
            }
        )
    table = _table(
        "Per agent",
        [
            ("agent", "Agent", False),
            ("role", "Role", False),
            ("entry", "Entry page", True),
            ("catalog", "Catalogue", True),
            ("pages", "Pages", True),
            ("first", "First read after start", False),
            ("before", "Before first spawn", False),
            ("others", "Reads of others' work", True),
            ("prior", "Brief has Prior work", False),
        ],
        rows,
    )
    items = [numbers, _series("Library reads so far", "reads", "library", main, others), table]
    if main.shelving:
        items.append(
            _table(
                "Shelving",
                [("folder", "Folder", False), ("lag", "Requested to shelved", False)],
                [
                    {"folder": item.folder, "lag": duration(item.done - item.requested) if item.done else "pending"}
                    for item in main.shelving
                ],
            )
        )
    return {"id": "library", "label": "Library", "items": items}


def spawning(main: Analysis, others: list[Analysis]) -> dict:
    records = list(main.records.values())
    children = figures.subagents(main)
    opened, given = figures.links_opened(main)
    numbers = _numbers(
        "Spawning",
        [
            ("Subagents", str(len(children))),
            ("Deepest level", str(max((r.depth for r in records), default=0))),
            ("Agents with a single child", str(sum(len(r.children) == 1 for r in records))),
            ("Longest chain of single children", str(max((figures.chain(r, main) for r in records), default=0))),
            ("Most children at once", str(max((figures.most_children_at_once(r, main) for r in records), default=0))),
            ("Children spawned together", f"{sum(figures.spawned_together(r, main) for r in records)} groups"),
            ("Brief links opened", share(opened, given)),
            (
                "Parent's files read unlinked",
                f"{sum(len(r.unlinked_parent) for r in children)} "
                f"by {sum(bool(r.unlinked_parent) for r in children)} children",
            ),
            ("Messages to parents", str(sum(r.messages_to_parent for r in children))),
        ],
    )
    order = tree(main)
    timeline = {
        "type": "timeline",
        "title": "Agents over time",
        "note": "At work, idle, and their result with their parent (submitted).",
        "lanes": [
            {
                "id": r.key,
                "label": r.key,
                "depth": r.depth,
                "segments": [{"start": b - main.start, "end": e - main.start, "state": s} for b, e, s in r.segments],
            }
            for r in order
        ],
    }
    rows = [
        {
            "agent": r.key,
            "parent": r.parent or "–",
            "depth": r.depth,
            "children": len(r.children),
            "at_once": figures.most_children_at_once(r, main),
            "links": f"{sum(o for _, o in r.links)}/{len(r.links)}" if r.parent else "–",
            "unlinked": len(r.unlinked_parent),
            "messages": r.messages_to_parent,
            "lifetime": duration(r.end - r.start),
        }
        for r in order
    ]
    table = _table(
        "Per agent",
        [
            ("agent", "Agent", False),
            ("parent", "Parent", False),
            ("depth", "Level", True),
            ("children", "Children", True),
            ("at_once", "Most at once", True),
            ("links", "Brief links opened", False),
            ("unlinked", "Parent's files read unlinked", True),
            ("messages", "Messages to parent", True),
            ("lifetime", "Lifetime", False),
        ],
        rows,
    )
    return {
        "id": "spawning",
        "label": "Spawning",
        "items": [
            numbers,
            _series("Agents at work", "agents", "work", main, others),
            timeline,
            _series("Subagents started so far", "subagents", "spawns", main, others),
            _matrix(main),
            table,
        ],
    }


def _matrix(main: Analysis) -> dict:
    """Who reads or runs whose files: agents by the folders (and library, evidence) they used, their own aside."""
    counts: dict[str, dict[str, int]] = {}
    for r in main.records.values():
        for touch in r.touches:
            if touch.op == "write" or touch.kind == "own":
                continue
            column = (
                touch.owner
                if touch.owner
                else {
                    "library-entry": "library",
                    "catalog": "library",
                    "library-page": "library",
                    "evidence": "starting evidence",
                }.get(touch.kind)
            )
            if column:
                row = counts.setdefault(r.key, {})
                row[column] = row.get(column, 0) + 1
    rows = [r.key for r in tree(main) if counts.get(r.key)]
    used = {column for row in counts.values() for column in row}
    columns = [c for c in ["library", "starting evidence"] if c in used] + [r.key for r in tree(main) if r.key in used]
    columns += sorted(used - set(columns))
    return {
        "type": "matrix",
        "title": "Who reads or runs whose files",
        "unit": "accesses",
        "note": "Rows: the agent reading or running; columns: whose files. Own files aside.",
        "rows": rows,
        "columns": columns,
        "values": [[counts[row].get(column, 0) for column in columns] for row in rows],
    }


def checking(main: Analysis, others: list[Analysis]) -> dict:
    reviews = figures.reviews(main)
    decided = [v for v in reviews if v.decided is not None]
    numbers = _numbers(
        "Results and their review",
        [
            ("Results submitted", str(len(reviews))),
            ("Accepted", str(sum(v.outcome == "accept" for v in reviews))),
            ("Rejected", share(sum(v.outcome == "reject" for v in reviews), len(reviews))),
            ("Waiting for a decision", str(sum(v.outcome == "pending" for v in reviews))),
            (
                "Median time to decide",
                duration(figures.median([(v.decided or v.submitted) - v.submitted for v in decided])),
            ),
            ("Median reads of the work per review", str(figures.median([v.reads for v in reviews]) or 0)),
            ("Reviews that ran the child's work", share(sum(v.runs > 0 for v in reviews), len(reviews))),
            (
                "Reviewer rounds",
                ", ".join(
                    f"phase {p.number}: {p.rounds}" + (f" ({p.verdict})" if p.verdict else "") for p in main.phases
                ),
            ),
        ],
        note="A review: from a child's submission to its parent's decision. "
        "Reads of RESULT.md, TASK.md and the protocol's files are not counted.",
    )
    rows = [
        {
            "agent": v.child,
            "parent": parent.key,
            "submitted": duration(v.submitted - main.start),
            "decided": duration(v.decided - v.submitted) if v.decided else "–",
            "outcome": v.outcome,
            "reads": v.reads,
            "runs": v.runs,
            "files": len(v.files),
        }
        for parent in main.records.values()
        for v in parent.reviews
    ]
    table = _table(
        "Each result",
        [
            ("agent", "Child", False),
            ("parent", "Parent", False),
            ("submitted", "Submitted at", False),
            ("decided", "Decided after", False),
            ("outcome", "Outcome", False),
            ("reads", "Parent's reads", True),
            ("runs", "Parent's runs", True),
            ("files", "Files looked at", True),
        ],
        rows,
    )
    parents = [r for r in main.records.values() if r.reviews]
    bars = {
        "type": "bars",
        "title": "What each parent read and ran of work under review",
        "unit": "accesses",
        "note": "",
        "categories": [r.key for r in parents],
        "series": [
            {"name": "reads", "values": [sum(v.reads for v in r.reviews) for r in parents]},
            {"name": "runs", "values": [sum(v.runs for v in r.reviews) for r in parents]},
        ],
    }
    return {
        "id": "checking",
        "label": "Checking",
        "items": [
            numbers,
            _series("Results so far", "results", "results", main, others),
            _series("Parents' accesses to work under review so far", "accesses", "review", main, others),
            bars,
            table,
        ],
    }


def resources(main: Analysis, others: list[Analysis]) -> dict:
    records = list(main.records.values())
    tools = sum((r.tools for r in records), start=Counter())
    numbers = _numbers(
        "Resources",
        [
            ("Tool calls", str(main.calls)),
            ("Shell commands", str(tools.get("shell", 0))),
            ("File reads (Claude Code)", str(tools.get("read", 0))),
            ("Edits", str(tools.get("edit", 0))),
            ("Web searches", str(tools.get("web", 0))),
            ("Research tools", str(tools.get("research", 0))),
            ("Jobs", f"{sum(len(r.jobs) for r in records)}, {sum(figures.failed_jobs(r) for r in records)} failed"),
            ("Job hours", f"{sum(figures.job_hours(r, main.end) for r in records):.1f}"),
            ("Handoffs", str(sum(max(0, r.agent.sessions - 1) for r in records))),
        ],
    )
    models = sorted({f"{r.agent.backend}:{r.agent.model}" for r in records})
    bars = {
        "type": "bars",
        "title": "By model",
        "unit": "",
        "note": "",
        "categories": models,
        "series": [
            {
                "name": "agents",
                "values": [sum(f"{r.agent.backend}:{r.agent.model}" == m for r in records) for m in models],
            },
            {
                "name": "tool calls (hundreds)",
                "values": [
                    round(
                        sum(sum(r.tools.values()) for r in records if f"{r.agent.backend}:{r.agent.model}" == m) / 100,
                        1,
                    )
                    for m in models
                ],
            },
        ],
    }
    rows = [
        {
            "agent": r.key,
            "model": f"{r.agent.backend}:{r.agent.model}",
            "calls": sum(r.tools.values()),
            "shell": r.tools.get("shell", 0),
            "edits": r.tools.get("edit", 0),
            "web": r.tools.get("web", 0),
            "jobs": len(r.jobs),
            "hours": round(figures.job_hours(r, main.end), 2),
            "sessions": r.agent.sessions,
            "context": f"{round(100 * r.max_fill)}%" if r.max_fill is not None else "–",
        }
        for r in tree(main)
    ]
    table = _table(
        "Per agent",
        [
            ("agent", "Agent", False),
            ("model", "Model", False),
            ("calls", "Tool calls", True),
            ("shell", "Shell", True),
            ("edits", "Edits", True),
            ("web", "Web", True),
            ("jobs", "Jobs", True),
            ("hours", "Job hours", True),
            ("sessions", "Sessions", True),
            ("context", "Most context used", False),
        ],
        rows,
    )
    return {
        "id": "resources",
        "label": "Resources",
        "items": [
            numbers,
            _series("Tool calls", "per min", "calls", main, others),
            _series("Jobs running", "jobs", "jobs", main, others),
            bars,
            table,
        ],
    }


def comparison(main: Analysis, others: list[Analysis]) -> dict:
    table = [overview(analysis) for analysis in [main, *others]]
    columns = [("metric", "", False)] + [(f"run{i}", label(a), False) for i, a in enumerate([main, *others])]
    rows = [
        {"metric": label, **{f"run{i}": numbers[index][1] for i, numbers in enumerate(table)}}
        for index, (label, _, _) in enumerate(table[0])
    ]
    return {"id": "comparison", "label": "Comparison", "items": [_table("Key numbers", columns, rows)]}


def tree(analysis: Analysis) -> list[Record]:
    """The records in tree order: each agent followed by its children, by start."""
    found: list[Record] = []

    def visit(record: Record) -> None:
        found.append(record)
        for key in sorted(record.children, key=lambda key: analysis.records[key].start):
            visit(analysis.records[key])

    for root in sorted(
        (r for r in analysis.records.values() if r.parent not in analysis.records), key=lambda r: r.start
    ):
        visit(root)
    return found
