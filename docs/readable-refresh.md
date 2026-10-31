# Preserved readable refresh

Refresh preserves direct edits and renames as unsubmitted proposed work and publishes
one associated immutable reading generation. Open and pin `destination/generation`.
The entire prior tree remains untouched. The separate read-only capture and
planned-only APIs below retain their original contracts.

This is local preservation plus a reading generation, not backup, export, a filtered
reviewer workspace, scientific qualification or runtime authorization. No current
pointer, CLI, automatic importer or recovery writer is supplied.

Import directly from `research_pipeline.view_capture` and
`research_pipeline.view_preservation`; there are no package re-exports or CLI changes.

```text
CaptureLimits(
    plan_limits: SnapshotLimits,
    max_entries: int, max_files: int, max_directories: int, max_depth: int,
    max_file_bytes: int, max_total_bytes: int, max_metadata_bytes: int,
    max_diagnostics: int, max_open_descriptors: int,
)
capture_readable_view(prior_view, *, expected_plan: ReadablePlan,
                      source_root, protected_roots,
                      limits: CaptureLimits) -> CapturedReadableView
plan_readable_preservation(capture: CapturedReadableView) -> ReadablePreservationPlan
```

`expected_plan` must be the **full independently retained canonical plan**. It is a
caller assertion of the intended historical base, not authentication. Callers with
independently retained manifest bytes can reconstruct that plan with
`readable_plan_from_manifest(bytes, limits=independently_chosen_snapshot_limits)`.
Capture bounds the supplied immutable inventory and manifest before reconstructing
under `limits.plan_limits`, then requires the entire reconstructed plan to equal
the supplied value. Embedded allowances cannot enlarge these independent limits.
Rehashed but noncanonical generated prose is refused.

There is no store parameter, live-head lookup, database read, object read, provenance
input, identity-only fallback, or caller rename mapping. A later canonical revision
does not change the pinned base. Observed `manifest.json` is **opaque content**.
Missing, changed, corrupt or safely type-substituted controls are diagnosed against
the independent plan; they cannot supply inventory, identity, provenance or budgets.
Unsafe control entries fail capture. Expected control bytes remain separate.

## Bounds and filesystem contract

All arguments to `CaptureLimits` are mandatory ordinary signed-64-bit integers,
except its exact `SnapshotLimits` value. Booleans, floats, nulls and coercions are
rejected. Only file and total bytes may be zero. Nested limits are detached and
revalidated, including at consumption boundaries.

| Allowance | Accounting |
| --- | --- |
| `plan_limits` | Independent canonical plan reconstruction and rendering allowances. |
| `max_files` | Every physical regular file, including `manifest.json` and duplicate byte occurrences. |
| `max_directories` | Every directory, including the root. |
| `max_entries` | Every non-root file/directory; also bounds the explicit source/protected input count. Each enumeration pass independently uses this same total allowance. |
| `max_depth` | Relative path components; the root has depth zero. |
| `max_file_bytes` | Each complete physical file, including control bytes. |
| `max_total_bytes` | Sum of complete physical files. Initial capture and final byte verification each have this ceiling, plus one EOF probe per file per pass. This is not a claim that physical I/O equals retained bytes. |
| `max_metadata_bytes` | Aggregate independent canonical manifest text, canonical capture JSON, canonical preservation JSON and standalone UTF-8 explanation. Escaping, exact paths, group references and all associations count. Source/protected path metadata and temporary enumeration metadata are independently bounded before retention. Arrays reserve each contribution incrementally; exact final serialization is also checked. |
| `max_diagnostics` | Sum of complete comparison, rename-group, missing and target-diagnostic rows, including unchanged comparison rows. Exceeding the allowance fails; evidence is never truncated. |
| `max_open_descriptors` | All descriptors held by capture, including every ancestor, file and directory, plus temporary `scandir(fd)` enumeration descriptors. Checked before acquisition. |

File/directory/count/depth/byte limits apply **independently** to complete expected
and observed inventories. Unexpected subtrees are traversed iteratively. UTF-8 names
have a 240-byte component and 1024-byte relative-path ceiling. Original spellings
are used for opens. Work-product NFKC/casefold aliases are checked across the union
of expected and observed paths, including missing old paths: a case-only or
normalization-equivalent move is a layout conflict. Unsafe components, traversal,
reserved devices and non-scalar names are refused. Other safe Unicode names and
inert `.obsidian` contents are permitted.

`source_root` is explicit and `protected_roots` must be a list or tuple. Callers must
include canonical runtime/object storage, backups, controller state and external
Git administration. Capture has no store handle from which to discover those
boundaries. Containment in either direction is refused, including the executing
implementation tree. Fixed-marker checks reject recognizable runtime, backup,
checkout and attempt ancestors without unbounded ancestor enumeration. Only the
intended prior root's manifest is permitted as a view marker.

