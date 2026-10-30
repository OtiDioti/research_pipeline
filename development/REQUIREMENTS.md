# Specification-to-evidence crosswalk

Reconciled 2026-10-30 against **project_description.md v1.3**, dated 2026-10-29, read in full (1,738 lines). Source commit: `dce9bedb998c8be4389d42627916911f4c25d336`; SHA-256: `13d2ed9198916b7af3a3f9c3522745b0b6882b5492c9e27ccdc0c46114137ab7`. The original is unchanged and authoritative. Source sections below identify all constituent obligations, including their enumerated fields and failure cases.

## State, ownership and evidence

Every R-* row is mandatory within the first-version scope except explicitly conditional adapter obligations. **Default state: PLANNED. Request: unassigned. Executed tests/reviews, accepted source and integrated source: NONE.** These defaults apply to every row until replaced by linked exact evidence. R-001–R-003 are BLOCKED on human scientific decisions/evidence. No requirement has an authorized scope reduction. Owner is the accountable phase; dependencies follow the roadmap and explicit row references.

Requests must cite these IDs in acceptance criteria and retain partial coverage and unsupported behavior. A row is complete only with its exact accepted/integrated source, final receipt, executed checks and required live/human evidence. Deterministic contracts cannot establish scientific performance or live interoperability. The former RG-01–RG-17 conceptual groups are superseded by these specific obligations; their subjects are all retained. Original record names in §5.1 and operation contracts in §10.1 remain controlling.

## Scientific contract and foundation

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-001 | §§1.3–1.4, 11.2, M0, 14.2 | Human confirms narrow pilot, useful outcomes, research envelope and consequential decisions; quantum spectral problems remain a proposal. | D01 contract gate before D02; human | Versioned human-approved pilot brief |
| R-002 | §§11.2–11.3, M0 | Expert-audited positive and negative fixtures, development/held-out separation, reference judgments and review criteria; retain valid unusual solutions. | D01 gate; R-001 | Audited fixture manifest, provenance and access policy |
| R-003 | §§11.4–11.5, M0 | Predeclare useful-result retention, question-level progress, endorsement-error standards, budgets, uncertainty and unresolved-case handling. | D01 gate; R-001–002 | Versioned evaluation protocol and human approval |
| R-004 | §§5.1–5.6, 10.1, M0 | Common record/message/revision, eligibility, intake, vault, draft, tool, resource, checkpoint and report contracts; complete candidate/failed-check paper example. | D01 gate then D02–D07 | Reviewed administrative contract; executable schemas/fixtures through CWI |
| R-005 | §§1.1–1.2, 2.2, 3.9 | Separate assumptions/calculations/checks/conclusions and mathematical/computational/physical/novelty assessments; negative, conditional, conjectural, unresolved work is legitimate; no truth from consensus/completion. | D02, D06–D10 | Record/transition/report tests and scientific assessment |
| R-006 | §§1.3, 2.1–2.3, 12.1, 14.1 | One researcher/local project/controller, bounded replaceable roles, provider/tool-neutral core, useful single-branch path and strong single-researcher baseline. | D01–D10 | Architecture and complete single-branch workflow |
| R-007 | §§12.2–12.4; repository bootstrap policy | Nested package, help/version/errors, source-local imports, meaningful deterministic validation, Markdown root and preserved specification. | D01 / REQ-D01-001 | AC-D01-01–06, bootstrap/permanent checks, final receipt and integration |

