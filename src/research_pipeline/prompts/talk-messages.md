The messages of a talk session after the end, one section each (filled by research_pipeline.talks).

<!-- section:opening -->
[controller] Phase $phase $situation. The human wants to talk with you about the work. Your last handoff:

$handoff

$files
<!-- /section:opening -->

<!-- section:primary-files -->
Your result is $result and your status $status; the library's entry page is library/LIBRARY.md.
<!-- /section:primary-files -->

<!-- section:reviewer-files -->
Your reviews are in $reviews/ (the last one: $review); the primary's result is $result.
<!-- /section:reviewer-files -->

<!-- section:note -->
[controller] Your talk note from your previous talk session:

$note
<!-- /section:note -->

<!-- section:handoff -->
[controller] Save your talk note now with write_talk_note ($reason), then end your turn.
<!-- /section:handoff -->

<!-- section:handoff-missing -->
[controller] Your talk note was not saved: call write_talk_note now, then end your turn.
<!-- /section:handoff-missing -->
