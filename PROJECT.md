# Autonomous Scientific Research Pipeline

**Status:** Draft product specification for a clean implementation restart  
**Initial platform:** Python on Linux, with Codex CLI as the first research-agent backend  
**Scope:** The five first-release milestones in §10; the future directions in §11 are not authorized implementation work

## 1. Purpose

Build a **researcher-directed, substantially autonomous scientific investigator**. A human supplies a research objective and, optionally, existing evidence and project-specific instructions. The system independently frames the problem, investigates relevant literature, develops hypotheses and methods, performs analytical and computational work, checks consequential results, and writes useful scientific findings. It should not require the human to supervise intermediate steps.

The product is **discipline-agnostic**. It must not hardcode workflows, scientific methods, or evidence standards for any particular field. Scientific strategies and tools should be chosen according to the problem. The system should pursue original, potentially publishable contributions without treating novelty as guaranteed or discounting valuable negative results, replications, or improvements to existing understanding.

**Success means scientific usefulness, not architectural completeness.** Research artifacts should enable a human scientist to evaluate what was done, reproduce important calculations, understand limitations, and continue the investigation.

## 2. First-release boundary and initial scientific benchmark

The first release (V0) must demonstrate a complete, usable research workflow. It does not need to solve an open scientific problem or produce a publishable discovery.

**Initial scientific benchmark:** Investigate **light-hole spin qubits confined in Ge-rich quantum wells, coupled to resonators**, extending the relevant light-hole-qubit literature, including the work by Valvo and collaborators identified by the researcher. The investigation must include both (a) substantive analytical derivation of effective models and (b) meaningful numerical study of those models. The exact research questions, starting papers, model assumptions, and constraints will be supplied through the project's `starting_evidence/RESEARCH_QUESTIONS.md` and any additional starting materials. This benchmark tests general-purpose research capabilities; it must not produce physics-specific infrastructure in the platform itself.

The benchmark should demonstrate literature assessment, autonomous planning, computational experimentation, reasoned decomposition and delegation, independent checking, documented conclusions, pausing and resuming, and adaptation to updated research questions. **The human scientist judges scientific competence.** Automated tests judge engineering correctness.

V0 deliberately excludes a custom graphical interface, a distributed platform, universal scientific claim databases, advanced model routing, elaborate message queues, and general-purpose scientific workflow engines.

## 3. The scientific investigation lifecycle

Each project represents **one evolving investigation** that may span many sessions and contain many related questions and dependent subproblems. Distinct investigations use separate project directories, while relevant scientific knowledge can be shared across accessible projects.

### 3.1 Start and frame a problem

- The authoritative user-maintained statement of objectives is `starting_evidence/RESEARCH_QUESTIONS.md`.
- At the start of an investigation, read that file, inspect relevant starting evidence, and read the project's optional `AGENTS.md`.
- Translate broad natural-language questions into a concrete, revisable research plan without requiring the user to supply an implementation-grade specification.
- Make reasonable assumptions explicitly and proceed. Ask the human only when an ambiguity fundamentally changes the scientific objective or makes meaningful work impossible.
- Treat user-provided materials as scientific inputs to evaluate critically, not as infallible evidence.

### 3.2 Investigate autonomously

- Select promising lines of inquiry, revise priorities, and abandon unproductive approaches when justified.
- Search for, retrieve, and assess relevant scientific literature throughout the investigation, not only at intake. Examine primary sources and supplementary materials when available; distinguish full-text examination from abstract-only or secondary-source knowledge. Respect access restrictions.
- Develop hypotheses, analytical arguments, derivations, approximations, numerical experiments, and appropriate methodological checks.
- Write, execute, debug, and revise scientific code directly in the project's permitted execution environment.
- Identify dependencies between questions, create subproblems when needed, and integrate their findings into the parent investigation.
- Preserve useful partial results, failed approaches, open questions, and uncertainties. Do not confuse an unsuccessful hypothesis with an unsuccessful investigation.
- Evaluate scientific novelty against the available literature; distinguish results new to the project from claims plausibly new to the field.

### 3.3 Stop at a meaningful point

The researcher may conclude, checkpoint, or stop when it has made useful progress and further work is not currently justified, the assigned resources are exhausted, or it encounters a genuine blocker. Report meaningful partial findings even if the objective is unresolved. It must be possible to interrupt, redirect, and resume the investigation without resetting scientific progress.

