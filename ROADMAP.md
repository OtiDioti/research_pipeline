# Development roadmap

Defines phase outcomes and dependency gates; current execution belongs to STATUS and historical deliveries remain separately preserved.

## Current progression

D00 commissioning is complete. D01–D05 and M0-E remain partial; later phases and M0-S are not completed. All 94 specification requirements and13 FOLLOWON criteria remain mandatory. Product coordination is STOPPED after the human-directed current-request checkpoint; underlying revision 7 and all remaining obligations persist.

Latest product evidence belongs to [run9252c1a1](development/runs/9252c1a1-74db-4390-b5d8-7305479ab7d6.md): saved Source-proposal inspection and explicit submission/retry are accepted/exact-integrated at4c25bc8, final/mandatory target1618/1618. The original failed Source request remains frozen. Capture preparation remains library-only and proposal-file publication caller-controlled; their CLI is a possible future engineering slice after explicit human resumption and fresh reconciliation; no next request is launched or scheduled. Seed/project/readiness/full CLI, Task/lifecycle/report and scientific duties remain mandatory.

## Phase map

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

When currently authorized and not subject to a human stop instruction, normal completion of a request or phase leads directly to the next ready scoped request. Do not wait for a human merely to move from D02 to D03. Every transition still requires its dependency and evidence gates. Use [AUTONOMY.md](development/AUTONOMY.md) and [AUTHORIZATION.md](development/AUTHORIZATION.md).

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

## Evidence and updates

[REQUIREMENTS](development/REQUIREMENTS.md) owns exact obligation mapping;[BACKLOG](BACKLOG.md) owns holds;[STATUS](STATUS.md) owns current execution and one next action. Update this roadmap only when phase scope/dependencies/progress change. Delivery narratives remain in owning runs and the [historical roadmap](development/history/ROADMAP.md).
