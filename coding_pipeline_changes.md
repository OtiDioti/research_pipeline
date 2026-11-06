# Coding-pipeline backend change index

Indexes actual backend repairs and their evidence; unchanged-backend product observations remain in run records and preserved history.

## Current backend

Separate ignored clone `coding_pipeline/`,revision`bcb7ad24f83ff5193345f3d4fa72122ea53a4e66`. Cumulative attempts/adoptions/reversions:**3/3/0**. This migration changes no backend source,guards,evidence or launch environment.

## Adopted changes

| ID | Change | Revision | Evidence |
| --- | --- | --- | --- |
| CP-001 | Private final-response preparation | `c74df0b09b4883776b1889b859b2df065f0b2fe4` | [Audit](development/history/backend-audit.md#cp-001--prepare-private-final-response-before-child-launch--2026-11-02) |
| CP-002 | Targeted Reviewer diagnostics;full controller gates retained | `b6a2e05283f92f2bb42402d49e4a274225b43f6a` | [Audit](development/history/backend-audit.md#cp-002--human-requested-targeted-reviewer-diagnostics-adopted-2026-11-03) |
| CP-003 | Authorized role/prompt modernization | `bcb7ad24f83ff5193345f3d4fa72122ea53a4e66` | [Audit](development/history/backend-audit.md#cp-003--human-requested-role-configuration-and-prompt-modernization-2026-11-04) |

## Recording rule

Record every actual maintenance attempt,adoption or reversion with authority,original/adopted revisions,diagnosis,checks,patches/backups and unresolved limits. Keep live/base-bound observations local under AGENTS. Routine unchanged-backend product narratives belong in owning runs.

[Historical audit](development/history/backend-audit.md) and [manifest](development/history/MANIFEST.md) preserve all previous entries. Existing `development/backend_patches/` and `local/backend-repairs/` artifacts are untouched. Necessary maintenance and the closed dated modernization exception retain their original limits.
