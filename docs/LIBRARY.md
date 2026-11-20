# The library and the Librarian

`librarian.py`, `library.py`, `links.py`. Finished work stays in the folder of the
agent that made it. `library/` holds the Librarian's Markdown pages, which lead a
human to it: what was established or built for each objective, how, and with
which tools. Nothing is moved, renamed or deleted for the library, so every path
an agent, a job or a note uses stays valid.

## Shelving

An agent's folder is shelved when:
- its parent accepts it, or it is cancelled (each agent of a cancelled subtree,
  deepest first, also when the human cancels it);
- a phase ends: its primary's and Reviewer's folders, and any other
  ended agent's not shelved yet.

Shelving:
1. **catalogues** every file of the folder in `.research/library.json`: what git
   tracks, and files over 50 MB, each with its line from its folder's
   `FOLDER_CONTENT.md` and the commit at shelving. What git ignores otherwise
   (environments, caches) is not catalogued and stays on disk untouched;
2. **freezes** the folder: agents could never write another agent's folder, and
   jobs now see it read-only too (a job started before the shelving keeps the
   access it started with);
3. **asks the Librarian** to place the work (`Shelving request: the agent of <folder>/ …`).

Nothing is deleted. A reopened phase's primary and Reviewer continue in
their folders, which are no longer frozen; the catalogue keeps the earlier entry
until the next end replaces it.

## The catalogue

The controller renders it at every commit and after every shelving, in two parts,
so that agents can read the index whole and search the rest:
- `library/CATALOG.md`, a short index: the shelved agents by phase, each with the
  title of its TASK.md, who it is, its number of files and when it was shelved,
  linking to its page; then the agents at work, each linking to its folder and
  its `FOLDER_CONTENT.md`;
- `library/catalog/phase-<N>/<id>.md`, one page per shelved agent: its folder,
  the commit at shelving, and every catalogued file with its index line. Each
  folder of `catalog/` has a `FOLDER_CONTENT.md`, written by the controller too.

Agents read `library/LIBRARY.md` and `CATALOG.md`, and search `library/catalog/`,
before solving something or spawning. Pages are rewritten only when they change.
A Librarian's page elsewhere in `library/` is never touched.

## The Librarian

| | |
|---|---|
| CLI, model, effort | `--librarian` (required on the first run; editable live in the web app) |
| Started | At its first shelving request; between requests it rests |
| Session cap | Not counted against `--max-agents` |
| Writes | Its own folder (`librarian/`, at the top level: it serves every phase); `library/` only through `write_page` |
| Tools | `write_page(path, text)`, `shelved(folder)` |
| Instructions | `prompts/librarian.md` (no shared scientific part), then the human's `AGENTS.md` |
| Quota | Paused only by a hold on its own CLI, or by the human |

- **`write_page(path, text)`** writes a Markdown page of `library/` (the path is
  relative to `library/`), atomically and never through a symlink; empty text
  removes it, with folders left empty. Refused: a path outside `library/`, not
  ending in `.md`, hidden, a folder, `CATALOG.md` or under `catalog/`. The reply lists the page's
  links that lead nowhere.
- **`shelved(folder)`** reports a request done; requests name agents by folder (e.g. `phases/2/agents/fit`), as agent ids repeat across phases. It is refused, with the list,
  while a catalogued file of that agent is reachable from no page, a link in
  `library/` leads nowhere, or the layout check of `library/` fails (a folder's
  `FOLDER_CONTENT.md` missing an entry; `catalog/` needs no line, and its folders are
  the controller's). `CATALOG.md` and `catalog/` do not count as pages.
  Accepted: the request is removed and the controller commits
  `librarian: shelved <folder>`.
- **Its turns.** At the end of each turn, the pages it changed are committed
  (`librarian: library pages updated`), and new links that lead nowhere are sent
  to it once.
- **Idle and stalled.** It is idle only while a request is pending: then it is
  nudged once, and if it ends its turn idle again without using a tool, the human
  is alerted (ALERT) and its requests wait. Otherwise ending its turn means it rests.

## Links

Recognised in pages: inline links and images, reference definitions, and Obsidian
wikilinks (`[[note]]`, resolved next to the page, from the project root, or by file
name, shortest path first). Links in code are ignored, and so are URLs and in-page
anchors; `#anchors` and URL encoding are stripped. A link to a folder covers every
file in it.

## The end

On COMPLETE or a confirmed STOP, every session but the Librarian's closes and the
outcome is committed. The final folders are shelved, and the controller waits for
the Librarian to place them (no time limit; Ctrl+Q exits at once), then commits
`controller: the library after the end` and stays open for talks
([FINISHING.md](FINISHING.md)). If the Librarian cannot run (its CLI is held, its
session failed, the human paused it) or stalls, the work is catalogued already, and
its requests reach it at the next `run`, talk-only or reopened.

## Earlier projects

`run` refuses a project that still has `sources/` or `tools/` at its top level: it
predates the library and is not migrated.
