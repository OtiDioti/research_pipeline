# D10 — Scientific pilot and architecture evaluation

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Assess usefulness and reliability against a strong single-agent baseline before expanding autonomy.

**Dependencies:** D09

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Execute the narrow problem family and audited protocol chosen at the D01 M0 gate, including known results, flawed derivations, fresh expert-designed extensions and limited open investigations.
2. Compare matched tools, resources, and human review; ablate independent reconstruction and extra researchers.
3. Measure unsupported acceptance, false rejection, scope accuracy, reproducibility, useful progress, cost, and expert attention.
4. Report benchmark uncertainty and evaluation failures rather than treating the reference answers as infallible.

## Acceptance obligations

- [ ] The pilot contains both useful positive outputs and adversarial cases; indiscriminate refusal cannot count as success.
- [ ] Results and limitations are evidenced and reproducible; no claim of general autonomous research is inferred from a small pilot.
- [ ] Further model, tool, or concurrency expansion has an explicit evidence-based decision.

## Important failure cases

- Known-result memorization is mistaken for novelty.
- Budget matching excludes hidden nested agent/tool cost.
- Trivial claim splitting inflates output counts or subjective scoring hides unsupported conclusions.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Continuous-development boundary

The coordinator can implement evaluation machinery through CWI and run already authorized assessments. It cannot invent expert judgments, treat a mock provider as live evidence, or acquire unapproved external data/services. Missing scientific data, live-resource allowance, or human assessment becomes a precise obligation/hold, not a reason to claim the entire project complete. See [the completion gate](../AUTONOMY.md) and [report template](../templates/COMPLETION.md).

## Reconciled v1.3 gate — Actual scientific and usability evaluation

**Requirement ownership:** R-001–R-006, R-060, R-069, R-073–R-074, R-078, R-086–R-094. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

Use the pilot, expert fixtures and standards settled at D01; do not choose them after observing results. Execute all three evaluation tracks, all twelve §11.2 classes and all nineteen §11.6 scenarios. Compare matched total budgets including nested calls/tool development/reviewer effort; evaluate all fourteen metric families and valid nontrivial results. Zero endorsements give undefined error rate. Preserve unresolved judgments and held-out separation; real data/provider approval and human scientific/release acceptance remain required. No full-project completion without them.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.
