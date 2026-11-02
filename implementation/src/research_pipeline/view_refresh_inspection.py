"""Read-only current-state inspection of token-paired refresh observations and packages."""

from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import posixpath
import re
import stat

from research_pipeline.checkout import CheckoutIntegrityError, _Directories, _path, _outside, _identity, _signature
from research_pipeline.domain import ArtifactReference, DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError, SnapshotIntegrityError, _canonical, _strict_json
from research_pipeline.vault import (
    ViewDifference, ViewIntegrityError, ViewLayoutError, _boundary, _parent,
    _safe_directory, _safe_file, _inspect_open, _inspect_bytes, _present,
)
from research_pipeline.view_capture import _validated_metadata, _fields, _digest, _Metadata, _binding_stat
from research_pipeline.view_plan import readable_plan_from_manifest, ViewPlanError
from research_pipeline.view_preservation import _plan_metadata
from research_pipeline.view_refresh_metadata import (
    RefreshLimits, RefreshInspection, _limits_value, _package_metadata, _relationships, ATTEMPT_LIMITATIONS,
)
from research_pipeline.work_product import _path as _portable_path


class _IdentityMismatch(Exception):
    """Keep an independent caller identity mismatch outside ordinary divergence classification."""


class _Reader:
    """Bound each acquisition/read and retain original descriptors for a final inspection gate."""

    def __init__(self, stack, directories, limits):
        """Share one descriptor/physical/metadata budget across package and evidence traversal."""
        self.stack, self.directories, self.limits = stack, directories, limits
        self.pins, self.tree, self.modes, self.inventory = {}, {}, {}, {}
        self.files, self.count, self.total = 0, 0, 0
        self.metadata = _Metadata(limits.max_metadata_bytes)
        self.names_metadata = _Metadata(limits.max_metadata_bytes)
        self.directory_ids = set()
        self.directory_pins = {}

    def capacity(self, extra=1):
        """Check aggregate retained plus temporary descriptors before acquisition."""
        if len(self.directories.bindings) + len(self.pins) + extra > self.limits.max_open_descriptors:
            raise SnapshotLimitError("max_open_descriptors exceeded during inspection")

    def names(self, fd):
        """Bound one aggregate enumeration pass before retaining each safe portable name."""
        self.capacity()
        names, aliases = [], set()
        with os.scandir(fd) as iterator:
            for entry in iterator:
                if self.count >= self.limits.max_entries:
                    raise SnapshotLimitError("max_entries exceeded during inspection")
                self.count += 1
                try:
                    key = _portable_path(entry.name, "inspection child")
                except DomainValidationError as error:
                    raise ViewLayoutError("unsafe inspection child") from error
                if len(key) != 1 or key in aliases or len(entry.name.encode("utf-8")) > 240:
                    raise ViewLayoutError("aliased/oversized inspection child")
                aliases.add(key)
                self.names_metadata.reserve(self.names_metadata.size(entry.name))
                names.append(entry.name)
        return sorted(names)

    def directory(self, parent, name, path, key):
        """Pin a safe private directory, charging root and descendants before opens."""
        if len(self.tree) >= self.limits.max_directories:
            raise SnapshotLimitError("max_directories exceeded")
        self.capacity()
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if key.startswith("package/") and info.st_dev != os.fstat(self.tree["package"]).st_dev:
            raise ViewLayoutError("cross-device package subtree")
        if _identity(info) in self.directory_ids:
            raise ViewLayoutError("repeated package directory inode")
        if not _safe_directory(info):
            raise ViewLayoutError(f"unsafe inspection directory: {path}")
        fd = self.directories.open(name, parent, private=True, path=path)
        if _signature(os.fstat(fd)) != _signature(info):
            raise ViewIntegrityError(f"inspection directory changed during open: {path}")
        if key == "attempt":
            self.count += 1
            if self.count > self.limits.max_entries:
                raise SnapshotLimitError("max_entries exceeded")
        self.directory_ids.add(_identity(info))
        self.tree[key] = fd
        self.modes[key] = stat.S_IMODE(info.st_mode)
        self.directory_pins[key] = (parent, name, fd, info)
        return fd

    def file(self, parent, name, key, *, retain):
        """Charge physical/control bytes and independent capture limits before opening or retention."""
        from research_pipeline.view_refresh import _relative
        _relative(key.removeprefix("package/"), self.limits)
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if info.st_dev != os.fstat(parent).st_dev:
            raise ViewLayoutError("cross-device package file")
        if not _safe_file(info):
            raise ViewLayoutError(f"unsafe inspection file: {key}")
        if self.files >= self.limits.max_files:
            raise SnapshotLimitError("max_files exceeded")
        if info.st_size > self.limits.max_file_bytes or self.total + info.st_size > self.limits.max_total_bytes:
            raise SnapshotLimitError("inspection physical byte allowance exceeded")
        self.files += 1
        self.total += info.st_size
        if (key == "package/capture.json"
                and info.st_size > self.limits.capture_limits.max_metadata_bytes):
            raise SnapshotLimitError("capture text exceeds independent max_metadata_bytes")
        if retain or key == "package/preservation/controls/observed-manifest.bin":
            self.metadata.reserve(info.st_size)
        self.capacity()
        fd = _inspect_open(self.stack, parent, name, info, key)
        digest, data = _inspect_bytes(fd, info, key, retain=retain)
        self.pins[key] = (parent, name, fd, info, ArtifactReference(digest, info.st_size))
        return data

    def walk_package(self, root, path):
        """Observe bounded package entries, rejecting directories at fixed control-file paths.

        Retain parsed controls only; observed-manifest and authored bytes remain
        opaque. Unwritten controls are allowed, but present entries must be files.
        """
        from research_pipeline.view_refresh import _relative
        retained, pending = {}, [("package", root, "")]
        controls = {"refresh.json", "capture.json", "preservation-plan.json", "README.md",
                    "generation/manifest.json", "preservation/controls/expected-manifest.json"}
        control_files = controls | {"preservation/controls/observed-manifest.bin"}
        while pending:
            key, fd, relative = pending.pop()
            names = self.names(fd)
            self.inventory[key] = set(names)
            for name in names:
                child = posixpath.join(relative, name)
                _relative(child, self.limits)
                child_key = "package/" + child
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child_fd = self.directory(fd, name, path / child, child_key)
                    if child in control_files:
                        raise ViewIntegrityError(f"directory occupies control-file path: {child}")
                    pending.append((child_key, child_fd, child))
                else:
                    data = self.file(fd, name, child_key, retain=child in controls)
                    if child in controls:
                        retained[child] = data
        return retained

    def check(self):
        """Conclude reads with exact memberships and original full in-package binding signatures."""
        from research_pipeline.view_refresh import _check_pins, _check_tree
        self.capacity()
        self.check_directories()
        _check_tree(self.directories, self.tree, self.modes, self.inventory, self.limits.max_entries - 1)
        _check_pins(self.pins)
        # No close callback is a consistency gate. Verify membership after reads,
        # then sweep every retained signature without imposing sibling stability
        # on external ancestors.
        self.check_directories()
        _check_tree(self.directories, self.tree, self.modes, self.inventory, self.limits.max_entries - 1)
        self.check_directories()
        for key, (parent, name, fd, original, _) in self.pins.items():
            if (_signature(_binding_stat(parent, name)) != _signature(original)
                    or _signature(os.fstat(fd)) != _signature(original)):
                raise ViewIntegrityError(f"inspection file changed: {key}")

    def check_directories(self):
        """Detect ordinary mutations/rebindings of the attempt and package, excluding ancestors."""
        for key, (parent, name, fd, original) in self.directory_pins.items():
            if (_signature(_binding_stat(parent, name)) != _signature(original)
                    or _signature(os.fstat(fd)) != _signature(original)):
                raise ViewIntegrityError(f"inspection directory changed: {key}")


