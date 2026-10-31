"""Bounded, inert local copies with durable publication and untrusted base descriptors."""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat

from research_pipeline.artifacts import ArtifactError, _regular_object
from research_pipeline.assessment import _copy
from research_pipeline.domain import (
    DomainValidationError, RecordEnvelope, RecordReference, _fields, _snapshot,
)
from research_pipeline.store import RecordStore
from research_pipeline.work_product import (
    _path as _logical_path, _unique_object, _reject_constant, decode_envelope,
)


_CONTROL = ".work-product"
_DESCRIPTOR = "checkout.json"
_MARKER = "incomplete"
_FORMAT = "research_pipeline.work_product_checkout"
_CHUNK = 64 * 1024


class CheckoutError(Exception):
    """Base for unsafe layouts, integrity failures and retained-output I/O failures."""


class CheckoutLayoutError(CheckoutError):
    """A path or control layout is unsafe, incomplete, missing or already occupied."""


class CheckoutIntegrityError(CheckoutError):
    """Selected metadata, bytes or observed filesystem bindings are inconsistent."""


class CheckoutOperationalError(CheckoutError):
    """An operation failed; output is retained and publication may be uncertain."""


def _base(value):
    """Reconstruct a caller's exact checkout reference, rejecting forged frozen fields."""
    value = _copy(value, RecordReference, "base")
    if value.relationship != "checkout_base" or value.target_kind != "work_product_manifest":
        raise DomainValidationError("base: requires checkout_base relationship and work_product_manifest target_kind")
    return value


@dataclass(frozen=True)
class CheckoutInfo:
    """Detached original base and envelope; local inspection does not authenticate either."""

    base: RecordReference
    envelope: RecordEnvelope

    def __post_init__(self):
        """Detach and validate exact envelope coherence; retain no second file inventory."""
        base = _base(self.base)
        decode_envelope(self.envelope)
        envelope = _copy(self.envelope, RecordEnvelope, "envelope")
        if (base.record_id, base.revision) != (envelope.record_id, envelope.revision):
            raise DomainValidationError("base: disagrees with envelope identity/revision")
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "envelope", envelope)


def _fault(boundary):
    """Private failure/termination seam after real work, never a public callback."""


def _limit(value, name, minimum):
    """Require a finite ordinary integer budget, with the specified inclusive minimum."""
    if type(value) is not int or value < minimum:
        raise DomainValidationError(f"{name}: expected ordinary integer >= {minimum}")


def _encode(info):
    """Serialize only the exact original base/envelope in compact sorted ASCII JSON."""
    return _snapshot(dict(format=_FORMAT, version=1, base=info.base.to_dict(),
                          envelope=info.envelope.to_dict()), "checkout descriptor").encode("ascii")


