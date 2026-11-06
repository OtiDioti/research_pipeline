# Current development environment contract

Defines non-secret operating requirements for permitted future CWI work; dated readiness observations belong to their runs and historical records.

## Fixed identities and prerequisites

| Item | Required identity or condition |
| --- | --- |
| Platform/product | Local Linux;Python3.11+;standard-library validation;worktree-relative imports |
| Backend | Separate ignored clone `coding_pipeline/`,clean `bcb7ad24f83ff5193345f3d4fa72122ea53a4e66` |
| Codex | 0.166.0;`/home/francesco/.codex/packages/standalone/releases/0.166.0-x86_64-unknown-linux-musl/bin/codex` |
| Executable SHA-256 | `b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8` |
| Stable map | `local/readiness-2026-10-30/launch-environment.json`;no session-variable additions |
| Validation environment digest | `46f63a419a7b148d3489f4a2dd9109c1c3d3a3f334364123e7a858ddee6ace09` |
| Process descriptors | Explicit soft RLIMIT_NOFILE 4096 within existing hard limit |
| Models/flags | [MODEL_POLICY](MODEL_POLICY.md);eight role-specific flags in [RUNBOOK](RUNBOOK.md) |
| Bounds | 2700 seconds per role/check;repairs 2/review, 6/run;latest requests use 1 milestone;grant allows at most 3 later milestones |
| Full checks | `python3 -B implementation/scripts/validate.py`;`git diff --check LITERAL_COMMITTED_LAUNCH_BASE HEAD --`;no `--merge` |

## Stable non-secret map

Use the exact recorded values for a permitted launch; do not change an unfinished run’s environment.

| Name | Value |
| --- | --- |
| HOME | `/home/francesco` |
| CODEX_HOME | `/home/francesco/.codex` |
| PATH | `/home/francesco/miniconda3/pkgs/git-2.40.1-pl5340h9abc3c3_4/bin:/home/francesco/miniconda3/bin:/home/francesco/.local/bin:/usr/bin:/bin` |
| GIT_EXEC_PATH | `/home/francesco/miniconda3/pkgs/git-2.40.1-pl5340h9abc3c3_4/libexec/git-core` |
| GIT_TEMPLATE_DIR | `/home/francesco/miniconda3/pkgs/git-2.40.1-pl5340h9abc3c3_4/share/git-core/templates` |
| LANG / LC_ALL | `C.UTF-8` / `C.UTF-8` |
| TERM | `dumb` |
| PYTHONDONTWRITEBYTECODE | `1` |
| GIT_AUTHOR_NAME / GIT_COMMITTER_NAME | `Codex Development Coordinator` / `Codex Development Coordinator` |
| GIT_AUTHOR_EMAIL / GIT_COMMITTER_EMAIL | `codex@localhost` / `codex@localhost` |

## Access and evidence

Fresh parser,authentication,approved-model/effort and actual-host ownership checks are prerequisites for a permitted new run;prior success is not a future access guarantee. Existing ChatGPT development allowance only;follow [AUTHORIZATION](AUTHORIZATION.md) and actual OS/provider permissions.

Default sandbox `/proc` cannot establish host ownership. Preserve the exact environment,executable,backend and frozen settings of unfinished runs. Historical schema1 inspection uses `local/backend-repairs/CP-002/bin/agentic-flow`;do not migrate or automatically resume old state.

Latest final/required target evidence belongs to [run9bae8bd6](runs/9bae8bd6-2d0d-4cc7-ab70-9ec7b652d998.md). Terminal CWI may clear transient validation/diff pointers:resolve immutable evidence through receipts. Native `status` is JSON;`diagnose` is text;successful dispositions may include `subtest_success`. Effective server-model/quota attestation is unavailable.

## Historical observations

Exact previous launch maps,readiness checks,platform observations,failures and limitations remain in [environment history](history/development-ENVIRONMENT.md),[verbatim original](history/originals/2026-11-06/development/ENVIRONMENT.md.txt) and owning runs. New readiness observations belong with the corresponding attempt/run;change this contract only when requirements change.
