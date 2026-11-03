# Development test validation

Run `python3 -B implementation/scripts/validate.py` from the candidate checkout.
Automatic scheduling is the default. For a complete comparison run:

```bash
python3 -B implementation/scripts/validate.py --sequential
```

Both commands derive their root from the script location, check root layout and
required documents, enforce candidate package origin, disable bytecode writes,
and discover the entire suite. There are no filtering, alternate-root, skipping,
caching or replay options. Abbreviated options are rejected. The self-contained
script can be copied alone into a disposable candidate's `implementation/scripts`.
Importing it does not validate, install handlers or create processes.

The Python entry points `run_validation(root, stream, *, sequential=False)` and
`run_suite(root, stream, *, sequential=False)` retain integer-status and boolean
results respectively. Call them from a **fresh, single-threaded Linux interpreter
with no existing child processes**. Native threads are checked through `/proc`
as well as Python's thread registry. Discovery hooks that leave live threads or
children make execution unsupported; hooks are not replayed. Linux fork, wait4,
proc ancestry and prctl subreaping are required. Missing lifecycle facilities
produce operational failure. Missing CPU affinity alone selects sequential work.
The validator neither changes the coordinator's affinity nor raises resource
limits. The existing soft file-descriptor prerequisite of 4096 still applies.

## Discovery, fixture ownership and exceptional dependencies

One fresh unittest loader calls
`discover(implementation/tests, pattern='test_*.py', top_level_dir='implementation')`.
Ordinary added modules, classes and methods join discovery without registration or
scheduler changes. Discovery exceptions retain tracebacks; loader errors and failed
imports always fail validation, even alongside passing tests.

The planner inventories actual discovered objects and their concrete class/module
identities. It preserves leaf discovery order and groups contiguous concrete module
owners. Thus an inherited method belongs to the concrete subclass's module fixture,
not the module defining that method. A class or module fixture is never split across
concurrent children. Recurrent module ownership after another owner selects intact
sequential execution, preserving fixture transitions instead of regrouping tests.
Duplicate IDs, repeated objects, cycles and inconsistent counts fail explicitly.

Only stock suite trees with ordinary TestCase execution are parallelized. Discovery
hooks, custom suites, custom execution machinery and FunctionTestCase use the
original discovered suite intact in one supervised child. No names are reloaded,
no hook is called again, and no run method is replaced. Custom suites must expose
a stable stock-backed list through stock iteration for safe inventory inspection;
opaque inventories fail explicitly. Known custom execution order is retained in
the event ledger. An unexplained omitted, repeated or additional leaf fails accounting.
Fixture inference requires proven stock traversal. A custom runner's stock-backed
inventory cannot distinguish complete traversal from execution of a temporary
partial stock suite. Consequently custom execution with fixture-suppressed leaves
fails conservatively: those leaves remain `not-run`, even if the author intended
complete traversal or a peer passed. Custom reordered execution remains supported
when every leaf supplies complete start/outcome/stop evidence. Explicit sequential
mode, serial metadata or a hook returning a stock tree do not themselves prevent
stock fixture inference.

After discovery and inventory inspection, the planner checks the live process-global
`unittest.case._module_cleanups` stack. Import-time or discovery-time registrations
select exclusive execution of the **original discovered suite**, with the reason
`pending process-global unittest module cleanups`. The stack stores opaque callbacks
and arguments, with no trustworthy per-module ownership mapping. Stock unittest
drains it in LIFO order at module teardown or after failed module setup: a callback
registered while importing a later-running module can run during an earlier module's
teardown, before the later module's setup. Splitting the suite would duplicate the
inherited stack and change those transitions. Intact traversal preserves callback
order, exception selection and skip/error outcomes without clearing, transferring
or replaying callbacks. Explicit sequential mode retains this reason as well.

Supported introspection is limited to stock CPython with an exact built-in `list`
at that private attribute. Only an empty list establishes an empty stack. Missing
state, other representations (including list subclasses) and other Python
implementations select the same exclusive fallback with
`unavailable or unrecognized unittest module cleanup state`. This private stdlib
interface is a limitation, not a portable guarantee. Ordinary tests still need no
registration; cleanups registered during execution remain managed by stock fixtures
inside the existing execution units. Empty discovery still fails positive coverage
without creating a worker. Cleanup fallback alone does not disable stock fixture
accounting, and ordinary suites with an empty stack remain eligible for concurrency.

Ordinary tests must isolate mutable external resources and clean up their own
threads/processes. Reusing immutable declarations, fixture builders or setup-only
base classes does not itself imply a shared live resource. Process isolation
separates cwd changes, patches and mutable Python globals. It cannot infer arbitrary
undeclared dependencies on external services, fixed paths or ordering effects.

