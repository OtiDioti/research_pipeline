# Research Pipeline

An autonomous research investigator. You give it objectives (research questions
to answer or research tasks to perform), starting evidence and tools; a **primary researcher** agent leads the investigation, spawns
**subagents** for subproblems, runs computations and writes what it learns into an
ordinary project folder. When it judges the work done it proposes **COMPLETE**,
which an independent **Reviewer** must agree with, or **STOP**. A **Librarian**
keeps a library of pages that lead to the finished work. You judge the
science. The specification is [PROJECT.md](PROJECT.md); [docs/](docs/OVERVIEW.md) describes each
part and what it does under each condition.

```mermaid
flowchart LR
    You([You]) -->|objectives, evidence, messages, Pause| C{{"Controller<br/>(deterministic)"}}
    C -->|transcript, status, alerts| You
    C <-->|tools, notices, handoffs| A
    subgraph A ["Agents: one confined CLI session each"]
        P[Primary researcher] <-->|spawns, messages, accepts or rejects| S[Subagents]
        P -->|proposes COMPLETE or STOP| R[Reviewer]
        L[Librarian]
    end
    C -->|runs, confined| J[Jobs]
    A -->|notes, code, data| F[("Project folder<br/>(git)")]
    C -->|commits| F
```

Agents run on agent CLIs (Codex and Claude Code today), each in a persistent
session inside its own `bwrap` confinement. A deterministic controller makes every
operational decision:
- it keeps an agent's session while it waits, and hands it off to a fresh session at 55% context, measured
  from the CLI's own reports, or after 58 idle minutes;
- it pauses a CLI's agents when its usage quota runs low;
- it runs long jobs, confined too, that survive handoffs and restarts;
- it notices agents that stop working and tells whoever can act;
- it commits the project to git at every significant event.

## Requirements

- Linux with [bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`), git and Python 3.11+.
  bwrap must also be **allowed to create user namespaces**, which Ubuntu 23.10 and later forbid
  through AppArmor until bwrap has a profile: see [docs/CONFINEMENT.md](docs/CONFINEMENT.md), "What
  the machine must allow". A CLI greyed with "bubblewrap cannot confine sessions on this machine"
  needs that fix.
- [uv](https://docs.astral.sh/uv/).
- At least one agent CLI, installed and logged in: [Codex](https://github.com/openai/codex) (`codex`)
  and/or [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`).
- For the reports: a LaTeX installation with `latexmk` (without it, no report is written).
- SSH access to the private repository `OtiDioti/agent_toolkit`, which `uv sync` installs as a dependency, at the
  release tag pinned in `pyproject.toml`.

## Install

```bash
git clone git@github.com:OtiDioti/research_pipeline.git
cd research_pipeline
uv sync                     # creates .venv with the research-pipeline command
uv tool install -e .        # optional: research-pipeline on your PATH
```

## Prepare a project

You can start from any folder, even one that does not exist yet: the web app's
setup page helps you add your material (and remove what you added by mistake),
place it in `starting_evidence/` and write the objectives, by hand or with the help
of a setup assistant ([docs/SETUP.md](docs/SETUP.md)). With `--no-web`, prepare it
yourself.

A project is a folder (not under `/tmp`) containing at least the first phase's
objectives:

```text
my-project/
├── AGENTS.md                         optional instructions, given to every agent
├── starting_evidence/                material shared by every phase
│   ├── FOLDER_CONTENT.md             one line describing each entry here
│   ├── ...                           papers, notes, data
│   └── tools/                        optional tools of yours
└── phases/
    └── 1/
        └── OBJECTIVES.md             the phase's authoritative objectives: questions or tasks
```

Before the first run nothing else may sit at the top level, and
`starting_evidence/FOLDER_CONTENT.md` must describe every entry at its top. The
controller creates the rest of the layout (PROJECT.md §2) and a git
repository on the first run. A project made before the library (with `sources/`
or `tools/` at its top level) is refused: start a new one. Agents can read everything except the controller's
`.research/` folder, and write only their own folder (`phases/<N>/agents/<id>/`). Only a
phase's primary writes its `STATUS.md` and `RESULT.md`; only its Reviewer writes its `reviews/`;
only the Librarian writes the pages of `library/`, through the controller.

