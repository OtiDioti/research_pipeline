"""Strict committed report declarations and deterministic, inert saved-state rendering."""

from dataclasses import dataclass
import hashlib
import json
import math

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, Submission, SubmissionReceipt, _fields, _identifier, _integer, _timestamp,
    _validate_json_string,
)
from research_pipeline.work_product import WorkProductFile, WorkProductManifest, encode_envelope
from research_pipeline.project import AttributedText
from research_pipeline.source import DeclaredText
from research_pipeline.snapshot import DetachedSnapshot, SnapshotLimits, _canonical, _json_parts
from research_pipeline.resources import ResourceInspectionLimits, ResourceRequest, ResourceReceipt, amounts, vector

REQUEST_BYTES = 256 * 1024
REPORT_BYTES = 64 * 1024 * 1024
_EMPTY_RESULTS = "No result was established by this report."
# result.receipt.provenance adds one fixed container to request.provenance's 32-container bound.
_RESULT_MAXIMUM_DEPTH = 33
OUTCOMES = ("objective_met", "partial_progress", "unresolved", "stopped", "not_yet_assessed")
QUALIFICATIONS = [
    "Bounded caller-selected outgoing closure; uncaptured records are unknown.",
    "Membership without an explicit ownership contract is caller-selected and unauthenticated.",
    "Authenticated admission and authority unavailable: no operating-authority contract exists.",
    "Verified operational stopping unavailable: a declaration cannot establish execution stopped.",
    "Complete job inventory and termination unavailable: no operational job inventory exists.",
    "Reading this report or its saved continuation never authorizes action.",
    "Generic payloads are opaque descriptive data; typed interpretation may be unavailable.",
    "Resource estimates and protected capacity are declarations, not permission or available capacity.",
]


class ReportLimitError(ValueError):
    """A complete request, retained observation or output exceeds its report byte budget."""


class ReportScopeError(ValueError):
    """Exact requested records or resource accounts contradict the declared project/run scope."""


class ReportIntegrityError(ValueError):
    """Retained report identities, bindings or derived projections are inconsistent."""


def _fields_exact(value, names, label):
    """Require an ordinary closed object with every named field present."""
    return _fields(value, set(names.split()), set(), label)


def _text(value):
    """Require nonblank authored scalar text within the report-specific character bound."""
    if type(value) is not str or not value.strip() or len(value) > 4096:
        raise DomainValidationError("report text: expected 1–4096 nonblank characters")
    _validate_json_string(value, "report text")
    return value


def _tree(value, depth=0, maximum_depth=32):
    """Preflight exact JSON types, finite numbers and bounded nesting before serialization."""
    kind = type(value)
    if kind in (dict, list):
        if depth >= maximum_depth:
            raise DomainValidationError("report JSON nesting exceeded")
        if kind is dict:
            for key, child in value.items():
                if type(key) is not str:
                    raise DomainValidationError("report object keys must be ordinary strings")
                _validate_json_string(key, "report key")
                _tree(child, depth + 1, maximum_depth)
        else:
            for child in value:
                _tree(child, depth + 1, maximum_depth)
    elif kind is str:
        _validate_json_string(value, "report JSON")
    elif kind is float:
        if not math.isfinite(value):
            raise DomainValidationError("nonfinite report number")
    elif value is not None and kind not in (bool, int):
        raise DomainValidationError("report JSON requires ordinary values")


def _encode(value, maximum, label):
    """Encode canonical JSON incrementally, failing rather than truncating complete data."""
    chunks, size = [], 0
    for chunk in _json_parts(value):
        size += len(chunk)
        if size > maximum:
            raise ReportLimitError(label + " exceeds byte budget")
        chunks.append(chunk)
    return "".join(chunks)


