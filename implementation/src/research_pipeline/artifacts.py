"""Owned local POSIX artifact storage with verified, durable no-overwrite publication."""

from contextlib import contextmanager, ExitStack
import errno
import hashlib
import os
from pathlib import Path
import stat
import uuid

from research_pipeline.domain import ArtifactReference, DomainValidationError


class ArtifactError(Exception):
    """Base for layout, availability, integrity, and operational artifact failures."""


class ArtifactLayoutError(ArtifactError):
    """The selected artifact area is missing, unsafe, or not an owned private layout."""


class ArtifactNotFoundError(ArtifactError):
    """The requested digest has no canonical object in an otherwise valid area."""


class ArtifactIntegrityError(ArtifactError):
    """An object is unsafe or its actual bytes do not match the typed reference."""


class ArtifactIOError(ArtifactError):
    """An operating-system read, publication, or durability operation failed."""


def _runtime_path(root: str | os.PathLike) -> Path:
    """Anchor an explicit runtime path to caller cwd without resolving away symlinks."""
    path = Path(root)
    return path if path.is_absolute() else Path.cwd() / path


@contextmanager
def _directory(name: str | Path, parent: int | None = None, owned: bool = False):
    """Open one no-follow directory and close it reliably; optionally enforce privacy."""
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EACCES):
            raise ArtifactLayoutError(f"open directory {name}: missing, inaccessible, or unsafe") from error
        raise
    try:
        info = os.fstat(descriptor)
        if owned and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise ArtifactLayoutError(f"directory {name}: requires effective-user ownership and no group/other access")
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _path_directory(path: Path):
    """Traverse every supplied path component without following directory symlinks."""
    with ExitStack() as stack:
        descriptor = stack.enter_context(_directory(path.anchor))
        for part in path.parts[1:]:
            descriptor = stack.enter_context(_directory(part, descriptor))
        yield descriptor


def _typed_reference(reference: ArtifactReference) -> None:
    """Validate the typed address before it can become a directory-relative filename."""
    if type(reference) is not ArtifactReference:
        raise DomainValidationError("reference: expected ArtifactReference")
    # Recheck at the filesystem boundary even if callers bypassed frozen construction.
    ArtifactReference(reference.digest, reference.size)


def _regular_object(info: os.stat_result, digest: str) -> None:
    """Reject nonregular, foreign-owned, or writable canonical objects."""
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o222):
        raise ArtifactIntegrityError(f"object {digest}: requires an owned read-only regular file")


def _read_object(objects: int, reference: ArtifactReference, *, retain: bool,
                 synchronize: bool = False, expected: bytes | None = None) -> bytes | None:
    """Verify one opened inode's type, bytes, size and hash, optionally retaining or syncing it."""
    digest = reference.digest
    try:
        info = os.stat(digest, dir_fd=objects, follow_symlinks=False)
    except FileNotFoundError as error:
        raise ArtifactNotFoundError(f"read object {digest}: absent") from error
    _regular_object(info, digest)
    try:
        descriptor = os.open(digest, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=objects)
    except FileNotFoundError as error:
        raise ArtifactNotFoundError(f"open object {digest}: absent") from error
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ArtifactIntegrityError(f"open object {digest}: symlink") from error
        raise
    try:
        opened = os.fstat(descriptor)
        _regular_object(opened, digest)
        if opened.st_size != reference.size:
            raise ArtifactIntegrityError(f"object {digest}: expected size {reference.size}, found {opened.st_size}")
        count = 0
        hasher = hashlib.sha256()
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            if expected is not None and chunk != expected[count:count + len(chunk)]:
                raise ArtifactIntegrityError(f"object {digest}: existing bytes differ from put input")
            count += len(chunk)
            if count > reference.size:
                raise ArtifactIntegrityError(f"object {digest}: grew beyond expected size")
            hasher.update(chunk)
            if retain:
                chunks.append(chunk)
        if count != reference.size or hasher.hexdigest() != digest:
            raise ArtifactIntegrityError(f"object {digest}: byte count or SHA-256 mismatch")
        _regular_object(os.fstat(descriptor), digest)
        if synchronize:
            os.fsync(descriptor)
        return b"".join(chunks) if retain else None
    finally:
        os.close(descriptor)