def _decode(data):
    """Decode strict UTF-8 JSON and require complete nested serialized field sets/types."""
    try:
        value = json.loads(data.decode("utf-8", errors="strict"),
                           object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        canonical = _snapshot(value, "checkout descriptor")
        _fields(value, {"format", "version", "base", "envelope"}, set(), "checkout descriptor")
        if value["format"] != _FORMAT or type(value["version"]) is not int or value["version"] != 1:
            raise DomainValidationError("checkout descriptor: unsupported format/version")
        info = CheckoutInfo(RecordReference.from_dict(value["base"]),
                            RecordEnvelope.from_dict(value["envelope"]))
        # Comparing canonical JSON, not Python equality, preserves bool/int and
        # omitted/default distinctions throughout references and provenance.
        if canonical.encode("ascii") != _encode(info):
            raise DomainValidationError("checkout descriptor: incomplete or noncanonical nested fields")
        _inventory(info)
        return info
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as error:
        raise CheckoutIntegrityError(f"decode {_CONTROL}/{_DESCRIPTOR}: {error}") from error


def _inventory(info):
    """Validate the manifest and checkout-only reserved namespace without changing wire rules."""
    manifest = decode_envelope(info.envelope)
    for entry in manifest.files:
        if _logical_path(entry.path, "file path")[0] == _CONTROL:
            raise DomainValidationError(f"file path {entry.path}: reserved checkout control component")
    return manifest


def _path(value):
    """Anchor explicit paths at cwd, rejecting traversal and normalizing POSIX // lexically."""
    try:
        path = Path(value)
    except (TypeError, ValueError) as error:
        raise DomainValidationError(f"path {value!r}: expected a filesystem path") from error
    if "\0" in str(path):
        raise DomainValidationError(f"path {path!r}: NUL is forbidden")
    if ".." in path.parts:
        raise CheckoutLayoutError(f"path {path}: parent traversal is forbidden")
    path = path if path.is_absolute() else Path.cwd() / path
    return Path("/").joinpath(*path.parts[1:]) if path.anchor == "//" else path


def _outside(destination, roots):
    """Reject component containment in either direction before reserving any destination."""
    for root in roots:
        if destination == root or root in destination.parents or destination in root.parents:
            raise CheckoutLayoutError(f"destination {destination}: overlaps excluded root {root}")


def _identity(info):
    """Return the filesystem identity shared by lstat and held descriptors."""
    return info.st_dev, info.st_ino


def _signature(info):
    """Capture relevant file changes without treating read-induced atime changes as mutation."""
    return (_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_mode, info.st_uid, info.st_gid, info.st_nlink)


@contextmanager
def _operation(operation, path):
    """Attach the affected operation/path to filesystem and artifact failures with causes."""
    try:
        yield
    except CheckoutError:
        raise
    except ArtifactError as error:
        raise CheckoutIntegrityError(f"{operation} {path}: {error}") from error
    except OSError as error:
        raise CheckoutOperationalError(f"{operation} {path}: {error}") from error


def _stat(parent, name):
    """Read a parent-relative entry without following even a dangling symbolic link."""
    return os.stat(name, dir_fd=parent, follow_symlinks=False)


def _private_directory(info, path, exact):
    """Require owned private directory permissions, with exact 0700 for checkout directories."""
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or (exact and stat.S_IMODE(info.st_mode) != 0o700)):
        raise CheckoutLayoutError(f"directory {path}: requires owned private {'0700 ' if exact else ''}directory")


class _Directories:
    """Operation-scoped held directories and their no-follow parent-relative bindings."""

    def __init__(self, stack):
        """Use the caller's ExitStack to close every opened descriptor on all outcomes."""
        self.stack = stack
        self.bindings = []

    def open(self, name, parent=None, *, private=False, exact=False, path=None):
        """Open and compare lstat/fstat identities, retaining binding and ownership requirements."""
        path = str(path if path is not None else name)
        with _operation("open directory", path):
            before = _stat(parent, name)
            if not stat.S_ISDIR(before.st_mode):
                raise CheckoutLayoutError(f"open directory {path}: symlink or non-directory")
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            self.stack.callback(os.close, descriptor)
            opened = os.fstat(descriptor)
            if _identity(before) != _identity(opened):
                raise CheckoutIntegrityError(f"open directory {path}: entry replaced")
            self.bindings.append((parent, name, descriptor, opened, private, exact, path))
            self.check()
            return descriptor

    def check(self):
        """Revalidate each held directory against its current parent entry and initial identity."""
        for parent, name, descriptor, original, private, exact, path in self.bindings:
            with _operation("check directory binding", path):
                current, opened = _stat(parent, name), os.fstat(descriptor)
                if (not stat.S_ISDIR(current.st_mode) or not stat.S_ISDIR(opened.st_mode)
                        or _identity(current) != _identity(original)
                        or _identity(opened) != _identity(original)):
                    raise CheckoutIntegrityError(f"check directory binding {path}: replaced or changed type")
                if private:
                    _private_directory(current, path, exact)
                    _private_directory(opened, path, exact)

    def traverse(self, path, *, exclude_layouts=False, private=False, exact=False):
        """Hold the whole ancestor chain, refusing symlinks and optionally recognizable storage."""
        descriptor = self.open(path.anchor)
        current = Path(path.anchor)
        if exclude_layouts:
            _not_storage(descriptor, current)
        for part in path.parts[1:]:
            current = current / part
            leaf = current == path
            descriptor = self.open(part, descriptor, private=private and leaf,
                                   exact=exact and leaf, path=current)
            if exclude_layouts:
                _not_storage(descriptor, current)
        return descriptor

    def create(self, name, parent, path):
        """Exclusively create a private directory, retaining partial output on any later failure."""
        with _operation("create directory", path):
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
            except FileExistsError as error:
                raise CheckoutLayoutError(f"create directory {path}: destination already exists") from error
            return self.open(name, parent, private=True, exact=True, path=path)


