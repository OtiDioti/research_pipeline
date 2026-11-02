# Authenticated local operating decisions

This API adds a local shared-credential authority boundary for exact project
readiness. **An eligibility result must be recomputed with current external host
policy and trusted time inside the later admitting write transaction.** It reserves
nothing and guarantees neither dispatch nor continued artifact availability.
Admission, worker isolation, lifecycle/restart gates, tool enforcement and M0-S
remain subsequent work. Synthetic procedural approvals are not scientific evidence.

`ProjectSetup.readiness` remains an attributed proposal. A signed operator decision
authenticates the configured principal's exact procedural statements, not scientific
truth, legal identity, nonrepudiation or independent review. HMAC proves possession
of a configured shared secret. The local controller is trusted; this mechanism does
not isolate hostile code in the same process.

## Trusted bootstrap and secrets

Import from `research_pipeline.operating_authority`:

- `OperatorCredential(principal_id, key_id, key, projects, capabilities)` accepts
  ordinary immutable key bytes (32–64 bytes), explicit unique project IDs (at most
  256), and a unique subset of `approve_setup`, `approve_main_research`, `deny`,
  `revoke`. Empty collections authorize nothing.
- `OperatorPolicy(authority_domain, credentials)` accepts at most 128 exact
  credentials, with unique principal/key pairs and no key ID shared across
  principals. It snapshots all collections. Keys are excluded from repr.
- `sign_decision(decision, *, key)` is a pure helper returning
  `SignedOperatingDecision`. It installs no policy and grants no permission.
- `verify_signature(signed, *, policy)` returns `verified`, `invalid`, or
  `unavailable`, for cryptographic verification only. Authorization independently
  checks domain, principal/key, project and the outcome's capability.

Host code must supply keys/verifiers outside source, canonical records, artifact
bytes, imported/task content and future worker inputs. There is no policy loader,
key discovery, daemon, environment lookup, secret persistence or operator CLI.
Keep a credential with empty capabilities to retain historical verification while
withdrawing permission. Removing verification material yields `unavailable`.
Rotation must use a new `key_id`. Each operation captures a detached policy snapshot.

`policy_fingerprint` hashes canonical public domain/principal/key identifiers,
project scopes and capabilities, **excluding key bytes**. It does not authenticate
key bytes or replace rechecking the actual current verifier. No key is passed to
persistence, projections, generated artifacts or backup code.

Backups contain history but no trust configuration. Without external trust they
remain historically inspectable but cannot authenticate permission. **Restoring an
older backup cannot discover or reconcile later omitted revocations.** A restart
must supply current external denying policy or credential withdrawal and resolve
the restored snapshot before any future dispatch. Restore is not a freshness oracle.

## Constructors and wire contract

All seven values have the constructor `Class(document)`, strict
`Class.from_dict(document)` and `to_dict()`. Input/output trees are detached;
constructors, serialization and public consumers revalidate bypassable frozen
state and reject subclasses/lookalikes. Unknown, omitted (including nullable),
duplicate JSON fields, coercions, surrogates and nonfinite values are rejected.

Every top-level object requires `format` and ordinary-integer `version: 1`.
The following table lists **all other required fields**. References always have
`record_id`, `revision`, `relationship`, `target_kind`, with an explicit existing
supported kind. Digests are 64 lowercase SHA-256 hexadecimal characters.

| Class / format suffix after `research_pipeline.` | Required fields |
| --- | --- |
| `OperatingScope` / `operating_scope` | `purpose`, `capability_releases`, `data_access`, `disclosures`, `resources` |
| `OperatingBinding` / `operating_binding` | `project`, `dossier`, `record_evidence`, `artifact_evidence`, `head_expectations` |
| `OperatingDecision` / `operating_decision` | `authority_domain`, `principal_id`, `key_id`, `operation_id`, `decision_id`, `revision`, `predecessor`, `outcome`, `binding`, `judgments`, `rationale`, `issued_at`, `valid_from`, `valid_until`, `scope` |
| `SignedOperatingDecision` / `operating_authority_content` | `kind: "decision"`, `decision`, `signature` |
| `DecisionCommitResult` / `operating_commit_result` | `operation_id`, `decision`, `envelope_digest`, `receipt` |
| `AuthorityHistory` / `authority_history` | `authority_domain`, `project_id`, `decisions`, `watermark` |
| `EligibilityResult` / `operating_eligibility` | `authority_domain`, `project_id`, `purpose`, `evaluated_at`, `status`, `eligible`, `decision`, `signature_status`, `policy_status`, `binding`, `observed_heads`, `verified_artifacts`, `history_signatures`, `watermark`, `policy_fingerprint`, `recheck_required` |

