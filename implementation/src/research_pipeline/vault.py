"""Private immutable reading generations with exclusive Linux publication and offline checks.

These observations are local integrity checks, not authentication or acceptance.
Trusted external ancestors and the same-owner/privileged mutation boundary are the
same as checkout: held descriptors detect observed changes, not a hostile owner
who coherently rewrites the whole filesystem between observations.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import posixpath
import secrets
import stat

from research_pipeline.checkout import (
    CheckoutError, CheckoutLayoutError, CheckoutIntegrityError, CheckoutOperationalError,
    _path, _outside, _Directories, _identity, _signature, _leaf, _new_leaf,
    _stream, _write_all,
)
from research_pipeline.domain import ArtifactReference, DomainValidationError, _integer
from research_pipeline.snapshot import SnapshotLimits, SnapshotLimitError, _canonical
from research_pipeline.store import RecordStore
from research_pipeline.view_plan import (
    ReadablePlan, ViewPlanError, readable_plan_from_manifest, verify_plan_links,
)
from research_pipeline.work_product import _path as _portable_path


class ViewError(Exception):
    """Base for local view layout, integrity and operational failures."""


class ViewLayoutError(ViewError):
    """An explicit location or descriptor cannot safely be used as a reading view."""


class ViewIntegrityError(ViewError):
    """Observed bytes or filesystem bindings disagree with the pinned generation."""


class ViewOperationalError(ViewError):
    """I/O failed; retained evidence may describe uncertain publication acknowledgment."""


@dataclass(frozen=True)
class MaterializedView:
    """Immutable local observation at materialization, not continuing availability."""

    snapshot_id: str
    plan_id: str
    manifest_sha256: str
    destination: str
    attempt_path: str
    verification: str = "verified_at_materialization"


@dataclass(frozen=True, order=True)
class ViewDifference:
    """One deterministic bounded explanation of an observed relative-path difference."""

    relative_path: str
    code: str
    detail: str


@dataclass(frozen=True)
class ViewInspection:
    """Current local comparison with a reconstructed plan, without publication history claims."""

    snapshot_id: str
    plan_id: str
    manifest_sha256: str
    status: str
    differences: tuple[ViewDifference, ...]


def _fault(boundary):
    """Private observation/failure seam after real work and before guarded checks."""


@contextmanager
def _boundary(path):
    """Translate reused filesystem errors at the view boundary, retaining paths and causes."""
    try:
        yield
    except CheckoutError as error:
        kind = (ViewLayoutError if isinstance(error, CheckoutLayoutError) else
                ViewIntegrityError if isinstance(error, CheckoutIntegrityError) else ViewOperationalError)
        raise kind(f"view {path}: {error}") from error
    except OSError as error:
        raise ViewOperationalError(f"view {path}: {error}") from error


def _entries(fd, maximum):
    """Enumerate incrementally with a hard allowance, including directory entries."""
    names = set()
    with os.scandir(fd) as entries:
        for entry in entries:
            if len(names) >= maximum:
                raise SnapshotLimitError("max_entries exceeded during directory enumeration")
            names.add(entry.name)
    return names


def _present(fd, name):
    """Inspect a fixed marker name without following links or opening its contents."""
    try:
        os.stat(name, dir_fd=fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _not_layout(fd, path):
    """Reject storage/control roots and even empty interrupted evidence or payload reservations."""
    markers = ("metadata.sqlite3", "snapshot.sqlite3", ".backup-incomplete", ".restore-incomplete",
               ".work-product", "manifest.json", "intent.json", "ready.json", "published.json", "refresh.json")
    if (any(_present(fd, name) for name in markers)
            or (_present(fd, "objects") and _present(fd, ".staging"))
            or path.name.startswith((".readable-view-", ".readable-generation-",
                                       ".readable-refresh-attempt-", ".readable-refresh-package-"))):
        raise ViewLayoutError(f"destination ancestor {path}: recognizable storage/control/view layout")


def _parent(directories, path):
    """Hold all destination ancestors, rejecting symlinks/layouts and requiring a private 0700 parent."""
    parent = directories.traverse(path, private=True, exact=True)
    for _, _, fd, _, _, _, location in directories.bindings:
        _not_layout(fd, Path(location))
    return parent


def _guards(directories, mutable=()):
    """Recheck bindings plus original ancestor ownership/permissions, allowing owned mode transitions."""
    directories.check()
    for _, _, fd, original, _, _, path in directories.bindings:
        current = os.fstat(fd)
        if (current.st_uid, current.st_gid) != (original.st_uid, original.st_gid):
            raise ViewIntegrityError(f"directory {path}: ownership changed")
        if fd not in mutable and current.st_mode != original.st_mode:
            raise ViewIntegrityError(f"directory {path}: permissions changed")


def _absent(parent, name, maximum):
    """Refuse exact or portable-alias siblings without collecting an unbounded parent listing."""
    key = _portable_path(name, "destination basename")
    if len(key) != 1 or len(name.encode("utf-8")) > 240:
        raise ViewLayoutError("destination basename must be one portable component of at most 240 bytes")
    for sibling in _entries(parent, maximum):
        try:
            alias = _portable_path(sibling, "destination sibling")
        except DomainValidationError as error:
            raise ViewLayoutError(f"destination {name}: nonportable sibling {sibling!r}; ambiguous parent") from error
        if sibling == name or alias == key:
            raise ViewLayoutError(f"destination {name}: existing exact or portable-alias sibling {sibling!r}")


def _create(directories, parent, name, path):
    """Reserve a 0700 directory and acquire it safely before any descriptor-only mode transition.

    An umask masking owner bits fails closed; no path-based chmod fallback can
    safely repair a directory whose descriptor could not be acquired.
    """
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
    except FileExistsError as error:
        raise ViewLayoutError(f"new directory {path}: already occupied; no adoption") from error
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if stat.S_IMODE(before.st_mode) != 0o700:
        raise ViewOperationalError(f"new directory {path}: owner-bit-masking umask prevents safe acquisition; retained")
    fd = directories.open(name, parent, private=True, path=path)
    if _identity(os.fstat(fd)) != _identity(before):
        raise ViewIntegrityError(f"new directory {path}: replaced during acquisition")
    os.fchmod(fd, 0o700)
    return fd


def _inventory(plan, maximum):
    """Preflight complete physical files/bytes and directory enumeration before object reads or creation."""
    limits = plan.limits
    files = {f.relative_path: ArtifactReference(hashlib.sha256(f.data).hexdigest(), len(f.data))
             for f in plan.generated_files}
    files.update({f.relative_path: ArtifactReference(f.digest, f.size) for f in plan.artifact_copies})
    if (len(files) > limits.max_files or any(f.size > limits.max_file_bytes for f in files.values())
            or sum(f.size for f in files.values()) > limits.max_total_bytes):
        raise SnapshotLimitError("physical generation exceeds retained limits")
    if len(files) + len(plan.directories) - 1 > maximum:
        raise SnapshotLimitError("max_entries cannot enumerate complete file/directory inventory")
    inventory = {d.relative_path: set() for d in plan.directories}
    for path in (*files, *(d.relative_path for d in plan.directories if d.relative_path)):
        inventory[posixpath.dirname(path)].add(posixpath.basename(path))
    return files, inventory


def _rename_noreplace():
    """Lazily bind Linux libc renameat2; unsupported systems fail without an overwriting fallback."""
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as error:
        raise ViewOperationalError("libc renameat2 unavailable; exclusive publication unsupported") from error
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int

    def publish(source_fd, source_name, target_fd, target_name):
        """Perform exactly one kernel no-replace rename, preserving a competitor's destination."""
        _fault("at_rename")
        if rename(source_fd, os.fsencode(source_name), target_fd, os.fsencode(target_name), 1) != 0:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number), target_name)

    return publish


