"""Pure immutable seed inventories over exact Source captures; declarations confer no authority."""

from dataclasses import dataclass, fields
import json

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, _fields, _identifier, _integer, _snapshot, _validate_json_string,
)
from research_pipeline.scientific import NotTypedContentError, _record_from_dict
from research_pipeline.assessment import _code, _copy, _nested, _rebuild, _reference
from research_pipeline.source import (
    DeclaredText, SourceProvenance, SourceRestrictions, Source,
    _text, _texts, _values, _ids,
)
from research_pipeline.work_product import _path, _validate_paths


_FORMAT = "research_pipeline.corpus_content"
_STATUSES = ("captured", "reference_only", "unavailable", "unresolved")
_CLASSIFICATIONS = ("research_note", "published_source", "derivation", "notebook", "calculation",
                    "software", "data", "prior_report", "operating_instruction", "other", "unknown")
_COVERAGES = ("uninspected", "metadata_only", "selected_material", "unknown")
_CATEGORIES = ("relevance", "purpose", "contradiction", "gap", "proposed_question",
               "proposed_baseline", "unresolved_mapping")


def _array(value, field, maximum=1024):
    """Require a bounded ordinary wire array before decoding or copying any of its members."""
    if type(value) is not list or len(value) > maximum:
        raise DomainValidationError(f"{field}: expected list of at most {maximum} members")
    return value


def _locations(values, field):
    """Detach exact locations and reject repeated uses within this declaration only."""
    result = _values(values, CorpusLocation, field)
    if len(set(result)) != len(result):
        raise DomainValidationError(f"{field}: duplicate exact location")
    return result


def _changes(values):
    """Detach at most 2048 changes, allowing replacement of every entry in a full inventory."""
    if type(values) not in (list, tuple) or len(values) > 2048:
        raise DomainValidationError("changes: expected list/tuple of at most 2048 members")
    return tuple(_copy(value, CorpusEntryChange, f"changes[{index}]") for index, value in enumerate(values))


@dataclass(frozen=True)
class CorpusOriginal:
    """One selected original mapping; its logical path is distinct from its inert supplied locator."""

    artifact_id: str
    path: str
    supplied_locator: DeclaredText
    artifact: ArtifactReference

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _identifier(self.artifact_id, "artifact_id")
        _path(self.path, "path")
        if len(self.path) > 4096:
            raise DomainValidationError("path: at most 4096 characters")
        object.__setattr__(self, "supplied_locator", _copy(self.supplied_locator, DeclaredText, "supplied_locator"))
        object.__setattr__(self, "artifact", _copy(self.artifact, ArtifactReference, "artifact"))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusOriginal, "CorpusOriginal")
        return {
            "artifact_id": value.artifact_id,
            "path": value.path,
            "supplied_locator": value.supplied_locator.to_dict(),
            "artifact": value.artifact.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusOriginal":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusOriginal")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusOriginal")
        result["supplied_locator"] = _nested(result["supplied_locator"], DeclaredText, "supplied_locator")
        result["artifact"] = _nested(result["artifact"], ArtifactReference, "artifact")
        return cls(**result)


@dataclass(frozen=True)
class CorpusUncaptured:
    """Explicit provenance and restrictions for material without a captured byte reference."""

    authors: tuple[DeclaredText, ...]
    upstream_identity: DeclaredText
    upstream_version: DeclaredText
    provenance: SourceProvenance
    restrictions: SourceRestrictions

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        object.__setattr__(self, "authors", _values(self.authors, DeclaredText, "authors"))
        if not self.authors:
            raise DomainValidationError("authors: nonempty declarations required; unknown is allowed")
        for name, expected in (("upstream_identity", DeclaredText), ("upstream_version", DeclaredText),
                               ("provenance", SourceProvenance), ("restrictions", SourceRestrictions)):
            object.__setattr__(self, name, _copy(getattr(self, name), expected, name))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusUncaptured, "CorpusUncaptured")
        return {
            "authors": [item.to_dict() for item in value.authors],
            "upstream_identity": value.upstream_identity.to_dict(),
            "upstream_version": value.upstream_version.to_dict(),
            "provenance": value.provenance.to_dict(),
            "restrictions": value.restrictions.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusUncaptured":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusUncaptured")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusUncaptured")
        result["authors"] = [_nested(item, DeclaredText, f"authors[{index}]")
                           for index, item in enumerate(_array(result["authors"], "authors"))]
        result["upstream_identity"] = _nested(result["upstream_identity"], DeclaredText, "upstream_identity")
        result["upstream_version"] = _nested(result["upstream_version"], DeclaredText, "upstream_version")
        result["provenance"] = _nested(result["provenance"], SourceProvenance, "provenance")
        result["restrictions"] = _nested(result["restrictions"], SourceRestrictions, "restrictions")
        return cls(**result)


