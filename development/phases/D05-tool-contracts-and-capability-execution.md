# D05 — Tool contracts and capability execution

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Support optional bundled, supplied, and research-generated tools without coupling the product to one tool set.

**Dependencies:** D04

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Implement capability needs, versioned manifests, input/output domains, permissions, resource contracts, and exact invocation evidence.
2. Separate permission to run, software qualification, scientific domain applicability, and the support provided by a particular output.
3. Support simple programs and bounded adapters; treat opaque services and composite workflows explicitly rather than assuming source code or unlimited recursive delegation.
4. Allow a missing capability to trigger an alternative method, a development/integration proposal, or a blocked task.

## Acceptance obligations

- [ ] A deterministic local fixture tool can be registered, qualified for a limited domain, run under policy, and linked to evidence.
- [ ] An unavailable or unqualified capability produces an honest controlled outcome.
- [ ] Version changes, permission denial, timeout, nested costs, and output provenance are tested. No particular symbolic or coding tool is mandatory.

## Important failure cases

- Tool success is interpreted as scientific correctness.
- Outputs from one tool release are attributed to another.
- A nested workflow exceeds budget, escapes its workspace, or cannot demonstrate cancellation.

## Execution and evidence

Before execution, divide these outcomes into the smallest coherent requests with independently testable results. Do not invent every function signature months ahead of its dependencies. The active request fixes its public interfaces, exact changed paths, validation, scope, and stop conditions before CWI starts. A phase may require multiple runs. Record each final receipt/source pair, integration commit, requirement evidence, limitations, and newly deferred items.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Reconciled v1.3 gate — Tool releases and bounded adapter boundary

**Requirement ownership:** R-029, R-040, R-043–R-044, R-054–R-060, R-064, R-082, R-092. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

Complete all release manifest and lifecycle fields in §§10.6–10.8. Distinguish execution permission/qualification/lifecycle, scientific semantics/schema shape and live observed versions/pinned local code. Demonstrate actual isolated local execution and authentic receipts. Register representative fixtures without requiring a user tool. Define optional delegated-job boundaries and descendant accounting; do not claim named compatibility without real qualified execution. Restricted TeX rendering must preserve source on build failure.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.
