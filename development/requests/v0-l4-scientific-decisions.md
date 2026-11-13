# V0-L4 scientific decisions — implementation and native validation

Scientific opposition, repeated revisions and version-bound COMPLETE/scientific
STOP finalization are implemented. **Independent pipeline review approved
Milestone 1**, including its repairs; the review ran no tests. Milestone 2 adds
the public native investigation gate, authenticated observations, retained receipts
and ungated failure regressions in `tests/test_v0_l4_native.py`.

**Native scientific validation remains pending for trusted final/combined stages.**
The first trusted final run failed after its 1200-second engineering bound:
fixture instructions contained an invalid placeholder document link that blocked
proposal freezing. Its native receipt confirms cleanup but records no opponent
or scientific terminal outcome. The fixture is repaired; see the integration
repair below. The enabled Writer attempt also failed before runtime creation
because the inherited authorized user bus is unavailable. Failed receipts remain
retained. Successful native final/combined checks and overall L4 acceptance remain
outstanding. L5 reopening/resumption and L6/M5 work are excluded. Human scientific
acceptance remains mandatory for M5. Historical implementation and repair evidence
below retains its original scope.

## Implemented behavior and decisions

- Operational schema **7** rejects schema 6 and earlier without migration. The
  single `opposition` runtime record retains the designated opponent ID, current
  proposal and proposal history. Scientific arguments remain Markdown; this is
  terminal bookkeeping, not a claim database.
- Only the authenticated primary proposes COMPLETE/scientific STOP and requests
  scientific finalization. Only the designated opponent submits opposition.
  Delegated completion and normal native turn endings never finish an investigation.
  The old response/closure protocols remain rejected. Unused finite-exchange
  constants were removed from `verification.py`.
- Proposals freeze results, assumptions, reasons, coverage and explicitly linked
  evidence together with authoritative questions and optional instructions/feedback.
  Existing stable-read, explicit-dependency, per-file/aggregate and atomic-install
  protections remain. Freezing never executes submitted evidence.
- `document:ID` links copy exact bytes through primary-authorized `Documents.raw`.
  The manifest records the document ID, original scientific path, original hash
  and rebased packet path/hash. The opponent reads the copied packet without
  obtaining unrelated private-document permissions. Its input tree mounts read-only.
- The primary enumerates the free-form questions. The opponent explicitly judges
  exhaustiveness and scientific adequacy for each one. COMPLETE requires supported
  coverage, `agree_complete` and no open substantive objection. Negative,
  inconclusive and supported-unanswerable findings can qualify. Structural checks
  establish eligibility only; they never certify scientific correctness.
- The same logical opponent preserves stable objection IDs, dispositions and
  review phase across proposals, idle allocation release and measured rollover.
  Every later review must retain all prior objection IDs with reasons; primary
  responses cannot resolve them. No scientific exchange ceiling exists.
- A proposal binds authoritative input fingerprints, copied evidence, canonical
  observations and effective retained drafts. Source selection follows publication
  order: contexts integrate their own jobs, successors replace ancestors. Version
  checks also compare every retained writer batch for reviewed paths, so a changed
  deferred job cannot hide behind an older context draft or manipulated mtime.
  Identical publication preserves agreement. Changed questions, feedback, code,
  data, drafts or frozen packets invalidate it. Checks run at review submission,
  final request and after writers stop.
- Human Markdown changes must be incorporated with the existing exact-hash
  acknowledgement before freezing a draft that would conceal them. Scientific final status
  conflicts preserve the human text and prevent an unqualified acknowledgement.
- Finished delegates explicitly save results/handoffs and release slots after
  confirmed cleanup. Primary retirement requests interrupt the ordinary runner,
  attempt a focused checkpoint when that runner/context is available, stop owned
  jobs/context and validate the retained handoff. Failed saving never disables the
  remaining cleanup. Missing handoffs or uncertain ownership retain the slot and
  report the failure. An idle opponent releases capacity and reactivates with its
  original identity. No allocation is enlarged.
- Final decisions explicitly dispose of each delegated task as integrated,
  superseded or no longer needed, with reasons. Integration requires the delegated
  task to have finished and released its allocation.
- Scientific STOP requires a current delivered challenge addressing findings,
  stopping rationale and possible further work. The primary retains authority to
  reject unpromising further work, recording best recovery attempts, reasons,
  unresolved objections and required human intervention. Opponent agreement is
  unnecessary.
- Scientific and quota outcomes use the existing common owned-process cleanup
  path. Admission blocks synchronously; lifecycle work runs outside RPC-reader
  callbacks. Replies mean pending work, never successful terminal acknowledgement.
  Quota cutoff overrides pending science and starts no opponent/checkpoint
  inference. Missing telemetry or backend/protocol failure overrides uncommitted
  scientific intent as an operational failure.
- Scientific STOP preserves its explanation early and best-effort in its project
  marker and Markdown decision handoff. Actual preservation/interruption outcomes,
  unfinished jobs/tasks, missing handoffs, artifacts and continuation guidance are
  retained there and in research status. Failed checkpointing, snapshotting,
  publication, state/status/index/marker writes or cleanup cannot manufacture a
  successful acknowledgement. CLI diagnostics retain a failed STOP rationale even
  if saving is unavailable.
