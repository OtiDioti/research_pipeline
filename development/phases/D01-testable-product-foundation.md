# D01 — Testable product foundation

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Create a minimal, worktree-local Python package and meaningful validation infrastructure through one CWI implementation milestone.

**Dependencies:** D00

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

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

Use [REQ-D01-001](../requests/REQ-D01-001.md) after D00. One internal CWI milestone establishes the complete minimal foundation; the coordinator then requests human inspection of the accepted-unmerged result. The phase remains incomplete until authorized integration and evidence recording.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).