def _pairs(pairs):
    """Reject duplicate keys before a JSON object can discard their evidence."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError("duplicate report field: " + key)
        result[key] = value
    return result


def _constant(value):
    """Reject nonfinite literals during decoding."""
    raise DomainValidationError("nonfinite report literal: " + value)


def _loads(data, maximum=REPORT_BYTES, depth=40):
    """Bound bytes and nesting before parsing strict UTF-8 with duplicate detection."""
    from research_pipeline.snapshot import _check_json_depth
    if type(data) not in (str, bytes):
        raise DomainValidationError("report JSON requires ordinary str or bytes")
    if len(data) > maximum:
        raise ReportLimitError("report JSON exceeds byte budget")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8")
        if len(data.encode("utf-8")) > maximum:
            raise ReportLimitError("report JSON exceeds byte budget")
        _validate_json_string(data, "report JSON")
        _check_json_depth(data, depth)
        value = json.loads(data, object_pairs_hook=_pairs, parse_constant=_constant)
        _tree(value, maximum_depth=depth)
        return value
    except (DomainValidationError, ReportLimitError):
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError("invalid report JSON") from error


def _array(value, maximum=128, minimum=0):
    """Validate an ordered ordinary bounded declaration list without reordering it."""
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise DomainValidationError(f"report array requires {minimum}–{maximum} entries")
    return value


def _declared(value, *, unknown=False):
    """Reuse DeclaredText while enforcing the report text bound and explicit unknowns."""
    result = DeclaredText.from_dict(value).to_dict()
    _text(result["value"] if result["value"] is not None else result["unknown_reason"])
    if unknown and result["value"] is not None:
        raise DomainValidationError("expected an explicit unavailable reason")
    return result


def unavailable(reason):
    """Build the closed explicit-unavailability value used by report unions."""
    return _declared({"value": None, "unknown_reason": reason}, unknown=True)


def _attributed(value):
    """Validate authored narrative and require known attribution for known text."""
    result = AttributedText.from_dict(value).to_dict()
    for field in ("text", "attribution"):
        _declared(result[field])
    if result["text"]["value"] is not None and result["attribution"]["value"] is None:
        raise DomainValidationError("known report text requires known attribution")
    return result


def _reference(value, role=None, kinds=None):
    """Validate a complete exact pin and its prescribed semantic role and target kind."""
    _fields_exact(value, "record_id revision relationship target_kind", "report reference")
    result = RecordReference.from_dict(value)
    if (result.target_kind is None or (role is not None and result.relationship != role)
            or (kinds is not None and result.target_kind not in kinds)):
        raise DomainValidationError("report reference role/kind mismatch")
    return result.to_dict()


def _optional_reference(value, role, kind):
    """Accept exactly an exact reference or a DeclaredText unavailable reason."""
    if type(value) is dict and "record_id" in value:
        return _reference(value, role, (kind,))
    return _declared(value, unknown=True)


def _references(values, role=None, kinds=None, maximum=32, minimum=0, *, unique_identity=False):
    """Check exact reference lists; only original selection forbids multiple revisions per identity."""
    refs = [_reference(v, role, kinds) for v in _array(values, maximum, minimum)]
    keys = [r["record_id"] if unique_identity else (r["record_id"], r["revision"]) for r in refs]
    if len(set(keys)) != len(keys):
        raise DomainValidationError("duplicate/conflicting report reference selection")
    kinds_by_id = {}
    for ref in refs:
        if kinds_by_id.setdefault(ref["record_id"], ref["target_kind"]) != ref["target_kind"]:
            raise DomainValidationError("conflicting kinds for a stable reference identity")
    return refs


def _limits(value):
    """Validate explicit inherited capture budgets and the three hard report byte ceilings."""
    _fields_exact(value, "snapshot resources max_source_bytes max_output_file_bytes max_output_total_bytes", "report limits")
    snapshot = SnapshotLimits(**_fields_exact(value["snapshot"],
        "max_roots max_records max_references max_record_bytes max_metadata_bytes max_artifacts max_files max_file_bytes max_total_bytes", "snapshot limits"))
    ResourceInspectionLimits(**_fields_exact(value["resources"], "max_accounts max_operations max_metadata_bytes", "resource limits"))
    for key in ("max_source_bytes", "max_output_file_bytes", "max_output_total_bytes"):
        _integer(value[key], key, 1)
        if value[key] > REPORT_BYTES:
            raise ReportLimitError(key + " exceeds 64 MiB")
    return {**value, "snapshot": snapshot.to_dict()}


def _declarations(value):
    """Check every closed narrative, exact evidence and saved continuation declaration."""
    _fields_exact(value, "objective scope outcome interpretation stop_reason results completed_checks unresolved_issues saved_work outstanding_jobs gaps continuation reproduction limitations", "declarations")
    for key in ("objective", "scope"):
        _attributed(value[key])
    for key in ("interpretation", "stop_reason"):
        if type(value[key]) is dict and "text" in value[key]:
            _attributed(value[key])
        else:
            _declared(value[key], unknown=True)
    outcome = _fields_exact(value["outcome"], "label explanation attribution", "outcome")
    if type(outcome["label"]) is not str or outcome["label"] not in OUTCOMES:
        raise DomainValidationError("unsupported attributed outcome")
    _attributed({"text": outcome["explanation"], "attribution": outcome["attribution"]})
    if _declared(outcome["attribution"])["value"] is None:
        raise DomainValidationError("outcome label requires known attribution")
    for entry in _array(value["results"]):
        _fields_exact(entry, "statement supporting_references", "result")
        _attributed(entry["statement"])
        _references(entry["supporting_references"], minimum=1)
    for entry in _array(value["completed_checks"]):
        _fields_exact(entry, "evidence description", "completed check")
        _reference(entry["evidence"], "reported_evidence", ("evidence",))
        _attributed(entry["description"])
    for entry in _array(value["unresolved_issues"]):
        if type(entry) is dict and "record_id" in entry:
            _reference(entry, "unresolved_issue", ("issue",))
        else:
            _attributed(entry)
    for entry in _array(value["saved_work"]):
        _fields_exact(entry, "manifest description state", "saved work")
        _reference(entry["manifest"], "saved_work", ("work_product_manifest",))
        _attributed(entry["description"])
        if entry["state"] not in ("saved", "incomplete", "checkpoint"):
            raise DomainValidationError("invalid saved work state")
    for entry in _array(value["outstanding_jobs"]):
        _fields_exact(entry, "reference description state", "outstanding job")
        _reference(entry["reference"], "outstanding_job", ("attempt", "tool_execution"))
        _attributed(entry["description"])
        if entry["state"] not in ("outstanding", "uncertain"):
            raise DomainValidationError("invalid declared job state")
    for key in ("gaps", "limitations"):
        for entry in _array(value[key]):
            _attributed(entry)
    plan = value["continuation"]
    if type(plan) is list:
        previous = 0
        for entry in _array(plan, minimum=1):
            _fields_exact(entry, "priority task checkpoint dependencies expected_output required_checks required_authority required_resources", "continuation item")
            _integer(entry["priority"], "priority", 1)
            if entry["priority"] <= previous:
                raise DomainValidationError("continuation priorities must increase")
            previous = entry["priority"]
            _reference(entry["task"], "task", ("task_specification",))
            _optional_reference(entry["checkpoint"], "checkpoint", "work_product_manifest")
            _references(entry["dependencies"])
            for key in ("expected_output", "required_checks", "required_authority"):
                _attributed(entry[key])
            resources = entry["required_resources"]
            if type(resources) is dict and "account_id" in resources:
                _fields_exact(resources, "account_id estimates", "required resources")
                _identifier(resources["account_id"], "account_id")
                vector(resources["estimates"])
            else:
                _declared(resources, unknown=True)
    else:
        _declared(plan, unknown=True)
    _fields_exact(value["reproduction"], "procedure build environment", "reproduction")
    for item in value["reproduction"].values():
        _attributed(item)


def _request(value):
    """Normalize a complete bounded version-1 request without resolving live records."""
    _tree(value)
    _encode(value, REQUEST_BYTES, "request")
    _fields_exact(value, "format version operation_id report_revision provenance authors project run context selection start_baseline declarations limits", "report request")
    if value["format"] != "research_pipeline.report_request" or type(value["version"]) is not int or value["version"] != 1:
        raise DomainValidationError("unsupported report request format/version")
    _identifier(value["operation_id"], "operation_id")
    _integer(value["report_revision"], "report_revision", 1)
    _fields_exact(value["provenance"], "actor created_at details", "report provenance")
    provenance = CreationProvenance.from_dict(value["provenance"]).to_dict()
    for author in _array(value["authors"], 32, 1):
        _text(author)
    _reference(value["project"], "project", ("project",))
    _reference(value["run"], "run", ("run",))
    _optional_reference(value["context"], "context", "research_context")
    _references(value["selection"], "report_selection", maximum=128, unique_identity=True)
    _optional_reference(value["start_baseline"], "start_baseline", "work_product_manifest")
    _declarations(value["declarations"])
    _limits(value["limits"])
    normalized = {**value, "provenance": provenance}
    # Timestamp normalization can increase bytes; the persisted form owns the bound.
    _encode(normalized, REQUEST_BYTES, "normalized request")
    return normalized


@dataclass(frozen=True, init=False)
class ReportRequest:
    """A detached closed declaration; known authored text is attributed, never authenticated."""

    _json: str

    def __init__(self, value):
        """Validate a complete wire object and retain canonical request bytes only."""
        try:
            object.__setattr__(self, "_json", _encode(_request(value), REQUEST_BYTES, "request"))
        except (TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise DomainValidationError("malformed report request") from error

    @classmethod
    def from_dict(cls, value):
        """Reconstruct every request field, including nested bounds and union semantics."""
        if cls is not ReportRequest:
            raise DomainValidationError("expected exact ReportRequest")
        return cls(value)

    def to_dict(self):
        """Return isolated revalidated data, rejecting forged private retained state."""
        if type(self) is not ReportRequest:
            raise DomainValidationError("expected exact ReportRequest")
        try:
            value = _request(_loads(self._json, REQUEST_BYTES, 32))
        except (TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise DomainValidationError("malformed retained report request") from error
        if _canonical(value) != self._json:
            raise DomainValidationError("noncanonical retained report request")
        return value


def dumps_request(value):
    """Serialize only an exact revalidated ReportRequest at a public boundary."""
    if type(value) is not ReportRequest:
        raise DomainValidationError("expected ReportRequest")
    return _canonical(ReportRequest.to_dict(value))


def loads_request(value):
    """Decode bounded strict request JSON, including duplicate and unknown field rejection."""
    return ReportRequest(_loads(value, REQUEST_BYTES, 32))


def manifest_id(run_id):
    """Derive one stable manifest identity from the exact UTF-8 stable run identifier."""
    _identifier(run_id, "run_id")
    return "run-report-" + hashlib.sha256(run_id.encode("utf-8")).hexdigest()


def source_id(operation_id):
    """Derive the immutable revision-1 source event identity from the original operation."""
    _identifier(operation_id, "operation_id")
    return "report-source-" + hashlib.sha256(operation_id.encode("utf-8")).hexdigest()


def pin(reference):
    """Return an exact identity/revision key without erasing historical revisions."""
    return reference["record_id"], reference["revision"]


def _walk_references(value):
    """Collect references only from the already validated report declaration grammar."""
    if type(value) is dict:
        if set(value) == {"record_id", "revision", "relationship", "target_kind"}:
            yield value
        else:
            for child in value.values():
                yield from _walk_references(child)
    elif type(value) is list:
        for child in value:
            yield from _walk_references(child)


def _scientific_roots(request):
    """Preserve primary exact roots followed by original selection and declaration references."""
    roots = [request["project"], request["run"]]
    if "record_id" in request["context"]:
        roots.append(request["context"])
    roots.extend(request["selection"])
    roots.extend(_walk_references(request["declarations"]))
    return roots


def _root_categories(request, resources):
    """Derive labeled root categories without folding ledger/report context into scientific work."""
    from research_pipeline.resource_ledger import references
    previous = []
    if request["report_revision"] > 1:
        previous = [RecordReference(manifest_id(request["run"]["record_id"]), request["report_revision"] - 1,
                                    "supersedes", "work_product_manifest").to_dict()]
    baseline = [request["start_baseline"]] if "record_id" in request["start_baseline"] else []
    ledger = []
    if "operations" in resources:
        for item in resources["operations"]:
            ledger.extend(references(item["request"]))
    return {"scientific": _scientific_roots(request), "saved_baseline": baseline,
            "previous_report": previous, "resource_evidence": ledger}


def _scope_match(account, kind, identity):
    """Match only record-scoped stable identities; controller names are not record links."""
    scope = account["scope"]
    return scope["type"] == "record" and scope["kind"] == kind and scope["reference"]["record_id"] == identity


def _resource_scope(state, request):
    """Describe the selected complete project tree and distinguish its exact reported run subtree."""
    accounts = state["accounts"]
    roots = [a["account_id"] for a in accounts.values() if _scope_match(a, "project", request["project"]["record_id"])]
    runs = [a["account_id"] for a in accounts.values() if _scope_match(a, "run", request["run"]["record_id"])]
    if len(roots) > 1 or len(runs) > 1:
        raise ReportIntegrityError("ambiguous project/run resource accounts")
    run_ids = []
    if runs:
        for aid, account in accounts.items():
            current = account
            while current is not None:
                if current["account_id"] == runs[0]:
                    run_ids.append(aid)
                    break
                current = accounts.get(current["parent_account_id"])
    return {"project_account": roots[0] if roots else unavailable("No recorded record-scoped project account; usage and admission are unknown."),
            "run_account": runs[0] if runs else unavailable("No record-scoped account matches the reported run; controller names cannot establish linkage."),
            "run_subtree": sorted(run_ids),
            "controller_run_linkage": [{"account_id": a["account_id"], "linkage": unavailable("Controller identity is not an exact run record reference.")}
                for a in sorted(accounts.values(), key=lambda a: a["account_id"])
                if a["scope"]["kind"] == "run" and a["scope"]["type"] == "controller"]}


def _project_resources(snapshot, request, *, _source_budget=None):
    """Project complete relevant history, retaining original sequences and receipts.

    A private source budget measures the full wrapper before retaining the new
    projection. Legacy callers retain their original format and default behavior.
    """
    from research_pipeline.resource_ledger import _empty_state, _admit, _projections, _balances
    accounts = {a["account_id"]: a for a in snapshot["accounts"]}
    roots = [a["account_id"] for a in accounts.values() if _scope_match(a, "project", request["project"]["record_id"])]
    selected = set(roots)
    for aid, account in accounts.items():
        current = account
        while current["parent_account_id"] is not None:
            current = accounts[current["parent_account_id"]]
        if current["account_id"] in selected:
            selected.add(aid)
    primary_ids = {r["record_id"] for r in _scientific_roots(request) if r["target_kind"] in ("run", "task_specification")}
    for aid, account in accounts.items():
        if (account["scope"]["type"] == "record" and account["scope"]["reference"]["record_id"] in primary_ids
                and aid not in selected):
            raise ReportScopeError("primary run/task resource account belongs to another project")
    operations = [item for item in snapshot["operations"] if item["receipt"]["account_id"] in selected]
    state = _empty_state()
    for item in operations:
        _admit(state, item["request"])
    projected, balances, scope = _projections(state), _balances(state), _resource_scope(state, request)
    if _source_budget is not None:
        _source_budget.projection(projected, balances, scope, operations, request, snapshot)
    return {"format": "research_pipeline.report_resources", "version": 1,
            "project": request["project"], "run": request["run"],
            "resource_sequence": snapshot["resource_sequence"], "complete_snapshot_id": snapshot["snapshot_id"],
            "operations": operations, **projected, "balances": balances,
            "scope": scope, "limits": request["limits"]["resources"]}


def _validate_resources(value, request, schema):
    """Replay the complete selected project history with original noncontiguous sequence numbers."""
    from research_pipeline.resource_ledger import _empty_state, _admit, _receipt, _projections, _balances, _root
    if schema == 2:
        if value != unavailable("Schema 2: resource accounting unavailable; explicit migration to schema 3 is required."):
            raise ReportIntegrityError("schema-2 resource unavailability mismatch")
        return
    if schema != 3:
        raise ReportIntegrityError("reports require schema 2 or 3")
    _fields_exact(value, "format version project run resource_sequence complete_snapshot_id operations accounts allocations reservations reservation_usage breaches balances scope limits", "report resources")
    if value["format"] != "research_pipeline.report_resources" or type(value["version"]) is not int or value["version"] != 1:
        raise ReportIntegrityError("unsupported report resource projection")
    for key in ("project", "run"):
        if _canonical(value[key]) != _canonical(request[key]):
            raise ReportIntegrityError("resource projection scope mismatch")
    if _canonical(value["limits"]) != _canonical(request["limits"]["resources"]):
        raise ReportIntegrityError("resource limits mismatch")
    _integer(value["resource_sequence"], "resource_sequence", 0)
    ArtifactReference(value["complete_snapshot_id"], 0)
    limits = ResourceInspectionLimits(**value["limits"])
    operations = _array(value["operations"], limits.max_operations)
    state, previous, watermark, ops, receipts = _empty_state(), 0, 0, set(), set()
    for item in operations:
        _fields_exact(item, "request receipt", "report resource operation")
        req = ResourceRequest.from_dict(item["request"])
        receipt = ResourceReceipt.from_dict(item["receipt"])
        doc, result = req.to_dict(), receipt.to_dict()
        if (_canonical(doc) != _canonical(item["request"]) or _canonical(result) != _canonical(item["receipt"])
                or not previous < result["sequence"] <= value["resource_sequence"]
                or result["scientific_watermark_event_id"] < watermark
                or doc["operation_id"] in ops or doc["receipt_id"] in receipts
                or receipt != _receipt(doc, req.fingerprint, result["sequence"], result["committed_at"], result["scientific_watermark_event_id"])):
            raise ReportIntegrityError("resource receipt/sequence mismatch")
        _admit(state, doc)
        previous, watermark = result["sequence"], result["scientific_watermark_event_id"]
        ops.add(doc["operation_id"])
        receipts.add(doc["receipt_id"])
    if len(state["accounts"]) > limits.max_accounts:
        raise ReportIntegrityError("project account count exceeds limits")
    for account in state["accounts"].values():
        root = state["accounts"][_root(state, account)]
        if not _scope_match(root, "project", request["project"]["record_id"]):
            raise ReportScopeError("resource projection contains another project")
    expected = {**_projections(state), "balances": _balances(state), "scope": _resource_scope(state, request)}
    for key, item in expected.items():
        if _canonical(value[key]) != _canonical(item):
            raise ReportIntegrityError("resource projection mismatch: " + key)
    _encode(value, limits.max_metadata_bytes, "report resource projection")


def _envelopes(snapshot):
    """Reconstruct exact captured envelopes; DetachedSnapshot has already validated their JSON."""
    return {pin(entry): RecordEnvelope.from_dict(json.loads(entry["envelope_json"])) for entry in snapshot["records"]}


def _closure(roots, envelopes, *, bounds=None):
    """Derive scientific membership without treating report bookkeeping as scientific changes.

    The saved DetachedSnapshot still contains the entire outgoing closure. This
    narrower presentation/comparison walk stops at report artifacts and source
    events so their retained ledger/history dependencies do not become results.
    Lifecycle callers supply (root occurrences, records, reference occurrences)
    ceilings. The internal root-occurrence bound differs from SnapshotLimits.max_roots,
    which counts distinct selection pins. Inventory is checked before traversal
    containers are allocated; legacy callers retain their historical unbounded behavior.
    """
    if bounds is not None:
        max_root_occurrences, max_records, max_references = bounds
        if len(roots) > max_root_occurrences or len(envelopes) > max_records:
            raise ReportLimitError("closure inventory ceiling exceeded")
        references = 0
        for envelope in envelopes.values():
            references += len(envelope.record_references) + len(envelope.artifact_references)
            if references > max_references:
                raise ReportLimitError("closure reference ceiling exceeded")
    pending, reached, visited = [], set(), set()
    root_count = edge_count = 0
    for root in roots:
        root_count += 1
        if bounds is not None and root_count > max_root_occurrences:
            raise ReportLimitError("closure root ceiling exceeded")
        pending.append(pin(root))
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        if key not in envelopes:
            raise ReportIntegrityError("missing required report closure record")
        envelope = envelopes[key]
        content = envelope.content
        if ((envelope.kind == "event" and content.get("format") == "research_pipeline.report_source")
                or (envelope.kind == "work_product_manifest" and content.get("format") == "research_pipeline.work_product_content"
                    and content.get("product_kind") == "end_of_run_report")):
            continue
        reached.add(key)
        for ref in envelope.record_references:
            edge_count += 1
            if bounds is not None and edge_count > max_references:
                raise ReportLimitError("closure traversal ceiling exceeded")
            pending.append((ref.record_id, ref.revision))
    return reached


def _check_scope(request, snapshot, resources, *, closure_bounds=None):
    """Check ownership and typed declarations, using explicit bounded lifecycle traversal when supplied."""
    from research_pipeline.store import _decode_typed_envelope
    from research_pipeline.work_product import WorkProductManifest
    from research_pipeline.scientific import Evidence
    envelopes = _envelopes(snapshot)
    roots = _scientific_roots(request)
    for ref in roots:
        target = envelopes.get(pin(ref))
        if target is None or target.kind != ref["target_kind"]:
            raise ReportScopeError("required report reference absent or wrong kind")
    run = envelopes[pin(request["run"])]
    project_id, run_id = request["project"]["record_id"], request["run"]["record_id"]
    projects = [r for r in run.record_references if r.relationship == "project"]
    if not projects or any(r.target_kind != "project" or r.record_id != project_id for r in projects):
        raise ReportScopeError("primary run requires an exact project link to the selected stable project")
    for envelope in envelopes.values():
        if envelope.kind == "project" and envelope.record_id != project_id:
            raise ReportScopeError("different project in required closure")
        for ref in envelope.record_references:
            if ref.relationship == "project" and (ref.target_kind != "project" or ref.record_id != project_id):
                raise ReportScopeError("cross-project ownership edge")
    closure = _closure(roots, envelopes, bounds=closure_bounds)
    primary = {pin(r) for r in roots}
    for key in primary | closure:
        envelope = envelopes[key]
        if envelope.kind == "run" and envelope.record_id != run_id:
            raise ReportScopeError("sibling runs are allowed only as resource context")
        for ref in envelope.record_references:
            if ref.relationship == "run" and (ref.target_kind != "run" or ref.record_id != run_id):
                raise ReportScopeError("selected work explicitly belongs to a different run")
            if (key in primary and ref.relationship == "context"
                    and "record_id" in request["context"] and ref.record_id != request["context"]["record_id"]):
                raise ReportScopeError("selected work explicitly names a different context")
    for ref in roots:
        if "record_id" in request["context"] and pin(ref) == pin(request["context"]):
            _decode_typed_envelope(envelopes[pin(ref)])
    declarations = request["declarations"]
    for entry in declarations["completed_checks"]:
        if type(_decode_typed_envelope(envelopes[pin(entry["evidence"])])) is not Evidence:
            raise ReportIntegrityError("completed check requires typed Evidence")
    for entry in declarations["unresolved_issues"]:
        if "record_id" in entry:
            _decode_typed_envelope(envelopes[pin(entry)])
    work = [(entry["manifest"], entry["state"] == "checkpoint") for entry in declarations["saved_work"]]
    if type(declarations["continuation"]) is list:
        work.extend((entry["checkpoint"], True) for entry in declarations["continuation"] if "record_id" in entry["checkpoint"])
        accounts = {a["account_id"]: a for a in resources.get("accounts", [])}
        for entry in declarations["continuation"]:
            estimate = entry["required_resources"]
            if "account_id" in estimate:
                account = accounts.get(estimate["account_id"])
                if account is None:
                    raise ReportScopeError("estimate requires an included resource account")
                amounts(estimate["estimates"], account["dimensions"])
    for ref, checkpoint in work:
        value = _decode_typed_envelope(envelopes[pin(ref)])
        if type(value) is not WorkProductManifest or checkpoint and value.product_kind != "checkpoint":
            raise ReportIntegrityError("saved work/checkpoint requires the declared typed manifest kind")


def _artifact_map(value):
    """Validate exactly the three generated immutable objects without opening their bytes."""
    _fields_exact(value, "source.json report.md continuation.json", "report artifacts")
    artifacts = {name: ArtifactReference.from_dict(ref) for name, ref in value.items()}
    sizes = {}
    for artifact in artifacts.values():
        if sizes.setdefault(artifact.digest, artifact.size) != artifact.size:
            raise ReportIntegrityError("generated artifact digest has contradictory sizes")
    return artifacts


def _manifest(request, artifacts):
    """Build the one prescribed typed manifest using established roles and exact historical pins."""
    context = request["context"]
    revision = request["report_revision"]
    identity = manifest_id(request["run"]["record_id"])
    content = WorkProductManifest(
        product_kind="end_of_run_report", title="Committed run state report",
        purpose="Dated controller-generated state observation; reading never authorizes continuation.",
        authors=tuple(request["authors"]), task=None, branch=None,
        context=RecordReference.from_dict(context) if "record_id" in context else None,
        run=RecordReference.from_dict(request["run"]), linked_claims=(), linked_sources=(),
        supersedes=RecordReference(identity, revision - 1, "supersedes", "work_product_manifest") if revision > 1 else None,
        build_dependencies=(RecordReference(source_id(request["operation_id"]), 1, "build_dependency", "event"),
                            RecordReference(*pin(request["project"]), "build_dependency", "project")),
        files=tuple(WorkProductFile(name, artifacts[name]) for name in ("source.json", "report.md", "continuation.json")),
        entry_file="report.md", limitations=tuple(QUALIFICATIONS))
    return encode_envelope(identity, revision, content, CreationProvenance.from_dict(request["provenance"]))


def _submission(observation, artifacts):
    """Bind a saved observation and every historical artifact to one mixed event/manifest batch."""
    request = observation["request"]
    manifest = _manifest(request, artifacts)
    manifest_ref = RecordReference(manifest.record_id, manifest.revision, "report_manifest", "work_product_manifest")
    payload = {"format": "research_pipeline.report_source", "version": 1,
               "request": request, "snapshot_id": observation["snapshot_id"], "observed_at": observation["observed_at"],
               "artifacts": {name: artifact.to_dict() for name, artifact in artifacts.items()},
               "report_manifest": manifest_ref.to_dict()}
    links = []
    for entry in observation["scientific"]["records"]:
        envelope = _envelopes({"records": [entry]})[pin(entry)]
        links.append(RecordReference(*pin(entry), "report_source_revision", envelope.kind))
    objects = {artifacts["source.json"].digest: artifacts["source.json"]}
    for entry in observation["scientific"]["artifacts"]:
        artifact = ArtifactReference(entry["digest"], entry["size"])
        old = objects.setdefault(artifact.digest, artifact)
        if old.size != artifact.size:
            raise ReportIntegrityError("historical artifact digest has contradictory sizes")
    provenance = CreationProvenance.from_dict(request["provenance"])
    event = RecordEnvelope(source_id(request["operation_id"]), 1, "event", payload, provenance,
                           (*links, manifest_ref), tuple(objects.values()))
    return Submission(request["operation_id"], provenance, (event, manifest),
                      {event.record_id: 0, manifest.record_id: request["report_revision"] - 1})


def _saved_report_binding(envelopes, reference, request, observation=None):
    """Verify retained report-chain metadata and optional baseline bytes against exact source links."""
    manifest = envelopes.get(pin(reference))
    if manifest is None:
        raise ReportIntegrityError("missing saved report manifest")
    dependencies = [r for r in manifest.record_references if r.relationship == "build_dependency" and r.target_kind == "event"]
    if len(dependencies) != 1:
        raise ReportIntegrityError("saved report requires one source event")
    event = envelopes.get((dependencies[0].record_id, dependencies[0].revision))
    if event is None:
        raise ReportIntegrityError("saved report source event is missing")
    payload = event.content
    _fields_exact(payload, "format version request snapshot_id observed_at artifacts report_manifest", "saved report source")
    if (payload["format"] != "research_pipeline.report_source" or type(payload["version"]) is not int or payload["version"] != 1
            or event.kind != "event" or event.revision != 1):
        raise ReportIntegrityError("invalid saved report source event")
    prior = ReportRequest(payload["request"]).to_dict()
    if (prior["operation_id"] == request["operation_id"] or prior["report_revision"] >= request["report_revision"]
            or any(prior[k]["record_id"] != request[k]["record_id"] for k in ("project", "run"))
            or event.record_id != source_id(prior["operation_id"])):
        raise ReportScopeError("saved report source belongs to a different project/run, operation or revision")
    artifacts = _artifact_map(payload["artifacts"])
    expected_manifest = _manifest(prior, artifacts)
    expected_ref = RecordReference(manifest.record_id, manifest.revision, "report_manifest", "work_product_manifest")
    if (_canonical(manifest.to_dict()) != _canonical(expected_manifest.to_dict())
            or _canonical(payload["report_manifest"]) != _canonical(expected_ref.to_dict())):
        raise ReportIntegrityError("saved report manifest/source binding mismatch")
    if observation is not None:
        if (_canonical(observation["request"]) != _canonical(prior)
                or observation["snapshot_id"] != payload["snapshot_id"] or observation["observed_at"] != payload["observed_at"]):
            raise ReportIntegrityError("baseline observation differs from saved source event")
        source_bytes = _canonical(observation).encode("ascii")
        if (artifacts["source.json"].digest != hashlib.sha256(source_bytes).hexdigest()
                or artifacts["source.json"].size != len(source_bytes)
                or _canonical(_submission(observation, artifacts).records[0].to_dict()) != _canonical(event.to_dict())):
            raise ReportIntegrityError("baseline bytes/closure differ from saved source event")


def _observation(value):
    """Validate either persisted rendering version with identical closed capture/baseline semantics.

    Mixed-version baselines retain their own version and source hashes; validation
    never upgrades or reinterprets an earlier observation.
    """
    _tree(value, maximum_depth=40)
    _encode(value, REPORT_BYTES, "observation")
    _fields_exact(value, "format version request observed_at scientific resources baseline root_categories source_bindings qualifications snapshot_id", "report observation")
    if value["format"] != "research_pipeline.report_observation" or type(value["version"]) is not int or value["version"] not in (1, 2):
        raise ReportIntegrityError("unsupported report observation")
    request = ReportRequest(value["request"]).to_dict()
    if _canonical(request) != _canonical(value["request"]) or _timestamp(value["observed_at"]) != value["observed_at"]:
        raise ReportIntegrityError("noncanonical request/date in observation")
    _encode(value, request["limits"]["max_source_bytes"], "source observation")
    snapshot = DetachedSnapshot(value["scientific"]).to_dict()
    if _canonical(snapshot["limits"]) != _canonical(request["limits"]["snapshot"]):
        raise ReportIntegrityError("scientific limits mismatch")
    _validate_resources(value["resources"], request, snapshot["schema"]["version"])
    categories = _root_categories(request, value["resources"])
    if _canonical(value["root_categories"]) != _canonical(categories):
        raise ReportIntegrityError("report root categories mismatch")
    roots = list(dict.fromkeys(pin(ref) for refs in categories.values() for ref in refs))
    if [pin(r) for r in snapshot["resolutions"]] != roots:
        raise ReportIntegrityError("report root resolution mismatch")
    expected_selection = {"project": {"record_id": roots[0][0], "revision": roots[0][1]},
                          "roots": [{"record_id": k[0], "revision": k[1]} for k in roots[1:]]}
    if _canonical(snapshot["selection"]) != _canonical(expected_selection):
        raise ReportIntegrityError("report cannot contain live-head selectors")
    if value["qualifications"] != QUALIFICATIONS:
        raise ReportIntegrityError("missing scope/authority qualifications")
    _check_scope(request, snapshot, value["resources"])
    bindings = value["source_bindings"]
    if type(bindings) is not list or len(bindings) != len(snapshot["records"]):
        raise ReportIntegrityError("source binding membership mismatch")
    seen, event_submissions, submission_events = set(), {}, {}
    by_pin = {}
    for binding, entry in zip(bindings, snapshot["records"]):
        _fields_exact(binding, "record_id revision event_id ordinal", "source binding")
        _identifier(binding["record_id"], "source binding record_id")
        _integer(binding["revision"], "source binding revision", 1)
        _integer(binding["event_id"], "event_id", 1)
        _integer(binding["ordinal"], "ordinal", 0)
        if pin(binding) != pin(entry) or binding["event_id"] > snapshot["watermark"]["event_id"]:
            raise ReportIntegrityError("source binding outside captured watermark")
        key = (binding["event_id"], binding["ordinal"])
        if key in seen:
            raise ReportIntegrityError("duplicate source submission membership")
        seen.add(key)
        commit = entry["commit"]
        event_id, submission_id = binding["event_id"], commit["submission_id"]
        if (event_submissions.setdefault(event_id, _canonical(commit)) != _canonical(commit)
                or submission_events.setdefault(submission_id, event_id) != event_id):
            raise ReportIntegrityError("inconsistent source submission/event bindings")
        by_pin[pin(binding)] = binding
        if entry["commit"]["submission_id"] == snapshot["watermark"]["submission_id"] and binding["event_id"] != snapshot["watermark"]["event_id"]:
            raise ReportIntegrityError("source event differs from watermark")
    from research_pipeline.resource_ledger import references
    envelopes = _envelopes(snapshot)
    for item in value["resources"].get("operations", []):
        if item["receipt"]["scientific_watermark_event_id"] > snapshot["watermark"]["event_id"]:
            raise ReportIntegrityError("resource operation is newer than scientific capture")
        for ref in references(item["request"]):
            if (envelopes[pin(ref)].kind != ref["target_kind"] or
                    by_pin[pin(ref)]["event_id"] > item["receipt"]["scientific_watermark_event_id"]):
                raise ReportIntegrityError("resource reference not visible at original watermark")
    for previous in categories["previous_report"]:
        _saved_report_binding(envelopes, previous, request)
    baseline = value["baseline"]
    if "record_id" in request["start_baseline"]:
        _fields_exact(baseline, "reference observation", "saved baseline")
        if _canonical(baseline["reference"]) != _canonical(request["start_baseline"]):
            raise ReportIntegrityError("baseline reference mismatch")
        old = _observation(baseline["observation"])
        _saved_report_binding(envelopes, baseline["reference"], request, old)
        old_request = old["request"]
        if (old_request["report_revision"] >= request["report_revision"] or
                pin(baseline["reference"]) != (manifest_id(request["run"]["record_id"]), old_request["report_revision"]) or
                any(old_request[k]["record_id"] != request[k]["record_id"] for k in ("project", "run")) or
                old["scientific"]["watermark"]["event_id"] >= snapshot["watermark"]["event_id"]):
            raise ReportIntegrityError("baseline must be an earlier saved observation for this project/run")
    elif _canonical(baseline) != _canonical(request["start_baseline"]):
        raise ReportIntegrityError("baseline unavailable reason mismatch")
    body = {k: v for k, v in value.items() if k != "snapshot_id"}
    if value["snapshot_id"] != hashlib.sha256(_canonical(body).encode("ascii")).hexdigest():
        raise ReportIntegrityError("report observation hash mismatch")
    return value


@dataclass(frozen=True, init=False)
class ReportObservation:
    """A bounded immutable pre-submission observation, revalidated independently of a live store."""

    _json: str

    def __init__(self, value):
        """Validate a complete source document, including replay and redundant identities."""
        try:
            object.__setattr__(self, "_json", _canonical(_observation(value)))
        except (TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise ReportIntegrityError("malformed report observation") from error

    def to_dict(self):
        """Revalidate retained private state and return a detached ordinary document."""
        if type(self) is not ReportObservation:
            raise DomainValidationError("expected exact ReportObservation")
        try:
            value = _observation(_loads(self._json))
        except (TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise ReportIntegrityError("malformed retained report observation") from error
        if _canonical(value) != self._json:
            raise ReportIntegrityError("noncanonical retained observation")
        return value

    @classmethod
    def from_dict(cls, value):
        """Decode either rendering version without assuming its hash proves consistency."""
        if cls is not ReportObservation:
            raise DomainValidationError("expected exact ReportObservation")
        return cls(value)


def dumps_observation(value):
    """Serialize an exact ReportObservation after semantic revalidation."""
    if type(value) is not ReportObservation:
        raise DomainValidationError("expected ReportObservation")
    return _canonical(ReportObservation.to_dict(value))


def loads_observation(value):
    """Decode bounded strict source JSON and verify internal saved-state consistency."""
    return ReportObservation(_loads(value))


def _result(value):
    """Check committed metadata and receipt membership within the 33-container wrapper bound."""
    _tree(value, maximum_depth=_RESULT_MAXIMUM_DEPTH)
    _encode(value, REQUEST_BYTES, "report result")
    _fields_exact(value, "format version operation_id source_event report_manifest snapshot_id observed_at artifacts receipt", "report result")
    if value["format"] != "research_pipeline.report_commit_result" or type(value["version"]) is not int or value["version"] != 1:
        raise ReportIntegrityError("unsupported report result")
    _identifier(value["operation_id"], "operation_id")
    _reference(value["source_event"], "report_source", ("event",))
    _reference(value["report_manifest"], "report_manifest", ("work_product_manifest",))
    if pin(value["source_event"]) != (source_id(value["operation_id"]), 1):
        raise ReportIntegrityError("source operation identity mismatch")
    ArtifactReference(value["snapshot_id"], 0)
    if _timestamp(value["observed_at"]) != value["observed_at"]:
        raise ReportIntegrityError("noncanonical observation date")
    _artifact_map(value["artifacts"])
    if sum(a["size"] for a in value["artifacts"].values()) > REPORT_BYTES:
        raise ReportLimitError("report result artifact sizes exceed hard output budget")
    receipt = SubmissionReceipt.from_dict(value["receipt"])
    if (receipt.submission_id != value["operation_id"] or
            receipt.revisions != (pin(value["source_event"]), pin(value["report_manifest"])) or
            _canonical(receipt.to_dict()) != _canonical(value["receipt"])):
        raise ReportIntegrityError("report receipt membership mismatch")
    return value


@dataclass(frozen=True, init=False)
class ReportCommitResult:
    """Original committed-source metadata and receipt; it makes no publication claim."""

    _json: str

    def __init__(self, value):
        """Validate exact outcome membership without reading artifact availability or current heads."""
        try:
            object.__setattr__(self, "_json", _canonical(_result(value)))
        except (TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise ReportIntegrityError("malformed report result") from error

    def to_dict(self):
        """Return detached metadata within 33 containers, rejecting forged retained state."""
        if type(self) is not ReportCommitResult:
            raise DomainValidationError("expected exact ReportCommitResult")
        try:
            value = _result(_loads(self._json, REQUEST_BYTES, _RESULT_MAXIMUM_DEPTH))
        except (TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise ReportIntegrityError("malformed retained report result") from error
        if _canonical(value) != self._json:
            raise ReportIntegrityError("noncanonical retained result")
        return value

    @classmethod
    def from_dict(cls, value):
        """Reconstruct the closed committed-source result contract."""
        if cls is not ReportCommitResult:
            raise DomainValidationError("expected exact ReportCommitResult")
        return cls(value)

    @property
    def receipt(self):
        """Return the original detached SubmissionReceipt for reconciliation."""
        return SubmissionReceipt.from_dict(ReportCommitResult.to_dict(self)["receipt"])


def dumps_result(value):
    """Encode exact revalidated committed metadata as canonical JSON."""
    if type(value) is not ReportCommitResult:
        raise DomainValidationError("expected ReportCommitResult")
    return _canonical(ReportCommitResult.to_dict(value))


def loads_result(value):
    """Decode strict result JSON within 256 KiB and 33 containers without reading artifacts."""
    return ReportCommitResult(_loads(value, REQUEST_BYTES, _RESULT_MAXIMUM_DEPTH))


def _changes(observation):
    """Compare original scientific selections/closures, never collapsing historical revision pins."""
    baseline = observation["baseline"]
    if "observation" not in baseline:
        return {"unavailable": baseline}
    old = baseline["observation"]
    current_roots = _scientific_roots(observation["request"])
    old_roots = _scientific_roots(old["request"])
    before = _closure(old_roots, _envelopes(old["scientific"]))
    after = _closure(current_roots, _envelopes(observation["scientific"]))
    old_selected, new_selected = {}, {}
    for refs, target, members in ((old_roots, old_selected, before), (current_roots, new_selected, after)):
        for ref in refs:
            if pin(ref) in members:
                target.setdefault(ref["record_id"], set()).add(ref["revision"])
    return {"label": "Recorded revision/selection changes; not discoveries, improvements or canonical deletions.",
            "added_exact_revisions": [list(k) for k in sorted(after - before)],
            "no_longer_selected_exact_revisions": [list(k) for k in sorted(before - after)],
            "selected_root_revisions": [{"record_id": k, "old_revisions": sorted(old_selected[k]), "new_revisions": sorted(new_selected[k])}
                for k in sorted(old_selected.keys() & new_selected.keys())]}


def _project_groups(*, declarations, context, baseline, scientific, resources,
                    root_categories, source_bindings, qualifications, fact_roots,
                    recorded_changes, authority_notice, stopping_notice, job_notice,
                    continuation_notice, closure_bounds=None):
    """Project seven validated saved-fact groups without interpreting baselines or authority.

    Callers supply explicit facts/notices and authorize reconstruction beforehand.
    The optional closure bounds are mandatory on the lifecycle path.
    """
    envelopes = _envelopes(scientific)
    selected = _closure(fact_roots, envelopes, bounds=closure_bounds)
    typed, opaque = [], []
    for entry in scientific["records"]:
        if pin(entry) not in selected:
            continue
        envelope = envelopes[pin(entry)]
        fact = {"record_id": envelope.record_id, "revision": envelope.revision, "kind": envelope.kind,
                "operational_status": envelope.operational_status, "scientific_disposition": envelope.scientific_disposition}
        if entry["classification"]["category"] == "locally_decoded":
            typed.append({**fact, "saved_typed_fields": envelope.content})
        else:
            opaque.append({**fact, "typed_interpretation": unavailable(entry["classification"]["detail"])})
    return {
        "objective_scope_context_outcome": {k: declarations[k] for k in ("objective", "scope", "outcome", "interpretation", "stop_reason")} | {
            "context": context, "operational_stop_verification": unavailable(stopping_notice),
            "admission_and_authority": unavailable(authority_notice)},
        "results_and_recorded_changes": {"results": declarations["results"], "baseline": baseline,
            "empty_results": _EMPTY_RESULTS if not declarations["results"] else None,
            "recorded_changes": recorded_changes},
        "reported_checks_and_unresolved_issues": {"reported_completed_checks": declarations["completed_checks"],
            "unresolved_issues": declarations["unresolved_issues"], "exact_typed_assessments_and_states": typed,
            "unavailable_typed_interpretations": opaque},
        "saved_work_jobs_and_gaps": {"saved_work": declarations["saved_work"], "declared_outstanding_jobs": declarations["outstanding_jobs"],
            "job_inventory_and_termination": unavailable(job_notice), "gaps": declarations["gaps"],
            "ledger_uncertainty": resources.get("reservation_usage", resources)},
        "dimensioned_resources_and_stopping_decision": {"resources": resources, "reported_stopping_decision": declarations["stop_reason"],
            "accounting_rule": "Use separate recorded balances. Never sum ancestors/descendants or add cache/reasoning telemetry to token totals.",
            "protected_capacity": QUALIFICATIONS[7]},
        "saved_prioritized_continuation": {"plan": declarations["continuation"], "authority": unavailable(authority_notice),
            "notice": continuation_notice},
        "inspection_reproduction_and_limitations": {"reproduction": declarations["reproduction"], "limitations": declarations["limitations"],
            "scope_qualifications": qualifications, "root_categories": root_categories,
            "record_routes": [{"record_id": r["record_id"], "revision": r["revision"], "commit": r["commit"], "membership": b}
                              for r, b in zip(scientific["records"], source_bindings)],
            "artifact_routes": [{"digest": a["digest"], "size": a["size"]} for a in scientific["artifacts"]]}}


def _groups(value):
    """Supply the historical projection inputs and earlier-report comparison unchanged."""
    request = value["request"]
    return _project_groups(declarations=request["declarations"], context=request["context"],
        baseline=request["start_baseline"], scientific=value["scientific"], resources=value["resources"],
        root_categories=value["root_categories"], source_bindings=value["source_bindings"],
        qualifications=value["qualifications"], fact_roots=_scientific_roots(request),
        recorded_changes=_changes(value), authority_notice=QUALIFICATIONS[2],
        stopping_notice=QUALIFICATIONS[3], job_notice=QUALIFICATIONS[4], continuation_notice=QUALIFICATIONS[5])


_HEADINGS = ("Objective, scope, exact context and attributed outcome", "Saved results and recorded revision/selection changes",
             "Reported completed checks and unresolved issues", "Saved products, incomplete work, declared jobs and gaps",
             "Dimensioned resources, protected capacity and reported stopping decision", "Saved prioritized continuation",
             "Exact inspection, reproduction and limitations")
_LEGACY_OPENING = ("This dated observation describes state immediately before its own submission. It is not indefinitely current.\n\n"
    "Outcome labels and stop reasons are attributed assessments. Operational stopping and authenticated authority remain unavailable.\n\n"
    "[Saved source](source.json) · [Saved continuation](continuation.json)\n\n")
_LEGACY_FOOTER = ("Inspect original metadata with get_report_operation(operation_id); verify retained content with read_report(operation_id). "
    "Use get_revision/get_typed_revision(record_id, revision), read_artifact(digest/size reference), or existing checkout for exact evidence. "
    "Reproduction text is inert and is never executed. Reading does not authorize continuation.\n")


def _markdown_frames(identities, groups, *, opening, navigation, footer):
    """Yield fixed prose and literal values for both sizing and the single Markdown framing engine."""
    yield "# Controller-generated state report\n\n"
    yield opening
    yield identities
    yield navigation
    for heading, facts in zip(_HEADINGS, groups.values()):
        yield "## " + heading + "\n\n"
        if facts.get("empty_results"):
            yield _EMPTY_RESULTS + "\n\n"
        yield facts
    yield footer


def _serialize_outputs(identities, groups, continuation, *, opening, navigation, footer, maximum):
    """Emit inert Markdown and canonical ASCII continuation bytes after the caller's preflight."""
    from research_pipeline.view_plan import _literal
    chunks = []
    for frame in _markdown_frames(identities, groups, opening=opening, navigation=navigation, footer=footer):
        if type(frame) is str:
            chunks.append(frame)
        else:
            chunks.extend(_literal(frame))
    return {"report.md": "".join(chunks).encode("utf-8"),
            "continuation.json": (_encode(continuation, maximum, "continuation") + "\n").encode("ascii")}