class ArtifactStore:
    """Trusted-controller byte store; use create/open with an explicit outside-source root.

    Handles are scoped to operations. Privacy and read-only files constrain ordinary
    access, not a hostile owner or privileged process. Integrity is not scientific proof.
    """

    def __init__(self, root: Path):
        """Retain only a runtime path; create/open and every operation validate the layout."""
        self._root = root

    @classmethod
    def create(cls, root: str | os.PathLike) -> "ArtifactStore":
        """Create and sync an absent private area under an existing non-symlink parent.

        Existing roots are never changed. Failed creation may leave a partial area;
        neither creation nor opening repairs or removes it.
        """
        path = _runtime_path(root)
        try:
            with _path_directory(path.parent) as parent:
                try:
                    os.mkdir(path.name, 0o700, dir_fd=parent)
                except FileExistsError as error:
                    raise ArtifactLayoutError(f"create {path}: root already exists") from error
                with _directory(path.name, parent, owned=True) as area:
                    for name in ("objects", ".staging"):
                        os.mkdir(name, 0o700, dir_fd=area)
                    for name in ("objects", ".staging"):
                        with _directory(name, area, owned=True) as child:
                            os.fsync(child)
                    os.fsync(area)
                # Persist the root entry too, not only the directories inside it.
                os.fsync(parent)
            return cls.open(path)
        except OSError as error:
            raise ArtifactIOError(f"create artifact area {path}: {error}") from error

    @classmethod
    def open(cls, root: str | os.PathLike) -> "ArtifactStore":
        """Validate a complete existing private area without creating or repairing files."""
        store = cls(_runtime_path(root))
        try:
            with store._layout():
                pass
        except OSError as error:
            raise ArtifactIOError(f"open artifact area {store._root}: {error}") from error
        return store

    @contextmanager
    def _layout(self):
        """Recheck owned directories on each operation and keep only scoped descriptors."""
        with _path_directory(self._root.parent) as parent:
            with _directory(self._root.name, parent, owned=True) as area:
                with _directory("objects", area, owned=True) as objects:
                    with _directory(".staging", area, owned=True) as staging:
                        if os.fstat(objects).st_dev != os.fstat(staging).st_dev:
                            raise ArtifactLayoutError("objects and .staging must share a filesystem")
                        yield objects, staging

    def put(self, data: bytes) -> ArtifactReference:
        """Durably publish immutable bytes, or fully verify and sync an identical object.

        Failures never repair or remove canonical objects. A failure after linking
        may retain a valid unreferenced object; abrupt termination can retain staging.
        """
        if type(data) is not bytes:
            raise DomainValidationError("data: put accepts immutable bytes only")
        reference = ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))
        try:
            with self._layout() as (objects, staging):
                try:
                    _read_object(objects, reference, retain=False, synchronize=True, expected=data)
                except ArtifactNotFoundError:
                    self._publish(objects, staging, reference, data)
                # Required even on reuse: another publisher may have just linked it.
                os.fsync(objects)
            return reference
        except OSError as error:
            raise ArtifactIOError(f"put object {reference.digest}: {error}") from error

    def _publish(self, objects: int, staging: int, reference: ArtifactReference, data: bytes) -> None:
        """Stage, fsync, and link bytes without clobbering; clean only this call's temp entry."""
        name = uuid.uuid4().hex
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=staging)
        failed = True
        try:
            try:
                remaining = memoryview(data)
                while remaining:
                    written = os.write(descriptor, remaining)
                    if written == 0:
                        raise OSError(errno.EIO, "staging write made no progress")
                    remaining = remaining[written:]
                os.fchmod(descriptor, 0o400)
                # No buffered writes remain; inode durability precedes publication.
                os.fsync(descriptor)
                try:
                    # Atomic destination creation never replaces a concurrent winner.
                    os.link(name, reference.digest, src_dir_fd=staging,
                            dst_dir_fd=objects, follow_symlinks=False)
                except FileExistsError:
                    _read_object(objects, reference, retain=False, synchronize=True, expected=data)
            finally:
                os.close(descriptor)
            failed = False
        finally:
            try:
                os.unlink(name, dir_fd=staging)
                os.fsync(staging)
            except OSError:
                # Preserve the publication diagnostic on failure; cleanup failure on
                # the success path is itself a failed durability acknowledgment.
                if not failed:
                    raise

    def read(self, reference: ArtifactReference) -> bytes:
        """Return verified bytes or raise for absence, unsafe objects, corruption, or I/O."""
        _typed_reference(reference)
        try:
            with self._layout() as (objects, _):
                return _read_object(objects, reference, retain=True)
        except OSError as error:
            raise ArtifactIOError(f"read object {reference.digest}: {error}") from error

    def verify(self, reference: ArtifactReference) -> None:
        """Perform full read integrity checks without retaining the resulting byte string."""
        _typed_reference(reference)
        try:
            with self._layout() as (objects, _):
                _read_object(objects, reference, retain=False)
        except OSError as error:
            raise ArtifactIOError(f"verify object {reference.digest}: {error}") from error

    def _verify_for_commit(self, reference: ArtifactReference) -> None:
        """Verify and sync existing bytes and their directory before a metadata commit.

        This closes an interrupted publisher's directory-barrier gap without
        changing bytes, repairing objects, or changing public read semantics.
        """
        _typed_reference(reference)
        try:
            with self._layout() as (objects, _):
                _read_object(objects, reference, retain=False, synchronize=True)
                os.fsync(objects)
        except OSError as error:
            raise ArtifactIOError(f"commit verification {reference.digest}: {error}") from error
