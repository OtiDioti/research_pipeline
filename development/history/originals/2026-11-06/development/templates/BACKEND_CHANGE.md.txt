# CP-nnn — Focused backend repair

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
