"""Complete implicit Tool histories, exact selected inspection and snapshot authority limits."""

from unittest.mock import Mock, patch

from research_pipeline.artifacts import ArtifactNotFoundError, ArtifactIntegrityError
from research_pipeline.domain import CreationProvenance
from research_pipeline.snapshot import RootSelector, SnapshotSelection
from research_pipeline.store import RecordStore, RecordNotFoundError, StoreDatabaseError
from research_pipeline.tool_release import ToolReleaseLimitError
from tests.snapshot_fixtures import limits
from tests.test_store import CREATOR, record, request
from tests.test_typed_store import ref
from tests.tool_registration_fixtures import (
    ROLES, RegistrationCase, altered, changed, declaration, rows, tool,
)
from tests.tool_release_fixtures import rehash

EDITOR = CreationProvenance("new-envelope-author", "2026-11-04T12:00:00Z", {"why": "new provenance"})


class ToolHistoryTests(RegistrationCase):
    """Follow older metadata without requiring old bytes or granting historical certification."""

    def test_three_revisions_exact_pins_and_independent_release_hash(self):
        """Unchanged content/new provenance and changed content retain immutable exact releases."""
        first = declaration()
        self.store.submit_typed(request("first", [tool(first)]))
        self.store.submit_typed(request("second", [tool(first, 2, EDITOR)], {"tool": 1}))
        third = changed(first, display_name="Amended affine declaration")
        self.assertEqual(third.release_id, rehash(third.to_dict())["release_id"])
        self.assertNotEqual(third.release_id, first.release_id)
        self.store.submit_typed(request("third", [tool(third, 3)], {"tool": 2}))
        self.store.submit(request("unrelated", [record("unrelated")]))
        self.store.submit(request("unrelated-advance", [record("unrelated", 2)], {"unrelated": 1}))
        consumer = declaration("consumer", links=[(ROLES[3][0], ref("tool", "child_tool", "tool_release", 2))])
        self.store.submit_typed(request("historical-use", [tool(consumer)]))
        self.assertEqual(self.store.history("tool"), (tool(first), tool(first, 2, EDITOR), tool(third, 3)))
        self.assertEqual(self.store.get_typed_revision("tool", 2)[1].release_id, first.release_id)
        self.assertEqual(self.store.get_revision("tool", 1).provenance, CREATOR)
        self.assertEqual(self.store.get_revision("tool", 2).provenance, EDITOR)
        self.assertEqual(self.store.get_revision("consumer", 1).record_references[0].revision, 2)

    def test_coherent_latest_cannot_hide_old_invalid_predecessors(self):
        """Both successor and consumer admission find failures two steps behind a coherent latest Tool."""
        for mode in ("generic", "unsupported", "malformed", "wrong-identity", "projection", "limit", "metadata", "closure"):
            with self.subTest(mode=mode):
                identity = "history-" + mode
                good = declaration(identity)
                first = tool(good)
                if mode in ("generic", "unsupported", "malformed"):
                    first = altered(first, content={} if mode == "generic" else {"format": "future"} if mode == "unsupported" else {"format": first.content["format"], "version": 1})
                elif mode == "wrong-identity":
                    first = altered(first, content=changed(good, tool_id="another").to_dict())
                elif mode == "projection":
                    first = altered(first, record_references=[ref(identity, "child_tool", "tool_release").to_dict()])
                elif mode == "limit":
                    first = altered(first, provenance=CreationProvenance("curator", "2026-11-04T10:00:00Z", {"note": "x" * 262144}).to_dict())
                elif mode == "closure":
                    bad_child = identity + "-bad-child"
                    self.store.submit(request(bad_child, [record(bad_child, kind="tool_release")]))
                    first = tool(declaration(identity, links=[(ROLES[3][0], ref(bad_child, "child_tool", "tool_release"))]))
                self.store.submit(request(identity + "-1", [first]))
                for revision in (2, 3):
                    self.store.submit(request(f"{identity}-{revision}", [tool(good, revision)], {identity: revision - 1}))
                if mode == "metadata":
                    self.damage("UPDATE revisions SET content_json=? WHERE record_id=? AND revision=1", ("{", identity))
                self.assertEqual(self.store.get_typed_revision(identity, 3)[1], good)
                error = self.rejects(request(identity + "-4", [tool(good, 4)], {identity: 3}))
                self.assertIsNotNone(error.__cause__ if mode != "closure" else error)
                if mode == "limit":
                    self.assertIsInstance(error.__cause__, ToolReleaseLimitError)
                if mode != "closure":
                    self.assertIn(identity + "@1", str(error))
                consumer = declaration(identity + "-consumer", links=[(ROLES[3][0], ref(identity, "child_tool", "tool_release", 3))])
                self.rejects(request(identity + "-consume", [tool(consumer)]))
                shallow = declaration(identity + "-shallow", links=[(ROLES[7][0], ref(identity, "build_dependency", "tool_release", 3))])
                self.store.submit_typed(request(identity + "-report", [tool(shallow)]))

    def test_missing_predecessor_after_open_rejects_without_further_effects(self):
        """A genuinely absent older row is detected during admission using the already-open handle."""
        value = declaration()
        for revision in (1, 2, 3):
            self.store.submit_typed(request(f"rev-{revision}", [tool(value, revision)], {"tool": revision - 1}))
        self.damage("DELETE FROM revisions WHERE record_id=? AND revision=?", ("tool", 1))
        error = self.rejects(request("successor", [tool(value, 4)], {"tool": 3}))
        self.assertIn("tool@1", str(error))
        self.assertIsInstance(error.__cause__, RecordNotFoundError)
        consumer = declaration("consumer", links=[(ROLES[3][0], ref("tool", "child_tool", "tool_release", 3))])
        self.rejects(request("consume", [tool(consumer)]))
        self.assertEqual(self.store.get_typed_revision("tool", 3)[1], value)

    def test_history_and_constrained_targets_are_metadata_only(self):
        """Unavailable historical and child bytes do not block fresh direct-byte-complete admission."""
        artifacts = self.stage()
        old = declaration("tool", "local_program", artifacts=True)
        self.store.submit_typed(request("old", [tool(old)]))
        current = declaration("tool")
        self.store.submit_typed(request("current", [tool(current, 2)], {"tool": 1}))
        for mode in ("missing", "corrupt"):
            path = self.object_path(artifacts[0])
            if mode == "missing":
                path.unlink()
            else:
                path.write_bytes(b"damaged")
                path.chmod(0o400)
            consumer = declaration(mode, links=[(ROLES[3][0], ref("tool", "child_tool", "tool_release"))])
            # These public read paths must never be used by transitive admission.
            with patch.object(RecordStore, "get_revision", side_effect=AssertionError("transitive read")), \
                    patch.object(RecordStore, "get_typed_revision", side_effect=AssertionError("transitive typed read")), \
                    patch.object(RecordStore, "history", side_effect=AssertionError("transitive history read")):
                self.store.submit_typed(request(mode, [tool(consumer)]))
                revision = 3 if mode == "missing" else 4
                self.store.submit_typed(request(mode + "-successor", [tool(current, revision)], {"tool": revision - 1}))
            with self.assertRaises(ArtifactNotFoundError if mode == "missing" else ArtifactIntegrityError):
                self.store.get_typed_revision("tool", 1)
            self.assertEqual(self.store.get_typed_revision(mode, 1)[1], consumer)

    def test_snapshot_local_classification_has_no_history_or_admission_authority(self):
        """Snapshot codec recognition neither expands implicit history nor verifies artifact bytes."""
        self.store.submit(request("project", [record("project", kind="project")]))
        self.store.submit(request("old", [record("tool", kind="tool_release")]))
        value = declaration()
        self.store.submit(request("selected", [tool(value, 2)], {"tool": 1}))
        examples = [altered(tool(declaration("generic")), content={}),
                    altered(tool(declaration("unsupported")), content={"format": "future"}),
                    altered(tool(declaration("malformed")), content={"format": value.to_dict()["format"], "version": 1}),
                    altered(tool(declaration("version")), content={**declaration("version").to_dict(), "version": 2})]
        self.store.submit(request("examples", examples))
        self.stage()
        local = tool(declaration("local", "local_program", artifacts=True))
        self.store.submit_typed(request("local", [local]))
        self.object_path(local.artifact_references[0]).unlink()
        chosen = SnapshotSelection(RootSelector("project", 1), tuple(RootSelector(name, revision) for name, revision in
                                   (("tool", 2), ("generic", 1), ("unsupported", 1), ("malformed", 1), ("version", 1), ("local", 1))))
        snapshot = self.store.capture_snapshot(chosen, limits=limits())
        categories = {r["record_id"]: r["classification"] for r in snapshot.records}
        self.assertEqual({name: item["category"] for name, item in categories.items()}, {
            "project": "generic", "tool": "locally_decoded", "generic": "generic", "unsupported": "unsupported",
            "malformed": "malformed_typed", "version": "unsupported", "local": "locally_decoded"})
        self.assertEqual(categories["tool"]["detail"], "No historical admission certification.")
        self.assertEqual(categories["version"]["diagnostic"], "unsupported_version")
        self.assertNotIn(("tool", 1), [(r["record_id"], r["revision"]) for r in snapshot.records])
        consumer = declaration("consumer", links=[(ROLES[3][0], ref("tool", "child_tool", "tool_release", 2))])
        self.rejects(request("consumer", [tool(consumer)]))

    def test_authority_reader_hooks_and_failures_are_preserved(self):
        """Tool predecessor reads use the supplied reader and retain hook without masking owner errors."""
        from research_pipeline.operating_authority import AuthorityIntegrityError, AuthorityLimitError

        value = declaration()
        for revision in (1, 2, 3):
            self.store.submit_typed(request(f"rev-{revision}", [tool(value, revision)], {"tool": revision - 1}))
        batch = request("fourth", [tool(value, 4)], {"tool": 3})
        before = rows(self.root)
        with self.store._transaction() as connection:
            def read(key):
                """Resolve actual metadata on the caller's existing transaction connection."""
                return self.store._metadata_envelope(connection, *key)

            reader = Mock(history=Mock(return_value=None), read=Mock(side_effect=read), retain_typed=Mock())
            envelopes, values = self.store._check_typed_targets(connection, batch, (value,), authority_reader=reader)
            self.assertEqual(set(values), {("tool", revision) for revision in (1, 2, 3, 4)})
            self.assertEqual([call.args[0] for call in reader.read.call_args_list], [("tool", 3), ("tool", 2), ("tool", 1)])
            self.assertEqual([call.args[0].revision for call in reader.retain_typed.call_args_list], [3, 2, 1])
            self.assertEqual(envelopes[("tool", 1)], tool(value))
            for operation in ("read", "retain_typed"):
                for error in (AuthorityLimitError("bounded"), AuthorityIntegrityError("integrity"),
                              StoreDatabaseError("storage"), AssertionError("programming")):
                    with self.subTest(operation=operation, error=type(error).__name__):
                        reader = Mock(history=Mock(return_value=None), read=Mock(side_effect=read), retain_typed=Mock())
                        getattr(reader, operation).side_effect = error
                        with self.assertRaises(type(error)) as caught:
                            self.store._check_typed_targets(connection, batch, (value,), authority_reader=reader)
                        self.assertIs(caught.exception, error)
        self.assertEqual(rows(self.root), before)

    def test_shared_histories_decode_once_but_preserve_every_incoming_occurrence(self):
        """Repeated exact histories share caches while both committed consumers keep their full pins."""
        from research_pipeline.tool_release_envelope import decode_envelope

        value = declaration()
        for revision in (1, 2, 3):
            self.store.submit_typed(request(f"rev-{revision}", [tool(value, revision)], {"tool": revision - 1}))
        links = [(ROLES[3][0], ref("tool", "child_tool", "tool_release", revision)) for revision in (3, 1, 2, 3)]
        consumers = [declaration(name, links=links) for name in ("left", "right")]
        with patch("research_pipeline.store._decode_tool_release_envelope", wraps=decode_envelope) as decoder:
            receipt = self.store.submit_typed(request("shared", [tool(value) for value in consumers]))
        self.assertEqual(decoder.call_count, 5)  # Two local members and three distinct historical releases.
        self.assertEqual(receipt.revisions, (("left", 1), ("right", 1)))
        for consumer in consumers:
            self.assertEqual(self.store.get_revision(consumer.tool_id, 1).record_references,
                             tuple(reference for _, reference in links))
