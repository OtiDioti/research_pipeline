"""Bounded draft previews and pure frozen proposals; explicit typed submission commits."""

from contextlib import ExitStack
from dataclasses import dataclass
import json
import os
import stat

from research_pipeline.assessment import _copy
from research_pipeline.checkout import (
    CheckoutInfo, CheckoutIntegrityError, CheckoutLayoutError, _CHUNK, _CONTROL,
    _capture_regular, _capture_leaf, _read_bytes,
    _DESCRIPTOR, _Directories, _base, _decode, _encode, _inventory, _leaf, _limit,
    _operation, _outside, _path, _signature, _source_bindings, _stat, _stream,
    _unchanged,
)
from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, RecordReference, Submission,
    _fields, _snapshot, _validate_json_string,
)
from research_pipeline.store import RecordStore
from research_pipeline.work_product import (
    WorkProductFile, WorkProductManifest, _path as _logical_path, _reject_constant,
    _unique_object, _validate_paths, decode_envelope, encode_envelope,
)


_FORMAT = "research_pipeline.work_product_import_submission"
_METADATA = ("product_kind", "title", "purpose", "authors", "task", "branch",
             "context", "run", "linked_claims", "linked_sources", "build_dependencies",
             "entry_file", "limitations")


def _proposal(value):
    """Detach one coherent append request, requiring exact immediate-predecessor CAS."""
    if type(value) is not Submission:
        raise DomainValidationError("proposal: expected Submission")
    try:
        _copy(value.provenance, CreationProvenance, "submission.provenance")
        if type(value.records) not in (tuple, list) or len(value.records) != 1:
            raise DomainValidationError("proposal: requires exactly one work-product envelope")
        decode_envelope(value.records[0])
        result = Submission.from_dict(value.to_dict())
        envelope = result.records[0]
        manifest = decode_envelope(envelope)
        if (manifest.supersedes is None
                or result.expected_heads != {envelope.record_id: envelope.revision - 1}):
            raise DomainValidationError("proposal: requires immediate-predecessor supersession and matching expected head")
        return result
    except (AttributeError, TypeError, KeyError, RecursionError) as error:
        raise DomainValidationError(f"proposal: malformed request: {error}") from error


def dumps_prepared_submission(submission: Submission) -> str:
    """Purely encode a complete detached append proposal, preserving IDs, attribution and order.

    No checkout or store is accessed. Invalid or incoherent requests raise
    DomainValidationError; callers must durably save this value before committing.
    """
    submission = _proposal(submission)
    return _snapshot(dict(format=_FORMAT, version=1, submission=submission.to_dict()), "proposal")