@dataclass(frozen=True)
class CorpusLocation:
    """An exact Source location used through one entry and its selected original artifacts."""

    entry_id: str
    source: RecordReference
    location_id: str

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _identifier(self.entry_id, "entry_id")
        _identifier(self.location_id, "location_id")
        object.__setattr__(self, "source", _reference(self.source, "source_location", "source", "source"))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusLocation, "CorpusLocation")
        return {
            "entry_id": value.entry_id,
            "source": value.source.to_dict(),
            "location_id": value.location_id,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusLocation":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusLocation")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusLocation")
        result["source"] = _record_from_dict(result["source"], "source")
        return cls(**result)


@dataclass(frozen=True)
class CorpusInspection:
    """Attributed intake coverage and explicit uninspected remainder, independent of Source reading."""

    coverage: str
    locations: tuple[CorpusLocation, ...]
    uninspected: DeclaredText
    attribution: DeclaredText
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _code(self.coverage, _COVERAGES, "coverage")
        object.__setattr__(self, "locations", _locations(self.locations, "locations"))
        if (self.coverage == "selected_material") != bool(self.locations):
            raise DomainValidationError("locations: required only for selected_material coverage")
        for name in ("uninspected", "attribution"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusInspection, "CorpusInspection")
        return {
            "coverage": value.coverage,
            "locations": [item.to_dict() for item in value.locations],
            "uninspected": value.uninspected.to_dict(),
            "attribution": value.attribution.to_dict(),
            "limitations": list(value.limitations),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusInspection":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusInspection")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusInspection")
        result["locations"] = [_nested(item, CorpusLocation, f"locations[{index}]")
                           for index, item in enumerate(_array(result["locations"], "locations"))]
        result["uninspected"] = _nested(result["uninspected"], DeclaredText, "uninspected")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["limitations"] = _array(result["limitations"], "limitations")
        return cls(**result)


