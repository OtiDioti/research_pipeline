# Synthetic harmonic/quartic paper walkthrough

This is synthetic local **development material**, neither expert-audited nor
held-out evaluation material. The [JSON fixture](../implementation/evaluations/harmonic_quartic_v1.json)
is a paper scenario with expected outcomes, not an execution transcript. Every
record declares `simulation=true`, `execution="not_performed"`, and “Expected
fixture oracle, not observed execution or expert judgment.” All content was authored
together; simulated role labels identify narrative functions, not real people or
independent agents. There are no measurements, authentic tool receipts, scientific
confidence scores, execution timestamps, or resource-account conclusions.

The source is [project_description.md §13.1](../project_description.md), with the
supplied specification SHA-256
`13d2ed9198916b7af3a3f9c3522745b0b6882b5492c9e27ccdc0c46114137ab7`.
This identifies the source specification, not a calculation receipt. The loader
performs no source hashing. Schema version is `1`; fixture version is `1.0.0`.

## Read the example

All `name@1` references below mean the exact JSON object
`{"id": "name", "revision": 1}`. `walkthrough` orders the complete narrative;
relationships always use exact references, never an implicit latest revision.

### Seed, context, and obligations

`seed@1` asks whether the full-line Hamiltonian

\[
H=\frac{p^2}{2m}+\frac{m\omega^2x^2}{2}+\lambda x^4
\]

has a minimum-energy ground state for small quartic coefficients of either sign,
and when a first-order perturbative energy expression is meaningful.
`context-both@1` specifies \(L^2(\mathbb R)\), \(p=-i\hbar d/dx\),
\(m>0,\omega>0,\hbar>0\), real \(\lambda\), consistent units, the
harmonic \(\lambda=0\) reference, and small positive/negative regimes.
The dimensionless coupling is \(g=\lambda\hbar/(m^2\omega^3)\);
\(|g|\ll1\) is symbolic, not an invented numerical accuracy threshold.
The observable is minimum ground-state energy on the full real line.

Normalization, square integrability, decay/regularity and finite expectations on
an appropriate domain describe admissible states. They do not assume a ground
state exists. The three explicit open obligations are:

- `both-existence_domain@1`: establish the Hamiltonian domain, lower boundedness,
  and a normalizable minimum-energy state in the claimed regime.
- `both-approximation@1`: justify the first-order interpretation and its
  remainder/asymptotic behavior and applicability.
- `both-convergence@1`: control truncation error and convergence as \(N\to\infty\).

The projection uses the first \(N\) harmonic states \(|n\rangle\),
\(n=0,\ldots,N-1\), for symbolic positive integer \(N\), forming
\(P_NHP_N\). A finite truncation need not preserve full-line stability.
Readiness is only `simulated_ready`; no product intake is implemented.

### Expected baseline checks and formal exploration

`harmonic-check@1` has expected outcome `pass` within the harmonic baseline only.
`harmonic-algebra@1` gives the documentary derivation: the harmonic ground-state
probability density is proportional to \(\exp(-m\omega x^2/\hbar)\), so

\[
E_0^{(0)}=\hbar\omega/2,\qquad
\langle x^2\rangle=\hbar/(2m\omega),\qquad
\langle x^4\rangle=3\langle x^2\rangle^2.
\]

Taking the expectation of the perturbation gives the **formal first-order** term

\[
\Delta E_0=\lambda\langle x^4\rangle
=3\lambda\bigl(\hbar/(2m\omega)\bigr)^2.
\]

The resulting formal expression
\(E_0\approx\hbar\omega/2+3\lambda(\hbar/(2m\omega))^2\) does not
establish existence of the state whose energy is interpreted. Remainder,
asymptotic and applicability obligations remain open. No formula API, symbolic
engine or numerical solver is provided, and no automated test validates physics
experimentally.

`basis-check@1` has expected outcome `pass` for basis construction only:
orthonormal harmonic states and projected operators should produce a finite
Hermitian matrix for real \(\lambda\). In particular,
\((P_NxP_N)^4\) need not equal \(P_Nx^4P_N\); projection order matters.
`finite-matrix@1` describes the finite-matrix justification: a finite Hermitian
matrix has a lowest eigenvalue. `matrix-task@1` has expected operational outcome
`completed`, but actual execution remains `not_performed`. No matrix was
constructed or diagonalized and no numerical benchmark is supplied.
`baseline@1` captures this exploratory oracle with all obligations retained.

### Exact candidate freeze