The entire ancestor chain and prior root are pinned with no-follow directory
descriptors. External ancestors retain the existing trusted-ancestor boundary:
identity, type, ownership and modes are checked during acquisition and final
verification; unrelated membership changes are allowed. Ancestor size, timestamps
and link count are not comparison gates. Complete signatures apply to the prior
root and every entry inside it during acquisition and final verification.
Inside the tree, directories must be owned, private, readable/searchable, with no
special bits. Files must be owned, private, readable single-link regular files.
Protected `0500`/`0400` generations and owner-edited `0700`/`0600` modes work.
Owner execute bits on a file remain inert and are reported as mode divergence.
Group/world access, special permission bits, foreign ownership, symlinks (including
dangling ones), hardlinked files, FIFOs, sockets and devices are refused. Cross-device
subtrees and repeated directory identities are refused. No chmod grants access.

Stable safe file/directory substitutions are differences. Capture traverses the
actual safe subtree and records all missing or blocked expected descendants.
Disappearance after enumeration or change during open is a conflict. Initial lstat,
opened fstat and final parent-relative bindings must agree. Every opened descriptor
is held until the final gate: all directory memberships/signatures are checked,
every file is reread in chunks of at most 64 KiB against captured bytes, and all
file/directory/ancestor bindings are checked again. This detects equal-byte inode
replacement, growth, truncation, earlier-file edits, mode changes and root/directory
rebinding. All resources must close successfully before a result escapes.

`ViewLayoutError` means unsafe input/layout; `ViewIntegrityError` means detected
mutation or inconsistent detached evidence; `ViewOperationalError` means an I/O,
resource or close failure with a chained cause. EIO, EMFILE, ENFILE and permission
failures cannot become ordinary divergence. `DomainValidationError`,
`SnapshotLimitError` and `ViewPlanError` retain their input, budget and canonical-plan
meanings. Failure yields no partial successful observation or plan.

Ordinary reads may update atime. No content, permissions, paths, canonical records,
objects or receipts are changed, imported, repaired or activated. Capture cannot
lock an editor indefinitely or authenticate a coherent hostile same-owner or
privileged rewrite. A later refresh must recheck the prior tree against this
observation before publication. No publication or historical fsync claim is made.

## Detached capture format, version 1

`CapturedReadableView` exposes `capture_id`, `expected_plan_id`,
`expected_manifest_bytes`, `to_dict()` and `file_bytes(relative_path: str) -> bytes`.
A missing file raises `KeyError`. All observed regular bytes, including unchanged and
empty files, are retained as immutable path/bytes pairs outside JSON. Planning and
byte access remain available after the store, descriptors and even prior paths are
closed or unavailable. This is in-memory retention, **not durable preservation**.

State uses compact sorted-key ASCII JSON, strict ordinary numeric types, exact fields,
no duplicate keys/nonfinite values and no unknown fields or versions. Arrays retain
the orders below. Accessors reconstruct fresh metadata; mutating returned dictionaries
cannot alter retained state. Bypassed frozen assignments are revalidated for schema,
identities, safe types, parentage, duplicate fields, payload sizes/hashes and complete
cross-references. No arbitrary persisted-capture loader is provided.

Detached-state revalidation derives the required external-ancestor count from the
lexically validated absolute path before expanding any prefixes. Both that count
and the retained row count must fit the descriptor capacity (including all observed
files/directories and one temporary enumeration descriptor), and the counts must
agree. Prefixes are then checked incrementally in root-to-parent order. This bounds
allocation even for rehashed, bypass-mutated state; `max_depth` continues to govern
only relative paths inside the observed tree.

The exact top-level fields are:

```text
format, version, capture_id, prior_view, expected_plan_id, expected_snapshot_id,
expected_manifest_sha256, expected_manifest, limits, ancestors, directories, files,
limitations
```

`format` is `research_pipeline.readable_view_capture`, `version` is ordinary integer
`1`, `prior_view` is the lexical absolute path, and `expected_manifest` is the exact
canonical ASCII manifest text. `limits` has exactly the `CaptureLimits` argument
names, with the complete existing `SnapshotLimits` object at `plan_limits`.
`capture_id` is SHA-256 of canonical JSON excluding only `capture_id`. It binds a
local observation and payload hashes, not a timestamp, receipt or authentication.

| Array | Exact row fields and order |
| --- | --- |
| `ancestors` | `{path, device, inode, mode, uid, gid}`; root-to-parent order, excluding the prior root. `mode` is permission bits. |
| `directories` | `{path, mode, signature, entries}`; exact path-sorted, root `path=""`. `entries` is the exact sorted immediate-name array. |
| `files` | `{path, sha256, size, mode, signature}`; exact path-sorted, one row per observed regular file. |
| `limitations` | Fixed ordered declarations of captured-only status, unchanged canonical authority, inert proposed contents, local mutation limits and absence of durable preservation/authentication. |

A signature has exactly `{device, inode, size, mtime_ns, ctime_ns, mode, uid, gid,
nlink}`. Its mode includes type bits; row mode is permission bits. Duplicate mode/size
fields must agree. Atime is omitted because reading may change it. Every non-root
entry has an observed directory parent and every directory's names exactly match
its children. The private payload tuple is sorted by path, with exact one-to-one file
membership. Empty files retain `b""`; missing files have no fabricated payload.

## Identity comparison and preservation-plan format, version 1