The investigation runs in **phases**, one folder each under `phases/`, each with its
own objectives, primary, Reviewer and subagents. One phase runs at a time. On the web
page you can start a new phase (a fresh primary, for a new direction, optionally
building on an earlier phase), continue an earlier one, and talk with any phase's
primary and Reviewer while another runs; `starting_evidence/`, `AGENTS.md`, the
library and the Librarian are shared ([docs/WEB.md](docs/WEB.md)).

When a subagent is accepted or cancelled, and at a phase's end for its primary and
Reviewer, its folder is **shelved**: catalogued (indexed in `library/CATALOG.md`, its files listed in `library/catalog/`) and frozen
in place (nothing moves, so every path stays valid). The Librarian then links the
work from its pages, starting at `library/LIBRARY.md`, organised for you: what was
established or built in each phase and for each objective, how, and with which tools
([docs/LIBRARY.md](docs/LIBRARY.md)). `starting_evidence/` is yours
alone: agents and their jobs can only read it, so your tools there should write
their output to a path they are given, never next to themselves.

Agents and jobs can reach remote machines, such as a computing cluster, over SSH
with your keys. Describe the machine and its rules in a file in
`starting_evidence/`, point to it from `AGENTS.md`, and never write passwords
there. See [SSH and remote machines](docs/CONFINEMENT.md#ssh-and-remote-machines).

To run the benchmark, copy `research_example/` somewhere outside this repository
first, so that the investigation's git history stays separate from the code's.

## Run

```bash
research-pipeline run
```

opens the web app in your browser, on the projects of this machine: pick one in the
sidebar, or create one (*+ New project*) or add a folder (*+ Open folder*). A new
project's setup page helps you get the folder ready and offers every option below,
then Start shows the investigation as a live graph. One project works at a time. The
terminal prints the transcripts. `research-pipeline run my-project` also adds that
folder and shows it at once. Without the page:

```bash
research-pipeline run my-project --no-web --primary codex:gpt-6.1-sol:high --reviewer claude:opus:high \
    --librarian claude:opus:high --max-agents 4
```

The options below concern one project, so they need `PROJECT` (except `--web-port`
and `--web-no-open`); on the page each project's are set on its setup page.

| Option | Meaning (default) |
|---|---|
| `--primary`, `--reviewer`, `--librarian` | CLI, model and effort as `BACKEND:MODEL:EFFORT` (chosen on the setup page; all three required on the first run with `--no-web`) |
| `--setup` | the setup assistant's `BACKEND:MODEL:EFFORT` (`codex:gpt-6.1-sol:high`; also on the page) |
| `--writer` | the Writer's `BACKEND:MODEL:EFFORT`, which writes the reports for you and checks them (`claude:claude-opus-5-5:high`; also on the page) |
| `--backends` | CLIs agents may choose for subagents (those of the primary and Reviewer) |
| `--max-agents` | agent sessions open at the same time, idle ones included, the Librarian's aside (6, at least 2); a spawn beyond it is refused |
| `--reference PATH` | another project, as unverified evidence; the primary is told about it (repeatable) |
| `--short-limit`, `--weekly-limit` | % left of a CLI's short or weekly usage window that pauses its agents (15) |
| `--context-threshold` | context fill that triggers a handoff (0.55, at most 0.8); keep it well above a fresh session's own start-up context |
| `--idle-limit MINUTES` | minutes an idle session waits before it saves its handoff and closes (58, inside the prompt cache's hour; 0: never) |
| `--no-durable-state` | write the controller's state without forcing it to disk (for slow network filesystems) |
| `--tui` | show the project in the terminal app instead of printing the transcripts |
| `--no-web` | no web app (the folder must be ready already) |
| `--start`, `--web-port PORT`, `--web-no-open` | start (or resume) the project at once; the page's port; print its address instead of opening the browser (see [docs/WEB.md](docs/WEB.md)) |

The models the agents' prompt recommends for subagents (coding: `claude:claude-opus-5-5:xhigh`, analysis:
`codex:gpt-6.1-sol:xhigh`) are set on the setup page, at every launch.

On the page, a paused, shut down or interrupted project is shown as it was left, with
*Resume phase N* (with `--no-web`, running the same command again resumes its latest
phase). After a phase's COMPLETE or STOP its project stays open: you can still talk
with its primary and Reviewer about their work, talk-only, until you close it. Turn on
*Allow edits* in the chat with a primary to let it change its own files, e.g. to make a new
plot in its folder; what it changes is committed after each answer. To reopen it, press *Prepare reopening* on the
web page: change its objectives there (by hand, or with the reopening assistant,
which can grill you and revise them), then press Reopen, without leaving the page.
Only a change of the phase's OBJECTIVES.md reopens it. With `--no-web`, a later `run`
reopens the latest phase if you changed its objectives
([docs/FINISHING.md](docs/FINISHING.md)). Or start a new phase from the page's sidebar.
Options given again replace the stored ones. `research-pipeline status my-project`
prints the phases and the latest one's state without starting anything.

### Statistics

The page's *Stats* button replaces the graph with how the run went: library use,
whether work was split into parallel subagents or passed down chains, which links of
their briefs children opened and which of their parent's files they read without
being given them, what parents read and ran of their children's work before deciding,
and resources, as charts and tables, live and compared with other projects.
`research-pipeline stats my-project [--phase N|all]` prints the key numbers
([docs/STATS.md](docs/STATS.md)). Both only read: nothing is computed by a model.

### The terminal app

With `--tui`, the app shows the transcript, the agent tree (status, CLI, context fill, latest
activity), the usage quota and a chat box. Lines marked ALERT need you, for
example when the primary has stopped and waits for your answer.

| Control | Effect |
|---|---|
| Chat box, Enter | Message to the primary researcher, delivered during its turn (during a review or a pause it answers you, talk-only) |
| Ctrl+P | Pause: agents at work finish their current step and wait in their sessions; jobs stop. Edit any file, then Ctrl+P again to resume in the same sessions |
| Ctrl+R | Resume agents held by a weekly or unreadable quota, or failed agents no longer retried automatically (jobs keep running) |
| Ctrl+Q / F10 | Exit cleanly (also while paused): every agent saves its handoff, jobs keep running; the next `run` resumes and reattaches them |
| F2 / F3 | Show one agent's transcript / all agents |
| Ctrl+C | Exit at once; jobs keep running, and the next `run` restarts agents from their handoffs |

### The web app

The page first helps you make the folder ready, before the first
start (material, objectives, an optional setup assistant: [docs/SETUP.md](docs/SETUP.md)),
then shows every option as a setup form (Start begins the investigation), then the phases in a sidebar and the
selected phase's agent tree as a graph (live for the phase that runs): every agent that ever worked,
coloured by status, with its context use, its messages (coloured by sender) and
tool calls, its documents, jobs and the websites it used. Single agents can be
messaged, paused and resumed, sent to a fresh session, or cancelled; the handoff
threshold, usage limits, number of sessions, idle limit, the CLI choices and the recommended models can be changed while it runs. See
[docs/WEB.md](docs/WEB.md).

You may edit your own files (a phase's `OBJECTIVES.md`, `AGENTS.md`, starting
evidence) at any time: the primary is told which files changed, and a new
`AGENTS.md` reaches every agent at its next session. Put corrections and
constraints in the objectives (their *Constraints*), one-off remarks in a message,
and standing instructions in `AGENTS.md`; there is no FEEDBACK.md. Edit agent-written files only while
paused or shut down: when the investigation resumes, the agents concerned are told
what changed meanwhile (by you, or by jobs that kept running).

## How an investigation runs

- **Agents and subagents.** An agent spawns a subagent by writing a brief and
  calling `spawn` with the subagent's CLI, model and effort. It is told when the
  subagent submits `RESULT.md`, and then accepts the result, or rejects it with
  feedback (the subagent continues). Meanwhile the parent keeps doing whatever does
  not depend on the subagent, and ends its turn only when nothing useful remains.
  A parent and its subagents can message each other at any time. Subagents can
  spawn their own.
- **Instructions.** Every agent's instructions come from the controller alone:
  its role prompt and your `AGENTS.md`. The CLIs load nothing of your own setup
  (personal instruction files, skills, plugins, MCP servers); your own use of the
  CLIs is unaffected. If a CLI reports having loaded some of it anyway, the session
  does not start and you are told what to remove; then press Ctrl+R.
- **Handoffs.** At the context threshold an agent is asked, during its turn, to
  update `HANDOFF.md` and end the turn; a fresh session continues from it. The
  request repeats every further 25 points of context. Agents are never killed for
  overshooting. Context use comes only from each CLI's own reports; until a
  session's CLI has reported it, it shows as unknown and triggers nothing; if it is
  still unknown after the session's first turn, you get an ALERT.
- **Waiting keeps the session.** An agent waiting for a review, a verdict, its
  parent's decision, a pause or a quota hold keeps its session and context. A
  session idle for `--idle-limit` minutes updates `HANDOFF.md` and closes; the
  agent's next input starts a fresh session from it. Idle sessions count against
  `--max-agents` until they close.
- **Idle and stalled agents.** An agent that ends its turn with nothing running or
  pending is reminded once. If it ends its turn idle again, it has stalled: a
  subagent's parent is told (and may message it or cancel it), you are alerted for
  the primary and for the Librarian (idle only while shelving requests are pending),
  and a stalled Reviewer's round is withdrawn.
- **Jobs.** `run_job(command, timeout_seconds)` runs a computation outside the
  agent's session, in its own confinement (`starting_evidence/`, `library/` and
  shelved folders read-only, `.research/` hidden), with its output in
  `phases/<N>/agents/<id>/jobs/`. The owner is told
  when it ends.
