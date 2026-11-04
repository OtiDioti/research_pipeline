# Immutable private readable snapshots

Capture a bounded consistent committed metadata selection, derive one deterministic
plan, materialize independently verified protected copies, and inspect that generation
offline. Snapshot capture and snapshot planning never read artifact bytes;
materialization and inspection report separate local observations. The
[readable-view CLI](readable-view-cli.md) exposes these operations with explicit
selection and independent limits; displayed edits are never automatically imported.
[Preserved readable refresh](readable-refresh.md) compares edits and renames against
an independent canonical plan, preserves proposed work and atomically publishes an
associated successor package with read-only offline inspection.

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
limits: SnapshotLimits) -> DetachedSnapshot` is the store capture API.
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
physical object files are unknown to capture/planning: even successful plans say
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

## Manifest reconstruction and verification stages

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

`readable_plan_from_manifest(data: bytes, *, limits: SnapshotLimits) -> ReadablePlan`
is a pure strict decoder in `research_pipeline.view_plan`. It bounds descriptor
length before canonical JSON/depth checks, reconstructs the retained detached
snapshot, reruns the same planner and requires byte-for-byte manifest equality.
Unknown fields, duplicate keys, noncanonical numeric types, altered projections,
paths or generated prose fail. **Every embedded allowance must be no greater than
the corresponding caller allowance**, before reconstruction/rendering. This
conservative rule prevents untrusted descriptors from choosing their own processing
budgets; a small generation with generous retained budgets still requires those
allowances from its inspector.

Manifest `expected_unverified` and `hash_kind=expected` fields continue to describe
capture/planning expectations even in a published tree. They never become an
availability receipt. Successful materialization reports `verified_at_materialization`;
inspection reports current `verified` or `diverged`. Both compare actual bytes with
the expectations. Generated pages remain exactly the canonical planned bytes.

## Protected materialization

Direct imports, with no package re-exports:

```python
from research_pipeline.vault import materialize_readable_view, inspect_readable_view

