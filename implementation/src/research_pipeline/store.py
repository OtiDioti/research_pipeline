"""Local controller-only atomic revision submissions over SQLite and immutable bytes."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import sqlite3
import stat

from research_pipeline.artifacts import (
    ArtifactStore, ArtifactLayoutError, ArtifactIntegrityError, _path_directory,
)
from research_pipeline.domain import (
    ArtifactReference, AuditEvent, CreationProvenance, DomainValidationError,
    RecordEnvelope, RecordReference, Submission, SubmissionReceipt,
    _identifier, _integer, _snapshot, _MAX_INTEGER,
)
from research_pipeline.scientific import ScientificContent, decode_envelope
from research_pipeline.schema import _VERSIONS, validate_schema, validate_request_kinds, validate_history


class StoreError(Exception):
    """Base for metadata store failures; artifact and input errors retain their own types."""


class StoreLayoutError(StoreError):
    """The runtime layout or fixed versioned schema is missing or unsupported."""


class StoreClosedError(StoreError):
    """The handle is closed or was invalidated after an unrecoverable transaction failure."""


class RecordNotFoundError(StoreError):
    """An exact record revision does not exist."""


class RevisionConflictError(StoreError):
    """An expected head, proposed revision, or stable kind conflicts with committed state."""


class ReferenceResolutionError(StoreError):
    """An exact target is absent, wrong-kind, or invalid for a constrained typed role."""


class SubmissionConflictError(StoreError):
    """A submission identity has already committed a different canonical request."""


class StoreBusyError(StoreError):
    """SQLite could not obtain a lock within its fixed bounded wait; no automatic retry."""


class StoreDatabaseError(StoreError):
    """SQLite or metadata integrity failed; COMMIT errors may require identity reconciliation."""




def _fault(boundary: str) -> None:
    """Private test seam: before_metadata, after_first_revision, or after_commit.

    Tests may inject exceptions or terminate the process here. This is never a
    controller callback, configuration option, or worker capability.
    """


def _database_error(error: sqlite3.Error, *, committing: bool = False) -> StoreError:
    """Translate lock versus database errors while explaining uncertain commit outcomes."""
    code = getattr(error, "sqlite_errorcode", 0) & 0xff
    kind = StoreBusyError if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) else StoreDatabaseError
    suffix = "; reopen and reconcile the original submission_id before retrying" if committing else ""
    return kind(f"SQLite metadata failure: {error}{suffix}")


def _connect(path):
    """Open only an existing database with checked rollback-journal durability settings."""
    connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=5.0)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
            raise StoreLayoutError("only rollback-journal DELETE mode is supported")
        connection.execute("PRAGMA synchronous=EXTRA")
        connection.execute("PRAGMA foreign_keys=ON")
        for name, expected in (("synchronous", 3), ("foreign_keys", 1), ("busy_timeout", 5000)):
            if connection.execute(f"PRAGMA {name}").fetchone()[0] != expected:
                raise StoreLayoutError(f"required SQLite setting unavailable: {name}")
        return connection
    except BaseException:
        connection.close()
        raise


def _check_database_file(root):
    """Reject interrupted restores before inspecting private metadata or journal layouts."""
    with _path_directory(root) as area:
        try:
            os.stat(".restore-incomplete", dir_fd=area, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise StoreLayoutError("incomplete restore: .restore-incomplete exists; no recovery attempted")
        for suffix in ("-wal", "-shm"):
            try:
                os.stat("metadata.sqlite3" + suffix, dir_fd=area, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise StoreLayoutError("WAL sidecars are unsupported; no conversion attempted")
        try:
            journal = os.stat("metadata.sqlite3-journal", dir_fd=area, follow_symlinks=False)
        except FileNotFoundError:
            journal = None
        if journal is not None and (not stat.S_ISREG(journal.st_mode)
                                    or journal.st_uid != os.geteuid()
                                    or stat.S_IMODE(journal.st_mode) & 0o077):
            raise StoreLayoutError("rollback journal must be an owned private regular file")
        descriptor = os.open("metadata.sqlite3", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=area)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise StoreLayoutError("metadata.sqlite3 must be an owned private regular file")
            header = os.read(descriptor, 100)
            if len(header) != 100 or header[:16] != b"SQLite format 3\0" or header[18:20] != b"\x01\x01":
                raise StoreLayoutError("invalid SQLite header or unsupported journal format")
        finally:
            os.close(descriptor)


def _schema_gate(path):
    """Read only the immutable main-file schema; never infer live data or recover here.

    Version and DDL are fixed at creation. An immutable connection ignores hot
    journals deliberately; only the later operational connection recovers them.
    """
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, isolation_level=None)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        statements = [row[0] for row in connection.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")]
        return validate_schema(version, statements)
    except (sqlite3.Error, ValueError) as error:
        raise StoreLayoutError(f"cannot inspect fixed schema: {error}") from error
    finally:
        connection.close()


class RecordStore:
    """Thread-confined local metadata handle; independent handles serialize writes.

    Use create/open and close or a context manager. No connection or general SQL
    operation is exposed. submit is trusted generic persistence; submit_typed adds
    structural scientific admission. Supported APIs append revisions and links,
    never rewrite exact history. The owner must prevent external file mutation.
    """

    def __init__(self, artifacts, connection, version):
        """Retain private resources and validated schema version; no implicit initialization."""
        self._artifacts = artifacts
        self._connection = connection
        self._schema_version = version

    @classmethod
    def create(cls, root) -> "RecordStore":
        """Create an absent schema-2 store, commit DDL/version together, and sync the layout.

        Existing roots are rejected unchanged. Failed creation may leave an
        incomplete root, which is retained rather than erased or repaired.
        """
        try:
            artifacts = ArtifactStore.create(root)
            path = artifacts._root / "metadata.sqlite3"
            with _path_directory(artifacts._root) as area:
                descriptor = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=area)
                os.close(descriptor)
                connection = _connect(path)
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    for statement in _VERSIONS[2][0]:
                        connection.execute(statement)
                    connection.execute("PRAGMA user_version=2")
                    connection.execute("COMMIT")
                finally:
                    connection.close()
                descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=area)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                os.fsync(area)
            return cls.open(root)
        except ArtifactLayoutError as error:
            raise StoreLayoutError(str(error)) from error
        except OSError as error:
            raise StoreLayoutError(f"create database: {error}") from error
        except sqlite3.Error as error:
            raise _database_error(error) from error

    @classmethod
    def open(cls, root) -> "RecordStore":
        """Gate layout/schema, recover legitimate journals, then validate live administrative history."""
        try:
            artifacts = ArtifactStore.open(root)
            path = artifacts._root / "metadata.sqlite3"
            _check_database_file(artifacts._root)
            version = _schema_gate(path)
            connection = _connect(path)
            try:
                # Live administrative rows must be read after legitimate journal recovery.
                if version == 2:
                    try:
                        validate_history(connection.execute("SELECT * FROM migration_history").fetchall(),
                                         connection.execute("SELECT digest,size FROM artifacts").fetchall())
                    except (ValueError, TypeError, RecursionError, OverflowError) as error:
                        raise StoreLayoutError(f"invalid migration history: {error}") from error
                return cls(artifacts, connection, version)
            except BaseException:
                connection.close()
                raise
        except (ArtifactLayoutError, OSError) as error:
            raise StoreLayoutError(f"open store: {error}") from error
        except sqlite3.Error as error:
            raise _database_error(error) from error

    def _require_open(self):
        """Return the private connection or reject use after close/invalidation."""
        if self._connection is None:
            raise StoreClosedError("record store is closed")
        return self._connection

    def close(self) -> None:
        """Release this connection; repeated closes are harmless on its owning thread."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "RecordStore":
        """Return an open handle for scoped use."""
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Close the handle on both successful and exceptional context exit."""
        self.close()

    @contextmanager
    def _transaction(self, *, write=False):
        """Bound a snapshot or serialized write; rollback failures invalidate the handle.

        COMMIT errors can be ambiguous. A successful COMMIT exits rollback handling
        before the caller's acknowledgment seam, so it is never reported as undone.
        """
        connection = self._require_open()
        committing = False
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            committing = True
            connection.execute("COMMIT")
        except BaseException as error:
            try:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
            except BaseException:
                # Invalidate even if closing also fails; preserve the first diagnostic.
                self._connection = None
                try:
                    connection.close()
                except BaseException:
                    pass
            if isinstance(error, sqlite3.Error):
                raise _database_error(error, committing=committing) from error
            raise

    def put_artifact(self, data: bytes) -> ArtifactReference:
        """Publish verified bytes without registering metadata; failed batches retain orphans."""
        self._require_open()
        return self._artifacts.put(data)

    def read_artifact(self, reference: ArtifactReference) -> bytes:
        """Return actual verified bytes, independently of metadata registration."""
        self._require_open()
        return self._artifacts.read(reference)

    def _receipt(self, connection, submission_id):
        """Reconstruct original commit metadata and membership within the caller's snapshot."""
        row = connection.execute("""SELECT s.fingerprint, e.event_id, e.committed_at, e.provenance_json
            FROM submissions s JOIN audit_events e USING(submission_id) WHERE submission_id=?""", (submission_id,)).fetchone()
        if row is None:
            return None
        pairs = tuple(connection.execute("SELECT record_id, revision FROM revisions WHERE submission_id=? ORDER BY ordinal", (submission_id,)))
        return SubmissionReceipt(submission_id, row[0], row[1], row[2], CreationProvenance.from_dict(json.loads(row[3])), pairs)

    def submit(self, submission: Submission) -> SubmissionReceipt:
        """Append a trusted generic batch, or return an identical request's old receipt.

        This checks generic storage contracts, not scientific target content.
        Reconcile acknowledgment/COMMIT uncertainty using the original submission_id
        after reopening. Never substitute a new identity to resolve that uncertainty.
        """
        return self._commit_submission(self._normalize_submission(submission), ())

    def submit_typed(self, submission: Submission) -> SubmissionReceipt:
        """Atomically admit four-kind scientific members and exact constrained targets.

        Reconstruct and decode every member before reconciliation; malformed members
        raise domain/codec errors. New requests check typed target closure inside the
        write transaction, raising ReferenceResolutionError for invalid targets.
        Exact retries acknowledge the original commit without rechecking targets or
        bytes, including identical requests originally committed through submit.
        """
        submission = self._normalize_submission(submission)
        for record in submission.records:
            decode_envelope(record)
        required = tuple(reference for record in submission.records
                         for reference in self._scientific_references(record))
        return self._commit_submission(submission, required)

    def _normalize_submission(self, submission):
        """Detach a request and reject forged nested values before either commit entry point."""
        self._require_open()
        if type(submission) is not Submission:
            raise DomainValidationError("submission: expected Submission")
        try:
            submission = Submission.from_dict(submission.to_dict())
        except (AttributeError, TypeError, ValueError, RecursionError) as error:
            if isinstance(error, DomainValidationError):
                raise
            raise DomainValidationError("submission: malformed nested typed value") from error
        return submission

    def _commit_submission(self, submission, required):
        """Commit a normalized request with immutable typed requirements via one algorithm.

        Reconciliation precedes schema-kind admission and all availability/CAS checks. Exact revisions and links
        are append-only under supported APIs; serialized target inspection and CAS
        share this transaction even when independent handles advance heads. The owner
        must still prevent external database/file mutation.
        """
        canonical = _snapshot({"fingerprint_version": 1, "submission": submission.to_dict()}, "request")
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self._transaction(write=True) as connection:
            # Resolve idempotency before heads, references or artifact availability.
            old = connection.execute("SELECT request_json FROM submissions WHERE submission_id=?", (submission.submission_id,)).fetchone()
            if old is not None:
                if old[0] != canonical:
                    raise SubmissionConflictError(f"submission {submission.submission_id}: different canonical request")
                return self._receipt(connection, submission.submission_id)
            validate_request_kinds(submission, self._schema_version)
            self._check_batch(connection, submission)
            self._check_scientific_targets(connection, submission, required)
            _fault("before_metadata")
            connection.execute("INSERT INTO submissions VALUES (?, ?, ?)", (submission.submission_id, canonical, fingerprint))
            for ordinal, record in enumerate(submission.records):
                if submission.expected_heads[record.record_id] == 0:
                    connection.execute("INSERT INTO identities VALUES (?, ?, ?)", (record.record_id, record.kind, record.revision))
                connection.execute("INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                   (record.record_id, record.revision, submission.submission_id, ordinal,
                                    _snapshot(record.content, "content"), _snapshot(record.provenance.to_dict(), "provenance"),
                                    record.operational_status, record.scientific_disposition))
                if ordinal == 0:
                    _fault("after_first_revision")
            # All exact revisions exist before links, permitting forward edges/cycles.
            for record in submission.records:
                self._insert_links(connection, record)
                connection.execute("UPDATE identities SET head=? WHERE record_id=?", (record.revision, record.record_id))
            committed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
            connection.execute("INSERT INTO audit_events(submission_id,event_type,committed_at,provenance_json) VALUES (?, 'submission_committed', ?, ?)",
                               (submission.submission_id, committed_at, _snapshot(submission.provenance.to_dict(), "provenance")))
            receipt = self._receipt(connection, submission.submission_id)
        # A failure here is lost acknowledgment, not a rolled-back submission.
        _fault("after_commit")
        return receipt

    def _check_batch(self, connection, submission):
        """Check relevant heads and exact targets, then verify and sync distinct objects."""
        proposed = {(record.record_id, record.revision): record.kind for record in submission.records}
        expectations = submission.expected_heads
        objects = {}
        for record in submission.records:
            row = connection.execute("SELECT head, kind FROM identities WHERE record_id=?", (record.record_id,)).fetchone()
            expected = expectations[record.record_id]
            if ((row[0] if row else 0) != expected or expected == _MAX_INTEGER
                    or record.revision != expected + 1 or (row and row[1] != record.kind)):
                raise RevisionConflictError(f"record {record.record_id}: head, next revision, or stable kind conflict")
            for reference in record.record_references:
                target = proposed.get((reference.record_id, reference.revision))
                if target is None:
                    found = connection.execute("""SELECT i.kind FROM revisions r JOIN identities i USING(record_id)
                        WHERE r.record_id=? AND r.revision=?""", (reference.record_id, reference.revision)).fetchone()
                    target = found[0] if found else None
                if target is None or (reference.target_kind is not None and reference.target_kind != target):
                    raise ReferenceResolutionError(f"{reference.relationship} target {reference.record_id}@{reference.revision}: absent or wrong kind")
            for reference in record.artifact_references:
                if reference.digest in objects and objects[reference.digest].size != reference.size:
                    raise ArtifactIntegrityError(f"object {reference.digest}: inconsistent sizes in submission")
                objects[reference.digest] = reference
        for reference in objects.values():
            self._artifacts._verify_for_commit(reference)

    @staticmethod
    def _scientific_references(record):
        """Return constrained roles from an already decoded envelope, excluding input edges."""
        return tuple(reference for reference in record.record_references
                     if reference.relationship in ("context", "premise", "conclusion", "evidence", "target_claim"))

    def _check_scientific_targets(self, connection, submission, required):
        """Resolve exact typed target closure from batch then historical metadata, without bytes.

        Each incoming edge checks kind even for cached targets. Invalid historical
        codecs are chained as reference errors; generic input_record edges are not
        traversed. All work stays inside the caller's serialized write transaction.
        """
        proposed = {(record.record_id, record.revision): record for record in submission.records}
        visited = {}
        worklist = list(required)
        while worklist:
            reference = worklist.pop()
            key = (reference.record_id, reference.revision)
            diagnostic = f"{reference.relationship} target {reference.record_id}@{reference.revision}"
            target = visited.get(key)
            if target is None:
                target = proposed.get(key)
                if target is None:
                    try:
                        target = self._metadata_envelope(connection, *key)
                    except RecordNotFoundError as error:
                        raise ReferenceResolutionError(f"{diagnostic}: absent") from error
                    except DomainValidationError as error:
                        raise ReferenceResolutionError(f"{diagnostic}: invalid metadata: {error}") from error
            if target.kind != reference.target_kind:
                raise ReferenceResolutionError(f"{diagnostic}: expected {reference.target_kind}, found {target.kind}")
            if key in visited:
                continue
            try:
                decode_envelope(target)
            except DomainValidationError as error:
                raise ReferenceResolutionError(f"{diagnostic}: invalid scientific content: {error}") from error
            # Mark before enqueueing: repeated roles and provisional cycles terminate.
            visited[key] = target
            worklist.extend(self._scientific_references(target))

    def _insert_links(self, connection, record):
        """Persist ordered duplicate links without rewriting any historical revision."""
        for ordinal, reference in enumerate(record.record_references):
            connection.execute("INSERT INTO record_links VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (record.record_id, record.revision, ordinal, reference.relationship,
                                reference.record_id, reference.revision, reference.target_kind))
        for ordinal, reference in enumerate(record.artifact_references):
            existing = connection.execute("SELECT size FROM artifacts WHERE digest=?", (reference.digest,)).fetchone()
            if existing is None:
                connection.execute("INSERT INTO artifacts VALUES (?, ?)", (reference.digest, reference.size))
            elif existing[0] != reference.size:
                raise ArtifactIntegrityError(f"object {reference.digest}: registered size differs")
            connection.execute("INSERT INTO artifact_links VALUES (?, ?, ?, ?, ?)",
                               (record.record_id, record.revision, ordinal, reference.digest, reference.size))

    def _envelope(self, connection, record_id, revision):
        """Rebuild from normalized rows and verify direct artifacts in one read snapshot."""
        envelope = self._metadata_envelope(connection, record_id, revision)
        for reference in envelope.artifact_references:
            self._artifacts.verify(reference)
        return envelope

    def _metadata_envelope(self, connection, record_id, revision):
        """Reconstruct detached exact metadata/ordered links in a supplied snapshot, without bytes.

        Missing revisions raise RecordNotFoundError. This private reconstruction is
        used for typed admission; public revision reads additionally verify artifacts.
        """
        row = connection.execute("""SELECT i.kind,r.content_json,r.provenance_json,r.operational_status,r.scientific_disposition
            FROM revisions r JOIN identities i USING(record_id) WHERE r.record_id=? AND r.revision=?""", (record_id, revision)).fetchone()
        if row is None:
            raise RecordNotFoundError(f"record {record_id}@{revision}: absent")
        references = tuple(RecordReference(*link) for link in connection.execute(
            "SELECT target_id,target_revision,relationship,target_kind FROM record_links WHERE record_id=? AND revision=? ORDER BY ordinal", (record_id, revision)))
        artifacts = tuple(ArtifactReference(*link) for link in connection.execute(
            "SELECT digest,size FROM artifact_links WHERE record_id=? AND revision=? ORDER BY ordinal", (record_id, revision)))
        return RecordEnvelope(record_id, revision, row[0], json.loads(row[1]), CreationProvenance.from_dict(json.loads(row[2])),
                              references, artifacts, row[3], row[4])

    def get_revision(self, record_id: str, revision: int) -> RecordEnvelope:
        """Return an exact revision with verified direct artifacts, or raise if absent."""
        _identifier(record_id, "record_id")
        _integer(revision, "revision", 1)
        with self._transaction() as connection:
            return self._envelope(connection, record_id, revision)

    def get_typed_revision(self, record_id: str, revision: int) -> tuple[RecordEnvelope, ScientificContent]:
        """Return an exact detached envelope and decoded value, verifying direct artifacts.

        Preserve missing-revision/artifact errors; absent discriminators raise
        NotTypedContentError and other codec failures raise DomainValidationError.
        This checks local coherence, not past admission or scientific validity.
        """
        envelope = self.get_revision(record_id, revision)
        return envelope, decode_envelope(envelope)

    def history(self, record_id: str) -> tuple[RecordEnvelope, ...]:
        """Return revision-ascending verified history; an absent identity has empty history."""
        _identifier(record_id, "record_id")
        with self._transaction() as connection:
            revisions = connection.execute("SELECT revision FROM revisions WHERE record_id=? ORDER BY revision", (record_id,)).fetchall()
            return tuple(self._envelope(connection, record_id, row[0]) for row in revisions)

    def head(self, record_id: str) -> int | None:
        """Return the current revision number or None; this metadata read proves no availability."""
        _identifier(record_id, "record_id")
        with self._transaction() as connection:
            row = connection.execute("SELECT head FROM identities WHERE record_id=?", (record_id,)).fetchone()
            return row[0] if row else None

    def get_submission(self, submission_id: str) -> SubmissionReceipt | None:
        """Return original commit metadata or None, even if attached artifacts are damaged."""
        _identifier(submission_id, "submission_id")
        with self._transaction() as connection:
            return self._receipt(connection, submission_id)

    def audit_events(self) -> tuple[AuditEvent, ...]:
        """Return detached events in event-id order from a consistent metadata-only snapshot."""
        with self._transaction() as connection:
            events = []
            for event_id, submission_id, event_type, committed_at, provenance in connection.execute(
                    "SELECT event_id,submission_id,event_type,committed_at,provenance_json FROM audit_events ORDER BY event_id"):
                receipt = self._receipt(connection, submission_id)
                events.append(AuditEvent(event_id, submission_id, event_type, committed_at,
                                         CreationProvenance.from_dict(json.loads(provenance)), receipt.revisions))
            return tuple(events)
