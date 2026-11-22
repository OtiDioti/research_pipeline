# The web app

`research-pipeline run` shows every project of this machine in your browser: the projects in a sidebar, and for the
selected one its phases under it, the selected phase's agent tree as a graph (live for the phase that runs), what every
agent says and does, its documents, and controls for single agents. It is agent_toolkit's web app
(`agent-toolkit[web]`, its workbench), described for this program by `workbench.py` and `web.py`.

## Starting

| Option | Meaning (default) |
|---|---|
| (default) | serve the page on 127.0.0.1 and open it in your browser, on the empty workbench |
| `PROJECT` | also add this folder to the list and show it at once (a new folder opens on its setup page) |
| `--start` | with `PROJECT`: start it at once with the options given and stored (a started one resumes) |
| `--no-web` | with `PROJECT`: no page, the terminal alone, and the folder must be ready |
| `--web-port PORT` | use this port (8780, or the next free one) |
| `--web-no-open` | print the page's address instead of opening the browser |

The address is always printed, so the page can be opened by hand (e.g. over an SSH
tunnel) when no browser can be opened. It carries a secret token; only pages opened
with it can see or act. A second `run` while the page's server runs opens that page
(with `PROJECT`, adding it to the list and showing it) and exits; the options for one
project are refused then, since they cannot reach the running server. The terminal
prints every project's transcript, each line under its project's name (`run PROJECT
--tui` shows that project in the terminal app instead, the others quietly; closing it
ends the program). Ctrl+C shuts every project down cleanly (twice forces). Any number
of pages may be open: they all show the same project and act on it.

## Projects

The collapsible sidebar on the left lists the projects of this machine, most recently
created, added or started first, each with a status dot and its latest phase's state.
The list lives in `~/.config/research_pipeline/projects.json` (`$XDG_CONFIG_HOME`);
a project's display name lives in the project, in `.research/name`, so it moves with
the folder, whose own name never changes.

- **The empty workbench.** The page opens with no project selected and the sidebar
  open; a line in the middle points to the sidebar. Everything about a project
  (Settings, Stats, the windows) is greyed until one is picked. Once picked, you
  switch between projects; there is no closing back to the empty workbench. The
  sidebar starts open when a page loads with no project selected and collapsed when
  one is (e.g. after `run PROJECT`, or a reload); picking a project leaves it as it is.
- **Selecting a project** unfolds its phases under it (only the selected project is
  unfolded) and shows its running phase, else its latest. A project not started yet
  opens on its setup page (below). A project whose phase ended opens for talks at once
  (no work resumes; the Librarian finishes placing what was left). A project that does
  not run (paused, shut down, interrupted) is shown as it was left, read-only, with
  *Resume phase N* in the top bar. Both use the CLIs the phase last ran with: while
  its primary's, Reviewer's or Librarian's CLI is not installed or not logged in, the
  ended project is not opened (*Open for talks* waits) and *Resume phase N* waits,
  each with the reason on hover. The page checks again every 30 seconds while it shows
  the project, and once more at the press, so logging in elsewhere frees them. A project another research_pipeline process runs
  is read-only, and a project whose folder is gone is greyed and cannot be selected.
  The page's address names the project and phase (`#/projects/<id>/phases/<n>`), so a
  reload, Back and Forward, and bookmarks work.
- **One project works at a time.** While one runs (or is pausing), the others can be
  browsed, set up and talked with, but their Start, Resume and Reopen wait (hovering
  says which project runs): pause it first. A paused or ended project does not block.
- **+ New project** opens a folder browser (folders of this machine, served by the
  program: go up or in, type a path, create a folder), starting where the last
  project was created or added; then a name field in the list. Enter creates the
  folder, named after the project in a simple form (`Protein Folding 2` →
  `protein-folding-2/`; an existing one is refused), and opens its setup page.
  **+ Open folder** puts an existing folder in the list (a folder that is not a
  project yet opens on its setup page).
- **Renaming.** Hovering a project or a phase shows a pencil: the name becomes a
  field, Enter or clicking away saves, Esc cancels. A phase's title can change at
  any time, even while it runs (`phases/FOLDER_CONTENT.md` follows; agents see it the
  next time they are told of the phases). Names need not be unique.
- **Removing** a project from the list (✕ on hover, after a confirmation) leaves its
  folder as it is; *+ Open folder* brings it back. The project that runs cannot be
  removed.