`candidate-both@1` provisionally asserts existence and the first-order energy
relation for sufficiently small nonzero coefficients **of both signs** in
`context-both@1`. It references `harmonic-algebra@1`, `finite-matrix@1` and the
three original obligations; support is explicitly incomplete, with no endorsement.
`before-challenge@1` freezes that expected view. The historical candidate remains
unchanged after challenge: its original provisional content is not overwritten by
later dispositions.

### Expected failed existence check and scoped review

`translated-state@1` records the supplied argument. Choose a normalized smooth
compactly supported fixed-width \(\varphi\in C_c^\infty(\mathbb R)\), and
translate it as \(\psi_a(x)=\varphi(x-a)\). These normalized test states retain
admissibility in the test-function domain. The kinetic expectation is translation
invariant. With \(x=a+y\), the harmonic contribution is \(O(a^2)\) while the
quartic contribution is \(\lambda a^4+O(a^3)\) for fixed negative \(\lambda\).
Thus energy tends to \(-\infty\) as \(a\to+\infty\). There can be no lower
bound or minimum-energy full-line ground state in that regime. An expert still
needs to inspect the argument and domain; this text is not an expert assessment.

`negative-check@1` therefore has expected outcome `fail` for existence in the
negative full-line scope, targeting exactly `candidate-both@1` and
`context-both@1`. `negative-review@1` retains that target, all three evidence
records and `translated-state@1`. It explicitly declares no actual blind or
independent review and that all content was authored together.
`negative-issue@1` records the same exact target, context, evidence and argument,
plus the review link.

The universal both-signs interpretation fails through its negative branch. This
does **not** invalidate finite Hermitian matrix diagonalization or erase the formal
Gaussian moment algebra. `after-challenge@1` preserves the old candidate, context,
evidence and obligations while changing its scoped assessment. The justification
and evidence links are a paper evidence graph, not a task scheduling graph or an
accepted deductive proof; reciprocal argument/check links identify the same scoped
challenge and confer no independent corroboration.

### Separate positive candidate and proposed new question

`context-positive@1` has a distinct identity and restricts coefficient signs to
`["positive"]`, with the harmonic case only a reference limit.
`candidate-positive@1` is a distinct frozen identity/revision derived from the
historical candidate. It remains provisional, `pending_review`, unendorsed, and
subject to `positive-existence_domain@1`, `positive-approximation@1` and
`positive-convergence@1`. Its reused analytical and matrix material is explicitly
`requires_applicability_review`, not automatically sufficient support. The old
review cannot assess this new target. No actual positive-branch existence or
approximation judgment is supplied.

`resonance-question@1` proposes a separate metastability/resonance investigation.
It requires a newly defined observable (for example a resonance position/width or
lifetime), boundary conditions, versioned context, task and verification
obligations. None is executed or approved here. It is not an answer substituted
for the original ground-state question.

### Expected snapshots and partial result

These state dimensions are separate fields, all simulated:

| Snapshot | Task status | Work stage | Scientific disposition | Full-line applicability |
| --- | --- | --- | --- | --- |
| `baseline@1` | completed | exploring | provisional | unresolved |
| `before-challenge@1` | completed | frozen_candidate | provisional | requires_reassessment |
| `after-challenge@1` | completed | reconciled | refuted_within_negative_scope | negative_full_line_inapplicable |
| `partial-stop@1` | completed | partial_stop | provisional_pending_review | requires_applicability_review |

All snapshots retain analytical support only for `formal_harmonic_moments` and
numerical support only for `finite_projection`, each `limited_scope_only`.
“Numerical” labels the finite-matrix route, not observed computation. Neither is
promoted to formal proof. Novelty is always `unassessed`, endorsement always
`none`. Each snapshot references `matrix-task@1`, its current context, evidence,
retained and outstanding obligations, and rationale. The baseline has no candidate;
the frozen and challenged snapshots reference the old candidate; the last references
the new one while retaining the old historical candidate. Only the challenged
snapshot invokes `negative-review@1` as its current review; the partial stop retains
the historical issue without attaching the old review to the positive candidate.

`partial-report@1` references `partial-stop@1`, both contexts, the original and
positive candidates, all three justifications and evidence records, the historical
review/issue, the still-completed matrix task, all six obligations, and the proposed
follow-up. Its expected stop reason is `paper walkthrough stops pending review`.
Useful results and the failed interpretation remain separately described. Its next
discriminating action is expert examination of the scoped argument and of positive
existence/domain, approximation and convergence requirements. All independence and
expert-review gaps remain open.

Resource fields represent execution as `not_applicable` and usage, cost and
liability as `not_measured`, each with quantitative `value=null`. Missing execution
data does not mean zero usage or zero liability. No real account/resource conclusion
follows. This is a synthetic partial-report record, not a running/stopped controller.

## Public loader and validation contract

`research_pipeline.fixtures` exposes:

- `load_oscillator_fixture(path=None) -> dict`: read UTF-8 JSON, validate it and
  return a freshly parsed mutable nested tree. Independent calls share no mutable
  data. Explicit relative paths have ordinary caller-relative semantics.
- `validate_oscillator_fixture(data) -> None`: check a JSON-shaped dictionary/list
  representation without mutation; return `None` on success.
- `FixtureValidationError(ValueError)`: malformed JSON/encoding or contract errors,
  with a useful field/record location and source path when loaded from a file.

The default path is derived from the module's resolved source location:
`implementation/evaluations/harmonic_quartic_v1.json`. It does not depend on cwd,
installed distribution metadata or another checkout. A relocated source tree works
with its accompanying `evaluations` directory. Missing or unreadable files raise
ordinary `OSError` subclasses, including the path. No fallback acquisition occurs.
Duplicate JSON keys and nonstandard `NaN`/`Infinity` are rejected. Import performs
no fixture reads. Loading and validation have no cache, downloads, writes, directory
creation, subprocesses, environment changes, output or persistence behavior.

### Representation and required fields

Top-level fields are exactly `schema_version`, `fixture_version`, `metadata`,
`records` and `walkthrough`. Only schema `1` and fixture `1.0.0` are supported;
version changes require an explicit contract update. Metadata requires `source`,
`section`, `specification_sha256`, `origin="synthetic_local"`,
`visibility="development"` and the common provenance markers below.

Every record requires a nonempty string `id`, positive integer `revision` (not a
boolean), `kind`, `simulated_role`, and these exact provenance markers:
`synthetic=true`, `classification="synthetic-development"`, `expert_audited=false`,
`held_out=false`, `simulation=true`, `execution="not_performed"`, and the
`oracle_statement` quoted at the start. No extra contract fields are accepted,
including nested references/resources/support entries. Textual explanations must
be strings of at least 20 stripped characters; this is a structural guard, not a
prose or physics quality assessment.

The following table lists **all additional fields** for each kind. `ref(kind)` is
an exact `{id, revision}` object, `refs(kind)` a nonempty ordered duplicate-free
list. Nullable fields are identified explicitly. All remaining explanation fields
are substantive strings. The scenario relationships described above further
constrain the finite vocabularies and links; this is not a general-purpose schema.

| Kind / simulated role suffix | Additional fields and rules |
| --- | --- |
| `seed` / requester | `question`; `context`: ref(context); `readiness=simulated_ready` |
| `context` / framer | `scope`: both_signs or positive; `coefficient_signs`: [positive, negative] or [positive], respectively; `domain=full_real_line`; `observable=minimum_energy_ground_state`; `hamiltonian`, `parameters`, `units`, `small_parameter`, `boundary_assumptions`, `projection`; `existence_is_obligation=true` |
| `obligation` / framer | `context`: ref(context); `category`: existence_domain, approximation or convergence; `status=unresolved`; `requirement` |
| `candidate` / explorer | `context`: ref(context); nullable `derived_from`: ref(candidate); `statement`; `disposition=provisional`; `review_status`: awaiting_challenge or pending_review; `endorsement=none`; `justifications`: refs(justification); `support_use`: incomplete or requires_applicability_review; `obligations`: refs(obligation); `frozen=true` |
| `justification` / explorer | `context`: ref(context); `method`: analytical, finite_matrix or translated_trial_state; `scope`: formal_harmonic_moments, finite_projection or negative_full_line, respectively; `explanation`; `evidence`: refs(evidence) |
| `evidence` / checker | `context`: ref(context); `purpose`: harmonic_limit, basis_construction or negative_existence; corresponding `scope`: harmonic_baseline, finite_projection or negative_full_line; `expected_outcome`: pass, pass or fail, respectively; nullable `target`: ref(candidate), and `argument`: ref(justification), both required for the negative check and null otherwise; `explanation` |
| `task` / executor | `context`: ref(context); `justification`: ref(justification); `evidence`: refs(evidence); `expected_outcome=completed`; `scope=finite_projection`; `completion_condition` |
| `review` / reviewer | `target`: ref(candidate); `context`: ref(context); `evidence`: refs(evidence); `argument`: ref(justification); `expected_outcome=refuted_within_scope`; `refuted_scope=negative_full_line`; `preserved_scopes=[formal_harmonic_moments, finite_projection]`; `independence=none_no_blind_or_independent_review`; `all_authored_together=true`; `assessment` |
| `issue` / reviewer | `target`: ref(candidate); `context`: ref(context); `review`: ref(review); `evidence`: refs(evidence); `argument`: ref(justification); `disposition=negative_interpretation_refuted`; `explanation` |
| `snapshot` / coordinator | `stage`: baseline, frozen, challenged or partial_stop; `task`: ref(task); nullable `candidate`: ref(candidate), `review`: ref(review), `issue`: ref(issue), `historical_candidate`: ref(candidate); `context`: ref(context); `evidence`: refs(evidence); `retained_obligations`, `outstanding_obligations`: refs(obligation); `operational_status`, `work_stage`, `scientific_disposition`, `applicability` as in the snapshot table; `novelty=unassessed`; `endorsement=none`; `support` as specified below; `rationale` |
| `proposed_question` / explorer | `derived_from`: ref(candidate); `status=proposed_requires_new_specification`; `observable`, `boundary_conditions`, `context_requirement`, `task_requirement`, `question` |
| `partial_report` / reporter | `snapshot`: ref(snapshot); `historical_candidate`: ref(candidate); `contexts`: refs(context); `evidence`: refs(evidence); `justifications`: refs(justification); `review`: ref(review); `issue`: ref(issue); `task`: ref(task); `pending_candidate`: ref(candidate); `followup`: ref(proposed_question); `obligations`: refs(obligation); `stop_reason="paper walkthrough stops pending review"`; `retained_results`, `failed_interpretation`, `next_action`; `pending_review=true`; `resources` as below |

