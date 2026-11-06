"""Bounded saved Source inspection and explicit original-ID typed submission.

The pure Source codec owns request coherence; the store owns admission and
reconciliation. Scientific declarations never select paths to acquire here.
"""

from contextlib import ExitStack
import errno
import hashlib

from research_pipeline import checkout, source_capture, vault
from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactLayoutError
from research_pipeline.cli_controls import (
    CliError, _ObservedDirectories, _ancestors, _check, _config_value, _read_control,
    causes, path_value, receipt_document, receipt_reservation_value, source_root, strict_json,
)
from research_pipeline.domain import DomainValidationError, SubmissionReceipt, _fields
from research_pipeline.claim_use import ClaimUseIntegrityError, ClaimUseLimitError
from research_pipeline.resources import ResourceIntegrityError
from research_pipeline.snapshot import SnapshotIntegrityError, SnapshotLimitError, _bounded_json, _json_parts
from research_pipeline.store import (
    ReferenceResolutionError, RevisionConflictError, SubmissionConflictError, StoreLayoutError,
)

COMMANDS = frozenset(("inspect-source-proposal", "submit-source-capture"))
CONTEXT_FIELDS = ("config", "proposal", "record_id", "revision", "submission_id",
                  "proposal_sha256", "submission_fingerprint", "next_action")
DESCRIPTIONS = {
    "inspect-source-proposal": "Inspect a saved private Source proposal offline; config establishes exclusions only. "
        "No runtime, original inputs, artifacts, references or admission are inspected.",
    "submit-source-capture": "Submit one saved exact Source request to the configured existing runtime. "
        "Recover using inspect-receipt and an identical saved-request retry with the original ID/config/runtime. "
        "Preparation remains library-only; research execution is unavailable.",
}
SPECIFICATIONS = {
    "max_control_bytes": (65536, 1, 1048576, "actual UTF-8 configuration bytes including whitespace"),
    "max_proposal_bytes": (2097152, 1, 16777216, "actual UTF-8 saved proposal bytes including whitespace"),
    "max_metadata_bytes": (16777216, 1, 67108864, "reservation for two complete canonical ASCII Submissions"),
    "max_result_bytes": (4194304, 1, 16777216, "complete canonical ASCII Source wrapper or receipt, excluding framing/LF"),
    "max_serialization_bytes": (67108864, 1, 134217728, "aggregate adapter reservation: 2*S + 2*P + F + D + O + 1"),
    "max_output_bytes": (8388608, 1, 16777216, "complete canonical ASCII CLI document including LF"),
}


def validate(arguments, context=None):
    """Validate every Source argv value before acquisition, retaining only normalized control paths."""
    from research_pipeline.cli import _number
    for name, (_, minimum, maximum, _) in SPECIFICATIONS.items():
        setattr(arguments, name, _number(getattr(arguments, name), minimum, maximum))
    for name in ("config", "proposal"):
        path = path_value(getattr(arguments, name))
        setattr(arguments, name, path)
        if context is not None:
            context[name] = str(path)


def _size(value, maximum, label):
    """Count compact sorted ASCII bytes incrementally before allocating escaped representations."""
    size = 0
    for part in _json_parts(value):
        size += len(part)
        if size > maximum:
            raise SnapshotLimitError(label + ": byte allowance exceeded")
    return size


def _budget(size, maximum, label):
    """Enforce an independent inclusive reservation without truncating the requested value."""
    if size > maximum:
        raise SnapshotLimitError(label + ": byte allowance exceeded")


