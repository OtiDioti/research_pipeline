# M3 collaboration and independent verification: engineering readiness

Implements the supplied delegation and independent-verification increments. One
primary owns scientific integration; subordinate researchers and separate verifiers
use the existing bounded coordinator, task workspaces, checkpoints and fresh-context
launcher. The bounded real Codex M3 gate is implemented and ready for enabled
controller-host verification after review. This report establishes code readiness,
not M3 scientific acceptance.

## Decisions and scope

- Schema-3 tasks have stable identity, objective, scientific parent, assigning primary
  and workspace across activations. A verifier is a newly created task, never a role
  change of the researcher checked. The accepted schema-2 single-agent M2 path and
  all previous evidence projects remain intact; normalization remains deferred.
- Primary-only helper requests now support verification, response and closure through
  the existing bounded request/ack channel. Waiting verifiers release their slot and
  remain stopped on resume. Preparing tasks and pending rollovers retain reservations.
  Full capacity refuses admission; no queue or additional resource grant is created.
- Explicitly linked evidence is copied into versioned initial/response input trees
  with source paths/hashes and rebased Markdown links. Copies are bounded, regular-file
  only, checked for mutation and installed atomically without executing evidence.
  Local Markdown dependencies must be supplied explicitly. An identical complete
  uncommitted response copy can be recovered after interrupted admission.
- Bubblewrap mounts verifier inputs read-only, protecting code/data and Markdown.
  Scoped draft validation rejects writes into inputs, assignments and accepted check
  reports. CHECK.md and REEXAMINATION.md remain separate. Concurrent human conflicts
  preserve the edited report/proposal and require reassessment before delivery;
  changed accepted packets/reports cannot silently inherit an endorsement.
- Accepted initial and final reports retain SHA-256 fingerprints of every explicitly
  linked local check artifact. Integrity checks cover this evidence as well as packets
  and report text, so altered/deleted code, data or supporting Markdown requires
  reassessment before continuation, delivery or integration. Hashing uses the existing
  streaming reader and investigation deadline; revised checks must use new artifact
  paths. This addresses the review finding without adding another snapshot mechanism.
- Each verifier gets one initial check and at most one committed primary response /
  re-examination. The response and allowance are durable before launch. Failed startup
  or execution can retry the same accepted phase/version without replacing the response
  or resetting its allowance. Repeated packet requests identify the existing check;
  closed exchanges cannot reopen. Pause/crash/rollover do not consume another round.
- Initial objections are scientific deliveries, not backend failures. Final unresolved
  objections or inconclusive re-examination are disputed; initial insufficient evidence
  is preliminary. Declining further exchange preserves a disputed closure explanation.
  Backend failure, malformed reports, missing linked evidence or human conflicts cannot
  produce a completed checked delivery. Structural validation cannot certify science.
- Verifier prompts require independent reconstruction/challenge, actual observations,
  scoped assumptions, reproducible checks and justified targeted tests. Primary synthesis
  links the initial check, accepted response and final check/closure, explains scope,
  assumptions, uncertainty, objections and superseded conclusions. Disputed completed
  work permits normal completion; a fully checked synthesis need not also claim to be
  preliminary. The single-agent preliminary-label requirement remains unchanged. Later originals require a version limitation rather
  than inheriting the frozen evidence's label.
- All roles retain acknowledged preparation, confirmed cleanup, fresh native context,
  current human intake and cumulative owner-wall/usage accounting. Slot memory/process
  shares and zero swap remain aggregate. Fixed session durations reserve 15 seconds
  for saving; occupancy is unavailable, with no exact 60% guarantee. Hard spending,
  CPU fraction/aggregate CPU time and missing usage remain disclosed limitations.

The opt-in paid gate described below adds acceptance evidence without a new workflow
engine, transcript continuation, claim registry, model routing or host-permission changes. PROJECT.md, root AGENTS.md and manager
STATUS.md were preserved. The README documents the packet/report headings and commands.

## Prior engineering validation (2026-11-10)

The focused verification tests use explicit engineering backend/service doubles,
not real scientific receipts. They exercise initial and re-examination rollover with
saved calculations, distinct native sessions, stable task/parent/workspace, parent
progress and cumulative limits; objection/response/targeted-test evidence; disputed
and declined exchanges; capacity, retries and immutable accepted responses; waiting
resume; initial/re-examination pause; human edits; changed evidence versions; missing
artifacts and backend failure. A real controller-process SIGKILL immediately after
response acceptance is recovered and the same accepted re-examination completes in
fresh contexts without another response allowance.

`RESEARCH_PIPELINE_M3_LIVE=1 python -m unittest tests.test_isolation.BubblewrapBoundaryTests -q`: **3 tests passed**. Actual Bubblewrap tests check verifier write/unlink/rename rejection against frozen
code/data/notes, original research and accepted checks, with permitted independent
code execution and scoped final-check publication. The production-service descendant
cleanup test now includes primary, researcher and verifier, pending a capable host.

