"""The Stats view of a research project (agent_toolkit's ``Dashboard.stats``), and its scopes and comparisons.

:class:`Statistics` keeps each project it reads (this one, and those compared) and
refreshes it incrementally at each call, so the web page can ask every few seconds.
The description follows docs/web-app.md of agent_toolkit ("The Stats view"): notes on
the numbers' precision, an overview strip, the tabs (:mod:`research_pipeline.stats.tabs`)
and a card per agent.
"""

from __future__ import annotations

import threading
from pathlib import Path

from research_pipeline.stats import figures
from research_pipeline.stats.analysis import Analysis, Record, analyse
from research_pipeline.stats.figures import duration
from research_pipeline.stats.sources import Source, projects_beside
from research_pipeline.stats.tabs import ALL, checking, comparison, label, library, overview, resources, spawning, yes


class Statistics:
    """The statistics of the project at ``root``, compared with others on request."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self._sources: dict[Path, Source] = {}
        # The web app computes off its event loop: a page's request may overlap a refresh of the same sources.
        self._lock = threading.Lock()

    def source(self, folder: Path | str) -> Source:
        path = Path(folder).expanduser().resolve()
        if path not in self._sources:
            self._sources[path] = Source(path)
        source = self._sources[path]
        source.refresh()
        return source

    def scopes(self) -> list[dict]:
        source = self.source(self.root)
        phases = [
            {"id": str(n), "label": f"Phase {n}" + (f": {p.title}" if p.title else "")}
            for n, p in sorted(source.phases.items())
        ]
        return phases + [{"id": ALL, "label": "All phases"}]

    def analyse(self, scope: str | None, compare: list[str]) -> tuple[Analysis, list[Analysis]]:
        """This project's ``scope`` (None: its latest phase) and the compared projects' matching scopes."""
        source = self.source(self.root)
        if not source.phases:
            raise ValueError("no phase has started yet")
        scope = scope or str(max(source.phases))
        if scope != ALL and (not scope.isdigit() or int(scope) not in source.phases):
            raise ValueError(f"there is no phase {scope}")
        others = []
        for folder in compare:
            other = self.source(folder)
            if not other.phases:
                raise ValueError(f"{other.name} has no phase yet")
            matching = scope if scope == ALL or int(scope) in other.phases else str(max(other.phases))
            others.append(analyse(other, matching))
        return analyse(source, scope), others

    def describe(self, scope: str | None, compare: list[str]) -> dict:
        """The Stats view's description."""
        with self._lock:
            return self._describe(scope, compare)

    def _describe(self, scope: str | None, compare: list[str]) -> dict:
        main, others = self.analyse(scope, compare)
        tabs = [library(main, others), spawning(main, others), checking(main, others), resources(main, others)]
        if others:
            tabs.insert(0, comparison(main, others))
        return {
            "title": f"{main.name}: " + ("all phases" if main.scope == ALL else f"phase {main.scope}"),
            "scope": main.scope,
            "scopes": self.scopes(),
            "sources": [{"path": str(path), "label": path.name} for path in projects_beside(self.root)],
            "compare": [str(Path(folder).expanduser().resolve()) for folder in compare],
            "start": main.start,
            "notes": notes(main) + [f"Compared: {label(other)}." for other in others],
            "overview": [{"label": label, "value": value, "note": note} for label, value, note in overview(main)],
            "tabs": tabs,
            "agents": {key: card(record, main) for key, record in main.records.items()},
        }


def notes(analysis: Analysis) -> list[str]:
    """What the reader should know about the numbers' precision."""
    found = [
        "Times are counted from the start of what is shown. Gaps of over 10 minutes without activity show as idle."
    ]
    cut = analysis.share("cut")
    if cut:
        found.append(
            f"Approximate: {round(100 * cut)}% of the tool calls were recorded only in part (runs before the "
            "activity log kept whole calls), so file accesses are undercounted."
        )
    unparsed = analysis.share("unparsed")
    if unparsed:
        found.append(f"{round(100 * unparsed)}% of the tool calls include a command no rule recognises.")
    return found


# Agent cards ----------------------------------------------------------------------------------


def card(record: Record, analysis: Analysis) -> dict:
    agent = record.agent
    same, earlier = figures.others_work(record)
    sections = [
        {
            "title": "Agent",
            "rows": [
                ["Role", agent.role],
                ["Parent", record.parent or "–"],
                ["Model", f"{agent.backend}:{agent.model}"],
                ["Status", agent.status],
                ["Started", duration(record.start - analysis.start) + " after the start"],
                ["Lifetime", duration(record.end - record.start)],
                ["Sessions", str(agent.sessions)],
            ],
        },
        {
            "title": "Library",
            "rows": [
                ["Entry page reads", str(len(record.library("library-entry")))],
                ["Catalogue reads", str(len(record.library("catalog")))],
                ["Librarian's page reads", str(len(record.library("library-page")))],
                ["Read before its first spawn", yes(figures.read_before_spawning(record, analysis))],
                ["Reads of others' work", f"{same} this phase, {earlier} earlier"],
            ],
        },
    ]
    if record.parent:
        brief = [["Prior work section", yes(record.prior_work)]]
        brief += [[path, "opened" if opened else "not opened"] for path, opened in record.links]
        sections.append({"title": "Its brief's links", "rows": brief})
        unlinked = [[path, "read, not linked"] for path in record.unlinked_parent[:30]]
        if len(record.unlinked_parent) > 30:
            unlinked.append(["…", f"{len(record.unlinked_parent) - 30} more"])
        sections.append({"title": "Its parent's files it read without a link", "rows": unlinked or [["None", ""]]})
        sections.append(
            {
                "title": "Its results",
                "rows": [
                    ["Submitted", str(len(record.submissions))],
                    ["Rejected", str(agent.rejections)],
                    ["Messages to its parent", str(record.messages_to_parent)],
                ],
            }
        )
    if record.children:
        sections.append(
            {
                "title": "Its children",
                "rows": [
                    ["Children", ", ".join(record.children)],
                    ["Most at once", str(figures.most_children_at_once(record, analysis))],
                    ["Spawned together", f"{figures.spawned_together(record, analysis)} groups"],
                ]
                + [[f"Review of {v.child}", f"{v.outcome}, {v.reads} reads, {v.runs} runs"] for v in record.reviews],
            }
        )
    sections.append(
        {
            "title": "Resources",
            "rows": [
                ["Tool calls", ", ".join(f"{kind} {count}" for kind, count in record.tools.most_common()) or "none"],
                [
                    "Jobs",
                    f"{len(record.jobs)} ({figures.failed_jobs(record)} failed), "
                    f"{figures.job_hours(record, analysis.end):.2f} h",
                ],
                ["Most context used", f"{round(100 * record.max_fill)}%" if record.max_fill is not None else "–"],
                ["Recorded only in part", f"{record.cut} calls"],
            ],
        }
    )
    return {"label": f"{record.key} ({agent.role})", "sections": sections}
