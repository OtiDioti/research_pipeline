# Blocked, paused, and deferred work

This is the authoritative list of **deliberate exceptions to the normal roadmap**. Ordinary future phases belong in [ROADMAP.md](ROADMAP.md), not here again.

No product implementation is currently paused. The entries below are preparation decisions or deliberately deferred extensions; they are not discovered research-product implementation failures. The backend readiness finding is separately identified below.

| ID | State | Item | Reason / dependency | Resume or decision condition | Owner |
| --- | --- | --- | --- | --- | --- |
| B-001 | DECISION_NEEDED | Exact specification-to-phase reconciliation | The full local `project_description.md` must be read before committing implementation scope | D00 maps every mandatory requirement and resolves material conflicts | Coordinator + human for material changes |
| B-002 | DECISION_NEEDED | Initial language, platform, and dependency policy | Python 3.11+ and Linux are proposed development defaults, not a quoted product requirement | D00 checks the specification and records the choice | Coordinator within authorized scope |
| B-003 | DEFERRED | Selection of live model/provider adapters | Deterministic fixtures should establish contracts before paid/live integrations | D06 has an approved adapter contract, credentials policy, and budget | Human + coordinator |
| B-004 | DEFERRED | Extra development-status automation | Markdown records and CWI inspection are sufficient initially | Repeated manual reconciliation cost justifies a bounded CWI request | Coordinator |
| B-005 | DEFERRED | Distributed workers and multi-user operation | Not required to establish a trustworthy single-machine vertical slice | Pilot evidence and exact product requirements justify expansion | Human |
| B-006 | DEFERRED | Specific symbolic, theorem-proving, or software-development tools in the product | Product tools are optional capabilities, not a fixed supplied set | A concrete research task and tool qualification contract justify integration | Research/product owner |
| B-007 | INVESTIGATE | Supplied-backend test findings and real CLI readiness | Review found a non-hermetic Codex prerequisite, one-second deadline failures, and a pytest fixture environment mismatch; authenticated CLI execution was unavailable | D00 reproduces relevant cases, records explicit disposition, and verifies local compatibility; necessary focused maintenance follows BACKEND_MAINTENANCE.md and is logged in coding_pipeline_changes.md; no preemptive patching | Coordinator under the user maintenance exception |
| B-008 | DECISION_NEEDED | Exact development model identity | User requested Astra 6.1; no official identifier for that exact label was verified during the update | Establish actual available identifier/access or obtain explicit user correction; no silent fallback | Human + coordinator |
| B-009 | DEFERRED | Automatic restart of outer Codex sessions | Documentation provides continuous execution and manual recovery, not a daemon | Separate CWI request, explicit need/authority, single-owner and bounded-recovery tests | Coordinator + human |

## Required fields for a new blocked or paused item

Record an ID; state; affected requirement/phase/request; concrete reason; exact run and source revision where relevant; evidence location; already-completed work; unresolved effects; owner; resume condition; and one next safe action.

`INVESTIGATE` means an observation needs reproduction and disposition; it is not automatically a product blocker or a waived failure. `BLOCKED` means the prerequisite prevents progress. `PAUSED` means progress was deliberately suspended even though continuation may be possible. `DEFERRED` means intentionally outside the current approved slice. `REJECTED` records a considered approach that should not be repeatedly rediscovered. `RESOLVED` retains the resolution evidence.

An unfinished CWI run is never made safe by calling it paused here. Follow its actual recovery guidance.

In continuous mode, a blocker prevents dependent work and any full-scope completion claim. It need not stop independent authorized work after current run ownership/bindings are safely resolved. Preserve actual local backlog entries; these newly supplied rows are not evidence of your local installation state.
