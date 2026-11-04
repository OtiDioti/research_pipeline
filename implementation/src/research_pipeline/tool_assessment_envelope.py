"""Pure bounded assessment envelopes; projections and provenance remain unauthenticated data."""

from dataclasses import dataclass, fields
import json
import math
import re

from research_pipeline import domain
from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope, RecordReference,
)
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_assessment import (
    ToolAssessment, _checked_tree, _finish, _known, _known_items, _DIMENSIONS,
)
from research_pipeline.tool_assessment_codec import (
    ToolAssessmentLimits, ToolAssessmentValidationError, ToolAssessmentLimitError,
    _checked_limits, _raw_attribute, _parse, _canonical,
)


@dataclass(frozen=True, slots=True)
class ToolAssessmentEnvelopeLimits:
    """Independent metadata, projection and provenance-depth ceilings, bounded by defaults."""

    max_metadata_chars: int = 262144
    max_projection_references: int = 1024
    max_provenance_depth: int = 24

    def __post_init__(self):
        """Validate exact constructor receiver and each external ceiling."""
        _checked_envelope_limits(self)


def _checked_envelope_limits(value):
    """Create fresh defaults or revalidate exact retained limits, including bypass mutations."""
    if value is None:
        return ToolAssessmentEnvelopeLimits()
    if type(value) is not ToolAssessmentEnvelopeLimits:
        raise ToolAssessmentValidationError("envelope_limits: expected exact ToolAssessmentEnvelopeLimits")
    for field in fields(ToolAssessmentEnvelopeLimits):
        number = _raw_attribute(value, field.name)
        if type(number) is not int or not 0 <= number <= field.default:
            raise ToolAssessmentValidationError(f"{field.name}: invalid processing ceiling")
    return value


def _limit(limits, name, amount):
    """Reject an exceeded envelope ceiling before its protected operation."""
    if amount > _raw_attribute(limits, name):
        raise ToolAssessmentLimitError(f"{name}: processing ceiling exceeded")


def _characters(total, value, limits):
    """Charge exact metadata text length before scanning, parsing or copying it."""
    if type(value) is not str:
        raise ToolAssessmentValidationError("metadata: expected exact string")
    total += len(value)
    _limit(limits, "max_metadata_chars", total)
    return total


def _base_metadata(record_id, revision, kind, provenance, limits):
    """Read and size base raw metadata; syntax validation waits for all supplied text."""
    total = _characters(0, record_id, limits)
    if type(revision) is not int:
        raise ToolAssessmentValidationError("revision: expected exact integer")
    total = _characters(total, kind, limits)
    if type(provenance) is not CreationProvenance:
        raise ToolAssessmentValidationError("provenance: expected exact CreationProvenance")
    actor = _raw_attribute(provenance, "actor")
    total = _characters(total, actor, limits)
    created_at = _raw_attribute(provenance, "created_at")
    total = _characters(total, created_at, limits)
    details = _raw_attribute(provenance, "_details_json")
    total = _characters(total, details, limits)
    return total, (actor, created_at, details)


def _supplied_projections(envelope, limits):
    """Bound both exact retained tuples before inspecting any reference element."""
    records = _raw_attribute(envelope, "record_references")
    artifacts = _raw_attribute(envelope, "artifact_references")
    if type(records) is not tuple or type(artifacts) is not tuple:
        raise ToolAssessmentValidationError("projections: expected exact retained tuples")
    _limit(limits, "max_projection_references", len(records) + len(artifacts))
    return records, artifacts


def _supplied_fields(records, artifacts, total, limits):
    """Read fixed reference attributes and complete supplied metadata bounds before syntax checks."""
    result_records, result_artifacts = [], []
    for reference in records:
        if type(reference) is not RecordReference:
            raise ToolAssessmentValidationError("record projection: expected exact RecordReference")
        item = {}
        for name in ("record_id", "revision", "relationship", "target_kind"):
            value = _raw_attribute(reference, name)
            if name == "revision":
                if type(value) is not int:
                    raise ToolAssessmentValidationError("reference revision: expected exact integer")
            else:
                total = _characters(total, value, limits)
            item[name] = value
        result_records.append(item)
    for reference in artifacts:
        if type(reference) is not ArtifactReference:
            raise ToolAssessmentValidationError("artifact projection: expected exact ArtifactReference")
        digest = _raw_attribute(reference, "digest")
        total = _characters(total, digest, limits)
        size = _raw_attribute(reference, "size")
        if type(size) is not int:
            raise ToolAssessmentValidationError("artifact size: expected exact integer")
        result_artifacts.append({"digest": digest, "size": size})
    return tuple(result_records), tuple(result_artifacts)


