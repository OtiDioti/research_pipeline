"""Passive attributed tool assessments; local validity conveys no permission or truth."""

from dataclasses import dataclass
import re

from research_pipeline import domain
from research_pipeline.domain import ArtifactReference, RecordReference, DomainValidationError
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_assessment_codec import (
    ToolAssessmentLimits, ToolAssessmentValidationError, ToolAssessmentLimitError,
    _checked_limits, _raw_attribute, _preflight, _parse, _detached, _canonical,
    _check_limit,
)

_FORMAT = "research_pipeline.tool_assessment_content"
_DIMENSIONS = ("operational_interface", "software_behavior", "scientific_applicability")
_OUTCOMES = ("unperformed", "pass", "fail", "inconclusive")
_BASES = ("assessor_assertion", "builder_self_test", "reported_tool_execution", "independent_review")
_EVIDENCE_ROLES = {
    "assessor_assertion": ("reported_assertion", ("source", "work_product_manifest", "evidence")),
    "builder_self_test": ("builder_self_test", ("work_product_manifest", "evidence")),
    "reported_tool_execution": ("reported_tool_execution", ("tool_execution",)),
    "independent_review": ("independent_review", ("review",)),
}


def _fact(payload):
    """Describe a required reasoned fact in this private fixed schema."""
    return ("fact", payload)


def _list(payload):
    """Describe a finite ordered collection in the assessment schema."""
    return ("list", payload)


def _enum(words):
    """Describe one closed vocabulary of exact scalar text."""
    return ("enum", tuple(words.split()))


def _record(role, kinds):
    """Describe a complete exact record pin with a fixed role and allowed kinds."""
    return ("record", role, tuple(kinds.split()))


_TEXT = _fact("nonblank")
_TEXTS = _fact(_list("nonblank"))
_ATTRIBUTION = {"actor": _TEXT, "reported_at": _fact("timestamp"),
                "origin": _enum("synthetic unverified")}
