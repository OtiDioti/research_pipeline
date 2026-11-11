# Research Pipeline — persistent scientific investigations

A Python/Linux CLI runs a primary Codex researcher, optionally with bounded delegated
researchers and independent verifiers, in a scientific project. It reads human questions and evidence, asks the researcher to plan, assess
primary literature, derive and compute, and saves ordinary linked Markdown and
reproducible scientific artifacts. `start` stays in the foreground; `inspect` uses
saved files and needs no model access. `resume` continues the same investigation
from a validated checkpoint in fresh conversation context.

The **M1 minimal scientific loop has been demonstrated** in two real isolated
Codex quadrature investigations. Prior enabled final and pre-merge suites each
passed all 34 tests, including 18 numerical estimates, bounded reproduction
agreeing within `rtol=atol=1e-12`, protected inputs and confirmed service cleanup.
The [evidence assessment](development/requests/m1-implementation.md#m1-live-evidence-closeout)
examines the actual plans, retrieved literature, derivations, code and preliminary
findings, and identifies the preserved demonstration paths and pipeline review gate.
This establishes a bounded capability demonstration, without certifying novelty
or overall scientific competence.

M2 implementation now supports checkpoints, foreground resumption, full live pause,
human direction, note-edit reconciliation and automatic primary rollover. The
**M2 live demonstration passed** in both enabled final and pre-merge verification:
each suite passed 85 tests with only the separate M1 live gate skipped. Both real
investigations preserved baseline data and human edits, adapted the plan, continued
the same logical task in a distinct native session after an acknowledged rollover,
reproduced the successor computation in isolation, and confirmed service cleanup.
M3 supports dependent research and separate independent verification with a finite
exchange, described below. **M3 acceptance passed** in enabled final and combined
verification, and integrated locally at `034d9a9`. Each suite passed 176 tests with
only the separate M1/M2 paid gates disabled. M4 now implements explicit reference
navigation/retrieval and locally validated reusable tools. **This M4 increment passed**
enabled final/combined verification and integrated locally at `37f35d6`: both suites
passed 210 tests with only the separate M1–M3 paid gates disabled.
**M4 job controls and reporting also passed** enabled final and combined verification
and integrated locally at `8f275fb`: each suite ran 237 tests with only the separate
M1–M3 paid gates disabled. Both actual investigations exposed the six bounded
adapter operations, critically reused prior science and tools, reproduced all 18
numerical rows in production isolation, preserved inputs and confirmed cleanup.
The [implementation and recovery report](development/requests/m4-job-controls.md)
describes the bounded execution surface and its disclosed limitations. **M1–M4
engineering milestones are accepted.** The researcher has supplied the M5 question,
Valvo manuscript and six-band notes in `research_example/starting_evidence/`.
The first M5 increment investigates the mechanisms contributing to linear light-hole
spin–orbit interaction. Its first live attempt saved draft derivations and numerical
artifacts, then stopped without a usable rollover handoff. Scientific continuation,
independent criticism and isolated reproduction remain incomplete; see
[the current checkpoint](STATUS.md) for recovery state. M5 still requires human
scientific acceptance.

## Authorized reference retrieval

Authorize each source explicitly on the **target** investigation, before `start` or
while stopped. Nothing scans the user's home or discovers projects implicitly:

```sh
research-pipeline reference add /path/to/new-investigation prior /path/to/prior-project
research-pipeline reference list /path/to/new-investigation
research-pipeline reference browse /path/to/new-investigation prior outputs --max-entries 50
research-pipeline reference search /path/to/new-investigation 'convergence' --source prior --max-results 30
research-pipeline reference read /path/to/new-investigation prior outputs/REPORT.md --start-line 1 --max-lines 100
research-pipeline reference remove /path/to/new-investigation prior
```

All commands return JSON. The human-controlled `.research_pipeline/references.json`
contains only `{"version": 1, "references": {"prior": "/absolute/path/to/prior-project"}}`.
Aliases start with a letter and contain letters, digits, `_` or `-` (up to 64
characters). Re-adding the same alias/path is idempotent; remove an alias before
replacing its path. Authorization changes acquire the existing investigation lock,
recover stale ownership and require confirmed cleanup. They cannot change an active
investigation. Invalid registrations leave existing authorizations intact. A later
missing or unsafe reference stays recorded with its reason; other available sources
and saved science remain usable. Malformed registries fail before research launches.

Each fresh primary, delegated or verifier session gets a current read-only catalog
at `/run/research-references.json`, scientific source entries at `/references/ALIAS`,
and a standalone helper sharing the CLI retrieval implementation:

```sh
python3 /run/research-references.py list
python3 /run/research-references.py browse prior outputs --max-entries 50 --offset 0
python3 /run/research-references.py search 'convergence' --source prior --max-results 30
python3 /run/research-references.py read prior outputs/REPORT.md --start-line 101 --max-lines 100
```

Scientific Markdown may cite `/references/ALIAS/relative-file`; deliverable validation
resolves these through the current authorization and rejects missing or unsafe sources.
For links usable outside isolation, prefer the helper's original `source_uri` and
retain the alias, source path and observed hash. Reference citations do not replace
the report's required link to local computational code or data in `work/`.

Browse lists immediate entries, types and sizes; source `FOLDER_CONTENT.md` files can
also be read. Search streams actual UTF-8 file contents, including Markdown, text,
scripts and structured text, using **literal, case-sensitive** line matching.
Matches include original root, alias, relative file, one-based line and bounded
excerpt. Read returns paginated numbered lines and the SHA-256 of the observed
complete file, rejecting changed or disappeared versions. `next_line` / `next_offset`
continue pages. Result/entry/page limits accept 1–1000; read lines are clipped at
2000 characters and search excerpts at 500. Truncation and text clipping are explicit.
Binary/PDF extraction, OCR and semantic search are unsupported. Errors, unreadable
files and invalid UTF-8 make search `incomplete`; an empty incomplete result cannot
establish that a term is absent. Search stops at its result limit. At most 100 error
details are displayed, with the full `error_count` and explicit `errors_truncated`.

Source roots cannot overlap the target in either direction. Symlinked roots or
ancestors, links and special files in exposed subtrees are unsupported; an unsafe
subtree disables that reference conservatively. All hidden top-level entries,
including `.research_pipeline`, `.git`, `.codex` and `.agents`, are excluded.
Paths cannot traverse upward, be absolute, or enter those private roots. The
controller mounts individual non-hidden entries read-only, preserving source files
and indexes; it never grants writable reference directories. Reference preparation
uses the existing deadline and polls the foreground owner's live services and pause
requests while enumerating and validating entries. Services and checkpoint
acknowledgements continue to be processed during slow preparation. Resume intake is
registered in recoverable cumulative accounting before traversal: failures,
interruptions and timeouts consume elapsed allowance, while successful preparation
transfers into the session interval without a second charge. Scientific retrieval
shares the session's resource and suspension boundaries. Authorization fingerprints
and catalogs survive intake
snapshots and checkpoint interpretation without hashing entire source projects.

**Retrieval is not endorsement.** Reference papers, `AGENTS.md`, scripts and tool
descriptions are scientific evidence, never operational authority. They cannot
change target questions/instructions, approve execution/dependencies or expand
access/budgets. Unstated or ambiguous source verification is **unknown**; even
checked findings need an applicability assessment for the new question.

For material actually reused, the researcher writes `sources/REUSE.md` through the
normal drafts (delegated/verifier roles use their own workspace's `REUSE.md`).
Each substantive entry records source alias/root, relative path, original URI and
observed SHA-256; assumptions and limitations; source verification status and basis;
intended use, applicability, uncertainty and needed checks. Reports and handoffs link
the relevant entry. This is a researcher-authored scientific note, not an automatically
inferred claim status or a log of every browse action. Existing human-edit preservation
and index reconciliation apply to it. Adaptations use permitted local working copies.
When an independent verifier needs exact prior evidence, include the identified local
copy explicitly in the existing frozen packet; live references cannot substitute for
versioned verification inputs. Consequential new conclusions retain independent checking.

Existing cumulative grants and disclosed CPU, spending, occupancy, disk and
missing-telemetry limitations still apply to tools. See the
[M4 implementation note](development/requests/m4-cross-project-reuse.md).

## Reusable scientific tools

A tool is an ordinary directory, usually `work/tools/NAME/`, with `tool.json`,
explicitly listed native runtime/check files and a researcher-authored Markdown
assessment. User-supplied local tools can start in `starting_evidence/`; external
tools must come from an explicitly authorized reference. Discovery never executes
or registers a tool. There is no plugin loader, import scanner or dependency installer.

For example, a user-supplied periodic integration function/script can use:

```json
{
  "version": 1,
  "name": "periodic-quadrature",
  "origin": "user",
  "purpose": "Evaluate periodic integrals with trapezoidal quadrature.",
  "files": ["method.py", "check.py"],
  "invocation": ["python3", "method.py"],
  "dependencies": ["Python standard library"],
  "checks": [
    {
      "description": "Check constant and harmonic integrands.",
      "argv": ["python3", "check.py"]
    }
  ],
  "limitations": "Assess integrand smoothness, grid adequacy and roundoff for each use."
}
```

Descriptions require all these fields; `dependencies` may explicitly be empty.
Payload paths must be ordinary relative files without hidden components, traversal
or symlinks. List every required local runtime/check file. Commands are nonempty argv
arrays, executed directly from the working-copy directory. They do not pass through
a shell. Python functions remain ordinary imports from scientist-written scripts.

Inside an active scientific service, use the immutable helper/context:

```sh
python3 /run/research-tools.py list --candidates
python3 /run/research-tools.py list --source prior
python3 /run/research-tools.py stage --source prior work/tools/quadrature/tool.json --name quadrature
python3 /run/research-tools.py stage --local starting_evidence/my-tool/tool.json --name my-tool
python3 /run/research-tools.py register work/tools/quadrature/tool.json --assessment work/tools/quadrature/ASSESSMENT.md
python3 /run/research-tools.py run work/tools/quadrature/tool.json -- --output /project/work/new-values.json
```

These execution commands are deliberately namespace-local, with no host execution
command. Use the public host `reference browse/search/read` commands for offline
source discovery. Delegated researchers/verifiers stage and register beneath their
own `work/tasks/TASK/tools/` paths. They cannot register or execute a working copy
owned by another task or in frozen inputs. Read-only scientific inputs can be copied
into their own workspace for adaptation.

`list` searches local scientific locations and authorized references. By default it
exposes only matching successful registrations; local registrations must belong to
the current activation. `--candidates` includes unvalidated, malformed, failed and
stale descriptions with reasons. A matching source registration records checks in
its original environment; every imported copy still requires local checks.
Staging copies only the description and declared payloads, refuses collisions,
checks source stability, and preserves original root/alias, paths, hashes and origin
in `SOURCE.json`. Failed staging retains partial files and its failure reason.
Source projects and their indexes remain unchanged.

Write the intended-use assessment at
`/run/research-drafts/work/tools/quadrature/ASSESSMENT.md`: intended calculation,
relevant checks, assumptions, applicability, limitations and uncertainty.
Registration writes a pending `VALIDATION.md` draft before checks, and records
description/payload identities, source attribution, assessment path/hash/scope,
activation, exact commands/cwd, Python/PATH observations, outcomes and bounded
stdout/stderr excerpts with explicit clipping. All checks must succeed without
changing the files or assessment. Missing files, unavailable executables/dependencies,
check failures, interruption or an exhausted deadline leave no successful new
registration. Review failures and fix the local copy before registering again.

`run` requires matching successful checks and the unchanged assessment in the
**current activation**. A fresh context/resume must re-register; dependencies in
`/tmp` may have disappeared. Re-register after changing an environment within a
context as well. Dependencies must be installed only inside the authorized scientific
environment, e.g. a private `/tmp` virtual environment with its explicit interpreter
in argv, within the existing grant. A description grants no installation authority.
Invocation receipts in `runs/*.md` retain argv/cwd, source/validation identities,
bounded diagnostics, outcomes and links to file arguments. Runtime failures retain
partial outputs, code and diagnostic evidence.
After foreground exit, capture drains for at most 0.2 seconds within the existing
deadline. If a descendant still holds an output pipe, the helper closes that pipe
and records `output_drain_incomplete` and the affected clipping flags. The foreground
exit status is retained; detached descendants remain owned by service cleanup.
Malformed validation records appear as ineligible candidates with reasons, while
healthy local and reference tools remain discoverable.

For an agent-developed extension, create `work/tools/study/` with `origin: "agent"`,
an invocation such as `["python3", "study.py"]`, its checks and all dependencies,
including any adapted/imported `method.py`. Explain the retrieved method's attribution,
original verification status and new-use limitations in the description, assessment
and `sources/REUSE.md`; do not relabel a copied user method as an independently
verified result. Validate/register this study before reusable exposure.

Assessments, validation records, receipts and copied Markdown use the normal scoped
drafts and human-edit reconciliation. Markdown used as a runtime input must first
be published through the ordinary checkpoint path; native runtime files exist directly
in the permitted working copy. Link records, `REUSE.md`, code, data and limitations
from reports and handoffs. Explicitly include exact reused artifacts in the existing
frozen evidence packet when independent verification needs them.

Tool checks establish only declared execution observations for intended use. They do
not establish scientific correctness, general applicability or independent claim
verification. Foreground checks/runs inherit the current service's filesystem,
network, memory, process, wall-time and cleanup limits. The helper polls the existing
pause/rollover request and effective deadline; it cannot create another service,
extend the grant or authorize a new reference. Detached descendants remain owned by
the same service and are stopped by the existing whole-investigation cleanup.

## Dependent collaboration

```sh
research-pipeline start /path/to/investigation --max-agents 2 \
  --wall-seconds 600 --memory-mib 2048 --max-tasks 128 \
  --primary-session-seconds 300 --delegated-session-seconds 300
```

The primary decides whether a dependent question has a scientific benefit. Inside
its isolated session it writes a Markdown assignment draft, for example
`/run/research-drafts/work/ASSIGNMENT.md`, with substantive `## Objective`,
`## Parent question`, `## Scientific benefit`, `## Assumptions`,
`## Requested result`, and `## Artifacts` sections. Relative artifact links resolve
against the assignment's canonical location. The primary submits and inspects it with:

```sh
python3 /run/research-checkpoint-helper.py --delegate work/ASSIGNMENT.md --parent primary
python3 /run/research-checkpoint-helper.py --tasks
```

Task summaries expose `activation_id`, `predecessor_activation`, `saving_reason` and
the scheduled `rollover_at_monotonic`. The primary's routine `--check` prints concurrent
status with a current `rollover_in_seconds` countdown when it has no saving request
of its own. This lets it stage short scientific commands around saving. A child's
`saving_reason=rollover` is visible before handoff publication; the successor's ID and
predecessor relationship remain available if that brief notice was missed. The primary
can check status and perform its chosen calculation within one command to avoid another
model turn before acting. These notices do not request that the primary save.

An acknowledgement identifies a stable `task-...` and `work/tasks/<task-id>/`.
The assignment and referenced private Markdown drafts are copied into that workspace;
canonical scientific inputs stay linked. Only the primary may authorize assignments.
An existing delegated task can be the scientific parent, so scientific decomposition
can be recursive without nested controllers. Full capacity returns a refusal and
launches nothing. There is no pending assignment queue. To retry an unfinished
existing task, the primary submits that task's saved `ASSIGNMENT.md` path with its
original `--parent`; the same logical identity, objective and workspace continue.
On resume, unfinished tasks beyond the available slots stay interrupted for explicit
primary selection. Re-observing a request returns
its recorded outcome, and the helper permits one outstanding request per activation.

Researchers read shared science but write native code/data only within their own
workspace and Markdown only through scoped drafts. The primary cannot modify child
workspaces or handoffs. A child saves `RESULT.md` with methods, assumptions, linked
artifacts, uncertainties, limitations and remaining questions, plus
`handoffs/<task-id>.md`. Its handoff includes logical identity, objective, parent
question, progress, artifacts, assumptions, uncertainty, interrupted computation,
next action, and whether to resume or reconsider. The primary continues useful work,
reads deliveries, and incorporates their implications and retained uncertainties into
its own notes/report with links to each `RESULT.md`. Structural integration checks
require those links; they do not certify the quality of the scientific synthesis.
Unchecked findings remain **preliminary**. Consequential results can receive a separate,
version-scoped independent check through the verification flow below.

The count includes the primary. Every probe/research service receives fixed shares
`floor(memory_mib / max_agents)` and `floor(max_tasks / max_agents)`, with zero swap.
Zero shares are rejected. Unused shares stay unused. A slot is reserved before a
probe and cannot be reused before predecessor/probe descendant cleanup is confirmed.
Concurrent roles share one cumulative active-wall allowance, including controller
work; overlapping durations are charged once. Usage totals sum observed turns from
all roles; missing usage stays unknown. Hard spending, CPU fraction/aggregate time
and reliable context occupancy remain unavailable.

Each role independently uses acknowledged handoff, cleanup, guarded publication and
fresh `codex exec --ephemeral` context to roll over while siblings keep running.
`--delegated-session-seconds` defaults to 300, must exceed 15 seconds, and survives
resume alongside the primary policy and original resource grant. Collaboration
sessions reserve one quarter of their duration for rollover saving, bounded between
15 and 60 seconds, inside the existing session cap. This allows a model turn and
handoff validation to finish without extending the resource grant. A human pause
overrides rollover and retains its shared 15-second saving deadline.
These fixed durations provide **no exact 60% occupancy guarantee**. Billing
tokens are never treated as occupancy. Fresh contexts reload current questions,
instructions, feedback and saved science, retaining task/parent/workspace identity.
Clean child failures preserve partial artifacts and recovery guidance; unconfirmed
cleanup stops further launches. A primary that ends with unfinished children triggers
whole-investigation saving/stopping and an incomplete outcome.

`pause` targets the foreground owner independently of task activations, fans out one
shared saving deadline and confirms all recorded services/descendants stopped.
`resume` recovers all old owned services before reading drafts or launching work.
Crash accounting covers the owner interval rather than an ended primary's lifetime.
Malformed child preparation cannot prevent stopping siblings; accepted science and
older checkpoints survive failed saving/publication. A successful pause may still
report an unusable newest handoff.

Collaboration projects use schema 3 with task records separate from activations and
compact task-tagged session history. The accepted single-agent M2 path remains schema
2 and continues using its existing synchronous controller; existing evidence projects
are not migrated. This intentionally defers the plan's automatic schema-2
normalization rather than replacing the accepted M2 execution path in this increment.
Schema-1 evidence remains inspectable. `inspect --json` exposes task status, deliveries,
integration references, activation identities and cumulative accounting for schema 3.

Engineering coverage includes actual Bubblewrap role separation and live publication
visibility, concurrent service/descendant stopping where the host supports systemd,
and explicit doubles for independent task rollover, parent progress, budgets,
pause/resume, human edits, full capacity and killed-controller recovery. Enabled
`RESEARCH_PIPELINE_M3_LIVE=1` makes unavailable enforcement prerequisites fail.
The opt-in M3 gate below exercises actual Codex science. Code readiness and
disabled discovery do not establish independent scientific verification or M3 acceptance.

## Independent verification and finite disagreement

Within a schema-3 investigation the primary prepares a scientific Markdown packet with
`## Claim and scope`, `## Parent question`, `## Scientific benefit`,
`## Assumptions and approximation regime`, `## Sources and artifacts`, and
`## Reproduction instructions` (parameters and dependencies). Explicitly link every
local evidence file needed, including dependencies of linked Markdown. The packet
can be a canonical primary note or the primary's private draft; other sessions'
private drafts and operational logs are never verification input.

```sh
python3 /run/research-checkpoint-helper.py --verify work/PACKET.md --parent TASK_ID
python3 /run/research-checkpoint-helper.py --tasks
```

The verifier gets a new logical ID/workspace and a fresh native context. Its parent
is the research task checked; the primary remains the assigning owner. Only supplied
evidence is copied into `work/tasks/<verifier>/inputs/initial/`, with source paths,
SHA-256 hashes and a reviewed version in `manifest.json`. Markdown links are rebased;
reproduction commands are preserved for the verifier to adapt and record explicitly.
Admission executes no evidence. Inputs must be regular files: at most 128 supplied
files, 16 MiB each and 64 MiB total, within the original investigation deadline.
The entire `inputs/` tree is read-only, including code/data. The verifier writes its
own checks in its workspace and Markdown through scoped drafts, without editing
original research or shared synthesis.

The verifier independently reconstructs or challenges consequential work, preferably
using another method. `CHECK.md` requires `Disposition: checked`, `objection`, or
`inconclusive`, and substantive sections `## Claim and scope`, `## Independent approach`,
`## Observations`, `## Objections and limitations`, and
`## Reproduction or analytical evidence`, with saved evidence/check links. Scientific
reasoning and actual observations establish the check; these structural requirements
cannot certify its quality. An inconclusive initial check closes as preliminary.
At acceptance, the controller records SHA-256 fingerprints of every explicitly linked
local check artifact, including code, data and supporting Markdown. Changing or deleting
these artifacts requires reassessment and prevents continuation or successful integration.
Preserve accepted evidence and save revised calculations under new paths.

An initial objection saves a handoff and **releases its service and agent slot**.
It stays stopped on resume while awaiting the primary. The primary can continue
other work, decline further exchange, or submit **one** response/revision:

```sh
python3 /run/research-checkpoint-helper.py --respond VERIFIER_ID --response work/RESPONSE.md
python3 /run/research-checkpoint-helper.py --close-verification VERIFIER_ID --reason work/CLOSURE.md
```

A response needs `## Response to objections`, `## Revised claim`,
`## Sources and artifacts`, and `## Reproduction instructions`. Its explicitly supplied
revised evidence is frozen separately under `inputs/response/`; the original packet
and accepted `CHECK.md` remain unchanged. Acceptance commits the single exchange
allowance before launching the same logical verifier in a fresh context. A justified
targeted test can be performed in the response or re-examination, within the existing
grant. The verifier saves `REEXAMINATION.md` with the same check sections/disposition.
Resolved work closes checked for the reviewed version; unresolved objections or an
inconclusive final check close disputed with both arguments retained. Declining an
awaiting exchange also closes disputed and links the primary's `CLOSURE.md` explanation.
Closure needs no slot; a new check or re-examination needs a free slot. Full capacity
consumes no exchange allowance and creates no pending work.

Repeating the same request returns its saved outcome. Resubmitting a packet identifies
its existing check, without another exchange budget; materially different future claims
need a new packet with scientific explanation of the relationship. Retrying a failed or
interrupted check with the same packet/accepted response preserves its phase and frozen
version. Closed checks cannot reopen. Pause and crash recovery retain accepted phases,
responses and allowances. Preparing and rolling-over verifiers keep their reservations;
waiting verifiers consume none. Both verifier phases use the same acknowledged rollover,
fresh context, cumulative accounting and full cleanup as researchers.

The primary integrates the check, accepted response and final check/closure through
ordinary Markdown links, explaining scope, assumptions, uncertainty, objections and
superseded conclusions. Disputed work can be integrated without preventing unrelated
research from completing. Labels apply to the frozen version, never automatically to
later original edits. Changed frozen packets or accepted reports require reassessment;
human edits are preserved. `--tasks` and `inspect --json` expose phase, disposition,
reviewed versions and evidence/report paths. Original changes detected at integration
are recorded and require an explicit version limitation in the synthesis.
Structural integration validation checks the outcome label, links to all accepted
exchange stages and evidence integrity. It does not require specific words in the
scientific explanation or assess whether that explanation is scientifically adequate.

## Installation and prerequisites

Use Python 3.11+ on Linux, Bubblewrap, systemd with an already available user service
manager, and a cgroup v2 hierarchy delegated to that manager. Install a recent
**standalone Linux Codex distribution** (including sibling helpers). npm/Node wrapper
installations are not supported by this small launcher. CLI options were inspected
with `codex-cli 0.167.0`, also used in both successful isolated demonstrations.
Their receipts record the research model as **backend default**, without a resolved
model identity.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/research-pipeline --help
```

Install Bubblewrap/systemd through your Linux distribution. In an authorized login
session, configure Codex native authentication with `codex login` and file credential
storage (`cli_auth_credentials_store = "file"`). The launcher copies only the native
`$CODEX_HOME/auth.json` (default `~/.codex/auth.json`) to a private temporary Codex
home, excludes configuration, and deletes the copy afterward. Keyring-only login,
inherited API keys, custom providers/proxies and inherited connectors are unsupported.
Credential refresh in the temporary home does not update the host login.

Check the existing execution environment:

```sh
codex --version
codex exec --help
systemd-run --user --wait --pipe --quiet /usr/bin/true
```

A successful `/usr/bin/true` service checks bus access, but does not establish
resource enforcement. The service hierarchy must expose the cgroup v2 `memory`
and `pids` controllers, including `memory.swap.max`. Preflight verifies their
actual settings; missing controllers or unapplied limits block execution.
CPU controller delegation is not required. CPU fraction and aggregate CPU time
are not capped.

Do not route through another user bus, disable an enclosing sandbox, or change
permissions to evade restrictions. If the user manager, native authentication, PID/user
namespaces, controlled Codex configuration or resource controllers are unavailable,
`start` records a blocker and stops. It has no unisolated fallback.

## Start and inspect

Use an ordinary project directory, separate from this product checkout:

```sh
mkdir -p /path/to/investigation/starting_evidence
# Write the human questions in starting_evidence/RESEARCH_QUESTIONS.md.
# Add relevant notes, papers, code or datasets and optional root AGENTS.md.
.venv/bin/research-pipeline start /path/to/investigation \
  --wall-seconds 600 --memory-mib 2048 --max-tasks 128 --primary-session-seconds 300 \
  --job-runtime-seconds 60 --max-jobs 1
.venv/bin/research-pipeline inspect /path/to/investigation
.venv/bin/research-pipeline inspect /path/to/investigation --json
```

`--codex /absolute/path/to/codex` and `--model MODEL` select the installed binary
and account-supported model. Without `--model`, Codex selects its backend default;
the controller does not assert a particular resolved model. All limits must be
positive and finite.

Scientific commands use the `research_jobs` stdio MCP adapter. The installed `mcp`
dependency and Python runtime are mounted read-only inside each original research
service. Trusted adapter/supervisor launches exclude the research working directory
and user site from Python's import search (`-P -s`); scientific argv retains ordinary
workspace imports. Codex retains `workspace-write`, ignored inherited configuration/rules,
ephemeral contexts and native file authentication. Strict configuration disables
stock command-launch tools, apps, plugins, image generation and backend agent
spawning, including the separate native Code Mode collaboration gate. The adapter
namespace is direct-only, so its six actual schemas appear in the model request.
Its noninteractive approval
policy preauthorizes only the adapter's six allowlisted operations; job admission,
ownership, scoped Markdown writes and original resource limits still apply.
Each backend records its native request trace inside its temporary private home,
which scientific jobs cannot access. On closure the controller retains only the
actual top-level request tools, `additional_tools` declarations and native
session/request provenance in
the session's private `native-tools.json`; full prompt/response traces are removed
with the temporary home. This uses the installed Codex native rollout trace
(`CODEX_ROLLOUT_TRACE_ROOT`, schema 2), including the nested code-mode tool
declarations. It adds no inference session. `codex exec --json` does not expose
the code-mode catalog output, so asking the model to print it cannot establish
this evidence. Missing, incomplete or unsupported trace metadata remains unverified.
Both locations are examined, including nested Code Mode declarations; changes in
either location create a new observation. Earlier receipts that omitted top-level
tools cannot certify complete capture. Successful adapter calls cannot substitute
for declared schemas. The enabled M4 host gate must observe fresh session-bound
declarations, compare all six direct schemas with the adapter and reject any
unrestricted or unknown execution route or missing controlled tool.
A credential-free loopback diagnostic exercises the installed strict configuration,
real stdio adapter, request capture and namespace mounts without inference.
It is diagnostic evidence; fresh enabled controller-host M4 science, reproduction,
resource/cleanup checks and LOCAL integration remain required for closeout.
See [the implementation record](development/requests/m4-job-controls.md).
Config/features listings and controller test doubles do not establish capability.
The validator recognizes the native goal lifecycle (`create_goal`, `get_goal`,
`update_goal`), read-only agent listing/waiting, clock and web utilities by explicit
names. Native goals do not change investigation grants or service deadlines.
Validation reports all unsupported declarations and missing adapter operations
together. Agent spawning/messaging, image generation and unknown routes remain
unsupported. Omitted adapter declarations cannot be inferred from successful
calls or a description advertising deferred tools.

The agent uses `job_run(argv, cwd, runtime_seconds?, yield_seconds?)`; for example,
`job_run(["python3", "calculate.py"], "/project/work")`. It may explicitly run
`["/bin/bash", "-c", "..."]`, edit/debug its own code and install scientific
dependencies in its activation's `/tmp`. Scientific scripts remain ordinary
researcher-authored files and do not pass through coding_pipeline. Shell pipelines,
threads and detached descendants all belong to the same admitted job. Code mode
orchestrates these tools inside the backend; in-process model/tool orchestration
remains part of the aggregate service grant, rather than an admitted argv job.

`--job-runtime-seconds` defaults to **60 seconds** and `--max-jobs` to **1 across
the investigation**, including primary, researchers and verifiers. A caller may
request a shorter runtime. Preparation consumes that runtime, and the effective
deadline is the minimum of admission plus runtime, role-session deadline and the
original investigation deadline. A trusted supervisor outside each job's nested
Bubblewrap PID namespace enforces its timer independently of other preparation
or MCP calls. All supervisors and descendants remain in the original service's
memory, zero-swap, task and wall grants. Concurrency counts argv jobs, not threads,
CPU fractions or researcher slots.

`job_run` returns a terminal observation or a job ID. `job_status`, `job_wait`
(at most five seconds per call) and `job_cancel` inspect or stop owned work.
Primary status also shows aggregate reservations. Full capacity refuses immediately:
`Job capacity exhausted (1/1); no command launched.` There is no queue or retry.
A reservation persists through preparation and stopping. Capacity is released only
after namespace teardown is confirmed; exited parents and closed pipes are not
completion evidence. Unconfirmed cleanup retains that reservation and stops the owning role using
the original service cleanup authority. Runtime expiry reports
`Job runtime exhausted; partial artifacts retained.` Missing executables and failed
commands retain bounded stdout/stderr and useful files.
`job_status()` returns up to 32 compact summaries, prioritizing active jobs and then
recent finished jobs, with `jobs_omitted` and `active_jobs_omitted` counts. Output
buffers are separate: `job_status(job_id)` returns a full retained result, including
earlier activations for the primary. History truncation does not change aggregate
capacity counts, and reading an archived result does not authorize canceling it.

For the investigation started above, the agent can run
`job_run(["python3", "-c", "print(sum(i*i for i in range(10)))"], "/project/work")`,
then call `job_status()` to see its jobs and the shared `budget_report`, even at full
capacity. The report copies the original configured limits and shows cumulative
spent/remaining active seconds, reservations and observed completed-turn model
counters. `observed_at` identifies the controller observation; elapsed time refreshes
about once per second. All roles see the same investigation totals, distinct from
their individual session deadlines. Missing status, unsettled intervals and missing
usage remain unknown; waiting, new jobs, checks and fresh contexts add no allowance.
At a reached limit, save useful progress and stop the affected work.

The human can read the same budget in the compact `inspect` summary or the structured
`inspect --json` diagnostic output shown above. To suspend and later continue:

```sh
.venv/bin/research-pipeline pause /path/to/investigation
.venv/bin/research-pipeline resume /path/to/investigation
.venv/bin/research-pipeline inspect /path/to/investigation
```

Resume retains the job limits and cumulative allowance. Inspection is read-only and
reserves no slot. Configured limits describe authorization; they alone do not prove
a service is running or that an enforcement check passed. Model counters cover emitted
completed-turn usage observed so far, with a completeness flag; missing usage is not
zero. Spending and context occupancy remain unknown, and fixed session rollover is
the conservative fallback. These operational observations accompany researcher-authored
Markdown status, findings, provenance and handoffs.

Reusable-tool discovery, staging, registration and invocation commands shown
elsewhere in this README run through `job_run`. Declared checks/runs inherit that
job's slot and deadline; helper execution outside an admitted job fails. Dependency
environments persist across jobs in the same activation, while fresh contexts still
require local tool revalidation. Interrupted pending validation/receipts remain
unsuccessful or unknown, with the controller's job diagnostics recording termination.

Saving does not require a job. `write_draft("handoffs/primary.md", content)` saves
scoped Markdown; `control(action="check"|"acknowledge"|"tasks")` handles checkpoints.
`control(action="delegate"|"verify", path=..., parent=...)`,
`control(action="respond", target=..., path=...)`, and
`control(action="close", target=..., path=...)` replace the checkpoint-helper shell
examples elsewhere in this README. New science is blocked during saving; these
fixed operations remain available within the existing saving deadline. They
cannot launch commands. Existing human-edit reconciliation and scientific Markdown
publication still occur after full owned-service cleanup.
`--max-tasks` counts processes and threads, including backend overhead.
The research service has no swap allowance (`MemorySwapMax=0`).
The controlled Codex launcher enables code mode and its host, as required by current
model metadata. Inside backend services, `TOKIO_WORKER_THREADS=1` bounds runtime
thread-pool overhead so the backend and its helpers can share the process/thread
grant. This does not cap scientific CPU use or increase the grant; sandbox and
model selection remain as configured.

`start` accepts only fresh projects: existing scientific directories/status/indexes or a
previous run are conflicts. Symlinks/special files in the supplied project and symlink
ancestors are rejected. Use a plain project without `.git`, `.agents` or `.codex`
tool configuration. Questions and optional instructions must be UTF-8, nonempty
questions, and at most 256 KiB each; intake supports up to 10,000 evidence files.
Optional root `HUMAN_FEEDBACK.md` follows the same UTF-8/256 KiB limit and remains
distinct from questions and scientific conclusions. Keep human inputs stable during
a run; detected changes require reassessment on the next activation. Only explicit
human `redirect` and `feedback` commands write those inputs.

## Pause, continue and redirect

From another terminal, suspend a foreground investigation before editing or redirecting:

```sh
research-pipeline pause /path/to/investigation
research-pipeline redirect /path/to/investigation --questions-file /path/to/new-questions.md
research-pipeline feedback /path/to/investigation --file /path/to/feedback.md
# Alternatively edit questions, optional AGENTS.md, HUMAN_FEEDBACK.md or scientific notes.
research-pipeline resume /path/to/investigation
research-pipeline inspect /path/to/investigation --json
```

`pause` needs no model authentication. It requests suspension from the current owner
and waits up to 60 seconds for confirmation, including release of the foreground
project lock. The researcher has a fixed 15-second saving grace, bounded by the
remaining investigation deadline. It checks a read-only request channel, writes
draft progress and a handoff, and invokes a small mounted checkpoint helper as its
final command. The controller validates the saved handoff and referenced drafts or
native artifacts, persists preparation, and acknowledges it. A one-second exit grace
inside the original saving period allows the researcher to finish and emit usage.
Preparation checks the same saving deadline while validating links and reading or
hashing files in chunks; expiry abandons preparation and requests service stopping.
Then whole-service cleanup stops all research, computation and checkpoint helpers.
A request during startup/preflight cancels startup without launching inference.

Zero exit from `pause` means confirmed suspension with no intentional work left
running, including detached descendants. It does not guarantee a new checkpoint:
ignored requests, long computations or invalid drafts are forcibly stopped, and
inspection reports whether a fresh checkpoint, an older checkpoint or only ordinary
artifacts can be used. Saving and shutdown consume the cumulative active allowance.
Duplicate requests reuse the same request and cannot extend saving time. A confirmation
timeout returns nonzero and leaves the request pending; suspension is not confirmed.
An ownership conflict reports that another foreground owner replaced the requested owner.
Automatic session changes within that same owner are followed by the pause requester.
Pausing an idle investigation is idempotent; pausing a stale owner first requires
confirmed cleanup of recorded services. Previous failures and checkpoint errors remain
available in saved state. Unconfirmed cleanup prevents publication and further work.

`redirect` replaces the questions; `feedback` appends a dated, distinct human
contribution. These commands require the exclusive project lock and confirmed
quiescence. Direct human file edits remain supported. Resume reloads current
questions, optional instructions (including removal), feedback and evidence inventory.
It supplies the previous accepted intake and handoff, changed/deleted note paths and
pending conflicts so the researcher can revise added, changed and removed objectives,
preserve unaffected findings and reconsider affected assumptions. It does not delete
artifacts when questions change.

Limits are immutable across activations: `--wall-seconds` is the investigation's
**cumulative active-work allowance**, covering startup, research and finalization.
Time while fully stopped between foreground invocations is free; automatic
inter-session preparation is charged. Resume accepts `--codex` and `--model`, but no
budget-increase flags. Missing usage/native identity is explicitly unknown; observed
turn usage accumulates without adding cached input tokens a second time.
Inspection exposes cumulative usage, completeness, remaining active time, checkpoint,
session policy, rollover outcome, session identities and pending reconciliation.
It also reports spent active time, persisted job limits, reservations and each
job's state/reason. Live accounting includes the current observed controller
interval; lost-controller intervals remain unknown until recovery settles them.
JSON inspection includes the separate operational `budget_report` and `jobs`;
these do not replace scientific status, findings, provenance or handoff prose.
Supported older schema-2/3 states missing job settings adopt the conservative
defaults after ownership cleanup; continuation cannot increase any allowance.

Each activation has a stable investigation ID and logical researcher `primary`,
and fresh activation/native session identities (native identity only when emitted).
Interrupting the foreground CLI requests bounded whole-service cleanup; use `pause`
for cooperative saving.

## Automatic primary context rollover

`--primary-session-seconds` defaults to **300**, must be finite and greater than the
15-second saving reserve, and is persisted separately from investigation resource
limits. Existing schema-2 investigations without a policy receive this default
on resume. Each research session's duration starts after backend inspection,
preflight and authentication. The effective service/controller deadline is the
earlier of launch plus this duration and the cumulative investigation deadline.
When the session duration constrains execution, the controller requests saving
15 seconds before that deadline. Saving, cleanup and preparation consume the
original investigation allowance.

This Codex backend exposes completed-turn billing usage, **not reliable context
occupancy or capacity**. A 60% occupancy default is preferred if reliable telemetry
becomes available; the fixed session duration is the current configurable fallback.
It provides no exact 60% guarantee and never treats cumulative tokens as occupancy.

Rollover uses the same checkpoint helper as pause. The controller requires an
acknowledged handoff, confirmed whole-service cleanup, unchanged prepared files
and a valid published checkpoint before launching a successor. Current questions,
instructions, feedback and note changes are reloaded. Ordinary scientific conflicts
are carried for reconciliation; a conflicting handoff blocks continuation.
The same foreground command retains the exclusive project lock, investigation,
logical researcher `primary`, workspace, ownership nonce and cumulative limits.
Each successor gets a new activation/service, private authentication-only Codex
home and `codex exec --ephemeral` conversation. No transcript or native resume
command is supplied. Repeated nonempty native identities are an error; absent
identities remain unknown and cannot establish live freshness.

Human pause takes precedence, including during saving or successor registration.
Upgrading a rollover request preserves its ID and original grace. Successful pause
stops the entire investigation. Automatic rollover instead continues the same
logical task within the running foreground command.

Ignored/unacknowledged saving, damaged preparation, failed publication or successor
startup stops automatic continuation with an explicit limitation. Inspect the
checkpoint/error and use `resume` after addressing the failure. Unconfirmed cleanup
blocks both publication and further launches. Controller loss at rollover boundaries
uses the same checkpoint recovery; interrupted work and unknown usage are disclosed.
Inspection's `rollover` summary records source/destination activation, checkpoint,
native identities when known, phase and limitation; session summaries retain links,
attempted research/probe service names, cleanup outcomes and observed research
control-group paths for durable cleanup evidence.

Existing scientific Markdown is mounted read-only. The researcher writes Markdown
drafts under `/run/research-drafts`, mirroring final project paths; code/data use
the scientific directories directly. After confirmed cleanup the controller checks
each destination against its activation-start fingerprint before publishing. Concurrent
human edits, creations and deletions win; conflicting proposals go to
`handoffs/proposed/`. On a later activation, intentional replacement of a previously
detected human version first saves that version in `handoffs/preserved/`.
Edited indexes are similarly preserved before navigation is regenerated. The
controller never replaces scientific status prose with operational JSON updates.
Rejected draft batches remain private diagnostics; invalid draft entries cannot
block service recovery or reuse of an earlier checkpoint.

`handoffs/primary.md` records the objective, completed work, linked saved artifacts,
assumptions, unresolved/interrupted work and next action. Checkpoints retain a private
immutable copy and the accepted intake; a damaged newest handoff falls back to the
previous valid copy. A structurally valid checkpoint can retain useful partial work
even when final reports are incomplete. It does not certify scientific quality.

After controller loss, resume first stops the recorded research/probe services and
requires confirmed inactivity. It marks interrupted work and uses saved science;
there is no exact replay guarantee. Without trustworthy service timing it conservatively
charges elapsed real time up to the recorded activation allocation/deadline and marks
accounting uncertain. Unobserved model usage stays unknown. If no valid checkpoint
exists, ordinary artifacts remain available with an explicit recovery limitation.
If the controller dies after preparing a pause handoff, recovery first confirms
cleanup, validates its saved hashes/intake/baseline and attempts the same guarded
publication used at normal checkpoints. Damaged preparation or drafts retain the
previous checkpoint with an interrupted-finalization limitation. Human edits still win.
Pending preparation is retried even if an earlier recovery already recorded cleanup.
Recovery validation, publication and index reconciliation consume the remaining active
allowance. Their accounting interval is saved separately and settled once; if its
controller dies, elapsed time through the next recovery is conservatively charged,
capped at the saved remaining allowance and reported as uncertain.
Schema-1 M1 investigations remain inspectable, but cannot resume; preserved M1
demonstrations are not migrated.

Unconfirmed cleanup leaves active-work accounting pending. Once inactivity is
confirmed, recovery charges the additional interval after the amount already
accounted for, capped at the original activation allowance. Residual work cannot
grant extra time to a later activation.

## Files and status

The researcher writes:

- `work/PLAN.md`: concrete, revisable questions, assumptions, methods and checks.
- `sources/LITERATURE.md`: citations, URLs, access dates, relevance, and explicit full-text,
  abstract-only, secondary-source or inaccessible assessments.
- `work/`: analytical notes, scientific scripts, parameters, data and rerun instructions.
- `outputs/REPORT.md`: linked preliminary findings, limitations and next questions.
- `RESEARCH_STATUS.md`: scientific progress and next directions.
- `handoffs/primary.md`: concise continuation guidance.

The controller initializes root `RESEARCH_STATUS.md`, maintains immediate-entry
`FOLDER_CONTENT.md` indexes, and writes private `.research_pipeline/run.json`,
`run.lock`, the short-lived `control.lock`, and per-activation `sessions/<id>/` directories. Each session retains
bounded `backend.jsonl`/`stderr.txt`, drafts, and accepted checkpoint Markdown.
Its `control/` directory holds ownership-scoped requests/acknowledgements, mounted
read-only to the researcher; `response/` receives untrusted bounded readiness JSON.
Prepared handoff/intake Markdown and small preparation metadata support interrupted
finalization. These operational files cannot change research limits or select services.
Indexes are reconciled at startup and the terminal checkpoint after process cleanup.
The controller does not traverse scientific trees while agent commands can mutate them. Starting evidence is listed in the root index; no
index is written into `starting_evidence/`. Other subdirectories are created only
when the science needs them. Operational diagnostics may contain private scientific
material; keep the project private as appropriate.

Exit codes: `0` completed/inspected/confirmed paused, `2` bad input, conflict or pause confirmation timeout, `3` unsupported runtime
or authentication, `4` backend failure/incomplete artifacts/uncertain cleanup, `124`
wall deadline, `130` interruption. States include `starting`, `running`, `completed`,
`pausing`, `rolling_over`, `paused`, `incomplete`, `blocked`, `failed`, `timed_out`, and `interrupted`. Inspection marks
unconfirmed/stale activity explicitly. Partial artifacts are retained on failure.

Completion requires backend success, investigation-level observed successful command execution,
nonempty required Markdown, a report link to a local computational artifact (code or
data) under `work/`, an explicit scientific status label (preliminary on the single-agent
path), a usable new handoff and confirmed cleanup. These structural checks cannot establish scientific
correctness, literature quality, novelty, or reproducibility. M1 has **no independent
scientific verifier**. Failed experimental commands are retained in telemetry; a
corrected command or useful negative finding is not automatically a failed investigation.

## Enforced boundary and limits

The supported launcher is a systemd user transient service containing Bubblewrap.
It mounts `/project` read-only, overlays only `sources/`, `work/`, and `outputs/`
writable, read-only mounts for existing scientific Markdown,
and a separate writable draft mount; it hides `.research_pipeline/`. System programs/libraries, certificates
and resolver files are mounted explicitly read-only; the host root and home are
not mounted. Temporary storage and Codex home are private. The actual Codex session
uses `workspace-write`, never approval, live literature search, and no inherited
user config/rules, discovered AGENTS instructions, connectors or delegated agents.
Only root project instructions are inserted as authority; supplied sources remain evidence.

The PID namespace, `--die-with-parent`, dropped capabilities, and systemd
`KillMode=control-group` contain descendants, including detached sessions. Cleanup
runs after success, failure, deadline and interruption, with short grace then
SIGKILL. The launcher refuses completion unless service/cgroup inactivity is confirmed.
Systemd enforces aggregate memory, zero swap, tasks and remaining wall time; the controller
also checks a monotonic deadline. Startup uses that same wall budget; bounded service
cleanup may add several seconds. A disposable probe checks protected inputs, permitted
computation, and actual cgroup `memory.max`, `memory.swap.max`, `pids.max`
settings before inference. Missing or nonzero swap limits fail preflight.

Limits that are **not** guaranteed:

- No hard model-token/spending cap or reliable context occupancy. Optional emitted
  turn usage is stored verbatim and never interpreted as context occupancy.
- CPU fraction and aggregate CPU time are not capped. Scientific commands can use
  available CPUs within the shared wall, memory and task limits.
- No CPU/thread allocation per scientific job. Runtime and concurrent argv-job
  limits supplement the original aggregate quotas; there is no queued scheduler.
- A 64 MiB per-file limit and 4 MiB per operational log are **not** a total disk quota.
  Private tmpfs consumes the service's memory allowance.
- Literature/inference networking has no destination filter. No host sockets, user
  home or inherited MCP/connector configuration are supplied. The controlled job
  adapter is platform-owned. The authorized backend's native credentials exist in
  its private namespace; scientific job namespaces do not mount those credentials
  or adapter admission storage.
- Abrupt host/controller SIGKILL cannot finalize status; systemd still enforces its
  lifetime bound. Checkpoint recovery and forced pause can lose uncheckpointed work.
  Concurrent collaboration uses the fixed slot shares described above.

## Checks and demonstration

Tests also run from an uninstalled checkout with `python3 -m unittest discover -s tests -v`.
Shared test setup exposes this checkout's `src/` to the test process and its Python
CLI subprocesses. Install the package as above for normal CLI usage.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m research_pipeline --help
```

Tests distinguish orchestration doubles, actual Bubblewrap enforcement, and actual
systemd/cgroup enforcement. An unsupported-host skip means incomplete acceptance.
`test_continuity.py` checks checkpoint/resume, human edits, direction, cumulative
accounting, stale ownership and a genuinely killed controller with an explicitly
doubled research launcher. `test_pause.py` checks separate CLI pause processes,
duplicate/stale requests, handoff preparation, startup cancellation, fixed grace,
human edits and a real controller SIGKILL after acknowledgement. `test_rollover.py`
checks sequential fresh sessions, current intake, cumulative budgets, failed saving
and startup, pause precedence and a killed controller between publication and launch.
`test_isolation.py`
adds cooperative and ignored-request scientific-worker fixtures through the production
launcher, including closed output streams and detached heartbeat descendants. These
fixtures supply enforcement evidence separate from the paid scientific gates below.
Ordinary tests do not launch inference. The pipeline's integrated-test stage can
explicitly enable the real, potentially paid acceptance run in its existing authorized
host context:

```sh
RESEARCH_PIPELINE_M1_LIVE=1 \
RESEARCH_PIPELINE_M1_OUTPUT_DIR=/absolute/private/request-output/m1 \
  .venv/bin/python -m unittest discover -s tests -v
```

Both variables must be supplied to that process. Enabled acceptance fails on missing
prerequisites; the service/filesystem integration checks cannot skip unavailable
capabilities when either `RESEARCH_PIPELINE_M1_LIVE=1` or
`RESEARCH_PIPELINE_M2_LIVE=1` or `RESEARCH_PIPELINE_M3_LIVE=1` or
`RESEARCH_PIPELINE_M4_LIVE=1`.
Do not give a restricted Writer access to another execution context.

For M2, enable only its dedicated gate (M1 inference remains opt-in separately):

```sh
RESEARCH_PIPELINE_M2_LIVE=1 \
RESEARCH_PIPELINE_M2_OUTPUT_DIR=/absolute/private/request-output/m2 \
  .venv/bin/python -m unittest discover -s tests -v
```

`test_m2_live.py` uses the public start/pause/redirect/feedback/resume/inspect flow.
Codex authors the quadrature derivation, plan, code and data. After detecting live
baseline progress, the test confirms full suspension before changing questions,
instructions, feedback and a derivation paragraph. The same resumed foreground
process must automatically roll over with an acknowledged handoff; a distinct
native session then computes a reserved near-singular parameter study. Numerical
convergence, preservation, current input integrity, indexes, cumulative time/usage
and service inactivity are checked. The researcher-written calculation is reproduced
only through the production isolation launcher.

Bounds are 900 seconds cumulative active work, 240 seconds per research session
(including saving), 60 seconds for reproduction and 1500 seconds overall including
failure cleanup. The test reserves cleanup time and rejects extra research sessions.
Fixed-duration rollover is a conservative fallback for unavailable occupancy, with
no exact 60% guarantee; spending and CPU limitations above still apply.
Each invocation retains a fresh private `m2-live-*` directory with exact command
arguments/logs, phase snapshots, scientific evidence and `receipt.json`, including on
failure. The unittest report prints scientific excerpts, numerical observations,
human-edit preservation, accounting and cleanup results; transcripts remain private.
These structural and numerical observations support manager assessment, not independent
scientific verification. Disabled discovery starts no inference or demonstration.
Enabled missing output/prerequisites fail instead of skipping. Writer/Reviewer code
readiness transfers to Architect completion and existing controller final tests;
no additional implementation milestone is required to collect host receipts.

The accepted M2 final demonstration (`m2-live-e17h2s_r`) and pre-merge demonstration
(`m2-live-4_euwf6h`) are preserved under
`coding_pipeline/logs/manager/m2-persistence-human-direction-rollover-20261110T111256Z-aa5787cf/live-host-acceptance/`.
The pipeline report at `coding_pipeline/logs/20261110T111316_7e4bef43/summary.md`
records passed final/pre-merge verification and local integration at `53a68e1`.
Receipts report about 351 and 359 seconds of cumulative activity, respectively,
with missing model usage explicitly unknown. Fixed-duration rollover does not
establish an exact 60% context threshold. These are bounded engineering and
scientific-continuity demonstrations, not independent scientific certification.

For M3, keep both earlier paid gates disabled and enable only this gate:

```sh
RESEARCH_PIPELINE_M3_LIVE=1 \
RESEARCH_PIPELINE_M3_OUTPUT_DIR=/absolute/private/request-output/m3 \
  .venv/bin/python -m unittest discover -s tests -v
```

`test_m3_live.py` runs one fresh investigation through the production CLI, coordinator,
Codex backend and isolation launcher. Actual researchers author all scientific code,
assignments, derivations, checks, responses and synthesis. For a near-boundary integral
approximation, the primary delegates a dependent quadrature study, continues its own
parameter/error analysis while the child rolls over, incorporates the fresh successor's
reserved calculation, and requests an independent approximation challenge. The gate
submits both the derived near-boundary regime and the exploratory hypothesis of
one-percent accuracy across the parameter study, including the stress case, as
distinct verification subjects. A refuted exploratory extension can receive an
objection while the restricted theorem is confirmed; no false theorem or verdict
is prescribed. The gate requires an actual objection, one response and one
re-examination; a checked-only first
examination is retained honestly as failed demonstration evidence. Final disagreement
may pass with a scientifically explained disputed synthesis and opposing arguments.
The gate does not seed answers, forge helper requests or retry paid investigations.

Bounds are 900 seconds cumulative owner activity, 540 seconds per primary session,
240 seconds per delegated/verifier session, 60 seconds for isolated reproduction,
a 1200-second ordinary-work cutoff and 1800 seconds overall including failure cleanup.
Two simultaneous slots share the original 2048 MiB/128-process grant. At most two
primary contexts, exactly two delegated contexts and two verifier examination contexts
are accepted. Fixed-duration handoff reserves 60 seconds inside these sessions; context
occupancy remains unavailable, without an exact 60% guarantee. CPU/spending limitations
remain as disclosed above. Existing engineering tests also cover verifier rollover.

Every invocation retains a private fresh `m3-live-*` directory, command logs, project
and receipt, including failed runs. Receipts preserve stable task/parent/workspace and
distinct native identities, acknowledged handoff, baseline hashes, successor numerics,
parent calculations between the observed rollover-saving request and successor
calculation, frozen evidence versions, objection /
response / final outcome, cumulative accounting and unknown telemetry, exact commands,
available control groups and confirmed descendant cleanup. Both child and verifier
programs are reproduced through the production isolation launcher from their original
task working directories, recorded with each command in the receipt. Original
accepted evidence is checked again for mutation. Each verifier report explicitly lists
its consequential JSON tables under `## Numerical observations`; every selected table
must satisfy the numerical interface and have a recorded executed calculation.
Initial and new targeted tables are reproduced with their saved scripts and parameters.
Other linked integrity/provenance records retain the platform's authoritative fingerprints
and frozen snapshots, without interpreting optional sidecar assertions as proof.
Numerical observations and scientific
excerpts appear in the unittest report for manager assessment; structural labels or
exit zero alone cannot pass. The real schema-3 CLI pause path additionally has a
three-role production-service test with explicitly non-model engineering workers and
detached computations. It supplies enforcement evidence, not paid scientific evidence.

On a restricted Writer host, enabled missing prerequisites fail and retain diagnostics;
no alternate bus, authentication or unisolated fallback is used. Writer readiness and
Reviewer approval proceed to Architect completion, which must trigger the existing
enabled controller final tests and local integration. Only those successful enabled
checks and their actual scientific observations complete M3 acceptance.

Accepted M3 final (`m3-live-s5ot7g0w`) and combined (`m3-live-pl1i_zc2`)
demonstrations are preserved under
`coding_pipeline/logs/manager/m3-collaboration-independent-verification-20261110T135106Z-715e354e/live-host-acceptance/`.
The pipeline report at `coding_pipeline/logs/20261110T135145_2b46d578/summary.md`
records both passed checks and local integration. Each demonstration continued a
stable delegated task in a fresh native Codex session, observed same-primary
numerical progress during rollover, integrated the result, and completed a separate
independent objection/response/re-examination with isolated numerical reproduction.
All thirteen services per demonstration stopped without cleanup errors. Reported
cumulative active work was about 691 and 716 seconds of the 900-second allowance;
missing model usage remains unknown. Fixed-duration rollover supplies no exact
60% context-occupancy guarantee. This is M3 engineering/scientific-workflow evidence,
not human scientific acceptance of the M5 benchmark.

The preserved M1 gate remains available separately.
Each invocation saves a fresh private `m1-live-*` directory containing the project,
CLI command logs and `receipt.json`. The test starts the actual CLI/Codex session
with a 600-second limit, inspects its scientific artifacts, checks a small quadrature
parameter grid against an analytical reference, reruns the researcher-written script
through the production launcher with a fresh 60-second bound, and confirms input
integrity and service cleanup. Literature assessment and scientific Markdown are
printed to the test log; model transcripts remain private in the project. Automated
numerical and artifact checks do not constitute independent scientific verification.
The preserved enabled final run (`m1-live-ig_wfv10`) and pre-merge run
(`m1-live-nomwciin`) are under
`coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/live-host-acceptance/`
in the original target checkout. Exact command logs, receipts, scientific assessment
and limitations are recorded in the
[implementation report](development/requests/m1-implementation.md#m1-live-evidence-closeout).
These completed runs supply the execution evidence for the documentation closeout;
ordinary documentation checks keep paid live inference disabled.

For M4, keep the accepted M1–M3 paid gates off:

```sh
RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 \
RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=1 \
RESEARCH_PIPELINE_M4_OUTPUT_DIR=/absolute/private/request-output/m4 \
  .venv/bin/python -m unittest discover -s tests -v
```

`test_m4_live.py` is ordinarily discovered but starts inference only with
`RESEARCH_PIPELINE_M4_LIVE=1`. Enabled missing output, authentication, services or
isolation prerequisites fail. One fresh private directory contains a disclosed prior
fixture (a preliminary method heuristic, generic user quadrature and elementary
checks; no target answer or fabricated registration) and a new investigation.
The actual researcher discovers/searches/reads this evidence, critically qualifies
it, stages/registers/invokes the user tool, and authors/registers/invokes its own
study of the squared-denominator periodic integral. All new science and target code
come from the actual researcher. The narrow exploratory study stays preliminary;
consequential conclusions still need the existing separate independent verifier.

The harness requires actual successful standalone backend helper invocation events,
matching validation/receipt identities, finite parameter-grid results and resolved
convergence against a hidden composite-Simpson numerical oracle. It revalidates and
reproduces both saved tools only through `isolation.run_isolated`, with explicit output
substitutions. Original science, human inputs and source files/indexes must remain
unchanged. Oracle checks are engineering evidence, not independent Codex verification.

Bounds are 600 seconds for the sole investigation/session, 900 seconds for all
demonstration activity including startup/checks/reproduction, 60 seconds for isolated
reproduction within that allowance, and 1200 seconds overall including failure
cleanup. No forced rollover/delegation gate is repeated. The test inventories
attempted services, stops every owned unit in `finally`, confirms cgroups empty or
removed, and retains failure evidence. Its private `receipt.json` and test output
include exact commands, authorizations/hashes, scientific excerpts, numerical and
reproduction observations, cumulative accounting, unknown telemetry, integrity and
cleanup observations. Readiness on a restricted Writer/Reviewer host transfers to
the existing enabled controller-host final/combined checks and pipeline-confirmed
LOCAL integration; it does not establish whole-M4 or M5 acceptance.

The accepted retrieval/tool demonstrations (`m4-live-s2qz1lq_` and
`m4-live-9dm5m_7w`) are preserved under
`coding_pipeline/logs/manager/m4-cross-project-reuse-tools-20261110T225137Z-ac955108/live-host-acceptance/`.
Pipeline report `coding_pipeline/logs/20261110T225305_1f92cb97/summary.md` records
passed final/combined checks and local integration. Each actual researcher critically
qualified the prior source, validated and invoked both user and agent tools, computed
18 new quadrature rows and retained preliminary status. Isolated reproduction matched
all rows and user output; source/input integrity and cleanup of three services per run
passed. Reported active activity was about 277 and 282 seconds within the grants.
These demonstrations establish the retrieval/tool increment, not whole-M4 or M5 acceptance.

PROJECT.md §7.2 job controls and operational reporting completed normal review,
passed enabled final/combined verification and integrated locally at `8f275fb`.
The accepted demonstrations (`m4-live-t9itjkl7` and `m4-live-jwdlafq4`) are preserved
under `coding_pipeline/logs/manager/m4-compute-job-limits-reporting-20261111T002118Z-e8b7fdea/live-host-acceptance/`.
Both reproduced all 18 numerical rows in production isolation, preserved inputs
and confirmed cleanup. Pipeline report
`coding_pipeline/logs/20261111T002338_830acaa4/summary.md` records the passed outcome.
M1–M4 engineering milestones are accepted. M5 inputs are now supplied in
`research_example/starting_evidence/`; its initial study concerns the mechanism
contributions to linear light-hole spin–orbit interaction. Human scientific
acceptance remains outstanding.
Known backend limitations
remain disclosed: no hard spending cap or reliable context occupancy; CPU fraction
and aggregate CPU time are uncapped; missing usage stays unknown; per-file limits
are not an aggregate disk quota. Tool validation supplies none of these guarantees.