Exact paths associate edited content with the **expected occupant of that path**.
This is path-based attribution, not authentication of edited bytes as a historical
revision. Canonical `expected_path` references index the retained manifest's file
roles, directory inventory, `records/page_path` companion and adjacent exact-envelope
relationships, and all `mappings/relative_path` entries. Those original mappings
retain their full `logical_key`, original path, provenance and details. The planner
does not copy a speculative provenance dictionary or infer identity from a title,
filename, YAML property, authored link or reference-shaped supplied data.

Complete directory moves require unique matching relative subtree structure: every
descendant suffix/type/file hash/size must match. Modes are compared separately.
Only absent old directories and observed directories outside expected inventory are
candidates. The root and an empty directory alone do not establish identity. Maximal
non-overlapping matches are selected; contained associations follow exact suffixes.
This can disambiguate duplicate bytes through the complete prior relationship.

Remaining file moves require a unique missing canonical owner and unique unexpected
observation of exact hash/size. All canonical owners and observed occurrences count,
including unchanged copies. Otherwise compact ambiguous groups retain all candidates;
there is no nearest/first/name-based choice or Cartesian candidate expansion. Swapped
or replaced occupied paths retain exact-path comparisons with candidate groups.
Rename-plus-edit without an exact relationship stays `added_unresolved`, together
with missing-target evidence and an explicit manual-mapping explanation. No deletion,
rename or missing target instructs a canonical revision or removal.

`ReadablePreservationPlan` exposes `preservation_plan_id`, `capture_id`, `to_dict()`
and `explanation`. Its private capture and serialized state are detached, and
consumption rederives the deterministic complete schema and cross-references.

The exact top-level fields are:

```text
format, version, preservation_plan_id, capture_id, expected_plan_id, status,
files, directories, comparisons, rename_groups, missing, target_diagnostics,
explanation, limitations
```

`format` is `research_pipeline.readable_preservation_plan`, `version` is ordinary
integer `1`, and `status` is always `planned_only`. `preservation_plan_id` hashes the
canonical document excluding only that ID. All fields below are mandatory, including
explicit nulls. Kind values are `file` or `directory`.

| Array | Exact nested schema and deterministic order |
| --- | --- |
| `files` | `{source_path, preservation_path, sha256, size, reasons}`; preservation-path sorted, reasons sorted. The expected control has null source. All others reference one observed file. Fixed future file mode is **0600**. |
| `directories` | `{source_path, preservation_path, observed_mode, mode, reasons}`; preservation-path sorted, reasons sorted. Synthesized output root/controls use null source/mode; tree directories retain exact observed source path/mode. `mode` is always future **0700**. |
| `comparisons` | `{expected_path, expected_kind, expected_sha256, expected_size, expected_mode, observed_path, observed_kind, observed_sha256, observed_size, observed_mode, codes, association_basis, rename_group}`; one row for each expected path in sorted order, followed by unmatched observed paths in sorted order. Directory hashes/sizes and nonexistent values are null. Codes are sorted. |
| `rename_groups` | `{group_id, basis, expected_paths, observed_paths, ambiguous}`; group-ID sorted, path arrays sorted. `group_id` hashes the other canonical row fields. `ambiguous` is a strict boolean. |
| `missing` | `{expected_path, expected_kind, blocked_ancestor}`; expected-path sorted. Every absent original path is included, even when a move was identified. `blocked_ancestor` is the nearest observed file blocking that path, or null. |
| `target_diagnostics` | `{expected_path, observed_path, preservation_path, rename_group, codes}`; expected-path sorted. Covers missing, moved, type-changed and ambiguous canonical targets. Unresolved paths are null; groups provide exact candidate membership. |

`association_basis` is `exact_path`, `exact_bytes`, `exact_subtree` or `unresolved`.
Group `basis` is `exact_bytes` or `exact_subtree`. `rename_group` is null or a sorted
array of group IDs: an occupied-path swap can reference both its old-byte group and
its observed-byte group. Codes are `content_changed`, `mode_changed`, `missing`,
`type_changed`, `renamed`, `added_unresolved`, `ambiguous`; unchanged rows have `[]`.
File `reasons` use these codes plus `independent_expected_manifest` or
`observed_manifest` for controls. Directory reasons use comparison codes or
`output_root`, `control_evidence`, `required_parent`.

The expected manifest always plans `controls/expected-manifest.json`. A safe observed
manifest always plans its separate exact `controls/observed-manifest.bin`, even when
unchanged. Every other divergent observed file is planned once at `tree/<exact
observed path>`, including mode-only edits, unchanged renames, ambiguous/unresolved
files, additions and files in safely substituted subtrees. Associations do not
multiply copies. Required tree parents, added/moved empty directories and mode-only
directories retain their source paths and modes separately from prospective private
output modes. Missing targets have metadata only.

The explanation uses fixed prose and the existing inert literal JSON renderer for
supplied paths. It identifies old snapshot/plan/capture identities, summarizes changes
and unresolved groups, and states unsubmitted proposed work, planning only, no durable
preservation/successor, no scientific endorsement or policy activation. Fixed
limitations distinguish prior mechanically verified generated navigation from authored
and edited links that are not certified or repaired. No authored Markdown is parsed.

For an unchanged tree there are no divergence codes, missing targets, or divergent
`tree/` copies. Both control copies remain planned. Full capture and consistency gates
still run. This same-plan comparison is not a successful refresh or successor no-op;
the separate refresh API always publishes a distinct package, including for unchanged same-plan calls.