The paired codecs are `dumps_scope/loads_scope`, `dumps_binding/loads_binding`,
`dumps_decision/loads_decision`, `dumps_signed_decision/loads_signed_decision`,
`dumps_commit_result/loads_commit_result`, `dumps_history/loads_history`, and
`dumps_eligibility/loads_eligibility`. Dumps return compact sorted-key
`ensure_ascii=True` JSON text; loads accept bounded UTF-8 text/bytes.

### Nested scope fields

| Field | Exact shape and meaning |
| --- | --- |
| `purpose` | `setup` or `main_research` |
| `capability_releases[]` | `{capability_id, release}`; release role `allowed_release`, kind `tool_release` |
| `data_access[]` | `{source, original_ids, operations}`; source role `allowed_source`, kind `source`; unique nonempty original IDs and operations from `read`, `reuse`, `external_processing`; read is required |
| `disclosures[]` | `{source, original_ids, recipient_id, policy_reference}`; source role `disclosed_source`, kind `source`; policy role `disclosure_policy`, any explicit supported kind; each original needs matching external-processing permission |
| `resources` | `{dimensions, ceiling, purpose_limits, call_bounds, run_policy}` |
| `purpose_limits` | Exactly `ordinary`, `verification`, `handoff`, `closeout`, each a complete vector |

Dimensions, vectors, call bounds and run policy use the existing
[resource contract](resource-accounting.md), including 7–16 dimensions and exact
integer arithmetic. Pools must fit the ceiling; protected pools cover their run
policy minima. Handoff call arithmetic is checked. Ordinary `call_bounds` is null
only if all ordinary model-call/input/output capacity is zero; otherwise it must
provision ordinary calls and fit the context/output constraints. Monetary services
support only `monitored_target`, never a claimed enforceable provider hard ceiling.
These declarations do not allocate, reserve, reset usage or release uncertain
liabilities, qualify tools or establish external availability.

Empty permission arrays grant nothing. There are no wildcards, inherited scope,
prose-derived permissions or unspecified defaults. Permitted originals must belong
to captured entries of the bound current corpus; extraction outputs and cross-project
Sources do not qualify. Read requires Source `access=available`; reuse additionally
requires `reuse=permitted`. External processing additionally requires
`external_processing=permitted`, `confidentiality=public` and exact recipient/policy
disclosure evidence. Restricted/confidential/unknown inputs are outside this first
supported disclosure boundary. Policy evidence alone does not grant authorization.

### Nested binding and decision fields

`project` is a `project_setup` reference of kind `project`. `dossier` has exactly
`initial_corpus`, `current_corpus`, `context`, `brief`, `intake_report`. Corpus roles
retain their names; optional roles are `context`, `research_brief`, `intake_report`.
Absent optional pins use exactly
`{"value":null,"unknown_reason":"Absent from the bound ProjectSetup."}`.
Present metadata pins do not claim artifact availability.

`record_evidence[]` is `{reference, envelope_digest}`, role `authority_evidence`
with the actual target kind. The digest covers the complete canonical
`RecordEnvelope.to_dict()`, including provenance and ordered projections.
`artifact_evidence[]` is `{record, selector_kind, selector, artifact}`, with owner
role `authority_artifact_record`. A `source_original` selector is an original
artifact ID; a `work_product_file` selector is a manifest logical path. Artifact
values are exact `{digest,size}`. Distinct owner/selector occurrences survive byte
deduplication; duplicate identical occurrences and conflicting sizes are rejected.
`head_expectations[]` is `{record_id,revision,kind}`, unique by identity. Evidence
and heads sort by identity/revision; artifacts also sort by selector kind/selector.

The binding includes the complete bounded constrained dossier metadata and typed
histories to revision 1, exact capability/disclosure-policy targets, every inspected
or explicitly permitted original and every selected brief/report file. Generic
shallow references get bounded existence/kind checks, not automatic recursive
certification. Each incoming constrained role is checked independently of caching.

Watched heads are the current project, current corpus, present context/brief/intake
report, Sources named in current inspection/declarations or data permissions, and
exact capability-release/disclosure-policy targets. Each watched identity must
have one consistent selected revision and be current at approval. Initial-corpus
revision 1 and history-only occurrences are immutable evidence, not current-head
requirements. Other constrained metadata stays pinned by complete envelope digest.
A watched-head change makes approval stale; unrelated audit events do not.

`outcome` is `approve`, `deny`, or `revoke`. Approve requires a complete new scope;
reductions require null scope. `predecessor` is null at revision 1; otherwise it is
`{reference,envelope_digest}`, role `supersedes`, kind `decision`, exactly the
immediately preceding same-stream revision. Revoke requires a predecessor. A
reduction with a predecessor copies its binding exactly, without rereading old
artifacts, demanding current dossier heads or requiring the old signer. It still
loads the exact historical ProjectSetup through the bounded metadata reader,
checks its complete envelope digest against the copied binding, and requires each
judgment evidence ID to belong to that setup. A newer setup cannot add or remove
IDs for this historical check. Empty evidence selections remain valid for reductions;
this local check does not resolve dossier targets or repeat fresh readiness.

