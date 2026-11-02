"""Detached local operating declarations and explicit host-only HMAC trust.

These values authorize no execution. Eligibility must be recomputed with current
external policy and trusted time inside the later admitting write transaction.
"""

from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import math
import re

from research_pipeline.domain import (
    DomainValidationError, RecordReference, ArtifactReference, RecordEnvelope,
    CreationProvenance, Submission, SubmissionReceipt, _identifier as _domain_identifier, _integer,
    _kind, _timestamp, _validate_json_string,
)
from research_pipeline import resources
from research_pipeline.project import ProceduralJudgment
from research_pipeline.source import DeclaredText
from research_pipeline.snapshot import _commit

IDENTIFIER_CHARS = 128
TEXT_CHARS = 4096
PERMISSION_ENTRIES = 128
ORIGINAL_IDS = 1024
EVIDENCE_DECLARATIONS = 1024
EVIDENCE_ENTRIES = 4096
DECISION_BYTES = 1024 * 1024
SIGNED_BYTES = DECISION_BYTES + 1024
ENVELOPE_BYTES = 4 * 1024 * 1024
RESULT_BYTES = 64 * 1024 * 1024
JSON_DEPTH = 32
JSON_NODES = 131072
MAX_DECISIONS = 1024
MAX_METADATA_RECORDS = 4096
MAX_REFERENCES = 32768
ABSENT_REASON = "Absent from the bound ProjectSetup."
SIGNING_PREFIX = b"research_pipeline.operating_decision.v1\x00"
STREAM_PREFIX = b"research_pipeline.operating_stream.v1\x00"
CAPABILITIES = ("approve_setup", "approve_main_research", "deny", "revoke")
SIGNATURE_STATUSES = ("verified", "invalid", "unavailable")
POLICY_STATUSES = ("permitted", "denied", "unavailable")
ELIGIBILITY_STATUSES = ("no_decision", "missing_trust", "policy_denied", "unauthenticated",
    "denied", "revoked", "not_yet_valid", "expired", "scope_mismatch", "stale", "incomplete",
    "artifact_unavailable", "eligible_setup", "eligible_main_research")


class AuthorityValidationError(DomainValidationError):
    """A new authority contract is malformed; diagnostics contain no request or key bytes."""


class AuthorityAuthenticationError(ValueError):
    """A new append lacks a valid signature or configured current authorization."""


class AuthorityReadinessError(ValueError):
    """A fresh approval fails its exact dossier, scope or artifact prerequisites."""


class AuthorityIntegrityError(ValueError):
    """Persisted authority metadata or its immutable history is incoherent."""


class AuthorityLimitError(ValueError):
    """Complete inspection cannot fit the caller's independent explicit bounds."""


def _identifier(value, label):
    """Apply shared identifier syntax with a sanitized authority-specific validation error."""
    try:
        _domain_identifier(value, label)
    except DomainValidationError:
        raise AuthorityValidationError("invalid authority identifier") from None


def canonical(value):
    """Encode validated values as sorted, compact ASCII JSON, with exact integers."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def bounded(value, maximum):
    """Preflight scalar types, cycles, depth and nodes before recursive canonical encoding."""
    pending, ancestors, nodes = [(value, 0, False)], set(), 0
    while pending:
        item, depth, leaving = pending.pop()
        if leaving:
            ancestors.remove(id(item))
            continue
        nodes += 1
        if nodes > JSON_NODES:
            raise AuthorityValidationError("authority JSON node limit exceeded")
        kind = type(item)
        if kind in (dict, list):
            if depth >= JSON_DEPTH or id(item) in ancestors:
                raise AuthorityValidationError("authority JSON depth exceeded or cyclic container")
            ancestors.add(id(item))
            pending.append((item, depth, True))
            if len(item) > JSON_NODES - nodes:
                raise AuthorityValidationError("authority JSON node limit exceeded")
            if kind is dict:
                for key in item:
                    if type(key) is not str:
                        raise AuthorityValidationError("authority JSON keys must be strings")
                    _validate_json_string(key, "authority key")
                children = item.values()
            else:
                children = item
            pending.extend((child, depth + 1, False) for child in children)
        elif kind is str:
            _validate_json_string(item, "authority string")
            if len(item) > maximum:
                raise AuthorityValidationError("authority JSON byte limit exceeded")
        elif kind is float:
            if not math.isfinite(item):
                raise AuthorityValidationError("nonfinite authority JSON number")
        elif item is not None and kind not in (int, bool):
            raise AuthorityValidationError("unsupported authority JSON value")
    text = canonical(value)
    if len(text) > maximum:
        raise AuthorityValidationError("authority canonical byte limit exceeded")
    return text


def _pairs(pairs):
    """Reject duplicate JSON keys at every depth without echoing untrusted fields."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityValidationError("duplicate authority JSON field")
        result[key] = value
    return result


def _constant(value):
    """Refuse nonfinite JSON constants during parsing."""
    raise AuthorityValidationError("nonfinite authority JSON number")


