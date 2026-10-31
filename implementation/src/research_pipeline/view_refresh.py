"""Preserve an original observation and atomically publish its associated reading successor.

No metadata transaction, automatic import, cleanup, replay or mutable pointer is
part of this protocol. The source handle only locates immutable artifact objects.
"""

from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import posixpath
import secrets
import stat

from research_pipeline.checkout import (
    _Directories, _path, _outside, _identity, _signature, _leaf, _new_leaf, _write_all, _stream,
)
from research_pipeline.domain import ArtifactReference, DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError, _canonical
from research_pipeline.store import RecordStore
from research_pipeline.vault import (
    ViewError, ViewLayoutError, ViewIntegrityError, ViewOperationalError, _boundary,
    _parent, _create, _present, _guards, _source_check, _not_layout,
    _prepare_generation, _rename_noreplace, _attach_recovery,
)
from research_pipeline.view_capture import (
    _canonical_plan, _capture_observation, _digest, _Metadata, _binding_stat, _expected,
)
from research_pipeline.view_plan import ReadablePlan, ViewPlanError
from research_pipeline.view_preservation import _plan_metadata
from research_pipeline.view_refresh_metadata import (
    RefreshLimits, RefreshedReadableView, RefreshInspection, _limits_value, _relationships,
    _package_metadata, ATTEMPT_LIMITATIONS,
)
from research_pipeline.work_product import _path as _portable_path


ATTEMPT_PREFIX = ".readable-refresh-attempt-"
PACKAGE_PREFIX = ".readable-refresh-package-"


def _fault(boundary):
    """Private lifecycle seam after real work, before final byte/binding publication gates."""


def _relative(path, limits):
    """Check package-relative names before allocation, retaining the 240-byte component rule."""
    if type(path) is not str or len(path) > 4096:
        raise ViewLayoutError("invalid package path or 4096-byte ceiling exceeded")
    if not path:
        return ()
    try:
        if len(path.encode("utf-8")) > 4096 or any(len(c.encode("utf-8")) > 240 for c in path.split("/")):
            raise ViewLayoutError("package component/path byte ceiling exceeded")
        keys = _portable_path(path, "package path")
    except (UnicodeError, DomainValidationError) as error:
        raise ViewLayoutError("unsafe package path") from error
    if len(keys) > limits.max_depth:
        raise SnapshotLimitError("max_depth exceeded")
    return keys


def _inventory_bounds(files, directories, limits):
    """Charge physical copies and directories, including root, without trusting stored budgets."""
    if len(files) > limits.max_files:
        raise SnapshotLimitError("max_files exceeded")
    if len(directories) > limits.max_directories:
        raise SnapshotLimitError("max_directories exceeded")
    if len(files) + len(directories) - 1 > limits.max_entries:
        raise SnapshotLimitError("max_entries exceeded")
    total = 0
    for row in files:
        total += row["size"]
        if row["size"] > limits.max_file_bytes or total > limits.max_total_bytes:
            raise SnapshotLimitError("refresh physical byte allowance exceeded")
    for row in (*files, *directories):
        _relative(row["path"], limits)


def _locations(destination, source_root, protected_roots, limits, *, prior=None, runtime=None):
    """Validate bounded lexical boundaries in both directions without resolving caller paths."""
    if type(protected_roots) not in (list, tuple):
        raise DomainValidationError("protected_roots: explicit list/tuple required")
    if len(protected_roots) + 1 > limits.max_entries:
        raise SnapshotLimitError("protected input count exceeds max_entries")
    budget = _Metadata(limits.max_metadata_bytes)
    paths = []
    for value in (destination, source_root, *protected_roots, Path(__file__).resolve().parents[2],
                  *((prior,) if prior is not None else ()), *((runtime,) if runtime is not None else ())):
        path = _path(value)
        budget.reserve(budget.size(str(path)))
        paths.append(path)
    destination, exclusions = paths[0], paths[1:]
    _relative(destination.name, limits)
    if destination.name.startswith((ATTEMPT_PREFIX, PACKAGE_PREFIX)):
        raise ViewLayoutError("reserved refresh destination prefix")
    _outside(destination, exclusions)
    return destination, exclusions


