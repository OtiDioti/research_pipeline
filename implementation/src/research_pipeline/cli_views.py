"""Bounded CLI admission and observations for the existing immutable readable-view APIs."""

from contextlib import ExitStack
from dataclasses import asdict
import errno
import hashlib
from pathlib import Path

from research_pipeline import checkout, cli_proposals, vault, view_refresh
from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactLayoutError
from research_pipeline.cli_controls import (
    CliError, _ControlDirectories, causes, path_value, read_config, read_observed_control,
    read_selection, read_readable_limits, source_root,
)
from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotIntegrityError, SnapshotLimitError
from research_pipeline.store import RecordNotFoundError, ReferenceResolutionError, StoreLayoutError
from research_pipeline.view_capture import _not_storage
from research_pipeline.view_plan import ViewPlanError, plan_readable_snapshot, readable_plan_from_manifest

COMMANDS = frozenset(("generate-readable-view", "refresh-readable-view",
                      "inspect-readable-view", "inspect-readable-refresh"))
WRITERS = frozenset(("generate-readable-view", "refresh-readable-view"))
CONTEXT_FIELDS = ("destination", "attempt_path", "snapshot_id", "plan_id", "manifest_sha256",
                  "prior_snapshot_id", "prior_plan_id", "capture_id", "preservation_plan_id",
                  "successor_snapshot_id", "successor_plan_id", "refresh_id", "next_action")


def _ancestors(directories, selected=None, *, initial_preparation=False):
    """Reject recognizable storage/control ancestors, allowing only an exact published generation child."""
    for _, _, fd, _, _, _, location in directories.bindings:
        path = Path(location)
        _not_storage(fd, path, root=path == selected, initial_preparation=initial_preparation)
        cli_proposals.not_proposal(fd, path)
        if path != selected and vault._present(fd, "refresh.json") and selected != path / "generation":
            raise vault.ViewLayoutError("refresh package is not the exact selected generation ancestor")


def _admit(view, paths, plan=None, *, copying=False):
    """Reserve conservative descriptors before traversal, then canonical depth/inventory before API entry.

    This is admission, not a measurement of descriptors actually used. Doubled
    terms cover adapter pins, transient traversal and independent source copies.
    """
    reservation = 64 + 2 * sum(len(path.parts) for path in paths)
    if plan is not None:
        inventory = (*plan.directories, *plan.generated_files, *plan.artifact_copies)
        for item in inventory:
            depth = len(item.relative_path.split("/")) if item.relative_path else 0
            if depth > view["max_depth"]:
                raise SnapshotLimitError("canonical inventory exceeds max_depth")
        reservation += 2 * (len(plan.directories) + len(plan.generated_files) + len(plan.artifact_copies))
        if copying:
            reservation += 2 * len({item.digest for item in plan.artifact_copies})
    if reservation > view["max_open_descriptors"]:
        raise SnapshotLimitError("conservative descriptor reservation exceeds allowance")


def _admit_refresh(arguments, runtime, limits):
    """Bound adapter chains before acquisition under independent nested and outer allowances."""
    baseline = len(arguments.baseline_manifest.parent.parts)
    destination = len(arguments.destination.parent.parts)
    prior = len(arguments.prior_view.parts)
    runtime_count = len(runtime.parts)
    if prior + 1 > limits.capture_limits.max_open_descriptors:
        raise SnapshotLimitError("prior ancestor descriptor allowance exceeded")
    # Destination pins overlap prior, then runtime pins. Store opening traverses
    # runtime independently; common ancestors still consume separate descriptors.
    reservation = 64 + 2 * max(baseline + 1, destination + prior + 1,
                               destination + runtime_count + 2)
    if reservation > limits.max_open_descriptors:
        raise SnapshotLimitError("refresh preflight descriptor reservation exceeds allowance")


