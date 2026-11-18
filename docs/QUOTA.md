# Usage quota

The controller pauses a CLI's agents before its usage windows run out, and resumes
them afterwards. Each driver reads its own CLI's windows without a model call
([DRIVERS.md](DRIVERS.md)); the usage guard all agent controllers share
(`agent_toolkit.quota.Guard`) turns the readings into holds, and the controller
decides what a hold pauses.

## Reading

- Every 120 s, and at every start, resume and release, each CLI in use is read:
  those of the primary, the Reviewer, the Librarian, `--backends`, and of every agent not yet ended.
- A window is **short** (e.g. 5 hours) or **weekly** (7 days or longer).

## Holds

| Reading | Hold | Ends |
|---|---|---|
| A short window at `--short-limit` (15%) left or less | `short` | Automatically, at the first reading above the limit taken at or after the reported reset (any such reading, if the CLI reported no reset) |
| A weekly window at `--weekly-limit` (15%) left or less | `weekly` | Only when the human resumes: Ctrl+R, a resume after a pause, or the next `run` |
| Unreadable twice in a row (one failure is taken for a glitch) | `unreadable` | As for weekly |

A limit of 0 disables that check. A CLI without a usage probe is never held. Holds
are kept in `.research/state.json` (kind, reported reset or none, detail), and
`research-pipeline status` lists them.

## While a CLI is held

- Each of its agents with a session updates HANDOFF.md (a request during its turn;
  an idle one gets one short turn for it), then waits in its session, paused
  (`quota`). Each subagent's parent is told that the pause is temporary and not a
  scientific blocker.
- Agents on other CLIs keep working, whichever CLI the primary uses.
- New spawns on that CLI are refused with the reason. A rejected subagent on it
  waits, and its rejection stands.
- Jobs keep running.
- If the hold ends within the idle limit (58 minutes, [CONTEXT.md](CONTEXT.md)),
  each agent continues in the same session, told "The usage quota allows work
  again. Continue your work." Otherwise its session closed at the idle limit,
  without another turn (its note is saved), and it starts a fresh session from
  HANDOFF.md once a slot is free. An agent whose context was at the threshold
  continues in a fresh session too. Parents are told that their subagent resumed.
- The terminal app shows the hold in its status line, e.g. `RUNNING (HELD: CLAUDE SHORT)`.

## If the limit is hit anyway

When the remaining 15% runs out between two readings, the CLI fails the turn:

| When | Result |
|---|---|
| During the quota handoff | Paused for quota. HANDOFF.md may not have been updated, so the next session starts from the previous one. |
| Before the hold was noticed | An ordinary failure, with a retry after 30 s. Once the hold is detected (within 2 minutes), the retry turns into a quota pause. |
