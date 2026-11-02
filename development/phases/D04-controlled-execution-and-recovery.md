# D04 — Controlled execution and recovery

**State:** PARTIAL. Resource accounting, committed-report/publication/recovery and authenticated local operating-decision/readiness foundations are finally accepted and integrated. REQ-D04-004 is ready for durable run/report lifecycle and pending recovery gates. Queue/attempt/fencing,actual admission/dispatch and worker/context/tool/model enforcement remain unimplemented.

**Goal:** Run bounded research tasks with durable attempts, isolated workspaces, accounted resources, and conservative recovery.

**Dependencies:** D02, D03 engineering contracts actually needed by the next request; empirical acceptance is tracked separately.

**Specification:** [project_description.md](../../project_description.md), v1.4, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Implement task dependencies, attempts, dispatch interfaces, cancellation, checkpointing, deadlines, resource reservations, and one-writer persistence rules.
2. Record exact input versions, permitted visibility, execution identity, artifacts, and communications per attempt.
3. Separate scheduling decisions from deterministic authorization. Retain uncertain in-flight costs and side effects until reconciled.
4. Start with fixture workers and bounded local execution rather than distributed orchestration.

## Acceptance obligations

- [ ] A controlled end-to-end fixture survives injected interruption without duplicate work or false completion.
- [ ] Cancellation is distinguished from observed process termination; budgets cover nested work.
- [ ] A session can be replaced using durable notes and evidence without losing scientific context.

## Important failure cases

- Process disappears while external computation continues.
- A worker submits stale evidence after an assumption changes.
- A retry exceeds the remaining budget or replays an uncertain side effect.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Current v1.4 gate — Resource-safe execution and mandatory minimum closeout

**Requirement ownership:** R-009, R-016, R-018, R-020, R-032, R-036, R-038–R-053, R-082, R-092. All constituent obligations remain; bounded resource-accounting evidence is below and the remaining obligations are open.

Own the M2 minimum deterministic end-of-run report now, not in D09. Every admitted run has initial/checkpoint/stop snapshots, all §10.5 fields and a continuation manifest/home link. Test idempotent recovery from publication/storage failure and cancellation forbidding model calls. Define model limits/counting/normalized completion reasons; preserve truncated output, reject partial tool arguments. Enforce separate context/output/cumulative limits, verification/handoff/closeout reserves, uncertain liabilities, authority fencing and no-budget-reset continuation. Fresh attempts require valid checkpoint/fallback and new reservation.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.

## Engineering and scientific acceptance tracked separately

Under specification v1.4, relevant implemented predecessor contracts and deterministic/fault evidence gate engineering. M0-E is evidenced per consumed contract, not completed by this plan. M0-S (R-001–R-003) and live interoperability remain pending until actual approvals/evidence exist; they block only the affected scientific evaluations, qualification claims and final release. An engineering-complete subset may enable subsequent independent work while the whole mixed phase remains partial. No exposed development fixture becomes held-out evidence, and scientific standards must precede scored evaluation.

## First ready boundary — durable resource accounting

[REQ-D04-001](../requests/REQ-D04-001.md) consumes accepted durable SQLite/history/artifact/backup/migration and project/task reference contracts through integrated3f4564c. Two meaningful milestones cover strict opt-in schema3 with preserved historical migration/backup, atomic protected hierarchy reservations, then attributed usage/uncertainty/settlement/breach and recovery. Preserve defaultschema2. Existing scientific records and view contracts remain intact. Request preparation does not authenticate operating authority, admit research, implement lease fencing/dispatch/context, or satisfy mandatory model-independent initial/checkpoint/stop reports. Those are subsequent mandatory engineering boundaries. Scientific/live-provider approvals still gate their dependent work only.

## Resource accounting evidenced; report primitive next

REQ-D04-001 / CWI 6eaf6f92-ec81-4d73-b83d-9b97a30cfb02 is finally accepted and exact-integrated at b13fff0a2e26acba9b4b9bad3dde430207e4eaab, tree 202546e8128e7c7f31b7e6f5be86f4028656764f, final receipt f37a74adf475689ab0110ccc7e37095c2fe5c48fea996f322457c4c55d2f58ce. Final controller 778/778 in 496.704s; integrated target 778/778 in 495.886s, zero skips/failures/errors and unchanged clean source. Target completed 2026-11-01T03:34:59.250932+00:00, stdout SHA-256 ef9b8636d8d14e4414e348652585f6c6ef551c1d211127ee92fe3feebd426c4f, empty stderr. [Run evidence](../runs/6eaf6f92-ec81-4d73-b83d-9b97a30cfb02.md). Strict opt-in schema 3, verified 2→3 backup migration, protected hierarchical reservations, attributed partial/complete usage, conservative/authoritative settlement, exact retries, sticky breach gates, coherent snapshot 2 and crash/reopen/backup recovery are evidenced. Default schema 2, old DDL/migrations and scientific records/artifacts remain intact. Resource declarations do not authenticate grants, admit research or establish service-enforced caps. Actual authority/readiness, lifecycle/fencing, dispatch, model/tool/context, mandatory reporting hooks and scientific qualification remain required.

[REQ-D04-002](../requests/REQ-D04-002.md) next provides persisted report inputs/coherent capture, seven content groups, deterministic rendering and immutable publication/recovery. It does not supply automatic per-admitted-run guarantees before lifecycle integration; phase boxes remain unchecked.


