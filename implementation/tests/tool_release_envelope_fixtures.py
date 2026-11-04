"""Independent envelope fixtures and ordered expectations, never production projections."""

from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordReference
from research_pipeline.tool_release import ToolRelease
from tests.tool_release_fixtures import artifact, constructor_sections, known, record, rehash, wire


def complete_wire(kind="local_program"):
    """Populate every pin slot with repetition within/across roles and artifact sections."""
    doc = wire(kind=kind)
    shared = record("reported_provenance", "source", "shared")
    doc["identity"]["provenance_records"] = known([shared, shared, record("reported_provenance", "project", "project")])
    doc["identity"]["implementation"]["source_records"] = known([
        record("implementation_source", "source", "shared"), record("implementation_source", "source", "source2")])
    doc["effects_authority"]["child_tools"] = known([
        record("child_tool", "tool_release", "child1"), record("child_tool", "tool_release", "child2")])
    for field, role, kind_name in (("qualification_reports", "reported_qualification", "tool_assessment"),
                                   ("evidence", "reported_evidence", "evidence"), ("issues", "reported_issue", "issue")):
        doc["evidence_limitations"][field] = known([record(role, kind_name, field + "1"), record(role, kind_name, field + "2")])
    doc["reproducibility"]["dependency_records"] = known([
        record("build_dependency", "source", "shared"), record("build_dependency", "source", "dep2")])
    a, b, c, d = [artifact(label) for label in (b"A", b"BB", b"CCC", b"DDDD")]
    if kind != "remote_service":
        doc["identity"]["implementation"]["artifacts"] = known([
            {"path": "a.py", "artifact": a}, {"path": "a-copy.py", "artifact": a}, {"path": "b.py", "artifact": b}])
    doc["invocation"]["adapter"]["files"] = known([
        {"path": "a.py", "artifact": a}, {"path": "b.py", "artifact": b},
        {"path": "c.py", "artifact": c}, {"path": "c-copy.py", "artifact": c}])
    doc["invocation"]["adapter"]["entry_file"] = known("a.py")
    doc["evidence_limitations"]["self_tests"] = known([a, b, c, c, d, d])
    doc["reproducibility"]["dependency_artifacts"] = known([a, b, c, d, d, artifact(b"EEEEE")])
    return rehash(doc)


def expected_records():
    """State the concrete complete occurrence order independently of product traversal."""
    return tuple(RecordReference(name, 3, role, kind) for name, role, kind in (
        ("shared", "reported_provenance", "source"),
        ("shared", "reported_provenance", "source"),
        ("project", "reported_provenance", "project"),
        ("shared", "implementation_source", "source"),
        ("source2", "implementation_source", "source"),
        ("child1", "child_tool", "tool_release"), ("child2", "child_tool", "tool_release"),
        ("qualification_reports1", "reported_qualification", "tool_assessment"),
        ("qualification_reports2", "reported_qualification", "tool_assessment"),
        ("evidence1", "reported_evidence", "evidence"), ("evidence2", "reported_evidence", "evidence"),
        ("issues1", "reported_issue", "issue"), ("issues2", "reported_issue", "issue"),
        ("shared", "build_dependency", "source"), ("dep2", "build_dependency", "source")))


def expected_artifacts():
    """State first-digest artifact order using independent hashlib fixture pins."""
    return tuple(ArtifactReference(**artifact(label)) for label in (b"A", b"BB", b"CCC", b"DDDD", b"EEEEE"))


def creator():
    """Supply distinct creator attribution and the full range of legitimate generic JSON."""
    return CreationProvenance("envelope_creator", "2026-11-04T10:00:00Z", {
        "reported_provenance": {"record_id": "not_a_pin"},
        "data": [True, False, None, -17, 1.25, {"α": '😀\n\\"'}]})


def release(kind="local_program"):
    """Construct a substantive release through the public typed API with actual pins."""
    return ToolRelease(**constructor_sections(complete_wire(kind)))


def metadata_chars(envelope):
    """Measure the specified retained strings independently, counting every occurrence."""
    total = sum(len(value) for value in (envelope.record_id, envelope.kind,
                                        envelope.provenance.actor, envelope.provenance.created_at,
                                        envelope.provenance._details_json))
    total += sum(len(pin.record_id) + len(pin.relationship) + len(pin.target_kind)
                 for pin in envelope.record_references)
    return total + sum(len(pin.digest) for pin in envelope.artifact_references)


def forged(value, **changes):
    """Copy only fixed retained fields into an exact bypass object for negative consumption tests."""
    result = object.__new__(type(value))
    for name, child in vars(value).items():
        object.__setattr__(result, name, child)
    for name, child in changes.items():
        object.__setattr__(result, name, child)
    return result


def unlinked_release():
    """Build small valid remote content with no concrete pins, retaining its access/effects limits."""
    doc = wire(kind="remote_service")
    for fact in (doc["identity"]["provenance_records"], doc["identity"]["implementation"]["source_records"],
                 doc["effects_authority"]["child_tools"], doc["evidence_limitations"]["qualification_reports"],
                 doc["evidence_limitations"]["evidence"], doc["evidence_limitations"]["issues"],
                 doc["reproducibility"]["dependency_records"], doc["evidence_limitations"]["self_tests"],
                 doc["reproducibility"]["dependency_artifacts"], doc["invocation"]["adapter"]["files"]):
        fact.update(known([]))
    doc["invocation"]["adapter"]["entry_file"] = known(None)
    return ToolRelease(**constructor_sections(doc))
