# Read-only readable-view capture and preservation planning

The first refresh milestone supplies a bounded observation of an explicitly selected
prior generation and a pure preservation plan. It does **not** create durable
preservation, construct or publish a successor, inspect recovery evidence, import
edits, or manage a current pointer. The entire prior tree remains in place.

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
those decisions belong to the later publication milestone.

## Eventual explicit continuation

An established work-product mapping names the exact historical record/revision and
logical path in its original `logical_key` and `details`. After a later operation has
durably preserved an edit, a caller can explicitly create `checkout_work_product`
output from that historical `checkout_base`, copy the selected preserved bytes into
the corresponding logical path, and call `prepare_work_product_import` with that
**exact revision as `expected_head`**, explicit metadata, selection and attribution.
Review the resulting proposal and separately submit through `submit_typed`.
[Checkout](checkout.md) and [preview/import](work-product-import.md) document those
existing APIs, saved proposals, explicit commit and stale-base conflicts. A changed
canonical head cannot be silently rebased; historical revisions and preserved edited
bytes remain separate evidence. Generated status/index edits require an authored
proposal, and ambiguous files require manual mapping. This milestone does not deliver
durable continuation or automatically import any material.
