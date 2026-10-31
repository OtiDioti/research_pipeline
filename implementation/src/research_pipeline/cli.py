"""Source-local inspection and explicit work-product round trips with bounded acknowledgment semantics."""

import argparse
from contextlib import ExitStack
import errno
import json
import os
from pathlib import Path
import re
import sys

from research_pipeline import __version__, checkout, cli_proposals, cli_views, work_product_import
from research_pipeline.artifacts import ArtifactError
from research_pipeline.cli_controls import CliError, causes, path_value, read_config, read_request, source_root
from research_pipeline.cli_inspection import exact_record, exact_receipt, local_checkout
from research_pipeline.domain import DomainValidationError, RecordReference, _identifier, _integer
from research_pipeline.snapshot import SnapshotIntegrityError, SnapshotLimitError, _bounded_json
from research_pipeline.store import (
    RecordNotFoundError, RecordStore, StoreError, StoreLayoutError, RevisionConflictError,
    SubmissionConflictError, ReferenceResolutionError,
)
from research_pipeline.vault import _not_layout, ViewLayoutError


_LIMITS = {
    "max_selection_bytes": (65536, 1, 1048576, "UTF-8 selection bytes"),
    "max_manifest_bytes": (16777216, 1, 67108864, "external historical manifest bytes per pass"),
    "max_request_bytes": (1048576, 1, 16777216, "UTF-8 preparation request bytes"),
    "max_proposal_bytes": (2097152, 1, 16777216, "exact saved ASCII proposal bytes"),
    "max_summary_bytes": (4194304, 1, 16777216, "exact saved ASCII summary bytes"),
    "max_inventory_entries": (4096, 1, 65536, "visited draft directory entries"),
    "max_control_bytes": (65536, 1, 1048576, "UTF-8 bytes"),
    "max_output_bytes": (2097152, 1, 16777216, "ASCII bytes including LF"),
    "max_metadata_bytes": (2097152, 1, 16777216, "selected metadata bytes"),
    "max_links": (4096, 0, 65536, "record and artifact link occurrences"),
    "max_receipt_records": (1024, 1, 65536, "ordered record occurrences"),
    "max_descriptor_bytes": (1048576, 1, 16777216, "descriptor bytes"),
    "max_files": (128, 1, 1024, "logical files"),
    "max_file_bytes": (16777216, 0, 1073741824, "bytes per file"),
    "max_total_bytes": (67108864, 0, 4294967296, "logical file bytes"),
}


class _Parser(argparse.ArgumentParser):
    """Keep standard usage status while escaping and bounding user-controlled error insertions."""

    def _print_message(self, message, file=None):
        """Acknowledge help/version only after stdout closes; preserve argparse's stderr usage text."""
        if message and file is sys.stdout:
            try:
                _emit(message.encode("ascii"))
            except (Exception, KeyboardInterrupt):
                failure = CliError(6, "output_failed", "Text output failed; no complete acknowledgment is claimed.")
                context = dict(store=None, destination=None, record_id=None, revision=None,
                               submission_id=None, next_action="Repeat the same help or version request.")
                _diagnostic(None, failure, context)
                self.exit(6)
        else:
            super()._print_message(message, file)

    def error(self, message):
        """Emit safe bounded usage text; no input, store or destination has been opened yet."""
        self.print_usage(sys.stderr)
        escaped = json.dumps(message[:6000], ensure_ascii=True)[1:-1][:60000]
        self.exit(2, f"{self.prog}: error: {escaped}\n")


class _Once(argparse.Action):
    """Reject repeated singleton options instead of silently selecting a later value."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Remember parsed destinations and report duplicates as usage failures."""
        specified = getattr(namespace, "_specified", set())
        if self.dest in specified:
            parser.error(f"repeated option: {option_string}")
        specified.add(self.dest)
        namespace._specified = specified
        setattr(namespace, self.dest, values)


def _decimal(value):
    """Recognize ASCII decimal syntax without converting a potentially enormous integer token."""
    if re.fullmatch(r"[0-9]+", value) is None:
        raise argparse.ArgumentTypeError("expected decimal integer syntax")
    return value


