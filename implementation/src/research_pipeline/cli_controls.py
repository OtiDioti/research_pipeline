"""Strict bounded local CLI controls; none of these values conveys scientific authority."""

from contextlib import ExitStack
import json
import math
from pathlib import Path
import stat

from research_pipeline import checkout
from research_pipeline.domain import DomainValidationError, _fields, _validate_json
from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordReference, Submission, _snapshot
from research_pipeline.snapshot import _check_json_depth, SnapshotLimitError
from research_pipeline.work_product import _unique_object, _reject_constant


class CliError(Exception):
    """Carry a fixed CLI status/code and safe explanation, without exposing input contents."""

    def __init__(self, status, code, message):
        """Retain an already classified failure for the command's single diagnostic boundary."""
        super().__init__(message)
        self.status, self.code = status, code


def _fault(boundary):
    """Private deterministic control-read test seam; never selected by CLI or environment."""


def _number(token, *, floating=False):
    """Bound numeric token work before conversion and reject nonfinite floating results."""
    if len(token) > 128:
        raise DomainValidationError("JSON numeric token exceeds 128 characters")
    value = float(token) if floating else int(token)
    if floating and not math.isfinite(value):
        raise DomainValidationError("nonfinite JSON number")
    return value


def _float(token):
    """Apply the same finite token budget to JSON floats as to integers."""
    return _number(token, floating=True)


def strict_json(data):
    """Decode bounded UTF-8 controls with depth/scalar checks, accepting whitespace and key order."""
    try:
        text = data.decode("utf-8", errors="strict")
        _check_json_depth(text, 64)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
                           parse_int=_number, parse_float=_float)
        _validate_json(value, "control", set())
        return value
    except (ValueError, TypeError, RecursionError, OverflowError) as error:
        raise CliError(5, "invalid_input", "Invalid structured control.") from error


def path_value(value, *, absolute=False):
    """Validate a supplied path's scalar/byte/traversal contract and normalize it without symlink resolution."""
    if type(value) is not str or not value:
        raise DomainValidationError("path requires a nonempty string")
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeError as error:
        raise DomainValidationError("path requires Unicode scalar values") from error
    if size > 4096:
        raise SnapshotLimitError("path exceeds 4096 UTF-8 bytes")
    if absolute and not Path(value).is_absolute():
        raise DomainValidationError("configuration path must be absolute")
    path = checkout._path(value)
    if len(str(path).encode("utf-8")) > 4096:
        raise SnapshotLimitError("normalized path exceeds 4096 UTF-8 bytes")
    return path


def source_root():
    """Derive the entire executing software checkout from the resolved source-local module layout."""
    module = Path(__file__).resolve(strict=True)
    package, src, implementation = module.parent, module.parent.parent, module.parent.parent.parent
    if (package.name != "research_pipeline" or src.name != "src"
            or implementation.name != "implementation"
            or not (package / "__main__.py").is_file()
            or not (package / "checkout.py").is_file()):
        raise CliError(5, "unsafe_layout", "Cannot establish the executing source checkout.")
    return implementation.parent


def read_control(parent, name, path, maximum, *, modes):
    """Consume a size-bounded, checked regular leaf while retaining its original inode/signature.

    Type, ownership, single-link and mode checks precede the nonblocking no-follow
    open. The final EOF probe and binding checks detect observed growth/replacement;
    close errors propagate, so closed input is a prerequisite to acknowledgment.
    """
    before = checkout._stat(parent, name)
    mode = stat.S_IMODE(before.st_mode)
    if mode not in modes:
        raise checkout.CheckoutLayoutError("control requires a private permitted mode")
    checkout._regular(before, path, mode)
    if before.st_size > maximum:
        raise SnapshotLimitError("control byte limit exceeded")
    _fault("before_control_open")
    with checkout._leaf(parent, name, path, mode=mode, expected=before) as (fd, info):
        data = checkout._read_bytes(fd, info.st_size, path, _fault)
        _fault("after_control_read")
    return data


def read_config(path, maximum):
    """Read a stable owned private config and return its absolute runtime and explicit exclusions."""
    try:
        with ExitStack() as stack:
            directories = checkout._Directories(stack)
            parent = directories.traverse(path.parent, private=True, exact=True)
            data = read_control(parent, path.name, path, maximum, modes=(0o600, 0o400))
            directories.check()
    except Exception as error:
        if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
            raise CliError(5, "invalid_input", "Configuration file or parent is missing.") from error
        raise
    value = strict_json(data)
    _fields(value, {"format", "version", "store", "protected_roots"}, set(), "CLI configuration")
    if (value["format"] != "research_pipeline.cli_config"
            or type(value["version"]) is not int or value["version"] != 1):
        raise DomainValidationError("unsupported CLI configuration format/version")
    roots = value["protected_roots"]
    if type(roots) is not list:
        raise DomainValidationError("protected_roots must be an explicit array")
    if len(roots) > 64:
        raise SnapshotLimitError("at most 64 protected roots")
    runtime = path_value(value["store"], absolute=True)
    roots = tuple(path_value(root, absolute=True) for root in roots)
    if len(set(roots)) != len(roots):
        raise DomainValidationError("duplicate normalized protected roots")
    return runtime, roots


