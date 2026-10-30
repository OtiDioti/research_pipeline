# D02 — Durable scientific records and provenance

**State:** PARTIAL; REQ-D02-001 INTEGRATED at b51e421626f9fe6ffe8ca76dfe3f7267e689c82d; READY for REQ-D02-002 backup/restoration.

**Goal:** Implement the smallest trustworthy storage core for versioned research objects and their justifications.

**Dependencies:** D01 foundation plus settled M0-E storage contract; first bounded D02 slice commissions its executable evidence. M0-S is not a blanket engineering prerequisite.

**Specification:** [project_description.md](../../project_description.md), v1.4, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Define explicit versioned objects for project/model contexts, assumptions, claims, justifications, objections, evidence, tasks, decisions, and artifact references.
2. Implement transactional updates, stable IDs, immutable artifact integrity, event history, checkpoints, and selective dependency impact handling.
3. Keep task completion separate from claim support. Represent conjunctions of premises within one justification and alternative justifications separately.
4. Specify schema migration, corruption detection, and how stale assessment differs from a historically false claim.

## Acceptance obligations

- [x] Initial five-kind storage slice: round trips, rollback on interrupted writes, content integrity, and fresh-process restart are tested. Full scientific schemas and product run recovery remain pending.
- [ ] Withdrawing one justification does not erase an independently supported claim; changed context invalidates only affected uses.
- [ ] A completed counterexample task can leave the target claim refuted rather than supported.

## Important failure cases

- Partial commit between metadata and artifact storage.
- Circular support, ambiguous version references, or silently overwritten history.
- An old review is applied to new premises or a different physical regime.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Current v1.4 gate — Durable record and atomic freshness gates

**Requirement ownership:** R-005, R-008–R-019, R-030. All constituent obligations in those rows and cited original sections apply; the initial slice below is partial evidence, not blanket completion.

Implement every record kind in §5.1 and narrow operations in §10.1, not just claims. Preserve artifact-before-metadata ordering, submission idempotency, lease fencing, migrations, and separate support/assessment/issue revisions. Assessment changes synchronously invalidate eligibility; alternative support survives only when already assessed sufficient. Foundations for backup and restoration begin here. Dependency: relevant M0-E contracts, accepted/integrated executable subset before downstream reliance. REQ-D02-001 begins envelope/artifact/transaction storage; full scientific records, eligibility, fencing and migration remain subsequent work.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.

## Engineering and scientific acceptance tracked separately

Under specification v1.4, relevant implemented predecessor contracts and deterministic/fault evidence gate engineering. M0-E is evidenced per consumed contract, not completed by this plan. M0-S (R-001–R-003) and live interoperability remain pending until actual approvals/evidence exist; they block only the affected scientific evaluations, qualification claims and final release. An engineering-complete subset may enable subsequent independent work while the whole mixed phase remains partial. No exposed development fixture becomes held-out evidence, and scientific standards must precede scored evaluation.

## Integrated initial slice and next request

[REQ-D02-001 evidence](../runs/77ab31a1-a7c2-4185-a26b-f9ed52da1593.md): two milestones, one resolved Unicode serialization repair, final source b51e421626f9fe6ffe8ca76dfe3f7267e689c82d, exact integration and 72/72 post-integration tests. Five common envelopes, immutable artifacts and atomic/idempotent SQLite revisions/links/receipts/events now exist. Stale-write, missing/corrupt artifact, rollback, hot-journal recovery and post-commit lost-acknowledgment cases use real storage/fresh processes.

REQ-D02-002 next commissions consistent local backup and verified restoration. Full §5.1 scientific kinds/fields, support alternatives and assessment/eligibility freshness, attempt fences, resource state, schema migrations and complete interrupted-run recovery remain pending. R-005/R-010–R-015/R-030 are not completed by generic envelopes.
