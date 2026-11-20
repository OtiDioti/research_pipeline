The messages the setup assistant receives, one section each (filled by research_pipeline.assistant).

<!-- section:opening -->
[setup] The folder as it is now:

$state
<!-- /section:opening -->

<!-- section:note -->
[setup] Your handoff note from your previous session:

$note
<!-- /section:note -->

<!-- section:organise -->
[human] Place the loose material:

$loose

Read each entry, enough to describe it, then place them all with one call of place.
<!-- /section:organise -->

<!-- section:ideas-grill -->
[human] My first ideas:

$ideas

Grill me first: ask your first round of questions with ask, informed by these ideas and the material.
<!-- /section:ideas-grill -->

<!-- section:ideas-draft -->
[human] My first ideas:

$ideas

Write $objectives from these ideas and the material, with write_objectives.
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
[setup] Save your handoff note now with write_handoff ($reason), then end your turn.
<!-- /section:handoff -->

<!-- section:handoff-missing -->
[setup] Your handoff note was not saved: call write_handoff now, then end your turn.
<!-- /section:handoff-missing -->