- COMPLETE/STOP acknowledgements require actual cleanup, required handoffs,
  preservation, final version reassessment and matching marker bytes. Runtime
  state records the marker and SHA-256; inspection refuses a recorded commit
  without its matching acknowledgement. Subsequent pause/cleanup preserves a
  confirmed committed outcome. A quiescent revision invalidating COMPLETE leaves
  `reassessment_required`, with neither COMPLETE_ACK nor invented scientific STOP.

The implementation follows the plan's file boundaries. No new backend, framework,
database, migration, controller dependency or scientific timer was added. The
small pure `decisions.py` validates receipts; Coordinator owns authority, scheduling
and cleanup. Retirement's 20-second runner interruption wait and existing
90-second checkpoint bound are operational bounds, never scientific work budgets.
Native intake explains the contracts and independent scientific obligations.

## Markdown and controlled interface contracts

The six MCP tools and `control(action, path, parent, offset, sha256)` signature
remain unchanged. Added actions are `finish_task`, `retire_task`,
`propose_complete`, `propose_stop`, `submit_review`, `finalize_complete`,
`finalize_stop`. Proposals/results/reviews/final decisions use scoped Markdown paths;
retirement takes a secondary task ID. Reviews and final requests require an
explicit `sha256` equal to the current proposal version. `check/tasks` includes
bounded task/opposition summaries, review versions and allocation blockers.
`history` pages proposal references and `read_history` returns complete submitted
proposal/review/final text in bounded pages; see the review repair below.

Proposal sections: Results; Assumptions; Evidence and reproduction; Reasons;
Recovery attempts; Unfinished work; Continuation guidance; Responses to objections;
Decision record. The record is one JSON object, optionally fenced `json`:

```json
{"coverage": [{"id": "q1", "question": "Current question", "disposition": "negative",
 "explanation": "Supported account of the negative finding", "evidence": ["work/check.py"]}]}
```

Review sections: Independent approach; Observations and counterchecks; Evidence;
Objections and limitations; Review record. STOP additionally requires Stopping
rationale and Further work. Its record:

```json
{"version": "<proposal version>", "exhaustive": true,
 "coverage": [{"id": "q1", "adequate": true, "reason": "Independent scientific assessment"}],
 "objections": [{"id": "boundary", "substantive": true, "disposition": "resolved",
                 "reason": "Countercheck and resolution"}], "outcome": "agree_complete"}
```

Allowed objection dispositions: open, resolved, withdrawn, inapplicable. Review
outcomes: agree_complete, needs_revision, stop_challenged.

Final sections: Reasons; Response to challenge; Unfinished work; Continuation
guidance; Decision record. The record contains `version` and `delegated_work`,
mapping secondary researcher/verifier task IDs to `disposition` and `reason`.
The persistent opponent is excluded from that delegated-work mapping.

## Validation and retained evidence

All new scientific judgments in automated tests are **engineering fixtures**,
explicitly labelled; none claims native scientific agreement. The opponent rollover
test injects a labelled 55% occupancy observation. Quota races inject labelled
native-shaped account observations into engineering doubles. Production quota
admission has not been replaced or bypassed.

Focused tests cover four actual proposal/review cycles with an open substantive
objection, supported agreement, mixed question dispositions, omitted/inadequate
coverage, authority, stale versions, human edits, changed code/successor/deferred-job
drafts, immutable delegate evidence, persistent opponent rollover, capacity release,
concurrent proposals, Unix-RPC disconnect/revocation, settling-job admission,
scientific STOP, quota preemption and operational failure.

Failure tests cover missing handoffs, checkpoint/snapshot/state/status/marker/ack
errors, unconfirmed ownership, backend interrupt/close failures, final quiescent
revision, human status preservation and matching terminal inspection/pause.
The local process test launches two actual process groups representing an owned
agent and job, each with a descendant, retains partial files/stdout and verifies
termination despite a state-saving failure. **This is local process-group evidence,
not native cgroup or production authentication/isolation proof.** Processes are
terminated in fixture cleanup even when assertions fail.

Commands used from the implementation worktree:

```sh
export PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies
/home/francesco/miniconda3/bin/python -m unittest tests.test_v0_l4 tests.test_v0_l4_cleanup -q
RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 \
RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 \
RESEARCH_PIPELINE_M5_LIVE=0 RESEARCH_PIPELINE_V0_L1_NATIVE=0 \
RESEARCH_PIPELINE_V0_L2_NATIVE=0 RESEARCH_PIPELINE_V0_L3_NATIVE=0 \
RESEARCH_PIPELINE_V0_L4_NATIVE=0 \
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

The supplied baseline passed 232 tests with seven discovery gates skipped.
An initial regression run exposed the superseded schema-version expectation and
an unconfirmed-rollover exception-state regression; both were corrected.
Focused iterations corrected the Markdown-only human-edit check and process
fixture handoff/async-double errors. The first full run passed **268 tests, seven
skipped**. Final post-race-check commands exited **0**:

- Focused `tests.test_v0_l4 tests.test_v0_l4_cleanup`: **40 passed**, 3.399 seconds.
- Ordinary discovery: **272 tests**, **seven skipped**, 14.618 seconds, no failures.

The final checks include telemetry/backend failure preemption, explicit version
arguments, rollover revocation while waiting for job admission, full CLI failure
reporting and failed-finalization preservation during later pause.

Writer logs are private engineering diagnostics:
`coding_pipeline/logs/20261113T025921_734d7f95/runtime/tmp/l4-focused.txt` and
`l4-discovery.txt`. These are not native receipts or scientific acceptance.

## Milestone 1 handoff — historical

Milestone 2 must deliver the representative production-path public/test
investigation with real native primary/opponent reasoning and meaningful independent
challenge, honest terminal finalization and confirmed owned cleanup. Its opt-in
discovery gate is `RESEARCH_PIPELINE_V0_L4_NATIVE=1`, with unique private receipts
under inherited `RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR`; enabled missing prerequisites
must fail visibly. This milestone does not claim that gate or demonstration.
Trusted native verification must use inherited authorized user bus/native file
authentication. No restricted-bus isolation workaround was attempted.

Independent pipeline review and required fresh final/combined checks were
pending at that handoff. Milestone 1 review has since approved the implementation;
see the current Milestone 2 verification status above and below.
Accepted L1–L3 native gates and historical M1–M5 live gates stayed disabled.
L5 must implement explicit stopped-state resume/reopening and recovery; an
invalidated final attempt remains admission-blocked pending that continuation work.

No Git orchestration, remote action, component merge or agent-session management
was performed by this implementation role. The pipeline assigns implementation
refs and independent review/verification receipts. The accepted L3 anchors remain
`e1030013f69fcc558d3edd2066d90a4f8d9e8b27` /
`c544bf1eefb9dca9da0b96963aff6e7b351c829d`.
PROJECT.md, AGENTS.md, the human lifecycle amendment and manager-owned STATUS.md
were read and left unchanged. The retained M5 branch/worktree at
`1b70aea25f6c5f8496acdea12e9a27c6f3d4ecbd`, protected scientific inputs and
historical receipts were not modified, resumed or accepted.

## Review repair — attempt 1

Addressed all three findings in `milestones/001/review.md`:

1. Frozen ordinary sources now validate the provenance of the selected retained
   draft, including predecessor and job drafts absent from the current context.
   A confirmed publication establishes the expected canonical hash; subsequent
   human corrections require exact incorporation. Job checks use the originating
   context's edit policy rather than a job's newer baseline. Missing job provenance
   fails explicitly. Version comparisons still permit identical publication of
   already reviewed bytes.
2. Historical publication conflicts remain in their original records. A successful
   descendant publication with a valid incorporation acknowledgement records the
   resolving source ID, human hash and published hash on affected ancestor
   conflicts. Finalization gates on unresolved conflicts; settled history does
   not permanently block COMPLETE or scientific STOP. Human versions and earlier
   conflict proposals remain available.
3. Opponent slot availability and actionable blockers are determined inside
   `jobs.lock`, before evidence installation or opponent mutation. Reactivation
   uses that reserved slot and cannot raise `StopIteration` when a queued
   delegation consumes the last allocation.

Nine added regressions cover published-note corrections before/after successor
attachment, unchanged predecessor evidence, fresh job baselines hiding edits,
COMPLETE after context/job conflict resolution, scientific STOP after resolution,
unresolved conflicts still blocking finalization, and deterministic FIFO
delegation/opponent reactivation. Rollover uses actual runtime handoff/publication
code with labelled native checkpoint/context doubles; no native science or quota
admission evidence is claimed.

Repair commands used the same inherited MCP dependency path and trusted Python
shown above:

```sh
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup \
  tests.test_pending_documents tests.test_v0_l2 -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

The focused repair/publication/rollover run passed **108 tests** in **9.441
seconds**, exit 0. Ordinary discovery passed **281 tests, seven skipped**, in
**14.912 seconds**, exit 0, with the same nine live/native environment gates
explicitly set to `0`. Private
engineering logs: `runtime/tmp/l4-repair-focused.txt` and
`runtime/tmp/l4-repair-discovery.txt` under run `20261113T025921_734d7f95`.
The original attempt's logs remain intact. Native demonstration, continuing
independent review, trusted final/combined verification and L5 remain outstanding;
protected human requirements and manager-owned STATUS.md remain unchanged.

## Review repair — attempt 2

Closed the immutable-document incorporation bypass reported in the second review.
Terminal freezing now resolves `document:ID` through source-provenance validation
as well as the existing scoped snapshot integrity read. Human corrections require
the same exact-hash incorporation as ordinary source links. Missing retained
provenance cannot silently accept a different canonical version.

The original document ID/hash and immutable bytes remain intact. If the validated
current source differs from that snapshot, freezing includes the current
incorporated revision alongside the historical snapshot. The opponent can inspect
the actual correction; version observations bind it to finalization. Existing
packet size/dependency checks, scoped access, schema 7, capacity handling and
historical-conflict resolution remain in force. Native intake and README now
explain this behavior.

Four added tests exercise publication/rollover, corrections before and after
successor attachment, rejection before incorporation and after an acknowledged
draft changes, renewed incorporation followed by successful COMPLETE, unchanged
snapshots, and missing retained drafts. They verify both frozen versions and that
the original snapshot is unchanged through finalization. Scientific judgments and
native checkpoint/context behavior remain explicitly labelled engineering doubles.

Validation used the inherited dependency path and trusted Python documented above:

- Before the fix, the new `test_immutable_document_requires_human_edit_incorporation_after_successor_attach`
  regression failed with **“JobError not raised”**, reproducing the bypass.
- `python -m unittest tests.test_v0_l4 tests.test_v0_l4_cleanup tests.test_pending_documents tests.test_v0_l2 -q`:
  **112 tests passed**, **9.767 seconds**, exit 0.