def strict_json(text, maximum=RESULT_BYTES):
    """Check UTF-8 size and container depth before parsing; then check all value nodes."""
    try:
        if type(text) is bytes:
            if len(text) > maximum:
                raise AuthorityValidationError("authority input byte limit exceeded")
            text = text.decode("utf-8")
        if type(text) is not str or len(text.encode("utf-8")) > maximum:
            raise AuthorityValidationError("authority input must be bounded UTF-8 JSON")
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
                if depth > JSON_DEPTH:
                    raise AuthorityValidationError("authority JSON depth limit exceeded")
            elif char in "]}":
                depth -= 1
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        bounded(value, maximum)
        return value
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        raise AuthorityValidationError("invalid or oversized authority JSON") from None


def exact(value, names):
    """Require every named field, including null fields, and reject extensions."""
    if type(value) is not dict or set(value) != set(names.split()):
        raise AuthorityValidationError("incorrect authority fields")
    return value


def text_value(value):
    """Require a nonblank explanatory string of at most 4096 Unicode scalar characters."""
    if type(value) is not str or not value.strip() or len(value) > TEXT_CHARS:
        raise AuthorityValidationError("authority explanation requires 1–4096 characters")
    _validate_json_string(value, "authority explanation")
    return value


def enum(value, choices):
    """Validate a closed string enumeration without coercion."""
    if type(value) is not str or value not in choices:
        raise AuthorityValidationError("unsupported authority enumeration")
    return value


def timestamp(value):
    """Require an already normalized microsecond UTC calendar timestamp; never read a clock."""
    try:
        if _timestamp(value) != value or len(value) != 27:
            raise ValueError
    except (ValueError, TypeError):
        raise AuthorityValidationError("authority time requires YYYY-MM-DDTHH:MM:SS.ffffffZ") from None
    return value


def digest(value):
    """Validate a lowercase SHA-256 digest without accepting alternate encodings."""
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AuthorityValidationError("invalid authority digest")
    return value


def array(value, maximum, *, nonempty=False):
    """Require an ordinary bounded JSON array, optionally with at least one entry."""
    if type(value) is not list or not int(nonempty) <= len(value) <= maximum:
        raise AuthorityValidationError("authority collection limit or type mismatch")
    return value


def unique(value, key=canonical):
    """Reject ambiguous duplicate keys while preserving the supplied array order."""
    keys = [key(item) for item in value]
    if len(keys) != len(set(keys)):
        raise AuthorityValidationError("duplicate authority collection member")
    return value


def ids(value, maximum, *, nonempty=False):
    """Validate unique ordinary identifiers without interpreting names as permissions."""
    array(value, maximum, nonempty=nonempty)
    for item in value:
        _identifier(item, "authority identifier")
    return unique(value)


def reference(value, role, kind=None):
    """Require all four reference fields and an explicit supported exact target kind."""
    exact(value, "record_id revision relationship target_kind")
    result = RecordReference.from_dict(value)
    if result.relationship != role or result.target_kind is None or (kind and result.target_kind != kind):
        raise AuthorityValidationError("authority reference role or kind mismatch")
    return result.to_dict()


def pin(value):
    """Return identity/revision independent of an incoming role."""
    return value["record_id"], value["revision"]


def absent():
    """Return the fixed explicit unavailable shape for an absent ProjectSetup optional pin."""
    return {"value": None, "unknown_reason": ABSENT_REASON}


def _heads(value):
    """Normalize exact watched heads and reject multiple selected revisions per identity."""
    array(value, EVIDENCE_ENTRIES)
    for item in value:
        exact(item, "record_id revision kind")
        _identifier(item["record_id"], "head identity")
        _integer(item["revision"], "head revision", 1)
        _kind(item["kind"], "head kind")
    unique(value, lambda item: item["record_id"])
    return sorted(value, key=pin)


def _resources(value):
    """Reuse dimensioned run-policy arithmetic for complete declarations, never reservations."""
    exact(value, "dimensions ceiling purpose_limits call_bounds run_policy")
    dims = resources.dimensions(value["dimensions"])
    ceiling = resources.vector(value["ceiling"])
    caps = resources.amounts(ceiling, dims)
    exact(value["purpose_limits"], "ordinary verification handoff closeout")
    pools = {name: resources.vector(value["purpose_limits"][name]) for name in resources.PURPOSES}
    quantities = {name: resources.amounts(pool, dims) for name, pool in pools.items()}
    if any(sum(pool[unit] for pool in quantities.values()) > cap for unit, cap in caps.items()):
        raise AuthorityValidationError("authority pools exceed ceiling")
    policy = resources.policy(value["run_policy"], run=True)
    resources.validate_run_policy(policy, dims)
    for name in resources.PURPOSES[1:]:
        minimum = resources.amounts(policy[name + "_minimum"], dims)
        if any(quantities[name][unit] < number for unit, number in minimum.items()):
            raise AuthorityValidationError("protected authority pool below policy minimum")
    ordinary = resources.by_kind(pools["ordinary"], dims)
    bounds = value["call_bounds"]
    if bounds is None:
        if any(ordinary[k] for k in ("model_calls", "model_input_tokens", "model_output_tokens")):
            raise AuthorityValidationError("ordinary calls/tokens require call bounds")
    else:
        bounds = resources.call_bounds(bounds)
        resources.validate_call_envelope(ordinary, bounds, policy["context_capacity_tokens"], policy["per_call_output_tokens"])
    return dict(dimensions=dims, ceiling=ceiling, purpose_limits=pools, call_bounds=bounds, run_policy=policy)