## Explicit continuation

An established work-product mapping names the exact historical record/revision and
logical path in its original `logical_key` and `details`. After refresh has
durably preserved an edit, a caller can explicitly create `checkout_work_product`
output from that historical `checkout_base`, copy the selected preserved bytes into
the corresponding logical path, and call `prepare_work_product_import` with that
**exact revision as `expected_head`**, explicit metadata, selection and attribution.
Review the resulting proposal and separately submit through `submit_typed`.
[Checkout](checkout.md) and [preview/import](work-product-import.md) document those
existing APIs, saved proposals, explicit commit and stale-base conflicts. A changed
canonical head cannot be silently rebased; historical revisions and preserved edited
bytes remain separate evidence. Generated status/index edits require an authored
proposal, and ambiguous files require manual mapping. Refresh never automatically imports any material.

## Complete refresh and offline inspection APIs

Import directly from `research_pipeline.view_refresh`:

```text
RefreshLimits(capture_limits: CaptureLimits, successor_limits: SnapshotLimits,
    max_entries: int, max_files: int, max_directories: int, max_depth: int,
    max_file_bytes: int, max_total_bytes: int, max_metadata_bytes: int,
    max_diagnostics: int, max_open_descriptors: int)
refresh_readable_view(source: RecordStore, prior_view, destination, *,
    expected_plan: ReadablePlan, new_plan: ReadablePlan, source_root,
    protected_roots, limits: RefreshLimits) -> RefreshedReadableView
inspect_readable_refresh(attempt_path, destination, *, source_root,
    protected_roots, limits: RefreshLimits,
    expected_refresh_id: str | None = None) -> RefreshInspection
```

Every allowance is required. Exact types, signed-64-bit bounds and detached nested
limits are revalidated at consumption, including bypass-mutated frozen values.
Only file/total bytes may be zero. Both complete canonical plans are reconstructed
under independently supplied limits before reading the prior tree. The open store
only locates guarded canonical artifact objects; refresh never resolves live heads,
looks up records or opens a metadata transaction. The requested and resolved project
identity must agree across plans. Revisions, selections and outgoing closures may
change and remain visible in exact record mappings. These checks establish local
coherence, not historical admission or authentication.

Same-plan means exact plan-ID equality. It always captures, preserves, verifies and
publishes a distinct package at an absent destination. Unchanged trees have controls
and metadata without divergent tree copies. An occupied destination cannot be reused.

`RefreshedReadableView` is frozen, with fields `refresh_id`, `prior_view`,
`prior_snapshot_id`, `prior_plan_id`, `capture_id`, `preservation_plan_id`,
`successor_snapshot_id`, `successor_plan_id`, `destination`, `successor_path`,
`preservation_path`, `attempt_path`, `same_plan`, and
`verification='verified_at_refresh'`. Paths are lexical absolute strings. Success
requires every barrier, final check and descriptor close to complete.

### Package, modes and identities

The already-existing destination parent must be owned and exactly 0700. Source,
prior, runtime, executing implementation and caller-protected roots are disjoint
from output in both component-containment directions. No caller symlink is resolved.
Portable aliases, unsafe ancestors, ambiguous siblings and reserved refresh basename
prefixes are refused. A completed package's explicitly selected `generation/` can
serve as the next refresh's prior tree.

Token-paired siblings `.readable-refresh-attempt-<32 lowercase hex>` and
`.readable-refresh-package-<same token>` are exclusively reserved. Only the package
is renamed, once, to destination. The attempt remains outside on success and failure.

```text
destination/                     0500
    refresh.json                 0400
    README.md                    0400
    capture.json                 0400
    preservation-plan.json       0400
    preservation/                0700 directories, 0600 files
        controls/expected-manifest.json
        controls/observed-manifest.bin  (when observed)
        tree/<divergent observed paths>
    generation/                  0500 directories, 0400 files
        manifest.json
        README.md
        <complete canonical successor inventory>
```

Every planned preservation row is implemented exactly using the initial captured
immutable bytes, never a later pathname reread. Missing targets have metadata only.
Safe type changes, mode-only edits, renames, unresolved additions and meaningful
empty directories remain represented. Executable and configuration-looking content
is inert non-executable content. Copies have independent single-link inodes, disjoint
from prior files, canonical objects and other outputs; legitimate canonical staging
hardlinks remain permitted. Nothing chmods the prior or an occupied destination.

`capture.json` is the canonical accepted version-1 capture metadata.
`preservation-plan.json` retains its exact `planned_only` status and limitations.
`refresh.json` separately binds completed preservation to the successor. The README
provides the continuation and exact diagnostics without implying the plan became a
receipt. It uses inert literal text and encoded relative links for supplied paths.
Its bytes do not contain refresh_id, avoiding a self-hash cycle.

The accepted version-1 generated renderer and historical manifests are unchanged.
Legacy generated availability wording describes that original projection; this
separate API supplies refresh. Reconstruction is not weakened to rewrite history.

### Exact refresh and attempt schemas

