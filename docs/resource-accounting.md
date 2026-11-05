# Controller-private resource accounting

Schema3 provides durable ceilings, immutable purpose allocations, reservations,
cumulative usage observations and explicit settlement in the canonical `metadata.sqlite3`. It does not execute jobs.
`RecordStore.create(root)` still creates schema2; use
`RecordStore.create(root, schema_version=3)` explicitly. Only ordinary integers 2, 3
and 4 are accepted, before reserving the absent destination. Schema1/2 resource
calls raise migration-required `StoreLayoutError` without changing metadata.

Reservations retain liability until explicit reconciliation. Bounded actual usage
is preserved even when it establishes a sticky breach that blocks further admission.
Amendments, downward corrections/refunds and automatic reallocation are unsupported.
A declared ceiling or synthetic fixture does not admit research or authenticate an
operating grant. Worker authority, task/attempt state machines, leases/fencing,
dispatch/cancellation, live provider enforcement, token estimation, exchange-rate
conversion, context construction, scientific qualification and report/current-pointer
publication remain outside this API.

## Public contracts

Import `RecordStore` from `research_pipeline.store`; import the resource values,
codecs and errors below from `research_pipeline.resources`.

| Method | Result and effects |
| --- | --- |
| `create_resource_account(request)` | Atomically creates a root project ceiling; returns `ResourceReceipt`. |
| `allocate_resources(request)` | Atomically creates a child and its immutable incoming allocation; returns `ResourceReceipt`. |
| `reserve_resources(request)` | Commits conservative maxima, without executing work; returns `ResourceReceipt`. |
| `observe_resource_usage(request)` | Appends cumulative receipt or uncertainty evidence; returns `ResourceReceipt`. |
| `reconcile_resource_usage(request)` | Explicitly settles an original reservation with evidence and a predecessor; returns `ResourceReceipt`. |
| `get_resource_operation(operation_id)` | Original receipt or `None`, using the original caller-supplied ID. |
| `inspect_resources(*, limits)` | Complete detached `ResourceSnapshot`; fails rather than truncating. |

Construct `ResourceRequest(kind, operation_id, receipt_id, provenance,
policy_references, evidence_references, payload)` with an explicit
`CreationProvenance` and JSON-compatible lists/dictionaries for the other nested
values. Alternatively use `ResourceRequest.from_dict(document)`. Both reconstruct
all fields. `to_dict()` returns isolated data. `dumps_request`/`loads_request` and
`dumps_receipt`/`loads_receipt` implement strict canonical wire conversion.
`ResourceReceipt.from_dict` and `ResourceSnapshot.from_dict` validate detached
observations; they do not grant authority or independently resolve scientific
references. `Dimension(dimension_id, kind, unit, currency, scale)` and
`ScopeReference(document)` also provide `to_dict`/`from_dict`.

The request envelope has **exactly** `format`, `version`, `kind`, `operation_id`,
`receipt_id`, `provenance`, `policy_references`, `evidence_references`, `payload`.
The format is `research_pipeline.resource_request`, version is ordinary integer
`1`, and kind is `create_account`, `allocate`, `reserve`, `observe` or `reconcile`. Provenance contains
exactly `actor`, `created_at`, `details`; timestamps follow the existing UTC
canonicalization. Details are descriptive JSON, never operating instructions.

Every ID uses the existing 1–128 character opaque ASCII identifier syntax.
Canonical requests are at most 65,536 ASCII bytes and 16 nested containers;
policy statements are nonempty and at most 4,096 characters. Each reference list
has at most 32 entries. Duplicate, unknown or omitted fields, duplicate dimensions,
nonfinite values, surrogate Unicode, coercions and bool-as-integer are rejected.
Reference arrays retain declared order; dimensions and vectors sort by dimension ID.
All supplied numeric quantities are ordinary integers in `[0, B]`, `B = 2**63 - 1`.
Usage can also be explicitly null. Derived aggregate values use exact decimal strings.

A dimension has exactly `dimension_id`, `kind`, `unit`, `currency`, `scale`.
There are 7–16 dimensions, with exactly one each of:

| Kind | Unit |
| --- | --- |
| `model_input_tokens`, `model_output_tokens` | `token` |
| `model_calls`, `tool_calls` | `call` |
| `local_time` | `nanosecond` |
| `local_compute` | `cpu_nanosecond` |
| `local_storage` | `byte` |

