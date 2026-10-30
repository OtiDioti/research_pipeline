# Continuous development policy

**Policy version:** 2, 2026-10-30. This is a workflow policy, not an authorization grant, an installed scheduler, or evidence of product completion.

## 1. Strategy: supervised commissioning, then bounded continuous execution

Use the existing outer Codex coordinator and CWI implementation backend. Do not replace them with a new development framework. Keep individual requests small, but let the coordinator repeat them without asking for routine permission at every request or phase boundary.

The recommended sequence preserves the user's first-run inspection:

1. **Commissioning:** complete D00, execute only REQ-D01-001, inspect the real final acceptance, then stop at accepted-unmerged for human review. Do not pass `--merge`.
2. **One-time activation:** the human authorizes integration of that exact accepted commit and a continuous-development envelope. The coordinator records the grant and proceeds; subsequent ordinary requests and phase transitions within the envelope do not require new prompts.
3. **Continuous execution:** select, implement through CWI, inspect, integrate, checkpoint, and continue until the scoped completion gate or a genuine stopping condition.
4. **Recovery across sessions:** a new coordinator reads the same durable authorization and reconciles actual evidence. A fresh session is not a new budget and does not require reauthorization unless authority changed or expired.

The [startup prompts](CODEX_START.md) link a complete [optional single-prompt alternative](CODEX_START_AUTONOMOUS.md) for explicitly preauthorizing step 2 before the first run. That removes the human first-integration checkpoint only when the human actually selects it. Do not infer that permission from a request to update documentation.

### Alternatives and tradeoffs

A single enormous CWI request hides useful stopping points and makes recovery expensive. A new prompt after every small request unnecessarily makes the human the scheduler. A generic script that repeatedly says “continue” can loop through blockers or start competing controllers. Bounded requests in one continuing coordinator session, with durable checkpoints and explicit authorization, avoid these problems without adding untested automation.

## 2. Source of authority

[AUTHORIZATION.md](AUTHORIZATION.md) records the actual operating grant. [STATUS.md](../STATUS.md) points to it and reports consumed allowances; it does not grant new permissions. Live local observations and self-written agent plans never broaden the grant.

Use the most restrictive applicable rule from the human's grant, repository policy, frozen CWI run, operating-system permissions, and provider limits. A human revocation or new restriction takes effect immediately; do not launch further work. If a process is already executing, preserve its identity and use its supported interruption/recovery path rather than assuming it stopped.

The grant must identify the repository, target branch, applicable specification revision, scope, integration authority, resource limits, model policy, permitted services, and stop conditions. Permission to work toward completion is not permission to alter the definition of completion.

## 3. Modes

| Mode | Allowed progression | Integration |
| --- | --- | --- |
| `COMMISSIONING` | D00 and one bootstrap request | First result held for human review |
| `SUPERVISED` | One named request | According to that request's explicit grant |
| `PHASE` | All ready requests within named phases | Verified exact-commit integration if authorized |
| `CONTINUOUS` | All ready work across the approved phase range | Same verification gate; no routine human pause |
| `HOLD` | Inspection and safe recording only | No new implementation or integration |

A material architecture choice is not automatically a human decision: the coordinator may choose reversible internal details within the specification and document the rationale. Changes to mandatory requirements, scientific intent, data disclosure, external costs, security boundaries, or the operating grant require authorization. Keep this distinction so autonomy does not collapse into questions about every function name.

## 4. The continuous loop

At every iteration:

1. **Reconcile.** Inspect Git, local attempts/handoff, CWI evidence, effective authorization, remaining resources, and any backend-maintenance state. Discover an unfinished or accepted-unmerged run before planning a new one.
2. **Resolve existing work.** Continue only through a supported resume or authorized exact-source integration. An uncertain run blocks another implementation run in that target repository.
3. **Select.** Choose the smallest useful ready slice that advances a mandatory requirement. Prioritize correctness/recovery defects over new features. Respect dependencies. An unrelated blocked item need not halt independent authorized work once no active or bound run prevents it.
4. **Prepare.** Read the original specification sections; write a bounded request with testable criteria, interfaces, dependencies, risks, limits, model/effort, and validation. Commit the prelaunch records while the target is clean and no prior binding remains.
5. **Execute.** Launch CWI once with explicit supported settings. Record attempt identity and later the actual run UUID under ignored local storage. Do not change the original checkout or backend installation during execution.
6. **Inspect.** Read final receipts, exact accepted source, meaningful test results, review findings, and the complete diff. Successful inspection or the presence of `accepted_head` alone is insufficient.
7. **Integrate.** Under the existing grant, fast-forward only to the exact finally accepted commit after branch/base/cleanliness/collision checks. Do not pass CWI `--merge` in this default workflow; coordinator-controlled integration is still automatic from the human's perspective after activation.
8. **Validate and record.** Run the documented read-only post-integration check. Record exact source/receipt identities, requirement evidence, phase outcomes, resource consumption, unresolved issues, and one next action in an administrative checkpoint. Distinguish that commit from the accepted product commit.
9. **Continue.** If completion is not established and another authorized task is ready, begin the next iteration in the same session. Ordinary request success, a phase boundary, or finishing a status update is not a stopping condition.

