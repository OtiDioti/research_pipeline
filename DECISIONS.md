# Development decisions

This index records consequential implementation and workflow choices. D00 decisions recorded 2026-10-30 after full v1.3 reconciliation. Reversible implementation defaults are coordinator choices within the human grant, not invented scientific approvals.

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
| DEV-010 | Continuous bounded requests after commissioning, with durable authority | Removes routine prompts without discarding verification or recovery | Conditionally authorized; activation pending successful commissioning/integration/checkpoint |
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
