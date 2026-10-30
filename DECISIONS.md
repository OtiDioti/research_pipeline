# Development decisions

This index records consequential implementation and workflow choices. D00 decisions recorded after full v1.3 reconciliation; v1.4 dependency amendment explicitly authorized 2026-10-30. Reversible implementation defaults are coordinator choices within the human grant, not invented scientific approvals.

| ID | Proposed choice | Rationale | Confirmation |
| --- | --- | --- | --- |
| DEV-001 | Outer Codex coordinator; all implementation through CWI | Preserves the chosen backend without recursive controller calls | Confirmed by actual human grant |
| DEV-002 | Markdown-only repository root; implementation in `implementation/` | Meets the root layout requirement without disguising configuration files | Confirmed by actual human grant |
| DEV-003 | Ignored nested `coding_pipeline/` clone, not a submodule | Matches the reviewed backend's supported source-launch layout | Verified clean supported direct-child clone; ENVIRONMENT.md |
| DEV-004 | One scoped CWI run at a time; explicit phase boundaries | The backend is sequential and has no public stop-after-milestone command | Confirmed by actual human grant |
| DEV-005 | Root status is a committed checkpoint; live observations are local | Avoids changing the target checkout during validation and merge | Confirmed by actual human grant |
| DEV-006 | Python 3.11+ with stdlib unittest for the first foundation | Minimizes dependencies and allows an independently enforced bootstrap test run | Confirmed coordinator default; specification §§12.2, 14.1 |
| DEV-007 | No CWI automatic merge; first result normally held for human review | Exact-source inspection before coordinator-controlled integration | Human explicitly preauthorized coordinator exact integration; AUTH-2026-10-30-001 |
| DEV-008 | Stable, minimal launch environment | CWI resume requires an exact environment digest | Verified and recorded in ENVIRONMENT.md |
| DEV-009 | Research data/vaults separated from development state | Prevents product investigations from becoming source-control noise or leaking private data | Confirmed by actual human grant |
| DEV-010 | Continuous bounded requests after commissioning, with durable authority | Removes routine prompts without discarding verification or recovery | Activated after successful commissioning integration/validation at AUTH revision 3 checkpoint |
| DEV-011 | Focused direct backend repair exception, separate from product implementation | A faulty backend may need repair without depending on itself | User requested; apply maintenance policy and audit every attempt |
| DEV-012 | Requested Astra 6.1, verified identifier; explicit effort at or below xhigh | Preserves requested selection without inventing model availability | Human corrected to gpt-6-astra; explicit medium for foundation; max xhigh |
| DEV-013 | Session continuation is separate from an external supervisor | Avoids claiming that Markdown automatically restarts Codex | No supervisor implemented by this update |

For a substantial decision, create a detailed record under [development/decisions/](development/decisions/README.md) using the [template](development/templates/DECISION.md). Include alternatives, consequences, evidence, and revisit conditions. Do not record a proposed default as an approved decision without an actual decision event.

A product-requirement change additionally needs an explicit, reviewed change to `project_description.md`; this index alone cannot authorize it.

Workflow rationale: [ADR-010](development/decisions/ADR-010-continuous-development.md). Preserve earlier decisions and actual approvals when adopting this update; a proposed entry cannot supersede a human decision by itself.

## Reconciliation decisions — 2026-10-30

- DEV-014: Preserve specification M0 timing by adding the scientific-contract gate to D01 before D02. D10 runs the already approved pilot/protocol; it does not first choose them after implementation. The authorized foundation request remains independent of scientific choices.
- DEV-015: Move minimum deterministic end-of-run reporting and model-limit/resource contracts into D04/M2. D09 builds richer synthesis and portable export.
- DEV-016: Preserve actual backend `1f68060` unchanged. Its two prompt-resource differences from reviewed `122f865` were inspected, including Architect-like wording in Designer; rely on frozen role schemas and inspect actual commissioning evidence. No diagnosed malfunction warrants a patch.
- DEV-017: Use installed Git 2.40.1 via fixed launch PATH because system 2.34.1 lacks required worktree porcelain -z. No environment installation or live-run change occurred.

- DEV-018: Use explicit workflow-local `Codex Development Coordinator <codex@localhost>` author/committer variables because Git identity is unconfigured. Attribute agent-generated commits honestly; do not copy the human author from old history or change global Git settings.

- DEV-019: Record the human's “create your mock for this example” as authority for a synthetic harmonic/quartic development fixture. Keep mock provenance distinct from expert reference judgments and actual execution. M0 remains incomplete; no mandatory scientific gate is waived.
- DEV-020: Commissioning used one start with no repairs. Inspected final receipt and exact accepted source, then fast-forwarded before the administrative activation commit. Use the permanent validator for every subsequent request; the original bootstrap exemption is retired.

- DEV-021: After REQ-D01-002's inspected exact integration and 28/28 target validation, hold dependent D02 work at the original M0→M1 scientific gate. The human's requested mock is fully delivered as synthetic material; it is not an expert audit or authorization to replace mandatory scientific reference judgments. The M0 packet makes remaining human decisions concrete. This is a defined stopping condition under the still-valid continuous grant, not a routine phase-boundary permission request or a completed project.

## Version 1.4 dependency amendment — current authority

