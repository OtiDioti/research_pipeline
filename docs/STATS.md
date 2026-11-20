# Statistics

`stats/` (`sources.py`, `calls.py`, `analysis.py`, `figures.py`, `tabs.py`, `view.py`,
`summary.py`). How an investigation actually ran: whether agents use the library,
whether work is split into parallel subagents or passed down chains, whether children
get what they need from their briefs, and how much parents re-read and re-run their
children's work. Deterministic and read-only: no model is asked anything, nothing is
written, no lock is taken, so a running project can be read, and so can any other.

## Where to see them

- **The web page:** the top bar's *Stats* button replaces the graph with the Stats
  view; it then reads *Graph*, to go back. It shows the phase selected in the sidebar,
  or another phase or all phases (the choice above the tabs), and is recomputed every
  5 seconds while shown (only what changed is read). *Compare* adds other projects:
  those next to this one are listed, any folder can be typed in; their numbers and
  lines appear beside this project's (dashed lines, on the same time axis from each
  one's start), with a Comparison tab of key numbers. Clicking an agent in a table, a
  timeline lane, a matrix row or a bar opens its card.
- **The terminal:** `research-pipeline stats PROJECT [--phase N|all]` prints the key
  numbers (the overview, then each tab's numbers; default: the latest phase).

## What is read

- each phase's `state.json` (agents, parents, statuses, rejections, sessions, jobs,
  Reviewer rounds) and the project's `project.json`;
- the activity logs, `.research/phases/<N>/activity/<agent>.jsonl` and the
  Librarian's `.research/activity/librarian.jsonl`: every tool call (with its whole
  input, since agent_toolkit 0.15.0), message and context reading;
- each subagent's `TASK.md`.

A project made before phases (`.research/state.json`, `agents/` at the top) reads as
phase 1.

## From tool calls to file accesses

Each tool call becomes the files it **read**, **ran**, **wrote**, **listed** or
**searched** (`calls.py`), by fixed rules:

- shell commands (Codex's, Claude Code's Bash, and `run_job` commands) are split at
  `&&`, `||`, `;`, `|` and new lines, heredoc bodies dropped; `cd` moves the working
  folder for what follows; each simple command is classified by its verb: readers
  (`cat`, `sed`, `head`, `rg`, `pdftotext`, `pdflatex`, …: their file arguments, a
  pattern or program argument aside), listers (`ls`, `find`, …), interpreters
  (`python x.py`, `julia`, `bash x.sh`, `pytest`, `uv run …`: what they run),
  writers (redirections, `tee`, `cp`/`mv` targets, `mkdir`, `rm`, `sed -i`), and
  verbs with no file effect (`echo`, `sleep`, `curl`, …);
- Claude Code's `Read`, `Write`, `Edit`, `Grep`, `Glob`; Codex's file edits;
- the research tools' arguments: `spawn` reads its brief; `accept`, `reject`, `cancel`
  and `message` name an agent; `submit_result` is a submission.

A command whose verb no rule knows is counted, and its share shown under the title.
Runs recorded before the activity log kept whole calls have only a one-line summary
(cut at 200–300 characters): it is parsed as far as it goes, and the share of calls
recorded only in part is shown, as the numbers they feed are then too low.

Each path is resolved from the agent's folder (or the command's working folder) and
attributed by its shape: `phases/<N>/agents/<id>/` (the agent itself, its parent, one
of its children, or another agent), `library/LIBRARY.md`, the catalogue
(`CATALOG.md`, `catalog/`), the Librarian's other pages, `starting_evidence/`, a
phase's own files, or other. A path that does not exist (resolved from the wrong
folder, as in runs made from the project's root or before the phases' layout) is
attributed by its last recognisable part.

## The view

- **Overview:** subagents and the deepest level, most agents at work at once, library
  reads, brief links opened, parent's files read without a link, results rejected,
  reads of work under review, tool calls and jobs.
- **Library:** reads of the entry page, the catalogue and the Librarian's pages, per
  agent and over time; agents that never read it; agents that read it before their
  first spawn; briefs with a "Prior work" section; reads of other agents' work (this
  phase, earlier phases); the Librarian's time from a shelving request to `shelved`.
- **Spawning:** the agents over time (at work, idle after 10 minutes without
  activity, their result with their parent), agents at work, subagents started, who
  reads or runs whose files (a matrix, own files aside), and per agent: level,
  children, most children at once, children spawned together (within 10 minutes),
  single-child chains, **brief links opened** (each link of TASK.md into the project,
  and whether the child ever read or ran it), **its parent's files it read without a
  link** (information the parent had and did not hand over), messages to its parent.
- **Checking:** each result from its submission to its parent's decision (accept,
  reject, cancel, or pending), what the parent read and ran of the child's work
  meanwhile (its RESULT.md, TASK.md and the protocol's files aside), the time to
  decide, rejections, Reviewer rounds.
- **Resources:** tool calls by kind and over time, jobs (running over time, failed,
  hours), handoffs, the most context each agent used, by model.
- **Agent cards:** the same, for one agent, with its brief's links one by one and
  the parent's files it read without a link.

The statistics give numbers, not verdicts: nothing is flagged as good or bad.
