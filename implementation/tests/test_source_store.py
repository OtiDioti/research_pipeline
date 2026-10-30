"""Real synthetic Source history, exact admission, backup/restore and unchanged shallow boundaries."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import CreationProvenance, DomainValidationError, RecordEnvelope
from research_pipeline.scientific import decode_envelope as scientific_content
from research_pipeline.source import RelatedSource, SourceStatement, encode_envelope
from research_pipeline.store import RecordStore, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError
from tests.legacy import create_legacy
from tests.test_assessment_store import assessment_envelope, declarations, issue, metadata, mixed_graph
from tests.test_source import source, uninspected, known, unknown, TEXT
from tests.test_store import CREATOR, request, record
from tests.test_typed_store import envelope, ref
from tests.test_work_product import manifest
from tests.test_work_product_store import product


EDITOR = CreationProvenance("source-editor", "2026-10-30T16:00:00Z", {"attribution": "Synthetic α"})
BYTES = (b"Synthetic TeX-like x^2\n", b"Synthetic license declaration\n", b"Supplied extraction: x squared\n")


def capture(identity, value, revision=1, provenance=CREATOR):
    """Encode an explicit exact capture without deriving upstream or report versions."""
    return encode_envelope(identity, revision, value, provenance)


class SourceStoreTests(unittest.TestCase):
    """Assert durable outcomes with real objects and complete application-table snapshots."""

    def setUp(self):
        """Create a disposable runtime using the established default temporary-directory convention."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "sources α #?"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def child(self, program, *arguments, expected=0):
        """Run a finite fresh candidate-source interpreter with bytecode disabled and explicit arguments."""
        source_path = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source_path),
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def rejects(self, batch, error=ReferenceResolutionError):
        """Require rejected admission to preserve every table, ordered link, head, receipt and event."""
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            self.store.submit_typed(batch)
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def populate(self):
        """Submit all eight typed kinds with forward references and retain legacy generic source history."""
        self.store.submit(request("declarations", [*declarations(), record("related", kind="source")]))
        artifacts = tuple(self.store.put_artifact(data) for data in BYTES)
        value = source(artifacts)
        report = replace(manifest(artifacts[2]), product_kind="reading_report",
                         linked_sources=[ref("capture", "linked_source", "source")])
        graph = mixed_graph(artifacts[1])
        for index, item in enumerate(graph):
            if item.kind == "evidence":
                content = scientific_content(item)
                graph[index] = envelope(item.record_id, replace(content, input_records=[
                    *content.input_records, ref("capture", "input_record", "source")]))
        initial = request("mixed", [capture("capture", value), product("report", report),
                                    capture("unseen", uninspected()), *graph])
        return value, report, initial, self.store.submit_typed(initial)

    def test_mixed_history_reports_backup_restore_and_fresh_reads(self):
        """Exact uses, byte lineage, corrections, independent report revisions and original receipts survive restore."""
        value, report, initial, receipt = self.populate()
        initial_metadata = metadata(self.root)
        old_evidence = self.store.get_revision("evidence", 1)
        self.assertEqual(self.store.get_typed_revision("unseen", 1)[1].reading.coverage, "uninspected")
        corrected = replace(value, title=known("Corrected α title"), supersedes=ref("capture", "supersedes", "source"))
        second = capture("capture", corrected, 2, EDITOR)
        correction = request("correction", [second], {"capture": 1})
        second_receipt = self.store.submit_typed(correction)
        new_bytes = b"Synthetic new upstream edition\n"
        new = self.store.put_artifact(new_bytes)
        changed = replace(corrected, upstream_version=known("edition β"),
                          originals=[replace(item, artifact=new) if item.artifact_id == "original" else item
                                     for item in corrected.originals],
                          supersedes=ref("capture", "supersedes", "source", 2))
        third = capture("capture", changed, 3)
        new_capture = request("new-bytes", [third], {"capture": 2})
        third_receipt = self.store.submit_typed(new_capture)
        report2 = replace(report, title="Revised separate reading report", supersedes=ref("report", "supersedes", "work_product_manifest"))
        report_request = request("report-next", [product("report", report2, 2, EDITOR)], {"report": 1})
        report_receipt = self.store.submit_typed(report_request)
        repinned = replace(changed, reading=replace(changed.reading, report=ref("report", "reading_report", "work_product_manifest", 2)),
                           supersedes=ref("capture", "supersedes", "source", 3))
        fourth = capture("capture", repinned, 4)
        repin_request = request("new-report-pin", [fourth], {"capture": 3})
        repin_receipt = self.store.submit_typed(repin_request)
        self.assertEqual(repinned.originals, changed.originals)
        self.assertEqual(repinned.upstream_version, changed.upstream_version)
        self.assertEqual(self.store.get_revision("evidence", 1), old_evidence)
        self.assertEqual(self.store.get_typed_revision("report", 2)[1].linked_sources, report.linked_sources)
        self.assertEqual(self.store.history("capture"), (initial.records[0], second, third, fourth))
        # Old use rows retain their exact positions and targets after all append operations.
        after = metadata(self.root)
        for row in initial_metadata["record_links"]:
            self.assertIn(row, after["record_links"])
        expected_histories = {identity: self.store.history(identity) for identity, _, _ in after["identities"]}
        requests = [initial, correction, new_capture, report_request, repin_request]
        receipts = [receipt, second_receipt, third_receipt, report_receipt, repin_receipt]
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        self.assertEqual(metadata(self.root), after)
        backup, restored_root = self.parent / "backup", self.parent / "restored"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        with restore_backup(backup, restored_root) as restored:
            self.assertEqual(metadata(restored_root), after)
            for identity, history in expected_histories.items():
                self.assertEqual(restored.history(identity), history)
            for item, data in zip((value.originals[0].artifact, value.originals[1].artifact,
                                   value.extractions[0].outputs[0].artifact, new), (*BYTES, new_bytes)):
                self.assertEqual(restored.read_artifact(item), data)
            for batch, expected in zip(requests, receipts):
                self.assertEqual(restored.submit_typed(batch), expected)
            self.assertEqual(restored.get_typed_revision("capture", 1)[1], value)
            self.assertEqual(restored.get_typed_revision("capture", 4)[1], repinned)
            self.assertEqual(metadata(restored_root), after)
        result = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    captures = [[e.to_dict(), v.to_dict()] for n in (1, 2, 3, 4)
                for e, v in [store.get_typed_revision("capture", n)]]
    reports = [store.get_revision("report", n).to_dict() for n in (1, 2)]
    receipts = [store.submit_typed(Submission.from_dict(batch)).to_dict() for batch in json.loads(sys.argv[2])]
    data = [store.read_artifact(a).hex() for a in store.get_revision("capture", 1).artifact_references]
    print(json.dumps([captures, reports, receipts, data]))