These seven have `currency=null`, `scale=1`. Additional dimensions must have kind
`monetary`, unit `currency_quantum`, explicit three-uppercase-letter currency and
ordinary scale `1..10**9`. Quantity `q` represents `q/scale` declared currency units.
Aliases or multiple scales for the same currency are rejected. A currency absent
from the root is untracked, not zero expenditure. No conversion is performed.
A vector is a list of `{ "dimension_id": ID, "quantity": INTEGER }` entries with
**every root dimension exactly once**, including zeros. Descendants cannot change
or omit units. Model input/output/calls are separate dimensions; cache/reasoning telemetry is not an additional charge.

Scope is one of these closed shapes:

- `{"type":"record", "kind":SCOPE_KIND, "reference":EXACT_REFERENCE}`
- `{"type":"controller", "kind":SCOPE_KIND, "stable_identity":ID}`

Scope kinds are `project`, `run`, `branch`, `task`, `attempt`. Project/task require
exact records of kind `project`/`task_specification`. Run/branch/attempt may use
matching exact records or controller identities. Exact references contain all
four `RecordReference` fields: `record_id`, `revision`, `relationship`,
`target_kind`; target kind must be non-null. Policy/evidence references must have
roles `resource_policy`/`resource_evidence`. They resolve exact scientific revisions
and cannot directly register artifacts. Empty reference lists use the inline
policy declaration. Supporting artifact evidence belongs on referenced records.

Payloads are closed and complete:

| Kind | Exact payload fields |
| --- | --- |
| `create_account` | `account_id`, `owner_id`, `scope`, `dimensions`, `ceiling`, `policy` |
| `allocate` | `allocation_id`, `parent_account_id`, `account_id`, `owner_id`, `scope`, `purpose_limits`, `run_policy` |
| `reserve` | `reservation_id`, `account_id`, `owner_id`, `purpose`, `maxima`, `call_bounds` |
| `observe` | `account_id`, `owner_id`, `reservation_id`, `event`, `evidence`, `usage`, `telemetry`, `call_observation` |
| `reconcile` | `account_id`, `owner_id`, `reservation_id`, `mode`, `observation_operation_id`, `previous_reconciliation_operation_id`, `reason` |

Root policy contains exactly `policy_id`, `statement`. Purpose limits contain
exactly `ordinary`, `verification`, `handoff`, `closeout`, each a complete vector.
Run policy contains exactly `policy_id`, `statement`, `verification_minimum`,
`handoff_minimum`, `closeout_minimum`, **`handoff_call_bounds`**,
`context_capacity_tokens`, `per_call_output_tokens`, `monetary_services`.
It is mandatory for a run allocation and explicitly `null` for every non-run
allocation. Descendants inherit it unchanged. Each monetary service entry contains
`dimension_id`, `service_id`, `mode="monitored_target"`, `statement`; exactly one
entry is required per monetary dimension. This is a monitored declaration, not a
claim that an external service enforces a hard cost limit.

Receipt fields are exactly `format="research_pipeline.resource_receipt"`,
`version=1`, `operation_id`, `receipt_id`, `sequence`, `request_fingerprint`, `kind`,
`account_id`, `allocation_id`, `reservation_id`, `committed_at`, `provenance`,
`scientific_watermark_event_id`. Inapplicable allocation/reservation IDs are
explicitly null. The watermark identifies the latest scientific audit event
visible during admission; resource operations never insert scientific events.
Observation/reconciliation receipts identify the original account and reservation;
their `allocation_id` is null. Their operation IDs are the observation/settlement
identities; there is no extra generated identity.

## Hierarchy and protected capacity

Allowed edges are project→run, run→branch/task, branch→task, task→attempt.
A root declares an owner that every descendant allocation/reservation must echo.
Each stable scope can have only one account, independently of record revision.
No reparenting, cycles, cross-owner delegation, amendments or automatic increases
are supported. These are trusted controller declarations, not human authentication.

For a nonproject account and purpose, effective commitment `U` is the sum of
its direct reservation charges plus `max(child allocation, child U)` for each
immediate child, componentwise. At the project, sum those child contributions
across purposes. This retains allocation commitments without charging contained
descendant usage twice; excess propagates to every ancestor. Local availability
is ceiling minus effective commitment and can be negative after an overrun.
Allocations are never refunded or amended, even when every reservation settles.
Creating another attempt requires new parent allocation capacity; replacement
work needs independently available capacity.

