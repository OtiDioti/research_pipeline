# Development environment contract

Historical commissioning observations from 2026-10-30 appear in the first table; later dated evidence supersedes its initial specification/run/effort observations. The stable launch map remains operative and unchanged. This is local evidence, not the starter-kit template. Product live/scientific execution remains separately gated. Private commissioning outputs are under ignored `local/readiness-2026-10-30/`.

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

REQ-D01-002 repeated the same executable/catalog/ChatGPT login checks before launch and used the unchanged fixed map/backend with explicit gpt-6-astra/medium. Actual run 34bcb77d finally accepted and integrated 79a84d2. Post-integration 28/28 tests, zero skipped/failures, log SHA-256 `abc88b153b57fa0bb2ef931ff73f67774ed283ca4b2bc93c7fc668a71d380868`. No installation, environment or backend modification occurred. Both actual run records retain usage and source/receipt evidence; no product live-provider validation occurred.

## Dependency-amendment readiness — 2026-10-30

Before REQ-D02-001, both old runs were reconciled via status/diagnose and receipt/source-digest checks; accepted commits are integrated and no owner/effect remains unresolved. Backend and Codex executable hashes/dirty state remain unchanged. Exact selected CLI reports ChatGPT login; account catalog advertises gpt-6-astra/high. Python 3.11.15 provides SQLite 3.53.2; stdlib-only storage needs no installation. Use the same launch map, explicit gpt-6-astra/high for the new transaction/authority work; old runs retain medium. Prior runtime/artifact identities are preserved. No backend maintenance or new service/data/billing authority is involved.

## Post-storage and next backup readiness — 2026-10-30

REQ-D02-001 finally accepted/integrated b51e421 with the same backend/environment and explicit gpt-6-astra/high. Final/target validation passed 72/72; target log SHA-256 67d0185b7c54109a6423d6cda7ea4c798b776217cb4bd543df93bcf066e2e37e. Before REQ-D02-002, selected executable digest and clean backend identity were rechecked unchanged; account catalog advertises high and selected CLI reports ChatGPT login. Login inspection emitted a sandbox read-only PATH-alias warning but succeeded; no installation/environment change or required dependency was introduced. Actual prior high-effort invocation evidence is retained; no server-side model attestation beyond recorded invocation configuration/telemetry is asserted. Same stdlib SQLite environment, no new service or API authority.

REQ-D02-002 used the same frozen gpt-6-astra/high, Codex digest, clean backend and launch map. Final/target validation passed 88/88; target log SHA-256 6b97d1d4cb1dd49a384c0d9e15ab1da369ffb5fe67b452ab8aaae2109431433e. The coordinator executed the exact accepted docs/backups.md example with literal /tmp before integration (exit 0, source unchanged), resolving the delegated sandbox limitation without changing its environment. No dependencies, installation, provider or permissions were changed.

Before REQ-D02-003, selected Codex 0.166.0 executable digest and backend clean 1f68060 identity are unchanged; local catalog advertises gpt-6-astra/high and CLI login status succeeds using ChatGPT (same harmless read-only alias warning). No install or environment mutation occurred. Explicit high is chosen for typed reference/admission/idempotency review. Same no-API-cap and unmeasured quota/liability limits apply.

REQ-D02-003 used unchanged backend/environment and frozen gpt-6-astra/high. Final/target validation passed 116/116; target log SHA-256 be212248f17fadfc550c154eedd819b6ebd577de193d2dee983a3e23aeb88a26. The actual documented persistence example executed in the suite using a fresh process and explicit /tmp runtime. No installation/dependency/provider changes.

Before REQ-D02-004: same Codex executable digest, clean backend identity and stable launch map rechecked; selected CLI reports ChatGPT login and account catalog advertises gpt-6-astra/high. No installation, dependencies or launch-setting changes. Explicit high is selected for strict dual-version compatibility and migration publication.

Observed in 9af6f133: controller baseline passed 116/116, but Writer sandbox denied literal /tmp in 12 existing typed tests. codex_cli deliberately excludes /tmp/TMPDIR grants. Do not change these frozen/security settings or confuse advisory Writer execution with controller validation. R1 retains the same environment/backend and meaningful frozen check; no permission expansion.

REQ-D02-004-R1 completed with unchanged clean backend, Codex digest and stable launch map; frozen gpt-6-astra/high. Final/target 169/169, target log SHA-256 26ff8c15c955c81b25874b809d0fd8db814cb67034c521fdb4e29fad67f6e5ed. Exact documented migration example ran under controller validation. No environment/security/dependency/backend change; the request ownership clarification resolved the prior mismatch.

