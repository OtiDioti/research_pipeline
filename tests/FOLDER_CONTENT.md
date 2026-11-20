# Folder contents

- [__init__.py](__init__.py) — Package marker, so that tests import as `tests.*` (run with `-t .`).
- [helpers.py](helpers.py) — Temporary projects, fake CLI drivers (from agent_toolkit's testing module) and a controller harness.
- [test_controller.py](test_controller.py) — The controller's decisions, played through fake sessions.
- [test_librarian.py](test_librarian.py) — The Librarian and the library: shelving, `write_page`, `shelved`, the end and reopening.
- [test_links.py](test_links.py) — Links in Markdown pages: link forms, folders, wikilinks, links that lead nowhere.
- [test_project.py](test_project.py) — Layout (with the phases' folders), layout check, git commits, the human's files, state.
- [test_jobs.py](test_jobs.py) — Real job processes: exit status, timeout, cancellation, reattachment.
- [test_tools.py](test_tools.py) — Each role's tools, through the toolkit's MCP tool server over real stdio.
- [test_cli_view.py](test_cli_view.py) — Command line and terminal app.
- [test_web.py](test_web.py) — The human's single-agent actions and live settings, and the web app's view.
- [test_standards.py](test_standards.py) — The repository follows the shared development standard (agent_toolkit.standards).
- [live_smoke.py](live_smoke.py) — Live smoke run through the real CLIs (manual; uses model quota).
- [test_setup.py](test_setup.py) — The web setup before the first start: readiness, material placed by hand, the objectives' versions, the setup assistant on fake sessions, quota and failures.
- [test_talks.py](test_talks.py) — Talks after a phase's end: talk-only sessions, talk notes, staying talk-only until its objectives change, quota.
- [test_reopen.py](test_reopen.py) — Reopening a phase from the web page after its end: the preparation offered again, changes and reverts, the reopening assistant, Reopen on changed objectives, and later runs.
- [test_phases.py](test_phases.py) — Phases: a new phase from the web page, talks with another phase while one runs, switching phases through a pause, later phases' notice, the library across phases.
