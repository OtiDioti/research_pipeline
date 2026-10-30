# Development operating authorization

**Record state: TEMPLATE — no continuous-development grant has been recorded here.** Preserve any actual grant already present when applying this update. Proposed policy is in [AUTONOMY.md](AUTONOMY.md).

The supplied first-session prompt authorizes commissioning only when the human actually issues it. The supplied activation prompt authorizes its stated continuous envelope only when the human actually issues it. The existence of a prompt file, roadmap, or checked box is not evidence that either action occurred.

## Effective grant

| Field | Actual value to record |
| --- | --- |
| Authorization ID and revision | Not yet recorded |
| State | NOT_RECORDED / ACTIVE / HOLD / EXHAUSTED / COMPLETED / REVOKED |
| Actual human grant reference and timestamp | Not yet recorded; retain a non-secret copy or digest/reference |
| Repository identity / target branch | Inspect locally |
| Specification revision | Actual source commit/hash |
| Mode | COMMISSIONING until an explicit broader grant exists |
| Allowed phases / requests / dependencies | Initially D00 and one REQ-D01-001 only |
| Integration authority | First accepted source requires human review unless explicitly preauthorized |
| Exact first accepted commit authorized for integration | Not yet established |
| New-start / retry / maintenance limits | Commissioning: at most 3 starts for the same bootstrap request, with diagnosed corrections and safe disposition; no blind retries. Broader defaults require activation |
| Existing Codex allowance or API budget | Not yet established; no purchases implied |
| Permitted services, network/data disclosures | Existing explicitly approved services only |
| Product live-provider / scientific-pilot allowance | Not authorized by this template |
| Model policy | Requested Astra 6.1; exact supported ID must be verified; effort ceiling xhigh |
| Direct backend maintenance | User permits focused necessary repairs; apply BACKEND_MAINTENANCE.md, never direct product implementation |
| Target-host / repository scope | This approved local project; no unrelated repositories or global changes |
| Publication, push, deployment authority | None unless separately recorded |
| Expiry / revocation / completion condition | Actual grant terms; session ending does not itself renew or enlarge authority |

## Recording activation safely

If the first result is accepted-unmerged, the original checkout must remain at its bound base until integration. Capture the human approval first in `local/authorization-pending.md` with the exact commit and terms. After inspecting all preconditions, integrate that exact accepted commit under the actual human approval, then commit this authorization record with the post-integration checkpoint. Do not make a tracked “approval commit” before the fast-forward.

If there is no active or still-bound run, record the actual grant and a clean prelaunch checkpoint before starting. A grant that cannot yet be fulfilled may be recorded, but its unmet prerequisites remain blockers; it does not authorize guessing a model ID or bypassing authentication.

## Consumption and revisions

The limits here are authority; attempt/run records contain consumption evidence; STATUS summarizes the remainder. Count failed starts, resumptions, repairs, unknown liabilities, and previous sessions consistently. Do not edit the approved ceiling upward merely because work remains.

For changes, record the human decision, superseded revision, new bounds, and effective time. Do not erase the previous grant. A restriction/revocation immediately prevents new work; reconcile an in-flight operation safely. A new grant must explicitly say how cumulative resource use carries forward; it never silently resets uncertain liabilities.
