# Setting a folder up

`preparation.py`, `material.py`, `assistant.py`, `project.py`. The web app's setup
page makes a folder ready to be a project before the first start: material in
`starting_evidence/`, each entry described, and the objectives written. Most of
the work is deterministic code; an optional setup assistant (an agent) helps on
request.

## When

- `research-pipeline run DIR --web` opens the setup page on any folder no
  investigation has started in (it has no `.research/state.json`): one that does
  not exist yet (it is created), an empty one, one with material dumped at its top
  level, or an incomplete project. The page shows the preparation steps even when
  the folder is ready already, so a partial setup can still be improved.
- Once an investigation has started, there are no preparation steps: the human
  edits their files directly ([PROJECT_FOLDER.md](PROJECT_FOLDER.md)).
- Without `--web`, a folder that is not ready is refused, with the problems and
  the hint to run with `--web`; nothing is created. `--web --start` on a folder
  that is not ready is refused too.
- With `--web`, `--primary`, `--reviewer` and `--librarian` are optional: the
  page's last step sets them.

## Ready

`Project.unready()` lists what keeps a folder from being a project, the same for
the command line and the page's Start:

| Check | Before the first start | Afterwards |
|---|---|---|
| Not under `/tmp`, no `sources/` or `tools/` at the top level | yes | yes |
| `starting_evidence/OBJECTIVES.md` exists and is not empty (the former `RESEARCH_QUESTIONS.md` is named) | yes | yes |
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
3. **Settings.** The launch options, as before, with the checks above; Start waits
   until they all hold.

## The setup assistant

- Its CLI, model and effort: `--setup`, or chosen on the page (default
  `codex:gpt-6.1-sol:high`); stored with the options at the start.
- It runs one request at a time (organise, ideas with or without a grill, answers,
  draft now, a free message), through agent_toolkit's `Relay`: its sessions hand
  over through a handoff note (`write_handoff`) at the context threshold.
- It reads the whole folder and may search the web, and writes nothing but its
  note: it acts through three tools, answered by the deterministic code above:
  `place(entries, folders)`, `write_objectives(text)` and `ask(questions)`.
- Its usage quota is read before each request; at a short or weekly limit the
  request is refused, naming the limit (choose another CLI, or work by hand).
- If its session fails, the page says so and everything stays doable by hand.
- What the page shows of it (the conversation, open questions, its CLI choice) is
  kept in `.research/setup/`, so a restarted program continues there. At the start
  that folder is removed; only its CLI logs stay, in `.research/logs/setup-N.jsonl`.
