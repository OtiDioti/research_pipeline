# coding_pipeline change audit

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
