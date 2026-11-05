# Passive Tool-record CLI

These two source-local operations expose passive Tool metadata through the existing
RecordStore. Put the candidate's `implementation/src` on `PYTHONPATH`; no
installation is needed. Research execution is unavailable.

```text
python3 -B -m research_pipeline inspect-tool-record --config FILE --kind tool_release|tool_assessment --record-id ID --revision N [LIMIT OPTIONS]
python3 -B -m research_pipeline submit-tool-records --config FILE --batch FILE [LIMIT OPTIONS]
```

Every selection is required. Inspection selects an exact positive revision,
1..9223372036854775807, never a head. Submission accepts a nonempty ordered batch
containing either or both Tool kinds; both kinds are not required. There are no
aliases, positional shortcuts, stdin inputs, environment-selected stores, implicit
configuration, ingestion, installation, execution or generic canonical writes.
Options cannot be abbreviated or repeated. New-command numeric argv spelling is
`0` or a nonzero ASCII digit followed by digits. Signs, whitespace, leading zeros,
Unicode digits, fractional and exponent aliases are usage errors. Bounded token
conversion follows syntax checking. All ranges, IDs, kind choices and normalized
path syntax are validated before control/runtime/artifact access. Other CLI
commands retain their existing syntax and numeric behavior.

## Controls and filesystem observations

Configuration is exactly the existing [local CLI version-one configuration](local-cli.md):
`{"format":"research_pipeline.cli_config","version":1,"store":"/private/runtime","protected_roots":[]}`.
All four fields are mandatory and no others are allowed. The runtime and exclusions
are absolute; at most 64 distinct normalized exclusions are allowed. CLI control
paths may be relative to cwd and normalize lexically to absolute paths. Paths are
Unicode scalar strings, at most 4096 UTF-8 bytes before/after normalization, with
no NUL or `..` components. There is no environment or control override for source
protection. Normalization does not resolve symlinks.

Both controls require owned single-link regular 0600/0400 leaves and owned exact
0700 immediate parents. Reads reuse nonblocking no-follow opening, initial
stat/open agreement, bounded reads plus an EOF probe, signatures and checked
closes. All input descriptors close before protected work. Held directory bindings
and initial parent-relative leaf signatures remain checked on failure paths,
immediately before submission, and after store operations/close. An initially
missing config is invalid input; an initially missing explicit batch/runtime is
missing. Disappearance/replacement after observation is integrity failure before
submission and uncertain acknowledgement after possible submission. Real EACCES/EIO
causes remain operational errors.

The executing source checkout is derived from the module layout. Runtime overlap
with source/exclusions in either direction is refused. Controls cannot overlap
source, runtime, exclusions or one another. Fixed-name no-follow ancestor probes
reject recognizable storage, backup, checkout, readable-view/refresh and proposal
layouts, without arbitrary directory enumeration or reading sentinel contents.
Runtime acquisition permits only the explicitly selected runtime and its expected
objects/staging internals, rejecting enclosing recognizable layouts. The CLI opens
only an existing RecordStore: it never creates, migrates, repairs, chmods, cleans
or imports anything.

Ancestors outside owned private controls remain trusted. Held observations detect
observed substitutions; they do not sandbox a hostile same-owner or privileged
process. `RecordStore.open` retains its five-second busy timeout, schema/history
validation and legitimate rollback-journal recovery. Inspection and invalid-control
refusal create no canonical submission, but neither promises zero physical SQLite
writes. Selected limits do not bound all SQLite opening/recovery work.

Strict UTF-8 JSON rejects duplicate decoded keys at every depth, nonfinite floats,
unpaired surrogates, numeric tokens longer than 128 characters and containers
beyond depth 64 before parsing. Batch integer `-0` is additionally refused.
Descriptive provenance details retain signed integers, booleans and finite floats.
Integer fields elsewhere require ordinary integers, never bool/float/string aliases.
Whitespace, object ordering and equivalent valid string escaping are insignificant.

## Independent caller limits

Both commands expose every row below except the four submission-only rows.
Ranges are inclusive. Canonical bytes include ASCII escape expansion; repeated
occurrences always count. Limits are independent and a larger allowance never
replaces a smaller one.

