# Passive versioned Tool releases

`research_pipeline.tool_release` describes one exact reusable release before
registration, admission, qualification or execution. Local consistency and a content
identity authenticate neither historical records nor available bytes. There is no
store dispatch, envelope codec, `submit_typed` support, reference resolver, registry,
current pointer, installation, dependency discovery or execution in this API.

## Public API

The public names are `ToolRelease`, `ToolReleaseLimits`,
`ToolReleaseValidationError`, `ToolReleaseLimitError`, `decode_content`,
`dumps_content` and `loads_content`:

```text
ToolRelease(*, identity: dict, invocation: dict, scientific_meaning: dict,
            effects_authority: dict, resources_recovery: dict,
            evidence_limitations: dict, reproducibility: dict,
            limits: ToolReleaseLimits | None = None)
ToolRelease.to_dict(self, *, limits=None) -> dict
ToolRelease.from_dict(cls, value: dict, *, limits=None) -> ToolRelease
decode_content(value: dict, *, limits=None) -> ToolRelease
dumps_content(value: ToolRelease, *, limits=None) -> str
loads_content(data: str | bytes, *, limits=None) -> ToolRelease
```

`tool_id` and `release_id` are read-only properties. Construction retains one private
canonical JSON string, never caller dictionaries, mutable nested objects or limits.
`to_dict` produces a fresh ordinary wire tree. All consumption boundaries revalidate
the complete retained content and its canonicality, including equality and properties.
Equality compares revalidated exact releases; releases are unhashable. Properties
and equality use fresh default ceilings. Use `to_dict(limits=...)` when imposing
smaller ceilings. Inherited construction/serialization rejects subclass receivers
without calling their overrides. Exact typed objects are read through their raw
fields; their serialization methods and cached identities are not trusted.

## Common notation and scalars

Every object below is closed: all listed fields are required, even nullable fields
and known-empty declarations. There are no factual defaults or extension mappings.
Constructor section objects must be ordinary `dict`; collections must be ordinary
`list` or `tuple`. Wire objects and arrays must be ordinary `dict` and `list`.
Subclasses, lookalikes, generators, sets and arbitrary objects are rejected.

`F(T)` means exactly `{state, value, reason}`:

| state | value | reason |
| --- | --- | --- |
| `known` | the indicated T | null |
| `unknown` | null | nonblank explanation of missing knowledge |
| `unavailable` | null | nonblank explanation of why the fact cannot be obtained |

Unknown does not mean unavailable. Neither means empty. Known empty text, lists
and integer zero remain literal values where T permits them. The only known-null
payload is `F(optional path)`: null explicitly selects no bundle entry file.

Text is an exact Python `str` containing Unicode scalar values. Spelling, authored
whitespace, Markdown, HTML, links and command-like text are preserved without
interpretation. Identifiers, named fields used as identifiers, human display names
and required explanations are nonblank. Opaque IDs follow `domain._identifier`:
1–128 ASCII letters/digits/underscore/hyphen, beginning with a letter or digit.
Narrative `F(text)` may be deliberately empty. Integers are exact `int` from zero
through `2**63-1`, except positive reference revisions and dimension scales.
Booleans, floats, numerical aliases and nonfinite values are rejected everywhere.
An authored interface label such as `float64` remains legal text.

## Seven closed sections

### Identity and origin

`identity` has exactly:

| Field | Type or vocabulary |
| --- | --- |
| tool_id | opaque ID |
| display_name | nonblank text |
| release_label | F(text) |
| origin | bundled, researcher_supplied, research_generated |
| supplier, developer | F(list[text]) |
| declared_by | F(text) |
| declared_at | F(text); known nonempty values use domain UTC timestamp syntax |
| provenance_records | F(list[RecordReference]); reported_provenance; any explicit supported target_kind |
| access | `{status, detail}`; status available/restricted/unavailable/unknown; detail nonblank text |
| license | F(text) |
| implementation | object specified below |
| readme | nonblank inert Markdown |

`declared_at` uses `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` and a valid calendar date. The
supplied spelling is retained, including fractional precision. Missing dates never
read a clock. Display labels do not substitute for tool or release identities.
Access is reported access, not tested availability or permission.

`implementation` has exactly `identity: F(text)`, `reported_version: F(text)`,
`artifacts: F(list[WorkProductFile])`, `source_records: F(list[RecordReference])`,
`observability`, and `limitations: F(list[text])`. Source relationships are
`implementation_source`, with target kind `source` or `work_product_manifest`.
Observability is `pinned_local`, `reported_version_only`, `opaque`, `unknown` or
`unavailable`. `pinned_local` requires known nonempty artifacts;
`reported_version_only` requires a known nonblank reported version.

