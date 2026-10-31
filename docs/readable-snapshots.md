# Detached readable snapshot plans

This API captures a bounded, consistent selection of committed metadata and plans
an offline reading view. It does **not** read or verify artifact bytes, copy files,
choose a destination, publish a generation, inspect an existing view, refresh it,
or import displayed edits. Those materialization responsibilities belong to the
second milestone. There is no new CLI command.

A plan is a private local reading snapshot, not a backup, redistributable export,
independently filtered worker/reviewer workspace, or new source of scientific
truth. Source restrictions remain declarations, not permission to disclose. No
sync, subscription, plugin, execution, operating policy, authorized readiness,
task admission, scientific qualification, or permission enforcement is supplied.
Synthetic test dossiers are engineering evidence, not scientific evaluation.

## Public constructors and entry points

Import directly from the modules, without package-wide aliases:

```python
from research_pipeline.snapshot import RootSelector, SnapshotSelection, SnapshotLimits
from research_pipeline.view_plan import plan_readable_snapshot, verify_plan_links

selection = SnapshotSelection(
    project=RootSelector("project", None),
    roots=(RootSelector("claim", 3), RootSelector("report", None)),
)
limits = SnapshotLimits(
    max_roots=10,
    max_records=200,
    max_references=4000,
    max_record_bytes=2_000_000,
    max_metadata_bytes=20_000_000,
    max_artifacts=200,
    max_files=2000,
    max_file_bytes=20_000_000,
    max_total_bytes=100_000_000,
)
# store is an already-open RecordStore; these identities must actually exist.
snapshot = store.capture_snapshot(selection, limits=limits)
# snapshot remains usable after store.close().
plan = plan_readable_snapshot(snapshot)
verify_plan_links(plan)
```

`RootSelector(record_id: str, revision: int | None)` uses the existing opaque
ASCII identifier syntax. `None` explicitly requests the current head; an ordinary
positive integer selects that exact historical revision. It has no invented
scientific relationship. `SnapshotSelection(project, roots)` requires a project
selector and an explicit list or tuple of additional selectors, possibly empty.
It detaches the sequence and preserves request order. Identical selectors are
rejected, including a duplicate of the project selector. Current and exact
requests for one identity remain separate requests even if both resolve to the
same revision. The project must have actual envelope kind `project`; its payload
may be generic or unsupported. Other root kinds are unrestricted within the
existing envelope domain.

`RecordStore.capture_snapshot(selection: SnapshotSelection, *,
limits: SnapshotLimits) -> DetachedSnapshot` is the only new store API.
`plan_readable_snapshot(snapshot: DetachedSnapshot) -> ReadablePlan` is pure:
there is no store, destination, filesystem, callback, clock, environment,
artifact-reader, or rendering-option parameter. One fixed version-1 rendering
policy applies. `verify_plan_links(plan: ReadablePlan) -> None` checks inventory,
manifest identity and generated navigation, raising `ViewPlanError` on defects;
construction and planning invoke it before returning a successful plan.

`DetachedSnapshot(document: dict)` validates a complete canonical snapshot
representation. Its private retained state is serialized text. `snapshot_id` is
a validated immutable digest; `selection`, `resolutions`, `schema`, `watermark`,
`records`, `artifacts`, `limits`, `scope` and `to_dict()` reconstruct independent
values. Records are identity/revision-sorted metadata dictionaries, including
`content_json`, `provenance_json`, canonical full `envelope_json`, classification,
local commit metadata and fetched-byte accounting. No mutable retained envelope,
provenance or reference object is exposed. Public consumption revalidates state,
including state altered by bypassing frozen dataclass assignment.
Redundant record identity/revision fields are validated independently. Exact JSON
copies are compared canonically, preserving the difference between `1`, `1.0` and
`true`; recomputing an identity cannot legitimize inconsistent representations.

`ReadablePlan` contains `snapshot_id`, `plan_id`, immutable tuples
`generated_files`, `artifact_copies`, `directories`, and `manifest_bytes`.
`GeneratedFile(relative_path, data: bytes, role, mode=0o400)` represents generated
bytes. `ArtifactCopy(relative_path, digest, size, mode=0o400)` represents an exact
**expectation**, with no supplied or observed bytes. `DirectoryEntry(relative_path,
mode=0o500)` represents a useful directory; the empty relative path is the root.
`limits` returns fresh effective budgets and `to_dict()` returns fresh manifest
metadata. These mode values are expectations only until materialization.

