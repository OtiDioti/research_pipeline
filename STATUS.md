# Status

**2026-11-16.** The V0 core implements [PROJECT.md](PROJECT.md) (approved 2026-11-16). See [README.md](README.md)
for usage.

- **Implemented:**
  - the controller: the agent tree, live notices, handoffs, tools, and messages between parents and subagents;
  - idle and stalled agents, and the Reviewer exchange with the primary's session closed during review;
  - quota holds, pause, shutdown, crash restart and reopening;
  - Codex and Claude Code sessions from the shared package `agent_sessions` (drivers, confinement and
    quota probes, also used by coding_pipeline and project_manager), with the CLIs' own discovery switched
    off and checked at every session start;
  - the machinery shared with coding_pipeline and project_manager through `agent_sessions`: handoff rules,
    usage holds, durable state and controller files (never written through a symlink), a git runner that
    never runs hooks, strict prompt files and the terminal app;
  - an ALERT when a session's context use is still unknown after its first turn;
  - `bwrap` confinement of agent sessions and of jobs: `starting_evidence/` is read-only and `.research/` hidden;
  - the MCP tool server;
  - jobs that survive handoffs, quota pauses, shutdowns and crashes;
  - the layout check and git commits;
  - the terminal app and the command line.
- **Tests:** `uv run python -m unittest discover -s tests -t .` runs 66 tests, with no model usage; the shared drivers, confinement and machinery are tested in
  agent_sessions.
- **Checked against the installed CLIs without model calls** (Codex 0.167, Claude Code 2.1.325): both start inside
  the confinement with the human's own setup masked, report what they loaded, and pass the setup check. Claude
  Code reports its context window before the first model call.
- **Live verification:** `tests/live_smoke.py` has not yet been run on this implementation.

**Next:** run the live smoke test, then the light-hole benchmark (PROJECT.md §11) on a copy of `research_example/`,
judge the science, and let project_manager deliver further increments.
