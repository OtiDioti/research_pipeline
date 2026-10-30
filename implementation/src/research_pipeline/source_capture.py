"""Explicit bounded local Source preparation and pure saved requests; never implicit commit."""

from contextlib import ExitStack
from dataclasses import dataclass, fields
import json
import os
from pathlib import Path
import stat

from research_pipeline.assessment import _copy, _reference, _unique_targets
from research_pipeline.checkout import (
    CheckoutIntegrityError, CheckoutLayoutError, _Directories, _capture_leaf,
    _operation, _outside, _path, _read_bytes, _stat, _unchanged,
)
from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, RecordReference, Submission,
    _fields, _identifier, _integer, _snapshot, _validate_json_string,
)
from research_pipeline.source import (
    DeclaredText, LocationMapping, RelatedSource, Source, SourceExtraction,
    SourceLocation, SourceProvenance, SourceReading, SourceRestrictions,
    SourceStatement, ToolSetting, _collection, _ids, _reject_constant, _texts,
    _unique_object, decode_envelope, encode_envelope,
)
from research_pipeline.store import RecordStore
from research_pipeline.work_product import _validate_paths


_FORMAT = "research_pipeline.source_capture_submission"


def _proposal(value):
    """Reconstruct one coherent Source request, rejecting forged values and mismatched CAS."""
    if type(value) is not Submission:
        raise DomainValidationError("proposal: expected Submission")
    try:
        _copy(value.provenance, CreationProvenance, "submission.provenance")
        if type(value.records) not in (tuple, list) or len(value.records) != 1:
            raise DomainValidationError("proposal: requires exactly one Source envelope")
        decode_envelope(value.records[0])
        original = value.to_dict()
        result = Submission.from_dict(original)
        if _snapshot(original, "proposal") != _snapshot(result.to_dict(), "proposal"):
            raise DomainValidationError("proposal: nested values must already be canonical")
        envelope = result.records[0]
        decode_envelope(envelope)
        if result.expected_heads != {envelope.record_id: envelope.revision - 1}:
            raise DomainValidationError("proposal: expected head must equal revision minus one")
        return result
    except (AttributeError, TypeError, KeyError, RecursionError) as error:
        raise DomainValidationError(f"proposal: malformed request: {error}") from error


def dumps_prepared_submission(submission: Submission) -> str:
    """Purely encode one complete Source request as deterministic compact sorted ASCII JSON.

    Validate nested values without storage, admission, IDs or timestamp generation.
    A structurally valid saved request can still fail historical admission at commit.
    """
    value = _proposal(submission)
    return _snapshot(dict(format=_FORMAT, version=1, submission=value.to_dict()), "proposal")


def loads_prepared_submission(data: str | bytes) -> Submission:
    """Decode strict UTF-8 Source proposal JSON with all nested fields explicit.

    Reject duplicates, nonfinite numbers, malformed Unicode, coercion and changed
    projections. No filesystem/store access or reconciliation occurs here.
    """
    if type(data) not in (str, bytes):
        raise DomainValidationError("proposal: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "proposal JSON")
        value = json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        canonical = _snapshot(value, "proposal")
        _fields(value, {"format", "version", "submission"}, set(), "proposal")
        if value["format"] != _FORMAT or type(value["version"]) is not int or value["version"] != 1:
            raise DomainValidationError("proposal: unsupported format/version")
        result = _proposal(Submission.from_dict(value["submission"]))
        if canonical != dumps_prepared_submission(result):
            raise DomainValidationError("proposal: incomplete or noncanonical nested fields")
        return result
    except DomainValidationError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"proposal: cannot decode JSON: {error}") from error


def _inventory(value):
    """Flatten originals then extraction outputs in the accepted Source inventory order."""
    return [*value.originals, *(entry for extraction in value.extractions for entry in extraction.outputs)]


def _paths(paths):
    """Validate exact portable spellings independently, including Source's path-length bound."""
    _validate_paths(paths)
    if any(len(path) > 4096 for path in paths):
        raise DomainValidationError("path: at most 4096 characters")


def _local_provenance(value, supplied_path):
    """Require caller-declared available local acquisition to name the exact selected path."""
    if (value.method != "supplied_local" or value.outcome != "available"
            or value.supplied_locator.value != supplied_path):
        raise DomainValidationError("provenance: requires available supplied_local and exact supplied_locator")