The run's verification pool must meet its complete configurable minimum (at least
one positive entry); no verification fraction is recommended. The handoff minimum
requires positive model calls/input/output, local time and local storage. Closeout
requires positive local time and storage. Only the run owns closeout capacity;
all child closeout vectors are zero. Each attempt receives its own entire handoff
minimum; branch/task allocations carry those quantities within parent budgets.

Ordinary and verification reservations belong only to attempts, handoff to its
owning attempt, and closeout to the run. Ordinary/verification admission also
requires the attempt's entire handoff minimum and the run's entire closeout
minimum to remain free. Prior handoff/closeout commitments can block more ordinary
work even while ordinary tokens remain. Protected purposes never lend capacity.

## Explicit handoff provisioning and actual reservation bounds

Both policy `handoff_call_bounds` and non-null reservation `call_bounds` have exactly
`max_input_tokens_per_call` (ordinary integer `0..B`) and
`max_output_tokens_per_call` (ordinary integer `1..B`). They cannot be omitted,
coerced or inferred from token totals or call count.

For handoff provisioning, resolve `N`, `I`, `O` from the minimum vector's validated
**kinds** model calls/input/output; let `i`, `o` be the declared provisioning bounds,
`C` context capacity and `P` per-call output. Require:

- `1 <= N, I, O <= B`, `0 <= i <= B`, `1 <= o <= B`;
- `1 <= P <= C <= B`, `i + o <= C`, `o <= P`;
- `N*i <= B`, `N*o <= B`, `I >= N*i`, `O >= N*o`.

All arithmetic is exact Python integer arithmetic, with no division, rounding,
clipping, floating point or SQLite quantity aggregation. Equality and surplus
allowances are valid. For `N=2, i=3, o=5, C=8, P=5`, input needs at least 6 and
output at least 10. Zero per-call input is valid while the cumulative handoff
input allowance must still be positive. Context and output constraints describe
individual calls, not cumulative renewable budgets. Provisioning bounds do not
consume capacity separately from allocations/reservations.

Each actual reservation with positive model calls supplies its **own** bounds and
passes those multiplication/context/output checks against its own maxima and
inherited `C/P`. Its bounds can differ from the policy provisioning envelope;
that envelope is not an extra reservation ceiling or a default. Zero-model-call
reservations require null `call_bounds` and zero input/output maxima. Every
reservation needs at least one positive maximum. Admission arithmetic expressions
remain bounded by `B`; actual usage aggregates follow the separate exact
representation below. Operation sequence exhaustion is a metadata admission limit.

## Cumulative usage and explicit settlement

An observation's `evidence` has exactly `source_kind`, `source_id`,
`source_receipt_id`, `statement`. IDs use the identifier syntax above; statements
are nonempty and at most 4,096 characters. Valid source/event combinations are:

| source_kind | event | source_receipt_id |
| --- | --- | --- |
| `controller_receipt` | `partial_usage`, `authoritative_completion` | Required external identifier |
| `controller_status` | `process_loss`, `acknowledgment_loss`, `timeout`, `cancellation`, `lease_expiry`, `provider_error` | null |
| `worker_narrative` | `worker_narrative` | null |

These are trusted controller declarations, **not authenticated transport or worker
authority**. A `(source_id, source_receipt_id)` pair belongs to one observation
operation and one original reservation across the entire ledger. Aliasing it under
another operation conflicts, even for otherwise identical content: retry the saved
original operation. This external source receipt ID is distinct from the ledger
result's `receipt_id`. Arbitrary provenance details cannot authorize settlement.
Policy/evidence references remain the exact envelope references with scientific
watermark validation; observations register no new artifacts or submissions.

`usage` is a complete dimension-sorted vector whose quantities are integers `0..B`
or null. Null means unavailable, never measured zero. Non-receipt observations
require every quantity null. A partial receipt needs at least one numeric quantity;
**authoritative completion declares execution and billing complete for every
tracked dimension** and requires every quantity numeric. Receipts are cumulative
usage for the original reservation, never deltas. The latest known lower bound is
retained when a later quantity is null; numeric decreases conflict. Known zero
model calls cannot accompany positive model tokens, including across receipts.
Exceeding admission maxima does not invalidate a bounded receipt.