- **Finishing.**
  - COMPLETE: the primary writes its phase's `RESULT.md` and its `HANDOFF.md` and calls `complete`.
    It then waits in its session, talk-only, while the Reviewer examines the work as
    committed at the proposal and writes a review to its phase's `reviews/`. COMPLETE stands
    only if the Reviewer agrees; otherwise the review reaches the primary in the
    same session, and it continues or stops.
  - STOP: the Reviewer first challenges the primary's reasons, then the primary
    decides.
  - At the end, the Librarian places the primary's and the Reviewer's work (unless
    it cannot run: then at the next `run`), and the program stays open for talks
    with the primary and the Reviewer until you quit.
- **Reports.** The agents write their results for each other; the Writer writes the
  reports you read: a PDF per phase in `reports/phase-<N>/` (once a phase ends, and on
  request from the web page) and the project's in `reports/project/`, following your
  `WRITING.md` (created from the built-in rules) and your documents' notation. A fresh
  checker compares each report with the work; the Writer corrects it, for up to three
  checks, and what is left is shown to you. You talk with the Writer from its node in
  the graph. See [docs/WRITER.md](docs/WRITER.md).
- **Quota.**
  - A CLI's short window at 15% or less left: its agents update their handoffs and
    wait in their sessions until the reset.
  - A weekly window at 15% or less left, or quota that can't be read twice in a row: its
    agents pause until you resume them (Ctrl+R, or Resume when nothing is working).
  - Only the held CLI's agents pause, whichever CLI the primary uses. Jobs keep
    running through quota pauses.
