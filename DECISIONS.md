# Development decisions

This index records consequential implementation and workflow choices. The starter-kit entries are **proposed defaults**, to be confirmed or amended during D00. They are not assertions that the product specification already mandates these choices.

| ID | Proposed choice | Rationale | Confirmation |
| --- | --- | --- | --- |
| DEV-001 | Outer Codex coordinator; all implementation through CWI | Preserves the chosen backend without recursive controller calls | Pending D00 |
| DEV-002 | Markdown-only repository root; implementation in `implementation/` | Meets the root layout requirement without disguising configuration files | Pending D00 |
| DEV-003 | Ignored nested `coding_pipeline/` clone, not a submodule | Matches the reviewed backend's supported source-launch layout | Pending local version check |
| DEV-004 | One scoped CWI run at a time; explicit phase boundaries | The backend is sequential and has no public stop-after-milestone command | Pending D00 |
| DEV-005 | Root status is a committed checkpoint; live observations are local | Avoids changing the target checkout during validation and merge | Pending D00 |
| DEV-006 | Python 3.11+ with stdlib unittest for the first foundation | Minimizes dependencies and allows an independently enforced bootstrap test run | Pending specification reconciliation |
| DEV-007 | No automatic merge for the first run | Makes the initial workflow and exact-commit evidence inspectable | Initial recommended operating policy |
| DEV-008 | Stable, minimal launch environment | CWI resume requires an exact environment digest | Pending local environment check |
| DEV-009 | Research data/vaults separated from development state | Prevents product investigations from becoming source-control noise or leaking private data | Pending D00 |

For a substantial decision, create a detailed record under [development/decisions/](development/decisions/README.md) using the [template](development/templates/DECISION.md). Include alternatives, consequences, evidence, and revisit conditions. Do not record a proposed default as an approved decision without an actual decision event.

A product-requirement change additionally needs an explicit, reviewed change to `project_description.md`; this index alone cannot authorize it.
