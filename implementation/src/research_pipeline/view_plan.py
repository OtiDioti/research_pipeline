"""Pure deterministic reading plans with inert originals and verified generated navigation."""

from dataclasses import dataclass
import hashlib
import json
import posixpath
import re
import unicodedata

from research_pipeline.domain import ArtifactReference, DomainValidationError, RecordEnvelope
from research_pipeline.snapshot import (
    DetachedSnapshot, SnapshotLimits, SnapshotLimitError, _canonical, _strict_json, _json_parts,
)
from research_pipeline.work_product import WorkProductManifest, _validate_paths
from research_pipeline.source import Source
from research_pipeline.corpus import CorpusManifest, _validate_selection
from research_pipeline.project import ProjectSetup, _validate_dossier, setup_presentation
from research_pipeline.operating_authority import SignedOperatingDecision
from research_pipeline.scientific import Claim, Justification
from research_pipeline.assessment import Review, Issue


class ViewPlanError(ValueError):
    """A readable projection, portable inventory or generated link is inconsistent."""


_HEADINGS = ("Purpose and scope", "Contents", "Current work", "Provenance", "Use",
             "Dependencies and limitations", "Editing route")
_LIMITATIONS = (
    "Private local reading snapshot; not a backup, redistributable export, independently filtered "
    "worker/reviewer workspace or new source of scientific truth.",
    "Manifest artifacts remain expected_unverified: planning does not establish byte availability. "
    "Successful materialization verifies the complete copied generation with modes 0500/0400; "
    "offline inspection checks its current local contents against these expectations.",
    "Restrictions are retained declarations, not disclosure permission.",
    "Local decoding and outgoing navigation do not prove original submit_typed admission, transitive "
    "admission, scientific validity, authenticated authorship or effective authority. Shallow admission "
    "roles retain their original meaning. Hyperlink counts establish no support.",
    "Unrelated records and reverse-only incoming relationships were not searched. Missing incoming "
    "records may be outside selection; this is not a complete project/store inventory.",
    "All attachments of each reached Source are included. Corpus original selection, inspection and "
    "exposure coverage remain distinct; inclusion does not imply selection or inspection by the corpus.",
    "No sync, plugin, subscription, execution, operating policy, authorized readiness, task admission, "
    "scientific qualification or permission enforcement is supplied. Full runtime run/tool/policy/task "
    "management and optional workspace hierarchies are unavailable.",
    "Authored internal links are preserved bytes, not certified or rewritten. No attachments are read, "
    "rendered, extracted, imported, compiled or executed by this planner.",
    "manifest.json is the reserved descriptor, excluded from its own hashed file list. Offline inspection "
    "reconstructs the canonical plan and checks the descriptor and all expected bytes separately.",
)
_EDITING = ("Displayed edits have no canonical effect. Changes require a separate supported checkout/import "
            "or new record submission. There is no view-refresh/import service.")
_SUFFIXES = {".md", ".txt", ".tex", ".pdf", ".png", ".jpg", ".csv", ".json", ".ipynb"}
_AREAS = {"project": "brief/projects", "research_context": "brief/contexts", "corpus_manifest": "brief/seeds",
          "source": "literature", "claim": "claims", "review": "reviews", "issue": "navigation/issues",
          "justification": "navigation/justifications", "evidence": "navigation/evidence"}
_BRANCH_PRODUCTS = {"note": "notes", "checkpoint": "notes", "derivation": "derivations",
                    "calculation": "calculations", "notebook": "notebooks", "figure": "figures"}


@dataclass(frozen=True)
class GeneratedFile:
    """One immutable generated file; data are planned bytes, never authored artifact contents."""

    relative_path: str
    data: bytes
    role: str
    mode: int = 0o400

    def __post_init__(self):
        """Require immutable byte content and the fixed owner-read-only expected mode."""
        if type(self.relative_path) is not str or type(self.data) is not bytes or type(self.role) is not str or type(self.mode) is not int or self.mode != 0o400:
            raise ViewPlanError("invalid generated file")


@dataclass(frozen=True)
class ArtifactCopy:
    """One physical copy expectation; digest/size describe metadata expectations, separate from observed byte verification."""

    relative_path: str
    digest: str
    size: int
    mode: int = 0o400

    def __post_init__(self):
        """Validate exact expected content address without opening any bytes."""
        if type(self.relative_path) is not str or type(self.mode) is not int or self.mode != 0o400:
            raise ViewPlanError("invalid artifact copy")
        try:
            ArtifactReference(self.digest, self.size)
        except DomainValidationError as error:
            raise ViewPlanError(str(error)) from error


@dataclass(frozen=True)
class DirectoryEntry:
    """One useful planned directory; empty relative path identifies the reading root."""

    relative_path: str
    mode: int = 0o500

    def __post_init__(self):
        """Require an immutable relative path and fixed owner-read/search-only mode."""
        if type(self.relative_path) is not str or type(self.mode) is not int or self.mode != 0o500:
            raise ViewPlanError("invalid directory entry")


@dataclass(frozen=True)
class ReadablePlan:
    """Immutable generated bytes, artifact expectations and canonical manifest for one generation."""

    snapshot_id: str
    plan_id: str
    generated_files: tuple[GeneratedFile, ...]
    artifact_copies: tuple[ArtifactCopy, ...]
    directories: tuple[DirectoryEntry, ...]
    manifest_bytes: bytes

    def __post_init__(self):
        """Revalidate full inventory, canonical identity and rendered navigation on construction."""
        verify_plan_links(self)

    def to_dict(self):
        """Return independently decoded manifest metadata after public-boundary validation."""
        verify_plan_links(self)
        return json.loads(self.manifest_bytes)

    @property
    def limits(self):
        """Return fresh effective capture/output budgets retained in the canonical manifest."""
        return SnapshotLimits(**self.to_dict()["limits"])


def _token(identity):
    """Derive a full-length stable record token from the exact validated ASCII identity."""
    return "r-" + hashlib.sha256(identity.encode("ascii")).hexdigest()


def _safe(value):
    """Escape supplied inline text as inert numeric entities, including punctuation and controls.

    Machine headings/targets never use supplied text. Entities prevent Markdown,
    HTML, wikilinks, URL autolinks and frontmatter injection; bidi/control characters
    are displayed as explicit Unicode escape notation rather than active controls.
    """
    result = []
    for char in str(value):
        if unicodedata.category(char) in ("Cc", "Cf", "Cs", "Zl", "Zp"):
            result.append("&#92;u" + format(ord(char), "04x"))
        elif char.isalnum() or char == " ":
            result.append(char)
        else:
            result.append(f"&#{ord(char)};")
    return "".join(result)


def _link(page, target, label, fragment=None):
    """Emit ordinary relative links using only generated destinations and escaped display text."""
    path = posixpath.relpath(target, posixpath.dirname(page) or ".")
    if fragment is not None:
        path += "#" + fragment
    return f"[{_safe(label)}]({path})"


def _literal(value):
    """Yield inert indented JSON scalar notation, preserving exact whitespace and control spelling."""
    # JSON escaping makes line breaks/bidi controls visible and prevents code-block
    # termination by supplied newlines; originals remain exact in envelope.json.
    yield "    "
    yield from _json_parts(value)
    yield "\n\n"


