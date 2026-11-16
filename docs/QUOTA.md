# Usage quota

The controller pauses a CLI's agents before its usage windows run out, and resumes
them afterwards. Each driver reads its own CLI's windows without a model call
([DRIVERS.md](DRIVERS.md)); `quota.py` holds the shared rules.

## Reading

- Every 120 s, and at every start, resume and release, each CLI in use is read:
  those of the primary, the Reviewer, `--backends`, and of every agent not yet ended.
- A window is **short** (e.g. 5 hours) or **weekly** (7 days or longer).

## Holds

| Reading | Hold | Ends |
|---|---|---|
| A short window at `--short-limit` (15%) left or less | `short` | Automatically, at the first reading above the limit (after the reset) |
| A weekly window at `--weekly-limit` (15%) left or less | `weekly` | Only when the human resumes: Ctrl+R, a resume after a pause, or the next `run` |
| Unreadable twice in a row | `unreadable` | As for weekly |

A limit of 0 disables that check. A CLI without a usage probe is never held.

## While a CLI is held

- Its working agents get a handoff request, end their turn, and pause (`quota`).
  Each subagent's parent is told that the pause is temporary and not a scientific blocker.
- If it is the primary's CLI, every agent pauses, whatever its CLI.
- New spawns on that CLI are refused with the reason. A rejected subagent on it
  waits, and its rejection stands.
- Jobs keep running.
- When the hold ends, paused agents restart from their handoffs (if slots are
  free), and parents are told that their subagent resumed.
- The terminal app shows the hold in its status line, e.g. `RUNNING (HELD: CLAUDE SHORT)`.

## If the limit is hit anyway

When the remaining 15% runs out between two readings, the CLI fails the turn:

| When | Result |
|---|---|
| During the quota handoff | Paused for quota. HANDOFF.md may not have been updated, so the next session starts from the previous one. |
| Before the hold was noticed | An ordinary failure, with a retry after 30 s. Once the hold is detected (within 2 minutes), the retry turns into a quota pause. |
