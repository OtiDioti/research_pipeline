# Portable handoff packaging plan

This records the packaging work authorized on 2026-11-13. It is not a new
product milestone and does not authorize L5 acceptance or M5 research.

**Goal:** recover the published source and interrupted L5 checkpoint on a fresh
machine without changing the existing supporting repositories or merging L5.

**Approach:** ordinary Markdown, unchanged historical evidence, a compressed
checkpoint, SHA-256 checksums and one small Python restoration command. Keep
STATUS.md authoritative. Use the existing pipeline's ownership checks.

## Constraints

- Change and publish only research_pipeline.
- Preserve the L5 source at 2e3e7b3e95714e9aa08d84b1d11f7bea01707105.
- Keep L5 unmerged and unaccepted; M5 remains inactive.
- Preserve failed/interrupted results; historical records are not new passes.
- Restore only into a clean, stopped clone; never overwrite a run.
- Recreate Git worktree ownership; do not copy .git registrations or host locks.
- Do not start native inference or paid validation while testing this handoff.

## Task 1: Preserve the handoff inputs

- [x] Copy the frozen L5 request/configuration, roadmap and selected review,
  validation, shutdown and follow-up records with their original bytes.
- [x] Preserve L1-L4 pipeline acceptance state and relevant native receipts.
- [x] Archive L5 checkpoint reports/tests, excluding its worktree, credentials,
  old process locks and disposable model runtime.
- [x] Preserve interrupted final-006 science as a historical archive.

## Task 2: Restore the checkpoint offline

- [x] First demonstrate a failing clean-clone restoration check.
- [x] Implement restore_l5.py using Python's standard library and Git.
- [x] Verify branch identity, relocated paths, checkpoint status and existing
  pipeline worktree ownership checks; refuse an existing run or wrong revision.
- [x] Check discover/status/report without resuming execution.

## Task 3: Document, verify and publish

- [x] Write setup/restart instructions and a manager startup brief using current
  paths, exact component revisions, real prerequisites and explicit gate rules.
- [x] Link the handoff from STATUS.md/README.md and correct the stale scientific
  directory index's superseded time allowances.
- [x] Verify checksums, links, restoration and component preparation from clean
  temporary clones; run the routine project suite with native gates disabled.
- [x] Obtain an independent handoff review and address consequential findings.

Publication follows the final packaging checks: commit the scoped files, push
main and verify GitHub plus unchanged L5. Git history and the final publication
report record that outcome; this document does not embed its own commit hash.

## Review focus

Check that missing run state cannot be mistaken for a resumable run; restoration
does not overwrite existing work; path relocation preserves historical evidence;
auto-merge and native-gate requirements remain explicit; all recovery inputs are
available from published Git objects without the old machine.
