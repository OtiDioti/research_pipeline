# CLI drivers

`drivers/`. One persistent session per running agent. Each driver is the only
code that knows its CLI; everything else is generic.

## The shared base (`drivers/base.py`)

- Starts the CLI inside its confinement, and speaks JSON lines on its stdin and stdout.
- Logs every line to `.research/logs/<agent>-<session>.jsonl`. Prefixes: `>` sent,
  `<` received, `E` error output, `!` a message it couldn't handle.
- Matches replies to requests (timeout: 120 s); a request still waiting when the CLI ends fails at once.
- **Setup check:** refuses a session whose CLI reports having loaded any instruction
  file, skill, or MCP server other than the controller's `research` server.
- Turns everything into five events for the controller: `text`, `tool`, `context`, `turn_ended`, `exited`.
- Closing: the CLI gets SIGTERM, then SIGKILL after 10 s; its confinement ends with it.
- An unexpected exit reports the last 20 lines of the CLI's error output.

## Codex (`drivers/codex.py`)

- **Process:** `codex app-server`, speaking JSON-RPC.
- **Discovery off:**
  - native subagents, apps, plugins, host skills and user-input requests are disabled;
  - `project_doc_max_bytes=0` stops project AGENTS.md files;
  - the personal `config.toml` and `AGENTS.md` are masked ([CONFINEMENT.md](CONFINEMENT.md)).
- **Start:**
  1. `initialize`;
  2. `thread/start` (ephemeral, `danger-full-access` inside our confinement, no
     approvals, the session instructions as developer instructions);
  3. the setup check, on `instructionSources` and `mcpServerStatus/list`;
  4. `turn/start` with the opening message.
- **Messages:** `turn/steer` during a turn, otherwise a new `turn/start`.
- **Context:** `thread/tokenUsage/updated`.
- **Requests from Codex** (approvals) are refused.
- **Quota:** `account/rateLimits/read` on a short-lived app-server.

## Claude Code (`drivers/claude.py`)

- **Process:** `claude -p` with stream-json in and out, no session persistence,
  and permissions bypassed inside our confinement.
- **Discovery off:**
  - no setting sources, hooks off, sandbox off;
  - only the controller's MCP server;
  - built-in tools limited (no skills, no Task or Agent);
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
| "loaded the human's own setup (…)" | A personal file or server reached the session; remove it from that CLI's configuration, or fix the driver's switches; then Ctrl+R |
| "Codex refused …" / "Claude Code refused …" | The CLI rejected a request; the reason follows (e.g. an unknown model) |
| "… exited with status …" | The CLI ended by itself; the last error lines follow |
| Context stays `–` | The CLI hasn't reported both tokens and window yet |

## Adding a CLI

Write one `Session` subclass and register it in `drivers/__init__.py`. It provides:
- `command`: the command line, with the CLI's own discovery switched off;
- `begin`: the handshake, then `check_setup` with what the CLI reports having loaded;
- `deliver`: messages during a turn, or as a new turn;
- `receive`: turning the CLI's output into the five events;
- optionally `environment`, `state_paths`, `masked_paths` and `read_usage` (the quota probe).
