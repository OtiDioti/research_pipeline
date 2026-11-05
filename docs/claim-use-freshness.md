# Transactional claim-use freshness

`research_pipeline.claim_use` defines passive exact bindings. Register them with
`RecordStore.submit_typed(Submission(...))`, using `encode_envelope`; the result is
an unchanged `SubmissionReceipt`. Generic `submit` recognizes the same explicit
content and enforces the same registration and freshness rules. Policy-head freshness requires opt-in schema 5; schema 4 retains its original
Review/Issue semantics. Neither path produces positive scientific eligibility, promotion or authorized disposition.

## Values and wire contract

All constructor fields are required:

- `ClaimUsePremise(claim, upstream_use)` pins a `premise/claim` and either an
  explicit `premise_use/promotion_eligibility` binding or `None` (unrecorded support).
- `ClaimUseRoute(justification, premises, assessments)` pins a
  `support_route/justification`, its complete ordered conjunctive premises, and at
  least one `support_assessment/review`. Each route is a separate alternative.
- `ClaimUse(candidate_claim, target_context, routes, issues, policies, limitations)`
  requires `candidate_claim/claim`, `target_context/research_context`, zero or more
  routes and `relevant_issue/issue` pins, at least one
  `authorization_policy/decision`, and explicit narrative limitations.

Collections accept ordinary lists/tuples and detach into tuples. `to_dict` and
`from_dict` use required JSON arrays, including empty arrays; `upstream_use` is
explicitly null when omitted support is declared. Exact duplicate routes and
repeated targets within assessment, issue and policy collections are rejected.
`decode_content`, `dumps_content`, `loads_content`, `encode_envelope` and
`decode_envelope` follow the assessment codecs. Content has exactly
`format="research_pipeline.claim_use_content"`, ordinary integer `version=1`,
`kind="claim_use"`, and the six ClaimUse fields. Extra fields (including eligibility,
generation, approval and disposition), duplicate JSON keys, nonfinite numbers,
unsupported types, invalid Unicode, cycles and excessive JSON nesting fail.
A missing discriminator raises `NotTypedContentError`; malformed explicit content
raises `DomainValidationError`.

The envelope kind is `promotion_eligibility`, with null canonical state fields and
no artifacts. This existing kind name grants no promotion. Projection order is
candidate, target context; each route's justification, each premise claim followed
by its non-null upstream use, then its assessment pins; finally issues and policies.
Decode compares the entire ordered projection and never repairs it.

The envelope record ID is the stable use identity; its revision is the binding
revision. First registration must create revision 1. Rebinding appends with normal
expected-head CAS to an already registered identity. Generic historical identities
cannot be converted; registered identities cannot become opaque content. Historical
binding envelopes and original receipts never acquire mutable generation fields.

## Exact support and trust

Required candidate/context/route/premise/evidence/assessment/issue roles resolve to
coherent supported typed records. Every route must conclude the exact candidate;
its premise entries must equal the complete ordered Justification conjunction.
Every bound Review must match the exact candidate, target context, route and a
bound exact policy. Any reported outcome is allowed and remains attributed.
Policies stay shallow declared decision references. Existing shallow Issue
`affected_records`, Review `context_manifest`, ToolExecution and Evidence input
roles do not become authenticated or recursively typed authority.

Only a non-null explicit upstream-use binding extends support ancestry. Its
candidate must equal the exact premise. Direct self-support, explicit use cycles
and ancestry returning to its own candidate as an undischarged premise fail.
Descriptive back-references, Evidence inputs, other Justifications and prose never
discharge premises. Issue association cycles are impact-navigation links, bounded
with visited sets; they are not deductive support.

Different candidate, route, premise or upstream contexts remain historical pins
and are reported as unresolved context transfer. Bound Reviews still need the
use's exact target context. Registration verifies direct artifacts of required
inspected typed closure under independent limits. Later propagation and current
inspection use metadata and do not require old attachment availability. Exact
historical reads retain direct-artifact verification.

## Transactions, generations and relevance

