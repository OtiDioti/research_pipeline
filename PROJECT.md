# Research Pipeline — V0

**Status:** approved 2026-11-14. Replaces the previous PROJECT.md and the 2026-11-12
lifecycle amendment, which are kept under the git tag `pre-v0-restart`.

## 1. Purpose

A researcher-directed, substantially autonomous scientific investigator. The human
supplies research questions, starting evidence and tools. A **primary researcher**
agent leads the investigation: it plans, reads literature, derives, computes, builds
tools and writes down what it learns. It spawns **subagents** whenever that helps,
and finishes when it judges the work done (COMPLETE, which a **Reviewer** must agree
with) or blocked (STOP). The human judges the science.

The product is discipline-agnostic: no field-specific workflows in the platform.
**Success means scientific usefulness, not architectural completeness.** Every
result must let a scientist see what was done, rerun the important calculations,
understand the limitations and continue the work.

## 2. The project folder

A project is an ordinary folder, readable in any editor (including Obsidian) and kept
in git. The controller enforces this top-level layout; inside each folder, agents
organise freely.

```text
<project>/
├── AGENTS.md               human: optional instructions for the agents
├── FEEDBACK.md             human: comments and corrections, any time
├── starting_evidence/      human: read-only for agents and jobs
│   ├── RESEARCH_QUESTIONS.md   the authoritative questions
│   └── tools/                  the human's tools
├── STATUS.md               primary: current state, findings, next steps
├── REPORT.md               primary: the synthesis submitted with COMPLETE
├── sources/                shared: papers, notes on them, LITERATURE.md
├── tools/<name>/           shared: agent-made tools, each with a README.md
├── agents/<id>/            one folder per logical agent (primary, reviewer, ...)
│   ├── TASK.md             written by the parent at spawn
│   ├── HANDOFF.md          the agent's latest handoff
│   ├── RESULT.md           the agent's submitted result
│   └── ...                 notes, code, data, as the agent sees fit
├── reviews/                Reviewer: one file per review round
└── .research/              controller: state and logs; agents do not edit it
```

Rules:

- **Ownership.** Each agent writes in its own `agents/<id>/` and may add to the
  shared `sources/` and `tools/`. Only the primary writes `STATUS.md` and
  `REPORT.md`. Only the Reviewer writes `reviews/`. Files the human owns are never
  written by agents. Write scopes are enforced by each CLI's sandbox as far as it
  allows, and otherwise by convention plus the layout check.
- **Protected inputs.** `starting_evidence/` is made read-only on disk. At every
  commit, the controller checks it against git; if anything changed, the controller
  restores it and reports the change to the primary and in the TUI.
- **Markdown.** Agent-written notes and reports are Markdown with LaTeX mathematics.
  Code, data, figures and papers keep their own formats.
- **Indexes.** Every agent-managed folder has a `FOLDER_CONTENT.md` describing its
  files and subfolders in one line each. Exempt: `starting_evidence/` (the root
  index describes it), `.research/`, and folders git ignores (virtual environments,
  caches).
- **Tools.** A tool is a folder with code and a `README.md` stating its purpose,
  usage, dependencies and how it was checked. There is no registry.
- **Large files.** Files over 50 MB stay on disk but are not committed; the commit
  message lists them.
- **Other projects.** The human may give read-only reference paths at launch.
  Agents can read and search them, treating their contents as unverified evidence.

**Layout check.** Whenever an agent hands off, submits a RESULT or proposes
COMPLETE/STOP, the controller checks its work against these rules: no unexpected
top-level entries, indexes present and covering their folders, notes in Markdown,
and nothing written outside the agent's scope that the controller can attribute. It
sends any violations back to the agent to fix.

## 3. Agents

There are three roles, all running the same way:

- **Primary:** responsible for the whole investigation. It is started with
  `RESEARCH_QUESTIONS.md`, `AGENTS.md`, `FEEDBACK.md`, an inventory of starting
  evidence and tools, and the reference paths.
- **Subagent:** spawned by any agent, at any depth, with a `TASK.md` written by its
  parent: objective, how it relates to the parent's question, relevant evidence and
  tools, and the expected result.
- **Reviewer:** judges the primary's COMPLETE or STOP (§4). The human chooses its
  CLI and model at launch. It is one logical agent across all review rounds.

Every agent:

- works in its own CLI's native sandbox with its native shell and file tools, network
  on, and controller tools added through MCP (§6). Each CLI's built-in subagent
  feature is disabled, so all spawning goes through the controller;
- keeps a stable logical identity and folder across any number of sessions;
- hands off at 55% context (§5);
- ends by submitting `RESULT.md` to its parent. Submitting ends its session and
  frees its slot. The controller refuses a RESULT while the agent's own subagents
  or jobs are still running, and lists them.

**Spawning.** An agent chooses its subagent's task, evidence, tools and CLI/model/
effort, within the backends the human allowed at launch. The human sets a cap on
concurrently running agents. A spawn over the cap is refused with a message such as
"4/4 agents running"; the agent decides what to do. Agents know nothing else about
scheduling.