- `python -m unittest discover -s tests`: **285 tests, seven skipped**,
  **15.387 seconds**, exit 0, all nine live/native environment gates explicitly `0`.

Private engineering logs under this run's `runtime/tmp/` are
`l4-document-repair-before.txt`, `l4-document-repair-focused.txt` and
`l4-document-repair-discovery.txt`; earlier logs remain intact. No native
demonstration or trusted final/combined verification is claimed. Continuing
independent review, those validation stages and L5 remain pending. Human-owned
requirements, STATUS.md, protected scientific inputs and historical receipts
remain unchanged.

## Recovery repair — retired delegated evidence

Reassessed the incorporation boundary from the preserved plan, recovery response
and latest P2 review. The previous repair correctly rejected unincorporated source
corrections, but required an acknowledgement from a retired writer. A primary
could not provide that acknowledgement even after integrating the correction.

The existing `incorporate_edit` action now supports a primary-owned account of a
human correction to a confirmed-retired delegate's published Markdown:

```python
control(action="incorporate_edit", path=DELEGATE_SOURCE_PATH,
        parent=PRIMARY_ACCOUNT_PATH, sha256=CURRENT_HUMAN_SOURCE_HASH)
```

`parent` names the primary's saved synthesis only for this incorporation case;
the six tools and their schemas remain unchanged. The source must have an
attributed immutable document from confirmed cleanup and successful publication;
the owner must be a released researcher/verifier with no active context. The
account must be a nonempty, primary-scoped draft whose own provenance is valid.
The small acknowledgement on the logical primary binds source/document/task
identity, current human hash, account path/hash and acknowledging context.
It survives measured primary rollover without reviving the delegate.

This acknowledgement changes evidence selection, never foreign publication.
Ordinary source links use the exact canonical correction; historical document
links retain their original bytes and add the correction. Both automatically
freeze the primary account. Proposal observations bind the acknowledgement and
both evidence versions; changed source/account content requires renewed
incorporation and reassessment. A human restoration of historical bytes also
requires renewed incorporation after a correction. Uncorrected snapshots remain
historical evidence, never an implicit acknowledgement of a later human version.
Live/unpublished delegates, protected inputs, foreign accounts, stale hashes and
revoked contexts cannot use this authority. Foreign drafts and immutable snapshots
remain unchanged, with sibling access restrictions intact.

Six new regression tests finish a delegate, publish through the actual runtime
rollover/publication path, apply a human correction and save a primary synthesis.
They cover both source-link and snapshot-link opposition through COMPLETE,
unchanged delegate drafts/snapshots, renewed corrections, account changes,
authority restrictions, agreement invalidation and primary rollover continuity.
Native checkpoint/context and scientific judgments remain labelled engineering
doubles; no native scientific reasoning or quota admission is claimed.

The document-review regression failed before repair with **“Incorporation requires
a changed scientific path owned by this task”**, reproducing the review scenario.
An initial focused iteration also caught an overly narrow `working`-phase guard;
incorporation remains available during valid successor intake, while attachment
revocation and terminal admission blocking remain enforced.

Validation uses the previously documented trusted Python and
`PYTHONPATH=src:<existing MCP dependency directory>`:

```sh
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup \
  tests.test_pending_documents tests.test_v0_l2 -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

Discovery explicitly disables all nine `RESEARCH_PIPELINE_{M1–M5}_LIVE` /
`RESEARCH_PIPELINE_{V0_L1–V0_L4}_NATIVE` gates as in the command above. Private
engineering logs are under this run's `runtime/tmp/`:
`l4-retired-evidence-before.txt`, `l4-retired-evidence-focused.txt`,
`l4-retired-evidence-discovery.txt`, `l4-retired-evidence-focused-final.txt`
and `l4-retired-evidence-discovery-final.txt`. Earlier reports/receipts are retained.
Final focused verification passed **118 tests** in **11.008 seconds**, exit 0.
Final discovery passed **291 tests, seven skipped**, in **16.778 seconds**, exit 0.

Cleanup uses the existing per-test owned cleanup path, including the focused
suite's actual local process/descendant tests; this is not production native
cgroup proof. Continuing independent review, Milestone 2 native demonstration
and trusted final/combined verification remain pending. No stopped-state resume,
L5 recovery, L6 or M5 work was added. STATUS.md and human-owned requirements remain
unchanged.

## Review repair — published opposition and control transport

Addressed the latest P1/P2 review findings:

1. Review submission now uses the existing `verification.freeze` mechanism to
   retain the review, explicitly linked local counterevidence and the validated
   handoff's supporting artifacts. Normal bounded copying, dependency validation,
   immutable-document scope and read-only input protection apply. The accepted
   record binds both the review packet and observations of its original sources.
   Pending computations must finish or be cancelled before review evidence is
   frozen. Version/provenance checks run before final admission and again after
   terminal cleanup. A correction to a successfully published review or its
   countercheck evidence invalidates agreement, even while the retired writer's
   old draft remains intact. Identical publication still qualifies, including
   while publication bookkeeping settles. A revised proposal can return to the
   same opponent, which incorporates corrections and submits a fresh assessment.
   Primary incorporation cannot override the opponent's verdict.
2. `check/tasks`, proposal admission replies and fresh-context opposition intake
   now carry bounded summaries and packet/history references. Summaries retain
   phase, versions, outcomes, objection counts and capacity information; complete
   scientific arguments remain in the original records. Tasks are paged 16 at a
   time. `control(action="history", offset=...)` pages four proposal references,
   newest first, and `read_history` selects a proposal by `path`, a submission
   (`proposal`, `review`, `final`) by `parent`, and a character offset. Text pages
   contain at most 8192 characters and identify the entire text's SHA-256.
   `next_offset` preserves access to every prior submission. History text is
   scoped to the primary and designated opponent. No scientific round limit,
   argument truncation, context replay or increased transport limit was introduced.
   The six tool signatures are unchanged; these are additional fixed control
   actions. README, intake instructions, tool documentation and indexes describe
   the new access path.

Eight added regressions cover human corrections after successful review and
countercheck publication, unchanged publication, fresh assessment by the same
opponent, frozen reproduction data, a correction during final cleanup, scoped
history reads and actual adapter transport across five full proposal/review cycles.
Each large submission is a valid **256 KiB** Markdown document. The transport test
uses the production `job_server.Adapter` and Unix control server, checks both
`check` and `tasks`, traverses multiple history pages and reconstructs every
complete submitted proposal/review through bounded text pages. It also checks
fresh-intake size and task pagination. Scientific judgments, context replacement
and sufficient-quota observations remain explicitly labelled engineering fixtures;
this is not native scientific reasoning or production quota-admission evidence.

Before repair, the two published-correction regressions failed with **“JobError
not raised”**. The adapter regression reproduced **“Separator is found, but chunk
is longer than limit”** during the second review cycle. An initial focused repair
iteration exposed an identical-publication regression and a cleanup-fixture
callback missing the existing `locked` keyword; both were corrected.

Commands used the previously documented trusted Python and inherited MCP
dependency path:

```sh
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup \
  tests.test_pending_documents tests.test_v0_l2 -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