## Human-requested shutdown — 2026-11-01

REQ-D04-002 / CWI 6ae8ca11-0df2-48e2-abc8-65d51adaa187 was stopped at the human’s explicit resource-conservation request. Provisional 2e4343890e519075915e2d25b4bf18875d2ef8a9 passed 806/806 controller tests and the complete-base diff check; first-milestone Reviewer was cancelled, zero milestones/final receipts exist, and nothing from this request was integrated. STOPPED_INCOMPLETE, no lease/quarantine/live execution; retained pending_authoritative_operation is a recovery record, not a running process. CWI says resume_allowed=false and new_run_after_manual_salvage. Preserve the candidate and all old work; do not replay/resume or start another workflow in this session.

Phase remains PARTIAL. Preserve the capture draft for future CWI-only salvage and review; immutable report publication/navigation has not begun. Current session must stop; future execution grant remains subject to reconciliation and resources. See [run record](../runs/6ae8ca11-0df2-48e2-abc8-65d51adaa187.md) and local/live.md.

## Resumed reporting boundary — 2026-11-02

The human resumed engineering after the shutdown. [REQ-D04-002-R1](../requests/REQ-D04-002-R1.md) is prepared with byte-exact unaccepted draft context for fresh CWI-only implementation/review and completion of publication/navigation. All first-milestone semantics and full original criteria remain; persistent late-usage reporting coverage must close the recorded gap. No new acceptance or phase completion exists yet. Automatic lifecycle/report hooks, readiness/authority/fencing and dispatch remain subsequent mandatory prerequisites.

## Publication recovery — 2026-11-02

REQ-D04-002-R1 capture milestone acceptedadb1b439 (811/811) but publication Writer timed out after2700 seconds. No final acceptance or integration; terminal owners resolved and no resume allowed. [REQ-D04-002-R2](../requests/REQ-D04-002-R2.md) is the one-milestone, last permitted deadline recovery using exact preserved capture/publication reference plus confirmed metadata-bound correction. Full original criteria/checks/reviews remain. Phase acceptance boxes remain unchecked and all automatic lifecycle/readiness/fencing obligations remain mandatory.

## Compact review recovery — 2026-11-02

R2 Writer completed within deadline; exact complete candidatebdcbd679 passed845/845, but CWI stopped before Reviewer on combined prompt size. No final acceptance/integration. [R3](../requests/REQ-D04-002-R3.md) freezes compact immutable source identities, with full diff/criteria/checks still required. Context recovery1/2 is distinct from exhausted deadline2/2. No phase box is checked; lifecycle/authority/report admission gates and scientific obligations remain open.


## Reporting foundation integrated; authority prerequisite next — 2026-11-02

[Run 528cf918-2619-45c8-a6b6-ee35ed42fb3e](../runs/528cf918-2619-45c8-a6b6-ee35ed42fb3e.md) finally accepted/exact-integrated7a1edeb8, final receipt851d915f2588097602250ddcfe671586a90e65d802165df72227057a02cb69db; final/target845/845, zero skips/errors/failures/source mutation. Coherent report capture, deterministic seven-group output, complete historical navigation and offline original-plan publication/refresh recovery are delivered. Automatic initial/checkpoint/stop hooks and pending-report restart gates remain unimplemented and required before admitted execution.

[REQ-D04-003](../requests/REQ-D04-003.md) delivers bounded authenticated operator decisions and exact readiness with synthetic credentials/fixtures. It does not dispatch research or certify science. Queue/attempt lifecycle, fencing and transactional authority/resource/report admission follow. Acceptance boxes stay unchecked; M0-S remains pending and gates dependent scientific work only.


## Authority acceptance recovery — 2026-11-02

REQ-D04-003/run5f304a70 retained231c712e (876/876, diff clean) after two repairs, then nonreplayable Reviewer capacity failure. Zero accepted milestones/final receipts/integration; phase boxes stay unchecked. Verified terminal no-owner/lease/quarantine evidence permits REQ-D04-003-R1 compact immutable source reuse through a fresh CWI-only workflow. All original criteria and formally open F001–F005 remain. Provider capacity1/2, cumulative coordinator8; no model/backend/security/authority change or reset of exhausted deadline2/2. Lifecycle/report restart gates and subsequent admission/fencing remain mandatory after actual authority integration.

## Authority integrated; lifecycle commissioned next — 2026-11-02

REQ-D04-003-R1/runf14139d7 finally accepted/exact-integrated27638a93/tree17ba0d7b,final receiptc58ce255;repaired candidate883/8831004.278s,final883/8831006.217s,target883/8831005.220s,zero skips/errors/failures/source mutation. Target ended15:50:26.430627Z,stdout4df8faa7,empty stderr. [Exact run evidence](../runs/f14139d7-a856-4b5a-986a-df5014792800.md). One CWI repair adds independent detached-retention reservations before constructors and7meaningful boundaries. Operator HMAC policy/decision history,current exact eligibility,reductions despite missing old artifacts,original-operation recovery and backup/current-policy limits are implemented. No scientific admission or actual worker isolation is claimed.

REQ-D04-004 scopes at most2safe milestones for typed run/report obligations then deterministic automatic lifecycle publication/recovery and pending-report gates. Control preparation never implies actual scientific dispatch; later queue/reservation/fencing and tool/context/model boundaries remain required. All phase-completion boxes stay unchanged. Scientific/live M0-S dependencies remain separate.
