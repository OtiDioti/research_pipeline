"""Passive Tool CLI controls, bounded selected reads and original-ID acknowledgement.

Admission and recovery remain RecordStore-owned. No operation here executes a
Tool, stages bytes, selects a head, or authenticates supplied declarations.
"""

from contextlib import ExitStack
import errno
from pathlib import Path
import re

from research_pipeline import checkout, cli_proposals, vault
from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactLayoutError
from research_pipeline.cli_controls import (
    CliError, _ObservedDirectories, _config_value, causes,
    read_observed_control, source_root, strict_json,
)
from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, Submission, SubmissionReceipt, _fields, _identifier, _integer, _kind, _timestamp,
)
from research_pipeline.operating_authority_store import _object_bytes, _text_bound
from research_pipeline.report_capture import _text_length, _integer_length
from research_pipeline.snapshot import (
    SnapshotIntegrityError, SnapshotLimitError, _bounded_json, _check_json_depth, _commit,
)
from research_pipeline.store import (
    RecordNotFoundError, ReferenceResolutionError, RevisionConflictError,
    SubmissionConflictError, StoreLayoutError,
)
from research_pipeline.tool_release import ToolRelease, ToolReleaseLimits, ToolReleaseLimitError
from research_pipeline.tool_release_envelope import decode_envelope as decode_release
from research_pipeline.tool_assessment import ToolAssessment, ToolAssessmentLimits, ToolAssessmentLimitError
from research_pipeline.tool_assessment_envelope import (
    ToolAssessmentEnvelopeLimits, decode_envelope as decode_assessment,
)

COMMANDS = frozenset(("inspect-tool-record", "submit-tool-records"))
CONTEXT_FIELDS = ("config", "batch", "kind", "record_id", "revision", "submission_id", "next_action")
COMMON_LIMITS = ("max_control_bytes", "max_envelope_bytes", "max_content_bytes", "max_metadata_bytes",
                 "max_links", "max_provenance_bytes", "max_provenance_depth", "max_file_bytes", "max_total_bytes")
SUBMIT_LIMITS = ("max_batch_bytes", "max_records", "max_receipt_records", "max_receipt_bytes")
LIMIT_UNITS = {
    "max_control_bytes": "UTF-8 configuration bytes",
    "max_metadata_bytes": "canonical Submission bytes (submit); selected read/retention reservation (inspect)",
    "max_links": "projected record plus artifact occurrences, including repetitions",
    "max_file_bytes": "declared bytes per projected direct artifact",
    "max_total_bytes": "declared bytes across projected direct-artifact occurrences",
}
DESCRIPTIONS = {
    "inspect-tool-record": (
        "Inspect one explicit exact Tool revision in an existing runtime; verify selected direct bytes and local "
        "typed coherence only, without history/pairing admission or execution authority. Research execution is unavailable."),
    "submit-tool-records": (
        "Submit a nonempty saved ordered batch of passive Tool releases/assessments into an existing runtime. "
        "Only submit_typed owns atomic metadata admission. Bytes must already exist. Recover with inspect-receipt "
        "and the identical saved batch/config under the original submission ID; never regenerate it. "
        "Research execution is unavailable."),
}
_ENVELOPE_FIELDS = {"record_id", "revision", "kind", "content", "provenance", "record_references",
                    "artifact_references", "operational_status", "scientific_disposition"}
_KINDS = ("tool_release", "tool_assessment")
_LIMIT_ERRORS = (SnapshotLimitError, ToolReleaseLimitError, ToolAssessmentLimitError)


def _budget(amount, maximum, label):
    """Refuse one independently selected caller allowance before its protected operation."""
    if amount > maximum:
        raise SnapshotLimitError(label + ": selected allowance exceeded")


def _provenance(value, arguments):
    """Check complete raw provenance, depth and ASCII bytes before domain copying.

    Details intentionally retain signed numbers, booleans and finite floats.
    Timestamp normalization and missing descriptive defaults are refused.
    """
    _fields(value, {"actor", "created_at", "details"}, set(), "provenance")
    _identifier(value["actor"], "actor")
    if type(value["created_at"]) is not str or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value["created_at"]) is None:
        raise DomainValidationError("provenance requires six-fraction UTC timestamp")
    if _timestamp(value["created_at"]) != value["created_at"] or type(value["details"]) is not dict:
        raise DomainValidationError("provenance requires canonical date and details object")
    _detail_depth(value["details"], arguments.max_provenance_depth)
    _bounded_json(value, arguments.max_provenance_bytes, "complete provenance")


