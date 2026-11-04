"""Passive immutable tool-release declarations; identities confer no execution authority."""

from dataclasses import dataclass
import hashlib
import re

from research_pipeline import domain, resources, work_product
from research_pipeline.domain import ArtifactReference, RecordReference, DomainValidationError
from research_pipeline.resources import Dimension
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.work_product import WorkProductFile
from research_pipeline.tool_release_codec import (
    ToolReleaseValidationError, ToolReleaseLimitError, ToolReleaseLimits,
    checked_limits, raw_attribute, raw_fields, preflight, check_limit, detached,
    canonical, parse,
)

_FORMAT = "research_pipeline.tool_release_content"
_IDENTITY_PLACEHOLDER = "sha256:" + "0" * 64


def _fact(payload):
    """Describe one required known/unknown/unavailable declaration in the fixed schema."""
    return ("fact", payload)


def _list(payload):
    """Describe an ordered collection without introducing a public schema language."""
    return ("list", payload)


def _enum(words):
    """Describe a closed vocabulary of ordinary authored scalar strings."""
    return ("enum", tuple(words.split()))


def _record(role, kinds=None):
    """Describe an exact reported link with a required relationship and explicit target kind."""
    return ("record", role, None if kinds is None else tuple(kinds.split()))


_TEXTS = _fact(_list("text"))
_TEXT = _fact("text")
_VISIBILITY = _enum("complete partial unobserved unknown unavailable")
_IMPLEMENTATION = {
    "identity": _TEXT, "reported_version": _TEXT,
    "artifacts": _fact(_list(WorkProductFile)),
    "source_records": _fact(_list(_record("implementation_source", "source work_product_manifest"))),
    "observability": _enum("pinned_local reported_version_only opaque unknown unavailable"),
    "limitations": _TEXTS,
}
_IDENTITY = {
    "tool_id": "identifier", "display_name": "nonblank", "release_label": _TEXT,
    "origin": _enum("bundled researcher_supplied research_generated"),
    "supplier": _TEXTS, "developer": _TEXTS, "declared_by": _TEXT,
    "declared_at": _fact("timestamp"),
    "provenance_records": _fact(_list(_record("reported_provenance"))),
    "access": {"status": _enum("available restricted unavailable unknown"), "detail": "nonblank"},
    "license": _TEXT, "implementation": _IMPLEMENTATION, "readme": "nonblank",
}
_ADAPTER = {
    "adapter_id": "identifier", "version": _TEXT, "description": _TEXT,
    "files": _fact(_list(WorkProductFile)), "entry_file": _fact("optional_path"),
    "entry_point": _TEXT,
}
_PARAMETER = {
    "name": "nonblank", "type": "nonblank", "shape": _TEXTS,
    "presence": _enum("required optional conditional"), "description": _TEXT,
    "artifact_conventions": _TEXTS,
}
_INTERFACE = {"description": _TEXT, "fields": _fact(_list(_PARAMETER))}
_INVOCATION = {
    "kind": _enum("local_program local_callable remote_service composite_workflow"),
    "adapter": _ADAPTER,
    "configuration": _fact(_list({"name": "nonblank", "value": "text"})),
    "inputs": _INTERFACE, "outputs": _INTERFACE, "artifact_conventions": _TEXTS,
    "mode": _enum("synchronous asynchronous either unknown"), "mode_detail": _TEXT,
    "environment_requirements": _TEXTS,
}
_SCIENCE = dict.fromkeys((
    "equations_or_transformations", "units", "conventions", "input_domains", "output_domains",
    "parameter_regimes", "boundary_conditions", "approximations", "error_claims",
    "success_meaning", "failure_conditions"), _TEXTS)