def _historical(data, limits):
    """Reconstruct raw canonical historical bytes under independent budgets and the existing 69-level gate."""
    try:
        return readable_plan_from_manifest(data, limits=limits)
    except SnapshotLimitError:
        raise
    except (ViewPlanError, SnapshotIntegrityError, DomainValidationError) as error:
        raise CliError(5, "invalid_input", "Historical manifest is not a canonical readable plan.") from error


def _baseline(arguments, limits, exclusions):
    """Read and pin an independent baseline, separating initial absence from observed mutation."""
    path = arguments.baseline_manifest
    checkout._outside(path, (*exclusions, arguments.prior_view, arguments.destination))
    with ExitStack() as stack:
        directories = _ControlDirectories(stack)
        try:
            parent = directories.traverse(path.parent, private=True, exact=True)
            before = checkout._stat(parent, path.name)
        except checkout.CheckoutIntegrityError:
            raise
        except Exception as error:
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                directories.check()
                raise CliError(3, "missing", "Explicit baseline file or parent is missing.") from error
            raise
        _ancestors(directories)
        maximum = min(arguments.max_manifest_bytes, limits.max_file_bytes, limits.max_total_bytes)
        data, _ = read_observed_control(parent, path.name, path, maximum, modes=(0o400, 0o600), before=before)
        directories.check()
    plan = _historical(data, limits)
    digest = hashlib.sha256(data).hexdigest()
    if digest != arguments.expected_base_manifest_sha256 or plan.plan_id != arguments.expected_base_plan_id:
        raise vault.ViewIntegrityError("independent baseline pins disagree")
    return plan, digest


def _remember(result, context, effects):
    """Retain established return identities immediately, before any subsequent serialization or close."""
    effects["returned"] = True
    for name in CONTEXT_FIELDS:
        if name in result:
            context[name] = result[name]


def _reservation(arguments, snapshot, plan, prior=None, baseline_hash=None):
    """Construct the entire predictable success envelope, using fixed-length tokens only where unallocated."""
    destination = arguments.destination
    refresh = prior is not None
    prefix = view_refresh.ATTEMPT_PREFIX if refresh else ".readable-view-"
    attempt = path_value(str(destination.parent / (prefix + "0" * 32)))
    preparation = path_value(str(destination.parent / (
        (view_refresh.PACKAGE_PREFIX if refresh else ".readable-generation-") + "0" * 32)))
    # Predictable successor paths are admitted early; refresh also checks its
    # complete preservation inventory inside the library before reservation.
    for entry in (*plan.directories, *plan.generated_files, *plan.artifact_copies):
        for root in (destination, preparation):
            path_value(str(root / ("generation" if refresh else "") / entry.relative_path))
    common = dict(destination=str(destination), attempt_path=str(attempt),
                  selection=snapshot["selection"], resolutions=snapshot["resolutions"])
    if not refresh:
        return dict(**common, snapshot_id=plan.snapshot_id, plan_id=plan.plan_id,
                    manifest_sha256=hashlib.sha256(plan.manifest_bytes).hexdigest(),
                    verification="verified_at_materialization")
    return dict(**common, refresh_id="0" * 64, prior_view=str(arguments.prior_view),
                prior_snapshot_id=prior.snapshot_id, prior_plan_id=prior.plan_id,
                capture_id="0" * 64, preservation_plan_id="0" * 64,
                successor_snapshot_id=plan.snapshot_id, successor_plan_id=plan.plan_id,
                successor_path=str(path_value(str(destination / "generation"))),
                preservation_path=str(path_value(str(destination / "preservation"))),
                same_plan=False, verification="verified_at_refresh", baseline_manifest_sha256=baseline_hash)