_MODE = _enum("answer_blind_reconstruction proof_blind_reconstruction candidate_aware_audit")
_INDEPENDENCE = {
    "requested_mode": _fact(_MODE), "reported_mode": _fact(_MODE),
    **dict.fromkeys(("shared_formulation", "shared_sources", "shared_lemmas", "shared_method",
                     "shared_implementation", "shared_communications", "limitations"), _TEXTS),
}
_DEPENDENCY = {
    "name": "nonblank", "reported_version": _TEXT,
    "records": _fact(_list(_record("assessed_dependency", "source work_product_manifest tool_release"))),
    "artifacts": _fact(_list(ArtifactReference)), "limitations": _TEXTS,
}
_ENVIRONMENT = {
    "kind": _enum("local remote composite unknown unavailable"), "identity": _TEXT,
    "reported_version": _TEXT, "implementation_version": _TEXT,
    "configuration": _fact(_list({"name": "nonblank", "value": "text"})),
    "observability": _enum("pinned_description reported_version_only opaque unknown unavailable"),
    "records": _fact(_list(_record("assessed_environment", "source work_product_manifest"))),
    "artifacts": _fact(_list(ArtifactReference)), "dependencies": _fact(_list(_DEPENDENCY)),
    "limitations": _TEXTS,
}
_EVIDENCE = {
    "basis": ("enum", _BASES), "attribution": _ATTRIBUTION, "statement": _TEXT,
    # The selected basis restricts these roles during the same schema walk.
    "records": _fact(_list(RecordReference)), "artifacts": _fact(_list(ArtifactReference)),
    "resource_usage": _TEXTS, "unresolved_liabilities": _TEXTS,
    "independence": _INDEPENDENCE, "limitations": _TEXTS,
}
_CHECK = {
    "check_id": "identifier", "dimension": ("enum", _DIMENSIONS), "basis": ("enum", _BASES),
    "attribution": _ATTRIBUTION, "outcome": ("enum", _OUTCOMES), "scope": _TEXTS,
    "method": _TEXT, "expected": _TEXT, "observed": _TEXT,
    "definition_records": _fact(_list(_record("check_definition", "source work_product_manifest"))),
    "definition_artifacts": _fact(_list(ArtifactReference)), "evidence": _fact(_list(_EVIDENCE)),
    "independence": _INDEPENDENCE, "limitations": _TEXTS,
}
_REVIEW = {
    "review": _record("reported_review", "review"), "attribution": _ATTRIBUTION,
    "outcome": ("enum", _OUTCOMES), "scope": _TEXTS, "rationale": _TEXT,
    "evidence": _fact(_list(_EVIDENCE)), "independence": _INDEPENDENCE, "limitations": _TEXTS,
}
_ISSUE = {
    "issue": _record("reported_issue", "issue"), "attribution": _ATTRIBUTION,
    "category": _enum("operational_interface software_behavior scientific_applicability observability other"),
    "summary": _TEXT, "affected_scope": _TEXTS, "evidence": _fact(_list(_EVIDENCE)),
    "limitations": _TEXTS,
}
_PERMISSION = {
    "status": _enum("unassessed permitted denied revoked restricted unknown"), "attribution": _ATTRIBUTION,
    "scope": _TEXTS, "rationale": _TEXT,
    "decisions": _fact(_list(_record("reported_permission_decision", "decision"))),
    "evidence": _fact(_list(_EVIDENCE)), "limitations": _TEXTS,
}
_QUALIFICATION = {
    "outcome": ("enum", _OUTCOMES), "attribution": _ATTRIBUTION, "scope": _TEXTS,
    "rationale": _TEXT,
    "decisions": _fact(_list(_record("reported_qualification_decision", "decision"))),
    "evidence": _fact(_list(_EVIDENCE)), "limitations": _TEXTS,
}
_REPLACEMENT = {"release": _record("replacement_release", "tool_release"), "release_id": "digest"}
_LIFECYCLE = {
    "status": _enum("unassessed active restricted suspended withdrawn superseded unknown"),
    "reason_category": _enum("unassessed routine_revision operational_restriction software_defect scientific_defect observability_limit other unknown"),
    "attribution": _ATTRIBUTION, "scope": _TEXTS, "rationale": _TEXT,
    "decisions": _fact(_list(_record("reported_lifecycle_decision", "decision"))),
    "evidence": _fact(_list(_EVIDENCE)), "limitations": _TEXTS,
    "replacement": _fact(_REPLACEMENT),
    "supersedes": _fact(_list(_record("supersedes_assessment", "tool_assessment"))),
    "superseded_by": _fact(_record("superseded_by_assessment", "tool_assessment")),
}
_SECTIONS = {
    "attribution": _ATTRIBUTION,
    "target": {"release": _record("assessed_release", "tool_release"), "release_id": "digest"},
    "environment": _ENVIRONMENT, "scope": {"intended_uses": _TEXTS, "tested_scope": _TEXTS},
    "checks": _fact(_list(_CHECK)), "reviews": _fact(_list(_REVIEW)), "limitations": _TEXTS,
    "issues": _fact(_list(_ISSUE)), "execution_permission": _PERMISSION,
    "qualification": dict.fromkeys(_DIMENSIONS, _QUALIFICATION), "lifecycle": _LIFECYCLE,
}
_ROOT = {"format": _enum(_FORMAT), "version": "version", "kind": _enum("tool_assessment"),
         "assessment_id": "identifier", **_SECTIONS}
_RECORD_FIELDS = {"record_id": "identifier", "revision": "revision",
                  "relationship": "identifier", "target_kind": "record_kind"}
_ARTIFACT_FIELDS = {"digest": "artifact_digest", "size": "integer"}


def _closed(value, schema, label):
    """Require ordinary objects with every required field and no extension fields."""
    if type(value) is not dict or value.keys() != schema.keys():
        raise ToolAssessmentValidationError(f"{label}: incorrect closed fields")


def _text(value, label, *, nonblank=False):
    """Validate scalar text while preserving its authored spelling."""
    if type(value) is not str or (nonblank and not value.strip()):
        raise ToolAssessmentValidationError(f"{label}: expected {'nonblank ' if nonblank else ''}text")


def _raw_reference(value, expected):
    """Read fixed exact reference fields without serialization or dynamic type lookup."""
    names = _RECORD_FIELDS if expected is RecordReference else _ARTIFACT_FIELDS
    return {name: _raw_attribute(value, name) for name in names}