## Records, scope and authority

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-008 | §5.1 | Every listed record has stable ID, revision where meaning changes, provenance and activity links; immutable scientific revisions, transactional current state and audit history. | D02; R-004 | All core record kinds round-trip; immutable revisions |
| R-009 | §§5.1, 8.3 | Separate project/run/task-specification/attempt/session/job identities and states; issued assignments never rewritten; fresh session is fresh attempt. | D02, D04 | Supersession and continuation tests |
| R-010 | §§2.2, 5.2 | Scientific graph differs from task graph; conjunctions of premises, alternative support; deductive self-support and circular admitted task waits prohibited. | D02, D08 | Multi-premise, alternative route and cycle cases |
| R-011 | §§3.3, 5.3 | Context pins equations, definitions, units, domains, boundary conditions, regimes, approximations and limit order; branch differences/translations explicit. | D02, D06 | Context and handoff scope preservation |
| R-012 | §§5.3, 7.2, 13.1 | Conditional premises, existence, consistency and nonempty-domain obligations remain visible; conditional/vacuous implication is not unconditional physical prediction. | D02, D07 | Conditional and ground-state existence cases |
| R-013 | §5.4 | Independent stage/disposition/support/applicability/novelty dimensions; attributed disagreements; uncalibrated model confidence cannot govern acceptance. | D02, D07 | Transition and display-label cases |
| R-014 | §§5.5, 13.2–13.3 | Invalid/stale/inapplicable/incomplete support differs from refutation; preserve old contexts, failed routes and sufficient independent alternatives. | D02, D08 | Failed-route, selective impact and context-change tests |
| R-015 | §§5.5, 7.5 | Assessment/issue changes synchronously update affected eligibility in the metadata transaction even without statement change; only previously assessed sufficient alternatives preserve eligibility. | D02, D07–D08 | Withdrawal/promotion race; no inferred sufficiency |
| R-016 | §§4.1–4.4, 6.7, 10.1 | Controller alone writes canonical state; narrow submissions; no unbounded spawning, self-promotion, reviewer repair in place or generic worker DB write. | D02, D04, D07 | Access/authority denials and attributed submissions |
| R-017 | §§9.1–9.2 | SQLite metadata/queue/resources/events; immutable hashed artifacts stored durably before atomic authority/version/resource-checked metadata commit. | D02 | Crash between artifact and DB commit, corruption and rollback |
| R-018 | §§9.2–9.3, 13.4 | Submission IDs prevent duplicate effects/charges; lease generation fences expired attempts; preserve late/stale work without advancing current outcome. | D02, D04 | Duplicate delivery, stale worker and relevant-dependency conflicts |
| R-019 | §§9.1, 9.5–9.6 | Runtime data separate from code; schema migration/old-record access or export; consistent metadata/artifact backup and interrupted-run restore; inspection/replay/reconstruction distinct. | D02, D09 | Migration, integrity and real restoration exercise |

