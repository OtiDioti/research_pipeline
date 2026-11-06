"""Bounded metadata-only CLI views of current claim uses and generation history.

The public store APIs own snapshot semantics and complete domain documents. This
adapter owns explicit argv accounts, held controls and read-only acknowledgement.
"""

from contextlib import ExitStack
import errno

from research_pipeline import checkout, vault
from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactLayoutError
from research_pipeline.claim_use import ClaimUseInspectionLimits, ClaimUseIntegrityError, ClaimUseLimitError
from research_pipeline.cli_controls import (
    CliError, _ObservedDirectories, _ancestors, _check, _config_value, _read_control,
    causes, path_value, source_root, strict_json,
)
from research_pipeline.domain import DomainValidationError, _identifier
from research_pipeline.resources import ResourceIntegrityError
from research_pipeline.snapshot import SnapshotIntegrityError, SnapshotLimitError
from research_pipeline.store import RecordNotFoundError, ReferenceResolutionError, StoreLayoutError

COMMANDS = frozenset(("inspect-claim-use", "inspect-claim-use-history"))
CONTEXT_FIELDS = ("config", "use_id", "after_generation", "page_limit", "next_action")
INSPECTION_FIELDS = ("max_bindings", "max_records", "max_references", "max_assertion_revisions",
                     "max_metadata_bytes", "max_result_bytes")
LIMITS = {
    "max_bindings": (512, 1, 512, "exact binding nodes"),
    "max_records": (1024, 1, 1024, "required metadata records"),
    "max_references": (8192, 1, 8192, "reference occurrences"),
    "max_assertion_revisions": (1024, 1, 1024, "relevant assertion revisions"),
    "max_metadata_bytes": (67108864, 1, 67108864, "Reader metadata/work reservation bytes, including repetitions"),
    "max_result_bytes": (4194304, 1, 4194304, "complete canonical ASCII domain bytes excluding CLI framing/LF"),
    "max_control_bytes": (65536, 1, 1048576, "actual UTF-8 config bytes including whitespace"),
    "max_output_bytes": (8388608, 1, 16777216, "complete canonical ASCII CLI bytes including framing/LF"),
}
HISTORY_SELECTIONS = {
    "after_generation": (0, 0, 9223372036854775807, "exclusive generation cursor"),
    "page_limit": (256, 1, 256, "transitions per page; no automatic pagination"),
}
DESCRIPTIONS = {
    "inspect-claim-use": (
        "Inspect a coherent current operational claim-use snapshot over immutable scientific pins. "
        "Metadata-only; no historical attachment verification, positive eligibility or authority. "
        "Research execution is unavailable."),
    "inspect-claim-use-history": (
        "Inspect one complete metadata-only generation-history page for a registered claim use. "
        "Follow next_cursor explicitly; no historical attachment verification or scientific certification. "
        "Research execution is unavailable."),
}


def specifications(command):
    """Return independent command-specific numeric contracts, adding cursors only for history."""
    return {**LIMITS, **(HISTORY_SELECTIONS if command == "inspect-claim-use-history" else {})}


def validate(arguments, context):
    """Validate all argv before controls, retaining only established diagnostic selections."""
    from research_pipeline.cli import _number

    if context is None:
        context = dict.fromkeys(CONTEXT_FIELDS)
    arguments.config = path_value(arguments.config)
    context["config"] = str(arguments.config)
    _identifier(arguments.use_id, "use_id")
    context["use_id"] = arguments.use_id
    for name, (_, minimum, maximum, _) in specifications(arguments.command).items():
        value = _number(getattr(arguments, name), minimum, maximum)
        setattr(arguments, name, value)
        if name in HISTORY_SELECTIONS:
            context[name] = value


def execute(arguments, context, effects):
    """Hold config/runtime observations until store and descriptor closes precede prepared output.

    Every established observation is rechecked even if a later acquisition fails.
    No submission or publication effects are entered by either read operation.
    """
    from research_pipeline.cli import _open_store, _result

    source = source_root()
    observations = []
    with ExitStack() as pins:
        directories = _ObservedDirectories(pins)
        try:
            config = _read_control(directories, observations, arguments.config,
                                   arguments.max_control_bytes, config=True)
            try:
                runtime, roots = _config_value(strict_json(config))
            except SnapshotIntegrityError as error:
                raise CliError(5, "invalid_input", "Configuration nesting exceeds the control ceiling.") from error
            checkout._outside(runtime, (source, *roots))
            checkout._outside(arguments.config, (source, runtime, *roots))
            with ExitStack() as store_stack:
                try:
                    directories.traverse(runtime, private=True)
                except Exception as error:
                    _check(directories, observations)
                    if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                        raise CliError(3, "missing", "Explicit runtime is missing; no store was created.") from error
                    raise
                _ancestors(directories, runtime)
                store = _open_store(store_stack, directories, runtime)
                _ancestors(directories, runtime)
                limits = ClaimUseInspectionLimits(**{name: getattr(arguments, name) for name in INSPECTION_FIELDS})
                result = dict(store=str(runtime), use_id=arguments.use_id)
                history = arguments.command == "inspect-claim-use-history"
                if history:
                    result.update(after_generation=arguments.after_generation, page_limit=arguments.page_limit)
                try:
                    document = (store.claim_use_history(arguments.use_id,
                        after_generation=arguments.after_generation, limit=arguments.page_limit, limits=limits)
                        if history else store.inspect_claim_use(arguments.use_id, limits=limits))
                except RecordNotFoundError:
                    document = None
                result["history" if history else "inspection"] = None if document is None else document.to_dict()
                absent = document is None
                output = _result(arguments.command, result, arguments.max_output_bytes, absent=absent)
        finally:
            # Store close has already run. Held descriptors close on leaving pins,
            # before the caller can write even the first byte of prepared output.
            _check(directories, observations)
    return output, 3 if absent else 0


def classify(error, effects):
    """Preserve real chained I/O failures and distinguish limits, corruption and unsafe layouts."""
    if isinstance(error, CliError) and error.code == "output_failed":
        return error
    chain = tuple(causes(error))
    io_errors = [cause for cause in chain if isinstance(cause, OSError)]
    if any(cause.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE)
           for cause in io_errors):
        return CliError(6, "operational_error", "A filesystem or resource operation failed.")
    if isinstance(error, CliError):
        return error
    if isinstance(error, (ClaimUseLimitError, SnapshotLimitError)):
        return CliError(5, "limit_exceeded", "An independent selected allowance was exceeded.")
    if any(isinstance(cause, (ClaimUseIntegrityError, SnapshotIntegrityError,
                             checkout.CheckoutIntegrityError, ReferenceResolutionError,
                             ArtifactIntegrityError, ResourceIntegrityError)) for cause in chain):
        return CliError(6, "integrity_error", "Canonical metadata, references or held observations failed integrity checks.")
    if isinstance(error, DomainValidationError):
        return CliError(5, "invalid_input", "A supplied value or configuration is invalid.")
    if io_errors or isinstance(error, (checkout.CheckoutLayoutError, StoreLayoutError,
                                      vault.ViewLayoutError, ArtifactLayoutError)):
        return CliError(5, "unsafe_layout", "A required path or store layout is unsafe or unsupported.")
    return CliError(6, "operational_error", "The read failed without complete acknowledgement.")


def guidance(command, failure):
    """Refer to retained selections without repeating paths or suggesting submission recovery."""
    return ("Repeat " + command + " with context.config and context.use_id and the same validated selections "
            "and sufficient independent limits; discard partial output. Command success grants no scientific authority.")
