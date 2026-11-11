# M4 reference and reusable-tool implementation readiness

Supplied milestones 1 and 2 are implemented. This is code/demonstration readiness,
not whole-M4 acceptance. Enabled controller-host final/combined verification,
pipeline review and pipeline-confirmed LOCAL integration remain required. No paid
M1–M3 gate was repeated. PROJECT.md, engineering AGENTS.md and manager STATUS.md
remain unchanged.

## Implementation decisions

The existing explicit-reference catalog and read-only mounts remain the retrieval
boundary. Host `reference add/remove/list/browse/search/read` commands authorize and
navigate actual UTF-8 full text, with original identity, line locations and hashes.
Missing sources, binary/PDF extraction limitations, clipping and incomplete searches
remain explicit. Reference instructions never become target authority. Scoped
`sources/REUSE.md`, current-input reconciliation, ordinary checkpoints and explicit
frozen verification packets continue to carry scientific qualifications and exact
reused evidence. No retrieval index service, claim database or new controller was
added.

`tools.py` is a standalone standard-library helper mounted read-only alongside an
activation-specific immutable context. Its namespace CLI lists candidates or
matching registrations, stages attributed working copies, runs declared checks to
register them and executes registered argv. There is no host command to execute
scientific tools and no automatic dependency installation. Python functions remain
ordinary imports. The description explicitly lists origin (user/agent), purpose,
native payloads, invocation, dependencies, checks and limitations.

- Discovery never validates or executes. Source registrations are only evidence of
  successful checks in their source environment. Imported copies require local
  checks even when their source registration matches.
- Local scientific inputs, including protected starting evidence and frozen inputs,
  can be copied into the caller's workspace. Registration and execution require its
  own working copy; other tasks, protected inputs and frozen originals stay read-only.
- Staging copies only the description and declared files, rejects collisions,
  traversal, symlinks and private paths, and preserves root/alias, original paths,
  origin and hashes in SOURCE.json. Source instability leaves a preserved failed
  copy and diagnostic reason rather than a registration.
- Registration requires a nonempty researcher-authored Markdown assessment of
  intended use/checks/applicability. VALIDATION.md records pending before checks,
  then success or failure with description/payload hashes, source identity,
  assessment/hash/scope, activation, commands/cwd, Python/PATH observations and
  bounded stdout/stderr excerpts with explicit clipping. Checks must succeed with
  unchanged files/assessment. A changed description cannot validate different argv.
- Invocation requires a matching success in the current activation. Fresh contexts
  revalidate because dependency environments may have disappeared. Researchers
  must also revalidate after changing their environment. Failed execution retains
  partial science and an exact-argv Markdown receipt; it does not erase the earlier
  useful files or turn a failed calculation into scientific success.
- Assessments, validation, receipts and copied Markdown use existing scoped drafts
  and human-edit publication. Native runtime payloads reside in the permitted copy;
  a Markdown runtime dependency must pass ordinary publication before native access.
  SOURCE.json is small attribution metadata, not another state/resource ledger.
- Checks/runs are foreground children of the current production service. They poll
  its effective monotonic deadline and pending suspension request, drain output with
  bounded capture, and inherit filesystem/network/memory/tasks/lifetime controls.
  Detached descendants remain service-owned and existing controller cleanup stops
  them. No operation extends a grant, creates a service or authorizes a reference.

Both primary and coordinator launch paths generate the context after setting the
effective session deadline, poll through existing preparation callbacks and retain
recoverable cumulative accounting. The existing checkpoint, verification and
reference mechanisms were not changed. Prompts/README explain both tool origins,
working-copy adaptation, attribution, local dependency installation, revalidation,
REUSE.md and frozen evidence. Execution checks, source claim status and independent
scientific verification remain distinct.

## Bounded actual demonstration

`tests/test_m4_live.py` is ordinarily discovered and runs only with
RESEARCH_PIPELINE_M4_LIVE=1 plus RESEARCH_PIPELINE_M4_OUTPUT_DIR. Enabled missing
output/authentication/services/isolation fails; no alternate execution context,
authentication bypass or unisolated reproduction is used.

A fresh private directory holds a disclosed prior-input fixture: a preliminary
heuristic, a general user quadrature function/script and meaningful elementary
checks. It supplies no target derivation, target program, target results or fake
successful registration. The actual researcher must discover/search/read the
source, assess its qualifications and applicability, stage/register/invoke the
user tool, then author/register/invoke an attributed agent-developed study of the
squared-denominator periodic integral. The limited explored cases remain explicitly
preliminary; consequential claims still require the existing separate verifier.

The harness requires actual successful standalone retrieval/helper execution events,
matching validation/invocation identities and finite grid results with resolved
convergence against a hidden independent composite-Simpson oracle. Documentation
strings, shell authoring and successful trailing shell statements cannot stand in
for helper execution. Both saved tools are revalidated/reproduced through
isolation.run_isolated with explicit output substitutions and original artifacts
checked unchanged. Harness numerical comparisons are engineering evidence, not
independent Codex scientific verification.