Before REQ-D02-005, all seven retained runs were reconciled (six integrated, one preserved terminal no-effects failure). Selected Codex digest and backend unchanged; catalog advertises gpt-6-astra/high and CLI reports ChatGPT login. Higher catalog efforts do not change the project xhigh ceiling; next run explicitly uses high. No provider/environment installation or authority change.

REQ-D02-005 run 46114120 stopped at its frozen 900-second Writer deadline, with no backend/environment change. Original source effects preserved; host advisory 184/184 verifies the draft without acceptance. Human explicitly authorizes 2700-second agent/validation deadlines for new runs (AUTH revision 5). Supported --context can freeze the existing CWI-authored draft as reference input; it changes neither model provider nor installed backend/environment. Timed-out Writer token usage is unknown.

REQ-D02-005-R1 / 8dc45005-5187-4be0-a009-dece7c493f2b froze explicit gpt-6-astra/high and 2700-second agent/validation deadlines, supported preserved-draft context, and unchanged backend/Codex/environment. Finally accepted/integrated a5bba690a6c7e7113a92f34cc99efffc7a8c5656; 204/204 target tests, log SHA-256 61ecb89ba3e08779a3476c9328d1beddf674cbce629f6347233bff860e07e7cc. One fixture identity repair was product-test work, not a backend/environment change. All nine relevant runs reconciled; seven integrated and two terminal preserved failures. REQ-D02-006 will recheck catalog/login/backend and exact baseline before its new start; no installation or provider change is planned.

REQ-D02-006 / 2b6ed304-5044-45b5-adcd-a8be9c3e314d used unchanged clean backend 1f68060, Codex 0.166.0 hash and stable launch map, explicit gpt-6-astra/high and2700-second agent/validation deadlines. Accepted/exact-integrated a56111f3; target 291/291,138.378 seconds, clean source, log 78be60616be9511fc53a949fc1add3a76a7e771cc31b7fa16e3051f36300640c. Writer-local /tmp and AF_UNIX bind restrictions were reported without changing checks; host controller and target passed all cases. Ten relevant runs reconciled: eight integrated, two terminal preserved; no owner/effect remains. No environment/install/backend change. Recheck exact catalog/login/backend/baseline before REQ-D03-001; no provider substitution or new service permission.

## Source integration and explicit process limits — 2026-10-31

REQ-D03-001 exact-integrated d8dffdd on main through approved guarded Git execution. Backend 1f68060 and Codex 0.166.0 SHA b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8 remain unchanged. Current catalog fetched 2026-10-31 advertises gpt-6-astra/high; configured extra levels do not alter project ceiling xhigh. Login inspection reports ChatGPT (sandbox PATH-alias creation warning did not prevent inspection); no authentication/configuration file was copied or changed. Stable launch-environment JSON remains byte-for-byte unchanged.

New process resource prerequisite: **RLIMIT_NOFILE soft 4096, existing hard 1048576** for target validation and future CWI launch/resume contexts. The 1024-file capture boundary holds every selected leaf and directory handle through its final integrity check. Inherited soft=1024 caused a genuine target EMFILE failure (342/343); exact test failed at 1024 and passed at 4096, then the unchanged full suite passed 343/343, 242.885 seconds, clean source. Set only the launching process's soft limit within the existing hard limit before starting; verify it is inherited. Do not alter host-wide limits or mutate a running/frozen controller. Prior controller resource limits were not recorded, so no historical value is asserted. This resource prerequisite is separate from the stable environment-variable digest.

Local evidence: local/attempts/D03-001-attempt-001/integration-recheck-20261031T115054Z, including original failing validation, nofile-diagnosis, passing target-validation-4096 and next-launch-readiness. One environment recovery consumed, backend candidates remain zero. Next request uses explicit gpt-6-astra/high, one milestone, repairs 2/6 and 2700-second agent/validation deadlines; no --merge.

## Corpus checkpoint

REQ-D03-002 retained the same backend/executable/model/high-effort/environment and inherited soft descriptor limit 4096; both controller validations and target 369/369 passed. The initial candidate's new capture directories used default mkdir modes and failed the existing safety guard under inherited umask. CWI fixed only its synthetic fixture/example directories to0o700; no launch or host setting changed. Continue explicit private input-directory modes in fixtures, stable environment and 2700-second new-run bounds.

## Project-intake execution checkpoint — 2026-10-31