After a phase ends its project stays open for talks: the chat window talks with its
primary and its Reviewer (below), and the top bar's controls are *Prepare reopening*
and Close ([FINISHING.md](FINISHING.md)). *Prepare reopening* opens the setup page
again, to reopen the phase (below); *Back* returns to the graph. *Close* and *Shut
down* end the project's controller (its talks save their notes, its agents their
handoffs); the project then stays shown as it was left, and the program goes on.

## Phases

Under the selected project the sidebar lists its phases: each with its number, title and
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

A CLI that is not installed or not logged in (asked of the CLI itself, `claude auth
status` and `codex login status`, without any model call) is greyed in every CLI
choice, with the reason on hover (e.g. "codex is not logged in: run `codex login`").
The page asks when it opens and again with *Check again* (after logging in in a
terminal). A primary, Reviewer or Librarian on such a CLI keeps Start waiting; a
recommended model or a CLI for subagents on one only warns (agents choose another).
The same holds for the live settings and the setup assistant's CLI (a warning only).

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
  sessions, and its action ring: round buttons on its left (on its right near the
  page's right edge) for chat, pause or resume, hand off, cancel and files (below).
  Clicking selects it, which highlights it and shows it in the panel; Shift- or
  Ctrl-click and dragging a box select several; double-click selects its subtree.
  Esc clears the selection.
- The ring's *files* button unfolds what the agent owns: its documents (the files
  in its folder except FOLDER_CONTENT.md; the primary's OBJECTIVES.md, STATUS.md
  and REPORT.md; the Reviewer's reviews; the Librarian's top pages), its jobs, and
  the websites and library pages it used (from its tool calls). Several agents'
  can be open at once; a click on empty space folds them all.
- Search finds agents, files and websites and highlights the path to the primary;
  filters hide agents by status, CLI or role.

## The panel

For the selected agents (all agents when none is selected): **Activity**, their
messages coloured by sender (its parent orange, you teal, the controller green,
its subagents violet, its own neutral) and, with the *Tools* switch on, their
tool calls, in time order; its header names the agent with its status. Below it, **Task & notes**, its documents. Both float over the graph at
its right edge. Each folds on its own to a bar at the bottom, leaving the graph
visible above; open windows fill the height down to the bars, two of them split
it at a border you drag, and their left edge sets the width. The page remembers
the folds, the switch, the split and the width. A file opens in the panel or, with *Open outside*,
in your desktop's application; a website in a new tab.

Messages and tool calls come from `.research/phases/<N>/activity/<agent>.jsonl` (the
Librarian's from `.research/activity/`), which the controller appends for every
agent (hidden from agents, like all of `.research/`).

## Controls

The top bar has the selected phase's state (e.g. `phase 2: complete`; while it runs,
also its open sessions and any proposal under review, and nothing more once it ended:
the outcome line is in its STATUS.md) and controls (for the running phase:
Pause/Resume, *Resume held* when something waits for you; Shut down), the usage
quota, and *Stats*, which replaces the graph with the run's statistics (then
*Graph* goes back; see [STATS.md](STATS.md)).

Single agents, from their action ring (a button that does not apply now is greyed,
its tooltip saying why):

| Action | Effect |
|---|---|
| Chat | Opens the chat window over the page: your messages and the agent's own text, from its activity log (so earlier talks are there whenever it opens), with Markdown and LaTeX. A message is delivered during the agent's turn, into its waiting session (talk-only while paused), or at its next session; its parent receives a copy |
| Pause | The agent finishes its current step, ends its turn and waits in its session (pause reason `held`), talk-only; its subagents and jobs keep working, and their messages and results wait for it; its parent is told. Pausing and resuming the whole investigation does not resume it |
| Resume | The agent continues in the same session (from its handoff if the session closed at the idle limit, or failed) as soon as it can run; its parent is told |
| Hand off | The agent updates HANDOFF.md and continues in a fresh session (unlike a context handoff, not called off by the CLI's compaction) |
| Cancel | A subagent, its subagents and their jobs end, as with its parent's cancel tool; the parent is told |

Notifications: the page shows a toast for alerts and noteworthy controller events
(quota holds, failures, pauses, verdicts, the outcome); with the bell, your
browser shows alerts as system notifications too.
