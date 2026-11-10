# Development status — research_pipeline

## Milestones and evidence

- Human contract: unchanged PROJECT.md and root AGENTS.md. **M1 implementation and actual host demonstrations are integrated; scientific-evidence closeout is pending before M2.** M2–M5 have not started; M5 additionally requires researcher-supplied questions/materials and human scientific acceptance.
- Implementation request `m1-minimal-scientific-loop-20261110T091644Z-1be6cf51`, run `20261110T091713_50e21105`: pipeline-confirmed merged locally as `dd2efc9` (reviewed feature HEAD `c7fb08f`). Worktree removed; exec `29827` exited successfully. No pipeline/research jobs remain from that run.
- Pipeline final and combined pre-merge verification each passed 34 tests, including actual service/memory/zero-swap/task/lifetime checks, real Codex literature/analytical/numerical research and bounded reproduction. All 18 grid estimates agreed at rtol=atol=1e-12; inputs preserved and services inactive. Report: `coding_pipeline/logs/20261110T091713_50e21105/summary.md`; detailed evidence in `tests/final-004.txt.commands/0001.txt` and `tests/pre-merge-005.txt.commands/0001.txt` beneath that run.
- Persistent demo projects/receipts: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/live-host-acceptance/`. Saved inputs only seeded questions/hypothesis; actual agent artifacts and reproduction survive worktree cleanup.
- Material decisions: trusted controller host tests handle capabilities unavailable to the restricted Writer. Source-checkout test imports repaired. Removed implementation-added CPU quota because host delegates memory/pids without CPU; wall time, memory, zero swap, task bounds and whole-service cleanup remain enforced. CPU fraction/aggregate CPU time, spending caps and exact context occupancy remain unavailable and disclosed. No host settings or components changed.

## Current request and ownership

- Selected increment: M1 live-evidence closeout. Pipeline assesses saved literature/derivation/numerical artifacts, records actual observations and updates acceptance documentation; no new product behavior or paid research run.
- Request ID: `m1-live-evidence-closeout-20261110T104847Z-2c130cb6`; linked to the implementation request above.
- Frozen directory: `coding_pipeline/logs/manager/m1-live-evidence-closeout-20261110T104847Z-2c130cb6/` containing `request.md`, `config.toml`, and planned `receipt.json`.
- Config: standard, auto_merge=true; Architect gpt-6.1-sol/xhigh; Writer and Reviewer gpt-6.1-sol/high; writer_network preauthorized. Other effective settings preserved. Live inference opt-in disabled for this documentation closeout.
- Submitted from management checkpoint `0d96d80`. Actual run `20261110T104911_bee8ceea`; branch `cwi/20261110T104911_bee8ceea`; worktree `coding_pipeline/logs/20261110T104911_bee8ceea/worktree`. Reported running in baseline/planning. Live owner: manager exec session `66567`, native PID `59175` / start ticks `1677861` (request directory `ownership.json`); do not resume/retry concurrently. Receipt is present. Prior run process/worktree fully reconciled; one active request at a time.

## Continuation

- Monitor exec session `66567` and flow status/report for `20261110T104911_bee8ceea`; trust pipeline review/testing/assessment. Reconcile process ownership before recovery. The manager performs no independent product inspection/review/testing.
- If the report identifies a real M1 gap, resolve it through pipeline recovery before M2. Otherwise record M1 acceptance after local integration and choose the next M2 increment. No COMPLETE until all current PROJECT.md gates, including human M5 acceptance, pass and all jobs stop.
- Components: pipeline clean main `6c7b4d4`; controller clean `project-manager/setup` at `d0771db`. No manager component repairs or restart needed.