_ACTIVITY = {
    "state": _enum("none declared unknown unobserved"), "runtime": _TEXT,
    "providers": _TEXTS, "description": _TEXT, "visibility": _VISIBILITY, "limitations": _TEXTS,
}
_DELEGATION = dict.fromkeys((
    "assignment", "input_artifacts_and_context", "acceptance_criteria", "deliverables",
    "descendant_scope", "backend_state_and_run_identity", "waiting_parent_behavior"), _TEXT)
_EFFECTS = {
    "filesystem_read": _TEXTS, "filesystem_write": _TEXTS, "network_destinations": _TEXTS,
    "credential_references": _fact(_list({"credential_id": "identifier", "purpose": "nonblank"})),
    "external_effects": _TEXTS,
    "child_tools": _fact(_list(_record("child_tool", "tool_release"))),
    "model_activity": _ACTIVITY, "delegated_activity": _ACTIVITY,
    "delegation_contract": _DELEGATION,
}
_EXTRA_UNITS = dict(zip((
    "memory_bytes", "output_bytes", "context_capacity_tokens", "per_call_output_tokens",
    "model_concurrency", "descendant_jobs", "retries", "repairs"),
    ("byte", "byte", "token", "token", "concurrent_call", "job", "retry", "repair")))
_BOUND = {
    "name": _enum(" ".join((*resources.UNITS, *_EXTRA_UNITS, "monetary"))),
    "dimension": ("nullable", Dimension), "unit": "nonblank", "quantity": _fact("integer"),
    "mode": _enum("claimed_hard monitored_target unknown"),
    "enforceability": _enum("reported_enforceable not_enforceable unknown unavailable"),
    "mechanism": _TEXT, "limitations": _TEXTS,
}
_RECOVERY = {
    "cancellation": _TEXT, "checkpointing": _TEXT,
    "replay_safety": _enum("safe unsafe conditional unknown unavailable"),
    "replay_conditions": _TEXT, "uncertain_completion": _TEXT,
    "descendant_cancellation": _TEXT, "reconciliation": _TEXT,
}
_RESOURCES = {
    "bounds": _list(_BOUND), "recovery": _RECOVERY,
    "nested_accounting": {"basis": _enum("exclusive inclusive mixed unknown unavailable"),
                          "visibility": _VISIBILITY, "limitations": _TEXTS},
}
_EVIDENCE = {
    "intended_uses": _TEXTS, "reported_qualified_applicability": _TEXTS,
    "qualification_reports": _fact(_list(_record("reported_qualification", "tool_assessment"))),
    "self_tests": _fact(_list(ArtifactReference)),
    "evidence": _fact(_list(_record("reported_evidence", "evidence"))),
    "issues": _fact(_list(_record("reported_issue", "issue"))),
    "tested_environments": _TEXTS, "tested_cases": _TEXTS,
    "known_failures": _TEXTS, "limitations": _TEXTS,
}
_REPRODUCIBILITY = {
    "dependencies": _TEXTS, "dependency_artifacts": _fact(_list(ArtifactReference)),
    "dependency_records": _fact(_list(_record("build_dependency"))),
    "environment": _TEXTS, "determinism": _enum("deterministic stochastic conditional unknown unavailable"),
    "randomness": _TEXTS, "output_provenance": _TEXTS, "replay_limits": _TEXTS,
}
_SECTIONS = {
    "identity": _IDENTITY, "invocation": _INVOCATION, "scientific_meaning": _SCIENCE,
    "effects_authority": _EFFECTS, "resources_recovery": _RESOURCES,
    "evidence_limitations": _EVIDENCE, "reproducibility": _REPRODUCIBILITY,
}
_ROOT = {
    "format": _enum(_FORMAT), "version": "version", "kind": _enum("tool_release"),
    "release_id": "digest", "adapter_identity": "digest", "configuration_identity": "digest",
    **_SECTIONS,
}
_TYPED_SCHEMAS = {
    ArtifactReference: {"digest": "artifact_digest", "size": "integer"},
    RecordReference: {"record_id": "identifier", "revision": "revision", "relationship": "identifier", "target_kind": "record_kind"},
    WorkProductFile: {"path": "path", "artifact": ArtifactReference},
    Dimension: {"dimension_id": "identifier", "kind": "nonblank", "unit": "nonblank", "currency": ("nullable", "text"), "scale": "revision"},
}


