# Durable prepared run control

Run control records authenticated **preparation** and ordered report intent. It does
not admit, dispatch, resume, fence, terminate, or settle work. Every commit result
and inspection has `ordinary_work_allowed: false` and `recheck_required: true`.
Existing generic `run` records remain descriptive. Authority eligibility is a
current-policy evaluation; prepared control is an immutable record of one such
evaluation plus a pending report obligation. Neither is an admission token.

## Python boundary

`research_pipeline.run_control` contains detached contracts, codecs, identities,
projections, transition rules, and errors. `research_pipeline.run_control_store`
provides the following functions, with a `RecordStore` as their first argument.
The store exposes corresponding methods:

```python
store.commit_run_control(request, *, policy, evaluated_at, limits)
store.get_run_control_operation(operation_id, *, limits)
store.inspect_run_control(run_id, *, limits)
```

Commit returns `RunControlCommitResult`; get returns that original value or `None`;
inspect returns `RunControlInspection`. Policy is external trusted input, snapshotted
at entry. Preparation and continuation require normalized explicit UTC evaluation
time at least the transition time. Metadata-only reductions and evidence updates
need neither usable policy nor evaluation time. Historical get/inspect take no
policy, read no clock, and verify no external artifact bytes.

All five classes accept `Class(document)` and `from_dict(document)` and expose
`to_dict()`. Paired `dumps_request/loads_request`, `dumps_transition/loads_transition`,
`dumps_obligation/loads_obligation`, `dumps_commit_result/loads_commit_result`, and
`dumps_inspection/loads_inspection` use compact, sorted-key, ASCII-escaped JSON.
Exact classes are required; retained state is revalidated. Unknown/missing fields,
duplicate keys, coercions, invalid Unicode, cycles and nonfinite values reject.

## Wire contract, version 1

Every field below is required, including fields whose value is null. Each document
also has `format` and ordinary-integer `version: 1`. Formats have the prefix
`research_pipeline.` followed respectively by `run_control_request`,
`run_control_transition`, `run_report_obligation`, `run_control_commit_result`, and
`run_control_inspection`.

Identifiers obey `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`, including the actor. Actor is
controller attribution, not authentication. Narrative text uses its separate
4096-character Unicode contract. New trusted timestamps must already be normalized
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. Revisions are positive SQLite-range ordinary integers.
References have exactly `record_id`, `revision`, `relationship`, `target_kind`.
Digest pins have exactly `reference`, `envelope_digest`; SHA-256 covers the complete
canonical envelope, including provenance and ordered links.

| Document | Fields beyond format/version |
|---|---|
| Request | `operation_id run_id run_revision revision predecessor action actor transitioned_at preparation expected_authority operational_reason report` |
| Transition | `request disposition prepared_from authorization obligation` |
| Obligation | `operation_id run_id run_revision transition report_operation_id report_source_id report_manifest_id report_revision kind required_at selection` |
| Commit result | `operation_id transition transition_digest obligation obligation_digest disposition report_state report_source report_plan_id ordinary_work_allowed recheck_required receipt` |
| Inspection | `run_id head disposition transitions pending_obligations watermark ordinary_work_allowed recheck_required` |

`run_id` names the existing generic run. `run_revision` selects its exact stored
revision explicitly; it is independent of contiguous control `revision`, starting
at one. Preparation and continuation require the selected generic run's current
head. Other actions may retain the selection or explicitly advance it. Every
selection must have an actual project reference to the prepared stable project.
Control time and generic run revision cannot decrease.

`predecessor` is null only on revision one. Otherwise it pins the immediately
preceding control envelope, with role `supersedes`, kind `event` and its digest.
`prepared_from` is null on prepare; otherwise it references control revision one
with role `prepared_from`. Immutable bindings are reached through this reference.

Preparation has exactly `authority_domain purpose project initial_corpus
current_corpus context start_baseline operating_scope allocation previous_run`.
Purpose is `setup` or `main_research`. The project role is `project_setup`; both
corpus roles use `corpus_manifest`, with initial revision one of the same identity.
Context is a `context/research_context` reference or authority's explicit absent
value. Baseline is a `start_baseline/work_product_manifest` reference or explicit
unavailable `DeclaredText`. This initial saved-work meaning does not change
historical ReportRequest v1 restrictions. Operating scope is an exact existing
`OperatingScope` with matching purpose; all nested limits remain in force.

