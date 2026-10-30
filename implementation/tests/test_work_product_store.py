"""Real durable manifest admission, exact history, shallow declarations and preserved backups."""

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
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.store import RecordStore, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError
from research_pipeline.work_product import WorkProductFile, decode_envelope, encode_envelope
from tests.legacy import create_legacy, historical_store, table_values
from tests.test_assessment import forge
from tests.test_assessment_store import assessment_envelope, declarations, metadata, mixed_graph, review
from tests.test_store import CREATOR, request, record
from tests.test_typed_store import claim, context, envelope, ref
from tests.test_work_product import manifest, TEXT


EDITOR = CreationProvenance("editor", "2026-10-30T16:00:00Z", {"declared": "編集 α"})


def product(identity, value, revision=1, provenance=CREATOR):
    """Encode one explicitly attributed manifest with no implicit identity or revision inference."""
    return encode_envelope(identity, revision, value, provenance)


class WorkProductStoreTests(unittest.TestCase):
    """Use actual outside-source stores and snapshot all application tables on rejected requests."""

    def setUp(self):
        """Create a private temporary runtime and close handles before removing its parent."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "products ü #?"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def child(self, program, *arguments):
        """Execute real candidate-source Python in a fresh interpreter outside source, with a finite deadline."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source),
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def rejects(self, batch, error=ReferenceResolutionError):
        """Return the observed exception and require all metadata, receipts and events to remain unchanged."""
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            self.store.submit_typed(batch)
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def populate(self):
        """Admit all seven typed kinds together, with forward claims and cyclic shallow build declarations."""
        self.store.submit(request("declarations", declarations() + [record("branch", kind="branch"),
            record("run", kind="run"), record("source", kind="source")]))
        text = self.store.put_artifact(TEXT.encode())
        binary = self.store.put_artifact(b"\x00\xff\x80\n")
        value = replace(manifest(text), task=ref("task", "task", "task_specification"),
                        branch=ref("branch", "branch", "branch"), context=ref("context", "context", "research_context"),
                        run=ref("run", "run", "run"), linked_claims=[ref("candidate", "linked_claim", "claim")],
                        linked_sources=[ref("source", "linked_source", "source")],
                        build_dependencies=[ref("candidate", "build_dependency", "claim"),
                                            ref("peer", "build_dependency", "work_product_manifest")],
                        files=[WorkProductFile("notes/α.txt", text), WorkProductFile("data/raw.bin", binary),
                               WorkProductFile("copy.txt", text)], limitations=["Synthetic only", TEXT])
        peer = replace(manifest(text), build_dependencies=[ref("product", "build_dependency", "work_product_manifest")])
        initial = request("mixed", [product("product", value), *mixed_graph(text), product("peer", peer)])
        return value, initial, self.store.submit_typed(initial)

    def test_forward_batch_multifile_history_reopen_and_fresh_process(self):
        """Exact ordered links, text/binary bytes, attribution and nullable supersession survive restart and append."""
        value, initial, receipt = self.populate()
        first = initial.records[0]
        self.assertEqual(first.record_references, (
            ref("task", "task", "task_specification"), ref("branch", "branch", "branch"),
            ref("context", "context", "research_context"), ref("run", "run", "run"),
            ref("candidate", "linked_claim", "claim"), ref("source", "linked_source", "source"),
            ref("candidate", "build_dependency", "claim"), ref("peer", "build_dependency", "work_product_manifest")))
        self.assertEqual(first.artifact_references, (value.files[0].artifact, value.files[1].artifact))
        self.assertEqual(len(first.content["files"]), 3)
        changed_bytes = self.store.put_artifact(b"new edition\n")
        changed = replace(value, authors=[" Another author β "], title="Revised title",
                          supersedes=ref("product", "supersedes", "work_product_manifest"),
                          files=[WorkProductFile("notes/α.txt", changed_bytes)])
        second = product("product", changed, 2, EDITOR)
        append = request("append", [second], {"product": 1})
        second_receipt = self.store.submit_typed(append)
        third = product("product", replace(changed, supersedes=None), 3, EDITOR)
        self.store.submit_typed(request("optional-null", [third], {"product": 2}))
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.history("product"), (first, second, third))
        for expected in (first, second, third):
            exposed, decoded = self.store.get_typed_revision("product", expected.revision)
            self.assertEqual(exposed, expected)
            self.assertEqual(decoded.to_dict(), expected.content)
            exposed.content.clear()
            decoded.to_dict()["files"].clear()
            self.assertEqual(self.store.get_typed_revision("product", expected.revision)[0], expected)
            self.assertIsNone(exposed.operational_status)
            self.assertIsNone(exposed.scientific_disposition)
        self.assertEqual(self.store.read_artifact(value.files[0].artifact), TEXT.encode())
        self.assertEqual(self.store.read_artifact(value.files[1].artifact), b"\x00\xff\x80\n")
        self.assertEqual(self.store.read_artifact(changed_bytes), b"new edition\n")
        self.assertEqual(self.store.history("product")[0].provenance, CREATOR)
        self.assertEqual(self.store.history("product")[1].provenance, EDITOR)
        self.assertEqual(self.store.get_typed_revision("product", 2)[1].authors, (" Another author β ",))
        self.assertEqual((self.root / "objects" / changed_bytes.digest).stat().st_mode & 0o222, 0)
        output = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    values = [[e.to_dict(), v.to_dict()] for n in (1, 2, 3)
              for e, v in [store.get_typed_revision("product", n)]]
    receipts = [store.submit_typed(Submission.from_dict(json.loads(data))).to_dict() for data in sys.argv[2:]]
    print(json.dumps([values, receipts]))
