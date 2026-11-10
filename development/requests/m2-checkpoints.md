# M2 checkpoints, full pause and primary rollover — milestones 001–003

Implemented the supplied plans: quiescent checkpoints, foreground `resume`,
`redirect`, distinct `feedback`, cooperative full `pause` and automatic primary
rollover. The opt-in real M2 scientific demonstration belongs to milestone 004.
This report transfers code readiness to controller verification;
it does not establish M2 acceptance.

## Decisions

- New investigations use schema 2 with stable investigation/logical identity,
  immutable limits and fresh activation/native session identities. Schema 1 stays
  inspectable; no migration of preserved M1 evidence.
- Existing canonical scientific Markdown is mounted read-only. Agents write
  proposed Markdown in a dedicated draft mount. Only after confirmed descendant
  cleanup does the controller validate the batch and compare each target before
  replacement. Concurrent human changes/deletions survive; proposals are retained.
  Human versions intentionally incorporated later receive selective Markdown copies.
- Checkpoints retain immutable handoff/intake Markdown and safe artifact references,
  with the two newest accepted references for fallback. Ordinary science remains
  in place. Failed publication or handoff validation retains the prior checkpoint.
  Partial checkpoints do not require final-deliverable completeness.
- Operational state writes do not overwrite scientific status. Index reconciliation
  preserves modified indexes and indexes newly created preservation directories.
  Untargeted note edits are also detected at checkpoints and carried into resumption.
- Both research and disposable preflight service launch intent are persisted before
  spawning. Available project locks never authorize launching over an unresolved
  old service. Uncertain cleanup prevents publication and further launch.
  Accounting remains pending until inactivity is confirmed, retaining the amount
  already charged for the activation. Recovery adds only the residual interval,
  updates the session total and caps the charge at its original allocation.
- State loading validates the trusted state file before service recovery; intake
  validates other operational paths individually afterward. Historical untrusted
  drafts are never recursively validated during either step. Symlinks/FIFOs reject
  publication of that batch, which stays private for diagnosis, without blocking
  cleanup or continuation from the previous valid checkpoint.
- Completed-turn usage is persisted as emitted, including before controller loss.
  Cached usage remains a separate field. Missing identity/usage is unknown.
  Active time is cumulative. Recovery prefers observed service inactivity on the
  same boot; otherwise it conservatively charges elapsed time capped at the saved
  allocation/deadline, with uncertainty disclosed. No reliable occupancy or hard
  model spending cap is claimed.
- Handoff links use ordinary paths relative to `handoffs/primary.md`, preserving
  Markdown navigability. Current inputs govern the continuation prompt; historical
  instructions and scientific feedback cannot change platform limits.

## Milestone 001 validation

`python -m unittest discover -s tests -v`: 40 tests, successful with two skips.
The actual Bubblewrap probe passed, including rejection of canonical note
write/unlink/rename and successful writes through the draft mount. Consequential
orchestration checks cover changed/removed objectives/instructions, feedback,
human edits and deletions, index preservation, invalid/damaged checkpoints,
partial work, competing locks, stale ownership, cleanup failure, cumulative
accounting and a real SIGKILL of a controller at the doubled research boundary.
Completed-turn usage survives that SIGKILL without being counted twice.
Regression checks reproduce both review findings and now cover failed cleanup
followed by delayed recovery (observed inactivity and fallback timing), rejection
of launches after exhaustion, and no double charging. Both symlink and FIFO drafts
are rejected at finalization without disabling continuation; the killed controller
also leaves invalid drafts, and recovery still attempts and confirms service cleanup.

The milestone 001 process lacked the required systemd user bus, so service/cgroup
checks could not run. Paid M1 inference was disabled. No paid Codex-backed M2
evidence was claimed. Current validation and remaining gates follow below.

## Milestone 002: cooperative checkpoints and full pause

- `pause PROJECT` requires no inference/authentication. A separate short-lived
  control lock serializes owner registration, request creation and the final
  request check together with service spawn. The project lock remains held by
  the foreground controller. Requests carry investigation, activation, ownership
  and request identities; duplicates reuse the original request. A requester
  waits without either lock, then acquires the project lock to confirm suspension.
  Replacement owners produce a conflict rather than inheriting old requests.
- The saving grace is 15 seconds from controller observation, capped by the
  existing investigation deadline. The separate confirmation wait is 60 seconds.
  Neither duplicate requests nor readiness retries extend the grace. A one-second
  exit interval after acknowledgement remains within that grace. Startup/preflight
  cancellation prevents subsequent inference; the launcher continues polling
  even when output streams have closed.
- A read-only helper and read-only control mount expose only the checkpoint
  handshake. A separate writable response mount is also included in Codex's
  `workspace-write` roots. Response JSON is size-bounded and opened nonblocking
  without following symlinks; malformed, stale, FIFO and symlink readiness cannot
  authorize a stop target or prevent forced suspension.
- Preparation validates nonempty handoff sections and ordinary scientific links
  against drafts or existing native artifacts. It saves handoff/intake Markdown,
  reference hashes and the publication baseline, and persists preparation before
  acknowledging. Validation and chunked reading/hashing check the original saving
  deadline; expiry abandons preparation and immediately requests service stopping.
  Canonical Markdown stays pinned until descendant cleanup.
