# Development roadmap

This is the proposed sequence for implementing the product in [project_description.md](project_description.md). Current execution belongs in [STATUS.md](STATUS.md), not in a second independent set of status cells here. Each phase has a coherent outcome and acceptance obligations; each may require several bounded coding-pipeline runs.

**Amended 2026-10-30 to specification v1.4:** M0-E contracts and executable evidence gate dependent engineering. M0-S pilot/expert/protocol decisions remain pending and gate their corresponding scientific evaluations, qualification claims and release, not independent implementation. All mandatory requirements remain mapped; documentation is not M0-E completion. Mixed phases track engineering and empirical outcomes separately.

| Phase | Outcome | Depends on |
| --- | --- | --- |
| [D00](development/phases/D00-specification-and-operating-readiness.md) | Specification and operating readiness | Initial repository |
| [D01](development/phases/D01-testable-product-foundation.md) | Testable foundation; M0-E engineering contracts and separate pending M0-S | D00 |
| [D02](development/phases/D02-durable-scientific-records-and-provenance.md) | Durable scientific records and provenance | Relevant settled M0-E contract; commissioned executable subset before downstream reliance |
| [D03](development/phases/D03-seeded-project-intake-and-navigable-vault.md) | Seeded project intake and navigable vault | Relevant evidenced D02 engineering contracts |
| [D04](development/phases/D04-controlled-execution-and-recovery.md) | Controlled execution and recovery | D02, D03 |
| [D05](development/phases/D05-tool-contracts-and-capability-execution.md) | Tool contracts and capability execution | D04 |
| [D06](development/phases/D06-single-researcher-vertical-slice.md) | Single-researcher vertical slice | D03, D04, D05 |
| [D07](development/phases/D07-independent-verification-and-scoped-acceptance.md) | Independent verification and scoped acceptance | D06 |
| [D08](development/phases/D08-adaptive-research-coordination.md) | Adaptive research coordination | D07 |
| [D09](development/phases/D09-whole-project-operation-and-reporting.md) | Whole-project operation and reporting | D08 |
| [D10](development/phases/D10-scientific-pilot-and-architecture-evaluation.md) | Scientific pilot and architecture evaluation | D09 |

## Scope discipline

The sequence deliberately establishes a usable single-researcher path before multi-agent coordination. Reliability, provenance, boundaries, and recovery are developed with each capability, not appended as a final hardening phase. Verification infrastructure for development begins at D01; scientific candidate verification is the product feature delivered at D07.

The phases are proposed defaults. Move an outcome if the exact specification or actual interfaces require it, and record why. Distributed services, a graph database, an Obsidian plugin, and any particular symbolic/numerical/coding tool are not prerequisites unless the specification explicitly requires them. Future plans remain outcome-level until they become executable requests.

## The first implementation boundary

D00 prepares and verifies the environment. REQ-D01-001 is one complete, testable foundation slice; it must not be split into an accepted empty skeleton followed later by tests. Start with one CWI milestone because the frozen bootstrap candidate check requires the whole foundation. Later runs can use more internal milestones when each intermediate candidate satisfies the frozen checks.

## Requirement coverage

Use [REQUIREMENTS.md](development/REQUIREMENTS.md) to map each mandatory requirement to a phase, request, exact evidence, and integrated source. Record deferred obligations in [BACKLOG.md](BACKLOG.md) with authorization and resume conditions. A phase cannot be called complete while its mandatory obligations are merely moved into an unowned future list.

## Progression under continuous authorization

After commissioning and the actual activation grant, normal completion of a request or phase leads directly to the next ready scoped request. Do not wait for a human merely to move from D02 to D03. Every transition still requires its dependency and evidence gates. Use [AUTONOMY.md](development/AUTONOMY.md) and [AUTHORIZATION.md](development/AUTHORIZATION.md).

