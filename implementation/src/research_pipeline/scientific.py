"""Pure versioned scientific descriptions and coherent links, without scientific authority."""

from dataclasses import dataclass
import json

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, _fields, _identifier, _integer, _snapshot, _validate_json_string,
)


_FORMAT = "research_pipeline.scientific_content"
_CONTEXT_COLLECTIONS = (
    "equations", "definitions", "units", "conventions", "mathematical_domains",
    "boundary_conditions", "initial_conditions", "parameter_regime", "approximations",
    "limit_ordering",
)


class NotTypedContentError(DomainValidationError):
    """Content has no format discriminator; its generic fields do not imply typed status."""


def _text(value: str, field: str) -> None:
    """Require nonblank scalar-value text without trimming or interpreting statements."""
    if type(value) is not str or not value.strip():
        raise DomainValidationError(f"{field}: expected nonblank text")
    _validate_json_string(value, field)


def _collection(values, field: str) -> tuple:
    """Snapshot ordinary constructor lists/tuples; reject unordered or lazy inputs."""
    if type(values) not in (list, tuple):
        raise DomainValidationError(f"{field}: expected ordinary list or tuple")
    return tuple(values)


def _texts(values, field: str) -> tuple[str, ...]:
    """Copy an ordered text collection, validating each statement and retaining repeats."""
    result = _collection(values, field)
    for index, value in enumerate(result):
        _text(value, f"{field}[{index}]")
    return result


def _role(value, relationship: str, target_kind: str | None, field: str) -> RecordReference:
    """Check an exact reference's declared role/kind without relabeling or resolving it."""
    if type(value) is not RecordReference:
        raise DomainValidationError(f"{field}: expected RecordReference")
    RecordReference.from_dict(value.to_dict())
    if value.relationship != relationship or (target_kind is not None and value.target_kind != target_kind):
        raise DomainValidationError(f"{field}: expected relationship {relationship} and target_kind {target_kind}")
    return value


def _roles(values, relationship: str, target_kind: str | None, field: str,
           nonempty: bool = False) -> tuple[RecordReference, ...]:
    """Snapshot one reference role, rejecting redundant exact targets within that role."""
    result = _collection(values, field)
    if nonempty and not result:
        raise DomainValidationError(f"{field}: expected nonempty collection")
    seen = set()
    for index, value in enumerate(result):
        _role(value, relationship, target_kind, f"{field}[{index}]")
        target = (value.record_id, value.revision)
        if target in seen:
            raise DomainValidationError(f"{field}: repeated exact target {target}")
        seen.add(target)
    return result


def _assumptions(values, field: str) -> tuple["NamedAssumption", ...]:
    """Snapshot local named statements and reject duplicate case-sensitive labels."""
    result = _collection(values, field)
    labels = set()
    for index, value in enumerate(result):
        if type(value) is not NamedAssumption:
            raise DomainValidationError(f"{field}[{index}]: expected NamedAssumption")
        if value.label in labels:
            raise DomainValidationError(f"{field}: repeated assumption label {value.label}")
        labels.add(value.label)
    return result


def _artifacts(values, field: str, nonempty: bool = False) -> tuple[ArtifactReference, ...]:
    """Snapshot one artifact role, rejecting repeated digests regardless of size."""
    result = _collection(values, field)
    if nonempty and not result:
        raise DomainValidationError(f"{field}: expected nonempty collection")
    seen = set()
    for index, value in enumerate(result):
        if type(value) is not ArtifactReference:
            raise DomainValidationError(f"{field}[{index}]: expected ArtifactReference")
        ArtifactReference.from_dict(value.to_dict())
        if value.digest in seen:
            raise DomainValidationError(f"{field}: repeated artifact digest {value.digest}")
        seen.add(value.digest)
    return result


def _header(value: dict) -> dict:
    """Validate strict JSON and the explicit typed discriminator/version, without inference."""
    _snapshot(value, "scientific content")
    # Generic content stays generic even when its field names resemble typed data.
    if "format" not in value:
        raise NotTypedContentError("scientific content: missing format discriminator")
    if type(value["format"]) is not str or value["format"] != _FORMAT:
        raise DomainValidationError("format: unsupported scientific content format")
    if "version" not in value:
        raise DomainValidationError("version: missing required field")
    _integer(value["version"], "version", 1)
    if value["version"] != 1:
        raise DomainValidationError("version: unsupported scientific content version")
    return value


def _content_fields(value: dict, kind: str, required: set[str]) -> dict:
    """Check a content document's header and exact fields, returning constructor fields."""
    fields = _fields(_header(value), required | {"format", "version", "kind"}, set(), kind)
    if type(fields["kind"]) is not str or fields["kind"] != kind:
        raise DomainValidationError(f"kind: expected {kind}")
    for name in ("format", "version", "kind"):
        del fields[name]
    return fields


