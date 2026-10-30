# Blocked, paused, and deferred work

This is the authoritative list of **deliberate exceptions to the normal roadmap**. Ordinary future phases belong in [ROADMAP.md](ROADMAP.md), not here again.

Reconciled 2026-10-30 against local evidence. Foundation and requested mock are accepted/integrated; continuous grant is active, with execution held at the mandatory M0 human gate. Mandatory human scientific and live-resource dependencies below remain obligations; optional extensions are distinct.

| ID | State | Item | Reason / dependency | Resume or decision condition | Owner |
| --- | --- | --- | --- | --- | --- |
| B-001 | RESOLVED | Exact specification-to-phase reconciliation | Full v1.3 read and R-001–R-094 mapped | Maintain exact evidence as requests integrate | Coordinator |
| B-002 | RESOLVED | Foundation language/platform/dependencies | Python 3.11+, stdlib unittest, nested implementation and local Linux chosen within proposed specification defaults | Revisit only with concrete need; preserve provider neutrality | Coordinator |
| B-003 | DEFERRED | Selection of live model/provider adapters | Deterministic fixtures should establish contracts before paid/live integrations | D06 has an approved adapter contract, credentials policy, and budget | Human + coordinator |
| B-004 | DEFERRED | Extra development-status automation | Markdown records and CWI inspection are sufficient initially | Repeated manual reconciliation cost justifies a bounded CWI request | Coordinator |
| B-005 | DEFERRED | Distributed workers and multi-user operation | Not required to establish a trustworthy single-machine vertical slice | Pilot evidence and exact product requirements justify expansion | Human |
| B-006 | DEFERRED | Specific symbolic, theorem-proving, or software-development tools in the product | Product tools are optional capabilities, not a fixed supplied set | A concrete research task and tool qualification contract justify integration | Research/product owner |
| B-007 | RESOLVED FOR CURRENT BACKEND | Supplied-backend findings and parser/auth readiness | Local 1,010 pass/21 skip; focused bootstrap 21 pass resolves six pytest skips; exact Codex parser/login probes pass | Actual commissioning accepted/integrated (run 47d6ef06); 15 opt-in live tests unrun; ENVIRONMENT.md records limits | Coordinator |
| B-008 | RESOLVED | Development model identity | Human explicitly approved gpt-6-astra after catalog ambiguity; AUTH revision 2 | Use explicit model/effort; no silent substitution | Human + coordinator |
| B-009 | DEFERRED | Automatic restart of outer Codex sessions | Documentation provides continuous execution and manual recovery, not a daemon | Separate CWI request, explicit need/authority, single-owner and bounded-recovery tests | Coordinator + human |
| B-010 | BLOCKED — REQUIRED_HUMAN_SCIENTIFIC_JUDGMENT | M0 scientific acceptance before D02 (R-001–R-004) | Human-requested mock delivered as 79a84d2, run 34bcb77d; 28 tests and synthetic walkthrough do not establish expert audit, approved pilot/usefulness or evaluation standards | Human returns scientific decision/evidence using [M0 packet](development/decisions/M0-contract-and-scientific-review.md); preserve M0→M1 gate | Human scientific owner |
| B-011 | BLOCKED FOR LIVE WORK | Product provider/data/budget approval and scientific acceptance | Development Codex allowance does not authorize product experiments or pilot data access | Separate explicit service/data/budget and expert review records before live work | Human |

## Required fields for a new blocked or paused item

Record an ID; state; affected requirement/phase/request; concrete reason; exact run and source revision where relevant; evidence location; already-completed work; unresolved effects; owner; resume condition; and one next safe action.

`INVESTIGATE` means an observation needs reproduction and disposition; it is not automatically a product blocker or a waived failure. `BLOCKED` means the prerequisite prevents progress. `PAUSED` means progress was deliberately suspended even though continuation may be possible. `DEFERRED` means intentionally outside the current approved slice. `REJECTED` records a considered approach that should not be repeatedly rediscovered. `RESOLVED` retains the resolution evidence.

An unfinished CWI run is never made safe by calling it paused here. Follow its actual recovery guidance.

In continuous mode, a blocker prevents dependent work and any full-scope completion claim. It need not stop independent authorized work after current run ownership/bindings are safely resolved. Preserve actual local backlog entries; these newly supplied rows are not evidence of your local installation state.