def _detail_depth(value, maximum, depth=1):
    """Bound parsed provenance containers before reconstruction, counting the root object at one."""
    _budget(depth, maximum, "provenance depth")
    children = value.values() if type(value) is dict else value
    for child in children:
        if type(child) in (dict, list):
            _detail_depth(child, maximum, depth + 1)


def _content_limits(kind, arguments):
    """Narrow only canonical content bytes, preserving all codec hard ceilings."""
    codec = ToolReleaseLimits if kind == "tool_release" else ToolAssessmentLimits
    return codec(max_canonical_bytes=arguments.max_content_bytes)


def _decode(envelope, arguments):
    """Use the existing public Tool envelope decoder under the caller's smaller limits."""
    limits = _content_limits(envelope.kind, arguments)
    if envelope.kind == "tool_release":
        return decode_release(envelope, limits=limits)
    return decode_assessment(envelope, limits=limits,
        envelope_limits=ToolAssessmentEnvelopeLimits(max_provenance_depth=arguments.max_provenance_depth))


def _raw_envelope(value, arguments):
    """Validate closed fields and projected occurrences before generic envelope reconstruction."""
    _fields(value, _ENVELOPE_FIELDS, set(), "Tool envelope")
    if type(value["kind"]) is not str or value["kind"] not in _KINDS:
        raise DomainValidationError("only Tool envelope kinds are permitted")
    _identifier(value["record_id"], "record_id")
    _integer(value["revision"], "revision", 1)
    if value["operational_status"] is not None or value["scientific_disposition"] is not None:
        raise DomainValidationError("passive Tool states must explicitly be null")
    if type(value["content"]) is not dict:
        raise DomainValidationError("Tool content requires an object")
    _bounded_json(value["content"], arguments.max_content_bytes, "Tool content")
    _provenance(value["provenance"], arguments)
    records, artifacts = value["record_references"], value["artifact_references"]
    if type(records) is not list or type(artifacts) is not list:
        raise DomainValidationError("projections require ordered arrays")
    _budget(len(records) + len(artifacts), min(arguments.max_links, 1024), "projected links")
    provenance = value["provenance"]
    metadata_chars = (len(value["record_id"]) + len(value["kind"]) + len(provenance["actor"])
        + len(provenance["created_at"]) + len(_bounded_json(provenance["details"], arguments.max_provenance_bytes, "provenance details")))
    for ref in records:
        _fields(ref, {"record_id", "revision", "relationship", "target_kind"}, set(), "record reference")
        for name in ("record_id", "relationship", "target_kind"):
            _identifier(ref[name], name)
        _integer(ref["revision"], "reference revision", 1)
        _kind(ref["target_kind"], "target_kind")
        metadata_chars += sum(len(ref[name]) for name in ("record_id", "relationship", "target_kind"))
    for ref in artifacts:
        _fields(ref, {"digest", "size"}, set(), "artifact reference")
        if type(ref["digest"]) is not str or re.fullmatch(r"[0-9a-f]{64}", ref["digest"]) is None:
            raise DomainValidationError("invalid artifact digest")
        _integer(ref["size"], "artifact size", 0)
        _budget(ref["size"], arguments.max_file_bytes, "direct artifact bytes")
        metadata_chars += len(ref["digest"])
    _budget(metadata_chars, 262144, "envelope metadata characters")
    _bounded_json(value, arguments.max_envelope_bytes, "complete Tool envelope")
    return len(records) + len(artifacts), sum(ref["size"] for ref in artifacts)


