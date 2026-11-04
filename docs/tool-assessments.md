# Passive attributed Tool assessments

`research_pipeline.tool_assessment` declares a supplied assessment of an exact
ToolRelease record revision and its supplied release identity. Pure content and
`research_pipeline.tool_assessment_envelope` conversion check local consistency.
They read no targets, artifact bytes, store, files, clock, environment, credentials,
providers or network, and execute no assessed material. Text, equations, HTML,
URLs and shell-like prose are retained literally.

A pass/fail is an **attributed supplied assessment**, not scientific truth.
Reported permission never grants permission. Builder self-tests, assessor
assertions, reported executions and independent reviews remain distinct reports.
Even an exact `tool_execution` reference cannot authenticate a receipt. Declared
independence, empty sharing lists, actor names, valid hashes and successful round
trips establish no actual absence of exposure, authenticity or admission.

## Public interfaces and identity

Import directly from the two pure submodules; package exports are unchanged.
[Transactional persistence](tool-assessment-persistence.md) extends existing store
dispatch and selected inspection. Content public signatures are:

```text
ToolAssessment(*, assessment_id: str, attribution: dict, target: dict,
               environment: dict, scope: dict, checks: dict, reviews: dict,
               limitations: dict, issues: dict, execution_permission: dict,
               qualification: dict, lifecycle: dict,
               limits: ToolAssessmentLimits | None = None)
ToolAssessment.to_dict(self, *, limits: ToolAssessmentLimits | None = None) -> dict
ToolAssessment.from_dict(cls, value: dict, *, limits: ToolAssessmentLimits | None = None) -> ToolAssessment
ToolAssessment.assessment_id  # read-only explicit stable opaque identity
ToolAssessment.__eq__(self, other)
decode_content(value: dict, *, limits: ToolAssessmentLimits | None = None) -> ToolAssessment
dumps_content(value: ToolAssessment, *, limits: ToolAssessmentLimits | None = None) -> str
loads_content(data: str | bytes, *, limits: ToolAssessmentLimits | None = None) -> ToolAssessment
ToolAssessmentLimits(max_wire_bytes=1048576, max_canonical_bytes=1048576,
                     max_string_chars=16384, max_collection_items=256,
                     max_references=1024, max_nodes=32768, max_depth=24,
                     max_reconstruction_units=262144)
```

`ToolAssessmentValidationError` derives from `DomainValidationError`;
`ToolAssessmentLimitError` derives from it and names the exceeded ceiling.
The content module exposes both errors and `ToolAssessmentLimits`.

The frozen, unhashable value retains only ordinary private `_json` text, never
caller containers, reference instances or processing limits. There is no generated
dataclass equality. Every public consumption revalidates the entire snapshot.
Equality validates the left operand first, returns `NotImplemented` for any
non-exact other class without inspecting that operand, then validates an exact
right operand and compares complete canonical values. Equal `assessment_id`
values alone do not establish equality. The property and equality intentionally
use fresh default limits. All other internal consumption forwards smaller caller
limits. Supplied serializer overrides do not run.

`assessment_id` is explicitly supplied, not a generated content digest or
certificate. `target.release_id` is a supplied ToolRelease identity; conversion
does not recompute it or claim that it matches a resolved target. Envelope creator
provenance is distinct from top-level assessor attribution and from every nested
check/evidence/review/issue/decision reporter. Missing nested actors and dates are
never filled from an enclosing attribution.

## Closed version-one schema

Every object below is closed: every listed field is mandatory, including nulls
and known-empty lists. Listed order defines schema traversal, regardless of
external object order. The root has exactly:

```text
format, version, kind, assessment_id, attribution, target, environment, scope,
checks, reviews, limitations, issues, execution_permission, qualification, lifecycle
```

Constants are `format="research_pipeline.tool_assessment_content"`, exact integer
`version=1`, `kind="tool_assessment"`. The root sections are described below.

Notation: `T` is ordinary Unicode-scalar text (possibly empty); `N` is nonblank T,
retained without trimming; `I` is a domain opaque ID (1–128 ASCII letters/digits/
underscore/hyphen, beginning with a letter/digit); `D` is `sha256:` plus 64 lowercase
hexadecimal digits; `L(X)` is an ordered list of X. Every prose-list element is N.
Integers are exact signed-64-domain `int`, excluding bool/subclasses; reference
revisions are positive, artifact sizes nonnegative. Content has no boolean or
floating scalar fields. Known dates must be nonempty valid domain UTC timestamps
`YYYY-MM-DDTHH:MM:SS[.ffffff]Z`; authored fractional precision is preserved.