- **Failures.** If a session crashes or a turn fails (for example, an API outage), the
  agent restarts from its handoff after 30 s, 2 min and 10 min; after that, Ctrl+R retries it.

Controller state and session logs are in `.research/` (not committed, and hidden
from agents and jobs).

## Development

```bash
uv run python -m unittest discover -s tests -t .     # unit and integration tests (no model usage)
uv run python -m tests.live_smoke                     # live run through the real CLIs (uses quota)
```

The web app's live checks (the page driven in Chrome against real sessions) are in
agent_toolkit's `web-ui/live/` (`node live/research.cjs`, `node live/alongside.cjs`).

The code is in `src/research_pipeline/`; [FOLDER_CONTENT.md](src/research_pipeline/FOLDER_CONTENT.md)
describes each module. Everything specific to one agent CLI (the drivers, the
confinement, the quota probes) lives in the shared package `agent_toolkit`, together
with the machinery research_pipeline shares with coding_pipeline and project_manager:
the handoff rules, the usage guard, durable records, the safe git runner, strict prompt
files and the terminal app. A new CLI is one driver there, and research_pipeline needs
no change. To work on both at
once, point `[tool.uv.sources]` in `pyproject.toml` at a local checkout
(`agent-toolkit = { path = "../agent_toolkit", editable = true }`).