def decode_batch(data, arguments):
    """Reconstruct a complete locally valid saved request without querying runtime state.

    The complete raw Submission is bounded before any domain snapshots. Public
    codecs own nested Tool schemas, identities and exact ordered projections.
    """
    try:
        value = strict_json(data, reject_negative_zero=True)
    except SnapshotIntegrityError as error:
        raise CliError(5, "invalid_input", "Batch JSON nesting exceeds the control ceiling.") from error
    _fields(value, {"format", "version", "submission"}, set(), "Tool batch")
    if (value["format"] != "research_pipeline.cli_tool_batch"
            or type(value["version"]) is not int or value["version"] != 1):
        raise DomainValidationError("unsupported Tool batch format/version")
    raw = value["submission"]
    _fields(raw, {"submission_id", "provenance", "records", "expected_heads"}, set(), "submission")
    _identifier(raw["submission_id"], "submission_id")
    records, heads = raw["records"], raw["expected_heads"]
    if type(records) is not list or not records or type(heads) is not dict:
        raise DomainValidationError("nonempty ordered records and explicit expected_heads required")
    _budget(len(records), arguments.max_records, "batch records")
    _provenance(raw["provenance"], arguments)
    links = total = 0
    identities = set()
    for item in records:
        count, size = _raw_envelope(item, arguments)
        links += count
        total += size
        _budget(links, arguments.max_links, "batch projected links")
        _budget(total, arguments.max_total_bytes, "batch declared direct bytes")
        if item["record_id"] in identities:
            raise DomainValidationError("one revision per stable ID required")
        identities.add(item["record_id"])
    if len(heads) != len(records) or set(heads) != identities:
        raise DomainValidationError("expected_heads must cover exactly the submitted IDs")
    for identity, head in heads.items():
        _identifier(identity, "expected_heads identity")
        _integer(head, "expected head", 0)
    canonical = _bounded_json(raw, arguments.max_metadata_bytes, "complete Submission")
    # Existing content codecs check all nested fields before generic domain
    # reconstruction can snapshot a supplied content dictionary.
    for item in records:
        limits = _content_limits(item["kind"], arguments)
        codec = ToolRelease if item["kind"] == "tool_release" else ToolAssessment
        decoded = codec.from_dict(item["content"], limits=limits).to_dict(limits=limits)
        if _bounded_json(decoded, arguments.max_content_bytes, "decoded content") != _bounded_json(
                item["content"], arguments.max_content_bytes, "supplied content"):
            raise DomainValidationError("incomplete or coercive Tool content")
    submission = Submission.from_dict(raw)
    if _bounded_json(submission.to_dict(), arguments.max_metadata_bytes, "Submission") != canonical:
        raise DomainValidationError("incomplete or coercive submission")
    for item, envelope in zip(records, submission.records):
        content = _decode(envelope, arguments).to_dict(limits=_content_limits(envelope.kind, arguments))
        if _bounded_json(content, arguments.max_content_bytes, "decoded content") != _bounded_json(
                item["content"], arguments.max_content_bytes, "supplied content"):
            raise DomainValidationError("incomplete or coercive Tool content")
    return submission


def _ancestors(directories, runtime=None):
    """Reject fixed-name control/storage ancestors, allowing only the selected runtime internals."""
    for _, _, fd, _, _, _, location in directories.bindings:
        path = Path(location)
        cli_proposals.not_proposal(fd, path)
        if runtime is not None and path in (runtime, runtime / "objects", runtime / ".staging"):
            markers = ("snapshot.sqlite3", ".backup-incomplete", ".restore-incomplete", ".work-product",
                       "manifest.json", "intent.json", "ready.json", "published.json", "refresh.json")
            if any(vault._present(fd, name) for name in markers):
                raise checkout.CheckoutLayoutError("runtime overlaps recognizable control layout")
        else:
            vault._not_layout(fd, path)


def _read_control(directories, observations, path, maximum, *, config=False):
    """Read and close a private leaf while retaining its initial parent-relative signature."""
    try:
        parent = directories.traverse(path.parent, private=True, exact=True)
        _ancestors(directories)
        before = checkout._stat(parent, path.name)
    except Exception as error:
        directories.check()
        if any(isinstance(cause, FileNotFoundError) for cause in causes(error)):
            raise CliError(5 if config else 3, "invalid_input" if config else "missing",
                           "Configuration is missing." if config else "Explicit batch is missing.") from error
        raise
    # Register before the reader so failures cannot discard an established pin.
    observations.append((parent, path.name, before))
    data, _ = read_observed_control(parent, path.name, path, maximum, modes=(0o400, 0o600), before=before)
    return data