## 4. Scientific quality, verification, and provenance

**Scientific rigor is a product requirement.** Avoid overengineering the infrastructure used to support it.

### 4.1 Independent checking

Consequential conclusions receive **independent verification proportional to their significance and uncertainty**. Verification is performed by a **separate Codex agent session**, not by asking the original researcher simply to approve its own work.

The verifier receives the claim, assumptions, relevant sources, and reproducible artifacts, but need not inherit the researcher's entire reasoning history. It should attempt an independent reconstruction or challenge; alternative approaches are preferred when feasible. Checks may include:

- Analytical work: mathematical correctness, assumptions, approximation regimes, consistency, and limiting cases.
- Numerical work: reproducibility, convergence, stability, parameter sensitivity, and comparison with analytical results where appropriate.
- Literature-based statements: direct support from the cited material and appropriate qualification of inaccessible or partial sources.
- Novel conclusions: critical comparison with existing work, alternative explanations, and limitations.

A verifier may request additional calculations or corrections. Disagreements are handled through a **bounded** exchange: documented objection, response/revision, re-examination, and an additional targeted test if justified. If disagreement remains unresolved within the budget, preserve the opposing arguments and mark the claim **disputed**. Do not force consensus or block unrelated research.

Exploratory ideas and provisional findings can be reported without exhaustive verification, but must be labeled appropriately. Distinguish **preliminary**, **checked**, **disputed**, and **superseded** findings; use scientific explanation, not a complex universal claim-status database, to support the labels.

### 4.2 Artifact-centered provenance

For each consequential result, preserve enough information to understand and reproduce it:

- Assumptions, domain of validity, and important approximations.
- Supporting derivations, sources, calculations, and relevant earlier findings.
- For computational results: code, inputs, parameters, relevant software/dependency versions, random seeds where applicable, and enough instructions to rerun the work.
- Verification outcome, limitations, and unresolved objections.

Use ordinary Markdown links and small pieces of structured metadata when useful. The researcher reasons about affected downstream conclusions when assumptions change. **Do not build a universal claim graph, automatic invalidation engine, or event-level provenance system for V0.**

## 5. Project workspace and scientific artifacts

Projects are ordinary, portable directories. Their contents must remain intelligible without opening agent conversation logs or a proprietary database.

An illustrative minimal layout is:

```text
<research-project>/
├── AGENTS.md                         # Optional, user-owned research instructions
├── FOLDER_CONTENT.md                 # Automatically maintained directory index
├── RESEARCH_STATUS.md                # Current scientific status and next directions
├── starting_evidence/                 # User-owned, read-only to agents
│   └── RESEARCH_QUESTIONS.md         # Authoritative evolving questions
├── sources/                           # Retrieved papers and reference materials
├── work/                              # Agent workspaces, derivations, code, data
├── outputs/                           # Reports, figures, validated results
└── handoffs/                          # Unfinished agent work and resume guidance
```

Only the minimal top-level conventions are standardized. Subdirectories under `sources/`, `work/`, `outputs/`, and `handoffs/` are created as needed according to the scientific problem. Do not create empty directory hierarchies or force a physics-specific arrangement onto other disciplines.

### 5.1 Starting evidence and human-owned files

- `starting_evidence/` contains original user-provided notes, papers, code, datasets, and `RESEARCH_QUESTIONS.md`. Agents **must not modify or delete** anything within it. They may make working copies elsewhere.
- The human may change the research questions or any other starting material between sessions. **The latest `RESEARCH_QUESTIONS.md` is authoritative** at the next intake or resumption.
- The optional project-root `AGENTS.md` is also human-owned and read-only to agents. Explicit restrictions are binding; methodological preferences normally apply, but an agent may deviate for a compelling scientific reason if it documents the departure. Project instructions cannot override platform security limits.
- Scientific sources, including papers and user notes, are evidence to analyze; they do not confer operational authority to issue agent instructions.

### 5.2 Navigability and Markdown requirements

