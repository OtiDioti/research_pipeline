# coding_pipeline change audit

## 2026-11-04 — REQ-D05-002 backend audit

Run `d4513360-8b98-4b8d-9bdc-91835d40a323` accepted and integrated `0a6a01e2552b886232e2880d80123479b70a79e6`. Backend remained clean at `b6a2e05283f92f2bb42402d49e4a274225b43f6a`; no backend maintenance attempted. Attempted/adopted/reverted remains 2/2/0.

This file records necessary modifications to the separately cloned development backend. It is not the research product's changelog. Follow [the maintenance policy](development/BACKEND_MAINTENANCE.md).

**Initial record:** no backend source modification was made in preparing this documentation update. This is not a statement about changes that may already exist in your local clone. Inspect and preserve those before adopting this template.

## Changes

| ID | Reason / affected run | Backend base → resulting revision | Paths / patch reference | Regression and wider checks | Disposition |
| --- | --- | --- | --- | --- | --- |
| CP-001 | Orphan child response retained permissive mode; original recovery blocked | 1f68060b → c74df0b09b4883776b1889b859b2df065f0b2fe4 | README.md, cwi/codex_cli.py, tests/test_codex_cli.py; [patch](development/backend_patches/CP-001-private-final-response.patch) | Red/green regression, adapter47, full1033/1012pass21skip, pinned real-binary offline write probe; failed environment runs preserved | Adopted exact FF after old run terminal/noresume |

Add one detailed entry per incident using [BACKEND_CHANGE.md](development/templates/BACKEND_CHANGE.md). Include failed and reverted attempts and any pre-existing edits that the repair depended on. Do not replace this audit with a summary that loses earlier changes.

## Recording during an active or base-bound run

Write the full pending entry immediately under `local/backend-maintenance/`, with exact diff/backup references. Keep the original checkout unchanged. Transfer the entry here at the first safe administrative checkpoint; never falsify its event time to match the later commit time.

A backend Git commit lives in a different repository and is not preserved by committing this Markdown file. Preserve a reviewable patch or protected backend backup and record where it can be recovered. Do not push backend changes without separate authority.

## Local inspection — 2026-10-30

Supported clone was clean at `1f68060b5a5a9964c91811a53d3a515e0b01a073`; no pre-existing dirty edits, pending repair audit or live CWI owner found. Its upstream prompt changes relative to the reviewed `122f865` were already committed before this session; they are not coordinator repairs. Backend repair candidates attempted/adopted/reverted: **0/0/0**. Local deterministic suite and focused bootstrap follow-up passed as recorded in [ENVIRONMENT.md](development/ENVIRONMENT.md). System Git incompatibility was addressed by selecting an existing capable installation, without editing backend source.

Commissioning checkpoint: run 47d6ef06 completed and integrated using unchanged backend 1f68060. Attempted/adopted/reverted repairs remain **0/0/0**; no pending local backend log exists.

Post-mock checkpoint: run 34bcb77d completed and integrated using the same clean backend 1f68060. Attempted/adopted/reverted repairs remain **0/0/0** across both runs; no pending maintenance log or unresolved owner.

Post-storage checkpoint: run 77ab31a1-a7c2-4185-a26b-f9ed52da1593 integrated with unchanged clean backend 1f68060. Backend repair candidates attempted/adopted/reverted remain **0/0/0**; no pending local maintenance log. One CWI product repair is not a backend change.

Post-backup checkpoint: run 2d82f186-4cf2-4fb7-9f96-f0ea8db10340 accepted/integrated using unchanged clean backend 1f68060. Backend attempted/adopted/reverted repairs remain **0/0/0**; no pending maintenance log or unresolved owner.

Post-typed-record checkpoint: run d7e765f5 completed and integrated using unchanged clean backend 1f68060. Backend attempted/adopted/reverted repairs remain **0/0/0**; no pending maintenance log.

Migration attempt 9af6f133 stopped on a role/validation-context mismatch, not a diagnosed backend malfunction. No source repair attempted; backend attempted/adopted/reverted remains **0/0/0**. Recovery is an administrative request clarification with original evidence preserved.

Post-migration checkpoint: 25e5020e accepted/integrated using unchanged clean backend 1f68060. Attempted/adopted/reverted backend repairs remain **0/0/0**; no pending maintenance log. The administrative validation-ownership recovery succeeded without backend or security changes.

REQ-D02-005 timeout 46114120 is an exhausted configured deadline, not a diagnosed backend defect. Human extended future invocation/validation limits via supported flags; no backend source/config mutation. Attempted/adopted/reverted backend repairs remain **0/0/0**. Draft recovery uses supported frozen context and a new run, never hot patch/resume.

Post-attributed-record checkpoint: 8dc45005 accepted/integrated using unchanged clean backend 1f68060. Supported new-run deadlines were explicitly 2700 seconds. Attempted/adopted/reverted backend repairs remain **0/0/0**; no pending maintenance log. The resolved fixture identity collision consumed one CWI product repair only.

Post-work-product checkpoint:2b6ed304 accepted/exact-integrated a56111f3 using unchanged clean backend 1f68060. Attempted/adopted/reverted backend repairs remain **0/0/0**; no pending maintenance log. Writer-local socket/tmp limitations were resolved by authoritative host validation, with no backend/security/acceptance change and no coordinator recovery.

Post-source-capture checkpoint, 2026-10-31: 7b46536e accepted/exact-integrated d8dffdd using unchanged clean backend 1f68060. Backend attempted/adopted/reverted repairs remain **0/0/0**; no pending maintenance change. Guarded automatic approval resolved Git write capability. An observed EMFILE validation failure was diagnosed as a process descriptor prerequisite and resolved by bounded launch-only soft=4096 within the existing hard limit, with unchanged full 343/343 tests. This is an environment recovery, not a backend defect or source change; failed evidence is preserved.

## REQ-D03-002 backend audit — 2026-10-31

Runf746e33a-7475-44dc-b8bf-4613130fba79 accepted/exact-integrated 7d6dd6246e47ace09ff44a1decef14c93251f0ac, 369/369 target tests. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073; attempted/adopted/reverted backend changes0. The single CWI repair corrected new product test/example directory modes through its Writer; capture safeguards and launch environment stayed intact. The cosmetic EOF disposition changed no backend/source/configuration. Existing permission approvals were scoped to authorized CWI/Git/validation operations. No live/frozen execution or receipt was edited.

## 2026-10-31 — REQ-D03-003 checkpoint

Rundb2829bc-fca9-48d7-b2c1-b9e99348c197 accepted/exact-integrated9373860,396/396 target tests. Backend remains clean unchanged1f68060b5a5a9964c91811a53d3a515e0b01a073; no backend attempt, patch or reverted candidate. Actual controller failure was diagnosed as new product fixture provenance/file-mode setup and repaired by its Writer, not a backend defect. Frozen model/high effort,2700-second limits and process-local descriptor4096 retained. Backend candidate count0; prior evidence preserved.

## 2026-10-31 — REQ-D03-004 terminal validation-profile omission

Run32b61b7f stopped after432/432 because the frozen controller profile lacked required complete-diff evidence. Existing repeated --check and frozen --context capabilities support a bounded replacement without backend edits. Clean backend remains1f68060b5a5a9964c91811a53d3a515e0b01a073. Attempted/adopted/reverted backend repairs remain0/0/0; no failed/reverted backend change is hidden. Source/test syntax repair belonged to CWI Writer. Coordinator recovery corrects new-run validation configuration only, preserving the old run/candidate/evidence and all security/acceptance rules.

## 2026-10-31 — REQ-D03-004-R1 integration audit

