# Durable attributed reviews and issues

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

| Field | Required relationship / target_kind | Durable admission contract |
| --- | --- | --- |
| `Review.candidate_claim` | `candidate_claim / claim` | Constrained typed target |
| `Review.target_context` | `target_context / research_context` | Constrained typed target |
| `Review.context_manifest` | `context_manifest / work_product_manifest` | Generic target |
| `Review.authorization_policy` | `authorization_policy / decision` | Generic target |
| `Review.reported_checks` entry | `reported_evidence / evidence` or `reported_tool_execution / tool_execution` | Typed Evidence or generic ToolExecution, respectively |
| `SupportRouteAssessment.justification` | `assessed_route / justification` | Constrained typed target |
| `Issue.affected_records` entry | `affected_record / any supported domain kind` | Generic target, even for scientific, review or issue kinds |
| `Issue.supporting_evidence` entry | `supporting_evidence / evidence` | Constrained typed target |

Durable typed admission enforces this distinction; the pure API does not
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

## Durable API and exact traversal

Import `RecordStore` from `research_pipeline.store` and the shared `Submission`
from `research_pipeline.domain`. The existing durable methods support ten kinds:
ResearchContext, Claim, Justification, Evidence, Review, Issue,
[WorkProductManifest](work-products.md), [Source](sources.md), [CorpusManifest](corpus.md) and [ProjectSetup](project-intake.md).

- `submit_typed(submission: Submission) -> SubmissionReceipt`
- `get_typed_revision(record_id: str, revision: int) -> tuple[RecordEnvelope, ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest | ProjectSetup]`

Use the scientific encoder for scientific content and the assessment encoder for
Review/Issue, the work-product encoder for coherent manifests, the Source
encoder for source captures, the corpus encoder for inventories, and the project encoder for intake snapshots. Mixed typed batches permit arbitrary member order and forward
references, including Issue affected references to later Review/Issue members.
Every member must decode independently. Commit arbitrary generic manifests, policies,
ToolExecutions, tasks and other generic records separately with `submit`.
The store dispatches only on the explicit content format, without inference or
fallback to a different codec after failure. The four scientific codecs and wire
bytes remain unchanged. Pure conversion still performs no lookup.

For new requests the complete proposed batch takes precedence over committed
exact history. Required kinds and roles come
from the successfully decoded value, never from arbitrary generic field names.