def _not_storage(descriptor, path):
    """Probe fixed storage/control names without enumerating arbitrary ancestor directories."""
    names = set()
    for name in (".backup-incomplete", ".restore-incomplete", _CONTROL,
                 "objects", ".staging", "metadata.sqlite3", "snapshot.sqlite3"):
        try:
            _stat(descriptor, name)
        except FileNotFoundError:
            continue
        names.add(name)
    if (names & {".backup-incomplete", ".restore-incomplete", _CONTROL}
            or {"objects", ".staging"} <= names
            or "metadata.sqlite3" in names or "snapshot.sqlite3" in names):
        raise CheckoutLayoutError(f"destination ancestor {path}: recognizable runtime/backup/checkout layout")


def _regular(info, path, mode):
    """Validate canonical objects or exact private single-link checkout leaves before opening."""
    if mode is None:
        _regular_object(info, str(path))
    elif (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
          or stat.S_IMODE(info.st_mode) != mode or info.st_nlink != 1):
        raise CheckoutLayoutError(f"file {path}: requires owned single-link mode {mode:04o} regular file")


def _unchanged(parent, name, descriptor, original, path):
    """Detect replacement and in-place changes after consuming/writing an opened inode."""
    if (_signature(os.fstat(descriptor)) != _signature(original)
            or _signature(_stat(parent, name)) != _signature(original)):
        raise CheckoutIntegrityError(f"check file {path}: changed or replaced")


@contextmanager
def _leaf(parent, name, path, *, mode, expected=None):
    """Open readable leaves nonblocking/no-follow after type checks; compare bindings on exit."""
    with _operation("read file", path):
        before = _stat(parent, name)
        _regular(before, path, mode)
        if expected is not None and _signature(before) != _signature(expected):
            raise CheckoutIntegrityError(f"read file {path}: changed since creation/capture")
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            opened = os.fstat(descriptor)
            _regular(opened, path, mode)
            if _signature(before) != _signature(opened):
                raise CheckoutIntegrityError(f"read file {path}: replaced during open")
            yield descriptor, opened
            _unchanged(parent, name, descriptor, opened, path)
        finally:
            os.close(descriptor)


def _capture_regular(info, path):
    """Accept owned readable single-link regular draft files, including inert executable bytes; reject unsafe stat results."""
    mode = stat.S_IMODE(info.st_mode)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1
            or not mode & 0o400 or mode & (0o022 | 0o7000)):
        raise CheckoutLayoutError(
            f"capture {path}: requires owned readable single-link regular file without shared write/special bits")


@contextmanager
def _capture_leaf(parent, name, path, fault):
    """Hold a no-follow leaf through final checks; fault is a private caller mutation seam."""
    with _operation("capture file", path):
        before = _stat(parent, name)
        _capture_regular(before, path)
        fault("before_leaf_open")
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            opened = os.fstat(descriptor)
            _capture_regular(opened, path)
            if _signature(before) != _signature(opened):
                raise CheckoutIntegrityError(f"capture {path}: replaced during open")
            yield descriptor, opened
            _unchanged(parent, name, descriptor, opened, path)
        finally:
            os.close(descriptor)


def _read_bytes(descriptor, size, path, fault):
    """Read one size-checked file with bounded chunks/EOF probe and a private fault seam."""
    remaining, chunks = size, []
    while remaining:
        data = os.read(descriptor, min(remaining, _CHUNK))
        if not data:
            raise CheckoutIntegrityError(f"capture {path}: early EOF")
        chunks.append(data)
        remaining -= len(data)
        fault("chunk_read")
    if os.read(descriptor, 1):
        raise CheckoutIntegrityError(f"capture {path}: grew during read")
    return b"".join(chunks)


def _write_all(descriptor, data):
    """Drain a bounded chunk through short writes; zero progress is an operational failure."""
    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("write made no progress")
        remaining = remaining[written:]


def _sync(descriptor, path):
    """Synchronize a known file/directory inode with an affected-path diagnostic on failure."""
    with _operation("synchronize", path):
        os.fsync(descriptor)