def _parser():
    """Build the explicit operations; every parser disables option abbreviation."""
    parser = _Parser(prog="python -m research_pipeline", allow_abbrev=False,
                     description="Research workbench foundation: research execution is unavailable.")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", parser_class=_Parser)
    descriptions = {
        "inspect-record": "Inspect one exact attributed envelope and commit without artifact reads.",
        "inspect-receipt": "Inspect the original submission receipt, independent of current heads.",
        "checkout-work-product": "Copy an exact historical bundle into a new writable draft.",
        "inspect-checkout": "Read original published checkout controls offline, without checking edited files.",
    }
    descriptions.update({
        "prepare-work-product": "Preview explicit edited files and durably save a new package without submitting.",
        "inspect-proposal": "Inspect a saved proposal and recomputed changes offline; never repair or submit.",
        "submit-work-product": "Submit exactly a published saved package; reconcile retries under the original ID.",
    })
    descriptions.update({
        "generate-readable-view": "Publish a new immutable readable view from one explicit selection.",
        "refresh-readable-view": "Preserve prior edits against an independent baseline and publish a new package.",
        "inspect-readable-view": "Observe an explicit readable view offline without historical acknowledgment.",
        "inspect-readable-refresh": "Observe exact retained refresh evidence offline; never replay or repair.",
    })
    for command, description in descriptions.items():
        sub = subparsers.add_parser(command, description=description, help=description, allow_abbrev=False)
        limits = ["max_output_bytes"]
        if command in cli_views.COMMANDS:
            for option in ("config", "limits"):
                sub.add_argument("--" + option, required=True, action=_Once, metavar="FILE")
            limits += ["max_control_bytes"]
            if command in cli_views.WRITERS:
                sub.add_argument("--selection", required=True, action=_Once, metavar="FILE")
                sub.add_argument("--destination", required=True, action=_Once, metavar="PATH")
                limits += ["max_selection_bytes"]
            if command == "refresh-readable-view":
                for option in ("prior-view", "baseline-manifest", "expected-base-plan-id",
                               "expected-base-manifest-sha256"):
                    sub.add_argument("--" + option, required=True, action=_Once)
                limits += ["max_manifest_bytes"]
            if command == "inspect-readable-view":
                sub.add_argument("--view", required=True, action=_Once, metavar="PATH")
                sub.add_argument("--expected-plan-id", action=_Once, metavar="SHA256")
                limits += ["max_manifest_bytes"]
            if command == "inspect-readable-refresh":
                for option in ("attempt", "destination"):
                    sub.add_argument("--" + option, required=True, action=_Once, metavar="PATH")
                sub.add_argument("--expected-refresh-id", action=_Once, metavar="SHA256")
        elif command in ("prepare-work-product", "inspect-proposal", "submit-work-product"):
            limits += ["max_control_bytes", "max_proposal_bytes", "max_summary_bytes"]
            if command != "inspect-proposal":
                sub.add_argument("--config", required=True, action=_Once, metavar="FILE")
                limits += ["max_files", "max_file_bytes", "max_total_bytes"]
            if command == "prepare-work-product":
                for option in ("checkout", "request", "destination"):
                    sub.add_argument("--" + option, required=True, action=_Once, metavar="PATH")
                limits += ["max_request_bytes", "max_metadata_bytes", "max_links", "max_receipt_records",
                           "max_descriptor_bytes", "max_inventory_entries"]
            else:
                sub.add_argument("--proposal", required=True, action=_Once, metavar="DIRECTORY")
        elif command == "inspect-checkout":
            sub.add_argument("--checkout", required=True, action=_Once, metavar="PATH")
            limits += ["max_descriptor_bytes"]
        else:
            sub.add_argument("--config", required=True, action=_Once, metavar="FILE")
            limits += ["max_control_bytes", "max_metadata_bytes"]
            if command == "inspect-receipt":
                sub.add_argument("--submission-id", required=True, action=_Once, metavar="ID")
                limits += ["max_receipt_records"]
            else:
                sub.add_argument("--record-id", required=True, action=_Once, metavar="ID")
                sub.add_argument("--revision", required=True, type=_decimal, action=_Once, metavar="N")
                limits += ["max_links"]
            if command == "checkout-work-product":
                sub.add_argument("--destination", required=True, action=_Once, metavar="PATH")
                limits += ["max_descriptor_bytes", "max_files", "max_file_bytes", "max_total_bytes"]
        for name in limits:
            default, minimum, maximum, unit = _LIMITS[name]
            if name == "max_control_bytes" and command in (
                    "prepare-work-product", "inspect-proposal", "submit-work-product"):
                unit = "bytes per config/package manifest (manifest also capped at 16384 bytes)"
            sub.add_argument("--" + name.replace("_", "-"), action=_Once, type=_decimal,
                             default=default, metavar="N",
                             help=f"{unit}; default {default}; range {minimum}..{maximum}")
    return parser


