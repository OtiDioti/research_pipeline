# CLI drivers

One persistent session per running agent, from the private package
`agent_toolkit`, shared with coding_pipeline and project_manager. It is the only
code that knows the CLIs. research_pipeline only describes each session in
CLI-neutral terms (a `Launch`) and reacts to its events.

## What research_pipeline asks for

Every agent session gets:
- **Session instructions:** the role prompt and the human's AGENTS.md.
- **Model and effort:** the agent's own, always explicit.
- **All native capabilities:** shell commands, files and the web.
- **One MCP server**, `research`, the controller's tools ([TOOLS.md](TOOLS.md)).
- **Confinement:** its role's write scope, with `.research/` hidden ([CONFINEMENT.md](CONFINEMENT.md)).
- **A log** of every JSON line, in `.research/logs/<agent>-<session>.jsonl`. Prefixes: `>` sent, `<` received,
  `E` error output, `!` a message it couldn't handle.

The agent's own calls to the `research` tools are shown when the controller handles them, not twice.

## The shared base

- Starts the CLI inside its confinement and speaks JSON lines on its stdin and stdout.
- Matches replies to requests (timeout: 120 s); a request still waiting when the CLI ends fails at once.
- **Setup check:** refuses a session whose CLI reports having loaded any instruction
  file, skill, or MCP server it wasn't given.
- Turns everything into five events for the controller: `text`, `tool`, `context`, `turn_ended`, `exited`.
- Closing: the CLI gets SIGTERM, then SIGKILL after 10 s; its confinement ends with it.
- An unexpected exit reports the last 20 lines of the CLI's error output.

## Codex

- **Process:** `codex app-server`, speaking JSON-RPC.
- **Discovery off:**
  - project AGENTS.md files (`project_doc_max_bytes=0`);
  - native subagents, apps, plugins, skills, hooks and similar ambient features;
  - the personal `config.toml`, `AGENTS.md`, `AGENTS.override.md` and command `rules/`, which are masked. The credential store chosen in `config.toml` is kept, so logins still work.
- **Start:**
  1. `initialize`;
  2. `thread/start`: ephemeral, `danger-full-access` inside our confinement, no
     approvals, the session instructions as developer instructions;
  3. the setup check, on `instructionSources` and `mcpServerStatus/list`;
  4. `turn/start` with the opening message.
- **Messages:** `turn/steer` during a turn, otherwise a new `turn/start`.
- **Context:** `thread/tokenUsage/updated`, after every model call.
- **Requests from Codex** (approvals) are refused.
- **Quota:** `account/rateLimits/read` on a short-lived app-server.

## Claude Code

- **Process:** `claude -p` with stream-json in and out, no session persistence,
  and permissions bypassed inside our confinement.
- **Discovery off:**
  - no setting sources, hooks off, sandbox off, no slash commands;
  - only the given MCP servers;
  - built-in tools limited to the capabilities, with no skills, Task or Agent;
  - no CLAUDE.md, auto-memory, background tasks or auto-updates.
- **Start:** `get_context_usage` (the window and starting fill; the instruction
  files and skills loaded) and `mcp_status` (its MCP servers); then the setup
  check; then the opening message. No model call happens before this point.
- **Messages:** a stream-json user message, taken in at the next step of a running
  turn, or starting a new one.
- **Context:** the usage of each top-level model call; each turn's result repeats the window.
- **Quota:** a `get_usage` control request to a short-lived print process.

## When a driver misbehaves

| Symptom | Likely cause |
|---|---|
| "loaded the human's own setup (…)" | A personal file or server reached the session; remove it from that CLI's configuration, or fix the driver's switches in `agent_toolkit`; then Ctrl+R |
| "Codex refused …" / "Claude Code refused …" | The CLI rejected a request; the reason follows (e.g. an unknown model) |
| "… exited with status …" | The CLI ended by itself; the last error lines follow |
| Context stays `–`, then an ALERT | The CLI hasn't reported both tokens and window; that session can't be handed off |

## Adding a CLI

A new CLI is one driver in `agent_toolkit` (see its README). research_pipeline
needs no change beyond allowing the new backend name in `--backends`.
