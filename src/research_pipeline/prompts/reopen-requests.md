The messages the reopening assistant receives, and the sentences on the human's talks in its prompt, one section each (filled by research_pipeline.assistant and research_pipeline.preparation).

<!-- section:opening -->
[reopen] Phase $number ended: $outcome

$state
<!-- /section:opening -->

<!-- section:note -->
[reopen] Your handoff note from your previous session:

$note
<!-- /section:note -->

<!-- section:talks -->
[reopen] The human talked with the phase's primary or Reviewer since your last request: $talks_file has the new messages.
<!-- /section:talks -->

<!-- section:talks-open -->
The human may give you their talks with this phase's primary and Reviewer since its end: if they do, you are told where they are with their first message to you.
<!-- /section:talks-open -->

<!-- section:talks-given -->
The human's talks with this phase's primary and Reviewer since its end are in $talks_file (you are told when it changes).
<!-- /section:talks-given -->

<!-- section:talks-now -->
[reopen] The human gives you their talks with this phase's primary and Reviewer since its end: they are in $talks_file, kept up to date (you are told when it changes). Read what their requests need.
<!-- /section:talks-now -->

<!-- section:organise -->
[human] Place the loose material:

$loose

Read each entry, enough to describe it, then place them all with one call of place.
<!-- /section:organise -->

<!-- section:ideas-grill -->
[human] What I want from the reopened phase:

$ideas

Grill me first: ask your first round of questions with ask, informed by these ideas, the work and the talks if you have them.
<!-- /section:ideas-grill -->

<!-- section:ideas-draft -->
[human] What I want from the reopened phase:

$ideas

Revise $objectives from these ideas, the work and the talks if you have them, with write_objectives.
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
