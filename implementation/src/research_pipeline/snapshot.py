"""Bounded detached navigation metadata, without artifact availability or admission claims."""

from dataclasses import dataclass, fields
import hashlib
import json

from research_pipeline.domain import (
    ArtifactReference, DomainValidationError, RecordEnvelope, _fields, _identifier,
    _integer, _timestamp,
)
from research_pipeline.schema import _json, _VERSIONS


class SnapshotLimitError(ValueError):
    """A complete capture or plan cannot fit the caller's explicit budgets."""


class SnapshotIntegrityError(ValueError):
    """Stored metadata or a detached document is malformed or internally inconsistent."""


@dataclass(frozen=True)
class RootSelector:
    """An explicit current-head request (None) or positive exact revision pin."""

    record_id: str
    revision: int | None

    def __post_init__(self):
        """Validate identity and revision without resolving a live head."""
        _identifier(self.record_id, "record_id")
        if self.revision is not None:
            _integer(self.revision, "revision", 1)

    def to_dict(self):
        """Return a fresh request, revalidating even bypassed frozen fields."""
        self.__post_init__()
        return {"record_id": self.record_id, "revision": self.revision}


@dataclass(frozen=True)
class SnapshotSelection:
    """One project request followed by explicitly ordered additional root requests."""

    project: RootSelector
    roots: tuple[RootSelector, ...]

    def __post_init__(self):
        """Detach list/tuple roots; reject duplicate identical requests, including the project."""
        if type(self.project) is not RootSelector or type(self.roots) not in (tuple, list):
            raise DomainValidationError("selection: expected project selector and explicit list/tuple roots")
        copies = []
        for item in (self.project, *self.roots):
            if type(item) is not RootSelector:
                raise DomainValidationError("selection: expected RootSelector")
            copies.append(RootSelector(**item.to_dict()))
        if len(set(copies)) != len(copies):
            raise DomainValidationError("selection: duplicate identical selector")
        object.__setattr__(self, "project", copies[0])
        object.__setattr__(self, "roots", tuple(copies[1:]))

    def to_dict(self):
        """Revalidate requests and return independent JSON-compatible selection metadata."""
        value = SnapshotSelection(self.project, self.roots)
        return {"project": value.project.to_dict(), "roots": [r.to_dict() for r in value.roots]}


