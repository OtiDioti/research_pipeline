# Context monitoring and handoffs

An agent keeps its CLI session, and its context, while it works and while it waits
(for a review, a verdict, its parent's decision, a pause or a quota hold). Its
context is reset only:
- at the context threshold, or when the human forces a handoff;
- at the idle limit;
- when the controller stops (shutdown, crash, restart).

The agent's identity, folder, subagents and jobs carry over; its HANDOFF.md bridges
the two sessions.

## Measurement

Context use comes only from the CLI's own reports. It is never estimated, carried
over from an earlier session, or asked of the agent.

| CLI | Tokens | Window |
|---|---|---|
| Codex | `thread/tokenUsage/updated`, after every model call (`last.totalTokens`) | The same notification (`modelContextWindow`) |
| Claude Code | The usage of every top-level model call (input, cache creation, cache read and output tokens) | `get_context_usage` at session start (`maxTokens`), and each turn's result (`contextWindow`) |

- Fill = tokens / window. It updates after every model call: context does not
  change between calls.
- Until both are reported, the fill is unknown: the terminal app shows `–`, and
  nothing is triggered. Every new session starts unknown.
- If a session's fill is still unknown after its first turn, the human gets an
  ALERT, once per session: that session cannot be handed off. It continues.

## Handoff

| Condition | Action |
|---|---|
| Fill reaches the threshold (0.55, `--context-threshold`, above 0 and at most 0.8) | A handoff request during its turn: finish the current step, update HANDOFF.md, end the turn |
| Fill rises another 25 points (80%, 105%, …) | A reminder |
| The CLI compacts its context and the fill falls below the threshold | A context handoff is cancelled, and the cycle restarts at the threshold. The agent is not told. A handoff for any other reason stands. |
| The turn ends with HANDOFF.md written since the request (any write counts, even of the same text) | Layout check (problems go to the next session as a notice, without blocking); commit (except during a shutdown); then as the reason says (below) |
| The turn ends without a write | Asked again, up to 3 times; then the next session starts from the existing HANDOFF.md |

- These rules are the ones every agent controller shares (`agent_toolkit.handoff`,
  also used by coding_pipeline and project_manager); research keeps its own
  HANDOFF.md, which agents edit with their file tools, and has no limit on the
  number of handoffs.
- An agent is never killed for overshooting.
- The next session gets TASK.md (the primary: the objectives), HANDOFF.md and the queued notices.

What follows the note depends on the reason. A request for a later reason in this
table replaces a pending one (`HANDOFF_ORDER`):

| Reason | After the note |
|---|---|
| `idle` | The session closes; the agent's next input starts a fresh one ([Idle limit](#idle-limit)) |
| `context` | A fresh session continues |
| `refresh` | The human forced it from the web app: a fresh session continues; compaction never calls it off |
| `quota` | It waits in its session, paused ([QUOTA.md](QUOTA.md)); at the threshold, a fresh session continues after the hold |
| `shutdown` | The session ends with the controller; the next `run` starts a fresh one |

A human pause is not a handoff: agents finish their current step, end their turn
and wait in their sessions ([OPERATIONS.md](OPERATIONS.md)).

## Idle limit

A session idle for `--idle-limit` minutes (58, `agent_toolkit.handoff.IDLE_LIMIT`,
just inside the prompt cache's one-hour lifetime; 0 disables it; editable live on
the web page) is asked for one turn to update HANDOFF.md, then closes. It closes
without that turn while its CLI is held by the quota, or when its note was already
saved for a request since settled (e.g. at a quota hold). The clock restarts with
every turn.

The agent's next input (a notice, a message, a verdict, its parent's decision)
starts a fresh session from HANDOFF.md. An agent without a session and with nothing
to do is `resting`, and news wakes it. Idle sessions count against `--max-agents`
until they close.

## A good handoff

It is short:
- what was done, and where the artifacts are;
- essential assumptions;
- open issues;
- running jobs and subagents;
- the next concrete step.

The science lives in the agent's notes, not in HANDOFF.md.
