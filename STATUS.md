# Development status — research_pipeline

Updated 2026-11-13, 12:40 UTC. **V0-L1–L4 are accepted and integrated. L5 remains reviewed but unmerged and unaccepted. Final-005 failed production finalization; a targeted retry is prepared. L6 and M5 remain outstanding.**

## Active objective and recovery

- Request **`v0-l5-continuity-20261113T063510Z-a187c3d5`**, run **`20261113T063709_7f21ba4a`**: owned resume, COMPLETE reopening, pause/crash recovery and scientific continuity.
- Actual state: **failed / final, turn 36**, `final_test_path=tests/final-005.txt`, `integration_attempt=2`; reason **Integration repair budget exhausted**. Tool session **42179 exited 5**; `resume-003.log` preserves output. No implementation/native research worker remains. The outer manager controller owns its lifecycle and stays running.
- Latest reviewed source: branch **`cwi/20261113T063709_7f21ba4a` at `9ac334c3d2fd536f2e56662dd59bcaad5dd763f6`**; worktree `coding_pipeline/logs/20261113T063709_7f21ba4a/worktree/`. Main remains accepted L4/schema 7; reviewed L5 uses schema 10 without migration. Preserve the clean feature branch and prior source repair `56adcb52d6a68ba20a52602131c7333187dcf662`; no reset, stash, manual merge or duplicate request.
- Frozen request directory: **`coding_pipeline/logs/manager/v0-l5-continuity-20261113T063510Z-a187c3d5/`** (`request.md`, `config.toml`, `receipt.json`, `submission.json`). Submitted hashes unchanged. Standard mode, `auto_merge=true`; Architect `gpt-6.1-sol/xhigh`, Writer/Reviewer `gpt-6.1-sol/high`; existing `writer_network` preauthorization retained.
- Host reconciliation **12:38 UTC**: both L5/M5 locks unowned, no implementation/native worker, **all 125 recorded research cgroups empty**, target/feature/components clean. Receipt **`restart-003-ownership.json`**. Components unchanged; no repair/restart required.

**Next action:** checkpoint this decision, then use supported **`flow resume 20261113T063709_7f21ba4a --retry --input "$(cat .../retry-003-input.md)"`** for the newest completed final-005 failure. `retry-003-input.md` freezes the targeted investigation: trace scientific publication/edit attribution before terminal finalization, reproduce without paid inference, make the smallest justified correction, preserve real human edits, then independent review and fresh final/combined verification. The diagnostic is evidence, not an established root cause. This is continuation of the existing L5 objective, not a new feature. Do not waive the gate or resend already corrected final-002/final-004 failures.

Before any later executor launch, discover/status/report the same run and reconcile actual ownership. An interrupted manager or tool timeout does not establish that its pipeline stopped. Never run two executors. Avoid advancing main during combined verification unless retirement requires checkpointing.

Trusted execution uses `/home/francesco/miniconda3/bin/python`, inherited authorized host bus/native file authentication, and:

```sh
export PYTHONPATH="src:$manager_root/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies"
export RESEARCH_PIPELINE_V0_L5_NATIVE=1
export RESEARCH_PIPELINE_V0_L5_OUTPUT_DIR="$manager_root/coding_pipeline/logs/manager/v0-l5-continuity-20261113T063510Z-a187c3d5/native-host"
```

Both L5 native and process gates must execute in fresh final and combined stages with distinct output reservations. Keep historical M1–M5 live and accepted L1–L4 native gates disabled unless changed behavior warrants repetition. Restricted Writer bus failures authorize no workaround. Trust pipeline reports; do not independently repeat completed product testing/review.

## Completed verification and retained evidence

- **Final-005:** **416 tests, one failure, eight skipped; 1559.063 seconds**. `native-host-2xom5geo/receipt.json` records Phase A CLI exit 1 after four opposition exchanges: **`Scientific reassessment required: Incorporate current human edit before review: work/NUMERICAL_CHECK.md`**. No Phase B operator edits had occurred. State `reassessment_required`, scientific preliminary, cleanup confirmed, finalization false. All **27/27 cleanup reconciliations confirmed**. Preserve its project and partial science. The independent process gate **passed**, `native-host-1xidnfy2/receipt.json`. Summary **`restart-002-final005-outcome.json`** and saved pipeline status/report in the request directory.
- **Accounting-gate repair `9ac334c`:** independent review approved, no actionable findings. It preserves historical counters and uncertainty, requires increased resumed observed usage, and labels incomplete totals as lower bounds; production behavior is unchanged. Writer reported 49 focused tests (one skipped) and 416 discovery tests (ten skipped), passing. Restricted Writer native attempts failed bus preflight and are not acceptance. Reports `milestones/005/integration-2/{writer,review,test-evidence}.md`; receipt `restart-002-reviewed-accounting-repair.json`.
- **Final-004:** **415 tests, one failure, eight skipped; 1594.537 seconds**. `native-host-iawjnnsh/receipt.json` records acknowledged COMPLETE in both native phases, unchanged-completion handling and reopening for corrective feedback/human note edits, but failed the gate's unsupported requirement that usage totals be complete. Observed cumulative counters remain retained and honestly incomplete. Process gate **passed**, `native-host-j7s2jtgm/receipt.json`. Summary `restart-002-final004-outcome.json`. This failure received reviewed repair above; do not duplicate it.
- Earlier **final-002** (411 tests, failure/error) hit Phase B handoff-link rejection and a recovery `KeyError: continuation`; reviewed repair **`56adcb5`** addressed those. Receipt summary `restart-001-final002-outcome.json`; retained projects `native-host/` and `native-host-0kt_nec6/`. **Final-003 was interrupted for prior manager retirement**, not a completed failure; `native-host-ldqvi0kt/receipt.json` records confirmed 16-group cleanup. Prior shutdown receipts `retirement-002-{interrupt,ownership}.json` retain exact identities/recovery. No receipt is relabelled acceptance.