def _scope(value):
    """Validate explicit capability, original-data, disclosure and resource permissions."""
    exact(value, "format version purpose capability_releases data_access disclosures resources")
    enum(value["purpose"], ("setup", "main_research"))
    for item in array(value["capability_releases"], PERMISSION_ENTRIES):
        exact(item, "capability_id release")
        _identifier(item["capability_id"], "capability")
        reference(item["release"], "allowed_release", "tool_release")
    unique(value["capability_releases"])
    permissions = {}
    for item in array(value["data_access"], PERMISSION_ENTRIES):
        exact(item, "source original_ids operations")
        reference(item["source"], "allowed_source", "source")
        ids(item["original_ids"], ORIGINAL_IDS, nonempty=True)
        unique(array(item["operations"], 3, nonempty=True))
        for operation in item["operations"]:
            enum(operation, ("read", "reuse", "external_processing"))
        if "read" not in item["operations"]:
            raise AuthorityValidationError("data permissions require explicit read")
        for identity in item["original_ids"]:
            key = (*pin(item["source"]), identity)
            if key in permissions:
                raise AuthorityValidationError("duplicate data original permission")
            permissions[key] = item["operations"]
    for item in array(value["disclosures"], PERMISSION_ENTRIES):
        exact(item, "source original_ids recipient_id policy_reference")
        reference(item["source"], "disclosed_source", "source")
        ids(item["original_ids"], ORIGINAL_IDS, nonempty=True)
        _identifier(item["recipient_id"], "recipient")
        reference(item["policy_reference"], "disclosure_policy")
        for identity in item["original_ids"]:
            if "external_processing" not in permissions.get((*pin(item["source"]), identity), ()):
                raise AuthorityValidationError("disclosure requires matching external-processing permission")
    unique(value["disclosures"])
    return {**value, "resources": _resources(value["resources"])}


def _binding(value):
    """Normalize exact dossier pins and sorted complete envelope/artifact evidence occurrences."""
    exact(value, "format version project dossier record_evidence artifact_evidence head_expectations")
    reference(value["project"], "project_setup", "project")
    dossier = exact(value["dossier"], "initial_corpus current_corpus context brief intake_report")
    for name, role, kind in (("initial_corpus", "initial_corpus", "corpus_manifest"),
            ("current_corpus", "current_corpus", "corpus_manifest"), ("context", "context", "research_context"),
            ("brief", "research_brief", "work_product_manifest"), ("intake_report", "intake_report", "work_product_manifest")):
        item = dossier[name]
        if name in ("context", "brief", "intake_report") and item == absent():
            DeclaredText.from_dict(item)
        else:
            reference(item, role, kind)
    if (dossier["initial_corpus"]["revision"] != 1 or
            dossier["initial_corpus"]["record_id"] != dossier["current_corpus"]["record_id"]):
        raise AuthorityValidationError("authority corpus baseline mismatch")
    records = array(value["record_evidence"], EVIDENCE_ENTRIES)
    for item in records:
        exact(item, "reference envelope_digest")
        reference(item["reference"], "authority_evidence")
        digest(item["envelope_digest"])
    unique(records, lambda item: pin(item["reference"]))
    artifacts = array(value["artifact_evidence"], EVIDENCE_ENTRIES)
    sizes = {}
    for item in artifacts:
        exact(item, "record selector_kind selector artifact")
        selector = enum(item["selector_kind"], ("source_original", "work_product_file"))
        reference(item["record"], "authority_artifact_record", "source" if selector == "source_original" else "work_product_manifest")
        if selector == "source_original":
            _identifier(item["selector"], "original selector")
        else:
            from research_pipeline.work_product import _path
            _path(item["selector"], "artifact selector")
        artifact = ArtifactReference.from_dict(item["artifact"])
        if artifact.digest in sizes and sizes[artifact.digest] != artifact.size:
            raise AuthorityValidationError("conflicting evidence artifact sizes")
        sizes[artifact.digest] = artifact.size
    unique(artifacts, lambda item: (*pin(item["record"]), item["selector_kind"], item["selector"]))
    return {**value, "record_evidence": sorted(records, key=lambda item: pin(item["reference"])),
            "artifact_evidence": sorted(artifacts, key=lambda item: (*pin(item["record"]), item["selector_kind"], item["selector"])),
            "head_expectations": _heads(value["head_expectations"])}


def stream_id(authority_domain, project_id):
    """Derive the sole stream for a domain/project using domain-separated canonical identifiers."""
    _identifier(authority_domain, "authority domain")
    _identifier(project_id, "project identity")
    return "operating_" + hashlib.sha256(STREAM_PREFIX + canonical([authority_domain, project_id]).encode("ascii")).hexdigest()