result = materialize_readable_view(
    store, plan, destination,
    source_root=source_root,
    protected_roots=[backup_root, controller_root, external_git_root],
    max_entries=10000,
)
# Close the store before offline inspection if desired.
inspection = inspect_readable_view(
    destination, limits=limits, max_entries=10000,
    expected_plan_id=result.plan_id,
)
```

`materialize_readable_view(source: RecordStore, plan: ReadablePlan, destination, *,
source_root, protected_roots, max_entries: int) -> MaterializedView` requires an open
store but uses it only to locate its guarded artifact area. It never resolves heads,
reads records or starts a metadata transaction. It validates the supplied plan
against reconstruction, including every generated byte and physical copy entry.
Repeated logical mappings consume distinct physical copies and their full sizes.
File counts, per-file/total bytes and directory inventory are preflighted before
object reads or output construction under the retained `SnapshotLimits`.

`protected_roots` must be an explicit list/tuple, including any additional backup,
control and external Git locations; `[]` explicitly declares none. Source root,
source runtime and executing implementation tree are automatically excluded. The
destination, evidence and payload preparation paths must avoid component overlap
in either direction.
The destination parent must already exist, belong to the effective user and have
exact mode **0700**. Held no-follow descriptors pin every ancestor; symlinks,
parent traversal, non-directories, recognizable runtime/backup/checkout/view/attempt
layouts and portable basename aliases fail closed. Recognizable layouts are checked
by fixed markers without reading their content. Exact or alias siblings—including
files, empty directories, edited prior views and dangling links—are refused intact.
Nonportable sibling names make the selected parent ambiguous and are also refused.
No existing destination is chmodded, adopted or replaced; no ancestors are created.

`max_entries` is a required ordinary positive signed-64-bit integer. It bounds each
complete tree-enumeration pass (files **and** directories) and each destination-parent
collision inspection. Enumeration is incremental, not an unbounded list operation.
An insufficient allowance raises `SnapshotLimitError`; it cannot yield partial success.
File descriptors are retained where required; resource exhaustion fails explicitly.

The API first reserves a random sibling `.readable-view-<32 lowercase hex digits>`
for evidence, then a separate sibling `.readable-generation-<same token>` for the
payload, both under the held destination parent. The token affects neither
snapshot/plan identity nor portable bytes. Both start at 0700; privacy depends on
their required owned 0700 parent and permissions, not hidden names. The evidence
directory is retained at 0700 on success and failure and contains only the exclusive
files `intent.json` (at most 16 KiB), `ready.json` and `published.json` (at most 2 KiB
each) as they are created. The payload is never its child. Control size is bounded
before reservation. Destination/evidence/payload basename equality or portable
aliasing is rejected before reservation. Occupied exact or alias reservation names
are refused intact without adoption, removal or retry. Even empty interrupted
evidence and payload directories cannot be used as destination ancestors.

Files are independently allocated; canonical objects are opened no-follow/nonblocking
and checked as owned read-only regular files with exact sizes, bounded 64 KiB reads,
one EOF probe, SHA-256 and stable bindings/signatures. A legitimate canonical staging
hard link is allowed. Every output is single-link and disjoint from all observed
source and other output inodes. No hard link/reflink, extraction, authored Markdown
parsing, PDF rendering, Python import, notebook execution or program launch is used.

Files finish exactly **0400**, directories including the root exactly **0500**.
Preparation directories start at 0700, with descriptor-only permission changes;
the process-global umask is never changed. Umasks 000, 022 and 077 preserve these
explicit modes. An owner-bit-masking umask that prevents safe acquisition of a newly
created directory fails closed and retains the attempt. There is no unsafe path-chmod
fallback. Output is reread and hashed through guarded inodes, all files and directories
are synchronized, and final bindings/inventory/source checks precede publication.

Publication requires Linux libc/kernel/filesystem support for `renameat2` with
`RENAME_NOREPLACE`, reliable file/directory fsync and the existing POSIX no-follow
facilities. The libc symbol is loaded lazily. There is exactly one no-replace rename,
from the sibling payload basename to the destination basename using the same held
parent descriptor for both arguments. On Linux, moving a directory between parents
requires write permission on the moved directory to update its `..` entry. This
same-parent layout avoids that requirement: the generation root remains 0500
throughout publication, with no temporary restoration of write permission and no
chmod after publication. There is no overwriting fallback, raw syscall, shell call
or retry. A competitor's exact destination wins intact. This rename is the atomic
visibility boundary: a fresh
reader sees absence or a complete generation. Parent/ancestor and moved-root bindings
are rechecked against the original inodes, and the old preparation binding must be
absent. Descendant descriptors stay pinned; only the root's tracked basename changes.
The one parent changed by rename is synchronized before `published.json` is written.
That evidence file and its evidence directory have their own synchronization barriers,
as do intent and ready preparation observations. Post-publication checks and
descriptor-close failures also prevent success.

`MaterializedView` is frozen and retains only `snapshot_id`, `plan_id`,
`manifest_sha256`, absolute string `destination`, absolute string `attempt_path`,
and `verification="verified_at_materialization"`. These are local observations, not
authentication, future availability, scientific authority or controller acceptance.
External ancestors must remain trusted. Same-owner/privileged hostile mutation is
not sandboxed by this API; portable aliases are checked at the final boundary under
that local trust contract, while the kernel independently guarantees exact-name
no-replacement.

## Retained evidence and uncertain acknowledgment

`intent.json` is a strict version-1 observation with format
`research_pipeline.readable_view_attempt`, token, destination basename, required
`generation_name` preparation basename, parent `[dev, inode]`, generation `[dev, inode]`,
snapshot/plan IDs, manifest SHA-256 and an explicit no-auto-replay limitation.
It contains no timestamps or canonical runtime
locators. `ready.json` and `published.json` contain only the generation pair and
snapshot/plan/manifest identities. They are append-only observations, not an
authoritative mutable state machine or acceptance receipts. Parse complete exact
field sets and compare identities before using the table. The evidence-directory
token, intent token and `generation_name=".readable-generation-" + token` must agree
exactly. Before rename, explicitly inspect that sibling preparation path and compare
its inode, plan and manifest with intent; after rename, do the same at the destination.
Filename presence alone is not valid evidence or proof of a successful historical
fsync acknowledgment.

| Retained observations | Honest interpretation and explicit diagnosis |
| --- | --- |
| Evidence directory without payload or durable intent | Interruption between reservations or failure reserving payload; no acknowledged preparation. Inspect both token-associated names explicitly; do not adopt or reuse them. |
| Evidence/payload pair without durable intent | Interruption after payload reservation and before acknowledged intent. The token associates the names but supplies no verified content identity; never adopt or automatically publish. |
| Intent and sibling payload, no ready | Incomplete preparation or interrupted verification. Inspect the recorded sibling; do not publish automatically. |
| Ready and sibling payload, destination absent | Observed ready unpublished payload, subject to checking identities and current contents. No automatic completion/replay. |
| Ready, no sibling payload, destination present, no published | Rename may have completed but acknowledgment was lost. Compare destination generation inode, plan and manifest with intent; inspect bytes. |
| Ready and sibling payload, competitor destination present | A losing publisher retains its complete payload. Compare both bindings and identities; never overwrite the winner or replay automatically. |
| Published and destination matching intent | A publication marker is present; verify the exact destination and current bytes. Present evidence never proves historical barrier success or acknowledgment. |
| Missing/mismatched destination, both bindings claiming the recorded generation, mismatched identities or contradictory evidence | Outcome remains uncertain; do not manufacture a receipt or overwrite/replay. |

Preparation errors identify destination, attempt_path and payload_path, including
failures before durable intent. After an attempted rename, errors identify destination
and attempt_path and explain uncertain publication acknowledgment whenever success
cannot be ruled out. A complete
renamed generation is never described as rolled back, removed or renamed back. Even
failure writing `published.json` can leave a complete destination. Inspection cannot
prove that a historical fsync returned successfully or that the historical rename
occurred; it verifies current content. There is no automatic attempt scan, resume,
cleanup, repair, destination reuse or acceptance reconciliation service.

## Read-only offline inspection and errors

`inspect_readable_view(root, *, limits: SnapshotLimits, max_entries: int,
expected_plan_id: str | None = None) -> ViewInspection` requires no store. It pins
one explicitly chosen root and ancestor chain once. It reads bounded safe
`manifest.json`, reconstructs the canonical plan, optionally checks an independently
retained lowercase SHA-256 plan pin, and compares exact inventory/content/modes.
A missing, unsafe, malformed, over-budget descriptor, unusable root or mismatched
pin raises an error; it never returns a partially verified inventory.

The frozen result has `snapshot_id`, `plan_id`, `manifest_sha256`,
`status` (`verified` or `diverged`) and deterministically sorted immutable
`differences: tuple[ViewDifference, ...]`. Each difference has `relative_path`,
`code` and explanatory `detail` bounded to 240 characters. Stable codes are
`missing`, `extra`, `type`, `mode`, `owner`, `hardlink`, `size`, `digest`, and
`changed_during_inspection`. A rename yields missing old path plus extra new path.
An unexpected directory can be reported as one extra subtree without following it.
Unsafe expected directories are reported without traversing their children.

Owned private regular 0600 edited files are safely readable and report mode and
content differences. Foreign ownership, hard links and unsafe types are reported
without reading them. Actual bytes consume caller bounds. All opened signatures
and bindings, plus bounded directory inventories, are rechecked at the final gate;
an observed race cannot return `verified`. Inspection performs no write, chmod,
repair, metadata access, canonical lookup, subprocess launch or network operation.
An inaccessible or disappeared binding at the final directory guard is reported as
`changed_during_inspection`. Failure to complete final binding verification because
of resource exhaustion, I/O errors or unclassified operational failures raises
`ViewOperationalError`, retaining the original cause even if other differences were
already collected; no partial `ViewInspection` is returned.
It cannot authenticate a coherent hostile-owner rewrite; retain independent plan
pins and exact original metadata for stronger external comparison.

| Error | Meaning |
| --- | --- |
| `ViewLayoutError` | Unsafe/missing/occupied layout or unusable descriptor/root. |
| `ViewIntegrityError` | Bytes/bindings disagree, or independent plan pin mismatches. |
| `ViewOperationalError` | OS/resource/synchronization/close failure; post-rename uncertainty includes both paths. |
| `DomainValidationError` | Malformed caller argument or strict domain field. |
| `SnapshotLimitError` | Caller or retained budget exceeded. |
| `ViewPlanError` | Invalid/noncanonical manifest, projection or supplied plan. |
| `StoreClosedError` | Materialization requires an open source handle. |

The first three derive from `ViewError`; underlying checkout/OS causes remain
chained. Displayed edits have no canonical effect and require separate supported
checkout/import or new record submission. The separate [refresh API](readable-refresh.md) preserves displayed edits; explicit
checkout/preview/import remains separate. Mutable latest pointers and independently
filtered workspaces remain future obligations. Legacy version-1 generated availability
wording describes its original projection and is retained for historical reconstruction.

## Runnable local example

From the candidate root, execute this exact self-contained block with:

```sh
PYTHONPATH=implementation/src python3 -B -c 'from pathlib import Path; text = Path("docs/readable-snapshots.md").read_text(); section = text.split("## Runnable local example\n", 1)[1]; exec(section.split("```python\n", 1)[1].split("```", 1)[0])'
```

It creates external 0700 temporary directories and 0600 supplied inputs, performs
real bounded Source capture, commits a partial dossier and synthetic scientific
relationships, publishes, closes the store and inspects offline. Mixed authored
Markdown/text/TeX/binary and imported configuration remain inert. It follows actual
disk navigation and detects one deliberately edited independent copy, then reopens
the store to establish unchanged canonical bytes and exact historical revisions.
This is engineering demonstration data, not scientific evaluation. The final
permission restoration disposes only this example's temporary directories.

```python
from dataclasses import replace
import json
import os
import posixpath
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
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
from research_pipeline.scientific import (
    ResearchContext, Claim, Evidence, Justification, encode_envelope as context_envelope,
)
from research_pipeline.assessment import (
    Review, Issue, IndependenceDeclaration, SubstantiveAssessment, SupportRouteAssessment,
    encode_envelope as assessment_envelope,
)
from research_pipeline.snapshot import RootSelector, SnapshotSelection, SnapshotLimits
from research_pipeline.view_plan import plan_readable_snapshot
from research_pipeline.vault import materialize_readable_view, inspect_readable_view
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
    parent.chmod(0o700)
    input_root = parent / "input"
    input_root.mkdir(mode=0o700)
    input_root.chmod(0o700)
    for directory in ("notes", ".obsidian"):
        (input_root / directory).mkdir(mode=0o700)
        (input_root / directory).chmod(0o700)
    note = input_root / "notes" / "seed.txt"
    note.write_text("Let f(x)=x on the real numbers. What changes on a restricted domain?\n", encoding="utf-8")
    note.chmod(0o600)
    payloads = {"notes/seed.txt": note.read_bytes(), "copy.txt": note.read_bytes(),
                "native.tex": b"Synthetic TeX $x=x$\n", "native.bin": b"\x00\xffnative\n",
                ".obsidian/app.json": b'{"inert":"configuration"}\n',
                "authored.md": b"# Supplied authored note\nNo scientific validation.\n"}
    for logical, data in payloads.items():
        supplied = input_root / logical
        supplied.write_bytes(data)
        supplied.chmod(0o600)
    root = parent / "runtime"
    saved = parent / "initial.json"
    with RecordStore.create(root) as store:
        initial = Submission("empty-setup", controller,
                             [encode_envelope("project", 1, shell, creator), corpus_envelope("seeds", 1, baseline, creator)],
                             {"project": 0, "seeds": 0})
        saved.write_text(json.dumps(initial.to_dict()), encoding="utf-8")
        saved.chmod(0o600)
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
        metadata["originals"] = []
        selected_files = []
        for index, logical in enumerate(payloads):
            identity = "note" if index == 0 else "original-" + str(index)
            metadata["originals"].append({"artifact_id": identity, "path": logical,
                "media_type": unknown.to_dict(),
                "provenance": replace(provenance, supplied_locator=known(str(input_root / logical))).to_dict()})
            selected_files.append({"artifact_id": identity, "input_path": logical})
        metadata["locations"] = [SourceLocation("question", "note", "section", "Supplied short question", None, None).to_dict()]
        capture = prepare_source_capture(store, input_root,
            selected_files=selected_files, metadata=metadata,
            record_id="capture", revision=1, expected_head=0, submission_id="capture-note",
            record_provenance=creator, submission_provenance=controller, source_root=source_root,
            backup_roots=[], control_roots=[], max_file_bytes=4096, max_total_bytes=32768, max_files=6)
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
            readiness=ReadinessProposal("incomplete_intake", ["Other supplied originals remain uninspected"], actor,
                                        ["question"], relevant, usable),
            supersedes=pin("project", 1, "supersedes", "project"), revision_reason="Record supplied intake dossier", revision_attribution=actor)
        appended = encode_envelope("project", 2, proposed, creator)
        store.submit_typed(Submission("propose-intake", controller, [appended], {"project": 1}))
        assert proposed.initial_corpus.revision == 1 and proposed.current_corpus.revision == 2
        assert appended.operational_status is None and appended.scientific_disposition is None
        assert setup_presentation(proposed) == "setup_incomplete"
        # Generic policy is retained as an opaque declaration, never an operating grant.
        store.submit(Submission("policy-declaration", controller,
            [RecordEnvelope("policy", 1, "decision", {"description": "No authorization supplied"}, creator)], {"policy": 0}))
        claim = Claim("The supplied identity remains to be assessed under restriction", "synthetic question", [], scope,
                      [], [], ["Establish the domain and all prerequisites"])
        observation_bytes = store.put_artifact(b"Synthetic observation, no computation executed.\n")
        evidence = Evidence([observation_bytes], scope, "Declared domain restriction",
            [pin("claim", 1, "target_claim", "claim")], "Supplied description only",
            [pin("capture", 1, "input_record", "source")], [], ["Synthetic example"],
            "Unverified", ["No evaluation performed"], [], "synthetic")
        route = Justification(scope, [], [], "Unverified declared route",
            [pin("claim", 1, "conclusion", "claim")], [pin("evidence", 1, "evidence", "evidence")],
            ["Not a proof or scientific evaluation"])
        native = WorkProductManifest("note", "Synthetic native bundle", "Keep authored bytes inert", ["Synthetic author"],
            None, None, scope, None, [pin("claim", 1, "linked_claim", "claim")],
            [pin("capture", 1, "linked_source", "source")], None, [],
            [WorkProductFile(item.path, item.artifact) for item in captured.originals], "authored.md", ["No execution"])
        independence = IndependenceDeclaration("candidate_aware_audit", "candidate_aware_audit",
                                              [], [], [], [], [], [], ["Synthetic, unauthenticated"])
        assessment = SubstantiveAssessment("under_review", "disputed", [], "unresolved", "unassessed",
            "Scope remains unverified", [], ["Check assumptions"], ["No scientific evaluation"])
        review = Review(pin("claim", 1, "candidate_claim", "claim"),
            pin("context", 1, "target_context", "research_context"), "Synthetic reviewer", independence,
            pin("native", 1, "context_manifest", "work_product_manifest"),
            pin("policy", 1, "authorization_policy", "decision"), [pin("evidence", 1, "reported_evidence", "evidence")],
            assessment, [SupportRouteAssessment(pin("route", 1, "assessed_route", "justification"), "invalid",
                "Declared route has no verified support", [], ["Invalid support does not refute the claim"])],
            ["Resolve the domain"], [], [], "synthetic")
        issue = Issue("Domain is unresolved", [pin("claim", 1, "affected_record", "claim")],
            "The restriction is unspecified", "blocking", "State the domain", "open", "Unverified conditions remain",
            [], [pin("evidence", 1, "supporting_evidence", "evidence")], [], "synthetic")
        science = [context_envelope("claim", 1, claim, creator), context_envelope("evidence", 1, evidence, creator),
                   context_envelope("route", 1, route, creator), document_envelope("native", 1, native, creator),
                   assessment_envelope("review", 1, review, creator), assessment_envelope("issue", 1, issue, creator)]
        store.submit_typed(Submission("science-dossier", controller, science, {r.record_id: 0 for r in science}))
        chosen = SnapshotSelection(RootSelector("project", None),
            [RootSelector(identity, 1) for identity in ("claim", "native", "review", "issue")])
        limits = SnapshotLimits(max_roots=10, max_records=100, max_references=1000,
            max_record_bytes=1_000_000, max_metadata_bytes=10_000_000, max_artifacts=30,
            max_files=1000, max_file_bytes=5_000_000, max_total_bytes=20_000_000)
        snapshot = store.capture_snapshot(chosen, limits=limits)
        plan = plan_readable_snapshot(snapshot)
        canonical_records = {(item["record_id"], item["revision"]): item["envelope_json"] for item in snapshot.records}
        store.submit_typed(Submission("later-claim", controller,
            [context_envelope("claim", 2, replace(claim, statement="Later provisional wording"), creator)], {"claim": 1}))
        destination = parent / "reading"
        publication = materialize_readable_view(store, plan, destination, source_root=source_root,
                                               protected_roots=[], max_entries=4096)
    # The source handle is closed. Inspection performs no canonical lookup.
    assert inspect_readable_view(destination, limits=limits, max_entries=4096,
                                 expected_plan_id=publication.plan_id).status == "verified"
    manifest = json.loads((destination / "manifest.json").read_bytes())
    pages = {item["record_id"]: item["page_path"] for item in manifest["records"]}

    def links(page):
        """Read actual generated Markdown links and assert every destination and heading target exists."""
        text = (destination / page).read_text()
        prose = "\n".join(line for line in text.splitlines() if not line.startswith("    "))
        result = set()
        for link in re.findall(r"\[[^\[\]\n]*\]\(([^)]+)\)", prose):
            path, _, fragment = link.partition("#")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path)) if path else page
            assert (destination / target).is_file()
            if fragment:
                headings = re.findall(r"^#{1,6} (.+)$", (destination / target).read_text(), re.MULTILINE)
                assert fragment in [h.lower().replace(" ", "-").replace("/", "") for h in headings]
            result.add(target)
        return result

    assert pages["claim"] in links("README.md")
    assert pages["native"] in links(pages["claim"])
    assert pages["capture"] in links(pages["native"])
    assert {pages["review"], pages["issue"], pages["route"]} <= links(pages["claim"])
    for file in plan.generated_files:
        assert (destination / file.relative_path).read_bytes() == file.data
        if file.relative_path.endswith(".md"):
            links(file.relative_path)
    originals = [m for m in manifest["mappings"] if m["logical_key"]["record_id"] == "native"]
    for mapping in originals:
        assert mapping["relative_path"] in links(pages["native"])
        assert (destination / mapping["relative_path"]).read_bytes() == payloads[mapping["details"]["original_path"]]
    assert not (destination / ".obsidian").exists()
    edited = destination / originals[0]["relative_path"]
    edited.chmod(0o600)
    edited.write_bytes(b"Local edit, never canonical.\n")
    observed = inspect_readable_view(destination, limits=limits, max_entries=4096, expected_plan_id=publication.plan_id)
    assert observed.status == "diverged" and any(d.code == "digest" for d in observed.differences)
    with RecordStore.open(root) as reopened:
        assert reopened.get_typed_revision("project", 1)[1] == shell
        assert reopened.get_typed_revision("project", 2)[1] == proposed
        saved_request = Submission.from_dict(json.loads(saved.read_bytes()))
        assert reopened.submit_typed(saved_request) == original_receipt
        assert reopened.read_artifact(original.artifact) == note.read_bytes()
        assert reopened.head("claim") == 2
        for (identity, revision), exact_json in canonical_records.items():
            assert reopened.get_revision(identity, revision).to_dict() == json.loads(exact_json)
        for item in captured.originals:
            assert reopened.read_artifact(item.artifact) == payloads[item.path]
    # Example-only disposal: product APIs never repair or clean retained generations.
    for current, directories, _ in os.walk(parent):
        Path(current).chmod(0o700)
        for name in directories:
            (Path(current) / name).chmod(0o700)
