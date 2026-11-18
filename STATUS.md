# Status

**2026-11-18.** 0.10.0: the web setup ([docs/SETUP.md](docs/SETUP.md), PROJECT.md §2, §3, §6). `run DIR --web`
opens a setup page on any folder no investigation has started in, even one that does not exist yet or is ready
already: *Material* (upload, copy from local paths, or by hand; each loose entry placed in `starting_evidence/` with
a one-line description, new folders described too, by hand or by the setup assistant), *Objectives* (first ideas,
an optional grill of multiple-choice questions, an editor whose saves name their version), then the launch options;
Start waits for `Project.unready()`'s checks, which the command line now applies too (before the first start: no loose
material, `starting_evidence/` described). Without `--web` an unready folder is refused with the hint. The setup
assistant (`--setup`, default `codex:gpt-6.1-sol:high`; new prompts `setup.md`, `setup-requests.md`,
`objectives-template.md`) runs through agent_toolkit's `Relay` and acts only through `place`, `write_objectives`
and `ask`; its quota is read before each request. Needs agent_toolkit 0.7.0 (preparation steps on the setup page),
pinned by its tag. Not yet tried with real CLIs.

**2026-11-18.** 0.9.0: objectives instead of questions. The human's input is `starting_evidence/OBJECTIVES.md`
(formerly `RESEARCH_QUESTIONS.md`; a project that still has the old file is told to rename it), and an objective is a
question to answer or a task to perform. A task is met when its deliverable is built, verified and documented;
prompts, the `complete` and `spawn` descriptions, notices and docs say "objective", and summaries mark each one
met, partial, infeasible or open. PROJECT.md's summary of the prompts now also matches 0.8.0 (decide, don't ask).

**2026-11-18.** 0.8.0, prompts only (`src/research_pipeline/prompts/`): agents decide what a question leaves open and
record each decision with its criterion; work is held to a no-shortcuts standard (only physical limits excuse
less, with evidence), which parents apply when accepting results and the Reviewer when judging; citations must be
sources actually opened; every summary (RESULT.md, REPORT.md, reviews) first restates the request it answers.
Subagents are routed by task: coding to Opus 5.5, analysis to GPT-6.1 Sol, the other when a backend is not
allowed or held by its quota. Not yet tried in a live run.

**2026-11-18.** 0.7.0: the Librarian and the library ([docs/LIBRARY.md](docs/LIBRARY.md), PROJECT.md §2–§10).
Finished work stays where it was made: an accepted or cancelled subagent's folder, and at the end the primary's and
the Reviewer's, is shelved (catalogued in `library/CATALOG.md` and frozen, read-only for jobs too), and the
Librarian (`--librarian`, required; outside `--max-agents`) links it from its Markdown pages in `library/` through
`write_page`; `shelved(agent)` is refused until every file is reachable and no link leads nowhere. At the end the
controller waits for it unless it cannot run or stalls. `sources/` and `tools/` are gone, and projects that still
have them are refused. A quota hold now pauses only the held CLI's agents, also when it is the primary's. The live
smoke run checks the shelving but has not been run since.

**2026-11-18.** On agent_toolkit 0.6.2: AGENTS.md alone carries the shared standard, and CLAUDE.md is removed.
No behaviour changed.

**2026-11-18.** The shared development standard of agent_toolkit: AGENTS.md carries it (CLAUDE.md imports it),
the code is formatted and linted by ruff and type-checked by pyright (`uv run ruff format --check`, `uv run ruff
check`, `uv run pyright`), every folder has a FOLDER_CONTENT.md, `tests/test_standards.py` checks all of it, and
CI (`.github/workflows/checks.yml`) runs the checks and the tests on Python 3.11 and 3.13. No behaviour changed.
agent_toolkit is a local path dependency until its release restores the tag pin.

**2026-11-18.** Context resets only at the threshold ([docs/CONTEXT.md](docs/CONTEXT.md)): an agent keeps its
CLI session while it waits (for a review, a verdict, its parent's decision, a human pause or a quota hold), and its
context is reset only at a context or forced handoff, at the idle limit (`--idle-limit`, 58 minutes, inside the
prompt cache's hour; editable live), or when the controller stops. `--max-agents` counts open sessions, idle ones
included (default 6). The Reviewer judges the project as of the proposal's commit. On the first run the primary is
no longer told wrongly that the human's files changed.

**2026-11-17.** The web app (`--web`, [docs/WEB.md](docs/WEB.md)): a setup page for every option, the agent
graph with every agent's messages and tool calls (kept in `.research/activity/`), and the human's actions on
single agents (message with the parent copied, pause and resume, force a handoff, cancel) and live settings.

**2026-11-16.** The V0 core implements [PROJECT.md](PROJECT.md) (approved 2026-11-16). See [README.md](README.md)
for usage.

- **Implemented:**
  - the controller: the agent tree, live notices, handoffs, tools, and messages between parents and subagents;
  - idle and stalled agents, the idle limit, and the Reviewer exchange with the primary waiting in its session;
  - quota holds, pause, shutdown, crash restart and reopening;
  - Codex and Claude Code sessions from the shared package `agent_toolkit` (drivers, confinement and
    quota probes, also used by coding_pipeline and project_manager), with the CLIs' own discovery switched
    off and checked at every session start;
  - the machinery shared with coding_pipeline and project_manager through `agent_toolkit`: handoff rules,
    usage holds, durable state and controller files (never written through a symlink), a git runner that
    never runs hooks, strict prompt files and the terminal app;
  - an ALERT when a session's context use is still unknown after its first turn;
  - `bwrap` confinement of agent sessions and of jobs: `starting_evidence/` is read-only and `.research/` hidden;
  - the MCP tool server;
  - jobs that survive handoffs, quota pauses, shutdowns and crashes;
  - the layout check and git commits;
  - the terminal app and the command line.
- **Tests:** `uv run python -m unittest discover -s tests -t .` runs 99 tests, with no model usage; the shared drivers, confinement and machinery are tested in
  agent_toolkit.
- **Checked against the installed CLIs without model calls** (Codex 0.167, Claude Code 2.1.325): both start inside
  the confinement with the human's own setup masked, report what they loaded, and pass the setup check. Claude
  Code reports its context window before the first model call.
- **Live verification:** `tests/live_smoke.py` now also checks, with a Monitor, that waiting keeps sessions (a
  rejected subagent, the verdict, a human pause, a quota hold) and that an idle session closes at a lowered idle
  limit (`--idle-limit`, 0.5 minutes there). Run on 2026-11-18 (Codex primary, Claude Haiku Reviewer and
  subagents; thresholds 3% and 10%), every investigation ended COMPLETE and each check passed: the rejected
  subagent continued in its session, the primary received the verdict in its session (replaced only by context
  handoffs), paused agents resumed in their sessions, a quota-held subagent continued in its session when the
  hold lifted within the idle limit and, in another run, closed without a turn when the hold outlasted it, and
  idle sessions closed after one note turn.

**Next:** the light-hole benchmark (PROJECT.md §11) on a copy of `research_example/`,
judge the science, and let project_manager deliver further increments.