''', self.root, json.dumps(initial.to_dict()), json.dumps(append.to_dict()))
        self.assertEqual(json.loads(output), [[[item.to_dict(), item.content] for item in (first, second, third)],
                                              [receipt.to_dict(), second_receipt.to_dict()]])

    def test_each_reference_role_missing_and_wrong_kind_is_atomic(self):
        """Every ordinary new manifest edge requires exact existence and its own declared kind."""
        artifact = self.store.put_artifact(b"files")
        self.store.submit(request("wrong", [record("wrong", kind="event")]))
        roles = (("task", "task", "task_specification"), ("branch", "branch", "branch"),
                 ("context", "context", "research_context"), ("run", "run", "run"),
                 ("linked_claims", "linked_claim", "claim"), ("linked_sources", "linked_source", "source"),
                 ("build_dependencies", "build_dependency", "claim"))
        for name, role, kind in roles:
            for target in ("absent", "wrong"):
                link = ref(target, role, kind)
                changed = replace(manifest(artifact), **{name: [link] if name in (
                    "linked_claims", "linked_sources", "build_dependencies") else link})
                error = self.rejects(request("bad", [envelope("early", context()), product("bad", changed)]))
                self.assertIn(role, str(error))
                self.assertIn(target + "@1", str(error))
        self.assertIsNone(self.store.head("early"))

    def test_historical_context_claim_and_recursive_closure(self):
        """Historical generic, unsupported and incoherent typed targets fail through manifest and claim closure."""
        artifact = self.store.put_artifact(b"direct")
        base = manifest(artifact)
        for index, kind in enumerate(("research_context", "claim")):
            name = "generic-" + str(index)
            self.store.submit(request(name, [record(name, kind=kind)]))
            value = (replace(base, context=ref(name, "context", kind)) if kind == "research_context" else
                     replace(base, linked_claims=[ref(name, "linked_claim", kind)]))
            error = self.rejects(request("bad", [product("bad", value)]))
            self.assertIsInstance(error.__cause__, NotTypedContentError)
        # A locally coherent historical claim still follows its invalid context.
        historical = envelope("historical", claim("generic-0"))
        self.store.submit(request("historical", [historical]))
        value = replace(base, linked_claims=[ref("historical", "linked_claim", "claim")])
        error = self.rejects(request("bad", [product("bad", value)]))
        self.assertIn("context target generic-0@1", str(error))
        self.assertIsInstance(error.__cause__, NotTypedContentError)
        self.store.submit(request("historical-product", [product("historical-product", value)]))
        successor = replace(base, supersedes=ref("historical-product", "supersedes", "work_product_manifest"))
        error = self.rejects(request("successor", [product("historical-product", successor, 2)],
                                     {"historical-product": 1}))
        self.assertIn("context target generic-0@1", str(error))
        # Advancing a context head cannot substitute for the pinned bad revision.
        self.store.submit_typed(request("new-scope", [envelope("generic-0", context(), 2)], {"generic-0": 1}))
        self.rejects(request("bad", [product("bad", value)]))
        for name, kind, content in (("future-context", "research_context", context()),
                                    ("future-claim", "claim", claim("generic-0", 2))):
            item = envelope(name, content)
            wire = item.to_dict()
            wire["content"]["version"] = 99
            self.store.submit(request(name, [RecordEnvelope.from_dict(wire)]))
            value = replace(base, **({"context": ref(name, "context", kind)} if kind == "research_context" else
                                    {"linked_claims": [ref(name, "linked_claim", kind)]}))
            error = self.rejects(request("bad", [product("bad", value)]))
            self.assertIsInstance(error.__cause__, DomainValidationError)
        incoherent = envelope("incoherent-claim", claim("generic-0", 2)).to_dict()
        incoherent["record_references"] = []
        self.store.submit(request("incoherent", [RecordEnvelope.from_dict(incoherent)]))
        error = self.rejects(request("bad", [product("bad", replace(base,
            linked_claims=[ref("incoherent-claim", "linked_claim", "claim")]))]))
        self.assertIn("record_references", str(error))

    def test_shallow_payloads_links_and_damaged_attachments_are_not_traversed(self):
        """All shallow roles accept generic or unsupported targets without reading their outgoing links or bytes."""
        direct = self.store.put_artifact(b"manifest bytes")
        transitive = self.store.put_artifact(b"transitive bytes")
        targets = [record(name, kind=kind, content={"format": "research_pipeline.work_product_content", "version": 99},
                          artifact_references=[transitive]) for name, kind in (
                              ("task", "task_specification"), ("branch", "branch"), ("run", "run"),
                              ("source", "source"), ("dependency", "claim"))]
        # Generic payloads and links are opaque to shallow typed admission.
        targets.append(record("generic", kind="work_product_manifest", artifact_references=[transitive],
                              record_references=[ref("dependency", "describes", "claim")]))
        self.store.submit(request("targets", targets))
        (self.root / "objects" / transitive.digest).unlink()
        value = replace(manifest(direct), task=ref("task", "task", "task_specification"),
                        branch=ref("branch", "branch", "branch"), run=ref("run", "run", "run"),
                        linked_sources=[ref("source", "linked_source", "source")],
                        build_dependencies=[ref("dependency", "build_dependency", "claim"),
                                            ref("generic", "build_dependency", "work_product_manifest")])
        self.store.submit_typed(request("valid", [product("valid", value)]))
        self.assertEqual(self.store.get_typed_revision("valid", 1)[1], value)
        error = self.rejects(request("bad", [product("bad", replace(value,
            linked_claims=[ref("dependency", "linked_claim", "claim")]))]))
        self.assertIsInstance(error.__cause__, DomainValidationError)
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_revision("dependency", 1)
        # Shallow references do not exempt independently submitted typed members.
        unsupported = product("new-dependency", manifest(direct)).to_dict()
        unsupported["content"]["version"] = 99
        bad = replace(manifest(direct), build_dependencies=[ref("new-dependency", "build_dependency", "work_product_manifest")])
        self.rejects(request("bad", [product("bad", bad), RecordEnvelope.from_dict(unsupported)]), DomainValidationError)

    def test_review_manifest_role_remains_shallow(self):
        """Review exposure declarations stay shallow for generic, unsupported and incoherent manifests."""
        artifact = self.store.put_artifact(b"bundle")
        self.store.submit(request("policy", [record("policy", kind="decision")]))
        self.store.submit_typed(request("scope", [envelope("target-context", context()), envelope("context", context()),
                                                  envelope("candidate", claim())]))
        for index, mode in enumerate(("generic", "unsupported", "incoherent")):
            identity = "manifest-" + str(index)
            item = product(identity, manifest(artifact)).to_dict()
            if mode == "generic":
                del item["content"]["format"]
            elif mode == "unsupported":
                item["content"]["version"] = 99
            else:
                item["artifact_references"] = []
            self.store.submit(request(identity, [RecordEnvelope.from_dict(item)]))
            value = replace(review(), context_manifest=ref(identity, "context_manifest", "work_product_manifest"),
                            reported_checks=[], route_assessments=[])
            self.store.submit_typed(request("review-" + str(index), [assessment_envelope("review-" + str(index), value)]))
            self.assertEqual(self.store.get_typed_revision("review-" + str(index), 1)[1], value)
            successor = replace(manifest(artifact), supersedes=ref(identity, "supersedes", "work_product_manifest"))
            self.rejects(request("next", [product(identity, successor, 2)], {identity: 1}))

    def test_supersession_local_errors_and_invalid_historical_targets(self):
        """Domain checks reject wrong identity/revision; historical supersession requires coherent typed manifests."""
        artifact = self.store.put_artifact(b"bundle")
        self.store.submit_typed(request("first", [product("product", manifest(artifact))]))
        for revision, target, target_revision in ((1, "product", 1), (2, "other", 1), (2, "product", 2),
                                                  (2, "product", 3), (3, "product", 1)):
            value = replace(manifest(artifact), supersedes=ref(target, "supersedes", "work_product_manifest", target_revision))
            # Generic construction preserves malformed content for the explicit typed boundary.
            item = RecordEnvelope("product", revision, "work_product_manifest", value.to_dict(), CREATOR,
                                  [value.supersedes], [artifact])
            self.rejects(request("bad", [item], {"product": revision - 1}), DomainValidationError)
        # A nonexistent identity cannot supply the predecessor required by an append.
        missing = replace(manifest(artifact), supersedes=ref("missing", "supersedes", "work_product_manifest"))
        self.rejects(request("missing", [product("missing", missing, 2)], {"missing": 1}), RevisionConflictError)
        self.store.submit(request("wrong-kind", [record("wrong-kind", kind="source")]))
        wrong = replace(manifest(artifact), supersedes=ref("wrong-kind", "supersedes", "work_product_manifest"))
        self.rejects(request("wrong-append", [product("wrong-kind", wrong, 2)], {"wrong-kind": 1}),
                     RevisionConflictError)
        for mode in ("generic", "unsupported", "incoherent", "recursive", "local"):
            identity = mode
            item = product(identity, manifest(artifact)).to_dict()
            if mode in ("generic", "recursive"):
                del item["content"]["format"]
            elif mode == "unsupported":
                item["content"]["version"] = 99
            elif mode == "incoherent":
                item["artifact_references"] = []
            self.store.submit(request(identity, [RecordEnvelope.from_dict(item)]))
            revision = 2
            if mode in ("recursive", "local"):
                value = replace(manifest(artifact), supersedes=ref(identity, "supersedes", "work_product_manifest",
                                                                  1 if mode == "recursive" else 2))
                historical = RecordEnvelope(identity, 2, "work_product_manifest", value.to_dict(), CREATOR,
                                            [value.supersedes], [artifact])
                self.store.submit(request(identity + "-second", [historical], {identity: 1}))
                revision = 3
                if mode == "local":
                    with self.assertRaisesRegex(DomainValidationError, "supersedes"):
                        self.store.get_typed_revision(identity, 2)
            value = replace(manifest(artifact), supersedes=ref(identity, "supersedes", "work_product_manifest", revision - 1))
            error = self.rejects(request("bad", [product(identity, value, revision)], {identity: revision - 1}))
            self.assertIn("supersedes target", str(error))
            self.assertIsInstance(error.__cause__, DomainValidationError)

    def test_supersession_closure_does_not_read_transitive_artifacts(self):
        """A valid predecessor's typed closure is checked under the write transaction without reading old bytes."""
        old = self.store.put_artifact(b"old")
        new = self.store.put_artifact(b"new")
        self.store.submit_typed(request("initial", [product("product", manifest(old))]))
        (self.root / "objects" / old.digest).unlink()
        value = replace(manifest(new), supersedes=ref("product", "supersedes", "work_product_manifest"))
        original = RecordStore._metadata_envelope
        seen = []

        def inspect(store, connection, identity, revision):
            """Observe real historical metadata reads while the serialized writer owns its transaction."""
            self.assertTrue(connection.in_transaction)
            seen.append((identity, revision))
            return original(store, connection, identity, revision)

        with patch.object(RecordStore, "_metadata_envelope", inspect):
            self.store.submit_typed(request("next", [product("product", value, 2)], {"product": 1}))
        self.assertIn(("product", 1), seen)
        self.assertEqual(self.store.get_typed_revision("product", 2)[1], value)
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("product", 1)

    def test_missing_corrupt_direct_objects_and_forged_projections_are_atomic(self):
        """Direct bytes and content/link coherence fail before any metadata is inserted."""
        for index, mode in enumerate(("missing", "corrupt")):
            artifact = self.store.put_artifact(("bytes-" + mode).encode())
            identity = "existing-" + str(index)
            self.store.submit_typed(request(identity, [product(identity, manifest(artifact))]))
            path = self.root / "objects" / artifact.digest
            if mode == "missing":
                path.unlink()
                error = ArtifactNotFoundError
            else:
                path.chmod(0o600)
                path.write_bytes(b"x" * artifact.size)
                path.chmod(0o400)
                error = ArtifactIntegrityError
            self.rejects(request("bad", [envelope("early", context()), product("bad", manifest(artifact))]), error)
            before = metadata(self.root)
            with self.assertRaises(error):
                self.store.get_typed_revision(identity, 1)
            self.assertEqual(metadata(self.root), before)
        artifact = self.store.put_artifact(b"healthy")
        item = product("bad", manifest(artifact))
        for name, invalid in (("artifact_references", []), ("artifact_references", [artifact, artifact]),
                              ("record_references", [ref("bad", "build_dependency", "work_product_manifest")])):
            self.rejects(request("bad", [forge(item, name, invalid)]), DomainValidationError)
        wire = item.to_dict()
        wire["content"]["files"][0]["path"] = "../escape"
        self.rejects(request("bad", [RecordEnvelope.from_dict(wire)]), DomainValidationError)

    def test_exact_retry_after_head_advance_and_damage_conflicting_content_order_attribution(self):
        """Original-ID reconciliation precedes current targets/objects/heads, while canonical changes conflict."""
        value, initial, receipt = self.populate()
        second = product("product", replace(value, supersedes=ref("product", "supersedes", "work_product_manifest")), 2)
        append = request("append", [second], {"product": 1})
        append_receipt = self.store.submit_typed(append)
        third = product("product", replace(value, supersedes=None), 3)
        self.store.submit_typed(request("later", [third], {"product": 2}))
        (self.root / "objects" / value.files[0].artifact.digest).unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(self.store.submit_typed(append), append_receipt)
        self.assertEqual(metadata(self.root), before)
        for changed in (replace(value, title="Different"), replace(value, authors=list(reversed(value.authors))),
                        replace(value, files=list(reversed(value.files))),
                        replace(value, build_dependencies=list(reversed(value.build_dependencies)))):
            altered = request(initial.submission_id, [product("product", changed), *initial.records[1:]])
            self.rejects(altered, SubmissionConflictError)
        altered = request(initial.submission_id, [product("product", value, provenance=EDITOR), *initial.records[1:]])
        self.rejects(altered, SubmissionConflictError)
        self.rejects(request(initial.submission_id, list(reversed(initial.records))), SubmissionConflictError)
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("product", 1)

    def test_generic_original_receipt_is_not_retroactive_typed_certification(self):
        """A generic commit with invalid constrained targets still reconciles through the typed API locally."""
        artifact = self.store.put_artifact(b"bundle")
        self.store.submit(request("generic-context", [record("context")]))
        value = replace(manifest(artifact), context=ref("context", "context", "research_context"))
        batch = request("original", [product("product", value)])
        receipt = self.store.submit(batch)
        self.assertEqual(self.store.submit_typed(batch), receipt)
        fresh = request("fresh", [product("other", value)])
        error = self.rejects(fresh)
        self.assertIsInstance(error.__cause__, NotTypedContentError)
        (self.root / "objects" / artifact.digest).unlink()
        before = metadata(self.root)
        self.assertEqual(self.store.submit_typed(batch), receipt)
        self.assertEqual(metadata(self.root), before)

    def test_independent_append_cas_preserves_history(self):
        """Two independent handles cannot both append against one expected head, and old content remains exact."""
        artifact = self.store.put_artifact(b"bundle")
        value = manifest(artifact)
        first = product("product", value)
        self.store.submit_typed(request("initial", [first]))
        with RecordStore.open(self.root) as other:
            expected = other.head("product")
            winner = product("product", replace(value, title="Winner", supersedes=ref("product", "supersedes", "work_product_manifest")), 2)
            loser = product("product", replace(decode_envelope(winner), title="Other author's proposal"), 2, EDITOR)
            self.store.submit_typed(request("winner", [winner], {"product": expected}))
            before = metadata(self.root)
            with self.assertRaises(RevisionConflictError):
                other.submit_typed(request("loser", [loser], {"product": expected}))
            self.assertEqual(metadata(self.root), before)
            self.assertEqual(other.history("product"), (first, winner))
            self.assertEqual(loser.content["title"], "Other author's proposal")

    def test_backup_exact_restore_preserves_generic_history_and_receipts(self):
        """Healthy backups preserve multiple editions, malformed generic payloads, ordered links and original requests."""
        value, initial, receipt = self.populate()
        new = self.store.put_artifact(b"revised binary\x00\xff")
        changed = replace(value, files=[WorkProductFile("notes/α.txt", new)],
                          supersedes=ref("product", "supersedes", "work_product_manifest"))
        append = request("next", [product("product", changed, 2, EDITOR)], {"product": 1})
        next_receipt = self.store.submit_typed(append)
        generic = []
        for name in ("missing-marker", "future-version", "incoherent"):
            item = product(name, value).to_dict()
            if name == "missing-marker":
                del item["content"]["format"]
            elif name == "future-version":
                item["content"]["version"] = 99
            else:
                item["record_references"] = item["record_references"][::-1]
            generic.append(RecordEnvelope.from_dict(item))
        generic_batch = request("generic", generic)
        generic_receipt = self.store.submit(generic_batch)
        before = metadata(self.root)
        histories = {identity: self.store.history(identity) for identity, _, _ in before["identities"]}
        backup, restored_root = self.parent / "backup", self.parent / "restored"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        with restore_backup(backup, restored_root) as restored:
            self.assertEqual(metadata(restored_root), before)
            for identity, history in histories.items():
                self.assertEqual(restored.history(identity), history)
            for item in generic:
                self.assertEqual(restored.get_revision(item.record_id, 1), item)
                with self.assertRaises(DomainValidationError):
                    restored.get_typed_revision(item.record_id, 1)
            self.assertEqual(restored.submit_typed(initial), receipt)
            self.assertEqual(restored.submit_typed(append), next_receipt)
            self.assertEqual(restored.submit(generic_batch), generic_receipt)
            self.assertEqual(restored.read_artifact(new), b"revised binary\x00\xff")
            self.assertEqual(restored.read_artifact(value.files[0].artifact), TEXT.encode())
            self.assertEqual(metadata(restored_root), before)
        output = self.child('''
