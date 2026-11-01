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
from research_pipeline.assessment import (
    AssessmentContent, Issue, Review, decode_envelope as _decode_assessment_envelope,
)
from research_pipeline.scientific import (
    Claim, Evidence, Justification, NotTypedContentError, ResearchContext, ScientificContent,
    decode_envelope as _decode_scientific_envelope,
)
from research_pipeline.work_product import (
    WorkProductManifest, decode_envelope as _decode_work_product_envelope,
)
from research_pipeline.source import Source, decode_envelope as _decode_source_envelope
from research_pipeline.corpus import (
    CorpusManifest, decode_envelope as _decode_corpus_envelope, _links as _corpus_links,
    _validate_selection, _validate_successor,
)
from research_pipeline.project import (
    ProjectSetup, decode_envelope as _decode_project_envelope, _links as _project_links,
    _validate_dossier, _validate_successor as _validate_project_successor,
)
from research_pipeline.schema import _VERSIONS, validate_schema, validate_request_kinds, validate_history
from research_pipeline.snapshot import (
    SnapshotSelection, SnapshotLimits, DetachedSnapshot, SnapshotLimitError,
    SnapshotIntegrityError, _bounded_json, _canonical, _strict_json, _classification,
    _scope, _schema_identity, _commit,
)


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
    """Private submission and capture observation seam, never a caller callback.

    Submission boundaries are before_metadata, after_first_revision and after_commit.
    Capture boundaries are snapshot_after_first_read and snapshot_after_head_resolution.
    Tests may coordinate independent handles or inject failures at these points;
    no operational setting or worker capability exposes this seam.
    """


def _decode_typed_envelope(envelope: RecordEnvelope) -> ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest | ProjectSetup:
    """Decode a normalized envelope using one explicit format, without inference or fallback.

    Missing markers retain NotTypedContentError; other format/codec failures raise
    DomainValidationError. Scientific, assessment, work-product, Source, corpus and project codecs
    validate states and ordered links.
    """
    content = envelope.content
    if "format" not in content:
        raise NotTypedContentError("typed content: missing format discriminator")
    discriminator = content["format"]
    if type(discriminator) is str:
        if discriminator == "research_pipeline.scientific_content":
            return _decode_scientific_envelope(envelope)
        if discriminator == "research_pipeline.assessment_content":
            return _decode_assessment_envelope(envelope)
        if discriminator == "research_pipeline.work_product_content":
            return _decode_work_product_envelope(envelope)
        if discriminator == "research_pipeline.source_content":
            return _decode_source_envelope(envelope)
        if discriminator == "research_pipeline.corpus_content":
            return _decode_corpus_envelope(envelope)
        if discriminator == "research_pipeline.project_content":
            return _decode_project_envelope(envelope)
    raise DomainValidationError("format: unsupported typed content format")