def _values(value):
    """Yield literal labeled data with bounded escaping; dictionaries never imply reference semantics."""
    if isinstance(value, dict):
        if not value:
            yield "No recorded values.\n\n"
        for key, child in value.items():
            for offset in range(0, len(key), 2048):
                yield _safe(key[offset:offset + 2048])
            yield ":\n\n"
            yield from _values(child)
    elif isinstance(value, (list, tuple)):
        if not value:
            yield "No recorded values.\n\n"
        for index, child in enumerate(value):
            yield f"Recorded item {index + 1}:\n\n"
            yield from _values(child)
    elif value is None:
        yield "Recorded null; no value declared.\n\n"
    else:
        yield from _literal(value)


def _projection_map(records):
    """Qualify detached projections, checking corpus mappings before dependent project displays.

    Local codec classifications remain intact. These pure checks neither repeat
    admission nor establish historical certification for generic submissions.
    """
    from research_pipeline.store import _decode_typed_envelope

    decoded, notices = {}, {}
    for key, record in records.items():
        if record["classification"]["category"] == "locally_decoded":
            decoded[key] = _decode_typed_envelope(RecordEnvelope.from_dict(json.loads(record["envelope_json"])))
    for key, value in decoded.items():
        if type(value) is not CorpusManifest:
            continue
        try:
            _validate_selection(value, decoded)
        except DomainValidationError as error:
            notices[key] = {"category": "cross_record_projection_unavailable", "detail": str(error)[:512]}
    for key, value in decoded.items():
        if type(value) is not ProjectSetup:
            continue
        try:
            # Project admission constrains these pins. Navigation independently
            # retains generic-admitted records, so display must qualify them here.
            for name in ("initial_corpus", "current_corpus"):
                pin = getattr(value, name)
                target = (pin.record_id, pin.revision)
                if type(decoded.get(target)) is not CorpusManifest:
                    raise DomainValidationError(f"{name} typed projection unavailable")
                if target in notices:
                    raise DomainValidationError(
                        f"{name} target {pin.record_id}@{pin.revision}: "
                        "dependent corpus mapping projection unavailable; " + notices[target]["detail"])
            _validate_dossier(value, decoded)
            if value.context is not None:
                from research_pipeline.scientific import ResearchContext
                if type(decoded.get((value.context.record_id, value.context.revision))) is not ResearchContext:
                    raise DomainValidationError("context typed projection unavailable")
        except DomainValidationError as error:
            notices[key] = {"category": "cross_record_projection_unavailable", "detail": str(error)[:512]}
    return decoded, notices


def _record_paths(records, decoded):
    """Assign one exact bundle per record, using only actual kinds and decoded product relationships."""
    tokens, paths, branches = {}, {}, {}
    for key, entry in records.items():
        token = _token(key[0])
        if token in tokens and tokens[token] != key[0]:
            raise ViewPlanError("record token collision")
        tokens[token] = key[0]
        envelope = json.loads(entry["envelope_json"])
        kind, value = envelope["kind"], decoded.get(key)
        area = _AREAS.get(kind, "navigation/records/" + kind)
        if kind == "decision" and entry["classification"]["category"] == "generic":
            area = "decisions"
        if kind == "branch":
            area = "branches/" + token + "/revisions"
            branches.setdefault(token, set()).add(key)
        if type(value) is WorkProductManifest:
            product = value.product_kind
            if value.branch is not None:
                branch_key = (value.branch.record_id, value.branch.revision)
                branch = json.loads(records[branch_key]["envelope_json"])
                if branch["kind"] != "branch":
                    raise ViewPlanError("work product branch target is not branch")
                branches.setdefault(_token(branch_key[0]), set()).add(branch_key)
            if product == "research_brief":
                area = "brief/documents"
            elif product in ("intake_report", "reading_report", "end_of_run_report"):
                area = "reports/" + {"intake_report": "intake", "reading_report": "reading", "end_of_run_report": "end-of-run"}[product]
                if product == "end_of_run_report" and value.run is not None:
                    area = "reports/runs/" + _token(value.run.record_id)
            elif product in _BRANCH_PRODUCTS and value.branch is not None:
                area = "branches/" + _token(value.branch.record_id) + "/" + _BRANCH_PRODUCTS[product]
            else:
                area = "navigation/work-products"
        paths[key] = f"{area}/{token}/{key[1]}/README.md"
    return paths, branches


def _mapping_items(envelope, value, decoded):
    """Yield one declared artifact mapping at a time so file budgets bound accumulation."""
    if type(value) is WorkProductManifest:
        for item in value.files:
            yield ("work_product_file", item.path, item.artifact, {
                "original_path": item.path, "entry_file": item.path == value.entry_file,
                "product_kind": value.product_kind, "authors": list(value.authors),
                "media_declaration": None, "original_mode": None, "restrictions": None})
    elif type(value) is Source:
        for item in value.originals:
            yield ("source_original", item.artifact_id, item.artifact,
                   {**item.to_dict(), "restrictions": value.restrictions.to_dict()})
        for extraction in value.extractions:
            for item in extraction.outputs:
                yield ("source_extraction", item.artifact_id, item.artifact,
                    {**item.to_dict(), "extraction_id": extraction.extraction_id,
                     "original_inputs": list(extraction.original_inputs), "restrictions": value.restrictions.to_dict()})
    elif type(value) is CorpusManifest:
        for entry in value.entries:
            source = decoded.get((entry.source.record_id, entry.source.revision)) if entry.source is not None else None
            for item in entry.originals:
                identifier = _canonical({"entry_id": entry.entry_id, "artifact_id": item.artifact_id})
                yield ("corpus_selected_original", identifier, item.artifact, {
                    **item.to_dict(), "entry_id": entry.entry_id, "source": entry.source.to_dict(),
                    "entry_file": False, "original_mode": None,
                    "restrictions": source.restrictions.to_dict() if type(source) is Source else None,
                    "restriction_projection": "recorded_source_declarations" if type(source) is Source else "unavailable"})
    else:
        for ordinal, artifact in enumerate(envelope.artifact_references):
            role = "envelope_attachment" if value is None else envelope.kind + "_attachment"
            yield (role, str(ordinal), artifact, {"ordinal": ordinal,
                "original_path": None, "entry_file": False, "media_declaration": None,
                "original_mode": None, "restrictions": None})


def _mappings(key, envelope, value, bundle, decoded):
    """Encode each exact logical mapping as an inert filename without collecting all mappings."""
    for role, identifier, artifact, details in _mapping_items(envelope, value, decoded):
        logical = {"record_id": key[0], "revision": key[1], "role": role, "identifier": identifier}
        original_path = details.get("path", details.get("original_path"))
        if original_path is not None:
            logical["original_path"] = original_path
        suffix = posixpath.splitext(original_path or "")[1].lower()
        if suffix not in _SUFFIXES:
            suffix = ".bin"
        path = bundle + "/originals/a-" + hashlib.sha256(_canonical(logical).encode("ascii")).hexdigest() + suffix
        yield {"logical_key": logical, "relative_path": path, "digest": artifact.digest,
               "size": artifact.size, "availability": "expected_unverified", "hash_kind": "expected",
               "provenance": envelope.provenance.to_dict(), "details": details}


