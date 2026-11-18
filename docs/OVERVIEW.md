# Overview

How the parts fit together, and where to look when one misbehaves. The
specification is [PROJECT.md](../PROJECT.md); usage is in [README.md](../README.md).

## Components

| Component | Code (`src/research_pipeline/`) | Role | Details |
|---|---|---|---|
| Controller | `controller.py` | Runs one investigation and makes every operational decision | [CONTROLLER.md](CONTROLLER.md) |
| Agents | `prompts.py`, `prompts/` | Primary, subagents and Reviewer: their tasks, tools and lifecycle | [AGENT_ROLES.md](AGENT_ROLES.md) |
| Context handoffs | `controller.py`, `agent_toolkit` (`handoff.py`), drivers | Fresh sessions before the context fills up | [CONTEXT.md](CONTEXT.md) |
| Review and finishing | `controller.py` | COMPLETE, STOP, the Reviewer exchange, reopening | [FINISHING.md](FINISHING.md) |
| Jobs | `jobs.py` | Long computations outside the agents' sessions | [JOBS.md](JOBS.md) |
| Quota | `controller.py`, `agent_toolkit` | Pausing a CLI's agents before its usage runs out | [QUOTA.md](QUOTA.md) |
| Confinement | `agent_toolkit` (`confine.py`) | The bwrap boundary of every session and job | [CONFINEMENT.md](CONFINEMENT.md) |
| CLI drivers | `agent_toolkit` (shared package) | One persistent session per agent; everything CLI-specific | [DRIVERS.md](DRIVERS.md) |
| Agent tools | `tools.py` (served by agent_toolkit's tool bridge) | The MCP tools agents call, and how calls reach the controller | [TOOLS.md](TOOLS.md) |
| Project folder | `project.py`, `state.py` | Layout, layout check, git commits, the human's files | [PROJECT_FOLDER.md](PROJECT_FOLDER.md) |
| Operating it | `cli.py`, `view.py` (on `agent_toolkit`'s terminal app) | Launch, terminal app, pause, shutdown, logs, troubleshooting | [OPERATIONS.md](OPERATIONS.md) |
| The web app | `web.py` (on `agent_toolkit`'s web app) | Setup page, the agent graph, activity, single-agent controls, live settings | [WEB.md](WEB.md) |

## One investigation

1. `research-pipeline run` prepares the project folder and starts the primary's session.
2. The primary plans, writes notes and spawns subagents. Long computations run as jobs.
3. Each agent keeps its session while it waits, and hands off to a fresh session at 55% context; a session
   idle for 58 minutes closes. A CLI whose quota runs low pauses its agents.
4. Subagents submit `RESULT.md`; their parent accepts it, or rejects it with feedback.
5. The primary proposes COMPLETE or STOP and waits in its session. The Reviewer examines the work and gives a verdict.
6. COMPLETE needs the Reviewer's agreement. STOP is the primary's decision after the Reviewer's challenge.
   The controller then stops everything and commits.

Every significant event is committed to the project's git repository.

## Where to look

| Symptom | First look at |
|---|---|
| An agent is idle and nothing happens | [CONTROLLER.md](CONTROLLER.md), "Waiting, idle and stalled agents" |
| An ALERT in the terminal app | [CONTROLLER.md](CONTROLLER.md) (stalled primary), [DRIVERS.md](DRIVERS.md) (personal setup loaded), [CONTEXT.md](CONTEXT.md) (context use unknown) |
| An agent paused with reason `failure` | [CONTROLLER.md](CONTROLLER.md), "Failures"; its session log ([OPERATIONS.md](OPERATIONS.md)) |
| An agent paused with reason `quota` or `slots` | [QUOTA.md](QUOTA.md); `--max-agents` in [OPERATIONS.md](OPERATIONS.md) |
| Handoffs too early, too late, or not at all | [CONTEXT.md](CONTEXT.md) |
| A tool call refused | [TOOLS.md](TOOLS.md), "Refusals" |
| A write fails inside an agent session or job | [CONFINEMENT.md](CONFINEMENT.md) |
| A job's status is `lost`, `timeout` or `cancelled` | [JOBS.md](JOBS.md) |
| A RESULT or proposal refused for layout problems | [PROJECT_FOLDER.md](PROJECT_FOLDER.md), "Layout check" |
| The review hangs, or the primary seems missing | [FINISHING.md](FINISHING.md) |
| The controller won't start | [OPERATIONS.md](OPERATIONS.md), "Troubleshooting" |