def _closed(value, names, label):
    """Require an ordinary dictionary with exactly the schema's required fields."""
    if type(value) is not dict or value.keys() != names.keys():
        raise ToolReleaseValidationError(f"{label}: incorrect closed fields")


def _text(value, label, *, nonblank=False):
    """Validate authored text without trimming or rewriting its retained spelling."""
    if type(value) is not str or (nonblank and not value.strip()):
        raise ToolReleaseValidationError(f"{label}: expected {'nonblank ' if nonblank else ''}text")


class _SchemaCheck:
    """Check the fixed schemas and finish aggregate reference/path charges before reconstruction."""

    def __init__(self, limits, typed, units):
        """Keep only counters and mode for the bounded schema traversal."""
        self.limits, self.typed, self.units = limits, typed, units
        self.references = 0

    def visit(self, value, schema, label):
        """Validate a bounded subtree with inert exact-type checks before consuming its fields."""
        if type(schema) is dict:
            _closed(value, schema, label)
            for name, child in schema.items():
                self.visit(value[name], child, f"{label}.{name}")
        elif type(schema) is tuple:
            tag = schema[0]
            if tag == "fact":
                _closed(value, dict.fromkeys(("state", "value", "reason")), label)
                self.visit(value["state"], _enum("known unknown unavailable"), label + ".state")
                if value["state"] == "known":
                    if value["reason"] is not None:
                        raise ToolReleaseValidationError(f"{label}: known reason must be null")
                    self.visit(value["value"], schema[1], label + ".value")
                else:
                    if value["value"] is not None:
                        raise ToolReleaseValidationError(f"{label}: missing fact value must be null")
                    _text(value["reason"], label + ".reason", nonblank=True)
            elif tag == "list":
                kind = type(value)
                if kind is not list and not (self.typed and kind is tuple):
                    raise ToolReleaseValidationError(f"{label}: expected ordinary ordered collection")
                for child in value:
                    self.visit(child, schema[1], label + "[]")
            elif tag == "enum":
                if type(value) is not str or value not in schema[1]:
                    raise ToolReleaseValidationError(f"{label}: unsupported vocabulary value")
            elif tag == "nullable":
                if value is not None:
                    self.visit(value, schema[1], label)
            elif tag == "record":
                self.visit(value, RecordReference, label)
                fields = raw_fields(value) if self.typed else value
                if fields["relationship"] != schema[1] or (schema[2] is not None and fields["target_kind"] not in schema[2]):
                    raise ToolReleaseValidationError(f"{label}: wrong reference role or target kind")
        elif schema in _TYPED_SCHEMAS:
            if self.typed:
                if type(value) is not schema:
                    raise ToolReleaseValidationError(f"{label}: expected exact {schema.__name__}")
                value = raw_fields(value)
            if schema in (ArtifactReference, RecordReference):
                self.references += 1
                check_limit(self.limits, "max_references", self.references)
            self.visit(value, _TYPED_SCHEMAS[schema], label)
        else:
            self.scalar(value, schema, label)

    def scalar(self, value, schema, label):
        """Check scalar conventions and charge path-prefix work without path normalization."""
        if schema == "optional_path" and value is None:
            return
        if schema in ("integer", "revision", "version"):
            minimum = 0 if schema == "integer" else 1
            domain._integer(value, label, minimum)
            if schema == "version" and value != 1:
                raise ToolReleaseValidationError("version: unsupported tool-release version")
            return
        _text(value, label, nonblank=schema in ("nonblank", "path", "optional_path"))
        if schema == "identifier":
            domain._identifier(value, label)
        elif schema == "record_kind":
            domain._kind(value, label)
        elif schema == "timestamp" and value:
            domain._timestamp(value)
        elif schema in ("digest", "artifact_digest"):
            pattern = r"sha256:[0-9a-f]{64}" if schema == "digest" else r"[0-9a-f]{64}"
            if re.fullmatch(pattern, value) is None:
                raise ToolReleaseValidationError(f"{label}: invalid SHA-256 identity")
        elif schema in ("path", "optional_path"):
            components = value.count("/") + 1
            self.units += components * (components + 1) // 2
            check_limit(self.limits, "max_reconstruction_units", self.units)