All fields are mandatory, with explicit nulls, ordinary numeric/boolean types,
compact sorted-key ASCII JSON, bounded nesting, deterministic array ordering,
duplicate-key rejection and unknown-field/version rejection. SHA-256 identities
bind canonical bytes, not authority.

`refresh.json` has exactly `format, version, refresh_id, prior, successor, capture,
preservation, same_plan, selection, records, files, directories, descriptor,
limitations`. Format is `research_pipeline.readable_refresh`, version is integer 1,
and refresh_id hashes the canonical document excluding only refresh_id.

| Field | Exact shape |
| --- | --- |
| prior | `{path, snapshot_id, plan_id, manifest_sha256}`; original lexical absolute path, report data only. |
| successor | `{path, snapshot_id, plan_id, manifest_sha256}`; path is `generation`. |
| capture | `{path, capture_id, sha256, size}`; path is `capture.json`. |
| preservation | `{path, plan_path, preservation_plan_id, sha256, size, status}`; `preservation`, `preservation-plan.json`, plan-file hash/size and `unsubmitted_proposed_work`. |
| selection | `{prior_requested, prior_resolutions, successor_requested, successor_resolutions}`; exact independent plan values. |
| records | Sorted by `(record_id, revision)` over both inventories. Each row is `{record_id, revision, prior_page_path, successor_page_path, prior_root_ordinals, successor_root_ordinals}`; missing pages are null and ordinals retain resolution order. |
| files | Complete path-sorted inventory excluding refresh.json: `{path, sha256, size, mode}`. |
| directories | Path-sorted `{path, mode}`, including root `''`. |
| descriptor | `{path:'refresh.json', mode:256, self_excluded:true}`. |
| limitations | Fixed ordered statements of proposed-work status, no import/endorsement/activation, link boundaries, local mutation limits and absence of historical acknowledgment proof. |

The two retained full plan manifests preserve envelope identities, original logical
paths, mappings, provenance and exact relationships. Record mappings do not guess a
single replacement revision or omit historical dependencies.

Intent fields are exactly `format, version, token, destination, package_name,
parent, package, prior_plan_id, successor_plan_id, capture_id, preservation_plan_id,
refresh_id, manifest_sha256, limitations`. Format is
`research_pipeline.readable_refresh_attempt`, version 1. Destination/package_name
are single basenames; parent/package are `[device,inode]` pairs. Intent binds the
precomputed complete refresh.json hash. Fixed limitations prohibit automatic replay,
cleanup and acceptance claims.

Ready/published fields are exactly `format, version, token, package, refresh_id,
manifest_sha256`, with formats `research_pipeline.readable_refresh_ready` and
`research_pipeline.readable_refresh_published`, version 1. The package pair and
identities must match intent. Marker presence alone establishes no completion.

### Outer bounds and barriers

Nested capture accounting is unchanged. Successor limits independently bound new
plan reconstruction and rendering. Outer limits count the complete package plus
all three possible attempt files: repeated physical copies count separately,
including repeated controls. Directory counts include package and attempt roots;
entries count files/directories, excluding only the package root. Package-relative
paths have explicit 4096-byte and max_depth ceilings and 240-byte components.

The exact serialized-control metadata aggregate includes the four top-level
controls (`capture.json`, `preservation-plan.json`, `refresh.json`, `README.md`),
the successor manifest, the independent expected-manifest copy, the actual opaque
observed-manifest copy when present, and all three possible attempt files. The
expected manifest embedded in capture JSON is already charged in that JSON's
length. A missing or directory-substituted observed manifest adds no control-file
bytes; preserved authored files do not become controls because of a `.json` suffix.
Refresh reserves evidence using maximum-width device/inode integers before output
creation; inspection uses the actual intent and corresponding possible markers.
Temporary traversal-name/diagnostic accounting has a separate `max_metadata_bytes` ceiling
and is not added to this serialized-control aggregate.

Diagnostics count comparisons, groups, missing/target rows and
refresh mappings without truncation. Known output descriptor needs are reserved
alongside prior capture descriptors; temporary enumeration/read/write descriptors
also count. Known inventories/control sizes and integer placeholders are preflighted
before reservation/object reads. During capture, outer reservations admit known
successor copies, fixed controls and roots, then each known preservation obligation
after safe stat and nested checks but before its payload is opened/read. Added,
type-substituted, size/mode-changed files and the observed manifest consume their
actual bytes and prefixed preservation paths; new/changed directories and shared
parents count once. Exact-path size/mode matches need comparison reads under the
independent capture limits. A divergent hash admits its copy before retaining the
file result. Complete subtree and duplicate associations require the full tree;
their additional copies are admitted with deterministic planning before output
metadata construction. Final physical-inventory preflight remains the exact
completed-package check. Unchanged comparison payloads do not all count as output
copies, and nested allowances are not replaced by minima of outer limits.

Offline inspection checks `capture.json`'s stat size against the caller's independent
capture metadata allowance before opening/reading it, then checks capture text plus
its reconstructed expected manifest and planning metadata. Insufficient independent
allowances raise `SnapshotLimitError`, including for unfinished preparations; they
do not classify valid evidence as corrupt.
Each parent collision scan has an independent max_entries ceiling. Each verification
pass rereads declared bounded bytes plus one EOF probe per file; the limits are not
an assertion of a single physical-read budget. Stored budgets cannot enlarge offline
caller's independently supplied limits.