| Option | Default | Range | Meaning |
| --- | ---: | --- | --- |
| `--max-control-bytes` | 65536 | 1..1048576 | Actual UTF-8 configuration bytes |
| `--max-output-bytes` | 2097152 | 1..16777216 | Complete ASCII result bytes including LF |
| `--max-envelope-bytes` | 2097152 | 1..4194304 | Canonical ASCII bytes per complete enclosing envelope |
| `--max-content-bytes` | 1048576 | 0..1048576 | Canonical ASCII bytes per Tool content document |
| `--max-metadata-bytes` | 2097152 | 1..16777216 | Complete canonical Submission before reconstruction, or inspection fetch/retention reservation below |
| `--max-links` | 4096 | 0..65536 | Record plus artifact projection occurrences across the batch or selected envelope |
| `--max-provenance-bytes` | 262144 | 1..1048576 | Canonical ASCII bytes per complete CreationProvenance, including details; submission and each envelope are independent |
| `--max-provenance-depth` | 24 | 1..24 | Provenance details container nesting; details object is depth one |
| `--max-file-bytes` | 16777216 | 0..1073741824 | Declared bytes per projected direct artifact |
| `--max-total-bytes` | 67108864 | 0..4294967296 | Declared bytes summed over direct-artifact occurrences; the same digest in another envelope counts again |
| `--max-batch-bytes` (submit only) | 2097152 | 1..16777216 | Actual UTF-8 batch bytes including whitespace |
| `--max-records` (submit only) | 128 | 1..4096 | Submitted envelope occurrences |
| `--max-receipt-records` (submit only) | 1024 | 1..65536 | Ordered receipt membership occurrences |
| `--max-receipt-bytes` (submit only) | 262144 | 1..16777216 | Complete canonical ASCII receipt bytes, excluding outer result and LF |

Existing hard codec limits also apply. ToolReleaseLimits/ToolAssessmentLimits keep
max_wire_bytes=1048576, max_string_chars=16384, max_collection_items=256,
max_references=1024, max_nodes=32768, max_depth=24 and
max_reconstruction_units=262144; only max_canonical_bytes narrows to the caller's
max_content_bytes. Nested dictionary input does not turn external-load-only
max_wire_bytes into a batch/envelope bound. Envelope hard limits remain
max_metadata_chars=262144 and max_projection_references=1024. Assessment envelope
provenance depth narrows to the caller value; the CLI checks that depth independently
for releases and submission provenance as well.

Bounded JSON chunking checks escape expansion before whole-value encoding/copying.
For selected inspection, length/type/join/count/ordinal guards precede fetching
payloads or materializing links. Let E be the conservative complete canonical
envelope bound from canonical content/provenance lengths and fixed framing plus
escaped scalar/link bounds (at most six ASCII bytes per UTF-8 byte plus quotes).
Let F cover the complete selected raw field/link/commit byte lengths, including
identity, revision and ordinal contributions; K bounds the canonical commit object.
The guard requires `E <= max_envelope_bytes` and
`2*F + 2*E + K <= max_metadata_bytes`. This reserves guard/store reads plus
retained envelope/separate content/commit. Stored JSON is depth/numeric/duplicate/
Unicode guarded and must reproduce its canonical representation exactly. The
selected kind is checked before another kind's artifacts are inspected. Preflight,
typed body and original commit identity share one SQLite read snapshot. No head,
predecessor, target closure or release pairing is read by this inspection.

These are representation and selected-data bounds, not RAM measurements, timeouts,
total SQLite work or fresh transaction-owned target/history limits. The assessment
store retains its separate fixed processing ceilings: 4096 roots/distinct metadata
identities, 4096 mandatory history revisions, 32768 projected occurrences,
4194304 bytes per envelope and 67108864 bytes aggregate fetched/retained/scratch.
Its complete control/request and reconstruction scratch accounts remain unchanged;
see [persistence processing details](tool-assessment-persistence.md).

## Closed batch schema and local decoding

The complete batch has exactly:

```json
{"format":"research_pipeline.cli_tool_batch","version":1,"submission":{"submission_id":"original-id","provenance":{"actor":"controller","created_at":"2026-11-05T10:00:00.000000Z","details":{}},"records":[],"expected_heads":{}}}
```

The displayed empty records is only a field-set illustration: actual batches must
be nonempty. Version is the ordinary integer 1. Submission has exactly
submission_id, provenance, records and expected_heads. One revision per stable ID
is allowed; repeated IDs are refused. expected_heads is explicit and covers exactly
the submitted IDs, with ordinary integers 0..9223372036854775807. Zero requires
an absent identity. The CLI never infers or queries expectations.

