# M3 increment 1: dependent collaboration

Implements selective primary-owned dependent assignments, separate task workspaces,
preliminary delivery and primary integration, concurrent fresh-context rollover,
fixed aggregate memory/process shares, cumulative owner-wall accounting, and full
pause/recovery across owned services. The README documents the CLI/helper flow.
This is engineering readiness for the delegation increment, not M3 acceptance.
Independent verification, bounded disagreement, the opt-in real Codex M3 gate and
its scientific demonstration remain subsequent milestone work in the supplied plan.

## Decisions and deviations

- One foreground coordinator owns a flat task collection with scientific parent
  references. Only the primary authorizes assignments/retries. Full capacity refuses
  immediately; no queue, nested controller, transcript continuation or message board.
  Retrying an unfinished task's saved assignment preserves its objective, parent,
  owner and workspace. Resume does not enlarge the saved grant.
- Each slot receives floor-divided memory/process limits and zero swap. Probes
  reserve a slot and must stop before its research service. One investigation wall
  interval covers overlapping services, startup, saving and finalization. Recovered
  charging cannot reduce already consumed allowance. Missing telemetry stays unknown.
  Admission counts preparing tasks and pending rollovers as allocated; successors
  reuse their own reservation. Resume cannot admit an extra interrupted child into
  a slot retained by a sibling awaiting its successor.
- Existing transport now exposes nonblocking polling and finish, while its synchronous
  wrapper remains the production probe/reproduction interface. No science runs outside
  Bubblewrap/systemd. Original/shared research is read-only to children; the primary
  cannot write child workspaces. Readers mount directories rather than pinning other
  roles' Markdown inodes, so newly published replacements become visible.
  Backend inspection and preflight poll existing sessions during launch preparation,
  so sibling saving requests and acknowledgements remain serviced. Any ready successor
  starts through the outer loop, including when the preparing launch fails.
- Private assignment inputs are copied and local links rebased. Dependencies that
  exist only in private drafts must be explicitly included in the assignment.
  Draft publication validates the entire task-scoped batch before replacement;
  human conflicts preserve canonical science and proposals. Every clean unfinished
  child has a saved researcher handoff or an explicitly controller-authored fallback
  describing unknown/interrupted work; a fallback never qualifies as an acknowledged
  rollover checkpoint. Crash recovery attempts prepared publication before writing
  fallback guidance, avoiding controller-created conflicts at a first checkpoint.
- Rollover requires acknowledged preparation, cleanup, unchanged preparation and a
  valid published checkpoint. Fresh contexts reload current human inputs and saved
  science, preserving task identity while siblings continue. Fixed session durations
  reserve 15 seconds for saving; reliable occupancy is unavailable, so there is no
  exact 60% guarantee. Cumulative billing usage is not occupancy.
- **Plan deviation:** opt-in collaboration uses schema 3, but the accepted default
  single-agent M2 controller/schema-2 resume path remains intact. Automatic schema-2
  normalization was deferred to avoid replacing that proven path in this increment.
  There is no duplicated primary storage inside schema 3. This leaves two bounded
  execution paths and should be considered explicitly in review. Prior evidence,
  human-owned PROJECT.md/root AGENTS.md and manager STATUS.md were not changed.
- Structural checks require delivered-result links in primary scientific notes and
  detect unfinished tasks. They cannot establish substantive scientific correctness;
  all results remain preliminary. Hard spending, exact occupancy, CPU fraction and
  aggregate CPU time remain disclosed limitations.

## Validation (2026-11-10)

`python3 -m unittest discover -s tests -q`: **95 tests run successfully, 3 skips**. The skips
are the disabled paid M1/M2 gates and the unavailable systemd service-test class.
Twenty collaboration tests exercise acknowledged delegated/primary rollover with
stable tasks and fresh native identities, parent progress, delivery/integration,
fixed shares, cumulative usage/wall accounting, full pause, unchanged grants on
resume, human edits/intake reload, capacity/ownership/refusal idempotence, partial
failure, task retry, and real controller-process SIGKILL recovery with engineering
backend/service doubles. These are not real Codex scientific demonstrations.
Review-repair coverage includes a simulated 20-second inspection/preflight overlapping
a sibling's rollover, real inspection-subprocess polling/cancellation, continuation
after a failed launch with its failure explanation retained, and a controller SIGKILL
immediately after a child's first checkpoint acknowledgement. Recovery preserves that
researcher handoff and creates a usable checkpoint without a fallback conflict.
Resume regression coverage supplies two unfinished children with two total slots:
the primary rolls over during the first child's slow preflight, retains its slot,
and continues while the extra child stays interrupted. The test reproduced the
controller-failure shutdown before the repair and passes afterward.

Actual Bubblewrap tests passed for child write/unlink/rename rejection against
parent/sibling research and human inputs, permitted own calculation, and a running
primary reading a replaced child delivery. A production-service test additionally
covers concurrent roles and detached compute cleanup, pending a capable host.

`RESEARCH_PIPELINE_M3_LIVE=1 python3 -m unittest tests.test_isolation.ServiceIsolationTests -v`
**fails as required** here with `Required systemd user bus unavailable during enabled
live acceptance`. No alternate bus, host-permission changes or isolation fallback
were attempted. Cgroup enforcement and concurrent real-service cleanup are therefore
unverified locally and must run in existing controller final verification. No paid
inference or M3 acceptance receipt is claimed by this increment.