A `remote_service` cannot claim `pinned_local` or nonempty implementation artifacts.
Its artifacts must be known empty, unknown or unavailable. Local clients belong in
`invocation.adapter.files`; exact source descriptions may remain source records.
Remote implementation limitations and reproducibility replay limits cannot be
known empty; reasoned unknown/unavailable declarations are valid. Inaccessible and
opaque tools remain representable. A README should explain all seven areas, but
headings are not checked for semantic completeness or qualification.

### Invocation

`invocation` has exactly `kind`, `adapter`, `configuration`, `inputs`, `outputs`,
`artifact_conventions`, `mode`, `mode_detail`, `environment_requirements`.

- `kind`: local_program, local_callable, remote_service, composite_workflow.
- `adapter`: exactly `{adapter_id, version, description, files, entry_file,
  entry_point}`. `adapter_id` is an opaque ID; version, description and entry_point
  are F(text); files is F(list[WorkProductFile]); entry_file is F(optional path).
  A known non-null entry file requires known files and exact path membership.
  A command or callable description is never imported, resolved or executed.
- `configuration`: F(list[setting]); setting is exactly `{name, value}` with
  unique nonblank name and ordinary string value, including empty string. These
  are inert non-secret settings, not instructions or arbitrary executable values.
- `inputs` and `outputs`: each exactly `{description, fields}`, with description
  F(text) and fields F(list[parameter]). Parameter is exactly `{name, type, shape,
  presence, description, artifact_conventions}`. Name is nonblank and unique in
  that interface; type is a nonblank authored label; shape and artifact_conventions
  are F(list[text]); description is F(text); presence is required/optional/conditional.
  Order is retained. Nested shapes are described in text, never interpreted as a
  universal schema language.
- `artifact_conventions` and `environment_requirements`: F(list[text]).
- `mode`: synchronous, asynchronous, either, unknown; `mode_detail`: F(text).

### Scientific meaning

`scientific_meaning` has exactly these fields, each F(list[text]):
`equations_or_transformations`, `units`, `conventions`, `input_domains`,
`output_domains`, `parameter_regimes`, `boundary_conditions`, `approximations`,
`error_claims`, `success_meaning`, `failure_conditions`.

Statements, equations, qualifications and deliberate empty lists retain their
order and actual text. Claimed scientific semantics remain separate from interface
shape and evidence. No calculation, interpretation, inferred applicability or
promotion to support occurs.

### Effects and authority

`effects_authority` has exactly `filesystem_read`, `filesystem_write`,
`network_destinations`, `credential_references`, `external_effects`, `child_tools`,
`model_activity`, `delegated_activity`, `delegation_contract`.

Filesystem scopes, network destinations and external effects are F(list[text]).
They are descriptions, not paths to open, URLs to fetch or permissions. Only bundle
paths undergo logical-path validation. Credential references are F(list[credential]);
credential is exactly `{credential_id, purpose}`, with unique opaque ID and nonblank
purpose. There is no token, password, credential value or environment-lookup field.
Syntax cannot identify every secret someone might paste into authored prose.
Child tools are F(list[RecordReference]), relationship `child_tool`, target kind
`tool_release`. Detached links do not authenticate registration.

Both activity objects have exactly `{state, runtime, providers, description,
visibility, limitations}`. State is none/declared/unknown/unobserved. Runtime and
description are F(text); providers and limitations are F(list[text]). Visibility
is complete/partial/unobserved/unknown/unavailable. State `none` requires known empty
runtime and providers. State `declared` requires a known nonblank description.
Unknown and unobserved remain distinct from none. All other supplied statements
remain literal. These are claimed activity/observability, not usage receipts.

`delegation_contract` has exactly these F(text) fields: `assignment`,
`input_artifacts_and_context`, `acceptance_criteria`, `deliverables`,
`descendant_scope`, `backend_state_and_run_identity`, `waiting_parent_behavior`.
They describe an optional expected boundary, exact deliverable identity and
backend-owned state. They are not an assignment, allocation, job ID or execution
receipt. Known empty fields permit no delegation. Effects never change authority,
enable tools, allocate resources or establish descendant termination.

### Resources and recovery