@dataclass(frozen=True)
class CorpusEntry:
    """A stable inventory observation with an immutable material binding and separately correctable description."""

    entry_id: str
    status: str
    classification: str
    title: DeclaredText
    origin_collection: DeclaredText
    origin_locator: DeclaredText
    source: RecordReference | None
    originals: tuple[CorpusOriginal, ...]
    uncaptured: CorpusUncaptured | None
    reason: str | None
    inspection: CorpusInspection

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _identifier(self.entry_id, "entry_id")
        _code(self.status, _STATUSES, "status")
        _code(self.classification, _CLASSIFICATIONS, "classification")
        for name in ("title", "origin_collection", "origin_locator"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        object.__setattr__(self, "originals", _values(self.originals, CorpusOriginal, "originals"))
        object.__setattr__(self, "inspection", _copy(self.inspection, CorpusInspection, "inspection"))
        if self.status == "captured":
            object.__setattr__(self, "source", _reference(self.source, "inventory_source", "source", "source"))
            if not self.originals or self.uncaptured is not None or self.reason is not None:
                raise DomainValidationError("captured: nonempty originals, null uncaptured and null reason required")
        else:
            if self.source is not None or self.originals:
                raise DomainValidationError("noncaptured: null source and empty originals required")
            object.__setattr__(self, "uncaptured", _copy(self.uncaptured, CorpusUncaptured, "uncaptured"))
            _text(self.reason, "reason")
        if len({item.artifact_id for item in self.originals}) != len(self.originals):
            raise DomainValidationError("originals: duplicate artifact_id")
        _validate_paths([item.path for item in self.originals])
        for location in self.inspection.locations:
            _local_location(location, {self.entry_id: self}, "inspection.locations")

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusEntry, "CorpusEntry")
        return {
            "entry_id": value.entry_id,
            "status": value.status,
            "classification": value.classification,
            "title": value.title.to_dict(),
            "origin_collection": value.origin_collection.to_dict(),
            "origin_locator": value.origin_locator.to_dict(),
            "source": None if value.source is None else value.source.to_dict(),
            "originals": [item.to_dict() for item in value.originals],
            "uncaptured": None if value.uncaptured is None else value.uncaptured.to_dict(),
            "reason": value.reason,
            "inspection": value.inspection.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusEntry":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusEntry")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusEntry")
        result["title"] = _nested(result["title"], DeclaredText, "title")
        result["origin_collection"] = _nested(result["origin_collection"], DeclaredText, "origin_collection")
        result["origin_locator"] = _nested(result["origin_locator"], DeclaredText, "origin_locator")
        if result["source"] is not None:
            result["source"] = _record_from_dict(result["source"], "source")
        result["originals"] = [_nested(item, CorpusOriginal, f"originals[{index}]")
                           for index, item in enumerate(_array(result["originals"], "originals"))]
        if result["uncaptured"] is not None:
            result["uncaptured"] = _nested(result["uncaptured"], CorpusUncaptured, "uncaptured")
        result["inspection"] = _nested(result["inspection"], CorpusInspection, "inspection")
        return cls(**result)