`F(X)` is exactly `{state, value, reason}`:

| State | Value | Reason |
| --- | --- | --- |
| known | valid X, never null | null |
| unknown | null | nonblank explanation |
| unavailable | null | nonblank explanation |

Known empty lists are allowed except for the local rules below. Unknown and
unavailable remain reasoned missing information, never empty observations, zero
usage or zero liabilities.

Constructor objects must be exact dict; collection positions accept exact list
or tuple, and reference slots require exact existing domain `RecordReference` or
`ArtifactReference` instances. Wire decoders require exact dict/list and complete
ordinary reference dictionaries. No boundary accepts both typed and wire pins.
Subclasses, arbitrary mappings/sequences, generators and lookalikes are rejected
without their hooks or metaclass equality/hash. Shared dict/list/tuple identities
and cycles are rejected before copying; equal independent containers are legal.
Repeated exact immutable pin instances are legal, validated and charged for each
occurrence, then detached. This rule does not change ToolRelease alias behavior.

Complete references are `RecordReference={record_id:I, revision:positive int,
relationship:I, target_kind:non-null supported kind}` and
`ArtifactReference={digest:64 lowercase hex digits, size:nonnegative int}`.
Across the declaration, one digest cannot have conflicting sizes and one
record_id/revision pair cannot have conflicting target kinds. Repeated equal
reports and repeated record occurrences, including different valid roles, survive;
only configuration names, dependency names and check IDs have uniqueness rules.

### Attribution, independence and target

`Attribution={actor:F(N), reported_at:F(timestamp), origin}`; origin is
`synthetic | unverified`. actor is descriptive reported authorship, not an
authenticated domain actor ID. Top-level `attribution` identifies the assessor.

`Independence={requested_mode:F(mode), reported_mode:F(mode),
shared_formulation:F(L(N)), shared_sources:F(L(N)), shared_lemmas:F(L(N)),
shared_method:F(L(N)), shared_implementation:F(L(N)), shared_communications:F(L(N)),
limitations:F(L(N))}`. mode is `answer_blind_reconstruction |
proof_blind_reconstruction | candidate_aware_audit`. Requested and reported modes
may differ. Empty sharing reports prove no actual absence of exposure.

`target={release:RecordReference, release_id:D}`. release has role
`assessed_release` and targets `tool_release`.

### Environment and scope

`environment={kind, identity:F(N), reported_version:F(N),
implementation_version:F(N), configuration:F(L(Setting)), observability,
records:F(L(RecordReference)), artifacts:F(L(ArtifactReference)),
dependencies:F(L(Dependency)), limitations:F(L(N))}`.

kind is `local | remote | composite | unknown | unavailable`; observability is
`pinned_description | reported_version_only | opaque | unknown | unavailable`.
`Setting={name:N, value:T}`; names are unique within known configuration.
`Dependency={name:N, reported_version:F(N), records:F(L(RecordReference)),
artifacts:F(L(ArtifactReference)), limitations:F(L(N))}`; dependency names are
unique within the known list.

Environment records use `assessed_environment` targeting `source |
work_product_manifest`. Dependency records use `assessed_dependency` targeting
`source | work_product_manifest | tool_release`. `pinned_description` requires
known nonempty environment records or artifacts. `reported_version_only` requires
a known nonblank reported_version or implementation_version. Remote kind or opaque
observability rejects known-empty limitations; known nonempty or reasoned missing
limitations are allowed. Environment artifact pins describe supplied configuration
material, not a running environment; a pinned description does not freeze remote
implementation. Remote versions may remain missing with reasons.

`scope={intended_uses:F(L(N)), tested_scope:F(L(N))}`. Authored domains, regimes,
units, tolerances, exclusions and intended uses are not interpreted.

### Evidence and checks

Common outcome vocabulary: `unperformed | pass | fail | inconclusive`.
Common dimensions: `operational_interface | software_behavior |
scientific_applicability`. Common evidence bases: `assessor_assertion |
builder_self_test | reported_tool_execution | independent_review`.

