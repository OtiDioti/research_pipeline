"""Pure attributed assessment contracts; declarations confer no scientific authority."""

from dataclasses import dataclass, fields
import json

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, _fields, _integer, _snapshot, _validate_json_string,
)
from research_pipeline.scientific import (
    NotTypedContentError, _collection, _list, _record_from_dict, _record_list,
    _text, _texts,
)


_FORMAT = "research_pipeline.assessment_content"
_MODES = ("answer_blind_reconstruction", "proof_blind_reconstruction", "candidate_aware_audit")
_SHARED = ("shared_formulation", "shared_sources", "shared_lemmas", "shared_method",
           "shared_implementation", "shared_communications", "limitations")
_STAGES = ("exploring", "frozen_candidate", "under_review", "archived")
_DISPOSITIONS = ("provisional", "supported_within_scope", "disputed", "support_withdrawn",
                 "refuted_within_scope", "superseded")
_SUPPORT = ("heuristic", "analytical", "symbolic", "numerical", "formal", "source_based")
_APPLICABILITY = ("applicable", "requires_reassessment", "inapplicable", "unresolved")
_NOVELTY = ("unassessed", "known_equivalent_identified", "search_found_no_equivalent",
            "researcher_assessed_contribution")
_OUTCOMES = ("sufficient", "invalid", "stale", "inapplicable", "incomplete", "unresolved")


def _code(value, choices: tuple, field: str) -> None:
    """Require an ordinary string code without interpreting or ranking dimensions."""
    if type(value) is not str or value not in choices:
        raise DomainValidationError(f"{field}: expected one of {', '.join(choices)}")


def _copy(value, expected: type, field: str):
    """Reconstruct an exact nested value, isolating aliases and reporting its containing field."""
    if type(value) is not expected:
        raise DomainValidationError(f"{field}: expected {expected.__name__}")
    try:
        return expected.from_dict(value.to_dict())
    except (AttributeError, TypeError, ValueError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"{field}: malformed {expected.__name__}: {error}") from error


def _rebuild(value, expected: type, field: str):
    """Revalidate dataclass fields before serialization, including bypassed frozen state."""
    if type(value) is not expected:
        raise DomainValidationError(f"{field}: expected {expected.__name__}")
    try:
        return expected(**{item.name: getattr(value, item.name) for item in fields(expected)})
    except (AttributeError, TypeError, ValueError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"{field}: malformed {expected.__name__}: {error}") from error


def _reference(value, relationship: str, target_kind: str | None, field: str) -> RecordReference:
    """Detach a reference with a required declared kind and an exact semantic role."""
    result = _copy(value, RecordReference, field)
    if result.target_kind is None:
        raise DomainValidationError(f"{field}: target_kind must be declared")
    if result.relationship != relationship or (target_kind is not None and result.target_kind != target_kind):
        raise DomainValidationError(f"{field}: expected relationship {relationship} and target_kind {target_kind}")
    return result


def _unique_targets(values: tuple, field: str) -> None:
    """Reject repeated identity/revision pairs within one semantic collection, across roles."""
    seen = set()
    for value in values:
        target = (value.record_id, value.revision)
        if target in seen:
            raise DomainValidationError(f"{field}: repeated exact target {target}")
        seen.add(target)


def _references(values, relationship: str, target_kind: str | None, field: str) -> tuple:
    """Detach one ordered reference collection and reject repeated exact targets."""
    result = tuple(_reference(value, relationship, target_kind, f"{field}[{index}]")
                   for index, value in enumerate(_collection(values, field)))
    _unique_targets(result, field)
    return result


def _artifacts(values) -> tuple[ArtifactReference, ...]:
    """Detach exact artifact objects; a digest may occur once regardless of declared size."""
    result = tuple(_copy(value, ArtifactReference, f"artifacts[{index}]")
                   for index, value in enumerate(_collection(values, "artifacts")))
    if len({value.digest for value in result}) != len(result):
        raise DomainValidationError("artifacts: repeated artifact digest")
    return result


def _nested(value: dict, expected: type, field: str):
    """Decode a nested wire object with field/index context on validation failures."""
    try:
        return expected.from_dict(value)
    except (AttributeError, TypeError, ValueError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"{field}: {error}") from error


