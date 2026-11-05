# Committed run-report observations

`RecordStore.commit_report(ReportRequest(document))` captures a bounded, exact,
dated state observation and commits its source plus deterministic `report.md` and
`continuation.json` artifacts. It returns `ReportCommitResult`, meaning **source
committed**. It makes no filesystem publication claim. Reports work on schema 2
(resource accounting explicitly unavailable) and schemas 3–7. New captures identify the actual schema; older saved
documents retain exact bytes and interpretation. Schema 1 requires an
explicit existing migration. Schema identities, default creation at 2, backup
formats, generic/typed admission and previous readable formats remain unchanged.

Import the values and codecs from `research_pipeline.reports`. Each value accepts
a complete ordinary dictionary, has `from_dict`/`to_dict`, and retains detached
canonical JSON. The pairs `dumps_request`/`loads_request`,
`dumps_observation`/`loads_observation` and `dumps_result`/`loads_result` strictly
validate at public consumption boundaries. JSON has sorted keys, meaningful array
order, finite ordinary scalar values, valid Unicode and no duplicate keys.
Unknown/missing fields, coercions, boolean integers, subclass lookalikes and forged
retained state fail. Recomputing a hash does not bypass semantic checks. A detached
observation establishes internal consistency, not authentication.

## Exact version-1 request

The only request fields are:

| Field | Contract |
| --- | --- |
| `format`, `version` | `research_pipeline.report_request`, ordinary integer `1` |
| `operation_id` | Existing 1–128 ASCII identifier; also the submission ID |
| `report_revision` | Positive integer; expected manifest head is revision minus one |
| `provenance` | Exactly `actor`, `created_at`, `details`, using existing `CreationProvenance.to_dict()` |
| `authors` | Nonempty ordered list of at most 32 nonblank strings |
| `project`, `run` | Complete exact references with roles/kinds `project/project`, `run/run` |
| `context` | Exact `context/research_context` reference or explicit unavailable value |
| `selection` | Ordered exact `report_selection` references with non-null target kinds; at most 128; no two entries with the same identity |
| `start_baseline` | Exact `start_baseline/work_product_manifest` reference or explicit unavailable value |
| `declarations` | Complete object below |
| `limits` | Complete explicit budget object below |

Every exact reference has exactly `record_id`, `revision`, `relationship` and
`target_kind`. Head selectors are unavailable. All unions use either the stated
exact reference/object/list, or `DeclaredText` wire form
`{"value": null, "unknown_reason": "Nonblank reason"}`. There is no implicit null
or empty-string sentinel. Provenance timestamps retain the existing UTC normalization
to six fractional digits; the normalized request is checked again against the
canonical byte bound. Omitted `details` is invalid even though generic provenance
decoding permits it. Available baselines must be earlier reports generated
by this API for the same stable project/run, designated by the caller as the
saved start observation. Arbitrary historical checkpoint formats are unsupported:
declare them unavailable with an explanation. Their current heads are never read.

Authored statements use `AttributedText.to_dict()`:
`{"text": {"value": "…", "unknown_reason": null}, "attribution": {"value": "…", "unknown_reason": null}}`.
Unknown text uses an explicit `unknown_reason`; known text requires known
attribution. Authorship remains unauthenticated. Authored text/reasons are bounded
to 4096 characters per field.

`declarations` has exactly these fields:

| Field | Exact contents |
| --- | --- |
| `objective`, `scope` | AttributedText, including explicit unknown text |
| `interpretation`, `stop_reason` | AttributedText or a DeclaredText explicit unavailable reason |
| `outcome` | `label`, `explanation` (DeclaredText), `attribution` (known DeclaredText) |
| `results` | Ordered objects with `statement` (AttributedText) and nonempty `supporting_references` |
| `completed_checks` | Objects with `evidence` (exact `reported_evidence/evidence`) and attributed `description` |
| `unresolved_issues` | Exact `unresolved_issue/issue` references and/or AttributedText |
| `saved_work` | Objects with `manifest` (`saved_work/work_product_manifest`), attributed `description`, `state` (`saved`, `incomplete`, `checkpoint`) |
| `outstanding_jobs` | Objects with `reference` (`outstanding_job/attempt` or `outstanding_job/tool_execution`), attributed `description`, `state` (`outstanding`, `uncertain`) |
| `gaps`, `limitations` | Ordered AttributedText lists |
| `continuation` | Nonempty saved ordered plan below, or explicit unavailable reason |
| `reproduction` | Exactly attributed `procedure`, `build`, `environment`, each permitting explicit unknowns |

Outcome labels are `objective_met`, `partial_progress`, `unresolved`, `stopped`,
and `not_yet_assessed`. These are attributed report assessments, never canonical
scientific or operational states. Stop reasons never establish execution stopped.
A completed-check declaration requires locally valid typed Evidence, preserving
origin, result, uncertainty and failure details. Generic tool payloads cannot
qualify as completed checks. Saved checkpoints require typed manifest
`product_kind=checkpoint`. Job termination remains unavailable.

Each continuation entry has exactly `priority` (positive unique, increasing in
saved order), `task` (`task/task_specification`), `checkpoint`
(`checkpoint/work_product_manifest` or unavailable), `dependencies` (exact
references), attributed `expected_output`, `required_checks`, `required_authority`,
and `required_resources`. The last field is either unavailable or exactly
`{"account_id": "included-account", "estimates": [complete dimension/quantity vector]}`
using existing resource dimension IDs and ordinary bounded integer quantities.
Estimates must cover every dimension of the included account. They are not charged
and never imply available capacity. Saved plans do not authorize continuation.