`telemetry` has exactly `cached_input_tokens` and `reasoning_output_tokens`, each
null or an integer `0..B`. A numeric category requires the corresponding numeric
input/output total in that observation and cannot exceed it. These subsets never
add charges. `call_observation` is null or exactly `call_id`, `input_tokens`,
`output_tokens`; token values are integers `0..B`. It requires explicit numeric
model calls >=1 and input/output totals containing the sample. One sample describes
one call; repeated samples remain evidence without adding usage. Samples permit
exact reservation input/output, run output and input+output context checks.
Compliant aggregate totals cannot rule out an individual peak; totals exceeding
the observed call count times a bound conclusively prove an invocation violation.
Non-receipt observations require both telemetry values and `call_observation` null.

For either partial usage or authoritative completion, a controller receipt with
an explicitly numeric, positive current `model_calls` count `N` also supports
cumulative proofs. With retained numeric input/output totals `I`/`O`, reservation
per-call bounds `i`/`o`, inherited run output bound `P` and context capacity `C`,
the violations are independently `I > N*i`, `O > N*o`, `O > N*P`, and
`I+O > N*C`. Absent reservation call bounds give zero reservation invocation
allowances. These are necessary conditions for compliant calls, not measured
peaks or renewable budgets. A numeric count alone does not finalize execution or
release liability.

A null current count cannot use an earlier receipt's count or the reservation's
maximum: neither bounds the call population underlying newer tokens. Retained
token totals are lower bounds; unknown token quantities skip their individual
checks. For context only, a missing token quantity contributes zero as a mathematical
lower bound without becoming measured zero in usage. Known input alone exceeding
`N*C` therefore proves a context breach; two unknown token quantities prove none.
Status, uncertainty and narrative observations establish no new invocation facts.
All derived products and sums use exact Python integers, even above the input
quantity bound `B`; they never pass through the bounded-input validator and add
no charges.

Reconciliation echoes the original `account_id`, `owner_id`, `reservation_id`;
purpose, dimensions and ancestry always come from that original declaration.
`mode` is `authoritative` or `conservative`. `reason` is a required bounded statement;
the envelope supplies actor/time attribution. `previous_reconciliation_operation_id`
must equal the latest settlement for that reservation, or null initially.
Authoritative mode references the most recent controller-receipt observation;
it must be `authoritative_completion` and contain all previously known usage.
Conservative mode references the latest observation of any kind, or null only
when there are no observations, and explains why uncertain execution/billing is
charged conservatively. It accepts no caller-selected lower charge.

For each original maximum `M` and known lower bound `K` (zero **internally only**
where knowledge is absent):

| State | charged_total | known_spent | remaining_reserved | conservative_excess | actual_usage |
| --- | --- | --- | --- | --- | --- |
| unresolved (initial) | max(M,K) | K | max(M-K,0) | 0 | null |
| conservative | max(M,K) | K | 0 | max(M,K)-K | null |
| authoritative | K | K | 0 | 0 | K |

Thus `M=10`, partial `K=4` means 4 spent plus 6 reserved; authoritative final
`K=6` followed by explicit reconciliation means 6 spent and zero reserved. Parent
delegation does not change. A completion observation alone retains liability, as
do timeout, cancellation, expiry, error and narrative observations.

Newer authoritative completion evidence can explicitly refine a conservative
settlement, releasing conservative excess without erasing history or breaches.
A conservative charge is not measured usage or proof execution stopped. Redundant
new identities for an unchanged terminal settlement conflict; exact retries return
the original result. Later bounded receipts remain recordable: in conservative
state they raise knowledge and, if needed, charges without releasing capacity.
An increase after authoritative settlement returns the reservation to unresolved
accounting with `max(M,K)` liability and a sticky `post_settlement_usage` breach.
Uncertainty alone does not undo authoritative settlement. Downward corrections,
refunds and policy amendments are explicitly unsupported.

## Sticky breaches and exact aggregate arithmetic

Every supplied quantity is bounded by `B`; aggregates never pass through that input
validator. Python integers preserve exact sums with no SQLite SUM, floats, clipping,
wrapping or rounding. Derived quantities are canonical decimal strings bounded by
`B*B`, with availability down to `-B*B`: at most `B` operations each introduce
at most `B` per-entity quantity per dimension. Sequence exhaustion is a separate
metadata admission limit, never a reason to discard an authentic bounded bill as
aggregate arithmetic overflow.

