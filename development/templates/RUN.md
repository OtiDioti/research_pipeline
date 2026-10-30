# Development run — actual CWI UUID

## Identity

| Field | Value |
| --- | --- |
| Phase / request / request source commit | Record actual values |
| CWI run UUID | Actual generated UUID, not an invented label |
| Controller source revision | Exact local clone commit |
| Launch model/runtime/environment record | Link non-secret environment record and retained identity |
| Target branch / original base | Exact recorded values |
| Start / last observation / completion | Actual timestamps with timezone |
| Current CWI phase / outcome | Exact inspected fields |
| Exact accepted commit / final receipt | Actual evidence or NOT ESTABLISHED |
| Integration commit / date / authority | Actual evidence or NOT INTEGRATED |
| Administrative checkpoint commit | May follow the accepted code commit; do not conflate them |

## Assignment and observed result

Summarize intended change, actual implemented behavior, and what remains unsupported. Separate an interrupted attempt from a completed negative result.

## Acceptance evidence

Map request criteria and requirement IDs to actual tests/reviews/artifacts. Record command, outcome, meaningful counts, skipped live checks, unresolved findings, and final source identity. Retain a digest or protected artifact reference for the acceptance receipt where practical; do not dump private prompts or credentials into Git.

## Locations and provenance

Record controller state/artifact relative locations and protected backup identity, diagnostic log location, and local report paths. Machine-absolute/private paths may remain in local records. Git alone does not preserve excluded logs or external run state.

## Integration

Record inspected accepted diff, original-base checks, authorization, exact fast-forward or alternative reviewed integration, and subsequent validation. If source was altered during integration, it is no longer the identical accepted candidate.

## Remaining work and next action

Link backlog entries, effects whose termination is uncertain, prerequisite changes, and one next safe action. State whether resume, a new request, or human decision is appropriate. Do not rewrite CWI historical status to match a manual merge.

## Continuation, authorization, and resource accounting

Actual grant ID/revision; mode; outer coordinator session ID (distinct from CWI UUID); start-attempt label; requested and verified model/provider; explicit effort and available effective-invocation evidence; cumulative starts/recovery/maintenance consumption before/after; measured usage vs unknown liabilities; expiry/remaining authority.

Link backend-maintenance incidents and exact backend revisions if any. State why the original run could safely resume under unchanged code, was safely superseded, or requires human recovery. Preserve old receipts. Record whether next ready work should continue automatically under the grant or the exact reason it cannot.
