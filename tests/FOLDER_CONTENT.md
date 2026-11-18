# Folder contents

- [__init__.py](__init__.py) — Package marker, so that tests import as `tests.*` (run with `-t .`).
- [helpers.py](helpers.py) — Temporary projects, fake CLI drivers (from agent_toolkit's testing module) and a controller harness.
- [test_controller.py](test_controller.py) — The controller's decisions, played through fake sessions.
- [test_project.py](test_project.py) — Layout, layout check, git commits, the human's files, state.
- [test_jobs.py](test_jobs.py) — Real job processes: exit status, timeout, cancellation, reattachment.
- [test_tools.py](test_tools.py) — Each role's tools, through the toolkit's MCP tool server over real stdio.
- [test_cli_view.py](test_cli_view.py) — Command line and terminal app.
- [test_web.py](test_web.py) — The human's single-agent actions and live settings, and the web app's view.
- [test_standards.py](test_standards.py) — The repository follows the shared development standard (agent_toolkit.standards).
- [live_smoke.py](live_smoke.py) — Live smoke run through the real CLIs (manual; uses model quota).