Declare an exceptional shared external resource or order dependence with:

```python
VALIDATION_SERIAL = True
```

The declaration may be on a discovered test package/module, a loaded candidate-local
fixture-helper module, or a test class/base class. Loaded candidate-local modules
and every discovered class MRO are inspected dynamically after discovery. Absence
and `False` mean no declaration; other values are configuration failures. Any `True`
selects the **entire original suite** for exclusive sequential execution, including
ordinary peers. This intentionally conservative contract needs no dependency graph,
ordinary-test allow-list or manually maintained module assignments.

## Independence audit and source protection

The supplied immutable `SAFETY.md` and `BASELINE.json` are baseline evidence, not
runtime scheduler input. The prior inventory contains 1063 unique tests and 85
fixture-owner modules; neither number nor the module list is embedded in scheduling.
The source review supports ordinary module isolation with these representative paths:

| Resource or effect | Source evidence and scheduling implication |
| --- | --- |
| SQLite, artifacts, backups and mutable files | `implementation/tests/test_store.py`, `test_backup.py`, and `test_resource_recovery.py` create fixture-local stores and paths. Sharing inside a race is intentional and stays within an intact unit. |
| Captured input files and permissions | `snapshot_fixtures.captured_source` takes a caller-owned parent, creates private input modes and excludes the repository from capture. Worker space must remain outside candidate source. |
| Literal `/tmp` | Source/lifecycle fixture tests use unique `TemporaryDirectory(dir='/tmp')` roots because product guards exclude the checkout. Literal `/tmp/evidence.txt`, `/tmp/file` and `/tmp/outside` in assessment/backup tests are rejected input strings, not shared writable fixtures. |
| AF_UNIX sockets and cwd | `test_view_capture.py`, `test_source_capture.py`, `test_work_product_import.py` and `test_cli_proposals.py` bind relative socket names under unique private directories and restore cwd. No fixed TCP listener was found in the inspected tests. |
| Patches and globals | Source, view and lifecycle tests use `unittest.mock.patch` and process-local state. Forked module units isolate their mutations from peers. |
| Imported helpers | `snapshot_fixtures.py`, `lifecycle_rendering_fixtures.py`, `view_capture_fixtures.CaptureFixture` and `view_refresh_fixtures.RefreshFixture` reuse declarations or construct each caller's resources; the latter bases provide setup/helpers rather than inherited test-bearing classes. |
| Class snapshots | `test_lifecycle_rendering.py` and the source/binding lifecycle tests create closed-store detached observations in class fixtures. Those fixtures remain intact and run once per stock fixture transition. |
| Candidate subprocesses | `child_environment` and the example tests select current candidate source and no-bytecode flags. Recovery tests keep bounded subprocess handles and cleanup. |
| Real internal races | `test_store.py`, `test_run_control_recovery.py`, `test_resource_recovery.py` and `test_resource_usage_recovery.py` use real events/barriers, SQLite writes and child processes. Their synchronization and assertions remain unchanged. |

Each execution child receives a unique owner-private, short `v-` temporary directory
under the compatible external temporary base. A base inside candidate source is
rejected. Only the child sets `TMPDIR`, `TEMP`, `TMP` and resets tempfile's cached
directory. HOME, service settings, umask and source paths are unchanged. Literal
`TemporaryDirectory(dir='/tmp')` remains uniquely named but is **not** redirected
by TMPDIR. Restricted advisory sandboxes may deny `/tmp` writes or socket binding;
these failures are reported, not used to weaken the existing fixtures.

The coordinator removes only its owned private directories, after processes are
gone. Cleanup failures fail validation. Abrupt coordinator death cannot execute
Python directory cleanup; external controller recovery remains responsible then.

## CPU constraints and wave boundaries

The resource sampler takes the most restrictive applicable positive CPU bound from
supported `os.process_cpu_count()`, `os.cpu_count()`, current affinity, exposed
cpusets and CPU quotas. Linux `/proc/self/cgroup` is resolved against mountinfo,
including escaped paths, mount roots and separate v1 controller mounts. Every
visible ancestor is inspected. Finite quotas contribute
`max(1, quota // period)`, deliberately rounding fractional capacity down; unlimited
quotas add no bound. CPU range lists are parsed strictly and cpusets intersect.

Absent files differ from unreadable active limits. In v2, controller/delegation
files establish when a missing `cpu.max` is legitimate: the inspected host lists
`cpu` at the root but does not delegate it, and has no descendant/root `cpu.max`.
This alone is not an unknown quota. Hidden ancestry, ambiguous mount mappings,
malformed values and unreadable active limits are explicit limitations; unknown
applicable constraints conservatively force effective `A=1`. Observations describe
only exposed constraints and never claim knowledge of hidden host ancestors.

