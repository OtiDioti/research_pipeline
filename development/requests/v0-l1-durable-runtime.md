# V0-L1 implementation and verification handoff

Milestone 001 code review approved `df844341d4465a740704df23cb2e3dc4bc6c738f`.
Milestone 002 prepares repeated required host verification; its changes still
require independent review. **Production L1 acceptance is not established.** The enabled native
check failed on the Writer's missing authorized systemd user bus. No private science,
M5 work, external publication or remote action occurred.

## Source and preservation

Base reference: `22213b2aba2514c0ba72034bd7e92ee98931a49d`. Working implementation:
`cwi/20261112T190532_377a68b3`, in this pipeline worktree. The pipeline records the
final implementation reference; the Writer performed no Git orchestration.
`PROJECT.md` and `2026-11-12-v0-context-lifecycle-design.md` match their pre-edit
SHA-256 checksums (`runtime/tmp/human-inputs.sha256`, relative to this run).

Recovery stopped at planning, with a zero-byte implementation diff. Read the
preserved plan/recovery/baseline directly from the shared filesystem after the
artifact reader refused their listed paths. The original unavailable baseline is
unchanged. A fresh baseline with the retained MCP installation completed **222 tests: 215 passed,
seven skipped**; see `runtime/tmp/recovered-baseline.txt`.

Inspected the retained M5 candidate at
`cwi/20261111T063907_2732fff6`, recorded reference
`1b70aea25f6c5f8496acdea12e9a27c6f3d4ecbd`, under its preserved worktree. Selectively
ported `workspace.validate_fresh(..., preserve_existing)` and the corresponding CLI
opt-in: refuse existing/orphaned runtime while preserving ordinary scientific files.
Extended its exclusions to the new context/job directories. Adapted its early,
handoff-first guidance into the new scientific prompt. No old timer, execution
adapter, M5 harness, state or scientific evidence was copied or resumed. The old
candidate and its partial science remain unmerged, inactive and unaccepted.

## Consequential decisions

- Logical task identity is logical agent identity. Context UUIDs/native thread IDs
  are disposable; job UUIDs, logical owner, original deadline and fixed slot persist.
  Schema 4 is fresh-only. Old schemas and timer CLI options fail explicitly.
- One research-owned asynchronous JSON-RPC driver replaces `codex exec` entirely.
  It handles bounded messages, correlation, notifications, telemetry, interruption,
  EOF, errors and unknown requests. No controller-engine dependency was introduced.
- A transient investigation slice enforces the aggregate human grant. Persistent
  child slices divide memory/tasks equally, leaving integer remainders unallocated.
  Each context and job service uses its owner's same slot. Defaults remain 2048 MiB,
  zero swap, 128 tasks, two logical agents and one admitted job. Applied cgroup files
  must match before any context launch. No scientific context `RuntimeMaxSec` exists.
- Jobs are independent systemd services, with `Restart=no`, cgroup termination and
  `RuntimeMaxSec` derived from the immutable admission deadline. A separate worker
  enforces that deadline too. Preparation consumes it. A private release file holds
  scientific execution until actual invocation/cgroup ownership is captured and
  saved; short computations cannot outrun ownership capture. Lost acknowledgements
  never trigger a retry. Pausing during launch prevents command release.
- Per-context MCP adapters communicate over a private filesystem Unix socket and
  authenticated attachment. Binding through a directory descriptor handles long
  project paths without abstract/network sockets. Scientific namespaces omit the
  socket directory, control storage, user bus, backend home and credentials.
- Model waits subscribe through the runtime. Only trusted observation polls systemd;
  repeated model turns are unnecessary. Disconnect cancels a subscription, not the
  job. Status history is compact/bounded; a job ID retrieves retained full results.
  MCP's one-year transport ceiling is an operational subscription bound, not a job
  timeout; an interrupted wait leaves the same job inspectable.
- Cleanup checks boot identity, recorded invocation/cgroup and actual group
  population. Missing ownership or failed observation stays uncertain and reserves
  capacity. Context close affects only that context. Admission blocking latches
  before investigation cleanup. Failed saving/publication cannot disable cleanup;
  process outcome, cleanup and publication failures remain distinct.
- Existing scoped mounts, source helpers, qualified reusable tools and frozen
  independent-check packets remain. Primary contexts mount the entire `work/tasks`
  directory read-only so newly created delegates are protected too. Job draft batches
  are separate from disposable context drafts. Frozen inputs are excluded from
  generated indexes. Human Markdown edits retain canonical precedence; conflicts
  are saved as proposals. New contexts reread current human inputs.
