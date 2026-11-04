"""Independent synthetic assessment declarations, projection oracles and accounting."""

from copy import deepcopy
from dataclasses import fields
import hashlib
import json

from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordReference
from research_pipeline.tool_assessment import ToolAssessment


DIMENSIONS = ("operational_interface", "software_behavior", "scientific_applicability")
PROSE = '  ∫₀¹ x² dx = 1/3; 😀\x7f\n<script>text</script> $(echo inert) https://example.invalid/a?q=1  '


def known(value):
    """Create an independent explicit known fact, preserving its payload literally."""
    return {"state": "known", "value": value, "reason": None}


def missing(state="unknown", reason="The reporter supplied no observation."):
    """Create reasoned missing information rather than inferring an empty report."""
    return {"state": state, "value": None, "reason": reason}


def attribution(actor="Synthetic assessor"):
    """Describe reported authorship and retain authored timestamp precision."""
    return {"actor": known(actor), "reported_at": known("2026-10-30T12:34:56.12Z"), "origin": "synthetic"}


def independence():
    """Report mismatched requested/actual visibility and explicit shared exposure."""
    return {"requested_mode": known("proof_blind_reconstruction"),
            "reported_mode": known("candidate_aware_audit"),
            "shared_formulation": known(["Same supplied equation; no independent derivation."]),
            "shared_sources": missing(), "shared_lemmas": known([]),
            "shared_method": known(["Shared quadrature method."]),
            "shared_implementation": known(["Same builder implementation was visible."]),
            "shared_communications": missing("unavailable", "Earlier communications were not retained."),
            "limitations": known(["Exposure prevents a blindness claim."])}


def record(name, role, kind, revision=2):
    """State a complete exact wire pin without product serializers."""
    return {"record_id": name, "revision": revision, "relationship": role, "target_kind": kind}


def artifact(name):
    """Hash inert in-memory synthetic bytes, returning an independent wire pin."""
    data = (name + "\n").encode("utf-8")
    return {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}


def evidence(name, basis="assessor_assertion"):
    """Build separately attributed evidence with supplied pins and unknown liabilities."""
    roles = {"assessor_assertion": ("reported_assertion", "source"),
             "builder_self_test": ("builder_self_test", "work_product_manifest"),
             "reported_tool_execution": ("reported_tool_execution", "tool_execution"),
             "independent_review": ("independent_review", "review")}
    role, kind = roles[basis]
    return {"basis": basis, "attribution": attribution(name + " reporter"),
            "statement": known(PROSE), "records": known([record(name, role, kind)]),
            "artifacts": known([artifact(name)]), "resource_usage": missing(),
            "unresolved_liabilities": missing("unavailable", "No authentic usage ledger was supplied."),
            "independence": independence(), "limitations": known(["This is a supplied report, not an authentic receipt."])}


def report(name, outcome, role):
    """Build a qualification-like decision report with explicit scope and evidence."""
    return {"outcome": outcome, "attribution": attribution(name), "scope": known(["x ∈ [0,1]; dimensionless"]),
            "rationale": known("Supplied scoped assessment: " + outcome),
            "decisions": known([record(name + "_decision", role, "decision")]),
            "evidence": known([evidence(name + "_evidence")]), "limitations": missing()}