def _json(data):
    """Require exact canonical ASCII JSON, bounded nesting and duplicate-key rejection."""
    try:
        text = data.decode("ascii")
        value = _strict_json(text, maximum_depth=80)
        if _canonical(value) != text:
            raise ViewIntegrityError("noncanonical refresh control bytes")
        return value
    except (UnicodeError, SnapshotIntegrityError) as error:
        raise ViewIntegrityError("malformed refresh JSON") from error


def _pair(value):
    """Validate an ordinary nonnegative device/inode pair from filesystem observation metadata."""
    if type(value) is not list or len(value) != 2:
        raise ViewIntegrityError("invalid filesystem identity pair")
    for number in value:
        if type(number) is not int or not 0 <= number <= 2**64 - 1:
            raise ViewIntegrityError("invalid filesystem identity integer")


def _intent(data, token, destination, package_name, parent):
    """Validate exact caller-bound evidence; never turn metadata names into traversal targets."""
    value = _json(data)
    _fields(value, ("format", "version", "token", "destination", "package_name", "parent", "package",
                   "prior_plan_id", "successor_plan_id", "capture_id", "preservation_plan_id", "refresh_id",
                   "manifest_sha256", "limitations"), "refresh intent")
    _pair(value["parent"])
    _pair(value["package"])
    if (value["format"] != "research_pipeline.readable_refresh_attempt" or type(value["version"]) is not int
            or value["version"] != 1 or value["token"] != token or value["destination"] != destination
            or value["package_name"] != package_name or value["parent"] != list(_identity(os.fstat(parent)))
            or value["limitations"] != list(ATTEMPT_LIMITATIONS)):
        raise ViewIntegrityError("intent does not match explicit locations/schema")
    for name in ("prior_plan_id", "successor_plan_id", "capture_id", "preservation_plan_id", "refresh_id", "manifest_sha256"):
        ArtifactReference(value[name], 0)
    return value


