# Immutable seed inventories

`research_pipeline.corpus` records an explicitly selected collection over exact
[Source captures](sources.md). Its only top-level typed content is
`CorpusManifest`, admitted and read through `RecordStore.submit_typed` and
`get_typed_revision`. Import the submodule directly; there are no package exports,
new submission services, dependencies, CLI commands or proposal formats.

A corpus is a full inventory snapshot. Its envelope supplies the stable identity
and revision; content does not repeat them. Revision 1 is the original baseline.
Every later revision explicitly pins its immediately preceding revision. Saving
or reading an inventory confers no scientific support, operating permission,
exposure certificate, project-ready state or authority to launch research.
Operational status and scientific disposition are always null.

Empty, metadata-only and partial inventories are valid recorded setup data. They
are insufficient by themselves for main research. Inventory, reading, permission,
scientific support and project readiness remain separate. Unknown provenance and
uninspected material must remain explicit rather than being inferred from names,
classification, byte hashes or a short list of locations.

## Required constructors and wire fields

All arguments are required, in the orders below, including every nullable field
and empty collection. `D` below means the existing `source.DeclaredText`, not a
new type or alias. Known declarations are `DeclaredText(value, None)`; unknowns
are `DeclaredText(None, unknown_reason)`. Exactly one nonblank field is required.
`SourceProvenance`, `SourceRestrictions`, `RecordReference` and `ArtifactReference`
are reused with their existing validation.

Constructor collections accept ordinary lists/tuples and become detached tuples.
Wire collections must be ordinary lists. Every nested wire object's fields are
exactly its constructor fields. Only `CorpusManifest` adds the fixed header
`format="research_pipeline.corpus_content"`, `version=1`,
`kind="corpus_manifest"`. No header/state constructor arguments exist.

```text
CorpusOriginal(
    artifact_id: str,
    path: str,
    supplied_locator: D,
    artifact: ArtifactReference,
)
CorpusUncaptured(
    authors: tuple[D, ...],
    upstream_identity: D,
    upstream_version: D,
    provenance: SourceProvenance,
    restrictions: SourceRestrictions,
)
CorpusLocation(
    entry_id: str,
    source: RecordReference,
    location_id: str,
)
CorpusInspection(
    coverage: str,
    locations: tuple[CorpusLocation, ...],
    uninspected: D,
    attribution: D,
    limitations: tuple[str, ...],
)
CorpusEntry(
    entry_id: str,
    status: str,
    classification: str,
    title: D,
    origin_collection: D,
    origin_locator: D,
    source: RecordReference | None,
    originals: tuple[CorpusOriginal, ...],
    uncaptured: CorpusUncaptured | None,
    reason: str | None,
    inspection: CorpusInspection,
)
CorpusObservation(
    observation_id: str,
    category: str,
    text: str,
    attribution: D,
    entry_ids: tuple[str, ...],
    locations: tuple[CorpusLocation, ...],
    unresolved_locator: D | None,
    limitations: tuple[str, ...],
)
CorpusLink(
    link_id: str,
    source_entry_id: str,
    source_location: CorpusLocation | None,
    original_locator: D,
    original_text: D,
    target_kind: str,
    target_entry_id: str | None,
    target_location: CorpusLocation | None,
    external_locator: str | None,
    unresolved_reason: str | None,
    attribution: D,
)
CorpusRelationship(
    relationship_id: str,
    source_entry_id: str,
    target_entry_id: str,
    relation: str,
    detail: str,
    attribution: D,
)
CorpusExposure(
    entry_id: str,
    candidate_content: str,
    detail: D,
    attribution: D,
)
CorpusEntryChange(
    action: str,
    entry_id: str,
    replaces_entry_id: str | None,
    reason: str,
    attribution: D,
)
CorpusManifest(
    title: str,
    purpose: str,
    selection_provenance: str,
    attribution: D,
    entries: tuple[CorpusEntry, ...],
    observations: tuple[CorpusObservation, ...],
    links: tuple[CorpusLink, ...],
    relationships: tuple[CorpusRelationship, ...],
    exposures: tuple[CorpusExposure, ...],
    limitations: tuple[str, ...],
    supersedes: RecordReference | None,
    revision_reason: str,
    revision_attribution: D,
    changes: tuple[CorpusEntryChange, ...],
)
```