@contextmanager
def _new_leaf(parent, name, path, mode):
    """Exclusively create an owned leaf and verify its name still binds the created inode."""
    with _operation("create/write file", path):
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        try:
            created = os.fstat(descriptor)
            if _identity(_stat(parent, name)) != _identity(created):
                raise CheckoutIntegrityError(f"create file {path}: replaced before writing")
            os.fchmod(descriptor, mode)
            _regular(os.fstat(descriptor), path, mode)
            yield descriptor
            final = os.fstat(descriptor)
            _regular(final, path, mode)
            if _identity(final) != _identity(created):
                raise CheckoutIntegrityError(f"write file {path}: replaced inode")
            _unchanged(parent, name, descriptor, final, path)
        finally:
            os.close(descriptor)


def _stream(descriptor, reference, path, target=None):
    """Hash exactly the declared bytes in bounded chunks, with at most one extra EOF byte."""
    if os.fstat(descriptor).st_size != reference.size:
        raise CheckoutIntegrityError(f"capture {path}: declared size mismatch")
    remaining, hasher = reference.size, hashlib.sha256()
    while remaining:
        with _operation("read bytes", path):
            chunk = os.read(descriptor, min(_CHUNK, remaining))
        if not chunk:
            raise CheckoutIntegrityError(f"capture {path}: early EOF")
        remaining -= len(chunk)
        hasher.update(chunk)
        if target is not None:
            _write_all(target, chunk)
    with _operation("probe EOF", path):
        extra = os.read(descriptor, 1)
    if extra:
        raise CheckoutIntegrityError(f"capture {path}: grew beyond declared size")
    if hasher.hexdigest() != reference.digest:
        raise CheckoutIntegrityError(f"capture {path}: SHA-256 mismatch")


def _read_descriptor(control, path, maximum, expected=None):
    """Bound allocation and reads; detect descriptor replacement/growth while reading."""
    with _leaf(control, _DESCRIPTOR, path, mode=0o400, expected=expected) as (descriptor, info):
        if info.st_size > maximum:
            raise CheckoutIntegrityError(f"read descriptor {path}: exceeds max_descriptor_bytes")
        chunks, remaining = [], info.st_size
        while remaining:
            chunk = os.read(descriptor, min(_CHUNK, remaining))
            if not chunk:
                raise CheckoutIntegrityError(f"read descriptor {path}: early EOF")
            remaining -= len(chunk)
            chunks.append(chunk)
        if os.read(descriptor, 1):
            raise CheckoutIntegrityError(f"read descriptor {path}: grew during read")
        return b"".join(chunks)


def _bounded_entries(descriptor, expected_count):
    """Collect at most the expected count plus one entry for exact inventory comparison."""
    names = set()
    with os.scandir(descriptor) as entries:
        for entry in entries:
            names.add(entry.name)
            if len(names) > expected_count:
                break
    return names


def _control_inventory(control, path, incomplete):
    """Require exact control entries; any marker entry makes public inspection unusable."""
    expected = {_DESCRIPTOR, _MARKER} if incomplete else {_DESCRIPTOR}
    names = _bounded_entries(control, len(expected))
    if names != expected:
        raise CheckoutLayoutError(f"inspect controls {path}: incomplete or unexpected/missing entries")


def inspect_checkout(root, *, max_descriptor_bytes: int) -> CheckoutInfo:
    """Read untrusted original-base information from a structurally published local checkout.

    Bound descriptor reads and reject unsafe controls/incomplete output. This is
    read-only, does not consult storage, authenticate attribution, or verify product
    bytes. Edits/additions/removals outside controls are intentionally permitted.
    """
    _limit(max_descriptor_bytes, "max_descriptor_bytes", 1)
    path = _path(root)
    with _operation("inspect checkout", path), ExitStack() as stack:
        directories = _Directories(stack)
        area = directories.traverse(path, private=True, exact=True)
        control = directories.open(_CONTROL, area, private=True, exact=True, path=path / _CONTROL)
        _control_inventory(control, path / _CONTROL, False)
        info = _decode(_read_descriptor(control, path / _CONTROL / _DESCRIPTOR, max_descriptor_bytes))
        _control_inventory(control, path / _CONTROL, False)
        directories.check()
        return info


