# V0-L3 — centralized weekly reserve and secondary staleness

Implementation is ready for independent pipeline review and trusted native verification. **L3 is not accepted by this Writer report.** The authorized host user bus is absent here; the enabled production gate failed before research admission. No real account reading, production inference or native service cleanup is claimed for this attempt. L1/L2 remain the accepted foundations, with L2 integration `f9119e31e816e7f83bb475ce01f58a5873f3b6fa`. No implementation/review/integration ref has been assigned by this implementation role; the pipeline owns those refs and subsequent final/combined results.

## Telemetry contract and material choices

Read PROJECT.md, engineering AGENTS.md, manager STATUS.md, the complete human lifecycle amendment, the supplied milestone plan and baseline. The artifact reader refused inspection; the same supplied plan/decisions/baseline were read from the local run artifact directory. Baseline evidence was 184 tests, six skipped; it was not new L3 evidence. Human-owned requirements and STATUS.md are unchanged.

Inspected `/home/francesco/Desktop/gits/codex_controller/codex_tui/policy.py` (`QuotaBook`, `WEEK_MINUTES`) and `controller.py` (`_poll`, `_read_quota`, `_admit`, `account/rateLimits/updated`). The controller uses **10080 minutes**, independent of the `primary`/`secondary` window label, minimum weekly remaining across quota IDs, full-read replacement, non-null sparse merging, a **30-second default poll**, reads before admission and immediate refusal on unavailable required quota. No controller imports, component changes or separate controller processes were introduced.

Installed standalone backend: **codex-cli 0.167.2**. Protocol discovery:

```sh
codex --version
codex app-server generate-json-schema --out ../runtime/tmp/l3-protocol
```

The generated stable schema includes `account/rateLimits/read`, `account/rateLimits/updated` and `turn/steer`. Relevant generated files are `v2/NullableGetAccountRateLimitsParams.json`, `GetAccountRateLimitsResponse.json`, `AccountRateLimitsUpdatedNotification.json` and `TurnSteerParams.json`. A read accepts `{}`; no reserve-fallback capability or account mutation is requested. The full response has `rateLimits` and optional `rateLimitsByLimitId`; each snapshot has nullable `limitId`, `primary` and `secondary`. A window supplies `usedPercent` (native int32), nullable `windowDurationMins` and Unix `resetsAt`. Notifications explicitly describe sparse rolling updates. Steering uses `threadId`, `expectedTurnId` and text `input`; active-turn mismatch is a normal delivery race.

Research-owned `quota.py` adapts that policy, retaining bucket IDs, window position/duration, raw values, provenance and observation times. It compares unrounded finite values at used >=85 / remaining <=15, and takes the most restrictive weekly bucket. An observed cutoff wins even if another bucket is invalid. Full-read admission conservatively requires valid weekly telemetry in every returned bucket. Sparse omissions/nulls preserve known weekly data and never renew its age; new metadata-only or short-window notices do not invalidate established weekly observations. A changed window duration replaces its positional predecessor rather than mixing two identities. Full reads replace snapshots, but never remove the first cutoff latch. Explicit native denial of ordinary account usage also refuses admission; percentages/null metadata cannot override a known denial.

The research runtime adds a **60-second per-weekly-observation freshness bound** (one missed 30-second poll). Reported reset expiry also requires a supported refresh; elapsed time never fabricates allowance. Reads use the existing 15-second operational RPC bound; failures refuse further work rather than retrying scientific inference. This is an operational telemetry bound, not a research lifetime. Native payload observations and labelled test injections remain distinguishable, including the immutable first cutoff.

## Runtime and cleanup

Schema **6** rejects older or incomplete operational state without migration. `start()` prepares the primary owned app-server, performs actual account preflight **before `thread/start`**, then lets the primary runner consume that existing attachment. Secondary context, task/assignment, computation reservation, command-release and inference-turn admissions use the same cached investigation guard. Only the current logical primary transport supplies policy reads/notifications; secondary and retired-primary account events are ignored. A separate polling task keeps slow quota RPCs out of inventory/pause monitoring. Primary replacement preserves quota/latch state, blocks admissions while its transport is absent, and requires fresh successor preflight. Secondary turns/attachments wait outside the lifecycle lock during that expected gap, preserving unrelated contexts/jobs; ordinary sparse successor notifications cannot mistake transport replacement for missing-quota failure. A real primary control-path failure wakes waiters and schedules operational cleanup rather than leaving them indefinitely unmonitored. No context receives a new allowance.

At cutoff the RPC callback synchronously blocks admissions, records quota origin and signals runners, then schedules one common cleanup task. It does not await lifecycle RPCs in the reader. Existing early handoffs, immutable documents, saved drafts and job records provide best-effort preservation. **No post-cutoff saving inference or scientific opposition turn is started.** Active turns receive bounded operational interruption; failure proceeds to owned-service cleanup. Job cancellation runs concurrently with context cleanup and waits for settling admissions under the existing job lock, so optional saving cannot postpone computation interruption. The command-release gate prevents a reserved service from starting its command after cutoff.