def _inspect_view(arguments, view, exclusions, context):
    """Pin a bounded manifest admission pass and require the subsequent inspection to match that observation."""
    path = arguments.view
    checkout._outside(path, exclusions)
    _admit(view, (path,))
    with ExitStack() as stack:
        directories = checkout._Directories(stack)
        try:
            area = directories.traverse(path, private=True)
        except Exception as error:
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                raise CliError(3, "missing", "Explicit view root or ancestor is missing.") from error
            raise
        _ancestors(directories, path, initial_preparation=True)
        data, before = read_observed_control(area, "manifest.json", path / "manifest.json",
                            min(arguments.max_manifest_bytes, view["plan_limits"].max_file_bytes,
                                view["plan_limits"].max_total_bytes), modes=(0o400, 0o600))
        # Keep the original observation pinned across the second, independently
        # bounded API pass; equal hashes alone do not conceal a replaced inode.
        stack.enter_context(checkout._leaf(area, "manifest.json", path / "manifest.json",
                            mode=before.st_mode & 0o777, expected=before))
        plan = _historical(data, view["plan_limits"])
        digest = hashlib.sha256(data).hexdigest()
        context.update(snapshot_id=plan.snapshot_id, plan_id=plan.plan_id, manifest_sha256=digest)
        if arguments.expected_plan_id is not None and arguments.expected_plan_id != plan.plan_id:
            raise vault.ViewIntegrityError("expected plan identity disagrees")
        _admit(view, (path,), plan)
        try:
            observed = vault._inspect_readable_view(path, limits=view["plan_limits"], max_entries=view["max_entries"],
                expected_plan_id=plan.plan_id, manifest_maximum=arguments.max_manifest_bytes)
        finally:
            # Mutation remains an integrity failure even if the second pass
            # rejects its enlarged descriptor before reading the extra bytes.
            try:
                current = checkout._stat(area, "manifest.json")
            except FileNotFoundError as error:
                raise vault.ViewIntegrityError("admitted manifest disappeared") from error
            if checkout._signature(current) != checkout._signature(before):
                raise vault.ViewIntegrityError("manifest changed between admission and inspection")
        if ((observed.snapshot_id, observed.plan_id, observed.manifest_sha256)
                != (plan.snapshot_id, plan.plan_id, digest)):
            raise vault.ViewIntegrityError("manifest identity changed between admission and inspection")
        directories.check()
        _ancestors(directories, path, initial_preparation=True)
    return dict(view=str(path), **asdict(observed), historical_acknowledgment="not_established")