def causes(error):
    """Walk explicit exception causes so translated layout errors retain their actual I/O meaning."""
    while error is not None:
        yield error
        error = error.__cause__


def complete_codec(value, codec):
    """Decode a complete nested declaration, refusing defaults and coercive normalized equivalents."""
    result = codec.from_dict(value)
    if _snapshot(value, "declaration") != _snapshot(result.to_dict(), "declaration"):
        raise DomainValidationError("incomplete or noncanonical nested declaration")
    return result


def read_request(path, maximum, max_files):
    """Validate an authored preparation request before any draft read or object publication.

    Require private stable controls and complete nested values. Inert artifact
    placeholders exercise existing manifest/proposal codecs and never escape this
    structural gate. The returned dictionary contains detached API arguments.
    """
    from research_pipeline import work_product_import as importer
    from research_pipeline.work_product import WorkProductFile, _path, _validate_paths, encode_envelope

    with ExitStack() as stack:
        directories = checkout._Directories(stack)
        parent = directories.traverse(path.parent, private=True, exact=True)
        value = strict_json(read_control(parent, path.name, path, maximum, modes=(0o600, 0o400)))
        directories.check()
    _fields(value, {"format", "version", "base", "expected_head", "metadata", "selected_paths",
                    "submission_id", "record_provenance", "submission_provenance"}, set(), "preparation")
    if (value["format"] != "research_pipeline.cli_work_product_preparation"
            or type(value["version"]) is not int or value["version"] != 1):
        raise DomainValidationError("unsupported preparation format/version")
    base = checkout._base(complete_codec(value["base"], RecordReference))
    if (type(value["expected_head"]) is not int or value["expected_head"] != base.revision
            or base.revision == 2**63 - 1):
        raise DomainValidationError("expected_head must equal an incrementable exact base")
    record = complete_codec(value["record_provenance"], CreationProvenance)
    submission = complete_codec(value["submission_provenance"], CreationProvenance)
    paths = value["selected_paths"]
    if type(paths) is not list or not paths:
        raise DomainValidationError("selected_paths requires a nonempty ordered array")
    if len(paths) > max_files:
        raise SnapshotLimitError("selected path count exceeded")
    _validate_paths(paths)
    if any(_path(path, "selected path")[0] in (checkout._CONTROL, ".work-product-proposal") for path in paths):
        raise DomainValidationError("reserved control namespace")
    _fields(value["metadata"], set(importer._METADATA), set(), "metadata")
    supersedes = RecordReference(base.record_id, base.revision, "supersedes", "work_product_manifest")
    template = importer._manifest(value["metadata"],
                                  [WorkProductFile(path, ArtifactReference("0" * 64, 0)) for path in paths],
                                  supersedes)
    importer._proposal(Submission(value["submission_id"], submission,
                       [encode_envelope(base.record_id, base.revision + 1, template, record)],
                       {base.record_id: value["expected_head"]}))
    return dict(base=base, expected_head=value["expected_head"], metadata=value["metadata"],
                selected_paths=paths, submission_id=value["submission_id"],
                record_provenance=record, submission_provenance=submission)


# These ceilings apply independently at every nested occurrence; retained plans
# never choose the caller's allowances.
_READABLE_CEILINGS = dict(max_roots=1024, max_records=65536, max_references=65536,
    max_artifacts=65536, max_files=65536, max_entries=65536, max_directories=65536,
    max_diagnostics=65536, max_record_bytes=16777216, max_metadata_bytes=268435456,
    max_file_bytes=1073741824, max_total_bytes=4294967296, max_depth=64,
    max_open_descriptors=4096)
_READABLE_SCALARS = frozenset(("max_entries", "max_files", "max_directories", "max_depth",
    "max_file_bytes", "max_total_bytes", "max_metadata_bytes", "max_diagnostics", "max_open_descriptors"))


class _ControlDirectories(checkout._Directories):
    """Retain control ancestry so disappearance of an acquired binding is mutation."""

    def check(self):
        """Verify held bindings, translating missing observed ancestors into integrity failure."""
        try:
            super().check()
        except checkout.CheckoutIntegrityError:
            raise
        except Exception as error:
            # Inherited open() also checks all earlier pins during traversal.
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                raise checkout.CheckoutIntegrityError("observed control ancestor disappeared") from error
            raise


def read_observed_control(parent, name, path, maximum, *, modes, before=None):
    """Read a new CLI control and return bytes/stat, distinguishing initial absence from later mutation.

    The established reader still owns bounded reads and checked closes. This outer
    observation makes disappearance between its own probes an integrity failure.
    Callers may supply the initial stat to separate missing-input classification
    from subsequent reads and checked closes.
    """
    if before is None:
        before = checkout._stat(parent, name)
    try:
        data = read_control(parent, name, path, maximum, modes=modes)
    finally:
        try:
            current = checkout._stat(parent, name)
        except FileNotFoundError as error:
            raise checkout.CheckoutIntegrityError("observed control disappeared") from error
        if checkout._signature(current) != checkout._signature(before):
            raise checkout.CheckoutIntegrityError("observed control changed")
    return data, before