Rundb2829bc-fca9-48d7-b2c1-b9e99348c197 used the unchanged non-secret environment, backend/Codex executable, gpt-6-astra/high and2700-second agent/validation deadlines, inheriting soft RLIMIT_NOFILE4096. Milestone/final/target396/396 passed. Target: 396/396, zero skips/failures/errors, 307.310 test seconds; clean unchanged accepted source; completed 2026-10-31T14:18:19.406823+00:00, stdout SHA-256 21c4d84ae8fe38d38050697a52bbcd88c1fc977900ea40982b633a56065348d4

New synthetic capture fixtures/example must explicitly declare available supplied_local provenance with exact file locators and create directories0700/files0600. Default file creation can inherit shared-write bits; never weaken capture guards or change global umask to compensate. One CWI repair corrected these new inputs. Writer sandbox/tmp/socket restrictions remain separate advisory limitations; full controller acceptance and host target validation are mandatory.

## Required check-profile correction — 2026-10-31

REQ-D03-004 ended STOPPED_INCOMPLETE because its frozen single `python3 -B implementation/scripts/validate.py` check did not record the separately required complete-range formatting check. Supported CWI CLI repeated --check creates ordered check-1/check-2 and runs both at baseline/candidate/final. New REQ-D03-004-R1 explicitly adds `git diff --check ACTUAL_NEW_LAUNCH_BASE HEAD --` with a literal committed SHA, never shell expansion; preserve permanent validator and all prior environment values. Already ignored frozen context carries exact CWI-authored candidate files,296,842UTF-8bytes including SALVAGE.md, within existing bounds. No backend mutation, global configuration or security change. Host process namespace inspection confirms terminal owners gone; sandbox PID invisibility alone is not shutdown evidence.

## Readable-snapshot integration checkpoint — 2026-10-31

Run 7ee32819-ee00-4b1b-bdba-ea26fb90cf3e used the unchanged stable map, clean backend 1f68060, Codex 0.166.0/executable SHA b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8, explicit gpt-6-astra/high, 2700-second agent/validation deadlines and soft/hard descriptor limits 4096/1048576. Both meaningful full-suite and literal-base full-diff checks were frozen and passed. Current specification remains v1.4, SHA fefc5b9b750ca270f286c7b799f71da610f33c3babf77e53b2321bf1d060664f.

Actual Linux publication/race/process/fault tests passed after a CWI product-layout repair kept private payload and destination within the same held parent. No host permission elevation, global setting, dependency or backend change was needed for publication. Writer-local restrictions remained advisory; real controller failures required product repair. Host owners exited before integration. Target on exact c57a621c3e3f7806030de13b75b4fe2890b81cc7: 489/489, zero skips/failures/errors, 340.412 test seconds; clean unchanged accepted source; completed 2026-10-31T17:12:46.950703+00:00; stdout SHA-256 781599a6858d5e2b51cb3c96c6d6317a4196af9f617c1a702407be7a5300fd32. Full validation inherited recorded limits and left source clean. All 15 retained runs reconcile; no live operation remains. No product-live or scientific evidence is claimed.

## Refresh prelaunch inspection — 2026-10-31

At 17:35 UTC host process inspection found no related controller/role/validator. All fifteen retained runs were inspected through status/diagnose; twelve accepted commits are ancestors of main and three terminal failures remain preserved. c57a621 final receipt, final validations/review hashes and historical exact integration/target-validation evidence were independently reverified; 7f3f081 changes administrative Markdown only. Clean backend remains 1f68060 and selected Codex executable digest remains b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8. Selected CLI reports ChatGPT login; local catalog advertises gpt-6-astra/high. No installation/configuration/backend change. REQ-D03-005 uses the unchanged stable map, explicit gpt-6-astra/high, 2700-second deadlines, soft descriptor 4096 and both required frozen checks. Detailed non-secret reconciliation evidence is under local/reconciliation-20261031-view-refresh/.

## Preserved refresh integration and CLI preflight — 2026-10-31

REQ-D03-005 used unchanged stable environment, backend 1f68060, selected Codex 0.166.0 SHA b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8, explicit gpt-6-astra/high,2700-second agent/validation limits and process-local descriptors4096/1048576. All17 actual role invocation configurations and completed transports were inspected; no independent server-side attestation is claimed. No dependency/security/host/backend change.

Target exact8cfb035:579/579 in382.974 testseconds,zero skips/errors/failures/source mutation; completed 20:29:18.551279Z; stdout a3fd79bdc352f9a1f28e0b4626d9920387d0c1e5c5f7a974fdca7776c7af3703. Post-run ownership was resolved before exact integration. The local model catalog fetched 20:25:43Z still advertises gpt-6-astra/high; higher catalog efforts do not change project ceiling xhigh. Selected CLI login status succeeds with ChatGPT, with the existing read-only PATH-alias warning only. Next REQ-D03-006 preserves the same launch map and exact executable/backend, freezing both full-suite and literal committed-base complete-diff checks.

