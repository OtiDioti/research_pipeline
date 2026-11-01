"""Strict, detached controller resource declarations; these confer no execution authority."""

from dataclasses import dataclass
import hashlib
import json
import re

from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, RecordReference, _identifier,
    _integer, _timestamp, _validate_json_string, _MAX_INTEGER as MAX_QUANTITY,
)
PURPOSES = ("ordinary", "verification", "handoff", "closeout")
UNCERTAINTY_EVENTS = ("process_loss", "acknowledgment_loss", "timeout", "cancellation",
                      "lease_expiry", "provider_error")
UNITS = {"model_input_tokens": "token", "model_output_tokens": "token",
         "model_calls": "call", "tool_calls": "call", "local_time": "nanosecond",
         "local_compute": "cpu_nanosecond", "local_storage": "byte"}
SCOPE_KINDS = {"project": "project", "run": "run", "branch": "branch",
               "task": "task_specification", "attempt": "attempt"}


class ResourceValidationError(DomainValidationError):
    """A finite resource declaration is malformed or internally incompatible."""


class ResourceConflictError(ValueError):
    """An immutable operation, entity, receipt, or stable scope identity was reused."""


class ResourceCapacityError(ValueError):
    """Admission exceeds capacity or is blocked by a sticky breach beneath its project."""


class ResourceIntegrityError(ValueError):
    """Persisted resource history disagrees with its strict declarations or projections."""


class ResourceInspectionLimitError(ValueError):
    """A complete detached inspection cannot fit the caller's explicit limits."""


def canonical(value):
    """Encode already validated JSON deterministically, with ASCII and exact integers."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _unicode(value, label):
    """Apply the shared scalar-value Unicode rule with a resource-specific diagnostic."""
    try:
        _validate_json_string(value, label)
    except DomainValidationError as error:
        raise ResourceValidationError(str(error)) from error


def _bounded(value, *, max_bytes=65536):
    """Check size/depth iteratively before recursive codecs, including cycles and Unicode."""
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > max_bytes or depth > 16:
            raise ResourceValidationError("resource JSON exceeds size or 16-container depth bound")
        if type(item) in (dict, list):
            if len(item) > max_bytes:
                raise ResourceValidationError("resource JSON container exceeds size bound")
            if depth == 16:
                raise ResourceValidationError("resource JSON exceeds 16-container depth bound")
            if type(item) is dict:
                for key in item:
                    if type(key) is not str:
                        raise ResourceValidationError("JSON keys must be strings")
                    _unicode(key, "JSON key")
                pending.extend((child, depth + 1) for child in item.values())
            else:
                pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            _unicode(item, "JSON string")
            if len(item) > max_bytes:
                raise ResourceValidationError("resource JSON string exceeds size bound")
        elif item is not None and type(item) not in (bool, int, float):
            raise ResourceValidationError("unsupported resource JSON value")
    try:
        text = canonical(value)
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise ResourceValidationError(f"invalid resource JSON: {error}") from error
    if len(text) > max_bytes:
        raise ResourceValidationError("resource JSON exceeds byte bound")
    return text


def _pairs(pairs):
    """Reject duplicate object fields at every nesting level."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResourceValidationError(f"duplicate resource field {key!r}")
        result[key] = value
    return result


def _constant(value):
    """Reject nonfinite JSON numbers before contract reconstruction."""
    raise ResourceValidationError(f"nonfinite resource number {value}")


def strict_json(text, *, max_bytes=65536):
    """Decode size/depth bounded strict JSON without recursive parsing of deep input."""
    try:
        if type(text) is bytes:
            text = text.decode("utf-8")
        if type(text) is not str or len(text) > max_bytes:
            raise ResourceValidationError("resource JSON exceeds byte bound or is not text")
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > 16:
                    raise ResourceValidationError("resource JSON exceeds 16-container depth bound")
            elif char in "]}":
                depth -= 1
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        _bounded(value, max_bytes=max_bytes)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as error:
        raise ResourceValidationError(f"invalid resource JSON: {error}") from error


def fields(value, names, label):
    """Require a closed object with every named field explicitly present."""
    if type(value) is not dict or set(value) != set(names.split()):
        raise ResourceValidationError(f"{label}: incorrect fields")
    return value


def quantity(value, label, minimum=0):
    """Validate a bounded ordinary integer, preserving zero where explicitly permitted."""
    try:
        _integer(value, label, minimum)
    except DomainValidationError as error:
        raise ResourceValidationError(str(error)) from error
    return value


