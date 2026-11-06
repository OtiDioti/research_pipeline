# Development records

Explains the separation between current coordination, detailed evidence and historical records so sessions can read selectively.

## Restart reading order

1. Read current STATUS and effective AUTHORIZATION, plus the local handoff and applicable active run/request.
2. Inspect actual Git/CWI/host ownership and verify the specification digest and cumulative limits.
3. Read only the relevant requirement rows, specification sections, phase and decision records. Initial commissioning and changed/uncertain specification evidence retain AGENTS.md's full-reading requirements.

The ownership map is in [DEVELOPMENT](../DEVELOPMENT.md#4-information-ownership-avoid-competing-status-files). [FOLDER_CONTENT](FOLDER_CONTENT.md) locates immediate children. Do not load the full history or changelog by default.

## Record ownership

| Information | Owner |
| --- | --- |
| Current checkpoint and aggregate consumption | STATUS.md |
| Actual human authority and source amendments | AUTHORIZATION.md and linked source records |
| Stable setup and permitted commands | ENVIRONMENT.md, RUNBOOK.md, MODEL_POLICY.md |
| Requirement obligations and evidence pointers | REQUIREMENTS.md |
| Exact execution narrative | One runs/ record per actual CWI run |
| Backend maintenance detail | backend_changes/CP-ID.md, linked from the root backend index |
| Frozen implementation request | requests/; bodies stay unchanged after launch |
| Consequential rationale | Individual decisions/ record; DECISIONS is the index |
| Current phase scope and progress | phases/ and ROADMAP.md |
| Superseded snapshots, dated checkpoints and preserved originals | history/ |

Update current views in place. Record detail once in its owner and link elsewhere. Human authority, Git and CWI receipts retain their evidentiary roles; summaries cannot create permissions or acceptance.

## Preservation and scope

[History](history/FOLDER_CONTENT.md) includes readable archival views and a hash manifest of every exact original input. Frozen requests/specification and product/CWI-owned files are unchanged; their purpose is described in navigation rather than inserted into hashed evidence. This administrative migration does not resume product development or reset any budget.
