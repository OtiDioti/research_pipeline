# V0 implementation request: persistent research, scientific opposition and lifecycle control

## 1. Scope and authority

Implement and verify this V0 extension **before attempting M5 again**. It applies
to ordinary investigations and live demonstrations alike.

The extension makes scientific work persist across fresh agent contexts, preserves
running computations during context rollover, and gives completion and stopping
explicit scientific and operational meanings. It incorporates the context and
weekly-quota safeguards already developed in `codex_controller`, adapted to a
multi-agent research investigation.

| Area | Required outcome |
| --- | --- |
| Context lifecycle | Primary and all secondary agents use measured context usage and a 55% rollover threshold, continuing the same logical work through handoffs. |
| Computation lifecycle | Jobs survive context replacement, retain their identity and researcher-selected timeout, and remain within shared resource caps. |
| Weekly quota | The primary's control path monitors account-wide weekly quota; at 15% remaining or less, it invokes investigation-wide STOP directly, bypassing the opponent. |
| Secondary staleness | Each secondary has an inactivity clock reset by measured context-length changes; repeated warnings go to the primary, which chooses the response. |
| Scientific opposition | The same independent opponent challenges results when the primary proposes COMPLETE or scientific STOP. It does not approve research plans. |
| COMPLETE | Primary and opponent agree that all current questions meet the completion requirements; unresolved substantive objections prevent completion. |
| Scientific STOP | The primary hears the opponent's challenge, then decides whether further work is promising or human intervention is needed. |
| Continuity | Explicit resume preserves prior science, incorporates changed questions/evidence/feedback, and safely clears applicable terminal markers. |
| Delivery | Focused engineering checks and representative live evidence establish the new lifecycle before private M5 science resumes. |

Read this request with PROJECT.md, AGENTS.md and STATUS.md. This request supersedes
conflicting earlier requirements concerning investigation/session/demo time
allowances, context thresholds, verification timing and exchange limits,
completion authority, stopping and reopening. Other scientific requirements,
isolation protections, authentication/data-access authority and **human scientific
acceptance of M5** remain binding. Preserve the human-owned PROJECT.md; use this
request as the amendment and align active operational guidance with it.

This document commissions future implementation through the established development
workflow. The present authoring task changes documentation only; it does not launch
implementation, research, the manager, commits or publication.

## 2. Roles and decision authority

- **Primary:** the scientific agent responsible for the whole investigation,
  delegation, synthesis and proposals to finish or stop. The human supervises the
  primary's responsiveness.
- **Secondary researchers:** delegated scientific agents reporting findings and
  blockers to the primary. Their task completion never completes the investigation.
- **Scientific opponent:** a separate agent that independently challenges the
  primary's presented results, including assumptions, derivations, numerical
  evidence, interpretation and conclusions. It is invoked when the primary proposes
  COMPLETE or scientific STOP, rather than as an intermediate plan-approval stage.
- **Runtime:** the deterministic machinery enforcing context rollover, resource
  controls, ownership, cleanup and observable state. Weekly-quota monitoring is
  centralized in the primary's control path; secondary agents do not monitor quota
  or independently decide quota stops.

The scientific opponent is distinct from the engineering project manager and
coding-pipeline code reviewer. Use the same **logical opponent** across subsequent
proposals and revisions, retaining its objections and their disposition. A fresh
context for that opponent must preserve its identity and review history through
artifacts and a handoff. Do not replace it simply to obtain a different verdict.

| Event | Decision and effect |
| --- | --- |
| An agent reaches the context threshold | Runtime replaces that agent's context after handoff; other agents and jobs can continue. |
| A secondary's context length remains unchanged | Runtime warns the primary at the configured intervals; the primary decides what to do. |
| Primary proposes COMPLETE | Opponent challenges the results; agreement on all completion requirements is necessary before finalization. |
| Primary proposes scientific STOP | Opponent challenges the results and proposed stopping rationale; primary decides whether to continue or STOP. |
| Weekly quota reaches 15% remaining or less | Primary's runtime control path invokes STOP for the entire investigation without opponent review or approval. |
| Human requests pause | Runtime fully suspends agents and computations, preserving useful work. |
| Runtime fails | Report the actual operational failure and cleanup state; do not fabricate scientific agreement or a primary-issued decision. |