Every class provides strict `to_dict() -> dict` and `from_dict(value: dict)`.
The manifest's attribution applies to title, purpose, selection provenance and
collection limitations. Inspections, observations, links, relationships, exposures
and changes keep their own attribution. Attribution may explicitly be unknown;
it is a declaration, never authenticated identity. Envelope `CreationProvenance`
remains separately supplied and need not equal these declarations.

| Bound | Limit |
| --- | --- |
| Corpus-owned ordinary text | Nonblank scalar Unicode, at most 16,384 characters; spelling/whitespace preserved |
| IDs | 1–128 ASCII letters/digits/underscore/hyphen, starting with a letter/digit |
| Original logical path | Portable path rules below; at most 4,096 characters |
| Each collection except changes | At most 1,024 members |
| Changes | At most 2,048 members, allowing complete replacement of 1,024 entries |
| Originals across all entries | At most 1,024 occurrences, including repeated bytes/selections |
| Locations across inspections, observations and links | At most 4,096 occurrences |
| Reference revision | Ordinary integer 1 through `2**63-1` |
| Artifact size | Ordinary integer 0 through `2**63-1` |

Collection bounds are checked before reconstructing members. Reused Source
declarations retain their existing bounds. Bool, float and string coercion is
forbidden for integers. Every nested exact class is reconstructed defensively;
subclasses, serialization lookalikes and bypassed frozen-state mutations fail.

## Entry and inspection declarations

`status` is exactly `captured`, `reference_only`, `unavailable` or `unresolved`.
`classification` is exactly `research_note`, `published_source`, `derivation`,
`notebook`, `calculation`, `software`, `data`, `prior_report`,
`operating_instruction`, `other` or `unknown`. These labels do not infer scientific
equivalence, readability or substantive relevance.

Captured entries require an exact `inventory_source → source` reference,
nonempty originals, null uncaptured and null reason. Authorship, upstream
identity/version, acquisition provenance, original modes and restrictions come
exclusively from that pinned Source. There are no corpus restriction overrides
or operational permission fields. Each selected original's artifact ID, logical
path, supplied locator and digest/size must exactly match a member of
`Source.originals`, including `SourceArtifact.provenance.supplied_locator`.
Extraction outputs cannot be selected as originals.

Noncaptured entries require null source, empty originals, `CorpusUncaptured` and
a nonblank status reason. Uncaptured authors are nonempty and may include explicit
unknowns. Its provenance/restrictions are reported or unknown Source declarations,
not grants; there are no artifact references. Entry origin collection/locator
record separately attributed collection context and need not equal the Source's
top-level acquisition provenance.

Original artifact IDs are unique within each entry. Different entries may select
the same Source, artifact or repeated bytes. Repeated digests must always have
identical sizes. Entry, observation, link and relationship IDs are unique within
their respective collections. Exposures are unique by current entry ID.

Each `CorpusLocation` requires `source_location → source`. Its entry must be
captured, and its record identity/revision must match that entry's inventory pin;
the differing reference relationship is intentional. Durable admission checks
that the exact Source location exists and anchors to an original selected by
that specific entry. Derived-output locations, unanchored upstream labels and
originals selected only by another entry fail, even when both entries share a
Source. Labels and ranges come from the Source location and are not duplicated.

Inspection coverage is exactly `uninspected`, `metadata_only`,
`selected_material` or `unknown`. `selected_material` requires nonempty exact
locations belonging to this captured entry. Every other coverage requires an
empty location list. Metadata-only inspection does not claim inspection of
original bytes. The required `uninspected` declaration describes the remainder,
including any uninspected part of a partially inspected artifact. It can be
explicitly unknown. Locations do not imply exhaustive coverage or calculate a
complement. Duplicate exact locations within one collection fail; separate
declarations may repeat them. Intake inspection does not alter `Source.reading`,
its report or coverage.