def _wire(kind: str, fields: dict) -> dict:
    """Attach fixed version-1 metadata to a fresh content serialization."""
    return {"format": _FORMAT, "version": 1, "kind": kind, **fields}


def _record_from_dict(value: dict, field: str) -> RecordReference:
    """Decode all four required reference fields, including explicit nullable target_kind."""
    try:
        return RecordReference.from_dict(_fields(
            value, {"record_id", "revision", "relationship", "target_kind"}, set(), field))
    except DomainValidationError as error:
        raise DomainValidationError(f"{field}: {error}") from error


def _list(value, field: str) -> list:
    """Require actual JSON arrays on wire input, never constructor tuple coercion."""
    if type(value) is not list:
        raise DomainValidationError(f"{field}: expected serialized JSON list")
    return value


def _record_list(value, field: str) -> list[RecordReference]:
    """Decode ordered exact references with indexed diagnostics for malformed fields."""
    return [_record_from_dict(item, f"{field}[{index}]")
            for index, item in enumerate(_list(value, field))]


def _assumption_list(value, field: str) -> list["NamedAssumption"]:
    """Decode local statements, adding their containing role to validation errors."""
    try:
        return [NamedAssumption.from_dict(item) for item in _list(value, field)]
    except DomainValidationError as error:
        raise DomainValidationError(f"{field}: {error}") from error


def _artifact_list(value, field: str) -> list[ArtifactReference]:
    """Decode exact artifact objects and preserve the containing role in diagnostics."""
    try:
        return [ArtifactReference.from_dict(item) for item in _list(value, field)]
    except DomainValidationError as error:
        raise DomainValidationError(f"{field}: {error}") from error


@dataclass(frozen=True)
class NamedAssumption:
    """A local opaque label and statement, scoped to the containing exact record revision."""

    label: str
    statement: str

    def __post_init__(self) -> None:
        """Validate the label and nonblank scalar text without assigning global identity."""
        _identifier(self.label, "assumption.label")
        _text(self.statement, "assumption.statement")

    def to_dict(self) -> dict:
        """Return a detached two-field statement document."""
        return {"label": self.label, "statement": self.statement}

    @classmethod
    def from_dict(cls, value: dict) -> "NamedAssumption":
        """Reconstruct strict JSON with exactly label and statement; reject coercions."""
        _snapshot(value, "assumption")
        return cls(**_fields(value, {"label", "statement"}, set(), "assumption"))


