# Status

**2026-11-14.** The V0 core is implemented and verified. See [README.md](README.md) for usage and
[PROJECT.md](PROJECT.md) for the specification.

- **Implemented:**
  - the controller (agent tree, live notices, handoffs, tools, Reviewer exchange, quota holds, pause/resume, crash restart, reopening);
  - Codex and Claude Code drivers on one shared transport;
  - single-`bwrap` confinement;
  - the MCP tool server;
  - jobs;
  - the layout check and git commits;
  - the terminal app and the command line.
- **Tests:** `uv run python -m unittest discover -s tests -t .` runs 61 tests, with no model usage.
- **2026-11-16:** context use comes only from each CLI's own reports (Claude Code's window from `get_context_usage` at session start). The assumed 200k window and windows carried over between sessions are removed. Not yet confirmed on a live run.
- **Live verification** (`tests/live_smoke.py`), public investigations, each reaching COMPLETE with the Reviewer's agreement:
  1. Codex primary, Claude subagent and Claude Reviewer. Shown: cross-CLI spawn, a rejected then accepted result, jobs, a subagent handoff.
  2. Claude primary, Codex subagents and Codex Reviewer. Shown: a primary handoff; a quota hold on Codex only, with automatic resume; a human pause with edits announced on resume; nested subagents; a Reviewer helper.
  3. Codex primary, Claude subagents and Reviewer. Shown: a STOP proposal, a human pause in the middle of a review, the Reviewer challenging the STOP, the primary continuing and then reaching COMPLETE in round 2.
- **Independent code review:** found 12 defects (a pause that could hang, an acceptance that could revert, stray files blocking work, failed turns stalling agents, and others). All are fixed and covered by regression tests.
- **From run 3:** a CLI held by its quota used to make `reject` fail, and the primary then proposed STOP. Rejections now always stand and simply wait for the CLI, and parents are told that quota pauses are temporary.
  Run 4 repeated that scenario: the primary was told the pause was temporary, its rejection went through, and the run reached COMPLETE.
- **Previous implementation:** tag `pre-v0-restart`. The unmerged L5 work is on the remote branch `cwi/20261113T063709_7f21ba4a`.

**Next:** implement what PROJECT.md (approved 2026-11-16) specifies beyond the code:
- jobs in their own confinement (`starting_evidence/` read-only, `.research/` hidden for agents and jobs);
- messages between parents and subagents;
- idle and stalled agents;
- the primary's session closed during review;
- jobs surviving a shutdown;
- AGENTS.md for every agent, with the CLIs' own discovery switched off;
- explicit model and effort for every agent.

Then run the light-hole benchmark (PROJECT.md §11) on a copy of `research_example/`, judge the science, and let
project_manager deliver further increments.
