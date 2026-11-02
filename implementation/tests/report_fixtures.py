"""Bounded synthetic report declarations without admission or operational authority."""

from research_pipeline.domain import RecordReference
from research_pipeline.reports import ReportRequest, unavailable
from tests.test_store import record, request, CONTROLLER
from tests.snapshot_fixtures import limits
from tests.resource_fixtures import LIMITS


def ref(identity, kind, role="report_selection", revision=1):
    """Construct a complete exact report pin with an explicit role."""
    return RecordReference(identity, revision, role, kind).to_dict()


def text(value=None, reason="No authored assessment was supplied."):
    """Declare attributed text or an explicit unknown without inventing an author."""
    return {"text": {"value": value, "unknown_reason": reason if value is None else None},
            "attribution": {"value": "Synthetic author", "unknown_reason": None}}


def report_request(operation="report_initial", revision=1, **updates):
    """Build a complete setup report with explicit budgets and unavailable optional knowledge."""
    unknown = unavailable("Not recorded for this synthetic setup observation.")
    declaration = {"objective": text("Inspect saved state"), "scope": text("Explicit bounded selection"),
                   "outcome": {"label": "not_yet_assessed", "explanation": unknown,
                               "attribution": {"value": "Synthetic author", "unknown_reason": None}},
                   "interpretation": text(), "stop_reason": text(), "results": [], "completed_checks": [],
                   "unresolved_issues": [], "saved_work": [], "outstanding_jobs": [], "gaps": [],
                   "continuation": unknown, "reproduction": {key: text() for key in ("procedure", "build", "environment")},
                   "limitations": [text("Synthetic data only") ]}
    return ReportRequest({"format": "research_pipeline.report_request", "version": 1,
        "operation_id": operation, "report_revision": revision, "provenance": CONTROLLER.to_dict(),
        "authors": ["Synthetic author"], "project": ref("project", "project", "project"),
        "run": ref("run", "run", "run"), "context": unknown, "selection": [], "start_baseline": unknown,
        "declarations": declaration,
        "limits": {"snapshot": limits(max_roots=2000, max_records=2000, max_references=10000,
                    max_record_bytes=4_000_000, max_metadata_bytes=30_000_000, max_artifacts=2000,
                    max_files=2000, max_file_bytes=30_000_000, max_total_bytes=60_000_000).to_dict(),
                   "resources": vars(LIMITS), "max_source_bytes": 30_000_000,
                   "max_output_file_bytes": 30_000_000, "max_output_total_bytes": 60_000_000}, **updates})


def populate(store):
    """Commit a generic project and exact project-linked run, without operational claims."""
    return store.submit(request("report_scopes", [record("project", kind="project"),
        record("run", kind="run", record_references=[RecordReference("project", 1, "project", "project")])]))
