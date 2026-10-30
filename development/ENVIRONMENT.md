# Development environment contract

Observed 2026-10-30; this is local evidence, not the starter-kit template. Product live/scientific execution remains separately gated. Private raw outputs are under ignored `local/readiness-2026-10-30/`.

| Field | Observation / launch contract |
| --- | --- |
| Platform | Linux x86_64; first verified development target only |
| Python | `/home/francesco/miniconda3/bin/python3`, 3.11.15; backend stdlib runtime; setuptools/wheel/build available |
| Git | System 2.34.1 fails required `worktree list --porcelain -z`; existing Conda Git 2.40.1 passes. Use fixed paths below; no install/update |
| Target | Original checkout `/home/francesco/Desktop/gits/research_pipeline`, local branch `main`; initial source `dce9bedb998c8be4389d42627916911f4c25d336` |
| Specification | v1.3 SHA-256 `13d2ed9198916b7af3a3f9c3522745b0b6882b5492c9e27ccdc0c46114137ab7` |
| Backend | Real untracked direct child `coding_pipeline/`, separate Git clone, no submodule/symlink; clean `main` at `1f68060b5a5a9964c91811a53d3a515e0b01a073` |
| Backend remote | `git@github.com:OtiDioti/coding_pipeline.git` |
| Reviewed base | `122f86588f829387ea460a1e2a997a87ce325c53`; local changes since it are 71 additions/1 deletion in common/designer prompt resources; complete diff inspected |
| Prompt difference | Clarifies active vs final milestone scope, but Designer file also contains Architect-like prescription language. Preserve unmodified; one-milestone request and authoritative role schema still govern; inspect actual Designer result |
| Local exclusions | Git common-dir info/exclude now preserves existing rules and excludes `/coding_pipeline/`, `/workflow_logs/`, `/local/*` except README, and `/.obsidian/`; no root .gitignore |
| Existing run evidence | Account `/home/francesco/.local/state/cwi` absent; no target logs/CWI refs/linked worktrees/local attempt records observed before setup. No UUID available for status/diagnose |
| Selected Codex | CWI discovery selected `/home/francesco/.codex/packages/standalone/releases/0.166.0-x86_64-unknown-linux-musl/bin/codex`, version 0.166.0 |
| Executable SHA-256 | `b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8` |
| Compatibility | Actual CodexCliAdapter.check_compatibility passed ephemeral, persistent-new, resume and login-status parser checks; no model called |
| Authentication/billing | Exact adapter authentication_available true; CLI says Logged in using ChatGPT. Existing allowance authorized. No API key used/copied; no API budget granted; remaining service quota unknown |
| Model | Human corrected Astra 6.1 to `gpt-6-astra`; local account model cache fetched 2026-10-30T07:20:30Z lists it with low/medium/high/xhigh; default config is not used as CWI selection |
| Model evidence limits | Cached account catalog and login status establish advertised availability/login, not a successful new model invocation. Real launch still subject to provider access/quota; record actual frozen argv/evidence |
| Next effort | `medium` for REQ-D01-001: bounded foundation with straightforward CLI/validator contracts; hardest role is test adequacy review. Ceiling xhigh |
| Product dependencies | Foundation Python stdlib runtime and unittest; no editable installation or paid dependency |
| Backend tests | 1,031 run in 545.099s; 1,010 pass, 21 skip, zero failures/errors. 15 opt-in live tests, 6 pytest cases initially unavailable; focused bootstrap module then passed all 21 cases in 23.114s using existing botify312 Python 3.12.13 / pytest 9.0.3, including all 6 initially skipped pytest cases |
| Launch permissions | Local Git exclusion write required and received specific escalation. CWI account-state/Git/child execution needs specific trusted launch approval; not established merely by help/parser checks |
| Backend maintenance | None; see root audit. No backend, Codex installation or authentication changes made |

## Stable non-secret launch map

Use `env -i` with exactly these values from target root for start/resume. Retained local JSON: `local/readiness-2026-10-30/launch-environment.json`. Do not add session variables mid-run.

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

Model and reasoning are explicit argv (`--model gpt-6-astra --reasoning medium`), not new exported variables. No proxy/certificate override has been found necessary by parser/login inspection; authenticated model transport is not yet exercised. Any required launch-environment correction must occur after safely resolving the prior attempt, never silently on resume. The focused pytest test override is test-only and is not part of this launch map.

## Evidence identities

Full backend suite log SHA-256: `8108ffd8b02a062369413436a386516ad00111e8793f76d584b4e94adf17d01e`. Local `codex-compatibility.json` retains selected path/version/digest and probe outcome. Raw auth/config/session files are not copied into the repository.

Official [model catalog](https://developers.openai.com/api/docs/models) was checked on 2026-10-30 and lists GPT-6 Astra as `gpt-6-astra`; the human's explicit correction, rather than similarity of names, authorizes selection. Account cache is supplemental evidence; no effective-model self-report is treated as proof.

Focused bootstrap log SHA-256: `85e3f178b7fb7746fba9ab399a3213dba7d805be98ffa9502a4c9555d7568dd2`. Original review T-01 crash-recovery and T-02 session cases pass in the full local suite; T-03 pytest bootstrap cases pass in the focused follow-up. No failure was waived or backend source changed. Fifteen real-model integration tests remain unrun; REQ-D01-001 will be the bounded commissioning integration, not a claim that those tests passed.

Git author/committer config was absent. The explicit workflow-local agent identity above supplies Git identity without changing global configuration or attributing generated work to the human. Preserve these four variables on resume.

## Commissioning transport evidence and continuation

Run `47d6ef06-c251-4a0d-bb2c-da2059d9360f` completed successfully with the recorded environment/backend, explicit `gpt-6-astra` / `medium`, and selected Codex. Frozen invocation evidence and successful role responses establish actual access for this run; natural-language self-identification is not used. No independent server-side effective-model attestation is claimed beyond retained invocation configuration/telemetry. No API key transport, installation change or backend patch occurred.

Post-integration validator: 19/19 passing, zero skipped, log SHA-256 `ba3c989d077057b92a336e923eab7a41569e18fec105457d9e69388cd208b978`. Next request REQ-D01-002 uses the same launch map and model with medium effort for a bounded deterministic fixture. All future requests use the permanent validator; no bootstrap baseline exception. Quota remains unknown.