D10 requires actual scientific evaluation and any mandated human judgment; it is not automatically completed by implementing the evaluation code. A blocked mandatory requirement remains visible even when other independent development can continue.

## Specification milestone mapping

| Specification gate | Development ownership |
| --- | --- |
| M0-E engineering contracts | D01 and commissioning executable contracts in bounded D02–D07 requests; downstream reliance requires actual evidence |
| M0-S scientific decisions/evaluation material | R-001–R-003 remain pending; fix before dependent scored evaluations, qualification and release; independent engineering may continue |
| M1 durable records and vault | D02–D03 |
| M2 controlled execution, adapter contracts, minimum no-model report | D04–D05 |
| M3 single complete research loop and bounded context | D06 |
| M4 verification and atomic promotion | D07 |
| M5 adaptive coordination and optional delegation | D08 |
| M6 synthesis, human decisions, navigation and export | D09 |
| M7 actual held-out pilot and architecture comparison | D10 |

Continuous authority is active under AUTH revision 6 (100 starts, unchanged explicit 2700-second new-run deadlines). Commissioning, the synthetic example and REQ-D02-001 durable records are integrated, but M0-E overall, M0-S, D02 and the research product are not complete. REQ-D02-002 verified backup/restoration is also integrated. REQ-D02-003 typed provisional scientific contracts/admission is integrated. REQ-D02-004-R1 versioned core identities and verified-backup migration are integrated. REQ-D02-005-R1 attributed review/issue records are accepted/integrated. REQ-D02-006 work-product bundles and safe draft checkout/preview/import are accepted/integrated. REQ-D03-001 versioned Source captures and bounded inert local ingestion are accepted/exact-integrated at d8dffdd with 343/343 target tests under the recorded descriptor prerequisite. That historical Source checkpoint led to REQ-D03-002 corpus history and REQ-D03-003 project/intake dossiers, now integrated below; support freshness, fencing and remaining core record semantics remain required. [M0 packet](development/decisions/M0-contract-and-scientific-review.md) separates settled engineering choices from missing scientific decisions. Later requests consume only the evidenced predecessor behaviors they need; they need not wait for unrelated empirical acceptance. No live-product service/data/budget authority has been added.

REQ-D03-002 is now accepted/exact-integrated at 7d6dd6246e47ace09ff44a1decef14c93251f0ac with 369/369 target tests. Its immutable inventory and exact Source/history contracts enable the next bounded project/intake dossier in REQ-D03-003, followed by protected readable views and actual authorized research admission. The ordinary remaining D03/D04 requirements and scientific holds remain open; no phase completion follows from this recording subset.

## Historical project-intake checkpoint — 2026-10-31

REQ-D03-003 is finally accepted/exact-integrated at9373860 with396/396 target tests; [run evidence](development/runs/db2829bc-fca9-48d7-b2c1-b9e99348c197.md). Exact project history, attributed inspected subsets and coherent brief/report/context pins support readiness proposals only. D02/D03 and M0-E remain partial; M0-S remains pending. Next [REQ-D03-004](development/requests/REQ-D03-004.md) prepares consistent immutable readable snapshots with bounded private generation/exclusive publication. Refresh/direct-edit preservation and all scientific/operational obligations remain required. Continuous12/50 starts consumed,38 remain; deadlines2700 seconds, unchanged model/grant.

## Historical snapshot recovery checkpoint — 2026-10-31

REQ-D03-004 stopped terminally without acceptance: first-milestone candidate81ec2f3 passed432/432 but lacked required controller-recorded complete-diff evidence. Main remains accepted project/intake9373860 (396 tests); no snapshot feature is integrated. [Run evidence](development/runs/32b61b7f-7d9b-475d-a44e-74e53d03c5a0.md). [REQ-D03-004-R1](development/requests/REQ-D03-004-R1.md) is the next bounded replacement, using preserved CWI draft context and two frozen checks. Protected publication/inspection is still unimplemented. Continuous13/50used,37remain; repairs7,recoveries4,backend0. No scientific or phase completion is inferred.