def _number(value, minimum, maximum):
    """Convert validated decimal syntax only within a small token bound and inclusive range."""
    if type(value) is str:
        value = value.lstrip("0") or "0"
        if len(value) > 20:
            raise SnapshotLimitError("numeric option exceeds range")
        value = int(value)
    if not minimum <= value <= maximum:
        raise SnapshotLimitError("numeric option outside permitted range")
    return value


def _validate(arguments):
    """Validate every selected value before opening controls or any dependent resource."""
    for name, (_, minimum, maximum, _) in _LIMITS.items():
        if hasattr(arguments, name):
            setattr(arguments, name, _number(getattr(arguments, name), minimum, maximum))
    for name in ("record_id", "submission_id"):
        if hasattr(arguments, name):
            _identifier(getattr(arguments, name), name)
    if hasattr(arguments, "revision"):
        arguments.revision = _number(arguments.revision, 1, 2**63 - 1)
        _integer(arguments.revision, "revision", 1)
    for name in ("expected_base_plan_id", "expected_base_manifest_sha256", "expected_plan_id", "expected_refresh_id"):
        value = getattr(arguments, name, None)
        if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise DomainValidationError("identity requires lowercase SHA-256")
    for name in ("config", "destination", "checkout", "request", "proposal", "limits", "selection",
                 "prior_view", "baseline_manifest", "view", "attempt"):
        if hasattr(arguments, name):
            setattr(arguments, name, path_value(getattr(arguments, name)))


def _result(command, result, maximum, *, absent=False):
    """Prepare one complete canonical machine document including LF before any stdout write."""
    value = dict(format="research_pipeline.cli_result", version=1, command=command,
                 status="absent" if absent else "ok", result=result)
    return (_bounded_json(value, maximum - 1, "CLI output") + "\n").encode("ascii")


def _destination(directories, path, roots):
    """Preflight exclusions, private parent and fixed ancestor sentinels before exclusive checkout."""
    checkout._outside(path, roots)
    parent = directories.traverse(path.parent, private=True, exact=True)
    for _, _, fd, _, _, _, location in directories.bindings:
        _not_layout(fd, Path(location))
        cli_proposals.not_proposal(fd, Path(location))
    try:
        checkout._stat(parent, path.name)
    except FileNotFoundError:
        return
    raise CliError(4, "conflict", "Destination already exists; retained material was not reused.")


def _checkout_preflight(arguments, envelope):
    """Validate exact manifest/namespace and all four checkout budgets without reserving output."""
    base = RecordReference(arguments.record_id, arguments.revision, "checkout_base", "work_product_manifest")
    info = checkout.CheckoutInfo(base, envelope)
    manifest = checkout._inventory(info)
    if (len(manifest.files) > arguments.max_files
            or any(entry.artifact.size > arguments.max_file_bytes for entry in manifest.files)
            or sum(entry.artifact.size for entry in manifest.files) > arguments.max_total_bytes):
        raise SnapshotLimitError("checkout inventory budget exceeded")
    if len(checkout._encode(info)) > arguments.max_descriptor_bytes:
        raise SnapshotLimitError("checkout descriptor byte budget exceeded")
    return info