## Observations, links, relationships and exposure

Observation category is exactly `relevance`, `purpose`, `contradiction`, `gap`,
`proposed_question`, `proposed_baseline` or `unresolved_mapping`. Entry IDs are
ordered, unique current entries; empty means collection scope. Every pinned
location must belong to an entry in that observation's entry IDs. Only
`unresolved_mapping` requires non-null `unresolved_locator`; other categories
require null. Its text explains the missing/broken mapping. Any locations supplied
with it describe successfully pinned endpoints only. Unknown/nonexistent endpoints
remain in the unresolved declaration. These observations create no Claims, Issues,
work products, assessments, calculations or judgments of scientific sufficiency.

Every link names a current source entry. An optional source location must belong
to that entry. At least one original locator/text declaration must be known;
both are preserved exactly. Self-links are allowed.

| Link target kind | Required target | Fields that must be null |
| --- | --- | --- |
| `entry` | Current `target_entry_id`, including a noncaptured entry | target_location, external_locator, unresolved_reason |
| `source_location` | Exact `target_location`, whose entry_id identifies its target | target_entry_id, external_locator, unresolved_reason |
| `external` | Nonblank external_locator | target_entry_id, target_location, unresolved_reason |
| `unresolved` | Nonblank unresolved_reason | target_entry_id, target_location, external_locator |

An entry target resolves inventory identity, not byte availability. No imported
text is parsed, external locator opened, link discovered, or unresolved link
silently repaired. `CorpusRelationship` connects two distinct current entries
with relation exactly `duplicate`, `version`, `related` or `accompanying`, a
nonblank detail and explicit attribution. Separate declarations and their order
are preserved. Licenses, data and operating instructions can have their own
classified entries and explicit accompanying relationships. Matching bytes never
automatically create relationships.

Exposure candidate_content is exactly `reported_present`, `reported_absent` or
`unknown`. Detail and attribution are explicit known/unknown declarations. This
records candidate-bearing material only. It supplies neither authenticated
session exposure nor independent-checking certification or visibility authority.

## Logical paths and inert provenance strings

