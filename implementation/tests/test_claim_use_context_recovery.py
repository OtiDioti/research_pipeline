"""Context transaction rollback, original receipts, activation and exact durable restoration."""

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
from tests.claim_use_fixtures import populate, binding, batch, ref, review, assessment_envelope, PROVENANCE, LIMITS
from tests.test_claim_use_store import metadata
from tests.test_claim_use_context import context_record, exact


def successor(revision=2, text="Prose-only successor"):
    """Advance the setup graph's explicitly bound scope with coherent context metadata."""
    return context_record("scope", revision, question=text)


class ContextRecoveryTests(unittest.TestCase):
    """Own disposable stores and independent thread-confined handles for every test."""

    def setUp(self):
        """Allocate private paths without fixed names or mutable shared graph state."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=6)
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
        """All precommit tables roll back; lost acknowledgment retries never execute context twice."""
        request = batch("advance", [successor()])
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
            self.store.submit(batch("stale", request.records, {"scope": 0}))
        self.assertEqual(metadata(self.root), before)
        def lost(point):
            """Lose acknowledgment after the transaction has actually committed."""
            if point == "after_commit":
                raise RuntimeError("lost acknowledgment")
        with patch("research_pipeline.store._fault", lost), self.assertRaisesRegex(RuntimeError, "lost"):
            self.store.submit(request)
        original = self.store.get_submission("advance")
        self.assertEqual(self.view()["generation"], 2)
        self.store.submit(batch("later", [successor(revision=3)]))
        self.store.submit_typed(batch("rebind", [use_envelope("use", 2, binding(), PROVENANCE)]))
        self.store.submit_typed(batch("later-assessment", [assessment_envelope("review-a", 2,
            replace(review(), reviewer="Later attributed reviewer"), PROVENANCE)]))
        path = self.root/"objects"/self.artifact.digest
        path.unlink()
        with patch.object(self.store._artifacts, "verify", side_effect=AssertionError("historical attachment read")):
            self.store.submit(batch("context-after-artifact-damage", [successor(revision=4)]))
        self.assertEqual(self.view()["attachment_availability"], "not_checked_metadata_only")
        from research_pipeline.artifacts import ArtifactError
        with self.assertRaises(ArtifactError):
            self.store.get_typed_revision("evidence", 1)
        before_retry = metadata(self.root)
        with patch.object(RecordStore, "_check_batch", side_effect=AssertionError("retry admitted")), \
             patch.object(claim_use_store, "prepare", side_effect=AssertionError("retry replanned")):
            self.assertEqual(self.store.submit(request), original)
            self.assertEqual(self.store.submit_typed(self.initial), self.receipt)
        self.assertEqual(metadata(self.root), before_retry)
        with self.assertRaises(SubmissionConflictError):
            self.store.submit(batch("advance", [successor(text="Conflicting request")]))
        self.assertEqual(metadata(self.root), before_retry)

    def test_readers_see_old_then_new_complete_context_generation(self):
        """A writer paused before commit cannot expose its new context with an old generation."""
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
                self.store.submit(batch("advance", [successor()]))
        finally:
            updated.set()
            committed.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual([(v["generation"], v["observed_target_contexts"][0]["observed_context"]["revision"]) for v in results], [(1, 1), (2, 2)])

    def test_paused_inspection_stays_coherent_during_writer_progress(self):
        """A snapshot opened before writer progress resolves context heads from that same snapshot."""
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
                self.store.submit(batch("advance", [successor()]))
        finally:
            begin.set()
            resume.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results[0]["generation"], 1)
        self.assertEqual(results[0]["observed_target_contexts"][0]["observed_context"], exact("scope"))
        self.assertEqual(self.view()["generation"], 2)

    def test_reopen_process_backup_exact_restore_and_continued_retry(self):
        """Healthy format 6 retains metadata bytes, all three origins, receipts and future writes."""
        request = batch("advance", [successor()])
        receipt = self.store.submit(request)
        expected = self.view()
        backup = self.parent/"backup"
        info = create_backup(self.store, backup)
        self.assertEqual((info.format_version, info.schema_version), (6, 6))
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
            store.submit(batch("next", [successor(revision=3)]))
            self.assertEqual(store.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"], 3)

    def test_schema5_context_history_migration_preserves_all_rows_and_old_request(self):
        """Migration exposes a prefeature context mismatch but records only the next successor as a transition."""
        oldroot = self.parent/"old"
        with RecordStore.create(oldroot, schema_version=5) as old:
            populate(old)
            # A pre-feature context exceeds the newly introduced record bound.
            # Exact original reconciliation must still precede new context gates.
            request = batch("old-context", [successor(text="x"*(1024*1024+1))])
            receipt = old.submit(request)
            view = old.inspect_claim_use("use", limits=LIMITS).to_dict()
            self.assertEqual((view["version"], view["generation"]), (2, 1))
            self.assertNotIn("observed_target_contexts", view)
            create_backup(old, self.parent/"oversized")
        # Activation cannot support its required context metadata; reject before publication.
        with self.assertRaisesRegex(BackupError, "record_bytes"):
            restore_backup(self.parent/"oversized", self.parent/"rejected", target_schema=6, migration_provenance=PROVENANCE)
        self.assertTrue((self.parent/"rejected/.restore-incomplete").exists())
        # A large unrelated old context request can migrate and must remain retryable.
        healthy = self.parent/"healthy-old"
        with RecordStore.create(healthy, schema_version=5) as old:
            old_artifact, _, _ = populate(old)
            old_receipt = old.submit(batch("p2", [successor()]))
            unrelated = batch("old-large-unrelated", [RecordEnvelope("opaque", 1, "research_context",
                {"declaration": "x"*(1024*1024+1)}, PROVENANCE, artifact_references=[old_artifact])])
            unrelated_receipt = old.submit(unrelated)
            before = metadata(healthy)
            create_backup(old, self.parent/"old-backup")
        with restore_backup(self.parent/"old-backup", self.parent/"migrated", target_schema=6, migration_provenance=PROVENANCE) as store:
            after = metadata(self.parent/"migrated")
            self.assertEqual({k: v for k, v in after.items() if k not in ("migration_history", "claim_use_context_origin")},
                             {k: v for k, v in before.items() if k != "migration_history"})
            view = store.inspect_claim_use("use", limits=LIMITS).to_dict()
            self.assertEqual(view["generation"], 1)
            self.assertTrue(view["observed_target_contexts"][0]["superseded"])
            self.assertEqual(view["target_context_freshness"]["activation_event_watermark"], unrelated_receipt.event_id)
            self.assertEqual(store.submit(unrelated), unrelated_receipt)
            self.assertEqual(store.submit(batch("p2", [successor()])), old_receipt)
            store.submit(batch("p3", [successor(revision=3)]))
            transition = store.claim_use_history("use", limits=LIMITS).to_dict()["transitions"][-1]
            self.assertEqual(transition["generation"], 2)
            cause = transition["causes"][0]
            self.assertEqual((cause["bound_context"], cause["previous_context"], cause["new_context"]),
                             (exact("scope"), exact("scope", 2), exact("scope", 3)))
            create_backup(store, self.parent/"migrated-backup")
            (self.parent/"migrated/objects"/old_artifact.digest).unlink()
            self.assertEqual(store.submit(unrelated), unrelated_receipt)
        with RecordStore.open(self.parent/"migrated"):
            pass

    def test_near_ceiling_legacy_registration_keeps_original_replay_accounts(self):
        """Near-ceiling registrations on both sides of activation retain their independent replay accounts."""
        oldroot = self.parent/"large-old"
        with RecordStore.create(oldroot, schema_version=5) as old:
            populate(old)
            value = replace(binding("premise-a", (), (), ()), limitations=["z"*1030000])
            request = batch("large-old-register", [use_envelope("large-old-use", 1, value, PROVENANCE)])
            receipt = old.submit_typed(request)
            create_backup(old, self.parent/"large-old-backup")
        with restore_backup(self.parent/"large-old-backup", self.parent/"large-migrated", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            self.assertEqual(store.submit_typed(request), receipt)
            self.assertEqual(store.inspect_claim_use("large-old-use", limits=LIMITS).to_dict()["generation"], 1)
            current = batch("large-current-register", [use_envelope("large-current-use", 1,
                            replace(value, candidate_claim=ref("premise-b", "candidate_claim", "claim")), PROVENANCE)])
            current_receipt = store.submit_typed(current)
            self.assertEqual(store.submit_typed(current), current_receipt)
            create_backup(store, self.parent/"large-migrated-backup")
        with RecordStore.open(self.parent/"large-migrated"):
            pass

    def test_actual_migration_interruptions_retain_marker_and_sources(self):
        """Transform, committed-unpublished and publication crashes retain unusable destinations."""
        with RecordStore.create(self.parent/"old", schema_version=5) as old:
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
backup.restore_backup(sys.argv[1],sys.argv[2],target_schema=6,
    migration_provenance=CreationProvenance("synthetic","2026-11-05T00:00:00Z"))
'''
            self.child(code, self.parent/"backup", destination, boundary, expected=73)
            self.assertTrue((destination/".restore-incomplete").exists())
            with self.assertRaises(StoreLayoutError):
                RecordStore.open(destination)
        self.assertEqual((self.parent/"backup/snapshot.sqlite3").read_bytes(), source)

    def test_actual_submission_interruptions_reopen_complete_old_or_new_state(self):
        """Process death at real write seams preserves records, heads, receipts and generations together."""
        request = batch("process-context", [successor()])
        saved = self.parent/"request.json"
        saved.write_text(json.dumps(request.to_dict()))
        code = """