class _Output:
    """Local bounded accumulator; reserves the complete inventory before constructing page bytes."""

    def __init__(self, limits, planned_paths, copies):
        """Check file counts and physical-copy amplification, reserving manifest.json explicitly."""
        self.limits = limits
        self.generated = []
        self.paths = set(planned_paths)
        if len({c.relative_path for c in copies}) != len(copies):
            raise ViewPlanError("colliding logical artifact mappings")
        if len(self.paths) != len(planned_paths) or self.paths & {c.relative_path for c in copies}:
            raise ViewPlanError("duplicate planned file path")
        if len(self.paths) + len(copies) > limits.max_files:
            raise SnapshotLimitError("max_files exceeded before rendering")
        self.total = sum(c.size for c in copies)
        if self.total > limits.max_total_bytes:
            raise SnapshotLimitError("physical artifact copies exceed max_total_bytes")
        if any(c.size > limits.max_file_bytes for c in copies):
            raise SnapshotLimitError("artifact copy exceeds max_file_bytes")

    def add(self, path, chunks, role):
        """Append bounded UTF-8 chunks, failing before retaining an oversized generated file."""
        if path not in self.paths:
            raise ViewPlanError("unreserved or duplicate generated file")
        self.paths.remove(path)
        pieces, size = [], 0
        for chunk in chunks:
            data = chunk.encode("utf-8")
            size += len(data)
            self.total += len(data)
            if size > self.limits.max_file_bytes or self.total > self.limits.max_total_bytes:
                raise SnapshotLimitError(f"{path}: generated byte budget exceeded")
            pieces.append(data)
        result = GeneratedFile(path, b"".join(pieces), role)
        self.generated.append(result)
        return result


def _json_chunks(value):
    """Yield canonical JSON without allocating the complete output before budget checks."""
    yield from _json_parts(value)


# Fixed field groups provide useful headings without letting payload keys generate headings.
_FIELDS = {
    "project": (("Objective and researcher intent", ("title", "objective", "researcher_intent")),
                ("Declarations", ("declarations",)), ("Remaining decisions", ("remaining", "readiness")),
                ("Inspection and limitations", ("inspection", "limitations", "revision_reason", "revision_attribution"))),
    "corpus_manifest": (("Seed inventory", ("title", "purpose", "selection_provenance", "attribution", "entries")),
                        ("Inspection and exposure limitations", ("observations", "exposures", "limitations")),
                        ("Original mappings and unresolved links", ("links", "relationships", "changes", "revision_reason", "revision_attribution"))),
    "source": (("Origin and restrictions", ("work_id", "upstream_identity", "upstream_version", "title", "authors", "provenance", "restrictions")),
               ("Originals and extraction lineage", ("originals", "extractions")),
               ("Source locations", ("locations",)), ("Reading coverage and reported statements", ("reading", "statements", "limitations"))),
    "work_product_manifest": (("Authored work product", ("product_kind", "title", "purpose", "authors", "entry_file", "limitations")),
                              ("Build dependencies", ("build_dependencies",))),
    "research_context": (("Context definitions and qualifications", ("question", "equations", "definitions", "units", "conventions", "mathematical_domains", "boundary_conditions", "initial_conditions", "parameter_regime", "approximations", "limit_ordering")),),
    "claim": (("Claim statement", ("statement", "category", "quantifiers", "approximation_qualifications")),
              ("Assumptions", ("assumptions",)), ("Open obligations", ("open_obligations",))),
    "justification": (("Premises and conclusions", ("context", "premises", "required_assumptions", "method", "conclusions", "evidence", "limitations")),),
    "evidence": (("Reported evidence", ("origin", "target_property", "method", "tested_scope", "result", "uncertainty_details", "failure_details", "target_claims", "input_records", "input_artifacts")),),
    "review": (("Attributed assessment", ("reviewer", "origin", "assessment")), ("Route outcomes", ("route_assessments",)),
               ("Independence and limitations", ("independence", "limitations", "reported_checks")), ("Open obligations", ("open_obligations",))),
    "issue": (("Objection and proposed action", ("disputed_point", "objection_or_counterexample", "severity", "disposition", "proposed_discriminating_action", "rationale", "origin", "limitations", "supporting_evidence")),),
}


def _properties(envelope, value, snapshot_id):
    """Emit only fixed YAML keys and JSON-compatible quoted scalars for exact supported identities."""
    properties = {"record_id": envelope.record_id, "revision": envelope.revision, "kind": envelope.kind,
                  "snapshot_id": snapshot_id}
    for name in ("context", "branch"):
        reference = getattr(value, name, None) if value is not None else None
        if reference is not None:
            properties[name + "_id"] = reference.record_id
            properties[name + "_revision"] = reference.revision
    yield "---\n"
    for name, scalar in properties.items():
        yield name + ": " + json.dumps(str(scalar), ensure_ascii=True) + "\n"
    yield "---\n\n"


