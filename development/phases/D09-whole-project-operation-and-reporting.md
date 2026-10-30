# D09 — Whole-project operation and reporting

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Make the workbench inspectable, restorable, and usable for complete investigations under explicit human authority.

**Dependencies:** D08

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

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

## Reconciled v1.3 gate — Current scientific synthesis and portable evidence

**Requirement ownership:** R-005, R-019, R-027, R-030–R-031, R-051–R-053, R-069, R-082–R-086, R-092. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

Build richer synthesis on D04 minimum reports; narrative never grants promotion and falls back to deterministic report when unavailable. Audit exact current claims, conditions, figures/data/generators, citations and objections. Provide all CLI operations, concrete human decisions, reference-aware retention, consistent restore, and reuse-restricted portable exports readable without the live database. Preserve report history and later job/liability revisions.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.