@dataclass(frozen=True)
class CorpusObservation:
    """An attributed intake note, with explicit unresolved mappings instead of fabricated endpoints."""

    observation_id: str
    category: str
    text: str
    attribution: DeclaredText
    entry_ids: tuple[str, ...]
    locations: tuple[CorpusLocation, ...]
    unresolved_locator: DeclaredText | None
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _identifier(self.observation_id, "observation_id")
        _code(self.category, _CATEGORIES, "category")
        _text(self.text, "text")
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))
        object.__setattr__(self, "entry_ids", _ids(self.entry_ids, "entry_ids"))
        object.__setattr__(self, "locations", _locations(self.locations, "locations"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        if self.category == "unresolved_mapping":
            object.__setattr__(self, "unresolved_locator", _copy(self.unresolved_locator, DeclaredText, "unresolved_locator"))
        elif self.unresolved_locator is not None:
            raise DomainValidationError("unresolved_locator: must be null except for unresolved_mapping")
        if any(location.entry_id not in self.entry_ids for location in self.locations):
            raise DomainValidationError("locations: each entry must be included in entry_ids")

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusObservation, "CorpusObservation")
        return {
            "observation_id": value.observation_id,
            "category": value.category,
            "text": value.text,
            "attribution": value.attribution.to_dict(),
            "entry_ids": list(value.entry_ids),
            "locations": [item.to_dict() for item in value.locations],
            "unresolved_locator": None if value.unresolved_locator is None else value.unresolved_locator.to_dict(),
            "limitations": list(value.limitations),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusObservation":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusObservation")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusObservation")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["entry_ids"] = _array(result["entry_ids"], "entry_ids")
        result["locations"] = [_nested(item, CorpusLocation, f"locations[{index}]")
                           for index, item in enumerate(_array(result["locations"], "locations"))]
        if result["unresolved_locator"] is not None:
            result["unresolved_locator"] = _nested(result["unresolved_locator"], DeclaredText, "unresolved_locator")
        result["limitations"] = _array(result["limitations"], "limitations")
        return cls(**result)


@dataclass(frozen=True)
class CorpusLink:
    """Preserved original link declarations with an explicit local, external or unresolved target."""

    link_id: str
    source_entry_id: str
    source_location: CorpusLocation | None
    original_locator: DeclaredText
    original_text: DeclaredText
    target_kind: str
    target_entry_id: str | None
    target_location: CorpusLocation | None
    external_locator: str | None
    unresolved_reason: str | None
    attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _identifier(self.link_id, "link_id")
        _identifier(self.source_entry_id, "source_entry_id")
        for name in ("original_locator", "original_text", "attribution"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        if self.original_locator.value is None and self.original_text.value is None:
            raise DomainValidationError("link: at least one original locator/text must be known")
        if self.source_location is not None:
            object.__setattr__(self, "source_location", _copy(self.source_location, CorpusLocation, "source_location"))
            if self.source_location.entry_id != self.source_entry_id:
                raise DomainValidationError("source_location: must belong to source_entry_id")
        _code(self.target_kind, ("entry", "source_location", "external", "unresolved"), "target_kind")
        required = {"entry": "target_entry_id", "source_location": "target_location",
                    "external": "external_locator", "unresolved": "unresolved_reason"}[self.target_kind]
        for name in ("target_entry_id", "target_location", "external_locator", "unresolved_reason"):
            if name != required and getattr(self, name) is not None:
                raise DomainValidationError(f"{name}: must be null for target_kind {self.target_kind}")
        if required == "target_entry_id":
            _identifier(self.target_entry_id, "target_entry_id")
        elif required == "target_location":
            object.__setattr__(self, "target_location", _copy(self.target_location, CorpusLocation, "target_location"))
        else:
            _text(getattr(self, required), required)

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusLink, "CorpusLink")
        return {
            "link_id": value.link_id,
            "source_entry_id": value.source_entry_id,
            "source_location": None if value.source_location is None else value.source_location.to_dict(),
            "original_locator": value.original_locator.to_dict(),
            "original_text": value.original_text.to_dict(),
            "target_kind": value.target_kind,
            "target_entry_id": value.target_entry_id,
            "target_location": None if value.target_location is None else value.target_location.to_dict(),
            "external_locator": value.external_locator,
            "unresolved_reason": value.unresolved_reason,
            "attribution": value.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusLink":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusLink")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusLink")
        if result["source_location"] is not None:
            result["source_location"] = _nested(result["source_location"], CorpusLocation, "source_location")
        result["original_locator"] = _nested(result["original_locator"], DeclaredText, "original_locator")
        result["original_text"] = _nested(result["original_text"], DeclaredText, "original_text")
        if result["target_location"] is not None:
            result["target_location"] = _nested(result["target_location"], CorpusLocation, "target_location")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        return cls(**result)


@dataclass(frozen=True)
class CorpusRelationship:
    """An attributed relation between distinct inventory identities, never inferred from matching bytes."""

    relationship_id: str
    source_entry_id: str
    target_entry_id: str
    relation: str
    detail: str
    attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        for name in ("relationship_id", "source_entry_id", "target_entry_id"):
            _identifier(getattr(self, name), name)
        if self.source_entry_id == self.target_entry_id:
            raise DomainValidationError("relationship: endpoints must be distinct")
        _code(self.relation, ("duplicate", "version", "related", "accompanying"), "relation")
        _text(self.detail, "detail")
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusRelationship, "CorpusRelationship")
        return {
            "relationship_id": value.relationship_id,
            "source_entry_id": value.source_entry_id,
            "target_entry_id": value.target_entry_id,
            "relation": value.relation,
            "detail": value.detail,
            "attribution": value.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusRelationship":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusRelationship")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusRelationship")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        return cls(**result)


@dataclass(frozen=True)
class CorpusExposure:
    """A candidate-bearing-material declaration, without authenticated exposure or visibility authority."""

    entry_id: str
    candidate_content: str
    detail: DeclaredText
    attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _identifier(self.entry_id, "entry_id")
        _code(self.candidate_content, ("reported_present", "reported_absent", "unknown"), "candidate_content")
        for name in ("detail", "attribution"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusExposure, "CorpusExposure")
        return {
            "entry_id": value.entry_id,
            "candidate_content": value.candidate_content,
            "detail": value.detail.to_dict(),
            "attribution": value.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusExposure":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusExposure")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusExposure")
        result["detail"] = _nested(result["detail"], DeclaredText, "detail")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        return cls(**result)


