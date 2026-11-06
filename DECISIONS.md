# Development decisions

## DEV-091 — Preserve the failed baseline and hold the scoped fixture repair

The Source-proposal run5d1adb23 failed the unchanged full baseline before any role ran. Bound evidence identifies an empty PID read; focused inspection of the failing concurrency fixture reveals entry-count readiness before complete PID publication. No product source or backend change, diagnostic rerun, draft adoption or acceptance occurred. Preserve that failure alongside the prior genuine1577/1577 acceptance/target results.

Prepare [REQ-DEV-VALIDATION-002](development/requests/REQ-DEV-VALIDATION-002.md) for reliable fixture readiness with a deterministic publication-window regression, unchanged live-overlap proof and all predecessor/full checks. Do not launch it under the current passing-baseline precondition: REQUEST.md explicitly prohibits an already-failing baseline and BOOTSTRAP is inapplicable. A human decision on one fresh repair start, with the baseline gate still enforced, is the smallest unresolved operating judgment. This is not a self-issued grant amendment or a reason to bypass CWI. B-024 corrective actions0/2; no recovery/limit reset. The Source frozen request remains unchanged and held; STATUS owns the single next safe action.

This index records consequential implementation and workflow choices. D00 decisions recorded after full v1.3 reconciliation; v1.4 dependency amendment explicitly authorized 2026-10-30. Reversible implementation defaults are coordinator choices within the human grant, not invented scientific approvals.

| ID | Proposed choice | Rationale | Confirmation |
| --- | --- | --- | --- |
| DEV-001 | Outer Codex coordinator; all implementation through CWI | Preserves the chosen backend without recursive controller calls | Confirmed by actual human grant |
| DEV-002 | Markdown-only repository root; implementation in `implementation/` | Meets the root layout requirement without disguising configuration files | Confirmed by actual human grant |
| DEV-003 | Ignored nested `coding_pipeline/` clone, not a submodule | Matches the reviewed backend's supported source-launch layout | Verified clean supported direct-child clone; ENVIRONMENT.md |
| DEV-004 | One scoped CWI run at a time; explicit phase boundaries | The backend is sequential and has no public stop-after-milestone command | Confirmed by actual human grant |
| DEV-005 | Root status is a committed checkpoint; live observations are local | Avoids changing the target checkout during validation and merge | Confirmed by actual human grant |
| DEV-006 | Python 3.11+ with stdlib unittest for the first foundation | Minimizes dependencies and allows an independently enforced bootstrap test run | Confirmed coordinator default; specification §§12.2, 14.1 |
| DEV-007 | No CWI automatic merge; first result normally held for human review | Exact-source inspection before coordinator-controlled integration | Human explicitly preauthorized coordinator exact integration; AUTH-2026-10-30-001 |
| DEV-008 | Stable, minimal launch environment | CWI resume requires an exact environment digest | Verified and recorded in ENVIRONMENT.md |
| DEV-009 | Research data/vaults separated from development state | Prevents product investigations from becoming source-control noise or leaking private data | Confirmed by actual human grant |
| DEV-010 | Continuous bounded requests after commissioning, with durable authority | Removes routine prompts without discarding verification or recovery | Activated after successful commissioning integration/validation at AUTH revision 3 checkpoint |
| DEV-011 | Focused direct backend repair exception, separate from product implementation | A faulty backend may need repair without depending on itself | User requested; apply maintenance policy and audit every attempt |
| DEV-012 | Requested Astra 6.1, verified identifier; explicit effort at or below xhigh | Preserves requested selection without inventing model availability | Human corrected to gpt-6-astra; explicit medium for foundation; max xhigh |
| DEV-013 | Session continuation is separate from an external supervisor | Avoids claiming that Markdown automatically restarts Codex | No supervisor implemented by this update |

For a substantial decision, create a detailed record under [development/decisions/](development/decisions/README.md) using the [template](development/templates/DECISION.md). Include alternatives, consequences, evidence, and revisit conditions. Do not record a proposed default as an approved decision without an actual decision event.

A product-requirement change additionally needs an explicit, reviewed change to `project_description.md`; this index alone cannot authorize it.

Workflow rationale: [ADR-010](development/decisions/ADR-010-continuous-development.md). Preserve earlier decisions and actual approvals when adopting this update; a proposed entry cannot supersede a human decision by itself.

## Reconciliation decisions — 2026-10-30

- DEV-014: Preserve specification M0 timing by adding the scientific-contract gate to D01 before D02. D10 runs the already approved pilot/protocol; it does not first choose them after implementation. The authorized foundation request remains independent of scientific choices.
- DEV-015: Move minimum deterministic end-of-run reporting and model-limit/resource contracts into D04/M2. D09 builds richer synthesis and portable export.
- DEV-016: Preserve actual backend `1f68060` unchanged. Its two prompt-resource differences from reviewed `122f865` were inspected, including Architect-like wording in Designer; rely on frozen role schemas and inspect actual commissioning evidence. No diagnosed malfunction warrants a patch.
- DEV-017: Use installed Git 2.40.1 via fixed launch PATH because system 2.34.1 lacks required worktree porcelain -z. No environment installation or live-run change occurred.

- DEV-018: Use explicit workflow-local `Codex Development Coordinator <codex@localhost>` author/committer variables because Git identity is unconfigured. Attribute agent-generated commits honestly; do not copy the human author from old history or change global Git settings.

- DEV-019: Record the human's “create your mock for this example” as authority for a synthetic harmonic/quartic development fixture. Keep mock provenance distinct from expert reference judgments and actual execution. M0 remains incomplete; no mandatory scientific gate is waived.
- DEV-020: Commissioning used one start with no repairs. Inspected final receipt and exact accepted source, then fast-forwarded before the administrative activation commit. Use the permanent validator for every subsequent request; the original bootstrap exemption is retired.

- DEV-021: After REQ-D01-002's inspected exact integration and 28/28 target validation, hold dependent D02 work at the original M0→M1 scientific gate. The human's requested mock is fully delivered as synthetic material; it is not an expert audit or authorization to replace mandatory scientific reference judgments. The M0 packet makes remaining human decisions concrete. This is a defined stopping condition under the still-valid continuous grant, not a routine phase-boundary permission request or a completed project.

## Version 1.4 dependency amendment — current authority

- DEV-022 supersedes the blanket engineering prerequisite in DEV-014/DEV-021, preserving their historical rationale/evidence. Human explicitly separates M0-E engineering readiness from pending M0-S scientific validation. The old combined M0 and R-001–R-003 stay incomplete. Genuine scientific design dependencies still block their affected slice; no empirical threshold may be set after seeing scored/held-out outcomes.
- DEV-023: Settle the next M0-E storage contract in the M0 packet and REQ-D02-001: Python stdlib SQLite, content-addressed immutable bytes, typed exact record/artifact references, append-only revisions, explicit expected heads, idempotent transactional submissions and events, controller-only local API. This is a reversible technical choice within the amended specification, not pilot selection. Executable evidence remains pending until CWI acceptance/integration.
- DEV-024: Preserve all v1.3 historical receipts/requests/fixture hashes. New requests cite v1.4; the oscillator's original source identity remains v1.3. Do not rewrite scientific provenance when dependencies change.
- DEV-025: Select explicit gpt-6-astra/high for D02-001 because atomicity, corruption and authority boundaries need deeper review. This changes effort only for the new run, never a frozen run; all original limits persist.

## DEV-026 — Consistent backup/restoration next

After REQ-D02-001 accepted/integrated local version-1 SQLite storage, commission a self-contained consistent metadata/artifact backup and verified restore before broader runtime use. This is ready independent R-019/R-017 engineering and tests real recoverability; full scientific record semantics/eligibility remain subsequent D02 obligations. Use one bounded high-effort CWI milestone, stdlib SQLite/filesystem, no new provider/data/service authority. Preserve all source/receipt identities; no migration is invented merely to claim one exists.

## DEV-027 — Typed scientific content without reinterpreting history

After accepted local storage and backup, implement four provisional scientific payloads and exact typed admission using the existing immutable version-1 database. A content discriminator separates typed records from legacy generic envelopes; no silent migration or competing graph is allowed. Required assumptions are local named statements bound to exact revisions, while assessed sufficiency and authentic tool execution remain separate future authority. Preserve provisional cycles and keep alternate routes separate; no scientific judgment is inferred from structural validity. REQ-D02-003 records the concrete contract and failure/compatibility evidence. High effort remains appropriate for provenance, exact references and idempotency.

