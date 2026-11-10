# M3 collaboration and independent verification: engineering readiness

Implements the supplied delegation and independent-verification increments. One
primary owns scientific integration; subordinate researchers and separate verifiers
use the existing bounded coordinator, task workspaces, checkpoints and fresh-context
launcher. The real bounded Codex M3 gate/demonstration is the next planned increment.
This report establishes code readiness, not M3 scientific acceptance.

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

No new paid gate, workflow engine, transcript continuation, claim registry, model
routing or host-permission changes were added. PROJECT.md, root AGENTS.md and manager
STATUS.md were preserved. The README documents the packet/report headings and commands.

## Validation (2026-11-10)

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