def identifier(value, label):
    """Validate an opaque identifier using the shared record syntax."""
    try:
        _identifier(value, label)
    except DomainValidationError as error:
        raise ResourceValidationError(str(error)) from error
    return value


def statement(value):
    """Require a nonempty bounded descriptive policy, never instructions or authentication."""
    if type(value) is not str or not value.strip() or len(value) > 4096:
        raise ResourceValidationError("policy statement: require 1–4096 characters")
    _unicode(value, "statement")
    return value


@dataclass(frozen=True)
class Dimension:
    """A stable accounting unit; monetary quantities mean quantity/scale declared currency."""

    dimension_id: str
    kind: str
    unit: str
    currency: str | None
    scale: int

    def __post_init__(self):
        """Reject ambiguous units, bool scales, unknown kinds and unsupported money modes."""
        identifier(self.dimension_id, "dimension_id")
        quantity(self.scale, "scale", 1)
        if type(self.kind) is not str or type(self.unit) is not str:
            raise ResourceValidationError("dimension kind/unit must be strings")
        if self.kind in UNITS:
            valid = self.unit == UNITS[self.kind] and self.currency is None and self.scale == 1
        else:
            valid = (self.kind == "monetary" and self.unit == "currency_quantum"
                     and type(self.currency) is str and re.fullmatch(r"[A-Z]{3}", self.currency)
                     and self.scale <= 10**9)
        if not valid:
            raise ResourceValidationError("dimension: invalid kind/unit/currency/scale")

    def to_dict(self):
        """Return the complete detached dimension declaration."""
        return {name: getattr(self, name) for name in ("dimension_id", "kind", "unit", "currency", "scale")}

    @classmethod
    def from_dict(cls, value):
        """Reconstruct every unit field, rejecting missing and unknown fields."""
        return cls(**fields(value, "dimension_id kind unit currency scale", "dimension"))


def dimensions(value):
    """Validate and sort a complete dimension set, rejecting aliases before sorting."""
    if type(value) is not list or not 7 <= len(value) <= 16:
        raise ResourceValidationError("dimensions: require 7–16 entries")
    result = [Dimension.from_dict(item).to_dict() for item in value]
    if len({d["dimension_id"] for d in result}) != len(result):
        raise ResourceValidationError("duplicate dimension_id")
    kinds = [d["kind"] for d in result if d["kind"] != "monetary"]
    currencies = [d["currency"] for d in result if d["kind"] == "monetary"]
    if sorted(kinds) != sorted(UNITS) or len(currencies) != len(set(currencies)):
        raise ResourceValidationError("dimensions: missing/duplicate kinds or currency aliases")
    return sorted(result, key=lambda d: d["dimension_id"])


def vector(value, *, nullable=False):
    """Normalize quantities, optionally retaining unavailable usage as null; require units in replay."""
    if type(value) is not list or not 1 <= len(value) <= 16:
        raise ResourceValidationError("vector: require 1–16 explicit quantities")
    result = []
    for item in value:
        fields(item, "dimension_id quantity", "quantity")
        result.append({"dimension_id": identifier(item["dimension_id"], "dimension_id"),
                       "quantity": None if nullable and item["quantity"] is None else quantity(item["quantity"], "quantity")})
    if len({item["dimension_id"] for item in result}) != len(result):
        raise ResourceValidationError("duplicate vector dimension")
    return sorted(result, key=lambda item: item["dimension_id"])


def amounts(value, declared):
    """Resolve a complete vector by dimension ID, rejecting omitted or additional units."""
    result = {item["dimension_id"]: item["quantity"] for item in value}
    if set(result) != {item["dimension_id"] for item in declared}:
        raise ResourceValidationError("vector must contain exactly the root dimensions")
    return result


def by_kind(value, declared):
    """Resolve nonmonetary quantities by validated kinds, never caller-chosen identifiers."""
    values = amounts(value, declared)
    return {item["kind"]: values[item["dimension_id"]] for item in declared if item["kind"] != "monetary"}


def reference(value, role=None):
    """Reconstruct an exact complete record reference, including a non-null target kind."""
    fields(value, "record_id revision relationship target_kind", "record reference")
    try:
        result = RecordReference.from_dict(value)
    except DomainValidationError as error:
        raise ResourceValidationError(str(error)) from error
    if result.target_kind is None or (role is not None and result.relationship != role):
        raise ResourceValidationError("reference: explicit target kind and matching role required")
    return result.to_dict()