def _execute(arguments, context, effects):
    """Dispatch one operation and close inputs/store/held paths before returning bounded output."""
    command = arguments.command
    if command in cli_views.COMMANDS:
        return cli_views.execute(arguments, context, effects)
    if command in ("prepare-work-product", "inspect-proposal", "submit-work-product"):
        return _execute_proposal(arguments, context, effects)
    if command == "inspect-checkout":
        info = local_checkout(arguments.checkout, arguments.max_descriptor_bytes)
        return _result(command, dict(checkout=str(arguments.checkout), base=info.base.to_dict(),
                       envelope=info.envelope.to_dict(), observation="published_descriptor",
                       historical_durability="unknown"), arguments.max_output_bytes), 0
    runtime, roots = read_config(arguments.config, arguments.max_control_bytes)
    context["store"] = str(runtime)
    source = source_root()
    checkout._outside(runtime, (source, *roots))
    with ExitStack() as stack:
        directories = checkout._Directories(stack)
        if command == "checkout-work-product":
            _destination(directories, arguments.destination, (source, runtime, arguments.config, *roots))
        store = _open_store(stack, directories, runtime)
        if command == "inspect-receipt":
            receipt = exact_receipt(store, arguments.submission_id, arguments.max_metadata_bytes,
                                    arguments.max_receipt_records)
            absent = receipt is None
            output = _result(command, dict(submission_id=arguments.submission_id,
                             receipt=None if absent else receipt.to_dict()),
                             arguments.max_output_bytes, absent=absent)
        else:
            try:
                envelope, commit = exact_record(store, arguments.record_id, arguments.revision,
                                                arguments.max_metadata_bytes, arguments.max_links)
                absent = False
            except RecordNotFoundError:
                envelope, commit, absent = None, None, True
            if command == "inspect-record":
                output = _result(command, dict(record_id=arguments.record_id, revision=arguments.revision,
                                 envelope=None if absent else envelope.to_dict(), commit=commit),
                                 arguments.max_output_bytes, absent=absent)
            elif absent:
                raise CliError(3, "missing", "Exact checkout base is absent.")
            else:
                info = _checkout_preflight(arguments, envelope)
                output = _result(command, dict(destination=str(arguments.destination), base=info.base.to_dict(),
                                 descriptor=".work-product/checkout.json"), arguments.max_output_bytes)
                directories.check()
                effects["artifacts"] = {entry.artifact.digest for entry in checkout._inventory(info).files}
                effects["begun"] = True
                actual = checkout.checkout_work_product(
                    store, info.base, arguments.destination, source_root=source,
                    protected_roots=(*roots, arguments.config),
                    **{name: getattr(arguments, name) for name in
                       ("max_files", "max_file_bytes", "max_total_bytes", "max_descriptor_bytes")})
                effects["returned"] = True
                if checkout._encode(actual) != checkout._encode(info):
                    raise CliError(7, "effects_uncertain", "Checkout returned inconsistent historical information.")
        directories.check()
    return output, 3 if absent else 0


def _open_store(stack, directories, runtime):
    """Open only an explicit existing runtime, distinguishing missing roots from damaged internal files."""
    try:
        area = directories.traverse(runtime, private=True)
    except checkout.CheckoutOperationalError as error:
        if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
            raise CliError(3, "missing", "Store root is absent; no store was created.") from error
        raise
    directories.open("objects", area, private=True, path=runtime / "objects")
    directories.open(".staging", area, private=True, path=runtime / ".staging")
    return stack.enter_context(RecordStore.open(runtime))


def _proposal_identity(observation, context, effects):
    """Retain established package identities for bounded recovery diagnostics on later failure."""
    context.update(submission_id=observation["submission_id"],
                   record_id=observation["base"]["record_id"], revision=observation["proposed_revision"])
    effects["proposal_sha256"] = observation["proposal_sha256"]


def _declared_files(submission, arguments):
    """Bound declared inventory without artifact availability checks ahead of original-ID reconciliation."""
    files = work_product_import.decode_envelope(submission.records[0]).files
    if (len(files) > arguments.max_files
            or any(entry.artifact.size > arguments.max_file_bytes for entry in files)
            or sum(entry.artifact.size for entry in files) > arguments.max_total_bytes):
        raise SnapshotLimitError("declared inventory budget exceeded")


