# DEV-095 — Maintain development records by owner and event

Records the human-approved maintenance rule and update-guide mapping, preserving the separation between current views and historical evidence.

## Decision and scope

On 2026-11-06 the human requests implementing the preceding documentation-maintenance analysis, checking every owner in UPDATE_GUIDE and committing the result. This authorizes administrative Markdown only. Product coordination remains stopped after the PID repair; no CWI run, implementation phase, backend repair, model change or limit reset follows.

[AGENTS](../../AGENTS.md) requires consulting [DEVELOPMENT's ownership map](../../DEVELOPMENT.md#4-information-ownership-avoid-competing-status-files) and [UPDATE_GUIDE](../UPDATE_GUIDE.md) before maintenance. Reconcile relevant records at safe checkpoints, but edit only owners whose facts changed. Keep detail once, current views in place and navigation/semantic references synchronized with file changes. The guide supplies event-specific destinations and checks rather than duplicating that table in AGENTS.

Git history preserves routine committed edits; substantive superseded context may need a separately indexed record. Before removing a redundant mutable file, transfer unique information and repair references. Frozen inputs, historical claims and unfinished-run recovery evidence remain intact. Current administrative task labels belong in STATUS; correction of authority metadata cannot change grant content.

## Preservation and verification

The clean pre-change revision is `81b7958b8a9491e05c2548ab5a635608b1995e85`; it preserves every preceding document without another bulk archive. The original shutdown procedure and all other AGENTS sections remain unchanged. Earlier migrations and their evidence retain their original identities under [history](../history/FOLDER_CONTENT.md).

Check documentation links/headings, purpose introductions, immediate-child indexes, semantic owner references and whitespace. Compare protected tracked files, authorized specification digest, retained CWI state hashes and backend identity with the pre-change snapshot. Record results and exact checkpoint identity in ignored `local/documentation-maintenance-policy-20261106/` and `local/live.md`; add no product-test rerun solely for this administrative change.
