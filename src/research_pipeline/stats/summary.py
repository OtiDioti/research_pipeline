"""The terminal summary of ``research-pipeline stats``: the Stats view's key numbers, as text."""

from __future__ import annotations

from research_pipeline.stats.view import Statistics


def summary(statistics: Statistics, scope: str | None) -> str:
    """The key numbers of ``scope`` (None: the latest phase): the overview, then each tab's numbers."""
    view = statistics.describe(scope, [])
    lines = [view["title"], "=" * len(view["title"]), *view["notes"], ""]
    lines += _rows([(item["label"], item["value"], item.get("note", "")) for item in view["overview"]])
    for tab in view["tabs"]:
        for item in tab["items"]:
            if item["type"] == "numbers":
                lines += ["", f"{tab['label']}: {item['title']}", "-" * (len(tab["label"]) + len(item["title"]) + 2)]
                lines += _rows([(entry["label"], entry["value"], "") for entry in item["items"]])
    return "\n".join(lines) + "\n"


def _rows(rows: list[tuple[str, str, str]]) -> list[str]:
    width = max((len(label) for label, _, _ in rows), default=0)
    return [f"  {label.ljust(width)}  {value}" + (f"  ({note})" if note else "") for label, value, note in rows]
