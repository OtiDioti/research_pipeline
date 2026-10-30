# D00 — Specification and operating readiness

**State:** NOT_STARTED. This plan is a proposed scope, not execution evidence.

**Goal:** Reconcile the exact local product specification and establish an honest, reproducible development environment.

**Dependencies:** None; inspect the actual repository first.

**Specification:** [project_description.md](../../project_description.md), with exact references to be reconciled in [REQUIREMENTS.md](../REQUIREMENTS.md) during D00.

## Outcomes

1. Read the full existing project_description.md; enumerate every mandatory requirement, its source location, dependencies, planned phase, and eventual evidence in development/REQUIREMENTS.md.
2. Inspect the real target Git repository and any prior CWI state. Confirm initial branch/commit, supported untracked coding_pipeline clone, local excludes, installed versions, credentials, and launch permissions.
3. Review the supplied-backend audit and reproduce relevant failures locally. Record unresolved backend risks. Only a demonstrated necessary defect permits the focused direct repair exception in BACKEND_MAINTENANCE.md; preserve evidence, test the smallest fix, and audit every attempt. Do not preemptively change the backend.
4. Confirm or revise the proposed Python/stdlib foundation, explicit-check strategy, phase scopes, resource envelope, and first-run integration policy. Commit the administrative prelaunch checkpoint.

## Acceptance obligations

- [ ] Every mandatory requirement has a disposition: assigned, deliberately deferred with authorization, or blocking. No silent requirement deletion.
- [ ] The baseline contains only tracked Markdown; the frozen bootstrap baseline passes and its strict candidate branch has been inspected.
- [ ] CWI help/version/compatibility and required real Codex authentication are checked locally. Report any limitation as a blocker or explicitly accepted, bounded risk.
- [ ] The first request has measurable acceptance criteria and no unresolved material design choice.

## Important failure cases

- A previously active run is discovered; do not start a competing run.
- The local controller differs from the audited snapshot; assess the difference rather than assume equivalence.
- Required Codex flags or authenticated transport are unavailable; do not replace CWI with direct coding.

## Execution and evidence

This is administrative planning and environment inspection. Product code is not written here. Do not create a product skeleton to make CWI preflight convenient. Use the reviewed bootstrap procedure. Record verification evidence and unresolved risks in the environment record, requirements map, and decisions.

Operational details: [runbook](../RUNBOOK.md), [request template](../templates/REQUEST.md), [run record](../templates/RUN.md).

## Additional readiness obligations for continuous development

- Resolve the requested Astra 6.1 identifier/access, explicit supported effort and xhigh ceiling, billing mode, and invocation evidence under [MODEL_POLICY.md](../MODEL_POLICY.md). Unresolved identity blocks calls, not read-only preparation.
- Record commissioning vs continuous authority, integration terms, and cumulative resource bounds in [AUTHORIZATION.md](../AUTHORIZATION.md). A prompt template does not activate itself.
- Inspect prior runs and pending backend-repair records before applying updated policies; do not invalidate an unfinished run by installing the update.
- Confirm the first-result human checkpoint or its explicit preauthorization. Prepare dependencies and a safe baseline; do not implement the product directly.
