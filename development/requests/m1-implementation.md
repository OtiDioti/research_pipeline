# M1 implementation report

The minimal Python CLI and isolated Codex backend boundary are implemented and
ready for code review and controller-owned final verification. **M1
acceptance remains incomplete:** the Writer's restricted execution environment cannot
run the required systemd user service and has no supported native file credentials.
This is not a host-wide diagnosis. No actual Codex research
session, literature assessment, scientific derivation or numerical research result
is claimed. The Writer-local demonstration stopped at the prerequisite gate.
The recovery response places the mandatory enabled host suite after the Architect's
`CWI: complete` signal; missing Writer capabilities do not block that handoff.

## Implementation and decisions

The package provides foreground `research-pipeline start PROJECT` and inference-free
`inspect PROJECT [--json]`, with the interfaces and exit codes in the supplied plan.
It inventories/fingerprints questions and evidence, separates project instructions
from scientific source authority, rejects existing managed output/tool configuration
and symlinked inputs, and holds an exclusive project lock. Status distinguishes
missing artifacts and stale/unconfirmed activity. Backend failures, incomplete
artifacts, cleanup uncertainty, deadlines and interruptions retain partial work.

The only science execution path is Bubblewrap inside a resource-limited systemd
user service. Human files are read-only kernel mounts; controller files are hidden;
only scientific output directories are writable. Native authentication is copied
alone into a private temporary home and removed afterward. The standalone ELF
Codex distribution is supported; wrappers, inherited config/tools/proxies, keyring-only
credentials and environment-key fallbacks are intentionally unsupported. The prompt
requires planning, ongoing primary literature assessment, substantive reasoning,
researcher-authored executable computation and preliminary linked Markdown results.

Aggregate memory/tasks/CPU/wall limits apply to the backend and every scientific
subprocess, with swap disabled. Preflight uses the production launcher on disposable sentinels and checks
actual cgroup v2 settings. Shutdown stops the service control group and verifies
inactivity; uncertain cleanup prevents completion. Logs are bounded while output is
continuously drained. Emitted usage and failed command outcomes are retained without
claiming spending or context telemetry.

One deliberate adjustment to the plan: folder indexes are generated at startup and
the terminal checkpoint after confirmed shutdown, rather than while agent commands
are changing directories. This keeps host-side index traversal away from live
agent-controlled path changes. Index failures prevent completion, symlinks are not
followed, special files are not opened, and Markdown descriptions use bounded reads.
Inputs must remain stable for this fresh-session M1; reconciliation is deferred.

Completion checks are structural: required Markdown, a local report link to saved
code or data in `work/`, preliminary labels, a successful observed command and confirmed cleanup.
They impose no programming-language whitelist and do not certify scientific quality.
No M2–M5 capabilities, product-manager files, controllers or old architecture were added.

## Installation and automated evidence

All commands below ran from the request worktree. Python: **3.11.15**;
Bubblewrap: **0.6.1**; systemd: **249**; backend: **codex-cli 0.167.0**.

The initially requested `python -m pip install -e .` built the package but exited 1
because the enclosing environment's default user installation directory is read-only:
`[Errno 30] Read-only file system: .../runtime/home/.local`. Installation then succeeded
inside the writable, ignored local virtual environment:

```sh
python -m venv .m1-local/venv
.m1-local/venv/bin/python -m pip install -e . > .m1-local/install.txt 2>&1
.m1-local/venv/bin/python -m unittest discover -s tests -v > .m1-local/tests.txt 2>&1
.m1-local/venv/bin/python -m research_pipeline --help > .m1-local/help.txt
```

Initial implementation outcome: **19 tests ran successfully; one service-integration class setup was
skipped** with `Required systemd user bus is not available; cgroup/lifetime acceptance
incomplete`. There are no failing automated checks on this host. The skipped class
means memory/CPU/task enforcement and service descendant-lifetime acceptance are
still unverified, not passed.

Orchestration doubles cover intake errors, optional instructions, evidence inventory,
protected-source separation, competing starts, successful linked output/status/indexes,
backend absence/failure, missing artifacts after zero exit, failed computation events,
cleanup uncertainty, timeout/interruption, changed human inputs, index symlinks,
FIFO artifacts, authentication absence/private-copy cleanup, startup expiration,
stale inspection, invalid limits, bounded fragmented JSON events and broken links.
These doubles are explicitly labeled in the tests and are not a research demonstration.

