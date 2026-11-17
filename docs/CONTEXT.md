# Context monitoring and handoffs

An agent's session is replaced by a fresh one before its context fills up. The
agent's identity, folder, subagents and jobs carry over; its HANDOFF.md bridges the
two sessions.

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
| The CLI compacts its context and the fill falls below the threshold | A context handoff is cancelled, and the cycle restarts at the threshold. The agent is not told. A handoff for a pause, shutdown or quota hold stands. |
| The turn ends with HANDOFF.md written since the request (any write counts, even of the same text) | Layout check (problems go to the next session as a notice, without blocking); commit; the session closes; a fresh one starts |
| The turn ends without a write | Asked again, up to 3 times; then the next session starts from the existing HANDOFF.md |

- These rules are the ones every agent controller shares (`agent_toolkit.handoff`,
  also used by coding_pipeline and project_manager); research keeps its own
  HANDOFF.md, which agents edit with their file tools, and has no limit on the
  number of handoffs.
- An agent is never killed for overshooting.
- The same handoff happens for a human pause, a shutdown and a quota hold; the
  agent then pauses instead of restarting.
- The next session gets TASK.md (the primary: the questions), HANDOFF.md and the queued notices.

## A good handoff

It is short:
- what was done, and where the artifacts are;
- essential assumptions;
- open issues;
- running jobs and subagents;
- the next concrete step.

The science lives in the agent's notes, not in HANDOFF.md.