- **All agent-written scientific notes and reports must be Markdown (`.md`)**. Write mathematical expressions in LaTeX within Markdown. Code, datasets, figures, source papers, and other non-note artifacts may keep suitable native formats.
- Every agent-managed directory must contain an automatically maintained `FOLDER_CONTENT.md` listing its immediate files and subdirectories, each with a concise, useful description. This is a navigation aid, not a scientific knowledge graph.
- To preserve the read-only rule, **`starting_evidence/` is exempt from agent-written indexes**. Its contents should be discoverable through the parent directory's index or a generated index stored *outside* `starting_evidence/`.
- Maintain indexes as agent-managed files change and reconcile them at checkpoints. Continuous filesystem monitoring is not required.

### 5.3 Required scientific deliverables

Maintain substantive documentation continuously rather than reconstructing it from conversation history at the end:

1. **Research status:** Objectives, progress, active questions, blockers, and next steps.
2. **Scientific notes:** Derivations, assumptions, hypotheses, reasoning, intermediate results, and failed approaches worth retaining.
3. **Computational artifacts:** Reproducible scripts, data, figures, parameter settings, and usage instructions.
4. **Conclusions:** A readable synthesis distinguishing established, preliminary, negative, disputed, and unresolved results.
5. **Supporting evidence:** Citations and links to relevant source materials, calculations, and verification work.

Do not generate exhaustive transcripts, ceremonial reports, or documentation for every trivial agent action. Operational diagnostics may exist separately but do not substitute for scientific notes.

## 6. Researchers, subproblems, and coordination

A **single primary researcher** is responsible for planning, conducting, and synthesizing the investigation. It may recruit additional Codex agent sessions when doing so has an identifiable scientific benefit, such as an independent check, a competing hypothesis, or a dependent subproblem.

Research decomposition can be recursive: resolving one question may require resolving several other questions, each of which may have further dependencies. **A hierarchy of scientific questions does not imply a permanent hierarchy of agents.** The primary researcher coordinates resource allocation and final integration.

- Delegated researchers have their own working directories and can read relevant shared scientific materials.
- Subagents normally write to their own directories rather than directly modifying common synthesis documents.
- The primary researcher integrates their substantive findings into shared notes and conclusions.
- Independent verifiers inspect supporting artifacts without editing the original research they are checking.
- The primary researcher mediates requests for assistance and information exchange in V0. A peer-to-peer message board is not required.

Every unfinished delegated investigation must have a concise Markdown handoff in `handoffs/`: objective, relationship to the parent question, progress, artifacts, uncertainties, remaining steps, and whether it should be resumed or reconsidered. Handoffs are **scientific and operational summaries**, not copies of complete model conversations.

### 6.1 Automatic context rollover (required in V0)

**An agent's scientific task must outlive its individual Codex context window.** Every active research agent, including the primary researcher, delegated researchers, and independent verifiers, must be able to continue its logical task in a fresh Codex session without restarting the investigation. Context rollover is distinct from pausing an entire project or exhausting its resource budget.

- **Delegated agents (including verifiers) have a context-usage ceiling of 60% of their usable context window per Codex session.** They must start a safe handoff and roll over **at or before 60%**, not wait for automatic compaction or near-exhaustion at 100%. The controller should reserve sufficient headroom for the handoff and avoid launching a turn predicted to cross the ceiling. The initial primary researcher may use the same conservative 60% default; its limit should remain configurable.
- Track context occupancy **for each live session separately**, using Codex-provided context-window and token information when reliable. **Cumulative model-token consumption is not context occupancy.** If the backend cannot expose a reliable figure, use a conservative documented estimate or shorter fixed session budget and **do not claim an exact 60% guarantee**.
- Before rollover, the agent saves useful scientific work to its ordinary project files and updates its concise `handoffs/` Markdown file: stable logical-agent ID, objective and parent subproblem, completed work, artifact paths, essential assumptions, unresolved issues, the next concrete action, and any interrupted computation. Keep detailed derivations and evidence in scientific artifacts rather than bloating the handoff.
- The controller confirms that usable handoff/artifact files exist, then closes the old Codex session and starts a **new session with fresh conversation context**. Supply the applicable project instructions, current research questions, handoff, and paths to relevant artifacts; do not rely exclusively on resuming or compacting the old conversation.
- Preserve the logical agent ID, task ownership, workspace, and parent-child relationship across sessions. The parent researcher continues other work where possible and incorporates the resumed subagent's eventual findings normally. Research, tool, and model budgets remain **cumulative across rollovers**; resetting context does not reset spending or investigation limits.
- If an attempted rollover fails, recover from the latest valid handoff/checkpoint and report missing work or telemetry limitations. Do not create a generalized event-replay system or save complete conversation histories.

