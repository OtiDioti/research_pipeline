# Review and finishing

How an investigation ends: COMPLETE (the Reviewer must agree) or STOP (the
primary's decision, after the Reviewer's challenge).

## Proposing

`complete(report)` and `stop(reason)` are refused unless:
- the primary's subagents and jobs are settled;
- its layout check passes;
- no earlier proposal is still with the Reviewer.

`complete` also needs a non-empty result, the phase's RESULT.md by default (a phase that ended
with only a REPORT.md, before results were renamed, keeps that as its result).

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
  the phase's `reviews/<round>.md`, and calls `verdict(review, agree)`. It must settle its
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
  since the proposal's commit (except the phase's `reviews/` and `agents/reviewer/`,
  `library/` and `librarian/`): the review
  does not cover them.
- After a verdict, the Reviewer rests, keeping its session (until the idle limit);
  the next round's request reaches it there.
- It keeps its objections across rounds, in its HANDOFF.md for a fresh session, and its earlier reviews are in the phase's `reviews/`.

## Ending

On COMPLETE or a confirmed STOP, the controller:
- closes every session but the Librarian's;
- marks the primary `finished`, open subagents `cancelled`, and the Reviewer `resting`;
- kills every job;
- appends the outcome to the phase's STATUS.md;
- commits "controller: phase N COMPLETE/STOPPED", and takes the human's files
  as they are then as the baseline for reopening (their fingerprint, that commit
  and the time are kept in the phase's state);
- shelves the primary's and the Reviewer's folders, and any other ended agent's not shelved yet;
- lets the Librarian place them (if it cannot run or stalls, its requests reach it at the next `run`)
  and commits "controller: the library after the end";
- stays open for talks until the human quits (Ctrl+Q, or Close on the web page), or
  reopens the phase, or starts or resumes another, from the web page. The state reads `complete (talk only)` or
  `stopped (talk only)`.

Machine COMPLETE is not scientific acceptance: that is the human's judgment.

## Talks

`talks.py`. After a phase's end the human can talk with its primary (the chat box, or
the web page) and its Reviewer (the web page), talk-only; no other agent takes
messages after the end. On the web page the human can also talk, at any time, with
the primary and the Reviewer of any other phase that has started (ended or paused),
while another phase runs: select it in the sidebar ([WEB.md](WEB.md)).

- A message starts a **talk session** of that agent, on its stored CLI, model and
  effort. Its instructions are `prompts/talk.md` (its phase has ended, or is paused;
  answer from the work, citing the files; say what was not done or is uncertain) and
  the human's AGENTS.md; its first message gives where its phase stands, its last
  HANDOFF.md and its key files (the phase's RESULT.md and STATUS.md, or the latest
  review), then the human's message.
- It has every native capability, but nothing in the project is writable (only its
  private /tmp), `.research/` is hidden, and its one controller tool is
  `write_talk_note`. It starts no subagents or jobs.
- Further messages go to the same session: into a running answer, or as the next
  request.
- At the context threshold (also in the middle of an answer, which then continues in
  a fresh session), at the idle limit, or when the human quits or switches phases,
  the session saves a talk note in `.research/phases/<N>/talks/<agent>.md`; the next
  talk session starts from the handoff plus that note. HANDOFF.md never changes.
- Talks are kept in the phase's activity log only (transcript, web page); nothing is
  committed.
- While the agent's CLI is held by its usage quota, a message is refused, naming the hold.
- Changes to the human's files while the program stays open do not reopen anything.
  With the web page they wait for its Reopen (below); without it, once the phase's
  objectives changed, the human is told once to quit and run again.

## Reopening

Only a change of the phase's OBJECTIVES.md reopens it: a new or extended objective,
a sharper criterion, or a constraint (an objection to answer, a correction, what to
keep). Files of the human's changed *since the end* (the phase's OBJECTIVES.md,
AGENTS.md, starting_evidence/) are those whose content differs from the end's commit
(a file the commit lacks, new or too large to be committed, counts by its
fingerprint); all of them are listed to the reopened primary.

**From the web page** (`preparation.py`, `web.py`). With a phase that ended selected,
the top bar offers *Prepare reopening*, which opens the setup page again
([WEB.md](WEB.md)); the program stays open and the talks go on meanwhile.
- *Material*: add, place and remove material, as before the first start.
- *Instructions*: the phase's OBJECTIVES.md and AGENTS.md, one editor each (a save
  names the version it started from, as on the setup page).
- The last step lists the files changed since the end. *Revert* brings a file back
  from the end's commit, or sets a new one aside in `.research/removed/` (restorable
  from the Material step's Removed list, with its index line dropped); a file too
  large to be committed at the end cannot be reverted. *Discard all* reverts every
  one that can be.
- **Reopen** waits until the phase's objectives changed since the end, the folder is
  ready (as for the first start), the Librarian has placed the phase's final work,
  the assistant is idle and no other phase runs; hovering it says which of these it
  waits for. The launch options can be changed there as at a start.
- Reopen ends the talks (each saves its note) and the running controller (whose phase
  must have ended or be paused, see [WEB.md](WEB.md)); a new controller then reopens
  the phase, as below, in the same program and page.

**The reopening assistant** (`assistant.py`, `prompts/reopen.md`) is the setup
assistant with its own prompt and requests, on the same CLI choice, and is optional:
- it reads the project, and the phase's talks since its end if the *Talks* switch
  is on when the human first writes to it ([SETUP.md](SETUP.md)), written for it to
  `.research/setup/<N>/TALKS.md` (each request says when that changed);
- it can grill the human (rounds of one to four multiple-choice questions) and writes
  through tools: `write_objectives` (the phase's OBJECTIVES.md, kept short: what is
  done belongs in the report and the library), `place`, and `write_agents_md`
  (AGENTS.md, only when asked);
- its conversation is kept in `.research/setup/<N>/` while the human prepares (across
  *Back*, other phases and a quit), and removed at Reopen, leaving only its CLI logs.

**From the command line.** `research-pipeline run` on a project whose latest phase
has ended:
- with the web page: opens talk-only, whatever changed; prepared changes wait for
  the page's Reopen;
- with `--no-web`: opens talk-only unless the phase's objectives changed since the
  end, and otherwise reopens it.

Opening talk-only commits pending changes as "controller: changes after the end" (the
end's commit stays the reference), and the Librarian places what was left pending.

**Reopening the phase**:
1. commits the human's changes ("human: changes before reopening");
2. ends the phase's talks and removes their notes (the primary gets nothing of them);
3. sets the phase running, and takes the human's files as they are as known;
4. restarts the primary from its handoff, with a notice listing the files changed
   since the end (and, if other phases ran since, the later phases with their
   outcomes and reports). It must keep unaffected work. Its folder and the
   Reviewer's are no longer frozen: both continue in them;
5. gives the Librarian any shelving requests left pending at the end.

The Reviewer gets nothing new: it sees the new objectives with the next proposal.
Earlier reviews stay in the phase's `reviews/`, and round numbers continue.