The complete canonical [semantic traversal and ordered projection tables](project-intake.md#complete-semantic-traversal-and-ordered-projections)
cover all ten kinds, including every retained shallow role and target kind.


CorpusManifest additionally validates every exact original mapping and location
occurrence against its own entry selection, and every historical snapshot/diff
through revision 1. No generic corpus baseline transition is permitted. Entry IDs,
changes, relationship endpoints, strings, provenance details and exposure
declarations add no traversal edges. See [corpus projections and history](corpus.md).

Traversed targets require supported typed content and complete coherent ordered
links. Their constrained outgoing edges follow the same rules; their generic
outgoing edges receive only shallow existence/kind checks. Generic targets do not
have their payloads, outgoing links or attachments inspected. A generic occurrence
does not establish typed validity if the same target also occurs in a constrained
role. Review `context_manifest` remains shallow even when a manifest has a supported
codec: generic, unsupported or incoherent content still does not establish verified
exposure. Manifest supersession requires a coherent typed predecessor and follows
its constrained outgoing roles. Envelope-local identity/revision rules apply even
to historical targets. Every incoming constrained edge checks its required kind. A finite worklist
with separate decoded/processed caches terminates descriptive cycles without
imposing an accepted-deduction cycle policy.

[Source capture history](sources.md) additionally checks the immediately preceding
capture on new admission and historical constrained closure: an explicitly typed
Source predecessor must be coherent, have the same `work_id`, and be pinned by
supersedes. A legacy generic predecessor permits a first typed revision with null
supersedes without certification. Every incoming Source reading-report edge checks
`product_kind=reading_report`, including cached targets. These checks are metadata-only.
Adding Source does not strengthen manifest `linked_source`, Evidence `input_record`,
Issue `affected_record` or any other shallow role: generic, unsupported or incoherent
Source payloads and damaged transitive attachments remain eligible shallow targets
if exact existence/kind checks pass. All independently submitted typed members still
require coherent typed content. References authenticate neither actors nor exposure,
execution, approval or scientific support.

For every submitted Review, each assessed Justification's conclusions must contain
the candidate's exact `(record_id, revision)`. Relationship labels differ between
candidate and conclusion, so whole-reference equality is not used. This membership
rule applies to every outcome, including invalid, stale and inapplicable, and to
both proposed and historical routes. A matching later conclusion is sufficient
for structural membership; it establishes no scientific sufficiency. Reviews
without routes remain valid. Candidate context, route context and review target
context may all differ and may name older revisions after their heads advance.
Conditional favorable judgments retain their obligations. Invalid support does
not refute the candidate.

## Transactions, retries and failures

Both submission methods use one canonical request/fingerprint and one serialized
`BEGIN IMMEDIATE` commit algorithm. Local defensive request reconstruction and
codec checks precede original-ID reconciliation. An identical canonical request
returns the original receipt before checking current heads, targets, route
membership or artifact availability. This includes a locally valid request
originally committed through generic `submit`, even if new typed admission would
reject its route. The receipt acknowledges history; it is not retroactive typed
certification. Reordering mapping keys is immaterial; content, attribution,
expectations and meaningful collection ordering participate in equality.

For new requests the schema-kind gate precedes target inspection. Schema 1 rejects
Review/Issue with the existing migration-required error and never upgrades
implicitly. Expected-head CAS, stable kinds, exact references, direct artifact
verification/synchronization, constrained closure and route membership all precede
metadata insertion under the same write transaction. Revisions, ordered links,
heads, receipt and event commit atomically. Rejected batches leave all metadata
unchanged; previously published orphan bytes may remain.

| Failure | Error contract |
| --- | --- |
| Missing format discriminator on submitted content or an exact typed read | `NotTypedContentError`, a `DomainValidationError` subtype |
| Unknown/malformed format, unsupported version, malformed submitted content, kind/state/link mismatch | `DomainValidationError` |
| Missing/wrong-kind target, malformed historical constrained target, route not concluding the exact candidate | `ReferenceResolutionError` naming role and exact target; historical reconstruction/codec failure is chained |
| Different canonical request under a committed ID | `SubmissionConflictError` |
| Stale expected head, wrong next revision or changed stable kind | `RevisionConflictError` |
| Missing exact read / closed handle / unavailable direct artifact | Existing `RecordNotFoundError` / `StoreClosedError` / artifact error categories |

Historical constrained admission reconstructs metadata without checking transitive
artifact bytes. Structurally coherent historical Evidence can remain referencable
after its bytes disappear, while reading that Evidence itself still fails.
`get_typed_revision` first performs the snapshot-consistent generic exact read,
verifies direct attachments and returns detached envelope/content values. It
validates only that selected envelope; it neither traverses targets nor certifies
past route membership or admission. Generic reads preserve unsupported typed-looking
data without granting typed validity.

After interruption or lost acknowledgment, reopen and resubmit the original request
with its original ID. Exact retries remain available after later assessment revisions
or artifact damage. Healthy backups preserve generic, scientific and assessment
histories, ordered links, canonical requests, receipts and events using the unchanged
[backup formats](backups.md). Capture before byte damage. Exact restoration retains
retry semantics; explicit `restore_backup(..., target_schema=2,
migration_provenance=...)` is the existing v1-to-v2 migration boundary.

## Runnable synthetic persistence example

From the repository root, run this Python block with
`PYTHONPATH="$PWD/implementation/src" /home/francesco/miniconda3/bin/python3 -B`.
The integration test executes this actual block in a fresh interpreter. Runtime,
backup and restored paths are explicit and outside source. No scientific
calculation or provider call occurs.

```python
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.scientific import (
    ResearchContext, Claim, Justification, encode_envelope as scientific_envelope,
)
from research_pipeline.assessment import (
    IndependenceDeclaration, SubstantiveAssessment, SupportRouteAssessment, Review, Issue,
    encode_envelope as assessment_envelope,
)
from research_pipeline.store import RecordStore
from research_pipeline.backup import create_backup, inspect_backup, restore_backup

creator = CreationProvenance("synthetic-author", "2026-10-30T12:00:00Z")
second_creator = CreationProvenance("synthetic-reviewer-b", "2026-10-30T12:01:00Z")
controller = CreationProvenance("controller", "2026-10-30T12:02:00Z")

def reference(identity, role, kind):
    """Pin a synthetic first revision without looking up or rebinding a head."""
    return RecordReference(identity, 1, role, kind)

def batch(identity, members, expected=None):
    """Build an attributed request with explicit creation or append expectations."""
    return Submission(identity, controller, members,
                      {r.record_id: 0 for r in members} if expected is None else expected)

scope = ResearchContext("Synthetic scope α", [], [], [], [], [], [], [], [], [], [])
context = reference("scope", "context", "research_context")
candidate = Claim("Synthetic candidate", "declaration", [], context, [], [], ["Assess premises"])
route = Justification(context, [], [], "Declared route α",
                      [reference("candidate", "conclusion", "claim")], [], [])
independence = IndependenceDeclaration("answer_blind_reconstruction", "candidate_aware_audit",
                                      [], [], [], [], [], [], ["Exposure not verified"])
assessment = SubstantiveAssessment("under_review", "supported_within_scope", ["analytical"],
                                  "requires_reassessment", "unassessed", "Conditional synthetic report",
                                  ["If premises hold"], ["Existence obligation"], [])
routes = [SupportRouteAssessment(reference(name, "assessed_route", "justification"),
                                "sufficient", "Declared route judgment", ["Check premises"], [])
          for name in ("route-a", "route-b")]
first = Review(reference("candidate", "candidate_claim", "claim"),
               reference("scope", "target_context", "research_context"), "Reviewer α", independence,
               reference("manifest", "context_manifest", "work_product_manifest"),
               reference("policy", "authorization_policy", "decision"),
               [reference("execution", "reported_tool_execution", "tool_execution")],
               assessment, routes, ["Compare scopes"], [], [], "synthetic")
second = replace(first, reviewer="Reviewer β",
                 assessment=replace(assessment, scientific_disposition="disputed"),
                 route_assessments=[replace(r, outcome="invalid") for r in routes])
objection = Issue("Unverified premises", [reference("review-a", "affected_record", "review")],
                  "The conditions remain open", "blocking", "Compare assumptions", "open",
                  "Synthetic objection", [], [], [], "synthetic")

with TemporaryDirectory(prefix="assessment-example-", dir="/tmp") as temporary:
    runtime = Path(temporary) / "runtime"
    backup = Path(temporary) / "backup"
    restored_root = Path(temporary) / "restored"
    with RecordStore.create(runtime) as store:
        declarations = [RecordEnvelope(name, 1, kind, {"synthetic": True}, creator,
                                       operational_status="completed" if kind == "task_specification" else None)
                        for name, kind in (("manifest", "work_product_manifest"), ("policy", "decision"),
                                           ("execution", "tool_execution"), ("task", "task_specification"))]
        declared = batch("declarations", declarations)
        members = [assessment_envelope("review-a", 1, first, creator),
                   assessment_envelope("review-b", 1, second, second_creator)]
        members += [scientific_envelope(name, 1, value, creator) for name, value in (
            ("route-a", route), ("route-b", replace(route, method="Separate route β")),
            ("candidate", candidate), ("scope", scope))]
        initial = batch("initial", members)
        receipts = [store.submit(declared), store.submit_typed(initial)]
        original_claim = store.history("candidate")
        issue_record = assessment_envelope("issue", 1, objection, creator)
        issue_initial = batch("issue-created", [issue_record])
        receipts.append(store.submit_typed(issue_initial))
        issue_next = assessment_envelope("issue", 2, replace(objection, disposition="under_investigation"), creator)
        issue_revision = batch("issue-revised", [issue_next], {"issue": 1})
        receipts.append(store.submit_typed(issue_revision))
        retained = declarations + members + [issue_record, issue_next]
        events = store.audit_events()
        assert store.history("candidate") == original_claim
        assert original_claim[0].scientific_disposition == "provisional"
        assert store.history("issue") == (issue_record, issue_next)
        assert len(events) == 4
    with RecordStore.open(runtime) as reopened:
        assert reopened.get_typed_revision("review-a", 1)[1] == first
        assert reopened.get_typed_revision("review-b", 1)[1] == second
        assert reopened.history("candidate") == original_claim
        info = create_backup(reopened, backup)
        assert inspect_backup(backup) == info
    with restore_backup(backup, restored_root) as restored:
        for item in retained:
            assert restored.get_revision(item.record_id, item.revision) == item
        assert restored.get_typed_revision("issue", 2)[1].disposition == "under_investigation"
        assert restored.get_typed_revision("review-a", 1)[1].assessment.obligations == ("Existence obligation",)
        assert restored.get_typed_revision("review-b", 1)[1].route_assessments[0].outcome == "invalid"
        assert restored.history("candidate") == original_claim
        assert restored.audit_events() == events
        assert restored.submit(declared) == receipts[0]
        for submitted, receipt in zip((initial, issue_initial, issue_revision), receipts[1:]):
            assert restored.get_submission(submitted.submission_id) == receipt
            assert restored.submit_typed(submitted) == receipt
```

Reviewer/provenance attribution, requested/reported blind modes, empty sharing
declarations, ToolExecution references, completed tasks and policy references
certify neither independence, execution nor authority. Review dimensions and Issue
dispositions never update candidate history or create eligibility, permission,
endorsement or decision records; generic decision references are caller declarations.
Current eligibility/freshness, Apply disposition, scientific qualification and M0-S
remain future work. This infrastructure neither completes D02 nor authorizes a
scientific pilot or release. Local checks are advisory; the unchanged controller
validator remains `/home/francesco/miniconda3/bin/python3 -B implementation/scripts/validate.py`.
