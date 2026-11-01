# Controller-private resource accounting

Schema3 provides durable ceilings, immutable purpose allocations and conservative
reservations in the canonical `metadata.sqlite3`. It does not execute jobs.
`RecordStore.create(root)` still creates schema2; use
`RecordStore.create(root, schema_version=3)` explicitly. Only ordinary integers 2
and 3 are accepted, before reserving the absent destination. Schema1/2 resource
calls raise migration-required `StoreLayoutError` without changing metadata.

This is the reservation milestone. Every reservation remains an outstanding
liability. Usage observations, partial usage, settlement, reconciliation, release,
amendments, actual-overrun receipts and admission-blocking breaches are unavailable.
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
`1`, and kind is `create_account`, `allocate` or `reserve`. Provenance contains
exactly `actor`, `created_at`, `details`; timestamps follow the existing UTC
canonicalization. Details are descriptive JSON, never operating instructions.

Every ID uses the existing 1–128 character opaque ASCII identifier syntax.
Canonical requests are at most 65,536 ASCII bytes and 16 nested containers;
policy statements are nonempty and at most 4,096 characters. Each reference list
has at most 32 entries. Duplicate, unknown or omitted fields, duplicate dimensions,
nonfinite values, surrogate Unicode, coercions and bool-as-integer are rejected.
Reference arrays retain declared order; dimensions and vectors sort by dimension ID.
All accounting quantities are ordinary integers in `[0, B]`, `B = 2**63 - 1`.

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
or omit units. Model input/output/calls are separate dimensions; any eventual
cache/reasoning telemetry is not an additional charge.

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

## Hierarchy and protected capacity

Allowed edges are project→run, run→branch/task, branch→task, task→attempt.
A root declares an owner that every descendant allocation/reservation must echo.
Each stable scope can have only one account, independently of record revision.
No reparenting, cycles, cross-owner delegation, amendments or automatic increases
are supported. These are trusted controller declarations, not human authentication.

A project ceiling covers the sum of its complete run allocations. Below a run,
each purpose covers immediate child allocations plus direct reservations.
Descendant reservations are already inside their allocation and are **not added
again** to the parent's charge. Allocations remain committed. Creating another
attempt cannot reset capacity or replace an outstanding liability for free.

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
reservation needs at least one positive maximum. All new arithmetic expressions
and sequences are bounded by `B`; overflow rejects before insertion.

## Inspection and recovery

`ResourceInspectionLimits(max_accounts, max_operations, max_metadata_bytes)` uses
positive ordinary integers. Counts and serialized sizes are preflighted, and the
complete result must fit; no partial snapshot is returned. Inspection captures
schema identity, ordered administrative history, accounts, allocations,
reservations, ordered requests/receipts, resource sequence and balances in one
read transaction. `snapshot_id` is the SHA-256 of the complete canonical document
without that field. Snapshots contain no capture timestamp and expose detached data.

Each account/purpose balance contains per-dimension canonical decimal strings for
`ceiling`, `delegated_to_children`, `direct_reserved`, `subtree_reserved`,
`known_spent`, `available_for_local_use`. Project uses purpose `total` for remaining
allocation capacity. Local availability subtracts immediate delegations and direct
reservations; subtree totals are informative and are not subtracted twice.
`unresolved_reservation_ids`, `usage_complete`, `breach` accompany each balance.
The known spent lower bound is `"0"`; actual usage is `null` wherever reservations
remain unresolved, otherwise `"0"`. It is not measured zero usage. Valid current
states have `breach=false`; future actual-overrun recording is unavailable.

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

## Runnable synthetic reservation and migration example

Run this self-contained Python block with `PYTHONPATH=implementation/src` from the
repository root. All fixtures are synthetic; no provider or research job is used.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from research_pipeline.domain import CreationProvenance, RecordEnvelope, Submission
from research_pipeline.store import RecordStore
from research_pipeline.resources import ResourceRequest, ResourceInspectionLimits
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
            "owner_id": "owner", "purpose": "ordinary", "maxima": vector(tool_calls=1), "call_bounds": None})
        receipt = store.reserve_resources(work)
        assert store.reserve_resources(work) == receipt
        observed = store.inspect_resources(limits=inspection_limits)
        assert any(not b["usage_complete"] for b in observed.to_dict()["balances"])
        create_backup(store, parent / "backup")
    with RecordStore.open(runtime) as reopened:
        assert reopened.get_resource_operation(work.operation_id) == receipt
    with restore_backup(parent / "backup", parent / "restored") as restored:
        assert restored.inspect_resources(limits=inspection_limits) == observed
        assert restored.reserve_resources(work) == receipt
        # The reservation is still a liability; there is no settlement/release API.
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