`Evidence={basis, attribution:Attribution, statement:F(N),
records:F(L(RecordReference)), artifacts:F(L(ArtifactReference)),
resource_usage:F(L(N)), unresolved_liabilities:F(L(N)), independence:Independence,
limitations:F(L(N))}`. Narrative usage/liabilities do not update a ledger.

| Basis | Record role | Allowed target kinds | Local requirement |
| --- | --- | --- | --- |
| assessor_assertion | reported_assertion | source, work_product_manifest, evidence | known nonblank statement; pins may be empty/missing |
| builder_self_test | builder_self_test | work_product_manifest, evidence | known nonempty records or artifacts identifying supplied report |
| reported_tool_execution | reported_tool_execution | tool_execution | known nonempty records |
| independent_review | independent_review | review | known nonempty records |

These categories describe supplied evidence, not authenticity. A statement that a
tool ran without an exact reported-execution pin belongs under assessor_assertion.

`checks=F(L(Check))` where `Check={check_id:I, dimension, basis,
attribution:Attribution, outcome, scope:F(L(N)), method:F(N), expected:F(N),
observed:F(N), definition_records:F(L(RecordReference)),
definition_artifacts:F(L(ArtifactReference)), evidence:F(L(Evidence)),
independence:Independence, limitations:F(L(N))}`. check_id is unique within known
checks. Definition records use `check_definition` targeting `source |
work_product_manifest`; frozen definitions/acceptance methods stay distinct from
result evidence.

Pass/fail requires known nonempty scope, known nonblank method/expected/observed,
and known nonempty evidence with at least one item matching the check's basis.
This is local declaration consistency, not an evidence-sufficiency judgment.
Unperformed requires unknown/unavailable observed and evidence either known empty
or reasoned missing; planned definitions remain allowed. Inconclusive may retain
unknown observations and missing evidence. Neither outcome nor observations are
inferred from the other.

### Reviews, issues and top-level limitations

`reviews=F(L(ReportedReview))` where `ReportedReview={review:RecordReference,
attribution:Attribution, outcome, scope:F(L(N)), rationale:F(N),
evidence:F(L(Evidence)), independence:Independence, limitations:F(L(N))}`.
review uses `reported_review` targeting `review`. Every non-unperformed outcome
requires known nonempty scope and known nonblank rationale. Review references and
independence reports remain unverified.

`issues=F(L(ReportedIssue))` where `ReportedIssue={issue:RecordReference,
attribution:Attribution, category, summary:F(N), affected_scope:F(L(N)),
evidence:F(L(Evidence)), limitations:F(L(N))}`. issue uses `reported_issue`
targeting `issue`. category is `operational_interface | software_behavior |
scientific_applicability | observability | other`. Scientific defects remain
distinct from operational restrictions. Root `limitations` is F(L(N)).

### Independent permission, qualification and lifecycle

`execution_permission={status, attribution:Attribution, scope:F(L(N)),
rationale:F(N), decisions:F(L(RecordReference)), evidence:F(L(Evidence)),
limitations:F(L(N))}`. status is `unassessed | permitted | denied | revoked |
restricted | unknown`. Decisions use `reported_permission_decision` targeting
`decision`. Permitted/denied/revoked/restricted requires known nonblank rationale;
permitted/restricted additionally requires known nonempty scope. Reports grant no
execution authority.

`qualification={operational_interface:QualificationReport,
software_behavior:QualificationReport, scientific_applicability:QualificationReport}`.
`QualificationReport={outcome, attribution:Attribution, scope:F(L(N)),
rationale:F(N), decisions:F(L(RecordReference)), evidence:F(L(Evidence)),
limitations:F(L(N))}`. Decisions use `reported_qualification_decision` targeting
`decision`. Every non-unperformed outcome requires known nonempty scope and known
nonblank rationale. Matching checks, independent evidence or scientifically
sufficient evidence are not required to record an attributed qualification report;
evidence may be explicitly absent or reasoned missing. Check pass never implies
qualification.