def _mapping(submission, mapping):
    """Validate an explanatory mapping against every ordered canonical inventory occurrence."""
    _fields(mapping, {"input_root", "files"}, set(), "mapping")
    mapping = json.loads(_snapshot(mapping, "mapping"))
    root = mapping["input_root"]
    if type(root) is not str or not root.startswith("/") or str(_path(root)) != root:
        raise DomainValidationError("mapping.input_root: expected anchored lexical absolute path")
    entries = _inventory(decode_envelope(submission.records[0]))
    if type(mapping["files"]) is not list or not entries or len(mapping["files"]) != len(entries):
        raise DomainValidationError("mapping.files: must cover the complete nonempty inventory")
    selected = []
    for item, entry in zip(mapping["files"], entries):
        _fields(item, {"input_path", "supplied_path", "artifact_id", "path", "artifact",
                       "original_mode", "provenance"}, set(), "mapping file")
        _paths([item["input_path"]])
        supplied = str(Path(root) / item["input_path"])
        _local_provenance(entry.provenance, supplied)
        if entry.original_mode is None:
            raise DomainValidationError("mapping.original_mode: captured mode required")
        expected = dict(input_path=item["input_path"], supplied_path=supplied,
                        **{name: entry.to_dict()[name] for name in (
                            "artifact_id", "path", "artifact", "original_mode", "provenance")})
        if _snapshot(item, "mapping file") != _snapshot(expected, "mapping file"):
            raise DomainValidationError("mapping file: disagrees with Source inventory")
        selected.append(item["input_path"])
    _paths(selected)
    return mapping


@dataclass(frozen=True, init=False)
class PreparedSourceCapture:
    """Canonical request and checked explanatory mapping, freshly detached on every access."""

    _submission_json: str
    _mapping_json: str

    def __init__(self, submission: Submission, mapping: dict):
        """Snapshot a valid proposal and reject mappings inconsistent with its Source inventory."""
        serialized = dumps_prepared_submission(submission)
        checked = _mapping(loads_prepared_submission(serialized), mapping)
        object.__setattr__(self, "_submission_json", serialized)
        object.__setattr__(self, "_mapping_json", _snapshot(checked, "mapping"))

    @property
    def submission(self) -> Submission:
        """Return a newly reconstructed exact request for caller-controlled save or explicit commit."""
        return loads_prepared_submission(self._submission_json)

    @property
    def mapping(self) -> dict:
        """Return fresh explanatory JSON data; this mapping grants no commit authority."""
        return json.loads(self._mapping_json)


def _fault(boundary):
    """Private deterministic mutation seam before real checks, never a public API callback."""


def _template(metadata):
    """Validate complete standalone template declarations before any content reads.

    Inventory references/modes are deliberately absent. Cross-inventory lineage and
    actual byte ranges are checked later by Source.from_dict using captured evidence.
    """
    _fields(metadata, {field.name for field in fields(Source)}, set(), "metadata")
    data = json.loads(_snapshot(metadata, "metadata"))
    _identifier(data["work_id"], "work_id")
    for name, cls in (("upstream_identity", DeclaredText), ("upstream_version", DeclaredText),
                      ("title", DeclaredText), ("provenance", SourceProvenance),
                      ("restrictions", SourceRestrictions), ("reading", SourceReading)):
        cls.from_dict(data[name])
    for name, cls in (("authors", DeclaredText), ("locations", SourceLocation),
                      ("statements", SourceStatement), ("related_sources", RelatedSource)):
        for item in _collection(data[name], name):
            cls.from_dict(item)
    if not data["authors"]:
        raise DomainValidationError("authors: nonempty collection required")
    _texts(data["limitations"], "limitations")
    if data["supersedes"] is not None:
        previous = RecordReference.from_dict(data["supersedes"])
        _reference(previous, "supersedes", "source", "supersedes")
        if previous.to_dict() != data["supersedes"]:
            raise DomainValidationError("supersedes: incomplete nested fields")
    _unique_targets(tuple(RelatedSource.from_dict(item).reference for item in data["related_sources"]),
                    "related_sources")
    entries = list(_collection(data["originals"], "originals"))
    for extraction in _collection(data["extractions"], "extractions"):
        _fields(extraction, {field.name for field in fields(SourceExtraction)}, set(), "extraction")
        _identifier(extraction["extraction_id"], "extraction_id")
        inputs = _ids(extraction["original_inputs"], "original_inputs")
        for name in ("tool", "tool_version"):
            DeclaredText.from_dict(extraction[name])
        settings = [ToolSetting.from_dict(item) for item in _collection(extraction["settings"], "settings")]
        mappings = [LocationMapping.from_dict(item) for item in _collection(extraction["mappings"], "mappings")]
        warnings = _texts(extraction["warnings"], "warnings")
        outputs = _collection(extraction["outputs"], "outputs")
        if not inputs or not outputs or (not mappings and not warnings):
            raise DomainValidationError("extraction: inputs, outputs and mappings or warnings required")
        if len({item.name for item in settings}) != len(settings) or len(set(mappings)) != len(mappings):
            raise DomainValidationError("extraction: duplicate setting or mapping")
        entries.extend(outputs)
    if len(entries) > 1024:
        raise DomainValidationError("inventory: at most 1024 entries")
    for entry in entries:
        _fields(entry, {"artifact_id", "path", "media_type", "provenance"}, set(), "inventory entry")
        _identifier(entry["artifact_id"], "artifact_id")
        DeclaredText.from_dict(entry["media_type"])
        SourceProvenance.from_dict(entry["provenance"])
    if len({entry["artifact_id"] for entry in entries}) != len(entries):
        raise DomainValidationError("artifact_id: duplicate ID")
    _paths([entry["path"] for entry in entries])
    return data, entries


