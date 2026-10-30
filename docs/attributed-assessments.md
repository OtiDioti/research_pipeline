# Attributed review and issue contracts

`research_pipeline.assessment` supplies pure frozen values, strict version-1
codecs and exact envelope conversion. Import directly from this submodule; the
package initializer and CLI remain unchanged. Imports perform no storage,
filesystem or scientific work and use only the standard library.

These values preserve attributed assertions and disagreements. Requested versus
reported independence, reported checks, reviewer text, policy references, origin
and caller provenance establish neither isolation, authentic execution, authority,
approval nor scientific truth. Empty sharing declarations establish neither an
absence of sharing nor independence. Shared declarations are narrative text,
not record locators. `reviewer` is descriptive nonblank text, not an authenticated
actor or opaque identifier. Issue attribution comes from mandatory envelope
`CreationProvenance`; there is no second identity or authentication system.

Pure conversion follows no edges: it never looks up route conclusions, compares
contexts, interprets manifest/policy/tool payloads, traverses affected records or
verifies artifact bytes. Exact identifiers and revisions remain pinned; nothing
rebinds to a current head. A review may use a different target context or assess
no routes. The values can be converted without any store or target existing.

## Required constructors and wire fields

All arguments are required in the positional order below; keyword arguments are
also supported. No defaults, extension dictionaries or state switches are accepted.

| Constructor | Required arguments |
| --- | --- |
| `IndependenceDeclaration` | `requested_mode, reported_mode, shared_formulation, shared_sources, shared_lemmas, shared_method, shared_implementation, shared_communications, limitations` |
| `SubstantiveAssessment` | `work_stage, scientific_disposition, support_types, applicability, novelty, rationale, conditions, obligations, limitations` |
| `SupportRouteAssessment` | `justification, outcome, rationale, outstanding_conditions, limitations` |
| `Review` | `candidate_claim, target_context, reviewer, independence, context_manifest, authorization_policy, reported_checks, assessment, route_assessments, open_obligations, limitations, artifacts, origin` |
| `Issue` | `disputed_point, affected_records, objection_or_counterexample, severity, proposed_discriminating_action, disposition, rationale, limitations, supporting_evidence, artifacts, origin` |

Every class has `to_dict()` and `from_dict(value: dict)`. Review and Issue
wire documents contain exactly their constructor fields plus
`format="research_pipeline.assessment_content"`, `version=1`, and respectively
`kind="review"` or `kind="issue"`. Nested value objects contain exactly their
constructor fields, without headers. All fields and arrays are mandatory at every
level. `AssessmentContent = Review | Issue` is the public content union.

`Review.independence` and `assessment` require the corresponding exact classes;
`route_assessments` contains exact `SupportRouteAssessment` values. All shared
fields, conditions, obligations, outstanding conditions, open obligations and
limitations are ordered collections of nonblank descriptive strings. Rationale,
reviewer, disputed point, objection/counterexample and proposed discriminating
action are nonblank text. Nonblank validation does not trim or normalize text.

Every collection is explicit and may be empty except `Issue.affected_records`,
which must be nonempty. Constructor collections accept only ordinary lists or
tuples and become tuples. Wire arrays must be ordinary lists. Descriptive repeats
are retained. Nested values and domain references are reconstructed, not merely
trusted because a dataclass is frozen. Parents retain no mutable input containers.
Every returned dictionary and decoded or envelope-derived value is detached.
Subclasses and duck-typed replacements do not satisfy exact-class requirements.

## Independent codes

Codes are ordinary strings, without enum coercion, ranking or inferred combinations.

| Field | Exact supported codes |
| --- | --- |
| `requested_mode`, `reported_mode` | `answer_blind_reconstruction`, `proof_blind_reconstruction`, `candidate_aware_audit` |
| `work_stage` | `exploring`, `frozen_candidate`, `under_review`, `archived` |
| `scientific_disposition` | `provisional`, `supported_within_scope`, `disputed`, `support_withdrawn`, `refuted_within_scope`, `superseded` |
| `support_types` | Ordered unique collection of `heuristic`, `analytical`, `symbolic`, `numerical`, `formal`, `source_based` |
| `applicability` | `applicable`, `requires_reassessment`, `inapplicable`, `unresolved` |
| `novelty` | `unassessed`, `known_equivalent_identified`, `search_found_no_equivalent`, `researcher_assessed_contribution` |
| Route `outcome` | `sufficient`, `invalid`, `stale`, `inapplicable`, `incomplete`, `unresolved` |
| Issue `severity` | `informational`, `nonblocking`, `blocking` |
| Issue `disposition` | `open`, `under_investigation`, `resolved`, `dismissed` |
| Review/Issue `origin` | `synthetic`, `unverified` |

Requested and reported modes may differ without declaring compliance. Each
substantive dimension varies independently. Favorable dispositions and sufficient
routes may retain obligations and conditions. Invalid support does not imply a
refuted claim. Different reviews may disagree about the same exact route. Each
route judgment pins a Justification without copying or flattening its conjunction
of premises; alternative routes remain separate entries.

## Exact references and projection

Every assessment record reference requires all four wire keys: `record_id`,
`revision`, `relationship`, `target_kind`. The kind must be non-null and supported
by the domain. Identifiers, exact positive revisions and signed-64-bit integer
limits follow the [domain contract](durable-records.md); booleans, numeric strings
and floats are not integers. Supplied roles are checked, never relabeled.

