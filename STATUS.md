# Development status — research_pipeline

## Current progress

- Human contract: unchanged PROJECT.md and root AGENTS.md. Clean-restart product; **M1 remains incomplete**. M2–M5 have not started; M5 requires human scientific acceptance and researcher-supplied benchmark materials.
- M1 CLI/backend implementation and code-review repairs are preserved. Latest reviewed feature commit: `30e4707`. Target main has management checkpoints only; product integration is pending.
- Pipeline-reported local checks: 24 passes; Writer-local service/live cases unavailable. Actual Bubblewrap protection/computation passed. Host final verification is now enabled and has run; no actual research session has started successfully.
- The pipeline owns implementation, tests, review and functional demonstrations. Manager uses its reports and performs no independent product inspection/review/testing.

## Active request and ownership

- Request: `m1-minimal-scientific-loop-20261110T091644Z-1be6cf51` — implement and demonstrate M1 minimal scientific loop.
- Request directory: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/`; frozen `request.md`, `config.toml`, and `receipt.json` remain there.
- Configuration: standard, auto_merge=true; Architect gpt-6.1-sol/xhigh; Writer and Reviewer gpt-6.1-sol/high; writer_network preauthorized. No settings substituted.
- Actual run: `20261110T091713_50e21105`; branch `cwi/20261110T091713_50e21105`; worktree `coding_pipeline/logs/20261110T091713_50e21105/worktree`.
- Current phase: running Writer recovery in pipeline milestone 003 / integration repair 2. Live owner: manager exec session `29827`. Do not resume/retry concurrently.
- Earlier exec sessions `18506`, `95848`, `9727` exited blocked with code 4. Partial work, immutable reports and useful unfinished documentation were preserved. Reported preflight probes cleaned up; no research jobs were launched.

## Material decisions and blockers

- Writer lacks host bus/authentication by design. Host-presence checks found both available; protected capabilities were not exposed to the Writer. Recovery 001 added a small opt-in live unittest for controller-owned host verification. Recovery 002 corrected ordering: implementation readiness transfers to final tests, without claiming M1 acceptance.
- First host failure: uninstalled source-checkout imports. Pipeline repaired test imports and CLI subprocess discovery.
- Next host failure: `cpu.max` unavailable. Read-only diagnosis confirmed user services receive memory/pids controllers, without CPU-controller delegation. No host settings were changed. Operational evidence: request directory `host-environment-receipt.json` and `host-cgroup-receipt.json`.
- Latest decision/input: request directory `recovery-input-003.md`. Remove the implementation-added CPU-percentage control, which PROJECT.md does not require; retain enforced wall time, aggregate memory, zero swap, task/thread count, one researcher, protected inputs, and whole-service cleanup. Disclose unavailable CPU capping. No alternative execution framework or host administration.
- Remaining acceptance: actual host service/resource checks, real Codex literature/analytical/numerical research, bounded reproduction and cleanup must pass with pipeline evidence before M2. Enabled gates must fail rather than skip when necessary capabilities are missing. Context occupancy/spending caps remain disclosed backend limitations.

## Continuation

- Monitor exec session `29827` and `flow status/report 20261110T091713_50e21105`. Reconcile process ownership before any resume/retry; discover by the stable request ID if necessary.
- Preserve live-test environment for every recovery/approval: `RESEARCH_PIPELINE_M1_LIVE=1`; `RESEARCH_PIPELINE_M1_OUTPUT_DIR` = absolute request-directory path plus `/live-host-acceptance`. Both frozen role config and original scope remain binding. Current source-level recovery returns to controller final tests.
- Pipeline component: clean main at `6c7b4d4`. Controller: clean `project-manager/setup` at `d0771db`. No component repairs or restart required.
- Next action: await current repair/review and mandatory host final verification; resolve concrete pipeline failures. Update this checkpoint and README as warranted after confirmed integration. Do not write COMPLETE until all current PROJECT.md gates, including human M5 acceptance, pass and all jobs stop.
