# M4 job controls: implementation and verification handoff

The supplied recovery response resolves the earlier prerequisite escalation:
implement against the installed documented controlled MCP configuration; defer
fresh native effective-tool-catalog and systemd observations to the mandatory
controller-host checks. No new execution context, user-bus retry, authentication
expansion or permissions bypass was used.

PROJECT.md and engineering AGENTS.md were read fully and not edited. Manager
STATUS.md and accepted M1–M4 scientific evidence were not edited. No Git
orchestration, agent-session management, paid research or integration was performed.

## Decisions and scope

- `start --job-runtime-seconds` defaults to 60 and `--max-jobs` to one across the
  investigation. Both controllers persist these settings, restore them on
  continuation and adopt defaults for older supported states only after ownership
  cleanup. Malformed values, booleans and larger requested runtime are rejected.
- One job is an admitted argv invocation and its complete descendant tree.
  Preparation consumes its effective deadline, clamped to the original role and
  investigation deadlines. No queue, automatic retry or job-level memory grant
  was introduced. Supervisor, backend, adapters and science share original
  memory, zero-swap, task and service-wall grants.
- The foreground owner reserves capacity in ordinary run state before authorizing
  the namespace-local adapter. Ownership includes investigation, activation and
  nonce; primary/subordinate/verifier admission shares that authority. Reserved,
  running, stopping and cleanup-unconfirmed work occupies capacity.
- Each job has a trusted Python supervisor outside its nested Bubblewrap PID
  namespace, inside its original role service. An OS timer in this separate
  process covers preparation and execution; another MCP call or job preparation
  cannot delay it. This is a small deviation from supervision directly in the
  adapter: synchronous namespace preparation could otherwise delay another job's
  deadline. The separate supervisor is necessary for the advertised control.
- Teardown checks Bubblewrap's actual namespace-init PID before releasing
  capacity. Exited foreground parents and closed pipes do not establish cleanup.
  Missing namespace information or a lost supervisor retains capacity and
  triggers original service cleanup. Recovery reconciles reservations only after
  confirmed owned-service stop. Partial files remain in permitted workspaces.
- Scientific namespaces omit backend credentials and adapter admission storage.
  Existing scoped mounts, immutable sources/inputs and publication rules apply.
  Dependency scratch persists across jobs within an activation. Job counts do
  not promise CPU fractions or thread counts; backend reasoning/code-mode
  orchestration remains within the aggregate service grant.
- The established `mcp` Python SDK supplies stdio transport. The adapter exposes
  only `job_run`, `job_wait`, `job_status`, `job_cancel`, `write_draft`, `control`.
  Scoped Markdown and fixed checkpoint/collaboration actions remain available
  while scientific admission is blocked; saving cannot execute arbitrary argv.
- Codex retains normal inner permissions, ignored inherited configuration/rules,
  ephemeral contexts and native authentication. `features.shell_tool=false`
  disables command tools; disabling unified execution alone is deliberately not
  used. Apps, plugins and backend spawning are disabled. The platform-owned MCP
  server is required. The installed Python and SDK are mounted read-only.