Confirmed process termination is recorded before optional snapshot/publication writes. Cleanup, quota origin and finalization success are separate. Persistence/snapshot/interruption failures cannot disable remaining cleanup; uncertain contexts/jobs retain their attachment/reservation and partial output. Publication retains the accepted confirmed-quiescence and human-edit rules. Failure to snapshot/publish/save status prevents an unqualified success acknowledgement without relabelling terminated processes as alive.

`STOP` identifies quota origin, first observation, known artifacts, unfinished jobs, actual cleanup and limitations. A runtime-authored Markdown handoff is written under `handoffs/` after confirmed quiescence, or under private runtime state while cleanup is unconfirmed. Scientific status/index publication waits for confirmed cleanup. Existing scientific status is retained with an operational link when safe; human status edits remain intact and are reported as preserved. `STOP_ACK` matches STOP bytes only after confirmed cleanup and successful finalization. A failed acknowledgement write is saved as failure when state storage remains writable. A successful acknowledged STOP is not replaced by later pause/cleanup requests. Missing quota telemetry yields `quota_unavailable`, without a quota-origin STOP marker. CLI return/output distinguishes these states and awaits centralized shutdown before gathering runners. `resume` is still unsupported until L5; terminal markers reject fresh admission even with `--preserve-existing`.

## Secondary clocks and delivery

`Config.secondary_staleness_seconds` defaults to **2700**, with a positive integer human CLI option `--secondary-staleness-seconds`. The effective value is persisted and no model tool can relax it. Each attached secondary researcher/verifier/opponent has an independent explicit-monotonic clock. The first reliable sample establishes raw length without postponing attachment. Only a later raw measured `last.totalTokens` change, increasing or decreasing, resets it. Unchanged reports, cumulative spending, occupancy flooring, window/turn changes and warnings do not reset it. Missing measurements suppress staleness emission and remain a separate operational condition; they do not manufacture activity. Fresh successors get fresh clocks. The primary has no inactivity clock.

Each newly crossed interval multiple emits once with agent/context, scheduled interval, actual elapsed staleness and provenance. Delayed observation can record several crossed intervals with the same actual emission time. Pending observations live in small ordinary runtime records keyed by secondary context, with history retained. Primary `control(check/tasks)`, continuation turns and successor intake expose them independently of document pagination. Active primary turns can receive noninterrupting steering outside the reader; completion/replacement races leave notices pending. RPC delivery is not scientific acknowledgement. Activity/context replacement supersedes old pending notices. Warning functions do not cancel, replace, restart or stop work, change deadlines or score scientific progress.

## Verification and receipts

All commands use the existing dependencies, without installation:

```sh
PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies \
RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 \
RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 \
RESEARCH_PIPELINE_M5_LIVE=0 RESEARCH_PIPELINE_V0_L1_NATIVE=0 \
RESEARCH_PIPELINE_V0_L2_NATIVE=0 RESEARCH_PIPELINE_V0_L3_NATIVE=0 \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
```

Logs are under `coding_pipeline/logs/20261113T002546_9500464b/runtime/tmp/` (sibling of this worktree). Initial failing development runs `l3-routine-1.txt`, `l3-routine-2.txt` and `l3-focused-1.txt`/`-2.txt` remain there. Repairs added explicit account-read responses to accepted successor doubles, corrected cleanup/persistence separation, synchronized actual descendant-termination observation and updated old assertions that conflated saved artifacts with successful process cleanup. Earlier passing routine snapshots `l3-routine-3.txt` and `l3-routine-4.txt` each ran **214 tests, seven skipped**. Focused `l3-focused-3.txt` ran **38 tests, all passed**. An intermediate `l3-writer-final.txt` ran 218 tests with one fixture failure: the test assumed state JSON rejected nonfinite values. The corrected fixture explicitly injects a serialization failure and verifies cleanup independently. `l3-writer-final-2.txt` passed 220 tests, seven skipped; `l3-writer-final-3.txt` passed 221 tests, seven skipped, after adding transport-gap waiting. Final Writer verification is recorded below.

Coverage includes >/=/<15%, fractional boundaries, either weekly position, short windows, multiple quota IDs and incomplete buckets; missing/invalid/nonfinite data; sparse omission ages, explicit account denial, reset refresh, immutable cutoff despite positive recovery; absent-preflight refusal; primary-only policy authority; transport replacement; queued assignment and reserved-job command-release races; active checkpoint interruption and closure; real local process/descendant termination retaining partial output even when runtime writes fail; uncertain cleanup retaining ownership; snapshot/STOP/ACK failures and protected human status; independent clocks, increasing/decreasing raw lengths, repeated exact interval multiples and missing samples; warning delivery races and successor intake; jobs/deadlines unaffected by warnings; full foreground CLI waiting and failure exit status. Existing accepted L1/L2 logical continuity, job/resource/isolation, immutable reads and human-edit publication checks remain in routine discovery.