def _sibling_aliases(parent, names, maximum, *, absent=()):
    """Stream a bounded collision scan without retaining unrelated sibling path metadata."""
    keys = {_portable_path(name, "reserved sibling"): name for name in names}
    if len(keys) != len(names):
        raise ViewLayoutError("aliased reserved names")
    with os.scandir(parent) as iterator:
        for count, entry in enumerate(iterator, 1):
            if count > maximum:
                raise SnapshotLimitError("max_entries exceeded during parent collision scan")
            name = entry.name
            try:
                key = _portable_path(name, "sibling")
            except DomainValidationError as error:
                raise ViewLayoutError("ambiguous parent sibling") from error
            if name in absent:
                error = ViewLayoutError("occupied reserved destination: " + name)
                error._readable_collision = True
                raise error
            if key in keys and keys[key] != name:
                raise ViewLayoutError("portable alias for reserved sibling")


def _marker(format_name, token, package, refresh_id, manifest_hash):
    """Construct exact ready/published observations, without historical durability claims."""
    return dict(format="research_pipeline.readable_refresh_" + format_name, version=1,
                token=token, package=package, refresh_id=refresh_id, manifest_sha256=manifest_hash)


def _physical_rows(manifest, controls, evidence):
    """Include the self-excluded descriptor and all possible separate evidence copies in bounds."""
    files = list(manifest["files"])
    files.append(dict(path="refresh.json", size=len(controls["refresh.json"])))
    files.extend(dict(path="attempt/" + name, size=len(_canonical(value).encode("ascii")))
                 for name, value in evidence.items())
    return files, [*manifest["directories"], dict(path="attempt", mode=0o700)]


def _absolute_paths(files, directories, destination, package_path, attempt_path, maximum):
    """Admit all physical paths beneath both package roots using strict UTF-8 byte lengths.

    Called after complete inventory admission and before any output reservation.
    The optional private ceiling leaves public API path behavior unchanged.
    """
    if maximum is None:
        return

    def check(path):
        """Reject paths above the byte ceiling, including invalid Unicode scalar values."""
        try:
            size = len(str(path).encode("utf-8", errors="strict"))
        except UnicodeError as error:
            raise SnapshotLimitError("absolute output path requires strict UTF-8") from error
        if size > maximum:
            raise SnapshotLimitError("absolute output path byte allowance exceeded")

    for root in (destination, package_path, attempt_path):
        check(root)
    for row in (*files, *directories):
        relative = row["path"]
        # Synthetic attempt rows account for sibling evidence, not package children.
        if relative == "attempt" or relative.startswith("attempt/"):
            check(attempt_path / relative.removeprefix("attempt").lstrip("/"))
        else:
            for root in (destination, package_path):
                check(root / relative)


