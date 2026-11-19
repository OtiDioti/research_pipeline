The messages the reopening assistant receives, one section each (filled by research_pipeline.assistant).

<!-- section:opening -->
[reopen] The investigation ended: $outcome

$state
<!-- /section:opening -->

<!-- section:note -->
[reopen] Your handoff note from your previous session:

$note
<!-- /section:note -->

<!-- section:talks -->
[reopen] The human talked with the primary or the Reviewer since your last request: $talks has the new messages.
<!-- /section:talks -->

<!-- section:organise -->
[human] Place the loose material:

$loose

Read each entry, enough to describe it, then place them all with one call of place.
<!-- /section:organise -->

<!-- section:ideas-grill -->
[human] What I want from the reopening:

$ideas

Grill me first: ask your first round of questions with ask, informed by these ideas, the talks and the work.
<!-- /section:ideas-grill -->

<!-- section:ideas-draft -->
[human] What I want from the reopening:

$ideas

Write this reopening's section of FEEDBACK.md from these ideas, the talks and the work, with write_feedback (and the objectives, if they change).
<!-- /section:ideas-draft -->

<!-- section:answers -->
[human] My answers:

$answers

Ask another round with ask, or, if you know enough, write this reopening's section of FEEDBACK.md with write_feedback (and the objectives, if they change).
<!-- /section:answers -->

<!-- section:draft -->
[human] Enough questions: write this reopening's section of FEEDBACK.md now with write_feedback (and the objectives, if they change), from what you know.
<!-- /section:draft -->

<!-- section:message -->
[human] $text
<!-- /section:message -->

<!-- section:handoff -->
[reopen] Save your handoff note now with write_handoff ($reason), then end your turn.
<!-- /section:handoff -->

<!-- section:handoff-missing -->
[reopen] Your handoff note was not saved: call write_handoff now, then end your turn.
<!-- /section:handoff-missing -->