def _execute_proposal(arguments, context, effects):
    """Prepare, inspect or submit exact saved evidence with operation-specific lifecycle tracking."""
    command = arguments.command
    if command == "inspect-proposal":
        observation, _ = cli_proposals.observe(arguments.proposal, arguments, recovery=effects)
        absent = observation["state"] == "absent"
        if observation["base"] is not None:
            _proposal_identity(observation, context, effects)
        return _result(command, observation, arguments.max_output_bytes, absent=absent), 3 if absent else 0
    runtime, roots = read_config(arguments.config, arguments.max_control_bytes)
    context["store"] = str(runtime)
    source = source_root()
    checkout._outside(runtime, (source, *roots))
    if command == "submit-work-product":
        observation, submission = cli_proposals.observe(arguments.proposal, arguments, durable=True, recovery=effects)
        _proposal_identity(observation, context, effects)
        _declared_files(submission, arguments)
        result = dict(destination=str(arguments.proposal), proposal_sha256=observation["proposal_sha256"],
                      submission_id=submission.submission_id)
        # This is an output-size reservation, never an invented committed receipt.
        reservation = dict(submission_id=submission.submission_id, fingerprint="0" * 64,
                           event_id=2**63 - 1, committed_at="9999-12-31T23:59:59.999999Z",
                           provenance=submission.provenance.to_dict(),
                           revisions=[[submission.records[0].record_id, submission.records[0].revision]])
        _result(command, dict(**result, receipt=reservation), arguments.max_output_bytes)
        with ExitStack() as stack:
            directories = checkout._Directories(stack)
            store = _open_store(stack, directories, runtime)
            directories.check()
            # The store must reconcile the original ID before availability/head checks.
            effects["begun"] = effects["submit_entered"] = True
            receipt = store.submit_typed(submission)
            effects["returned"] = True
            output = _result(command, dict(**result, receipt=receipt.to_dict()), arguments.max_output_bytes)
            directories.check()
        return output, 0
    request = read_request(arguments.request, arguments.max_request_bytes, arguments.max_files)
    base = request["base"]
    context.update(record_id=base.record_id, revision=base.revision + 1, submission_id=request["submission_id"])
    result = dict(destination=str(arguments.destination), proposal_sha256="0" * 64,
                  submission_id=request["submission_id"], base=base.to_dict(), proposed_revision=base.revision + 1)
    _result(command, result, arguments.max_output_bytes)
    exclusions = (source, runtime, arguments.config, arguments.request, *roots)
    checkout._outside(arguments.checkout, (*exclusions, arguments.destination))
    with ExitStack() as stack:
        directories = checkout._Directories(stack)
        _destination(directories, arguments.destination, (*exclusions, arguments.checkout))
        draft_parent = directories.traverse(arguments.checkout.parent)
        for _, _, fd, _, _, _, location in directories.bindings:
            _not_layout(fd, Path(location))
            cli_proposals.not_proposal(fd, Path(location))
        draft = directories.open(arguments.checkout.name, draft_parent, private=True, exact=True,
                                 path=arguments.checkout)
        cli_proposals.not_proposal(draft, arguments.checkout)
        store = _open_store(stack, directories, runtime)
        envelope, commit = exact_record(store, base.record_id, base.revision,
                                        arguments.max_metadata_bytes, arguments.max_links)
        info = checkout.CheckoutInfo(base, envelope)
        receipt = exact_receipt(store, commit["submission_id"], arguments.max_metadata_bytes,
                                arguments.max_receipt_records)
        if receipt is None:
            raise SnapshotIntegrityError("missing base receipt")
        observed = local_checkout(arguments.checkout, arguments.max_descriptor_bytes)
        if checkout._encode(observed) != checkout._encode(info):
            raise checkout.CheckoutIntegrityError("checkout differs from exact base")
        directories.check()
        effects["begun"] = True
        prepared = work_product_import.prepare_work_product_import(
            store, checkout_directory=arguments.checkout, **request, source_root=source,
            protected_roots=(*roots, arguments.config, arguments.request, arguments.destination),
            **{name: getattr(arguments, name) for name in ("max_files", "max_file_bytes", "max_total_bytes",
                                                         "max_descriptor_bytes", "max_inventory_entries")})
        documents = cli_proposals.documents(prepared, info, receipt.provenance, arguments)
        result["proposal_sha256"] = cli_proposals._digest(documents["proposal.json"])["sha256"]
        effects["proposal_sha256"] = result["proposal_sha256"]
        output = _result(command, result, arguments.max_output_bytes)
        directories.check()
        cli_proposals.publish(arguments.destination, documents, arguments, effects)
        effects["returned"] = True
        directories.check()
    return output, 0