## DEV-028 — Explicit schema evolution with preserved v1 restoration

REQ-D02-004 introduces schema 2 for all twenty generic §5.1 envelope identities and an explicit v1-backup-to-new-v2-runtime migration. Preserve v1 read/old-kind append/retry/backup and exact default restoration; never migrate a live source in place or rewrite original receipt provenance. New generic kinds confer no authority and retain null canonical state until their concrete typed/state contracts are implemented. Use strict version-specific schema/backup gates, separate migration attribution and the existing incomplete-restore publication boundary. This is a reversible technical dependency for remaining records/assessments, not scientific approval; high effort is appropriate.

## DEV-029 — Preserve controller validation ownership after observed sandbox mismatch

Run 9af6f133 passed the exact 116-test controller baseline but stopped when its Writer independently encountered literal-/tmp denial and the Architect treated that as the missing baseline. Preserve the stopped nonresumable run and its actual passing baseline. REQ-D02-004-R1 clarifies that meaningful acceptance checks remain controller-owned, while Writer-local runs must report narrower-sandbox limitations honestly. No tests/validator/security/environment/backend change is authorized as the correction. A new bounded run after clean terminal disposition is recovery action 1, not a blind resume or waived gate.

## DEV-030 — Attributed reports before current assessment authority

REQ-D02-005 consumes schema-2 review/issue identities and existing scientific typed admission to persist independent dimensions, disagreements and explicit route judgments. A separate versioned assessment-content discriminator preserves old codecs. Reported sufficiency/independence/execution are declarations, not approval or current disposition. Exact route-conclusion membership is a mechanical admission check; differing contexts remain expressible. Current eligibility generation/invalidation and authorized promotion are subsequent work. This is reversible domain-independent record engineering, not a scientific pilot or sufficiency decision.

## DEV-031 — Human deadline extension and preserved-draft recovery

After run 46114120 timed out at its frozen 900-second Writer deadline, the human explicitly set CWI time limits to 2,700 seconds. AUTH revision 5 applies that per-agent/per-validation ceiling to new runs, without changing model/effort/start/repair/billing or acceptance limits. Preserve the terminal unaccepted draft and freeze its exact files through supported --context for REQ-D02-005-R1; only its delegated Writer may implement them in its new worktree. Full product scope and gates stay unchanged. This is one diagnosed deadline recovery, not a backend repair, silent resume or direct product transplant. Unknown timed-out Writer usage remains a liability.

## DEV-032 — Work-product/draft infrastructure as the next independent slice

After attributed Review/Issue records are accepted/integrated, implement real multi-file work-product manifests and a safe checkout → preview → explicit atomic submission round trip in REQ-D02-006. This consumes established storage/reference/backup contracts and enables D03 authoring without waiting for unrelated scientific acceptance or current eligibility. Keep those mandatory obligations visible. Use inert copied bytes, portable logical paths, canonical exact bases, bounded capture, detached saved proposals, explicit expected heads and preserved edits; descriptor text does not grant authority. Separate preview/orphan publication from canonical commit so lost acknowledgment reconciles the original proposal instead of rereading mutable files. High effort, at most three milestones and human-authorized 2700-second deadlines. No schema/provider/security/approval expansion; detailed TeX/checkpoint/closeout semantics remain later work.

## DEV-033 — Preserve sources before seeded intake and readable views

REQ-D03-001 will consume evidenced storage/authoring contracts for versioned Source records and a bounded explicit local capture/proposal/commit path. Keep upstream version, local capture revision and reading-report revision separate. Preserve originals, exact extraction lineage and locators, reported partial coverage, unknown attribution and access/reuse/processing declarations; bytes or metadata never certify scientific reading, reproduction or permission. No network/parser/archive execution or readiness transition is commissioned. This is a concrete independent D03 prerequisite, while D02 eligibility/authority and M0-S remain mandatory pending work. Reuse proven filesystem/admission primitives where appropriate, with high effort and at most two milestones under unchanged2700-second deadlines; no authority expansion.

## DEV-034 — Immutable corpus baseline before project readiness

After exact Source integration and 343/343 target validation, REQ-D03-002 commissions one strict corpus-manifest feature over exact Source originals, unresolved inventory, original path/link mappings and attributed inspection. A complete intake/readiness/vault feature would combine separate authority and publication contracts too early; a generic JSON inventory would fail the required identity/reference checks. Choose the existing schema-2 typed/submission boundary with one meaningful milestone, preserving initial history through later changes. Project setup/readiness and generated views follow separately; current inventory never admits research. High effort, one milestone, existing 2700-second deadlines and limits. This is the coordinator's reversible engineering choice under the human grant.

## DEV-035 — Explicit process descriptor prerequisite

REQ-D03-001 retains selected file handles through final integrity checks. The 1024-file maximum-boundary test cannot fit the current inherited soft RLIMIT_NOFILE=1024 plus directory/database/stream handles. Exact isolated reproduction failed at 1024 and passed unchanged at 4096; the full target then passed 343/343. Set soft=4096 within the existing hard=1048576 for new CWI/validation processes, record it outside the unchanged environment map, and preserve it during any future run. Do not alter a live process/frozen run, host-wide setting or test. Historical controller limits are unknown. This is one diagnosed environment recovery, not a backend defect or an acceptance waiver.

## DEV-036 — Preserve exact acceptance while recording one cosmetic diagnostic

For REQ-D03-002, git diff --check reported only one terminal empty line in test_corpus.py:471. Exact-source hash and identical AST establish a formatting-only observation. Exercise the existing ordinary technical/review authority to record it as nonblocking while preserving accepted 7d6dd6246e47ace09ff44a1decef14c93251f0ac; the integration guard permits only that exact diagnostic/hash and rejects any other error. No configured CWI criterion/test, Git configuration, source/security/ownership/integrity gate changed. This is a narrow documented interpretation of the runbook formatting check, not general authority to ignore failed checks. Delegate removal through REQ-D03-003; require complete base-to-candidate diff checking, including new files.

## DEV-037 — Project/intake dossier before readable vault generation

After accepted corpus history, give setup an explicit project identity, original/current corpus pins, a source-linked brief and authored intake report. A proposed-readiness judgment remains attributed data; actual ready state and task admission require the later authorized controller contract. This supplies coherent project context to vault views without prematurely implementing a policy/queue/resource system. Unknowns, partial inspection and contradictory materials remain usable setup data. Add explicit brief/report work-product labels only through the bounded CWI request, preserving existing meanings. No scientific sufficiency, direction approval or operating grant is inferred from saving records.

## DEV-038 — Consistent immutable reading snapshots before refresh

After exact project/intake integration, commission REQ-D03-004 with at most two independently acceptable milestones: consistent bounded detached metadata plus a deterministic readable plan, then protected copies/private generation/exclusive complete publication and inspection. A current-head selection must use one read snapshot, not separate transactions. This creates a useful private offline reading view without inventing policy, run or branch semantics. Explicit scope, exact revisions/hashes and truthful missing information remain visible. Existing destinations are refused intact; mutable refresh/pointers and human-edit import follow separately. This ordering isolates snapshot/publication failures from later replacement behavior and preserves original objects/drafts. The view grants neither support nor operating authority and is not an externally shareable export. Same model/high effort and2700-second deadlines; no scientific/live approval inferred.

## DEV-039 — Freeze every required check and reuse preserved CWI drafts

REQ-D03-004's first milestone passed432/432 after one syntax repair, but the reviewer stopped because complete base-to-candidate formatting evidence was not in the frozen controller profile. Coordinator inspection cannot substitute for a required bound result. The run is terminal, unaccepted and preserved. Use existing repeated --check support in a fresh run: unchanged permanent validator plus `git diff --check ACTUAL_NEW_LAUNCH_BASE HEAD --`, supplying the literal committed base SHA. This captures new files and all cumulative changes at baseline/candidates/final without changing the validator, backend or historical evidence. No guard/criterion is waived.

Preserve exact CWI-authored candidate81ec2f3 as frozen --context reference data; the new delegated Writer alone reuses and reviews it in its own worktree. Do not transplant unaccepted source into main or restart the completed Source/corpus/project work. New REQ-D03-004-R1 retains both bounded snapshot milestones, model/high effort,2700-second limits and all scope/safety boundaries. This is recovery1 for a distinct validation-profile omission, with one further evidence-based action available; cumulative counters persist.

## DEV-040 — Publish protected generations within one parent and preserve operational errors