Bounds are one investigation/session of at most 600 seconds, all demonstration
activity/startup/checks/reproduction within a 900-second absolute deadline,
reproduction within 60 seconds of that same allowance, and the entire test including
failure cleanup within 1200 seconds. Finally inventories attempted services, stops
every owned unit and confirms cgroups empty or removed. Failure evidence is retained.
The private receipt and test report contain exact commands, authorizations/source
hashes and fixture disclosure, scientific excerpts, numerical/reproduction
observations, cumulative accounting/unknown telemetry, input/source integrity,
folder indexes and every cleanup observation. Researcher-authored scientific
excerpts and study payloads are also printed as readable text for manager assessment.

## Validation and host limits

Ordinary discovery with all paid gates disabled:

```sh
env RESEARCH_PIPELINE_M1_LIVE=0 RESEARCH_PIPELINE_M2_LIVE=0 \
  RESEARCH_PIPELINE_M3_LIVE=0 RESEARCH_PIPELINE_M4_LIVE=0 \
  python -m unittest discover -s tests -v
```

Initial readiness checks passed: **193 tests, five expected skips** (four disabled paid gates and the
unavailable systemd user-service test class). Actual Bubblewrap filesystem/task/
frozen-evidence boundaries and native code-mode runtime checks passed. Existing
M1–M3 engineering tests retained preparation cancellation/accounting, cumulative
grants, task ownership, rollover, independent criticism, pause and crash recovery.
After the final receipt presentation change, the focused tool/live-gate module
checks also passed: **14 tests, one expected disabled-live skip**.

New tests cover both tool origins, local user-input discovery, successful checks
and reuse with explicit execution doubles; malformed descriptions, missing payloads,
missing executable/dependency, check/runtime/interruption failures, changed files or
assessments, unstable staging, stale/fresh activation records, private/traversal/
symlink boundaries, attribution/source integrity, pending suspension/deadlines,
Markdown publication, checkpoint/resume, cumulative grants and concurrent human edits.
The evidence-parser regression initially rejected a test because shell punctuation
was not tokenized; it was corrected to reject compound shells, then passed.

Production-service tests were added for actual tool registration/check/run
computation, bounded verbose diagnostics, dependency/runtime failures, immutable
sources/helper/context, an agent tool, and detached descendants on normal completion,
timeout and whole-service pause. **These service tests and the actual Codex M4 gate
are unverified on this Writer host, which has no systemd user bus.** The service
class's restricted-host skip is not acceptance evidence. Enabled M4 verification
cannot skip missing prerequisites. Writer/Reviewer readiness transfers to the
existing enabled controller final/combined checks; host receipts are outstanding.

No architectural plan deviation was required. Copying local user inputs before
validation explicitly supports supplied tools without mutating starting evidence.
No Git orchestration, permission changes or agent-session management was performed.

## Review repair

Both supplied findings were reproduced by new unpaid regressions before repair.
Successful and failed foreground processes each waited until the three-second test
deadline when another process retained their output descriptors. The structured
record reader also accepted non-object records and malformed nested fields.

- Foreground completion now starts a drain interval of at most 0.2 seconds, bounded
  by the existing effective deadline. The helper then closes inherited output pipes,
  retains the foreground exit status and captured diagnostics, and records
  `output_drain_incomplete` plus affected clipping flags. The existing service
  continues to own detached descendants and cleanup; no lifetime grant was extended.
- Record loading now requires a version-1 JSON object with valid activation/outcome
  types. Assessments and check entries receive type validation before consumption,
  including explicit argv arrays and integer/null exit codes. Invalid records raise
  actionable ToolErrors, remain ineligible and do not prevent discovery of healthy
  local or reference registrations.

The unpaid subprocess regression uses explicit engineering process/pipe doubles,
never supplied scientific code. It checks successful and failed foreground exits,
retained stdout/stderr, incomplete-capture flags and a detached pipe holder still
alive until its owner cleans it up. Every fixture process is stopped and reaped.
The discovery regression places malformed local and reference registrations beside
healthy tools and confirms candidate reasons and continued eligible listing.
README and the test index document these behaviors.

Repair validation with all paid gates disabled:

- Focused tools, continuity and isolation checks: **44 tests, one expected skip**.
- Full ordinary discovery: **195 tests, five expected skips**, in 12.470 seconds.

Actual Bubblewrap/native-runtime checks passed. The systemd user-service class is
still unavailable on this Writer host, and all four paid gates remain disabled.
Production-service and enabled M4 live verification still require the existing
controller-host handoff; these repairs do not establish whole-M4 acceptance.

## Concrete remaining M4 closeout gaps

Enabled real demonstration evidence, normal review, final/combined verification and
pipeline-confirmed LOCAL integration still determine acceptance. General V0 control/
reporting gaps remain: no backend hard spending cap or reliable context-occupancy
control (fixed session durations cannot guarantee exact 60% occupancy), uncapped CPU
fraction/aggregate CPU time, incomplete model-usage telemetry and no aggregate disk
quota. Tool validation supplies none of these controls. M4/M5 completion and human
scientific acceptance are not claimed.
