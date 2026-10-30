"""Pure bounded source declarations and exact capture links, without acquisition or parsing."""

from dataclasses import dataclass, fields
import json

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, _fields, _identifier, _integer, _snapshot, _timestamp,
    _validate_json_string,
)
from research_pipeline.scientific import NotTypedContentError, _list, _record_from_dict
from research_pipeline.assessment import (
    _code, _copy, _nested, _rebuild, _reference, _unique_targets,
)
from research_pipeline.work_product import _path, _validate_paths


_FORMAT = "research_pipeline.source_content"


def _text(value, field):
    """Require bounded nonblank scalar text while preserving its supplied spelling."""
    if type(value) is not str or not value.strip() or len(value) > 16384:
        raise DomainValidationError(f"{field}: expected nonblank text of at most 16384 characters")
    _validate_json_string(value, field)


def _collection(values, field):
    """Snapshot an ordinary ordered list/tuple with the Source-only member bound."""
    if type(values) not in (list, tuple) or len(values) > 1024:
        raise DomainValidationError(f"{field}: expected list/tuple of at most 1024 members")
    return tuple(values)


def _texts(values, field):
    """Detach bounded ordered text, retaining repetitions and whitespace."""
    result = _collection(values, field)
    for index, value in enumerate(result):
        _text(value, f"{field}[{index}]")
    return result


def _values(values, expected, field):
    """Reconstruct each exact nested value in a bounded Source collection."""
    return tuple(_copy(value, expected, f"{field}[{index}]")
                 for index, value in enumerate(_collection(values, field)))


def _ids(values, field):
    """Detach unique ordered local identifiers; resolution belongs to the containing Source."""
    result = _collection(values, field)
    for value in result:
        _identifier(value, field)
    if len(set(result)) != len(result):
        raise DomainValidationError(f"{field}: duplicate local identifier")
    return result


def _checks(values):
    """Detach explicit evidence/execution checks and reject repeated exact targets."""
    result = _values(values, RecordReference, "checks")
    for value in result:
        if (value.relationship, value.target_kind) not in (
                ("reported_evidence", "evidence"), ("reported_tool_execution", "tool_execution")):
            raise DomainValidationError("checks: expected reported_evidence/evidence or reported_tool_execution/tool_execution")
    _unique_targets(result, "checks")
    return result


@dataclass(frozen=True)
class DeclaredText:
    """One known string or an explicit reason it is unknown, never inferred from a sentinel word."""

    value: str | None
    unknown_reason: str | None

    def __post_init__(self) -> None:
        """Require exactly one non-null bounded field, preserving known text literally."""
        if (self.value is None) == (self.unknown_reason is None):
            raise DomainValidationError("declared text: exactly one of value and unknown_reason is required")
        _text(self.value if self.value is not None else self.unknown_reason, "declared text")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, DeclaredText, "DeclaredText")
        return {
            "value": value.value,
            "unknown_reason": value.unknown_reason,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "DeclaredText":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "DeclaredText")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "DeclaredText")
        return cls(**result)


