# Development status — research_pipeline

## Progress and decisions

- PROJECT.md is the unchanged human-owned product contract. Clean restart: no product implementation or completed milestone yet.
- Selected increment: M1 minimal scientific loop, including CLI start/inspect, current questions/evidence intake, actual Codex research, literature, analytical reasoning, executable computation, Markdown artifacts, basic enforced boundaries and essential resource protections.
- Acceptance requires pipeline-reported focused automated checks and an actual bounded question-to-artifact demonstration. The pipeline owns implementation, testing, review, and the demonstration; the manager does not independently inspect or test completed product work.
- M2–M4 follow only after preceding demonstrations pass. M5 additionally requires human scientific acceptance; researcher-supplied benchmark questions/materials are not present.
- Broad approach: small Python/Linux package, ordinary files, minimal Codex CLI boundary, no speculative infrastructure. Writer network preauthorized for literature and actual model-backed demonstration; sandbox restrictions remain binding.
- Prepared runtime .gitignore is tracked unchanged with this management checkpoint so the repository can be clean for pipeline submission. No human source edits or staged files were present at intake. Initial Git commit already exists.

## Active pipeline work

- Request ID: `m1-minimal-scientific-loop-20261110T091644Z-1be6cf51`.
- Objective: implement and demonstrate M1 as described above.
- Frozen request: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/request.md`.
- Effective config: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/config.toml` (standard; auto_merge=true; Architect gpt-6.1-sol/xhigh; Writer and Reviewer gpt-6.1-sol/high).
- Receipt: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/receipt.json`.
- Submission checkpoint: `3583428`; submitted in standard mode with explicit frozen config.
- Actual run: `20261110T091713_50e21105`; reported running in planning. Local branch `cwi/20261110T091713_50e21105`; worktree `coding_pipeline/logs/20261110T091713_50e21105/worktree`.
- Ownership: live manager-owned exec session `18506`; no resume/retry while it remains active. Receipt was published successfully.
- Reconciliation: `flow discover` returned no runs; pipeline logs tree did not previously exist. No earlier worktree or partial run is recorded. One implementation request at a time.

## Components and continuation

- Pipeline: clean `main` at `6c7b4d4` (native Codex authentication reuse). Controller: clean `project-manager/setup` at `d0771db`. No manager repairs or required restart.
- Blockers: none established; actual nested Codex execution and live demonstration must be established by pipeline reports.
- Next action: monitor the active M1 run using status/report and the owned exec session; resolve reported questions and trust reported test/review/demo outcomes before proceeding.
- Recovery: discover by the request ID above, then use status/report and reconcile process ownership before resume/retry. Do not mark COMPLETE until all current PROJECT.md acceptance gates are satisfied and all jobs stop.
