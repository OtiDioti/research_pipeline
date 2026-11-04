"""Independent complete passive declarations and stdlib-only wire/count oracles."""

import copy
import hashlib
import json

from research_pipeline.domain import ArtifactReference, RecordReference
from research_pipeline.resources import Dimension
from research_pipeline.work_product import WorkProductFile


SCIENCE = {
    "equations_or_transformations": ["y = a*x + b; no fit is performed."],
    "units": ["x and y have unit metre; a is dimensionless and b has unit metre."],
    "conventions": ["Column vectors; input order is retained."],
    "input_domains": ["Finite real x only; interface float64 is an authored label."],
    "output_domains": ["Finite real y if no overflow occurs."],
    "parameter_regimes": ["No small-parameter assumption; |a*x+b| must fit the format."],
    "boundary_conditions": ["No spatial boundary value problem is solved."],
    "approximations": ["Binary64 roundoff is expected; no interval guarantee."],
    "error_claims": ["No certified numerical error bound is reported."],
    "success_meaning": ["Returning y reports a transformation, not scientific support."],
    "failure_conditions": ["Nonfinite inputs or overflow invalidate this declared use."],
}
UNITS = {
    "local_time": "nanosecond", "local_compute": "cpu_nanosecond", "local_storage": "byte",
    "model_input_tokens": "token", "model_output_tokens": "token", "model_calls": "call",
    "tool_calls": "call", "memory_bytes": "byte", "output_bytes": "byte",
    "context_capacity_tokens": "token", "per_call_output_tokens": "token",
    "model_concurrency": "concurrent_call", "descendant_jobs": "job", "retries": "retry", "repairs": "repair",
}
RECORD_SLOTS = (
    ("identity", "provenance_records"), ("identity", "implementation", "source_records"),
    ("effects_authority", "child_tools"), ("evidence_limitations", "qualification_reports"),
    ("evidence_limitations", "evidence"), ("evidence_limitations", "issues"),
    ("reproducibility", "dependency_records"),
)
ARTIFACT_SLOTS = (("evidence_limitations", "self_tests"), ("reproducibility", "dependency_artifacts"))
FILE_SLOTS = (("identity", "implementation", "artifacts"), ("invocation", "adapter", "files"))
SECTION_NAMES = ("identity", "invocation", "scientific_meaning", "effects_authority",
                 "resources_recovery", "evidence_limitations", "reproducibility")


def known(value):
    """Declare an explicit known value, including zero, empty collections and optional null."""
    return {"state": "known", "value": value, "reason": None}


def missing(state="unknown", reason="The supplier did not report this fact."):
    """Declare why a fact is unknown or unavailable without substituting an empty value."""
    return {"state": state, "value": None, "reason": reason}


def artifact(data=b"synthetic affine implementation\n"):
    """Specify a synthetic byte identity directly with hashlib, without a file or execution."""
    return {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}


def record(role, kind, name=None):
    """Specify an exact revision and explicit role/kind independently of product serializers."""
    return {"record_id": name or role, "revision": 3, "relationship": role, "target_kind": kind}


def activity(state="none"):
    """Describe optional activity; maxima elsewhere do not assert that activity occurred."""
    return {"state": state, "runtime": known(""), "providers": known([]),
            "description": known("No inner activity is reported."), "visibility": "complete",
            "limitations": known(["This declaration is not a usage receipt."])}


def parameter(name):
    """Provide a compact inert interface with an authored numerical type label."""
    return {"name": name, "type": "float64", "shape": known(["N rows"]), "presence": "required",
            "description": known("Ordered measured coordinates in metres."), "artifact_conventions": known(["UTF-8 decimal rows"])}


