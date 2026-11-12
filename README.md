# Research pipeline — V0-L1

A Linux/Python research runtime with ordinary scientific files, a research-owned
Codex app-server driver, and computations that outlive individual model contexts.
The human specification is [PROJECT.md](PROJECT.md); the authoritative amendment
is [the V0 lifecycle design](2026-11-12-v0-context-lifecycle-design.md).

**Implementation verification is pending production-host validation and independent
pipeline review.** See [the L1 report](development/requests/v0-l1-durable-runtime.md).
L1 does not implement or establish acceptance of the full V0 extension. Historical
M1–M4 receipts remain evidence of their original implementation. M5 is unaccepted,
unmerged and inactive; no private benchmark run is part of this increment.

## Setup and use

Use Python 3.11+, the declared `mcp` dependency, a standalone Linux Codex executable,
Bubblewrap, systemd's authorized user bus, `busctl`, and cgroup v2 memory/swap/tasks
controls. Native file authentication must already be available through the human's
Codex installation. No environment-key or unisolated fallback is supported. Do not
connect to another context's bus to work around missing prerequisites.

Start with a plain project directory containing
`starting_evidence/RESEARCH_QUESTIONS.md`, optional `AGENTS.md` and optional
`HUMAN_FEEDBACK.md`. These remain read-only to scientific agents.

```sh
PYTHONPATH=src python -m research_pipeline start /path/to/project
PYTHONPATH=src python -m research_pipeline inspect /path/to/project --json
PYTHONPATH=src python -m research_pipeline pause /path/to/project
```

`start --preserve-existing` explicitly adopts existing ordinary science while
preserving human Markdown edits. Existing or orphaned runtime state is refused.
Schema 4 is the only operational state supported; no migration is provided.
`resume` explicitly reports that stopped-state recovery/reopening requires V0-L5.
Do not delete old runtime state to bypass ownership reconciliation.

The default human-configured caps are two logical agents sharing 2048 MiB, no swap,
128 process/thread tasks, and one concurrent admitted computation. The human may
set `--memory-mib`, `--max-tasks`, `--max-agents` and `--max-jobs` on a fresh launch.
A persistent investigation slice enforces the aggregate caps. Fixed per-agent
slices divide memory/tasks equally (integer remainder is unallocated). Context
services, MCP helpers, job supervisors and job descendants share those slices.
Replacing a context grants no additional allocation. In L1 a logical task retains
its slot even while its context is absent; repeated/sequential task retirement and
automatic continuation belong to later lifecycle integration.

Fixed scientific investigation/session/demo lifetimes and the configured universal
job maximum have been removed. `--wall-seconds`, `--primary-session-seconds`,
`--delegated-session-seconds` and `--job-runtime-seconds` are rejected. Operational
RPC/startup/shutdown bounds report failures and never create scientific COMPLETE.

## Scientific commands and continuity

The app-server has a private authentication home and an explicit native tool
configuration. Before a context can admit scientific commands, the runtime checks
its actual backend request tool declarations and controlled MCP schemas. Unknown
execution routes, incomplete inventory, protocol errors and missing tools fail
closed. Tool configuration or model statements alone establish no capability.

Scientific commands use these fixed MCP operations:

| Operation | Behavior |
| --- | --- |
| `job_run(argv, cwd, runtime_seconds)` | Reserve once and launch with a required positive finite timeout, including hours. |
| `job_status(job_id)` | Inspect the logical owner's job, including retained stdout/stderr and cleanup evidence. |
| `job_wait(job_id)` | Subscribe to completion without repeated model turns. |
| `job_cancel(job_id)` | Cancel the owned command tree and report observed cleanup. |
| `write_draft(path, content)` | Save scoped scientific Markdown independently of job capacity. |
| `control(action, path, parent, offset)` | Inspect tasks, read immutable scientific documents, delegate a scoped assignment or freeze independent-check evidence. |

Use absolute namespace paths such as `/project/work` for cwd. Scientific shells,
dependency installation, source retrieval helpers and reusable-tool checks all use
admitted jobs. Preparation consumes the chosen timeout. Extremely small or
unrepresentable durations are rejected. Both the job supervisor and systemd enforce
the original deadline. Systemd still enforces the bound if the Python supervisor
or original Codex context dies. No job is automatically retried or restarted.

A command and all descendants occupy one job reservation until cleanup is
confirmed. Missing launch acknowledgements, missing ownership and uncertain cleanup
retain capacity. Cleanup verifies boot identity, unit invocation and cgroup before
stopping, then checks termination and cgroup population. A PID or a stop request
alone is insufficient. Timeout/cancellation retains partial files and bounded
stdout/stderr with clipping indicators. Supervisor completion timestamps and termination
causes distinguish an expired computation from a successful computation observed late. A job timeout does not stop unrelated work.

Logical task IDs own jobs and workspaces. Context IDs and native thread IDs identify
disposable conversations; job IDs identify computations. `Coordinator.close_context`
revokes one attachment and closes only its service. `Coordinator.successor` is the
explicit internal L1 continuation operation: it requires confirmed predecessor
closure, attaches a fresh native thread to the same task/slot, and leaves jobs and
deadlines unchanged. Automatic measured rollover is V0-L2, not an L1 claim. The CLI
keeps the runtime observing live computations after turns end; it does not silently
start replacement model contexts. An idle outcome preserves preliminary science.