''', restored_root, json.dumps([batch.to_dict() for batch in requests]))
        result = json.loads(result)
        self.assertEqual(result[0], [[item.to_dict(), item.content] for item in expected_histories["capture"]])
        self.assertEqual(result[1], [item.to_dict() for item in expected_histories["report"]])
        self.assertEqual(result[2], [item.to_dict() for item in receipts])
        self.assertEqual(result[3], [data.hex() for data in BYTES])

    def test_every_reference_role_missing_wrong_kind_and_report_product_kind(self):
        """All Source roles require exact kinds; constrained reports additionally require reading_report content."""
        self.store.submit(request("wrong", [record("wrong", kind="run")]))
        base = uninspected()
        for target in ("missing", "wrong"):
            report = replace(base, reading=replace(base.reading, report=ref(target, "reading_report", "work_product_manifest")))
            related = replace(base, related_sources=[RelatedSource(ref(target, "related_source", "source"), TEXT)])
            variants = [report, related]
            for role, kind in (("reported_evidence", "evidence"), ("reported_tool_execution", "tool_execution")):
                check = ref(target, role, kind)
                variants.append(replace(base, reading=replace(base.reading, checks=[check])))
                variants.append(replace(base, statements=[SourceStatement("check", "referenced_check", TEXT, unknown(), [], [check], [])]))
            for value in variants:
                self.rejects(request("bad", [capture("bad", value)]))
        # A missing predecessor is rejected by ordinary CAS before Source history checks.
        self.rejects(request("absent", [capture("absent", replace(base, supersedes=ref("absent", "supersedes", "source")), 2)],
                             {"absent": 1}), RevisionConflictError)
        self.rejects(request("wrong-next", [capture("wrong", replace(base, supersedes=ref("wrong", "supersedes", "source")), 2)],
                             {"wrong": 1}), RevisionConflictError)
        a = self.store.put_artifact(b"Synthetic report")
        ordinary = manifest(a)
        self.store.submit_typed(request("ordinary", [product("ordinary", ordinary)]))
        value = replace(base, reading=replace(base.reading, report=ref("ordinary", "reading_report", "work_product_manifest")))
        self.rejects(request("bad-product", [capture("bad", value)]))
        # Both worklist orders must check each incoming role even after a target is cached.
        report_member = product("new-report", ordinary)
        value = replace(base, reading=replace(base.reading, report=ref("new-report", "reading_report", "work_product_manifest")))
        for members in ([capture("bad", value), report_member], [report_member, capture("bad", value)]):
            self.rejects(request("cached", members))

    def test_predecessor_continuity_legacy_transition_and_historical_closure(self):
        """Typed predecessors cannot be hidden by omitted links; generic history remains uncertified."""
        base = uninspected()
        self.store.submit_typed(request("first", [capture("capture", base)]))
        for value in (base, replace(base, work_id="different", supersedes=ref("capture", "supersedes", "source"))):
            error = self.rejects(request("bad", [capture("capture", value, 2)], {"capture": 1}))
            self.assertIsInstance(error.__cause__, DomainValidationError)
        for index, mode in enumerate(("version", "malformed", "incoherent", "legacy", "other-format")):
            identity = "history" + str(index)
            wire = capture(identity, base).to_dict()
            if mode == "version":
                wire["content"]["version"] = 99
            elif mode == "malformed":
                del wire["content"]["authors"]
            elif mode == "incoherent":
                wire["content"]["reading"]["checks"] = [ref("wrong", "reported_tool_execution", "tool_execution").to_dict()]
            elif mode == "legacy":
                wire["content"] = {"unvalidated": TEXT}
            else:
                wire["content"] = {"format": "other", "version": 999}
            self.store.submit(request(identity, [RecordEnvelope.from_dict(wire)]))
            if mode in ("legacy", "other-format"):
                self.rejects(request("explicit", [capture(identity, replace(base, supersedes=ref(identity, "supersedes", "source")), 2)], {identity: 1}))
                self.store.submit_typed(request(identity + "-typed", [capture(identity, base, 2)], {identity: 1}))
                self.assertEqual(self.store.get_revision(identity, 1).content, wire["content"])
            else:
                for predecessor in (None, ref(identity, "supersedes", "source")):
                    error = self.rejects(request("bad", [capture(identity, replace(base, supersedes=predecessor), 2)], {identity: 1}))
                    self.assertIsInstance(error.__cause__, DomainValidationError)
        # Generic persistence can retain locally coherent but historically invalid Source.
        second = capture("capture", base, 2)
        self.store.submit(request("generic-second", [second], {"capture": 1}))
        third = replace(base, supersedes=ref("capture", "supersedes", "source", 2))
        error = self.rejects(request("third", [capture("capture", third, 3)], {"capture": 2}))
        self.assertIn("supersedes", str(error))
        self.assertEqual(self.store.get_revision("capture", 2), second)

    def test_invalid_historical_report_and_evidence_closure(self):
        """Constrained Source closure checks old reports and Evidence metadata even when reached through predecessors."""
        base = uninspected()
        artifact = self.store.put_artifact(b"Synthetic report")
        self.store.submit_typed(request("note", [product("note", manifest(artifact))]))
        first = replace(base, reading=replace(base.reading, report=ref("note", "reading_report", "work_product_manifest")))
        self.store.submit(request("historical", [capture("capture", first)]))
        next_value = replace(base, supersedes=ref("capture", "supersedes", "source"))
        error = self.rejects(request("next", [capture("capture", next_value, 2)], {"capture": 1}))
        self.assertIn("product_kind", str(error))
        self.store.submit(request("generic-evidence", [record("evidence", kind="evidence")]))
        check = ref("evidence", "reported_evidence", "evidence")
        first = replace(base, reading=replace(base.reading, checks=[check]))
        self.store.submit(request("historical-evidence", [capture("with-evidence", first)]))
        next_value = replace(base, supersedes=ref("with-evidence", "supersedes", "source"))
        error = self.rejects(request("next", [capture("with-evidence", next_value, 2)], {"with-evidence": 1}))
        self.assertIsInstance(error.__cause__, DomainValidationError)

    def test_existing_shallow_source_roles_preserve_unvalidated_damaged_history(self):
        """Manifest, Evidence, Issue and related-source edges never traverse generic/unsupported/incoherent Sources."""
        value, report, initial, _ = self.populate()
        healthy = value.originals[1].artifact
        damaged = self.store.put_artifact(b"Transitive damaged source bytes")
        targets = []
        for index, mode in enumerate(("generic", "unsupported", "incoherent", "bad-history")):
            identity = "opaque" + str(index)
            wire = capture(identity, uninspected()).to_dict()
            wire["artifact_references"] = [damaged.to_dict()]
            if mode == "generic":
                wire["content"] = {"legacy": True}
            elif mode == "unsupported":
                wire["content"]["version"] = 99
            self.store.submit(request(identity, [RecordEnvelope.from_dict(wire)]))
            revision = 1
            if mode == "bad-history":
                self.store.submit(request(identity + "-two", [capture(identity, uninspected(), 2)], {identity: 1}))
                revision = 2
            targets.append((identity, revision))
        (self.root / "objects" / damaged.digest).unlink()
        for index, (identity, revision) in enumerate(targets):
            shallow = ref(identity, "related_source", "source", revision)
            own = replace(uninspected(), related_sources=[RelatedSource(shallow, TEXT)])
            product_value = replace(manifest(healthy), linked_sources=[ref(identity, "linked_source", "source", revision)])
            evidence = scientific_content(self.store.get_revision("evidence", 1))
            evidence = replace(evidence, input_records=[ref(identity, "input_record", "source", revision)])
            objection = replace(issue(), affected_records=[ref(identity, "affected_record", "source", revision)], supporting_evidence=[])
            self.store.submit_typed(request("shallow" + str(index), [capture("related" + str(index), own),
                product("use" + str(index), product_value), envelope("input" + str(index), evidence),
                assessment_envelope("issue" + str(index), objection)]))
        # A shallow edge cannot excuse a malformed independently submitted member.
        wire = capture("new-opaque", uninspected()).to_dict()
        wire["content"]["version"] = 99
        own = replace(uninspected(), related_sources=[RelatedSource(ref("new-opaque", "related_source", "source"), TEXT)])
        self.rejects(request("invalid-member", [capture("new", own), RecordEnvelope.from_dict(wire)]), DomainValidationError)

    def test_direct_damage_and_metadata_only_transitive_artifacts(self):
        """Missing/corrupt original or derived bytes fail direct operations, while predecessor traversal reads metadata only."""
        for index, (which, mode) in enumerate(((0, "missing"), (0, "corrupt"), (2, "missing"), (2, "corrupt"))):
            artifacts = tuple(self.store.put_artifact(data + bytes([index])) for data in BYTES)
            value = replace(source(artifacts), reading=uninspected().reading, statements=[], related_sources=[])
            identity = "capture" + str(index)
            self.store.submit_typed(request(identity, [capture(identity, value)]))
            path = self.root / "objects" / artifacts[which].digest
            if mode == "missing":
                path.unlink()
                error = ArtifactNotFoundError
            else:
                path.chmod(0o600)
                path.write_bytes(b"x" * artifacts[which].size)
                path.chmod(0o400)
                error = ArtifactIntegrityError
            self.rejects(request("bad", [capture("bad", value)]), error)
            before = metadata(self.root)
            with self.assertRaises(error):
                self.store.get_typed_revision(identity, 1)
            self.assertEqual(metadata(self.root), before)
            successor = replace(uninspected(), supersedes=ref(identity, "supersedes", "source"))
            self.store.submit_typed(request(identity + "-next", [capture(identity, successor, 2)], {identity: 1}))
            self.assertEqual(self.store.get_typed_revision(identity, 2)[1], successor)

    def test_original_receipts_competing_handles_and_conflicting_reuse(self):
        """CAS selects one next capture, exact retries survive damage, and changed requests conflict before admission."""
        value, _, initial, receipt = self.populate()
        successor = replace(value, supersedes=ref("capture", "supersedes", "source"))
        winner = request("winner", [capture("capture", successor, 2)], {"capture": 1})
        loser = request("loser", [capture("capture", replace(successor, title=known("Other")), 2, EDITOR)], {"capture": 1})
        with RecordStore.open(self.root) as other:
            self.assertEqual(other.head("capture"), 1)
            winner_receipt = self.store.submit_typed(winner)
            before = metadata(self.root)
            with self.assertRaises(RevisionConflictError):
                other.submit_typed(loser)
            self.assertEqual(metadata(self.root), before)
            self.assertEqual(other.history("capture"), (initial.records[0], winner.records[0]))
        third = replace(successor, supersedes=ref("capture", "supersedes", "source", 2))
        self.store.submit_typed(request("third", [capture("capture", third, 3)], {"capture": 2}))
        (self.root / "objects" / value.originals[0].artifact.digest).unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(self.store.submit_typed(winner), winner_receipt)
        self.assertEqual(metadata(self.root), before)
        for changed in (replace(value, title=known("Changed")), replace(value, authors=value.authors[::-1]),
                        replace(value, originals=value.originals[::-1]), replace(value, statements=value.statements[::-1])):
            self.rejects(request(initial.submission_id, [capture("capture", changed), *initial.records[1:]]), SubmissionConflictError)
        self.rejects(request(initial.submission_id, [capture("capture", value, provenance=EDITOR), *initial.records[1:]]), SubmissionConflictError)
        self.rejects(request(initial.submission_id, initial.records[::-1]), SubmissionConflictError)
        expectations = dict(initial.expected_heads)
        expectations["capture"] = 1
        self.rejects(request(initial.submission_id, initial.records, expectations), SubmissionConflictError)
        output = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps(store.submit_typed(Submission.from_dict(json.loads(sys.argv[2]))).to_dict()))
''', self.root, json.dumps(initial.to_dict()))
        self.assertEqual(json.loads(output), receipt.to_dict())
        self.assertEqual(metadata(self.root), before)

    def test_generic_original_reconciliation_is_not_typed_certification(self):
        """A locally valid generic commit keeps its receipt despite invalid targets/history and later damage."""
        artifacts = tuple(self.store.put_artifact(data) for data in BYTES)
        value = replace(uninspected(), originals=source(artifacts).originals)
        self.store.submit(request("generic-report", [record("report", kind="work_product_manifest")]))
        value = replace(value, reading=replace(value.reading, report=ref("report", "reading_report", "work_product_manifest")))
        initial = request("original", [capture("capture", value)])
        receipt = self.store.submit(initial)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.rejects(request("new", [capture("different", value)]))
        # Generic persistence may advance through invalid typed history; reconciliation still comes first.
        later = capture("capture", replace(value, work_id="changed"), 2)
        self.store.submit(request("generic-later", [later], {"capture": 1}))
        (self.root / "objects" / artifacts[0].digest).unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(metadata(self.root), before)

    def test_preview_read_only_orphans_and_serialized_history_checks(self):
        """Preview uses the shared checks without metadata writes; admission history stays inside its transaction."""
        first = capture("capture", uninspected())
        self.store.submit_typed(request("first", [first]))
        value = replace(uninspected(), supersedes=ref("capture", "supersedes", "source"))
        batch = request("next", [capture("capture", value, 2)], {"capture": 1})
        before = metadata(self.root)
        orphan = self.store.put_artifact(b"Published but unreferenced")
        original = RecordStore._metadata_envelope
        inspected = []

        def inspect(store, connection, identity, revision):
            """Observe real metadata lookup within the caller's snapshot without replacing its behavior."""
            self.assertTrue(connection.in_transaction)
            inspected.append((identity, revision))
            return original(store, connection, identity, revision)

        with patch.object(RecordStore, "_metadata_envelope", inspect):
            self.assertEqual(self.store._check_prepared_typed(batch), batch)
        self.assertEqual(metadata(self.root), before)
        self.assertEqual(self.store.read_artifact(orphan), b"Published but unreferenced")
        with self.assertRaises(ReferenceResolutionError):
            self.store._check_prepared_typed(request("bad", [capture("capture", uninspected(), 2)], {"capture": 1}))
        self.assertEqual(metadata(self.root), before)
        with patch.object(RecordStore, "_metadata_envelope", inspect):
            self.store.submit_typed(batch)
        self.assertIn(("capture", 1), inspected)

    def test_source_fault_seams_and_original_receipts_after_process_exit(self):
        """Real exits retain rollback versus post-COMMIT outcomes through unchanged shared transaction seams."""
        for index, boundary in enumerate(("before_metadata", "after_first_revision", "after_commit")):
            root = self.parent / ("crash" + str(index))
            with RecordStore.create(root):
                pass
            batch = request("crash", [capture("capture", uninspected())])
            before = metadata(root)
            self.child('''
import json, os, sys
import research_pipeline.store as module
from research_pipeline.domain import Submission

def fault(boundary):
    """Exit at one requested real metadata boundary, simulating a lost process."""
    if boundary == sys.argv[2]:
        os._exit(73)
module._fault = fault
with module.RecordStore.open(sys.argv[1]) as store:
    store.submit_typed(Submission.from_dict(json.loads(sys.argv[3])))
''', root, boundary, json.dumps(batch.to_dict()), expected=73)
            with RecordStore.open(root) as recovered:
                if boundary == "after_commit":
                    original_receipt = recovered.get_submission("crash")
                    committed = metadata(root)
                    self.assertEqual(recovered.submit_typed(batch), original_receipt)
                    self.assertEqual(metadata(root), committed)
                else:
                    self.assertIsNone(recovered.get_submission("crash"))
                    self.assertEqual(metadata(root), before)
                    recovered.submit_typed(batch)
                self.assertEqual(recovered.history("capture"), batch.records)
                self.assertEqual(len(recovered.audit_events()), 1)

    def test_schema_one_rejects_source_without_migration(self):
        """Source uses the existing schema-2 kind boundary; no new schema or implicit migration is introduced."""
        root = self.parent / "legacy"
        with create_legacy(root) as legacy:
            before = metadata(root)
            with self.assertRaisesRegex(DomainValidationError, "migration"):
                legacy.submit_typed(request("source", [capture("source", uninspected())]))
            self.assertEqual(metadata(root), before)

    def test_documented_source_example(self):
        """Execute the exact Markdown Python block in a fresh candidate-source interpreter."""
        document = (Path(__file__).resolve().parents[2] / "docs" / "sources.md").read_text()
        section = document.split("## Runnable synthetic typed-source persistence example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