def _available_controls(reader, controls, intent, limits):
    """Validate present controls and their dependencies without inventing unwritten payloads.

    Capture precedes the preservation plan. Successor construction follows all
    top-level controls, so its manifest may legitimately still be absent.
    """
    from research_pipeline.view_refresh_controls import _refresh_control
    prior = successor = capture = preservation = manifest = None
    expected_path = "preservation/controls/expected-manifest.json"
    if expected_path in controls:
        prior = readable_plan_from_manifest(controls[expected_path], limits=limits.capture_limits.plan_limits)
        if prior.plan_id != intent["prior_plan_id"]:
            raise ViewIntegrityError("independent prior plan differs from intent")
    if "generation/manifest.json" in controls:
        successor = readable_plan_from_manifest(controls["generation/manifest.json"], limits=limits.successor_limits)
        if successor.plan_id != intent["successor_plan_id"]:
            raise ViewIntegrityError("successor plan differs from intent")
    if "capture.json" in controls:
        _json(controls["capture.json"])
        capture_text = controls["capture.json"].decode("ascii")
        capture, captured_prior, capture_limits = _validated_metadata(capture_text, limits.capture_limits)
        if (capture["capture_id"] != intent["capture_id"] or captured_prior.plan_id != intent["prior_plan_id"]
                or prior is not None and prior.manifest_bytes != captured_prior.manifest_bytes):
            raise ViewIntegrityError("capture/expected manifest differs from intent or retained prior")
        prior = captured_prior
        allowance = limits.max_diagnostics
        if successor is not None:
            _, mappings = _relationships(prior, successor, limits.max_diagnostics)
            allowance -= len(mappings)
        if allowance < 1:
            raise SnapshotLimitError("max_diagnostics cannot cover preservation comparisons")
        planning_limits = replace(capture_limits,
            max_metadata_bytes=min(capture_limits.max_metadata_bytes, limits.max_metadata_bytes),
            max_diagnostics=min(capture_limits.max_diagnostics, allowance))
        preservation = _plan_metadata(capture, prior, planning_limits, len(capture_text))
        if preservation["preservation_plan_id"] != intent["preservation_plan_id"]:
            raise ViewIntegrityError("deterministic preservation differs from intent")
    if "preservation-plan.json" in controls:
        if preservation is None:
            raise ViewIntegrityError("preservation plan precedes capture control")
        if _canonical(_json(controls["preservation-plan.json"])) != _canonical(preservation):
            raise ViewIntegrityError("contradictory preservation plan")
    if prior is not None and successor is not None:
        _relationships(prior, successor, limits.max_diagnostics)
    if "refresh.json" in controls:
        manifest = _refresh_control(_json(controls["refresh.json"]), controls["refresh.json"], intent, reader, limits)
        for side, plan in (("prior", prior), ("successor", successor)):
            if plan is not None:
                document = plan.to_dict()
                expected = dict(plan_id=plan.plan_id, snapshot_id=plan.snapshot_id,
                                manifest_sha256=_digest(plan.manifest_bytes))
                if (any(manifest[side][k] != v for k, v in expected.items())
                        or manifest["selection"][side + "_requested"] != document["selection"]
                        or manifest["selection"][side + "_resolutions"] != document["resolutions"]):
                    raise ViewIntegrityError("refresh descriptor contradicts available canonical plan")
                expected_pages = {(row["record_id"], row["revision"]): row["page_path"] for row in document["records"]}
                observed_pages = {(row["record_id"], row["revision"]): row[side + "_page_path"]
                                  for row in manifest["records"] if row[side + "_page_path"] is not None}
                if observed_pages != expected_pages:
                    raise ViewIntegrityError("refresh record mappings contradict available canonical plan")
        if capture is not None and manifest["prior"]["path"] != capture["prior_view"]:
            raise ViewIntegrityError("refresh prior location contradicts capture")
    if capture is None or successor is None:
        return None
    manifest, expected_controls, metadata_size = _package_metadata(capture, preservation, prior, successor, limits)
    from research_pipeline.view_refresh import _physical_rows, _inventory_bounds, _marker
    possible_evidence = {"intent.json": intent,
        "ready.json": _marker("ready", intent["token"], intent["package"], intent["refresh_id"], intent["manifest_sha256"]),
        "published.json": _marker("published", intent["token"], intent["package"], intent["refresh_id"], intent["manifest_sha256"])}
    files, directories = _physical_rows(manifest, expected_controls, possible_evidence)
    _inventory_bounds(files, directories, limits)
    if metadata_size + sum(len(_canonical(value)) for value in possible_evidence.values()) > limits.max_metadata_bytes:
        raise SnapshotLimitError("aggregate inspection metadata exceeds max_metadata_bytes")
    for path, data in expected_controls.items():
        if path in controls and controls[path] != data:
            raise ViewIntegrityError(f"noncanonical or contradictory package control: {path}")
    if (intent["refresh_id"] != manifest["refresh_id"]
            or intent["manifest_sha256"] != _digest(expected_controls["refresh.json"])):
        raise ViewIntegrityError("intent/package association mismatch")
    return manifest