def wire(scientific="fail"):
    """Build a substantive complete declaration with every reference/artifact slot populated."""
    checks = []
    for name, dimension, basis, outcome in (
            ("interface", "operational_interface", "builder_self_test", "pass"),
            ("software", "software_behavior", "reported_tool_execution", "pass"),
            ("science", "scientific_applicability", "assessor_assertion", scientific),
            ("audit", "scientific_applicability", "independent_review", "inconclusive")):
        checks.append({"check_id": name, "dimension": dimension, "basis": basis,
                       "attribution": attribution(name + " checker"), "outcome": outcome,
                       "scope": known(["x ∈ [0,1], tolerance 10⁻⁶"]), "method": known("Compare frozen test cases."),
                       "expected": known("Bounded error ≤ 10⁻⁶"),
                       "observed": missing() if outcome == "unperformed" else known(PROSE),
                       "definition_records": known([record("definition", "check_definition", "source"),
                                                    record("definition_manifest", "check_definition", "work_product_manifest")]),
                       "definition_artifacts": known([artifact(name + "_definition")]),
                       "evidence": known([] if outcome == "unperformed" else [evidence(name + "_result", basis)]),
                       "independence": independence(), "limitations": missing()})
    permission = report("permission", "fail", "reported_permission_decision")
    del permission["outcome"]
    permission = {"status": "revoked", **permission}
    lifecycle = report("lifecycle", "fail", "reported_lifecycle_decision")
    del lifecycle["outcome"]
    # Repeated distant digest remains an occurrence for content accounting.
    lifecycle["evidence"]["value"][0]["artifacts"]["value"].append(artifact("environment"))
    lifecycle = {"status": "withdrawn", "reason_category": "scientific_defect", **lifecycle,
                 "replacement": known({"release": record("tool", "replacement_release", "tool_release", 3),
                                       "release_id": "sha256:" + "a" * 64}),
                 "supersedes": known([record("earlier_assessment", "supersedes_assessment", "tool_assessment")]),
                 "superseded_by": known(record("later_assessment", "superseded_by_assessment", "tool_assessment"))}
    return {
        "format": "research_pipeline.tool_assessment_content", "version": 1, "kind": "tool_assessment",
        "assessment_id": "assessment", "attribution": attribution(),
        "target": {"release": record("tool", "assessed_release", "tool_release"), "release_id": "sha256:" + "a" * 64},
        "environment": {"kind": "remote", "identity": known("Opaque synthetic service"),
                        "reported_version": missing(), "implementation_version": missing("unavailable", "Remote implementation cannot be inspected."),
                        "configuration": known([{"name": "precision", "value": ""}, {"name": "literal", "value": PROSE}]),
                        "observability": "opaque",
                        "records": known([record("environment", "assessed_environment", "source"),
                                          record("environment_manifest", "assessed_environment", "work_product_manifest"),
                                          record("environment", "assessed_environment", "source")]),
                        "artifacts": known([artifact("environment")]),
                        "dependencies": known([{"name": "quadrature", "reported_version": known("reported 1.2"),
                                                "records": known([record("dependency", "assessed_dependency", "source"),
                                                                  record("dep_manifest", "assessed_dependency", "work_product_manifest"),
                                                                  record("dep_tool", "assessed_dependency", "tool_release")]),
                                                "artifacts": known([artifact("dependency")]), "limitations": missing()}]),
                        "limitations": known(["Configuration pins do not freeze the remote running implementation."])},
        "scope": {"intended_uses": known([PROSE]), "tested_scope": known(["Synthetic finite cases only."])},
        "checks": known(checks),
        "reviews": known([{"review": record("review", "reported_review", "review"),
                           "attribution": attribution("Separate reviewer"), "outcome": "inconclusive",
                           "scope": known(["Scientific assumptions"]), "rationale": known("Shared formulation remains unresolved."),
                           "evidence": known([evidence("review_result", "independent_review")]),
                           "independence": independence(), "limitations": missing()}]),
        "limitations": known(["Synthetic supplied assessments cannot establish scientific truth."]),
        "issues": known([{"issue": record("issue", "reported_issue", "issue"), "attribution": attribution("Issue author"),
                          "category": "scientific_applicability", "summary": known("Uncontrolled approximation."),
                          "affected_scope": known(["Continuum extrapolation"]),
                          "evidence": known([evidence("issue_result")]), "limitations": missing()}]),
        "execution_permission": permission,
        "qualification": {name: report(name, scientific if name == "scientific_applicability" else "pass",
                                        "reported_qualification_decision") for name in DIMENSIONS},
        "lifecycle": lifecycle,
    }


def constructor_fields(value=None):
    """Convert only complete wire reference shapes to exact typed pins for constructor tests."""
    value = wire() if value is None else value

    def convert(item):
        """Recursively create independent constructor containers and typed references."""
        if type(item) is dict:
            if set(item) == {"record_id", "revision", "relationship", "target_kind"}:
                return RecordReference(**item)
            if set(item) == {"digest", "size"}:
                return ArtifactReference(**item)
            return {key: convert(child) for key, child in item.items()}
        if type(item) is list:
            return [convert(child) for child in item]
        return item
    return {key: convert(child) for key, child in value.items() if key not in ("format", "version", "kind")}


def assessment():
    """Return a fresh synthetic content object without touching external state."""
    return ToolAssessment.from_dict(wire())


def creator(details=None):
    """Use a distinct unauthenticated envelope creator with generic JSON details."""
    return CreationProvenance("archivist", "2026-10-30T12:35:00Z",
                              {"synthetic": True, "signed": -2, "fraction": 0.25, "nested": {"items": []}} if details is None else details)


