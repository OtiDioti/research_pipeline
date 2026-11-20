# Research Pipeline — V0

**Status:** approved 2026-11-16; amended 2026-11-18: the Librarian, a library of pages over frozen agent folders (§1–§10), quota holds limited to the held CLI's agents (§6), the web setup of a folder before the first start, with its setup assistant (§2, §3, §6), and talks with the primary and the Reviewer after the end (§4); amended 2026-11-19: reopening from the web page, with the reopening assistant (§4); amended 2026-11-20: phases, each with its own objectives, primary and Reviewer, sharing the library, and FEEDBACK.md removed (§1–§4, §6).

## 1. Purpose

A researcher-directed, substantially autonomous scientific investigator. The human
supplies objectives (research questions to answer or research tasks to perform),
starting evidence and tools. A **primary researcher**
agent leads the investigation: it plans, reads literature, derives, computes, builds
tools and writes down what it learns. It spawns **subagents** whenever that helps,
and finishes when it judges the work done (COMPLETE, which a **Reviewer** must agree
with) or blocked (STOP). The investigation runs in **phases**: each has its own
objectives, primary and Reviewer, and the human can start a new phase (a fresh
primary, for a new direction) or continue an earlier one. A **Librarian** keeps a
library shared by every phase: pages, organised for a human reader, that lead to
the agents' finished work where it was made. The human judges the science.

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
├── AGENTS.md               human: optional instructions, given to every agent of every phase
├── starting_evidence/      human: evidence and tools shared by every phase; read-only for agents and jobs
├── library/                Librarian: Markdown pages leading to the finished work of every phase
│   ├── LIBRARY.md              the entry page: how the library is organised, and its changes
│   ├── CATALOG.md              controller: every shelved file, and work in progress
│   └── ...                     pages and folders of pages, as the Librarian sees fit
├── librarian/              the Librarian's own folder (its HANDOFF.md)
├── phases/                 one folder per phase; FOLDER_CONTENT.md (controller) lists them
│   └── <N>/
│       ├── OBJECTIVES.md       human: the phase's authoritative objectives (questions or tasks)
│       ├── STATUS.md           primary: current state, findings, next steps
│       ├── REPORT.md           primary: the synthesis submitted with COMPLETE
│       ├── agents/<id>/        one folder per logical agent of the phase (primary, reviewer, ...)
│       │   ├── TASK.md             written by the parent at spawn
│       │   ├── HANDOFF.md          the agent's latest handoff
│       │   ├── RESULT.md           the agent's submitted result
│       │   └── ...                 notes, code, data, as the agent sees fit; frozen once shelved
│       └── reviews/            Reviewer: one file per review round
└── .research/              controller: state, logs, removed setup material; hidden from agents and jobs
```

Rules:

- **Ownership.** Each agent writes in its own folder (`phases/<N>/agents/<id>/`; the
  Librarian's is `librarian/`). Only a phase's primary writes its `STATUS.md` and
  `REPORT.md`. Only its Reviewer writes its `reviews/`. Only the Librarian writes `library/`, and only Markdown pages there, through the controller
  (see **The library**). Nobody writes a shelved agent's folder. Files the human
  owns are never written by agents or their jobs.
- **Confinement.** Each agent session runs inside one `bwrap` boundary. The whole
  filesystem is readable except `.research/`, which is hidden. Everything is
  read-only except the agent's own folder, its role's files (its phase's `STATUS.md`,
  `REPORT.md` and `FOLDER_CONTENT.md` for the primary, its phase's `reviews/` for the
  Reviewer) and the CLI's own state folder. The network is on, and `/tmp` is private
  to the session. The CLIs' own sandboxes are switched off. One mechanism serves
  every CLI.
- **Job confinement.** Each job runs inside its own `bwrap` boundary, with its own
  process namespace: `starting_evidence/`, `library/`, the folders of the other
  phases and the folders of shelved agents are read-only, `.research/` is hidden, and the rest of the filesystem is as
  the controller sees it.
- **Protected inputs.** Only the human writes `starting_evidence/`, at any time; it
  is read-only for agents and their jobs. A job's attempt to write there, in
  `library/` or in a shelved agent's folder fails, and its owner sees the error in
  the job-ended notice. The human's tools therefore take an output path and never
  write next to themselves; shelved code that does is copied first (see **The
  library**).
- **Markdown.** Agent-written notes and reports are Markdown with LaTeX mathematics.
  Code, data, figures and papers keep their own formats.
- **Indexes.** Every agent-managed folder has a `FOLDER_CONTENT.md` describing its
  files and subfolders in one line each. Exempt: `starting_evidence/` (the root
  index describes it), `.research/`, and folders git ignores (virtual environments,
  caches).
- **Tools.** A tool is a folder with code and a `README.md` stating its purpose,
  usage, dependencies, how it was checked, and the command that builds its
  environment. Software that agents install from the internet goes into such
  documented environments in their own folders, which agents prefer to software
  installed elsewhere on the machine. Environments are git-ignored: a shelved tool
  carries its recipe, and each agent that uses it builds its own environment in its
  own folder. The library's catalogue is the only registry.
- **Large files.** Files over 50 MB stay on disk but are not committed; the commit
  message lists them.
- **Other projects.** The human may give read-only reference paths at launch. The
  primary is told about them and decides which subagents need them. Agents treat
  their contents as unverified evidence.

**Ready to start.** Before the first start, a folder is a project only with a
non-empty `phases/1/OBJECTIVES.md`, nothing loose at the top level (only
the entries above), and a `starting_evidence/FOLDER_CONTENT.md` describing every
entry at its top. With `--no-web`, a folder that is not ready is refused; otherwise
the setup page makes it ready first (docs/SETUP.md): material added
(uploaded, copied from local paths, or by hand; removed again without loss: an
unchanged copy is deleted, its original kept, anything else set aside in
`.research/removed/` to restore) and placed in `starting_evidence/`
with a one-line description each, by hand or by the setup assistant (§3), and the
objectives written in an editor, optionally drafted by the assistant after it has
grilled the human with multiple-choice questions. Placing is deterministic, checked
whole, and never overwrites. After the first start only each phase's `OBJECTIVES.md`
is required, and strays are reported to the primary.

**Layout check.** Whenever an agent hands off, submits a RESULT, proposes
COMPLETE/STOP, delivers a verdict or reports a shelving done, the controller checks
the folders it may write (its own, plus its phase's folder for the primary, its
phase's `reviews/` for the Reviewer and `library/` for the Librarian): indexes present and covering their
folders, and notes in Markdown. A RESULT, proposal, verdict or shelving is refused
until the problems are fixed; at a handoff, they are passed to the next session to
fix.
Unexpected top-level entries can only come from jobs or the human: they are
reported to the primary and never block anyone.

**Phases.** The investigation runs in numbered phases, one folder each
(`phases/<N>/`), each with its own objectives, primary, Reviewer, subagents,
status, report and reviews. The human's `AGENTS.md` and `starting_evidence/`, the
library and the Librarian are shared by every phase. One phase runs at a time:

- **A new phase** (from the web page) starts a fresh primary and Reviewer on its own
  objectives, with a title, and optionally an earlier phase it builds on, whose
  report and status its primary starts from. Every primary is told of the other
  phases (their folders, outcomes and reports); their folders are read-only for it,
  and their finished work is in the library.
- **An earlier phase can be continued**: a paused one resumes from its handoffs; one
  that ended (COMPLETE or STOP) reopens only on a change of its own `OBJECTIVES.md`
  (§4). Its primary is then told of the phases that ran after it.
- **Switching** to another phase needs the running one paused (its sessions then save
  their handoffs) or ended. While a phase runs, the human can talk with the primary
  and the Reviewer of any other phase that has started (§4).
- The controller keeps the list of phases (title, the phase built on), the phase run
  last, the Librarian and its pending requests in `.research/project.json`, each
  phase's own state in `.research/phases/<N>/state.json`, and the list in
  `phases/FOLDER_CONTENT.md`. Without the web page, `run` runs the latest phase.

**The library.** The agents' finished work stays in the folders where it was made.
`library/` holds the Librarian's (§3) Markdown pages, which lead a human to it:
what was established or built in each phase and for each objective, how, and with
which tools.
Nothing is moved, renamed or deleted for the library, so every path an agent, a
job or a note uses stays valid.

- **Shelving.** When a subagent is accepted or cancelled (each agent of a cancelled
  subtree), and when a phase ends for its primary and its Reviewer (§4),
  the controller shelves the agent's folder:
  - it catalogues every file in it except the git-ignored ones (environments,
    caches), which stay on disk untouched;
  - it freezes the folder: from then on, no agent or job writes it;
  - it asks the Librarian to place the work, giving it the agent's task, result,
    index lines and the commit.
- **Placing.** The Librarian writes its pages with `write_page`. Links are
  relative, and a link to a folder covers everything in it. Once every catalogued
  file of the agent is reachable from a page, it calls `shelved(folder)`, naming the
  agent's folder (agent ids repeat across phases). The
  controller refuses that while any of those files is reachable from no page, or
  while a link in `library/` leads nowhere, and lists them; otherwise it commits.
- **Reorganising.** The Librarian may rewrite its pages at any time, and records
  each change of structure and its reason, dated, in `library/LIBRARY.md`. Only
  pages change, so nothing that agents and jobs use ever moves. At the end of each
  of its turns, the controller commits the pages it changed and tells it of any
  link that leads nowhere.
- **Catalogue.** The controller keeps a catalogue of every shelved file (its path,
  the agent's folder, which agent it is, the commit at shelving and its index line) and renders
  it as `library/CATALOG.md`, together with the work in progress in agents' folders
  (their index lines), refreshed at every commit.
- **Using it.** Agents read and run shelved files in place, writing outputs to
  their own folder. To change a shelved file, or to run code that writes next to
  itself, an agent copies it into its own folder and says where it came from in
  its index. Before solving something or spawning, agents look in `library/`
  (starting from `LIBRARY.md`) and search `CATALOG.md`.
- **Never waiting on it.** Shelving never blocks an agent: the controller catalogues
  and freezes the folder at once, and the pages follow when the Librarian can run.
  Its requests wait while it is paused, held by the quota or stalled, and survive a
  shutdown or a crash.

## 3. Agents

There are four roles, all running the same way, and a setup assistant on the web page:

- **Primary:** responsible for its phase of the investigation. It is started with
  its phase's `OBJECTIVES.md`, the other phases (and the one it builds on), an
  inventory of starting evidence and tools, and the reference paths.
- **Subagent:** spawned by any agent, at any depth, with a `TASK.md` written by its
  parent: objective, how it relates to the parent's objective, relevant evidence and
  tools, and the expected result.
- **Reviewer:** judges the primary's COMPLETE or STOP (§4). The human chooses its
  CLI, model and effort at launch. It is one logical agent per phase, across all its
  review rounds.
- **Librarian:** keeps the pages of `library/` (§2, **The library**), for every phase;
  it is told when a new phase starts. It does no research and never judges the science. The human chooses its CLI, model and
  effort at launch. It is one logical agent, started at its first shelving request;
  between requests it rests. It is not counted against the cap on agent sessions.
- **Setup assistant:** optional, only on the web page, to prepare a phase: the first
  one before the first start, a new one, or the reopening of one that ended
  (docs/SETUP.md), each with its own prompt. It places the human's material and
  drafts the phase's `OBJECTIVES.md` on request (and, for a new or reopened phase,
  rewrites `AGENTS.md` when asked, a fourth tool), asking multiple-choice questions first if asked to, through three tools
  answered by deterministic code (`place`, `write_objectives`, `ask`); it writes
  nothing else but its handoff note. Its CLI, model and effort: `--setup` or the
  page (default `codex:gpt-6.1-sol:high`). It is not part of the investigation.

Every agent:

- works inside its confinement (§2) with its CLI's native shell and file tools, and
  controller tools added through MCP (§6). Each CLI's built-in subagent and
  background-task features are disabled, so spawning and long computations go
  through the controller;
- receives its instructions from the controller only (see **Instructions**);
- keeps a stable logical identity and folder across any number of sessions;
- hands off at 55% context (§5);
- ends by submitting `RESULT.md` to its parent, then waits in its session, its
  tools refused, until the parent decides. The controller refuses a RESULT while
  the agent's own subagents or jobs are still running, and lists them. (The
  primary, the Reviewer and the Librarian finish differently: §4 and §2.)

**Instructions.** Every session receives, as its CLI's system or developer
instructions, the role prompt (§8) and the project's `AGENTS.md`; both stay in force
for the whole session. An edit to `AGENTS.md` reaches each agent at its next
session, and the primary is told at once. In the sessions the controller starts, the
CLIs discover nothing by themselves: no instruction files (the project's or the
human's personal `AGENTS.md` or `CLAUDE.md`), skills, plugins, apps or MCP servers
from the human's own configuration. The human's own use of the CLIs is unaffected.
At every session start the driver checks the CLI's own report of what it loaded; a
session that loaded anything personal is stopped, and the human is told why.

**Spawning.** An agent chooses its subagent's task, evidence, tools, CLI, model and
effort, within the backends the human allowed at launch. Before spawning, it looks
in the library for what the project already has on the subject, and names the
relevant files in the brief. Model and effort are always
explicit: a spawn without them is refused, and so is a launch whose `--primary`,
`--reviewer` or `--librarian` lacks them; an effort the CLI is known not to accept is refused before
any session starts. The role prompt recommends a model for coding tasks (by default
Opus 5.5, `claude:claude-opus-5-5:xhigh`) and one for analytical ones (by default
GPT-6.1 Sol, `codex:gpt-6.1-sol:xhigh`), which the human sets on the setup page at every
launch or while the investigation runs (from each agent's next session); when a
recommended model's backend is not allowed or held by its quota, agents use the best
model they can on an available backend, unless the human's `AGENTS.md` says otherwise. The human sets a cap on open agent sessions, idle
ones included (6 by default, at least 2). A spawn over the cap is refused with a message such as
"6/6 agent sessions are already open"; the agent decides what to do. Agents know nothing else about
scheduling.

**Results.** When a subagent submits, the controller notifies its parent at once. The
parent may **accept** the result, or **reject** it with feedback. The feedback reaches
the subagent in the session it submitted from (or, if that closed at the idle limit,
a fresh session from its handoff, subject to the cap like any spawn). Accepting or
cancelling closes its session and shelves its folder (§2). The parent may
**cancel** a running subagent at any time.

**Messages.** A parent and each of its direct subagents can message each other at
any time. A message is delivered during the recipient's turn, or starts its next turn
if it is waiting or idle; a paused recipient receives it when it continues, and one
without a session when its next session starts. Messages are not stored in
files: what matters belongs in the recipient's notes or `HANDOFF.md`. A subagent
that has submitted its result receives no messages; its parent answers with accept,
reject or cancel. Agents that are not parent and subagent, such as the primary and
the Reviewer, do not message each other; the Librarian neither sends nor receives
messages, and works only from the controller's shelving requests (§2).

**Working while subagents and jobs run.** Starting a subagent or a job does not
stop its parent: the parent keeps doing whatever does not depend on it, and news
about it reaches the parent as it happens, even during a turn. The parent ends its
turn only when nothing useful remains until a subagent or job reports.

**Waiting, idle and stalled agents.** An agent that ends its turn is *waiting* while
it has a running or paused subagent or a running job, or, for the primary, a
proposal under review; the next notice wakes it. Otherwise it is *idle*: the
controller tells it once to continue or finish, naming any subagent result that
awaits its decision. If it ends its turn idle again without having used a tool, it
is *stalled*:

- a stalled subagent keeps its session, and its parent is told, with the
  subagent's last message; the parent may message it or cancel it;
- a stalled primary keeps its session, and the human is alerted with its last
  message; the human's reply continues that session;
- for a stalled Reviewer, the proposal under review is withdrawn and the
  Reviewer rests; the primary is told why, and may continue, propose again or stop;
- the Librarian is idle only while a shelving request is pending; otherwise, ending
  its turn means it rests. A stalled Librarian keeps its session, and the human is
  alerted with its last message; its requests wait, and the work stays catalogued
  and frozen in its folders meanwhile.

## 4. Finishing: COMPLETE and STOP

**COMPLETE.** The primary proposes COMPLETE when every current objective is met
(a question answered; a task's deliverable built, verified and documented) or
adequately shown infeasible.
Negative and inconclusive findings count. The primary first settles its subagents
and jobs and updates `HANDOFF.md`, then submits its phase's `REPORT.md`.

The Reviewer then examines the results, as committed at the proposal. It can read the whole project, run jobs,
and spawn helpers to reproduce or check claims independently. It writes
`phases/<N>/reviews/<round>.md` with its objections and a verdict:

- **agree** → the phase is COMPLETE;
- **disagree** → the primary continues, with the review. It may do more research and
  propose COMPLETE again; there is no round limit. Or it may STOP, recording the
  Reviewer's unresolved objections.

The Reviewer keeps its earlier objections across rounds and checks whether they
were addressed.

**STOP.** The primary may STOP only when its objectives cannot be achieved:
continuing needs human intervention or is not justified. The Reviewer challenges the stopping reason and the results so far,
and may suggest further work. The decision is the primary's: it confirms STOP or
resumes research.

**During review.** The proposal records its commit, and the Reviewer judges the
project as of that commit. The primary waits in its session, talk-only: it answers
the human, but its `spawn` and `run_job` calls are refused until the verdict. The
verdict arrives in the same session and lists the files changed since the proposal's
commit (outside the phase's `reviews/`, `library/` and the folders of the Reviewer
and the Librarian), which the review does not cover. The Reviewer keeps its session across
rounds. If the Reviewer stalls, the proposal is withdrawn (§3). The Librarian's
pages may change during a review: they move nothing the review examines.

**Ending.** On COMPLETE or confirmed STOP, the controller stops all agents and jobs
except the Librarian, records the outcome in the phase's `STATUS.md`, commits, and shelves the
folders of the primary and the Reviewer. The Librarian places their work and any
still pending; then the controller makes a final commit and stays open for talks
until the human quits. If the Librarian cannot run, or stalls, its pending requests
reach it at the controller's next run: the work is catalogued already. Machine
COMPLETE is not scientific acceptance; that is the human's judgment.

**Talks.** After a phase's end the human can still talk with its primary (chat box
or web page) and its Reviewer (web page), talk-only; on the web page, also with the
primary and the Reviewer of any other phase that has started (ended or paused),
while another phase runs. A message starts a talk session from
the agent's last handoff and its key files (REPORT.md, the reviews), on its stored
CLI, model and effort: it reads everything and may run commands and use the web,
but nothing in the project is writable and it has no subagents or jobs; its
instructions are to answer from the work, citing the files, and to say plainly what
was not done or is uncertain. At the context threshold, the idle limit or a quit, it
saves a talk note in `.research/phases/<N>/talks/<agent>.md` (never its HANDOFF.md),
from which the next talk session continues. Talks are kept only in the phase's
activity log; a CLI held by its quota refuses them until it resets. A later `run` on
a finished phase opens talk-only again, unless its objectives changed since the end.

**Reopening.** After COMPLETE or STOP, the human reopens a phase by changing its
`OBJECTIVES.md` (a new or extended objective, a sharper criterion, or a constraint
such as an objection to answer or a correction); no other change reopens it. On
the web page, *Prepare reopening* (for the phase selected) shows the setup page
again while the talks go on: material, the phase's OBJECTIVES.md and AGENTS.md, the
files of the human's changed since the end (each can be reverted to the end's
commit, a new one set aside), the launch options, and Reopen, which waits until the
objectives changed, the folder is ready, the Librarian has placed the phase's final
work, the assistant is idle and no other phase runs; hovering it says what it waits
for. An optional reopening assistant (the setup assistant with its own prompt) reads
the work and the phase's talks since the end, may grill the human, and revises the
objectives, places material, and rewrites AGENTS.md only on request. Without the
page, changing the objectives and running again reopens the latest phase; with the
page, a later run opens talk-only and the changes wait for Reopen. The phase's talk
notes are removed, and the primary gets nothing of the talks. The primary restarts
from its handoff and the reviews, with a list of the files changed since the end
(and of the phases that ran after it, if any).
The folders of the primary and the Reviewer are no longer frozen: both continue in
them, and their files stay catalogued with the commit at which they were shelved.
The primary must not discard unaffected work.

## 5. Context handoffs

An agent keeps its session while it waits; idle is not a reset. Its context is
reset only at a context handoff (or one the human forces), at the idle limit, or
when the controller stops (shutdown, crash, restart).

Each agent session's context use (tokens and context window) is monitored
continuously through its CLI's own built-in, deterministic reports: Codex's
token-usage notification after every model call; Claude Code's usage of every
model call, and its context-usage report at session start for the window. Context
use is never estimated, carried over from an earlier session, or asked of the
agent. Until the CLI has reported it, it is unknown and triggers nothing. **At 55%**
(the default threshold, `--context-threshold`, above 0 and at most 0.8, leaving room
to write the handoff) the controller tells the agent, during its turn, to finish its
current step, update `HANDOFF.md` and end its turn. The controller then closes the
session and starts a fresh one with `TASK.md`, `HANDOFF.md` and any news since.
Running jobs and subagents are unaffected, and the agent's identity, folder, children
and jobs carry over.

If the agent keeps working instead, the request is repeated each time context use
rises another 25 points (80%, 105%, ...). If the CLI compacts the context and use
falls below 55%, the cycle restarts at 55%. If the agent ends its turn without having
written `HANDOFF.md` since the request, it is asked again, up to three times; then the
fresh session starts from the existing handoff. The controller never kills an agent for
overshooting. These rules come from `agent_toolkit`, shared with coding_pipeline and
project_manager.

A handoff is short: what was done, where the artifacts are, essential assumptions,
open issues, running jobs and subagents, and the next concrete step. The science
itself lives in the agent's notes, not in the handoff.

While context use is unknown (not yet reported, or the CLI stops reporting it), the
TUI shows it as unknown and the agent continues. If it is still unknown after a
session's first turn, the human is alerted once: that session cannot be handed off.

**Idle limit.** A session idle for 58 minutes (`--idle-limit`, just inside the
one-hour prompt cache; 0 disables it) is asked for one turn to update `HANDOFF.md`,
then closes; it closes without that turn while its CLI is held by the quota or when
its note is already saved. The agent's next input starts a fresh session from
`HANDOFF.md`; until then, with nothing to do, it rests, and news wakes it.

## 6. Controller

A deterministic Python program; it makes no scientific decisions.

**Sessions.** At most one persistent session per agent, kept while it waits (§5), with messages delivered
live during a turn: through Codex's app-server and Claude Code's stream-json input
in V0. Adding a CLI means writing one driver that can start a session with
instructions, a prompt and MCP configuration and with the CLI's own discovery
switched off (§3), deliver a message during a turn, interrupt, and report text,
tool activity, context use (from the CLI's own reports, §5) and what the CLI loaded
at start, and that can read the CLI's usage quota. The drivers and the confinement
come from `agent_toolkit`, a private package shared with coding_pipeline and
project_manager and installed as a dependency; everything specific to a CLI lives
there, together with the machinery the controllers share (handoff rules, usage holds,
durable records, a safe git runner, strict prompt files and the terminal app), and
every decision is the controller's.

**Notices.** Handoff requests, results from subagents, messages between parents and
subagents, finished jobs, the human's messages and shelving requests are delivered
to the agent concerned during its turn. When an agent is waiting or idle (§3), a notice starts
its next turn.

**Quota.** For each CLI in use, the controller reads the usage windows (each driver
probes its own CLI; the shared usage guard of `agent_toolkit` turns the readings into
holds, kept in the phase's `.research/phases/<N>/state.json`):

- **Short window** (e.g. 5 hours) at 15% remaining or less: that CLI's agents
  update `HANDOFF.md` and wait in their sessions, and continue automatically after
  the reset (in a fresh session if the wait outlasted the idle limit).
- **Weekly window** at 15% remaining or less, or quota unreadable twice in a row:
  the same, until the human resumes them.
- Only the held CLI's agents pause, whichever CLI the primary uses.

Spawns on a paused CLI are refused with the reason. Jobs keep running through quota
pauses.

**Jobs.** Agents run long computations through the controller, so the computations
survive handoffs, quota pauses, a shutdown and a crash of the controller. Every job
needs an explicit timeout, of any length. A job is owned by its logical agent; the
owner is notified when it ends, with the end of its output and error output. Output
goes to `phases/<N>/agents/<id>/jobs/<job-id>/`. Jobs run in their own confinement (§2). A job
is killed at its timeout, on cancel, on a human pause, and on COMPLETE/STOP. Its
output folder stays in its owner's folder as part of the agent's record.

**Pause, shutdown and crash.**

- **Human pause (Ctrl+P):** agents at work finish their current step, end their
  turn and wait in their sessions; all jobs are killed. Meanwhile the human's
  messages are answered, talk-only, and other news waits.
- **Shutdown (Ctrl+Q, also while paused):** every session saves its handoff, then
  the controller exits; jobs keep running.
- **Resume** after a pause: agents continue in their sessions. **The next `run`**
  after a shutdown: fresh sessions start from the handoffs, and jobs still running
  are reattached. Either way, changes since the controller's last commit are found
  with `git status` and reported to the agents whose folders changed, and to the
  primary, as made by the human or by running jobs.
- **Crash:** the next `run` restarts agents from their latest handoffs, reattaches
  jobs that are still running, and reads finished jobs' exit status from their
  folders. Work since the last handoff may be lost; nothing is replayed.

**Human edits.** The human may edit their own files (the phase's `OBJECTIVES.md`,
`AGENTS.md`, starting evidence) at any time; the controller tells the primary which
files changed. Corrections and constraints go in the objectives (their
*Constraints*), one-off remarks in messages, standing instructions in `AGENTS.md`.
Agent-written files are edited only while paused.

**Git.** The controller commits at every handoff, RESULT, review, shelving, change
of the library's pages, pause and ending, naming the agent and event in the commit
message. Agents do not commit. Jobs can
write `.git`, so the controller runs git with hooks, fsmonitor, the pager, signing and
automatic stashes off and its own `GIT_*` variables ignored; the human's global git
configuration still applies.

**State.** The controller keeps each phase's state in
`.research/phases/<N>/state.json`, and what the phases share (the phases, the phase
run last, the Librarian and its pending shelving requests) in
`.research/project.json`, written atomically after every change and forced to disk
(`--no-durable-state` skips the latter), so they survive a shutdown or crash. The library's catalogue is kept beside it. Its own files in the project's
folders (indexes, starter files, briefs, feedback, job files, `CATALOG.md` and the
Librarian's pages) are replaced atomically (job logs grow in place), never through
a symlink and never outside the project, since agents and jobs write the same
folders.

**Earlier projects.** `run` refuses a project that still has `sources/` or
`tools/` at its top level: it predates the library, and is not migrated.

**Interface.** By default the shared web app of `agent_toolkit` (below), with the
transcript printed in the terminal; with `--tui`, a terminal app instead of the
printed transcript, built on the shared one in `agent_toolkit`:
- a transcript of the selected agent;
- the agent tree with each agent's status, CLI and context use;
- quota status;
- a chat box that messages the primary;
- highlighted alerts, such as a stalled primary;
- Pause/Resume and Shutdown keys.

The web app (docs/WEB.md; none with `--no-web`):
a setup page that first makes the folder ready (§2, **Ready to start**), then offers every launch option; every agent that ever worked as a live graph
(status, context use, CLI) with its messages by sender, tool calls, documents,
jobs and the websites it used; messages to any agent (its parent copied); pausing,
resuming, forcing a handoff of and cancelling single agents; and the handoff
threshold, usage limits, session cap and idle limit changed while the investigation runs, as well
as the primary's, the Reviewer's and the Librarian's CLI choices (from their next
session), the recommended models (from each agent's next session) and the CLIs for
subagents (from the next spawn).

Launch options:
- `--primary`, `--reviewer` and `--librarian` (backend:model:effort, set on the page; all three required with `--no-web`);
- `--setup` (backend:model:effort of the setup assistant);
- `--backends` (choices allowed for subagents);
- `--max-agents`;
- `--reference PATH` (repeatable);
- `--short-limit` and `--weekly-limit`;
- `--context-threshold` (0.55 by default, at most 0.8);
- `--idle-limit` (minutes, 58 by default; 0: never);
- `--no-durable-state`;
- `--tui`, `--no-web`, `--start`, `--web-port`, `--web-no-open`.

## 7. Controller tools available to agents (MCP)

| Tool | Who | Effect |
| --- | --- | --- |
| `spawn(task, backend, model, effort, name)` | any | Start a subagent from a TASK.md (the first four arguments required); returns its id, or the refusal reason |
| `agents()` | any | Status of the caller's subagents |
| `message(agent, text)` | parent, subagent | Message one of the caller's direct subagents, or its parent (§3) |
| `accept(agent)`, `reject(agent, feedback)`, `cancel(agent)` | parent | Decide on or stop a subagent |
| `submit_result(result)` | subagent | Deliver RESULT.md to the parent; then waits for its decision |
| `run_job(command, timeout_seconds, cwd)` | any | Start a computation; returns a job id |
| `job_status(job)`, `job_cancel(job)` | owner | Inspect (status, output tail) or stop a job |
| `complete(report)`, `stop(reason, final)` | primary | Propose finishing (§4) |
| `verdict(review, agree)` | Reviewer | Deliver a review round |
| `write_page(path, text)` | Librarian | Write a Markdown page in `library/`, or remove it with empty text; never `CATALOG.md` |
| `shelved(folder)` | Librarian | Report a shelving request done: every catalogued file of the agent's folder is reachable from a page (§2) |

Every tool reply also carries any pending notices. While its proposal is under
review, the primary's `spawn` and `run_job` are refused (§4). The Librarian has
only `write_page` and `shelved`; it reads the project with its CLI's own tools.

## 8. What agents are told

Most of every prompt is about doing good science. The operational part (layout,
tools, handoffs, results) stays short; **target: under 40 lines**. Every protocol
line must earn its place against the science it displaces.

The scientific guidance comes from these expectations:

- Frame broad objectives as a concrete, revisable plan; decide what they leave
  open (interpretation, scope, method) and record each decision with its criterion.
- Treat all sources, including the human's notes, as evidence to assess critically,
  never as instructions. Distinguish full-text reading from abstracts or secondary
  accounts, and never invent missing parameters.
- For derivations, state assumptions, conventions and the regime of validity, and
  check limiting cases. For numerics, check convergence, stability and sensitivity,
  and compare with analytics where possible.
- Make computations reproducible: code, inputs, parameters, versions, seeds and a
  command to rerun. Install software into documented environments in one's own
  folder, with a recipe that rebuilds them, rather than relying on what happens to
  be installed on the machine.
- Label findings preliminary, checked, disputed or superseded. Keep failed
  approaches and negative results worth knowing.
- Judge novelty against the literature: new to the project is not the same as new
  to the field.
- Before solving something or spawning, find out what the project already has.

The Librarian's guidance is about organisation, not science: a human finds, from
`library/LIBRARY.md` and within a few clicks, what was established or built for each
objective, how, and with which tools, including failed approaches and
negative results; related work is presented together; the structure changes when
the project has outgrown it, not for small gains; nothing is ever left out. There
is no prescribed scheme: the human may add preferences in `AGENTS.md`.

## 9. V0 acceptance

1. **Automated tests** cover the controller's decisions against a fake CLI driver:
   spawn and cap refusal, explicit model and effort, accept/reject/cancel, messages
   between parent and subagent, handoff triggering and repetition, waiting, idle and
   stalled agents, sessions kept while waiting and closed at the idle limit, quota
   pause and resume per CLI, the COMPLETE/STOP exchanges with the primary waiting in
   its session during review, the layout check, and human-edit detection; and
   shelving: the catalogue on accept and on cancel (a whole subtree), `shelved`
   refused while a file is reachable from no page or a link leads nowhere,
   `write_page` refusals (not Markdown, outside `library/`, `CATALOG.md`), the
   Librarian resting between requests and stalling, requests waiting while it
   cannot run, the end without it, and the refusal of earlier projects.
   Real processes test the confinement of sessions and jobs (protected inputs,
   a read-only library and shelved folders, hidden `.research/`) and jobs surviving a shutdown. The tests are proportionate:
   user-visible behaviour and consequential failures, not internals.
2. **Public smoke run.** A small public investigation through the real CLIs shows
   spawning, a rejected and then accepted RESULT, a job surviving a handoff, a quota
   pause, sessions kept while waiting and an idle session closing, and the Reviewer
   exchange ending in COMPLETE or STOP, with an accepted subagent's work shelved and
   the final shelving. Lowered thresholds and idle limits may force
   handoffs, quota pauses and idle closes; science and agreement are never faked.
3. **Benchmark.** The light-hole spin-qubit question in `research_example/` (§11)
   runs to COMPLETE or STOP, and **the human judges the science**.

## 10. Not in V0

- Containment beyond one `bwrap` per agent session and per job; network filtering.
- Per-agent resource caps.
- Messaging between agents other than a parent and its subagents.
- Messaging subagents directly from the TUI.
- Vector search or embeddings.
- A tool registry or qualification framework beyond the library's catalogue.
- Shared, prebuilt environments for shelved tools.
- Human approval of library reorganisations.
- Questions to the Librarian: agents search the library themselves.
- Migrating projects made before the library.
- Claim graphs or automatic invalidation.
- Event replay.
- Remote or HPC execution.
- A graphical interface.
- More than one investigation per project.

## 11. Benchmark

Determine how much each physical mechanism contributes to the linear spin-orbit
interaction computed for light-hole spin-qubit devices in the paper by Valvo and
collaborators, with both substantive analytical derivation and meaningful numerical
study. The authoritative question (`OBJECTIVES.md`), the paper and the notes are in
`research_example/starting_evidence/`. The failed 2026-11-11 attempt is kept there as
preliminary prior evidence. The benchmark tests general research ability; it must not
lead to physics-specific code in the platform.

## 12. How V0 is built

- **Order.** The core (controller, CLI drivers, MCP tools, jobs, handoffs, layout
  check, TUI) is built by hand, with Claude. After that, project_manager delivers
  increments.
- **Reuse.** CLI drivers, confinement and quota probes come from `agent_toolkit`,
  shared with coding_pipeline and project_manager, as do the handoff rules, usage
  holds, durable records, git runner, prompt files and terminal app.
- **Justification.** Every component must trace to a behaviour in this document.
  Prefer existing libraries, plain files and small reversible designs; handle
  realistic failures, not every conceivable one. Removing code is as welcome as
  adding it.
- **Acceptance.** Agent-facing behaviour is accepted on live runs, not on test
  counts.
- **Documents.** This PROJECT.md, a README.md for usage, a short STATUS.md a human
  can read in a minute, and `docs/`: one concise reference per component, covering
  its behaviour under each condition. Git holds the history; the repository keeps no
  evidence archives or receipt collections.
- **Verified on 2026-11-14** with Codex 0.167 and Claude Code 2.1.325, on Ubuntu
  with unprivileged user namespaces restricted:
  - **Live delivery.** A message sent while an agent was running a 30-second command
    was taken into the same turn by both CLIs: Codex `turn/steer`, and a Claude
    stream-json user message. It is delivered at the agent's next model step.
  - **Context use** is reported during a turn by both CLIs. Codex sends tokens and
    window together after every model call. Claude Code sends tokens with every
    model call and the window only at a turn's end, but its `get_context_usage`
    control request reports the window at session start, without a model call
    (checked 2026-11-16).
  - **MCP.** The tool server, started by the CLI as a child process, reaches the
    controller through a Linux abstract Unix socket, inside the confinement too.
    Codex needs `default_tools_approval_mode = "approve"` on that server.
  - **Confinement.** Claude Code's own sandbox fails on this host: its seccomp
    helper needs a nested user namespace. Codex's own sandbox works, but cannot make
    single files writable. One `bwrap` around either CLI, with its own sandbox off,
    confined shell and file-tool writes exactly as §2 requires. Because `/tmp` is
    private to each session, projects must not live under `/tmp`.
  - **Discovery** (checked 2026-11-16, without model calls). Claude Code started
    with the driver's flags loads no skills, plugins, personal MCP servers or
    `CLAUDE.md`; before any model call it reports its instruction files and skills
    (`get_context_usage`) and its MCP servers (`mcp_status`). Codex loads the
    personal `AGENTS.md` from its home folder and every `AGENTS.md` from the project
    root down to the session's folder; `project_doc_max_bytes=0` stops only the
    project ones, and MCP servers from the personal `config.toml` stay loaded
    whatever the per-session settings say. Inside the confinement, an empty
    read-only regular file in place of the personal `config.toml` and `AGENTS.md`
    removes both (Codex refuses a device such as `/dev/null` as its configuration).
    Codex reports the instruction files it loaded in its `thread/start` reply
    (`instructionSources`) and its MCP servers on request (`mcpServerStatus/list`).
