# Repository instructions

## 1. Determine your execution mode first

**Delegated CWI mode:** If your task identifies you as the Codex Workflow Controller's Designer, Architect, Writer, or Reviewer, or supplies its authoritative frozen role context, you are already inside `coding_pipeline`.

- Follow the controller's role policy, permissions, frozen request, and response schema.
- Do not invoke `coding_pipeline`, start another controller, create your own worktree, commit, stage intentionally, merge, change refs, or edit controller state.
- Work only in the assigned run worktree. Do not access the original checkout to implement changes.
- Only the delegated Writer implements prescribed product changes. This is precisely how the requirement to use the coding pipeline is satisfied.
- The nested `coding_pipeline/` checkout is normally absent from the private worktree; do not recreate it.
- Do not claim a final pipeline verdict, merge, or completed development phase in documentation before those events exist. Use `implementation submitted; controller acceptance pending` when appropriate.
- Repository conventions below apply only within your role permissions. They cannot override the controller.

**Top-level coordinator mode:** Otherwise, you coordinate development from the original repository checkout.

- Read `STATUS.md`, `ROADMAP.md`, `BACKLOG.md`, `DEVELOPMENT.md`, the active phase/request, and relevant decisions. Inspect actual Git and pipeline state before trusting a stored checkpoint.
- At initial setup, read the entire `project_description.md` and reconcile `development/REQUIREMENTS.md`. On later sessions, read the relevant original sections, preserving their context and constraints.
- Use `coding_pipeline/bin/agentic-flow` for every product implementation or repair: code, tests, executable utilities, dependency/build configuration, runtime model prompts, and behavior-changing configuration.
- You may directly maintain administrative Markdown plans, requests, status summaries, decisions, and handoffs. You may execute documented setup, inspection, validation, and authorized Git integration commands. This exception does not authorize embedding an implementation in Markdown and executing it to bypass CWI.
- Do not use your own subagents, skills, or another coding mechanism to bypass the selected implementation backend. Planning and read-only analysis are allowed.
- If CWI is blocked, diagnose it and record the blocker. Do not silently implement the feature yourself or disable its safety checks.

## 2. Scope and source of truth

`project_description.md` defines the product. This development workflow controls how it is built. A bounded, committed change request defines one CWI run. Record a substantive conflict or proposed requirement change; do not silently alter the product description to match convenient code.

Keep the product tool-agnostic. The repository's coding pipeline is a development tool, not an obligatory component of the scientific runtime.

The phase ordering is a proposed decomposition, not permission to omit requirements absent from a phase summary. Complete the exact specification crosswalk in D00.

## 3. One active implementation run

Before starting anything, inspect `STATUS.md`, local live notes, retained run IDs, and CWI `status`/`diagnose` for any unfinished run. Do not start a competing controller or assume a timeout terminated its children.

Before launch, commit the request and administrative checkpoint so the target checkout is clean. During the run, do not edit or commit tracked files in the original checkout. Record transient observations only under the already-excluded `local/` area, outside the controller-owned worktree and logs. Do not alter Git exclusions during a run.

After the run, distinguish final acceptance from incomplete execution. Integrate only the exact accepted commit under the recorded merge authorization. Complete the post-integration documentation checkpoint afterward.

## 4. Files and environments

- Root regular files must be `.md`, except Git's administrative `.git` pointer in linked worktrees.
- Put product source, tests, packaging, dependency manifests, and validation utilities under `implementation/`.
- Keep `coding_pipeline/` untracked and locally excluded; never make it a submodule.
- Do not change or clean `workflow_logs/` or CWI's authoritative account-state directory.
- Do not run broad `git add .`, `git clean -fdx`, destructive resets, or worktree pruning to force progress.
- Use a stable, recorded launch environment. Do not upgrade the controller, Codex executable, or dependencies during an unfinished run.
- Use worktree-relative source imports. Do not accidentally test an editable installation pointing at the original checkout.
- Dependencies and necessary reference material must be prepared before a CWI run. Its agents have no general network/package-installation permission.
- Never commit credentials, raw environment dumps, authentication material, private research data, or unreviewed forensic logs.

## 5. Validation and completion

Use the committed validation contract and frozen check commands. The first implementation run must follow `development/BOOTSTRAP.md`; normal automatic discovery cannot admit this Markdown-only nested layout.

Do not replace checks with `true`, `pass`, a version command, or a silently successful empty suite. An explicit `--check` does not gain CWI's built-in test-count gate; the supplied command must enforce meaningful execution itself.

For an implementation run, completion requires final acceptance evidence, an exact accepted source revision, the relevant requirement/test mapping, integration evidence, updated documentation, and explicit recording of remaining gaps. A successful `status` command proves only that inspection succeeded.

When pausing, record why, the exact evidence/run/commit, unresolved effects, the resume condition, and the single next safe action. Never invent a successful test, commit, merge, or completed phase.

## 6. Session handoff

Before stopping, reconcile what actually happened. Update tracked records only at a safe boundary. If a run remains active or the target must stay unchanged, leave the handoff in `local/` and leave a durable local run ID. The next coordinator must inspect that run before starting another.

The default initial authorization is one bootstrap run, without automatic merge. Further autonomous phases or integration require an explicit recorded operating envelope.

