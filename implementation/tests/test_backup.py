"""Real snapshot, independent restore, corruption and publication recovery evidence."""

from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import backup
from research_pipeline.backup import (
    BackupError, BackupIntegrityError, BackupLayoutError, BackupOperationalError,
    create_backup, inspect_backup, restore_backup,
)
from research_pipeline.domain import Submission, RecordReference
from research_pipeline.store import RecordStore, StoreClosedError, StoreLayoutError, SubmissionConflictError
from tests.test_store import graph, record, request


class BackupTests(unittest.TestCase):
    """Exercise actual SQLite and private files through bounded candidate-source processes."""

    def setUp(self):
        """Create isolated explicit paths and one source handle per case."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "source #? ü"
        self.destination = self.parent / "backup #? ü"
        self.restored = self.parent / "restored #? ü"
        self.source = RecordStore.create(self.root)
        self.addCleanup(self.source.close)

    def child(self, program, *arguments, expected=0):
        """Run a bounded interpreter with candidate-first imports and checked exit status."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source),
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def populate(self):
        """Commit a synthetic graph and historical-only artifact with advanced heads."""
        artifact = self.source.put_artifact(b"historical adjacency")
        first = request(records=graph(artifact))
        receipt = self.source.submit(first)
        self.source.submit(request("advance-evidence", [record("evidence", 2, "evidence")], {"evidence": 1}))
        self.source.submit(request("history", [record("context", 2, record_references=[
            RecordReference("evidence", 1, "historical", "evidence")])], {"context": 1}))
        return artifact, first, receipt

    def files(self, root):
        """Record regular file bytes and relative names to detect unexpected mutation."""
        return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    def rewrite(self, path, data):
        """Mutate a disposable owned test file, then restore its read-only protection."""
        path.chmod(0o600)
        path.write_bytes(data)
        path.chmod(0o400)

    def damaged_copy(self, name):
        """Make an independent disposable backup copy for a single corruption scenario."""
        return Path(shutil.copytree(self.destination, self.parent / name))

    def manifest(self, root, document):
        """Write a tampered manifest while preserving the file's required protection."""
        self.rewrite(root / "manifest.json", json.dumps(document).encode())

    def mutate_database(self, root, sql):
        """Tamper with actual SQLite rows, then recompute the outer metadata reference."""
        path = root / "snapshot.sqlite3"
        path.chmod(0o600)
        connection = sqlite3.connect(path)
        try:
            connection.executescript(sql)
            connection.commit()
        finally:
            connection.close()
        path.chmod(0o400)
        document = json.loads((root / "manifest.json").read_text())
        data = path.read_bytes()
        document["metadata"] = {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}
        self.manifest(root, document)

    def refuses(self, root, name):
        """Require inspection and restore to fail without reserving or modifying anything."""
        target = self.parent / ("rejected-" + name)
        with self.assertRaises(BackupError):
            inspect_backup(root)
        with self.assertRaises(BackupError):
            restore_backup(root, target)
        self.assertFalse(target.exists())

    def test_roundtrip_history_receipts_retry_and_independent_append(self):
        """Preserve all graph fields/history/events and retry identity through independent restore."""
        artifact, initial, receipt = self.populate()
        source_before = self.files(self.root)
        info = create_backup(self.source, self.destination)
        self.assertEqual(info.artifacts, (artifact,))
        with self.assertRaises(FrozenInstanceError):
            info.backup_id = "changed"
        before = self.files(self.destination)
        output = self.child('''
import sys
from research_pipeline.backup import inspect_backup
print(inspect_backup(sys.argv[1]).backup_id)
''', self.destination)
        self.assertEqual(output.strip(), info.backup_id)
        with restore_backup(self.destination, self.restored) as restored:
            for identity in ("claim", "task", "justification", "evidence", "context"):
                self.assertEqual(restored.history(identity), self.source.history(identity))
                self.assertEqual(restored.head(identity), self.source.head(identity))
            self.assertEqual(restored.audit_events(), self.source.audit_events())
            self.assertEqual(restored.get_submission("submit"), receipt)
            extra = restored.put_artifact(b"restored independent")
            restored.submit(request("continued", [record("context", 3, artifact_references=[extra])], {"context": 2}))
            canonical_retry = initial.to_dict()
            canonical_retry["expected_heads"] = dict(reversed(list(canonical_retry["expected_heads"].items())))
            self.assertEqual(restored.submit(Submission.from_dict(canonical_retry)), receipt)
            events = restored.audit_events()
            with self.assertRaises(SubmissionConflictError):
                restored.submit(request("submit", [record("different")]))
            self.assertEqual(restored.audit_events(), events)
            self.assertEqual(restored.read_artifact(artifact), b"historical adjacency")
        for original, copy in ((self.root / "metadata.sqlite3", self.destination / "snapshot.sqlite3"),
                               (self.destination / "snapshot.sqlite3", self.restored / "metadata.sqlite3"),
                               (self.root / "objects" / artifact.digest, self.destination / "objects" / artifact.digest),
                               (self.destination / "objects" / artifact.digest, self.restored / "objects" / artifact.digest)):
            self.assertNotEqual(original.stat().st_ino, copy.stat().st_ino)
        self.assertEqual(stat.S_IMODE((self.restored / "metadata.sqlite3").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.restored / "objects" / artifact.digest).stat().st_mode), 0o400)
        self.assertEqual(self.files(self.root), source_before)
        self.assertEqual(self.files(self.destination), before)

    def test_empty_store_empty_artifact_and_relative_paths(self):
        """Empty histories and zero-byte objects work, including explicit caller-relative paths."""
        info = create_backup(self.source, self.destination)
        self.assertEqual(info.artifacts, ())
        with restore_backup(self.destination, self.restored) as restored:
            self.assertEqual(restored.audit_events(), ())
        self.child('''
from research_pipeline.store import RecordStore
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import CreationProvenance, RecordEnvelope, Submission
p = CreationProvenance("author", "2026-10-30T00:00:00Z")
with RecordStore.create("relative source") as source:
    a = source.put_artifact(b"")
    source.submit(Submission("empty", p, [RecordEnvelope("empty", 1, "evidence", {}, p, artifact_references=[a])], {"empty": 0}))
    info = create_backup(source, "relative backup")
assert inspect_backup("relative backup") == info
with restore_backup("relative backup", "relative restored") as restored:
    assert restored.read_artifact(a) == b""
''')

    def test_real_incremental_capture_with_separate_writer_and_later_append(self):
        """A commit during real page steps restarts coherently; post-capture appends stay excluded."""
        old = self.source.put_artifact(b"old history")
        self.source.submit(request("large", [record(content={"padding": "x" * 1500000}, artifact_references=[old])]))
        calls = []
        captured = []
        later = []

        def boundary(point):
            """Commit through a separate connection at a deterministic real backup boundary."""
            if point == "capture_progress":
                calls.append(point)
                if len(calls) == 1:
                    with RecordStore.open(self.root) as writer:
                        artifact = writer.put_artifact(b"during capture")
                        writer.submit(request("during", [record("during", artifact_references=[artifact])]))
                        captured.append(artifact)
            if point == "after_capture":
                with RecordStore.open(self.root) as writer:
                    artifact = writer.put_artifact(b"after capture")
                    writer.submit(request("later", [record("later", artifact_references=[artifact])]))
                    later.append(artifact)

        with patch.object(backup, "_fault", side_effect=boundary):
            info = create_backup(self.source, self.destination)
        self.assertGreater(len(calls), 2)
        self.assertEqual(set(info.artifacts), {old, captured[0]})
        self.assertNotIn(later[0], info.artifacts)
        self.assertEqual(self.source.head("later"), 1)
        with restore_backup(self.destination, self.restored) as restored:
            self.assertEqual(restored.head("during"), 1)
            self.assertIsNone(restored.head("later"))
            self.assertEqual(restored.read_artifact(old), b"old history")
            self.assertEqual(restored.read_artifact(captured[0]), b"during capture")

    def test_capture_deadline_active_transaction_and_closed_source(self):
        """The real SQLite progress path enforces its deadline and rejects invalid handles early."""
        with patch.object(backup.time, "monotonic", side_effect=[0.0, 6.0]):
            with self.assertRaisesRegex(BackupOperationalError, "deadline"):
                create_backup(self.source, self.destination)
        self.refuses(self.destination, "deadline")
        self.source._connection.execute("BEGIN")
        with self.assertRaisesRegex(BackupOperationalError, "active transaction"):
            create_backup(self.source, self.restored)
        self.assertFalse(self.restored.exists())
        self.source._connection.execute("ROLLBACK")
        self.source.close()
        with self.assertRaises(StoreClosedError):
            create_backup(self.source, self.restored)

    def test_strict_manifest_and_inventory_damage(self):
        """Reject malformed fields, scalar types, unsafe addresses and noncanonical inventories."""
        artifact, _, _ = self.populate()
        extra = self.source.put_artifact(b"second referenced")
        self.source.submit(request("extra", [record("extra", artifact_references=[extra])]))
        create_backup(self.source, self.destination)
        base = json.loads((self.destination / "manifest.json").read_text())
        variants = []
        for field in base:
            value = json.loads(json.dumps(base))
            del value[field]
            variants.append(value)
        for field in ("format_version", "schema_version"):
            for wrong in (True, 1.0, "1", 0, 2, None):
                variants.append({**base, field: wrong})
        variants.extend([{**base, "extra": 1}, [], {**base, "artifacts": {}},
                         {**base, "artifacts": []}, {**base, "artifacts": base["artifacts"] * 2},
                         {**base, "artifacts": list(reversed(base["artifacts"]))}])
        for field in ("metadata", "artifacts"):
            for entry in ({"digest": "../outside", "size": 0}, {"digest": "/tmp/outside", "size": 0},
                          {"digest": "a" * 64, "size": True}, {"digest": "a" * 64, "size": -1},
                          {"digest": "a" * 64, "size": 1.0}, {"digest": "a" * 64, "size": "1"},
                          {"digest": "a" * 64, "size": 1, "path": "outside"}, {"digest": "G" * 64, "size": 0},
                          {"size": 0}, {"digest": "a" * 64, "size": 1}):
                variants.append({**base, field: entry if field == "metadata" else [entry]})
        variants.extend([{**base, "metadata": {**base["metadata"], "size": 1}},
                         {**base, "artifacts": [{**artifact.to_dict(), "size": artifact.size + 1}, extra.to_dict()]}])
        payloads = [json.dumps(value).encode() for value in variants]
        payloads += [b"{", b"\xff", b'{"format_version":1,"format_version":1}',
                     json.dumps(base).replace('"size":', '"size":0,"size":', 1).encode(),
                     json.dumps(base).replace('"size":', '"size":NaN,"ignored":', 1).encode()]
        for index, data in enumerate(payloads):
            with self.subTest(index=index):
                root = self.damaged_copy(f"manifest-{index}")
                self.rewrite(root / "manifest.json", data)
                before = self.files(root)
                self.refuses(root, f"manifest-{index}")
                self.assertEqual(self.files(root), before)
        whitespace = self.damaged_copy("whitespace")
        self.rewrite(whitespace / "manifest.json", json.dumps(base, indent=4, sort_keys=False).encode())
        self.assertEqual(inspect_backup(whitespace), inspect_backup(self.destination))

    def test_missing_truncated_wrong_hash_files_and_layout(self):
        """Actual metadata/object damage and extra files never pass inspection or restoration."""
        artifact, _, _ = self.populate()
        create_backup(self.source, self.destination)
        for relative in ("snapshot.sqlite3", "objects/" + artifact.digest):
            for damage in ("missing", "truncated", "hash"):
                with self.subTest(relative=relative, damage=damage):
                    name = relative.split("/")[0] + damage
                    root = self.damaged_copy(name)
                    path = root / relative
                    original = path.read_bytes()
                    if damage == "missing":
                        path.unlink()
                    else:
                        self.rewrite(path, original[:1] if damage == "truncated" else bytes([original[0] ^ 1]) + original[1:])
                    before = self.files(root)
                    self.refuses(root, name)
                    self.assertEqual(self.files(root), before)
        for index, relative in enumerate(("extra", "snapshot.sqlite3-journal", "snapshot.sqlite3-wal", "snapshot.sqlite3-shm", ".staging/leftover", "objects/" + "f" * 64, ".backup-incomplete")):
            root = self.damaged_copy(f"layout-{index}")
            (root / relative).write_bytes(b"extra")
            self.refuses(root, f"layout-{index}")

    def test_rehashed_database_tampering_is_rejected(self):
        """Recomputed outer digests cannot hide malformed schema or inconsistent application rows."""
        self.populate()
        create_backup(self.source, self.destination)
        mutations = [
            "PRAGMA user_version=2;", "CREATE TABLE extra(value);", "DROP TRIGGER revision_states;",
            "UPDATE identities SET head=1 WHERE record_id='context';",
            "UPDATE identities SET kind='evidence' WHERE record_id='context';",
            "UPDATE revisions SET content_json='{\"changed\":true}' WHERE record_id='context';",
            "UPDATE revisions SET content_json=replace(content_json, '1.0', '1') WHERE record_id='claim';",
            "UPDATE revisions SET ordinal=99 WHERE record_id='claim';",
            "UPDATE revisions SET provenance_json='{\"actor\":\"changed\"}' WHERE record_id='claim';",
            "UPDATE record_links SET ordinal=99 WHERE record_id='claim' AND ordinal=0;",
            "UPDATE record_links SET target_kind='task_specification' WHERE record_id='claim';",
            "UPDATE artifact_links SET ordinal=99 WHERE ordinal=0;",
            "DELETE FROM artifacts;",
            "INSERT INTO artifacts VALUES ('" + "a" * 64 + "', 0);",
            "UPDATE submissions SET fingerprint='" + "a" * 64 + "';",
            "UPDATE submissions SET request_json=replace(request_json, '\"fingerprint_version\":1', '\"fingerprint_version\":true');",
            "UPDATE submissions SET request_json=replace(request_json, '\"fingerprint_version\":1', '\"fingerprint_version\":1,\"fingerprint_version\":1');",
            "UPDATE audit_events SET committed_at='invalid';",
            "UPDATE audit_events SET provenance_json='{}';", "DELETE FROM audit_events WHERE event_id=1;",
            "UPDATE audit_events SET event_id=100 WHERE event_id=1;",
            "DELETE FROM revisions WHERE record_id='context' AND revision=1;",
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(sql=mutation):
                root = self.damaged_copy(f"database-{index}")
                self.mutate_database(root, mutation)
                self.refuses(root, f"database-{index}")

    def test_unsafe_entries_are_bounded_and_do_not_touch_sentinels(self):
        """No-follow/nonblocking validation rejects files, roots, ancestors, dangling links and FIFOs."""
        artifact, _, _ = self.populate()
        create_backup(self.source, self.destination)
        sentinel = self.parent / "sentinel"
        sentinel.write_bytes(b"do not change")
        for relative in ("snapshot.sqlite3", "manifest.json", "objects/" + artifact.digest):
            for kind in ("symlink", "dangling", "directory", "fifo"):
                name = relative.split("/")[0] + "-" + kind
                root = self.damaged_copy(name)
                path = root / relative
                path.unlink()
                if kind in ("symlink", "dangling"):
                    path.symlink_to(sentinel if kind == "symlink" else self.parent / "absent")
                elif kind == "directory":
                    path.mkdir()
                else:
                    os.mkfifo(path, 0o400)
                self.child('''
import sys
from research_pipeline.backup import inspect_backup, restore_backup, BackupError
for action in (lambda: inspect_backup(sys.argv[1]), lambda: restore_backup(sys.argv[1], sys.argv[2])):
    try: action()
    except BackupError: pass
    else: raise AssertionError("unsafe entry accepted")
''', root, self.parent / ("reject-" + name))
        for index, relative in enumerate(("objects", ".staging")):
            root = self.damaged_copy(f"directory-link-{index}")
            shutil.rmtree(root / relative)
            (root / relative).symlink_to(self.destination / relative, target_is_directory=True)
            self.refuses(root, f"directory-link-{index}")
        alias = self.parent / "alias"
        alias.symlink_to(self.parent, target_is_directory=True)
        self.refuses(alias / self.destination.name, "ancestor")
        root_alias = self.parent / "root-alias"
        root_alias.symlink_to(self.destination, target_is_directory=True)
        self.refuses(root_alias, "root")
        self.refuses(self.parent / "unused" / ".." / self.destination.name, "traversal")
        self.assertEqual(sentinel.read_bytes(), b"do not change")

    def test_destinations_are_exclusive_and_not_nested(self):
        """Existing files/directories/dangling links and unsafe/nested paths remain unchanged."""
        self.populate()
        create_backup(self.source, self.destination)
        before = self.files(self.root)
        for index, kind in enumerate(("file", "directory", "dangling")):
            target = self.parent / f"existing-{index}"
            if kind == "file": target.write_bytes(b"preserved")
            elif kind == "directory": target.mkdir()
            else: target.symlink_to(self.parent / "absent")
            inode = target.lstat().st_ino
            for action in (lambda: create_backup(self.source, target), lambda: restore_backup(self.destination, target)):
                with self.assertRaises(BackupError): action()
                self.assertEqual(target.lstat().st_ino, inode)
            if kind == "file": self.assertEqual(target.read_bytes(), b"preserved")
        for action, target in ((lambda p: create_backup(self.source, p), self.root / "nested"),
                               (lambda p: create_backup(self.source, p), Path("/" + str(self.root / "double-slash"))),
                               (lambda p: restore_backup(self.destination, p), self.destination / "nested"),
                               (lambda p: create_backup(self.source, p), self.parent / "unused" / ".." / "bad")):
            with self.assertRaises(BackupLayoutError): action(target)
            self.assertFalse(target.exists())
        alias = self.parent / "alias"
        alias.symlink_to(self.parent, target_is_directory=True)
        with self.assertRaises(BackupError): create_backup(self.source, alias / "unsafe")
        with self.assertRaises(BackupError): restore_backup(self.destination, alias / "unsafe")
        self.assertFalse((self.parent / "unsafe").exists())
        self.assertEqual(self.files(self.root), before)

    def test_damaged_source_references_leave_incomplete_backup(self):
        """Missing/truncated/wrong-hash committed source objects fail without changing the source."""
        artifact, _, _ = self.populate()
        path = self.root / "objects" / artifact.digest
        original = path.read_bytes()
        for index, damage in enumerate((None, b"short", b"x" * len(original))):
            if damage is None: path.unlink()
            else:
                if not path.exists(): path.write_bytes(b"")
                self.rewrite(path, damage)
            before = self.files(self.root)
            target = self.parent / f"bad-source-{index}"
            with self.assertRaises(BackupError): create_backup(self.source, target)
            self.refuses(target, f"bad-source-{index}")
            self.assertEqual(self.files(self.root), before)

    def test_lifecycle_failures_and_uncertain_final_acknowledgment(self):
        """Real copied files remain incomplete before removal and verifiable after uncertain publication."""
        self.populate()
        create_backup(self.source, self.destination)
        for operation in ("backup", "restore"):
            for boundary in ("file_copied", "before_publication", "after_publication"):
                target = self.parent / f"{operation}-{boundary}"
                calls = []

                def fail(point):
                    """Fail after real work, skipping the marker's own empty-file write."""
                    if point == boundary:
                        calls.append(point)
                        if boundary != "file_copied" or len(calls) == (3 if operation == "backup" else 2):
                            raise OSError("injected lifecycle failure")

                with patch.object(backup, "_fault", side_effect=fail):
                    with self.assertRaises(BackupOperationalError) as caught:
                        if operation == "backup": create_backup(self.source, target)
                        else: restore_backup(self.destination, target)
                if boundary == "after_publication":
                    self.assertIn("uncertain", str(caught.exception))
                    if operation == "backup": inspect_backup(target)
                    else:
                        with RecordStore.open(target) as store:
                            self.assertEqual(store.audit_events(), self.source.audit_events())
                elif operation == "backup": self.refuses(target, target.name)
                else:
                    with self.assertRaises(StoreLayoutError): RecordStore.open(target)

    def test_partial_writes_read_failures_and_inode_selected_sync_failures(self):
        """Exercise partial OS writes, real read errors and inode-selected durability failures."""
        artifact, _, _ = self.populate()
        create_backup(self.source, self.destination)
        original_write, original_read, original_sync = os.write, os.read, os.fsync
        source_before, backup_before = self.files(self.root), self.files(self.destination)
        for operation in ("backup", "restore"):
            for mode in ("partial", "read", "sync", "remove", "final-sync"):
                target = self.parent / f"{operation}-{mode}"
                source_object = (self.root if operation == "backup" else self.destination) / "objects" / artifact.digest
                read_inode = source_object.stat().st_ino
                writes = []

                def write(descriptor, data):
                    """Write an actual prefix into the destination and fail on the next write."""
                    if data:
                        if writes: raise OSError("failure after partial write")
                        writes.append(original_write(descriptor, data[:1]))
                        return writes[-1]
                    return original_write(descriptor, data)

                def read(descriptor, count):
                    """Fail only reads of the selected actual source artifact inode."""
                    if os.fstat(descriptor).st_ino == read_inode:
                        raise OSError("source read failure")
                    return original_read(descriptor, count)

                def sync(descriptor):
                    """Fail a named destination inode barrier only after actual content exists."""
                    marker = target / (".backup-incomplete" if operation == "backup" else ".restore-incomplete")
                    metadata = target / ("snapshot.sqlite3" if operation == "backup" else "metadata.sqlite3")
                    info = os.fstat(descriptor)
                    if metadata.exists() and metadata.stat().st_size:
                        selected = metadata if mode == "sync" else target
                        if info.st_ino == selected.stat().st_ino and (mode != "final-sync" or not marker.exists()):
                            raise OSError("selected barrier failure")
                    original_sync(descriptor)

                original_unlink = os.unlink

                def unlink(name, *args, **kwargs):
                    """Reject final marker removal while allowing normal artifact staging cleanup."""
                    if str(name).endswith("-incomplete"):
                        raise OSError("marker removal failure")
                    return original_unlink(name, *args, **kwargs)

                replacement = {"partial": ("write", write), "read": ("read", read),
                               "sync": ("fsync", sync), "remove": ("unlink", unlink),
                               "final-sync": ("fsync", sync)}[mode]
                with patch.object(os, replacement[0], side_effect=replacement[1]):
                    with self.assertRaises(BackupError):
                        if operation == "backup": create_backup(self.source, target)
                        else: restore_backup(self.destination, target)
                if mode == "final-sync":
                    if operation == "backup": inspect_backup(target)
                    else:
                        with RecordStore.open(target) as store:
                            self.assertEqual(store.audit_events(), self.source.audit_events())
                elif target.exists():
                    if operation == "backup": self.refuses(target, target.name)
                    else:
                        with self.assertRaises(StoreLayoutError): RecordStore.open(target)

        self.assertEqual(self.files(self.root), source_before)
        self.assertEqual(self.files(self.destination), backup_before)

    def test_abrupt_interruption_and_unsafe_restore_marker(self):
        """Fresh processes refuse complete-looking copies terminated before marker removal."""
        self.populate()
        create_backup(self.source, self.destination)
        for operation in ("backup", "restore"):
            target = self.parent / ("crash-" + operation)
            self.child('''
import os, sys
from research_pipeline import backup
from research_pipeline.store import RecordStore
def crash(point):
    """Terminate after full verification but before publication."""
    if point == "before_publication": os._exit(73)
backup._fault = crash
if sys.argv[1] == "backup":
    with RecordStore.open(sys.argv[2]) as source: backup.create_backup(source, sys.argv[4])
else: backup.restore_backup(sys.argv[3], sys.argv[4])
''', operation, self.root, self.destination, target, expected=73)
            before = self.files(target)
            self.child('''
import sys
from research_pipeline.backup import inspect_backup, BackupError
from research_pipeline.store import RecordStore, StoreLayoutError
try:
    if sys.argv[1] == "backup": inspect_backup(sys.argv[2])
    else: RecordStore.open(sys.argv[2])
except (BackupError, StoreLayoutError): pass
else: raise AssertionError("interrupted copy accepted")
''', operation, target)
            self.assertEqual(self.files(target), before)
        with restore_backup(self.destination, self.restored): pass
        marker = self.restored / ".restore-incomplete"
        marker.symlink_to(self.parent / "absent")
        with self.assertRaisesRegex(StoreLayoutError, "incomplete restore"):
            RecordStore.open(self.restored)
        self.assertTrue(marker.is_symlink())

    def test_durable_unacknowledged_submission_and_failed_orphan_end_to_end(self):
        """Recover a real lost acknowledgment, exclude a failed batch's orphan, then restore/retry."""
        artifact = self.source.put_artifact(b"committed original")
        initial = request("lost-ack", [record(artifact_references=[artifact])])
        self.source.close()
        self.child('''
import json, os, sys
from research_pipeline import store
from research_pipeline.domain import Submission
def crash(point):
    """Exit after the real durable COMMIT, before the caller receives its receipt."""
    if point == "after_commit": os._exit(74)
store._fault = crash
with store.RecordStore.open(sys.argv[1]) as source:
    source.submit(Submission.from_dict(json.loads(sys.argv[2])))
''', self.root, json.dumps(initial.to_dict()), expected=74)
        self.source = RecordStore.open(self.root)
        self.addCleanup(self.source.close)
        receipt = self.source.get_submission("lost-ack")
        self.assertIsNotNone(receipt)
        self.assertEqual(self.source.submit(initial), receipt)
        orphan = self.source.put_artifact(b"uncommitted orphan")

        def fail(point):
            """Fail after an actual first revision insert so SQLite rolls the request back."""
            if point == "after_first_revision": raise OSError("failed batch")

        with patch("research_pipeline.store._fault", side_effect=fail):
            with self.assertRaises(OSError):
                self.source.submit(request("failed", [record("failed", artifact_references=[orphan])]))
        (self.root / ".staging" / "retained").write_bytes(b"not copied")
        (self.root / "credentials").write_bytes(b"not copied")
        before = self.files(self.root)
        info = create_backup(self.source, self.destination)
        self.assertEqual(info.artifacts, (artifact,))
        self.assertEqual(set((self.destination / "objects").iterdir()), {self.destination / "objects" / artifact.digest})
        with restore_backup(self.destination, self.restored) as restored:
            self.assertEqual(restored.submit(initial), receipt)
            self.assertEqual(restored.history("context"), initial.records)
            self.assertEqual(restored.audit_events(), self.source.audit_events())
            self.assertEqual(len(restored.audit_events()), 1)
            self.assertIsNone(restored.get_submission("failed"))
        self.assertEqual(self.files(self.root), before)

    def test_busy_backup_retry_deadline_is_bounded(self):
        """A real exclusive source lock reaches SQLite's busy retry callback and times out."""
        lock = sqlite3.connect(self.root / "metadata.sqlite3", isolation_level=None)
        lock.execute("BEGIN EXCLUSIVE")
        points = []

        def observe(point):
            """Record real backup progress callbacks without replacing SQLite capture."""
            points.append(point)

        try:
            with patch.object(backup, "_fault", side_effect=observe), patch.object(
                    backup.time, "monotonic", side_effect=[0.0, 6.0]):
                with self.assertRaisesRegex(BackupOperationalError, "deadline"):
                    create_backup(self.source, self.destination)
        finally:
            lock.execute("ROLLBACK")
            lock.close()
        self.assertIn("capture_progress", points)
        self.refuses(self.destination, "busy")

    def test_successful_short_writes_and_durability_targets(self):
        """Short writes complete correctly and actual file/directory barriers precede success."""
        artifact, _, _ = self.populate()
        original_write, original_sync = os.write, os.fsync
        synchronized = set()

        def short_write(descriptor, data):
            """Force several actual writes per metadata/object without suppressing any bytes."""
            return original_write(descriptor, data[:max(1, len(data) // 2)])

        def observe_sync(descriptor):
            """Record descriptor identity while performing each real synchronization barrier."""
            info = os.fstat(descriptor)
            synchronized.add((info.st_dev, info.st_ino))
            original_sync(descriptor)

        with patch.object(os, "write", side_effect=short_write), patch.object(os, "fsync", side_effect=observe_sync):
            create_backup(self.source, self.destination)
            with restore_backup(self.destination, self.restored) as restored:
                self.assertEqual(restored.read_artifact(artifact), b"historical adjacency")
        for root, metadata in ((self.destination, "snapshot.sqlite3"), (self.restored, "metadata.sqlite3")):
            for path in (root, root.parent, root / metadata, root / "objects", root / ".staging", root / "objects" / artifact.digest):
                info = path.stat()
                self.assertIn((info.st_dev, info.st_ino), synchronized, str(path))
        info = (self.destination / "manifest.json").stat()
        self.assertIn((info.st_dev, info.st_ino), synchronized)
