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

`research_pipeline.__main__` uses standard-library argparse to expose help and
version. No arguments prints help; unknown or abbreviated arguments exit with
status 2. The package has no third-party runtime dependencies. Setuptools is solely
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
original-ID reconciliation order is unchanged. See [preview and explicit import](work-product-import.md).
`RecordStore.submit_typed` selects the scientific, assessment, work-product, Source, corpus or project codec
explicitly and decodes every member locally, admitting mixed ten-kind batches. For a new canonical
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
and checks each incoming document role independently of cached target resolution. No transitive artifact
verification is added. Every submitted Review's assessed route
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
`metadata.sqlite3`. It creates schema 2 only in absent roots and gates opening on the fixed
version-1 or version-2 schema through a read-only immutable preflight, before allowing normal
SQLite rollback-journal recovery. This preflight is solely for fixed schema/version,
never live data or integrity conclusions. Operational connections require DELETE
journaling, EXTRA synchronization, foreign keys and a 5000 ms busy timeout.

`research_pipeline.schema` owns a fixed two-entry DDL/kind/backup-format registry
and pure manifest/history validation, depending only on domain values and the
standard library. It owns no SQLite connections or filesystem work. Schema 1's
exact five-kind DDL remains supported; schema 2 extends the kind checks and state
trigger and adds a singleton administrative history table, empty on fresh creation.
Operational connections validate administrative rows after journal recovery.
Explicit restore-time v1→v2 migration lives only in `backup.py`, transforming a
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

These modules do not depend on `fixtures`. Imports remain inert, with no new CLI
commands or dependencies. The [durable contract and runnable example](durable-records.md)
give exact APIs, errors, ordering/fingerprint semantics, trusted-owner assumptions,
retained-orphan behavior and acknowledgment recovery by original submission ID.
Real subprocess exits exercise hot-journal rollback and post-commit receipt recovery.
Remaining typed payloads and state machines, support/assessment
freshness, eligibility/promotion, worker isolation, leases/fencing, resource authorization/accounting, general migrations,
periodic scheduling, distributed execution and research execution remain
unsupported. No ledger means no duplicate charging guarantee. This slice does not
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
initializer and CLI remain unchanged.

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
Default restore preserves exact bytes. Explicit migration requires target 2 and
caller attribution, temporarily suspends foreign-key enforcement on the private
copy, replaces changed tables/trigger using registered DDL and inserts separate
administrative provenance. Exact schema, foreign-key, application and history
checks precede COMMIT; standalone verification and synchronization precede marker
removal. Failures retain incomplete paths and journals; publication acknowledgment
can be uncertain after removal. No scientific identity regeneration or submission replay occurs. This
is partial R-019/R-017 evidence, not complete D02 or research-run/session/job recovery.