- DEV-022 supersedes the blanket engineering prerequisite in DEV-014/DEV-021, preserving their historical rationale/evidence. Human explicitly separates M0-E engineering readiness from pending M0-S scientific validation. The old combined M0 and R-001–R-003 stay incomplete. Genuine scientific design dependencies still block their affected slice; no empirical threshold may be set after seeing scored/held-out outcomes.
- DEV-023: Settle the next M0-E storage contract in the M0 packet and REQ-D02-001: Python stdlib SQLite, content-addressed immutable bytes, typed exact record/artifact references, append-only revisions, explicit expected heads, idempotent transactional submissions and events, controller-only local API. This is a reversible technical choice within the amended specification, not pilot selection. Executable evidence remains pending until CWI acceptance/integration.
- DEV-024: Preserve all v1.3 historical receipts/requests/fixture hashes. New requests cite v1.4; the oscillator's original source identity remains v1.3. Do not rewrite scientific provenance when dependencies change.
- DEV-025: Select explicit gpt-6-astra/high for D02-001 because atomicity, corruption and authority boundaries need deeper review. This changes effort only for the new run, never a frozen run; all original limits persist.

## DEV-026 — Consistent backup/restoration next

After REQ-D02-001 accepted/integrated local version-1 SQLite storage, commission a self-contained consistent metadata/artifact backup and verified restore before broader runtime use. This is ready independent R-019/R-017 engineering and tests real recoverability; full scientific record semantics/eligibility remain subsequent D02 obligations. Use one bounded high-effort CWI milestone, stdlib SQLite/filesystem, no new provider/data/service authority. Preserve all source/receipt identities; no migration is invented merely to claim one exists.

## DEV-027 — Typed scientific content without reinterpreting history

After accepted local storage and backup, implement four provisional scientific payloads and exact typed admission using the existing immutable version-1 database. A content discriminator separates typed records from legacy generic envelopes; no silent migration or competing graph is allowed. Required assumptions are local named statements bound to exact revisions, while assessed sufficiency and authentic tool execution remain separate future authority. Preserve provisional cycles and keep alternate routes separate; no scientific judgment is inferred from structural validity. REQ-D02-003 records the concrete contract and failure/compatibility evidence. High effort remains appropriate for provenance, exact references and idempotency.

## DEV-028 — Explicit schema evolution with preserved v1 restoration

REQ-D02-004 introduces schema 2 for all twenty generic §5.1 envelope identities and an explicit v1-backup-to-new-v2-runtime migration. Preserve v1 read/old-kind append/retry/backup and exact default restoration; never migrate a live source in place or rewrite original receipt provenance. New generic kinds confer no authority and retain null canonical state until their concrete typed/state contracts are implemented. Use strict version-specific schema/backup gates, separate migration attribution and the existing incomplete-restore publication boundary. This is a reversible technical dependency for remaining records/assessments, not scientific approval; high effort is appropriate.

## DEV-029 — Preserve controller validation ownership after observed sandbox mismatch

Run 9af6f133 passed the exact 116-test controller baseline but stopped when its Writer independently encountered literal-/tmp denial and the Architect treated that as the missing baseline. Preserve the stopped nonresumable run and its actual passing baseline. REQ-D02-004-R1 clarifies that meaningful acceptance checks remain controller-owned, while Writer-local runs must report narrower-sandbox limitations honestly. No tests/validator/security/environment/backend change is authorized as the correction. A new bounded run after clean terminal disposition is recovery action 1, not a blind resume or waived gate.

## DEV-030 — Attributed reports before current assessment authority

REQ-D02-005 consumes schema-2 review/issue identities and existing scientific typed admission to persist independent dimensions, disagreements and explicit route judgments. A separate versioned assessment-content discriminator preserves old codecs. Reported sufficiency/independence/execution are declarations, not approval or current disposition. Exact route-conclusion membership is a mechanical admission check; differing contexts remain expressible. Current eligibility generation/invalidation and authorized promotion are subsequent work. This is reversible domain-independent record engineering, not a scientific pilot or sufficiency decision.

## DEV-031 — Human deadline extension and preserved-draft recovery

After run 46114120 timed out at its frozen 900-second Writer deadline, the human explicitly set CWI time limits to 2,700 seconds. AUTH revision 5 applies that per-agent/per-validation ceiling to new runs, without changing model/effort/start/repair/billing or acceptance limits. Preserve the terminal unaccepted draft and freeze its exact files through supported --context for REQ-D02-005-R1; only its delegated Writer may implement them in its new worktree. Full product scope and gates stay unchanged. This is one diagnosed deadline recovery, not a backend repair, silent resume or direct product transplant. Unknown timed-out Writer usage remains a liability.

## DEV-032 — Work-product/draft infrastructure as the next independent slice

After attributed Review/Issue records are accepted/integrated, implement real multi-file work-product manifests and a safe checkout → preview → explicit atomic submission round trip in REQ-D02-006. This consumes established storage/reference/backup contracts and enables D03 authoring without waiting for unrelated scientific acceptance or current eligibility. Keep those mandatory obligations visible. Use inert copied bytes, portable logical paths, canonical exact bases, bounded capture, detached saved proposals, explicit expected heads and preserved edits; descriptor text does not grant authority. Separate preview/orphan publication from canonical commit so lost acknowledgment reconciles the original proposal instead of rereading mutable files. High effort, at most three milestones and human-authorized 2700-second deadlines. No schema/provider/security/approval expansion; detailed TeX/checkpoint/closeout semantics remain later work.

## DEV-033 — Preserve sources before seeded intake and readable views

REQ-D03-001 will consume evidenced storage/authoring contracts for versioned Source records and a bounded explicit local capture/proposal/commit path. Keep upstream version, local capture revision and reading-report revision separate. Preserve originals, exact extraction lineage and locators, reported partial coverage, unknown attribution and access/reuse/processing declarations; bytes or metadata never certify scientific reading, reproduction or permission. No network/parser/archive execution or readiness transition is commissioned. This is a concrete independent D03 prerequisite, while D02 eligibility/authority and M0-S remain mandatory pending work. Reuse proven filesystem/admission primitives where appropriate, with high effort and at most two milestones under unchanged2700-second deadlines; no authority expansion.
