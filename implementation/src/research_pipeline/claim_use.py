"""Passive exact claim-use bindings and bounded, detached freshness observations.

These declarations never authorize scientific disposition or positive eligibility.
"""

from dataclasses import dataclass
import json
from types import MappingProxyType

from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, RecordEnvelope, RecordReference,
    _fields, _integer, _snapshot, _MAX_INTEGER,
)
from research_pipeline.assessment import (
    _copy, _rebuild, _reference, _references,
)
from research_pipeline.scientific import NotTypedContentError, _collection, _list, _texts
from research_pipeline.schema import _json
from research_pipeline.snapshot import _check_json_depth

FORMAT = "research_pipeline.claim_use_content"
WRITE_LIMITS = MappingProxyType(dict(
    routes=16, premises=256, direct_references=512, request_bytes=8*1024*1024,
    record_bytes=1024*1024, metadata_bytes=64*1024*1024, records=1024,
    references=8192, assertion_revisions=1024, policy_revisions=1024, bindings=512, index_rows=8192,
    context_revisions=1024, context_observations=512,
    transitions=128, causes=8192, support_depth=64, artifacts=256,
    artifact_bytes=64*1024*1024,
))


class ClaimUseLimitError(DomainValidationError):
    """A finite independent claim-use operation ceiling was exhausted; no partial write."""


class ClaimUseIntegrityError(ValueError):
    """Stored freshness metadata disagrees with exact immutable submission history."""


def _check_count(value, maximum, name):
    """Reject an occurrence count before work can exceed its public hard ceiling."""
    if value > maximum:
        raise ClaimUseLimitError(f"{name}: claim-use limit {maximum} exceeded")


@dataclass(frozen=True)
class ClaimUsePremise:
    """An ordered conjunctive premise and an optional exact registered support binding."""

    claim: RecordReference
    upstream_use: RecordReference | None

    def __post_init__(self):
        """Detach exact required roles; null means support is unrecorded, never sufficient."""
        object.__setattr__(self, "claim", _reference(self.claim, "premise", "claim", "claim"))
        if self.upstream_use is not None:
            object.__setattr__(self, "upstream_use", _reference(
                self.upstream_use, "premise_use", "promotion_eligibility", "upstream_use"))

    def to_dict(self):
        """Return fresh exact fields, defensively checking frozen instances."""
        value = _rebuild(self, ClaimUsePremise, "premise")
        return dict(claim=value.claim.to_dict(), upstream_use=(
            value.upstream_use.to_dict() if value.upstream_use is not None else None))

    @classmethod
    def from_dict(cls, value):
        """Decode both mandatory fields, including explicit null upstream support."""
        _snapshot(value, "premise")
        data = _fields(value, {"claim", "upstream_use"}, set(), "premise")
        return cls(RecordReference.from_dict(data["claim"]),
                   None if data["upstream_use"] is None else RecordReference.from_dict(data["upstream_use"]))


@dataclass(frozen=True)
class ClaimUseRoute:
    """One separate recorded alternative, preserving its complete premise conjunction."""

    justification: RecordReference
    premises: tuple[ClaimUsePremise, ...]
    assessments: tuple[RecordReference, ...]

    def __post_init__(self):
        """Detach route roles and require at least one attributed assessment pin."""
        object.__setattr__(self, "justification", _reference(
            self.justification, "support_route", "justification", "justification"))
        premises = _collection(self.premises, "premises")
        _check_count(len(premises), WRITE_LIMITS["premises"], "premises")
        object.__setattr__(self, "premises", tuple(_copy(p, ClaimUsePremise, "premise") for p in premises))
        _check_count(len(_collection(self.assessments, "assessments")), WRITE_LIMITS["direct_references"], "direct_references")
        assessments = _references(self.assessments, "support_assessment", "review", "assessments")
        if not assessments:
            raise DomainValidationError("assessments: at least one assessment per route is required")
        object.__setattr__(self, "assessments", assessments)

    def to_dict(self):
        """Return a detached conjunction and its ordered historical assessment pins."""
        value = _rebuild(self, ClaimUseRoute, "route")
        return dict(justification=value.justification.to_dict(),
                    premises=[p.to_dict() for p in value.premises],
                    assessments=[r.to_dict() for r in value.assessments])

    @classmethod
    def from_dict(cls, value):
        """Decode required route arrays without flattening alternatives or premises."""
        _snapshot(value, "route")
        data = _fields(value, {"justification", "premises", "assessments"}, set(), "route")
        return cls(RecordReference.from_dict(data["justification"]),
                   [ClaimUsePremise.from_dict(p) for p in _list(data["premises"], "premises")],
                   [RecordReference.from_dict(r) for r in _list(data["assessments"], "assessments")])


