"""Verified legacy migration, exact history, actual interruption and continued-use evidence."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import backup
from research_pipeline.backup import (
    BackupError, BackupLayoutError, BackupOperationalError,
    create_backup, inspect_backup, restore_backup,
)
from research_pipeline.domain import CreationProvenance
from research_pipeline.schema import _VERSIONS
from research_pipeline.store import RecordStore
from tests import test_backup, test_schema_history
from tests.legacy import LEGACY_DDL, canonical, create_legacy, historical_store, historical_backup, table_values
from tests.test_store import record, request


ATTRIBUTION = CreationProvenance("synthetic-migration-operator", "2026-10-30T14:00:00Z", {})


class MigrationTests(unittest.TestCase):
    """Exercise the sole explicit transition on independently constructed historical databases."""

    child = test_backup.BackupTests.child
    history = test_schema_history.HistoryTests.history
    insert = test_schema_history.HistoryTests.insert
    invalid_rows = test_schema_history.HistoryTests.invalid_rows

    def setUp(self):
        """Build authentic v1 graphs and a format-1 backup outside candidate source."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.source_root = self.parent / "legacy"
        self.source, self.requests, self.artifact = historical_store(self.source_root)
        self.addCleanup(self.source.close)
        self.backup_root = self.parent / "legacy-backup"
        self.manifest, identity = historical_backup(self.source_root, self.backup_root)
        self.row = (1, 1, 2, identity, canonical(self.manifest), canonical(ATTRIBUTION.to_dict()))
        self.root = self.parent / "migrated"

    def files(self, root):
        """Snapshot directory names and file bytes without opening SQLite or recovering journals."""
        return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                for path in root.rglob("*")}

    def migrate(self, destination=None):
        """Return an explicitly upgraded handle using fixed synthetic caller attribution."""
        return restore_backup(self.backup_root, destination or self.root,
                              target_schema=2, migration_provenance=ATTRIBUTION)

    def assert_schema(self, root, version):
        """Inspect committed test metadata for exact DDL, version and resolved foreign keys."""
        connection = sqlite3.connect((root / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (version,))
            statements = connection.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
            expected = LEGACY_DDL if version == 1 else _VERSIONS[2][0]
            self.assertEqual({" ".join(row[0].split()) for row in statements},
                             {" ".join(sql.split()) for sql in expected})
            self.assertEqual(len(statements), len(expected))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()

    def refuse_in_fresh_process(self, root):
        """Require both public gates to reject retained files without recovery or mutation."""
        before = self.files(root)
        self.child('''
import sys
from research_pipeline.backup import inspect_backup, BackupError
from research_pipeline.store import RecordStore, StoreLayoutError
for action, error in ((RecordStore.open, StoreLayoutError), (inspect_backup, BackupError)):
    try:
        action(sys.argv[1])
    except error:
        pass
    else:
        raise AssertionError("incomplete migration accepted")
''', root)
        self.assertEqual(self.files(root), before)

    def test_preservation_fresh_process_retries_appends_and_exact_export(self):
        """Preserve every historical SQL/public value, then continue independently in a new process."""
        original = table_values(self.source_root)
        source_before, backup_before = self.files(self.source_root), self.files(self.backup_root)
        receipts = [self.source.get_submission(item.submission_id) for item in self.requests]
        with self.migrate() as store:
            self.assertEqual(table_values(self.root), original)
            self.assertEqual(self.history(self.root), [self.row])
            self.assertEqual(store.audit_events(), self.source.audit_events())
            self.assertEqual([event.event_id for event in store.audit_events()], [11, 22, 33, 44, 55])
            for identity, _, _ in original["identities"]:
                self.assertEqual(store.history(identity), self.source.history(identity))
                self.assertEqual(store.head(identity), self.source.head(identity))
            for item in self.requests[2].records + self.requests[3].records:
                self.assertEqual(store.get_typed_revision(item.record_id, item.revision),
                                 self.source.get_typed_revision(item.record_id, item.revision))
            for item, receipt in zip(self.requests, receipts):
                self.assertEqual(store.get_submission(item.submission_id), receipt)
            self.assertEqual(store._connection.execute("PRAGMA foreign_keys").fetchone(), (1,))
        self.assert_schema(self.root, 2)
        self.assertNotEqual((self.root / "metadata.sqlite3").read_bytes(), backup_before["snapshot.sqlite3"])
        for first, second in ((self.source_root / "metadata.sqlite3", self.backup_root / "snapshot.sqlite3"),
                              (self.backup_root / "snapshot.sqlite3", self.root / "metadata.sqlite3"),
                              (self.source_root / "objects" / self.artifact.digest, self.backup_root / "objects" / self.artifact.digest),
                              (self.backup_root / "objects" / self.artifact.digest, self.root / "objects" / self.artifact.digest)):
            self.assertNotEqual(first.stat().st_ino, second.stat().st_ino)
        self.child('''
import json, sys
from research_pipeline.backup import create_backup, inspect_backup
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.store import RecordStore
requests = [Submission.from_dict(item) for item in json.loads(sys.argv[2])]
with RecordStore.open(sys.argv[1]) as store:
    events = store.audit_events()
    assert store.get_revision("g-context", 1) == requests[0].records[-1]
    for item in requests[2].records + requests[3].records:
        assert store.get_typed_revision(item.record_id, item.revision)[0] == item
    for item in requests:
        assert store.submit(item) == store.get_submission(item.submission_id)
    assert store.submit_typed(requests[2]) == store.get_submission("legacy-typed")
    assert store.audit_events() == events
    p = CreationProvenance("continued-synthetic-author", "2026-10-30T15:00:00Z")
    artifact = store.put_artifact(b"new registration after migration")
    item = RecordEnvelope("project", 1, "project", {}, p,
                          record_references=[RecordReference("project", 1, "self", "project")],
                          artifact_references=[artifact])
    store.submit(Submission("new-kind", p, [item], {"project": 0}))
    next_item = RecordEnvelope("g-context", 3, "research_context", {"later": True}, p)
    store.submit(Submission("later-revision", p, [next_item], {"g-context": 2}))
    info = create_backup(store, sys.argv[3])
    assert (info.format_version, info.schema_version) == (2, 2)
assert inspect_backup(sys.argv[3]) == info
''', self.root, json.dumps([item.to_dict() for item in self.requests]), self.parent / "v2-backup")
        with restore_backup(self.parent / "v2-backup", self.parent / "exact") as exact:
            self.assertEqual(self.history(self.parent / "exact"), [self.row])
            self.assertEqual(table_values(self.parent / "exact"), table_values(self.root))
            self.assertEqual((self.parent / "exact" / "metadata.sqlite3").read_bytes(),
                             (self.parent / "v2-backup" / "snapshot.sqlite3").read_bytes())
            for item, receipt in zip(self.requests, receipts):
                self.assertEqual(exact.submit(item), receipt)
            self.assertEqual(exact.submit_typed(self.requests[2]), receipts[2])
            self.assertEqual(exact.head("project"), 1)
            self.assertEqual(exact.head("g-context"), 3)
        for item, receipt in zip(self.requests, receipts):
            self.assertEqual(self.source.submit(item), receipt)
        self.assertEqual(self.source.submit_typed(self.requests[2]), receipts[2])
        exported = create_backup(self.source, self.parent / "still-v1")
        self.assertEqual((exported.format_version, exported.schema_version), (1, 1))
        self.assertEqual(self.files(self.source_root), source_before)
        self.assertEqual(self.files(self.backup_root), backup_before)

    def test_empty_legacy_zero_byte_object_and_canonical_manifest(self):
        """Empty stores migrate; zero-byte objects and noncanonical outer whitespace retain identity."""
        for populated in (False, True):
            root = self.parent / f"empty-{populated}"
            with create_legacy(root) as store:
                if populated:
                    artifact = store.put_artifact(b"")
                    store.submit(request("zero", [record(artifact_references=[artifact])]))
                exported = self.parent / f"empty-backup-{populated}"
                info = create_backup(store, exported)
            path = exported / "manifest.json"
            document = json.loads(path.read_text())
            path.chmod(0o600)
            path.write_text(json.dumps(document, indent=4))
            path.chmod(0o400)
            before = self.files(exported)
            destination = self.parent / f"empty-migrated-{populated}"
            with restore_backup(exported, destination, target_schema=2, migration_provenance=ATTRIBUTION) as store:
                self.assertEqual(table_values(destination), table_values(root))
                self.assertEqual(self.history(destination), [(1, 1, 2, info.backup_id,
                                                             canonical(document), canonical(ATTRIBUTION.to_dict()))])
                if populated:
                    self.assertEqual(store.read_artifact(artifact), b"")
                else:
                    self.assertEqual(store.audit_events(), ())
            self.assertEqual(self.files(exported), before)

    def test_invalid_options_and_forged_attribution_do_not_reserve(self):
        """Reject every unsupported target/provenance combination, including forged frozen fields."""
        with RecordStore.create(self.parent / "fresh-v2") as store:
            create_backup(store, self.parent / "v2-backup")
        with self.migrate():
            pass
        with RecordStore.open(self.root) as store:
            create_backup(store, self.parent / "migrated-backup")
        sources = (self.backup_root, self.parent / "v2-backup", self.parent / "migrated-backup")
        before = [self.files(root) for root in sources]
        invalid_provenances = [None, {}, ATTRIBUTION.to_dict(), "operator", True]
        for name, value in (("actor", ""), ("actor", 1), ("created_at", None),
                            ("created_at", "2026-02-30T00:00:00Z"), ("_details_json", "[]"),
                            ("_details_json", '{"x":NaN}'), ("_details_json", '{"x":1,"x":2}')):
            forged = CreationProvenance("operator", "2026-10-30T00:00:00Z")
            object.__setattr__(forged, name, value)
            invalid_provenances.append(forged)
        invalid_provenances.append(object.__new__(CreationProvenance))
        cases = [(target, provenance) for target in (True, False, "2", 2.0, 0, 1, 3, 4, -1, [], {})
                 for provenance in (None, ATTRIBUTION)]
        cases += [(None, provenance) for provenance in invalid_provenances[1:] + [ATTRIBUTION]]
        cases += [(2, provenance) for provenance in invalid_provenances]
        for source_index, source in enumerate(sources):
            # Genuine attributed 2→3 transitions now have positive schema3 coverage.
            source_cases = [(target, provenance) for target, provenance in cases
                            if not (source_index and target == 3 and provenance is ATTRIBUTION)]
            source_cases += ([(2, ATTRIBUTION)] if source_index else [])
            source_cases += [(3, provenance) for provenance in invalid_provenances]
            for index, (target, provenance) in enumerate(source_cases):
                destination = self.parent / f"invalid-{source_index}-{index}"
                with self.subTest(source=source_index, case=index), self.assertRaisesRegex(BackupLayoutError, "schema 1 to schema 2"):
                    restore_backup(source, destination, target_schema=target, migration_provenance=provenance)
                self.assertFalse(destination.exists())
        self.assertEqual([self.files(root) for root in sources], before)

    def test_damaged_source_and_unsafe_destinations_remain_untouched(self):
        """Full source verification precedes reservation, and no migration bypasses path exclusions."""
        source_before = self.files(self.source_root)
        backup_before = self.files(self.backup_root)
        for index, relative in enumerate(("snapshot.sqlite3", "objects/" + self.artifact.digest)):
            damaged = Path(shutil.copytree(self.backup_root, self.parent / f"damaged-{index}"))
            path = damaged / relative
            path.chmod(0o600)
            path.write_bytes(b"corrupt")
            path.chmod(0o400)
            before = self.files(damaged)
            target = self.parent / f"rejected-{index}"
            with self.assertRaises(BackupError):
                restore_backup(damaged, target, target_schema=2, migration_provenance=ATTRIBUTION)
            self.assertFalse(target.exists())
            self.assertEqual(self.files(damaged), before)
        sentinel = self.parent / "sentinel"
        sentinel.write_bytes(b"untouched")
        existing = self.parent / "existing"
        existing.mkdir()
        link = self.parent / "link"
        link.symlink_to(sentinel)
        dangling = self.parent / "dangling"
        dangling.symlink_to(self.parent / "absent")
        ancestor = self.parent / "alias"
        ancestor.symlink_to(self.parent, target_is_directory=True)
        for target in (sentinel, existing, link, dangling):
            inode = target.lstat().st_ino
            with self.assertRaises(BackupError):
                self.migrate(target)
            self.assertEqual(target.lstat().st_ino, inode)
        for target in (self.backup_root / "nested", ancestor / "unsafe", self.parent / "unused" / ".." / "traversal"):
            with self.assertRaises(BackupError):
                self.migrate(target)
            self.assertFalse(target.exists())
        self.assertFalse((self.parent / "unsafe").exists())
        self.assertEqual(sentinel.read_bytes(), b"untouched")
        self.assertEqual(self.files(self.source_root), source_before)
        self.assertEqual(self.files(self.backup_root), backup_before)

    def test_genuine_migration_history_corruption_with_rehashed_backups(self):
        """Apply the full malformed-history matrix to real migration and rehashed v2 snapshots."""
        with self.migrate() as store:
            create_backup(store, self.parent / "baseline")
        # Reuse the accepted structural/canonical/identity/inventory corruption
        # matrix, now starting from an actually migrated historical graph.
        for index, rows in enumerate([[row] for row in self.invalid_rows()] + [[self.row, (2, *self.row[1:])]]):
            with self.subTest(index=index):
                self.insert(self.root, rows)
                before = self.files(self.root)
                from research_pipeline.store import StoreLayoutError
                with self.assertRaises(StoreLayoutError):
                    RecordStore.open(self.root)
                self.assertEqual(self.files(self.root), before)
                damaged = Path(shutil.copytree(self.parent / "baseline", self.parent / f"history-{index}"))
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
                manifest = damaged / "manifest.json"
                manifest.chmod(0o600)
                manifest.write_text(canonical(document))
                manifest.chmod(0o400)
                before = self.files(damaged)
                with self.assertRaises(BackupError):
                    inspect_backup(damaged)
                destination = self.parent / f"history-rejected-{index}"
                with self.assertRaises(BackupError):
                    restore_backup(damaged, destination)
                self.assertFalse(destination.exists())
                self.assertEqual(self.files(damaged), before)

    def test_mid_transform_exception_rolls_back_private_copy(self):
        """A caught fault after actual DDL restores all original v1 tables but retains the marker."""
        before_source, before_backup = self.files(self.source_root), self.files(self.backup_root)

        def fail(point):
            """Raise only after the old tables and trigger have actually been dropped."""
            if point == "migration_transform":
                raise OSError("mid-transform failure")

        with patch.object(backup, "_fault", side_effect=fail):
            with self.assertRaisesRegex(BackupOperationalError, "mid-transform failure"):
                self.migrate()
        self.assertTrue((self.root / ".restore-incomplete").is_file())
        self.assert_schema(self.root, 1)
        self.assertEqual(table_values(self.root), table_values(self.source_root))
        self.refuse_in_fresh_process(self.root)
        self.assertEqual(self.files(self.source_root), before_source)
        self.assertEqual(self.files(self.backup_root), before_backup)

    def test_abrupt_transform_commit_and_prepublication_refuse_without_recovery(self):
        """Abrupt exits retain real work/journals; fresh public opens never recover incomplete copies."""
        before_source, before_backup = self.files(self.source_root), self.files(self.backup_root)
        for boundary in ("migration_transform", "migration_committed", "before_publication"):
            target = self.parent / boundary
            self.child('''
import os, sys
from research_pipeline import backup
from research_pipeline.domain import CreationProvenance
def crash(point):
    """Terminate at a real transformation or publication boundary without Python cleanup."""
    if point == sys.argv[3]:
        os._exit(73)
backup._fault = crash
backup.restore_backup(sys.argv[1], sys.argv[2], target_schema=2,
                      migration_provenance=CreationProvenance("operator", "2026-10-30T14:00:00Z"))
''', self.backup_root, target, boundary, expected=73)
            self.assertTrue((target / ".restore-incomplete").is_file())
            self.assertEqual((target / "objects" / self.artifact.digest).read_bytes(),
                             (self.backup_root / "objects" / self.artifact.digest).read_bytes())
            self.assertGreater((target / "metadata.sqlite3").stat().st_size, 0)
            if boundary == "migration_transform":
                # Do not open this database through SQLite: preserve crash evidence.
                self.assertTrue((target / "metadata.sqlite3-journal").is_file())
            else:
                self.assert_schema(target, 2)
                self.assertEqual(table_values(target), table_values(self.source_root))
            self.refuse_in_fresh_process(target)
        self.assertEqual(self.files(self.source_root), before_source)
        self.assertEqual(self.files(self.backup_root), before_backup)

    def test_migrated_sync_removal_and_publication_failures(self):
        """Fail real inode-selected barriers after transformation, retaining truthful publication state."""
        before_source, before_backup = self.files(self.source_root), self.files(self.backup_root)
        sentinel = self.parent / "sentinel"
        sentinel.write_bytes(b"unchanged")
        original_sync, original_unlink = os.fsync, os.unlink
        for mode in ("metadata", "directory", "remove", "final-directory", "final-parent", "after-publication", "committed"):
            target = self.parent / mode
            marker = target / ".restore-incomplete"
            committed = []
            failures = []

            def boundary(point):
                """Arm OS failures only after the real migration COMMIT, or fail its acknowledgment."""
                if point == "migration_committed":
                    committed.append(point)
                if ((mode == "committed" and point == "migration_committed")
                        or (mode == "after-publication" and point == "after_publication")):
                    failures.append(point)
                    raise OSError("migration boundary failure")

            def sync(descriptor):
                """Select metadata or directory inodes after transformation and at the correct marker state."""
                if committed and mode in ("metadata", "directory", "final-directory", "final-parent"):
                    selected = (target / "metadata.sqlite3" if mode == "metadata" else
                                target.parent if mode == "final-parent" else target)
                    info, expected = os.fstat(descriptor), selected.stat()
                    if ((info.st_dev, info.st_ino) == (expected.st_dev, expected.st_ino)
                            and (not mode.startswith("final-") or not marker.exists())):
                        failures.append(mode)
                        raise OSError("migration synchronization failure")
                original_sync(descriptor)

            def unlink(name, *args, **kwargs):
                """Fail only the final incomplete marker removal, retaining ordinary copy operations."""
                if mode == "remove" and str(name) == ".restore-incomplete":
                    self.assertTrue(committed)
                    failures.append(mode)
                    raise OSError("migration marker removal failure")
                return original_unlink(name, *args, **kwargs)

            with patch.object(backup, "_fault", side_effect=boundary), patch.object(os, "fsync", side_effect=sync), patch.object(os, "unlink", side_effect=unlink):
                with self.assertRaises(BackupOperationalError) as caught:
                    self.migrate(target)
            self.assertEqual(len(committed), 1)
            self.assertEqual(len(failures), 1)
            self.assert_schema(target, 2)
            self.assertEqual(table_values(target), table_values(self.source_root))
            if mode.startswith("final-") or mode == "after-publication":
                self.assertIn("uncertain", str(caught.exception))
                self.assertFalse(marker.exists())
                with RecordStore.open(target) as store:
                    self.assertEqual(store.audit_events(), self.source.audit_events())
            else:
                self.assertTrue(marker.exists())
                self.refuse_in_fresh_process(target)
        self.assertEqual(sentinel.read_bytes(), b"unchanged")
        self.assertEqual(self.files(self.source_root), before_source)
        self.assertEqual(self.files(self.backup_root), before_backup)

    def test_v1_lost_commit_acknowledgment_survives_migration_and_exact_restore(self):
        """Carry an actual v1 post-COMMIT crash identity through explicit migration and v2 export."""
        initial = request("lost-ack", [record("lost", artifact_references=[self.artifact])])
        self.source.close()
        self.child('''
import json, os, sys
from research_pipeline import store
from research_pipeline.domain import Submission
def crash(point):
    """Exit after the durable v1 submission COMMIT before receipt delivery."""
    if point == "after_commit":
        os._exit(74)
store._fault = crash
with store.RecordStore.open(sys.argv[1]) as source:
    assert source._schema_version == 1
    source.submit(Submission.from_dict(json.loads(sys.argv[2])))
''', self.source_root, json.dumps(initial.to_dict()), expected=74)
        with RecordStore.open(self.source_root) as source:
            receipt = source.get_submission("lost-ack")
            self.assertIsNotNone(receipt)
            events = source.audit_events()
            self.assertEqual(source.submit(initial), receipt)
            info = create_backup(source, self.parent / "lost-backup")
            self.assertEqual((info.format_version, info.schema_version), (1, 1))
        before_source = self.files(self.source_root)
        before_backup = self.files(self.parent / "lost-backup")
        with restore_backup(self.parent / "lost-backup", self.root, target_schema=2, migration_provenance=ATTRIBUTION) as store:
            self.assertEqual(store.get_submission("lost-ack"), receipt)
            self.assertEqual(store.submit(initial), receipt)
            self.assertEqual(store.audit_events(), events)
            create_backup(store, self.parent / "lost-v2")
        with restore_backup(self.parent / "lost-v2", self.parent / "lost-exact") as store:
            self.assertEqual(store.get_submission("lost-ack"), receipt)
            self.assertEqual(store.submit(initial), receipt)
            self.assertEqual(store.audit_events(), events)
            self.assertEqual(self.history(self.parent / "lost-exact"), self.history(self.root))
        self.assertEqual(self.files(self.source_root), before_source)
        self.assertEqual(self.files(self.parent / "lost-backup"), before_backup)

    def test_documented_migration_example(self):
        """Execute the exact synthetic documentation block in a bounded process outside source."""
        implementation = Path(__file__).resolve().parents[1]
        document = (implementation.parent / "docs" / "backups.md").read_text()
        section = document.split("## Runnable synthetic migration example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=self.parent,
                                env={**os.environ, "PYTHONPATH": os.pathsep.join((str(implementation / "src"), str(implementation))),
                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