## Historical snapshot integration checkpoint — 2026-10-31

REQ-D03-004-R1 is finally accepted and exact-integrated at c57a621c3e3f7806030de13b75b4fe2890b81cc7, with 489/489 controller/target tests and both bound checks passing. [Run evidence](development/runs/7ee32819-ee00-4b1b-bdba-ea26fb90cf3e.md). Consistent detached metadata, deterministic linked Markdown/manifests, verified independent copies, private complete publication and bounded offline inspection now have implementation evidence. B-016's missing-check recovery is resolved; its terminal predecessor remains preserved. No backend change.

D03 and M0-E remain partial; M0-S remains pending. Generated-view refresh with preservation of direct edits and renames is the next ready engineering boundary under §§9.7–9.11/R-026/R-028. Full branch/runtime/report workspaces, intake interpretation/authorized readiness and lifecycle/authority/tool/research obligations remain required. The authoritative next action and handoff are in STATUS; continuous 14/50 starts used, 36 remain, unchanged grant and 2700-second deadlines.

## Refresh preparation — 2026-10-31

Fresh Git and retained CWI reconciliation confirms c57a621 is already integrated beneath administrative 7f3f081; twelve accepted results and three terminal failures are preserved, with no active owner or pending integration. [REQ-D03-005](development/requests/REQ-D03-005.md) is the next ready two-milestone request for bounded divergence/rename capture and immutable successor refresh with preservation and recovery. Existing view and draft APIs provide its prerequisites. No product implementation is added by this preparation. Continuous starts remain 14/50 until launch; next start is 15/50. Full D03, remaining M0-E and scientific/live obligations remain open.

## Historical refresh integration and CLI progression — 2026-10-31

REQ-D03-005 is finally accepted/exact-integrated at 8cfb0357ccccff1f079c419eb1ca4b7f4d3b135c, with 579/579 controller/target tests and both bound checks. [Run evidence](development/runs/c62af399-bf8c-4b25-8ef7-ec1947fad6ae.md). Direct edits, renames and ambiguous identities are preserved/diagnosed in an immutable successor package, with verified generated links and real interrupted/conflicting publication evidence. All prior scientific artifacts and canonical history remain fixed. Three CWI repairs resolved the review findings; no backend or authority change.

Next ready [REQ-D03-006](development/requests/REQ-D03-006.md) exposes exact inspection and explicit work-product checkout/preview/saved-proposal/submission through the local CLI. This is a bounded R-082 subset consuming evidenced contracts, before broader execution/authority work. D03/M0-E remain partial; M0-S and all remaining scientific/runtime obligations persist. Continuous 15/50 used, 35 remain before next start 16; unchanged model/high effort and2700-second deadlines. STATUS contains the single current next safe action.

## Current local CLI integration and view-command progression — 2026-10-31

REQ-D03-006 is finally accepted/exact-integrated at0a875dd4c822465a297ff3e6757f69962823aea0, controller/target657/657 and both bound checks passed; [run evidence](development/runs/63f0416b-b04a-4a2a-9173-d59716ec6741.md). Seven commands expose bounded exact inspection and explicit work-product checkout/preparation/saved-proposal inspection/submission with original-ID recovery. Two product repairs resolved directory/leaf observation races and a fixture mode;78 new tests preserve earlier behavior. No backend/authority change.

Next ready [REQ-D03-007](development/requests/REQ-D03-007.md) exposes existing immutable-view generation, independent-baseline preserved refresh and offline inspection. This makes the requested view workflow usable through the CLI before D04 admission, whose resource/authority/minimum-closeout dependencies remain required. D03/M0-E remain partial; M0-S and remaining scientific/runtime duties persist. Continuous16/50 used,34 remain before start17. STATUS contains the single current next safe action.

## Current view CLI integration and diagnostic repair — 2026-11-01