Do not start the next run until the previous integration and checkpoint are reconciled. Do not create a status commit between acceptance and the pending fast-forward: that changes the expected base.

## 5. Proposed limits for the activation prompt

These are transparent defaults for a grant, not claims that they guarantee completion or limit monetary expenditure. Adjust before activation, not while resuming a frozen run.

| Limit | Proposed value / interpretation |
| --- | --- |
| Phase range | D01–D10, including remaining D01 obligations |
| Product CWI concurrency | One |
| New CWI start attempts | 50 after activation, including failed preflights and replacement starts |
| Internal milestones | 1 for bootstrap; at most 3 for a later request, each independently acceptable |
| CWI repairs | At most 2 per review and 6 per run |
| Agent / validation deadlines | 900 seconds per invocation / check; configurable before a new run |
| Same-blocker recovery | At most 2 recovery actions with new diagnostic evidence before escalation |
| Backend maintenance | At most 2 unsuccessful repair candidates for the same diagnosed issue, then stop that maintenance path |
| Session renewals | May reuse the same grant; counters and unresolved liabilities do not reset |
| External purchases | None; no top-ups, subscriptions, or new paid services |
| Product live-provider experiments | Not authorized until an explicit service, data, and usage budget is recorded |
| Destructive Git / pushes / publication | Not authorized by this default |

Count `start` attempts before launching, including attempts that never receive a run UUID. Maintain counters from attempt/run records and reconcile uncertain consumption conservatively. Changing request IDs does not reset a repeated-failure count. A resume is not a new start, but it consumes the same resource allowance and is subject to its recovery bound. Read-only status inspection does not consume a recovery attempt.

The grant may use an existing explicitly approved Codex subscription allowance. API-billed Codex execution requires an actual monetary cap or other explicit spending authorization; do not invent one. CWI's flags bound workflow operations, not token cost, elapsed whole-project time, or provider bills. Record unmeasured usage as unknown; do not claim a hard financial cap without an enforcing provider/supervisor mechanism.

## 6. Stop, hand off, or continue?

Stop for human action when the next necessary operation exceeds authority, the model cannot be resolved, required authentication/permissions are missing, a material requirement conflict exists, side effects or process ownership remain uncertain, evidence integrity fails, the target diverges unexpectedly, a resource limit is reached, or repeated repairs fail. Stop at the commissioning review unless the human explicitly replaced it with preauthorization.

For each hold, report the smallest concrete issue, preserved run/source identities, what is already complete, what was not done, and **exactly one next safe action**. Do not ask the human to decide unrelated details at the same time.

Pause for session/context limits at a clean checkpoint where possible. If CWI is active or acceptance remains bound to the old base, leave the handoff under `local/` without editing tracked parent files. Read-only checks may continue; an absent process or timed-out tool call is not proof of safe termination.

If the next action is independent and authorized, continue instead of treating every backlog entry as a global stop. A required blocked item still prevents declaring the full scope complete.

## 7. Session continuity is not automatic restart

This kit provides prompts and durable records. It does **not** install an external supervisor or promise that a Codex session runs forever. Use the continuation prompt in a fresh session when necessary. Distinguish the outer Codex session ID from the CWI run UUID and from CWI's internal role-session IDs; never resume an arbitrary “last” session across these layers.

An optional future supervisor must itself be implemented through CWI as a separately scoped development utility. It must persist a single coordinator owner/lease, pass the same grant and counters, distinguish complete / runnable / waiting / blocked / uncertain states, use bounded restart backoff, and reconcile active CWI work before restarting. Exit code zero or a final agent message is not sufficient to trigger another run. It must not automatically approve new permissions, purchase credits, replace a human judgment, or replay an uncertain validation. Until that implementation and its recovery tests exist, session restarts remain manual.

## 8. Completion gate

Declare `COMPLETE` only for a named, approved scope and specification revision when:

- Every mandatory requirement in that scope has exact integrated-source evidence and the required tests/reviews; unresolved mandatory obligations are not disguised as optional backlog.
- All CWI work is reconciled, and no result remains accepted-unmerged, uncertain, or awaiting required review.
- Whole-product checks, reproducible clean-environment setup, documentation/navigation, representative workflows, and relevant recovery/security tests pass under the documented conditions.
- Required real-provider or scientific-pilot evidence actually exists. Mocks establish contracts, not real scientific performance.
- Required human scientific judgments and acceptance have been obtained. The coordinator cannot impersonate expert review.
- A completion report links the specification, exact implementation revision, tests, limitations, run records, and backend-change audit.

D10 may remain blocked awaiting live resources or expert review after D01–D09 are delivered. Report `IMPLEMENTATION_SCOPE_COMPLETE; SCIENTIFIC_EVALUATION_PENDING` for an explicitly bounded implementation scope, not “the whole project is complete.” Use the [completion template](templates/COMPLETION.md).