## 3. Implementation constraints and non-goals

Use a **research-owned Codex app-server driver** alongside scientific coordination.
Reuse or adapt useful telemetry policies, handoff conventions, marker handling and
cleanup mechanisms from the existing projects. Keep research operation independent
of the separate project-manager controller engine and its single-session retirement
policy. Expanding or rebuilding that controller is outside this request.

Prefer existing Python/Linux facilities, controlled tools, ordinary Markdown and
small structured runtime records. Reuse proven local process/service supervision.
Replace superseded timer-based execution paths instead of maintaining competing
lifecycles. Choose module boundaries, exact messages and other ordinary engineering
details autonomously; record consequential choices concisely.

**No backward compatibility is required.** Fresh runtime state may be required.
Reject unsupported old operational state and options clearly. Do not build
migrations, legacy backends, schema adapters, command-option shims or automatic
conversion of expired investigations. Preserve historical scientific artifacts,
inputs and receipts without requiring the new runtime to execute their protocols.

No new database, broker, distributed scheduler, generalized claim registry,
conversation replay system or workflow framework is required. Keep existing
scientific rigor and trust boundaries while simplifying supporting mechanisms.

Remove fixed investigation, researcher-session and live-demonstration work
allowances. Individual computation timeouts and operational RPC/shutdown/cleanup
timeouts remain legitimate. They must not become hidden research lifetimes or
automatic responses to secondary inactivity. A normal model-turn ending, useful
partial progress or elapsed time alone never establishes scientific COMPLETE.

The 55% context threshold and 15% weekly reserve use observed telemetry, following
the established controller behavior. They are deterministic triggers on observed
values, not guarantees against sampling delay, a single large operation or token
use during handoff. Report actual observations and overshoot honestly. Context
occupancy, cumulative token consumption and remaining account quota are distinct.

## 4. Ordered implementation milestones

Use the identifiers **V0-L1 through V0-L6** to distinguish this extension from the
already accepted M1–M4 milestones and the pending M5 benchmark. Deliver in the order
below: durable execution ownership enables safe rollover; those foundations enable
resource controls and scientific decisions; resumption then reconciles their
persistent state. Each milestone inherits the scope limits above.

### V0-L1 — Establish the runtime boundary and durable computation ownership

**Objective:** provide the production execution foundation on which contexts can
be replaced without destroying their scientific computations.

**Required behavior**

- Validate the installed app-server protocol, native tool surface and controlled
  MCP operations within the production isolation boundary. No unisolated fallback
  may stand in for a working production path.
- Keep logical-agent/task identity, ephemeral context identity and owned job identity
  distinct. Track actual ownership using reliable local process/service mechanisms;
  an unchecked PID is insufficient.
- Each researcher chooses an explicit positive finite timeout per computation.
  Durations above 60 seconds, including hours when scientifically justified, are
  supported. Remove the universal 60-second maximum and session-lifetime clamp.
- A job's timeout covers its command and descendants and remains enforceable
  independently of the owning model context. Context replacement neither extends
  the timeout nor restarts the job.
- Support inspection, waiting, cancellation and result retrieval by the owning
  logical agent and its successor context. Waiting must not require repeated model
  turns merely to poll. Useful concurrent research remains possible within caps.
- On job timeout, stop its descendants, retain partial outputs and record the actual
  outcome. Return control to the researcher; do not automatically terminate the
  investigation or silently retry the job.
- Enforce human-configured aggregate memory, process/thread, simultaneous-agent and
  concurrent-job caps. Agents cannot enlarge them. Surviving jobs and replacement
  contexts share allocations. Preserve zero-swap policy, scoped writes, protected
  inputs, frozen verification evidence and exclusion of backend credentials from
  scientific computations.
- Provide reusable investigation-wide admission blocking and owned-process cleanup
  for later STOP/pause workflows. A cleanup failure must remain observable.

**Acceptance**

1. Production-boundary checks establish that intended native tools and controlled
   operations work and unrestricted execution routes remain excluded.
