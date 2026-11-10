# M2 checkpoints and full pause — milestones 001–002

Implemented the supplied plans: quiescent checkpoints, foreground `resume`,
`redirect`, distinct `feedback`, and cooperative full `pause`. Automatic context
rollover and the opt-in real M2 scientific demonstration belong to subsequent
milestones. This report transfers code readiness to controller verification;
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