def render_report(observation):
    """Return exactly report.md and continuation.json bytes using only validated saved values.

    Persisted version 1 stays byte-identical; version 2 adds adjacent publication navigation.
    Authored data uses inert JSON literal blocks, never active Markdown. No store,
    clock, filesystem, environment, execution callback or network is consulted.
    """
    if type(observation) is not ReportObservation:
        raise DomainValidationError("expected ReportObservation")
    value = ReportObservation.to_dict(observation)
    request = value["request"]
    groups = _groups(value)
    identities = {"operation_id": request["operation_id"], "run": request["run"], "report_revision": request["report_revision"],
                  "source_event": RecordReference(source_id(request["operation_id"]), 1, "report_source", "event").to_dict(),
                  "report_manifest": RecordReference(manifest_id(request["run"]["record_id"]), request["report_revision"], "report_manifest", "work_product_manifest").to_dict(),
                  "snapshot_id": value["snapshot_id"], "observed_at": value["observed_at"],
                  "scientific_watermark": value["scientific"]["watermark"],
                  "resource_sequence": value["resources"].get("resource_sequence", value["resources"])}
    continuation = {"format": "research_pipeline.report_continuation", "version": 1, "identities": identities,
                    "saved_work": request["declarations"]["saved_work"], "groups": groups,
                    "continuation": request["declarations"]["continuation"]}
    limits = request["limits"]
    # Rendering identity is persisted: retain version-specific navigation and bytes.
    navigation = ("[Evidence navigation available in a published readable generation](README.md)\n\n"
                  if value["version"] == 2 else "")
    outputs = _serialize_outputs(identities, groups, continuation, opening=_LEGACY_OPENING,
        navigation=navigation, footer=_LEGACY_FOOTER, maximum=limits["max_output_file_bytes"])
    source_bytes = len(_canonical(value))
    if (any(len(data) > limits["max_output_file_bytes"] for data in outputs.values()) or
            source_bytes > limits["max_output_file_bytes"] or
            source_bytes + sum(map(len, outputs.values())) > limits["max_output_total_bytes"]):
        raise ReportLimitError("complete generated files exceed output budgets")
    return outputs


