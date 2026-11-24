# Agent roles

Four roles that run the same way: one persistent CLI session at a time, inside its
confinement ([CONFINEMENT.md](CONFINEMENT.md)), with the controller's tools
([TOOLS.md](TOOLS.md)). Each agent keeps its id and its folder `phases/<N>/agents/<id>/` (the Librarian's: `librarian/`)
across any number of sessions.

| | Primary | Subagent | Reviewer | Librarian |
|---|---|---|---|---|
| Started by | The controller, at launch | `spawn`, by any agent | A COMPLETE or STOP proposal | Its first shelving request |
| CLI, model, effort | `--primary` | The `spawn` arguments | `--reviewer` | `--librarian` |
| Opening message | Its phase's objectives (their links rewritten to work from its folder), the other phases (and the one it builds on), an inventory of the starting evidence, the reference paths | TASK.md, and PARENT_FEEDBACK.md after a rejection | The review request | Its pending shelving requests |
| Writes, besides its folder | Its phase's STATUS.md, RESULT.md, FOLDER_CONTENT.md | — | Its phase's `reviews/` | `library/` pages, through `write_page` |
| Finishes with | `complete` or `stop` | `submit_result` | `verdict` | `shelved`, for each request |

The Librarian does no research: it organises the library ([LIBRARY.md](LIBRARY.md)).
It is not counted against `--max-agents`, has no other tools, and neither sends nor
receives agents' messages (the human can write to it from the web app).

After the end, the primary and the Reviewer answer the human in **talk sessions**:
talk-only, read-only, from their handoff and key files, with `prompts/talk.md` and the
one tool `write_talk_note` ([FINISHING.md](FINISHING.md)).

Before the first start, the web setup page may also run a **setup assistant**: not part of the
investigation, it places material and drafts `OBJECTIVES.md` on request, through its tools `place`,
`write_objectives` and `ask`, with `prompts/setup.md` as its instructions ([SETUP.md](SETUP.md)).

## What every session receives

- **Session instructions** (system or developer prompt, in force for the whole
  session): the role prompt (`prompts/common.md` and the role's file; for the
  Librarian, `prompts/librarian.md` alone), then the project's `AGENTS.md`,
  shortened beyond 20,000 characters.
- **Opening message:**
  - the session number;
  - the role's sections above;
  - HANDOFF.md if there is one (otherwise: "write a short plan and a first HANDOFF.md");
  - any queued notices.
- Nothing else: the CLIs load none of the human's own setup ([DRIVERS.md](DRIVERS.md)).

## Results, checks and notation

Results are written for agents, not for the human: a subagent's RESULT.md serves its
parent, the Reviewer and the agents that build on it, and the phase's RESULT.md, which
the primary writes, serves the Reviewer and the later phases. An account for the human
is a separate, later step (it will be the phase's REPORT.md). `prompts/common.md` gives
the one format of every result:

- **Coverage:** one row per criterion of the request (each part of an objective's
  statement, "Result" and "Met when", each numbered criterion of a brief), quoted, with its status
  (met, partial, infeasible, open) and the claims that support it.
- **Claims** C1, C2, …: IDs are permanent; each claim gives its status (checked,
  preliminary, disputed, superseded by another, withdrawn), what it rests on (other
  claims, cited as `[fit C3](/phases/2/agents/fit/RESULT.md)`, and inputs), its evidence,
  the author's check and a rerun command.
- **Decisions**, **Negative results**, **Open** and a **Glossary** of labels coined in
  the work.

A result states the current state of the work, without narrative or history; the
primary answers a review in `agents/primary/RESPONSES.md`, under each objection's ID.
Whoever checks another agent's claim (a parent accepting a result, the Reviewer) records
it in `CHECKS.md` in its own folder: the claim, what was done, the outcome, the command.
The Reviewer checks the consequential claims no CHECKS.md covers, numbers its objections
`R<round>.<n>`, and from the second round opens each review with the state of the earlier
ones.

A derivation is the evidence of an analytic claim: a note in the agent's folder, one section per
claim, that a checker can follow step by step. It opens with its starting point (cited claims, the
human's equations, the notation file); its numbered steps each name the operation (the equations
substituted, the identity, the approximation and its regime) and keep the starting quantities
visible, without chains of shorthand definitions; its last step is the claim's statement; it closes
with its checks. A symbolic script reproducing it is the claim's rerun command where feasible. An
intermediate result that others use is a claim of its own. The Reviewer objects to a derivation it
cannot follow from its stated starting point.

A brief has the sections Purpose, Request (numbered criteria), Prior work, Inputs (claims,
files, the notation file) and Check. The human's documents fix the notation and
terminology; the primary keeps the phase's `agents/primary/NOTATION.md`, built from them
in every phase rather than from an earlier phase's file.

A phase that ended before results were renamed (0.29.0) keeps its REPORT.md as its result:
the controller names it wherever it would name the phase's RESULT.md.

## Subagents

- `spawn(task, backend, model, effort, name)` needs all four arguments. The role
  prompt recommends a model for coding tasks and one for analytical ones, the
  options `coding` and `analysis` (default `claude:claude-opus-5-5:xhigh` and
  `codex:gpt-6.1-sol:xhigh`), set on the setup page or live, from each agent's next
  session. When a recommended model's backend is not allowed or held by its quota,
  agents use the best model they can on an available backend; the project's
  `AGENTS.md` may say otherwise. An effort
  Claude Code does not accept (it accepts `low`, `medium`, `high`, `xhigh` and `max`) is
  refused before any session starts; Codex checks the effort itself when the session starts. The brief
  `task` (a non-empty Markdown file) is copied to the phase's `agents/<id>/TASK.md`. The id
  comes from `name`: lower case, dashes, at most 40 characters, with `-2` or `-3`
  added if taken.
- TASK.md is read from the subagent's folder, not from the brief's, so the copy's
  relative links become links from the project's root (`links.rebase`; PROJECT.md
  §2, "Links"), to the file each reaches from the brief's folder, or from the
  subagent's if the parent wrote it for TASK.md. A link that reaches nothing from
  either folder, or a different file from each, is kept as written, and the `spawn`
  reply names it. URLs, anchors, links from the root, wikilinks and links in code
  are untouched.
- **Links.** Every agent writes its links from the project's root, with a leading
  slash; `PROJECT` in its sessions and jobs is the project's folder. At the end of
  each turn of the primary, a subagent or the Reviewer, the controller reads the
  Markdown it changed in what it may write (`linkcheck.py`; its FOLDER_CONTENT.md
  files and the controller's TASK.md and PARENT_FEEDBACK.md aside) and tells it,
  once each, of the links that are relative, absolute paths into the project, or
  lead nowhere. Nothing is refused.
- Spawning does not stop the parent: it keeps doing whatever does not depend on the
  subagent, and news reaches it even during its turn. It ends its turn only when
  nothing useful remains until a subagent or job reports.
- `submit_result` requires a non-empty RESULT.md, no running subagents or jobs of
  its own, and a passing layout check. The subagent is then `submitted`: it ends
  its turn and waits in its session, its tools refused, and its parent is told at once,
  with the links of its files that break the link convention, if any (it then
  decides whether they matter; the subagent's reply names them too).
- The parent decides what happens next:
  - **accept:** the subagent ends, its session closes, and its folder is shelved
    ([LIBRARY.md](LIBRARY.md));
  - **reject(feedback):** the feedback, its relative links made links from the
    root as for TASK.md, is appended to PARENT_FEEDBACK.md and
    reaches the subagent in the same session (in a fresh one from HANDOFF.md if
    its session closed at the idle limit). If its CLI is held, or it needs a new
    session and every slot is taken, it waits; the rejection still stands;
  - **cancel:** the subagent, its whole subtree and all their jobs stop, and each
    of their folders is shelved.
- The Reviewer's subagents are its helpers, for independent checks.

## Messages

- `message(agent, text)` works between a parent and its direct subagents, in both directions.
- It is delivered during the recipient's turn, or wakes it if it waits idle; a paused recipient receives it
  when it continues, and one without a session at its next session.
- Messages are not stored in files for the agents: the recipient notes what matters. (The controller keeps
  them, for the web app, in `.research/activity/`, which agents cannot see.)
- The human can also write to any agent from the web app (`[human] ...`); its parent receives a copy
  (`[human → <id>] ...`).
- Refused when the agents aren't parent and subagent, the text is empty, the
  recipient has ended, or the recipient has submitted its result. In that last
  case, use accept, reject or cancel.

## When agents stop working

For waiting, idle and stalled agents, see [CONTROLLER.md](CONTROLLER.md). For handoffs, see [CONTEXT.md](CONTEXT.md).