def _record_body(key, entry, value, notice, paths, decoded, envelopes, mappings, snapshot_id):
    """Render exact captured fields/relations, qualifying signed decisions as historical and unverified.

    This detached projection has neither current external policy nor a trusted
    evaluation clock; approval prose never becomes current permission here.
    """
    page = paths[key]
    envelope = envelopes[key]
    yield from _properties(envelope, value, snapshot_id)
    yield "# Exact record revision\n\n"
    yield _safe(f"{key[0]}@{key[1]}") + "\n\n"
    yield "## Purpose and scope\n\n"
    yield "One exact committed record, with local classification and attributed declarations.\n\n"
    yield from _values(entry["classification"])
    if notice:
        yield "Typed mapping projection unavailable: recorded declarations below are disputed/unestablished mappings. Exact records and links remain retained.\n\n"
        yield from _values(notice)
    yield "## Contents\n\n"
    yield _link(page, posixpath.dirname(page) + "/envelope.json", "Exact envelope JSON") + "\n\n"
    if mappings:
        yield _link(page, posixpath.dirname(page) + "/originals/README.md", "Expected originals") + "\n\n"
        for mapping in mappings:
            label = "Authored entry file" if mapping["details"].get("entry_file") else "Expected attachment"
            yield _link(page, mapping["relative_path"], label) + "\n\n"
            yield from _values(mapping["logical_key"])
    yield "## Current work\n\n"
    yield "Canonical operational_status and scientific_disposition are separate from attributed assessment or issue disposition.\n\n"
    yield from _values({"operational_status": envelope.operational_status,
                       "scientific_disposition": envelope.scientific_disposition})
    if value is None:
        yield "Typed projection unavailable. Opaque committed payload follows; generic keys do not establish runtime or scientific semantics.\n\n"
        yield from _literal(envelope.content)
    else:
        if type(value) is ProjectSetup:
            yield "Setup presentation (proposal only): " + _safe(setup_presentation(value)) + ".\n\n"
        if type(value) is WorkProductManifest and value.product_kind == "end_of_run_report":
            yield "Recorded run report; this declaration does not establish successful execution, stop reasons or continuation readiness.\n\n"
        content = value.to_dict()
        if type(value) is SignedOperatingDecision:
            yield "## Operating decision\n\n"
            yield ("Operating decision status: historical; unverified. "
                   "This detached snapshot cannot verify current external operator policy or trusted time. "
                   "An approval is not current permission. Recompute eligibility inside the later admitting "
                   "write transaction; this view reserves nothing and guarantees no dispatch.\n\n")
            yield from _values(content)
        for heading, names in _FIELDS.get(envelope.kind, ()):
            yield "## " + heading + "\n\n"
            for name in names:
                yield _safe(name) + ":\n\n"
                yield from _values(content[name])
    if envelope.kind == "claim":
        if type(value) is not Claim:
            yield "## Assumptions\n\nTyped claim projection unavailable.\n\n"
            yield "## Open obligations\n\nTyped claim projection unavailable.\n\n"
        for heading, expected in (("Supporting justifications", Justification),
                                  ("Contradictions and objections", Issue), ("Reviews", Review)):
            yield "## " + heading + "\n\n"
            found = False
            for incoming, candidate in decoded.items():
                if type(candidate) is not expected:
                    continue
                refs = (candidate.conclusions if expected is Justification else candidate.affected_records
                        if expected is Issue else (candidate.candidate_claim,))
                if any((ref.record_id, ref.revision) == key for ref in refs):
                    found = True
                    yield _link(page, paths[incoming], f'{incoming[0]}@{incoming[1]}') + "\n\n"
            if not found:
                yield "Unavailable or not selected; incoming records may be outside the captured closure.\n\n"
            yield "Attributed relationships only. Invalid support does not refute a claim; evidence prose is not interpreted as contradiction.\n\n"
    yield "## Exact outgoing relationships\n\n"
    if not envelope.record_references:
        yield "No recorded outgoing relationships.\n\n"
    for ordinal, ref in enumerate(envelope.record_references):
        target = (ref.record_id, ref.revision)
        fragment = "source-locations" if ref.relationship == "source_location" and type(decoded.get(target)) is Source else None
        yield f"Edge {ordinal}: " + _safe(ref.relationship) + " — " + _link(
            page, paths[target], f"{ref.record_id}@{ref.revision}", fragment) + "\n\n"
        yield "Declared target kind: " + _safe(ref.target_kind) + ".\n\n"
    yield "## Other captured incoming relationships\n\n"
    yield "These exact envelope relationships are navigation, not additional support. A generic support edge remains generic.\n\n"
    for incoming, other in envelopes.items():
        for ordinal, ref in enumerate(other.record_references):
            if (ref.record_id, ref.revision) == key:
                yield _link(page, paths[incoming], f'{incoming[0]}@{incoming[1]}') + f" edge {ordinal}: " + _safe(ref.relationship) + "\n\n"
    yield "## Provenance\n\n"
    yield from _values(envelope.provenance.to_dict())
    yield "Commit history metadata only; not research execution.\n\n"
    yield from _values(entry["commit"])
    yield "## Use\n\n"
    yield _link(page, "README.md", "Home") + "\n\n"
    parent = posixpath.dirname(posixpath.dirname(page))
    yield _link(page, (parent + "/" if parent else "") + "README.md", "Parent index") + "\n\n"
    yield "## Dependencies and limitations\n\n"
    for limitation in _LIMITATIONS:
        yield limitation + "\n\n"
    yield "## Editing route\n\n" + _EDITING + "\n"


def _root_body(document, paths, decoded, notices, mappings, envelopes, directories):
    """Lead with exact project/scope and link guarded dossier routes plus every child index."""
    pin = document["resolutions"][0]
    key = (pin["record_id"], pin["revision"])
    yield "# Private local reading snapshot\n\n"
    yield "Selected project: " + _safe(f"{key[0]}@{key[1]}") + ".\n\n"
    yield "Snapshot: " + document["snapshot_id"] + ".\n\n"
    yield "Commit watermark (local commit history only):\n\n"
    yield from _values(document["watermark"])
    yield "Partial explicit-root plus outgoing navigation closure. Manifest artifacts are expected_unverified; planning does not assert availability. Successful materialization verifies the complete copied generation; offline inspection checks current local contents.\n\n"
    yield "## Purpose and scope\n\n"
    yield from _values(document["scope"])
    yield "## Contents\n\n"
    yield _link("README.md", paths[key], "Selected project dossier") + "\n\n"
    yield "Requested root resolutions, in caller order:\n\n"
    for ordinal, resolution in enumerate(document["resolutions"]):
        target = (resolution["record_id"], resolution["revision"])
        yield f"Root {ordinal}: " + _link("README.md", paths[target], f"{target[0]}@{target[1]}") + "\n\n"
    project = decoded.get(key)
    if type(project) is ProjectSetup:
        for name, expected, product_kind in (("initial_corpus", CorpusManifest, None), ("current_corpus", CorpusManifest, None),
                                            ("context", None, None), ("brief", WorkProductManifest, "research_brief"),
                                            ("intake_report", WorkProductManifest, "intake_report")):
            ref = getattr(project, name)
            if ref is None:
                yield _safe(name) + ": recorded null; unavailable or not selected.\n\n"
                continue
            target = (ref.record_id, ref.revision)
            actual = decoded.get(target)
            valid = actual is not None and (expected is None or type(actual) is expected)
            if name == "context":
                from research_pipeline.scientific import ResearchContext
                valid = type(actual) is ResearchContext
            valid = valid and (product_kind is None or actual.product_kind == product_kind)
            label = name if valid and key not in notices and target not in notices else name + " recorded target; typed mapping projection unavailable"
            yield _link("README.md", paths[target], label) + "\n\n"
            if valid and key not in notices:
                for mapping in mappings.get(target, ()):
                    if mapping["details"].get("entry_file"):
                        yield _link("README.md", mapping["relative_path"], name + " authored entry file") + "\n\n"
    else:
        yield "Initial/current seed maps, selected context, brief and intake-report typed projections unavailable for opaque project. Exact envelope navigation remains available.\n\n"
    for kind, label in (("claim", "Claims"), ("justification", "Justifications"), ("evidence", "Evidence"),
                        ("research_context", "Contexts"), ("source", "Sources"), ("work_product_manifest", "Work products"),
                        ("review", "Reviews"), ("issue", "Issues"), ("decision", "Decision records")):
        yield label + ":\n\n"
        found = False
        for target, envelope in envelopes.items():
            if envelope.kind == kind:
                found = True
                yield _link("README.md", paths[target], f'{target[0]}@{target[1]}') + "\n\n"
        if not found:
            yield "Unavailable or not selected.\n\n"
    yield _link("README.md", "README.md", "Remaining decisions", "remaining-decisions") + "\n\n"
    yield _link("README.md", "manifest.json", "Canonical manifest") + "\n\n"
    for directory in sorted(directories):
        if directory and not posixpath.dirname(directory):
            yield _link("README.md", directory + "/README.md", directory + " index") + "\n\n"
    yield "## Current work\n\nOnly committed declarations are displayed. No execution or readiness is inferred.\n\n"
    yield "## Remaining decisions\n\n"
    if type(project) is ProjectSetup:
        yield "Setup presentation: " + _safe(setup_presentation(project)) + ". No authorization supplied.\n\n"
        yield from _values({"remaining": project.to_dict()["remaining"], "readiness": project.to_dict()["readiness"]})
    else:
        yield "Typed remaining requirements unavailable; consult the opaque project envelope.\n\n"
    yield "## Provenance\n\nSnapshot: " + document["snapshot_id"] + ".\n\n"
    yield "Exact revisions and their commit history are retained in record companions and manifest.json.\n\n"
    yield "## Use\n\nFollow ordinary relative links to generated companions and expected inert originals. No database, plugin or LLM is required to read a materialized complete generation.\n\n"
    yield "## Dependencies and limitations\n\n"
    for limitation in _LIMITATIONS:
        yield limitation + "\n\n"
    yield "## Editing route\n\n" + _EDITING + "\n"