Schema-4 binding registration initializes generation 1, or increments the stable
identity's generation for a revised binding. Status is always
`requires_reassessment`; the public view derives `eligible=false`. Every newly
accepted relevant Review/Issue revision is potentially material, including prose,
conditions, limitations, withdrawal, changed targets, resolution and reopening.
One submission coalesces all distinct causes into at most one transition per use.
An already stale use still increments for a new relevant assertion transaction.
Signed-64-bit generation overflow rejects the entire write.

Exact dependency indexes retain context-scoped candidate/route anchors, complete
premises/evidence, selected assertions and their declared references. Premises
retain both their Claim context and a different use context. Review impact uses
exact candidate/context and assessed-route/context pairs. Issue impact follows
exact affected records; an affected Review/Issue is inspected for association.
An exact explicitly registered binding is itself an Issue-impact anchor:
an Issue affecting `U@1/promotion_eligibility` marks U@1 and propagates through
recorded downstream uses even when U@1 has no routes or incoming references.
A generic `promotion_eligibility` record without registration does not become a
use. Other target kinds remain shallow anchors. A changed assertion identity includes
its historical targets as well as new targets, so removing links cannot erase
relevance. Pinned Review/Issue identities have watches even if a successor changes
scope. This history union invalidates conservatively; it never replaces a pin or
certifies support. An independent Review in another context does not affect an
old-scope use merely by naming the same claim. Under the historical schema-4
contract, policy-head advancement alone does not increment generations. Unrelated
contexts and unrelated global events do not increment generations on either schema.

Reverse explicit upstream edges propagate affected binding nodes to completion.
Historical binding nodes remain traversable: D pinning U@1 still receives relevant
changes to U@1 after U@2 becomes current. Rebinding U alone neither repoints D nor
invalidates it. Only current binding nodes receive current-use transitions.
An Issue targeting U@1 after U@2 is registered still reaches D pinned to U@1,
but does not advance U@2 solely from that old target. Current U@2 inspection does
not observe that Issue unless its own recorded dependencies establish relevance.
Causes include `binding_registered` for registration, `binding_affected` with the
changed assertion's exact pin and the directly affected binding's exact pin,
`assertion_changed` with matched dependency details, and `upstream_affected` with
the immediate upstream binding. Direct and dependency reasons coexist and are
coalesced canonically within one transition, without enumerating every full path.
A forward same-batch Issue targeting a new use appears in its prospective and
persisted inspection; applicable assertion and registration reasons share generation 1.

Planning, ordinary typed admission, record/head/link/receipt/event insertion and
freshness application occur under the same owning `BEGIN IMMEDIATE` transaction.
The shared insertion seam covers report, control, source and operating writers.
It indexes every schema-4/5 revision/event and selected original association-link
occurrence after the actual receipt exists, even when no freshness plan is needed.
These navigation projections share the owning transaction and exact-retry behavior.
No worker, post-commit scan or second commit exists. Any planning/application
failure rolls everything back. Readers own one read transaction and see a coherent
old or new state. A successful commit exits rollback handling before the lost
acknowledgment seam. Retry the original submission ID and exact saved request:
canonical reconciliation returns its original receipt before new-state checks,
closure reads or artifact verification, including after later revisions or byte
damage. Different canonical reuse raises `SubmissionConflictError`.

## Current and history APIs

Import `ClaimUseInspectionLimits` from `research_pipeline.claim_use`. All six fields
are required ordinary positive integers, no greater than corresponding write
ceilings: `max_bindings`, `max_records`, `max_references`,
`max_assertion_revisions`, `max_metadata_bytes`, `max_result_bytes`. Result bytes
are capped at 4 MiB. Limits apply to the complete operation, not truncation.

