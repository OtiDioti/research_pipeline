# Controller

`controller.py`. A deterministic program that runs one investigation. It owns the
agent tree, starts and closes sessions, handles every CLI event and tool call, and
makes every operational decision. It never makes a scientific one.

## How it runs

- One asyncio loop. One lock serialises driver events, tool calls and background
  checks, so no two changes interleave halfway.
- State lives in `.research/state.json`, rewritten atomically after every change and
  forced to disk (`--no-durable-state` skips that, for slow network filesystems).
- Every file the controller writes in the project (indexes, TASK.md,
  PARENT_FEEDBACK.md, job files) is written atomically, never through a symlink and
  never outside the project (`agent_sessions.records`), since agents and jobs can
  write the same folders.
- Background loops:

| Loop | Interval | Does |
|---|---|---|
| Watch | 2 s (`WATCH_INTERVAL`) | Notices jobs that ended, restarts agents whose retry is due, closes sessions overdue to close |
| Human files | 10 s (`HUMAN_INTERVAL`) | Tells the primary when `AGENTS.md`, `FEEDBACK.md` or `starting_evidence/` changed |
| Quota | 120 s (`QUOTA_INTERVAL`) | Reads the usage of every CLI in use ([QUOTA.md](QUOTA.md)) |

## Agent statuses

| Status | Session | Uses a slot | Meaning |
|---|---|---|---|
| `running` | yes | yes | Working, or idle in its session |
| `handing_off` | yes | yes | Asked to update HANDOFF.md and end its turn |
| `paused` | no | no | Waits to start; see the pause reason |
| `submitted` | closing | no | A subagent submitted its result; its parent decides |
| `resting` | no | no | The Reviewer between rounds; the primary while its proposal is reviewed |
| `accepted`, `cancelled`, `finished` | no | no | Ended (until the investigation is reopened) |

Pause reasons:
- `start`: the primary before its first session.
- `restart`: it was running when the controller ended.
- `human`: a pause or shutdown.
- `quota`: its CLI is held.
- `slots`: the cap was reached.
- `failure`: its session failed.
- `retry`: a retry is due.
- `wake`: it is about to be woken (the primary or the Reviewer).
- `reopen`: the investigation was reopened.

The cap `--max-agents` counts agents that are `running` or `handing_off`. When a
slot frees, paused agents start in order: the primary, then the Reviewer, then
subagents with the fewest sessions first.

## CLI events

| Event | Reaction |
|---|---|
| `text` | Shown; becomes the agent's latest activity |
| `tool` | Shown; clears the agent's idle nudge |
| `context` | Handoff logic ([CONTEXT.md](CONTEXT.md)) |
| `turn_ended` | Checked in order. A closing session (after a result, verdict or proposal) is closed. During a handoff, the handoff is checked. Queued notices are delivered. Otherwise the idle check runs. |
| `turn_ended`, failed | Session closed; see "Failures" |
| `exited` (not asked to) | See "Failures" |

## Waiting, idle and stalled agents

- **Waiting:** the agent has a running or paused subagent, a running job, or (for
  the primary) a proposal under review. It is left alone; the next notice wakes it.
  Agents are told to keep working on whatever does not depend on their subagents
  and jobs, and to end their turn only when nothing useful remains.
- **Idle:** it ended its turn without waiting for anything. It is nudged once:
  "continue your work, or finish". The nudge names any submitted results that
  await its decision.
- **Stalled:** it ends its turn idle again without having used a tool. What happens:
  - a **subagent** keeps its session, and its parent gets a notice with its last
    message; the parent may `message` it or `cancel` it;
  - the **primary** keeps its session, and the human gets an ALERT with its last
    message; a chat reply continues the same session;
  - for the **Reviewer**, the proposal is withdrawn, its session closes, and the
    primary is woken ([FINISHING.md](FINISHING.md)).

## Failures

| Condition | Action |
|---|---|
| A session cannot start, its CLI exits, or a turn fails | Paused (`failure`); restarts from HANDOFF.md after 30 s, 2 min and 10 min (`RETRY_DELAYS`); after that, waits for Ctrl+R |
| The CLI loaded the human's own setup ([DRIVERS.md](DRIVERS.md)) | Paused (`failure`) with no automatic retry; the message names what loaded; fix it, then Ctrl+R |
| A failure while handing off for a pause or shutdown | Counts as paused by the human |
| A failure while handing off for a quota hold | Counts as paused for quota |

A successful turn resets the failure count. Agents fail independently: the others continue.

## Notices

- Delivered during the recipient's turn; an idle agent's next turn starts with them.
- An agent without a session keeps them in the state; its next opening message includes them.
- Every tool reply also carries the caller's pending notices.
- Prefixes: `[controller]`, `[human]` (chat messages), and `[from <id>]` (messages between a parent and its subagents).

## The human

| Event | Action |
|---|---|
| Chat message | Goes to the primary; during a review it wakes the primary in talk-only mode |
| `AGENTS.md`, `FEEDBACK.md` or `starting_evidence/` changed | The primary is told within about 10 s; a new `AGENTS.md` reaches each agent at its next session |
| Agent-written files edited while running | Not detected; included in the next commit (edit them only while paused) |
| Pause, shutdown, forced exit, release | [OPERATIONS.md](OPERATIONS.md) |

## Each `run`

- Takes `.research/lock`; a second controller on the same project is refused.
- **First run:** prepares the layout (a new repository starts with the commit "controller: project
  prepared"), commits "controller: investigation started", and starts the primary.
- **After a pause or shutdown:** changes since the last commit are committed and
  announced to the primary and to the owners of changed agent folders, "by the
  human or by running jobs".
- **After a crash:** agents that were running restart from their handoffs; pending
  changes are committed as "work recovered after a restart"; running jobs are reattached.
- **After COMPLETE or STOP:** the investigation is reopened ([FINISHING.md](FINISHING.md)).
- **Every run** clears quota holds and reads the quota again.
