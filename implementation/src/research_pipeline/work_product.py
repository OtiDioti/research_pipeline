"""Pure versioned multi-file declarations; paths and kind labels confer no authority."""

from dataclasses import dataclass, fields
import json
import unicodedata

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, _fields, _integer, _snapshot, _validate_json_string,
)
from research_pipeline.scientific import (
    NotTypedContentError, _collection, _list, _record_from_dict, _record_list,
    _text, _texts,
)
from research_pipeline.assessment import (
    _code, _copy, _nested, _rebuild, _reference, _references,
)


_FORMAT = "research_pipeline.work_product_content"
_PRODUCT_KINDS = ("note", "derivation", "calculation", "notebook", "checkpoint",
                  "reading_report", "end_of_run_report", "figure", "program", "context_packet")
_OPTIONAL_ROLES = (("task", "task_specification"), ("branch", "branch"),
                   ("context", "research_context"), ("run", "run"),
                   ("supersedes", "work_product_manifest"))
_COLLECTION_ROLES = (("linked_claims", "linked_claim", "claim"),
                     ("linked_sources", "linked_source", "source"),
                     ("build_dependencies", "build_dependency", None))
_DEVICES = {"con", "prn", "aux", "nul", "clock$", "conin$", "conout$"} | {
    f"{prefix}{digit}" for prefix in ("com", "lpt") for digit in range(1, 10)}


def _component(component: str, field: str) -> None:
    """Reject unsafe original or alias components before any path normalization."""
    if (not component or component in (".", "..") or component.endswith((" ", "."))
            or any(char in '/\\<>:"|?*' or unicodedata.category(char) in ("Cc", "Cf")
                   for char in component)):
        raise DomainValidationError(f"{field}: unsafe logical path component {component!r}")


def _path(value: str, field: str) -> tuple[str, ...]:
    """Validate a portable relative POSIX path and return its conservative component keys.

    NFKC/casefold intentionally rejects some distinct case-sensitive names. Keys
    only detect ambiguity; original spellings are never rewritten or opened.
    """
    if type(value) is not str or not value:
        raise DomainValidationError(f"{field}: expected nonempty logical path string")
    _validate_json_string(value, field)
    keys = []
    for component in value.split("/"):
        _component(component, field)
        key = unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", component).casefold())
        _component(key, field)
        if key.split(".", 1)[0].rstrip(" ") in _DEVICES:
            raise DomainValidationError(f"{field}: reserved device component {component!r}")
        keys.append(key)
    return tuple(keys)


def _validate_paths(paths) -> None:
    """Check ordered logical paths for portable aliases and file/directory collisions."""
    prefixes = {}
    for index, path in enumerate(paths):
        keys = _path(path, f"files[{index}].path")
        original = tuple(path.split("/"))
        for length in range(1, len(keys) + 1):
            prefix = keys[:length]
            is_file = length == len(keys)
            prior = prefixes.get(prefix)
            if prior is not None:
                spelling, was_file, prior_path = prior
                # Shared directories must retain identical spelling. A file can
                # never be reused as a directory, in either insertion order.
                if spelling != original[:length] or was_file or is_file:
                    raise DomainValidationError(f"files: conflicting paths {prior_path!r} and {path!r}")
            else:
                prefixes[prefix] = (original[:length], is_file, path)


def _files(values) -> tuple["WorkProductFile", ...]:
    """Detach files and reject ambiguous paths, file/directory collisions and conflicting sizes."""
    result = tuple(_copy(value, WorkProductFile, f"files[{index}]")
                   for index, value in enumerate(_collection(values, "files")))
    if not result:
        raise DomainValidationError("files: expected nonempty collection")
    _validate_paths([value.path for value in result])
    sizes = {}
    for index, value in enumerate(result):
        digest, size = value.artifact.digest, value.artifact.size
        if digest in sizes and sizes[digest] != size:
            raise DomainValidationError(f"files[{index}].artifact: conflicting size for digest {digest}")
        sizes[digest] = size
    return result