def _decision(value):
    """Validate a complete permission statement, exact predecessor and bounded explicit validity."""
    exact(value, "format version authority_domain principal_id key_id operation_id decision_id revision predecessor outcome binding judgments rationale issued_at valid_from valid_until scope")
    for name in ("authority_domain", "principal_id", "key_id", "operation_id", "decision_id"):
        _identifier(value[name], name)
    _integer(value["revision"], "decision revision", 1)
    enum(value["outcome"], ("approve", "deny", "revoke"))
    binding = OperatingBinding(value["binding"]).to_dict()
    if value["decision_id"] != stream_id(value["authority_domain"], binding["project"]["record_id"]):
        raise AuthorityValidationError("decision must use the canonical domain/project stream")
    prior = value["predecessor"]
    if value["revision"] == 1:
        if prior is not None or value["outcome"] == "revoke":
            raise AuthorityValidationError("initial decision cannot supersede or revoke")
    else:
        exact(prior, "reference envelope_digest")
        reference(prior["reference"], "supersedes", "decision")
        digest(prior["envelope_digest"])
        if pin(prior["reference"]) != (value["decision_id"], value["revision"] - 1):
            raise AuthorityValidationError("decision requires its immediate same-stream predecessor")
    judgments = exact(value["judgments"], "substantive_relevance assignment_usability evidence_declarations")
    for name in ("substantive_relevance", "assignment_usability"):
        judgment = ProceduralJudgment.from_dict(judgments[name])
        text_value(judgment.explanation)
        for declared in judgment.attribution.to_dict().values():
            if declared is not None:
                text_value(declared)
    ids(judgments["evidence_declarations"], EVIDENCE_DECLARATIONS)
    text_value(value["rationale"])
    for name in ("issued_at", "valid_from", "valid_until"):
        timestamp(value[name])
    if not value["issued_at"] <= value["valid_from"] < value["valid_until"]:
        raise AuthorityValidationError("invalid authority validity ordering")
    if datetime.fromisoformat(value["valid_until"][:-1]) - datetime.fromisoformat(value["valid_from"][:-1]) > timedelta(days=366):
        raise AuthorityValidationError("authority validity exceeds 366 days")
    scope = value["scope"]
    if value["outcome"] == "approve":
        scope = OperatingScope(scope).to_dict()
        if scope["purpose"] == "main_research":
            if (not judgments["evidence_declarations"] or
                    any(judgments[name]["status"] != "affirmed" for name in ("substantive_relevance", "assignment_usability"))):
                raise AuthorityValidationError("main approval requires affirmed judgments and selected evidence")
    elif scope is not None:
        raise AuthorityValidationError("reductions cannot carry permissions")
    return {**value, "binding": binding, "scope": scope}


def _signed(value):
    """Validate the closed HMAC wire format without treating local decoding as verification."""
    exact(value, "format version kind decision signature")
    enum(value["kind"], ("decision",))
    exact(value["signature"], "algorithm value")
    enum(value["signature"]["algorithm"], ("hmac-sha256",))
    digest(value["signature"]["value"])
    return {**value, "decision": OperatingDecision(value["decision"]).to_dict()}


def _envelope_document(envelope):
    """Preflight bypassable envelope snapshots before domain reconstruction, including exact nested types."""
    if type(envelope) is not RecordEnvelope:
        raise AuthorityValidationError("expected exact RecordEnvelope")
    try:
        provenance = envelope.provenance
        if type(provenance) is not CreationProvenance:
            raise ValueError
        references, artifacts = envelope.record_references, envelope.artifact_references
        if type(references) not in (list, tuple) or len(references) > MAX_REFERENCES:
            raise ValueError
        if type(artifacts) not in (list, tuple) or len(artifacts) > MAX_REFERENCES:
            raise ValueError
        if any(type(item) is not RecordReference for item in references) or any(type(item) is not ArtifactReference for item in artifacts):
            raise ValueError
        result = {"record_id": envelope.record_id, "revision": envelope.revision, "kind": envelope.kind,
            "content": strict_json(envelope._content_json, ENVELOPE_BYTES),
            "provenance": {"actor": provenance.actor, "created_at": provenance.created_at,
                           "details": strict_json(provenance._details_json, ENVELOPE_BYTES)},
            "record_references": [item.to_dict() for item in references],
            "artifact_references": [item.to_dict() for item in artifacts],
            "operational_status": envelope.operational_status, "scientific_disposition": envelope.scientific_disposition}
        bounded(result, ENVELOPE_BYTES)
        if RecordEnvelope.from_dict(result).to_dict() != result:
            raise ValueError
        return result
    except (ValueError, TypeError, AttributeError, RecursionError, OverflowError):
        raise AuthorityValidationError("invalid bounded authority evidence envelope") from None


def envelope_digest(envelope):
    """Revalidate and hash the complete canonical envelope, including provenance and ordered projections."""
    return hashlib.sha256(canonical(_envelope_document(envelope)).encode("ascii")).hexdigest()


def _receipt(value):
    """Validate an exact detached receipt and its nested provenance without optional omissions."""
    exact(value, "submission_id fingerprint event_id committed_at provenance revisions")
    exact(value["provenance"], "actor created_at details")
    result = SubmissionReceipt.from_dict(value).to_dict()
    if result != value:
        raise AuthorityValidationError("noncanonical authority receipt")
    return result