def _evidence(fd, name, value, path, maximum):
    """Append one bounded exclusive read-only observation and synchronize its inode."""
    data = _canonical(value).encode("ascii")
    if len(data) > maximum:
        raise SnapshotLimitError(f"{name}: control metadata exceeds {maximum} bytes")
    with _new_leaf(fd, name, path / name, 0o400) as leaf:
        _write_all(leaf, data)
        os.fsync(leaf)
    return os.stat(name, dir_fd=fd, follow_symlinks=False)


def _attempt_check(fd, path, evidence, maximum):
    """Check only bounded exact evidence inventory and originally synchronized file signatures."""
    if _entries(fd, maximum) != set(evidence):
        raise ViewIntegrityError(f"attempt {path}: unexpected control inventory")
    for name, info in evidence.items():
        with _leaf(fd, name, path / name, mode=0o400, expected=info):
            pass


def _source_check(objects, runtime, observed):
    """Recheck every distinct canonical binding; legitimate staging hard links remain permitted."""
    for digest, original in observed.items():
        with _leaf(objects, digest, runtime / "objects" / digest, mode=None, expected=original):
            pass


def _generation_check(directories, tree, files, inventory, observations, source_ids, maximum, *, read):
    """Verify exact complete protected output, disjoint inodes and stable held leaf/directory bindings."""
    _guards(directories, tree.values())
    remaining = maximum
    for relative, fd in tree.items():
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o500:
            raise ViewIntegrityError(f"generation directory {relative}: expected 0500")
        names = _entries(fd, remaining)
        remaining -= len(names)
        if names != inventory[relative]:
            raise ViewIntegrityError(f"generation directory {relative}: inventory changed")
    identities = set(source_ids)
    for path, reference in files.items():
        parent = tree[posixpath.dirname(path)]
        with _leaf(parent, posixpath.basename(path), path, mode=0o400,
                   expected=observations[path]) as (fd, info):
            if _identity(info) in identities:
                raise ViewIntegrityError(f"generation file {path}: shared source/output inode")
            identities.add(_identity(info))
            if read:
                _stream(fd, reference, path)
    _guards(directories, tree.values())