At a boundary with no workers remaining, `T` is the remaining independent module
unit count (one exclusive unit for an unsafe/dependent layout) and the exact allocation is:

```text
C = min(T // 2, max(0, A - 2))
```

For positive C, the next wave admits at most `2*C` units in discovery order. Every
child gets the same deterministic subset of at most C currently allowed CPU IDs,
leaving at least two allowed IDs out when possible. Each child sets and verifies
its mask before executing tests; descendants inherit it. Affinity-setting failure
is an infrastructure failure, with no unrestricted retry or replay.

A whole wave drains and is reaped before A, T, C and the mask are recomputed. Slots
are not refilled using an old larger T. Changes during a wave cannot authorize
additional admissions. C=0 runs the remaining original-order work in one child;
initial fallback and `--sequential` execute the entire original suite in one child.
Missing affinity reports the formula and limitation, then uses intact sequential
execution. Empty discovery creates no execution child and fails positive coverage.
Wave numbers, A/T/C, admitted concurrency, masks and fallback reasons are deterministic;
durations are separately labeled measurements.

## Results, inventories and transport integrity

Stock unittest suites/cases and TextTestRunner still execute tests. CoverageResult
extends TextTestResult: **only addSuccess credits successful cases**. Successful
subtests are observations, not successful test cases. Multiple subtest failures,
teardown faults or cleanup errors may belong to one leaf. Consequently outcome
counters need not sum to testsRun. Skipped-only, expected-failure-only and empty
suites fail; legitimate mixed skips/expected failures retain unittest semantics.

The Counts line preserves this order:
`discovered testsRun successful skipped expected_failures failures errors unexpected_successes`.
Under proven stock traversal, fixture setup holders account for affected unstarted
leaves as `fixture-skipped` or `fixture-blocked`, with references to actual fixture
events. Custom setup holders retain their original counts and diagnostics but infer
no affected IDs; unstarted leaves remain `not-run` and fail even beside a passing
peer. Fixture events do not invent startTest, stopTest, testsRun or success.
Teardown/cleanup events do not remove
completed leaves. Unexplained omissions remain `not-run` and fail validation.
Formatted exception tracebacks and subtest parameters/reasons are retained.

Reports consolidate units in discovery order, independently of completion order.
Stdout and stderr remain labeled with within-stream byte order; no total ordering
between those streams is claimed. Full event records, per-leaf dispositions and
ordered discovered, started, completed and accounted inventories are emitted.
Completed means a genuine stopTest; accounted additionally includes explained
fixture dispositions. Custom-suite execution order can differ from discovery order
and is preserved separately in per-unit execution-order records and events. Final
started/completed inventories use discovery order for comparison. Compare IDs and dispositions, not
counts alone. Each inventory SHA-256 hashes UTF-8 encoding of:

```python
json.dumps(ids, ensure_ascii=True, separators=(',', ':'))
```

Three private pipes per child carry descriptor-level stdout, stderr and a separate
result protocol. Capturing fd 1/2 includes `os.write` and inherited subprocess
output. Protocol descriptors do not survive exec. Selectors drain all channels
without blocking readline, pickle, multiprocessing queues or disk spooling.

Protocol v1 uses a four-byte unsigned network-order length followed by UTF-8 JSON.
One hello binds version, unit ordinal, PID, inventory digest and actual affinity;
monotonically sequenced callback events precede exactly one end containing counters
and started/completed ordinals. The parent enforces exact field/type schemas,
rejects duplicate JSON keys/non-finite values, reconstructs counters from events,
and checks identity, sequence, accounting and final totals. Unknown IDs, duplicate
or missing callbacks, invalid stock order, partial/oversized frames, trailing
frames and premature EOF fail. A valid report cannot excuse nonzero exit or leaks.

## Bounds, cleanup and failure precedence

All workers and test descendants stay in the inherited CWI process group. The
validator never calls setsid/setpgid or signals that group. Scoped Linux subreaping
adopts orphaned descendants; `/proc` parentage and start-time identities include
children created by threads. Ordinary waits target known workers, preserving
workers' ownership of their subprocess wait statuses. Signaling uses pidfds when
available and verifies stable identities; recycled PIDs are not deliberately signaled.
A worker's surviving/adopted child is a failure, even after a green report or when
it retains output descriptors. Direct workers set a parent-death signal with a
parent-PID race check. Abrupt coordinator death still relies on **CWI group
supervision for arbitrary grandchildren**.

