# Research pipeline — V0-L2

A Linux/Python research runtime with ordinary scientific files, a research-owned
Codex app-server driver, and computations that outlive individual model contexts.
The human specification is [PROJECT.md](PROJECT.md); the authoritative amendment
is [the V0 lifecycle design](2026-11-12-v0-context-lifecycle-design.md).

**V0-L1 and V0-L2 are accepted and integrated.** L2 integrated at `f9119e3`.
Pipeline final and combined verification each passed 184 tests with five gates
disabled. Fresh native receipts passed primary, delegated-researcher and opponent
continuation, with job identity/deadline/allocation preserved and cleanup confirmed.
Threshold crossings used labelled telemetry fixtures alongside actual native
telemetry and scientific inference. See [STATUS.md](STATUS.md) for refs, receipts
and remaining gates, and the [L1](development/requests/v0-l1-durable-runtime.md) and
[L2](development/requests/v0-l2-measured-rollover.md) implementation reports.

L3–L6 remain required before another private M5 attempt. Historical M1–M4 receipts
retain their original meaning. M5 remains inactive, unmerged and scientifically
unaccepted; human scientific acceptance is mandatory.

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
Schema 5 is the only operational state supported; no migration is provided.
`resume` explicitly reports that stopped-state recovery/reopening requires V0-L5.
Do not delete old runtime state to bypass ownership reconciliation.

The default human-configured caps are two logical agents sharing 2048 MiB, no swap,
128 process/thread tasks, and one concurrent admitted computation. The human may
set `--memory-mib`, `--max-tasks`, `--max-agents` and `--max-jobs` on a fresh launch.
A persistent investigation slice enforces the aggregate caps. Fixed per-agent
slices divide memory/tasks equally (integer remainder is unallocated). Context
services, MCP helpers, job supervisors and job descendants share those slices.
Replacing a context grants no additional allocation. A logical task retains its
slot while its context is absent; task retirement is not implemented.

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
| `control(action, path, parent, offset, sha256)` | Inspect tasks, read immutable scientific documents, delegate a scoped assignment or freeze independent-check evidence. |

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
disposable conversations; job IDs identify computations. All roles (primary,
delegated researcher, verifier and opponent) automatically begin handoff at observed
**55% usable occupancy**. Ordinary completed turns continue the same task in the
same thread. A checkpoint validates saved science and a handoff, confirms old
service closure, captures immutable versions, and starts a fresh native thread.
Objective, workspace, parent, role, research/review phase, slot, cumulative observed
usage and admitted jobs remain. Other agents and jobs continue within the same grant.
No compaction, old-thread resume or conversation replay is used.

The app-server notification `thread/tokenUsage/updated` supplies `threadId`,
`turnId`, `tokenUsage.last.totalTokens`, `total` and `modelContextWindow`.
Following the established controller's Codex display convention:

```text
occupancy = max(0, last.totalTokens - 12000) / (modelContextWindow - 12000)
```

Windows of 12,000 tokens or less use the raw ratio. The native window is the
reported model window; the documented display baseline determines its usable
portion. Values above 100% remain visible. Each context retains its first trigger,
latest measurement, maximum observed occupancy, provenance and native cumulative
counters. The fixed runtime threshold is unavailable to model tools. Observation
can lag and checkpointing consumes tokens: this is a measured trigger, not a hard
no-overshoot promise. Cumulative token spending and account quota are separate.
`inspect` reports each explicitly; spending/quota caps remain unavailable until L3.

Before substantial execution, a restricted intake turn must acquire reliable
telemetry. Missing/invalid observations block new computations and assignments;
one focused recovery turn may reacquire supported native telemetry. The existing
thread-bound native request trace also records distinct `inference_started` request
references, independently of tool-declaration deduplication. Starting another
inference without the preceding usage report blocks admissions and interrupts the
active turn for bounded recovery. Duplicate or injected usage cannot credit later
inferences; a fully measured recovery turn establishes fresh coverage. A late
valid report leaves the recovery state and interruption event latched until that
bounded recovery succeeds; ordinary turns cannot bypass it. These
request counts check measurement freshness; occupancy still comes solely from the
native length/window fields. Completed turns also require per-inference reports.
An unchanged valid sample
during a long job wait has no wall-clock expiry. Intake/recovery and checkpoint
turns have 90-second operational bounds; interruption completion has a 15-second
bound. Failure preserves partial science, records operational failure and cleans
owned work. These bounds never establish scientific completion or investigation
work allowances. One handoff repair is permitted; successor failure is not retried
indefinitely. Scientific COMPLETE/STOP and weekly reserve remain later increments.

`pause` latches the admission block and interrupts all owned contexts and jobs,
then publishes available drafts and reports actual cleanup. Current context drafts
and job-specific draft batches are separate. Failed publication cannot turn
confirmed process cleanup into uncertainty, and failed saving cannot disable
cleanup. A later successful cleanup retry finalizes the same context record, clears
its attachment and releases its private resources; the admission block stays latched.
An unsuccessful acknowledgement retains the request and failure evidence.
The runtime can clean recorded services after a foreground exit; it does not resume research
from stopped state or promise controller-crash continuation.

## Scientific files, references and independent checks

