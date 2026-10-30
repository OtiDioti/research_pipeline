"""Version-specific real SQLite admission, legacy compatibility and exact backup tests."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.backup import BackupError, create_backup, inspect_backup, restore_backup
from research_pipeline.domain import DomainValidationError, RecordEnvelope, RecordReference, _KINDS, _LEGACY_KINDS
from research_pipeline.scientific import decode_envelope
from research_pipeline.store import RecordStore, StoreLayoutError, ReferenceResolutionError, RevisionConflictError, SubmissionConflictError
from tests import test_backup, test_store
from tests.legacy import canonical, create_legacy, historical_store, historical_backup, table_values
from tests.test_store import record, request
from tests.test_typed_store import typed_graph, envelope


class LegacyBackupTests(test_backup.BackupTests):
    """Run the preserved publication/corruption/concurrency suite against genuine v1 DDL."""

    def setUp(self):
        """Use independently frozen legacy creation for the suite's actual source."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "source #? ü"
        self.destination = self.parent / "backup #? ü"
        self.restored = self.parent / "restored #? ü"
        self.source = create_legacy(self.root)
        self.addCleanup(self.source.close)


class LegacyStoreTests(test_store.StoreTests):
    """Preserve generic transaction, journal, retry and crash coverage on genuine v1."""

    def setUp(self):
        """Allocate a private legacy store without changing production version selection."""
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "runtime #? space"
        self.store = create_legacy(self.root)
        self.addCleanup(self.store.close)