class _PreservationAdmission:
    """Refresh-only prospective physical reservations, separate from nested comparison allowances."""

    def __init__(self, prior, successor, limits, evidence):
        """Reserve fixed locations/copies and known controls before any observed payload is read."""
        self.limits = limits
        files, directories = _expected(prior, limits.capture_limits)
        self.expected_files = {row["path"]: row for row in files}
        self.expected_dirs = {row["path"]: row for row in directories}
        self.files, self.directories = {}, {""}
        self.control_files = set()
        self.total, self.metadata = 0, 0
        for entry in successor.directories:
            self.reserve("generation" + ("/" + entry.relative_path if entry.relative_path else ""))
        for entry in successor.generated_files:
            self.reserve("generation/" + entry.relative_path, len(entry.data),
                         control=entry.relative_path == "manifest.json")
        for entry in successor.artifact_copies:
            self.reserve("generation/" + entry.relative_path, entry.size)
        for name in ("capture.json", "preservation-plan.json", "README.md", "refresh.json"):
            # The embedded canonical manifest's escaped JSON text is already a
            # known lower bound; replace it with the full capture size later.
            size = len(_canonical(prior.manifest_bytes.decode("ascii"))) if name == "capture.json" else 0
            self.reserve(name, size, control=True)
        self.reserve("preservation/controls/expected-manifest.json", len(prior.manifest_bytes), control=True)
        for name, value in evidence.items():
            self.reserve("attempt/" + name, len(_canonical(value)), control=True)

    def reserve(self, path, size=None, *, control=False):
        """Admit a copy/parents, replacing a known size reservation as control bytes become available."""
        _relative(path, self.limits)
        parents = set()
        parent = path if size is None else posixpath.dirname(path)
        while parent and parent not in self.directories:
            parents.add(parent)
            parent = posixpath.dirname(parent)
        added = size is not None and path not in self.files
        extra_bytes = 0 if size is None else size - self.files.get(path, 0)
        count = len(self.files) + added
        directories = len(self.directories) + len(parents)
        total = self.total + extra_bytes
        metadata = self.metadata + (extra_bytes if control or path in self.control_files else 0)
        if count > self.limits.max_files or directories > self.limits.max_directories:
            raise SnapshotLimitError("prospective preservation file/directory allowance exceeded")
        if count + directories - 1 > self.limits.max_entries:
            raise SnapshotLimitError("prospective preservation max_entries exceeded")
        if (size is not None and size > self.limits.max_file_bytes) or total > self.limits.max_total_bytes:
            raise SnapshotLimitError("prospective preservation byte allowance exceeded")
        if metadata > self.limits.max_metadata_bytes:
            raise SnapshotLimitError("prospective control evidence exceeds max_metadata_bytes")
        self.directories.update(parents)
        if size is not None:
            self.files[path] = size
            if control:
                self.control_files.add(path)
        self.total, self.metadata = total, metadata

    def observe(self, path, info, digest=None):
        """Admit stat-known divergence before open, or hash-known divergence before payload retention."""
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISDIR(info.st_mode):
            expected = self.expected_dirs.get(path)
            if expected is None or mode != expected["mode"]:
                self.reserve("preservation/tree" + ("/" + path if path else ""))
        else:
            expected = self.expected_files.get(path)
            if path == "manifest.json":
                self.reserve("preservation/controls/observed-manifest.bin", info.st_size, control=True)
            elif (expected is None or (info.st_size, mode) != (expected["size"], expected["mode"])
                    or digest is not None and digest != expected["sha256"]):
                self.reserve("preservation/tree/" + path, info.st_size)

    def descriptors(self):
        """Return additional preservation descriptors, charging shared ancestors only once."""
        return sum(path.startswith("preservation/") for path in self.files) + sum(
            path == "preservation" or path.startswith("preservation/") for path in self.directories)

    def reconcile(self, preservation):
        """Admit final rename/ambiguity copies once the complete tree establishes their associations."""
        # Subtree rename decisions require the entire observation; guessing an
        # ambiguity earlier could overcharge unchanged owners of a unique move.
        for row in preservation["directories"]:
            self.reserve("preservation" + ("/" + row["preservation_path"] if row["preservation_path"] else ""))
        for row in preservation["files"]:
            self.reserve("preservation/" + row["preservation_path"], row["size"])


def _write_pin(stack, tree, path, data, mode):
    """Exclusively write/sync an independent private inode and retain its guarded read descriptor."""
    parent, name = tree[posixpath.dirname(path)], posixpath.basename(path)
    with _new_leaf(parent, name, path, mode) as fd:
        for offset in range(0, len(data), 65536):
            _write_all(fd, data[offset:offset + 65536])
        os.fsync(fd)
        info = os.fstat(fd)
        pin, _ = stack.enter_context(_leaf(parent, name, path, mode=mode, expected=info))
    return parent, name, pin, info, ArtifactReference(_digest(data), len(data))


def _check_pins(pins, identities=()):
    """Verify bytes and original signatures before/after reads and across the complete pass."""
    seen = set(identities)
    for path, (parent, name, fd, original, reference) in sorted(pins.items()):
        if (_signature(_binding_stat(parent, name)) != _signature(original)
                or _signature(os.fstat(fd)) != _signature(original)):
            raise ViewIntegrityError(f"output binding changed: {path}")
        identity = _identity(original)
        if identity in seen:
            raise ViewIntegrityError(f"shared output/prior/source inode: {path}")
        seen.add(identity)
        os.lseek(fd, 0, os.SEEK_SET)
        _stream(fd, reference, path)
        if (_signature(_binding_stat(parent, name)) != _signature(original)
                or _signature(os.fstat(fd)) != _signature(original)):
            raise ViewIntegrityError(f"output changed during verification: {path}")
    # A later stream can overlap an edit to an already verified inode or name.
    # Reading affects atime only, which the shared full signature excludes.
    for path, (parent, name, fd, original, _) in sorted(pins.items()):
        if (_signature(_binding_stat(parent, name)) != _signature(original)
                or _signature(os.fstat(fd)) != _signature(original)):
            raise ViewIntegrityError(f"output changed across verification: {path}")


