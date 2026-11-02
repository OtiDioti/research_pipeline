"""Bounded authority operations on the existing immutable SQLite submission store.

The caller supplies current external trust and time. No policy or key is retained
on RecordStore or sent to persistence, artifact storage, projections or backups.
"""

import hashlib

from research_pipeline import operating_authority as authority
from research_pipeline.operating_authority import (
    AuthorityValidationError, AuthorityAuthenticationError, AuthorityReadinessError,
    AuthorityIntegrityError, AuthorityLimitError, OperatingScope, OperatingBinding,
    SignedOperatingDecision, DecisionCommitResult, AuthorityHistory, EligibilityResult,
)
from research_pipeline.domain import (
    RecordReference, RecordEnvelope, ArtifactReference, CreationProvenance,
    Submission, SubmissionReceipt, DomainValidationError, _identifier, _integer,
)
from research_pipeline.report_capture import _text_length, _integer_length
from research_pipeline.project import ProjectSetup, ProceduralJudgment, _validate_ready_prerequisites
from research_pipeline.corpus import CorpusManifest
from research_pipeline.source import Source
from research_pipeline.work_product import WorkProductManifest
from research_pipeline.scientific import ResearchContext
from research_pipeline.artifacts import ArtifactError
from research_pipeline.snapshot import _commit


def _fault(boundary):
    """Expose authority snapshot/commit observation seams without owning transaction behavior."""


def _length(row):
    """Reject malformed storage types or absent required joins using length-only SQL results."""
    if row is None or any(type(size) is not int or size < 0 for size in row):
        raise AuthorityIntegrityError("missing or invalid authority metadata storage types")
    return sum(row)


def _canonical_json(raw, maximum):
    """Decode strict bounded stored JSON and require exact canonical ASCII representation."""
    try:
        value = authority.strict_json(raw, maximum)
        if authority.canonical(value) != raw:
            raise ValueError
        return value
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise AuthorityIntegrityError("noncanonical or malformed stored authority JSON") from None


def _text_bound(size):
    """Bound canonical JSON text from SQL UTF-8 bytes, including quotes or nullable null."""
    # Each UTF-8 input byte needs at most six ASCII escape bytes; null needs four.
    return max(4, 6 * size + 2)


def _object_bytes(**fields):
    """Count fixed JSON field names/punctuation plus already bounded value fragments."""
    return 2 + max(0, len(fields) - 1) + sum(len(name) + 3 + size for name, size in fields.items())


def _array_bytes(sizes):
    """Count array framing and already measured elements without building a wire copy."""
    total = 2
    for index, size in enumerate(sizes):
        total += size + (1 if index else 0)
    return total