def _complete(reader, controls, intent, limits):
    """Require all deterministic controls plus exact complete file/directory inventories."""
    required = ("refresh.json", "capture.json", "preservation-plan.json", "README.md", "generation/manifest.json",
                "preservation/controls/expected-manifest.json")
    if any(p not in controls for p in required):
        raise ViewIntegrityError("incomplete package controls")
    manifest = _available_controls(reader, controls, intent, limits)
    expected_files = {r["path"]: (r["sha256"], r["size"], r["mode"]) for r in manifest["files"]}
    expected_files["refresh.json"] = (_digest(controls["refresh.json"]), len(controls["refresh.json"]), 0o400)
    observed_files = {key.removeprefix("package/"): (pin[4].digest, pin[4].size, stat.S_IMODE(pin[3].st_mode))
                      for key, pin in reader.pins.items() if key.startswith("package/")}
    if expected_files != observed_files:
        raise ViewIntegrityError("package file inventory/bytes/modes disagree")
    expected_dirs = {r["path"]: r["mode"] for r in manifest["directories"]}
    observed_dirs = {("" if k == "package" else k.removeprefix("package/")): v
                     for k, v in reader.modes.items() if k == "package" or k.startswith("package/")}
    if expected_dirs != observed_dirs:
        raise ViewIntegrityError("package directory inventory/modes disagree")
    # The complete reconstructed generation includes every generated byte and
    # artifact hash. No unchanged prior payload is fabricated or required here.
    return manifest["refresh_id"]