REQ-D03-007 / CWI c9055f4c-f63c-4815-ab5e-670116ce1333 finally accepted and exact-integrated 2643673035b5be43c3f12cbab1567dcce3377aa6, final receipt 8372ac488fa8f0b3989e7fa637f34c97174b0d0eb2d8724868f67dbcffc3d67f. Four source-local commands expose immutable generation, independently pinned preserved refresh and offline inspection. Final controller696/696 in451.094s; integrated target696/696 in451.163s, zero skips/errors/failures/source mutation, completed2026-11-01T00:11:17.402942+00:00, stdoutSHA256ba0d147f67885b616e725a45e89fc51b68b4ad92923174d43a727168f3b64f94 and empty stderr. Two internal repairs resolved F001–F004;39 new tests preserve657 baseline tests and the permanent validator. No backend/authority change. [Run evidence](development/runs/c9055f4c-f63c-4815-ab5e-670116ce1333.md).

Independent coordinator inspection also confirmed B-017: loss of a pinned selected-view root after real offline inspection returns is reported as5/unsafe_layout instead of6/integrity_error. It fails closed without success output, data loss or canonical mutation. CWI acceptance does not close this separate observation. DEV-046 retains it explicitly and prioritizes bounded REQ-D03-008 before D04; no diagnostic criterion or integration gate is waived. Next ready [REQ-D03-008](development/requests/REQ-D03-008.md) is a localized observation-classification repair with real subprocess regressions. D04 resource accounting follows once this defect is resolved; run admission still requires readiness/authority/fencing/closeout prerequisites. D03/M0-E remain partial, M0-S pending. Continuous17/50used,33remain before start18; STATUS supplies the single current next safe action.

## Diagnostic repair integrated; next resource-accounting boundary — 2026-11-01

REQ-D03-008 / CWI 4c1833ef-8ef9-4b07-9f33-79acb6f7e8b0 finally accepted and exact-integrated `3f4564c770bdec8848587ad6052a8f2c6bdb75de`, tree `204b5eb30e5309bd23839bd58d0afb2e00b2d082`, final receipt `80ad5251c81e2a26c32e7528c58cdc41d38f93ef0a4247a1e00487c1f265df94`. Final controller 707/707 in 475.208s; Integrated target 707/707 in 476.667s, zero skips/errors/failures and unchanged clean source; completed 2026-11-01T01:20:15.956694+00:00, stdout SHA-256 `8479e46b433fb6d6c318fd9256b0cd365c79d76e9beac27a192ec8bb4f58a077`, empty stderr. One internal test repair resolved F-001/F-002. All 696 predecessor tests and the permanent validator are preserved. [Evidence](development/runs/4c1833ef-8ef9-4b07-9f33-79acb6f7e8b0.md).

B-017 is resolved without changing shared checkout/package/publication contracts or scientific records. Next ready [REQ-D04-001](development/requests/REQ-D04-001.md) commissions durable controller-private resource accounting in the canonical SQLite boundary, explicit opt-in schema3 with verified2→3 migration, protected hierarchical reservations and conservative uncertainty/receipt reconciliation. Two bounded milestones; default schema2 and old schema/backup behavior remain. Preparation is not executable evidence or research admission. Authority/readiness/fencing/dispatch/context and mandatory no-model minimum reporting remain prerequisites before research execution. All broader D03/M0-E and M0-S obligations remain pending.

Continuous18/50 used,32 remain before start19; STATUS supplies the single current next safe action.

## Resource ledger integrated; deterministic reporting next — 2026-11-01