def _check_tree(directories, tree, modes, inventory, maximum):
    """Bound one exact membership pass, ending with original bindings and package modes.

    Each invocation has its own entry allowance; external ancestors retain their
    existing guards without acquiring a package membership requirement.
    """
    _guards(directories, tree.values())
    remaining = maximum
    for path, fd in sorted(tree.items()):
        if stat.S_IMODE(os.fstat(fd).st_mode) != modes[path]:
            raise ViewIntegrityError(f"output directory mode changed: {path}")
        names = set()
        with os.scandir(fd) as iterator:
            for entry in iterator:
                # Unknown names fail before retention; expected names already fit
                # the complete manifest metadata allowance.
                if entry.name not in inventory[path]:
                    raise ViewIntegrityError(f"unexpected output member: {path}")
                remaining -= 1
                if remaining < 0:
                    raise SnapshotLimitError("max_entries exceeded during output verification")
                names.add(entry.name)
        if names != inventory[path]:
            raise ViewIntegrityError(f"output membership changed: {path}")
    _guards(directories, tree.values())
    for path, fd in sorted(tree.items()):
        if stat.S_IMODE(os.fstat(fd).st_mode) != modes[path]:
            raise ViewIntegrityError(f"output directory mode changed: {path}")


def _members(files, directories):
    """Index exact immediate child names from already validated complete relative inventories."""
    inventory = {r["path"]: set() for r in directories}
    for path in [r["path"] for r in files] + [r["path"] for r in directories if r["path"]]:
        inventory[posixpath.dirname(path)].add(posixpath.basename(path))
    return inventory


def refresh_readable_view(source: RecordStore, prior_view, destination, *, expected_plan: ReadablePlan, new_plan: ReadablePlan,
                          source_root, protected_roots, limits: RefreshLimits) -> RefreshedReadableView:
    """Preserve one consistent prior observation and publish a distinct complete successor package.

    Both canonical plans are independently reconstructed before prior reads. Every
    same-plan call still captures, preserves and publishes at an absent destination.
    Failures retain all work; private exception metadata records established recovery
    facts, including on KeyboardInterrupt. After attempted rename acknowledgment is uncertain.
    Each verification rereads bounded bytes with one EOF probe per file, not one
    lifetime I/O allowance. Coherent hostile-owner changes and the interval after
    final observation remain outside the local mutation guarantee.
    """
    return _refresh_readable_view(source, prior_view, destination, expected_plan=expected_plan,
        new_plan=new_plan, source_root=source_root, protected_roots=protected_roots, limits=limits)