The same lightweight handoff/resume mechanism should underpin graceful pausing and interruption recovery where appropriate. Test continuation of actual scientific work after a forced rollover, not only the threshold arithmetic.

## 7. Scientific tools, execution, and resources

### 7.1 General-purpose scientific tooling

The researcher must be able to choose methods, install appropriate dependencies, write and run scientific code, debug failed computations, develop new techniques, and reuse helpful tools. Scientific scripts **do not** pass through `coding_pipeline`; that mechanism develops the *research platform*, not calculations performed *by* the platform.

Support both user-supplied tools and tools independently discovered or developed by agents. A reusable tool should have a concise description of its purpose, invocation, dependencies, and relevant checks. Validate newly acquired tools sufficiently for their intended use before placing them in the reusable collection. Prefer an initially simple way to expose Python functions, scripts, and command-line programs; do not build a general plugin marketplace or complex qualification framework.

### 7.2 Local-first, bounded execution

- Implement the orchestration layer in **Python on Linux**. Use **Codex CLI** as the initial research-agent backend, with a small boundary that allows another backend to be integrated later if needed.
- Allow broad scientific activity within an **isolated workspace** and a configurable budget: code execution, dependency installation, network literature access, local CPU/GPU work, and permitted scientific file operations.
- Require explicit human authorization for access to protected files, modifications outside permitted workspaces, external disclosure of private information, or significant computational/financial overruns.
- Use existing, proven isolation and execution mechanisms where adequate; do not create a bespoke sandbox or security framework without demonstrated need. Never assume a protection is enforced if the chosen backend cannot actually enforce it.
- Set per-investigation limits, optionally inherited from global defaults: wall-clock duration, reliably measurable model usage or spending, compute-job runtime and concurrency, and simultaneous agent count. The primary researcher allocates the available budget to subproblems.
- When a limit is reached, preserve useful work, report progress, and stop or request additional authorization. Where model usage cannot be measured or capped reliably, disclose that limitation instead of claiming a hard limit.

Remote clusters, remote GPUs, and cloud execution are not prerequisites for V0.

## 8. Human interaction, edits, and continuity

### 8.1 User-facing controls

V0 uses a **CLI and the Markdown workspace**. The CLI must let a user start, inspect, pause, resume, and redirect an investigation and submit scientific feedback. The files must be readable in ordinary editors, including Obsidian. A custom graphical interface is deferred.

The user may also provide feedback through a dedicated user-maintained Markdown file. Feedback can correct assumptions, ask new questions, or propose methodological changes; it remains distinguishable from agent-generated scientific conclusions.

### 8.2 Incorporating changes

On resumption, reread `starting_evidence/RESEARCH_QUESTIONS.md`, project `AGENTS.md`, and new user feedback. Identify added, revised, or removed objectives, adapt the plan, retain unaffected findings, and reconsider work whose assumptions no longer hold. Do not restart the whole investigation merely because the objectives changed.

The human may edit **any agent-generated scientific Markdown file**. Agents must detect relevant external modifications at checkpoints, when resuming, and before overwriting affected files. Do not silently overwrite human edits. Treat them as authoritative input to incorporate while still assessing their scientific implications. Use lightweight file-change detection and selective preservation of superseded versions; continuous filesystem watching and elaborate collaborative revision systems are unnecessary.

### 8.3 Pause, crash recovery, and resumption

A requested pause is a **full suspension**: stop launching work, checkpoint relevant progress, gracefully stop agents and computational jobs where feasible, and update active-agent handoffs. No job should intentionally continue after a successful pause. On resume, reconstruct what to do from the project files, status, and handoffs. Restart computations that cannot resume internally. **Automatic context rollover, in contrast, replaces only the affected agent session; it does not pause the whole investigation.**

Unexpected crashes are handled by **lightweight checkpoint-based recovery**. Some work since the last checkpoint may be lost. Preserve finished artifacts, avoid unnecessary repetition, and identify interrupted tasks; **do not guarantee exact replay of conversations or every intermediate action**.

## 9. Persistent scientific memory

Scientific knowledge should be discoverable and reusable across accessible projects, including notes, derivations, literature, computational methods, negative results, and reusable scripts.