`CorpusOriginal.path` uses the existing [portable logical path rules](work-products.md#portable-logical-paths):
relative POSIX paths, no traversal/absolute/drive forms, unsafe separators,
control/format characters, device names or unsafe trailing dots/spaces.
NFKC/casefold alias collisions, file/directory-prefix conflicts and inconsistent
shared-directory spelling fail within each entry's selected originals. Paths
are preserved, never normalized or opened. Collision checks do not span separate
entries or Sources.

By contrast, supplied_locator, origin_collection, origin_locator, original link
strings and external locators are bounded inert provenance text. Absolute paths,
URLs, Markdown/wikilinks and traversal-looking strings are allowed literally.
They are never filesystem arguments, acquisition requests or operating instructions.
The separate capture API has its own explicit input-path authorization/selection
checks; storing a locator here does not invoke it.

## Baseline and revision identity

Every revision has a reason and attribution; the baseline reason describes the
initial selection. Revision 1 requires null supersedes. Every `n > 1` requires
`RecordReference(same_record_id, n-1, "supersedes", "corpus_manifest")`.
Both envelope directions reject omitted, skipped, cross-identity, self and future
predecessors. Content-only decoding can check role/kind and baseline declarations
but cannot know the enclosing record identity/revision.

Changes have action exactly `added`, `corrected` or `removed`, with unique entry
IDs. Added/corrected IDs must be present; removed IDs must be absent. Only an added
change may set replaces_entry_id, naming a distinct removed ID in this revision;
at most one replacement may claim it. Baselines have exactly one added declaration
per entry and no replacements; empty baselines have no changes.

Admission compares each full snapshot to its immediate predecessor: all new IDs
must have added changes, all absent prior IDs removed changes, and all retained
entries whose complete values differ corrected changes. Unchanged entries have no
change declaration. False/no-op corrections and missing/false changes fail.
Ordering changes and top-level observations, links, relationships, exposures,
title, purpose, selection provenance, attribution or limitations changes use the
revision reason and do not manufacture entry changes. Caller ordering is preserved.
Every snapshot independently rejects dangling local references after removal.

An entry's immutable material binding is exactly `(status, origin_collection,
origin_locator, source, originals, uncaptured)`. Correction may change title,
classification, reason or inspection but cannot change that binding. Repinning
Source, changing selected originals/mappings, changing origin or uncaptured
provenance/restrictions, or converting unresolved material to captured requires
removal plus a fresh ID with an explicit added.replaces_entry_id declaration.
Replacement identifies a new inventory observation, not scientific equivalence.
A removed ID can never be reused later in this corpus history, even for identical
bytes; reintroduction uses a fresh ID.

Constrained corpus history must decode coherently to revision 1. Generic payloads,
unsupported formats/versions and incoherent typed-looking predecessors block
continuation: there is no generic-to-typed baseline transition or implicit reset.
Supported typed payloads originally stored using generic submit receive the same
history checks when constrained traversal subsequently reaches them. Storage does
not authenticate which API admitted a revision; neither traversal nor its original
receipt creates that certification. Source's existing permitted legacy transition
and optional work-product supersession remain unchanged.

## Codecs, exact projections and traversal

| Operation in research_pipeline.corpus | Result |
| --- | --- |
| `decode_content(value: dict) -> CorpusManifest` | Strict version-1 content |
| `dumps_content(value: CorpusManifest) -> str` | Sorted-key compact ASCII-escaped JSON; array order and Unicode values preserved |
| `loads_content(data: str \| bytes) -> CorpusManifest` | Strict JSON, bytes decoded as UTF-8 |
| `encode_envelope(record_id: str, revision: int, content: CorpusManifest, provenance: CreationProvenance) -> RecordEnvelope` | Detached null-state envelope with exact projections and local history checks |
| `decode_envelope(envelope: RecordEnvelope) -> CorpusManifest` | Revalidated exact content, ordered projections and local history |

Missing format raises existing `scientific.NotTypedContentError`, a
`DomainValidationError` subtype. Other malformed input raises `DomainValidationError`
with field/index context and chained causes where applicable. Missing/extra fields
at every depth, missing reference target_kind, unsupported headers, duplicate JSON
keys at every depth, nonfinite values including numeric overflow, invalid UTF-8,
nonscalar Unicode, cycles/excessive nesting, nonordinary containers, subclasses,
lookalikes and forged frozen state fail. Constructors and codecs are pure: no
filesystem, network, subprocess, model or store access.

| Envelope projection | Exact order and membership |
| --- | --- |
| record_references | supersedes if present; every captured entry's source in entry order; entry inspection locations in entry/location order; observation locations in observation/location order; each link's optional source_location then optional target_location in link order |
| artifact_references | Scan entries then originals in caller order; retain the first occurrence of each digest, with exact size |

Every location contributes its source reference occurrence. Record edges are
never deduplicated across entries or roles. Direct artifacts are exactly selected
originals: no extraction outputs, unselected Source artifacts or predecessor-only
artifacts are projected. Both envelope directions require complete ordered
equality; extra, missing, reordered or substituted projections fail without repair.

This is the complete traversal table (also canonical in
[attributed assessments](attributed-assessments.md#durable-api-and-exact-traversal)).

| Decoded kind | Traversed roles → required typed kinds | Shallow roles → declared generic kinds |
| --- | --- | --- |
| ResearchContext | None | None |
| Claim | `context` → research_context | None |
| Justification | `context` → research_context; `premise`, `conclusion` → claim; `evidence` → evidence | None |
| Evidence | `context` → research_context; `target_claim` → claim | `input_record` → any supported kind, or explicit null |
| Review | `candidate_claim` → claim; `target_context` → research_context; `reported_evidence` → evidence; `assessed_route` → justification | `context_manifest` → work_product_manifest; `authorization_policy` → decision; `reported_tool_execution` → tool_execution |
| Issue | `supporting_evidence` → evidence | `affected_record` → any supported kind, including scientific, review and issue |
| WorkProductManifest | `context` → research_context; `linked_claim` → claim; `supersedes` → work_product_manifest | `task` → task_specification; `branch` → branch; `run` → run; `linked_source` → source; `build_dependency` → any explicitly declared supported kind |
| Source | `supersedes` → source; `reading_report` → work_product_manifest with product_kind reading_report; `reported_evidence` → evidence | `related_source` → source; `reported_tool_execution` → tool_execution |
| CorpusManifest | `supersedes` → corpus_manifest; `inventory_source`, `source_location` → source, with complete history, exact original selection and per-entry location checks | None |

Local entry IDs, changes, relationship endpoints, strings, provenance details and
exposure declarations are not additional graph traversal inputs. Shallow edges
check only exact existence and declared kind, never target payloads, outgoing
links or attachments. Evidence input_record retains its existing nullable declared
kind. An independently submitted typed member is always decoded. A shallow use
cannot excuse a separate constrained occurrence of the same target.

## Durable checks, artifacts and recovery

The existing typed store supports nine kinds and returns
`ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest`
from `get_typed_revision`. New target/history checks remain in the same serialized
transaction, before metadata insertion, after original-ID reconciliation,
schema-kind checks and ordinary expected-head CAS/batch checks. Resolution uses
proposed batch members first, then exact historical metadata, with cached envelopes,
decoded values, a processed set and an iterative worklist. Each location use is
checked against its own entry selection even after another role reached the same
Source. All reachable corpus histories are checked in ascending revision order,
tracking previously used IDs per corpus in transaction-local memory. Every
historical diff and immutable binding is checked, not just the newest successor.
Existing Source closure and separately implemented Review checks are unchanged.

Local submitted malformation raises `DomainValidationError`. Missing/wrong-kind or
unsupported constrained targets, selection/location mismatches and cross-revision
failures raise `ReferenceResolutionError` with role and exact target context (and
corpus/entry/location context for corpus semantic checks). Underlying codec/domain
causes are chained where applicable. Existing artifact, CAS, submission-conflict,
schema and database errors retain their meaning. Rejection leaves all application
tables, heads, links, submissions, receipts and events unchanged; published orphan
artifact files may remain.

Current direct selected artifacts receive existing verification and synchronization.
Closure reads metadata only; it never calls public record/history/artifact reads.
Damaged unselected Source originals, extraction outputs or predecessor-only bytes
do not cause new transitive artifact reads. Removing a damaged baseline selection
can therefore produce a new valid snapshot while keeping its metadata history.
Damage to a currently selected original fails a new direct submission or typed
read. Typed reads verify this envelope's direct artifacts and local codec coherence;
they do not traverse history, certify past admission or prove availability of the
whole transitive Source graph.

Exact original-ID retries return the original receipt/event before head, target
or artifact checks, including locally valid requests originally committed through
generic submit. Local normalization/codec validation still precede reconciliation.
Changed content, attribution or meaningful ordering under that ID conflicts.
Generic submit continues to accept arbitrary generic corpus payloads under its
existing rules. Canonical states remain null for typed content.

Save a complete ordinary `Submission.to_dict()` JSON proposal before submitting;
reconstruct with `Submission.from_dict`. Do not use the Source-only saved-proposal
wrapper for corpus proposals. Competing expected-head submissions yield one CAS
winner without modifying the losing proposal or issuing it a receipt. On ambiguous
commit acknowledgment, close/reopen and reconcile the saved original identity.
The unchanged fault seams distinguish rollback before metadata/after first revision
from complete commit with lost acknowledgment after commit.

Healthy schema-2 backup/inspect/exact restore preserves every table, envelope,
selection, observation, byte, canonical request, receipt and event without replay.
Backup integrity verification still covers its complete referenced byte set, even
though corpus closure is metadata-only. Schema 1 refuses corpus admission until
explicit attributed v1-backup → schema-2 restore migration; subsequent schema-2
backup/exact restore retains old receipts and new corpus history. No schema,
migration or backup algorithm changes are part of this feature.

## Runnable local example

From the candidate root, run the exact Python block below with worktree-relative
imports using:

```sh
PYTHONPATH=implementation/src python3 -B -c 'from pathlib import Path; text = Path("docs/corpus.md").read_text(); section = text.split("## Runnable local example\n", 1)[1]; exec(section.split("```python\n", 1)[1].split("```", 1)[0])'
```

The example uses temporary runtime/input paths outside source, the actual candidate
source root for exclusions, explicit Source declarations and caller-selected IDs.
All bytes are synthetic and inert. Tests extract and execute this exact block in
a fresh candidate-source interpreter.

```python
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import research_pipeline
from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.source import (
    DeclaredText, SourceProvenance, SourceDeclaration, SourceRestrictions,
    SourceReading, SourceLocation, decode_envelope as decode_source,
)
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.corpus import (
    CorpusOriginal, CorpusUncaptured, CorpusLocation, CorpusInspection, CorpusEntry,
    CorpusLink, CorpusEntryChange, CorpusManifest, encode_envelope,
)
from research_pipeline.store import RecordStore


