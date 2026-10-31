"""Pure versioned intake dossiers; attributed readiness proposals grant no authority."""

from dataclasses import dataclass, fields
import json

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, _fields, _identifier, _integer, _snapshot, _validate_json_string,
)
from research_pipeline.scientific import NotTypedContentError, _record_from_dict
from research_pipeline.assessment import _code, _copy, _nested, _rebuild, _reference, _unique_targets
from research_pipeline.source import DeclaredText, Source, _text, _texts, _values, _ids
from research_pipeline.corpus import CorpusLocation, CorpusInspection, CorpusManifest, _array, _locations
from research_pipeline.work_product import WorkProductManifest


_FORMAT = "research_pipeline.project_content"
_CATEGORIES = ("definition", "assumption", "convention", "existing_work", "proposed_question",
               "proposed_baseline", "contradiction", "gap", "unprocessed_remainder", "brief_choice")
_LINK_ROLES = (("intake_context", "research_context"), ("intake_claim", "claim"),
               ("intake_justification", "justification"), ("intake_evidence", "evidence"),
               ("intake_review", "review"), ("intake_issue", "issue"),
               ("intake_work_product", "work_product_manifest"))
_PROJECT_ROLES = (("initial_corpus", "initial_corpus", "corpus_manifest"),
                  ("current_corpus", "current_corpus", "corpus_manifest"),
                  ("context", "context", "research_context"),
                  ("brief", "research_brief", "work_product_manifest"),
                  ("intake_report", "intake_report", "work_product_manifest"),
                  ("supersedes", "supersedes", "project"))


@dataclass(frozen=True)
class AttributedText:
    """Researcher-supplied text and unauthenticated attribution, each explicitly known or unknown."""

    text: DeclaredText
    attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        for name in ("text", "attribution"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, AttributedText, "AttributedText")
        return {
            "text": value.text.to_dict(),
            "attribution": value.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "AttributedText":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "AttributedText")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "AttributedText")
        result["text"] = _nested(result["text"], DeclaredText, "text")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        return cls(**result)


@dataclass(frozen=True)
class IntakeLink:
    """An exact typed scientific relationship with an inert explanation; never an endorsement."""

    reference: RecordReference
    relation: str

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        object.__setattr__(self, "reference", _copy(self.reference, RecordReference, "reference"))
        if (self.reference.relationship, self.reference.target_kind) not in _LINK_ROLES:
            raise DomainValidationError("reference: unsupported intake relationship/target_kind")
        _text(self.relation, "relation")

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, IntakeLink, "IntakeLink")
        return {
            "reference": value.reference.to_dict(),
            "relation": value.relation,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "IntakeLink":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "IntakeLink")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "IntakeLink")
        result["reference"] = _record_from_dict(result["reference"], "reference")
        return cls(**result)


@dataclass(frozen=True)
class IntakeDeclaration:
    """One attributed observation, new proposal or explicit unknown origin within the inspected subset."""

    declaration_id: str
    category: str
    text: str
    origin: str
    origin_detail: DeclaredText
    attribution: DeclaredText
    locations: tuple[CorpusLocation, ...]
    links: tuple[IntakeLink, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        _identifier(self.declaration_id, "declaration_id")
        _code(self.category, _CATEGORIES, "category")
        _text(self.text, "text")
        _code(self.origin, ("supplied_observation", "new_proposal", "unknown_origin"), "origin")
        for name in ("origin_detail", "attribution"):
            object.__setattr__(self, name, _copy(getattr(self, name), DeclaredText, name))
        if (self.origin == "unknown_origin") != (self.origin_detail.value is None):
            raise DomainValidationError("origin_detail: unknown_origin requires unknown_reason; other origins require known detail")
        object.__setattr__(self, "locations", _locations(self.locations, "locations"))
        object.__setattr__(self, "links", _values(self.links, IntakeLink, "links"))
        _unique_targets(tuple(link.reference for link in self.links), "links")
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, IntakeDeclaration, "IntakeDeclaration")
        return {
            "declaration_id": value.declaration_id,
            "category": value.category,
            "text": value.text,
            "origin": value.origin,
            "origin_detail": value.origin_detail.to_dict(),
            "attribution": value.attribution.to_dict(),
            "locations": [item.to_dict() for item in value.locations],
            "links": [item.to_dict() for item in value.links],
            "limitations": list(value.limitations),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "IntakeDeclaration":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "IntakeDeclaration")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "IntakeDeclaration")
        result["origin_detail"] = _nested(result["origin_detail"], DeclaredText, "origin_detail")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["locations"] = [_nested(item, CorpusLocation, f"locations[{index}]")
                           for index, item in enumerate(_array(result["locations"], "locations"))]
        result["links"] = [_nested(item, IntakeLink, f"links[{index}]")
                           for index, item in enumerate(_array(result["links"], "links"))]
        result["limitations"] = _array(result["limitations"], "limitations")
        return cls(**result)