@dataclass(frozen=True)
class ResearchContext:
    """Explicit scientific scope as uninterpreted text with required ordered declarations."""

    question: str
    equations: tuple[str, ...]
    definitions: tuple[str, ...]
    units: tuple[str, ...]
    conventions: tuple[str, ...]
    mathematical_domains: tuple[str, ...]
    boundary_conditions: tuple[str, ...]
    initial_conditions: tuple[str, ...]
    parameter_regime: tuple[str, ...]
    approximations: tuple[str, ...]
    limit_ordering: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate the question and freeze every explicit collection without normalization."""
        _text(self.question, "question")
        for name in _CONTEXT_COLLECTIONS:
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict:
        """Return all versioned scope fields with independent ordered JSON arrays."""
        return _wire("research_context", {"question": self.question, **{
            name: list(getattr(self, name)) for name in _CONTEXT_COLLECTIONS}})

    @classmethod
    def from_dict(cls, value: dict) -> "ResearchContext":
        """Decode every required scope declaration, rejecting extra fields and non-arrays."""
        fields = _content_fields(value, "research_context", {"question", *_CONTEXT_COLLECTIONS})
        for name in _CONTEXT_COLLECTIONS:
            fields[name] = _list(fields[name], name)
        return cls(**fields)


@dataclass(frozen=True)
class Claim:
    """A provisional statement with exact context, local assumptions and explicit scope."""

    statement: str
    category: str
    quantifiers: tuple[str, ...]
    context: RecordReference
    assumptions: tuple[NamedAssumption, ...]
    approximation_qualifications: tuple[str, ...]
    open_obligations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate descriptive text and context role; detach all ordered declarations."""
        _text(self.statement, "statement")
        _text(self.category, "category")
        _role(self.context, "context", "research_context", "context")
        for name in ("quantifiers", "approximation_qualifications", "open_obligations"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        object.__setattr__(self, "assumptions", _assumptions(self.assumptions, "assumptions"))

    def to_dict(self) -> dict:
        """Return detached required claim fields; descriptive text cannot promote state."""
        return _wire("claim", {
            "statement": self.statement, "category": self.category,
            "quantifiers": list(self.quantifiers), "context": self.context.to_dict(),
            "assumptions": [item.to_dict() for item in self.assumptions],
            "approximation_qualifications": list(self.approximation_qualifications),
            "open_obligations": list(self.open_obligations),
        })

    @classmethod
    def from_dict(cls, value: dict) -> "Claim":
        """Reconstruct strict claim fields and nested references/assumptions without lookup."""
        fields = _content_fields(value, "claim", {
            "statement", "category", "quantifiers", "context", "assumptions",
            "approximation_qualifications", "open_obligations"})
        fields["context"] = _record_from_dict(fields["context"], "context")
        fields["assumptions"] = _assumption_list(fields["assumptions"], "assumptions")
        for name in ("quantifiers", "approximation_qualifications", "open_obligations"):
            fields[name] = _list(fields[name], name)
        return cls(**fields)


@dataclass(frozen=True)
class Justification:
    """One provisional route whose ordered premises are jointly required, never alternatives."""

    context: RecordReference
    premises: tuple[RecordReference, ...]
    required_assumptions: tuple[NamedAssumption, ...]
    method: str
    conclusions: tuple[RecordReference, ...]
    evidence: tuple[RecordReference, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Freeze one conjunctive route and validate role syntax, without assessing support."""
        _role(self.context, "context", "research_context", "context")
        # Every premise is required; alternative routes are separate values/records.
        object.__setattr__(self, "premises", _roles(self.premises, "premise", "claim", "premises"))
        object.__setattr__(self, "conclusions", _roles(self.conclusions, "conclusion", "claim", "conclusions", True))
        object.__setattr__(self, "evidence", _roles(self.evidence, "evidence", "evidence", "evidence"))
        object.__setattr__(self, "required_assumptions", _assumptions(self.required_assumptions, "required_assumptions"))
        _text(self.method, "method")
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))

    def to_dict(self) -> dict:
        """Return complete detached route fields, retaining conjunction and role boundaries."""
        return _wire("justification", {
            "context": self.context.to_dict(), "premises": [item.to_dict() for item in self.premises],
            "required_assumptions": [item.to_dict() for item in self.required_assumptions],
            "method": self.method, "conclusions": [item.to_dict() for item in self.conclusions],
            "evidence": [item.to_dict() for item in self.evidence], "limitations": list(self.limitations),
        })

    @classmethod
    def from_dict(cls, value: dict) -> "Justification":
        """Decode exactly one route, rejecting malformed fields, roles and duplicate targets."""
        fields = _content_fields(value, "justification", {
            "context", "premises", "required_assumptions", "method", "conclusions", "evidence", "limitations"})
        fields["context"] = _record_from_dict(fields["context"], "context")
        for name in ("premises", "conclusions", "evidence"):
            fields[name] = _record_list(fields[name], name)
        fields["required_assumptions"] = _assumption_list(fields["required_assumptions"], "required_assumptions")
        fields["limitations"] = _list(fields["limitations"], "limitations")
        return cls(**fields)


@dataclass(frozen=True)
class Evidence:
    """Declared synthetic/unverified observations with exact artifacts and structural inputs."""

    artifacts: tuple[ArtifactReference, ...]
    context: RecordReference
    target_property: str
    target_claims: tuple[RecordReference, ...]
    method: str
    input_records: tuple[RecordReference, ...]
    input_artifacts: tuple[ArtifactReference, ...]
    tested_scope: tuple[str, ...]
    result: str
    uncertainty_details: tuple[str, ...]
    failure_details: tuple[str, ...]
    origin: str

    def __post_init__(self) -> None:
        """Validate declared origin and exact roles, freezing collections without trust claims."""
        _role(self.context, "context", "research_context", "context")
        for name in ("target_property", "method", "result"):
            _text(getattr(self, name), name)
        if type(self.origin) is not str or self.origin not in ("synthetic", "unverified"):
            raise DomainValidationError("origin: expected synthetic or unverified")
        object.__setattr__(self, "target_claims", _roles(self.target_claims, "target_claim", "claim", "target_claims"))
        object.__setattr__(self, "input_records", _roles(self.input_records, "input_record", None, "input_records"))
        object.__setattr__(self, "artifacts", _artifacts(self.artifacts, "artifacts", True))
        object.__setattr__(self, "input_artifacts", _artifacts(self.input_artifacts, "input_artifacts"))
        sizes = {item.digest: item.size for item in self.artifacts}
        # The same digest can serve both roles, but cannot describe two byte sizes.
        for item in self.input_artifacts:
            if item.digest in sizes and sizes[item.digest] != item.size:
                raise DomainValidationError("input_artifacts: conflicting size across artifact roles")
        for name in ("tested_scope", "uncertainty_details", "failure_details"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict:
        """Return detached evidence fields with separate output/input artifact role arrays."""
        return _wire("evidence", {
            "artifacts": [item.to_dict() for item in self.artifacts], "context": self.context.to_dict(),
            "target_property": self.target_property,
            "target_claims": [item.to_dict() for item in self.target_claims], "method": self.method,
            "input_records": [item.to_dict() for item in self.input_records],
            "input_artifacts": [item.to_dict() for item in self.input_artifacts],
            "tested_scope": list(self.tested_scope), "result": self.result,
            "uncertainty_details": list(self.uncertainty_details),
            "failure_details": list(self.failure_details), "origin": self.origin,
        })

    @classmethod
    def from_dict(cls, value: dict) -> "Evidence":
        """Strictly decode declared evidence; never authenticate text or resolve inputs."""
        fields = _content_fields(value, "evidence", {
            "artifacts", "context", "target_property", "target_claims", "method", "input_records",
            "input_artifacts", "tested_scope", "result", "uncertainty_details", "failure_details", "origin"})
        fields["context"] = _record_from_dict(fields["context"], "context")
        for name in ("target_claims", "input_records"):
            fields[name] = _record_list(fields[name], name)
        for name in ("artifacts", "input_artifacts"):
            fields[name] = _artifact_list(fields[name], name)
        for name in ("tested_scope", "uncertainty_details", "failure_details"):
            fields[name] = _list(fields[name], name)
        return cls(**fields)


ScientificContent = ResearchContext | Claim | Justification | Evidence


def decode_content(value: dict) -> ScientificContent:
    """Decode explicitly marked version-1 content; distinguish absent format from invalid data."""
    _header(value)
    kind = value.get("kind")
    if type(kind) is not str:
        raise DomainValidationError("kind: required scientific content kind must be a string")
    if kind == "research_context":
        return ResearchContext.from_dict(value)
    if kind == "claim":
        return Claim.from_dict(value)
    if kind == "justification":
        return Justification.from_dict(value)
    if kind == "evidence":
        return Evidence.from_dict(value)
    raise DomainValidationError(f"kind: unsupported scientific content kind {kind!r}")


def dumps_content(value: ScientificContent) -> str:
    """Serialize a typed value as strict canonical ASCII JSON, preserving ordered lists."""
    if type(value) not in (ResearchContext, Claim, Justification, Evidence):
        raise DomainValidationError("content: expected a scientific content value")
    return _snapshot(value.to_dict(), "scientific content")


def _unique_object(pairs: list) -> dict:
    """Build one JSON object while rejecting duplicate keys at every parsing depth."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError(f"scientific content: duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    """Reject JavaScript nonfinite constants instead of accepting nonstandard JSON."""
    raise DomainValidationError(f"scientific content: nonfinite JSON constant {value}")


def loads_content(data: str | bytes) -> ScientificContent:
    """Parse strict UTF-8 JSON and typed fields; report syntax, encoding and depth failures."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("scientific content: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "scientific content JSON")
        value = json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        return decode_content(value)
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"scientific content: cannot decode JSON: {error}") from error


def _links(content: ScientificContent) -> tuple[tuple[RecordReference, ...], tuple[ArtifactReference, ...]]:
    """Project roles in their fixed order, preserving valid occurrences across roles."""
    if type(content) is ResearchContext:
        return (), ()
    if type(content) is Claim:
        return (content.context,), ()
    if type(content) is Justification:
        return (content.context, *content.premises, *content.conclusions, *content.evidence), ()
    if type(content) is Evidence:
        # ArtifactReference has no role label. Named arrays and their lengths define
        # the boundary in this fixed projection; cross-role occurrences stay twice.
        return ((content.context, *content.target_claims, *content.input_records),
                (*content.artifacts, *content.input_artifacts))
    raise DomainValidationError("content: expected a scientific content value")


def encode_envelope(record_id: str, revision: int, content: ScientificContent,
                    provenance: CreationProvenance) -> RecordEnvelope:
    """Create an exact coherent envelope with explicit attribution and canonical provisional state."""
    content = loads_content(dumps_content(content))
    records, artifacts = _links(content)
    document = content.to_dict()
    return RecordEnvelope(record_id, revision, document["kind"], document, provenance,
                          records, artifacts, operational_status=None,
                          scientific_disposition="provisional" if type(content) is Claim else None)


def decode_envelope(envelope: RecordEnvelope) -> ScientificContent:
    """Return detached typed content only when generic state, kind and all ordered links agree."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected RecordEnvelope")
    try:
        checked = RecordEnvelope.from_dict(envelope.to_dict())
    except (AttributeError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, DomainValidationError):
            raise
        raise DomainValidationError("envelope: malformed nested value") from error
    content = decode_content(checked.content)
    if checked.kind != content.to_dict()["kind"]:
        raise DomainValidationError("envelope.kind: disagrees with scientific content kind")
    records, artifacts = _links(content)
    if checked.record_references != records:
        raise DomainValidationError("envelope.record_references: disagree with complete ordered content roles")
    if checked.artifact_references != artifacts:
        raise DomainValidationError("envelope.artifact_references: disagree with complete ordered content roles")
    return content