import json,os,sys
from research_pipeline import store as module
from research_pipeline.domain import Submission
def crash(point):
    '''Exit at a real owning transaction seam without unwinding Python state.'''
    if point == sys.argv[3]: os._exit(74)
module._fault=crash
with module.RecordStore.open(sys.argv[1]) as store:
    store.submit(Submission.from_dict(json.loads(open(sys.argv[2]).read())))
"""
        for boundary in ("before_metadata", "after_first_revision", "after_claim_use_updates", "after_commit"):
            before = metadata(self.root)
            self.child(code, self.root, saved, boundary, expected=74)
            with RecordStore.open(self.root) as reopened:
                if boundary == "after_commit":
                    original = reopened.get_submission(request.submission_id)
                    self.assertIsNotNone(original)
                    self.assertEqual(reopened.submit(request), original)
                    self.assertEqual(reopened.head("scope"), 2)
                    self.assertEqual(reopened.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"], 2)
                else:
                    self.assertEqual(metadata(self.root), before)
                    self.assertIsNone(reopened.get_submission(request.submission_id))
                    self.assertEqual(reopened.head("scope"), 1)

    def test_empty_activation_and_invalid_options_do_not_reserve_destinations(self):
        """An empty source activates at zero, while malformed/skipped/backward options reserve nothing."""
        from research_pipeline.backup import BackupLayoutError
        with RecordStore.create(self.parent/"empty-old", schema_version=5) as old:
            create_backup(old, self.parent/"empty-backup")
        with restore_backup(self.parent/"empty-backup", self.parent/"empty-migrated", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            for table in ("claim_use_origin", "claim_use_policy_origin", "claim_use_context_origin"):
                self.assertEqual(list(store._connection.execute(f"SELECT * FROM {table}")), [(1, 0)])
        for index, (version, provenance) in enumerate(((True, PROVENANCE), (6.0, PROVENANCE),
                (4, PROVENANCE), (5, PROVENANCE), (7, PROVENANCE), (6, None), (None, PROVENANCE))):
            destination = self.parent/f"invalid-{index}"
            with self.subTest(version=version), self.assertRaises(BackupLayoutError):
                restore_backup(self.parent/"empty-backup", destination,
                               target_schema=version, migration_provenance=provenance)
            self.assertFalse(destination.exists())

    def test_policy_activation_stays_context_disabled_after_six_migration(self):
        """Independent policy activation never reinterprets later context scope in its boundary view."""
        with RecordStore.create(self.parent/"four", schema_version=4) as old:
            populate(old)
            create_backup(old, self.parent/"four-backup")
        with restore_backup(self.parent/"four-backup", self.parent/"five", target_schema=5,
                migration_provenance=PROVENANCE) as old:
            old.submit(batch("prefeature-context", [successor()]))
            create_backup(old, self.parent/"five-backup")
        with restore_backup(self.parent/"five-backup", self.parent/"six", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            store.submit(batch("first-later-context", [successor(revision=3)]))
            store.submit_typed(batch("later-binding", [use_envelope("later", 1, binding("unrelated", (), (), ()), PROVENANCE)]))
            captured = []
            original = claim_use_store._inspection
            def capture(reader, identity, limits):
                '''Retain real independent boundary views, without replacing validation or admission.'''
                result = original(reader, identity, limits)
                if reader.overlay is None and reader.cutoff is not None:
                    captured.append((reader.context_active, reader.cutoff, result.to_dict()))
                return result
            with patch.object(claim_use_store, "_inspection", capture), RecordStore.open(self.parent/"six"):
                pass
            policy = [v for active, cutoff, v in captured if not active]
            context = [v for active, cutoff, v in captured if active]
            self.assertEqual(len(policy), 3)
            self.assertEqual(len(context), 3)
            self.assertTrue(all(v["version"] == 2 and "observed_target_contexts" not in v for v in policy))
            self.assertTrue(all(v["version"] == 3 and all(o["observed_context"]["revision"] == 2
                for o in v["observed_target_contexts"]) for v in context))
            self.assertTrue(all(v["generation"] == 1 for v in policy+context))

    def test_activation_at_signed_maximum_never_adds_one(self):
        """A maximum-ID boundary without later events validates yet rejects further scientific writes."""
        oldroot = self.parent/"maximum-old"
        with RecordStore.create(oldroot, schema_version=5) as old:
            populate(old)
            request = batch("ceiling", [RecordEnvelope("ceiling", 1, "event", {}, PROVENANCE)])
            old.submit(request)
            connection = old._connection
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("UPDATE audit_events SET event_id=? WHERE submission_id='ceiling'", (2**63-1,))
            connection.execute("UPDATE claim_use_revision_events SET event_id=? WHERE record_id='ceiling'", (2**63-1,))
            connection.execute("PRAGMA foreign_keys=ON")
            original = old.get_submission("ceiling")
            create_backup(old, self.parent/"maximum-backup")
        with restore_backup(self.parent/"maximum-backup", self.parent/"maximum-six", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            self.assertEqual(store.inspect_claim_use("use", limits=LIMITS).to_dict()["target_context_freshness"],
                             dict(available=True, activation_event_watermark=2**63-1))
            self.assertEqual(store.submit(request), original)
            before = metadata(self.parent/"maximum-six")
            from research_pipeline.claim_use import ClaimUseLimitError
            with self.assertRaisesRegex(ClaimUseLimitError, "event_id"):
                store.submit(batch("overflow", [RecordEnvelope("never", 1, "event", {}, PROVENANCE)]))
            self.assertEqual(metadata(self.parent/"maximum-six"), before)
        with RecordStore.open(self.parent/"maximum-six"):
            pass

    def test_activation_rejects_unsupported_required_head_but_preserves_source(self):
        """Schema-5 generic context history is preservable, but unusable watched heads cannot activate."""
        with RecordStore.create(self.parent/"unsupported-old", schema_version=5) as old:
            populate(old)
            request = batch("opaque-head", [RecordEnvelope("scope", 2, "research_context", {}, PROVENANCE)])
            original = old.submit(request)
            create_backup(old, self.parent/"unsupported-backup")
            before = metadata(self.parent/"unsupported-old")
            with self.assertRaises(BackupError):
                restore_backup(self.parent/"unsupported-backup", self.parent/"unsupported-six", target_schema=6,
                               migration_provenance=PROVENANCE)
            self.assertEqual(metadata(self.parent/"unsupported-old"), before)
            self.assertEqual(old.submit(request), original)
            self.assertTrue((self.parent/"unsupported-six/.restore-incomplete").exists())

    def test_auxiliary_schema6_capabilities_and_authenticated_policy_successor(self):
        """Resources, reports, control/source and authenticated policy writes retain their contracts."""
        from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
        from tests import resource_fixtures as resources, report_fixtures as reports, operating_fixtures as operating
        from research_pipeline import operating_authority as authority
        from research_pipeline.snapshot import _schema_identity
        from research_pipeline.resources import ResourceSnapshot
        with RecordStore.create(self.parent/"capabilities", schema_version=6) as store:
            request, control = sources.populate(store)
            source = sources.commit(store)
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
            self.assertEqual(sources.commit(store).to_dict(limits=sources.LIMITS), source.to_dict(limits=sources.LIMITS))
            snapshot = store.inspect_resources(limits=resources.LIMITS).to_dict()
            self.assertEqual(snapshot["schema_version"], 6)
            self.assertEqual(snapshot["schema_identity"], _schema_identity(6))
            self.assertEqual(ResourceSnapshot(snapshot).to_dict(), snapshot)
            create_backup(store, self.parent/"capabilities-backup")
        with restore_backup(self.parent/"capabilities-backup", self.parent/"restored") as store:
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
        with RecordStore.create(self.parent/"reports", schema_version=6) as store:
            reports.populate(store)
            result = store.commit_report(reports.report_request())
            self.assertEqual(store.get_report_operation("report_initial"), result)
            self.assertEqual(store.read_report("report_initial").to_dict()["scientific"]["schema"]["version"], 6)
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
        self.assertEqual(view["observed_policies"][0]["observed_policy"], exact(envelope.record_id, 2, "decision"))
        self.assertFalse(view["eligible"])
        self.assertEqual(self.store.commit_operating_decision(reduced, policy=None, evaluated_at=None, limits=operating.LIMITS), receipt)

    def test_schema5_saved_capability_documents_and_recovery_survive_activation(self):
        """Migration preserves old report/control/source bytes and original-operation recovery semantics."""
        from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
        from tests import report_fixtures as reports
        with RecordStore.create(self.parent/"old-controls", schema_version=5) as old:
            request, control = sources.populate(old)
            source = sources.commit(old)
            saved_source = source.to_dict(limits=sources.LIMITS)
            before = metadata(self.parent/"old-controls")
            create_backup(old, self.parent/"old-controls-backup")
        with restore_backup(self.parent/"old-controls-backup", self.parent/"new-controls", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
            self.assertEqual(sources.commit(store).to_dict(limits=sources.LIMITS), saved_source)
            after = metadata(self.parent/"new-controls")
            self.assertEqual({k: v for k, v in after.items() if k not in ("migration_history", "claim_use_context_origin")},
                             {k: v for k, v in before.items() if k != "migration_history"})
        with RecordStore.create(self.parent/"old-reports", schema_version=5) as old:
            reports.populate(old)
            request = reports.report_request()
            receipt = old.commit_report(request)
            observation = old.read_report("report_initial").to_dict()
            self.assertEqual(observation["scientific"]["schema"]["version"], 5)
            create_backup(old, self.parent/"old-reports-backup")
        with restore_backup(self.parent/"old-reports-backup", self.parent/"new-reports", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            before_retry = metadata(self.parent/"new-reports")
            self.assertEqual(store.commit_report(request), receipt)
            self.assertEqual(store.read_report("report_initial").to_dict(), observation)
            self.assertEqual(metadata(self.parent/"new-reports"), before_retry)

    def test_migration_chain_continues_through_six(self):
        """The existing explicit 1→2→3→4→5 sequence can continue without rewriting original rows."""
        from tests.legacy import historical_store, table_values
        original, requests, artifact = historical_store(self.parent/"legacy")
        with original:
            rows = table_values(self.parent/"legacy")
            receipts = [original.get_submission(r.submission_id) for r in requests]
            create_backup(original, self.parent/"backup-1")
        for version in (2, 3, 4, 5, 6):
            with restore_backup(self.parent/f"backup-{version-1}", self.parent/f"store-{version}",
                    target_schema=version, migration_provenance=PROVENANCE) as store:
                self.assertEqual(table_values(self.parent/f"store-{version}"), rows)
                self.assertEqual([store.submit(r) for r in requests], receipts)
                create_backup(store, self.parent/f"backup-{version}")
        with sqlite3.connect(self.parent/"store-6/metadata.sqlite3") as connection:
            self.assertEqual(list(connection.execute("SELECT migration_id,source_schema,target_schema FROM migration_history")),
                             [(1,1,2), (2,2,3), (3,3,4), (4,4,5), (5,5,6)])


if __name__ == "__main__":
    unittest.main()