def _metadata_syntax(record_id, revision, kind, provenance_fields, supplied):
    """Validate bounded scalar syntax without reconstructing provenance or references."""
    domain._identifier(record_id, "record_id")
    domain._integer(revision, "revision", 1)
    if kind != "tool_assessment":
        raise ToolAssessmentValidationError("kind: expected tool_assessment")
    actor, created_at, _ = provenance_fields
    domain._identifier(actor, "provenance.actor")
    if domain._timestamp(created_at) != created_at:
        raise ToolAssessmentValidationError("provenance.created_at: noncanonical retained timestamp")
    if supplied is None:
        return
    for item in supplied[0]:
        domain._identifier(item["record_id"], "reference.record_id")
        domain._integer(item["revision"], "reference.revision", 1)
        domain._identifier(item["relationship"], "reference.relationship")
        domain._kind(item["target_kind"], "reference.target_kind")
    for item in supplied[1]:
        if re.fullmatch(r"[0-9a-f]{64}", item["digest"]) is None:
            raise ToolAssessmentValidationError("artifact.digest: invalid SHA-256")
        domain._integer(item["size"], "artifact.size", 0)


def _record_candidates(tree):
    """Yield every record occurrence in the fixed v1 order, independent of JSON key order."""
    yield tree["target"]["release"]
    environment = tree["environment"]
    yield from _known_items(environment["records"])
    for dependency in _known_items(environment["dependencies"]):
        yield from _known_items(dependency["records"])
    for check in _known_items(tree["checks"]):
        yield from _known_items(check["definition_records"])
        for evidence in _known_items(check["evidence"]):
            yield from _known_items(evidence["records"])
    for review in _known_items(tree["reviews"]):
        yield review["review"]
        for evidence in _known_items(review["evidence"]):
            yield from _known_items(evidence["records"])
    for issue in _known_items(tree["issues"]):
        yield issue["issue"]
        for evidence in _known_items(issue["evidence"]):
            yield from _known_items(evidence["records"])
    for report in (tree["execution_permission"], *(tree["qualification"][name] for name in _DIMENSIONS), tree["lifecycle"]):
        yield from _known_items(report["decisions"])
        for evidence in _known_items(report["evidence"]):
            yield from _known_items(evidence["records"])
    lifecycle = tree["lifecycle"]
    if _known(lifecycle["replacement"]):
        yield lifecycle["replacement"]["value"]["release"]
    yield from _known_items(lifecycle["supersedes"])
    if _known(lifecycle["superseded_by"]):
        yield lifecycle["superseded_by"]["value"]


def _artifact_candidates(tree):
    """Yield artifact candidates in the separately prescribed order without flattening them."""
    environment = tree["environment"]
    yield from _known_items(environment["artifacts"])
    for dependency in _known_items(environment["dependencies"]):
        yield from _known_items(dependency["artifacts"])
    for check in _known_items(tree["checks"]):
        yield from _known_items(check["definition_artifacts"])
        for evidence in _known_items(check["evidence"]):
            yield from _known_items(evidence["artifacts"])
    for field in ("reviews", "issues"):
        for report in _known_items(tree[field]):
            for evidence in _known_items(report["evidence"]):
                yield from _known_items(evidence["artifacts"])
    for report in (tree["execution_permission"],
                   *(tree["qualification"][name] for name in _DIMENSIONS), tree["lifecycle"]):
        for evidence in _known_items(report["evidence"]):
            yield from _known_items(evidence["artifacts"])


def _projections(tree, total, limits):
    """Guard derived counts and complete metadata incrementally before appending entries.

    Supplied and derived projections start from the same base and are charged
    independently. All artifact occurrences are content-validated, even those
    omitted here after their digest's first occurrence.
    """
    records, artifacts, seen = [], [], set()
    for item in _record_candidates(tree):
        _limit(limits, "max_projection_references", len(records) + 1)
        for name in ("record_id", "relationship", "target_kind"):
            total = _characters(total, item[name], limits)
        records.append(item)
    for item in _artifact_candidates(tree):
        if item["digest"] not in seen:
            _limit(limits, "max_projection_references", len(records) + len(artifacts) + 1)
            total = _characters(total, item["digest"], limits)
            seen.add(item["digest"])
            artifacts.append(item)
    return tuple(records), tuple(artifacts)


def _provenance_depth(text, limits):
    """Bound retained ASCII JSON nesting before parsing with an escape-aware bracket stack.

    For n already charged ASCII characters, token lengths, decoded string lengths,
    memberships and node counts are each at most n; these are upper bounds, not
    simultaneous attainable equalities. Only depth-sized scanner state is kept.
    """
    if not text.isascii():
        raise ToolAssessmentValidationError("provenance: expected canonical ASCII JSON")
    stack = []
    quoted = escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            _limit(limits, "max_provenance_depth", len(stack) + 1)
            stack.append(character)
        elif character in "]}":
            if not stack or stack.pop() != ("[" if character == "]" else "{"):
                raise ToolAssessmentValidationError("provenance: mismatched JSON brackets")
    if quoted or stack:
        raise ToolAssessmentValidationError("provenance: incomplete retained JSON")


