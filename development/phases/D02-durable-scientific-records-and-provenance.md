# D02 — Durable scientific records and provenance

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Implement the smallest trustworthy storage core for versioned research objects and their justifications.

**Dependencies:** D01

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

## Outcomes

1. Define explicit versioned objects for project/model contexts, assumptions, claims, justifications, objections, evidence, tasks, decisions, and artifact references.
2. Implement transactional updates, stable IDs, immutable artifact integrity, event history, checkpoints, and selective dependency impact handling.
3. Keep task completion separate from claim support. Represent conjunctions of premises within one justification and alternative justifications separately.
4. Specify schema migration, corruption detection, and how stale assessment differs from a historically false claim.

## Acceptance obligations

- [ ] Round trips, rollback on interrupted writes, content integrity, and restart reconstruction are tested.
- [ ] Withdrawing one justification does not erase an independently supported claim; changed context invalidates only affected uses.
- [ ] A completed counterexample task can leave the target claim refuted rather than supported.

## Important failure cases

- Partial commit between metadata and artifact storage.
- Circular support, ambiguous version references, or silently overwritten history.
- An old review is applied to new premises or a different physical regime.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).