Each envelope has exactly record_id, revision, kind, content, provenance,
record_references, artifact_references, operational_status and scientific_disposition.
Both state fields explicitly equal null. kind is exactly tool_release or
tool_assessment. Record references have exactly record_id, revision, relationship
and explicit non-null target_kind. Artifact references have exactly digest and size.
Every provenance has exactly actor, created_at and details; timestamps must already
have six fractional digits and UTC `Z`. Nothing is filled in or normalized.

Content is the complete unchanged version-one public wire schema. Release root
fields are exactly format, version, kind, release_id, adapter_identity,
configuration_identity, identity, invocation, scientific_meaning, effects_authority,
resources_recovery, evidence_limitations and reproducibility. Assessment root
fields are exactly format, version, kind, assessment_id, attribution, target,
environment, scope, checks, reviews, limitations, issues, execution_permission,
qualification and lifecycle. Nested closed schemas and null/unknown/unavailable/
known-empty distinctions are defined by the existing
[release](tool-releases.md), [assessment](tool-assessments.md) and envelope codecs.
Supplied identities and projections are checked, never regenerated.

Complete raw fields/types/counts, canonical representations, provenance depth,
projected-link totals and declared direct bytes are bounded before domain copying.
The raw complete Submission is bounded before Submission.from_dict. Public Tool
codecs and envelope decoders check nested content and exact complete canonical
equivalence, refusing missing defaults, timestamp repairs and coercive equivalents.
Array order and exact canonical content survive. Missing/unsupported/malformed
Tool content never falls back to generic submission.

Local decoding does no target/history/pairing checks, byte availability, CAS or
schema-kind admission. An assessment may precede its release. All non-Tool
references must already exist; referenced bytes must already be present in the
configured runtime. This CLI never stages them.

## Store effects, output reservation and retries

Submission calls `RecordStore.submit_typed(Submission)` exactly once after stable
control checks. The existing transaction owns fresh availability, schema admission,
CAS, constrained history and exact release pairing after original-ID reconciliation.
There is no preview, generic-submit fallback or second transaction algorithm.
Inspection uses the same connection-owned body as public get_typed_revision,
including its direct ArtifactStore verifier, accepted local typed decoding and
detached returns. It reports only selected direct verification.

Before opening the store or entering submission, the saved request alone reserves
the complete ordered receipt, using its exact submission ID/provenance/member pairs,
a 64-character fingerprint placeholder, maximum signed-64-bit event ID and
`9999-12-31T23:59:59.999999Z`. Membership/receipt limits and the complete success
result with actual normalized paths and LF must fit. These are sizing placeholders,
never emitted receipts. No target/head/receipt/artifact lookup builds this bound.
The returned original receipt alone supplies output. A returned receipt immediately
marks acknowledgement; conversion, observation or close failures after it are
uncertain, with no automatic retry or rollback claim.

Identical locally valid requests acknowledge the same original receipt despite
head advance, unavailable/damaged direct bytes or damaged target/history metadata
where opening still succeeds. Generic-original Tool requests are acknowledgement
only; they are never retrospectively typed-admitted. Changed locally valid used
IDs conflict before availability. Malformed or locally over-limit retries fail
locally before reconciliation. Fresh failures are atomic under the existing store
contract; published inert objects are not destructively cleaned up.

## Closed results and diagnostics

Stdout contains one compact sorted-key ASCII-escaped JSON document plus LF. Array
order is retained. The outer object has exactly format=`research_pipeline.cli_result`,
version=1, command, status=`ok` or `absent`, and result. Complete acknowledgement
requires draining short writes and successful stdout flush and close.

`inspect-tool-record` result has exactly store, kind, record_id, revision, envelope,
content, commit and direct_artifacts. store is the normalized explicitly configured
runtime; selections equal the request. envelope is the complete detached envelope;
content is the complete decoded wire document. commit has exactly submission_id,
committed_at and fingerprint. direct_artifacts is exactly
`{"status":"verified","count":N}`, including zero. Missing exact revisions
retain selections/store, set envelope/content/commit/direct_artifacts to null,
use outer status `absent`, exit 3, and emit no stderr.

`submit-tool-records` result has exactly store, batch, submission_id and receipt.
batch is the normalized absolute saved path. receipt has exactly submission_id,
fingerprint, event_id, committed_at, provenance and ordered revisions (arrays of
[record_id, revision]). No flags for fresh/replayed/admitted, current heads,
authenticated identity, permission, scientific summary or artifact bytes are added.