class _SchemaCheck:
    """Check closed schema, aliases and aggregate occurrences before detachment or reconstruction."""

    def __init__(self, limits, typed):
        """Keep bounded occurrence counts and container identities for one declaration."""
        self.limits, self.typed = limits, typed
        self.references = 0
        self.seen = set()

    def visit(self, value, schema, label, *, virtual=False):
        """Check a bounded subtree in schema order; never dispatch caller type hooks."""
        # Immutable exact pins may repeat; all actual containers must be independent.
        kind = type(value)
        if not virtual and (kind is dict or kind is list or kind is tuple):
            if id(value) in self.seen:
                raise ToolAssessmentValidationError(f"{label}: shared container identity")
            self.seen.add(id(value))
        if type(schema) is dict:
            _closed(value, schema, label)
            for name, child in schema.items():
                if schema is _EVIDENCE and name == "records":
                    role, kinds = _EVIDENCE_ROLES[value["basis"]]
                    child = _fact(_list(("record", role, kinds)))
                self.visit(value[name], child, f"{label}.{name}")
        elif type(schema) is tuple:
            tag = schema[0]
            if tag == "fact":
                _closed(value, dict.fromkeys(("state", "value", "reason")), label)
                if type(value["state"]) is not str or value["state"] not in ("known", "unknown", "unavailable"):
                    raise ToolAssessmentValidationError(f"{label}.state: unsupported fact state")
                if value["state"] == "known":
                    if value["reason"] is not None:
                        raise ToolAssessmentValidationError(f"{label}: known reason must be null")
                    self.visit(value["value"], schema[1], label + ".value")
                else:
                    if value["value"] is not None:
                        raise ToolAssessmentValidationError(f"{label}: missing value must be null")
                    _text(value["reason"], label + ".reason", nonblank=True)
            elif tag == "list":
                if kind is not list and not (self.typed and kind is tuple):
                    raise ToolAssessmentValidationError(f"{label}: expected ordinary ordered collection")
                for child in value:
                    self.visit(child, schema[1], label + "[]")
            elif tag == "enum":
                if kind is not str or value not in schema[1]:
                    raise ToolAssessmentValidationError(f"{label}: unsupported vocabulary value")
            elif tag == "record":
                # Revisit a wire reference without treating the same slot as an alias.
                self.visit(value, RecordReference, label, virtual=True)
                fields = _raw_reference(value, RecordReference) if self.typed else value
                if fields["relationship"] != schema[1] or fields["target_kind"] not in schema[2]:
                    raise ToolAssessmentValidationError(f"{label}: wrong reference role or target kind")
        elif schema is ArtifactReference or schema is RecordReference:
            if self.typed:
                if kind is not schema:
                    raise ToolAssessmentValidationError(f"{label}: expected exact {schema.__name__}")
                value = _raw_reference(value, schema)
            self.references += 1
            _check_limit(self.limits, "max_references", self.references)
            # Identity comparisons avoid hostile metaclass equality/hash dispatch.
            fields = _RECORD_FIELDS if schema is RecordReference else _ARTIFACT_FIELDS
            self.visit(value, fields, label, virtual=True)
        else:
            self.scalar(value, schema, label)

    def scalar(self, value, schema, label):
        """Validate fixed-width domain scalars without constructing references."""
        if schema in ("integer", "revision", "version"):
            domain._integer(value, label, 0 if schema == "integer" else 1)
            if schema == "version" and value != 1:
                raise ToolAssessmentValidationError("version: unsupported assessment version")
            return
        _text(value, label, nonblank=schema in ("nonblank", "timestamp"))
        if schema == "identifier":
            domain._identifier(value, label)
        elif schema == "record_kind":
            domain._kind(value, label)
        elif schema == "timestamp":
            domain._timestamp(value)  # Validate without normalizing authored precision.
        elif schema in ("digest", "artifact_digest"):
            pattern = r"sha256:[0-9a-f]{64}" if schema == "digest" else r"[0-9a-f]{64}"
            if re.fullmatch(pattern, value) is None:
                raise ToolAssessmentValidationError(f"{label}: invalid SHA-256 identity")


def _known(fact):
    """Distinguish explicit knowledge from missing information without inference."""
    return fact["state"] == "known"


def _known_items(fact):
    """Yield authored entries only for a known collection fact."""
    if _known(fact):
        yield from fact["value"]


def _present(fact):
    """Test a known nonempty payload after schema validation."""
    return _known(fact) and bool(fact["value"])


def _require(fact, label):
    """Require a known nonempty payload for a local conditional consistency rule."""
    if not _present(fact):
        raise ToolAssessmentValidationError(f"{label}: requires known nonempty value")


def _unique(fact, key, label):
    """Reject only explicitly unique authored identifiers, preserving other duplicates."""
    seen = set()
    for item in _known_items(fact):
        if item[key] in seen:
            raise ToolAssessmentValidationError(f"{label}: duplicate {key}")
        seen.add(item[key])