All declaration lists have at most 128 entries; per-entry reference lists have at
most 32. Reference lists cannot duplicate exact pins or contradict stable kinds. Only the
original selection forbids multiple revisions of one identity. Historical revisions
in supporting references and outgoing closure remain independent exact pins.

## Bounds, scope and resource semantics

Canonical request JSON is at most 256 KiB with at most 32 nested containers.
Committed-result JSON is also at most 256 KiB and permits at most 33 nested
containers: `result.receipt.provenance` adds one fixed receipt wrapper relative
to `request.provenance`, preserving provenance accepted at the request boundary.
Constructors, dictionary conversion, JSON codecs and receipt access enforce this
result bound; deeper results fail.
`limits` has exactly `snapshot` (all existing `SnapshotLimits` fields), `resources`
(all `ResourceInspectionLimits` fields), and positive `max_source_bytes`,
`max_output_file_bytes`, `max_output_total_bytes`, each at most 64 MiB. All fields
are required even for schema 2. Existing snapshot content nesting rules are
preserved; the report decoder permits only the additional fixed observation
wrappers (40 outer containers). Nested saved baseline observations consume this
same depth allowance; deeply nested baseline chains fail rather than being elided. Complete source observations, including retained
baselines, and all three generated files count toward the budgets. Stored metadata
lengths and source artifact sizes are checked before loading. Oversized required
content fails; no truncation or replacement with unavailable occurs.

The scientific roots are the exact project, run, available context, original
selection and every declaration reference. The existing cycle-safe outgoing
closure captures exact envelope/content/provenance JSON, commit bindings, artifact
occurrences, schema identity and effective limits. Separate root categories label
saved baseline, previous report and selected resource evidence. Ledger-only and
report-chain records are not presented as scientific results/changes. The original
selection is retained independently. No reverse-linked review/task/job search is
performed. Uncaptured records and a complete operational job inventory remain
unknown. Generic payloads are opaque, with unavailable typed interpretation.
Required missing edges, wrong kinds and malformed explicitly requested typed
evidence/checkpoints fail.

The primary run must contain an actual exact `project` envelope edge to the
selected stable project. Historical revisions of that same project are allowed.
A different project in required closure, or explicitly selected work linked to a
different run/project, fails. Shared source/context records without ownership are
allowed. Membership without an ownership contract is caller-selected and
unauthenticated. Sibling runs reached only through project accounting remain
project context, distinct from the reported run.

For schema 3 the transaction performs the existing **complete** resource
inspection preflight and `validate_ledger`, including other projects and
administrative history. Global bounds/integrity failures therefore can prevent a
report. The resulting complete `ResourceSnapshot` retains version 2 and contiguous
operations. It is not weakened or persisted as a filtered snapshot.

A separately named `research_pipeline.report_resources` version-1 projection
retains the entire selected record-scoped project account tree: all descendants,
allocations, reservations, observations, settlements, breaches and uncertain
liabilities, including siblings. It contains exact project/run references, global
`resource_sequence`, complete-snapshot digest, original selected request/receipt
pairs, accounts/allocations/reservations/reservation_usage/breaches/balances,
explicit scope and limits. Other projects' policies, provenance, operations and
administrative-history payloads are excluded. Receipt sequence gaps are retained.
Validation replays selected operations through the existing admission/accounting
functions and compares every projection and original receipt. Sequences must be
unique, increasing and bounded by the captured global sequence; selected sequences
need not be contiguous. Completeness comes from canonical capture; detached
validation is not independent proof of omission-free capture.

Record-scoped runs match stable record identity while preserving original exact
scope revisions. Controller-scoped runs with matching names are not equated with
records; their linkage is explicitly unavailable. No project account means
no-recorded-account, not zero usage or proof of admission. An account assigned to
another project cannot claim the selected primary run/task. Every selected
operation's scope/policy/evidence reference joins scientific closure and is
verified against its original scientific watermark. Captured revision commit
metadata is supplemented only by actual event ID and selected membership ordinal;
unrelated submission payloads/membership are not embedded. Original canonical
submission bytes and audit provenance are preflighted against the remaining snapshot
metadata budget, verified by fingerprint and selected membership ordinal, then
discarded. Large shared batches can therefore exhaust this verification budget.

Renderers expose the ledger's own dimensioned projections. Observed lower bounds,
remaining reservations, conservative excess, charged totals and unknown actual
usage remain separate, as do unresolved/conservative/authoritative statuses.
Ancestor and descendant balances are never summed. Cache/reasoning telemetry is
not added again to token totals. Protected verification/handoff/closeout pools are
ledger declarations, not authenticated spending permission. Later settlements
require later dated observations.

## Transaction, identities and recovery

The manifest ID is `run-report-` plus lowercase SHA-256 of the UTF-8 stable run
record ID. Its revision is `report_revision`. Each later revision retains the
stable project/run, supersedes its immediate predecessor, and uses a distinct
operation ID. The immutable revision-1 event ID is `report-source-` plus SHA-256 of
the operation ID. Existing identity/kind collisions fail without overwriting.

`commit_report` first normalizes the entire request. It then owns one
`BEGIN IMMEDIATE` through original-ID reconciliation, predecessor/CAS checks,
source capture, rendering, artifact placement and metadata insertion. The lock
intentionally serializes scientific and ledger writers for this bounded cost.
There are no independently timed public snapshot/resource/revision calls inside
capture. One UTC `observed_at` and scientific watermark identify state immediately
before the report's own submission, not indefinitely current state.

