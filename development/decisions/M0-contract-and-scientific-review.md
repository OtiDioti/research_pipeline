# M0 contract and scientific decision packet — revision 1

**State:** PROPOSED FOR HUMAN SCIENTIFIC REVIEW. Prepared 2026-10-30 after full specification reconciliation; saved locally while CWI was bound, transferred after accepted integration. Administrative design only; not a runtime prompt, executable schema, authorization, expert audit or completed M0 gate. Source: unchanged [project_description.md](../../project_description.md) v1.3, especially §§3–10, 11.2–11.5, 12.3 M0 and 13.1. The original specification controls every field and exception. Concrete APIs and persistence are future CWI work.

The human authorized a mock of the supplied harmonic/quartic example. That choice supplies a development scenario, not a held-out collection, reference certification, release standard or live resource allocation. No material in this packet is described as expert reviewed. The missing scientific decisions below must be supplied before D02/M1 proceeds under the original M0 dependency.

## Decision summary

| Item | Evidence now | Required disposition |
| --- | --- | --- |
| Development example | Human requested the harmonic/quartic mock; [CWI delivery](../../docs/synthetic-oscillator.md), accepted/integrated at 79a84d2 | Inspect/correct the delivered walkthrough; it is not expert certification |
| Pilot and useful progress | Proposed spectral family and example only | Scientific owner confirms the pilot, scope and nontrivial useful outcomes |
| Reference collection | One exposed synthetic case; no audited or held-out set | Supply permitted expert-audited positive/negative references and held-out manifest |
| Evaluation standards | Definitions below; no approved thresholds or scientific budgets | Approve predeclared usefulness/retention/error standards, uncertainty and resource protocol |
| Implementation contracts | Administrative proposal below; production behaviors unimplemented | Review material scientific ambiguities before D02; technical implementation remains CWI work |
| Live execution | No product service/data/budget grant | Separate approval required when live evaluation becomes ready; no such calls now |

## 1. Proposed envelope and permitted use

Development example: quantum spectral questions on the full real line with positive mass/frequency and a harmonic plus quartic potential. The mock contrasts finite-basis computational evidence with full-system ground-state existence, retaining the supplied negative-coefficient instability challenge and a separately scoped positive-coefficient candidate awaiting review. It is a pedagogical scenario, not new research. Metastability/resonance requires a new question/context.

Proposed usefulness: preserve valid scoped algebra/calculation and informative failure, localize why the overbroad interpretation fails, and expose the next discriminating question. A domain owner must decide whether this is a useful pilot family and identify nontrivial additional questions. Merely rejecting every candidate or reproducing the harmonic limit cannot satisfy release usefulness.

Permitted now: synthetic local deterministic fixture preparation using the supplied specification. No product model calls, scientific data ingestion from external/private collections, paid scientific compute or publication. Existing development Codex authority is separate. Every mock assessment carries synthetic provenance and is in the development partition.

## 2. Identity, revision and status contract

All canonical records have stable opaque identities, explicit kind/schema revision, attributed creation event, and exact links to producing/assessing activities. A reference identifies both record identity and revision; a current-pointer lookup cannot substitute in a scientific evidence binding. Scientific content revisions are immutable. Meaning-changing edits create a revision with an explicit predecessor, never overwrite prior content. Proposed and committed timestamps/provenance remain distinct. Schema migrations require versioned, tested transformations and recovery; no automatic reinterpretation of old receipts.

Assessments, issues, policies and promotion eligibility have separate versioned identities from statement revisions. An unchanged claim statement can become ineligible because a premise loses support. Current operational state and current assessment views update transactionally with attributed events. Scientific disposition never derives from task completion, file existence, consensus, a model's confidence or a materialized note property.

| Independent dimension | Required meaning |
| --- | --- |
| Work stage | exploring, frozen candidate, under review, archived; procedure only |
| Scientific disposition | provisional, supported within scope, disputed, support withdrawn, refuted within scope, superseded; attributed assessment |
| Support type | heuristic, analytical, symbolic, numerical, formal, source-based; multiple may coexist |
| Applicability | applicable, requires reassessment, inapplicable, unresolved, tied to target context |
| Novelty | unassessed, known equivalent, search found no equivalent, researcher-assessed contribution; no automatic novelty inference |
| Task / attempt / tool-job status | Separate vocabularies and transition records from §8.3; unknown completion and interrupted partial work stay explicit |

## 3. Core record field matrix

The following is the administrative minimum schema inventory, preserving §5.1 in full. Exact language signatures/serialization and validation belong in bounded CWI requests. Optional/unavailable values must be represented explicitly, without invented measurements or permissions. All references below use exact revisions.