def read_authored(path, maximum):
    """Read one private control; only initial acquisition/observation can mean missing input."""
    with ExitStack() as stack:
        directories = _ControlDirectories(stack)
        try:
            parent = directories.traverse(path.parent, private=True, exact=True)
            before = checkout._stat(parent, path.name)
        except checkout.CheckoutIntegrityError:
            raise
        except Exception as error:
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                # An absent next component must not hide loss of an earlier pin.
                directories.check()
                raise CliError(3, "missing", "Explicit control file or parent is missing.") from error
            raise
        data, _ = read_observed_control(parent, path.name, path, maximum, modes=(0o400, 0o600), before=before)
        directories.check()
    return strict_json(data)


def read_selection(path, maximum):
    """Decode complete ordered selectors; only explicit null requests the current head."""
    from research_pipeline.snapshot import RootSelector, SnapshotSelection
    value = read_authored(path, maximum)
    _fields(value, {"format", "version", "project", "roots"}, set(), "snapshot selection")
    _readable_version(value, "cli_snapshot_selection")
    if type(value["roots"]) is not list:
        raise DomainValidationError("roots requires an ordered array")
    selectors = []
    for row in (value["project"], *value["roots"]):
        _fields(row, {"record_id", "revision"}, set(), "selector")
        revision = row["revision"]
        if revision is not None:
            if type(revision) is not int:
                raise DomainValidationError("revision requires an ordinary integer or null")
            if not 1 <= revision <= 9223372036854775807:
                raise SnapshotLimitError("revision outside permitted range")
        selectors.append(RootSelector(**row))
    return SnapshotSelection(selectors[0], tuple(selectors[1:]))


def _readable_version(value, name):
    """Require the authored version-1 format without bool/integer equivalence."""
    if (value["format"] != "research_pipeline." + name
            or type(value["version"]) is not int or value["version"] != 1):
        raise DomainValidationError("unsupported readable control format/version")


def _readable_integers(value, names, zero=()):
    """Validate complete scalar allowances, separating malformed types from exceeded ranges."""
    result = {}
    for name in names:
        number = value[name]
        if type(number) is not int:
            raise DomainValidationError(name + ": ordinary integer required")
        if not (0 if name in zero else 1) <= number <= _READABLE_CEILINGS[name]:
            raise SnapshotLimitError(name + ": outside CLI range")
        result[name] = number
    return result


def _snapshot_limits(value):
    """Construct a complete independently bounded SnapshotLimits, with no nested defaults."""
    from dataclasses import fields
    from research_pipeline.snapshot import SnapshotLimits
    names = {field.name for field in fields(SnapshotLimits)}
    _fields(value, names, set(), "snapshot limits")
    return SnapshotLimits(**_readable_integers(value, names,
                          ("max_references", "max_artifacts", "max_total_bytes")))


def _capture_limits(value):
    """Construct complete capture allowances, independently decoding historical plan limits."""
    from research_pipeline.view_capture import CaptureLimits
    _fields(value, _READABLE_SCALARS | {"plan_limits"}, set(), "capture limits")
    return CaptureLimits(plan_limits=_snapshot_limits(value["plan_limits"]),
        **_readable_integers(value, _READABLE_SCALARS, ("max_file_bytes", "max_total_bytes")))


def read_readable_limits(path, maximum, command):
    """Decode the exact command-specific limit document into existing independent domain limits."""
    from research_pipeline.view_refresh import RefreshLimits
    groups = {
        "generate-readable-view": {"snapshot_limits", "view_limits"},
        "refresh-readable-view": {"snapshot_limits", "refresh_limits"},
        "inspect-readable-view": {"view_limits"},
        "inspect-readable-refresh": {"refresh_limits"},
    }[command]
    value = read_authored(path, maximum)
    _fields(value, {"format", "version", "command"} | groups, set(), "readable limits")
    _readable_version(value, "cli_readable_limits")
    if value["command"] != command:
        raise DomainValidationError("limits command mismatch")
    result = {}
    if "snapshot_limits" in groups:
        result["snapshot_limits"] = _snapshot_limits(value["snapshot_limits"])
    if "view_limits" in groups:
        view = value["view_limits"]
        names = {"max_entries", "max_depth", "max_open_descriptors"}
        _fields(view, names | {"plan_limits"}, set(), "view limits")
        result["view_limits"] = dict(plan_limits=_snapshot_limits(view["plan_limits"]),
                                    **_readable_integers(view, names))
    if "refresh_limits" in groups:
        refresh = value["refresh_limits"]
        _fields(refresh, _READABLE_SCALARS | {"capture_limits", "successor_limits"}, set(), "refresh limits")
        result["refresh_limits"] = RefreshLimits(
            capture_limits=_capture_limits(refresh["capture_limits"]),
            successor_limits=_snapshot_limits(refresh["successor_limits"]),
            **_readable_integers(refresh, _READABLE_SCALARS, ("max_file_bytes", "max_total_bytes")))
    return result