`test_isolation.BubblewrapBoundaryTests.test_actual_mount_boundary_and_permitted_computation`
runs a real Bubblewrap process using the product mount builder. It verifies that
write/unlink/rename of disposable evidence and project instructions fail, controller
files are invisible, an existing outside host sentinel is inaccessible, and an
agent-style Python script can write and execute to produce `sum(i*i for i in range(10)) = 285`.
It checks original sentinel contents afterward. This is an engineering boundary
probe, not scientific computation evidence for the live M1 criterion.

The full service test class additionally exercises production preflight, nonzero
compute exits, detached descendants after normal exit/deadline/SIGINT, memory/file
limits and task exhaustion. Those checks remain pending on a suitable host.

## Runtime gate and bounded demonstration attempt

These read-only capability commands were executed:

```sh
codex --version
codex exec --help
systemd-run --user --wait --pipe --quiet /usr/bin/true
bwrap --unshare-user --unshare-pid --die-with-parent --ro-bind /usr /usr \
  --ro-bind /lib /lib --ro-bind /lib64 /lib64 --symlink usr/bin /bin \
  --proc /proc --dev /dev /bin/true
```

Codex help confirms the installed `exec`, `--json`, `--ephemeral`,
`--ignore-user-config`, `--ignore-rules`, `--sandbox` and directory options. The
Bubblewrap command exits 0. The systemd command exits 1 with:

```text
Failed to connect to bus: $DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined
```

