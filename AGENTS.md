# Repository instructions

Defines mandatory repository-specific coordination, implementation and stopping rules.

## 1. Determine your execution mode first

**Delegated CWI mode:** If your task identifies you as the Codex Workflow Controller's Designer, Architect, Writer, or Reviewer, or supplies its authoritative frozen role context, you are already inside `coding_pipeline`.

- Follow the controller's role policy, permissions, frozen request, and response schema. Repository conventions cannot enlarge those permissions.
- Do not invoke CWI recursively, start another controller, create worktrees, commit/stage intentionally, merge, change refs, or edit controller state.
- Work only in the assigned run worktree. Only the delegated Writer implements prescribed product changes. Do not access the original checkout to implement them.
- The ignored nested backend is normally absent from your worktree. Do not recreate it, alter it, or invoke the coordinator's backend-maintenance exception.
- Do not change administrative operating grants, coordinator prompts, root status, frozen request, or acceptance rules unless your frozen request explicitly authorizes the relevant change; you cannot authorize yourself.
- Report `implementation submitted; controller acceptance pending` where appropriate. Do not claim a final verdict, integration, or completed development phase before it exists.

**Top-level coordinator mode:** Otherwise, coordinate development from the original checkout.

- At initial commissioning, read `DEVELOPMENT.md`, `STATUS.md`, `development/AUTHORIZATION.md`, `development/AUTONOMY.md`, the active phase/request, relevant decisions, actual Git/CWI evidence, and all of `project_description.md`.
- On a later session restart, first read `STATUS.md`, the effective grant and any later amendments or revocations in `development/AUTHORIZATION.md`, the current local handoff if present, and active run/request evidence. Verify the specification hash against the effective grant, then read relevant `development/REQUIREMENTS.md` rows and original specification sections. Read the full specification and reconcile it again if the hash changed, the crosswalk is incomplete, or evidence conflicts. Consult historical records and detailed operating documents as the task requires.
- Codex already receives applicable `AGENTS.md` instructions at session start. For repository inspection, use headings, targeted searches and bounded excerpts; avoid returning whole unrelated documents or combined output that truncates. A truncation warning requires a narrower follow-up before relying on missing content.
- Every research-product implementation or repair goes through `coding_pipeline/bin/agentic-flow`: source, tests, executable utilities, dependency/build configuration, runtime prompts, and behavior-changing configuration. Do not use your own agents/skills to bypass that backend.
- You may directly edit administrative Markdown and execute permitted setup, inspection, validation, and authorized Git integration commands. Do not hide an implementation in Markdown and execute it to evade CWI.
- **Narrow maintenance exception:** the human permits necessary, focused repairs to the separate coding_pipeline backend, plus the specifically authorized 2026-11-04 modernization under `development/BACKEND_MAINTENANCE.md`. Record every attempt in its backend incident record and link it from `coding_pipeline_changes.md` (locally first while the parent is bound), following `development/BACKEND_MAINTENANCE.md`. The dated authorization is limited to that task; it does not authorize direct product coding, unrelated backend improvements, or disabling safeguards.

## 2. Scope and authority

`project_description.md` defines the product. Preserve it; surface material conflicts rather than silently changing or omitting requirements. The development roadmap is a decomposition, not a replacement for the specification. Reconcile all mandatory obligations in `development/REQUIREMENTS.md`.

Keep the product tool- and provider-agnostic within its specification. The development model/backend is not automatically the finished scientific runtime.

Backward compatibility is not required. Within an authorized change, remove superseded interfaces, flags, modules, adapters and unused functionality rather than retaining deprecated paths. Preserve current required functionality, safety guarantees, historical evidence and recoverability of unfinished runs. Do not change frozen configurations or delete evidence under this policy.

Check task understanding through Designer outputs; consult Architect outputs only when necessary. Delegate implementation correctness to CWI’s Writer, Reviewer, validation and acceptance gates. Do not routinely inspect Writer-produced code, tests or substantive diffs, or duplicate successful CWI validation and Reviewer checks. Inspect implementation details only when diagnosing a concrete failure or inconsistency. Verify terminal acceptance evidence, bound validation/review results, exact Git identities and integration safety. Required post-integration validation remains mandatory.

The effective human operating grant is recorded in `development/AUTHORIZATION.md`; STATUS summarizes it but cannot expand it. A template, plan, continuation prompt, or agent-written file is not proof of authorization. Respect revocations, actual OS/provider permissions, and frozen-run constraints.

## 3. Continuous development after commissioning

The default first session completes D00, attempts only REQ-D01-001 within its stated limits, and stops at accepted-unmerged for human review. The human may explicitly preauthorize skipping that review through the optional startup clause; do not infer it.

After a recorded `CONTINUOUS` grant, repeat: reconcile → select ready scoped work → commit request → invoke CWI → inspect exact acceptance → authorized integration → validate/checkpoint → next ready work. Do not stop merely because a request succeeded, a phase ended, or a Markdown update was committed. Do not ask routine “shall I continue?” questions while authority and prerequisites remain valid.