def sections(origin="researcher_supplied", kind="local_program"):
    """Build all seven complete wire sections with substantive, independent declarations."""
    implementation = {
        "identity": known("synthetic affine transform"), "reported_version": known("example-1"),
        "artifacts": known([{"path": "src/affine.py", "artifact": artifact()}]),
        "source_records": known([record("implementation_source", "source")]),
        "observability": "pinned_local", "limitations": known(["Synthetic bytes have not been executed or qualified."]),
    }
    adapter = {
        "adapter_id": "affine_adapter", "version": known("adapter-1"),
        "description": known("Descriptive adapter for affine rows."),
        "files": known([{"path": "src/adapter.py", "artifact": artifact(b"inert adapter\n")}]),
        "entry_file": known("src/adapter.py"), "entry_point": known("python src/adapter.py --input rows.txt"),
    }
    bounds = []
    for index, (name, unit) in enumerate(UNITS.items()):
        dimension = {"dimension_id": "dim_" + name, "kind": name, "unit": unit, "currency": None, "scale": 1} if index < 7 else None
        bounds.append({"name": name, "dimension": dimension, "unit": unit,
                       "quantity": known(0 if index >= 3 else 100), "mode": "claimed_hard",
                       "enforceability": "unknown", "mechanism": missing(),
                       "limitations": known(["Unverified maximum; no resource has been allocated."])})
    result = {
        "identity": {
            "tool_id": "affine_tool", "display_name": "Affine example α 😀", "release_label": known(" v1 "),
            "origin": origin, "supplier": known(["Researcher Ada"]), "developer": known(["Example author"]),
            "declared_by": known("Researcher Ada"), "declared_at": known("2026-10-30T12:00:00Z"),
            "provenance_records": known([record("reported_provenance", "work_product_manifest")]),
            "access": {"status": "available", "detail": "Bytes are described in memory only; availability is not tested."},
            "license": known("Example text may be reused; no third-party license is asserted."),
            "implementation": implementation,
            "readme": "# Affine release\nIdentity: synthetic researcher-supplied transform.\nInvocation: ordered rows via a descriptive adapter.\nScience: y=a*x+b in metres, with binary64 roundoff.\nEffects: local input/output only as reported.\nResources: unverified per-invocation maxima; no allocation.\nEvidence: example links are unauthenticated.\nReproducibility: local byte identities do not prove execution.\n<script>inert()</script> https://example.invalid/ $(touch sentinel)",
        },
        "invocation": {"kind": kind, "adapter": adapter, "configuration": known([{"name": "offset", "value": "0"}, {"name": "annotation", "value": ""}]),
                       "inputs": {"description": known("Input coordinates."), "fields": known([parameter("x")])},
                       "outputs": {"description": known("Transformed coordinates."), "fields": known([parameter("y")])},
                       "artifact_conventions": known(["Preserve exact row order."]), "mode": "synchronous", "mode_detail": known("One result per invocation."),
                       "environment_requirements": known(["A separately verified Python environment would be needed."])},
        "scientific_meaning": {name: known(value.copy()) for name, value in SCIENCE.items()},
        "effects_authority": {
            "filesystem_read": known(["selected input rows; ../descriptive-only"]),
            "filesystem_write": known(["selected output destination"]), "network_destinations": known([]),
            "credential_references": known([]), "external_effects": known([]), "child_tools": known([]),
            "model_activity": activity(), "delegated_activity": activity(),
            "delegation_contract": {name: known("") for name in ("assignment", "input_artifacts_and_context", "acceptance_criteria", "deliverables", "descendant_scope", "backend_state_and_run_identity", "waiting_parent_behavior")},
        },
        "resources_recovery": {"bounds": bounds,
            "recovery": {"cancellation": missing(), "checkpointing": known("No checkpoint protocol is reported."), "replay_safety": "conditional",
                         "replay_conditions": known("Use exact inputs and a fresh output destination."), "uncertain_completion": known("Retain liability pending authoritative reconciliation."),
                         "descendant_cancellation": known("No descendants are declared; this does not certify termination."), "reconciliation": missing("unavailable", "No runtime receipt exists in this passive example.")},
            "nested_accounting": {"basis": "exclusive", "visibility": "complete", "limitations": known(["No actual usage was measured."])}},
        "evidence_limitations": {
            "intended_uses": known(["Illustrate an affine transformation contract."]),
            "reported_qualified_applicability": known(["Author reports only synthetic example applicability; no independent qualification."]),
            "qualification_reports": known([record("reported_qualification", "tool_assessment")]),
            "self_tests": known([artifact(b"synthetic test description")]), "evidence": known([record("reported_evidence", "evidence")]),
            "issues": known([record("reported_issue", "issue")]), "tested_environments": missing(),
            "tested_cases": known(["No executed case is asserted; this is a declaration fixture."]),
            "known_failures": known(["Overflow lies outside the declared output domain."]), "limitations": known(["No scientific inference or support promotion."]),
        },
        "reproducibility": {"dependencies": known([]), "dependency_artifacts": known([]), "dependency_records": known([]),
                            "environment": known(["No environment was inspected."]), "determinism": "conditional", "randomness": known([]),
                            "output_provenance": known(["A future receipt must link exact input and output bytes."]),
                            "replay_limits": known(["Exact environment and authentic execution remain unverified."])},
    }
    if kind == "remote_service":
        result["identity"]["access"] = {"status": "unavailable", "detail": "The endpoint is inaccessible to this example."}
        result["identity"]["license"] = missing("unavailable", "Service license terms could not be obtained.")
        implementation.update(artifacts=missing("unavailable", "The remote implementation bytes cannot be obtained."), observability="opaque",
                              limitations=known(["Reported version does not pin the running remote service."]))
        result["invocation"]["adapter"]["entry_point"] = known("POST https://example.invalid/affine")
        result["effects_authority"]["network_destinations"] = known(["https://example.invalid/affine"])
        result["effects_authority"]["credential_references"] = known([{"credential_id": "service_access", "purpose": "Future separately authorized access."}])
        result["reproducibility"]["replay_limits"] = known(["Access is unavailable; the provider may change the implementation or reported version."])
        result["identity"]["readme"] = "# Opaque remote affine service\nIdentity: reported example-1; inaccessible and license unavailable.\nInvocation: descriptive HTTP client only; adapter bytes do not pin the service.\nScience: claimed affine transformation, not verified remotely.\nEffects: network access would need separate permission and credential lookup.\nResources: unverified maxima and uncertain-completion liability.\nEvidence: unauthenticated reported links cannot qualify the service.\nReproducibility: provider versions, access and replay can change."
    if kind == "composite_workflow":
        for name in ("model_activity", "delegated_activity"):
            result["effects_authority"][name].update(state="declared", runtime=known("descriptive_runtime"), providers=known(["unspecified_provider"]), visibility="partial")
        result["effects_authority"]["child_tools"] = known([record("child_tool", "tool_release")])
        result["effects_authority"]["delegation_contract"] = {name: known(text) for name, text in zip(result["effects_authority"]["delegation_contract"], (
            "Expected bounded affine analysis only.", "Exact input artifact IDs and context revision are required.",
            "Return the requested output with explicit failure details.", "An exact work-product revision and artifact hashes are expected.",
            "No descendants beyond the declared scope.", "Backend owns run identity and state; this manifest is not a job.",
            "Waiting parent checkpoints and yields its slot while retaining liability."))}
    return result


