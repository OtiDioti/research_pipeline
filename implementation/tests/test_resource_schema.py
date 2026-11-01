"""Schema3 creation, verified migrations, immutable tampering and scientific compatibility."""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import backup
from research_pipeline.backup import BackupError, BackupIntegrityError, BackupOperationalError, create_backup, inspect_backup, restore_backup
from research_pipeline.resources import ResourceRequest, ResourceIntegrityError, canonical
from research_pipeline.store import RecordStore, StoreLayoutError
from tests.legacy import create_legacy, table_values, historical_store
from tests.resource_fixtures import PROVENANCE, LIMITS, populate, reservation, root_request, allocation, observation, reconciliation, vector
from tests.test_store import record, request
from tests.test_vault import child_environment, restore_directories


def rehash_backup(root):
    """Repair outer byte hashes only, so tests exercise deeper application invariant checks."""
    data = (root / "snapshot.sqlite3").read_bytes()
    path = root / "manifest.json"
    document = json.loads(path.read_text())
    document["metadata"] = {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}
    path.chmod(0o600)
    path.write_text(canonical(document))
    path.chmod(0o400)


class ResourceSchemaTests(unittest.TestCase):
    """Preserve old schemas while validating the entire new canonical ledger boundary."""

    def setUp(self):
        """Allocate an external disposable runtime area and bounded candidate process environment."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.addCleanup(restore_directories, self.parent)

    def test_creation_defaults_invalid_options_and_old_schema_resource_rejection(self):
        """Invalid schema choices never reserve roots and old resource calls cannot migrate implicitly."""
        for i, version in enumerate((None, True, False, 1, 0, 4, -1, "3", 3.0, [], {})):
            root = self.parent / f"invalid-{i}"
            with self.assertRaises(StoreLayoutError):
                RecordStore.create(root, schema_version=version)
            self.assertFalse(root.exists())
        for version in (1, 2, 3):
            root = self.parent / str(version)
            creator = create_legacy if version == 1 else RecordStore.create
            with creator(root, **({"schema_version": 3} if version == 3 else {})) as store:
                self.assertEqual(store._schema_version, version)
                if version == 3:
                    self.assertEqual(store.inspect_resources(limits=LIMITS).to_dict()["operations"], [])
                    continue
                before = (root / "metadata.sqlite3").read_bytes()
                for operation in (lambda: store.create_resource_account(root_request()), lambda: store.allocate_resources(allocation("run", "run", "project")),
                                  lambda: store.reserve_resources(reservation()), lambda: store.observe_resource_usage(observation()),
                                  lambda: store.reconcile_resource_usage(reconciliation()), lambda: store.get_resource_operation("missing"),
                                  lambda: store.inspect_resources(limits=LIMITS)):
                    with self.assertRaisesRegex(StoreLayoutError, "migration"):
                        operation()
                self.assertEqual((root / "metadata.sqlite3").read_bytes(), before)

    def test_fresh_and_historical_v2_to_v3_preserve_all_scientific_rows(self):
        """Both 2→3 paths preserve SQL/artifacts/history while completing usage and retaining uncertainty."""
        for historical in (False, True):
            root = self.parent / f"source-{historical}"
            if historical:
                legacy = self.parent / "legacy"
                with create_legacy(legacy) as store:
                    artifact = store.put_artifact(b"legacy exact bytes")
                    batch = request("original", [record("context", artifact_references=[artifact])])
                    receipt = store.submit(batch)
                    store.submit(request("revision", [record("context", 2)], {"context": 1}))
                    create_backup(store, self.parent / "v1-backup")
                with restore_backup(self.parent / "v1-backup", root, target_schema=2, migration_provenance=PROVENANCE):
                    pass
            else:
                with RecordStore.create(root) as store:
                    artifact = store.put_artifact(b"fresh2 exact bytes")
                    batch = request("original", [record("context", artifact_references=[artifact])])
                    receipt = store.submit(batch)
                    store.submit(request("revision", [record("context", 2)], {"context": 1}))
            with RecordStore.open(root) as store:
                exported = self.parent / f"backup-{historical}"
                info = create_backup(store, exported)
            with sqlite3.connect(root / "metadata.sqlite3") as connection:
                old_history = connection.execute("SELECT * FROM migration_history").fetchall()
            original = table_values(root)
            source_bytes = (exported / "snapshot.sqlite3").read_bytes()
            upgraded = self.parent / f"upgraded-{historical}"
            with restore_backup(exported, upgraded, target_schema=3, migration_provenance=PROVENANCE) as store:
                self.assertEqual(store._schema_version, 3)
                self.assertEqual(table_values(upgraded), original)
                self.assertEqual(store.submit(batch), receipt)
                self.assertEqual(store.read_artifact(artifact), (exported / "objects" / artifact.digest).read_bytes())
                with sqlite3.connect(upgraded / "metadata.sqlite3") as connection:
                    history = connection.execute("SELECT * FROM migration_history ORDER BY migration_id").fetchall()
                self.assertEqual(history[:-1], old_history)
                self.assertEqual(history[-1], (len(old_history) + 1, 2, 3, info.backup_id,
                    canonical(json.loads((exported / "manifest.json").read_text())), canonical(PROVENANCE.to_dict())))
                populate(store)
                item = reservation()
                result = store.reserve_resources(item)
                store.observe_resource_usage(observation("partial"))
                store.observe_resource_usage(observation("timeout", event="timeout"))
                store.reconcile_resource_usage(reconciliation("conservative", mode="conservative", observation_operation_id="op_timeout"))
                store.observe_resource_usage(observation("complete", event="authoritative_completion"))
                store.reconcile_resource_usage(reconciliation(previous="op_conservative"))
                store.reserve_resources(reservation("unknown"))
                store.observe_resource_usage(observation("lost", "reservation_unknown", event="acknowledgment_loss"))
                snapshot = store.inspect_resources(limits=LIMITS)
                complete = self.parent / f"v3-backup-{historical}"
                create_backup(store, complete)
            with restore_backup(complete, self.parent / f"exact-{historical}") as store:
                self.assertEqual(store.inspect_resources(limits=LIMITS), snapshot)
                self.assertEqual(store.get_resource_operation(item.operation_id), result)
                self.assertEqual(store.submit(batch), receipt)
                self.assertEqual((self.parent / f"exact-{historical}" / "metadata.sqlite3").read_bytes(), (complete / "snapshot.sqlite3").read_bytes())
            self.assertEqual((exported / "snapshot.sqlite3").read_bytes(), source_bytes)

    def test_transform_rollback_and_abrupt_publication_failures(self):
        """Actual 2→3 DDL/COMMIT faults retain incomplete copies and leave source bytes unchanged."""
        source = self.parent / "source"
        with RecordStore.create(source) as store:
            store.submit(request())
            exported = self.parent / "backup"
            create_backup(store, exported)
        before = (exported / "snapshot.sqlite3").read_bytes()

        def fail(point):
            """Raise after the old history table was dropped inside the real transform transaction."""
            if point == "migration_transform":
                raise OSError("actual transform interrupted")

        with patch.object(backup, "_fault", side_effect=fail), self.assertRaises(BackupOperationalError):
            restore_backup(exported, self.parent / "failed", target_schema=3, migration_provenance=PROVENANCE)
        with sqlite3.connect(self.parent / "failed/metadata.sqlite3") as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (2,))
        for boundary in ("migration_transform", "migration_committed", "before_publication"):
            destination = self.parent / boundary
            program = '''
import os, sys
from research_pipeline import backup
from research_pipeline.domain import CreationProvenance
def fail(point):
    """Exit after a real migration boundary without cleanup or rollback simulation."""
    if point == sys.argv[3]:
        os._exit(73)
backup._fault = fail
backup.restore_backup(sys.argv[1], sys.argv[2], target_schema=3,
    migration_provenance=CreationProvenance("controller", "2026-11-01T00:00:00Z"))
'''
            result = subprocess.run([sys.executable, "-B", "-c", program, str(exported), str(destination), boundary],
                                    env=child_environment(), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 73, result.stderr)
            self.assertTrue((destination / ".restore-incomplete").exists())
            with self.assertRaises(StoreLayoutError):
                RecordStore.open(destination)
        self.assertEqual((exported / "snapshot.sqlite3").read_bytes(), before)

    def test_live_and_rehashed_backup_tampering_rejects_history_and_projections(self):
        """Rehashed policies, receipts, historical admissions and normalized facts remain invalid."""
        root = self.parent / "baseline"
        exported = self.parent / "backup"
        with RecordStore.create(root, schema_version=3) as store:
            populate(store)
            store.reserve_resources(reservation())
            create_backup(store, exported)
        baseline = (root / "metadata.sqlite3").read_bytes()
        changes = []
        for mode in ("missing_bounds", "null_bounds", "bool_bounds", "duplicate_bounds", "short_input", "short_output", "context", "overflow"):
            changes.append(("policy", mode))
        changes += [("sql", sql) for sql in (
            "UPDATE resource_operations SET fingerprint='" + "0" * 64 + "' WHERE sequence=1",
            "UPDATE resource_accounts SET owner_id='wrong' WHERE account_id='attempt'",
            "UPDATE resource_accounts SET policy_json='{}' WHERE account_id='task'",
            "DELETE FROM resource_record_links WHERE ordinal=0",
            "UPDATE resource_operations SET sequence=100 WHERE sequence=5",
            "UPDATE resource_reservations SET purpose='handoff'",
            "UPDATE resource_allocations SET purpose_limits_json='{}'",
            "UPDATE resource_operations SET result_json='{}' WHERE sequence=5",
            "INSERT INTO migration_history VALUES (1,2,3,'bad','{}','{}')",
            "CREATE TABLE unknown_table (x TEXT)",
            "CREATE INDEX extra_resource_index ON resource_accounts(owner_id)",
            "ALTER TABLE resource_reservations ADD COLUMN unknown TEXT",
        )]
        for index, (kind, change) in enumerate(changes):
            candidate = self.parent / f"live-{index}"
            shutil.copytree(root, candidate)
            with sqlite3.connect(candidate / "metadata.sqlite3") as connection:
                if kind == "sql":
                    connection.execute(change)
                else:
                    text, result = connection.execute("SELECT request_json,result_json FROM resource_operations WHERE sequence=2").fetchone()
                    doc, receipt = json.loads(text), json.loads(result)
                    run_policy = doc["payload"]["run_policy"]
                    if change == "missing_bounds":
                        del run_policy["handoff_call_bounds"]
                    elif change == "null_bounds":
                        run_policy["handoff_call_bounds"] = None
                    elif change == "bool_bounds":
                        run_policy["handoff_call_bounds"]["max_input_tokens_per_call"] = True
                    elif change == "context":
                        run_policy["context_capacity_tokens"] = 7
                    elif change == "overflow":
                        run_policy["handoff_call_bounds"]["max_input_tokens_per_call"] = 2**62
                        run_policy["context_capacity_tokens"] = 2**63 - 1
                        for quantity in run_policy["handoff_minimum"]:
                            if quantity["dimension_id"] == "dim_model_input_tokens":
                                quantity["quantity"] = 2**63 - 1
                    elif change.startswith("short"):
                        dimension = "dim_model_input_tokens" if change == "short_input" else "dim_model_output_tokens"
                        for quantity in run_policy["handoff_minimum"]:
                            if quantity["dimension_id"] == dimension:
                                quantity["quantity"] -= 1
                    text = canonical(doc)
                    if change == "duplicate_bounds":
                        text = text.replace('"max_input_tokens_per_call":3', '"max_input_tokens_per_call":3,"max_input_tokens_per_call":3')
                    digest = hashlib.sha256(text.encode()).hexdigest()
                    receipt["request_fingerprint"] = digest
                    connection.execute("UPDATE resource_operations SET request_json=?,fingerprint=?,result_json=? WHERE sequence=2", (text, digest, canonical(receipt)))
                    connection.execute("UPDATE resource_accounts SET policy_json=? WHERE account_id IN ('run','task','attempt')", (canonical(run_policy),))
            with self.subTest(change=change), self.assertRaises(StoreLayoutError):
                RecordStore.open(candidate)
            damaged = self.parent / f"backup-{index}"
            shutil.copytree(exported, damaged)
            snapshot = damaged / "snapshot.sqlite3"
            snapshot.chmod(0o600)
            snapshot.write_bytes((candidate / "metadata.sqlite3").read_bytes())
            snapshot.chmod(0o400)
            rehash_backup(damaged)
            with self.subTest(backup=change), self.assertRaises(BackupError):
                inspect_backup(damaged)
            destination = self.parent / f"rejected-{index}"
            with self.assertRaises(BackupError):
                restore_backup(damaged, destination)
            self.assertFalse(destination.exists())
        self.assertEqual((root / "metadata.sqlite3").read_bytes(), baseline)

    def test_ledger_inspection_revalidates_historical_admission(self):
        """Even coherently edited projections cannot hide a historically over-capacity reservation."""
        root = self.parent / "runtime"
        with RecordStore.create(root, schema_version=3) as store:
            populate(store)
            store.reserve_resources(reservation())
            with sqlite3.connect(root / "metadata.sqlite3") as connection:
                text, result = connection.execute("SELECT request_json,result_json FROM resource_operations WHERE sequence=5").fetchone()
                doc, receipt = json.loads(text), json.loads(result)
                for q in doc["payload"]["maxima"]:
                    if q["dimension_id"] == "dim_tool_calls":
                        q["quantity"] = 26
                text = canonical(doc)
                digest = hashlib.sha256(text.encode()).hexdigest()
                receipt["request_fingerprint"] = digest
                connection.execute("UPDATE resource_operations SET request_json=?,fingerprint=?,result_json=? WHERE sequence=5", (text, digest, canonical(receipt)))
                connection.execute("UPDATE resource_reservations SET maxima_json=?", (canonical(doc["payload"]["maxima"]),))
            with self.assertRaises(ResourceIntegrityError):
                store.inspect_resources(limits=LIMITS)

    def test_open_handle_inspection_rejects_new_schema_objects(self):
        """Inspection verifies actual schema identity as well as previously validated history."""
        root = self.parent / "runtime"
        with RecordStore.create(root, schema_version=3) as store:
            populate(store)
            with sqlite3.connect(root / "metadata.sqlite3") as connection:
                connection.execute("CREATE VIEW unknown_projection AS SELECT account_id FROM resource_accounts")
            with self.assertRaises(ResourceIntegrityError):
                store.inspect_resources(limits=LIMITS)

    def test_schema3_typed_dossier_capture_generation_refresh_and_scientific_closure(self):
        """Usage, settlement and breaches preserve scientific outgoing closure and all readable smoke paths."""
        from tests.snapshot_fixtures import populated, limits
        from tests.view_capture_fixtures import capture_limits
        from tests.view_refresh_fixtures import refresh_limits
        from research_pipeline.view_plan import plan_readable_snapshot
        from research_pipeline.vault import materialize_readable_view
        from research_pipeline.view_capture import capture_readable_view
        from research_pipeline.view_refresh import refresh_readable_view
        temporary = TemporaryDirectory(prefix="resource-smoke-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.addCleanup(restore_directories, self.parent)
        source = Path(__file__).resolve().parents[1]
        root = self.parent / "runtime"
        with RecordStore.create(root, schema_version=3) as store:
            chosen, payloads = populated(store, self.parent)
            before = store.capture_snapshot(chosen, limits=limits())
            plan = plan_readable_snapshot(before)
            envelopes = [json.loads(r["envelope_json"]) for r in before.to_dict()["records"]]
            kinds = {r["kind"] for r in envelopes}
            self.assertTrue({"source", "corpus_manifest", "project", "work_product_manifest", "claim"} <= kinds)
            # Use the existing exact project reference already present in this dossier.
            project_id = next(r["record_id"] for r in envelopes if r["kind"] == "project")
            doc = root_request().to_dict()
            doc["payload"]["scope"]["reference"]["record_id"] = project_id
            store.create_resource_account(ResourceRequest.from_dict(doc))
            store.allocate_resources(allocation("run", "run", "project"))
            store.reserve_resources(reservation("close", account="run", purpose="closeout", maxima=vector(local_time=2)))
            store.observe_resource_usage(observation("complete", "reservation_close", account_id="run",
                event="authoritative_completion", usage=vector(local_time=1)))
            store.reconcile_resource_usage(reconciliation(reservation_id="reservation_close", account_id="run"))
            store.observe_resource_usage(observation("late", "reservation_close", account_id="run", usage=vector(local_time=11)))
            self.assertTrue(store.inspect_resources(limits=LIMITS).to_dict()["breaches"])
            after = store.capture_snapshot(chosen, limits=limits())
            self.assertEqual(after, before)
            view = self.parent / "view"
            materialize_readable_view(store, plan, view, source_root=source, protected_roots=[], max_entries=4096)
            captured = capture_readable_view(view, expected_plan=plan, source_root=source, protected_roots=[root], limits=capture_limits())
            self.assertIsNotNone(captured)
            result = refresh_readable_view(store, view, expected_plan=plan, destination=self.parent / "refreshed",
                new_plan=plan, source_root=source, protected_roots=[], limits=refresh_limits())
            self.assertIsNotNone(result)

    def test_schema3_same_version_migration_and_damaged_v2_sources_do_not_reserve(self):
        """Exact restore remains distinct from migration, whose source must be fully verified first."""
        with RecordStore.create(self.parent / "v3", schema_version=3) as store:
            create_backup(store, self.parent / "v3-backup")
        with RecordStore.create(self.parent / "v2") as store:
            create_backup(store, self.parent / "v2-backup")
        for index, (source, target) in enumerate((("v3-backup", 3), ("v3-backup", 2), ("v2-backup", 2),
                                                ("v2-backup", 4), ("v2-backup", "3"), ("v2-backup", 3.0))):
            destination = self.parent / f"invalid-migration-{index}"
            with self.assertRaises(BackupError):
                restore_backup(self.parent / source, destination, target_schema=target, migration_provenance=PROVENANCE)
            self.assertFalse(destination.exists())
        snapshot = self.parent / "v2-backup/snapshot.sqlite3"
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"not a valid immutable source")
        snapshot.chmod(0o400)
        destination = self.parent / "damaged-source"
        with self.assertRaises(BackupIntegrityError):
            restore_backup(self.parent / "v2-backup", destination, target_schema=3, migration_provenance=PROVENANCE)
        self.assertFalse(destination.exists())

    def test_nonconsecutive_historical_receipts_survive_both_migrations_and_resource_restore(self):
        """Carry nonconsecutive receipts through 1→2→3 and retain measured and uncertain settlements."""
        original, batches, artifact = historical_store(self.parent / "historical-v1")
        with original:
            receipts = [original.get_submission(batch.submission_id) for batch in batches]
            self.assertEqual([receipt.event_id for receipt in receipts], [11, 22, 33, 44, 55])
            create_backup(original, self.parent / "historical-v1-backup")
        scientific_rows = table_values(self.parent / "historical-v1")
        with restore_backup(self.parent / "historical-v1-backup", self.parent / "historical-v2",
                            target_schema=2, migration_provenance=PROVENANCE) as store:
            self.assertEqual(table_values(self.parent / "historical-v2"), scientific_rows)
            create_backup(store, self.parent / "historical-v2-backup")
        with sqlite3.connect(self.parent / "historical-v2/metadata.sqlite3") as connection:
            prior_history = connection.execute("SELECT * FROM migration_history").fetchall()
        original_snapshots = [(self.parent / name / "snapshot.sqlite3").read_bytes()
                              for name in ("historical-v1-backup", "historical-v2-backup")]
        with restore_backup(self.parent / "historical-v2-backup", self.parent / "historical-v3",
                            target_schema=3, migration_provenance=PROVENANCE) as store:
            self.assertEqual(table_values(self.parent / "historical-v3"), scientific_rows)
            for batch, receipt in zip(batches, receipts):
                self.assertEqual(store.submit(batch), receipt)
            self.assertEqual(store.submit_typed(batches[2]), receipts[2])
            self.assertEqual(store.read_artifact(artifact), b"independent historical graph bytes\n")
            with sqlite3.connect(self.parent / "historical-v3/metadata.sqlite3") as connection:
                history = connection.execute("SELECT * FROM migration_history ORDER BY migration_id").fetchall()
            self.assertEqual(history[:-1], prior_history)
            self.assertEqual([row[:3] for row in history], [(1, 1, 2), (2, 2, 3)])
            store.submit(request("resource-project", [record("project", kind="project")]))
            store.create_resource_account(root_request())
            for item in (allocation("run", "run", "project"), allocation("task", "task", "run"),
                         allocation("attempt", "attempt", "task")):
                store.allocate_resources(item)
            work = reservation("retained")
            committed = store.reserve_resources(work)
            store.observe_resource_usage(observation("partial", "reservation_retained"))
            store.observe_resource_usage(observation("complete", "reservation_retained", event="authoritative_completion"))
            store.reconcile_resource_usage(reconciliation(reservation_id="reservation_retained"))
            store.reserve_resources(reservation("unknown"))
            store.observe_resource_usage(observation("lost", "reservation_unknown", event="process_loss"))
            captured = store.inspect_resources(limits=LIMITS)
            create_backup(store, self.parent / "historical-complete")
        with restore_backup(self.parent / "historical-complete", self.parent / "historical-exact") as restored:
            self.assertEqual(restored.inspect_resources(limits=LIMITS), captured)
            self.assertEqual(restored.reserve_resources(work), committed)
            self.assertEqual([restored.get_submission(batch.submission_id) for batch in batches], receipts)
            self.assertEqual((self.parent / "historical-exact/metadata.sqlite3").read_bytes(),
                             (self.parent / "historical-complete/snapshot.sqlite3").read_bytes())
        self.assertEqual(original_snapshots, [(self.parent / name / "snapshot.sqlite3").read_bytes()
                         for name in ("historical-v1-backup", "historical-v2-backup")])