- Current official sources:
  [configuration reference](https://developers.openai.com/codex/config-reference/)
  documents `features.shell_tool` and ignored unified-exec opt-outs;
  [MCP configuration](https://developers.openai.com/codex/mcp/) documents stdio
  commands, tool allowlists and required startup. These establish configuration
  interfaces, not a passing effective-tool-catalog observation.
- Reusable-tool checks/runs require the immutable admitted-job context and inherit
  its slot/deadline. There is no production helper route outside admission.
  Pending receipts after termination remain unknown/unsuccessful. Controller job
  observations supply timeout/interruption diagnostics independently of helper
  finalization. Successful-command validation uses admitted execution records,
  separately from model usage and stock command events.
  Previously accepted successful-command counts remain separately identified
  during migration; they are not reset or relabeled as bounded-job observations.
- CLI inspection now distinguishes recorded/live active time, remaining allowance,
  job limits/reservations/status, emitted usage and unknown spending/occupancy.
  Lost intervals stay unknown until recovery. Scientific status, findings,
  uncertainties, verification labels and handoffs retain their Markdown flow.

## Existing M4 gate

The existing gate now requests standalone helper argv through `job_run`, checks
admitted execution/cleanup records and records actual configured job limits.
Reproduction revalidates tools inside one admitted job through the production
isolation launcher. The study's scientific question, model-authored derivation,
critical source/tool reuse, 18-row numerical oracle, source/input integrity,
preliminary scope and original grant ceilings are retained.

The gate requires the actual fresh native model-request tool declarations,
including the nested code-mode surface, bound to the emitted native session ID.
The integration-3 repair below replaces the original `ALL_TOOLS` output request:
`codex exec --json` did not expose that evidence. Agent prose, configuration
listings and engineering doubles cannot satisfy the gate. Missing controlled
tools, unrestricted or unknown routes and unsupported native formats fail it.

Enabled host job fixtures retain private directories, exact argv/configuration,
job and output observations, service cleanup results and observed original
cgroup limits under `RESEARCH_PIPELINE_M4_OUTPUT_DIR`. The native numerical
engineering fixture computes 285, exercises a 1.5-second job limit, keeps partial
data, refuses concurrent admission, tests both detached output-descriptor cases,
handles missing/nonzero executables and saves after scientific work is stopped.

## Verification and remaining acceptance

Controller-host service/native-catalog observations, normal review,
fresh enabled final/required combined checks, actual M4 science/reproduction and
pipeline-confirmed LOCAL integration remain required. This is implementation
readiness only; it does not close M4, M5 or the project.

Only `RESEARCH_PIPELINE_M4_LIVE=1` with `RESEARCH_PIPELINE_M4_OUTPUT_DIR` is to be
enabled on the existing controller host. M1/M2/M3 paid gates stay disabled.
Missing prerequisites must fail when enabled. Keep real research sessions at
most 600 seconds, demonstration active work at most 900, isolated reproduction
at most 60 and each whole live test including cleanup at most 1200.

Initial implementation verification, from the supplied worktree:

```sh
PYTHONPATH=src:/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T002338_830acaa4/runtime/tmp/job-deps python -m unittest discover -s tests
```

**208 tests reported: 201 passed, seven skipped, 19.366 seconds.** The four paid
M1/M2/M3/M4 gates were disabled. Three skips represent unavailable user-bus
verification: the existing production-service test class and two new job/service
checks. No disabled or unavailable check is claimed as acceptance evidence.
The emitted `Owned service cleanup unconfirmed; launch blocked` diagnostic is an
expected injected-failure test, not a suite failure.

Full output is preserved at
`/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T002338_830acaa4/runtime/tmp/jobs-verified.txt`.
The focused job suite separately reported eleven tests in 5.129 seconds, passing
with the two service checks unavailable; its output is `../runtime/tmp/jobs-teardown.txt`
relative to the worktree.

The available native test uses real nested Bubblewrap namespaces and the installed
MCP stdio client/server without inference or credentials. It observed the six
fixed adapter operations, an actual calculation yielding **285**, 1.5-second
runtime expiry with retained `partial` data, refused concurrent admission,
teardown of detached children with both closed and inherited pipes, subsequent
admission, exit 7, a missing executable, and a saved Markdown handoff after
scientific admission was blocked. It also checked that scientific commands share
the original cgroup identity and cannot see backend credentials/admission storage.
This proves the namespace/transport component in this environment, not the
unavailable systemd resource or native Codex effective-tool-catalog checks.

Investigation/controller tests cover both ownership paths, primary/delegated and
verifier continuation, cumulative grants, migration without loss of accepted
historical command evidence, malformed limits, interrupted preparation/recovery,
human-edit preservation, tool qualification and finite independent verification.

During native-test development the SDK returned JSON in text content rather than
`structuredContent`; the client fixture now handles the observed representation.
An immediate pause could precede namespace identity reporting, correctly leaving
cleanup unconfirmed. The normal pause fixture now waits for a readiness artifact
written by running work; the product retains the conservative owning-service-stop
fallback whenever namespace identity/cleanup cannot be confirmed. The final
passing tests do not relax the teardown condition.

A subsequent fresh run exposed delayed namespace-init reaping after a detached
child's foreground launcher had already returned. The reservation correctly
remained occupied, but immediate observation needlessly required whole-service
cleanup. Normal teardown now waits at most 0.5 seconds for confirmed PID
disappearance, retaining capacity throughout; unconfirmed teardown still stops
the owning service. A regression explicitly attempts concurrent admission while
the namespace PID remains visible and admits replacement only after the trusted
completion observation. The final full and focused runs above passed after this
correction.

## Review repair — attempt 1

P1: Both the MCP startup command and the per-job supervisor now use Python
`-P -s`. Python excludes the inherited research working directory and user site
while retaining the controller-supplied read-only source/dependency paths.
Scientific argv still supports ordinary workspace imports. Trusted test and
reproduction drivers use the same startup protections.

The existing native namespace regression now plants `work/research_pipeline/`
with hostile `__init__.py`, `job_server.py` and `jobs.py` before MCP startup.
The fixture loads the actual configured MCP argv, initializes the real SDK
transport and runs jobs from that writable working directory. It asserts that
the shadow package never executes, while normal calculation, timeout, admission,
detached-child teardown and saving continue to work.

P2: `status.json` contains at most 32 compact summaries with active work first
and then recent finished work. It omits argv/source and output buffers, bounds
diagnostic text, reports omitted counts, and computes capacity from every
reservation. Full results are published as separate private read-only responses
for `job_status(job_id)`. A new primary activation can inspect retained results,
including entries omitted from its summary; cancellation and waiting retain
their existing activation ownership restrictions.

A regression accumulates 48 jobs with both 8192-byte output buffers (the former
aggregate exceeds 256 KiB), continues into a fresh primary activation and reserves
another job. It checks bounded readable status, correct occupied/maximum capacity,
omission counts and full output retrieval for an older omitted job. Archived
inspection cannot cancel that old job, and path traversal is rejected.

Review-repair verification:

```sh
PYTHONPATH=src:../runtime/tmp/job-deps python -m unittest tests.test_jobs tests.test_cli
PYTHONPATH=src:../runtime/tmp/job-deps python -m unittest discover -s tests
```

Focused: **35 reported, 33 passed, two unavailable service checks skipped,
5.410 seconds**. Full: **209 reported, 202 passed, seven skipped,
19.490 seconds**. Full discovery includes the actual nested-namespace shadow
package/MCP/supervisor regression and the accumulated-output/fresh-context
status regression. The seven skips remain the four disabled paid gates and
three unavailable user-bus checks; no paid gate was enabled for this repair.
Outputs are preserved in `../runtime/tmp/review-repair-focused.txt` and
`../runtime/tmp/review-repair-full.txt`, relative to the supplied worktree.
The expected injected cleanup-failure diagnostic remains part of passing tests.

Controller-host acceptance,
fresh enabled final/combined checks, actual M4 science/reproduction and LOCAL
integration remain pending; the repairs do not waive those requirements.

## Milestone 2 — shared scientific budget observations

Extracted the existing read-only calculation into `budget.py`, shared by CLI
inspection and controller-published agent status. Charging and ownership remain
in the existing controllers. Reports now copy the original configured limits,
identify their observation timestamp, qualify completed-turn model counters, and
describe the supported job boundary and unknown spending/context telemetry.
Historical missing job settings remain unknown during inspection.

`job_status()` now includes the same investigation-wide `budget_report` for every
role while retaining role-scoped job records, the 32-summary bound and separate
full-result access. Inspection reserves no slot. Job/result/usage changes publish
immediately; elapsed-time-only observations refresh about once a second rather
than rewriting every role's snapshot on every poll. Missing status explicitly
returns an unknown budget without extrapolating remaining allowance.

The extraction includes three small correctness clarifications: absent boot
identity cannot establish a live clock, a settled coordinator interval does not
accrue more observed time, and an unobservable preparation interval cannot fall
back to an older session's clock. Unsettled time remains unknown until the
existing recovery path settles it. No new charging or resource authorization was
introduced.

Human `inspect` output includes configured cumulative time, observed spent and
remaining time, memory/zero-swap/tasks/researcher/job limits and model counters.
Fresh role prompts explain shared totals versus role-session deadlines, unknown
telemetry, stopping at limits and grants persisting through waiting, tool checks
and fresh contexts. Scientific Markdown publication and human-edit handling
remain separate. README documents start, calculation, agent/CLI inspection and
pause/resume together.

The existing M4 gate now retains a live CLI budget observation, final readable
and JSON CLI output with exact commands, settled report/state/emitted-usage
comparisons, and `RESEARCH_STATUS.md` alongside the scientific excerpts.
Inspection subprocesses have separate handles and use the existing absolute
deadlines. The researcher-authored study, critical reuse, 18-row oracle, isolated
reproduction, protected inputs and original grant ceilings remain unchanged.
The existing native MCP fixture additionally reads and prints the budget through
the actual tool while capacity is full, before the original job expires.

Verification used the supplied Python and existing installed dependency directory:

```sh
PYTHONPATH=src:../runtime/tmp/job-deps python -m unittest tests.test_jobs tests.test_cli tests.test_continuity tests.test_collaboration
PYTHONPATH=src:../runtime/tmp/job-deps RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 python -m unittest discover -s tests
```

Focused: **87 reported, 85 passed, two unavailable user-bus checks skipped,
12.581 seconds**. Full after the final code/test changes: **213 reported,
206 passed, seven skipped, 22.033 seconds**. Full output:
`../runtime/tmp/m2-reporting-full.txt`; focused output:
`../runtime/tmp/m2-reporting-focused.txt`, relative to the supplied worktree.
`git diff --check` passed. The cleanup-unconfirmed error is expected injected
failure coverage.

Coverage includes live single-agent/coordinator/preparation accounting without
double charging, stopped and exhausted allowances, changed/missing boots,
unknown/partial usage, shared snapshots and throttled refresh, inspection at full
capacity, retained cumulative totals in fresh activations, and read-only human/JSON
CLI inspection. Existing continuation, pause, recovery, scientific publication,
tool validation and independent-verification checks passed. The real nested
Bubblewrap/MCP fixture passed with full-capacity budget inspection, calculation,
runtime expiry, retained partial files and detached-descendant teardown.

The seven full-suite skips are the four disabled paid gates, the unavailable
production-service test class and two unavailable service job checks. No host
service/cgroup observation or fresh native Codex catalog/scientific acceptance
is claimed from these restricted checks. Normal review, enabled controller-host
M4 final/required combined verification and pipeline-confirmed LOCAL integration
remain mandatory in the next milestone. Enable only M4 with its output directory;
M1/M2/M3 stay disabled. This is milestone-2 code readiness, not M4 closeout,
M5 or project completion. PROJECT.md, engineering AGENTS.md, manager STATUS.md
and accepted earlier evidence were preserved.

## Integration-2 repair — bounded MCP operation approval

Read the complete `tests/final-003.txt` report and its command log, the supplied
recovery note, and the failed research activation's native `backend.jsonl`.
The artifact reader refused the supplied paths, so these were read directly
from the preserved local run directory. Final-003 reported 228 tests with one
failure and three disabled paid gates. Its native production job fixtures
passed; the actual M4 researcher produced no scientific jobs or deliverables.

The native log for `m4-live-8qz6saub`, activation
`7ace60131a844dd5955bd5b8c6f7c5ee`, records the concrete cause:
`control`, `job_run` and `write_draft` all failed with
“MCP tool call requires approval, but approval policy is never”.
The SDK transport fixture did not exercise Codex's approval layer. The declared
MCP dependency was present in this attempt and is not the source defect.

`build_command` now sets per-tool `approval_mode="approve"` for exactly the
six existing adapter operations, alongside the same explicit tool allowlist.
No server-wide default approval was added. The existing noninteractive policy,
inner workspace sandbox, disabled stock shell tools, native authentication,
admission/ownership checks, scoped drafts and original cumulative grants remain
in force. This is configuration for the already authorized bounded operations,
not a new command path. README describes the scope.
The official [configuration reference](https://developers.openai.com/codex/config-reference/)
and [MCP documentation](https://developers.openai.com/codex/mcp/), fetched during
this repair using the OpenAI Docs skill, document the per-tool approval setting.

A regression parses the actual generated TOML overrides, compares preauthorized
operations with the real adapter catalog, and requires the fixed allowlist,
required server, never-approval policy and disabled stock shell tools.
It does not claim a native inference observation.

Verification with the configured interpreter and existing prepared dependencies:

```sh
PYTHONPATH=src:../runtime/tmp/milestone-003-deps /home/francesco/miniconda3/bin/python -m unittest tests.test_jobs tests.test_cli
PYTHONPATH=src:../runtime/tmp/milestone-003-deps RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 /home/francesco/miniconda3/bin/python -m unittest discover -s tests -v
```

Focused: **40 reported, 38 passed, two skipped, 6.959 seconds**.
Full: **214 reported, 207 passed, seven skipped, 21.994 seconds**.
Full output is retained at `../runtime/tmp/integration-2-approval-full.txt`.
The nested Bubblewrap/MCP fixture passed, including normal calculation,
timeout, partial artifacts, bounded admission, detached descendants and saving.
The seven skips comprise four disabled paid gates, the unavailable systemd
service test class and two service job checks. The cleanup-unconfirmed error is
expected injected failure coverage.

The restricted environment has no systemd user bus. Fresh enabled controller-host
final and required combined checks must still exercise Codex's actual approval
layer, obtain the effective native tool catalog, complete model-authored M4
science and isolated reproduction, and confirm integrity/accounting/full cleanup.
The failed activation also lacks the required catalog result; no prose claim
or configuration listing replaces it. Existing gate assertions remain intact.
Only M4 is to be enabled on that host, with the existing frozen output directory
and original grant ceilings. No paid research, Git orchestration, component
repair, dependency installation or session/permission management was performed
here. PROJECT.md, engineering AGENTS.md, manager STATUS.md and accepted prior
evidence were preserved. This is repair readiness, not M4 acceptance or LOCAL
integration.

## Integration repair — final-004 native tool evidence

The complete final-004 log reports 229 tests, one failure and three disabled
M1–M3 gates. The failure is `test_m4_live.py`'s missing fresh catalog assertion,
after successful research completion and budget checks. The preserved session
at `live-host-acceptance/m4-live-ahg4neos/project/.research_pipeline/sessions/166eecc520454d50b435600c4a033dcd`
contains 55 completed MCP calls, two web searches, five agent messages and no
code-mode result items. Its stderr is empty. The parser expected code-mode
result items that the installed CLI's JSON stream did not emit. Nothing here
upgrades that failed run or claims its unreached reproduction checks passed.
Its scientific work, reports, inputs and source files remain untouched.

The installed `codex-cli 0.167.0` supports `CODEX_ROLLOUT_TRACE_ROOT` and
`codex debug trace-reduce`. Native trace schema 2 records `inference_started`
events referring to actual serialized request payloads. Those requests include
backend-generated `additional_tools` protocol items, with direct tool schemas
and the enabled nested tool declarations in `functions.exec`'s description.
Inspection used native metadata rendering without inference or credentials;
an unauthenticated diagnostic request returned 401 and confirmed the trace
payload shape. No paid probe, science execution or authentication bypass was
used. That diagnostic is format evidence only, never host acceptance.

The production backend now writes this trace inside its existing temporary
private authentication home. Scientific job namespaces do not mount that home
or receive the trace environment variable. On primary/subordinate/verifier
closure, before removing the home, the controller retains only deduplicated tool
declarations, native manifest/event provenance, model and request SHA-256 in the
session's `native-tools.json`. Full native prompts/responses are removed with the
temporary home. Retained evidence is bounded to 4 MiB; truncation, malformed
data and unsupported formats remain unverified. No workflow, replay mechanism,
extra research session, larger grant or new execution route was added.

The existing M4 gate reads this evidence, matches its root/thread/rollout IDs
against the actual session ID emitted in `backend.jsonl`, validates direct and
nested tool declarations and retains the raw evidence in its private receipt.
Only the exact research_jobs server's six operations satisfy the adapter check.
Command tools, backend spawning and unknown routes still fail. Harmless native
clock and user-input operations are recognized explicitly. The failed
model-output catalog prompt/parser was removed.

Verification in this restricted worker:

```sh
PYTHONPATH=src:../runtime/tmp/milestone-003-deps TMPDIR=../runtime/tmp /home/francesco/miniconda3/bin/python -m unittest tests.test_jobs.AdmissionTests tests.test_cli tests.test_collaboration
PYTHONPATH=src:../runtime/tmp/milestone-003-deps TMPDIR=../runtime/tmp /home/francesco/miniconda3/bin/python -m unittest discover -s tests
PYTHONPATH=src:../runtime/tmp/milestone-003-deps TMPDIR=../runtime/tmp /home/francesco/miniconda3/bin/python -m unittest -v tests.test_isolation.BubblewrapBoundaryTests
```

Paths were expanded to the supplied run's absolute paths when executed.
Focused: **68 passed, 5.271 seconds**. Full after the parser changes:
**217 reported, 210 passed, seven skipped, 21.954 seconds**. The four real
Bubblewrap boundary/native runtime tests also passed separately (1.585 seconds).
Coverage includes native request retention, session identity mismatch, rejecting
user/prose substitutes, incomplete traces, interrupted closure, nested/direct
command bypass detection and retaining all six adapter operations. Existing job
expiry/concurrency/cleanup, budget, continuity, human-edit and verification tests
pass. The cleanup-unconfirmed diagnostic is expected injected-failure coverage.

The metadata renderer's separate diagnostic surface includes collaboration
operations, which the validator deliberately rejects; it is not a substitute for
the effective surface of the actual isolated `exec` session. The enabled host
gate must establish the latter from its own request trace and fail if those
routes are exposed. No diagnostic catalog is imported as research evidence.

The seven skips remain four disabled paid gates and three unavailable systemd
user-bus checks. `systemctl --user show --property=ActiveState` reports that
`DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` are undefined. This worker does
not configure an alternative bus or run paid science. Normal review, a fresh
enabled controller-host M4 final and required combined check, numerical
reproduction/integrity/cleanup evidence and pipeline-confirmed LOCAL integration
remain mandatory. Use the same frozen `RESEARCH_PIPELINE_M4_OUTPUT_DIR` with
only `RESEARCH_PIPELINE_M4_LIVE=1`; M1/M2/M3 stay disabled. This is code readiness,
not M4 acceptance, M5 or project completion.

## Integration repair: final-005 reference citation

Read the complete `tests/final-005.txt.commands/0001.txt` artifact. Despite the
summary's `unavailable: True`, its command output records 232 tests with one
failure and three deliberately disabled M1–M3 gates. The primary exited
successfully after 409.979 active seconds, but final deliverable validation
rejected `/references/prior/outputs/METHOD.md` in `sources/LITERATURE.md`.
That is an authorized scientific namespace path, which the host validator
incorrectly interpreted as an outside-project host path. The failed receipt
records preserved source/input integrity and confirmed service cleanup; its
later acceptance/reproduction checks were not reached. No earlier receipt or
scientific artifact was changed or promoted to passed evidence.

Deliverable validation now resolves `/references/ALIAS/relative-file` with the
existing reference catalog and retrieval path checks. Missing aliases/files,
unavailable or unsafe roots, private paths, traversal (including URL encoding),
symlinks and directory targets fail. Arbitrary outside-project host links
remain rejected, and reference citations cannot satisfy the requirement for a
local computational artifact in `work/`. The README documents citation scope
and recommends the helper's original `source_uri` for links outside isolation.
No execution, grant, scientific-status or native-tool-surface rules changed.

Verification in this restricted worker, using the existing installed dependency:

```sh
PYTHONPATH=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T002338_830acaa4/runtime/tmp/milestone-003-deps /home/francesco/miniconda3/bin/python -m unittest tests.test_references tests.test_cli -v
PYTHONPATH=/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261111T002338_830acaa4/runtime/tmp/milestone-003-deps /home/francesco/miniconda3/bin/python -m unittest discover -s tests -v
```

Focused: **32 passed, 0.369 seconds**. Full: **218 reported, 211 passed,
seven skipped, 21.974 seconds**. Full output is retained at
`runtime/tmp/integration-4-unittest.txt` relative to the pipeline run directory.
The regression covers authorized citations with fragments, rejected reference
targets and the retained local-computation requirement. Seven skips comprise
four opt-in live gates and three unavailable systemd user-bus checks; the
Bubblewrap boundary checks passed. This worker has no production user bus and
did not launch paid research or reproduce scientific code on the host.

Fresh enabled controller-host M4 final and required combined verification remain
mandatory, with only `RESEARCH_PIPELINE_M4_LIVE=1`, the existing frozen
`RESEARCH_PIPELINE_M4_OUTPUT_DIR`, and M1/M2/M3 disabled. This repair establishes
code readiness only; it does not establish M4 acceptance or local integration.
