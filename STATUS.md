# Development status — research_pipeline

## Milestone checkpoint

- Human contract: unchanged PROJECT.md and root AGENTS.md. **M1 accepted; M2 selected next.** M3–M5 have not started. M5 requires researcher-supplied benchmark questions/materials and human scientific acceptance.
- M1 implementation run `20261110T091713_50e21105` merged locally at `dd2efc9`; final and combined pre-merge suites each passed 34 tests, including real Codex scientific work, 18 numerical estimates, bounded reproduction agreeing within rtol=atol=1e-12, input preservation and inactive services.
- M1 evidence-closeout run `20261110T104911_bee8ceea` merged at `a39d454`; final/pre-merge verification passed. Its Reviewer directly assessed both saved scientific demonstrations and confirmed meaningful planning, derivation, full-text primary literature, computation, preliminary conclusions and reproduction. Authoritative review: `coding_pipeline/logs/20261110T104911_bee8ceea/milestones/001/review.md`; synthesis: `development/requests/m1-implementation.md`.
- Both prior run worktrees are removed and owning execs exited successfully. No prior implementation/research jobs remain. Persistent M1 evidence: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/live-host-acceptance/`.
- Retain existing memory/zero-swap/task/wall protection and systemd/Bubblewrap cleanup. Host delegates memory/pids, without CPU quota; CPU fraction/time are uncapped. Reliable context occupancy and hard spending caps are unavailable. No host settings changed. Trusted controller final tests handle capabilities unavailable to restricted Writers.

## Current M2 request

- Objective: persistent checkpoints, full pause/resume, changed questions/instructions/feedback, preserved human notes/unaffected results, checkpoint-based crash recovery and automatic fresh-context primary rollover with cumulative budgets. Actual live scientific continuation is required before M3.
- Request ID: `m2-persistence-human-direction-rollover-20261110T111256Z-aa5787cf`.
- Frozen directory: `coding_pipeline/logs/manager/m2-persistence-human-direction-rollover-20261110T111256Z-aa5787cf/` containing `request.md`, `config.toml`, and planned `receipt.json`.
- Effective config: standard; auto_merge=true; Architect gpt-6.1-sol/xhigh; Writer and Reviewer gpt-6.1-sol/high; writer_network preauthorized; other settings preserved.
- Submitted from checkpoint `6201787`. Actual run `20261110T111316_7e4bef43`, reported running in Writer review-repair 1 for pipeline milestone 002 (full pause); branch `cwi/20261110T111316_7e4bef43`; worktree `coding_pipeline/logs/20261110T111316_7e4bef43/worktree`. Live owner: exec session `72841`, native PID `62544` / start ticks `1822351` (request-directory `ownership.json`). Receipt present. Do not resume/retry concurrently; one active implementation request at a time.
- Pipeline roadmap: (1) persistent checkpoints, guarded Markdown publication, human direction/resumption/accounting; (2) cooperative checkpoints/full pause; (3) automatic primary rollover; (4) real opt-in M2 demonstration and handoff to final tests. First increment is reviewed and committed on the feature branch at `74bc2d6`; Writer reported 40 tests, OK with two local skips. Review repairs retained pending accounting through uncertain cleanup and permitted service/old-checkpoint recovery despite invalid drafts. Full pause, automatic rollover and live demonstration remain; no M2 target integration or acceptance yet.
- Current pause increment is implemented but under review repair. Writer reported 52 successful tests with two local skips. Reviewer requests bounded handoff preparation, preservation of prepared checkpoints across interrupted recovery, and one-time charging of recovery finalization. Automatic rollover and real M2 host demonstration remain pending.
- Controller-host live settings for submission/recovery/approval: `RESEARCH_PIPELINE_M2_LIVE=1`; `RESEARCH_PIPELINE_M2_OUTPUT_DIR` = absolute request-directory path plus `/live-host-acceptance`. M1 live opt-in stays disabled. Writer/Reviewer implementation readiness must hand off to Architect completion and mandatory controller final tests; no circular Writer host-verification milestone.

## Continuation

- Monitor exec `72841` and flow status/report for `20261110T111316_7e4bef43`; reconcile native process/lock state before recovery. Trust pipeline implementation/testing/review/live reports; manager performs no independent product inspection/review/testing.
- Require actual pause/edit/resume and fresh-session task continuation, cumulative limits and cleanup evidence before accepting M2 or proceeding to M3. Use documented conservative short-session fallback rather than a false occupancy guarantee. Preserve protected inputs and existing M1 evidence.
- Components: pipeline clean main `6c7b4d4`; controller clean `project-manager/setup` at `d0771db`. No manager component repairs or restart needed.
- No COMPLETE until all current PROJECT.md gates, including human M5 scientific acceptance, pass and all jobs stop.
