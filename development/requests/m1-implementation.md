# M1 implementation report

**Current Writer verdict (2026-11-10): the preserved evidence supports the M1
minimal scientific loop.** Both enabled controller suites passed all 34 tests.
Inspection of both actual scientific projects establishes a meaningful bounded
question-to-artifact demonstration, beyond structural and numerical assertions.
The [closeout assessment](#m1-live-evidence-closeout) records the evidence,
qualifications and remaining pipeline Reviewer gate. Findings remain preliminary;
this does not certify novelty, overall scientific competence, M3 independent
verification or M5 human scientific acceptance.

The authorized CPU-quota removal remains in effect: memory, zero swap,
task/thread limits, wall deadlines, namespace/mount protections and whole-service
cleanup are required; CPU fraction and aggregate CPU time are uncapped.

## M1 live-evidence closeout

### Preserved execution evidence

All evidence paths below resolve against the **original target checkout**,
`/home/francesco/Desktop/gits/research_project/research_pipeline`, not this
documentation worktree. The prior pipeline summary identifies successful
final/pre-merge verification and local integration at
`dd2efc92cfaccb3776b730fc9fa6a33bd09090dc`. These abbreviations give exact
target-root-relative paths:

```text
L = coding_pipeline/logs/20261110T091713_50e21105
E = coding_pipeline/logs/manager/m1-minimal-scientific-loop-20261110T091644Z-1be6cf51/live-host-acceptance
F = E/m1-live-ig_wfv10
P = E/m1-live-nomwciin
```

The Writer inspected `L/summary.md`, both complete command logs, the actual
receipts and the scientific projects:

| Stage | Command log under L | Exact suite outcome | Preserved receipt and project |
|---|---|---|---|
| Final | `tests/final-004.txt.commands/0001.txt` | `Ran 34 tests in 233.142s`, `OK`, no skips | `F/receipt.json`, `F/project/` |
| Pre-merge | `tests/pre-merge-005.txt.commands/0001.txt` | `Ran 34 tests in 281.364s`, `OK`, no skips | `P/receipt.json`, `P/project/` |

`L/tests/final-004.txt` and `L/tests/pre-merge-005.txt` record exit code 0
for `/home/francesco/miniconda3/bin/python -m unittest discover -s tests`.
Both ran with live acceptance enabled. Each receipt records `outcome: passed`,
`state: completed`, no validation failures, research return code 0, unchanged
protected inputs and successful text/JSON CLI inspection. The exact absolute
`start`/`inspect` invocations are in each receipt's `commands`; start used
`--wall-seconds 600 --memory-mib 2048 --max-tasks 128`.
F ran at 10:37:52–10:41:39 UTC and P at 10:41:46–10:46:20 UTC on 2026-11-10.
Earlier blocked projects, including `E/m1-live-rwho2ts7`, are not counted.

Selected scientific Markdown, code, data and saved source text are copied to
ignored `.m1-local/m1-live-evidence-closeout/` for bounded Reviewer inspection.
`EVIDENCE_INDEX.md` maps copies to originals and SHA-256 values. Each demo has
`COMMAND_EVIDENCE.md` with sanitized command outcomes and original JSONL record
numbers, `SOURCE_EXCERPTS.md` with PDF page references, and
`receipt-selected.json` containing whitelisted outcome fields.
All 12 receipt-listed scientific artifact hashes and six protected-input hashes
match the preserved files. No authentication, native histories, raw diagnostic
streams or unrelated logs were copied. Original PDFs remain in each original
`project/sources/`; their full extracted text is staged instead.

### Intake and planning before computation

Both projects preserve `project/starting_evidence/RESEARCH_QUESTIONS.md`,
`STARTING_NOTE.md` alongside it, and `project/AGENTS.md`. The human supplied the
integral, tentative nearby-singularity hypothesis, grid and script/data interface,
but no analytical solution, scientific code or report. Instructions required
deterministic standard-library calculations and honest failure reporting.
This demonstrates a focused supplied question, not unrestricted research framing.

Recorded command order in each original
`project/.research_pipeline/backend.jsonl` establishes the sequence independently
of file timestamps or retrospective report statements:

- F: records 5 and 9 read the starting files and project instructions; record 11
  writes the initial plan. Retrieval and source inspection follow. Record 36
  writes the derivation/program and executes the first quadrature; 42 runs a
  separate output.
- P: record 5 reads both starting files; 9 writes the initial plan, before
  retrieval and first computation at 24. Record 30 adds error decomposition
  and regenerates results; 33 writes the final derivation note; 35 runs the
  final program to a separate output and compares it with the final original.
  The final derivation note was saved after computation, although planning
  preceded it. Project instructions were supplied through intake rather than
  a separate recorded `cat AGENTS.md`.

The initial plans define the unshifted periodic grid, fixed real `a>1`,
exact arithmetic versus binary64, literature, derivation, direct sums, checks
and a stopping point. Later checkpoints document the method adjustments:
F added 80/100-digit Decimal checks to interpret saturation; P used 340/370
digits to resolve tiny predicted errors and added input/evaluation-error
separation. These are methods connected to the question, not empty headings.

### Substantive derivation and assumptions

Both complete `project/work/DERIVATION.md` files split the interval at pi for
the tangent half-angle substitution, obtaining
`I(a)=2*pi/sqrt((a-1)*(a+1))`. They locate simple complex poles at
`2*pi*k +/- i*alpha`, with `alpha=acosh(a)`, and expand the Poisson kernel
with `q=1/(a+sqrt(a*a-1))`. Absolute convergence for fixed `a>1` justifies
integration and finite-node averaging. Only Fourier modes divisible by n
survive averaging on the unshifted grid, yielding

```text
T_n - I = 2*I*q**n/(1-q**n) = 2*I/(exp(n*alpha)-1).
```

This explains positive exact error, exponential refinement at fixed a, and
nonuniform convergence near one: `alpha ~ sqrt(2*(a-1))`, so the node count
for fixed relative tolerance grows as `(a-1)**(-1/2)`. The integral diverges
at `a=1`, which is excluded. Both notes correctly distinguish the exact
formula from a general bounded analytic-strip theorem: a narrower strip
`0<b<alpha` admits `M_b=1/(a-cosh(b))`; inserting `b=alpha` would incorrectly
assume boundedness at the poles. This is substantive reasoning that explains
the experiment and its approximation regime.

### Literature actually consulted

Both `project/sources/LITERATURE.md` files give citations, URLs, relevance,
access date **2026-11-10 UTC** and links to these saved full texts:

| Work and role | Files under each project/sources | Relevant content inspected |
|---|---|---|
| Mohsin Javed and Lloyd N. Trefethen (2014), “A trapezoidal rule error bound unifying the Euler–Maclaurin formula and geometric convergence for periodic functions,” *Proc. R. Soc. A* 470 (2161), 20130571; DOI `10.1098/rspa.2013.0571`. Original primary research. | `javed_trefethen_2014.pdf`, `javed_trefethen_2014.txt` | PDF pp. 2–4: Theorem 2.1, Corollary 3.1 and proof; periodic cancellation removes boundary contributions, leaving the geometric bound. Scaling the unit interval supports the notes' strip argument. |
| Lloyd N. Trefethen and J. A. C. Weideman (2014), “The Exponentially Convergent Trapezoidal Rule,” *SIAM Review* 56 (3), 385–458; DOI `10.1137/130932132`. Author-written review with explicit proofs, not an original priority source. | `trefethen_weideman_2014.pdf`, `trefethen_weideman_2014.txt` | Section 3, printed pp. 394–397 (PDF pp. 10–13): Theorem 3.2 and Fourier aliasing proof, especially (3.17)–(3.18). Supports the mechanism and hypotheses, not floating-point guarantees. |

The author URLs are
`https://people.maths.ox.ac.uk/trefethen/publication/PDF/2014_150.pdf`
and `https://people.maths.ox.ac.uk/trefethen/publication/PDF/2014_149.pdf`,
respectively. F records successful `urllib` downloads at JSONL records 17
and 19, with PDF signatures and byte counts; successful `pdftotext -layout`
at 23 and 25; theorem/proof reads at 27, 34, 38 and 40. P records successful
`curl -fL` retrieval at 15 and within 22, conversions at 19 and 22, and
source reads at 26, 28 and 30.

The actual extracted text contains titles, authors, theorems, proofs and
subsequent sections, rather than substituted landing or error pages.
The Javed–Trefethen PDF is 318349 bytes, SHA-256
`acdc861a0ddd8dc30c980720478390aa4f68081fa6a94d10d679b773363f73fc`;
the Trefethen–Weideman PDF is 1213120 bytes, SHA-256
`378ed15ee9b822bc222dac0e90cacf689d56cc21be7710bbce715dd1e6d2324b`.
These agree with F's `sources/provenance.json` and P's `sources/MANIFEST.md`.
Full texts were retrieved and relevant sections examined; reading every page
is neither claimed nor established. The research paper fulfills the primary
literature requirement; the review corroborates direct theory. No inaccessible
or abstract-only work substantiates a theorem here.

Web-search records establish bibliographic discovery. The scientific notes
also describe publisher metadata access; search snippets alone do not prove
that a publisher page was read. This assessment relies on the saved author
texts and local reads. Two closely related works provide a focused methodological
assessment, not a systematic literature or novelty search.

F records 20 commands, 19 successful; P records 14, 13 successful. Each has
one recorded exit-127 command for unavailable `rg`, recovered with `grep`,
`sed` and Python. P's failed composite command includes successful retrieval
and conversions before the final search failure; it is not a download failure.
P also records a grep-to-head broken-pipe diagnostic despite composite exit 0,
and initial Decimal-to-float diagnostic underflow displaying tiny residuals
as zero. The retained table generator formats Decimal directly. These display
and tool problems were resolved; no unresolved numerical or retrieval failure
is apparent in the inspected evidence. Composite success alone would not
establish this.

### Executable study and preliminary findings

Inspection of both `project/work/compute.py` files confirms direct evaluation
of all n samples `1/(a-math.cos(2*math.pi*j/n))`, `j=0,...,n-1`, using
`math.fsum` and `2*pi/n`; no duplicated endpoint. References and exact errors
are separate comparison fields, not substituted estimates. Both implement
`--output PATH`. F refuses existing output; P can overwrite it, so its rerun
instructions require a fresh filename.

Each `work/results.json` contains all 18 combinations of
`a=1.01,1.1,2.0` and `n=16,32,64,128,256,512`, with identical binary64
estimates across demonstrations. For `a=1.01`, the estimate decreases from
`54.635116083083503` at n=16 to `44.318173338057896` at n=128, near the
reference `44.3181721004628`; relative discretization error falls from about
0.233 to `2.79e-8`. At n=16, `a=1.1` and `a=2` already have relative errors
about `1.66e-3` and `1.41e-9`. This resolved convergence agrees with pole
distances about 0.141304, 0.443568 and 1.316958.

The numerical floor matters: at `a=1.01`, n=256 and 512 have observed absolute
errors about `-3.47e-15` and `-4.61e-14`, despite positive exact discretization
errors about `1.73e-14` and `3.37e-30`. Refinement can worsen the computed
answer. Both notes separate parameter representation, node/cosine, denominator,
scaling and summation effects; `fsum` does not repair them all. The alternative
sine-squared denominator is a diagnostic, not a uniformly better result.

F's Decimal direct sums at 80/100 digits cannot resolve the predicted `a=2`,
n=512 absolute error around `1.06e-292`; its report explicitly labels such
tiny errors as formula predictions. P's 340/370-digit direct sums empirically
resolve that scale: maximum relative precision difference `7.48364e-339`,
identity residual `8.57436e-369`. Both use Machin's pi formula and a cosine
Taylor series as additional computational routes. Precision repetition and
stopping rules are not interval certificates or independent verification.
The broader near-one scaling rests on derivation, not three sampled parameters.

Both `outputs/REPORT.md` files link the plan, literature, derivation, code and
original/repeated data; F includes its table and P links
`work/NUMERICAL_RESULTS.md`. They label findings **PRELIMINARY**, explain
assumptions, limitations and next questions, and reject field-novelty claims.
JSON preserves Python 3.10.12, Linux x86_64, libmpdec 2.5.1, binary64 with
53 mantissa bits, precisions, code hashes and deterministic/no-randomness
parameters. The scientific subprocess Python differs from the controller's.
Both receipts record `codex-cli 0.167.0` and research model `backend default`;
pipeline role settings and cumulative emitted token usage do not establish
resolved model identity or reliable context occupancy.

### Reproduction, protection and cleanup

F's command-log lines 206–207 and P's lines 198–199 print the production
invocation and exact executable shell command. These are also preserved in
each original receipt's `reproduction_invocation` and
`reproduction_rerun_command`. The scientific command was exactly:

```sh
/usr/bin/python3 /project/work/compute.py --output /project/work/reproduced.json
```

It ran through `research_pipeline.isolation.run_isolated`, with
`Config(wall_seconds=60, memory_mib=512, max_tasks=32,
deadline=time.monotonic()+60)` inside a fresh production systemd/Bubblewrap
service. The saved shell command creates a fresh deadline and exits 4 on
uncertain cleanup. No reproduction command was executed again for closeout.

Both receipts record reproduction return code 0, no timeout/interruption,
`cleanup_ok: true` and **“All 18 estimates agree within rtol=atol=1e-12”**.
Inspection of saved original/reproduced data also finds identical binary64
estimates. `work/results_rerun.json` is each researcher's internal repeat;
`work/reproduced.json` is the later bounded launcher reproduction. Final
original results still match receipt hashes. P regenerated its original after
adding diagnostics; preservation concerns the receipt-hashed final result,
not every intermediate version.

Both receipts confirm unchanged starting evidence and project `AGENTS.md`;
current hash comparison agrees. Preflight recorded actual cgroup
`memory.max=2147483648`, `memory.swap.max=0`, `pids.max=128`, and successful
protected-sentinel/permitted-computation checks. The enabled suites also
include existing real boundary, resource and detached-descendant cleanup tests.
Research and reproduction properties record `ActiveState: inactive`,
`SubState: dead`, `LoadState: not-found` and empty control groups.
Final receipt cleanup maps confirm both services for each demonstration:

| Demo | Research service | Reproduction service |
|---|---|---|
| F | `research-3e92dccc6c40472c9862aa600ab87902.service` | `research-17cf677e8db94d8bb25937a152ff0c75.service` |
| P | `research-289d79e1f7784b90b9d983ae9a1a6877.service` | `research-2d8fa22b7e9b4c128fc5992c2b32f107.service` |

These are confirmed inactive at execution time; no new service inspection
or demonstration job occurred during closeout.

### Verdict, review boundary and documentation checks

The Writer finds no material gap in the **M1 meaningful question-to-artifact
demonstration**: both runs show real intake, prior planning, relevant retrieved
primary text, substantive reasoning, executed direct quadrature and useful
linked preliminary conclusions with reproducible artifacts. This bounded
application of known theory to a supplied grid does not certify novelty or
overall scientific competence.

The pipeline Reviewer must still assess the staged actual sources, derivations,
code, data and command evidence. Its authoritative outcome belongs in
`coding_pipeline/logs/20261110T104911_bee8ceea/milestones/001/review.md`
and adjacent `review-outcome.txt` when produced. This report does not
predeclare approval. Prior reviews in `L/summary.md` approved implementation
readiness before these live artifacts and do not substitute for this review.

Numerical reproduction and pipeline artifact assessment remain distinct from
the separate scientific verifier required by M3 and human acceptance required
by M5. M2 persistence/human direction/primary rollover, M3 collaboration and
verification, M4 cross-project reuse/remaining controls and M5 Ge-rich
quantum-well light-hole-qubit/resonator research remain deferred. One fresh
session supplies no pause/resume or edit reconciliation. Hard spending/token
and context guarantees remain unavailable; CPU fraction/time are uncapped,
network destinations unfiltered, and file/log bounds are not an aggregate
disk quota. Memory, zero swap, tasks and wall limits are aggregate, not a
per-command scheduler.

Only README and this report change. Original evidence, `PROJECT.md`, root
`AGENTS.md`, manager `STATUS.md`, production code, tests, dependencies and
configuration are preserved. No scientific code, live inference or reproduction
was rerun. The existing ordinary suite ran with paid inference explicitly disabled:

```sh
RESEARCH_PIPELINE_M1_LIVE=0 \
  /home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

It exited **0**: `Ran 26 tests in 1.158s`, `OK (skipped=2)`. The disabled
live test and unavailable Writer user-bus class setup explain the skips;
these local checks do not replace prior enabled 34-test results. Log:
`.m1-local/m1-live-evidence-closeout/ordinary-tests.txt`.
`git diff --check` passed; only the two authorized documents appear in the
tracked diff. New links/anchors and 17 durable evidence paths resolve.
Before/after hashes confirm 15 protected, configuration, production and test
files unchanged. Results are saved in the same ignored directory's
`documentation-checks.txt` and `preservation-{before,after}.json`.

## Historical implementation and verification record

The following records describe earlier attempts and their interfaces. Historical
commands, CPU-quota claims and failed receipts are retained as evidence, not
current usage guidance. The CPU-quota recovery record below supersedes that
CPU contract; README describes the supported interface. All pending/blocked
statements below describe their historical stage; the closeout assessment above
is the current Writer verdict.

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

## Integration repair — source-checkout test discovery

The supplied `tests/final-002.txt.commands/0001.txt` shows three import errors,
before any assertions ran: `research_pipeline` was unavailable to the integrated
runner's uninstalled Python interpreter. Reproduced all three errors with the
exact supplied command:

```sh
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
```

Added shared `tests.use_checkout()` setup and invoked it before product imports
in each test module. It exposes the checkout's `src/` through `sys.path` and
inherited `PYTHONPATH`, so actual Python CLI subprocesses also exercise this
checkout. Existing Python search paths are retained. This avoids requiring
installation into the runner's interpreter or changing the product's source
layout. Production code, packaging, isolation and live-acceptance configuration
are unchanged. README and the test directory index document this setup.

After repair the exact command exits **0**: `Ran 25 tests`, `OK (skipped=2)`.
The verbose repeat also exits **0**, with **24 passing tests**, including real
Bubblewrap input protection/permitted computation and subprocess CLI start/inspect.
Private log:

```sh
/home/francesco/miniconda3/bin/python -m unittest discover -s tests -v \
  > .m1-local/integration-1/tests.txt 2>&1
```

Independent discovery of the live-test module also imports successfully:

```sh
/home/francesco/miniconda3/bin/python -m unittest discover -s tests \
  -p test_m1_live.py -v
```

It exits **0**, with one explicitly disabled live test skipped. No new test cases
were needed: the reproduced discovery command and existing CLI subprocess checks
directly verify the repair.

Acceptance limitations remain: service integration class setup skips because this
Writer environment has neither `XDG_RUNTIME_DIR` nor `DBUS_SESSION_BUS_ADDRESS`;
live research skips because `RESEARCH_PIPELINE_M1_LIVE` is unset. These skips do
not establish service enforcement or scientific acceptance. The enabled controller
host suite remains required. No research agent, model inference or demonstration
job was launched during this repair. `PROJECT.md`, root `AGENTS.md`, human evidence
and manager-owned `STATUS.md` were not edited.

## Integration repair 2 — host CPU controller unavailable

Read the complete supplied `tests/final-003.txt` report and its sibling
`tests/final-003.txt.commands/0001.txt`. The artifact reader refused the sibling
file, so its complete contents were read from the existing local artifact path.
Both failures share one cause: service integration setup and actual CLI research
preflight cannot read the transient service's `cpu.max`. The recorded backend
version is `codex-cli 0.167.0`; the CLI exits **3**, state **blocked**, before
research starts. The disposable boundary probe passes and reports
`cleanup_ok=True`. These failures do not establish a scientific demonstration.

Read-only inspection of this host's cgroup hierarchy confirms the prerequisite
failure rather than a wrong service path or an exited probe:

```text
/sys/fs/cgroup/cgroup.controllers: cpuset cpu io memory hugetlb pids rdma misc
/sys/fs/cgroup/cgroup.subtree_control: memory pids
/sys/fs/cgroup/user.slice/cgroup.controllers: memory pids
/sys/fs/cgroup/user.slice/cgroup.subtree_control: memory pids
```

The same `memory pids` values appear at `user-1000.slice`,
`user@1000.service` and `app.slice`; `cpu.max` is absent throughout that user
hierarchy. The CPU controller is available at the host root but unavailable to
these descendants. Requesting systemd `CPUQuota` has not established a kernel
quota, and accepting the missing file would falsely claim enforced protection.
No production or test change can supply the missing host delegation within this
task's authority. Preserve the existing rejection. README now explains this
specific prerequisite and why a successful trivial service is insufficient.
No host configuration, permissions, controller machinery or isolation settings
were changed.

Verification:

```sh
/home/francesco/miniconda3/bin/python -m unittest discover -s tests
/home/francesco/miniconda3/bin/python -m unittest discover -s tests -v \
  > .m1-local/integration-2/tests.txt 2>&1
```

Both commands exit **0**: `Ran 25 tests`, `OK (skipped=2)`, with **24 passing
tests**, including actual Bubblewrap input protection and permitted computation.
Service-class setup skips because this Writer session has neither user-bus
environment variable; the opt-in live test skips because it is not enabled.
The verbose run took 1.153 seconds. The read-only controller-availability snapshot
is preserved in `.m1-local/integration-2/runtime.json`.

The enabled controller test's **one failure and one setup error remain
unresolved**. A host with CPU, memory and task controllers available to the
authorized user-service hierarchy is required before its existing enabled full
suite can validate actual research, resource enforcement, reproduction and
cleanup. This session cannot perform that host repair or submit controller-owned
verification. No additional live run was attempted: it would fail earlier on the
already documented missing Writer bus. No agent or compute job was launched or
left running. `PROJECT.md`, root `AGENTS.md`, human inputs and manager-owned
`STATUS.md` were not edited.

## Integration repair 2 recovery — remove the CPU-quota requirement

Read the preserved recovery response and full failure output from the existing
local artifact files after the artifact reader refused those paths. The response
explicitly authorizes removing the plan-imposed CPU quota within M1; no host
configuration or alternate execution mechanism is authorized or needed.

Removed `--cpu-percent`, `Config.cpu_percent`, saved CPU limit fields,
`CPUQuota`, and the `cpu.max` preflight check. Actual live CLI and reproduction
commands now use wall, memory and task limits only. Status/inspection limitations
and README explicitly disclose that CPU fraction and aggregate CPU time are not
capped. Historical commands and failure receipts above and under `.m1-local/`
remain intact. They describe the superseded contract.

The production launcher still requests `MemoryMax`, `MemorySwapMax=0`,
`TasksMax`, `RuntimeMaxSec`, the per-file bound and whole-control-group cleanup.
Preflight still checks actual memory, zero-swap and task settings. Namespace and
mount boundaries, protected-input checks, one researcher, monotonic deadlines,
detached-descendant cleanup and enabled-acceptance failure behavior are unchanged.
No optional-resource framework, fallback sandbox, controller change or later
milestone functionality was introduced.

Regression coverage exercises preflight with memory/pids settings and **no
`cpu.max` file**. Each remaining cgroup setting must reject absent, unlimited or
incorrect values. CLI checks reject the removed option without creating a run,
and successful saved/inspected status contains no CPU-percentage limit and
discloses the uncapped CPU limitation. Existing real service and live research
tests retain their checks and explicit opt-in behavior.

Writer-local verification commands:

```sh
mkdir -p .m1-local/integration-2-recovery/tmp
TMPDIR="$PWD/.m1-local/integration-2-recovery/tmp" \
  /home/francesco/miniconda3/bin/python -m unittest discover -s tests -v \
  > .m1-local/integration-2-recovery/tests.txt 2>&1
PYTHONPATH="$PWD/src" /home/francesco/miniconda3/bin/python \
  -m research_pipeline start --help \
  > .m1-local/integration-2-recovery/start-help.txt
sha256sum -c .m1-local/integration-2-recovery/protected-before.sha256
```

All exit **0**. The final suite reports `Ran 26 tests in 1.159s`,
`OK (skipped=2)`: **25 tests pass**, including actual Bubblewrap protected-input
enforcement and permitted computation. Service-class setup skips for this
Writer's unavailable user bus; live research skips because it is not enabled.
No host bus/authentication access or live research invocation was attempted.
The regression's cgroup service doubles establish validation behavior only;
actual memory/tasks/swap enforcement and descendant cleanup still require
enabled controller verification. Before/after SHA-256 manifests confirm
`PROJECT.md`, root `AGENTS.md` and manager-owned `STATUS.md` are unchanged.

Reviewed the repair against the preserved failure: neither service startup nor
preflight now requests a CPU controller, while remaining protection requests and
checks are retained. The implementation repair is ready for review and returns
directly to the existing integrated final suite with
`RESEARCH_PIPELINE_M1_LIVE=1` and the same private request output directory.
No additional implementation milestone is required. This is **not M1 scientific
completion**: actual Codex research, primary-literature assessment, numerical
reproduction and cleanup must pass in that pipeline evidence. No demonstration
agents or compute jobs were launched or left running by this recovery.