@dataclass(frozen=True)
class CorpusEntryChange:
    """An attributed addition, correction or removal in a complete inventory snapshot."""

    action: str
    entry_id: str
    replaces_entry_id: str | None
    reason: str
    attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        _code(self.action, ("added", "corrected", "removed"), "action")
        _identifier(self.entry_id, "entry_id")
        _text(self.reason, "reason")
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))
        if self.replaces_entry_id is not None:
            _identifier(self.replaces_entry_id, "replaces_entry_id")
            if self.action != "added" or self.replaces_entry_id == self.entry_id:
                raise DomainValidationError("replaces_entry_id: only an added entry may replace a distinct removed ID")

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusEntryChange, "CorpusEntryChange")
        return {
            "action": value.action,
            "entry_id": value.entry_id,
            "replaces_entry_id": value.replaces_entry_id,
            "reason": value.reason,
            "attribution": value.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusEntryChange":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusEntryChange")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "CorpusEntryChange")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        return cls(**result)


@dataclass(frozen=True)
class CorpusManifest:
    """An attributed full seed-inventory snapshot whose identity and revision belong to its envelope."""

    title: str
    purpose: str
    selection_provenance: str
    attribution: DeclaredText
    entries: tuple[CorpusEntry, ...]
    observations: tuple[CorpusObservation, ...]
    links: tuple[CorpusLink, ...]
    relationships: tuple[CorpusRelationship, ...]
    exposures: tuple[CorpusExposure, ...]
    limitations: tuple[str, ...]
    supersedes: RecordReference | None
    revision_reason: str
    revision_attribution: DeclaredText
    changes: tuple[CorpusEntryChange, ...]

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed declarations and local invariants."""
        for name in ("title", "purpose", "selection_provenance", "revision_reason"):
            _text(getattr(self, name), name)
        for name in ("attribution", "revision_attribution"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        for name, expected in (("entries", CorpusEntry), ("observations", CorpusObservation),
                               ("links", CorpusLink), ("relationships", CorpusRelationship), ("exposures", CorpusExposure)):
            object.__setattr__(self, name, _values(getattr(self, name), expected, name))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        object.__setattr__(self, "changes", _changes(self.changes))
        if self.supersedes is not None:
            object.__setattr__(self, "supersedes", _reference(self.supersedes, "supersedes", "corpus_manifest", "supersedes"))
        _validate_manifest(self)

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, CorpusManifest, "CorpusManifest")
        return {
            "format": _FORMAT, "version": 1, "kind": "corpus_manifest",
            "title": value.title,
            "purpose": value.purpose,
            "selection_provenance": value.selection_provenance,
            "attribution": value.attribution.to_dict(),
            "entries": [item.to_dict() for item in value.entries],
            "observations": [item.to_dict() for item in value.observations],
            "links": [item.to_dict() for item in value.links],
            "relationships": [item.to_dict() for item in value.relationships],
            "exposures": [item.to_dict() for item in value.exposures],
            "limitations": list(value.limitations),
            "supersedes": None if value.supersedes is None else value.supersedes.to_dict(),
            "revision_reason": value.revision_reason,
            "revision_attribution": value.revision_attribution.to_dict(),
            "changes": [item.to_dict() for item in value.changes],
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusManifest":
        """Decode required fields and bounded arrays, reporting nested field/index failures."""
        _snapshot(value, "CorpusManifest")
        if "format" not in value:
            raise NotTypedContentError("corpus content: missing format discriminator")
        _code(value["format"], (_FORMAT,), "format")
        result = _fields(value, {item.name for item in fields(cls)} | {"format", "version", "kind"}, set(), "CorpusManifest")
        _integer(result["version"], "version", 1)
        if result["version"] != 1:
            raise DomainValidationError("version: unsupported corpus content version")
        _code(result["kind"], ("corpus_manifest",), "kind")
        for name in ("format", "version", "kind"):
            del result[name]
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["entries"] = [_nested(item, CorpusEntry, f"entries[{index}]")
                           for index, item in enumerate(_array(result["entries"], "entries"))]
        result["observations"] = [_nested(item, CorpusObservation, f"observations[{index}]")
                           for index, item in enumerate(_array(result["observations"], "observations"))]
        result["links"] = [_nested(item, CorpusLink, f"links[{index}]")
                           for index, item in enumerate(_array(result["links"], "links"))]
        result["relationships"] = [_nested(item, CorpusRelationship, f"relationships[{index}]")
                           for index, item in enumerate(_array(result["relationships"], "relationships"))]
        result["exposures"] = [_nested(item, CorpusExposure, f"exposures[{index}]")
                           for index, item in enumerate(_array(result["exposures"], "exposures"))]
        result["limitations"] = _array(result["limitations"], "limitations")
        if result["supersedes"] is not None:
            result["supersedes"] = _record_from_dict(result["supersedes"], "supersedes")
        result["revision_attribution"] = _nested(result["revision_attribution"], DeclaredText, "revision_attribution")
        result["changes"] = [_nested(item, CorpusEntryChange, f"changes[{index}]")
                           for index, item in enumerate(_array(result["changes"], "changes", 2048))]
        return cls(**result)


def _local_location(location, entries, field):
    """Require an occurrence to use its own captured entry's exact Source identity/revision."""
    entry = entries.get(location.entry_id)
    if entry is None or entry.status != "captured":
        raise DomainValidationError(f"{field}: entry {location.entry_id} must identify a captured entry")
    if (location.source.record_id, location.source.revision) != (entry.source.record_id, entry.source.revision):
        raise DomainValidationError(f"{field}: entry {location.entry_id} source_location must equal inventory_source pin")


