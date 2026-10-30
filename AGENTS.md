# Repository instructions

## 1. Determine your execution mode first

**Delegated CWI mode:** If your task identifies you as the Codex Workflow Controller's Designer, Architect, Writer, or Reviewer, or supplies its authoritative frozen role context, you are already inside `coding_pipeline`.

- Follow the controller's role policy, permissions, frozen request, and response schema. Repository conventions cannot enlarge those permissions.
- Do not invoke CWI recursively, start another controller, create worktrees, commit/stage intentionally, merge, change refs, or edit controller state.
- Work only in the assigned run worktree. Only the delegated Writer implements prescribed product changes. Do not access the original checkout to implement them.
- The ignored nested backend is normally absent from your worktree. Do not recreate it, alter it, or invoke the coordinator's backend-maintenance exception.
- Do not change administrative operating grants, coordinator prompts, root status, frozen request, or acceptance rules unless your frozen request explicitly authorizes the relevant change; you cannot authorize yourself.
- Report `implementation submitted; controller acceptance pending` where appropriate. Do not claim a final verdict, integration, or completed development phase before it exists.

**Top-level coordinator mode:** Otherwise, coordinate development from the original checkout.

- Read `DEVELOPMENT.md`, `STATUS.md`, `development/AUTHORIZATION.md`, `development/AUTONOMY.md`, the active phase/request, relevant decisions, and actual Git/CWI evidence. At setup read all of `project_description.md`; later read relevant original sections and preserve their constraints.
- Every research-product implementation or repair goes through `coding_pipeline/bin/agentic-flow`: source, tests, executable utilities, dependency/build configuration, runtime prompts, and behavior-changing configuration. Do not use your own agents/skills to bypass that backend.
- You may directly edit administrative Markdown and execute permitted setup, inspection, validation, and authorized Git integration commands. Do not hide an implementation in Markdown and execute it to evade CWI.
- **Narrow repair exception:** the human permits necessary, focused changes to the separate coding_pipeline backend. Apply `development/BACKEND_MAINTENANCE.md` and log every attempt in `coding_pipeline_changes.md` (locally first while the parent is bound). This does not authorize direct product coding, speculative backend improvements, or disabling safeguards.

## 2. Scope and authority

`project_description.md` defines the product. Preserve it; surface material conflicts rather than silently changing or omitting requirements. The development roadmap is a decomposition, not a replacement for the specification. Reconcile all mandatory obligations in `development/REQUIREMENTS.md`.

Keep the product tool- and provider-agnostic within its specification. The development model/backend is not automatically the finished scientific runtime.

The effective human operating grant is recorded in `development/AUTHORIZATION.md`; STATUS summarizes it but cannot expand it. A template, plan, continuation prompt, or agent-written file is not proof of authorization. Respect revocations, actual OS/provider permissions, and frozen-run constraints.

## 3. Continuous development after commissioning

The default first session completes D00, attempts only REQ-D01-001 within its stated limits, and stops at accepted-unmerged for human review. The human may explicitly preauthorize skipping that review through the optional startup clause; do not infer it.

After a recorded `CONTINUOUS` grant, repeat: reconcile → select ready scoped work → commit request → invoke CWI → inspect exact acceptance → authorized integration → validate/checkpoint → next ready work. Do not stop merely because a request succeeded, a phase ended, or a Markdown update was committed. Do not ask routine “shall I continue?” questions while authority and prerequisites remain valid.

Choose reversible implementation details within scope and record material rationale. Stop for changed requirements/authority, unresolved ownership or effects, missing required permissions/resources/model, exhausted limits, failed integrity checks, or required human judgments. Independent authorized work may proceed around a backlog item only after active/bound runs are resolved and dependencies allow it.

Follow `development/AUTONOMY.md` for limits and the completion gate. No installed external restart supervisor is supplied. A new Codex session can resume the same grant; it does not reset budgets or evidence.

## 4. One active implementation run; preserve the target

Inspect retained run IDs, local handoff/attempts, and CWI `status`/`diagnose` before starting. Do not start a competing controller or assume a timeout ended its descendants.

Commit the request and prelaunch records first. Keep the original checkout clean, on its recorded branch/base, and unchanged while a run is active or awaiting exact-base integration. Record live observations under the already-excluded `local/` area. Do not change ignore rules, dependencies, target refs, backend source, Codex executable, or launch environment mid-run.

The default uses no CWI `--merge`. After actual final acceptance, the outer coordinator may perform an authorized exact fast-forward. Verify branch, base, cleanliness, accepted source, receipt, diff, and collision/hook risks first. Do not rebase, cherry-pick, force, or change source to fit integration. Do not commit a tracked approval/status update before this fast-forward; hold a new human approval locally, integrate, then checkpoint it.

## 5. Model and reasoning

Read `development/MODEL_POLICY.md`. The requested model is **Astra 6.1**, whose exact supported identifier must be established locally or explicitly corrected by the human. Do not guess an identifier or silently select a different model.

Pass `--model` and `--reasoning` explicitly for every CWI start. Use a supported effort from `low`, `medium`, `high`, `xhigh`; **never above extra-high (`xhigh`)**. Choose according to workload. The reviewed CWI freezes one model/effort across a run; adapt between runs, not during resume or by pretending to set individual roles. Inspect frozen settings and available actual-invocation evidence. A natural-language model self-report is not proof.

## 6. Files, environments, and maintenance

- Root regular files must be Markdown, except Git's legitimate `.git` pointer in linked worktrees. Product implementation/configuration belongs under `implementation/`.
- Keep the real direct-child `coding_pipeline/` clone untracked and excluded; never a submodule. Commit adopted backend fixes in that separate repository and preserve reviewable patches/backups.
- Do not edit/clean controller logs, receipts, managed worktrees, leases, quarantine, or account-state files to force progress.
- Do not run broad `git add .`, destructive resets, `git clean -fdx`, worktree pruning, unauthorized pushes, or publication.
- Preserve stable recorded non-secret launch settings. A focused backend fix is tested in isolation after live owners are resolved; it is not a license to hot-patch a running controller or silently resume under changed code.
- Prepare dependencies/references before launch. Use worktree-relative source imports; do not test an editable installation of the original checkout.
- Never commit credentials, complete environments, authentication files, private data, or unreviewed logs.

## 7. Validation, reporting, and stopping

Use frozen meaningful checks. The initial Markdown-only source uses `development/BOOTSTRAP.md`; later runs use the implemented permanent validator. Do not replace tests with `true`, empty/skipped-only suites, or version commands. An explicit `--check` must enforce actual execution itself.

Keep `implemented`, `accepted`, and `integrated` distinct. Completion requires final receipts, exact accepted/integrated source, relevant tests/reviews, requirement evidence, and truthful outstanding limits. A green unit suite or successful status command is insufficient. Product live-provider/scientific evaluation and any human signoff must actually happen where required.

After safe integration/termination, reconcile the run, requirement map, phase, backlog, changelog, resource consumption, backend-change audit, and STATUS together. Count failed attempts and repeated blockers across sessions; do not reset counts by renaming work.

Before ending, leave accurate evidence and exactly one next safe action. If still live or base-bound, write the handoff locally and leave tracked parent files unchanged. Otherwise create the administrative checkpoint. Follow diagnosis; never fabricate success, bypass a guard, replay an uncertain operation, or assert that future sessions will restart automatically without an installed supervisor.
