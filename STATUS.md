# Status

**2026-11-24.** 0.28.0: **agents write for the human** ([PROJECT.md](PROJECT.md) §1 and §8 amended;
docs/SETUP.md). Prompt wording, changed deliberately (agent-facing): common.md replaces the summary recipe (request,
what was done, verdict, each claim with its link and command) with a section "Writing for the human". The result comes
first and in full (an expression asked for is a displayed equation with its symbols defined, never only a table of
numbers), then the argument that explains it, then the evidence (links, commands, checks) in a closing section. Terms
are defined where they first appear, coined names are not allowed, and only what the reader needs goes in. The human's
instructions may adopt their documents' notation, which common.md no longer contradicts. primary.md: REPORT.md opens
with the phase's main results on one page, and a report corrected after a review reads as if written once. reviewer.md:
the Reviewer first reads the objectives and REPORT.md as the human will, restates the main results, and objects when it
cannot or when the writing standards lapse, asking for fixes in place, never for more material. objectives-template.md
gains *Request* (the human's words, unchanged) and *Result* (what they will get); the setup, phase and reopening
assistants keep the human's intent on top, in their vocabulary, and leave methods and the design of checks to the
agents. Asked for after lh_cavity's reports grew less readable phase by phase: phase 3 gave its Hamiltonian only as
tables of numbers. Its reopening under these prompts produced a report with the Hamiltonian on its first page.

**2026-11-23.** 0.27.1: **a flaky test fixed**; no behaviour changed. The pause test
(`test_pause_keeps_sessions_stops_jobs_and_resume_reports_changes_in_them`) failed in the full suite ("pausing" !=
"paused") and passed alone: the pause completes only once the stopped job's process is reaped in a worker thread,
which under load took longer than the fixed wait after the agents' last turns. The test now waits for the pause to
complete, up to five seconds.

**2026-11-23.** 0.27.0, on agent_toolkit 0.21.0: **links are written from the project's root**
([PROJECT.md](PROJECT.md) §2, "Links"; docs/AGENT_ROLES.md, LIBRARY.md, JOBS.md, STATS.md). Every link in the
project's Markdown names its file with a leading slash (`[the fit](/phases/2/agents/fit/RESULT.md)`), so it leads to
the same file wherever the text is read; a folder's FOLDER_CONTENT.md alone names its own files. Every session and job
gets `PROJECT`, the project's folder (`cat "$PROJECT/phases/…"`). The prompts ask for it (common.md, librarian.md,
talk.md and the setup assistants', deliberate agent-facing wording); nothing is refused: at the end of each turn an
agent is told, once each, of the links breaking the convention in the Markdown it changed (`linkcheck.py`), with a
submitted result its parent is told of all of them, and the Librarian hears of its pages' relative links with the
broken ones. Text the controller moves (briefs, feedback, the primary's objectives, the catalogue's index lines) has its
relative links turned into links from the root; the catalogue links from the root too and drops an index line's link
to its own file, which broke 227 of lh_cavity's catalogue links. Older text keeps its relative links. The page's viewer
opens links to project files in place (agent_toolkit 0.21.0), and the statistics read `$PROJECT` and links from the
root. A new end-to-end test (`tests/test_link_audit.py`) reads every Markdown file and message of a whole run for links
that lead nowhere; it found two in the controller's own indexes (AGENTS.md listed when absent, the Reviewer's folder
before it exists), now listed only once they exist. Asked for after lh_cavity showed that every broken link came from
text the controller moved.

**2026-11-23.** 0.26.0, on agent_toolkit 0.20.0: **a *Talks* switch decides whether the assistant gets your
talks** ([docs/SETUP.md](docs/SETUP.md), "The talks"; PROJECT.md §3 and §4 amended). On a new phase's or a
reopening's setup page, above the conversation, like the activity's Tools switch: on by default, its note on hover
says what it gives and how many messages there are. Your first conversation message (ideas, answers, draft now or a
free message; not *organise*) fixes it, greyed from then on and kept across restarts; a first message the assistant
refuses fixes nothing. On, that message hands the assistant TALKS.md, written only from then on; off, it never gets
the talks. The assistant now no longer sees the program's records in `.research/` (but its own folder), as no agent
does: it could read the earlier phases' activity logs, talks included. Prompt wording (agent-facing, deliberate):
phase.md and reopen.md say only what the switch allows (that the talks may come, where they are, or nothing), and a
notice hands them over with the first message; a reopening's requests and its first-ideas placeholder mention the
talks only as "if you have them". A preparation saved before the switch existed keeps the talks, fixed once the
human had written. Asked for after preparing lh_cavity's phase 2 while talking with phase 1's primary.