@dataclass(frozen=True)
class WorkProductFile:
    """One safe logical path and immutable byte reference, without filesystem access."""

    path: str
    artifact: ArtifactReference

    def __post_init__(self) -> None:
        """Validate the original path and detach an exact artifact value; availability is not checked."""
        _path(self.path, "path")
        object.__setattr__(self, "artifact", _copy(self.artifact, ArtifactReference, "artifact"))

    def to_dict(self) -> dict:
        """Return fresh exact path/artifact fields after revalidating bypassed frozen state."""
        value = _rebuild(self, WorkProductFile, "file")
        return {"path": value.path, "artifact": value.artifact.to_dict()}

    @classmethod
    def from_dict(cls, value: dict) -> "WorkProductFile":
        """Decode exactly path and artifact, including strict nested digest/size fields."""
        _snapshot(value, "file")
        result = _fields(value, {"path", "artifact"}, set(), "file")
        result["artifact"] = _nested(result["artifact"], ArtifactReference, "artifact")
        return cls(**result)


@dataclass(frozen=True)
class WorkProductManifest:
    """Ordered immutable files and attributed descriptive links, never execution or support authority."""

    product_kind: str
    title: str
    purpose: str
    authors: tuple[str, ...]
    task: RecordReference | None
    branch: RecordReference | None
    context: RecordReference | None
    run: RecordReference | None
    linked_claims: tuple[RecordReference, ...]
    linked_sources: tuple[RecordReference, ...]
    supersedes: RecordReference | None
    build_dependencies: tuple[RecordReference, ...]
    files: tuple[WorkProductFile, ...]
    entry_file: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach declarations, validate roles and portable paths, and require exact entry membership."""
        _code(self.product_kind, _PRODUCT_KINDS, "product_kind")
        _text(self.title, "title")
        _text(self.purpose, "purpose")
        object.__setattr__(self, "authors", _texts(self.authors, "authors"))
        if not self.authors:
            raise DomainValidationError("authors: expected nonempty collection")
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        for name, kind in _OPTIONAL_ROLES:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _reference(value, name, kind, name))
        for name, role, kind in _COLLECTION_ROLES:
            object.__setattr__(self, name, _references(getattr(self, name), role, kind, name))
        object.__setattr__(self, "files", _files(self.files))
        _path(self.entry_file, "entry_file")
        if self.entry_file not in {value.path for value in self.files}:
            raise DomainValidationError("entry_file: must equal a supplied file path exactly")

    def to_dict(self) -> dict:
        """Return fresh version-1 JSON fields, rejecting forged values and retaining all array order."""
        value = _rebuild(self, WorkProductManifest, "work_product_manifest")
        return dict(format=_FORMAT, version=1, kind="work_product_manifest",
                    product_kind=value.product_kind, title=value.title, purpose=value.purpose,
                    authors=list(value.authors),
                    **{name: None if getattr(value, name) is None else getattr(value, name).to_dict()
                       for name, _ in _OPTIONAL_ROLES},
                    **{name: [item.to_dict() for item in getattr(value, name)]
                       for name, _, _ in _COLLECTION_ROLES},
                    files=[item.to_dict() for item in value.files], entry_file=value.entry_file,
                    limitations=list(value.limitations))

    @classmethod
    def from_dict(cls, value: dict) -> "WorkProductManifest":
        """Decode the fixed discriminator and exact required fields, never inferring missing declarations."""
        _snapshot(value, "work product content")
        if "format" not in value:
            raise NotTypedContentError("work product content: missing format discriminator")
        if type(value["format"]) is not str or value["format"] != _FORMAT:
            raise DomainValidationError("format: unsupported work product content format")
        result = _fields(value, {item.name for item in fields(cls)} | {"format", "version", "kind"},
                         set(), "work_product_manifest")
        _integer(result["version"], "version", 1)
        if result["version"] != 1:
            raise DomainValidationError("version: unsupported work product content version")
        _code(result["kind"], ("work_product_manifest",), "kind")
        for name in ("format", "version", "kind"):
            del result[name]
        for name, _ in _OPTIONAL_ROLES:
            if result[name] is not None:
                result[name] = _record_from_dict(result[name], name)
        for name, _, _ in _COLLECTION_ROLES:
            result[name] = _record_list(result[name], name)
        result["files"] = [_nested(item, WorkProductFile, f"files[{index}]")
                           for index, item in enumerate(_list(result["files"], "files"))]
        for name in ("authors", "limitations"):
            result[name] = _list(result[name], name)
        return cls(**result)


def decode_content(value: dict) -> WorkProductManifest:
    """Decode explicitly marked version-1 manifest content; malformed data raises domain errors."""
    return WorkProductManifest.from_dict(value)


def dumps_content(value: WorkProductManifest) -> str:
    """Revalidate an exact manifest and encode compact sorted-key ASCII JSON with ordered arrays."""
    if type(value) is not WorkProductManifest:
        raise DomainValidationError("content: expected WorkProductManifest")
    return _snapshot(value.to_dict(), "work product content")


def _unique_object(pairs: list) -> dict:
    """Reject duplicate JSON fields at every depth while constructing ordinary dictionaries."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError(f"work product content: duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    """Reject nonfinite JSON literals with a content-specific validation error."""
    raise DomainValidationError(f"work product content: nonfinite JSON constant {value}")