@dataclass(frozen=True, init=False)
class ScopeReference:
    """Closed exact-record or stable-controller scope union with detached serialization."""

    _json: str

    def __init__(self, value):
        """Validate a scope document; project/task scopes must reference exact records."""
        _bounded(value)
        if type(value) is not dict:
            raise ResourceValidationError("scope: expected object")
        if value.get("type") == "record":
            fields(value, "type kind reference", "record scope")
            ref = reference(value["reference"])
            kind = value["kind"]
            if type(kind) is not str or SCOPE_KINDS.get(kind) != ref["target_kind"]:
                raise ResourceValidationError("scope: mismatched record kind")
            result = {"type": "record", "kind": kind, "reference": ref}
        else:
            fields(value, "type kind stable_identity", "controller scope")
            if value["type"] != "controller" or value["kind"] not in ("run", "branch", "attempt"):
                raise ResourceValidationError("scope: controller identity unavailable for this kind")
            result = {**value, "stable_identity": identifier(value["stable_identity"], "stable_identity")}
        object.__setattr__(self, "_json", canonical(result))

    def to_dict(self):
        """Return a detached scope; callers cannot modify the declaration."""
        return strict_json(self._json)

    @classmethod
    def from_dict(cls, value):
        """Reconstruct the closed scope union."""
        return cls(value)


def call_bounds(value):
    """Validate explicit per-invocation input/output maxima without inferring quantities."""
    fields(value, "max_input_tokens_per_call max_output_tokens_per_call", "call bounds")
    return {"max_input_tokens_per_call": quantity(value["max_input_tokens_per_call"], "per-call input"),
            "max_output_tokens_per_call": quantity(value["max_output_tokens_per_call"], "per-call output", 1)}


def validate_call_envelope(values, bounds, context, output):
    """Check a positive-call declaration with exact products and inherited per-call constraints.

    Provisioning and actual reservation envelopes share arithmetic, not identity or
    ceilings. A policy envelope provisions cumulative capacity; each reservation
    supplies its own bounds, which may differ from that provisioning declaration.
    """
    n = quantity(values["model_calls"], "model calls", 1)
    quantity(values["model_input_tokens"], "model input tokens")
    quantity(values["model_output_tokens"], "model output tokens")
    bounds = call_bounds(bounds)
    i, o = bounds["max_input_tokens_per_call"], bounds["max_output_tokens_per_call"]
    quantity(context, "context capacity", 1)
    quantity(output, "per-call output", 1)
    if output > context or i + o > context or o > output:
        raise ResourceValidationError("call envelope exceeds context/output constraints")
    needed_input, needed_output = n * i, n * o
    quantity(needed_input, "input product")
    quantity(needed_output, "output product")
    if values["model_input_tokens"] < needed_input or values["model_output_tokens"] < needed_output:
        raise ResourceValidationError("cumulative tokens do not provision declared call bounds")


def policy(value, *, run=False):
    """Validate a closed policy shape; dimension-dependent admission occurs in the ledger."""
    names = "policy_id statement"
    if run:
        names += " verification_minimum handoff_minimum closeout_minimum handoff_call_bounds context_capacity_tokens per_call_output_tokens monetary_services"
    fields(value, names, "run policy" if run else "policy")
    result = {"policy_id": identifier(value["policy_id"], "policy_id"), "statement": statement(value["statement"])}
    if run:
        for purpose in ("verification", "handoff", "closeout"):
            result[purpose + "_minimum"] = vector(value[purpose + "_minimum"])
        result["handoff_call_bounds"] = call_bounds(value["handoff_call_bounds"])
        result["context_capacity_tokens"] = quantity(value["context_capacity_tokens"], "context", 1)
        result["per_call_output_tokens"] = quantity(value["per_call_output_tokens"], "output", 1)
        services = value["monetary_services"]
        if type(services) is not list or len(services) > 9:
            raise ResourceValidationError("monetary_services: expected bounded list")
        result["monetary_services"] = []
        for entry in services:
            fields(entry, "dimension_id service_id mode statement", "monetary service")
            if entry["mode"] != "monitored_target":
                raise ResourceValidationError("monetary service: only monitored_target is supported")
            result["monetary_services"].append({"dimension_id": identifier(entry["dimension_id"], "dimension_id"),
                "service_id": identifier(entry["service_id"], "service_id"), "mode": entry["mode"],
                "statement": statement(entry["statement"])})
        ids = [s["dimension_id"] for s in result["monetary_services"]]
        if len(ids) != len(set(ids)):
            raise ResourceValidationError("duplicate monetary service dimension")
    return result