def _reference_semantics(root):
    """Validate every pin occurrence and reject conflicting sizes or target kinds globally."""
    sizes, kinds = {}, {}

    def visit(value, schema):
        """Walk only validated fixed schema slots, reconstructing exact domain pins."""
        if type(schema) is dict:
            for name, child in schema.items():
                visit(value[name], child)
        elif type(schema) is tuple:
            if schema[0] == "fact" and _known(value):
                visit(value["value"], schema[1])
            elif schema[0] == "list":
                for child in value:
                    visit(child, schema[1])
            elif schema[0] == "record":
                visit(value, RecordReference)
        elif schema is ArtifactReference:
            ArtifactReference(**value)
            if sizes.setdefault(value["digest"], value["size"]) != value["size"]:
                raise ToolAssessmentValidationError("artifact digest has conflicting sizes")
        elif schema is RecordReference:
            RecordReference(**value)
            key = value["record_id"], value["revision"]
            if kinds.setdefault(key, value["target_kind"]) != value["target_kind"]:
                raise ToolAssessmentValidationError("record revision has conflicting target kinds")
    visit(root, _ROOT)


def _semantics(root):
    """Enforce local report consistency; never infer truth, permission or qualification."""
    _reference_semantics(root)
    environment = root["environment"]
    _unique(environment["configuration"], "name", "configuration")
    _unique(environment["dependencies"], "name", "dependencies")
    _unique(root["checks"], "check_id", "checks")
    if environment["observability"] == "pinned_description":
        if not (_present(environment["records"]) or _present(environment["artifacts"])):
            raise ToolAssessmentValidationError("pinned_description: requires known environment pins")
    if environment["observability"] == "reported_version_only":
        if not (_present(environment["reported_version"]) or _present(environment["implementation_version"])):
            raise ToolAssessmentValidationError("reported_version_only: requires a known version")
    if environment["kind"] == "remote" or environment["observability"] == "opaque":
        if _known(environment["limitations"]) and not environment["limitations"]["value"]:
            raise ToolAssessmentValidationError("remote/opaque environment: requires explicit limitations")

    def evidence_rules(evidence):
        """Validate the supplied evidence category, not its authenticity or sufficiency."""
        basis = evidence["basis"]
        if basis == "assessor_assertion":
            _require(evidence["statement"], "assessor_assertion.statement")
        elif basis == "builder_self_test":
            if not (_present(evidence["records"]) or _present(evidence["artifacts"])):
                raise ToolAssessmentValidationError("builder_self_test: requires a supplied report pin")
        else:
            _require(evidence["records"], basis + ".records")

    def all_evidence(value, schema):
        """Apply evidence rules at every nested evidence slot in the fixed schema."""
        if schema is _EVIDENCE:
            evidence_rules(value)
        if type(schema) is dict:
            for name, child in schema.items():
                all_evidence(value[name], child)
        elif type(schema) is tuple:
            if schema[0] == "fact" and _known(value):
                all_evidence(value["value"], schema[1])
            elif schema[0] == "list":
                for item in value:
                    all_evidence(item, schema[1])
    all_evidence(root, _ROOT)
    for check in _known_items(root["checks"]):
        outcome = check["outcome"]
        if outcome in ("pass", "fail"):
            for name in ("scope", "method", "expected", "observed", "evidence"):
                _require(check[name], "check." + name)
            if not any(item["basis"] == check["basis"] for item in check["evidence"]["value"]):
                raise ToolAssessmentValidationError("check.evidence: missing declared basis")
        elif outcome == "unperformed":
            if _known(check["observed"]) or _present(check["evidence"]):
                raise ToolAssessmentValidationError("unperformed check: observations/evidence contradict outcome")
    for review in _known_items(root["reviews"]):
        if review["outcome"] != "unperformed":
            for name in ("scope", "rationale"):
                _require(review[name], "review." + name)
    permission = root["execution_permission"]
    if permission["status"] in ("permitted", "denied", "revoked", "restricted"):
        _require(permission["rationale"], "execution_permission.rationale")
    if permission["status"] in ("permitted", "restricted"):
        _require(permission["scope"], "execution_permission.scope")
    for dimension in _DIMENSIONS:
        report = root["qualification"][dimension]
        if report["outcome"] != "unperformed":
            for name in ("scope", "rationale"):
                _require(report[name], "qualification." + dimension + "." + name)
    lifecycle = root["lifecycle"]
    if lifecycle["status"] in ("active", "restricted", "suspended", "withdrawn", "superseded"):
        _require(lifecycle["rationale"], "lifecycle.rationale")
    if lifecycle["status"] == "superseded" and not (_known(lifecycle["replacement"]) or _known(lifecycle["superseded_by"])):
        raise ToolAssessmentValidationError("superseded: requires replacement or superseded_by")
    if _known(lifecycle["replacement"]):
        replacement, target = lifecycle["replacement"]["value"]["release"], root["target"]["release"]
        if (replacement["record_id"], replacement["revision"]) == (target["record_id"], target["revision"]):
            raise ToolAssessmentValidationError("replacement: cannot name the assessed exact revision")


