"""Atomic report source capture on existing scientific, artifact and resource transactions."""

from datetime import datetime, timezone
import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_pipeline.store import RecordStore
    from research_pipeline.view_plan import ReadablePlan

from research_pipeline.domain import (
    RecordReference, Submission, _identifier,
)
from research_pipeline.snapshot import (
    RootSelector, SnapshotSelection, SnapshotLimits, SnapshotLimitError,
    SnapshotIntegrityError, _canonical, _strict_json, _bounded_json,
)
from research_pipeline.resources import ResourceInspectionLimits
from research_pipeline.work_product import decode_envelope
from research_pipeline import reports
from research_pipeline.reports import (
    ReportRequest, ReportObservation, ReportCommitResult, ReportLimitError,
    ReportScopeError, ReportIntegrityError, REPORT_BYTES, QUALIFICATIONS,
    manifest_id, source_id, pin, unavailable, _artifact_map, _manifest, _submission,
)


def _fault(boundary):
    """Expose bounded synchronization/failure seams, including actual after-COMMIT acknowledgment loss."""


def _require_schema(store):
    """Preserve closed-handle errors and require explicit migration from schema 1."""
    from research_pipeline.store import StoreLayoutError
    store._require_open()
    if store._schema_version not in (2, 3):
        raise StoreLayoutError("committed reports require explicit migration to schema 2 or 3")


def _result(event, receipt):
    """Return original committed metadata without opening any referenced object."""
    payload = event.content
    return ReportCommitResult({"format": "research_pipeline.report_commit_result", "version": 1,
        "operation_id": receipt.submission_id,
        "source_event": RecordReference(event.record_id, 1, "report_source", "event").to_dict(),
        "report_manifest": payload["report_manifest"], "snapshot_id": payload["snapshot_id"],
        "observed_at": payload["observed_at"], "artifacts": payload["artifacts"], "receipt": receipt.to_dict()})


def _text_length(column, *, nullable=False):
    """Build a private SQL UTF-8 length expression that rejects non-text stored values.

    Column names are fixed implementation constants, never caller SQL. Null optional
    states/kinds consume zero bytes; missing required joins remain invalid lengths.
    """
    null = f"WHEN {column} IS NULL THEN 0 " if nullable else ""
    return f"CASE {null}WHEN typeof({column})='text' THEN length(CAST({column} AS BLOB)) ELSE NULL END"


def _integer_length(column, minimum=0):
    """Preflight numeric storage types before fetching potentially corrupt scalar values."""
    return (f"CASE WHEN typeof({column})='integer' AND {column}>={minimum} "
            f"THEN length(CAST({column} AS BLOB)) ELSE NULL END")


def _length_total(row):
    """Validate length-only results and sum in Python, rejecting absent joins and invalid types."""
    if row is None or any(type(size) is not int or size < 0 for size in row):
        raise ReportIntegrityError("missing or invalid stored report metadata")
    return sum(row)


def _preflight_receipt(connection, operation_id, budget):
    """Reserve actual audit fields and exactly two ordered members before receipt reconstruction.

    The strict provenance read and the existing receipt reader each fetch provenance;
    both occurrences count. Receipt members are fixed, separate from link allowances.
    All work uses the preparation's existing read transaction and shared budget.
    """
    columns = (_text_length("s.fingerprint"), _integer_length("a.event_id", 1),
               _text_length("a.committed_at"), _text_length("a.provenance_json"),
               _text_length("a.event_type"), _text_length("a.submission_id"))
    row = connection.execute("SELECT " + ",".join(columns) + """ FROM submissions s
        LEFT JOIN audit_events a USING(submission_id) WHERE s.submission_id=?""", (operation_id,)).fetchone()
    budget.reserve(_length_total(row))
    budget.reserve(row[3])  # Repeated provenance fetch by _receipt after strict validation.
    count = connection.execute("SELECT count(*) FROM revisions WHERE submission_id=?", (operation_id,)).fetchone()[0]
    if type(count) is not int or count != 2:
        raise ReportIntegrityError("actual report submission membership mismatch")
    columns = ("CASE WHEN typeof(r.ordinal)='integer' THEN r.ordinal ELSE NULL END",
               _text_length("i.record_id"), _integer_length("r.revision", 1))
    cursor = connection.execute("SELECT " + ",".join(columns) + """ FROM revisions r
        LEFT JOIN identities i USING(record_id) WHERE r.submission_id=? ORDER BY r.ordinal""", (operation_id,))
    for ordinal in range(count):
        row = cursor.fetchone()
        if row is None or type(row[0]) is not int or row[0] != ordinal:
            raise ReportIntegrityError("noncontiguous report receipt ordinals")
        budget.reserve(_length_total(row[1:]) + len(str(ordinal)))
    if cursor.fetchone() is not None:
        raise ReportIntegrityError("report receipt membership changed inside snapshot")
    event_type, provenance, sid = connection.execute("""SELECT event_type,provenance_json,submission_id
        FROM audit_events WHERE submission_id=?""", (operation_id,)).fetchone()
    if event_type != "submission_committed" or sid != operation_id:
        raise ReportIntegrityError("noncanonical report audit binding")
    try:
        _strict_json(provenance)
    except SnapshotIntegrityError as error:
        raise ReportIntegrityError("noncanonical report audit provenance") from error