@dataclass(frozen=True)
class SourceProvenance:
    """Reported acquisition facts; locators are inert text and never operational authority."""

    method: str
    attribution: DeclaredText
    occurred_at: DeclaredText
    supplied_locator: DeclaredText
    requested_locator: DeclaredText
    resolved_locator: DeclaredText
    outcome: str
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach facts, validate supplied locators and known UTC times without normalizing them."""
        _code(self.method, ("supplied_local", "supplied_artifact", "reported_retrieval", "unknown"), "method")
        _code(self.outcome, ("available", "partial", "unavailable", "unknown"), "outcome")
        for name in ("attribution", "occurred_at", "supplied_locator", "requested_locator", "resolved_locator"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        if self.occurred_at.value is not None:
            _timestamp(self.occurred_at.value)
        if self.method in ("supplied_local", "supplied_artifact") and self.supplied_locator.value is None:
            raise DomainValidationError("supplied_locator: supplied methods require a known locator")
        object.__setattr__(self, "notes", _texts(self.notes, "notes"))

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceProvenance, "SourceProvenance")
        return {
            "method": value.method,
            "attribution": value.attribution.to_dict(),
            "occurred_at": value.occurred_at.to_dict(),
            "supplied_locator": value.supplied_locator.to_dict(),
            "requested_locator": value.requested_locator.to_dict(),
            "resolved_locator": value.resolved_locator.to_dict(),
            "outcome": value.outcome,
            "notes": list(value.notes),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceProvenance":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceProvenance")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceProvenance")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["occurred_at"] = _nested(result["occurred_at"], DeclaredText, "occurred_at")
        result["supplied_locator"] = _nested(result["supplied_locator"], DeclaredText, "supplied_locator")
        result["requested_locator"] = _nested(result["requested_locator"], DeclaredText, "requested_locator")
        result["resolved_locator"] = _nested(result["resolved_locator"], DeclaredText, "resolved_locator")
        result["notes"] = _list(result["notes"], "notes")
        return cls(**result)


@dataclass(frozen=True)
class SourceDeclaration:
    """An explained restriction status whose vocabulary is checked by its containing field."""

    status: str
    detail: str

    def __post_init__(self) -> None:
        """Require bounded nonblank status/detail, without treating declarations as permissions."""
        _text(self.status, "status")
        _text(self.detail, "detail")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceDeclaration, "SourceDeclaration")
        return {
            "status": value.status,
            "detail": value.detail,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceDeclaration":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceDeclaration")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceDeclaration")
        return cls(**result)


@dataclass(frozen=True)
class SourceRestrictions:
    """Four independent explained declarations, without broader policy enforcement."""

    access: SourceDeclaration
    reuse: SourceDeclaration
    confidentiality: SourceDeclaration
    external_processing: SourceDeclaration

    def __post_init__(self) -> None:
        """Detach each declaration and require its field-specific status vocabulary."""
        for name, choices in (
                ("access", ("available", "limited", "unavailable", "unknown")),
                ("reuse", ("permitted", "restricted", "prohibited", "unknown")),
                ("confidentiality", ("public", "confidential", "restricted", "unknown")),
                ("external_processing", ("permitted", "restricted", "prohibited", "unknown"))):
            value = _copy(getattr(self, name), SourceDeclaration, name)
            _code(value.status, choices, name)
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceRestrictions, "SourceRestrictions")
        return {
            "access": value.access.to_dict(),
            "reuse": value.reuse.to_dict(),
            "confidentiality": value.confidentiality.to_dict(),
            "external_processing": value.external_processing.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceRestrictions":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceRestrictions")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceRestrictions")
        result["access"] = _nested(result["access"], SourceDeclaration, "access")
        result["reuse"] = _nested(result["reuse"], SourceDeclaration, "reuse")
        result["confidentiality"] = _nested(result["confidentiality"], SourceDeclaration, "confidentiality")
        result["external_processing"] = _nested(result["external_processing"], SourceDeclaration, "external_processing")
        return cls(**result)


@dataclass(frozen=True)
class SourceArtifact:
    """One supplied logical file and immutable bytes, with declared media, mode and provenance."""

    artifact_id: str
    path: str
    artifact: ArtifactReference
    media_type: DeclaredText
    original_mode: int | None
    provenance: SourceProvenance

    def __post_init__(self) -> None:
        """Validate portable names and supplied mode; detach references without reading or chmod."""
        _identifier(self.artifact_id, "artifact_id")
        _path(self.path, "path")
        if len(self.path) > 4096:
            raise DomainValidationError("path: at most 4096 characters")
        object.__setattr__(self, "artifact", _copy(self.artifact, ArtifactReference, "artifact"))
        object.__setattr__(self, "media_type", _copy(self.media_type, DeclaredText, "media_type"))
        object.__setattr__(self, "provenance", _copy(self.provenance, SourceProvenance, "provenance"))
        if self.original_mode is not None:
            _integer(self.original_mode, "original_mode", 0)
            if self.original_mode > 0o7777:
                raise DomainValidationError("original_mode: at most 0o7777")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceArtifact, "SourceArtifact")
        return {
            "artifact_id": value.artifact_id,
            "path": value.path,
            "artifact": value.artifact.to_dict(),
            "media_type": value.media_type.to_dict(),
            "original_mode": value.original_mode,
            "provenance": value.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceArtifact":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceArtifact")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceArtifact")
        result["artifact"] = _nested(result["artifact"], ArtifactReference, "artifact")
        result["media_type"] = _nested(result["media_type"], DeclaredText, "media_type")
        result["provenance"] = _nested(result["provenance"], SourceProvenance, "provenance")
        return cls(**result)


@dataclass(frozen=True)
class ToolSetting:
    """A bounded declarative tool setting, not arbitrary JSON or executable configuration."""

    name: str
    value: DeclaredText

    def __post_init__(self) -> None:
        """Preserve the exact setting name and reconstruct its known or unknown value."""
        _text(self.name, "name")
        object.__setattr__(self, "value", _copy(self.value, DeclaredText, "value"))

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, ToolSetting, "ToolSetting")
        return {
            "name": value.name,
            "value": value.value.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ToolSetting":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "ToolSetting")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "ToolSetting")
        result["value"] = _nested(result["value"], DeclaredText, "value")
        return cls(**result)


@dataclass(frozen=True)
class SourceLocation:
    """An explicit named, half-open byte, or inclusive line locator; no content is interpreted."""

    location_id: str
    artifact_id: str | None
    kind: str
    label: str
    start: int | None
    end: int | None

    def __post_init__(self) -> None:
        """Validate locator shape; the containing Source resolves bytes and enforces size bounds."""
        _identifier(self.location_id, "location_id")
        if self.artifact_id is not None:
            _identifier(self.artifact_id, "artifact_id")
        _code(self.kind, ("page", "section", "equation", "theorem", "byte", "line"), "kind")
        _text(self.label, "label")
        if self.kind in ("byte", "line"):
            if self.artifact_id is None:
                raise DomainValidationError("artifact_id: byte/line location requires an artifact")
            _integer(self.start, "start", 0 if self.kind == "byte" else 1)
            _integer(self.end, "end", 0 if self.kind == "byte" else 1)
            if self.start > self.end or (self.kind == "byte" and self.start == self.end):
                raise DomainValidationError("location: invalid ordered endpoints")
        elif self.start is not None or self.end is not None:
            raise DomainValidationError("location: named locations require null start/end")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceLocation, "SourceLocation")
        return {
            "location_id": value.location_id,
            "artifact_id": value.artifact_id,
            "kind": value.kind,
            "label": value.label,
            "start": value.start,
            "end": value.end,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceLocation":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceLocation")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceLocation")
        return cls(**result)


@dataclass(frozen=True)
class LocationMapping:
    """One declared original/output correspondence, asserting neither equivalence nor fidelity."""

    original_location: str
    output_location: str

    def __post_init__(self) -> None:
        """Validate local endpoint IDs; the containing Source resolves their extraction roles."""
        _identifier(self.original_location, "original_location")
        _identifier(self.output_location, "output_location")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, LocationMapping, "LocationMapping")
        return {
            "original_location": value.original_location,
            "output_location": value.output_location,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "LocationMapping":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "LocationMapping")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "LocationMapping")
        return cls(**result)


@dataclass(frozen=True)
class SourceExtraction:
    """Supplied outputs from exact originals with declared tool details, warnings and mappings."""

    extraction_id: str
    original_inputs: tuple[str, ...]
    tool: DeclaredText
    tool_version: DeclaredText
    settings: tuple[ToolSetting, ...]
    outputs: tuple[SourceArtifact, ...]
    mappings: tuple[LocationMapping, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach ordered lineage, require inputs/outputs and explain absent mappings; execute nothing."""
        _identifier(self.extraction_id, "extraction_id")
        object.__setattr__(self, "original_inputs", _ids(self.original_inputs, "original_inputs"))
        for name in ("tool", "tool_version"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        for name, expected in (("settings", ToolSetting), ("outputs", SourceArtifact), ("mappings", LocationMapping)):
            object.__setattr__(self, name, _values(getattr(self, name), expected, name))
        object.__setattr__(self, "warnings", _texts(self.warnings, "warnings"))
        if not self.original_inputs or not self.outputs:
            raise DomainValidationError("extraction: nonempty original_inputs and outputs required")
        if len({item.name for item in self.settings}) != len(self.settings):
            raise DomainValidationError("settings: duplicate exact name")
        if len(set(self.mappings)) != len(self.mappings):
            raise DomainValidationError("mappings: duplicate pair")
        if not self.mappings and not self.warnings:
            raise DomainValidationError("warnings: explain unavailable mapping")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceExtraction, "SourceExtraction")
        return {
            "extraction_id": value.extraction_id,
            "original_inputs": list(value.original_inputs),
            "tool": value.tool.to_dict(),
            "tool_version": value.tool_version.to_dict(),
            "settings": [item.to_dict() for item in value.settings],
            "outputs": [item.to_dict() for item in value.outputs],
            "mappings": [item.to_dict() for item in value.mappings],
            "warnings": list(value.warnings),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceExtraction":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceExtraction")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceExtraction")
        result["tool"] = _nested(result["tool"], DeclaredText, "tool")
        result["tool_version"] = _nested(result["tool_version"], DeclaredText, "tool_version")
        result["original_inputs"] = _list(result["original_inputs"], "original_inputs")
        result["settings"] = [_nested(item, ToolSetting, "settings") for item in _list(result["settings"], "settings")]
        result["outputs"] = [_nested(item, SourceArtifact, "outputs") for item in _list(result["outputs"], "outputs")]
        result["mappings"] = [_nested(item, LocationMapping, "mappings") for item in _list(result["mappings"], "mappings")]
        result["warnings"] = _list(result["warnings"], "warnings")
        return cls(**result)