@dataclass(frozen=True)
class IntakeRequirement:
    """An outstanding attributed requirement for intake or later admission, never an executable grant."""

    requirement_id: str
    kind: str
    stage: str
    description: AttributedText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        _identifier(self.requirement_id, "requirement_id")
        _code(self.kind, ("material", "prerequisite", "policy_proposal", "resource_proposal"), "kind")
        _code(self.stage, ("intake", "research_admission"), "stage")
        object.__setattr__(self, "description", _copy(self.description, AttributedText, "description"))

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, IntakeRequirement, "IntakeRequirement")
        return {
            "requirement_id": value.requirement_id,
            "kind": value.kind,
            "stage": value.stage,
            "description": value.description.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "IntakeRequirement":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "IntakeRequirement")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "IntakeRequirement")
        result["description"] = _nested(result["description"], AttributedText, "description")
        return cls(**result)


@dataclass(frozen=True)
class ProceduralJudgment:
    """An explained human or caller judgment, not a scientific conclusion inferred by this codec."""

    status: str
    explanation: str
    attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        _code(self.status, ("not_assessed", "affirmed", "not_affirmed"), "status")
        _text(self.explanation, "explanation")
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))
        if self.status == "affirmed" and self.attribution.value is None:
            raise DomainValidationError("attribution: affirmed judgment requires known attribution")

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, ProceduralJudgment, "ProceduralJudgment")
        return {
            "status": value.status,
            "explanation": value.explanation,
            "attribution": value.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ProceduralJudgment":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "ProceduralJudgment")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "ProceduralJudgment")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        return cls(**result)


@dataclass(frozen=True)
class ReadinessProposal:
    """An attributed proposal with local evidence IDs and independent explained procedural judgments."""

    status: str
    reasons: tuple[str, ...]
    attribution: DeclaredText
    evidence_declarations: tuple[str, ...]
    substantive_relevance: ProceduralJudgment
    assignment_usability: ProceduralJudgment

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        _code(self.status, ("not_assessed", "insufficient_materials", "incomplete_intake", "proposed_ready"), "status")
        object.__setattr__(self, "reasons", _texts(self.reasons, "reasons"))
        if not self.reasons:
            raise DomainValidationError("reasons: at least one reason required")
        object.__setattr__(self, "attribution", _copy(self.attribution, DeclaredText, "attribution"))
        object.__setattr__(self, "evidence_declarations", _ids(self.evidence_declarations, "evidence_declarations"))
        for name in ("substantive_relevance", "assignment_usability"):
            object.__setattr__(self, name, _copy(getattr(self, name), ProceduralJudgment, name))
        if self.status == "proposed_ready" and not self.evidence_declarations:
            raise DomainValidationError("evidence_declarations: proposed_ready requires evidence")

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, ReadinessProposal, "ReadinessProposal")
        return {
            "status": value.status,
            "reasons": list(value.reasons),
            "attribution": value.attribution.to_dict(),
            "evidence_declarations": list(value.evidence_declarations),
            "substantive_relevance": value.substantive_relevance.to_dict(),
            "assignment_usability": value.assignment_usability.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ReadinessProposal":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "ReadinessProposal")
        result = _fields(value, {item.name for item in fields(cls)}, set(), "ReadinessProposal")
        result["reasons"] = _array(result["reasons"], "reasons")
        result["attribution"] = _nested(result["attribution"], DeclaredText, "attribution")
        result["evidence_declarations"] = _array(result["evidence_declarations"], "evidence_declarations")
        result["substantive_relevance"] = _nested(result["substantive_relevance"], ProceduralJudgment, "substantive_relevance")
        result["assignment_usability"] = _nested(result["assignment_usability"], ProceduralJudgment, "assignment_usability")
        return cls(**result)


@dataclass(frozen=True)
class ProjectSetup:
    """A full intake snapshot; identity/revision live only in its envelope and all canonical states are null."""

    title: AttributedText
    objective: AttributedText
    researcher_intent: AttributedText
    initial_corpus: RecordReference
    current_corpus: RecordReference
    context: RecordReference | None
    brief: RecordReference | None
    intake_report: RecordReference | None
    inspection: CorpusInspection
    declarations: tuple[IntakeDeclaration, ...]
    remaining: tuple[IntakeRequirement, ...]
    readiness: ReadinessProposal
    limitations: tuple[str, ...]
    supersedes: RecordReference | None
    revision_reason: str
    revision_attribution: DeclaredText

    def __post_init__(self) -> None:
        """Detach exact nested values and reject malformed local declarations without resolving targets."""
        for name, expected in (("title", AttributedText), ("objective", AttributedText),
                               ("researcher_intent", AttributedText), ("inspection", CorpusInspection),
                               ("readiness", ReadinessProposal), ("revision_attribution", DeclaredText)):
            object.__setattr__(self, name, _copy(getattr(self, name), expected, name))
        for name, role, kind in _PROJECT_ROLES:
            value = getattr(self, name)
            if value is not None or name in ("initial_corpus", "current_corpus"):
                object.__setattr__(self, name, _reference(value, role, kind, name))
        object.__setattr__(self, "declarations", _values(self.declarations, IntakeDeclaration, "declarations"))
        object.__setattr__(self, "remaining", _values(self.remaining, IntakeRequirement, "remaining"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        _text(self.revision_reason, "revision_reason")
        _validate_setup(self)

    def to_dict(self) -> dict:
        """Return detached exact wire fields after revalidating bypassable frozen state."""
        value = _rebuild(self, ProjectSetup, "ProjectSetup")
        return {
            "format": _FORMAT, "version": 1, "kind": "project",
            "title": value.title.to_dict(),
            "objective": value.objective.to_dict(),
            "researcher_intent": value.researcher_intent.to_dict(),
            "initial_corpus": value.initial_corpus.to_dict(),
            "current_corpus": value.current_corpus.to_dict(),
            "context": None if value.context is None else value.context.to_dict(),
            "brief": None if value.brief is None else value.brief.to_dict(),
            "intake_report": None if value.intake_report is None else value.intake_report.to_dict(),
            "inspection": value.inspection.to_dict(),
            "declarations": [item.to_dict() for item in value.declarations],
            "remaining": [item.to_dict() for item in value.remaining],
            "readiness": value.readiness.to_dict(),
            "limitations": list(value.limitations),
            "supersedes": None if value.supersedes is None else value.supersedes.to_dict(),
            "revision_reason": value.revision_reason,
            "revision_attribution": value.revision_attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ProjectSetup":
        """Decode required exact fields and bound wire arrays before reconstructing members."""
        _snapshot(value, "ProjectSetup")
        if "format" not in value:
            raise NotTypedContentError("project content: missing format discriminator")
        _code(value["format"], (_FORMAT,), "format")
        result = _fields(value, {item.name for item in fields(cls)} | {"format", "version", "kind"}, set(), "ProjectSetup")
        _integer(result["version"], "version", 1)
        if result["version"] != 1:
            raise DomainValidationError("version: unsupported project content version")
        _code(result["kind"], ("project",), "kind")
        for name in ("format", "version", "kind"):
            del result[name]
        result["title"] = _nested(result["title"], AttributedText, "title")
        result["objective"] = _nested(result["objective"], AttributedText, "objective")
        result["researcher_intent"] = _nested(result["researcher_intent"], AttributedText, "researcher_intent")
        result["initial_corpus"] = _record_from_dict(result["initial_corpus"], "initial_corpus")
        result["current_corpus"] = _record_from_dict(result["current_corpus"], "current_corpus")
        if result["context"] is not None:
            result["context"] = _record_from_dict(result["context"], "context")
        if result["brief"] is not None:
            result["brief"] = _record_from_dict(result["brief"], "brief")
        if result["intake_report"] is not None:
            result["intake_report"] = _record_from_dict(result["intake_report"], "intake_report")
        result["inspection"] = _nested(result["inspection"], CorpusInspection, "inspection")
        result["declarations"] = [_nested(item, IntakeDeclaration, f"declarations[{index}]")
                           for index, item in enumerate(_array(result["declarations"], "declarations"))]
        result["remaining"] = [_nested(item, IntakeRequirement, f"remaining[{index}]")
                           for index, item in enumerate(_array(result["remaining"], "remaining"))]
        result["readiness"] = _nested(result["readiness"], ReadinessProposal, "readiness")
        result["limitations"] = _array(result["limitations"], "limitations")
        if result["supersedes"] is not None:
            result["supersedes"] = _record_from_dict(result["supersedes"], "supersedes")
        result["revision_attribution"] = _nested(result["revision_attribution"], DeclaredText, "revision_attribution")
        return cls(**result)


def _validate_setup(value):
    """Enforce snapshot membership and proposal prerequisites without implying authority or byte availability."""
    if value.initial_corpus.revision != 1:
        raise DomainValidationError("initial_corpus: must select revision 1")
    if value.current_corpus.record_id != value.initial_corpus.record_id:
        raise DomainValidationError("current_corpus: must retain initial corpus identity")
    if value.brief is not None and value.context is None:
        raise DomainValidationError("brief: requires context")
    for name, identity in (("declarations", "declaration_id"), ("remaining", "requirement_id")):
        items = getattr(value, name)
        if len({getattr(item, identity) for item in items}) != len(items):
            raise DomainValidationError(f"{name}: duplicate {identity}")
    if len(value.inspection.locations) + sum(len(item.locations) for item in value.declarations) > 4096:
        raise DomainValidationError("locations: at most 4096 total occurrences")
    if sum(len(item.links) for item in value.declarations) > 4096:
        raise DomainValidationError("links: at most 4096 total occurrences")
    inspected = set(value.inspection.locations)
    declarations = {item.declaration_id: item for item in value.declarations}
    for item in value.declarations:
        if any(location not in inspected for location in item.locations):
            raise DomainValidationError(f"declaration {item.declaration_id} locations: must occur exactly in inspection.locations")
    readiness = value.readiness
    if any(identity not in declarations for identity in readiness.evidence_declarations):
        raise DomainValidationError("readiness.evidence_declarations: unknown declaration ID")
    if readiness.status != "proposed_ready":
        return
    for name in ("title", "objective", "researcher_intent"):
        if getattr(value, name).text.value is None:
            raise DomainValidationError(f"{name}.text: proposed_ready requires known text")
    if (value.inspection.coverage != "selected_material" or not inspected
            or value.inspection.attribution.value is None):
        raise DomainValidationError("inspection: proposed_ready requires attributed selected_material locations")
    for name in ("context", "brief", "intake_report"):
        if getattr(value, name) is None:
            raise DomainValidationError(f"{name}: required for proposed_ready")
    for name in ("substantive_relevance", "assignment_usability"):
        if getattr(readiness, name).status != "affirmed":
            raise DomainValidationError(f"readiness.{name}: proposed_ready requires affirmed judgment")
    if readiness.attribution.value is None:
        raise DomainValidationError("readiness.attribution: proposed_ready requires known attribution")
    if not any(declarations[identity].locations for identity in readiness.evidence_declarations):
        raise DomainValidationError("readiness.evidence_declarations: requires a declaration with an inspected location")
    if any(item.stage == "intake" for item in value.remaining):
        raise DomainValidationError("remaining: proposed_ready cannot retain intake requirements")


def setup_presentation(content: ProjectSetup) -> str:
    """Revalidate and present a proposal as setup progress; no result authorizes research admission."""
    value = _rebuild(content, ProjectSetup, "content")
    return {"insufficient_materials": "awaiting_materials", "not_assessed": "setup_incomplete",
            "incomplete_intake": "setup_incomplete", "proposed_ready": "awaiting_authorization"}[value.readiness.status]


def _target(reference):
    """Compare exact pins independently of their incoming relationship labels."""
    return None if reference is None else (reference.record_id, reference.revision)


def _location_uses(value):
    """Yield every inspection/declaration location with its own diagnostic context, retaining repeats."""
    for index, location in enumerate(value.inspection.locations):
        yield f"inspection.locations[{index}]", location
    for declaration in value.declarations:
        for index, location in enumerate(declaration.locations):
            yield f"declaration {declaration.declaration_id} locations[{index}]", location


def _validate_dossier(value, values):
    """Check each dossier role against cached exact typed metadata after corpus history validation.

    The store owns resolution and the transaction. This pure check deliberately
    examines every occurrence, including historical snapshots and cached targets;
    it neither reads bytes nor upgrades a corpus entry's historical inspection.
    """
    corpus = values.get(_target(value.current_corpus))
    if type(corpus) is not CorpusManifest:
        raise DomainValidationError(f"current_corpus target {_target(value.current_corpus)}: expected supported CorpusManifest")
    entries = {item.entry_id: item for item in corpus.entries}
    for field, location in _location_uses(value):
        target = _target(location.source)
        diagnostic = (f"{field} entry {location.entry_id} source_location target "
                      f"{target[0]}@{target[1]} location {location.location_id}")
        entry = entries.get(location.entry_id)
        if entry is None or entry.status != "captured" or _target(entry.source) != target:
            raise DomainValidationError(f"{diagnostic}: must use its captured current-corpus entry's exact Source pin")
        source = values.get(target)
        if type(source) is not Source:
            raise DomainValidationError(f"{diagnostic}: expected supported Source")
        found = next((item for item in source.locations if item.location_id == location.location_id), None)
        if (found is None or found.artifact_id is None
                or found.artifact_id not in {item.artifact_id for item in entry.originals}):
            raise DomainValidationError(f"{diagnostic}: must anchor to an original selected by this entry")
    corpora = {_target(value.initial_corpus), _target(value.current_corpus)}
    inspected = {_target(location.source) for location in value.inspection.locations}
    sources = {_target(entry.source) for entry in corpus.entries if entry.status == "captured"}
    for name, product_kind in (("brief", "research_brief"), ("intake_report", "intake_report")):
        reference = getattr(value, name)
        if reference is None:
            continue
        target = _target(reference)
        diagnostic = f"{reference.relationship} target {target[0]}@{target[1]}"
        document = values.get(target)
        if type(document) is not WorkProductManifest or document.product_kind != product_kind:
            raise DomainValidationError(f"{diagnostic}: expected manifest product_kind {product_kind}")
        if _target(document.context) != _target(value.context):
            raise DomainValidationError(f"{diagnostic}: context must equal exact project context")
        dependencies = document.build_dependencies
        if {_target(ref) for ref in dependencies if ref.target_kind == "corpus_manifest"} != corpora:
            raise DomainValidationError(f"{diagnostic}: corpus_manifest build_dependencies must equal initial/current pins")
        linked = {_target(ref) for ref in document.linked_sources}
        if not inspected <= linked or not linked <= sources:
            raise DomainValidationError(f"{diagnostic}: linked_sources must include inspected Sources and belong to current captured entries")
        for dependency in dependencies:
            if dependency.target_kind == "source" and _target(dependency) not in sources:
                raise DomainValidationError(f"{diagnostic}: Source build_dependency must belong to current corpus")
            if (dependency.target_kind == "research_context"
                    and (value.context is None or _target(dependency) != _target(value.context))):
                raise DomainValidationError(f"{diagnostic}: research_context build_dependency must equal project context")


def _validate_successor(value, previous):
    """Preserve the original baseline and monotonic corpus selection across complete project history."""
    if previous is None:
        if value.supersedes is not None:
            raise DomainValidationError("supersedes: incomplete project history to revision 1")
        return
    if value.initial_corpus != previous.initial_corpus:
        raise DomainValidationError(f"initial_corpus target {value.initial_corpus.record_id}@{value.initial_corpus.revision}: "
                                    "cannot rebind baseline; use a new project identity")
    if (value.current_corpus.record_id != previous.current_corpus.record_id
            or value.current_corpus.revision < previous.current_corpus.revision):
        raise DomainValidationError(f"current_corpus target {value.current_corpus.record_id}@{value.current_corpus.revision}: "
                                    "cannot change identity or regress; append a corrective corpus revision")


def decode_content(value: dict) -> ProjectSetup:
    """Decode only explicit version-1 project content, without target resolution or artifact reads."""
    return ProjectSetup.from_dict(value)


def dumps_content(value: ProjectSetup) -> str:
    """Revalidate an exact setup and serialize sorted compact ASCII JSON, preserving array order."""
    if type(value) is not ProjectSetup:
        raise DomainValidationError("content: expected ProjectSetup")
    return _snapshot(value.to_dict(), "project content")


def _unique_object(pairs):
    """Reject duplicate JSON keys at every depth before ordinary dictionary construction loses them."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DomainValidationError(f"project content: duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    """Reject nonfinite JSON constants instead of silently accepting nonstandard numeric values."""
    raise DomainValidationError(f"project content: nonfinite JSON constant {value}")


def loads_content(data: str | bytes) -> ProjectSetup:
    """Decode strict UTF-8 JSON, translating syntax, encoding and excessive nesting failures."""
    if type(data) not in (str, bytes):
        raise DomainValidationError("project content: expected ordinary str or bytes")
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        _validate_json_string(data, "project content JSON")
        return decode_content(json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    except DomainValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise DomainValidationError(f"project content: cannot decode JSON: {error}") from error


def _links(content: ProjectSetup) -> tuple[tuple[RecordReference, ...], tuple[ArtifactReference, ...]]:
    """Project exact ordered record occurrences, including repeated pins; projects have no direct artifacts."""
    records = [content.supersedes] if content.supersedes is not None else []
    records.extend((content.initial_corpus, content.current_corpus))
    records.extend(ref for ref in (content.context, content.brief, content.intake_report) if ref is not None)
    records.extend(location.source for location in content.inspection.locations)
    for declaration in content.declarations:
        records.extend(location.source for location in declaration.locations)
        records.extend(link.reference for link in declaration.links)
    return tuple(records), ()


def _history_link(record_id, revision, content):
    """Require baseline null or this project identity's exact immediately preceding revision."""
    previous = content.supersedes
    if revision == 1:
        if previous is not None:
            raise DomainValidationError("supersedes: revision 1 requires null")
    elif previous is None or previous.record_id != record_id or previous.revision != revision - 1:
        raise DomainValidationError("supersedes: required exact same-record immediate predecessor")


def encode_envelope(record_id: str, revision: int, content: ProjectSetup,
                    provenance: CreationProvenance) -> RecordEnvelope:
    """Build a detached null-state project envelope with complete exact projections and local history checks."""
    content = loads_content(dumps_content(content))
    provenance = _copy(provenance, CreationProvenance, "provenance")
    records, artifacts = _links(content)
    envelope = RecordEnvelope(record_id, revision, "project", content.to_dict(), provenance, records, artifacts)
    _history_link(envelope.record_id, envelope.revision, content)
    return envelope


def decode_envelope(envelope: RecordEnvelope) -> ProjectSetup:
    """Reject malformed classes, states, history links and ordered projections without repairing them."""
    if type(envelope) is not RecordEnvelope:
        raise DomainValidationError("envelope: expected RecordEnvelope")
    try:
        _copy(envelope.provenance, CreationProvenance, "envelope.provenance")
        for name, expected in (("record_references", RecordReference), ("artifact_references", ArtifactReference)):
            values = getattr(envelope, name)
            if type(values) not in (list, tuple):
                raise DomainValidationError(f"envelope.{name}: expected list/tuple")
            for index, value in enumerate(values):
                _copy(value, expected, f"envelope.{name}[{index}]")
    except AttributeError as error:
        raise DomainValidationError("envelope: missing nested value") from error
    checked = _copy(envelope, RecordEnvelope, "envelope")
    content = decode_content(checked.content)
    if checked.kind != "project":
        raise DomainValidationError("envelope.kind: expected project")
    if checked.operational_status is not None or checked.scientific_disposition is not None:
        raise DomainValidationError("envelope: project states must be null")
    records, artifacts = _links(content)
    if checked.record_references != records:
        raise DomainValidationError("envelope.record_references: disagree with complete ordered content roles")
    if checked.artifact_references != artifacts:
        raise DomainValidationError("envelope.artifact_references: disagree with complete ordered empty artifact projection")
    _history_link(checked.record_id, checked.revision, content)
    return content