def _checked_tree(value, limits, *, typed=False):
    """Preflight then check complete schema/aggregates without copying or constructing pins."""
    if type(value) is not dict:
        raise ToolAssessmentValidationError("content: expected ordinary dictionary")
    _preflight(value, limits, typed=typed)
    if "format" not in value:
        raise NotTypedContentError("tool assessment content: missing format discriminator")
    try:
        _SchemaCheck(limits, typed).visit(value, _ROOT, "content")
    except ToolAssessmentValidationError:
        raise
    except (DomainValidationError, AttributeError, TypeError, RecursionError, OverflowError) as error:
        raise ToolAssessmentValidationError("content: invalid assessment fields") from error
    return value


def _finish(value):
    """Detach guarded content and complete semantics before canonical serialization."""
    try:
        result = _detached(value)
        _semantics(result)
        return result
    except ToolAssessmentValidationError:
        raise
    except (DomainValidationError, AttributeError, TypeError, RecursionError, OverflowError) as error:
        raise ToolAssessmentValidationError("content: invalid assessment declaration") from error


@dataclass(frozen=True, init=False, eq=False)
class ToolAssessment:
    """One canonical private report snapshot, carrying no admission or execution authority."""

    _json: str
    __hash__ = None

    def __init__(self, *, assessment_id: str, attribution: dict, target: dict,
                 environment: dict, scope: dict, checks: dict, reviews: dict,
                 limitations: dict, issues: dict, execution_permission: dict,
                 qualification: dict, lifecycle: dict, limits: ToolAssessmentLimits | None = None):
        """Validate mandatory authored sections and exact typed pins; retain only canonical JSON."""
        limits = _checked_limits(limits)
        if type(self) is not ToolAssessment:
            raise ToolAssessmentValidationError("constructor: expected exact ToolAssessment")
        root = dict(format=_FORMAT, version=1, kind="tool_assessment", assessment_id=assessment_id,
                    attribution=attribution, target=target, environment=environment, scope=scope,
                    checks=checks, reviews=reviews, limitations=limitations, issues=issues,
                    execution_permission=execution_permission, qualification=qualification, lifecycle=lifecycle)
        result = _finish(_checked_tree(root, limits, typed=True))
        object.__setattr__(self, "_json", _canonical(result))

    def to_dict(self, *, limits: ToolAssessmentLimits | None = None) -> dict:
        """Revalidate the complete retained canonical snapshot and return a fresh wire tree."""
        limits = _checked_limits(limits)
        if type(self) is not ToolAssessment:
            raise ToolAssessmentValidationError("content: expected exact ToolAssessment")
        text = _raw_attribute(self, "_json")
        result = _finish(_checked_tree(_parse(text, limits, retained=True), limits))
        if _canonical(result) != text:
            raise ToolAssessmentValidationError("content: noncanonical retained snapshot")
        return result

    @classmethod
    def from_dict(cls, value: dict, *, limits: ToolAssessmentLimits | None = None) -> "ToolAssessment":
        """Decode closed ordinary wire fields without resolving or authenticating their pins."""
        limits = _checked_limits(limits)
        if cls is not ToolAssessment:
            raise ToolAssessmentValidationError("decoder: expected exact ToolAssessment class")
        result = object.__new__(ToolAssessment)
        object.__setattr__(result, "_json", _canonical(_finish(_checked_tree(value, limits))))
        return result

    @property
    def assessment_id(self):
        """Return explicit stable identity after complete fresh-default-limit validation."""
        return ToolAssessment.to_dict(self)["assessment_id"]

    def __eq__(self, other):
        """Validate left first, then compare complete exact reports under fresh default ceilings."""
        left = ToolAssessment.to_dict(self)
        if type(other) is not ToolAssessment:
            return NotImplemented
        return left == ToolAssessment.to_dict(other)


def decode_content(value: dict, *, limits: ToolAssessmentLimits | None = None) -> ToolAssessment:
    """Decode a bounded complete v1 wire dictionary into a detached passive report."""
    return ToolAssessment.from_dict(value, limits=limits)


def dumps_content(value: ToolAssessment, *, limits: ToolAssessmentLimits | None = None) -> str:
    """Revalidate exact retained content and emit compact canonical ASCII JSON, without newline."""
    return _canonical(ToolAssessment.to_dict(value, limits=limits))


def loads_content(data: str | bytes, *, limits: ToolAssessmentLimits | None = None) -> ToolAssessment:
    """Bound all external UTF-8 bytes and lexical work before parsing and semantic decoding."""
    limits = _checked_limits(limits)
    return ToolAssessment.from_dict(_parse(data, limits), limits=limits)
