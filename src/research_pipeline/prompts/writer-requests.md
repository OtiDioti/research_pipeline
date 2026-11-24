The messages the Writer and its checker receive, one section each (filled by research_pipeline.writer).

<!-- section:opening -->
[controller] You write $target in $folder. $report
<!-- /section:opening -->

<!-- section:no-report -->
No report exists there yet.
<!-- /section:no-report -->

<!-- section:a-report -->
A report exists there: report.tex, with its CHANGELOG.md.
<!-- /section:a-report -->

<!-- section:write -->
[controller] Write the report.
<!-- /section:write -->

<!-- section:revise -->
[controller] Bring the report up to date with the work: revise what changed since its last version (its CHANGELOG.md says when that was), and keep the rest.
<!-- /section:revise -->

<!-- section:fresh -->
[controller] Start fresh: write the report anew from the work, replacing the current one (record it in CHANGELOG.md).
<!-- /section:fresh -->

<!-- section:findings -->
[checker] The checker found discrepancies (round $round of at most $rounds), in $file:

$findings

Fix each one, or say in your reply why it needs no change; then compile and call submit_report again.
<!-- /section:findings -->

<!-- section:answer -->
[primary of phase $phase] $answer
<!-- /section:answer -->

<!-- section:question -->
[writer] The Writer of the reports for the human asks about your work: $question
<!-- /section:question -->

<!-- section:note -->
[controller] Your handoff note from your previous session:

$note
<!-- /section:note -->

<!-- section:handoff -->
[controller] Save your handoff note now with write_handoff ($reason), then end your turn.
<!-- /section:handoff -->

<!-- section:handoff-missing -->
[controller] Your handoff note was not saved: call write_handoff now, then end your turn.
<!-- /section:handoff-missing -->

<!-- section:check -->
[controller] Check $target, round $round of at most $rounds.$previous
<!-- /section:check -->

<!-- section:previous -->


The previous round's findings are in $file. The Writer's reply to them:

$reply
<!-- /section:previous -->