`judgments` has exactly `substantive_relevance`, `assignment_usability` (existing
`ProceduralJudgment` shapes `{status,explanation,attribution}`), and unique
`evidence_declarations` IDs from the exact ProjectSetup. Main approval requires
both judgments affirmed with known attribution and selected location-bearing
evidence. Setup can retain unassessed/unaffirmed judgments.

Main approval independently checks known title/objective/intent, attributed
selected-material inspection, a coherent nonempty inspected subset, no outstanding
intake-stage requirement, usable context, exact authored nonempty brief and intake
report, corpus/context/Source membership and a selected declaration anchored to a
nonempty original. All inspected originals need explicit read permission. Required
originals and all brief/report files are streamed through ArtifactStore integrity
verification; commits synchronize them. No parser or length/title heuristic infers
scientific relevance. Negative material, contradictions, unknowns and uninspected
remainder remain visible. Setup requires coherent metadata but verifies only
original-data permissions it actually grants; absent optional document bytes do
not prevent bounded setup. Initial denial is metadata-only.

All authority times are exact `YYYY-MM-DDTHH:MM:SS.ffffffZ` calendar strings.
`issued_at <= valid_from < valid_until`; the validity interval is at most 366 days.
New commits require explicit trusted `evaluated_at` in `[valid_from, valid_until)`
and not earlier than issuance. No signing, history, rendering or eligibility API
consults an implicit clock. Store audit timestamps retain existing recording behavior.
A denied/revoked latest state never reveals an older approval after its interval ends.

### Signature, stream and envelope

`signature` has exactly `algorithm: "hmac-sha256"` and a lowercase 64-hex `value`.
The signing preimage is
`b"research_pipeline.operating_decision.v1\x00" + canonical_decision.encode("ascii")`.
Use `hmac.new(key, preimage, hashlib.sha256)` and `hmac.compare_digest`.

`stream_id(authority_domain, project_id)` returns `"operating_"` plus SHA-256 of
`b"research_pipeline.operating_stream.v1\x00"` followed by ASCII canonical JSON for
`[authority_domain, project_id]`. The decision ID must equal this sole stream.
There is no caller-selected alternative stream or historical eligibility selector.

`encode_envelope(signed)` derives ID/revision, kind `decision`, null canonical
states and `CreationProvenance(principal_id, issued_at, {})`. Ordered record
projections are predecessor, project, dossier roles in the order listed above,
record evidence, artifact owners, capability releases, data Sources, then each
disclosure Source/policy. Repeated roles are preserved. Direct artifact projection
is empty so a reduction remains appendable after artifact loss. `decode_envelope`
recomputes every field and projection. It is local decoding, not authentication.

Generic `submit` remains compatible. New `submit_typed` operating decisions must
use `commit_operating_decision`; identical original retries reconcile first. Generic
stored signed decisions affect eligibility only after independent complete envelope,
submission, history, signature, scope and dossier checks. A malformed/generic record
at the canonical stream fails closed, with no older-approval fallback.

## Store operations and results

All methods are on `RecordStore`; they use schema 2 or 3, with no new tables.

| Method | Result and boundary |
| --- | --- |
| `prepare_operating_binding(project, *, scope, limits)` | `OperatingBinding`; exact project_setup reference, scope or null for initial denial; one read transaction, metadata only, no reservation |
| `commit_operating_decision(signed, *, policy, evaluated_at, limits)` | `DecisionCommitResult`; one existing `BEGIN IMMEDIATE` transaction |
| `get_operating_operation(operation_id, *, limits)` | Original `DecisionCommitResult` or null; no policy, time or artifacts |
| `inspect_operating_history(authority_domain, project_id, *, policy, limits)` | Complete ascending `AuthorityHistory`; nullable policy, no time/artifact reads |
| `inspect_operating_eligibility(authority_domain, project_id, *, purpose, policy, evaluated_at, limits)` | Current `EligibilityResult`; latest stream, all chain metadata and current dossier in one read snapshot |

The derived submission uses operation ID as submission ID, exactly one derived
envelope, identical derived provenance and `{decision_id: revision-1}` expected
heads. Fingerprint version 1 hashes the existing canonical complete submission.
Original-ID lookup checks canonical request/fingerprint, exact one-record membership,
links and audit receipt consistency before current trust, clock, heads or artifacts.
An identical retry returns the original result; a changed request conflicts. Recover
by original ID after post-COMMIT/process/actual-close acknowledgment loss; never
assume rollback or issue another operation automatically.