## Seeds and workspace

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-020 | §§1.3, 3.2, 8.1 | Substantive pre-existing scientific material before research; awaiting_materials and bounded intake allowed; empty titles/metadata/placeholders/tool catalogs insufficient. | D03–D04 | Empty/unreadable denial and substantive short-note admission |
| R-021 | §3.2 | Preserve original bytes, organization, provenance, permissions and seed baseline; support notes/text/TeX/PDF/scans with inspection/notebooks/calculations/pasted content/vault imports. | D03 | Mixed corpus, original hashes/path mappings and limitations |
| R-022 | §3.2 | Classify duplicates/versions/inaccessible/uninspected content; inspect relevant subset; map questions, provisional claims, conventions, contradictions, gaps and baselines. | D03 | Partial/conflicting corpus and accurate coverage |
| R-023 | §§3.2–3.3 | Source-linked usable brief and authorized envelope precede readiness; unknown origin stays unknown; seeds/prior reviews not automatically endorsed. | D03, D06 | Readiness decision and no-promotion cases |
| R-024 | §§3.2, 6.6 | Preserve original/unresolved/external links; no imported plugins/templates/config activation; record candidate exposure from seeds. | D03, D07 | Vault link/configuration and exposure cases |
| R-025 | §§9.7–9.8 | Source-prescribed logical Obsidian areas and branch bundles, stable IDs/revisions, manifests and meaningful-folder READMEs with all seven prescribed fields; optional folders only when useful. | D03 | Layout and README contract fixtures |
| R-026 | §9.7 | Private generation and atomic publication of complete snapshot views; pinned readers, labeled stale indexes, no writable hard links to immutable objects. | D03 | Interrupted refresh, generation consistency and mutation isolation |
| R-027 | §§9.8, 9.11 | Home/branch/question/claim/source/issue navigation, safe relative Markdown links/IDs/headings, companions and generated properties; typed support distinct from hyperlinks. | D03, D09 | Link/companion checks and human navigation |
| R-028 | §§9.10–9.11, 13.7 | Draft checkout pins base; submit shows diff/authorship/new revision; concurrent edits conflict; preserve direct edits/renames before refresh; committed paths fixed. | D03 | Conflict/divergence and generated-status nonauthority tests |
| R-029 | §§9.10–9.11 | Confined archive import checks paths/links/types/sizes; no autoexecution/install; retain licenses, related data, confidentiality and external-processing restrictions. | D03, D05 | Malicious imports and disclosure denials |
| R-030 | §§9.9–9.10 | Versioned exploratory notes/failures, separate authors and generated journal; retain consequential evidence/native raw data; reference-aware retention and explicit deletion tombstones/unavailability. | D02, D06, D09 | Note history, eviction and missing-evidence cases |
| R-031 | §9.11 | Ordinary Markdown usable without plugins/subscriptions; exact external-artifact manifests/limits; editor filters not permissions; optional sync only with qualified consistent snapshots/restore. | D03, D09 | Offline reading/export and unavailable unqualified sync |