`python -m unittest tests.test_verification -q`: **21 tests passed**. Review regressions
cover re-examination overwriting/deleting initial data while retaining a valid final
handoff, persisted fingerprints for linked code/data/Markdown, and rejection of changed
initial or final evidence at integration. Both destructive re-examinations remain
incomplete with explicit reassessment guidance.

`python -m unittest discover -s tests -q`: **117 tests run successfully, 3 skips** (disabled
M1/M2 paid gates and the unavailable systemd service-test class). Prior delegation,
M1/M2 continuity and rollover regression coverage remains passing.

`RESEARCH_PIPELINE_M3_LIVE=1 python -m unittest tests.test_isolation.ServiceIsolationTests -q`
**fails as required** here: `Required systemd user bus unavailable during enabled live
acceptance`. No alternate bus or isolation/authentication fallback was attempted.
Cgroup enforcement and real three-role descendant cleanup remain unverified locally;
existing controller-host final verification must run them. No inference was launched.

## Bounded M3 gate and acceptance handoff (2026-11-10)

`tests/test_m3_live.py` adds one normally discovered test enabled only by
`RESEARCH_PIPELINE_M3_LIVE=1`, requiring `RESEARCH_PIPELINE_M3_OUTPUT_DIR`. Disabled
execution creates no demonstration or inference. Enabled execution uses fresh private
projects, production CLI/backend/coordinator/checkpoints/isolation, and fails missing
prerequisites. M1/M2 paid gates must remain disabled. No scientific solutions or
programs are seeded: the primary, dependent researcher and separate verifier author
all substantive work. The trusted harness only observes, parses, hashes and compares
numerics; reproduction runs agent code inside production isolation.

The fixture investigates the leading near-boundary approximation of a periodic
integral. It requires baseline quadrature, an acknowledged fixed-policy delegated
rollover, a distinct native successor computing the reserved near-boundary case,
and substantive parent parameter-study progress during that transition. It also
requires a frozen independent check with an actual supported stress-case objection,
one committed response, a targeted re-examination and integrated checked/disputed
synthesis. An initially checked-only report cannot satisfy the challenge requirement;
it is retained as failed evidence without manufacturing disagreement. Initial accepted
check artifacts remain fingerprinted and unchanged; revised checks use new paths.

Allocations follow the supplied plan: 900 seconds cumulative owner activity, primary
sessions 540 seconds, delegated/verifier sessions 240 seconds, reproduction 60 seconds,
ordinary work cutoff at 1200 seconds and final cleanup cutoff at 1800 seconds. Two
slots divide the 2048 MiB/128-process grant. Unexpected extra contexts fail instead
of retrying paid work. Existing verifier rollover engineering coverage is retained.
Receipts include exact commands, identity/parent/workspace relationships, acknowledged
handoff, preserved baseline/code hashes, successor calculations, parent overlap,
versions and evidence integrity, objection/response/outcome, usage/unknown telemetry,
limits, services/cgroups and observed cleanup before emergency recovery. Available
scientific excerpts, numerical observations and cumulative accounting are printed in
the test report; exit zero and structural labels alone are insufficient.

`isolation.stop_service()` and its systemctl/query helpers accept an optional shared
monotonic deadline, preserving existing callers. Exhaustion grants no new escalation
wait and reports unconfirmed cleanup. The real service enforcement test now uses the
actual schema-3 foreground owner, primary-only helper requests, CLI pause and project
lock, with primary/researcher/verifier services and detached computation descendants.
Only backend/auth/command construction are explicit engineering fixtures; production
isolation, probes, coordination and saving remain real. This test is separate from
paid scientific evidence.

Local validation and the final controller handoff are recorded below. PROJECT.md,
root AGENTS.md, manager STATUS.md and prior M1/M2 evidence remain unchanged. No
scientific acceptance is claimed until normal review, enabled controller final tests
and local integration succeed; no extra Writer milestone waits for host receipts.

### Current local validation

The interrupted review repair retains both harness corrections. Parent progress
collection starts at the observed rollover-saving request and ends at the observed
successor calculation. Acceptance requires new parameter observations and a new
parent command within that interval; progress made only before saving cannot pass.
Isolated reproduction supplies each script's original task working directory through
`cwd` and records it alongside the exact arguments, preserving relative input paths.

- `python -m unittest discover -s tests -q`: **126 tests run, OK with 4 skips** in 6.1 s.
  Skips are the disabled M1/M2/M3 paid gates and the unavailable systemd service class.
- `python -m unittest tests.test_m3_evidence -v`: **6 tests passed**. Regressions
  reject progress occurring only before saving or after successor calculation,
  unchanged science and missing calculation events; accept work during handoff or
  continuation; and execute trusted reproduction fixtures with distinct relative
  inputs in researcher and verifier workspaces.