Run 7ee32819-ee00-4b1b-bdba-ea26fb90cf3e accepted/exact-integrated c57a621c3e3f7806030de13b75b4fe2890b81cc7; 489/489 target tests. Backend remains clean 1f68060b5a5a9964c91811a53d3a515e0b01a073; attempted/adopted/reverted backend changes remain 0/0/0, with no pending or hidden maintenance attempt. Existing repeated --check and frozen --context resolved the predecessor's missing evidence without backend changes. Two CWI product repairs corrected planner provenance/depth, publication staging geometry and inspection error handling. Real EACCES from cross-parent publication was repaired in product layout, not by elevation, host/security mutation or backend patch. Stable environment/executable/model/high effort, 2700-second deadlines and process-local descriptor 4096 remained intact. Old failed runs and their evidence are preserved.

## 2026-10-31 — REQ-D03-005 integration audit

Run c62af399-bf8c-4b25-8ef7-ec1947fad6ae accepted/exact-integrated 8cfb035,579/579 target tests. Backend remains clean 1f68060b5a5a9964c91811a53d3a515e0b01a073; attempted/adopted/reverted changes 0/0/0. Three product-review repairs belonged to CWI Writer: stable bounded capture, independent preservation limits/control checks and post-hash final binding checks. Local test-fixture corrections and coordinator read-only diagnose-output parsing did not require backend repairs or constitute new starts/recoveries. No controller state, environment, executable, security or acceptance rule changed; all historical evidence retained.

## 2026-10-31 — REQ-D03-006 integration audit

Run63f0416b accepted/exact-integrated0a875dd,657/657 target tests. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073; attempted/adopted/reverted0/0/0 with no pending maintenance candidate. Two CWI product repairs fixed an explicit fixture mode and observed directory/leaf disappearance classification. Read-only coordinator audit assertion corrections required no source/configuration/state edits and consumed no recovery. Stable model/executable/environment/checks remain unchanged; historical evidence and failed candidates are preserved.

## 2026-11-01 — View CLI acceptance/integration audit

Runc9055f4c-f63c-4815-ab5e-670116ce1333 finally accepted/exact-integrated2643673. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073, attempted/adopted/reverted0/0/0. Two CWI product repairs addressed authored-control/descriptor/path-budget findings and a fixture mode; the independent remaining B-017 diagnostic is also product work and will use CWI. No backend patch, controller-state edit, security/configuration waiver or automatic-approval rejection. Historical failed validations and Writer-local advisory limitations remain recorded.

## 2026-11-01 — Diagnostic repair acceptance/integration audit

CWI4c1833ef-8ef9-4b07-9f33-79acb6f7e8b0 finally accepted/exact-integrated3f4564c. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073; attempted/adopted/reverted0/0/0, no pending maintenance. One CWI product test repair corrected disposable fixture permissions/recovery and unpublished-generation identity assertions. Production diagnostic changes belonged solely to its CWI Writer. A coordinator read-only diagnose-output parser mistake changed no backend/state and consumed no recovery. No automatic-approval rejection, security or frozen configuration change. Preserve failed controller and Writer advisory results; no waived test or receipt edit.

## Resource-accounting checkpoint — 2026-11-01

REQ-D04-001/6eaf6f92-ec81-4d73-b83d-9b97a30cfb02: backend attempts/adoptions/reversions0/0/0 cumulative. Separate excluded backend 1f68060b remains clean. Both repairs were ordinary CWI product/prescription work. Read-only backend inspection established final-repair receipt binds repair-delta and whole-base digests separately; adapting the coordinator audit changed no controller source/state. Failed Writer advisory evidence retained, no isolation weakening or new grant.

## 2026-11-02 — Report recovery preparation audit

Read-only reconciliation confirmed clean backend 1f68060b5a5a9964c91811a53d3a515e0b01a073 and no live development owner. The cancelled read-only review requires a fresh run with preserved draft reference; existing --context and normal acceptance support recovery. No diagnosed backend defect, modification, maintenance attempt or state edit. Cumulative attempted/adopted/reverted remains 0/0/0.

## 2026-11-02 — Publication Writer deadline audit

Run d343c0af stopped safely after Writer2700-second timeout with changes; no replay allowed. No backend defect established. Existing supported frozen --context provides fresh CWI-only salvage; source/test repairs stay delegated product work. Old index contains generated example/log output and remains untouched; reference excludes it. Backend clean1f68060b5a5a9964c91811a53d3a515e0b01a073, attempted/adopted/reverted0/0/0. No security/frozen-state alteration or approval rejection.

## 2026-11-02 — Combined Reviewer context limit diagnosis

R2 stopped before review because frozen source bodies plus the mandatory full diff made a1,497,360-byte prompt, over the existing1MiB guard. Read-only unchanged context.py composition reproduced overflow and accepted compact immutable commit/blob/hash reference at595,915 bytes, retaining all mandatory diff/validation/criteria/prescription evidence. No invocation, state persistence, code modification, guard increase or truncation. Supported --context suffices; no backend defect/repair candidate is established. Backend1f68060b unchanged, attempted/adopted/reverted0/0/0.


## 2026-11-02 — Compact report recovery completed

R3/528cf918 finally accepted and exact-integrated7a1edeb8; final/target845/845. Full milestone/final prompts596043/591401bytes fit unchanged guards using supported compact immutable Git-reference context. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073, attempted/adopted/reverted0/0/0. No hot patch, state/receipt edit, evidence truncation, environment/security change or approval rejection. Historical failures and recovery limits remain; no pending maintenance attempt.


## 2026-11-02 — Authority Reviewer provider capacity, no backend change

Run5f304a70 passed876/876 after two CWI product repairs, then selected-model capacity failure interrupted read-only review before verdict. Existing diagnosis requires terminal resolution and new_run_after_manual_salvage; supported compact context/fresh workflow provides the route. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073; attempted/adopted/reverted0/0/0. No backend defect/modification, state/receipt/guard edit, model substitution, live patch or approval rejection. All old failures and counters remain.


## 2026-11-02 — Authority capacity recovery completed without backend change

R1/f14139d7 finally accepted/exact-integrated27638a93,final/target883/883. Backend stays clean1f68060b5a5a9964c91811a53d3a515e0b01a073;attempted/adopted/reverted0/0/0,no pending maintenance. One new product-review repair reserved detached metadata before construction across authority paths and added7tests; it belonged entirely to CWI Writer. Old provider-capacity failure,advisory mode-assumption failure,unknown usage and all counters remain preserved. No hot patch,guard/state/receipt edit,model substitution or approval rejection. Supported frozen context and fresh complete review/validation resolved recovery.


## 2026-11-02 — Lifecycle contract blockers,backend unchanged

Rune83c7165 stopped after preimplementation blockers:no source candidate/acceptance. Read-only inspection found Architectaddition-onlyresponse contrary to existingcomplete-prescription policy,and a full replacement's Unicodeactor contract incompatible with established ASCIIprovenance. Writerblocked correctly and removedincompleteown draft;actual parent/childclean. Frozen completecorrectedcontract/newboundedrequest resolves inputswithoutbackendpatch/state/guard/permission/model/limit changes. Backend remains clean1f68060b5a5a9964c91811a53d3a515e0b01a073;attempted/adopted/reverted0/0/0,no pendingmaintenance. All blockedroleusage and2internalrepairs retained.


## CP-001 — Prepare private final response before child launch — 2026-11-02

