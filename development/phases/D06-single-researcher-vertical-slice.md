# D06 — Single-researcher vertical slice

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Execute one bounded research investigation from seeds to a scoped candidate and an explicitly provisional synthesis.

**Dependencies:** D03, D04, D05

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

## Outcomes

1. Define a provider-independent model invocation contract; use deterministic responses first, then an explicitly authorized real adapter.
2. Implement literature search/capture/report states, source-version references, bounded paper inspection, derivation notes, LaTeX bundles, computational links, and failed-attempt memory.
3. Connect question formulation, baseline reproduction, coherent researcher sessions, candidate freezing, checkpoint notes, and unresolved outcomes.
4. Treat retrieved material as untrusted data and separate what a source states from what the system independently establishes.

## Acceptance obligations

- [ ] A fixture investigation produces linked notes, exact artifacts, a candidate, outstanding obligations, and reproducible continuation.
- [ ] A source is never described as read merely because it was downloaded; equation extraction uncertainty is visible.
- [ ] A live smoke test, when authorized, records cost and limitations separately from deterministic correctness tests.

## Important failure cases

- The researcher silently adds an assumption or reformulates the problem.
- LaTeX compiles but an unsupported mathematical step is marked established.
- A summary loses a critical qualification or replaces an exact source.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).