Commit results contain a decision reference with role `operating_decision`, envelope
digest and existing `SubmissionReceipt`, never an eligible flag. History decisions
contain `{envelope,receipt,signature_status,policy_status}`. Signature statuses are
`verified`, `invalid`, `unavailable`; policy statuses are `permitted`, `denied`,
`unavailable` under the supplied **current** configuration, not reconstructed past
permission. Missing historical keys are reported explicitly. A separately authorized
fresh approval can establish its own complete scope after all fresh checks despite
an unavailable old verifier; a known-invalid predecessor signature fails closed.

Eligibility statuses are `no_decision`, `missing_trust`, `policy_denied`,
`unauthenticated`, `denied`, `revoked`, `not_yet_valid`, `expired`, `scope_mismatch`,
`stale`, `incomplete`, `artifact_unavailable`, `eligible_setup`, `eligible_main_research`.
Only the last two set `eligible=true`, matching the requested purpose. Missing or
corrupt selected bytes give `artifact_unavailable`; corrupt metadata/history and
exhausted limits raise errors. No successful partial/truncated history is returned.

`decision` and `binding` identify the actual latest state or are null.
`observed_heads` uses the watched-head shape. `verified_artifacts` contains only
unique `{digest,size}` values actually verified during this evaluation.
`history_signatures[]` contains `{reference,envelope_digest,signature_status}`.
Unchecked evidence uses null/empty fields. The existing watermark has exactly
`event_id`, `submission_id`, `committed_at`, `fingerprint` (all null for an empty
store). It identifies a snapshot, not global freshness. `recheck_required` is always
true. Detached readable projections label decisions historical/unverified; a view
cannot turn a signed approval into current permission.

## Simultaneous bounds and errors

Published constants include `IDENTIFIER_CHARS=128`, `TEXT_CHARS=4096`,
`PERMISSION_ENTRIES=128`, `ORIGINAL_IDS=1024`, `EVIDENCE_DECLARATIONS=1024`,
`EVIDENCE_ENTRIES=4096`, `JSON_DEPTH=32`, `JSON_NODES=131072`,
`DECISION_BYTES=1048576`, `SIGNED_BYTES=1049600`, `ENVELOPE_BYTES=4194304`,
`RESULT_BYTES=67108864`. Equality is allowed; all bounds apply simultaneously.
Identifiers use existing 1–128 ASCII syntax. Explanations are 1–4096 Unicode scalar
characters. Resource vectors have 1–16 entries, dimension sets 7–16, monetary-service
entries at most 9. Reference/artifact/head evidence has at most 4096 entries each.
Complete decision documents are at most 1 MiB; signed content adds 1024 bytes;
projected envelopes are at most 4 MiB; detached result/component documents at most
64 MiB. A separately prepared scope/binding must still fit inside the complete
1 MiB decision when it is used for signing.
Input UTF-8 bytes are checked before parsing and normalized ASCII bytes afterward.
Cycles, non-string keys, duplicate keys, nonfinite numbers, bool-as-integer and
integer coercions are rejected before domain reconstruction. JSON depth counts
nested containers; node counts include each container and scalar value.

`AuthorityLimits(max_decisions, max_history_revisions, max_records, max_references,
max_record_bytes, max_metadata_bytes, max_artifacts, max_file_bytes, max_total_bytes,
max_result_bytes)` has no defaults. Validate all fields before database work.
Hard ceilings are 1024 decisions, 4096 metadata records/history revisions, 32768
reference occurrences, 4 MiB per record, 64 MiB aggregate metadata/output and 4096
verified artifact digests. Artifact byte limits are explicit ordinary integers in
`0..2**63-1` (per-file must be positive). Byte/record/decision limits are positive;
zero is allowed for history/reference/artifact counts and aggregate artifact bytes.
History revisions count independently of records; repeated references count;
actual artifact reads deduplicate by digest only after checking each occurrence.
Actual SQLite storage types, UTF-8 BLOB lengths, counts and ordinals are preflighted
before value fetches. Original-operation recovery first checks actual single-member
membership and ordinal zero, then the actual revision and both link-table counts,
ordered link metadata and independent audit metadata. It reserves fetches and
retained request/envelope representations before decoding the saved request, and
reserves receipt/result retention before constructing those values after consistency
checks. A cached envelope never substitutes for membership or audit checks;
a successful preflight is reused only within its transaction to avoid charging the
same planned fetch/reference occurrence twice. Recovery remains metadata-only and
does not run the historical reduction declaration check.