Replay appends the first fact per account/purpose/dimension/reason. Each fact has
exactly `trigger_operation_id`, `account_id`, `purpose`, `dimension_id`, `reason`,
`observed`, `limit`; numbers are decimal strings. Reasons are `reservation_maximum`,
`per_call_bound`, `run_output_bound`, `context_bound`, `ceiling_excess`,
`aggregate_known_overflow`, `post_settlement_usage`. Sampled invocation facts keep
individual-call values and limits. Cumulative invocation facts store the exact
observed total (or context lower-bound sum) and the exact `N`-times-bound limit;
the triggering request supplies `N`. `context_bound` always uses the model input
dimension. Sample facts are processed before cumulative proofs within an observation,
preserving the sample's diagnostics when both prove the same reason. Facts retain
their first chronological trigger; later evidence remains in operations, and
settlement never clears them.

A breach commits together with its observation and **blocks all new allocations
and reservations under that project**, including sibling runs and protected purposes.
This deliberately conservative boundary does not affect unrelated projects. No
settlement clears a breach or grants a recovery override. Exact retries, inspection,
backup, observation and reconciliation remain available. Subsequent admissions
raise `ResourceCapacityError` naming the blocked project; the observation that
establishes the breach does not roll back. Replay validates admission at each
historical sequence, so a later breach does not invalidate earlier reservations.

## Inspection and recovery

`ResourceInspectionLimits(max_accounts, max_operations, max_metadata_bytes)` uses
positive ordinary integers. Counts and serialized sizes are preflighted, and the
complete result must fit; no partial snapshot is returned. Inspection captures
schema identity, ordered administrative history, accounts, allocations,
reservations, ordered requests/receipts, resource sequence and balances in one
read transaction. `snapshot_id` is the SHA-256 of the complete canonical document
without that field. Snapshots contain no capture timestamp and expose detached data.

The complete version-2 snapshot has exactly `format="research_pipeline.resource_snapshot"`,
`version=2`, actual `schema_version=3` or `4`, `schema_identity`, `resource_sequence`,
`administrative_history`, `operations`, `accounts`, `allocations`, `reservations`,
`reservation_usage`, `breaches`, `balances`, `snapshot_id`. Declarations retain their
original shapes. Operations retain every original request and receipt in sequence;
earlier observations, uncertainties and settlements are never collapsed away.

`reservation_usage` sorts by reservation ID. Each row has exactly `reservation_id`,
`status` (`unresolved`, `conservative`, `authoritative`),
`latest_observation_operation_id`, `latest_receipt_operation_id`,
`latest_reconciliation_operation_id`, `dimensions`. Absent pointers are null.
Each dimension row has exactly `dimension_id`, `observed_quantity` (decimal string
or null), `known_spent`, `conservative_excess`, `remaining_reserved`, `charged_total`,
`actual_usage` (decimal string only in authoritative state; otherwise null).

Each balance row has exactly `account_id`, `purpose`, `dimensions`,
`unresolved_reservation_ids`, `usage_complete`, `breach`, `admission_blocked`.
Project uses purpose `total`; other accounts have each of the four purposes.
Each dimension row has exactly `dimension_id`, `ceiling`, `delegated_to_children`,
`child_overrun`, `direct_known_spent`, `direct_conservative_excess`,
`direct_reserved`, `known_spent`, `conservative_excess`, `subtree_reserved`,
`available_for_local_use`, `actual_usage`, `unknown_reservation_ids`.
Quantities are canonical decimal strings (no leading zeros); availability is signed.
`actual_usage` is null unless every relevant reservation is authoritative. Empty
subtrees have exact zero measured/final usage. `known_spent`, `conservative_excess`
and `subtree_reserved` are subtree sums; `direct_reserved` is remaining direct
liability. `unknown_reservation_ids` identifies nonauthoritative final usage for
that dimension. `unresolved_reservation_ids` is the union of those unknown final
usage IDs, including conservative settlements, and `usage_complete` means it is empty.
Local availability is exactly:

```
ceiling - delegated_to_children - child_overrun
        - direct_known_spent - direct_conservative_excess - direct_reserved
```

`breach` identifies local recorded facts; `admission_blocked` reflects the whole
project's sticky restriction. Snapshot validation replays all operations to
reconstruct usage, pointers, balances, breaches and gates, independently of the
supplied projections and hash. It rejects inconsistent or noncanonical projections.

`ResourceValidationError`, `ResourceConflictError`, `ResourceCapacityError`,
`ResourceIntegrityError`, and `ResourceInspectionLimitError` distinguish malformed
input, reused immutable identity, insufficient capacity, invalid persisted history,
and insufficient inspection budgets. Existing closed-handle, SQLite database and
lock/busy errors remain store errors. Live-open invariant failures map to
`StoreLayoutError`; immutable backup failures map to `BackupIntegrityError`.

