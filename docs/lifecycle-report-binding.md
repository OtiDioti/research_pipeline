# Offline lifecycle-report bindings

`research_pipeline.lifecycle_report_binding` validates the local relationship
between the original preparation, one selected control transition, and its required
report obligation. It reads no store, clock, policy evaluator, artifact, model, or
network. The packet neither creates nor discharges an obligation. Its work gate is
permanently closed, regardless of current policy or pending-report status.

## Public API

Import these exact classes and functions from `research_pipeline.lifecycle_report_binding`:

```python
LifecycleReportBindingLimits(*, max_input_bytes: int, max_packet_bytes: int,
                             max_work_bytes: int, max_nodes: int, max_depth: int)
LifecycleReportBinding(document: dict, *, limits: LifecycleReportBindingLimits)
LifecycleReportBinding.from_dict(document: dict, *, limits: LifecycleReportBindingLimits) -> LifecycleReportBinding
LifecycleReportBinding.to_dict(self, *, limits: LifecycleReportBindingLimits) -> dict
bind_lifecycle_report(preparation: dict, transition: dict, obligation: dict,
                      *, limits: LifecycleReportBindingLimits) -> LifecycleReportBinding
dumps_binding(value: LifecycleReportBinding, *, limits: LifecycleReportBindingLimits) -> str
loads_binding(data: str | bytes, *, limits: LifecycleReportBindingLimits) -> LifecycleReportBinding
binding_digest(value: LifecycleReportBinding, *, limits: LifecycleReportBindingLimits) -> str
```

Every allowance is mandatory and keyword-only. There are no defaults, retained
budgets, unbounded public inspection properties, or alternate summaries. `to_dict`
is the inspection operation. Limits and bindings are frozen exact classes;
subclasses and bypass-mutated limits are rejected. Bindings retain only a private
canonical string, `_json`, without caller dictionaries, limits, or nested mutable
objects. They use object identity equality/hash and a non-content repr. Compare
canonical JSON or `binding_digest` explicitly.

The factory accepts three **complete ordinary envelope wire dictionaries**, not
`RecordEnvelope` objects, control objects, arbitrary mappings, or callbacks.
Obtain wire dictionaries through the accepted APIs before entering this boundary.
Nested domain objects (including forged envelopes, provenance, scopes and
references) are invalid. Only exact dict/list/str/int/bool/finite-float/null JSON
values and ordinary string keys are permitted. Strings must contain Unicode
scalars. Integers must fit the signed SQLite range before decimal conversion.
Existing field grammars additionally enforce integer/bool distinctions. Actors
retain the historical 1–128 ASCII identifier grammar; narrative Unicode uses its
separate accepted grammar.

## Closed wire format and canonical identity

Every packet has exactly these ten fields:

| Field | Meaning |
| --- | --- |
| `format` | Exactly `research_pipeline.lifecycle_report_binding` |
| `version` | Ordinary integer `1` |
| `preparation` | Complete original revision-one prepare transition envelope |
| `preparation_digest` | Lowercase SHA-256 of that complete canonical envelope |
| `transition` | Complete selected control transition envelope |
| `transition_digest` | Lowercase SHA-256 of that complete canonical envelope |
| `obligation` | Complete selected transition's required-report obligation envelope |
| `obligation_digest` | Lowercase SHA-256 of that complete canonical envelope |
| `ordinary_work_allowed` | Exactly `false`, permanently |
| `recheck_required` | Exactly `true`, permanently |

Every envelope explicitly contains `record_id`, `revision`, `kind`, `content`,
`provenance`, `record_references`, `artifact_references`, `operational_status`, and
`scientific_disposition`. Provenance explicitly contains `actor`, `created_at`,
and `details`. References explicitly contain `record_id`, `revision`,
`relationship`, and `target_kind`. Generic decoder defaults are not accepted.
Nested timestamps and values must already be canonical; nothing is silently
normalized or filled in.