def inspect_readable_refresh(attempt_path, destination, *, source_root, protected_roots,
                             limits: RefreshLimits, expected_refresh_id: str | None = None) -> RefreshInspection:
    """Classify retained observations without store/prior access, writes, recovery or historical claims.

    Only caller paths and the fixed token-paired preparation sibling are opened.
    A competing destination is lstat-only; it is never traversed or exposed as this
    attempt's successor. Stored budgets cannot increase independent caller limits.
    """
    return _inspect_or_recover_refresh(attempt_path, destination, source_root=source_root,
        protected_roots=protected_roots, limits=limits, expected_refresh_id=expected_refresh_id)


def _inspect_or_recover_refresh(attempt_path, destination, *, source_root, protected_roots,
                                limits, expected_refresh_id=None, recover=False):
    """Share strict offline acquisition while retaining all descriptors through optional recovery."""
    from research_pipeline.view_refresh import ATTEMPT_PREFIX, PACKAGE_PREFIX, _locations, _marker, _sibling_aliases
    limits = _limits_value(limits)
    if expected_refresh_id is not None:
        ArtifactReference(expected_refresh_id, 0)
    with _boundary(destination):
        path, exclusions = _locations(destination, source_root, protected_roots, limits)
        attempt = _path(attempt_path)
        if attempt.parent != path.parent or not re.fullmatch(re.escape(ATTEMPT_PREFIX) + "[0-9a-f]{32}", attempt.name):
            raise ViewLayoutError("attempt must be the strict token-paired sibling of destination")
        token = attempt.name[len(ATTEMPT_PREFIX):]
        package = path.parent / (PACKAGE_PREFIX + token)
        for reserved in (attempt, package):
            _outside(reserved, exclusions)
        if len(path.parent.parts) + 1 > limits.max_open_descriptors:
            raise SnapshotLimitError("max_open_descriptors exceeded before ancestor traversal")
        with ExitStack() as stack:
            directories = _Directories(stack)
            parent = _parent(directories, path.parent)
            # Parent collision scans have their own finite allowance, independent
            # of package traversal. Exact caller bindings are permitted here.
            _sibling_aliases(parent, (path.name, attempt.name, package.name), limits.max_entries)
            reader = _Reader(stack, directories, limits)
            status, identity, verified, differences = "incomplete_preparation", None, None, ()
            readiness = publication = "absent"
            if not _present(parent, attempt.name):
                directories.check()
                stack.close()
                if recover:
                    raise ViewIntegrityError("missing attempt cannot be recovered")
                return RefreshInspection(status, None, None, None, None, readiness, publication, "not_established", ())
            attempt_fd = reader.directory(parent, attempt.name, attempt, "attempt")
            names = reader.names(attempt_fd)
            reader.inventory["attempt"] = set(names)
            readiness = "present" if "ready.json" in names else "absent"
            publication = "present" if "published.json" in names else "absent"
            evidence, bindings = {}, None
            for name in names:
                info = os.stat(name, dir_fd=attempt_fd, follow_symlinks=False)
                if not _safe_file(info):
                    raise ViewLayoutError("unsafe attempt evidence")
                evidence[name] = reader.file(attempt_fd, name, "attempt/" + name, retain=True)
            try:
                if reader.modes["attempt"] != 0o700 or any(stat.S_IMODE(pin[3].st_mode) != 0o400 for pin in reader.pins.values()):
                    raise ViewIntegrityError("attempt evidence modes disagree")
                if _present(parent, package.name):
                    info = os.stat(package.name, dir_fd=parent, follow_symlinks=False)
                    if not _safe_directory(info):
                        raise ViewLayoutError("unsafe preparation binding")
                if set(names) - {"intent.json", "ready.json", "published.json"}:
                    raise ViewIntegrityError("unexpected attempt entry")
                if "intent.json" not in evidence:
                    if names:
                        raise ViewIntegrityError("markers without intent")
                else:
                    intent = _intent(evidence["intent.json"], token, path.name, package.name, parent)
                    identity = intent["refresh_id"]
                    if expected_refresh_id is not None and identity != expected_refresh_id:
                        raise _IdentityMismatch("independent expected_refresh_id mismatch")
                    for marker in ("ready", "published"):
                        name = marker + ".json"
                        if name in evidence and _canonical(_json(evidence[name])) != _canonical(_marker(
                                marker, token, intent["package"], identity, intent["manifest_sha256"])):
                            raise ViewIntegrityError("contradictory refresh marker")
                    if publication == "present" and readiness != "present":
                        raise ViewIntegrityError("impossible publication marker ordering")
                    bindings = {}
                    for label, candidate in (("preparation", package), ("destination", path)):
                        if _present(parent, candidate.name):
                            bindings[label] = os.stat(candidate.name, dir_fd=parent, follow_symlinks=False)
                    own = [label for label, info in bindings.items() if list(_identity(info)) == intent["package"]]
                    if len(own) != 1:
                        raise ViewIntegrityError("recorded package missing or conflicting bindings")
                    location = own[0]
                    if location == "destination" and "preparation" in bindings:
                        raise ViewIntegrityError("preparation binding remains beside published package")
                    if location == "preparation" and publication == "present":
                        raise ViewIntegrityError("published marker with unpublished binding")
                    current = path if location == "destination" else package
                    root = reader.directory(parent, current.name, current, "package")
                    controls = reader.walk_package(root, current)
                    # A visibly unfinished private preparation can be reported as
                    # incomplete only before readiness, never as a verified successor.
                    if location == "preparation" and reader.modes["package"] == 0o700 and readiness == "absent":
                        status = "competing_destination" if "destination" in bindings else "incomplete_preparation"
                        _available_controls(reader, controls, intent, limits)
                    else:
                        identity = _complete(reader, controls, intent, limits)
                        verified = str(current)
                        status = ("published" if location == "destination" else
                                  "competing_destination" if "destination" in bindings else "complete_unpublished")
                reader.check()
                _sibling_aliases(parent, (path.name, attempt.name, package.name), limits.max_entries)
                if bindings is not None:
                    for label, candidate in (("preparation", package), ("destination", path)):
                        present = _present(parent, candidate.name)
                        if present != (label in bindings):
                            raise ViewIntegrityError("package/destination presence changed during inspection")
                        if present:
                            current = os.stat(candidate.name, dir_fd=parent, follow_symlinks=False)
                            if _identity(current) != _identity(bindings[label]) or current.st_mode != bindings[label].st_mode:
                                raise ViewIntegrityError("package/destination binding changed during inspection")
            except _IdentityMismatch as error:
                raise ViewIntegrityError(str(error)) from error
            except SnapshotLimitError:
                raise
            except (CheckoutIntegrityError, ViewIntegrityError, ViewPlanError, SnapshotIntegrityError, DomainValidationError,
                    KeyError, TypeError, UnicodeError, ValueError) as error:
                # Operational and budget/layout failures deliberately escape.
                status, identity, verified = "inconsistent", None, None
                detail = str(error)
                # Diagnostic bookkeeping is transient, not another serialized
                # control copy. Exact control-budget equality must still permit
                # reporting an observed mutation as inconsistent.
                reader.names_metadata.reserve(reader.names_metadata.size(detail))
                if limits.max_diagnostics < 1:
                    raise SnapshotLimitError("max_diagnostics exceeded") from error
                differences = (ViewDifference("", "inconsistent", detail),)
            if expected_refresh_id is not None and identity is not None and identity != expected_refresh_id:
                raise ViewIntegrityError("independent expected_refresh_id mismatch")
            if recover:
                if status not in ("complete_unpublished", "published"):
                    raise ViewIntegrityError("refresh attempt cannot be recovered: " + status)
                return _recover_payload(reader, parent, attempt, path, package, intent, controls, status, stack)
            result = RefreshInspection(status, identity, verified,
                str(Path(verified) / "generation") if verified else None,
                str(Path(verified) / "preservation") if verified else None,
                readiness, publication, "not_established", differences)
        return result


