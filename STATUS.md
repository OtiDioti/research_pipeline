# Status

**2026-11-16.** The V0 core implements [PROJECT.md](PROJECT.md) (approved 2026-11-16). See [README.md](README.md)
for usage.

- **Implemented:**
  - the controller: the agent tree, live notices, handoffs, tools, and messages between parents and subagents;
  - idle and stalled agents, and the Reviewer exchange with the primary's session closed during review;
  - quota holds, pause, shutdown, crash restart and reopening;
  - Codex and Claude Code drivers on one shared transport. Each driver holds everything specific to its CLI,
    including its quota probe, switches off the CLI's own discovery, and reports what the CLI loaded to a
    shared setup check at every session start;
  - `bwrap` confinement of agent sessions and of jobs: `starting_evidence/` is read-only and `.research/` hidden;
  - the MCP tool server;
  - jobs that survive handoffs, quota pauses, shutdowns and crashes;
  - the layout check and git commits;
  - the terminal app and the command line.
- **Tests:** `uv run python -m unittest discover -s tests -t .` runs 76 tests, with no model usage.
- **Checked against the installed CLIs without model calls** (Codex 0.167, Claude Code 2.1.325): both start inside
  the confinement with the human's own setup masked, report what they loaded, and pass the setup check. Claude
  Code reports its context window before the first model call.
- **Live verification:** `tests/live_smoke.py` has not yet been run on this implementation.

**Next:** run the live smoke test, then the light-hole benchmark (PROJECT.md §11) on a copy of `research_example/`,
judge the science, and let project_manager deliver further increments.