REQ-D03-004-R1's first publication candidate failed real controller tests at renameat2: moving an already 0500 directory between parents requires write permission to change its parent entry. The [Linux rename manual](https://man7.org/linux/man-pages/man2/rename.2.html) documents that permission requirement. The observed failure was a product staging-layout defect, not a backend defect or authority to elevate the operation. CWI repaired it by reserving a separate 0700 evidence directory and sibling payload under the same held destination parent, then exclusively renaming the complete 0500/0400 payload within that parent. This preserves read-only visibility and no-replace semantics without a temporary writable published window. Explicit pairing, held descriptors and retained interruption/acknowledgment evidence prevent blind replay or adoption.

The same Writer repair separated observed binding changes from genuine I/O/resource failures during final inspection: ordinary edits/replacements report divergence, while operational errors retain their cause and fail explicitly. Real mode-at-publication, reservation, competing-publisher, replacement, process/fault and stat/fstat tests support the contract. Final acceptance/integration at c57a621c3e3f7806030de13b75b4fe2890b81cc7, 489/489 target tests; [run evidence](development/runs/7ee32819-ee00-4b1b-bdba-ea26fb90cf3e.md). Existing destinations remain untouched; no refresh/import, authority, scientific approval or host/security/backend change is inferred.

## DEV-041 — Preserve edits through immutable successor refresh

REQ-D03-005 uses the accepted snapshot, exclusive publication and draft/import contracts to compare a pinned prior view, preserve divergent bytes/path identities as unsubmitted proposed work and publish a complete successor. Historical view and canonical revision paths remain untouched. In-place multi-file replacement would complicate consistent readers and editor conflicts; a mutable current-pointer manager adds a separate lifecycle. The successor API is the bounded reversible choice, with exact association/recovery evidence and an explicit import route. Unambiguous renames retain identities; duplicate or edited-rename ambiguity is diagnosed rather than guessed. Generated links are checked; arbitrary authored links are not silently certified or rewritten. High effort and at most two milestones address filesystem/recovery risks. This is coordinator engineering judgment under existing authority, not a scientific decision or completion of full vault/CLI behavior.

## DEV-042 — Bound complete refresh evidence at final observation gates

REQ-D03-005 review required independent outer/nested budgets before payload reads, actual divergent control-byte accounting, strict fixed-control semantics for incomplete output, and stable file/directory observations after hashing at inspection and publication gates. External ancestor identity checks exclude unrelated sibling mtime activity. This avoids both false conflicts and falsely complete evidence while preserving exact retained work. Same-owner/privileged mutation and post-observation intervals remain explicit limitations; current file presence cannot prove historical fsync acknowledgment. All changes were implemented by CWI Writer and accepted at 8cfb035, with 579/579 target tests. No backend or scientific-authority change.

## DEV-043 — Expose a narrow explicit CLI authoring path before research execution

REQ-D03-006 makes accepted exact inspection and work-product checkout/preview/saved-proposal/submit contracts usable without Python calls. Preparation and durable human-reviewable saved bytes remain separate from explicit typed CAS submission; original-ID receipt lookup and exact retry reconcile lost acknowledgment. Strict bounded inert controls and trusted local paths preserve source/runtime protections. The command spelling and publication details belong to the delegated Architect within this bounded request. Missing stores are not implicitly created, arbitrary canonical writes and runtime execution remain unavailable, and authored metadata grants no scientific or operating authority. Two milestones/high effort are chosen for output/durability/recovery risks. Full R-082 command coverage and D04 authority remain mandatory later work; no scientific prerequisite is bypassed.

## DEV-044 — Keep saved proposals and uncertain acknowledgments explicit

REQ-D03-006 accepted0a875dd stores exact typed proposal bytes, recomputed meaningful summary and binding manifest before a separate explicit submit. A private incomplete marker, durable complete checks and final marker removal define publication; file presence cannot prove historical acknowledgment. Original submission identity remains the reconciliation key after commit/output loss. Observed directory or saved-leaf disappearance is a conflict; genuine I/O errors remain operational, and failures after effects remain uncertain. Real regression/CLI tests and657/657 target validation support this distinction. No generic canonical-write, scientific-authority or auto-retry route was added.

## DEV-045 — Expose existing views with an independent historical baseline

REQ-D03-007 is the next bounded R-082 slice: initial immutable views, preserved successor refresh and offline inspection through established APIs. Require separately retained complete historical manifest bytes outside mutable prior/output trees; the edited prior manifest must remain opaque divergence evidence. Reconstruct historical formats under independent limits, including accepted69-level canonical wrappers, while authored CLI controls keep their own bounds. Return exact resolved pins/recovery paths and reuse existing publication protocols. One coherent milestone/high effort fits this adapter boundary. D04 resource/authority/minimum-closeout contracts follow independently; no run admission is commissioned before those prerequisites. Full vault/CLI/scientific duties remain required.

## DEV-046 — Preserve exact accepted work and repair the remaining observed-directory diagnostic

REQ-D03-007 / CWI c9055f4c-f63c-4815-ab5e-670116ce1333 finally accepted and exact-integrated 2643673035b5be43c3f12cbab1567dcce3377aa6, final receipt 8372ac488fa8f0b3989e7fa637f34c97174b0d0eb2d8724868f67dbcffc3d67f. Four source-local commands expose immutable generation, independently pinned preserved refresh and offline inspection. Final controller696/696 in451.094s; integrated target696/696 in451.163s, zero skips/errors/failures/source mutation, completed2026-11-01T00:11:17.402942+00:00, stdoutSHA256ba0d147f67885b616e725a45e89fc51b68b4ad92923174d43a727168f3b64f94 and empty stderr. Two internal repairs resolved F001–F004;39 new tests preserve657 baseline tests and the permanent validator. No backend/authority change.

The coordinator's independent real CLI probe found one additional fail-closed classification defect: selected-view root loss after real inspection returns remains unsafe_layout5 instead of integrity_error6. Exact source/receipt/check/ownership/base/collision/hook gates all pass, so the existing continuous grant permits exact development integration while retaining B-017 and immediately commissioning the smallest compatible product repair. No error is treated as correct, test waived, receipt changed or completion/release claimed. Preserve accepted2643673; never discard, transplant or recreate it to bypass integration. The CWI Writer alone fixes readable adapter observation boundaries; initial absence, saved-package conflicts, true I/O and publication uncertainty keep distinct contracts. One milestone/high effort and unchanged2700-second deadlines are proportionate. D04 accounting remains next after this repair, with admission prerequisites still open.

## DEV-047 — Close observed-directory diagnostics with exact-source evidence — 2026-11-01

REQ-D03-008 / CWI 4c1833ef-8ef9-4b07-9f33-79acb6f7e8b0 finally accepted and exact-integrated `3f4564c770bdec8848587ad6052a8f2c6bdb75de`, tree `204b5eb30e5309bd23839bd58d0afb2e00b2d082`, final receipt `80ad5251c81e2a26c32e7528c58cdc41d38f93ef0a4247a1e00487c1f265df94`. Final controller 707/707 in 475.208s; Integrated target 707/707 in 476.667s, zero skips/errors/failures and unchanged clean source; completed 2026-11-01T01:20:15.956694+00:00, stdout SHA-256 `8479e46b433fb6d6c318fd9256b0cd365c79d76e9beac27a192ec8bb4f58a077`, empty stderr. One internal test repair resolved F-001/F-002. All 696 predecessor tests and the permanent validator are preserved. Observed directory loss/replacement now reports integrity_error after observation, including missing-child traversal after earlier ancestor loss. Initial absence/layout and actual I/O/checked-close/collision/publication-uncertainty precedence remain distinct. The independent real inspector-then-root-rename probe returns exit6/integrity_error with no stdout and exact retained bytes/modes/inodes/canonical objects/history preserved. Production bytes are unchanged between that probed initial candidate and the final test-only repair. Full actual CLI mutation matrices and published/unpublished recovery identities pass. The actual first controller candidate failed on new fixture permissions and unpublished-generation identity assertions; its one CWI repair changed tests only and retained all production guards. The coordinator did not implement product code or alter accepted source. Exact fast-forward occurred2026-11-01T01:12:14.740398Z after all recorded gates; historical CWI state remains ACCEPTED_UNMERGED. No scientific/overall completion claim.

## DEV-048 — Resource accounting before controlled admission — 2026-11-01

