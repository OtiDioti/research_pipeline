# Folder contents

- [helpers.py](helpers.py) — Temporary projects, a fake CLI driver and a controller harness.
- [test_controller.py](test_controller.py) — The controller's decisions, played through fake sessions.
- [test_project.py](test_project.py) — Layout, layout check, git commits, the human's files, state.
- [test_jobs.py](test_jobs.py) — Real job processes: exit status, timeout, cancellation, reattachment.
- [test_confine.py](test_confine.py) — Real bwrap confinement.
- [test_mcp_server.py](test_mcp_server.py) — The MCP tool server over real stdio.
- [test_drivers.py](test_drivers.py) — Shared transport with a real confined process; Codex and Claude events.
- [test_cli_view.py](test_cli_view.py) — Command line and terminal app.
- [live_smoke.py](live_smoke.py) — Live smoke run through the real CLIs (manual; uses model quota).