def _silence_stdout(stream):
    """Prevent shutdown from retrying failed buffered output against the original recipient."""
    sys.stdout = None
    fd = None
    try:
        fd = stream.fileno()
        sink = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(sink, fd)
        finally:
            os.close(sink)
    except Exception:
        # Even descriptor exhaustion must not leave a buffered retry connected
        # to the recipient. The command has already lost its acknowledgment.
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
    try:
        stream.close()
    except Exception:
        pass


def _emit(data):
    """Drain short writes and require flush and close before acknowledging complete stdout output."""
    stream = sys.stdout
    try:
        target = stream.buffer
        remaining = memoryview(data)
        while remaining:
            written = target.write(remaining)
            if type(written) is not int or not 0 < written <= len(remaining):
                raise OSError("stdout made no progress")
            remaining = remaining[written:]
        stream.flush()
        stream.close()
        sys.stdout = None
    except BaseException:
        _silence_stdout(stream)
        raise


def _classify(error, effects):
    """Map failures using types and chained errno, never parsing publication-message wording."""
    operation = effects.get("operation")
    if operation in cli_views.COMMANDS:
        return cli_views.classify(error, effects)
    if operation in ("prepare-work-product", "submit-work-product"):
        if effects.get("returned") or effects.get("published"):
            if isinstance(error, CliError) and error.status == 7:
                return error
            return CliError(7, "effects_uncertain", "Saved publication or submission acknowledgment is uncertain.")
        if isinstance(error, (RevisionConflictError, SubmissionConflictError)):
            message = ("Preparation conflicts with the current head or a used submission ID."
                       if operation == "prepare-work-product" else
                       "Saved submission conflicts with the current head or a different request under its ID.")
            return CliError(4, "conflict", message)
        if isinstance(error, (ArtifactError, ReferenceResolutionError)):
            return CliError(6, "integrity_error", "Required canonical objects or references are unavailable or invalid.")
        if isinstance(error, RecordNotFoundError) and operation == "prepare-work-product":
            return CliError(3, "missing", "Exact preparation base is absent.")
        if effects.get("submit_entered"):
            return CliError(7, "effects_uncertain", "Submission effects or acknowledgment are uncertain.")
    if isinstance(error, CliError):
        return error
    chain = tuple(causes(error))
    begun = effects["begun"]
    if effects.get("returned"):
        return CliError(7, "effects_uncertain", "Published checkout synchronization or acknowledgment is uncertain.")
    if any(isinstance(cause, FileExistsError) for cause in chain):
        return CliError(4, "conflict", "Destination collision; retained material was not reused.")
    if isinstance(error, SnapshotLimitError):
        return CliError(5, "limit_exceeded", "A selected count or byte limit was exceeded.")
    if isinstance(error, DomainValidationError):
        return CliError(5, "invalid_input", "A requested value or structured control is invalid.")
    io_errors = [cause for cause in chain if isinstance(cause, OSError)]
    if any(isinstance(cause, FileNotFoundError) and cause.filename in effects.get("artifacts", ())
           for cause in chain):
        return CliError(6, "integrity_error", "Required canonical artifact bytes are unavailable.")
    if begun and operation == "prepare-work-product" and isinstance(
            error, (checkout.CheckoutOperationalError, OSError, KeyboardInterrupt, StoreError)):
        return CliError(7, "effects_uncertain", "Preparation effects or acknowledgment are uncertain; output is retained.")
    if begun and isinstance(error, (checkout.CheckoutOperationalError, OSError, KeyboardInterrupt, StoreError)):
        return CliError(7, "effects_uncertain", "Checkout effects or acknowledgment are uncertain; output is retained.")
    if isinstance(error, (checkout.CheckoutIntegrityError, SnapshotIntegrityError, ArtifactError)):
        return CliError(6, "integrity_error", "Selected metadata, artifact bytes or observed bindings failed integrity checks.")
    if io_errors:
        if all(cause.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP) for cause in io_errors):
            return CliError(5, "unsafe_layout", "A required path or control layout is missing or unsafe.")
        return CliError(6, "operational_error", "A filesystem operation failed.")
    if isinstance(error, (checkout.CheckoutLayoutError, StoreLayoutError, ViewLayoutError)):
        return CliError(5, "unsafe_layout", "A required path or control layout is unsafe or incomplete.")
    return CliError(6, "operational_error", "The operation failed without a complete acknowledgment.")


