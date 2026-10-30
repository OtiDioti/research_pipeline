# coding_pipeline change audit

This file records necessary modifications to the separately cloned development backend. It is not the research product's changelog. Follow [the maintenance policy](development/BACKEND_MAINTENANCE.md).

**Initial record:** no backend source modification was made in preparing this documentation update. This is not a statement about changes that may already exist in your local clone. Inspect and preserve those before adopting this template.

## Changes

| ID | Reason / affected run | Backend base → resulting revision | Paths / patch reference | Regression and wider checks | Disposition |
| --- | --- | --- | --- | --- | --- |
| — | No recorded maintenance event yet | — | — | Not run for a repair | — |

Add one detailed entry per incident using [BACKEND_CHANGE.md](development/templates/BACKEND_CHANGE.md). Include failed and reverted attempts and any pre-existing edits that the repair depended on. Do not replace this audit with a summary that loses earlier changes.

## Recording during an active or base-bound run

Write the full pending entry immediately under `local/backend-maintenance/`, with exact diff/backup references. Keep the original checkout unchanged. Transfer the entry here at the first safe administrative checkpoint; never falsify its event time to match the later commit time.

A backend Git commit lives in a different repository and is not preserved by committing this Markdown file. Preserve a reviewable patch or protected backend backup and record where it can be recovered. Do not push backend changes without separate authority.