## Execution, context, resources and reporting

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-032 | §§4.2–4.5, 8.1 | Replaceable coordinator/persisted rationale; coherent bounded assignments; DB queue checks exact prerequisites, visibility, tools, seed readiness and budget. | D04, D06, D08 | Invalid admission and reconstruction |
| R-033 | §§6.1–6.2 | Durable explicit work and source-linked summaries, no dependence on hidden reasoning/private history; exact mathematics/failures/objections remain retrievable. | D06 | Transcript-free restart and failed-route retrieval |
| R-034 | §6.2 | Filter before traversal/search/summary; mandatory core includes precise equations, conditions, assumptions, assessments, issues/obligations and allowed checkpoint. | D06–D07 | Lost condition and forbidden summary cases |
| R-035 | §6.2 | Mandatory dependency traversal/reliance depth/locators; deterministic optional ranking/deduplication and bounded on-demand retrieval; semantic search optional. | D06 | Stable selection and required premise/objection retention |
| R-036 | §§6.2, 6.7 | Count complete prospective request with declared model-specific limits/method; reserve response/handoff/margin; record inclusion/defer reasons privately; recheck all subsequent calls/results. | D04 contract, D06 | Initial/subsequent overflow, large retrieval and metadata leakage |
| R-037 | §6.2 | Compress optional background only with source/scope/failure links; regenerate stale summaries; mandatory overflow requires coherent explicit revision/staging/authorized model or blocker. | D06 | Stale summary and no silent truncation |
| R-038 | §§6.2–6.6 | Preserve original messages and exposure through compaction; recorded envelopes for all §6.3 message types, collaboration and disclosure; excluded-content metadata remains private. | D04, D07–D08 | Envelope/exposure histories and leakage tests |
| R-039 | §6.7 | Provider-neutral adapter pins model/parameters/template/context, saves returned content/raw metadata/usage first; distinguish complete/truncated/context/rate/quota/uncertain completion. | D04 contract, D06 | Deterministic response faults and separately authorized real-provider evidence |
| R-040 | §§6.7, 9.1 | Task data cannot grant policy; credentials/canonical state outside worker writes; enforced filesystem/tool/network access and approved external disclosure. | D03–D07 | Actual access and hostile task-data tests |
| R-041 | §8.2 | Spent/reserved/available ledger across project/run/branch/task/attempt; context, output and cumulative usage distinct; input/output/reasoning/cache counts only when available; cost/time/compute separate. | D04 | Concurrent reservations and cumulative continuation accounting |
| R-042 | §8.2 | Verification plus per-attempt handoff and local closeout reserves within authorized ceilings; hard caps need enforceable upper bounds, else explicit monitored-service policy. | D04 | Insufficient-overhead admission, simultaneous handoffs and no double charging |
| R-043 | §§8.2, 9.4 | Unknown execution/billing retains liability; replacements need additional capacity; settle from authoritative evidence or documented conservative policy, never lease expiry alone. | D04–D05 | Outliving job, unknown charge and duplicate receipt |
| R-044 | §§8.2, 10.8 | Bound worker/model concurrency including coordinator/descendants; waiting parents yield slots; durable separately bounded numerical jobs; builds/downloads/storage all accounted. | D04–D05, D08 | Deadlock, oversubscription and nested usage tests |
| R-045 | §§8.3–8.4 | Distinct task/attempt/job/science outcomes; handoff interruption not success; replay-safe retry distinct from scientific revision; preserve unfavorable results. | D04, D08 | Incomplete work, negative result and retry classification |
| R-046 | §§4.5, 9.4, 9.9 | Meaningful and periodic incremental checkpoint manifests pin inputs/exposure/hashes, last/unresolved step, failures, next action/output, jobs and ledger; no promotion. | D04, D06 | Manifest/path/hash and multi-handoff retention |
| R-047 | §§6.2, 8.2, 9.4 | Controller initiates handoff before reserve breach; stop ordinary actions, bound jobs, persist valid checkpoint/fallback; reserve successor and inherit exposure/usage. | D04, D06 | Capacity boundary, invalid checkpoint and successor admission |
| R-048 | §§6.7, 9.4 | Preserve malformed/truncated fragments as incomplete; never execute partial tool arguments; bounded continuation without replay; no-LLM inventory cannot invent mathematics/next action. | D04, D06 | Quota loss, truncated calls and authentic receipt recovery |
| R-049 | §9.4 | Restart reconciles schema/owners/jobs/checkpoints/current dependencies/policy/cancellation/resources; publish pending report before research; missing plan needs bounded reconstruction. | D04 | Crash/restart, stale checkpoint and denied continuation |
| R-050 | §§8.4, 9.4 | Pause preserves allocation; cancel signals jobs and may prohibit models; new approved allocation creates linked run; no automatic reopening or uncertain replay. | D04 | Pause/cancel/resume and late job cases |
| R-051 | §§3.9, 9.4, 10.5 | Every admitted run gets initial/milestone/stop reports even with zero results/failure/cancellation; deterministic minimum needs no model, new inference or TeX. | D04 minimum, D09 richer | All stop modes and explicit empty results |
| R-052 | §10.5 | report.md plus continuation manifest includes all seven required content groups: scope/outcome, labeled changes, checks/issues, saved work/gaps/jobs, resources/liabilities, saved continuation/authority, reading/replay route. | D04, D09 | Exact field contract and home-note navigation |
| R-053 | §§9.4, 10.5 | Idempotent snapshot closeout, pending publication after storage failure, revised dated reports for later jobs/settlements, immutable history and unknown liabilities. | D04, D09 | Publication crash/recovery and later-result revision |

