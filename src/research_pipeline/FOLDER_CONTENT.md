# Folder contents

- [__init__.py](__init__.py) — Package marker.
- [__main__.py](__main__.py) — `python -m research_pipeline` entry point.
- [cli.py](cli.py) — Command line: `run` (start, resume, reopen) and `status`.
- [controller.py](controller.py) — The controller: agent tree, sessions, notices and messages, handoffs, idle and stalled agents, tools, the Reviewer exchange, quota, pause, shutdown, finishing.
- [state.py](state.py) — Persistent state (agents, jobs, proposals, quota holds) in `.research/state.json`.
- [project.py](project.py) — The project folder: layout, layout check, git commits, the human's files.
- [channel.py](channel.py) — Abstract Unix socket between agents' MCP servers and the controller.
- [mcp_server.py](mcp_server.py) — The MCP tool server each agent's CLI starts; the agent-facing tools.
- [jobs.py](jobs.py) — Long computations that outlive agent sessions.
- [prompts.py](prompts.py) — Session instructions (role prompt and the human's AGENTS.md), opening messages and notices.
- [prompts](prompts) — Role prompt texts: shared scientific and operational guidance, one file per role.
- [view.py](view.py) — The terminal app (adapted from project_manager).