`ReportObservation` contains exactly `format`, `version`, `request`, `observed_at`,
`scientific`, `resources`, `baseline`, `root_categories`, `source_bindings`,
`qualifications`, `snapshot_id`. Its ID hashes the canonical body excluding only
`snapshot_id`; future submission receipts and generated artifact hashes are not
in that body. Available `baseline` contains exactly `reference` and the verified
saved `observation`; unavailable baseline preserves the request reason. Fixed
saved observations produce identical output bytes.

The three objects are placed through existing `put_artifact`, then a single
Submission inserts exactly one closed `research_pipeline.report_source` version-1
generic event and one typed `end_of_run_report` WorkProductManifest. The event
retains `request`, `snapshot_id`, `observed_at`, exact `artifacts` and
`report_manifest`. Ordered record links bind every captured exact revision plus
the resulting manifest. Artifact links bind source.json and every distinct
historical closure artifact, deduplicated by digest with size contradictions
rejected. The manifest uses supplied authors, exact run/context, three files,
`entry_file=report.md`, immediate supersession, and source-event/project build
dependencies. This mixed path preserves generic semantics and does not admit
arbitrary events through `submit_typed`.

Object placement/verification/synchronization precedes metadata insertion.
Failure before SQLite commit rolls metadata back, but may leave unregistered
immutable orphan objects. They are never deleted or mutated. COMMIT uncertainty,
after-commit interruption or checked-close acknowledgment loss requires reopening
and reconciling **the original operation ID**, not recapturing under a new ID.
Rollback failure retains the existing invalidated-handle behavior.

`get_report_operation(operation_id)` returns the original `ReportCommitResult` or
None using metadata only. The result has exactly `format`, `version`,
`operation_id`, `source_event`, `report_manifest`, `snapshot_id`, `observed_at`,
`artifacts` (source.json/report.md/continuation.json), and the actual `receipt`.
Its `.receipt` property returns a detached SubmissionReceipt. Exact `commit_report`
retries return this same result before examining current heads, new timestamps,
resources or artifact availability. Changed requests and non-report submission-ID
collisions raise `SubmissionConflictError`. Original request comparison is bound
to original canonical submission JSON, fingerprints, actual revisions and audit
receipts, not just a marker.

`read_report(operation_id)` verifies source bytes, the strict retained observation,
original event/request/manifest/receipt and source-membership bindings, and the
deterministic generated bytes/hashes. Missing or damaged objects fail content
reading; they do not prevent an exact metadata retry. Backups retain historical
artifacts through the event links; exact restoration preserves original IDs,
receipts and bytes.

Malformed declarations raise `DomainValidationError`; inherited capture budget
failures retain `SnapshotLimitError` or `ResourceInspectionLimitError`;
report-specific byte bounds raise `ReportLimitError`; contradictory scope raises
`ReportScopeError`; inconsistent report bindings/projections raise
`ReportIntegrityError`. Existing store/schema/reference/artifact/CAS/conflict and
busy/database errors remain applicable. These failures never imply publication,
job completion, charge settlement or scientific qualification.

## Reading and remaining obligations

`render_report(observation)` returns exactly `report.md` and `continuation.json`
bytes with UTF-8/LF and canonical sorted JSON, retaining list order. It uses no
store, clock, filesystem reads, model, network, external process or callback.
Authored data appears as inert JSON literal blocks, following readable-view safe
literal conventions. Reproduction text is never executed. All seven content
groups are explicit, including empty results, missing baseline/interpretation,
unknown estimates/authority and absent continuation. Outcome labels are visibly
attributed. Actual Evidence, Review, Issue, claim and task fields are preserved
without favorable reinterpretation.

Available baseline comparison uses only original scientific roots/outgoing
closures. It lists sorted added and no-longer-selected exact pins and old/new
revision sets for roots present in both. These are recorded revision/selection
changes, not discoveries, improvements or deletions from canonical history.
Multiple historical pins are retained. Without a saved baseline there is no
computed change claim.

`continuation.json` is a closed `research_pipeline.report_continuation` version-1
document with `identities`, `saved_work`, `groups` (all seven structured fact/unknown
groups) and the unchanged `continuation`. It is not a second canonical manifest
or an execution request. The sibling links to source.json/continuation.json refer
to actual manifest files. Inspect exact revisions with `get_revision` or
`get_typed_revision`, artifacts with `read_artifact(ArtifactReference(digest,size))`,
and use existing manifest checkout for ordinary files. Explicit readable publication uses
`reports/runs/<actual-safe-run-id>/<decimal-revision>/report.md`,
`continuation.json`, and `source.json`. Existing readable formats/identities are
not reinterpreted.

Prepared control history and durable report obligations are implemented through
[run control](run-control.md), using authenticated operating authority. Automatic
initial/milestone/stop reporting, admission enforcement and restart readiness remain
**mandatory subsequent controller obligations**. Real jobs/providers, synthesis/export
and scientific acceptance remain unimplemented. Reading a report or plan never authorizes
continuation. D04, D03 and M0-E remain partial; M0-S remains pending.

## Exact report publication and recovery

```text
research_pipeline.report_capture.prepare_report_view(
    source: RecordStore, operation_id: str, *, limits: SnapshotLimits
) -> ReadablePlan

research_pipeline.vault.inspect_readable_publication(
    attempt_path, destination, *, expected_plan: ReadablePlan,
    limits: SnapshotLimits, source_root, protected_roots, max_entries: int
) -> PublicationInspection

research_pipeline.vault.recover_readable_view(
    attempt_path, destination, *, expected_plan: ReadablePlan,
    limits: SnapshotLimits, source_root, protected_roots, max_entries: int
) -> MaterializedView
```

