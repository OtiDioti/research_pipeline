# Development status — research_pipeline

## Progress and decisions

- PROJECT.md is the unchanged human-owned product contract. Clean restart: no product implementation or completed milestone yet.
- Selected increment: M1 minimal scientific loop, including CLI start/inspect, current questions/evidence intake, actual Codex research, literature, analytical reasoning, executable computation, Markdown artifacts, basic enforced boundaries and essential resource protections.
- Acceptance requires pipeline-reported focused automated checks and an actual bounded question-to-artifact demonstration. The pipeline owns implementation, testing, review, and the demonstration; the manager does not independently inspect or test completed product work.
- M2–M4 follow only after preceding demonstrations pass. M5 additionally requires human scientific acceptance; researcher-supplied benchmark questions/materials are not present.
- Broad approach: small Python/Linux package, ordinary files, minimal Codex CLI boundary. Pipeline selected Bubblewrap plus a systemd user service for enforced boundaries and aggregate resource/lifetime controls. Writer network preauthorized; sandbox restrictions remain binding.
- Writer-reported partial result: CLI/backend implemented; 19 tests passed, one service-integration class skipped. Its actual demonstration stopped before research with exit 3 because the Writer environment lacks a user bus and native file credentials. M1 acceptance remains incomplete.
- Prepared runtime .gitignore is tracked unchanged with this management checkpoint so the repository can be clean for pipeline submission. No human source edits or staged files were present at intake. Initial Git commit already exists.

## Active pipeline work

- Request ID: `m1-minimal-scientific-loop-20261110T091644Z-1be6cf51`.
- Objective: implement and demonstrate M1 as described above.
- Frozen request: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/request.md`.
- Effective config: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/config.toml` (standard; auto_merge=true; Architect gpt-6.1-sol/xhigh; Writer and Reviewer gpt-6.1-sol/high).
- Receipt: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/receipt.json`.
- Submission checkpoint: `3583428`; submitted in standard mode with explicit frozen config.
- Actual run: `20261110T091713_50e21105`; reported running in review after the first Writer attempt. Local branch `cwi/20261110T091713_50e21105`; worktree `coding_pipeline/logs/20261110T091713_50e21105/worktree`.
- Ownership: live manager-owned exec session `18506`; no resume/retry while it remains active. Receipt was published successfully.
- Reconciliation: `flow discover` returned no runs; pipeline logs tree did not previously exist. No earlier worktree or partial run is recorded. One implementation request at a time.

## Components and continuation

- Pipeline: clean `main` at `6c7b4d4` (native Codex authentication reuse). Controller: clean `project-manager/setup` at `d0771db`. No manager repairs or required restart.
- Acceptance blocker: pipeline still owes actual service/resource checks and the real Codex scientific demonstration. A read-only manager environment-presence check found the controller host has a user bus and native file credentials; these were absent only in the Writer environment. Operational receipt: request directory `host-environment-receipt.json`. Presence alone does not establish product functionality; verification must remain inside coding_pipeline.
- Next action: await the Reviewer and pipeline-controlled host verification. If the actual research demonstration remains unavailable, resolve it through a pipeline recovery or focused linked request before M2. Do not call M1 complete based only on passing unit tests or integration.
- Recovery: discover by the request ID above, then use status/report and reconcile process ownership before resume/retry. Do not mark COMPLETE until all current PROJECT.md acceptance gates are satisfied and all jobs stop.
