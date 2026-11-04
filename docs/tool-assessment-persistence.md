# Transactional passive Tool-assessment persistence

`RecordStore.submit_typed(Submission)` admits explicit version-one
`research_pipeline.tool_assessment_content` envelopes alongside existing typed
content. Import `ToolAssessment` and its envelope codec directly from their
submodules. `submit`, `submit_typed`, `get_typed_revision` and `capture_snapshot`
retain their signatures; there is no schema, migration, registry or admission ledger.

Creator provenance, the top-level assessor and nested reporters are separate
supplied attributions. None is filled, compared for authentication or interpreted
as a permission grant. Denied/revoked permission may coexist with operational and
software passes and scientific failure/inconclusive reports.

## References and attachments

The unchanged codec defines every ordered record occurrence and the first-digest
artifact projection. Unknown/unavailable facts add nothing; known empty remains
empty. The following roles require exact existence and declared kind only:

- `assessed_dependency`: source, work_product_manifest or tool_release.
- `reported_tool_execution`: tool_execution.
- `reported_permission_decision`, `reported_qualification_decision` and
  `reported_lifecycle_decision`: decision.

All remaining assessment roles require the corresponding decoded class and its
existing constrained closure:

| Role | Required kind/class |
| --- | --- |
| assessed_release, replacement_release | tool_release / ToolRelease, complete metadata history |
| assessed_environment, check_definition | source / Source or work_product_manifest / WorkProductManifest |
| reported_assertion | source / Source, work_product_manifest / WorkProductManifest or evidence / scientific Evidence |
| builder_self_test | work_product_manifest / WorkProductManifest or evidence / scientific Evidence |
| independent_review, reported_review | review / Review, including route-conclusion rules |
| reported_issue | issue / Issue, with affected_record links still shallow |
| supersedes_assessment, superseded_by_assessment | tool_assessment / ToolAssessment, complete metadata history |

The common evidence rules apply independently to checks, reviews, issues,
permission, each qualification dimension and lifecycle. Decision payloads never
enter authenticated operating-decision decoding merely because of a reported
slot. ToolRelease `reported_qualification` remains shallow after this extension.

Order remains assessed release; environment; dependencies; each check's definitions
and evidence; each review pin/evidence; each issue pin/evidence; permission;
operational_interface, software_behavior, scientific_applicability; lifecycle;
replacement; supersedes; superseded_by. Within each report, decisions precede
evidence. Direct artifacts follow environment, dependencies, each check's
definitions/evidence, reviews, issues, permission, the three qualification dimensions
and lifecycle. Repeated digests retain their first projected occurrence while every
content occurrence still receives size-consistency and codec accounting.

## Fresh admission, history and local inspection

Fresh admission checks each assessment's assessed and known replacement
`release_id` against its exact resolved ToolRelease content. Proposed revisions
resolve before committed metadata, so either mixed-batch order works. Heads,
actor names, timestamps and artifact hashes cannot substitute for exact pairs.

Each submitted or constrained-reached assessment requires immutable metadata
revisions N-1 through 1, with the same stable assessment_id, exact kind, canonical
content/provenance and projections, valid closure and its own release pairing.
Every revision uses its own target/environment; explicit reassessment may change
those declarations without copying earlier checks or qualifications. Explicit
lifecycle links neither replace this history nor become mandatory on revision N.
Descriptive self/cross supersession cycles are allowed. Exact caches terminate
traversal, but every incoming role/class/pairing rule still runs on cache hits.
No transitive artifact bytes are read for this metadata closure.

`get_typed_revision(id, revision)` verifies direct attachments then returns an
independent envelope and ToolAssessment for that selected revision only. It does
not inspect predecessors or target/release pairing. A coherent generically stored
assessment can therefore be inspected although fresh admission would reject its
history. Snapshot classification likewise distinguishes generic, unsupported,
malformed_typed and locally_decoded without implicit history traversal, artifact
verification, authentication or admission. Its explicit outgoing navigation and
caller limits remain unchanged. Neither operation certifies former typed admission.

## Bounds, errors, commit and recovery

Original retained fields and exact container/classes are checked before generic
serializers can normalize them. Pure content/envelope ceilings and their A–F
stage order are unchanged. Provenance retains strict generic JSON including signed
integers, booleans and finite floats; it is not subject to content scalar restrictions.

Assessment-aware work additionally bounds supplied roots and distinct exact
metadata identities to 4096, mandatory assessment/release history prefixes to
4096 revisions including revision one, and projected record plus artifact
occurrences to 32768. Cache rereads do not charge stored projections twice.
Each complete enclosing envelope is bounded to 4194304 bytes, with 67108864 bytes
of aggregate fetched/retained representations plus scratch. These are processing
accounts, not measured RAM. Permanent charges cover fetched field/link bytes,
prospective envelope framing, retained typed text, and twice the complete
prospective canonical request size. Six temporary enclosing envelope
representations protect member decoding and reconstruction.
In addition, six temporary enclosing control-object representations protect
submission provenance and expected-head parsing/reconstruction, including full
provenance details and framing. Six temporary complete fingerprint-v1 request
representations protect request serialization, canonicalization, encoding and
hashing, including exact retries. Control scratch is refunded after preparation;
request scratch is refunded before entering the transaction. Permanent charges
remain in both cases, including when protected work raises an exception.
SQL type/length/count and ordinal checks precede stored payload/link reconstruction.
Existing connection owners keep their own smaller read/history/retention budgets;
snapshot and explicit codec limits are never expanded.

