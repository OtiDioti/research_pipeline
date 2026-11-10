# Development status — research_pipeline

## Accepted and unfinished work

- Human contract: current PROJECT.md and root AGENTS.md are unchanged. **M1 accepted; M2 unfinished.** M3–M5 have not started. M5 additionally requires researcher-supplied benchmark questions/materials and human scientific acceptance.
- M1 implementation run `20261110T091713_50e21105` merged at `dd2efc9`; final and pre-merge suites each passed 34 tests, including real Codex literature/analytical/numerical work, 18 estimates, bounded reproduction agreeing within rtol=atol=1e-12, protected inputs and confirmed cleanup.
- M1 evidence-closeout run `20261110T104911_bee8ceea` merged at `a39d454`. Writer and Reviewer directly assessed both scientific demonstrations and found the bounded M1 objective satisfied. Review: `coding_pipeline/logs/20261110T104911_bee8ceea/milestones/001/review.md`; synthesis: `development/requests/m1-implementation.md`.
- M2 reviewed work is preserved only on feature branch `cwi/20261110T111316_7e4bef43`: persistence/human direction/resumption at `74bc2d6`, then cooperative checkpoints/full pause and reviewed repairs at `cdf0b8f80126f4695821580aa5f3c03da2d31582`. Latest Writer result: 56 successful tests, two disclosed local skips. Actual M2 host verification has not run; no M2 target integration or acceptance.
- Remaining M2 work: primary fresh-context rollover, opt-in real pause/edit/resume/rollover demonstration, final review/testing and local integration. Do not proceed to M3 until the current PROJECT.md M2 gates pass.

## Preserved request and recovery ownership

- Objective: M2 persistence, full suspension, current questions/instructions/feedback, preserved human notes/unaffected results, crash recovery and primary rollover with cumulative budgets.
- Request ID: `m2-persistence-human-direction-rollover-20261110T111256Z-aa5787cf`.
- Frozen directory: `coding_pipeline/logs/manager/m2-persistence-human-direction-rollover-20261110T111256Z-aa5787cf/`; original `request.md`, effective `config.toml`, creation `receipt.json` and operational shutdown receipts remain there.
- Actual run: `20261110T111316_7e4bef43`; resumed **running**, phase `plan`, pipeline milestone 003 (primary rollover). Report: `coding_pipeline/logs/20261110T111316_7e4bef43/summary.md`.
- Worktree: `coding_pipeline/logs/20261110T111316_7e4bef43/worktree`; clean, preserved at reviewed HEAD `cdf0b8f`. Roadmap, prior plans/reviews/tests and partial planning artifacts remain in the run directory.
- Prior retirement: verified owner and descendants stopped after SIGINT; run checkpointed interruption. Evidence: request-directory `shutdown-ownership-before.json`, `shutdown-interrupt.json`, `shutdown-termination.json`.
- Recovery invocation, 2026-11-10: current root, unchanged human contract, clean target/component checkouts, matching discovery/receipt and interrupted planning state reconciled. Preserved worktree is clean at `cdf0b8f`; the exclusive run lock is free. Resume this same request with frozen configuration and enabled M2 host acceptance; no duplicate submission.
- Active recovery owner: PID `72466`, start ticks `2352086`, exec session `49093`; resumed 12:41 UTC. Identity receipt: request-directory `recovery-20261110T1241-ownership.json`. M2 live acceptance variables are enabled; M1 live inference is disabled.

## Decisions, limits and recovery

- Keep standard mode, auto_merge=true, Architect gpt-6.1-sol/xhigh, Writer and Reviewer gpt-6.1-sol/high; writer_network preauthorized. Frozen configuration is unchanged.
- Existing systemd/Bubblewrap isolation, memory/zero-swap/task/wall limits and whole-service cleanup remain required. Host delegates memory/pids without CPU quotas; CPU fraction/time are uncapped. Exact context occupancy and hard spending caps are unavailable: implement the documented conservative short-session fallback without a false 60% guarantee. Active-work accounting stays cumulative across continuation.
- Guarded Markdown publication preserves human edits; pause publication follows confirmed cleanup. Reviewed repairs retain unresolved cleanup charges, recover despite invalid drafts, bound preparation, preserve prepared handoffs across recovery and charge finalization once.
- Trusted controller final tests execute host capabilities unavailable to restricted Writers. Implementation readiness must transfer to Architect completion and final tests; avoid a circular Writer host-acceptance milestone. Manager trusts pipeline reports and performs no independent product inspection/review/testing.
- Next action: monitor this same run, resolve pipeline questions/failures, and assess its reported real M2 acceptance before integration. Reconcile live ownership again before any further recovery.
- Resume environment: `RESEARCH_PIPELINE_M2_LIVE=1`; `RESEARCH_PIPELINE_M2_OUTPUT_DIR` = absolute frozen request-directory path plus `/live-host-acceptance`; M1 live opt-in disabled. With those variables, use `flow resume 20261110T111316_7e4bef43`. Require actual scientific continuation, fresh context/stable logical identity, cumulative limits and cleanup evidence before M2 acceptance.
- Components: pipeline clean main `6c7b4d4`; controller clean `project-manager/setup` at `d0771db`. No component repairs or required restart; controller owns its lifecycle.
- Publication authority for this invocation: local commits/integration only; no push, PR, remote changes or external publication. Component repair branches must remain unmerged.
- Project completion conditions remain unmet; COMPLETE must not be written until all current PROJECT.md gates, including human M5 scientific acceptance, pass.