- Explicit `Coordinator.successor(task_id)` is the L1 attachment primitive, requiring
  confirmed predecessor closure. It reuses the logical allocation and existing jobs.
  L1 retains idle logical task slots and does not automatically retire logical tasks,
  invoke successor science, roll over at 55%, monitor weekly reserve, make scientific
  terminal decisions, or resume stopped research. These limitations are explicit.
- The duplicated timed runtime/coordinator/checkpoint protocols and their tests were
  replaced, rather than retained to satisfy implementation-specific checks. Useful
  source/tool/numerical-provenance tests remain. Historical paid M1–M4 harnesses now
  explicitly reject enabled use; accepted receipts and evidence parsers remain.
  Their new lifecycle integration is a V0-L6 gate, not an L1 acceptance claim.

## Review repair, attempt 1

All six supplied findings have corresponding repairs and regressions:

1. Context and job draft publication, plus directory indexes, now wait for confirmed
   quiescence of **all** owned contexts/jobs. This conservative boundary also covers
   shared handoff directories. Private batches retain `publication_pending` and are
   flushed by the last confirmed cleanup; no computation is stopped merely to
   publish. Status/results/data remain available during the delay. Concurrent-read
   helpers pin ancestors with Linux directory descriptors, refuse symlinks/FIFOs,
   and traverse via `os.fwalk`. Production Markdown mount sources use held file
   descriptors so a directory replacement cannot redirect a later Bubblewrap bind.
   Context and job mount descriptors have separate ownership/lifetimes. Synchronized
   process tests exercise symlink/FIFO replacement, parent pinning, delayed publication,
   and eventual safe publication. Global quiescence intentionally delays canonical
   draft visibility while another context/job remains live; this is explicit in README.
2. CLI success now requires every context and job record to have confirmed cleanup.
   Missing aggregate state can no longer default to success. A full CLI regression
   ends a normal turn, fails service cleanup, and verifies exit 1 plus retained
   `cleanup_unconfirmed` state.
3. Failed/interrupted native turn outcomes are retained before validation and become
   context failures. Full CLI regressions verify nonzero status and preserved native
   error details; real JSON-RPC process fixtures exercise these notifications.
4. The supervisor persists `finished_monotonic` and `termination_cause`. A completed
   command observed later keeps its completion outcome, even if the idle retained
   service subsequently hits its own bound. Expiry is established by supervisor or
   service evidence, never the controller's reconciliation clock. Controlled-clock
   tests and real supervisor fixtures cover the distinction.
5. Delegation rebases canonical evidence links and copies recursively linked private
   Markdown dependencies into protected delegate inputs. Missing evidence rejects
   the assignment before allocating a task. Tests resolve all installed links,
   including nested draft dependencies and fragments, and preserve the original draft.
6. The native survival computation waits on an explicit fixture-owned release file.
   Before release, the fixture requires a running computation, its unchanged service
   invocation/deadline/job ID, a distinct live successor, and observed membership of
   both services in the same persistent slot. Only then does it release and collect
   the public sum. Its 180-second computation timeout remains the original deadline;
   the separate 61/7200-second admission/cancellation exercises remain unchanged.

The revised enabled production fixture was invoked and failed before inference on
this Writer's missing authorized user bus. Latest failure log:
`runtime/tmp/review-repair-native.txt`; latest failed receipt:
`runtime/tmp/l1-native-writer-repair-001/receipt.json`. Its evidence and commands are
empty. Production validation of the pinned mounts and synchronized native coexistence
remains a required controller-host check, alongside independent review and combined
verification. The earlier `l1-native-writer-001` failed receipt is preserved.

## Review repair, attempt 2

Both remaining findings are repaired without reopening canonical writes while
science is live:

- Confirmed-stopped context and job batches are validated independently of live
  canonical paths, then copied into a private immutable document store. Document
  metadata retains task, original scientific path, source context/job and SHA-256.
  The existing controlled MCP `control` tool adds `documents` and `read_document`
  actions, with bounded lists/pages and strict task/parent/primary read scope.
  Successor intake and `check`/`tasks` expose IDs. This lets a live successor consume
  its handoff while awaiting its unchanged job, and a live primary consume and
  integrate a completed delegate's RESULT.md or verifier's CHECK.md. Canonical
  publication still waits for all owned writers to stop. Snapshot reads do not
  consume job capacity, change deadlines or grant filesystem/command access.
  The existing 16 MiB bounded regular-file reader applies to each snapshot;
  invalid/oversized/unreadable batches produce visible snapshot errors, never
  unchecked reads. Scope, special-file rejection, pagination and integrity failures
  are covered. Snapshots identify versions; they cannot supersede human canonical edits.