Actual defect: after coordinator/controller loss in d838a2c8, the orphan Codex completed its591-byte final-response.txt under inherited umask002, yielding0664. Unchanged StateStore rejected recovery with “durable file grants group or other access.” The adapter had privately created stdout/stderr but chmodded its child-created final response only after process completion. Controller survival itself is not repaired or guaranteed.

All live owners were resolved before maintenance. Existing Writer naturally completed; source and originals were preserved. The human explicitly approved tightening only that exact response0664→0600. A held no-follow descriptor verified device64513/inode7109551/uidgid1000/591bytes/hash65c4770db75aa1399c8e38485630c7530a088a57b6ffbd9c4c995dac53e6180a before/after. The original1f68060 controller then safely stopped d838a2c8/noresume without replay/adoption. That specific human exception does not authorize future evidence edits; historical logging gaps remain. No run was silently resumed under patched code.

**Attempt1, adopted.** Isolated backend worktree local/backend-repairs/CP-001, branchmaintenance/CP-001-private-final-response. Minimal change exclusively creates final-response0600 immediately before Popen and treats an empty placeholder as no response. Existing post-exit normalization, privacy guard, success/acceptance checks, model settings, schemas and resource/security boundaries remain. README documents the conservative availability tradeoff: existing recovery treats an empty prepared artifact as requiring explicit adoption, so automatic interrupted-call retry is unavailable throughout the pre-response lifetime. It grants no success or unsafe replay. Global/child umask was not changed for production.

Red/green: the corrected real supervisor-loss regression failed on0664/0644 output under umask002/022; the storage-preparation failure regression also failed before implementation. Initial regression setup missed creating its disposable runtime directory; that test-only error was corrected before production changes and preserved in the local audit. Both meaningful regressions then passed. Existing adapter baseline45/5.049s and repaired47/5.239s passed with9existing live skips. The regression removes supervisor cleanup after the child writes; it does not literally delay that fake child's write until after parent death. This minor limitation is explicit.

Two failed full-suite TEST ENVIRONMENT launches are retained, never counted green:1033tests/36.165s with systemGit2.34.1 failed67assertions/664errors/21skips;1033/543.127s withGit2.40.1 but production Git actor variables failed exactly3fixture-identity cases. All3passed in0.205s when those four actor variables were omitted. No code changed between these runs. Final full suite usedGit2.40.1/fixture-owned identities/liveoptinsdisabled/FD4096: **1033run,1012passed,21skipped,zero failures/errors,544.062s**; ended2026-11-02T18:31:23.525186Z, logSHA2564264a92cbdff1edbf72678eb1bc690a9ec4576e72822f49cd6e3f7388c1987e1. Skips are15existing opt-in live cases and6optional pytest fixtures. No live-provider test is claimed. The backend test environment correction does not alter the frozen CWI launch map.

Independent backend-only gpt-6-astra/high reviewer found no Critical issue and closed both substantive conditions after documentation and real-binary evidence. The exact pinned Codex0.166.0/b8a11fed was exercised directly against a disposable loopback Responses fixture with empty credentialHOME: absent response0664; precreated0600 retained inode2387215/mode0600; exact expected text and exit0 in both cases. No external model/service or credential was used. The fixture's reported tokens are synthetic. Native reviewer usage is unmeasured, separate from CWI accounting.

Backend base1f68060b5a5a9964c91811a53d3a515e0b01a073 → **c74df0b09b4883776b1889b859b2df065f0b2fe4**, tree959b57dc98b5dedc846539843614887f9bc9f277. Committed18:32:06.472064Z and adopted by exact FF of the separate clean backendmain at18:32:25.000788Z after no affected live owners and old-run terminal/noresume proof. Only README.md,cwi/codex_cli.py,tests/test_codex_cli.py changed:100insertions/1deletion. Full executable/test verification preceded the final README-only recovery note. [Sanitized preserved patch](development/backend_patches/CP-001-private-final-response.patch),6332bytes,SHA256**09983a00373d16f0c381cdf3c0dbd7d2fbfc61c22d64091fe6b0b9d1cccecd86**. Local second exact patch, plan, immediate audit, red/green, both failed environment logs, final full result, pinned-binary proof, independent review and adoption evidence are underlocal/backend-maintenance/CP-001/. No push/publication, force/reset, destructive cleanup, guard weakening or automatic-approval rejection.

Cumulative backend attempted/adopted/reverted **1/1/0**, one code candidate, no unsuccessful code candidate hidden by the two failed test-environment launches. New product runs use the recorded new backend; all old frozen runs remain historical and may not resume under it. Return to normal CWI-only product salvage in REQ-D04-004-R2 after its clean committed baseline.

The tracked patch uses zero context (`git apply --unidiff-zero` when applying) so blank unified-diff context markers do not violate the parent complete-diff whitespace guard. The initial staged full-context evidence failed that guard on two context-only blank lines; no commit or acceptance followed. Exact full-context7660-byte patchSHA2564bdfd3fc4427b82cca88388a31ac6b00823c705fed37f2c0bf067d47bad74031 remains locally preserved. Backend source/commit and all tests are unchanged.

## Prepared-control acceptance completed on the adopted backend — 2026-11-02

Existing run 153bf4bf completed naturally on unchanged clean backend `c74df0b09b4883776b1889b859b2df065f0b2fe4`; exact source `771422b7` finally accepted/integrated, final 946/946 and integrated target passed 946/946 in 1146.754 seconds, zero skips/errors/failures/source mutation, ending 2026-11-02T20:54:40.836813Z (stdout SHA256 `0af73e8950f6ce1f59051b68cf134487e56610a1fae683b72bc47a9b3e38a243`, empty stderr). Its one product bounds repair belonged entirely to the CWI Architect/Writer and is not backend maintenance. No backend source/state/guard/log/lease modification, hot patch, evidence permission correction, model substitution or recovery replay occurred in this session. CP-001 and both failed test-environment attempts remain fully audited above; cumulative backend attempted/adopted/reverted stays 1/1/0. Controller survival is still not guaranteed. No automatic-approval rejection occurred.

## 2026-11-03 — Reporting prescription failure, backend unchanged

Run7632b4e0 ended at Writer-blocker repair limit with no candidate/change/acceptance. Read-only context.py/controller.py/architect.md inspection confirms fresh Writer gets current prescription only and existing policy already requires complete prescriptions. Addendum-only output and oversized coupled product work do not establish a new backend defect. Narrow request decomposition and standalone prescriptions address coordinator/role inputs without backend patch/state/guard/evidence edit. Backendc74df0b clean; cumulative attempted/adopted/reverted1/1/0, no pending maintenance. A failed administrative apply_patch call was rejected before any mutation (duplicate STATUS target); subsequent edits are Markdown only. No automatic approval rejection or security change.

## 2026-11-03 — Binding acceptance and administrative start-budget amendment

R1/b4dd25a5 finally accepted/exact-integrated091561b9, final/target978/978, zero CWI repairs. Backendc74df0b remains clean/unchanged; cumulative attempted/adopted/reverted1/1/0, no pending maintenance. Actual human50→100 extension is the coordinator's administrative continuous-start allowance in AUTH/autonomy/startup settings; reviewed backend CLI/config has no aggregate-start field, and its milestone/repair limits were not changed. No hot patch, state/receipt/evidence-mode edit, guard weakening, environment/model substitution or approval rejection. Coordinator read-only link/process parser corrections and prior narrative chronology correction changed no implementation/recovery counters. Old CP-001 evidence/failed test-environment attempts stay preserved.

## 2026-11-03 — Source review exhaustion, backend unchanged