def _marker(control, path, expected):
    """Check the original empty regular marker immediately before publication."""
    with _leaf(control, _MARKER, path, mode=0o400, expected=expected) as (_, info):
        if info.st_size != 0:
            raise CheckoutIntegrityError(f"marker {path}: must be empty")


def _source_bindings(objects, runtime, captured):
    """Recheck captured canonical names against their original inodes after mutation seams."""
    for digest, original in captured.items():
        with _leaf(objects, digest, runtime / "objects" / digest, mode=None, expected=original):
            pass


def _verify_tree(directories, product_dirs, files, inventory, control, path,
                 marker, descriptor, encoded, max_descriptor_bytes):
    """Verify bounded exact inventories, independent copies and controls before publication."""
    directories.check()
    for relative, (directory, _) in product_dirs.items():
        if _bounded_entries(directory, len(inventory[relative])) != inventory[relative]:
            raise CheckoutIntegrityError(f"verify inventory {path / relative}: unexpected/missing entries")
    identities = set()
    for entry, parent, name, original in files:
        with _leaf(parent, name, path / entry.path, mode=0o600, expected=original) as (fd, info):
            if _identity(info) in identities:
                raise CheckoutIntegrityError(f"verify file {path / entry.path}: shared copy inode")
            identities.add(_identity(info))
            _stream(fd, entry.artifact, path / entry.path)
    _control_inventory(control, path / _CONTROL, True)
    _marker(control, path / _CONTROL / _MARKER, marker)
    if _read_descriptor(control, path / _CONTROL / _DESCRIPTOR,
                        max_descriptor_bytes, descriptor) != encoded:
        raise CheckoutIntegrityError(f"verify descriptor {path}: changed bytes")
    directories.check()