Preparation verifies the original operation and complete same-run report chain in
one existing read transaction. It checks original observations, receipts, submission
fingerprints, historical closure and actual object bytes. It writes no metadata or
artifacts and never calls report commitment, live head resolution, resource inspection
or current snapshot capture. Later writes, reopen and exact restore preserve the plan.
A missing, damaged, contradictory or oversized required object fails explicitly.

The selected observation's original scientific snapshot is the common exact record
and artifact inventory. Historical reports must be consistent subsets of that
inventory. The selected report's own later source/manifest/submission binding is
retained separately, never inserted as a scientific result before its watermark.
Declared source lengths and actual stored metadata are checked before fetching or
JSON decoding. One preparation-wide metadata allowance covers the complete history,
source-binding verification, predecessor lookups, retained results and source observations.
SQL UTF-8 byte lengths preflight original submission text and fingerprint, audit
provenance and receipt scalars, actual revision content/provenance/status fields,
and every actual link field. Repeated reads consume bytes again. Original request
length is never an estimate for actual revision, audit or link storage.

Each actual record's fields and links must independently fit `max_record_bytes`,
and its canonical envelope must also fit that allowance. Passing the per-record
check does not replenish the remaining aggregate allowance. Link occurrences
consume the shared `max_references` allowance, as do source-binding occurrences;
the fixed two-member receipt is checked separately for exact original order and
contiguous ordinals. Link counts and contiguous ordinals are checked before collection,
then length-only rows bound all fields before loading their values. Matching counts
do not permit oversized relationships, identities or digests. Equality with an
allowance succeeds; exceeding it raises `SnapshotLimitError` before oversized
values reach envelope/receipt reconstruction or decoding. Malformed or contradictory
bindings still fail integrity checks. These publication preflights neither impose
caller publication limits on ordinary metadata-only receipt recovery nor require
artifact availability for retries. Caller SnapshotLimits
independently bound processing; every retained snapshot allowance must fit. Physical
copies, report navigation, folder indexes and duplicated manifest metadata consume
real file/byte budgets under the selected snapshot's unchanged output limits.
There is no truncation, timestamp refresh or limit erasure to make output fit.

`research_pipeline.readable_plan.v1` retains its original interpretation and bytes,
including ordinary `end_of_run_report` manifests. Explicit report publication uses
`research_pipeline.readable_plan.v2`, adding exactly `selected_report_operation_id`
and `reports` to the common manifest fields. Reports contain exactly `result` and
`observation`, ordered as the complete chain 1 through the selected revision. All
paths, mappings, summaries and generated bytes are recomputed. Detached reconstruction
checks internal consistency, not authentication; canonical preparation verifies storage.
Unknown fields, duplicate keys, changed prose and rehashed noncanonical projections
fail. V2 permits only its fixed outer wrapper depth; nested codecs keep their limits.

New commitments persist ReportObservation version 2, with the same closed capture
fields and semantics. Its renderer adds an ordinary adjacent `README.md` navigation
link. Persisted version 1 retains byte-exact rendering; mixed baselines and predecessor
chains remain valid. Original-operation retry precedes any new rendering-version
choice. Request, source-event, continuation and result versions remain unchanged.

Pass the resulting plan directly to `materialize_readable_view`. For each revision,
`reports/runs/<actual-run-record-id>/<decimal-revision>/` contains exact committed
`report.md`, `source.json` and `continuation.json` artifact copies and a generated
seven-field `README.md`. Portable component, device-name and alias rules apply to
the actual run ID; unsafe identifiers fail preparation, never sanitize or hash.
Every physical copy is independently verified and single-link protected. The home
pairs report and navigation links, showing the original operation, snapshot/date,
qualified outcome, recorded stopping declaration or unavailable reason, and saved
continuation requirements. It never describes a report as current live state.

Follow home → report → adjacent navigation → exact companion/envelope/artifact.
Historical v1 reports use the paired home/navigation links without byte changes.
Each navigation page links only its own saved observation, with labeled claims,
evidence, reviews, issues/objections, derivations/calculations, saved work/checkpoints
and continuation dependencies. Missing categories are explicit. Arbitrary authored
artifact links remain uncertified; only the retained report renderer's links are
verified. Reading works offline without a store, model, network or editor plugin.

Retain the original request/result **and independently pinned plan manifest before
publication**. SQLite source commitment, an in-memory plan, a complete unpublished
payload, a published generation and successful acknowledgment are separate facts.
SQLite and filesystem publication are separate atomic boundaries. The existing
same-parent exclusive rename publishes once to an absent destination. There is no
mutable latest pointer, mutable publication ledger, or append into a published tree.

Publication inspection returns frozen `PublicationInspection`: `status`, established
`snapshot_id`, `plan_id`, `manifest_sha256`, `verified_payload_path`,
`readiness_observation`, `publication_observation`, `differences`, and
`historical_acknowledgment="not_established"`. Status is `incomplete_preparation`,
`complete_unpublished`, `published`, `competing_destination`, or `inconsistent`.
It validates strict token-paired siblings, recorded parent/payload device/inode
associations, canonical controls, marker ordering and bounded protected inventory.
A different destination inode is a competitor even with equal bytes; it is never
traversed or adopted. Present markers cannot prove historical fsync success.

Explicit recovery only accepts a complete exact retained payload or that attempt's
already-published destination. It rechecks bytes, modes, links, ownership, controls
and held bindings, establishes current file/directory barriers and checked closes,
then appends missing readiness/publication evidence as appropriate. Already-present
evidence is preserved. Success returns `verification="verified_at_recovery"`, a new
acknowledgment of current verified state; historical acknowledgment remains unknown.
Failure after entering rename is uncertain. Recovery uses no live source artifacts,
model or database and never commits or recaptures another report. Repetition uses
the same attempt and plan.

