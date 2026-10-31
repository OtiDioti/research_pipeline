"""Shared private synthetic inputs for reader/planner engineering evidence, never scientific evaluation."""

from dataclasses import replace
from pathlib import Path

from research_pipeline.corpus import encode_envelope as corpus_envelope
from research_pipeline.domain import RecordReference
from research_pipeline.project import encode_envelope as project_envelope
from research_pipeline.source import decode_envelope as source_content
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.snapshot import RootSelector, SnapshotLimits, SnapshotSelection
from research_pipeline.work_product import WorkProductFile, encode_envelope as product_envelope
from tests.test_assessment_store import mixed_graph, declarations, assessment_envelope, issue
from tests.test_corpus import inventory, entry, missing, inspection, location
from tests.test_project import setup, attributed, declaration
from tests.test_source import source, uninspected, known
from tests.test_store import CREATOR, CONTROLLER, record, request
from tests.test_typed_store import ref
from tests.test_work_product import manifest


HOSTILE = '  ---\n[[other]] ![image](https://example.invalid) [x](../../escape) <script>& ` ``` (x) : #\n\u202e\x01  '


def limits(**changes):
    """Supply explicit generous finite budgets, with caller overrides for boundary cases."""
    values = dict(max_roots=32, max_records=256, max_references=4096, max_record_bytes=2_000_000,
                  max_metadata_bytes=20_000_000, max_artifacts=64, max_files=2048,
                  max_file_bytes=10_000_000, max_total_bytes=50_000_000)
    values.update(changes)
    return SnapshotLimits(**values)


def selection(*roots):
    """Select current project and explicit additional current identities in supplied order."""
    return SnapshotSelection(RootSelector("project", None), tuple(RootSelector(name, None) for name in roots))


def simple_project(store):
    """Commit a generic project with no required edges for isolated accounting/error tests."""
    store.submit(request("project-created", [record("project", kind="project")]))


def captured_source(store, parent):
    """Create explicit 0700/0600 inputs, capture mixed inert originals and return the prepared Source."""
    input_root = parent / "inputs"
    input_root.mkdir(mode=0o700)
    input_root.chmod(0o700)
    (input_root / ".obsidian").mkdir(mode=0o700)
    (input_root / "notes").mkdir(mode=0o700)
    payloads = (("original", "notes/seed.tex", b"Synthetic TeX $x=x$\n"),
                ("copy", "copy.tex", b"Synthetic TeX $x=x$\n"),
                ("settings", ".obsidian/app.json", b'{"synthetic":"inert"}\n'),
                ("readme", "README.md", b"# Authored README\n[x](missing.md)\n"),
                ("binary", "native.bin", b"\x00\xff\x80native\n"),
                ("text", "extracted.txt", b"Supplied extraction; never executed.\n"))
    meta = uninspected().to_dict()
    for key in ("format", "version", "kind"):
        del meta[key]
    meta["title"] = known(HOSTILE).to_dict()
    selected = []
    for identity, logical, data in payloads:
        path = input_root / logical
        path.write_bytes(data)
        path.chmod(0o600)
        item = source().originals[0].to_dict()
        item.update(artifact_id=identity, path=logical)
        del item["artifact"]
        del item["original_mode"]
        item["provenance"].update(method="supplied_local", outcome="available",
                                  supplied_locator=known(str(path)).to_dict())
        selected.append({"artifact_id": identity, "input_path": logical})
        if identity == "text":
            extraction = source().extractions[0].to_dict()
            extraction.update(original_inputs=["original"], outputs=[item], mappings=[])
            meta["extractions"] = [extraction]
        else:
            meta["originals"].append(item)
    meta["locations"] = [source().locations[0].to_dict()]
    prepared = prepare_source_capture(store, input_root, selected_files=selected, metadata=meta,
        record_id="capture", revision=1, expected_head=0, submission_id="capture-source",
        record_provenance=CREATOR, submission_provenance=CONTROLLER,
        source_root=Path(__file__).resolve().parents[2], backup_roots=[], control_roots=[],
        max_file_bytes=10000, max_total_bytes=100000, max_files=10)
    store.submit_typed(prepared.submission)
    return source_content(prepared.submission.records[0]), {path: data for _, path, data in payloads}


def populated(store, parent):
    """Commit coherent captured dossier, scientific disagreement and branch/native product routes."""
    captured, payloads = captured_source(store, parent)
    seeds = inventory([entry(selected=captured.originals[:1]), missing("reference", "reference_only"),
                       missing("unavailable", "unavailable"), missing("unresolved", "unresolved")])
    value = replace(setup(), title=attributed(HOSTILE), objective=attributed("Synthetic engineering evidence"),
                    context=ref("context", "context", "research_context"),
                    brief=ref("brief", "research_brief", "work_product_manifest"),
                    intake_report=ref("intake", "intake_report", "work_product_manifest"),
                    inspection=inspection("selected_material", [location()]),
                    declarations=[declaration(locations=[location()])])
    artifact = store.put_artifact(b"Synthetic engineering observation, no scientific evaluation.\n")
    store.submit(request("shallow-declarations", [*declarations(), record("branch", kind="branch", content={
        "purpose": "Invented runtime keys must stay opaque", "stop_reason": "not a run result"}),
        record("run", kind="run", content={"success": True, "authorized": True})]))
    graph = mixed_graph(artifact)
    # Select an actual claim objection in addition to the review/peer issue cycle.
    graph.append(assessment_envelope("claim-objection", replace(issue(),
        affected_records=[ref("candidate", "affected_record", "claim")], supporting_evidence=[])))
    store.submit_typed(request("science", graph))
    authored = []
    for identity, product_kind in (("brief", "research_brief"), ("intake", "intake_report")):
        product = replace(manifest(artifact), product_kind=product_kind, context=value.context,
                          title=HOSTILE, authors=[HOSTILE],
                          linked_sources=[ref("capture", "linked_source", "source")],
                          build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest")],
                          files=[WorkProductFile("README.md", artifact)], entry_file="README.md")
        authored.append(product_envelope(identity, 1, product, CREATOR))
    product = replace(manifest(artifact), title=HOSTILE, branch=ref("branch", "branch", "branch"),
        context=value.context, linked_claims=[ref("candidate", "linked_claim", "claim")],
        linked_sources=[ref("capture", "linked_source", "source")],
        files=[WorkProductFile("notes/α.md", artifact), WorkProductFile("shared.txt", artifact),
               WorkProductFile(".obsidian/settings.py", captured.originals[-1].artifact)], entry_file="notes/α.md")
    authored.append(product_envelope("native-product", 1, product, CREATOR))
    report = replace(manifest(artifact), product_kind="end_of_run_report", run=ref("run", "run", "run"))
    authored.append(product_envelope("run-report", 1, report, CREATOR))
    store.submit_typed(request("dossier", [project_envelope("project", 1, value, CREATOR),
        corpus_envelope("corpus", 1, seeds, CREATOR), *authored]))
    roots = selection("candidate", "review-a", "review-b", "claim-objection", "native-product", "run-report")
    return roots, payloads