def _refresh_readable_view(source: RecordStore, prior_view, destination, *, expected_plan: ReadablePlan,
                           new_plan: ReadablePlan, source_root, protected_roots, limits: RefreshLimits,
                           absolute_path_maximum=None) -> RefreshedReadableView:
    """Run the single capture/publication lifecycle with an optional private absolute output ceiling.

    CLI callers bound the complete derived inventory before reservation; public
    callers retain the existing independent relative-path and resource limits.
    Failures preserve the same established recovery facts as the public entry point.
    """
    limits = _limits_value(limits)
    if type(source) is not RecordStore:
        raise DomainValidationError("source: expected open RecordStore")
    source._require_open()
    if type(expected_plan) is ReadablePlan and type(expected_plan.manifest_bytes) is bytes:
        if len(expected_plan.manifest_bytes) > limits.max_metadata_bytes:
            raise SnapshotLimitError("prior input metadata exceeds outer max_metadata_bytes")
    prior = _canonical_plan(expected_plan, limits.capture_limits)
    successor_capture_limits = replace(limits.capture_limits, plan_limits=limits.successor_limits,
        max_entries=limits.max_entries, max_files=limits.max_files, max_directories=limits.max_directories,
        max_depth=limits.max_depth, max_file_bytes=limits.max_file_bytes, max_total_bytes=limits.max_total_bytes,
        max_metadata_bytes=limits.max_metadata_bytes)
    successor = _canonical_plan(new_plan, successor_capture_limits)
    _, mappings = _relationships(prior, successor, limits.max_diagnostics)
    diagnostic_allowance = limits.max_diagnostics - len(mappings)
    if diagnostic_allowance < 1:
        raise SnapshotLimitError("max_diagnostics cannot cover preservation comparisons")
    attempted = False
    with _boundary(destination):
        runtime = _path(source._artifacts._root)
        path, exclusions = _locations(destination, source_root, protected_roots, limits,
                                      prior=prior_view, runtime=runtime)
        prior_path = _path(prior_view)
        _outside(prior_path, [_path(source_root), runtime, *(_path(p) for p in protected_roots),
                              Path(__file__).resolve().parents[2]])
        token = secrets.token_hex(16)
        attempt_path, package_path = path.parent / (ATTEMPT_PREFIX + token), path.parent / (PACKAGE_PREFIX + token)
        names = path.name, attempt_path.name, package_path.name
        if len({_portable_path(n, "reserved basename") for n in names}) != 3:
            raise ViewLayoutError("reserved refresh names alias")
        for reserved in (attempt_path, package_path):
            _outside(reserved, exclusions)
    placeholders = [2**64 - 1] * 2
    intent = dict(format="research_pipeline.readable_refresh_attempt", version=1, token=token,
        destination=path.name, package_name=package_path.name, parent=placeholders, package=placeholders,
        prior_plan_id=prior.plan_id, successor_plan_id=successor.plan_id, capture_id="0" * 64,
        preservation_plan_id="0" * 64, refresh_id="0" * 64, manifest_sha256="0" * 64,
        limitations=list(ATTEMPT_LIMITATIONS))
    evidence = {"intent.json": intent,
        "ready.json": _marker("ready", token, placeholders, "0" * 64, "0" * 64),
        "published.json": _marker("published", token, placeholders, "0" * 64, "0" * 64)}
    admission = _PreservationAdmission(prior, successor, limits, evidence)
    # Nested capture limits bound comparison reads. Independently reserve known
    # output obligations before the associated prior descriptors/payloads exist.
    fixed_descriptors = (len(path.parent.parts) + len(runtime.parts) + 2 + 2 + len(successor.directories)
                         + len(successor.generated_files) + len(successor.artifact_copies)
                         + len({e.digest for e in successor.artifact_copies}) + 4 + 3 + 3)
    def capacity(prior_count):
        """Enforce the single operation allowance before capture acquires another descriptor."""
        if fixed_descriptors + prior_count + admission.descriptors() > limits.max_open_descriptors:
            raise SnapshotLimitError("max_open_descriptors exceeded across refresh")
    capacity(len(prior_path.parts) + len(prior.generated_files) + len(prior.artifact_copies) + len(prior.directories))
    recovery = dict(destination=str(path), prior_snapshot_id=prior.snapshot_id, prior_plan_id=prior.plan_id,
                    successor_snapshot_id=successor.snapshot_id, successor_plan_id=successor.plan_id,
                    rename_entered=False, collision=False)
    try:
        with _boundary(path), ExitStack() as stack:
            captured, observation = _capture_observation(stack, prior_path, expected_plan=prior,
                source_root=source_root, protected_roots=[runtime, *protected_roots],
                limits=limits.capture_limits, capacity=capacity, metadata_maximum=limits.max_metadata_bytes,
                admission=admission.observe)
            capture = captured.to_dict()
            recovery["capture_id"] = capture["capture_id"]
            admission.reserve("capture.json", len(captured._state), control=True)
            planning_limits = replace(limits.capture_limits,
                max_metadata_bytes=min(limits.capture_limits.max_metadata_bytes, limits.max_metadata_bytes),
                max_diagnostics=min(limits.capture_limits.max_diagnostics, diagnostic_allowance))
            preservation = _plan_metadata(capture, prior, planning_limits, len(captured._state))
            recovery["preservation_plan_id"] = preservation["preservation_plan_id"]
            admission.reconcile(preservation)
            admission.reserve("preservation-plan.json", len(_canonical(preservation)), control=True)
            capacity(len(observation.bindings))
            manifest, controls, metadata_size = _package_metadata(capture, preservation, prior, successor, limits)
            recovery["refresh_id"] = manifest["refresh_id"]
            manifest_hash = _digest(controls["refresh.json"])
            recovery["manifest_sha256"] = manifest_hash
            intent.update(capture_id=capture["capture_id"],
                preservation_plan_id=preservation["preservation_plan_id"], refresh_id=manifest["refresh_id"],
                manifest_sha256=manifest_hash)
            evidence = {"intent.json": {**intent, "parent": placeholders, "package": placeholders},
                "ready.json": _marker("ready", token, placeholders, manifest["refresh_id"], manifest_hash),
                "published.json": _marker("published", token, placeholders, manifest["refresh_id"], manifest_hash)}
            rows, dirs = _physical_rows(manifest, controls, evidence)
            _inventory_bounds(rows, dirs, limits)
            if metadata_size + sum(len(_canonical(v)) for v in evidence.values()) > limits.max_metadata_bytes:
                raise SnapshotLimitError("evidence exceeds aggregate max_metadata_bytes")
            _absolute_paths(rows, dirs, path, package_path, attempt_path, absolute_path_maximum)
            directories = _Directories(stack)
            parent = _parent(directories, path.parent)
            ancestors = tuple((b[2], Path(b[6])) for b in directories.bindings)
            _sibling_aliases(parent, names, limits.max_entries, absent=names)
            source_area = directories.traverse(runtime, private=True)
            objects = directories.open("objects", source_area, private=True, path=runtime / "objects")
            staging = directories.open(".staging", source_area, private=True, path=runtime / ".staging")
            if len({os.fstat(fd).st_dev for fd in (source_area, objects, staging)}) != 1:
                raise ViewLayoutError("source runtime/objects/staging filesystems differ")
            # Retain exact token association before mkdir: a successful allocation
            # followed by an open/check failure must not lose its recovery path.
            recovery.update(attempt_path=str(attempt_path), preparation_path=str(package_path))
            attempt = _create(directories, parent, attempt_path.name, attempt_path)
            _fault("after_attempt_reservation")
            _sibling_aliases(parent, names, limits.max_entries, absent=(package_path.name,))
            package = _create(directories, parent, package_path.name, package_path)
            _fault("after_package_reservation")
            intent.update(parent=list(_identity(os.fstat(parent))), package=list(_identity(os.fstat(package))))
            evidence_pins = {"intent.json": _write_pin(stack, {"": attempt}, "intent.json",
                                                       _canonical(intent).encode("ascii"), 0o400)}
            for fd in (attempt, package, parent):
                os.fsync(fd)
            _fault("after_intent")
            publish = _rename_noreplace()
            tree = {"": package}
            for row in manifest["directories"]:
                relative = row["path"]
                if relative and not relative.startswith("generation/"):
                    tree[relative] = _create(directories, tree[posixpath.dirname(relative)],
                        posixpath.basename(relative), package_path / relative)
            payloads = dict(captured._payloads)
            pins = {}
            for row in preservation["files"]:
                relative = "preservation/" + row["preservation_path"]
                data = prior.manifest_bytes if row["source_path"] is None else payloads[row["source_path"]]
                pins[relative] = _write_pin(stack, tree, relative, data, 0o600)
                _fault("after_preservation_file")
            for relative, data in controls.items():
                pins[relative] = _write_pin(stack, tree, relative, data, 0o400)
            generation, files, inventory, observations, sources, source_ids = _prepare_generation(
                stack, directories, tree["generation"], package_path / "generation", successor, objects, runtime,
                limits.max_entries)
            for relative, fd in generation.items():
                tree["generation" + ("/" + relative if relative else "")] = fd
            _fault("after_successor")
            os.fchmod(package, 0o500)
            modes = {r["path"]: r["mode"] for r in manifest["directories"]}
            physical = [*manifest["files"], dict(path="refresh.json")]
            membership = _members(physical, manifest["directories"])
            prior_ids = {_identity(info) for _, _, _, info, ancestor in observation.bindings
                         if not ancestor and stat.S_ISREG(info.st_mode)}
            def check():
                """Verify all bytes, then conclude with package membership, modes and bindings."""
                observation.check()
                for fd, location in ancestors:
                    _not_layout(fd, location)
                _check_tree(directories, tree, modes, membership, limits.max_entries - len(evidence_pins) - 1)
                identities = prior_ids | source_ids
                _check_pins({**pins, **{"attempt/" + p: pin for p, pin in evidence_pins.items()}}, identities)
                identities |= {_identity(pin[3]) for pin in pins.values()}
                identities |= {_identity(pin[3]) for pin in evidence_pins.values()}
                for relative, reference in files.items():
                    info = observations[relative]
                    if _identity(info) in identities:
                        raise ViewIntegrityError("successor shares an output/prior/source inode")
                    identities.add(_identity(info))
                    with _leaf(generation[posixpath.dirname(relative)], posixpath.basename(relative), relative,
                               mode=0o400, expected=info) as (fd, _):
                        _stream(fd, reference, relative)
                evidence_names = set()
                with os.scandir(attempt) as iterator:
                    for entry in iterator:
                        if entry.name not in evidence_pins:
                            raise ViewIntegrityError("unexpected attempt evidence entry")
                        evidence_names.add(entry.name)
                if evidence_names != set(evidence_pins):
                    raise ViewIntegrityError("attempt evidence inventory changed")
                _source_check(objects, runtime, sources)
                _sibling_aliases(parent, names, limits.max_entries)
                # Held file descriptors can still hash detached bytes after their
                # parent directory ceases to be reachable at the published path.
                _check_tree(directories, tree, modes, membership, limits.max_entries - len(evidence_pins) - 1)
            check()
            for fd in reversed(tuple(tree.values())):
                os.fsync(fd)
            os.fsync(parent)
            _fault("after_complete_package")
            ready = _marker("ready", token, intent["package"], manifest["refresh_id"], manifest_hash)
            evidence_pins["ready.json"] = _write_pin(stack, {"": attempt}, "ready.json", _canonical(ready).encode("ascii"), 0o400)
            os.fsync(attempt)
            _fault("after_ready")
            _fault("before_rename")
            check()
            _sibling_aliases(parent, names, limits.max_entries, absent=(path.name,))
            # One no-follow, same-parent kernel no-replace publication; no retry.
            attempted = True
            recovery["rename_entered"] = True
            try:
                publish(parent, package_path.name, parent, path.name)
            except FileExistsError:
                recovery["collision"] = True
                raise
            for index, binding in enumerate(directories.bindings):
                if binding[2] == package:
                    directories.bindings[index] = (parent, path.name, *binding[2:6], str(path))
                    break
            _fault("after_rename")
            if _present(parent, package_path.name):
                raise ViewIntegrityError("preparation binding remains after publication")
            os.fsync(parent)
            _fault("after_publication_sync")
            published = _marker("published", token, intent["package"], manifest["refresh_id"], manifest_hash)
            evidence_pins["published.json"] = _write_pin(stack, {"": attempt}, "published.json",
                                                        _canonical(published).encode("ascii"), 0o400)
            os.fsync(attempt)
            _fault("after_published")
            check()
        # Successful closes are part of acknowledgment, after all final checks.
    except KeyboardInterrupt as error:
        _attach_recovery(error, recovery)
        raise
    except Exception as error:
        recovery["collision"] = recovery["collision"] or getattr(error, "_readable_collision", False)
        context = f"destination {path}; attempt_path {attempt_path}; package_path {package_path}"
        if attempted:
            reported = ViewOperationalError(context + f": uncertain publication acknowledgment; retained, no rollback/replay: {error}")
        elif isinstance(error, (ViewError, SnapshotLimitError, DomainValidationError, ViewPlanError)):
            reported = type(error)(context + f": {error}")
        else:
            reported = ViewOperationalError(context + f": preparation failed; retained: {error}")
        raise _attach_recovery(reported, recovery) from error
    return RefreshedReadableView(manifest["refresh_id"], str(prior_path), prior.snapshot_id, prior.plan_id,
        capture["capture_id"], preservation["preservation_plan_id"], successor.snapshot_id, successor.plan_id,
        str(path), str(path / "generation"), str(path / "preservation"), str(attempt_path), prior.plan_id == successor.plan_id)


# Import after private shared checks are defined: inspection never calls the writer.
from research_pipeline.view_refresh_inspection import inspect_readable_refresh