def execute(arguments, context, effects):
    """Validate independent controls and boundaries, delegate once, and close all inputs before acknowledgment."""
    from research_pipeline.cli import _destination, _open_store, _result
    command = arguments.command
    source = source_root()
    runtime, roots = read_config(arguments.config, arguments.max_control_bytes)
    checkout._outside(runtime, (source, *roots))  # Lexical only, even for an unavailable offline runtime.
    exclusions = (source, runtime, *roots)
    controls = [arguments.config, arguments.limits]
    if command in WRITERS:
        controls.append(arguments.selection)
    for control in controls:
        checkout._outside(control, exclusions)
    exclusions = (*exclusions, *controls)
    for name in ("destination", "prior_view", "view", "attempt"):
        if hasattr(arguments, name):
            checkout._outside(getattr(arguments, name), exclusions)
    limits = read_readable_limits(arguments.limits, arguments.max_control_bytes, command)
    if command == "refresh-readable-view":
        _admit_refresh(arguments, runtime, limits["refresh_limits"])
    if command == "inspect-readable-view":
        result = _inspect_view(arguments, limits["view_limits"], exclusions, context)
        return _result(command, result, arguments.max_output_bytes), 0
    if command == "inspect-readable-refresh":
        # The existing inspector alone owns strict attempt-token association and
        # paired-package traversal. A short separate ancestor pass adds proposal guards.
        if len(arguments.destination.parent.parts) + 1 > limits["refresh_limits"].max_open_descriptors:
            raise SnapshotLimitError("ancestor descriptor allowance exceeded")
        with ExitStack() as stack:
            directories = checkout._Directories(stack)
            directories.traverse(arguments.destination.parent, private=True, exact=True)
            _ancestors(directories)
            directories.check()
        result = dict(attempt_path=str(arguments.attempt), destination=str(arguments.destination),
            **asdict(view_refresh.inspect_readable_refresh(arguments.attempt, arguments.destination,
                source_root=source, protected_roots=(runtime, *roots, *controls),
                limits=limits["refresh_limits"], expected_refresh_id=arguments.expected_refresh_id)))
        for name in CONTEXT_FIELDS:
            if name in result:
                context[name] = result[name]
        return _result(command, result, arguments.max_output_bytes), 0
    selected = read_selection(arguments.selection, arguments.max_selection_bytes)
    prior = baseline_hash = None
    if command == "refresh-readable-view":
        prior, baseline_hash = _baseline(arguments, limits["refresh_limits"].capture_limits.plan_limits, exclusions)
        controls.append(arguments.baseline_manifest)
        exclusions = (*exclusions, arguments.baseline_manifest)
        checkout._outside(arguments.prior_view, (*exclusions, arguments.destination))
        context.update(prior_snapshot_id=prior.snapshot_id, prior_plan_id=prior.plan_id)
    else:
        _admit(limits["view_limits"], (arguments.destination.parent, runtime))
    with ExitStack() as stack:
        guard_stack = stack.enter_context(ExitStack())
        directories = checkout._Directories(guard_stack)
        _destination(directories, arguments.destination,
                     (*exclusions, *((arguments.prior_view,) if prior else ())))
        _ancestors(directories)
        if prior is not None:
            # Close this admission chain before refresh performs its own nested
            # descriptor accounting; no extra prior pins escape this block.
            with ExitStack() as prior_stack:
                prior_dirs = checkout._Directories(prior_stack)
                try:
                    prior_dirs.traverse(arguments.prior_view, private=True)
                except Exception as error:
                    if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                        raise CliError(3, "missing", "Explicit prior root or ancestor is missing.") from error
                    raise
                _ancestors(prior_dirs, arguments.prior_view)
                prior_dirs.check()
        store = _open_store(stack, directories, runtime)
        captured = store.capture_snapshot(selected, limits=limits["snapshot_limits"])
        plan = plan_readable_snapshot(captured)
        snapshot = captured.to_dict()
        if prior is None:
            _historical(plan.manifest_bytes, limits["view_limits"]["plan_limits"])
            _admit(limits["view_limits"], (arguments.destination.parent, runtime), plan, copying=True)
            context.update(snapshot_id=plan.snapshot_id, plan_id=plan.plan_id,
                           manifest_sha256=hashlib.sha256(plan.manifest_bytes).hexdigest())
        else:
            context.update(successor_snapshot_id=plan.snapshot_id, successor_plan_id=plan.plan_id)
        reserved = _reservation(arguments, snapshot, plan, prior, baseline_hash)
        _result(command, reserved, arguments.max_output_bytes)
        directories.check()
        # The refresh API accounts for its own held chains. Release adapter
        # admission pins before entry rather than adding hidden descriptors.
        guard_stack.close()
        effects["artifacts"] = {entry.digest for entry in plan.artifact_copies}
        effects["begun"] = True
        try:
            if prior is None:
                actual = vault.materialize_readable_view(store, plan, arguments.destination,
                    source_root=source, protected_roots=(*roots, *controls),
                    max_entries=limits["view_limits"]["max_entries"])
            else:
                actual = view_refresh._refresh_readable_view(store, arguments.prior_view, arguments.destination,
                    expected_plan=prior, new_plan=plan, source_root=source,
                    protected_roots=(*roots, *controls), limits=limits["refresh_limits"],
                    absolute_path_maximum=4096)
        except (Exception, KeyboardInterrupt) as error:
            recovery = getattr(error, "_readable_recovery", None)
            if recovery is not None:
                effects["recovery"] = recovery
                context.update({key: value for key, value in recovery.items() if key in CONTEXT_FIELDS})
            raise
        result = asdict(actual)
        _remember(result, context, effects)
        result.update(selection=snapshot["selection"], resolutions=snapshot["resolutions"])
        if prior is not None:
            result["baseline_manifest_sha256"] = baseline_hash
        output = _result(command, result, arguments.max_output_bytes)
    return output, 0


