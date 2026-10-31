"""Real captured project dossiers, exact historical admission, retries and durable recovery."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactStore
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.corpus import encode_envelope as corpus_envelope
from research_pipeline.domain import DomainValidationError, RecordEnvelope, Submission
from research_pipeline.project import IntakeLink, encode_envelope, setup_presentation
from research_pipeline.scientific import decode_envelope as scientific_content
from research_pipeline.source import decode_envelope as source_content, encode_envelope as source_envelope
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.store import RecordStore, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError
from research_pipeline.work_product import WorkProductFile, decode_envelope as product_content
from tests.test_assessment_store import assessment_envelope, declarations, issue, metadata, mixed_graph
from tests.test_corpus import inventory, entry, missing, inspection, location, change
from tests.test_project import setup, dossier, declaration, readiness, attributed
from tests.test_source import source, uninspected, known
from tests.test_store import CREATOR, CONTROLLER, request
from tests.test_typed_store import envelope, ref, context
from tests.test_work_product import manifest
from tests.test_work_product_store import product


def project_record(value, revision=1, identity="project"):
    """Encode the supplied full snapshot without consulting or rebasing a current head."""
    return encode_envelope(identity, revision, value, CREATOR)


def successor(value, revision, **changes):
    """Append an explicitly attributed project correction, retaining every pin unless caller changes it."""
    return replace(value, supersedes=ref("project", "supersedes", "project", revision - 1),
                   revision_reason="Explicit synthetic correction", revision_attribution=known("Editor"), **changes)


def corpus_successor(value, revision, **changes):
    """Append a corpus snapshot with explicit caller-provided entry diffs and a mandatory predecessor."""
    return replace(value, supersedes=ref("corpus", "supersedes", "corpus_manifest", revision - 1),
                   revision_reason="Explicit inventory revision", changes=[], **changes)


class ProjectStoreTests(unittest.TestCase):
    """Exercise real storage and all-table rollback without inheriting existing test execution."""

    def setUp(self):
        """Allocate a private outside-source runtime and close it before automatic directory cleanup."""
        temporary = TemporaryDirectory(prefix="project-tests-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        self.source_root = Path(__file__).resolve().parents[2]

    def child(self, program, *arguments, expected=0):
        """Run a bounded fresh interpreter using candidate-relative package/test imports only."""
        implementation = self.source_root / "implementation"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, capture_output=True, text=True, timeout=60,
                                env={**os.environ, "PYTHONPATH": os.pathsep.join((str(implementation / "src"), str(implementation))),
                                     "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def rejects(self, batch, error=ReferenceResolutionError):
        """Every rejected transactional request must leave all application tables byte-for-byte unchanged."""
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            self.store.submit_typed(batch)
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def capture(self, identity="capture"):
        """Capture inert synthetic inputs with explicit private directories and owner-only file permissions."""
        input_root = self.parent / (identity + "-input")
        input_root.mkdir(mode=0o700)
        (input_root / "notes").mkdir(mode=0o700)
        payloads = (("original", "notes/seed.txt", b"Let f(x)=x for real x. What changes on a restricted domain?\n"),
                    ("license", "LICENSE", b"Synthetic accompanying metadata\n"),
                    ("text", "derived.txt", b"Supplied extraction, never executed\n"))
        meta = uninspected().to_dict()
        for name in ("format", "version", "kind"):
            del meta[name]
        selections = []
        for identity2, path, data in payloads:
            physical = input_root / path
            physical.write_bytes(data)
            physical.chmod(0o600)
            original = source().originals[0].to_dict()
            original.update(artifact_id=identity2, path=path)
            del original["artifact"]
            del original["original_mode"]
            original["provenance"].update(method="supplied_local", outcome="available",
                                          supplied_locator=known(str(physical)).to_dict())
            selections.append({"artifact_id": identity2, "input_path": path})
            if identity2 == "text":
                extraction = source().extractions[0].to_dict()
                extraction.update(outputs=[original])
                meta["extractions"] = [extraction]
            else:
                meta["originals"].append(original)
        meta["locations"] = [item.to_dict() for item in source().locations]
        meta["locations"][1]["end"] = len(payloads[-1][2])
        meta["locations"].append({"location_id": "license-location", "artifact_id": "license", "kind": "section",
                                  "label": "Supplied license heading", "start": None, "end": None})
        prepared = prepare_source_capture(self.store, input_root, selected_files=selections, metadata=meta,
            record_id=identity, revision=1, expected_head=0, submission_id=identity + "-capture",
            record_provenance=CREATOR, submission_provenance=CONTROLLER, source_root=self.source_root,
            backup_roots=[], control_roots=[], max_file_bytes=10000, max_total_bytes=100000, max_files=10)
        return prepared.submission, source_content(prepared.submission.records[0])

    def prepared_dossier(self):
        """Prepare actual captured seeds and authored context/documents with forward exact references."""
        captured_batch, captured = self.capture()
        corpus = inventory([entry(selected=captured.originals[:1]),
                            entry("license-entry", selected=captured.originals[1:]), missing("reference", "reference_only")])
        value = replace(dossier(), declarations=[declaration(locations=[location()]),
                        replace(declaration("conflict"), category="contradiction", text="A supplied alternative remains unresolved"),
                        replace(declaration("remainder"), category="unprocessed_remainder", text="License and reference not inspected")])
        records = [project_record(value), corpus_envelope("corpus", 1, corpus, CREATOR), *captured_batch.records,
                   envelope("context", context())]
        for identity, kind, path in (("brief", "research_brief", "brief/research.md"),
                                     ("intake", "intake_report", "reports/intake/intake/report.md")):
            artifact = self.store.put_artifact(("Synthetic authored " + kind + "; no scientific validation\n").encode())
            document = replace(manifest(artifact), product_kind=kind, context=value.context,
                               linked_sources=[ref("capture", "linked_source", "source")],
                               build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest")],
                               files=[WorkProductFile(path, artifact)], entry_file=path)
            records.append(product(identity, document))
        return value, corpus, captured, records

    def test_empty_references_only_partial_and_short_substantive_note(self):
        """Empty, references-only and conflicting setup remain truthful; a supplied short note can support a proposal."""
        for identity, entries in (("empty", []), ("references", [missing("ref", "reference_only")])):
            value = replace(setup(), initial_corpus=ref(identity, "initial_corpus", "corpus_manifest"),
                            current_corpus=ref(identity, "current_corpus", "corpus_manifest"))
            self.store.submit_typed(request(identity, [project_record(value, identity=identity + "-project"),
                                                      corpus_envelope(identity, 1, inventory(entries), CREATOR)]))
            self.assertEqual(setup_presentation(value), "awaiting_materials")
        value, corpus, captured, records = self.prepared_dossier()
        receipt = self.store.submit_typed(request("dossier", records))
        self.assertEqual(self.store.get_typed_revision("project", 1)[1], value)
        self.assertEqual(setup_presentation(value), "awaiting_authorization")
        self.assertEqual(captured.reading.coverage, "uninspected")
        self.assertEqual(corpus.entries[0].inspection.coverage, "uninspected")
        self.assertEqual(value.inspection.uninspected, inspection().uninspected)
        self.assertEqual(self.store.submit_typed(request("dossier", records)), receipt)
        partial = successor(value, 2, brief=None, readiness=readiness("incomplete_intake"))
        self.store.submit_typed(request("partial", [project_record(partial, 2)], {"project": 1}))
        self.assertEqual(setup_presentation(partial), "setup_incomplete")

    def test_forward_orders_and_independently_committed_targets(self):
        """Supported exact targets work independently and in mixed-batch forward orders."""
        value, corpus, captured, records = self.prepared_dossier()
        for index, ordered in enumerate((records, records[::-1], records[2:] + records[:2])):
            root = self.parent / f"order{index}"
            with RecordStore.create(root) as store:
                for record in records:
                    for artifact in record.artifact_references:
                        store.put_artifact(self.store.read_artifact(artifact))
                store.submit_typed(request("ordered", ordered))
                self.assertEqual(store.get_typed_revision("project", 1)[1], value)
        for record in (records[2], records[1], records[3], records[4], records[5]):
            self.store.submit_typed(request(record.record_id, [record]))
        self.store.submit_typed(request("project", [records[0]]))
        self.assertEqual(self.store.get_typed_revision("project", 1)[1], value)

    def test_document_roles_context_and_dependency_sets(self):
        """Incoming roles reject false labels, stale/missing pins and context/source mismatches even on cache hits."""
        value, corpus, captured, records = self.prepared_dossier()
        extra_capture, _ = self.capture("outside")
        self.store.submit_typed(extra_capture)
        self.store.submit_typed(request("other-context", [envelope("other-context", context())]))
        self.store.submit_typed(request("other-corpus", [corpus_envelope("other-corpus", 1, inventory(), CREATOR)]))
        changes = [dict(product_kind="note"), dict(product_kind="reading_report"), dict(context=None),
                   dict(context=ref("other-context", "context", "research_context")), dict(build_dependencies=[]),
                   dict(build_dependencies=[ref("other-corpus", "build_dependency", "corpus_manifest")]),
                   dict(linked_sources=[]), dict(linked_sources=[ref("outside", "linked_source", "source")]),
                   dict(build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest"), ref("outside", "build_dependency", "source")]),
                   dict(build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest"), ref("other-context", "build_dependency", "research_context")])]
        for position in (4, 5):
            document = product_content(records[position])
            for change_fields in changes:
                bad_record = product(records[position].record_id, replace(document, **change_fields))
                bad_records = [*records]
                bad_records[position] = bad_record
                for ordered in (bad_records, bad_records[::-1]):
                    with self.subTest(position=position, fields=change_fields):
                        error = self.rejects(request("bad-role", ordered))
                        self.assertIn("project project@1", str(error))
        # Both document roles can encounter the same already cached valid typed manifest.
        for shared_kind in ("research_brief", "intake_report"):
            shared = product("shared", replace(product_content(records[4]), product_kind=shared_kind))
            linked = replace(value, brief=ref("shared", "research_brief", "work_product_manifest"),
                             intake_report=ref("shared", "intake_report", "work_product_manifest"),
                             declarations=[replace(value.declarations[0], links=[IntakeLink(
                                 ref("shared", "intake_work_product", "work_product_manifest"), "Explicit descriptive use")])])
            for ordered in ([project_record(linked), *records[1:4], shared], [shared, *records[1:4], project_record(linked)]):
                self.rejects(request("reuse", ordered))
        # No-context incomplete intake reports are allowed only with null document context.
        shell = replace(setup(), intake_report=value.intake_report)
        report = product("intake", replace(product_content(records[5]), context=None, linked_sources=[]))
        self.store.submit_typed(request("incomplete", [project_record(shell), *records[1:4], report]))
        next_value = successor(shell, 2, context=value.context)
        self.rejects(request("wrong-report-context", [project_record(next_value, 2)], {"project": 1}))

    def test_every_location_occurrence_and_current_entry_selection(self):
        """Missing, derived, unanchored, other-entry-only and wrong-pin locations cannot count as inspected seeds."""
        value, corpus, captured, records = self.prepared_dossier()
        for name in ("missing", "bytes", "upstream", "license-location"):
            for entry_id in ("seed", "reference", "absent"):
                bad_loc = location(entry_id, name=name)
                bad = replace(value, inspection=replace(value.inspection, locations=[location(), bad_loc]),
                              declarations=[declaration(locations=[location(), bad_loc])])
                for ordered in ([project_record(bad), *records[1:]], [*records[1:], project_record(bad)]):
                    error = self.rejects(request("bad-location", ordered))
                    self.assertIn("source_location target capture@1", str(error))
                    self.assertIn(name, str(error))
        second_capture, second_source = self.capture("other")
        self.store.submit_typed(second_capture)
        bad_loc = location(capture="other")
        bad = replace(value, inspection=replace(value.inspection, locations=[location(), bad_loc]),
                      declarations=[declaration(locations=[bad_loc])])
        self.rejects(request("wrong-source-pin", [project_record(bad), *records[1:]]))
        self.store.submit_typed(request("targets", records[1:]))
        bad_loc = location(name="bytes")
        bad = replace(value, inspection=replace(value.inspection, locations=[bad_loc]),
                      declarations=[declaration(locations=[bad_loc])])
        self.rejects(request("committed-location", [project_record(bad)]))

    def test_constrained_targets_and_optional_scientific_links(self):
        """Every optional link requires supported typed targets, while distinct scientific contexts are permitted."""
        value, corpus, captured, records = self.prepared_dossier()
        self.store.submit_typed(request("targets", records[1:]))
        self.store.submit(request("declarations", declarations()))
        graph = mixed_graph(self.store.put_artifact(b"Synthetic evidence"))
        # The existing graph owns context; keep its other contexts and reuse this exact context.
        self.store.submit_typed(request("graph", [r for r in graph if r.record_id != "context"]))
        links = [IntakeLink(ref(identity, role, kind), "Explicit relationship, not an endorsement") for identity, role, kind in (
            ("route-context", "intake_context", "research_context"), ("candidate", "intake_claim", "claim"),
            ("route", "intake_justification", "justification"), ("evidence", "intake_evidence", "evidence"),
            ("review-a", "intake_review", "review"), ("issue", "intake_issue", "issue"),
            ("brief", "intake_work_product", "work_product_manifest"))]
        linked = replace(value, declarations=[replace(value.declarations[0], links=links)])
        self.store.submit_typed(request("linked", [project_record(linked)]))
        for index, mode in enumerate(("generic", "unsupported", "malformed", "projection", "wrong-kind")):
            identity = f"invalid{index}"
            wire = product(identity, product_content(records[4])).to_dict()
            if mode == "generic": wire["content"] = {"arbitrary": "not typed"}
            elif mode == "unsupported": wire["content"]["version"] = 99
            elif mode == "malformed": del wire["content"]["authors"]
            elif mode == "projection": wire["record_references"] = []
            else: wire["kind"] = "project"
            self.store.submit(request(identity, [RecordEnvelope.from_dict(wire)]))
            for role in ("research_brief", "intake_report", "intake_work_product"):
                if role == "intake_work_product":
                    bad = successor(value, 2, declarations=[replace(value.declarations[0], links=[IntakeLink(
                        ref(identity, role, "work_product_manifest"), "Declared")])])
                else:
                    bad = successor(value, 2, **{"brief" if role == "research_brief" else "intake_report":
                                                ref(identity, role, "work_product_manifest")})
                self.rejects(request("invalid", [project_record(bad, 2)], {"project": 1}))
        self.rejects(request("missing", [project_record(successor(value, 2, context=ref("absent", "context", "research_context")), 2)], {"project": 1}))

    def test_source_reading_report_rejects_new_labels(self):
        """New project labels cannot satisfy the older incoming Source reading_report contract."""
        value, corpus, captured, records = self.prepared_dossier()
        self.store.submit_typed(request("targets", records[1:]))
        for identity in ("brief", "intake"):
            reading = replace(captured.reading, report=ref(identity, "reading_report", "work_product_manifest"))
            changed = replace(captured, reading=reading, supersedes=ref("capture", "supersedes", "source"))
            error = self.rejects(request("reading", [source_envelope("capture", 2, changed, CREATOR)], {"capture": 1}))
            self.assertIn("product_kind reading_report", str(error))

    def test_history_corrections_additions_forward_jumps_and_exact_old_pins(self):
        """Project corrections retain baselines, allow unchanged/forward corpus selections and keep historic document pins."""
        value, corpus, captured, records = self.prepared_dossier()
        self.store.submit_typed(request("first", records))
        second = successor(value, 2, declarations=[replace(value.declarations[0], text="Corrected attributed wording")])
        self.store.submit_typed(request("second", [project_record(second, 2)], {"project": 1}))
        c2 = corpus_successor(corpus, 2)
        c3 = replace(corpus_successor(c2, 3), entries=[*c2.entries, missing("later")], changes=[change("later")])
        self.store.submit_typed(request("corpus2", [corpus_envelope("corpus", 2, c2, CREATOR)], {"corpus": 1}))
        self.store.submit_typed(request("corpus3", [corpus_envelope("corpus", 3, c3, CREATOR)], {"corpus": 2}))
        new_docs = []
        for item in records[4:]:
            doc = replace(product_content(item), supersedes=ref(item.record_id, "supersedes", "work_product_manifest"),
                          build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest"),
                                              ref("corpus", "build_dependency", "corpus_manifest", 3)])
            new_docs.append(product(item.record_id, doc, 2))
        advanced = successor(second, 3, current_corpus=ref("corpus", "current_corpus", "corpus_manifest", 3),
                             brief=ref("brief", "research_brief", "work_product_manifest", 2),
                             intake_report=ref("intake", "intake_report", "work_product_manifest", 2))
        self.rejects(request("stale-docs", [project_record(replace(advanced, brief=value.brief), 3), *new_docs],
                             {"project": 2, "brief": 1, "intake": 1}))
        self.store.submit_typed(request("advance", [project_record(advanced, 3), *new_docs], {"project": 2, "brief": 1, "intake": 1}))
        self.assertEqual(self.store.get_typed_revision("project", 1)[1], value)
        self.assertEqual(advanced.initial_corpus.revision, 1)
        regression = successor(advanced, 4, current_corpus=value.current_corpus, brief=value.brief, intake_report=value.intake_report)
        self.rejects(request("regression", [project_record(regression, 4)], {"project": 3}))
        self.store.submit_typed(request("other", [corpus_envelope("other", 1, inventory(), CREATOR)]))
        rebound = successor(setup(), 4, initial_corpus=ref("other", "initial_corpus", "corpus_manifest"),
                            current_corpus=ref("other", "current_corpus", "corpus_manifest"))
        self.rejects(request("rebound", [project_record(rebound, 4)], {"project": 3}))
        # A new project may start at a later current corpus, provided the full corpus chain exists.
        self.store.submit_typed(request("new-project", [project_record(replace(advanced, supersedes=None), identity="new-project")]))

    def test_hidden_generic_history_and_original_retry_without_certification(self):
        """Relationally invalid generic snapshots remain locally readable but cannot hide behind later coherent pins."""
        value, corpus, captured, records = self.prepared_dossier()
        self.store.submit_typed(request("targets", records[1:]))
        invalid = replace(value, brief=ref("intake", "research_brief", "work_product_manifest"))
        original = request("generic-original", [project_record(invalid)])
        receipt = self.store.submit(original)
        corrected = successor(value, 2)
        self.rejects(request("corrected", [project_record(corrected, 2)], {"project": 1}))
        self.store.submit(request("generic-advance", [project_record(corrected, 2)], {"project": 1}))
        self.rejects(request("hidden", [project_record(successor(value, 3), 3)], {"project": 2}))
        self.assertEqual(self.store.get_typed_revision("project", 1)[1], invalid)
        for artifact in records[4].artifact_references:
            (self.root / "objects" / artifact.digest).unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(original), receipt)
        self.assertEqual(metadata(self.root), before)
        for changes in ({"revision_attribution": known("Other")}, {"revision_reason": "Changed"},
                        {"declarations": invalid.declarations[::-1]}):
            self.rejects(request("generic-original", [project_record(replace(invalid, **changes))]), SubmissionConflictError)
        # A wholly opaque predecessor cannot become a typed baseline/reset.
        self.store.submit(request("opaque", [RecordEnvelope("opaque", 1, "project", {}, CREATOR)]))
        opaque_next = replace(setup(), supersedes=ref("opaque", "supersedes", "project"))
        self.rejects(request("opaque-next", [project_record(opaque_next, 2, "opaque")], {"opaque": 1}))

    def test_shallow_old_roles_and_independently_checked_members(self):
        """Old Evidence, Issue and build dependencies remain shallow for damaged generic project attachments."""
        self.store.submit(request("declarations", declarations()))
        artifact = self.store.put_artifact(b"Synthetic evidence bytes")
        self.store.submit_typed(request("graph", mixed_graph(artifact)))
        self.store.submit_typed(request("corpus", [corpus_envelope("corpus", 1, inventory(), CREATOR)]))
        evidence = scientific_content(self.store.get_revision("evidence", 1))
        for index, mode in enumerate(("generic", "unsupported", "malformed")):
            identity = f"opaque{index}"
            attached = self.store.put_artifact(identity.encode())
            wire = project_record(setup(), identity=identity).to_dict()
            if mode == "generic": wire["content"] = {"arbitrary": "inert"}
            elif mode == "unsupported": wire["content"]["version"] = 99
            else: del wire["content"]["objective"]
            wire["artifact_references"] = [attached.to_dict()]
            self.store.submit(request(identity, [RecordEnvelope.from_dict(wire)]))
            (self.root / "objects" / attached.digest).unlink()
            input_value = replace(evidence, input_records=[ref(identity, "input_record", "project")])
            issue_value = replace(issue(), affected_records=[ref(identity, "affected_record", "project")], supporting_evidence=[])
            product_value = replace(manifest(artifact), build_dependencies=[ref(identity, "build_dependency", "project")])
            self.store.submit_typed(request("shallow" + str(index), [envelope("input" + str(index), input_value),
                assessment_envelope("issue" + str(index), issue_value), product("product" + str(index), product_value)]))
            next_value = replace(setup(), supersedes=ref(identity, "supersedes", "project"))
            for ordered in ([envelope("new-input", input_value), project_record(next_value, 2, identity)],
                            [project_record(next_value, 2, identity), envelope("new-input", input_value)]):
                self.rejects(request("constrained", ordered, {identity: 1, "new-input": 0}))
        malformed = project_record(setup(), identity="new-opaque").to_dict()
        malformed["content"]["version"] = 99
        shallow = replace(manifest(artifact), build_dependencies=[ref("new-opaque", "build_dependency", "project")])
        self.rejects(request("invalid-member", [product("new-product", shallow), RecordEnvelope.from_dict(malformed)]), DomainValidationError)

    def test_cached_metadata_closure_never_reads_transitive_bytes(self):
        """Repeated targets resolve metadata once; damaged historical bytes and public read APIs are never consulted."""
        value, corpus, captured, records = self.prepared_dossier()
        first = request("first", records)
        receipt = self.store.submit_typed(first)
        for record in records:
            for artifact in record.artifact_references:
                path = self.root / "objects" / artifact.digest
                if path.exists(): path.unlink()
        real_metadata = RecordStore._metadata_envelope
        resolved = []

        def lookup(store, connection, identity, revision):
            """Observe unique metadata reads within the existing transaction, retaining real decoding."""
            self.assertTrue(connection.in_transaction)
            resolved.append((identity, revision))
            return real_metadata(store, connection, identity, revision)

        with patch.object(RecordStore, "_metadata_envelope", lookup), \
                patch.object(ArtifactStore, "_verify_for_commit", side_effect=AssertionError("transitive artifact verification")), \
                patch.object(RecordStore, "get_revision", side_effect=AssertionError("public read")), \
                patch.object(RecordStore, "get_typed_revision", side_effect=AssertionError("typed read")), \
                patch.object(RecordStore, "history", side_effect=AssertionError("history read")), \
                patch.object(RecordStore, "read_artifact", side_effect=AssertionError("byte read")):
            self.store.submit_typed(request("next", [project_record(successor(value, 2), 2)], {"project": 1}))
            self.assertEqual(self.store.submit_typed(first), receipt)
        self.assertEqual(len(resolved), len(set(resolved)))
        self.assertIn(("capture", 1), resolved)
        self.assertIn(("project", 1), resolved)
        self.assertEqual(self.store.get_typed_revision("project", 1)[1], value)

    def test_saved_proposals_compete_with_one_cas_winner(self):
        """Independent owning-thread stores race saved proposals without rebasing or modifying losing bytes."""
        value, corpus, captured, records = self.prepared_dossier()
        self.store.submit_typed(request("first", records))
        proposals = [request(f"proposal{i}", [project_record(successor(value, 2, title=attributed(f"Choice {i}")), 2)], {"project": 1})
                     for i in range(2)]
        saved = []
        for proposal in proposals:
            path = self.parent / (proposal.submission_id + ".json")
            raw = json.dumps(proposal.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            path.write_bytes(raw)
            saved.append((path, raw))
        barrier = threading.Barrier(2, timeout=15)
        outcomes, failures = [], []

        def compete(index):
            """Use a fresh owning-thread handle and the original expected head after synchronization."""
            try:
                with RecordStore.open(self.root) as store:
                    proposal = Submission.from_dict(json.loads(saved[index][0].read_bytes()))
                    barrier.wait()
                    try:
                        outcomes.append((index, store.submit_typed(proposal)))
                    except RevisionConflictError:
                        outcomes.append((index, None))
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=compete, args=(i,)) for i in range(2)]
        for thread in threads: thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 2)
        winners = [(index, receipt) for index, receipt in outcomes if receipt is not None]
        self.assertEqual(len(winners), 1)
        winner, receipt = winners[0]
        self.assertIsNone(self.store.get_submission(proposals[1 - winner].submission_id))
        self.assertEqual(self.store.get_revision("project", 2), proposals[winner].records[0])
        for path, raw in saved: self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.store.submit_typed(proposals[winner]), receipt)
        self.assertEqual(len(self.store.audit_events()), 2)

    def test_fault_rollback_process_death_and_lost_acknowledgment(self):
        """Real existing seams preserve all-table rollback or exactly one original receipt/event across reopen."""
        import research_pipeline.store as store_module
        value, corpus, captured, records = self.prepared_dossier()
        batch = request("saved", records)
        saved = self.parent / "proposal.json"
        saved.write_text(json.dumps(batch.to_dict()), encoding="utf-8")
        for mode in ("exception", "exit"):
            for boundary in ("before_metadata", "after_first_revision", "after_commit"):
                root = self.parent / (mode + "-" + boundary)
                with RecordStore.create(root) as store:
                    for record in records:
                        for artifact in record.artifact_references:
                            store.put_artifact(self.store.read_artifact(artifact))
                    before = metadata(root)
                    if mode == "exception":
                        def fault(point):
                            """Raise at the selected real transaction seam, retaining storage recovery behavior."""
                            if point == boundary: raise RuntimeError("injected " + point)
                        with patch.object(store_module, "_fault", fault), self.assertRaises(RuntimeError):
                            store.submit_typed(batch)
                if mode == "exit":
                    self.child('''
import json, os, sys
from pathlib import Path
import research_pipeline.store as module
from research_pipeline.domain import Submission

def fault(point):
    """Terminate the interpreter at a real storage seam to exercise crash recovery."""
    if point == sys.argv[2]: os._exit(73)
module._fault = fault
with module.RecordStore.open(sys.argv[1]) as store:
    store.submit_typed(Submission.from_dict(json.loads(Path(sys.argv[3]).read_bytes())))
''', root, boundary, saved, expected=73)
                with RecordStore.open(root) as reopened:
                    if boundary != "after_commit":
                        self.assertEqual(metadata(root), before)
                        self.assertIsNone(reopened.get_submission("saved"))
                        receipt = reopened.submit_typed(batch)
                    else:
                        receipt = reopened.get_submission("saved")
                        self.assertIsNotNone(receipt)
                        stable = metadata(root)
                        self.assertEqual(reopened.submit_typed(batch), receipt)
                        self.assertEqual(metadata(root), stable)
                    self.assertEqual(len(reopened.audit_events()), 1)
                    self.assertEqual(reopened.get_typed_revision("project", 1)[1], value)
                    reopened.submit_typed(request("advance", [project_record(successor(value, 2), 2)], {"project": 1}))
                    for record in records:
                        for artifact in record.artifact_references:
                            path = root / "objects" / artifact.digest
                            if path.exists(): path.unlink()
                    stable = metadata(root)
                    self.assertEqual(reopened.submit_typed(batch), receipt)
                    self.assertEqual(metadata(root), stable)
                    for modified in (replace(value, title=attributed("Changed")),
                                     replace(value, revision_attribution=known("Other")),
                                     replace(value, declarations=value.declarations[::-1])):
                        with self.assertRaises(SubmissionConflictError):
                            reopened.submit_typed(request("saved", [project_record(modified), *records[1:]]))
                        self.assertEqual(metadata(root), stable)
                    with self.assertRaises(SubmissionConflictError):
                        reopened.submit_typed(request("saved", records[::-1]))
                    self.assertEqual(metadata(root), stable)
                output = self.child('''
import json, sys
from pathlib import Path
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    proposal = Submission.from_dict(json.loads(Path(sys.argv[2]).read_bytes()))
    receipt = store.submit_typed(proposal)
    assert receipt == store.get_submission("saved")
    assert store.head("project") == 2
    assert len(store.audit_events()) == 2
    assert store.get_typed_revision("project", 1)[1].readiness.status == "proposed_ready"
    print(json.dumps(receipt.to_dict()))
''', root, saved)
                self.assertEqual(json.loads(output), receipt.to_dict())
                self.assertEqual(metadata(root), stable)

    def test_healthy_backup_exact_restore_and_fresh_history(self):
        """Healthy backups retain complete history, byte objects, canonical submissions, receipts and audit events."""
        value, corpus, captured, records = self.prepared_dossier()
        first = request("first", records)
        receipt = self.store.submit_typed(first)
        c2 = corpus_successor(corpus, 2)
        self.store.submit_typed(request("corpus2", [corpus_envelope("corpus", 2, c2, CREATOR)], {"corpus": 1}))
        second = request("second", [project_record(successor(value, 2), 2)], {"project": 1})
        receipt2 = self.store.submit_typed(second)
        before = metadata(self.root)
        histories = {identity: self.store.history(identity) for identity, _, _ in before["identities"]}
        backup, destination = self.parent / "backup", self.parent / "restored"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        with restore_backup(backup, destination) as restored:
            self.assertEqual(metadata(destination), before)
            for identity, history in histories.items(): self.assertEqual(restored.history(identity), history)
            for record in records:
                for artifact in record.artifact_references:
                    self.assertEqual(restored.read_artifact(artifact), self.store.read_artifact(artifact))
            self.assertEqual(restored.submit_typed(first), receipt)
            self.assertEqual(restored.submit_typed(second), receipt2)
            self.assertEqual(metadata(destination), before)
        saved = self.parent / "requests.json"
        saved.write_text(json.dumps([first.to_dict(), second.to_dict()]), encoding="utf-8")
        output = self.child('''
import json, sys
from pathlib import Path
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    receipts = [store.submit_typed(Submission.from_dict(w)).to_dict() for w in json.loads(Path(sys.argv[2]).read_bytes())]
    history = [store.get_typed_revision("project", n)[1].to_dict() for n in (1, 2)]
    for identity in ("capture", "brief", "intake"):
        for artifact in store.get_revision(identity, 1).artifact_references:
            store.read_artifact(artifact)
    print(json.dumps([receipts, history]))
''', destination, saved)
        self.assertEqual(json.loads(output), [[receipt.to_dict(), receipt2.to_dict()],
                                             [value.to_dict(), successor(value, 2).to_dict()]])
        self.assertEqual(metadata(destination), before)

    def test_schema_one_refusal_and_explicit_migration(self):
        """Existing schema gating precedes targets/bytes; explicit migration preserves old receipts and new dossiers."""
        from tests.legacy import historical_store, table_values
        legacy_root = self.parent / "legacy"
        legacy, batches, _ = historical_store(legacy_root)
        self.addCleanup(legacy.close)
        before = metadata(legacy_root)
        with patch.object(RecordStore, "_check_typed_targets", side_effect=AssertionError("target admission")), \
                patch.object(ArtifactStore, "_verify_for_commit", side_effect=AssertionError("artifact admission")), \
                self.assertRaisesRegex(DomainValidationError, "migration"):
            legacy.submit_typed(request("project", [project_record(setup())]))
        self.assertEqual(metadata(legacy_root), before)
        original = table_values(legacy_root)
        old_receipts = [legacy.get_submission(batch.submission_id) for batch in batches]
        backup = self.parent / "v1-backup"
        create_backup(legacy, backup)
        migrated_root = self.parent / "migrated"
        with restore_backup(backup, migrated_root, target_schema=2, migration_provenance=CREATOR) as migrated:
            self.assertEqual(table_values(migrated_root), original)
            proposal = request("setup", [project_record(setup()), corpus_envelope("corpus", 1, inventory(), CREATOR)])
            receipt = migrated.submit_typed(proposal)
            for batch, old_receipt in zip(batches, old_receipts): self.assertEqual(migrated.submit(batch), old_receipt)
            backup2 = self.parent / "v2-backup"
            info = create_backup(migrated, backup2)
            self.assertEqual(inspect_backup(backup2), info)
            before = metadata(migrated_root)
            destination = self.parent / "v2-restored"
            with restore_backup(backup2, destination) as restored:
                self.assertEqual(metadata(destination), before)
                self.assertEqual(restored.get_typed_revision("project", 1)[1], setup())
                self.assertEqual(restored.submit_typed(proposal), receipt)
                for batch, old_receipt in zip(batches, old_receipts): self.assertEqual(restored.submit(batch), old_receipt)
                self.assertEqual(metadata(destination), before)

    def test_documented_example(self):
        """Execute the published example verbatim in a fresh candidate-source interpreter."""
        document = (self.source_root / "docs" / "project-intake.md").read_text()
        section = document.split("## Runnable local example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
