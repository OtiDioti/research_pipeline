# Typed provisional scientific content

`research_pipeline.scientific` supplies pure frozen values, strict version-1
codecs and exact `RecordEnvelope` conversion. Import directly from this submodule;
there are no package re-exports or CLI commands. Imports perform no filesystem,
storage or scientific work. The implementation uses only the standard library
and existing domain values.

This contract establishes structural coherence, not scientific completeness,
truth, implication, sufficiency, execution, approval or support. It performs no
target lookup or artifact availability check. **The typed durable submit/read API
is not yet implemented.** `RecordStore` remains a trusted generic persistence API,
not a scientific admission gate. Do not treat generic submission of one of these
envelopes as typed target validation. SQLite and backup formats remain version 1;
original generic history and the oscillator fixture's v1.3 provenance are unchanged.

## Constructors and exact wire fields

All constructor arguments below are required, including explicitly empty
collections. The signatures list arguments in positional order; keyword arguments
are also supported. No constructor accepts format, version, kind or state switches.

| Constructor | Required arguments |
| --- | --- |
| `NamedAssumption` | `label, statement` |
| `ResearchContext` | `question, equations, definitions, units, conventions, mathematical_domains, boundary_conditions, initial_conditions, parameter_regime, approximations, limit_ordering` |
| `Claim` | `statement, category, quantifiers, context, assumptions, approximation_qualifications, open_obligations` |
| `Justification` | `context, premises, required_assumptions, method, conclusions, evidence, limitations` |
| `Evidence` | `artifacts, context, target_property, target_claims, method, input_records, input_artifacts, tested_scope, result, uncertainty_details, failure_details, origin` |

Every scientific content dictionary contains exactly its constructor fields plus
`format="research_pipeline.scientific_content"`, `version=1`, and `kind` equal to
`research_context`, `claim`, `justification` or `evidence`, respectively. Fields
are flat, with no payload wrapper. Version is an ordinary integer, excluding
booleans, floats and numeric strings. Every serialized field is required, even
empty arrays and nullable reference target kinds. Extra fields fail at every level.

Field types and constraints are:

- `ResearchContext.question` is nonblank text. Its other fields are ordered text
  collections. Boundary and initial conditions are separate explicit declarations.
- `Claim.statement` and `category` are nonblank text. Category is descriptive,
  without a taxonomy. `quantifiers`, `approximation_qualifications` and
  `open_obligations` are ordered text collections. `context` is one
  `RecordReference`; `assumptions` is an ordered `NamedAssumption` collection.
- `Justification.context` is one `RecordReference`. `premises`, `conclusions` and
  `evidence` are ordered reference collections. `conclusions` must be nonempty.
  `required_assumptions` contains `NamedAssumption` values; `method` is nonblank
  text and `limitations` is an ordered text collection.
- `Evidence.artifacts` is a nonempty ordered `ArtifactReference` collection.
  `context` is one `RecordReference`. `target_property`, `method` and `result` are
  nonblank text. `target_claims` and `input_records` are ordered record-reference
  collections; `input_artifacts` is an ordered artifact-reference collection.
  `tested_scope`, `uncertainty_details` and `failure_details` are ordered text
  collections. `origin` is exactly `synthetic` or `unverified`.
- `NamedAssumption` serializes exactly `label` and `statement`. Labels follow
  `[A-Za-z0-9][A-Za-z0-9_-]{0,127}` and are case sensitive and unique within the
  containing assumptions collection. Statements are nonblank text. Labels are
  scoped by the containing exact record revision; they create neither global
  identities nor reference resolution.
- `RecordReference` serializes exactly `record_id, revision, relationship,
  target_kind`, with `target_kind` present even when null. IDs and relationship
  labels follow the same opaque identifier rule; revisions are ordinary integers
  from 1 through `2**63 - 1`.
- `ArtifactReference` serializes exactly `digest, size`: 64 lowercase SHA-256 hex
  digits and an ordinary integer byte count from 0 through `2**63 - 1`.

All collections without a stated nonempty requirement may be empty. Empty
uncertainty or failure details do not establish absence of uncertainty or failure.
Empty premises describe a provisional route with no recorded premises; they do
not imply an axiom or proof. Every listed premise is jointly required.
Alternatives are separate justification values/records, never an OR flag.

Every supplied statement must be an ordinary string containing Unicode scalar
values and must not be blank. Whitespace is tested, never stripped from storage.
Meaningful whitespace, line breaks, non-ASCII/supplementary notation, literal
escape text, ordered statements and repeated text are preserved. No mathematical
parsing, normalization or completeness inference occurs.

Constructors accept only ordinary lists or tuples for collections and snapshot
them as tuples. Strings, mappings, sets, generators and invalid members fail.
Nested references and assumptions are immutable. All `to_dict()` calls return
fresh dictionaries and lists; mutation of caller collections, input dictionaries
or returned trees cannot change the values. Wire arrays must be ordinary JSON
lists; tuples are not accepted by `from_dict()`.

## Exact roles and envelope projection

| Content field | Literal relationship | Required target kind |
| --- | --- | --- |
| All `context` fields | `context` | `research_context` |
| Justification `premises` | `premise` | `claim` |
| Justification `conclusions` | `conclusion` | `claim` |
| Justification `evidence` | `evidence` | `evidence` |
| Evidence `target_claims` | `target_claim` | `claim` |
| Evidence `input_records` | `input_record` | Explicit null or any supported envelope kind |

Constrained kinds cannot be omitted or null. Supplied references are checked,
never relabeled. Within each record-reference collection, repeated
`(record_id, revision)` targets fail, including differently constrained references
to the same target. Distinct revisions are distinct references. The same exact
target can appear in different roles, including premise and conclusion. Cycles
and self-references remain provisional and structurally valid; there is no
acyclicity or support assessment. Evidence inputs may describe arbitrary exact
structural inputs, including evidence itself, without endorsing their contents.