def _prepare_generation(stack, directories, generation, generation_path, plan, objects, runtime,
                        max_entries):
    """Construct and verify a complete generation in a caller-owned new directory.

    The caller owns publication and all retained source/output pins. This helper
    preserves the materializer's file seams, independent copies and sync order.
    """
    files, inventory = _inventory(plan, max_entries)
    tree = {"": generation}
    for entry in plan.directories:
        if entry.relative_path:
            relative = entry.relative_path
            tree[relative] = _create(directories, tree[posixpath.dirname(relative)],
                                     posixpath.basename(relative), generation_path / relative)
    observations, sources = {}, {}
    for entry in (*plan.generated_files, *plan.artifact_copies):
        relative = entry.relative_path
        target_parent, name = tree[posixpath.dirname(relative)], posixpath.basename(relative)
        with _new_leaf(target_parent, name, relative, 0o400) as target:
            if hasattr(entry, "data"):
                for offset in range(0, len(entry.data), 65536):
                    _write_all(target, entry.data[offset:offset + 65536])
            else:
                with _leaf(objects, entry.digest, runtime / "objects" / entry.digest, mode=None,
                           expected=sources.get(entry.digest)) as (original, info):
                    if entry.digest not in sources:
                        # Pin each observed source inode through publication and all closes,
                        # so unlink/recreate cannot exploit inode reuse between observations.
                        stack.enter_context(_leaf(objects, entry.digest, runtime / "objects" / entry.digest,
                                                  mode=None, expected=info))
                        sources[entry.digest] = info
                    _stream(original, ArtifactReference(entry.digest, entry.size), entry.digest, target)
            os.fsync(target)
            observations[relative] = os.fstat(target)
            # Acquire the read pin while the exclusive writer still holds the inode.
            # Guarded read-back and final context exits refer to this same allocation.
            stack.enter_context(_leaf(target_parent, name, relative, mode=0o400,
                                      expected=observations[relative]))
        _fault("after_file")
    # All writable preparation ends before the protected complete generation is read back.
    for fd in reversed(tuple(tree.values())):
        os.fchmod(fd, 0o500)
    source_ids = {_identity(info) for info in sources.values()}
    _generation_check(directories, tree, files, inventory, observations, source_ids, max_entries, read=True)
    _source_check(objects, runtime, sources)
    for fd in reversed(tuple(tree.values())):
        os.fsync(fd)
    return tree, files, inventory, observations, sources, source_ids


