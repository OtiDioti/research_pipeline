# Agent tools

The controller's tools reach agents through MCP (`mcp_server.py`). Each agent's CLI
starts its own tool server inside the confinement, offering only its role's
tools. The server forwards every call to the controller (`channel.py`).

## Tools

| Tool | Who | Effect |
|---|---|---|
| `spawn(task, backend, model, effort, name)` | any | Start a subagent from a brief ([AGENT_ROLES.md](AGENT_ROLES.md)) |
| `agents()` | any | The caller's subagents: status, context fill, latest activity |
| `message(agent, text)` | any | Message one's parent or a direct subagent |
| `accept(agent)`, `reject(agent, feedback)`, `cancel(agent)` | parent | Decide on or stop a subagent |
| `run_job(command, timeout_seconds, cwd)` | any | Start a job ([JOBS.md](JOBS.md)) |
| `job_status(job)`, `job_cancel(job)` | owner | A job's status and output tail; stop it |
| `submit_result(result)` | subagent | Deliver RESULT.md to the parent; the session then ends |
| `complete(report)`, `stop(reason, final)` | primary | Propose finishing ([FINISHING.md](FINISHING.md)) |
| `verdict(review, agree)` | Reviewer | Deliver a review round |

Every reply also carries the caller's pending notices.

## The channel

- Each controller run listens on its own Linux abstract Unix socket. It needs no
  file, so it also works inside the confinement.
- One JSON request and one reply per connection, up to 4 MB each. The tool server waits up to 300 s for a reply.
- Every request carries the agent's id and the **token of its current session**. A
  replaced or closed session's calls are refused.

## Refusals

| Reply | Cause |
|---|---|
| "Error: this session has ended …" | The call came from a replaced or closed session |
| "Error: your session is closing …" | The caller submitted a result, a verdict or a proposal; it should end its turn |
| "… is not available to the …" | A tool of another role |
| "Error: invalid arguments …" | A required argument is missing or wrong |
| "Error: the research controller is unreachable …" | The controller isn't running (its socket is gone) |
| "Refused: the investigation is paused/…" | Nothing new starts while the investigation isn't running |
| "Refused: N/N agents are already working …" | The cap `--max-agents` is reached |
| "Refused: … temporarily paused by the usage quota …" | That CLI is held ([QUOTA.md](QUOTA.md)) |
| "Refused: backend … is not allowed" / "a model and an effort are required" | `spawn` without an allowed backend, a model and an effort |
| "Refused: the subagent: … does not accept effort …" | `spawn` with an effort the backend's CLI rejects ([AGENT_ROLES.md](AGENT_ROLES.md)) |
| "Refused: first settle your subagents … and jobs …" | Before `submit_result`, a proposal or a verdict, running work must end |
| "Refused: Fix these layout problems first …" | The layout check failed ([PROJECT_FOLDER.md](PROJECT_FOLDER.md)) |
| "Refused: first update HANDOFF.md …" | A proposal needs a handoff written in the current session |
| "Refused: your proposal … is with the Reviewer: … only talk" | The primary was woken by the human during a review |
| "Refused: your previous proposal … is still with the Reviewer" | `complete` or `stop` during a review |
| "Refused: … is not one of your subagents" | `accept`, `reject` or `cancel` aimed at another agent |
| "Refused: … is neither your parent nor one of your subagents" | `message` aimed at another agent |
| "Refused: … has submitted its result …" | `message` to a submitted subagent: accept, reject or cancel it |
| "Refused: … is not an existing file/folder in the project" | A path outside the project, inside `.research/`, or missing |
