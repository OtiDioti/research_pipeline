"""Passive ToolRelease admission across exact roles, generic origins and cached closures."""

from dataclasses import replace
import hashlib
import json

from research_pipeline.domain import CreationProvenance, DomainValidationError
from research_pipeline.scientific import Evidence, NotTypedContentError
from research_pipeline.source import encode_envelope as source_envelope
from research_pipeline.store import RecordNotFoundError, RecordStore
from research_pipeline.tool_release import ToolRelease, ToolReleaseLimitError, ToolReleaseValidationError
from tests.test_assessment_store import assessment_envelope, issue
from tests.test_source import uninspected
from tests.test_store import CREATOR, record, request
from tests.test_typed_store import context, envelope, ref
from tests.test_work_product import manifest
from tests.test_work_product_store import product
from tests.tool_registration_fixtures import (
    ROLES, RegistrationCase, altered, declaration, rows, tool,
)
from tests.tool_release_fixtures import RECORD_SLOTS, at, known, missing, rehash


def target(identity, kind, artifact, invalid_closure=False):
    """Build real supported targets, optionally pointing constrained roles at generic lookalikes.

    Dependencies are returned for generic storage so fresh consumers must validate
    the target's own closure, independently of its original persistence route.
    """
    bad_context = record(identity + "-context")
    good_context = envelope(identity + "-context", context())
    scope = ref(identity + "-context", "context", "research_context")
    if kind == "source":
        value = uninspected()
        if invalid_closure:
            value = replace(value, reading=replace(value.reading,
                report=ref(identity + "-report", "reading_report", "work_product_manifest")))
            return source_envelope(identity, 1, value, CREATOR), [record(identity + "-report", kind="work_product_manifest")]
        return source_envelope(identity, 1, value, CREATOR), []
    if kind == "work_product_manifest":
        value = replace(manifest(artifact), context=scope)
        return product(identity, value), [bad_context if invalid_closure else good_context]
    if kind == "tool_release":
        links = [(ROLES[3][0], ref(identity + "-child", "child_tool", "tool_release"))] if invalid_closure else []
        return tool(declaration(identity, links=links)), ([record(identity + "-child", kind="tool_release")] if invalid_closure else [])
    if kind == "evidence":
        value = Evidence([artifact], scope, "Declared affine check", [], "No execution asserted", [], [],
                         ["finite values"], "Synthetic result", [], [], "unverified")
        return envelope(identity, value), [bad_context if invalid_closure else good_context]
    value = replace(issue(), affected_records=[ref(identity, "affected_record", "issue")], supporting_evidence=[])
    if invalid_closure:
        value = replace(value, supporting_evidence=[ref(identity + "-evidence", "supporting_evidence", "evidence")])
    return assessment_envelope(identity, value), ([record(identity + "-evidence", kind="evidence")] if invalid_closure else [])


