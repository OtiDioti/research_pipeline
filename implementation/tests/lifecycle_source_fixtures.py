"""Real disposable lifecycle source state and explicit independent processing budgets."""

from research_pipeline import lifecycle_report_source as source
from tests import run_control_fixtures as control, lifecycle_binding_fixtures as binding

LIMITS = source.LifecycleSourceLimits(control=control.LIMITS, binding=binding.LIMITS,
    scientific=source.LifecycleScientificCaptureLimits(max_roots=1000, max_records=10000,
        max_references=100000, max_record_bytes=8*1024*1024, max_metadata_bytes=64*1024*1024,
        max_artifacts=10000, max_file_bytes=64*1024*1024, max_total_bytes=128*1024*1024,
        max_work_bytes=8*1024**3),
    resources=source.LifecycleResourceCaptureLimits(max_accounts=10000, max_operations=10000,
        max_rows=100000, max_references=100000, max_record_bytes=8*1024*1024,
        max_metadata_bytes=64*1024*1024, max_result_bytes=64*1024*1024, max_work_bytes=2**63-1),
    max_artifacts=10000, max_artifact_bytes=64*1024*1024, max_artifact_total_bytes=256*1024*1024,
    max_input_bytes=64*1024*1024, max_source_bytes=64*1024*1024, max_submission_bytes=64*1024*1024,
    max_result_bytes=64*1024*1024, max_work_bytes=8*1024**3, max_nodes=1048576, max_depth=96)


def populate(store):
    """Commit real original preparation with explicitly empty scientific report selection."""
    request = control.populate(store)
    value = request.to_dict()
    value['report']['selection'] = []
    value['report']['declarations']['results'] = []
    value['report']['declarations']['completed_checks'] = []
    value['report']['declarations']['unresolved_issues'] = []
    value['report']['declarations']['saved_work'] = []
    value['report']['declarations']['outstanding_jobs'] = []
    from research_pipeline.run_control import RunControlRequest
    request = RunControlRequest(value)
    result = control.commit(store, request)
    return request, result


def commit(store, operation='prepare', *, limits=LIMITS):
    """Resolve the verified persisted binding digest and commit using the original control ID."""
    inspection = store.inspect_lifecycle_source(operation, limits=limits).to_dict(limits=limits)
    return store.commit_lifecycle_source(operation, expected_binding_digest=inspection['binding_digest'], limits=limits)
