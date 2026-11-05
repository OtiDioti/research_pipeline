"""Schema-7 atomicity, original-ID recovery, independent snapshots and durable activation."""

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

from research_pipeline import claim_use_store as freshness
from research_pipeline.backup import create_backup, restore_backup, inspect_backup, BackupError, BackupLayoutError
from research_pipeline.claim_use import ClaimUseLimitError, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope, DomainValidationError
from research_pipeline.store import RecordStore, RevisionConflictError, SubmissionConflictError
from tests.claim_use_fixtures import support_context_graph, batch, ref, PROVENANCE, LIMITS
from tests.test_claim_use_context import exact, context_record
from tests.test_claim_use_support_context import OCCURRENCES, support_cause
from tests.test_claim_use_store import metadata


class SupportContextRecoveryTests(unittest.TestCase):
    """Isolated stores and thread-confined handles preserve transaction and publication boundaries."""

    def setUp(self):
        """Create private source/artifact state with exact saved registration receipts."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=7)
        self.addCleanup(self.store.close)
        self.fixture = support_context_graph(self.store)

    def view(self, store=None):
        """Return a complete support inspection using the caller's own connection."""
        return (store or self.store).inspect_claim_use("use", limits=LIMITS).to_dict()

    def child(self, code, *args, expected=0):
        """Run candidate-local code in a fresh interpreter with bounded retained diagnostics."""
        implementation = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-B", "-c", code, *map(str, args)], cwd=self.parent,
            env={**os.environ, "PYTHONPATH": os.pathsep.join((str(implementation/"src"), str(implementation))),
                 "PYTHONDONTWRITEBYTECODE": "1"}, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def test_rollback_cas_lost_acknowledgment_and_artifact_independent_retry(self):
        """Heads, support rows and generations roll back together; completed requests bypass all fresh checks."""
        request = batch("advance", [context_record("support-evidence")])
        before = metadata(self.root)
        for boundary in ("before_metadata", "after_first_revision", "after_claim_use_updates"):
            def fail(point):
                """Raise only at the selected owning-transaction seam."""
                if point == boundary:
                    raise RuntimeError(boundary)
            with patch("research_pipeline.store._fault", fail), self.assertRaisesRegex(RuntimeError, boundary):
                self.store.submit(request)
            self.assertEqual(metadata(self.root), before)
        with self.assertRaises(RevisionConflictError):
            self.store.submit(batch("stale", request.records, {"support-evidence": 0}))
        self.assertEqual(metadata(self.root), before)
        def lost(point):
            """Lose acknowledgment after the transaction has actually committed."""
            if point == "after_commit":
                raise RuntimeError("lost acknowledgment")
        with patch("research_pipeline.store._fault", lost), self.assertRaisesRegex(RuntimeError, "lost"):
            self.store.submit(request)
        receipt = self.store.get_submission("advance")
        self.store.submit(batch("later", [context_record("support-evidence", 3)]))
        (self.root/"objects"/self.fixture["artifact"].digest).unlink()
        with patch.object(self.store._artifacts, "verify", side_effect=AssertionError("historical byte read")):
            self.store.submit(batch("metadata-only", [context_record("support-evidence", 4)]))
            self.assertEqual(self.view()["generation"], 4)
        from research_pipeline.artifacts import ArtifactError
        with self.assertRaises(ArtifactError):
            self.store.get_typed_revision("s-evidence", 1)
        before = metadata(self.root)
        with patch.object(freshness, "prepare", side_effect=AssertionError("retry planned")), \
             patch.object(RecordStore, "_check_batch", side_effect=AssertionError("retry admitted")):
            self.assertEqual(self.store.submit(request), receipt)
            self.assertEqual(self.store.submit_typed(self.fixture["request"]), self.fixture["receipt"])
        with self.assertRaises(SubmissionConflictError):
            self.store.submit(batch("advance", [context_record("support-evidence", question="conflict")]))
        with self.assertRaises(ArtifactError):
            self.store.submit_typed(batch("fresh-admission", [use_envelope("fresh", 1, self.fixture["upstream"], PROVENANCE)]))
        self.assertEqual(metadata(self.root), before)

    def test_independent_handles_observe_old_then_new_coherent_heads_and_generations(self):
        """A writer paused before commit exposes no new support head with an old affected generation."""
        updated, observed, committed = threading.Event(), threading.Event(), threading.Event()
        results, failures = [], []
        def read():
            """Confine each reader connection to its thread and synchronize without sleeps."""
            try:
                self.assertTrue(updated.wait(10))
                with RecordStore.open(self.root) as store:
                    results.append(self.view(store))
                    observed.set()
                    self.assertTrue(committed.wait(10))
                    results.append(self.view(store))
            except BaseException as error:
                failures.append(error)
                observed.set()
        def barrier(point):
            """Pause after real SQL updates while an independent old snapshot completes."""
            if point == "after_claim_use_updates":
                updated.set()
                self.assertTrue(observed.wait(10))
        thread = threading.Thread(target=read)
        thread.start()
        try:
            with patch("research_pipeline.store._fault", barrier):
                self.store.submit(batch("advance", [context_record("support-evidence")]))
        finally:
            updated.set()
            committed.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual([(v["generation"], v["observed_support_contexts"][4]["observed_context"]["revision"]) for v in results], [(1, 1), (2, 2)])

    def test_inspection_paused_across_writer_transaction_keeps_original_snapshot(self):
        """Exact bound and observed support contents come from one read snapshot during concurrent writes."""
        ready, begin, paused, resume, done = (threading.Event() for _ in range(5))
        results, failures = [], []
        def read():
            """Open before fault patching, then pause only the public inspection."""
            try:
                with RecordStore.open(self.root) as store:
                    ready.set()
                    self.assertTrue(begin.wait(10))
                    results.append(self.view(store))
            except BaseException as error:
                failures.append(error)
            finally:
                done.set()
        def barrier(point):
            """Let writer SQL finish while the reader retains its earlier snapshot."""
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
                self.store.submit(batch("advance", [context_record("support-evidence")]))
        finally:
            begin.set()
            resume.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results[0]["generation"], 1)
        self.assertEqual(results[0]["observed_support_contexts"][4]["observed_context"], exact("support-evidence"))
        self.assertEqual(self.view()["generation"], 2)

    def test_reopen_fresh_process_and_exact_backup_preserve_metadata_and_receipts(self):
        """Exact format/schema 7 preserves bytes, all origins and complete provenance in independent processes."""
        request = batch("advance", [context_record("support-evidence")])
        receipt = self.store.submit(request)
        expected = self.view()
        backup = self.parent/"backup"
        info = create_backup(self.store, backup)
        self.assertEqual((info.format_version, info.schema_version), (7, 7))
        self.assertEqual(inspect_backup(backup), info)
        output = self.child('''
import json,sys
from research_pipeline.store import RecordStore
from tests.claim_use_fixtures import LIMITS
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps(store.inspect_claim_use("use",limits=LIMITS).to_dict(),sort_keys=True))
''', self.root)
        self.assertEqual(json.loads(output), expected)
        destination = self.parent/"restore"
        with restore_backup(backup, destination) as store:
            self.assertEqual((destination/"metadata.sqlite3").read_bytes(), (backup/"snapshot.sqlite3").read_bytes())
            self.assertEqual(self.view(store), expected)
            self.assertEqual(store.submit(request), receipt)
            for table in ("claim_use_origin", "claim_use_policy_origin", "claim_use_context_origin", "claim_use_support_context_origin"):
                self.assertEqual(list(store._connection.execute("SELECT * FROM "+table)), [(1, 0)])

    def test_six_to_seven_backfill_preserves_old_rows_history_and_temporal_activation(self):
        """Old support advancements become observations; U@1 remains backfilled after a disjoint U@2."""
        oldroot, backup, destination = (self.parent/n for n in ("six", "six-backup", "migrated"))
        with RecordStore.create(oldroot, schema_version=6) as old:
            fixture = support_context_graph(old)
            request = batch("prefeature", [context_record("support-evidence")])
            receipt = old.submit(request)
            old.submit_typed(batch("rebind", [use_envelope("use", 2, fixture["independent"], PROVENANCE)]))
            before = metadata(oldroot)
            watermark = old.get_submission("rebind").event_id
            create_backup(old, backup)
        with restore_backup(backup, destination, target_schema=7, migration_provenance=PROVENANCE) as store:
            after = metadata(destination)
            for table, rows in before.items():
                if table != "migration_history":
                    self.assertEqual(after[table], rows, table)
            self.assertEqual(after["migration_history"][:-1], before["migration_history"])
            self.assertEqual(store.submit(request), receipt)
            view = store.inspect_claim_use("downstream-use", limits=LIMITS).to_dict()
            self.assertEqual(view["generation"], 1)
            self.assertEqual(view["support_context_freshness"], dict(available=True, activation_event_watermark=watermark))
            self.assertEqual([c["type"] for c in view["mechanical_freshness"]["last_transition"]["causes"]], ["binding_registered"])
            self.assertTrue(any(o["superseded"] for o in view["observed_support_contexts"] if o["source_role"] == "evidence"))
            store.submit(batch("after-activation", [context_record("support-evidence", 3)]))
            view = store.inspect_claim_use("downstream-use", limits=LIMITS).to_dict()
            self.assertEqual(view["generation"], 2)
            causes = [c for c in view["mechanical_freshness"]["last_transition"]["causes"] if c["type"] == "support_context_changed"]
            self.assertEqual(causes, sorted([support_cause(o, "support-evidence", previous=2, new=3) for o in (OCCURRENCES[4], OCCURRENCES[7])], key=freshness._canonical))
            self.assertEqual(self.view(store)["generation"], 2)
        with RecordStore.open(destination):
            pass
        self.assertEqual(metadata(oldroot), before)

    def test_full_consecutive_chain_empty_activation_and_invalid_options_before_reservation(self):
        """Only explicit consecutive attributed steps activate features; empty origins remain zero."""
        with RecordStore.create(self.parent/"default") as store:
            self.assertEqual(store._schema_version, 2)
        from tests.legacy import create_legacy
        with create_legacy(self.parent/"one") as store:
            create_backup(store, self.parent/"backup-1")
        for version in range(2, 8):
            root = self.parent/("schema-"+str(version))
            with restore_backup(self.parent/("backup-"+str(version-1)), root,
                    target_schema=version, migration_provenance=PROVENANCE) as store:
                self.assertEqual(store._schema_version, version)
                create_backup(store, self.parent/("backup-"+str(version)))
        for table in ("claim_use_origin", "claim_use_policy_origin", "claim_use_context_origin", "claim_use_support_context_origin"):
            self.assertEqual(metadata(root)[table], [(1, 0)])
        for index, (version, provenance) in enumerate(((True, PROVENANCE), (7.0, PROVENANCE), (8, PROVENANCE),
                (5, PROVENANCE), (7, None), (None, PROVENANCE))):
            destination = self.parent/("invalid-"+str(index))
            with self.assertRaises(BackupLayoutError):
                restore_backup(self.parent/"backup-6", destination, target_schema=version, migration_provenance=provenance)
            self.assertFalse(destination.exists())

    def test_process_death_at_real_submission_and_migration_boundaries(self):
        """Hot-journal rollback and published-copy recovery retain old-or-new effects and incomplete markers."""
        saved = self.parent/"request.json"
        request = batch("process", [context_record("support-evidence")])
        saved.write_text(json.dumps(request.to_dict()))
        code = '''
import json,os,sys
from research_pipeline import store as module
from research_pipeline.domain import Submission
def crash(point):
    """Exit only at the selected real transaction seam, without unwinding."""
    if point == sys.argv[3]: os._exit(74)
module._fault=crash
with module.RecordStore.open(sys.argv[1]) as store:
    store.submit(Submission.from_dict(json.loads(open(sys.argv[2]).read())))
'''
        for boundary in ("before_metadata", "after_first_revision", "after_claim_use_updates", "after_commit"):
            before = metadata(self.root)
            self.child(code, self.root, saved, boundary, expected=74)
            with RecordStore.open(self.root) as reopened:
                if boundary == "after_commit":
                    self.assertEqual(reopened.submit(request), reopened.get_submission("process"))
                    self.assertEqual(self.view(reopened)["generation"], 2)
                else:
                    self.assertEqual(metadata(self.root), before)
        with RecordStore.create(self.parent/"six", schema_version=6) as old:
            support_context_graph(old)
            create_backup(old, self.parent/"six-backup")
        before = metadata(self.parent/"six")
        code = '''
import os,sys
from research_pipeline import backup
from tests.claim_use_fixtures import PROVENANCE
def crash(point):
    """Exit at transformation, commit or publication without removing the marker."""
    if point == sys.argv[3]: os._exit(75)
backup._fault=crash
backup.restore_backup(sys.argv[1],sys.argv[2],target_schema=7,migration_provenance=PROVENANCE)
'''
        for boundary in ("migration_transform", "migration_committed", "before_publication"):
            destination = self.parent/boundary
            self.child(code, self.parent/"six-backup", destination, boundary, expected=75)
            self.assertTrue((destination/".restore-incomplete").exists())
            self.assertEqual(metadata(self.parent/"six"), before)
            with self.assertRaises(BackupError):
                restore_backup(self.parent/"six-backup", destination, target_schema=7, migration_provenance=PROVENANCE)
        with restore_backup(self.parent/"six-backup", self.parent/"recovered", target_schema=7, migration_provenance=PROVENANCE) as store:
            self.assertEqual(self.view(store)["version"], 4)

    def test_unusable_support_head_or_oversized_boundary_rejects_before_publication(self):
        """Pre-feature generic support heads may exist, but migration must inspect complete usable scopes."""
        for label, content in (("unsupported", {}), ("oversized", None)):
            oldroot = self.parent/label
            with RecordStore.create(oldroot, schema_version=6) as old:
                fixture = support_context_graph(old, shared=True)
                record = (RecordEnvelope("support-shared", 2, "research_context", content, PROVENANCE)
                          if content is not None else context_record("support-shared", question="x"*600000))
                request = batch("prefeature", [record])
                receipt = old.submit(request)
                backup = self.parent/(label+"-backup")
                create_backup(old, backup)
                before = metadata(oldroot)
                destination = self.parent/(label+"-seven")
                with self.assertRaises(BackupError):
                    restore_backup(backup, destination, target_schema=7, migration_provenance=PROVENANCE)
                self.assertTrue((destination/".restore-incomplete").exists())
                self.assertEqual(metadata(oldroot), before)
                self.assertEqual(old.submit(request), receipt)

    def test_auxiliary_schema7_capabilities_and_authenticated_policy_successor(self):
        """Resources, reports, control/source and authenticated policy writes retain their contracts."""
        from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
        from tests import resource_fixtures as resources, report_fixtures as reports, operating_fixtures as operating
        from research_pipeline import operating_authority as authority
        from research_pipeline.snapshot import _schema_identity
        from research_pipeline.resources import ResourceSnapshot
        with RecordStore.create(self.parent/"capabilities", schema_version=7) as store:
            request, control = sources.populate(store)
            source = sources.commit(store)
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
            self.assertEqual(sources.commit(store).to_dict(limits=sources.LIMITS), source.to_dict(limits=sources.LIMITS))
            snapshot = store.inspect_resources(limits=resources.LIMITS).to_dict()
            self.assertEqual(snapshot["schema_version"], 7)
            self.assertEqual(snapshot["schema_identity"], _schema_identity(7))
            self.assertEqual(ResourceSnapshot(snapshot).to_dict(), snapshot)
            create_backup(store, self.parent/"capabilities-backup")
        with restore_backup(self.parent/"capabilities-backup", self.parent/"restored") as store:
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
        with RecordStore.create(self.parent/"reports", schema_version=7) as store:
            reports.populate(store)
            result = store.commit_report(reports.report_request())
            self.assertEqual(store.get_report_operation("report_initial"), result)
            self.assertEqual(store.read_report("report_initial").to_dict()["scientific"]["schema"]["version"], 7)
        operating.empty(self.store)
        scope = operating.scope()
        bound = operating.prepare(self.store, scope)
        signed = operating.sign(operating.decision(bound, scope))
        self.store.commit_operating_decision(signed, policy=operating.policy(), evaluated_at=operating.TIME, limits=operating.LIMITS)
        envelope = authority.encode_envelope(signed)
        leaf = replace(self.fixture["independent"], policies=[ref(envelope.record_id, "authorization_policy", "decision")])
        self.store.submit_typed(batch("operating-policy-use", [use_envelope("operating-use", 1, leaf, PROVENANCE)]))
        reduced = operating.sign(operating.decision(bound, revision=2, previous=envelope, outcome="revoke", operation="reduce"))
        with self.assertRaisesRegex(DomainValidationError, "commit_operating_decision"):
            self.store.submit_typed(authority.submission(reduced))
        receipt = self.store.commit_operating_decision(reduced, policy=operating.policy(), evaluated_at=operating.TIME, limits=operating.LIMITS)
        view = self.store.inspect_claim_use("operating-use", limits=LIMITS).to_dict()
        self.assertEqual(view["generation"], 2)
        self.assertEqual(view["observed_policies"][0]["observed_policy"], exact(envelope.record_id, 2, "decision"))
        self.assertFalse(view["eligible"])
        self.assertEqual(self.store.commit_operating_decision(reduced, policy=None, evaluated_at=None, limits=operating.LIMITS), receipt)


    def test_schema6_saved_capability_documents_and_recovery_survive_activation(self):
        """Migration preserves old report/control/source bytes and original-operation recovery semantics."""
        from tests import lifecycle_source_fixtures as sources, run_control_fixtures as controls
        from tests import report_fixtures as reports
        with RecordStore.create(self.parent/"old-controls", schema_version=6) as old:
            request, control = sources.populate(old)
            source = sources.commit(old)
            saved_source = source.to_dict(limits=sources.LIMITS)
            before = metadata(self.parent/"old-controls")
            create_backup(old, self.parent/"old-controls-backup")
        with restore_backup(self.parent/"old-controls-backup", self.parent/"new-controls", target_schema=7,
                migration_provenance=PROVENANCE) as store:
            self.assertEqual(store.get_run_control_operation("prepare", limits=controls.LIMITS), control)
            self.assertEqual(sources.commit(store).to_dict(limits=sources.LIMITS), saved_source)
            after = metadata(self.parent/"new-controls")
            self.assertEqual({k: v for k, v in after.items() if k not in ("migration_history", "claim_use_support_context_origin", "claim_use_support_contexts")},
                             {k: v for k, v in before.items() if k != "migration_history"})
        with RecordStore.create(self.parent/"old-reports", schema_version=6) as old:
            reports.populate(old)
            request = reports.report_request()
            receipt = old.commit_report(request)
            observation = old.read_report("report_initial").to_dict()
            self.assertEqual(observation["scientific"]["schema"]["version"], 6)
            create_backup(old, self.parent/"old-reports-backup")
        with restore_backup(self.parent/"old-reports-backup", self.parent/"new-reports", target_schema=7,
                migration_provenance=PROVENANCE) as store:
            before_retry = metadata(self.parent/"new-reports")
            self.assertEqual(store.commit_report(request), receipt)
            self.assertEqual(store.read_report("report_initial").to_dict(), observation)
            self.assertEqual(metadata(self.parent/"new-reports"), before_retry)


    def test_support_activation_at_signed_maximum_uses_no_successor_arithmetic(self):
        """A maximum scientific watermark can activate and reopen, while further no-impact writes fail."""
        with RecordStore.create(self.parent/"maximum-six", schema_version=6) as old:
            support_context_graph(old)
            request = batch("ceiling", [RecordEnvelope("ceiling", 1, "event", {}, PROVENANCE)])
            old.submit(request)
            connection = old._connection
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("UPDATE audit_events SET event_id=? WHERE submission_id='ceiling'", (2**63-1,))
            connection.execute("UPDATE claim_use_revision_events SET event_id=? WHERE record_id='ceiling'", (2**63-1,))
            connection.execute("PRAGMA foreign_keys=ON")
            receipt = old.get_submission("ceiling")
            create_backup(old, self.parent/"maximum-backup")
        destination = self.parent/"maximum-seven"
        with restore_backup(self.parent/"maximum-backup", destination, target_schema=7, migration_provenance=PROVENANCE) as store:
            self.assertEqual(self.view(store)["support_context_freshness"], dict(available=True, activation_event_watermark=2**63-1))
            self.assertEqual(store.submit(request), receipt)
            before = metadata(destination)
            with self.assertRaisesRegex(ClaimUseLimitError, "event_id"):
                store.submit(batch("no-impact", [RecordEnvelope("never", 1, "event", {}, PROVENANCE)]))
            self.assertEqual(metadata(destination), before)
        with RecordStore.open(destination):
            pass

    def test_earlier_activation_accounts_explicitly_disable_support_semantics(self):
        """Policy/target boundary inspections and old chronological accounts cannot consume later support views."""
        with RecordStore.create(self.parent/"four", schema_version=4) as store:
            support_context_graph(store)
            create_backup(store, self.parent/"activation-backup-4")
        for version in (5, 6, 7):
            with restore_backup(self.parent/("activation-backup-"+str(version-1)),
                    self.parent/("activation-"+str(version)), target_schema=version, migration_provenance=PROVENANCE) as store:
                store.submit(batch("event-"+str(version), [context_record("support-evidence", version-3)]))
                create_backup(store, self.parent/("activation-backup-"+str(version)))
        captured = []
        original = freshness._inspection
        def capture(reader, identity, limits):
            """Retain real boundary outputs and feature selections without replacing validation work."""
            result = original(reader, identity, limits)
            if reader.overlay is None and reader.cutoff is not None:
                captured.append((reader.context_active, reader.support_context_active, result.to_dict()["version"]))
            return result
        with patch.object(freshness, "_inspection", capture), RecordStore.open(self.parent/"activation-7"):
            pass
        self.assertEqual(sorted(set(captured)), [(False, False, 2), (True, False, 3), (True, True, 4)])

    def test_original_registration_account_remains_exact_after_independent_backfill(self):
        """New projections and boundary views do not recharge completed schema-6 event admission accounts."""
        with RecordStore.create(self.parent/"account-six", schema_version=6) as old:
            fixture = support_context_graph(old)
            request, event = fixture["request"], fixture["receipt"].event_id
            with old._transaction() as connection:
                previous = freshness.prepare(old, connection, request, cutoff=event, verify=False)
            old_counts, old_transitions = dict(previous.reader.counts), previous.transitions
            create_backup(old, self.parent/"account-backup")
        with restore_backup(self.parent/"account-backup", self.parent/"account-seven", target_schema=7,
                migration_provenance=PROVENANCE) as store:
            with store._transaction() as connection:
                actual = freshness.prepare(store, connection, request, cutoff=event, verify=False,
                    policy=True, context=True, support_context=False)
            self.assertEqual(actual.reader.counts, old_counts)
            self.assertEqual(actual.transitions, old_transitions)
            self.assertEqual(actual.support_contexts, {})
            self.assertEqual(self.view(store)["version"], 4)
            self.assertEqual(len(self.view(store)["observed_support_contexts"]), 8)
