# Research Pipeline — persistent scientific investigations

A Python/Linux CLI runs one researcher-directed Codex session at a time in a scientific
project. It reads human questions and evidence, asks the researcher to plan, assess
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
real Codex-backed M2 demonstration remains for the next increment and has **not**
passed M2 live acceptance. M3 collaboration
and independent verification; M4 cross-project reuse and remaining controls; and
M5 physics-benchmark investigation and human scientific acceptance remain deferred.

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
  --wall-seconds 600 --memory-mib 2048 --max-tasks 128 --primary-session-seconds 300
.venv/bin/research-pipeline inspect /path/to/investigation
.venv/bin/research-pipeline inspect /path/to/investigation --json
```

`--codex /absolute/path/to/codex` and `--model MODEL` select the installed binary
and account-supported model. Without `--model`, Codex selects its backend default;
the controller does not assert a particular resolved model. All limits must be
positive and finite.
`--max-tasks` counts processes and threads, including backend overhead.
The research service has no swap allowance (`MemorySwapMax=0`).

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
native identities when known, phase and limitation; session summaries retain links.

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
data) under `work/`, a preliminary
label, a usable new handoff and confirmed cleanup. These structural checks cannot establish scientific
correctness, literature quality, novelty, or reproducibility. M1 has **no independent
scientific verifier**. Failed experimental commands are retained in telemetry; a
corrected command or useful negative finding is not automatically a failed investigation.

## Enforced boundary and limits

The supported launcher is a systemd user transient service containing Bubblewrap.
It mounts `/project` read-only, overlays only `sources/`, `work/`, and `outputs/`
writable along with `handoffs/`, read-only mounts for existing scientific Markdown,
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
- No separate per-command runtime or scientific-job scheduler. All commands share
  the remaining investigation lifetime and aggregate quotas; there is one researcher.
- A 64 MiB per-file limit and 4 MiB per operational log are **not** a total disk quota.
  Private tmpfs consumes the service's memory allowance.
- Literature/inference networking has no destination filter. No host sockets, user
  home or custom MCP/connector configuration are supplied. The authorized backend's
  native credentials exist in its private namespace during the run.
- Abrupt host/controller SIGKILL cannot finalize status; systemd still enforces its
  lifetime bound. Checkpoint recovery and forced pause can lose uncheckpointed work.
  Collaboration remains a later increment.

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
fixtures supply no paid scientific evidence. This increment's
code-readiness handoff proceeds to pipeline controller final verification; it does
not assert the full M2 demonstration gate.
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
`RESEARCH_PIPELINE_M2_LIVE=1`. The small paid M2 test belongs to the next
demonstration increment; enabling M2 here enforces isolation prerequisites.
Do not give a restricted Writer access to another execution context.
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