Incomplete preparation is retained and cannot be patched or promoted. First reconcile
the old attempt. Once demonstrably unpublished, explicitly prepare/materialize the
original committed operation and pinned plan into an absent destination, retaining
the old attempt. This is a distinct replacement filesystem attempt, not a new report
revision or proof that an earlier uncertain attempt did not publish. Initial reservation
failure or unavailable destinations still leave the caller's committed-source identity.
Never sweep orphans, overwrite competitors or automatically retry uncertain publication.

Report-containing refresh uses `refresh_readable_view` with its independently retained
expected plan and prepared successor. A successor must retain every old report binding.
V1→v2 and v2→v2 preserve edits and renames as unsubmitted proposed work, including
ambiguous equal-byte moves, while retaining the prior tree and canonical artifacts.
`recover_readable_refresh` uses the same explicit paths, exclusions, `RefreshLimits`
and optional expected refresh ID as `inspect_readable_refresh`. It verifies and
publishes the complete frozen preservation/successor package without recapturing
possibly changed prior files. Existing read-only inspectors and CLI behavior remain
unchanged. See [refresh](readable-refresh.md) and [protected generations](readable-snapshots.md).

## Runnable synthetic committed-report example

Run this self-contained block from the repository root with
`PYTHONPATH=implementation/src`. The test executes these exact bytes. Disposable output explicitly uses `/tmp`,
outside the source tree, rather than an inherited temporary directory. All data is
synthetic and no jobs, providers or commands are dispatched. Controlled capture
dates distinguish the initial, partial, conservative, authoritative, reopened-liability
and resettled revisions. Late usage arrives after authoritative settlement; its
new report retains unknown actual usage and the sticky project-wide breach. All
three actual artifacts, generated bytes, requests and receipts are checked after
later writes, reopen and verified exact restore. Each dated report is published with
its history. A partial-work publication is interrupted and explicitly recovered
after later accounting writes using its original operation and independently pinned plan.

