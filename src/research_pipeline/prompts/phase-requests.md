The messages the new phase's assistant receives, one section each (filled by research_pipeline.assistant).

<!-- section:opening -->
[phase] Phase $number is new. The earlier phases:

$phases

$state
<!-- /section:opening -->

<!-- section:note -->
[phase] Your handoff note from your previous session:

$note
<!-- /section:note -->

<!-- section:talks -->
[phase] The human talked with earlier phases' primaries or Reviewers since your last request: $talks has the new messages.
<!-- /section:talks -->

<!-- section:organise -->
[human] Place the loose material:

$loose

Read each entry, enough to describe it, then place them all with one call of place.
<!-- /section:organise -->

<!-- section:ideas-grill -->
[human] What I want from the new phase:

$ideas

Grill me first: ask your first round of questions with ask, informed by these ideas, the earlier phases and the material.
<!-- /section:ideas-grill -->

<!-- section:ideas-draft -->
[human] What I want from the new phase:

$ideas

Write $objectives from these ideas, the earlier phases and the material, with write_objectives.
<!-- /section:ideas-draft -->

<!-- section:answers -->
[human] My answers:

$answers

Ask another round with ask, or, if you know enough, write the objectives with write_objectives.
<!-- /section:answers -->

<!-- section:draft -->
[human] Enough questions: write $objectives now with write_objectives, from what you know.
<!-- /section:draft -->

<!-- section:message -->
[human] $text
<!-- /section:message -->

<!-- section:handoff -->
[phase] Save your handoff note now with write_handoff ($reason), then end your turn.
<!-- /section:handoff -->

<!-- section:handoff-missing -->
[phase] Your handoff note was not saved: call write_handoff now, then end your turn.
<!-- /section:handoff-missing -->
