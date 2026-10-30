# ADR-010 — Bounded continuous development with a narrow backend-repair exception

**State:** PROPOSED operating defaults; user-requested constraints identified below. **Prepared:** 2026-10-30. **Activation authority:** a real human grant, recorded separately. This document is not such a grant.

## Context

The product needs many implementation steps. The user wants progress preserved in Markdown and implementation through coding_pipeline, with less repeated prompting. Their revised prompt retains first-result human review, requires Astra 6.1 with effort no higher than extra-high, and permits necessary focused backend fixes with a coding_pipeline_changes.md audit.

## Alternatives

A single giant CWI request gives few durable decision points. A prompt per request imposes unnecessary coordination work on the human. An immediate external restart supervisor adds executable machinery, ownership hazards, and another component to test before it is needed.

## Decision

Recommend supervised commissioning, then one actual continuous grant covering bounded requests across phases. The outer coordinator inspects each accepted result, fast-forwards under that grant, updates evidence, and continues. Do not use CWI --merge by default. Offer an explicit optional first-run preauthorization for a genuinely single-start workflow; do not assume it overrides the user's retained review condition.

Allow the coordinator to repair only an observed backend defect directly in an isolated backend maintenance branch with regression evidence, preserved run/source identities, and a complete audit. Research-product implementation still exclusively uses CWI. No silent patched-code resumes or evidence rewriting.

Preserve the requested model name, verify its real identity locally, and stop for explicit clarification when unavailable. The official catalog checked for this update did not verify Astra 6.1. Map extra-high to xhigh and choose an explicit supported effort per CWI run. No substitute is authorized by this decision.

## Consequences

Routine request and phase boundaries no longer require human prompts after activation. Resource limits, real model availability, operating-system approvals, scientific judgment, and session limits can still stop progress. Durable records enable manual continuation; automatic restart remains unimplemented. Limits in AUTONOMY.md are proposed values to be accepted or changed in the actual grant, not guarantees of cost or project completion.

## Revisit

Reconsider a tested external supervisor if manual session renewal becomes a measured burden. Reconsider per-role reasoning configuration only when evidence justifies a separate backend change; do not pretend the reviewed backend supports it already.
