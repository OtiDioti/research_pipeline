# Review and finishing

How an investigation ends: COMPLETE (the Reviewer must agree) or STOP (the
primary's decision, after the Reviewer's challenge).

## Proposing

`complete(report)` and `stop(reason)` are refused unless:
- the primary's subagents and jobs are settled;
- its layout check passes;
- no earlier proposal is still with the Reviewer.

`complete` also needs a non-empty report, REPORT.md by default.

On a proposal:
1. The round number increases, and the proposal is committed; the proposal records that commit.
2. The primary ends its turn and waits in its session, **talk-only**: `spawn`,
   `run_job`, `complete` and `stop` are refused until the verdict. Its write scope
   does not change.
3. The Reviewer gets the review request, in its session if it kept one. A fresh
   session may need to wait for a slot or for its CLI's quota.

## During the review

- The Reviewer judges the project as of the proposal's commit: `git diff --stat
  <commit>` lists what changed since, `git show <commit>:PATH` shows a file as
  proposed. It reads the whole project, may run jobs and spawn helpers, writes
  `reviews/<round>.md`, and calls `verdict(review, agree)`. It must settle its
  helpers and jobs first.
- The human's chat messages reach the primary in its session; it answers, talk-only.
  If its session closed at the idle limit, a fresh one starts, told that its
  proposal is under review.
- If the Reviewer stalls (ends its turn idle twice without a verdict), the proposal
  is withdrawn, the Reviewer rests, and the primary is told: it may continue,
  propose again or stop.

## Verdicts

| Proposal | Verdict | Result |
|---|---|---|
| COMPLETE | agree | The investigation is COMPLETE |
| COMPLETE | disagree | The proposal ends; the primary receives the review, and continues, proposes again (no round limit) or stops |
| STOP | agree or disagree (a challenge) | The primary receives the review and decides: `stop(reason, final=True)` confirms; continuing the work (any `spawn` or `run_job`) withdraws the STOP |

- The verdict reaches the primary in the same session (a fresh one if that closed
  at the idle limit). It lists the files changed
  since the proposal's commit (except `reviews/`, `library/`, `agents/reviewer/` and
  `agents/librarian/`): the review
  does not cover them.
- After a verdict, the Reviewer rests, keeping its session (until the idle limit);
  the next round's request reaches it there.
- It keeps its objections across rounds, in its HANDOFF.md for a fresh session, and its earlier reviews are in `reviews/`.

## Ending

On COMPLETE or a confirmed STOP, the controller:
- closes every session but the Librarian's;
- marks the primary `finished`, open subagents `cancelled`, and the Reviewer `resting`;
- kills every job;
- appends the outcome to STATUS.md;
- commits "controller: investigation COMPLETE/STOPPED", and takes the human's files
  as they are then as the baseline for reopening;
- shelves the primary's and the Reviewer's folders, and any other ended agent's not shelved yet;
- lets the Librarian place them (if it cannot run or stalls, its requests reach it at the next `run`)
  and commits "controller: the library after the end";
- stays open for talks until the human quits (Ctrl+Q, or Quit on the web page). The
  state reads `complete (talk only)` or `stopped (talk only)`.

Machine COMPLETE is not scientific acceptance: that is the human's judgment.

## Talks after the end

`talks.py`. The human can talk with the primary (the chat box, or the web page) and
the Reviewer (the web page), talk-only; no other agent takes messages after the end.

- A message starts a **talk session** of that agent, on its stored CLI, model and
  effort. Its instructions are `prompts/talk.md` (answer from the work, citing the
  files; say what was not done or is uncertain) and the human's AGENTS.md; its first
  message gives the outcome, its last HANDOFF.md and its key files (REPORT.md and
  STATUS.md, or the latest review), then the human's message.
- It has every native capability, but nothing in the project is writable (only its
  private /tmp), `.research/` is hidden, and its one controller tool is
  `write_talk_note`. It starts no subagents or jobs.
- Further messages go to the same session: into a running answer, or as the next
  request.
- At the context threshold (also in the middle of an answer, which then continues in
  a fresh session), at the idle limit, or when the human quits, the session saves a
  talk note in `.research/talks/<agent>.md`; the next talk session starts from the
  handoff plus that note. The frozen HANDOFF.md never changes.
- Talks are kept in the activity log only (transcript, web page); nothing is committed.
- While the agent's CLI is held by its usage quota, a message is refused, naming the hold.
- Changes to the human's files while the program stays open do not reopen anything:
  the human is told once to quit and run again.

## Reopening

Running `research-pipeline run` on a finished project:
- **without** changes to the human's files (OBJECTIVES.md, FEEDBACK.md, AGENTS.md,
  starting_evidence/) since the end: opens talk-only again (other pending changes are
  committed as "controller: changes after the end"; the Librarian places what was
  left pending);
- **with** such changes: reopens the investigation:
  1. commits the human's changes ("human: changes before reopening");
  2. ends the talks and removes their notes (the primary gets nothing of them);
  3. sets the investigation running;
  4. restarts the primary from its handoff, with a notice listing the files changed
     since the end. It must keep unaffected work. Its folder and the Reviewer's are no
     longer frozen: both continue in them;
  5. gives the Librarian any shelving requests left pending at the end.

Earlier reviews stay in `reviews/`, and round numbers continue.