```python
from datetime import datetime
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline.reports import ReportRequest, render_report, manifest_id, unavailable
from research_pipeline.resources import ResourceRequest, ResourceInspectionLimits
from research_pipeline.snapshot import SnapshotLimits
from research_pipeline.work_product import WorkProductManifest, WorkProductFile, encode_envelope
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.report_capture import prepare_report_view
from research_pipeline.vault import materialize_readable_view, inspect_readable_publication, recover_readable_view
from research_pipeline.view_plan import readable_plan_from_manifest

provenance = CreationProvenance("synthetic-author", "2026-11-01T00:00:00Z", {"synthetic": True})
unknown = unavailable("Not recorded in this synthetic setup.")
units = {"model_input_tokens": "token", "model_output_tokens": "token", "model_calls": "call",
         "tool_calls": "call", "local_time": "nanosecond", "local_compute": "cpu_nanosecond", "local_storage": "byte"}
dimensions = [{"dimension_id": key, "kind": key, "unit": unit, "currency": None, "scale": 1}
              for key, unit in units.items()]


def vector(default=0, **values):
    """Declare complete dimensioned vectors; null measured usage remains unknown."""
    return [{"dimension_id": key, "quantity": values.get(key, default)} for key in units]


def reference(identity, kind, role, revision=1):
    """Name one saved exact record without following live heads."""
    return RecordReference(identity, revision, role, kind).to_dict()


def authored(value=None):
    """Supply attributed inert text, or an explicit missing interpretation."""
    return {"text": unknown if value is None else {"value": value, "unknown_reason": None},
            "attribution": {"value": "Synthetic author", "unknown_reason": None}}


def proposal(identity, revision, baseline=None, partial=False):
    """Construct a full bounded report, optionally naming the saved initial baseline and partial work."""
    declarations = {"objective": authored("Inspect saved synthetic state"), "scope": authored("Explicit saved subset"),
        "outcome": {"label": "partial_progress" if partial else "not_yet_assessed", "explanation": unknown,
                    "attribution": {"value": "Synthetic author", "unknown_reason": None}},
        "interpretation": authored(), "stop_reason": authored(), "results": [], "completed_checks": [],
        "unresolved_issues": [], "saved_work": [], "outstanding_jobs": [], "gaps": [], "continuation": unknown,
        "reproduction": {key: authored() for key in ("procedure", "build", "environment")},
        "limitations": [authored("Synthetic engineering example, no scientific acceptance")]}
    if partial:
        declarations["saved_work"] = [{"manifest": reference("checkpoint", "work_product_manifest", "saved_work"),
                                       "description": authored("Partial saved draft"), "state": "checkpoint"}]
        declarations["continuation"] = [{"priority": 1, "task": reference("task", "task_specification", "task"),
            "checkpoint": reference("checkpoint", "work_product_manifest", "checkpoint"), "dependencies": [],
            "expected_output": authored("A verified draft"), "required_checks": authored("Independent review"),
            "required_authority": authored(), "required_resources": unknown}]
    return ReportRequest({"format": "research_pipeline.report_request", "version": 1, "operation_id": identity,
        "report_revision": revision, "provenance": provenance.to_dict(), "authors": ["Synthetic author"],
        "project": reference("project", "project", "project"), "run": reference("run", "run", "run"),
        "context": unknown, "selection": [], "start_baseline": baseline or unknown, "declarations": declarations,
        "limits": {"snapshot": SnapshotLimits(1000, 1000, 10000, 4000000, 30000000, 1000, 1000, 30000000, 60000000).to_dict(),
                   "resources": {"max_accounts": 100, "max_operations": 100, "max_metadata_bytes": 1000000},
                   "max_source_bytes": 30000000, "max_output_file_bytes": 30000000, "max_output_total_bytes": 60000000}})


def operation(kind, identity, payload):
    """Save one original resource identity with explicit attribution and payload."""
    return ResourceRequest(kind, "op_" + identity, "receipt_" + identity, provenance, [], [], payload)


def scope(kind):
    """Use exact project/run/task scope and an explicitly controller-scoped attempt."""
    if kind == "attempt":
        return {"type": "controller", "kind": kind, "stable_identity": kind}
    return {"type": "record", "kind": kind, "reference": reference(kind,
            "task_specification" if kind == "task" else kind, "resource_scope")}


def usage(identity, event, quantities, reservation_id="work"):
    """Record synthetic cumulative usage or explicitly unknown loss evidence."""
    receipt = event in ("partial_usage", "authoritative_completion")
    return operation("observe", identity, {"account_id": "attempt", "owner_id": "owner", "reservation_id": reservation_id,
        "event": event, "evidence": {"source_kind": "controller_receipt" if receipt else "controller_status",
            "source_id": "synthetic", "source_receipt_id": identity if receipt else None, "statement": "Synthetic evidence only"},
        "usage": quantities, "telemetry": {"cached_input_tokens": None, "reasoning_output_tokens": None}, "call_observation": None})


def settle(identity, mode, observation_id, previous, reservation_id="work"):
    """Name settlement evidence and the actual previous reconciliation ID; accounting derives charges."""
    return operation("reconcile", identity, {"account_id": "attempt", "owner_id": "owner", "reservation_id": reservation_id,
        "mode": mode, "observation_operation_id": observation_id, "previous_reconciliation_operation_id": previous,
        "reason": "Explicit synthetic settlement"})


policy = {"policy_id": "policy", "statement": "Synthetic provisioning only", "verification_minimum": vector(tool_calls=1),
    "handoff_minimum": vector(model_calls=2, model_input_tokens=6, model_output_tokens=10, local_time=1, local_storage=1),
    "closeout_minimum": vector(local_time=1, local_storage=1),
    "handoff_call_bounds": {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5},
    "context_capacity_tokens": 8, "per_call_output_tokens": 5, "monetary_services": []}

with TemporaryDirectory(prefix="committed-report-example-", dir="/tmp") as temporary:
    parent = Path(temporary)
    runtime = parent / "runtime"
    stages, publications, pending = [], {}, {}
    software = parent / "synthetic-software"
    software.mkdir(mode=0o700)
    view_limits = SnapshotLimits(**proposal("bounds", 1).to_dict()["limits"]["snapshot"])

    def inspect_routes(root):
        """Resolve actual generated/report links; arbitrary authored Markdown stays uncertified."""
        manifest = json.loads((root / "manifest.json").read_bytes())
        paths = [row["path"] for row in manifest["files"] if row["hash_kind"] == "generated" and row["path"].endswith(".md")]
        paths += ["reports/runs/run/" + str(item["observation"]["request"]["report_revision"]) + "/report.md" for item in manifest["reports"]]
        for path in paths:
            page = root / path
            text = "\n".join(line for line in page.read_text().splitlines() if not line.startswith("    "))
            for route in re.findall(r"\[[^\[\]\n]*\]\(([^)]+)\)", text):
                target = (page.parent / route.split("#")[0]).resolve()
                assert target.is_relative_to(root.resolve()) and target.is_file()

    def publish(store, identity, plan):
        """Publish a distinct dated generation and verify its actual offline navigation."""
        result = materialize_readable_view(store, plan, parent / ("view-" + identity),
            source_root=software, protected_roots=[], max_entries=10000)
        publications[identity] = (plan, Path(result.destination))
        inspect_routes(Path(result.destination))
        return result

    def capture(store, identity, revision, baseline=None, partial=False):
        """Save a report at a controlled date, retaining all actual bytes and original resource receipts."""
        saved_request = proposal(identity, revision, baseline, partial)
        date = f"2026-11-{revision:02d}T12:00:00.000000Z"
        with patch("research_pipeline.report_capture.datetime") as clock:
            clock.now.return_value = datetime.fromisoformat(date.replace("Z", "+00:00"))
            result = store.commit_report(saved_request)
        observation = store.read_report(identity)
        assert observation.to_dict()["observed_at"] == date
        generated = render_report(observation)
        actual = {name: store.read_artifact(ArtifactReference.from_dict(ref))
                  for name, ref in result.to_dict()["artifacts"].items()}
        assert json.loads(actual["source.json"]) == observation.to_dict()
        assert all(actual[name] == data for name, data in generated.items())
        operations = store.inspect_resources(limits=ResourceInspectionLimits(100, 100, 1000000)).to_dict()["operations"]
        stages.append((saved_request, result, actual, generated, operations))
        plan = prepare_report_view(store, identity, limits=view_limits)
        # Save an independently chosen ordinary file before any filesystem publication.
        pinned = parent / (identity + ".plan.json")
        with pinned.open("xb") as stream:
            stream.write(plan.manifest_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        assert readable_plan_from_manifest(pinned.read_bytes(), limits=view_limits) == plan
        if identity == "partial":
            def interrupt(point):
                """Lose acknowledgment after real protected preparation and readiness."""
                if point == "before_rename":
                    raise KeyboardInterrupt("synthetic publication interruption")
            try:
                with patch("research_pipeline.vault._fault", side_effect=interrupt):
                    publish(store, identity, plan)
            except KeyboardInterrupt as error:
                pending.update(error._readable_recovery)
            else:
                raise AssertionError("interruption was not exercised")
            pending["plan"] = plan
            observed = inspect_readable_publication(pending["attempt_path"], pending["destination"],
                expected_plan=plan, limits=view_limits, source_root=software, protected_roots=[runtime], max_entries=10000)
            assert observed.status == "complete_unpublished" and observed.historical_acknowledgment == "not_established"
        else:
            publish(store, identity, plan)
        return observation.to_dict()["resources"], generated

    def verify_history(store):
        """Check saved requests, all three objects, generated bytes and original receipts without recapture."""
        for saved_request, result, actual, generated, operations in stages:
            identity = saved_request.to_dict()["operation_id"]
            plan, published = publications[identity]
            assert prepare_report_view(store, identity, limits=view_limits) == plan
            inspect_routes(published)
            for previous, _, old_actual, _, _ in stages:
                revision = previous.to_dict()["report_revision"]
                if revision <= saved_request.to_dict()["report_revision"]:
                    for name, data in old_actual.items():
                        assert (published / "reports/runs/run" / str(revision) / name).read_bytes() == data
            assert store.commit_report(saved_request) == result
            assert store.get_report_operation(identity) == result
            assert store.get_submission(identity) == result.receipt
            assert render_report(store.read_report(identity)) == generated
            for name, ref in result.to_dict()["artifacts"].items():
                assert store.read_artifact(ArtifactReference.from_dict(ref)) == actual[name]
            for item in operations:
                assert store.get_resource_operation(item["request"]["operation_id"]).to_dict() == item["receipt"]
        assert store.read_artifact(artifact) == b"Synthetic incomplete draft\n"

    def tool_usage(resources):
        """Select the work reservation's tool-call row without summing ancestor balances."""
        usage_row = next(row for row in resources["reservation_usage"] if row["reservation_id"] == "work")
        return usage_row, next(row for row in usage_row["dimensions"] if row["dimension_id"] == "tool_calls")

    with RecordStore.create(runtime, schema_version=3) as store:
        project = RecordEnvelope("project", 1, "project", {"synthetic": True}, provenance)
        run = RecordEnvelope("run", 1, "run", {"descriptive": True}, provenance,
                             [RecordReference("project", 1, "project", "project")])
        store.submit(Submission("setup", provenance, [project, run], {"project": 0, "run": 0}))
        _, initial_bytes = capture(store, "initial", 1)
        assert b"No result was established" in initial_bytes["report.md"]
        baseline = reference(manifest_id("run"), "work_product_manifest", "start_baseline")
        artifact = store.put_artifact(b"Synthetic incomplete draft\n")
        task = RecordEnvelope("task", 1, "task_specification", {"synthetic": True}, provenance, operational_status="blocked")
        checkpoint = WorkProductManifest("checkpoint", "Partial draft", "Saved incomplete work", ["Synthetic author"],
            RecordReference("task", 1, "task", "task_specification"), None, None, RecordReference("run", 1, "run", "run"),
            [], [], None, [], [WorkProductFile("draft.txt", artifact)], "draft.txt", ["Incomplete synthetic work"])
        store.submit(Submission("task", provenance, [task], {"task": 0}))
        store.submit_typed(Submission("checkpoint", provenance, [encode_envelope("checkpoint", 1, checkpoint, provenance)], {"checkpoint": 0}))
        store.create_resource_account(operation("create_account", "project", {"account_id": "project", "owner_id": "owner",
            "scope": scope("project"), "dimensions": dimensions, "ceiling": vector(100),
            "policy": {"policy_id": "root", "statement": "Synthetic ceiling"}}))
        for kind, parent_id in (("run", "project"), ("task", "run"), ("attempt", "task")):
            pools = {"ordinary": vector(20), "verification": vector(5), "handoff": vector(10), "closeout": vector(2 if kind == "run" else 0)}
            store.allocate_resources(operation("allocate", kind, {"allocation_id": "allocation_" + kind,
                "parent_account_id": parent_id, "account_id": kind, "owner_id": "owner", "scope": scope(kind),
                "purpose_limits": pools, "run_policy": policy if kind == "run" else None}))
        store.reserve_resources(operation("reserve", "work", {"reservation_id": "work", "account_id": "attempt",
            "owner_id": "owner", "purpose": "ordinary", "maxima": vector(tool_calls=10), "call_bounds": None}))
        store.reserve_resources(operation("reserve", "uncertain", {"reservation_id": "uncertain", "account_id": "attempt",
            "owner_id": "owner", "purpose": "ordinary", "maxima": vector(tool_calls=3), "call_bounds": None}))
        store.observe_resource_usage(usage("partial", "partial_usage", vector(None, tool_calls=4)))
        store.observe_resource_usage(usage("lost", "acknowledgment_loss", vector(None), "uncertain"))
        resources, partial_bytes = capture(store, "partial", 2, baseline, True)
        row, tool = tool_usage(resources)
        assert row["status"] == "unresolved" and tool["remaining_reserved"] == "6"
        assert b"unresolved" in partial_bytes["report.md"]
        conservative = store.reconcile_resource_usage(settle("conservative", "conservative", "op_partial", None))
        store.reconcile_resource_usage(settle("uncertain-settled", "conservative", "op_lost", None, "uncertain"))
        resources, _ = capture(store, "conservative", 3, baseline, True)
        row, tool = tool_usage(resources)
        assert row["status"] == "conservative" and tool["conservative_excess"] == "6"
        store.observe_resource_usage(usage("complete", "authoritative_completion", vector(tool_calls=6)))
        settled = store.reconcile_resource_usage(settle("settled", "authoritative", "op_complete", conservative.to_dict()["operation_id"]))
        resources, final_bytes = capture(store, "settlement", 4, baseline, True)
        row, tool = tool_usage(resources)
        assert row["status"] == "authoritative" and tool["actual_usage"] == tool["charged_total"] == "6"
        assert b"authoritative" in final_bytes["report.md"] and b"conservative" in final_bytes["report.md"]

        # Distinct late evidence reopens liability AFTER authoritative settlement.
        store.observe_resource_usage(usage("late", "partial_usage", vector(None, tool_calls=7)))
        resources, reopened_bytes = capture(store, "reopened-liability", 5, baseline, True)
        continuation = json.loads(reopened_bytes["continuation.json"])
        assert continuation["groups"]["dimensioned_resources_and_stopping_decision"]["resources"] == resources
        row, tool = tool_usage(resources)
        assert row["status"] == "unresolved"
        assert (tool["known_spent"], tool["remaining_reserved"], tool["charged_total"], tool["actual_usage"]) == ("7", "3", "10", None)
        breach = next(item for item in resources["breaches"] if item["reason"] == "post_settlement_usage")
        assert (breach["observed"], breach["limit"]) == ("7", "6")
        assert all(item["admission_blocked"] for item in resources["balances"])
        for phrase in ('"status":"unresolved"', '"known_spent":"7"', '"remaining_reserved":"3"',
                       '"charged_total":"10"', '"actual_usage":null', '"reason":"post_settlement_usage"',
                       '"observed":"7"', '"limit":"6"', '"admission_blocked":true'):
            assert phrase.encode() in reopened_bytes["report.md"]
        store.observe_resource_usage(usage("complete-again", "authoritative_completion", vector(tool_calls=7)))
        store.reconcile_resource_usage(settle("settled-again", "authoritative", "op_complete-again", settled.to_dict()["operation_id"]))
        resources, _ = capture(store, "resettlement", 6, baseline, True)
        row, tool = tool_usage(resources)
        assert row["status"] == "authoritative" and tool["actual_usage"] == tool["charged_total"] == "7"
        assert breach in resources["breaches"] and all(item["admission_blocked"] for item in resources["balances"])
        later_task = RecordEnvelope("task", 2, "task_specification", {"later": True}, provenance, operational_status="blocked")
        store.submit(Submission("later-task", provenance, [later_task], {"task": 1}))
        store.observe_resource_usage(usage("later-receipt", "partial_usage", vector(None, tool_calls=7)))
        # Newer scientific/resource/report state cannot change the interrupted plan.
        original = pending["plan"]
        assert prepare_report_view(store, "partial", limits=view_limits) == original
        recovery_args = dict(expected_plan=original, limits=view_limits, source_root=software,
                             protected_roots=[runtime], max_entries=10000)
        recovered = recover_readable_view(pending["attempt_path"], pending["destination"], **recovery_args)
        assert recover_readable_view(pending["attempt_path"], pending["destination"], **recovery_args) == recovered
        publications["partial"] = (original, Path(recovered.destination))
        assert recovered.plan_id == original.plan_id
        verify_history(store)
        create_backup(store, parent / "backup")
        inspect_backup(parent / "backup")
    with RecordStore.open(runtime) as reopened:
        verify_history(reopened)
    with restore_backup(parent / "backup", parent / "restored") as restored:
        # Inspect exact restoration before retries or new writes on the restored handle.
        assert (parent / "restored/metadata.sqlite3").read_bytes() == (parent / "backup/snapshot.sqlite3").read_bytes()
        verify_history(restored)
        publish(restored, "restored-history", publications["resettlement"][0])

```