def _commit_result(value):
    """Validate metadata-only original operation evidence; this result contains no permission."""
    exact(value, "format version operation_id decision envelope_digest receipt")
    _identifier(value["operation_id"], "operation")
    reference(value["decision"], "operating_decision", "decision")
    digest(value["envelope_digest"])
    receipt = _receipt(value["receipt"])
    if receipt["submission_id"] != value["operation_id"] or receipt["revisions"] != [list(pin(value["decision"]))]:
        raise AuthorityValidationError("authority result receipt mismatch")
    return value


def _history(value):
    """Validate complete ascending decision evidence and current verification annotations."""
    exact(value, "format version authority_domain project_id decisions watermark")
    identity = stream_id(value["authority_domain"], value["project_id"])
    previous = None
    for revision, item in enumerate(array(value["decisions"], MAX_DECISIONS), 1):
        exact(item, "envelope receipt signature_status policy_status")
        bounded(item["envelope"], ENVELOPE_BYTES)
        envelope = RecordEnvelope.from_dict(item["envelope"])
        if envelope.to_dict() != item["envelope"]:
            raise AuthorityValidationError("authority history requires the complete canonical envelope")
        signed = decode_envelope(envelope)
        decision = signed.to_dict()["decision"]
        receipt = _receipt(item["receipt"])
        if (envelope.record_id != identity or envelope.revision != revision or
                receipt["submission_id"] != decision["operation_id"] or receipt["revisions"] != [[identity, revision]]):
            raise AuthorityValidationError("authority history membership mismatch")
        if previous is not None and decision["predecessor"]["envelope_digest"] != envelope_digest(previous):
            raise AuthorityValidationError("authority history predecessor digest mismatch")
        if previous is not None and decision["outcome"] != "approve" and decision["binding"] != previous.content["decision"]["binding"]:
            raise AuthorityValidationError("historical reduction binding mismatch")
        if receipt["provenance"] != envelope.provenance.to_dict():
            raise AuthorityValidationError("historical receipt provenance mismatch")
        previous = envelope
        enum(item["signature_status"], SIGNATURE_STATUSES)
        enum(item["policy_status"], POLICY_STATUSES)
    _commit(value["watermark"], watermark=True)
    return value


def _eligibility(value):
    """Validate detached status/evidence consistency without certifying freshness or admission."""
    exact(value, "format version authority_domain project_id purpose evaluated_at status eligible decision signature_status policy_status binding observed_heads verified_artifacts history_signatures watermark policy_fingerprint recheck_required")
    identity = stream_id(value["authority_domain"], value["project_id"])
    purpose = enum(value["purpose"], ("setup", "main_research"))
    timestamp(value["evaluated_at"])
    status = enum(value["status"], ELIGIBILITY_STATUSES)
    if type(value["eligible"]) is not bool or value["eligible"] != (status in ("eligible_setup", "eligible_main_research")):
        raise AuthorityValidationError("eligibility status/flag mismatch")
    if value["eligible"] and status != "eligible_" + purpose:
        raise AuthorityValidationError("eligibility purpose mismatch")
    if value["recheck_required"] is not True:
        raise AuthorityValidationError("detached eligibility always requires transactional recheck")
    for name, choices in (("signature_status", SIGNATURE_STATUSES), ("policy_status", POLICY_STATUSES)):
        if value[name] is not None:
            enum(value[name], choices)
    if value["decision"] is not None:
        reference(value["decision"], "operating_decision", "decision")
        if value["decision"]["record_id"] != identity or value["binding"] is None:
            raise AuthorityValidationError("eligibility stream/binding mismatch")
    elif status != "no_decision" or value["binding"] is not None:
        raise AuthorityValidationError("missing eligibility decision")
    if value["binding"] is not None:
        value = {**value, "binding": OperatingBinding(value["binding"]).to_dict()}
        if value["binding"]["project"]["record_id"] != value["project_id"]:
            raise AuthorityValidationError("eligibility project mismatch")
    artifacts = array(value["verified_artifacts"], EVIDENCE_ENTRIES)
    for artifact in artifacts:
        ArtifactReference.from_dict(artifact)
    unique(artifacts, lambda item: item["digest"])
    history = array(value["history_signatures"], MAX_DECISIONS)
    for revision, item in enumerate(history, 1):
        exact(item, "reference envelope_digest signature_status")
        reference(item["reference"], "operating_decision", "decision")
        if pin(item["reference"]) != (identity, revision):
            raise AuthorityValidationError("eligibility history must be contiguous")
        digest(item["envelope_digest"])
        enum(item["signature_status"], SIGNATURE_STATUSES)
    if value["decision"] is None and (history or value["observed_heads"] or artifacts or value["signature_status"] is not None or value["policy_status"] is not None):
        raise AuthorityValidationError("no-decision result cannot invent checked decision evidence")
    if value["decision"] is not None and len(history) != value["decision"]["revision"]:
        raise AuthorityValidationError("eligibility history must reach selected head")
    if value["eligible"] and (value["signature_status"] != "verified" or value["policy_status"] != "permitted" or
            any(item["signature_status"] == "invalid" for item in history)):
        raise AuthorityValidationError("eligible result lacks authenticated evidence")
    _commit(value["watermark"], watermark=True)
    if value["policy_fingerprint"] is not None:
        digest(value["policy_fingerprint"])
    return {**value, "observed_heads": _heads(value["observed_heads"])}