`pause` latches the admission block and interrupts all owned contexts and jobs,
then publishes available drafts and reports actual cleanup. Current context drafts
and job-specific draft batches are separate. Failed publication cannot turn
confirmed process cleanup into uncertainty, and failed saving cannot disable
cleanup. A later successful cleanup retry finalizes the same context record, clears
its attachment and releases its private resources; the admission block stays latched.
An unsuccessful acknowledgement retains the request and failure evidence.
L1 can clean recorded services after a foreground exit; it does not resume research
from stopped state or promise controller-crash continuation.

## Scientific files, references and independent checks

Scientific notes and handoffs use Markdown; code and data keep ordinary formats.
The runtime pins existing canonical Markdown read-only while a context/job runs,
and holds descriptor-pinned mount sources for each service. Scoped draft publication
and index generation wait until **all owned contexts and jobs are confirmed stopped**.
Pending batches remain in private runtime storage with `publication_pending=true`;
command results and ordinary data remain inspectable while publication is deferred.
Confirmed-stopped context/job batches also become immutable scientific document
snapshots. A live successor reads its predecessor's handoff, and a live primary or
parent reads a delivered `RESULT.md` or `CHECK.md`, using the same controlled tool:

```text
control(action="documents")
control(action="read_document", path="DOCUMENT_ID", offset=0)
```

`check`/`tasks` include available document IDs, and successor intake includes them.
Document lists return at most 32 entries; reads return at most 8192 characters.
Follow `next_offset` with `offset` until null. Reads require no job slot, accept only
known authorized IDs, and return original scientific paths, source context/job IDs
and whole-document SHA-256. Owners, their successors, their direct parent and the
primary can read a snapshot; sibling tasks cannot read each other's private batches.
Snapshot capture validates only the stopped writer's scoped private Markdown batch,
never live canonical paths. It rejects links/special files and uses the existing
16 MiB per-file reader bound. Capture/integrity failures remain visible as
`document_snapshot_error`/`document_errors`; an unconfirmed writer supplies no snapshot.
Snapshot versions remain readable after publication and do not assert that human-edited
canonical files still have the same content.
Concurrent human edits remain canonical; conflicting proposals are retained under `handoffs/proposed/`.
Directory indexes exclude protected inputs and frozen check evidence. Handoffs name
live jobs and observed outcomes; changing outputs are not hashed as finalized
checkpoint evidence. Prepare a handoff early, before substantial research.

Primary `control(delegate, path=...)` accepts a Markdown assignment with Objective,
Parent question, Scientific benefit, Assumptions, Requested result and Artifacts
sections. Canonical evidence links are rebased to their original project paths.
Linked private Markdown drafts, including their draft dependencies, are retained
under the delegate's read-only inputs with rebased links. Delegates write only
their own task workspace. `control(verify, path=...)`
requires a packet with Claim and scope, Parent question, Scientific benefit,
Assumptions and approximation regime, Sources and artifacts, and Reproduction
instructions sections. Link all local code, data and dependencies explicitly. The
runtime freezes those versions and gives the independent checker a separate task,
context and writable workspace. Active jobs must finish or be cancelled before
freezing evidence. This is an independent scientific check; the continuing opponent
and scientific terminal decisions require V0-L4. Old response/closure protocols
are explicitly rejected. Structural checks never certify scientific correctness.

Reference authorization/retrieval remains available through
`reference add/remove/list/browse/search/read`. For example:

```sh
PYTHONPATH=src python -m research_pipeline reference add /path/to/project prior /path/to/prior-project
PYTHONPATH=src python -m research_pipeline reference search /path/to/project 'literal text' --source prior
```

Authorized source trees are mounted read-only, excluding private top-level paths.
Inside admitted jobs, `python3 /run/research-references.py` provides bounded
list/browse/search/read with source identity, hashes and incomplete-result reporting.
`python3 /run/research-tools.py` provides list/stage/register/run for ordinary
user-supplied or agent-created tools. Checks and invocations inherit the admitted
job's identity and deadline; new jobs require local revalidation. Record qualified
reuse, assumptions, intended applicability and limitations in `REUSE.md`.

Human `redirect --questions-file` and `feedback --file` controls save direction while
quiescent. Current input is re-read for fresh contexts. Human input never authorizes
broader grants. Scientific commands cannot access native credentials, control
sockets, admission storage, systemd's bus or protected/frozen write routes.
Networking remains available without destination filtering; the 64 MiB file limit
is not an aggregate disk quota. Raw model usage/context telemetry is retained when
emitted; no spending cap, quota reserve or measured-rollover guarantee is claimed.

## Verification

Routine checks disable all paid gates:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

When the declared MCP dependency is supplied externally, append its existing
installation to `PYTHONPATH`; do not replace it to conceal an environment issue.
The old timed M1–M4 live harnesses reject enabled use; their evidence parsers remain
covered. The public L1 production fixture uses the same runtime launch path and
requires a private output destination:

```sh
RESEARCH_PIPELINE_V0_L1_NATIVE=1 \
RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR=/fresh/private/l1-validation \
PYTHONPATH=src python -m unittest tests.test_v0_l1_native -v
```

This opt-in check performs minimal native inference for actual tool declarations,
then tests public process survival across context replacement, original deadlines,
descendant timeout, partial output, long-duration admission with prompt cancellation,
ownership denials and shared cgroup membership/caps. Enabled missing prerequisites
are failures with a retained `receipt.json`, never accepted skips. The complete
controller-host command and current missing evidence are in the L1 report.

The first invocation creates the requested output directory with mode `0700`.
If that directory already exists, each invocation reserves a fresh private sibling
with the same basename as a prefix. Existing receipts and evidence are retained.
Files, symlinks (including ancestors) and unusable parents are rejected. The fixture
prints its actual output path immediately; its receipt records both requested and
actual paths. Final and combined checks can inherit the same destination and still
execute independently with distinct receipts.