| Record | Required information and relations |
| --- | --- |
| Project | objective, researcher, policies, resource limits, initial-corpus manifest, readiness/intake state, approved active context, run history |
| Run | project, policy/budget allocation, start/end snapshots, state/stop reason, protected handoff/closeout reserves, jobs/liabilities, report revision or pending publication |
| Corpus/seed manifest | admitted exact materials, original paths/provenance, processing permission, inspection coverage, unresolved imports, intake report, later additions |
| Research context | question, equations, definitions, units, conventions, domain/boundary, regime, approximations and limit ordering; existence is an obligation where claimed |
| Branch | parent/context, method, extra hypotheses, scope differences, continuation rationale, current issues |
| Claim revision | precise statement/category/quantifiers, context, assumptions, approximation qualifications and open obligations |
| Justification | all premise revisions jointly required, assumptions, method, conclusion revisions, evidence and assessed limitations; independent alternatives are separate routes |
| Evidence | artifact references, target property/claim, method/inputs, tested scope, result, uncertainty and failure detail; mock versus authentic provenance |
| Source | stable work ID, upstream version/local capture revision, authorship, retrieval/access/reuse, originals/extraction lineage, exact locations, reading coverage, attributed statements |
| Work-product manifest | kind, identity/revision, author/task/branch/context/run, artifact hashes/entry, linked claims/sources, supersession/build dependencies |
| Tool release | identity, pinned local artifact or external version, adapter/interface config, origin/environment, semantics/effects/capabilities, nested behavior and observability limits |
| Tool assessment | exact release/environment, distinct permission and qualification scope, checks/limitations/issues, withdrawal/replacement decision |
| Issue | disputed point, affected records, objection/counterexample, severity, proposed discriminating action and disposition |
| Review | exact frozen candidate, reviewer, independence mode/context exposure, performed checks, assessment and limitations |
| Promotion eligibility | candidate, already-approved sufficient routes, relevant assessment/issue revisions, current context, authority/policy revision and eligibility generation |
| Decision | choice/rationale, real authority, evidence considered, affected records/resulting action; proposal does not become approval |
| Task specification | scientific objective, immutable inputs, expected outputs/completion, tool/visibility policy and allocation |
| Attempt | task/session, exact fitted context, checkpoint source, inherited exposure, fenced authority, timestamps/usage/output, outcome/stop/handoff reason |
| Tool execution | actual invocation/release/inputs, parent/job ID, environment/state, authentic observations/output hashes, descendant receipts/visibility limits, usage or unresolved liability |
| Event | stable ID, attributed change/communication, timestamp and exact affected revisions |

Artifacts are staged, hashed and made immutable before the metadata transaction commits references. Recoverable failures leave no valid canonical record pointing at absent data; retained orphans are reconciled safely. Submissions carry idempotency identity, exact input/base expectations and fencing authority; repeated identical submission is distinguishable from conflicting reuse. Worker submissions create provisional records, not generic database writes or endorsements.

## 4. Support, eligibility and disposition contract

The scientific graph and task-dependency graph are separate. An inference route requires its entire premise conjunction. Multiple independently assessed sufficient routes may support a conclusion. Accepted deductive support cannot depend on its own undischarged conclusion. Task schedules are acyclic; iterative work uses new tasks/revisions.

A failed argument invalidates that route, not automatically every downstream proposition. Stale, inapplicable, incomplete and invalid routes differ from a refuted claim. Conditional implications retain undischarged premises; they cannot become unconditional predictions. Domain nonemptiness and consistency are review obligations, not assumed merely to make an implication true.

Apply-disposition consumes candidate revision, exact review references, eligibility generation, selected already-assessed sufficient routes, current context, policy/authority and relevant issue/assessment versions. It checks them atomically with the assessment write. Any relevant support/issue change synchronously updates affected eligibility and marks dependent uses for reassessment in that transaction, closing stale-promotion windows. A remaining route preserves eligibility only if previously assessed sufficient in the same scope/policy; the controller cannot invent sufficiency. The committed decision records consumed versions. Branch reconciliation preserves historical scopes, disagreements and explicit compatibility decisions; it never broadens claims by merge.

## 5. Message and operation contracts

The inter-agent message envelope additionally identifies sender, recipient, project, task, branch, exact referenced versions, type, visibility and related artifacts. Initial types are assignment, clarification, result submission, issue report, collaboration request, resource request, review request and review response. Preserve originals; summaries link to them. Substantive reviewer/author exchanges remain review evidence.

Each request identifies operation/schema version, attributed caller and authority, immutable inputs, submission/idempotency ID where effects occur, expected revision/eligibility/fence, allowed effects/visibility and bounded resource allocation. Each response distinguishes success, blocked, failure and uncertain effects, returns exact created/read revisions and observations, and preserves recovery instructions/unknown liability. These are responsibilities, not yet an implemented API.

