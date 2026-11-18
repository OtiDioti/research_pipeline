# Controller

`controller.py`. A deterministic program that runs one investigation. It owns the
agent tree, starts and closes sessions, handles every CLI event and tool call, and
makes every operational decision. It never makes a scientific one.

## How it runs

- One asyncio loop. One lock serialises driver events, tool calls and background
  checks, so no two changes interleave halfway.
- State lives in `.research/state.json`, rewritten atomically after every change and
  forced to disk (`--no-durable-state` skips that, for slow network filesystems).
- The files the controller writes in the project (the starter files and
  `.gitignore`, indexes, TASK.md, PARENT_FEEDBACK.md, the outcome in STATUS.md, a
  job's `command.txt`) are replaced atomically, and a job's logs are created fresh;
  none is written through a symlink or outside the project (`agent_toolkit.records`),
  since agents and jobs can write the same folders.
- Background loops:

| Loop | Interval | Does |
|---|---|---|
| Watch | 2 s (`WATCH_INTERVAL`) | Notices jobs that ended, restarts agents whose retry is due, closes sessions past the idle limit ([CONTEXT.md](CONTEXT.md)) |
| Human files | 10 s (`HUMAN_INTERVAL`) | Tells the primary when `AGENTS.md`, `FEEDBACK.md` or `starting_evidence/` changed |
| Quota | 120 s (`QUOTA_INTERVAL`) | Reads the usage of every CLI in use ([QUOTA.md](QUOTA.md)) |

## Agent statuses

An agent keeps its session while it waits; idle is not a reset. Its context is
reset only at a context or forced handoff, at the idle limit, or when the
controller stops ([CONTEXT.md](CONTEXT.md)).

| Status | Session | Meaning |
|---|---|---|
| `running` | yes | Working, or idle in its session |
| `handing_off` | yes | Asked to update HANDOFF.md and end its turn |
| `paused` | kept, or none | Waits; see the pause reason. Paused by the human or the quota, it waits in its session |
| `submitted` | kept, or none | A subagent submitted its result; its parent decides. Its tools are refused meanwhile |
| `resting` | kept, or none | Nothing to do until its next input: the Reviewer between rounds, or an agent whose session closed at the idle limit. News wakes it |
| `accepted`, `cancelled`, `finished` | no | Ended (until the investigation is reopened) |

Pause reasons:
- `start`: the primary before its first session.
- `restart`: it was at work when the controller ended.
- `human`: the human paused the investigation.
- `held`: the human paused this agent alone (from the web app); only its own Resume continues it.
- `resume`: the human resumed it; it continues as soon as it can run.
- `quota`: its CLI is held.
- `slots`: the cap was reached.
- `failure`: its session failed.
- `retry`: a retry is due.
- `wake`: news arrived for a resting or submitted agent; it continues as soon as it can run.
- `reopen`: the investigation was reopened.

The cap `--max-agents` (6, at least 2) counts live sessions, idle ones included. A
slot frees only when a session closes: at the idle limit, on accept or cancel, or
at the end. When a slot frees, paused agents without a session start in order: the
primary, then the Reviewer, then subagents with the fewest sessions first.

## CLI events

| Event | Reaction |
|---|---|
| `text` | Shown; becomes the agent's latest activity |
| `tool` | Shown; clears the agent's idle nudge |
| `context` | Handoff logic ([CONTEXT.md](CONTEXT.md)) |
| `turn_ended` | Checked in order. During a handoff, the handoff is checked. A waiting agent (paused, submitted, resting, or the investigation paused) is left alone: its news waits. Queued notices are delivered. A Reviewer that answered the human between rounds rests again. Otherwise the idle check runs. |
| `turn_ended`, failed | Session closed; see "Failures" |
| `turn_ended` with messages still pending | A message (a notice, a handoff request) reached the CLI too late for that turn; the CLI runs it in a further turn, and the controller acts only on that turn's end |
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
  - for the **Reviewer**, the proposal is withdrawn, it rests, and the primary is
    told ([FINISHING.md](FINISHING.md)).

## Failures

| Condition | Action |
|---|---|
| A session cannot start, its CLI exits, or a turn fails | Paused (`failure`); restarts from HANDOFF.md after 30 s, 2 min and 10 min (`RETRY_DELAYS`); after that, waits for Ctrl+R |
| The CLI loaded the human's own setup ([DRIVERS.md](DRIVERS.md)) | Paused (`failure`) with no automatic retry; the message names what loaded; fix it, then Ctrl+R |
| The session of a waiting agent (paused, submitted, resting) ends | It keeps waiting; its next input starts a fresh session from HANDOFF.md |
| A failure while saving its note at the idle limit | It rests |
| A failure while handing off for a quota hold | Counts as paused for quota |

A successful turn resets the failure count. Agents fail independently: the others continue.

## Notices

- Delivered during the recipient's turn; an idle agent's next turn starts with them, and a resting one is woken.
- A paused or submitted agent, or one saving its note, keeps them until it continues; while the investigation is
  paused, only the human's messages are delivered.
- An agent without a session keeps them in the state; its next opening message includes them.
- Every tool reply also carries the caller's pending notices.
- Prefixes: `[controller]`, `[human]` (the human's messages), `[human → <id>]` (the copy a parent receives of a
  message to its subagent) and `[from <id>]` (messages between a parent and its subagents).
- Every message an agent receives, with its sender, and everything it says and does are appended to
  `.research/activity/<id>.jsonl` (for the web app).

## The human

| Event | Action |
|---|---|
| Chat message | Goes to the primary. During a review or a pause it answers in its session, talk-only (`spawn` and `run_job` refused) |
| Message to another agent (web app) | Delivered during its turn, or into its waiting session (talk-only if paused), or at its next session; its parent receives a copy |
| Pause, resume, force handoff or cancel of one agent (web app) | [WEB.md](WEB.md) |
| `AGENTS.md`, `FEEDBACK.md` or `starting_evidence/` changed | The primary is told within about 10 s; a new `AGENTS.md` reaches each agent at its next session |
| Agent-written files edited while running | Not detected; included in the next commit (edit them only while paused) |
| Pause, shutdown, forced exit, release | [OPERATIONS.md](OPERATIONS.md) |

## Each `run`

- Takes `.research/lock` (a `flock`, released when the controller ends, even by a crash); a second
  controller on the same project is refused.
- **First run:** prepares the layout (a new repository starts with the commit "controller: project
  prepared"), commits "controller: investigation started", and starts the primary.
- **After a pause or shutdown:** changes since the last commit are committed and
  announced to the primary and to the owners of changed agent folders, "by the
  human or by running jobs". (Resuming a pause does the same, into the agents' kept sessions.)
- **After a crash:** agents that were running restart from their handoffs; pending
  changes are committed as "work recovered after a restart"; running jobs are reattached.
- **After COMPLETE or STOP:** the investigation is reopened ([FINISHING.md](FINISHING.md)).
- **Every run** clears quota holds and reads the quota again.