def canonical(value):
    """Independently encode expected bytes using the specified standard-library options."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def rehash(value):
    """Recompute expected hash preimages independently, even for semantic-negative fixtures."""
    result = copy.deepcopy(value)
    for key, child in (("adapter_identity", result["invocation"]["adapter"]), ("configuration_identity", result["invocation"]["configuration"])):
        result[key] = "sha256:" + hashlib.sha256(canonical(child).encode("ascii")).hexdigest()
    result.pop("release_id", None)
    result["release_id"] = "sha256:" + hashlib.sha256(canonical(result).encode("ascii")).hexdigest()
    return result


def wire(origin="researcher_supplied", kind="local_program"):
    """Specify the complete expected wire document without any production serializer."""
    return rehash({"format": "research_pipeline.tool_release_content", "version": 1, "kind": "tool_release", **sections(origin, kind)})


def at(value, path):
    """Select a fixture slot for isolated mutations or typed conversion."""
    for key in path:
        value = value[key]
    return value


def constructor_sections(value=None):
    """Convert only declared typed slots using direct constructors, preserving all other fields."""
    result = copy.deepcopy(sections() if value is None else {name: value[name] for name in SECTION_NAMES})
    for paths, cls in ((RECORD_SLOTS, RecordReference), (ARTIFACT_SLOTS, ArtifactReference)):
        for path in paths:
            fact = at(result, path)
            if fact["state"] == "known":
                fact["value"] = [cls(**item) for item in fact["value"]]
    for path in FILE_SLOTS:
        fact = at(result, path)
        if fact["state"] == "known":
            fact["value"] = [WorkProductFile(item["path"], ArtifactReference(**item["artifact"])) for item in fact["value"]]
    for bound in result["resources_recovery"]["bounds"]:
        if bound["dimension"] is not None:
            bound["dimension"] = Dimension(**bound["dimension"])
    return result


def requirements(value, text=None):
    """Independently measure exact complete wire occurrences and path-prefix workload."""
    result = {"max_wire_bytes": len((canonical(value) if text is None else text).encode("utf-8")),
              "max_canonical_bytes": len(canonical(value)), "max_string_chars": 0,
              "max_collection_items": 0, "max_references": 0, "max_nodes": 0,
              "max_depth": 0, "max_reconstruction_units": 0}

    def visit(item, depth):
        """Count repeated key/scalar/container occurrences directly in the expected tree."""
        result["max_nodes"] += 1
        result["max_reconstruction_units"] += 1
        if isinstance(item, str):
            result["max_string_chars"] = max(result["max_string_chars"], len(item))
            result["max_reconstruction_units"] += len(item)
        if isinstance(item, (dict, list)):
            result["max_depth"] = max(result["max_depth"], depth)
            result["max_collection_items"] = max(result["max_collection_items"], len(item))
            if isinstance(item, dict):
                for key, child in item.items():
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
    visit(value, 1)
    for path in RECORD_SLOTS + ARTIFACT_SLOTS + FILE_SLOTS:
        fact = at(value, path)
        if fact["state"] == "known":
            result["max_references"] += len(fact["value"])
    paths = []
    for path in FILE_SLOTS:
        fact = at(value, path)
        if fact["state"] == "known":
            paths.extend(item["path"] for item in fact["value"])
    fact = value["invocation"]["adapter"]["entry_file"]
    if fact["state"] == "known" and fact["value"] is not None:
        paths.append(fact["value"])
    for path in paths:
        count = len(path.split("/"))
        result["max_reconstruction_units"] += count * (count + 1) // 2
    return result
