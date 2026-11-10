# M2 checkpoint foundation — milestone 001

Implemented the supplied milestone plan: quiescent checkpoints, foreground
`resume`, `redirect` and distinct `feedback`. Full live pause, automatic context
rollover and the opt-in real M2 scientific demonstration belong to subsequent
milestones. This report transfers code readiness to controller final verification;
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

## Validation and remaining gates

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

The local process lacks the required systemd user bus, so the service/cgroup test
class could not run. Paid M1 inference was not enabled. No paid Codex-backed M2
evidence is claimed. Controller final verification must still run available host
checks; later milestones must deliver and demonstrate actual full pause and
automatic primary rollover before M2 acceptance.