## Tools and research work

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-054 | §§3.5, 10.2, 10.6 | Capability-led selection; bundled/supplied/generated tools share contracts; missing capability permits alternative, bounded development/integration or blocker. | D05–D06 | Empty/supplied/generated catalog and unavailable tool |
| R-055 | §§5.1, 10.6 | Immutable release and README cover all seven manifest areas: identity, invocation, scientific meaning, effects/authority, resources/recovery, evidence/limits and reproducibility. | D05 | Manifest/version/domain/permission tests |
| R-056 | §§7.3, 10.2, 10.6 | Controlled source inspection and numerical/symbolic execution; authentic release/input/environment/output receipts/raw output; partial/failed/inconclusive states; shape is not scientific meaning. | D05–D06 | Real isolated local execution and failure/confinement cases |
| R-057 | §10.7 | Execution permission, qualification scope and lifecycle separate; independent frozen acceptance checks; no self-trusted flag; proportionate one-off script requirements. | D05, D07 | Narrow qualification, denial and preserved failed release |
| R-058 | §§5.5, 10.7 | All eight build/import lifecycle stages; pinned admitted dependencies; service observability limits; defect reassessment differs from operational permission revocation. | D05, D08 | Release change, denied install, service drift and affected-use cases |
| R-059 | §§6.7, 8.2, 10.8 | Optional delegation boundary pins assignment/inputs/context/environment/checks/effects/budget/exact deliverables; inner success never grants activation/scientific support. | D05 contract, D08 if enabled | Generic contract tests; real evidence for named compatibility |
| R-060 | §10.8 | Enabled delegation bounds descendants/providers/access/accounting/cancellation, persists outer/inner IDs, reconciles uncertain effects; backend state remains backend-owned. | D08, D10 if enabled; R-059 | Real nested invocation/recovery/usage or explicit unavailability |
| R-061 | §§3.3–3.5 | Source-linked framing/literature and informative baseline with precise tested scope; coherent exploration with hypotheses, uncertainty, cheapest next action and stopping rationale. | D06, D08 | Reproduction and adjacent exploration; distinguish fixture/live evidence |
| R-062 | §§3.6, 7.1 | Frozen claim/context/justifications/evidence/obligations and verification plan; pin mathematical includes/tools/code/decisive inputs; revisions trigger reassessment. | D06–D07 | Changed macro/input/code and exact review-target tests |
| R-063 | §§9.9, 10.9 | Markdown exploratory notes; substantial TeX derivation with all eight bundle fields, pinned includes, companion, stable equation locators, source/companion consistency and explicit format exceptions. | D06 | Mathematical bundle and incomplete-source preservation |
| R-064 | §10.9 | Restricted pinned TeX build, bounded receipts/logs, no network/shell escape by default; compilation not proof; native symbolic/numeric/formal artifacts and reviewable translations. | D05 adapter, D06 | Restricted build, missing package and macro revision |
| R-065 | §§7.3, 9.9 | Computations pin source/inputs/runtime/tolerances/precision/seeds/output; notebooks require clean declared execution or reproducible entry point; stored output alone not authentic execution. | D06–D07 | Hidden state, stale notebook, wrong source and replay |
| R-066 | §§3.4, 10.10 | Bounded permitted capture records requested/resolved version/purpose/location/time; reject login/partial content; preserve originals and truthful manual-upload/download provenance. | D06 | Wrong/inaccessible/partial/reused document and transfer limits |
| R-067 | §10.10 | Separate upstream/capture/extraction/report revisions; parser/OCR settings/location lineage, critical-passage inspection, exact reading coverage and correction reassessment. | D06 | Sign extraction error, abstract-only reading and new version |
| R-068 | §§3.4, 10.10 | Prescribed search/source/report/bibliography paths; precise source locations, assumptions/method/relevance/gaps; distinguish statements/inference/independent checks and declared reliance. | D06 | Report fidelity, reproduction receipts and navigation |
| R-069 | §§3.8, 7.2, 10.10 | Repeat novelty search for precise result/equivalents; closest prior work, coverage/uncertainty; source access/reuse metadata and limited attributed quotations. | D06, D09–D10 | Search logs, known-equivalent case and expert assessment |