@dataclass(frozen=True, init=False)
class _Document:
    """Shared detached snapshot mechanics for the seven closed authority wire documents."""

    _json: str

    def __init__(self, document):
        """Validate exact concrete type and snapshot a complete canonical document."""
        object.__setattr__(self, "_json", _normalize(type(self), document))

    def to_dict(self):
        """Revalidate bypassable frozen state and return an isolated mutable JSON tree."""
        try:
            maximum = _CONTRACTS[type(self)][1]
            return strict_json(_normalize(type(self), strict_json(self._json, maximum)), maximum)
        except (KeyError, AttributeError, ValueError, TypeError, RecursionError, OverflowError):
            raise AuthorityValidationError("invalid detached authority value") from None

    @classmethod
    def from_dict(cls, document):
        """Construct only an exact supported authority class from all required wire fields."""
        return cls(document)


@dataclass(frozen=True, init=False)
class OperatingScope(_Document):
    """Complete deny-by-default permissions and dimensioned declarations; reserves nothing."""


@dataclass(frozen=True, init=False)
class OperatingBinding(_Document):
    """Exact dossier, metadata digests, artifact occurrences and watched head expectations."""


@dataclass(frozen=True, init=False)
class OperatingDecision(_Document):
    """Complete unsigned operator statement, including attribution, validity and effective scope."""


@dataclass(frozen=True, init=False)
class SignedOperatingDecision(_Document):
    """HMAC-authenticated bytes whose authorization still requires current external host policy."""


@dataclass(frozen=True, init=False)
class DecisionCommitResult(_Document):
    """Original receipt evidence only; recovery never returns eligibility."""


@dataclass(frozen=True, init=False)
class AuthorityHistory(_Document):
    """Complete historical metadata with present-policy cryptographic and authorization annotations."""


@dataclass(frozen=True, init=False)
class EligibilityResult(_Document):
    """Detached evidence requiring recomputation inside a later admitting write transaction.

    No reservation, dispatch, continued artifact availability or global freshness is
    promised. Unrelated audit events do not invalidate the watched dependencies.
    """


_CONTRACTS = {
    OperatingScope: ("operating_scope", RESULT_BYTES, _scope),
    OperatingBinding: ("operating_binding", RESULT_BYTES, _binding),
    OperatingDecision: ("operating_decision", DECISION_BYTES, _decision),
    SignedOperatingDecision: ("operating_authority_content", SIGNED_BYTES, _signed),
    DecisionCommitResult: ("operating_commit_result", RESULT_BYTES, _commit_result),
    AuthorityHistory: ("authority_history", RESULT_BYTES, _history),
    EligibilityResult: ("operating_eligibility", RESULT_BYTES, _eligibility),
}


def _normalize(cls, document):
    """Apply protocol bounds before and after closed-contract normalization with sanitized failures."""
    try:
        name, maximum, validator = _CONTRACTS[cls]
        bounded(document, maximum)
        if (type(document) is not dict or document.get("format") != "research_pipeline." + name or
                type(document.get("version")) is not int or document["version"] != 1):
            raise AuthorityValidationError("unsupported authority format/version")
        return bounded(validator(document), maximum)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        raise AuthorityValidationError("invalid authority contract or protocol limit") from None


def document(value, cls):
    """Consume only an exact supported detached class and revalidate its frozen state."""
    if type(value) is not cls:
        raise AuthorityValidationError("expected exact authority value type")
    return value.to_dict()


def dumps_scope(value):
    """Serialize a revalidated OperatingScope to canonical ASCII JSON."""
    return canonical(document(value, OperatingScope))


def loads_scope(value):
    """Decode bounded strict JSON into an OperatingScope."""
    return OperatingScope(strict_json(value, RESULT_BYTES))


def dumps_binding(value):
    """Serialize a revalidated OperatingBinding to canonical ASCII JSON."""
    return canonical(document(value, OperatingBinding))


def loads_binding(value):
    """Decode bounded strict JSON into an OperatingBinding."""
    return OperatingBinding(strict_json(value, RESULT_BYTES))


def dumps_decision(value):
    """Serialize a revalidated complete OperatingDecision signing payload."""
    return canonical(document(value, OperatingDecision))


def loads_decision(value):
    """Decode bounded strict JSON into an OperatingDecision."""
    return OperatingDecision(strict_json(value, DECISION_BYTES))


def dumps_signed_decision(value):
    """Serialize a revalidated SignedOperatingDecision without any credential material."""
    return canonical(document(value, SignedOperatingDecision))


def loads_signed_decision(value):
    """Decode bounded strict JSON into a SignedOperatingDecision without establishing trust."""
    return SignedOperatingDecision(strict_json(value, SIGNED_BYTES))


def dumps_commit_result(value):
    """Serialize bounded original receipt evidence only."""
    return canonical(document(value, DecisionCommitResult))


def loads_commit_result(value):
    """Decode bounded strict JSON into a metadata-only DecisionCommitResult."""
    return DecisionCommitResult(strict_json(value))


def dumps_history(value):
    """Serialize complete detached historical evidence without inferring current permission."""
    return canonical(document(value, AuthorityHistory))