Local missing discriminators retain `NotTypedContentError`; malformed/over-limit
assessment values use `ToolAssessmentValidationError` / `ToolAssessmentLimitError`.
Other input/schema failures retain `DomainValidationError`. Fresh missing,
wrong-kind, invalid constrained/history or mismatched release targets raise
`ReferenceResolutionError` with owner, role/exact target or predecessor and chained
causes. Historical work limits are chained reference failures. CAS, next revision
and stable kind conflicts retain `RevisionConflictError`; changed valid duplicates
retain `SubmissionConflictError`; absent selected revisions retain
`RecordNotFoundError`. Artifact, closed, busy, database, supplied-reader and programmer
failures keep their established identities. Necessary raw count/type/size guards
precede protected operations; safely reconstructable selected metadata retains
direct-artifact-before-content-error behavior.

Local validation precedes fingerprint-version-one reconciliation. Within the
existing BEGIN IMMEDIATE transaction: original-ID reconciliation comes first;
fresh control restrictions and schema gates precede expected-head/stable-kind,
exact reference and direct-artifact checks; complete constrained history/pairing
precedes insertion. All revisions precede links, receipt and one audit event.
Artifact durability precedes publication; registered-size failures roll back metadata.
Rejected batches leave metadata intact; published orphan bytes retain existing
retention behavior. Target/history checks share the committing write lock.

An identical locally valid original returns its original receipt before fresh
schema, availability, CAS, history or pairing checks, even after head advancement
or byte/target/history damage. A generic-original receipt is acknowledgment only,
never retrospective typed certification. Changed valid duplicates fail without
effects; malformed/over-limit retries still fail local validation. Preview reserves
nothing and rejects an already-used ID; commit repeats fresh checks under its lock.
COMMIT completes before the after_commit seam: lost acknowledgment is recovered
with the exact saved Submission and original submission_id after reopen, never by
inventing another ID or claiming rollback.

## Executable private-store example

This self-contained product/stdlib-only block stages inert bytes, supplies all
provenance, commits a substantive mixed batch, reopens, reconciles and demonstrates
atomic mismatched-pair refusal. No credentials, services, external data, running
environment discovery or assessed execution are required.

<!-- tool-assessment-persistence-example:start -->
```python
import copy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.resources import Dimension
from research_pipeline.work_product import WorkProductFile
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

# The complete ToolRelease uses these exact local bytes, without an additional
# implementation-record link. Nothing in this example executes either file.
local_sections["identity"]["implementation"]["source_records"] = K([])


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


creator = CreationProvenance("archival-creator", "2026-11-04T10:00:00Z",
                             {"purpose": "passive persistence", "synthetic": True, "signed": -2, "fraction": 0.25})
controller = CreationProvenance("submission-controller", "2026-11-04T10:01:00Z", {"purpose": "example"})
with TemporaryDirectory(prefix="assessment-persistence-") as temporary:
    parent = Path(temporary)
    parent.chmod(0o700)
    runtime = parent / "runtime"
    with RecordStore.create(runtime) as store:
        for name, data in (("implementation.txt", b"# synthetic affine bytes; never executed\n"),
                           ("adapter.txt", b"# synthetic client description; never executed\n")):
            source = parent / name
            source.write_bytes(data)
            source.chmod(0o600)
            store.put_artifact(source.read_bytes())
        configuration = store.put_artifact(b"precision=binary64; synthetic supplied description\n").to_dict()
        release = ToolRelease(**local_sections)
        doc = assessment_document(release, configuration)
        value = ToolAssessment.from_dict(doc)
        assessed = assessment_envelope(value.assessment_id, 1, value, creator)
        released = release_envelope(release.tool_id, 1, release, creator)
        saved = Submission("assessment-original", controller, [assessed, released],
                           {value.assessment_id: 0, release.tool_id: 0})
        receipt = store.submit_typed(saved)  # assessment precedes its release
        assert receipt.revisions == ((value.assessment_id, 1), (release.tool_id, 1))
    with RecordStore.open(runtime) as store:
        envelope, inspected = store.get_typed_revision("affine_assessment", 1)
        assert inspected.to_dict() == doc and envelope.provenance == creator
        assert envelope.provenance.actor != doc["attribution"]["actor"]["value"]
        events = store.audit_events()
        assert store.submit_typed(saved) == receipt
        assert store.audit_events() == events
        bad = copy.deepcopy(doc)
        bad["assessment_id"] = "mismatched_assessment"
        bad["target"]["release_id"] = "sha256:" + "0" * 64
        rejected = assessment_envelope("mismatched_assessment", 1, ToolAssessment.from_dict(bad), creator)
        try:
            store.submit_typed(Submission("mismatched-request", controller, [rejected], {"mismatched_assessment": 0}))
        except ReferenceResolutionError:
            pass
        else:
            raise AssertionError("mismatched exact release pairing admitted")
        assert store.get_submission("mismatched-request") is None
        assert store.head("mismatched_assessment") is None
        assert store.audit_events() == events
print("Assessment and forward release committed; reopened inspection and original-ID reconciliation agree.")
print("Mismatched pairing refused atomically; no permission, qualification or execution established.")
```
<!-- tool-assessment-persistence-example:end -->

## Outstanding duties

Passive persistence grants no authenticated scoped enablement/withdrawal,
qualification credit, lifecycle selection, isolated execution or authentic execution
receipts/recovery. D04 and all FOLLOWON obligations, M0-E completeness, M0-S/live
resources, scientific sufficiency and human scientific/release acceptance remain
outstanding. This establishes no phase or product completion.
