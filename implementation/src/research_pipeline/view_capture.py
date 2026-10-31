"""Bounded read-only observations of edited readable generations, detached from storage."""

from contextlib import ExitStack
from dataclasses import dataclass, fields
import errno
import hashlib
import os
from pathlib import Path
import posixpath
import stat

from research_pipeline.checkout import _path, _outside, _identity, _signature
from research_pipeline.domain import ArtifactReference, DomainValidationError, _integer
from research_pipeline.snapshot import (
    SnapshotLimits, SnapshotLimitError, SnapshotIntegrityError, _bounded_json,
    _canonical, _strict_json,
)
from research_pipeline.vault import (
    ViewLayoutError, ViewIntegrityError, _boundary, _present, _safe_directory, _safe_file,
)
from research_pipeline.view_plan import (
    ArtifactCopy, DirectoryEntry, GeneratedFile, ReadablePlan, ViewPlanError,
    readable_plan_from_manifest,
)
from research_pipeline.work_product import _path as _portable_path


_FORMAT = "research_pipeline.readable_view_capture"
_LIMITATIONS = (
    "Captured-only local observation; canonical authority is unchanged.",
    "All contents are inert, unsubmitted proposed work; no execution or policy activation.",
    "Binding and byte checks detect observed local mutations, not coherent hostile same-owner or privileged rewrites.",
    "No durable preservation, successor, receipt, timestamp or authentication is supplied.",
)
_SIGNATURE_FIELDS = ("device", "inode", "size", "mtime_ns", "ctime_ns", "mode", "uid", "gid", "nlink")


@dataclass(frozen=True)
class CaptureLimits:
    """Mandatory independent reconstruction, inventory, metadata and descriptor allowances."""

    plan_limits: SnapshotLimits
    max_entries: int
    max_files: int
    max_directories: int
    max_depth: int
    max_file_bytes: int
    max_total_bytes: int
    max_metadata_bytes: int
    max_diagnostics: int
    max_open_descriptors: int

    def __post_init__(self):
        """Detach nested limits and reject coerced, infinite or non-signed-64-bit budgets."""
        if type(self.plan_limits) is not SnapshotLimits:
            raise DomainValidationError("plan_limits: expected SnapshotLimits")
        object.__setattr__(self, "plan_limits", SnapshotLimits(**self.plan_limits.to_dict()))
        for field in fields(self):
            if field.name != "plan_limits":
                minimum = 0 if field.name in ("max_file_bytes", "max_total_bytes") else 1
                _integer(getattr(self, field.name), field.name, minimum)

    def to_dict(self):
        """Return independent strict budgets, revalidating bypassed frozen assignments."""
        value = CaptureLimits(**{f.name: getattr(self, f.name) for f in fields(self)})
        return {f.name: (value.plan_limits.to_dict() if f.name == "plan_limits" else getattr(value, f.name))
                for f in fields(self)}


def _limits(value):
    """Require the exact public limits type and detach its nested allowance."""
    if type(value) is not CaptureLimits:
        raise DomainValidationError("limits: expected CaptureLimits")
    return CaptureLimits(**{f.name: getattr(value, f.name) for f in fields(value)})


def _digest(data):
    """Return the exact SHA-256 of immutable content or canonical ASCII metadata."""
    return hashlib.sha256(data).hexdigest()


def _identified(document, field):
    """Bind every other canonical field, without inventing authentication or a receipt."""
    return _digest(_canonical({k: v for k, v in document.items() if k != field}).encode("ascii"))