- With `RESEARCH_PIPELINE_M3_LIVE=1`, all **3 actual Bubblewrap boundary tests pass**.
  Protected original research, verifier inputs and accepted reports reject writes,
  unlinks and renames while role-local scientific computation remains permitted.
- Enabled `tests.test_m3_live` and `tests.test_isolation.ServiceIsolationTests` **fail
  as required**, rather than skip, because this Writer has no `XDG_RUNTIME_DIR` /
  `DBUS_SESSION_BUS_ADDRESS` systemd user bus. The real gate fails before inference,
  saves a fresh failed receipt with the exact prerequisite error and empty owned-unit
  inventory, and reports no cleanup errors. Latest diagnostic receipt:
  `/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261110T135145_2b46d578/runtime/tmp/m3-recovery-check/m3-live-kny8zoiz/receipt.json`.
  No alternate bus, authentication fallback or unisolated science was attempted.

The enabled scientific demonstration and real three-role owner pause remain **unverified
locally**. After normal review, Architect completion must trigger the existing enabled
controller-host final suite with M1/M2 paid gates disabled, and local integration. Any
failure there requires normal implementation repair; this handoff is code readiness,
not an M3 acceptance claim.

### Integration repair: required code-mode runtime (2026-11-10)

The complete `tests/final-003.txt.commands/0001.txt` records one failure: the primary
could not save a handoff. Its native stderr repeatedly says `code-mode host is
disabled`; the backend records no scientific commands. The previous repair disabled
the host after final-002's SIGTRAP, but `codex debug models --bundled` shows that
the installed current models require `tool_mode: code_mode_only`. Feature-list
output alone did not establish usable tools.

