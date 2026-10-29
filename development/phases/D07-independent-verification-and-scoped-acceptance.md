# D07 — Independent verification and scoped acceptance

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Make candidate acceptance depend on appropriately independent, claim-specific evidence and current support.

**Dependencies:** D06

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

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
