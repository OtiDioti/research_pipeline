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

Continuous authority is active under AUTH revision 5 (explicit 2700-second new-run deadlines). Commissioning, the synthetic example and REQ-D02-001 durable records are integrated, but M0-E overall, M0-S, D02 and the research product are not complete. REQ-D02-002 verified backup/restoration is also integrated. REQ-D02-003 typed provisional scientific contracts/admission is integrated. REQ-D02-004-R1 versioned core identities and verified-backup migration are integrated. REQ-D02-005-R1 attributed review/issue records are accepted/integrated. REQ-D02-006 work-product bundles and safe draft checkout/preview/import are accepted/integrated. REQ-D03-001 versioned Source captures and bounded inert local ingestion are accepted/exact-integrated at d8dffdd with 343/343 target tests under the recorded descriptor prerequisite. That historical Source checkpoint led to REQ-D03-002 corpus history and REQ-D03-003 project/intake dossiers, now integrated below; support freshness, fencing and remaining core record semantics remain required. [M0 packet](development/decisions/M0-contract-and-scientific-review.md) separates settled engineering choices from missing scientific decisions. Later requests consume only the evidenced predecessor behaviors they need; they need not wait for unrelated empirical acceptance. No live-product service/data/budget authority has been added.

REQ-D03-002 is now accepted/exact-integrated at 7d6dd6246e47ace09ff44a1decef14c93251f0ac with 369/369 target tests. Its immutable inventory and exact Source/history contracts enable the next bounded project/intake dossier in REQ-D03-003, followed by protected readable views and actual authorized research admission. The ordinary remaining D03/D04 requirements and scientific holds remain open; no phase completion follows from this recording subset.

## Historical project-intake checkpoint — 2026-10-31

REQ-D03-003 is finally accepted/exact-integrated at9373860 with396/396 target tests; [run evidence](development/runs/db2829bc-fca9-48d7-b2c1-b9e99348c197.md). Exact project history, attributed inspected subsets and coherent brief/report/context pins support readiness proposals only. D02/D03 and M0-E remain partial; M0-S remains pending. Next [REQ-D03-004](development/requests/REQ-D03-004.md) prepares consistent immutable readable snapshots with bounded private generation/exclusive publication. Refresh/direct-edit preservation and all scientific/operational obligations remain required. Continuous12/50 starts consumed,38 remain; deadlines2700 seconds, unchanged model/grant.

## Historical snapshot recovery checkpoint — 2026-10-31

REQ-D03-004 stopped terminally without acceptance: first-milestone candidate81ec2f3 passed432/432 but lacked required controller-recorded complete-diff evidence. Main remains accepted project/intake9373860 (396 tests); no snapshot feature is integrated. [Run evidence](development/runs/32b61b7f-7d9b-475d-a44e-74e53d03c5a0.md). [REQ-D03-004-R1](development/requests/REQ-D03-004-R1.md) is the next bounded replacement, using preserved CWI draft context and two frozen checks. Protected publication/inspection is still unimplemented. Continuous13/50used,37remain; repairs7,recoveries4,backend0. No scientific or phase completion is inferred.

## Current snapshot integration checkpoint — 2026-10-31

REQ-D03-004-R1 is finally accepted and exact-integrated at c57a621c3e3f7806030de13b75b4fe2890b81cc7, with 489/489 controller/target tests and both bound checks passing. [Run evidence](development/runs/7ee32819-ee00-4b1b-bdba-ea26fb90cf3e.md). Consistent detached metadata, deterministic linked Markdown/manifests, verified independent copies, private complete publication and bounded offline inspection now have implementation evidence. B-016's missing-check recovery is resolved; its terminal predecessor remains preserved. No backend change.

D03 and M0-E remain partial; M0-S remains pending. Generated-view refresh with preservation of direct edits and renames is the next ready engineering boundary under §§9.7–9.11/R-026/R-028. Full branch/runtime/report workspaces, intake interpretation/authorized readiness and lifecycle/authority/tool/research obligations remain required. The authoritative next action and handoff are in STATUS; continuous 14/50 starts used, 36 remain, unchanged grant and 2700-second deadlines.

## Refresh preparation — 2026-10-31

Fresh Git and retained CWI reconciliation confirms c57a621 is already integrated beneath administrative 7f3f081; twelve accepted results and three terminal failures are preserved, with no active owner or pending integration. [REQ-D03-005](development/requests/REQ-D03-005.md) is the next ready two-milestone request for bounded divergence/rename capture and immutable successor refresh with preservation and recovery. Existing view and draft APIs provide its prerequisites. No product implementation is added by this preparation. Continuous starts remain 14/50 until launch; next start is 15/50. Full D03, remaining M0-E and scientific/live obligations remain open.

## Current refresh integration and CLI progression — 2026-10-31

REQ-D03-005 is finally accepted/exact-integrated at 8cfb0357ccccff1f079c419eb1ca4b7f4d3b135c, with 579/579 controller/target tests and both bound checks. [Run evidence](development/runs/c62af399-bf8c-4b25-8ef7-ec1947fad6ae.md). Direct edits, renames and ambiguous identities are preserved/diagnosed in an immutable successor package, with verified generated links and real interrupted/conflicting publication evidence. All prior scientific artifacts and canonical history remain fixed. Three CWI repairs resolved the review findings; no backend or authority change.

Next ready [REQ-D03-006](development/requests/REQ-D03-006.md) exposes exact inspection and explicit work-product checkout/preview/saved-proposal/submission through the local CLI. This is a bounded R-082 subset consuming evidenced contracts, before broader execution/authority work. D03/M0-E remain partial; M0-S and all remaining scientific/runtime obligations persist. Continuous 15/50 used, 35 remain before next start 16; unchanged model/high effort and2700-second deadlines. STATUS contains the single current next safe action.