`store.inspect_claim_use(use_id, *, limits) -> ClaimUseInspection` returns a
canonical privately retained JSON document through detached deterministic
`to_dict()`. It includes identity, binding revision, generation, status,
`requires_reassessment`, `eligible=false`, exact binding envelope/content,
candidate/context, separate conjunctive routes, exact upstream binding snapshots,
historical assessment/issue/policy pins, and current observed assertion pins with
attributed content. `still_assesses_bound_route` distinguishes successors that no
longer assess the selected route. `mechanical_freshness` contains the last
transition and structured reasons; `authorized_disposition.available` is false.
`limitations` always records absent positive authorization and unverified
attribution/independence/execution, plus unrecorded premise support and unresolved
context transfers where present. `attachment_availability` explicitly states
`not_checked_metadata_only`. Unchanged alternatives remain recorded possibilities.
Observation discovery includes the inspected root and every exact upstream
binding visited by support traversal, as well as recorded dependencies and
assessment/issue watches. Direct Issues remain attributed observations after
resolution, reopening or target removal through the assertion's historical union;
historical upstream pins are never substituted with current heads.

`store.claim_use_history(use_id, *, after_generation=0, limit=256, limits)
-> ClaimUseHistoryPage` returns generation-ordered transitions with binding,
submission/event identity, status and canonical causes. `limit` is 1–256;
`after_generation` is a nonnegative signed-64-bit integer. `next_cursor` is the
last returned generation when more exist, otherwise null. A page never silently
omits transitions within its requested range. Missing/unregistered uses raise
`RecordNotFoundError`. `get_revision`/`get_typed_revision` continue reading exact
immutable use snapshots independently of current generations.

## Independent write ceilings and failures

`WRITE_LIMITS` is an immutable public mapping, never operator configuration.

| Dimension | Hard ceiling per operation |
| --- | ---: |
| Routes per binding | 16 |
| Premise occurrences per binding | 256 |
| Direct binding-reference occurrences | 512 |
| Complete relevant request | 8 MiB |
| Reconstructed metadata record | 1 MiB |
| Aggregate metadata/work representations | 64 MiB |
| Distinct exact metadata records | 1,024 |
| Record/artifact reference occurrences | 8,192 |
| Assertion revisions | 1,024 |
| Exact policy Decision revisions (schema 5, independent of assertions) | 1,024 |
| Visited use bindings | 512 |
| Examined freshness index rows | 8,192 |
| Current-use transitions | 128 |
| Retained cause entries | 8,192 |
| Explicit support depth | 64 |
| Distinct verified direct artifacts | 256 |
| Aggregate verified direct artifact sizes | 64 MiB |

Proposed members, historical revisions, rejected-context reverse candidates and
required downstream work count. Occurrences are independent of cache hits. UTF-8
length/type/ordinal preflight precedes variable metadata reconstruction; indexed
streaming queries traverse equality prefixes followed by event ranges and the
complete index suffix, with remaining-budget-plus-one sentinels in both scalar
preflight and payload passes. Dependency, watch and upstream rows carry their
owning binding's registration event. Revision-event and selected association-link
projections carry the original source event; wrong-kind association sources still
consume examined occurrences. Historical traversal seeks only events strictly
before the current event; the proposed overlay supplies current-event records.
Later lifetime history remains invisible to the historical range and cannot
exhaust an earlier operation's account. Historical head and current-generation
lookups seek the visible predecessor through use/record and event indexes.
Context rejection and cause deduplication do not hide examined occurrences.
Direct binding discovery uses at-most-one-row membership lookups in the existing
binding table's exact `(use_id, binding_revision)` indexes, with registration events
strictly before the historical cutoff. Same-batch registrations reserve equivalent
index/byte work, including the full future event width. The binding keys also seed
the existing reverse-association indexes for inspection, and remain exact relevance
anchors in its assertion filter. No lifetime registration scan or persisted
self-dependency projection is added; schema-4 DDL and dependency ordinals stay
unchanged. Each direct cause is charged before canonical deduplication.
Assessment originals
pass their independent retained-shell and raw-field guards before freshness checks;
instance serializers cannot bypass either boundary.