`lifecycle={status, reason_category, attribution:Attribution, scope:F(L(N)),
rationale:F(N), decisions:F(L(RecordReference)), evidence:F(L(Evidence)),
limitations:F(L(N)), replacement:F(Replacement),
supersedes:F(L(RecordReference)), superseded_by:F(RecordReference)}`.
status is `unassessed | active | restricted | suspended | withdrawn | superseded |
unknown`. reason_category is `unassessed | routine_revision |
operational_restriction | software_defect | scientific_defect | observability_limit |
other | unknown`. Decisions use `reported_lifecycle_decision` targeting `decision`.
`Replacement={release:RecordReference, release_id:D}` uses `replacement_release`
targeting `tool_release`. supersedes uses `supersedes_assessment` targeting
`tool_assessment`; superseded_by uses `superseded_by_assessment` targeting
`tool_assessment`.

Active/restricted/suspended/withdrawn/superseded requires known nonblank rationale.
Superseded requires known replacement or known superseded_by. A replacement cannot
name the assessed exact record_id/revision pair; its release_id may equal the
target's because distinct record revisions can repeat content. Assessment links
impose no chronology or history resolution.

All dimensions vary independently under only these local rules. Denied/revoked
permission may coexist with operational pass; software pass may coexist with
scientific fail/inconclusive/unperformed; withdrawn reports may retain successful
checks. No confidence score, trusted/enabled flag, scientific disposition, current
release selection or liability release is inferred.

## Pure envelope conversion and complete projections

```text
ToolAssessmentEnvelopeLimits(max_metadata_chars=262144,
                             max_projection_references=1024,
                             max_provenance_depth=24)
encode_envelope(record_id: str, revision: int, content: ToolAssessment,
                provenance: CreationProvenance, *,
                limits: ToolAssessmentLimits | None = None,
                envelope_limits: ToolAssessmentEnvelopeLimits | None = None) -> RecordEnvelope
decode_envelope(envelope: RecordEnvelope, *,
                limits: ToolAssessmentLimits | None = None,
                envelope_limits: ToolAssessmentEnvelopeLimits | None = None) -> ToolAssessment
```

Both directions require exact classes, an explicit domain record_id, positive
revision, valid exact CreationProvenance, kind tool_assessment and both states null.
record_id must equal assessment_id. Revision/creator/provenance do not enter
content. Encoding returns fresh provenance, pins and snapshot; decoding returns
fresh content and never builds a discarded RecordEnvelope. Missing/extra/reordered/
substituted projections fail without repair; supplied object equality is not
trusted before validation. Retained projection collections must be exact tuples.

Unknown/unavailable facts project nothing. Every record occurrence is projected
in this fixed order, preserving each list's authored order:

1. target.release.
2. environment.records; then each dependency's records in dependency order.
3. Each check: definition_records, then evidence records in evidence order.
4. Each review: its review pin, then evidence records.
5. Each issue: its issue pin, then evidence records.
6. Permission decisions, then permission evidence records.
7. Qualification dimensions in operational_interface, software_behavior,
   scientific_applicability order: each dimension's decisions, then evidence records.
8. Lifecycle decisions, evidence records, known replacement.release, supersedes,
   then known superseded_by.

Artifact candidates have their own order: environment.artifacts; dependency
artifacts in dependency order; each check's definition_artifacts then evidence
artifacts; review evidence artifacts; issue evidence artifacts; permission evidence
artifacts; qualification evidence artifacts in the fixed three-dimension order;
lifecycle evidence artifacts. Project only the first occurrence of each digest.
Every later duplicate still undergoes complete content accounting, validation and
size consistency. Attribution, independence, scope and prose contain no pins.

## Finite controls, guarded operations and errors

All limit classes are exact frozen slots dataclasses. None creates fresh defaults.
Every field accepts exact int from zero through its default, which is also its
hard maximum. Missing/bypassed fields, subclasses, bool, floats, negatives and
increases fail; ceilings never clamp, expand, enter wire content or remain retained.
Revalidate controls at every public entry, before any payload work.

| Content ceiling (validation order) | Default / hard maximum | Complete accounting |
| --- | ---: | --- |
| max_wire_bytes | 1048576 | external loads UTF-8 bytes including whitespace |
| max_canonical_bytes | 1048576 | entire canonical root, headers, keys, escapes, framing |
| max_string_chars | 16384 | decoded Unicode scalar count per string, including keys |
| max_collection_items | 256 | members of each object/array independently |
| max_references | 1024 | every record/artifact occurrence before deduplication |
| max_nodes | 32768 | every container/key/scalar/null/empty occurrence |
| max_depth | 24 | container nesting, root depth one |
| max_reconstruction_units | 262144 | nodes plus all decoded string lengths, including repeated text/keys |

