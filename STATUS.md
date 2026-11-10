# Development status — research_pipeline

## Progress and decisions

- PROJECT.md is the unchanged human-owned product contract. Clean restart: no product implementation or completed milestone yet.
- Selected increment: M1 minimal scientific loop, including CLI start/inspect, current questions/evidence intake, actual Codex research, literature, analytical reasoning, executable computation, Markdown artifacts, basic enforced boundaries and essential resource protections.
- Acceptance requires pipeline-reported focused automated checks and an actual bounded question-to-artifact demonstration. The pipeline owns implementation, testing, review, and the demonstration; the manager does not independently inspect or test completed product work.
- M2–M4 follow only after preceding demonstrations pass. M5 additionally requires human scientific acceptance; researcher-supplied benchmark questions/materials are not present.
- Broad approach: small Python/Linux package, ordinary files, minimal Codex CLI boundary. Pipeline selected Bubblewrap plus a systemd user service for enforced boundaries and aggregate resource/lifetime controls. Writer network preauthorized; sandbox restrictions remain binding.
- Writer-reported partial result after review repairs: CLI/backend implemented; 22 tests passed, one service-integration class skipped. Swap accounting and local computation links were repaired. Demonstration stopped before research with exit 3 because the Writer environment lacks a user bus and native file credentials. Reviewer reports no further actionable defects but blocked acceptance; M1 remains incomplete.
- Prepared runtime .gitignore is tracked unchanged with this management checkpoint so the repository can be clean for pipeline submission. No human source edits or staged files were present at intake. Initial Git commit already exists.

## Active pipeline work

- Request ID: `m1-minimal-scientific-loop-20261110T091644Z-1be6cf51`.
- Objective: implement and demonstrate M1 as described above.
- Frozen request: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/request.md`.
- Effective config: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/config.toml` (standard; auto_merge=true; Architect gpt-6.1-sol/xhigh; Writer and Reviewer gpt-6.1-sol/high).
- Receipt: `coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/receipt.json`.
- Submission checkpoint: `3583428`; submitted in standard mode with explicit frozen config.
- Actual run: `20261110T091713_50e21105`; Reviewer blocked after repair attempt 1: implementation defects resolved, live acceptance still pending. No product commit or integration yet. Local branch `cwi/20261110T091713_50e21105`; worktree `coding_pipeline/logs/20261110T091713_50e21105/worktree`.
- Ownership: original exec session `18506` exited with code 4; no active pipeline job remains from that invocation. Recovery prepared for the same run; receipt remains valid.
- Reconciliation: `flow discover` returned no runs; pipeline logs tree did not previously exist. No earlier worktree or partial run is recorded. One implementation request at a time.

## Components and continuation

- Pipeline: clean `main` at `6c7b4d4` (native Codex authentication reuse). Controller: clean `project-manager/setup` at `d0771db`. No manager repairs or required restart.
- Acceptance blocker: pipeline still owes actual service/resource checks and the real Codex scientific demonstration. A read-only manager environment-presence check found the controller host has a user bus and native file credentials; these were absent only in the Writer environment. Operational receipt: request directory `host-environment-receipt.json`. Presence alone does not establish product functionality; verification must remain inside coding_pipeline.
- Recovery decision: preserve this run and add a small opt-in unittest live acceptance path executed by pipeline-controlled host final/premerge verification. Recovery input: original request directory `recovery-input-001.md`. Resume with `RESEARCH_PIPELINE_M1_LIVE=1` and `RESEARCH_PIPELINE_M1_OUTPUT_DIR` pointing to request directory `live-host-acceptance`. No credential/bus access is granted to the restricted Writer.
- Next action: resume the same run with that input/environment, record new ownership, and require actual pipeline-reported demonstration/reproduction/cleanup success before M2. Do not mark M1 complete based only on unit tests or code review.
- Recovery: discover by the request ID above, then use status/report and reconcile process ownership before resume/retry. Do not mark COMPLETE until all current PROJECT.md acceptance gates are satisfied and all jobs stop.