## Local CLI integration and view-CLI preflight — 2026-10-31

REQ-D03-006 retained backend1f68060, Codex0.166.0/executable SHAb8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8, stable environment, explicit gpt-6-astra/high,2700-second deadlines and process-local descriptors4096/1048576. All14 completed role configurations/transport hashes were inspected; no independent provider-side attestation is claimed. No dependency/security/host/backend change.

Integrated-target validation on exact0a875dd4c822465a297ff3e6757f69962823aea0:657/657 in422.364 test seconds,zero skips/errors/failures/source mutation; completed2026-10-31T22:26:56.729486+00:00; stdout SHA-256d62420d88da32b38a7d5d42fe3664dfebb7219e2a239348a9708866fdc8bcd4f, empty stderr. The recorded stable environment and4096/1048576 descriptor limits were retained; main stayed clean at the accepted tree.

Prelaunch reconciliation for REQ-D03-007 inspected all17 retained status/diagnose records:14 accepted ancestors of main,3 terminal failures, no lease/inflight/quarantine/recording gaps. Local catalog fetched22:20:55.957159Z advertises gpt-6-astra/high; higher advertised efforts do not change ceiling xhigh. Selected CLI login reports ChatGPT with the existing read-only PATH-alias warning only. Same stable map/backend/executable, literal-base full-diff check and full validator remain required. Actual start identity/settings belong locally until safe reconciliation.

## 2026-11-01 — Post-view-CLI environment evidence

REQ-D03-007 retained backend1f68060b5a5a9964c91811a53d3a515e0b01a073, Codex0.166.0 executableSHA256b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8, explicitgpt-6-astra/high and frozen environmentdigest46f63a419a7b148d3489f4a2dd9109c1c3d3a3f334364123e7a858ddee6ace09. Final696/696; integrated target696/696 in451.163s, zero skips/errors/failures/source mutation, completed2026-11-01T00:11:17.402942+00:00, stdoutSHA256ba0d147f67885b616e725a45e89fc51b68b4ad92923174d43a727168f3b64f94 and empty stderr. Process-only4096/1048576 descriptors; unchanged source-local validator and two orderedchecks. No host-wide security/environment/backend change. The current local model catalog advertisesgpt-6-astra/high; project effort ceiling staysxhigh despite higher catalog options. Refresh non-secret catalog/login/executable evidence before next launch; do not infer server model identity from self-report. New REQ-D03-008 retains the same environment and2700-second deadlines.

## Diagnostic repair and resource-ledger preflight — 2026-11-01

REQ-D03-008 / CWI 4c1833ef-8ef9-4b07-9f33-79acb6f7e8b0 finally accepted and exact-integrated `3f4564c770bdec8848587ad6052a8f2c6bdb75de`, tree `204b5eb30e5309bd23839bd58d0afb2e00b2d082`, final receipt `80ad5251c81e2a26c32e7528c58cdc41d38f93ef0a4247a1e00487c1f265df94`. Final controller 707/707 in 475.208s; Integrated target 707/707 in 476.667s, zero skips/errors/failures and unchanged clean source; completed 2026-11-01T01:20:15.956694+00:00, stdout SHA-256 `8479e46b433fb6d6c318fd9256b0cd365c79d76e9beac27a192ec8bb4f58a077`, empty stderr. One internal test repair resolved F-001/F-002. All 696 predecessor tests and the permanent validator are preserved. Backend1f68060b5a5a9964c91811a53d3a515e0b01a073 and selected Codex0.166.0 executableSHA256b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8 remain clean/unchanged. Stable environmentdigest46f63a419a7b148d3489f4a2dd9109c1c3d3a3f334364123e7a858ddee6ace09; explicitgpt-6-astra/high; process-only descriptors4096/1048576;2700-second deadlines and both exact frozen checks. All8prepared/completed role configurations and retained usage evidence inspected; no server attestation claimed. No dependency/security/host/backend change.

Before the next launch, all19retained status/diagnose records reconcile:16accepted ancestors of main and3terminal failures, no CWI lease/inflight/quarantine. Local catalog fetched2026-11-01T01:12:41.364677442Z advertisesgpt-6-astra/high; selected CLI login remainsChatGPT. Higher catalog efforts do not change project ceilingxhigh. REQ-D04-001 preserves these settings with2milestones. Target-validation completion and administrative checkpoint precede its start.