def _check(directories, observations):
    """Recheck all established leaf signatures and held bindings on success and failure paths."""
    directories.check()
    for parent, name, before in observations:
        try:
            current = checkout._stat(parent, name)
        except FileNotFoundError as error:
            raise checkout.CheckoutIntegrityError("observed control disappeared") from error
        if checkout._signature(current) != checkout._signature(before):
            raise checkout.CheckoutIntegrityError("observed control changed")


def _receipt_reservation(arguments, submission, runtime):
    """Reserve sufficient complete receipt/output bytes solely from the saved request.

    Placeholder timestamp, event ID and fingerprint size actual store values from
    above. They are never emitted as a receipt or used to query current state.
    """
    from research_pipeline.cli import _result
    _budget(len(submission.records), arguments.max_receipt_records, "receipt membership")
    receipt = dict(submission_id=submission.submission_id, provenance=submission.provenance.to_dict(),
        revisions=[[item.record_id, item.revision] for item in submission.records],
        fingerprint="0" * 64, event_id=9223372036854775807, committed_at="9999-12-31T23:59:59.999999Z")
    size = len(_bounded_json(receipt, arguments.max_receipt_bytes, "receipt reservation"))
    result = dict(store=str(runtime), batch=str(arguments.batch), submission_id=submission.submission_id, receipt=receipt)
    _result(arguments.command, result, arguments.max_output_bytes)
    return size


def _receipt_dict(receipt, submission, arguments, reserved):
    """Validate returned raw fields before bounded receipt conversion after acknowledgement.

    Comparing provenance's retained strings first avoids parsing/copying unexpected
    details. Ordered membership is checked before to_dict allocates its list. Any
    failure here is post-return uncertainty, never evidence of rollback.
    """
    if type(receipt) is not SubmissionReceipt:
        raise CliError(7, "effects_uncertain", "Invalid returned receipt contract.")
    if type(receipt.submission_id) is not str or receipt.submission_id != submission.submission_id:
        raise CliError(7, "effects_uncertain", "Returned receipt has a different original ID.")
    if type(receipt.fingerprint) is not str or re.fullmatch(r"[0-9a-f]{64}", receipt.fingerprint) is None:
        raise DomainValidationError("invalid returned fingerprint")
    _integer(receipt.event_id, "returned event ID", 1)
    if (type(receipt.committed_at) is not str or len(receipt.committed_at) != 27
            or _timestamp(receipt.committed_at) != receipt.committed_at):
        raise DomainValidationError("invalid returned timestamp")
    if type(receipt.provenance) is not CreationProvenance:
        raise DomainValidationError("invalid returned provenance")
    for name in ("actor", "created_at", "_details_json"):
        actual = object.__getattribute__(receipt.provenance, name)
        if type(actual) is not str or actual != object.__getattribute__(submission.provenance, name):
            raise DomainValidationError("returned provenance differs from saved request")
    if type(receipt.revisions) is not tuple or len(receipt.revisions) != len(submission.records):
        raise DomainValidationError("invalid returned membership")
    for pair, record in zip(receipt.revisions, submission.records):
        if (type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str or type(pair[1]) is not int
                or pair != (record.record_id, record.revision)):
            raise DomainValidationError("returned membership differs from saved request")
    actual = receipt.to_dict()
    _bounded_json(actual, min(reserved, arguments.max_receipt_bytes), "returned receipt")
    return actual


