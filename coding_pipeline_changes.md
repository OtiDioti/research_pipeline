# Coding-pipeline backend change index

Indexes actual backend repairs and their evidence; unchanged-backend product observations remain in run records and preserved history.

## Current backend

Separate ignored clone `coding_pipeline/`,revision`bcb7ad24f83ff5193345f3d4fa72122ea53a4e66`. Cumulative attempts/adoptions/reversions:**3/3/0**. This migration changes no backend source,guards,evidence or launch environment.

## Adopted changes

| ID | Change | Revision | Evidence |
| --- | --- | --- | --- |
| CP-001 | Private final-response preparation | `c74df0b09b4883776b1889b859b2df065f0b2fe4` | [Audit](development/backend_changes/CP-001.md) |
| CP-002 | Targeted Reviewer diagnostics;full controller gates retained | `b6a2e05283f92f2bb42402d49e4a274225b43f6a` | [Audit](development/backend_changes/CP-002.md) |
| CP-003 | Authorized role/prompt modernization | `bcb7ad24f83ff5193345f3d4fa72122ea53a4e66` | [Audit](development/backend_changes/CP-003.md) |

## Recording rule

Keep one full [incident record](development/backend_changes/README.md) per CP-ID, using [BACKEND_CHANGE](development/templates/BACKEND_CHANGE.md). Record every attempted, rejected, reverted and adopted variant there with authority, revisions, checks, patches/backups and unresolved limits; this file adds only its concise index row and link. Keep pending detail local while live/base-bound. Routine unchanged-backend product narratives belong in owning runs.

[Historical audit](development/history/backend-audit.md) and [manifest](development/history/MANIFEST.md) preserve all previous entries. Existing `development/backend_patches/` and `local/backend-repairs/` artifacts are untouched. Necessary maintenance and the closed dated modernization exception retain their original limits.