Diagnostics use exactly format=`research_pipeline.cli_diagnostic`, version=1,
command, code, message and context, capped at 65536 ASCII bytes including LF.
New-command context has exactly config, batch, kind, record_id, revision,
submission_id and next_action; unknown values are null, and batch is null for
inspection. Established paths are normalized. The runtime is deliberately omitted
so two worst-case escaped 4096-byte paths fit the cap. Exact identities/paths are
reserved before bounded explanatory text. Guidance refers to context fields
without repeating potentially large paths. Abrupt termination may emit nothing.

Precedence: argv; stable configuration/layout/exclusion checks; bounded batch and
local decoding or selected metadata/kind bounds; submission receipt/output
reservation; store operations; final held-observation/close checks; stdout
acknowledgement. Existing codecs retain their own stage precedence. Earlier held
observations are checked when a later acquisition/operation fails. After a returned
receipt, observation, close and conversion failures take uncertain precedence.

| Exit | Codes and meaning |
| ---: | --- |
| 0 | Complete successful acknowledgement |
| 2 | Usage: missing/unknown/repeated/abbreviated options or malformed numeric argv |
| 3 | `missing`: initially absent explicit batch/runtime; deliberate absent exact revision has stdout result and no stderr |
| 4 | `conflict`: RevisionConflictError or SubmissionConflictError |
| 5 | `invalid_input`, `unsafe_layout`, `limit_exceeded`: controls, local typed values, unsupported kinds/formats, independent caller/codec ceilings |
| 6 | `integrity_error`: corrupt selected canonical metadata/direct bytes or fresh ReferenceResolutionError; `operational_error`: opening/read-only database/busy/I/O/interruption; read-only/help `output_failed` |
| 7 | `effects_uncertain`: unclassified database/busy/I/O/interruption after submit entry, or post-return conversion/observation/close loss; submission `output_failed` for write/flush/close acknowledgement loss |

Known typed refusal classes retain their conflict/input/integrity classifications
after submission entry. The public API does not expose transaction stage for other
failures: the CLI conservatively reports uncertainty, never parses exception prose
to invent proof of rollback. Actual tests independently observe metadata effects.
Artifact absence/integrity remains distinct from genuine I/O by types/chained errno.

## Saved-control and original-ID recovery

Retain the exact original config, batch and submission ID and use the same runtime:

```bash
python3 -B -m research_pipeline inspect-receipt --config /exact/saved/config.json --submission-id original-id
python3 -B -m research_pipeline submit-tool-records --config /exact/saved/config.json --batch /exact/saved/batch.json
```

For example, if the saved request used larger allowances, carry sufficient
matching receipt/output/local limits through both routes:

```bash
python3 -B -m research_pipeline inspect-receipt --config /exact/saved/config.json --submission-id original-id --max-control-bytes 1048576 --max-metadata-bytes 16777216 --max-receipt-records 4096 --max-output-bytes 16777216
python3 -B -m research_pipeline submit-tool-records --config /exact/saved/config.json --batch /exact/saved/batch.json --max-control-bytes 1048576 --max-batch-bytes 16777216 --max-records 4096 --max-receipt-records 4096 --max-receipt-bytes 16777216 --max-metadata-bytes 16777216 --max-output-bytes 16777216 --max-envelope-bytes 4194304 --max-links 65536 --max-provenance-bytes 1048576 --max-file-bytes 1073741824 --max-total-bytes 4294967296
```

The actual request must still satisfy the hard codec/store ceilings. Save every
chosen allowance with the controls. Receipt inspection is metadata observation,
not request equality, typed certification, authentication or authority. An absent
receipt alone does not authorize changing the request. Reconciliation can fail if
controls are lost/changed, limits insufficient or the runtime cannot safely open.
Never automatically retry, choose a new ID, change expected heads, regenerate
provenance, clean up evidence or claim rollback. Read-only output failure requires
repeating the exact inspection with the same config/kind/ID/revision/limits and
discarding all partial output.

Creator, assessor and nested reporter declarations remain distinct unauthenticated
reports. Hashes pin declarations/bytes, not scientific truth. Inspection checks
selected local coherence and direct bytes, without history/pairing or past typed
admission. Submission adds no authenticated enablement, permission, qualification,
current lifecycle selection, scientific support or execution authority. Current
external operating authority and all remaining D04 admission/isolation/report gates,
D05 duties, all 94 requirements, 13 FOLLOWON criteria, M0-E/M0-S, live evidence and
human scientific/release acceptance remain mandatory. This slice does not complete
D05 or the product.