def validate_run_policy(value, declared):
    """Enforce complete protected minima and explicit handoff provisioning using exact integers."""
    minima = {p: by_kind(value[p + "_minimum"], declared) for p in ("verification", "handoff", "closeout")}
    if not any(amounts(value["verification_minimum"], declared).values()):
        raise ResourceValidationError("verification minimum must contain positive capacity")
    for p in ("handoff", "closeout"):
        for kind in ("local_time", "local_storage"):
            quantity(minima[p][kind], p + " " + kind, 1)
    for kind in ("model_calls", "model_input_tokens", "model_output_tokens"):
        quantity(minima["handoff"][kind], "handoff " + kind, 1)
    validate_call_envelope(minima["handoff"], value["handoff_call_bounds"],
                           value["context_capacity_tokens"], value["per_call_output_tokens"])
    if {s["dimension_id"] for s in value["monetary_services"]} != {d["dimension_id"] for d in declared if d["kind"] == "monetary"}:
        raise ResourceValidationError("require one monitored service policy per monetary dimension")


def _observation(value):
    """Validate finite evidence and nullable cumulative usage without granting transport authority.

    Authoritative completion declares execution and billing complete for every
    tracked dimension. Dimension-dependent telemetry checks belong to replay.
    """
    evidence = fields(value["evidence"], "source_kind source_id source_receipt_id statement", "evidence")
    identifier(evidence["source_id"], "source_id")
    statement(evidence["statement"])
    source, event = evidence["source_kind"], value["event"]
    receipt = source == "controller_receipt"
    if receipt:
        identifier(evidence["source_receipt_id"], "source_receipt_id")
        if event not in ("partial_usage", "authoritative_completion"):
            raise ResourceValidationError("controller receipt requires usage or complete execution/billing")
    elif (source == "controller_status" and event in UNCERTAINTY_EVENTS
          or source == "worker_narrative" and event == "worker_narrative"):
        if evidence["source_receipt_id"] is not None:
            raise ResourceValidationError("non-receipt evidence requires null source_receipt_id")
    else:
        raise ResourceValidationError("incompatible evidence source/event")
    usage = vector(value["usage"], nullable=True)
    known = [entry["quantity"] is not None for entry in usage]
    if ((not receipt and any(known)) or (event == "partial_usage" and not any(known))
            or (event == "authoritative_completion" and not all(known))):
        raise ResourceValidationError("event requires unavailable, partial, or complete usage")
    telemetry = fields(value["telemetry"], "cached_input_tokens reasoning_output_tokens", "telemetry")
    for number in telemetry.values():
        if number is not None:
            quantity(number, "telemetry quantity")
            if not receipt:
                raise ResourceValidationError("non-receipt telemetry must be null")
    sample = value["call_observation"]
    if sample is not None:
        fields(sample, "call_id input_tokens output_tokens", "call observation")
        identifier(sample["call_id"], "call_id")
        quantity(sample["input_tokens"], "call input")
        quantity(sample["output_tokens"], "call output")
        if not receipt:
            raise ResourceValidationError("non-receipt call observation must be null")
    return {**value, "usage": usage}


def _reconciliation(value):
    """Validate an explicit settlement reference and predecessor; replay verifies their authority."""
    if value["mode"] not in ("authoritative", "conservative"):
        raise ResourceValidationError("unsupported reconciliation mode; refunds/amendments unavailable")
    for key in ("observation_operation_id", "previous_reconciliation_operation_id"):
        if value[key] is not None:
            identifier(value[key], key)
    statement(value["reason"])
    return value


