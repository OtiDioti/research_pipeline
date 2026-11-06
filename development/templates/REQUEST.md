# REQ-Dxx-nnn — Bounded result

Provides a reusable request record format; placeholders are not execution evidence or authority.

**Phase:** Dxx. **Readiness:** PROPOSED. **Request revision:** source commit to be captured at launch.

## Goal and source requirements

Give the one result to obtain, exact requirement IDs and original specification references. Explain how it builds on the current accepted source.

## Inputs and interfaces

List exact existing APIs/data formats, context/conventions, relevant decisions, source paths to inspect, and references available in the candidate worktree. Do not rely on an unrecorded outer chat or on ignored local files.

## Required changes and non-goals

List concrete responsibilities and allowed areas. Define public interfaces that later requests will rely on. Backward compatibility is not required: remove superseded interfaces, flags, modules, adapters and unused functionality within scope, preserving current required behavior, safety, historical evidence and unfinished-run recovery. Let the Architect resolve internal implementation details within the specified constraints.

## Acceptance criteria

Use stable IDs. Define meaningful behavior and important adverse cases. Name what requires deterministic tests, integration evidence, review, or human assessment. Include documentation and migration obligations where relevant.

## Validation profile and prerequisites

State exact checks, cwd assumptions, prepared dependencies, environment identity, and passing baseline. Explicit commands are argv, not shell scripts. Do not start a request with an already-failing baseline unless the documented bootstrap policy actually applies.

## Budget, scope, and stopping

Specify limits, required external permissions, milestone ceiling, integration authorization, blocked conditions, and when to ask for a material decision. Do not change frozen constraints during resume.

## Completion reporting

Require truthful changed-path summaries, executed checks, remaining obligations, and evidence references. CWI owns implementation correctness, validation, review, final acceptance and Git source transitions. The coordinator checks Designer goal understanding (Architect only when necessary), verifies acceptance evidence, Git identities and integration safety, and owns post-integration administrative records. No routine Writer code/test/diff inspection or duplicate successful CWI checks; implementation diagnostics require a concrete failure or inconsistency. Required post-integration validation remains.

## Coordinator execution envelope

Link the actual grant ID/revision and specification/source identity. Record and verify all four approved CWI selections: Designer `gpt-6-astra` / `xhigh`, Architect `gpt-6.1-sol` / `xhigh`, Writer `gpt-6.1-sol` / `high`, Reviewer `gpt-6.1-sol` / `high`. The launch must explicitly pass `--designer-model gpt-6-astra --designer-reasoning xhigh --architect-model gpt-6.1-sol --architect-reasoning xhigh --writer-model gpt-6.1-sol --writer-reasoning high --reviewer-model gpt-6.1-sol --reviewer-reasoning high`. Record start-attempt/milestone/repair/deadline allowance, existing billing/service/data authority, and integration policy. All four pairs are immutable in schema-revision-2 state; no old-state migration or automatic historical resume. Describe whether the next normal action after successful integration is another request or a real scoped completion/hold.

Necessary backend maintenance is separate under BACKEND_MAINTENANCE.md; delegated roles do not inherit the coordinator's exception. Do not change this request's frozen contents on resume.
