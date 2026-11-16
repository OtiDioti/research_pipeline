# Research Pipeline

An autonomous research investigator. You give it research questions, starting
evidence and tools; a **primary researcher** agent leads the investigation, spawns
**subagents** for subproblems, runs computations and writes what it learns into an
ordinary project folder. When it judges the work done it proposes **COMPLETE**,
which an independent **Reviewer** must agree with, or **STOP**. You judge the
science. The specification is [PROJECT.md](PROJECT.md).

```mermaid
flowchart LR
    You([You]) -->|questions, evidence, messages, Pause| C{{"Controller<br/>(deterministic)"}}
    C -->|transcript and status| You
    C <-->|tools, notices, handoffs| A
    subgraph A ["Agents: one confined CLI session each"]
        P[Primary researcher] -->|spawns, accepts or rejects| S[Subagents]
        P -->|proposes COMPLETE or STOP| R[Reviewer]
    end
    C -->|runs| J[Jobs]
    A -->|notes, code, data| F[("Project folder<br/>(git)")]
    C -->|commits| F
```

Agents run on agent CLIs (Codex and Claude Code today), each in a persistent
session inside its own `bwrap` confinement. A deterministic controller makes every
operational decision:
- it hands an agent off to a fresh session at 55% context;
- it pauses a CLI's agents when its usage quota runs low;
- it runs long jobs that survive handoffs;
- it commits the project to git at every significant event.

## Requirements

- Linux with [bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`), git and Python 3.11+.
- [uv](https://docs.astral.sh/uv/).
- At least one agent CLI, installed and logged in: [Codex](https://github.com/openai/codex) (`codex`)
  and/or [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`).

## Install

```bash
git clone git@github.com:OtiDioti/research_pipeline.git
cd research_pipeline
uv sync                     # creates .venv with the research-pipeline command
uv tool install -e .        # optional: research-pipeline on your PATH
```

## Prepare a project

A project is a folder (not under `/tmp`) containing at least the questions:

```text
my-project/
├── AGENTS.md                         optional instructions for the agents
└── starting_evidence/
    ├── RESEARCH_QUESTIONS.md         the authoritative questions
    ├── ...                           papers, notes, data
    └── tools/                        optional tools of yours
```

The controller creates the rest of the layout (PROJECT.md §2) and a git
repository on the first run. Agents can read everything but write only their own
`agents/<id>/` folder and the shared `sources/` and `tools/`. Only the primary
writes `STATUS.md` and `REPORT.md`; only the Reviewer writes `reviews/`.
`starting_evidence/` is never writable by agents.

To run the benchmark, copy `research_example/` somewhere outside this repository
first, so that the investigation's git history stays separate from the code's.

## Run

```bash
research-pipeline run my-project --primary codex --reviewer claude:opus --max-agents 4
```

| Option | Meaning (default) |
|---|---|
| `--primary`, `--reviewer` | CLI as `BACKEND[:MODEL[:EFFORT]]` (`codex`) |
| `--backends` | CLIs agents may choose for subagents (those of the primary and Reviewer) |
| `--max-agents` | agents working at the same time (4); a spawn beyond it is refused |
| `--reference PATH` | another project agents may read, as unverified evidence (repeatable) |
| `--short-limit`, `--weekly-limit` | % left of a CLI's short or weekly usage window that pauses its agents (15) |
| `--context-threshold` | context fill that triggers a handoff (0.55); keep it well above a fresh session's own start-up context |
| `--no-tui` | print the transcript instead of the terminal app |

Running the same command again resumes a paused or interrupted investigation, or
reopens a finished one. Options given again replace the stored ones.
`research-pipeline status my-project` prints the state without starting anything.

### The terminal app

The app shows the transcript, the agent tree (status, CLI, context fill, latest
activity), the usage quota and a chat box.

| Control | Effect |
|---|---|
| Chat box, Enter | Message to the primary researcher, delivered during its turn |
| Ctrl+P | Pause: every agent hands off, then jobs stop. Edit any file, then Ctrl+P again to resume |
| Ctrl+R | Resume agents held by a weekly or unreadable quota, or whose automatic retries ran out (jobs keep running) |
| Ctrl+Q / F10 | Pause cleanly, then exit; the next `run` resumes |
| F2 / F3 | Show one agent's transcript / all agents |
| Ctrl+C | Exit at once; the next `run` restarts agents from their handoffs |

You may edit your own files (`RESEARCH_QUESTIONS.md`, `AGENTS.md`, `FEEDBACK.md`,
starting evidence) at any time: the primary is told. Edit agent-written files
only while paused: on resume, the agents concerned are told what you changed.

## How an investigation runs

- **Agents and subagents.** An agent spawns a subagent by writing a brief and
  calling `spawn`. It is told when the subagent submits `RESULT.md`, and then
  accepts the result, or rejects it with feedback (the subagent continues).
  Subagents can spawn their own.
- **Handoffs.** At the context threshold an agent is asked, during its turn, to
  update `HANDOFF.md` and end the turn; a fresh session continues from it. The
  request repeats every further 25 points of context. Agents are never killed for
  overshooting. Context use comes only from each CLI's own reports; until a
  session's CLI has reported it, it shows as unknown and triggers nothing.
- **Jobs.** `run_job(command, timeout_seconds)` runs a computation outside the
  agent's session, with its output in `agents/<id>/jobs/`. The owner is told when
  it ends.
- **Finishing.**
  - COMPLETE: the primary writes `REPORT.md` and calls `complete`. The Reviewer
    examines the work and writes a review to `reviews/`. COMPLETE stands only if
    the Reviewer agrees; otherwise the primary continues or stops.
  - STOP: the Reviewer first challenges the primary's reasons, then the primary
    decides.
- **Quota.**
  - A CLI's short window at 15% or less left: its agents hand off and pause until
    the reset.
  - A weekly window at 15% or less left, or quota that can't be read: its agents
    pause until you resume them (Ctrl+R, or Resume when nothing is working).
  - If the primary's CLI is affected, everyone pauses. Jobs keep running through
    quota pauses.

- **Failures.** If a session crashes or a turn fails (for example, an API outage), the
  agent restarts from its handoff after 30 s, 2 min and 10 min; after that, Ctrl+R retries it.

Controller state and session logs are in `.research/` (not committed).

## Development

```bash
uv run python -m unittest discover -s tests -t .     # unit and integration tests (no model usage)
uv run python -m tests.live_smoke                     # live run through the real CLIs (uses quota)
```

The code is in `src/research_pipeline/`; [FOLDER_CONTENT.md](src/research_pipeline/FOLDER_CONTENT.md)
describes each module. To support another agent CLI, write one session driver in
`drivers/` (four hooks: `command`, `begin`, `deliver`, `receive`), register it in
`drivers/__init__.py`, and optionally add its usage probe to `quota.py`.
Everything else (confinement, tools, handoffs, jobs, quota policy) is shared.