Choose reversible implementation details within scope and record material rationale. Stop for changed requirements/authority, unresolved ownership or effects, missing required permissions/resources/model, exhausted limits, failed integrity checks, or required human judgments. Independent authorized work may proceed around a backlog item only after active/bound runs are resolved and dependencies allow it.

Follow `development/AUTONOMY.md` for limits and the completion gate. No installed external restart supervisor is supplied. A new Codex session can resume the same grant; it does not reset budgets or evidence.

## 4. One active implementation run; preserve the target

Inspect retained run IDs, local handoff/attempts, and CWI `status`/`diagnose` before starting. Do not start a competing controller or assume a timeout ended its descendants.

Commit the request and prelaunch records first. Keep the original checkout clean, on its recorded branch/base, and unchanged while a run is active or awaiting exact-base integration. Record live observations under the already-excluded `local/` area. Do not change ignore rules, dependencies, target refs, backend source, Codex executable, or launch environment mid-run.

The default uses no CWI `--merge`. After actual final acceptance, the outer coordinator may perform an authorized exact fast-forward. Verify branch, base, cleanliness, accepted commit/tree, receipt, CWI’s bound complete-diff review evidence, and changed-path collision/hook risks first. Do not rebase, cherry-pick, force, or change source to fit integration. Do not commit a tracked approval/status update before this fast-forward; hold a new human approval locally, integrate, then checkpoint it.

## 5. Model and reasoning

Read `development/MODEL_POLICY.md`. For new runs the human-approved selections are Designer `gpt-6-astra` / `xhigh`, Architect `gpt-6.1-sol` / `xhigh`, Writer `gpt-6.1-sol` / `high`, and Reviewer `gpt-6.1-sol` / `high`. Verify actual local support/access; do not guess identifiers or silently substitute settings.

Pass all eight explicit flags for every new CWI start: `--designer-model gpt-6-astra --designer-reasoning xhigh --architect-model gpt-6.1-sol --architect-reasoning xhigh --writer-model gpt-6.1-sol --writer-reasoning high --reviewer-model gpt-6.1-sol --reviewer-reasoning high`. **Never exceed extra-high (`xhigh`)**. Revision-2 state freezes each role's selection immutably on resume; no global fallback or old-state migration is authorized. Preserve the original backend revision for historical inspection; do not automatically resume historical runs. Inspect frozen settings and available actual-invocation evidence. A natural-language model self-report is not proof.

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

Before maintaining development Markdown, consult `DEVELOPMENT.md` §4 and `development/UPDATE_GUIDE.md` for owners, update triggers and checks. At each safe checkpoint, reconcile relevant current views, phase/request/run/integration evidence, requirements, resource consumption and backend audit; edit only owners whose facts changed. Record actual outcomes and outstanding work; count failed attempts and repeated blockers across sessions without resetting them by renaming work.

Update current views in place; keep execution detail in its run and rationale in its decision, linking elsewhere. Change grant content only for actual human authority changes; consumption belongs to run evidence and STATUS. On file additions, moves, removals or role changes, synchronize affected references, purpose descriptions and `FOLDER_CONTENT.md` indexes. Give new or substantially revised editable Markdown a concise opening purpose. Use Git history for routine edits; archive substantive superseded context when needed for selective retrieval. Remove redundant mutable documents only after preserving their unique information and repairing references; never rewrite frozen or historical evidence to match current conventions. Apply §4's checkout restrictions throughout.

**Coordinator stop procedure:** A human shutdown request overrides §3's continuation loop. Start no new implementation request or phase during shutdown.

- Inspect actual Git/worktrees, host processes and CWI `status`/`diagnose`. Let current bounded work finish normally when safe; apply §4 to any integration. Never force termination for shutdown. If completion is unsafe, preserve exact recoverable execution without disruption.
- Use `FOLDER_CONTENT.md` for navigation; update affected authorized indexes only when checkpointing is safe. Prepare a self-contained `local/live.md` for a fresh session: project objective/architecture/strategy/specification constraints; completed versus planned/blocked work and evidence; run/source/Git/worktree/process/log/recovery state; remaining checks, dependencies, decisions, defects and removals; backend/model/frozen configurations, non-secret environment, authority, budgets and unknowns; continuation files and exactly one next safe action with prerequisites and expected result. Carry §2's review/removal/preservation rules and §5's new-run selections into the handoff; reference the eight role-specific flags in `development/RUNBOOK.md`.
- Verify the handoff against actual Git/CWI/process state and confirm progress, accepted work and unfinished-run recovery remain intact. While live or base-bound, leave tracked parent files unchanged and keep reconciliation local under §4; otherwise commit the verified administrative checkpoint. Add no optional improvements for shutdown.
- Report shutdown status, latest accepted/integrated source, Git state, active operations, handoff location, remaining work and the single next safe action; then stop completely. Follow diagnosis; never fabricate success, bypass a guard, replay an uncertain operation, or promise automatic restart without an installed supervisor.