## Bounds and failure behavior

Every `SnapshotLimits` argument is required. Values must be ordinary integers in
SQLite's signed 64-bit range; booleans, floats, coercions and infinity are rejected.
Roots, records, record bytes, metadata bytes, files and file bytes must be positive.
References, artifacts and total bytes may be zero.

| Limit | What consumes it |
| --- | --- |
| `max_roots` | Every requested selector, including the project and separate current/exact requests. |
| `max_records` | Distinct exact `(record_id, revision)` pairs in the outgoing closure. |
| `max_references` | Every record-link and artifact-link occurrence, including repeats. |
| `max_record_bytes` | Per-record fetched metadata preflight and complete serialized record entry, including exact stored JSON, reconstructed envelope, classification and commit metadata. |
| `max_metadata_bytes` | Cumulative fetched metadata **plus** complete detached serialized representation, including JSON overhead, own identity, scope and effective limits. |
| `max_artifacts` | Distinct selected artifact digests. |
| `max_files` | Final physical inventory: every generated README/envelope/descriptor and each physical artifact copy. `manifest.json` counts. |
| `max_file_bytes` | Each expected artifact size and each generated file, including manifest. |
| `max_total_bytes` | Capture checks unique expected artifact bytes; planning additionally counts every physical copy occurrence plus every generated file, including the manifest. |

Record preflight uses SQLite BLOB lengths for UTF-8 text, including variable-width
link and relevant commit fields, before loading JSON or links. Accounting includes
the repeated JSON fetch required by the existing metadata envelope reader. Link
counts are checked before retrieval, ordinals must be contiguous, and closure
worklists are bounded. Stored content/provenance JSON nesting is limited to 64 before decoding;
the reconstructed full envelope permits its one additional wrapper level (65).
Version-1 manifest parsing permits five fixed wrapper levels (69 total): the
manifest object, artifacts array, artifact object, mappings array and mapping
object before embedded provenance. Top-level mappings add only three levels.
Reconstructed snapshot validation and canonical mapping comparisons still enforce
the underlying stored provenance limit of 64 and exact preservation. Duplicate
keys, nonfinite values, noncanonical storage JSON, malformed envelopes and invalid
canonical states are integrity errors. Planning reserves file counts before page
rendering, including every useful parent README as each mapping is added, and
checks bytes incrementally; it never truncates a page or drops an
attachment to meet a budget. Conservative fetched-byte accounting is part of the
versioned representation, not a promise of process RSS usage.

Invalid caller arguments raise `DomainValidationError`. Absent selected roots
retain `RecordNotFoundError`. Missing closure targets identify the source record,
revision and edge ordinal in `SnapshotIntegrityError`; wrong declared target kinds,
malformed metadata and absent/conflicting artifact registrations also fail capture.
`SnapshotLimitError` rejects any exceeded count/byte allowance. `ViewPlanError`
identifies projection/inventory/link failures. Existing store closed/busy/database
transaction errors retain their contracts. No required-target or budget failure
returns a partial successful snapshot/plan.

A recorded null brief/context/report, unknown declaration, unavailable/reference-only/
unresolved corpus entry or uninspected remainder is valid partial setup. Missing
physical object files are unknown at this milestone: even successful plans say
`expected_unverified`. Capture does not stat, open, hash or verify an object.

## Consistent navigation and identity

Capture uses one existing SQLite read transaction. The first watermark SELECT
establishes its snapshot; all requested current heads resolve within that same
snapshot. Traversal follows every outgoing `RecordReference` in ordinal order,
regardless of payload classification or the original admission role. Each exact
revision is visited once, cycles terminate, repeated edges remain recorded, and
`target_kind` is checked on every occurrence. Historical references are never
replaced by current heads. The existing DELETE journal mode is preserved: a writer
can prepare changes but cannot complete its commit while the reader retains its
snapshot. No WAL mode or connection-setting change is introduced.

All direct artifact occurrences of all reached records are included and checked
against exact digest/size registrations. This deliberately expands beyond a corpus
entry's selected originals when that entry reaches a Source with other attachments.
Inclusion does not imply that those extra originals were selected, exposed, read or
inspected by the corpus. No reverse edges, unrelated records or all-live-claim/
review/issue inventories are searched. Reverse navigation uses only captured records.