Runf78fa4a9 completed roles and both candidate checks but stopped at its fixed per-review repair limit. Actual defects concern source resource chronology and a redundant baseline contract, not CWI evidence/process/executable behavior. Host quiescence and terminal no-lease/quarantine/recording-gap state were verified; no resume or guard change occurred. Retained source is input only for fresh CWI-only product correctness work. Backendc74df0b remains clean; attempted/adopted/reverted1/1/0, no new candidate or maintenance attempt. Old CP-001/failed environment evidence and all recovery counts persist. Read-only audit schema/path/phase-transition corrections changed no controller state, product code, permissions or source refs; no automatic-approval rejection occurred.

## 2026-11-03 — Source recovery finally accepted and integrated; backend unchanged

Run7d05376e finally accepted/exact integrated b19e7ffa, final/target 1033/1033, no
CWI repairs. Existing controller survived the prior session-only shutdown and
completed naturally; no replay/restart, backend fix, controller-state/receipt edit,
permission correction, guard weakening or model/environment substitution was used.
Final receipt/source/diff/review/check chain, host quiescence and exact FF were
verified, then the unchanged target validator passed. Backend remains clean
c74df0b; attempted/adopted/reverted1/1/0. Old CP-001 and its failed environment
attempts remain preserved. No new maintenance candidate or pending audit exists.

The coordinator maintained administrative local evidence and froze accepted legacy
renderer output references for next 007-A; all product implementation/tests remain
CWI-owned. Read-only path/patch-context mistakes were corrected without product,
controller or source-evidence mutation; no automatic-approval rejection occurred.


## 2026-11-03 — Renderer acceptance and focused product-validator optimization preparation

Existing b7952877 completed naturally on unchanged clean backendc74df0b, final source1867872/receipt31f52a0a,controller/target1063/1063. One final-review repeated-root correction belonged entirely to the CWI Architect/Writer. Coordinator verified evidence/ownership, exact-integrated, and ran unchanged full target validation with external timing. No controller source/state/receipt/lease/quarantine/evidence-mode/security/executable/environment change or replay. Cumulative backend attempted/adopted/reverted remains1/1/0; CP-001 and failed environment attempts remain preserved. Read-only receipt-descriptor/filter/schema inspection assumptions were corrected without source/evidence changes or recovery consumption; no automatic approval rejection.

The human now requests safe automatically scalable concurrent validation. **This is a proposed product-validator change in implementation/scripts/validate.py, not coding_pipeline backend maintenance. The backend itself has not been modified.** REQ-DEV-VALIDATION-001 is prepared with process/fixture/resource/CPU/result/lifecycle regressions, future automatic discovery and unchanged CWI gates. Existing sequential behavior is one discovered unittest suite in one process; measured exact source1867872:1063discovered/executed/successful,zero other outcomes,2103.466wall seconds,2073.61user+11.35system CPU,99%CPU,340388KiB GNUtime maximum resident set. Inventory85a80da695886d34301e5f56a2f12d146cf71123f67239b3328244e21c4dc5d4; stdout3aaaa7a9. Later accepted implementation/commits/files/regressions/full comparisons/limitations and any rejected attempts must be appended here after safe integration; no acceleration claimed at preparation. Detailed local evidence:local/concurrent-validation-20261103/.

## 2026-11-03 — Product concurrent-validator implementation accepted; integration declined for fixture semantics

**Only the product validator/tests/documentation were implemented through CWI. The coding_pipeline backend itself was not modified.** Existing one-suite sequential behavior and original1063test/2103.466wall-second benchmark remain the integrated product. CWI REQ-DEV-VALIDATION-001/cd93ad37 finally accepted7d2622c51d75d8411b189eb558c4f7a732711a9c/tree dc097375b1ee9eedaeca9dac486d717f2197994b,receipt9d2516eed248a257e53099a4dffced07c37c6e0103d9dd077374e60b77bd32fb. Modified eight paths: implementation/scripts/validate.py; new test_validation_concurrent.py/test_validation_lifecycle.py/test_validation_resources.py/validation_fixtures.py under implementation/tests; implementation/README.md; docs/test-validation.md; docs/README.md. All98 original test/helper/fixture bytes/modes remain;56new methods.