def _payload(kind, value):
    """Normalize the closed declaration, observation and settlement unions; reject amendments."""
    names = {"create_account": "account_id owner_id scope dimensions ceiling policy",
             "allocate": "allocation_id parent_account_id account_id owner_id scope purpose_limits run_policy",
             "reserve": "reservation_id account_id owner_id purpose maxima call_bounds",
             "observe": "account_id owner_id reservation_id event evidence usage telemetry call_observation",
             "reconcile": "account_id owner_id reservation_id mode observation_operation_id previous_reconciliation_operation_id reason"}
    if type(kind) is not str or kind not in names:
        raise ResourceValidationError("unsupported resource kind; amendments/refunds unavailable")
    fields(value, names[kind], kind)
    result = dict(value)
    for key in ("account_id", "owner_id", "allocation_id", "parent_account_id", "reservation_id"):
        if key in value:
            result[key] = identifier(value[key], key)
    if kind == "observe":
        return _observation(result)
    if kind == "reconcile":
        return _reconciliation(result)
    if kind == "reserve":
        if value["purpose"] not in PURPOSES:
            raise ResourceValidationError("unsupported reservation purpose")
        result["maxima"] = vector(value["maxima"])
        result["call_bounds"] = None if value["call_bounds"] is None else call_bounds(value["call_bounds"])
    else:
        result["scope"] = ScopeReference(value["scope"]).to_dict()
        if kind == "create_account":
            if result["scope"]["kind"] != "project":
                raise ResourceValidationError("root must have project scope")
            result["dimensions"] = dimensions(value["dimensions"])
            result["ceiling"] = vector(value["ceiling"])
            amounts(result["ceiling"], result["dimensions"])
            result["policy"] = policy(value["policy"])
        else:
            fields(value["purpose_limits"], " ".join(PURPOSES), "purpose limits")
            result["purpose_limits"] = {p: vector(value["purpose_limits"][p]) for p in PURPOSES}
            is_run = result["scope"]["kind"] == "run"
            if is_run:
                result["run_policy"] = policy(value["run_policy"], run=True)
            elif value["run_policy"] is not None:
                raise ResourceValidationError("descendants must inherit run_policy; declaration must be null")
    return result


@dataclass(frozen=True, init=False)
class ResourceRequest:
    """Immutable complete resource request, reconstructible before every public admission."""

    _json: str

    def __init__(self, kind, operation_id, receipt_id, provenance, policy_references, evidence_references, payload):
        """Snapshot explicit declarations without resolving references or consuming capacity."""
        if type(provenance) is not CreationProvenance:
            raise ResourceValidationError("provenance: expected CreationProvenance")
        try:
            details = strict_json(provenance._details_json)
            doc = {"format": "research_pipeline.resource_request", "version": 1, "kind": kind,
                   "operation_id": operation_id, "receipt_id": receipt_id,
                   "provenance": {"actor": provenance.actor, "created_at": provenance.created_at, "details": details},
                   "policy_references": policy_references, "evidence_references": evidence_references, "payload": payload}
            object.__setattr__(self, "_json", self._normalize(doc))
        except (AttributeError, ValueError, TypeError, RecursionError, OverflowError) as error:
            raise ResourceValidationError(f"invalid resource request: {error}") from error

    @staticmethod
    def _normalize(value):
        """Validate closed fields, nested bounds and canonical order before storing a request."""
        _bounded(value)
        fields(value, "format version kind operation_id receipt_id provenance policy_references evidence_references payload", "resource request")
        if value["format"] != "research_pipeline.resource_request" or type(value["version"]) is not int or value["version"] != 1:
            raise ResourceValidationError("unsupported resource request format/version")
        result = dict(value)
        for key in ("operation_id", "receipt_id"):
            identifier(value[key], key)
        fields(value["provenance"], "actor created_at details", "provenance")
        result["provenance"] = CreationProvenance.from_dict(value["provenance"]).to_dict()
        for key, role in (("policy_references", "resource_policy"), ("evidence_references", "resource_evidence")):
            refs = value[key]
            if type(refs) is not list or len(refs) > 32:
                raise ResourceValidationError("references: expected list of at most 32 entries")
            result[key] = [reference(ref, role) for ref in refs]
        result["payload"] = _payload(value["kind"], value["payload"])
        return _bounded(result)

    def to_dict(self):
        """Return isolated request data, detecting forged private JSON before use."""
        return strict_json(self._json)

    @classmethod
    def from_dict(cls, value):
        """Reconstruct all nested fields and normalize ordering without trusting frozen objects."""
        try:
            text = cls._normalize(value)
            result = object.__new__(cls)
            object.__setattr__(result, "_json", text)
            return result
        except (ValueError, TypeError, AttributeError, RecursionError, OverflowError) as error:
            raise ResourceValidationError(f"invalid resource request: {error}") from error

    @property
    def operation_id(self):
        """Return the stable original operation identity."""
        return self.to_dict()["operation_id"]

    @property
    def fingerprint(self):
        """Return the SHA-256 identity of the complete canonical declaration."""
        return hashlib.sha256(self._json.encode("ascii")).hexdigest()


