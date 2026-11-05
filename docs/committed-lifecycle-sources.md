# Committed lifecycle sources

Lifecycle sources commit the actual first observation for an existing required
control obligation. They preserve its original intent, every pending obligation,
and `ordinary_work_allowed:false` / `recheck_required:true`. They produce no
rendered report, continuation output, publication, acknowledgment, restart
readiness, or worker admission. The accepted offline binding remains structural
evidence; capture verifies its persisted origin independently.

Schema support extends through explicit schema 6, using the actual registry-derived
schema identity in new captures and retaining original-operation reconciliation,
authentication/guards and resource liabilities. Old saved documents retain exact
bytes and interpretation. Target-context freshness shares the existing insertion
transaction; it grants no work admission or scientific authority.

## Public boundary and identities

Import contracts/codecs/errors from `research_pipeline.lifecycle_report_source`.
The connection-owning functions in `research_pipeline.lifecycle_source_capture`
take a `RecordStore` first; the matching store methods are:

```text
commit_lifecycle_source(control_operation_id: str, *, expected_binding_digest: str,
                        limits: LifecycleSourceLimits) -> LifecycleSourceCommitResult
get_lifecycle_source_operation(control_operation_id: str, *,
                               limits: LifecycleSourceLimits) -> LifecycleSourceCommitResult | None
inspect_lifecycle_source(control_operation_id: str, *,
                         limits: LifecycleSourceLimits) -> LifecycleSourceInspection
read_lifecycle_source(control_operation_id: str, *,
                      limits: LifecycleSourceLimits) -> LifecycleSourceObservation
```

The argument is the **original control operation C**. Inspection returns its
verified original binding digest. Commit accepts neither a binding packet nor
an observation. A missing control makes inspect/commit/read raise
`RecordNotFoundError`; get returns `None` when no source submission exists.
An occupied source submission belonging to another submission is a conflict.

`S = run_control._identity('run-control-source-', C)` owns the one-member source
submission. Preserve `O = run_control.report_operation_id(C)`,
`E = reports.source_id(O)`, `M = reports.manifest_id(run_id)`, and obligation
report revision `n`. Capture creates only `E@1` under S, ordinal zero, with
`expected_heads={E:0}`. Neither O nor M is consumed. Captures may occur out of
obligation order, independently of earlier sources or rendered reports.

The reserved later output identity is
`X = run_control._identity('run-control-output-', C)`. The later protocol uses a
separate O submission containing `X@1` and `M@n`, consuming the exact committed
E/source artifact and requiring heads `X:0, M:n-1`. Output commitments must be
ordered by manifest revision. They cannot append to S, replace E, regenerate its
source, or reinterpret S's one-member receipt. This milestone implements no
output API, output event, manifest, placeholder or publication mechanism.
The separate [pure lifecycle renderer](lifecycle-report-rendering.md) now returns
generated report/continuation bytes from detached sources; capture does not invoke it.
Generic, typed, import, authority, control and legacy-report fresh writes respect
these reservations. Exact historical reconciliation still precedes fresh guards.

## Closed version-one documents

Every new top-level observation/result/inspection has ordinary integer `version:1`,
its exact format, and the fixed gates `ordinary_work_allowed:false` and
`recheck_required:true`. Unknown and omitted fields reject. Complete references,
canonical six-fraction UTC dates and lowercase SHA-256 digests retain existing
conventions. Canonical JSON is sorted compact ASCII, without duplicate fields,
nonfinite numbers, invalid Unicode or cycles.

| Format suffix after `research_pipeline.lifecycle_source_` | Additional exact fields |
|---|---|
| `observation` | `binding binding_digest observed_at control scientific resources baseline root_categories source_bindings verified_artifacts qualifications snapshot_id` |
| `commit_result` | `operation_id control_operation_id binding_digest source_event source_artifact snapshot_id observed_at scientific_watermark resource_sequence captured_control receipt` |
| `inspection` | `control_operation_id binding_digest obligation state result artifact_verification` |