**Enabled native attempt (failed prerequisite, preserved):**

```sh
PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T063907_2732fff6/runtime/tmp/test-dependencies \
RESEARCH_PIPELINE_V0_L3_NATIVE=1 \
RESEARCH_PIPELINE_V0_L3_OUTPUT_DIR=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261113T002546_9500464b/runtime/tmp/l3-native-writer-001 \
/home/francesco/miniconda3/bin/python -W error::ResourceWarning -m unittest tests.test_v0_l3_native.NativeL3Tests -v
```

Exit 1; log `runtime/tmp/l3-native-writer-001.txt`, private receipt `runtime/tmp/l3-native-writer-001/receipt.json`. Actual error: `systemd user bus unavailable: XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS must already be set in the authorized host environment`. Both inherited variables were absent. Receipt: `outcome=failed`, no scenarios/commands. No production service or inference was launched, so no native cleanup or real remaining percentage was observed. No bus/auth/isolation workaround was attempted. Local owned process checks are engineering evidence, explicitly not production cgroup evidence.

`tests/test_v0_l3_native.py` provides opt-in discovery with `RESEARCH_PIPELINE_V0_L3_NATIVE=1` and inherited `RESEARCH_PIPELINE_V0_L3_OUTPUT_DIR`. It reserves unique private receipts before prerequisites; receipt regression tests preserve two independent failed invocations. Researcher/opponent scenarios run sequentially within unchanged two-agent/one-job defaults. Each requires an actual sufficient native preflight before injections, native public analytical work, one controlled public quadrature job and descendant, a real primary rollover with original job identity/deadline, labelled warning intake across that rollover, labelled quota cutoff and actual owned-service cleanup. Native readings, native lengths, injected occupancy/clock/quota and saved science are distinct receipt fields. It never manufactures agreement/scientific completion or admits a run with invented quota. Synchronization bounds fail engineering tests; they are not research lifetimes.

Trusted **final and combined stages must inherit the enabled L3 gate**, existing authorized bus/native file credentials, dependencies, Bubblewrap and cgroup v2. Allocate a fresh private output destination per invocation and preserve all failures. Keep M1–M5 and accepted L1/L2 native gates disabled. This Writer did not manage sessions, refs, permissions, publication, or the retained M5 candidate. Independent review and required trusted final/combined receipts are pending pipeline work; this report cannot substitute for them.

## Next dependency

L4 implements scientific opposition and COMPLETE/scientific STOP authority, using this separate quota-origin cleanup path. L5 owns explicit stopped-state resumption/reopening/recovery; L6 owns integrated lifecycle validation and M5 harness reconciliation. No full lifecycle or M5 acceptance is claimed. Protected scientific inputs, archived preliminary science, historical receipts and retained M5 branch/worktree remain unchanged.

## Final Writer result

Final current-source routine discovery, using the disabled-gate command above: **221 tests in 9.912 seconds, OK (seven opt-in gates skipped)**; log `runtime/tmp/l3-writer-final-4.txt`. This includes the new primary transport-gap/early-notification regression and retained L1/L2 engineering checks. `git diff --check` passed. A read-only diff confirmed no changes to PROJECT.md, engineering AGENTS.md, STATUS.md or the human lifecycle amendment. The native prerequisite failure receipt remains unchanged. No independent review or trusted native final/combined pass is asserted; those gates remain necessary for milestone acceptance.

## Review repair — attempt 1

Addressed all three supplied findings without changing the protected requirements or manager STATUS.md:

- **P1, native dispatch admission:** `attach()` now prepares reconciled job metadata and the prompt before rechecking quota immediately before `thread/start`. The scheduled native-turn coroutine checks quota again before invoking `client.turn()`, so a ready quota notification can block it before `turn/start`. The driver writes each RPC before its first transport I/O suspension. Synchronized regressions latch cutoff while job inspection is suspended and queue a cutoff callback ahead of the scheduled inference coroutine; neither native operation is admitted, and owned cleanup completes.
- **P2, edited indexes after failed publication:** the coordinator retains the last known generated index hashes rather than accepting current disk contents as the baseline during STOP. `refresh_indexes()` returns hashes of the indexes it actually wrote; ordinary publication and quota finalization update only those known versions. Index preservation therefore remains independent of draft publication success, without adopting unrelated edits or misclassifying normal regeneration. A regression combines a human-edited `work/FOLDER_CONTENT.md`, an invalid primary draft destination and quota cutoff. The exact human text survives in the existing preserved-version format with a navigation link; cleanup is confirmed and saving failure still prevents STOP_ACK.
- **P2, late optional warning replies:** the client tracks the exact IDs of optional `turn/steer` requests, including canceled/timed-out requests until their reply arrives or the transport closes. A late success or error for one such expired request is discarded once without failing the RPC reader or claiming delivery. The warning remains pending. Unrelated IDs, duplicate replies and malformed responses retain ordinary protocol failure handling. A real local JSON-RPC fixture releases late success/error replies only after the warning timeout; subsequent correlated requests work, the primary turn and secondary stay active, the job/deadline remain unchanged, and no shutdown is scheduled. A separate negative check verifies that an unrelated response ID still fails the reader. These are local engineering fixtures, not native production/cgroup evidence.