Admission uses the existing `BEGIN IMMEDIATE` transaction. An exact operation-ID
retry returns its original committed receipt **before** current reference/capacity
checks. Changing any canonical field, including either provisioning bound,
conflicts. Reused entity or receipt IDs under another operation also conflict.
Keep the complete original request and caller-supplied IDs before execution.

A failure before COMMIT with successful rollback differs from lost acknowledgment
after COMMIT. Successful commit is outside rollback handling; close/process loss
cannot erase the commitment. Reopen, call `get_resource_operation(original_id)`,
and compare the saved request fingerprint/receipt. After proven rollback the same
accounting request can be retried under the same ID. Never resolve uncertainty by
minting another ID or automatically replaying external work. Absence of an
accounting receipt alone is not proof that external execution never happened.

Live open validates chronological resource admissions after legitimate journal
recovery, in one operational read transaction. Inspection and immutable backups
use the same invariant checks, including complete policy bounds, exact normalized
projections, fingerprints, scientific reference watermarks and historical capacity.
This establishes internal consistency, not authenticity against a hostile owner.

[Backups](backups.md) support exact schema3 restoration with complete metadata bytes,
including every outstanding liability. Explicit attributed 2→3 migration validates
the immutable source before reserving an absent runtime, preserves all scientific
SQL values and prior 1→2 history, and appends the ordered 2→3 administrative row.
Direct 1→3 and in-place migration are rejected. Resource record links introduce no
artifact registrations, so exact historical scientific artifact closure remains
unchanged. Scientific outgoing-closure snapshots do not advance on resource writes
and are not complete runtime backups.

## Runnable synthetic usage, recovery and migration example

Run this self-contained Python block with `PYTHONPATH=implementation/src` from the
repository root. All fixtures are synthetic; no provider or research job is used.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordEnvelope, Submission
from research_pipeline.store import RecordStore
from research_pipeline.resources import ResourceRequest, ResourceInspectionLimits, ResourceCapacityError
from research_pipeline.backup import create_backup, restore_backup

attribution = CreationProvenance("synthetic-controller", "2026-11-01T00:00:00Z", {})
units = {"model_input_tokens": "token", "model_output_tokens": "token",
         "model_calls": "call", "tool_calls": "call", "local_time": "nanosecond",
         "local_compute": "cpu_nanosecond", "local_storage": "byte"}
dimensions = [{"dimension_id": kind, "kind": kind, "unit": unit,
               "currency": None, "scale": 1} for kind, unit in units.items()]

def vector(default=0, **values):
    """Declare all dimensions explicitly, including zero allowances."""
    return [{"dimension_id": kind, "quantity": values.get(kind, default)} for kind in units]

def operation(kind, identity, payload):
    """Construct one saved accounting request with stable caller-supplied IDs."""
    return ResourceRequest(kind, "op_" + identity, "receipt_" + identity,
                           attribution, [], [], payload)

def scope(kind):
    """Use exact scientific scopes where required and explicit controller identities elsewhere."""
    if kind in ("project", "task"):
        return {"type": "record", "kind": kind, "reference": {
            "record_id": kind, "revision": 1, "relationship": "resource_scope",
            "target_kind": "project" if kind == "project" else "task_specification"}}
    return {"type": "controller", "kind": kind, "stable_identity": kind}

def usage(identity, event, quantities, reservation_id="work"):
    """Save finite cumulative evidence; operational uncertainty has explicitly null quantities."""
    receipt = event in ("partial_usage", "authoritative_completion")
    return operation("observe", identity, {"account_id": "attempt", "owner_id": "owner",
        "reservation_id": reservation_id, "event": event,
        "evidence": {"source_kind": "controller_receipt" if receipt else "controller_status",
                     "source_id": "synthetic-source", "source_receipt_id": identity if receipt else None,
                     "statement": "Synthetic execution and billing evidence only"},
        "usage": quantities, "telemetry": {"cached_input_tokens": None, "reasoning_output_tokens": None},
        "call_observation": None})

def settle(identity, mode, observation_id, reservation_id="work", previous=None):
    """Declare explicit settlement evidence and predecessor, never caller-selected charges."""
    return operation("reconcile", identity, {"account_id": "attempt", "owner_id": "owner",
        "reservation_id": reservation_id, "mode": mode, "observation_operation_id": observation_id,
        "previous_reconciliation_operation_id": previous,
        "reason": "Synthetic explicit settlement; conservative mode retains uncertain billing"})

