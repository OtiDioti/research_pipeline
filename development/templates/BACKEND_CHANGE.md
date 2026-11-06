# CP-nnn — Focused backend repair

Provides the full per-incident backend change record format; placeholders are not execution evidence or authority.

Save the record as `development/backend_changes/CP-ID.md` at a safe checkpoint and link it from the root backend index. While live/base-bound, keep pending detail under `local/backend-maintenance/`. Preserve each attempt and its disposition within the incident record; do not replace failures with a later success.

**Disposition:** DIAGNOSING / CANDIDATE / ADOPTED / REVERTED / BLOCKED. **Event time:** actual timestamp. **Recorded in parent:** actual later checkpoint if delayed.

## Cause and scope

Observed failure; exact command; affected CWI run IDs and request/base; evidence reference; demonstrated root cause; why environment/product failure is not the explanation; smallest intended correction.

## Source and isolation

Backend upstream/base commit; pre-existing dirty changes and their preservation; maintenance branch/worktree; original and adopted revisions; owners/processes inspected; proof of quiescence; old-run disposition. Do not record a missing PID as complete proof.

## Changes

Every changed path and purpose; all attempted/reverted variants; sanitized diff/patch reference and digest; durable backup; remaining compatibility implications. No unrelated refactoring.

## Verification

Failing regression command/result before fix; same command/result after; adjacent/full tests as applicable; relevant negative security/recovery checks; skipped/unavailable tests; Codex/model propagation checks if affected; review method and its independence limitations.

## Adoption and recovery

Adopted exact commit or reason not adopted; no unauthorized push; old run resumed under original code / safely superseded / human recovery required; affected prior evidence requiring reassessment; rollback route; audit transfer status; exactly one next safe action.