Accounting uses canonical JSON bytes, not Python heap estimates. Accepted canonical
content/provenance fragments use their measured input lengths. Before validation,
a JSON text scalar reserves at most six ASCII bytes per UTF-8 input byte plus quotes
(or four bytes for null); fixed field names, punctuation, numbers and collection
framing are counted separately. The request reservation covers its raw fetch and
four additional representations: decoded JSON, Submission, signed envelope and
derived Submission. Temporary decoded/derived values are discarded after comparison.
Unused upper-bound reservations are reconciled to actual canonical sizes after
validation. Binding preparation, history, eligibility and fresh append all reserve
their complete detached retention before construction, independently of retained
envelopes, typed content and history entries. History entries include their full
wrappers and signature/policy annotations; derived history-signature entries also
consume independent allowances. Empty history and eligibility results still consume
metadata allowance, including null fields, empty arrays and the audit watermark.

Standalone receipt and complete result retention (including the result's receipt
copy) are reserved separately. Fresh append reserves both before the shared insert
helper constructs its receipt. The generated positive SQLite event ID is bounded
by 19 decimal digits and the normalized audit timestamp by 27 characters plus JSON
quotes; unused overhead is reconciled after successful construction. Recovery keeps
its independent stored-metadata preflight and conservative stored-text bounds.
`max_result_bytes` independently bounds the complete returned result; it does not
charge metadata a second time. An append exceeding that output cap rolls back.
Repeated fetches and separately retained metadata consume their own allowances.
These internal memory-accounting allowances do not reserve execution or resources
and confer no permission or admission guarantee.

| Error | Meaning |
| --- | --- |
| `AuthorityValidationError(DomainValidationError)` | Malformed new contract or caller limits |
| `AuthorityAuthenticationError` | New-call signature/current host authorization or validity failed |
| `AuthorityReadinessError` | Fresh approval prerequisites/binding/head/artifacts failed, or judgment evidence IDs are absent from the bound setup |
| `AuthorityIntegrityError` | Stored authority/dossier metadata or history incoherent |
| `AuthorityLimitError` | Independent caller bounds exhausted; never successful truncation |
| Existing `SubmissionConflictError`, `RevisionConflictError` | Original-ID conflict or exact stream CAS conflict |
| Existing database/layout/closed-handle errors | Existing transaction/storage failure behavior |

Diagnostics never echo credentials or raw request/stored payloads. Existing
`before_metadata`, `after_first_revision`, `after_commit` fault semantics remain.
No approval or reduction modifies resource tables, releases reservations, cancels
processes or asserts termination.

For this workflow, the controller-owned checks run in order:
`python3 -B implementation/scripts/validate.py`, then
`git diff --check 85f034e8352c8879e8c19d7e84b9d62bbdc81848 HEAD --`.
Fresh controller validation and independent milestone and final review determine
acceptance; retained historical results and Writer installation checks do not.

## Runnable synthetic example

Run from the candidate root with source-relative imports:

```sh
PYTHONPATH=implementation/src python3 -B -c 'from pathlib import Path; text=Path("docs/operating-authority.md").read_text(); exec(text.split("## Runnable synthetic example\n",1)[1].split("```python\n",1)[1].split("```",1)[0])'
```

This self-contained block uses disposable explicit credentials and outside-source
private temporary directories. It captures a substantive short note, preserves an
empty corpus baseline, authorizes bounded incomplete setup then main readiness,
reduces authority with a separately authorized revoker, and recovers original IDs.
It executes no research or provider call and imports no test helpers.

