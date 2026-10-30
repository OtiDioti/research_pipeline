"""Validated storage envelopes; descriptive JSON never grants scientific authority."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import json
import math
import re
from typing import Any


_KINDS = frozenset({"research_context", "claim", "justification", "evidence", "task_specification"})
_TASK_STATES = frozenset({"proposed", "ready", "blocked", "active", "completed", "cancelled", "abandoned"})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", re.ASCII)
_MAX_INTEGER = 2**63 - 1


class DomainValidationError(ValueError):
    """A domain value has malformed fields, JSON, references, or state dimensions."""


def _identifier(value: str, field: str) -> None:
    """Reject non-opaque or malformed identifiers without normalizing their meaning."""
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise DomainValidationError(f"{field}: expected 1–128 ASCII letters/digits/_/-, starting with a letter/digit")


def _integer(value: int, field: str, minimum: int) -> None:
    """Require an ordinary integer within the future SQLite metadata range."""
    if type(value) is not int or not minimum <= value <= _MAX_INTEGER:
        raise DomainValidationError(f"{field}: expected integer from {minimum} through {_MAX_INTEGER}")


def _kind(value: str, field: str) -> None:
    """Require a supported envelope kind, without coercing arbitrary objects."""
    if type(value) is not str or value not in _KINDS:
        raise DomainValidationError(f"{field}: unsupported record kind")


def _timestamp(value: str) -> str:
    """Validate caller-supplied UTC calendar time and return six fractional digits."""
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        raise DomainValidationError("created_at: expected YYYY-MM-DDTHH:MM:SS[.ffffff]Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise DomainValidationError(f"created_at: invalid calendar/time: {value}") from error
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_json_string(value: str, field: str) -> None:
    """Reject surrogate code points in a JSON string with a field-specific error."""
    # ASCII JSON escapes encode supplementary scalars and explicit surrogate pairs
    # identically; decoding could change strings or collapse distinct object keys.
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise DomainValidationError(f"{field}: JSON strings must contain Unicode scalar values, not surrogate code points")


def _validate_json(value: Any, field: str, ancestors: set[int]) -> None:
    """Check strict JSON types and scalar-value strings recursively; report paths and cycles."""
    kind = type(value)
    if value is None or kind in (int, bool):
        return
    if kind is str:
        _validate_json_string(value, field)
        return
    if kind is float:
        if not math.isfinite(value):
            raise DomainValidationError(f"{field}: nonfinite JSON number")
        return
    if kind not in (dict, list):
        raise DomainValidationError(f"{field}: unsupported JSON type {kind.__name__}")
    if id(value) in ancestors:
        raise DomainValidationError(f"{field}: cyclic JSON container")
    ancestors.add(id(value))
    try:
        if kind is dict:
            for key, child in value.items():
                if type(key) is not str:
                    raise DomainValidationError(f"{field}: JSON object keys must be strings")
                _validate_json_string(key, f"{field} key {key!r}")
                _validate_json(child, f"{field}[{key!r}]", ancestors)
        else:
            for index, child in enumerate(value):
                _validate_json(child, f"{field}[{index}]", ancestors)
    finally:
        ancestors.remove(id(value))


def _snapshot(value: dict, field: str) -> str:
    """Return a private canonical JSON object snapshot or a field-specific error."""
    if type(value) is not dict:
        raise DomainValidationError(f"{field}: expected JSON object")
    try:
        _validate_json(value, field, set())
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (ValueError, TypeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"{field}: cannot snapshot JSON: {error}") from error


def _fields(value: dict, required: set[str], optional: set[str], name: str) -> dict:
    """Validate a serialized object's exact field set before reconstructing it."""
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise DomainValidationError(f"{name}: expected object with string field names")
    missing, unknown = required - value.keys(), value.keys() - required - optional
    if missing or unknown:
        raise DomainValidationError(f"{name}: missing fields {sorted(missing)}; unknown fields {sorted(unknown)}")
    return value.copy()