`resources_recovery` has exactly `{bounds, recovery, nested_accounting}`. Bounds is
an ordered list of objects with exactly `{name, dimension, unit, quantity, mode,
enforceability, mechanism, limitations}`. Quantity is F(integer); mechanism F(text);
limitations F(list[text]). Mode is claimed_hard/monitored_target/unknown.
Enforceability is reported_enforceable/not_enforceable/unknown/unavailable.

`claimed_hard` requires a known quantity and cannot say `not_enforceable`.
`reported_enforceable` requires a known nonblank mechanism. A claimed hard maximum
with unknown/unavailable enforceability stays unverified; it is never an enforced
ceiling. Missing quantities are not replaced by zero or infinity.

Exactly one of each required name below must occur. Optional `monetary` entries
use distinct currencies. No required name or monetary currency may repeat.

| name | dimension | unit | Meaning of maximum |
| --- | --- | --- | --- |
| local_time | matching Dimension | nanosecond | per invocation |
| local_compute | matching Dimension | cpu_nanosecond | per invocation |
| local_storage | matching Dimension | byte | per invocation |
| model_input_tokens | matching Dimension | token | cumulative per invocation |
| model_output_tokens | matching Dimension | token | cumulative per invocation |
| model_calls | matching Dimension | call | cumulative per invocation |
| tool_calls | matching Dimension | call | cumulative per invocation |
| memory_bytes | null | byte | peak memory |
| output_bytes | null | byte | complete produced output |
| context_capacity_tokens | null | token | per model request |
| per_call_output_tokens | null | token | per model request |
| model_concurrency | null | concurrent_call | simultaneous inner model calls |
| descendant_jobs | null | job | descendant count |
| retries | null | retry | optional internal repetition |
| repairs | null | repair | optional internal repair |
| monetary | monetary Dimension | currency_quantum | per-invocation currency quantity/scale |

The first seven use existing `resources.UNITS`. No new ledger dimensions are
introduced. Every non-null bound unit equals its dimension unit. Dimension IDs
cannot be reused with different definitions. Bound order is retained, not sorted.
A positive allowance does not assert activity occurred; it can coexist with none
activity. All maxima are declarations, not fresh allocations.

`recovery` has exactly `cancellation`, `checkpointing`, `replay_safety`,
`replay_conditions`, `uncertain_completion`, `descendant_cancellation`,
`reconciliation`. Replay safety is safe/unsafe/conditional/unknown/unavailable;
all other fields are F(text). `nested_accounting` is exactly `{basis, visibility,
limitations}`: basis exclusive/inclusive/mixed/unknown/unavailable; visibility
complete/partial/unobserved/unknown/unavailable; limitations F(list[text]).
Uncertainty cannot release liability, justify replacement execution or certify
stopped descendants. No recovery or accounting policy is enforced here.

### Evidence and limitations

`evidence_limitations` has exactly the following fields:

| Field | Type and reference rule |
| --- | --- |
| intended_uses, reported_qualified_applicability | F(list[text]) |
| qualification_reports | F(list[RecordReference]); reported_qualification; tool_assessment |
| self_tests | F(list[ArtifactReference]) |
| evidence | F(list[RecordReference]); reported_evidence; evidence |
| issues | F(list[RecordReference]); reported_issue; issue |
| tested_environments, tested_cases, known_failures, limitations | F(list[text]) |

Reported applicability is attributed prose. No qualified, trusted, enabled,
support-status or lifecycle flag exists. Builder statements, self-tests and
reported assessment links authenticate or qualify nothing by themselves.

### Reproducibility

`reproducibility` has exactly `dependencies`, `dependency_artifacts`,
`dependency_records`, `environment`, `determinism`, `randomness`, `output_provenance`,
`replay_limits`. Dependency artifacts are F(list[ArtifactReference]); dependency
records are F(list[RecordReference]) with `build_dependency` and any explicit
supported target kind. Determinism is deterministic/stochastic/conditional/unknown/
unavailable. All remaining fields are F(list[text]). No package resolution,
environment inspection or execution occurs. Remote access/version/replay limits
remain visible even when the local adapter and configuration have exact identities.

## References and logical paths

Constructor reference positions require the exact existing `domain.ArtifactReference`,
`domain.RecordReference`, `work_product.WorkProductFile` and `resources.Dimension`
classes. Wire positions require complete ordinary dictionaries, never optional
predecessor-codec shorthand:

- ArtifactReference: exactly `{digest, size}`; 64 lowercase hexadecimal SHA-256
  digits without a prefix, nonnegative size through `2**63-1`.
- RecordReference: exactly `{record_id, revision, relationship, target_kind}`;
  opaque IDs/relationship, revision 1 through `2**63-1`, explicit non-null supported
  kind. Supported kinds are research_context, claim, justification, evidence,
  task_specification, project, run, corpus_manifest, branch, source,
  work_product_manifest, tool_release, tool_assessment, issue, review,
  promotion_eligibility, decision, attempt, tool_execution, event. Field-specific
  relationship/target rules above also apply.
- WorkProductFile: exactly `{path, artifact}`.
- Dimension: exactly `{dimension_id, kind, unit, currency, scale}`. ID is opaque.
  For the seven existing kinds currency is null and scale is 1. Monetary dimensions
  use kind monetary, unit currency_quantum, three uppercase ASCII currency letters,
  and integer scale 1 through `10**9`.

Repeated references remain ordered and count on every occurrence. Across the
complete release, an artifact digest cannot have different sizes, and the same
record ID/revision cannot have different target kinds. Rehashing cannot bypass
these checks. References are not resolved or authenticated.

Implementation and adapter files are separate bundle inventories. Each uses the
existing `work_product._path` and `_validate_paths` rules after bounded preflight:
portable relative POSIX paths, no empty/dot/parent components, absolute paths,
backslashes, control/format characters, reserved device names, trailing spaces or
dots, or forbidden portable punctuation. NFKC/casefold aliases, inconsistent shared
directory spelling, duplicate files and file/directory collisions are rejected.
Exact spelling is retained. The same path in the two distinct bundles is allowed.
A non-null entry file uses the same safety rules and exact adapter membership.
Paths are never joined to the host filesystem. Arbitrary descriptive scopes,
commands and links remain inert text, even when they resemble unsafe paths.

## Version-one wire and identities

The root has exactly `format`, `version`, `kind`, `release_id`, `adapter_identity`,
`configuration_identity`, and the seven section fields. Format is
`research_pipeline.tool_release_content`, version is the ordinary integer `1`, and
kind is `tool_release`. Constructor callers supply only sections and optional
external limits. Wire decoders require and verify all identities; they never repair
stale identities.

Canonical JSON is `json.dumps(value, sort_keys=True, separators=(',', ':'),
ensure_ascii=True, allow_nan=False)`, with no newline. Array order and decoded
string values are retained. All three identities are `sha256:` plus 64 lowercase
hexadecimal digits, hashing canonical ASCII bytes:

| Identity | Complete preimage |
| --- | --- |
| adapter_identity | invocation.adapter |
| configuration_identity | invocation.configuration, including state/value/reason |
| release_id | entire root with only release_id omitted |

The release preimage includes subordinate identities, headers, labels, README,
references and all seven sections. No placeholder is hashed into it. Fixed-width
placeholders are used only to account for generated metadata before serialization.
Equivalent mapping order and legal JSON whitespace/escaping normalize to the same
identity. Array order, authored whitespace and different unknown reasons matter.
Any changed content yields a different release identity; it does not replace an
old release or prove immutable history.

Identities pin exact declarations. Available local implementation pins are only
artifact references, whose bytes and availability still require authentication.
Neither an adapter nor configuration identity freezes a remote implementation or
makes unknown adapter bytes known. Internally consistent rehashed detached content
is a new local declaration, not authenticated history.

## Independent finite processing ceilings

`ToolReleaseLimits` is frozen and has exactly these fields. Each default is also a
hard maximum. Supply an ordinary integer from zero to that maximum; larger values
are rejected, not clamped. `None` creates fresh defaults. Supplied limits are
revalidated even after bypass mutation and are never embedded or retained.

| Field | Default and hard maximum | Accounting |
| --- | ---: | --- |
| max_wire_bytes | 1048576 | complete external JSON UTF-8 bytes, including whitespace and repetitions |
| max_canonical_bytes | 1048576 | complete canonical root, including every header, identity, key, escape and empty frame |
| max_string_chars | 16384 | decoded Unicode scalar count per string, including keys |
| max_collection_items | 256 | member count of each dictionary or list/tuple separately |
| max_references | 1024 | each ArtifactReference and RecordReference occurrence, including artifacts in files |
| max_nodes | 32768 | every container, scalar and object-key occurrence; root, null and empty containers count |
| max_depth | 24 | maximum container nesting, root container at depth one |
| max_reconstruction_units | 262144 | nodes + decoded string lengths + bundle-path prefix workload |