def _database_error(error: sqlite3.Error, *, committing: bool = False, reconciliation_id="submission_id") -> StoreError:
    """Translate SQLite errors, naming the original scientific or resource reconciliation identity."""
    code = getattr(error, "sqlite_errorcode", 0) & 0xff
    kind = StoreBusyError if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) else StoreDatabaseError
    suffix = f"; reopen and reconcile the original {reconciliation_id} before retrying" if committing else ""
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
    structural scientific and assessment admission. Supported APIs append revisions and links,
    never rewrite exact history. The owner must prevent external file mutation.
    """

    def __init__(self, artifacts, connection, version):
        """Retain private resources and validated schema version; no implicit initialization."""
        self._artifacts = artifacts
        self._connection = connection
        self._schema_version = version

    @classmethod
    def create(cls, root, *, schema_version=2) -> "RecordStore":
        """Create an absent schema2 (default) or explicit schema3 store and sync its layout.

        Only ordinary integer versions 2 and 3 are accepted, before root reservation.
        Existing roots are rejected unchanged. Failed creation may leave an
        incomplete root, which is retained rather than erased or repaired.
        """
        if type(schema_version) is not int or schema_version not in (2, 3):
            raise StoreLayoutError("creation requires ordinary integer schema_version 2 or 3")
        try:
            artifacts = ArtifactStore.create(root)
            path = artifacts._root / "metadata.sqlite3"
            with _path_directory(artifacts._root) as area:
                descriptor = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=area)
                os.close(descriptor)
                connection = _connect(path)
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    for statement in _VERSIONS[schema_version][0]:
                        connection.execute(statement)
                    connection.execute(f"PRAGMA user_version={schema_version}")
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
        """Gate fixed schema, recover legitimate journals, then validate history and schema3 ledger."""
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
                if version == 3:
                    from research_pipeline.resource_ledger import validate_ledger
                    try:
                        # Read all live invariants in one snapshot only after the
                        # operational connection has recovered legitimate journals.
                        connection.execute("BEGIN")
                        validate_ledger(connection)
                        connection.execute("COMMIT")
                    except (ValueError, TypeError, RecursionError, OverflowError) as error:
                        raise StoreLayoutError(f"invalid resource ledger: {error}") from error
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
    def _transaction(self, *, write=False, reconciliation_id="submission_id"):
        """Bound a snapshot or serialized write; rollback failures invalidate the handle.

        reconciliation_id selects the original submission or resource operation
        named in an uncertain COMMIT diagnostic. A successful COMMIT exits rollback handling
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
                raise _database_error(error, committing=committing, reconciliation_id=reconciliation_id) from error
            raise

    def create_resource_account(self, request):
        """Declare a project ceiling atomically; return its original ResourceReceipt on exact retry."""
        from research_pipeline.resource_ledger import mutate
        return mutate(self, request, "create_account")

    def allocate_resources(self, request):
        """Create a child and its immutable purpose allocation without double charging descendants."""
        from research_pipeline.resource_ledger import mutate
        return mutate(self, request, "allocate")

    def reserve_resources(self, request):
        """Commit conservative maxima before work; no execution, usage settlement or release occurs."""
        from research_pipeline.resource_ledger import mutate
        return mutate(self, request, "reserve")

    def observe_resource_usage(self, request):
        """Append trusted cumulative usage or uncertainty; observations never release liability."""
        from research_pipeline.resource_ledger import mutate
        return mutate(self, request, "observe")

    def reconcile_resource_usage(self, request):
        """Settle an original reservation with explicit evidence and its latest settlement predecessor."""
        from research_pipeline.resource_ledger import mutate
        return mutate(self, request, "reconcile")

    def get_resource_operation(self, operation_id):
        """Inspect an original accounting outcome after uncertainty, returning its receipt or None."""
        from research_pipeline.resource_ledger import get_operation
        return get_operation(self, operation_id)

    def inspect_resources(self, *, limits):
        """Return one complete detached ledger snapshot or fail explicit inspection limits."""
        from research_pipeline.resource_ledger import inspect
        return inspect(self, limits)

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
        """Atomically admit scientific, assessment, work-product, Source, corpus and project content with exact target checks.

        Reconstruct and decode every member before reconciliation; malformed members
        raise domain/codec errors. New requests check typed target closure inside the
        write transaction, raising ReferenceResolutionError for invalid targets.
        Exact retries acknowledge the original commit without rechecking targets or
        bytes, including identical requests originally committed through submit.
        """
        submission = self._normalize_submission(submission)
        decoded = tuple(_decode_typed_envelope(record) for record in submission.records)
        return self._commit_submission(submission, decoded)

    def _check_prepared_typed(self, submission):
        """Preview typed admission in one read snapshot without reserving IDs or writing metadata.

        Object verification/synchronization is allowed. This snapshot cannot promise
        eventual admission: commit must repeat the checks under its write lock. A
        used ID belongs to reconciliation through submit_typed, never preparation.
        """
        submission = self._normalize_submission(submission)
        decoded = tuple(_decode_typed_envelope(record) for record in submission.records)
        with self._transaction() as connection:
            if self._receipt(connection, submission.submission_id) is not None:
                raise SubmissionConflictError(
                    f"submission {submission.submission_id}: already used; retry the saved proposal directly")
            validate_request_kinds(submission, self._schema_version)
            self._check_batch(connection, submission)
            self._check_typed_targets(connection, submission, decoded)
        return submission

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

    def _commit_submission(self, submission, decoded: tuple[ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest | ProjectSetup, ...]):
        """Commit a normalized request and its ordered decoded values via one algorithm.

        Generic requests supply an empty tuple; typed requests supply one immutable
        value per member. Local decoding precedes this shared reconciliation path.

        Reconciliation precedes schema-kind admission and all availability/CAS checks.
        Exact revisions and links are append-only; serialized target inspection and CAS
        share this transaction even when independent handles advance heads. The owner
        must still prevent external database/file mutation.
        """
        canonical = _snapshot({"fingerprint_version": 1, "submission": submission.to_dict()}, "request")
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self._transaction(write=True) as connection:
            # Reconcile before heads, targets, route membership or artifact availability.
            old = connection.execute("SELECT request_json FROM submissions WHERE submission_id=?", (submission.submission_id,)).fetchone()
            if old is not None:
                if old[0] != canonical:
                    raise SubmissionConflictError(f"submission {submission.submission_id}: different canonical request")
                return self._receipt(connection, submission.submission_id)
            validate_request_kinds(submission, self._schema_version)
            self._check_batch(connection, submission)
            self._check_typed_targets(connection, submission, decoded)
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
    def _typed_references(value: ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest | ProjectSetup) -> tuple[
            tuple[RecordReference, ...], tuple[RecordReference, ...]]:
        """Partition decoded semantic roles into constrained and shallow generic references.

        Generic declarations confer no typed validity: never inspect their payloads,
        outgoing edges or attachments, even when they name a supported typed kind.
        Manifest context/claims/supersedes are constrained; its other roles are shallow.
        Review context_manifest stays shallow even for a typed manifest target.
        Source predecessors/reports/evidence are constrained; related sources and
        reported executions stay shallow. All corpus and project projected record roles are constrained.
        """
        if type(value) is ResearchContext:
            return (), ()
        if type(value) is Claim:
            return (value.context,), ()
        if type(value) is Justification:
            return (value.context, *value.premises, *value.conclusions, *value.evidence), ()
        if type(value) is Evidence:
            return (value.context, *value.target_claims), value.input_records
        if type(value) is Review:
            return ((value.candidate_claim, value.target_context,
                     *(ref for ref in value.reported_checks if ref.relationship == "reported_evidence"),
                     *(route.justification for route in value.route_assessments)),
                    (value.context_manifest, value.authorization_policy,
                     *(ref for ref in value.reported_checks if ref.relationship == "reported_tool_execution")))
        if type(value) is Issue:
            return value.supporting_evidence, value.affected_records
        if type(value) is WorkProductManifest:
            constrained = tuple(ref for ref in (value.context, *value.linked_claims, value.supersedes)
                                if ref is not None)
            shallow = tuple(ref for ref in (value.task, value.branch, value.run,
                                           *value.linked_sources, *value.build_dependencies)
                            if ref is not None)
            return constrained, shallow
        if type(value) is Source:
            checks = (*value.reading.checks, *(check for statement in value.statements for check in statement.checks))
            constrained = tuple(ref for ref in (value.supersedes, value.reading.report,
                                *(ref for ref in checks if ref.relationship == "reported_evidence"))
                                if ref is not None)
            shallow = (*(item.reference for item in value.related_sources),
                       *(ref for ref in checks if ref.relationship == "reported_tool_execution"))
            return constrained, shallow
        if type(value) is CorpusManifest:
            return _corpus_links(value)[0], ()
        if type(value) is ProjectSetup:
            return _project_links(value)[0], ()
        raise DomainValidationError("content: expected a decoded scientific, assessment, work-product, Source, corpus or project value")

    def _check_typed_targets(self, connection, submission,
                             decoded: tuple[ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest | ProjectSetup, ...]):
        """Validate exact constrained closure and review routes within the caller's snapshot.

        Resolve batch members before historical metadata, never reading transitive
        artifact bytes. Every incoming edge checks kind, independently of caching.
        Historical decoding/reconstruction failures become chained reference errors;
        generic edges check only existence and declared kind and are never enqueued.
        Historical manifest supersession receives the same local and recursive checks.
        Sources additionally require stable work identity and explicit typed predecessors;
        reading-report edges check product kind even when a target is cached. Corpus
        selections are checked per occurrence; complete histories are checked in order.
        Project dossiers are checked against their own pins after corpus validation,
        including every historical snapshot and every incoming document/location role.
        """
        if not decoded:
            return
        proposed = {(record.record_id, record.revision): record for record in submission.records}
        envelopes = dict(proposed)
        values = {(record.record_id, record.revision): value
                  for record, value in zip(submission.records, decoded)}
        processed = set()
        worklist = list(proposed)
        while worklist:
            key = worklist.pop()
            if key in processed:
                continue
            # Decoding and outgoing-edge processing are separate caches. Mark before
            # following edges so descriptive scientific/self cycles terminate.
            processed.add(key)
            value = values[key]
            if type(value) is Source and key[1] > 1:
                # A missing supersedes must not hide a typed predecessor. Inspect only
                # metadata, only on constrained closure, after original-ID reconciliation
                # and ordinary CAS. Legacy generic captures receive no certification.
                previous_key = (key[0], key[1] - 1)
                diagnostic = f"source predecessor {previous_key[0]}@{previous_key[1]}"
                try:
                    previous = envelopes.get(previous_key)
                    if previous is None:
                        previous = self._metadata_envelope(connection, *previous_key)
                        envelopes[previous_key] = previous
                    if (previous.content.get("format") == "research_pipeline.source_content"
                            or value.supersedes is not None):
                        if previous_key not in values:
                            values[previous_key] = _decode_source_envelope(previous)
                        predecessor = values[previous_key]
                        if type(predecessor) is not Source:
                            raise DomainValidationError("predecessor must be typed Source")
                        if predecessor.work_id != value.work_id:
                            raise DomainValidationError("work_id: must equal typed predecessor")
                        if value.supersedes is None:
                            raise DomainValidationError("supersedes: required for a typed predecessor")
                        if previous_key not in processed:
                            worklist.append(previous_key)
                except (RecordNotFoundError, ValueError, TypeError, RecursionError, OverflowError) as error:
                    raise ReferenceResolutionError(f"{diagnostic}: invalid typed history: {error}") from error
            constrained, generic = self._typed_references(value)
            for reference in generic:
                target_key = (reference.record_id, reference.revision)
                target = proposed.get(target_key)
                if target is not None:
                    kind = target.kind
                else:
                    row = connection.execute("""SELECT i.kind FROM revisions r JOIN identities i USING(record_id)
                        WHERE r.record_id=? AND r.revision=?""", target_key).fetchone()
                    kind = row[0] if row else None
                if kind is None or (reference.target_kind is not None and reference.target_kind != kind):
                    raise ReferenceResolutionError(
                        f"{reference.relationship} target {reference.record_id}@{reference.revision}: absent or wrong kind")
            for reference in constrained:
                target_key = (reference.record_id, reference.revision)
                diagnostic = f"{reference.relationship} target {reference.record_id}@{reference.revision}"
                if type(value) is CorpusManifest:
                    diagnostic = f"corpus {key[0]}@{key[1]} {diagnostic}"
                if type(value) is ProjectSetup:
                    diagnostic = f"project {key[0]}@{key[1]} {diagnostic}"
                target = envelopes.get(target_key)
                if target is None:
                    try:
                        target = self._metadata_envelope(connection, *target_key)
                    except RecordNotFoundError as error:
                        raise ReferenceResolutionError(f"{diagnostic}: absent") from error
                    except (ValueError, TypeError, RecursionError, OverflowError) as error:
                        raise ReferenceResolutionError(f"{diagnostic}: invalid metadata: {error}") from error
                    envelopes[target_key] = target
                if target.kind != reference.target_kind:
                    raise ReferenceResolutionError(f"{diagnostic}: expected {reference.target_kind}, found {target.kind}")
                if target_key not in values:
                    try:
                        values[target_key] = _decode_typed_envelope(target)
                    except DomainValidationError as error:
                        raise ReferenceResolutionError(f"{diagnostic}: invalid typed content: {error}") from error
                # Role-specific checks belong to each incoming edge, not the cache fill.
                if (type(value) is Source and reference.relationship == "reading_report"
                        and (type(values[target_key]) is not WorkProductManifest
                             or values[target_key].product_kind != "reading_report")):
                    raise ReferenceResolutionError(f"{diagnostic}: expected manifest product_kind reading_report")
                if target_key not in processed:
                    worklist.append(target_key)

        # Metadata-only closure includes every mandatory corpus predecessor. Validate
        # every reachable snapshot, including generic-admitted typed payloads, without
        # turning either a prior receipt or a shallow occurrence into certification.
        corpora = {}
        for key, value in values.items():
            if type(value) is CorpusManifest:
                corpora.setdefault(key[0], {})[key[1]] = value
        for identity, revisions in corpora.items():
            used_ids = set()
            previous = None
            for revision in sorted(revisions):
                value = revisions[revision]
                diagnostic = f"corpus {identity}@{revision}"
                try:
                    _validate_selection(value, values)
                    if revision > 1 and revision - 1 not in revisions:
                        raise DomainValidationError("supersedes: incomplete corpus history")
                    _validate_successor(value, previous, used_ids)
                except DomainValidationError as error:
                    predecessor = (f" supersedes target {identity}@{revision - 1}"
                                   if revision > 1 else " baseline")
                    raise ReferenceResolutionError(f"{diagnostic}{predecessor}: {error}") from error
                previous = value

        # Every predecessor is constrained. A coherent latest snapshot cannot hide
        # generic-admitted history, and each document role is checked on cache hits.
        projects = {}
        for key, value in values.items():
            if type(value) is ProjectSetup:
                projects.setdefault(key[0], {})[key[1]] = value
        for identity, revisions in projects.items():
            previous = None
            for revision in sorted(revisions):
                value = revisions[revision]
                try:
                    if revision > 1 and revision - 1 not in revisions:
                        raise DomainValidationError(f"supersedes target {identity}@{revision - 1}: incomplete project history")
                    _validate_project_successor(value, previous)
                    _validate_dossier(value, values)
                except DomainValidationError as error:
                    raise ReferenceResolutionError(f"project {identity}@{revision}: {error}") from error
                previous = value

        for record, value in zip(submission.records, decoded):
            if type(value) is not Review:
                continue
            candidate = (value.candidate_claim.record_id, value.candidate_claim.revision)
            for assessment in value.route_assessments:
                route_key = (assessment.justification.record_id, assessment.justification.revision)
                route = values[route_key]
                # Roles differ (candidate_claim versus conclusion); only exact identity
                # and revision define membership, for every reported route outcome.
                if not any((ref.record_id, ref.revision) == candidate for ref in route.conclusions):
                    raise ReferenceResolutionError(
                        f"review {record.record_id}@{record.revision}: assessed_route target "
                        f"{route_key[0]}@{route_key[1]} does not conclude candidate {candidate[0]}@{candidate[1]}")

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

    def _snapshot_record(self, connection, key, limits, remaining_metadata, remaining_references):
        """Preflight one exact revision before fetching JSON/links; return bounded detached metadata.

        Counts include repeated record/artifact links. BLOB lengths count UTF-8
        bytes, including variable-width links and commit metadata. This private
        capture path leaves admission and existing public read semantics unchanged.
        """
        row = connection.execute("""SELECT
            length(CAST(i.kind AS BLOB)), length(CAST(r.content_json AS BLOB)),
            length(CAST(r.provenance_json AS BLOB)),
            length(CAST(coalesce(r.operational_status,'') AS BLOB)),
            length(CAST(coalesce(r.scientific_disposition,'') AS BLOB)),
            length(CAST(r.submission_id AS BLOB)), length(CAST(a.committed_at AS BLOB)),
            length(CAST(s.fingerprint AS BLOB))
            FROM revisions r LEFT JOIN identities i USING(record_id)
            LEFT JOIN submissions s USING(submission_id)
            LEFT JOIN audit_events a USING(submission_id)
            WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        if row is None:
            raise RecordNotFoundError(f"record {key[0]}@{key[1]}: absent")
        if any(type(n) is not int or n < 0 for n in row):
            raise SnapshotIntegrityError(f"{key[0]}@{key[1]}: missing or invalid commit/record metadata")
        # Account repeated JSON reads by the unchanged envelope helper as well.
        fetched = 2 * (sum(row) + len(key[0]) + len(str(key[1])))
        if fetched > limits.max_record_bytes or fetched > remaining_metadata:
            raise SnapshotLimitError(f"{key[0]}@{key[1]}: record/metadata byte preflight exceeded")
        reference_count = 0
        for table, columns in (("record_links", ("relationship", "target_id", "target_revision", "target_kind")),
                               ("artifact_links", ("digest", "size"))):
            count = connection.execute(
                f"SELECT count(*) FROM {table} WHERE record_id=? AND revision=?", key).fetchone()[0]
            reference_count += count
            if reference_count > remaining_references:
                raise SnapshotLimitError("max_references exceeded before fetching links")
            lengths = ",".join(f"length(CAST(coalesce({column},'') AS BLOB))" for column in columns)
            cursor = connection.execute(
                f"SELECT CASE WHEN typeof(ordinal)='integer' THEN ordinal ELSE NULL END,{lengths} FROM {table} WHERE record_id=? AND revision=? ORDER BY ordinal", key)
            for expected in range(count):
                link = cursor.fetchone()
                if link is None or type(link[0]) is not int or link[0] != expected:
                    raise SnapshotIntegrityError(f"{key[0]}@{key[1]}: noncontiguous {table} ordinals")
                fetched += sum(link[1:]) + len(str(link[0]))
                if fetched > limits.max_record_bytes or fetched > remaining_metadata:
                    raise SnapshotLimitError(f"{key[0]}@{key[1]}: link metadata bytes exceeded")
            if cursor.fetchone() is not None:
                raise SnapshotIntegrityError("link count changed inside snapshot")
        raw = connection.execute("""SELECT r.content_json,r.provenance_json,
            r.submission_id,a.committed_at,s.fingerprint FROM revisions r
            JOIN submissions s USING(submission_id) JOIN audit_events a USING(submission_id)
            WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        try:
            _strict_json(raw[0])
            _strict_json(raw[1])
            envelope = self._metadata_envelope(connection, *key)
            commit = dict(zip(("submission_id", "committed_at", "fingerprint"), raw[2:]))
            _commit(commit)
            if _canonical(envelope.content) != raw[0] or _canonical(envelope.provenance.to_dict()) != raw[1]:
                raise SnapshotIntegrityError("noncanonical content/provenance structure")
            envelope_json = _bounded_json(envelope.to_dict(), limits.max_record_bytes, "envelope")
            entry = {"record_id": key[0], "revision": key[1], "content_json": raw[0],
                     "provenance_json": raw[1], "envelope_json": envelope_json,
                     "classification": _classification(envelope, _decode_typed_envelope),
                     "commit": commit, "fetched_bytes": fetched}
            _bounded_json(entry, min(limits.max_record_bytes, remaining_metadata - fetched), "record metadata")
            return envelope, entry, fetched, reference_count
        except (DomainValidationError, TypeError, KeyError, RecursionError) as error:
            raise SnapshotIntegrityError(f"{key[0]}@{key[1]}: {str(error)[:240]}") from error

    def capture_snapshot(self, selection: SnapshotSelection, *, limits: SnapshotLimits) -> DetachedSnapshot:
        """Capture one bounded exact outgoing closure under a single SQLite read transaction.

        Current roots resolve in caller order after the watermark establishes the
        snapshot. Missing selected roots retain RecordNotFoundError; missing edges
        and malformed metadata raise SnapshotIntegrityError. No artifact bytes are
        opened or verified, and navigation never invokes typed target admission.
        """
        if type(selection) is not SnapshotSelection or type(limits) is not SnapshotLimits:
            raise DomainValidationError("capture requires SnapshotSelection and SnapshotLimits")
        try:
            selection = SnapshotSelection(selection.project, selection.roots)
            limits = SnapshotLimits(**limits.to_dict())
        except (AttributeError, TypeError) as error:
            raise DomainValidationError("capture: malformed selection or limits") from error
        requests = (selection.project, *selection.roots)
        if len(requests) > limits.max_roots:
            raise SnapshotLimitError("max_roots exceeded (including project)")
        with self._transaction(write=False) as connection:
            # This first SELECT establishes the rollback-journal read snapshot.
            # A competing writer may prepare but cannot finish COMMIT until it ends.
            top = connection.execute("""SELECT a.event_id,
                length(CAST(a.submission_id AS BLOB)),length(CAST(a.committed_at AS BLOB)),
                length(CAST(s.fingerprint AS BLOB)) FROM audit_events a
                LEFT JOIN submissions s USING(submission_id) ORDER BY a.event_id DESC LIMIT 1""").fetchone()
            _fault("snapshot_after_first_read")
            fetched = 0
            watermark = dict.fromkeys(("event_id", "submission_id", "committed_at", "fingerprint"))
            if top is not None:
                if any(type(n) is not int or n < 0 for n in top):
                    raise SnapshotIntegrityError("invalid watermark metadata")
                fetched = sum(top[1:]) + len(str(top[0]))
                if fetched > limits.max_metadata_bytes:
                    raise SnapshotLimitError("watermark metadata bytes exceeded")
                row = connection.execute("""SELECT a.event_id,a.submission_id,a.committed_at,s.fingerprint
                    FROM audit_events a JOIN submissions s USING(submission_id) WHERE a.event_id=?""", (top[0],)).fetchone()
                watermark = dict(zip(watermark, row))
            try:
                _commit(watermark, watermark=True)
            except DomainValidationError as error:
                raise SnapshotIntegrityError(f"watermark: {error}") from error
            resolutions = []
            for index, selector in enumerate(requests):
                if selector.revision is None:
                    row = connection.execute("SELECT CASE WHEN typeof(head)='integer' THEN head ELSE NULL END FROM identities WHERE record_id=?", (selector.record_id,)).fetchone()
                else:
                    row = connection.execute("SELECT revision FROM revisions WHERE record_id=? AND revision=?",
                                             (selector.record_id, selector.revision)).fetchone()
                if row is None:
                    raise RecordNotFoundError(f"selected root {selector.record_id}@{selector.revision}: absent")
                try:
                    _integer(row[0], "resolved revision", 1)
                except DomainValidationError as error:
                    raise SnapshotIntegrityError(str(error)) from error
                fetched += len(str(row[0]))
                if fetched > limits.max_metadata_bytes:
                    raise SnapshotLimitError("root resolution metadata exceeded")
                resolutions.append({"record_id": selector.record_id, "revision": row[0]})
                if index == 0:
                    _fault("snapshot_after_head_resolution")
            from collections import deque
            queue = deque()
            enqueued = set()
            for pin in resolutions:
                key = (pin["record_id"], pin["revision"])
                if key not in enqueued:
                    if len(enqueued) >= limits.max_records:
                        raise SnapshotLimitError("max_records exceeded")
                    enqueued.add(key)
                    queue.append((key, None))
            records, envelopes, artifacts = {}, {}, {}
            references = 0
            expected_bytes = 0
            retained = 0
            while queue:
                key, origin = queue.popleft()
                try:
                    envelope, entry, size, count = self._snapshot_record(
                        connection, key, limits, limits.max_metadata_bytes - fetched - retained,
                        limits.max_references - references)
                except RecordNotFoundError as error:
                    if origin is None:
                        raise
                    raise SnapshotIntegrityError(f"{origin}: missing {key[0]}@{key[1]}") from error
                records[key], envelopes[key] = entry, envelope
                fetched += size
                retained += len(_canonical(entry))
                references += count
                for ordinal, edge in enumerate(envelope.record_references):
                    target = (edge.record_id, edge.revision)
                    if target not in enqueued:
                        if len(enqueued) >= limits.max_records:
                            raise SnapshotLimitError("max_records exceeded during closure traversal")
                        enqueued.add(target)
                        queue.append((target, f"{key[0]}@{key[1]} edge {ordinal}"))
                for ordinal, artifact in enumerate(envelope.artifact_references):
                    registered = connection.execute("SELECT CASE WHEN typeof(size)='integer' THEN size ELSE NULL END FROM artifacts WHERE digest=?", (artifact.digest,)).fetchone()
                    if registered is None or type(registered[0]) is not int or registered[0] != artifact.size:
                        raise SnapshotIntegrityError(f"{key[0]}@{key[1]} artifact {ordinal}: registration mismatch")
                    fetched += len(str(registered[0]))
                    if fetched + retained > limits.max_metadata_bytes:
                        raise SnapshotLimitError("artifact registration metadata exceeded")
                    if artifact.digest not in artifacts:
                        if len(artifacts) >= limits.max_artifacts:
                            raise SnapshotLimitError("max_artifacts exceeded")
                        expected_bytes += artifact.size
                        if artifact.size > limits.max_file_bytes or expected_bytes > limits.max_total_bytes:
                            raise SnapshotLimitError("expected artifact bytes exceeded")
                        artifacts[artifact.digest] = {"digest": artifact.digest, "size": artifact.size,
                            "availability": "expected_unverified", "occurrences": []}
                    if artifacts[artifact.digest]["size"] != artifact.size:
                        raise SnapshotIntegrityError("conflicting sizes for digest")
                    artifacts[artifact.digest]["occurrences"].append(
                        {"record_id": key[0], "revision": key[1], "ordinal": ordinal})
            first = resolutions[0]
            if envelopes[(first["record_id"], first["revision"])].kind != "project":
                raise DomainValidationError("project selector must resolve to envelope kind project")
            # Check every occurrence, including edges whose target was already cached.
            for key, envelope in envelopes.items():
                for ordinal, edge in enumerate(envelope.record_references):
                    if edge.target_kind not in (None, envelopes[(edge.record_id, edge.revision)].kind):
                        raise SnapshotIntegrityError(f"{key[0]}@{key[1]} edge {ordinal}: declared target kind mismatch")
            ordered_records = [records[key] for key in sorted(records)]
            ordered_artifacts = [artifacts[key] for key in sorted(artifacts)]
            for artifact in ordered_artifacts:
                artifact["occurrences"].sort(key=lambda item: (item["record_id"], item["revision"], item["ordinal"]))
            schema = _schema_identity(connection.execute("PRAGMA user_version").fetchone()[0])
            fetched += len(str(schema["version"]))
            document = {"format": "research_pipeline.snapshot.v1", "selection": selection.to_dict(),
                "resolutions": resolutions, "schema": schema,
                "watermark": watermark, "records": ordered_records, "artifacts": ordered_artifacts,
                "limits": limits.to_dict(), "metadata_fetched_bytes": fetched,
                "scope": _scope(selection.to_dict(), resolutions, ordered_records, ordered_artifacts)}
            body = _bounded_json(document, limits.max_metadata_bytes - fetched, "detached metadata")
            document["snapshot_id"] = hashlib.sha256(body.encode("ascii")).hexdigest()
            _bounded_json(document, limits.max_metadata_bytes - fetched, "detached metadata")
            return DetachedSnapshot(document)

    def get_revision(self, record_id: str, revision: int) -> RecordEnvelope:
        """Return an exact revision with verified direct artifacts, or raise if absent."""
        _identifier(record_id, "record_id")
        _integer(revision, "revision", 1)
        with self._transaction() as connection:
            return self._envelope(connection, record_id, revision)

    def get_typed_revision(self, record_id: str, revision: int) -> tuple[RecordEnvelope, ScientificContent | AssessmentContent | WorkProductManifest | Source | CorpusManifest | ProjectSetup]:
        """Return an exact detached envelope and decoded value, verifying direct artifacts.

        Preserve missing-revision/artifact errors; absent discriminators raise
        NotTypedContentError and other codec failures raise DomainValidationError.
        This checks selected-envelope coherence, not past admission or scientific
        validity. Work-product/Source/corpus/project supersession is checked locally against identity/revision;
        corpus and project reads do not traverse or certify historical admission.
        It never traverses targets or establishes review route membership.
        """
        envelope = self.get_revision(record_id, revision)
        return envelope, _decode_typed_envelope(envelope)

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