Registration prepares the complete prospective inspection representation before
metadata insertion, using the same traversal, output shape and accounting as a
standalone maximum-limit inspection. This includes the binding envelope and content,
all exact upstream bindings (including same-batch forward pins), observed assertion
content, deduplicated limitations and every coalesced transition reason. Each root
has an independent inspection account; repeated preparation also counts toward the
owning write's aggregate work. The 4 MiB result ceiling and all independent public
ceilings apply without truncation, including the 64 MiB processing ceiling and
codec/canonicalization scratch. Even individually valid local bindings can exceed
these bounds when assembled into a complete view. Excess raises
`ClaimUseLimitError` (a `DomainValidationError`) naming its dimension and aborts
the submission. `ClaimUseIntegrityError` identifies inconsistent stored freshness
metadata. Existing record/reference/CAS/submission/artifact errors retain their
meaning. ToolAssessment keeps its separate independent protection and errors.

## Schema, migration and persistence

Creation still defaults to schema 2. Explicit ordinary integer `schema_version=4`
adds freshness metadata to unchanged schema-3 scientific/resource DDL. Schema 1/2/3
operations remain supported; new registration/current/history APIs on them raise
`StoreLayoutError` explaining the schema-4 migration requirement. They never
initialize tables, infer registration or upgrade on open. Locally valid historical
generic retries reconcile their canonical original request and receipt before the
fresh schema gate, including a coherent ClaimUse-looking document stored before
registration semantics existed. Conflicting reuse still fails before fresh target
admission; later heads and permitted artifact damage do not change the original
receipt. Preview remains fresh admission and rejects used submission IDs.
New schema-4 generic Review/Issue writes require supported coherent local
assessment content for impact
extraction; this preserves their shallow graph-admission boundary and grants no
scientific certification. Unsupported historical assertions remain readable; an
operation needing them for complete impact discovery fails explicitly.

Backup format/schema `(4,4)` supports exact restore by default. Only explicit
`restore_backup(..., target_schema=4, migration_provenance=...)` from schema 3 adds
the next migration. Older versions take explicit 1→2, then 2→3, then 3→4 steps.
The verified unpublished copy retains its durable `.restore-incomplete` marker
through transformation/publication barriers. SQL copies administrative history
text, records the source backup/provenance, preserves all requests, fingerprints,
revisions, heads, links, events, timestamps, resources and receipts without replay,
and starts binding, dependency, upstream, generation and current-use state empty.
Temporal revision-event navigation is backfilled for every original revision,
including generic and unsupported historical documents; association-link navigation
copies every original `candidate_claim`, `assessed_route` and `affected_record`
occurrence with its original ordinal and exact target, regardless of source kind.
This is SQL metadata copying without typed decoding, registration, submission replay
or receipt regeneration. Fresh creation starts with empty navigation projections.
The singleton origin is zero for fresh schema 4 or the source's exact maximum
scientific event ID for migration. It prevents reinterpretation of old generic claim-use-looking documents. Such a document
remains unregistered after migration: retry returns its original receipt without
creating a binding or generation, current/history inspection reports it as
unregistered, and a fresh write cannot convert that historical identity into a
registered use.

Open and backup inspection validate exact freshness projections and chronological
per-event relevance/propagation within coherent snapshots, without verifying live
attachment bytes merely to open or reconcile. Missing and extra transitions are
integrity failures. A separate streamed integrity pass checks exact temporal
navigation correspondence to original revisions, audit events and links, and owning
registration events for dependency/upstream rows. It visits lifetime metadata
without charging a single admission account or retaining a lifetime container.

Each chronological event still runs the complete bounded prospective preparation,
including independent root accounts and aggregate write accounting. Once that
admission plan finishes, validation uses independent bounded readers for each stored
record and binding-projection comparison. Stored transition scalars and canonical
causes must exactly match the derived transition, with type and byte-length checks
before fetching text; comparison work is not charged again to the completed
admission account. These checks preserve near-ceiling accepted registrations on
reopen and backup inspection while continuing to reject stored corruption.
There is no total lifetime generation or revision cap. Healthy backup
still verifies all historical artifacts; rehashing a corrupted projection cannot
make it valid. Resources, reports, operating decisions, controls and lifecycle
sources retain schema-3 capabilities on schema 4; new resource snapshots declare
actual schema 4 and its exact schema identity, while saved schema-3 documents stay
unchanged. Generic readable snapshots remain historical metadata projections,
not the current claim-use API.