def _directory_safety(directories, root):
    """Check retained names, ownership and permission stability without directory-content timestamps.

    Root-owned sticky shared ancestors are allowed only outside the selected root.
    Sibling activity is irrelevant; uid/gid/mode and device/inode bindings are not.
    """
    directories.check()
    for parent, name, descriptor, original, _, _, path in directories.bindings:
        current, held = _stat(parent, name), os.fstat(descriptor)
        inside = Path(path) == root or root in Path(path).parents
        for info in (current, held):
            if (info.st_uid, info.st_gid, info.st_mode) != (original.st_uid, original.st_gid, original.st_mode):
                raise CheckoutIntegrityError(f"directory {path}: ownership or mode changed")
            mode = stat.S_IMODE(info.st_mode)
            shared = not inside and info.st_uid == 0 and mode & 0o1000
            if (info.st_uid not in (0, os.geteuid())
                    or (inside and (info.st_uid != os.geteuid() or mode & 0o500 != 0o500))
                    or mode & (0o6000 if shared else 0o7022)):
                raise CheckoutLayoutError(f"directory {path}: unsafe ownership or permissions")


def prepare_source_capture(
        store: RecordStore, input_root, *, selected_files, metadata: dict,
        record_id: str, revision: int, expected_head: int, submission_id: str,
        record_provenance: CreationProvenance, submission_provenance: CreationProvenance,
        source_root, backup_roots, control_roots, max_file_bytes: int,
        max_total_bytes: int, max_files: int) -> PreparedSourceCapture:
    """Capture explicitly selected inert bytes and preview one exact Source submission.

    Require complete declarations, ordered selection, finite budgets and trusted
    exclusions. Only artifact objects are published; failures can retain orphans.
    Held no-follow descriptors and observed signatures detect changes under the
    documented POSIX trusted-owner/mount contract, not arbitrary hostile owners.
    No enumeration, parsing, input repair, metadata writes or reservations occur.
    Save the detached request durably, then explicitly submit_typed that saved value;
    repeating preparation is not original-ID reconciliation.
    """
    for name, value, minimum in (("revision", revision, 1), ("expected_head", expected_head, 0),
                                 ("max_file_bytes", max_file_bytes, 0),
                                 ("max_total_bytes", max_total_bytes, 0), ("max_files", max_files, 1)):
        _integer(value, name, minimum)
    if expected_head > 2**63 - 2 or revision != expected_head + 1:
        raise DomainValidationError("revision: requires expected_head + 1 within the revision range")
    if type(selected_files) not in (list, tuple) or not selected_files:
        raise DomainValidationError("selected_files: explicit nonempty list/tuple required")
    # Bound count before copying or inspecting entries, even malformed entries.
    if len(selected_files) > min(max_files, 1024):
        raise DomainValidationError("selected_files: exceeds max_files or Source inventory cap")
    selected = []
    for item in selected_files:
        selected.append(_fields(item, {"artifact_id", "input_path"}, set(), "selected file"))
    _paths([item["input_path"] for item in selected])
    _identifier(record_id, "record_id")
    _identifier(submission_id, "submission_id")
    record_provenance = _copy(record_provenance, CreationProvenance, "record_provenance")
    submission_provenance = _copy(submission_provenance, CreationProvenance, "submission_provenance")
    data, entries = _template(metadata)
    for item in selected:
        _identifier(item["artifact_id"], "artifact_id")
    if [item["artifact_id"] for item in selected] != [entry["artifact_id"] for entry in entries]:
        raise DomainValidationError("selected_files: IDs must equal complete ordered inventory")
    previous = data["supersedes"]
    if previous is not None and (revision == 1 or previous["record_id"] != record_id
                                 or previous["revision"] != revision - 1):
        raise DomainValidationError("supersedes: requires this capture's immediate predecessor")
    if any(item["reference"]["record_id"] == record_id for item in data["related_sources"]):
        raise DomainValidationError("related_sources: same capture identity requires supersedes")
    for name, roots in (("backup_roots", backup_roots), ("control_roots", control_roots)):
        if type(roots) not in (list, tuple):
            raise DomainValidationError(f"{name}: explicit list/tuple required")
    root = _path(input_root)
    # These exclusions are trusted caller authority, never derived from metadata.
    _outside(root, [_path(source_root), _path(store._artifacts._root),
                    *(_path(path) for path in backup_roots), *(_path(path) for path in control_roots)])
    for item, entry in zip(selected, entries):
        _local_provenance(SourceProvenance.from_dict(entry["provenance"]), str(root / item["input_path"]))
    with _operation("prepare source capture", root), ExitStack() as stack:
        directories = _Directories(stack)
        area = directories.traverse(root)
        _directory_safety(directories, root)
        parents, captured, total = {"": area}, [], 0
        identities = set()
        for item in selected:
            relative, target = "", area
            parts = item["input_path"].split("/")
            for part in parts[:-1]:
                relative = f"{relative}/{part}" if relative else part
                if relative not in parents:
                    parents[relative] = directories.open(part, target, path=root / relative)
                target = parents[relative]
            _directory_safety(directories, root)
            path = root / item["input_path"]
            fd, original = stack.enter_context(_capture_leaf(target, parts[-1], path, _fault))
            identity = (original.st_dev, original.st_ino)
            if identity in identities:
                raise CheckoutLayoutError(f"selected file {path}: duplicate physical selection")
            identities.add(identity)
            captured.append((target, parts[-1], fd, original, path))
            if original.st_size > max_file_bytes:
                raise DomainValidationError(f"selected file {path}: exceeds max_file_bytes")
            total += original.st_size
            if total > max_total_bytes:
                raise DomainValidationError("selected files: exceeds max_total_bytes")
        # All selected leaves are held and size-checked before the first allocation.
        for entry, binding in zip(entries, captured):
            parent, name, fd, original, path = binding
            _directory_safety(directories, root)
            _unchanged(*binding)
            content = _read_bytes(fd, original.st_size, path, _fault)
            _unchanged(*binding)
            _directory_safety(directories, root)
            entry["artifact"] = store.put_artifact(content).to_dict()
            del content
            entry["original_mode"] = stat.S_IMODE(original.st_mode)
            _fault("file_captured")
        source = Source.from_dict(dict(format="research_pipeline.source_content", version=1, kind="source", **data))
        submission = store._check_prepared_typed(Submission(submission_id, submission_provenance,
            [encode_envelope(record_id, revision, source, record_provenance)], {record_id: expected_head}))
        mapping = dict(input_root=str(root), files=[dict(input_path=item["input_path"],
            supplied_path=str(root / item["input_path"]), **{key: entry[key] for key in (
                "artifact_id", "path", "artifact", "original_mode", "provenance")})
            for item, entry in zip(selected, entries)])
        result = PreparedSourceCapture(submission, mapping)
        _fault("before_return")
        # Keep every earlier inode alive until this whole-operation gate. Same-byte
        # substitution and changes during later captures must not hide behind hashes.
        for binding in captured:
            _unchanged(*binding)
        _directory_safety(directories, root)
        return result