| Field | Required relationship / target_kind | Admission contract for the next milestone |
| --- | --- | --- |
| `Review.candidate_claim` | `candidate_claim / claim` | Constrained typed target |
| `Review.target_context` | `target_context / research_context` | Constrained typed target |
| `Review.context_manifest` | `context_manifest / work_product_manifest` | Generic target |
| `Review.authorization_policy` | `authorization_policy / decision` | Generic target |
| `Review.reported_checks` entry | `reported_evidence / evidence` or `reported_tool_execution / tool_execution` | Typed Evidence or generic ToolExecution, respectively |
| `SupportRouteAssessment.justification` | `assessed_route / justification` | Constrained typed target |
| `Issue.affected_records` entry | `affected_record / any supported domain kind` | Generic target, even for scientific, review or issue kinds |
| `Issue.supporting_evidence` entry | `supporting_evidence / evidence` | Constrained typed target |

This distinction specifies future admission requirements; the pure API does not
resolve even constrained targets. Generic manifest, policy, execution and affected
references preserve declarations without treating payloads as approved contracts.
Reported checks retain mixed Evidence/ToolExecution order and do not certify execution.

Duplicate `(record_id, revision)` targets are rejected separately within
`reported_checks`, `affected_records`, `supporting_evidence` and route assessments
(using each route's justification). Changing a check role/kind or a route judgment
does not evade uniqueness. Different revisions are distinct. Valid occurrences
across semantic fields remain separate, including affected records also used as
supporting evidence. No cross-role deduplication occurs.

Artifacts are explicit ordered exact `ArtifactReference(digest, size)` objects:
64 lowercase SHA-256 hexadecimal characters and an ordinary nonnegative integer
byte count within domain limits. Duplicate digests within a record fail even if
sizes differ. Paths and locator strings cannot serve as artifact evidence.

The complete ordered envelope projection is:

| Content | `record_references` | `artifact_references` |
| --- | --- | --- |
| Review | `candidate_claim`, `target_context`, `context_manifest`, `authorization_policy`, all `reported_checks`, then each route's `justification` | All `artifacts` |
| Issue | All `affected_records`, then all `supporting_evidence` | All `artifacts` |

Each collection retains its declared order. Envelope decoding compares the
complete ordered tuples; missing, added,
substituted, repeated, relabeled or reordered links fail without repair.

## Pure APIs and strict errors

| Function | Contract |
| --- | --- |
| `decode_content(value: dict) -> AssessmentContent` | Decode the explicit assessment discriminator, supported version and kind. |
| `dumps_content(value: AssessmentContent) -> str` | Revalidate the complete value and emit canonical compact sorted-key ASCII JSON, retaining array order. |
| `loads_content(data: str \| bytes) -> AssessmentContent` | Parse strict JSON; bytes must be UTF-8. |
| `encode_envelope(record_id: str, revision: int, content: AssessmentContent, provenance: CreationProvenance) -> RecordEnvelope` | Revalidate content and attribution and construct exact projected links, matching kind and null canonical states. |
| `decode_envelope(envelope: RecordEnvelope) -> AssessmentContent` | Defensively reconstruct envelope and content, requiring exact kind, state and ordered-link coherence. |

Malformed values raise `DomainValidationError` with useful containing fields or
indexes; expected parsing, encoding, serialization and recursion failures retain
causes. A missing format discriminator raises the existing
`research_pipeline.scientific.NotTypedContentError` subtype. A present unsupported
format, invalid kind or malformed/unsupported version raises `DomainValidationError`
without that missing-discriminator subtype. Scientific and assessment codecs
reject each other's documents. Familiar field names and envelope kinds never
trigger inference. Generic envelope round trips can preserve unsupported
assessment-looking JSON without granting typed validity.

Only ordinary JSON dictionaries, lists, scalar strings, finite numbers, booleans
and null can appear in input trees, further restricted by each field's contract.
Extra/missing keys, duplicate JSON keys at any depth, trailing data, invalid roots,
nonfinite values (including overflow to infinity), invalid UTF-8, alternative byte
encodings, cycles, excessive nesting and unsupported Python values fail. Scalar
Unicode, supplementary characters, line breaks and literal escape text survive.
Escaped valid surrogate pairs may decode to a supplementary scalar; lone surrogate
escapes and actual Python surrogate code points fail. No coercion is performed.

Both envelope kinds require `operational_status=None` and
`scientific_disposition=None`. A reported `supported_within_scope` assessment is
content only: it changes no Claim, canonical disposition, eligibility, permission
or decision. `CreationProvenance` is copied caller attribution, not authentication.

## Current durable boundary

The [scientific contract](typed-content.md) and its four wire representations
remain unchanged. `RecordStore.submit_typed` and `get_typed_revision` currently
support only ResearchContext, Claim, Justification and Evidence. Review/Issue
pure conversion is available; durable typed admission, constrained traversal,
route-conclusion membership checks, recovery coverage and a persistence example
belong to the next milestone. Schema, backup formats and generic storage remain
unchanged. Current eligibility/freshness, Apply disposition and scientific
qualification remain future work. These contracts do not complete D02 or authorize
a scientific pilot or release.