@dataclass(frozen=True)
class SnapshotLimits:
    """Required finite count/byte budgets; output limits include generated descriptors."""

    max_roots: int
    max_records: int
    max_references: int
    max_record_bytes: int
    max_metadata_bytes: int
    max_artifacts: int
    max_files: int
    max_file_bytes: int
    max_total_bytes: int

    def __post_init__(self):
        """Reject coercions and bools; permit zero only for references, artifacts and total bytes."""
        for field in fields(self):
            minimum = 0 if field.name in ("max_references", "max_artifacts", "max_total_bytes") else 1
            _integer(getattr(self, field.name), field.name, minimum)

    def to_dict(self):
        """Return revalidated, detached ordinary integer budgets."""
        self.__post_init__()
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _canonical(value):
    """Encode sorted compact ASCII JSON for identities; nonfinite numbers are forbidden."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _json_parts(value):
    """Yield canonical ASCII JSON in bounded string chunks, avoiding whole-string escape amplification."""
    if type(value) is str:
        yield '"'
        for offset in range(0, len(value), 2048):
            yield json.dumps(value[offset:offset + 2048], ensure_ascii=True)[1:-1]
        yield '"'
    elif type(value) is dict:
        if any(type(key) is not str for key in value):
            raise DomainValidationError("canonical JSON requires string object keys")
        yield "{"
        for index, key in enumerate(sorted(value)):
            if index:
                yield ","
            yield from _json_parts(key)
            yield ":"
            yield from _json_parts(value[key])
        yield "}"
    elif type(value) in (list, tuple):
        yield "["
        for index, item in enumerate(value):
            if index:
                yield ","
            yield from _json_parts(item)
        yield "]"
    else:
        yield json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _bounded_json(value, maximum, label):
    """Serialize incrementally, refusing a representation larger than its byte allowance."""
    chunks = []
    size = 0
    for chunk in _json_parts(value):
        size += len(chunk)  # ensure_ascii makes character and UTF-8 byte counts identical.
        if size > maximum:
            raise SnapshotLimitError(f"{label}: byte budget exceeded")
        chunks.append(chunk)
    return "".join(chunks)


def _strict_json(text, *, maximum_depth=64):
    """Bound nesting before decoding and require canonical JSON; envelope wrappers allow one extra level."""
    if type(text) is not str:
        raise SnapshotIntegrityError("stored JSON must be text")
    depth, quoted, escaped = 0, False, False
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
            depth += 1
            if depth > maximum_depth:
                raise SnapshotIntegrityError(f"JSON nesting exceeds {maximum_depth}")
        elif character in "]}":
            depth -= 1
    try:
        value = _json(text)
        if _canonical(value) != text:
            raise ValueError("noncanonical JSON")
        return value
    except (ValueError, TypeError, RecursionError, OverflowError) as error:
        raise SnapshotIntegrityError(f"stored JSON: {str(error)[:240]}") from error


def _classification(envelope, decoder):
    """Classify complete local codec results without checking targets or historical admission."""
    content = envelope.content
    if "format" not in content:
        return {"category": "generic", "diagnostic": "no_format", "detail": "Typed projection unavailable."}
    formats = {"research_pipeline." + name + "_content" for name in
               ("scientific", "assessment", "work_product", "source", "corpus", "project")}
    if type(content["format"]) is not str or content["format"] not in formats:
        return {"category": "unsupported", "diagnostic": "unknown_format", "detail": "Typed projection unavailable."}
    if "version" in content and (type(content["version"]) is not int or content["version"] != 1):
        return {"category": "unsupported", "diagnostic": "unsupported_version", "detail": "Typed projection unavailable."}
    try:
        decoder(envelope)
    except DomainValidationError as error:
        return {"category": "malformed_typed", "diagnostic": "local_codec_failure", "detail": str(error)[:512]}
    return {"category": "locally_decoded", "diagnostic": "local_codec_only", "detail": "No historical admission certification."}


_SCOPE_POLICY = {
    "traversal": "explicit_roots_complete_outgoing_navigation_closure",
    "not_searched": ["unrelated_records", "reverse_only_incoming_relationships"],
    "artifact_selection": "Every direct attachment of every reached envelope; corpus entry selection and inspection coverage remain separate.",
    "availability": "expected_unverified",
    "authority": "Local decoding is not original submit_typed admission, transitive admission, scientific validity, authenticated authorship or authority.",
    "boundary": "Private local reading snapshot; not a backup, redistributable export, independently filtered worker/reviewer workspace or new source of scientific truth.",
    "restrictions": "Retained declarations are not permission to disclose.",
}


def _scope(selection, resolutions, records, artifacts):
    """Describe precise root/closure and artifact inclusion without reverse or full-store claims."""
    roots = {(r["record_id"], r["revision"]) for r in resolutions}
    return {**_SCOPE_POLICY, "requested": selection, "resolutions": resolutions,
            "closure_only": [{"record_id": r["record_id"], "revision": r["revision"]}
                             for r in records if (r["record_id"], r["revision"]) not in roots],
            "artifact_reasons": [{"digest": a["digest"], "occurrences": a["occurrences"]} for a in artifacts]}


def _schema_identity(version):
    """Hash the registry's fixed whitespace-normalized DDL in its declared order."""
    if type(version) is not int or version not in _VERSIONS:
        raise SnapshotIntegrityError("unsupported schema version")
    ddl = [" ".join(statement.split()) for statement in _VERSIONS[version][0]]
    return {"version": version, "ddl_sha256": hashlib.sha256(_canonical(ddl).encode("ascii")).hexdigest()}


def _commit(value, *, watermark=False):
    """Validate exact local commit metadata; an empty watermark has explicit null fields."""
    names = {"submission_id", "committed_at", "fingerprint"}
    if watermark:
        names.add("event_id")
    _fields(value, names, set(), "commit")
    if watermark and value["event_id"] is None:
        if any(v is not None for v in value.values()):
            raise SnapshotIntegrityError("inconsistent empty-store watermark")
        return
    if watermark:
        _integer(value["event_id"], "event_id", 1)
    _identifier(value["submission_id"], "submission_id")
    if _timestamp(value["committed_at"]) != value["committed_at"]:
        raise SnapshotIntegrityError("noncanonical commit timestamp")
    ArtifactReference(value["fingerprint"], 0)


