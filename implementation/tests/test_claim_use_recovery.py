"""Deterministic concurrent snapshots, process loss, migration and schema-4 capability tests."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline.store import RecordStore, StoreLayoutError
from research_pipeline.backup import create_backup, restore_backup, inspect_backup, BackupError
from research_pipeline.claim_use import ClaimUsePremise, ClaimUseRoute, encode_envelope as use_envelope
from research_pipeline.scientific import encode_envelope
from tests.claim_use_fixtures import (
    populate, review, issue, binding, ref, batch, LIMITS, PROVENANCE, assessment_envelope,
)
from tests.test_claim_use_store import metadata


class ClaimUseRecoveryTests(unittest.TestCase):
    """Independent handles and bounded fresh processes observe actual SQLite barriers."""

    def setUp(self):
        """Create isolated outside-source stores; cleanup does not mutate shared fixtures."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=4)
        self.addCleanup(self.store.close)
        self.artifact, self.initial, self.receipt = populate(self.store)

    def child(self, code, *args, expected=0):
        """Run candidate-local product code with a timeout and intact failure diagnostics."""
        result = subprocess.run([sys.executable, "-B", "-c", code, *map(str, args)], cwd=self.parent,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]/"src"),
                 "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def test_concurrent_readers_observe_complete_old_or_new_state(self):
        """Review updates expose old or new assertions and both complete generations."""
        self.assert_concurrent_snapshots(batch("concurrent", [assessment_envelope("review-a", 2,
            replace(review(), reviewer="New assertion"), PROVENANCE)]), "review-a", [1, 2])

    def test_concurrent_direct_issue_updates_both_generations_with_its_observation(self):
        """Direct Issue impact shares the same pre-COMMIT snapshot barrier as Review impact."""
        self.assert_concurrent_snapshots(batch("concurrent-direct", [assessment_envelope("direct-issue", 1,
            issue("use", "promotion_eligibility"), PROVENANCE)]), "direct-issue", [None, 1])

    def assert_concurrent_snapshots(self, request, assertion_id, revisions):
        """Hold one writer before COMMIT; independent handles see complete old/new use views.

        Assert both current generations and the selected assertion revision for the
        root and its downstream binding. Events synchronize readers without sleeps.
        """
        mutated, observed, committed = threading.Event(), threading.Event(), threading.Event()
        failures, results = [], []
        def reader():
            """Keep the independent reader handle confined to its own thread."""
            try:
                self.assertTrue(mutated.wait(10))
                with RecordStore.open(self.root) as store:
                    results.append([store.inspect_claim_use(identity, limits=LIMITS).to_dict()
                                    for identity in ("use", "downstream-use")])
                    observed.set()
                    self.assertTrue(committed.wait(10))
                    results.append([store.inspect_claim_use(identity, limits=LIMITS).to_dict()
                                    for identity in ("use", "downstream-use")])
            except BaseException as error:
                failures.append(error)
                observed.set()
        def barrier(point):
            """Hold the writer while an old committed snapshot is read through the public API."""
            if point == "after_claim_use_updates":
                mutated.set()
                self.assertTrue(observed.wait(10))
        thread = threading.Thread(target=reader)
        thread.start()
        try:
            with patch("research_pipeline.store._fault", barrier):
                self.store.submit_typed(request)
        finally:
            committed.set()
            mutated.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual([[r["generation"] for r in snapshot] for snapshot in results], [[1, 1], [2, 2]])
        for snapshot, revision in zip(results, revisions):
            for view in snapshot:
                self.assertEqual(next((x["pin"]["revision"] for x in view["observed_assertions"]
                                       if x["pin"]["record_id"] == assertion_id), None), revision)

    def test_direct_issue_rollback_lost_ack_reopen_and_exact_restore(self):
        """Direct/downstream effects roll back together and survive committed retry and recovery."""
        request = batch("direct-recovery", [assessment_envelope("direct-issue", 1,
                        issue("use", "promotion_eligibility"), PROVENANCE)])
        for boundary in ("before_metadata", "after_first_revision", "after_claim_use_updates"):
            before = metadata(self.root)

            def fail(point):
                """Raise at the selected existing barrier before SQLite COMMIT."""
                if point == boundary:
                    raise RuntimeError(point)

            with self.subTest(boundary=boundary), patch("research_pipeline.store._fault", fail), \
                    self.assertRaisesRegex(RuntimeError, boundary):
                self.store.submit_typed(request)
            self.assertEqual(metadata(self.root), before)

        def lost(point):
            """Simulate acknowledgment loss after the sole metadata transaction commits."""
            if point == "after_commit":
                raise RuntimeError("lost direct acknowledgment")

        with patch("research_pipeline.store._fault", lost), self.assertRaisesRegex(RuntimeError, "lost direct"):
            self.store.submit_typed(request)
        receipt = self.store.get_submission(request.submission_id)
        self.assertIsNotNone(receipt)
        views = {identity: self.store.inspect_claim_use(identity, limits=LIMITS)
                 for identity in ("use", "downstream-use", "unrelated-use")}
        histories = {identity: self.store.claim_use_history(identity, limits=LIMITS) for identity in views}
        self.assertEqual([view.to_dict()["generation"] for view in views.values()], [2, 2, 1])
        for identity in ("use", "downstream-use"):
            view = views[identity].to_dict()
            self.assertEqual(view["mechanical_freshness"]["last_transition"]["event_id"], receipt.event_id)
            self.assertIn("direct-issue", {a["pin"]["record_id"] for a in view["observed_assertions"]})
            self.assertIn("binding_affected" if identity == "use" else "upstream_affected",
                          {c["type"] for c in view["mechanical_freshness"]["reasons"]})
        committed = metadata(self.root)
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.submit(request), receipt)
            for identity in views:
                self.assertEqual(reopened.inspect_claim_use(identity, limits=LIMITS), views[identity])
                self.assertEqual(reopened.claim_use_history(identity, limits=LIMITS), histories[identity])
        self.assertEqual(metadata(self.root), committed)
        backup = self.parent/"direct-backup"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        restored_root = self.parent/"direct-restored"
        with restore_backup(backup, restored_root) as restored:
            self.assertEqual((restored_root/"metadata.sqlite3").read_bytes(), (backup/"snapshot.sqlite3").read_bytes())
            self.assertEqual(restored.submit_typed(request), receipt)
            self.assertEqual(metadata(restored_root), committed)
            for identity in views:
                self.assertEqual(restored.inspect_claim_use(identity, limits=LIMITS), views[identity])
                self.assertEqual(restored.claim_use_history(identity, limits=LIMITS), histories[identity])

    def test_missing_direct_transition_rejected_even_when_downstream_history_remains(self):
        """Chronological open and rehashed-backup checks reject a locally consistent stale root."""
        self.store.submit_typed(batch("direct-corruption", [assessment_envelope("direct-issue", 1,
                               issue("use", "promotion_eligibility"), PROVENANCE)]))
        create_backup(self.store, self.parent/"direct-backup")
        damaged = self.parent/"direct-damaged"
        shutil.copytree(self.root, damaged)
        targets = (damaged/"metadata.sqlite3", self.parent/"direct-backup/snapshot.sqlite3")
        for target in targets:
            target.chmod(0o600)
            with sqlite3.connect(target) as connection:
                connection.execute("DELETE FROM claim_use_generations WHERE use_id='use' AND generation=2")
                connection.execute("""UPDATE claim_use_current SET generation=1,
                    last_event=(SELECT event_id FROM claim_use_generations WHERE use_id='use' AND generation=1)
                    WHERE use_id='use'""")
                self.assertEqual(connection.execute("SELECT generation FROM claim_use_current WHERE use_id='use'").fetchone(), (1,))
                self.assertEqual(connection.execute("SELECT generation FROM claim_use_current WHERE use_id='downstream-use'").fetchone(), (2,))
        with self.assertRaisesRegex(StoreLayoutError, "missing or extra generation transition"):
            RecordStore.open(damaged)
        snapshot = targets[1]
        snapshot.chmod(0o400)
        manifest = self.parent/"direct-backup/manifest.json"
        doc = json.loads(manifest.read_text())
        data = snapshot.read_bytes()
        doc["metadata"] = dict(digest=hashlib.sha256(data).hexdigest(), size=len(data))
        manifest.chmod(0o600)
        manifest.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")))
        manifest.chmod(0o400)
        with self.assertRaisesRegex(BackupError, "missing or extra generation transition"):
            inspect_backup(self.parent/"direct-backup")

    def test_real_process_exit_recovery_and_fresh_process_inspection(self):
        """Real exits before/after freshness and COMMIT preserve atomicity and original receipts."""
        for boundary in ("after_first_revision", "after_claim_use_updates", "after_commit"):
            with self.subTest(boundary=boundary):
                revision = self.store.head("review-a")+1
                value = replace(review(), assessment=replace(review().assessment, rationale="x"*200000))
                request = batch("crash-"+boundary, [assessment_envelope("review-a", revision, value, PROVENANCE)])
                saved = self.parent/(boundary+".json")
                saved.write_text(json.dumps(request.to_dict()))
                before = metadata(self.root)
                self.child('''
import json, os, sys
from research_pipeline.domain import Submission
import research_pipeline.store as module
store = module.RecordStore.open(sys.argv[1])
store._connection.execute("PRAGMA cache_size=1")
def crash(point):
    """Exit at the selected actual barrier without Python cleanup."""
    if point == sys.argv[3]:
        os._exit(73)
module._fault = crash
store.submit_typed(Submission.from_dict(json.loads(open(sys.argv[2]).read())))
raise AssertionError("barrier not reached")
''', self.root, saved, boundary, expected=73)
                with RecordStore.open(self.root) as reopened:
                    committed = boundary == "after_commit"
                    receipt = reopened.get_submission(request.submission_id)
                    self.assertEqual(receipt is not None, committed)
                    if not committed:
                        self.assertEqual(metadata(self.root), before)
                    result = reopened.submit_typed(request)
                    if committed:
                        self.assertEqual(receipt, result)
                    generation = reopened.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"]
                    self.assertEqual(reopened.submit(request), result)
                    self.assertEqual(reopened.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"], generation)
                self.child('''
import sys
from research_pipeline.store import RecordStore
from research_pipeline.claim_use import ClaimUseInspectionLimits
with RecordStore.open(sys.argv[1]) as store:
    limits=ClaimUseInspectionLimits(512,1024,8192,1024,64*1024*1024,4*1024*1024)
    view=store.inspect_claim_use("use",limits=limits).to_dict()
    assert view["generation"] == int(sys.argv[2]) and view["eligible"] is False
''', self.root, generation)

    def test_near_ceiling_binding_survives_reopen_backup_and_exact_restore(self):
        """Completed admission is not charged again for stored-envelope/transition verification.

        A real 1,030,000-character limitation stays complete through maximum-limit
        inspection, independent and fresh-process open, verified backup and restore.
        A same-length stored mutation must still fail its independent comparison.
        """
        limitation = "z" * 1030000
        value = replace(binding("premise-a", (), (), ()), limitations=[limitation])
        request = batch("large-register", [use_envelope("large-use", 1, value, PROVENANCE)])
        receipt = self.store.submit_typed(request)
        view = self.store.inspect_claim_use("large-use", limits=LIMITS)
        history = self.store.claim_use_history("large-use", limits=LIMITS)
        self.assertIn(limitation, view.to_dict()["limitations"])
        self.assertEqual(view.to_dict()["binding"]["content"]["limitations"], [limitation])
        self.assertEqual(view.to_dict()["generation"], 1)
        self.assertEqual(view.to_dict()["binding_revision"], 1)
        self.assertEqual(view.to_dict()["mechanical_freshness"]["last_transition"],
                         history.to_dict()["transitions"][0])
        self.assertEqual(self.store.submit_typed(request), receipt)
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.inspect_claim_use("large-use", limits=LIMITS), view)
            self.assertEqual(reopened.claim_use_history("large-use", limits=LIMITS), history)
            self.assertEqual(reopened.get_submission(request.submission_id), receipt)
        expected = self.parent/"large-expected.json"
        expected.write_text(json.dumps(dict(view=view.to_dict(), history=history.to_dict(), receipt=receipt.to_dict())))
        self.child('''
import json, sys
from research_pipeline.store import RecordStore
from research_pipeline.claim_use import ClaimUseInspectionLimits
with open(sys.argv[2]) as stream:
    expected = json.load(stream)
with RecordStore.open(sys.argv[1]) as store:
    limits = ClaimUseInspectionLimits(512,1024,8192,1024,64*1024*1024,4*1024*1024)
    assert store.inspect_claim_use("large-use", limits=limits).to_dict() == expected["view"]
    assert store.claim_use_history("large-use", limits=limits).to_dict() == expected["history"]
    assert store.get_submission("large-register").to_dict() == expected["receipt"]
''', self.root, expected)
        backup = self.parent/"large-backup"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        restored_root = self.parent/"large-restored"
        with restore_backup(backup, restored_root) as restored:
            self.assertEqual((restored_root/"metadata.sqlite3").read_bytes(), (backup/"snapshot.sqlite3").read_bytes())
            self.assertEqual(metadata(restored_root), metadata(self.root))
            self.assertEqual(restored.inspect_claim_use("large-use", limits=LIMITS), view)
            self.assertEqual(restored.claim_use_history("large-use", limits=LIMITS), history)
            self.assertEqual(restored.get_submission(request.submission_id), receipt)
        with sqlite3.connect(restored_root/"metadata.sqlite3") as connection:
            text = connection.execute("SELECT content_json FROM revisions WHERE record_id='large-use'").fetchone()[0]
            changed = text.replace("z"*32, "y"+"z"*31, 1)
            self.assertNotEqual(changed, text)
            self.assertEqual(len(changed.encode()), len(text.encode()))
            connection.execute("UPDATE revisions SET content_json=? WHERE record_id='large-use'", (changed,))
        with self.assertRaisesRegex(StoreLayoutError, "stored revision differs"):
            RecordStore.open(restored_root)

    def test_non_freshness_submission_indexes_original_occurrences_atomically(self):
        """The unconditional shared insertion seam covers generic records, retries and rollback."""
        from research_pipeline.domain import RecordEnvelope
        from research_pipeline import claim_use_store as freshness
        references = [ref("generic-target", "affected_record", "decision"),
                      ref("generic-target", "affected_record", "decision"),
                      ref("route-a", "assessed_route", "justification"),
                      ref("candidate", "descriptive", "claim")]
        record = RecordEnvelope("generic-links", 1, "decision", {}, PROVENANCE, record_references=references)
        request = batch("generic-navigation", [record, RecordEnvelope("generic-target", 1, "decision", {}, PROVENANCE)])
        before = metadata(self.root)

        def fail(point):
            """Reject after temporal insertion at the existing final transaction fault seam."""
            if point == "after_claim_use_updates":
                raise RuntimeError("navigation rollback")

        with patch("research_pipeline.store._fault", fail), self.assertRaisesRegex(RuntimeError, "navigation rollback"):
            self.store.submit(request)
        self.assertEqual(metadata(self.root), before)
        with self.store._transaction() as connection:
            self.assertIsNone(freshness.prepare(self.store, connection, request))
        receipt = self.store.submit(request)
        after = metadata(self.root)
        self.assertIn(("generic-links", 1, receipt.event_id), after["claim_use_revision_events"])
        for table in ("claim_use_bindings", "claim_use_generations", "claim_use_current"):
            self.assertEqual(after[table], before[table])
        actual = [row for row in after["claim_use_association_links"] if row[0] == "generic-links"]
        self.assertEqual(actual, [("generic-links", 1, ordinal, receipt.event_id, r.relationship, r.record_id, r.revision)
                                  for ordinal, r in enumerate(references[:3])])
        self.assertEqual(self.store.submit(request), receipt)
        self.assertEqual(metadata(self.root), after)
        # Wrong-kind source links still consume candidate examination work before
        # the observation layer rejects their source kind.
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection)
            deps = [(0, "generic-target", 1, "decision", "policy_declared", "", 0, -1, -1)]
            reader.caps["index_rows"] = 2
            self.assertEqual(freshness.observed(reader, deps, binding_keys=()), [])
            self.assertEqual(reader.counts["index_rows"], 2)
            reader = freshness.Reader(self.store, connection)
            reader.caps["index_rows"] = 1
            with self.assertRaisesRegex(freshness.ClaimUseLimitError, "index_rows"):
                freshness.observed(reader, deps, binding_keys=())
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.get_submission(request.submission_id), receipt)

    def test_support_cycles_and_repeated_candidates_are_not_descriptive_support(self):
        """Acyclic binding identities still cannot return to an ancestor's exact candidate."""
        from research_pipeline.store import ReferenceResolutionError
        route = self.store.get_typed_revision("route-a", 1)[1]
        circular = replace(route, premises=[ref("downstream", "premise", "claim")])
        self.store.submit_typed(batch("cycle-descriptions", [encode_envelope("return-route", 1, circular, PROVENANCE),
            assessment_envelope("return-review", 1, review(route="return-route"), PROVENANCE)]))
        first = binding(routes=("return-route",), assessments=("return-review",), premises=("downstream",), upstream="cycle-b")
        second = binding("downstream", ("route-d",), ("review-d",), ("candidate",), "cycle-a")
        request = batch("cycle", [use_envelope("cycle-a", 1, first, PROVENANCE),
                                  use_envelope("cycle-b", 1, second, PROVENANCE)])
        before = metadata(self.root)
        with self.assertRaises(ReferenceResolutionError):
            self.store.submit_typed(request)
        self.assertEqual(metadata(self.root), before)
        # Even without a binding back-edge, the last unrecorded candidate premise
        # returns to the root's exact candidate, so the ancestry is undischarged.
        second = binding("downstream", ("route-d",), ("review-d",), ("candidate",))
        with self.assertRaisesRegex(ReferenceResolutionError, "undischarged"):
            self.store.submit_typed(batch("repeated", [use_envelope("cycle-a", 1, first, PROVENANCE),
                use_envelope("cycle-b", 1, second, PROVENANCE)]))
        self.assertEqual(metadata(self.root), before)

    def test_migration_process_interruptions_keep_unusable_marked_copies(self):
        """3→4 transform, commit and publication exits never expose an incomplete runtime."""
        source = self.parent/"schema3"
        with RecordStore.create(source, schema_version=3) as old:
            create_backup(old, self.parent/"old-backup")
        original = (self.parent/"old-backup/snapshot.sqlite3").read_bytes()
        for boundary in ("migration_transform", "migration_committed", "before_publication"):
            destination = self.parent/boundary
            self.child('''
import os,sys
from research_pipeline import backup
from research_pipeline.domain import CreationProvenance
def crash(point):
    """Exit at the real migration barrier retaining the durable marker."""
    if point == sys.argv[3]: os._exit(73)
backup._fault=crash
backup.restore_backup(sys.argv[1],sys.argv[2],target_schema=4,
    migration_provenance=CreationProvenance("synthetic","2026-11-05T00:00:00Z"))
''', self.parent/"old-backup", destination, boundary, expected=73)
            self.assertTrue((destination/".restore-incomplete").exists())
            with self.assertRaises(StoreLayoutError):
                RecordStore.open(destination)
        self.assertEqual((self.parent/"old-backup/snapshot.sqlite3").read_bytes(), original)

    def test_rehashed_backup_rejects_corrupt_and_extra_freshness(self):
        """Rehashed immutable snapshots still reject temporal and chronological projection corruption."""
        self.store.submit_typed(batch("revision", [assessment_envelope("review-a", 2, review(), PROVENANCE)]))
        create_backup(self.store, self.parent/"backup")
        for i, sql in enumerate(("DELETE FROM claim_use_generations WHERE use_id='use' AND generation=2",
                "UPDATE claim_use_dependencies SET role='forged' WHERE use_id='use' AND ordinal=0",
                "INSERT INTO claim_use_generations VALUES ('unrelated-use',2,1,'revision',4,'requires_reassessment','[]')",
                "DELETE FROM claim_use_revision_events WHERE record_id='candidate'",
                "UPDATE claim_use_revision_events SET event_id=1 WHERE record_id='candidate'",
                "INSERT INTO claim_use_revision_events VALUES ('invented',1,1)",
                "DELETE FROM claim_use_association_links WHERE record_id='review-a' AND ordinal=0",
                "UPDATE claim_use_association_links SET target_id='premise-a' WHERE record_id='review-a' AND ordinal=0",
                "UPDATE claim_use_association_links SET event_id=1 WHERE record_id='review-a'",
                "INSERT INTO claim_use_association_links VALUES ('candidate',1,99,2,'affected_record','candidate',1)",
                "UPDATE claim_use_dependencies SET registration_event=1 WHERE use_id='use'",
                "UPDATE claim_use_upstreams SET registration_event=1 WHERE use_id='downstream-use'")):
            target = self.parent/f"bad-{i}"
            shutil.copytree(self.parent/"backup", target)
            snapshot = target/"snapshot.sqlite3"
            snapshot.chmod(0o600)
            with sqlite3.connect(snapshot) as connection:
                connection.execute(sql)
            snapshot.chmod(0o400)
            manifest = target/"manifest.json"
            doc = json.loads(manifest.read_text())
            data = snapshot.read_bytes()
            doc["metadata"] = dict(digest=hashlib.sha256(data).hexdigest(), size=len(data))
            manifest.chmod(0o600)
            manifest.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")))
            manifest.chmod(0o400)
            with self.subTest(sql=sql), self.assertRaises(BackupError):
                inspect_backup(target)

    def test_previously_migrated_source_keeps_original_sql_and_receipts(self):
        """Explicit 1→2→3→4 copies retain nonconsecutive source events and administrative text."""
        from tests.legacy import historical_store, table_values
        original, requests, artifact = historical_store(self.parent/"legacy")
        with original:
            receipts = [original.get_submission(r.submission_id) for r in requests]
            rows = table_values(self.parent/"legacy")
            create_backup(original, self.parent/"backup-v1")
        for version in (2, 3, 4):
            destination = self.parent/f"migrated-v{version}"
            with restore_backup(self.parent/f"backup-v{version-1}", destination,
                                target_schema=version, migration_provenance=PROVENANCE) as store:
                self.assertEqual(table_values(destination), rows)
                for request, receipt in zip(requests, receipts):
                    self.assertEqual(store.submit(request), receipt)
                create_backup(store, self.parent/f"backup-v{version}")
            if version == 4:
                with sqlite3.connect(destination/"metadata.sqlite3") as connection:
                    transitions = list(connection.execute("SELECT migration_id,source_schema,target_schema FROM migration_history ORDER BY migration_id"))
                    origin = connection.execute("SELECT event_watermark FROM claim_use_origin").fetchone()[0]
                self.assertEqual(transitions, [(1, 1, 2), (2, 2, 3), (3, 3, 4)])
                self.assertEqual(origin, max(r.event_id for r in receipts))

    def test_schema4_resources_reports_operating_controls_and_lifecycle_sources(self):
        """The actual schema-4 identity preserves schema-3 auxiliary capabilities and wire history."""
        from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
        from tests import resource_fixtures as resources, report_fixtures as reports
        from research_pipeline.snapshot import _schema_identity
        from research_pipeline.resources import ResourceSnapshot
        # Existing setup-only fixtures exercise operating decisions and control
        # preparation through their real dedicated insertion callers.
        root = self.parent/"capabilities"
        with RecordStore.create(root, schema_version=4) as store:
            request, control = sources.populate(store)
            source = sources.commit(store)
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
            self.assertEqual(sources.commit(store).to_dict(limits=sources.LIMITS), source.to_dict(limits=sources.LIMITS))
            snapshot = store.inspect_resources(limits=resources.LIMITS).to_dict()
            self.assertEqual(snapshot["schema_version"], 4)
            self.assertEqual(snapshot["schema_identity"], _schema_identity(4))
            self.assertEqual(ResourceSnapshot(snapshot).to_dict(), snapshot)
            create_backup(store, self.parent/"capabilities-backup")
        with RecordStore.create(self.parent/"reports", schema_version=4) as store:
            reports.populate(store)
            result = store.commit_report(reports.report_request())
            self.assertEqual(store.get_report_operation("report_initial"), result)
            self.assertEqual(store.read_report("report_initial").to_dict()["scientific"]["schema"]["version"], 4)
        with restore_backup(self.parent/"capabilities-backup", self.parent/"capabilities-restored") as store:
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)

    def test_historical_generic_claim_use_reconciles_before_schema_gate_and_after_migration(self):
        """Schema-3 generic history backfills navigation while preserving receipts and non-registration."""
        from research_pipeline.domain import DomainValidationError, RecordEnvelope
        from research_pipeline.store import SubmissionConflictError, RecordNotFoundError, ReferenceResolutionError
        from tests.legacy import seed_request, canonical, legacy_request
        from tests.test_tool_assessment_persistence_bounds import Hostile

        root = self.parent/"historical"
        with RecordStore.create(root, schema_version=3) as old:
            artifact = populate(old, uses=False)
            use = use_envelope("legacy-use", 1, binding(), PROVENANCE)
            evidence = encode_envelope("historical-evidence", 1, old.get_typed_revision("evidence", 1)[1], PROVENANCE)
            original = batch("historical-original", [use, evidence])
            # This models genuinely pre-feature generic rows, with an independent
            # canonical representation and explicit event, without disabling guards.
            with sqlite3.connect(root/"metadata.sqlite3") as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                seed_request(connection, original, 41)
            receipt = old.get_submission(original.submission_id)
            self.assertEqual(receipt.event_id, 41)
            text = old._connection.execute("SELECT request_json FROM submissions WHERE submission_id=?",
                                           (original.submission_id,)).fetchone()[0]
            self.assertEqual(text, canonical(legacy_request(original)))

            def retry_checks(store, path, unsupported):
                """Verify metadata-only retries/conflicts and local rejection, without target admission."""
                before = metadata(path)
                with patch.object(RecordStore, "_check_batch", side_effect=AssertionError("target admission reached")), \
                        patch("research_pipeline.claim_use_store.prepare", side_effect=AssertionError("fresh admission reached")):
                    self.assertEqual(store.submit(original), receipt)
                    self.assertEqual(store.submit_typed(original), receipt)
                    changed = batch(original.submission_id, [use_envelope("legacy-use", 1,
                                    replace(binding(), limitations=["different request"]), PROVENANCE), evidence])
                    for operation in (store.submit, store.submit_typed):
                        with self.assertRaises(SubmissionConflictError):
                            operation(changed)
                forged = batch(original.submission_id, [use, evidence])
                object.__setattr__(forged.records[0], "kind", Hostile())
                for operation in (store.submit, store.submit_typed):
                    with self.assertRaises(DomainValidationError):
                        operation(forged)
                if unsupported:
                    fresh = batch("fresh-on-old", [use_envelope("fresh-use", 1, binding(), PROVENANCE)])
                    for operation in (store.submit, store.submit_typed, store._check_prepared_typed):
                        with self.assertRaisesRegex(StoreLayoutError, "schema 4"):
                            operation(fresh)
                with self.assertRaises(SubmissionConflictError):
                    store._check_prepared_typed(original)
                self.assertEqual(metadata(path), before)

            retry_checks(old, root, True)
            # A later generic head does not change what the historical request acknowledged.
            old.submit(batch("later-generic", [RecordEnvelope("legacy-use", 2, "promotion_eligibility", {}, PROVENANCE),
                RecordEnvelope("old-unsupported-review", 1, "review", {}, PROVENANCE,
                               record_references=[ref("candidate", "candidate_claim", "claim")])]))
            retry_checks(old, root, True)
            create_backup(old, self.parent/"historical-backup")
            source = metadata(root)
            damage = root/"objects"/artifact.digest
            damage.chmod(0o600)
            damage.write_bytes(b"permitted retry damage")
            retry_checks(old, root, True)
        migrated_root = self.parent/"historical-migrated"
        with restore_backup(self.parent/"historical-backup", migrated_root, target_schema=4,
                            migration_provenance=PROVENANCE) as migrated:
            after = metadata(migrated_root)
            for name in ("submissions", "audit_events", "revisions", "identities", "record_links", "artifact_links"):
                self.assertEqual(after[name], source[name])
            self.assertEqual(after["claim_use_origin"], [(1, 42)])
            self.assertEqual(after["claim_use_bindings"], [])
            self.assertEqual(after["claim_use_generations"], [])
            with migrated._transaction() as connection:
                expected_revisions = list(connection.execute("""SELECT r.record_id,r.revision,a.event_id
                    FROM revisions r JOIN audit_events a USING(submission_id) ORDER BY r.record_id,r.revision"""))
                expected_links = list(connection.execute("""SELECT l.record_id,l.revision,l.ordinal,a.event_id,
                    l.relationship,l.target_id,l.target_revision FROM record_links l
                    JOIN revisions r USING(record_id,revision) JOIN audit_events a USING(submission_id)
                    WHERE l.relationship IN ('candidate_claim','assessed_route','affected_record')
                    ORDER BY l.record_id,l.revision,l.ordinal"""))
                self.assertEqual(list(connection.execute("SELECT * FROM claim_use_revision_events ORDER BY record_id,revision")), expected_revisions)
                self.assertEqual(list(connection.execute("SELECT * FROM claim_use_association_links ORDER BY record_id,revision,ordinal")), expected_links)
            self.assertEqual(migrated.get_revision("old-unsupported-review", 1).content, {})
            retry_checks(migrated, migrated_root, False)
            for operation in (migrated.inspect_claim_use, migrated.claim_use_history):
                with self.assertRaisesRegex(RecordNotFoundError, "unregistered"):
                    operation("legacy-use", limits=LIMITS)
            before = metadata(migrated_root)
            with self.assertRaisesRegex(ReferenceResolutionError, "new identity"):
                migrated.submit_typed(batch("convert-historical", [use_envelope("legacy-use", 3, binding(), PROVENANCE)]))
            self.assertEqual(metadata(migrated_root), before)
            damaged = migrated_root/"objects"/artifact.digest
            damaged.chmod(0o600)
            damaged.write_bytes(b"permitted retry damage")
            retry_checks(migrated, migrated_root, False)
        with RecordStore.open(migrated_root) as reopened:
            self.assertEqual(reopened.submit(original), receipt)
            self.assertEqual(reopened.submit_typed(original), receipt)
