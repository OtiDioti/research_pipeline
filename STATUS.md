# STATUS.md — Development handoff

**Checkpoint:** Restart documentation prepared; **no implementation or acceptance is asserted by this template**. Reconcile with actual Git, Codex/controller, and `coding_pipeline` state after placing these files in the new checkout.

## Current scope and milestone

- **Product contract:** `project_description.md` (new V0, including 60% subagent context rollover).
- **Milestone:** M1 — Minimal scientific loop.
- **Gate:** Not demonstrated in this new implementation.
- **Active `coding_pipeline` request/run:** None recorded **in this template**; verify actual backend state before launch.
- **Current implementation status:** Unknown until the new checkout is inspected. Do not import completion claims from the archived project.

## Last verified outcome

- New development documentation has been drafted for the restart.
- **No application tests, scientific runs, or integration steps have been executed for the new implementation.**

## Open blockers / decisions

- Confirm the new project's checkout and ensure the deterministic development controller and existing `coding_pipeline` are available and authorized to operate.
- Determine valid local Codex role/model settings from the actual installation; do not import historical selections.
- Scientific live-resource permissions and final human assessment remain separate from engineering milestone completion.

## Next safe action

**Inspect the target checkout, actual controller/backend state, and local permissions.** Then create the first bounded M1 request in `development/requests/` and delegate it through `coding_pipeline`, following `AGENTS.md`. Do not bypass existing controller constraints.

## Handoff fields to maintain during development

Replace or update the relevant entries above at every verified checkpoint, and always before a controller-directed stop. Keep this file short:

- Current milestone and exact demonstrated behavior, with links to evidence.
- Active request path, backend run ID and observed state, if any.
- Integrated/validated revision (when known), not an unverified assumption.
- Concrete blockers/permissions and one next safe action.

Do not duplicate the controller's detailed logs, Git history, or the requests themselves.