Choose a bounded durable ledger in the same canonical SQLite metadata, as required by original§9.1. Explicit opt-in schema3 and verified2→3 backup migration preserve defaultschema2 and historical1→2 behavior, exact scientific rows/receipts/artifacts and ordered provenance. Hierarchical protected verification/handoff/local-closeout reservations fit one ceiling; uncertainty retains liability, original IDs prevent duplicate charges, and authentic overrun receipts persist with blocked further admission. Two independently useful milestones limit scope. The Architect fixes exact APIs/invariants before its Writer implements. This choice avoids inventing authority in arbitrary scientific payloads or splitting transactional accounting into another database. Ledger declarations supply neither authenticated grants nor enforceable external service bounds. Actual readiness/fencing/dispatch/context and mandatory no-model reporting remain required before research admission. M0-S remains independent and pending; no new budget or provider authorization.

## DEV-049 — Derive only provable cumulative invocation breaches — 2026-11-01

Final review of REQ-D04-001 found cumulative receipts can prove excess without per-call samples. Acceptedb13fff0 uses the current receipt's positive observed call count, retained known totals and actual reservation/run bounds for sufficient inequalities; no fabricated peak or stale-count inference. Sample and first-trigger diagnostics stay stable; evidence persists while new project admissions stop. Shared replay validates live/reopened/restored histories, including exact products above single-input bounds. CWI Architect/Writer implemented the repair, with independent reproduction and review.

## DEV-050 — Minimum reporting before admitted execution — 2026-11-01

Reuse scientific SQLite/artifact/work-product and protected-view mechanisms for deterministic reports. Capture exact scientific/resource state coherently once, persist attributed interpretation and saved continuation, then render/publish immutable dated revisions without a model, tool or new inference. Preserve old formats and original retry identities. No new schema is presumed; Architect fixes minimal compatible contracts. Generic run records/readiness proposals/resource accounts cannot authenticate admission/termination. Automatic initial/checkpoint/stop and pending-report-before-restart hooks remain mandatory before admitted research. Two milestones/high effort address capture, commits and filesystem recovery; no scientific/authority change.


## DEV-051 — Preserve cancelled report candidate without implying acceptance — 2026-11-01

The human explicitly requested immediate resource-conserving shutdown. Existing controller SIGTERM handling safely cancelled the read-only Reviewer; independent host checks establish process exit. CWI retains STOPPED_INCOMPLETE and pending_authoritative_operation, with resume disallowed. Preserve2e4343890e51, its passing validation and all frozen artifacts; do not manufacture a review verdict or replay the turn. A future CWI-only replacement may salvage the exact draft after reconciliation. Terminal owner-free state permits an administrative shutdown checkpoint, while product refs, controller state and old worktrees stay untouched. Future CONTINUOUS authorization is not revoked; this session must not restart.

## DEV-052 — Resume by fresh CWI acceptance of preserved report work — 2026-11-02

The human resumed continuous development under existing limits. Fresh evidence confirms terminal nonresumable 6ae8ca11 and no host owner, lease, quarantine or pending accepted integration. Choose a bounded REQ-D04-002-R1 using supported frozen --context with byte-exact candidate 2e4343890e51; only the new CWI Writer implements it in its assigned worktree. Resuming the cancelled turn is forbidden, integrating the draft would bypass acceptance, and recreating its sound capture implementation would waste completed work. A fresh two-milestone run retains all original criteria, completes pending immutable publication/navigation and adds persistent post-settlement late-usage reporting coverage. Reuse established SQLite/artifact/view contracts, with high effort for transactional/publication recovery. No backend change or scope expansion. This consumes one recovery for the cancelled-reviewer salvage condition (five cumulative), and its eventual start counts 21/50. Scientific/live obligations remain pending; further independent engineering follows successful integration.

## DEV-053 — Reuse terminal report draft within the final deadline-recovery allowance

Run d343c0af accepted capture atadb1b439 but publication Writer exhausted2700 seconds, including repeated full advisory tests with known sandbox limitations. No final acceptance or integration; owners/lease/quarantine resolved. Choose one fresh bounded CWI milestone to reuse26 exact intended files, complete original criteria and fix the independently reproduced caller-metadata preflight violation. Exclude257 generated scratch/log paths from reference while leaving the old index/worktree intact. Preserve all tests/security guards, v1 identities and late-usage reporting; controller full checks/review/final receipt remain required. Use targeted advisory tests and keep diagnostics outside product paths. This is recovery2/2 for Writer deadlines, cumulative6; no increased time limit, backend repair, silent reset or scope/authority change. A further same-blocker failure requires escalation.

## DEV-054 — Freeze source identities instead of duplicating source bodies in review context

R2 candidatebdcbd679 passed845/845 and all formatting checks, but the complete Reviewer prompt exceeded the existing1MiB limit. All intended source already exists as immutable local Git objects. Choose supported frozen context containing exact commit/tree/per-path blob/mode/length/SHA256 identities and instructions to inspect/install only those objects from the new assigned worktree. No mutable branch-tip/original-working-file reads, ref mutation or coordinator product copying. The complete current diff and validation evidence still enter review. Read-only unchanged composer measures595,915 bytes; no mandatory evidence truncation or backend guard increase. This consumes context-size recovery1/2, cumulative7; prior deadline2/2 remains exhausted. Fresh acceptance is still required, and all original scope/tests remain.


## DEV-055 — Authenticate operator decisions before admission

REQ-D04-003 introduces a separately configured local HMAC-SHA256 operator credential boundary. Existing generic decision records and actor strings are descriptive; a typed label or approved boolean cannot authenticate permission. Domain-separated complete canonical signatures, constant-time verification and trusted principal/project/capability configuration provide the smallest concrete stdlib boundary for the single trusted controller. Keys remain outside canonical records, task data, artifacts and backups; no service, PKI or key-management subsystem is introduced. This proves configured credential possession, not legal identity, scientific correctness or hostile same-process isolation.

Bind the complete scope and exact project/corpus/brief/context/intake evidence, use one unambiguous current decision stream, and preserve denial/revocation/history. Original receipts survive expiry/revocation but cannot establish current permission. Revocation remains possible despite unavailable old artifacts. Current policy is external trusted input after restore; old backups cannot reveal later missing revocations, and restart reconciliation remains mandatory. Later task admission must recheck authority, resources, dependencies and report gates inside its own transaction. One milestone/high effort is bounded to this foundation; no worker execution, resource reset or scientific approval is commissioned.


## DEV-056 — Recover a nonreplayable capacity-failed review through fresh CWI acceptance

The authority candidate passed876/876 and formatting after two bounded repairs, but provider capacity interrupted the persistent Reviewer before verdict. Follow explicit nonresumable diagnosis: preserve all old state/source/usage and prove terminal host owners/local effects. A new one-milestone CWI workflow installs the exact21 immutable Git-object files using supported compact context; all original criteria and F001–F005 remain binding. This is external service capacity recovery1/2, not review shopping, deadline recovery, model substitution or a backend defect. New workflow preparation and full baseline provide natural backoff without replaying the uncertain turn. No test success or candidate identity supplies acceptance; fresh milestone/final review and exact integration gates remain. Coordinator recoveries8; all historical budgets/liabilities persist.


## DEV-057 — Separate durable run/report obligations from publication and later task admission

After actual authority integration, choose bounded REQ-D04-004 for typed run-control history and automatic initial/checkpoint/stop report lifecycle,at most2 independently safe milestones. Persist the small control transition and report obligation transactionally; capture,immutable artifact placement,publication and acknowledgment have explicit separate recovery phases. No filesystem/SQLite atomic-publication claim or recursive report-on-ack loop. Reconcile original operations first: an already committed source/plan is immutable; a first capture delayed by unavailable storage has its actual later watermark and any gap stated visibly. Pending required reports close the future ordinary-work gate,while offline deterministic recovery remains usable without models.

Prepared control/report state does not admit or dispatch scientific workers. Reuse current trusted authority/resource/report primitives with narrow connection-taking extractions; future queue/admission still rechecks current authority,report gates,dependencies,resource reservations and remaining isolation/context/tool checks in its own write transaction. Preserve run/allocation histories; no resource reset or scientific promotion. This advances a useful coherent lifecycle slice without claiming full D04/M0-E,provider compatibility or M0-S. Exact contracts/transition table remain the delegated Architect's prescription.


## DEV-058 — Freeze a complete compatible control contract and split lifecycle delivery