def _location_uses(value):
    """Yield every location occurrence in projection order, preserving each use's diagnostic context."""
    for entry in value.entries:
        for index, location in enumerate(entry.inspection.locations):
            yield f"entry {entry.entry_id} inspection.locations[{index}]", location
    for observation in value.observations:
        for index, location in enumerate(observation.locations):
            yield f"observation {observation.observation_id} locations[{index}]", location
    for link in value.links:
        for name in ("source_location", "target_location"):
            location = getattr(link, name)
            if location is not None:
                yield f"link {link.link_id} {name}", location


def _validate_manifest(value):
    """Check bounded local membership, unique IDs, byte-size consistency and snapshot change declarations."""
    for name, identity in (("entries", "entry_id"), ("observations", "observation_id"),
                           ("links", "link_id"), ("relationships", "relationship_id"),
                           ("exposures", "entry_id"), ("changes", "entry_id")):
        items = getattr(value, name)
        if len({getattr(item, identity) for item in items}) != len(items):
            raise DomainValidationError(f"{name}: duplicate {identity}")
    entries = {entry.entry_id: entry for entry in value.entries}
    if sum(len(entry.originals) for entry in value.entries) > 1024:
        raise DomainValidationError("entries.originals: at most 1024 total originals")
    sizes = {}
    for entry in value.entries:
        for original in entry.originals:
            digest, size = original.artifact.digest, original.artifact.size
            if digest in sizes and sizes[digest] != size:
                raise DomainValidationError(f"entry {entry.entry_id} originals: conflicting size for digest {digest}")
            sizes[digest] = size
    for index, (field, location) in enumerate(_location_uses(value)):
        if index >= 4096:
            raise DomainValidationError("locations: at most 4096 total occurrences")
        _local_location(location, entries, field)
    for observation in value.observations:
        if any(identity not in entries for identity in observation.entry_ids):
            raise DomainValidationError(f"observation {observation.observation_id} entry_ids: unknown entry")
    for link in value.links:
        if link.source_entry_id not in entries or (link.target_entry_id is not None and link.target_entry_id not in entries):
            raise DomainValidationError(f"link {link.link_id}: unknown source/target entry")
    for relationship in value.relationships:
        if relationship.source_entry_id not in entries or relationship.target_entry_id not in entries:
            raise DomainValidationError(f"relationship {relationship.relationship_id}: unknown endpoint")
    for exposure in value.exposures:
        if exposure.entry_id not in entries:
            raise DomainValidationError(f"exposure {exposure.entry_id}: unknown entry")
    removed = {change.entry_id for change in value.changes if change.action == "removed"}
    replacements = set()
    for change in value.changes:
        if (change.entry_id in entries) != (change.action != "removed"):
            raise DomainValidationError(f"change {change.entry_id}: action disagrees with current entry membership")
        if change.replaces_entry_id is not None:
            if change.replaces_entry_id not in removed or change.replaces_entry_id in replacements:
                raise DomainValidationError(f"change {change.entry_id}: replacement must name a uniquely claimed removed entry")
            replacements.add(change.replaces_entry_id)
    if value.supersedes is None:
        if (len(value.changes) != len(entries) or
                any(change.action != "added" or change.replaces_entry_id is not None for change in value.changes)):
            raise DomainValidationError("changes: baseline requires exactly one added declaration per entry, without replacements")