@dataclass(frozen=True)
class ClaimUse:
    """An exact, versioned use binding; registration always requires reassessment."""

    candidate_claim: RecordReference
    target_context: RecordReference
    routes: tuple[ClaimUseRoute, ...]
    issues: tuple[RecordReference, ...]
    policies: tuple[RecordReference, ...]
    limitations: tuple[str, ...]

    def __post_init__(self):
        """Detach required fields and reject duplicate alternatives and policy-free bindings."""
        for name, kind in (("candidate_claim", "claim"), ("target_context", "research_context")):
            object.__setattr__(self, name, _reference(getattr(self, name), name, kind, name))
        routes = _collection(self.routes, "routes")
        _check_count(len(routes), WRITE_LIMITS["routes"], "routes")
        routes = tuple(_copy(r, ClaimUseRoute, "route") for r in routes)
        if len({r.justification for r in routes}) != len(routes):
            raise DomainValidationError("routes: repeated exact route")
        object.__setattr__(self, "routes", routes)
        for name, role, kind in (("issues", "relevant_issue", "issue"),
                                 ("policies", "authorization_policy", "decision")):
            _check_count(len(_collection(getattr(self, name), name)), WRITE_LIMITS["direct_references"], "direct_references")
            object.__setattr__(self, name, _references(getattr(self, name), role, kind, name))
        if not self.policies:
            raise DomainValidationError("policies: at least one policy is required")
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        _check_count(sum(len(r.premises) for r in routes), WRITE_LIMITS["premises"], "premises")
        _check_count(len(_links(self)), WRITE_LIMITS["direct_references"], "direct_references")

    def to_dict(self):
        """Return strict versioned content without eligibility or disposition fields."""
        value = _rebuild(self, ClaimUse, "claim_use")
        return dict(format=FORMAT, version=1, kind="claim_use",
                    candidate_claim=value.candidate_claim.to_dict(), target_context=value.target_context.to_dict(),
                    routes=[r.to_dict() for r in value.routes], issues=[r.to_dict() for r in value.issues],
                    policies=[r.to_dict() for r in value.policies], limitations=list(value.limitations))

    @classmethod
    def from_dict(cls, value):
        """Decode only the explicit supported discriminator and all required arrays."""
        _snapshot(value, "claim_use")
        if "format" not in value:
            raise NotTypedContentError("claim_use: missing format discriminator")
        data = _fields(value, {"format", "version", "kind", "candidate_claim", "target_context",
                               "routes", "issues", "policies", "limitations"}, set(), "claim_use")
        if data.pop("format") != FORMAT or type(value["format"]) is not str:
            raise DomainValidationError("format: unsupported claim-use content format")
        version = data.pop("version")
        _integer(version, "version", 1)
        if version != 1 or data.pop("kind") != "claim_use":
            raise DomainValidationError("version/kind: unsupported claim-use content")
        for name in ("candidate_claim", "target_context"):
            data[name] = RecordReference.from_dict(data[name])
        data["routes"] = [ClaimUseRoute.from_dict(r) for r in _list(data["routes"], "routes")]
        for name in ("issues", "policies"):
            data[name] = [RecordReference.from_dict(r) for r in _list(data[name], name)]
        data["limitations"] = _list(data["limitations"], "limitations")
        return cls(**data)


def decode_content(value):
    """Decode an explicit passive claim-use document; missing format remains distinguishable."""
    return ClaimUse.from_dict(value)


def dumps_content(value):
    """Encode validated detached content as canonical JSON with ordered arrays."""
    if type(value) is not ClaimUse:
        raise DomainValidationError("content: expected exact ClaimUse")
    return _snapshot(value.to_dict(), "claim_use")


