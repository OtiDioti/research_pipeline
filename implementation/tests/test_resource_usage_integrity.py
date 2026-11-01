"""Rehashed live/immutable histories must retain evidence identity and historical admission semantics."""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.backup import BackupError, create_backup, inspect_backup, restore_backup
from research_pipeline.resources import ResourceRequest, canonical
from research_pipeline.store import RecordStore, StoreLayoutError
from tests.resource_fixtures import LIMITS, observation, populate, reconciliation, reservation, vector
from tests.test_resource_schema import rehash_backup
from tests.test_vault import restore_directories


def rewrite_operation(connection, operation_id, edit):
    """Rehash an intentionally corrupted request/result pair to exercise semantic replay, not outer hashes."""
    text, result = connection.execute("SELECT request_json,result_json FROM resource_operations WHERE operation_id=?", (operation_id,)).fetchone()
    doc, receipt = json.loads(text), json.loads(result)
    edit(doc)
    text = canonical(doc)
    digest = hashlib.sha256(text.encode()).hexdigest()
    receipt["request_fingerprint"] = digest
    connection.execute("UPDATE resource_operations SET request_json=?,fingerprint=?,result_json=? WHERE operation_id=?",
                       (text, digest, canonical(receipt), operation_id))


class UsageIntegrityTests(unittest.TestCase):
    """Validate closed replay invariants independently of a writable owner's recomputed byte hashes."""

    def test_rehashed_usage_settlement_and_historical_breach_tampering(self):
        """Live open and immutable inspection reject contradictory evidence and admissions after a past breach."""
        with TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.addCleanup(restore_directories, parent)
            root, exported = parent / "runtime", parent / "backup"
            with RecordStore.create(root, schema_version=3) as store:
                populate(store, attempts=2)
                store.reserve_resources(reservation(maxima=vector(tool_calls=10)))
                partial = observation(usage=vector(None, tool_calls=4)).to_dict()
                partial["evidence_references"] = [
                    {"record_id": "project", "revision": 1, "relationship": "resource_evidence", "target_kind": "project"},
                    {"record_id": "task", "revision": 1, "relationship": "resource_evidence", "target_kind": "task_specification"}]
                store.observe_resource_usage(ResourceRequest.from_dict(partial))
                store.observe_resource_usage(observation("complete", event="authoritative_completion", usage=vector(tool_calls=6)))
                store.reconcile_resource_usage(reconciliation())
                store.reserve_resources(reservation("later"))
                snapshot = store.inspect_resources(limits=LIMITS)
                create_backup(store, exported)
            modes = ("source_identity", "foreign_reservation", "reference_order", "predecessor", "settlement_evidence",
                     "nonmonotone", "historical_breach", "unknown_field", "evidence_watermark")
            for mode in modes:
                candidate = parent / ("live_" + mode)
                shutil.copytree(root, candidate)
                with sqlite3.connect(candidate / "metadata.sqlite3") as connection:
                    def edit(doc):
                        """Change one semantic constraint while retaining complete request and receipt hashes."""
                        p = doc["payload"]
                        if mode == "source_identity":
                            p["evidence"]["source_receipt_id"] = "external_partial"
                        elif mode == "foreign_reservation":
                            p["account_id"] = "attempt2"
                        elif mode == "predecessor":
                            p["previous_reconciliation_operation_id"] = "op_missing"
                        elif mode == "settlement_evidence":
                            p["observation_operation_id"] = "op_partial"
                        elif mode in ("nonmonotone", "historical_breach"):
                            for dimension in p["usage"]:
                                if dimension["dimension_id"] == "dim_tool_calls":
                                    dimension["quantity"] = 3 if mode == "nonmonotone" else 26
                        elif mode == "unknown_field":
                            p["evidence"]["authenticated"] = True
                    if mode == "reference_order":
                        connection.execute("UPDATE resource_record_links SET ordinal=ordinal+10 WHERE operation_id='op_partial'")
                        connection.execute("UPDATE resource_record_links SET ordinal=11-ordinal WHERE operation_id='op_partial'")
                    elif mode == "evidence_watermark":
                        result = json.loads(connection.execute("SELECT result_json FROM resource_operations WHERE operation_id='op_partial'").fetchone()[0])
                        result["scientific_watermark_event_id"] = 0
                        connection.execute("UPDATE resource_operations SET result_json=? WHERE operation_id='op_partial'", (canonical(result),))
                    else:
                        operation_id = "op_settlement" if mode in ("predecessor", "settlement_evidence") else "op_complete"
                        rewrite_operation(connection, operation_id, edit)
                        if mode == "historical_breach":
                            rewrite_operation(connection, "op_partial", edit)
                with self.subTest(live=mode), self.assertRaises(StoreLayoutError):
                    RecordStore.open(candidate)
                damaged = parent / ("backup_" + mode)
                shutil.copytree(exported, damaged)
                database = damaged / "snapshot.sqlite3"
                database.chmod(0o600)
                database.write_bytes((candidate / "metadata.sqlite3").read_bytes())
                database.chmod(0o400)
                rehash_backup(damaged)
                with self.subTest(backup=mode), self.assertRaises(BackupError):
                    inspect_backup(damaged)
                destination = parent / ("refused_" + mode)
                with self.assertRaises(BackupError):
                    restore_backup(damaged, destination)
                self.assertFalse(destination.exists())
            with RecordStore.open(root) as store:
                self.assertEqual(store.inspect_resources(limits=LIMITS), snapshot)

    def test_exact_retry_checks_saved_result_identity_before_returning(self):
        """A damaged saved observation/settlement receipt cannot be returned as an exact retry on a live handle."""
        from research_pipeline.resources import ResourceIntegrityError
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            with RecordStore.create(root, schema_version=3) as store:
                populate(store)
                store.reserve_resources(reservation())
                complete = observation("complete", event="authoritative_completion")
                settled = reconciliation()
                for item, method in ((complete, store.observe_resource_usage), (settled, store.reconcile_resource_usage)):
                    receipt = method(item)
                    original = store._connection.execute("SELECT result_json FROM resource_operations WHERE operation_id=?", (item.operation_id,)).fetchone()[0]
                    for field in ("operation_id", "receipt_id", "account_id", "reservation_id", "request_fingerprint"):
                        damaged = receipt.to_dict()
                        damaged[field] = "0" * 64 if field == "request_fingerprint" else "foreign_identity"
                        store._connection.execute("UPDATE resource_operations SET result_json=? WHERE operation_id=?",
                                                  (canonical(damaged), item.operation_id))
                        before = (root / "metadata.sqlite3").read_bytes()
                        with self.subTest(kind=item.to_dict()["kind"], field=field), self.assertRaises(ResourceIntegrityError):
                            method(item)
                        self.assertEqual((root / "metadata.sqlite3").read_bytes(), before)
                        store._connection.execute("UPDATE resource_operations SET result_json=? WHERE operation_id=?", (original, item.operation_id))
                    self.assertEqual(method(item), receipt)