The launcher now enables `features.code_mode.enabled` and `features.code_mode_host`.
The [official configuration reference](https://developers.openai.com/codex/config-reference/)
documents the former; the installed 0.167.0 binary supplies the host flag. Model,
authentication, isolation and resource grants are preserved. Backend namespaces set
`TOKIO_WORKER_THREADS=1` to reduce CPU-sized runtime pools. An unpaid native startup
probe, using the production Bubblewrap mounts, starts Codex's idle app server,
exec server and code-mode host together, executes JavaScript and a subprocess, and
counts namespace threads. Original pools reproduce **97 tasks**, exceeding the M3
slot's 64; bounded pools use **50 tasks** and execute successfully. This supports
thread exhaustion as the earlier SIGTRAP cause; the original host's fatal diagnostic
was not retained. This setting does not enforce CPU fraction or aggregate CPU time.

The regression uses installed binaries without inference, credentials or a research
session. It also runs through production systemd isolation with 1024 MiB, zero swap
and **TasksMax=64** when the host prerequisites are available. It checks real execution
and cleanup rather than only configuration strings.

- `python -m unittest discover -s tests -q`: **127 tests run, OK with 4 skips** in
  6.4 s (disabled M1/M2/M3 paid gates and unavailable systemd service class).
- `RESEARCH_PIPELINE_M3_LIVE=1 python -m unittest tests.test_isolation.BubblewrapBoundaryTests -v`:
  **4 tests passed**, including native runtime startup and existing protected-input,
  task-separation and verifier checks.
- Enabled `tests.test_m3_live` and `tests.test_isolation.ServiceIsolationTests` still
  **fail before inference**, as required, because this worker lacks `XDG_RUNTIME_DIR`
  and `DBUS_SESSION_BUS_ADDRESS`. Fresh diagnostic receipt:
  `/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261110T135145_2b46d578/runtime/tmp/m3-integration-2-repair/m3-live-5m3d4u61/receipt.json`.
  No owned services were created; cleanup errors are empty.

The enabled controller-host final suite must establish actual cgroup startup and
scientific acceptance. Local results establish repair readiness, not M3 acceptance.

### Integration repair: rollover saving headroom (2026-11-10)

Read the complete final-004/final-005 command logs and retained private session
diagnostics. Both delegated first contexts reached their hard cap without a readiness
acknowledgement. Final-004's primary saw the rollover request but had no time to save
before its cap; final-005's primary also missed acknowledgement and stopped its still
running child. Final-005's distinct child successor was a primary-requested recovery,
not evidence of successful automatic acknowledged rollover. Neither run reached
independent verification. The successful thread-pool repair is retained.

Collaboration now starts rollover saving one quarter of a session before its cap,
bounded between 15 and 60 seconds. The 240/540-second live policies therefore reserve
60 seconds, allowing another model turn and validation without extending session or
cumulative limits. Prompts and activation receipts expose the reserve. Human pause
still overrides rollover with the existing shared 15-second deadline. The M1/M2
single-agent policy remains unchanged. This is fixed-duration headroom, not measured
context occupancy or a guarantee that every delayed backend will acknowledge.

The live scientific instructions now prioritize compact convergence/uncertainty work,
staged parent progress, prompt successor delivery and integration/checking over the
optional large sweeps and extra programs observed in both failures. No calculations
or conclusions are supplied; all numerical, independence, objection/exchange, overlap,
acknowledgement, isolated reproduction and cleanup assertions remain required.

- `python -m unittest discover -s tests -q`: **130 tests run, OK with 4 expected skips**,
  8.7 seconds. New consequential regressions require primary/researcher saving after
  a 20-second model delay, both verifier phases after an 18-second delay, fresh
  continuation, integration, cumulative accounting and pause overriding slow saving.
- Enabled Bubblewrap checks: **4 passed**, including native runtime startup and the
  actual task/verifier write boundaries.
- Enabled service enforcement and M3 live gate **fail before inference** because
  this worker lacks the systemd user bus (`XDG_RUNTIME_DIR` and
  `DBUS_SESSION_BUS_ADDRESS`). The gate retains a failed prerequisite receipt at
  `/home/francesco/Desktop/gits/research_project/research_pipeline/coding_pipeline/logs/20261110T135145_2b46d578/runtime/tmp/m3-integration-3-repair/m3-live-ggnp30vz/receipt.json`.
  Its owned-unit inventory and cleanup errors are empty.

The integrated scientific failure cannot be revalidated on this worker. Normal
review and the enabled controller-host final suite must establish live success;
M3 remains unaccepted until those checks and local integration succeed. No host
bus/authentication fallback, resource increase or scientific acceptance claim was made.

### Integration repair: independent challenge scope (2026-11-10)

Read the full final-006 command output and frozen packet/CHECK.md from
`m3-live-2hxhi8ti`. Delegation, acknowledged rollover, integration and separate
verification completed. The packet explicitly excluded broader applicability and
submitted only the correct, qualified near-boundary theorem. The verifier reasonably
closed it checked, leaving one verifier session; the gate required an objection,
response and re-examination and failed `1 != 2`. Reopening a checked exchange or
inventing a theorem error would be incorrect.

The demonstration now explicitly submits two subjects: the derived scoped result
and the broader one-percent applicability hypothesis, clearly exploratory rather
than established. The verifier independently tests both and can object to an
unsupported extension while confirming the theorem. No answer or verdict is seeded.
All scientific exchange, continuation, resource, reproduction and cleanup assertions
remain required. A checked-only initial examination now fails with a scope-specific
diagnostic before the verifier-session count. Production coordination is unchanged.
A regression confirms that a checked initial report closes normally, rejects an
attempted response, preserves accepted evidence and launches no further session.

- `python -m unittest tests.test_verification tests.test_m3_evidence -q`: **29 passed**.
- `python -m unittest discover -s tests -q`: **131 run, OK, 4 expected skips**.
- Enabled `tests.test_isolation.BubblewrapBoundaryTests`: **4 passed**, including
  native runtime startup and researcher/verifier write protection.
- Enabled M3 gate and service-enforcement class fail before inference because this
  worker lacks the systemd user bus environment. Fresh prerequisite receipt:
  `runtime/tmp/m3-integration-4-repair/m3-live-12x_dsap/receipt.json` under this
  pipeline run; no owned services and no cleanup errors.

The updated real scientific protocol remains unverified locally. Normal review and
enabled controller-host final verification must establish live acceptance before
local integration; this repair reports readiness, not M3 completion.

### Integration repair: complete verifier handoff schema (2026-11-10)

Read the complete final-008 command log and retained session drafts/receipts from
`m3-live-c674_gm5`. The initial verifier completed its independent objection in
96 seconds but omitted three delegated handoff sections, recording their contents
in CHECK.md instead. Publication rejected the missing `Parent question`. A second
context repaired only that handoff; re-examination then exceeded the live gate's
two-context limit. Primary saving/rollover was acknowledged successfully in this run.

The prompt required those sections earlier, then instructed the verifier to use
“exactly” the shorter primary checklist. Prompt and validation now share one complete
role-specific schema; every required section must contain content in the handoff
itself. The regression follows the prompt's checklist literally through actual
publication, objection delivery, response, re-examination and integration. Substituting
the original shorter checklist reproduces the missing-section failure. With the fix,
both phases finish in two distinct native contexts without a handoff-repair activation.
Scientific judgments in this test remain explicit engineering doubles. Live science,
activation limits, resource grants and all acceptance assertions are unchanged.

- `python -m unittest discover -s tests -q`: **132 run, OK, 4 expected skips**.
- `python -m unittest tests.test_verification -q`: **24 passed**, including the
  completed objection/response exchange with the prompt-derived handoff checklist.
- Enabled `tests.test_isolation.BubblewrapBoundaryTests`: **4 passed**, including
  native runtime startup and protected verifier/research workspaces.
- Enabled M3 live and service checks **fail before inference** because this worker
  lacks `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. Fresh diagnostic receipt:
  `runtime/tmp/m3-integration-5-repair/m3-live-u7_78rdt/receipt.json` under this
  pipeline run; no owned services and no cleanup errors.

Enabled controller-host final verification is still required to establish scientific
acceptance. This repair establishes local code readiness only.

### Integration repair: ordinary scientific integration prose (2026-11-10)

Read the complete final-009 command output and preserved `m3-live-oegk2imb` state
and synthesis. Both delegated tasks completed, including the independent objection,
accepted response and checked re-examination. The synthesis linked every required
accepted artifact and explained its assumptions and numerical limitations, but lacked
the literal nouns `assumptions` and `uncertainty`. The integration validator discarded
all its links because of that keyword filter, reporting a misleading missing-reference
failure.

Removed the prose keyword checklist. Integration still requires the actual outcome
label, every accepted exchange-stage link, unchanged accepted evidence and an explicit
version limitation when original evidence changes. Prompts still require substantive
scientific explanations; the real gate and its scientific assertions are unchanged.
README now distinguishes structural validation from assessing scientific adequacy.
The regression reproduces the original rejection with the old filter and accepts
equivalent scientific prose with the repair; missing links and outcome labels still
fail. This deliberately avoids adding another mandatory report schema or vocabulary.

- Focused verification/collaboration/evidence suite: **53 passed**.
- `python -m unittest discover -s tests -q`: **133 run, OK, 4 expected skips**.
- Enabled actual Bubblewrap boundary/runtime checks: **4 passed**.
- Read-only validation of the preserved final-009 scientific files now returns no
  deliverable or integration failures; accepted evidence integrity passes. This did
  not rewrite the failed receipt, run state or scientific artifacts and is not a new
  scientific acceptance run.
- Enabled M3 live and service-enforcement checks **fail before inference** here because
  the required `XDG_RUNTIME_DIR` / `DBUS_SESSION_BUS_ADDRESS` are absent. Fresh failed
  receipt: `runtime/tmp/m3-integration-6-repair/m3-live-q9qnyfce/receipt.json` under this
  pipeline run. No owned services were created; cleanup errors are empty.

Normal review and enabled controller-host final verification remain required.
PROJECT.md, root AGENTS.md, manager STATUS.md and previous evidence are preserved.

Review follow-up: the live gate duplicated the same prose keyword checklist.
Extracted its synthesis check into `check_synthesis`, removed that checklist, and
extended the existing regression through the exact helper called by live acceptance.
The test first reproduced `Synthesis missing assumptions` after coordinator validation
passed. It now passes and rejects missing child/check/response/final-check links,
missing outcome labels and missing stress-case discussion. The live gate retains its
independent numerical observations, supported objection, finite exchange, fresh-context
continuation, cumulative accounting, isolated reproduction and cleanup checks.
Read-only replay of the preserved final-009 synthesis also passes this helper.

Follow-up validation: **31 focused tests passed; 133 full-suite tests passed with
4 expected skips**. Enabled M3 still fails before inference on the absent systemd
user bus, with no owned services or cleanup errors. Fresh receipt:
`runtime/tmp/m3-integration-6-review-repair/m3-live-osfl4jcr/receipt.json` under this
pipeline run. Controller-host live verification remains necessary.

### Integration repair: timely primary rollover observation (2026-11-10)

Read the complete final-011 command log and preserved `m3-live-_g3kn3qj`
receipt, native commands and artifact timestamps. The primary extended its study
at 261 seconds, after the observed child successor calculation at 247 seconds.
Its only captured transition observation was at saving (211 seconds). The failed
overlap assertion was valid; the receipt must remain failed. The task helper
reported the child as running throughout saving, and primary recognized the
transition only after reading the published handoff.

Task summaries now expose the activation ID and saving reason. Saving requests
publish that status immediately; the primary's routine `--check` prints compact
concurrent status unless its own saving request takes precedence. A fresh activation
clears its predecessor's saving notice. Production and demonstration instructions
explain how to continue independent parent science on the saving signal before
handoff publication. No new messages, queue, resource allowance or acceptance-window
relaxation was added.

- `python -m unittest discover -s tests -q`: **135 run, OK, 4 expected skips**.
- New coordination regression exercises the actual helper during child saving,
  parent progress before publication, and successor identity without stale saving.
  With immediate status publication withheld, it reproduces the missing notification.
  Another regression preserves the primary's own pause precedence.
- Enabled actual Bubblewrap boundary/runtime checks: **4 passed**.
- Enabled M3 and service-enforcement checks **fail before inference** here because
  `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` are absent. Fresh diagnostic:
  `runtime/tmp/m3-integration-7-repair/m3-live-n6yoyrn_/receipt.json` under this
  pipeline run; no owned services and no cleanup errors.

The scientific timing repair remains subject to fresh enabled controller-host final
verification. This is engineering readiness, not M3 acceptance. PROJECT.md, root
AGENTS.md, manager STATUS.md and retained scientific evidence were preserved.

### Integration repair: brief rollover notice and model-turn delay (2026-11-10)

Read the complete final-012 command log and retained `m3-live-qva6baq6` receipt
and primary commands. Saving was observed at 204.99 seconds, successor activation
at 219.87 and its calculation at 234.57. The primary never observed saving while
writing a long report command, then composed another command before extending its
study. Only one transition snapshot exists; the failed overlap assertion is valid.
Delegation, continuation, independent challenge/exchange and cleanup did complete.

Task summaries now expose the scheduled fixed-policy saving time and existing
predecessor relationship. Primary `--check` computes a fresh countdown from that
timestamp, so status need not be republished continuously. Prompts describe staging
short scientific commands and reacting within the same command rather than another
model turn. The live assignment asks the successor to record a scientific prediction
from saved baseline evidence before the reserved calculation. Primary authors its own
conditional expansion; no solution, wait loop, delayed launch or resource grant was
added. The original overlap window and all scientific acceptance assertions remain.

- Full discovery: **137 tests run, OK with 4 expected skips**, 9.0 seconds.
- Enabled actual Bubblewrap boundaries/native runtime: **4 passed**, 1.5 seconds.
- New engineering regressions cover a missed entire saving notice, predecessor
  identity, parent science before successor calculation, and countdown updates from
  an unchanged status snapshot, including no scheduled rollover near the wall limit.
- Enabled M3 and service enforcement **fail before inference**, as required, because
  this worker lacks `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. Fresh failed
  receipt: `runtime/tmp/m3-integration-8-repair/m3-live-m3ieq4zf/receipt.json` under
  this pipeline run; no owned services and no cleanup errors.

This is repair readiness, not live scientific acceptance. Normal review and fresh
enabled controller-host final verification remain necessary. Human-owned requirements,
manager STATUS.md and retained evidence were preserved.

### Integration repair: verifier evidence roles and targeted reproduction (2026-11-10)

Read the complete pre-merge-014 command log and retained `m3-live-yyz5ukqf`
reports, frozen artifacts and successful command events. The second initial JSON
was a valid evidence fingerprint map, alongside nine Simpson observations in
`check.json`. Re-examination independently authored `reexamine.py`, importing
the preserved Simpson routine, and produced four new observations.

The gate now distinguishes numerical tables from verified fingerprint maps by
content. It checks all linked tables coherently, requires boundary/stress coverage
and new re-examination evidence, and rejects unknown, malformed or conflicting
evidence. Each numerical output needs an unambiguous recorded direct Python call
with linked code and exact parameters. All selected initial and targeted outputs
are reproduced in the existing production isolation service, using their own
scripts/workspaces and fresh output paths, then compared with accepted rows.
Unsupported invocation forms fail explicitly. Existing fingerprint preservation,
scientific exchange, rollover, budgets and cleanup checks remain.

- Six new unpaid regressions cover provenance maps, multiple/partitioned tables,
  bad/missing/conflicting evidence, missing/ambiguous execution provenance, and
  separate targeted programs with reproduction of every selected output.
- Full discovery: **143 tests, OK with 4 expected skips**, 9.1 seconds.
- Read-only validation of retained evidence passes for both rounds and their
  executed programs; accepted fingerprints are unchanged. No science was executed.
- Enabled Bubblewrap/native checks: **4 passed**. Enabled M3 and service checks
  fail before inference because this worker lacks the systemd user bus. Receipt:
  `runtime/tmp/m3-integration-9-repair/m3-live-5iyl9zyx/receipt.json` under this
  pipeline run; no owned services or cleanup errors.

This establishes repair readiness only. Fresh enabled controller-host final and
combined verification and normal local integration remain required for acceptance.

Review repair: provenance recognition now validates complete command lists against
a restricted grammar before accepting any invocation. Heredoc executable prefixes
and ordinary chains share the same command validation, including allowed programs
and Python script requirements. Only writer redirections/bodies are opaque; a
prefix containing `exit`, `exec`, `eval` or another unsupported command invalidates
the entire event. Bracketed paths in sanitized backend events are accepted only
as opaque utility arguments, never as recorded Python arguments. Writer headers
and bodies supply no calculation calls. Within the
supported grammar, the first command of each statement is unconditional. Other
members of an `&&` chain count only in the final statement, whose success proves
all members ran. A later statement, including a heredoc writer, can hide an earlier
failed prerequisite; such conditional calls cannot establish provenance. The live
assignment now explains this supported invocation form. Unsupported
control flow, expansion, pipelines, multiline quotes and incomplete heredocs
invalidate the whole event. No shell program is replayed.

Six added regressions cover successful documentation-only heredocs (quoted and
tab-stripped delimiters), documentation with different parameters followed by a
genuine run, unsupported/incomplete structures, skipped checks masked by successful
checksum or heredoc statements, valid unconditional/final-chain calls, and early
shell exits hidden in writer prefixes. The latter reproduced four failures before
repair (`exit`, `exec`, `eval`, and a later chained `exit`). Trusted fixture shell
commands confirm that these successful events never ran Python. Positive coverage
retains checkpoint/mkdir/heredoc, standalone calculation and trailing checkpoint
shapes; unsupported Python prefixes are rejected consistently in both paths.

Full discovery: **149 tests, OK with 4 expected skips**, 9.3 seconds, including
all **18 evidence tests**. Read-only validation recognizes the retained nine-row
`check.py --output check.json` and four-row
`reexamine.py --output reexamination.json` executions, with all 17 accepted artifact
fingerprints unchanged. No agent-written science was executed during this repair.
Enabled Bubblewrap/native runtime checks: **4 passed**. Enabled M3 and service
checks fail before inference because this worker lacks `XDG_RUNTIME_DIR` and
`DBUS_SESSION_BUS_ADDRESS`. Fresh diagnostic receipt:
`runtime/tmp/m3-heredoc-prefix-repair/m3-live-8mn_d1gg/receipt.json` under this
pipeline run; no owned services or cleanup errors. Normal review and fresh enabled
controller-host final/combined verification remain required for acceptance.

### Integration repair: structured evidence audits (2026-11-10)

Read complete final-015 command output and the retained `m3-live-uk1qggkx`
evidence. The failure rejected a legitimate structured fingerprint audit with
supplementary numerical diagnostics. The gate now validates both flat hash maps
and nonempty artifact lists against actual bytes, including optional expected
hashes/match assertions. Supplementary finite numeric diagnostics cannot replace
observation rows; unknown structures, malformed audits and incorrect fingerprints
still fail. Both numerical rounds retain all observation/provenance/reproduction
requirements.

Read-only validation exposed a further rejection before reproduction: the recorded
targeted check followed Python stdin authoring in the same shell event. The narrow
grammar now permits that heredoc consumer, validates its entire executable prefix
and ignores its body for calculation provenance. Early exits, unsupported prefixes,
masked failed prerequisites and documentation-only calls remain rejected. Three
new regressions reproduced both failures before repair and cover false/malformed
audits; existing shell regressions now exercise Python heredocs too.

- Full discovery: **152 tests, OK with 4 expected skips**, 9.3 seconds.
- Focused evidence tests: **21 passed**. Enabled Bubblewrap/native checks:
  **4 passed**.
- Read-only retained-run validation recognizes all **10 initial and 5 targeted
  rows**, their two distinct executed scripts and synthesis links; all **15
  accepted artifact fingerprints remain unchanged**. No science was executed.
- Enabled M3 and service enforcement checks fail before inference because this
  worker lacks `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. Fresh receipt:
  `runtime/tmp/m3-integration-10-repair/m3-live-83vfcmde/receipt.json` under this
  pipeline run; owned services and cleanup errors are empty.

Normal review and fresh enabled controller-host final/combined verification remain
necessary, including isolated scientific reproduction. This repair establishes
code readiness, not live M3 acceptance. Requirements and prior evidence are preserved.

### Integration repair: wrapped primary calculations (2026-11-10)

Read the complete pre-merge-017 output and retained `m3-live-4405llp9` receipt
and native events. The original failure is a false negative: within observed
saving/continuation (209.41–240.03 seconds), the same primary native session
expanded its parameter table from five to eight to eleven rows, preserving all
prior values. Successful event `item_21` executed its scientific helper, whose
output matches the three newly observed threshold/stress rows exactly. The old
filename filter missed this event because the helper invoked `parent.py` internally.

Parent snapshots now retain all successful command events at their actual observation
times, including a separate snapshot when execution completes after its output
appears. Overlap requires new parameters, unchanged prior rows, one unchanged native
session and a new proven Python invocation in the primary's own scientific workspace.
The existing restricted command recognizer excludes documentation, skipped calls,
checkpoint helpers and other roles; it does not interpret helper source or depend
on a helper filename. Verifier provenance recognition is unchanged.

The existing bounded production-isolation reproduction also reruns the parent
program with the observed transition parameters and compares every scientific row.
The primary assignment explicitly requests that parameter-list interface. No timing
window, allowance, resource grant or scientific outcome requirement was relaxed.

- Focused evidence coverage: **28 passed** in full discovery, including the retained wrapped-call shape,
  actual trusted helper/subprocess arithmetic and reproduction, changed native
  identity, changed/missing prior rows, prose/hash-only updates, documentation,
  skipped calls, commands from another role and delayed completion without rewriting
  earlier snapshots.
- Full discovery: **159 tests, OK with 4 expected skips**, 9.5 seconds.
- Read-only retained-evidence validation confirms unchanged prior rows, stable native
  identity, recognized successful helper execution and output matching the new
  numerical rows. No agent-written science was executed, and the historical failed
  receipt remains failed.
- Enabled Bubblewrap/native runtime checks: **4 passed**. Enabled M3 and service
  checks fail before inference because this worker lacks `XDG_RUNTIME_DIR` and
  `DBUS_SESSION_BUS_ADDRESS`. Fresh diagnostic receipt:
  `runtime/tmp/m3-integration-11-repair/m3-live-we6o1oy1/receipt.json` under this
  pipeline run; no owned services or cleanup errors.

Fresh enabled controller-host final/combined verification, including actual isolated
parent reproduction, is still required. This establishes repair readiness only.
Human-owned requirements, manager status and prior scientific evidence are preserved.

### Integration repair 12: explicit numerical evidence roles (2026-11-10)

Resumed the preserved repair and read the complete final-018 failure, recovery
direction and retained science. Replaced the overfitted flat/structured audit parser
(superseding the earlier audit-classification decisions) with an explicit live-demo
interface: CHECK.md and REEXAMINATION.md list consequential JSON tables under
`## Numerical observations`. Missing or malformed selected tables fail. Every table
retains boundary/stress validation, executed-script provenance and isolated
reproduction with its recorded parameters; the new targeted round remains required.
Other linked records use the existing authoritative report/artifact fingerprints and
frozen input manifests. Optional sidecar assertions are unassessed and cannot establish
integrity or substitute for an independent calculation. Receipts record these roles.

Regressions cover flat hashes, structured and mixed integrity records, ordinary
metadata, missing/bad/conflicting observations, canonical fingerprint preservation,
both frozen exchange packets, and separately authored targeted checks with actual
trusted-fixture reproduction. Existing rollover timing/native identity/prior-row
requirements, immutable snapshots, parent reproduction, shell execution-provenance
protections, budgets and cleanup are preserved. No production schema was added.

- Full discovery: **160 tests run, OK, 4 expected skips**, 9.5 seconds.
- Focused evidence/verification/collaboration suite: **80 passed**.
- Read-only validation of `m3-live-yyz5ukqf`, `m3-live-uk1qggkx` and
  `m3-live-7ej_vgn_` passes for their explicit historical numerical roles:
  **9/4, 10/5 and 9/5 initial/targeted rows**, distinct executed check programs,
  synthesis links and **17, 15 and 22** accepted artifact fingerprints. Stress
  relative error is approximately **0.04880885** in each round. Historical reports
  and failed receipts were not rewritten; no retained science executed.
- Enabled Bubblewrap/native-runtime checks: **4 passed**. Enabled M3 and service
  enforcement checks fail before inference because this worker lacks
  `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. Fresh diagnostic receipt:
  `runtime/tmp/m3-evidence-roles-repair/live/m3-live-pgyupewl/receipt.json` under
  this pipeline run; no owned services or cleanup errors. An earlier diagnostic
  command used an unnormalized output path; rerunning with its canonical absolute
  path established the actual prerequisite failure.

Read-only validation script/output and test logs are retained under this pipeline
run's `runtime/tmp/m3-evidence-roles-repair/`. This establishes repair readiness only.
Normal review, fresh enabled controller-host final/combined verification and LOCAL
integration remain required for M3 acceptance. PROJECT.md, root AGENTS.md, manager
STATUS.md and earlier evidence are preserved.

### Integration repair 13: parent execution corroboration (2026-11-10)

Read the complete final-019 failure and repair-12 recovery direction. Read-only
inspection of `m3-live-zmooar8_` confirms data-before-completion at both expansions.
The current overlap code already compares the first and last retained in-window
snapshots, so it preserves the before-state while awaiting successful execution.
The remaining failure was command recognition: the first expansion's compound
event masks the calculation's status and correctly cannot prove success; the
second expansion's successful final `&&` chain was rejected because it includes
`ls` of the child's artifacts. Permit opaque listing only for parent progress.
Verifier provenance rules, masked-failure rejection, numerical reproduction,
immutable snapshots, native identity and the original transition window remain
unchanged. No new observation ledger or timing workaround was needed.

Regression coverage retains the six reported observation times, row counts and
command counts, including delayed completion, missing/out-of-window success,
failed events and changed native identity. The earlier wrapped-calculation
regression also passes. Read-only checks accept final-019's original snapshots
and recognize the older wrapped native event with output equal to the three
saved new rows; historical failed receipts remain unchanged.

- Full discovery: **162 tests, OK, 4 expected skips**, 9.6 seconds.
- Enabled isolation/M3 checks: all four Bubblewrap/native checks pass; systemd
  service setup and live M3 fail before inference because this worker lacks
  `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. Diagnostic receipt:
  `runtime/tmp/m3-integration-13-repair/m3-live-lq3pxusb/receipt.json` under this
  pipeline run; no owned services or cleanup errors.
- Discovery output and read-only retained-evidence observations are saved under
  the same `runtime/tmp/m3-integration-13-repair/` directory.

This establishes repair readiness. Fresh enabled controller-host final/combined
verification, including isolated scientific reproduction, and normal review/local
integration remain required for M3 acceptance. Human-owned requirements, manager
status, scientific artifacts and resource grants are preserved.