@dataclass(frozen=True)
class SourceReading:
    """Reported inspection and reproduction with a separately pinned report and unauthenticated checks."""

    coverage: str
    locations: tuple[str, ...]
    report: RecordReference | None
    reproduction: str
    checks: tuple[RecordReference, ...]
    attribution: DeclaredText
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate independent coverage and reproduction; neither artifacts nor checks upgrade coverage."""
        _code(self.coverage, ("uninspected", "metadata_only", "abstract_only", "selected_material", "whole_document"), "coverage")
        _code(self.reproduction, ("unreported", "not_attempted", "reported_failed", "reported_partial", "reported_succeeded"), "reproduction")
        object.__setattr__(self, "locations", _ids(self.locations, "locations"))
        object.__setattr__(self, "checks", _checks(self.checks))
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        if self.report is not None:
            object.__setattr__(self, "report", _reference(self.report, "reading_report", "work_product_manifest", "report"))
        if self.coverage == "uninspected" and self.locations:
            raise DomainValidationError("locations: uninspected requires empty locations")
        if self.coverage == "selected_material" and not self.locations:
            raise DomainValidationError("locations: selected_material requires locations")
        if self.reproduction.startswith("reported_") and not self.checks:
            raise DomainValidationError("checks: reported reproduction requires a separate check")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceReading, "SourceReading")
        return {
            "coverage": value.coverage,
            "locations": list(value.locations),
            "report": None if value.report is None else value.report.to_dict(),
            "reproduction": value.reproduction,
            "checks": [item.to_dict() for item in value.checks],
            "attribution": value.attribution.to_dict(),
            "limitations": list(value.limitations),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceReading":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceReading")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceReading")
        if result["report"] is not None:
            result["report"] = _record_from_dict(result["report"], "report")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["locations"] = _list(result["locations"], "locations")
        result["checks"] = [_record_from_dict(item, "checks") for item in _list(result["checks"], "checks")]
        result["limitations"] = _list(result["limitations"], "limitations")
        return cls(**result)


@dataclass(frozen=True)
class SourceStatement:
    """Attributed source text, interpretation or referenced check, never a Claim or promotion."""

    statement_id: str
    category: str
    text: str
    attribution: DeclaredText
    locations: tuple[str, ...]
    checks: tuple[RecordReference, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach scope and checks, keeping reported independent checks separate from attributed text."""
        _identifier(self.statement_id, "statement_id")
        _code(self.category, ("source_statement", "interpretation", "referenced_check"), "category")
        _text(self.text, "text")
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))
        object.__setattr__(self, "locations", _ids(self.locations, "locations"))
        object.__setattr__(self, "checks", _checks(self.checks))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        if self.category == "source_statement" and not self.locations:
            raise DomainValidationError("locations: source_statement requires a location")
        if (self.category == "referenced_check") != bool(self.checks):
            raise DomainValidationError("checks: required only for referenced_check statements")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, SourceStatement, "SourceStatement")
        return {
            "statement_id": value.statement_id,
            "category": value.category,
            "text": value.text,
            "attribution": value.attribution.to_dict(),
            "locations": list(value.locations),
            "checks": [item.to_dict() for item in value.checks],
            "limitations": list(value.limitations),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SourceStatement":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "SourceStatement")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "SourceStatement")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["locations"] = _list(result["locations"], "locations")
        result["checks"] = [_record_from_dict(item, "checks") for item in _list(result["checks"], "checks")]
        result["limitations"] = _list(result["limitations"], "limitations")
        return cls(**result)


@dataclass(frozen=True)
class RelatedSource:
    """An exact distinct capture with an explained relationship, without equivalent-content claims."""

    reference: RecordReference
    relation: str

    def __post_init__(self) -> None:
        """Detach an explicit source reference and preserve its descriptive relation."""
        object.__setattr__(self, "reference", _reference(self.reference, "related_source", "source", "reference"))
        _text(self.relation, "relation")

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, RelatedSource, "RelatedSource")
        return {
            "reference": value.reference.to_dict(),
            "relation": value.relation,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "RelatedSource":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "RelatedSource")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "RelatedSource")
        result["reference"] = _record_from_dict(result["reference"], "reference")
        return cls(**result)