The observation's `binding` is the complete unchanged LifecycleReportBinding v1
reconstructed from actual preparation, selected transition and obligation.
`binding_digest` hashes that complete packet. The original preparation deliberately
occurs twice for an initial binding. Original transition/preparation dates remain
in it. `observed_at` is sampled **after evidence collection and artifact verification**
in the first capture transaction, never backdated to the selected transition.
The lower bound is the maximum canonical timestamp of the scientific watermark,
every retained scientific record's original commit, every captured control
transition's `transitioned_at` and original receipt commit, and every resource
receipt in the complete captured prefix. Equality succeeds. Resource receipt
clocks are independent of the scientific watermark, and sequence order does not
imply monotonic wall-clock time: an earlier sequence may have the latest date.
Narrative dates, attributed content and policy validity intervals add no capture
clock constraints. A fresh clock below this maximum raises
LifecycleSourceStateError before source artifact placement or metadata insertion;
it is never clamped, retried or fabricated.

`control` is the complete unchanged RunControlInspection v1 through the actual
captured head, including later cancellation and every pending obligation.
Its watermark equals `scientific.watermark`. `scientific` retains DetachedSnapshot's
format, identity, original embedded limits and `expected_unverified` wording.
`verified_artifacts` separately records the digest-sorted exact `{digest,size}`
inventory verified by source capture. `resources` is the existing report_resources
v1 complete selected-project projection, or the exact schema-2 unavailable value.
It retains relevant siblings, balances, unknown liabilities, sequence gaps,
original receipts and complete-snapshot identity, excluding unrelated-project
payloads. Original unavailable account declarations stay unavailable; later facts
retain their own dated provenance. A saved schema-2 source stays schema 2 after
explicit migration.

Fresh capture checks the complete resource prefix before discarding unrelated
payloads; verified historical reads check that same saved prefix in their bounded
original receipt scan. A stored prefix receipt later than `observed_at` raises
LifecycleSourceIntegrityError. Operations after the saved sequence are irrelevant.
Detached constructors/codecs/retained consumers check the maximum of facts actually
present, raising LifecycleSourceValidationError for a contradictory observation.
Sequence gaps and `complete_snapshot_id` disclose no unrelated payload and cannot
establish omitted receipt dates offline. No private dates or new fields are added
to the public projection.

`baseline` equals the preparation's saved-work pin/unavailability exactly in its
type-preserving canonical JSON representation: boolean `true` and float `1.0`
cannot replace ordinary integer revision `1`. An
available arbitrary typed WorkProductManifest and its outgoing closure are verified
as saved work, without recursively reading historical report observations.
`root_categories` has exactly, in selection order: `scientific`, `dossier`,
`saved_baseline`, `control_history`, `resource_evidence`. Scientific roots retain
the original project, selected exact generic run, available context, original
selection and declarations. Dossier repeats initial/current corpus pins in that
order. Control history selects the actual captured control head. Resource evidence
retains operation/reference order. Category repetitions remain; SnapshotSelection
uses first-occurrence deduplication of exact pins across this order. Both caller
scientific and original snapshot `max_roots` count these distinct pins, not
repeated declaration references. Source-validation closure bounds its scientific
root occurrences separately by the locally derived category length, covered by
the source byte/node/depth/work reservations; repetitions remain charged. No latest
scientific head is selected implicitly.

`source_bindings` is the record-sorted list of exact
`{record_id,revision,event_id,ordinal}` entries. Each binds the actual original
submission member; complete relevant original batches, including unselected
members, are verified rather than silently elided. Scientific entries retain
original envelope bytes, submission IDs, fingerprints and commit dates.

The fixed ordered qualifications are:

1. This is a committed source observation, not a rendered or published report.
2. The observation records the actual first-capture snapshot; it does not reconstruct state at the selected transition time.
3. Original declarations and known gaps remain attributed input; missing execution, job, charge, and scientific interpretation evidence is not inferred.
4. All required report obligations remain pending and ordinary work remains prohibited.
5. Historical authority evidence does not establish current permission.

`snapshot_id` hashes the complete canonical observation with only that field
omitted, excluding the future source artifact reference and receipt to avoid a
circular identity. Detached values prove structural consistency only. Supplied
source binding revisions and artifact sizes are validated as ordinary integers,
even where an equal-valued boolean or float would compare equal in Python.
Committed inspections require the captured control head to belong to the obligation's
control stream and include its selected revision; a later head after cancellation
is valid. The source event must match the obligation and observation time must not
precede its required time.

The source event uses format `research_pipeline.lifecycle_source_event`, exactly
`format version request snapshot_id observed_at scientific_watermark resource_sequence
captured_control source_artifact`. Request is exactly
`{control_operation_id,binding_digest}`. Resource sequence is null on schema 2.
Captured control is `{reference,envelope_digest}` for the inspection's last
transition. Provenance is `CreationProvenance('lifecycle-source-controller',
observed_at,{})`; both event status fields are null. Record links are sorted distinct
closure pins with actual kinds and relationship `lifecycle_source_revision`.
Artifact links contain the canonical observation first, then digest-sorted distinct
evidence; conflicting sizes reject. There are no links to nonexistent outputs.

