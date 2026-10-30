# Typed provisional scientific content

`research_pipeline.scientific` supplies pure frozen values, strict version-1
codecs and exact `RecordEnvelope` conversion. Import directly from this submodule;
there are no package re-exports or CLI commands. Imports perform no filesystem,
storage or scientific work. The implementation uses only the standard library
and existing domain values.

The separate [attributed assessment contract](attributed-assessments.md) adds pure
Review/Issue values and exact envelopes with its own discriminator. Its reported
dimensions are content, separate from canonical state. Durable `submit_typed` and
`get_typed_revision` support all four scientific kinds and both assessment kinds,
with constrained traversal and exact review route-conclusion membership checks.

This contract establishes structural coherence, not scientific completeness,
truth, implication, sufficiency, execution, approval or support. The pure codecs perform no
target lookup or artifact availability check. `RecordStore.submit_typed` adds an
explicit structural admission boundary over durable storage; `submit` remains a
trusted generic persistence API, not a scientific admission gate. Generic
submission of a typed-looking envelope does not establish typed target validation.
Scientific wire version 1 and its four codecs remain unchanged. New metadata
stores use schema 2 and backup format 2; existing schema-1 stores and format-1
backups remain supported unchanged. Original generic history and the oscillator
fixture's v1.3 provenance are unchanged.

Evidence `input_records` may name any of the twenty generic kinds, including
new generic project, run or source records. Commit generic records separately
through `submit`; the six supported typed kinds may share a typed batch with
forward references. Input roles check exact existence and declared kinds without
extending constrained traversal. Generic project/run/source content cannot serve
as typed members or targets in context, premise, conclusion, evidence or
target-claim roles. Schema 1 still rejects new-kind declarations with
a migration-required error. Names and descriptive input content grant no authority.

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
unchanged `artifact_links` table have no relationship-label field. Named content
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

## Durable admission and exact reads

Import `RecordStore` from `research_pipeline.store`. Construct each member with
`encode_envelope(record_id, revision, content, provenance)` and construct the
existing `Submission(submission_id, provenance, records, expected_heads)` with
explicit controller attribution, ordered members and an expectation for each
identity (`0` for creation). The public methods are:

- `submit_typed(submission: Submission) -> SubmissionReceipt`
- `get_typed_revision(record_id: str, revision: int) -> tuple[RecordEnvelope, ScientificContent | AssessmentContent]`

A typed batch contains any of the four scientific kinds and the two
[assessment kinds](attributed-assessments.md), in any order. Commit generic tasks,
manifests, policies and executions separately through `submit`; evidence may name
them as exact inputs. All supplied members are defensively reconstructed and decoded,
including complete ordered content/link agreement. No links are repaired from
content. Local codec failures remain `DomainValidationError`; absent format
markers remain its `NotTypedContentError` subtype.

