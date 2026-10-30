# D01 — Testable product foundation

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Create a minimal, worktree-local Python package and meaningful validation infrastructure through one CWI implementation milestone.

**Dependencies:** D00

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Implement the bounded first request REQ-D01-001, including the nested package, minimal CLI, documentation, and non-placeholder infrastructure tests.
2. Establish a deterministic permanent validator that loads the candidate source, rejects invalid root layout, fails on a failing/empty/all-skipped suite, and does not modify source.
3. Keep this phase honest: no scientific research capability, model provider, or generated claim is established yet.

## Acceptance obligations

- [ ] The exact candidate passes the independent frozen bootstrap check and the permanent validator.
- [ ] Behavioral tests exercise meaningful CLI and validation failure cases, not just importability or file presence.
- [ ] Final CWI acceptance, reviewed exact integration, and a post-integration evidence checkpoint are recorded. The accepted source differs from the documentation-only base.

## Important failure cases

- The baseline exception is mistakenly retained as a general empty-test allowance.
- Tests import an editable install from the original checkout instead of the private candidate.
- All tests are skipped, a normal Git worktree .git file is rejected, or the validator modifies source.

## Execution and evidence

Use [REQ-D01-001](../requests/REQ-D01-001.md) after D00. One internal CWI milestone establishes the complete minimal foundation; the coordinator inspects the accepted-unmerged result and may integrate it under AUTH-2026-10-30-001; this is not a completed human review. The phase remains incomplete until authorized integration and evidence recording.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Reconciled v1.3 gate — Foundation and subsequent M0 gate

**Requirement ownership:** R-001–R-007, R-088, R-093–R-094. All constituent obligations in those rows and cited original sections apply; no product evidence exists yet.

REQ-D01-001 delivers only R-007 and the development foundation. After accepted integration, complete the M0 gate: human pilot/envelope choice; expert-audited positive/negative development and held-out material; predeclared usefulness/error/resource standards; common schemas/message/eligibility/context/checkpoint/report/tool/vault contracts; one complete paper candidate/failure example. Administrative design may be coordinated directly; executable schemas, tests and runtime prompts require a new CWI request. R-001–R-003 are currently BLOCKED. D01 is not complete until this gate is evidenced; D02 depends on it.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.