## Executable private-store example

Run the exact block with candidate source on PYTHONPATH and temporary storage
outside the checkout/exclusions. It uses only product APIs and the standard
library, supplies every provenance literally and prepares a prior constrained
manifest and inert bytes. It commits an assessment before its release, inspects
a reopened exact typed revision, recovers the original receipt, retries the
identical saved request and proves atomic refusal of a mismatched pair. Nothing
is executed from the assessed material; no credentials, services or environment
discovery is needed. A new test extracts this exact delimited block verbatim.

<!-- tool-record-cli-example:start -->
```python
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.resources import Dimension
from research_pipeline.work_product import WorkProductFile, WorkProductManifest, encode_envelope as manifest_envelope
from research_pipeline.tool_release_envelope import encode_envelope as release_envelope
from research_pipeline.store import RecordStore, ReferenceResolutionError
from research_pipeline.tool_release import ToolRelease


def K(value):
    """Declare a known fact, preserving empty strings, empty lists, null entry and zero."""
    return {"state": "known", "value": value, "reason": None}


def U(reason, state="unknown"):
    """Keep absent knowledge or unavailable information explicit and reasoned."""
    return {"state": state, "value": None, "reason": reason}


def pin(data):
    """Describe synthetic in-memory bytes without opening or executing anything."""
    return ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))


def no_activity():
    """Report no inner activity while making clear this is not an execution receipt."""
    return {"state": "none", "runtime": K(""), "providers": K([]),
            "description": K("No inner model or delegated activity is declared."),
            "visibility": "complete", "limitations": K(["No usage was measured."])}


def interface(name, description):
    """Describe ordered coordinate rows through inert authored labels."""
    return {"description": K(description), "fields": K([
        {"name": name, "type": "float64", "shape": K(["N ordered rows"]),
         "presence": "required", "description": K("Coordinate in metres."),
         "artifact_conventions": K(["UTF-8 decimal rows in original order."])}])}


implementation_file = WorkProductFile("src/affine.py", pin(b"# synthetic affine bytes; never executed\n"))
adapter_file = WorkProductFile("client.py", pin(b"# synthetic client description; never executed\n"))
units = {"local_time": "nanosecond", "local_compute": "cpu_nanosecond",
         "local_storage": "byte", "model_input_tokens": "token",
         "model_output_tokens": "token", "model_calls": "call", "tool_calls": "call"}
extra_units = {"memory_bytes": "byte", "output_bytes": "byte",
               "context_capacity_tokens": "token", "per_call_output_tokens": "token",
               "model_concurrency": "concurrent_call", "descendant_jobs": "job",
               "retries": "retry", "repairs": "repair"}
bounds = []
for name, unit in {**units, **extra_units}.items():
    dimension = Dimension("dim_" + name, name, unit, None, 1) if name in units else None
    bounds.append({"name": name, "dimension": dimension, "unit": unit,
                   "quantity": K(0), "mode": "claimed_hard", "enforceability": "unknown",
                   "mechanism": U("No enforcement was inspected."),
                   "limitations": K(["Zero is a declaration, not an available allocation."])})

local_sections = {
    "identity": {
        "tool_id": "affine_example", "display_name": "Affine transformation α",
        "release_label": K("example 1"), "origin": "researcher_supplied",
        "supplier": K(["Example researcher"]), "developer": K(["Example author"]),
        "declared_by": K("Example researcher"), "declared_at": K("2026-10-30T12:00:00Z"),
        "provenance_records": K([]),
        "access": {"status": "available", "detail": "Synthetic bytes are staged in this private runtime; no execution is asserted."},
        "license": K("Synthetic example text only; no external license is asserted."),
        "implementation": {
            "identity": K("affine y = 2*x"), "reported_version": K("example-1"),
            "artifacts": K([implementation_file]),
            "source_records": K([RecordReference("implementation", 1, "implementation_source", "work_product_manifest")]),
            "observability": "pinned_local",
            "limitations": K(["Synthetic bytes have not been run or scientifically qualified."])},
        "readme": """# Local affine release
Identity: researcher-supplied synthetic bytes, with exact artifact and source pins.
Invocation: a descriptive client consumes ordered coordinate rows in metres.
Scientific meaning: y=2*x; floating-point roundoff and overflow remain limitations.
Effects: input reading and output writing are requested descriptions, not permission.
Resources/recovery: zero unverified maxima; uncertain completion retains liability.
Evidence: no executed self-test or qualification is supplied.
Reproducibility: exact bytes do not prove a suitable environment or authentic output.
"""},
    "invocation": {
        "kind": "local_program",
        "adapter": {"adapter_id": "affine_client", "version": K("client-1"),
                    "description": K("Inert client declaration for ordered rows."),
                    "files": K([adapter_file]), "entry_file": K("client.py"),
                    "entry_point": K("python client.py --input rows.txt")},
        "configuration": K([{"name": "slope", "value": "2"}, {"name": "note", "value": ""}]),
        "inputs": interface("x", "Input coordinate rows."),
        "outputs": interface("y", "Transformed coordinate rows."),
        "artifact_conventions": K(["Preserve row order and explicit units."]),
        "mode": "synchronous", "mode_detail": K("One complete result is expected per call."),
        "environment_requirements": K(["Future execution needs an independently verified Python environment."])},
    "scientific_meaning": {
        "equations_or_transformations": K(["y = 2*x; this is a transformation, not a fit."]),
        "units": K(["x and y in metres; slope dimensionless."]),
        "conventions": K(["Ordered rows; no reordering or interpolation."]),
        "input_domains": K(["Finite real coordinates representable in binary64."]),
        "output_domains": K(["Finite results only; overflow is a failure."]),
        "parameter_regimes": K(["Fixed slope 2; no asymptotic approximation."]),
        "boundary_conditions": K(["No boundary value problem is solved."]),
        "approximations": K(["Binary64 roundoff; no interval certificate."]),
        "error_claims": K(["No certified numerical error bound is supplied."]),
        "success_meaning": K(["A returned number would not establish scientific support."]),
        "failure_conditions": K(["Nonfinite input or overflow invalidates the declared use."])},
    "effects_authority": {
        "filesystem_read": K(["selected input rows"]),
        "filesystem_write": K(["selected output file"]), "network_destinations": K([]),
        "credential_references": K([]), "external_effects": K([]), "child_tools": K([]),
        "model_activity": no_activity(), "delegated_activity": no_activity(),
        "delegation_contract": {name: K("") for name in (
            "assignment", "input_artifacts_and_context", "acceptance_criteria", "deliverables",
            "descendant_scope", "backend_state_and_run_identity", "waiting_parent_behavior")}},
    "resources_recovery": {
        "bounds": bounds,
        "recovery": {"cancellation": U("No running job or cancellation observation exists."),
                     "checkpointing": K("No checkpoint protocol is declared."),
                     "replay_safety": "conditional", "replay_conditions": K("Require exact inputs and a fresh output destination."),
                     "uncertain_completion": K("Retain liability and reconcile; do not infer safe replacement execution."),
                     "descendant_cancellation": K("No descendants declared; termination is not certified."),
                     "reconciliation": U("No execution receipt exists.", "unavailable")},
        "nested_accounting": {"basis": "exclusive", "visibility": "complete", "limitations": K(["Only declarations; no measured use."])}},
    "evidence_limitations": {
        "intended_uses": K(["Demonstrate an affine contract with explicit limitations."]),
        "reported_qualified_applicability": K(["No independently qualified applicability is claimed."]),
        "qualification_reports": K([]), "self_tests": K([]), "evidence": K([]), "issues": K([]),
        "tested_environments": U("No environment was tested."), "tested_cases": K([]),
        "known_failures": K(["Overflow is outside the declared successful domain."]),
        "limitations": K(["A manifest and synthetic byte hashes cannot establish scientific validity."])},
    "reproducibility": {
        "dependencies": K([]), "dependency_artifacts": K([]), "dependency_records": K([]),
        "environment": U("No execution environment was inspected."), "determinism": "conditional",
        "randomness": K([]), "output_provenance": K(["Future output receipts must link exact input/output artifact identities."]),
        "replay_limits": K(["Matching bytes alone do not establish matching execution environments."])}
}

from research_pipeline.tool_assessment import ToolAssessment
from research_pipeline.tool_assessment_envelope import encode_envelope as assessment_envelope

# The constrained implementation manifest is prepared before the Tool batch.
# Both implementation and adapter bytes remain inert throughout this example.


def attribution(actor):
    """Keep each supplied reporter independent from the archival creator."""
    return {"actor": K(actor), "reported_at": K("2026-11-04T10:00:00Z"), "origin": "synthetic"}


def independence():
    """Describe shared exposure without claiming actual independent verification."""
    return {"requested_mode": K("proof_blind_reconstruction"),
            "reported_mode": K("candidate_aware_audit"),
            **{name: K(["Same supplied implementation was visible."]) for name in (
                "shared_formulation", "shared_sources", "shared_lemmas", "shared_method",
                "shared_implementation", "shared_communications", "limitations")}}


def evidence(configuration):
    """Supply an attributed assertion with a real inert attachment and no execution receipt."""
    return {"basis": "assessor_assertion", "attribution": attribution("Separate evidence reporter"),
            "statement": K("Supplied finite examples do not cover a continuum error bound."),
            "records": K([]), "artifacts": K([copy.deepcopy(configuration)]),
            "resource_usage": U("No authentic usage observation."),
            "unresolved_liabilities": U("No authentic liability settlement.", "unavailable"),
            "independence": independence(), "limitations": K(["Synthetic report only."])}


def report(outcome, configuration):
    """Keep separately reported qualification outcomes without policy interpretation."""
    return {"outcome": outcome, "attribution": attribution("Qualification reporter"),
            "scope": K(["Finite binary64 coordinate examples in metres."]),
            "rationale": K("Supplied scoped report; no scientific acceptance."),
            "decisions": K([]), "evidence": K([evidence(configuration)]),
            "limitations": U("Unexamined cases remain unknown.")}


def assessment_document(release, configuration):
    """Describe exact target/environment, a failed scientific check and separate reports."""
    permission = report("fail", configuration)
    del permission["outcome"]
    permission.update(status="denied")
    lifecycle = report("inconclusive", configuration)
    del lifecycle["outcome"]
    lifecycle.update(status="withdrawn", reason_category="scientific_defect",
                     replacement=U("No replacement is declared."), supersedes=K([]),
                     superseded_by=U("No later assessment is declared."))
    check = {"check_id": "continuum_bound", "dimension": "scientific_applicability",
             "basis": "assessor_assertion", "attribution": attribution("Check reporter"),
             "outcome": "fail", "scope": K(["Continuum error bound."]),
             "method": K("Compare the supplied finite-case claim with its stated domain."),
             "expected": K("A uniform error bound."), "observed": K("Only finite cases supplied."),
             "definition_records": K([]), "definition_artifacts": K([copy.deepcopy(configuration)]),
             "evidence": K([evidence(configuration)]), "independence": independence(),
             "limitations": K(["No assessed material was executed."])}
    return {"format": "research_pipeline.tool_assessment_content", "version": 1,
            "kind": "tool_assessment", "assessment_id": "affine_assessment",
            "attribution": attribution("Top-level supplied assessor"),
            "target": {"release": RecordReference(release.tool_id, 1, "assessed_release", "tool_release").to_dict(),
                       "release_id": release.release_id},
            "environment": {"kind": "local", "identity": K("Supplied frozen configuration description"),
                "reported_version": U("No running environment inspected."),
                "implementation_version": U("No runtime discovered."),
                "configuration": K([{"name": "precision", "value": "binary64"}]),
                "observability": "pinned_description", "records": K([]),
                "artifacts": K([copy.deepcopy(configuration)]), "dependencies": K([]),
                "limitations": K(["A description does not prove a matching runtime."])},
            "scope": {"intended_uses": K(["Affine coordinate conversion."]),
                      "tested_scope": K(["Supplied finite cases only."])},
            "checks": K([check]), "reviews": K([]), "issues": K([]),
            "limitations": K(["Passive supplied data only."]), "execution_permission": permission,
            "qualification": {"operational_interface": report("pass", configuration),
                              "software_behavior": report("pass", configuration),
                              "scientific_applicability": report("fail", configuration)},
            "lifecycle": lifecycle}


creator = CreationProvenance("archival-creator", "2026-11-05T10:00:00.000000Z",
    {"purpose": "passive CLI", "synthetic": True, "signed": -2, "fraction": 0.25})
controller = CreationProvenance("submission-controller", "2026-11-05T10:01:00.000000Z", {"purpose": "example"})


def save(path, value):
    """Create an explicit private UTF-8 control; these bytes must be retained for recovery."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(0o600)


def cli(*argv, status=0):
    """Invoke the actual source-local CLI, requiring complete output or one expected refusal."""
    result = subprocess.run([sys.executable, "-B", "-m", "research_pipeline", *map(str, argv)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == status, result.stderr
    if status == 0:
        assert result.stderr == ""
        return json.loads(result.stdout)["result"]
    assert result.stdout == ""
    return json.loads(result.stderr)


with TemporaryDirectory(prefix="tool-cli-example-") as temporary:
    parent = Path(temporary)
    parent.chmod(0o700)
    runtime, config, batch = parent / "runtime", parent / "config.json", parent / "batch.json"
    with RecordStore.create(runtime) as store:
        implementation = store.put_artifact(b"# synthetic affine bytes; never executed\n")
        adapter = store.put_artifact(b"# synthetic client description; never executed\n")
        assert implementation == implementation_file.artifact
        assert adapter == adapter_file.artifact
        attachment = store.put_artifact(b"precision=binary64; inert description\n").to_dict()
        manifest = WorkProductManifest(
            "program", "Inert affine implementation", "Preserve supplied bytes",
            ["Example author"], None, None, None, None, [], [], None, [],
            [implementation_file], "src/affine.py", ["Not executed or qualified"])
        prior = manifest_envelope("implementation", 1, manifest, creator)
        store.submit_typed(Submission("prior-implementation", controller, [prior], {"implementation": 0}))
        release = ToolRelease(**local_sections)
        doc = assessment_document(release, attachment)
        value = ToolAssessment.from_dict(doc)
        assessed = assessment_envelope(value.assessment_id, 1, value, creator)
        released = release_envelope(release.tool_id, 1, release, creator)
        saved = Submission("cli-original", controller, [assessed, released],
                           {value.assessment_id: 0, release.tool_id: 0})
    save(config, {"format": "research_pipeline.cli_config", "version": 1,
                  "store": str(runtime), "protected_roots": []})
    save(batch, {"format": "research_pipeline.cli_tool_batch", "version": 1, "submission": saved.to_dict()})
    receipt = cli("submit-tool-records", "--config", config, "--batch", batch)["receipt"]
    assert receipt["revisions"] == [[value.assessment_id, 1], [release.tool_id, 1]]
    exact = cli("inspect-tool-record", "--config", config, "--kind", "tool_assessment",
                "--record-id", value.assessment_id, "--revision", "1")
    assert exact["content"] == doc and exact["envelope"] == assessed.to_dict()
    assert exact["direct_artifacts"] == {"status": "verified", "count": 1}
    with RecordStore.open(runtime) as store:
        envelope, content = store.get_typed_revision(value.assessment_id, 1)
        assert envelope == assessed and content.to_dict() == doc
        events = store.audit_events()
        historical_release = store.get_typed_revision(release.tool_id, 1)[0]
    observed = cli("inspect-receipt", "--config", config, "--submission-id", "cli-original")
    assert observed["receipt"] == receipt
    assert cli("submit-tool-records", "--config", config, "--batch", batch)["receipt"] == receipt
    bad = copy.deepcopy(doc)
    bad["assessment_id"] = "mismatched_assessment"
    bad["target"]["release_id"] = "sha256:" + "0" * 64
    rejected = assessment_envelope("mismatched_assessment", 1, ToolAssessment.from_dict(bad), creator)
    wrong = Submission("mismatched-request", controller, [rejected], {"mismatched_assessment": 0})
    bad_batch = parent / "mismatched.json"
    save(bad_batch, {"format": "research_pipeline.cli_tool_batch", "version": 1, "submission": wrong.to_dict()})
    diagnostic = cli("submit-tool-records", "--config", config, "--batch", bad_batch, status=6)
    assert diagnostic["code"] == "integrity_error"
    with RecordStore.open(runtime) as store:
        assert store.get_submission("mismatched-request") is None
        assert store.head("mismatched_assessment") is None
        assert store.audit_events() == events
        assert store.get_typed_revision(value.assessment_id, 1)[0] == assessed
        assert store.get_typed_revision("implementation", 1)[0] == prior
        assert store.get_typed_revision(release.tool_id, 1)[0] == historical_release
        assert store.get_submission("cli-original").to_dict() == receipt
    assert cli("submit-tool-records", "--config", config, "--batch", batch)["receipt"] == receipt
    with RecordStore.open(runtime) as store:
        assert store.audit_events() == events
print("Mixed CLI commit, reopened exact inspection, original-ID recovery and atomic refusal agree.")
```
<!-- tool-record-cli-example:end -->