Role labels are the suffix in the table prefixed with `simulated_`.
Snapshot `support` is an ordered list of two objects with exactly `type`, `scope`
and `applicability`: analytical/formal_harmonic_moments/limited_scope_only, then
numerical/finite_projection/limited_scope_only. Report `resources` has exactly
`execution`, `usage`, `cost`, `liability`, each an object with `status` and `value`
as described above, plus `statement` exactly
`No real account/resource conclusion follows from this fixture.`

Identity/revision pairs are globally unique, with a consistent kind across revisions
of one identity. Different revisions may coexist where they fill distinct narrative
roles (for example snapshot stages); this contract requires one record per role,
not arbitrary extra history. Original and positive candidates and contexts require
distinct identities. Every relationship resolves against the global exact index,
with target kinds enforced. All records must occur in the complete ordered
walkthrough. Filesystem paths are not scientific evidence references.

Validation first checks shape, provenance and typed references, then the required
scenario roles, obligations, scope and expected state transitions. It requires the
original exact review target, surviving historical links, unchanged finite-task
completion, negative-scope refutation and a distinct unendorsed positive scope.
It rejects old-review transfer or finite-task completion promoted to full-line
support. It does not search prose for scientific keywords or compare the entire
file to a golden literal. Harmless explanatory changes remain valid. Mathematical
arguments, boundary/domain assumptions and rationale require human inspection.

## Commands and evidence limits

From the repository root, without installation:

```bash
PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B -c 'from research_pipeline.fixtures import load_oscillator_fixture; data = load_oscillator_fixture(); print(data["fixture_version"])'
/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py
PYTHONPATH="$PWD/implementation/src:$PWD/implementation" /home/francesco/miniconda3/bin/python3 -B -m unittest tests.test_fixtures -v
```

The loader itself prints nothing; the first command explicitly prints the version.
The permanent validator runs the complete existing suite plus fixture tests.
Focused tests follow exact narrative links, independently assert before/after
state tuples, mutate fresh deep copies, check loader failures and mutation
isolation, and guard fresh imports/loads under `-B` from unrelated cwd with
candidate-first `PYTHONPATH`. They also exercise a relocated source tree and compare
fixture bytes/directory entries. Audit hooks guard writes, processes, network and
environment changes while permitting local reads. These are observed inertness
checks, not a sandbox guarantee or proof of scientific independence. Controller
validation, Reviewer verification and coordinator integration remain separate
from local test feedback.

## Human review checklist and remaining scope

- Correct the original both-signs and positive-only candidate scopes and obligations.
- Inspect the translated-state argument, admissible test-state domain and negative
  coefficient restriction.
- Inspect the harmonic Gaussian derivation, formal/asymptotic limitations, projection
  construction and finite-truncation limitations.
- Confirm the expected dispositions and preservation of exact historical candidate,
  context, algebra, evidence and unresolved obligations through the report.
- Identify missing independent/expert assessments and specify the next positive-branch
  existence/domain, approximation and convergence work before endorsement.

This fixture does not implement intake, research execution, production persistence,
promotion or recovery. It does not complete M0, choose a pilot, supply expert-audited
reference judgments, establish held-out performance or waive D02's pilot,
expert-audit and predeclared protocol prerequisites. The CLI continues to state that
research execution is unavailable. Complete fixture content, this walkthrough and
substantive adverse cases require final review in addition to test results.
