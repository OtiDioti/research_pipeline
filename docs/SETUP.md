# Setting a folder up

`preparation.py`, `material.py`, `assistant.py`, `project.py`. The web app's setup
page makes a folder ready to be a project before the first start: material in
`starting_evidence/`, each entry described, and the first phase's objectives
written (`phases/1/OBJECTIVES.md`). The same steps prepare a new phase, or the
reopening of one that ended. Most of
the work is deterministic code; an optional setup assistant (an agent) helps on
request.

## When

- The web page opens the setup page on any project no investigation has started
  in (it has no `.research/project.json`): one created with *+ New project*, a folder
  added with *+ Open folder* or `research-pipeline run DIR` (one that does not exist
  yet is created), an empty one, one with material dumped at its top level, or an
  incomplete project. The page shows the preparation steps even when
  the folder is ready already, so a partial setup can still be improved.
- Once an investigation has started, there are no preparation steps for the phase
  that runs: the human edits their files directly ([PROJECT_FOLDER.md](PROJECT_FOLDER.md)).
  The page offers them for a **new phase** (*New phase* in the sidebar: the same
  Material step, an Objectives step with its OBJECTIVES.md and AGENTS.md, and the new
  phase's assistant, [WEB.md](WEB.md)), and for a phase that ended, to **reopen** it
  (the same Material step, an Instructions step with its OBJECTIVES.md and AGENTS.md,
  and the reopening assistant, [FINISHING.md](FINISHING.md), "Reopening").
- With `--no-web`, a folder that is not ready is refused, with the problems and
  the hint to run without `--no-web`; nothing is created. `--start` on a folder
  that is not ready is refused too.
- With the page, `--primary`, `--reviewer` and `--librarian` are optional: the
  page's last step sets them.

## Ready

`Project.unready()` lists what keeps a folder from being a project, the same for
the command line and the page's Start:

| Check | Before the first start | Afterwards |
|---|---|---|
| Not under `/tmp`, no `sources/` or `tools/` at the top level | yes | yes |
| The phase's `phases/<N>/OBJECTIVES.md` exists and is not empty | yes | yes |
| No loose material: nothing at the top level but the project's own entries (hidden ones aside) | yes | no: strays are reported to the primary |
| `starting_evidence/FOLDER_CONTENT.md` describes every entry at the top of `starting_evidence/` | yes | no |

Deeper folders of `starting_evidence/` are the human's own (an archived run may
keep its index byte for byte); the folders the setup creates are described as
material is placed in them.

## The steps

1. **Material.** Material arrives *loose* at the top level:
   - dropped on the page, or chosen as files or a folder (`POST /upload`; a name
     the project reserves, a hidden one, `..`, or an existing file is refused);
   - copied from paths on this machine (Copy in);
   - put there by hand (Rescan).

   Placing moves each loose entry into `starting_evidence/` or a folder under it
   and adds its one-line description to that folder's `FOLDER_CONTENT.md`; every
   new folder on the way needs a description of its own, in its parent's index,
   and gets an index. An entry at the top of `starting_evidence/` without a
   description is loose too: placing it only adds its line. A folder without its
   own index (e.g. a code repository) is one unit and cannot receive material.
   Every placement is checked whole before anything moves, and nothing is ever
   overwritten. By hand, the page offers a folder and a description per entry;
   *Let the assistant organise* asks the assistant.

   **Removing.** Every entry, loose or placed, has a remove button (only the human
   removes; the assistant has no such tool); a confirmation says what removing it
   does. Nothing the human cannot get back is ever deleted:
   - a copy made by Copy in whose original is still where it was copied from, byte
     for byte, is deleted (the original stays). Copy in records each import (its
     project path and source) in `.research/material/imports.json`, and placing
     keeps that record in step, so a placed copy, or a file of a copied folder, is
     still recognised;
   - anything else (uploaded, copied by hand, or a changed copy) is set aside in
     `.research/removed/<id>/`, listed in `.research/material/removed.json`.
     *Removed* lists it on the page, and *Restore* brings it back to the top level
     as loose material (never over an existing entry; a restored copy is known as
     one again).

   A placed entry loses its line in its folder's `FOLDER_CONTENT.md`; a folder left
   with nothing but an index that says nothing more than its title is removed too,
   with its line in its parent's. `OBJECTIVES.md` cannot be removed this way (it is
   the Objectives step's). Both records and the removed material stay after the
   start, in `.research/`, hidden from agents and ignored by git.
2. **Objectives.** The human writes first ideas and sends them to the assistant,
   optionally asking to be *grilled* first: the assistant then asks rounds of one
   to four multiple-choice questions (each with a free answer), informed by the
   ideas and the material, until it knows enough or the human presses *Enough,
   draft now*; it then writes `OBJECTIVES.md`. The editor (with a preview) edits it
   at any time; a save names the version it started from and is refused if the file
   changed meanwhile (e.g. the assistant rewrote it). Writing the objectives also
   adds their line to `starting_evidence/FOLDER_CONTENT.md`. The light template
   (`prompts/objectives-template.md`: per objective its kind, statement, what counts
   as met, constraints) is shown in the empty editor and given to the assistant;
   nothing enforces it.
3. **Settings.** The launch options ([WEB.md](WEB.md)), with the checks above;
   Start waits until they all hold.

## The setup assistant

- Its CLI, model and effort: `--setup`, or chosen on the page (default
  `codex:gpt-6.1-sol:high`); stored with the options at the start.
- It runs one request at a time (organise, ideas with or without a grill, answers,
  draft now, a free message), through agent_toolkit's `Relay`: its sessions hand
  over through a handoff note (`write_handoff`) at the context threshold.
- It reads the whole folder (but the program's records in `.research/`, as for every
  agent; its own folder there stays visible) and may search the web, and writes nothing but its
  note: it acts through three tools, answered by the deterministic code above:
  `place(entries, folders)`, `write_objectives(text)` (the phase's OBJECTIVES.md) and
  `ask(questions)`; for a new or reopened phase also `write_agents_md(text)`, only
  when asked.
- Its prompt depends on what it prepares: `prompts/setup.md` (the first phase),
  `prompts/phase.md` (a new phase: it also reads the earlier phases) or
  `prompts/reopen.md` ([FINISHING.md](FINISHING.md)).
- **The talks** (a new phase's and a reopening's): a *Talks* switch above the
  conversation, on by default, says whether the assistant reads the human's talks
  with the earlier phases' primaries and Reviewers since those phases ended (a
  reopening's: with this phase since its end); its note on hover says how many
  messages there are. The human's first conversation message (ideas, answers, draft
  now or a free message; not *organise*) fixes it, greyed from then on, and it is
  kept with the preparation. If it is on, that message gives the assistant the
  talks, written for it to `.research/setup/<N>/TALKS.md`, and each later request
  says when they changed; if it is off, the assistant never gets them (until then
  its prompt only says the human may give them).
- Before each request its CLI is asked whether it can run (installed, logged in,
  and confinable by bwrap on this machine: [CONFINEMENT.md](CONFINEMENT.md)); while
  it cannot, the request is refused with the reason, before any session is tried.
- Its usage quota is read before each request; at a short or weekly limit the
  request is refused, naming the limit (choose another CLI, or work by hand).
- If its session fails, the page says so, with the CLI's reason, and everything
  stays doable by hand.
- What the page shows of it (the conversation, open questions, its CLI choice) is
  kept in `.research/setup/<N>/` (per phase), so a restarted program continues there.
  When the phase starts that folder is removed; only its CLI logs stay, in
  `.research/logs/setup-N.jsonl`
  (and the material records above, which are not the assistant's).