import json, sys
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps([[e.to_dict(), v.to_dict()] for n in (1, 2)
                      for e, v in [store.get_typed_revision("product", n)]]))
''', restored_root)
        self.assertEqual(json.loads(output), [[item.to_dict(), item.content] for item in (initial.records[0], append.records[0])])

    def test_schema_one_refusal_and_explicit_migration_then_continued_backup(self):
        """Schema 1 refuses the new kind before target/byte checks; explicit migration preserves all original receipts."""
        with create_legacy(self.parent / "empty-legacy") as legacy:
            before = metadata(self.parent / "empty-legacy")
            value = replace(manifest(), context=ref("missing", "context", "research_context"))
            with self.assertRaisesRegex(DomainValidationError, "migration"):
                legacy.submit_typed(request("new", [product("new", value)]))
            self.assertEqual(metadata(self.parent / "empty-legacy"), before)
        legacy_root, backup = self.parent / "legacy", self.parent / "legacy-backup"
        legacy, requests, _ = historical_store(legacy_root)
        self.addCleanup(legacy.close)
        original = table_values(legacy_root)
        old_receipts = [legacy.get_submission(item.submission_id) for item in requests]
        create_backup(legacy, backup)
        migrated_root = self.parent / "migrated"
        with restore_backup(backup, migrated_root, target_schema=2, migration_provenance=EDITOR) as migrated:
            self.assertEqual(table_values(migrated_root), original)
            migration_history = metadata(migrated_root)["migration_history"]
            self.assertEqual(len(migration_history), 1)
            for old, old_receipt in zip(requests, old_receipts):
                self.assertEqual(migrated.submit(old), old_receipt)
                self.assertEqual(migrated.get_submission(old.submission_id), old_receipt)
            artifact = migrated.put_artifact(b"new manifest after explicit migration")
            value = replace(manifest(artifact), context=ref("context", "context", "research_context"),
                            linked_claims=[ref("claim-a", "linked_claim", "claim")])
            batch = request("continued", [product("product", value)])
            receipt = migrated.submit_typed(batch)
            self.assertEqual(migrated.history("claim-a"), legacy.history("claim-a"))
            self.assertEqual(metadata(migrated_root)["migration_history"], migration_history)
            continued = self.parent / "continued-backup"
            info = create_backup(migrated, continued)
            self.assertEqual(inspect_backup(continued), info)
            before = metadata(migrated_root)
            with restore_backup(continued, self.parent / "continued-restored") as restored:
                self.assertEqual(metadata(self.parent / "continued-restored"), before)
                self.assertEqual(restored.get_typed_revision("product", 1)[1], value)
                self.assertEqual(restored.submit_typed(batch), receipt)
                for old, old_receipt in zip(requests, old_receipts):
                    self.assertEqual(restored.submit(old), old_receipt)
                for identity, _, _ in before["identities"]:
                    self.assertEqual(restored.history(identity), migrated.history(identity))

    def test_documented_manifest_persistence_example(self):
        """Execute the actual Markdown Python example in a fresh candidate-source subprocess."""
        document = (Path(__file__).resolve().parents[2] / "docs" / "work-products.md").read_text()
        section = document.split("## Runnable manifest persistence example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