**2026-11-23.** 0.25.1, on agent_toolkit 0.19.0: **unfolding an agent's files shows only its own
relations** ([docs/WEB.md](docs/WEB.md), "The graph"). A website or library page several agents used was one node
with edges to all of them, so unfolding one agent drew lines to every other agent that used it (in lh_cavity,
LIBRARY.md, CATALOG.md and an arXiv paper six agents looked up) and the layout pulled it between them. The page now
draws it once per agent, beside it and linked only to it; its hover card says "Also used by" the others, and a
search hit on it shows a copy beside each agent that used it. The snapshot sent to the page is unchanged.

**2026-11-23.** 0.25.0, on agent_toolkit 0.18.0: **links keep working in texts read from another folder**
([docs/AGENT_ROLES.md](docs/AGENT_ROLES.md), "Spawning"; PROJECT.md §3 amended). A brief is written in the parent's
folder, often in `briefs/`, and read as the subagent's `TASK.md`; it was copied unchanged, so its relative links led
to the wrong places. Now each relative link that reaches an existing file from the brief's folder and none from
`TASK.md` is rewritten to lead to the same file; every other link is kept as written, so links a parent already
wrote for `TASK.md` never change, and the `spawn` reply lists the kept links that reach nothing from either folder,
or a different file from each. The same applies to a rejection's feedback (read in the subagent's folder) and to the
objectives in the primary's opening message (read from its folder). The `spawn` tool description says so, in one
sentence (agent-facing wording). Found in the lh_cavity run: all 50 links of its 8 briefs were broken (the
primary and a subagent sent corrections by message), and so were 221 of the 372 in transport; on lh_cavity's briefs
the rule rewrites 47 and reports 3. Not yet tried in a live run.

