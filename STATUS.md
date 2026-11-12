# Development status — research_pipeline

Updated 2026-11-12. **M1–M4 are accepted; M5 remains unaccepted and unmerged.** The workspace/budget amendment is finished. The next manager task is a fresh M5 scientific demonstration.

## Next manager session

1. Read PROJECT.md and AGENTS.md; reconcile the retained worktree, staged changes, run lock and actual process ownership. Preserve existing edits. The last implementation invocation ended blocked at Reviewer turn 21 because live scientific evidence is outstanding, not because further implementation was requested.
2. Use **`coding_pipeline/logs/20261111T063907_2732fff6/worktree/`**, branch **`cwi/20261111T063907_2732fff6`**, including its staged/uncommitted changes. HEAD is `c1cd72ef1aa34cd8a92d9e29bcab69f6e44c148d`; the revised code is not committed there or integrated into `main`. Do not reset the worktree or use the older main/installed implementation.
3. From that worktree, run a fresh `python -m unittest tests.test_m5_live -v` with its `src/` and existing dependencies on `PYTHONPATH`. The retained worktree's README documents the invocation. Verify native Codex/systemd/Bubblewrap prerequisites on the controller host before inference; report any concrete prerequisite failure.
4. Set `RESEARCH_PIPELINE_M5_INPUT_DIR` to **`/home/francesco/Desktop/gits/research_project/research_pipeline/research_example/starting_evidence`** and `RESEARCH_PIPELINE_M5_OUTPUT_DIR` to a fresh private directory under **`/home/francesco/Desktop/gits/research_project/research_pipeline/research_example/.m5-acceptance/`**. Enable only `RESEARCH_PIPELINE_M5_LIVE=1`; keep M1–M4 live gates disabled and unset `RESEARCH_PIPELINE_M5_CHECK_RECEIPT` and `RESEARCH_PIPELINE_M5_RESUME_RECEIPT`.
5. Obtain actual successful handoff/continuation, separate scientific criticism, isolated reproduction, input-integrity checks and confirmed cleanup. Record the receipt, scientific artifact paths, actual outcome and remaining acceptance gates here. Integration requires the outstanding live evidence and required checks; **human scientific acceptance is required for M5**.

The next task uses the reviewed implementation; do not repeat the completed amendment's implementation/review or accepted M1–M4 paid demonstrations. If live execution exposes a new defect, record the specific evidence. This handoff does not itself start the manager or research.

## Scientific workspace and allocation

- **Project root:** `/home/francesco/Desktop/gits/research_project/research_pipeline/research_example/`. New science belongs directly in its `work/`, `sources/`, `outputs/`, `handoffs/`, research status and indexes. Runtime state uses `.research_pipeline/`; acceptance diagnostics use `.m5-acceptance/`. Scientific work must stay outside `starting_evidence/` and `coding_pipeline/logs/`.
- **Protected inputs:** the original question, manuscript and six-band notes, plus `starting_evidence/failed_m5_20261111/`. The archived investigation is preliminary prior evidence. Assess it critically and run working copies outside starting evidence; do not resume its embedded runtime state. Research AGENTS.md was absent at last inspection; preserve and read it if supplied.
- **Authorized next-attempt bounds:** 3600 seconds of demonstration work; up to 3480 seconds of research; 3900 seconds including cleanup. Existing session/resource limits remain: primary 420 seconds, delegated/verifier 240 seconds, two agents sharing 2048 MiB with zero swap and 128 tasks, admitted jobs up to 60 seconds/concurrency one, isolated reproduction up to 60 seconds inside the work allowance. Preserve cumulative accounting across rollover; spending/context telemetry remains unknown where unavailable.
- The new allocation is already authorized. Start a new attempt; do not revive the expired scientific deadline, reset historical usage or request the superseded allocation again. Existing consent for native OpenAI Codex processing of relevant private manuscript/notes excerpts persists.

## Implementation readiness

- Retained request `m5-linear-soi-mechanisms-20261111T063725Z-cf4d5b09`, run `20261111T063907_2732fff6`: **blocked / Reviewer, turn 21**. The handoff-first repair and new workspace/budget implementation are preserved. The harness uses the actual example root, recursive protected-evidence inventory and explicit `start PROJECT --preserve-existing` initialization; existing or orphaned runtime state still prevents a fresh start.
- Latest reported checks: **116 focused tests, one skip; 259 discovery tests, eight skips**, successful with live gates disabled. Final separate review confirmed the initialization issue resolved and found no additional actionable code defects. These checks do not demonstrate successful scientific continuation or acceptance.
- Final review: `coding_pipeline/logs/20261111T063907_2732fff6/milestones/003/integration-2/attempts/000021/reviewer.md`.
- Existing MCP dependency: `coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies/`; fallback retained installation: `coding_pipeline/logs/20261111T002338_830acaa4/runtime/tmp/milestone-003-deps/`. Do not install replacements unnecessarily.
- The human instructed **not to use coding_pipeline for the completed workspace/budget/evidence edits**. Do not reopen that amendment through it. General development policy remains in PROJECT.md; the next task above is the outstanding scientific demonstration.

## Preserved evidence and references

- The failed investigation was moved into `research_example/starting_evidence/failed_m5_20261111/`. All 141 original archived files, the three supplied originals and failed receipt matched their recorded hashes after relocation. [Archive provenance](research_example/starting_evidence/failed_m5_20261111/ARCHIVE_MANIFEST.json) records exact paths and hashes.
- Its actual failure was `No new handoff draft; previous checkpoint retained`. Scientific continuation, independent verification and isolated reproduction did not complete. Historical usage is 430.693 demonstration seconds / 421.244 product seconds; retain it separately. Preserve original receipts, grants and failed outcomes unchanged. Prompt and unit-test repairs do not prove the live failure resolved.
- Current [development amendment](development/requests/m5-workspace-and-budget.md); operational amendment and migration checks in `coding_pipeline/logs/manager/m5-workspace-and-budget-20261112/`. Detailed earlier recovery history remains in Git and the original request's immutable reports/receipts.
- All work remains local. Preserve component checkouts and human edits. No COMPLETE/COMPLETE.ack has been created; M5 is unfinished.