Initial packets deliberately repeat the same **complete** preparation envelope
in `preparation` and `transition`; both hashes must agree. Later packets retain the
original immutable dossier (authority domain, purpose, project, initial/current
corpus, context, saved-work baseline, operating scope, allocation and previous run)
through the included preparation. Their own report selection, declarations and
embedded limits come from `transition.content.request.report`. They need not equal
prepare-time report intent. An arbitrary exact `start_baseline/work_product_manifest`
reference or an explicit unavailable declaration is retained without dereferencing.
This does not change historical [ReportRequest/ReportObservation v1](committed-run-reports.md#exact-version-1-request)
earlier-report baseline grammar. No v1 report object is constructed here.

The accepted control validators enforce derived identities, references, projections,
null statuses, empty direct artifacts and exact provenance. The selected transition
must use the same run, a nondecreasing generic run revision and time, and the
original revision-one `prepared_from` reference. Initial preparation is checked
with `validate_successor(None, ...)`. Revision two is checked against the included
preparation as its actual predecessor, including its envelope digest. For higher
revisions, only predecessor syntax/identity/revision, local disposition grammar,
original lower bounds and structural capacity are checked; omitted intermediate
history is not reconstructed. Later operation IDs differ from prepare. A local
`continue` packet also requires the original policy fingerprint, without evaluating
permission or claiming a committed continuation. Existing pending-report denial
remains unchanged.

The obligation exactly equals the accepted derivation, with identical provenance.
`required_at` is the selected transition time; the original preparation time is
preserved separately. Control revision equals report revision, obligation envelope
revision is always one, and generic run revision is independent. Capacity checks
are structural hard ceilings, not evidence of actual history length or free slots.
Member hashes are checked only after semantic pairing.

Canonical JSON uses `run_control.canonical`: sorted keys, compact separators,
`ensure_ascii=True`, `allow_nan=False`, preserving array order. `dumps_binding`
returns ASCII text; `binding_digest` is lowercase SHA-256 over the ASCII bytes of
the entire canonical packet. There is no self-digest, budget, new watermark,
capture/publication time, receipt or readiness field. The factory derives the
three hashes and fixed wrapper fields. Constructor, classmethod and decoder
require and verify them using the same validation path.

External JSON may have whitespace, different key order and UTF-8 narrative text;
only its canonical encoding is retained. Every consumer revalidates the exact
binding class and `_json` from scratch under fresh allowances. Noncanonical retained
whitespace/key order, malformed retained state and contradictory forged semantics
fail. `to_dict` returns a detached parsed tree; mutating it does not change a binding.

## Independent limits and accounting

The exported hard constants and caller ranges are:

| Field | Inclusive range | Hard constant |
| --- | --- | --- |
| `max_input_bytes` | 1–16,777,216 | `MAX_INPUT_BYTES = 16 * 1024 * 1024` |
| `max_packet_bytes` | 1–16,777,216 | `MAX_PACKET_BYTES = 16 * 1024 * 1024` |
| `max_work_bytes` | 1–2,147,483,648 | `MAX_WORK_BYTES = 2 * 1024 * 1024 * 1024` |
| `max_nodes` | 0–393,224 | `MAX_NODES = 3 * 131072 + 8` |
| `max_depth` | 0–49 | `MAX_DEPTH = 49` |

All five are required ordinary integers, excluding booleans and integer subclasses.
Zero node/depth budgets are valid authorization for no packet and therefore fail
with `LifecycleReportBindingLimitError` when processing a packet. Embedded report
limits remain validated retained intent; they never increase independent processing
allowances. No history, resource-replay, publication or output budget is added.

* **R** is raw UTF-8 input size for `loads_binding`, including whitespace. On
  retained consumers it is the exact-str `_json` UTF-8 size and must also fit
  `max_input_bytes`. For dictionary constructor/classmethod/factory calls, R=0.
* **P** is the exact complete canonical ASCII packet size, including keys,
  punctuation, digest strings, fixed booleans, nulls and empty containers. Every
  occurrence counts: aliases, repeated original envelopes and projected references
  are not deduplicated. P fits both caller and hard packet ceilings.
* **N** counts every serialized container and scalar value occurrence, excluding
  object keys. `N = N_preparation + N_transition + N_obligation + 8`.
* **D** counts container levels, with root object depth one and scalars adding
  none. `D = 1 + max(D_preparation, D_transition, D_obligation)`.
* **W = 8R + 64P** is the fixed conservative canonical-representation workspace
  authorization. For retained canonical packets, R=P and W=72P. This is not an
  allocator/RSS measurement. Exact equality tests refer to this published charge,
  irrespective of cache hits or allocation optimizations.

The raw 8R reserve covers an upper bound for parsed canonical expansion and decoded
text. It is checked before UTF-8 decoding/parsing. Raw str length is measured
without an encoded copy. A lexical scanner checks complete-input value nodes and
container depth before strict parsing, which rejects duplicate keys at every level,
nonfinite constants and malformed syntax. Valid escaped supplementary surrogate
pairs are accepted; lone/literal surrogates are rejected before reconstruction.
The parsed tree is measured again before dependent allocation; raw UTF-8 size is
never assumed equal to escaped canonical size.

An iterative walker uses bounded iterator frames, checks collection lengths before
dependent collections, detects cycles only on the current ancestor path, and does
not copy caller trees. The factory measures a fixed shallow wrapper with three
64-character digest placeholders before hashing anything. Wrapper byte accounting
also uses a fixed skeleton with null envelope slots: subtract 12 null bytes and
add all three member sizes. No concatenated child encodings are used for sizing.
The complete W charge is checked before nested construction, copying, envelope
hashing or canonical container encoding. The 64P reserve covers sequential bounded
envelope/control/scope normalization, detached trees, projections, retained output,
and canonical/ASCII/hash scratch. Obsolete validation scratch is discarded.

Inherited fragment ceilings apply before their constructors: complete envelopes
at 4 MiB, 131072 nodes and 48 containers; transition content at 4 MiB; requests at
2 MiB; obligation content and each report intent at 256 KiB. Report intent retains
its 32-container rule, and operating scope retains 32 containers/131072 nodes and
its accepted byte ceiling. Existing field/list/text limits remain unchanged.
Expected complete projections are streamed and measured even when supplied links
are maliciously short. Canonical projected envelopes have
`content_nodes + 12 + 5 * projected_reference_count` nodes and
`max(content_depth + 1, 3)` depth. Reference tuples are built only after this check.
The preflight uses wire data for the fixed run reference because the accepted
projection generator itself constructs that reference; the accepted decoder then
checks the actual ordered projection. No shared validator globals are changed.

## Errors and precedence

Omitted/unknown arguments remain Python `TypeError`. Once a public body is entered:

1. Validate and detach all limits. Invalid allowances always win over payload errors.
2. Check exact public argument/self/class types. Wrong roots, codec input types,
   factory arguments or subclasses raise `LifecycleReportBindingArgumentError`
   (`ValueError`). Wrong or missing `_json` on an exact binding is content failure.
3. Check raw length and 8R reservation, then lexical node/depth safety before parsing.
4. Strictly parse and preflight full tree types, Unicode, cycles, size and shape;
   reserve W and check fragments and expected projections.
5. Validate closed fields, version, canonical nested grammar, pairing, projections,
   provenance and digests; finally require exact retained canonical equality.

`LifecycleReportBindingLimitError` (`ValueError`) reports caller/workspace or hard
structural byte/node/depth overflow. `LifecycleReportBindingValidationError`
(`DomainValidationError`) reports malformed/noncanonical content, invalid embedded
report allowances, identifier/list/text grammar and structural contradictions.
Accepted validator/state/integrity failures are translated to sanitized content
errors without implying store inspection. Safety precedes semantics; streaming
preflight reports the first encountered violation rather than traversing unsafe
input to select another diagnostic. Unexpected implementation errors and assertions
are not suppressed. Diagnostics do not echo packet or policy contents.

## What remains unverified

A `prepared_from` reference is not a cryptographic commitment to an omitted history.
Revision two supplies a real predecessor digest that this packet can check against
its preparation. Higher revisions do not. Contradictory supplied values fail even
when rehashed, but a fully rewritten internally consistent packet with recomputed
hashes cannot be distinguished here from persisted facts. Local hashes provide no
authenticity claim or guarantee that every alternate preparation is detectable.

The separate [committed source stage](committed-lifecycle-sources.md) establishes
the actual generic-run-to-project ownership
edge; dossier/source/account existence; original committed preparation bytes;
operation ownership; submission membership, receipt and audit provenance; authority
decision's committed historical metadata and original watermark; previous-run
relationship; and the necessary intermediate history. It does not claim current
cryptographic verification without current keys. This offline binding module itself
performs none of those reads.

[ADR-063](../development/decisions/ADR-063-lifecycle-report-decomposition.md) assigns
the implemented coherent lifecycle source capture/commit/original-ID recovery to REQ-D04-006;
[pure shared rendering](lifecycle-report-rendering.md) to REQ-D04-007-A, and
output commitment, complete-history plans and bounded offline reconstruction to
REQ-D04-007-B; ordered publication/refresh and separately verified acknowledgment to
REQ-D04-008; and current-policy restart/continuation with resource/dependency/pending
gates to REQ-D04-009. All FOLLOWON-01–13 and wider requirements remain mandatory.
Report v2, plan and publication contracts are unchanged. This binding proves no
capture, publication, stopping completion, available resources, continuation
readiness or worker admission. D04/M0-E/product/scientific obligations remain partial.

## Runnable offline lifecycle-binding example

Run this block with candidate-local `implementation/src` on `PYTHONPATH` and
`python3 -B`. It needs only product and standard-library APIs, no store or clock.
All IDs and authority digests are illustrative and unauthenticated. The arbitrary
saved-note baseline is not an earlier report. Synthetic consistency does not prove
that any referenced record exists.

```python
from copy import deepcopy
from dataclasses import replace
from research_pipeline import run_control as c, operating_authority as a
from research_pipeline import lifecycle_report_binding as b
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
    "limits": {"snapshot": {"max_roots": 10, "max_records": 100, "max_references": 1000,
        "max_record_bytes": 100000, "max_metadata_bytes": 1000000, "max_artifacts": 10,
        "max_files": 10, "max_file_bytes": 100000, "max_total_bytes": 1000000},
        "resources": {"max_accounts": 10, "max_operations": 100, "max_metadata_bytes": 1000000},
        "max_source_bytes": 1000000, "max_output_file_bytes": 1000000, "max_output_total_bytes": 2000000}}
pin = {"reference": c.reference("illustrative-decision", 1, "operating_decision", "decision"),
       "envelope_digest": "1" * 64}  # Illustrative, unauthenticated digest.
prepared_at = "2026-11-01T12:00:00.000000Z"
selected_at = "2026-11-03T12:00:00.000000Z"
request = c.RunControlRequest({"format": "research_pipeline.run_control_request", "version": 1,
    "operation_id": "prepare-example", "run_id": "run", "run_revision": 2, "revision": 1,
    "predecessor": None, "action": "prepare", "actor": "illustrator", "transitioned_at": prepared_at,
    "preparation": {"authority_domain": "illustrative", "purpose": "setup",
        "project": c.reference("project", 1, "project_setup", "project"),
        "initial_corpus": c.reference("corpus", 1, "initial_corpus", "corpus_manifest"),
        "current_corpus": c.reference("corpus", 2, "current_corpus", "corpus_manifest"),
        "context": a.absent(), "start_baseline": c.reference("saved-note", 7, "start_baseline", "work_product_manifest"),
        "operating_scope": scope, "allocation": {"allocation_id": "illustrative-allocation",
            "project_account": unknown, "run_account": unknown}, "previous_run": None},
    "expected_authority": pin, "operational_reason": None, "report": report}).to_dict()
original = c.RunControlTransition({"format": c.FORMATS[0], "version": 1, "request": request,
    "disposition": "prepared", "prepared_from": None,
    "authorization": {"decision": pin, "evaluated_at": prepared_at, "policy_fingerprint": "2" * 64,
        "watermark": {"event_id": None, "submission_id": None, "committed_at": None, "fingerprint": None}},
    "obligation": c.reference(c.obligation_id("prepare-example"), 1, "required_report")})
preparation = c.encode_transition(original)
selected_request = deepcopy(request)
selected_request.update(operation_id="cancel-example", run_revision=5, revision=2,
    predecessor={"reference": c.reference(preparation.record_id, 1, "supersedes"),
                 "envelope_digest": c.envelope_digest(preparation)},
    action="cancel", transitioned_at=selected_at, preparation=None, expected_authority=None,
    operational_reason={"code": "model_forbidden", "detail": "Illustrative reduction, no policy evaluation"})
selected_request["report"]["selection"] = [c.reference("saved-note", 7, "report_selection", "work_product_manifest")]
selected_request["report"]["declarations"]["objective"] = text("Preserve selected cancellation intent: α 𝒜")
selected_request["report"]["limits"]["max_output_total_bytes"] = 1500000
selected = c.RunControlTransition({"format": c.FORMATS[0], "version": 1, "request": selected_request,
    "disposition": "cancelled", "prepared_from": c.reference(preparation.record_id, 1, "prepared_from"),
    "authorization": None, "obligation": c.reference(c.obligation_id("cancel-example"), 1, "required_report")})
transition = c.encode_transition(selected)
obligation = c.encode_obligation(c.RunReportObligation(c.obligation_document(selected.to_dict())), actor="illustrator")
limits = b.LifecycleReportBindingLimits(max_input_bytes=100000, max_packet_bytes=100000,
    max_work_bytes=10000000, max_nodes=10000, max_depth=40)
larger = replace(limits, max_input_bytes=200000, max_packet_bytes=200000,
    max_work_bytes=20000000, max_nodes=20000, max_depth=49)
value = b.bind_lifecycle_report(preparation.to_dict(), transition.to_dict(), obligation.to_dict(), limits=limits)
wire = value.to_dict(limits=limits)
assert wire["preparation"] == preparation.to_dict()
assert wire["transition"]["content"]["request"]["report"] == selected_request["report"]
assert wire["preparation"]["content"]["request"]["transitioned_at"] == prepared_at
assert wire["obligation"]["content"]["required_at"] == selected_at
assert wire["transition"]["content"]["request"]["run_revision"] == 5
assert wire["obligation"]["content"]["report_revision"] == 2
assert wire["obligation"]["revision"] == 1
encoded = b.dumps_binding(value, limits=limits)
for reconstructed in (b.LifecycleReportBinding(wire, limits=limits),
                      b.LifecycleReportBinding.from_dict(wire, limits=limits),
                      b.loads_binding(encoded, limits=limits),
                      b.loads_binding(encoded.encode("ascii"), limits=limits)):
    assert b.dumps_binding(reconstructed, limits=larger) == encoded
    assert b.binding_digest(reconstructed, limits=larger) == b.binding_digest(value, limits=limits)
contradictory = deepcopy(wire)
contradictory["ordinary_work_allowed"] = True
try:
    b.LifecycleReportBinding(contradictory, limits=limits)
except b.LifecycleReportBindingValidationError:
    pass
else:
    raise AssertionError("contradictory work gate was accepted")
print("This proves local intent consistency only; no persistence, capture, publication or work permission.")
```

The example test executes this exact block in a fresh `python -B` process with
candidate-local imports. Focused Writer checks are advisory. Controller-owned
baseline/candidate/final validation remains the unchanged
`python3 -B implementation/scripts/validate.py` followed by
`git diff --check eeb9839a59978fc4bee6e8b9e644afdbc09742a3 HEAD --`.
Acceptance additionally requires the predecessor blob/mode and behavior checks,
independent reviews and controller receipts; this guide claims none of them.
