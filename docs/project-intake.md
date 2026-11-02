# Versioned project setup and attributed intake

`research_pipeline.project` records immutable `ProjectSetup` snapshots through
`RecordStore.submit_typed`. Import values from this submodule directly. The
existing schema-2 `project` envelope owns identity and revision; content never
duplicates them. Both canonical states are always null. There is no new submission
service, proposal wrapper, CLI, storage path or schema.

Researcher objective and intent remain distinct from a proposed scientific brief.
All attribution, including authors and procedural judgments, is unauthenticated.
A committed dossier preserves unknowns, repeated statements and contradictions;
it does not interpret mathematics, endorse imported reviews or authenticate actors.
Scientific text, imported configuration, actor names and generic decisions grant
no operating authority. Exact Source pins retain restrictions without overrides.

## Required constructors and wire contract

All arguments below are required in this order, including nulls and empty arrays.
`D` denotes existing `source.DeclaredText(value, unknown_reason)`, `R` denotes
`domain.RecordReference(record_id, revision, relationship, target_kind)`, and
`T[X]` denotes an ordered tuple whose constructor also accepts an ordinary list.
These are documentation notation, not runtime aliases. DeclaredText requires
exactly one known nonblank value or an explained unknown reason. Constructors
freeze and detach nested values. Wire arrays are ordinary lists.

```text
AttributedText(text: D, attribution: D)
IntakeLink(reference: R, relation: str)
IntakeDeclaration(declaration_id: str, category: str, text: str, origin: str,
                  origin_detail: D, attribution: D, locations: T[CorpusLocation],
                  links: T[IntakeLink], limitations: T[str])
IntakeRequirement(requirement_id: str, kind: str, stage: str, description: AttributedText)
ProceduralJudgment(status: str, explanation: str, attribution: D)
ReadinessProposal(status: str, reasons: T[str], attribution: D,
                  evidence_declarations: T[str], substantive_relevance: ProceduralJudgment,
                  assignment_usability: ProceduralJudgment)
ProjectSetup(title: AttributedText, objective: AttributedText, researcher_intent: AttributedText,
             initial_corpus: R, current_corpus: R, context: R | None, brief: R | None,
             intake_report: R | None, inspection: CorpusInspection,
             declarations: T[IntakeDeclaration], remaining: T[IntakeRequirement],
             readiness: ReadinessProposal, limitations: T[str], supersedes: R | None,
             revision_reason: str, revision_attribution: D)
```