def expected_records():
    """Specify literal complete projection order independently of production traversal."""
    return [
        record("tool", "assessed_release", "tool_release"),
        record("environment", "assessed_environment", "source"),
        record("environment_manifest", "assessed_environment", "work_product_manifest"),
        record("environment", "assessed_environment", "source"),
        record("dependency", "assessed_dependency", "source"),
        record("dep_manifest", "assessed_dependency", "work_product_manifest"),
        record("dep_tool", "assessed_dependency", "tool_release"),
        record("definition", "check_definition", "source"),
        record("definition_manifest", "check_definition", "work_product_manifest"),
        record("interface_result", "builder_self_test", "work_product_manifest"),
        record("definition", "check_definition", "source"),
        record("definition_manifest", "check_definition", "work_product_manifest"),
        record("software_result", "reported_tool_execution", "tool_execution"),
        record("definition", "check_definition", "source"),
        record("definition_manifest", "check_definition", "work_product_manifest"),
        record("science_result", "reported_assertion", "source"),
        record("definition", "check_definition", "source"),
        record("definition_manifest", "check_definition", "work_product_manifest"),
        record("audit_result", "independent_review", "review"),
        record("review", "reported_review", "review"),
        record("review_result", "independent_review", "review"),
        record("issue", "reported_issue", "issue"),
        record("issue_result", "reported_assertion", "source"),
        record("permission_decision", "reported_permission_decision", "decision"),
        record("permission_evidence", "reported_assertion", "source"),
        record("operational_interface_decision", "reported_qualification_decision", "decision"),
        record("operational_interface_evidence", "reported_assertion", "source"),
        record("software_behavior_decision", "reported_qualification_decision", "decision"),
        record("software_behavior_evidence", "reported_assertion", "source"),
        record("scientific_applicability_decision", "reported_qualification_decision", "decision"),
        record("scientific_applicability_evidence", "reported_assertion", "source"),
        record("lifecycle_decision", "reported_lifecycle_decision", "decision"),
        record("lifecycle_evidence", "reported_assertion", "source"),
        record("tool", "replacement_release", "tool_release", 3),
        record("earlier_assessment", "supersedes_assessment", "tool_assessment"),
        record("later_assessment", "superseded_by_assessment", "tool_assessment"),
    ]


def expected_artifacts():
    """Specify first-digest artifact order literally, including all distant evidence slots."""
    return [artifact(name) for name in (
        "environment", "dependency", "interface_definition", "interface_result", "software_definition",
        "software_result", "science_definition", "science_result", "audit_definition", "audit_result",
        "review_result", "issue_result", "permission_evidence", "operational_interface_evidence",
        "software_behavior_evidence", "scientific_applicability_evidence", "lifecycle_evidence")]


def canonical(value):
    """Compute expected canonical spelling independently using the documented JSON options."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def requirements(value, text=None):
    """Measure complete decoded occurrence accounting independently of product helpers."""
    result = dict(max_wire_bytes=len((canonical(value) if text is None else text).encode("utf-8")),
                  max_canonical_bytes=len(canonical(value)), max_string_chars=0, max_collection_items=0,
                  max_references=0, max_nodes=0, max_depth=0, max_reconstruction_units=0)

    def visit(item, depth):
        """Count keys, scalars, containers and repeated occurrences without deduplication."""
        result["max_nodes"] += 1
        result["max_reconstruction_units"] += 1
        if type(item) is str:
            result["max_string_chars"] = max(result["max_string_chars"], len(item))
            result["max_reconstruction_units"] += len(item)
        if type(item) is dict or type(item) is list:
            result["max_depth"] = max(result["max_depth"], depth)
            result["max_collection_items"] = max(result["max_collection_items"], len(item))
            if type(item) is dict:
                if set(item) in ({"digest", "size"}, {"record_id", "revision", "relationship", "target_kind"}):
                    result["max_references"] += 1
                for key, child in item.items():
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
    visit(value, 1)
    return result


def metadata_chars(envelope):
    """Count full retained metadata and each supplied projection occurrence independently."""
    total = sum(len(value) for value in (envelope.record_id, envelope.kind, envelope.provenance.actor,
                                         envelope.provenance.created_at, envelope.provenance._details_json))
    total += sum(len(item.record_id) + len(item.relationship) + len(item.target_kind) for item in envelope.record_references)
    return total + sum(len(item.digest) for item in envelope.artifact_references)


def forged(value, **changes):
    """Clone exact dataclass raw fields, permitting deliberate retained corruption for tests."""
    result = object.__new__(type(value))
    for field in fields(type(value)):
        object.__setattr__(result, field.name, deepcopy(getattr(value, field.name)))
    for name, child in changes.items():
        object.__setattr__(result, name, child)
    return result


def object_paths(value, path=()):
    """Yield every ordinary object position in a synthetic tree for closed-field tests."""
    if type(value) is dict:
        yield path
        for key, child in value.items():
            yield from object_paths(child, (*path, key))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from object_paths(child, (*path, index))


def at(value, path):
    """Locate an independently specified fixture position without altering the tree."""
    for key in path:
        value = value[key]
    return value
