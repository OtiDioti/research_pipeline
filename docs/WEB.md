# The web app

`research-pipeline run PROJECT` shows the investigation in your browser: its phases in a sidebar, the selected phase's agent tree as a
graph (live for the phase that runs), what every agent says and does, its documents, and controls for single agents. It is agent_toolkit's web app
(`agent-toolkit[web]`), described for this program by `web.py`.

## Starting

| Option | Meaning (default) |
|---|---|
| (default) | serve the page on 127.0.0.1 and open it in your browser; its setup page comes first |
| `--no-web` | no page: the terminal alone, and the folder must be ready |
| `--start` | skip the setup page: start at once with the options given and stored |
| `--web-port PORT` | use this port (8780, or the next free one) |
| `--web-no-open` | print the page's address instead of opening the browser |

The address is always printed, so the page can be opened by hand (e.g. over an SSH
tunnel) when no browser can be opened. It carries a secret token; only pages opened
with it can see or act. The terminal prints the transcript next to the page
(`--tui` shows the terminal app instead); both show and control the same investigation, and any number of pages
may be open. After a phase ends the page stays open for talks: the
message box talks with its primary, its Reviewer takes messages too, and the top
bar's controls are *Prepare reopening* and Quit ([FINISHING.md](FINISHING.md)).
*Prepare reopening* opens the setup page again, to reopen the phase (below); *Back*
returns to the graph. The page stays readable until the program exits.

## Phases

The collapsible sidebar on the left lists the phases (its *Phases* section folds
too; both stay as you left them in this browser): each with its number, title and
state (running, paused, COMPLETE, STOPPED, not started, and the phase it builds on),
the running one marked *running*, the selected one highlighted, and **New phase**
at the bottom. One phase runs at a time.

- **Selecting a phase** shows its graph, activity and documents. The running phase
  is live. Another phase is shown as it was left: its primary and Reviewer take
  messages, as talks ([FINISHING.md](FINISHING.md), "Talks"), and the top bar offers
  *Prepare reopening* (it ended), *Resume phase N* (it is paused) or *Prepare
  phase N* (not started yet). Selecting changes what every open page shows.
- **New phase** adds the next phase (one not started at a time) and opens its
  preparation: *Material*, *Objectives* (its OBJECTIVES.md, and AGENTS.md in a second
  tab) with the new phase's assistant ([SETUP.md](SETUP.md)), then its title, the
  earlier phase it builds on, every launch option, and **Start phase N**.
- **Start phase N**, **Reopen** and **Resume phase N** wait until no other phase runs:
  pause the running phase first (select it, Pause). Then its controller hands over:
  a paused phase's sessions save their handoffs first; an ended phase's talks save
  their notes. The new phase's controller starts in the same program and page.
- Each phase's settings are its own (prefilled from the phase run last); a phase's
  title and the phase it builds on can be changed in its preparation.

## Reopening on the page

With a phase that ended (COMPLETE or STOP) selected, *Prepare reopening* shows the
preparation again ([FINISHING.md](FINISHING.md), "Reopening"), titled with the outcome:

1. **Material**, as before the first start: new material, placed and described, or
   removed (set aside, restorable).
2. **Instructions**: the phase's OBJECTIVES.md and AGENTS.md, one tab each, with
   the reopening assistant's conversation and questions beside them.
3. **Settings**: the files changed since the end, each with Revert (a file the end's
   commit has comes back from it; a new one is set aside), and *Discard all*; the
   checks; every launch option, as at a start; and **Reopen**. Reopen waits until the
   phase's objectives changed, the folder is ready, the Librarian has placed the
   phase's final work, the assistant is idle and no other phase runs; hovering over
   it says what it waits for.

The page can switch between this and the graph at any time (*Back*, *Prepare
reopening*, the sidebar): saved edits are files, kept; the talks go on until Reopen.
A change typed but not saved is lost when switching. Reopen ends the talks and
reopens the phase in the same program and page.

## The setup page

Before the first start, the page first shows the preparation steps of the first
phase, always, even for a folder that is ready already: *Material* and *Objectives*
(`phases/1/OBJECTIVES.md`), with the setup assistant ([SETUP.md](SETUP.md)); the launch options are the last step, where the
checks Start waits for are listed. Afterwards it shows the launch options alone.

Every launch option, prefilled from the command line and the stored options (the
last used): the primary, the Reviewer and the Librarian (CLI, model from the CLI's own list or
typed, effort as a slider over the levels the model accepts), the CLIs for
subagents, the models the agents' prompt recommends for subagents' coding and
analytical tasks (a warning, not a refusal, when one's CLI is not among the CLIs
for subagents: agents then choose another), the number of sessions at once, the idle limit, the handoff threshold, the usage limits,
and under *Advanced* the reference folders and durable state. Start checks them
like the command line does and shows what is wrong next to each setting.

While the investigation runs, the settings button changes the handoff threshold
(live sessions follow at their next context reading), the usage limits, the
number of sessions at once and the idle limit, at once; and the primary's, the Reviewer's or the Librarian's CLI, model
and effort, from that agent's next session, the recommended models, from each
agent's next session, and the CLIs for subagents, from the next spawn. The reference folders and durable state need a new `run`.

## The graph

- One node per agent that ever worked on the selected phase (and the Librarian, which
  serves every phase), its shape by role (primary,
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
  the primary's OBJECTIVES.md, STATUS.md and REPORT.md; the Reviewer's reviews; the Librarian's top
  pages), their jobs, and
  the websites and library pages they used (from their tool calls). The other agents
  fade. Esc or a click on empty space clears the selection.
- Search finds agents, files and websites and highlights the path to the primary;
  filters hide agents by status, CLI or role.

## The panel

For the selected agents (all agents when none is selected): **Activity**, their
messages coloured by sender (its parent orange, you teal, the controller green,
its subagents violet, its own neutral) and, with the *Tools* switch on, their
tool calls, in time order; its header names the agent with its status and
actions. Below it, **Task & notes**, its documents. Both float over the graph at
its right edge: each folds to a bar on its own, leaving the graph visible around
it, and each is resized by dragging its bottom edge (their left edge sets the
width). The page remembers the folds, the switch and the sizes. A file opens in the panel or, with *Open outside*,
in your desktop's application; a website in a new tab.

Messages and tool calls come from `.research/phases/<N>/activity/<agent>.jsonl` (the
Librarian's from `.research/activity/`), which the controller appends for every
agent (hidden from agents, like all of `.research/`).

## Controls

The top bar has the selected phase's state and controls (for the running phase:
Pause/Resume, *Resume held* when something waits for you; Shut down) and the usage
quota; the message box writes
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