_LIFECYCLE_AUTHORITY = 'Captured authority is historical; current permission and admission are unavailable.'
_LIFECYCLE_QUALIFICATIONS = [
    'Detached structural consistency only; persisted origin and artifact availability are not authenticated.',
    'Generated bytes only; no output commitment, readable plan, publication, or acknowledgment is established.',
    'Actual first-capture state, not reconstructed transition-time state; missing facts remain unknown.',
    'Reading or rendering grants no readiness, restart, continuation, or worker admission.',
]
_LIFECYCLE_OPENING = (
    'This report renders detached first-capture facts and preserves original intent separately from later captured control. '
    'It proves structural consistency only and returns generated bytes without publication or authorization.\n\n')
_LIFECYCLE_FOOTER = (
    'The source_route describes get_lifecycle_source_operation(control_operation_id) and '
    'read_lifecycle_source(control_operation_id), requiring a separately opened store and appropriate limits. '
    'Inspect exact evidence with get_revision/get_typed_revision(record_id, revision), '
    'read_artifact(ArtifactReference(digest,size)), or existing work-product checkout through explicit inspection. '
    'Exact route arguments are retained in the literal data; availability is not established. '
    'Reproduction instructions are inert and never executed. Reading does not authorize continuation.\n')


def _lifecycle_projection(value, scientific_limits):
    """Extend the shared seven groups with validated original intent and later captured facts.

    The renderer must reserve projection work before calling. Repeated scientific,
    dossier and baseline root occurrences are intentional, not new snapshot roots.
    Control/resource history stays inspectable without becoming scientific results.
    """
    packet = value['binding']
    selected = packet['transition']['content']['request']
    preparation = packet['preparation']['content']['request']['preparation']
    obligation = packet['obligation']['content']
    report = selected['report']
    declarations = report['declarations']
    roots = [ref for category in ('scientific', 'dossier', 'saved_baseline')
             for ref in value['root_categories'][category]]
    bounds = (len(roots), *(min(getattr(scientific_limits, name), report['limits']['snapshot'][name])
                           for name in ('max_records', 'max_references')))
    groups = _project_groups(declarations=declarations, context=preparation['context'],
        baseline=value['baseline'], scientific=value['scientific'], resources=value['resources'],
        root_categories=value['root_categories'], source_bindings=value['source_bindings'],
        qualifications=list(_LIFECYCLE_QUALIFICATIONS), fact_roots=roots, closure_bounds=bounds,
        recorded_changes={'unavailable': unavailable('Historical report comparison is unavailable for a lifecycle saved-work baseline.')},
        authority_notice=_LIFECYCLE_AUTHORITY, stopping_notice=QUALIFICATIONS[3],
        job_notice=QUALIFICATIONS[4], continuation_notice=QUALIFICATIONS[5])
    groups['objective_scope_context_outcome']['lifecycle'] = {
        'binding': packet, 'captured_control': value['control'], 'selection': report['selection'],
        'source_qualifications': value['qualifications']}
    groups['saved_prioritized_continuation']['next_action_interpretation'] = unavailable(
        'No interpreted next action is established; inspect the saved continuation and checkpoint records.')
    groups['inspection_reproduction_and_limitations'].update(
        source_route={'control_operation_id': selected['operation_id'],
                      'metadata_method': 'get_lifecycle_source_operation',
                      'observation_method': 'read_lifecycle_source', 'limits_required': True},
        record_methods=['get_revision', 'get_typed_revision'], artifact_method='read_artifact')
    identities = {'control_operation_id': selected['operation_id'],
        'report_operation_id': obligation['report_operation_id'],
        'run': {'record_id': selected['run_id'], 'revision': selected['run_revision'],
                'relationship': 'run', 'target_kind': 'run'},
        'report_revision': obligation['report_revision'],
        'source_event': {'record_id': obligation['report_source_id'], 'revision': 1,
                         'relationship': 'lifecycle_report_source', 'target_kind': 'event'},
        'snapshot_id': value['snapshot_id'], 'scientific_snapshot_id': value['scientific']['snapshot_id'],
        'binding_digest': value['binding_digest'], 'transitioned_at': selected['transitioned_at'],
        'observed_at': value['observed_at'], 'scientific_watermark': value['scientific']['watermark'],
        'resource_sequence': value['resources'].get('resource_sequence')}
    continuation = {'format': 'research_pipeline.lifecycle_report_continuation', 'version': 1,
        'identities': identities, 'saved_work': declarations['saved_work'], 'groups': groups,
        'continuation': declarations['continuation'], 'ordinary_work_allowed': False, 'recheck_required': True}
    return identities, groups, continuation