@dataclass(frozen=True)
class Source:
    """A bounded versioned capture declaration; its envelope alone supplies capture identity/revision."""

    work_id: str
    upstream_identity: DeclaredText
    upstream_version: DeclaredText
    title: DeclaredText
    authors: tuple[DeclaredText, ...]
    provenance: SourceProvenance
    restrictions: SourceRestrictions
    originals: tuple[SourceArtifact, ...]
    extractions: tuple[SourceExtraction, ...]
    locations: tuple[SourceLocation, ...]
    reading: SourceReading
    statements: tuple[SourceStatement, ...]
    related_sources: tuple[RelatedSource, ...]
    supersedes: RecordReference | None
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach declarations and resolve all local inventory, location and lineage invariants."""
        _identifier(self.work_id, "work_id")
        for name, expected in (("upstream_identity", DeclaredText), ("upstream_version", DeclaredText),
                               ("title", DeclaredText), ("provenance", SourceProvenance),
                               ("restrictions", SourceRestrictions), ("reading", SourceReading)):
            object.__setattr__(self, name, _copy(getattr(self, name), expected, name))
        for name, expected in (("authors", DeclaredText), ("originals", SourceArtifact),
                               ("extractions", SourceExtraction), ("locations", SourceLocation),
                               ("statements", SourceStatement), ("related_sources", RelatedSource)):
            object.__setattr__(self, name, _values(getattr(self, name), expected, name))
        if not self.authors:
            raise DomainValidationError("authors: nonempty collection required; explicit unknown is allowed")
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        if self.supersedes is not None:
            object.__setattr__(self, "supersedes", _reference(self.supersedes, "supersedes", "source", "supersedes"))
        _unique_targets(tuple(item.reference for item in self.related_sources), "related_sources")
        _validate_inventory(self)

    def to_dict(self) -> dict:
        """Return detached exact fields after reconstructing and revalidating frozen state."""
        value = _rebuild(self, Source, "Source")
        return {
            "format": _FORMAT, "version": 1, "kind": "source",
            "work_id": value.work_id,
            "upstream_identity": value.upstream_identity.to_dict(),
            "upstream_version": value.upstream_version.to_dict(),
            "title": value.title.to_dict(),
            "authors": [item.to_dict() for item in value.authors],
            "provenance": value.provenance.to_dict(),
            "restrictions": value.restrictions.to_dict(),
            "originals": [item.to_dict() for item in value.originals],
            "extractions": [item.to_dict() for item in value.extractions],
            "locations": [item.to_dict() for item in value.locations],
            "reading": value.reading.to_dict(),
            "statements": [item.to_dict() for item in value.statements],
            "related_sources": [item.to_dict() for item in value.related_sources],
            "supersedes": None if value.supersedes is None else value.supersedes.to_dict(),
            "limitations": list(value.limitations),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "Source":
        """Decode exact required fields; missing declarations and malformed nested values are errors."""
        _snapshot(value, "Source")
        if "format" not in value:
            raise NotTypedContentError("source content: missing format discriminator")
        if type(value["format"]) is not str or value["format"] != _FORMAT:
            raise DomainValidationError("format: unsupported source content format")
        result = _fields(value, {item.name for item in fields(cls)} | {"format", "version", "kind"}, set(), "Source")
        _integer(result["version"], "version", 1)
        if result["version"] != 1:
            raise DomainValidationError("version: unsupported source content version")
        _code(result["kind"], ("source",), "kind")
        for name in ("format", "version", "kind"):
            del result[name]
        result["upstream_identity"] = _nested(result["upstream_identity"], DeclaredText, "upstream_identity")
        result["upstream_version"] = _nested(result["upstream_version"], DeclaredText, "upstream_version")
        result["title"] = _nested(result["title"], DeclaredText, "title")
        result["provenance"] = _nested(result["provenance"], SourceProvenance, "provenance")
        result["restrictions"] = _nested(result["restrictions"], SourceRestrictions, "restrictions")
        result["reading"] = _nested(result["reading"], SourceReading, "reading")
        if result["supersedes"] is not None:
            result["supersedes"] = _record_from_dict(result["supersedes"], "supersedes")
        result["authors"] = [_nested(item, DeclaredText, "authors") for item in _list(result["authors"], "authors")]
        result["originals"] = [_nested(item, SourceArtifact, "originals") for item in _list(result["originals"], "originals")]
        result["extractions"] = [_nested(item, SourceExtraction, "extractions") for item in _list(result["extractions"], "extractions")]
        result["locations"] = [_nested(item, SourceLocation, "locations") for item in _list(result["locations"], "locations")]
        result["statements"] = [_nested(item, SourceStatement, "statements") for item in _list(result["statements"], "statements")]
        result["related_sources"] = [_nested(item, RelatedSource, "related_sources") for item in _list(result["related_sources"], "related_sources")]
        result["limitations"] = _list(result["limitations"], "limitations")
        return cls(**result)


def _validate_inventory(value):
    """Resolve capture-local IDs and exact extraction roles without reading bytes or inferring fidelity."""
    inventory = (*value.originals, *(item for extraction in value.extractions for item in extraction.outputs))
    if len(inventory) > 1024:
        raise DomainValidationError("inventory: at most 1024 total artifact entries")
    for items, name in ((inventory, "artifact_id"), (value.extractions, "extraction_id"),
                        (value.locations, "location_id"), (value.statements, "statement_id")):
        if len({getattr(item, name) for item in items}) != len(items):
            raise DomainValidationError(f"{name}: duplicate local ID")
    _validate_paths([item.path for item in inventory])
    sizes = {}
    for item in inventory:
        if item.artifact.digest in sizes and sizes[item.artifact.digest] != item.artifact.size:
            raise DomainValidationError("inventory: conflicting sizes for repeated digest")
        sizes[item.artifact.digest] = item.artifact.size
    artifacts = {item.artifact_id: item.artifact for item in inventory}
    locations = {item.location_id: item for item in value.locations}
    for location in value.locations:
        if location.artifact_id is not None:
            if location.artifact_id not in artifacts:
                raise DomainValidationError("location.artifact_id: missing inventory entry")
            if location.kind == "byte" and location.end > artifacts[location.artifact_id].size:
                raise DomainValidationError("location.end: byte range exceeds artifact size")
    for inspected in (value.reading, *value.statements):
        if any(identity not in locations for identity in inspected.locations):
            raise DomainValidationError("locations: unknown reading/statement location ID")
    originals = {item.artifact_id for item in value.originals}
    for extraction in value.extractions:
        if not set(extraction.original_inputs) <= originals:
            raise DomainValidationError("original_inputs: must resolve exclusively to originals")
        outputs = {item.artifact_id for item in extraction.outputs}
        for mapping in extraction.mappings:
            original = locations.get(mapping.original_location)
            output = locations.get(mapping.output_location)
            # Unanchored upstream labels cannot certify a captured-byte correspondence.
            if original is None or original.artifact_id not in extraction.original_inputs:
                raise DomainValidationError("mapping.original_location: must anchor to an exact original input")
            if output is None or output.artifact_id not in outputs:
                raise DomainValidationError("mapping.output_location: must anchor to this extraction's output")


def decode_content(value: dict) -> Source:
    """Decode only explicit version-1 Source content; no store lookup or artifact reads occur."""
    return Source.from_dict(value)


def dumps_content(value: Source) -> str:
    """Revalidate an exact Source and return sorted compact ASCII JSON with array order intact."""
    if type(value) is not Source:
        raise DomainValidationError("content: expected Source")
    return _snapshot(value.to_dict(), "source content")


def _unique_object(pairs):
    """Reject duplicate fields at every JSON depth while constructing an ordinary dictionary."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError(f"source content: duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    """Reject nonfinite JSON constants before decoding Source declarations."""
    raise DomainValidationError(f"source content: nonfinite JSON constant {value}")