`record_references` projects in this exact order:

| Content | Ordered envelope references |
| --- | --- |
| ResearchContext | Empty |
| Claim | `context` |
| Justification | `context`, all `premises`, all `conclusions`, all `evidence` |
| Evidence | `context`, all `target_claims`, all `input_records` |

Order within each collection is retained. Contexts, claims and justifications
have no direct artifact references. Evidence's `artifact_references` is all
`artifacts` followed by all `input_artifacts`. `ArtifactReference` and the existing
version-1 `artifact_links` table have no relationship-label field. Named content
roles and this fixed positional projection encode role identity: the length of
`artifacts` defines the boundary. No schema or reference change is needed.
Repeated digests within either role fail, even when sizes differ. A digest may
occur in both roles with the same size and must appear twice in the projection;
conflicting sizes across the roles fail. There is no global deduplication.

## Codecs and strict failures

Every value has `to_dict() -> dict` and strict `from_dict(value)` methods.
Content codecs and envelope conversion are:

| Operation | Result |
| --- | --- |
| `decode_content(value: dict)` | One of the four scientific content values, based on an explicit supported discriminator/version/kind. |
| `dumps_content(value) -> str` | Canonical JSON for one typed content value. |
| `loads_content(data: str \| bytes)` | Strict JSON decoding followed by typed validation. Bytes must be strict UTF-8. |
| `encode_envelope(record_id, revision, content, provenance) -> RecordEnvelope` | Explicit identity/revision/`CreationProvenance`, derived kind and exact links. Claims are provisional; other scientific dispositions and all operational states are null. |
| `decode_envelope(envelope: RecordEnvelope)` | Detached typed content after generic envelope reconstruction and complete kind/link coherence checks. Identity, revision, provenance and state remain on the supplied envelope. |

`decode_envelope` rejects missing, extra, substituted, duplicated, relabeled,
differently constrained or reordered links, including any unexpected links on
contexts. It never repairs disagreement or discards supplied links. It does not
resolve exact targets, check artifact bytes or inspect scientific relationships.

Canonical output uses sorted object keys, compact separators, ASCII escaping,
preserved array order and finite numbers only. Strict loading rejects malformed
JSON, trailing data, duplicate keys at every depth, NaN/Infinity, invalid UTF-8,
alternative byte encodings, invalid roots and non-scalar Unicode. Valid JSON
escaped surrogate pairs decode to supplementary scalars; unpaired escapes and
actual Python surrogate code points fail. Direct dictionary decoding also rejects
unsupported Python values, cycles and depth/recursion failures. Syntax, encoding,
field and depth failures become useful `DomainValidationError` diagnostics with
underlying causes retained where applicable.

`NotTypedContentError` subclasses `DomainValidationError` and distinguishes
content lacking a format discriminator. A present but unknown/malformed format,
unsupported version or invalid typed structure raises `DomainValidationError` for
that specific failure. Familiar fields or an envelope kind do not imply typed
status. A marker alone does not establish successful validation.

Generic `RecordEnvelope` APIs retain their arbitrary strict JSON contract. They
continue to round-trip legacy documents, unknown formats and unsupported typed
versions as generic content. Generic duplicate-link behavior is unchanged.
Typed restrictions apply only at explicit typed boundaries; no history is
rewritten or silently reinterpreted. Descriptive execution/approval/support text
cannot change canonical provisional claims or grant an authentic evidence origin.
Completed tasks retain their separate generic operational state.

## Runnable synthetic codec example

Run from the repository root; this example performs no storage or execution:

```bash
PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B - <<'PY'
from research_pipeline.domain import CreationProvenance, RecordReference
from research_pipeline.scientific import (
    ResearchContext, Claim, NamedAssumption,
    dumps_content, loads_content, encode_envelope, decode_envelope,
)

context = ResearchContext(
    question="For which declared x does f(x) = x hold?",
    equations=["f(x) = x"], definitions=["f is the declared identity map"],
    units=[], conventions=[], mathematical_domains=["x ∈ ℝ"],
    boundary_conditions=[], initial_conditions=[], parameter_regime=[],
    approximations=[], limit_ordering=[],
)
creator = CreationProvenance("synthetic-author", "2026-10-30T12:00:00Z")
context_record = encode_envelope("scope", 1, context, creator)
claim = Claim(
    statement="∀ x ∈ ℝ, f(x) = x", category="synthetic declaration",
    quantifiers=["∀ x ∈ ℝ"],
    context=RecordReference("scope", 1, "context", "research_context"),
    assumptions=[NamedAssumption("A", "Use the declared identity map")],
    approximation_qualifications=[], open_obligations=["No scientific assessment recorded"],
)
record = encode_envelope("claim", 1, claim, creator)
assert loads_content(dumps_content(context)) == decode_envelope(context_record)
assert loads_content(dumps_content(claim)) == decode_envelope(record)
assert record.record_references == (claim.context,)
assert record.scientific_disposition == "provisional"
PY
```

Durable typed admission/read, target resolution, transactional integration,
retry/restart and typed backup evidence remain the next milestone. Assessment
sufficiency, promotion/eligibility, authentic tool receipts, all specification
§5.1 kinds and scientific validation remain later work. This contract does not
complete D02 or authorize a scientific pilot or release.

The unchanged controller check is
`/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py`.
The verification handoff still requires controller-owned evidence of 88 passing
baseline tests at the exact frozen request base, plus all existing and substantive
new tests passing with zero skips. Local test output is advisory; this document
claims neither those baseline results nor controller acceptance.
