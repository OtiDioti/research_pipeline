# ROADMAP.md — First release

**Authority:** `project_description.md` defines scope and acceptance. This file tracks what has actually been demonstrated; it cannot add requirements. Do **not** mark a milestone complete merely because code was merged or tests passed. No milestone is marked complete in this restart template.

## Development gates

### M1 — Minimal scientific loop

**Status:** Not started

**Deliver:** Linux/Python CLI launches and inspects a Codex researcher. It reads `starting_evidence/RESEARCH_QUESTIONS.md` and relevant evidence, forms a plan, conducts real scientific reasoning, executes a scientific calculation, and writes readable Markdown results with supporting artifacts. Establish essential workspace and resource boundaries.

**Gate:** Complete a short real question-to-artifact investigation, not just mocked tests. Inspect result files and validate the reproducible calculation.

### M2 — Persistence and human direction

**Status:** Not started

**Deliver:** Checkpoints, full pause/resume, lightweight crash recovery, primary-researcher context rollover into a **fresh Codex session**, updated research questions and project instructions, scientific feedback, human Markdown edits, and navigable `FOLDER_CONTENT.md` indexes.

**Gate:** Pause/resume an investigation, edit objectives and an existing scientific note, and verify affected-work reassessment. Force a context rollover and confirm the fresh session continues the same task from handoff and project artifacts.

### M3 — Delegated research and verification

**Status:** Not started

**Deliver:** Recursive subproblem decomposition, separate subagent workspaces, concise `handoffs/` files, independent verifier sessions, bounded scientific disagreements, and parent-driven result integration. **Delegated agents and verifiers roll over at or before 60% of usable context-window occupancy per session**, with conservative estimates if occupancy telemetry is unavailable.

**Gate:** Delegate a genuine research subproblem, force a subagent context rollover, and demonstrate continuation in a fresh session without pausing the parent or resetting cumulative budgets. Obtain and address an independent verification challenge.

### M4 — Cross-project memory and tools

**Status:** Not started

**Deliver:** Filesystem/full-text discovery across accessible projects, qualified reuse of findings, simple registration/reuse of user-supplied and agent-developed tools, and remaining V0 reporting and budget controls.

**Gate:** A new investigation discovers a relevant prior artifact or tool and uses it appropriately, preserving assumptions and uncertainty.

### M5 — Human scientific acceptance

**Status:** Awaiting M1–M4

**Deliver:** Live investigation of light-hole spin qubits in Ge-rich quantum wells coupled to resonators, including meaningful analytical models, numerical work, literature assessment, independent criticism, reproducible outputs, and multi-session continuity.

**Gate:** Human reviews scientific competence and evidence. New physical discoveries are **not required**. Software tests do not substitute for this assessment.

## Working rules

- Develop only the current milestone and its unavoidable prerequisites.
- Product manager may advance automatically through M1–M4 only after a **demonstrated** gate; record evidence links briefly in `STATUS.md` and update the milestone status here.
- Correct failed demonstrations through narrowly scoped `coding_pipeline` requests before advancing.
- M5 completion requires explicit human scientific acceptance.
- Future directions in §11 of `project_description.md` are nonbinding and excluded from this roadmap until approved.