def execute(arguments, context, effects):
    """Hold stable controls through store close and acknowledgement preparation, submitting at most once."""
    from research_pipeline.cli import _open_store, _result
    source = source_root()
    observations = []
    with ExitStack() as pins:
        directories = _ObservedDirectories(pins)
        try:
            config = _read_control(directories, observations, arguments.config, arguments.max_control_bytes, config=True)
            try:
                runtime, roots = _config_value(strict_json(config))
            except SnapshotIntegrityError as error:
                raise CliError(5, "invalid_input", "Configuration nesting exceeds the control ceiling.") from error
            checkout._outside(runtime, (source, *roots))
            controls = [arguments.config]
            if arguments.command == "submit-tool-records":
                controls.append(arguments.batch)
            for control in controls:
                checkout._outside(control, (source, runtime, *roots, *(other for other in controls if other != control)))
            if len(controls) != len(set(controls)):
                raise checkout.CheckoutLayoutError("controls overlap")
            submission = None
            if arguments.command == "submit-tool-records":
                data = _read_control(directories, observations, arguments.batch, arguments.max_batch_bytes)
                submission = decode_batch(data, arguments)
                context["submission_id"] = submission.submission_id
                reserved = _receipt_reservation(arguments, submission, runtime)
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
                if submission is None:
                    try:
                        envelope, content, commit = inspect_selected(store, arguments)
                    except RecordNotFoundError:
                        envelope = content = commit = None
                    absent = envelope is None
                    result = dict(store=str(runtime), kind=arguments.kind, record_id=arguments.record_id,
                        revision=arguments.revision, envelope=None if absent else envelope.to_dict(), content=content,
                        commit=commit, direct_artifacts=None if absent else dict(status="verified", count=len(envelope.artifact_references)))
                    output = _result(arguments.command, result, arguments.max_output_bytes, absent=absent)
                    status = 3 if absent else 0
                else:
                    _check(directories, observations)
                    effects["begun"] = effects["submit_entered"] = True
                    receipt = store.submit_typed(submission)
                    # Return is an acknowledgement boundary even if conversion or
                    # held observation/close subsequently fails after COMMIT.
                    effects["returned"] = True
                    actual = _receipt_dict(receipt, submission, arguments, reserved)
                    output = _result(arguments.command, dict(store=str(runtime), batch=str(arguments.batch),
                        submission_id=submission.submission_id, receipt=actual), arguments.max_output_bytes)
                    status = 0
        finally:
            # This runs after store close, also when acquisition/operation failed.
            # A later missing component cannot conceal loss of an earlier pin.
            try:
                _check(directories, observations)
            except (Exception, KeyboardInterrupt):
                if effects.get("submit_entered"):
                    effects["observation_failed"] = True
                raise
    return output, status


def _lengths(row):
    """Require selected SQL lengths/types and required joins before payload fetches."""
    if row is None or any(type(size) is not int or size < 0 for size in row):
        raise SnapshotIntegrityError("missing or invalid selected metadata storage types")
    return sum(row)


