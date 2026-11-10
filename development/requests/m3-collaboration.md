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