Reconstruction units equal nodes plus the sum of decoded string lengths (including
keys and repeated text), plus `c*(c+1)//2` for each declared bundle path with `c`
slash-separated components. Non-null adapter entry files are charged again.
This bounds existing ambiguity-check prefix construction; it is a workload index,
not measured CPU instructions. Empty framing is covered by nodes and canonical
bytes. Repeated acyclic aliases are charged again; cycles are rejected.

Bytes are size-checked before UTF-8 decoding. String inputs first use the cheap
character lower bound, then count UTF-8 bytes without allocating the full encoding.
An allocation-light lexical scan checks grammar, escapes, scalar lengths, member
counts, depth, nodes, base reconstruction units and canonical width before
`json.loads`. It combines legal supplementary surrogate-pair escapes, rejects
unpaired surrogates, bounds integer tokens before conversion, and rejects floats,
booleans and nonfinite constants. The stdlib parser additionally rejects duplicate
decoded fields at every depth. No unbounded token or pending-child list is built.

Constructor/dictionary/retained trees undergo iterative traversal with depth-sized
iterator frames before copying. Exact typed references/files/dimensions are counted
through their virtual wire fields. Aggregate reference and path-work ceilings finish
before reconstruction or path normalization. Canonical sizing computes quotes,
separators, ASCII escapes, six-character BMP and twelve-character supplementary
escapes without serializing. U+007F counts as the six-byte `\u007f` escape whether
external JSON spells it literally or escaped. Generated metadata and all three
identities count before hashing or output serialization. Work uses a fixed number
of bounded passes.
Retained text is bounded by max_canonical_bytes before parsing; max_wire_bytes
applies only to external `loads_content`, not dictionary construction or retention.

## Errors and stage order

`ToolReleaseValidationError` derives from `domain.DomainValidationError`;
`ToolReleaseLimitError` derives from it and names the violated limit field.
Missing format raises the existing `scientific.NotTypedContentError` after bounded
parsing. Unsupported formats/versions, malformed schemas, Unicode, references,
paths and identity mismatches raise ToolReleaseValidationError. Expected parser,
encoding, missing-attribute, recursion and overflow failures become domain errors
without echoing whole documents. Missing Python constructor arguments may retain
normal TypeError behavior.

The boundary order is:

1. Validate limits and outer exact types.
2. Enforce applicable input/preflight ceilings; reject illegal scalars and cycles.
3. Parse bounded wire syntax, rejecting duplicate fields.
4. Validate headers/version and all closed schemas.
5. Finish schema-specific reference/path/work checks before reconstruction and normalization.
6. Validate semantic and cross-field invariants.
7. Verify derived identities and retained canonicality.
8. Emit detached output.

Output sizing precedes every protected serialization, including hash preimages.
Earlier-stage errors win: oversized input cannot reach parsing, and contradictory
facts fail before hash mismatches. During streaming preflight, the first violation
encountered wins. Typed layouts use fixed field order; raw dictionary/wire traversal
retains supplied order. There is no global priority among simultaneous malformed
conditions.

## Runnable local and inaccessible remote example

Run this exact self-contained block with the candidate source on `PYTHONPATH`, for
example `PYTHONPATH="$PWD/implementation/src" python3 -B`, then paste the block.
No installation, file access, credentials or service are needed. Synthetic bytes
are hashed in memory and never installed or executed. The guide test executes this
block in a child process with source-local imports.