def _diagnostic(command, error, context):
    """Emit one bounded ASCII diagnostic, reserving exact recovery identities before explanatory text."""
    # Two 4096-byte paths need at most 49152 ASCII bytes after escaping. Fixed
    # identity/guidance fields and this message cap fit in the remaining allowance.
    message = str(error)[:1000]
    if command in cli_views.COMMANDS:
        # Bound explanatory text by escaped ASCII bytes, keeping exact recovery
        # paths/identities intact even when each path expands sixfold in JSON.
        while len(json.dumps(message, ensure_ascii=True).encode("ascii")) > 1024:
            message = message[:len(message) // 2]
    value = dict(format="research_pipeline.cli_diagnostic", version=1, command=command,
                 code=error.code, message=message, context=context)
    try:
        data = (_bounded_json(value, 65535, "diagnostic") + "\n").encode("ascii")
        checkout._write_all(sys.stderr.fileno(), data)
    except (OSError, ValueError, AttributeError):
        # An unusable stderr cannot turn a failed operation into success.
        pass


def main(argv=None):
    """Parse the complete invocation, run one bounded operation, and return its documented exit status."""
    parser = _parser()
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if arguments.command is None:
        parser.print_help()
        return 0
    context = dict(store=None, destination=None, record_id=None, revision=None,
                   submission_id=None, next_action=None)
    if arguments.command in cli_views.COMMANDS:
        context = dict.fromkeys(cli_views.CONTEXT_FIELDS)
    effects = {"begun": False, "operation": arguments.command}
    try:
        _validate(arguments)
        if arguments.command not in cli_views.COMMANDS:
            for name in ("record_id", "revision", "submission_id"):
                context[name] = getattr(arguments, name, None)
        if hasattr(arguments, "view"):
            context["destination"] = str(arguments.view)
        if hasattr(arguments, "attempt"):
            context["attempt_path"] = str(arguments.attempt)
        if hasattr(arguments, "destination"):
            context["destination"] = str(arguments.destination)
        if hasattr(arguments, "proposal"):
            context["destination"] = str(arguments.proposal)
        output, status = _execute(arguments, context, effects)
        try:
            _emit(output)
        except (Exception, KeyboardInterrupt) as error:
            raise CliError(7 if effects["begun"] else 6, "output_failed",
                           "Output write, flush or close failed; no complete acknowledgment is claimed.") from error
        return status
    except (Exception, KeyboardInterrupt) as error:
        failure = _classify(error, effects)
        if effects.get("verified") is not None:
            _proposal_identity(effects["verified"], context, effects)
        if arguments.command in cli_views.COMMANDS:
            context["next_action"] = cli_views.guidance(arguments.command, failure)
        elif arguments.command in ("prepare-work-product", "submit-work-product"):
            identity = effects.get("proposal_sha256")
            if arguments.command == "prepare-work-product":
                action = ("Use inspect-proposal --proposal PATH at the retained destination. "
                          "Preparation retry needs a new absent destination and recaptures the draft; "
                          "it does not reconcile the original ID.")
            else:
                action = ("Use inspect-receipt --config FILE --submission-id ID with the original ID, then "
                          "retry submit-work-product with the identical saved package/config when appropriate. "
                          "An absent receipt does not authorize regenerating the request.")
            context["next_action"] = action + (" Proposal SHA-256: " + identity + "." if identity else "")
        elif failure.status == 7:
            context["next_action"] = (
                "Inspect retained evidence with python -m research_pipeline inspect-checkout --checkout PATH "
                "using the exact destination in this diagnostic. Current presence does not prove historical durability. "
                "Review before using a new absent destination.")
        elif failure.code == "output_failed":
            context["next_action"] = "Repeat the same read-only inspection; discard any partial output."
            if effects.get("proposal_sha256"):
                context["next_action"] += " Proposal SHA-256: " + effects["proposal_sha256"] + "."
        _diagnostic(arguments.command, failure, context)
        return failure.status