def loads_content(data: str | bytes) -> WorkProductManifest:
    """Decode strict UTF-8 JSON and translate syntax, encoding and depth errors with chained causes."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("work product content: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "work product content JSON")
        return decode_content(json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"work product content: cannot decode JSON: {error}") from error


def _links(content: WorkProductManifest) -> tuple[tuple[RecordReference, ...], tuple[ArtifactReference, ...]]:
    """Project ordered semantic roles and the first occurrence of each immutable object digest."""
    records = (*(value for value in (content.task, content.branch, content.context, content.run)
                 if value is not None), *content.linked_claims, *content.linked_sources,
               *((content.supersedes,) if content.supersedes is not None else ()), *content.build_dependencies)
    # Paths remain separate in content; only envelope object links are deduplicated.
    artifacts = {}
    for value in content.files:
        artifacts.setdefault(value.artifact.digest, value.artifact)
    return records, tuple(artifacts.values())


def _supersession(record_id: str, revision: int, content: WorkProductManifest) -> None:
    """Check optional supersession using only the envelope identity/revision, without historical lookup."""
    reference = content.supersedes
    if reference is not None and (revision == 1 or reference.record_id != record_id
                                  or reference.revision != revision - 1):
        raise DomainValidationError("supersedes: must name this record's immediately preceding revision; revision 1 requires null")


def encode_envelope(record_id: str, revision: int, content: WorkProductManifest,
                    provenance: CreationProvenance) -> RecordEnvelope:
    """Build a detached manifest envelope with null states, ordered links and local supersession checks."""
    content = loads_content(dumps_content(content))
    provenance = _copy(provenance, CreationProvenance, "provenance")
    records, artifacts = _links(content)
    envelope = RecordEnvelope(record_id, revision, "work_product_manifest", content.to_dict(), provenance,
                              records, artifacts, operational_status=None, scientific_disposition=None)
    _supersession(envelope.record_id, envelope.revision, content)
    return envelope


def decode_envelope(envelope: RecordEnvelope) -> WorkProductManifest:
    """Reconstruct exact classes and demand complete ordered coherence and envelope-local supersession."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected RecordEnvelope")
    try:
        _copy(envelope.provenance, CreationProvenance, "envelope.provenance")
        for name, expected in (("record_references", RecordReference), ("artifact_references", ArtifactReference)):
            for index, value in enumerate(_collection(getattr(envelope, name), f"envelope.{name}")):
                _copy(value, expected, f"envelope.{name}[{index}]")
    except AttributeError as error:
        raise DomainValidationError("envelope: missing nested value") from error
    checked = _copy(envelope, RecordEnvelope, "envelope")
    content = decode_content(checked.content)
    if checked.kind != "work_product_manifest":
        raise DomainValidationError("envelope.kind: expected work_product_manifest")
    if checked.operational_status is not None or checked.scientific_disposition is not None:
        raise DomainValidationError("envelope: work product states must be null")
    records, artifacts = _links(content)
    if checked.record_references != records:
        raise DomainValidationError("envelope.record_references: disagree with complete ordered content roles")
    if checked.artifact_references != artifacts:
        raise DomainValidationError("envelope.artifact_references: disagree with complete ordered content files")
    _supersession(checked.record_id, checked.revision, content)
    return content