Every class exposes strict `to_dict()` and `from_dict(dict)`. Nested wire fields
are exactly the constructor fields. Only ProjectSetup additionally has
`format="research_pipeline.project_content"`, ordinary integer `version=1` and
`kind="project"`. No extension dictionaries, omitted defaults, header constructor
arguments or persisted presentation field exist. Reused [CorpusLocation and
CorpusInspection](corpus.md#required-constructors-and-wire-fields) retain their
original contracts, including required uninspected remainder and nonempty
locations exactly when coverage is `selected_material`.

| Field | Exact vocabulary / rule |
| --- | --- |
| declaration.category | `definition`, `assumption`, `convention`, `existing_work`, `proposed_question`, `proposed_baseline`, `contradiction`, `gap`, `unprocessed_remainder`, `brief_choice` |
| declaration.origin | `supplied_observation`, `new_proposal`, `unknown_origin` |
| declaration.origin_detail | Known detail for supplied observations/new proposals; unknown_reason for unknown_origin. Known locations may accompany uncertain origins. A textual origin alone is not inspected-seed evidence. |
| requirement.kind | `material`, `prerequisite`, `policy_proposal`, `resource_proposal`; all are inert outstanding requirements |
| requirement.stage | `intake`, `research_admission` |
| judgment.status | `not_assessed`, `affirmed`, `not_affirmed`; all require explanation; affirmed requires known attribution |
| readiness.status | `not_assessed`, `insufficient_materials`, `incomplete_intake`, `proposed_ready` |
| readiness.reasons | At least one nonblank reason for every status |
| readiness.evidence_declarations | Unique declaration IDs resolving within this snapshot; nonempty for proposed_ready |

| Bound | Contract |
| --- | --- |
| Project narrative text, including relation/explanations/revision_reason | Nonblank scalar Unicode, at most 16,384 characters; preserve whitespace and spelling |
| Every collection | At most 1,024 members, checked before reconstructing members |
| Inspection and declaration locations combined | At most 4,096 occurrences |
| Declaration links combined | At most 4,096 occurrences |
| Identifiers | Existing 1–128 ASCII letter/digit/underscore/hyphen rule, starting with letter/digit |
| Revisions | Ordinary integer 1 through `2**63-1`; no bool/float/string coercion |

Declaration IDs and requirement IDs are separately unique. Exact locations cannot
repeat within an individual location collection; repeats across declarations and
roles remain distinct. Links within one declaration cannot repeat an exact target
identity/revision, even under different roles. Distinct revisions and occurrences
in separate declarations remain distinct. Narrative repetitions are retained.
Every declaration location must occur exactly in the project's inspection subset.

## Readiness and truthful presentation

`setup_presentation(content: ProjectSetup) -> str` is pure and defensively
revalidates the entire value. `insufficient_materials` maps to `awaiting_materials`;
`not_assessed` and `incomplete_intake` map to `setup_incomplete`; `proposed_ready`
maps to `awaiting_authorization`. These strings are presentations, never canonical
operational states or authorization decisions. Empty setup may explicitly propose
insufficient materials.

Proposed ready requires known title, objective and researcher-intent text; an
attributed selected-material inspection with nonempty locations; context, brief
and intake report; affirmed substantive-relevance and assignment-usability
judgments with explanations; known readiness attribution; nonempty evidence IDs
including a declaration with an inspected location; and no outstanding intake
requirement. Future research-admission requirements, unknown origins,
contradictions and scientific gaps may remain. No requirement to invent every
category or inspect everything exists. A short substantive supplied note can
support an attributed proposal; length, title, path, classification, hash and count
never infer relevance or usability.

Project inspection covers its explicit subset and remainder. It neither copies
nor upgrades Source reading or corpus-entry inspection observations. Actual
admission must later enforce authorized operating policy, permissions, budgets and
scientific prerequisites. Full interpretation/acquisition, exposure enforcement,
task/run lifecycle, providers/tools and scientific evaluation
remain subsequent work.

## Exact target and history semantics

| Project field | Relationship → target_kind |
| --- | --- |
| initial_corpus | `initial_corpus` → corpus_manifest, always revision 1 |
| current_corpus | `current_corpus` → corpus_manifest, same corpus identity |
| context | `context` → research_context |
| brief | `research_brief` → work_product_manifest; requires context |
| intake_report | `intake_report` → work_product_manifest; may exist without context/brief |
| supersedes | `supersedes` → project |
| location.source | `source_location` → source |
| IntakeLink.reference | `intake_context` → research_context; `intake_claim` → claim; `intake_justification` → justification; `intake_evidence` → evidence; `intake_review` → review; `intake_issue` → issue; `intake_work_product` → work_product_manifest |

All these targets must be exact supported typed values. Optional scientific links
retain their explanatory relation and need not share the project's scientific
context. No project, policy, decision or execution link is added to IntakeLink.

Every inspection and declaration location must name a captured entry in the exact
current corpus, use that entry's exact Source identity/revision and resolve to a
Source location whose non-null artifact_id names an original selected by that same
entry. Corpus validation first establishes the selected original's path, digest,
size and supplied locator against Source.originals. Derived extraction outputs,
unanchored upstream locations, missing locations, reference-only/unavailable/
unresolved entries and originals selected only by another entry cannot qualify.
Every occurrence is checked, including repeated Source targets. Metadata-only
inventory cannot supply inspected original evidence. These are metadata-coherence
checks, not permission to inspect or proof of current transitive byte availability.

The work-product version-1 vocabulary adds exactly `research_brief` and
`intake_report`, retaining every old label/wire representation. Incoming brief/report
roles require those respective product kinds independently of titles or paths.
Nonempty authors/files record an authored bundle without authenticating authorship.
Document context must match the project's exact context ignoring incoming role
labels. A contextless project's intake report must also have null context.

For each brief/report, let C be distinct exact initial/current corpus targets,
I the distinct Sources in project.inspection.locations, and S the distinct Sources
of captured entries in the current corpus. Its corpus_manifest build_dependencies
must equal C as a set. Its linked_sources set must include I and be a subset of S.
Additional Sources in S may describe uninspected background or remainder, without
counting as inspected. Source build_dependencies must belong to S and cannot
substitute for linked_source. Any research_context build_dependency must equal the
non-null project context. Other build dependencies retain their shallow meaning;
arbitrary project/decision dependencies are not traversed. These conditions apply
to incomplete documents too. Corpus advances require correspondingly pinned
new document revisions before a new snapshot can claim proposed_ready.

Revision 1 has null supersedes; revision n > 1 requires this project's exact n−1
predecessor. Complete supported project history is checked in ascending order to
revision 1, including snapshots originally stored through generic submit. The
initial pin and corpus identity cannot change; current selection cannot regress.
Unchanged selections and forward jumps are allowed when full corpus history is
coherent. Every historical snapshot uses its own corpus and document pins. A good
latest snapshot cannot hide invalid generic-admitted history or reset its baseline.

Corrections append a full project snapshot with reason/attribution and predecessor,
explicitly replacing inaccurate declarations or document pins. To undo an erroneous
corpus selection, append a corrective corpus revision using existing corpus
correction/removal/replacement rules, then select that newer revision. A different
baseline/corpus identity needs a new project identity. Old pins never change.

## Complete semantic traversal and ordered projections

The following tables are the complete ten-kind contract. Shallow roles check only
existence and declared kind, including generic, unsupported or malformed typed-looking
projects. They do not inspect target payloads, attachments or outgoing edges.
Independently submitted typed batch members are always decoded. An incoming shallow
occurrence never exempts a separate constrained occurrence, and cached/processed
targets never bypass incoming role checks.

| Content | Constrained roles → target kinds | Shallow roles → target kinds |
| --- | --- | --- |
| ResearchContext | None | None |
| Claim | context → research_context | None |
| Justification | context → research_context; premise/conclusion → claim; evidence → evidence | None |
| Evidence | context → research_context; target_claim → claim | input_record → any record kind, nullable declared kind retains existing rule |
| Review | candidate_claim → claim; target_context → research_context; reported_evidence → evidence; assessed_route → justification | context_manifest → work_product_manifest; authorization_policy → decision; reported_tool_execution → tool_execution |
| Issue | supporting_evidence → evidence | affected_record → any explicitly declared record kind |
| WorkProductManifest | context → research_context; linked_claim → claim; supersedes → work_product_manifest | task → task_specification; branch → branch; run → run; linked_source → source; build_dependency → any explicitly declared record kind |
| Source | supersedes → source; reading_report → work_product_manifest with product_kind reading_report; reported_evidence → evidence | related_source → source; reported_tool_execution → tool_execution |
| CorpusManifest | supersedes → corpus_manifest; inventory_source/source_location → source; complete corpus history and original/location checks | None |
| ProjectSetup | All roles in the preceding project-reference table; complete project history, per-location and incoming brief/report checks | None |

Work-product linked_source/build_dependency roles remain globally shallow; the
additional dossier coherence conditions apply only when a project uses a document
as brief/report. Source reading_report continues to reject both new labels.
Review route-conclusion checks and historical scientific states remain unchanged.

| Content | Ordered record-reference projection | Artifact-reference projection |
| --- | --- | --- |
| ResearchContext | Empty | Empty |
| Claim | context | Empty |
| Justification | context, premises, conclusions, evidence | Empty |
| Evidence | context, target_claims, input_records | artifacts, then input_artifacts; no cross-role deduplication |
| Review | candidate_claim, target_context, context_manifest, authorization_policy, reported_checks, route justifications | artifacts |
| Issue | affected_records, supporting_evidence | artifacts |
| WorkProductManifest | task, branch, context, run, linked_claims, linked_sources, supersedes, build_dependencies | First occurrence of each digest scanning files |
| Source | supersedes, related_sources, reading.report, reading.checks, then each statement's checks | First digest scanning originals then extraction outputs |
| CorpusManifest | supersedes; captured entry sources; entry inspection locations; observation locations; each link's source then target location | First digest scanning selected originals in entry order |
| ProjectSetup | supersedes; initial_corpus; current_corpus; context; brief; intake_report; inspection location sources; then for each declaration its location sources followed by its IntakeLink references | Exactly empty |

Null optional references are omitted. All other record occurrences retain caller
order without deduplication, including initial/current pins to the same target and
locations repeated across roles. Both envelope directions reject missing, extra,
reordered, relabeled or substituted projections rather than repairing them.

## Pure codecs, admission and errors

| Module-local operation | Result |
| --- | --- |
| decode_content(dict) | ProjectSetup |
| dumps_content(ProjectSetup) | Sorted-key compact ASCII-escaped JSON str; array order preserved |
| loads_content(str or bytes) | ProjectSetup from strict UTF-8 JSON |
| encode_envelope(record_id, revision, content, provenance) | Detached RecordEnvelope with project kind, null states and exact projections |
| decode_envelope(RecordEnvelope) | ProjectSetup after exact local projection/history checks |
| setup_presentation(ProjectSetup) | Revalidated presentation string; no effects or authorization |

Missing format raises `scientific.NotTypedContentError`. Other malformed content,
headers, roles, bounds, local readiness or envelope mismatches raise
`DomainValidationError` with field/index context and chained causes where
appropriate. Duplicate JSON keys, invalid UTF-8, nonscalar Unicode, nonfinite or
overflow values, trailing data, cycles, excessive nesting, coercion, subclasses,
serialization lookalikes and forged frozen state fail. Supplied text and locators
are inert and are never opened or normalized by these pure operations.

`get_typed_revision` returns `(RecordEnvelope, ScientificContent | AssessmentContent |
WorkProductManifest | Source | CorpusManifest | ProjectSetup)`. Local decoding
precedes original-ID reconciliation; target/history lookups follow it. New requests
retain schema-kind checks, CAS/batch/direct-artifact verification, cached exact
metadata closure, then existing metadata insertion in the owned transaction.
Proposed batch targets resolve before exact stored metadata. Reachable corpus
histories are validated before project dossiers. No public reads or transitive
artifact rereads occur in closure. Project has no direct artifacts; newly submitted
corpus/document records retain their established direct verification.

Target/history failures become `ReferenceResolutionError` identifying project,
revision, role and target, with entry/location context where relevant. Existing
artifact, schema, CAS and submission-conflict errors remain distinct. Rejection
leaves all application tables, heads, requests, receipts and events unchanged;
already published orphan bytes may remain. Historical project reads check local
content/projection only, not prior admission or availability of transitive bytes.

Generic submit remains available without typed certification. Exact original-ID
retries return the original receipt/event before target/artifact checks even after
later revisions or artifact damage, including locally valid generic-admitted
requests. Changed content, attribution or ordering under the same ID conflicts.
Saved proposals remain ordinary Submission.to_dict/from_dict requests. Schema 1
requires explicit existing v1→v2 restore migration before new project admission;
healthy schema-2 backups/exact restore preserve all history, bytes and receipts.

ProjectSetup adds no path or attachment fields. Source locations use existing
original mappings and portable logical paths. Document files retain existing
portable path, alias and collision rules without an extension whitelist. The
specification's readable-view areas include `reports/intake/` and `brief/`. These
intake contracts store bundles without inferring roles from paths. The separate [readable snapshot API](readable-snapshots.md) captures, plans, materializes
and inspects private reading generations using the recorded roles.

## Runnable local example

From the candidate root, run the exact block with:

```sh
PYTHONPATH=implementation/src python3 -B -c 'from pathlib import Path; text = Path("docs/project-intake.md").read_text(); section = text.split("## Runnable local example\n", 1)[1]; exec(section.split("```python\n", 1)[1].split("```", 1)[0])'
```

This self-contained synthetic example explicitly creates private input directories
outside the candidate source root and gives synthetic inputs explicit owner-only
file permissions before capture. It executes no scientific/software artifacts.
The test suite extracts this Python block verbatim into a fresh interpreter.

```python
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline.source import (
    DeclaredText, Source, SourceDeclaration, SourceRestrictions, SourceProvenance,
    SourceReading, SourceLocation, decode_envelope as decode_source,
)
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.corpus import (
    CorpusManifest, CorpusEntry, CorpusOriginal, CorpusEntryChange, CorpusInspection,
    CorpusLocation, encode_envelope as corpus_envelope,
)
from research_pipeline.scientific import ResearchContext, encode_envelope as context_envelope
from research_pipeline.work_product import WorkProductManifest, WorkProductFile, encode_envelope as document_envelope
from research_pipeline.project import (
    AttributedText, IntakeDeclaration, IntakeRequirement, ProceduralJudgment,
    ReadinessProposal, ProjectSetup, encode_envelope, setup_presentation,
)
import research_pipeline


def known(text):
    """Preserve a supplied known declaration literally."""
    return DeclaredText(text, None)


def pin(identity, revision, role, kind):
    """Name an exact revision without resolving any current head."""
    return RecordReference(identity, revision, role, kind)


actor = known("Synthetic researcher; unauthenticated")
unknown = DeclaredText(None, "Not supplied in this synthetic example")
creator = CreationProvenance("synthetic-author", "2026-10-31T12:00:00Z", {})
controller = CreationProvenance("synthetic-controller", "2026-10-31T12:01:00Z", {})
source_root = Path(research_pipeline.__file__).resolve().parents[3]
empty_inspection = CorpusInspection("uninspected", [], known("No supplied materials yet"), actor, [])
unassessed = ProceduralJudgment("not_assessed", "Materials have not arrived", actor)
baseline = CorpusManifest("Synthetic seed inventory", "Retain exact supplied material", "Explicit selection", actor,
                          [], [], [], [], [], [], None, "Empty original baseline", actor, [])
shell = ProjectSetup(AttributedText(known("Synthetic question"), actor),
                     AttributedText(known("Explore domain restrictions"), actor),
                     AttributedText(known("Clarify what can be asked of a short note"), actor),
                     pin("seeds", 1, "initial_corpus", "corpus_manifest"),
                     pin("seeds", 1, "current_corpus", "corpus_manifest"), None, None, None,
                     empty_inspection, [], [],
                     ReadinessProposal("insufficient_materials", ["No supplied seeds yet"], actor, [], unassessed, unassessed),
                     [], None, "Create setup shell", actor)
with TemporaryDirectory(prefix="project-intake-example-", dir="/tmp") as temporary:
    parent = Path(temporary)
    input_root = parent / "input"
    input_root.mkdir(mode=0o700)
    (input_root / "notes").mkdir(mode=0o700)
    note = input_root / "notes" / "seed.txt"
    note.write_text("Let f(x)=x on the real numbers. What changes on a restricted domain?\n", encoding="utf-8")
    note.chmod(0o600)
    root = parent / "runtime"
    saved = parent / "initial.json"
    with RecordStore.create(root) as store:
        initial = Submission("empty-setup", controller,
                             [encode_envelope("project", 1, shell, creator), corpus_envelope("seeds", 1, baseline, creator)],
                             {"project": 0, "seeds": 0})
        saved.write_text(json.dumps(initial.to_dict()), encoding="utf-8")
        original_receipt = store.submit_typed(initial)
        assert setup_presentation(shell) == "awaiting_materials"
        provenance = SourceProvenance("supplied_local", actor, unknown, known(str(note)), unknown, unknown, "available", [])
        restriction = SourceDeclaration("unknown", "No processing grant supplied")
        source = Source("synthetic-note", unknown, unknown, known("Supplied short note"), [actor], provenance,
                        SourceRestrictions(restriction, restriction, restriction, restriction), [], [], [],
                        SourceReading("uninspected", [], None, "unreported", [], actor, []), [], [], None, [])
        metadata = source.to_dict()
        for field in ("format", "version", "kind"):
            del metadata[field]
        metadata["originals"] = [{"artifact_id": "note", "path": "notes/seed.txt",
                                  "media_type": known("text/plain").to_dict(), "provenance": provenance.to_dict()}]
        metadata["locations"] = [SourceLocation("question", "note", "section", "Supplied short question", None, None).to_dict()]
        capture = prepare_source_capture(store, input_root,
            selected_files=[{"artifact_id": "note", "input_path": "notes/seed.txt"}], metadata=metadata,
            record_id="capture", revision=1, expected_head=0, submission_id="capture-note",
            record_provenance=creator, submission_provenance=controller, source_root=source_root,
            backup_roots=[], control_roots=[], max_file_bytes=4096, max_total_bytes=4096, max_files=1)
        store.submit_typed(capture.submission)
        captured = decode_source(capture.submission.records[0])
        original = captured.originals[0]
        seed = CorpusEntry("seed", "captured", "research_note", known("Supplied short note"), known("Synthetic collection"),
                           known("notes/seed.txt"), pin("capture", 1, "inventory_source", "source"),
                           [CorpusOriginal(original.artifact_id, original.path, original.provenance.supplied_locator, original.artifact)],
                           None, None, empty_inspection)
        current = replace(baseline, entries=[seed], supersedes=pin("seeds", 1, "supersedes", "corpus_manifest"),
                          revision_reason="Add supplied original after empty baseline", revision_attribution=actor,
                          changes=[CorpusEntryChange("added", "seed", None, "Capture supplied note", actor)])
        store.submit_typed(Submission("add-seed", controller, [corpus_envelope("seeds", 2, current, creator)], {"seeds": 1}))
        context = ResearchContext("How does restricting the domain affect the stated identity?", ["f(x)=x"],
                                  ["f is the supplied identity map"], [], [], ["x is real"], [], [], [], [], [])
        scope = pin("context", 1, "context", "research_context")
        documents = []
        for identity, label, path in (("brief", "research_brief", "brief/research.md"),
                                      ("intake", "intake_report", "reports/intake/intake/report.md")):
            artifact = store.put_artifact(("Synthetic authored " + label + ": study domain restrictions; no scientific validation.\n").encode())
            document = WorkProductManifest(label, "Synthetic " + label, "Record attributed intake", ["Synthetic researcher"],
                None, None, scope, None, [], [pin("capture", 1, "linked_source", "source")], None,
                [pin("seeds", 1, "build_dependency", "corpus_manifest"), pin("seeds", 2, "build_dependency", "corpus_manifest")],
                [WorkProductFile(path, artifact)], path, ["No scientific validation or operating authorization"])
            documents.append(document_envelope(identity, 1, document, creator))
        store.submit_typed(Submission("author-documents", controller,
            [*documents, context_envelope("context", 1, context, creator)], {"brief": 0, "intake": 0, "context": 0}))
        location = CorpusLocation("seed", pin("capture", 1, "source_location", "source"), "question")
        inspected = CorpusInspection("selected_material", [location], known("No literature or alternative domains reviewed"), actor, [])
        observation = IntakeDeclaration("question", "proposed_question", "Investigate the supplied question about domain restrictions",
            "supplied_observation", known("Supplied notes/seed.txt question"), actor, [location], [], ["Not a proved result"])
        relevant = ProceduralJudgment("affirmed", "Researcher declares this supplied identity question relevant and substantive", actor)
        usable = ProceduralJudgment("affirmed", "Researcher declares the restricted-domain assignment usable", actor)
        proposed = replace(shell, current_corpus=pin("seeds", 2, "current_corpus", "corpus_manifest"), context=scope,
            brief=pin("brief", 1, "research_brief", "work_product_manifest"),
            intake_report=pin("intake", 1, "intake_report", "work_product_manifest"), inspection=inspected,
            declarations=[observation], remaining=[IntakeRequirement("operating-policy", "policy_proposal", "research_admission",
                AttributedText(known("Authorized operating policy and budget remain required before admission"), actor))],
            readiness=ReadinessProposal("proposed_ready", ["Attributed judgments and exact seed/documents recorded"], actor,
                                        ["question"], relevant, usable),
            supersedes=pin("project", 1, "supersedes", "project"), revision_reason="Record supplied intake dossier", revision_attribution=actor)
        appended = encode_envelope("project", 2, proposed, creator)
        store.submit_typed(Submission("propose-intake", controller, [appended], {"project": 1}))
        assert proposed.initial_corpus.revision == 1 and proposed.current_corpus.revision == 2
        assert appended.operational_status is None and appended.scientific_disposition is None
        assert setup_presentation(proposed) == "awaiting_authorization"
    with RecordStore.open(root) as reopened:
        assert reopened.get_typed_revision("project", 1)[1] == shell
        assert reopened.get_typed_revision("project", 2)[1] == proposed
        saved_request = Submission.from_dict(json.loads(saved.read_bytes()))
        assert reopened.submit_typed(saved_request) == original_receipt
        assert reopened.read_artifact(original.artifact) == note.read_bytes()
```

## Detached reading projection

The [readable snapshot planner](readable-snapshots.md) accepts a detached capture of
an explicit project and additional roots. It displays exact initial/current corpus,
context, authored brief/intake reports, remaining requirements and setup presentation
when their actual supported targets permit it. Null and partial setup stay visible.
Opaque targets retain raw envelopes and navigation; local dossier/corpus mapping
failures become explicit projection limitations rather than silently established
mappings. The captured outgoing closure includes every attachment of a reached
Source, which is distinct from corpus original selection and inspection coverage.
This reader does not certify historical typed admission, research readiness or
operating authority. Manifest artifact entries retain expected/unverified declarations
even after publication. Materialization separately verifies the complete private
generation; offline inspection checks its current local contents.

## Authenticated readiness is separate from the proposal

[Operating authority](operating-authority.md) now checks this exact dossier under
externally configured HMAC credentials and signed procedural judgments. It reuses
these technical intake and role-membership checks, verifies selected original and
brief/report bytes for main research, and watches relevant exact heads. Incomplete
setup may receive setup-only permission. `setup_presentation` remains proposal-only.
An eligibility observation must be recomputed inside a later admitting transaction;
no research admission or scientific endorsement follows from a proposal or signature.