## Schema-5 policy freshness and activation

Create with ordinary integer `RecordStore.create(root, schema_version=5)` for
transactional policy freshness. The default remains schema 2; explicit schema 3
and schema 4 remain supported without silent upgrade. ClaimUse content/envelopes,
SubmissionReceipt, both inspection/history method signatures, and the six-field
`ClaimUseInspectionLimits` constructor are unchanged. Schema-4 inspection remains
its exact version-1 document and its chronological events retain their original
causes, preparation and accounting. History still uses its version-1 structure.

Only a registered binding's explicit `policy_declared` dependency makes a Decision
identity a policy for this mechanism. Every newly admitted successor revision is
potentially material, including prose-only changes and identical declarations.
First creation is not an advancement. Kind, Review successor declarations, Issue
associations, arbitrary links and favorable values cannot infer a policy role.
Generic Decision JSON objects (including `{}`) remain valid shallow declarations;
policy resolution validates canonical JSON objects and exact complete envelopes
without scientific or operating-policy decoding. Recognized `format`/`version`
markers remain ordinary attributed JSON even when the declaration does not satisfy
the corresponding typed schema. No new policy-content schema or authority
interpretation exists. Generic Decisions use `submit`; new authenticated operating
decisions use `commit_operating_decision`.
`submit_typed` still rejects opaque Decisions and authenticated-operation bypasses.

Direct discovery seeks the policy identity/kind/role equality prefix of the existing
watch index, then its registration-event range and full suffix. It includes exact
historical bindings and same-batch dependency rows, without scanning registrations
or lifetime policy history. Each required bound Decision, visible preceding head
and proposed successor must resolve as coherent exact metadata. Direct attachment
bytes are unnecessary for observation and propagation; ordinary new-submission
artifact admission remains enforced. Missing/wrong-kind targets, damaged envelopes
or JSON, and unavailable required metadata fail explicitly rather than dropping impact.

A direct cause has exactly `type="policy_changed"`, `binding`,
`dependency_ordinal`, `bound_policy`, `previous_policy`, and `new_policy`. Each
policy is an exact Decision pin (`record_id`, `revision`, `target_kind`);
`binding` is the exact originating use pin. `previous_policy` is the head visible
before this submission, independently of the immutable bound pin. The owning
transition supplies the actual submission/event attribution. Schema-5
`assertion_changed` additionally carries its originating exact `binding`;
`binding_affected` retains that field. Downstream transitions retain all distinct
originating policy/assertion causes as well as immediate `upstream_affected` edge
reasons. A bounded delta worklist carries origins that arrive after a node's first
expansion, without enumerating complete paths. Registration alone never invalidates
upstream consumers. Repeated edges, matching occurrences and attempted cause
additions count before canonical deduplication.

Historical U@1 remains traversable after U@2 becomes current. A consumer pinned to
U@1/P observes P's successor and receives its origin causes, while current U@2/Q
changes only for U@2's own dependencies. Rebinding never repoints a downstream
pin. Policy, Review/Issue and rebinding changes are seeded together and coalesced
into one generation for each final current binding. First registration is generation
1; otherwise the generation advances exactly once, with overflow rejecting the
whole transaction. A same-batch binding may pin the old or the new policy revision.

Schema-5 current inspection is version 2 and adds:

- `observed_policies`, ordered by binding identity/revision and dependency ordinal.
  Each occurrence contains `binding`, `dependency_ordinal`, `bound_policy`,
  `observed_policy`, shallow `observed_content`, `attributed=true`, and `superseded`
  (observed revision greater than bound revision). Historical upstream policies
  participate without substituting current upstream bindings.