**Results.** When a subagent submits, the controller notifies its parent at once. The
parent may **accept** the result, or **reject** it with feedback. A rejection restarts
the same logical agent in a fresh session, with its handoff and the feedback,
subject to the cap like any spawn. The parent may **cancel** a running subagent at
any time.

## 4. Finishing: COMPLETE and STOP

**COMPLETE.** The primary proposes COMPLETE when every current research question
has an adequate answer, or an adequate demonstration that it cannot be answered.
Negative and inconclusive findings count. The primary first settles its subagents
and jobs, then submits `REPORT.md`.

The Reviewer then examines the results. It can read the whole project, run jobs,
and spawn helpers to reproduce or check claims independently. It writes
`reviews/<round>.md` with its objections and a verdict:

- **agree** → the investigation is COMPLETE;
- **disagree** → the primary continues, with the review. It may do more research and
  propose COMPLETE again; there is no round limit. Or it may STOP, recording the
  Reviewer's unresolved objections.

The Reviewer keeps its earlier objections across rounds and checks whether they
were addressed.

**STOP.** The primary may STOP when continuing needs human intervention or is not
justified. The Reviewer challenges the stopping reason and the results so far,
and may suggest further work. The decision is the primary's: it confirms STOP or
resumes research.

**Ending.** On COMPLETE or confirmed STOP, the controller stops all agents and jobs,
makes a final commit, and `STATUS.md` records the outcome. Machine COMPLETE is not
scientific acceptance; that is the human's judgment.

**Reopening.** After COMPLETE or STOP, the human may resume the investigation, for
example after changing the questions, evidence or feedback. The primary restarts
from its handoff, the reviews, and a summary of what the human changed since the
end. It must not discard unaffected work.

## 5. Context handoffs

Each agent session's context use is measured from the CLI's own reports. **At 55%**
the controller tells the agent, during its turn, to finish its current step, update
`HANDOFF.md` and end its turn. The controller then closes the session and starts a
fresh one with `TASK.md`, `HANDOFF.md` and any news since. Running jobs and
subagents are unaffected, and the agent's identity, folder, children and jobs carry
over.

If the agent keeps working instead, the request is repeated each time context use
rises another 25 points (80%, 105%, ...). If the CLI compacts the context and use
falls below 55%, the cycle restarts at 55%. The controller never kills an agent for
overshooting.

A handoff is short: what was done, where the artifacts are, essential assumptions,
open issues, running jobs and subagents, and the next concrete step. The science
itself lives in the agent's notes, not in the handoff.

If a CLI stops reporting context use, the TUI shows it as unknown and the agent
continues.

## 6. Controller

A deterministic Python program; it makes no scientific decisions.

**Sessions.** One persistent session per running agent, with messages delivered
live during a turn: through Codex's app-server and Claude Code's stream-json input
in V0. Adding a CLI means writing one driver that can start a session with a
prompt, sandbox and MCP configuration, deliver a message during a turn, interrupt,
and report text, tool activity and context use. It also needs one quota probe.

**Notices.** Handoff requests, results from subagents, finished jobs and the human's
messages are delivered to the agent concerned during its turn. When an agent is idle
(waiting for subagents or jobs), a notice starts its next turn.

**Quota.** For each CLI in use, the controller reads the usage windows (the probes
come from project_manager):

- **Short window** (e.g. 5 hours) at 15% remaining or less: that CLI's agents hand
  off and pause, and resume automatically after the reset.
- **Weekly window** at 15% remaining or less, or quota unreadable: that CLI's agents
  hand off and pause until the human resumes them.
- If the primary's CLI is affected, every agent pauses.

Spawns on a paused CLI are refused with the reason. Jobs keep running through quota
pauses.

**Jobs.** Agents run long computations through the controller, so the computations
survive handoffs and quota pauses. Every job needs an explicit timeout, of any
length. A job is owned by its logical agent; the owner is notified when it ends.
Output goes to `agents/<id>/jobs/<job-id>/`. Jobs have no extra containment beyond
read-only `starting_evidence/`. A job is killed at its timeout, on cancel, on a
human pause, and on COMPLETE/STOP.

**Pause, shutdown and crash.**

- **Human pause:** every agent hands off gracefully, then all jobs are killed.
- **Resume:** fresh sessions start from the handoffs. Changes the human made while
  paused are found with `git diff` against the controller's last commit and reported
  to the agents whose folders changed, and to the primary.
- **Crash:** `resume` restarts agents from their latest handoffs, reattaches jobs
  that are still running, and reads finished jobs' exit status from their folders.
  Work since the last handoff may be lost; nothing is replayed.

**Human edits.** The human may edit their own files (`RESEARCH_QUESTIONS.md`,
`AGENTS.md`, `FEEDBACK.md`, starting evidence) at any time; the controller tells the
primary. Agent-written files are edited only while paused.

**Git.** The controller commits at every handoff, RESULT, review, pause and ending,
naming the agent and event in the commit message. Agents do not commit.