| Operation family (§10.1) | Required input/output obligations |
| --- | --- |
| Initialize / source acquire-import / draft checkout-import / refresh view | exact materials and processing policy → project/corpus/readiness/intake tasks; exact source captures/lineage; draft base/editor → new revision; consistent visibility-filtered snapshot generation |
| Propose/admit task | objective/input/dependencies/expected output/rationale/visibility/budget → proposal/decision or ready/blocked with reason; reserve at dispatch |
| Start attempt / retrieve context | task, model profile, permission and optional checkpoint → fitted manifest/session/exposure/reserve/fenced token; bounded query → permitted exact locators/content and exposure record |
| Execute / register / assess tool / request development | exact release/input/limits → trusted execution/job/observations; staged release has no permission; assessment and authorized enablement separate; development is bounded ordinary/delegated task |
| Submit result / request-review / submit-review | attempt/submission/provisional records/artifacts; frozen candidate/review plan/independence; immutable attributed findings/evidence/limitations; no worker promotion authority |
| Apply disposition / reconcile branch | exact freshness/authority bundle above; receiving context and compatibility assessment → audited disposition or explicit conflict/reassessment |
| Checkpoint-stop / finalize report / export | identity/reason/permitted actions → checkpoint or fallback inventory, state/liability reconciliation, immutable report or pending publication; approved scope/artifacts → portable manifest preserving omissions/reuse restrictions |

## 6. Context, checkpoint and resource contracts

Use the §6.2 deterministic dependency-first builder: filter before traversal/search/ranking, include mandatory core, follow required dependencies, fill optional space by relevance with deterministic ties, then fit the complete prospective request. Deduplicate exact revisions, prefer current unresolved steps over recency, and retrieve proofs/passages before relying on uninspected details. Count tool definitions/instructions/conversation/content, reserve response and handoff headroom plus declared safety margin, and expose counting limitations. Keep excluded-content identities in controller-private audit, not the worker-visible packet. Overflow revises/splits the task or blocks; it never silently drops a premise/equation. Rebuild stale summaries from pinned sources rather than summary chains.

A context manifest records exact source revisions and locators, role/task/authority, mandatory question/context/assumptions/objections/policy/instructions, exclusions and deferred locators, summary origin and freshness, exposure history, token estimation and provider limits. Enforce visibility across source text, filenames, indexes, metadata, fixtures, caches, checkpoints and summaries. Retrieval is bounded and records exposure. Candidate-aware material cannot flow into a blind checker by restarting a session. A summary cannot promote or erase an open obligation.

A checkpoint identifies the exact task/input/context/authority, saved outputs and incomplete fragments, completed versus uncertain operations/jobs, outstanding obligations, inherited exposure, usage/reserves and next proposed action. Continuation rechecks permissions, current revisions/eligibility, context fit and available allocation; a new session renews context capacity only. Partial tool requests never execute. Repeated no-progress rollovers require reassessment. Stale checkpoints do not authorize replay or candidate leakage.

Track input/output/reasoning/cache counters when available and preserve missing values. Separate context capacity, per-call output, cumulative model usage, time, computation, calls, storage and monetary estimates. Reserve conservative enforceable maxima before actions; uncertain jobs retain liability. Never claim a hard cap where the provider supplies no enforceable bound. Ordinary, verification and protected handoff/closeout reservations share the authorized ceiling without double counting. Provider failure cannot prevent local minimal reporting. Pause retains allocation, a new allocation starts a linked run, and cancellation cannot silently reopen work. Numeric scientific allocations remain PENDING HUMAN APPROVAL; development CWI limits are not product budgets.

## 7. Seed, vault, draft, tool and closeout contracts

Readiness requires admitted substantive scientific material and a usable brief, not just tools or an empty shell. Preserve seed originals/provenance/permissions/inspection coverage, conflicts and incomplete imports. Later corpus additions are versioned updates, not silent replacement. Imported assertions remain provisional. Required vault folders, per-folder README indexes, home reading paths, source/claim/artifact links and typed companion manifests follow §§9.7–9.11 and 10.11. Views are regenerable committed generations, not canonical truth. Drafts record base/editor and import as new revisions; preserve conflicts/human edits. LaTeX/macros/notebooks/build inputs are pinned dependencies with artifact lineage. Upstream publication, capture, extraction and reading-report revisions remain distinct.