def _validate_selection(value, sources):
    """Check each original and location use against cached typed Sources, without accessing artifact bytes.

    The caller resolves exact targets inside its transaction and translates domain
    failures. Repeated targets never exempt a later entry or location occurrence.
    """
    entries = {entry.entry_id: entry for entry in value.entries}
    for entry in value.entries:
        if entry.source is None:
            continue
        target = (entry.source.record_id, entry.source.revision)
        diagnostic = f"entry {entry.entry_id} inventory_source target {target[0]}@{target[1]}"
        source = sources.get(target)
        if type(source) is not Source:
            raise DomainValidationError(f"{diagnostic}: expected supported typed Source")
        originals = {original.artifact_id: original for original in source.originals}
        for selected in entry.originals:
            original = originals.get(selected.artifact_id)
            if (original is None or selected.path != original.path or selected.artifact != original.artifact
                    or selected.supplied_locator != original.provenance.supplied_locator):
                raise DomainValidationError(f"{diagnostic}: original {selected.artifact_id} mapping disagrees with Source.originals")
    for field, location in _location_uses(value):
        entry = entries[location.entry_id]
        target = (location.source.record_id, location.source.revision)
        source = sources.get(target)
        diagnostic = (f"{field} entry {entry.entry_id} source_location target "
                      f"{target[0]}@{target[1]} location {location.location_id}")
        if type(source) is not Source:
            raise DomainValidationError(f"{diagnostic}: expected supported typed Source")
        found = next((item for item in source.locations if item.location_id == location.location_id), None)
        if found is None or found.artifact_id not in {item.artifact_id for item in entry.originals}:
            raise DomainValidationError(f"{diagnostic}: must anchor to an original selected by this entry")


def _validate_successor(value, previous, used_ids):
    """Validate exact entry diffs and material bindings, updating transaction-local historical IDs.

    Called in ascending revision order after the entire constrained closure is
    decoded. Retaining IDs preserves observations of material; retargeting requires
    a removal and explicitly attributed replacement under a fresh opaque ID.
    """
    before = {} if previous is None else {entry.entry_id: entry for entry in previous.entries}
    after = {entry.entry_id: entry for entry in value.entries}
    expected = {}
    for identity in before.keys() | after.keys():
        if identity not in before:
            if identity in used_ids:
                raise DomainValidationError(f"entry {identity}: previously removed IDs cannot be reused")
            expected[identity] = "added"
        elif identity not in after:
            expected[identity] = "removed"
        elif before[identity] != after[identity]:
            # These declarations bind identity to material, not to a title, classification or hash alone.
            for name in ("status", "origin_collection", "origin_locator", "source", "originals", "uncaptured"):
                if getattr(before[identity], name) != getattr(after[identity], name):
                    raise DomainValidationError(f"entry {identity}: immutable {name} changed; remove and replace under a fresh ID")
            expected[identity] = "corrected"
    actual = {change.entry_id: change.action for change in value.changes}
    if expected != actual:
        raise DomainValidationError(f"changes: must exactly describe entry differences; expected {expected}, found {actual}")
    # Retain removed IDs across every successor; no recursive rescans or stored history metadata.
    used_ids.update(after)