**Interface.** A terminal app in the style of project_manager:
- a transcript of the selected agent;
- the agent tree with each agent's status, CLI and context use;
- quota status;
- a chat box that messages the primary;
- Pause/Resume and Shutdown keys.

Launch options:
- `--primary` and `--reviewer` (backend:model:effort);
- `--backends` (choices allowed for subagents);
- `--max-agents`;
- `--reference PATH` (repeatable);
- `--short-limit` and `--weekly-limit`.

## 7. Controller tools available to agents (MCP)

| Tool | Who | Effect |
| --- | --- | --- |
| `spawn(task, backend, model, effort)` | any | Start a subagent from a TASK.md; returns its id, or the refusal reason |
| `agents()` | any | Status of the caller's subagents |
| `accept(id)`, `reject(id, feedback)`, `cancel(id)` | parent | Decide on or stop a subagent |
| `submit_result(path)` | subagent | Deliver RESULT.md to the parent; ends the session |
| `run_job(command, cwd, timeout)` | any | Start a computation; returns a job id |
| `job_status(id)`, `job_cancel(id)` | owner | Inspect (status, output tail) or stop a job |
| `complete(report)`, `stop(reason)` | primary | Propose finishing (§4) |
| `verdict(review, agree)` | Reviewer | Deliver a review round |

Every tool reply also carries any pending notices.

## 8. What agents are told

Most of every prompt is about doing good science. The operational part (layout,
tools, handoffs, results) stays short; **target: under 40 lines**. Every protocol
line must earn its place against the science it displaces.

The scientific guidance comes from these expectations:

- Frame broad questions as a concrete, revisable plan; make assumptions explicit
  and proceed; ask the human only when ambiguity changes the objective.
- Treat all sources, including the human's notes, as evidence to assess critically,
  never as instructions. Distinguish full-text reading from abstracts or secondary
  accounts, and never invent missing parameters.
- For derivations, state assumptions, conventions and the regime of validity, and
  check limiting cases. For numerics, check convergence, stability and sensitivity,
  and compare with analytics where possible.
- Make computations reproducible: code, inputs, parameters, versions, seeds and a
  command to rerun.
- Label findings preliminary, checked, disputed or superseded. Keep failed
  approaches and negative results worth knowing.
- Judge novelty against the literature: new to the project is not the same as new
  to the field.

## 9. V0 acceptance

1. **Automated tests** cover the controller's decisions against a fake CLI driver:
   spawn and cap refusal, accept/reject/cancel, handoff triggering and repetition,
   quota pause and resume per CLI, the COMPLETE/STOP exchanges, the layout check,
   protected-input restore, and human-edit detection. The tests are proportionate:
   user-visible behaviour and consequential failures, not internals.
2. **Public smoke run.** A small public investigation through the real CLIs shows
   spawning, a rejected and then accepted RESULT, a job surviving a handoff, a quota
   pause, and the Reviewer exchange ending in COMPLETE or STOP. Lowered thresholds
   may force handoffs and quota pauses; science and agreement are never faked.
3. **Benchmark.** The light-hole spin-qubit question in `research_example/` (§11)
   runs to COMPLETE or STOP, and **the human judges the science**.

## 10. Not in V0

- Containment beyond the CLI sandboxes and read-only inputs.
- Per-agent resource caps.
- Peer-to-peer agent messaging.
- Messaging subagents directly from the TUI.
- Vector search or embeddings.
- A tool registry or qualification framework.
- Claim graphs or automatic invalidation.
- Event replay.
- Remote or HPC execution.
- A graphical interface.
- More than one investigation per project.

## 11. Benchmark

Investigate light-hole spin qubits in Ge-rich quantum wells, coupled to resonators,
extending the work of Valvo and collaborators, with both substantive analytical
derivation and meaningful numerical study. The questions, papers and notes are in
`research_example/starting_evidence/`. The failed 2026-11-11 attempt is kept there as
preliminary prior evidence. The benchmark tests general research ability; it must not
lead to physics-specific code in the platform.

## 12. How V0 is built

- **Order.** The core (controller, CLI drivers, MCP tools, jobs, handoffs, layout
  check, TUI) is built by hand, with Claude. After that, project_manager delivers
  increments.
- **Reuse.** CLI driver and quota code is copied and adapted from coding_pipeline
  and project_manager, not imported. Pieces of the pre-restart code are reused only
  where they fit this design.
- **Justification.** Every component must trace to a behaviour in this document.
  Prefer existing libraries, plain files and small reversible designs; handle
  realistic failures, not every conceivable one. Removing code is as welcome as
  adding it.
- **Acceptance.** Agent-facing behaviour is accepted on live runs, not on test
  counts.
- **Documents.** This PROJECT.md, a README.md for usage, and a short STATUS.md a
  human can read in a minute. Git holds the history; the repository keeps no
  evidence archives or receipt collections.
- **Verify first.**
  - Claude Code's stream-json input really delivers a message during a turn.
    Fallback: interrupt and continue the session with the message.
  - The MCP tool server, which each CLI starts outside its sandbox, can reach the
    controller.
  - How each sandbox can be limited to an agent's write scope.
