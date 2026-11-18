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
  since the proposal's commit (except `reviews/` and `agents/reviewer/`): the review
  does not cover them.
- After a verdict, the Reviewer rests, keeping its session (until the idle limit);
  the next round's request reaches it there.
- It keeps its objections across rounds, in its HANDOFF.md for a fresh session, and its earlier reviews are in `reviews/`.

## Ending

On COMPLETE or a confirmed STOP, the controller:
- closes every session;
- marks the primary `finished`, open subagents `cancelled`, and the Reviewer `resting`;
- kills every job;
- appends the outcome to STATUS.md;
- commits "controller: investigation COMPLETE/STOPPED";
- exits.

Machine COMPLETE is not scientific acceptance: that is the human's judgment.

## Reopening

Running `research-pipeline run` on a finished project:
1. commits the human's changes ("human: changes before reopening");
2. sets the investigation running;
3. restarts the primary from its handoff, with a notice listing the files changed
   since the end. It must keep unaffected work.

Earlier reviews stay in `reviews/`, and round numbers continue.
