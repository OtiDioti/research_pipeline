# L5 checkpoint and evidence

Captured 2026-11-13 from run `20261113T063709_7f21ba4a`. Source is frozen at
`2e3e7b3e95714e9aa08d84b1d11f7bea01707105`. This handoff does not accept L5.

The [request](request.md), [configuration](config.toml) and [roadmap](roadmap.md)
are copied unchanged. The configuration preserves auto_merge=true, writer_network
preauthorization and the recorded model/effort choices. These historical settings
do not grant a new controller invocation permission to publish or bypass checks.

## Current state

Final-006 was interrupted in native Phase B for manager retirement. Phase A had
reached acknowledged scientific COMPLETE, and Phase B had reopened for corrective
feedback and a human note edit. The shutdown record reports 33 confirmed cleanup
reconciliations. This is partial validation, not a completed native pass.

Read [the retirement receipt](evidence/manager/retirement-003.json),
[the recorded interruption](evidence/manager/retirement-003-interrupt.json) and
[historical ownership reconciliation](evidence/manager/retirement-003-ownership.json).
Those records describe the old host at that time, not current process ownership.

## Earlier failures and reviewed repairs

| Result | Meaning | Subsequent reviewed repair |
| --- | --- | --- |
| Final-002 | Handoff-link/recovery failures | `56adcb5`; [review](evidence/reviews/integration-1/review.md) |
| Final-004 | Accounting completeness assumption failed | `9ac334c`; [review](evidence/reviews/integration-2/review.md) |
| Final-005 | An earlier overlapping draft could overwrite a later job revision | `2e3e7b3`; [review](evidence/reviews/integration-3/review.md) |
| Final-006 | Interrupted during Phase B; no completed result | Ordinary resume must repeat final verification. |

The [latest test evidence](evidence/reviews/integration-3/test-evidence.md) is
routine engineering evidence. The saved checkpoint still contains final-005's
failed result. Preserve it as history; do not mislabel it as final-006 or reopen
its already-reviewed defect without new evidence.

## Archives

- [checkpoint.tar.gz](checkpoint.tar.gz): 202 unchanged files under `run/`,
  including state, all L5 milestone reports/diffs, test outputs and roadmap.
  Model runtime, the old Git worktree and process locks are excluded.
- [native-final-006.tar.gz](native-final-006.tar.gz): 470 historical files under
  `native-final-006/`, including the complete interrupted receipt and retained
  scientific project. Keep it as evidence. Do not treat its runtime records,
  service names, PIDs or scientific COMPLETE from Phase A as a running resumed
  investigation or an overall L5 acceptance.
- `evidence/native/`: original receipts for failed native final-004/final-005
  phases and their separately completed process checks. Their paths and outcomes
  remain unchanged.

To inspect either archive, use `tar -tzf ARCHIVE`. Extract historical science into
a separate scratch directory, never over the active research_example directory.
The top-level CONTENTS.json records hashes for every archive member.

## Follow-ups

The [C1-C3 draft](follow-ups/next-portability-request-draft.md) and
[L6 draft](follow-ups/next-l6-request-draft.md) are unsubmitted proposals. They
retain historical machine paths and require adaptation before a future submission.
They do not authorize work before L5 acceptance. The copied conflict audits under
`evidence/manager/` support the current KNOWN_CONFLICTS.md findings.