def checkout_work_product(source: RecordStore, base: RecordReference, destination, *,
                          source_root, protected_roots, max_file_bytes: int,
                          max_total_bytes: int, max_files: int,
                          max_descriptor_bytes: int) -> CheckoutInfo:
    """Copy an exact committed bundle into a new durable, independently writable directory.

    All limits are required ordinary integers (byte limits may be zero). Repeated
    objects count separately. source_root and the explicit list/tuple of additional
    protected roots are trusted caller exclusions; runtime is always excluded too.
    Callers must supply external backup/Git/controller locations: arbitrary ones
    cannot be discovered. Only direct artifacts are read, never dependencies.

    Failures retain output. Marker removal is publication; failures afterward report
    uncertain acknowledgment. Binding checks detect observed changes and constrain
    ordinary access, but cannot authenticate/sandbox a hostile owner or privileged
    process. No canonical records, objects, heads, events or views are written.
    """
    for name, value, minimum in (("max_file_bytes", max_file_bytes, 0),
                                 ("max_total_bytes", max_total_bytes, 0),
                                 ("max_files", max_files, 1),
                                 ("max_descriptor_bytes", max_descriptor_bytes, 1)):
        _limit(value, name, minimum)
    base = _base(base)
    if type(protected_roots) not in (list, tuple):
        raise DomainValidationError("protected_roots: explicit list or tuple required")
    path = _path(destination)
    runtime = _path(source._artifacts._root)
    _outside(path, [_path(source_root), runtime, *(_path(root) for root in protected_roots)])
    # Metadata-only exact lookup closes its transaction before any byte capture.
    # It establishes local structural coherence, never past typed admission.
    with source._transaction() as connection:
        info = CheckoutInfo(base, source._metadata_envelope(connection, base.record_id, base.revision))
    manifest = _inventory(info)
    if len(manifest.files) > max_files:
        raise DomainValidationError("files: exceeds max_files")
    if any(entry.artifact.size > max_file_bytes for entry in manifest.files):
        raise DomainValidationError("files: exceeds max_file_bytes")
    if sum(entry.artifact.size for entry in manifest.files) > max_total_bytes:
        raise DomainValidationError("files: exceeds max_total_bytes")
    encoded = _encode(info)
    if len(encoded) > max_descriptor_bytes:
        raise DomainValidationError("descriptor: exceeds max_descriptor_bytes")
    marker_removed = False
    try:
        with _operation("checkout", path), ExitStack() as stack:
            directories = _Directories(stack)
            parent = directories.traverse(path.parent, exclude_layouts=True)
            source_area = directories.traverse(runtime, private=True)
            objects = directories.open("objects", source_area, private=True, path=runtime / "objects")
            staging = directories.open(".staging", source_area, private=True, path=runtime / ".staging")
            if os.fstat(objects).st_dev != os.fstat(staging).st_dev:
                raise CheckoutLayoutError(f"source layout {runtime}: objects/staging filesystems differ")
            area = directories.create(path.name, parent, path)
            control = directories.create(_CONTROL, area, path / _CONTROL)
            with _new_leaf(control, _MARKER, path / _CONTROL / _MARKER, 0o400) as fd:
                _sync(fd, path / _CONTROL / _MARKER)
                marker = os.fstat(fd)
            barriers = ((control, path / _CONTROL), (area, path), (parent, path.parent))
            for fd, location in barriers:
                _sync(fd, location)
            _fault("after_marker")
            directories.check()
            _marker(control, path / _CONTROL / _MARKER, marker)
            product_dirs = {"": (area, path)}
            inventory = {"": {_CONTROL}}
            files = []
            captured = {}
            for entry in manifest.files:
                parts, relative = entry.path.split("/"), ""
                target = area
                for part in parts[:-1]:
                    next_relative = f"{relative}/{part}" if relative else part
                    if next_relative not in product_dirs:
                        child = directories.create(part, target, path / next_relative)
                        product_dirs[next_relative] = (child, path / next_relative)
                        inventory[relative].add(part)
                        inventory[next_relative] = set()
                    target = product_dirs[next_relative][0]
                    relative = next_relative
                directories.check()
                source_path = runtime / "objects" / entry.artifact.digest
                with _leaf(objects, entry.artifact.digest, source_path, mode=None,
                           expected=captured.get(entry.artifact.digest)) as (source_fd, source_info):
                    captured[entry.artifact.digest] = source_info
                    with _new_leaf(target, parts[-1], path / entry.path, 0o600) as fd:
                        _stream(source_fd, entry.artifact, source_path, fd)
                        _sync(fd, path / entry.path)
                        original = os.fstat(fd)
                files.append((entry, target, parts[-1], original))
                inventory[relative].add(parts[-1])
                _fault("file_copied")
                directories.check()
                _source_bindings(objects, runtime, captured)
            _marker(control, path / _CONTROL / _MARKER, marker)
            with _new_leaf(control, _DESCRIPTOR, path / _CONTROL / _DESCRIPTOR, 0o400) as fd:
                _write_all(fd, encoded)
                _sync(fd, path / _CONTROL / _DESCRIPTOR)
                descriptor = os.fstat(fd)
            _fault("before_publication")
            # Fault/mutation seams precede checks, never bypass the publication gate.
            _source_bindings(objects, runtime, captured)
            _verify_tree(directories, product_dirs, files, inventory, control, path,
                         marker, descriptor, encoded, max_descriptor_bytes)
            for relative in sorted(product_dirs, key=lambda value: value.count("/") + bool(value), reverse=True):
                _sync(*product_dirs[relative])
            for fd, location in barriers:
                _sync(fd, location)
            # Barriers can fail or expose replacement too; check names again after
            # them, including files/control bytes, before the irreversible unlink.
            _verify_tree(directories, product_dirs, files, inventory, control, path,
                         marker, descriptor, encoded, max_descriptor_bytes)
            _source_bindings(objects, runtime, captured)
            directories.check()
            _marker(control, path / _CONTROL / _MARKER, marker)
            with _operation("remove incomplete marker", path / _CONTROL / _MARKER):
                os.unlink(_MARKER, dir_fd=control)
            marker_removed = True
            # Never recreate a marker after this logical boundary or promise rollback.
            _fault("after_publication")
            for fd, location in barriers:
                _sync(fd, location)
            directories.check()
            return info
    except Exception as error:
        if marker_removed:
            # This also covers failures while closing retained descriptors.
            raise CheckoutOperationalError(
                f"publication {path}: marker removed; final synchronization/acknowledgment uncertain; "
                "inspect retained checkout") from error
        raise