REQ-D04-001 / CWI 6eaf6f92-ec81-4d73-b83d-9b97a30cfb02 is finally accepted and exact-integrated at b13fff0a2e26acba9b4b9bad3dde430207e4eaab, tree 202546e8128e7c7f31b7e6f5be86f4028656764f, final receipt f37a74adf475689ab0110ccc7e37095c2fe5c48fea996f322457c4c55d2f58ce. Final controller 778/778 in 496.704s; integrated target 778/778 in 495.886s, zero skips/failures/errors and unchanged clean source. Target completed 2026-11-01T03:34:59.250932+00:00, stdout SHA-256 ef9b8636d8d14e4414e348652585f6c6ef551c1d211127ee92fe3feebd426c4f, empty stderr. [Run evidence](development/runs/6eaf6f92-ec81-4d73-b83d-9b97a30cfb02.md).

Strict opt-in schema 3, verified 2→3 backup migration, protected hierarchical reservations, attributed partial/complete usage, conservative/authoritative settlement, exact retries, sticky breach gates, coherent snapshot 2 and crash/reopen/backup recovery are evidenced. Default schema 2, old DDL/migrations and scientific records/artifacts remain intact. Resource declarations do not authenticate grants, admit research or establish service-enforced caps. Actual authority/readiness, lifecycle/fencing, dispatch, model/tool/context, mandatory reporting hooks and scientific qualification remain required.

Next ready [REQ-D04-002](development/requests/REQ-D04-002.md) provides committed report capture and protected publication before actual admission. Automatic lifecycle hooks and full D04/M0-E remain required; scientific holds gate dependent work only. STATUS owns the single next safe action.


## Human-requested resource-conservation stop — 2026-11-01

REQ-D04-002 / CWI 6ae8ca11-0df2-48e2-abc8-65d51adaa187 was stopped at the human’s explicit resource-conservation request. Provisional 2e4343890e519075915e2d25b4bf18875d2ef8a9 passed 806/806 controller tests and the complete-base diff check; first-milestone Reviewer was cancelled, zero milestones/final receipts exist, and nothing from this request was integrated. STOPPED_INCOMPLETE, no lease/quarantine/live execution; retained pending_authoritative_operation is a recovery record, not a running process. CWI says resume_allowed=false and new_run_after_manual_salvage. Preserve the candidate and all old work; do not replay/resume or start another workflow in this session.

D04 remains at the report primitive boundary; next engineering work requires preserved-draft salvage/review and the unimplemented publication milestone before broader admission/lifecycle work. STATUS and local/live.md supersede earlier “next ready” launch statements. Future authority remains; current session is stopped.

## New-session reporting recovery — 2026-11-02

The human resumed continuous engineering; fresh Git/CWI/host evidence validates the shutdown disposition and all 17 integrated acceptances. [REQ-D04-002-R1](development/requests/REQ-D04-002-R1.md) is prepared to reuse the exact unaccepted capture draft through frozen CWI context and complete immutable publication/navigation with fresh acceptance. No accepted reporting evidence is claimed yet. All original reporting/lifecycle, D02/D03/M0-E and scientific obligations remain. STATUS owns the single next safe action; historical shutdown statements refer to the ended session.

## Report boundary recovery — 2026-11-02

Capture-only milestone acceptance in d343c0af does not complete the report boundary; publication timed out and remains a retained draft. REQ-D04-002-R2 completes the same full report scope in one bounded recovery milestone, with actual-metadata preflight repair and preserved formats/guards/late-usage coverage. After final acceptance/integration, authenticated operating authority/readiness and lifecycle/admission/fencing remain the next engineering prerequisites. No phase or scientific gate is closed by salvage.

## Reporting acceptance recovery — 2026-11-02

The complete retained reporting candidate now passes845/845, but R2 stopped before independent review on combined context size. R3 changes only reference packaging and requires fresh acceptance; no product requirement or phase gate is removed. Authenticated operating authority/readiness and lifecycle/admission/fencing remain next after actual report integration and validation.


## Reporting primitives delivered; authority boundary next — 2026-11-02

