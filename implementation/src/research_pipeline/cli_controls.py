"""Strict bounded local CLI controls; none of these values conveys scientific authority."""

from contextlib import ExitStack
import json
import math
from pathlib import Path
import stat

from research_pipeline import checkout
from research_pipeline.domain import DomainValidationError, _fields, _validate_json
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
