# Safe development-document updates

Explains which development records to update, when and how, without losing authority, evidence, budgets or unfinished-run recoverability.

## 1. Establish scope and a safe boundary

Follow the current human instruction and effective grant. Inspect Git,local handoff/attempts and CWI status/diagnose. If a run is live or an accepted result remains base-bound,keep tracked updates outside that checkout until safe integration or supported recovery resolves the binding. Do not change its baseline,backend,environment or frozen inputs.

Preserve pre-update text,paths and hashes before replacing or retiring documents,including legitimate uncommitted work. An exact Git revision suffices for committed text; preserve uncommitted material separately before changing it. Do not create another bulk archive for routine edits. Do not overwrite the product specification,freeze new authority from a template,reset consumption or transfer an unaccepted draft into product source.

## 2. Keep one owner for each kind of information

Use [DEVELOPMENT](../DEVELOPMENT.md#4-information-ownership-avoid-competing-status-files) and [development records](README.md). Current STATUS,ROADMAP,BACKLOG,ENVIRONMENT and REQUIREMENTS views are updated in place;detailed execution belongs to its run and rationale to its decision record. Preserve superseded narratives in history and link them instead of merging them into current startup documents.

AUTHORIZATION is an effective-authority view,not a blank grant form. Actual new human grants,amendments or revocations need dated source records linked from that view;budget ceilings remain distinct from consumption in run evidence and STATUS. Preserve every operative restriction,source date and unknown liability;an upgrade package or proposed form cannot supply permission.

Stable identity/environment changes belong in ENVIRONMENT. Dated model/account/catalog readiness evidence belongs to the corresponding local attempt and owning run. [MODEL_POLICY](MODEL_POLICY.md) and [RUNBOOK](RUNBOOK.md) define current role flags and access checks;do not duplicate or overwrite historical frozen selections.

Backend detail belongs in [backend_changes/CP-ID.md](backend_changes/README.md);the root coding_pipeline_changes.md is its index and backend_patches/ holds patch artifacts. Transfer pending local incident detail and the index link only at a safe checkpoint,preserving all rejected/reverted attempts.

## 3. Apply update triggers to the correct owners

At each safe checkpoint, compare relevant records with actual human instructions, Git and CWI evidence. Reconciliation does not require editing every file: change an owner only when its facts changed. Use this table with the ownership map; it does not grant new authority.

| Owner | When and how to update |
| --- | --- |
| [AGENTS](../AGENTS.md) | Approved operating-rule changes: state mandatory boundaries concisely and link detailed procedures; omit execution history. |
| [DEVELOPMENT](../DEVELOPMENT.md) | Architecture, layout or information ownership changes: correct the map and synchronize this guide. |
| [README](../README.md), [development README](README.md) | Entry points or reading order change: correct navigation and file-role descriptions without copying status. |
| [STATUS](../STATUS.md) | Safe checkpoint changes: replace the current mode, source/evidence pointers, cumulative totals, remaining limits and single next action. During a binding, keep changes in the local handoff. |
| [ROADMAP](../ROADMAP.md), [phase records](phases/README.md) | Phase scope, dependencies or evidenced progress change: reconcile planned versus delivered work and link owning runs; retain unmet obligations. Use [PHASE](templates/PHASE.md) for a new phase record. |
| [BACKLOG](../BACKLOG.md) | A defect, dependency or hold changes: record disposition, evidence and resumption conditions; preserve failed attempts and consumed recovery limits. |
| [Requests](requests/README.md) | Before an authorized launch: prepare and commit scope, specification references and meaningful checks using [REQUEST](templates/REQUEST.md). Never edit a launched frozen body; record later outcomes in its run. |
| [Run records](runs/README.md) | Capture actual attempts locally; create a record only after CWI supplies its UUID, never inventing one for a failed preflight. Use [RUN](templates/RUN.md) for exact identities, frozen settings, failures, usage, validation, review, acceptance, integration receipts and required target checks. Preserve incomplete and accepted-unmerged results; reconcile failed starts into STATUS totals. |
| [REQUIREMENTS](REQUIREMENTS.md) | Coverage or approved obligations change: update only affected rows and evidence links; distinguish implementation, acceptance, integration and scientific validation. Retain partial and unevidenced obligations. [Historical evidence](history/requirements/README.md) remains dated context; link new owning runs without rewriting old claims. |
| [Individual decisions](decisions/README.md), [DECISIONS index](../DECISIONS.md) | A consequential choice or material policy change: record rationale, actual approval/status and evidence once using [DECISION](templates/DECISION.md); add a short index entry. Routine outcomes belong in runs. |
| [CHANGELOG](../CHANGELOG.md), [period logs](history/changelog/FOLDER_CONTENT.md) | A meaningful outcome: append a short dated entry to its period, linking the run or decision; refresh the root's current pointer. Preserve prior entries; add a new period and index link when needed. |
| [AUTHORIZATION](AUTHORIZATION.md), [authority sources](history/authorization/FOLDER_CONTENT.md) | An actual human grant, amendment or revocation: preserve its dated source separately and reconcile the effective view before relying on it. Reference/format corrections must not change grant content. Ordinary tasks within existing authority need no invented grant; consumption stays in runs/STATUS. |
| [ENVIRONMENT](ENVIRONMENT.md) | Stable non-secret identity, setup or version contract changes: correct the contract. Keep dated access/catalog/readiness observations in the owning local attempt/run. |
| [MODEL_POLICY](MODEL_POLICY.md) | An actual authorized role-selection or invocation-contract change: synchronize flags in AGENTS, RUNBOOK and affected prompts/forms. An access failure is run evidence, not permission to substitute or rewrite frozen settings. |
| [RUNBOOK](RUNBOOK.md), [AUTONOMY](AUTONOMY.md), [BOOTSTRAP](BOOTSTRAP.md) | Verified procedures or workflow rules change: correct their respective commands, loop/limit rules or initial-source validation instructions. Editing policy cannot enlarge a grant; bootstrap checks do not replace the implemented validator. |
| [BACKEND_MAINTENANCE](BACKEND_MAINTENANCE.md) | Maintenance policy changes: update the policy under actual authority. Actual incidents go in [backend_changes](backend_changes/README.md) using [BACKEND_CHANGE](templates/BACKEND_CHANGE.md), with a [root index](../coding_pipeline_changes.md) link and retained [patches/backups](backend_patches/README.md), including rejected/reverted attempts. |
| [CODEX_START](CODEX_START.md), [initial commissioning](templates/COMMISSIONING.md), [activation](templates/ACTIVATION.md), [optional initial preauthorization](CODEX_START_AUTONOMOUS.md) | Workflow, prerequisites or file roles change: correct the appropriate continuation prompt or issuance proposal. Use §5's state table; editing or reading a form issues no authority. |
| [Record templates](templates/README.md) | Required record fields change: update the relevant format and callers. [LIVE_HANDOFF](templates/LIVE_HANDOFF.md) and [COMPLETION](templates/COMPLETION.md) describe records; filling them cannot establish acceptance, completion or permission. |
| `FOLDER_CONTENT.md`, opening purpose paragraphs | Add/move/remove/role change: update affected immediate-child indexes and semantic references. New or substantially revised editable Markdown starts with a concise purpose after its title; unchanged frozen inputs are described externally. |
| [History](history/FOLDER_CONTENT.md) | Substantive superseded context needs selective retrieval: preserve an identified snapshot/source with provenance and link it. Routine edits use Git history. Append new dated records without rewriting preserved claims, manifests or frozen evidence. |
| [PIPELINE_REVIEW](PIPELINE_REVIEW.md), [benchmarks](benchmarks/FOLDER_CONTENT.md) | Preserve dated assessment/measurement evidence as recorded. A new authorized assessment gets its own identified record and navigation; do not refresh old results into a claim of current acceptance or performance. |
| [local/live.md](../local/live.md) | Live/base-bound observations or session handoff change: maintain the ignored overlay with exact execution/recovery state and one next safe action. Transfer durable facts into their owners only at a safe checkpoint; retain recovery context. |
| [Product specification](../project_description.md), product Markdown | Specification changes require explicit human authority and a new authorized digest/crosswalk reconciliation. Product instructions that affect runtime behavior follow CWI; administrative maintenance cannot bypass that boundary. |

No new run, phase, backend incident or requirement credit is created merely to document an administrative edit. Keep current task labels in STATUS rather than repeatedly changing stable authority/environment records.

## 4. Synchronize meaning as well as links

Review descriptions,repository diagrams,prompts,templates and references whenever a file's role changes. A resolving link can still send an operator to the wrong kind of content. Name the actual destination:continuation versus commissioning,contract versus observation,index versus detailed record,authority view versus issuance form.

Do not rewrite frozen requests,controller-owned evidence or preserved historical claims to match present conventions. Keep their context explicit and provide current navigation outside immutable inputs. For a redundant mutable document, transfer unique information to its owner, preserve its prior source, repair all current references, then remove it. Retain historical configurations needed for unfinished-run recovery.

Apply the existing AGENTS review/removal and source-preservation rules. Administrative updates do not authorize product coding,backend modernization,scientific judgments,new services or purchases.

## 5. Select the current form by actual state

| Actual state | Current destination |
| --- | --- |
| Genuinely unstarted repository; no unfinished run | [COMMISSIONING](templates/COMMISSIONING.md),only when actually issued by the human |
| First result accepted-unmerged; human chooses activation | [ACTIVATION](templates/ACTIVATION.md),with exact receipt/base/integration prerequisites |
| Existing activated grant and explicit human resumption | [Continuation](CODEX_START.md); preserve all consumption and prior restrictions |
| Already integrated but no continuous authority | Actual human grant for remaining scope;adapt the activation premise to the verified checkpoint without resetting prior history |
| Run active,ownership uncertain or recovery blocked | Supported inspection/recovery/hold;no competing start |

The [optional initial preauthorization form](CODEX_START_AUTONOMOUS.md) replaces the default first-result pause only if explicitly selected by the human. Reading or editing a form does not issue it,activate a grant or resume a stopped session.

## 6. Verify and checkpoint

Check recoverable prior sources,unchanged protected/source/request digests,scope,links and headings,purpose descriptions,index coverage and semantic owner references. Search current callers and descriptions of renamed or repurposed files; resolving links alone do not prove correct roles. Confirm authority and model/effort propagation remain correct and old states retain their original backend/configuration. Do not infer historical validity from a newly passing test.

Review the administrative diff and commit explicit safe paths after bindings are resolved. Do not stage the nested clone,private logs,credentials or unrelated files. Do not add routine product-test reruns solely for documentation;required product acceptance/integration/target checks still apply to product work.

Leave accurate current views and a self-contained handoff with exactly one next safe action. A documentation update installs no supervisor or automatic restart.

## Historical context

The [pre-cleanup guide](history/reference-cleanup-2026-11-06/originals/development/UPDATE_GUIDE.md.txt) preserves the former upgrade/starter-kit packaging instructions and original adoption evidence links. The [reference-cleanup record](history/reference-cleanup-2026-11-06/README.md) records this correction. Historical package descriptions do not define the current repository layout or create authority.
