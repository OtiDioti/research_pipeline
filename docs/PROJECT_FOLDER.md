# Project folder

`project.py`, `state.py`. A project is an ordinary folder kept in git. The
controller creates its layout, checks agents' work against it, and commits every
significant event. The layout itself is in [PROJECT.md](../PROJECT.md) §2.

## Preparing

On `run`, the controller:
- refuses a project under `/tmp`, or one without `starting_evidence/RESEARCH_QUESTIONS.md`;
- creates whatever is missing, keeping everything already there:
  - `sources/`, `tools/`, `agents/`, `reviews/` and `.research/logs/`;
  - STATUS.md, REPORT.md, FEEDBACK.md and the root FOLDER_CONTENT.md;
  - the folder indexes;
  - a `.gitignore` covering `.research/`, virtual environments and caches;
- creates the git repository on the first run, and commits the prepared layout.

## Ownership

| Who | Writes |
|---|---|
| The human | `AGENTS.md`, `FEEDBACK.md`, `starting_evidence/` (read-only for agents and jobs) |
| Every agent | Its own `agents/<id>/`, and the shared `sources/` and `tools/` |
| The primary | Also STATUS.md, REPORT.md and the root FOLDER_CONTENT.md |
| The Reviewer | Also `reviews/` |
| The controller | `.research/` (hidden from agents and jobs), `agents/FOLDER_CONTENT.md`, each `agents/<id>/jobs/FOLDER_CONTENT.md`, an agent's TASK.md and PARENT_FEEDBACK.md, and the outcome line of STATUS.md |

## Layout check

**When:** at every handoff, `submit_result`, proposal and verdict.
- At a handoff, problems go to the next session as a notice.
- At the other three, the call is refused until they are fixed.

**Where:** the agent's own folder, `sources/` and `tools/`, plus the root (for the
primary) or `reviews/` (for the Reviewer). Agents share `sources/` and `tools/`,
so one agent's missing entry there can block another; that agent fixes it.

**What is checked:**
- every folder has a `FOLDER_CONTENT.md` naming each of its files and subfolders;
- no notes in non-Markdown document formats (`.docx`, `.doc`, `.odt`, `.rtf`, `.rst`, `.org`).

**Exempt:** hidden entries, git-ignored ones, and the controller's `jobs/` output.
At most 30 problems are reported.

**Unexpected top-level entries** (not hidden, not part of the layout) can only come
from jobs or the human. They are reported to the primary once each, and never block anyone.

## The human's files

The controller fingerprints `AGENTS.md`, `FEEDBACK.md` and everything in
`starting_evidence/` by size and modification time. A change, whether by the human
or by anything else, is reported to the primary within about 10 s, and at every commit.

## Git

The controller commits under the identity `research-pipeline`; agents cannot write
`.git` (jobs can). Every commit message names the agent and the event:

| Event | Message |
|---|---|
| First run | `controller: project prepared` |
| Handoff | `<agent>: handoff (context, pause, shutdown or quota)` |
| Result, decision | `<agent>: result submitted`, `<parent>: accepted the result of <agent>`, `<parent>: cancelled <agent>` |
| Proposal, verdict | `primary: proposes COMPLETE/STOP (round n)`, `reviewer: verdict on … (agree/disagree)` |
| Stalled Reviewer | `reviewer: stalled in round n; proposal withdrawn` |
| Pause, shutdown | `controller: paused by the human`, `controller: shut down by the human` |
| Resume, restart, reopen | `controller: changes made while paused …`, `controller: work recovered after a restart`, `human: changes before reopening` |
| End | `controller: investigation COMPLETE/STOPPED` |

- Files over 50 MB stay on disk but are kept out of git (`.git/info/exclude`) and
  listed in the commit message. A file that grows past the limit is removed from git.
- A failed commit is shown in the transcript; the investigation continues.