The four new consequential regressions reproduced the original findings before the fixes: `runtime/tmp/l3-review-1-reproduced.txt` records three failures and two errors (the delayed-reply test has two subcases). An intermediate focused run exposed a test assertion that omitted the existing preserved-version Markdown provenance prefix; that assertion was corrected to check the complete saved format, including the exact human text. The intermediate log is retained as `runtime/tmp/l3-review-1-focused.txt`.

Repair verification used the existing dependency PYTHONPATH and `/home/francesco/miniconda3/bin/python -W error::ResourceWarning`:

```sh
# Focused protocol, lifecycle/publication and repair checks:
-m unittest tests.test_v0_l3 tests.test_app_server tests.test_pending_documents tests.test_review_repairs -v
# Routine discovery, with all M1–M5 and L1/L2/L3 native gates disabled:
-m unittest discover -s tests -v
```

Focused verification: **68 tests in 4.446 seconds, OK**, log `runtime/tmp/l3-review-1-focused-2.txt`. Routine verification: **226 tests in 10.176 seconds, OK (seven opt-in gates skipped)**, log `runtime/tmp/l3-review-1-routine.txt`. Paths are under the same run directory identified above; the routine command uses exactly the disabled-gate environment documented earlier. Read-only diff checks passed and confirmed PROJECT.md, engineering AGENTS.md, STATUS.md and the human amendment remain unchanged. README and the test directory index describe the repaired behavior.

The inherited `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` remain absent. No native gate was repeated against that unchanged prerequisite blocker; the original failed private receipt remains preserved. No new account quota reading, native science, production cleanup, successful independent re-review or trusted final/combined result is claimed. The supplied review has been repaired; pipeline re-review and the enabled native/trusted final/combined gates remain necessary for L3 acceptance.

## Review repair — attempt 2

Fixed the remaining P1 scheduling regression. The scheduled `dispatch_turn()` coroutine now calls `wait_quota_ready()` instead of directly rejecting an expected primary transport gap. This existing helper waits for replacement when needed and performs the cached quota check immediately before returning to native dispatch. A latched quota STOP still rejects inference; normal primary rollover leaves unrelated secondary work active.

The new synchronized regression runs the actual secondary `run_task()` loop with explicit backend/service/job doubles. It queues primary closure ahead of the scheduled secondary dispatch, after the outer admission wait has already succeeded. It then holds successor quota preflight open and verifies that the secondary has not dispatched, failed, closed or canceled its job. After successful successor preflight, intake completes and the same secondary context continues ordinary work; the job record, ownership, launch count and original deadline remain unchanged, with zero cancellation calls before explicit fixture cleanup. No global clock advancement or scientific lifetime was added.

Before the fix, this test reproduced the reported `JobError: Primary quota transport replacement in progress; research admission refused`, secondary failure and cleared attachment. That failed run is preserved as `runtime/tmp/l3-review-2-reproduced.txt` under the existing run directory.

Verification used the existing dependency PYTHONPATH and trusted Python command documented above:

- `-W error::ResourceWarning -m unittest tests.test_v0_l3 tests.test_v0_l2 -v`: **59 tests in 4.867 seconds, OK**, log `runtime/tmp/l3-review-2-focused.txt`.
- The documented full routine command, with all M1–M5 and L1/L2/L3 native gates disabled: **227 tests in 10.222 seconds, OK (seven gates skipped)**, log `runtime/tmp/l3-review-2-routine.txt`. This retains the previous cutoff-at-dispatch, index-preservation and late-warning-response regressions.
- Read-only diff checks passed; PROJECT.md, engineering AGENTS.md, STATUS.md and the human lifecycle amendment remain unchanged.

The inherited `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` were rechecked and remain absent. The original failed native receipt is unchanged; no production demonstration was repeated against the same prerequisite blocker. No new native quota reading, native cleanup or trusted final/combined pass is claimed. Re-review and successful enabled native/trusted final/combined checks remain required for L3 acceptance.
