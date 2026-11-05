"""Explicit local snapshots with strict verification and durable completeness markers."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import time

from research_pipeline.artifacts import (
    ArtifactStore, ArtifactError, ArtifactLayoutError, ArtifactIOError,
    _path_directory,
)
from research_pipeline.domain import ArtifactReference, AuditEvent, CreationProvenance, Submission
from research_pipeline.store import RecordStore, StoreLayoutError, _schema_gate, _connect
from research_pipeline.schema import (
    _VERSIONS, _json, _canonical, manifest_info, ManifestLayoutError,
    validate_request_kinds, validate_history, validate_schema,
)


class BackupError(Exception):
    """Base for backup layout, integrity and operational failures."""


class BackupLayoutError(BackupError):
    """A supplied path or backup format is unsafe, incomplete or unsupported."""


class BackupIntegrityError(BackupError):
    """Snapshot, inventory or bytes disagree or violate stored application invariants."""


class BackupOperationalError(BackupError):
    """Capture, copying or synchronization failed; the destination is retained."""


@dataclass(frozen=True)
class BackupInfo:
    """Verified format versions and byte references with a canonical manifest SHA-256 identity."""

    backup_id: str
    format_version: int
    schema_version: int
    metadata: ArtifactReference
    artifacts: tuple[ArtifactReference, ...]


def _fault(boundary: str) -> None:
    """Private seam at capture/copy, mid-migration, committed migration and publication.

    Not a public callback. Tests may fail or terminate after real storage work.
    """


@contextmanager
def _errors(stage, path):
    """Translate storage/format failures with stage and path, preserving useful causes."""
    try:
        yield
    except BackupError:
        raise
    except ArtifactLayoutError as error:
        raise BackupLayoutError(f"{stage} {path}: {error}") from error
    except (OSError, ArtifactIOError, sqlite3.OperationalError) as error:
        raise BackupOperationalError(f"{stage} {path}: {error}") from error
    except (ArtifactError, StoreLayoutError, sqlite3.Error, ValueError, TypeError,
            KeyError, RecursionError, OverflowError) as error:
        raise BackupIntegrityError(f"{stage} {path}: {error}") from error


def _path(value):
    """Anchor an explicit path without resolving symlinks; forbid parent traversal."""
    path = Path(value)
    if ".." in path.parts:
        raise BackupLayoutError(f"path {path}: parent traversal is forbidden")
    path = path if path.is_absolute() else Path.cwd() / path
    # Linux treats the double-slash anchor as root; normalize it lexically so
    # containment checks cannot be bypassed without resolving any symlinks.
    return Path("/").joinpath(*path.parts[1:]) if path.anchor == "//" else path


def _outside(destination, source):
    """Reject nested destinations before reservation; traversal later rejects symlinks."""
    if destination == source or source in destination.parents:
        raise BackupLayoutError(f"destination {destination}: must be outside {source}")


def _reference(data):
    """Compute the content address of actual metadata bytes."""
    return ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))


def _manifest(metadata, artifacts, version):
    """Construct the manifest pair belonging to the actual captured schema version."""
    return {"format_version": _VERSIONS[version][2], "schema_version": version,
            "metadata": metadata.to_dict(), "artifacts": [item.to_dict() for item in artifacts]}


def _info(document):
    """Map shared manifest validation to public backup information and layout errors."""
    try:
        return BackupInfo(*manifest_info(document))
    except ManifestLayoutError as error:
        raise BackupLayoutError(str(error)) from error


def _read_file(root, name, *, readonly=True, synchronize=False):
    """Read a checked owned regular inode without following links or blocking on a FIFO."""
    with _path_directory(root) as area:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=area)
        try:
            info = os.fstat(descriptor)
            forbidden = 0o222 if readonly else 0o077
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & forbidden):
                raise BackupLayoutError(f"{root / name}: requires owned {'read-only' if readonly else 'private'} regular file")
            chunks = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            if synchronize:
                os.fsync(descriptor)
            return b"".join(chunks)
        finally:
            os.close(descriptor)


def _write_file(root, name, data, *, readonly):
    """Exclusively write all bytes, set final permissions and synchronize the new inode."""
    with _path_directory(root) as area:
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=area)
        try:
            remaining = memoryview(data)
            while remaining:
                count = os.write(descriptor, remaining)
                if count == 0:
                    raise OSError("write made no progress")
                remaining = remaining[count:]
            _fault("file_copied")
            os.fchmod(descriptor, 0o400 if readonly else 0o600)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(area)


def _reserve(path, marker):
    """Reserve an absent private root and durably mark it before any metadata is written."""
    store = ArtifactStore.create(path)
    _write_file(path, marker, b"", readonly=True)
    return store


def _layout(store, metadata_name, marker=None):
    """Require exactly the complete layout (plus only this operation's private marker)."""
    expected = {metadata_name, "objects", ".staging"}
    if metadata_name == "snapshot.sqlite3":
        expected.add("manifest.json")
    if marker:
        expected.add(marker)
        _read_file(store._root, marker)
    with _path_directory(store._root) as area:
        if set(os.listdir(area)) != expected:
            raise BackupLayoutError(f"{store._root}: extra/missing entries or incomplete operation")
    with store._layout() as (objects, staging):
        if os.listdir(staging):
            raise BackupLayoutError(f"{store._root}: nonempty .staging")
        return set(os.listdir(objects))


def _equal(actual, expected, context):
    """Compare canonical representations so JSON booleans, integers and floats stay distinct."""
    if _canonical({"value": actual}) != _canonical({"value": expected}):
        raise BackupIntegrityError(f"snapshot {context}: normalized rows disagree with canonical request")


def _database(path):
    """Verify a checked standalone immutable snapshot's schema, relations and request history.

    Caller must first validate the file, sidecar-free layout and byte hash. The
    trusted parent/owner must not mutate checked pathnames while SQLite opens them.
    Schema3 additionally validates chronological resource admissions and projections.
    Return the validated version and inventory. No live source connection or
    submission replay is used here.
    """
    header = _read_file(path.parent, path.name, readonly=path.name == "snapshot.sqlite3")[:100]
    if len(header) != 100 or header[:16] != b"SQLite format 3\0" or header[18:20] != b"\x01\x01":
        raise BackupIntegrityError(f"snapshot {path}: invalid SQLite header or unsupported journal format")
    version = _schema_gate(path)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, isolation_level=None)
    try:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise BackupIntegrityError(f"snapshot {path}: SQLite integrity_check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise BackupIntegrityError(f"snapshot {path}: foreign key violations")
        _application(connection, version)
        links = tuple(ArtifactReference(*row) for row in connection.execute(
            "SELECT DISTINCT digest,size FROM artifact_links ORDER BY digest"))
        registrations = tuple(ArtifactReference(*row) for row in connection.execute(
            "SELECT digest,size FROM artifacts ORDER BY digest"))
        if links != registrations:
            raise BackupIntegrityError("snapshot artifact registrations disagree with historical links")
        if version == 2:
            validate_history(connection.execute("SELECT * FROM migration_history").fetchall(),
                             [(item.digest, item.size) for item in registrations])
        elif version in (3, 4, 5, 6, 7):
            from research_pipeline.resource_ledger import validate_ledger
            validate_ledger(connection)
            if version in (4, 5, 6, 7):
                from research_pipeline.claim_use_store import validate
                validate(RecordStore(None, connection, version), connection)
        return version, links
    finally:
        connection.close()


def _application(connection, version):
    """Check schema-specific request kinds, normalized rows and chronological exact links."""
    submissions = {row[0]: row[1:] for row in connection.execute(
        "SELECT submission_id,request_json,fingerprint FROM submissions")}
    heads, kinds, available, visited = {}, {}, set(), set()
    for event_id, sid, event_type, committed_at, provenance in connection.execute(
            "SELECT event_id,submission_id,event_type,committed_at,provenance_json FROM audit_events ORDER BY event_id"):
        text, fingerprint = submissions[sid]
        document = _json(text)
        if (type(document) is not dict or set(document) != {"fingerprint_version", "submission"}
                or type(document["fingerprint_version"]) is not int or document["fingerprint_version"] != 1):
            raise BackupIntegrityError(f"submission {sid}: unsupported canonical request")
        request = Submission.from_dict(document["submission"])
        validate_request_kinds(request, version)
        canonical = _canonical({"fingerprint_version": 1, "submission": request.to_dict()})
        if (request.submission_id != sid or canonical.decode() != text
                or hashlib.sha256(canonical).hexdigest() != fingerprint):
            raise BackupIntegrityError(f"submission {sid}: canonical request/fingerprint mismatch")
        proposed = {(record.record_id, record.revision) for record in request.records}
        proposed_kinds = {record.record_id: record.kind for record in request.records}
        rows = connection.execute("SELECT record_id,revision,ordinal FROM revisions WHERE submission_id=? ORDER BY ordinal", (sid,)).fetchall()
        _equal([list(row) for row in rows], [[r.record_id, r.revision, i] for i, r in enumerate(request.records)], f"submission {sid} membership")
        event = AuditEvent(event_id, sid, event_type, committed_at, request.provenance,
                           tuple((r.record_id, r.revision) for r in request.records))
        _equal(_json(provenance), request.provenance.to_dict(), f"event {event_id} provenance")
        if event.committed_at != committed_at:
            raise BackupIntegrityError(f"event {event_id}: noncanonical timestamp")
        for record in request.records:
            identity, revision = record.record_id, record.revision
            prior = heads.get(identity, 0)
            if (request.expected_heads[identity] != prior or revision != prior + 1
                    or kinds.get(identity, record.kind) != record.kind):
                raise BackupIntegrityError(f"revision {identity}@{revision}: history/head/kind mismatch")
            row = connection.execute("SELECT content_json,provenance_json,operational_status,scientific_disposition FROM revisions WHERE record_id=? AND revision=?", (identity, revision)).fetchone()
            _equal([_json(row[0]), _json(row[1]), row[2], row[3]],
                   [record.content, record.provenance.to_dict(), record.operational_status, record.scientific_disposition], f"revision {identity}@{revision}")
            actual_links = connection.execute("SELECT ordinal,target_id,target_revision,relationship,target_kind FROM record_links WHERE record_id=? AND revision=? ORDER BY ordinal", (identity, revision)).fetchall()
            _equal([list(row) for row in actual_links], [[i, r.record_id, r.revision, r.relationship, r.target_kind] for i, r in enumerate(record.record_references)], f"record links {identity}@{revision}")
            actual_artifacts = connection.execute("SELECT ordinal,digest,size FROM artifact_links WHERE record_id=? AND revision=? ORDER BY ordinal", (identity, revision)).fetchall()
            _equal([list(row) for row in actual_artifacts], [[i, r.digest, r.size] for i, r in enumerate(record.artifact_references)], f"artifact links {identity}@{revision}")
            for link in record.record_references:
                target = (link.record_id, link.revision)
                kind = kinds.get(link.record_id, proposed_kinds.get(link.record_id))
                if target not in available | proposed or (link.target_kind is not None and link.target_kind != kind):
                    raise BackupIntegrityError(f"revision {identity}@{revision}: unavailable or wrong-kind target {target}")
            heads[identity], kinds[identity] = revision, record.kind
        available.update(proposed)
        visited.add(sid)
    if visited != set(submissions):
        raise BackupIntegrityError("snapshot: submissions without exactly one event")
    actual = connection.execute("SELECT record_id,kind,head FROM identities ORDER BY record_id").fetchall()
    _equal([list(row) for row in actual], [[key, kinds[key], heads[key]] for key in sorted(heads)], "identity heads")


def _verify(root, marker=None):
    """Share complete read-only backup verification; only internal publication supplies a marker."""
    store = ArtifactStore.open(root)
    names = _layout(store, "snapshot.sqlite3", marker)
    info = _info(_json(_read_file(root, "manifest.json")))
    data = _read_file(root, "snapshot.sqlite3")
    if _reference(data) != info.metadata:
        raise BackupIntegrityError(f"snapshot {root}: metadata size/SHA-256 mismatch")
    if _database(root / "snapshot.sqlite3") != (info.schema_version, info.artifacts):
        raise BackupIntegrityError(f"snapshot {root}: manifest schema/inventory differs from metadata")
    if names != {item.digest for item in info.artifacts}:
        raise BackupIntegrityError(f"objects {root}: filenames differ from manifest inventory")
    for reference in info.artifacts:
        store.verify(reference)
    return info


def _synchronize(store, metadata_name, references):
    """Sync verified files and all layout directories before the completeness boundary."""
    _read_file(store._root, metadata_name, readonly=metadata_name == "snapshot.sqlite3", synchronize=True)
    if metadata_name == "snapshot.sqlite3":
        _read_file(store._root, "manifest.json", synchronize=True)
    for reference in references:
        store._verify_for_commit(reference)
    with store._layout() as (objects, staging):
        os.fsync(objects)
        os.fsync(staging)
    with _path_directory(store._root) as area:
        os.fsync(area)


def _complete(root, marker):
    """Remove the marker only after verification/barriers; report uncertain final acknowledgment."""
    _fault("before_publication")
    with _path_directory(root) as area:
        os.unlink(marker, dir_fd=area)
        # Removal is the logical boundary. A later failure cannot promise rollback.
        try:
            _fault("after_publication")
            os.fsync(area)
            with _path_directory(root.parent) as parent:
                os.fsync(parent)
        except Exception as error:
            raise BackupOperationalError(f"publication {root}: marker removed; final synchronization/acknowledgment uncertain; inspect retained copy") from error


def _capture(source, root):
    """Capture with real incremental SQLite backup, bounded by a five-second monotonic deadline."""
    _write_file(root, "snapshot.sqlite3", b"", readonly=False)
    target = _connect(root / "snapshot.sqlite3")
    deadline = time.monotonic() + 5.0

    def progress(status, remaining, total):
        """Bound SQLite retries and expose real page boundaries for deterministic tests."""
        _fault("capture_progress")
        if time.monotonic() >= deadline:
            raise BackupOperationalError(f"capture {root}: five-second backup deadline exceeded")

    try:
        source.backup(target, pages=64, progress=progress, sleep=0.01)
    finally:
        target.close()
    with _path_directory(root) as area:
        descriptor = os.open("snapshot.sqlite3", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=area)
        try:
            os.fchmod(descriptor, 0o400)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    _fault("after_capture")


def create_backup(source: RecordStore, destination) -> BackupInfo:
    """Capture an open thread-confined store into an absent explicit outside-source directory.

    The captured schema selects the manifest pair. Captures/retries have a fixed
    five-second bound. Artifacts use the largest-object full-byte buffer. Failures retain the destination; no overwrite or cleanup occurs.
    """
    connection = source._require_open()
    path = _path(destination)
    with _errors("create backup", path):
        connection.execute("SELECT 1")  # Enforce SQLite's owning-thread restriction before reservation.
        if connection.in_transaction:
            raise BackupOperationalError("capture source: active transaction is unsupported")
        _outside(path, _path(source._artifacts._root))
        target = _reserve(path, ".backup-incomplete")
        _capture(connection, path)
        # All inventory decisions now use the captured database, never the live source.
        _read_file(path, "snapshot.sqlite3")
        version, references = _database(path / "snapshot.sqlite3")
        for reference in references:
            if target.put(source._artifacts.read(reference)) != reference:
                raise BackupIntegrityError(f"copy object {reference.digest}: changed reference")
            target.verify(reference)
        metadata = _reference(_read_file(path, "snapshot.sqlite3", synchronize=True))
        _write_file(path, "manifest.json", _canonical(_manifest(metadata, references, version)), readonly=True)
        info = _verify(path, ".backup-incomplete")
        _synchronize(target, "snapshot.sqlite3", references)
        _complete(path, ".backup-incomplete")
        return info


def inspect_backup(root) -> BackupInfo:
    """Read-only complete verification without recovery, sidecars, repair or permission changes."""
    path = _path(root)
    with _errors("inspect backup", path):
        return _verify(path)


def _migrate_v1(path, info, provenance_json):
    """Transform only the verified private copy, retaining exact SQL values and source identity.

    The caller owns the durable incomplete marker. Any failure rolls back an
    active transaction and closes the connection, without publishing or cleaning
    retained evidence; even a failed/uncertain COMMIT cannot permit publication.
    """
    manifest = _manifest(info.metadata, info.artifacts, info.schema_version)
    if _info(manifest) != info:
        raise BackupIntegrityError("migration: canonical source manifest identity mismatch")
    identities, _, _, links, _, _, _, states, history = _VERSIONS[2][0]
    connection = _connect(path)
    try:
        # Only this unpublished private copy suspends enforcement. Dropping and
        # recreating the tables avoids SQLite renaming dependent FK/trigger SQL.
        # An explicit foreign_key_check before COMMIT is therefore mandatory.
        connection.execute("PRAGMA foreign_keys=OFF")
        if connection.execute("PRAGMA foreign_keys").fetchone() != (0,):
            raise BackupIntegrityError("migration: cannot suspend foreign keys")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE saved_identities AS SELECT record_id,kind,head FROM main.identities")
        connection.execute("CREATE TEMP TABLE saved_links AS SELECT record_id,revision,ordinal,relationship,target_id,target_revision,target_kind FROM main.record_links")
        connection.execute("DROP TRIGGER revision_states")
        connection.execute("DROP TABLE record_links")
        connection.execute("DROP TABLE identities")
        _fault("migration_transform")
        connection.execute(identities)
        connection.execute(links)
        # SQL copying retains text, NULLs, ordinals and identities without any
        # historical JSON decoding, submission replay or receipt regeneration.
        connection.execute("INSERT INTO identities (record_id,kind,head) SELECT record_id,kind,head FROM temp.saved_identities")
        connection.execute("INSERT INTO record_links (record_id,revision,ordinal,relationship,target_id,target_revision,target_kind) SELECT record_id,revision,ordinal,relationship,target_id,target_revision,target_kind FROM temp.saved_links")
        connection.execute(states)
        connection.execute(history)
        connection.execute("INSERT INTO migration_history VALUES (1,1,2,?,?,?)",
                           (info.backup_id, _canonical(manifest).decode(), provenance_json))
        connection.execute("PRAGMA user_version=2")
        connection.execute("DROP TABLE temp.saved_links")
        connection.execute("DROP TABLE temp.saved_identities")
        validate_schema(connection.execute("PRAGMA user_version").fetchone()[0],
                        [row[0] for row in connection.execute("SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL")])
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise BackupIntegrityError("migration: foreign key violations")
        _application(connection, 2)
        validate_history(connection.execute("SELECT * FROM migration_history").fetchall(),
                         connection.execute("SELECT digest,size FROM artifacts").fetchall())
        connection.execute("COMMIT")
        connection.execute("PRAGMA foreign_keys=ON")
        if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
            raise BackupIntegrityError("migration: cannot restore foreign keys")
        _fault("migration_committed")
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_v2(path, info, provenance_json):
    """Add schema3 on a verified unpublished copy, retaining every scientific/history SQL value.

    Only the administrative table is replaced. SQL copying preserves original
    history text and source provenance exactly; failures retain the incomplete copy.
    """
    from research_pipeline.schema import _HISTORY_V3, _RESOURCE_DDL
    from research_pipeline.resource_ledger import validate_ledger
    manifest = _manifest(info.metadata, info.artifacts, info.schema_version)
    if _info(manifest) != info:
        raise BackupIntegrityError("migration: canonical source manifest identity mismatch")
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE saved_history AS SELECT * FROM main.migration_history")
        connection.execute("DROP TABLE migration_history")
        _fault("migration_transform")
        connection.execute(_HISTORY_V3)
        connection.execute("INSERT INTO migration_history SELECT * FROM temp.saved_history")
        next_id = connection.execute("SELECT count(*) + 1 FROM migration_history").fetchone()[0]
        connection.execute("INSERT INTO migration_history VALUES (?,2,3,?,?,?)",
                           (next_id, info.backup_id, _canonical(manifest).decode(), provenance_json))
        connection.execute("DROP TABLE temp.saved_history")
        for statement in _RESOURCE_DDL:
            connection.execute(statement)
        connection.execute("PRAGMA user_version=3")
        validate_schema(3, [row[0] for row in connection.execute("SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL")])
        _application(connection, 3)
        validate_ledger(connection)
        connection.execute("COMMIT")
        _fault("migration_committed")
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_v3(path, info, provenance_json):
    """Install schema4 in a verified unpublished copy without rewriting historical SQL values.

    Temporal navigation is backfilled from original metadata without decoding or
    registering old generic documents. The source watermark preserves that boundary.
    The durable restore marker stays with the outer publisher across every failure seam.
    """
    from research_pipeline.schema import _HISTORY_V4
    from research_pipeline.claim_use_schema import FRESHNESS_DDL
    from research_pipeline.claim_use_store import validate
    from research_pipeline.resource_ledger import validate_ledger
    manifest = _manifest(info.metadata, info.artifacts, info.schema_version)
    if _info(manifest) != info:
        raise BackupIntegrityError("migration: source manifest identity mismatch")
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE saved_history AS SELECT * FROM main.migration_history")
        connection.execute("DROP TABLE migration_history")
        _fault("migration_transform")
        connection.execute(_HISTORY_V4)
        connection.execute("INSERT INTO migration_history SELECT * FROM temp.saved_history")
        next_id = connection.execute("SELECT count(*) + 1 FROM migration_history").fetchone()[0]
        connection.execute("INSERT INTO migration_history VALUES (?,3,4,?,?,?)",
                           (next_id, info.backup_id, _canonical(manifest).decode(), provenance_json))
        connection.execute("DROP TABLE temp.saved_history")
        for statement in FRESHNESS_DDL:
            connection.execute(statement)
        # Backfill every original revision and selected occurrence, without typed
        # reinterpretation, replay, receipt allocation or registration of old uses.
        connection.execute("""INSERT INTO claim_use_revision_events
            SELECT r.record_id,r.revision,a.event_id FROM revisions r JOIN audit_events a USING(submission_id)""")
        connection.execute("""INSERT INTO claim_use_association_links
            SELECT l.record_id,l.revision,l.ordinal,e.event_id,l.relationship,l.target_id,l.target_revision
            FROM record_links l JOIN claim_use_revision_events e USING(record_id,revision)
            WHERE l.relationship IN ('candidate_claim','assessed_route','affected_record')""")
        connection.execute("INSERT INTO claim_use_origin SELECT 1,coalesce(max(event_id),0) FROM audit_events")
        connection.execute("PRAGMA user_version=4")
        validate_schema(4, [r[0] for r in connection.execute("SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL")])
        _application(connection, 4)
        validate_ledger(connection)
        validate(RecordStore(None, connection, 4), connection)
        connection.execute("COMMIT")
        _fault("migration_committed")
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_v4(path, info, provenance_json):
    """Activate schema-5 policy freshness on a verified unpublished schema-4 copy.

    SQL copying preserves all six administrative fields and every scientific and
    freshness row. Validation includes boundary inspections before commit; failures
    roll back and leave the caller's durable incomplete marker intact.
    """
    from research_pipeline.schema import _HISTORY_V5
    from research_pipeline.claim_use_schema import POLICY_ORIGIN_DDL
    from research_pipeline.claim_use_store import validate
    from research_pipeline.resource_ledger import validate_ledger
    manifest = _manifest(info.metadata, info.artifacts, info.schema_version)
    if info.schema_version != 4 or _info(manifest) != info:
        raise BackupIntegrityError("migration: verified schema-4 source required")
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE saved_history AS SELECT * FROM main.migration_history")
        connection.execute("DROP TABLE migration_history")
        _fault("migration_transform")
        connection.execute(_HISTORY_V5)
        connection.execute("INSERT INTO migration_history SELECT * FROM temp.saved_history")
        next_id = connection.execute("SELECT count(*) + 1 FROM migration_history").fetchone()[0]
        connection.execute("INSERT INTO migration_history VALUES (?,4,5,?,?,?)",
                           (next_id, info.backup_id, _canonical(manifest).decode(), provenance_json))
        connection.execute("DROP TABLE temp.saved_history")
        connection.execute(POLICY_ORIGIN_DDL)
        connection.execute("INSERT INTO claim_use_policy_origin SELECT 1,coalesce(max(event_id),0) FROM audit_events")
        connection.execute("PRAGMA user_version=5")
        validate_schema(5, [r[0] for r in connection.execute("SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL")])
        _application(connection, 5)
        validate_ledger(connection)
        validate(RecordStore(None, connection, 5), connection)
        connection.execute("COMMIT")
        _fault("migration_committed")
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_v5(path, info, provenance_json):
    """Activate schema-6 target-context freshness on a verified unpublished schema-5 copy.

    SQL copying preserves all six administrative fields and every scientific and
    freshness row. Validation includes boundary inspections before commit; failures
    roll back and leave the caller's durable incomplete marker intact.
    """
    from research_pipeline.schema import _HISTORY_V6
    from research_pipeline.claim_use_schema import CONTEXT_ORIGIN_DDL
    from research_pipeline.claim_use_store import validate
    from research_pipeline.resource_ledger import validate_ledger
    manifest = _manifest(info.metadata, info.artifacts, info.schema_version)
    if info.schema_version != 5 or _info(manifest) != info:
        raise BackupIntegrityError("migration: verified schema-5 source required")
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE saved_history AS SELECT * FROM main.migration_history")
        connection.execute("DROP TABLE migration_history")
        _fault("migration_transform")
        connection.execute(_HISTORY_V6)
        connection.execute("INSERT INTO migration_history SELECT * FROM temp.saved_history")
        next_id = connection.execute("SELECT count(*) + 1 FROM migration_history").fetchone()[0]
        connection.execute("INSERT INTO migration_history VALUES (?,5,6,?,?,?)",
                           (next_id, info.backup_id, _canonical(manifest).decode(), provenance_json))
        connection.execute("DROP TABLE temp.saved_history")
        connection.execute(CONTEXT_ORIGIN_DDL)
        connection.execute("INSERT INTO claim_use_context_origin SELECT 1,coalesce(max(event_id),0) FROM audit_events")
        connection.execute("PRAGMA user_version=6")
        validate_schema(6, [r[0] for r in connection.execute("SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL")])
        _application(connection, 6)
        validate_ledger(connection)
        validate(RecordStore(None, connection, 6), connection)
        connection.execute("COMMIT")
        _fault("migration_committed")
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_v6(path, info, provenance_json):
    """Activate schema-7 support-context freshness on a verified unpublished schema-6 copy.

    SQL copying preserves all six administrative fields and every scientific and
    freshness row. Validation includes boundary inspections before commit; failures
    roll back and leave the caller's durable incomplete marker intact.
    """
    from research_pipeline.schema import _HISTORY_V7
    from research_pipeline.claim_use_schema import SUPPORT_CONTEXT_DDL
    from research_pipeline.claim_use_store import validate, _verify_support_contexts
    from research_pipeline.resource_ledger import validate_ledger
    manifest = _manifest(info.metadata, info.artifacts, info.schema_version)
    if info.schema_version != 6 or _info(manifest) != info:
        raise BackupIntegrityError("migration: verified schema-6 source required")
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TEMP TABLE saved_history AS SELECT * FROM main.migration_history")
        connection.execute("DROP TABLE migration_history")
        _fault("migration_transform")
        connection.execute(_HISTORY_V7)
        connection.execute("INSERT INTO migration_history SELECT * FROM temp.saved_history")
        next_id = connection.execute("SELECT count(*) + 1 FROM migration_history").fetchone()[0]
        connection.execute("INSERT INTO migration_history VALUES (?,6,7,?,?,?)",
                           (next_id, info.backup_id, _canonical(manifest).decode(), provenance_json))
        connection.execute("DROP TABLE temp.saved_history")
        for statement in SUPPORT_CONTEXT_DDL:
            connection.execute(statement)
        connection.execute("INSERT INTO claim_use_support_context_origin SELECT 1,coalesce(max(event_id),0) FROM audit_events")
        connection.execute("PRAGMA user_version=7")
        validate_schema(7, [r[0] for r in connection.execute("SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL")])
        _application(connection, 7)
        validate_ledger(connection)
        store = RecordStore(None, connection, 7)
        _verify_support_contexts(store, connection, backfill=True)
        validate(store, connection)
        connection.execute("COMMIT")
        _fault("migration_committed")
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def restore_backup(root, destination, *, target_schema=None, migration_provenance=None) -> RecordStore:
    """Verify and restore into an absent runtime, optionally migrating one step through 1→2→3→4→5→6→7.

    With both options absent, preserve the source schema and metadata bytes.
    Migration requires an ordinary integer next target (2, 3, 4, 5, 6 or 7), a fully verified
    source backup, and explicit CreationProvenance; invalid options raise BackupLayoutError
    before reservation. Original rows/receipts remain unchanged in either mode.
    The independent store opens after verification and publication barriers.
    Failures retain the destination; errors after publication report uncertainty.
    """
    path, destination = _path(root), _path(destination)
    with _errors("restore backup", destination):
        _outside(destination, path)
        provenance_json = None
        option_error = ("migration permits only schema 1 to schema 2, schema 2 to schema 3, schema 3 to schema 4, schema 4 to schema 5, schema 5 to schema 6 or schema 6 to schema 7 with "
                        "the next target_schema and explicit CreationProvenance; "
                        "omit both options for exact restore")
        if target_schema is None:
            if migration_provenance is not None:
                raise BackupLayoutError(option_error)
        else:
            if type(target_schema) is not int or target_schema not in (2, 3, 4, 5, 6, 7) or not isinstance(migration_provenance, CreationProvenance):
                raise BackupLayoutError(option_error)
            try:
                # Frozen instances can still be forged; reconstruct all fields,
                # including strict JSON details, rather than trusting to_dict.
                provenance = CreationProvenance(migration_provenance.actor,
                                                migration_provenance.created_at,
                                                _json(migration_provenance._details_json))
                provenance_json = _canonical(provenance.to_dict()).decode()
            except (AttributeError, ValueError, TypeError, RecursionError, OverflowError) as error:
                raise BackupLayoutError(option_error + f": invalid attribution: {error}") from error
        info = _verify(path)
        if target_schema is not None and (info.schema_version, target_schema) not in ((1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7)):
            raise BackupLayoutError(option_error)
        source = ArtifactStore.open(path)
        target = _reserve(destination, ".restore-incomplete")
        for reference in info.artifacts:
            if target.put(source.read(reference)) != reference:
                raise BackupIntegrityError(f"restore object {reference.digest}: changed reference")
            target.verify(reference)
        data = _read_file(path, "snapshot.sqlite3")
        if _reference(data) != info.metadata:
            raise BackupIntegrityError(f"restore {path}: snapshot changed after inspection")
        _write_file(destination, "metadata.sqlite3", data, readonly=False)
        copied = _read_file(destination, "metadata.sqlite3", readonly=False)
        if _reference(copied) != info.metadata or _database(destination / "metadata.sqlite3") != (info.schema_version, info.artifacts):
            raise BackupIntegrityError(f"restore {destination}: copied database mismatch")
        if target_schema is not None:
            transform = {2: _migrate_v1, 3: _migrate_v2, 4: _migrate_v3, 5: _migrate_v4, 6: _migrate_v5, 7: _migrate_v6}[target_schema]
            transform(destination / "metadata.sqlite3", info, provenance_json)
        # Check the standalone layout before immutable verification so a retained
        # SQLite sidecar can never be ignored and mistaken for a complete copy.
        if _layout(target, "metadata.sqlite3", ".restore-incomplete") != {r.digest for r in info.artifacts}:
            raise BackupIntegrityError(f"restore {destination}: object inventory mismatch")
        if target_schema is not None and _database(destination / "metadata.sqlite3") != (target_schema, info.artifacts):
            raise BackupIntegrityError(f"restore {destination}: migrated database mismatch")
        for reference in info.artifacts:
            target.verify(reference)
        _synchronize(target, "metadata.sqlite3", info.artifacts)
        _complete(destination, ".restore-incomplete")
        try:
            return RecordStore.open(destination)
        except Exception as error:
            raise BackupOperationalError(f"restore {destination}: complete copy published but opening failed") from error