def _known(fact):
    """Test factual state explicitly; known null and empty values remain distinguishable."""
    return fact["state"] == "known"


def _nonblank_fact(fact):
    """Identify a known nonblank statement for conditional semantic requirements."""
    return _known(fact) and bool(fact["value"].strip())


def _unique(fact, key, label):
    """Reject duplicate names within a known ordered declaration without deduplicating it."""
    if _known(fact):
        values = [item[key] for item in fact["value"]]
        if len(set(values)) != len(values):
            raise ToolReleaseValidationError(f"{label}: duplicate {key}")


def _references_and_dimensions(root):
    """Revalidate raw reference/dimension fields after aggregate guards; check cross-release consistency."""
    sizes, kinds, dimensions = {}, {}, {}

    def visit(value, schema):
        """Walk bounded schema slots, constructing only exact domain reference and dimension values."""
        if type(schema) is dict:
            for name, child in schema.items():
                visit(value[name], child)
        elif type(schema) is tuple:
            if schema[0] == "fact" and _known(value):
                visit(value["value"], schema[1])
            elif schema[0] == "list":
                for child in value:
                    visit(child, schema[1])
            elif schema[0] == "nullable" and value is not None:
                visit(value, schema[1])
            elif schema[0] == "record":
                visit(value, RecordReference)
        elif schema is ArtifactReference:
            ArtifactReference(**value)
            prior = sizes.setdefault(value["digest"], value["size"])
            if prior != value["size"]:
                raise ToolReleaseValidationError("artifact digest has conflicting sizes")
        elif schema is RecordReference:
            RecordReference(**value)
            key = (value["record_id"], value["revision"])
            if kinds.setdefault(key, value["target_kind"]) != value["target_kind"]:
                raise ToolReleaseValidationError("record revision has conflicting target kinds")
        elif schema is Dimension:
            Dimension(**value)
            if dimensions.setdefault(value["dimension_id"], value) != value:
                raise ToolReleaseValidationError("dimension_id has conflicting definitions")
        elif schema is WorkProductFile:
            visit(value["artifact"], ArtifactReference)
    visit(root, _ROOT)