def _recover_payload(reader, parent, attempt, destination, preparation, intent, controls, status, stack):
    """Reestablish current durability of a complete frozen package, then publish without replacement.

    Preservation remains byte-for-byte frozen; neither the prior view nor source
    artifacts are opened. Rebind only the root inode moved by the kernel. Checked
    closes are part of this new acknowledgment, never evidence of an old one.
    """
    from research_pipeline.view_refresh import _write_pin, _marker, _fault, _sibling_aliases
    from research_pipeline.view_refresh_metadata import RefreshedReadableView
    from research_pipeline.vault import _rename_noreplace, _not_layout, ViewOperationalError
    entered = status == "published"
    afd, package = reader.tree["attempt"], reader.tree["package"]
    token = intent["token"]
    manifest = _json(controls["refresh.json"])
    ancestors = tuple((binding[2], Path(binding[6])) for binding in reader.directories.bindings
                      if binding[2] not in reader.tree.values())

    def check():
        """Verify bytes and original signatures, including absent preparation and competing siblings."""
        reader.check()
        for fd, location in ancestors:
            _not_layout(fd, location)
        _sibling_aliases(parent, (attempt.name, destination.name, preparation.name), reader.limits.max_entries)
        if entered:
            if _present(parent, preparation.name):
                raise ViewIntegrityError("preparation binding remains beside published package")
        elif _present(parent, destination.name):
            raise ViewIntegrityError("competing destination during refresh recovery")

    def append_marker(name):
        """Append only a missing verified marker and update this operation's expected directory change."""
        key = "attempt/" + name + ".json"
        if key in reader.pins:
            return
        check()
        data = _canonical(_marker(name, token, intent["package"], intent["refresh_id"], intent["manifest_sha256"])).encode("ascii")
        # _available_controls preflights the complete inventory including both markers.
        reader.capacity()
        reader.pins[key] = _write_pin(reader.stack, {"": afd}, name + ".json", data, 0o400)
        reader.inventory["attempt"].add(name + ".json")
        owner, leaf, fd, _ = reader.directory_pins["attempt"]
        reader.directory_pins["attempt"] = (owner, leaf, fd, os.fstat(fd))
        os.fsync(afd)

    try:
        check()
        for _, _, fd, _, _ in reader.pins.values():
            os.fsync(fd)
        for fd in reversed(tuple(reader.tree.values())):
            os.fsync(fd)
        os.fsync(parent)
        check()
        append_marker("ready")
        if not entered:
            _fault("before_rename")
            check()
            _sibling_aliases(parent, (attempt.name, destination.name, preparation.name), reader.limits.max_entries,
                             absent=(destination.name,))
            publish = _rename_noreplace()
            entered = True
            publish(parent, preparation.name, parent, destination.name)
            for index, binding in enumerate(reader.directories.bindings):
                if binding[2] == package:
                    reader.directories.bindings[index] = (parent, destination.name, *binding[2:6], str(destination))
                    break
            reader.directory_pins["package"] = (parent, destination.name, package, os.fstat(package))
            _fault("after_rename")
        check()
        os.fsync(parent)
        _fault("after_publication_sync")
        append_marker("published")
        _fault("after_published")
        check()
        stack.close()
    except KeyboardInterrupt as error:
        from research_pipeline.vault import _attach_recovery
        _attach_recovery(error, dict(attempt_path=str(attempt), destination=str(destination),
            refresh_id=intent["refresh_id"], rename_entered=entered))
        raise
    except Exception as error:
        if entered:
            raise ViewOperationalError(f"uncertain refresh recovery acknowledgment; retain {attempt} and {destination}: {error}") from error
        raise
    return RefreshedReadableView(manifest["refresh_id"], manifest["prior"]["path"],
        manifest["prior"]["snapshot_id"], manifest["prior"]["plan_id"], manifest["capture"]["capture_id"],
        manifest["preservation"]["preservation_plan_id"], manifest["successor"]["snapshot_id"],
        manifest["successor"]["plan_id"], str(destination), str(destination / "generation"),
        str(destination / "preservation"), str(attempt), manifest["same_plan"], "verified_at_recovery")


def recover_readable_refresh(attempt_path, destination, *, source_root, protected_roots,
                             limits: RefreshLimits, expected_refresh_id: str | None = None):
    """Explicitly recover the exact complete retained refresh package without recapturing prior edits.

    Incomplete, inconsistent and competing attempts fail without repair. Current
    bytes, controls, modes, identities and durability barriers must all verify;
    successful checked closes establish a new acknowledgment only.
    """
    return _inspect_or_recover_refresh(attempt_path, destination, source_root=source_root,
        protected_roots=protected_roots, limits=limits, expected_refresh_id=expected_refresh_id, recover=True)
