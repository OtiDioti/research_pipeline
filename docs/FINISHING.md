# Review and finishing

How an investigation ends: COMPLETE (the Reviewer must agree) or STOP (the
primary's decision, after the Reviewer's challenge).

## Proposing

`complete(report)` and `stop(reason)` are refused unless:
- the primary's subagents and jobs are settled;
- its layout check passes;
- HANDOFF.md was updated during its current session (a brief one suffices);
- no earlier proposal is still with the Reviewer.

`complete` also needs a non-empty report, REPORT.md by default.

On a proposal:
1. The round number increases, and the proposal is committed.
2. The primary becomes `resting`: its session ends with its turn.
3. The Reviewer is woken with the review request. It may need to wait for a slot or for its CLI's quota.

## During the review

- The Reviewer reads the whole project, may run jobs and spawn helpers, writes
  `reviews/<round>.md`, and calls `verdict(review, agree)`. It must settle its
  helpers and jobs first.
- A chat message from the human wakes the primary in **talk-only** mode. It is told
  its proposal is under review. `spawn`, `run_job`, `complete` and `stop` are
  refused, and STATUS.md and REPORT.md are read-only for it. Its session stays
  open until the verdict.
- If the Reviewer stalls (ends its turn idle twice without a verdict), the proposal
  is withdrawn, its session closes, and the primary is woken: it may continue,
  propose again or stop.

## Verdicts

| Proposal | Verdict | Result |
|---|---|---|
| COMPLETE | agree | The investigation is COMPLETE |
| COMPLETE | disagree | The proposal ends; the primary restarts with the review, and continues, proposes again (no round limit) or stops |
| STOP | agree or disagree (a challenge) | The primary restarts with the review and decides: `stop(reason, final=True)` confirms; continuing the work (any `spawn` or `run_job`) withdraws the STOP |

- After a verdict, the Reviewer's session ends with its turn, and it rests until the next round.
- It keeps its objections across rounds in its HANDOFF.md, and its earlier reviews are in `reviews/`.
- A talk-only session of the primary is replaced when the verdict arrives, so the new one can write STATUS.md and REPORT.md.

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
