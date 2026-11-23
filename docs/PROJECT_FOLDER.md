# Project folder

`project.py`, `state.py`, `phases.py`. A project is an ordinary folder kept in git,
split into phases (`phases/<N>/`), which share the human's AGENTS.md and
starting_evidence/, the library and the Librarian. The controller of the phase that
runs creates its layout, checks agents' work against it, and commits every
significant event. The layout itself is in [PROJECT.md](../PROJECT.md) §2.

## Preparing

On `run`, the controller:
- refuses a folder that is not ready ([SETUP.md](SETUP.md), **Ready**): under `/tmp`, without a non-empty
  `phases/<N>/OBJECTIVES.md` for the phase it runs, before the
  first start with loose material at the top level or undescribed entries at the top of `starting_evidence/`, or made
  before the library (with `sources/` or `tools/` at its top level: it is not migrated);
- creates whatever is missing, keeping everything already there:
  - `library/`, `librarian/`, the phase's `agents/` and `reviews/`, and `.research/logs/`
    (`.research/phases/<N>/activity/`, every agent's messages and tool calls for the web
    app, appears with the first session);
  - the phase's STATUS.md, REPORT.md and FOLDER_CONTENT.md, the root FOLDER_CONTENT.md,
    `phases/FOLDER_CONTENT.md` and `library/LIBRARY.md`; the root index lists AGENTS.md
    while it exists, and only then (no link may lead nowhere), and `agents/FOLDER_CONTENT.md`
    lists the agents whose folders exist (the Reviewer's appears at its first session);
  - the folder indexes;
  - a `.gitignore` covering `.research/`, virtual environments and caches (or `.research/`
    added to an existing one);
- creates the git repository on the first run, and commits the prepared layout.

## Ownership

| Who | Writes |
|---|---|
| The human | `AGENTS.md`, `starting_evidence/` (read-only for agents and jobs), each phase's `OBJECTIVES.md` |
| Every agent | Its own `phases/<N>/agents/<id>/` (the Librarian: `librarian/`), until it is shelved ([LIBRARY.md](LIBRARY.md)) |
| The primary | Also its phase's STATUS.md, REPORT.md and FOLDER_CONTENT.md |
| The Reviewer | Also its phase's `reviews/` |
| The Librarian | Also the Markdown pages of `library/`, only through `write_page` |
| The controller | `.research/` (hidden from agents and jobs), `phases/FOLDER_CONTENT.md`, each phase's `agents/FOLDER_CONTENT.md` and `agents/<id>/jobs/FOLDER_CONTENT.md`, an agent's TASK.md and PARENT_FEEDBACK.md, `library/CATALOG.md` and `library/catalog/`, the Librarian's pages (as it asks), and the outcome line of STATUS.md |

Other phases' folders are read-only for a phase's agents and jobs.

These controller files, the starter files and a job's files are written atomically
(a job's logs are created fresh), never through a symlink and never outside the
project: agents and jobs can write the same folders ([CONTROLLER.md](CONTROLLER.md)).

## Layout check

**When:** at every handoff, `submit_result`, proposal, verdict and `shelved`.
- At a handoff, problems go to the next session as a notice.
- At the other four, the call is refused until they are fixed.

**Where:** the agent's own folder, plus its phase's folder (for the primary, its
own entries), its phase's `reviews/` (for the Reviewer) or `library/` (for the
Librarian).

**What is checked:**
- every folder has a `FOLDER_CONTENT.md` naming each of its files and subfolders;
- no notes in non-Markdown document formats (`.docx`, `.doc`, `.odt`, `.rtf`, `.rst`, `.org`).

**Exempt:** hidden entries, git-ignored ones, and the controller's `jobs/` output.
At most 30 problems are reported.

**Unexpected top-level entries** (not hidden, not part of the layout) can only come
from jobs or the human. They are reported to the primary once each, and never block anyone.

## The human's files

The controller fingerprints `AGENTS.md`, everything in `starting_evidence/` and the
phase's `OBJECTIVES.md` by size and modification time. A change, whether by the human
or by anything else, is reported to the primary (by file name) within about 10 s, and
at every commit. There is no FEEDBACK.md: corrections and constraints go in the
objectives, one-off remarks in messages, standing instructions in AGENTS.md.

## Git

The controller commits under the identity `research-pipeline`; agents cannot write
`.git` (jobs can). It runs git through the safe runner of `agent_toolkit.git`: hooks,
fsmonitor, the pager, external diff tools, signing and automatic stashes are off and
the controller's own `GIT_*` environment variables are ignored, so nothing a job puts
into `.git` runs outside the confinement, while your own global git configuration
(ignore file, default branch, LFS) still applies. Every commit message names the agent and the event:

| Event | Message |
|---|---|
| First run of a phase | `controller: project prepared` (a new repository only), then `controller: phase N started` |
| Handoff | `<agent>: handoff (context, refresh, idle or quota)` |
| Result, decision | `<agent>: result submitted`, `<parent>: accepted the result of <agent>`, `<parent>: cancelled <agent>` |
| Library | `librarian: shelved <folder>`, `librarian: library pages updated` |
| Proposal, verdict | `primary: proposes COMPLETE/STOP (round n)`, `reviewer: verdict on … (agree/disagree)` |
| Stalled Reviewer | `reviewer: stalled in round n; proposal withdrawn` |
| Pause, shutdown | `controller: paused by the human`, `controller: shut down by the human` |
| Resume, restart, reopen | `controller: changes made while paused …`, `controller: work recovered after a restart`, `human: changes before reopening` |
| End | `controller: phase N COMPLETE/STOPPED`, then `controller: the library after the end` |

- Files over 50 MB stay on disk but are kept out of git (`.git/info/exclude`) and
  listed in the commit message. A file that grows past the limit is removed from git.
- A failed commit is shown in the transcript; the investigation continues.