There are no bundle-path charges. Zero wire allowance is harmless outside external
loads. Bytes are sized before UTF-8 decoding. External str is checked by character
lower bound then incremental UTF-8 widths before encoding allocation. A reused
allocation-light lexical scanner guards canonical width, strings, collections,
depth, nodes and reconstruction before json.loads, rejecting invalid escapes,
lone surrogates, out-of-range integers, booleans, floats and nonfinite tokens.
Duplicate decoded keys fail at every depth. Legal external `-0` normalizes to zero.
Constructor/dict trees receive complete iterative preflight before copying,
serializers, reference construction or semantics. The schema walk then checks
aliases, all pin occurrences, roles and local types before detachment.

Content precedence: controls; exact receiver/class/input type; lexical/tree bounds;
missing discriminator; closed schema and aggregate/alias checks in schema order;
local semantics including global size/kind conflicts; canonical serialization and
retained-canonical comparison. A missing format on otherwise bounded input raises
existing `NotTypedContentError`. Unsupported format/version/kind and other failures
raise assessment errors. Expected JSON/Unicode/attribute/type/recursion/overflow/
domain failures retain causes without echoing documents; programmer assertions
propagate. Ordinary Python signature TypeError may remain. Retained `_json` must
be exact str, bounded first by canonical bytes, fully scanned and checked, and
already canonical. It is never repaired. Canonical JSON uses sorted keys, compact
separators, ensure_ascii=True, allow_nan=False and no newline. Arrays/text survive
literally; legal external whitespace, order and equivalent escaping normalize.

| Envelope ceiling (validation order) | Default / hard maximum | Accounting |
| --- | ---: | --- |
| max_metadata_chars | 262144 | record_id, kind, creator actor/time/full retained details JSON; each projected record_id/relationship/target_kind and artifact digest |
| max_projection_references | 1024 | record occurrences plus artifact projection entries; every supplied tuple element before inspection |
| max_provenance_depth | 24 | provenance details containers, root object depth one |

Repeated records count repeatedly; provenance escapes and framing count fully.
Content text has separate content ceilings; bounded integer widths need no extra
metadata charge. Supplied and prospective projections are independently charged
from the same base, never summed or substituted. Prospective counts/metadata are
checked incrementally before appending; no candidate inventory is flattened first.

Envelope stages are contractual, with listed field order within each stage:

1. **A:** Validate content controls, envelope controls, exact receiver; read required
   raw fields, reject non-null states, require exact tuples and bound their combined
   lengths before element access.
2. **B:** Read fixed raw base/provenance/supplied-pin fields. Check exact scalar types
   and cumulative text lengths before scanning/copying/parsing/reference construction.
   Complete supplied metadata bounds before scalar syntax: positive revisions,
   nonnegative sizes, IDs/kinds/digests, canonical creator time and envelope kind.
3. **C:** Bound/parse retained content, preflight, check closed schema/aliases and
   aggregate occurrences, without constructing domain pins. Missing format keeps
   NotTypedContentError.
4. **D:** Incrementally bound complete prospective projections and metadata before
   provenance reconstruction, full semantic reference validation or generic snapshots.
5. **E:** Validate provenance details, complete content semantics/canonicality, require
   stable identity agreement, then compare complete supplied and expected projections.
6. **F:** Encode fresh references/provenance/envelope, or return fresh decoded content.

Earlier stages win over later contradictions. A bounded preflight deficit reports
its exceeded dimension. Content semantic failures precede identity/projection
mismatches. Provenance details retain generic domain JSON scalars, including bool,
signed integers and finite floats; content's scalar restrictions do not apply.
After the metadata bound, an escape-aware depth-sized bracket scanner enforces
max_provenance_depth before each push and before json.loads. Retained details must
be exact ASCII canonical JSON for an ordinary object; duplicate keys, nonfinite
constants/parsed floats, malformed dates, surrogate contradictions, whitespace and
key-order normalization opportunities fail. Reconstruction must reproduce exact
retained creator timestamp and details text. Expected parser/recursion/number
conversion failures use assessment errors.