REQ-D04-002-R3 / CWI 528cf918-2619-45c8-a6b6-ee35ed42fb3e finally accepted and exact-integrated **7a1edeb8b604bd7acd9c90861f096e2e107e32f6**, final receipt 851d915f2588097602250ddcfe671586a90e65d802165df72227057a02cb69db. Final controller845/845; Integrated target **845/845 in 958.769s**, zero skips/errors/failures and unchanged clean source; completed 2026-11-02T10:48:24.247315+00:00, stdout SHA-256 e62a74d73df7c3c135f081b7ec5097b1758ff8c752151ba159c9315a8af1c37d, empty stderr. [Run evidence](development/runs/528cf918-2619-45c8-a6b6-ee35ed42fb3e.md).

Coherent committed reports, complete minimum content, immutable navigation/publication and offline recovery are delivered as library primitives. Automatic initial/checkpoint/stop hooks and pending-report restart gates remain mandatory before admitted execution. Next bounded REQ-D04-003 supplies authenticated operator decisions and exact readiness; database queue/attempt/fencing/resource admission follows. D02/D03/D04/M0-E remain partial and M0-S pending. The roadmap does not turn synthetic operator decisions into scientific approval; STATUS owns the current next safe action.


## Authority candidate and capacity recovery — 2026-11-02

[Run5f304a70](development/runs/5f304a70-d68b-422b-ac31-6d006d8a1825.md) candidate231c712e passed876/876 and full committed-base diff after two repairs, but Reviewer provider capacity failure returned no verdict. No final acceptance/integration; all five findings formally open. Terminal owners/effects resolved; diagnosis forbids resume/replay. [REQ-D04-003-R1](development/requests/REQ-D04-003-R1.md) preserves21 immutable source identities, original criteria/findings and requires fresh CWI install/check/review using the same approved model. No phase/full-product completion. STATUS remains authoritative for the next action.


## Authenticated operating authority integrated; lifecycle next — 2026-11-02

[REQ-D04-003-R1](development/runs/f14139d7-a856-4b5a-986a-df5014792800.md) finally accepted/exact-integrated27638a93e1658c269ffab68a9cf6c82c10115af8, final receiptc58ce255916cedd3a285a2f7e89123f14c9c6e65f6604f904e7d39af8044de84. Final/target883/883,zero skips/errors/failures/source mutation. Trusted external local credentials,exact immutable decisions/current eligibility/original receipts and backup-policy limits are executable; one repair adds preconstruction retention accounting and7boundary tests. No actual task admission/dispatch or scientific endorsement.

REQ-D04-004 next scopes durable run control and automatic initial/checkpoint/stop reports with pending recovery gates,at most2safe milestones. Later queue/attempt/fencing,atomic reservations,worker isolation and model/tool/context enforcement remain mandatory. STATUS is authoritative for consumed resources and the single next action. All94 requirements and M0-S/live obligations persist.


## Run-control contract recovery — 2026-11-02

REQ-D04-004/e83c7165 stopped before any candidate after prescription blockers consumed2repair slots:missing run_revision type,addendum-only context,then actor/provenance incompatibility. Baseline883/883 passed but no implementation/acceptance/integration exists. Parent/childed010210 and backend1f68060 clean;terminal owners resolved. [Evidence](development/runs/e83c7165-ab29-48f5-8942-581617895c2a.md).

[REQ-D04-004-R1](development/requests/REQ-D04-004-R1.md) freezes a full self-contained contract with existingASCII128 actor semantics and one bounded prepared-control/ordered-obligation milestone. Automatic reporting/restart recovery remains mandatory nextREQ-D04-005,with original13criteria retained;no scope-completion/admission claim. Prescriptions corrected rather than widening old provenance or changing backend/limits. STATUS remains authoritative for resources and the single next action.

## Interrupted control draft preserved — 2026-11-02