def _pairs(pairs):
    """Reject duplicate decoded provenance keys while allowing generic JSON scalars."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ToolAssessmentValidationError("provenance: duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    """Reject nonfinite JSON constants without exposing the supplied details document."""
    raise ToolAssessmentValidationError("provenance: nonfinite JSON constant")


def _finite_float(value):
    """Parse a bounded JSON float and reject overflow to infinity."""
    result = float(value)
    if not math.isfinite(result):
        raise ToolAssessmentValidationError("provenance: nonfinite parsed float")
    return result


def _provenance(provenance_fields, limits):
    """Reconstruct bounded generic details and reject every retained normalization opportunity."""
    actor, created_at, text = provenance_fields
    _provenance_depth(text, limits)
    details = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant,
                         parse_float=_finite_float)
    if type(details) is not dict:
        raise ToolAssessmentValidationError("provenance: details must be an ordinary object")
    result = CreationProvenance(actor, created_at, details)
    if (_raw_attribute(result, "created_at") != created_at
            or _raw_attribute(result, "_details_json") != text):
        raise ToolAssessmentValidationError("provenance: noncanonical retained snapshot")
    return result


def _convert(receiver, record_id, revision, provenance, limits, envelope_limits, *, decoding):
    """Apply ordered A–F guards and reconstruct only after independent quotas succeed."""
    try:
        limits = _checked_limits(limits)
        envelope_limits = _checked_envelope_limits(envelope_limits)
        if type(receiver) is not (RecordEnvelope if decoding else ToolAssessment):
            raise ToolAssessmentValidationError("receiver: expected exact assessment or envelope")
        kind, supplied = "tool_assessment", None
        if decoding:
            record_id = _raw_attribute(receiver, "record_id")
            revision = _raw_attribute(receiver, "revision")
            kind = _raw_attribute(receiver, "kind")
            provenance = _raw_attribute(receiver, "provenance")
            for name in ("operational_status", "scientific_disposition"):
                if _raw_attribute(receiver, name) is not None:
                    raise ToolAssessmentValidationError("envelope: both states must be null")
            supplied = _supplied_projections(receiver, envelope_limits)
        total, provenance_fields = _base_metadata(record_id, revision, kind, provenance, envelope_limits)
        if supplied is not None:
            supplied = _supplied_fields(*supplied, total, envelope_limits)
        _metadata_syntax(record_id, revision, kind, provenance_fields, supplied)

        # C: no reference construction or provenance parsing during this schema pass.
        text = _raw_attribute(receiver, "_content_json" if decoding else "_json")
        tree = _checked_tree(_parse(text, limits, retained=True), limits)
        # D: prospective quotas cannot be hidden by a shortened supplied projection.
        records, artifacts = _projections(tree, total, envelope_limits)
        # E: generic snapshots and full reference semantics are protected by both quotas.
        fresh_provenance = _provenance(provenance_fields, envelope_limits)
        tree = _finish(tree)
        canonical = _canonical(tree)
        if canonical != text:
            raise ToolAssessmentValidationError("content: noncanonical retained snapshot")
        if record_id != tree["assessment_id"]:
            raise ToolAssessmentValidationError("record_id: does not match assessment_id")
        if supplied is not None and supplied != (records, artifacts):
            raise ToolAssessmentValidationError("projections: disagree with complete ordered content references")
        if decoding:
            result = object.__new__(ToolAssessment)
            object.__setattr__(result, "_json", canonical)
            return result
        fresh_records = tuple(RecordReference(**item) for item in records)
        fresh_artifacts = tuple(ArtifactReference(**item) for item in artifacts)
        return RecordEnvelope(record_id, revision, kind, tree, fresh_provenance,
                              fresh_records, fresh_artifacts,
                              operational_status=None, scientific_disposition=None)
    except (ToolAssessmentValidationError, NotTypedContentError):
        raise
    except (DomainValidationError, ValueError, TypeError, AttributeError, RecursionError, OverflowError) as error:
        raise ToolAssessmentValidationError("envelope: invalid retained assessment fields") from error


def encode_envelope(record_id: str, revision: int, content: ToolAssessment,
                    provenance: CreationProvenance, *, limits: ToolAssessmentLimits | None = None,
                    envelope_limits: ToolAssessmentEnvelopeLimits | None = None) -> RecordEnvelope:
    """Create a fresh passive envelope after bounded validation of explicit identity and creator.

    No targets or artifact bytes are read. Assessment validation/limit errors report
    malformed retained fields or exceeded ceilings; creator and reported actors may differ.
    """
    return _convert(content, record_id, revision, provenance, limits, envelope_limits, decoding=False)


def decode_envelope(envelope: RecordEnvelope, *, limits: ToolAssessmentLimits | None = None,
                    envelope_limits: ToolAssessmentEnvelopeLimits | None = None) -> ToolAssessment:
    """Return fresh content only for exact null-state envelopes with complete ordered projections.

    Reject inconsistencies without repair or reference resolution. Missing format
    retains NotTypedContentError; other expected failures use assessment-specific errors.
    """
    return _convert(envelope, None, None, None, limits, envelope_limits, decoding=True)