class VersionTests(unittest.TestCase):
    """Check schema evolution without executing a migration or replaying old history."""

    def setUp(self):
        """Allocate outside-source disposable stores using the existing tempfile convention."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)

    def files(self, root):
        """Snapshot paths and regular file bytes for mutation-free rejection assertions."""
        return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                for path in root.rglob("*")}

    def test_twenty_kinds_history_and_atomic_conflicts(self):
        """All kinds preserve exact cyclic/duplicate links and append history; conflicts are atomic."""
        root = self.parent / "all"
        kinds = sorted(_KINDS)
        records = []
        for index, kind in enumerate(kinds):
            target = kinds[(index + 1) % len(kinds)]
            edge = RecordReference(target, 1, "describes", target)
            records.append(record(kind, kind=kind, content={"approved": True, "promoted": "supported"},
                                  record_references=[edge, edge, RecordReference(kind, 1, "self", kind)]))
        with RecordStore.create(root) as store:
            self.assertEqual(store._schema_version, 2)
            first = request("twenty", records)
            receipt = store.submit(first)
            for item in records:
                self.assertEqual(store.get_revision(item.record_id, 1), item)
            next_records = [RecordEnvelope.from_dict({**item.to_dict(), "revision": 2}) for item in records]
            store.submit(request("next", next_records, {kind: 1 for kind in kinds}))
            before = table_values(root)
            for batch, error in (
                (request("stale", next_records, {kind: 1 for kind in kinds}), RevisionConflictError),
                (request("changed-kind", [record("project", 3, "run")], {"project": 2}), RevisionConflictError),
                (request("wrong-target", [record("valid"), record("bad", record_references=[
                    RecordReference("project", 1, "uses", "run")])]), ReferenceResolutionError)):
                with self.assertRaises(error):
                    store.submit(batch)
                self.assertEqual(table_values(root), before)
            self.assertEqual(store.submit(first), receipt)
        with RecordStore.open(root) as store:
            for old, new in zip(records, next_records):
                self.assertEqual(store.history(old.record_id), (old, new))
            info = create_backup(store, self.parent / "backup")
        self.assertEqual((info.format_version, info.schema_version), (2, 2))
        with restore_backup(self.parent / "backup", self.parent / "restored") as store:
            self.assertEqual(table_values(root), table_values(self.parent / "restored"))
            store.submit(request("event", [record("new-event", kind="event")]))

    def test_added_kinds_have_no_canonical_state_or_typed_authority(self):
        """Every new kind rejects both state dimensions and scientific member admission."""
        with RecordStore.create(self.parent / "states") as store:
            for kind in sorted(_KINDS - _LEGACY_KINDS):
                for state in ({"operational_status": "completed"}, {"scientific_disposition": "provisional"}):
                    with self.subTest(kind=kind, state=state), self.assertRaises(DomainValidationError):
                        record(kind, kind=kind, **state)
                with self.assertRaises(DomainValidationError):
                    store.submit_typed(request(kind, [record(kind, kind=kind)]))
                self.assertIsNone(store.head(kind))
            self.assertEqual(store.audit_events(), ())

    def test_generic_inputs_to_unchanged_typed_evidence(self):
        """New generic inputs round-trip in Evidence but cannot enter constrained scientific roles."""
        root = self.parent / "typed-inputs"
        with RecordStore.create(root) as store:
            inputs = [record(kind, kind=kind) for kind in sorted(_KINDS - _LEGACY_KINDS)]
            store.submit(request("generic-inputs", inputs + [record("task", kind="task_specification")]))
            artifact = store.put_artifact(b"typed observations")
            graph = typed_graph(artifact)
            evidence = decode_envelope(graph[2])
            evidence = replace(evidence, input_records=tuple(RecordReference(item.record_id, 1, "input_record", item.kind) for item in inputs))
            graph[2] = envelope("evidence", evidence)
            receipt = store.submit_typed(request("typed", graph))
            self.assertEqual(store.get_typed_revision("evidence", 1)[1], evidence)
            before = table_values(root)
            wrong = replace(evidence, input_records=(RecordReference("project", 1, "input_record", "run"),))
            with self.assertRaises(ReferenceResolutionError):
                store.submit_typed(request("wrong-input", [envelope("wrong", wrong)]))
            route = decode_envelope(graph[0])
            for role, field, value, kind in (
                ("context", "context", evidence, "research_context"),
                ("premise", "premises", route, "claim"),
                ("conclusion", "conclusions", route, "claim"),
                ("evidence", "evidence", route, "evidence"),
                ("target_claim", "target_claims", evidence, "claim"),
            ):
                # A declared new kind fails the codec; an old-kind declaration
                # pointing at an actual project passes the codec but fails resolution.
                new_kind_link = RecordReference("project", 1, role, "project")
                with self.subTest(role=role), self.assertRaises(DomainValidationError):
                    replace(value, **{field: new_kind_link if field == "context" else (new_kind_link,)})
                wrong_target = RecordReference("project", 1, role, kind)
                wrong_value = replace(value, **{field: wrong_target if field == "context" else (wrong_target,)})
                with self.assertRaises(ReferenceResolutionError):
                    store.submit_typed(request("forbidden-" + role, [envelope("forbidden-" + role, wrong_value)]))
            self.assertEqual(table_values(root), before)
            create_backup(store, self.parent / "typed-backup")
        with restore_backup(self.parent / "typed-backup", self.parent / "typed-restored") as restored:
            self.assertEqual(restored.get_typed_revision("evidence", 1)[1], evidence)
            self.assertEqual(restored.get_submission("typed"), receipt)

    def test_authentic_legacy_history_independent_manifest_and_retries(self):
        """Preserve independently seeded old requests/events and independent format-1 identity."""
        root = self.parent / "legacy"
        store, requests, artifact = historical_store(root)
        self.addCleanup(store.close)
        original = table_values(root)
        receipts = [store.get_submission(item.submission_id) for item in requests]
        self.assertEqual([event.event_id for event in store.audit_events()], [11, 22, 33, 44, 55])
        self.assertEqual(store.get_typed_revision("context", 1)[0].revision, 1)
        self.assertEqual(len(store.history("context")), 2)
        document, expected_id = historical_backup(root, self.parent / "historical")
        source_bytes = self.files(root)
        backup_bytes = self.files(self.parent / "historical")
        info = inspect_backup(self.parent / "historical")
        self.assertEqual(info.backup_id, expected_id)
        self.assertEqual(expected_id, hashlib.sha256(canonical(document).encode()).hexdigest())
        with restore_backup(self.parent / "historical", self.parent / "restored") as restored:
            self.assertEqual(restored._schema_version, 1)
            self.assertEqual(table_values(self.parent / "restored"), original)
            self.assertEqual((self.parent / "restored" / "metadata.sqlite3").read_bytes(),
                             (self.parent / "historical" / "snapshot.sqlite3").read_bytes())
            for item, receipt in zip(requests, receipts):
                self.assertEqual(restored.submit(item), receipt)
            restored.submit(request("append", [record("context", 3)], {"context": 2}))
            artifact_path = self.parent / "restored" / "objects" / artifact.digest
            artifact_path.unlink()
            for item, receipt in zip(requests, receipts):
                self.assertEqual(restored.submit(item), receipt)
            self.assertEqual(restored.submit_typed(requests[2]), receipts[2])
            with self.assertRaisesRegex(DomainValidationError, "project.*schema 1.*migration"):
                restored.submit(request("project", [record("project", kind="project")]))
        output = test_backup.BackupTests.child(self, """
