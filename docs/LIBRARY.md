# The library and the Librarian

`librarian.py`, `library.py`, `links.py`. Finished work stays in the folder of the
agent that made it. `library/` holds the Librarian's Markdown pages, which lead a
human to it: what was established about each research question, how, and with
which tools. Nothing is moved, renamed or deleted for the library, so every path
an agent, a job or a note uses stays valid.

## Shelving

An agent's folder is shelved when:
- its parent accepts it, or it is cancelled (each agent of a cancelled subtree,
  deepest first, also when the human cancels it);
- the investigation ends: the primary's and the Reviewer's folders, and any other
  ended agent's not shelved yet.

Shelving:
1. **catalogues** every file of the folder in `.research/library.json`: what git
   tracks, and files over 50 MB, each with its line from its folder's
   `FOLDER_CONTENT.md` and the commit at shelving. What git ignores otherwise
   (environments, caches) is not catalogued and stays on disk untouched;
2. **freezes** the folder: agents could never write another agent's folder, and
   jobs now see it read-only too (a job started before the shelving keeps the
   access it started with);
3. **asks the Librarian** to place the work (`Shelving request: <id> …`).

Nothing is deleted. A reopened investigation's primary and Reviewer continue in
their folders, which are no longer frozen; the catalogue keeps the earlier entry
until the next end replaces it.

## The catalogue

`library/CATALOG.md` is rendered by the controller at every commit and after every
shelving: each shelved agent with its files and index lines, then the work in
progress in the other agents' folders (the lines of their `FOLDER_CONTENT.md`).
Agents search it, with `library/LIBRARY.md`, before solving something or spawning.

## The Librarian

| | |
|---|---|
| CLI, model, effort | `--librarian` (required on the first run; editable live in the web app) |
| Started | At its first shelving request; between requests it rests |
| Session cap | Not counted against `--max-agents` |
| Writes | Its own folder (`agents/librarian/`); `library/` only through `write_page` |
| Tools | `write_page(path, text)`, `shelved(agent)` |
| Instructions | `prompts/librarian.md` (no shared scientific part), then the human's `AGENTS.md` |
| Quota | Paused only by a hold on its own CLI, or by the human |

- **`write_page(path, text)`** writes a Markdown page of `library/` (the path is
  relative to `library/`), atomically and never through a symlink; empty text
  removes it, with folders left empty. Refused: a path outside `library/`, not
  ending in `.md`, hidden, a folder, or `CATALOG.md`. The reply lists the page's
  links that lead nowhere.
- **`shelved(agent)`** reports a request done. It is refused, with the list,
  while a catalogued file of that agent is reachable from no page, a link in
  `library/` leads nowhere, or the layout check of `library/` fails (a folder's
  `FOLDER_CONTENT.md` missing an entry). `CATALOG.md` does not count as a page.
  Accepted: the request is removed and the controller commits
  `librarian: shelved <agent>`.
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
`controller: the library after the end` and exits. It does not wait if the
Librarian cannot run (its CLI is held, its session failed, the human paused it) or
once it stalls: the work is catalogued already, and its requests reach it at the
next `run`.

## Earlier projects

`run` refuses a project that still has `sources/` or `tools/` at its top level: it
predates the library and is not migrated.