def loads_prepared_submission(data: str | bytes) -> Submission:
    """Purely decode strict UTF-8 proposal JSON with every nested serialized field explicit.

    Reject duplicates, unknown fields/versions, coercion and non-scalar/nonfinite
    values. Loading never regenerates IDs/timestamps or checks artifact availability.
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


@dataclass(frozen=True, init=False)
class PreparedWorkProduct:
    """A frozen proposal and explanatory summary, detached anew on every public access."""

    _submission_json: str
    _summary_json: str

    def __init__(self, submission: Submission, summary: dict):
        """Snapshot validated proposal/summary values without retaining caller-owned nested objects."""
        object.__setattr__(self, "_submission_json", dumps_prepared_submission(submission))
        object.__setattr__(self, "_summary_json", _snapshot(summary, "change summary"))

    @property
    def submission(self) -> Submission:
        """Return a fresh exact Submission for explicit submit_typed or durable serialization."""
        return loads_prepared_submission(self._submission_json)

    @property
    def summary(self) -> dict:
        """Return fresh explanatory JSON data, never commit authority."""
        return json.loads(self._summary_json)


def _fault(boundary):
    """Private deterministic mutation seam preceding real checks, never a public callback."""


def _manifest(metadata, files, supersedes):
    """Use the accepted strict manifest codec and require explicit nested metadata fields."""
    document = dict(format="research_pipeline.work_product_content", version=1,
                    kind="work_product_manifest", **metadata,
                    files=[entry.to_dict() for entry in files], supersedes=supersedes.to_dict())
    result = WorkProductManifest.from_dict(document)
    if _snapshot(document, "proposed manifest") != _snapshot(result.to_dict(), "proposed manifest"):
        raise DomainValidationError("metadata: incomplete or noncanonical nested fields")
    return result


def _file_budget(files, max_files, max_file_bytes, max_total_bytes):
    """Bound a canonical logical inventory before opening any originals; repeated files count."""
    if len(files) > max_files:
        raise DomainValidationError("base files: exceeds max_files")
    if any(entry.artifact.size > max_file_bytes for entry in files):
        raise DomainValidationError("base files: exceeds max_file_bytes")
    if sum(entry.artifact.size for entry in files) > max_total_bytes:
        raise DomainValidationError("base files: exceeds max_total_bytes")


def _controls(control, path):
    """Require only the descriptor, stopping after the first unexpected control entry."""
    found = False
    with os.scandir(control) as entries:
        for entry in entries:
            if entry.name != _DESCRIPTOR or found:
                raise CheckoutLayoutError(f"controls {path}: incomplete or unexpected entries")
            found = True
    if not found:
        raise CheckoutLayoutError(f"controls {path}: missing descriptor")


def _entries(descriptor, path, remaining):
    """Bound iterator enumeration and lstat entries without opening or following their contents."""
    before = os.fstat(descriptor)
    result = {}
    with os.scandir(descriptor) as entries:
        for entry in entries:
            if len(result) >= remaining:
                raise CheckoutLayoutError(f"inventory {path}: exceeds max_inventory_entries")
            result[entry.name] = _signature(_stat(descriptor, entry.name))
    if _signature(os.fstat(descriptor)) != _signature(before):
        raise CheckoutIntegrityError(f"inventory {path}: directory changed during enumeration")
    return before, result


def _unselected(product_dirs, selected, maximum, root):
    """Snapshot visited directories and report unselected entries, leaving other subtrees opaque."""
    observed, report, count = {}, [], 0
    for relative, descriptor in product_dirs.items():
        before, entries = _entries(descriptor, root / relative, maximum - count)
        count += len(entries)
        if not relative:
            names = set(entries)
            if (names & {".backup-incomplete", ".restore-incomplete", "metadata.sqlite3", "snapshot.sqlite3"}
                    or {"objects", ".staging"} <= names):
                raise CheckoutLayoutError(f"checkout {root}: recognizable storage layout")
        observed[relative] = (before, entries)
        for name, signature in entries.items():
            path = f"{relative}/{name}" if relative else name
            if (not relative and name == _CONTROL) or path in selected or path in product_dirs:
                continue
            mode = signature[4]
            kind = ("file" if stat.S_ISREG(mode) else "directory" if stat.S_ISDIR(mode)
                    else "symlink" if stat.S_ISLNK(mode) else "other")
            escaped = any(0xD800 <= ord(char) <= 0xDFFF for char in path)
            display = json.dumps(path, ensure_ascii=True)[1:-1] if escaped else path
            report.append(dict(path=display, path_escaped=escaped, kind=kind, opaque=kind == "directory"))
    return observed, sorted(report, key=lambda entry: (entry["path"], entry["path_escaped"]))


def _check_inventory(product_dirs, observed, maximum, root):
    """Re-enumerate bounded membership/signatures so a changing report cannot appear complete."""
    count = 0
    for relative, descriptor in product_dirs.items():
        before, entries = _entries(descriptor, root / relative, maximum - count)
        count += len(entries)
        original, expected = observed[relative]
        if _signature(before) != _signature(original) or entries != expected:
            raise CheckoutIntegrityError(f"inventory {root / relative}: changed during preparation")


def _summary(info, old, new, submission, base_submission_provenance, unselected):
    """Compare exact ordered membership, byte references, metadata and explicit attribution."""
    old_files = {entry.path: entry.artifact.to_dict() for entry in old.files}
    new_files = {entry.path: entry.artifact.to_dict() for entry in new.files}
    comparisons = []
    for path in dict.fromkeys([*old_files, *new_files]):
        before, after = old_files.get(path), new_files.get(path)
        status = ("added" if before is None else "removed" if after is None
                  else "unchanged" if before == after else "changed")
        comparisons.append(dict(path=path, status=status, old=before, new=after))
    old_data, new_data = old.to_dict(), new.to_dict()
    differences = {name: dict(before=old_data[name], after=new_data[name]) for name in _METADATA
                   if _snapshot({"value": old_data[name]}, name) != _snapshot({"value": new_data[name]}, name)}
    provenance = {}
    for name, before, after in (
            ("record", info.envelope.provenance.to_dict(), submission.records[0].provenance.to_dict()),
            ("submission", base_submission_provenance.to_dict(), submission.provenance.to_dict())):
        if _snapshot(before, name) != _snapshot(after, name):
            provenance[name] = dict(before=before, after=after)
    return dict(base=info.base.to_dict(), proposed_revision=submission.records[0].revision,
                paths=comparisons, old_files=list(old_files), new_files=list(new_files),
                metadata_changes=differences, provenance_changes=provenance,
                structural_changes=dict(revision=dict(before=info.base.revision, after=submission.records[0].revision),
                                        supersedes=dict(before=old_data["supersedes"], after=new_data["supersedes"])),
                unselected_material=unselected)


def prepare_work_product_import(
        source: RecordStore, base: RecordReference, checkout_directory, *, expected_head: int,
        metadata: dict, selected_paths, submission_id: str,
        record_provenance: CreationProvenance, submission_provenance: CreationProvenance,
        source_root, protected_roots, max_file_bytes: int, max_total_bytes: int,
        max_files: int, max_descriptor_bytes: int, max_inventory_entries: int) -> PreparedWorkProduct:
    """Capture explicit draft files and preview one exact next-revision typed submission.

    The complete metadata dictionary and ordered nonempty path list are caller
    declarations. Trusted exclusions and finite budgets are mandatory. Validate the
    pinned canonical base and all its direct originals, then pin controls and safely
    capture selected files without altering them. Only immutable artifact publication
    occurs; failures may retain orphan objects. No application metadata is written.

    Read-snapshot admission is advisory: later commit can conflict. Save the returned
    proposal durably, then explicitly call source.submit_typed with that exact request.
    Retrying preparation is not original-ID reconciliation. Binding checks detect
    observed changes but cannot sandbox arbitrary same-owner hostile mutation.
    """
    for name, value, minimum in (("expected_head", expected_head, 1),
                                 ("max_file_bytes", max_file_bytes, 0),
                                 ("max_total_bytes", max_total_bytes, 0),
                                 ("max_files", max_files, 1),
                                 ("max_descriptor_bytes", max_descriptor_bytes, 1),
                                 ("max_inventory_entries", max_inventory_entries, 1)):
        _limit(value, name, minimum)
    base = _base(base)
    if expected_head != base.revision:
        raise DomainValidationError("expected_head: must equal the exact base revision; reconcile against a new base explicitly")
    record_provenance = _copy(record_provenance, CreationProvenance, "record_provenance")
    submission_provenance = _copy(submission_provenance, CreationProvenance, "submission_provenance")
    metadata = json.loads(_snapshot(metadata, "metadata"))
    _fields(metadata, set(_METADATA), set(), "metadata")
    if type(selected_paths) not in (list, tuple) or not selected_paths:
        raise DomainValidationError("selected_paths: explicit nonempty list or tuple required")
    selected = tuple(selected_paths)
    if len(selected) > max_files:
        raise DomainValidationError("selected_paths: exceeds max_files")
    _validate_paths(selected)
    if any(_logical_path(path, "selected path")[0] == _CONTROL for path in selected):
        raise DomainValidationError("selected_paths: reserved checkout control namespace")
    if type(protected_roots) not in (list, tuple):
        raise DomainValidationError("protected_roots: explicit list or tuple required")
    root, runtime = _path(checkout_directory), _path(source._artifacts._root)
    _outside(root, [_path(source_root), runtime, *(_path(path) for path in protected_roots)])
    with source._transaction() as connection:
        info = CheckoutInfo(base, source._metadata_envelope(connection, base.record_id, base.revision))
        row = connection.execute("SELECT submission_id FROM revisions WHERE record_id=? AND revision=?",
                                 (base.record_id, base.revision)).fetchone()
        base_provenance = source._receipt(connection, row[0]).provenance
    old = _inventory(info)
    _file_budget(old.files, max_files, max_file_bytes, max_total_bytes)
    canonical = _encode(info)
    if len(canonical) > max_descriptor_bytes:
        raise DomainValidationError("descriptor: exceeds max_descriptor_bytes")
    supersedes = RecordReference(base.record_id, base.revision, "supersedes", "work_product_manifest")
    # Validate all metadata and attribution before opening draft content. Placeholder
    # references only exercise the existing codec; they are never published/returned.
    template = _manifest(metadata, [WorkProductFile(path, old.files[0].artifact) for path in selected], supersedes)
    _proposal(Submission(submission_id, submission_provenance,
                         [encode_envelope(base.record_id, base.revision + 1, template, record_provenance)],
                         {base.record_id: expected_head}))
    with _operation("prepare import", root), ExitStack() as stack:
        directories = _Directories(stack)
        parent = directories.traverse(root.parent, exclude_layouts=True)
        area = directories.open(root.name, parent, private=True, exact=True, path=root)
        control = directories.open(_CONTROL, area, private=True, exact=True, path=root / _CONTROL)
        _controls(control, root / _CONTROL)
        control_original = os.fstat(control)
        descriptor_path = root / _CONTROL / _DESCRIPTOR
        descriptor, descriptor_original = stack.enter_context(_leaf(control, _DESCRIPTOR, descriptor_path, mode=0o400))
        if descriptor_original.st_size > max_descriptor_bytes:
            raise CheckoutIntegrityError("descriptor: exceeds max_descriptor_bytes")
        observed_info = _decode(_read_bytes(descriptor, descriptor_original.st_size, descriptor_path, _fault))
        if _encode(observed_info) != canonical:
            raise CheckoutIntegrityError("descriptor: does not equal caller-pinned canonical base/envelope")
        source_area = directories.traverse(runtime, private=True)
        objects = directories.open("objects", source_area, private=True, path=runtime / "objects")
        staging = directories.open(".staging", source_area, private=True, path=runtime / ".staging")
        if os.fstat(objects).st_dev != os.fstat(staging).st_dev:
            raise CheckoutLayoutError(f"source layout {runtime}: objects/staging filesystems differ")
        originals = {}
        for entry in old.files:
            if entry.artifact.digest in originals:
                continue
            path = runtime / "objects" / entry.artifact.digest
            with _leaf(objects, entry.artifact.digest, path, mode=None) as (fd, original):
                _stream(fd, entry.artifact, path)
                originals[entry.artifact.digest] = original
        product_dirs = {"": area}
        for path in selected:
            relative, target = "", area
            for part in path.split("/")[:-1]:
                relative = f"{relative}/{part}" if relative else part
                if relative not in product_dirs:
                    product_dirs[relative] = directories.open(part, target, private=True, exact=True, path=root / relative)
                target = product_dirs[relative]
        observed, report = _unselected(product_dirs, set(selected), max_inventory_entries, root)
        captured, files, total = [], [], 0
        for path in selected:
            relative, _, name = path.rpartition("/")
            target = product_dirs[relative]
            fd, original = stack.enter_context(_capture_leaf(target, name, root / path, _fault))
            if original.st_size > max_file_bytes:
                raise DomainValidationError(f"selected file {path}: exceeds max_file_bytes")
            total += original.st_size
            if total > max_total_bytes:
                raise DomainValidationError("selected files: exceeds max_total_bytes")
            data = _read_bytes(fd, original.st_size, root / path, _fault)
            _unchanged(target, name, fd, original, root / path)
            artifact = source.put_artifact(data)
            del data
            files.append(WorkProductFile(path, artifact))
            captured.append((target, name, fd, original, root / path))
            _fault("file_captured")
        new = _manifest(metadata, files, supersedes)
        envelope = encode_envelope(base.record_id, base.revision + 1, new, record_provenance)
        submission = source._check_prepared_typed(Submission(
            submission_id, submission_provenance, [envelope], {base.record_id: expected_head}))
        result = PreparedWorkProduct(submission, _summary(info, old, new, submission, base_provenance, report))
        _fault("before_return")
        # Held leaf descriptors survive until this final gate, so later captures
        # cannot conceal changes to earlier files, even replacement with equal bytes.
        directories.check()
        _source_bindings(objects, runtime, originals)
        _controls(control, root / _CONTROL)
        if _signature(os.fstat(control)) != _signature(control_original):
            raise CheckoutIntegrityError("controls: directory changed during preparation")
        _unchanged(control, _DESCRIPTOR, descriptor, descriptor_original, descriptor_path)
        for binding in captured:
            _unchanged(*binding)
        _check_inventory(product_dirs, observed, max_inventory_entries, root)
        directories.check()
        return result
