# Foundation architecture

The current foundation establishes a local Python package and honest development
feedback, validated domain envelopes, immutable local artifacts and atomic
SQLite revision submissions. It implements no research execution, models, scientific verification, vault generation
or provider integration. Exact revision history, submission receipts and audit
events persist locally.
A separate synthetic development fixture illustrates scoped records as local JSON
data. Specification v1.4 distinguishes engineering readiness from scientific
validation; these components complete neither overall gate. Acceptance and
integration are controller and coordinator decisions, not CLI or validator claims.

## Package and interface

`implementation/pyproject.toml` defines the `theoretical-research-pipeline`
distribution for Python 3.11+, with explicit `src` discovery restricted to
`research_pipeline`. Package initialization contains only identity documentation
and a literal version. Tests compare that version against TOML metadata; importing
the package does not read installed distribution or repository metadata.

`research_pipeline.__main__` delegates to a focused argparse CLI for help/version,
exact record and original-receipt inspection, historical work-product checkout and
offline original-descriptor inspection, bounded saved preparation, offline proposal
review and separate explicit submission. `cli_controls` enforces strict bounded
configuration and authored request reads; `cli_inspection` reuses bounded metadata
and checkout codecs. `cli_proposals` binds exact proposal/summary bytes to a strict
fixed package inventory, verifies saved comparisons and reuses checkout's exclusive
private-destination/incomplete-marker protocol. Marker removal is logical publication,
not atomic visibility of the directory. Saved inputs are synchronized, reverified
and closed before the unchanged typed submission/reconciliation boundary.
No arguments prints help; unknown or abbreviated arguments exit with status 2.
The [local CLI guide](local-cli.md) defines paths, limits, output and recovery.
Library preview/import APIs remain valid; CLI submission requires the coherent saved
package. Research execution is unavailable. The
package has no third-party runtime dependencies. Setuptools is solely
build tooling, and no installation is needed for the documented source commands.
Linux is the initially verified platform. See the [implementation guide](../implementation/README.md)
for exact commands and environment requirements.

## Durable records and artifacts

`research_pipeline.domain` provides frozen `CreationProvenance`, `RecordReference`,
`ArtifactReference`, `RecordEnvelope`, `Submission`, `SubmissionReceipt` and
`AuditEvent` values with runtime validation and detached
serialization. Private canonical JSON snapshots isolate mutable content and details.
Twenty common envelope kinds are supported in schema 2; generic envelopes retain arbitrary
strict JSON content. Task operational state and provisional claim disposition
are independent.