Local tests are advisory. The frozen controller checks remain, in order,
`python3 -B implementation/scripts/validate.py` and
`git diff --check b166730570ee2bd2997aaf1a61604297057b6bf1 HEAD --`, with the documented
process-only descriptor soft-limit prerequisite of 4096. Controller validation and
Reviewer verification own acceptance; this guide asserts no acceptance result.

## Controlled-run report reservations

[Run control](run-control.md) reserves ordered report identities as pending intent.
Fresh legacy report commits cannot take over a controlled run, reserved source or
report operation; exact original reconciliation remains available first. Uncontrolled
legacy reports retain their existing contracts. Automatic lifecycle capture, publication
and acknowledgment remain mandatory in the subsequent ADR-063 slices.

## Offline lifecycle intent binding

The [offline lifecycle-report binding contract](lifecycle-report-binding.md) retains and validates
original preparation, selected control transition and required-report intent
under explicit independent processing allowances. It accepts arbitrary saved-work
baselines without changing historical report v1 baseline grammar. It proves local
consistency only, creates/discharges no obligation, and never authorizes ordinary work.
[Committed lifecycle sources](committed-lifecycle-sources.md) implement the separate
one-event source stage. Historical report v1/v2 and their receipts remain unchanged.
The [pure lifecycle renderer](lifecycle-report-rendering.md) reuses the seven-group
projection and inert framing while preserving historical v1/v2 bytes. It returns
generated bytes only; output commitment/readable plans, automatic publication,
acknowledgment and current-policy continuation remain mandatory subsequent slices.

The [controlled lifecycle source API](committed-lifecycle-sources.md) does not call
`commit_report`, render output, or treat arbitrary saved-work baselines as earlier
generated reports. It reserves a distinct source submission S and a later report
submission O, preserving the existing source event identity and manifest revision.
The later output protocol cannot append to S or reinterpret its one-member receipt.

Schema 7 preserves this capability through the existing guarded insertion and
original-operation reconciliation paths. New snapshots/captures name actual
schema 7 and its registry-derived identity; saved schema-6 and earlier documents
retain their original bytes, interpretation and recovery. Support-context freshness
adds no execution or scientific authority.
