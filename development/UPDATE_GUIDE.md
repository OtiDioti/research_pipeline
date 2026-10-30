# Applying the continuous-development update

**Prepared:** 2026-10-30. This update changes development instructions and record formats. It contains no product implementation, backend source patch, installed supervisor, or replacement for `project_description.md`.

## 1. Choose the appropriate package

The **upgrade package** separates `replacement_files/` (policy-document candidates) from `merge_only/` (records that may already contain progress or local decisions). Its manifest identifies the files and their original/new digests. Review it outside the target repository first; do not extract the whole upgrade package into the project root.

The **complete v2 starter kit** contains the full resulting documentation tree. Use that only for a genuinely unstarted repository or as a comparison reference. Its fresh-project STATUS, BACKLOG, ENVIRONMENT, grants, and phase files are not observations of your current checkout.

Even replacement policy files may contain local customization. Compare before applying; preserve compatible additions and surface real policy conflicts. Never overwrite `project_description.md`.

## 2. Establish a safe update boundary

Inspect actual Git, local handoff/attempts, and retained CWI status before writing to the target. If a run is live or an accepted result is still bound to its original base, leave these new files outside the repository. Finish authorized exact integration under the old grant or follow the actual recovery/hold procedure first. Applying a documentation update can change HEAD and invalidate an otherwise legitimate pending integration.

If an unfinished run uses a different frozen model, do not change its model/effort, controller, or runtime to match these new instructions. Record its disposition explicitly. If required maintenance is the only route out of a genuine defect, the user's maintenance permission still applies, but parent files remain unchanged until safe and historical evidence must remain intact.

Do not use a hard reset, stash of unknown user work, broad clean, destructive worktree removal, or forced merge to make the update convenient. Preserve user edits and determine their ownership.

## 3. Integrate the policy changes

At a safe boundary, review and merge the updated root `AGENTS.md` and `DEVELOPMENT.md`, coordinator prompts, runbook, autonomy policy, model policy, and backend-maintenance policy. They form one coordinated update; changing only the prompt can leave contradictory repository instructions.

Add missing policy/navigation/template files. Add `coding_pipeline_changes.md` only if absent; if it exists, preserve every historical entry and adopt the new audit fields. This file records changes to the ignored nested backend, not research-product changes.

Merge the new authority/mode/model/consumption fields into the actual STATUS. Preserve actual phase, request, run, commits, blockers, and next action. Merge backlog, decisions, environment, requirements, phase plans, and the first request without erasing their histories. A request already frozen by a run must remain unchanged; use a later revision/new request as appropriate.

The new AUTHORIZATION file is a form, not an active grant. Migrate any existing genuine grant accurately; do not replace it with NOT_RECORDED or infer broader authority. Mark pending activation when no such grant exists. Preserve actual grants' dates, scope, source, budgets, and consumption.

## 4. Resolve the requested model before calling it

The user requested Astra 6.1. This update retains that requirement but does not invent a supported identifier. The official catalog inspected listed GPT-6 Astra and GPT-6.1 Sol, not a verified Astra 6.1 identifier. Confirm local model/account evidence or obtain an explicit correction before model-dependent execution. No silent fallback is permitted.

Record the resolved model/provider and effort policy in ENVIRONMENT. Select a supported effort per CWI run, at most `xhigh`; use explicit `--model` and `--reasoning` flags. Do not assume setting the outer Codex session's model configures its child processes.

## 5. Commit and enter the appropriate workflow

Inspect the complete diff, check links and root layout, and commit explicit paths at a safe boundary. Do not stage the nested clone, logs, secrets, or private local data. If bootstrap has not started, capture its exact baseline only **after** this final prelaunch commit. The bootstrap program is unchanged by this update; do not introduce a broad missing-tests exemption.

Select the prompt by actual state:

| Actual state | Action |
| --- | --- |
| No implementation yet, no unfinished run | First session: commission D00 and REQ-D01-001 |
| First result accepted-unmerged, not yet approved | Review it, then issue the one-time activation/integration prompt |
| Already integrated work and genuine continuous authority | Continuation prompt; reconcile records and continue |
| Already integrated work but only supervised authority | Issue an actual continuous grant for the remaining scope; do not rerun bootstrap |
| Run active, ownership uncertain, or recovery blocked | Inspect/recover/hold under its existing evidence; no competing start |

The activation prompt's first paragraph assumes the first result is waiting for integration. For an already-integrated project, replace that paragraph with an accurate reference to the inspected integrated checkpoint; the rest can authorize the remaining phase range. Record that actual grant before the next new run.

By default there is one human first-result review, then no routine prompt per request or phase. The optional ready-to-paste CODEX_START_AUTONOMOUS prompt can replace that review for a single initial instruction. Do not select it silently. Session limits, permissions, model availability, budgets, or scientific review can still require human action. No unattended supervisor is installed.

## 6. Verify the adoption

- The original product description and existing progress/evidence are intact.
- Coordinator and delegated-role permissions agree: product implementation through CWI; focused direct backend repairs only by the coordinator under the maintenance procedure.
- Continuous scope and integration authority trace to a real human grant; templates have not activated themselves.
- Every new start passes a verified model identifier and explicit supported effort at or below xhigh.
- Every live/base-bound run retains the original source/environment/runtime identity; no policy update rewrote its evidence.
- The next safe action is unambiguous and correctly distinguishes a new request, a resume, an integration, or a human decision.

Verification performed when preparing this update is recorded in [WORKFLOW_UPDATE_CHECKS.md](review/WORKFLOW_UPDATE_CHECKS.md). It does not certify your local installation or the finished scientific product.