def tool_usage(store, reservation_id="work"):
    """Inspect a single original reservation without treating null actual usage as zero."""
    snapshot = store.inspect_resources(limits=inspection_limits).to_dict()
    row = next(r for r in snapshot["reservation_usage"] if r["reservation_id"] == reservation_id)
    return next(d for d in row["dimensions"] if d["dimension_id"] == "tool_calls")

run_policy = {"policy_id": "policy", "statement": "Synthetic conservative provisioning",
    "verification_minimum": vector(tool_calls=1),
    "handoff_minimum": vector(model_calls=2, model_input_tokens=6, model_output_tokens=10,
                              local_time=1, local_storage=1),
    "closeout_minimum": vector(local_time=1, local_storage=1),
    "handoff_call_bounds": {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5},
    "context_capacity_tokens": 8, "per_call_output_tokens": 5, "monetary_services": []}
inspection_limits = ResourceInspectionLimits(100, 100, 1000000)

with TemporaryDirectory(prefix="synthetic-resources-") as temporary:
    parent = Path(temporary)
    runtime = parent / "runtime"
    with RecordStore.create(runtime, schema_version=3) as store:
        project = RecordEnvelope("project", 1, "project", {"synthetic": True}, attribution)
        task = RecordEnvelope("task", 1, "task_specification", {"synthetic": True}, attribution,
                              operational_status="proposed")
        store.submit(Submission("scopes", attribution, [project, task], {"project": 0, "task": 0}))
        root = operation("create_account", "project", {"account_id": "project", "owner_id": "owner",
            "scope": scope("project"), "dimensions": dimensions, "ceiling": vector(100),
            "policy": {"policy_id": "root", "statement": "Synthetic ceiling only"}})
        store.create_resource_account(root)
        for kind, parent_id in (("run", "project"), ("task", "run"), ("attempt", "task")):
            pools = {"ordinary": vector(10), "verification": vector(5),
                     "handoff": vector(10), "closeout": vector(2 if kind == "run" else 0)}
            store.allocate_resources(operation("allocate", kind, {
                "allocation_id": "allocation_" + kind, "parent_account_id": parent_id,
                "account_id": kind, "owner_id": "owner", "scope": scope(kind),
                "purpose_limits": pools, "run_policy": run_policy if kind == "run" else None}))
        work = operation("reserve", "work", {"reservation_id": "work", "account_id": "attempt",
            "owner_id": "owner", "purpose": "ordinary", "maxima": vector(tool_calls=10), "call_bounds": None})
        receipt = store.reserve_resources(work)
        assert store.reserve_resources(work) == receipt
        partial = usage("partial", "partial_usage", vector(None, tool_calls=4))
        partial_result = store.observe_resource_usage(partial)
        store.observe_resource_usage(usage("timeout", "timeout", vector(None)))
        assert tool_usage(store)["known_spent"] == "4"
        assert tool_usage(store)["remaining_reserved"] == "6"
        # Original-ID inspection resolves a saved accounting result; never replay external work.
        assert store.get_resource_operation(partial.operation_id) == partial_result
        assert partial_result.to_dict()["request_fingerprint"] == partial.fingerprint
        assert store.observe_resource_usage(partial) == partial_result
        store.observe_resource_usage(usage("complete", "authoritative_completion", vector(tool_calls=6)))
        assert tool_usage(store)["remaining_reserved"] == "4"
        settlement = settle("settled", "authoritative", "op_complete")
        store.reconcile_resource_usage(settlement)
        assert tool_usage(store)["actual_usage"] == "6"
        assert tool_usage(store)["remaining_reserved"] == "0"
        uncertain = operation("reserve", "uncertain", {"reservation_id": "uncertain", "account_id": "attempt",
            "owner_id": "owner", "purpose": "ordinary", "maxima": vector(tool_calls=3), "call_bounds": None})
        store.reserve_resources(uncertain)
        store.observe_resource_usage(usage("lost", "acknowledgment_loss", vector(None), "uncertain"))
        store.reconcile_resource_usage(settle("conservative", "conservative", "op_lost", "uncertain"))
        assert tool_usage(store, "uncertain")["conservative_excess"] == "3"
        assert tool_usage(store, "uncertain")["actual_usage"] is None
        late = usage("late", "partial_usage", vector(None, tool_calls=11))
        late_result = store.observe_resource_usage(late)
        assert store.observe_resource_usage(late) == late_result
        refused = operation("reserve", "refused", {"reservation_id": "refused", "account_id": "attempt",
            "owner_id": "owner", "purpose": "verification", "maxima": vector(tool_calls=1), "call_bounds": None})
        try:
            store.reserve_resources(refused)
        except ResourceCapacityError:
            pass
        else:
            raise AssertionError("sticky project breach must refuse admission")
        observed = store.inspect_resources(limits=inspection_limits)
        assert observed.to_dict()["breaches"]
        assert any(not b["usage_complete"] for b in observed.to_dict()["balances"])
        create_backup(store, parent / "backup")
    with RecordStore.open(runtime) as reopened:
        assert reopened.get_resource_operation(work.operation_id) == receipt
        assert reopened.get_resource_operation(partial.operation_id) == partial_result
        assert reopened.get_resource_operation(late.operation_id) == late_result
        assert reopened.inspect_resources(limits=inspection_limits) == observed
    with restore_backup(parent / "backup", parent / "restored") as restored:
        assert restored.inspect_resources(limits=inspection_limits) == observed
        assert restored.reserve_resources(work) == receipt
        assert restored.observe_resource_usage(late) == late_result
        assert (parent / "restored/metadata.sqlite3").read_bytes() == (parent / "backup/snapshot.sqlite3").read_bytes()
        # Late usage and conservative uncertainty both survive exact restoration.
    with RecordStore.create(parent / "schema2") as old:
        exported = create_backup(old, parent / "schema2-backup")
        assert exported.schema_version == 2
    with restore_backup(parent / "schema2-backup", parent / "migrated", target_schema=3,
                        migration_provenance=attribution) as migrated:
        history = migrated.inspect_resources(limits=inspection_limits).to_dict()["administrative_history"]
        assert [(h["source_schema"], h["target_schema"]) for h in history] == [(2, 3)]