## Verification and coordination

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-070 | §§4.4, 6.4–6.6 | Answer-blind/proof-blind/candidate-aware views enforced in retrieval/files/tools; commit reconstruction before disclosure; shared dependencies and exposure qualify independence. | D07 | Isolation and disclosure sequence |
| R-071 | §§3.2, 6.6, M4 | Filter seeds, titles/paths, README/index/summary/logs, equivalent lemmas, tool fixtures/examples, caches/notebooks/checkpoints and coordinator hints; downgrade on necessary disclosure. | D07 | Every listed leakage surface |
| R-072 | §§7.1–7.2 | Exact plans with fixed and fresh challenges; relevant source/structural/analytical/approximation/symbolic/numerical/formal/physical/novelty checks; version reasons for change, no post-failure weakening. | D07 | Plan/check history and scientific relevance review |
| R-073 | §§7.2–7.4 | Distinguish model implementation/residual/convergence/precision/applicability; meaningful scales and error sources, independent methods; floating agreement not certified bound/universal proof. | D07, D10 | Wrong-model residual, instability, exceptional domain and convergence |
| R-074 | §7.3 | Statistical selection/multiplicity/stopping recorded; independent confirmation or valid sequential uncertainty; exploratory reuse not independence; exact algebra exempt. | D07, D10 | Noisy selection and fresh confirmation |
| R-075 | §7.4 | Symbolic branches/domains/inconclusiveness; optional formal result pins statement/assumptions/object/checker, exposes gaps/axioms and separately assesses physical translation. | D07; formal adapter conditional | Symbolic tests and formal translation if enabled |
| R-076 | §7.5 | Provisional ingestion/completeness/freeze/checks/assessment/issues/authorized disposition/propagation; delegated intermediate scope only; no author endorsement, major conclusions human-reviewed. | D07 | Self-promotion and missing evidence/authority denials |
| R-077 | §§5.5, 7.5 | Atomic promotion checks candidate/support/assessment/issues/context/policy/generation; changed material blocks endorsement until reconciled while preserving historical review. | D07; R-015 | Stale promotion and policy/context races |
| R-078 | §§3.7, 7.6, 13.5 | Specific disagreements and discriminating work; reviewers/references fallible; uncertain counterexamples preserved; majority or failure to find never proves proposition. | D07–D08, D10 | Wrong reviewer, unresolved-budget and uncertain counterexample |
| R-079 | §§3.5, 4.2, 8.1, M5 | Scientific rationale/priority for ready tasks and distinct approaches, deterministic admission and foundational assumption audit. | D08 | Recorded prioritization and blocked prerequisites |
| R-080 | §§5.6, 6.4, 13.3 | Serialized branch reconciliation preserves scope/translations/contradictions; equivalence needs evidence; old-snapshot result cannot silently advance current science. | D08 | Boundary mismatch, late task and alternative support |
| R-081 | §§8.3–8.4, 14.1 | Recorded stop/reassessment; initial one replay-safe retry, reassess after two failed scientific revisions; no review shopping or endless handoffs without progress. | D08 | Repeated-failure/new-evidence/budget-stop cases |

## Whole product and evaluation