Intent is written and synchronized before payload files, then attempt, package and
parent are synchronized. Preservation and successor files are independently written,
fsynced and read back; directories synchronize bottom-up. Ready is appended only
after complete verification and synchronization. After the final mutation seam,
refresh rechecks the *original* prior observation, output bytes/inventories/bindings,
canonical bindings, evidence and destination absence/aliases. It never recaptures a
later tree as a replacement observation.

One same-parent `renameat2(RENAME_NOREPLACE)` publishes the package. No fallback,
overwrite retry or cleanup occurs. Only the moved root binding changes; descendants
remain pinned and the preparation binding must disappear. Parent fsync precedes
published observation; that file and attempt directory are fsynced. Final prior,
source, output and evidence checks and all closes precede return.
Every writer verification concludes, after both preservation/control hashing and
the entire successor streaming pass, with bounded exact package directory
membership, prescribed modes and original parent-relative bindings. Enumeration
ends with another binding/ownership guard and exact package-mode sweep. Held file
descriptors alone cannot establish that their parent directories remain reachable
through the published path.

Any prepublication failure retains partial work and identifies destination,
attempt_path and package_path, even without completed intent. After attempted rename,
a failure that may leave visible output reports **uncertain acknowledgment**, with
paths and chained cause. It never renames back, repairs, replays or promises rollback.
EIO, permissions, descriptor/resource exhaustion and close errors remain operational.
Prior changes are integrity conflicts and the mutator's final tree remains intact.
There is an unavoidable interval after the final observation; no universal editor
lock or defense against coherent same-owner/privileged rewriting is promised.
Offline final verification compares full atime-free file signatures and pathname
bindings after each hash and again after all hashes. It concludes with exact bounded
directory memberships and original directory/file bindings. Edits to already-read
chunks, earlier verified files, or package memberships during that observation
invalidate every verified path. External ancestors retain binding/ownership/mode
checks; unrelated sibling activity is not a package mutation. These observations
and successful closes do not extend the guarantee beyond the observation interval.

### Read-only inspection matrix

Inspection needs neither store, prior tree nor source objects. It parses the caller's
attempt basename strictly and derives only the fixed token-paired preparation name.
The old prior path is never opened. Pinned no-follow traversal, bounded byte checks,
independent canonical reconstruction, metadata-only capture validation and exact
preservation/report recomputation are required. Unchanged prior payloads are not
fabricated. Coherently rehashed preservation omissions are rejected.

An unfinished private preparation can contain no controls, only preservation
controls, or capture before the preservation plan. A present preservation plan
requires the earlier capture and must equal its deterministic plan. A present
refresh descriptor requires strict schema, self-identity, intent associations,
inventory references and matching bytes/modes for files already written. The
successor manifest may still be unwritten at that stage. Each available canonical
manifest is independently reconstructed; once both plans and capture are available,
all present deterministic controls and report bytes are recomputed and compared.
Opaque observed-manifest evidence is hashed and preserved, never used as authority.
An unwritten control differs from a present directory at its fixed file location.
Directories occupying `capture.json`, `preservation-plan.json`, `refresh.json`,
`README.md`, `generation/manifest.json`,
`preservation/controls/expected-manifest.json`, or
`preservation/controls/observed-manifest.bin` make even an unfinished preparation
`inconsistent`, with null identity and verified paths. Unsafe directories still
raise layout errors; safe substitutions are rejected before traversing descendants.
These are exact package-relative locations: similarly named directories captured
from the prior view under `preservation/tree` remain inert proposed content.

| Current observations | Status and paths |
| --- | --- |
| Empty reservations or unfinished preparation before readiness | `incomplete_preparation`; no verified successor. Unwritten files are permitted; every present control must satisfy its schema and available intent/plan associations. |
| Complete matching preparation, destination absent, with or without ready | `complete_unpublished`; verified preparation generation. |
| Complete matching destination, preparation absent, with or without published | `published`; verified destination generation. |
| Recorded preparation remains, unrelated destination exists | `competing_destination`; a complete losing preparation may be identified; competitor is not traversed. |
| Missing/conflicting identities, malformed controls, impossible ordering, changed bytes or contradictory cross-references | `inconsistent`; no claimed complete successor. |

`RefreshInspection` is frozen with `status, refresh_id, verified_package_path,
successor_path, preservation_path, readiness_observation, publication_observation,
historical_acknowledgment, differences`. Unestablished identity/path fields are null.
Observations are `present` or `absent`; historical_acknowledgment is always
`not_established`. Differences are bounded deterministic `ViewDifference` tuples.
An independent expected_refresh_id mismatch raises ViewIntegrityError. Unsafe
layouts raise ViewLayoutError, exceeded allowances SnapshotLimitError, and actual
I/O/resource/close failures ViewOperationalError. No inspection writes, chmods,
completes preparation or authorizes replay. A valid published observation records
what the writer claimed; its current bytes cannot prove historical fsync return.

## Runnable preservation and explicit import example