Original two-milestone run failed before implementation because prescriptions were incomplete or incompatible with immutable provenance. Preserve all role outcomes and2consumed internal repair slots. The existing actor contract is the correct constraint:1–128ASCII identifier characters,with arbitrary authored narrative remaining separately typed. Correct the new control actor declaration,not domain/provenance/old tests. No backend modification is warranted;complete-prescription policy and Writer blockers worked.

Freeze the entire latest Architect blueprint plus explicit actor correction/new-base validation binding in supported context so stateless replacement roles always receive every contract. Fresh Architect must adopt a complete compatible prescription;an unavailable prior response cannot be a dependency. Scope the next run to the safe prepared-control/ordered-report-intent foundation,one milestone. Keep the original automatic-report/publication/restart recovery13criteria as mandatory nextREQ-D04-005. No ordinary-work gate opens and no scientific admission/fullD04 claim is added. This localized decomposition limits another Writer workload without dropping requirements or increasing deadlines/repair caps. It consumes prescription completeness/compatibility coordinator recovery1/2,cumulative9;all prior counters and unknown liabilities persist.

## DEV-059 — Preserve a completed orphan draft through explicit fresh acceptance

A fresh session proved the prior controller absent and its assigned Writer alive. Preserve the frozen parent, allow natural completion and verify all descendants before supported recovery. The orphan's response0664 made the unchanged private-file guard reject recovery; an exact human-authorized one-file0664→0600 exception preserved bytes/inode/owner. Original CWI then stopped nonresumably without replay, validation or adoption. Preserve its observational gaps rather than manufacturing complete logs or receipts.

Use R2's exact frozen patch/full-file hashes, complete corrected contract and entire retained Architect prescription so its new Writer installs/reviews the existing work instead of recreating it. Fresh full checks, milestone/final review and exact integration remain mandatory. This is the final interrupted-workflow salvage2/2; the distinct permission blocker consumed2/2, overall coordinator recoveries12. No reset of exhausted deadlines or other budgets. All automatic-report/restart follow-ons and broader mandatory scope persist.

## DEV-060 — Secure child output before supervision can disappear

CP-001's narrow backend candidate prepares the final-response file exclusively0600 before Popen, with empty/missing output still unsuccessful and the unchanged privacy guard. Pinned Codex0.166.0/b8a11fed loopback-only fixture proved in-place writes preserve that inode/mode; no external model/credentials were used. Independent backend review closed substantive conditions. The explicit tradeoff is conservative loss of automatic interrupted-call retry throughout the pre-response lifetime, because an empty prepared file requires explicit adoption. This grants no acceptance or unsafe replay. Global umask and evidence-safety guards remain unchanged; old runs never silently resume under patched code. Final validation/commit/adoption is recorded in the backend audit.

## DEV-061 — Reconcile an existing final acceptance before starting lifecycle reporting

Fresh-session inspection found the original controller and final Reviewer still alive. Preserve the frozen parent and observe that owner. After natural final acceptance, rehash receipt/review/check artifacts, match the complete previously reviewed diff and all predecessor blobs/modes, verify no live owner and exact fast-forward conditions, then integrate only the accepted commit. No replay, new start, backend change or tracked pre-merge checkpoint is needed. Record final eight-turn usage once; the previous seven-turn snapshot was provisional. This is normal completion of the existing run and consumes no coordinator recovery.

## DEV-062 — Complete automatic reports through compatible binding and verified acknowledgment

REQ-D04-005 retains all 13 original follow-on criteria and two independently safe milestones. Reuse the existing report capture, deterministic renderer and protected publication/recovery algorithms behind an explicit compatible lifecycle binding. Reinterpreting historical ReportRequest v1 would conflict with its baseline grammar; a parallel renderer/publication stack would duplicate recovery behavior. The CWI Architect owns exact versions, signatures and preconstruction limits before Writer implementation.

First commit a coherent report source/plan while pending intent remains truthful; then drive automatic lifecycle publication and separately verified nonrecursive acknowledgment. Original historical control results remain immutable pending-capture facts, while explicit new inspection evidence can report later discharge. An earlier acknowledgment cannot override a later cancellation. Restart/continuation rechecks current supplied policy, dependencies, pending obligations and resource/liability evidence, keeps unsupported owner/job facts unknown, and grants no worker admission. Preserve all 82 predecessor test/fixture/validator blobs/modes. High effort, two milestones and unchanged limits address transactional and filesystem recovery without broadening scope or scientific authority.

## DEV-063 — Narrow lifecycle reporting after coupled prescription failures

[ADR-063](development/decisions/ADR-063-lifecycle-report-decomposition.md) records actual terminal7632b4e0 evidence, alternatives and independent pure-binding/source/plan/publication/restart decomposition. R1 earns only executable structural binding; all13original criteria and historical formats remain. Complete standalone prescriptions, independent caller limits and structural-versus-persisted trust boundaries are explicit. This coordinator choice uses the final prescription recovery2/2, cumulative13, with no backend/limit/scientific change.

## DEV-064 — Actual human raises continuous CWI starts50→100

The human explicitly requested100uses throughoutsettings. AUTHrevision6 records the actual quote and effective100-start allowance; consumed30starts remain30, leaving70. Active autonomy/startup settings and current counters/newrequests use100. Old frozen requests/receipts/historical denominators remain factual. Backend has no aggregate-start configuration flag; its other limits stay unchanged. No API/purchase/live/scientific/integration/recovery authority is expanded.

## DEV-065 — Commit source facts before rendering and publication

R1finallyaccepted/integrated091561b9 supplies exact offline structural bindings, not authenticity. REQ-D04-006 consumes them with actual persisted ownership/history and coherent scientific/resource capture in the shared connection. Legacy report commit couples rendering/two-record membership and earlier-report baseline grammar; it cannot be reused unchanged as a source-only commit. Architect must prescribe a compatible durable source-stage identity/receipt protocol that later outputs can consume without rewriting originals, minimal shared capture/budget extraction, and complete independent preallocation tests. Rendering/plans/publication/ack/restart remain later ADR-063 slices. One milestone/high effort and unchanged2700s/repair bounds keep scope concrete; no parallel ledger/renderer or invented permission.

## DEV-066 — Repair retained source invariants through fresh CWI acceptance

Original006is safely terminal/nonresumable after two internal repairs, with1025passes but no accepted milestone/final receipt/integration. Independent review and actual disposable-store probes establish resource-date chronology and redundant baseline scalar defects. Choose a compact immutable-source recovery with those two focused corrections, preserving all sound code and full original acceptance, rather than reauthoring the feature. Resume is prohibited; integrating provisional code and direct coordinator product patches are unavailable. No backend defect or larger guard/budget is established.

[REQ-D04-006-R1](development/requests/REQ-D04-006-R1.md) uses source1f9c243c/tree947d3b7e and exact22-path identities; only its Writer installs21complete blobs plus original README navigation while preserving the current administrative maturity paragraph. B-022 source contract correctness1/2 is conservatively counted as coordinator14, distinct from completed-role-context/ownership/deadline failures and with no reset of exhausted families. All original source guarantees,47new methods,86accepted predecessor paths and13follow-on criteria remain. Dependent renderer/plans/publication/restart wait for actual corrected source evidence; scientific/live judgments stay separate.

## DEV-067 — Share pure rendering before durable output plans

Corrected lifecycle sources are finally accepted, exact integrated and target-validated
at b19e7ffa; no source failure or backend issue requires recovery. The coordinator
selects two independently reviewable parts of ADR-063's007boundary: pure bounded
shared rendering007-A, then authenticated separate O/X/M output commitment, complete
history plans and offline reconstruction007-B. One combined request couples output
projection, metadata recovery and plan accounting; the split costs another full CWI
cycle but keeps each contract useful and assessable. This is an ordinary engineering
choice under existing authority, not a new human approval or recovery allowance.

Reuse actual shared fact projection and inert framing; fabricated legacy observations
conflict with saved-work baseline semantics and duplicate renderers are excluded.
Freeze accepted v1/v2 source/output hashes before extraction, preserve93 predecessor
paths and require exact-byte compatibility. New lifecycle output is detached generated
bytes, without publication/authenticity/current permission. Architect must prescribe
complete APIs/formats/errors/accounting before Writer work. All 13FOLLOWONcriteria,
008publication/verified acknowledgment and009restart/final audit remain mandatory.


## DEV-068 — Recover the existing renderer before the focused validator optimization

