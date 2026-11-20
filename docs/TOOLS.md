# Agent tools

The controller's tools reach agents through MCP: `tools.py` defines them, and the
controller offers each session its role's tools through agent_toolkit's
`ToolBridge`. Each agent's CLI starts the toolkit's tool server
(`agent_toolkit.tool_server`, on the official MCP SDK) inside the confinement; the
SDK checks every call against the tool's schema, and the server forwards it to the
controller.

## Tools

| Tool | Who | Effect |
|---|---|---|
| `spawn(task, backend, model, effort, name)` | any | Start a subagent from a brief ([AGENT_ROLES.md](AGENT_ROLES.md)) |
| `agents()` | any | The caller's subagents: status, context fill, latest activity |
| `message(agent, text)` | any | Message one's parent or a direct subagent |
| `accept(agent)`, `reject(agent, feedback)`, `cancel(agent)` | parent | Decide on or stop a subagent |
| `run_job(command, timeout_seconds, cwd)` | any | Start a job ([JOBS.md](JOBS.md)) |
| `job_status(job)`, `job_cancel(job)` | owner | A job's status and output tail; stop it |
| `submit_result(result)` | subagent | Deliver RESULT.md to the parent; the session then waits for its decision |
| `complete(report)`, `stop(reason, final)` | primary | Propose finishing ([FINISHING.md](FINISHING.md)) |
| `verdict(review, agree)` | Reviewer | Deliver a review round |
| `write_page(path, text)` | Librarian | Write a Markdown page of `library/` (empty text removes it) ([LIBRARY.md](LIBRARY.md)) |
| `shelved(folder)` | Librarian | Report a shelving request done (the agent's folder, as the request names it) |

Every reply also carries the caller's pending notices.

## The channel

- Each controller run listens on its own Linux abstract Unix socket (`agent_toolkit.channel`). It needs no
  file, so it also works inside the confinement.
- One JSON request and one reply per connection, up to 4 MB each. The tool server waits up to 300 s for a reply.
- Every session's tool server carries a **token of its own**. A replaced or closed session's calls are refused.

## Refusals

| Reply | Cause |
|---|---|
| "Error: this session has ended …" | The call came from a replaced or closed session |
| "Error: your result is with …; end your turn and wait …" | A submitted subagent's call, until its parent decides |
| "… is not one of your tools" | A tool of another role |
| An input validation error | A required argument is missing or has the wrong type (checked by the MCP SDK) |
| "… the controller is unreachable …" | The controller isn't running (its socket is gone) |
| "Refused: the investigation is paused/…" | Nothing new starts while the investigation isn't running |
| "Refused: N/N agent sessions are already open …" | The cap `--max-agents` is reached (idle sessions count until the idle limit) |
| "Refused: … temporarily paused by the usage quota …" | That CLI is held ([QUOTA.md](QUOTA.md)) |
| "Refused: backend … is not allowed" / "a model and an effort are required" | `spawn` without an allowed backend, a model and an effort |
| "Refused: … has no "Prior work" section …", "… links in the "Prior work" section of … lead nowhere …" | `spawn` with a brief without that section (it may be empty), or with a link in it that leads nowhere from the subagent's TASK.md ([AGENT_ROLES.md](AGENT_ROLES.md)) |
| "Refused: the subagent: … does not accept effort …" | `spawn` with an effort the backend's CLI rejects ([AGENT_ROLES.md](AGENT_ROLES.md)) |
| "Refused: first settle your subagents … and jobs …" | Before `submit_result`, a proposal or a verdict, running work must end |
| "Refused: Fix these layout problems first …" | The layout check failed ([PROJECT_FOLDER.md](PROJECT_FOLDER.md)) |
| "Refused: your proposal … is with the Reviewer: … only talk" | `spawn` or `run_job` by the primary during a review |
| "Refused: you are paused: … only talk" | `spawn` or `run_job` by a paused agent (by the human or the quota), or while the investigation is paused |
| "Refused: your previous proposal … is still with the Reviewer" | `complete` or `stop` during a review |
| "Refused: … is not one of your subagents" | `accept`, `reject` or `cancel` aimed at another agent |
| "Refused: … is neither your parent nor one of your subagents" | `message` aimed at another agent |
| "Refused: … has submitted its result …" | `message` to a submitted subagent: accept, reject or cancel it |
| "Refused: … is not an existing file/folder in the project" | A path outside the project, inside `.research/`, or missing |
| "Refused: …: a page's path is relative to library/ …", "… must end in .md", "… library/CATALOG.md and library/catalog/ are written by the controller" | `write_page` outside `library/`, not Markdown, hidden, or on the catalogue |
| "Refused: <agent> is not shelved yet: …" | `shelved` while a file of the agent is reachable from no page, a link leads nowhere, or `library/` fails the layout check |
| "Refused: no shelving request for … is pending" | `shelved` for an agent without a pending request |
