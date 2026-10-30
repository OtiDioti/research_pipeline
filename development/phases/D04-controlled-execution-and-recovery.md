# D04 — Controlled execution and recovery

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Run bounded research tasks with durable attempts, isolated workspaces, accounted resources, and conservative recovery.

**Dependencies:** D02, D03

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

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

## Reconciled v1.3 gate — Resource-safe execution and mandatory minimum closeout

**Requirement ownership:** R-009, R-016, R-018, R-020, R-032, R-036, R-038–R-053, R-082, R-092. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

Own the M2 minimum deterministic end-of-run report now, not in D09. Every admitted run has initial/checkpoint/stop snapshots, all §10.5 fields and a continuation manifest/home link. Test idempotent recovery from publication/storage failure and cancellation forbidding model calls. Define model limits/counting/normalized completion reasons; preserve truncated output, reject partial tool arguments. Enforce separate context/output/cumulative limits, verification/handoff/closeout reserves, uncertain liabilities, authority fencing and no-budget-reset continuation. Fresh attempts require valid checkpoint/fallback and new reservation.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.