2. A real job remains inspectable under stable ownership after its agent context
   ends; its original timeout still stops the command and descendants.
3. Admission supports durations above 60 seconds. A short expiry exercise preserves
   partial outputs and does not terminate unrelated research. Hours-long tests are
   unnecessary to demonstrate support for hours-long timeouts.
4. Replacement contexts cannot duplicate allocations or bypass isolation/resource
   caps. Cancellation and cleanup evidence reflect actual process outcomes.

**Boundary:** no distributed job system or promise that arbitrary simulations can
checkpoint or resume internally.

### V0-L2 — Continue every logical agent across measured context rollover

**Objective:** replace context lifetimes with measured rollover for the primary,
secondary researchers and scientific opponent.

**Required behavior**

- Observe context usage separately for every active agent. Use the current measured
  context length and usable window, rather than cumulative model-token consumption.
  Adapt the established controller calculation and document its telemetry basis.
- Use **55% usable-context occupancy** as the rollover threshold for all roles,
  including the primary and opponent, superseding the earlier 60% requirement.
  Begin handoff when the observed threshold is reached and preserve headroom for
  saving. Keep any retained human configuration explicit; agents cannot silently
  relax the configured threshold.
- Save useful science and a concise handoff, validate its usability, close the old
  context and create a fresh native context. Preserve logical identity, objective,
  workspace, parent relationship and research/review phase. Automatic compaction
  or whole-conversation replay is not a substitute.
- Handoffs identify completed work, evidence, assumptions, unresolved issues and the
  next action. For jobs, include stable references, purpose, command/configuration,
  working directory, observed status, output/checkpoint locations and how to inspect
  or stop them. The successor reconciles actual jobs before launching replacements.
- An individual rollover leaves other agents and running computations active within
  the same resource allocations. Normal turn completion does not automatically
  finalize an investigation or discard unfinished logical work.
- Report missing/unreliable context telemetry and recover it where possible. Do not
  substitute fixed session timers or continue indefinitely without measurement.
  If continuation cannot be made safe, preserve available work and report the actual
  operational failure rather than inventing a scientific STOP decision.

**Acceptance**

1. Each role independently triggers rollover from its own measured context usage;
   activity in one agent does not reset or substitute another agent's measurements.
2. Fresh native contexts continue the same logical tasks from validated handoffs.
   The opponent retains prior objections and its current review phase.
3. A real computation spans a context replacement with the same job identity,
   outputs, original timeout and allocation; its successor collects it without
   duplication while another agent can continue working.
4. Missing telemetry and unusable handoffs produce truthful recovery/failure states,
   rather than false claims of successful continuation.

**Boundary:** do not implement timer-driven session retirement, compaction-only
continuation or full conversation reconstruction.

### V0-L3 — Enforce weekly reserve and report secondary staleness

**Objective:** protect the shared weekly quota and inform the primary about inactive
secondary contexts without imposing scientific time budgets.

**Weekly-quota control**

- Only the **primary's deterministic control path** monitors the account-wide weekly
  allowance. The value covers shared account consumption, including secondary work;
  it is not a private allocation for the primary or a fresh grant per context.
- Incorporate the existing controller's **15% weekly quota remaining** safeguard.
  Read quota before admitting research and refresh it during operation using the
  existing polling/event approach. Recognize the actual weekly window; preserve
  correct handling of multiple quota buckets and incomplete notifications.
- At **15% remaining or less**, latch an investigation-wide STOP, prevent new work,
  save handoffs where possible, and interrupt agents and simulations using the
  common STOP cleanup path. **Do not invoke or await the opponent.** The runtime
  must enforce this even if the primary would prefer to continue research.
- A later quota refresh must not silently undo the stop. Resume requires an explicit
  launch and successful quota preflight. Context rollover never resets quota policy.
- Reuse the controller's refusal to admit further research when required weekly
  telemetry is unavailable. Preserve the distinction between an observed quota
  cutoff and a telemetry failure, including in terminal output and saved status.
- Do not promise that exactly 15% remains after saving and cleanup. Report observed
  quota, the trigger and any limitations honestly. Secondary agents do not each poll
  account quota or independently invoke quota stops.

**Secondary staleness**

