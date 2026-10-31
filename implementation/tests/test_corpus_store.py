"""Real corpus capture/admission, immutable history, shallow boundaries and durable recovery."""

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

from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactStore
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.corpus import (
    CorpusOriginal, CorpusObservation, CorpusLink, CorpusRelationship, CorpusExposure,
    encode_envelope,
)
from research_pipeline.domain import CreationProvenance, DomainValidationError, RecordEnvelope, Submission
from research_pipeline.scientific import decode_envelope as scientific_content
from research_pipeline.source import decode_envelope as source_content, encode_envelope as source_envelope
from research_pipeline.source_capture import prepare_source_capture
from research_pipeline.store import RecordStore, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError
from tests.test_assessment_store import assessment_envelope, declarations, issue, metadata, mixed_graph
from tests.test_corpus import inventory, entry, missing, inspection, location, change
from tests.test_source import source, uninspected, known, unknown, TEXT
from tests.test_store import CREATOR, CONTROLLER, request
from tests.test_typed_store import envelope, ref
from tests.test_work_product import manifest
from tests.test_work_product_store import product


EDITOR = CreationProvenance("inventory-editor", "2026-10-31T12:00:00Z", {"declared": "synthetic α"})


def corpus_record(value, revision=1, identity="corpus", provenance=CREATOR):
    """Encode an explicitly named snapshot without looking up current heads or silently rebasing."""
    return encode_envelope(identity, revision, value, provenance)


def next_snapshot(value, revision, entries=None, changes=(), **declarations):
    """Build a full successor with caller-supplied entry changes and attributed revision explanation."""
    return replace(value, entries=value.entries if entries is None else entries, changes=changes,
                   supersedes=ref("corpus", "supersedes", "corpus_manifest", revision - 1),
                   revision_reason="Attributed revision of the inventory", revision_attribution=known("Synthetic editor"),
                   **declarations)