def _selected_bounds(connection, key, arguments):
    """Reserve selected guard/store fetches and retained canonical values without collecting links.

    E bounds the canonical envelope, F the complete raw fields/links/commit, and
    K the commit object. 2F + 2E + K covers both reads and envelope, separate
    content and commit retention; it is neither measured RAM nor codec scratch.
    """
    fields = (_text_length("i.kind"), _text_length("r.content_json"), _text_length("r.provenance_json"),
        _text_length("r.operational_status", nullable=True), _text_length("r.scientific_disposition", nullable=True),
        _text_length("r.submission_id"), _text_length("a.committed_at"), _text_length("s.fingerprint"),
        _integer_length("r.ordinal"), _text_length("r.record_id"), _integer_length("r.revision", 1),
        _text_length("i.record_id"), _text_length("a.submission_id"), _text_length("s.submission_id"),
        _text_length("a.event_type"), _integer_length("a.event_id", 1))
    row = connection.execute("SELECT " + ",".join(fields) + """ FROM revisions r
        LEFT JOIN identities i USING(record_id) LEFT JOIN submissions s USING(submission_id)
        LEFT JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
    if row is None:
        raise RecordNotFoundError("selected exact revision absent")
    fetched = _lengths(row)
    _budget(row[0], 128, "stored kind")
    # Select the bounded kind before touching another kind's artifacts/payloads.
    kind = connection.execute("SELECT i.kind FROM revisions r JOIN identities i USING(record_id) WHERE r.record_id=? AND r.revision=?", key).fetchone()[0]
    if kind != arguments.kind:
        raise CliError(5, "invalid_input", "Selected revision has a different kind.")
    _budget(row[1], arguments.max_content_bytes, "selected content")
    _budget(row[2], arguments.max_provenance_bytes, "selected provenance")
    tables = (("record_links", (_text_length("target_id"), _integer_length("target_revision", 1),
                _text_length("relationship"), _text_length("target_kind"))),
              ("artifact_links", (_text_length("digest"), _integer_length("size"))))
    counts = [connection.execute(f"SELECT count(*) FROM {table} WHERE record_id=? AND revision=?", key).fetchone()[0]
              for table, _ in tables]
    _budget(sum(counts), min(arguments.max_links, 1024), "selected projected links")
    # Valid canonical actor/date/identifiers are ASCII. Removing provenance
    # framing leaves the existing codec's exact metadata-character account.
    metadata_chars = len(key[0]) + row[0] + max(0, row[2] - _object_bytes(actor=2, created_at=2, details=0))
    _budget(metadata_chars, 262144, "selected envelope metadata characters")
    collections = []
    total = 0
    for (table, columns), count in zip(tables, counts):
        collection = 2 + max(0, count - 1)
        extra = ",CASE WHEN typeof(size)='integer' AND size>=0 THEN size ELSE NULL END" if table == "artifact_links" else ""
        cursor = connection.execute("SELECT CASE WHEN typeof(ordinal)='integer' THEN ordinal ELSE NULL END,"
            + ",".join(columns) + extra + f" FROM {table} WHERE record_id=? AND revision=? ORDER BY ordinal", key)
        for ordinal in range(count):
            link = cursor.fetchone()
            if link is None or type(link[0]) is not int or link[0] != ordinal:
                raise SnapshotIntegrityError("noncontiguous selected link ordinals")
            lengths = link[1:-1] if extra else link[1:]
            fetched += _lengths(lengths) + len(str(ordinal)) + len(key[0]) + len(str(key[1]))
            metadata_chars += link[1] + (link[3] + link[4] if not extra else 0)
            _budget(metadata_chars, 262144, "selected envelope metadata characters")
            if extra:
                if type(link[-1]) is not int or link[-1] < 0:
                    raise SnapshotIntegrityError("invalid selected artifact size")
                _budget(link[-1], arguments.max_file_bytes, "selected direct bytes")
                total += link[-1]
                _budget(total, arguments.max_total_bytes, "selected total direct bytes")
                collection += _object_bytes(digest=_text_bound(link[1]), size=link[2])
            else:
                collection += _object_bytes(record_id=_text_bound(link[1]), revision=link[2],
                    relationship=_text_bound(link[3]), target_kind=_text_bound(link[4]))
            _budget(2 * fetched, arguments.max_metadata_bytes, "selected fetch reservation")
        if cursor.fetchone() is not None:
            raise SnapshotIntegrityError("selected link count changed")
        collections.append(collection)
    envelope = _object_bytes(record_id=_text_bound(row[9]), revision=row[10], kind=_text_bound(row[0]),
        content=row[1], provenance=row[2], operational_status=_text_bound(row[3]), scientific_disposition=_text_bound(row[4]),
        record_references=collections[0], artifact_references=collections[1])
    commit = _object_bytes(submission_id=_text_bound(row[5]), committed_at=_text_bound(row[6]), fingerprint=_text_bound(row[7]))
    _budget(envelope, arguments.max_envelope_bytes, "selected envelope reservation")
    _budget(2 * fetched + 2 * envelope + commit, arguments.max_metadata_bytes, "selected metadata reservation")


def _stored_json(raw, maximum, *, depth=64):
    """Guard stored JSON before generic parsing; corruption is never authored-input refusal."""
    try:
        if type(raw) is not str or not raw.isascii():
            raise ValueError("expected canonical ASCII")
        _check_json_depth(raw, 64)
        if depth < 64:
            try:
                _check_json_depth(raw, depth)
            except SnapshotIntegrityError as error:
                raise SnapshotLimitError("selected provenance depth allowance exceeded") from error
        value = strict_json(raw.encode("ascii"), reject_negative_zero=True)
        if _bounded_json(value, maximum, "stored canonical JSON") != raw:
            raise ValueError("noncanonical selected JSON")
        return value
    except SnapshotLimitError:
        raise
    except (CliError, ValueError, TypeError, RecursionError) as error:
        raise SnapshotIntegrityError("invalid selected canonical JSON") from error


def inspect_selected(store, arguments):
    """Guard and read one exact Tool plus original commit in a single store-owned snapshot."""
    key = (arguments.record_id, arguments.revision)
    with store._transaction() as connection:
        _selected_bounds(connection, key, arguments)
        raw = connection.execute("""SELECT r.content_json,r.provenance_json,r.submission_id,
            a.committed_at,s.fingerprint,a.event_type FROM revisions r JOIN submissions s USING(submission_id)
            JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        content = _stored_json(raw[0], arguments.max_content_bytes)
        # The enclosing provenance object is one level above details. This
        # lexical gate applies before strict_json can allocate nested containers.
        provenance = _stored_json(raw[1], arguments.max_provenance_bytes, depth=arguments.max_provenance_depth + 1)
        try:
            _provenance(provenance, arguments)
            if raw[5] != "submission_committed":
                raise SnapshotIntegrityError("invalid selected commit event")
            commit = dict(zip(("submission_id", "committed_at", "fingerprint"), raw[2:5]))
            _commit(commit)
            envelope, value = store._get_typed_revision(connection, *key)
            expected = ToolRelease if arguments.kind == "tool_release" else ToolAssessment
            if type(value) is not expected:
                raise SnapshotIntegrityError("selected content has a different typed class")
            # Reapply smaller codec ceilings on the shared body's detached value;
            # raw content/envelope guards already preceded its reconstruction.
            decoded = value.to_dict(limits=_content_limits(arguments.kind, arguments))
            if decoded != content or envelope.provenance.to_dict() != provenance:
                raise SnapshotIntegrityError("selected reconstruction changed canonical values")
            return envelope, decoded, commit
        except _LIMIT_ERRORS:
            raise
        except (DomainValidationError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise SnapshotIntegrityError("invalid selected typed metadata") from error


def classify(error, effects):
    """Classify typed refusals and true I/O causes, preserving post-entry uncertainty."""
    if effects.get("returned") or effects.get("observation_failed"):
        if isinstance(error, CliError) and error.code == "output_failed":
            return error
        return CliError(7, "effects_uncertain", "Submission acknowledgement is uncertain; retain original saved controls and ID.")
    if isinstance(error, (RevisionConflictError, SubmissionConflictError)):
        return CliError(4, "conflict", "Submission conflicts with a head or a different request under its ID.")
    if isinstance(error, CliError):
        return error
    if isinstance(error, _LIMIT_ERRORS):
        return CliError(5, "limit_exceeded", "An independent caller or codec allowance was exceeded.")
    if isinstance(error, DomainValidationError):
        return CliError(5, "invalid_input", "A supplied control or local Tool declaration is invalid.")
    chain = tuple(causes(error))
    io_errors = [cause for cause in chain if isinstance(cause, OSError)]
    real_io = any(cause.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE) for cause in io_errors)
    if not real_io and isinstance(error, (ReferenceResolutionError, ArtifactIntegrityError, ArtifactNotFoundError,
                                         checkout.CheckoutIntegrityError, SnapshotIntegrityError)):
        return CliError(6, "integrity_error", "Canonical metadata, direct bytes or held observations failed integrity checks.")
    if effects.get("submit_entered"):
        return CliError(7, "effects_uncertain", "Submission effects or acknowledgement are uncertain; reconcile the original ID.")
    if real_io:
        return CliError(6, "operational_error", "A filesystem or resource operation failed.")
    if isinstance(error, RecordNotFoundError):
        return CliError(3, "missing", "An explicit exact revision is absent.")
    if io_errors or isinstance(error, (checkout.CheckoutLayoutError, StoreLayoutError, vault.ViewLayoutError, ArtifactLayoutError)):
        return CliError(5, "unsafe_layout", "A required path or control layout is unsafe or incomplete.")
    return CliError(6, "operational_error", "The operation failed before complete acknowledgement.")


def guidance(command, failure):
    """Give bounded recovery routes referring to exact context values without repeating paths."""
    if command == "submit-tool-records":
        return ("Use python3 -B -m research_pipeline inspect-receipt --config context.config --submission-id "
                "context.submission_id, then python3 -B -m research_pipeline submit-tool-records --config "
                "context.config --batch context.batch with the identical canonical saved request and original ID/runtime. "
                "Use sufficient matching receipt/output/local limits. Receipt absence alone does not authorize changes. "
                "No automatic retry, new ID, regenerated provenance, cleanup or rollback claim.")
    return ("Repeat python3 -B -m research_pipeline inspect-tool-record --config context.config --kind context.kind "
            "--record-id context.record_id --revision context.revision with the same limits; discard partial output.")