def materialize_readable_view(source: RecordStore, plan: ReadablePlan, destination, *,
                              source_root, protected_roots, max_entries: int) -> MaterializedView:
    """Verify independent protected copies and publish once to an explicitly absent destination.

    The open source handle only locates guarded objects; no metadata is read.
    Explicit additional backup/control/external Git exclusions are required. The
    parent must exist, be owned and exactly 0700. Token-paired sibling directories
    hold the payload and retained intent/ready/published evidence separately.
    Errors before publication identify both reservations. Errors after attempted rename
    identify uncertain acknowledgment; never roll back or automatically replay.
    """
    _integer(max_entries, "max_entries", 1)
    if type(source) is not RecordStore or type(plan) is not ReadablePlan:
        raise DomainValidationError("expected open RecordStore and ReadablePlan")
    source._require_open()
    if type(protected_roots) not in (list, tuple):
        raise DomainValidationError("protected_roots: explicit list/tuple required")
    verify_plan_links(plan)
    canonical = readable_plan_from_manifest(plan.manifest_bytes, limits=plan.limits)
    if canonical != plan:
        raise ViewPlanError("supplied generated bytes/copies differ from canonical plan")
    files, inventory = _inventory(plan, max_entries)
    attempted = False
    with _boundary(destination):
        path, runtime = _path(destination), _path(source._artifacts._root)
        exclusions = [_path(source_root), runtime, Path(__file__).resolve().parents[2],
                      *(_path(root) for root in protected_roots)]
        _outside(path, exclusions)
        token = secrets.token_hex(16)
        attempt_path = path.parent / (".readable-view-" + token)
        generation_path = path.parent / (".readable-generation-" + token)
        names = (path.name, attempt_path.name, generation_path.name)
        aliases = [_portable_path(name, "reserved basename") for name in names]
        if len(set(aliases)) != len(names):
            raise ViewLayoutError("destination, evidence and payload basenames must not alias")
        for reserved in (attempt_path, generation_path):
            _outside(reserved, exclusions)
    manifest_hash = hashlib.sha256(plan.manifest_bytes).hexdigest()
    intent = dict(format="research_pipeline.readable_view_attempt", version=1,
                  token=token, destination=path.name, generation_name=generation_path.name,
                  parent=[0, 0], generation=[0, 0],
                  snapshot_id=plan.snapshot_id, plan_id=plan.plan_id, manifest_sha256=manifest_hash,
                  recovery="No automatic replay, cleanup, resume or acceptance receipt.")
    # Reserve room for actual signed/unsigned filesystem identity integers before mkdir.
    bounded_intent = {**intent, "parent": [2**64 - 1] * 2, "generation": [2**64 - 1] * 2}
    if len(_canonical(bounded_intent).encode("ascii")) > 16384:
        raise SnapshotLimitError("intent.json exceeds control allowance before reservation")
    try:
        with _boundary(path), ExitStack() as stack:
            directories = _Directories(stack)
            parent = _parent(directories, path.parent)
            ancestors = tuple((b[2], Path(b[6])) for b in directories.bindings)
            for name in names:
                _absent(parent, name, max_entries)
            source_area = directories.traverse(runtime, private=True)
            objects = directories.open("objects", source_area, private=True, path=runtime / "objects")
            staging = directories.open(".staging", source_area, private=True, path=runtime / ".staging")
            if len({os.fstat(fd).st_dev for fd in (source_area, objects, staging)}) != 1:
                raise ViewLayoutError(f"source {runtime}: runtime/objects/staging filesystems differ")
            attempt = _create(directories, parent, attempt_path.name, attempt_path)
            _fault("after_attempt_reservation")
            _absent(parent, generation_path.name, max_entries)
            # Pair evidence and payload by token, but keep the payload in the destination's parent.
            generation = _create(directories, parent, generation_path.name, generation_path)
            _fault("after_generation_reservation")
            intent.update(parent=list(_identity(os.fstat(parent))), generation=list(_identity(os.fstat(generation))))
            evidence = {"intent.json": _evidence(attempt, "intent.json", intent, attempt_path, 16384)}
            for fd in (generation, attempt, parent):
                os.fsync(fd)
            _fault("after_intent")
            _guards(directories)
            publish = _rename_noreplace()
            tree, files, inventory, observations, sources, source_ids = _prepare_generation(
                stack, directories, generation, generation_path, plan, objects, runtime, max_entries)
            identity = {name: intent[name] for name in ("generation", "snapshot_id", "plan_id", "manifest_sha256")}
            evidence["ready.json"] = _evidence(attempt, "ready.json", identity, attempt_path, 2048)
            os.fsync(attempt)
            os.fsync(parent)
            _fault("after_ready")
            _fault("before_rename")
            _generation_check(directories, tree, files, inventory, observations, source_ids, max_entries, read=False)
            _source_check(objects, runtime, sources)
            _attempt_check(attempt, attempt_path, evidence, max_entries)
            for fd, location in ancestors:
                _not_layout(fd, location)
            _absent(parent, path.name, max_entries)
            # Same-parent rename leaves '..' unchanged, so the 0500 root needs no write bit.
            # The kernel independently refuses even a just-created empty destination.
            attempted = True
            publish(parent, generation_path.name, parent, path.name)
            # Only the moved root's binding changes; every descendant descriptor stays pinned.
            for index, binding in enumerate(directories.bindings):
                if binding[2] == generation:
                    directories.bindings[index] = (parent, path.name, *binding[2:6], str(path))
                    break
            _fault("after_rename")
            _generation_check(directories, tree, files, inventory, observations, source_ids, max_entries, read=False)
            if _present(parent, generation_path.name):
                raise ViewIntegrityError(f"payload {generation_path}: old preparation binding still present")
            # Only this parent participates in the rename; evidence has its own append barriers.
            os.fsync(parent)
            _fault("after_publication_sync")
            _generation_check(directories, tree, files, inventory, observations, source_ids, max_entries, read=False)
            _source_check(objects, runtime, sources)
            evidence["published.json"] = _evidence(attempt, "published.json", identity, attempt_path, 2048)
            os.fsync(attempt)
            _fault("after_published")
            _generation_check(directories, tree, files, inventory, observations, source_ids, max_entries, read=False)
            _source_check(objects, runtime, sources)
            for fd, location in ancestors:
                _not_layout(fd, location)
            _attempt_check(attempt, attempt_path, evidence, max_entries)
        # ExitStack closes are part of success. After rename any failure is lost acknowledgment,
        # not rollback: both the destination and evidence must remain for explicit diagnosis.
    except Exception as error:
        if attempted:
            raise ViewOperationalError(f"destination {path}; attempt_path {attempt_path}: uncertain publication acknowledgment; "
                                       f"inspect explicit destination and retained evidence; no rollback/replay: {error}") from error
        if isinstance(error, (ViewError, SnapshotLimitError, DomainValidationError, ViewPlanError)):
            raise type(error)(f"destination {path}; attempt_path {attempt_path}; payload_path {generation_path}: {error}") from error
        raise ViewOperationalError(f"destination {path}; attempt_path {attempt_path}; payload_path {generation_path}: "
                                   f"preparation failed; retained: {error}") from error
    return MaterializedView(plan.snapshot_id, plan.plan_id, manifest_hash, str(path), str(attempt_path))


