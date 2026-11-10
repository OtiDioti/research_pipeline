# Research Pipeline — M1

A Python/Linux CLI runs one researcher-directed Codex session in a fresh scientific
project. It reads human questions and evidence, asks the researcher to plan, assess
primary literature, derive and compute, and saves ordinary linked Markdown and
reproducible scientific artifacts. `start` stays in the foreground; `inspect` uses
saved files and needs no model access.

This implementation is **not yet accepted as M1**: the Writer's restricted
environment has no user bus or native file credentials. Actual Codex research and
cgroup/lifetime acceptance must pass in the pipeline's authorized controller host
environment using the opt-in check below. See the
[implementation report](development/requests/m1-implementation.md).

Implementation is ready for code review and the existing controller-owned final
verification stage. That stage runs after the Architect emits `CWI: complete`;
the signal completes the implementation roadmap, while M1 acceptance still
requires the enabled suite and assessment of its actual scientific evidence.

## Installation and prerequisites

Use Python 3.11+ on Linux, Bubblewrap, systemd with an already available user service
manager, and a cgroup v2 hierarchy delegated to that manager. Install a recent
**standalone Linux Codex distribution** (including sibling helpers). npm/Node wrapper
installations are not supported by this small launcher. CLI options were inspected
with `codex-cli 0.167.0`; the isolated inference path is still awaiting live validation.

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
  --wall-seconds 600 --memory-mib 2048 --max-tasks 128 --cpu-percent 100
.venv/bin/research-pipeline inspect /path/to/investigation
.venv/bin/research-pipeline inspect /path/to/investigation --json
```

`--codex /absolute/path/to/codex` and `--model MODEL` select the installed binary
and account-supported model. Without `--model`, Codex selects its backend default;
the controller does not assert a particular resolved model. All limits must be
positive and finite. `--cpu-percent 100` is an aggregate quota of one logical CPU.
`--max-tasks` counts processes and threads, including backend overhead.
The research service has no swap allowance (`MemorySwapMax=0`).

M1 accepts only fresh projects: existing scientific directories/status/indexes or a
previous run are conflicts. Symlinks/special files in the supplied project and symlink
ancestors are rejected. Use a plain project without `.git`, `.agents` or `.codex`
tool configuration. Questions and optional instructions must be UTF-8, nonempty
questions, and at most 256 KiB each; intake supports up to 10,000 evidence files.
Keep human inputs stable during the run. Fingerprint differences invalidate completion;
this is detection, not M2 edit reconciliation. Inputs are never rewritten.

## Files and status

The researcher writes:

- `work/PLAN.md`: concrete, revisable questions, assumptions, methods and checks.
- `sources/LITERATURE.md`: citations, URLs, access dates, relevance, and explicit full-text,
  abstract-only, secondary-source or inaccessible assessments.
- `work/`: analytical notes, scientific scripts, parameters, data and rerun instructions.
- `outputs/REPORT.md`: linked preliminary findings, limitations and next questions.

The controller writes root `RESEARCH_STATUS.md`, immediate-entry `FOLDER_CONTENT.md`
indexes, and private `.research_pipeline/run.json`, `backend.jsonl`, `stderr.txt` and
`run.lock`. Indexes are reconciled at startup and the terminal checkpoint after process cleanup.
The controller does not traverse scientific trees while agent commands can mutate them. Starting evidence is listed in the root index; no
index is written into `starting_evidence/`. Other subdirectories are created only
when the science needs them. Operational diagnostics may contain private scientific
material; keep the project private as appropriate.

Exit codes: `0` completed/inspected, `2` bad input or conflict, `3` unsupported runtime
or authentication, `4` backend failure/incomplete artifacts/uncertain cleanup, `124`
wall deadline, `130` interruption. States include `starting`, `running`, `completed`,
`incomplete`, `blocked`, `failed`, `timed_out`, and `interrupted`. Inspection marks
unconfirmed/stale activity explicitly. Partial artifacts are retained on failure.

Completion requires backend success, observed successful command execution,
nonempty required Markdown, a report link to a local computational artifact (code or
data) under `work/`, a preliminary
label and confirmed cleanup. These structural checks cannot establish scientific
correctness, literature quality, novelty, or reproducibility. M1 has **no independent
scientific verifier**. Failed experimental commands are retained in telemetry; a
corrected command or useful negative finding is not automatically a failed investigation.

## Enforced boundary and limits

The supported launcher is a systemd user transient service containing Bubblewrap.
It mounts `/project` read-only, overlays only `sources/`, `work/`, and `outputs/`
writable, and hides `.research_pipeline/`. System programs/libraries, certificates
and resolver files are mounted explicitly read-only; the host root and home are
not mounted. Temporary storage and Codex home are private. The actual Codex session
uses `workspace-write`, never approval, live literature search, and no inherited
user config/rules, discovered AGENTS instructions, connectors or delegated agents.
Only root project instructions are inserted as authority; supplied sources remain evidence.

The PID namespace, `--die-with-parent`, dropped capabilities, and systemd
`KillMode=control-group` contain descendants, including detached sessions. Cleanup
runs after success, failure, deadline and interruption, with short grace then
SIGKILL. The launcher refuses completion unless service/cgroup inactivity is confirmed.
Systemd enforces aggregate memory, zero swap, CPU, tasks and remaining wall time; the controller
also checks a monotonic deadline. Startup uses that same wall budget; bounded service
cleanup may add several seconds. A disposable probe checks protected inputs, permitted
computation, and actual cgroup `memory.max`, `memory.swap.max`, `pids.max`, `cpu.max`
settings before inference. Missing or nonzero swap limits fail preflight.

Limits that are **not** guaranteed:

- No hard model-token/spending cap or reliable context occupancy. Optional emitted
  turn usage is stored verbatim and never interpreted as context occupancy.
- No separate per-command runtime or scientific-job scheduler. All commands share
  the remaining investigation lifetime and aggregate quotas; there is one researcher.
- A 64 MiB per-file limit and 4 MiB per operational log are **not** a total disk quota.
  Private tmpfs consumes the service's memory allowance.
- Literature/inference networking has no destination filter. No host sockets, user
  home or custom MCP/connector configuration are supplied. The authorized backend's
  native credentials exist in its private namespace during the run.
- Abrupt host/controller SIGKILL cannot finalize status; systemd still enforces its
  lifetime bound. Pause/resume, human-edit reconciliation, rollover and collaboration
  are later milestones.

## Checks and demonstration

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m research_pipeline --help
```

Tests distinguish orchestration doubles, actual Bubblewrap enforcement, and actual
systemd/cgroup enforcement. An unsupported-host skip means incomplete acceptance.
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
capabilities. Do not give a restricted Writer access to another execution context.
Each invocation saves a fresh private `m1-live-*` directory containing the project,
CLI command logs and `receipt.json`. The test starts the actual CLI/Codex session
with a 600-second limit, inspects its scientific artifacts, checks a small quadrature
parameter grid against an analytical reference, reruns the researcher-written script
through the production launcher with a fresh 60-second bound, and confirms input
integrity and service cleanup. Literature assessment and scientific Markdown are
printed to the test log; model transcripts remain private in the project. Automated
numerical and artifact checks do not constitute independent scientific verification.
The implementation report records Writer-local outcomes; the enabled controller test
result is the remaining M1 acceptance gate.