The current human requests a temporary safe-concurrent-validation priority and a stop after its verified integrated documented checkpoint. Follow the original renderer's live owner first; no replay, competing run or tracked frozen-baseline edit. Its final F-001 repair received1063/1063 checks and independent acceptance; coordinator verified exact receipt/source/complete diff/predecessors/process ownership and fast-forwarded1867872 before full target validation. That unchanged check also supplies the original sequential measurement:2103.466wall seconds,1063executions,2073.61user+11.35system CPU,340388KiB maximum resident set. No waiver or backend change.

REQ-DEV-VALIDATION-001 targets the existing standalone product validator, preserving full unittest discovery, fixture semantics, coverage/results, source checks, CWI process-group supervision and exact integration. Prefer process execution groups established by actual resource audit and fixture ownership, conservative serial/custom-suite fallback and minimal exceptional shared-resource metadata. Ordinary future tests require no registration. Exact CPU allocation C=min(T//2,max(0,A-2)), at most2*C units, child-only affinity where supported; all uncertain/crashed/incomplete execution fails without replay. CWI Architect supplies a complete standalone prescription; only its Writer implements. Alternatives of controller changes, per-case fixture splitting, manual worker assignments or direct coordinator coding conflict with scope/integrity. New regressions and equivalent full-source measurements establish correctness/performance, not assumption. No research-runtime scheduler, resource grant or scientific requirement change. Stop after completion; do not launch007-B this session.

## DEV-069 — Decline a finally accepted source when independent fixture evidence contradicts it

Run cd93ad37's exact final7d2622c5 passed1119/1119 twice and both reviews, but a fresh executed probe proves import-time unittest module cleanup duplication with false success. Preserve the genuine acceptance and independent contradictory evidence separately. Explicitly decline integration at the terminal/quiescent boundary rather than change frozen state/source or transplant a repair. Main retains the original validator.

Fresh bounded R1 uses supported compact immutable Git-object manifest/probe/audit context; only its Writer adopts the eight exact product paths and corrects global cleanup handling. Prefer conservative whole-original-suite fallback when cleanup ownership is ambiguous, preserving stock LIFO transitions and genuine error/skip outcomes. Do not infer callback ownership, discard callbacks, manually register ordinary tests or replay discovery. Preserve all56 added regression methods,98 predecessors, original formula/limits, finalization repairs, full acceptance and exact integration. B-023 first recovery1/2 is counted, global coordinator15; prior B-022 chronology/reference and all historical limits persist. Corrected integration/full benchmarks/checkpoint are required before STOP; no backend change or broader permission follows.


## DEV-070 — Adopt corrected full-suite concurrency and limit duplicate Reviewer diagnostics

The exact R1 sourceef3bfcf723a246750021cce32024cf6717eb5fa9/receipt2ecf76d5 closes the independently proven global-cleanup flaw with whole-original-suite fallback for pending/unknown state. It preserves all predecessor assertions, existing finalization repairs and stock fixture/result semantics. Independent stock-oracle regressions and fresh callback probe, full CWI acceptance and exact fast-forward integration support adoption. The original accepted7d2622c5 remains deliberately declined/superseded; no historical receipt or failed evidence is rewritten.

Keep the permanent full validation command unchanged. Automatic discovery creates fixture-safe units without a manual registry; exact C=min(T//2,max(0,A-2)) and at most2*C workers, child-only CPU masks, effective-resource resampling and fail-closed lifecycle/accounting apply. Exceptional dependencies serialize; ambiguous global cleanups traverse the original suite intact. Future ordinary test modules require no scheduler change. Linux/fresh-process/private-CPython and wave-barrier limitations are explicit in the guide. All1130tests and per-leaf dispositions agree in both modes; same-source wall2131.505420/472.709730seconds establishes4.5091× speedup, at higher total CPU/group memory. This is development validation, not research-runtime scheduling or scientific evidence.

The human additionally authorized targeted Reviewer testing. Only the separate backend Reviewer prompt changes (c74df0b→b6a2e052) after all frozen runs and benchmarks terminate. Optional diagnostic execution follows changed behavior/callers/dependencies/fixtures and concrete review uncertainties; current bound controller full results supply required execution evidence. No Reviewer full-suite rerun, stale cached evidence or new validation IDs. Required full baseline/candidate/final/target checks and all review criteria remain unchanged. An instruction-level prompt is appropriate to discretionary review; no mechanical test-impact selector or changed controller scheduler is introduced. Focused123passed+2pre-existing opt-in skips, independent read-only audit and adopted packaged/routing7/7 support this narrow adoption; no live-model compliance or Reviewer timing gain is asserted. Preserve exact backend commit and sanitized patch in coding_pipeline_changes.md. Complete checkpoint/handoff then STOP as instructed; next roadmap work belongs to a subsequent session.

## DEV-071 — Commit authentic lifecycle output before complete-history plans — 2026-11-04

The human resumes continuous engineering in a new session after the required focused STOP. Fresh Git/CWI/host evidence confirms all36runs terminal,24accepted sources integrated and one accepted validator source intentionally superseded, with no pending integration. Adopt the preserved conditional B1/B2 draft's ordinary decomposition: [REQ-D04-007-B1](development/requests/REQ-D04-007-B1.md) authentic separate O/X/M output commitment/recovery, then mandatory B2 complete-history plans/offline reconstruction. A combined request couples connection-owned metadata/artifact commitment to pure offline history/plan reconstruction and repeats earlier workload risk. Separate accepted contracts cost another full cycle but simplify exact review and failure attribution. This is the coordinator's engineering decision under existing authority, not human design approval or a new recovery.

Reuse accepted source verification on the same transaction connection and the unchanged pure renderer; preserve source S/E and its one-member receipt, separate output O/X/M and ordered manifests, every pending obligation, historical dates and closed work gates. Architect owns exact complete standalone contracts/accounting; only CWI Writer implements. All104current predecessor test/helper/fixture/validator blobs/modes remain protected. B2/008/009 retain all remaining original13FOLLOWONcriteria and wider D04/M0-E/scientific duties. No provider/dependency/schema/backend change, authority expansion or counter reset.

## DEV-072 — Respect exhausted deadline recovery and select independent Tool-release contracts

B1/run2bc3d843 did not fit the frozen2700-second Writer invocation: CWI stopped without candidate/review/acceptance. A clean host/source/lease/quarantine audit resolved ownership and preserved17unaccepted files. This is the existing B-013deadline mechanism, whose2/2 recovery actions are already exhausted. No third retry, relabeled adoption, higher timeout, acceptance waiver or direct implementation is authorized; no backend defect is established by the configured stop.

Select [REQ-D05-001](development/requests/REQ-D05-001.md), a complete passive seven-area Tool-release manifest/codec boundary. It consumes accepted domain/reference/work-product conventions and no failed output code. Continuing dependent B2 would lack its prerequisite; starting actual tool execution would lack D04 admission/isolation/report gates. Passive provider/tool-independent declarations need neither and commission a useful M0-E subset. This is the coordinator's ordinary decomposition decision under the existing v1.4 grant, not human scientific approval or a reset. Later D05 typed registration, authority/qualification and real isolated execution remain mandatory. B1/B2/008/009, all13FOLLOWONcriteria/all94requirements and scientific/live judgments persist. Keep new source/test work CWI-only.


## DEV-073 — Exact Tool-release envelopes before typed registration

REQ-D05-001 is actually accepted, integrated and target-validated at8cd859f7; its
complete pure declaration is a usable consumed M0-E subset. The next decision is
whether to combine exact envelope/projection conversion with transactional typed
admission or review those boundaries separately. Existing store dispatch includes
constrained/shallow targets, historical closure, original-ID recovery and generic
lookalike semantics; coupling all of that to new projections increases repair scope.

Choose [REQ-D05-002](development/requests/REQ-D05-002.md) for exact passive envelopes
first, followed by mandatory typed registration/reference/history work. An extra
CWI cycle costs time, but gives independent local-consistency evidence before
persisted authenticity. Record IDs match stable tool_id; revision and creator
provenance are explicit. No activation, permission, qualification or store authenticity
comes from conversion. Finite content and projection bounds must precede copying;
unknown projected collections retain their unknown state in content. Architect owns
the complete prescription; CWI Writer alone implements. This is an ordinary
reversible engineering choice under the existing grant, not new human design
approval, a failed-draft salvage or a recovery reset. All broader obligations remain.


## DEV-074 — Reuse transactional typed admission for passive Tool releases

REQ-D05-002 is exact-integrated/target-validated0a6a01e2. The existing MetadataStore already owns immutable revisions, direct-artifact synchronization, same-connection target resolution, rollback and original-ID reconciliation. A separate registry or dedicated duplicate transaction would introduce competing identity/recovery semantics. Choose REQ-D05-003 to extend existing dispatch and constrained closure, keeping local inspection separate from past admission.

Implementation Source/manifest, child release, Evidence and Issue roles are constrained; provenance/dependencies/reported tool_assessment stay shallow. The last has no implemented typed qualification contract. Complete prior ToolRelease revisions are metadata-validated under the same transaction; unchanged content can receive new provenance without manufacturing a new release hash. No new marker or schema change claims generic-original retries were typed-certified. This is an ordinary coordinator decision under the existing grant, not human scientific approval, failed-B1 adoption or a recovery reset. CWI Architect prescribes complete interfaces/errors/tests and only its Writer implements. D04 output/restart, all13FOLLOWONcriteria, permission/qualification/actual execution and all scientific/live requirements remain mandatory.


## DEV-075 — Passive attributed assessments before admission and enablement

After exact registration integration`4608f0ecd8a0599e81c31a170dba50fdff0b36f0` and matching1216/1216final/target results, choose [REQ-D05-004](development/requests/REQ-D05-004.md) for a complete pure ToolAssessment declaration, finite codecs and exact envelopes. Combining this with store history/authenticated permission would couple new assessment semantics to a second persistence/authority boundary. The pure content/envelope slice is substantive and independently reviewable; later typed persistence, exact release/environment pairing, current authenticated enablement and actual execution remain mandatory.

Reported permission, operational/software/scientific qualification and lifecycle status remain separate supplied dimensions. A reported pass, assessor attribution or generic qualification reference cannot grant execution or scientific support. Architect prescribes complete schemas/vocabularies/bounds and only CWI Writer implements. No failed B1 draft, new recovery or scope/scientific-authority change. All117current predecessor test/helper/fixture/validator paths are protected. The long session ends at a safe context boundary with a committed ready request, not a new active controller or completed product.

## DEV-076 — Passive transactional assessment admission before enablement

After exact ToolAssessment contract integration and matching final/target
1276/1276 results, choose REQ-D05-005 to extend the existing RecordStore transaction
and typed inspection boundary. Reuse pure envelopes and existing connection-owned
release/reference/history/artifact/idempotency checks rather than introducing a
parallel registry or admission ledger. Exact target/release pairing is persisted
consistency, not evidence of authenticated assessor identity, permission, check
execution or scientific qualification. A separate authority/enablement boundary
remains mandatory. Architect prescribes complete role/history/limit/error rules;
only CWI Writer implements. Preserve 123 test/helper/fixture/validator paths and
all1276tests, while updating navigation indexes as required. This is ordinary
independent engineering, with no failed B1 source, new recovery or scientific
authority. Existing holds and all remaining requirements persist.

## DEV-077 — Expose passive Tool records through the existing CLI

After actual assessment persistence acceptance/integration and1326/1326 target
validation, choose REQ-D05-006 for exact typed inspection and a separate explicit
mixed ToolRelease/ToolAssessment submission batch. One atomic batch preserves
forward-reference pairing; reuse private config, bounded control/output handling
and existing typed store/recovery instead of a generic canonical-write command or
another registry. Permit only an essential prescribed connection-owned bounded
read seam if required to preserve caller limits and snapshot identity.

Authenticated enablement is a separate current-authority boundary; execution also
needs missing D04 admission/isolation/report contracts. Those remain mandatory;
this CLI gives a useful terminal workflow without consuming failed B1 source or
an exhausted recovery. Preserve128 predecessor blobs/modes and1326 tests, exact
original IDs and the local-consistency/authenticity distinction. Architect fixes
complete standalone interfaces before its CWI Writer implements. This is an
ordinary coordinator choice within the existing grant, not human scientific
approval or a reset. Session context requires a safe handoff with this committed
request ready; no new implementation start is claimed.


## DEV-078 — Declare immutable task assignments before admission

After exact passive Tool CLI integration and required1372/1372 target validation,
select REQ-D04-010 for complete pure TaskSpecification values,finite codecs and
exact task envelopes. Existing generic task identities and shallow task references
do not yet supply this §5.1 contract. A coupled scheduler would consume unfinished
report/fencing/isolation gates; authenticated Tool enablement introduces a separate
current-authority/assessment boundary. Pure declarations commission a useful
independent M0-E subset without either dependency.

The contract preserves exact inputs,expected work products/completion,declared
visibility/tools and allocation constraints while separating actual attempt/worker
identity,availability,permission,resources and scientific support. Architect owns
complete standalone representation/limits/errors using actual accepted APIs; only
CWI Writer implements. Future typed persistence/history/original-ID recovery and
actual queue/admission/fencing/report/isolation remain mandatory. Preserve134
predecessor blobs/modes and1372 tests. No failed B1 source,third deadline recovery,
scientific judgment,scope reduction or authority reset. This is the coordinator's
ordinary technical choice under the existing grant,not human design approval.

## DEV-079 — Hold failed Task draft; scope independent current eligibility

REQ-D04-010/run8cef23e2 stopped without acceptance after controller interruption and an orphaned Writer. The resulting source is unaccepted, and prior interrupted-workflow salvage recovery 2/2 is exhausted. Do not relabel a replacement, transplant the draft, alter CWI evidence or treat its completed response as an accepted implementation. CWI's later final-response digest mismatch is preserved. With the old process exited and parent clean, independent engineering may proceed. R-015 synchronous current eligibility/invalidation is a candidate because accepted typed Review/Issue and exact transaction contracts exist; it does not consume Task declarations or the failed D04 B1 source. First scope a bounded request against the actual accepted APIs and original §5.5/§7.5 requirements. If a required dependency or scientific decision is missing, record that instead of silently weakening the criterion. This is an operational choice within the existing grant, not a recovery-limit or scientific-authority amendment.

## DEV-080 — Conservative transactional freshness before positive promotion

REQ-D02-007 scopes explicit claim-use bindings and synchronous generation/reassessment changes on material Review/Issue updates. The accepted attributed reports and generic policy references are not authenticated scientific approvals. A current-use view must therefore begin ineligible and cannot become positive merely from a reported `sufficient` route or an alternative edge. Positive promotion and policy-change freshness remain later R-015/R-077 work. This bounded, independent slice consumes accepted Review/Issue admission and SQLite transaction contracts, not the unaccepted Task draft or blocked D04 B1 source. It preserves old-scope evidence and treats dependency propagation as a finite, fail-closed metadata transaction. This technical decomposition grants no scientific judgment, recovery reset or new authority.

**DEV-080 outcome, 2026-11-05:** REQ-D02-007 was accepted, exact-integrated and target-validated at `1296c93f1bffa306d04a7b240241a5b85275335b`; [run evidence](development/runs/8715d97e-341b-450a-8281-4760a34ba2cb.md). Its conservative use/reassessment contract preserves the original decision's trust boundary. Full positive disposition, authenticated sufficiency, policy-change freshness and promotion remain future R-015/R-077 obligations. The later human shutdown instruction pauses further selection in this session without changing the architecture, specification or continuous grant.

## DEV-081 — One owner for current coordinator rules and selective restart reading

The 2026-11-05 human request authorizes a Markdown-only reorganization, excluding the separate `coding_pipeline/` checkout, followed by a commit and handoff. Keep current coordinator permissions and review boundaries in [AGENTS.md](AGENTS.md), actual human grants in [AUTHORIZATION.md](development/AUTHORIZATION.md), model settings in [MODEL_POLICY.md](development/MODEL_POLICY.md), the continuous loop in [AUTONOMY.md](development/AUTONOMY.md), operational commands in [RUNBOOK.md](development/RUNBOOK.md), and record ownership in [DEVELOPMENT.md](DEVELOPMENT.md). The [continuation prompt](development/CODEX_START.md) directs the next coordinator to current status, grant, handoff, active evidence and relevant specification sections, then opens historical records only when needed. Cross-references replace copied standing policy in the runbook and navigation pages.

Keep separate commissioning and approval templates self-contained because a human may issue either independently; they are not the continuation prompt for this commissioned repository. Remove the duplicate model paragraph inside the optional single-prompt commissioning template, while keeping its first full statement and all eight flags. The local handoff template distinguishes live recovery detail from safe checkpoint pointers. Preserve frozen requests, historical grant amendments, run records and local snapshots. Several `docs/` examples are extracted and executed by implementation tests, so moving their blocks would change product validation and is outside this administrative task. This decision changes no requirement, grant, CWI state, backend file or product behavior. Future checkpoint records should link to their information owner instead of restating long evidence narratives.

## DEV-082 — Explicit policy-freshness boundary and shutdown

The coordinator selected policy freshness as independent engineering from accepted claim-use contracts, rather than adoption of exhausted failed drafts. CWI Designer confirmed one bounded milestone; accepted implementation uses opt-in schema5 and verified4→5 activation to preserve legacy chronological semantics. Generic policy declarations remain shallow and eligibility false. [Run evidence](development/runs/c255a52f-4034-46dd-b2ff-69e046e7814a.md) records acceptance, exact integration, required target validation and one repaired finding. The human then directed shutdown; no next development cycle is authorized in this session. Backward compatibility is unnecessary when superseded safely within scope, while historical evidence and unfinished-run frozen settings remain preserved.

## DEV-083 — Conservative target-context revision freshness

The human resumed top-level CONTINUOUS coordination under the unchanged revision7 grant. Fresh native status/diagnose reconciles46 terminal histories,33receipts,32integrated final sources,one deliberately superseded acceptance and13incomplete histories. No live owner/lease/quarantine/pending integration; preserved historical operation PIDs are absent. Latest receipt and required target-log hashes match their owning run record, accepted source is an unchanged ancestor of clean main, and the specification digest matches the grant. All cumulative/exhausted limits persist.

[REQ-D02-009](development/requests/REQ-D02-009.md) chooses explicit target-context identity watches plus conservative reassessment from accepted ClaimUse contracts. Positive eligibility requires additional authority/sufficiency contracts; project active-context adoption requires a separate selection contract. Neither is ready for inclusion in this small slice. Exact bound context pins remain historical, observed successors never transfer scientific support, and broader context dependencies remain mandatory later work. Architect chooses APIs/schema/activation within the request; CWI alone implements/reviews. No failed Task/B1 draft is reused and no recovery allowance is consumed by preparation.

## DEV-084 — Preserve completed orphan output; recover through fresh CWI acceptance

Human attributed the controller interruption to accidental cancellation and authorized one additional REQ-D02-009 salvage attempt after reviewing the conditional recovery proposal. Waited for Writer completion and actual process quiescence before supported reconciliation, avoiding a response-digest race. CWI correctly refuses automatic adoption/replay of changed interrupted-agent effects. Preserve all33 changed files as an exact hashed reference patch with per-file identities; only a newly prescribed CWI Writer may adopt/repair them. No original-checkout source transplant, old-state modification, successful-check duplication or backend patch. The replacement preserves all1470predecessors and original context-freshness criteria, with fresh complete validation/review. This is an explicit one-attempt authority exception, not a reset or reuse permission for other failed drafts.

## DEV-085 — Explicit context activation accepted; checkpoint after bounded salvage

[REQ-D02-009-R1](development/runs/c0bffb7b-f83d-4b19-aeef-752f925671e9.md) delivers explicit schema6 context activation/migration and conservative target-context successor freshness with exact historical downstream scope. CWI Designer confirmed15criteria,Reviewer resolved obsolete schema6-invalid coverage and migration-guide inconsistency through one prescribed repair,and final full-range review/receipt plus final/target1511/1511 establish bounded engineering evidence. Eligibility remains false; active-context adoption,scientific transfer and sufficiency/authority/promotion need separate mandatory contracts/evidence. Original failed run and frozen configurations remain intact. Current human shutdown was honored after normal completion,authorized exact integration and required target validation; no follow-on request or phase. Backward compatibility is unnecessary when safely superseded,while current functionality,historical evidence and unfinished-run recovery remain protected.

## DEV-086 — Explicit support-context dependencies before active-context adoption

Under the unchanged continuous grant, select [REQ-D02-010](development/requests/REQ-D02-010.md) from accepted ClaimUse and typed-context contracts. Extend the existing conservative mechanism to candidate,selected Justification,complete premise and selected Evidence context occurrences,including exact upstream bindings. This closes a bounded recorded-dependency gap without needing human scientific selection. Active-project-context adoption needs a separate explicit selection contract; positive eligibility needs authenticated sufficiency/authority; failed Task/B1 adoption remains blocked. Neither alternative is included or waived. Architect owns APIs,schema,activation and finite indexed work; CWI owns implementation/review. Preserve old event semantics and all historical pins; no transfer or sufficiency follows. No new grant,recovery allowance,requirement credit or product change is created by preparation.

## DEV-087 — Support-context activation accepted; expose existing current views next

[REQ-D02-010 evidence](development/runs/b4a385e8-ede3-446d-8069-bbdd76c9e9b6.md) binds schema7's explicit support activation to accepted0668007 and final/target1544/1544,without repairs. Historical contexts remain exact;current freshness is conservative and grants no support transfer,sufficiency or authority. CWI owns implementation correctness;the coordinator verified bound evidence and exact integration safety without independent Writer code/test/diff review. Historical terminal process markers were preserved and distinguished from actual ownership;local verifier assumptions changed no source/evidence or recovery counts.

Select bounded read-only current claim-use and generation-history CLI as the next R-082 candidate:existing APIs already expose complete coherent metadata,and the current generic exact-envelope CLI does not expose these operational views. Reuse established private controls and output/limit/error contracts. No new core freshness algorithm,submission,disposition or scientific decision is needed. A local contingent draft is not a run/grant;fresh readiness and a committed request remain prerequisites after this checkpoint. All other engineering/scientific obligations and exhausted limits persist.

## DEV-088 — Read-only claim-use/history CLI before new scientific authority

The current generic CLI inspector returns exact immutable envelopes;it does not expose the existing coherent current claim-use document or generation history. Select [REQ-D03-009](development/requests/REQ-D03-009.md),a bounded R-082 read-only wrapper around accepted inspect_claim_use/claim_use_history,retaining complete versioned scope,provenance,limitations and independent finite accounts. Reuse existing private controls/error/output contracts;Architect finalizes numeric/default/result details within the request. No canonical submission or new core freshness algorithm is needed. Active-project-context adoption and positive eligibility require separate authority/sufficiency contracts,and failed Task/B1 adoption remains held;neither is included or waived. This is ordinary engineering under the same CONTINUOUS grant,not recovery or new scientific authority. Fresh readiness and ownership evidence is local;all prior counters/limits persist.

## DEV-089 — Preserve late-observation error meaning; expose frozen Sources before capture publication

[REQ-D03-009 evidence](development/runs/45afcd6b-0489-4e55-a807-a92ea9b15083.md) binds accepted6d023d5,final/target1577/1577 and resolvedF-001. An initially unsafe layout and a permission/ownership change after a held observation are different facts;CWI's repair preserves initial unsafe classification and treats late changes as integrity failures. CWI owns implementation correctness;coordinator verified bound review/check/source evidence and exact integration safety without routine Writer code/test/diff review or duplicate successful checks.

For R-082 Source creation,considered a combined capture/inspect/submit CLI against existing source_capture APIs. Choose a smaller first request:inspect a saved strict Source wrapper and explicitly submit that exact request,retaining original-ID-first retry with no input/head/artifact preview or recapture. This avoids coupling new input-file capture and proposal publication to metadata acknowledgement in one Writer assignment. Existing preparation and caller-controlled exclusive/fsynced save remain library-only until a separate mandatory CLI follow-up;seed/project/readiness and scientific permissions are not inferred. Actual current check/administrative checkpoint and fresh model/ownership readiness precede any request/start. This is a reversible decomposition within the same grant,not a requirement waiver or new authority.

## DEV-090 — Reuse the exact saved Source wrapper at the CLI boundary

Select [REQ-D03-010](development/requests/REQ-D03-010.md) after verified CLI integration/checkpointbad7a10. Two protected commands inspect an existing strict source_capture_submission/version1 file without opening runtime/locators/artifacts,and explicitly pass the pure-decoded exact Source-only request to submit_typed. Preserve original-ID-first receipt reconciliation without input/head/admission-preview/artifact prechecks or recapture. Reuse private controls,complete bounded output and initial-unsafe versus late-integrity distinctions from accepted6d023d5. Architect finalizes argv/default/result details within the frozen request. No new wrapper,publisher,capture algorithm,generic write endpoint or scientific/operating authority. A later capture-preparation CLI remains mandatory;full Source/seed/project/readiness/CLI and scientific obligations are not waived. Fresh prelaunch model/ownership evidence is local;all counters/limits remain consumed.