The passing focused run completed **126 tests in 12.925 seconds**, exit 0.
Discovery completed **299 tests, seven skipped, in 18.537 seconds**, exit 0,
with all nine historical live/L1–L4 native environment gates explicitly `0`.
Private logs under this run's `runtime/tmp/` are
`l4-review-transport-before.txt`, `l4-review-transport-focused.txt`,
`l4-review-transport-focused-2.txt` and `l4-review-transport-discovery.txt`;
failed iterations and earlier receipts remain retained.

Existing cleanup tests again verified actual local process/descendant termination
and partial-output retention; backend/service doubles do not establish native
cgroup isolation or authentication. In the new final-cleanup race, cleanup succeeds
and the terminal state requires reassessment, with no COMPLETE acknowledgement.
Independent pipeline review, native demonstration and trusted final/combined
verification remain pending. L5 continuation remains a separate dependency.
STATUS.md, PROJECT.md, AGENTS.md, the human lifecycle amendment, protected
scientific inputs and historical receipts were not changed.

## Review repair — reader-scoped review sources

Closed the remaining sibling-document isolation bypass. The ordinary-source
resolver for review freezing now carries the authenticated opponent's logical
identity. It selects only that task's context/job drafts; shared paths and
explicitly supplied frozen inputs use their canonical bytes. It never falls
back to another task's unpublished retained draft. A missing shared file fails
before a review packet is installed. Document-ID reads retain their existing
permission and integrity checks.

Review source observations and terminal version/provenance checks use the same
reader scope. This binds agreement to the bytes actually supplied to the opponent,
without tracking an unrelated sibling's private batch as if it had been reviewed.
Corrections to reviewed canonical evidence still invalidate agreement. The
primary's existing ability to freeze authorized delegate snapshots explicitly is
preserved, including delivery to subsequent contexts of the same logical opponent.
This uses optional reader filtering in the existing source/observation helpers;
no new permission framework, tool action, schema or lifecycle was added.

Two new consequential regressions use a finished delegate with a captured snapshot
and publication still pending while the primary remains active. Before repair,
the adapter-level denial regression failed with **“JobError not raised”**: an
ordinary review link exposed the private bytes despite denied document-ID access.
The second regression froze the private draft instead of a differing shared
canonical file. After repair:

- Both direct document-ID and ordinary-path attempts fail without installing a
  review packet or delivering a review. The opponent can submit a legitimate
  challenge afterward.
- The primary can explicitly freeze the delegate's snapshot into a revised
  proposal. The same opponent then reviews those supplied copies and completes
  the normal decision/finalization path; direct sibling-document access remains
  denied and the delegate's retained draft/snapshot remain intact.
- Shared canonical bytes are frozen and version-bound. A later private-batch
  change does not affect that review, while a canonical correction requires
  reassessment and produces no COMPLETE acknowledgement.

README, native intake and the test index document this boundary. These tests use
labelled scientific judgments, backend/context doubles and sufficient-quota
fixtures, plus the actual Unix control server/MCP adapter. They do not establish
native scientific reasoning, cgroup isolation or real quota admission.

Validation used the existing trusted Python and documented MCP dependency path:

```sh
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup \
  tests.test_pending_documents tests.test_v0_l2 -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

Focused verification passed **128 tests in 13.200 seconds**, exit 0.
Discovery passed **301 tests, seven skipped, in 19.110 seconds**, exit 0; all nine
historical live/L1–L4 native environment gates were explicitly `0`.
Private logs in this run's `runtime/tmp/`:
`l4-review-scope-before.txt`, `l4-review-scope-focused.txt` and
`l4-review-scope-discovery.txt`. Earlier failed and successful receipts remain
unchanged. Existing local process/descendant cleanup and partial-output tests
passed again; all new fixture contexts are cleaned up through the existing
per-test cleanup path.

Continuing independent review, native demonstration and trusted final/combined
verification remain pending. L5 recovery/reopening remains a separate dependency.
STATUS.md, PROJECT.md, AGENTS.md, the lifecycle amendment, protected scientific
inputs and historical receipts were not modified.

## Milestone 2 — native gate and verification handoff

Followed `milestones/002/plan.md`. The artifact reader refused the plan page;
the same complete plan was read from the local pipeline artifact directory.
`milestones/002/decisions.md` and its supplied diff were empty. The baseline
discovery receipt reports exit 0. The current
`milestones/001/review.md` explicitly approves the complete Milestone 1 diff and
repairs, with no remaining actionable finding; it executed no tests and leaves
native/trusted verification pending.

Changes are confined to the planned native test module, README, test/request
indexes and this report. No production repair, schema/tool change, isolation
exception or alternate lifecycle was necessary. The new gate reuses
`reserve_validation_output()` and the existing Coordinator, project lock,
default Config, quota admission and common cleanup path.

The fixture asks two public questions about the signed trapezoidal error for
`x^2` and the limits of generalization to other smooth functions. Native agents
must supply all results, calculations, challenges, responses and terminal
submissions. The fixture neither supplies a solution nor demands an objection,
agreement or exchange count. Each role's numerical job must write its own
`NUMERICAL_CHECK.md`; its job snapshot's hash must match evidence frozen in the
current proposal/review. This procedural filename distinguishes actual retained
numerical work from an inspection-only job without prescribing scientific findings.

An observer wraps the authenticated `control()` handler without originating,
changing or holding its requests. It retains identities, submission hashes,
versions, genuine responses/errors and history-page metadata/hashes. Assertions
bind proposals/reviews/final requests to their actual contexts and verify the
primary read every page of each delivered challenge before its final request.
The same logical opponent must serve all observed proposals. Frozen packet
manifests and all evidence hashes are rechecked after terminal cleanup.

The gate accepts only acknowledged `complete` with current scientific agreement,
or `scientific_stopped` with a delivered stopping challenge and the primary's
actual reasons/recovery account. Quota and operational outcomes fail/interrupt
the demonstration. It requires usable final handoffs and decision/status
artifacts, matching marker/acknowledgement/runtime hashes, unchanged protected
inputs and engineering-root markers, confirmed cleanup for every recorded owner
and fresh service properties/empty-cgroup observations. Receipts retain
native inventory/measurement references, scientific submissions and artifacts,
job commands/results/original deadlines and ownership uncertainty.

The 1200-second fixture bound and 120-second cleanup/close bounds apply only to
the engineering test. Expiry fails it, records interruption and attempts owned
cleanup. An actual RPC timeout retains its own diagnostics instead of being
misreported as fixture expiry. Nested finalizers attempt both common cleanup and
close after runtime creation, including failures, and save a failed receipt when
storage is available. No science, quota, clock, telemetry or consensus is injected
by the enabled native gate. No new native rollover or revision is claimed unless
observed. Ungated regressions explicitly mock missing prerequisites,
interruption, cleanup failure and fixture expiry; these establish engineering
failure behavior only. Existing tests establish private output/symlink handling.

Writer verification used:

```sh
export PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies
export RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0
export RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0
export RESEARCH_PIPELINE_M5_LIVE=0 RESEARCH_PIPELINE_V0_L1_NATIVE=0
export RESEARCH_PIPELINE_V0_L2_NATIVE=0 RESEARCH_PIPELINE_V0_L3_NATIVE=0
export RESEARCH_PIPELINE_V0_L4_NATIVE=0
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup tests.test_v0_l4_native -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

The initial focused run passed **73 tests, one skipped**, in **8.169 seconds**.
After strengthening the numerical evidence check and adding the fixture-expiry
regression, focused verification passed **74 tests, one skipped**, in **8.205
seconds**, exit 0. Ordinary discovery passed **306 tests, eight skipped**, in
**19.134 seconds**, exit 0. Logs under this run's `runtime/tmp/`:
`l4-m2-focused.txt` and `l4-m2-discovery.txt`. Existing actual local
agent/job/descendant interruption and retained partial-output tests passed;
these are local process evidence, not new native cgroup proof.

Final code inspection refined observation-only error handling, bound submission
hashes to frozen proposal sources and clarified immutable links for unpublished
job reports. The same commands and disabled-gate environment were rerun afterward:
focused **74 tests, one skipped, 8.200 seconds** and discovery **306 tests, eight
skipped, 18.768 seconds**, both exit 0. Final logs are
`runtime/tmp/l4-m2-focused-final.txt` and `runtime/tmp/l4-m2-discovery-final.txt`
under run `20261113T025921_734d7f95`; earlier logs and the failed native receipt
remain intact.

One enabled Writer invocation used the same Python/dependency path and disabled
historical gates, overriding only:

```sh
RESEARCH_PIPELINE_V0_L4_NATIVE=1 \
RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261113T025921_734d7f95/runtime/tmp/l4-writer-native \
/home/francesco/miniconda3/bin/python -m unittest tests.test_v0_l4_native.NativeL4Tests -v
```