SIGINT/SIGTERM handlers are installed before discovery and remain installed through
final reporting and flushing, then are restored along with the prior subreaper
setting. During cleanup the invocation handlers latch cancellation without
abandoning resource removal. Restoration uses a short blocked-signal handoff:
SIGINT and SIGTERM are blocked together while the prior subreaper setting and both
caller handlers are restored. A bounded pending-signal snapshot consumes and latches
only signals that were unblocked in the caller's saved mask; caller-blocked signals
remain blocked and pending. Standard signals may coalesce. The exact saved mask is
restored last, after all other restoration actions have been attempted and cleanup
protection is cleared. Signals delivered after the handoff follow the restored
caller dispositions. This requires Linux signal-mask/pending-wait facilities and
the single-threaded invocation convention; a cleanup flag alone cannot protect a
handler already returned to the caller. Restoration errors fail validation even
when another restoration action succeeds. A latched cancellation still fails the
invocation, including after workers have genuinely completed. Cancellation,
deadline, output/protocol failure, crashes and scheduler exceptions stop admissions and enter the same
cleanup path. Owned trees receive TERM, at most five seconds of grace, then KILL;
adopted children are rediscovered and reaped. Cleanup does not wait indefinitely
for pipe EOF. Remaining OS identities and secondary cleanup failures are reported
for CWI quiescence enforcement. No uncertain work is automatically replayed.

The internal monotonic deadline is **2650 seconds from run_validation entry**, not
a short per-module timeout. Workers inherit the remaining invocation deadline.
Discovery, cleanup, final reporting/flushing and scoped restoration are included in
the success decision. State is checked after cleanup and worker reporting, after
the final caller-stream flush, and again after restoration; passing test counts
remain provisional until these finish. Late failure does not erase genuine completed
inventories or fabricate uncertain execution. If Python cannot interrupt a
blocking operation promptly, the unchanged external 2700-second CWI supervision
remains authoritative.

Aggregate read-byte limits across all workers are **16 MiB stdout**, **16 MiB stderr**
and a separate **16 MiB protocol integrity allowance**. Frame lengths are checked
before their payload allocation. Coordinator-rendered output is also capped at
16 MiB, including JSON expansion and consolidated stderr, with 1 KiB reserved for
failure diagnostics. This can fail earlier than either individual raw channel.
Discovery's direct output remains subject to external CWI stream limits. Overflow
names its unit/channel/bound, stops execution and invalidates the report; an
incomplete traceback is never claimed complete. Green totals cannot override
transport, lifecycle, deadline or cleanup failure.

## Equivalent-condition measurement

The immutable original benchmark reports 1063/1063, approximately 2103.466 wall
seconds (2102.974 test seconds), 2073.61 user plus 11.35 system CPU seconds, and
340388 KiB GNU time maximum RSS. A second prior full check took 2102.306 test
seconds. These are baseline observations, **not measured candidate acceleration**.
No representative candidate speedup is claimed by this implementation submission.

The coordinator measures the unchanged original baseline, candidate `--sequential`
and candidate automatic command on exact recorded sources under equivalent
Python/platform, CPU/cgroup/affinity, descriptor, environment and external bounds.
Repeat where practical and retain full logs and their hashes. Record the exact
command/check identities and non-secret environment identity without dumping the
environment. Use external process-tree supervision and GNU time (where available)
for wall time, user/system CPU, utilization and memory observations. Do not change
the controller's frozen check commands merely to add a timing wrapper.

Validator diagnostics include source revision, Python/platform, resource bounds
and limitations, inventory hashes/IDs, discovery/planning time, total wall time,
per-unit fork-to-observed-hello latency and execution time. Fork-to-ready includes
parent observation/draining latency; it is not pure fork syscall cost. wait4 usage
reports worker user/system CPU (including reaped child usage under Linux) and
maximum RSS. Coordinator usage is reported separately. Per-process maximum RSS,
including GNU time's maximum, is **not aggregate concurrent-tree memory** and must
not be summed as though peaks were simultaneous. External monitoring is needed to
characterize concurrent memory peaks and contention.

Compare full sequential/automatic discovered/completed/accounted IDs and dispositions
on the same candidate. Use per-unit inventories to distinguish prior test work from
added regression cost; never filter or disable either in full validation. Report
wave-barrier idle time, resource/platform fallbacks, instability and contention.
Synthetic gates prove overlap and isolation, not representative acceleration.
Acceptance, independent review, receipt, exact integration, full post-integration
validation, representative benchmarks and the administrative checkpoint/STOP remain
controller/coordinator-owned gates.