def dumps_request(value):
    """Reconstruct and serialize a request, including forged nested values at this boundary."""
    if type(value) is not ResourceRequest:
        raise ResourceValidationError("expected ResourceRequest")
    try:
        return ResourceRequest.from_dict(value.to_dict())._json
    except (AttributeError, TypeError) as error:
        raise ResourceValidationError("malformed ResourceRequest") from error


def loads_request(value):
    """Strictly decode a finite request, rejecting duplicate fields before reconstruction."""
    return ResourceRequest.from_dict(strict_json(value))


@dataclass(frozen=True, init=False)
class ResourceReceipt:
    """Immutable exact outcome with a scientific watermark, never mutable balances."""

    _json: str

    def __init__(self, value):
        """Validate the full versioned receipt and retain canonical detached JSON."""
        _bounded(value)
        fields(value, "format version operation_id receipt_id sequence request_fingerprint kind account_id allocation_id reservation_id committed_at provenance scientific_watermark_event_id", "resource receipt")
        if value["format"] != "research_pipeline.resource_receipt" or type(value["version"]) is not int or value["version"] != 1:
            raise ResourceValidationError("unsupported resource receipt format/version")
        kind = value["kind"]
        if kind not in ("create_account", "allocate", "reserve", "observe", "reconcile"):
            raise ResourceValidationError("unsupported receipt kind")
        for key in ("operation_id", "receipt_id", "account_id"):
            identifier(value[key], key)
        for key, required in (("allocation_id", kind == "allocate"), ("reservation_id", kind in ("reserve", "observe", "reconcile"))):
            if required:
                identifier(value[key], key)
            elif value[key] is not None:
                raise ResourceValidationError("inapplicable receipt identity must be null")
        quantity(value["sequence"], "sequence", 1)
        quantity(value["scientific_watermark_event_id"], "scientific watermark")
        if type(value["request_fingerprint"]) is not str or re.fullmatch(r"[0-9a-f]{64}", value["request_fingerprint"]) is None:
            raise ResourceValidationError("invalid request fingerprint")
        fields(value["provenance"], "actor created_at details", "provenance")
        try:
            result = {**value, "committed_at": _timestamp(value["committed_at"]),
                      "provenance": CreationProvenance.from_dict(value["provenance"]).to_dict()}
        except DomainValidationError as error:
            raise ResourceValidationError(str(error)) from error
        object.__setattr__(self, "_json", canonical(result))

    def to_dict(self):
        """Return detached original receipt data."""
        return strict_json(self._json)

    @classmethod
    def from_dict(cls, value):
        """Reconstruct the complete receipt contract."""
        return cls(value)


@dataclass(frozen=True)
class ResourceInspectionLimits:
    """Explicit positive bounds for complete inspection; results are never truncated."""

    max_accounts: int
    max_operations: int
    max_metadata_bytes: int

    def __post_init__(self):
        """Reject coercions and nonpositive inspection budgets."""
        for key in ("max_accounts", "max_operations", "max_metadata_bytes"):
            quantity(getattr(self, key), key, 1)


@dataclass(frozen=True, init=False)
class ResourceSnapshot:
    """Detached canonical ledger observation, identified by all captured metadata."""

    _json: str

    def __init__(self, value):
        """Validate closed snapshot membership and identity before isolating its data."""
        from research_pipeline.resource_ledger import validate_snapshot
        try:
            validate_snapshot(value)
            object.__setattr__(self, "_json", canonical(value))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
            raise ResourceValidationError(f"invalid resource snapshot: {error}") from error

    def to_dict(self):
        """Return isolated data; later admissions or caller mutations cannot change this snapshot."""
        return json.loads(self._json)

    @classmethod
    def from_dict(cls, value):
        """Reconstruct a strict detached observation, checking its complete canonical identity."""
        return cls(value)

    @property
    def snapshot_id(self):
        """Return the canonical SHA-256 identity of this observation."""
        return self.to_dict()["snapshot_id"]


def dumps_receipt(value):
    """Reconstruct and serialize an original receipt without trusting frozen internals."""
    if type(value) is not ResourceReceipt:
        raise ResourceValidationError("expected ResourceReceipt")
    try:
        return ResourceReceipt.from_dict(value.to_dict())._json
    except (AttributeError, TypeError) as error:
        raise ResourceValidationError("malformed ResourceReceipt") from error


def loads_receipt(value):
    """Decode the strict complete receipt contract, including nested duplicate rejection."""
    return ResourceReceipt.from_dict(strict_json(value))