Adopt the complete logical §9.7 layout: root README.md/project.yaml; brief/ and brief/seeds/; navigation/, literature/, branches/, claims/, reviews/, decisions/, reports/ with reports/runs/<run>/<revision>/; tools/<tool>/<release>/; runs/<run>/attempts/<attempt>/; drafts/, incoming/, controller-private state/, artifacts/objects/, disposable permission-scoped cache/, exports/, backups/, and researcher-owned .obsidian/. Branches contain README.md/branch.md plus revisioned notes, derivations, calculations, notebooks and figures. Create optional directories when useful rather than empty scaffolding. Every meaningful bundle README includes purpose, inventory, current linked work, provenance/snapshot, inspection/build route, dependencies/limits and editing route. Protected copies/immutable revision directories enforce views; no writable object-store hard links. Publication is one complete generation. Backups require separate failure-domain copies and verified restoration. These are runtime-vault obligations, not files to create in the development root now.

Tool identity/configuration/environment are frozen per execution; qualification and operational permission are separate. Passing software tests does not establish scientific applicability. Mock tool observations are never authentic receipts. Optional composite jobs must account for descendants, cancellation, polling, unsettled effects and inclusive-versus-exclusive resource usage; waiting parents yield slots. No optional backend is claimed supported without real invocation/recovery evidence.

Minimum end-of-run report is deterministic over committed state: objective/context and run/policy/allocation; execution outcome/stop reason; scoped supported/partial/negative/unresolved work; exact checks and limitations; output/source manifests; outstanding issues/jobs/liabilities and spent/reserved/unknown usage; saved checkpoints, next discriminating work and required authorization/resources for continuation. It works with no model access, distinguishes no supported conclusions from failure to save work, and records pending publication on storage failure. Synthesis cannot invent or promote claims. Exports enforce reuse/access restrictions, exact citations for omitted material and replay limitations.

## 8. Evaluation protocol proposal and missing scientific evidence

The mock is development-only and exposed to implementers. Do not relabel it held-out. Before evaluating configurations, a human scientific owner must fix immutable task statements, audited reference judgments, scoring criteria, nontrivial result groups, useful-progress/retention/endorsement-error standards, resource budgets and uncertainty handling. This packet intentionally leaves numeric scientific thresholds unapproved rather than inventing them.

Required expert-audited classes (§11.2): valid unfamiliar equivalent derivation; missing boundary/convention change; division losing zero-case solutions; nonuniform perturbation; finite truncation hiding instability; small residual for wrong model/observable; unjustified exchange of limiting operations; shared erroneous inputs in apparently independent computations; apparent counterexample due to uncertainty/convergence; selected noisy effect failing fresh confirmation; formal correctness encoding wrong physics; known result in new notation with overstated novelty. Include positive controls and maintain a separate unexposed held-out manifest. Only the finite-truncation example is currently commissioned as synthetic material; the other eleven and the held-out collection are absent.

Measure incorrect and unsupported acceptance separately, valid-result retention, localized error detection, scope accuracy, repair harm and benefit, inspection/replay/independent reconstruction separately, novelty, question-level useful progress, model/compute/researcher cost, operational/context/handoff integrity, navigation and tool utility. Endorsement-error denominator zero is undefined, not zero. Unresolved truth/novelty stays unresolved. Preserve all attempts and selection decisions. Small samples do not justify universal error claims.

Compare a strong single researcher, independent-checking system and second-method branch where applicable, with matched total resources including tool development and human review. Predeclare ablations and anonymized expert assessment. Refresh compromised held-out material. The full §11.6 reliability cases and §11.5 release gates remain mandatory; the mock and a green software suite cannot satisfy them.

## 9. Human review packet and exact gate

The next required human action is to review this packet together with the delivered mock and return an M0 scientific decision record. That record must identify the accountable scientific reviewer, confirm/correct the pilot and useful nontrivial outcomes, supply permitted expert-audited development/held-out references, and approve the predeclared evaluation/resource standards or identify changes. Correct the mock's scope, argument, expected disposition and limitations explicitly; no response will be inferred from silence.

The coordinator may prepare administrative contracts and the requested synthetic fixture. It cannot certify these scientific inputs. D01/M0 remains incomplete and D02 blocked until the required record/evidence exists. Separate service/data/budget approval is still required before any live product experiment. This is a dependency gate, not a request for routine permission to continue authorized work.

## Delivered example and evidence

[Complete walkthrough](../../docs/synthetic-oscillator.md), [26-record synthetic fixture](../../implementation/evaluations/harmonic_quartic_v1.json), and [actual CWI run evidence](../runs/34bcb77d-1cbc-4432-ba5e-e419e930ad2f.md). Accepted/integrated source `79a84d2ee9ae7dd19539eede86a19753442eed5d`; 28 deterministic software tests passed after integration. This is a source/evidence link, not a domain-expert judgment. The general contracts in this administrative proposal remain design obligations for future CWI implementation; the fixture implements only its focused data contract.