Both environment variables are unset, and the effective native Codex home's
`auth.json` does not exist. No alternate bus, inherited pipeline credentials,
sandbox bypass or service-manager escape was attempted. Controlled Codex settings
were checked against the official [CLI reference](https://developers.openai.com/codex/cli/reference/)
and [configuration reference](https://developers.openai.com/codex/config-reference/);
isolated inference remains unvalidated.

The prepared private project is `.m1-local/demonstration/`. Its only starting scientific
materials are `starting_evidence/RESEARCH_QUESTIONS.md` and `STARTING_NOTE.md`: a
periodic trapezoidal quadrature question for `1/(a-cos(theta))`, with `a=1.01,1.1,2`,
and a tentative singularity/convergence hypothesis. No solution, program, data or
report was supplied. The exact final commands are:

```sh
.m1-local/venv/bin/research-pipeline start .m1-local/demonstration \
  --wall-seconds 120 --memory-mib 1024 --max-tasks 64 --cpu-percent 100 \
  > .m1-local/demonstration-start.txt 2>&1
.m1-local/venv/bin/research-pipeline inspect .m1-local/demonstration --json \
  > .m1-local/demonstration-inspect.json
.m1-local/venv/bin/research-pipeline inspect .m1-local/demonstration \
  > .m1-local/demonstration-inspect.txt
```

Start exits **3**, state **blocked**, with:

```text
systemd user bus unavailable: XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS must already be set; do not connect to another execution context to bypass restrictions
```

Both inspections exit 0. Useful saved paths are:

- `.m1-local/demonstration/RESEARCH_STATUS.md`: honest blocked status.
- `.m1-local/demonstration/.research_pipeline/run.json`: backend version, explicit
  limits, input inventory/fingerprints, no research service attempted, missing artifacts.
- `.m1-local/demonstration/FOLDER_CONTENT.md`: discoverable supplied questions/material.
- `.m1-local/tests.txt`, `install.txt`, `help.txt`, `environment.json`: private check evidence.

There is **no observed research behavior** beyond controller intake: no model session
started, no literature was fetched or examined, no research commands executed, and
no scientific plan/results or usage were produced. The empty scientific directories
contain navigation only. Scientific reproduction could not run because there is no
researcher-produced program/data; no reproduction command or successful outcome is
invented. Earlier blocked attempts are retained separately under `.m1-local/demo*`.

## Preservation, cleanup and remaining acceptance

`PROJECT.md`, root `AGENTS.md` and manager-owned `STATUS.md` match their initial
worktree commit bytes (read-only baseline comparison; no branch/index/commit operations).
The manager's separate main-worktree status has changed independently; it was not copied
or overwritten. Demo input fingerprints are unchanged. No index was written inside
starting evidence. Environment evidence records hashes without credential contents.

The demonstration's `service_attempted` is false. Its preflight returned before any
`systemd-run` or inference launch, so there is **no demonstration service or descendant
to stop**. The service's inactive state cannot be independently queried without the
missing bus. The direct disposable Bubblewrap probe exited normally, and every test
subprocess was waited on. No demonstration agents or compute jobs were intentionally
left running.

Remaining gates: a supported authorized user-service/cgroup environment and native
file login, then the real service integration suite, bounded actual Codex research,
literature/access-quality inspection, produced-command reproduction inside a fresh
bounded isolated service, and cleanup confirmation. This is a disclosed environmental
blocker, not successful M1 completion. Spending/context occupancy remain unavailable;
limits are aggregate, networking unfiltered, and file/log bounds are not a disk quota.

## Review repair — attempt 1

Both P2 findings are corrected:

- The transient service requests `MemorySwapMax=0` alongside `MemoryMax`. Preflight
  reads `memory.swap.max`, rejects missing or nonzero values before inference, and
  records the observed zero limit. Saved/configured limits expose `swap_bytes: 0`.
  A named service integration test checks the observed swap setting. A separate,
  explicitly doubled preflight regression exercises rejection of unlimited, positive
  and missing swap limits and acceptance of zero; it does not claim kernel enforcement.
- Completion now requires an existing local, non-Markdown computational file under
  `work/` linked directly from `outputs/REPORT.md`. An external citation plus an
  unrelated native artifact cannot satisfy this check. Tests exercise the resulting
  CLI `incomplete` state after backend exit zero, reject links to notes/directories/
  starting evidence, and accept saved code and URL-encoded data paths.

The README documents both requirements. Verification command:

```sh
.m1-local/venv/bin/python -m unittest discover -s tests -v > .m1-local/review-repair-tests.txt 2>&1
```

Outcome: **22 tests passed; one systemd integration class setup skipped** because the
required user bus is still unavailable. The real Bubblewrap boundary/computation
check passed. Actual service swap enforcement, the remaining service integration
checks, Codex research and scientific reproduction remain unvalidated on this host;
M1 acceptance is still incomplete. Native file credentials are still absent. No
research session or demonstration job was launched during this repair.

`.m1-local/review-repair-checks.json` records the current prerequisite checks and
confirms `PROJECT.md`, root `AGENTS.md` and manager-owned `STATUS.md` remain byte-for-byte
unchanged from the start of this repair. No human evidence was modified.

## Recovery: opt-in controller host acceptance

The recovery response reports a manager presence check of the bus and native
authentication in the legitimate controller host context. Presence does not
establish functioning isolation or inference. The Writer remains restricted; no
bus, credentials or alternate execution context were supplied to it.

Added `tests/test_m1_live.py`, discovered by the existing unittest command. It runs
only with `RESEARCH_PIPELINE_M1_LIVE=1`; enabled acceptance requires
`RESEARCH_PIPELINE_M1_OUTPUT_DIR`. Ordinary checks never start paid inference.
The existing filesystem and service integration checks now fail rather than skip
missing capabilities when that flag is enabled. Two focused regressions check
those decisions using explicit environment/tool doubles.

The live test makes a fresh private `m1-live-*` output directory per invocation.
It supplies only questions, a tentative hypothesis and deterministic-method
instructions, then invokes the actual product CLI with a 600-second wall bound,
2048 MiB memory, zero swap, 128 tasks and one CPU. Codex must produce the plan,
primary-source assessment with saved source material, derivation, standard-library
script, data and linked preliminary findings. The fixed `compute.py --output`
interface and 18-point quadrature grid are demonstration requirements, with no
discipline-specific changes to product code.

The test invokes both CLI inspection forms, prints scientific Markdown to the
test log, checks finite numerical estimates and convergence against an analytical
reference, and reruns the researcher-written script through `run_isolated` with a
fresh 60-second, 512 MiB, 32-task bound. Reproduction must match all estimates with
`rtol=atol=1e-12` and preserve the original data. It confirms human input hashes,
absence of indexes in starting evidence, and production service cleanup, including
on failure. The existing service tests exercise detached descendants explicitly.
The receipt records CLI commands, production reproduction arguments and a runnable
reproduction command, backend/version, emitted telemetry, artifact hashes, outcome,
cleanup and limitations. Model transcripts stay in private project diagnostics.
These checks support scientific review; they cannot certify literature quality,
novelty, or independent scientific verification.

Writer-local commands:

```sh
python -m venv .m1-local/venv
.m1-local/venv/bin/python -m pip install -e . > .m1-local/recovery-install.txt 2>&1
.m1-local/venv/bin/python -m unittest discover -s tests -v > .m1-local/recovery-tests.txt 2>&1
.m1-local/venv/bin/python -m research_pipeline --help > .m1-local/recovery-help.txt
RESEARCH_PIPELINE_M1_LIVE=1 \
RESEARCH_PIPELINE_M1_OUTPUT_DIR="$PWD/.m1-local/live-gate-probe" \
  .m1-local/venv/bin/python -m unittest discover -s tests -p test_m1_live.py -v \
  > .m1-local/recovery-live-gate.txt 2>&1
```

Installation succeeded. The ordinary suite passed **24 tests**, skipped the
disabled live test, and skipped systemd integration class setup for the unavailable
Writer user bus (`Ran 25 tests`, `OK (skipped=2)`). Real Bubblewrap protection and
permitted computation passed. The explicitly enabled negative probe exited **1**
as required: its actual product `start` exited **3**, `blocked`, because
`XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` were absent. Both inspections
succeeded. Private failed-probe evidence is at
`.m1-local/live-gate-probe/m1-live-144mtp6x/receipt.json` and its `project/`
subdirectory. Inputs were unchanged; `service_attempted` was false, with no
inference or compute job started. This negative probe is not a scientific
demonstration or a passing enabled acceptance result.

The next pipeline integrated-test invocation must run the full suite with both live
variables set in its existing authorized host environment, as documented in README.
It must retain a passing fresh receipt and the printed scientific/literature evidence
before M1 acceptance. The implementation and opt-in path are ready for that gate;
actual host enforcement, research, reproduction and cleanup remain pending.
No production isolation settings were weakened, and no controller/session/config
machinery or later milestone features were changed.

Final verification after the receipt changes repeated the ordinary suite:
`Ran 25 tests in 1.155s`, `OK (skipped=2)`; CLI help exited 0.
`.m1-local/recovery-preservation-after.json` confirms `PROJECT.md`, root `AGENTS.md`
and manager-owned `STATUS.md` match the hashes captured before recovery work.
No demonstration agents or compute jobs were intentionally left running.

## Milestone 002 — full acceptance invocation remains blocked

The following evidence is preserved from the previous Writer attempt. The
execution-order correction below supersedes its blocked implementation handoff,
without changing the pending M1 acceptance requirements.

The supplied milestone plan requests completion of the remaining M1 acceptance
gates, with production changes only for a demonstrated defect. The current
Writer environment still has neither `XDG_RUNTIME_DIR` nor
`DBUS_SESSION_BUS_ADDRESS`, and its effective native Codex home has no
`auth.json`. A direct `systemd-run --user --wait --pipe --quiet /usr/bin/true`
probe exits **1** with `Failed to connect to bus: $DBUS_SESSION_BUS_ADDRESS and
$XDG_RUNTIME_DIR not defined`.

The existing trusted integrated-test stage is not exposed as an invocation
capability in this Writer session. The following full acceptance invocation ran
in the current restricted environment; it is **not** a controller-host result.
No alternate bus, credential source, execution context, controller configuration,
or permissions were used. The artifact reader refused the supplied artifact
paths; the plan, earlier decisions and failure reports were read from their
existing local artifact-directory files instead.

Exact commands, from the request worktree:

```sh
umask 077
python3 -m venv .m1-local/venv
.m1-local/venv/bin/python -m pip install -e . \
  > .m1-local/milestone-002/install.txt 2>&1
.m1-local/venv/bin/research-pipeline --help \
  > .m1-local/milestone-002/help.txt 2>&1
.m1-local/venv/bin/python -m unittest discover -s tests -v \
  > .m1-local/milestone-002/local-tests.txt 2>&1
RESEARCH_PIPELINE_M1_LIVE=1 \
RESEARCH_PIPELINE_M1_OUTPUT_DIR="$PWD/.m1-local/milestone-002/host-acceptance" \
  .m1-local/venv/bin/python -m unittest discover -s tests -v \
  > .m1-local/milestone-002/host-acceptance-tests.txt 2>&1
```

Installation and entry-point help exit **0**. Ordinary regression testing exits
**0**: `Ran 25 tests in 1.170s`, `OK (skipped=2)`; 24 tests pass, the disabled
research test skips, and service-integration class setup skips. The real
Bubblewrap protected-input/permitted-computation check passes.

Both live variables reached the full acceptance process. Enabled testing exits
**1**: `Ran 25 tests in 1.285s`, `FAILED (failures=1, errors=1)`, with 24 passing
tests and no skips. Service-integration setup errors with `Required systemd user
bus unavailable during enabled live acceptance`. The actual research test fails
because product `start` exits **3**, state **blocked**, with:

```text
systemd user bus unavailable: XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS must already be set; do not connect to another execution context to bypass restrictions
```

Fresh private evidence is
`.m1-local/milestone-002/host-acceptance/m1-live-2pfmd962/receipt.json`,
with the scientific project at the adjacent `project/`. The receipt contains
the absolute CLI invocations. Their equivalent commands from the worktree are:

```sh
demo_project="$PWD/.m1-local/milestone-002/host-acceptance/m1-live-2pfmd962/project"
.m1-local/venv/bin/python -m research_pipeline start "$demo_project" \
  --wall-seconds 600 --memory-mib 2048 --max-tasks 128 --cpu-percent 100
.m1-local/venv/bin/python -m research_pipeline inspect "$demo_project" --json
.m1-local/venv/bin/python -m research_pipeline inspect "$demo_project"
```

The recorded start exits **3**; both inspection commands exit **0**. Do not
rerun `start` on this used project: the test creates a fresh project on each
acceptance invocation. `start.stdout`, `start.stderr`, `inspect-json.stdout`,
`inspect-json.stderr`, `inspect.stdout`, and `inspect.stderr` retain the outputs.
State records **codex-cli 0.167.0**, backend-default model, all three required
scientific artifacts missing, unchanged protected inputs, and
`service_attempted: false`. No research service was created, so
`cleanup_ok: null` and the empty receipt cleanup map do not establish service
cleanup acceptance. The test process and direct Bubblewrap subprocess finished;
no demonstration agent or compute job was launched or left running.

Observed work is limited to controller intake, status and folder indexes.
No Codex scientific plan, literature retrieval or access assessment, derivation,
quadrature estimates, report, emitted model usage, or reproduction exists.
Accordingly, there is no reproduction command/outcome to report. Actual cgroup
resource enforcement and detached-descendant cleanup remain untested here.
The documented aggregate-budget, authentication, unrestricted-network,
nonaggregate-disk and unavailable spending/context-telemetry limitations remain.

No production or test change is justified by these environmental failures.
README acceptance statements remain accurate. `PROJECT.md`, root `AGENTS.md`,
and manager-owned `STATUS.md` are preserved; before/after SHA-256 evidence is
in `.m1-local/milestone-002/preservation-{before,after}.json`.
Human input fingerprints match the receipt, no starting-evidence index was
written, and the generated managed-directory indexes are present.

**Unresolved gate:** run the existing enabled full suite in the existing
authorized controller test environment with a functional systemd user
manager/delegated cgroup v2 and native Codex file authentication. Retain its
fresh receipt, assess actual primary-source access and scientific artifacts,
and pass bounded numerical reproduction and cleanup before accepting M1.

## Milestone 002 recovery — implementation ready for final verification

The recovery response corrects execution order: controller-owned host tests run
only after the Architect emits `CWI: complete` and cannot be submitted by the
Writer. No implementation tasks remain. Preserve implementation commit `b0e119c`,
the existing opt-in acceptance suite, production protections and earlier blocked
evidence. This recovery changes documentation only; no new runner or platform
functionality is needed.

**Decision for milestone decisions and review summary:** after code-review
approval, the next Architect action is `CWI: complete`, transferring execution to
the existing controller-owned FINAL VERIFICATION stage. No further implementation
milestone is authorized absent an actual final-test defect. This signal ends the
implementation roadmap; it does not establish scientific acceptance of M1.
The mandatory full suite must inherit `RESEARCH_PIPELINE_M1_LIVE=1` and the
original request's `live-host-acceptance` output directory. Actual research,
literature assessment, service/resource enforcement, bounded numerical reproduction
and cleanup remain pending. A final-test failure requires normal integration
repair; auto-merge cannot pass without enabled acceptance success.

Fresh ordinary checks used the existing installation:

```sh
RESEARCH_PIPELINE_M1_LIVE=0 \
TMPDIR="$PWD/.m1-local/milestone-002-recovery/tmp" \
  .m1-local/venv/bin/python -m unittest discover -s tests -v \
  > .m1-local/milestone-002-recovery/local-tests.txt 2>&1
.m1-local/venv/bin/research-pipeline --help \
  > .m1-local/milestone-002-recovery/help.txt
```

Both commands exit **0**. The suite reports `Ran 25 tests in 1.156s`,
`OK (skipped=2)`: **24 tests pass**, including actual Bubblewrap input protection
and permitted computation; service-class setup skips for the unavailable user
bus, and live research skips because it is explicitly disabled for this local
command. The inherited controller acceptance configuration was not changed.
No enabled host probe, bus/credential access or research job was attempted.
The standalone boundary-test subprocess finished normally.

SHA-256 manifests at
`.m1-local/milestone-002-recovery/preservation-{before,after}.json` confirm
`PROJECT.md`, root `AGENTS.md`, manager-owned `STATUS.md`, packaging, production
Python and test sources are unchanged. Earlier milestone-002 report evidence is
retained. The disclosed Writer-local infeasibility remains; the next required
execution belongs to controller final verification, not another Writer milestone.
