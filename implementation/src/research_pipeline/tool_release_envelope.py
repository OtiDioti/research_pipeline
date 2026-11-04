"""Bounded, passive ToolRelease envelopes; local consistency is not authenticity.

Retained fields are inspected without dispatching supplied methods. Complete
metadata and projection guards precede provenance/reference reconstruction and
all generic copying. Content has its own independent lexical and schema guards.
"""

from dataclasses import dataclass, fields
import json
import re

from research_pipeline import domain
from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError,
    RecordEnvelope, RecordReference,
)
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_release import ToolRelease, _ROOT, _SchemaCheck
from research_pipeline.tool_release_codec import (
    ToolReleaseLimits, ToolReleaseLimitError, ToolReleaseValidationError,
    checked_limits, parse, preflight, raw_attribute,
)


@dataclass(frozen=True, slots=True)
class ToolReleaseEnvelopeLimits:
    """Independent envelope ceilings, accepting exact integers from zero to defaults."""

    max_metadata_chars: int = 262144
    max_projection_references: int = 1024

    def __post_init__(self):
        """Validate the exact receiver and both ceilings, including constructor aliases."""
        _checked_envelope_limits(self)


def _checked_envelope_limits(value):
    """Create defaults or revalidate retained ceilings without trusting frozen fields."""
    if value is None:
        return ToolReleaseEnvelopeLimits()
    if type(value) is not ToolReleaseEnvelopeLimits:
        raise ToolReleaseValidationError("envelope_limits: expected exact ToolReleaseEnvelopeLimits")
    for field in fields(ToolReleaseEnvelopeLimits):
        number = raw_attribute(value, field.name)
        if type(number) is not int or not 0 <= number <= field.default:
            raise ToolReleaseValidationError(f"{field.name}: invalid processing ceiling")
    return value


def _limit(limits, name, amount):
    """Reject an exceeded envelope ceiling with its name and no supplied document."""
    if amount > raw_attribute(limits, name):
        raise ToolReleaseLimitError(f"{name}: processing ceiling exceeded")


def _characters(total, value, limits):
    """Charge exact retained text before scanning, encoding or copying its contents."""
    if type(value) is not str:
        raise ToolReleaseValidationError("metadata: expected exact string")
    total += len(value)
    _limit(limits, "max_metadata_chars", total)
    return total


def _base_metadata(record_id, revision, kind, provenance, limits):
    """Read and bound fixed envelope/provenance fields without generic serialization."""
    if type(provenance) is not CreationProvenance:
        raise ToolReleaseValidationError("provenance: expected exact CreationProvenance")
    if type(revision) is not int:
        raise ToolReleaseValidationError("revision: expected exact integer")
    actor = raw_attribute(provenance, "actor")
    created_at = raw_attribute(provenance, "created_at")
    details = raw_attribute(provenance, "_details_json")
    total = 0
    for value in (record_id, kind, actor, created_at, details):
        total = _characters(total, value, limits)
    if kind != "tool_release":
        raise ToolReleaseValidationError("kind: expected tool_release")
    domain._identifier(record_id, "record_id")
    domain._integer(revision, "revision", 1)
    return total, (actor, created_at, details)


def _supplied_projections(envelope, limits):
    """Reject oversized exact tuples before visiting any supplied reference element."""
    records = raw_attribute(envelope, "record_references")
    artifacts = raw_attribute(envelope, "artifact_references")
    if type(records) is not tuple or type(artifacts) is not tuple:
        raise ToolReleaseValidationError("projections: expected exact retained tuples")
    _limit(limits, "max_projection_references", len(records) + len(artifacts))
    return records, artifacts


def _reference_fields(values, expected, names):
    """Read bounded exact reference instances through fixed raw fields, never serializers."""
    result = []
    for value in values:
        if type(value) is not expected:
            raise ToolReleaseValidationError("projection: expected exact reference class")
        result.append({name: raw_attribute(value, name) for name in names})
    return tuple(result)