```

Focused tests exercise real independent-handle/process races, authorizer-denied
transactions, process loss, actual page-spill hot journals, rehashed invalid
backups and this exact block. Writer-local checks are advisory; controller validation
and Reviewer verification determine acceptance. No controller or scientific
acceptance is asserted by this guide.

## Approved operating declarations

[Authenticated operating scopes](operating-authority.md) reuse these dimensions,
vectors, protected minima and call-envelope arithmetic for signed declarations.
They do not allocate or reserve capacity, reset spent usage, release reservations
or erase uncertain liabilities. Approval, denial and revocation leave every resource
table unchanged. Monetary service declarations retain only `monitored_target`.
Actual authenticated run/resource admission and enforced execution remain later work.

## Committed lifecycle source observations

[Lifecycle source capture](committed-lifecycle-sources.md) uses the same complete
ledger replay/accounting algorithms inside its scientific/control write transaction,
with independent preflighted row/reference/byte/work limits. Its saved project
projection retains sibling liabilities and original receipt sequence gaps while
excluding unrelated-project payloads. Reading an older source verifies saved relevant
original requests, receipts and immutable rows through its original sequence, without
recapturing today's balances. Fresh source time must equal or exceed the maximum
of captured scientific/control factual dates and every receipt date in the complete
resource prefix, including omitted unrelated operations. Resource clocks are
independent; an earlier sequence can carry a later timestamp. Fresh violations
raise LifecycleSourceStateError before source artifact placement or metadata.
Verified reads enforce the saved complete prefix with LifecycleSourceIntegrityError;
later operations are irrelevant. Detached validation enforces only retained facts
with LifecycleSourceValidationError: gaps and complete-snapshot identity establish
no omitted receipt dates offline and disclose no private payload. Equality succeeds,
and metadata-only exact retries return original fixed dates without current-clock
checks. Capture neither reserves nor settles resources and
cannot turn preparation's unknown account declarations into an earlier known fact.

Schemas 4, 5 and 6 retain the complete schema-3 resource contract alongside [claim-use freshness](claim-use-freshness.md). New resource snapshots identify their actual schema and registry-derived `_schema_identity(version)`; historical schema-3/4/5 snapshots remain accepted unchanged. Administrative history validation uses that actual schema, including valid consecutive suffixes through 3→4→5→6. Report/control/lifecycle-source resource capture remains available on all four resource-capable versions.