def _preflight_revision(connection, expected, limits, budget, remaining_references):
    """Bound actual record fields and link occurrences before the existing envelope reader.

    Raw fields plus all ordered links must fit the per-record ceiling independently
    of the preparation-wide remaining bytes. Length-only cursors never retain an
    unbounded collection; counts and ordinals cannot substitute for byte checks.
    JSON is read once for strict canonical validation and again by the established
    envelope reader; both reads consume the aggregate allowance, not record size.
    """
    key = expected.record_id, expected.revision
    columns = (_text_length("i.kind"), _text_length("r.content_json"), _text_length("r.provenance_json"),
               _text_length("r.operational_status", nullable=True),
               _text_length("r.scientific_disposition", nullable=True))
    row = connection.execute("SELECT " + ",".join(columns) + """ FROM revisions r
        LEFT JOIN identities i USING(record_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
    size = _length_total(row)
    if size > limits.max_record_bytes:
        raise SnapshotLimitError("actual report record byte preflight exceeded")
    budget.reserve(size)
    if row[1] + row[2] > REPORT_BYTES:
        raise ReportIntegrityError("actual report revision is oversized")
    budget.reserve(row[1] + row[2])
    for table, expected_count, columns in (
            ("record_links", len(expected.record_references),
             (_text_length("target_id"), _integer_length("target_revision", 1),
              _text_length("relationship"), _text_length("target_kind", nullable=True))),
            ("artifact_links", len(expected.artifact_references),
             (_text_length("digest"), _integer_length("size")))):
        count = connection.execute("SELECT count(*) FROM " + table + " WHERE record_id=? AND revision=?", key).fetchone()[0]
        if type(count) is not int or count < 0:
            raise ReportIntegrityError("invalid report link count")
        if count > remaining_references[0]:
            raise SnapshotLimitError("report links exceed remaining reference allowance")
        if count != expected_count:
            raise ReportIntegrityError("actual report link count differs from original submission")
        remaining_references[0] -= count
        cursor = connection.execute("SELECT CASE WHEN typeof(ordinal)='integer' THEN ordinal ELSE NULL END,"
            + ",".join(columns) + " FROM " + table + " WHERE record_id=? AND revision=? ORDER BY ordinal", key)
        for ordinal in range(count):
            row = cursor.fetchone()
            if row is None or type(row[0]) is not int or row[0] != ordinal:
                raise ReportIntegrityError("noncontiguous report link ordinals")
            contribution = _length_total(row[1:]) + len(str(ordinal))
            size += contribution
            if size > limits.max_record_bytes:
                raise SnapshotLimitError("actual report link bytes exceed record allowance")
            budget.reserve(contribution)
        if cursor.fetchone() is not None:
            raise ReportIntegrityError("report link count changed inside snapshot")
    content, provenance = connection.execute("SELECT content_json,provenance_json FROM revisions "
        "WHERE record_id=? AND revision=?", key).fetchone()
    for text in (content, provenance):
        try:
            _strict_json(text)
        except SnapshotIntegrityError as error:
            raise ReportIntegrityError("noncanonical actual report revision JSON") from error


def _metadata(store, connection, operation_id, *, preparation_limits=None,
              preparation_budget=None, remaining_references=None):
    """Reconcile against original submission JSON, actual envelope rows and audit membership.

    This precedes heads, timestamps, ledger inspection and artifact availability.
    An event marker alone cannot certify that a submission was a report operation.
    Preparation supplies independent limits and shared byte/reference reservations;
    ordinary receipt recovery retains its metadata-only reconciliation contract.
    """
    from research_pipeline.store import SubmissionConflictError
    row = connection.execute("SELECT " + _text_length("request_json") + "," + _text_length("fingerprint")
        + " FROM submissions WHERE submission_id=?", (operation_id,)).fetchone()
    if row is None:
        return None
    if preparation_budget is not None:
        preparation_budget.reserve(_length_total(row))
    if type(row[0]) is not int or row[0] < 0 or row[0] > REPORT_BYTES:
        raise SubmissionConflictError("original submission is not bounded report metadata")
    if type(row[1]) is not int or row[1] != 64:
        raise ReportIntegrityError("invalid original report fingerprint length")
    text, fingerprint = connection.execute("SELECT request_json,fingerprint FROM submissions WHERE submission_id=?", (operation_id,)).fetchone()
    document = reports._loads(text)
    reports._fields_exact(document, "fingerprint_version submission", "original submission")
    if type(document["fingerprint_version"]) is not int or document["fingerprint_version"] != 1:
        raise ReportIntegrityError("unsupported original submission fingerprint")
    submission = Submission.from_dict(document["submission"])
    if submission.submission_id != operation_id or len(submission.records) != 2:
        raise SubmissionConflictError("operation ID belongs to a non-report submission")
    event, manifest = submission.records
    payload = event.content
    if event.kind != "event" or payload.get("format") != "research_pipeline.report_source":
        raise SubmissionConflictError("operation ID belongs to a non-report submission")
    reports._fields_exact(payload, "format version request snapshot_id observed_at artifacts report_manifest", "report source event")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ReportIntegrityError("unsupported report source event version")
    request = ReportRequest(payload["request"]).to_dict()
    artifacts = _artifact_map(payload["artifacts"])
    expected_manifest = _manifest(request, artifacts)
    if (request["operation_id"] != operation_id or event.record_id != source_id(operation_id) or event.revision != 1
            or event.operational_status is not None or event.scientific_disposition is not None
            or _canonical(request) != _canonical(payload["request"])
            or _canonical(manifest.to_dict()) != _canonical(expected_manifest.to_dict())
            or submission.expected_heads != {event.record_id: 0, manifest.record_id: manifest.revision - 1}
            or _canonical(event.provenance.to_dict()) != _canonical(submission.provenance.to_dict())
            or _canonical(event.provenance.to_dict()) != _canonical(manifest.provenance.to_dict())):
        raise ReportIntegrityError("original report event/request/manifest binding mismatch")
    expected_ref = RecordReference(manifest.record_id, manifest.revision, "report_manifest", "work_product_manifest")
    if (_canonical(payload["report_manifest"]) != _canonical(expected_ref.to_dict())
            or not event.record_references or event.record_references[-1] != expected_ref):
        raise ReportIntegrityError("report manifest link mismatch")
    source_links = event.record_references[:-1]
    if (any(r.relationship != "report_source_revision" or r.target_kind is None for r in source_links)
            or [(r.record_id, r.revision) for r in source_links] != sorted(set((r.record_id, r.revision) for r in source_links))
            or not event.artifact_references or event.artifact_references[0] != artifacts["source.json"]):
        raise ReportIntegrityError("invalid report source links")
    artifact_sizes = {}
    for artifact in event.artifact_references:
        if artifact.digest in artifact_sizes:
            raise ReportIntegrityError("report event artifact links must be distinct by digest")
        artifact_sizes[artifact.digest] = artifact.size
    required_roots = reports._scientific_roots(request)
    if "record_id" in request["start_baseline"]:
        required_roots.append(request["start_baseline"])
    if request["report_revision"] > 1:
        required_roots.append({"record_id": manifest.record_id, "revision": manifest.revision - 1})
    if not {pin(ref) for ref in required_roots} <= {(ref.record_id, ref.revision) for ref in source_links}:
        raise ReportIntegrityError("report event omits a declared exact root")
    if (artifacts["source.json"].size > request["limits"]["max_source_bytes"]
            or any(a.size > request["limits"]["max_output_file_bytes"] for a in artifacts.values())
            or sum(a.size for a in artifacts.values()) > request["limits"]["max_output_total_bytes"]):
        raise ReportLimitError("report metadata artifact sizes exceed original budgets")
    if (_canonical(document) != text or _canonical(submission.to_dict()) != _canonical(document["submission"])
            or hashlib.sha256(text.encode("ascii")).hexdigest() != fingerprint):
        raise ReportIntegrityError("original report submission fingerprint mismatch")
    count = connection.execute("SELECT count(*) FROM revisions WHERE submission_id=?", (operation_id,)).fetchone()[0]
    if count != 2:
        raise ReportIntegrityError("actual report submission membership mismatch")
    if preparation_budget is not None:
        _preflight_receipt(connection, operation_id, preparation_budget)
    receipt = store._receipt(connection, operation_id)
    if receipt is None or receipt.fingerprint != fingerprint or _canonical(receipt.provenance.to_dict()) != _canonical(submission.provenance.to_dict()):
        raise ReportIntegrityError("report audit receipt binding mismatch")
    if receipt.revisions != tuple((r.record_id, r.revision) for r in submission.records):
        raise ReportIntegrityError("report receipt membership order mismatch")
    for expected in submission.records:
        if preparation_budget is not None:
            _preflight_revision(connection, expected, preparation_limits, preparation_budget, remaining_references)
        else:
            # Ordinary metadata-only recovery keeps its existing format ceiling;
            # it does not inherit publication caller allowances or require objects.
            size = connection.execute("SELECT length(CAST(content_json AS BLOB))+length(CAST(provenance_json AS BLOB)) FROM revisions WHERE record_id=? AND revision=?",
                                      (expected.record_id, expected.revision)).fetchone()
            if size is None or size[0] > REPORT_BYTES:
                raise ReportIntegrityError("actual report revision is absent or oversized")
            for table, expected_count in (("record_links", len(expected.record_references)),
                                          ("artifact_links", len(expected.artifact_references))):
                count = connection.execute("SELECT count(*) FROM " + table + " WHERE record_id=? AND revision=?",
                                           (expected.record_id, expected.revision)).fetchone()[0]
                if count != expected_count:
                    raise ReportIntegrityError("actual report link count differs from original submission")
        actual = store._metadata_envelope(connection, expected.record_id, expected.revision)
        if preparation_limits is not None:
            _bounded_json(actual.to_dict(), preparation_limits.max_record_bytes, "report envelope")
        if _canonical(actual.to_dict()) != _canonical(expected.to_dict()):
            raise ReportIntegrityError("actual report revision differs from original submission")
    return _result(event, receipt), request, submission


def _read(store, connection, operation_id, *, maximum=REPORT_BYTES, found=None,
          preparation_budget=None, remaining_references=None):
    """Verify source/output/receipt bindings inside the caller's transaction.

    Preparation may supply already-verified metadata and an independent aggregate
    read budget and remaining reference counter; ordinary historical reads retain
    their original bounds.
    """
    from research_pipeline.store import RecordNotFoundError
    if found is None:
        found = _metadata(store, connection, operation_id)
    if found is None:
        raise RecordNotFoundError("report operation not found: " + operation_id)
    result, request, submission = found
    artifacts = _artifact_map(result.to_dict()["artifacts"])
    source = artifacts["source.json"]
    if source.size > min(maximum, request["limits"]["max_source_bytes"]):
        raise ReportLimitError("saved source exceeds retained baseline/source budget")
    for artifact in artifacts.values():
        if artifact.size > request["limits"]["max_output_file_bytes"]:
            raise ReportLimitError("saved generated object exceeds file budget")
    if sum(a.size for a in artifacts.values()) > request["limits"]["max_output_total_bytes"]:
        raise ReportLimitError("saved generated objects exceed total budget")
    source_bytes = store.read_artifact(source)
    observation = reports.loads_observation(source_bytes)
    if reports.dumps_observation(observation).encode("ascii") != source_bytes:
        raise ReportIntegrityError("source object must contain canonical observation bytes")
    value = observation.to_dict()
    if (_canonical(value["request"]) != _canonical(request) or value["snapshot_id"] != result.to_dict()["snapshot_id"]
            or value["observed_at"] != result.to_dict()["observed_at"]):
        raise ReportIntegrityError("saved observation differs from committed source event")
    expected = _submission(value, artifacts)
    if _canonical(expected.to_dict()) != _canonical(submission.to_dict()):
        raise ReportIntegrityError("source observation closure/event links differ from original submission")
    receipt = result.receipt
    if value["scientific"]["watermark"]["event_id"] != receipt.event_id - 1:
        raise ReportIntegrityError("report observation is not immediately before its own submission")
    _verify_bindings(store, connection, value["scientific"], value["source_bindings"],
                     preparation_budget=preparation_budget, remaining_references=remaining_references)
    generated = reports.render_report(observation)
    for name, data in generated.items():
        artifact = artifacts[name]
        if artifact.digest != hashlib.sha256(data).hexdigest() or artifact.size != len(data):
            raise ReportIntegrityError("deterministic output differs from original artifact binding")
        if store.read_artifact(artifact) != data:
            raise ReportIntegrityError("stored output differs from deterministic rendering")
    return observation


def _verify_bindings(store, connection, snapshot, expected=None, *, preparation_budget=None,
                     remaining_references=None):
    """Verify original requests/audits, retaining only selected revision event IDs and ordinals.

    Original batches may contain unrelated members. Bound their input bytes before
    reading, check their canonical fingerprint and selected ordinal, then discard
    unrelated payloads rather than copying whole receipts into the observation.
    Preparation shares byte and reference counters across the entire report chain;
    its scalar preflight is independent of capture's existing verification allowance.
    """
    bindings, verified = [], {}
    remaining = min(REPORT_BYTES, snapshot["limits"]["max_metadata_bytes"])
    remaining -= snapshot["metadata_fetched_bytes"] + len(_canonical(snapshot))
    for entry in snapshot["records"]:
        if preparation_budget is not None:
            if remaining_references[0] < 1:
                raise SnapshotLimitError("source bindings exceed remaining reference allowance")
            remaining_references[0] -= 1
            columns = (_integer_length("a.event_id", 1), _integer_length("r.ordinal"),
                       _text_length("r.submission_id"), _text_length("a.committed_at"),
                       _text_length("s.fingerprint"))
            lengths = connection.execute("SELECT " + ",".join(columns) + """ FROM revisions r
                LEFT JOIN audit_events a USING(submission_id) LEFT JOIN submissions s USING(submission_id)
                WHERE r.record_id=? AND r.revision=?""", pin(entry)).fetchone()
            preparation_budget.reserve(_length_total(lengths))
        row = connection.execute("""SELECT a.event_id,r.ordinal,r.submission_id,a.committed_at,s.fingerprint
            FROM revisions r JOIN audit_events a USING(submission_id) JOIN submissions s USING(submission_id)
            WHERE r.record_id=? AND r.revision=?""", pin(entry)).fetchone()
        if row is None or dict(zip(("submission_id", "committed_at", "fingerprint"), row[2:])) != entry["commit"]:
            raise ReportIntegrityError("captured revision commit binding mismatch")
        if not 1 <= row[0] <= snapshot["watermark"]["event_id"]:
            raise ReportIntegrityError("captured revision outside scientific watermark")
        sid = row[2]
        if sid not in verified:
            sizes = connection.execute("SELECT " + _text_length("s.request_json") + ","
                + _text_length("a.provenance_json") + """ FROM submissions s
                LEFT JOIN audit_events a USING(submission_id) WHERE s.submission_id=?""", (sid,)).fetchone()
            size = _length_total(sizes)
            if preparation_budget is not None:
                preparation_budget.reserve(size)
            remaining -= size
            if remaining < 0:
                raise SnapshotLimitError("original source submission verification exceeds metadata budget")
            text, provenance = connection.execute("""SELECT s.request_json,a.provenance_json
                FROM submissions s JOIN audit_events a USING(submission_id) WHERE submission_id=?""", (sid,)).fetchone()
            # Stored scientific content keeps its existing 64-container bound;
            # original submission/envelope wrappers add only fixed outer levels.
            document = _strict_json(text, maximum_depth=68)
            reports._fields_exact(document, "fingerprint_version submission", "source submission")
            original = Submission.from_dict(document["submission"])
            if (type(document["fingerprint_version"]) is not int or document["fingerprint_version"] != 1
                    or original.submission_id != sid
                    or _canonical({"fingerprint_version": 1, "submission": original.to_dict()}) != text
                    or hashlib.sha256(text.encode("ascii")).hexdigest() != row[4]
                    or _canonical(original.provenance.to_dict()) != provenance):
                raise ReportIntegrityError("original source submission/audit fingerprint mismatch")
            selected = {pin(r) for r in snapshot["records"] if r["commit"]["submission_id"] == sid}
            verified[sid] = {(r.record_id, r.revision): (ordinal, _canonical(r.to_dict()))
                             for ordinal, r in enumerate(original.records) if (r.record_id, r.revision) in selected}
        if verified[sid].get(pin(entry)) != (row[1], entry["envelope_json"]):
            raise ReportIntegrityError("captured revision differs from original submission ordinal/content")
        bindings.append({"record_id": entry["record_id"], "revision": entry["revision"], "event_id": row[0], "ordinal": row[1]})
    if expected is not None and _canonical(bindings) != _canonical(expected):
        raise ReportIntegrityError("saved source membership differs from actual audit rows")
    return bindings


def _report_at(store, connection, reference):
    """Resolve one historical report manifest through its original submission, never its head."""
    row = connection.execute("SELECT submission_id FROM revisions WHERE record_id=? AND revision=?", pin(reference)).fetchone()
    if row is None:
        raise ReportIntegrityError("saved report predecessor/baseline is absent")
    found = _metadata(store, connection, row[0])
    if found is None or pin(found[0].to_dict()["report_manifest"]) != pin(reference):
        raise ReportIntegrityError("baseline/predecessor is not a generated report manifest")
    return found


def _compatible(prior, request):
    """Require the report chain to preserve stable project/run identities and distinct operations."""
    if (any(prior[k]["record_id"] != request[k]["record_id"] for k in ("project", "run"))
            or prior["operation_id"] == request["operation_id"]):
        raise ReportScopeError("report predecessor/baseline belongs to a different project/run or operation")


def commit_report(store, request):
    """Commit a coherent bounded pre-report observation and all three objects in one write transaction.

    BEGIN IMMEDIATE intentionally blocks scientific and ledger writers through
    capture, rendering, object placement and shared metadata insertion. Immutable
    objects may survive rollback as unregistered orphans; they are never removed.
    After COMMIT, acknowledgment failure requires original-operation reconciliation.
    Fresh controlled-run/report reservations reject before capture or object placement.
    """
    from research_pipeline.store import SubmissionConflictError, RevisionConflictError
    from research_pipeline.schema import validate_request_kinds
    from research_pipeline.resource_ledger import _inspect, _check_references
    request = reports.loads_request(reports.dumps_request(request)).to_dict()
    _require_schema(store)
    with store._transaction(write=True, reconciliation_id="operation_id") as connection:
        # Retry before availability: do not observe new state or require old bytes.
        found = _metadata(store, connection, request["operation_id"])
        if found is not None:
            if _canonical(request) != _canonical(found[1]):
                raise SubmissionConflictError("report operation ID has a different canonical request")
            return found[0]
        from research_pipeline.run_control_store import guard_report
        guard_report(connection, request)
        watermark = connection.execute("SELECT max(event_id) FROM audit_events").fetchone()[0]
        _fault("after_first_read")
        observed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        mid = manifest_id(request["run"]["record_id"])
        for identity, expected, kind in ((mid, request["report_revision"] - 1, "work_product_manifest"),
                                         (source_id(request["operation_id"]), 0, "event")):
            row = connection.execute("SELECT head,kind FROM identities WHERE record_id=?", (identity,)).fetchone()
            if (row[0] if row else 0) != expected or row is not None and row[1] != kind:
                raise RevisionConflictError("report identity/kind/head collision: " + identity)
        if request["report_revision"] > 1:
            previous = _report_at(store, connection, {"record_id": mid, "revision": request["report_revision"] - 1})
            _compatible(previous[1], request)
        baseline = request["start_baseline"]
        if "record_id" in baseline:
            prior = _report_at(store, connection, baseline)
            _compatible(prior[1], request)
            if prior[1]["report_revision"] >= request["report_revision"]:
                raise ReportScopeError("start baseline must be an earlier saved report")
            baseline = {"reference": baseline, "observation": _read(store, connection, prior[1]["operation_id"],
                         maximum=request["limits"]["max_source_bytes"]).to_dict()}
        if store._schema_version == 3:
            complete = _inspect(connection, ResourceInspectionLimits(**request["limits"]["resources"])).to_dict()
            resources = reports._project_resources(complete, request)
            for item in resources["operations"]:
                _check_references(connection, item["request"], item["receipt"]["scientific_watermark_event_id"])
        else:
            resources = unavailable("Schema 2: resource accounting unavailable; explicit migration to schema 3 is required.")
        _fault("between_resource_and_scientific")
        categories = reports._root_categories(request, resources)
        keys = list(dict.fromkeys(pin(ref) for refs in categories.values() for ref in refs))
        selection = SnapshotSelection(RootSelector(*keys[0]), tuple(RootSelector(*key) for key in keys[1:]))
        scientific = store._capture_snapshot(connection, selection, SnapshotLimits(**request["limits"]["snapshot"])).to_dict()
        if scientific["watermark"]["event_id"] != watermark:
            raise ReportIntegrityError("scientific watermark changed inside report transaction")
        body = {"format": "research_pipeline.report_observation", "version": 2, "request": request,
                "observed_at": observed_at, "scientific": scientific, "resources": resources, "baseline": baseline,
                "root_categories": categories, "source_bindings": _verify_bindings(store, connection, scientific),
                "qualifications": QUALIFICATIONS}
        # Hash only the saved observation, excluding future receipt and generated
        # artifact hashes. The source-before-report watermark avoids circular IDs.
        encoded = reports._encode(body, request["limits"]["max_source_bytes"], "source observation")
        observation = ReportObservation({**body, "snapshot_id": hashlib.sha256(encoded.encode("ascii")).hexdigest()})
        outputs = reports.render_report(observation)
        outputs = {"source.json": reports.dumps_observation(observation).encode("ascii"), **outputs}
        _fault("before_artifacts")
        artifacts = {name: store.put_artifact(data) for name, data in outputs.items()}
        _fault("after_artifacts")
        submission = store._normalize_submission(_submission(observation.to_dict(), artifacts))
        validate_request_kinds(submission, store._schema_version)
        store._check_batch(connection, submission)
        # Only the manifest enters the existing typed validator. The event's
        # closed report grammar is checked above; generic typed admission stays closed.
        manifest = submission.records[1]
        typed = Submission(submission.submission_id, submission.provenance, (manifest,),
                           {manifest.record_id: request["report_revision"] - 1})
        store._check_typed_targets(connection, typed, (decode_envelope(manifest),), report_source=submission.records[0])
        canonical = reports._encode({"fingerprint_version": 1, "submission": submission.to_dict()}, REPORT_BYTES, "report submission")
        receipt = store._insert_submission(connection, submission, canonical, hashlib.sha256(canonical.encode("ascii")).hexdigest())
        result = _result(submission.records[0], receipt)
    _fault("after_commit")
    return result


def get_report_operation(store, operation_id):
    """Return validated original committed metadata or None without recapture or object reads."""
    _identifier(operation_id, "operation_id")
    _require_schema(store)
    with store._transaction(reconciliation_id="operation_id") as connection:
        found = _metadata(store, connection, operation_id)
        return None if found is None else found[0]


def read_report(store, operation_id):
    """Read and verify exact committed source and deterministic outputs; damaged bytes fail explicitly."""
    _identifier(operation_id, "operation_id")
    _require_schema(store)
    with store._transaction(reconciliation_id="operation_id") as connection:
        return _read(store, connection, operation_id)


def prepare_report_view(source: "RecordStore", operation_id: str, *, limits: SnapshotLimits) -> "ReadablePlan":
    """Prepare one exact committed operation and its complete report chain without writes.

    One read transaction verifies original submission/source/output bindings. No
    current heads, resource observations, clock or report commit are consulted.
    Actual stored fields are preflighted against shared metadata and reference
    allowances across the entire chain, before reconstruction or JSON decoding.
    Caller allowances independently bound metadata reads, retained history and
    physical output; embedded capture limits cannot enlarge them. The returned
    ReadablePlan must be independently retained before filesystem publication.
    """
    from research_pipeline.domain import DomainValidationError
    from research_pipeline.store import RecordStore, RecordNotFoundError
    from research_pipeline.snapshot import DetachedSnapshot
    from research_pipeline.view_capture import _Metadata
    from research_pipeline.report_view import plan_report_snapshot, _within, report_directory
    if type(source) is not RecordStore or type(limits) is not SnapshotLimits:
        raise DomainValidationError("expected RecordStore and SnapshotLimits")
    limits = SnapshotLimits(**limits.to_dict())
    _identifier(operation_id, "operation_id")
    _require_schema(source)
    budget = _Metadata(limits.max_metadata_bytes)
    entries, seen, total_bytes = [], set(), 0
    remaining_references = [limits.max_references]
    with source._transaction(reconciliation_id="operation_id") as connection:
        current = operation_id
        while True:
            if current in seen or len(entries) >= limits.max_records:
                raise SnapshotLimitError("complete report history exceeds count allowance")
            seen.add(current)
            found = _metadata(source, connection, current, preparation_limits=limits,
                              preparation_budget=budget, remaining_references=remaining_references)
            if found is None:
                raise RecordNotFoundError("report operation not found: " + current)
            result, request, _ = found
            if any(value > limits.to_dict()[key] for key, value in request["limits"]["snapshot"].items()):
                raise SnapshotLimitError("original snapshot allowances exceed caller limits before source fetch")
            result_doc = result.to_dict()
            budget.reserve(len(_canonical(result_doc)))
            if 3 * len(seen) > limits.max_artifacts:
                raise SnapshotLimitError("history artifact copies exceed caller allowance")
            report_directory({"observation": {"request": request}})
            for artifact in result_doc["artifacts"].values():
                total_bytes += artifact["size"]
                if artifact["size"] > limits.max_file_bytes or total_bytes > limits.max_total_bytes:
                    raise SnapshotLimitError("required report objects exceed caller allowance before fetch")
            budget.reserve(result_doc["artifacts"]["source.json"]["size"])
            observation = _read(source, connection, current, maximum=limits.max_file_bytes,
                                found=found, preparation_budget=budget, remaining_references=remaining_references)
            value = observation.to_dict()
            _within(value, limits)
            entries.append(dict(result=result_doc, observation=value))
            if request["report_revision"] == 1:
                break
            predecessor = value["root_categories"]["previous_report"]
            if len(predecessor) != 1:
                raise ReportIntegrityError("missing exact report predecessor")
            lengths = connection.execute("SELECT " + _text_length("submission_id")
                + " FROM revisions WHERE record_id=? AND revision=?", pin(predecessor[0])).fetchone()
            budget.reserve(_length_total(lengths))
            row = connection.execute("SELECT submission_id FROM revisions WHERE record_id=? AND revision=?", pin(predecessor[0])).fetchone()
            current = row[0]
        entries.reverse()
        snapshot = DetachedSnapshot(entries[-1]["observation"]["scientific"])
        # Verify every historical evidence object, not only generated outputs.
        for artifact in snapshot.to_dict()["artifacts"]:
            source._artifacts.verify(reports.ArtifactReference(artifact["digest"], artifact["size"]))
        return plan_report_snapshot(snapshot, entries, limits=limits)