The result's `source_event` is E@1 with `lifecycle_report_source/event`; its original
receipt belongs to S and contains exactly that one member. The scientific event
immediately precedes the source receipt's event, and recovery checks the actual
preceding audit tuple. Inspection contains the complete selected obligation,
`state:durable_intent,result:null` or `state:committed_source,result:<original>`;
`artifact_verification` is always `not_checked`. It neither detects every orphan
object nor certifies availability.

Each detached class supports `Class(document:dict, *, limits)`,
`from_dict(document, *, limits)` and `to_dict(*, limits)`. The codec pairs are
`dumps_observation/loads_observation`, `dumps_commit_result/loads_commit_result`,
and `dumps_inspection/loads_inspection`, all with mandatory keyword-only limits.
Dumps returns canonical ASCII str; loads accepts exact str or bytes. Frozen exact
classes retain only private canonical `_json`, use non-content repr and identity
equality, and expose no unbounded convenience properties. Every consumption
revalidates bypass-mutated state; a detached instance never authenticates storage.

## Independent limits and published accounting

All three new limits are frozen, keyword-only, exact classes with every field
required. Nested limits are reconstructed at every public boundary.

| Limit class | Required fields |
|---|---|
| LifecycleScientificCaptureLimits | `max_roots max_records max_references max_record_bytes max_metadata_bytes max_artifacts max_file_bytes max_total_bytes max_work_bytes` |
| LifecycleResourceCaptureLimits | `max_accounts max_operations max_rows max_references max_record_bytes max_metadata_bytes max_result_bytes max_work_bytes` |
| LifecycleSourceLimits | `control:RunControlLimits binding:LifecycleReportBindingLimits scientific:LifecycleScientificCaptureLimits resources:LifecycleResourceCaptureLimits max_artifacts max_artifact_bytes max_artifact_total_bytes max_input_bytes max_source_bytes max_submission_bytes max_result_bytes max_work_bytes max_nodes max_depth` |

New integers exclude booleans/subclasses. Count ceilings are at most 1,048,576;
max_depth is at most 96. Work/artifact byte ceilings are at most `2**63-1`;
other byte ceilings at most 64 MiB. References, artifacts, resource accounts,
operations and rows, total artifact bytes, nodes and depth may be zero. Other
ceilings are positive. Inherited stricter fragment/type/grammar ceilings still
apply. There are no defaults or new planner max_files budget. Original rendered
output/max_files allowances remain intent only.

Scientific meanings follow SnapshotLimits. Caller and original embedded capture
allowances both apply, with their minimum authorizing work; only original embedded
limits are serialized. `Ws = 64*M + 4096`, where M is the smaller scientific
metadata allowance, is reserved **before shared capture/reconstruction**. Existing
metadata/count accounting remains, with SQL type checks and complete enclosing
envelope, escaped record entry and snapshot framing before canonical copies. Each
record's ordinary positive `fetched_bytes` must independently fit the smaller
caller/original `max_record_bytes`, as must its complete canonical entry.

Resource counts cover complete replay before capture projection. Rows count
normalized rows, links, administrative history, schema and registration reads and
auxiliary reference/watermark checks, with repeated planned reads charged again.
Every consumed SQL cell is preflighted by type/length before payload fetch; lengths
are summed incrementally in Python. References count repeated occurrences.
Per-record bytes bound complete requests/receipts/operations and normalized rows.
Metadata bounds raw fetched and retained representations; result bytes bound full
resource wrappers. Let B be preflighted raw metadata-cell bytes, A the number of
unique account creations in bounded original `create_account`/`allocate` requests,
and O the actual operation count. Authorize `256*(B+1)` before decoding requests
one at a time for structural membership. Count scope, policy and evidence reference
occurrences directly before building combined lists; repetitions count. Reconcile
ordered links and account/allocation/reservation identities and owning operations
with those requests before target queries or shared replay. Stored counts remain
additional checks and cannot substitute for request membership. Charge both the
membership pass and every later repeated fetch, plus target/watermark probes and
auxiliary reads. Before the accepted replay/accounting algorithms run, authorize
the full `Wr = 256*(B+1) + 262144*(A+1)*(O+1)`; its metadata term is the initial
authorization extended to the final B, not a second full charge.