- `block_and_cleanup` routes a known context's retry through `close_context`, even
  after its client was removed. Success reconciles the context record, clears the
  attachment, releases private resources, captures its documents and flushes eligible
  pending publications. Aggregate cleanup additionally requires every context/job
  record to confirm cleanup. Failed retries retain ownership reservations and hide
  unconfirmed batches; successful retry does not remove the latched admission block.
  Failure-then-success, failure-again, idempotence and full CLI regressions cover this.

New regressions use real Unix control connections with explicit backend/service
doubles, not production proof. The successor test invokes actual successor setup,
reads its saved handoff during a pending job wait and collects the same job without
changed service/ID/deadline/launch count. Parent tests consume both researcher and
verifier reports while their own context remains active, then publish a synthesis
at quiescence. The opt-in native fixture now also requires actual controlled
handoff retrieval while the admitted computation remains held for coexistence.

Latest routine discovery is 122 tests: 117 passed, five disabled opt-in gates.
Focused checks passed 54 tests. Logs: `runtime/tmp/review-repair-2-discovery.txt` and
`runtime/tmp/review-repair-2-focused.txt`. Compilation and protected-specification
checksums pass. The revised enabled native check failed before inference on the
same unavailable authorized user bus; it is not accepted or skipped evidence.
Latest failure log: `runtime/tmp/review-repair-2-native.txt`; failed receipt:
`runtime/tmp/l1-native-writer-repair-002/receipt.json`. No production context/job
identity, survival, boundary or cleanup evidence was produced. Controller-host
production verification using the invocation below remains mandatory; use its
fresh `l1-native-host-final-repair-2` output directory. Earlier receipts are preserved.

## Checks and observed results

Trusted test interpreter: `/home/francesco/miniconda3/bin/python`.
Dependency already supplied by recovery:

```text
/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies
```

Run from this implementation worktree:

```sh
export PYTHONPATH="$PWD/src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies"
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

Latest routine discovery: **122 tests: 117 passed, five intentional opt-in skips**
(four superseded historical paid gates and the disabled L1 native gate). The
`runtime/tmp/review-repair-2-discovery.txt` log records the repaired candidate check. Later final verification
is recorded by the pipeline and must pass the final candidate. No enabled missing
prerequisite is counted as a passing skip.

Coverage includes explicit 61/7200-second admission, immutable deadlines and shared
capacity across replacement, foreign/stale ownership, reservation-before-launch,
lost launch acknowledgements, supervision/query/stop failures, event-driven wait and
real Unix disconnects, latched admission/cleanup during saving failures, scoped
writes, frozen evidence and human conflicts, required MCP schemas, native request
catalog provenance, app-server protocol errors, cgroup property mismatch, removal of
timer/options/state migrations, source retrieval and reusable-tool qualification.
Real local protocol processes exercise request correlation and failure handling.
Real worker fixtures verify expiry, bounded retained output and nonzero outcomes.
Those fixtures are explicitly **not production isolation evidence**.

A worker test exposed swallowed `InterruptedError` in Python selectors; a dedicated
interruption exception fixes that failure. A real Unix test exposed sockaddr path
length, and descriptor-relative binding fixes it. These were investigated, corrected
and rerun; failed intermediate logs remain under `runtime/tmp/`.

Installed protocol inspection: **codex-cli 0.167.2**;
`codex app-server --help` and `generate-json-schema --out runtime/tmp/app-schema`
confirmed the initialize, thread/start, turn/start, token-usage, MCP status/call,
interrupt and unsubscribe shapes used by the driver. Generated schemas are in this
run's `runtime/tmp/app-schema`. This inspection is protocol reference evidence only,
not a substitute for production isolation or native tool validation.

Enabled production check actually run by Writer:

```sh
RESEARCH_PIPELINE_V0_L1_NATIVE=1 \
RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR="$PWD/../runtime/tmp/l1-native-writer-001" \
/home/francesco/miniconda3/bin/python -m unittest tests.test_v0_l1_native -v
```

It **failed**, before any inference or process admission, with:

```text
systemd user bus unavailable: XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS
must already be set in the authorized host environment
```

Failure log: `runtime/tmp/native-writer-check.txt`.
Receipt: `runtime/tmp/l1-native-writer-001/receipt.json`.
These paths are relative to run `20261112T190532_377a68b3`. No context/thread/job/unit
identities, actual cap observations or production survival/timeout results exist in
that receipt: `commands` and `evidence` are empty. Do not describe it as passing or
skip the native test in required host verification.

## Milestone 002: repeated verification preparation

The recovery preserved the approved milestone 001 candidate and supplied host
environment metadata for trusted pipeline testing. Inspection confirmed the
native fixture's fresh-directory assertion would reject the second required
stage inheriting the same destination. A test-local reservation helper now
creates the first requested directory or a unique private sibling on later runs.
This changes evidence storage only; production preflight, assertions, failure
receipts and cleanup requirements remain enforced. No runtime repair was needed.

Three ordinary regressions cover private/distinct directories, retention of
earlier evidence, file/symlink/invalid-parent rejection, and two independent
preflight failures retaining separate failed receipts. The latter use an explicit
preflight double and establish fixture behavior only.

Writer checks from this checkout, with the retained dependency on `PYTHONPATH`:

```sh
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l1_native.ValidationOutputTests -v
RESEARCH_PIPELINE_V0_L1_NATIVE=0 /home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest discover -s tests
RESEARCH_PIPELINE_V0_L1_NATIVE=1 \
RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR="$PWD/../runtime/tmp/l1-native-writer-milestone-002" \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l1_native.NativeL1Tests -v
sha256sum -c ../runtime/tmp/human-inputs.sha256
```

Results: three focused tests pass; discovery runs **125 tests: 120 passed, five
disabled opt-in skips**. Both protected specification checksums match. Routine
discovery disables the L1 gate only in that Writer subprocess; it does not alter
the trusted pipeline's launch environment. Log:
`runtime/tmp/milestone-002-writer-discovery.txt`.

The enabled native invocation **fails**, retaining
`runtime/tmp/l1-native-writer-milestone-002/receipt.json`; log:
`runtime/tmp/milestone-002-writer-native.txt`. This Writer still lacks
`XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. No inference or service admission
occurred: `commands` and `evidence` remain empty. Cleanup was not exercised.
The controller's authorized bus metadata is not passing product evidence, and no
alternative execution context was requested. Paths above are relative to run
`20261112T190532_377a68b3`.