It ran **one test**, exit **1**, at phase `preflight`, with:
`RuntimeUnavailable: systemd user bus unavailable: XDG_RUNTIME_DIR and
DBUS_SESSION_BUS_ADDRESS must already be set in the authorized host environment`.
The private failed receipt is
`coding_pipeline/logs/20261113T025921_734d7f95/runtime/tmp/l4-writer-native/receipt.json`.
It records requested/actual paths, the failure and preserved absent engineering
markers. No runtime, agents or jobs were created, so there was no owned-process
cleanup to assert. No bus replacement or isolation/authentication bypass was
attempted, and the earlier receipt remains unchanged.

**Outstanding verification:** independent Milestone 2 review and fresh trusted
final/combined discovery, each inheriting `RESEARCH_PIPELINE_V0_L4_NATIVE=1`,
`RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR`, the authorized host bus and native
authentication. Keep M1–M5 live and L1–L3 native gates disabled. The shared
requested output reserves distinct private actual directories on successive
invocations; retain failures as well as both successful receipts.
Actual native scientific findings, the independent challenge, primary response,
observed revisions/rollovers, cleanup and receipt paths must be assessed and
reported from those runs; none is asserted by the Writer's prerequisite failure.
Reviewed source with this validation pending is not L4 acceptance.

Implementation refs and trusted-stage receipts are assigned by the pipeline;
this role performed no Git orchestration or session/permission/budget management.
L5 stopped-state resumption/reopening remains a separate dependency.
PROJECT.md, AGENTS.md, the human amendment, manager-owned STATUS.md,
`research_example/starting_evidence/`, the inactive retained M5 candidate and
historical receipts were preserved.

## Milestone 3 integration repair — native fixture evidence link

Read the supplied baseline/final reports, the complete final command output and
earlier milestone decisions. The artifact tool refused the command log and
decision pages; their read-only filesystem copies were inspected. Baseline
`tests/baseline-001.txt` reports exit 0. Trusted `tests/final-002.txt` ran 306 tests,
seven skipped, and failed only the enabled L4 investigation after its 1200-second
operational bound (1208.949 seconds including cleanup).

The preserved native receipt at
`coding_pipeline/logs/manager/v0-l4-scientific-decisions-20261113T025828Z-9c0cb8e8/native-host/receipt.json`
shows repeated `Invalid immutable document ID` errors at proposal admission,
no designated opponent and confirmed owned cleanup. The initial recoverable
human-edit incorporation error was followed by the persistent link error.
The fixture's own `AGENTS.md` included `[numerical report](document:ID)`;
authoritative instructions are frozen with every proposal, so this literal
placeholder was treated as a real evidence dependency. The agents could not
repair that protected input, and no proposal reached independent opposition.
This was an engineering fixture failure, not a scientific stopping decision.

Replaced the malformed example with prose specifying the `document:` prefix
followed by an actual 64-character document identifier. No production code,
evidence validation, input freezing, isolation, quota policy or operational
bound changed. The fixture still requires real agent-authored science,
computations, independent challenge and authenticated terminal decisions.

An ungated regression imports the exact native questions/instructions, freezes
them through the Coordinator proposal control, checks their retained bytes and
hashes, verifies opponent scheduling, then exercises review/finalization through
a matching terminal acknowledgement. Scientific judgments, quota observations
and contexts are labelled engineering doubles, using the existing decision
fixture; this is not native scientific consensus. With the original instructions
from the failed native project, this test reproduced
`InputError: Invalid immutable document ID` before repair. With corrected
instructions it passes. Existing per-test cleanup runs on both paths.

Validation used the trusted Python and existing MCP dependencies:

```sh
export PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies
export RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0
export RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0
export RESEARCH_PIPELINE_M5_LIVE=0 RESEARCH_PIPELINE_V0_L1_NATIVE=0
export RESEARCH_PIPELINE_V0_L2_NATIVE=0 RESEARCH_PIPELINE_V0_L3_NATIVE=0
export RESEARCH_PIPELINE_V0_L4_NATIVE=0
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup tests.test_v0_l4_native -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
RESEARCH_PIPELINE_V0_L4_NATIVE=1 \
RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261113T025921_734d7f95/runtime/tmp/l4-integration-writer-native \
/home/francesco/miniconda3/bin/python -m unittest tests.test_v0_l4_native.NativeL4Tests -v
```

Focused verification: **75 tests, one skipped, 8.452 seconds, exit 0**.
Discovery: **307 tests, eight skipped, 19.299 seconds, exit 0**.
These include actual local process/descendant termination and partial-output
retention tests, not new native cgroup evidence. Private logs under this run's
`runtime/tmp/` are `l4-integration-before.txt`, `l4-integration-focused.txt`,
`l4-integration-discovery.txt` and `l4-integration-native.txt`.

The enabled Writer invocation ran one test and failed visibly at preflight,
exit 1, in 0.005 seconds: inherited `XDG_RUNTIME_DIR` and
`DBUS_SESSION_BUS_ADDRESS` are absent. The distinct failed receipt is
`runtime/tmp/l4-integration-writer-native/receipt.json`. No runtime, agents or
jobs were created; no native cleanup or scientific outcome is claimed. No
isolation/authentication workaround was attempted. Both the earlier timeout
receipt and this prerequisite receipt remain intact.

