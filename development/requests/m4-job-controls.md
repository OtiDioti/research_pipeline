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

The same fresh research session must emit code mode's actual `ALL_TOOLS` catalog.
The gate accepts catalog output only from completed tool-result output, rejecting
agent prose, input/source text, missing controlled tools and unrestricted or
unknown routes. This is a mandatory new controller-host observation, not a claim
that a configuration listing or engineering double proves the effective surface.
If native event/catalog shape or capabilities differ, the enabled gate fails;
inspect the exact fresh native receipt before changing any assumptions.

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