- `policy_freshness={"available":true,"activation_event_watermark":...}`.
- `mechanical_freshness.last_transition` remains the exact immutable stored row.
  Its `reasons` are the canonical union of stored causes and current derived
  `policy_pin_superseded` reasons, each containing `binding`, `dependency_ordinal`,
  `bound_policy`, and `observed_policy`. Derived observations create no transition.

Registration against an already advanced head therefore exposes the old bound pin
and current exact successor immediately, even if its only stored cause is
`binding_registered`. A head older than its bound pin is an integrity failure.
All transitioning current uses receive a complete maximum-limit prospective
inspection before insertion, including policy successor contents, historical
upstream pins and same-batch forward registrations. Independent per-root work also
counts against the aggregate write account; only the private future-event width
reservation differs from the committed view. There is no fabricated public receipt.
All planning, heads, revisions, links, events, receipts, temporal indexing and
freshness updates share the owning transaction and existing fault seams. Signed
64-bit scientific event exhaustion rejects the entire schema-5 write before
SQLite can allocate a lower fallback event. Original canonical request reconciliation
still precedes fresh-state checks. A point existence probe only bypasses newly
introduced policy preflight for a used, safely validated ID; it does not acknowledge
or compare the request and never reads its targets or attachments.

Schema 5 adds only `claim_use_policy_origin` and expanded ordered migration history;
scientific/resource/freshness DDL and indexes are shared unchanged with schema 4.
Fresh stores initialize both origins to zero. Verified format/schema `(5,5)`
backups restore exactly by default, preserving metadata bytes, both origins and
receipts without another migration row. The sole forward step is explicit
`restore_backup(schema4_backup, destination, target_schema=5,
migration_provenance=...)`; older stores take the existing 1→2→3→4 steps first.
There are no skipped or in-place upgrades. In the unpublished copy's single
`BEGIN IMMEDIATE`, SQL copies all six administrative columns, appends the attributed
4→5 source-backup/manifest row, and records the source's exact maximum scientific
event as policy activation watermark. Every existing scientific/freshness row is
preserved. No submission replay, receipt regeneration, generation or scientific
event occurs. The durable `.restore-incomplete` marker covers transformation,
commit and publication failures.

The policy singleton must be correctly typed; fresh schema 5 requires zero. A
migrated origin requires the matching 4→5 administrative step, cannot precede the
registration origin or exceed the scientific maximum, and must name an existing
event when nonzero. This is separate from the schema-4 registration origin.
For example, migrating a U@1/P@1 binding when P@2 is head retains its exact
generation/history but inspection exposes P@2 as superseding P@1. A later P@3
causes one P@2→P@3 transition while retaining bound P@1. Migration never invents a
P@2 transition.

Open/backup chronological validation uses precisely legacy schema-4 preparation,
output and accounts at/below policy activation, and schema-5 semantics only for
later events. It independently compares complete transitions, causes and all
projections. Activation validation streams the registered identities visible at
the watermark and runs an independent complete schema-5 boundary inspection for
each. It uses the first later scientific event as a strict cutoff (or the current
snapshot when none exists), avoiding watermark-plus-one overflow and excluding
later history from earlier accounts. A source whose required policy metadata or
complete boundary views exceed the limits cannot migrate and remains unchanged.
Lifetime streaming belongs only to integrity and activation verification; ordinary
admission uses exact bounded indexed ranges. New policy reads and result processing
consume the existing independent accounts and the additional 1,024 exact-policy
revision ceiling; separate prospective-root resolutions charge the aggregate write.
Excess raises `ClaimUseLimitError` naming the dimension and rolls back the write.
Projection inconsistencies use `ClaimUseIntegrityError` and existing public layout
translations; target, CAS, conflict and artifact errors retain their meanings.

Resources, reports, operating decisions, controls and lifecycle sources retain
existing capabilities on schema 5. New snapshots use actual schema 5 and the
registry-derived identity; historical schema-2/3/4 documents retain exact bytes
and interpretation. Policy declarations, sufficient/favorable reports and
mechanical freshness never establish policy authority, scientific truth, route
certification, independence or disposition. `eligible=false`,
`requires_reassessment=true` and `authorized_disposition.available=false` remain.