Run this exact self-contained block in a fresh bytecode-disabled interpreter with
`PYTHONPATH=implementation/src`. It uses synthetic supplied-local provenance and
private `/tmp` inputs, never test fixtures or real scientific data. Cleanup only
restores modes in this example's disposable tree. No scientific endorsement follows.

```python
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
from urllib.parse import unquote

import research_pipeline
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.store import RecordStore, RevisionConflictError
from research_pipeline.source import (
    DeclaredText, Source, SourceDeclaration, SourceRestrictions, SourceProvenance,
    SourceReading, decode_envelope as decode_source,
)
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.work_product import WorkProductManifest, WorkProductFile, encode_envelope
from research_pipeline.checkout import checkout_work_product
from research_pipeline.work_product_import import (
    prepare_work_product_import, dumps_prepared_submission, loads_prepared_submission,
)
from research_pipeline.snapshot import RootSelector, SnapshotSelection, SnapshotLimits
from research_pipeline.view_plan import plan_readable_snapshot, verify_plan_links
from research_pipeline.vault import materialize_readable_view
from research_pipeline.view_capture import CaptureLimits
from research_pipeline.view_refresh import RefreshLimits, refresh_readable_view, inspect_readable_refresh


def known(text):
    """Declare supplied literal text, without authenticating its author."""
    return DeclaredText(text, None)


def tables(runtime):
    """Snapshot application metadata to distinguish refresh/preview from explicit submission."""
    with sqlite3.connect(runtime / "metadata.sqlite3") as db:
        names = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return {name: db.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall() for (name,) in names.fetchall()}


def save_proposal(path, submission):
    """Exclusively save the exact codec proposal and synchronize file and containing directory."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(dumps_prepared_submission(submission))
        stream.flush()
        os.fsync(stream.fileno())
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return loads_prepared_submission(path.read_bytes())


source_root = Path(research_pipeline.__file__).resolve().parents[3]
author = CreationProvenance("synthetic-author", "2026-10-31T12:00:00Z", {"qualification": "none"})
editor = CreationProvenance("declared-editor", "2026-10-31T13:00:00Z", {"reason": "explicit chosen edit"})
unknown = DeclaredText(None, "Not supplied")
snapshot_limits = SnapshotLimits(16, 128, 1024, 1_000_000, 20_000_000, 64, 2048, 10_000_000, 50_000_000)
capture_limits = CaptureLimits(snapshot_limits, 4096, 2048, 2048, 32, 10_000_000, 50_000_000, 50_000_000, 10000, 4096)
refresh_limits = RefreshLimits(capture_limits, snapshot_limits, 10000, 5000, 5000, 40,
                               50_000_000, 200_000_000, 200_000_000, 20000, 4096)
with TemporaryDirectory(prefix="readable-refresh-example-", dir="/tmp") as temporary:
    parent = Path(temporary)
    parent.chmod(0o700)
    try:
        inputs = parent / "inputs"
        inputs.mkdir(mode=0o700)
        inputs.chmod(0o700)
        supplied = inputs / "note.md"
        supplied.write_bytes(b"# Synthetic authored note\n[original link](missing.md)\n")
        supplied.chmod(0o600)
        runtime = parent / "runtime"
        with RecordStore.create(runtime) as store:
            provenance = SourceProvenance("supplied_local", known("Synthetic supplier"), unknown,
                known(str(supplied)), unknown, unknown, "available", [])
            declaration = SourceDeclaration("unknown", "No permission or endorsement inferred")
            source = Source("synthetic-note", unknown, unknown, known("Supplied note"), [unknown], provenance,
                SourceRestrictions(declaration, declaration, declaration, declaration), [], [], [],
                SourceReading("uninspected", [], None, "unreported", [], unknown, []), [], [], None,
                ["Engineering example only"])
            template = source.to_dict()
            for key in ("format", "version", "kind"):
                del template[key]
            template["originals"] = [dict(artifact_id="note", path="note.md", media_type=unknown.to_dict(),
                                           provenance=provenance.to_dict())]
            proposed_source = prepare_source_capture(store, inputs,
                selected_files=[dict(artifact_id="note", input_path="note.md")], metadata=template,
                record_id="source", revision=1, expected_head=0, submission_id="capture-source",
                record_provenance=author, submission_provenance=author, source_root=source_root,
                backup_roots=[], control_roots=[], max_file_bytes=4096, max_total_bytes=4096, max_files=1)
            store.submit_typed(proposed_source.submission)
            original = decode_source(proposed_source.submission.records[0]).originals[0].artifact
            product = WorkProductManifest("note", "Synthetic bundle", "Exercise explicit continuation", ["Declared author"],
                None, None, None, None, [], [RecordReference("source", 1, "linked_source", "source")], None, [],
                [WorkProductFile("note.md", original)], "note.md", ["No scientific evaluation"])
            bundle = encode_envelope("bundle", 1, product, author)
            project = RecordEnvelope("project", 1, "project", {"purpose": "Synthetic engineering"}, author,
                record_references=[RecordReference("bundle", 1, "work_product", "work_product_manifest")])
            store.submit_typed(Submission("initial-bundle", author, [bundle], {"bundle": 0}))
            store.submit(Submission("initial-project", author, [project], {"project": 0}))
            selection = SnapshotSelection(RootSelector("project", None), ())
            old_plan = plan_readable_snapshot(store.capture_snapshot(selection, limits=snapshot_limits))
            prior = parent / "prior"
            materialize_readable_view(store, old_plan, prior, source_root=source_root, protected_roots=[], max_entries=4096)
            mapping = next(m for m in old_plan.to_dict()["mappings"]
                           if m["logical_key"]["record_id"] == "bundle")
            logical_path = mapping["logical_key"]["original_path"]
            authored = prior / mapping["relative_path"]
            authored.chmod(0o600)
            chosen_edit = b"# Explicit preserved correction\nNo scientific endorsement.\n"
            authored.write_bytes(chosen_edit)
            page = prior / old_plan.to_dict()["records"][0]["page_path"]
            page.chmod(0o600)
            page.write_bytes(b"---\nstatus: displayed-only\n---\nHuman generated-page edit\n")
            # A uniquely identifiable unchanged generated file is renamed separately.
            prior.chmod(0o700)
            (prior / "README.md").rename(prior / "human-renamed-home.md")
            project2 = RecordEnvelope("project", 2, "project", {"purpose": "Later committed description"}, author,
                                     record_references=project.record_references)
            store.submit(Submission("advance-project", author, [project2], {"project": 1}))
            new_plan = plan_readable_snapshot(store.capture_snapshot(selection, limits=snapshot_limits))
            before = tables(runtime)
            refreshed = refresh_readable_view(store, prior, parent / "refreshed", expected_plan=old_plan,
                new_plan=new_plan, source_root=source_root, protected_roots=[], limits=refresh_limits)
            assert tables(runtime) == before
            assert authored.read_bytes() == chosen_edit
            assert (prior / "human-renamed-home.md").exists()
            verify_plan_links(new_plan)
            generation = Path(refreshed.successor_path)
            for generated in new_plan.generated_files:
                if generated.relative_path.endswith(".md"):
                    text = (generation / generated.relative_path).read_text()
                    for target in re.findall(r"\]\(([^)]+)\)", text):
                        relative = unquote(target.split("#", 1)[0])
                        assert (generation / generated.relative_path).parent.joinpath(relative).is_file()
            preserved = Path(refreshed.preservation_path) / "tree" / mapping["relative_path"]
            assert preserved.read_bytes() == chosen_edit
            assert (generation / mapping["relative_path"]).read_bytes() == store.read_artifact(original)
        inspected = inspect_readable_refresh(refreshed.attempt_path, refreshed.destination, source_root=source_root,
            protected_roots=[runtime], limits=refresh_limits, expected_refresh_id=refreshed.refresh_id)
        assert inspected.status == "published" and inspected.historical_acknowledgment == "not_established"
        with RecordStore.open(runtime) as store:
            base = RecordReference("bundle", 1, "checkout_base", "work_product_manifest")
            draft = parent / "independent-draft"
            options = dict(source_root=source_root, protected_roots=[], max_file_bytes=10000,
                           max_total_bytes=100000, max_files=10, max_descriptor_bytes=100000)
            checkout_work_product(store, base, draft, **options)
            (draft / logical_path).write_bytes(preserved.read_bytes())
            metadata = product.to_dict()
            for key in ("format", "version", "kind", "supersedes", "files"):
                del metadata[key]
            metadata["authors"] = ["Declared editor"]
            before = tables(runtime)
            prepared = prepare_work_product_import(store, base, draft, expected_head=1, metadata=metadata,
                selected_paths=[logical_path], submission_id="explicit-preserved-import", record_provenance=editor,
                submission_provenance=author, max_inventory_entries=100, **options)
            assert tables(runtime) == before
            assert prepared.summary["paths"][0]["status"] == "changed"
            # A separate saved proposal tests a commit race after successful preview.
            competing_preview = prepare_work_product_import(store, base, draft, expected_head=1, metadata=metadata,
                selected_paths=[logical_path], submission_id="stale-after-preview", record_provenance=editor,
                submission_provenance=author, max_inventory_entries=100, **options)
            saved = save_proposal(parent / "chosen.proposal.json", prepared.submission)
            stale = save_proposal(parent / "stale.proposal.json", competing_preview.submission)
            store.submit_typed(saved)  # The explicit separate commit; refresh never does this.
            try:
                store.submit_typed(stale)
            except RevisionConflictError:
                pass
            else:
                raise AssertionError("stale post-preview proposal must conflict")
            try:
                prepare_work_product_import(store, base, draft, expected_head=1, metadata=metadata,
                    selected_paths=[logical_path], submission_id="stale-at-preview", record_provenance=editor,
                    submission_provenance=author, max_inventory_entries=100, **options)
            except RevisionConflictError:
                pass
            else:
                raise AssertionError("stale historical checkout must conflict")
            assert store.get_revision("bundle", 1) == bundle
            assert store.read_artifact(original) == supplied.read_bytes()
            assert store.read_artifact(store.get_typed_revision("bundle", 2)[1].files[0].artifact) == chosen_edit
            assert preserved.read_bytes() == chosen_edit and authored.read_bytes() == chosen_edit
    finally:
        for current, directories, files in os.walk(parent):
            os.chmod(current, 0o700)  # Disposable example cleanup, outside refresh.
```
