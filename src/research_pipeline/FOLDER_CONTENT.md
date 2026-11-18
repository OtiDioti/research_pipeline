# Folder contents

- [__init__.py](__init__.py) — Package marker.
- [__main__.py](__main__.py) — `python -m research_pipeline` entry point.
- [cli.py](cli.py) — Command line: `run` (start, resume, reopen) and `status`.
- [controller.py](controller.py) — The controller: agent tree, sessions, notices and messages, handoffs, idle and stalled agents, tools, the Reviewer exchange, quota, pause, shutdown, finishing (with the Librarian's final shelving).
- [state.py](state.py) — Persistent state (agents, jobs, proposals, quota holds, pending shelving) in `.research/state.json`.
- [project.py](project.py) — The project folder: layout, layout check, git commits, the human's files.
- [librarian.py](librarian.py) — The controller's side of the Librarian: shelving requests, `write_page` and `shelved`, its turns.
- [library.py](library.py) — The library's catalogue of shelved files (`.research/library.json`) and `library/CATALOG.md`.
- [links.py](links.py) — Links in Markdown pages: the files they reach and the links that lead nowhere.
- [tools.py](tools.py) — The agent-facing MCP tools of each role, offered through agent_toolkit's tool bridge, and their refusal.
- [jobs.py](jobs.py) — Long computations that outlive agent sessions.
- [prompts.py](prompts.py) — Session instructions (role prompt and the human's AGENTS.md), opening messages and notices.
- [prompts](prompts) — Role prompt texts: shared scientific and operational guidance, one file per role.
- [view.py](view.py) — The terminal app (built on agent_toolkit's shared one).
- [web.py](web.py) — The web app's view of the investigation: setup page, agent graph, activity, single-agent controls.