Mechanism: one automatic unittest discovery, contiguous concrete module fixture units with exclusive conservative custom/dependency metadata fallback, inherited isolated fork workers/private external temp paths, wave C=min(T//2,max(0,A-2)), at most2*C workers, child-only affinity and conservative quota/cpuset sampling, bounded strict complete event/accounting protocol, inherited CWI groups/subreaping/cleanup/no replay. Future ordinary tests have no assignment list. Candidate/final1119/1119 in466.037593s/458.412761s, all four inventories exact16082d01a863b34a61e0a1d502fcaf90c2c301dbafea72ba6e4283a9be996ef8,zero other outcomes/source mutation. Two Writer repairs preserve genuine rejected initial1107/1115 sources and resolve custom fixture missing coverage, late finalization failure and signal restoration window. F001–003 closed by actual independent milestone/final reviews. Detailed stdlib/Linux/whole-suite serial/output/startup/memory limits remain in retained guide and run record; no equivalent-source full sequential comparison or final acceleration claim yet.

Independent exact-source disposable probe proves import-time unittest global module cleanups are inherited by both workers and execute twice rather than once, while success is reported. Integration explicitly declined; accepted branch/receipt/diff/26rehash references and probe preserved. No code/receipt/state/role transport/lease/quarantine edit, hot patch, model/limit/security change or replay. New REQ-DEV-VALIDATION-001-R1 freezes exact8-path Git identities/probe for fresh CWI Writer-only correction/adoption and full acceptance/integration/benchmarks. Preparing first B-023 fixture-mechanism recovery1/2 brings coordinator15; all previous limits preserved. This is product correctness work, not backend maintenance; backend attempted/adopted/reverted remains1/1/0 at cleanc74df0b. CP-001 and all earlier failed attempts remain. No approval rejection occurred.


## 2026-11-03 — Concurrent product validation integrated; controller unchanged by the optimization

**REQ-DEV-VALIDATION-001 and its R1 changed the product validator, not the coding_pipeline backend.** The original command discovered every `test_*.py` and ran one stock unittest suite sequentially. The human requested safe automatic concurrency to reduce repeated full validation time, with all coverage, fixture semantics, source-origin/layout checks and mandatory CWI gates preserved. Initial request/prelaunch commit60148d92a4e3381fa7b7feef4cc1fef5350ade1c; corrected request/prelaunch4736d1d9cf3324ec8913d98993736346d5381cdd. Only the CWI Writer implemented product code/tests.

Corrected run **1c313198-868b-4bbb-bd2f-7e7c0d3cec60** finally accepted and was exact fast-forward integrated as **ef3bfcf723a246750021cce32024cf6717eb5fa9**, tree777c79c5214e5042f2fb31bab605767d03cfe654, final receipt SHA256 **2ecf76d54d7e85b60b25eb3a61ae1201e842cabbb4c54d0758ecba203ebee1de**. No R1 repairs/findings. [Full run and nine-file inventory](development/runs/1c313198-868b-4bbb-bd2f-7e7c0d3cec60.md). Modified paths: implementation/scripts/validate.py; implementation/tests/test_validation_concurrent.py, test_validation_lifecycle.py, test_validation_module_cleanups.py, test_validation_resources.py, validation_fixtures.py; implementation/README.md; docs/test-validation.md; docs/README.md. All98 original test/helper/fixture blobs/modes and1063 original IDs remain;67 regression methods were added,56 retained unchanged from the first run and11 new stock-oracle cleanup cases.

One standard unittest discovery feeds automatically derived fixture-owner module units. No fixed test list, worker registry, result cache or per-test filtering exists. Custom/dependent suites, exceptional `VALIDATION_SERIAL=True` metadata and pending/unrecognized global module cleanup state select intact exclusive execution; opaque execution/accounting fails closed. Ordinary future tests enter the same planner without configuration. After each drained wave, effective affinity/cgroup quota/cpuset constraints and eligible T are resampled. Exact **C=min(T//2,max(0,A-2))**, at most2*C independent units, C0 sequential fallback. Concurrent children are constrained to C available CPUs without changing parent/host affinity. Unsupported safety/resource conditions fall back conservatively. Actual machine A24/T89→45→1 gave C22→22→0 and44→44→1 units, concurrent mask0–21; parent0–23 unchanged.

Linux fork/wait4/proc/prctl workers inherit the CWI process group, use private external temporary directories, bounded pipes/protocol/outputs, exact per-leaf start/completion/result ledgers, subreaping and PID-aware descendant cleanup. No detached workers, replay after uncertain effects or persistent execution state. Internal2650-second total deadline leaves cleanup inside the unchanged2700-second outer limit;16MiB stream limits remain. Failures/errors/skips/expected/unexpected outcomes, fixture exceptions and subtests retain stock meanings; only genuine addSuccess contributes successful coverage. Missing/duplicate/inconsistent results, crashes, deadlines, signals or cleanup failures invalidate success. Sequential full traversal remains available with `--sequential`.

Regression evidence covers dynamic discovery/exactly-once accounting, fixture/ordering/resource isolation, sequential equivalence, CPU even/odd/small-machine/quota/affinity cases, crashes/timeouts/descendant cleanup/output bounds/repetition, custom partial coverage and finalization signals. R1 specifically preserves import-time cleanup LIFO transitions, exception selection, setup/cleanup skips/errors, hook-time registration, unknown global state, original-suite identity and real independent overlap. Independent formerly failing callback probe now matches stock traversal once each. Candidate/final **1130/1130** in466.418689/462.455221seconds; integrated full automatic/sequential **1130/1130** with all four inventories and exact dispositions identical, inventory SHA2562a1e409cdce13cb00130703fcf3a786222a7df809b97a8f7a458d0f0425a0639,zero other outcomes/source mutation. Writer's advisory sandbox AF_UNIX denial was retained; real host full checks passed.

| Same accepted source, full suite | Wall seconds | CPU seconds | Largest-process max RSS KiB | Sampled group PSS KiB |
| --- | --- | --- | --- | --- |
| Sequential |2131.505420|2308.59|341220|312076|
| Automatic |472.709730|3000.75|245284|1119204|

Observed **4.5091× speedup /77.8227% wall reduction**, at about30% more total CPU and higher group memory. Original unchanged1063-test baseline2103.465754seconds is contextual, not the acceleration denominator. [Benchmark](development/benchmarks/concurrent-validation-20261103.md) records all timings, utilization, sampling coverage, startup latency, repeated full automatic runs and limitations. GNU time maximum RSS is not aggregate memory; one-second PSS samples are not a true peak. Linux fresh-process and private CPython cleanup-state introspection, exceptional serial dependencies and wave barriers remain documented constraints. No scientific/live-provider validation is implied.

Preserve initial cd93ad37 acceptance7d2622c5/receipt9d2516ee and all attempted1107/1115/1119 sources: two internal repairs closed genuine accounting/finalization/signal findings, but independent duplicated module-cleanup evidence caused explicit **declined integration**. R1 alone adopted/corrected through fresh CWI acceptance; nothing was cherry-picked, hotpatched or retrospectively relabeled. B-023 recovery1/2 is resolved but consumed. Backend remained cleanc74df0b through both CWI runs and all equivalent benchmarks. The separate human-requested prompt change below occurred only after quiescence. No controller state, receipt, frozen records or acceptance rules were edited.

## CP-002 — Human-requested targeted Reviewer diagnostics; adopted 2026-11-03

Explicit additional human instruction: “also change the reviewer's prompt ensuring that not all tests are run every time, but only those that might have been affected by the changes of the writer (should save some extra time)”. This authorizes this narrow backend prompt refinement; **no controller defect is asserted**, and the product optimization is not reclassified as backend maintenance. All mandatory full baseline/candidate/final and post-integration validation remains unchanged. Reviewers use the exact candidate's current controller results; their own extra tests/reproductions target affected code, callers, dependencies, helpers, fixtures and unresolved findings. They do not rerun the complete suite/full-suite command. Broad uncertainty requires the existing evidence and repair/stop route, not a speculative whole-suite rerun. Selection, actual commands/results and limits are reported as advisory evidence without invented validation IDs or cached passes. Complete criteria/final-diff review, permissions, schemas and clarification's no-execution rule persist.

Base **c74df0b09b4883776b1889b859b2df065f0b2fe4**; isolated local/backend-repairs/CP-002 on maintenance/CP-002-targeted-reviewer-tests. Only **cwi/prompts/reviewer.md** changed,13insertions/1deletion. Exact candidate/adopted commit **b6a2e05283f92f2bb42402d49e4a274225b43f6a**, tree84d10e6503367c940880d9b7ad9e603202c57b25, promptSHA256c6ace4d262ef52a602eb606cebf3a7362bf09df477af4c0dea045ff930c19f2b. Backend main exact-fast-forwarded at22:21:51.055203Z only after all affected owners/benchmarks/tests terminated. No product controller was launched from the maintenance worktree; no old frozen run resumed under new backend code. No executable backend code, tests, dependencies or role grants changed.

Source-local tests.test_prompts, tests.test_finalization, tests.test_validation and tests.test_contracts: clean baseline **125 run /123 passed /2 skipped /0 failures/errors**,94.180testseconds; modified candidate **same counts**,94.010seconds. The two pre-existing skips require opt-in independently authenticated Codex final-review runs; these were not enabled. Git2.40.1, fixture-owned actor identities, FD4096 and normal time/output supervision were preserved. Initial baseline launch failed before tests because its origin guard tried Path(tests.__file__) on a namespace package; no code changed. Concrete test-module origin guard corrected the launcher, then both real before/after suites passed. `cwi` itself is a regular package. This is a preserved pre-test evidence-launch failure, not a skipped failing test or rejected code candidate.

Fresh-history read-only native Astra/high audit examined the exact diff, packaged/context/clarification routing and gate boundaries: **ready to adopt, zero findings**. It changed no files and ran no extra tests; it is not a CWI acceptance or live-policy timing experiment. Supported adopted checkout subsequently passed all **7 packaged-prompt/routing tests**,zero skips/failures/errors,6.253testseconds/6.404202wallseconds. Backend and maintenance worktrees remain clean atb6a2e052. Prompt-level instruction cannot mechanically prove model compliance; no measured Reviewer acceleration is claimed. The actual measured speedup above belongs to full product validation.

Preserved sanitized [3159-byte zero-context patch](development/backend_patches/CP-002-targeted-reviewer-diagnostics.patch), SHA256 **f00b43e34d375931bd7a199675aa26fd61408b1c580db76fd4aae96eecd66339** (`git apply --unidiff-zero`); full commit retained separately. Local audit/proposal/failed launch/results/review/adoption/fresh readiness: local/backend-maintenance/CP-002/. Earlier CP-001 worktree, patch and all failed attempts remain. Backend attempted/adopted/reverted cumulative **2/2/0**; no new CWI start/repair or product recovery consumed. Fresh22:26:51Z confirms compatibility/login/model availability with unchanged Codex/executable/environment. No auto-review rejection, push, publication, budget reset or guard weakening occurred. Final administrative checkpoint and STOP; future roadmap work waits for a new session.

## 2026-11-04 — Output Writer deadline; no backend change

REQ-D04-007-B1/run2bc3d843 used clean supported backendb6a2e052 and stopped at its frozen2700-second Writer timeout after source changes. Actual final status has no candidate/acceptance/integration and forbids resume. Host/effects/lease/quarantine are resolved; draft/evidence are preserved. Enforcement of the configured limit is not evidence of a backend defect. No backend repair candidate, source/config/prompt change, guard/receipt/state edit, environment/security change or automatic-approval rejection occurred. Cumulative attempted/adopted/reverted2/2/0 stays. Existing deadline recovery2/2 remains exhausted; independent passive Tool-release work is selected without the failed draft or a new recovery allowance.


## 2026-11-04 — Passive Tool-release acceptance; backend unchanged

REQ-D05-001/run33db2c31 finally accepted/exact-integrated8cd859f7, final/target1165/1165.
The two genuine findings concerned new product codec DEL sizing and caller metaclass
hooks; both were repaired only by CWI Writers and independently accepted. No backend
malfunction, source/prompt/configuration change or maintenance attempt occurred.
Supported clone remains cleanb6a2e05283f92f2bb42402d49e4a274225b43f6a; cumulative
attempted/adopted/reverted2/2/0. CP001/002 patches, failed environments and all prior
evidence remain. No controller state/receipt/log/lease/quarantine edit, guard waiver,
model substitution, frozen-environment change or automatic approval rejection.
Read-only coordinator audit corrections changed no product/backend state and consumed
no recovery. Current source/receipt/check/integration evidence: [run record](development/runs/33db2c31-2248-425c-9de3-8c553d2dbd47.md).


## 2026-11-04 — Passive registration accepted; no backend change

REQ-D05-003/run9ec9e902 finally accepted/exact-integrated4608f0e,receiptb343da69,final/target1216/1216. No internal repair, backend defect, source/config/prompt change or maintenance candidate. Clean supported clone remainsb6a2e05283f92f2bb42402d49e4a274225b43f6a; cumulative attempted/adopted/reverted2/2/0. Timing observation and one corrected read-only receipt-reference helper changed no product/backend/state/receipt and consumed no recovery. All prior patches, failed attempts and historical recording findings remain preserved. No controller-owned state/log/lease/quarantine edit, guard weakening, model substitution or automatic approval rejection occurred. [Exact evidence](development/runs/9ec9e902-27ba-4f3f-891e-4e89eed13e0d.md).

## CP-003 — Human-requested role configuration and prompt modernization, 2026-11-04

**Authorization and scope:** the human's November 4 focused modernization instruction expressly authorizes this backend update beyond observed defects, and the exact future role allocation recorded in AUTH-2026-10-30-001 revision 7. No general maintenance expansion, product implementation, product run, historical resume, provider experiment, push, or publication occurred. All previous grants, budgets, historical configurations and resource-consumption records remain preserved.

**Safety and source:** original parent `b9068d8e527c7872de8dd35b2694597f27b3f09e`, clean main; original supported backend `b6a2e05283f92f2bb42402d49e4a274225b43f6a`, clean main. Isolated worktree `local/backend-repairs/CP-003`, branch `maintenance/CP-003-role-selections`. CP-001/002 remain retained. Host inspection found no live CWI/controller/role/validator; all 40 retained runs terminal, latest accepted source integrated, no lease/quarantine/pending integration. Old6ae8ca11/5f304a70 pending-operation markers are documented terminal nonresumable evidence, not live owners; preserved without replay. Historical inspection remains available with the original revision in `local/backend-repairs/CP-002` and the protected Git backup below.

**Architecture:** mandatory `RoleSelection`/`RoleSelections` immutable records replace the global run pair. Eight required flags validate generic model syntax and low/medium/high/xhigh before new-run effects; no defaults, inheritance, deprecated aliases or project model IDs in production. One typed role resolver supplies every invocation, correction, repair, final review and persistent continuation. Snapshot, in-flight, active-session, Designer-origin, amendment-conversation and replacement-state checks enforce the invoked role's pair while retaining session/source/Git/executable/sandbox/runtime identity checks. Run/audit schema 2 explicitly refuses old snapshots without mutation; no migration. Independent repository identity remains schema 1 so future new runs can use existing targets without touching old coordination records. Validation TOML and role response schemas remain unchanged.

Existing observational `run_published.details.role_selections` records all four requested model/reasoning_effort pairs, including unexecuted roles. Existing invocation_prepared events retain exact role attribution through corrections and resume; logging remains nonauthoritative and failure-contained. This is requested configuration, not independent provider execution telemetry.

Writer policy requires meaningful silent-test support and parallel-safe fixture design with legitimate serial exceptions; Reviewer optional diagnostics always use a valid quiet mode, remain targeted/read-only, and do not rerun full suites. Controller validation, native execution counts, failure evidence and acceptance remain unchanged. Shared FOLDER_CONTENT policy covers immediate directory navigation recursively within authorized scope, with planning/implementation/review responsibilities and ephemeral/external exclusions. Four source indexes were added; an explicit nine-resource manifest keeps navigation out of runtime prompts. Parent policy/runbook/startup/templates now require Designer gpt-6-astra/xhigh; Architect gpt-6.1-sol/xhigh; Writer/Reviewer gpt-6.1-sol/high, with all eight flags. Historical observations and frozen requests remain unchanged.

**Exact changed backend paths** (relative to the separate backend repository):

```text
FOLDER_CONTENT.md
README.md
cwi/FOLDER_CONTENT.md
cwi/cli.py
cwi/controller_logging.py
cwi/milestone.py
cwi/orchestration.py
cwi/prompts/FOLDER_CONTENT.md
cwi/prompts/common.md
cwi/prompts/reviewer.md
cwi/prompts/writer.md
cwi/role_selection.py
cwi/run_setup.py
cwi/state.py
cwi/state_store.py
pyproject.toml
tests/FOLDER_CONTENT.md
tests/role_selection_fixtures.py
tests/test_agent_logging.py
tests/test_amendment_conversations.py
tests/test_automatic_start.py
tests/test_cli.py
tests/test_codex_cli.py
tests/test_codex_selection.py
tests/test_command_start.py
tests/test_controller.py
tests/test_controller_logging.py
tests/test_conversations.py
tests/test_diagnostics.py
tests/test_finalization.py
tests/test_git_logging.py
tests/test_milestone.py
tests/test_orchestration.py
tests/test_prompts.py
tests/test_recovery_logging.py
tests/test_release.py
tests/test_release_live.py
tests/test_repair.py
tests/test_repository_coordination.py
tests/test_roadmap.py
tests/test_role_selection.py
tests/test_run_setup.py
tests/test_sessions.py
tests/test_source_launcher.py
tests/test_state.py
tests/test_state_store.py
tests/test_terminal_progress.py
tests/test_test_bootstrap.py
tests/test_validation.py
tests/test_validation_logging.py
tests/test_workflow.py
```

**Exact parent operating-document paths:**

```text
AGENTS.md
DEVELOPMENT.md
STATUS.md
coding_pipeline_changes.md
development/AUTHORIZATION.md
development/BACKEND_MAINTENANCE.md
development/CODEX_START.md
development/CODEX_START_AUTONOMOUS.md
development/ENVIRONMENT.md
development/MODEL_POLICY.md
development/PIPELINE_REVIEW.md
development/README.md
development/RUNBOOK.md
development/UPDATE_GUIDE.md
development/phases/D00-specification-and-operating-readiness.md
development/templates/REQUEST.md
development/templates/RUN.md
```

**Verification environment:** existing Python 3.11.15 (conda-forge), Git 2.40.1 from `/home/francesco/miniconda3/pkgs/git-2.40.1-pl5340h9abc3c3_4/bin`, matching GIT_EXEC_PATH/libexec/git-core and GIT_TEMPLATE_DIR/share/git-core/templates, process-only FD 4096. Final full verification uses explicit umask 022, a protected precreated log, a minimal process environment and PYTHONDONTWRITEBYTECODE=1; fixture-owned actor identities, no live opt-ins or changed global environment. Source imports resolve to the isolated checkout. Pytest-specific follow-up uses existing `/home/francesco/miniconda3/envs/botify312/bin/python` (3.12.13/pytest9.0.3), without installation.

**Attempt history:** one CP-003 maintenance candidate, refined before adoption. Required-CLI regression first failed as expected; packaging regression exposed wildcard inclusion before the explicit manifest. Original revision focused state/CLI29/29 passed. Initial fixture migration boundary batch102/102 passed (tool transcript only). First routing batch107 ran with 104passes,1 opt-in skip,2fixture errors: retained Writer intent in a newly added sequence, and a role-only forged session rejected earlier by stronger invariants. Reordering the no-effect argv probe and forging a coherent role/settings tuple preserved the intended original assertions; five targeted cases then passed. A follow-up command had a nonexistent selector (3passes/1loader error), corrected without product changes. An early `/usr/bin/python3` attempt failed imports because it is Python3.10; suitable existing Python3.11 was selected. An early diagnostic full sweep was interrupted 130 before a completion summary; not counted as passing. The agent's initial Python3.13 label was corrected from actual interpreter evidence to3.11.15.

Independent review found two Important issues, both fixed before adoption: the run schema bump must not change the shared repository identity format; opted-in real integration tests must not use fake fixture model IDs. The repository regression first encountered a test-directory permissions error, then reproduced the actual schema mismatch once private fixture setup was correct, then passed with the independent schema 1 identity constant. All 19 coordination tests passed. All opt-in entry points now require eight explicit CWI_LIVE_* model/effort settings; deterministic helper validation passed, and no actual live model was invoked. Reviewer's initial system-Git targeted attempt failed the existing -z prerequisite; rerun with the established capable Git passed. Independent final review: no outstanding findings,17 targeted checks passed including package build/install; final small prompt/assertion additions also reviewed without findings.

The in-progress diagnostic sweep completed 1044 tests/703.001s:1017 passed,21 skipped,2 failures,4 errors. Five failures/errors match the reviewed repository-schema and session-fixture issues; the other is a test-launch prerequisite: umask 077 masks an existing fixture's requested 0755 public log directory to 0700. The permissions test passed unchanged under a normal mask. A second full sweep was interrupted 130 after recognizing that same mask; host inspection confirmed no surviving test/CWI descendants. No frozen-candidate claim is made for either sweep. A third sweep with corrected mask exposed a deterministic adapter fault test that deliberately bypassed live setUp, leaving its new role_selections absent. The fake-CLI fixture now supplies explicit synthetic selections; the preceding corrected-environment full sweep recorded 1046 tests/1030 passed/15 skipped/1error in719.799s, preserving that exact failure. All 47 adapter cases complete with 38 passed/9 live skips in5.580s. Earlier full patch b47bcd9d18e0932ffedbfced833a66e12cc5b621f35fe85e4efc5cec857903b0 is retained separately; no old record was rewritten to hide these attempts. Final verification uses the corrected stable source.

**Retained verification commands and results:**

- `python3 -m unittest tests.test_state tests.test_cli -v` on original CP-002:29 passed/1.683s.
- `python -m unittest tests.test_role_selection tests.test_state tests.test_state_store tests.test_controller tests.test_cli tests.test_command_start -q`:102 passed/9.115s, tool transcript only.
- `python -m unittest tests.test_sessions tests.test_agent_logging tests.test_controller_logging tests.test_amendment_conversations tests.test_state_store.StateStoreTests.test_old_global_selection_schema_rejects_load_without_mutation -q`: initial107/104 passed/1 skipped/2 errors,145.261s; preserved tests-focused-routing.log. Corrected five-case follow-up5 passed/1.807s, tests-focused-final.log.
- `python -m unittest tests.test_prompts tests.test_release -q`:25 passed/20.434s, including actual sdist/wheel/clean-install/external loading. Later strengthened assembled-prompt tests: `python3 -m unittest tests.test_prompts -q`,7 passed/9.411s, prompts-final.log.
- `python3 -m unittest tests.test_repository_coordination -q`:19 passed/1.960s, repository-schema-green.log; actual old-identity-to-new-run failure retained in repository-schema-red.log.
- Live-fixture/helper deterministic checks:24 collected/9 passed/15 opt-in skipped,0.175s, tests-live-fixture-checks.log. Full exact commands and diagnostic artifacts remain under local/backend-maintenance/CP-003 and in the task transcript.
- `CWI_TEST_PYTEST_PYTHON=/home/francesco/miniconda3/envs/botify312/bin/python PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_test_bootstrap -v`:21 passed/35.807s, zero skips; covers all 6 pytest cases absent from the primary interpreter.
- Current README and runbook: all 4 start examples parse against the new CLI;13 shell blocks pass bash -n;92 parent local links checked; git diff --check clean. No obsolete global CWI flags remain in current startup instructions; remaining mentions are labeled historical evidence or the unchanged underlying Codex option.

**Final verification and adoption:** `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` from the isolated checkout, with the environment above and existing CWI_TEST_PYTEST_PYTHON, ran **1046 tests:1031 passed,15 opt-in live skipped,0 failures/errors**,721.167s,exit 0 (2026-11-04T17:07:52Z–17:19:54Z). All 6 pytest cases executed within this full run. The15 skipped cases require separately opted-in authenticated model execution; they were not represented as passed. Full log `local/backend-maintenance/CP-003/acceptance-suite.log`,SHA256`6ad7c18c8f084c448048a0c9042c7c3550de5f3ed7e66485904544ca7f528223`. Source-byte manifest confirms the exact105 source files stayed unchanged throughout this final run. Observational-logging warning messages belong to intentional failure-containment tests, not acceptance overrides.

Backend commit **bcb7ad24f83ff5193345f3d4fa72122ea53a4e66**,tree`887cb6cfb7650276851da99e0f5164f6309e8fd4`, was committed on the maintenance branch and adopted into supported main by exact fast-forward at **2026-11-04T17:21:41Z**. Original base **b6a2e05283f92f2bb42402d49e4a274225b43f6a** remains in CP-002 and the backup. Fresh host17:21:12Z inspection found no controller/role/validator/test descendants;40 retained runs terminal. Original-backend status confirmed no lease/quarantine/recovery; branch/base/cleanliness/hooks/diff/collision checks passed. The supported checkout then passed `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_role_selection tests.test_prompts -q`:**15/15**,zero skips/failures/errors,8.622s, including real packaging/install verification, with supported-checkout source origin proved. Its logSHA256`92c9adbf3932857d5fe2694f829b7b7f911f5dccec8dbbcc39ffaf60cfc99eab`. Both backend worktrees remain clean at the tested commit.

Protected reviewable [final patch](local/backend-maintenance/CP-003/CP-003-role-selections-final.patch),SHA256**b26dc6650538784e479c6010a5536a74aede2609fe99b516fc99148c18f7e575**, matches the exact base-to-adopted Git diff. Protected [complete-history Git bundle](local/backend-maintenance/CP-003/CP-003-backend.bundle),SHA256**c2b3d878782dec0eecc5c6e2026e75cd7edef3ff1228c82473e2153e70911f38**, passed git bundle verify and retains both original and new branch refs. Earlier intermediate patch, failed/pre-test/interrupted outputs, final source digests and sanitized adoption record remain in the same private evidence directory; no failed attempt was relabeled successful. Backend attempted/adopted/reverted cumulative **3/3/0**; all product start/repair/recovery limits and historical resource accounting are unchanged. Coordinator/native review usage is not measured by the product CWI ledger.

All 745 retained historical snapshots/events/receipts/observational log files rehash unchanged. No implementation/, product specification, historical request/run record, controller state, receipts or validation results were modified. STATUS adds only a new operating handoff note and next safe action; its prior product checkpoint and consumption text are preserved. Parent current policy, examples and templates are synchronized, with complete17-path inventory above. The initial parent staging/commit command encountered the sandbox's read-only .git boundary before changing the index or creating a commit; scoped Git escalation is required for the already-authorized administrative checkpoint. This was a filesystem denial, not an automatic-approval review rejection. No push or publication occurred. The backend is implemented, tested and adopted, and is safe for **new schema-2 runs** after ordinary readiness checks; this does not authorize historical resume or skipping future prelaunch reconciliation.


**Limits and next action:** no live provider-model execution or effective provider-model attestation is claimed. Actual installed Codex 0.166.0 parser/security interface and existing ChatGPT authentication probes passed; SHA256 b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8. Account catalog fetched2026-11-04T16:39:43.361492207Z advertises both approved identifiers/efforts; readiness is time-dependent. No scientific/product acceptance is implied. The unlaunched REQ-D05-004 retains its preparatory old model note; request snapshots were outside this maintenance edit set. Exactly one next safe action after this checkpoint: in a later session, reconcile that pending request and fresh new-run readiness against revision 7 before any product launch. This session stops without a new product run or historical resume.

## 2026-11-04 — Assessment contracts accepted; backend unchanged

REQ-D05-004/run `2b89ca22-5cae-4535-aa48-c16d07b3cff6` finally accepted/exact-integrated
`150aa0ee3e9e5611c77eeb714f18b8484578235c`; final/target1276/1276 with no findings or repairs.
This first product run on adopted schema-2 backendbcb7ad24 used the four approved
role pairs and all five actual invocation records agree. Backend source, Codex,
launch map and security settings stayed fixed. No maintenance candidate or
recovery was attempted; backend counts remain3/3/0 after CP-003. CWI owns
implementation review/validation; coordinator checked Designer understanding,
receipt/source/integration safety and required target validation. Historical
state and the original backend remain preserved; no migration/resume occurred.

## 2026-11-05 — Passive assessment persistence; backend unchanged

REQ-D05-005/run5bad636b finally accepted/exact-integrated9f6cd171,
receipt1c598a1b,final/target1326/1326. Two CWI product repairs close four
allocation/error-context findings; they are not backend maintenance or coordinator
recoveries. Backend stayed cleanbcb7ad24,pinnedCodex/map/security unchanged;all11
role invocations match revision7. No maintenance candidate or historical migration
was attempted. Counts remain3/3/0. Original backend/evidence are preserved.
Read-only coordinator audit-helper assumptions were corrected without mutating
source/state/receipts or consuming recovery. Required target verification passed.


## 2026-11-05 — Passive Tool CLI; backend unchanged

REQ-D05-006/run0c046a57 finally accepted/exact-integrated53be2755,
receipt538f6cb4,final/target1372/1372. One CWI fixture repair closes F001; it is not
backend maintenance or coordinator recovery. Backend stayed cleanbcb7ad24,
pinnedCodex/map/security unchanged;all8actual role invocations match revision7.
No maintenance candidate,state/evidence rewrite or historical migration. Counts
remain3/3/0. Read-only audit-helper syntax/log-source assumptions were corrected
without mutating evidence or consuming recovery. Required target check ran once,
with exact matching final dispositions. Original backend and failed evidence remain.

## 2026-11-05 — REQ-D02-007 and graceful shutdown; backend unchanged

REQ-D02-007/run `8715d97e-341b-450a-8281-4760a34ba2cb` used clean supported backend `bcb7ad24f83ff5193345f3d4fa72122ea53a4e66` with its frozen schema-2 role settings. Three CWI product repairs, two final-review rounds and the post-integration validation environment correction did not edit backend source, controller state, receipts or historical evidence. No backend maintenance candidate, attempt, adoption or reversion occurred; cumulative backend counts remain **3/3/0**. The original backend revision remains preserved for old schema-1 inspection. The human directed shutdown after the exact product integration/checkpoint, without another CWI start.

## 2026-11-05 — REQ-D02-008; backend unchanged

Run `c255a52f-4034-46dd-b2ff-69e046e7814a` used unchanged clean backend bcb7ad24f83ff5193345f3d4fa72122ea53a4e66 and eight approved recorded role pairs. One CWI product repair, final/target validation and external exact integration did not change backend/controller/evidence. No maintenance attempt/adoption/reversion; cumulative3/3/0. Preserved original backend and historical configurations remain intact.

## 2026-11-05 — REQ-D02-009 accidental interruption; no backend change

Original controller cancellation left a live orphan Writer. Coordinator preserved execution, waited for actual completion/quiescence, then performed one supported resume under unchanged bcb7ad24/environment. It reconciled STOPPED_INCOMPLETE/noresume/completed response requiring explicit adoption; historical observational uncertain_shutdown/logging_incomplete findings are preserved. No backend defect, repair candidate, source/config/prompt/executable/environment/state/receipt/log/lease/quarantine edit or automatic-approval rejection. Attempts/adoptions/reversions remain3/3/0; all previous failed candidates/patches/backups remain. Human explicitly authorizes one additional product salvage attempt, REQ-D02-009-R1, preserving normal acceptance gates. That is not backend maintenance or old-run replay authority.

## 2026-11-05 — REQ-D02-009-R1 accepted/integrated; backend unchanged

The expressly authorized one-use salvage completed through unchanged clean backend bcb7ad24f83ff5193345f3d4fa72122ea53a4e66. One CWI product test/documentation repair resolved F-001/F-002; final full-range acceptance and required target1511/1511 passed. Exact external integration0da0dd0f and shutdown reconciliation changed no backend source/config/prompt/executable/environment/controller state/receipt/log/lease/quarantine or security guard. No maintenance attempt/adoption/reversion; cumulative3/3/0. Prior CP-001/002/003,failed candidates,patches/backups and schema1-compatible original backend remain intact. Read-only local verifier metadata/positive-subtest-shape assumptions were corrected against actual evidence without changing source or consuming CWI recovery. No automatic-approval rejection occurred. Human stopped after current bounded completion;no additional implementation request or phase.

## 2026-11-06 — REQ-D02-010 backend audit

Runb4a385e8 accepted/exact-integrated0668007,final/target1544/1544. Backend remained unchanged cleanbcb7ad24f83ff5193345f3d4fa72122ea53a4e66;no maintenance attempt,adoption or reversion. Cumulative3/3/0. Historical source,patches,backups and unfinished-run evidence remain preserved. Read-only metadata/namespace verifier clarifications were not backend changes or CWI recoveries.

## 2026-11-06 — REQ-D03-009 backend audit

Run45afcd6b accepted/exact-integrated6d023d5,final/target1577/1577. Backend stayed unchanged cleanbcb7ad24f83ff5193345f3d4fa72122ea53a4e66;no maintenance attempt/adoption/reversion. Cumulative3/3/0. The one CWI product repair is not backend maintenance. Historical source,patches,backups and unfinished-run evidence remain preserved.