def decode_proposal(data, arguments):
    """Guard raw representations before using the authoritative pure Source loader/dumper.

    Return the detached exact Submission, complete wrapper, semantic fingerprint
    and conservative base representation reservation. Negative zero retains the
    Source codec's JSON semantics; no Tool-specific numeric rule is applied.
    """
    try:
        value = strict_json(data)
    except SnapshotIntegrityError as error:
        raise CliError(5, "invalid_input", "Proposal JSON nesting exceeds the control ceiling.") from error
    _fields(value, {"format", "version", "submission"}, set(), "Source proposal")
    # This is only a size guard. The existing Source codec owns all format,
    # nested-field, projection, identity and expected-head decisions.
    raw = value["submission"]
    s = _size(raw, arguments.max_metadata_bytes // 2, "two complete Submissions")
    p = _size(value, arguments.max_serialization_bytes, "complete Source wrapper")
    fingerprint_value = dict(fingerprint_version=1, submission=raw)
    f = _size(fingerprint_value, arguments.max_serialization_bytes, "fingerprint representation")
    base = 2 * s + 2 * p + f
    _budget(base, arguments.max_serialization_bytes, "preliminary serialization")
    if arguments.command == "inspect-source-proposal":
        _reserve_output(arguments, dict(proposal_path=str(arguments.proposal), proposal_sha256="0" * 64,
            submission_fingerprint="0" * 64, proposal=value), base, value)
    submission = source_capture.loads_prepared_submission(data)
    canonical = source_capture.dumps_prepared_submission(submission)
    if canonical != _bounded_json(value, p, "guarded Source wrapper"):
        raise DomainValidationError("decoded Source proposal changed the guarded document")
    # The loader/dumper equality proves the complete revalidated S/P bounds.
    # Hash only bounded canonical data, using the store's version-one identity.
    fingerprint = hashlib.sha256(_bounded_json(fingerprint_value, f,
        "fingerprint representation").encode("ascii")).hexdigest()
    return submission, value, fingerprint, base


def _reserve_output(arguments, domain, base, result_document):
    """Count independent result/framing/LF accounts without materializing a disposable output."""
    _size(result_document, arguments.max_result_bytes, "complete domain document")
    d = _size(domain, arguments.max_serialization_bytes, "domain result")
    outer = dict(format="research_pipeline.cli_result", version=1,
                 command=arguments.command, status="ok", result=domain)
    o = _size(outer, arguments.max_output_bytes - 1, "CLI output including LF")
    # Repeated request/wrapper/domain/output occurrences count independently.
    _budget(base + d + o + 1, arguments.max_serialization_bytes, "complete serialization")


def _output(arguments, domain, base, result_document):
    """Recheck actual complete representations and encode the one success document before checked closes."""
    from research_pipeline.cli import _result
    _reserve_output(arguments, domain, base, result_document)
    return _result(arguments.command, domain, arguments.max_output_bytes)


def execute(arguments, context, effects):
    """Hold checked controls through store close; inspect offline or submit the loaded request once.

    Every predictable receipt/output reservation precedes runtime acquisition.
    Final observations run even when a later acquisition fails and preserve
    post-entry uncertainty. Checked descriptor closes precede stdout emission.
    """
    from research_pipeline.cli import _open_store
    source = source_root()
    controls = (arguments.config, arguments.proposal)
    for control in controls:
        checkout._outside(control, (source,))
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
            if len(set(controls)) != 2:
                raise checkout.CheckoutLayoutError("controls overlap")
            for control, other in ((controls[0], controls[1]), (controls[1], controls[0])):
                checkout._outside(control, (source, runtime, *roots, other))
            data = _read_control(directories, observations, arguments.proposal,
                                 arguments.max_proposal_bytes, label="proposal")
            submission, wrapper, fingerprint, base = decode_proposal(data, arguments)
            record = submission.records[0]
            context.update(record_id=record.record_id, revision=record.revision,
                           submission_id=submission.submission_id,
                           proposal_sha256=hashlib.sha256(data).hexdigest(),
                           submission_fingerprint=fingerprint)
            common = dict(proposal_path=str(arguments.proposal), proposal_sha256=context["proposal_sha256"],
                          submission_fingerprint=fingerprint)
            if arguments.command == "inspect-source-proposal":
                output = _output(arguments, dict(**common, proposal=wrapper), base, wrapper)
            else:
                reservation = receipt_reservation_value(submission)
                reserved = _size(reservation, arguments.max_result_bytes, "receipt reservation")
                _reserve_output(arguments, dict(store=str(runtime), **common, receipt=reservation), base, reservation)
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
                    _check(directories, observations)
                    effects["begun"] = effects["submit_entered"] = True
                    receipt = store.submit_typed(submission)
                    effects["returned"] = True
                    if (type(receipt) is SubmissionReceipt and type(receipt.fingerprint) is str
                            and receipt.fingerprint != fingerprint):
                        raise DomainValidationError("returned fingerprint differs from saved request")
                    actual = receipt_document(receipt, submission, arguments.max_result_bytes, reserved)
                    output = _output(arguments, dict(store=str(runtime), **common, receipt=actual), base, actual)
        finally:
            try:
                _check(directories, observations)
            except (Exception, KeyboardInterrupt):
                if effects.get("submit_entered"):
                    effects["observation_failed"] = True
                raise
    return output, 0


def classify(error, effects):
    """Preserve deterministic refusals and real I/O causes without inferring transaction rollback."""
    if isinstance(error, CliError) and error.code == "output_failed":
        return error
    if effects.get("returned") or effects.get("observation_failed"):
        return CliError(7, "effects_uncertain", "Submission acknowledgement is uncertain; retain the original saved request and ID.")
    # A finally-based observation or checked close can mask an earlier I/O
    # exception without an explicit cause. Retain those active failure contexts
    # too, so an integrity wrapper cannot turn EACCES/EIO into corruption.
    chain, pending, seen = [], [error], set()
    while pending:
        failure = pending.pop()
        if failure is None or id(failure) in seen:
            continue
        seen.add(id(failure))
        chain.append(failure)
        pending.extend((failure.__cause__, failure.__context__))
    io_errors = [cause for cause in chain if isinstance(cause, OSError)]
    real_io = any(cause.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE)
                  for cause in io_errors)
    if real_io:
        return CliError(7 if effects.get("submit_entered") else 6,
            "effects_uncertain" if effects.get("submit_entered") else "operational_error",
            "A filesystem or resource operation failed; complete acknowledgement is unavailable.")
    if isinstance(error, (RevisionConflictError, SubmissionConflictError)):
        return CliError(4, "conflict", "Saved request conflicts with a head or different request under its original ID.")
    if isinstance(error, CliError):
        return error
    if isinstance(error, (SnapshotLimitError, ClaimUseLimitError)):
        return CliError(5, "limit_exceeded", "An independent caller allowance was exceeded.")
    if any(isinstance(cause, (ReferenceResolutionError, ArtifactIntegrityError, ArtifactNotFoundError,
                             checkout.CheckoutIntegrityError, SnapshotIntegrityError,
                             ClaimUseIntegrityError, ResourceIntegrityError)) for cause in chain):
        return CliError(6, "integrity_error", "Canonical references, direct bytes or held observations failed integrity checks.")
    if isinstance(error, DomainValidationError):
        return CliError(5, "invalid_input", "A supplied configuration or Source proposal is invalid.")
    if effects.get("submit_entered"):
        return CliError(7, "effects_uncertain", "Submission effects or acknowledgement are uncertain; reconcile the original ID.")
    if io_errors or isinstance(error, (checkout.CheckoutLayoutError, StoreLayoutError, ArtifactLayoutError, vault.ViewLayoutError)):
        return CliError(5, "unsafe_layout", "A required control or runtime layout is unsafe or unsupported.")
    return CliError(6, "operational_error", "The operation failed before complete acknowledgement.")


def guidance(command, failure):
    """Describe only same-request recovery, referring to bounded retained context identities."""
    if command == "submit-source-capture":
        return ("Use inspect-receipt --config context.config --submission-id context.submission_id, then "
                "submit-source-capture --config context.config --proposal context.proposal with the identical saved "
                "request, original ID/config/runtime and sufficient original-request limits. Receipt absence does not "
                "authorize changing or regenerating the request. No automatic retry or rollback is claimed; "
                "failed output disavows acknowledgement.")
    return ("Repeat the same offline inspect-source-proposal --config context.config --proposal context.proposal "
            "with sufficient limits; discard partial output. This inspection has no canonical submission effect.")