def _safe_directory(info):
    """Permit traversal only of owned private readable/searchable directories without special bits."""
    mode = stat.S_IMODE(info.st_mode)
    return (stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
            and not mode & 0o7077 and mode & 0o500 == 0o500)


def _safe_file(info):
    """Permit reads of owned private single-link regular files, including owner-edited 0600 copies."""
    mode = stat.S_IMODE(info.st_mode)
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and info.st_nlink == 1
            and not mode & 0o7077 and bool(mode & 0o400))


def _inspect_open(stack, parent, name, info, path):
    """Retain a no-follow/nonblocking readable inode after validating the initial entry's safe type."""
    if not _safe_file(info):
        raise ViewIntegrityError(f"descriptor/file {path}: unsafe type, ownership, hardlink or permissions")
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR, errno.ENOENT, errno.ESTALE):
            raise ViewIntegrityError(f"file {path}: binding changed during open") from error
        raise
    stack.callback(os.close, fd)
    if _signature(os.fstat(fd)) != _signature(info):
        raise ViewIntegrityError(f"file {path}: changed during open")
    return fd


def _inspect_bytes(fd, info, path, *, retain=False):
    """Hash one bounded observed size with a single EOF probe; optionally retain descriptor bytes."""
    remaining, digest, chunks = info.st_size, hashlib.sha256(), []
    while remaining:
        chunk = os.read(fd, min(remaining, 65536))
        if not chunk:
            raise ViewIntegrityError(f"file {path}: truncated during inspection")
        remaining -= len(chunk)
        digest.update(chunk)
        if retain:
            chunks.append(chunk)
        _fault("inspection_chunk")
    if os.read(fd, 1):
        raise ViewIntegrityError(f"file {path}: grew during inspection")
    if _signature(os.fstat(fd)) != _signature(info):
        raise ViewIntegrityError(f"file {path}: changed during inspection")
    return digest.hexdigest(), b"".join(chunks)