def loads_history(value):
    """Decode bounded strict JSON into AuthorityHistory."""
    return AuthorityHistory(strict_json(value))


def dumps_eligibility(value):
    """Serialize detached evidence whose recheck_required flag always remains true."""
    return canonical(document(value, EligibilityResult))


def loads_eligibility(value):
    """Decode bounded strict JSON into EligibilityResult; decoding grants no authority."""
    return EligibilityResult(strict_json(value))


@dataclass(frozen=True)
class AuthorityLimits:
    """Explicit independent operation budgets; no operational defaults or truncation."""

    max_decisions: int
    max_history_revisions: int
    max_records: int
    max_references: int
    max_record_bytes: int
    max_metadata_bytes: int
    max_artifacts: int
    max_file_bytes: int
    max_total_bytes: int
    max_result_bytes: int

    def __post_init__(self):
        """Validate ordinary integers and hard ceilings before any database work."""
        if type(self) is not AuthorityLimits:
            raise AuthorityValidationError("expected exact AuthorityLimits")
        caps = {"max_decisions": MAX_DECISIONS, "max_history_revisions": MAX_METADATA_RECORDS,
            "max_records": MAX_METADATA_RECORDS, "max_references": MAX_REFERENCES,
            "max_record_bytes": ENVELOPE_BYTES, "max_metadata_bytes": RESULT_BYTES,
            "max_artifacts": EVIDENCE_ENTRIES, "max_result_bytes": RESULT_BYTES}
        zero = {"max_history_revisions", "max_references", "max_artifacts", "max_total_bytes"}
        try:
            for item in dataclass_fields(AuthorityLimits):
                number = getattr(self, item.name)
                _integer(number, "authority limit", 0 if item.name in zero else 1)
                if item.name in caps and number > caps[item.name]:
                    raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise AuthorityValidationError("invalid explicit authority limits") from None


def checked_limits(value):
    """Detach and revalidate exact caller limits before opening a transaction."""
    if type(value) is not AuthorityLimits:
        raise AuthorityValidationError("expected exact AuthorityLimits")
    try:
        return AuthorityLimits(**{item.name: getattr(value, item.name) for item in dataclass_fields(AuthorityLimits)})
    except AttributeError:
        raise AuthorityValidationError("malformed AuthorityLimits") from None


def _key(value):
    """Validate immutable host-only secret bytes without including them in diagnostics."""
    if type(value) is not bytes or not 32 <= len(value) <= 64:
        raise AuthorityValidationError("credential key must be 32–64 immutable bytes")
    return value


def _collection(value, maximum):
    """Snapshot an explicit host collection without coercing strings or arbitrary iterators."""
    if type(value) not in (list, tuple, set, frozenset) or len(value) > maximum:
        raise AuthorityValidationError("invalid host policy collection")
    return tuple(value)


@dataclass(frozen=True)
class OperatorCredential:
    """Host-only shared credential; no persisted codec and no secret-bearing repr."""

    principal_id: str
    key_id: str
    key: bytes = field(repr=False)
    projects: tuple
    capabilities: tuple

    def __post_init__(self):
        """Validate explicit project/capability allowlists and snapshot their nonsecret collections."""
        if type(self) is not OperatorCredential:
            raise AuthorityValidationError("expected exact OperatorCredential")
        _identifier(self.principal_id, "principal")
        _identifier(self.key_id, "key identity")
        _key(self.key)
        projects = _collection(self.projects, 256)
        capabilities = _collection(self.capabilities, 4)
        ids(list(projects), 256)
        unique(list(capabilities))
        for capability in capabilities:
            enum(capability, CAPABILITIES)
        object.__setattr__(self, "projects", tuple(sorted(projects)))
        object.__setattr__(self, "capabilities", tuple(sorted(capabilities)))


@dataclass(frozen=True)
class OperatorPolicy:
    """Trusted host bootstrap only; never reconstructed from tasks, store records or backups."""

    authority_domain: str
    credentials: tuple

    def __post_init__(self):
        """Snapshot exact credentials and reject ambiguous principal/key identities."""
        if type(self) is not OperatorPolicy:
            raise AuthorityValidationError("expected exact OperatorPolicy")
        _identifier(self.authority_domain, "authority domain")
        credentials = _collection(self.credentials, 128)
        copied = []
        for credential in credentials:
            if type(credential) is not OperatorCredential:
                raise AuthorityValidationError("expected exact OperatorCredential")
            try:
                copied.append(OperatorCredential(credential.principal_id, credential.key_id, credential.key,
                                                 credential.projects, credential.capabilities))
            except (ValueError, TypeError, AttributeError):
                raise AuthorityValidationError("invalid host credential") from None
        if len({item.key_id for item in copied}) != len(copied):
            raise AuthorityValidationError("duplicate or ambiguous host key identity")
        object.__setattr__(self, "credentials", tuple(sorted(copied, key=lambda item: (item.principal_id, item.key_id))))


