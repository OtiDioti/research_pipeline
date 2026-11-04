"""Real disposable stores and independent passive-assessment persistence declarations."""

from dataclasses import replace

from research_pipeline.tool_assessment import ToolAssessment
from research_pipeline.tool_assessment_envelope import encode_envelope
from tests.test_assessment_store import assessment_envelope, review
from tests.test_store import record, request
from tests.test_typed_store import claim, context, envelope, ref
from tests.test_tool_registration import target
from tests.tool_assessment_fixtures import (
    DIMENSIONS, creator, expected_artifacts, expected_records, known, missing, wire,
)
from tests.tool_registration_fixtures import RegistrationCase, declaration, tool

ARTIFACT_NAMES = (
    "environment", "dependency", "interface_definition", "interface_result", "software_definition",
    "software_result", "science_definition", "science_result", "audit_definition", "audit_result",
    "review_result", "issue_result", "permission_evidence", "operational_interface_evidence",
    "software_behavior_evidence", "scientific_applicability_evidence", "lifecycle_evidence",
)


def document(identity="assessment", release=None, *, complete=False):
    """Adapt accepted substantive declarations to real release IDs and revision-one pins."""
    release = declaration() if release is None else release
    doc = wire()
    doc["assessment_id"] = identity
    doc["target"] = {"release": ref(release.tool_id, "assessed_release", "tool_release").to_dict(),
                     "release_id": release.release_id}
    doc["lifecycle"]["replacement"] = missing()
    doc["lifecycle"]["supersedes"] = known([])
    doc["lifecycle"]["superseded_by"] = missing()

    def revise(item):
        """Repin each independently supplied fixture occurrence to its actual first revision."""
        if type(item) is dict:
            if set(item) == {"record_id", "revision", "relationship", "target_kind"}:
                item["revision"] = 1
            else:
                for child in item.values():
                    revise(child)
        elif type(item) is list:
            for child in item:
                revise(child)
    revise(doc)
    if not complete:
        doc["environment"]["records"] = known([])
        doc["environment"]["dependencies"] = known([])
        doc["environment"]["artifacts"] = known([])
        doc["checks"] = known([])
        doc["reviews"] = known([])
        doc["issues"] = known([])
        for report in (doc["execution_permission"], *(doc["qualification"][name] for name in DIMENSIONS), doc["lifecycle"]):
            report["decisions"] = known([])
            report["evidence"] = known([])
    return doc


def assessment(doc=None, revision=1):
    """Encode an exact passive assessment with creator distinct from all reported actors."""
    doc = document() if doc is None else doc
    value = ToolAssessment.from_dict(doc)
    return encode_envelope(doc["assessment_id"], revision, value, creator())


def independent_projection():
    """Repin the predecessor fixture's literal ordered oracle, without product projection code."""
    result = expected_records()[:-3]
    for item in result:
        item["revision"] = 1
    return result


class AssessmentCase(RegistrationCase):
    """Add real assessment graphs while retaining isolated private schema-three stores."""

    def seed_release(self, value=None):
        """Commit the exact release prerequisite and return its immutable content."""
        value = declaration() if value is None else value
        self.store.submit_typed(request(value.tool_id + "-seed", [tool(value)]))
        return value

    def full_graph(self, identity="assessment"):
        """Supply every role, real constrained closure and all inert direct attachments."""
        for name, expected in zip(ARTIFACT_NAMES, expected_artifacts()):
            actual = self.store.put_artifact((name + "\n").encode())
            self.assertEqual(actual.to_dict(), expected)
        artifact = self.store.put_artifact(b"independent target attachment")
        doc = document(identity, complete=True)
        typed, shallow, seen = [], [], set()
        for pin in independent_projection()[1:]:
            name, kind = pin["record_id"], pin["target_kind"]
            if name in seen:
                continue
            seen.add(name)
            if pin["relationship"] in {"assessed_dependency", "reported_tool_execution", "reported_permission_decision",
                                       "reported_qualification_decision", "reported_lifecycle_decision"}:
                shallow.append(record(name, kind=kind, content={"format": "research_pipeline.operating_authority_content", "version": -1}))
            elif kind == "review":
                value = replace(review(), candidate_claim=ref(name + "-candidate", "candidate_claim", "claim"),
                    target_context=ref(name + "-context", "target_context", "research_context"),
                    context_manifest=ref(name + "-manifest", "context_manifest", "work_product_manifest"),
                    authorization_policy=ref(name + "-policy", "authorization_policy", "decision"),
                    reported_checks=[], route_assessments=[])
                typed.extend([assessment_envelope(name, value), envelope(name + "-candidate", claim(name + "-context")),
                              envelope(name + "-context", context())])
                shallow.extend([record(name + "-manifest", kind="work_product_manifest"), record(name + "-policy", kind="decision")])
            else:
                item, dependencies = target(name, kind, artifact)
                typed.extend([item, *dependencies])
        self.store.submit(request(identity + "-shallow", shallow))
        return doc, [assessment(doc), tool(declaration()), *typed]
