# Agent roles

Four roles that run the same way: one persistent CLI session at a time, inside its
confinement ([CONFINEMENT.md](CONFINEMENT.md)), with the controller's tools
([TOOLS.md](TOOLS.md)). Each agent keeps its id and its folder `agents/<id>/`
across any number of sessions.

| | Primary | Subagent | Reviewer | Librarian |
|---|---|---|---|---|
| Started by | The controller, at launch | `spawn`, by any agent | A COMPLETE or STOP proposal | Its first shelving request |
| CLI, model, effort | `--primary` | The `spawn` arguments | `--reviewer` | `--librarian` |
| Opening message | The questions, FEEDBACK.md, an inventory of the starting evidence, the reference paths | TASK.md, and PARENT_FEEDBACK.md after a rejection | The review request | Its pending shelving requests |
| Writes, besides its folder | STATUS.md, REPORT.md, root FOLDER_CONTENT.md | — | `reviews/` | `library/` pages, through `write_page` |
| Finishes with | `complete` or `stop` | `submit_result` | `verdict` | `shelved`, for each request |

The Librarian does no research: it organises the library ([LIBRARY.md](LIBRARY.md)).
It is not counted against `--max-agents`, has no other tools, and neither sends nor
receives agents' messages (the human can write to it from the web app).

## What every session receives

- **Session instructions** (system or developer prompt, in force for the whole
  session): the role prompt (`prompts/common.md` and the role's file; for the
  Librarian, `prompts/librarian.md` alone), then the project's `AGENTS.md`,
  shortened beyond 20,000 characters.
- **Opening message:**
  - the session number;
  - the role's sections above;
  - HANDOFF.md if there is one (otherwise: "write a short plan and a first HANDOFF.md");
  - any queued notices.
- Nothing else: the CLIs load none of the human's own setup ([DRIVERS.md](DRIVERS.md)).

## Subagents

- `spawn(task, backend, model, effort, name)` needs all four arguments. The role
  prompt limits model and effort to `claude-opus-5-5` (claude) or `gpt-6.1-sol`
  (codex), at `high` or `xhigh`, unless the project's `AGENTS.md` says otherwise. An effort
  Claude Code does not accept (it accepts `low`, `medium`, `high`, `xhigh` and `max`) is
  refused before any session starts; Codex checks the effort itself when the session starts. The brief
  `task` (a non-empty Markdown file) is copied to `agents/<id>/TASK.md`. The id
  comes from `name`: lower case, dashes, at most 40 characters, with `-2` or `-3`
  added if taken.
- Spawning does not stop the parent: it keeps doing whatever does not depend on the
  subagent, and news reaches it even during its turn. It ends its turn only when
  nothing useful remains until a subagent or job reports.
- `submit_result` requires a non-empty RESULT.md, no running subagents or jobs of
  its own, and a passing layout check. The subagent is then `submitted`: it ends
  its turn and waits in its session, its tools refused, and its parent is told at once.
- The parent decides what happens next:
  - **accept:** the subagent ends, its session closes, and its folder is shelved
    ([LIBRARY.md](LIBRARY.md));
  - **reject(feedback):** the feedback is appended to PARENT_FEEDBACK.md and
    reaches the subagent in the same session (in a fresh one from HANDOFF.md if
    its session closed at the idle limit). If its CLI is held, or it needs a new
    session and every slot is taken, it waits; the rejection still stands;
  - **cancel:** the subagent, its whole subtree and all their jobs stop, and each
    of their folders is shelved.
- The Reviewer's subagents are its helpers, for independent checks.

## Messages

- `message(agent, text)` works between a parent and its direct subagents, in both directions.
- It is delivered during the recipient's turn, or wakes it if it waits idle; a paused recipient receives it
  when it continues, and one without a session at its next session.
- Messages are not stored in files for the agents: the recipient notes what matters. (The controller keeps
  them, for the web app, in `.research/activity/`, which agents cannot see.)
- The human can also write to any agent from the web app (`[human] ...`); its parent receives a copy
  (`[human → <id>] ...`).
- Refused when the agents aren't parent and subagent, the text is empty, the
  recipient has ended, or the recipient has submitted its result. In that last
  case, use accept, reject or cancel.

## When agents stop working

For waiting, idle and stalled agents, see [CONTROLLER.md](CONTROLLER.md). For handoffs, see [CONTEXT.md](CONTEXT.md).