Detached relevant projections use their full canonical size for B and request-derived
A/O. Their row allowance counts all supplied projection rows. Declaration membership,
unique reservation usage, and account/purpose balance membership must match requests
before accounting; deleting projections cannot lower the authorized work. The fixed
term includes empty replay overhead and existing at-most-16 dimension projections. Read checks saved
relevant originals through the captured global sequence without requiring today's
balances or later artifacts. Scientific watermark existence uses checked probes,
not an unbounded set of all audit IDs.

At each new codec boundary, R is raw UTF-8 length measured without an encoded copy,
or zero for dictionary construction. Check `R <= max_input_bytes` and reserve 8R
before lexical node/depth preflight and strict parsing. P is exact full canonical
ASCII size, including escapes, repeated envelopes and nested JSON strings.
Reserve `W = 8R + 64P` before semantic reconstruction, hashing, serialization or
retention. Retained consumers have R=P, hence W=72P. Value nodes exclude keys;
root-container depth starts at one; aliases count repeatedly and only ancestor
cycles reject. Equality is permitted. These are logical representation charges,
not RSS measurements or claims about allocator behavior.

Observation P must fit max_source_bytes, original embedded max_source_bytes and
max_result_bytes. Results/inspections must fit max_result_bytes, including nested
results. Event, submission and fingerprint-version wrapper independently fit
max_submission_bytes. Store construction reserves 64 times each simultaneously
required wrapper before assembly/copy, without refunding still-retained values.
New receipt reservations use a 19-digit SQLite event ID and 29-byte canonical
JSON timestamp upper bound; recovery uses actual receipt size. Control/history
processing uses the accepted Reader's distinct-record/history counters, repeated
ordered reference counter and fetched/retained/temporary byte accounting.

Outer artifact ceilings cover the distinct complete required inventory, including
the generated source, by count, individual size and unique-digest total size.
Scientific evidence limits apply independently. Metadata-only recovery charges no
artifact reads and works with zero artifact-read allowances. Reads reserve a fixed
1 MiB streaming chunk; retained source reads additionally reserve both chunk/joined
source bytes and codec work (`74*source_size + 1 MiB`, alongside retained wrappers).
This reservation updates the same cumulative counter as all wrapper reservations
and remains live until the public operation completes, including subsequent event,
original-batch and receipt reconstruction. Fresh capture also retains its single
streaming slot until completion. Sequential evidence verification reuses that slot;
there is no refund while source representations remain live.
Actual reads use `min(1 MiB, remaining expected bytes + 1)`; growth bytes are never
retained. Existing no-follow, descriptor, size/hash, sync and checked-close rules
remain authoritative. Required evidence is never truncated to fit.

## Trust, failures and recovery

Historical control validation checks original committed authority metadata and
linked previous-run prefixes, without evaluating today's policy or claiming
cryptographic verification with unavailable current keys. Original declarations,
unknowns and gaps remain attributed input. Cancellation, absent rows and settlement
do not establish scientific meaning or execution/job completion. No credentials
are persisted or reconstructed, and capture uses no model/network/tool/TeX hook.

| Actual outcome | Recoverable source state |
|---|---|
| No source submission; optional detached capture or unregistered object | durable_intent; no committed-source result |
| Exception before metadata commit | inspect actual outcome; an orphan object may remain |
| Successful COMMIT, acknowledgment lost | committed_source; recover using original C/S |
| COMMIT, rollback, storage or checked-close failure | uncertain until original-ID reconciliation; no claimed rollback or acknowledgment |
| Source/evidence objects later missing or damaged | metadata recovery may return authentic original result; verified read fails |

Commit reconciles S before fresh heads, clock, replay, policy or artifact guards.
Exact retries compare the original expected binding digest and return the immutable
original receipt/date without current-clock checks, even after a clock rollback.
Different input raises SubmissionConflictError. Source bytes
are durably synchronized and checked closes succeed before metadata registration
and E insertion in the same transaction. No alternate ID, orphan deletion, overwrite,
external-work replay or obligation discharge is performed. Original control results
retain their historical `pending_capture` and pending-obligation meanings.