These changes are prepared for independent review and the trusted final/required
combined checks. Their outcomes, actual candidate/integration refs and distinct
production receipt paths remain pending pipeline stages. V0-L1 is not yet accepted.
The next product dependency remains V0-L2 measured automatic context rollover.

## Required controller-host verification

Use the final integrated candidate's checkout, the existing dependency and the
already authorized host environment (including native file auth, Codex, Bubblewrap,
user bus and cgroup controls). Keep **all M1–M5 live gates disabled**. The invocation
below runs discovery with the L1 gate enabled. During pipeline final/combined
stages, retain the controller's inherited `RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR`
recorded in `host-verification-recovery.json`. For a separate authorized invocation,
set it to a caller-chosen private destination first. Do not replace the inherited
controller environment with Writer settings:

```sh
cd /home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261112T190532_377a68b3/worktree
export PYTHONPATH="$PWD/src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies"
unset RESEARCH_PIPELINE_M1_LIVE RESEARCH_PIPELINE_M2_LIVE RESEARCH_PIPELINE_M3_LIVE RESEARCH_PIPELINE_M4_LIVE RESEARCH_PIPELINE_M5_LIVE
export RESEARCH_PIPELINE_V0_L1_NATIVE=1
: "${RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR:?Set a private validation destination}"
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

Each invocation creates the exact requested directory if absent, or reserves a
fresh mode-`0700` sibling if it already exists as an ordinary directory. Symlinks,
including ancestors, files and unusable parents fail. Existing receipts are never
overwritten or reused as evidence. The actual path is printed before preflight;
`requested_output_dir` and `output_dir` in each new receipt identify the selection.
Every required stage must execute the native fixture and retain its own receipt.
Four disabled historical paid gates may remain skipped; the enabled L1 gate may not.

The opt-in fixture uses the actual production coordinator, slices, services,
Bubblewrap, app-server and controlled MCP schemas/operations. It is intended to
retain native tool declarations, distinct context/thread IDs, unchanged job/service
identity/deadline/launch count, real survival/result retrieval, detached-descendant
expiry after original context closure, partial output, unrelated useful computation,
61/7200-second admission with prompt confirmed cancellation, shared parent/slot cap
observations, ownership/write/credential denials and real supervisor loss/cleanup.
Its operational readiness/RPC/test bounds never assert scientific completion.
Missing enabled prerequisites or unsupported native evidence formats are blockers.

Pipeline independent review and final/combined checks remain required. Resolve any
host failures in this candidate; do not weaken the boundary or reuse historical
receipts. The next product dependency is **V0-L2**: measured per-context telemetry,
validated scientific handoff and automatic fresh-context continuation for every
role, with the same live jobs and allocations. L3–L6 and human M5 scientific
acceptance remain later gates.