import sys
from research_pipeline.backup import restore_backup
from research_pipeline.store import RecordStore
with restore_backup(sys.argv[1], sys.argv[2]) as store:
    assert store._schema_version == 1
    assert len(store.history("context")) == 2
    assert store.get_typed_revision("context", 1)[0].revision == 1
    assert [event.event_id for event in store.audit_events()] == [11, 22, 33, 44, 55]
    print(store.get_submission("legacy-typed").event_id)
""", self.parent / "historical", self.parent / "child-restored")
        self.assertEqual(output.strip(), "33")
        self.assertEqual(self.files(root), source_bytes)
        self.assertEqual(self.files(self.parent / "historical"), backup_bytes)
        for original_file, copied in ((root / "metadata.sqlite3", self.parent / "historical" / "snapshot.sqlite3"),
                                      (root / "objects" / artifact.digest, self.parent / "historical" / "objects" / artifact.digest)):
            self.assertNotEqual(original_file.stat().st_ino, copied.stat().st_ino)
        exported = create_backup(store, self.parent / "exported")
        self.assertEqual((exported.format_version, exported.schema_version), (1, 1))
        store.submit(request("old-append", [record("old")]))
        self.assertEqual(store._schema_version, 1)

    def test_legacy_kind_admission_precedes_all_new_request_effects(self):
        """Reject every new kind/declaration atomically, while original ID conflicts take precedence."""
        root = self.parent / "legacy"
        store, requests, artifact = historical_store(root)
        self.addCleanup(store.close)
        before = self.files(root)
        for kind in sorted(_KINDS - _LEGACY_KINDS):
            for records in ([record("new", kind=kind)],
                            [record("old"), record("new", kind=kind)],
                            [record("old", record_references=[RecordReference("missing", 1, "uses", kind)])]):
                with self.subTest(kind=kind), patch("research_pipeline.store._fault") as fault:
                    with self.assertRaisesRegex(DomainValidationError, kind + ".*schema 1.*migration"):
                        store.submit(request("rejected", records))
                    fault.assert_not_called()
                self.assertEqual(self.files(root), before)
            with self.assertRaises(SubmissionConflictError):
                store.submit(request(requests[0].submission_id, [record("new", kind=kind)]))
        self.assertEqual(self.files(root), before)

    def test_version_ddl_gate_rejects_without_mutation(self):
        """Unknown/crossed versions, altered constraints/triggers and extra objects fail closed."""
        for version, create in ((1, create_legacy), (2, RecordStore.create)):
            root = self.parent / str(version)
            create(root).close()
            database = root / "metadata.sqlite3"
            original = database.read_bytes()
            mutations = ["PRAGMA user_version=99", f"PRAGMA user_version={3-version}",
                         "DROP TABLE record_links", "DROP TRIGGER revision_states",
                         "CREATE TABLE extra(x)", "CREATE INDEX extra ON identities(kind)",
                         "CREATE VIEW extra AS SELECT * FROM identities",
                         "DROP TRIGGER revision_states; CREATE TRIGGER revision_states BEFORE INSERT ON revisions BEGIN SELECT 1; END",
                         "DROP TABLE artifacts; CREATE TABLE artifacts(digest TEXT PRIMARY KEY NOT NULL, size INTEGER NOT NULL, UNIQUE(digest,size))"]
            if version == 1:
                mutations.append("CREATE TABLE migration_history(migration_id INTEGER)")
            for sql in mutations:
                database.write_bytes(original)
                with sqlite3.connect(database) as connection:
                    connection.executescript(sql)
                before = self.files(root)
                with self.subTest(version=version, sql=sql), self.assertRaises(StoreLayoutError):
                    RecordStore.open(root)
                self.assertEqual(self.files(root), before)

    def test_sql_kind_reference_and_state_constraints(self):
        """Real SQL enforces each schema's kinds, reference kinds and both state dimensions."""
        for version, create in ((1, create_legacy), (2, RecordStore.create)):
            root = self.parent / str(version)
            create(root).close()
            connection = sqlite3.connect(root / "metadata.sqlite3")
            self.addCleanup(connection.close)
            connection.execute("INSERT INTO submissions VALUES ('s','{}','unused')")
            allowed = _LEGACY_KINDS if version == 1 else _KINDS
            for kind in sorted(_KINDS | {"unknown"}):
                if kind not in allowed:
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute("INSERT INTO identities VALUES (?,?,1)", (kind, kind))
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute("INSERT INTO record_links VALUES ('a',1,0,'uses','b',1,?)", (kind,))
                    continue
                connection.execute("INSERT INTO identities VALUES (?,?,1)", (kind, kind))
                valid = ("completed" if kind == "task_specification" else None,
                         "provisional" if kind == "claim" else None)
                for states in ((None, None), ("completed", None), (None, "provisional"), ("completed", "provisional")):
                    if states != valid:
                        with self.subTest(version=version, kind=kind, states=states), self.assertRaises(sqlite3.IntegrityError):
                            connection.execute("INSERT INTO revisions VALUES (?,1,'s',0,'{}','{}',?,?)", (kind, *states))
                connection.execute("INSERT INTO revisions VALUES (?,1,'s',?,'{}','{}',?,?)", (kind, len(list(allowed)) + sorted(allowed).index(kind), *valid))
                connection.execute("INSERT INTO record_links VALUES (?,1,0,'self',?,1,?)", (kind, kind, kind))
            connection.rollback()

    def test_manifest_pairs_and_actual_schema_are_both_checked(self):
        """Reject crossed, noninteger and actual-metadata mismatched pairs before reserving restore."""
        for version, create in ((1, create_legacy), (2, RecordStore.create)):
            root = self.parent / str(version)
            with create(root) as store:
                create_backup(store, self.parent / f"backup-{version}")
            backup_root = self.parent / f"backup-{version}"
            document = json.loads((backup_root / "manifest.json").read_text())
            for index, pair in enumerate(((1, 2), (2, 1), (3-version, 3-version), (True, True), (2.0, 2), (2, "2"), (99, 99))):
                changed = {**document, "format_version": pair[0], "schema_version": pair[1]}
                path = backup_root / "manifest.json"
                path.chmod(0o600)
                path.write_text(canonical(changed))
                path.chmod(0o400)
                before = self.files(backup_root)
                with self.assertRaises(BackupError):
                    inspect_backup(backup_root)
                target = self.parent / f"rejected-{version}-{index}"
                with self.assertRaises(BackupError):
                    restore_backup(backup_root, target)
                self.assertFalse(target.exists())
                self.assertEqual(self.files(backup_root), before)
