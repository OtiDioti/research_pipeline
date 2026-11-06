# Supplied-pipeline test results

**Review date:** 2026-10-29. **Target:** the supplied archive, unchanged. **Environment:** Linux, Python 3.13.5, git version 2.47.3; no real Codex executable or authenticated service session available.

## Execution scope and aggregate result

All 45 `test_*.py` modules were discovered and run separately, using up to eight concurrent module processes. Each process ran:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p <module.py> -v
```

The explicit live-integration flags were not enabled. This was a complete per-module discovery run, **not** a successfully completed single-process serial suite. An earlier serial attempt was deliberately stopped before completion and is not included in these counts.

| Aggregate | Cases |
| --- | ---: |
| Discovered and reported by unittest | 1031 |
| Passed | 1000 |
| Skipped | 17 |
| Assertion failures | 7 |
| Errors | 7 |

42 module processes completed successfully; 3 returned failure. **The supplied suite did not fully pass in this environment.** The static inventory contains 1,032 methods named `test_*`; runtime discovery reports 1,031 cases. Static method counts are not execution evidence.

## Finding T-01 — crash-recovery test depends on an installed Codex

`test_recovery_logging.RecoveryLoggingTests.test_abrupt_controller_loss_is_observed_only_on_subsequent_resume` failed: its child process exited 1 rather than the expected injected-crash code 23. The test constructs a real `start(StartOptions(...))` in a new process without injecting the fixture adapter or Codex discovery. `cwi/orchestration.py` discovers a Codex executable before reaching the intended crash boundary. No executable is installed here.

The same test failed when rerun alone. A controlled repeat using the repository's existing `tests.codex_fixture.write_codex` to supply a temporary mock executable passed. No source file was changed and no real model call occurred. This isolates a non-hermetic test prerequisite; it does not independently prove or disprove the underlying production crash-recovery behavior.

Local action: reproduce on the user's compatible authenticated setup; if improving test isolation, handle that as an explicit backend-maintenance change, not an unrecorded edit during research-product development.

## Finding T-02 — persistent-session tests hit a one-second deadline

`test_sessions.py` initially reported one failure and seven errors, all associated with persistent-session invocation timeouts. Its `PersistentSessionTests.setUp` writes `agent_timeout_seconds = 1`. A subsequent run of the module alone reduced the result to **24 passed, 2 errors, 2 skipped** out of 28, with the two remaining errors also reporting timeouts.

The remaining tests were `test_completion_artifact_before_atomic_publication_cannot_activate_session` and `test_unavailable_persisted_history_stops_without_substitution_or_retry`. This is evidence of deadline sensitivity in this environment, not a verified diagnosis that every failure is harmless load noise. No timeout was relaxed in the supplied source, and the module is not reported as passing. Reproduce and diagnose locally before relying on the affected guarantees.

## Finding T-03 — pytest fixture relocates a virtual-environment executable

Five `test_test_bootstrap.py` cases failed. A direct diagnostic reproduction of `test_pytest_bootstrap_merge_uses_junit_and_preserves_exit_five` showed the actual baseline stderr: `No module named pytest` from the temporary `pytest-bin/python` executable.

The fixture first confirms that the original interpreter can import pytest, then symlinks that executable into a new directory. In this environment, launching `/opt/pyvenv/bin/python` directly uses the virtual environment and imports pytest 9.0.2. Launching the temporary symlink changes `sys.prefix` to `/usr` and cannot import pytest. A separate minimal process probe reproduced this difference. Thus the fixture's precheck does not establish that its later executable retains the same package environment.

This identifies a concrete cause for the diagnostic reproduction and a shared fixture affecting the five failures. The other four were not individually repaired and rerun to a passing result. Do not convert their original failures into passes by inference. A locally appropriate interpreter/fixture should be qualified through an explicit backend test change when necessary; do not weaken product validation.

## What was not established

No real authenticated Codex workflow, remote model response, permission escalation from an outer Codex sandbox, Windows/macOS support, or user-machine installation was exercised. Existing skipped live/probe tests remain skipped. The review is not a security audit or a proof that the implementation has no defects. All original archive files retained their recorded SHA-256 hashes after testing.

## Starter-kit checks, distinct from backend tests

The inline first-run bootstrap checker was tested separately against ten disposable Git/fixture scenarios: exact documentation baseline, forbidden root file, root symlink, legitimate linked-worktree `.git` pointer, a different documentation-only commit, zero tests, all-skipped tests, failing tests, actual candidate-source tests, and permanent-validator failure. All ten produced the expected outcomes. These were test fixtures outside the deliverable, not an implementation of the research product. They do not replace a real CWI/CLI integration test.

## Per-module original results

| Module | Total | Passed | Skipped | Failures | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| `test_agent_logging.py` | 22 | 22 | 0 | 0 | 0 |
| `test_amendment_conversations.py` | 32 | 31 | 1 | 0 | 0 |
| `test_automatic_start.py` | 8 | 8 | 0 | 0 | 0 |
| `test_cli.py` | 4 | 4 | 0 | 0 | 0 |
| `test_codex_cli.py` | 45 | 36 | 9 | 0 | 0 |
| `test_codex_runtime.py` | 12 | 12 | 0 | 0 | 0 |
| `test_codex_selection.py` | 8 | 8 | 0 | 0 | 0 |
| `test_command_start.py` | 18 | 18 | 0 | 0 | 0 |
| `test_config.py` | 7 | 7 | 0 | 0 | 0 |
| `test_contracts.py` | 27 | 27 | 0 | 0 | 0 |
| `test_controller.py` | 22 | 22 | 0 | 0 | 0 |
| `test_controller_logging.py` | 22 | 22 | 0 | 0 | 0 |
| `test_conversations.py` | 18 | 18 | 0 | 0 | 0 |
| `test_criterion_evidence.py` | 17 | 17 | 0 | 0 | 0 |
| `test_diagnostics.py` | 33 | 33 | 0 | 0 | 0 |
| `test_evidence.py` | 34 | 34 | 0 | 0 | 0 |
| `test_finalization.py` | 51 | 49 | 2 | 0 | 0 |
| `test_git_logging.py` | 22 | 22 | 0 | 0 | 0 |
| `test_logging_hardening.py` | 7 | 7 | 0 | 0 | 0 |
| `test_m00_probes.py` | 2 | 2 | 0 | 0 | 0 |
| `test_milestone.py` | 48 | 48 | 0 | 0 | 0 |
| `test_observability.py` | 32 | 32 | 0 | 0 | 0 |
| `test_orchestration.py` | 22 | 22 | 0 | 0 | 0 |
| `test_preflight.py` | 17 | 17 | 0 | 0 | 0 |
| `test_prompts.py` | 7 | 7 | 0 | 0 | 0 |
| `test_reconstruction.py` | 46 | 46 | 0 | 0 | 0 |
| `test_recovery_logging.py` | 21 | 20 | 0 | 1 | 0 |
| `test_release.py` | 18 | 18 | 0 | 0 | 0 |
| `test_release_live.py` | 1 | 0 | 1 | 0 | 0 |
| `test_repair.py` | 51 | 50 | 1 | 0 | 0 |
| `test_repository_coordination.py` | 18 | 18 | 0 | 0 | 0 |
| `test_repository_logs.py` | 23 | 23 | 0 | 0 | 0 |
| `test_roadmap.py` | 29 | 29 | 0 | 0 | 0 |
| `test_run_setup.py` | 18 | 18 | 0 | 0 | 0 |
| `test_sessions.py` | 28 | 18 | 2 | 1 | 7 |
| `test_source_launcher.py` | 23 | 23 | 0 | 0 | 0 |
| `test_state.py` | 25 | 25 | 0 | 0 | 0 |
| `test_state_store.py` | 24 | 24 | 0 | 0 | 0 |
| `test_terminal_progress.py` | 27 | 27 | 0 | 0 | 0 |
| `test_test_bootstrap.py` | 21 | 16 | 0 | 5 | 0 |
| `test_test_discovery.py` | 33 | 33 | 0 | 0 | 0 |
| `test_test_execution.py` | 7 | 7 | 0 | 0 | 0 |
| `test_validation.py` | 40 | 40 | 0 | 0 | 0 |
| `test_validation_logging.py` | 21 | 21 | 0 | 0 | 0 |
| `test_workflow.py` | 20 | 19 | 1 | 0 | 0 |
