# Operations

Running an investigation, controlling it, and finding out what went wrong.

## Launch

`research-pipeline run` opens the web page on every project of this machine
([WEB.md](WEB.md)), where each one starts or resumes an investigation, or opens a
finished one for talks, from where *Prepare reopening* reopens it. `run PROJECT` also
adds that folder and shows it; with `--no-web` it runs that project's latest phase,
reopening it if the human's files changed since the end ([FINISHING.md](FINISHING.md)).
The options are listed in [README.md](../README.md); those for one project (models,
limits, `--setup`, `--start`, `--tui`, `--no-web`) need `PROJECT`. A second `run`
while the page's server runs opens that page and exits.
- On the page, a project not started yet opens on its setup page: before the first
  start it helps make the folder ready ([SETUP.md](SETUP.md)), with
  `--setup BACKEND:MODEL:EFFORT` for its assistant, then it offers every option.
  One project works at a time.
- With `--no-web` there is no page: on the first run `--primary`, `--reviewer`
  and `--librarian` are required as `BACKEND:MODEL:EFFORT`, and a folder that is
  not ready is refused. `--backends` defaults to the primary's and the Reviewer's
  CLIs. `--max-agents` (6) counts open sessions, idle ones included but not the
  Librarian's, and must be at least 2 (the primary and the Reviewer). `--idle-limit MINUTES` (58; 0: never) closes a session idle
  that long ([CONTEXT.md](CONTEXT.md)).
- Options given on a later run replace the stored ones.
- `research-pipeline status PROJECT` prints the state without starting anything:
  the investigation, whether a controller is running it, the proposal, quota
  holds, each agent with its pause reason, and running jobs.
- `research-pipeline stats PROJECT [--phase N|all]` prints a run's key numbers
  (library use, spawning, briefs, reviews, resources), read-only ([STATS.md](STATS.md)).
- The terminal prints the transcripts (each line under its project's name); Ctrl+C
  once shuts every project down cleanly, twice forces an exit. `run PROJECT --tui`
  shows that project in the terminal app instead.

## The terminal app (`--tui`)

- **Panels:** the transcript (one agent with F2, all with F3), the agents (status,
  CLI, context fill, latest activity), the status line (state, holds, open
  sessions, proposal round, quota readings, handoff threshold, idle limit), and the chat box.
- **Highlighted lines:** controller lines, notices, your messages, and ALERTs.
- The transcript keeps the most recent 400,000 characters.

| Control | Agents | Jobs | Next `run` |
|---|---|---|---|
| Ctrl+P (pause) | Agents at work finish their current step, end their turn and wait in their sessions; your messages are answered, talk-only (`spawn`, `run_job` refused), other news waits. Ctrl+P again resumes: the changes notice and "The investigation has resumed. Continue your work." go into the same sessions | Stopped | — |
| Ctrl+Q / F10 (shutdown), also while paused | Every session saves its handoff (without a turn if its CLI is held or its note is saved already), then the controller exits | Keep running | Agents restart from their handoffs; jobs are reattached; changes are announced |
| Ctrl+C (forced exit) | Sessions end at once (work since the last handoff may be lost) | Keep running | Agents restart from their handoffs; jobs are reattached |
| Ctrl+R (release) | Restarts agents held by a weekly or unreadable quota, or failed without automatic retry | Keep running | — |

When nothing is working and something waits for Ctrl+R, the Pause button reads
Resume and does the same.

## Editing files

| Files | When | What happens |
|---|---|---|
| The phase's `OBJECTIVES.md`, `AGENTS.md`, starting evidence | Any time | The primary is told which files changed; a new `AGENTS.md` reaches each agent at its next session; after a phase's end, only changed objectives reopen it |
| Agent-written files | Only while paused or shut down | The primary and the folder's owner are told on resume, "by the human or by running jobs" |

## Where to look

| What | Where |
|---|---|
| What happened | The transcript; `git log` in the project |
| What an agent's CLI said and did, line by line | `.research/logs/<agent>-<session>.jsonl` |
| The controller's view (agents, jobs, proposal, holds) | `.research/phases/<N>/state.json` and `.research/project.json`, or `research-pipeline status` |
| A job's command and output | `phases/<N>/agents/<owner>/jobs/<job-id>/` |
| An agent's own account | Its `HANDOFF.md`, and `RESULT.md` if it has submitted one |

## Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| "Another controller is already running this project." | `.research/lock` is held | Stop the other controller |
| "--primary must be BACKEND:MODEL:EFFORT …" | A missing CLI choice on the first run | Give all three parts |
| "--primary: … does not accept effort …" | An effort that CLI rejects | Choose one of those listed |
| "--context-threshold must be > 0 and <= 0.8 …" | A threshold that leaves no room to write the handoff | Choose one in that range (default 0.55) |
| "Projects cannot live under /tmp" | Each session has a private `/tmp` | Move the project |
| "bubblewrap (bwrap) is required" | bwrap is not installed | Install it |
| An agent paused (`failure`), restarting in 30 s / 2 min / 10 min | Its CLI crashed or a turn failed | See its session log; after the third retry, press Ctrl+R |
| ALERT: the primary has stopped | It ended its turn idle twice, often to ask you something | Answer in the chat box |
| A session "loaded the human's own setup" | A personal instruction file, skill or MCP server reached it | Remove it from that CLI's configuration, then Ctrl+R |
| A CLI is held as `unreadable` | Its usage can't be read (e.g. logged out) | Log the CLI in, then Ctrl+R |
| A CLI's agents paused for quota | That CLI is held | Wait for the reset (short), or Ctrl+R after it (weekly) |
| ALERT: the Librarian has stopped | It ended its turn idle twice with shelving requests pending | Message it from the web app, or look at its log; the work stays catalogued meanwhile |
| "This project predates the library" | It has `sources/` or `tools/` at its top level | Start a new project, with what it needs in `starting_evidence/` |
| A job can't write another agent's folder | That agent is shelved: its folder is frozen | Copy what you need into your own folder |
| Spawns refused at "N/N agent sessions are already open" | The cap is reached; idle sessions count until the idle limit closes them | Wait, or raise the cap (`--max-agents`, or live on the web page) |
| No handoff although the context looks full | The CLI hasn't reported both tokens and window, or the fill is below the threshold | See [CONTEXT.md](CONTEXT.md) |
| `sed -i` or `rm` fails on STATUS.md | A single-file bind ([CONFINEMENT.md](CONFINEMENT.md)) | Edit in place |
| A job wrote nothing into `starting_evidence/` | It is read-only for jobs | Write output elsewhere |
| A review hangs | The Reviewer is waiting for a slot or for quota, or it stalled (then the proposal is withdrawn) | Check the Reviewer's status and its log |