def _fragment_bytes(value):
    """Measure an already validated JSON fragment without serializing a whole document.

    Only scalar encoding allocates text; recursive framing preserves canonical
    escaping for retained bindings, history entries, heads and audit watermarks.
    This does not validate untrusted input or replace SQL metadata preflight.
    """
    if isinstance(value, dict):
        return 2 + max(0, len(value) - 1) + sum(
            len(authority.canonical(key)) + 1 + _fragment_bytes(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return _array_bytes(_fragment_bytes(item) for item in value)
    return len(authority.canonical(value))


def _reference_bytes(record_id, revision, relationship, kind):
    """Count a new exact reference from validated scalars before constructing it."""
    return _object_bytes(record_id=_fragment_bytes(record_id), revision=len(str(revision)),
        relationship=_fragment_bytes(relationship), target_kind=_fragment_bytes(kind))


def _commit_result_bytes(key, operation_id, receipt_size):
    """Count the detached commit wrapper, including its independent embedded receipt."""
    return _object_bytes(format=len('"research_pipeline.operating_commit_result"'), version=1,
        operation_id=_fragment_bytes(operation_id),
        decision=_reference_bytes(*key, "operating_decision", "decision"),
        envelope_digest=66, receipt=receipt_size)


def _receipt_result_bytes(key, operation_id, event_size, timestamp_size, provenance_size):
    """Plan standalone receipt and result retention from validated or bounded audit fields."""
    receipt_size = _object_bytes(submission_id=_fragment_bytes(operation_id), fingerprint=66,
        event_id=event_size, committed_at=timestamp_size, provenance=provenance_size,
        revisions=_array_bytes([_array_bytes([_fragment_bytes(key[0]), len(str(key[1]))])]))
    return receipt_size + _commit_result_bytes(key, operation_id, receipt_size)


def _key(reference):
    """Select exact record identity/revision independently of the incoming role."""
    return reference.record_id, reference.revision


def _ref(envelope, role):
    """Build a complete explicit-kind reference to a previously validated envelope."""
    return RecordReference(envelope.record_id, envelope.revision, role, envelope.kind).to_dict()


def _require_store(store):
    """Preserve closed/layout errors and require the existing schema-2/3 record model."""
    from research_pipeline.store import StoreLayoutError
    store._require_open()
    if store._schema_version not in (2, 3):
        raise StoreLayoutError("operating decisions require explicit migration to schema 2 or 3")


class _Reader:
    """One-operation bounded metadata cache and artifact verification budget in one connection."""

    def __init__(self, store, connection, limits):
        """Initialize caller-owned transaction accounting; never retain host credentials."""
        self.store, self.connection, self.limits = store, connection, limits
        self.metadata_bytes = 0
        self.references = 0
        self.records = set()
        self.histories = set()
        self.envelopes = {}
        self.envelope_sizes = {}
        self.preflighted = {}
        self.typed = set()
        self.submission_ids = {}
        self.operations = {}
        self.verified = {}
        self.artifact_bytes = 0

    def reserve(self, size):
        """Charge every fetched or retained byte before allocating metadata; never truncate."""
        if type(size) is not int or size < 0:
            raise AuthorityIntegrityError("invalid authority metadata accounting")
        if self.metadata_bytes + size > self.limits.max_metadata_bytes:
            raise AuthorityLimitError("authority aggregate metadata byte limit exceeded")
        self.metadata_bytes += size

    def record(self, key):
        """Count distinct metadata records, including shallow existence reads, before fetching."""
        if key not in self.records:
            if len(self.records) >= self.limits.max_records:
                raise AuthorityLimitError("authority metadata record limit exceeded")
            self.records.add(key)

    def reference_count(self, count):
        """Count repeated ordered reference occurrences independently of target-cache hits."""
        if self.references + count > self.limits.max_references:
            raise AuthorityLimitError("authority reference occurrence limit exceeded")
        self.references += count

    def history_count(self, key):
        """Count decision/dossier history revisions independently of metadata-record limits."""
        if key not in self.histories:
            if len(self.histories) >= self.limits.max_history_revisions:
                raise AuthorityLimitError("authority history revision limit exceeded")
            self.histories.add(key)

    def head(self, identity):
        """Preflight identity kind/head types and bytes before fetching a watched head."""
        row = self.connection.execute("SELECT " + _integer_length("head", 1) + "," +
            _text_length("kind") + " FROM identities WHERE record_id=?", (identity,)).fetchone()
        if row is None:
            return None
        if _length(row) > self.limits.max_record_bytes:
            raise AuthorityLimitError("authority head metadata byte limit exceeded")
        self.reserve(_length(row))
        head, kind = self.connection.execute("SELECT head,kind FROM identities WHERE record_id=?", (identity,)).fetchone()
        try:
            _integer(head, "head", 1)
            authority._kind(kind, "kind")
        except ValueError:
            raise AuthorityIntegrityError("invalid authority watched head") from None
        self.record((identity, head))
        return {"record_id": identity, "revision": head, "kind": kind}

    def shallow(self, reference, *, repeated=False):
        """Inspect existence/kind only; generic roles never recursively certify payloads."""
        key = _key(reference)
        self.record(key)
        row = self.connection.execute("SELECT " + _text_length("i.kind") + """ FROM revisions r
            LEFT JOIN identities i USING(record_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        if row is None:
            raise AuthorityIntegrityError("missing shallow authority target")
        if _length(row) > self.limits.max_record_bytes:
            raise AuthorityLimitError("authority shallow metadata byte limit exceeded")
        self.reserve(_length(row) * (2 if repeated else 1))
        kind = self.connection.execute("""SELECT i.kind FROM revisions r JOIN identities i USING(record_id)
            WHERE r.record_id=? AND r.revision=?""", key).fetchone()[0]
        try:
            authority._kind(kind, "shallow kind")
        except ValueError:
            raise AuthorityIntegrityError("invalid shallow authority target kind") from None
        if reference.target_kind is not None and reference.target_kind != kind:
            raise AuthorityIntegrityError("shallow authority target kind mismatch")
        return kind

    def preflight(self, key):
        """Reserve actual row/link fetches and canonical retention before any reconstruction.

        Successful plans belong to this transaction's reader. Reuse charges neither
        the planned fetch nor its ordered references twice; operation membership and
        audit fetches are independent and are never certified by this cache.
        """
        if key in self.preflighted:
            return self.preflighted[key]
        self.record(key)
        columns = (_text_length("i.kind"), _text_length("r.content_json"),
            _text_length("r.provenance_json"), _text_length("r.operational_status", nullable=True),
            _text_length("r.scientific_disposition", nullable=True), _text_length("r.submission_id"),
            _text_length("s.fingerprint"), _text_length("a.committed_at"), _integer_length("r.ordinal"))
        lengths = self.connection.execute("SELECT " + ",".join(columns) + """ FROM revisions r
            LEFT JOIN identities i USING(record_id) LEFT JOIN submissions s USING(submission_id)
            LEFT JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        size = _length(lengths)
        if size > self.limits.max_record_bytes:
            raise AuthorityLimitError("authority actual record byte limit exceeded")
        self.reserve(size)
        tables = (("record_links", (_text_length("target_id"), _integer_length("target_revision", 1),
                _text_length("relationship"), _text_length("target_kind", nullable=True))),
                ("artifact_links", (_text_length("digest"), _integer_length("size"))))
        counts = [self.connection.execute("SELECT count(*) FROM " + table +
            " WHERE record_id=? AND revision=?", key).fetchone()[0] for table, _ in tables]
        # Both actual counts must fit before even the first link value is fetched.
        self.reference_count(sum(counts))
        collections = []
        for (table, columns), count in zip(tables, counts):
            collection = 2 + max(0, count - 1)
            cursor = self.connection.execute("SELECT CASE WHEN typeof(ordinal)='integer' THEN ordinal ELSE NULL END,"
                + ",".join(columns) + " FROM " + table + " WHERE record_id=? AND revision=? ORDER BY ordinal", key)
            for ordinal in range(count):
                row = cursor.fetchone()
                if row is None or type(row[0]) is not int or row[0] != ordinal:
                    raise AuthorityIntegrityError("noncontiguous authority link ordinals")
                contribution = _length(row[1:]) + len(str(ordinal))
                size += contribution
                if size > self.limits.max_record_bytes:
                    raise AuthorityLimitError("authority actual link byte limit exceeded")
                self.reserve(contribution)
                if table == "record_links":
                    collection += _object_bytes(record_id=_text_bound(row[1]), revision=row[2],
                        relationship=_text_bound(row[3]), target_kind=_text_bound(row[4]))
                else:
                    collection += _object_bytes(digest=_text_bound(row[1]), size=row[2])
            if cursor.fetchone() is not None:
                raise AuthorityIntegrityError("authority link count changed inside snapshot")
            collections.append(collection)
        # Accepted content/provenance must be canonical, so their input lengths
        # bound their canonical fragments. Other scalars are not yet validated.
        retained = _object_bytes(record_id=_text_bound(len(key[0].encode("utf-8"))),
            revision=len(str(key[1])), kind=_text_bound(lengths[0]), content=lengths[1],
            provenance=lengths[2], operational_status=_text_bound(lengths[3]),
            scientific_disposition=_text_bound(lengths[4]),
            record_references=collections[0], artifact_references=collections[1])
        self.reserve(retained)
        self.preflighted[key] = retained
        return retained

    def read(self, key):
        """Reconstruct a preflighted envelope, reconcile retention and cache its exact size for later copies."""
        retained = self.preflight(key)
        if key in self.envelopes:
            return self.envelopes[key]
        row = self.connection.execute("""SELECT i.kind,r.content_json,r.provenance_json,r.operational_status,
            r.scientific_disposition,r.submission_id,s.fingerprint,a.committed_at FROM revisions r
            JOIN identities i USING(record_id) JOIN submissions s USING(submission_id)
            JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        content = _canonical_json(row[1], self.limits.max_record_bytes)
        provenance = _canonical_json(row[2], self.limits.max_record_bytes)
        try:
            _commit({"submission_id": row[5], "fingerprint": row[6], "committed_at": row[7]})
            links = tuple(RecordReference(*item) for item in self.connection.execute("""SELECT target_id,
                target_revision,relationship,target_kind FROM record_links WHERE record_id=? AND revision=? ORDER BY ordinal""", key))
            artifacts = tuple(ArtifactReference(*item) for item in self.connection.execute("""SELECT digest,size
                FROM artifact_links WHERE record_id=? AND revision=? ORDER BY ordinal""", key))
            envelope = RecordEnvelope(*key, row[0], content, CreationProvenance.from_dict(provenance),
                                      links, artifacts, row[3], row[4])
            encoded = authority.bounded(envelope.to_dict(), authority.ENVELOPE_BYTES)
            if len(encoded) > self.limits.max_record_bytes:
                raise AuthorityLimitError("authority canonical record byte limit exceeded")
            self.metadata_bytes -= retained - len(encoded)
            if envelope.provenance.to_dict() != provenance:
                raise ValueError
        except (ValueError, TypeError, AttributeError, RecursionError, OverflowError) as error:
            if isinstance(error, AuthorityLimitError):
                raise
            raise AuthorityIntegrityError("invalid authority record metadata") from None
        self.envelopes[key] = envelope
        self.envelope_sizes[key] = len(encoded)
        self.submission_ids[key] = row[5]
        return envelope

    def retain_typed(self, envelope):
        """Reserve a second detached typed-content snapshot before the shared resolver reconstructs it."""
        key = envelope.record_id, envelope.revision
        if key not in self.typed:
            self.reserve(len(envelope._content_json))
            self.typed.add(key)

    def history(self, envelope, value):
        """Require complete typed dossier histories, with exact mandatory predecessors where defined."""
        if type(value) not in (ProjectSetup, CorpusManifest, Source, WorkProductManifest, ResearchContext):
            return None
        key = envelope.record_id, envelope.revision
        self.history_count(key)
        if envelope.revision == 1:
            return None
        prior_key = envelope.record_id, envelope.revision - 1
        if type(value) is not ResearchContext:
            prior = value.supersedes
            if prior is None or _key(prior) != prior_key or prior.target_kind != envelope.kind:
                raise AuthorityIntegrityError("selected dossier history lacks its exact predecessor")
        previous = self.read(prior_key)
        # Context has no supersedes field. Its contiguous revisions are still typed.
        if previous.kind != envelope.kind:
            raise AuthorityIntegrityError("selected dossier history changed kind")
        return previous

    def watermark(self):
        """Establish the read snapshot using bounded latest audit metadata; never infer global freshness."""
        columns = (_integer_length("a.event_id", 1), _text_length("a.submission_id"),
                   _text_length("a.committed_at"), _text_length("s.fingerprint"))
        row = self.connection.execute("SELECT " + ",".join(columns) + """ FROM audit_events a
            LEFT JOIN submissions s USING(submission_id) ORDER BY a.event_id DESC LIMIT 1""").fetchone()
        result = dict.fromkeys(("event_id", "submission_id", "committed_at", "fingerprint"))
        if row is not None:
            self.reserve(_length(row))
            raw = self.connection.execute("""SELECT a.event_id,a.submission_id,a.committed_at,s.fingerprint
                FROM audit_events a LEFT JOIN submissions s USING(submission_id) ORDER BY a.event_id DESC LIMIT 1""").fetchone()
            result = dict(zip(result, raw))
        try:
            _commit(result, watermark=True)
        except ValueError:
            raise AuthorityIntegrityError("invalid authority audit watermark") from None
        return result

    def output(self, value):
        """Enforce independent detached-output size after strict complete result construction."""
        if len(authority.canonical(value.to_dict())) > self.limits.max_result_bytes:
            raise AuthorityLimitError("authority detached result byte limit exceeded")
        return value

    def verify_artifacts(self, artifacts, *, commit=False):
        """Validate every occurrence, deduplicate actual streaming reads by digest, and bound bytes."""
        selected = {}
        for value in artifacts:
            artifact = ArtifactReference.from_dict(value)
            previous = selected.get(artifact.digest) or self.verified.get(artifact.digest)
            if previous is not None and previous.size != artifact.size:
                raise AuthorityIntegrityError("conflicting selected authority artifact sizes")
            selected[artifact.digest] = artifact
        pending = [artifact for identity, artifact in selected.items() if identity not in self.verified]
        if len(self.verified) + len(pending) > self.limits.max_artifacts:
            raise AuthorityLimitError("authority artifact count limit exceeded")
        if any(item.size > self.limits.max_file_bytes for item in pending):
            raise AuthorityLimitError("authority artifact file byte limit exceeded")
        total = sum(item.size for item in pending)
        if self.artifact_bytes + total > self.limits.max_total_bytes:
            raise AuthorityLimitError("authority aggregate artifact byte limit exceeded")
        self.artifact_bytes += total
        for artifact in pending:
            if commit:
                self.store._artifacts._verify_for_commit(artifact)
            else:
                self.store._artifacts.verify(artifact)
            self.verified[artifact.digest] = artifact


def _result(envelope, receipt):
    """Build immutable original-operation evidence without an eligible flag or artifact reads."""
    return DecisionCommitResult({"format": "research_pipeline.operating_commit_result", "version": 1,
        "operation_id": receipt.submission_id, "decision": _ref(envelope, "operating_decision"),
        "envelope_digest": authority.envelope_digest(envelope), "receipt": receipt.to_dict()})


def _operation(reader, operation_id):
    """Recover actual original canonical submission, exact membership and audit/link consistency.

    Reconciliation always precedes current policy, clock, CAS, dossier and artifact
    checks. Actual membership, links and audit metadata are preflighted before
    parsing the request; every retained representation is reserved before its
    construction. Recovery authenticates no permission, including for generic submissions.
    """
    from research_pipeline.store import SubmissionConflictError
    if operation_id in reader.operations:
        return reader.operations[operation_id]
    connection = reader.connection
    row = connection.execute("SELECT " + _text_length("request_json") + "," + _text_length("fingerprint")
        + " FROM submissions WHERE submission_id=?", (operation_id,)).fetchone()
    if row is None:
        return None
    request_size, fingerprint_size = row
    size = _length(row)
    if request_size > min(authority.ENVELOPE_BYTES, reader.limits.max_record_bytes) + 1024:
        raise AuthorityLimitError("authority original request byte limit exceeded")
    if fingerprint_size != 64:
        raise AuthorityIntegrityError("invalid authority original fingerprint")
    # Actual membership, never the saved request, selects the bounded revision.
    count = connection.execute("SELECT count(*) FROM revisions WHERE submission_id=?", (operation_id,)).fetchone()[0]
    if count != 1:
        raise AuthorityIntegrityError("authority submission must have exactly one stored member")
    lengths = connection.execute("SELECT " + _text_length("record_id") + "," +
        _integer_length("revision", 1) + "," + _integer_length("ordinal") +
        " FROM revisions WHERE submission_id=?", (operation_id,)).fetchone()
    member_size = _length(lengths)
    if member_size > reader.limits.max_record_bytes:
        raise AuthorityLimitError("authority member metadata byte limit exceeded")
    reader.reserve(member_size)
    member = connection.execute("SELECT record_id,revision,ordinal FROM revisions WHERE submission_id=?", (operation_id,)).fetchone()
    try:
        _identifier(member[0], "member")
        _integer(member[1], "revision", 1)
        if member[2] != 0:
            raise ValueError
    except ValueError:
        raise AuthorityIntegrityError("invalid authority submission member/ordinal") from None
    key = member[:2]
    reader.preflight(key)
    columns = (_integer_length("event_id", 1), _text_length("committed_at"), _text_length("provenance_json"),
               _text_length("event_type"), _text_length("submission_id"))
    lengths = connection.execute("SELECT " + ",".join(columns) + " FROM audit_events WHERE submission_id=?", (operation_id,)).fetchone()
    audit_size = _length(lengths)
    if audit_size > reader.limits.max_record_bytes:
        raise AuthorityLimitError("authority audit provenance byte limit exceeded")
    # Audit fetch and decoded canonical provenance are independent of the row's
    # join fetch. Request copies cover decoded JSON, Submission, signed value and
    # derived Submission in addition to the raw fetch; none is allocated first.
    reader.reserve(audit_size + lengths[2])
    reader.reserve(size + 4 * request_size)
    raw, fingerprint = connection.execute("SELECT request_json,fingerprint FROM submissions WHERE submission_id=?", (operation_id,)).fetchone()
    document = _canonical_json(raw, authority.ENVELOPE_BYTES + 1024)
    try:
        authority.exact(document, "fingerprint_version submission")
        if type(document["fingerprint_version"]) is not int or document["fingerprint_version"] != 1:
            raise ValueError
        submitted = Submission.from_dict(document["submission"])
    except (ValueError, TypeError, KeyError, AttributeError):
        raise AuthorityIntegrityError("invalid authority original submission") from None
    if submitted.submission_id != operation_id or len(submitted.records) != 1:
        raise SubmissionConflictError("operation identity belongs to another submission")
    expected = submitted.records[0]
    if expected.content.get("format") != "research_pipeline.operating_authority_content":
        raise SubmissionConflictError("operation identity belongs to another submission")
    try:
        signed = authority.decode_envelope(expected)
        derived = authority.submission(signed)
        if (derived.to_dict() != submitted.to_dict() or document["submission"] != submitted.to_dict() or
                hashlib.sha256(raw.encode("ascii")).hexdigest() != fingerprint):
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        if isinstance(error, AuthorityLimitError):
            raise
        raise AuthorityIntegrityError("original authority request or fingerprint mismatch") from None
    # Canonical accepted fragments give exact sizes. Drop temporary decoded and
    # derived values; only submitted and signed representations remain retained.
    reader.metadata_bytes -= 4 * request_size - (
        len(authority.canonical(submitted.to_dict())) + len(authority.canonical(signed.to_dict())))
    del document, derived, raw
    if member != (expected.record_id, expected.revision, 0):
        raise AuthorityIntegrityError("authority submission member/ordinal mismatch")
    event_id, committed_at, provenance, event_type, sid = connection.execute("""SELECT event_id,committed_at,
        provenance_json,event_type,submission_id FROM audit_events WHERE submission_id=?""", (operation_id,)).fetchone()
    audit_provenance = _canonical_json(provenance, reader.limits.max_record_bytes)
    if event_type != "submission_committed" or sid != operation_id or audit_provenance != submitted.provenance.to_dict():
        raise AuthorityIntegrityError("authority audit provenance or operation mismatch")
    actual = reader.read(key)
    if actual.to_dict() != expected.to_dict() or reader.submission_ids[key] != operation_id:
        raise AuthorityIntegrityError("authority actual envelope differs from original request")
    # Reserve the standalone receipt and the complete detached result separately.
    # Numeric lengths and canonical provenance come from independent audit preflight.
    retained = _receipt_result_bytes(key, operation_id, lengths[0], _text_bound(lengths[1]), lengths[2])
    reader.reserve(retained)
    try:
        receipt = SubmissionReceipt(operation_id, fingerprint, event_id, committed_at,
            CreationProvenance.from_dict(audit_provenance), (key,))
        if receipt.committed_at != committed_at:
            raise ValueError
        result = reader.output(_result(actual, receipt))
    except (ValueError, TypeError, AttributeError) as error:
        if isinstance(error, AuthorityLimitError):
            raise
        raise AuthorityIntegrityError("invalid original authority receipt") from None
    reader.metadata_bytes -= retained - (_fragment_bytes(receipt.to_dict()) + len(result._json))
    found = result, signed, submitted
    reader.operations[operation_id] = found
    return found


def _history(reader, authority_domain, project_id, policy):
    """Validate the complete actual stream and reserve each annotated entry before copying it."""
    from research_pipeline.store import SubmissionConflictError
    identity = authority.stream_id(authority_domain, project_id)
    head = reader.head(identity)
    if head is None:
        return []
    if head["kind"] != "decision":
        raise AuthorityIntegrityError("canonical authority stream has wrong kind")
    if head["revision"] > reader.limits.max_decisions:
        raise AuthorityLimitError("authority decision count limit exceeded")
    count = reader.connection.execute("SELECT count(*) FROM revisions WHERE record_id=?", (identity,)).fetchone()[0]
    if count != head["revision"]:
        raise AuthorityIntegrityError("authority stream history/head mismatch")
    result, previous = [], None
    for revision in range(1, head["revision"] + 1):
        key = identity, revision
        reader.history_count(key)
        envelope = reader.read(key)
        try:
            signed = authority.decode_envelope(envelope)
            decision = signed.to_dict()["decision"]
            found = _operation(reader, reader.submission_ids[key])
            if found is None or found[1] != signed:
                raise ValueError
            if decision["authority_domain"] != authority_domain or decision["binding"]["project"]["record_id"] != project_id:
                raise ValueError
            if previous is not None:
                prior_envelope, prior_decision = previous
                if decision["predecessor"]["envelope_digest"] != authority.envelope_digest(prior_envelope):
                    raise ValueError
                if decision["outcome"] != "approve" and decision["binding"] != prior_decision["binding"]:
                    raise ValueError
        except (DomainValidationError, SubmissionConflictError, TypeError, KeyError, AttributeError):
            raise AuthorityIntegrityError("invalid canonical authority history") from None
        except ValueError as error:
            if isinstance(error, (AuthorityIntegrityError, AuthorityLimitError)):
                raise
            raise AuthorityIntegrityError("incoherent canonical authority history") from None
        signature_status = authority.verify_signature(signed, policy=policy)
        policy_status = authority.policy_status(signed, policy=policy)
        # The recovered result already retains a receipt; this entry owns another
        # copy, its envelope and both annotations, independently of that cache.
        # Subtract its known wrapper to measure the receipt without decoding a copy.
        receipt_size = len(found[0]._json) - _commit_result_bytes(key, reader.submission_ids[key], 0)
        reader.reserve(_object_bytes(envelope=reader.envelope_sizes[key], receipt=receipt_size,
            signature_status=_fragment_bytes(signature_status), policy_status=_fragment_bytes(policy_status)))
        result.append({"envelope": envelope.to_dict(), "receipt": found[0].to_dict()["receipt"],
            "signature_status": signature_status, "policy_status": policy_status})
        previous = envelope, decision
    return result


def _resolve(reader, project, scope):
    """Resolve bounded typed roles and reserve the detached dossier before constructing its binding."""
    from research_pipeline.store import _decode_typed_envelope, ReferenceResolutionError
    root = reader.read(_key(project))
    if root.kind != "project":
        raise AuthorityIntegrityError("authority dossier root is not a project")
    try:
        reader.retain_typed(root)
        value = _decode_typed_envelope(root)
        if type(value) is not ProjectSetup:
            raise ValueError
        # This is a resolver seed, never a submitted operation. All data are stored
        # roots already read by the bounded reader in the same transaction.
        seed = Submission("authority_resolution", root.provenance, (root,), {root.record_id: root.revision - 1})
        envelopes, values = reader.store._check_typed_targets(reader.connection, seed, (value,), authority_reader=reader)
    except (DomainValidationError, ReferenceResolutionError, TypeError, KeyError, AttributeError):
        raise AuthorityIntegrityError("incoherent selected dossier metadata or history") from None
    except ValueError as error:
        if isinstance(error, (AuthorityLimitError, AuthorityIntegrityError)):
            raise
        raise AuthorityIntegrityError("invalid selected project dossier") from None
    watched = {}

    def watch(reference):
        """Record one consistent selected revision per current dependency, independent of roles."""
        selected = {"record_id": reference.record_id, "revision": reference.revision, "kind": reference.target_kind}
        if reference.record_id in watched and watched[reference.record_id] != selected:
            raise AuthorityReadinessError("authority watched identity has inconsistent selected revisions")
        watched[reference.record_id] = selected

    watch(project)
    watch(value.current_corpus)
    for item in (value.context, value.brief, value.intake_report):
        if item is not None:
            watch(item)
    for location in (*value.inspection.locations, *(location for declaration in value.declarations for location in declaration.locations)):
        watch(location.source)
    if scope is not None:
        # Permission targets are read exactly, without inventing qualification or
        # recursively certifying arbitrary supporting disclosure-policy payloads.
        for item in scope["capability_releases"]:
            reference = RecordReference.from_dict(item["release"])
            reader.reference_count(1)
            selected = reader.read(_key(reference))
            if selected.kind != reference.target_kind:
                raise AuthorityIntegrityError("capability release target kind mismatch")
            envelopes[_key(reference)] = selected
            watch(reference)
        for item in scope["disclosures"]:
            reference = RecordReference.from_dict(item["policy_reference"])
            reader.reference_count(2)
            selected = reader.read(_key(reference))
            if selected.kind != reference.target_kind:
                raise AuthorityIntegrityError("disclosure policy target kind mismatch")
            envelopes[_key(reference)] = selected
            watch(reference)
        for item in scope["data_access"]:
            reader.reference_count(1)
            watch(RecordReference.from_dict(item["source"]))
    artifacts = {}

    def original(source_key, original_id):
        """Add one exact selected original occurrence; never accept extraction outputs."""
        source = values.get(source_key)
        if type(source) is not Source:
            raise AuthorityReadinessError("permission selects a Source outside the bound captured corpus")
        selected = next((item for item in source.originals if item.artifact_id == original_id), None)
        if selected is None:
            raise AuthorityReadinessError("permission selects an absent original or extraction output")
        owner = envelopes[source_key]
        occurrence = {"record": _ref(owner, "authority_artifact_record"), "selector_kind": "source_original",
                      "selector": original_id, "artifact": selected.artifact.to_dict()}
        artifacts[(*source_key, "source_original", original_id)] = occurrence
        return selected.artifact

    inspected = set()
    for location in value.inspection.locations:
        source_key = _key(location.source)
        source = values[source_key]
        selected = next(item for item in source.locations if item.location_id == location.location_id)
        original(source_key, selected.artifact_id)
        inspected.add((*source_key, selected.artifact_id))
    corpus = values[_key(value.current_corpus)]
    captured = {(*_key(entry.source), item.artifact_id) for entry in corpus.entries if entry.status == "captured" for item in entry.originals}
    permissions = {}
    if scope is not None:
        for item in scope["data_access"]:
            source_key = authority.pin(item["source"])
            for original_id in item["original_ids"]:
                key = (*source_key, original_id)
                if key not in captured:
                    raise AuthorityReadinessError("data permission must select an original of a current captured corpus entry")
                original(source_key, original_id)
                permissions[key] = item["operations"]
                restrictions = values[source_key].restrictions
                if restrictions.access.status != "available":
                    raise AuthorityReadinessError("Source restriction does not permit read")
                if "reuse" in item["operations"] and restrictions.reuse.status != "permitted":
                    raise AuthorityReadinessError("Source restriction does not permit reuse")
                if "external_processing" in item["operations"]:
                    disclosed = any(authority.pin(entry["source"]) == source_key and original_id in entry["original_ids"]
                                    for entry in scope["disclosures"])
                    if (restrictions.external_processing.status != "permitted" or
                            restrictions.confidentiality.status != "public" or not disclosed):
                        raise AuthorityReadinessError("external processing requires public Source permission and exact disclosure")
        if scope["purpose"] == "main_research" and not inspected <= permissions.keys():
            raise AuthorityReadinessError("main scope must explicitly permit read of every inspected original")
    for reference in (value.brief, value.intake_report):
        if reference is None:
            continue
        for item in values[_key(reference)].files:
            artifacts[(*_key(reference), "work_product_file", item.path)] = {
                "record": _ref(envelopes[_key(reference)], "authority_artifact_record"),
                "selector_kind": "work_product_file", "selector": item.path, "artifact": item.artifact.to_dict()}
    dossier = {name: authority.absent() if getattr(value, name) is None else getattr(value, name).to_dict()
               for name in ("initial_corpus", "current_corpus", "context", "brief", "intake_report")}
    # Cached envelopes and typed content remain retained; neither pays for this
    # independent snapshot, including reference wrappers, null pins and framing.
    reader.reserve(_object_bytes(format=len('"research_pipeline.operating_binding"'), version=1,
        project=_reference_bytes(project.record_id, project.revision, project.relationship, project.target_kind),
        dossier=_fragment_bytes(dossier),
        record_evidence=_array_bytes(_object_bytes(
            reference=_reference_bytes(envelope.record_id, envelope.revision, "authority_evidence", envelope.kind),
            envelope_digest=66) for envelope in envelopes.values()),
        artifact_evidence=_array_bytes(_fragment_bytes(item) for item in artifacts.values()),
        head_expectations=_array_bytes(_fragment_bytes(item) for item in watched.values())))
    try:
        binding = OperatingBinding({"format": "research_pipeline.operating_binding", "version": 1,
            "project": project.to_dict(), "dossier": dossier,
            "record_evidence": [{"reference": _ref(envelope, "authority_evidence"),
                "envelope_digest": authority.envelope_digest(envelope)} for envelope in envelopes.values()],
            "artifact_evidence": list(artifacts.values()), "head_expectations": list(watched.values())})
    except AuthorityValidationError:
        raise AuthorityLimitError("complete authority binding exceeds protocol bounds") from None
    return binding, value, values, inspected


def _observed(reader, binding):
    """Read only the exact watched dependency set; unrelated audit events are immaterial."""
    heads = []
    for expected in binding["head_expectations"]:
        actual = reader.head(expected["record_id"])
        if actual is None:
            raise AuthorityIntegrityError("watched authority dependency identity is missing")
        heads.append(actual)
    return heads


def _prerequisites(value, values, inspected, judgments):
    """Apply shared proposed-ready technical checks using the signed judgments and evidence IDs."""
    try:
        selected = judgments["evidence_declarations"]
        parsed = {name: ProceduralJudgment.from_dict(judgments[name])
                  for name in ("substantive_relevance", "assignment_usability")}
        _validate_ready_prerequisites(value, selected, parsed)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise AuthorityReadinessError("main-research dossier lacks technical intake prerequisites") from None
    context = values.get(_key(value.context))
    if type(context) is not ResearchContext or not context.question.strip():
        raise AuthorityReadinessError("main-research requires a usable nonempty context")
    for reference in (value.brief, value.intake_report):
        product = values[_key(reference)]
        if not product.authors or not next(item.artifact.size for item in product.files if item.path == product.entry_file):
            raise AuthorityReadinessError("main-research requires authored nonempty brief and intake report")
    # Nonempty bytes are a technical prerequisite only. Scientific substance is
    # the configured operator's authenticated judgment, also for non-text originals.
    declarations = {item.declaration_id: item for item in value.declarations}
    for identity in selected:
        for location in declarations[identity].locations:
            source = values[_key(location.source)]
            original_id = next(item.artifact_id for item in source.locations if item.location_id == location.location_id)
            if next(item.artifact.size for item in source.originals if item.artifact_id == original_id) > 0:
                return
    raise AuthorityReadinessError("main-research requires selected evidence anchored to a nonempty original")


def _declarations(value, selected):
    """Require judgment evidence IDs to belong to the already decoded exact ProjectSetup."""
    if not set(selected) <= {item.declaration_id for item in value.declarations}:
        raise AuthorityReadinessError("authority judgment selects unknown declaration IDs")


def _historical_declarations(reader, decision):
    """Check reduction evidence against digest-bound local setup metadata, without fresh readiness."""
    from research_pipeline import project
    binding = decision["binding"]
    key = authority.pin(binding["project"])
    envelope = reader.read(key)
    evidence = next((item for item in binding["record_evidence"]
                     if authority.pin(item["reference"]) == key), None)
    if (envelope.kind != "project" or evidence is None or
            evidence["reference"]["target_kind"] != "project" or
            evidence["envelope_digest"] != authority.envelope_digest(envelope)):
        raise AuthorityIntegrityError("historical authority setup evidence mismatch")
    # Reducing permission needs only the exact local declaration set. Following
    # targets, heads or artifacts here would make revocation depend on availability.
    try:
        reader.retain_typed(envelope)
        value = project.decode_envelope(envelope)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
        if isinstance(error, AuthorityLimitError):
            raise
        raise AuthorityIntegrityError("invalid historical authority setup") from None
    _declarations(value, decision["judgments"]["evidence_declarations"])


def _fresh(reader, decision, *, commit=False):
    """Reconstruct the entire approval binding and check only its explicitly granted permissions."""
    signed_binding, scope = decision["binding"], decision["scope"]
    project = RecordReference.from_dict(signed_binding["project"])
    binding, value, values, inspected = _resolve(reader, project, scope)
    if binding.to_dict() != signed_binding:
        raise AuthorityReadinessError("supplied authority binding differs from complete stored dossier evidence")
    observed = _observed(reader, signed_binding)
    if observed != signed_binding["head_expectations"]:
        raise AuthorityReadinessError("authority watched dependencies are stale")
    _declarations(value, decision["judgments"]["evidence_declarations"])
    if scope["purpose"] == "main_research":
        _prerequisites(value, values, inspected, decision["judgments"])
        artifacts = [item["artifact"] for item in signed_binding["artifact_evidence"]]
    else:
        # Optional setup document pins remain useful evidence even after byte loss;
        # only original-data permissions actually granted require available bytes.
        permitted = {(*authority.pin(item["source"]), original_id) for item in scope["data_access"] for original_id in item["original_ids"]}
        artifacts = [item["artifact"] for item in signed_binding["artifact_evidence"]
                     if item["selector_kind"] == "source_original" and (*authority.pin(item["record"]), item["selector"]) in permitted]
    reader.verify_artifacts(artifacts, commit=commit)
    return observed


def prepare_operating_binding(store, project, *, scope, limits):
    """Prepare complete exact metadata in one read transaction; commit must repeat every check.

    Present optional document pins do not assert byte availability. This preparation
    consumes metadata allowance, but reserves no execution resources and is not a
    permission or a future admitting transaction.
    """
    limits = authority.checked_limits(limits)
    if type(project) is not RecordReference:
        raise AuthorityValidationError("expected exact project_setup RecordReference")
    try:
        project = RecordReference.from_dict(authority.reference(project.to_dict(), "project_setup", "project"))
    except (ValueError, TypeError, AttributeError):
        raise AuthorityValidationError("invalid project_setup reference") from None
    scope = None if scope is None else authority.document(scope, OperatingScope)
    _require_store(store)
    with store._transaction() as connection:
        reader = _Reader(store, connection, limits)
        reader.watermark()
        binding, _, _, _ = _resolve(reader, project, scope)
        return reader.output(binding)


def commit_operating_decision(store, signed, *, policy, evaluated_at, limits):
    """Reconcile original IDs first, then authenticate and atomically append a complete new statement.

    A reduction with a predecessor uses its historical binding without artifact or
    old-signer checks, validating declaration IDs only against its exact local setup.
    No path updates resource tables or implies process termination.
    Lost post-COMMIT acknowledgment must be recovered by this same operation ID.
    Fresh receipt/result retention is reserved before insertion constructs a receipt.
    """
    from research_pipeline.store import SubmissionConflictError, RevisionConflictError, _fault as store_fault
    limits = authority.checked_limits(limits)
    signed = SignedOperatingDecision(authority.document(signed, SignedOperatingDecision))
    # Trust is captured at entry, but malformed/missing trust and time cannot prevent
    # recovery of an identical original committed operation.
    policy_error = False
    try:
        policy = authority.policy_snapshot(policy)
    except AuthorityValidationError:
        policy, policy_error = None, True
    submitted = authority.submission(signed)
    decision = signed.to_dict()["decision"]
    canonical = authority.canonical({"fingerprint_version": 1, "submission": submitted.to_dict()})
    fingerprint = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    _require_store(store)
    with store._transaction(write=True, reconciliation_id="operation_id") as connection:
        reader = _Reader(store, connection, limits)
        old = _operation(reader, decision["operation_id"])
        if old is not None:
            if old[2].to_dict() != submitted.to_dict():
                raise SubmissionConflictError("operation identity already has a different authority request")
            return reader.output(old[0])
        if policy_error or authority.verify_signature(signed, policy=policy) != "verified" or authority.policy_status(signed, policy=policy) != "permitted":
            raise AuthorityAuthenticationError("new authority operation lacks current configured authorization")
        authority.timestamp(evaluated_at)
        if not decision["issued_at"] <= decision["valid_from"] <= evaluated_at < decision["valid_until"]:
            raise AuthorityAuthenticationError("new authority operation is outside its explicit validity window")
        if decision["revision"] > limits.max_decisions:
            raise AuthorityLimitError("new authority decision exceeds complete stream decision limit")
        reader.watermark()
        history = _history(reader, decision["authority_domain"], decision["binding"]["project"]["record_id"], policy)
        if len(history) != decision["revision"] - 1:
            raise RevisionConflictError("authority stream expected head conflict")
        if history:
            previous = RecordEnvelope.from_dict(history[-1]["envelope"])
            prior = previous.content["decision"]
            if decision["predecessor"]["envelope_digest"] != authority.envelope_digest(previous):
                raise RevisionConflictError("authority predecessor envelope digest conflict")
            if decision["outcome"] != "approve" and decision["binding"] != prior["binding"]:
                raise AuthorityValidationError("authority reduction must copy its predecessor binding exactly")
        if decision["outcome"] == "approve":
            if any(item["signature_status"] == "invalid" for item in history):
                raise AuthorityAuthenticationError("authority approval has a known-invalid historical signature")
            try:
                _fresh(reader, decision, commit=True)
            except ArtifactError:
                raise AuthorityReadinessError("selected authority artifact is unavailable") from None
        elif not history:
            binding, value, _, _ = _resolve(reader, RecordReference.from_dict(decision["binding"]["project"]), None)
            if binding.to_dict() != decision["binding"]:
                raise AuthorityReadinessError("initial denial binding differs from committed dossier")
            _declarations(value, decision["judgments"]["evidence_declarations"])
        else:
            _historical_declarations(reader, decision)
        # _check_batch performs shallow target reads again. Preflight and charge each
        # before delegating; the signed envelope has no direct artifact projections.
        envelope = submitted.records[0]
        reader.reference_count(len(envelope.record_references))
        for reference in envelope.record_references:
            reader.shallow(reference, repeated=True)
        current_head = reader.head(envelope.record_id)
        if current_head is not None:
            reader.reserve(len(str(current_head["revision"])) + len(current_head["kind"]))
        if len(authority.canonical(envelope.to_dict())) > limits.max_record_bytes:
            raise AuthorityLimitError("new authority envelope exceeds caller record byte limit")
        reader.reserve(len(canonical))
        store._check_batch(connection, submitted)
        # _insert_submission constructs its receipt internally. Reserve both
        # retained representations first, bounding SQLite's positive event ID by
        # 19 digits and its normalized timestamp by 27 characters plus quotes.
        retained = _receipt_result_bytes((envelope.record_id, envelope.revision), submitted.submission_id,
            19, 29, _fragment_bytes(submitted.provenance.to_dict()))
        reader.reserve(retained)
        # The existing insert helper owns before_metadata/after_first_revision seams;
        # this function owns the transaction, never invoking public submit recursively.
        receipt = store._insert_submission(connection, submitted, canonical, fingerprint)
        result = reader.output(_result(envelope, receipt))
        reader.metadata_bytes -= retained - (_fragment_bytes(receipt.to_dict()) + len(result._json))
    store_fault("after_commit")
    _fault("after_commit")
    return result


def get_operating_operation(store, operation_id, *, limits):
    """Recover the original exact receipt using bounded metadata only; needs no trust or clock."""
    limits = authority.checked_limits(limits)
    authority._identifier(operation_id, "operation identity")
    _require_store(store)
    with store._transaction() as connection:
        reader = _Reader(store, connection, limits)
        found = _operation(reader, operation_id)
        return None if found is None else reader.output(found[0])


def inspect_operating_history(store, authority_domain, project_id, *, policy, limits):
    """Reserve and return full detached history with current annotations, without time or artifacts."""
    limits = authority.checked_limits(limits)
    policy = authority.policy_snapshot(policy)
    authority.stream_id(authority_domain, project_id)
    _require_store(store)
    with store._transaction() as connection:
        reader = _Reader(store, connection, limits)
        watermark = reader.watermark()
        decisions = _history(reader, authority_domain, project_id, policy)
        reader.reserve(_object_bytes(format=len('"research_pipeline.authority_history"'), version=1,
            authority_domain=_fragment_bytes(authority_domain), project_id=_fragment_bytes(project_id),
            decisions=_fragment_bytes(decisions), watermark=_fragment_bytes(watermark)))
        return reader.output(AuthorityHistory({"format": "research_pipeline.authority_history", "version": 1,
            "authority_domain": authority_domain, "project_id": project_id, "decisions": decisions, "watermark": watermark}))


def inspect_operating_eligibility(store, authority_domain, project_id, *, purpose, policy, evaluated_at, limits):
    """Evaluate the actual latest state and dossier in one coherent read snapshot.

    Recompute inside the later admitting write transaction with current external
    policy and trusted time. This evidence consumes metadata allowance but reserves
    no execution resources and guarantees neither dispatch nor continued artifact
    availability. Its watermark records this read snapshot, not a global freshness
    token; unrelated audit events are immaterial.
    """
    limits = authority.checked_limits(limits)
    policy = authority.policy_snapshot(policy)
    authority.stream_id(authority_domain, project_id)
    authority.enum(purpose, ("setup", "main_research"))
    authority.timestamp(evaluated_at)
    _require_store(store)
    with store._transaction() as connection:
        reader = _Reader(store, connection, limits)
        watermark = reader.watermark()
        _fault("snapshot_established")
        history = _history(reader, authority_domain, project_id, policy)
        status = "no_decision"
        signature_status = policy_status = binding = decision_reference = None
        observed_heads, history_signatures = [], []
        policy_fingerprint = authority.policy_fingerprint(policy)
        for item in history:
            stored = item["envelope"]
            envelope = reader.envelopes[(stored["record_id"], stored["revision"])]
            reader.reserve(_object_bytes(
                reference=_reference_bytes(envelope.record_id, envelope.revision, "operating_decision", envelope.kind),
                envelope_digest=66, signature_status=_fragment_bytes(item["signature_status"])))
            history_signatures.append({"reference": _ref(envelope, "operating_decision"),
                "envelope_digest": authority.envelope_digest(envelope), "signature_status": item["signature_status"]})
        if history:
            latest = history[-1]
            decision = latest["envelope"]["content"]["decision"]
            binding = decision["binding"]
            decision_reference = history_signatures[-1]["reference"]
            signature_status, policy_status = latest["signature_status"], latest["policy_status"]
            if latest["signature_status"] == "unavailable":
                status = "missing_trust"
            elif latest["signature_status"] == "invalid":
                status = "unauthenticated"
            elif latest["policy_status"] != "permitted":
                status = "policy_denied"
            elif decision["outcome"] in ("deny", "revoke"):
                # Reductions never expire into an older approval, including after
                # credential withdrawal; no earlier state is selected as fallback.
                status = "denied" if decision["outcome"] == "deny" else "revoked"
            elif any(item["signature_status"] == "invalid" for item in history):
                status = "unauthenticated"
            elif evaluated_at < decision["valid_from"]:
                status = "not_yet_valid"
            elif evaluated_at >= decision["valid_until"]:
                status = "expired"
            elif decision["scope"]["purpose"] != purpose:
                status = "scope_mismatch"
            else:
                observed_heads = _observed(reader, binding)
                if observed_heads != binding["head_expectations"]:
                    status = "stale"
                else:
                    try:
                        _fresh(reader, decision)
                        status = "eligible_" + purpose
                    except AuthorityReadinessError:
                        status = "incomplete"
                    except ArtifactError:
                        status = "artifact_unavailable"
        eligible = status in ("eligible_setup", "eligible_main_research")
        # Every branch, including an empty stream, owns a complete detached
        # snapshot. Existing history/binding/signature allowances stay charged.
        reader.reserve(_object_bytes(format=len('"research_pipeline.operating_eligibility"'), version=1,
            authority_domain=_fragment_bytes(authority_domain), project_id=_fragment_bytes(project_id),
            purpose=_fragment_bytes(purpose), evaluated_at=_fragment_bytes(evaluated_at),
            status=_fragment_bytes(status), eligible=_fragment_bytes(eligible),
            decision=_fragment_bytes(decision_reference), signature_status=_fragment_bytes(signature_status),
            policy_status=_fragment_bytes(policy_status), binding=_fragment_bytes(binding),
            observed_heads=_fragment_bytes(observed_heads), history_signatures=_fragment_bytes(history_signatures),
            verified_artifacts=_array_bytes(_object_bytes(digest=66, size=len(str(artifact.size)))
                for artifact in reader.verified.values()), watermark=_fragment_bytes(watermark),
            policy_fingerprint=_fragment_bytes(policy_fingerprint), recheck_required=4))
        return reader.output(EligibilityResult({"format": "research_pipeline.operating_eligibility", "version": 1,
            "authority_domain": authority_domain, "project_id": project_id, "purpose": purpose,
            "evaluated_at": evaluated_at, "status": status, "eligible": eligible, "decision": decision_reference,
            "signature_status": signature_status, "policy_status": policy_status, "binding": binding,
            "observed_heads": observed_heads, "history_signatures": history_signatures,
            "verified_artifacts": [artifact.to_dict() for _, artifact in sorted(reader.verified.items())],
            "watermark": watermark, "policy_fingerprint": policy_fingerprint, "recheck_required": True}))