Allocation has exactly `allocation_id project_account run_account`. Each account
is explicitly unavailable or exactly `{account_id, operation_id, anchor}`. Anchors
are `resource_scope` references to the preparation's exact project/run revisions.
A known run account requires a known project account. Schema 2 requires both
unavailable. Schema 3 checks original create-account/allocate operations, receipts,
normalized rows, links, owner, dimensions, run purpose pools and run policy.
Controller-only historical run scopes cannot supply an exact revision anchor.
Project total ceilings are not equated to run availability. Control operations
never modify ledger rows, spending, reservations or uncertain liabilities.

`previous_run` is null or an exact `previous_run/event` digest pin to another
logical run under the same stable project with a different allocation identity.
The selected immutable history is checked without treating it as a latest-head
dependency. A replacement link releases or transfers nothing.

`expected_authority` is required only on prepare/continue, with role
`operating_decision`, kind `decision`; other actions require null. The latest
actual authority decision must match its identity and digest, exact prepared
dossier and full scope. Current credentials are verified even if the public policy
fingerprint is unchanged. Setup eligibility can permit an incomplete setup dossier;
main research cannot use that as sufficient evidence. Denial, revocation, stale
relevant heads, invalid validity windows, inadequate dossiers, unavailable required
artifacts, and withdrawn/invalid trust all fail closed.

Authorization is null except on prepare/continue, when it has exactly `decision
evaluated_at policy_fingerprint watermark`. The decision equals the expected pin;
the other fields come from the shared evaluator in the lifecycle write transaction.
No policy, credentials, secret bytes or detached permission token is persisted.
Watermarks have existing authority/audit semantics, not global freshness guarantees.
Continuation requires unchanged prepared bindings, scope and public policy
fingerprint, and checks current authority **before** pending-report denial.

Operational reason is null for prepare/checkpoint/milestone/continue. Otherwise it
has exactly `code detail`. Codes: `requested`, `checkpoint`, `resource_limit`,
`authority_unavailable`, `model_forbidden`, `failure`, `completed`, `abandoned`.
Abandon requires `abandoned`; cancel forbids `completed`. These are disposition
reasons, not evidence of process termination. Scientific outcome remains the
attributed report declaration: prepare requires `not_yet_assessed`; `objective_met`
is forbidden for cancelled/abandoned controls and failure/resource/authority/model
prohibitions. Terminal evidence updates retain those restrictions.

Report intent has exactly `selection declarations limits`. It reuses existing
report declaration and limit grammars, including SnapshotLimits,
ResourceInspectionLimits and all three report byte ceilings. Selection contains
at most 128 unique stable identities with role `report_selection`, in caller order.
No historical ReportRequest is persisted merely to express intent.

## Transition table and pending capacity

| Action | Allowed predecessor disposition | Result |
|---|---|---|
| prepare | no control history | prepared |
| checkpoint, milestone | any existing disposition | unchanged |
| pause | prepared | paused |
| continue | paused | prepared, subject to authority and zero pending reports |
| stop | prepared, paused | stopped |
| cancel | prepared, paused, stopped | cancelled |
| abandon | prepared, paused, stopped | abandoned |

There is no acknowledgment route in this foundation. Every accepted transition
adds one pending obligation, so public continuation cannot succeed after
preparation. There is no completion flag or bypass. Different operation IDs
repeating pause/stop/cancel/abandon are not idempotent no-ops.

Both total history and pending reports have hard ceilings of 1024. Resulting
routine counts (prepare/checkpoint/milestone/continue) are limited to 1021, pause
to 1022, stop to 1023, cancel/abandon to 1024. Smaller explicit caller budgets still
apply. These slots reserve metadata capacity, not storage success or resources.
Older obligations are never discarded, coalesced, overwritten, or regenerated.

## Identities and envelopes

`control_id(run_id)` is `run-control-` plus SHA-256 of UTF-8 run ID.
`obligation_id(operation_id)` is `run-control-obligation-` plus SHA-256 of UTF-8
lifecycle operation ID; `report_operation_id(operation_id)` uses
`run-control-report-` plus the same digest. Future source/manifest identities use
existing `reports.source_id(report_operation_id)` and `reports.manifest_id(run_id)`.
The control operation itself creates only reservations. The separate
[committed source stage](committed-lifecycle-sources.md) can later create the source
and actual capture time; it creates no report manifest or plan. Its source submission
uses `run-control-source-` plus the original operation digest. The reserved later
output event uses `run-control-output-` plus that digest, in the separate report
submission. Source commitment never rewrites the original control receipt.