class ToolRegistrationTests(RegistrationCase):
    """Assert actual ordered metadata, detached reads and passive schema-3 effects."""

    def test_all_slots_forward_targets_and_passive_effects(self):
        """Local, remote and composite declarations preserve all pins, duplicates and attribution."""
        artifacts = self.stage()
        dependency = self.store.put_artifact(b"inert build lock")
        self.store.submit(request("shallow", [record("qualification", kind="tool_assessment")]))
        targets = []
        for identity, kind in (("source", "source"), ("manifest", "work_product_manifest"),
                               ("evidence", "evidence"), ("issue", "issue")):
            item, dependencies = target(identity, kind, artifacts[0])
            if kind == "source":
                source = uninspected()
                source = replace(source, reading=replace(source.reading,
                    report=ref("manifest", "reading_report", "work_product_manifest")))
                item = source_envelope(identity, 1, source, CREATOR)
            elif kind == "work_product_manifest":
                item = product(identity, replace(manifest(artifacts[0]), product_kind="reading_report",
                    context=ref("manifest-context", "context", "research_context")))
            elif kind == "issue":
                item = assessment_envelope(identity, replace(issue(), affected_records=[ref("issue", "affected_record", "issue")],
                    supporting_evidence=[ref("evidence", "supporting_evidence", "evidence")]))
            targets.extend([item, *dependencies])
        links = [
            (ROLES[0][0], ref("source", "reported_provenance", "source")),
            (ROLES[0][0], ref("source", "reported_provenance", "source")),
            (ROLES[1][0], ref("source", "implementation_source", "source")),
            (ROLES[2][0], ref("manifest", "implementation_source", "work_product_manifest")),
            (ROLES[3][0], ref("child", "child_tool", "tool_release", 2)),
            (ROLES[4][0], ref("qualification", "reported_qualification", "tool_assessment")),
            (ROLES[5][0], ref("evidence", "reported_evidence", "evidence")),
            (ROLES[6][0], ref("issue", "reported_issue", "issue")),
            (ROLES[7][0], ref("source", "build_dependency", "source")),
        ]
        child = declaration("child")
        self.store.submit_typed(request("child-first", [tool(child)]))
        values = []
        for name, kind in (("local", "local_program"), ("remote", "remote_service"), ("composite", "composite_workflow")):
            doc = declaration(name, kind, links, artifacts=True).to_dict()
            doc["reproducibility"]["dependency_artifacts"] = known([artifacts[0].to_dict(), dependency.to_dict()])
            doc["evidence_limitations"]["self_tests"]["value"].append(artifacts[1].to_dict())
            values.append(ToolRelease.from_dict(rehash(doc)))
        batch_records = [*(tool(value) for value in values), tool(child, 2), *targets]
        before = rows(self.root)
        batch = request("all-slots", batch_records, {r.record_id: (1 if r.record_id == "child" else 0) for r in batch_records})
        receipt = self.store.submit_typed(batch)
        self.assertEqual(receipt.revisions, tuple((r.record_id, r.revision) for r in batch_records))
        self.assertEqual(self.store.get_submission("all-slots"), receipt)
        canonical = json.dumps({"fingerprint_version": 1, "submission": batch.to_dict()},
                               sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        self.assertEqual(receipt.fingerprint, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        self.assertEqual(receipt.provenance, batch.provenance)
        event = self.store.audit_events()[-1]
        self.assertEqual((event.event_id, event.revisions, event.provenance),
                         (receipt.event_id, receipt.revisions, receipt.provenance))
        after = rows(self.root)
        for table in before.keys() - {"identities", "revisions", "record_links", "artifact_links", "artifacts", "submissions", "audit_events"}:
            self.assertEqual(after[table], before[table], table)
        expected_links = tuple(reference for _, reference in links)
        for value in values:
            stored, decoded = self.store.get_typed_revision(value.tool_id, 1)
            self.assertEqual(decoded, value)
            self.assertEqual(stored.record_references, expected_links)
            expected_artifacts = (*artifacts, dependency) if value.tool_id != "remote" else (artifacts[1], artifacts[2], artifacts[0], dependency)
            self.assertEqual(stored.artifact_references, expected_artifacts)
            self.assertIsNone(stored.operational_status)
            self.assertIsNone(stored.scientific_disposition)
            self.assertEqual(stored.provenance, CREATOR)
            self.assertNotEqual(stored.provenance.actor, decoded.to_dict()["identity"]["declared_by"]["value"])
            self.assertEqual(decoded.release_id, rehash(decoded.to_dict())["release_id"])
            stored.content["identity"]["display_name"] = "detached"
            decoded.to_dict()["identity"]["display_name"] = "detached"
            self.assertEqual(self.store.get_typed_revision(value.tool_id, 1)[1], value)
            actual = [r[3:] for r in after["record_links"] if r[:2] == (value.tool_id, 1)]
            self.assertEqual(actual, [(r.relationship, r.record_id, r.revision, r.target_kind) for r in expected_links])
        self.assertEqual([e.submission_id for e in self.store.audit_events()], ["shallow", "child-first", "all-slots"])

    def test_every_role_missing_and_wrong_kind(self):
        """Each fixed occurrence rejects absent exact targets and conflicting stable kinds atomically."""
        for index, (path, role, kind, _) in enumerate(ROLES):
            with self.subTest(role=role, kind=kind):
                identity = f"target-{index}"
                value = declaration(f"consumer-{index}", links=[(path, ref(identity, role, kind))])
                self.rejects(request(f"missing-{index}", [tool(value)]))
                self.store.submit(request(f"wrong-{index}", [record(identity, kind="decision")]))
                self.rejects(request(f"wrong-use-{index}", [tool(value)]))

    def test_constrained_generic_origins_and_invalid_closure_matrix(self):
        """Every constrained role accepts coherent generic origins and refuses all lookalike failures."""
        artifact = self.store.put_artifact(b"real target bytes")
        for index, (path, role, kind, constrained) in enumerate(ROLES):
            if not constrained:
                continue
            for mode in ("coherent", "generic", "unsupported", "malformed", "projection", "closure"):
                with self.subTest(kind=kind, mode=mode):
                    identity = f"target-{index}-{mode}"
                    item, dependencies = target(identity, kind, artifact, mode == "closure")
                    if mode in ("generic", "unsupported", "malformed"):
                        content = {} if mode == "generic" else {"format": "future"} if mode == "unsupported" else {"format": item.content["format"], "version": 1}
                        item = altered(item, content=content)
                    if mode == "projection":
                        item = altered(item, artifact_references=[artifact.to_dict(), artifact.to_dict()])
                    self.store.submit(request(f"origin-{identity}", [item, *dependencies]))
                    consumer = declaration(f"use-{identity}", links=[(path, ref(identity, role, kind))])
                    batch = request(f"consume-{identity}", [tool(consumer)])
                    if mode == "coherent":
                        self.store.submit_typed(batch)
                        self.assertEqual(self.store.get_typed_revision(consumer.tool_id, 1)[1], consumer)
                    else:
                        self.rejects(batch)

    def test_shallow_never_decodes_or_traverses(self):
        """Shallow supported kinds may be malformed or have invalid outgoing constrained closure."""
        artifact = self.store.put_artifact(b"target declaration")
        for index, path in enumerate((ROLES[0][0], ROLES[7][0])):
            role = "reported_provenance" if index == 0 else "build_dependency"
            for kind in ("source", "work_product_manifest", "tool_release", "evidence", "issue"):
                for mode in ("malformed", "closure"):
                    identity = f"shallow-{index}-{kind}-{mode}"
                    item, dependencies = target(identity, kind, artifact, True)
                    if mode == "malformed":
                        item = altered(item, content={"format": item.content["format"], "version": 1})
                    self.store.submit(request(f"origin-{identity}", [item, *dependencies]))
                    value = declaration(f"use-{identity}", links=[(path, ref(identity, role, kind))] * 2)
                    self.store.submit_typed(request(f"use-{identity}", [tool(value)]))
                    self.assertEqual(len(self.store.get_revision(value.tool_id, 1).record_references), 2)
        self.store.submit(request("assessment", [record("assessment", kind="tool_assessment")]))
        value = declaration("reported", links=[(ROLES[4][0], ref("assessment", "reported_qualification", "tool_assessment"))])
        self.store.submit_typed(request("report", [tool(value)]))
        self.assertIsNone(self.store.get_revision("reported", 1).operational_status)

    def test_shallow_occurrence_cannot_suppress_constrained_check(self):
        """Both batch worklist orders and cross-slot duplicates still reject a generic Source."""
        self.store.submit(request("generic", [record("source", kind="source")]))
        shallow = tool(declaration("shallow", links=[(ROLES[0][0], ref("source", "reported_provenance", "source"))]))
        constrained = tool(declaration("constrained", links=[
            (ROLES[0][0], ref("source", "reported_provenance", "source")),
            (ROLES[1][0], ref("source", "implementation_source", "source")),
            (ROLES[1][0], ref("source", "implementation_source", "source"))]))
        for index, members in enumerate(([shallow, constrained], [constrained, shallow])):
            self.rejects(request(f"ordering-{index}", members))

    def test_cached_manifest_must_meet_source_reading_report_role(self):
        """A Tool-cached implementation note cannot pass a later Source reading-report edge."""
        artifact = self.store.put_artifact(b"report text")
        note = product("report", manifest(artifact))
        source = replace(uninspected(), reading=replace(uninspected().reading,
            report=ref("report", "reading_report", "work_product_manifest")))
        source_record = source_envelope("source", 1, source, CREATOR)
        self.store.submit(request("origins", [source_record, note]))
        for index, order in enumerate((("source", "report"), ("report", "source"))):
            links = [(ROLES[1][0], ref(name, "implementation_source", "source" if name == "source" else "work_product_manifest")) for name in order]
            error = self.rejects(request(f"cached-{index}", [tool(declaration(f"use-{index}", links=links))]))
            self.assertIn("product_kind reading_report", str(error))

    def test_descriptive_self_cross_cycles_and_shared_closure(self):
        """Child cycles terminate, retain repeated links and create no canonical states."""
        values = [declaration(name, links=[(ROLES[3][0], ref(child, "child_tool", "tool_release"))
                  for child in (name, "left", "right", "right")]) for name in ("left", "right")]
        self.store.submit_typed(request("cycle", [tool(value) for value in values]))
        for value in values:
            item = self.store.get_revision(value.tool_id, 1)
            self.assertEqual(len(item.record_references), 4)
            self.assertIsNone(item.operational_status)
            self.assertIsNone(item.scientific_disposition)

    def test_error_distinctions_and_direct_read_order(self):
        """Local format/projection errors and exact missing reads keep their public distinctions."""
        item = tool()
        for index, (content, error) in enumerate((({}, NotTypedContentError), ({"format": "future"}, DomainValidationError),
                                                 ({"format": item.content["format"]}, ToolReleaseValidationError))):
            bad = altered(item, content=content)
            self.rejects(request(f"bad-{index}", [bad]), error)
        self.rejects(request("projection", [altered(item, record_references=[ref("tool", "child_tool", "tool_release").to_dict()])]), ToolReleaseValidationError)
        for revision in (None, True, 0, "1"):
            with self.subTest(revision=revision), self.assertRaises(DomainValidationError):
                altered(item, revision=revision)
        with self.assertRaises(RecordNotFoundError):
            self.store.get_typed_revision("absent", 1)

    def test_unknown_and_unavailable_collections_add_no_links(self):
        """Absent declared knowledge is preserved and contributes no inferred target occurrence."""
        doc = declaration().to_dict()
        for index, path in enumerate(RECORD_SLOTS):
            at(doc, path).update(missing("unknown" if index % 2 else "unavailable"))
        value = ToolRelease.from_dict(rehash(doc))
        self.store.submit_typed(request("unknowns", [tool(value)]))
        stored, decoded = self.store.get_typed_revision("tool", 1)
        self.assertEqual(stored.record_references, ())
        self.assertEqual(decoded.to_dict(), rehash(doc))
        self.assertEqual(rows(self.root)["record_links"], [])

    def test_default_codec_limits_apply_locally_and_to_constrained_targets(self):
        """The unchanged envelope ceiling is local input error and a chained reference error on reach."""
        oversized = CreationProvenance("curator", "2026-11-04T10:00:00Z", {"note": "x" * 262144})
        item = altered(tool(), provenance=oversized.to_dict())
        self.rejects(request("local-limit", [item]), ToolReleaseLimitError)
        self.store.submit(request("generic-limit", [item]))
        consumer = declaration("consumer", links=[(ROLES[3][0], ref("tool", "child_tool", "tool_release"))])
        error = self.rejects(request("consume-limit", [tool(consumer)]))
        self.assertIsInstance(error.__cause__, ToolReleaseLimitError)
        with self.assertRaises(ToolReleaseLimitError):
            self.store.get_typed_revision("tool", 1)

    def test_existing_schema_gate_and_schema_two_support(self):
        """Passive registration works on schema 2 and leaves unsupported schema 1 unchanged."""
        from tests.legacy import create_legacy

        with RecordStore.create(self.parent / "schema-two") as store:
            receipt = store.submit_typed(request("schema-two", [tool()]))
            self.assertEqual(store.get_typed_revision("tool", 1)[1], declaration())
            self.assertEqual(receipt.revisions, (("tool", 1),))
        legacy_root = self.parent / "schema-one"
        create_legacy(legacy_root)
        with RecordStore.open(legacy_root) as store:
            before = rows(legacy_root)
            with self.assertRaises(DomainValidationError):
                store.submit_typed(request("unsupported-kind", [tool()]))
            self.assertEqual(rows(legacy_root), before)
            self.assertIsNone(store.get_submission("unsupported-kind"))

    def test_exact_mixed_targets_survive_their_own_and_unrelated_head_advances(self):
        """Tool pins retain exact Source, manifest, Evidence and Issue revisions after head changes."""
        artifact = self.store.put_artifact(b"immutable historical target")
        members, links = [], []
        kinds = (("source", "source", "implementation_source", ROLES[1][0]),
                 ("manifest", "work_product_manifest", "implementation_source", ROLES[2][0]),
                 ("evidence", "evidence", "reported_evidence", ROLES[5][0]),
                 ("issue", "issue", "reported_issue", ROLES[6][0]))
        for name, kind, role, path in kinds:
            item, dependencies = target(name, kind, artifact)
            members.extend([item, *dependencies])
            links.append((path, ref(name, role, kind)))
        self.store.submit_typed(request("targets", members))
        old = {name: self.store.get_typed_revision(name, 1) for name, _, _, _ in kinds}
        next_source = replace(old["source"][1], supersedes=ref("source", "supersedes", "source"))
        next_manifest = replace(old["manifest"][1], title="New manifest head", supersedes=ref("manifest", "supersedes", "work_product_manifest"))
        advances = [source_envelope("source", 2, next_source, CREATOR), product("manifest", next_manifest, 2),
                    envelope("evidence", old["evidence"][1], 2), assessment_envelope("issue", old["issue"][1], 2)]
        self.store.submit_typed(request("advanced", advances, {name: 1 for name in old}))
        batch = request("historical", [tool(declaration(links=links))])
        self.store.submit(request("unrelated", [record("unrelated")]))
        self.store.submit(request("unrelated-next", [record("unrelated", 2)], {"unrelated": 1}))
        self.store.submit_typed(batch)
        self.assertEqual(self.store.get_revision("tool", 1).record_references, tuple(reference for _, reference in links))
        for name in old:
            self.assertEqual(self.store.head(name), 2)
            self.assertEqual(self.store.get_typed_revision(name, 1), old[name])
