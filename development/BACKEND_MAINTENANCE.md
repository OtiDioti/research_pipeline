# Necessary coding_pipeline repairs

## 1. Narrow exception, not a second implementation route

The human explicitly permits the **top-level development coordinator** to edit the separately cloned `coding_pipeline/` source when an observed defect prevents correct operation. This avoids requiring a broken implementation backend to repair itself.

The exception covers a focused backend fix, its regression tests, and necessary backend documentation. It does not authorize direct research-product implementation, opportunistic refactoring, replacing the backend, changing product requirements, altering the frozen request, weakening acceptance, or adding unrelated capabilities. Delegated CWI roles never receive this exception and must not repair the controller from a product run.

Do not preemptively modify the backend because it might fail. Preserve an actual observed failure and establish its cause first. An intended rejection of broken product code, denied permission, unavailable model, or exhausted quota is not automatically a backend defect.

## 2. Classify before changing anything

| Observation | First route |
| --- | --- |
| Product test/criterion failure | CWI's existing repair cycle, or a subsequent bounded product request |
| Authentication, incompatible CLI, missing dependency | Environment diagnosis; prepare changes only at a safe boundary |
| Rate limit / unavailable requested model | Respect limit / resolve model selection; no substitute or retry storm |
| Interrupted or uncertain process/effect | Read-only status/diagnose/reconstruct, ownership checks, preserve evidence |
| Reproducible controller defect | Isolated backend maintenance below |
| Acceptance, security, quarantine, state-format or migration issue | Treat as high risk; preserve invariants and require explicit intervention when safe recovery cannot be demonstrated |

## 3. Preserve identities and establish quiescence

Record the failure command, exit/result, traceback/log reference, source request, target base/branch, run UUID if any, backend commit, Codex identity, and non-secret environment. Keep raw private artifacts local.

Before any source change, check for all affected controllers/role/validation processes using this backend checkout, including other target repositories. A terminated outer shell does not establish quiescence. Do not change the source of a running controller or its children. Use only supported interruption/termination procedures within authority, then inspect their actual outcome. Unknown ownership or uncertain effects require a hold, not a forced repair.

Preserve the exact original backend revision and any pre-existing local changes. Do not overwrite someone else's dirty work or use destructive reset/cleanup. Snapshot relevant retained state without modifying the original. A copy is for inspection/tests, not an authority to replay its operations against the original repository.

## 4. Diagnose and implement in isolation

Once live owners are resolved, create a separate maintenance branch/worktree of the **backend repository**, for example under ignored `local/backend-repairs/CP-001/`. The parent research repository remains unchanged while any old run is still bound to it.

Use the backend's tests and disposable target repositories to reproduce the issue. Add a focused failing regression test when practical, confirm the failure has the intended cause, make the smallest correction, then show the regression and relevant surrounding tests pass. Record any test that could not run and why. Do not fake a green suite by deleting assertions, swallowing errors, skipping relevant cases, altering receipts, or turning failed checks into success.

Use at most two unsuccessful repair candidates for the same diagnosed issue under the default grant. A new filename, run ID, or cosmetic patch does not reset that count. Stop for a design decision if fixing the issue requires broad architectural changes or assurance that the coordinator cannot establish.

An isolated backend checkout is for maintenance tests. It is not the supported direct-child product launcher. Do not start a product run from it against the original target as a shortcut.

## 5. Review, publish locally, and log every attempt

Review the complete backend diff against the diagnosed cause, including tests and changed failure behavior. For acceptance/security/recovery changes, explicitly test that prohibited actions still fail; a successful happy path alone is insufficient. Review limitations must be stated; do not claim independent review when the same coordinator performed it.

Commit an adopted fix in the backend repository's maintenance branch, keeping its upstream base and exact new commit. Do not push upstream, upgrade the whole repository, or change global Codex settings without authorization. Adopt the tested commit into the supported `coding_pipeline/` checkout only when that is safe for all affected runs, and record the new environment identity before a new product run.

The root audit is [coding_pipeline_changes.md](../coding_pipeline_changes.md). Create it if absent, and log **every attempted change**, including reverted or rejected changes, not merely successful patches. While the target is live or still base-bound, write the complete entry and diff reference under `local/backend-maintenance/` immediately. Transfer the record into the tracked root audit at the first safe checkpoint. Do not commit the audit mid-run just to satisfy the logging rule.

Each entry includes incident ID, timestamps, reason/evidence, relevant run IDs, upstream/base/backend revisions, changed paths, exact patch or durable diff reference and digest, regression before/after, wider tests and skips, whether adopted/reverted, recovery disposition, limitations, and next action. Use [the change template](templates/BACKEND_CHANGE.md).

The nested repository is ignored by the parent. A parent Markdown log containing only a commit hash is not enough to preserve a patch if that clone is lost. Retain a reviewable sanitized patch or protected Git bundle/backup. A non-secret patch may be committed under `development/backend_patches/` after review; otherwise record its protected backup identity. Never publish credentials, raw private prompts, or authentication data. The root itself still contains only Markdown files and directories.

## 6. Resume versus a new run

**Default: never silently resume an existing run under changed backend code.** CWI pins the Codex executable and inputs, but that does not prove every Python controller file is frozen. Operator discipline must preserve the backend identity too.

After a repair, choose one documented route:

- Restore/use the exact original compatible backend and environment to resume only if diagnosis permits and the original issue does not prevent safe continuation.
- Preserve the old run; establish its safe, documented disposition; adopt the tested backend revision; then start a new bounded run with a fresh ID. Reconcile retained accepted/provisional source explicitly. Do not silently cherry-pick unaccepted work, call it accepted, or reset the original target.
- If safe recovery genuinely requires a patched-controller migration of retained state, stop for explicit human authorization and a tested, backed-up recovery plan. Permission to fix source is not permission to rewrite historical evidence.

Do not invent `abort`, `abandon`, `repair-state`, or `merge RUN_ID` commands. The reviewed CLI exposes no such general commands. Follow its actual diagnosis; if no supported safe way to release or salvage the run exists, preserve it and report that precise blocker. Never delete a lease/quarantine marker merely to start again.

If the defect could have invalidated an earlier acceptance decision, mark affected evidence suspect and require reassessment; do not retroactively change old receipts or assume a newly passing backend test validates prior product output.

## 7. Return to normal development

Recheck the fixed backend's compatibility, direct-child layout, clean committed revision, model/effort propagation, relevant tests, and any affected recovery invariants. Reconcile the parent checkpoint and audit at a safe boundary. Then return to the continuous-development loop within the existing grant. The exception ends when the diagnosed backend problem is addressed; product changes still go through CWI.