Get/inspect/exact retry never open artifacts. Read verifies canonical source bytes,
all detached semantics, committed event/submission links, captured original record
bytes and complete original batch membership, saved relevant resource requests,
receipts/normalized rows/links, and every scientific artifact. Healthy backup/exact
restore preserves source bytes, identities, receipts and histories. A stored source
is not a substitute for a complete runtime backup or current-policy restart.
After bounded SQL preflight, historical reads validate every normalized account
scope with the existing closed scope contract before traversing the hierarchy,
including child scopes. Malformed scope metadata raises LifecycleSourceIntegrityError
with `inconsistent stored source evidence`; genuine SQLite errors retain their
store-error mapping. Later resource operations remain excluded by the saved sequence.

Errors: LifecycleSourceArgumentError(ValueError),
LifecycleSourceValidationError(DomainValidationError), LifecycleSourceLimitError,
LifecycleSourceIntegrityError and LifecycleSourceStateError (the latter three
ValueError subclasses). Missing/unknown Python arguments remain TypeError. Order:
validate/detach all limits; exact argument/self types and identifier/digest syntax;
raw SQL/input safety preflight; bounded decoding/local semantics; original-operation
reconciliation/conflict; fresh-only history/capture guards; durability and insertion.
Missing/bypass-mutated `_json` on an exact class is validation failure. Inherited
limit failures translate to stage-labelled limits; malformed detached values and
stored inconsistencies have sanitized diagnostics. SubmissionConflictError,
RevisionConflictError, RecordNotFoundError, store closed/layout/operational errors,
and artifact layout/not-found/integrity/I/O errors retain their meanings. Genuine
storage errors and programming assertions are not logical denials.

The separate [pure lifecycle renderer](lifecycle-report-rendering.md) shares the
seven-group projection and inert framing with historical reports. Automatic lifecycle
driving, output commitment and immutable plans, publication, acknowledgment, and
current-policy restart remain mandatory later ADR-063 slices.
D04, transactional admission/fencing, worker isolation, scientific qualification and
live-provider obligations remain partial. These local engineering facts are no
scientific or live-provider acceptance.

## Runnable committed-source example

Run this product/stdlib-only block with candidate-local `implementation/src` on
PYTHONPATH. Runtime directories are disposable and owned by the example. The new
subprocess test extracts this exact block; documentation alone is not execution
evidence. The synthetic signing key is external demonstration input, never a new
operating grant or a value stored in source bytes.