def _index_body(directory, file_paths, directories, branches, paths, snapshot_id):
    """Provide seven-field folder navigation attributed to the exact detached snapshot."""
    page = (directory + "/" if directory else "") + "README.md"
    yield "# Reading index\n\n## Purpose and scope\n\nGenerated navigation within the captured outgoing closure.\n\n"
    yield "## Contents\n\n"
    for path in sorted(file_paths):
        if posixpath.dirname(path) == directory and path != page:
            yield _link(page, path, posixpath.basename(path)) + "\n\n"
    for child in sorted(directories):
        if child and posixpath.dirname(child) == directory:
            yield _link(page, child + "/README.md", posixpath.basename(child)) + "\n\n"
    yield "## Current work\n\nNo runtime progress is inferred from this index.\n\n"
    branch_token = directory.split("/")[-1]
    if directory.startswith("branches/") and branch_token in branches:
        yield "Captured exact branch revisions; generic payloads provide no inferred purpose, method, context differences or continuation policy.\n\n"
        for key in sorted(branches[branch_token]):
            yield _link(page, paths[key], f'{key[0]}@{key[1]}') + "\n\n"
    yield "## Provenance\n\nDerived solely from captured exact record metadata; manifest originals remain expected_unverified. Materialization verifies copied bytes; inspection checks current local contents.\n\n"
    yield "Snapshot: " + snapshot_id + ".\n\n"
    yield "Record/context/task attribution is available in linked exact companions; this index supplies no additional attribution.\n\n"
    yield "## Use\n\n"
    parent = posixpath.dirname(directory)
    yield _link(page, (parent + "/" if parent else "") + "README.md", "Parent index") + "\n\n"
    yield "## Dependencies and limitations\n\n" + _LIMITATIONS[0] + "\n\n" + _LIMITATIONS[7] + "\n\n"
    yield "## Editing route\n\n" + _EDITING + "\n"


def _branch_body(token, keys, paths, records):
    """Identify actual captured branch revisions without interpreting arbitrary branch payloads."""
    page = "branches/" + token + "/branch.md"
    yield "# Captured branch metadata\n\n"
    yield "Only actual exact branch records support this directory. Purpose, method, context differences and continuation policy are unavailable as typed runtime semantics.\n\n"
    for key in sorted(keys):
        yield _link(page, paths[key], f'{key[0]}@{key[1]}') + "\n\n"
        yield from _values(records[key]["classification"])
    yield _link(page, "branches/" + token + "/README.md", "Branch index") + "\n"


def plan_readable_snapshot(snapshot: DetachedSnapshot) -> ReadablePlan:
    """Pure version-1 projection of a validated detached closure, with no artifact/store/filesystem reads.

    All physical copy occurrences and generated descriptors consume limits. A
    failure produces no partial plan. Expected hashes never imply verified bytes.
    """
    return ReadablePlan(*_plan_inventory(snapshot))


def _plan_inventory(snapshot, report_entries=None):
    """Render the shared bounded inventory, retaining v1 bytes when no explicit reports are supplied.

    Return constructor arguments so v2 validation can compare canonical bytes
    without recursively constructing another self-validating ReadablePlan.
    """
    if type(snapshot) is not DetachedSnapshot:
        raise DomainValidationError("expected DetachedSnapshot")
    document = snapshot.to_dict()
    limits = SnapshotLimits(**document["limits"])
    if 2 * len(document["records"]) + 2 > limits.max_files:
        raise SnapshotLimitError("max_files cannot fit record companions and envelopes")
    records = {(r["record_id"], r["revision"]): r for r in document["records"]}
    envelopes = {key: RecordEnvelope.from_dict(json.loads(r["envelope_json"])) for key, r in records.items()}
    decoded, notices = _projection_map(records)
    paths, branches = _record_paths(records, decoded)
    mappings, copies = {}, []
    generated_paths = {"README.md", "manifest.json"}
    directories = {""}
    copy_paths = set()
    physical_bytes = 0

    def reserve_file(path, *, artifact=False):
        """Reserve a file and all useful parent READMEs before growing the retained inventory."""
        if path in copy_paths or (artifact and path in generated_paths):
            raise ViewPlanError("colliding logical artifact mappings")
        parents = set()
        parent = posixpath.dirname(path)
        while parent:
            parents.add(parent)
            parent = posixpath.dirname(parent)
        additions = {parent + "/README.md" for parent in parents} - generated_paths
        if not artifact and path not in generated_paths:
            additions.add(path)
        if len(generated_paths) + len(copy_paths) + len(additions) + int(artifact) > limits.max_files:
            raise SnapshotLimitError("max_files exceeded while reserving files and directory READMEs")
        generated_paths.update(additions)
        directories.update(parents)
        if artifact:
            copy_paths.add(path)

    for key, envelope in envelopes.items():
        bundle = posixpath.dirname(paths[key])
        reserve_file(paths[key])
        reserve_file(bundle + "/envelope.json")
        mappings[key] = []
        for mapping in _mappings(key, envelope, decoded.get(key), bundle, decoded):
            reserve_file(mapping["relative_path"], artifact=True)
            physical_bytes += mapping["size"]
            if mapping["size"] > limits.max_file_bytes or physical_bytes > limits.max_total_bytes:
                raise SnapshotLimitError("physical artifact copies exceed byte budgets")
            mappings[key].append(mapping)
            copies.append(ArtifactCopy(mapping["relative_path"], mapping["digest"], mapping["size"]))
    report_mappings = []
    if report_entries is not None:
        from research_pipeline.report_view import report_mappings as make_report_mappings, report_directory
        for item in report_entries:
            reserve_file(report_directory(item) + "/README.md")
            for mapping in make_report_mappings(item):
                reserve_file(mapping["relative_path"], artifact=True)
                report_mappings.append(mapping)
                copies.append(ArtifactCopy(mapping["relative_path"], mapping["digest"], mapping["size"]))
    for token in branches:
        reserve_file("branches/" + token + "/branch.md")
    all_paths = sorted(generated_paths | copy_paths)
    _inventory_paths(all_paths, sorted(directories), report_entries=report_entries)
    output = _Output(limits, sorted(generated_paths), copies)
    home = _root_body(document, paths, decoded, notices, mappings, envelopes, directories)
    if report_entries is not None:
        from research_pipeline.report_view import report_home, report_navigation
        from itertools import chain
        home = chain(report_home(report_entries), home)
    output.add("README.md", home, "home")
    for key, record in records.items():
        page = paths[key]
        output.add(page, _record_body(key, record, decoded.get(key), notices.get(key), paths, decoded,
                                     envelopes, mappings[key], document["snapshot_id"]), "record_companion")
        output.add(posixpath.dirname(page) + "/envelope.json", (record["envelope_json"],), "exact_envelope")
    record_pages = set(paths.values())
    if report_entries is not None:
        for item in report_entries:
            page = report_directory(item) + "/README.md"
            output.add(page, report_navigation(item, report_entries, paths, mappings), "report_navigation")
            record_pages.add(page)
    for directory in sorted(directories):
        page = (directory + "/" if directory else "") + "README.md"
        if page != "README.md" and page not in record_pages:
            output.add(page, _index_body(directory, all_paths, directories, branches, paths,
                                         document["snapshot_id"]), "index")
    for token, keys in sorted(branches.items()):
        output.add("branches/" + token + "/branch.md", _branch_body(token, keys, paths, records), "branch_metadata")
    files = [{"path": f.relative_path, "sha256": hashlib.sha256(f.data).hexdigest(), "size": len(f.data),
              "role": f.role, "mode": f.mode, "hash_kind": "generated"} for f in output.generated]
    files.extend({"path": c.relative_path, "sha256": c.digest, "size": c.size, "role": "artifact_copy",
                  "mode": c.mode, "hash_kind": "expected"} for c in copies)
    all_mappings = sorted([m for group in mappings.values() for m in group] + report_mappings, key=lambda item: item["relative_path"])
    manifest = {"format": "research_pipeline.readable_plan.v1", "snapshot_id": document["snapshot_id"],
        "schema": document["schema"], "watermark": document["watermark"], "selection": document["selection"],
        "resolutions": document["resolutions"], "scope": document["scope"], "limitations": list(_LIMITATIONS),
        "limits": document["limits"], "metadata_fetched_bytes": document["metadata_fetched_bytes"], "records": [{**entry, "page_path": paths[key],
            "relationships": envelopes[key].to_dict()["record_references"],
            "projection_limitation": notices.get(key)} for key, entry in records.items()],
        "artifacts": [{**a, "mappings": [m for m in all_mappings if m["digest"] == a["digest"]]}
                      for a in document["artifacts"]], "mappings": all_mappings,
        "directories": [{"path": d, "mode": 0o500} for d in sorted(directories)],
        "files": sorted(files, key=lambda item: item["path"]),
        "descriptor": {"path": "manifest.json", "mode": 0o400, "self_excluded": True}}
    if report_entries is not None:
        manifest.update(format="research_pipeline.readable_plan.v2", reports=report_entries,
                        selected_report_operation_id=report_entries[-1]["result"]["operation_id"])
    # The descriptor excludes itself. Hash the canonical body without plan_id;
    # bound both that body and the larger final descriptor before returning.
    digest = hashlib.sha256()
    size = 0
    for chunk in _json_chunks(manifest):
        size += len(chunk)
        if size > limits.max_file_bytes or output.total + size > limits.max_total_bytes:
            raise SnapshotLimitError("manifest byte budget exceeded")
        digest.update(chunk.encode("ascii"))
    plan_id = digest.hexdigest()
    manifest["plan_id"] = plan_id
    descriptor = output.add("manifest.json", _json_chunks(manifest), "manifest")
    return (document["snapshot_id"], plan_id,
                        tuple(sorted(output.generated, key=lambda item: item.relative_path)),
                        tuple(sorted(copies, key=lambda item: item.relative_path)),
                        tuple(DirectoryEntry(d) for d in sorted(directories)), descriptor.data)