Scientific notes and handoffs use Markdown; code and data keep ordinary formats.
`write_draft` paths are project-relative. Save each handoff at exactly
`handoffs/<logical-task-id>.md` (`handoffs/primary.md` for primary), including for
delegated researchers and opponents. The tool creates missing parent directories;
other delegated notes stay under the task's `work/tasks/<logical-task-id>/` workspace.
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

`check`/`tasks` include available document IDs. Successor intake includes the full
validated handoff with its exact ID/hash and linked artifact versions, independently
of list pagination. Link earlier versions with `[description](document:ID)`.
Handoffs require exact identity, Objective, Parent question (literal `None` for
primary), Phase and Role, plus Completed, Artifacts, Assumptions, Unresolved, Next
action and Jobs sections. Quote multiline objectives with `> ` so embedded Markdown
headings remain inside the Objective section. Delegates also provide Interrupted
computation and Resume or reconsider. Opponents preserve Review history and
Objections; this role has no L4 terminal authority. Structural validation establishes
usability, never scientific correctness.

Every surviving job needs its ID, scientific purpose, outputs/checkpoints and
`job_status`/`job_wait`/`job_cancel` guidance. The runtime retains authoritative
command/cwd/status/deadline records in `job-handoff.json` and successor intake,
reconciles each active/uncertain job under the job lock and blocks new computations
until the successor inspects each inherited active job by ID. Ordinary artifact
hashes are bounded file observations; changing job outputs are not immutable
evidence. Exact captured Markdown versions remain immutable.
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
When publication spans rollovers, the latest valid descendant draft for each path
supersedes its pending ancestors; earlier immutable snapshots remain available.
Job and context batches share this publication boundary. A context's scientific
draft takes precedence over its own jobs' drafts at the same path; a successor's
job can update a predecessor's science.
Before any batch publishes, canonical edits since the owning logical context's
baseline are checked again. This includes human corrections made after attachment
and before a job captures its own baseline.
Navigation is regenerated once per logical task after the batches are settled.
Successor `input_changes` also lists observed scientific Markdown changes;
`science_changes` retains their current canonical hashes and earlier baselines.
Unresolved human edits stay protected across pending successors, including edits
made before attachment. Reading an older snapshot never acknowledges those edits.
Inspect the current canonical text, save an incorporated revision with `write_draft`,
then call `control(action="incorporate_edit", path="work/NOTE.md", sha256=HUMAN_HASH)`.
Use `null` for an observed deletion. The acknowledgement binds that human version
and that exact saved draft: another draft change requires a new acknowledgement.
Stale hashes, protected inputs and other tasks' workspaces are rejected. Before
accepted publication, the human text is retained under `handoffs/preserved/`.
Without valid incorporation, human text remains canonical and the latest proposal
is retained under `handoffs/proposed/`. Version checks record explicit incorporation;
scientific adequacy remains the researcher's responsibility.
The same checks protect job-produced Markdown, even when the job was launched
after the human correction. To incorporate a job revision, save the exact revision
with `write_draft` and acknowledge it as above. A job's fresh baseline does not
acknowledge an unresolved human edit.
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
freezing evidence. This is an independent scientific check. The internal opponent role preserves
review phase and objections through rollover; invocation and terminal decision
protocols require V0-L4. Old response/closure protocols
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
is not an aggregate disk quota. Native context measurements trigger rollover; no
spending cap or weekly quota reserve is claimed.

## Verification

Routine checks disable all paid gates:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

When the declared MCP dependency is supplied externally, append its existing
installation to `PYTHONPATH`; do not replace it to conceal an environment issue.
The old timed M1–M4 live harnesses reject enabled use; their evidence parsers remain
covered. Keep M1–M5 and the accepted L1 native gate disabled for routine checks.
The L2 native gate must inherit the authorized host bus and native file credentials:

```sh
RESEARCH_PIPELINE_V0_L2_NATIVE=1 \
RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR=/fresh/private/l2-validation \
PYTHONPATH=src:/existing/mcp/dependencies python -W error::ResourceWarning -m unittest tests.test_v0_l2_native -v
```

This public fixture runs primary/researcher/opponent scenarios sequentially with
unchanged default caps. Native agents derive and continue a quadrature analysis;
a real admitted numerical job spans automatic rollover while another agent works.
The trusted harness injects labelled 55% telemetry through the production trigger;
native measurements and spending remain separate. It checks preserved identities,
original 7200-second job deadline, actual service coexistence, successor inspection,
output collection, model-written science and explicit pause/cleanup. It does not
prescribe scientific conclusions or certify science from structural assertions.
Enabled missing prerequisites fail visibly with retained receipts. This Writer's
missing authorized bus prevents native evidence; trusted final/combined must supply
it before L2 acceptance. See the L2 report for exact invocation and failure receipt.

The first invocation creates the requested output directory with mode `0700`.
If that directory already exists, each invocation reserves a fresh private sibling
with the same basename as a prefix. Existing receipts and evidence are retained.
Files, symlinks (including ancestors) and unusable parents are rejected. The fixture
prints its actual output path immediately; its receipt records both requested and
actual paths. Final and combined checks can inherit the same destination and still
execute independently with distinct receipts.