For already charged n ASCII provenance characters, token lengths, decoded string
characters, container memberships and node occurrences are each at most n. These
are finite upper bounds, not attainable equalities for every valid object. Depth
is independently bounded; there is no unbounded iterable or pending-child expansion.
Content max_string_chars and max_wire_bytes are never imposed on metadata.

## Remaining duties

This v1 boundary advances only structural contracts. Generic tool_assessment rows
and ToolRelease reported_qualification existence/kind-only links remain unchanged.
[Typed persistence](tool-assessment-persistence.md) now supplies transactional exact
target/release/history pairing and local selected inspection. Later work must provide
authenticated scoped decisions/enablement/withdrawal,
qualification enforcement, actual isolated execution, authentic receipts and
recovery, scientific review, live evaluation and human acceptance. This is not full
D05, M0-E or product completion; no current-release selection, persisted admission
certificate, eligibility or scientific judgment follows from these reports.

Focused development tests use stock unittest's native quiet mode, which retains
failure diagnostics, executed-test counts and exit codes:

```sh
PYTHONPATH=implementation/src:implementation python3 -B -m unittest -q tests.test_tool_assessment tests.test_tool_assessment_bounds tests.test_tool_assessment_envelope tests.test_tool_assessment_envelope_bounds tests.test_tool_assessment_example
```

Process-global sentinels run in serial unittest methods within the existing
validator's isolated module workers. Tests use fresh in-memory declarations and
the example subprocess uses candidate-local imports. Controller validation,
independent review and acceptance remain separate responsibilities.

## Executable in-memory example

The exact block below imports only product modules and stdlib. Its independently
checked pins and supplied release identity do not resolve records or certify any
running implementation. It opens no store/files/services/credentials and executes
no assessed tool.

