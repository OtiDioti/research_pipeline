# The Writer and its reports

The research agents write their results for each other. The Writer turns them into
reports for you: a LaTeX document compiled to a PDF, checked against the work by an
independent checker before you get it (`writer.py`; [PROJECT.md](../PROJECT.md) §4,
"Reports").

## What it writes, and where

| Report | Folder | Built from |
|---|---|---|
| A phase's | `reports/phase-<N>/` | the phase's objectives, result, status, agents' folders (results, notes, derivations, data, figures, the notation file), reviews; your documents in `starting_evidence/`; the earlier phases' reports |
| The project's | `reports/project/` | every phase's report, going back to the phases' results where the reports disagree or something is missing |

A report's folder holds `report.tex`, `report.pdf`, `figures/` (with the scripts that
make them), `build.sh` (how it compiles, with `latexmk`), `CHANGELOG.md` (one entry per
version) and `checks/` (the checker's findings, `round-<K>.md`). `reports/FOLDER_CONTENT.md`
lists the reports; the top index lists `reports/` and `WRITING.md` once they exist.

## How it writes

- **Your rules:** `WRITING.md` at the project's top level, which the first start creates
  from the built-in rules (`prompts/writing-starter.md`): the answer first, one section
  per main result, then limitations, negative results, key decisions, and the evidence
  with a reproduction appendix. Change it as you like; only the Writer and its checker
  read it.
- **Faithful to the work:** only what the work establishes, at the status it gives it.
  It may re-plot saved data, evaluate or rewrite the agents' expressions (checking them
  symbolically) and convert units; it never computes new results. Where the work is
  unclear it asks the phase's primary (`ask_primary`), answered by a talk session of
  that primary (any phase that does not run); the answer comes as its next request.
- **Your notation:** the symbols of your documents exactly; a quantity they lack gets a
  symbol in their style, defined and listed in a notation table; never the agents'
  shorthand or labels.

## When it runs

| Trigger | What it does |
|---|---|
| A phase ends, with *Report when a phase ends* on (default) | after the Librarian placed the final work: writes the report, or revises it if one exists, unless it is newer than the end |
| *Write report* / *Update report* (top bar, a phase that does not run) | writes it, or revises the existing one with what changed |
| *Rewrite report* (asks first) | writes it anew from the work; the old one stays in git |
| *Project report* (top bar) | writes or revises the project's report |
| A message to the Writer's node | answers you; if you ask for a change, makes it and submits again |

A request is refused while the Writer works on the same report, while the phase runs,
while its CLI cannot run or its quota is held, and on a machine without `latexmk` (the
controls are greyed then, saying why).

## The check

When the Writer submits a compiled report (`submit_report`, refused while `report.pdf`
is missing or older than `report.tex`), a fresh checker session (never the Writer's, so
that it is not anchored on its reading) checks fidelity, notation, `WRITING.md` and the
build (in a copy under its `/tmp`), and ends with `report_clean` or `report_findings`
(a non-empty file in `checks/`). Findings go to the Writer as its next request; it fixes
them or says why not, compiles and submits again. The next checker is told the previous
findings and the Writer's reply. After a clean check the report is done; after three
checks with findings, what is left is shown to you (an alert, and the Writer's node).
A checker that ends without a verdict is asked once more, then counts as left for you.

## Sessions, the page and the records

- Both use the *Writer* setting (CLI, model and effort; `--writer`; default
  `claude:claude-opus-5-5:high`), from their next session. They are hosted by the
  controller, like the talks, and do not count against *Sessions at once*.
- The Writer's session continues across requests and saves a handoff note
  (`.research/writer/<report>/HANDOFF.md`) at the context threshold and at shutdown,
  which waits for its current request. A request a restart interrupted is not resumed:
  ask again. Each checker starts afresh.
- The Writer writes only its report's folder (and its note); the checker only `checks/`.
  Both read everything but `.research/` (but their own notes). Agents' jobs see
  `reports/` and `WRITING.md` read-only.
- On the page, the Writer and its checker are nodes of the phase's graph (the project's
  in every phase's), once a report was asked for; the Writer's ring offers *message*.
  What they say and do is in the phase's activity log (the project's in the library's),
  and in the run's statistics as agents `writer` and `checker` of the phase.
- The controller commits after each request (`writer: …`).
