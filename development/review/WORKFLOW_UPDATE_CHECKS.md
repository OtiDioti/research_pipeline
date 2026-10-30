# Continuous-development documentation update: verification

**Date:** 2026-10-30. **Scope:** revised Markdown workflow documents and their compatibility with the supplied controller snapshot. This is not an authenticated Codex run, full backend regression rerun, product test, backend repair, or approval of the user's local environment.

## Inputs and changes

The earlier 44-file development kit and supplied coding_pipeline archive were available locally. The user's revised coordinator prompt supplied the model/effort requirement and focused backend-maintenance exception. The actual current target Git repository and its full project_description.md were not available; this update preserves that external specification and provides an upgrade path that does not overwrite existing progress.

All 98 original backend files were compared byte-for-byte to their archive contents after the checks. None changed. No product code, controller patch, daemon, or executable supervisor is included in the updated kit. The existing exact-baseline bootstrap Markdown and embedded validation program are unchanged; SHA-256:

`8ecc1321756dc1c5803baf20b6e97fad14e9f48610df008906676d4fe1a2ea77`

## Checks actually executed

| Check | Result and meaning |
| --- | --- |
| Markdown fences, local file links, nonempty documents, root layout | Checked across the updated complete tree; no detected errors. Links to the separately supplied project_description.md are intentional external requirements, not a bundled replacement. |
| Shell examples | All 15 Bash blocks parsed with bash -n; syntax only, not claims of actual installed commands or permission. |
| Embedded standalone Python example | Parsed successfully; the unchanged bootstrap was not re-certified as a new implementation here. |
| CWI command contracts | Seven parser cases verified start flags for 1/2/3 milestones plus status, diagnose, resume, and reconstruct. No product run or provider call. |
| Explicit model/effort in runbook starts | Both start examples supply --model and --reasoning. |
| Effort guard | Nine shell-only cases: low/medium/high/xhigh admitted; max/ultra/extra-high/empty effort and a missing model rejected. This does not verify that any real provider supports a particular model/effort pair. |
| Focused original-backend tests | 12 tests passed: the test_cli and test_config modules, plus test_success_captures_events_response_and_isolated_invocation from test_codex_cli.CodexCliAdapterTests. The latter uses a mock CLI and checks model/effort arguments and isolation controls. |
| Original backend source preservation | All 98 original file contents match the supplied archive. |

The first focused-test attempt had 11 passes and one error: Python ZIP extraction had not restored the archive's executable mode on bin/agentic-flow. The archive specified mode 100755 while the extracted copy was 100644. Restoring that archived permission, without changing source, resolved the error; the same 12 tests then passed. This is extraction preparation, not a backend source fix, and is not presented as a software defect repaired under the new exception.

The focused command was run from the extracted backend root:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests python3 -m unittest -v test_cli test_config test_codex_cli.CodexCliAdapterTests.test_success_captures_events_response_and_isolated_invocation
```

## Policy walkthrough performed

The documents were checked against the following scenarios: fresh commissioning; first accepted-unmerged result; approval recorded before a pending fast-forward; ordinary continuous request/phase progression; interruption during a run; interruption after integration but before the checkpoint; existing incompatible model settings; unresolved requested model identity; legitimate product rejection vs backend defect; a focused backend repair with an old bound run; quota exhaustion across sessions; mandatory scientific/human evidence still missing; optional explicit first-run preauthorization; and adoption into a repository with existing progress.

This was a document consistency review by the same assistant, not an independent agent review and not an executable end-to-end test of those scenarios.

## Remaining limitations

No authenticated Codex executable was available for live integration. The requested Astra 6.1 identifier was not verified in the official model catalog checked for this update; local resolution or an explicit human correction remains required. Provider access, billing, OS permissions, actual prior runs, local customizations, and the user's full specification must be checked on the target machine.

The original comprehensive backend report remains historical and unchanged in its test results; these 12 focused passes do not erase its earlier failures or establish a clean full suite. See [the original results](TEST_RESULTS.md). Current model references are recorded in [MODEL_POLICY.md](../MODEL_POLICY.md).

The continuous loop is instruction-driven. No claim is made that prompts alone enforce a financial ceiling, guarantee model honesty, guarantee project completion, or restart a terminated Codex session. A stronger launcher/supervisor is a separate implementation and evaluation task.