def _projection_metadata(records, artifacts, total, limits):
    """Count every record occurrence and selected artifact, then validate raw scalar syntax."""
    _limit(limits, "max_projection_references", len(records) + len(artifacts))
    for item in records:
        for name in ("record_id", "relationship", "target_kind"):
            total = _characters(total, item[name], limits)
        domain._integer(item["revision"], "reference revision", 1)
        domain._identifier(item["record_id"], "reference record_id")
        domain._identifier(item["relationship"], "relationship")
        domain._kind(item["target_kind"], "target_kind")
    for item in artifacts:
        total = _characters(total, item["digest"], limits)
        domain._integer(item["size"], "artifact size", 0)
        if re.fullmatch(r"[0-9a-f]{64}", item["digest"]) is None:
            raise ToolReleaseValidationError("digest: invalid artifact identity")


def _known_items(fact):
    """Yield only known collection entries from a bounded schema-checked fact."""
    if fact["state"] == "known":
        yield from fact["value"]


def _projections(tree, limits):
    """Select fixed version-one slots, retaining record occurrences and first artifact digests.

    Content preflight already bounds candidate digest-set work. Do not flatten
    the candidate inventory or reconstruct references before envelope guards.
    """
    identity, evidence = tree["identity"], tree["evidence_limitations"]
    implementation = identity["implementation"]
    reproducibility = tree["reproducibility"]
    records, artifacts, seen = [], [], set()
    for fact in (identity["provenance_records"], implementation["source_records"],
                 tree["effects_authority"]["child_tools"], evidence["qualification_reports"],
                 evidence["evidence"], evidence["issues"], reproducibility["dependency_records"]):
        for item in _known_items(fact):
            _limit(limits, "max_projection_references", len(records) + 1)
            records.append(item)
    for fact, files in ((implementation["artifacts"], True),
                        (tree["invocation"]["adapter"]["files"], True),
                        (evidence["self_tests"], False),
                        (reproducibility["dependency_artifacts"], False)):
        for item in _known_items(fact):
            artifact = item["artifact"] if files else item
            digest = artifact["digest"]
            if digest not in seen:
                _limit(limits, "max_projection_references", len(records) + len(artifacts) + 1)
                seen.add(digest)
                artifacts.append(artifact)
    return tuple(records), tuple(artifacts)


