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
one tool `write_talk_note`; the human may allow the primary to change its files
([FINISHING.md](FINISHING.md)).

The **Writer** writes the reports for the human from the agents' work, with a fresh
**checker** for each report it submits: not part of the investigation, hosted by the
controller like the talks, with `prompts/writer.md` and `prompts/checker.md` and the tools
`submit_report`, `ask_primary`, `report_clean` and `report_findings` ([WRITER.md](WRITER.md)).

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

## Results and notation

Results are written for agents, not for the human: a subagent's RESULT.md serves its
parent, the Reviewer and the agents that build on it, and the phase's RESULT.md, which
the primary writes, serves the Reviewer and the later phases. An account for the human
is a separate, later step (it will be the phase's REPORT.md).

Their form is free: no layout is prescribed or checked for results, briefs, checks or
reviews. `prompts/common.md` fixes only what a result contains: the request it answers,
restated; what was done, on what earlier work; each part of the request marked met,
partial, infeasible or open, with why; decisions; confidence and limitations; negative
results; and the key claims with their evidence, how each was checked and the command
that reproduces it. A result gives the current state of the work: the primary makes a
review's corrections in the work and answers each objection in
`agents/primary/RESPONSES.md`. A parent records its spot-checks in its notes. A
derivation must let another agent check it (its starting point stated, each step
justified).

The human's documents fix the notation and terminology: their symbols are never renamed
or given another meaning. Agents may add symbols of their own, defined in the human's
quantities, but no chains of shorthand definitions. The primary keeps the phase's
`agents/primary/NOTATION.md`, which starts from the human's documents and the earlier
phases' notation files and extends them; the human's documents win any conflict. The
Reviewer objects to notation that departs from the human's documents.

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
  files and the controller's TASK.md, PARENT_FEEDBACK.md and MESSAGES.md aside) and tells it,
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
- The controller appends every message an agent sends or receives (from its parent, a subagent or the
  human, and the parent's copy of the human's message to a subagent) to `MESSAGES.md` in that agent's folder,
  with when, from whom and to whom, and lists it in the folder's index (`messages.py`). A message refused,
  or sent to an agent whose folder is frozen, is not kept there. What a message decides still belongs in
  the agent's notes or result.
- The human can also write to any agent from the web app (`[human] ...`); its parent receives a copy
  (`[human → <id>] ...`).
- Refused when the agents aren't parent and subagent, the text is empty, the
  recipient has ended, or the recipient has submitted its result. In that last
  case, use accept, reject or cancel.

## When agents stop working

For waiting, idle and stalled agents, see [CONTROLLER.md](CONTROLLER.md). For handoffs, see [CONTEXT.md](CONTEXT.md).