def _header(value: dict) -> dict:
    """Require explicit assessment format/version; familiar field names never imply typing."""
    _snapshot(value, "assessment content")
    if "format" not in value:
        raise NotTypedContentError("assessment content: missing format discriminator")
    if type(value["format"]) is not str or value["format"] != _FORMAT:
        raise DomainValidationError("format: unsupported assessment content format")
    if "version" not in value:
        raise DomainValidationError("version: missing required field")
    _integer(value["version"], "version", 1)
    if value["version"] != 1:
        raise DomainValidationError("version: unsupported assessment content version")
    return value


def _content_fields(value: dict, kind: str, required: set[str]) -> dict:
    """Return exact constructor fields after validating the assessment-specific header."""
    result = _fields(_header(value), required | {"format", "version", "kind"}, set(), kind)
    if type(result["kind"]) is not str or result["kind"] != kind:
        raise DomainValidationError(f"kind: expected {kind}")
    for name in ("format", "version", "kind"):
        del result[name]
    return result


def _wire(kind: str, value: dict) -> dict:
    """Attach the fixed assessment discriminator to a fresh field tree."""
    return {"format": _FORMAT, "version": 1, "kind": kind, **value}


@dataclass(frozen=True)
class IndependenceDeclaration:
    """Reported exposure and requested/reported modes, without certifying independence."""

    requested_mode: str
    reported_mode: str
    shared_formulation: tuple[str, ...]
    shared_sources: tuple[str, ...]
    shared_lemmas: tuple[str, ...]
    shared_method: tuple[str, ...]
    shared_implementation: tuple[str, ...]
    shared_communications: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate modes independently and snapshot all required narrative collections."""
        _code(self.requested_mode, _MODES, "requested_mode")
        _code(self.reported_mode, _MODES, "reported_mode")
        for name in _SHARED:
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict:
        """Return detached declarations, rejecting malformed bypassed frozen state."""
        value = _rebuild(self, IndependenceDeclaration, "independence")
        return {"requested_mode": value.requested_mode, "reported_mode": value.reported_mode,
                **{name: list(getattr(value, name)) for name in _SHARED}}

    @classmethod
    def from_dict(cls, value: dict) -> "IndependenceDeclaration":
        """Decode exact nested fields and explicit arrays without inferring absent sharing."""
        _snapshot(value, "independence")
        result = _fields(value, {"requested_mode", "reported_mode", *_SHARED}, set(), "independence")
        for name in _SHARED:
            result[name] = _list(result[name], name)
        return cls(**result)


@dataclass(frozen=True)
class SubstantiveAssessment:
    """Independent attributed dimensions with conditional scope, never canonical state."""

    work_stage: str
    scientific_disposition: str
    support_types: tuple[str, ...]
    applicability: str
    novelty: str
    rationale: str
    conditions: tuple[str, ...]
    obligations: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate each code independently; favorable reports may retain obligations."""
        for name, choices in (("work_stage", _STAGES), ("scientific_disposition", _DISPOSITIONS),
                              ("applicability", _APPLICABILITY), ("novelty", _NOVELTY)):
            _code(getattr(self, name), choices, name)
        support = _collection(self.support_types, "support_types")
        for index, code in enumerate(support):
            _code(code, _SUPPORT, f"support_types[{index}]")
        if len(set(support)) != len(support):
            raise DomainValidationError("support_types: repeated code")
        object.__setattr__(self, "support_types", support)
        _text(self.rationale, "rationale")
        for name in ("conditions", "obligations", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict:
        """Return fresh dimension/scope fields after defensive reconstruction."""
        value = _rebuild(self, SubstantiveAssessment, "assessment")
        return dict(work_stage=value.work_stage, scientific_disposition=value.scientific_disposition,
                    support_types=list(value.support_types), applicability=value.applicability,
                    novelty=value.novelty, rationale=value.rationale, conditions=list(value.conditions),
                    obligations=list(value.obligations), limitations=list(value.limitations))

    @classmethod
    def from_dict(cls, value: dict) -> "SubstantiveAssessment":
        """Decode explicit dimension fields and arrays, rejecting inference and coercion."""
        _snapshot(value, "assessment")
        result = _fields(value, {"work_stage", "scientific_disposition", "support_types", "applicability",
                                "novelty", "rationale", "conditions", "obligations", "limitations"}, set(), "assessment")
        for name in ("support_types", "conditions", "obligations", "limitations"):
            result[name] = _list(result[name], name)
        return cls(**result)


@dataclass(frozen=True)
class SupportRouteAssessment:
    """One attributed judgment of an exact route, retaining outstanding conditions."""

    justification: RecordReference
    outcome: str
    rationale: str
    outstanding_conditions: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Pin the declared route without resolving conclusions or flattening premises."""
        object.__setattr__(self, "justification", _reference(
            self.justification, "assessed_route", "justification", "justification"))
        _code(self.outcome, _OUTCOMES, "outcome")
        _text(self.rationale, "rationale")
        for name in ("outstanding_conditions", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict:
        """Return a detached judgment with its exact route and conditional declarations."""
        value = _rebuild(self, SupportRouteAssessment, "route_assessment")
        return dict(justification=value.justification.to_dict(), outcome=value.outcome,
                    rationale=value.rationale, outstanding_conditions=list(value.outstanding_conditions),
                    limitations=list(value.limitations))

    @classmethod
    def from_dict(cls, value: dict) -> "SupportRouteAssessment":
        """Decode strict route fields, including all four exact-reference keys."""
        _snapshot(value, "route_assessment")
        result = _fields(value, {"justification", "outcome", "rationale", "outstanding_conditions", "limitations"},
                         set(), "route_assessment")
        result["justification"] = _record_from_dict(result["justification"], "justification")
        for name in ("outstanding_conditions", "limitations"):
            result[name] = _list(result[name], name)
        return cls(**result)


@dataclass(frozen=True)
class Review:
    """Attributed review of an exact candidate/context with declared checks and route judgments."""

    candidate_claim: RecordReference
    target_context: RecordReference
    reviewer: str
    independence: IndependenceDeclaration
    context_manifest: RecordReference
    authorization_policy: RecordReference
    reported_checks: tuple[RecordReference, ...]
    assessment: SubstantiveAssessment
    route_assessments: tuple[SupportRouteAssessment, ...]
    open_obligations: tuple[str, ...]
    limitations: tuple[str, ...]
    artifacts: tuple[ArtifactReference, ...]
    origin: str

    def __post_init__(self) -> None:
        """Detach and validate all roles and nested values, without target lookup or authority."""
        for name, kind in (("candidate_claim", "claim"), ("target_context", "research_context"),
                           ("context_manifest", "work_product_manifest"), ("authorization_policy", "decision")):
            object.__setattr__(self, name, _reference(getattr(self, name), name, kind, name))
        _text(self.reviewer, "reviewer")
        object.__setattr__(self, "independence", _copy(self.independence, IndependenceDeclaration, "independence"))
        object.__setattr__(self, "assessment", _copy(self.assessment, SubstantiveAssessment, "assessment"))
        checks = []
        for index, value in enumerate(_collection(self.reported_checks, "reported_checks")):
            field = f"reported_checks[{index}]"
            value = _copy(value, RecordReference, field)
            if (value.relationship, value.target_kind) not in (
                    ("reported_evidence", "evidence"), ("reported_tool_execution", "tool_execution")):
                raise DomainValidationError(f"{field}: expected reported_evidence/evidence or reported_tool_execution/tool_execution")
            checks.append(value)
        # Mixed check roles share an identity/revision namespace, so relabeling cannot evade duplicates.
        _unique_targets(tuple(checks), "reported_checks")
        object.__setattr__(self, "reported_checks", tuple(checks))
        routes = tuple(_copy(value, SupportRouteAssessment, f"route_assessments[{index}]")
                       for index, value in enumerate(_collection(self.route_assessments, "route_assessments")))
        _unique_targets(tuple(value.justification for value in routes), "route_assessments")
        object.__setattr__(self, "route_assessments", routes)
        for name in ("open_obligations", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        object.__setattr__(self, "artifacts", _artifacts(self.artifacts))
        _code(self.origin, ("synthetic", "unverified"), "origin")

    def to_dict(self) -> dict:
        """Return detached versioned content, revalidating even deliberately forged state."""
        value = _rebuild(self, Review, "review")
        return _wire("review", dict(
            candidate_claim=value.candidate_claim.to_dict(), target_context=value.target_context.to_dict(),
            reviewer=value.reviewer, independence=value.independence.to_dict(),
            context_manifest=value.context_manifest.to_dict(), authorization_policy=value.authorization_policy.to_dict(),
            reported_checks=[item.to_dict() for item in value.reported_checks], assessment=value.assessment.to_dict(),
            route_assessments=[item.to_dict() for item in value.route_assessments],
            open_obligations=list(value.open_obligations), limitations=list(value.limitations),
            artifacts=[item.to_dict() for item in value.artifacts], origin=value.origin))

    @classmethod
    def from_dict(cls, value: dict) -> "Review":
        """Decode exact review fields, preserving mixed-check and route ordering without lookup."""
        result = _content_fields(value, "review", {
            "candidate_claim", "target_context", "reviewer", "independence", "context_manifest",
            "authorization_policy", "reported_checks", "assessment", "route_assessments",
            "open_obligations", "limitations", "artifacts", "origin"})
        for name in ("candidate_claim", "target_context", "context_manifest", "authorization_policy"):
            result[name] = _record_from_dict(result[name], name)
        result["reported_checks"] = _record_list(result["reported_checks"], "reported_checks")
        result["independence"] = _nested(result["independence"], IndependenceDeclaration, "independence")
        result["assessment"] = _nested(result["assessment"], SubstantiveAssessment, "assessment")
        for name, expected in (("route_assessments", SupportRouteAssessment), ("artifacts", ArtifactReference)):
            result[name] = [_nested(item, expected, f"{name}[{index}]")
                            for index, item in enumerate(_list(result[name], name))]
        for name in ("open_obligations", "limitations"):
            result[name] = _list(result[name], name)
        return cls(**result)


@dataclass(frozen=True)
class Issue:
    """Attributed objection over exact generic targets; disposition changes no canonical state."""

    disputed_point: str
    affected_records: tuple[RecordReference, ...]
    objection_or_counterexample: str
    severity: str
    proposed_discriminating_action: str
    disposition: str
    rationale: str
    limitations: tuple[str, ...]
    supporting_evidence: tuple[RecordReference, ...]
    artifacts: tuple[ArtifactReference, ...]
    origin: str

    def __post_init__(self) -> None:
        """Require a nonempty affected set and detach exact references and narrative scope."""
        for name in ("disputed_point", "objection_or_counterexample", "proposed_discriminating_action", "rationale"):
            _text(getattr(self, name), name)
        affected = _references(self.affected_records, "affected_record", None, "affected_records")
        if not affected:
            raise DomainValidationError("affected_records: expected nonempty collection")
        object.__setattr__(self, "affected_records", affected)
        object.__setattr__(self, "supporting_evidence", _references(
            self.supporting_evidence, "supporting_evidence", "evidence", "supporting_evidence"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        object.__setattr__(self, "artifacts", _artifacts(self.artifacts))
        _code(self.severity, ("informational", "nonblocking", "blocking"), "severity")
        _code(self.disposition, ("open", "under_investigation", "resolved", "dismissed"), "disposition")
        _code(self.origin, ("synthetic", "unverified"), "origin")

    def to_dict(self) -> dict:
        """Return independent versioned issue fields after validating bypassed frozen state."""
        value = _rebuild(self, Issue, "issue")
        return _wire("issue", dict(
            disputed_point=value.disputed_point, affected_records=[item.to_dict() for item in value.affected_records],
            objection_or_counterexample=value.objection_or_counterexample, severity=value.severity,
            proposed_discriminating_action=value.proposed_discriminating_action, disposition=value.disposition,
            rationale=value.rationale, limitations=list(value.limitations),
            supporting_evidence=[item.to_dict() for item in value.supporting_evidence],
            artifacts=[item.to_dict() for item in value.artifacts], origin=value.origin))

    @classmethod
    def from_dict(cls, value: dict) -> "Issue":
        """Decode exact issue fields and explicit arrays, retaining cross-role occurrences."""
        result = _content_fields(value, "issue", {
            "disputed_point", "affected_records", "objection_or_counterexample", "severity",
            "proposed_discriminating_action", "disposition", "rationale", "limitations",
            "supporting_evidence", "artifacts", "origin"})
        for name in ("affected_records", "supporting_evidence"):
            result[name] = _record_list(result[name], name)
        result["artifacts"] = [_nested(item, ArtifactReference, f"artifacts[{index}]")
                               for index, item in enumerate(_list(result["artifacts"], "artifacts"))]
        result["limitations"] = _list(result["limitations"], "limitations")
        return cls(**result)


AssessmentContent = Review | Issue


def decode_content(value: dict) -> AssessmentContent:
    """Decode only explicitly marked supported assessment content, never generic lookalikes."""
    _header(value)
    kind = value.get("kind")
    if type(kind) is not str:
        raise DomainValidationError("kind: required assessment content kind must be a string")
    if kind == "review":
        return Review.from_dict(value)
    if kind == "issue":
        return Issue.from_dict(value)
    raise DomainValidationError(f"kind: unsupported assessment content kind {kind!r}")


def dumps_content(value: AssessmentContent) -> str:
    """Revalidate and encode canonical compact sorted-key ASCII JSON with array order intact."""
    if type(value) not in (Review, Issue):
        raise DomainValidationError("content: expected an assessment content value")
    return _snapshot(value.to_dict(), "assessment content")


def _unique_object(pairs: list) -> dict:
    """Reject duplicate JSON keys at every depth while building an ordinary object."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError(f"assessment content: duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    """Reject nonstandard nonfinite JSON constants with assessment-specific diagnostics."""
    raise DomainValidationError(f"assessment content: nonfinite JSON constant {value}")


def loads_content(data: str | bytes) -> AssessmentContent:
    """Decode strict UTF-8 JSON; translate syntax, encoding and depth failures with causes."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("assessment content: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "assessment content JSON")
        return decode_content(json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"assessment content: cannot decode JSON: {error}") from error


def _links(content: AssessmentContent) -> tuple[tuple[RecordReference, ...], tuple[ArtifactReference, ...]]:
    """Project declared roles in fixed order; cross-field occurrences remain distinct."""
    if type(content) is Review:
        return ((content.candidate_claim, content.target_context, content.context_manifest,
                 content.authorization_policy, *content.reported_checks,
                 *(route.justification for route in content.route_assessments)), content.artifacts)
    if type(content) is Issue:
        return ((*content.affected_records, *content.supporting_evidence), content.artifacts)
    raise DomainValidationError("content: expected an assessment content value")


def encode_envelope(record_id: str, revision: int, content: AssessmentContent,
                    provenance: CreationProvenance) -> RecordEnvelope:
    """Build a detached attributed envelope with exact projected links and null canonical states."""
    content = loads_content(dumps_content(content))
    provenance = _copy(provenance, CreationProvenance, "provenance")
    records, artifacts = _links(content)
    document = content.to_dict()
    return RecordEnvelope(record_id, revision, document["kind"], document, provenance,
                          records, artifacts, operational_status=None, scientific_disposition=None)


def decode_envelope(envelope: RecordEnvelope) -> AssessmentContent:
    """Reconstruct an envelope and require exact kind and complete ordered link equality."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected RecordEnvelope")
    # Domain serialization alone can erase a forged nested object's class. Check
    # exact classes before that conversion and retain field/index diagnostics.
    try:
        _copy(envelope.provenance, CreationProvenance, "envelope.provenance")
        for name, expected in (("record_references", RecordReference), ("artifact_references", ArtifactReference)):
            for index, value in enumerate(_collection(getattr(envelope, name), f"envelope.{name}")):
                _copy(value, expected, f"envelope.{name}[{index}]")
    except AttributeError as error:
        raise DomainValidationError("envelope: missing nested value") from error
    checked = _copy(envelope, RecordEnvelope, "envelope")
    content = decode_content(checked.content)
    if checked.kind != content.to_dict()["kind"]:
        raise DomainValidationError("envelope.kind: disagrees with assessment content kind")
    records, artifacts = _links(content)
    # Never repair missing/reordered links or follow any targets during pure conversion.
    if checked.record_references != records:
        raise DomainValidationError("envelope.record_references: disagree with complete ordered content roles")
    if checked.artifact_references != artifacts:
        raise DomainValidationError("envelope.artifact_references: disagree with complete ordered content roles")
    return content