class _Metadata:
    """Incremental canonical metadata reservation shared only by capture and its pure planner."""

    def __init__(self, maximum, used=0):
        """Start with separately retained metadata already charged to the aggregate budget."""
        self.maximum, self.used = maximum, used
        self.reserve(0)

    def reserve(self, size):
        """Charge bytes before retaining more metadata, failing instead of truncating evidence."""
        if self.used + size > self.maximum:
            raise SnapshotLimitError("max_metadata_bytes exceeded")
        self.used += size

    def size(self, value):
        """Bound JSON escaping before allocating a complete serialized row."""
        return len(_bounded_json(value, self.maximum - self.used, "max_metadata_bytes"))

    def append(self, rows, row):
        """Reserve one exact array contribution before appending a complete row."""
        self.reserve(self.size(row) + bool(rows))
        rows.append(row)


def _relative(path, limits):
    """Validate original Unicode spelling and byte/depth ceilings; return portable alias keys."""
    if type(path) is not str:
        raise ViewLayoutError("capture path must be an ordinary string")
    if path == "":
        return ()
    if len(path) > 1024:
        raise ViewLayoutError("capture path exceeds relative ceiling")
    try:
        if len(path.encode("utf-8")) > 1024 or any(len(p.encode("utf-8")) > 240 for p in path.split("/")):
            raise ViewLayoutError("capture path exceeds 240-byte component or 1024-byte relative ceiling")
        keys = _portable_path(path, "capture path")
    except (DomainValidationError, UnicodeError) as error:
        raise ViewLayoutError(f"unsafe capture path {path!r}") from error
    if len(keys) > limits.max_depth:
        raise SnapshotLimitError("max_depth exceeded")
    return keys


def _alias(path, aliases, limits):
    """Reject different spellings at any shared prefix, including across expected/observed trees."""
    keys = _relative(path, limits)
    parts = path.split("/") if path else []
    for length in range(1, len(keys) + 1):
        key, original = keys[:length], tuple(parts[:length])
        if key in aliases and aliases[key] != original:
            raise ViewLayoutError(f"portable alias conflict at {path!r}")
        aliases[key] = original


def _inventory_limits(files, directories, limits):
    """Independently bound a complete expected or observed physical inventory, including root."""
    if len(files) > limits.max_files:
        raise SnapshotLimitError("max_files exceeded")
    if len(directories) > limits.max_directories:
        raise SnapshotLimitError("max_directories exceeded")
    if len(files) + len(directories) - 1 > limits.max_entries:
        raise SnapshotLimitError("max_entries exceeded")
    total = 0
    for item in files:
        _integer(item["size"], "file size", 0)
        total += item["size"]
        if item["size"] > limits.max_file_bytes or total > limits.max_total_bytes:
            raise SnapshotLimitError("file inventory byte allowance exceeded")
    for item in (*files, *directories):
        _relative(item["path"], limits)


def _expected(plan, limits):
    """Derive complete physical expectations, explicitly including the self-excluded manifest."""
    document = plan.to_dict()
    files = [dict(item) for item in document["files"]]
    files.append(dict(path="manifest.json", sha256=_digest(plan.manifest_bytes), size=len(plan.manifest_bytes),
                      mode=0o400, role="manifest", hash_kind="generated"))
    files.sort(key=lambda item: item["path"])
    _inventory_limits(files, document["directories"], limits)
    return files, document["directories"]