def _binding_change(error):
    """Recognize inaccessible or disappeared bindings, excluding resource and I/O failures."""
    return isinstance(error, OSError) and error.errno in (
        errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE, errno.EACCES, errno.EPERM)


def inspect_readable_view(root, *, limits: SnapshotLimits, max_entries: int,
                          expected_plan_id: str | None = None) -> ViewInspection:
    """Read one explicitly pinned local tree without storage access, writes, repair or execution.

    Invalid/unsafe descriptors and roots raise errors. Once a canonical descriptor
    is established, differences describe missing/extra/unsafe/edited contents.
    Caller limits bound descriptor decoding, actual bytes and each enumeration
    pass. Final inode/signature and directory inventory checks prevent an observed
    race from returning verified. An optional independent plan pin strengthens
    comparison, but neither result authenticates a coherent hostile-owner rewrite
    nor proves historical publication/fsync acknowledgment. Resource/I/O failures
    during final binding verification raise ViewOperationalError even after differences.
    """
    _integer(max_entries, "max_entries", 1)
    if type(limits) is not SnapshotLimits:
        raise DomainValidationError("limits: expected SnapshotLimits")
    limits = SnapshotLimits(**limits.to_dict())
    if expected_plan_id is not None:
        ArtifactReference(expected_plan_id, 0)
    with _boundary(root), ExitStack() as stack:
        path = _path(root)
        directories = _Directories(stack)
        try:
            area = directories.traverse(path, private=True)
        except (CheckoutError, OSError) as error:
            raise ViewLayoutError(f"inspection root {path}: unusable: {error}") from error
        root_info = os.fstat(area)
        if not _safe_directory(root_info):
            raise ViewLayoutError(f"inspection root {path}: requires owned private readable/searchable directory")
        try:
            descriptor_info = os.stat("manifest.json", dir_fd=area, follow_symlinks=False)
            if descriptor_info.st_size > min(limits.max_file_bytes, limits.max_total_bytes):
                raise SnapshotLimitError("manifest exceeds caller descriptor byte allowance")
            descriptor = _inspect_open(stack, area, "manifest.json", descriptor_info, path / "manifest.json")
            manifest_hash, data = _inspect_bytes(descriptor, descriptor_info, "manifest.json", retain=True)
            if _signature(os.stat("manifest.json", dir_fd=area, follow_symlinks=False)) != _signature(descriptor_info):
                raise ViewIntegrityError("manifest.json: changed during descriptor read")
        except FileNotFoundError as error:
            raise ViewLayoutError(f"inspection {path}: missing manifest.json") from error
        plan = readable_plan_from_manifest(data, limits=limits)
        if expected_plan_id is not None and expected_plan_id != plan.plan_id:
            raise ViewIntegrityError(f"inspection {path}: expected_plan_id mismatch")
        files, inventory = _inventory(plan, max_entries)
        differences = set()

        def difference(relative, code, detail):
            """Retain a stable path/code and bounded diagnostic, never uncontrolled exception output."""
            differences.add(ViewDifference(relative, code, str(detail)[:240]))

        def attributes(relative, info, directory=False):
            """Report observable attributes before opening a child; unsafe values are never read/followed."""
            if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
                difference(relative, "type", "expected directory" if directory else "expected regular file")
            if info.st_uid != os.geteuid():
                difference(relative, "owner", "entry does not belong to effective user")
            expected = 0o500 if directory else 0o400
            if stat.S_IMODE(info.st_mode) != expected:
                difference(relative, "mode", f"expected {expected:04o}; observed {stat.S_IMODE(info.st_mode):04o}")
            if not directory and info.st_nlink != 1:
                difference(relative, "hardlink", "expected one link")

        attributes("", root_info, True)
        tree = {"": area}
        directory_stats = {"": root_info}
        inventories = {}
        observed = {"manifest.json": (area, "manifest.json", descriptor, descriptor_info)}
        total, remaining = descriptor_info.st_size, max_entries
        _fault("inspection_after_manifest")
        for relative in inventory:
            if relative not in tree:
                continue  # A missing/unsafe ancestor is reported as an unverifiable subtree.
            fd = tree[relative]
            names = _entries(fd, remaining)
            remaining -= len(names)
            inventories[relative] = names
            for name in sorted(names - inventory[relative]):
                difference(posixpath.join(relative, name), "extra", "unexpected entry/subtree; not followed")
            for name in sorted(inventory[relative] - names):
                difference(posixpath.join(relative, name), "missing", "expected entry/subtree absent")
            for name in sorted(names & inventory[relative]):
                child = posixpath.join(relative, name)
                try:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    is_directory = child in inventory
                    attributes(child, info, is_directory)
                    if is_directory:
                        if _safe_directory(info):
                            opened = directories.open(name, fd, private=True, path=path / child)
                            if _signature(os.fstat(opened)) != _signature(info):
                                raise ViewIntegrityError("directory changed during open")
                            tree[child], directory_stats[child] = opened, info
                    elif child != "manifest.json" and _safe_file(info):
                        if info.st_size > limits.max_file_bytes or total + info.st_size > limits.max_total_bytes:
                            raise SnapshotLimitError(f"{child}: actual inspected bytes exceed caller allowance")
                        total += info.st_size
                        leaf = _inspect_open(stack, fd, name, info, child)
                        observed[child] = (fd, name, leaf, info)
                        digest, _ = _inspect_bytes(leaf, info, child)
                        expected = files[child]
                        if info.st_size != expected.size:
                            difference(child, "size", f"expected {expected.size}; observed {info.st_size}")
                        if digest != expected.digest:
                            difference(child, "digest", "SHA-256 differs from canonical expectation")
                except (ViewIntegrityError, CheckoutIntegrityError, CheckoutLayoutError, FileNotFoundError) as error:
                    difference(child, "changed_during_inspection", error)
                except CheckoutOperationalError as error:
                    cause = error.__cause__
                    if isinstance(cause, PermissionError):
                        difference(child, "mode", "expected subtree is inaccessible")
                    elif _binding_change(cause):
                        difference(child, "changed_during_inspection", error)
                    else:
                        raise  # Resource/I/O exhaustion must never become partial successful inspection.
                except PermissionError as error:
                    difference(child, "mode", f"entry inaccessible: {error}")
        _fault("inspection_before_final")
        # Each pass counts both files and directories. Never recursively enumerate an extra subtree.
        remaining = max_entries
        for relative, fd in tree.items():
            try:
                names = _entries(fd, remaining)
                remaining -= len(names)
                if names != inventories[relative]:
                    difference(relative, "changed_during_inspection", "directory entries changed")
                if _signature(os.fstat(fd)) != _signature(directory_stats[relative]):
                    difference(relative, "changed_during_inspection", "directory signature changed")
            except (FileNotFoundError, PermissionError) as error:
                difference(relative, "changed_during_inspection", error)
        for relative, (parent, name, fd, original) in observed.items():
            try:
                if (_signature(os.fstat(fd)) != _signature(original)
                        or _signature(os.stat(name, dir_fd=parent, follow_symlinks=False)) != _signature(original)):
                    difference(relative, "changed_during_inspection", "opened file signature/binding changed")
            except FileNotFoundError:
                difference(relative, "changed_during_inspection", "opened file binding disappeared")
        try:
            _guards(directories)
        except (ViewIntegrityError, CheckoutIntegrityError, CheckoutLayoutError) as error:
            difference("", "changed_during_inspection", error)
        except CheckoutOperationalError as error:
            # An observed binding change is divergence; failure to check is not an observation.
            if not _binding_change(error.__cause__):
                raise
            difference("", "changed_during_inspection", error)
        except OSError as error:
            if not _binding_change(error):
                raise
            difference("", "changed_during_inspection", error)
        result = ViewInspection(plan.snapshot_id, plan.plan_id, manifest_hash,
                                "diverged" if differences else "verified", tuple(sorted(differences)))
    return result