def decode_content(value: dict) -> CorpusManifest:
    """Decode only explicit version-1 corpus content, without target resolution or artifact reads."""
    return CorpusManifest.from_dict(value)


def dumps_content(value: CorpusManifest) -> str:
    """Revalidate an exact manifest and serialize sorted compact ASCII JSON, preserving array order."""
    if type(value) is not CorpusManifest:
        raise DomainValidationError("content: expected CorpusManifest")
    return _snapshot(value.to_dict(), "corpus content")


def _unique_object(pairs):
    """Reject duplicate JSON keys at every depth before ordinary dictionary construction loses them."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError(f"corpus content: duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    """Reject nonfinite JSON constants instead of silently accepting nonstandard numeric values."""
    raise DomainValidationError(f"corpus content: nonfinite JSON constant {value}")


def loads_content(data: str | bytes) -> CorpusManifest:
    """Decode strict UTF-8 JSON, translating syntax, encoding and excessive nesting failures."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("corpus content: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "corpus content JSON")
        return decode_content(json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"corpus content: cannot decode JSON: {error}") from error


def _links(content: CorpusManifest) -> tuple[tuple[RecordReference, ...], tuple[ArtifactReference, ...]]:
    """Project every record occurrence and first occurrence of each directly selected artifact digest."""
    records = (*((content.supersedes,) if content.supersedes is not None else ()),
               *(entry.source for entry in content.entries if entry.source is not None),
               *(location.source for _, location in _location_uses(content)))
    artifacts = {}
    for entry in content.entries:
        for original in entry.originals:
            artifacts.setdefault(original.artifact.digest, original.artifact)
    return records, tuple(artifacts.values())


def _history_link(record_id, revision, content):
    """Require baseline null or this corpus identity's exact immediately preceding revision."""
    previous = content.supersedes
    if revision == 1:
        if previous is not None:
            raise DomainValidationError("supersedes: revision 1 requires null")
    elif previous is None or previous.record_id != record_id or previous.revision != revision - 1:
        raise DomainValidationError("supersedes: required exact same-record immediate predecessor")


def encode_envelope(record_id: str, revision: int, content: CorpusManifest,
                    provenance: CreationProvenance) -> RecordEnvelope:
    """Build a detached null-state corpus envelope with complete exact projections and local history checks."""
    content = loads_content(dumps_content(content))
    provenance = _copy(provenance, CreationProvenance, "provenance")
    records, artifacts = _links(content)
    envelope = RecordEnvelope(record_id, revision, "corpus_manifest", content.to_dict(), provenance, records, artifacts)
    _history_link(envelope.record_id, envelope.revision, content)
    return envelope


def decode_envelope(envelope: RecordEnvelope) -> CorpusManifest:
    """Reject malformed classes, states, history links and ordered projections without repairing them."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected RecordEnvelope")
    try:
        _copy(envelope.provenance, CreationProvenance, "envelope.provenance")
        for name, expected in (("record_references", RecordReference), ("artifact_references", ArtifactReference)):
            values = getattr(envelope, name)
            if type(values) not in (list, tuple):
                raise DomainValidationError(f"envelope.{name}: expected list/tuple")
            for index, value in enumerate(values):
                _copy(value, expected, f"envelope.{name}[{index}]")
    except AttributeError as error:
        raise DomainValidationError("envelope: missing nested value") from error
    checked = _copy(envelope, RecordEnvelope, "envelope")
    content = decode_content(checked.content)
    if checked.kind != "corpus_manifest":
        raise DomainValidationError("envelope.kind: expected corpus_manifest")
    if checked.operational_status is not None or checked.scientific_disposition is not None:
        raise DomainValidationError("envelope: corpus states must be null")
    records, artifacts = _links(content)
    if checked.record_references != records:
        raise DomainValidationError("envelope.record_references: disagree with complete ordered content roles")
    if checked.artifact_references != artifacts:
        raise DomainValidationError("envelope.artifact_references: disagree with complete ordered selected originals")
    _history_link(checked.record_id, checked.revision, content)
    return content