def _semantics(root):
    """Reject contradictions and validate bundle paths; no declaration becomes a permission or receipt."""
    _references_and_dimensions(root)
    identity, invocation = root["identity"], root["invocation"]
    implementation, adapter = identity["implementation"], invocation["adapter"]
    for fact in (implementation["artifacts"], adapter["files"]):
        if _known(fact):
            work_product._validate_paths(item["path"] for item in fact["value"])
    entry = adapter["entry_file"]
    if _known(entry) and entry["value"] is not None:
        work_product._path(entry["value"], "entry_file")
        if not _known(adapter["files"]) or entry["value"] not in [item["path"] for item in adapter["files"]["value"]]:
            raise ToolReleaseValidationError("entry_file: must exactly match an adapter file")
    if implementation["observability"] == "pinned_local" and not (_known(implementation["artifacts"]) and implementation["artifacts"]["value"]):
        raise ToolReleaseValidationError("pinned_local requires known nonempty implementation artifacts")
    if implementation["observability"] == "reported_version_only" and not _nonblank_fact(implementation["reported_version"]):
        raise ToolReleaseValidationError("reported_version_only requires a known nonblank version")
    if invocation["kind"] == "remote_service":
        if implementation["observability"] == "pinned_local" or (_known(implementation["artifacts"]) and implementation["artifacts"]["value"]):
            raise ToolReleaseValidationError("remote service cannot assert a local implementation pin")
        for fact in (implementation["limitations"], root["reproducibility"]["replay_limits"]):
            if _known(fact) and not fact["value"]:
                raise ToolReleaseValidationError("remote service requires explicit implementation and replay limitations")
    _unique(invocation["configuration"], "name", "configuration")
    for name in ("inputs", "outputs"):
        _unique(invocation[name]["fields"], "name", name)
    effects = root["effects_authority"]
    _unique(effects["credential_references"], "credential_id", "credential_references")
    for name in ("model_activity", "delegated_activity"):
        activity = effects[name]
        if activity["state"] == "none":
            if not (_known(activity["runtime"]) and activity["runtime"]["value"] == "" and _known(activity["providers"]) and activity["providers"]["value"] == []):
                raise ToolReleaseValidationError(f"{name}: none requires known empty runtime and providers")
        if activity["state"] == "declared" and not _nonblank_fact(activity["description"]):
            raise ToolReleaseValidationError(f"{name}: declared activity requires a known nonblank description")
    required, currencies = set(), set()
    for bound in root["resources_recovery"]["bounds"]:
        name, dimension = bound["name"], bound["dimension"]
        if name == "monetary":
            if dimension is None or dimension["kind"] != "monetary" or dimension["currency"] in currencies:
                raise ToolReleaseValidationError("monetary bound: missing dimension or duplicate currency")
            currencies.add(dimension["currency"])
        else:
            if name in required:
                raise ToolReleaseValidationError("duplicate required bound name")
            required.add(name)
        if name in resources.UNITS or name == "monetary":
            if dimension is None or dimension["kind"] != name or bound["unit"] != dimension["unit"]:
                raise ToolReleaseValidationError("bound: dimension kind/unit mismatch")
        elif dimension is not None or bound["unit"] != _EXTRA_UNITS[name]:
            raise ToolReleaseValidationError("declaration-only bound: expected null dimension and fixed unit")
        if bound["mode"] == "claimed_hard" and (not _known(bound["quantity"]) or bound["enforceability"] == "not_enforceable"):
            raise ToolReleaseValidationError("claimed_hard requires a known quantity and compatible enforceability")
        if bound["enforceability"] == "reported_enforceable" and not _nonblank_fact(bound["mechanism"]):
            raise ToolReleaseValidationError("reported_enforceable requires a known nonblank mechanism")
    if required != set(resources.UNITS) | set(_EXTRA_UNITS):
        raise ToolReleaseValidationError("bounds: every required category must occur exactly once")


def _hash(value):
    """Hash a previously bounded canonical ASCII preimage without a release placeholder."""
    return "sha256:" + hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def _validate(value, limits, *, typed=False):
    """Run ordered guards, schemas, aggregate checks, semantics, then generate or verify identities."""
    if type(value) is not dict:
        raise ToolReleaseValidationError("content: expected ordinary dictionary")
    units = preflight(value, limits, typed=typed)
    if "format" not in value:
        raise NotTypedContentError("tool release content: missing format discriminator")
    try:
        _SchemaCheck(limits, typed, units).visit(value, _ROOT, "content")
        result = detached(value)
        _semantics(result)
        adapter = _hash(result["invocation"]["adapter"])
        configuration = _hash(result["invocation"]["configuration"])
        if typed:
            result["adapter_identity"], result["configuration_identity"] = adapter, configuration
        elif (result["adapter_identity"], result["configuration_identity"]) != (adapter, configuration):
            raise ToolReleaseValidationError("subordinate identity mismatch")
        release = _hash({key: child for key, child in result.items() if key != "release_id"})
        if typed:
            result["release_id"] = release
        elif result["release_id"] != release:
            raise ToolReleaseValidationError("release_id mismatch")
        return result
    except ToolReleaseValidationError:
        raise
    except (DomainValidationError, AttributeError, RecursionError, OverflowError) as error:
        raise ToolReleaseValidationError("invalid tool-release declaration: " + str(error)) from error


