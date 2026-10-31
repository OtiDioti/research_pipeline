"""Source-local exact inspection and checkout commands with bounded acknowledgment semantics."""

import argparse
from contextlib import ExitStack
import errno
import json
import os
from pathlib import Path
import re
import sys

from research_pipeline import __version__, checkout
from research_pipeline.artifacts import ArtifactError
from research_pipeline.cli_controls import CliError, causes, path_value, read_config, source_root
from research_pipeline.cli_inspection import exact_record, exact_receipt, local_checkout
from research_pipeline.domain import DomainValidationError, RecordReference, _identifier, _integer
from research_pipeline.snapshot import SnapshotIntegrityError, SnapshotLimitError, _bounded_json
from research_pipeline.store import RecordNotFoundError, RecordStore, StoreError, StoreLayoutError
from research_pipeline.vault import _not_layout, ViewLayoutError


_LIMITS = {
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
        escaped = json.dumps(message[:6000], ensure_ascii=True)[1:-1]
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
    """Build the four explicit operations; every parser disables option abbreviation."""
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
    for command, description in descriptions.items():
        sub = subparsers.add_parser(command, description=description, help=description, allow_abbrev=False)
        limits = ["max_output_bytes"]
        if command == "inspect-checkout":
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
    for name in ("config", "destination", "checkout"):
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
    """Close inputs/store/held paths before returning prepared output; preserve all retained checkout effects."""
    command = arguments.command
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
        # Only failure to find the selected root (not missing internal store files)
        # is absence. Chained errno survives all existing layout translations.
        try:
            area = directories.traverse(runtime, private=True)
        except checkout.CheckoutOperationalError as error:
            if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
                raise CliError(3, "missing", "Store root is absent; no store was created.") from error
            raise
        directories.open("objects", area, private=True, path=runtime / "objects")
        directories.open(".staging", area, private=True, path=runtime / ".staging")
        store = stack.enter_context(RecordStore.open(runtime))
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
    value = dict(format="research_pipeline.cli_diagnostic", version=1, command=command,
                 code=error.code, message=str(error)[:1000], context=context)
    data = (_bounded_json(value, 65535, "diagnostic") + "\n").encode("ascii")
    try:
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
    effects = {"begun": False}
    try:
        _validate(arguments)
        for name in ("record_id", "revision", "submission_id"):
            context[name] = getattr(arguments, name, None)
        if hasattr(arguments, "destination"):
            context["destination"] = str(arguments.destination)
        output, status = _execute(arguments, context, effects)
        try:
            _emit(output)
        except (Exception, KeyboardInterrupt) as error:
            raise CliError(7 if effects["begun"] else 6, "output_failed",
                           "Output write, flush or close failed; no complete acknowledgment is claimed.") from error
        return status
    except (Exception, KeyboardInterrupt) as error:
        failure = _classify(error, effects)
        if failure.status == 7:
            context["next_action"] = (
                "Inspect retained evidence with python -m research_pipeline inspect-checkout --checkout PATH "
                "using the exact destination in this diagnostic. Current presence does not prove historical durability. "
                "Review before using a new absent destination.")
        elif failure.code == "output_failed":
            context["next_action"] = "Repeat the same read-only inspection; discard any partial output."
        _diagnostic(arguments.command, failure, context)
        return failure.status