- Normal completion, pause and recovery share guarded publication, edit
  preservation, index reconciliation and checkpoint validation. Recovery from
  prepared-state controller loss first confirms service cleanup, then checks
  preparation and attempts publication against the original baseline. Invalid
  preparation/drafts retain the previous checkpoint with an explicit limitation.
  Pending preparation is processed independently of stale-owner/accounting flags,
  so an interruption immediately after the cleanup state write does not strand it.
  Recovered validation/publication/index work has a persisted accounting interval,
  charged once up to the remaining allowance. A lost recovery controller causes
  conservative elapsed-time charging through reentry, with uncertainty disclosed.
- Confirmed cleanup permits `paused` even without a new checkpoint. Unconfirmed
  cleanup remains failed, blocks publication and leaves accounting pending.
  Final pause acknowledgement includes checkpoint outcome, cumulative accounting
  and session outcome. Previous idle/stale outcomes and interruption details are
  retained. Missing final model usage stays unknown.
- The artifact reader refused the supplied paths; the identical local pipeline
  plan, baseline and prior decisions were read directly. No scope deviation:
  this plan explicitly defers rollover and the paid M2 test to later increments.

Validation: `python3 -m unittest discover -s tests -v` passed 56 tests with two
skips. The actual Bubblewrap test passed, including read-only control/helper
mounts, writable responses, helper execution, canonical note protections and
permitted computation. New tests exercise separate duplicate CLI pause callers
while the owner holds the lock, preparation before acknowledgement/publication,
startup/preflight cancellation, stale owners, timeout/conflict, fixed grace,
invalid readiness, cleanup failure, partial/invalid drafts, and a real controller
SIGKILL immediately after preparation acknowledgement. Recovery preserves a
subsequent human edit, retains cumulative usage, and publishes a conflict proposal.
An actual local pipe-worker process with an explicitly doubled service confirms
that polling remains responsive after both output streams close.
Existing residual-time/double-charge and invalid-draft regressions still pass.
Review-repair regressions cover slow reference hashing that expires mid-file,
interruption immediately after persisted cleanup, charged recovery validation and
publication, remaining-allowance exhaustion, and recovery interrupted after its
accounting marker is saved. Repeated recovery does not charge completed intervals
again, and pending preparation survives both interruption points.

The systemd user bus is unavailable in this Writer process, so the production
service class (including the new cooperative worker and forced-stop/closed-pipe
worker with detached heartbeat descendants) remains unexecuted locally. Paid M1
inference is disabled. Either live M1 or M2 enablement now makes unavailable
isolation prerequisites fail instead of skip. Controller verification must run
these host checks; later rollover/demonstration work must still satisfy the real
Codex M2 gate. This is implementation readiness for milestone 002, not full M2
scientific acceptance.

## Milestone 003: automatic primary rollover

- Persist `--primary-session-seconds` separately from immutable resource limits:
  default 300 seconds, finite and greater than the existing 15-second saving grace.
  Missing schema-2 policy defaults on resume. There is no reliable occupancy/capacity
  telemetry, so this is a fixed-duration fallback, not an exact 60% guarantee.
  A reliable occupancy implementation should prefer the specification's 60% default.
- Reuse one checkpoint controller/helper with trusted reasons `pause` and `rollover`.
  Saving starts before the effective session deadline, measured after startup;
  that deadline also bounds the research service and saved crash allocation.
  Pause upgrades retain request identity/timing and take precedence.
- Hold the foreground project lock across sequential sessions and successor
  registration. Preserve investigation/logical identity, ownership nonce, workspace,
  useful artifacts and cumulative budgets. New activations/services use private
  authentication-only homes and fresh ephemeral execution, never native resume or
  transcripts. Reused nonempty native identity fails; missing identity stays unknown.
- Automatic continuation requires acknowledgement before closure, confirmed cleanup,
  revalidated preparation, guarded publication and the ending activation's valid
  checkpoint. Human handoff conflicts block rollover. Ordinary note conflicts remain
  preserved reconciliation inputs. Shared continuation intake reloads current human
  inputs, previous accepted intake, handoff, changed/missing science and interruptions.
- Record a small last/current rollover summary and predecessor/successor references
  in session summaries. Failed saving/publication/startup stops with retained science
  and a limitation; explicit resume remains available. Unknown usage stays sticky.
  One monotonic investigation deadline spans all sessions. Inter-session intake
  belongs to the next interval; its persisted pending marker also makes controller
  loss recoverable without charging the completed predecessor twice.

Validation: `python -m unittest discover -s tests -v` passed 73 tests with two skips.
New controlled-clock checks exercise multiple automatic sessions, unchanged reference
data plus new computation artifacts, fresh native identities/commands/auth homes,
stable ownership, changed/removed inputs, cumulative usage/time, unknown telemetry,
failed saving, changed preparation, human handoff conflicts, unconfirmed cleanup,
successor failure, repeated identity, exhausted allowance and pause precedence.
A real subprocess is killed after checkpoint publication and before successor intake;
recovery retains the checkpoint, charges the preparation interval once and resumes
with interruption disclosure. Existing controller-crash, pause and human-edit checks
still pass. The actual Bubblewrap boundary test passed.

The systemd user bus remains unavailable in this Writer environment; the production
service class, including its new rollover helper/descendant-cleanup worker variant,
could not run here. Paid M1 inference is disabled. These are disclosed local
limitations, not M2 acceptance. Milestone 004 must add the small opt-in actual Codex
demonstration and transfer completion to the enabled controller-host final gate.
No platform isolation, dependencies or controller capabilities were expanded.