The obligation's transition role is `run_control`. Its report revision equals the
control revision, and required time equals transition time. Kind is `initial` for
prepare, `checkpoint` for continue/checkpoint, otherwise the action. Selection is
copied exactly. Preparation, declarations and reasons are recovered through pinned
transitions, not duplicated into obligations.

Both records have kind `event`, null operational/scientific states, empty direct
artifact projections, and provenance `CreationProvenance(actor, transitioned_at,
{})`. Submission order is transition then obligation, with exact expected heads
`{control_id: revision-1, obligation_id: 0}`. Mutual links are inserted after both
revisions exist in the same transaction.

Transition link order: predecessor if present; prepared_from if present; selected
run; on prepare, project, initial/current corpus, present context/baseline/previous
run and known project/run account anchors; expected authority; selection in caller
order; declaration references traversed by sorted object keys with array order
preserved; required-report obligation. Authorization does not duplicate its decision
link. Obligation links are transition then explicit selection. Future report
identities are not links to nonexistent records.

`encode_transition/decode_transition` validate full projections. Obligations use
`encode_obligation(value, *, actor)` and `decode_obligation(envelope)`: actor is
intentionally absent from the obligation document. Local decoding validates that
envelope's actor/projection. Commit, recovery and inspection additionally require
its actor and all envelope/submission/audit provenance to equal the paired request.
Local decoding alone certifies neither pairing nor historical admission.

## Recovery, ownership and errors

Commit owns one BEGIN IMMEDIATE transaction and one aggregate reader. Original-ID
reconciliation occurs first, before current policy/time, heads, artifacts, report
destination or later transitions. Identical requests return the exact original
result; changed requests or another operation type raise SubmissionConflictError.
Original recovery checks actual membership/ordinals, canonical fingerprints,
projections, audit provenance, receipt and required immutable prefix. Inspection
checks the complete current history. Neither historical route grants permission.

An original result always records `pending_capture`, null report source/plan and
the original two-member receipt, even if subsequent work eventually publishes a
report. Inspection contains ascending `{envelope, receipt}` transitions and a
complete ascending obligation-envelope list. Empty histories have null head and
disposition. No API returns a successful truncated list.

Generic/typed submission and import preparation cannot install lifecycle formats,
control/obligation namespaces, reserved report-operation IDs or controlled manifest
and source identities. Authenticated authority writes also honor report operation
reservations. Fresh legacy report writes for managed runs reject before capture or
object placement. Existing exact original reconciliation remains first; uncontrolled
legacy reporting remains available. Preparation cannot adopt a legacy report stream
or an unrelated generic event at the canonical control identity.

Precommit failures roll back both members. COMMIT uncertainty, postcommit interruption
and checked-close acknowledgment loss require reopening and recovery with the same
original operation ID. An exception after commit does not prove rollback, and must
not cause automatic delivery under a replacement ID. Durable metadata cannot be
promised while storage is unavailable.

| Error | Meaning |
|---|---|
| RunControlValidationError (DomainValidationError) | malformed new contract or forged value |
| RunControlIntegrityError | stored metadata/history/projection inconsistency |
| RunControlLimitError | hard, caller or reserved-capacity exhaustion |
| RunControlStateError | illegal transition, binding, ownership or pending gate |
| RunControlPermissionError | failed current authority |
| SubmissionConflictError | changed original operation or another operation type |
| RevisionConflictError | control CAS or predecessor digest conflict |

Existing store closed/layout/busy/database errors remain distinct. Diagnostics never
dump requests, policies or keys.

## Explicit simultaneous bounds

`RunControlLimits(metadata, max_transitions, max_pending_reports, max_result_bytes)`
requires every argument. Metadata is an exact revalidated AuthorityLimits;
transition/pending counts are ordinary integers 0..1024, result bytes 1..64 MiB.
Authority's result limit independently bounds its evaluator result. Its history
budget counts traversed control, authority and typed dossier revisions. All helpers
share record/reference/artifact/metadata allowances, including previous-run and
resource anchors; repeated retained copies still consume bytes.