<!-- tool-assessment-example:start -->
```python
from hashlib import sha256
from research_pipeline.domain import ArtifactReference, RecordReference, CreationProvenance, RecordEnvelope
from research_pipeline.tool_assessment import ToolAssessment, ToolAssessmentValidationError, dumps_content, loads_content
from research_pipeline.tool_assessment_envelope import encode_envelope, decode_envelope


DIMENSIONS = ("operational_interface", "software_behavior", "scientific_applicability")
PROSE = '  ∫₀¹ x² dx = 1/3; 😀\x7f\n<script>text</script> $(echo inert) https://example.invalid/a?q=1  '


def known(value):
    """Create an independent explicit known fact, preserving its payload literally."""
    return {"state": "known", "value": value, "reason": None}

def missing(state="unknown", reason="The reporter supplied no observation."):
    """Create reasoned missing information rather than inferring an empty report."""
    return {"state": state, "value": None, "reason": reason}

def attribution(actor="Synthetic assessor"):
    """Describe reported authorship and retain authored timestamp precision."""
    return {"actor": known(actor), "reported_at": known("2026-10-30T12:34:56.12Z"), "origin": "synthetic"}

def independence():
    """Report mismatched requested/actual visibility and explicit shared exposure."""
    return {"requested_mode": known("proof_blind_reconstruction"),
            "reported_mode": known("candidate_aware_audit"),
            "shared_formulation": known(["Same supplied equation; no independent derivation."]),
            "shared_sources": missing(), "shared_lemmas": known([]),
            "shared_method": known(["Shared quadrature method."]),
            "shared_implementation": known(["Same builder implementation was visible."]),
            "shared_communications": missing("unavailable", "Earlier communications were not retained."),
            "limitations": known(["Exposure prevents a blindness claim."])}

def record(name, role, kind, revision=2):
    """State a complete exact wire pin without product serializers."""
    return {"record_id": name, "revision": revision, "relationship": role, "target_kind": kind}

def artifact(name):
    """Hash inert in-memory synthetic bytes, returning an independent wire pin."""
    data = (name + "\n").encode("utf-8")
    return {"digest": sha256(data).hexdigest(), "size": len(data)}

def evidence(name, basis="assessor_assertion"):
    """Build separately attributed evidence with supplied pins and unknown liabilities."""
    roles = {"assessor_assertion": ("reported_assertion", "source"),
             "builder_self_test": ("builder_self_test", "work_product_manifest"),
             "reported_tool_execution": ("reported_tool_execution", "tool_execution"),
             "independent_review": ("independent_review", "review")}
    role, kind = roles[basis]
    return {"basis": basis, "attribution": attribution(name + " reporter"),
            "statement": known(PROSE), "records": known([record(name, role, kind)]),
            "artifacts": known([artifact(name)]), "resource_usage": missing(),
            "unresolved_liabilities": missing("unavailable", "No authentic usage ledger was supplied."),
            "independence": independence(), "limitations": known(["This is a supplied report, not an authentic receipt."])}

def report(name, outcome, role):
    """Build a qualification-like decision report with explicit scope and evidence."""
    return {"outcome": outcome, "attribution": attribution(name), "scope": known(["x ∈ [0,1]; dimensionless"]),
            "rationale": known("Supplied scoped assessment: " + outcome),
            "decisions": known([record(name + "_decision", role, "decision")]),
            "evidence": known([evidence(name + "_evidence")]), "limitations": missing()}

def wire(scientific="fail"):
    """Build a substantive complete declaration with every reference/artifact slot populated."""
    checks = []
    for name, dimension, basis, outcome in (
            ("interface", "operational_interface", "builder_self_test", "pass"),
            ("software", "software_behavior", "reported_tool_execution", "pass"),
            ("science", "scientific_applicability", "assessor_assertion", scientific),
            ("audit", "scientific_applicability", "independent_review", "inconclusive")):
        checks.append({"check_id": name, "dimension": dimension, "basis": basis,
                       "attribution": attribution(name + " checker"), "outcome": outcome,
                       "scope": known(["x ∈ [0,1], tolerance 10⁻⁶"]), "method": known("Compare frozen test cases."),
                       "expected": known("Bounded error ≤ 10⁻⁶"),
                       "observed": missing() if outcome == "unperformed" else known(PROSE),
                       "definition_records": known([record("definition", "check_definition", "source"),
                                                    record("definition_manifest", "check_definition", "work_product_manifest")]),
                       "definition_artifacts": known([artifact(name + "_definition")]),
                       "evidence": known([] if outcome == "unperformed" else [evidence(name + "_result", basis)]),
                       "independence": independence(), "limitations": missing()})
    permission = report("permission", "fail", "reported_permission_decision")
    del permission["outcome"]
    permission = {"status": "revoked", **permission}
    lifecycle = report("lifecycle", "fail", "reported_lifecycle_decision")
    del lifecycle["outcome"]
    # Repeated distant digest remains an occurrence for content accounting.
    lifecycle["evidence"]["value"][0]["artifacts"]["value"].append(artifact("environment"))
    lifecycle = {"status": "withdrawn", "reason_category": "scientific_defect", **lifecycle,
                 "replacement": known({"release": record("tool", "replacement_release", "tool_release", 3),
                                       "release_id": "sha256:" + "a" * 64}),
                 "supersedes": known([record("earlier_assessment", "supersedes_assessment", "tool_assessment")]),
                 "superseded_by": known(record("later_assessment", "superseded_by_assessment", "tool_assessment"))}
    return {
        "format": "research_pipeline.tool_assessment_content", "version": 1, "kind": "tool_assessment",
        "assessment_id": "assessment", "attribution": attribution(),
        "target": {"release": record("tool", "assessed_release", "tool_release"), "release_id": "sha256:" + "a" * 64},
        "environment": {"kind": "remote", "identity": known("Opaque synthetic service"),
                        "reported_version": missing(), "implementation_version": missing("unavailable", "Remote implementation cannot be inspected."),
                        "configuration": known([{"name": "precision", "value": ""}, {"name": "literal", "value": PROSE}]),
                        "observability": "opaque",
                        "records": known([record("environment", "assessed_environment", "source"),
                                          record("environment_manifest", "assessed_environment", "work_product_manifest"),
                                          record("environment", "assessed_environment", "source")]),
                        "artifacts": known([artifact("environment")]),
                        "dependencies": known([{"name": "quadrature", "reported_version": known("reported 1.2"),
                                                "records": known([record("dependency", "assessed_dependency", "source"),
                                                                  record("dep_manifest", "assessed_dependency", "work_product_manifest"),
                                                                  record("dep_tool", "assessed_dependency", "tool_release")]),
                                                "artifacts": known([artifact("dependency")]), "limitations": missing()}]),
                        "limitations": known(["Configuration pins do not freeze the remote running implementation."])},
        "scope": {"intended_uses": known([PROSE]), "tested_scope": known(["Synthetic finite cases only."])},
        "checks": known(checks),
        "reviews": known([{"review": record("review", "reported_review", "review"),
                           "attribution": attribution("Separate reviewer"), "outcome": "inconclusive",
                           "scope": known(["Scientific assumptions"]), "rationale": known("Shared formulation remains unresolved."),
                           "evidence": known([evidence("review_result", "independent_review")]),
                           "independence": independence(), "limitations": missing()}]),
        "limitations": known(["Synthetic supplied assessments cannot establish scientific truth."]),
        "issues": known([{"issue": record("issue", "reported_issue", "issue"), "attribution": attribution("Issue author"),
                          "category": "scientific_applicability", "summary": known("Uncontrolled approximation."),
                          "affected_scope": known(["Continuum extrapolation"]),
                          "evidence": known([evidence("issue_result")]), "limitations": missing()}]),
        "execution_permission": permission,
        "qualification": {name: report(name, scientific if name == "scientific_applicability" else "pass",
                                        "reported_qualification_decision") for name in DIMENSIONS},
        "lifecycle": lifecycle,
    }

def constructor_fields(value=None):
    """Convert complete wire reference shapes to exact typed pins for construction."""
    value = wire() if value is None else value

    def convert(item):
        """Recursively create independent constructor containers and typed references."""
        if type(item) is dict:
            if set(item) == {"record_id", "revision", "relationship", "target_kind"}:
                return RecordReference(**item)
            if set(item) == {"digest", "size"}:
                return ArtifactReference(**item)
            return {key: convert(child) for key, child in item.items()}
        if type(item) is list:
            return [convert(child) for child in item]
        return item
    return {key: convert(child) for key, child in value.items() if key not in ("format", "version", "kind")}

declaration = wire()
content = ToolAssessment(**constructor_fields(declaration))
assert content.to_dict() == declaration
assert content.assessment_id == "assessment"
assert content.to_dict()["target"]["release_id"] == "sha256:" + "a" * 64
assert content.to_dict()["execution_permission"]["status"] == "revoked"
assert content.to_dict()["qualification"]["operational_interface"]["outcome"] == "pass"
assert content.to_dict()["qualification"]["software_behavior"]["outcome"] == "pass"
assert content.to_dict()["qualification"]["scientific_applicability"]["outcome"] == "fail"
assert content.to_dict()["lifecycle"]["status"] == "withdrawn"
assert content.to_dict()["environment"]["implementation_version"]["state"] == "unavailable"
assert content.to_dict()["checks"]["value"][0]["evidence"]["value"][0]["basis"] == "builder_self_test"
assert content.to_dict()["reviews"]["value"][0]["evidence"]["value"][0]["basis"] == "independent_review"
creator = CreationProvenance("archivist", "2026-10-30T12:35:00Z", {"synthetic": True})
assert creator.actor != declaration["attribution"]["actor"]["value"]
envelope = encode_envelope("assessment", 1, content, creator)
assert envelope.operational_status is None
assert envelope.scientific_disposition is None
assert envelope.record_references[0] == RecordReference("tool", 2, "assessed_release", "tool_release")
assert envelope.record_references[-3] == RecordReference("tool", 3, "replacement_release", "tool_release")
assert envelope.record_references[-2] == RecordReference("earlier_assessment", 2, "supersedes_assessment", "tool_assessment")
assert envelope.artifact_references[0] == ArtifactReference(sha256(b"environment\n").hexdigest(), 12)
assert loads_content(dumps_content(content).encode("utf-8")) == content
assert decode_envelope(envelope) == content
contradictory = RecordEnvelope("assessment", 1, "tool_assessment", content.to_dict(), creator,
                               envelope.record_references[1:], envelope.artifact_references)
try:
    decode_envelope(contradictory)
except ToolAssessmentValidationError:
    pass
else:
    raise AssertionError("A contradictory generic projection was accepted")
print("Synthetic assessment round-tripped; contradictory projection refused; no tool executed.")
```
<!-- tool-assessment-example:end -->