def _validate_document(document):
    """Check serialized capture structure, exact closure, accounting and self identity at boundaries."""
    from research_pipeline.store import _decode_typed_envelope

    required = {"format", "snapshot_id", "selection", "resolutions", "schema", "watermark", "records",
                "artifacts", "limits", "scope", "metadata_fetched_bytes"}
    _fields(document, required, set(), "snapshot")
    if document["format"] != "research_pipeline.snapshot.v1":
        raise SnapshotIntegrityError("unsupported snapshot format")
    limits = SnapshotLimits(**document["limits"])
    _integer(document["metadata_fetched_bytes"], "metadata_fetched_bytes", 0)
    _bounded_json(document, limits.max_metadata_bytes - document["metadata_fetched_bytes"], "max_metadata_bytes")
    selection = document["selection"]
    _fields(selection, {"project", "roots"}, set(), "selection")
    if type(selection["roots"]) is not list:
        raise DomainValidationError("roots must be a list")
    requested = SnapshotSelection(RootSelector(**selection["project"]),
                                  tuple(RootSelector(**r) for r in selection["roots"]))
    selectors = (requested.project, *requested.roots)
    if len(selectors) > limits.max_roots:
        raise SnapshotLimitError("max_roots exceeded")
    if document["schema"] != _schema_identity(document["schema"]["version"]):
        raise SnapshotIntegrityError("schema identity mismatch")
    _commit(document["watermark"], watermark=True)
    records, artifacts = document["records"], document["artifacts"]
    if type(records) is not list or type(artifacts) is not list or not records:
        raise SnapshotIntegrityError("snapshot requires record and artifact arrays")
    if len(records) > limits.max_records or len(artifacts) > limits.max_artifacts:
        raise SnapshotLimitError("record/artifact count exceeded")
    if document["watermark"]["event_id"] is None:
        raise SnapshotIntegrityError("selected committed records cannot have an empty-store watermark")
    values, occurrences = {}, {}
    references = 0
    for record in records:
        _fields(record, {"record_id", "revision", "content_json", "provenance_json", "envelope_json",
                         "classification", "commit", "fetched_bytes"}, set(), "snapshot record")
        _bounded_json(record, limits.max_record_bytes, "max_record_bytes")
        stored_envelope = _strict_json(record["envelope_json"], maximum_depth=65)
        envelope = RecordEnvelope.from_dict(stored_envelope)
        if envelope.kind not in _VERSIONS[document["schema"]["version"]][1]:
            raise SnapshotIntegrityError("record kind unavailable in captured schema")
        key = (envelope.record_id, envelope.revision)
        _identifier(record["record_id"], "snapshot record_id")
        _integer(record["revision"], "snapshot revision", 1)
        if key != (record["record_id"], record["revision"]) or key in values:
            raise SnapshotIntegrityError("duplicate or mismatched record identity")
        _strict_json(record["content_json"])
        _strict_json(record["provenance_json"])
        # Python equality aliases 1, 1.0 and True. Exact redundant JSON must
        # retain scalar spelling/types even when a caller recomputes the ID.
        if (_canonical(envelope.to_dict()) != record["envelope_json"]
                or record["content_json"] != _canonical(envelope.content)
                or record["provenance_json"] != _canonical(envelope.provenance.to_dict())):
            raise SnapshotIntegrityError("inconsistent exact JSON representations")
        if record["classification"] != _classification(envelope, _decode_typed_envelope):
            raise SnapshotIntegrityError("inconsistent local classification")
        _commit(record["commit"])
        if record["commit"]["submission_id"] == document["watermark"]["submission_id"]:
            if record["commit"] != {k: v for k, v in document["watermark"].items() if k != "event_id"}:
                raise SnapshotIntegrityError("record commit disagrees with watermark")
        _integer(record["fetched_bytes"], "fetched_bytes", 1)
        if record["fetched_bytes"] > limits.max_record_bytes:
            raise SnapshotLimitError("max_record_bytes fetched metadata exceeded")
        values[key] = envelope
        references += len(envelope.record_references) + len(envelope.artifact_references)
        if references > limits.max_references:
            raise SnapshotLimitError("max_references exceeded")
        for ordinal, ref in enumerate(envelope.artifact_references):
            previous = occurrences.setdefault(ref.digest, {"digest": ref.digest, "size": ref.size,
                                                           "availability": "expected_unverified", "occurrences": []})
            if previous["size"] != ref.size:
                raise SnapshotIntegrityError("conflicting artifact sizes")
            previous["occurrences"].append({"record_id": key[0], "revision": key[1], "ordinal": ordinal})
    if (list(values) != sorted(values)
            or _canonical(artifacts) != _canonical([occurrences[k] for k in sorted(occurrences)])):
        raise SnapshotIntegrityError("noncanonical record/artifact inventory")
    if (any(a["size"] > limits.max_file_bytes for a in artifacts)
            or sum(a["size"] for a in artifacts) > limits.max_total_bytes):
        raise SnapshotLimitError("expected artifact bytes exceeded")
    resolutions = document["resolutions"]
    if type(resolutions) is not list or len(resolutions) != len(selectors):
        raise SnapshotIntegrityError("root resolutions mismatch")
    for selector, pin in zip(selectors, resolutions):
        _fields(pin, {"record_id", "revision"}, set(), "resolution")
        RootSelector(**pin)
        if (pin["revision"] is None or pin["record_id"] != selector.record_id
                or selector.revision not in (None, pin["revision"])
                or (pin["record_id"], pin["revision"]) not in values):
            raise SnapshotIntegrityError("invalid resolved root")
    first = resolutions[0]
    if values[(first["record_id"], first["revision"])].kind != "project":
        raise SnapshotIntegrityError("selected project is not project kind")
    reached = set()
    enqueued = {(pin["record_id"], pin["revision"]) for pin in resolutions}
    pending = list(enqueued)
    while pending:
        key = pending.pop()
        if key in reached:
            continue
        reached.add(key)
        for ordinal, edge in enumerate(values[key].record_references):
            target = (edge.record_id, edge.revision)
            if target not in values or edge.target_kind not in (None, values[target].kind):
                raise SnapshotIntegrityError(f"{key[0]}@{key[1]} edge {ordinal}: absent/wrong-kind target")
            if target not in enqueued:
                enqueued.add(target)
                pending.append(target)
    if reached != set(values):
        raise SnapshotIntegrityError("snapshot contains records outside outgoing closure")
    if _canonical(document["scope"]) != _canonical(_scope(selection, resolutions, records, artifacts)):
        raise SnapshotIntegrityError("scope metadata mismatch")
    fetched = document["metadata_fetched_bytes"]
    _integer(fetched, "metadata_fetched_bytes", 0)
    if fetched < sum(r["fetched_bytes"] for r in records):
        raise SnapshotIntegrityError("inconsistent fetched metadata accounting")
    _bounded_json(document, limits.max_metadata_bytes - fetched, "max_metadata_bytes")
    body = {key: value for key, value in document.items() if key != "snapshot_id"}
    if document["snapshot_id"] != hashlib.sha256(_canonical(body).encode("ascii")).hexdigest():
        raise SnapshotIntegrityError("snapshot identity mismatch")