def loads_content(data):
    """Decode strict JSON, rejecting duplicates, invalid Unicode, nonfinite values and depth."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("claim_use: expected ordinary str or bytes")
    try:
        text = data.decode("utf-8", errors="strict") if type(data) is bytes else data
        _check_json_depth(text)
        return decode_content(_json(text))
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"claim_use: invalid JSON: {error}") from error


def _links(value):
    """Project every occurrence in candidate/context, route, issue and policy order."""
    refs = [value.candidate_claim, value.target_context]
    for route in value.routes:
        refs.append(route.justification)
        for premise in route.premises:
            refs.append(premise.claim)
            if premise.upstream_use is not None:
                refs.append(premise.upstream_use)
        refs.extend(route.assessments)
    return (*refs, *value.issues, *value.policies)


def encode_envelope(record_id, revision, content, provenance):
    """Build a passive promotion_eligibility envelope; the kind conveys no promotion."""
    value = loads_content(dumps_content(content))
    return RecordEnvelope(record_id, revision, "promotion_eligibility", value.to_dict(),
                          _copy(provenance, CreationProvenance, "provenance"), _links(value), (),
                          operational_status=None, scientific_disposition=None)


def decode_envelope(envelope):
    """Require the complete ordered projection and empty artifacts with null canonical states."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected exact RecordEnvelope")
    for reference in _collection(envelope.record_references, "record_references"):
        _copy(reference, RecordReference, "record_references")
    checked = _copy(envelope, RecordEnvelope, "envelope")
    content = decode_content(checked.content)
    if (checked.kind != "promotion_eligibility" or checked.operational_status is not None
            or checked.scientific_disposition is not None or checked.artifact_references
            or checked.record_references != _links(content)):
        raise DomainValidationError("envelope: claim-use kind, states, artifacts or ordered projection disagree")
    return content


@dataclass(frozen=True)
class ClaimUseInspectionLimits:
    """Required independent read ceilings; no read may silently truncate its graph."""

    max_bindings: int
    max_records: int
    max_references: int
    max_assertion_revisions: int
    max_metadata_bytes: int
    max_result_bytes: int

    def __post_init__(self):
        """Require ordinary positive integers within write ceilings and a 4 MiB result."""
        for name, ceiling in (("max_bindings", WRITE_LIMITS["bindings"]),
                              ("max_records", WRITE_LIMITS["records"]),
                              ("max_references", WRITE_LIMITS["references"]),
                              ("max_assertion_revisions", WRITE_LIMITS["assertion_revisions"]),
                              ("max_metadata_bytes", WRITE_LIMITS["metadata_bytes"]),
                              ("max_result_bytes", 4*1024*1024)):
            value = getattr(self, name)
            _integer(value, name, 1)
            if value > ceiling:
                raise DomainValidationError(f"{name}: must be at most {ceiling}")


@dataclass(frozen=True)
class ClaimUseInspection:
    """Canonical private JSON for a detached coherent current view; no mutable aliases."""

    _json: str

    def __post_init__(self):
        """Retain only ordinary bounded canonical object JSON, never a caller-owned container."""
        if type(self._json) is not str:
            raise DomainValidationError("observation: expected canonical private JSON text")
        _check_count(len(self._json), 4*1024*1024, "result_bytes")
        try:
            _check_json_depth(self._json)
            document = _json(self._json)
            if _snapshot(document, "observation") != self._json:
                raise DomainValidationError("observation: expected canonical object JSON")
        except (ValueError, TypeError, UnicodeError, RecursionError) as error:
            raise DomainValidationError(f"observation: invalid private JSON: {error}") from error

    def to_dict(self):
        """Return a fresh document; changing it cannot change the retained observation."""
        return json.loads(self._json)


@dataclass(frozen=True)
class ClaimUseHistoryPage:
    """Canonical private JSON for a generation-ordered immutable history page."""

    _json: str

    def __post_init__(self):
        """Retain only ordinary bounded canonical object JSON, never a caller-owned container."""
        if type(self._json) is not str:
            raise DomainValidationError("observation: expected canonical private JSON text")
        _check_count(len(self._json), 4*1024*1024, "result_bytes")
        try:
            _check_json_depth(self._json)
            document = _json(self._json)
            if _snapshot(document, "observation") != self._json:
                raise DomainValidationError("observation: expected canonical object JSON")
        except (ValueError, TypeError, UnicodeError, RecursionError) as error:
            raise DomainValidationError(f"observation: invalid private JSON: {error}") from error

    def to_dict(self):
        """Return detached transitions and an explicit continuation cursor."""
        return json.loads(self._json)