def _canonical_plan(plan, limits):
    """Bound frozen inputs before rendering and require equality with independent reconstruction."""
    if type(plan) is not ReadablePlan:
        raise DomainValidationError("expected_plan: full ReadablePlan required")
    if type(plan.manifest_bytes) is not bytes:
        raise ViewPlanError("expected immutable manifest bytes")
    if len(plan.manifest_bytes) > min(limits.max_metadata_bytes, limits.max_file_bytes,
                                    limits.max_total_bytes, limits.plan_limits.max_file_bytes):
        raise SnapshotLimitError("expected manifest exceeds caller allowances")
    for values in (plan.generated_files, plan.artifact_copies, plan.directories):
        if type(values) is not tuple:
            raise ViewPlanError("expected immutable inventory tuples")
    if (len(plan.generated_files) + len(plan.artifact_copies) > min(limits.max_files, limits.plan_limits.max_files)
            or len(plan.directories) > limits.max_directories
            or len(plan.generated_files) + len(plan.artifact_copies) + len(plan.directories) - 1 > limits.max_entries):
        raise SnapshotLimitError("expected inventory exceeds caller allowances")
    total = 0
    for values, entry_type in ((plan.generated_files, GeneratedFile), (plan.artifact_copies, ArtifactCopy),
                               (plan.directories, DirectoryEntry)):
        for entry in values:
            if type(entry) is not entry_type:
                raise ViewPlanError("incorrect expected inventory value type")
            entry.__post_init__()
            _relative(entry.relative_path, limits)
            if entry_type is DirectoryEntry:
                continue
            size = len(entry.data) if entry_type is GeneratedFile else entry.size
            total += size
            if size > limits.max_file_bytes or total > limits.max_total_bytes:
                raise SnapshotLimitError("expected physical bytes exceed caller allowances")
    # The manifest is retained both as independent bytes and as escaped capture
    # text. Reject impossible metadata budgets before canonical reconstruction.
    preflight = _Metadata(limits.max_metadata_bytes, len(plan.manifest_bytes))
    try:
        preflight.reserve(preflight.size(plan.manifest_bytes.decode("ascii")))
    except UnicodeError as error:
        raise ViewPlanError("expected canonical ASCII manifest") from error
    canonical = readable_plan_from_manifest(plan.manifest_bytes, limits=limits.plan_limits)
    # Equality alone aliases booleans and integers; the existing verifier also
    # revalidates exact frozen types before comparison with canonical rendering.
    from research_pipeline.view_plan import verify_plan_links
    verify_plan_links(plan)
    if canonical != plan:
        raise ViewPlanError("supplied plan differs from independent canonical reconstruction")
    _expected(canonical, limits)
    return canonical


def _stat_document(info):
    """Encode checkout's atime-free signature with exact named fields."""
    signature = _signature(info)
    return dict(zip(_SIGNATURE_FIELDS, (*signature[0], *signature[1:])))


def _fault(boundary, path):
    """Private observation seam for coordinated mutation/failure tests, never a caller callback."""


def _binding_stat(parent, name):
    """Read an established binding, classifying disappearance as conflict rather than missing work."""
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE):
            raise ViewIntegrityError(f"binding changed: {name!r}") from error
        raise


def _ancestor_binding(info):
    """Return stat identity, type, permissions and ownership without external membership metadata."""
    return _identity(info), info.st_mode, info.st_uid, info.st_gid


def _not_storage(fd, path, root=False):
    """Check only fixed layout markers, allowing the intended root's opaque manifest entry."""
    markers = ("metadata.sqlite3", "snapshot.sqlite3", ".backup-incomplete", ".restore-incomplete",
               ".work-product", "intent.json", "ready.json", "published.json")
    if (any(_present(fd, name) for name in markers)
            or (not root and _present(fd, "manifest.json"))
            or (_present(fd, "objects") and _present(fd, ".staging"))
            or path.name.startswith((".readable-view-", ".readable-generation-"))):
        raise ViewLayoutError(f"capture ancestor {path}: recognizable storage/control layout")