Positive authorization, promotion/Apply disposition, policy authority,
full support-sufficiency and sufficient-alternative certification, active-context
changes and context transfer, remaining task/fencing/report obligations, M0-S,
live evaluation and human scientific/release acceptance remain future work. D02
remains **PARTIAL**.
R-015 and R-077 remain **PARTIAL**.

## Executable synthetic example

This block uses only the standard library and product APIs. It is executed
verbatim in a fresh candidate-local interpreter by the example test.

```python
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.scientific import Claim, ResearchContext, Justification, encode_envelope
from research_pipeline.assessment import (
    IndependenceDeclaration, SubstantiveAssessment, SupportRouteAssessment, Review, Issue,
    encode_envelope as encode_assessment,
)
from research_pipeline.claim_use import (
    ClaimUse, ClaimUseRoute, ClaimUsePremise, ClaimUseInspectionLimits,
    encode_envelope as encode_use,
)
from research_pipeline.store import RecordStore

provenance = CreationProvenance("synthetic", "2026-11-05T00:00:00Z")
limits = ClaimUseInspectionLimits(512, 1024, 8192, 1024, 64*1024*1024, 4*1024*1024)


def pin(identity, role, kind):
    """Declare an exact revision-1 pin without resolving or authenticating it."""
    return RecordReference(identity, 1, role, kind)


def request(identity, records):
    """Use ordinary explicit expected-head CAS for each saved submission."""
    return Submission(identity, provenance, records, {r.record_id: r.revision-1 for r in records})


def review(candidate, route):
    """Report favorable synthetic scope; this grants no positive authorization."""
    return Review(pin(candidate, "candidate_claim", "claim"), pin("scope", "target_context", "research_context"),
        "synthetic reviewer", IndependenceDeclaration("candidate_aware_audit", "candidate_aware_audit",
        [], [], [], [], [], [], []), pin("manifest", "context_manifest", "work_product_manifest"),
        pin("policy", "authorization_policy", "decision"), [],
        SubstantiveAssessment("under_review", "supported_within_scope", ["analytical"], "applicable",
                              "unassessed", "Reported only", [], [], []),
        [SupportRouteAssessment(pin(route, "assessed_route", "justification"), "sufficient", "Unverified", [], [])],
        [], [], [], "synthetic")


def use(candidate, declarations, policy="policy"):
    """Keep alternatives separate and each route's premise support explicit."""
    return ClaimUse(pin(candidate, "candidate_claim", "claim"), pin("scope", "target_context", "research_context"),
        [ClaimUseRoute(pin(route, "support_route", "justification"),
         [ClaimUsePremise(pin(premise, "premise", "claim"),
          None if upstream is None else pin(upstream, "premise_use", "promotion_eligibility"))],
         [pin(assessment, "support_assessment", "review")])
         for route, premise, assessment, upstream in declarations], [],
        [pin(policy, "authorization_policy", "decision")], ["Synthetic only"])


with TemporaryDirectory() as temporary:
    root = Path(temporary) / "schema5"
    with RecordStore.create(root, schema_version=5) as store:
        store.submit(request("generic", [RecordEnvelope(identity, 1, kind, {}, provenance)
            for identity, kind in (("policy", "decision"), ("other-policy", "decision"), ("manifest", "work_product_manifest"))]))
        context = ResearchContext("Synthetic scope", [], [], [], [], [], [], [], [], [], [])
        records = [encode_envelope("scope", 1, context, provenance)]
        for identity in ("candidate", "premise-a", "premise-b", "downstream", "independent"):
            records.append(encode_envelope(identity, 1, Claim(identity, "synthetic", [],
                pin("scope", "context", "research_context"), [], [], []), provenance))
        for route, premise, candidate, assessment in (
            ("route-a", "premise-a", "candidate", "review-a"),
            ("route-b", "premise-b", "candidate", "review-b"),
            ("route-d", "candidate", "downstream", "review-d")):
            records.extend([
                encode_envelope(route, 1, Justification(pin("scope", "context", "research_context"),
                    [pin(premise, "premise", "claim")], [], route,
                    [pin(candidate, "conclusion", "claim")], [], []), provenance),
                encode_assessment(assessment, 1, review(candidate, route), provenance)])
        store.submit_typed(request("science", records))
        binding = encode_use("use", 1, use("candidate", [
            ("route-a", "premise-a", "review-a", None),
            ("route-b", "premise-b", "review-b", None)]), provenance)
        downstream = encode_use("downstream-use", 1, use("downstream", [
            ("route-d", "candidate", "review-d", "use")]), provenance)
        independent = encode_use("independent-use", 1, use("independent", [], "other-policy"), provenance)
        saved = request("register", [downstream, independent, binding])  # forward use reference
        original_receipt = store.submit_typed(saved)
        old_binding = store.get_typed_revision("use", 1)
        assert store.inspect_claim_use("use", limits=limits).to_dict()["generation"] == 1
        withdrawn = replace(review("candidate", "route-a"), route_assessments=[
            SupportRouteAssessment(pin("route-a", "assessed_route", "justification"),
                                   "stale", "Withdrawn assertion", [], [])])
        store.submit(request("withdraw", [encode_assessment("review-a", 2, withdrawn, provenance)]))
        objection = Issue("Synthetic objection", [pin("route-b", "affected_record", "justification")],
                          "Unverified", "blocking", "Inspect", "open", "Attributed only", [], [], [], "synthetic")
        store.submit_typed(request("issue", [encode_assessment("issue", 1, objection, provenance)]))
        store.submit_typed(request("resolve", [encode_assessment("issue", 2,
                               replace(objection, disposition="resolved"), provenance)]))
        for identity in ("use", "downstream-use"):
            current = store.inspect_claim_use(identity, limits=limits).to_dict()
            assert current["generation"] == 4 and current["eligible"] is False
            assert current["status"] == "requires_reassessment"
        # Rebind the current use to Q, retaining D's exact historical U@1/P pin.
        store.submit_typed(request("rebind", [encode_use("use", 2,
            use("candidate", [], "other-policy"), provenance)]))
        store.submit(request("policy-prose", [RecordEnvelope("policy", 2, "decision",
            {"declaration": "Prose-only change; no new authority"}, provenance)]))
        current = store.inspect_claim_use("use", limits=limits).to_dict()
        downstream_view = store.inspect_claim_use("downstream-use", limits=limits).to_dict()
        assert current["generation"] == 5  # Q is unrelated to this P successor
        assert downstream_view["generation"] == 5
        assert store.inspect_claim_use("independent-use", limits=limits).to_dict()["generation"] == 1
        observed = next(p for p in downstream_view["observed_policies"]
                        if p["binding"]["record_id"] == "use")
        assert observed["binding"]["revision"] == 1
        assert observed["bound_policy"]["revision"] == 1
        assert observed["observed_policy"]["revision"] == 2 and observed["superseded"]
        assert downstream_view["eligible"] is False
        store.submit(request("other-policy-prose", [RecordEnvelope("other-policy", 2, "decision", {}, provenance)]))
        assert store.inspect_claim_use("use", limits=limits).to_dict()["generation"] == 6
        assert store.inspect_claim_use("downstream-use", limits=limits).to_dict()["generation"] == 5
        assert store.head("candidate") == 1
        assert store.get_typed_revision("use", 1) == old_binding
        assert store.get_typed_revision("review-a", 1)[1].route_assessments[0].outcome == "sufficient"
        assert store.submit_typed(saved) == original_receipt
        assert len(store.claim_use_history("use", limits=limits).to_dict()["transitions"]) == 6
    with RecordStore.open(root) as reopened:
        assert reopened.inspect_claim_use("use", limits=limits).to_dict()["generation"] == 6
        assert reopened.submit_typed(saved) == original_receipt
```
