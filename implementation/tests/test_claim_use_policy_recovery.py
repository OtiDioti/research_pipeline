"""Policy transaction rollback, original receipts, activation and exact durable restoration."""

from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline import claim_use_store
from research_pipeline.backup import create_backup, restore_backup, inspect_backup, BackupError
from research_pipeline.claim_use import encode_envelope as use_envelope
from research_pipeline.domain import DomainValidationError, RecordEnvelope
from research_pipeline.store import RecordStore, StoreLayoutError, RevisionConflictError, SubmissionConflictError
from tests.claim_use_fixtures import populate, binding, batch, ref, PROVENANCE, LIMITS
from tests.test_claim_use_store import metadata
from tests.test_claim_use_policy import policy_record, exact


class PolicyRecoveryTests(unittest.TestCase):
    """Own disposable stores and independent thread-confined handles for every test."""

    def setUp(self):
        """Allocate private paths without fixed names or mutable shared graph state."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=5)
        self.addCleanup(self.store.close)
        self.artifact, self.initial, self.receipt = populate(self.store)

    def view(self, identity="use"):
        """Return a detached public current view under maximum finite limits."""
        return self.store.inspect_claim_use(identity, limits=LIMITS).to_dict()

    def child(self, code, *args, expected=0):
        """Run bounded fresh-process candidate code and retain diagnostic output on failure."""
        result = subprocess.run([sys.executable, "-B", "-c", code, *map(str, args)], cwd=self.parent,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]/"src"),
                 "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def test_fault_seams_cas_acknowledgment_loss_and_damaged_attachment_retry(self):
        """All precommit tables roll back; lost acknowledgment retries never execute policy twice."""
        request = batch("advance", [policy_record()])
        before = metadata(self.root)
        for boundary in ("before_metadata", "after_first_revision", "after_claim_use_updates"):
            def fail(point):
                """Interrupt only the selected real owning transaction seam."""
                if point == boundary:
                    raise RuntimeError(boundary)
            with self.subTest(boundary=boundary), patch("research_pipeline.store._fault", fail):
                with self.assertRaisesRegex(RuntimeError, boundary):
                    self.store.submit(request)
            self.assertEqual(metadata(self.root), before)
        with self.assertRaises(RevisionConflictError):
            self.store.submit(batch("stale", request.records, {"policy": 0}))
        self.assertEqual(metadata(self.root), before)
        def lost(point):
            """Lose acknowledgment after the transaction has actually committed."""
            if point == "after_commit":
                raise RuntimeError("lost acknowledgment")
        with patch("research_pipeline.store._fault", lost), self.assertRaisesRegex(RuntimeError, "lost"):
            self.store.submit(request)
        original = self.store.get_submission("advance")
        self.assertEqual(self.view()["generation"], 2)
        self.store.submit(batch("later", [policy_record(revision=3)]))
        self.store.submit_typed(batch("rebind", [use_envelope("use", 2, binding(), PROVENANCE)]))
        path = self.root/"objects"/self.artifact.digest
        path.unlink()
        self.assertEqual(self.view()["attachment_availability"], "not_checked_metadata_only")
        before_retry = metadata(self.root)
        with patch.object(RecordStore, "_check_batch", side_effect=AssertionError("retry admitted")), \
             patch.object(claim_use_store, "prepare", side_effect=AssertionError("retry replanned")):
            self.assertEqual(self.store.submit(request), original)
            self.assertEqual(self.store.submit_typed(self.initial), self.receipt)
        self.assertEqual(metadata(self.root), before_retry)
        with self.assertRaises(SubmissionConflictError):
            self.store.submit(batch("advance", [policy_record(text="Conflicting request")]))
        self.assertEqual(metadata(self.root), before_retry)

    def test_readers_see_old_then_new_complete_policy_generation(self):
        """A writer paused before commit cannot expose its new policy with an old generation."""
        updated, observed, committed = threading.Event(), threading.Event(), threading.Event()
        results, failures = [], []
        def read():
            """Keep a separate reader confined to this thread and synchronize without sleeps."""
            try:
                self.assertTrue(updated.wait(10))
                with RecordStore.open(self.root) as store:
                    results.append(store.inspect_claim_use("use", limits=LIMITS).to_dict())
                    observed.set()
                    self.assertTrue(committed.wait(10))
                    results.append(store.inspect_claim_use("use", limits=LIMITS).to_dict())
            except BaseException as error:
                failures.append(error)
                observed.set()
        def barrier(point):
            """Allow an independent old snapshot while every new SQL row is uncommitted."""
            if point == "after_claim_use_updates":
                updated.set()
                self.assertTrue(observed.wait(10))
        thread = threading.Thread(target=read)
        thread.start()
        try:
            with patch("research_pipeline.store._fault", barrier):
                self.store.submit(batch("advance", [policy_record()]))
        finally:
            updated.set()
            committed.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual([(v["generation"], v["observed_policies"][0]["observed_policy"]["revision"]) for v in results], [(1, 1), (2, 2)])

    def test_paused_inspection_stays_coherent_during_writer_progress(self):
        """A snapshot opened before writer progress resolves policy heads from that same snapshot."""
        ready, begin, paused, resume, done = (threading.Event() for _ in range(5))
        results, failures = [], []
        def read():
            """Open before fault patching so chronological open validation cannot enter the barrier."""
            try:
                with RecordStore.open(self.root) as store:
                    ready.set()
                    self.assertTrue(begin.wait(10))
                    results.append(store.inspect_claim_use("use", limits=LIMITS).to_dict())
            except BaseException as error:
                failures.append(error)
            finally:
                done.set()
        def barrier(point):
            """Pause the reader after binding traversal, then release it before writer commit."""
            if point == "claim_use_inspection_after_binding" and threading.current_thread() is thread:
                paused.set()
                self.assertTrue(resume.wait(10))
            if point == "after_claim_use_updates":
                resume.set()
                self.assertTrue(done.wait(10))
        thread = threading.Thread(target=read)
        thread.start()
        try:
            self.assertTrue(ready.wait(10))
            with patch("research_pipeline.store._fault", barrier):
                begin.set()
                self.assertTrue(paused.wait(10))
                self.store.submit(batch("advance", [policy_record()]))
        finally:
            begin.set()
            resume.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results[0]["generation"], 1)
        self.assertEqual(results[0]["observed_policies"][0]["observed_policy"], exact("policy"))
        self.assertEqual(self.view()["generation"], 2)

    def test_reopen_process_backup_exact_restore_and_continued_retry(self):
        """Healthy format 5 retains metadata bytes, both origins, receipts and future writes."""
        request = batch("advance", [policy_record()])
        receipt = self.store.submit(request)
        expected = self.view()
        backup = self.parent/"backup"
        info = create_backup(self.store, backup)
        self.assertEqual((info.format_version, info.schema_version), (5, 5))
        self.assertEqual(inspect_backup(backup), info)
        with RecordStore.open(self.root) as store:
            self.assertEqual(store.inspect_claim_use("use", limits=LIMITS).to_dict(), expected)
        code = '''
import json,sys
from research_pipeline.store import RecordStore
from research_pipeline.claim_use import ClaimUseInspectionLimits
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps(store.inspect_claim_use("use",limits=ClaimUseInspectionLimits(512,1024,8192,1024,67108864,4194304)).to_dict(),sort_keys=True))
'''
        self.assertEqual(json.loads(self.child(code, self.root)), expected)
        restored = self.parent/"restore"
        with restore_backup(backup, restored) as store:
            self.assertEqual((restored/"metadata.sqlite3").read_bytes(), (backup/"snapshot.sqlite3").read_bytes())
            self.assertEqual(store.submit(request), receipt)
            self.assertEqual(store.inspect_claim_use("use", limits=LIMITS).to_dict(), expected)
            store.submit(batch("next", [policy_record(revision=3)]))
            self.assertEqual(store.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"], 3)

    def test_schema4_policy_history_migration_preserves_all_rows_and_old_request(self):
        """Migration exposes a prefeature P@2 mismatch but creates only a later P@2→P@3 cause."""
        oldroot = self.parent/"old"
        with RecordStore.create(oldroot, schema_version=4) as old:
            populate(old)
            # A pre-feature Decision exceeds the newly introduced record bound.
            # Exact original reconciliation must still precede new policy gates.
            request = batch("old-policy", [policy_record(text="x"*(1024*1024+1))])
            receipt = old.submit(request)
            view = old.inspect_claim_use("use", limits=LIMITS).to_dict()
            self.assertEqual((view["version"], view["generation"]), (1, 1))
            self.assertNotIn("observed_policies", view)
            create_backup(old, self.parent/"oversized")
        # Activation cannot support its required policy metadata; reject before publication.
        with self.assertRaisesRegex(BackupError, "record_bytes"):
            restore_backup(self.parent/"oversized", self.parent/"rejected", target_schema=5, migration_provenance=PROVENANCE)
        self.assertTrue((self.parent/"rejected/.restore-incomplete").exists())
        # A large unrelated old Decision request can migrate and must remain retryable.
        healthy = self.parent/"healthy-old"
        with RecordStore.create(healthy, schema_version=4) as old:
            old_artifact, _, _ = populate(old)
            old_receipt = old.submit(batch("p2", [policy_record()]))
            unrelated = batch("old-large-unrelated", [RecordEnvelope("opaque", 1, "decision",
                {"declaration": "x"*(1024*1024+1)}, PROVENANCE, artifact_references=[old_artifact])])
            unrelated_receipt = old.submit(unrelated)
            before = metadata(healthy)
            create_backup(old, self.parent/"old-backup")
        with restore_backup(self.parent/"old-backup", self.parent/"migrated", target_schema=5, migration_provenance=PROVENANCE) as store:
            after = metadata(self.parent/"migrated")
            self.assertEqual({k: v for k, v in after.items() if k not in ("migration_history", "claim_use_policy_origin")},
                             {k: v for k, v in before.items() if k != "migration_history"})
            view = store.inspect_claim_use("use", limits=LIMITS).to_dict()
            self.assertEqual(view["generation"], 1)
            self.assertTrue(view["observed_policies"][0]["superseded"])
            self.assertEqual(view["policy_freshness"]["activation_event_watermark"], unrelated_receipt.event_id)
            self.assertEqual(store.submit(unrelated), unrelated_receipt)
            self.assertEqual(store.submit(batch("p2", [policy_record()])), old_receipt)
            store.submit(batch("p3", [policy_record(revision=3)]))
            transition = store.claim_use_history("use", limits=LIMITS).to_dict()["transitions"][-1]
            self.assertEqual(transition["generation"], 2)
            cause = transition["causes"][0]
            self.assertEqual((cause["bound_policy"], cause["previous_policy"], cause["new_policy"]),
                             (exact("policy"), exact("policy", 2), exact("policy", 3)))
            create_backup(store, self.parent/"migrated-backup")
            (self.parent/"migrated/objects"/old_artifact.digest).unlink()
            self.assertEqual(store.submit(unrelated), unrelated_receipt)
        with RecordStore.open(self.parent/"migrated"):
            pass

    def test_near_ceiling_legacy_registration_keeps_original_replay_accounts(self):
        """A large schema-4 admission remains replayable under exact legacy preparation after activation."""
        oldroot = self.parent/"large-old"
        with RecordStore.create(oldroot, schema_version=4) as old:
            populate(old)
            value = replace(binding("premise-a", (), (), ()), limitations=["z"*1030000])
            request = batch("large-old-register", [use_envelope("large-old-use", 1, value, PROVENANCE)])
            receipt = old.submit_typed(request)
            create_backup(old, self.parent/"large-old-backup")
        with restore_backup(self.parent/"large-old-backup", self.parent/"large-migrated", target_schema=5,
                migration_provenance=PROVENANCE) as store:
            self.assertEqual(store.submit_typed(request), receipt)
            self.assertEqual(store.inspect_claim_use("large-old-use", limits=LIMITS).to_dict()["generation"], 1)
            create_backup(store, self.parent/"large-migrated-backup")
        with RecordStore.open(self.parent/"large-migrated"):
            pass

    def test_actual_migration_interruptions_retain_marker_and_sources(self):
        """Transform, committed-unpublished and publication crashes retain unusable destinations."""
        with RecordStore.create(self.parent/"old", schema_version=4) as old:
            populate(old)
            create_backup(old, self.parent/"backup")
        source = (self.parent/"backup/snapshot.sqlite3").read_bytes()
        for boundary in ("migration_transform", "migration_committed", "before_publication"):
            destination = self.parent/boundary
            code = '''
import os,sys
from research_pipeline import backup
from research_pipeline.domain import CreationProvenance
def crash(point):
    """Exit at the selected actual restore barrier without cleanup or publication."""
    if point == sys.argv[3]: os._exit(73)
backup._fault=crash
backup.restore_backup(sys.argv[1],sys.argv[2],target_schema=5,
    migration_provenance=CreationProvenance("synthetic","2026-11-05T00:00:00Z"))
'''
            self.child(code, self.parent/"backup", destination, boundary, expected=73)
            self.assertTrue((destination/".restore-incomplete").exists())
            with self.assertRaises(StoreLayoutError):
                RecordStore.open(destination)
        self.assertEqual((self.parent/"backup/snapshot.sqlite3").read_bytes(), source)

    def test_auxiliary_schema5_capabilities_and_authenticated_policy_successor(self):
        """Resources, reports, control/source and authenticated policy writes retain their contracts."""
        from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
        from tests import resource_fixtures as resources, report_fixtures as reports, operating_fixtures as operating
        from research_pipeline import operating_authority as authority
        from research_pipeline.snapshot import _schema_identity
        from research_pipeline.resources import ResourceSnapshot
        with RecordStore.create(self.parent/"capabilities", schema_version=5) as store:
            request, control = sources.populate(store)
            source = sources.commit(store)
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
            self.assertEqual(sources.commit(store).to_dict(limits=sources.LIMITS), source.to_dict(limits=sources.LIMITS))
            snapshot = store.inspect_resources(limits=resources.LIMITS).to_dict()
            self.assertEqual(snapshot["schema_version"], 5)
            self.assertEqual(snapshot["schema_identity"], _schema_identity(5))
            self.assertEqual(ResourceSnapshot(snapshot).to_dict(), snapshot)
            create_backup(store, self.parent/"capabilities-backup")
        with restore_backup(self.parent/"capabilities-backup", self.parent/"restored") as store:
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
        with RecordStore.create(self.parent/"reports", schema_version=5) as store:
            reports.populate(store)
            result = store.commit_report(reports.report_request())
            self.assertEqual(store.get_report_operation("report_initial"), result)
            self.assertEqual(store.read_report("report_initial").to_dict()["scientific"]["schema"]["version"], 5)
        operating.empty(self.store)
        scope = operating.scope()
        bound = operating.prepare(self.store, scope)
        signed = operating.sign(operating.decision(bound, scope))
        self.store.commit_operating_decision(signed, policy=operating.policy(), evaluated_at=operating.TIME, limits=operating.LIMITS)
        envelope = authority.encode_envelope(signed)
        leaf = replace(binding("unrelated", (), (), ()), policies=[ref(envelope.record_id, "authorization_policy", "decision")])
        self.store.submit_typed(batch("operating-policy-use", [use_envelope("operating-use", 1, leaf, PROVENANCE)]))
        reduced = operating.sign(operating.decision(bound, revision=2, previous=envelope, outcome="revoke", operation="reduce"))
        with self.assertRaisesRegex(DomainValidationError, "commit_operating_decision"):
            self.store.submit_typed(authority.submission(reduced))
        receipt = self.store.commit_operating_decision(reduced, policy=operating.policy(), evaluated_at=operating.TIME, limits=operating.LIMITS)
        view = self.view("operating-use")
        self.assertEqual(view["generation"], 2)
        self.assertEqual(view["observed_policies"][0]["observed_policy"], exact(envelope.record_id, 2))
        self.assertFalse(view["eligible"])
        self.assertEqual(self.store.commit_operating_decision(reduced, policy=None, evaluated_at=None, limits=operating.LIMITS), receipt)

    def test_migration_chain_continues_through_five(self):
        """The existing explicit 1→2→3→4 sequence can continue without rewriting original rows."""
        from tests.legacy import historical_store, table_values
        original, requests, artifact = historical_store(self.parent/"legacy")
        with original:
            rows = table_values(self.parent/"legacy")
            receipts = [original.get_submission(r.submission_id) for r in requests]
            create_backup(original, self.parent/"backup-1")
        for version in (2, 3, 4, 5):
            with restore_backup(self.parent/f"backup-{version-1}", self.parent/f"store-{version}",
                    target_schema=version, migration_provenance=PROVENANCE) as store:
                self.assertEqual(table_values(self.parent/f"store-{version}"), rows)
                self.assertEqual([store.submit(r) for r in requests], receipts)
                create_backup(store, self.parent/f"backup-{version}")
        with sqlite3.connect(self.parent/"store-5/metadata.sqlite3") as connection:
            self.assertEqual(list(connection.execute("SELECT migration_id,source_schema,target_schema FROM migration_history")),
                             [(1,1,2), (2,2,3), (3,3,4), (4,4,5)])


if __name__ == "__main__":
    unittest.main()