V0 retrieval uses directory indexes, filesystem navigation, and full-text search. Agents apply their own reasoning to the retrieved material. Retrieved knowledge retains its source, assumptions, limitations, and verification status. **Retrieval is not endorsement:** unverified claims can guide investigation but must not silently be treated as facts; verified results must still be checked for applicability in a new context.

Provide a simple, extensible boundary for search and tool retrieval. Embeddings, vector databases, and automatic universal semantic indexing are future possibilities, not V0 requirements.

## 10. Required development milestones and acceptance

Development must advance by **demonstrated scientific functionality**, not by infrastructure completion, code volume, or number of passing tests. Each milestone must pass focused automated checks **and a representative functional demonstration** before the autonomous product manager proceeds. Build only what the current milestone needs, unless an earlier dependency is unavoidable.

### M1 — Minimal scientific loop

**Deliver:** A Codex research session reads `RESEARCH_QUESTIONS.md` and available starting materials, forms a plan, consults relevant literature, performs at least one substantive scientific reasoning task and executable computation, and writes readable Markdown results with supporting artifacts. The CLI starts and inspects the investigation. Basic workspace boundaries and essential resource protections apply from the beginning.

**Demonstrate:** An actual short research run completes a meaningful question-to-artifact workflow. Mocked orchestration tests alone are insufficient.

### M2 — Persistence and human direction

**Deliver:** Checkpointing, pause/resume, crash recovery at checkpoint granularity, **context rollover for the primary researcher**, user feedback, human edits to notes, reloading `RESEARCH_QUESTIONS.md` and project `AGENTS.md`, and preservation of unaffected results. Folder indexes remain correct and navigable.

**Demonstrate:** Pause and resume a live investigation; update its questions and a scientific note while stopped; observe an appropriate plan revision without unnecessary loss of prior work. Force a context rollover and confirm the new Codex session continues the same logical research task from saved scientific artifacts and a handoff.

### M3 — Collaboration and independent verification

**Deliver:** Subproblem decomposition, selective delegated research agents with separate working areas, unfinished-work handoffs, **automatic context rollover at or before 60% context occupancy for each subagent and verifier**, a separate independent verifier, bounded disagreement handling, and integration of subordinate results.

**Demonstrate:** A research task genuinely delegates a dependent subproblem, incorporates its output, and receives an independent verification challenge. Force a delegated agent to roll over at its 60% threshold; verify that its fresh Codex session recovers the same task and artifacts without stopping the primary investigation or resetting cumulative resource budgets.

### M4 — Cross-project knowledge and reusable tools

**Deliver:** Navigation and full-text retrieval across accessible projects, scientifically qualified reuse of prior results, simple registration and reuse of user-supplied and agent-developed tools, and the remaining V0 reporting and budget controls.

**Demonstrate:** A new investigation finds and critically uses a prior project's artifact or reusable tool without treating unverified material as established fact.

### M5 — Real scientific acceptance

**Deliver:** A complete live investigation of the **Ge-rich quantum-well light-hole spin-qubit/resonator** benchmark, including substantial analytical and numerical work, relevant literature analysis, independent criticism, scientific documentation, and evidence of multi-session continuity and response to changed research questions.

**Acceptance is separate:**

- **Engineering:** The product manager establishes that required functionality works through automated tests and end-to-end runs. It must correct deficiencies before marking an engineering milestone complete.
- **Science:** The human researcher reviews actual derivations, assumptions, calculations, reproducibility, physical interpretation, literature treatment, and clarity of uncertainty. The independent verifier informs this judgment but cannot certify overall scientific competence by itself.

Scientific novelty is desirable but **not a pass/fail condition**. Failure to discover new physics does not invalidate a scientifically competent investigation. **Human scientific acceptance is required for M5.**

## 11. Nonbinding future directions

The following ideas are **out of scope for V0**. They do not authorize speculative infrastructure or implementation without a subsequent approved change to this specification:

- Additional LLM/API backends, role-specific model routing, and sophisticated model-selection policies.
- Direct peer-to-peer agent messaging or a research-agent message board.
- Semantic/vector retrieval, embeddings, and advanced literature-knowledge indexing.
- Scheduled monitoring of newly published papers and other user-provided background research tools.
- Remote computing, HPC or cloud execution, and jobs that keep running during an investigation pause.
- A custom graphical interface and multiple independent investigations managed inside a single project.
- Universal scientific knowledge graphs, automatic claim-dependency invalidation, elaborate event replay, or generalized workflow engines.

