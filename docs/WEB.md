# The web app

`research-pipeline run PROJECT --web` also shows the investigation in your
browser: the agent tree as a live graph, what every agent says and does, its
documents, and controls for single agents. It is agent_toolkit's web app
(`agent-toolkit[web]`), described for this program by `web.py`.

## Starting

| Option | Meaning (default) |
|---|---|
| `--web` | serve the page on 127.0.0.1 and open it in your browser; its setup page comes first |
| `--start` | skip the setup page: start at once with the options given and stored |
| `--web-port PORT` | use this port (8780, or the next free one) |
| `--web-no-open` | print the page's address instead of opening the browser |

The address carries a secret token; only pages opened with it can see or act.
The terminal app runs as usual next to the page (`--no-tui` prints the transcript
instead); both show and control the same investigation, and any number of pages
may be open. The page stays readable after the investigation ends, until the
program exits.

## The setup page

Every launch option, prefilled from the command line and the stored options (the
last used): the primary and the Reviewer (CLI, model from the CLI's own list or
typed, effort as a slider over the levels the model accepts), the CLIs for
subagents, the number of sessions at once, the idle limit, the handoff threshold, the usage limits,
and under *Advanced* the reference folders and durable state. Start checks them
like the command line does and shows what is wrong next to each setting.

While the investigation runs, the settings button changes the handoff threshold
(live sessions follow at their next context reading), the usage limits, the
number of sessions at once and the idle limit, at once; and the primary's or the Reviewer's CLI, model
and effort, from that agent's next session, and the CLIs for subagents, from the
next spawn. The reference folders and durable state need a new `run`.

## The graph

- One node per agent that ever worked on the project, its shape by role (primary,
  subagent, Reviewer), its colour by status, a ring showing its context use (amber
  near the handoff threshold, red past it), its CLI as a badge. Ended agents are
  smaller and faded. Edges go from parent to subagent; a submitted, accepted or
  rejected result, and the Reviewer's last verdict, are marked on an edge to the
  receiver. Messages between agents travel along the edges as they happen.
- Statuses: *working* and *idle* (a running session, busy or waiting; a resting
  agent is idle too), *handing off*, *paused* (by you), *held* (by the usage quota),
  *waiting* (for a slot, a retry or a wake), *failed* (its session failed and waits
  for a retry), *submitted*, *finished* (accepted, or the finished primary) and
  *cancelled*. A waiting agent that kept its session shows "session kept": it
  occupies a slot until the idle limit.
- Hovering an agent shows its CLI, status, context use, current activity and
  sessions. Clicking selects it; Shift- or Ctrl-click and dragging a box select
  several; double-click selects its subtree. Selecting unfolds what the selected
  agents own: their documents (the files in their folder except FOLDER_CONTENT.md;
  the primary's STATUS.md and REPORT.md; the Reviewer's reviews), their jobs, and
  the websites and sources they used (from their tool calls). The other agents
  fade. Esc or a click on empty space clears the selection.
- Search finds agents, files and websites and highlights the path to the primary;
  filters hide agents by status, CLI or role.

## The panel

For the selected agents (all agents when none is selected): **Messages**,
coloured by sender (its parent orange, you teal, the controller green, its
subagents violet, its own neutral), and **Tool calls**, in two windows; and
**Task & notes**, its documents. A file opens in the panel or, with *Open outside*,
in your desktop's application; a website in a new tab.

Messages and tool calls come from `.research/activity/<agent>.jsonl`, which the
controller appends for every agent (hidden from agents, like all of `.research/`).

## Controls

The top bar has the investigation's controls (Pause/Resume, *Resume held* when
something waits for you, Shut down) and the usage quota; the message box writes
to the primary by default, or to the agent you choose.

Single agents, from their right-click menu or the panel's buttons:

| Action | Effect |
|---|---|
| Message | Delivered during the agent's turn, into its waiting session (talk-only while paused), or at its next session; its parent receives a copy |
| Pause | The agent finishes its current step, ends its turn and waits in its session (pause reason `held`), talk-only; its subagents and jobs keep working, and their messages and results wait for it; its parent is told. Pausing and resuming the whole investigation does not resume it |
| Resume | The agent continues in the same session (from its handoff if the session closed at the idle limit, or failed) as soon as it can run; its parent is told |
| Force handoff | The agent updates HANDOFF.md and continues in a fresh session (unlike a context handoff, not called off by the CLI's compaction) |
| Cancel | A subagent, its subagents and their jobs end, as with its parent's cancel tool; the parent is told |

Notifications: the page shows a toast for alerts and noteworthy controller events
(quota holds, failures, pauses, verdicts, the outcome); with the bell, your
browser shows alerts as system notifications too.
