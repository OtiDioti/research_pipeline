"""Disposable exact authority declarations and real stored short-note dossier fixtures."""

from dataclasses import replace
from research_pipeline import operating_authority as a
from research_pipeline.domain import RecordReference
from research_pipeline.project import encode_envelope as project_envelope
from research_pipeline.corpus import encode_envelope as corpus_envelope
from research_pipeline.source import SourceDeclaration, SourceRestrictions, encode_envelope as source_envelope
from research_pipeline.work_product import WorkProductFile
from tests.resource_fixtures import DIMENSIONS, vector, policy as run_policy
from tests.test_project import setup, dossier, declaration, judgment
from tests.test_corpus import inventory, entry, location, missing
from tests.test_source import source, uninspected
from tests.test_store import CREATOR, request
from tests.test_typed_store import ref, envelope, context
from tests.test_work_product import manifest
from tests.test_work_product_store import product

TIME = "2026-11-02T12:00:00.000000Z"
END = "2026-11-03T12:00:00.000000Z"
KEY = b"disposable-local-test-key-32bytes!"
REVOKER_KEY = b"separate-revoker-test-key-32bytes!"
LIMITS = a.AuthorityLimits(100, 1000, 1000, 20000, a.ENVELOPE_BYTES, a.RESULT_BYTES, 1000, 1000000, 10000000, a.RESULT_BYTES)


def policy(*, capabilities=a.CAPABILITIES, projects=("project",), key=KEY):
    """Configure a disposable local credential; no runtime/research grant is represented."""
    return a.OperatorPolicy("synthetic", [a.OperatorCredential("operator", "key1", key, projects, capabilities)])


def revoker_policy():
    """Configure only a separate reducer, deliberately omitting the approver's verifier."""
    return a.OperatorPolicy("synthetic", [a.OperatorCredential("revoker", "revoker1", REVOKER_KEY, ["project"], ["deny", "revoke"])])


def scope(purpose="setup", *, data=False):
    """Declare complete resource pools and optional exact original read permission."""
    policy_value = run_policy()
    pools = {"ordinary": vector(tool_calls=2), **{p: policy_value[p + "_minimum"] for p in ("verification", "handoff", "closeout")}}
    return a.OperatingScope({"format": "research_pipeline.operating_scope", "version": 1, "purpose": purpose,
        "capability_releases": [], "data_access": [{"source": ref("capture", "allowed_source", "source").to_dict(),
            "original_ids": ["original"], "operations": ["read"]}] if data else [], "disclosures": [],
        "resources": {"dimensions": DIMENSIONS, "ceiling": vector(100), "purpose_limits": pools,
                      "call_bounds": None, "run_policy": policy_value}})


def empty(store, *, entries=()):
    """Commit an incomplete setup and its immutable corpus baseline using existing typed APIs."""
    store.submit_typed(request("empty", [project_envelope("project", 1, setup(), CREATOR),
        corpus_envelope("corpus", 1, inventory(entries), CREATOR)]))


def short_note(store, *, document_path="document.md"):
    """Commit actual bytes, negative material, unprocessed remainder and authored documents.

    The optional logical document path permits canonical escaping tests using the
    same real stored dossier and unchanged readiness prerequisites.
    """
    originals = [store.put_artifact(data) for data in (b"Let f(x)=x. What changes for a restricted domain?\n", b"Accompanying metadata", b"Derived text")]
    full = source(originals)
    permitted = SourceDeclaration("permitted", "Disposable synthetic declaration")
    public = SourceDeclaration("public", "Disposable synthetic public example")
    captured = replace(uninspected(), originals=full.originals, extractions=full.extractions, locations=full.locations,
        restrictions=SourceRestrictions(SourceDeclaration("available", "Stored synthetic bytes"), permitted, public, permitted))
    corpus = inventory([entry(selected=captured.originals[:1]), missing("reference", "reference_only")])
    value = replace(dossier(), declarations=[declaration(locations=[location()]),
        replace(declaration("negative"), category="contradiction", text="A contrary supplied observation remains unresolved"),
        replace(declaration("remainder"), category="unprocessed_remainder", text="No exhaustive corpus inspection claimed")])
    records = [project_envelope("project", 1, value, CREATOR), corpus_envelope("corpus", 1, corpus, CREATOR),
               source_envelope("capture", 1, captured, CREATOR), envelope("context", context())]
    for identity, kind in (("brief", "research_brief"), ("intake", "intake_report")):
        artifact = store.put_artifact(("Authored synthetic " + kind + "; no scientific endorsement").encode())
        document = replace(manifest(artifact), product_kind=kind, context=value.context,
            linked_sources=[ref("capture", "linked_source", "source")],
            build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest")],
            files=[WorkProductFile(document_path, artifact)], entry_file=document_path)
        records.append(product(identity, document))
    store.submit_typed(request("short-note", records))
    return value, captured, records


def decision(binding, operating_scope=None, *, revision=1, previous=None, outcome="approve", operation="approve", **updates):
    """Construct a complete externally signable statement with exact predecessor and trusted explicit times."""
    wire = {"format": "research_pipeline.operating_decision", "version": 1,
        "authority_domain": "synthetic", "principal_id": "operator", "key_id": "key1", "operation_id": operation,
        "decision_id": a.stream_id("synthetic", binding.to_dict()["project"]["record_id"]), "revision": revision,
        "predecessor": None if previous is None else {"reference": RecordReference(previous.record_id, previous.revision, "supersedes", "decision").to_dict(),
                                                       "envelope_digest": a.envelope_digest(previous)},
        "outcome": outcome, "binding": binding.to_dict(),
        "judgments": {"substantive_relevance": judgment("affirmed").to_dict(),
                      "assignment_usability": judgment("affirmed").to_dict(),
                      "evidence_declarations": ["seed-note"] if operating_scope and operating_scope.to_dict()["purpose"] == "main_research" else []},
        "rationale": "Explicit synthetic procedural statement only", "issued_at": TIME, "valid_from": TIME, "valid_until": END,
        "scope": None if operating_scope is None else operating_scope.to_dict(), **updates}
    return a.OperatingDecision(wire)


def prepare(store, operating_scope):
    """Prepare exact project revision one with explicit bounds; preparation supplies no reservation."""
    return store.prepare_operating_binding(ref("project", "project_setup", "project"), scope=operating_scope, limits=LIMITS)


def sign(value, key=KEY):
    """Sign synthetic complete bytes without installing any policy in the store."""
    return a.sign_decision(value, key=key)