- Each newly started secondary context, including the opponent's, receives a fresh
  inactivity clock. Any **metered context-length change** resets that clock, whether
  the length increases or decreases. A repeated unchanged measurement does not.
- With no measured length change, warn the primary at every multiple of a configurable
  interval: **2700, 5400, 8100… uninterrupted seconds by default**. Issuing a warning
  does not reset the clock. A fresh successor context starts a fresh countdown.
- Report the affected agent and elapsed staleness. The primary chooses whether to
  wait, investigate, redirect, interrupt or take another appropriate action.
  A long computation can legitimately cause a warning; the warning asserts no
  scientific failure. Missing telemetry remains a separate operational condition.
- Do not automatically stop, restart or replace an agent merely because this clock
  expires. Do not add a primary-staleness watchdog: **the human controls the primary**.

**Acceptance**

1. Boundary tests cover quota above, exactly at and below 15%, missing weekly data,
   quota changes during a rollover and rejection of launches without sufficient
   allowance. The guard is centralized and includes shared account usage.
2. A quota stop bypasses scientific review, blocks new work, interrupts owned agents
   and jobs, and retains useful handoffs with honest cleanup results.
3. Controlled-clock tests establish independent secondary timers, resets only on
   measured changes or fresh contexts, and repeated warnings at interval multiples.
4. Staleness warnings alone never stop work; primary inactivity has no automatic
   staleness policy.

**Boundary:** no per-secondary quota allocation system, autonomous quota-reset
restart or automatic scientific-progress scoring.

### V0-L4 — Implement scientific opposition, COMPLETE and scientific STOP

**Objective:** challenge scientific results before terminal decisions and encode
precisely who can authorize each outcome.

**Opponent workflow**

- When the primary proposes COMPLETE or scientific STOP, present the current
  questions, results, assumptions, relevant evidence and reasons for the proposed
  outcome to the independent opponent. Freeze the reviewed evidence versions.
- The opponent examines results and performs proportionate independent reasoning,
  reproduction or counterchecks of consequential claims. It may identify errors,
  limitations, missing evidence or useful further investigations. It does not
  approve or reject mere plans. This final opposition workflow must retain the
  required scientific rigor rather than reducing verification to report formatting.
- Invoke the opponent at these decision points, not continuously for intermediate
  results. Researchers remain responsible for their own ordinary checks during
  research. Use the same logical opponent when revised results return for review,
  subject to the same 55% rollover and secondary-staleness behavior.
- Preserve objections, primary responses, counterevidence and resolutions in ordinary
  scientific Markdown. Remove the old single-response/single-re-examination ceiling
  as a restriction on resolving the investigation. Repeated review must remain
  possible; exhausting a fixed number of rounds never authorizes COMPLETE.

**COMPLETE**

- For **every current research question**, the primary presents an adequate answer
  or an adequate reason/demonstration that it cannot be answered. Primary and opponent
  must agree that the usual completion requirements are satisfied. Scientific
  adequacy remains their judgment; structural checks do not certify correctness.
- Negative and inconclusive findings can qualify. A flawed claim may be corrected
  or withdrawn and replaced with a supported negative/inconclusive finding, provided
  both agents agree that the resulting account satisfies the requirements.
- An unresolved substantive flaw or disagreement over those requirements prevents
  COMPLETE. The primary must continue research or pursue STOP. Marking a central
  result disputed, recording an objection or declaring further work unpromising
  cannot substitute for agreement on completion.
- Only the primary requests final COMPLETE, after both agree. Record question
  coverage, evidence paths, the opponent's findings and the agreement against the
  actual reviewed versions. Material changes invalidate pending agreement and
  require reassessment.
- Reconcile unfinished delegated tasks and stop remaining computations before
  finalization. The COMPLETE acknowledgement requires successful finalization and
  confirmed cleanup. Scientific COMPLETE does not establish human M5 acceptance or
  engineering-repository completion.

**Scientific STOP**

- The primary proposes STOP as a last resort after its best autonomous recovery
  efforts when continued work requires human intervention. Delegates report blockers
  to the primary; they cannot issue investigation-wide scientific STOP.