The snapshot stores schema version and SHA-256 of the fixed registry DDL after
whitespace normalization, in registry order. Its local watermark contains the
highest audit event ID, submission ID, committed time and submission fingerprint;
the empty-store representation has explicit null fields. This is not a global
database UUID or authentication claim. Capture does not load submission request
JSON or full audit history.

`snapshot_id` hashes a versioned canonical snapshot document with its own ID
omitted. It includes requested selection, resolved pins, schema/watermark, limits,
exact JSON, ordered references, sorted distinct record/artifact entries and scope.
Canonical JSON uses sorted keys, compact separators and ASCII escapes. There is no
capture timestamp, randomness, absolute runtime path or later live-head query.
Committed payloads may themselves contain supplied locators; those are retained
exactly as data. Changing a request, budget, committed value or watermark changes
the identity; identical detached inputs produce identical plan bytes.

## Local classifications and projections

- `locally_decoded`: the supported format/version passes its complete local envelope
  codec, including ordered envelope projections.
- `generic`: no format discriminator; no arbitrary payload key is treated as a typed
  research or runtime field.
- `unsupported`: unknown format or unsupported declared version.
- `malformed_typed`: recognized supported format/version fails its local codec or
  envelope projection.

Every category retains its exact opaque payload, links and attachments, with stable
bounded diagnostics. Local decoding does not certify original `submit_typed`
admission, transitive admission, scientific validity, authenticated authorship or
authority. Navigation does not call or strengthen scientific target admission.

Project/corpus projections reuse the existing pure cross-record dossier/selection
checks on the detached decoded map. Disagreement is a visible projection limitation,
not deleted evidence or proof of historical admission. Initial/current corpus,
context and brief/intake-report displays are guarded by actual kinds and supported
product kinds. Opaque targets keep exact envelope links while typed projections
remain unavailable.
Corpus mapping limitations also qualify every dependent initial/current project
display, independently of record sorting order. The local project codec may still
decode successfully; that classification does not establish its cross-record display.

Companions display supported fields by their real categories: project objectives,
intent, declarations, remaining requirements and `setup_presentation`; corpus
inventories, original mappings and inspection/exposure limits; Source origins,
restrictions, locations, extraction lineage, reading and reported statements;
work-product purpose/authors/entry/build dependencies; context qualifications;
claims, justifications, evidence, reviews and issues. Attributed assessment/issue
disposition is separate from canonical operational/scientific states.

Descriptive provenance is rendered as literal data and never creates reference
semantics, even when its dictionaries exactly resemble valid record references.
Validated envelope references remain linked under Exact outgoing relationships;
supported typed incoming categories and project/home routes provide navigation.

Claim assumptions, supporting justifications, contradictions/objections, reviews
and obligations are distinct. Incoming support comes only from decoded
`Justification.conclusions`, reviews from `Review.candidate_claim`, and objections
from `Issue.affected_records` in the captured set. Other exact relationships remain
separate. A generic edge called support stays generic. Evidence prose is not
interpreted as contradiction, invalid support does not refute a claim, and hyperlink
counts establish no support. Absent incoming records may be outside selection.

## Stable layout and generated link guarantees

Record tokens are `r-` plus the full lowercase SHA-256 of the exact ASCII record ID;
revision directories use positive decimal strings. Tokens are checked for collisions.
Each bundle retains original identity and revision in its companion and manifest.
There are no latest links.

| Captured record | Generated area |
| --- | --- |
| Projects / contexts / corpus | `brief/projects/`, `brief/contexts/`, `brief/seeds/` |
| Sources / claims / reviews | `literature/`, `claims/`, `reviews/` |
| Issues / justifications / evidence | Corresponding `navigation/` indexes |
| Generic decisions | `decisions/`, explicitly generic |
| Other opaque kinds | `navigation/records/<kind>/` |
| Research briefs | `brief/documents/` |
| Intake / reading reports | `reports/intake/`, `reports/reading/` |
| End-of-run reports | `reports/end-of-run/`, or `reports/runs/<run-token>/` when an actual exact run reference exists |
| Branch-associated note/checkpoint, derivation, calculation, notebook, figure | `branches/<branch-token>/{notes,derivations,calculations,notebooks,figures}/<product-token>/<revision>/` |
| Other decoded work products | `navigation/work-products/` |

