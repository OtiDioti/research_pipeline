# D07 — Independent verification and scoped acceptance

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Make candidate acceptance depend on appropriately independent, claim-specific evidence and current support.

**Dependencies:** D06

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Implement answer-blind, proof-blind, and informed review assignments with actual file/context filtering, not only prompt instructions.
2. Preserve reconstruction before disclosure; assess mathematical validity, numerical evidence, physical applicability, and novelty separately.
3. Enforce configured verification obligations, exact candidate versions, fresh support checks, disagreement handling, and human decisions for consequential conclusions.
4. Use method-specific checks for existence, domains, approximations, limiting behavior, physical constraints, convergence, and statistical selection where relevant.

## Acceptance obligations

- [ ] Deliberately flawed derivations are rejected for the right reasons, while valid scoped conclusions can be accepted.
- [ ] Candidate information cannot leak through reports, indexes, paths, tool examples, or notebooks supplied to a blind checker.
- [ ] Support withdrawn between review and promotion prevents stale acceptance; an alternative valid justification is preserved.

## Important failure cases

- Reviewer sees the answer through navigation metadata.
- A successful numerical or formal check is treated as proof of a different physical statement.
- The system avoids false claims only by refusing all useful results.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Reconciled v1.3 gate — Actual independence and atomic disposition

**Requirement ownership:** R-005, R-012–R-016, R-034, R-038, R-040, R-057, R-062, R-065, R-070–R-078, R-083, R-088, R-092. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

Exercise every §6.6 leakage surface, including inherited checkpoints, context-selection metadata, seed solutions and tool fixtures. Commit reconstruction before disclosure, preserve shared-dependency labels and reviewer errors. Test support withdrawal/policy/context changes between review and promotion. Apply all relevant scientific check classes, statistical selection controls and independent tool qualification. Human major-conclusion decisions and expert fixture judgments cannot be simulated as completed evidence.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.
