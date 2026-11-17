# Operations

Running an investigation, controlling it, and finding out what went wrong.

## Launch

`research-pipeline run PROJECT` starts, resumes or reopens an investigation; the
options are listed in [README.md](../README.md).
- On the first run, `--primary` and `--reviewer` are required as
  `BACKEND:MODEL:EFFORT`. `--backends` defaults to their CLIs. `--max-agents` must
  be at least 2 (the primary and the Reviewer).
- Options given on a later run replace the stored ones.
- `research-pipeline status PROJECT` prints the state without starting anything:
  the investigation, whether a controller is running it, the proposal, quota
  holds, each agent with its pause reason, and running jobs.
- `--no-tui` prints the transcript instead of the terminal app. Ctrl+C once shuts
  down cleanly; twice forces an exit.

## The terminal app

- **Panels:** the transcript (one agent with F2, all with F3), the agents (status,
  CLI, context fill, latest activity), the status line (state, holds, working
  agents, proposal round, quota readings, handoff threshold), and the chat box.
- **Highlighted lines:** controller lines, notices, your messages, and ALERTs.
- The transcript keeps the most recent 400,000 characters.

| Control | Agents | Jobs | Next `run` |
|---|---|---|---|
| Ctrl+P (pause) | Hand off, then wait; press Ctrl+P again to resume | Stopped | — |
| Ctrl+Q / F10 (shutdown) | Hand off, then the controller exits | Keep running | Agents restart from their handoffs; jobs are reattached; changes are announced |
| Ctrl+C (forced exit) | Sessions end at once (work since the last handoff may be lost) | Keep running | Agents restart from their handoffs; jobs are reattached |
| Ctrl+R (release) | Restarts agents held by a weekly or unreadable quota, or failed without automatic retry | Keep running | — |

When nothing is working and something waits for Ctrl+R, the Pause button reads
Resume and does the same.

## Editing files

| Files | When | What happens |
|---|---|---|
| `RESEARCH_QUESTIONS.md`, `AGENTS.md`, `FEEDBACK.md`, starting evidence | Any time | The primary is told; a new `AGENTS.md` reaches each agent at its next session |
| Agent-written files | Only while paused or shut down | The primary and the folder's owner are told on resume, "by the human or by running jobs" |

## Where to look

| What | Where |
|---|---|
| What happened | The transcript; `git log` in the project |
| What an agent's CLI said and did, line by line | `.research/logs/<agent>-<session>.jsonl` |
| The controller's view (agents, jobs, proposal, holds) | `.research/state.json`, or `research-pipeline status` |
| A job's command and output | `agents/<owner>/jobs/<job-id>/` |
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
| Everyone paused for quota | The primary's CLI is held | Wait for the reset (short), or Ctrl+R after it (weekly) |
| Spawns refused at "N/N agents are already working" | The cap is reached | Wait, or rerun with a larger `--max-agents` |
| No handoff although the context looks full | The CLI hasn't reported both tokens and window, or the fill is below the threshold | See [CONTEXT.md](CONTEXT.md) |
| `sed -i` or `rm` fails on STATUS.md | A single-file bind ([CONFINEMENT.md](CONFINEMENT.md)) | Edit in place |
| A job wrote nothing into `starting_evidence/` | It is read-only for jobs | Write output elsewhere |
| A review hangs | The Reviewer is waiting for a slot or for quota, or it stalled (then the proposal is withdrawn) | Check the Reviewer's status and its log |