def _pairs(pairs):
    """Reject duplicate provenance JSON keys without restricting generic JSON scalar types."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ToolReleaseValidationError("provenance: duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    """Reject nonfinite JSON constants without reporting the supplied details document."""
    raise ToolReleaseValidationError("provenance: nonfinite JSON constant")


def _provenance(fields):
    """Reconstruct bounded generic details and demand unchanged canonical retained spelling."""
    actor, created_at, text = fields
    # ASCII canonical text makes the earlier character guard a byte/allocation
    # bound too. Generic details may contain booleans, negative numbers and floats.
    if not text.isascii():
        raise ToolReleaseValidationError("provenance: retained details must be canonical ASCII JSON")
    details = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    if type(details) is not dict:
        raise ToolReleaseValidationError("provenance: details must be an ordinary object")
    result = CreationProvenance(actor, created_at, details)
    if (raw_attribute(result, "created_at") != created_at
            or raw_attribute(result, "_details_json") != text):
        raise ToolReleaseValidationError("provenance: noncanonical retained snapshot")
    return result


def _convert(receiver, record_id, revision, provenance, limits, envelope_limits, *, decoding):
    """Apply ordered preflight, reconstruction and exact comparison for either boundary.

    Earlier stages win: supplied metadata precedes content parsing; derived
    metadata precedes all full content validation and generic snapshots. A
    coherent forged detached declaration can pass; this establishes no authenticity.
    """
    try:
        limits = checked_limits(limits)
        envelope_limits = _checked_envelope_limits(envelope_limits)
        expected_class = RecordEnvelope if decoding else ToolRelease
        if type(receiver) is not expected_class:
            raise ToolReleaseValidationError("receiver: expected exact envelope or release")
        supplied = None
        kind = "tool_release"
        if decoding:
            record_id = raw_attribute(receiver, "record_id")
            revision = raw_attribute(receiver, "revision")
            kind = raw_attribute(receiver, "kind")
            provenance = raw_attribute(receiver, "provenance")
            for name in ("operational_status", "scientific_disposition"):
                if raw_attribute(receiver, name) is not None:
                    raise ToolReleaseValidationError("envelope: both states must be null")
            supplied = _supplied_projections(receiver, envelope_limits)
        total, provenance_fields = _base_metadata(record_id, revision, kind, provenance, envelope_limits)
        if supplied is not None:
            records = _reference_fields(supplied[0], RecordReference,
                                        ("record_id", "revision", "relationship", "target_kind"))
            artifacts = _reference_fields(supplied[1], ArtifactReference, ("digest", "size"))
            _projection_metadata(records, artifacts, total, envelope_limits)
            supplied = records, artifacts

        text = raw_attribute(receiver, "_content_json" if decoding else "_json")
        tree = parse(text, limits, retained=True)
        units = preflight(tree, limits)
        if type(tree) is not dict:
            raise ToolReleaseValidationError("content: expected ordinary dictionary")
        if "format" not in tree:
            raise NotTypedContentError("tool release content: missing format discriminator")
        _SchemaCheck(limits, False, units).visit(tree, _ROOT, "content")
        records, artifacts = _projections(tree, envelope_limits)
        # Independently charge the prospective envelope, not supplied + expected.
        _projection_metadata(records, artifacts, total, envelope_limits)
        fresh_provenance = _provenance(provenance_fields)
        release = ToolRelease.from_dict(tree, limits=limits)
        if raw_attribute(release, "_json") != text:
            raise ToolReleaseValidationError("content: noncanonical retained snapshot")
        if record_id != tree["identity"]["tool_id"]:
            raise ToolReleaseValidationError("record_id: does not match stable tool_id")

        if supplied is not None:
            fresh_records = tuple(RecordReference(**item) for item in supplied[0])
            fresh_artifacts = tuple(ArtifactReference(**item) for item in supplied[1])
            # Every compared scalar is now exact, range-checked and reconstructed;
            # Python bool/int equality or subclass hooks cannot mask substitutions.
            if supplied != (records, artifacts):
                raise ToolReleaseValidationError("projections: disagree with complete ordered content references")
        else:
            fresh_records = tuple(RecordReference(**item) for item in records)
            fresh_artifacts = tuple(ArtifactReference(**item) for item in artifacts)
        envelope = RecordEnvelope(record_id, revision, kind, tree, fresh_provenance,
                                  fresh_records, fresh_artifacts,
                                  operational_status=None, scientific_disposition=None)
        return release if decoding else envelope
    except (ToolReleaseValidationError, NotTypedContentError):
        raise
    except (DomainValidationError, ValueError, TypeError, AttributeError, RecursionError, OverflowError) as error:
        raise ToolReleaseValidationError("invalid retained tool-release envelope") from error


def encode_envelope(record_id: str, revision: int, content: ToolRelease,
                    provenance: CreationProvenance, *, limits: ToolReleaseLimits | None = None,
                    envelope_limits: ToolReleaseEnvelopeLimits | None = None) -> RecordEnvelope:
    """Build a detached exact passive envelope with explicit identity, revision and creator.

    Revalidate content, provenance and external ceilings before reconstruction.
    Invalid retained values raise ToolReleaseValidationError; exceeded ceilings
    raise ToolReleaseLimitError. No reference is resolved and no authority is granted.
    """
    return _convert(content, record_id, revision, provenance, limits, envelope_limits, decoding=False)


def decode_envelope(envelope: RecordEnvelope, *, limits: ToolReleaseLimits | None = None,
                    envelope_limits: ToolReleaseEnvelopeLimits | None = None) -> ToolRelease:
    """Return a fresh validated release only when both bounded projections agree exactly.

    Reject noncanonical snapshots and inconsistent envelopes without repairing
    identities or projections. Missing format retains NotTypedContentError;
    other malformed values and ceilings use the existing ToolRelease errors.
    Envelope creator metadata stays outside content; local validity is unauthenticated.
    """
    return _convert(envelope, None, None, None, limits, envelope_limits, decoding=True)