For a new request, `context`, `premise`, `conclusion`, `evidence` and `target_claim`
roles resolve first against the complete proposed batch and then against exact
committed revisions, never current target heads. Each target must have the
required kind and supported typed content with coherent stored links. The same
rule applies recursively to constrained roles reached through historical targets.
Review candidate/context/reported-Evidence/route and Issue supporting-Evidence
roles extend this same traversal. Review manifest/policy/reported-ToolExecution
and Issue affected-record roles remain shallow existence/kind checks; the
[complete role table](attributed-assessments.md#durable-api-and-exact-traversal)
specifies both contracts. Every assessed route must conclude its Review's exact
candidate, with no equality requirement among their separately pinned contexts.
A finite worklist caches exact identities/revisions, checking every incoming kind
and visiting before following outgoing edges; repeated roles and provisional
cycles terminate without imposing an acyclicity rule. No cross-record context
equality, assumption implication or scientific sufficiency is inferred.

Evidence `input_record` edges require existence and any explicitly declared kind,
but do not require typed content or extend this scientific traversal, even when
the declared kind is claim, context or evidence. An input also used in a
constrained role must meet that role's typed requirements. Missing or wrong-kind
targets raise `ReferenceResolutionError` naming the role and exact target.
Invalid/untyped historical target content raises the same error with the codec
failure chained. Submitted-member errors remain codec/domain errors.

Both submit methods use the same canonical request, SHA-256 fingerprint,
transaction, receipt/event sequence and fault boundaries. Inside `BEGIN IMMEDIATE`,
request equality is checked first: exact identity reuse returns the complete
original receipt; a different canonical request raises `SubmissionConflictError`.
Only uncommitted requests undergo head/revision/stable-kind checks, exact target
inspection and direct-artifact verification/synchronization. All checks precede
metadata insertion. Heads, revisions, ordered links, submission and event commit
atomically; every revision is inserted before links so forward references work.
Stale expectations retain `RevisionConflictError`; artifact and database errors
retain the generic store contract. A rejected request leaves all committed rows
unchanged (already published orphan bytes may remain).

Target inspection and CAS share the serialized write transaction. Supported APIs
append revisions/links without rewriting history; independent handles may advance
heads but cannot mutate exact historical targets. No sampled head or
out-of-transaction admission cache is trusted. The runtime owner must still
prevent external database/file mutation. A new claim may deliberately retain an
older context revision after its head advances.

Historical target admission reconstructs normalized metadata and links without
reading object bytes. It promises structural coherence, not transitive artifact
availability. New batch attachments undergo full existing commit verification.
`get_typed_revision` reuses the snapshot-consistent generic exact read, verifies
its direct attachments, and decodes the detached envelope. It returns both the
original identity/provenance/state/links and the scientific or assessment value.
Missing exact revisions retain `RecordNotFoundError`, direct-artifact errors propagate, and
closed handles retain `StoreClosedError`. A typed read checks the selected
revision's content and links; it does not certify historical typed admission or
perform scientific assessment. Generic reads continue exposing original generic,
unsupported and incoherent scientific documents without rewriting them.

Exact retry remains a historical acknowledgment after heads advance or bytes
become missing/corrupt. It requires fresh local request decoding but reaches no
target, head or artifact validation. This includes an identical request originally
written through trusted generic `submit`; the receipt is not a retroactive typed
admission certificate. Mapping-key order is immaterial; ordered content,
attribution and expectations participate in equality. After uncertain COMMIT or
lost acknowledgment, reopen and resubmit the original request with its original
ID. `get_submission` retrieves metadata but alone cannot establish request equality.
Never substitute a new ID to resolve uncertainty.

Existing backups preserve typed and generic history, canonical requests, ordered
links, receipts and events without interpreting scientific or assessment versions.
Unsupported typed versions remain valid generic backup data and fail typed reads. Capture
a healthy backup before artifact damage: capture/inspection verifies all historical
objects. Restored stores retain exact-retry reconciliation even if bytes later fail.

## Runnable synthetic persistence example

From the repository root, run the following Python block with
`PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B`.
It creates an explicit disposable runtime under `/tmp`, performs only synthetic
persistence, and is executed verbatim by the integration tests.

```python
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.scientific import (
    ResearchContext, Claim, Justification, Evidence, encode_envelope,
)
from research_pipeline.store import RecordStore

creator = CreationProvenance("synthetic-author", "2026-10-30T12:00:00Z")
controller = CreationProvenance("controller", "2026-10-30T12:01:00Z")
scope = ResearchContext("Does f(x) = x?", ["f(x) = x"], [], [], [],
                        ["x ∈ ℝ"], [], [], [], [], [])
context_ref = RecordReference("scope", 1, "context", "research_context")
claim = Claim("f(x) = x", "synthetic declaration", ["∀ x ∈ ℝ"],
              context_ref, [], [], ["No scientific assessment"])
conclusion = RecordReference("claim", 1, "conclusion", "claim")
route = Justification(context_ref, [], [], "declared route", [conclusion], [], [])
alternative = replace(route, method="independent alternative route")

with TemporaryDirectory(prefix="typed-example-", dir="/tmp") as temporary:
    root = Path(temporary) / "runtime"
    with RecordStore.create(root) as store:
        artifact = store.put_artifact(b"synthetic declared observation")
        evidence = Evidence([artifact], context_ref, "identity property", [],
                            "synthetic method", [], [], [], "declared result", [], [], "synthetic")
        members = [encode_envelope(name, 1, value, creator) for name, value in (
            ("route", route), ("alternative", alternative), ("claim", claim),
            ("evidence", evidence), ("scope", scope))]  # Forward context references.
        initial = Submission("initial", controller, members, {m.record_id: 0 for m in members})
        receipt = store.submit_typed(initial)
        changed = replace(scope, parameter_regime=("ε > 0",), limit_ordering=("ε → 0",))
        appended = [encode_envelope("scope", 2, changed, creator),
                    encode_envelope("claim", 2, replace(claim, statement="Retain original scope"), creator)]
        store.submit_typed(Submission("append", controller, appended, {"scope": 1, "claim": 1}))
    with RecordStore.open(root) as store:
        old_envelope, old_scope = store.get_typed_revision("scope", 1)
        assert old_scope == scope and old_envelope.provenance == creator
        assert store.get_typed_revision("scope", 2)[1] == changed
        assert store.get_typed_revision("claim", 2)[1].context.revision == 1
        assert store.get_typed_revision("claim", 1)[0].scientific_disposition == "provisional"
        assert store.submit_typed(initial) == receipt
```

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

Verification of assessment sufficiency, promotion/eligibility, Apply disposition,
authentic tool receipts, remaining typed §5.1 payloads and scientific validation
remain later work. This contract does not
complete D02 or authorize a scientific pilot or release.

The unchanged controller check is
`/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py`.
The verification handoff requires preservation of all 169 baseline
executions/assertions at the exact frozen request base, plus controller-owned
evidence of all existing and substantive new tests passing with zero skips.
Local test output is advisory; this document
claims neither those baseline results nor controller acceptance.
