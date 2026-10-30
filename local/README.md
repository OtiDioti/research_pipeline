# Local observations and scratch

This README is tracked; other contents are locally excluded before any CWI run.

Suggested local paths are `live.md`, `attempts/<local-attempt-id>/`, `context/<request-id>/`, and `research/`. Use them for transient handoffs, raw start/status reports, permitted extra context, and private sample vaults.

This is **not** CWI's authoritative state store. Do not copy or move CWI state here as a substitute for its fixed account-state directory. Do not edit `workflow_logs/` or the managed worktree from this area.

A local note can contain a run ID and observed phase, but it cannot authorize recovery or certify completion. Keep secrets out of notes; protect raw reports and review them before publication.

Additional ignored paths for continuous development: `authorization-pending.md`, `backend-maintenance/<incident-id>/`, and `backend-repairs/<incident-id>/`. Preserve grant references, pending audits, regression evidence, and patch backups there while the parent checkout cannot change. Record actual model/effort, cumulative limits, and distinct outer-session/CWI IDs in the live handoff. Do not treat a local observation as an independent grant.