Each record revision has `README.md` and `envelope.json`; attachments add an
`originals/` collection. Actual branch records support branch directories whose
README and `branch.md` identify all captured exact branch revisions. Generic branch
keys never establish purpose, method, context differences or continuation policy.
A work product has one originating bundle; other relations link there. Only decoded
`end_of_run_report` products are called recorded run reports, retaining their own
identity/revision even under a shared run. Generic run/task/event keys, filenames
and operational states do not establish execution success or continuation readiness.
No empty runtime, tool, policy or optional vault hierarchy is generated.

One physical copy entry is planned per Source original/extraction mapping, corpus
selected-original mapping or work-product file; other attachments retain envelope
artifact ordinal. Corpus mappings retain reached Source restriction declarations
when locally available, while disputed selection mappings remain visibly limited. Flat filenames
are `a-<full-logical-mapping-hash><safe-suffix>`, never supplied directory components.
The key includes record/revision, role and original path/artifact identity. The fixed
suffix allowlist is `.md`, `.txt`, `.tex`, `.pdf`, `.png`, `.jpg`, `.csv`, `.json`,
`.ipynb`; other names become `.bin`. Logical paths, entry designation, original mode
where recorded, media declarations, provenance, restrictions and digest/size remain
in the manifest. Shared objects under different mappings count as separate copies.
Imported README/configuration/script/template names cannot create root files or
active `.obsidian` settings. Archives are never extracted and authored bytes are
never rendered or executed by planning.

Every useful directory has a README with Purpose and scope, Contents, Current work,
Provenance, Use, Dependencies and limitations, and Editing route. Contents links to
explicit files or child READMEs. Non-root indexes link to parent READMEs. The home
and every index identify the exact snapshot in their provenance. The home
page immediately identifies the exact project, snapshot, commit watermark, partial
scope and unverified status, and links available dossier/scientific/Source/work-product/
issue records and remaining decisions. Missing categories are explicit.

Generated properties have fixed YAML keys and JSON-compatible quoted scalar values
for record ID, revision, kind, snapshot and supported exact context/branch pins.
Supplied strings cannot control headings, destinations, HTML or Markdown syntax.
Inline strings escape punctuation/HTML and visibly encode controls/bidi characters;
raw values use indented JSON literal notation preserving whitespace spelling without
active markup. Exact spelling remains in envelope/manifests. URLs are not autolinked,
images are not embedded, and supplied locators do not become destinations or invented
artifact fragments.

Inventory validation reuses portable work-product collision rules and adds generated
prefixes, a 240-byte component ceiling and 1024-byte relative-path ceiling. Duplicate
paths, case/Unicode aliases, file/directory conflicts, traversal, backslashes, absolute
paths and reserved names are rejected. Generated links are inspected from rendered
Markdown, not just a separately maintained link list. Destinations must normalize
inside the complete file inventory; bounded parent traversal is permitted, directory-
only targets and schemes are not. Fragments must exist uniquely in generated Markdown.
Authored internal links are **not** certified, rewritten or resolved.

## Manifest and future materialization boundary

`manifest.json` version `research_pipeline.readable_plan.v1` retains schema/watermark,
selection/resolutions, scope/limitations, limits, exact records and classification,
ordered relationships/page paths, artifact expectations/restrictions/mappings, and
sorted directory/file inventories. Generated file entries have actual generated
SHA-256/size and mode; copy entries explicitly label hashes as expected, not observed.

To avoid a self-hash cycle, `manifest.json` is a reserved descriptor excluded from
its own hashed file list. `plan_id` is SHA-256 of the canonical manifest body with
`plan_id` omitted. The full physical inventory is that list plus the descriptor,
whose actual generated bytes and size are available on `ReadablePlan`. It still
consumes both file and byte budgets. This is not a second mutable metadata store.

Milestone 2 must independently validate this descriptor/ID, protect and verify
selected bytes, enforce destination confinement, prepare privately, publish a complete
generation exclusively to an absent destination, and inspect divergence. None of
those operations is supplied here. Displayed edits have no canonical effect and
require separate supported checkout/import or new record submission.
