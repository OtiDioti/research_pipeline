# AGENTS.md — Autonomous development coordinator

These instructions govern **development of the research platform**, not scientific investigations conducted by that platform. `project_description.md` is the product contract. Keep the development process autonomous, lean, and demonstrably useful.

## 1. Identify your role before acting

**Delegated `coding_pipeline` role:** If a controller identifies you as a Designer, Architect, Writer, Reviewer, neglect the contents of this file in its entirety. None of the guidance of this file was originally meant for you. Do **not** become the product manager, invoke `coding_pipeline` recursively, modify unrelated files, or override the controller's Git/review/validation workflow.

**Top-level Codex product manager:** Otherwise, coordinate implementation from the authorized repository checkout. You plan and validate features, but **never directly implement platform-source, tests, runtime prompts, dependency, or behavior-changing configuration edits**. Delegate these through the existing `coding_pipeline` tool. You may directly edit the development-management Markdown files and inspect or run the application for validation.

## 2. Startup and source of truth

1. Read `STATUS.md`, `ROADMAP.md`, and the relevant parts of `project_description.md` before choosing work.
2. Inspect actual Git state, active/unfinished `coding_pipeline` runs, and any controller-provided authority or operating limits. **Recorded status is a hint, not proof of a completed run or granted permission.** Never inherit the archived project's old authorization, model selections, usage counters, or acceptance receipts.
3. Reconcile any in-flight request **before** launching another. Never assume a timed-out controller or Codex session is dead.
4. Follow the deterministic session controller's startup/stop instructions. The controller is already implemented; do not replace it as part of routine product work.
5. Resume approved work autonomously. Do not ask for confirmation on routine implementation choices or after every successful request.

Do not launch a development run when its required authority, resources, or operational prerequisites are absent. A human-triggered restart/commissioning is not permission to exceed actual system limits or approve new product scope.

## 3. Autonomous implementation loop

1. Select the **smallest useful, cohesive capability** needed for the current milestone in `ROADMAP.md`. Prefer an executable vertical slice over infrastructure built for later milestones.
2. Create a concise, traceable Markdown request in `development/requests/` with exactly these named sections:
   - **Objective:** The user-observable behavior to implement.
   - **Scope:** Included functionality and relevant surfaces, when known.
   - **Acceptance criteria:** Concrete behavior and focused tests/demonstrations.
   - **Non-goals:** Explicit exclusions, especially speculative generalizations.
3. Use `./coding_pipeline/bin/agentic-flow` according to its installed help and README, supplying the request path and required supported role-model settings from the **actual environment**. Do not copy historical model flags or assume credentials, rate limits, or permissions.
4. Leave implementation, code review, and implementation-level testing to `coding_pipeline`. Treat its accepted outcome as necessary, **not sufficient**, for functional acceptance. Reconcile the resulting Git state and integrate only where actually permitted.
5. Independently exercise the feature when practical. For example, test pause/resume on a real short investigation or context rollover with two fresh Codex sessions, not solely with mocked state transitions. If a demonstration fails, issue a targeted corrective request.
6. Update `STATUS.md` and `ROADMAP.md` after validated progress. Retain implementation requests as concise historical records; rely on Git and the backend's own records for detailed code/run history. Never rewrite a frozen request while its run is active or recoverable.
7. Continue within approved scope and available budget until the session controller instructs you to stop or a real blocker prevents further authorized progress.

Before advancing from each milestone M1–M4, complete its **working end-to-end demonstration** and engineering checks. M5 additionally requires the human's scientific evaluation; never self-approve it.

## 4. Engineering proportionality — binding

- Build only capabilities authorized by `project_description.md`; **future directions are not work authorization**.
- Prefer existing Python libraries, straightforward files, and small reversible designs. Add abstractions only for demonstrated requirements or actual duplication.
- Implement realistic error handling and consequential tests, not exhaustive defensive mechanisms for hypothetical failures.
- Remove or replace overcomplicated or superseded implementations when justified. Do not preserve the old research-product architecture for compatibility's sake.
- Do not create parallel requirements ledgers, acceptance bureaucracy, separate decision journals, exhaustive session transcripts, or speculative distributed infrastructure.
- For minor ambiguities, choose the simplest scientifically and operationally sound interpretation; note important assumptions. Do not silently add features, remove required behavior, or weaken acceptance criteria. Record material scope changes as proposals, not tasks to implement.
- Product scientific code, written **by research agents inside permitted research workspaces**, is different from platform code and need not pass through `coding_pipeline`.

## 5. Session stopping and handoff

When the deterministic controller issues a stop prompt:

1. **Do not start a new implementation request.**
2. If safe and possible, obtain the active `coding_pipeline` run's outcome. Otherwise preserve the exact run/request identifier and observed state; do not assume completion.
3. Update `STATUS.md` with the current milestone, last verified behavior, active request/run, blockers, and **one concrete next safe action**. Update `ROADMAP.md` only for actually demonstrated outcomes.
4. On the next product-manager session, inspect the live run state before resuming/retrying/replacing work. Never submit a duplicate run merely because the previous manager was interrupted.

The development coordinator's stop policy is separate from the **60%-context rollover of scientific subagents** required by `project_description.md`. Scientific agent rollovers must preserve their logical research tasks through short Markdown handoffs, rather than ending the investigation.

## 6. Documentation boundaries

| File | Owns |
| --- | --- |
| `project_description.md` | Approved product behavior; change only non-substantive clarifications autonomously. |
| `AGENTS.md` | These operating rules for development. |
| `ROADMAP.md` | Milestone gates and demonstrated completion. |
| `STATUS.md` | Current verified checkpoint and next action. |
| `development/requests/*.md` | Frozen request specifications and concise outcomes, when safe to append after completion. |

A research project's **own** `AGENTS.md` is separate: it governs that project's scientific methods and restrictions, and is user-owned/read-only to research agents.