Historical source/report anchors remain in the same run; internal milestone 5 is unrelated to scientific M5. Existing temporary-directory/asyncio diagnostics are disclosed in pipeline reports. Operational fixture expiry/cancellation means failed/interrupted engineering validation, never scientific COMPLETE/STOP.

## Accepted baseline and next increments

L4 request `v0-l4-scientific-decisions-20261113T025828Z-9c0cb8e8`, run `20261113T025921_734d7f95`; feature **`2b9c61d08fcad1ea005afeaf3fc219da91e22e06`**, integration **`3a23c695561f5c92ecd9c71c89da6d4c02114b4f`**. Final-005/pre-merge-006 each passed 308 tests, seven disabled gates. Both public native investigations reached acknowledged COMPLETE with confirmed cleanup and protected inputs unchanged. Exact acceptance/receipts: that request's `acceptance.json`, `native-host-2i4gtxur/receipt.json`, `native-host-a1yw2sfs/receipt.json`. No injected science/agreement/quota/clock/rollover. Earlier accepted refs: L1 `542ac0dbfa7a9fa13b99773f19e876054f035e54`, L2 `f9119e31e816e7f83bb475ce01f58a5873f3b6fa`, L3 `c544bf1eefb9dca9da0b96963aff6e7b351c829d`. Historical M1–M4 paid evidence need not be repeated merely to reconstruct history.

After L5 acceptance/integration, resolve confirmed **C1–C3** in human-requested [KNOWN_CONFLICTS.md](KNOWN_CONFLICTS.md): portable ordinary scientific links, concise terminal handoffs, and authoritative-input navigation decoupled from declared scientific dependencies. One bounded draft **`next-portability-request-draft.md`** is unsubmitted. C4 per-computation tool qualification and C5 broad delegation blocking remain confirmed policies with unmeasured practical impact; no speculative redesign is commissioned. Audit receipts remain in the request directory. Then deliver **L6 integrated public lifecycle validation and M5 harness reconciliation**; `next-l6-request-draft.md` remains unsubmitted.

The human [lifecycle amendment](2026-11-12-v0-context-lifecycle-design.md) governs: observed **55%** rollover for every role, centralized weekly STOP at **15% remaining or less**, secondary warnings at multiples of **2700 seconds** without automatic replacement, agreement for COMPLETE, primary authority after challenge for scientific STOP. No fixed scientific investigation/session/demo allowance or legacy migration. Preserve original job identities/deadlines, cumulative usage, isolation, human edits and truthful cleanup. Defaults: two agents sharing 2048 MiB, zero swap, 128 tasks, one concurrent job.

## M5, components and publication

Preserve inactive M5 branch **`cwi/20261111T063907_2732fff6` at `1b70aea25f6c5f8496acdea12e9a27c6f3d4ecbd`**, worktree `coding_pipeline/logs/20261111T063907_2732fff6/worktree/`; its run remains blocked / Reviewer, turn 21, lock unowned. Do not resume/reset/approve/merge it merely to unblock development.

Benchmark root **`research_example/`** contains active science/status/indexes directly. Runtime may use `.research_pipeline/`, receipts `.m5-acceptance/`. All starting evidence, questions, research AGENTS.md and archived `starting_evidence/failed_m5_20261111/` remain protected. Preserve preliminary science and historical usage (430.693 demonstration / 421.244 product seconds). Workspace/evidence amendment is complete. Do not restore superseded 3600/3480/3900-second allowances. Only after L1–L6 acceptance may current-source M5 proceed; **human scientific acceptance remains mandatory**.

Components remain clean/unmerged: coding_pipeline **`manager/final-retry-20261110` at `5bc0fbb04ad4e104f252f0dbd61361f62f3085d5`**; controller **`project-manager/setup` at `80063c7a7bbcc615146385b543ea6f921873ccaf`**. Let the controller manage its lifecycle.

No root COMPLETE/STOP or acknowledgement exists. Non-force pushes to existing origin are authorized **only for this invocation**. Management checkpoint `d6cee1e` was pushed to origin/main; `restart-002-publication.json` records it. Later local checkpoints remain to publish. Previous retirement publications convey no future authority. Preserve PROJECT.md and all human edits; only explicit management files enter management commits.
