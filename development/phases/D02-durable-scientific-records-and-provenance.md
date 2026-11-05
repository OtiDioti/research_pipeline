# D02 — Durable scientific records and provenance

**State:** PARTIAL; downstream Source/corpus/project-intake contracts are integrated at d8dffdd/7d6dd624/9373860 with ten typed kinds and396/396 target tests; latest phase-specific REQ-D02-007 INTEGRATED at 1296c93f1bffa306d04a7b240241a5b85275335b; REQ-D02-006 INTEGRATED at a56111f3e531b392ac997a6689944ec0820f151a; REQ-D02-005-R1 INTEGRATED at a5bba690a6c7e7113a92f34cc99efffc7a8c5656; REQ-D02-001 INTEGRATED at b51e421626f9fe6ffe8ca76dfe3f7267e689c82d; REQ-D02-002 backup/restoration INTEGRATED at 645c118a9846b23a3c410bc1a9fe7742f58846bc; REQ-D02-003 typed scientific content/admission is INTEGRATED at 22b863b1aabc5b3681c33800025f539c500462ca.

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

[REQ-D02-005-R1 evidence](../runs/8dc45005-5187-4be0-a009-dece7c493f2b.md): accepted/integrated a5bba690a6c7e7113a92f34cc99efffc7a8c5656, 204/204 target tests, two milestones and one resolved test-fixture identity repair. Six typed kinds preserve attributed independent dimensions, disagreements, exact route-conclusion membership and actual transactional/restart/backup behavior. No current eligibility or scientific authority is inferred. Both earlier terminal attempts remain preserved.

Prepared next: [REQ-D02-006](../requests/REQ-D02-006.md), at most three milestones for typed work-product bundles, safe durable checkout and preview/CAS import. This is a concrete R-008/R-019/R-028/R-030 dependency for D03 authoring. Support/eligibility freshness, authority/fencing/resources and remaining core payloads remain owned and pending; independent bundle work does not complete or waive them.

[REQ-D02-006 evidence](../runs/2b6ed304-5044-45b5-adcd-a8be9c3e314d.md): finally accepted/exact-integrated a56111f3e531b392ac997a6689944ec0820f151a,291/291 clean target tests, three milestones/zero repairs. Seven typed kinds now include work-product manifests; real durable checkout, bounded previews and saved explicit CAS proposals have mutation/interruption/backup evidence. D02 remains PARTIAL: eligibility/invalidation, authority/fencing/resources, other payloads and full scientific/operational behavior remain required. Independent REQ-D03-001 source capture consumes this evidenced subset without declaring the mixed phase complete.

Cross-phase evidence, 2026-10-31: [REQ-D03-001](../runs/7b46536e-42ac-4537-a720-beaaa5a34490.md) adds the eighth typed Source contract and exact durable admission/history, integrated d8dffdd with 343/343 target tests. This advances shared R-008/R-019 storage obligations without completing D02 current eligibility, authority/fencing/resources or other core semantic payloads.

## Corpus integration checkpoint — 2026-10-31

REQ-D03-002 is accepted/exact-integrated at 7d6dd6246e47ace09ff44a1decef14c93251f0ac, final receipt 47a10bdb59044535aba14572e86164abb22ed56c8704e6be7ea58146c6d53785, 369/369 target tests; [run evidence](../runs/f746e33a-7475-44dc-b8bf-4613130fba79.md). The ninth typed contract preserves exact seed inventories, original baseline and replacement history, per-entry Source locations, unresolved links and attributed partial observations with actual restart/recovery/backup evidence. One safe-directory fixture/example repair preserved production safeguards. Overall phase remains PARTIAL: project/intake/readiness, authorized admission, full vault layout/generation/edit protection, remaining core/authority/resource contracts and scientific evaluation are not completed. Next bounded [REQ-D03-003](../requests/REQ-D03-003.md) prepares versioned project/intake dossiers; proposed readiness is not an operational grant.

## Project/intake engineering checkpoint — 2026-10-31

[REQ-D03-003 evidence](../runs/db2829bc-fca9-48d7-b2c1-b9e99348c197.md) records exact project history, corpus/document/location coherence and proposal-only readiness at9373860,396/396 target tests. Existing storage/reconciliation/CAS/backup/migration contracts remain intact; meaningful process-fault and retry cases cover the new kind. D02 stays PARTIAL: current eligibility, authority/fencing/resources and full core lifecycle remain required. Next REQ-D03-004 consumes consistent read/storage contracts for local readable snapshots; scientific holds remain unchanged.

## Transactional claim-use freshness checkpoint — 2026-11-05

[REQ-D02-007 / run 8715d97e](../runs/8715d97e-341b-450a-8281-4760a34ba2cb.md) is finally accepted, exact-integrated and target-validated at `1296c93f1bffa306d04a7b240241a5b85275335b`, 1435/1435. Its explicitly registered use bindings and synchronous Review/Issue-driven reassessment generations advance the phase's atomic freshness gate; exact historical pins and backup/migration/recovery remain preserved. It does not certify positive eligibility, an alternative route's sufficiency, policy/context-change freshness or promotion. The phase stays PARTIAL, and the unchecked withdrawal/independent-support obligation above remains open for authenticated sufficiency and full alternative semantics. M0-S, full core records, operational authority and scientific evaluation remain pending. The human directed shutdown after this checkpoint; no new phase/request was started.

## Policy freshness checkpoint — 2026-11-05

[REQ-D02-008/run c255a52f](../runs/c255a52f-4034-46dd-b2ff-69e046e7814a.md) accepted/exact-integrated `ba6bdf39f713cdafab476985c8738267fc9b7dcc`, final/target1470/1470. Explicit schema5 activation/migration, selective historical downstream policy impact and coherent metadata inspection extend R-015/R-077 engineering only. Authority, positive eligibility, sufficient alternatives, active-context transfer, promotion and scientific evaluation remain pending. D02 remains PARTIAL. Human-directed shutdown; no new request/phase started.

## Target-context freshness selected — 2026-11-05

After REQ-D02-008 exact integration and required1470/1470 target evidence, [REQ-D02-009](../requests/REQ-D02-009.md) is the next bounded engineering slice: explicitly pinned target-context successor impact, historical downstream propagation and coherent bound/observed pins. It is prepared, not implemented/accepted. Broader context dependency/active-context selection, scientific transfer, sufficient alternatives, authority and promotion remain mandatory. D02 stays PARTIAL.