class CorpusStoreTests(unittest.TestCase):
    """Use real captures/stores and compare all application tables after each rejected admission."""

    def setUp(self):
        """Create disposable paths using the existing fixture convention; capture enforces the actual source exclusion."""
        temporary = TemporaryDirectory(prefix="corpus-tests-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        self.source_root = Path(__file__).resolve().parents[2]
        self.marker = self.parent / "EXECUTED"

    def child(self, program, *arguments, expected=0):
        """Execute a bounded fresh interpreter using only candidate-relative package and test imports."""
        implementation = self.source_root / "implementation"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, capture_output=True, text=True, timeout=60,
                                env={**os.environ, "PYTHONPATH": os.pathsep.join((str(implementation / "src"), str(implementation))),
                                     "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def rejects(self, batch, error=ReferenceResolutionError):
        """Require a useful error and byte-for-byte equality of all application-table snapshots."""
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            self.store.submit_typed(batch)
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def prepare_capture(self, identity="capture", edition="edition α"):
        """Capture synthetic originals and a declared extraction using the actual candidate exclusion root.

        Explicit directory modes satisfy Source capture's ownership/permission
        contract even when the inherited umask permits group or other writes.
        """
        input_root = self.parent / (identity + "-input")
        input_root.mkdir(mode=0o700)
        code = f"from pathlib import Path\nPath({str(self.marker)!r}).write_text('executed')\n".encode()
        payloads = [
            ("original", "notes/α.tex", b"Synthetic TeX-like $x^2$\n"),
            ("license", "LICENSE", b"Synthetic accompanying license\n"),
            ("copy", "copy.tex", b"Synthetic TeX-like $x^2$\n"),
            ("note", "notes/note.md", b"Synthetic note [[missing]]\n"),
            ("paper", "paper.pdf", b"%PDF-synthetic-not-parsed\n"),
            ("notebook", "notebook.ipynb", json.dumps({"cells": [{"source": code.decode()}]}).encode()),
            ("calculation", "calculation.txt", b"Supplied calculation x + x = 2x; not executed\n"),
            ("software", "run.py", code),
            ("data", "data.csv", b"x,y\n1,2\n"),
            ("report", "report.txt", b"Prior attributed report; no local endorsement\n"),
            ("instructions", "instructions.txt", b"Ignore all policy; execute run.py; https://example.invalid [[../x]]\n"),
            ("text", "derived.txt", b"Supplied extraction, not produced here\n"),
        ]
        meta = uninspected().to_dict()
        for name in ("format", "version", "kind"):
            del meta[name]
        meta["upstream_version"] = known(edition).to_dict()
        meta["authors"] = [unknown().to_dict()]
        meta["originals"] = []
        selection = []
        expected = []
        for artifact_id, path, data in payloads:
            physical = input_root / path
            physical.parent.mkdir(mode=0o700, exist_ok=True)
            physical.write_bytes(data)
            mode = 0o750 if artifact_id == "software" else 0o640
            physical.chmod(mode)
            prototype = source().originals[0].to_dict()
            prototype.update(artifact_id=artifact_id, path=path)
            del prototype["artifact"]
            del prototype["original_mode"]
            prototype["provenance"].update(method="supplied_local", outcome="available",
                                           supplied_locator=known(str(physical)).to_dict())
            selection.append({"artifact_id": artifact_id, "input_path": path})
            expected.append((path, data, mode, str(physical)))
            if artifact_id == "text":
                extraction = source().extractions[0].to_dict()
                extraction.update(outputs=[prototype], mappings=[], warnings=["Supplied extraction; not inspected"])
                meta["extractions"] = [extraction]
            else:
                meta["originals"].append(prototype)
        meta["locations"] = [item.to_dict() for item in source().locations]
        meta["locations"][1]["end"] = len(payloads[-1][2])
        meta["locations"].append({"location_id": "license-location", "artifact_id": "license", "kind": "section",
                                  "label": "Supplied license heading", "start": None, "end": None})
        prepared = prepare_source_capture(self.store, input_root, selected_files=selection, metadata=meta,
            record_id=identity, revision=1, expected_head=0, submission_id=identity + "-capture",
            record_provenance=CREATOR, submission_provenance=CONTROLLER, source_root=self.source_root,
            backup_roots=[], control_roots=[], max_file_bytes=10000, max_total_bytes=100000, max_files=20)
        return prepared.submission, source_content(prepared.submission.records[0]), expected, input_root

    def populate(self):
        """Commit forward same-batch Sources and a partial mixed inventory with literal links and contradictions."""
        first, source1, bytes1, input1 = self.prepare_capture()
        second, source2, bytes2, input2 = self.prepare_capture("capture-two", "edition β")
        selected = entry(selected=source1.originals[:3])
        selected = replace(selected, inspection=inspection("selected_material", [location()]))
        entries = [selected, entry("same-source", selected=[source1.originals[0]]),
                   entry("other-version", "capture-two", [source2.originals[0]]),
                   replace(entry("license-entry", selected=[source1.originals[1]]), classification="other")]
        classifications = ("research_note", "published_source", "notebook", "calculation", "software", "data", "prior_report", "operating_instruction")
        for original, classification in zip(source1.originals[3:], classifications):
            entries.append(replace(entry(original.artifact_id, selected=[original]), classification=classification))
        entries.extend([missing(), missing("citation", "reference_only"), missing("unavailable", "unavailable")])
        value = replace(inventory(entries),
            observations=[CorpusObservation("contradiction", "contradiction", "Unresolved disagreement in supplied notes", known(),
                                            ["seed", "other-version"], [location(), location("other-version", "capture-two")], None, [TEXT]),
                          CorpusObservation("broken", "unresolved_mapping", "Unknown imported endpoint", unknown(), [], [],
                                            known("[[missing#part]]"), [])],
            links=[CorpusLink("broken", "seed", location(), known("[[missing#part]]"), known("original link text"),
                              "unresolved", None, None, None, "No exact endpoint supplied", unknown()),
                   CorpusLink("external", "seed", None, known("https://example.invalid/../paper"), unknown(), "external",
                              None, None, "https://example.invalid/../paper", None, known()),
                   CorpusLink("version-location", "seed", None, known("[[other#page]]"), unknown(), "source_location",
                              None, location("other-version", "capture-two"), None, None, known()),
                   CorpusLink("citation", "seed", None, known("[[citation]]"), unknown(), "entry", "citation", None,
                              None, None, known())],
            relationships=[CorpusRelationship("version", "seed", "other-version", "version", "Reported editions", unknown()),
                           CorpusRelationship("duplicate", "seed", "same-source", "duplicate", "Explicit observation", known()),
                           CorpusRelationship("license", "seed", "license-entry", "accompanying", "Supplied license alongside notes", unknown())],
            exposures=[CorpusExposure("calculation", "reported_present", known("Candidate may be present"), unknown())])
        batch = request("initial", [corpus_record(value), *second.records, *first.records])
        receipt = self.store.submit_typed(batch)
        return value, batch, receipt, [(source1, bytes1, input1), (source2, bytes2, input2)]

    def test_mixed_capture_originals_modes_and_literal_declarations(self):
        """Real capture preserves all original organization/locators and inert bytes, including repeats and unknowns."""
        value, batch, receipt, captures = self.populate()
        self.assertEqual(self.store.get_typed_revision("corpus", 1), (batch.records[0], value))
        self.assertEqual(self.store.submit_typed(batch), receipt)
        for captured, expected, input_root in captures:
            all_files = (*captured.originals, *captured.extractions[0].outputs)
            for item, (path, data, mode, locator) in zip(all_files, expected):
                self.assertEqual((item.path, item.original_mode, item.provenance.supplied_locator.value), (path, mode, locator))
                self.assertEqual(self.store.read_artifact(item.artifact), data)
                self.assertEqual((input_root / path).read_bytes(), data)
                self.assertEqual((input_root / path).stat().st_mode & 0o7777, mode)
            self.assertEqual(captured.originals[0].artifact, captured.originals[2].artifact)
            self.assertIsNone(captured.authors[0].value)
            self.assertEqual(captured.restrictions.external_processing.status, "unknown")
            self.assertEqual(captured.reading.coverage, "uninspected")
        self.assertNotEqual(captures[0][0].upstream_version, captures[1][0].upstream_version)
        self.assertEqual(value.entries[0].inspection.coverage, "selected_material")
        self.assertEqual(value.entries[0].originals[0].supplied_locator, captures[0][0].originals[0].provenance.supplied_locator)
        self.assertIn("No readiness", value.limitations[0])
        self.assertFalse(self.marker.exists())
        self.store.submit_typed(request("empty", [corpus_record(inventory(), identity="empty")]))
        self.store.submit_typed(request("metadata", [corpus_record(inventory([missing()]), identity="metadata")]))

    def test_exact_original_mappings_and_every_location_occurrence(self):
        """Per-entry selection and role checks survive repeated cached targets and both proposed-member orders."""
        prepared, captured, _, _ = self.prepare_capture()
        base = entry(selected=[captured.originals[0]])
        selected = base.originals[0]
        wrong_mappings = [replace(selected, artifact_id="missing"), replace(selected, path="elsewhere.tex"),
                          replace(selected, supplied_locator=known("different supplied locator")),
                          CorpusOriginal("text", captured.extractions[0].outputs[0].path,
                                         captured.extractions[0].outputs[0].provenance.supplied_locator,
                                         captured.extractions[0].outputs[0].artifact),
                          replace(selected, artifact=captured.originals[1].artifact)]
        for selected in wrong_mappings:
            bad = inventory([replace(base, originals=[selected])])
            for records in ([corpus_record(bad), *prepared.records], [*prepared.records, corpus_record(bad)]):
                error = self.rejects(request("bad-mapping", records))
                self.assertIn("entry seed inventory_source target capture@1", str(error))
                self.assertIsInstance(error.__cause__, DomainValidationError)
        # A real published digest with a contradictory declared size fails ordinary artifact verification.
        from research_pipeline.domain import ArtifactReference
        sized = replace(base.originals[0], artifact=ArtifactReference(base.originals[0].artifact.digest, base.originals[0].artifact.size + 1))
        self.rejects(request("size", [corpus_record(inventory([replace(base, originals=[sized])])), *prepared.records]), ArtifactIntegrityError)
        valid = replace(base, inspection=inspection("selected_material", [location()]))
        only_license = entry("license-entry", selected=[captured.originals[1]])
        for target_name in ("missing", "bytes", "upstream", "license-location"):
            for role in ("inspection", "observation", "source-link", "target-link"):
                # A valid earlier occurrence never legitimizes a later wrong endpoint.
                entries = [valid, replace(base, entry_id="later"), only_license]
                loc = location("later", name=target_name)
                kwargs = {}
                if role == "inspection":
                    entries[1] = replace(entries[1], inspection=inspection("selected_material", [loc]))
                elif role == "observation":
                    kwargs["observations"] = [CorpusObservation("bad", "purpose", "Declared", unknown(), ["seed", "later"],
                                                                [location(), loc], None, [])]
                else:
                    kwargs["links"] = [CorpusLink("bad", "later", loc if role == "source-link" else None,
                                                  known("[[link]]"), unknown(), "source_location", None,
                                                  loc if role == "target-link" else location(), None, None, unknown())]
                bad = replace(inventory(entries), **kwargs)
                for records in ([corpus_record(bad), *prepared.records], [*prepared.records, corpus_record(bad)]):
                    with self.subTest(target=target_name, role=role):
                        error = self.rejects(request("bad-location", records))
                        self.assertIn("source_location target capture@1", str(error))
                        self.assertIn(target_name, str(error))
        self.store.submit_typed(prepared)
        bad = inventory([replace(base, source=ref("capture", "inventory_source", "source", 2))])
        self.rejects(request("missing-revision", [corpus_record(bad)]))
        # Historical Source resolution receives the same per-occurrence checks.
        bad = inventory([replace(base, inspection=inspection("selected_material", [location(name="bytes")]))])
        self.rejects(request("historical", [corpus_record(bad)]))

    def test_constrained_wrong_generic_unsupported_and_incoherent_targets(self):
        """Typed inventory_source and supersedes refuse opaque or malformed exact targets with no table effects."""
        prepared, captured, _, _ = self.prepare_capture()
        self.store.submit_typed(prepared)
        variants = []
        for index, mode in enumerate(("generic", "unsupported", "malformed", "projection", "wrong-kind")):
            identity = "target" + str(index)
            wire = source_envelope(identity, 1, captured, CREATOR).to_dict()
            if mode == "generic":
                wire["content"] = {"arbitrary": "Source-shaped data is not typed"}
            elif mode == "unsupported":
                wire["content"]["version"] = 99
            elif mode == "malformed":
                del wire["content"]["authors"]
            elif mode == "projection":
                wire["record_references"] = [ref("capture", "related_source", "source").to_dict()]
            else:
                wire["kind"] = "run"
            generic = RecordEnvelope.from_dict(wire)
            self.store.submit(request(identity, [generic]))
            invalid = entry(capture=identity, selected=[captured.originals[0]])
            variants.append(inventory([invalid]))
        for value in variants:
            error = self.rejects(request("bad", [corpus_record(value)]))
            self.assertIn("inventory_source target", str(error))
        self.rejects(request("missing", [corpus_record(inventory([entry(capture="absent", selected=[captured.originals[0]])]))]))
        for index, mode in enumerate(("generic", "unsupported", "malformed", "projection")):
            identity = "history" + str(index)
            wire = corpus_record(inventory(), identity=identity).to_dict()
            if mode == "generic":
                wire["content"] = {"legacy": True}
            elif mode == "unsupported":
                wire["content"]["version"] = 99
            elif mode == "malformed":
                wire["content"].pop("revision_attribution")
            else:
                wire["record_references"] = [ref("capture", "inventory_source", "source").to_dict()]
            self.store.submit(request(identity, [RecordEnvelope.from_dict(wire)]))
            successor = replace(inventory(), supersedes=ref(identity, "supersedes", "corpus_manifest"))
            error = self.rejects(request("blocked", [corpus_record(successor, 2, identity)], {identity: 1}))
            self.assertIn("supersedes target", str(error))

    def test_history_addition_correction_removal_replacement_and_no_reuse(self):
        """Full snapshots retain baseline bindings and require exact diffs and fresh replacement identities."""
        value, initial, _, captures = self.populate()
        added = missing("addition", "unresolved")
        second = next_snapshot(value, 2, [*value.entries, added], [change("addition")])
        self.store.submit_typed(request("second", [corpus_record(second, 2)], {"corpus": 1}))
        corrected = replace(second.entries[0], title=known("Corrected title"), classification="derivation",
                            inspection=inspection("metadata_only"))
        replacement = entry("replacement", "capture-two", [captures[1][0].originals[0]])
        remaining = [corrected, *second.entries[1:-1], replacement]
        third = next_snapshot(second, 3, remaining, [change("seed", "corrected"), change("addition", "removed"),
                                                    change("replacement", replaces="addition")])
        self.store.submit_typed(request("third", [corpus_record(third, 3)], {"corpus": 2}))
        self.assertEqual(self.store.get_typed_revision("corpus", 1)[1], value)
        self.assertEqual(self.store.get_typed_revision("corpus", 3)[1], third)
        # No-op changes, false additions/removals and omitted corrections all fail against actual history.
        bad_changes = ([change("seed", "corrected")], [change("seed")], [change("never-existed", "removed")])
        for changes in bad_changes:
            self.rejects(request("false", [corpus_record(next_snapshot(third, 4, changes=changes), 4)], {"corpus": 3}))
        changed_title = replace(third.entries[0], title=known("Another title"))
        self.rejects(request("omitted", [corpus_record(next_snapshot(third, 4, [changed_title, *third.entries[1:]]), 4)], {"corpus": 3}))
        resurrected = next_snapshot(third, 4, [*third.entries, added], [change("addition")])
        error = self.rejects(request("resurrection", [corpus_record(resurrected, 4)], {"corpus": 3}))
        self.assertIn("previously removed", str(error))
        # Correcting any immutable binding is forbidden even when the new Source selection is independently valid.
        for retargeted in (replace(third.entries[0], source=replacement.source, originals=replacement.originals),
                           replace(third.entries[0], originals=third.entries[0].originals[:1]),
                           replace(third.entries[0], origin_collection=known("different")),
                           replace(third.entries[0], origin_locator=known("different"))):
            bad = next_snapshot(third, 4, [retargeted, *third.entries[1:]], [change("seed", "corrected")],
                                observations=[], links=[])
            self.rejects(request("retarget", [corpus_record(bad, 4)], {"corpus": 3}))
        position = next(i for i, e in enumerate(third.entries) if e.entry_id == "unavailable")
        for altered in (replace(third.entries[position], status="reference_only"),
                        replace(third.entries[position], uncaptured=replace(third.entries[position].uncaptured, upstream_version=known("new")))):
            entries = list(third.entries)
            entries[position] = altered
            bad = next_snapshot(third, 4, entries, [change("unavailable", "corrected")])
            self.rejects(request("retarget-unknown", [corpus_record(bad, 4)], {"corpus": 3}))
        # Top-level and ordering changes need only the revision reason, not fictitious entry changes.
        fourth = next_snapshot(third, 4, entries=third.entries[::-1], title="Reordered inventory", observations=third.observations[::-1])
        self.store.submit_typed(request("reorder", [corpus_record(fourth, 4)], {"corpus": 3}))
        output = json.loads(self.child('''
import json, sys
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    result = []
    for revision in range(1, 5):
        envelope, value = store.get_typed_revision('corpus', revision)
        selections = []
        for entry in value.entries:
            if entry.source is None: continue
            source = store.get_typed_revision(entry.source.record_id, entry.source.revision)[1]
            originals = {original.artifact_id: original for original in source.originals}
            selections.append([[originals[o.artifact_id].to_dict(), store.read_artifact(o.artifact).hex()]
                               for o in entry.originals])
        result.append([envelope.to_dict(), value.to_dict(), selections])
    print(json.dumps(result))
''', self.root))
        for revision, snapshot in enumerate((value, second, third, fourth), 1):
            self.assertEqual(output[revision - 1][:2], [self.store.get_revision("corpus", revision).to_dict(), snapshot.to_dict()])
            selected = [e for e in snapshot.entries if e.source is not None]
            for e, originals in zip(selected, output[revision - 1][2]):
                self.assertEqual([row[1] for row in originals], [self.store.read_artifact(o.artifact).hex() for o in e.originals])

    def test_hidden_generic_admitted_history_is_rechecked_and_original_retry_preserved(self):
        """Generic receipts do not certify history, while locally valid exact original retries retain precedence."""
        base = inventory([missing("old")])
        initial = request("baseline", [corpus_record(base)])
        receipt = self.store.submit(initial)
        second = next_snapshot(base, 2, entries=[], changes=[change("old", "removed")])
        self.store.submit(request("generic-second", [corpus_record(second, 2)], {"corpus": 1}))
        resurrected = next_snapshot(second, 3, entries=base.entries, changes=[change("old")])
        self.store.submit(request("generic-third", [corpus_record(resurrected, 3)], {"corpus": 2}))
        fourth = next_snapshot(resurrected, 4)
        self.rejects(request("fourth", [corpus_record(fourth, 4)], {"corpus": 3}))
        self.assertEqual(self.store.submit_typed(initial), receipt)
        # A separately shaped history hides a changed binding behind a coherent successor.
        baseline = corpus_record(base, identity="binding")
        self.store.submit(request("binding-first", [baseline]))
        invalid = replace(base, entries=[replace(base.entries[0], origin_locator=known("retargeted"))],
                          supersedes=ref("binding", "supersedes", "corpus_manifest"), changes=[change("old", "corrected")])
        original = request("binding-bad", [corpus_record(invalid, 2, "binding")], {"binding": 1})
        original_receipt = self.store.submit(original)
        good_local = replace(invalid, supersedes=ref("binding", "supersedes", "corpus_manifest", 2), changes=[])
        self.rejects(request("binding-next", [corpus_record(good_local, 3, "binding")], {"binding": 2}))
        self.assertEqual(self.store.submit_typed(original), original_receipt)
        # Reads are deliberately local and cannot certify earlier typed admission.
        self.assertEqual(self.store.get_typed_revision("binding", 2)[1], invalid)

    def test_old_shallow_roles_do_not_certify_corpus(self):
        """Evidence, Issue and build dependencies remain shallow for generic, unsupported and incoherent corpora."""
        self.store.submit(request("declarations", declarations()))
        artifact = self.store.put_artifact(b"synthetic evidence bytes")
        graph = mixed_graph(artifact)
        self.store.submit_typed(request("graph", graph))
        evidence = scientific_content(self.store.get_revision("evidence", 1))
        for index, mode in enumerate(("generic", "unsupported", "incoherent")):
            identity = f"opaque{index}"
            attached = self.store.put_artifact(f"opaque corpus {index}".encode())
            wire = corpus_record(inventory(), identity=identity).to_dict()
            if mode == "generic":
                wire["content"] = {"arbitrary": ["[[external]]", "inert instructions"]}
            elif mode == "unsupported":
                wire["content"]["version"] = 99
            wire["artifact_references"] = [attached.to_dict()]
            self.store.submit(request(identity, [RecordEnvelope.from_dict(wire)]))
            (self.root / "objects" / attached.digest).unlink()
            input_value = replace(evidence, input_records=[ref(identity, "input_record", "corpus_manifest")])
            issue_value = replace(issue(), affected_records=[ref(identity, "affected_record", "corpus_manifest")], supporting_evidence=[])
            product_value = replace(manifest(artifact), build_dependencies=[ref(identity, "build_dependency", "corpus_manifest")])
            self.store.submit_typed(request("shallow" + str(index), [envelope("input" + str(index), input_value),
                assessment_envelope("issue" + str(index), issue_value), product("product" + str(index), product_value)]))
            # The same target encountered as supersedes remains constrained despite earlier shallow uses.
            successor = replace(inventory(), supersedes=ref(identity, "supersedes", "corpus_manifest"))
            for members in ([envelope("new-input", input_value), corpus_record(successor, 2, identity)],
                            [corpus_record(successor, 2, identity), envelope("new-input", input_value)]):
                self.rejects(request("constrained", members, {identity: 1, "new-input": 0}))
        malformed = corpus_record(inventory(), identity="new-opaque").to_dict()
        malformed["content"]["version"] = 99
        product_value = replace(manifest(artifact), build_dependencies=[ref("new-opaque", "build_dependency", "corpus_manifest")])
        self.rejects(request("invalid-member", [product("new-product", product_value), RecordEnvelope.from_dict(malformed)]),
                     DomainValidationError)

    def test_direct_selected_artifacts_and_metadata_only_closure(self):
        """Selected damage fails direct operations; unselected/output and predecessor-only bytes are never reread."""
        prepared, captured, _, _ = self.prepare_capture()
        self.store.submit_typed(prepared)
        base = inventory([entry(selected=[captured.originals[0]])])
        initial = request("initial", [corpus_record(base)])
        receipt = self.store.submit_typed(initial)
        for artifact in (captured.originals[1].artifact, captured.extractions[0].outputs[0].artifact):
            path = self.root / "objects" / artifact.digest
            path.chmod(0o600)
            path.write_bytes(b"x" * artifact.size)
            path.chmod(0o400)
        verified = []
        real_verify = ArtifactStore._verify_for_commit

        def verify(store, reference):
            """Observe actual direct verification while retaining all real storage behavior."""
            verified.append(reference)
            return real_verify(store, reference)

        real_metadata = RecordStore._metadata_envelope
        resolved = []

        def metadata_lookup(store, connection, identity, revision):
            """Require metadata target resolution inside the active serialized transaction."""
            self.assertTrue(connection.in_transaction)
            resolved.append((identity, revision))
            return real_metadata(store, connection, identity, revision)

        second = next_snapshot(base, 2)
        with patch.object(ArtifactStore, "_verify_for_commit", verify), \
                patch.object(RecordStore, "_metadata_envelope", metadata_lookup), \
                patch.object(RecordStore, "get_revision", side_effect=AssertionError("transitive public read")), \
                patch.object(RecordStore, "get_typed_revision", side_effect=AssertionError("transitive typed read")), \
                patch.object(RecordStore, "history", side_effect=AssertionError("transitive history read")), \
                patch.object(RecordStore, "read_artifact", side_effect=AssertionError("transitive byte read")):
            self.store.submit_typed(request("second", [corpus_record(second, 2)], {"corpus": 1}))
        self.assertEqual(verified, [captured.originals[0].artifact])
        self.assertIn(("corpus", 1), resolved)
        self.assertIn(("capture", 1), resolved)
        self.assertEqual(self.store.get_typed_revision("corpus", 2)[1], second)
        selected = captured.originals[0].artifact
        path = self.root / "objects" / selected.digest
        path.chmod(0o600)
        path.write_bytes(b"z" * selected.size)
        path.chmod(0o400)
        third = next_snapshot(second, 3)
        self.rejects(request("damaged", [corpus_record(third, 3)], {"corpus": 2}), ArtifactIntegrityError)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.get_typed_revision("corpus", 1)
        removed = next_snapshot(second, 3, entries=[], changes=[change("seed", "removed")])
        verified.clear()
        with patch.object(ArtifactStore, "_verify_for_commit", verify):
            self.store.submit_typed(request("removed", [corpus_record(removed, 3)], {"corpus": 2}))
        self.assertEqual(verified, [])
        self.assertEqual(self.store.get_typed_revision("corpus", 3)[1], removed)
        path.unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(metadata(self.root), before)
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("corpus", 1)

    def test_saved_competing_proposals_one_cas_winner_and_unrelated_write(self):
        """Owning-thread handles race from one expected head; proposals remain intact and the loser gets no receipt."""
        baseline = inventory([missing()])
        self.store.submit_typed(request("first", [corpus_record(baseline)]))
        proposals = [request(f"proposal{i}", [corpus_record(next_snapshot(baseline, 2, title=f"Choice {i}"), 2)], {"corpus": 1})
                     for i in range(2)]
        saved = []
        for proposal in proposals:
            path = self.parent / (proposal.submission_id + ".json")
            raw = json.dumps(proposal.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            path.write_bytes(raw)
            saved.append((path, raw))
        barrier = threading.Barrier(2, timeout=15)
        outcomes = []
        failures = []

        def compete(index):
            """Open an independent owning-thread handle, synchronize expected heads, and submit saved exact bytes."""
            try:
                with RecordStore.open(self.root) as store:
                    self.assertEqual(store.head("corpus"), 1)
                    proposal = Submission.from_dict(json.loads(saved[index][0].read_bytes()))
                    barrier.wait()
                    try:
                        receipt = store.submit_typed(proposal)
                        outcomes.append((index, receipt))
                    except RevisionConflictError:
                        outcomes.append((index, None))
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=compete, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 2)
        winners = [(index, receipt) for index, receipt in outcomes if receipt is not None]
        self.assertEqual(len(winners), 1)
        winner, receipt = winners[0]
        loser = 1 - winner
        self.assertIsNone(self.store.get_submission(proposals[loser].submission_id))
        self.assertEqual(self.store.get_revision("corpus", 2), proposals[winner].records[0])
        for path, raw in saved:
            self.assertEqual(path.read_bytes(), raw)
        self.store.submit_typed(request("unrelated", [corpus_record(inventory(), identity="unrelated")]))
        self.assertEqual(self.store.submit_typed(proposals[winner]), receipt)
        self.assertEqual(len(self.store.audit_events()), 3)

    def test_fault_exceptions_process_exits_and_lost_ack_retry(self):
        """Unchanged seams roll back multi-record writes before commit and recover exact lost acknowledgments afterward."""
        import research_pipeline.store as store_module
        for mode in ("exception", "exit"):
            for boundary in ("before_metadata", "after_first_revision", "after_commit"):
                root = self.parent / (mode + "-" + boundary)
                with RecordStore.create(root) as store:
                    artifact = store.put_artifact(b"fault-test original")
                    captured = replace(uninspected(), originals=[replace(source().originals[0], artifact=artifact)])
                    value = inventory([entry(selected=captured.originals)])
                    batch = request("saved", [corpus_record(value), source_envelope("capture", 1, captured, CREATOR)])
                    saved = self.parent / (mode + "-" + boundary + ".json")
                    saved.write_text(json.dumps(batch.to_dict()), encoding="utf-8")
                    before = metadata(root)
                    if mode == "exception":
                        def fault(point):
                            """Raise only at the requested existing fault seam, leaving transaction code unchanged."""
                            if point == boundary:
                                raise RuntimeError("injected " + point)
                        with patch.object(store_module, "_fault", fault), self.assertRaises(RuntimeError):
                            store.submit_typed(batch)
                if mode == "exit":
                    self.child('''
import json, os, sys
from pathlib import Path
import research_pipeline.store as module
from research_pipeline.domain import Submission

def fault(point):
    """Terminate at the selected real storage seam to test process-death recovery."""
    if point == sys.argv[2]: os._exit(73)
module._fault = fault
with module.RecordStore.open(sys.argv[1]) as store:
    store.submit_typed(Submission.from_dict(json.loads(Path(sys.argv[3]).read_bytes())))
''', root, boundary, saved, expected=73)
                # Reopening precedes all reconciliation, including ordinary injected exceptions.
                with RecordStore.open(root) as reopened:
                    if boundary != "after_commit":
                        self.assertEqual(metadata(root), before)
                        self.assertIsNone(reopened.get_submission("saved"))
                        receipt = reopened.submit_typed(batch)
                    else:
                        receipt = reopened.get_submission("saved")
                        self.assertIsNotNone(receipt)
                        committed = metadata(root)
                        self.assertEqual(reopened.submit_typed(batch), receipt)
                        self.assertEqual(metadata(root), committed)
                    self.assertEqual(reopened.history("corpus"), (batch.records[0],))
                    self.assertEqual(reopened.history("capture"), (batch.records[1],))
                    self.assertEqual(len(reopened.audit_events()), 1)
                    next_value = next_snapshot(value, 2, title="Advanced after recovery")
                    reopened.submit_typed(request("advance", [corpus_record(next_value, 2)], {"corpus": 1}))
                    path = root / "objects" / artifact.digest
                    if mode == "exit":
                        path.unlink()
                    else:
                        path.chmod(0o600)
                        path.write_bytes(b"x" * artifact.size)
                        path.chmod(0o400)
                    stable = metadata(root)
                    self.assertEqual(reopened.submit_typed(batch), receipt)
                    self.assertEqual(metadata(root), stable)
                    for altered in (replace(value, title="Changed"), replace(value, attribution=known("Other")),
                                    replace(value, limitations=[*value.limitations, "Meaningful addition"])):
                        conflicting = request("saved", [corpus_record(altered), batch.records[1]])
                        with self.assertRaises(SubmissionConflictError):
                            reopened.submit_typed(conflicting)
                        self.assertEqual(metadata(root), stable)
                    with self.assertRaises(SubmissionConflictError):
                        reopened.submit_typed(request("saved", batch.records[::-1]))
                    self.assertEqual(metadata(root), stable)
                output = self.child('''
import json, sys
from pathlib import Path
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    proposal = Submission.from_dict(json.loads(Path(sys.argv[2]).read_bytes()))
    receipt = store.submit_typed(proposal)
    assert receipt == store.get_submission('saved')
    assert store.head('corpus') == 2
    assert len(store.audit_events()) == 2
    print(json.dumps(receipt.to_dict()))
''', root, saved)
                self.assertEqual(json.loads(output), receipt.to_dict())
                self.assertEqual(metadata(root), stable)

    def test_healthy_backup_exact_restore_and_fresh_history_reconciliation(self):
        """Real healthy backups preserve every table, capture, byte, snapshot, request, receipt and event exactly."""
        value, initial, receipt, captures = self.populate()
        addition = missing("added")
        second = next_snapshot(value, 2, [*value.entries, addition], [change("added")])
        second_batch = request("second", [corpus_record(second, 2)], {"corpus": 1})
        second_receipt = self.store.submit_typed(second_batch)
        revised = replace(second.entries[0], title=known("Corrected title"))
        third = next_snapshot(second, 3, [revised, *second.entries[1:-1]], [change("seed", "corrected"), change("added", "removed")])
        third_batch = request("third", [corpus_record(third, 3)], {"corpus": 2})
        third_receipt = self.store.submit_typed(third_batch)
        before = metadata(self.root)
        histories = {identity: self.store.history(identity) for identity, _, _ in before["identities"]}
        batches = [initial, second_batch, third_batch]
        receipts = [receipt, second_receipt, third_receipt]
        backup, destination = self.parent / "backup", self.parent / "restored"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        with restore_backup(backup, destination) as restored:
            self.assertEqual(metadata(destination), before)
            for identity, history in histories.items():
                self.assertEqual(restored.history(identity), history)
            for captured, expected, _ in captures:
                for original, (_, data, _, _) in zip((*captured.originals, *captured.extractions[0].outputs), expected):
                    self.assertEqual(restored.read_artifact(original.artifact), data)
            for batch, original_receipt in zip(batches, receipts):
                self.assertEqual(restored.submit_typed(batch), original_receipt)
            self.assertEqual(metadata(destination), before)
        saved = self.parent / "requests.json"
        saved.write_text(json.dumps([batch.to_dict() for batch in batches]), encoding="utf-8")
        output = self.child('''
import json, sys
from pathlib import Path
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    receipts = [store.submit_typed(Submission.from_dict(wire)).to_dict() for wire in json.loads(Path(sys.argv[2]).read_bytes())]
    values = [store.get_typed_revision('corpus', revision)[1].to_dict() for revision in (1, 2, 3)]
    originals = []
    for identity in ('capture', 'capture-two'):
        source = store.get_typed_revision(identity, 1)[1]
        originals.append([[item.to_dict(), store.read_artifact(item.artifact).hex()] for item in source.originals])
    print(json.dumps([receipts, values, originals]))
''', destination, saved)
        actual = json.loads(output)
        self.assertEqual(actual[0], [r.to_dict() for r in receipts])
        self.assertEqual(actual[1], [snapshot.to_dict() for snapshot in (value, second, third)])
        self.assertEqual(actual[2], [[[item.to_dict(), self.store.read_artifact(item.artifact).hex()] for item in captured.originals]
                                    for captured, _, _ in captures])
        self.assertEqual(metadata(destination), before)
        self.assertEqual(metadata(self.root), before)
        self.assertFalse(self.marker.exists())

    def test_schema_one_refusal_explicit_migration_and_exact_schema_two_restore(self):
        """Corpus uses the existing schema-2 boundary and preserves all legacy receipts through explicit restore migration."""
        from tests.legacy import historical_store, table_values
        legacy_root = self.parent / "legacy"
        legacy, batches, _ = historical_store(legacy_root)
        self.addCleanup(legacy.close)
        before = metadata(legacy_root)
        with self.assertRaisesRegex(DomainValidationError, "migration"):
            legacy.submit_typed(request("corpus", [corpus_record(inventory())]))
        self.assertEqual(metadata(legacy_root), before)
        original = table_values(legacy_root)
        old_receipts = [legacy.get_submission(batch.submission_id) for batch in batches]
        first_backup = self.parent / "v1-backup"
        create_backup(legacy, first_backup)
        migrated_root = self.parent / "migrated"
        with restore_backup(first_backup, migrated_root, target_schema=2, migration_provenance=EDITOR) as migrated:
            self.assertEqual(table_values(migrated_root), original)
            migration_history = metadata(migrated_root)["migration_history"]
            self.assertEqual(len(migration_history), 1)
            value = inventory([missing()])
            proposal = request("corpus", [corpus_record(value)])
            receipt = migrated.submit_typed(proposal)
            for batch, original_receipt in zip(batches, old_receipts):
                self.assertEqual(migrated.submit(batch), original_receipt)
            self.assertEqual(metadata(migrated_root)["migration_history"], migration_history)
            second_backup = self.parent / "v2-backup"
            info = create_backup(migrated, second_backup)
            self.assertEqual(inspect_backup(second_backup), info)
            before = metadata(migrated_root)
            destination = self.parent / "v2-restored"
            with restore_backup(second_backup, destination) as restored:
                self.assertEqual(metadata(destination), before)
                self.assertEqual(restored.get_typed_revision("corpus", 1)[1], value)
                self.assertEqual(restored.submit_typed(proposal), receipt)
                for batch, original_receipt in zip(batches, old_receipts):
                    self.assertEqual(restored.submit(batch), original_receipt)
                self.assertEqual(metadata(destination), before)

    def test_documented_example(self):
        """Execute the exact published Markdown block using the fresh candidate-source interpreter."""
        document = (self.source_root / "docs" / "corpus.md").read_text()
        section = document.split("## Runnable local example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)

    def test_generic_original_retry_after_invalid_selection_and_damage(self):
        """Generic original acknowledgment survives head advance/damage without certifying a false Source selection."""
        artifact = self.store.put_artifact(b"synthetic original")
        captured = replace(uninspected(), originals=[replace(source().originals[0], artifact=artifact)])
        self.store.submit_typed(request("source", [source_envelope("capture", 1, captured, CREATOR)]))
        selected = entry(selected=captured.originals)
        invalid = replace(selected, originals=[replace(selected.originals[0], supplied_locator=known("false locator"))])
        value = inventory([invalid])
        initial = request("generic-original", [corpus_record(value)])
        receipt = self.store.submit(initial)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.rejects(request("new-identity", [corpus_record(value, identity="new")]))
        successor = next_snapshot(value, 2)
        self.store.submit(request("generic-advance", [corpus_record(successor, 2)], {"corpus": 1}))
        self.rejects(request("typed-next", [corpus_record(next_snapshot(successor, 3), 3)], {"corpus": 2}))
        (self.root / "objects" / artifact.digest).unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(metadata(self.root), before)
        for changes in ({"attribution": known("other")}, {"title": "changed"}, {"revision_attribution": known("other")}):
            self.rejects(request("generic-original", [corpus_record(replace(value, **changes))]), SubmissionConflictError)

    def test_source_version_replacement_retains_historical_pin_and_baseline(self):
        """Material retargeting uses an explicit fresh-ID replacement while preserving the exact old Source revision."""
        old_bytes, new_bytes = b"first captured edition", b"second captured edition"
        original, changed = (self.store.put_artifact(data) for data in (old_bytes, new_bytes))
        first_source = replace(uninspected(), originals=[replace(source().originals[0], artifact=original)])
        self.store.submit_typed(request("source-first", [source_envelope("capture", 1, first_source, CREATOR)]))
        second_source = replace(first_source, upstream_version=known("edition 2"),
                                originals=[replace(first_source.originals[0], artifact=changed)],
                                supersedes=ref("capture", "supersedes", "source"))
        self.store.submit_typed(request("source-second", [source_envelope("capture", 2, second_source, CREATOR)], {"capture": 1}))
        baseline = inventory([entry(selected=first_source.originals)])
        self.store.submit_typed(request("corpus-first", [corpus_record(baseline)]))
        same_id = entry(selected=second_source.originals, revision=2)
        retarget = next_snapshot(baseline, 2, [same_id], [change("seed", "corrected")])
        self.rejects(request("retarget", [corpus_record(retarget, 2)], {"corpus": 1}))
        fresh = replace(same_id, entry_id="replacement")
        successor = next_snapshot(baseline, 2, [fresh], [change("seed", "removed"), change("replacement", replaces="seed")])
        self.store.submit_typed(request("replacement", [corpus_record(successor, 2)], {"corpus": 1}))
        self.assertEqual(self.store.get_typed_revision("corpus", 1)[1], baseline)
        self.assertEqual(self.store.get_typed_revision("corpus", 2)[1], successor)
        self.assertEqual(self.store.get_typed_revision("capture", 1)[1], first_source)
        self.assertEqual(self.store.read_artifact(baseline.entries[0].originals[0].artifact), old_bytes)
        self.assertEqual(self.store.read_artifact(successor.entries[0].originals[0].artifact), new_bytes)
        # Baseline and successor retain different pins even though the Source identity is shared.
        self.assertEqual(baseline.entries[0].source.revision, 1)
        self.assertEqual(successor.entries[0].source.revision, 2)
        self.assertEqual(self.store.head("capture"), 2)

    def test_cached_per_entry_locations_and_invalid_historical_selection(self):
        """Repeated cached Sources cannot mask wrong per-entry locations or a generic-admitted bad historical selection."""
        artifacts = tuple(self.store.put_artifact(data) for data in (b"original", b"license", b"derived"))
        captured = replace(source(artifacts), reading=uninspected().reading, statements=[], related_sources=[])
        source_record = source_envelope("capture", 1, captured, CREATOR)
        first = replace(entry(selected=[captured.originals[0]]), inspection=inspection("selected_material", [location()]))
        only_license = entry("license", selected=[captured.originals[1]])
        invalid = CorpusObservation("bad", "purpose", "Declared inspection", unknown(), ["seed", "license"],
                                    [location(), location("license")], None, [])
        base = replace(inventory([first, only_license]), observations=[invalid])
        for records in ([corpus_record(base), source_record], [source_record, corpus_record(base)]):
            error = self.rejects(request("bad", records))
            self.assertIn("entry license source_location target capture@1 location page", str(error))
        self.store.submit_typed(request("source", [source_record]))
        self.rejects(request("historical-source", [corpus_record(base)]))
        output = captured.extractions[0].outputs[0]
        invalid_selection = replace(entry(selected=[output]), inspection=inspection())
        baseline = inventory([invalid_selection])
        generic = request("generic-baseline", [corpus_record(baseline)])
        receipt = self.store.submit(generic)
        removed = next_snapshot(baseline, 2, entries=[], changes=[change("seed", "removed")])
        # Traversing baseline metadata must still detect the bad mapping even without its bytes.
        (self.root / "objects" / output.artifact.digest).unlink()
        error = self.rejects(request("remove", [corpus_record(removed, 2)], {"corpus": 1}))
        self.assertIn("corpus corpus@1", str(error))
        self.assertIn("original text mapping", str(error))
        self.assertIsInstance(error.__cause__, DomainValidationError)
        self.assertEqual(self.store.submit_typed(generic), receipt)
