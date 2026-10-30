# Development roadmap

This is the proposed sequence for implementing the product in [project_description.md](project_description.md). Current execution belongs in [STATUS.md](STATUS.md), not in a second independent set of status cells here. Each phase has a coherent outcome and acceptance obligations; each may require several bounded coding-pipeline runs.

**Reconciled 2026-10-30:** the full local specification v1.3 is mapped in [REQUIREMENTS.md](development/REQUIREMENTS.md). Its M0–M7 gates remain controlling. D01 now includes a scientific-contract gate after the explicitly authorized foundation commissioning and before D02; D04 includes minimum deterministic run closeout. No phase is complete merely because its administrative plan exists.

| Phase | Outcome | Depends on |
| --- | --- | --- |
| [D00](development/phases/D00-specification-and-operating-readiness.md) | Specification and operating readiness | Initial repository |
| [D01](development/phases/D01-testable-product-foundation.md) | Testable foundation, then M0 scientific contract | D00 |
| [D02](development/phases/D02-durable-scientific-records-and-provenance.md) | Durable scientific records and provenance | D01 |
| [D03](development/phases/D03-seeded-project-intake-and-navigable-vault.md) | Seeded project intake and navigable vault | D02 |
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
| M0 scientific contract and expert evaluation material | D01 after REQ-D01-001; blocks D02 until approved, not postponed to D10 |
| M1 durable records and vault | D02–D03 |
| M2 controlled execution, adapter contracts, minimum no-model report | D04–D05 |
| M3 single complete research loop and bounded context | D06 |
| M4 verification and atomic promotion | D07 |
| M5 adaptive coordination and optional delegation | D08 |
| M6 synthesis, human decisions, navigation and export | D09 |
| M7 actual held-out pilot and architecture comparison | D10 |

Continuous authorization permits selecting ready work; it does not waive M0 scientific decisions, live-resource permissions or expert judgments. Foundation acceptance activates the conditional operating grant after integration/checkpoint, while the next scientific slice remains subject to its prerequisites.

Current M0 evidence: the requested synthetic oscillator fixture is integrated (REQ-D01-002), and [the administrative contract packet](development/decisions/M0-contract-and-scientific-review.md) is ready for scientific review. Its synthetic expected assessments do not satisfy the original expert-audit/pilot/protocol gate. D02 remains dependent on that gate; the continuous operating grant remains active with execution held for required human scientific judgment.