[Run d838a2c8](development/runs/d838a2c8-1f87-46d8-8e61-d90f34e9c60d.md) is terminal without candidate validation, review, final acceptance or integration. The orphan Writer completed16files/32newtests; exact source is preserved for [REQ-D04-004-R2](development/requests/REQ-D04-004-R2.md) through supported frozen context. The human authorized one exact final-response permission correction; the original controller then terminated without replay. This is recovery evidence, not delivery of the control foundation.

R2 preserves every original foundation criterion and all13mandatory subsequent REQ-D04-005 report/restart criteria. Automatic reports, pending gates, queue/attempt/fencing/admission, worker/model/tool/context enforcement and scientific/live obligations remain mandatory. D02/D03/D04/M0-E remain partial, M0-S pending. STATUS owns the single next safe action.

## Prepared control integrated; automatic reports and restart evidence next — 2026-11-02

[Run 153bf4bf](development/runs/153bf4bf-e2c8-4c52-aace-e0b8a4ab33b7.md) finally accepted and exactly integrated the prepared-control/ordered-report-obligation foundation. Source `771422b7fcb0b13648c7d4763d50444f358b1de8`, tree `50d73b5dd00d0ed407b21f1b8ec6d5aa7aa0768d`, final receipt `71f34d429ce06530db9b5c27dd066a924785116b11eb62a35e4d479e16b99634`. Final 946/946; integrated target passed 946/946 in 1146.754 seconds, zero skips/errors/failures/source mutation, ending 2026-11-02T20:54:40.836813Z (stdout SHA256 `0af73e8950f6ce1f59051b68cf134487e56610a1fae683b72bc47a9b3e38a243`, empty stderr). All foundation criteria, current-policy transaction checks, original-operation recovery, independent bounds and unchanged ledger/history have evidence. The work gate remains closed.

[REQ-D04-005](development/requests/REQ-D04-005.md) completes all 13 mandatory report-lifecycle criteria through two safe milestones: compatible lifecycle-bound coherent report sources/plans, then automatic publication, independently verified nonrecursive acknowledgment and conservative restart/continuation evidence. Existing formats, immutable receipts, 82 predecessor test/fixture/validator blobs and all pending obligations remain protected. Source commitment, publication and acknowledgment remain separate boundaries. Broader D04/M0-E and all scientific/live obligations remain partial; queue/fencing/admission and enforcement follow. STATUS owns the single next action.

## Reporting decomposition after terminal prescription blockers — 2026-11-03

REQ-D04-005/run7632b4e0 is terminal/nonresumable with no candidate/change/acceptance after two prescription repairs; baseline946/946 alone validates predecessor source. All30retained runs reconcile20finallyaccepted integrated/10terminal incomplete, no live owner/lease/quarantine/pending integration. [ADR-063](development/decisions/ADR-063-lifecycle-report-decomposition.md) supersedes DEV-062's two-milestone delivery decomposition, preserving every original FOLLOWON-01–13. [R1](development/requests/REQ-D04-005-R1.md) first implements independently useful pure bounded binding/codecs; mandatory006source/007plan/008automatic-publication/009restart slices follow actual predecessor evidence. No criterion/phase is complete by planning. D02/D03/D04/M0-E/scientific obligations stay partial; STATUS owns the sole next action.

## Offline binding integrated; source capture ready — 2026-11-03

[Runb4dd25a5](development/runs/b4dd25a5-c915-4e9f-85ea-598b1c6cce13.md) finally accepted/exact-integrated091561b9, final978/978 and target978/9781229.382s, zero skips/errors/failures/source mutation. Pure bounded lifecycle binding/codecs and executed offline guide are delivered; no capture/publication/discharge/current permission or worker admission. All82predecessor blobs/modes remain;86current protected paths. [REQ-D04-006](development/requests/REQ-D04-006.md) prepares coherent committed source capture/original recovery, with rendering/plans/publication/ack/restart still mandatory under ADR-063. Full D04/M0-E/scientific work stays partial. Human revision6 increases continuous allowance to100 without resets;30used70remain, next31leaves69. Earlier50-denominator entries are historical. STATUS owns the sole next action.

