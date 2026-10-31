"""Consistent bounded metadata capture over real private SQLite stores; engineering evidence only."""

from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactStore
from research_pipeline.domain import ArtifactReference, CreationProvenance, DomainValidationError, RecordReference
from research_pipeline.snapshot import (
    DetachedSnapshot, RootSelector, SnapshotLimits, SnapshotSelection,
    SnapshotIntegrityError, SnapshotLimitError, _canonical,
)
from research_pipeline.store import RecordStore, RecordNotFoundError, StoreClosedError
from research_pipeline.view_plan import plan_readable_snapshot
from tests.snapshot_fixtures import limits, selection, simple_project, populated
from tests.test_store import record, request, graph


class SnapshotTests(unittest.TestCase):
    """Exercise detached consistency, complete navigation and bounded metadata without object reads."""

    def setUp(self):
        """Allocate one private outside-source store and close before directory cleanup."""
        temporary = TemporaryDirectory(prefix="snapshot-tests-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.parent.chmod(0o700)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def corrupt(self, sql, arguments=()):
        """Apply isolated external SQLite damage for reader failure tests, never admission changes."""
        connection = sqlite3.connect(self.root / "metadata.sqlite3")
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("PRAGMA ignore_check_constraints=ON")
            connection.execute(sql, arguments)
            connection.commit()
        finally:
            connection.close()

    def test_selector_limits_validation_and_detachment(self):
        """Reject scalar coercions and duplicate requests while preserving current/exact ordering."""
        for field in fields(SnapshotLimits):
            for invalid in (True, False, 1.0, "1", None, -1, 2**63):
                with self.subTest(field=field.name, invalid=invalid), self.assertRaises(DomainValidationError):
                    limits(**{field.name: invalid})
            if field.name not in ("max_references", "max_artifacts", "max_total_bytes"):
                with self.assertRaises(DomainValidationError):
                    limits(**{field.name: 0})
        for revision in (True, 0, -1, "1", 1.0, 2**63):
            with self.assertRaises(DomainValidationError):
                RootSelector("project", revision)
        for identity in ("../x", "α", "", 1):
            with self.assertRaises(DomainValidationError):
                RootSelector(identity, None)
        with self.assertRaises(DomainValidationError):
            SnapshotSelection(RootSelector("project", None), [RootSelector("project", None)])
        with self.assertRaises(DomainValidationError):
            SnapshotSelection(RootSelector("project", None), None)
        roots = [RootSelector("project", 1)]
        chosen = SnapshotSelection(RootSelector("project", None), roots)
        roots.clear()
        simple_project(self.store)
        snapshot = self.store.capture_snapshot(chosen, limits=limits())
        self.assertEqual(len(snapshot.resolutions), 2)
        self.assertIsNone(snapshot.selection.project.revision)
        self.assertEqual(snapshot.selection.roots[0].revision, 1)

    def test_complete_graph_cycles_repeats_and_historical_references(self):
        """Navigation follows all outgoing links exactly once per revision, retaining duplicate occurrences."""
        artifact = self.store.put_artifact(b"synthetic")
        self.store.submit(request("graph", [record("project", kind="project", record_references=[
            RecordReference("claim", 1, "selected", "claim")]), *graph(artifact)]))
        self.store.submit(request("advance", [record("claim", 2, "claim")], {"claim": 1}))
        chosen = selection("claim")
        snapshot = self.store.capture_snapshot(chosen, limits=limits())
        records = {(r["record_id"], r["revision"]): json.loads(r["envelope_json"]) for r in snapshot.records}
        self.assertIn(("claim", 1), records)
        self.assertIn(("claim", 2), records)
        self.assertNotIn(("task", 1), records)
        self.assertNotIn(("justification", 1), records)
        edges = records[("claim", 1)]["record_references"]
        self.assertEqual(edges[0], edges[1])
        self.assertEqual(len(snapshot.artifacts[0]["occurrences"]), 2)
        self.assertEqual(records[("claim", 1)]["scientific_disposition"], "provisional")
        self.assertEqual(snapshot.resolutions[-1].revision, 2)
        self.assertTrue(snapshot.scope["closure_only"])

    def test_detached_after_close_and_no_artifact_reads(self):
        """Real captured sources remain plannable after close; missing objects are still unverified expectations."""
        chosen, _ = populated(self.store, self.parent)
        with patch.object(ArtifactStore, "verify", side_effect=AssertionError("artifact verification forbidden")), \
             patch.object(ArtifactStore, "read", side_effect=AssertionError("artifact reads forbidden")):
            snapshot = self.store.capture_snapshot(chosen, limits=limits())
        before = snapshot.to_dict()
        snapshot.records[0]["classification"]["category"] = "forged"
        snapshot.scope["not_searched"].clear()
        snapshot.artifacts[0]["occurrences"].clear()
        changed = snapshot.to_dict()
        changed["selection"]["roots"].clear()
        self.assertEqual(snapshot.to_dict(), before)
        self.store.close()
        plan = plan_readable_snapshot(snapshot)
        self.assertEqual(plan.snapshot_id, snapshot.snapshot_id)
        self.assertTrue(all(a["availability"] == "expected_unverified" for a in plan.to_dict()["artifacts"]))
        with self.assertRaises(StoreClosedError):
            self.store.capture_snapshot(chosen, limits=limits())

    def test_missing_physical_artifact_does_not_fail_metadata(self):
        """Deleting a selected object does not make capture or planning read or assert its availability."""
        artifact = self.store.put_artifact(b"absent later")
        self.store.submit(request("project", [record("project", kind="project", artifact_references=[artifact])]))
        # Locate the exact stored digest through the known object layout, not a public read.
        paths = [p for p in (self.root / "objects").rglob("*") if p.is_file()]
        self.assertEqual(len(paths), 1)
        paths[0].unlink()
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        self.assertEqual(snapshot.artifacts[0]["availability"], "expected_unverified")
        self.assertEqual(plan_readable_snapshot(snapshot).artifact_copies[0].digest, artifact.digest)

    def test_schema_watermark_and_content_identity(self):
        """Capture binds normalized schema, highest commit metadata, effective limits and exact raw JSON."""
        simple_project(self.store)
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        document = snapshot.to_dict()
        identity = document.pop("snapshot_id")
        self.assertEqual(identity, hashlib.sha256(_canonical(document).encode("ascii")).hexdigest())
        self.assertEqual(snapshot.schema["version"], 2)
        self.assertEqual(len(snapshot.schema["ddl_sha256"]), 64)
        self.assertEqual(snapshot.watermark["submission_id"], "project-created")
        self.assertEqual(snapshot.watermark["event_id"], 1)
        raw = self.store._connection.execute("SELECT content_json,provenance_json FROM revisions").fetchone()
        self.assertEqual((snapshot.records[0]["content_json"], snapshot.records[0]["provenance_json"]), raw)
        self.assertEqual(snapshot.snapshot_id, self.store.capture_snapshot(selection(), limits=limits()).snapshot_id)
        self.assertNotEqual(snapshot.snapshot_id, self.store.capture_snapshot(selection(), limits=limits(max_roots=33)).snapshot_id)

    def test_missing_roots_and_wrong_project_kind(self):
        """Absent selected roots keep the public not-found error; project selection requires actual kind."""
        with self.assertRaises(RecordNotFoundError):
            self.store.capture_snapshot(selection(), limits=limits())
        self.store.submit(request())
        with self.assertRaises(DomainValidationError):
            self.store.capture_snapshot(SnapshotSelection(RootSelector("context", None), ()), limits=limits())
        simple_project(self.store)
        with self.assertRaises(RecordNotFoundError):
            self.store.capture_snapshot(selection("missing"), limits=limits())
        with self.assertRaises(RecordNotFoundError):
            self.store.capture_snapshot(SnapshotSelection(RootSelector("project", 2), ()), limits=limits())

    def test_dangling_and_cached_wrong_kind_edges(self):
        """Both dangling and repeated cached-target mismatches identify source revision and edge ordinal."""
        self.store.submit(request("edges", [record("project", kind="project", record_references=[
            RecordReference("context", 1, "first"), RecordReference("context", 1, "again")]), record()]))
        self.corrupt("UPDATE record_links SET target_kind='claim' WHERE ordinal=1")
        with self.assertRaisesRegex(SnapshotIntegrityError, "project@1 edge 1"):
            self.store.capture_snapshot(selection(), limits=limits())
        self.corrupt("UPDATE record_links SET target_kind=NULL,target_id='absent' WHERE ordinal=1")
        with self.assertRaisesRegex(SnapshotIntegrityError, "project@1 edge 1"):
            self.store.capture_snapshot(selection(), limits=limits())

    def test_malformed_json_states_and_ordinals(self):
        """Malformed, duplicate-key, nonfinite and noncanonical stored JSON and invalid states fail closed."""
        simple_project(self.store)
        original = self.store._connection.execute("SELECT content_json FROM revisions").fetchone()[0]
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e400}', '{"x":1} ', '{', '[]',
                     '{"x":' + '[' * 65 + '0' + ']' * 65 + '}'):
            self.corrupt("UPDATE revisions SET content_json=?", (text,))
            with self.subTest(text=text[:40]), self.assertRaises(SnapshotIntegrityError):
                self.store.capture_snapshot(selection(), limits=limits())
        self.corrupt("UPDATE revisions SET content_json=?,operational_status='completed'", (original,))
        with self.assertRaises(SnapshotIntegrityError):
            self.store.capture_snapshot(selection(), limits=limits())
        self.corrupt("UPDATE revisions SET operational_status=NULL")
        self.corrupt("INSERT INTO record_links VALUES ('project',1,2,'self','project',1,'project')")
        with self.assertRaisesRegex(SnapshotIntegrityError, "noncontiguous"):
            self.store.capture_snapshot(selection(), limits=limits())

    def test_json_nesting_boundary_and_zero_optional_budgets(self):
        """Stored JSON at depth 64 is retained; one extra level fails before recursive envelope decoding."""
        value = 0
        for _ in range(63):
            value = [value]
        self.store.submit(request("deep", [record("project", kind="project", content={"nested": value})]))
        snapshot = self.store.capture_snapshot(selection(), limits=limits(max_references=0, max_artifacts=0, max_total_bytes=0))
        self.assertEqual(json.loads(snapshot.records[0]["content_json"]), {"nested": value})
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(snapshot)
        self.corrupt("UPDATE revisions SET content_json=?", (_canonical({"nested": [value]}),))
        with patch.object(RecordStore, "_metadata_envelope", side_effect=AssertionError("depth must preflight")), \
             self.assertRaises(SnapshotIntegrityError):
            self.store.capture_snapshot(selection(), limits=limits())

    def test_depth_65_provenance_rejected_before_envelope_decoding(self):
        """Capture preflights excessive stored provenance nesting before invoking the envelope reader."""
        value = 0
        for _ in range(63):
            value = [value]
        # The provenance and details objects bring the complete stored depth to 65.
        provenance = CreationProvenance("author", "2026-10-30T10:00:00Z", {"nested": value})
        artifact = self.store.put_artifact(b"Depth rejection retains stored attachments.\n")
        self.store.submit(request("deep-provenance", [record("project", kind="project", provenance=provenance,
                                                            artifact_references=[artifact])]))
        with patch.object(RecordStore, "_metadata_envelope", side_effect=AssertionError("depth must preflight")) as reader, \
             self.assertRaisesRegex(SnapshotIntegrityError, "JSON nesting exceeds 64"):
            self.store.capture_snapshot(selection(), limits=limits())
        reader.assert_not_called()

    def test_registration_mismatch_and_conflicting_sizes(self):
        """Every direct occurrence must match a registration, even for an already-seen digest."""
        artifact = self.store.put_artifact(b"shared")
        self.store.submit(request("project", [record("project", kind="project", artifact_references=[artifact, artifact])]))
        self.corrupt("UPDATE artifact_links SET size=size+1 WHERE ordinal=1")
        with self.assertRaises(SnapshotIntegrityError):
            self.store.capture_snapshot(selection(), limits=limits())
        self.corrupt("UPDATE artifact_links SET size=?", (artifact.size,))
        self.corrupt("DELETE FROM artifacts")
        with self.assertRaises(SnapshotIntegrityError):
            self.store.capture_snapshot(selection(), limits=limits())

    def test_classifications_do_not_upgrade_shallow_targets(self):
        """Opaque project, unknown formats/versions and supported-but-malformed payloads are retained honestly."""
        records = [record("project", kind="project", record_references=[RecordReference(name, 1, "shallow")
                   for name in ("generic", "unknown", "version", "malformed")]),
                   record("generic", kind="run", content={"success": True}),
                   record("unknown", content={"format": "other", "version": 1}),
                   record("version", content={"format": "research_pipeline.scientific_content", "version": 2}),
                   record("malformed", content={"format": "research_pipeline.scientific_content", "version": 1})]
        self.store.submit(request("opaque", records))
        with patch.object(RecordStore, "_check_typed_targets", side_effect=AssertionError("not admission")):
            snapshot = self.store.capture_snapshot(selection(), limits=limits())
        categories = {r["record_id"]: r["classification"]["category"] for r in snapshot.records}
        self.assertEqual(categories, {"project": "generic", "generic": "generic", "unknown": "unsupported",
                                      "version": "unsupported", "malformed": "malformed_typed"})
        home = next(f.data.decode() for f in plan_readable_snapshot(snapshot).generated_files if f.relative_path == "README.md")
        self.assertIn("Typed remaining requirements unavailable", home)

    def test_count_and_expected_byte_boundaries(self):
        """Roots, records, repeated references, distinct digests and unique expected bytes count exactly."""
        artifact = self.store.put_artifact(b"12345")
        self.store.submit(request("bounds", [record("project", kind="project", record_references=[
            RecordReference("context", 1, "edge"), RecordReference("context", 1, "edge")], artifact_references=[artifact, artifact]), record()]))
        chosen = selection("context")
        good = limits(max_roots=2, max_records=2, max_references=4, max_artifacts=1, max_file_bytes=5, max_total_bytes=5)
        self.assertEqual(len(self.store.capture_snapshot(chosen, limits=good).records), 2)
        for name, value in (("max_roots", 1), ("max_records", 1), ("max_references", 3), ("max_artifacts", 0),
                            ("max_file_bytes", 4), ("max_total_bytes", 4)):
            with self.subTest(name=name), self.assertRaises(SnapshotLimitError):
                self.store.capture_snapshot(chosen, limits=replace(good, **{name: value}))
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=limits(max_references=0))

    def test_record_byte_boundary_and_preflight_before_decoding(self):
        """Oversized JSON and link fields fail before envelope decoding; exact retained record boundary passes."""
        simple_project(self.store)
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        size = len(_canonical(snapshot.records[0]))
        self.store.capture_snapshot(selection(), limits=limits(max_record_bytes=size))
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=limits(max_record_bytes=size - 1))
        self.corrupt("UPDATE revisions SET content_json=?", ('{"huge":"' + 'x' * 10000 + '"}',))
        with patch.object(RecordStore, "_metadata_envelope", side_effect=AssertionError("must preflight")), \
             self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=limits(max_record_bytes=1000))
        self.corrupt("UPDATE revisions SET content_json='{}'")
        self.corrupt("INSERT INTO record_links VALUES ('project',1,0,?,'project',1,NULL)", ('x' * 10000,))
        with patch.object(RecordStore, "_metadata_envelope", side_effect=AssertionError("must preflight")), \
             self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=limits(max_record_bytes=1000))

    def test_metadata_boundary_includes_complete_serialization(self):
        """Cumulative fetched metadata plus detached serialization, including own ID and limits, is bounded."""
        simple_project(self.store)
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        needed = len(_canonical(snapshot.to_dict())) + snapshot.to_dict()["metadata_fetched_bytes"]
        # The budget's decimal spelling is itself retained; converge to its exact size.
        for _ in range(8):
            document = snapshot.to_dict()
            document["limits"]["max_metadata_bytes"] = needed
            candidate = len(_canonical(document)) + document["metadata_fetched_bytes"]
            if candidate == needed:
                break
            needed = candidate
        exact = self.store.capture_snapshot(selection(), limits=limits(max_metadata_bytes=needed))
        self.assertEqual(len(_canonical(exact.to_dict())) + exact.to_dict()["metadata_fetched_bytes"], needed)
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=limits(max_metadata_bytes=needed - 1))

    def test_forged_values_rejected_at_public_boundaries(self):
        """Bypassing frozen assignment cannot silently alter effective inputs or private detached state."""
        simple_project(self.store)
        bad = limits()
        object.__setattr__(bad, "max_records", True)
        with self.assertRaises(DomainValidationError):
            self.store.capture_snapshot(selection(), limits=bad)
        chosen = selection()
        object.__setattr__(chosen.project, "record_id", "../escape")
        with self.assertRaises(DomainValidationError):
            self.store.capture_snapshot(chosen, limits=limits())
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        document = snapshot.to_dict()
        document["records"][0]["classification"]["category"] = "locally_decoded"
        with self.assertRaises(SnapshotIntegrityError):
            DetachedSnapshot(document)
        object.__setattr__(snapshot, "_serialized", _canonical(document))
        with self.assertRaises(SnapshotIntegrityError):
            plan_readable_snapshot(snapshot)

    def test_single_transaction_and_no_submission_or_public_reads(self):
        """Trace exactly one read transaction and forbid whole-request recovery or public per-record transactions."""
        simple_project(self.store)
        statements = []
        self.store._connection.set_trace_callback(statements.append)
        try:
            with patch.object(RecordStore, "head", side_effect=AssertionError("public head read")), \
                 patch.object(RecordStore, "get_revision", side_effect=AssertionError("public revision read")), \
                 patch.object(RecordStore, "history", side_effect=AssertionError("history enumeration")), \
                 patch.object(RecordStore, "audit_events", side_effect=AssertionError("audit enumeration")):
                snapshot = self.store.capture_snapshot(selection(), limits=limits())
        finally:
            self.store._connection.set_trace_callback(None)
        self.assertEqual(statements.count("BEGIN"), 1)
        self.assertEqual(statements.count("COMMIT"), 1)
        self.assertIn("audit_events", next(s for s in statements if s.startswith("SELECT")))
        self.assertFalse(any("request_json" in s or "GROUP_CONCAT" in s.upper() for s in statements))
        self.assertEqual(snapshot.resolutions[0].revision, 1)

    def test_rehashed_scalar_substitutions_are_inconsistent(self):
        """A fresh hash cannot legitimize bool/int/float substitutions in redundant exact JSON."""
        simple_project(self.store)
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        for field in ("content_json", "provenance_json", "envelope_json"):
            for replacement in (True, 1, 1.0):
                document = snapshot.to_dict()
                entry = document["records"][0]
                value = json.loads(entry[field])
                if field == "provenance_json":
                    old = value["details"]["source"][1]["run"]
                    value["details"]["source"][1]["run"] = replacement
                else:
                    content = value["content"] if field == "envelope_json" else value
                    old = content["graph"]["weight"]
                    content["graph"]["weight"] = replacement
                if type(old) is type(replacement):
                    continue
                entry[field] = _canonical(value)
                document.pop("snapshot_id")
                document["snapshot_id"] = hashlib.sha256(_canonical(document).encode("ascii")).hexdigest()
                with self.subTest(field=field, replacement=replacement), self.assertRaisesRegex(
                        SnapshotIntegrityError, "inconsistent exact JSON"):
                    DetachedSnapshot(document)

    def test_redundant_revision_requires_an_ordinary_integer(self):
        """Record keys cannot use bool, float or coercion even when equal to the envelope's revision."""
        simple_project(self.store)
        snapshot = self.store.capture_snapshot(selection(), limits=limits())
        for revision in (True, 1.0, "1", None, 0, -1):
            document = snapshot.to_dict()
            document["records"][0]["revision"] = revision
            document.pop("snapshot_id")
            document["snapshot_id"] = hashlib.sha256(_canonical(document).encode("ascii")).hexdigest()
            with self.subTest(revision=revision), self.assertRaises(SnapshotIntegrityError):
                DetachedSnapshot(document)

    def test_capture_and_planning_preserve_application_tables_and_objects(self):
        """Successful and budget-failing reads leave every canonical row and object byte/mode intact."""
        artifact = self.store.put_artifact(b"private synthetic graph")
        self.store.submit(request("graph", [record("project", kind="project", record_references=[
            RecordReference("claim", 1, "selected", "claim")]), *graph(artifact)]))
        chosen = selection()

        def canonical_state():
            """Inspect fixed application tables and independently read object bytes for comparison."""
            tables = ("identities", "revisions", "record_links", "artifact_links", "artifacts",
                      "submissions", "audit_events", "migration_history")
            rows = {name: self.store._connection.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall()
                    for name in tables}
            objects = {path.relative_to(self.root).as_posix(): (path.read_bytes(), path.stat().st_mode)
                       for path in (self.root / "objects").iterdir()}
            return rows, objects

        before = canonical_state()
        snapshot = self.store.capture_snapshot(chosen, limits=limits())
        plan_readable_snapshot(snapshot)
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(chosen, limits=limits(max_records=1))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(self.store.capture_snapshot(chosen, limits=limits(max_files=1)))
        self.assertEqual(canonical_state(), before)

    def test_plan_reserves_parent_indexes_before_accumulating_mappings(self):
        """Small file limits stop lazy attachment enumeration before rendering or collecting all copies."""
        import research_pipeline.view_plan as planner

        artifact = self.store.put_artifact(b"shared")
        self.store.submit(request("attachments", [record("project", kind="project",
            artifact_references=[artifact] * 100)]))
        snapshot = self.store.capture_snapshot(selection(), limits=limits(max_files=9))
        enumerate_items = planner._mapping_items
        visited = []

        def observe(*arguments):
            """Count actually enumerated mapping declarations without altering their values."""
            for item in enumerate_items(*arguments):
                visited.append(item)
                yield item

        with patch.object(planner, "_mapping_items", side_effect=observe), \
             patch.object(planner._Output, "add", side_effect=AssertionError("must reserve before rendering")), \
             self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(snapshot)
        self.assertEqual(len(visited), 2)

    def test_long_closure_and_repeated_edges_are_bounded_iteratively(self):
        """A long cyclic chain with duplicate edges terminates without losing occurrences or bypassing counts."""
        count = 90
        nodes = []
        for index in range(count):
            target = "n" + str((index + 1) % count)
            edge = RecordReference(target, 1, "navigation", "decision")
            nodes.append(record("n" + str(index), kind="decision", record_references=[edge, edge]))
        project = record("project", kind="project", record_references=[RecordReference("n0", 1, "root")])
        self.store.submit(request("long-chain", [project, *nodes]))
        chosen = limits(max_records=count + 1, max_references=2 * count + 1)
        snapshot = self.store.capture_snapshot(selection(), limits=chosen)
        self.assertEqual(len(snapshot.records), count + 1)
        self.assertEqual(sum(len(json.loads(r["envelope_json"])["record_references"]) for r in snapshot.records), 2 * count + 1)
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=replace(chosen, max_references=2 * count))
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection(), limits=replace(chosen, max_records=count))

    def concurrent_capture(self, boundary):
        """Coordinate actual independent writer COMMIT boundary with a paused established read snapshot."""
        simple_project(self.store)
        self.store.submit(request("context-created", [record()]))
        paused, commit_reached, capture_finished = threading.Event(), threading.Event(), threading.Event()
        failures, result = [], []
        before = self.store.capture_snapshot(selection("context"), limits=limits())

        def seam(point):
            """Hold the reader after a snapshot SELECT until writer reaches its actual COMMIT statement."""
            if point == boundary:
                paused.set()
                if not commit_reached.wait(10):
                    raise AssertionError("writer did not reach COMMIT")

        def trace(statement):
            """Observe a real COMMIT; preserve DELETE-journal locking by waiting for capture completion."""
            if statement == "COMMIT":
                commit_reached.set()
                if not capture_finished.wait(10):
                    failures.append(AssertionError("capture did not finish"))

        def writer():
            """Append both heads on an independently opened thread-confined connection."""
            try:
                if not paused.wait(10):
                    raise AssertionError("reader did not establish snapshot")
                with RecordStore.open(self.root) as handle:
                    handle._connection.set_trace_callback(trace)
                    handle.submit(request("advance", [record("project", 2, "project"), record("context", 2)],
                                          {"project": 1, "context": 1}))
            except BaseException as error:
                failures.append(error)
                commit_reached.set()

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            with patch("research_pipeline.store._fault", side_effect=seam):
                result.append(self.store.capture_snapshot(selection("context"), limits=limits()))
        finally:
            capture_finished.set()
            thread.join(15)
        self.assertFalse(thread.is_alive(), "writer did not terminate")
        if failures:
            raise failures[0]
        self.assertTrue(commit_reached.is_set())
        self.assertEqual(result[0].resolutions, before.resolutions)
        self.assertEqual(result[0].watermark, before.watermark)
        self.assertEqual(result[0].snapshot_id, before.snapshot_id)
        after = self.store.capture_snapshot(selection("context"), limits=limits())
        self.assertEqual([pin.revision for pin in after.resolutions], [2, 2])
        self.assertEqual(after.watermark["submission_id"], "advance")

    def test_concurrent_commit_after_initial_snapshot_read(self):
        """A writer cannot mix heads with the watermark established by the first SELECT."""
        self.concurrent_capture("snapshot_after_first_read")

    def test_concurrent_commit_after_first_head_resolution(self):
        """A writer advancing two roots between resolutions still yields one consistent old generation."""
        self.concurrent_capture("snapshot_after_head_resolution")