```python
import copy
import hashlib

from research_pipeline.domain import ArtifactReference, RecordReference
from research_pipeline.resources import Dimension
from research_pipeline.work_product import WorkProductFile
from research_pipeline.tool_release import ToolRelease, dumps_content, loads_content


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
        "provenance_records": K([RecordReference("supplied_package", 2, "reported_provenance", "work_product_manifest")]),
        "access": {"status": "available", "detail": "Synthetic bytes are supplied in memory; no store availability was tested."},
        "license": K("Synthetic example text only; no external license is asserted."),
        "implementation": {
            "identity": K("affine y = 2*x"), "reported_version": K("example-1"),
            "artifacts": K([implementation_file]),
            "source_records": K([RecordReference("affine_source", 4, "implementation_source", "source")]),
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

local = ToolRelease(**local_sections)
remote_sections = copy.deepcopy(local_sections)
remote_sections["identity"].update(
    tool_id="remote_affine_example", display_name="Opaque affine service",
    access={"status": "unavailable", "detail": "The illustrative remote endpoint cannot be accessed."},
    license=U("Service license terms cannot be obtained.", "unavailable"),
    readme="""# Inaccessible remote affine service
Identity: reported example-1; service implementation is opaque and unavailable.
Invocation: local client bytes describe HTTP access; they do not pin the service.
Scientific meaning: the reported affine transformation has not been verified remotely.
Effects: any network access and credential resolution need separate authorization.
Resources/recovery: no enforceable ceiling or cancellation observation is available.
Evidence: no report or self-test qualifies this service or authenticates its output.
Reproducibility: access, provider version and behavior may change; replay is unverified.
""")
remote_sections["identity"]["implementation"].update(
    artifacts=U("Remote implementation bytes cannot be obtained.", "unavailable"),
    observability="opaque", limitations=K(["Reported example-1 does not pin the running service."]))
remote_sections["invocation"]["kind"] = "remote_service"
remote_sections["invocation"]["adapter"]["entry_point"] = K("POST https://example.invalid/affine")
remote_sections["effects_authority"]["network_destinations"] = K(["https://example.invalid/affine"])
remote_sections["effects_authority"]["credential_references"] = K([
    {"credential_id": "service_access", "purpose": "Future separately authorized access; no credential value."}])
remote_sections["reproducibility"]["replay_limits"] = K([
    "Access is unavailable; provider implementation, reported version and license may change."])
remote = ToolRelease(**remote_sections)

for release in (local, remote):
    text = dumps_content(release)
    assert loads_content(text) == release
    assert loads_content(text.encode("utf-8")) == release
    assert ToolRelease.from_dict(release.to_dict()) == release
assert local.to_dict()["identity"]["implementation"]["artifacts"]["value"][0]["artifact"]["digest"] == implementation_file.artifact.digest
assert local.to_dict()["identity"]["implementation"]["source_records"]["value"][0]["revision"] == 4
assert remote.to_dict()["identity"]["implementation"]["artifacts"]["state"] == "unavailable"
assert remote.to_dict()["reproducibility"]["environment"]["state"] == "unknown"
assert local.to_dict()["reproducibility"]["dependency_records"] == K([])
changed_sections = copy.deepcopy(local_sections)
changed_sections["identity"]["release_label"] = K("example 1, amended description")
changed = ToolRelease(**changed_sections)
assert changed.release_id != local.release_id
assert changed.to_dict()["adapter_identity"] == local.to_dict()["adapter_identity"]
assert changed.to_dict()["configuration_identity"] == local.to_dict()["configuration_identity"]
print("local", local.release_id)
print("remote", remote.release_id)
print("adapter", local.to_dict()["adapter_identity"])
print("configuration", local.to_dict()["configuration_identity"])
print("Unknown environment retained; unavailable remote bytes retained; changed label changes release.")
print("Both declarations round-trip; no tool was run or qualified.")
```

The exact output is:

```text
local sha256:0f018fcdb8aa347a6f882c4251cf7724cab83043bd9314d8aeb524219078c00e
remote sha256:b7658dbc74a391229ffda005cdb33fe75a34700c8202b594540e3e62704067ac
adapter sha256:30534f9f87ced3f2ed45ff4ab7b1a9ea9a1ce234b828f221414f7b2d0c1838aa
configuration sha256:f9ae32ce018eeb53fbcea26674ce9c63ac5fb68ccb9915e585afcc440ed86753
Unknown environment retained; unavailable remote bytes retained; changed label changes release.
Both declarations round-trip; no tool was run or qualified.
```

## Later responsibilities and remaining scope

A future registry/admission boundary must authenticate exact records and bytes,
validate references and immutable history, and record separate permission,
qualification and lifecycle assessments. A future executor must verify invocation
environment, confinement, available bounds, actual remote versions, authentic
outputs, descendants, cancellation, usage and uncertain-completion recovery.
A self-test or builder-authored report cannot self-qualify a tool, enable it, or
promote its output to scientific support. No passive declaration establishes
these facts. Real selected-backend evidence is required for interoperability and
optional composite qualification claims.

This contract does not complete D04, full D05 or M0-E. Registration, canonical typed
admission, actual isolation/execution, resource enforcement, receipts, recovery,
live permissions and scientific qualification remain separate work. Focused tests
are implementation evidence only; controller validation, independent reviews,
final receipt and coordinator inspection/integration remain separate responsibilities.