def policy_snapshot(policy):
    """Capture immutable external trust at operation entry; None supplies no verifier."""
    if policy is None:
        return None
    if type(policy) is not OperatorPolicy:
        raise AuthorityValidationError("expected exact host OperatorPolicy")
    try:
        return OperatorPolicy(policy.authority_domain, policy.credentials)
    except (ValueError, TypeError, AttributeError):
        raise AuthorityValidationError("invalid host policy") from None


def policy_fingerprint(policy):
    """Hash public policy scopes only; this neither authenticates key bytes nor replaces verification.

    Rotation must use a new key_id. Secrets never reach persistence/projection code.
    """
    policy = policy_snapshot(policy)
    if policy is None:
        return None
    public = {"authority_domain": policy.authority_domain, "credentials": [
        {"principal_id": item.principal_id, "key_id": item.key_id,
         "projects": list(item.projects), "capabilities": list(item.capabilities)} for item in policy.credentials]}
    return hashlib.sha256(canonical(public).encode("ascii")).hexdigest()


def sign_decision(decision, *, key):
    """Sign complete canonical bytes with an explicit secret; this pure helper establishes no authorization."""
    payload = document(decision, OperatingDecision)
    # Domain separation prevents signatures on other canonical payloads from replaying here.
    signature = hmac.new(_key(key), SIGNING_PREFIX + canonical(payload).encode("ascii"), hashlib.sha256).hexdigest()
    return SignedOperatingDecision({"format": "research_pipeline.operating_authority_content", "version": 1,
        "kind": "decision", "decision": payload, "signature": {"algorithm": "hmac-sha256", "value": signature}})


def _credential(decision, policy):
    """Find the exact configured domain/principal/key without deriving trust from content."""
    if policy is None or policy.authority_domain != decision["authority_domain"]:
        return None
    return next((item for item in policy.credentials if
        (item.principal_id, item.key_id) == (decision["principal_id"], decision["key_id"])), None)


def verify_signature(signed, *, policy):
    """Report cryptographic verification only: verified, invalid, or unavailable."""
    value = document(signed, SignedOperatingDecision)
    credential = _credential(value["decision"], policy_snapshot(policy))
    if credential is None:
        return "unavailable"
    expected = hmac.new(credential.key, SIGNING_PREFIX + canonical(value["decision"]).encode("ascii"), hashlib.sha256).hexdigest()
    return "verified" if hmac.compare_digest(expected, value["signature"]["value"]) else "invalid"


def policy_status(signed, *, policy):
    """Independently check current domain, principal/key, project and outcome capability."""
    decision = document(signed, SignedOperatingDecision)["decision"]
    policy = policy_snapshot(policy)
    credential = _credential(decision, policy)
    if credential is None:
        return "unavailable" if policy is None or policy.authority_domain == decision["authority_domain"] else "denied"
    capability = "approve_" + decision["scope"]["purpose"] if decision["outcome"] == "approve" else decision["outcome"]
    return "permitted" if decision["binding"]["project"]["record_id"] in credential.projects and capability in credential.capabilities else "denied"


def encode_envelope(signed):
    """Derive every envelope field and ordered role projection; direct artifacts stay empty.

    Evidence is authenticated in content and owner records. Reductions must remain
    appendable after loss of the original artifact bytes, so none are direct links.
    """
    value = document(signed, SignedOperatingDecision)
    decision = value["decision"]
    binding, scope, links = decision["binding"], decision["scope"], []
    if decision["predecessor"] is not None:
        links.append(decision["predecessor"]["reference"])
    links.append(binding["project"])
    # Preserve repeated incoming roles in the documented order, never dictionary order.
    links += [binding["dossier"][name]
        for name in ("initial_corpus", "current_corpus", "context", "brief", "intake_report")
        if "record_id" in binding["dossier"][name]]
    links.extend(item["reference"] for item in binding["record_evidence"])
    links.extend(item["record"] for item in binding["artifact_evidence"])
    if scope is not None:
        links.extend(item["release"] for item in scope["capability_releases"])
        links.extend(item["source"] for item in scope["data_access"])
        for item in scope["disclosures"]:
            links.extend((item["source"], item["policy_reference"]))
    envelope = RecordEnvelope(decision["decision_id"], decision["revision"], "decision", value,
        CreationProvenance(decision["principal_id"], decision["issued_at"], {}),
        tuple(RecordReference.from_dict(item) for item in links), ())
    bounded(envelope.to_dict(), ENVELOPE_BYTES)
    return envelope


def decode_envelope(envelope):
    """Recompute the entire signed projection and provenance; local decoding alone grants nothing."""
    if type(envelope) is not RecordEnvelope:
        raise AuthorityValidationError("expected exact RecordEnvelope")
    try:
        raw = _envelope_document(envelope)
        signed = SignedOperatingDecision(raw["content"])
        if raw != encode_envelope(signed).to_dict():
            raise ValueError
        return signed
    except (ValueError, TypeError, AttributeError, RecursionError, OverflowError):
        raise AuthorityValidationError("invalid operating decision envelope projection") from None


def submission(signed):
    """Derive the sole-record CAS submission without accepting independent unsigned metadata."""
    envelope = encode_envelope(signed)
    operation_id = signed.to_dict()["decision"]["operation_id"]
    return Submission(operation_id, envelope.provenance, (envelope,), {envelope.record_id: envelope.revision - 1})
