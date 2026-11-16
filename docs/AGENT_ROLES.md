# Agent roles

Three roles that run the same way: one persistent CLI session at a time, inside its
confinement ([CONFINEMENT.md](CONFINEMENT.md)), with the controller's tools
([TOOLS.md](TOOLS.md)). Each agent keeps its id and its folder `agents/<id>/`
across any number of sessions.

| | Primary | Subagent | Reviewer |
|---|---|---|---|
| Started by | The controller, at launch | `spawn`, by any agent | A COMPLETE or STOP proposal |
| CLI, model, effort | `--primary` | The `spawn` arguments | `--reviewer` |
| Opening message | The questions, FEEDBACK.md, an inventory of the starting evidence, the reference paths | TASK.md, and PARENT_FEEDBACK.md after a rejection | The review request |
| Writes, besides its folder, `sources/` and `tools/` | STATUS.md, REPORT.md, root FOLDER_CONTENT.md | — | `reviews/` |
| Finishes with | `complete` or `stop` | `submit_result` | `verdict` |

## What every session receives

- **Session instructions** (system or developer prompt, in force for the whole
  session): the role prompt (`prompts/common.md` and the role's file), then the
  project's `AGENTS.md`, shortened beyond 20,000 characters.
- **Opening message:**
  - the session number;
  - the role's sections above;
  - HANDOFF.md if there is one (otherwise: "write a short plan and a first HANDOFF.md");
  - any queued notices.
- Nothing else: the CLIs load none of the human's own setup ([DRIVERS.md](DRIVERS.md)).

## Subagents

- `spawn(task, backend, model, effort, name)` needs all four arguments. The brief
  `task` (a non-empty Markdown file) is copied to `agents/<id>/TASK.md`. The id
  comes from `name`: lower case, dashes, at most 40 characters, with `-2` or `-3`
  added if taken.
- Spawning does not stop the parent: it keeps doing whatever does not depend on the
  subagent, and news reaches it even during its turn. It ends its turn only when
  nothing useful remains until a subagent or job reports.
- `submit_result` requires a non-empty RESULT.md, no running subagents or jobs of
  its own, and a passing layout check. The subagent is then `submitted`. Its
  session ends with its turn (after 120 s at most), and its parent is told at once.
- The parent decides what happens next:
  - **accept:** the subagent ends;
  - **reject(feedback):** the feedback is appended to PARENT_FEEDBACK.md, and a
    fresh session continues from HANDOFF.md. If its CLI is held or every slot is
    taken, it waits; the rejection still stands;
  - **cancel:** the subagent, its whole subtree and all their jobs stop.
- The Reviewer's subagents are its helpers, for independent checks.

## Messages

- `message(agent, text)` works between a parent and its direct subagents, in both directions.
- It is delivered during the recipient's turn, or at its next session if it has none.
- Messages are not stored in files: the recipient notes what matters.
- Refused when the agents aren't parent and subagent, the text is empty, the
  recipient has ended, or the recipient has submitted its result. In that last
  case, use accept, reject or cancel.

## When agents stop working

For waiting, idle and stalled agents, see [CONTROLLER.md](CONTROLLER.md). For handoffs, see [CONTEXT.md](CONTEXT.md).