```python
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.store import RecordStore
from research_pipeline import operating_authority as authority
from research_pipeline.resources import UNITS
from research_pipeline.source import (
    DeclaredText, Source, SourceDeclaration, SourceRestrictions, SourceProvenance,
    SourceReading, SourceLocation, decode_envelope as decode_source,
)
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.corpus import (
    CorpusManifest, CorpusEntry, CorpusOriginal, CorpusEntryChange, CorpusInspection,
    CorpusLocation, encode_envelope as corpus_envelope,
)
from research_pipeline.scientific import ResearchContext, encode_envelope as context_envelope
from research_pipeline.work_product import WorkProductManifest, WorkProductFile, encode_envelope as document_envelope
from research_pipeline.project import (
    AttributedText, IntakeDeclaration, IntakeRequirement, ProceduralJudgment,
    ReadinessProposal, ProjectSetup, encode_envelope, setup_presentation,
)
import research_pipeline


def known(text):
    """Preserve a supplied known declaration literally."""
    return DeclaredText(text, None)


def pin(identity, revision, role, kind):
    """Name an exact revision without resolving any current head."""
    return RecordReference(identity, revision, role, kind)


def operating_scope(purpose, allow_note=False):
    """Declare complete explicit resource pools and only the selected synthetic original read."""
    dimensions = [{"dimension_id": kind, "kind": kind, "unit": unit, "currency": None, "scale": 1}
                  for kind, unit in UNITS.items()]

    def vector(**quantities):
        """Build a complete seven-unit vector with explicit zeros for ungranted capacity."""
        return [{"dimension_id": kind, "quantity": quantities.get(kind, 0)} for kind in UNITS]

    pools = {"ordinary": vector(tool_calls=2), "verification": vector(tool_calls=1),
             "handoff": vector(model_calls=1, model_input_tokens=3, model_output_tokens=5, local_time=1, local_storage=1),
             "closeout": vector(local_time=1, local_storage=1)}
    run_policy = {"policy_id": "synthetic-run-policy", "statement": "Synthetic capacity, no reservation",
        **{purpose + "_minimum": pools[purpose] for purpose in ("verification", "handoff", "closeout")},
        "handoff_call_bounds": {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5},
        "context_capacity_tokens": 8, "per_call_output_tokens": 5, "monetary_services": []}
    return authority.OperatingScope({"format": "research_pipeline.operating_scope", "version": 1,
        "purpose": purpose, "capability_releases": [], "disclosures": [],
        "data_access": [{"source": pin("capture", 1, "allowed_source", "source").to_dict(),
                         "original_ids": ["note"], "operations": ["read"]}] if allow_note else [],
        "resources": {"dimensions": dimensions, "ceiling": vector(**{kind: 100 for kind in UNITS}),
                      "purpose_limits": pools, "call_bounds": None, "run_policy": run_policy}})


def authorize(binding, scope, operation, *, previous=None, outcome="approve", revoker=False):
    """Sign a complete explicit statement outside storage; the append API checks current host policy."""
    prior = None if previous is None else authority.encode_envelope(previous)
    return authority.sign_decision(authority.OperatingDecision({
        "format": "research_pipeline.operating_decision", "version": 1, "authority_domain": "demo",
        "principal_id": "reducer" if revoker else "operator", "key_id": "reducer-key" if revoker else "operator-key",
        "operation_id": operation, "decision_id": authority.stream_id("demo", "project"),
        "revision": 1 if prior is None else prior.revision + 1,
        "predecessor": None if prior is None else {"reference": pin(prior.record_id, prior.revision, "supersedes", "decision").to_dict(),
                                                  "envelope_digest": authority.envelope_digest(prior)},
        "outcome": outcome, "binding": binding.to_dict(),
        "judgments": {"substantive_relevance": (relevant if scope and scope.to_dict()["purpose"] == "main_research" else unassessed).to_dict(),
                      "assignment_usability": (usable if scope and scope.to_dict()["purpose"] == "main_research" else unassessed).to_dict(),
                      "evidence_declarations": ["question"] if scope and scope.to_dict()["purpose"] == "main_research" else []},
        "rationale": "Synthetic procedural decision only; no scientific operating grant", "issued_at": now,
        "valid_from": now, "valid_until": "2026-11-03T12:00:00.000000Z",
        "scope": None if scope is None else scope.to_dict()}), key=reducer_key if revoker else operator_key)


now = "2026-11-02T12:00:00.000000Z"
operator_key = b"disposable-example-operator-key!!"
reducer_key = b"disposable-example-reducer-key!!!"
operator = authority.OperatorCredential("operator", "operator-key", operator_key, ["project"], ["approve_setup", "approve_main_research"])
reducer = authority.OperatorCredential("reducer", "reducer-key", reducer_key, ["project"], ["deny", "revoke"])
trust = authority.OperatorPolicy("demo", [operator, reducer])
withdrawn = authority.OperatorPolicy("demo", [reducer])
limits = authority.AuthorityLimits(20, 200, 200, 10000, 4194304, 67108864, 100, 1000000, 10000000, 67108864)


actor = known("Synthetic researcher; unauthenticated")
unknown = DeclaredText(None, "Not supplied in this synthetic example")
creator = CreationProvenance("synthetic-author", "2026-10-31T12:00:00Z", {})
controller = CreationProvenance("synthetic-controller", "2026-10-31T12:01:00Z", {})
source_root = Path(research_pipeline.__file__).resolve().parents[3]
empty_inspection = CorpusInspection("uninspected", [], known("No supplied materials yet"), actor, [])
unassessed = ProceduralJudgment("not_assessed", "Materials have not arrived", actor)
baseline = CorpusManifest("Synthetic seed inventory", "Retain exact supplied material", "Explicit selection", actor,
                          [], [], [], [], [], [], None, "Empty original baseline", actor, [])
shell = ProjectSetup(AttributedText(known("Synthetic question"), actor),
                     AttributedText(known("Explore domain restrictions"), actor),
                     AttributedText(known("Clarify what can be asked of a short note"), actor),
                     pin("seeds", 1, "initial_corpus", "corpus_manifest"),
                     pin("seeds", 1, "current_corpus", "corpus_manifest"), None, None, None,
                     empty_inspection, [], [],
                     ReadinessProposal("insufficient_materials", ["No supplied seeds yet"], actor, [], unassessed, unassessed),
                     [], None, "Create setup shell", actor)
with TemporaryDirectory(prefix="operating-authority-example-", dir="/tmp") as temporary:
    parent = Path(temporary)
    input_root = parent / "input"
    input_root.mkdir(mode=0o700)
    (input_root / "notes").mkdir(mode=0o700)
    note = input_root / "notes" / "seed.txt"
    note.write_text("Let f(x)=x on the real numbers. What changes on a restricted domain?\n", encoding="utf-8")
    note.chmod(0o600)
    root = parent / "runtime"
    saved = parent / "initial.json"
    with RecordStore.create(root) as store:
        initial = Submission("empty-setup", controller,
                             [encode_envelope("project", 1, shell, creator), corpus_envelope("seeds", 1, baseline, creator)],
                             {"project": 0, "seeds": 0})
        saved.write_text(json.dumps(initial.to_dict()), encoding="utf-8")
        original_receipt = store.submit_typed(initial)
        assert setup_presentation(shell) == "awaiting_materials"
        setup_scope = operating_scope("setup")
        setup_binding = store.prepare_operating_binding(pin("project", 1, "project_setup", "project"), scope=setup_scope, limits=limits)
        setup_decision = authorize(setup_binding, setup_scope, "authorize-setup")
        setup_receipt = store.commit_operating_decision(setup_decision, policy=trust, evaluated_at=now, limits=limits)
        assert store.inspect_operating_eligibility("demo", "project", purpose="setup", policy=trust, evaluated_at=now, limits=limits).to_dict()["eligible"]
        assert not store.inspect_operating_eligibility("demo", "project", purpose="main_research", policy=trust, evaluated_at=now, limits=limits).to_dict()["eligible"]
        provenance = SourceProvenance("supplied_local", actor, unknown, known(str(note)), unknown, unknown, "available", [])
        restriction = SourceDeclaration("unknown", "No processing grant supplied")
        source = Source("synthetic-note", unknown, unknown, known("Supplied short note"), [actor], provenance,
                        SourceRestrictions(SourceDeclaration("available", "Disposable captured original is locally readable"), restriction, restriction, restriction), [], [], [],
                        SourceReading("uninspected", [], None, "unreported", [], actor, []), [], [], None, [])
        metadata = source.to_dict()
        for field in ("format", "version", "kind"):
            del metadata[field]
        metadata["originals"] = [{"artifact_id": "note", "path": "notes/seed.txt",
                                  "media_type": known("text/plain").to_dict(), "provenance": provenance.to_dict()}]
        metadata["locations"] = [SourceLocation("question", "note", "section", "Supplied short question", None, None).to_dict()]
        capture = prepare_source_capture(store, input_root,
            selected_files=[{"artifact_id": "note", "input_path": "notes/seed.txt"}], metadata=metadata,
            record_id="capture", revision=1, expected_head=0, submission_id="capture-note",
            record_provenance=creator, submission_provenance=controller, source_root=source_root,
            backup_roots=[], control_roots=[], max_file_bytes=4096, max_total_bytes=4096, max_files=1)
        store.submit_typed(capture.submission)
        captured = decode_source(capture.submission.records[0])
        original = captured.originals[0]
        seed = CorpusEntry("seed", "captured", "research_note", known("Supplied short note"), known("Synthetic collection"),
                           known("notes/seed.txt"), pin("capture", 1, "inventory_source", "source"),
                           [CorpusOriginal(original.artifact_id, original.path, original.provenance.supplied_locator, original.artifact)],
                           None, None, empty_inspection)
        current = replace(baseline, entries=[seed], supersedes=pin("seeds", 1, "supersedes", "corpus_manifest"),
                          revision_reason="Add supplied original after empty baseline", revision_attribution=actor,
                          changes=[CorpusEntryChange("added", "seed", None, "Capture supplied note", actor)])
        store.submit_typed(Submission("add-seed", controller, [corpus_envelope("seeds", 2, current, creator)], {"seeds": 1}))
        context = ResearchContext("How does restricting the domain affect the stated identity?", ["f(x)=x"],
                                  ["f is the supplied identity map"], [], [], ["x is real"], [], [], [], [], [])
        scope = pin("context", 1, "context", "research_context")
        documents = []
        for identity, label, path in (("brief", "research_brief", "brief/research.md"),
                                      ("intake", "intake_report", "reports/intake/intake/report.md")):
            artifact = store.put_artifact(("Synthetic authored " + label + ": study domain restrictions; no scientific validation.\n").encode())
            document = WorkProductManifest(label, "Synthetic " + label, "Record attributed intake", ["Synthetic researcher"],
                None, None, scope, None, [], [pin("capture", 1, "linked_source", "source")], None,
                [pin("seeds", 1, "build_dependency", "corpus_manifest"), pin("seeds", 2, "build_dependency", "corpus_manifest")],
                [WorkProductFile(path, artifact)], path, ["No scientific validation or operating authorization"])
            documents.append(document_envelope(identity, 1, document, creator))
        store.submit_typed(Submission("author-documents", controller,
            [*documents, context_envelope("context", 1, context, creator)], {"brief": 0, "intake": 0, "context": 0}))
        location = CorpusLocation("seed", pin("capture", 1, "source_location", "source"), "question")
        inspected = CorpusInspection("selected_material", [location], known("No literature or alternative domains reviewed"), actor, [])
        observation = IntakeDeclaration("question", "proposed_question", "Investigate the supplied question about domain restrictions",
            "supplied_observation", known("Supplied notes/seed.txt question"), actor, [location], [], ["Not a proved result"])
        relevant = ProceduralJudgment("affirmed", "Researcher declares this supplied identity question relevant and substantive", actor)
        usable = ProceduralJudgment("affirmed", "Researcher declares the restricted-domain assignment usable", actor)
        proposed = replace(shell, current_corpus=pin("seeds", 2, "current_corpus", "corpus_manifest"), context=scope,
            brief=pin("brief", 1, "research_brief", "work_product_manifest"),
            intake_report=pin("intake", 1, "intake_report", "work_product_manifest"), inspection=inspected,
            declarations=[observation], remaining=[IntakeRequirement("operating-policy", "policy_proposal", "research_admission",
                AttributedText(known("Authorized operating policy and budget remain required before admission"), actor))],
            readiness=ReadinessProposal("proposed_ready", ["Attributed judgments and exact seed/documents recorded"], actor,
                                        ["question"], relevant, usable),
            supersedes=pin("project", 1, "supersedes", "project"), revision_reason="Record supplied intake dossier", revision_attribution=actor)
        appended = encode_envelope("project", 2, proposed, creator)
        store.submit_typed(Submission("propose-intake", controller, [appended], {"project": 1}))
        assert proposed.initial_corpus.revision == 1 and proposed.current_corpus.revision == 2
        assert appended.operational_status is None and appended.scientific_disposition is None
        assert setup_presentation(proposed) == "awaiting_authorization"
        main_scope = operating_scope("main_research", allow_note=True)
        main_binding = store.prepare_operating_binding(pin("project", 2, "project_setup", "project"), scope=main_scope, limits=limits)
        approval = authorize(main_binding, main_scope, "authorize-main", previous=setup_decision)
        original_approval = store.commit_operating_decision(approval, policy=trust, evaluated_at=now, limits=limits)
        eligible = store.inspect_operating_eligibility("demo", "project", purpose="main_research", policy=trust, evaluated_at=now, limits=limits).to_dict()
        assert eligible["status"] == "eligible_main_research" and eligible["recheck_required"]
        assert not store.inspect_operating_eligibility("demo", "project", purpose="main_research", policy=None, evaluated_at=now, limits=limits).to_dict()["eligible"]
        denial = authorize(main_binding, None, "deny-main", previous=approval, outcome="deny", revoker=True)
        store.commit_operating_decision(denial, policy=withdrawn, evaluated_at=now, limits=limits)
        assert store.inspect_operating_eligibility("demo", "project", purpose="main_research", policy=withdrawn, evaluated_at=now, limits=limits).to_dict()["status"] == "denied"
        (root / "objects" / original.artifact.digest).unlink()
        revocation = authorize(main_binding, None, "revoke-main", previous=denial, outcome="revoke", revoker=True)
        store.commit_operating_decision(revocation, policy=withdrawn, evaluated_at=now, limits=limits)
        assert store.inspect_operating_eligibility("demo", "project", purpose="main_research", policy=withdrawn, evaluated_at=now, limits=limits).to_dict()["status"] == "revoked"
        assert store.commit_operating_decision(approval, policy=None, evaluated_at=None, limits=limits) == original_approval
        assert store.get_operating_operation("authorize-setup", limits=limits) == setup_receipt
    with RecordStore.open(root) as reopened:
        assert reopened.get_typed_revision("project", 1)[1] == shell
        assert reopened.get_typed_revision("project", 2)[1] == proposed
        saved_request = Submission.from_dict(json.loads(saved.read_bytes()))
        assert reopened.submit_typed(saved_request) == original_receipt
        assert reopened.get_operating_operation("authorize-main", limits=limits) == original_approval
        history = reopened.inspect_operating_history("demo", "project", policy=withdrawn, limits=limits).to_dict()
        assert len(history["decisions"]) == 4
        assert history["decisions"][1]["signature_status"] == "unavailable"
        assert history["decisions"][-1]["signature_status"] == "verified"
```