def known(text):
    """Preserve a caller-supplied declaration as known text without interpreting it."""
    return DeclaredText(text, None)


unknown = DeclaredText(None, "Not supplied in synthetic example")
author = known("Synthetic supplier α")
creator = CreationProvenance("supplier", "2026-10-31T12:00:00Z")
controller = CreationProvenance("controller", "2026-10-31T12:01:00Z")
source_root = Path(research_pipeline.__file__).resolve().parents[3]
declaration = SourceDeclaration("unknown", "No permission inferred")
restrictions = SourceRestrictions(declaration, declaration, declaration, declaration)


def capture(store, inputs, identity, filename, data):
    """Capture one synthetic local original with explicit provenance, then commit its saved Source request."""
    path = inputs / filename
    path.write_bytes(data)
    path.chmod(0o640)
    provenance = SourceProvenance("supplied_local", author, unknown, known(str(path)),
                                  unknown, unknown, "available", ["Synthetic local example"])
    metadata = {
        "work_id": identity + "-work", "upstream_identity": unknown.to_dict(),
        "upstream_version": known("supplied edition").to_dict(), "title": known(filename).to_dict(),
        "authors": [unknown.to_dict()], "provenance": provenance.to_dict(),
        "restrictions": restrictions.to_dict(),
        "originals": [{"artifact_id": "original", "path": "notes/" + filename,
                       "media_type": unknown.to_dict(), "provenance": provenance.to_dict()}],
        "extractions": [],
        "locations": [SourceLocation("section", "original", "section", "Supplied first section", None, None).to_dict()],
        "reading": SourceReading("uninspected", [], None, "unreported", [], unknown, []).to_dict(),
        "statements": [], "related_sources": [], "supersedes": None, "limitations": ["Not scientifically evaluated"],
    }
    prepared = prepare_source_capture(
        store, inputs, selected_files=[{"artifact_id": "original", "input_path": filename}],
        metadata=metadata, record_id=identity, revision=1, expected_head=0,
        submission_id=identity + "-submission", record_provenance=creator,
        submission_provenance=controller, source_root=source_root, backup_roots=[], control_roots=[],
        max_file_bytes=10000, max_total_bytes=10000, max_files=1,
    )
    store.submit_typed(prepared.submission)
    return decode_source(prepared.submission.records[0])