def loads_content(data: str | bytes) -> Source:
    """Decode strict UTF-8 JSON and translate syntax, encoding and excessive depth failures."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("source content: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "source content JSON")
        return decode_content(json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"source content: cannot decode JSON: {error}") from error


def _links(content: Source) -> tuple[tuple[RecordReference, ...], tuple[ArtifactReference, ...]]:
    """Project exact roles in contract order and only the first occurrence of each artifact digest."""
    # Occurrences across roles/statements remain distinct; only immutable bytes deduplicate.
    records = (*((content.supersedes,) if content.supersedes is not None else ()),
               *(item.reference for item in content.related_sources),
               *((content.reading.report,) if content.reading.report is not None else ()),
               *content.reading.checks, *(check for statement in content.statements for check in statement.checks))
    artifacts = {}
    for item in (*content.originals, *(item for extraction in content.extractions for item in extraction.outputs)):
        artifacts.setdefault(item.artifact.digest, item.artifact)
    return records, tuple(artifacts.values())


def _capture_links(record_id, revision, content):
    """Enforce envelope-local immediate predecessor and distinct related-capture identities."""
    previous = content.supersedes
    if previous is not None and (revision == 1 or previous.record_id != record_id or previous.revision != revision - 1):
        raise DomainValidationError("supersedes: must pin this capture's immediately preceding revision; revision 1 requires null")
    if any(item.reference.record_id == record_id for item in content.related_sources):
        raise DomainValidationError("related_sources: same capture identity requires supersedes")


def encode_envelope(record_id: str, revision: int, content: Source,
                    provenance: CreationProvenance) -> RecordEnvelope:
    """Build a detached null-state Source envelope with exact projections and local capture checks."""
    content = loads_content(dumps_content(content))
    provenance = _copy(provenance, CreationProvenance, "provenance")
    records, artifacts = _links(content)
    envelope = RecordEnvelope(record_id, revision, "source", content.to_dict(), provenance, records, artifacts)
    _capture_links(envelope.record_id, envelope.revision, content)
    return envelope


def decode_envelope(envelope: RecordEnvelope) -> Source:
    """Reconstruct exact classes and reject kind, state or ordered projection incoherence without repair."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected RecordEnvelope")
    try:
        _copy(envelope.provenance, CreationProvenance, "envelope.provenance")
        for name, expected in (("record_references", RecordReference), ("artifact_references", ArtifactReference)):
            # Projection occurrences can exceed a single Source-owned collection's bound.
            values = getattr(envelope, name)
            if type(values) not in (list, tuple):
                raise DomainValidationError(f"envelope.{name}: expected list/tuple")
            for index, value in enumerate(values):
                _copy(value, expected, f"envelope.{name}[{index}]")
    except AttributeError as error:
        raise DomainValidationError("envelope: missing nested value") from error
    checked = _copy(envelope, RecordEnvelope, "envelope")
    content = decode_content(checked.content)
    if checked.kind != "source":
        raise DomainValidationError("envelope.kind: expected source")
    if checked.operational_status is not None or checked.scientific_disposition is not None:
        raise DomainValidationError("envelope: source states must be null")
    records, artifacts = _links(content)
    if checked.record_references != records:
        raise DomainValidationError("envelope.record_references: disagree with complete ordered content roles")
    if checked.artifact_references != artifacts:
        raise DomainValidationError("envelope.artifact_references: disagree with complete ordered inventory")
    _capture_links(checked.record_id, checked.revision, content)
    return content