- The opponent challenges the presented results and stopping rationale and may
  suggest further work. **The primary retains the STOP decision.** If it judges the
  proposed continuation unpromising, it may STOP while recording that judgment and
  the opponent's unresolved objection. Opponent agreement is not required for STOP.
- Do not prescribe arbitrary retry counts or a catalogue of scientific blockers.
  Preserve actual attempts, limitations and reasons. Runtime quota STOP remains the
  explicitly separate path that bypasses this scientific exchange.

**Common finalization**

- Use scientific-project-root COMPLETE/STOP markers and matching acknowledgements
  alongside runtime state. Identify whether STOP came from the primary's scientific
  decision or the quota safeguard. Never attribute a runtime failure to an agent.
- STOP blocks new admissions and interrupts **all owned agents and simulations**.
  Save useful partial work and confirm owned-process cleanup. Reuse existing
  checkpoint and cleanup mechanisms where suitable; merely waiting for a model turn
  to end is insufficient evidence that simulations stopped.
- Record the reason, review outcome where applicable, recovery attempts, unfinished
  questions/jobs, retained artifacts/checkpoints, actual interruption state, required
  intervention and continuation instructions in RESEARCH_STATUS.md and handoffs.
- If preferred checkpointing fails, preserve the stopping explanation in STOP and
  terminal output wherever possible. The failure must not disable cleanup. Issue a
  success acknowledgement only after finalization and cleanup are confirmed; never
  claim stopped processes or a valid handoff without evidence.

**Acceptance**

1. COMPLETE is rejected while a substantive objection remains; revised supported
   findings can reach COMPLETE after agreement by both agents.
2. The same opponent follows successive proposals across context replacements;
   changed evidence cannot inherit stale agreement. No plan-approval stage appears.
3. Scientific STOP includes opponent challenge, but the primary can reject an
   unpromising suggestion and stop with the reasoning preserved.
4. Quota STOP proceeds without opponent participation. Delegates, normal turn endings
   and exhausted review rounds cannot bypass the decision rules.
5. Real cleanup checks cover agents and descendants, partial-output retention and
   truthful failure handling when checkpointing or cleanup cannot be confirmed.

**Boundary:** no forced consensus, primary override of COMPLETE disagreement or
separate reviewer permission to enforce the weekly reserve.

### V0-L5 — Resume, reopen and recover without losing scientific continuity

**Objective:** preserve useful work and human direction across stops, pauses,
completion and operational failures.

**Required behavior**

- After STOP, explicit resume acquires exclusive investigation ownership, checks
  prerequisites including quota, and carries the stopping handoff into the successor.
  Clear STOP and its acknowledgement only after successful preflight. Help,
  inspection, rejected concurrent launches and failed preflight preserve the stopping
  explanation. Resumption does not assert that the prior blocker has been solved.
- After COMPLETE, explicit resume reopens research when authoritative questions,
  relevant evidence/documentation or human feedback have changed. Clear COMPLETE
  and its acknowledgement safely, retain the earlier scientific record, and
  **highlight the changed documentation and its implications** in resumed intake
  and research status. Questions need not change for new evidence or corrective
  feedback to invalidate the previous completion decision.
- Reassess affected results while retaining unaffected work. If no relevant inputs
  have changed, report the existing completion state rather than silently repeating
  the investigation. A reopened investigation must satisfy the normal opponent and
  completion requirements again.
- Reread current research instructions and feedback at intake/resumption. Detect
  relevant human edits at checkpoints and before overwriting affected scientific
  Markdown; preserve and incorporate them. Use lightweight change detection rather
  than continuous watching or generalized dependency invalidation.
- A human pause remains full suspension of agents and computations with handoffs;
  no job intentionally remains active after successful pause. On resume, reconcile
  actual job outcomes and retained outputs before deciding whether to restart work.
  Do not claim a killed simulation continued or can resume internally without support.
- On a controller crash, retain known identities/artifacts, reconcile actual ownership
  and cleanup before replacement admissions, and recover from usable checkpoints.
  Job timeouts remain independently enforceable. Do not leave unconstrained agents
  after controller failure or silently duplicate computations on restart.
- Some work since the last checkpoint may be lost. Report that limitation and any
  missing handoff or uncertain cleanup rather than promising exact replay.