class _Observation:
    """One operation's retained no-follow descriptors, inventories and final consistency gate."""

    def __init__(self, stack, limits, budget, document, aliases):
        """Use ExitStack for all closes; count retained and temporary enumeration descriptors."""
        self.stack, self.limits, self.budget = stack, limits, budget
        self.document, self.aliases = document, aliases
        self.bindings, self.tree, self.payloads = [], {}, []
        self.directory_ids = set()
        self.entries, self.total = 0, 0
        self.device = None

    def capacity(self):
        """Check before acquiring even the temporary descriptor duplicated by scandir(fd)."""
        if len(self.bindings) >= self.limits.max_open_descriptors:
            raise SnapshotLimitError("max_open_descriptors exceeded")

    def open(self, parent, name, path, info, *, ancestor=False):
        """Pin an entry; compare ancestor bindings or complete in-tree lstat/fstat signatures."""
        directory = stat.S_ISDIR(info.st_mode)
        if ancestor:
            if not directory:
                raise ViewLayoutError(f"ancestor {path}: symlink or non-directory")
        elif not (_safe_directory(info) if directory else _safe_file(info)):
            raise ViewLayoutError(f"unsafe entry {path}: type, ownership, permissions or links")
        if not ancestor and self.device is not None and info.st_dev != self.device:
            raise ViewLayoutError(f"cross-device subtree {path}")
        if directory and _identity(info) in self.directory_ids:
            raise ViewLayoutError(f"repeated directory identity {path}")
        self.capacity()
        _fault("before_open", str(path))
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                         (os.O_DIRECTORY if directory else 0), dir_fd=parent)
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE):
                raise ViewIntegrityError(f"entry changed during open: {path}") from error
            raise
        self.stack.callback(os.close, fd)
        opened = os.fstat(fd)
        signature = _ancestor_binding if ancestor else _signature
        if signature(opened) != signature(info):
            raise ViewIntegrityError(f"entry replaced during open: {path}")
        self.bindings.append((parent, name, fd, info, ancestor))
        if directory:
            self.directory_ids.add(_identity(info))
        return fd

    def ancestors(self, path):
        """Pin the complete chain without using unrelated external directory membership as a gate."""
        parent, current = None, Path(path.anchor)
        for name in (path.anchor, *path.parts[1:]):
            if parent is not None:
                current /= name
            root = current == path
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError as error:
                raise ViewLayoutError(f"missing prior root/ancestor: {current}") from error
            fd = self.open(parent, name, current, info, ancestor=not root)
            _not_storage(fd, current, root)
            if not root:
                row = dict(path=str(current), device=info.st_dev, inode=info.st_ino,
                           mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
                self.budget.append(self.document["ancestors"], row)
            parent = fd
        self.device = info.st_dev
        return fd, info

    def names(self, fd, relative, *, verification=False, count=0):
        """Enumerate incrementally under one pass-wide entry allowance before sorting names."""
        names, reserved = [], 0
        temporary = _Metadata(self.limits.max_metadata_bytes) if verification else self.budget
        self.capacity()
        with os.scandir(fd) as iterator:
            for entry in iterator:
                count += 1
                if count > self.limits.max_entries:
                    raise SnapshotLimitError("max_entries exceeded during enumeration")
                path = posixpath.join(relative, entry.name)
                try:
                    _alias(path, self.aliases, self.limits)
                except ViewLayoutError as error:
                    if verification:
                        raise ViewIntegrityError("directory acquired an unsafe/aliased member") from error
                    raise
                # Enumeration metadata is bounded before retaining each name, even
                # on the verification pass; it does not enlarge retained evidence.
                size = temporary.size(entry.name) + bool(names)
                temporary.reserve(size)
                reserved += size
                names.append(entry.name)
        temporary.used -= reserved
        return sorted(names), count

    def read(self, fd, info, path, *, verify=None):
        """Read at most the declared bounded size in 64 KiB chunks and one EOF probe per pass."""
        remaining, chunks, digest = info.st_size, [], hashlib.sha256()
        offset = 0
        while remaining:
            data = os.read(fd, min(remaining, 65536))
            if not data:
                raise ViewIntegrityError(f"early EOF: {path}")
            if verify is None:
                chunks.append(data)
            elif data != verify[offset:offset + len(data)]:
                raise ViewIntegrityError(f"bytes changed: {path}")
            remaining -= len(data)
            offset += len(data)
            digest.update(data)
            _fault("chunk_read" if verify is None else "verification_chunk", path)
        if os.read(fd, 1):
            raise ViewIntegrityError(f"file grew: {path}")
        if _signature(os.fstat(fd)) != _signature(info):
            raise ViewIntegrityError(f"file signature changed: {path}")
        return digest.hexdigest(), b"".join(chunks)

    def walk(self, fd, info):
        """Iteratively visit every safe subtree and retain every file, including unchanged bytes."""
        pending = [("", fd, info)]
        while pending:
            relative, directory, original = pending.pop()
            names, self.entries = self.names(directory, relative, count=self.entries)
            row = dict(path=relative, mode=stat.S_IMODE(original.st_mode),
                       signature=_stat_document(original), entries=names)
            self.budget.append(self.document["directories"], row)
            self.tree[relative] = (directory, original, names)
            for name in names:
                path = posixpath.join(relative, name)
                before = _binding_stat(directory, name)
                is_directory = stat.S_ISDIR(before.st_mode)
                if is_directory:
                    if len(self.tree) + len(pending) >= self.limits.max_directories:
                        raise SnapshotLimitError("max_directories exceeded")
                else:
                    if not _safe_file(before):
                        raise ViewLayoutError(f"unsafe file {path}")
                    if len(self.payloads) >= self.limits.max_files:
                        raise SnapshotLimitError("max_files exceeded")
                    if before.st_size > self.limits.max_file_bytes or self.total + before.st_size > self.limits.max_total_bytes:
                        raise SnapshotLimitError("observed byte allowance exceeded")
                    self.total += before.st_size
                child = self.open(directory, name, path, before)
                if is_directory:
                    pending.append((path, child, before))
                else:
                    digest, data = self.read(child, before, path)
                    self.budget.append(self.document["files"], dict(path=path, sha256=digest,
                        size=before.st_size, mode=stat.S_IMODE(before.st_mode), signature=_stat_document(before)))
                    self.payloads.append((path, data))
                    _fault("file_read", path)
        self.document["files"].sort(key=lambda row: row["path"])
        self.document["directories"].sort(key=lambda row: row["path"])
        self.payloads.sort()

    def check(self):
        """Recheck tree memberships, bytes and full signatures, and external ancestor bindings."""
        count = 0
        for path, (fd, original, expected) in sorted(self.tree.items()):
            names, count = self.names(fd, path, verification=True, count=count)
            if names != expected or _signature(os.fstat(fd)) != _signature(original):
                raise ViewIntegrityError(f"directory changed: {path!r}")
        payloads = dict(self.payloads)
        # Bindings are acquisition-ordered; payload lookup uses exact relative names.
        by_identity = {_identity(info): (fd, info) for _, _, fd, info, ancestor in self.bindings
                       if not ancestor and stat.S_ISREG(info.st_mode)}
        for row in self.document["files"]:
            # File records are sorted just like payloads; the held inode remains
            # accessible even if a concurrent editor moves its original name.
            path = row["path"]
            fd, info = by_identity[(row["signature"]["device"], row["signature"]["inode"])]
            os.lseek(fd, 0, os.SEEK_SET)
            self.read(fd, info, path, verify=payloads[path])
        _fault("before_binding_gate", "")
        for parent, name, fd, original, ancestor in self.bindings:
            current, held = _binding_stat(parent, name), os.fstat(fd)
            if ancestor:
                changed = (_ancestor_binding(current) != _ancestor_binding(original)
                           or _ancestor_binding(held) != _ancestor_binding(original))
            else:
                changed = _signature(current) != _signature(original) or _signature(held) != _signature(original)
            if changed:
                raise ViewIntegrityError(f"final binding changed: {name!r}")


def _fields(value, names, label):
    """Require exact ordinary object fields for the private versioned representation."""
    if type(value) is not dict or set(value) != set(names):
        raise ViewIntegrityError(f"{label}: incorrect fields")


def _signature_value(value, kind, mode):
    """Validate strict stat numbers, private safe types and duplicate permission fields."""
    _fields(value, _SIGNATURE_FIELDS, "signature")
    for name, number in value.items():
        _integer(number, "signature " + name, -(2**63) if name in ("mtime_ns", "ctime_ns") else 0)
    _integer(mode, "mode", 0)
    if stat.S_IMODE(value["mode"]) != mode or mode & 0o7077 or value["uid"] != os.geteuid():
        raise ViewIntegrityError("unsafe or inconsistent retained mode/owner")
    if kind == "directory":
        safe = value["mode"] == (stat.S_IFDIR | mode) and mode & 0o500 == 0o500 and value["nlink"] >= 1
    else:
        safe = value["mode"] == (stat.S_IFREG | mode) and bool(mode & 0o400) and value["nlink"] == 1
    if not safe:
        raise ViewIntegrityError("unsafe retained entry type")


def _validated_capture(capture):
    """Validate offline schema, authority and payloads; return document, plan and limits.

    Bound required ancestor depth before expanding prefixes, rejecting inconsistent
    retained chains or descriptor overruns before traversing their rows.
    """
    if type(capture) is not CapturedReadableView:
        raise DomainValidationError("capture: expected CapturedReadableView")
    limits = _limits(capture._limits)
    if type(capture._state) is not str or len(capture._state) > limits.max_metadata_bytes:
        raise ViewIntegrityError("invalid retained capture state")
    try:
        document = _strict_json(capture._state, maximum_depth=72)
    except SnapshotIntegrityError as error:
        raise ViewIntegrityError("invalid canonical capture JSON") from error
    _fields(document, ("format", "version", "capture_id", "prior_view", "expected_plan_id", "expected_snapshot_id",
                      "expected_manifest_sha256", "expected_manifest", "limits", "ancestors", "directories", "files",
                      "limitations"), "capture")
    if (document["format"] != _FORMAT or type(document["version"]) is not int or document["version"] != 1
            or _canonical(document["limits"]) != _canonical(limits.to_dict())
            or document["limitations"] != list(_LIMITATIONS)):
        raise ViewIntegrityError("unsupported capture schema/limits/limitations")
    manifest = document["expected_manifest"]
    if type(manifest) is not str or not manifest.isascii():
        raise ViewIntegrityError("expected canonical ASCII manifest")
    if len(capture._state) + len(manifest) > limits.max_metadata_bytes:
        raise SnapshotLimitError("aggregate capture metadata exceeds max_metadata_bytes")
    plan = readable_plan_from_manifest(manifest.encode("ascii"), limits=limits.plan_limits)
    if (document["expected_plan_id"] != plan.plan_id or document["expected_snapshot_id"] != plan.snapshot_id
            or document["expected_manifest_sha256"] != _digest(plan.manifest_bytes)
            or document["capture_id"] != _identified(document, "capture_id")):
        raise ViewIntegrityError("inconsistent capture identity")
    expected_files, expected_dirs = _expected(plan, limits)
    prior = document["prior_view"]
    if type(prior) is not str or not prior.startswith("/"):
        raise ViewIntegrityError("invalid absolute prior view")
    prior_path = _path(prior)
    if str(prior_path) != prior:
        raise ViewIntegrityError("invalid absolute prior view")
    if any(type(document[name]) is not list for name in ("files", "directories", "ancestors")):
        raise ViewIntegrityError("capture arrays required")
    if len(document["ancestors"]) + len(document["files"]) + len(document["directories"]) + 1 > limits.max_open_descriptors:
        raise SnapshotLimitError("retained inventory exceeds descriptor allowance")
    # Preflight lexical depth before allocating prefixes: retained rows alone
    # cannot bound a forged prior path, and a full parent list costs quadratic space.
    ancestor_count = len(prior_path.parts) - 1
    if ancestor_count + len(document["files"]) + len(document["directories"]) + 1 > limits.max_open_descriptors:
        raise SnapshotLimitError("required ancestor chain exceeds descriptor allowance")
    if ancestor_count != len(document["ancestors"]):
        raise ViewIntegrityError("incomplete ancestor chain")
    identities = set()
    path = Path(prior_path.anchor)
    for index, ancestor in enumerate(document["ancestors"]):
        if index:
            path /= prior_path.parts[index]
        _fields(ancestor, ("path", "device", "inode", "mode", "uid", "gid"), "ancestor")
        if ancestor["path"] != str(path):
            raise ViewIntegrityError("incorrect ancestor order")
        for key in ("device", "inode", "mode", "uid", "gid"):
            _integer(ancestor[key], key, 0)
        if ancestor["mode"] > 0o7777:
            raise ViewIntegrityError("ancestor mode is not permission bits")
        identity = ancestor["device"], ancestor["inode"]
        if identity in identities:
            raise ViewIntegrityError("repeated retained ancestor identity")
        identities.add(identity)
    aliases = {}
    for item in (*expected_files, *expected_dirs):
        _alias(item["path"], aliases, limits)
    observed, children = {}, {}
    for kind, rows in (("directory", document["directories"]), ("file", document["files"])):
        paths = []
        for row in rows:
            _fields(row, ("path", "mode", "signature", "entries") if kind == "directory" else
                    ("path", "sha256", "size", "mode", "signature"), kind)
            path = row["path"]
            _alias(path, aliases, limits)
            if path in observed or (not path and kind != "directory"):
                raise ViewIntegrityError("duplicate/invalid inventory path")
            _signature_value(row["signature"], kind, row["mode"])
            identity = row["signature"]["device"], row["signature"]["inode"]
            if identity in identities:
                raise ViewIntegrityError("repeated retained inode")
            identities.add(identity)
            paths.append(path)
            observed[path] = kind
            if kind == "directory":
                if type(row["entries"]) is not list or any(type(n) is not str for n in row["entries"]):
                    raise ViewIntegrityError("invalid directory names")
                if row["entries"] != sorted(set(row["entries"])):
                    raise ViewIntegrityError("noncanonical directory inventory")
                children[path] = []
            else:
                ArtifactReference(row["sha256"], row["size"])
                if row["size"] != row["signature"]["size"]:
                    raise ViewIntegrityError("conflicting file sizes")
        if paths != sorted(paths):
            raise ViewIntegrityError("inventory is not path-sorted")
    if observed.get("") != "directory":
        raise ViewIntegrityError("missing root directory")
    device = document["directories"][0]["signature"]["device"]
    for row in (*document["directories"], *document["files"]):
        if row["signature"]["device"] != device:
            raise ViewIntegrityError("retained cross-device subtree")
        if row["path"]:
            parent = posixpath.dirname(row["path"])
            if parent not in children:
                raise ViewIntegrityError("missing directory parent")
            children[parent].append(posixpath.basename(row["path"]))
    for row in document["directories"]:
        if row["entries"] != sorted(children[row["path"]]):
            raise ViewIntegrityError("directory membership disagrees with inventory")
    _inventory_limits(document["files"], document["directories"], limits)
    payloads = capture._payloads
    if type(payloads) is not tuple or len(payloads) != len(document["files"]):
        raise ViewIntegrityError("invalid immutable payload inventory")
    for pair, row in zip(payloads, document["files"]):
        if (type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str or type(pair[1]) is not bytes
                or pair[0] != row["path"] or len(pair[1]) != row["size"] or _digest(pair[1]) != row["sha256"]):
            raise ViewIntegrityError("payload path/bytes/hash mismatch")
    return document, plan, limits


@dataclass(frozen=True, init=False)
class CapturedReadableView:
    """Private canonical metadata plus immutable sorted path/byte pairs; no live resource handles."""

    _state: str
    _payloads: tuple
    _limits: CaptureLimits

    def __init__(self, document, payloads, limits):
        """Detach internally constructed state and reject incoherent schemas or payloads."""
        limits = _limits(limits)
        object.__setattr__(self, "_state", _bounded_json(document, limits.max_metadata_bytes, "capture"))
        object.__setattr__(self, "_payloads", tuple(payloads))
        object.__setattr__(self, "_limits", limits)
        _validated_capture(self)

    def to_dict(self):
        """Return freshly reconstructed metadata after complete retained-state validation."""
        return _validated_capture(self)[0]

    @property
    def capture_id(self):
        """Return the validated local observation identity, never an authentication claim."""
        return self.to_dict()["capture_id"]

    @property
    def expected_plan_id(self):
        """Return the independently supplied canonical base identity."""
        return self.to_dict()["expected_plan_id"]

    @property
    def expected_manifest_bytes(self):
        """Return exact independent canonical control bytes, separate from observed controls."""
        return self.to_dict()["expected_manifest"].encode("ascii")

    def file_bytes(self, relative_path: str) -> bytes:
        """Return retained exact observed bytes; missing paths raise KeyError without filesystem access."""
        _validated_capture(self)
        if type(relative_path) is not str:
            raise DomainValidationError("relative_path: expected string")
        for path, data in self._payloads:
            if path == relative_path:
                return data
        raise KeyError(relative_path)


def capture_readable_view(prior_view, *, expected_plan: ReadablePlan, source_root,
                          protected_roots, limits: CaptureLimits) -> CapturedReadableView:
    """Capture every safe observed byte against a full independently retained canonical plan.

    Explicit exclusions must include canonical runtime/objects, backups, controller
    state and external Git administration. Each enumeration pass has max_entries;
    initial reads and final verification each have max_total_bytes plus one EOF
    probe per file. Reads can affect atime. Nothing is written or made durable.
    A later publisher must recheck this observation; no indefinite editor lock or
    authentication against coherent hostile-owner rewrites is supplied.
    """
    limits = _limits(limits)
    plan = _canonical_plan(expected_plan, limits)
    if type(protected_roots) not in (list, tuple):
        raise DomainValidationError("protected_roots: explicit list/tuple required")
    if len(protected_roots) + 1 > limits.max_entries:
        raise SnapshotLimitError("source/protected input entries exceed max_entries")
    with _boundary(prior_view):
        path = _path(prior_view)
        inputs = _Metadata(limits.max_metadata_bytes)
        inputs.reserve(inputs.size(str(path)))
        excluded = []
        for root in (source_root, *protected_roots, Path(__file__).resolve(strict=True).parents[2]):
            candidate = _path(root)
            inputs.reserve(inputs.size(str(candidate)))
            excluded.append(candidate)
        _outside(path, excluded)
        document = dict(format=_FORMAT, version=1, capture_id="0" * 64, prior_view=str(path),
            expected_plan_id=plan.plan_id, expected_snapshot_id=plan.snapshot_id,
            expected_manifest_sha256=_digest(plan.manifest_bytes), expected_manifest=plan.manifest_bytes.decode("ascii"),
            limits=limits.to_dict(), ancestors=[], directories=[], files=[], limitations=list(_LIMITATIONS))
        budget = _Metadata(limits.max_metadata_bytes, len(plan.manifest_bytes))
        budget.reserve(budget.size(document))
        aliases = {}
        files, directories = _expected(plan, limits)
        for item in (*files, *directories):
            _alias(item["path"], aliases, limits)
        with ExitStack() as stack:
            observation = _Observation(stack, limits, budget, document, aliases)
            fd, info = observation.ancestors(path)
            observation.walk(fd, info)
            document["capture_id"] = _identified(document, "capture_id")
            result = CapturedReadableView(document, observation.payloads, limits)
            _fault("before_final_gate", "")
            observation.check()
        # Close failures are operational errors through _boundary, never partial
        # success. No descriptor or scandir iterator survives this return.
        return result