@dataclass(frozen=True, init=False)
class DetachedSnapshot:
    """Private serialized immutable metadata; accessors always reconstruct detached values."""

    _serialized: str

    def __init__(self, document: dict):
        """Validate a complete version-1 document and retain only canonical serialized text."""
        try:
            _validate_document(document)
            object.__setattr__(self, "_serialized", _canonical(document))
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError) as error:
            if isinstance(error, (SnapshotLimitError, SnapshotIntegrityError)):
                raise
            raise SnapshotIntegrityError(f"invalid detached snapshot: {str(error)[:240]}") from error

    def to_dict(self):
        """Return fresh full metadata after verifying retained state and identity."""
        try:
            document = _strict_json(self._serialized)
            _validate_document(document)
            return document
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError) as error:
            if isinstance(error, (SnapshotLimitError, SnapshotIntegrityError)):
                raise
            raise SnapshotIntegrityError(f"invalid detached snapshot: {str(error)[:240]}") from error

    @property
    def snapshot_id(self):
        """Return the validated content identity, independent of time, paths and object availability."""
        return self.to_dict()["snapshot_id"]

    @property
    def selection(self):
        """Reconstruct the original ordered requests, retaining current/exact distinctions."""
        value = self.to_dict()["selection"]
        return SnapshotSelection(RootSelector(**value["project"]), tuple(RootSelector(**r) for r in value["roots"]))

    @property
    def resolutions(self):
        """Return fresh exact pins in requested order."""
        return tuple(RootSelector(**pin) for pin in self.to_dict()["resolutions"])

    @property
    def schema(self):
        """Return detached version and normalized fixed-DDL identity."""
        return self.to_dict()["schema"]

    @property
    def watermark(self):
        """Return the local commit watermark; this is not a database UUID or authentication."""
        return self.to_dict()["watermark"]

    @property
    def records(self):
        """Return fresh sorted record metadata including exact JSON and ordered links."""
        return tuple(self.to_dict()["records"])

    @property
    def artifacts(self):
        """Return detached distinct artifact expectations and all inclusion occurrences."""
        return tuple(self.to_dict()["artifacts"])

    @property
    def limits(self):
        """Reconstruct the effective required budgets."""
        return SnapshotLimits(**self.to_dict()["limits"])

    @property
    def scope(self):
        """Return fresh inclusion reasons and explicit navigation/admission limitations."""
        return self.to_dict()["scope"]