**Acceptance**

1. STOP and its explanation survive failed and rejected launches; successful explicit
   resume carries the handoff forward under exclusive ownership.
2. Separate cases reopen COMPLETE for changed questions, new evidence and corrective
   feedback with unchanged questions. Changed documentation is highlighted and
   unaffected findings survive. Unchanged intake remains complete.
3. Pause stops all owned computation; resumed decisions reflect actual retained
   outputs and job outcomes. Human edits are preserved.
4. Representative crash/restart checks show no duplicate admissions or unconstrained
   surviving work and truthful accounting of uncertain or lost progress.

**Boundary:** no automatic resume merely because quota resets, exact event replay or
migration of historical runtime state.

### V0-L6 — Validate the integrated lifecycle and prepare the next M5 attempt

**Objective:** demonstrate the new V0 behavior through the production path before
spending another private M5 attempt on it.

**Required delivery and evidence**

- Combine focused deterministic checks for consequential decision/failure/race cases
  with real process checks for job survival, timeout enforcement and interruption.
  Keep live inference gates disabled during routine engineering checks.
- Run a representative live investigation with public/test inputs through the actual
  app-server, isolation, controlled tools and scientific decision path. Demonstrate
  useful science, context continuation, computation continuity and independent
  opposition leading to an honest terminal outcome.
- Exercise primary, secondary and opponent rollover, agreement and disagreement,
  scientific STOP, quota STOP without review, staleness warnings, cleanup and
  reopening with the appropriate mixture of live evidence and focused tests.
  Transparent telemetry/clock fixtures may exercise thresholds; do not deliberately
  exhaust an account, wait hours merely to test an interval, or manufacture scientific
  results or reviewer agreement. Label fixture evidence separately from live science.
- Use the ordinary research lifecycle without an outer scientific work timer.
  Operational fixture/RPC/shutdown/cleanup bounds may constrain an engineering test;
  hitting such a bound is an interrupted/failed test, never scientific COMPLETE.
- Update active requests, usage documentation and directory indexes to describe the
  new lifecycle and supported state. Clearly reject unsupported old operational state
  while leaving historical science and receipts intact.
- Preserve and reconcile the reviewed, unmerged M5 candidate identified in STATUS.md,
  including useful workspace, handoff and harness changes. Adapt its harness to the
  new lifecycle rather than reusing old timed behavior. Do not approve the previous
  blocked run merely to unblock integration or relabel old evidence as new validation.

**Acceptance**

1. The production-path live evidence and focused checks collectively cover V0-L1–L5;
   a small cohesive example is sufficient. Accepted paid M1–M4 demonstrations need
   not be repeated merely to reconstruct history.
2. Reports distinguish scientific findings, operational outcomes, deterministic
   fixtures, live observations and unresolved limitations. Cleanup is evidenced.
3. The updated M5 harness and preserved candidate are reconciled through the supported
   development workflow, with actual refs, reports and remaining gates in STATUS.md.
4. Only then may M5 proceed with its protected inputs, scientific requirements and
   existing execution authority. **Human scientific acceptance remains mandatory.**

**Boundary:** lifecycle acceptance does not accept the old M5 science, merge an
unfinished candidate indiscriminately or establish scientific competence by test
counts alone.

## 5. Development ownership and handoff

The manager first inspects current Git/pipeline state and preserves human edits,
retained candidates, scientific inputs and historical receipts. Recorded refs in
STATUS.md are recovery anchors, not instructions to reset or blindly merge work.

Commission the milestones through the established `coding_pipeline` workflow.
Implementation, consequential tests, independent code review and live validation
belong to that pipeline. The manager assesses its reports and maintains the
management checkpoint; it need not independently repeat completed product tests.
Keep lifecycle integration distinct from unfinished M5 scientific acceptance.

Each milestone handoff records the implementation reference, relevant checks and
observations, remaining limitations and the next dependency. Choose cohesive
increments within these milestones without creating redundant requirement ledgers
or speculative subsystems. Preserve the existing benchmark workspace and private
input/publication permissions. This request adds no authority to disclose private
materials or enlarge human-configured resource caps.