Successful enabled final/combined checks remain pending for the trusted host.
This repair is reviewable with that validation explicitly outstanding, not L4
acceptance. L5 recovery/reopening remains a separate dependency. README and
relevant indexes describe the failure, repair and remaining checks. No Git
orchestration, session management, remote action, protected input modification,
manager-owned STATUS.md change or human-requirement edit was performed.

## Milestone 3 integration-2 repair — manifest observation and job reports

Read the supplied plan, empty decisions/diff, baseline/final summary pages,
complete `tests/final-003.txt.commands/0001.txt`, earlier milestone decisions,
requirements and relevant implementation/tests before editing. The artifact
reader refused the command log and earlier decision pages; their read-only
filesystem copies were used. Final-003 ran **307 tests, seven skipped**, exit 1,
in **1069.842 test seconds** (1070.125 command seconds). Its sole reported failure
was the native observer comparing `None` with a frozen evidence manifest.

The preserved host receipt is
`coding_pipeline/logs/manager/v0-l4-scientific-decisions-20261113T025828Z-9c0cb8e8/native-host-70qv32u8/receipt.json`.
It records three proposals, the same logical opponent, delivered reviews,
acknowledged scientific COMPLETE and confirmed owned cleanup, but its overall
test outcome remains **failed**. Frozen manifests are JSON arrays;
`jobs.read` deliberately accepts only runtime JSON objects. The observer now
uses `json.loads` directly. Runtime reading/validation is unchanged. The existing
ungated exact-intake/finalization regression now calls the same packet observer
for both proposal and review, preserving manifest equality, version and every
evidence hash check. Before the reader fix it reproduced the reported assertion
without native inference; afterward it passes.

Read-only application of the corrected terminal assertions to retained host
evidence passed manifest checks, then exposed an additional unsatisfied numerical
provenance check. Both roles had written their reports directly under `/project`;
the numerical jobs had no retained job-document IDs. Later context snapshots
cannot establish the required job provenance. A separate retained-evidence
inspection confirms all **six** packet manifests/version digests/evidence hashes
pass, and the numerical-job assertion still rejects both roles. Neither the
receipt nor the science was modified or relabelled as passing.

Clarified the fixture instructions: the actual numerical job writes its report
under `/run/research-drafts/<task-workspace>/NUMERICAL_CHECK.md`, creates parents,
keeps code/data in its scoped `/project` workspace and links those dependencies
explicitly. Existing cleanup captures this private job batch as immutable
documents. The instructions still supply no scientific answer or judgment.
The numerical observer is shared with an ungated regression using real
`Documents.capture` and labelled report/job fixtures for primary and opponent.
It rejects missing job snapshots, failed/foreign jobs and mismatched report
hashes. Its first run exposed an invalid fixture task ID; the fixture now uses
the production task-ID shape. These are engineering checks, not new numerical
science or consensus. Production lifecycle, provenance requirements, isolation,
quota admission and operational bounds are unchanged.

Actual validation commands (the historical/native gates stay disabled except
for the explicitly enabled L4 prerequisite probe):

```sh
export PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies
export RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0
export RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0
export RESEARCH_PIPELINE_M5_LIVE=0 RESEARCH_PIPELINE_V0_L1_NATIVE=0
export RESEARCH_PIPELINE_V0_L2_NATIVE=0 RESEARCH_PIPELINE_V0_L3_NATIVE=0
export RESEARCH_PIPELINE_V0_L4_NATIVE=0
/home/francesco/miniconda3/bin/python -m unittest \
  tests.test_v0_l4 tests.test_v0_l4_cleanup tests.test_v0_l4_native -q
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
RESEARCH_PIPELINE_V0_L4_NATIVE=1 \
RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261113T025921_734d7f95/runtime/tmp/l4-integration2-writer-native \
/home/francesco/miniconda3/bin/python -m unittest tests.test_v0_l4_native.NativeL4Tests -v
```

Final focused checks: **76 tests, one skipped, 8.349 seconds, exit 0**.
Full discovery: **308 tests, eight skipped, 18.876 seconds, exit 0**.
These include actual local process/descendant interruption and partial-output
retention, not fresh native cgroup observations. Logs under this run's
`runtime/tmp/`: `l4-integration2-before.txt` (expected manifest reproduction),
`l4-integration2-focused-final.txt` (initial invalid task-ID fixture failure),
`l4-integration2-focused-passed.txt`, `l4-integration2-discovery.txt`,
`l4-integration2-retained-assertions.txt` (revealed missing numerical provenance)
and `l4-integration2-retained-packets.txt` (read-only packet checks).

The enabled Writer probe ran **one test**, failed visibly at preflight,
**0.012 seconds, exit 1**, because inherited `XDG_RUNTIME_DIR` and
`DBUS_SESSION_BUS_ADDRESS` are absent. Its distinct failed receipt is
`runtime/tmp/l4-integration2-writer-native/receipt.json`, log
`runtime/tmp/l4-integration2-native.txt`. No runtime, agent or job was created,
so no fresh cleanup or native scientific outcome is claimed. The receipt
confirms preserved engineering-root markers; no bus or authentication bypass
was attempted.

Fresh enabled trusted final/combined verification and independent review remain
required. In particular, the clarified numerical-report instructions still need
actual native validation. Retained evidence inspection cannot replace that gate
or accept the failed run. L5 reopening/recovery remains a separate dependency.
README and relevant indexes are updated. No Git orchestration or new refs,
session/permission/budget management, remote actions, manager-owned STATUS.md
edits, protected scientific-input edits or human-requirement edits were performed.