@dataclass(frozen=True, init=False, eq=False)
class ToolRelease:
    """One canonical private snapshot of seven passive declarations, never a registered capability."""

    _json: str
    __hash__ = None

    def __init__(self, *, identity: dict, invocation: dict, scientific_meaning: dict,
                 effects_authority: dict, resources_recovery: dict, evidence_limitations: dict,
                 reproducibility: dict, limits: ToolReleaseLimits | None = None):
        """Validate exact constructor sections and typed pins, then retain only canonical text.

        External ceilings apply before copying or reconstruction. Caller dictionaries,
        reference objects and processing limits are never retained by the release.
        """
        limits = checked_limits(limits)
        if type(self) is not ToolRelease:
            raise ToolReleaseValidationError("constructor: expected exact ToolRelease")
        root = dict(format=_FORMAT, version=1, kind="tool_release",
                    release_id=_IDENTITY_PLACEHOLDER, adapter_identity=_IDENTITY_PLACEHOLDER,
                    configuration_identity=_IDENTITY_PLACEHOLDER,
                    identity=identity, invocation=invocation, scientific_meaning=scientific_meaning,
                    effects_authority=effects_authority, resources_recovery=resources_recovery,
                    evidence_limitations=evidence_limitations, reproducibility=reproducibility)
        object.__setattr__(self, "_json", canonical(_validate(root, limits, typed=True)))

    def to_dict(self, *, limits=None) -> dict:
        """Revalidate retained canonical content and return a fresh ordinary wire tree."""
        limits = checked_limits(limits)
        if type(self) is not ToolRelease:
            raise ToolReleaseValidationError("content: expected exact ToolRelease")
        text = raw_attribute(self, "_json")
        value = _validate(parse(text, limits, retained=True), limits)
        if canonical(value) != text:
            raise ToolReleaseValidationError("retained snapshot is not canonical")
        return value

    @classmethod
    def from_dict(cls, value: dict, *, limits=None) -> "ToolRelease":
        """Verify complete wire fields and all three identities under external ceilings."""
        limits = checked_limits(limits)
        if cls is not ToolRelease:
            raise ToolReleaseValidationError("decoder: expected exact ToolRelease class")
        result = object.__new__(ToolRelease)
        object.__setattr__(result, "_json", canonical(_validate(value, limits)))
        return result

    @property
    def tool_id(self):
        """Return the stable opaque ID after revalidating all content with default ceilings."""
        return ToolRelease.to_dict(self)["identity"]["tool_id"]

    @property
    def release_id(self):
        """Return the derived declaration identity after complete default-limit revalidation."""
        return ToolRelease.to_dict(self)["release_id"]

    def __eq__(self, other):
        """Compare complete revalidated exact snapshots; never trust cached identity strings."""
        left = ToolRelease.to_dict(self)
        if type(other) is not ToolRelease:
            return NotImplemented
        return left == ToolRelease.to_dict(other)


def decode_content(value: dict, *, limits=None) -> ToolRelease:
    """Decode a complete version-one wire dictionary without resolving its reported links."""
    return ToolRelease.from_dict(value, limits=limits)


def dumps_content(value: ToolRelease, *, limits=None) -> str:
    """Revalidate an exact release and emit canonical ASCII JSON without a newline."""
    return canonical(ToolRelease.to_dict(value, limits=limits))


def loads_content(data: str | bytes, *, limits=None) -> ToolRelease:
    """Bound external UTF-8 input before parsing, then verify schemas and content identities."""
    limits = checked_limits(limits)
    return ToolRelease.from_dict(parse(data, limits), limits=limits)