def _inventory_paths(files, directories, *, report_entries=None):
    """Check portable paths and useful directory closure; report paths require explicit v2 bindings."""
    try:
        _validate_paths(files)
        if len(set(directories)) != len(directories):
            raise ViewPlanError("duplicate directories")
        allowed = {"brief", "projects", "contexts", "seeds", "documents", "literature", "claims", "reviews",
                   "navigation", "issues", "justifications", "evidence", "records", "work-products", "decisions",
                   "branches", "revisions", "notes", "derivations", "calculations", "notebooks", "figures",
                   "reports", "intake", "reading", "end-of-run", "runs", "originals"}
        from research_pipeline.domain import _KINDS
        allowed |= _KINDS
        expected = {""}
        report_paths = set()
        if report_entries is not None:
            from research_pipeline.report_view import report_directory
            for item in report_entries:
                base = report_directory(item)
                report_paths.update(base + "/" + name for name in ("README.md", "report.md", "source.json", "continuation.json"))
                report_paths.add(posixpath.dirname(base) + "/README.md")
        for path in files:
            if path in report_paths:
                parent = posixpath.dirname(path)
                while parent:
                    expected.add(parent)
                    parent = posixpath.dirname(parent)
                continue
            if len(path.encode("utf-8")) > 1024 or not path.isascii():
                raise ViewPlanError("generated path exceeds portable relative ceiling")
            components = path.split("/")
            if any(len(c.encode("ascii")) > 240 for c in components):
                raise ViewPlanError("generated component exceeds 240 bytes")
            if len(components) == 1:
                if path not in ("README.md", "manifest.json"):
                    raise ViewPlanError("unreserved root file")
            elif components[0] not in {"brief", "literature", "claims", "reviews", "navigation", "decisions", "branches", "reports"}:
                raise ViewPlanError("unexpected generated prefix")
            for component in components[:-1]:
                if component not in allowed and re.fullmatch(r"r-[0-9a-f]{64}|[1-9][0-9]*", component) is None:
                    raise ViewPlanError("unexpected generated directory component")
            filename = components[-1]
            if filename not in ("README.md", "envelope.json", "branch.md", "manifest.json"):
                if (len(components) < 3 or components[-2] != "originals"
                        or re.fullmatch(r"a-[0-9a-f]{64}\.(md|txt|tex|pdf|png|jpg|csv|json|ipynb|bin)", filename) is None):
                    raise ViewPlanError("unexpected generated filename")
            if filename == "manifest.json" and path != filename:
                raise ViewPlanError("manifest descriptor is root-only")
            parent = posixpath.dirname(path)
            while parent:
                expected.add(parent)
                parent = posixpath.dirname(parent)
        if set(directories) != expected:
            raise ViewPlanError("directories differ from useful inventory closure")
        for directory in expected:
            if (directory + "/" if directory else "") + "README.md" not in files:
                raise ViewPlanError("missing directory README")
    except DomainValidationError as error:
        raise ViewPlanError(str(error)) from error