```


## Explicit committed-report projections and recovery

The historical v1 planner above remains byte-identical, including its ordinary
work-product interpretation of `end_of_run_report`. Use
`report_capture.prepare_report_view(source, operation_id, *, limits)` for the explicit
`research_pipeline.readable_plan.v2` projection. Its common fields retain the selected
observation's original scientific snapshot/limits. It adds exactly
`selected_report_operation_id` and complete revision-ordered `reports` entries with
`result` and `observation`. Original source/manifest/receipt bindings are retained
separately from the scientific watermark. The materializer public boundary is unchanged.

Reports are exact artifact copies under
`reports/runs/<actual-portable-run-record-id>/<revision>/`, with `report.md`,
`continuation.json`, `source.json` and generated `README.md`. Unsafe actual run
components fail, including device aliases. Home identifies the selected dated
observation and links both report and evidence navigation; it never claims current
live state or permission to continue. Each adjacent navigation page links only that
report's own saved exact records/artifacts. Historical report version 1 bytes remain
unchanged; version 2 adds a fixed adjacent README link. All copies, navigation,
indexes and manifest duplication consume real output budgets. Caller allowances
independently bound complete retained history before object reads; no truncation or
limit substitution is permitted. See the [complete report contract and executed
guide](committed-run-reports.md).

Import `inspect_readable_publication` and `recover_readable_view` from `vault`.
Both accept `(attempt_path, destination, *, expected_plan: ReadablePlan,
limits: SnapshotLimits, source_root, protected_roots, max_entries: int)`.
Retain the exact plan manifest independently before publication. Inspection is
read-only and returns `PublicationInspection(status, snapshot_id, plan_id,
manifest_sha256, verified_payload_path, readiness_observation,
publication_observation, differences, historical_acknowledgment)`; identity and
payload fields may be unavailable. Status is `incomplete_preparation`,
`complete_unpublished`, `published`, `competing_destination`, or `inconsistent`.
Historical acknowledgment is always `not_established`. Strict token-paired siblings,
parent/payload device/inode bindings, canonical controls, marker ordering and bounded
protected inventories are verified. Competitors are not traversed or adopted, even
when equal bytes exist at the destination.

Explicit recovery accepts only the complete exact payload or this attempt's already
published destination. It revalidates bytes, modes, links, ownership, ancestors and
held bindings, synchronizes files/directories and requires checked closes. Missing
ready/publication markers are appended only after verification; existing evidence
is preserved. Complete unpublished output uses the same exclusive no-replace rename.
`MaterializedView.verification="verified_at_recovery"` acknowledges the current
verified state, never a lost historical acknowledgment. Source artifacts, live
metadata and models are unnecessary once the copied output is complete. A failure
after entering rename is uncertain and must be reconciled using the same attempt.

Incomplete preparation cannot be repaired in place. First reconcile the old attempt;
when demonstrably unpublished, retain it and explicitly materialize the original
operation and pinned plan into an absent destination as a distinct replacement
attempt. A new destination never proves an earlier uncertain attempt unpublished.
Unavailable destinations and reservation failures preserve the caller's committed
source/result identity even without complete controls. No automatic retries,
orphan sweeps, destination overwrites, mutable latest pointer, CLI behavior change
or database publication state is introduced.

[ToolAssessment persistence](tool-assessment-persistence.md) adds the explicit
version-one assessment format to local classification. It retains generic,
unsupported, malformed_typed and locally_decoded categories. Classification checks
no target/release pairing or implicit metadata predecessors; navigation still
follows only explicit outgoing links under the supplied SnapshotLimits. A locally
coherent generic-original assessment is inspectable without certification of former
typed admission, authentic actors, permission, qualification or execution.
