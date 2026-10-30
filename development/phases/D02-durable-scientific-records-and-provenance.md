# D02 — Durable scientific records and provenance

**State:** PARTIAL; REQ-D02-001 INTEGRATED at b51e421626f9fe6ffe8ca76dfe3f7267e689c82d; REQ-D02-002 backup/restoration INTEGRATED at 645c118a9846b23a3c410bc1a9fe7742f58846bc; REQ-D02-003 typed scientific content/admission is INTEGRATED at 22b863b1aabc5b3681c33800025f539c500462ca.

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

REQ-D02-002 has commissioned consistent local backup and verified restoration. Full §5.1 scientific kinds/fields, support alternatives and assessment/eligibility freshness, attempt fences, resource state, schema migrations and complete interrupted-run recovery remain pending. R-005/R-010–R-015/R-030 are not completed by generic envelopes.

[REQ-D02-002 evidence](../runs/2d82f186-4cf2-4fb7-9f96-f0ea8db10340.md): consistent version-1 snapshots, strict manifest/relational/application integrity, independent restore, retained incomplete-copy markers and fresh-process failures are accepted/integrated. Full suite 88/88. The original receipt identity survives lost acknowledgment, backup and restoration. General migrations, periodic scheduling and real run/session/job restoration remain pending. Next engineering focus is typed scientific content and relationship contracts, followed by assessment/eligibility and other §5.1 types; no scientific sufficiency is inferred.

Integrated request: [REQ-D02-003](../requests/REQ-D02-003.md), at most two internal milestones. It preserves legacy version-1 history/backup and commissions typed contexts/claims/justifications/evidence with exact semantic links and real persistence failures; assessment, eligibility and scientific sufficiency remain separate.

[REQ-D02-003 evidence](../runs/d7e765f5-9c2a-4d83-9703-73102ffb5891.md): four typed provisional payloads, exact coherent links and atomic target admission, 116/116 tests; two accepted milestones, no repairs. Remaining generic kinds/schema evolution and migration are the next bounded prerequisite. Full sufficient-support semantics, freshness and human scientific judgments remain pending.

Prepared next: [REQ-D02-004](../requests/REQ-D02-004.md), versioned generic core identities and explicit verified-backup migration, at most two milestones. Full typed authority/assessment payloads remain subsequent work, not claimed by generic names.

REQ-D02-004 attempt 1 stopped with no implementation on a documented validation-context mismatch; all migration outcomes remain pending. [R1](../requests/REQ-D02-004-R1.md) is the bounded evidence-based replacement after clean terminal disposition, with controller validation unchanged.

[REQ-D02-004-R1 evidence](../runs/25e5020e-e398-4998-b901-5268cd580778.md): finally accepted/integrated 06fc133, 169/169 target tests, two milestones/no repairs. Twenty generic core identities, dual exact backup formats and explicit verified v1→v2 restore preserve original records/receipts and refuse interrupted output. The earlier failed attempt is preserved; one validation-ownership recovery succeeded. This closes only the requested version-evolution subset. Full typed operational/review payloads, support/eligibility freshness, fences/resources and full run recovery remain required.

Prepared next: [REQ-D02-005](../requests/REQ-D02-005.md), typed attributed reviews/issues and durable exact admission, at most two milestones. This supplies the recorded assertions required before current eligibility/invalidation. Pure storage of a favorable review cannot confer endorsement or mark R-013/R-014/R-015 complete.

REQ-D02-005 attempt1 timed out after pure-contract edits, with no accepted milestone; main review/issue behavior remains pending. [Failure record](../runs/46114120-06d0-47ea-8e16-4a02066a1d0a.md) preserves the draft and advisory checks. [R1](../requests/REQ-D02-005-R1.md) retains both milestones under the explicit human 2700-second deadline extension, using frozen unaccepted draft context. No evidence gate is waived.
