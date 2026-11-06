# Active development backlog

Lists current unresolved dependencies and recovery holds; resolved items and chronological reconciliation remain in historical records.

## Open and deferred items

| ID | State | Item | Reason / dependency | Resume or decision condition | Owner |
| --- | --- | --- | --- | --- | --- |
| B-003 | DEFERRED | Selection of live model/provider adapters | Deterministic fixtures should establish contracts before paid/live integrations | D06 has an approved adapter contract, credentials policy, and budget | Human + coordinator |
| B-004 | DEFERRED | Extra development-status automation | Markdown records and CWI inspection are sufficient initially | Repeated manual reconciliation cost justifies a bounded CWI request | Coordinator |
| B-005 | DEFERRED | Distributed workers and multi-user operation | Not required to establish a trustworthy single-machine vertical slice | Pilot evidence and exact product requirements justify expansion | Human |
| B-006 | DEFERRED | Specific symbolic, theorem-proving, or software-development tools in the product | Product tools are optional capabilities, not a fixed supplied set | A concrete research task and tool qualification contract justify integration | Research/product owner |
| B-009 | DEFERRED | Automatic restart of outer Codex sessions | Documentation provides continuous execution and manual recovery, not a daemon | Separate CWI request, explicit need/authority, single-owner and bounded-recovery tests | Coordinator + human |
| B-010 | BLOCKED FOR DEPENDENT SCIENTIFIC WORK | M0-S scientific readiness (R-001–R-003 and related domain judgments) | No approved pilot/usefulness, audited references/protected held-out set or predeclared scientific protocol; oscillator remains exposed mock | Human supplies these before corresponding scored evaluations, qualification claims and release; independent M0-E/storage/vault/controller/tool engineering may proceed under v1.4 | Human scientific owner |
| B-011 | BLOCKED FOR LIVE WORK | Product provider/data/budget approval and scientific acceptance | Development Codex allowance does not authorize product experiments or pilot data access | Separate explicit service/data/budget and expert review records before live work | Human |

## Exhausted recovery paths

| Path | Current hold | Evidence |
| --- | --- | --- |
| B-013 Writer deadline | 2/2 consumed; no replacement, draft subdivision/adoption or timeout increase without actual new authority | [Latest recurrence](development/history/BACKLOG.md#b-013-reopened--writer-deadline-recurrence-path-blocked--2026-11-04) |
| Interrupted Task/B1 drafts | Interrupted-workflow salvage 2/2 and orphan-response-permission 2/2 exhausted; failed Task source remains unaccepted | [Task run](development/runs/8cef23e2-42cf-4580-b7f3-8d29520fccf7.md) |
| Additional context salvage | Separate one-attempt exception 1/1 consumed; not reusable for Task/B1 or another replacement | [Accepted salvage](development/runs/c0bffb7b-f83d-4b19-aeef-752f925671e9.md) |

All other historical consumed/partial allowances persist. Resolution does not replenish headroom; consult original ledgers and owning runs rather than infer a fresh allowance from this shortened view.

## Resolved work and ordinary remaining scope

B-024 is resolved by [accepted/integrated run9bae8bd6](development/runs/9bae8bd6-2d0d-4cc7-ab70-9ec7b652d998.md); first corrective action 1/2 remains consumed. Earlier B-001/B-002/B-007/B-008/B-012/B-014–B-023 resolutions, original counts and evidence remain in the [historical backlog](development/history/BACKLOG.md). B-013 was reopened as recorded above.

Source run5d1adb23 remains incomplete before role execution; no Source feature or draft was delivered. Source-proposal/capture CLI, seed/project/readiness, Task/lifecycle/report and broader mandatory scope remain in [ROADMAP](ROADMAP.md) and [REQUIREMENTS](development/REQUIREMENTS.md). They are not waived or automatically treated as new recovery attempts. Product coordination is explicitly resumed under unchanged revision 7 authority. The repaired baseline permits one conservatively counted replacement Source attempt, REQ-D03-010-R1; B-024 corrective actions become 2/2 on that launch, without replenishing prior recovery limits. STATUS owns the single next safe action.

## Required fields for a new blocked or paused item

Record an ID; state; affected requirement/phase/request; concrete reason; exact run and source revision where relevant; evidence location; already-completed work; unresolved effects; owner; resume condition; and one next safe action.

`INVESTIGATE` means an observation needs reproduction and disposition; it is not automatically a product blocker or a waived failure. `BLOCKED` means the prerequisite prevents progress. `PAUSED` means progress was deliberately suspended even though continuation may be possible. `DEFERRED` means intentionally outside the current approved slice. `REJECTED` records a considered approach that should not be repeatedly rediscovered. `RESOLVED` retains the resolution evidence.

An unfinished CWI run is never made safe by calling it paused here. Follow its actual recovery guidance.

In continuous mode, a blocker prevents dependent work and any full-scope completion claim. It need not stop independent authorized work after current run ownership/bindings are safely resolved. Preserve actual local backlog entries; these newly supplied rows are not evidence of your local installation state.