**2026-11-23.** 0.24.0, on agent_toolkit 0.18.0: **a machine where bwrap cannot confine sessions says so.** Being
installed is not enough: bwrap must be allowed to create unprivileged user namespaces, which Ubuntu 23.10 and later
forbid through AppArmor until bwrap has a profile ([docs/CONFINEMENT.md](docs/CONFINEMENT.md), "What the machine must
allow", with the check and the profile). A CLI's status now runs bwrap once, so on such a machine every CLI is greyed
with "bubblewrap cannot confine sessions on this machine (…)", Start and Resume wait, and the setup assistant refuses
its requests with that reason before trying a session. A session that ends before replying now says why ("codex ended
before replying: exited with status 1: bwrap: setting up uid map: Permission denied"). Found after an upgrade from
Ubuntu 22.04 to 24.04: "Let the assistant organise" only answered "codex ended before replying".

**2026-11-22.** 0.23.0, on agent_toolkit 0.17.0: **CLIs that are not set up are greyed** in the page's CLI
choices ([docs/WEB.md](docs/WEB.md), "The setup page"; PROJECT.md §6): one not installed, or not logged in (asked
of `claude auth status` / `codex login status`, no model call), with the reason on hover and *Check again*. The
primary, the Reviewer and the Librarian on such a CLI keep Start waiting; the recommended models and the CLIs for
subagents only warn. A stopped project shown on the page waits the same way: *Resume phase N*, and *Open for
talks* for one whose phase ended (no longer opened at once then), wait with the reason until its role CLIs can run
(checked again every 30 s while shown, and at the press). A failed turn now gives the CLI's reason ("primary: its turn failed (Not logged in · Please run
/login)"), still retried after 30 s / 2 min / 10 min; the setup assistant passes it on too. Found by trying both CLIs
logged out and missing: before, a logged-out CLI started its sessions normally and only "its turn failed" was shown.

**2026-11-22.** 0.22.0, on agent_toolkit 0.16.0: **`research-pipeline run` opens a workbench** of every project
of this machine ([docs/WEB.md](docs/WEB.md), "Projects"; PROJECT.md §6 amended). The page opens with no project and
the sidebar open (a line points to it; the project's parts are greyed); projects are selected, created (a folder
browser, then a name: `Protein Folding 2` → `protein-folding-2/`), added from a folder, renamed (display name in
`.research/name`) and removed from the list (the folder stays); the selected one's phases unfold under it and are
renamed there too (`phases/FOLDER_CONTENT.md` follows). The list is `~/.config/research_pipeline/projects.json`.
`run PROJECT` adds and shows one; the options for one project need it; a second `run` opens the running server's
page. One project works at a time: the others' Start, Resume and Reopen wait ("No other project runs"). Each
project's dashboard now runs its own controllers, so the server outlives them: a project that stopped is shown as it
was left, read-only, with *Resume phase N*; one whose phase ended opens for talks when selected; one another process
runs is read-only. The top bar's Quit is now Close (the program goes on). The page's address names the project and
phase. Not yet tried with real CLIs.

**2026-11-21.** 0.21.1, on agent_toolkit 0.15.0: the top bar no longer repeats the phase's state. After the
state (`phase 2: complete`) it showed the whole outcome line (`COMPLETE on <date>: the Reviewer agreed (…)`, true by
construction for COMPLETE) or, for a phase not running, its status again; now it shows only the running phase's
sessions and a proposal under review. The outcome line stays in the phase's STATUS.md ([docs/WEB.md](docs/WEB.md)).

**2026-11-20.** 0.21.0, on agent_toolkit 0.15.0: **statistics** of a run ([docs/STATS.md](docs/STATS.md)),
deterministic and read-only. The web page's *Stats* button replaces the graph with them (then *Graph* goes back):
library use; the spawn tree and agents at work over time; for each child, which links of its brief it opened and
which of its parent's files it read without a link; for each result, what the parent read and ran of the child's
work before deciding; resources; per-agent cards; live (every 5 s while shown) and comparable with other projects,
including those made before phases. `research-pipeline stats PROJECT [--phase N|all]` prints the key numbers.
Tool calls become file accesses by fixed rules (`stats/calls.py`), from the whole calls agent_toolkit 0.15.0 now
records; older runs are parsed from their summaries and marked approximate (a third of transport's calls were cut).
On transport: children opened 42% of their brief links and read 223 of their parents' files unlinked; parents
rejected 3 of 70 results. Not yet tried in a live run.

**2026-11-20.** 0.20.0, on agent_toolkit 0.14.0: prompts only (`common.md`, `reviewer.md`), from what the
`transport` run showed (below the primary, every subagent spawned at most one child, nearly always a check of its
own work; parents reread and reran their children's work and rarely rejected). Spawning now splits work: parallel
subproblems go to sibling subagents spawned together with a shared conventions file, a serial chain stays with one
agent, and no agent spawns a checker of its own result. Checking is divided: the author checks fully and lists its
key claims with evidence, check and reproducing command in every summary; the parent spot-checks one or two
deciding claims, records what it checked, and rejects rather than redoes; the Reviewer checks independently what
only the author checked. Every brief has a **"Prior work" section** (it may be empty): what the project already
has for the task, linked, or what was searched for and not found; summaries also link the earlier work they built
on. This is asked by the prompts only, not
checked by the controller, so that it can be changed in the prompts alone.
The **catalogue is split**: `library/CATALOG.md` is now a short index (the shelved agents by phase with the titles
of their tasks, then the agents at work), and each shelved agent's files are on its own page in
`library/catalog/phase-<N>/<id>.md`, for agents to search ([docs/LIBRARY.md](docs/LIBRARY.md)); in the transport
run the single file had grown to 285 KB, and agents read it whole. Existing projects get the new form at their
next commit. Not yet tried with real CLIs.

**2026-11-20.** 0.19.0, on agent_toolkit 0.14.0: acting on agents moved to an **action ring**
([docs/WEB.md](docs/WEB.md)). Hovering an agent shows, besides its card, round buttons on its left (on its right
near the page's edge): chat, pause or resume, hand off, cancel and files, greyed with the reason when not possible
now. The right-click menu and the message box are gone: chat opens a window over the page with one agent (your
messages and its own text, from its activity log, so earlier talks are there; Markdown and LaTeX), and the status
bar no longer names a default recipient (a message without a target is refused). Selecting only highlights;
*files* unfolds an agent's documents, jobs and sites, and a click on empty space folds them all. No change to the
controller's behaviour or the prompts. Not yet tried with real CLIs.

**2026-11-20.** 0.18.0, on agent_toolkit 0.13.0: folded panel windows drop to bars at the bottom-right of the
web page (Activity above Task & notes), leaving the graph visible above ([docs/WEB.md](docs/WEB.md)). Open windows
fill the height down to the bars; two open windows split it at a border to drag (remembered). The legend sits in
the top-right corner while every window is folded, beside the windows otherwise. No change to the controller or
prompts. Not yet tried with real CLIs.

**2026-11-20.** 0.17.0, on agent_toolkit 0.12.0: the web panel's windows float over the graph
([docs/WEB.md](docs/WEB.md)). The graph takes the whole width; Activity and Task & notes are docked at its right
edge, each folding to a bar on its own (the graph shows, and stays usable, around them), each with its own height
and a shared width, dragged by their edges. The legend sits above the folded bars and slides beside the windows
while one is unfolded; the message box stays left of them. No change to the controller or prompts. Not yet tried
with real CLIs.

**2026-11-20.** 0.16.0, on agent_toolkit 0.11.0: a roomier web panel ([docs/WEB.md](docs/WEB.md)). Messages and
tool calls share one **Activity** window, in time order; tool calls show only with its *Tools* switch on (off by
default). The separate header card is gone: the Activity header names the agent with its status and actions
(Cancel behind a ⋯ menu). Activity and Task & notes each fold to their header, one at a time; the folds, the
switch and the panel sizes are remembered in the browser. No change to the controller or prompts. Not yet tried
with real CLIs.

**2026-11-20.** 0.15.0, on agent_toolkit 0.10.0: **phases** (PROJECT.md §2 "Phases", §4;
[docs/WEB.md](docs/WEB.md)). A project's investigation runs in numbered phases, one folder each (`phases/<N>/`: its
OBJECTIVES.md, STATUS.md, REPORT.md, `agents/` and `reviews/`); `AGENTS.md`, `starting_evidence/`, `library/` and
the Librarian (now in `librarian/`) are shared. One phase runs at a time. The web page has a collapsible sidebar
listing the phases (running one marked): selecting a phase shows its graph (live, or as it was left, with talks
with its primary and Reviewer while another phase runs), *New phase* prepares a fresh primary on new objectives
(with a title and an optional phase it builds on, and its own assistant, `prompts/phase.md`), and an earlier phase
can be continued: a paused one resumes from its handoffs, an ended one reopens. Switching needs the running phase
paused (its sessions save their handoffs) or ended. A phase continued after others ran is told of the later ones;
every primary is told of the other phases; the Librarian is told of each new phase, and shelving requests name
folders (`shelved(folder)`). **FEEDBACK.md is gone**: only a change of a phase's own OBJECTIVES.md reopens it after
COMPLETE or STOP (AGENTS.md or material alone do not), and the reopening assistant revises the objectives instead
of writing a FEEDBACK section. State: each phase's in `.research/phases/<N>/state.json`, what the phases share in
`.research/project.json`; `run --no-web` runs the latest phase. New modules `phases.py` and `graph.py` (the web
page's per-phase graph); the controller runs one phase and hosts the Librarian's sessions; it is still over 500
lines. Deliberate prompt changes: every role is told its phase and folder paths; the primary's prompt drops
FEEDBACK.md, points to earlier phases' work through the library, and reserves STOP for objectives that cannot be
achieved; the Librarian organises by phase and objective; the talk, setup and reopening prompts are per phase; new
notices for a new phase (Librarian), the other phases (primary's opening) and later phases (on continuing); tool
descriptions of `shelved`, `write_objectives` and `write_page`, and `write_feedback` removed. No migration of
existing projects (to be moved by hand). Not yet tried with real CLIs.

**2026-11-19.** 0.14.0, on agent_toolkit 0.9.0: reopening from the web page
([docs/FINISHING.md](docs/FINISHING.md), PROJECT.md §4). After COMPLETE or STOP the top bar offers *Prepare reopening*:
the setup page again, while the talks go on, with Material, Instructions (FEEDBACK.md, OBJECTIVES.md, AGENTS.md as
tabs), the files changed since the end (Revert each, Discard all), the launch options and Reopen. Reopen waits for a
change, a ready folder, the Librarian's final shelving and an idle assistant, and says which it waits for; it ends the
talks and restarts the investigation in the same program and page. The reopening assistant (new `prompts/reopen.md`,
`reopen-requests.md`; tools `write_feedback`, `write_agents_md`) reads the talks since the end
(`.research/setup/TALKS.md`), can grill the human, and writes this reopening's `## Reopening N (date)` section of
FEEDBACK.md. With the page, a later `run` keeps prepared changes waiting for Reopen; `--no-web` still reopens on
changed files. Changes since the end are now judged by content against the end's commit (kept in the state), so a
reverted file is no change. Deliberate prompt change: the reopened primary's notice points to this reopening's
FEEDBACK.md section when there is one. Also fixed: after a reopening the primary was told about the same changes a
second time. `web.py`'s settings moved to `fields.py`. Not yet tried with real CLIs.

**2026-11-19.** 0.13.0: `--web` and `--no-tui` are gone. Since 0.12.0 they only repeated the defaults (the web
page, the printed transcript); a command that still passes them is now refused by the argument parser before
anything starts. Use `--no-web` and `--tui` for the other choices.

**2026-11-19.** 0.12.0, on agent_toolkit 0.8.0:
- **Removing material on the setup page** ([docs/SETUP.md](docs/SETUP.md)). Any entry, loose or placed, can be
  removed after a confirmation that says what happens, and nothing the human cannot get back is deleted. A copy made
  by Copy in is deleted only while its original is still there, byte for byte; imports are recorded in
  `.research/material/imports.json` and followed through placing. Anything else is set aside in
  `.research/removed/` and restored from the page as loose material. A placed entry's index line goes too, and so
  does a folder left empty. Only the human removes: the assistant has no such tool.
- **The web app is the default.** `run` opens the page (setup page first), and the terminal prints the transcript.
  `--no-web` runs without the page (an unready folder is refused), and `--tui` shows the terminal app. `--web` and
  `--no-tui` are still accepted, as no-ops.
- **Recommended models.** The prompt's model routing (`common.md`) now fills in two options, `coding` and `analysis`
  (default `claude:claude-opus-5-5:xhigh` and `codex:gpt-6.1-sol:xhigh`). They are set on the setup page at every
  launch, or live from each agent's next session, and the page warns when one's CLI is not among the CLIs for
  subagents. Deliberate prompt change: each recommendation's effort replaces "xhigh for the most demanding, high
  otherwise", and when a backend is unavailable agents use "the best model you can on an available backend" instead
  of "the other".
Not yet tried with real CLIs.

**2026-11-19.** 0.11.1, prompts only (`common.md`): parents give subagents the time their task needs (no deadline
unless the human sets one), message them to redirect or inform, never to hurry them, ask for an interim note when they
need part of the work sooner, and cancel rather than ask for a rushed result. Prompted by a run in which parents asked
subagents to finalize minutes after starting them, and a rushed priority check missed the closest antecedent.

**2026-11-18.** 0.11.0: talks after the end ([docs/FINISHING.md](docs/FINISHING.md), PROJECT.md §4). After COMPLETE
or a confirmed STOP the program stays open (`complete (talk only)`) until the human quits: a message to the primary
(chat box, web page) or the Reviewer (web page) starts a talk session from its handoff and key files, read-only,
without subagents or jobs, through agent_toolkit's `Relay`; its talk note (`.research/talks/<agent>.md`, saved at
the context threshold, the idle limit or a quit) carries the talk across sessions. Talks stay in the activity log
only. A later `run` opens talk-only again, and reopens only if the human's files changed since the end (they no
longer reopen it while the program stays open). New prompts `talk.md`, `talk-messages.md`; new tool
`write_talk_note`. The web page shows only Quit after the end. Not yet tried with real CLIs.

**2026-11-18.** 0.10.1: on agent_toolkit 0.7.1, the setup page keeps what was typed and not yet sent or saved
(ideas, unsaved edits of OBJECTIVES.md, answers in progress, the organiser's drafts) when switching between its steps.

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