def _references(values: Sequence, expected: type, field: str) -> tuple:
    """Copy an ordered sequence of typed references; reject malformed elements."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise DomainValidationError(f"{field}: expected a sequence of {expected.__name__}")
    result = tuple(values)
    if any(type(value) is not expected for value in result):
        raise DomainValidationError(f"{field}: every element must be {expected.__name__}")
    return result


@dataclass(frozen=True, init=False)
class CreationProvenance:
    """Attributed creator and explicit UTC time with isolated descriptive JSON details."""

    actor: str
    created_at: str
    _details_json: str

    def __init__(self, actor: str, created_at: str, details: dict = {}):
        """Validate attribution and snapshot details; never infer a timestamp or authority."""
        _identifier(actor, "actor")
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "created_at", _timestamp(created_at))
        object.__setattr__(self, "_details_json", _snapshot(details, "details"))

    @property
    def details(self) -> dict:
        """Return an independent decoded copy of the descriptive metadata."""
        return json.loads(self._details_json)

    def to_dict(self) -> dict:
        """Return detached JSON-compatible provenance, including the normalized timestamp."""
        return {"actor": self.actor, "created_at": self.created_at, "details": self.details}

    @classmethod
    def from_dict(cls, value: dict) -> "CreationProvenance":
        """Reconstruct validated attribution, rejecting missing or unknown fields."""
        return cls(**_fields(value, {"actor", "created_at"}, {"details"}, "provenance"))


@dataclass(frozen=True)
class RecordReference:
    """One exact record revision and relationship; construction does not resolve it."""

    record_id: str
    revision: int
    relationship: str
    target_kind: str | None = None

    def __post_init__(self) -> None:
        """Validate exact-reference syntax without inferring or resolving a target."""
        _identifier(self.record_id, "record_id")
        _integer(self.revision, "revision", 1)
        _identifier(self.relationship, "relationship")
        if self.target_kind is not None:
            _kind(self.target_kind, "target_kind")

    def to_dict(self) -> dict:
        """Return a detached JSON-compatible exact reference."""
        return {"record_id": self.record_id, "revision": self.revision,
                "relationship": self.relationship, "target_kind": self.target_kind}

    @classmethod
    def from_dict(cls, value: dict) -> "RecordReference":
        """Reconstruct an exact reference, rejecting malformed serialized fields."""
        return cls(**_fields(value, {"record_id", "revision", "relationship"}, {"target_kind"}, "record_reference"))


@dataclass(frozen=True)
class ArtifactReference:
    """A SHA-256 content address and byte count, without a path or availability claim."""

    digest: str
    size: int

    def __post_init__(self) -> None:
        """Reject unsafe content addresses and non-integer or out-of-range byte counts."""
        if type(self.digest) is not str or re.fullmatch(r"[0-9a-f]{64}", self.digest) is None:
            raise DomainValidationError("digest: expected exactly 64 lowercase SHA-256 hexadecimal characters")
        _integer(self.size, "size", 0)

    def to_dict(self) -> dict:
        """Return a detached JSON-compatible content address and size."""
        return {"digest": self.digest, "size": self.size}

    @classmethod
    def from_dict(cls, value: dict) -> "ArtifactReference":
        """Reconstruct a validated artifact reference with no extra locator fields."""
        return cls(**_fields(value, {"digest", "size"}, set(), "artifact_reference"))


@dataclass(frozen=True, init=False)
class RecordEnvelope:
    """Immutable common storage fields, independent of scientific payload schemas."""

    record_id: str
    revision: int
    kind: str
    _content_json: str
    provenance: CreationProvenance
    record_references: tuple[RecordReference, ...]
    artifact_references: tuple[ArtifactReference, ...]
    operational_status: str | None
    scientific_disposition: str | None

    def __init__(self, record_id: str, revision: int, kind: str, content: dict,
                 provenance: CreationProvenance,
                 record_references: Sequence[RecordReference] = (),
                 artifact_references: Sequence[ArtifactReference] = (),
                 operational_status: str | None = None,
                 scientific_disposition: str | None = None):
        """Validate fields and snapshot JSON/references; reject inferred or promoted state."""
        _identifier(record_id, "record_id")
        _integer(revision, "revision", 1)
        _kind(kind, "kind")
        if type(provenance) is not CreationProvenance:
            raise DomainValidationError("provenance: expected CreationProvenance")
        if kind == "task_specification":
            if type(operational_status) is not str or operational_status not in _TASK_STATES:
                raise DomainValidationError("operational_status: task requires an explicit supported task state")
        elif operational_status is not None:
            raise DomainValidationError("operational_status: only tasks have operational state")
        if kind == "claim":
            if type(scientific_disposition) is not str or scientific_disposition != "provisional":
                raise DomainValidationError("scientific_disposition: claims require explicit provisional disposition")
        elif scientific_disposition is not None:
            raise DomainValidationError("scientific_disposition: only claims have scientific disposition")
        values = {
            "record_id": record_id, "revision": revision, "kind": kind,
            "_content_json": _snapshot(content, "content"), "provenance": provenance,
            "record_references": _references(record_references, RecordReference, "record_references"),
            "artifact_references": _references(artifact_references, ArtifactReference, "artifact_references"),
            "operational_status": operational_status, "scientific_disposition": scientific_disposition,
        }
        for field, value in values.items():
            object.__setattr__(self, field, value)

    @property
    def content(self) -> dict:
        """Return a fresh descriptive content tree; editing it cannot change this value."""
        return json.loads(self._content_json)

    def to_dict(self) -> dict:
        """Return detached JSON-compatible fields, preserving reference and list order."""
        return {"record_id": self.record_id, "revision": self.revision, "kind": self.kind,
                "content": self.content, "provenance": self.provenance.to_dict(),
                "record_references": [value.to_dict() for value in self.record_references],
                "artifact_references": [value.to_dict() for value in self.artifact_references],
                "operational_status": self.operational_status,
                "scientific_disposition": self.scientific_disposition}

    @classmethod
    def from_dict(cls, value: dict) -> "RecordEnvelope":
        """Reconstruct all nested typed values, rejecting unknown or malformed fields."""
        fields = _fields(value, {"record_id", "revision", "kind", "content", "provenance"},
                         {"record_references", "artifact_references", "operational_status", "scientific_disposition"},
                         "envelope")
        fields["provenance"] = CreationProvenance.from_dict(fields["provenance"])
        for name, reference_type in (("record_references", RecordReference), ("artifact_references", ArtifactReference)):
            if name in fields:
                if type(fields[name]) is not list:
                    raise DomainValidationError(f"{name}: expected serialized JSON list")
                fields[name] = tuple(reference_type.from_dict(item) for item in fields[name])
        return cls(**fields)