def classify(error, effects):
    """Classify readable operations by established recovery facts, types and chained errno, never prose."""
    recovery = effects.get("recovery", {})
    chain = tuple(causes(error))
    if recovery.get("collision"):
        return CliError(4, "conflict", "An exact destination or reserved sibling is occupied; no overwrite occurred.")
    if effects.get("returned") or recovery.get("rename_entered"):
        return CliError(7, "effects_uncertain", "Publication or acknowledgment is uncertain; retain all evidence.")
    if isinstance(error, KeyboardInterrupt) and effects["begun"] and not recovery:
        return CliError(7, "effects_uncertain", "Interrupted writer has no evidence excluding publication.")
    if isinstance(error, CliError):
        return error
    io_errors = [cause for cause in chain if isinstance(cause, OSError)]
    if any(cause.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE, errno.EEXIST)
           for cause in io_errors):
        return CliError(6, "operational_error", "A filesystem or resource operation failed.")
    if isinstance(error, (vault.ViewIntegrityError, checkout.CheckoutIntegrityError, SnapshotIntegrityError,
                          ArtifactIntegrityError, ArtifactNotFoundError, ReferenceResolutionError)):
        return CliError(6, "integrity_error", "Canonical content, independent pins or observed bindings disagree.")
    if any(isinstance(cause, FileNotFoundError) and cause.filename is not None
           and Path(str(cause.filename)).name in effects.get("artifacts", ()) for cause in chain):
        return CliError(6, "integrity_error", "A required canonical artifact is missing.")
    if isinstance(error, RecordNotFoundError):
        return CliError(3, "missing", "An explicitly selected record is missing.")
    if isinstance(error, SnapshotLimitError):
        return CliError(5, "limit_exceeded", "An independently selected allowance was exceeded.")
    if isinstance(error, (DomainValidationError, ViewPlanError)):
        return CliError(5, "invalid_input", "A control or historical manifest is invalid.")
    if any(isinstance(cause, FileExistsError) for cause in chain):
        return CliError(4, "conflict", "An explicitly absent destination or reservation is occupied.")
    if io_errors or isinstance(error, (vault.ViewLayoutError, checkout.CheckoutLayoutError, StoreLayoutError, ArtifactLayoutError)):
        return CliError(5, "unsafe_layout", "A required internal path or control layout is missing or unsafe.")
    return CliError(6, "operational_error", "The operation failed without complete acknowledgment.")


def guidance(command, failure):
    """Return fixed bounded recovery instructions referring to exact diagnostic fields, never inferred facts."""
    if command == "inspect-readable-refresh" and failure.code == "output_failed":
        return ("Repeat inspect-readable-refresh with the same exact attempt_path and destination, and "
                "--expected-refresh-id refresh_id when known. Discard partial output; retain all evidence.")
    if command in ("refresh-readable-view", "inspect-readable-refresh"):
        return ("Use inspect-readable-refresh --config FILE --limits FILE with attempt_path and destination "
                "from this diagnostic, and --expected-refresh-id refresh_id when known. Retain all evidence. "
                "No replay, cleanup or rollback; a new destination does not reconcile this attempt.")
    if command == "inspect-readable-view":
        return "Repeat inspect-readable-view with the same explicit destination as --view; discard partial output."
    return ("Use inspect-readable-view --config FILE --limits FILE --view destination, or the paired preparation "
            "sibling .readable-generation-TOKEN where attempt_path is .readable-view-TOKEN. Retain attempt evidence "
            "for manual association. Incomplete payloads may not be inspectable. Inspection cannot establish historical "
            "publication acknowledgment. No automatic retry or rollback; a new destination does not reconcile this attempt.")
