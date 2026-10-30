"""Synthetic administrative-format consistency; these tests do not execute migration."""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.backup import BackupError, create_backup, inspect_backup, restore_backup
from research_pipeline.store import RecordStore, StoreLayoutError
from tests import test_backup
from tests.legacy import canonical, historical_store, historical_backup, table_values
from tests.test_store import CREATOR, record, request


class HistoryTests(unittest.TestCase):
    """Verify explicitly synthetic history independently of the future migration operation."""

    def setUp(self):
        """Construct a real legacy source manifest and a separately populated fresh v2 store."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        legacy, _, self.artifact = historical_store(self.parent / "legacy")
        legacy.close()
        self.manifest, identity = historical_backup(self.parent / "legacy", self.parent / "legacy-backup")
        self.root = self.parent / "v2"
        with RecordStore.create(self.root) as store:
            copied = store.put_artifact(b"independent historical graph bytes\n")
            store.submit(request("synthetic", [record(artifact_references=[copied])]))
        self.row = (1, 1, 2, identity, canonical(self.manifest), canonical(CREATOR.to_dict()))

    def insert(self, root, rows):
        """Write deliberately synthetic rows with CHECK bypass only for malformed-row fixtures."""
        with sqlite3.connect(root / "metadata.sqlite3") as connection:
            connection.execute("PRAGMA ignore_check_constraints=ON")
            connection.execute("DELETE FROM migration_history")
            connection.executemany("INSERT INTO migration_history VALUES (?,?,?,?,?,?)", rows)

    def history(self, root, filename="metadata.sqlite3"):
        """Read exact administrative values without normalizing their text or attribution."""
        connection = sqlite3.connect((root / filename).as_uri() + "?mode=ro", uri=True)
        try:
            return connection.execute("SELECT * FROM migration_history").fetchall()
        finally:
            connection.close()

    def test_empty_and_synthetic_history_exact_backup_restore(self):
        """Fresh creation invents no history; a consistent synthetic row survives exact copies."""
        self.assertEqual(self.history(self.root), [])
        with RecordStore.open(self.root) as store:
            create_backup(store, self.parent / "empty-history")
        self.assertEqual(self.history(self.parent / "empty-history", "snapshot.sqlite3"), [])
        with restore_backup(self.parent / "empty-history", self.parent / "empty-restored"):
            self.assertEqual(self.history(self.parent / "empty-restored"), [])
        self.insert(self.root, [self.row])
        original = table_values(self.root)
        with RecordStore.open(self.root) as store:
            artifact = store.put_artifact(b"later append")
            store.submit(request("later", [record("later", artifact_references=[artifact])]))
            info = create_backup(store, self.parent / "history-backup")
        self.assertEqual(self.history(self.parent / "history-backup", "snapshot.sqlite3"), [self.row])
        with restore_backup(self.parent / "history-backup", self.parent / "restored") as store:
            self.assertEqual(self.history(self.parent / "restored"), [self.row])
            self.assertEqual(table_values(self.root), table_values(self.parent / "restored"))
            self.assertEqual(store.get_submission("synthetic").submission_id, "synthetic")
            self.assertEqual(len(store.audit_events()), 2)
        self.assertEqual(inspect_backup(self.parent / "history-backup"), info)
        self.assertEqual(len(original["audit_events"]), 1)
        output = test_backup.BackupTests.child(self, '''
import sys
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    assert store._schema_version == 2
    assert len(store.audit_events()) == 2
    print(store.get_submission("synthetic").submission_id)
''', self.parent / "restored")
        self.assertEqual(output.strip(), "synthetic")

    def invalid_rows(self):
        """Enumerate structural, identity, strict JSON, canonical-time and inventory corruption."""
        rows = []
        for index, value in ((0, 2), (1, 2), (2, 1), (1, "bad"), (2, 2.5),
                             (3, "A" * 64), (3, "0" * 64), (4, "{}"), (4, "{"),
                             (4, '{"x":1,"x":2}'), (5, "{}"), (5, "[]"),
                             (5, '{"actor":"a","created_at":"2026-10-30T00:00:00Z","details":{"x":NaN}}')):
            row = list(self.row)
            row[index] = value
            rows.append(row)
        for provenance in ({"actor": "a", "created_at": "2026-10-30T00:00:00.000000Z"},
                           {**CREATOR.to_dict(), "created_at": "2026-10-30T00:00:00Z"},
                           {**CREATOR.to_dict(), "created_at": "2026-02-30T00:00:00.000000Z"},
                           {**CREATOR.to_dict(), "details": {"x": float("inf")}}):
            rows.append([*self.row[:5], json.dumps(provenance, sort_keys=True, separators=(",", ":"))])
        rows.append([*self.row[:5], canonical(CREATOR.to_dict()).replace('"actor":', '"actor":"duplicate","actor":')])
        rows.append([*self.row[:5], canonical(CREATOR.to_dict()) + "\n"])
        rows.append([*self.row[:4], self.row[4] + "\n", self.row[5]])
        for field, value in (("digest", "b" * 64), ("size", self.manifest["metadata"]["size"] + 1),
                             ("digest", "../invalid"), ("size", True), ("size", -1), ("size", 2.0)):
            document = {**self.manifest, "metadata": {**self.manifest["metadata"], field: value}}
            # Keep the old identity: even structurally valid digest/size changes must disagree.
            rows.append([*self.row[:4], canonical(document), self.row[5]])
        for change in ({"format_version": 2, "schema_version": 2}, {"extra": 1},
                       {"artifacts": [self.artifact.to_dict(), self.artifact.to_dict()]},
                       {"artifacts": [{"digest": "a" * 64, "size": 1}]},
                       {"artifacts": [{"digest": self.artifact.digest, "size": self.artifact.size + 1}]},
                       {"artifacts": sorted([self.artifact.to_dict(), {"digest": "a" * 64, "size": 1}],
                                            key=lambda value: value["digest"], reverse=True)}):
            document = {**self.manifest, **change}
            text = canonical(document)
            rows.append([*self.row[:3], hashlib.sha256(text.encode()).hexdigest(), text, self.row[5]])
        rows.append([*self.row[:4], self.row[4].replace('"format_version":1', '"format_version":1,"format_version":1'), self.row[5]])
        return rows

    def test_malformed_history_rejected_on_open_and_rehashed_snapshot(self):
        """Substantive history validation rejects corruption even when outer hashes are updated."""
        self.insert(self.root, [self.row])
        with RecordStore.open(self.root) as store:
            create_backup(store, self.parent / "baseline")
        for index, rows in enumerate([[row] for row in self.invalid_rows()] + [[self.row, (2, *self.row[1:])]]):
            with self.subTest(index=index):
                self.insert(self.root, rows)
                before = (self.root / "metadata.sqlite3").read_bytes()
                with self.assertRaises(StoreLayoutError):
                    RecordStore.open(self.root)
                self.assertEqual((self.root / "metadata.sqlite3").read_bytes(), before)
                damaged = Path(shutil.copytree(self.parent / "baseline", self.parent / f"damaged-{index}"))
                path = damaged / "snapshot.sqlite3"
                path.chmod(0o600)
                with sqlite3.connect(path) as connection:
                    connection.execute("PRAGMA ignore_check_constraints=ON")
                    connection.execute("DELETE FROM migration_history")
                    connection.executemany("INSERT INTO migration_history VALUES (?,?,?,?,?,?)", rows)
                path.chmod(0o400)
                document = json.loads((damaged / "manifest.json").read_text())
                data = path.read_bytes()
                document["metadata"] = {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}
                manifest_path = damaged / "manifest.json"
                manifest_path.chmod(0o600)
                manifest_path.write_text(canonical(document))
                manifest_path.chmod(0o400)
                with self.assertRaises(BackupError):
                    inspect_backup(damaged)
                target = self.parent / f"rejected-{index}"
                with self.assertRaises(BackupError):
                    restore_backup(damaged, target)
                self.assertFalse(target.exists())

    def test_history_is_validated_after_hot_journal_recovery(self):
        """An uncommitted spilled history edit rolls back before administrative validation."""
        self.insert(self.root, [self.row])
        test_backup.BackupTests.child(self, '''
import os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1] + "/metadata.sqlite3")
connection.execute("PRAGMA cache_size=1")
connection.execute("PRAGMA synchronous=EXTRA")
connection.execute("BEGIN IMMEDIATE")
connection.execute("UPDATE migration_history SET provenance_json=?", ('x' * 2000000,))
os._exit(73)
''', self.root, expected=73)
        self.assertTrue((self.root / "metadata.sqlite3-journal").exists())
        with RecordStore.open(self.root) as store:
            self.assertEqual(self.history(self.root), [self.row])
            self.assertEqual(store.get_submission("synthetic").submission_id, "synthetic")