Hard canonical sizes: request 2 MiB; transition 4 MiB; obligation and commit result
256 KiB each; stored two-member submission 8 MiB; inspection 64 MiB; report-intent
object 256 KiB. New documents allow at most 48 containers deep and 131072 JSON value
nodes. Existing nested contract restrictions remain independent. Zero history and
pending budgets allow only an empty inspection whose fixed overhead fits.

Stored SQL types and UTF-8 lengths, actual link/member counts and contiguous
ordinals are checked before decoding/reconstruction. Known transition and obligation
members have separate SQL content-length checks before the saved original batch is
parsed. Operation classification uses actual membership and top-level envelope/content
discriminators; a control-format string nested in descriptive content has no authority.

Fresh envelope preflight includes fixed fields, exact provenance, every ordered link,
empty artifacts and null state fields. Projected occurrences count before their tuple
is allocated. The complete submission and fingerprint wrapper are measured before
batch construction or canonical encoding. Detached trees, copied envelopes, typed
validation, receipt/result copies and canonical/ASCII strings reserve separate bytes
under the same reader. Scratch reservations are released only after those temporary
representations leave scope; cache hits do not excuse new copies. Receipt reservations
use a conservative event-ID bound, reconciled to the actual committed receipt afterward.
Authority reconstruction separately reserves its retained signed value and detached
decision tree before allocation, with scoped codec scratch. The resolver seed's copied
submission is also reserved before construction and stays charged while its root is
retained by dossier traversal; constructor scratch is a separate temporary allowance.

JSON preflight counts UTF-8 bytes without making an encoded copy, then counts value
and container tokens and nesting before parsing. Object keys are not value nodes;
quoted escapes cannot create extra tokens. Strict parsing still rejects duplicate keys
and malformed syntax. Empty and populated outputs reserve their framing and detached
validation copies before construction. Complete envelope and saved-submission node/depth
limits apply to fresh writes as well as recovery, including repeated projected references
and all enclosing wrapper fields. Fresh preflight combines measured content and cached
envelope shapes before constructing projections or the two-record submission.
Nested authority results retain their independent
authority ceiling; the final control result uses its separate control ceiling. No legacy
unbounded history, report closure or full ledger replay serves as a fallback.

## Mandatory subsequent scope

REQ-D04-005 FOLLOWON-01–13 remain mandatory subsequent work, not optional backlog:

1. Automatically drive initial/checkpoint/reduction reports and discharge pending intent.
2. Publish seven-group reports and continuation manifests with preserved earlier views.
3. Keep unknown scientific/job/resource facts explicit and capture without inference.
4. Add compatible lifecycle report binding/version with coherent watermarks.
5. Distinguish durable intent, capture, plan, publication and uncertain acknowledgment.
6. Reconcile and reuse original committed sources/plans without replay or recapture.
7. Preserve pending order through stop/cancel and prevent acknowledgment loops.
8. Recheck restart/restore readiness and current policy without treating snapshots as tokens.
9. Preserve simultaneous bounded reads and preconstruction checks across recovery.
10. Extend real failure/race/restore coverage through publication and late revisions.
11. Supply an executed lifecycle guide and precise recovery/version documentation.
12. Preserve predecessor contracts and controller-owned validation/integration evidence.
13. Retain broader queue/attempt/fencing, transactional admission/reservation, worker
    isolation, context/tool/model/access enforcement, adapter qualification,
    synthesis/export and M0-S boundaries.

The control foundation itself implements none of rendering, publication,
acknowledgment, restart readiness, task admission, dispatch or model hooks.
[Committed lifecycle sources](committed-lifecycle-sources.md) now implement the
separate bounded source capture/recovery stage, preserving all pending obligations. D04/M0-E remains partial;
synthetic engineering fixtures establish no live scientific execution, scientific
validation, new operating grant or M0-S claim.

## Offline lifecycle intent binding

The [offline lifecycle-report binding contract](lifecycle-report-binding.md) retains and validates
original preparation, selected control transition and required-report intent
under explicit independent processing allowances. It accepts arbitrary saved-work
baselines without changing historical report v1 baseline grammar. It proves local
consistency only, creates/discharges no obligation, and never authorizes ordinary work.
[Committed lifecycle sources](committed-lifecycle-sources.md) verify persisted origin
and commit coherent source facts. Rendering integration, publication, acknowledgment
and current-policy continuation remain mandatory subsequent ADR-063 slices.