## 12. Autonomous **development** policy (distinct from research behavior)

This section is binding on the Codex **product manager** and the development requests it issues to `coding_pipeline`. It governs how the *platform* is built; it does not limit agents' freedom to write ordinary scientific code within their research projects.

### 12.1 Preserve existing development machinery

The clean restart retains the existing broad technique, rather than rebuilding it:

1. A deterministic controller starts product-manager Codex sessions and sends startup/stop prompts based on token usage.
2. The Codex product manager decides the next approved implementation increment.
3. **Every change to platform code** is delegated to the existing `coding_pipeline`, which owns implementation-level testing and code review.
4. The product manager independently checks the resulting user-visible capability, preferably with a practical run, and conducts milestone demonstrations.
5. The product manager records progress and a concise handoff before stopping; the next session recovers unfinished work safely.

The controller and `coding_pipeline` already exist. **Rebuilding or expanding either is not a product milestone.** Focus changes on their instructions and small, unambiguous project-management Markdown files. Reuse old product code only when it demonstrably simplifies the new implementation; retaining compatibility with the old architecture is not a requirement.

### 12.2 Minimal development documentation

Use a small set of authoritative files with non-overlapping purposes:

| Path | Purpose |
| --- | --- |
| `project_description.md` | Approved product behaviors, scope, constraints, and acceptance criteria (this document). |
| `AGENTS.md` | Instructions to the development Codex product manager, including delegation, authority, stopping, and validation. This is **not** the project-specific research `AGENTS.md`. |
| `ROADMAP.md` | Milestones, acceptance gates, and their current progress. |
| `STATUS.md` | Current state, active request, blockers, most recent validated results, and next action; primary session handoff. |
| `development/requests/` | Concise individual implementation requests, outcomes, and notable architectural decisions. |

Use Git for detailed code history. Do not maintain parallel requirement ledgers, long development journals, duplicated handoffs, or redundant acceptance records. The product manager may update `ROADMAP.md`, `STATUS.md`, and requests within approved scope. It may clarify non-substantive wording in this specification but must not silently add features, remove capabilities, or weaken acceptance criteria.

Each request sent to `coding_pipeline` must state **(1) objective, (2) scope, (3) observable acceptance criteria, and (4) non-goals**. Prefer cohesive, bounded increments without artificially fragmenting trivial work.

### 12.3 Development autonomy, handoffs, and scope

The product manager chooses reasonable implementation details autonomously and avoids routine questions to the user. For minor ambiguity, choose the simplest adequate, reversible interpretation and document consequential assumptions. A genuinely new feature or material scope change is **not approved** merely because it seems useful: record it as a future proposal and continue other approved work where possible.

When the controller requests shutdown, the product manager must initiate no new implementation requests. Record any in-flight `coding_pipeline` request identifier and known status in `STATUS.md`; gather its outcome if possible. On restart, inspect that request's actual status before resuming, retrying, or replacing it. Never call unfinished work complete. Do not construct a new transaction system just to support this handoff.

The manager may advance through **M1–M4 autonomously** once functional demonstrations and engineering checks pass. **M5 requires human scientific acceptance.** Human approval is also required for material product-scope changes; ordinary implementation decisions do not require it.

### 12.4 Binding engineering proportionality principle

The product manager and `coding_pipeline` must:

- Prefer established Python libraries and direct solutions over custom frameworks.
- Prefer ordinary files and straightforward state management when sufficient.
- Introduce abstractions to address demonstrated requirements or actual duplication, not hypothetical future needs.
- Provide appropriate error handling for realistic failures without attempting to solve every conceivable race, replay, or consistency scenario.
- Test user-observable functionality and consequential failures; avoid disproportionate tests of internal details.
- Remove, replace, or simplify superseded implementations when justified; do not preserve complexity solely for backward compatibility.
- Avoid arbitrary lines-of-code and test-count targets; every substantial complexity cost must be justified by an approved capability.
- **Never weaken scientific rigor to reduce software complexity.** Simplify supporting mechanisms, not the standards applied to derivations, computations, evidence, and conclusions.

**Operating rule:** If a proposed component cannot be tied to an approved user-visible research capability or an immediately necessary safety/correctness requirement, do not build it.