def selected(entry_id, identity, source):
    """Map one exact Source original into a separately attributed uninspected inventory entry."""
    original = source.originals[0]
    return CorpusEntry(
        entry_id, "captured", "research_note", source.title, known("Synthetic collection"),
        known("[[" + original.path + "]]"), RecordReference(identity, 1, "inventory_source", "source"),
        [CorpusOriginal(original.artifact_id, original.path, original.provenance.supplied_locator, original.artifact)],
        None, None, CorpusInspection("uninspected", [], unknown, author, []),
    )


with TemporaryDirectory(prefix="corpus-example-", dir="/tmp") as temporary:
    parent = Path(temporary)
    inputs = parent / "inputs"
    # Owner-only directory permissions satisfy the existing capture safety checks.
    inputs.mkdir(mode=0o700)
    root = parent / "records"
    with RecordStore.create(root) as store:
        first_source = capture(store, inputs, "source-a", "α.txt", b"Synthetic first section\nUninspected remainder\n")
        second_source = capture(store, inputs, "source-b", "b.tex", b"Synthetic TeX-like $x^2$\n")
        first = selected("seed-a", "source-a", first_source)
        inspected = CorpusLocation("seed-a", RecordReference("source-a", 1, "source_location", "source"), "section")
        first = replace(first, inspection=CorpusInspection(
            "selected_material", [inspected], known("Remainder of original, including later sections"), author, []))
        missing_provenance = SourceProvenance(
            "unknown", author, unknown, known("[[missing]]"), unknown, unknown,
            "unavailable", ["Only an unresolved reference was supplied"],
        )
        unresolved = CorpusEntry(
            "unresolved", "unresolved", "unknown", unknown, known("Synthetic collection"), known("[[missing]]"),
            None, [], CorpusUncaptured([unknown], unknown, unknown, missing_provenance, restrictions),
            "No supplied original for this reference", CorpusInspection("metadata_only", [], unknown, author, []),
        )
        link = CorpusLink("missing-link", "seed-a", inspected, known("[[missing#section]]"), unknown,
                          "unresolved", None, None, None, "No exact endpoint supplied", author)
        baseline = CorpusManifest(
            "Synthetic partial inventory", "Preserve starting selections", "Explicit supplier selection", author,
            [first, unresolved], [], [link], [], [], ["Insufficient by itself for main research"], None,
            "Initial partial selection", author,
            [CorpusEntryChange("added", identity, None, "Initial selection", author) for identity in ("seed-a", "unresolved")],
        )
        first_envelope = encode_envelope("seeds", 1, baseline, creator)
        initial = Submission("inventory-initial", controller, [first_envelope], {"seeds": 0})
        receipt = store.submit_typed(initial)
        corrected = replace(first, title=known("Corrected description α"))
        addition = selected("seed-b", "source-b", second_source)
        successor = replace(
            baseline, entries=[corrected, unresolved, addition],
            supersedes=RecordReference("seeds", 1, "supersedes", "corpus_manifest"),
            revision_reason="Correct description and add the second selection", revision_attribution=author,
            changes=[CorpusEntryChange("corrected", "seed-a", None, "Corrected title only", author),
                     CorpusEntryChange("added", "seed-b", None, "Additional supplied selection", author)],
        )
        store.submit_typed(Submission("inventory-next", controller,
                          [encode_envelope("seeds", 2, successor, creator)], {"seeds": 1}))
    with RecordStore.open(root) as reopened:
        assert reopened.get_typed_revision("seeds", 1) == (first_envelope, baseline)
        assert reopened.get_typed_revision("seeds", 2)[1] == successor
        assert reopened.get_typed_revision("source-a", 1)[1] == first_source
        assert reopened.read_artifact(first.originals[0].artifact) == b"Synthetic first section\nUninspected remainder\n"
        assert reopened.read_artifact(addition.originals[0].artifact) == b"Synthetic TeX-like $x^2$\n"
        assert (inputs / "α.txt").read_bytes() == reopened.read_artifact(first.originals[0].artifact)
        assert reopened.submit_typed(initial) == receipt
        assert baseline.entries[0].title != successor.entries[0].title
        assert baseline.entries[0].originals == successor.entries[0].originals
```

## Deferred boundaries

This feature records a prerequisite for later intake and readable views. Project
setup/readiness decisions and authorized operating envelopes, full scientific
intake/interpretation, archive extraction, link discovery/parsing/OCR/network
acquisition, vault generation/edit protection, CLI lifecycle, tool execution,
exposure enforcement and scientific evaluation remain deferred. Stored instructions
never enable tools or broaden Source declarations. No complete D03 or product
completion follows from this inventory feature.