## Source correctness recovery — 2026-11-03

REQ-D04-006/f78fa4a9 is terminal without acceptance/integration despite1025passing tests. Resource chronology and an independently confirmed exact-baseline reference defect remain. [REQ-D04-006-R1](development/requests/REQ-D04-006-R1.md) preserves the exact22-path source as compact immutable CWI input and adds only focused correctness repair, all original criteria/checks/reviews and47retained methods. Source capture is not delivered until actual fresh acceptance/integration/target evidence. ADR-063 and all13FOLLOWONcriteria remain; dependent rendering/plans/publication/restart are not ready. Global repairs30/coordinator14 include B-022 source contract correctness1/2, with old exhausted families unchanged. Starts31/100used69remain before next32. Full phases/M0-E/M0-S remain partial; STATUS owns one current next safe action.

## Lifecycle sources integrated; bounded rendering next — 2026-11-03

[REQ-D04-006-R1 evidence](development/runs/7d05376e-aabf-4c5a-9481-91205611eb0c.md). Accepted/integrated `b19e7ffa82b490460225cfc1c0d5100355e2a5d6`, tree `93947f1b2c43dd83ec7e117f5eb759f5af535b2e`, final receipt `d790c2e53c3dda63789ff98604d7c73dc76732c5ff13396a516b971ffeb5640a`. Candidate 1033/1033 in 1730.199s; final 1033/1033 in 1740.418s; integrated target 1033/1033 in 1769.410s, zero skips/errors/failures/source mutation. Target ended 2026-11-03T14:11:07.355675Z, stdout SHA256 `5dee8e19cf18a033f1b07902cf3be7c9bfdcb392235cd079a9a6b4e711b9e5c6`, empty stderr.
B-022 is resolved with its1/2 recovery preserved; all 33 runs reconcile22 finally accepted
sources integrated and11terminal incomplete. No active CWI or pending integration.

[REQ-D04-007-A](development/requests/REQ-D04-007-A.md) is the next bounded shared-rendering request. It extracts
shared seven-group facts/framing while preserving legacy v1/v2 bytes and93 prior
blobs/modes; compact accepted references are frozen for compatibility. ADR-063 splits
007 into pure rendering007-A then authentic output commitment/complete-history plans
and offline recovery007-B. Automatic publication/ack008 and restart/audit009 remain
mandatory; all 13FOLLOWONcriteria persist. Full phases/M0-E/product remain PARTIAL;
scientific/live gates are unchanged. STATUS owns counters and one next action.


## Renderer integrated; human-priority validator optimization — 2026-11-03

REQ-D04-007-A/b7952877 finally accepted/exact-integrated18678728106b3956f83766b5e5a008242ec183ff, tree82b58805c34579d6d8962697382853c868651596, final receipt31f52a0af5006feaa1647da2e4e732eb7d51f950f5a717a48d63dd6236e91c71. Final repair1063/1063 in2102.306s and target1063/1063 in2102.974s passed, source unchanged. Shared detached rendering preserves legacyv1/v2 bytes and distinct-pin/repeated-occurrence bounds; no publication/discharge/admission. [Run evidence](development/runs/b7952877-c4a8-4a38-ab2e-daa9419e60c3.md).

The current human temporarily prioritizes [REQ-DEV-VALIDATION-001](development/requests/REQ-DEV-VALIDATION-001.md), a focused R-007 development-validator improvement through unchanged CWI acceptance/integration. Original sequential baseline2103.466wall seconds,1063unique executions,2073.61user+11.35system CPU,340388KiB maximum resident set. Optimization is prepared, not implemented or measured. After its actual integration/verification/benchmark/documentation checkpoint, stop. Mandatory007-B/008/009 and all94requirements/13FOLLOWONcriteria remain for later; no phase/scientific requirement is changed. STATUS owns counters and one next safe action.
