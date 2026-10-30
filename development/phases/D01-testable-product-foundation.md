# D01 — Testable product foundation

**State:** PARTIAL / HOLD — REQUIRED_HUMAN_SCIENTIFIC_JUDGMENT. REQ-D01-001 integrated at 7d5acab and REQ-D01-002 at 79a84d2; M0 remains incomplete.

**Goal:** Create a minimal, worktree-local Python package and meaningful validation infrastructure through one CWI implementation milestone.

**Dependencies:** D00

**Specification:** [project_description.md](../../project_description.md), v1.3, reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md).

## Outcomes

1. Implement the bounded first request REQ-D01-001, including the nested package, minimal CLI, documentation, and non-placeholder infrastructure tests.
2. Establish a deterministic permanent validator that loads the candidate source, rejects invalid root layout, fails on a failing/empty/all-skipped suite, and does not modify source.
3. Keep this phase honest: no scientific research capability, model provider, or generated claim is established yet.

## Acceptance obligations

- [x] The exact candidate passes the independent frozen bootstrap check and the permanent validator.
- [x] Behavioral tests exercise meaningful CLI and validation failure cases, not just importability or file presence.
- [x] Final CWI acceptance, reviewed exact integration, and a post-integration evidence checkpoint are recorded. The accepted source differs from the documentation-only base.

## Important failure cases

- The baseline exception is mistakenly retained as a general empty-test allowance.
- Tests import an editable install from the original checkout instead of the private candidate.
- All tests are skipped, a normal Git worktree .git file is rejected, or the validator modifies source.

## Execution and evidence

Use [REQ-D01-001](../requests/REQ-D01-001.md) after D00. One internal CWI milestone establishes the complete minimal foundation; the coordinator inspects the accepted-unmerged result and may integrate it under AUTH-2026-10-30-001; this is not a completed human review. The phase remains incomplete until authorized integration and evidence recording.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Reconciled v1.3 gate — Foundation and subsequent M0 gate

**Requirement ownership:** R-001–R-007, R-088, R-093–R-094. All constituent obligations apply; R-007 is integrated, other coverage remains partial or absent.

REQ-D01-001 delivers only R-007 and the development foundation. After accepted integration, complete the M0 gate: human pilot/envelope choice; expert-audited positive/negative development and held-out material; predeclared usefulness/error/resource standards; common schemas/message/eligibility/context/checkpoint/report/tool/vault contracts; one complete paper candidate/failure example. Administrative design may be coordinated directly; executable schemas, tests and runtime prompts require a new CWI request. R-001–R-003 are currently BLOCKED. D01 is not complete until this gate is evidenced; D02 depends on it.

- [ ] Link each owned obligation to executed checks/reviews and exact accepted/integrated source.
- [ ] Preserve any missing live, expert or human evidence as an explicit blocker; do not infer it from fixture success.

## Current evidence and next bounded work

[REQ-D01-001 run](../runs/47d6ef06-c251-4a0d-bb2c-da2059d9360f.md): 19 meaningful tests, bootstrap and permanent validation, exact fast-forward, target validation. The continuous envelope is activated.

The human requested a mock of the harmonic/quartic example. [REQ-D01-002](../requests/REQ-D01-002.md) delivered synthetic initial fixture material and a reviewable paper walkthrough without claiming live calculations or expert audit. It is independent preparatory M0 work. Human pilot/usefulness decisions, audited reference collection and predeclared scientific standards remain required before D02; the mock cannot complete those obligations.

REQ-D01-002 [final evidence](../runs/34bcb77d-1cbc-4432-ba5e-e419e930ad2f.md): 26 synthetic records, focused loader and adverse tests, full walkthrough; 28/28 suite after exact integration. [M0 contract/decision packet](../decisions/M0-contract-and-scientific-review.md) now proposes all general contract responsibilities and the evaluation framework. It is administrative design, not runtime implementation or expert approval. Required pilot/usefulness, audited references and predeclared standards are absent; no further dependent production request is ready. The next safe action is the human scientific decision described in STATUS.