```python
from copy import deepcopy
from dataclasses import replace
from research_pipeline import run_control as c, operating_authority as a
from research_pipeline import lifecycle_report_binding as b
from research_pipeline import lifecycle_report_source as s
from research_pipeline.store import RecordStore
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.source import DeclaredText
from research_pipeline.corpus import CorpusManifest, CorpusInspection, encode_envelope as corpus_envelope
from research_pipeline.project import (AttributedText, ProceduralJudgment, ReadinessProposal,
    ProjectSetup, encode_envelope as project_envelope)
from research_pipeline.work_product import WorkProductManifest, WorkProductFile, encode_envelope as work_envelope
from research_pipeline.resources import ResourceRequest
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.reports import unavailable
from research_pipeline.resources import UNITS


def vector(default=0, **values):
    """Declare all supported resource dimensions without observing available capacity."""
    return [{"dimension_id": kind, "quantity": values.get(kind, default)} for kind in UNITS]


def text(value):
    """Attribute a small synthetic narrative without claiming scientific verification."""
    return {"text": {"value": value, "unknown_reason": None},
            "attribution": {"value": "Illustrative author", "unknown_reason": None}}


unknown = unavailable("Not established by this offline example.")
policy = {"policy_id": "illustrative", "statement": "Declared bounds, not current permission",
    "verification_minimum": vector(tool_calls=1),
    "handoff_minimum": vector(model_calls=2, model_input_tokens=6, model_output_tokens=10,
                              local_time=1, local_storage=1),
    "closeout_minimum": vector(local_time=1, local_storage=1),
    "handoff_call_bounds": {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5},
    "context_capacity_tokens": 8, "per_call_output_tokens": 5, "monetary_services": []}
scope = a.OperatingScope({"format": "research_pipeline.operating_scope", "version": 1,
    "purpose": "setup", "capability_releases": [], "data_access": [], "disclosures": [],
    "resources": {"dimensions": [{"dimension_id": kind, "kind": kind, "unit": unit,
        "currency": None, "scale": 1} for kind, unit in UNITS.items()],
        "ceiling": vector(100), "purpose_limits": {"ordinary": vector(tool_calls=2),
            **{name: policy[name + "_minimum"] for name in ("verification", "handoff", "closeout")}},
        "call_bounds": None, "run_policy": policy}}).to_dict()
report = {"selection": [], "declarations": {
    "objective": text("Inspect original saved intent"), "scope": text("One local packet"),
    "outcome": {"label": "not_yet_assessed", "explanation": unknown,
                "attribution": {"value": "Illustrative author", "unknown_reason": None}},
    "interpretation": unknown, "stop_reason": unknown, "results": [], "completed_checks": [],
    "unresolved_issues": [], "saved_work": [], "outstanding_jobs": [], "gaps": [],
    "continuation": unknown, "reproduction": {name: text("No execution asserted")
        for name in ("procedure", "build", "environment")}, "limitations": [text("Unauthenticated synthetic data")]},
    "limits": {"snapshot": {"max_roots": 100, "max_records": 100, "max_references": 10000,
        "max_record_bytes": 4000000, "max_metadata_bytes": 30000000, "max_artifacts": 10,
        "max_files": 10, "max_file_bytes": 4000000, "max_total_bytes": 30000000},
        "resources": {"max_accounts": 10, "max_operations": 100, "max_metadata_bytes": 30000000},
        "max_source_bytes": 30000000, "max_output_file_bytes": 30000000, "max_output_total_bytes": 2000000}}

now = '2026-11-01T00:00:00.000000Z'
provenance = CreationProvenance('synthetic-controller', now, {})
actor = DeclaredText('Synthetic author', None)
unknown_text = DeclaredText(None, 'Not established by this example')
inspection = CorpusInspection('uninspected', [], actor, actor, [])
unassessed = ProceduralJudgment('not_assessed', 'No scientific work assessed', actor)
corpus = CorpusManifest('Empty seed inventory', 'Keep original inputs', 'Explicit selection', actor,
    [], [], [], [], [], [], None, 'Initial baseline', actor, [])
project = ProjectSetup(AttributedText(DeclaredText('Observe saved state', None), actor),
    AttributedText(unknown_text, actor), AttributedText(unknown_text, actor),
    RecordReference('corpus', 1, 'initial_corpus', 'corpus_manifest'),
    RecordReference('corpus', 1, 'current_corpus', 'corpus_manifest'), None, None, None,
    inspection, [], [], ReadinessProposal('insufficient_materials', ['No seeds'], actor, [], unassessed, unassessed),
    [], None, 'Initial setup', actor)
metadata = a.AuthorityLimits(100, 1000, 1000, 20000, 4194304, 67108864,
                            1000, 1000000, 10000000, 67108864)
control_limits = c.RunControlLimits(metadata, 1024, 1024, 67108864)
limits = s.LifecycleSourceLimits(control=control_limits,
    binding=b.LifecycleReportBindingLimits(max_input_bytes=16777216, max_packet_bytes=16777216,
        max_work_bytes=2147483648, max_nodes=b.MAX_NODES, max_depth=b.MAX_DEPTH),
    scientific=s.LifecycleScientificCaptureLimits(max_roots=100, max_records=1000, max_references=20000,
        max_record_bytes=4194304, max_metadata_bytes=67108864, max_artifacts=100,
        max_file_bytes=67108864, max_total_bytes=134217728, max_work_bytes=8589934592),
    resources=s.LifecycleResourceCaptureLimits(max_accounts=100, max_operations=1000, max_rows=10000,
        max_references=10000, max_record_bytes=4194304, max_metadata_bytes=67108864,
        max_result_bytes=67108864, max_work_bytes=8589934592),
    max_artifacts=100, max_artifact_bytes=67108864, max_artifact_total_bytes=134217728,
    max_input_bytes=67108864, max_source_bytes=67108864, max_submission_bytes=67108864,
    max_result_bytes=67108864, max_work_bytes=8589934592, max_nodes=1048576, max_depth=96)
key = b'disposable-source-example-key-32!'
trust = a.OperatorPolicy('demo', [a.OperatorCredential('operator', 'example-key', key, ['project'], ['approve_setup'])])


def submit(store, identity, records):
    """Save a real initial revision batch with exact zero heads."""
    return store.submit(Submission(identity, provenance, records, {r.record_id: 0 for r in records}))


def resource(kind, name, payload):
    """Create an explicit resource declaration without inventing charges or authority."""
    return ResourceRequest(kind, 'resource-' + name, 'receipt-' + name, provenance, [], [], payload)


def capture(store, operation):
    """Inspect persisted origin, then commit only its source using the verified binding digest."""
    before = store.inspect_lifecycle_source(operation, limits=limits).to_dict(limits=limits)
    return store.commit_lifecycle_source(operation, expected_binding_digest=before['binding_digest'], limits=limits)


def transition(store, original, previous, operation, action, selected_report):
    """Append descriptive intent after preparation, without current credentials or policy evaluation."""
    value = original.to_dict()
    prior = previous.to_dict()
    value.update(operation_id=operation, revision=prior['transition']['revision'] + 1,
        predecessor={'reference': {**prior['transition'], 'relationship': 'supersedes'},
                     'envelope_digest': prior['transition_digest']},
        action=action, preparation=None, expected_authority=None, report=selected_report,
        operational_reason={'code': 'model_forbidden', 'detail': 'Synthetic cancellation'} if action == 'cancel' else None)
    return store.commit_run_control(c.RunControlRequest(value), policy=None, evaluated_at=None, limits=control_limits)


with TemporaryDirectory(prefix='committed-lifecycle-source-example-') as temporary:
    root = Path(temporary) / 'runtime'
    with RecordStore.create(root, schema_version=3) as store:
        records = [project_envelope('project', 1, project, provenance), corpus_envelope('corpus', 1, corpus, provenance)]
        store.submit_typed(Submission('dossier', provenance, records, {'project': 0, 'corpus': 0}))
        submit(store, 'generic-run', [RecordEnvelope('run', 1, 'run', {'synthetic': True}, provenance,
            [RecordReference('project', 1, 'project', 'project')])])
        operating_scope = a.OperatingScope(scope)
        bound = store.prepare_operating_binding(RecordReference('project', 1, 'project_setup', 'project'),
                                               scope=operating_scope, limits=metadata)
        signed = a.sign_decision(a.OperatingDecision({'format': 'research_pipeline.operating_decision', 'version': 1,
            'authority_domain': 'demo', 'principal_id': 'operator', 'key_id': 'example-key',
            'operation_id': 'approval', 'decision_id': a.stream_id('demo', 'project'), 'revision': 1,
            'predecessor': None, 'outcome': 'approve', 'binding': bound.to_dict(),
            'judgments': {'substantive_relevance': unassessed.to_dict(), 'assignment_usability': unassessed.to_dict(),
                          'evidence_declarations': []},
            'rationale': 'Synthetic setup only', 'issued_at': now, 'valid_from': now,
            'valid_until': '2026-11-02T00:00:00.000000Z', 'scope': scope}), key=key)
        approval = store.commit_operating_decision(signed, policy=trust, evaluated_at=now, limits=metadata).to_dict()
        bound_doc = bound.to_dict()
        original = c.RunControlRequest({'format': 'research_pipeline.run_control_request', 'version': 1,
            'operation_id': 'prepare', 'run_id': 'run', 'run_revision': 1, 'revision': 1, 'predecessor': None,
            'action': 'prepare', 'actor': 'synthetic-controller', 'transitioned_at': now,
            'preparation': {'authority_domain': 'demo', 'purpose': 'setup', 'project': bound_doc['project'],
                **{k: bound_doc['dossier'][k] for k in ('initial_corpus', 'current_corpus', 'context')},
                'start_baseline': unknown, 'operating_scope': scope,
                'allocation': {'allocation_id': 'allocation', 'project_account': unknown, 'run_account': unknown},
                'previous_run': None},
            'expected_authority': {'reference': approval['decision'], 'envelope_digest': approval['envelope_digest']},
            'operational_reason': None, 'report': report})
        prepared = store.commit_run_control(original, policy=trust, evaluated_at=now, limits=control_limits)
        initial = capture(store, 'prepare').to_dict(limits=limits)
        initial_source = store.read_lifecycle_source('prepare', limits=limits)
        assert initial_source.to_dict(limits=limits)['binding']['transition']['content']['request']['report']['selection'] == []
        assert initial_source.to_dict(limits=limits)['resources']['accounts'] == []
        # Later saved work and resource facts do not retroactively modify that source.
        note_bytes = store.put_artifact(b'Later saved note; no scientific acceptance.\n')
        note = WorkProductManifest('note', 'Saved progress', 'Preserve unfinished work', ['Synthetic author'],
            None, None, None, None, [], [], None, [], [WorkProductFile('note.txt', note_bytes)], 'note.txt', [])
        store.submit_typed(Submission('save-note', provenance, [work_envelope('note', 1, note, provenance)], {'note': 0}))
        selected = deepcopy(report)
        selected['selection'] = [c.reference('note', 1, 'report_selection', 'work_product_manifest')]
        selected['declarations']['objective'] = text('Older checkpoint intent: α 𝒜 "\\\n')
        checkpoint = transition(store, original, prepared, 'checkpoint', 'checkpoint', selected)
        store.create_resource_account(resource('create_account', 'project', {'account_id': 'project-account',
            'owner_id': 'controller', 'scope': {'type': 'record', 'kind': 'project',
                'reference': c.reference('project', 1, 'resource_scope', 'project')},
            'dimensions': scope['resources']['dimensions'], 'ceiling': vector(1000),
            'policy': {'policy_id': 'example-root', 'statement': 'Synthetic ceiling'}}))
        store.allocate_resources(resource('allocate', 'run', {'allocation_id': 'allocation',
            'parent_account_id': 'project-account', 'account_id': 'run-account', 'owner_id': 'controller',
            'scope': {'type': 'record', 'kind': 'run', 'reference': c.reference('run', 1, 'resource_scope', 'run')},
            'purpose_limits': scope['resources']['purpose_limits'], 'run_policy': policy}))
        store.reserve_resources(resource('reserve', 'closeout', {'reservation_id': 'closeout', 'account_id': 'run-account',
            'owner_id': 'controller', 'purpose': 'closeout', 'maxima': vector(local_time=1), 'call_bounds': None}))
        later = deepcopy(report)
        later['declarations']['objective'] = text('Later cancellation intent remains separate')
        cancelled = transition(store, original, checkpoint, 'cancel', 'cancel', later)
        store.observe_resource_usage(resource('observe', 'completion', {'account_id': 'run-account',
            'owner_id': 'controller', 'reservation_id': 'closeout', 'event': 'authoritative_completion',
            'evidence': {'source_kind': 'controller_receipt', 'source_id': 'synthetic-closeout',
                'source_receipt_id': 'external-closeout', 'statement': 'Synthetic local time receipt'},
            'usage': vector(local_time=1), 'telemetry': {'cached_input_tokens': None, 'reasoning_output_tokens': None},
            'call_observation': None}))
        store.reconcile_resource_usage(resource('reconcile', 'settlement', {'account_id': 'run-account',
            'owner_id': 'controller', 'reservation_id': 'closeout', 'mode': 'authoritative',
            'observation_operation_id': 'resource-completion', 'previous_reconciliation_operation_id': None,
            'reason': 'Explicit synthetic settlement'}))
        delayed = capture(store, 'checkpoint').to_dict(limits=limits)
        delayed_source = store.read_lifecycle_source('checkpoint', limits=limits)
        saved = delayed_source.to_dict(limits=limits)
        assert saved['binding']['transition']['content']['request']['report'] == selected
        assert saved['control']['disposition'] == 'cancelled'
        assert len(saved['control']['pending_obligations']) == 3
        assert saved['resources']['operations'][-1]['request']['kind'] == 'reconcile'
        assert saved['binding']['preparation']['content']['request']['preparation']['allocation']['run_account'] == unknown
        assert not saved['ordinary_work_allowed'] and saved['recheck_required']
        assert prepared.to_dict()['report_state'] == 'pending_capture'
        assert store.get_submission(c.report_operation_id('checkpoint')) is None
        original_bytes = s.dumps_observation(initial_source, limits=limits)
        delayed_bytes = s.dumps_observation(delayed_source, limits=limits)
    with RecordStore.open(root) as reopened:
        assert reopened.get_lifecycle_source_operation('prepare', limits=limits).to_dict(limits=limits) == initial
        assert reopened.commit_lifecycle_source('checkpoint', expected_binding_digest=delayed['binding_digest'],
                                                limits=limits).to_dict(limits=limits) == delayed
        assert s.dumps_observation(reopened.read_lifecycle_source('prepare', limits=limits), limits=limits) == original_bytes
        assert s.dumps_observation(reopened.read_lifecycle_source('checkpoint', limits=limits), limits=limits) == delayed_bytes
        assert len(reopened.inspect_run_control('run', limits=control_limits).to_dict()['pending_obligations']) == 3
        assert reopened.head(c._identity('run-control-output-', 'checkpoint')) is None
print('Original source bytes and receipts recovered; all obligations pending. No report output or publication was produced.')
```