def _markdown_navigation(data):
    """Independently inspect rendered Markdown, rejecting unrecognized link syntax and duplicate headings."""
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        raise ViewPlanError("generated Markdown is not UTF-8") from error
    headings, links = set(), []
    frontmatter = False
    properties = set()
    for index, line in enumerate(text.splitlines()):
        if index == 0 and line == "---":
            frontmatter = True
            continue
        if frontmatter:
            if line == "---":
                frontmatter = False
            elif re.fullmatch(r'(record_id|revision|kind|snapshot_id|context_id|context_revision|branch_id|branch_revision): "[^"\\]*"', line) is None:
                raise ViewPlanError("unexpected generated YAML properties")
            else:
                name = line.split(":", 1)[0]
                if name in properties:
                    raise ViewPlanError("duplicate generated property")
                properties.add(name)
            continue
        if line.startswith("    "):
            continue  # Supplied values are inert code; their authored links are not generated navigation.
        if line.startswith("#"):
            match = re.fullmatch(r"#{1,6} ([A-Za-z][A-Za-z0-9 /-]*)", line)
            if match is None:
                raise ViewPlanError("unexpected generated heading")
            fragment = match[1].lower().replace(" ", "-").replace("/", "")
            if fragment in headings:
                raise ViewPlanError("duplicate generated heading fragment")
            headings.add(fragment)
        matches = list(re.finditer(r"\[([^\[\]\n]*)\]\(([^()\s]+)\)", line))
        for match in matches:
            links.append(match[2])
        residue = re.sub(r"\[([^\[\]\n]*)\]\(([^()\s]+)\)", "", line)
        if (any(char in residue for char in "[]<>`\\") or "![" in line
                or re.search(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://", residue)):
            raise ViewPlanError("unexpected generated Markdown link or HTML syntax")
    if frontmatter:
        raise ViewPlanError("unclosed generated properties")
    return headings, links


def _snapshot_from_manifest(manifest):
    """Extract retained capture fields, stripping only defined presentation fields.

    Unknown nested fields survive extraction so DetachedSnapshot's strict schema
    rejects them. The top-level manifest schema is exact as well.
    """
    required = {"format", "snapshot_id", "plan_id", "schema", "watermark", "selection", "resolutions", "scope",
                "limitations", "limits", "metadata_fetched_bytes", "records", "artifacts", "mappings", "directories", "files", "descriptor"}
    if type(manifest) is dict and manifest.get("format") == "research_pipeline.readable_plan.v2":
        required |= {"selected_report_operation_id", "reports"}
    if type(manifest) is not dict or set(manifest) != required or manifest["format"] not in ("research_pipeline.readable_plan.v1", "research_pipeline.readable_plan.v2"):
        raise ViewPlanError("unsupported manifest structure")
    names = ("snapshot_id", "schema", "watermark", "selection", "resolutions", "scope", "limits", "metadata_fetched_bytes")
    document = {name: manifest[name] for name in names}
    document["format"] = "research_pipeline.snapshot.v1"
    document["records"] = [{k: v for k, v in record.items()
                            if k not in ("page_path", "relationships", "projection_limitation")}
                           for record in manifest["records"]]
    document["artifacts"] = [{k: v for k, v in artifact.items() if k != "mappings"}
                             for artifact in manifest["artifacts"]]
    return document


def readable_plan_from_manifest(data: bytes, *, limits: SnapshotLimits) -> ReadablePlan:
    """Reconstruct the one deterministic plan from a bounded untrusted descriptor.

    Every embedded allowance must fit the corresponding caller allowance before
    reconstructing or rendering. This conservative rule prevents the descriptor
    from selecting its own processing budgets. Exact canonical bytes, including
    the self-excluded descriptor identity, must match the existing planner.
    """
    if type(data) is not bytes or type(limits) is not SnapshotLimits:
        raise DomainValidationError("expected immutable manifest bytes and SnapshotLimits")
    limits = SnapshotLimits(**limits.to_dict())
    if len(data) > min(limits.max_file_bytes, limits.max_total_bytes):
        raise SnapshotLimitError("manifest exceeds caller byte allowance")
    try:
        manifest = _manifest_json(data)
        embedded = SnapshotLimits(**manifest["limits"])
        allowances = limits.to_dict()
        if any(value > allowances[name] for name, value in embedded.to_dict().items()):
            raise SnapshotLimitError("embedded allowance exceeds caller inspection allowance")
        document = _snapshot_from_manifest(manifest)
        if manifest["format"] == "research_pipeline.readable_plan.v2":
            from research_pipeline.report_view import plan_report_snapshot
            plan = plan_report_snapshot(DetachedSnapshot(document), manifest["reports"], limits=limits)
        else:
            plan = plan_readable_snapshot(DetachedSnapshot(document))
        if plan.manifest_bytes != data:
            raise ViewPlanError("manifest differs from deterministic canonical plan")
        return plan
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, (ViewPlanError, SnapshotLimitError, DomainValidationError)):
            raise
        raise ViewPlanError(f"invalid manifest: {str(error)[:240]}") from error


def verify_plan_links(plan: ReadablePlan) -> None:
    """Validate immutable plan values, full inventory/manifest and every rendered generated link.

    Parent traversal is allowed only after normalization stays inside the complete
    file inventory. Fragments must uniquely identify generated Markdown headings;
    authored links and artifact fragments are deliberately outside this guarantee.
    Manifest wrappers permit depth 69 for v1 and 72 for v2; nested codecs retain
    their own limits, including depth 64 for stored provenance. Invalid plans raise ViewPlanError.
    """
    try:
        if type(plan) is not ReadablePlan:
            raise ViewPlanError("expected ReadablePlan")
        if type(plan.manifest_bytes) is not bytes:
            raise ViewPlanError("manifest must be immutable bytes")
        for entries, expected in ((plan.generated_files, GeneratedFile), (plan.artifact_copies, ArtifactCopy),
                                  (plan.directories, DirectoryEntry)):
            if type(entries) is not tuple or any(type(entry) is not expected for entry in entries):
                raise ViewPlanError("immutable inventory tuples required")
            for entry in entries:
                entry.__post_init__()
        ArtifactReference(plan.snapshot_id, 0)
        ArtifactReference(plan.plan_id, 0)
        dispatched = _manifest_json(plan.manifest_bytes)
        if dispatched.get("format") == "research_pipeline.readable_plan.v2":
            from research_pipeline.report_view import verify_report_plan
            verify_report_plan(plan, dispatched)
            return
        for entries in (plan.generated_files, plan.artifact_copies):
            if [entry.relative_path for entry in entries] != sorted(entry.relative_path for entry in entries):
                raise ViewPlanError("file inventory must be sorted")
        roles = {"home", "record_companion", "exact_envelope", "index", "branch_metadata", "manifest"}
        for file in plan.generated_files:
            if (file.role not in roles
                    or posixpath.basename(file.relative_path) not in ("README.md", "envelope.json", "branch.md", "manifest.json")):
                raise ViewPlanError("unexpected generated file role or descriptor")
        if type(plan.manifest_bytes) is not bytes:
            raise ViewPlanError("manifest must be immutable bytes")
        # Stored provenance allows depth 64. Its deepest v1 placement adds five
        # containers: manifest object, artifacts array, artifact object, mappings
        # array and mapping object. Top-level mappings add only three containers.
        manifest_v1_maximum_depth = 69
        manifest = _strict_json(plan.manifest_bytes.decode("ascii"),
                                maximum_depth=manifest_v1_maximum_depth)
        snapshot_document = _snapshot_from_manifest(manifest)
        ArtifactReference(plan.snapshot_id, 0)
        ArtifactReference(plan.plan_id, 0)
        if manifest["snapshot_id"] != plan.snapshot_id or manifest["plan_id"] != plan.plan_id:
            raise ViewPlanError("manifest identity disagreement")
        body = {key: value for key, value in manifest.items() if key != "plan_id"}
        if hashlib.sha256(_canonical(body).encode("ascii")).hexdigest() != plan.plan_id:
            raise ViewPlanError("plan identity mismatch")
        generated = {f.relative_path: f for f in plan.generated_files}
        copies = {f.relative_path: f for f in plan.artifact_copies}
        if len(generated) != len(plan.generated_files) or len(copies) != len(plan.artifact_copies) or generated.keys() & copies.keys():
            raise ViewPlanError("duplicate physical files")
        all_files = sorted(generated.keys() | copies.keys())
        directory_paths = [d.relative_path for d in plan.directories]
        _inventory_paths(all_files, directory_paths)
        if directory_paths != sorted(directory_paths):
            raise ViewPlanError("directory inventory not sorted")
        if ("manifest.json" not in generated or generated["manifest.json"].data != plan.manifest_bytes
                or generated["manifest.json"].role != "manifest"):
            raise ViewPlanError("missing/mismatched descriptor")
        expected_files = [{"path": f.relative_path, "sha256": hashlib.sha256(f.data).hexdigest(), "size": len(f.data),
            "role": f.role, "mode": f.mode, "hash_kind": "generated"} for f in plan.generated_files if f.relative_path != "manifest.json"]
        expected_files.extend({"path": c.relative_path, "sha256": c.digest, "size": c.size, "role": "artifact_copy",
                               "mode": c.mode, "hash_kind": "expected"} for c in plan.artifact_copies)
        if _canonical(manifest["files"]) != _canonical(sorted(expected_files, key=lambda item: item["path"])):
            raise ViewPlanError("manifest file inventory disagrees")
        if _canonical(manifest["directories"]) != _canonical([{"path": d.relative_path, "mode": d.mode} for d in plan.directories]):
            raise ViewPlanError("manifest directories disagree")
        if _canonical(manifest["descriptor"]) != _canonical({"path": "manifest.json", "mode": 0o400, "self_excluded": True}):
            raise ViewPlanError("invalid self-excluded descriptor")
        for record in manifest["records"]:
            page = record["page_path"]
            raw_path = posixpath.dirname(page) + "/envelope.json"
            if (page not in generated or raw_path not in generated
                    or generated[raw_path].data != record["envelope_json"].encode("ascii")
                    or _canonical(record["relationships"]) != _canonical(json.loads(record["envelope_json"])["record_references"])):
                raise ViewPlanError("record companion or exact envelope disagreement")
        for artifact in manifest["artifacts"]:
            if _canonical(artifact["mappings"]) != _canonical([m for m in manifest["mappings"] if m["digest"] == artifact["digest"]]):
                raise ViewPlanError("artifact inclusion mappings disagree")
        DetachedSnapshot(snapshot_document)
        record_map = {(r["record_id"], r["revision"]): r for r in snapshot_document["records"]}
        decoded, notices = _projection_map(record_map)
        page_paths, branches = _record_paths(record_map, decoded)
        expected_mappings = []
        for record in manifest["records"]:
            key = (record["record_id"], record["revision"])
            if record["page_path"] != page_paths[key] or record["projection_limitation"] != notices.get(key):
                raise ViewPlanError("record projection metadata differs from fixed policy")
            envelope = RecordEnvelope.from_dict(json.loads(record["envelope_json"]))
            prefix = "".join(_properties(envelope, decoded.get(key), plan.snapshot_id)).encode("ascii")
            if not generated[page_paths[key]].data.startswith(prefix):
                raise ViewPlanError("record properties disagree with exact identities")
            expected_mappings.extend(_mappings(key, envelope, decoded.get(key), posixpath.dirname(page_paths[key]), decoded))
        if _canonical(manifest["mappings"]) != _canonical(sorted(expected_mappings, key=lambda item: item["relative_path"])):
            raise ViewPlanError("logical mapping metadata differs from captured records")
        required_paths = {"README.md", "manifest.json", *page_paths.values()}
        required_paths.update(posixpath.dirname(page) + "/envelope.json" for page in page_paths.values())
        required_paths.update("branches/" + token + "/branch.md" for token in branches)
        required_paths.update(mapping["relative_path"] for mapping in expected_mappings)
        for path in tuple(required_paths):
            parent = posixpath.dirname(path)
            while parent:
                required_paths.add(parent + "/README.md")
                parent = posixpath.dirname(parent)
        if required_paths != set(all_files):
            raise ViewPlanError("inventory differs from useful fixed-policy files")
        expected_roles = {page: "record_companion" for page in page_paths.values()}
        expected_roles.update({posixpath.dirname(page) + "/envelope.json": "exact_envelope"
                               for page in page_paths.values()})
        expected_roles.update({"branches/" + token + "/branch.md": "branch_metadata" for token in branches})
        expected_roles.update({"README.md": "home", "manifest.json": "manifest"})
        for path, file in generated.items():
            if file.role != expected_roles.get(path, "index"):
                raise ViewPlanError("generated file role differs from fixed inventory policy")
        if manifest["limitations"] != list(_LIMITATIONS):
            raise ViewPlanError("missing fixed plan limitations")
        mapped = {}
        for mapping in manifest["mappings"]:
            path = mapping["relative_path"]
            if path in mapped or path not in copies or mapping["availability"] != "expected_unverified" or mapping["hash_kind"] != "expected":
                raise ViewPlanError("invalid logical-to-physical mapping")
            mapped[path] = (mapping["digest"], mapping["size"])
        if mapped != {c.relative_path: (c.digest, c.size) for c in plan.artifact_copies}:
            raise ViewPlanError("copy expectations disagree with mappings")
        limits = SnapshotLimits(**manifest["limits"])
        sizes = [len(f.data) for f in plan.generated_files] + [c.size for c in plan.artifact_copies]
        if len(sizes) > limits.max_files or max(sizes) > limits.max_file_bytes or sum(sizes) > limits.max_total_bytes:
            raise SnapshotLimitError("plan exceeds physical inventory budgets")
        markdown = {p: _markdown_navigation(f.data) for p, f in generated.items() if p.endswith(".md")}
        for page, (headings, links) in markdown.items():
            if posixpath.basename(page) == "README.md":
                if not {h.lower().replace(" ", "-") for h in _HEADINGS} <= headings:
                    raise ViewPlanError("README missing one of seven fixed fields")
            for link in links:
                if (link.startswith(("/", "\\")) or ":" in link or "\\" in link or "%" in link
                        or link.count("#") > 1 or "?" in link):
                    raise ViewPlanError("unsafe generated link destination")
                path, separator, fragment = link.partition("#")
                target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path)) if path else page
                if target.startswith("../") or target == ".." or target not in all_files:
                    raise ViewPlanError(f"generated link escapes or misses inventory: {page} -> {link}")
                if separator and (target not in markdown or not fragment or fragment not in markdown[target][0]):
                    raise ViewPlanError("generated link fragment missing or not generated Markdown")
    except (AttributeError, DomainValidationError, KeyError, TypeError, UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, (ViewPlanError, SnapshotLimitError)):
            raise
        raise ViewPlanError(f"invalid plan: {str(error)[:240]}") from error


def _manifest_json(data):
    """Dispatch strict manifest depth without enlarging the historical v1 decoder.

    V2 adds a reports array and entry wrapper; each report and snapshot codec
    independently enforces its original nested limits after this outer gate.
    """
    value = _strict_json(data.decode("ascii"), maximum_depth=72)
    if value.get("format") != "research_pipeline.readable_plan.v2":
        return _strict_json(data.decode("ascii"), maximum_depth=69)
    return value
