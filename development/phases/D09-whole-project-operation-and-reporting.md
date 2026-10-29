# D09 — Whole-project operation and reporting

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Make the workbench inspectable, restorable, and usable for complete investigations under explicit human authority.

**Dependencies:** D08

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

## Outcomes

1. Complete evidence-linked progress and final reports, manuscript/LaTeX exports, consistent snapshots, restore procedures, and scientific stopping conditions.
2. Expose navigation from results to assumptions, derivations, code, source captures, reviews, and objections; audit human edits and missing data.
3. Exercise data retention, secrets handling, user authorization, resource ceilings, and whole-project consistency.

## Acceptance obligations

- [ ] A frozen project can be restored and independently navigated; interrupted-state ambiguity remains explicit.
- [ ] Reports distinguish supported, conditional, numerical, conjectural, refuted, and unresolved conclusions.
- [ ] A human can find the next scientific decision and inspect its evidence without reading raw execution logs.

## Important failure cases

- A filesystem sync yields an inconsistent database/artifact snapshot.
- An export omits a decisive objection or exposes credentials/private papers contrary to policy.
- A report implies a general result from finite-range evidence.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).
