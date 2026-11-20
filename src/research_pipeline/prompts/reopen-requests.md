The messages the reopening assistant receives, one section each (filled by research_pipeline.assistant).

<!-- section:opening -->
[reopen] Phase $number ended: $outcome

$state
<!-- /section:opening -->

<!-- section:note -->
[reopen] Your handoff note from your previous session:

$note
<!-- /section:note -->

<!-- section:talks -->
[reopen] The human talked with the phase's primary or Reviewer since your last request: $talks has the new messages.
<!-- /section:talks -->

<!-- section:organise -->
[human] Place the loose material:

$loose

Read each entry, enough to describe it, then place them all with one call of place.
<!-- /section:organise -->

<!-- section:ideas-grill -->
[human] What I want from the reopened phase:

$ideas

Grill me first: ask your first round of questions with ask, informed by these ideas, the talks and the work.
<!-- /section:ideas-grill -->

<!-- section:ideas-draft -->
[human] What I want from the reopened phase:

$ideas

Revise $objectives from these ideas, the talks and the work, with write_objectives.
<!-- /section:ideas-draft -->

<!-- section:answers -->
[human] My answers:

$answers

Ask another round with ask, or, if you know enough, revise the objectives with write_objectives.
<!-- /section:answers -->

<!-- section:draft -->
[human] Enough questions: revise $objectives now with write_objectives, from what you know.
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