| ID | Source | Obligation | Owner / dependencies | Evidence required |
| --- | --- | --- | --- | --- |
| R-082 | §§10.1, 10.3 | CLI creation/intake/start/pause/resume/cancel, task/claim/tool/decision inspection/assessment, drafts/import/refresh/run reports/export; deny unauthorized continuation. | D03–D09 | Complete CLI workflow and negative paths |
| R-083 | §§1.4, 10.4 | Concrete batched human decisions with proposal/reasons/alternatives/evidence/consequences; routine in-envelope autonomy; human endorsement not mathematical truth. | D07, D09 | Decision authority and history |
| R-084 | §§3.9, 7.7, 10.5, 10.11 | Synthesis has all eight prescribed sections and exact current support/conditions/issues; no synthesis-only promotion; figures/tables/captions pin raw data, generator and context. | D09 | Stale caption, dropped premise, conflicting scope and unsupported interpretation |
| R-085 | §§9.10, 10.5, 10.11 | Portable self-contained README/record/artifact/environment/review manifest; relative links, restricted/unavailable dependency declarations; private backup distinct. | D09 | Clean inspection/replay without live DB; reuse-aware export |
| R-086 | §§9.11, 10.5, 11.6 | Human route home/report/claim/argument/calculation/source/review/objection and authorized continuation without logs/chat; historical snapshots retained. | D09–D10 | Actual navigation/continuation tasks and observed effort/errors |
| R-087 | §§11.1, 11.5, M7 | Separate competence, system reliability and real research value; pilot end-to-end/recovery and human acceptance of remaining limits required for release. | D10; R-001–003, D09 | Authorized live pilot, expert judgments and release decision |
| R-088 | §11.2 | All 12 positive/negative classes: equivalence, boundary/conventions, zero division, nonuniform approximation, instability, wrong model/residual, exchanged limits, shared error, uncertain counterexample, noisy selection, formal translation, novelty. | D01 curation, D07 development, D10 held-out | Frozen expert-audited case assessments and useful valid results |
| R-089 | §11.3 | Matched total tools/resources/records: single researcher, independent checking, applicable second method; ablate blinding/audit/dependencies/branches; count failures and human review time. | D10 | Predeclared comparison and complete accounting |
| R-090 | §11.4 | All 14 metric families with denominators/uncertainty; both repair directions; unresolved truth stays unresolved; zero endorsements means undefined rate; question-level grouping. | D10 | Evaluation outputs and auditable counts, including handoff/workspace/tool cost |
| R-091 | §§11.4–11.5 | No success by trivial splitting or universal rejection; nontrivial predeclared quality/progress gates; investigate unsupported central endorsement; new held-out assessment after repair; simpler default absent measured benefit. | D10 | Expert scoring, failure report and scoped architecture decision |
| R-092 | §11.6 | All 19 workbench/source/tool/context/handoff/closeout scenarios, including provider loss and model-forbidden cancellation; real compatibility evidence for enabled delegated adapters. | D03–D10 | Case-by-case execution manifest; mocks never labeled live |
| R-093 | §§12.3–12.4, 15 | Sequential M0–M7 reliability gates, consistent names/versions, meaningful unit/integration/fault/expert checks; demonstrate recovery/isolation/scope/failed-support before release. | D01–D10 | Phase and whole-scope evidence audit |
| R-094 | §§1.3, 12.1, 14 | No autonomous publication/unbounded spawning/weight training/universal proof or equivalence; distributed/learned/cross-project/custom UI deferred; expand only with authority and evidence. | All phases | Scope review; examples do not mandate optional tools |

## Reconciliation decisions

The original roadmap deferred pilot choice to D10, conflicting with M0 timing. A **D01 scientific-contract gate now precedes D02**; D10 evaluates the previously frozen protocol. The user's explicitly authorized REQ-D01-001 commissions development tooling before that gate. It adds no scientific behavior and does not complete M0 or all D01 obligations. Pilot choice and expert judgments remain human responsibilities.

Minimum deterministic no-model closeout belongs to M2: **D04 owns it**, while D09 adds richer synthesis/export. Model limit/stop-reason contracts also begin in D04, followed by dependency-first context and adapter work in D06. Python/SQLite/local CLI match the specification's proposed defaults. Nested `implementation/src/` preserves its illustrative module responsibilities while satisfying repository layout rules.

No scientific fixtures or live experiments are authorized as expert evidence by this mapping. Future runtime provider, scientific data/service permissions, pilot limits and judgments remain explicit dependencies. Product implementation can only proceed through CWI after the applicable gates.

## Completion audit

At phase boundaries reconcile every row to exact evidence and §§11.5/15. Permitted states are PLANNED, IN_PROGRESS, EVIDENCED_NOT_INTEGRATED, INTEGRATED, BLOCKED and DEFERRED_AUTHORIZED. Preserve partial results and unknown liabilities; only human authority can reduce mandatory scope. Apply [AUTONOMY.md](AUTONOMY.md) before any completion claim.