`research_pipeline.scientific` adds pure frozen contexts, claims, justifications
and evidence with an explicit version-1 format, strict codecs and exact ordered
envelope-link coherence. It depends on domain validation only, without store,
backup or fixture imports. See [typed content](typed-content.md) for required
fields, local assumptions, conjunctive premises and artifact-role boundaries.
`research_pipeline.assessment` supplies pure frozen Review/Issue values with a
distinct version-1 format, independent reported dimensions and exact ordered links.
Its declarations certify neither independence, execution nor authority.
`research_pipeline.work_product` supplies pure immutable multi-file manifests with
portable logical paths, conservative NFKC/casefold alias rejection and explicit
attribution. It reuses domain/scientific/assessment validation primitives without
filesystem access. See [work products](work-products.md) for exact wire contracts
and optional immediate-predecessor supersession.
`research_pipeline.checkout` owns bounded filesystem materialization of exact
committed manifests. It closes a metadata-only read transaction before capture,
keeps directory-relative no-follow bindings, verifies independent private writable
copies, and publishes through a durable incomplete marker. Its local descriptor
retains the original envelope but is untrusted; read-only inspection neither
authenticates attribution nor certifies edited product bytes. Explicit caller source
and backup/control exclusions supplement the internally excluded runtime. Failures
retain incomplete output or report uncertain acknowledgment after marker removal.
See [checkout](checkout.md) for limits, lifecycle and an executed example.
`research_pipeline.work_product_import` reuses those bindings for bounded edited-file
capture and compares the descriptor with a caller-pinned canonical base. Its narrow
store preview helper checks typed admission in a read snapshot without metadata writes.
Frozen serialized proposals are committed separately through `submit_typed`; its
original-ID reconciliation order is unchanged, including after head advancement or
object loss. CLI summary recomputation uses the original checkout and original
submission provenance saved with the exact proposal; digests are internal bindings,
not authentication. Offline inspection makes no historical durability claim and
never repairs retained evidence. Postpublication/postcommit close/output failures
retain uncertainty with original-ID receipt/retry guidance. See [preview and explicit import](work-product-import.md).
`RecordStore.submit_typed` selects the scientific, assessment, work-product, Source, corpus, project or ToolRelease codec
explicitly and decodes every member locally, admitting mixed eleven-kind batches. For a new canonical
request, it resolves constrained exact target closure inside the existing serialized
write transaction after submission-ID reconciliation. Historical target checks read metadata; public exact reads verify
direct artifacts. The traversal follows explicit per-kind constrained roles;
Review manifest/policy/ToolExecution, Issue affected-record and Evidence input roles
check only exact existence and declared kind. Manifest context/linked-claim/supersedes
roles are constrained typed edges; task/branch/run/source/build-dependency roles
remain shallow. [Source](sources.md) adds bounded capture declarations and typed
predecessor/work identity continuity; its report edges require a reading-report
manifest on every incoming edge. Related sources and reported executions stay
shallow. Legacy generic source content remains supported. [Corpus inventories](corpus.md)
constrain all projected predecessor/Source/location edges, validate each selected
original and location occurrence, and check full snapshot history to baseline.
Corpus history has no generic baseline transition; local IDs and attributed
narrative declarations add no traversal edges. [Project intake](project-intake.md) constrains
all project pins, validates each historical dossier against its own current corpus,
and checks each incoming document role independently of cached target resolution. [Tool releases](tool-releases.md) add constrained implementation Source/manifest,
child Tool, Evidence and Issue roles; provenance, qualification and build dependencies
remain shallow. Tool history expands exact predecessors back to revision 1 in the
same cached worklist, checking every historical constrained closure. No transitive
artifact verification is added. Every submitted Review's assessed route
must conclude its exact candidate, without equating their contexts. See the
[complete traversal contract](attributed-assessments.md#durable-api-and-exact-traversal).
`get_typed_revision` returns the detached envelope and typed value without recursively
establishing admission. Original-ID reconciliation precedes route membership and
all current availability/head checks; local decoding still precedes reconciliation.
Generic `submit` remains a trusted persistence API, not a scientific admission gate.
Neither structured descriptions nor coherent links establish support. Supported
APIs append historical revisions/links; other handles may advance heads, never
rewrite exact targets. External mutation still requires trusted-owner protection.

`research_pipeline.artifacts` owns an explicitly selected outside-source runtime
area. It validates private directories, stages bytes, publishes read-only files
with atomic no-overwrite hard links, and verifies size/hash on reads and reuse.
File and directory synchronization precede successful publication acknowledgment.
Operation-scoped descriptors, no-follow traversal and nonblocking object opens
bound unsafe filesystem handling. Failure can retain objects or staging entries;
the API does not sweep or repair them.

`research_pipeline.store` uses the artifact layout plus a private mode-0600
`metadata.sqlite3`. It creates schema2 by default or explicit schema3/4/5/6/7 in absent roots and gates opening on the fixed
version-1–7 registry through a read-only immutable preflight, before allowing normal
SQLite rollback-journal recovery. This preflight is solely for fixed schema/version,
never live data or integrity conclusions. Operational connections require DELETE
journaling, EXTRA synchronization, foreign keys and a 5000 ms busy timeout.

`research_pipeline.schema` owns a fixed seven-entry DDL/kind/backup-format registry
and pure manifest/history validation, depending only on domain values and the
standard library. It owns no SQLite connections or filesystem work. Schema 1's
exact five-kind DDL remains supported; schema 2 extends the kind checks and state
trigger and adds a singleton administrative history table, empty on fresh creation.
Operational connections validate administrative rows after journal recovery.
Explicit restore-time consecutive v1→v2→v3→v4→v5→v6→v7 migration lives only in `backup.py`, transforming a
verified private copy transactionally under the existing incomplete marker.
Store creation/opening and generic/typed submission do not migrate. See [version contracts](durable-records.md)
for kind mappings and [backup pairs](backups.md) for exact-copy verification.

Explicit `BEGIN IMMEDIATE` transactions compare relevant expected heads and append
revisions, exact ordered links, artifact registrations, submission identity and one
attributed audit event atomically. Whole-batch indexing resolves forward, self and
cyclic descriptive references. Historical links always retain their exact targets.
Canonical request text and a versioned SHA-256 fingerprint implement durable
idempotency before head checks: exact retries return the original persisted receipt.
Artifacts are verified and synchronized before metadata writes. Compound reads use
consistent snapshots; revision/history exposure checks directly attached bytes.
Receipts, heads, audit events and duplicate responses are metadata-only, remaining
useful for commit reconciliation even after later object damage.

These modules do not depend on `fixtures`. Imports remain inert, with no new dependencies. The local CLI delegates to these
existing contracts without adding a generic submission or execution endpoint. The [durable contract and runnable example](durable-records.md)
give exact APIs, errors, ordering/fingerprint semantics, trusted-owner assumptions,
retained-orphan behavior and acknowledgment recovery by original submission ID.
Real subprocess exits exercise hot-journal rollback and post-commit receipt recovery.
Remaining typed payloads and state machines, positive scientific
eligibility/promotion, worker isolation, leases/fencing, general migrations,
periodic scheduling, distributed execution and research execution remain
unsupported. Schema3 adds controller-private immutable allocation and reservation accounting
with cumulative usage, explicit settlement, sticky breaches and exact operation retries;
it does not implement execution. This slice does not
complete overall M0-E, M0-S, M1, D02 or scientific validation.

## Development validation

`implementation/scripts/validate.py` is development tooling outside the runtime
package. Its guarded entry point derives the candidate root from the script's
resolved location and offers no alternate-root or bypass option. An internal
`run_validation(root, stream)` seam supports disposable fixture testing.

The validator reports read-only Git HEAD context, or explicitly reports unavailable
revision information with its reason. It checks sorted root entries, rejecting all
root symlinks (including `.git` and dangling links) and unsupported special files.
Real directories and regular files with the exact `.md` suffix are allowed.
A regular `.git` file is allowed only as a single nonempty `gitdir: <path>` pointer
whose target directory exists and is accepted by `git rev-parse --resolve-git-dir`.
Relative targets resolve against the candidate root. A normal `.git` directory is
allowed. Required root documents are non-symlink, nonempty UTF-8 regular files and
are never rewritten. Git is a development dependency, not part of the scientific
runtime.

Before importing candidate code the validator disables bytecode writes and prepends
the candidate `implementation/src` and `implementation` paths. It verifies package
origin, then uses a fresh unittest loader with `test_*.py` discovery and the explicit
implementation top-level directory. Discovery problems fail with diagnostics.
The verbosity-2 runner retains tracebacks and reports discovered cases, tests run,
successful cases, skips, expected failures, failures, errors, and unexpected
successes. A result subclass counts `addSuccess` calls so failed subtests and
expected failures cannot inflate positive coverage. Success requires valid layout
and origin, clean nonempty discovery, a successful suite, and at least one real
successful case. There is no baseline exemption.

## Test isolation and evidence limits

CLI tests run fresh interpreters with explicit candidate-first `PYTHONPATH`, `-B`,
and temporary working directories. They check help, version, usage errors, package
origin even beside a competing package, and observed import behavior under guards
for writes, processes, and network operations. Reads remain permitted; these guards
are focused regression checks, not a security sandbox.

Validator tests load the real script in fresh subprocesses and inject tiny disposable
roots. They never validate the real complete suite recursively. Separate processes
avoid cached `tests` or `research_pipeline` modules contaminating discovery. Fixtures
exercise both meaningful passing bodies and rejected suite/layout cases, including
Git administration assembled without commits or real worktree changes. Snapshots
compare fixture bytes and entries before and after validation. Python subprocesses
use `-B` and `PYTHONDONTWRITEBYTECODE=1`.

The permanent validator and direct unittest command give development evidence.
The controller separately owns the frozen bootstrap check, exact-candidate validation,
and review. Unit results alone do not establish integration or scientific capability.
Future research runtime components remain defined by the preserved
[project specification](../project_description.md), outside this foundation.

## Synthetic development fixture

`research_pipeline.fixtures` reads source-relative
`implementation/evaluations/harmonic_quartic_v1.json` only when explicitly called.
It validates a narrow, versioned paper contract: provenance, exact typed references,
obligations and expected scenario relationships. It does not assess scientific
truth or execute the scenario. Import is inert; loading returns independent mutable
trees without writes, downloads, installed metadata or a cache. The package
initializer remains unchanged; the local CLI exposes only the documented
exact inspection and explicit saved work-product round-trip slice.

The [complete walkthrough and interface](synthetic-oscillator.md) document simulated
assessment versus actual execution, finite-matrix versus full-line support,
historical preservation, positive-branch review gaps, errors and test commands.
Fixture tests add mutation, reference, snapshot, isolation and guarded-load checks
to existing unittest discovery. The fixture itself introduces no production
controller or persistence mechanism. Its historical v1.3 provenance is preserved;
under v1.4, pending scientific validation gates the work that depends on it rather
than imposing a blanket hold on independent storage engineering.

## Consistent local snapshots

`research_pipeline.backup` reuses the private RecordStore connection for supported
SQLite incremental backup and ArtifactStore for independent verified object copies.
All inventory decisions use captured metadata across historical revisions. Strict
manifest, fixed schema, relational and application consistency checks share one
read-only verification path for inspection and restoration. Exclusive destination
markers define completeness; restore publishes artifacts before original metadata
and RecordStore rejects interrupted restores before opening SQLite. See
[the backup contract](backups.md) for snapshot selection, fixed capture deadline,
publication uncertainty, local POSIX/trusted-owner assumptions and runnable usage.
Default restore preserves exact bytes, including schema3 resource history and
outstanding liabilities. Explicit migration requires the next target (1→2 or 2→3)
and caller attribution. The 1→2 transform temporarily suspends foreign-key enforcement
on the private copy and replaces changed tables/trigger. The 2→3 transform preserves
scientific tables unchanged, replaces only administrative history with an ordered
form, retains every original row and appends the attributed source identity. Both
use registered DDL and operate only on the verified unpublished private copy. Exact schema, foreign-key, application and history
checks precede COMMIT; standalone verification and synchronization precede marker
removal. Failures retain incomplete paths and journals; publication acknowledgment
can be uncertain after removal. No scientific identity regeneration or submission replay occurs. This
is partial R-019/R-017 evidence, not complete D02 or research-run/session/job recovery.


## Controller resource ledger

`resources.py` owns complete strict detached declarations and shared bounded call
envelope validation. `resource_ledger.py` uses the existing RecordStore transaction
boundary for operation identity, hierarchy, protected capacity and normalized
account/allocation/reservation/reference projections. Usage and reconciliation append
to the same operation history, retaining original reservation declarations. No second database, scientific
audit-event charge, new artifact subsystem or worker SQL endpoint is introduced.

The run's explicit `handoff_call_bounds` provisions its complete minimum; actual
reservations supply independent invocation bounds. Ancestors retain each allocation
and propagate child commitment above it without double charging contained usage.
Shared replay derives cumulative spending, remaining liability, conservative charges,
authoritative final usage and sticky project-wide admission blocking. Live open
validates history only after journal recovery. A shared chronological validator
also checks ledger inspection and immutable backup inspection. The schema3 history
is empty for fresh creation, 2→3 for migrated fresh2, or preserved 1→2 followed by
2→3. Scientific outgoing closure remains unchanged by resource mutations.
See [the resource contract](resource-accounting.md) for exact fields, arithmetic,
version-2 detached inspection, original-ID recovery, and explicit settlement evidence.


## Committed report capture

`reports.py` owns strict saved declarations/observations/results, selected-project
resource replay and deterministic inert rendering. `report_capture.py` holds one
existing `BEGIN IMMEDIATE` through exact reconciliation, capture, artifacts and
shared submission insertion. Connection-taking private snapshot/inspection helpers
preserve the original public transaction boundaries. One generic source event and
one typed manifest bind all historical artifacts; no schema or mutable report index
is added. Metadata-only retries survive source-object damage. See the
[report contract and executed example](committed-run-reports.md) for bounds, exact
source membership, ledger projection completeness and original-ID recovery.
`report_view.py` projects explicitly verified committed report history through the
shared bounded readable inventory renderer. V1 plan/report rendering identities
remain fixed; v2 report observations add adjacent navigation, and v2 readable
manifests retain exact result/observation pairs separately from the pre-submission
scientific snapshot. `prepare_report_view` verifies the original operation and
complete chain in one read transaction, without recapture or metadata writes.
The existing materializer copies exact objects and exclusively publishes a complete
generation. Offline publication inspection and explicit recovery retain token/inode
association and independent plan pins, establish current durability with checked
closes, and never claim lost historical acknowledgment. Refresh recovery reuses
its strict package reader and frozen preservation payload, without rereading prior
edits or source artifacts. There is no schema, mutable ledger, CLI or service addition.
Prepared lifecycle facts and durable pending obligations are implemented by [run control](run-control.md).
Automatic reporting hooks and admission enforcement remain mandatory subsequent controller work.

## Authenticated operating readiness

[Local operating decisions](operating-authority.md) add externally configured HMAC-SHA256
operator authentication, immutable exact dossier bindings, bounded current eligibility
and original-operation recovery in the existing schema-2/3/4/5/6/7 submission transaction.
Keys and current trust remain host-only; generic records and local typed decoding
do not authenticate permission. Current eligibility must be recomputed with trusted
time and current external policy inside the later admitting write transaction.
No admission, dispatch, worker isolation, lifecycle enforcement, tool qualification
or M0-S validation is added. Resource usage and uncertain liabilities remain unchanged.

## Durable control foundation

[Run control](run-control.md) uses separate event histories and one atomic two-member
submission per transition. The same connection-owned authority evaluator checks fresh
preparation/continuation; metadata-only reductions do not require current external
bytes or trust. No schema, worker, task admission or reporting engine is added.

## Transactional claim-use freshness

Schema 4 preserves schema-3 resource/scientific DDL and adds immutable
binding/dependency/upstream and generation history projections plus a mutable
current projection. Temporal revision/event and selected association-link
projections support event-range navigation; dependency/upstream entries include
the owning registration event. Equality prefixes followed by event ranges and
complete index suffixes bound both query passes before payload reconstruction,
excluding later events from historical discovery. Record/event and use/event
indexes seek historical heads and generations. All submissions maintain temporal
navigation at the shared receipt insertion seam; explicit 3→4 migration backfills
it from original metadata without registering historical generic documents.

`claim_use_store.py` plans complete bounded indexed propagation before insertion
and applies it at the shared insertion seam within the owning transaction.
Historical upstream bindings remain indexed after rebinding. Connection-owned
readers separate exact scoped impact association from support traversal, with
historical assertion-target unions and no inferred authority. Current reads own
one metadata-only snapshot; open and backup stream exact temporal correspondence
and verify chronological projections. Complete prospective admission retains
independent root and aggregate accounts; subsequent stored-record and binding
comparisons use independent validation accounts, so verification cannot add a
stricter combined admission limit. See [the exact contract](claim-use-freshness.md).
Positive authorization remains absent; R-015 and R-077 remain PARTIAL.

Schema 5 reuses that same reader/plan/application machinery and indexes, adding
only a separate policy activation origin and expanded administrative history.
Exact policy identity watches discover successor impact, and a bounded worklist
propagates newly added originating causes through cached historical upstream edges.
All transitioning current roots receive complete prospective version-2 inspections
before insertion. There is no separate policy registry, engine, service or second
commit. Internal event semantics preserve exact schema-4 output/accounting through
the migration watermark; later events include policies. Independent streamed
activation inspections use the first later event as cutoff, never later lifetime
history. Resources and dedicated report/control/source/operating writers retain
the shared insertion seam and existing authentication/recovery rules on schema 5.

Schema 6 extends the same connection-owned plan with explicit target-context
identity watches and an independent context activation origin. Target-context,
policy and Review/Issue origins enter one bounded propagation worklist before any
metadata insertion. Version-3 prospective/current inspection retains complete
immutable bound and observed scope; observations never rewrite transitions.
Chronological policy and context selection use independent strict event boundaries;
policy activation inspections explicitly disable context semantics. Resource and
report/control/source/operating seams support actual schema 6 without weakening
their guards. See [target-context activation](claim-use-freshness.md#schema-6-target-context-freshness-and-activation).

Schema 7 extends that connection-owned Reader/Plan/apply path with immutable selected
support-context occurrences and one context/event watch index. Metadata derivation,
shared finite accounts and complete version-4 prospective inspection precede the
mandatory shared insertion seam. Independent 6→7 activation backfills exact historical
bindings at original temporal views without rewriting old dependencies, events or
receipts. Chronological verification explicitly disables support semantics before
activation. See [support-context activation](claim-use-freshness.md#schema-7-support-context-freshness-and-activation).
