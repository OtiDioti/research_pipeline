"""Private bounded assessment metadata handling; transactions remain owned by RecordStore.

The byte charges describe representation processing, not measured Python memory.
No helper here authenticates an actor, resolves policy or publishes metadata.
"""

from contextlib import contextmanager
from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, Submission, _identifier, _integer, _MAX_INTEGER,
)
from research_pipeline.operating_authority import (
    MAX_METADATA_RECORDS, MAX_REFERENCES, ENVELOPE_BYTES, RESULT_BYTES,
)
from research_pipeline.report_capture import _text_length, _integer_length
from research_pipeline.operating_authority_store import _object_bytes, _text_bound
from research_pipeline.snapshot import _canonical, _strict_json, SnapshotIntegrityError
from research_pipeline.tool_assessment_codec import ToolAssessmentLimitError, ToolAssessmentValidationError
from research_pipeline.tool_release_codec import scalar_size
from research_pipeline.tool_assessment_envelope import ToolAssessmentEnvelopeLimits


def _raw(value, name):
    """Read a fixed field of an exact checked value without dispatching user methods."""
    try:
        return object.__getattribute__(value, name)
    except AttributeError as error:
        raise ToolAssessmentValidationError(f"{name}: missing retained field") from error


def _text(value):
    """Bound retained text before encoding, parsing or scalar escape expansion."""
    if type(value) is not str:
        raise ToolAssessmentValidationError("metadata: expected exact text")
    if len(value) > ENVELOPE_BYTES:
        raise ToolAssessmentLimitError("envelope_bytes: raw text ceiling exceeded")
    if value.isascii():
        return len(value)
    size = 0
    for character in value:
        code = ord(character)
        if 0xD800 <= code <= 0xDFFF:
            raise ToolAssessmentValidationError("metadata: Unicode surrogate")
        size += 1 if code < 128 else 2 if code < 2048 else 3 if code < 65536 else 4
        if size > ENVELOPE_BYTES:
            raise ToolAssessmentLimitError("envelope_bytes: raw text ceiling exceeded")
    return size


def _scalar(value, *, integer=False, nullable=False):
    """Measure exact bounded scalars; leave signed integer semantics to their codec.

    The domain magnitude ceiling bounds decimal conversion and key hashing before
    allocation. It does not admit negative revisions or artifact sizes.
    """
    if nullable and value is None:
        return 4
    if integer:
        if type(value) is not int or not -_MAX_INTEGER <= value <= _MAX_INTEGER:
            raise ToolAssessmentValidationError("metadata integer: expected exact bounded integer")
        return len(str(value))
    _text(value)
    size = 2
    for character in value:
        size += scalar_size(ord(character))
        if size > ENVELOPE_BYTES:
            raise ToolAssessmentLimitError("envelope_bytes: escaped scalar ceiling exceeded")
    return size


def _length(row):
    """Reject missing joins and corrupt SQL storage types before fetching their payloads."""
    if row is None or any(type(n) is not int or n < 0 for n in row):
        raise ToolAssessmentValidationError("metadata: missing join or invalid stored type")
    return sum(row)


def _json(text, *, maximum_depth=64):
    """Read canonical generic JSON under a preparse depth bound, retaining generic scalars."""
    _text(text)
    if not text.isascii() or "\x7f" in text:
        raise ToolAssessmentValidationError("metadata: expected canonical ASCII JSON")
    try:
        return _strict_json(text, maximum_depth=maximum_depth)
    except SnapshotIntegrityError as error:
        if maximum_depth < 64 and str(error).startswith("JSON nesting exceeds"):
            raise ToolAssessmentLimitError("max_provenance_depth: stored creator ceiling exceeded") from error
        raise ToolAssessmentValidationError("metadata: invalid or noncanonical stored JSON") from error


def _provenance_fields(value):
    """Preflight exact retained creator fields without normalizing timestamps or JSON."""
    if type(value) is not CreationProvenance:
        raise ToolAssessmentValidationError("provenance: expected exact CreationProvenance")
    actor, date, details = (_raw(value, name) for name in ("actor", "created_at", "_details_json"))
    for item in (actor, date, details):
        _text(item)
    size = _object_bytes(actor=_scalar(actor), created_at=_scalar(date), details=len(details))
    return (actor, date, details), size


def _provenance(value):
    """Detach generic provenance and reject retained fields that reconstruction would repair."""
    (actor, date, details), _ = _provenance_fields(value)
    result = CreationProvenance(actor, date, _json(details))
    if result.created_at != date or result._details_json != details:
        raise ToolAssessmentValidationError("provenance: noncanonical retained creator")
    return result


def _shell(cls, **fields):
    """Build explicitly untrusted exact shells from bounded raw storage; keep them private.

    This bypasses normalizing constructors only to feed unchanged codec validation.
    No shell is returned by a public boundary before local validation succeeds.
    """
    result = object.__new__(cls)
    for name, value in fields.items():
        object.__setattr__(result, name, value)
    return result


def _candidate(kind, text):
    """Select guarded assessment handling, including a forged kind on canonical assessment text.

    This is only a safety selection; the unchanged codec must still validate the
    explicit discriminator, version, exact kind and every retained envelope field.
    """
    if type(kind) is str and kind == "tool_assessment":
        return True
    return (type(text) is str and text.startswith('{"assessment_id":')
            and '"format":"research_pipeline.tool_assessment_content"' in text)


def _assessment_request(submission):
    """Select safety handling by exact raw fields; this scan never constitutes admission."""
    if type(submission) is not Submission:
        raise DomainValidationError("submission: expected Submission")
    records = _raw(submission, "records")
    if type(records) is not tuple:
        raise DomainValidationError("records: expected exact retained tuple")
    # This allocation-free exact-field scan selects safety handling only.
    found = False
    for record in records:
        if type(record) is not RecordEnvelope:
            raise DomainValidationError("records: expected exact RecordEnvelope")
        kind, text = _raw(record, "kind"), _raw(record, "_content_json")
        if type(kind) is not str or type(text) is not str:
            related = ((type(kind) is str and kind == "tool_assessment")
                       or (type(text) is str and "research_pipeline.tool_assessment_content" in text))
            error = ToolAssessmentValidationError if related else DomainValidationError
            raise error("record: malformed retained kind/content")
        if kind == "tool_assessment" or "research_pipeline.tool_assessment_content" in text:
            found = True
    if found and len(records) > MAX_METADATA_RECORDS:
        raise ToolAssessmentLimitError("root_envelopes: processing ceiling exceeded")
    return found


class _Budget:
    """Finite assessment request/closure accounting in an existing owner's connection."""

    def __init__(self):
        """Start empty accounts; preparation must set request_size before commit.

        request_size is the prospective complete fingerprint-v1 canonical byte
        size, measured from bounded fields without serializing the request.
        """
        self.records = set()
        self.histories = {}
        self.history_revisions = 0
        self.references = 0
        self.metadata_bytes = 0
        self.sizes = {}
        self.typed = set()
        self.projections = set()
        self.plans = {}
        self.request_size = None

    def reserve(self, amount):
        """Charge fetched/retained representations before their protected allocation."""
        if self.metadata_bytes + amount > RESULT_BYTES:
            raise ToolAssessmentLimitError("metadata_bytes: processing ceiling exceeded")
        self.metadata_bytes += amount

    @contextmanager
    def temporary(self, amount):
        """Reserve bounded parse/reconstruction scratch and refund only this scratch."""
        self.reserve(amount)
        try:
            yield
        finally:
            self.metadata_bytes -= amount

    def record(self, key):
        """Reserve a distinct exact identity before fetching, retaining or enqueuing it."""
        if key not in self.records:
            if len(self.records) >= MAX_METADATA_RECORDS:
                raise ToolAssessmentLimitError("metadata_records: processing ceiling exceeded")
            self.records.add(key)

    def history(self, key):
        """Reserve a mandatory prefix including revision one without allocating range(N)."""
        old = self.histories.get(key[0], 0)
        increase = max(0, key[1] - old)
        if self.history_revisions + increase > MAX_METADATA_RECORDS:
            raise ToolAssessmentLimitError("history_revisions: processing ceiling exceeded")
        self.history_revisions += increase
        self.histories[key[0]] = max(old, key[1])

    def links(self, key, count):
        """Charge every projected occurrence once per fully retained exact envelope."""
        if key not in self.projections:
            if self.references + count > MAX_REFERENCES:
                raise ToolAssessmentLimitError("reference_occurrences: processing ceiling exceeded")
            self.references += count
            self.projections.add(key)

    def envelope(self, record):
        """Measure exact raw fields before copying, deferring semantics to the codec.

        Bounded exact identity text and signed integers are safe cache keys even
        when malformed; the original assessment decoder decides their validity.
        """
        if type(record) is not RecordEnvelope:
            raise ToolAssessmentValidationError("record: expected exact RecordEnvelope")
        identity, revision = _raw(record, "record_id"), _raw(record, "revision")
        _text(identity)
        revision_size = _scalar(revision, integer=True)
        key = identity, revision
        self.record(key)
        records, artifacts = _raw(record, "record_references"), _raw(record, "artifact_references")
        if type(records) is not tuple or type(artifacts) is not tuple:
            raise ToolAssessmentValidationError("projections: expected exact tuples")
        kind, content = _raw(record, "kind"), _raw(record, "_content_json")
        if _candidate(kind, content):
            if len(records) + len(artifacts) > ToolAssessmentEnvelopeLimits().max_projection_references:
                raise ToolAssessmentLimitError("max_projection_references: retained projection ceiling exceeded")
        self.links(key, len(records) + len(artifacts))
        raw_size = _text(kind) + _text(content) + _text(identity) + revision_size
        provenance, provenance_size = _provenance_fields(_raw(record, "provenance"))
        raw_size += sum(_text(item) for item in provenance)
        if raw_size > ENVELOPE_BYTES:
            raise ToolAssessmentLimitError("envelope_bytes: raw enclosing metadata ceiling exceeded")
        collections = []
        for values, cls, names in ((records, RecordReference, ("record_id", "revision", "relationship", "target_kind")),
                                   (artifacts, ArtifactReference, ("digest", "size"))):
            size = 2 + max(0, len(values) - 1)
            for item in values:
                if type(item) is not cls:
                    raise ToolAssessmentValidationError("projection: unexpected exact class")
                fields = {}
                for name in names:
                    value = _raw(item, name)
                    numeric = name in ("revision", "size")
                    # Check the aggregate raw lower bound before measuring the
                    # next escaped fragment, including repeated retained strings.
                    contribution = _scalar(value, integer=True) if numeric else (0 if value is None else _text(value))
                    raw_size += contribution
                    if raw_size > ENVELOPE_BYTES:
                        raise ToolAssessmentLimitError("envelope_bytes: raw enclosing metadata ceiling exceeded")
                    fields[name] = _scalar(value, integer=numeric, nullable=name == "target_kind")
                size += _object_bytes(**fields)
            collections.append(size)
        size = _object_bytes(record_id=_scalar(identity), revision=revision_size, kind=_scalar(kind),
            content=len(content), provenance=provenance_size, record_references=collections[0],
            artifact_references=collections[1],
            operational_status=_scalar(_raw(record, "operational_status"), nullable=True),
            scientific_disposition=_scalar(_raw(record, "scientific_disposition"), nullable=True))
        if size > ENVELOPE_BYTES:
            raise ToolAssessmentLimitError("envelope_bytes: processing ceiling exceeded")
        self.reserve(raw_size + size)
        self.sizes[key] = size
        return size

    def decode(self, record, decoder):
        """Charge retained content and six enclosing scratch representations before decoding."""
        key = record.record_id, record.revision
        if key not in self.typed:
            self.reserve(len(record._content_json))
            self.typed.add(key)
        with self.temporary(6 * self.sizes[key]):
            original = record if _candidate(record.kind, record._content_json) else _codec_input(record)
            return decoder(original)

    def preflight(self, connection, key):
        """Check SQL types, both counts, ordinals and byte framing before fetching metadata."""
        from research_pipeline.store import RecordNotFoundError
        if key in self.plans:
            return self.plans[key]
        self.record(key)
        columns = (_text_length("i.kind"), _text_length("r.content_json"), _text_length("r.provenance_json"),
            _text_length("r.operational_status", nullable=True), _text_length("r.scientific_disposition", nullable=True),
            _text_length("r.submission_id"), _text_length("s.fingerprint"), _text_length("a.committed_at"),
            _integer_length("r.ordinal"))
        row = connection.execute("SELECT " + ",".join(columns) + """ FROM revisions r
            LEFT JOIN identities i USING(record_id) LEFT JOIN submissions s USING(submission_id)
            LEFT JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        if row is None:
            raise RecordNotFoundError(f"record {key[0]}@{key[1]}: absent")
        actual = _length(row)
        if actual > ENVELOPE_BYTES:
            raise ToolAssessmentLimitError("envelope_bytes: fetched row ceiling exceeded")
        self.reserve(actual)
        tables = (("record_links", (_text_length("target_id"), _integer_length("target_revision", 1),
                    _text_length("relationship"), _text_length("target_kind", nullable=True))),
                  ("artifact_links", (_text_length("digest"), _integer_length("size"))))
        counts = [connection.execute(f"SELECT count(*) FROM {table} WHERE record_id=? AND revision=?", key).fetchone()[0]
                  for table, _ in tables]
        self.links(key, sum(counts))
        assessment = connection.execute(
            """SELECT i.kind='tool_assessment' OR
                (substr(r.content_json,1,17)='{"assessment_id":' AND
                 instr(r.content_json,'"format":"research_pipeline.tool_assessment_content"')>0)
                FROM revisions r JOIN identities i USING(record_id)
                WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        controls = ToolAssessmentEnvelopeLimits() if assessment is not None and assessment[0] == 1 else None
        # Valid canonical creator identifiers/timestamps are unescaped ASCII. Thus
        # removing fixed outer framing gives the codec's exact raw text charge.
        # Invalid representations remain subject to strict parsing and codec checks.
        metadata_chars = len(key[0]) + row[0] + max(0, row[2] - _object_bytes(actor=2, created_at=2, details=0))
        if controls is not None:
            if sum(counts) > controls.max_projection_references:
                raise ToolAssessmentLimitError("max_projection_references: stored projection ceiling exceeded")
            if metadata_chars > controls.max_metadata_chars:
                raise ToolAssessmentLimitError("max_metadata_chars: stored metadata ceiling exceeded")
        collections = []
        for (table, columns), count in zip(tables, counts):
            size = 2 + max(0, count - 1)
            cursor = connection.execute("SELECT CASE WHEN typeof(ordinal)='integer' THEN ordinal ELSE NULL END,"
                + ",".join(columns) + f" FROM {table} WHERE record_id=? AND revision=? ORDER BY ordinal", key)
            for ordinal in range(count):
                link = cursor.fetchone()
                if link is None or type(link[0]) is not int or link[0] != ordinal:
                    raise ToolAssessmentValidationError("metadata: noncontiguous link ordinals")
                contribution = _length(link[1:]) + len(str(ordinal))
                actual += contribution
                if actual > ENVELOPE_BYTES:
                    raise ToolAssessmentLimitError("envelope_bytes: fetched links ceiling exceeded")
                self.reserve(contribution)
                metadata_chars += link[1] + (link[3] + link[4] if table == "record_links" else 0)
                if controls is not None and metadata_chars > controls.max_metadata_chars:
                    raise ToolAssessmentLimitError("max_metadata_chars: stored metadata ceiling exceeded")
                if table == "record_links":
                    size += _object_bytes(record_id=_text_bound(link[1]), revision=link[2],
                        relationship=_text_bound(link[3]), target_kind=_text_bound(link[4]))
                else:
                    size += _object_bytes(digest=_text_bound(link[1]), size=link[2])
            if cursor.fetchone() is not None:
                raise ToolAssessmentValidationError("metadata: link count changed")
            collections.append(size)
        size = _object_bytes(record_id=_text_bound(len(key[0])), revision=len(str(key[1])),
            kind=_text_bound(row[0]), content=row[1], provenance=row[2],
            operational_status=_text_bound(row[3]), scientific_disposition=_text_bound(row[4]),
            record_references=collections[0], artifact_references=collections[1])
        if size > ENVELOPE_BYTES:
            raise ToolAssessmentLimitError("envelope_bytes: enclosing envelope ceiling exceeded")
        self.reserve(size)
        self.sizes[key] = size
        self.plans[key] = size
        return size

    def shallow(self, connection, key):
        """Charge a shallow kind fetch without inspecting its payload or attachments."""
        row = connection.execute("SELECT " + _text_length("i.kind") + """ FROM revisions r
            LEFT JOIN identities i USING(record_id) WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        if row is not None:
            size = _length(row)
            if size > ENVELOPE_BYTES:
                raise ToolAssessmentLimitError("envelope_bytes: shallow kind ceiling exceeded")
            self.reserve(size)

    def read(self, connection, key, reader=None):
        """Reconstruct bounded raw metadata in the supplied connection, never artifact bytes.

        An existing reader still owns its read hooks and smaller independent limits.
        Raw strings are separately checked so normalization cannot repair stored facts.
        Both preflights retain their permanent charges; assessment scratch covers
        the supplied read and raw reconstruction and is refunded even on failure.
        """
        if reader is not None:
            # Both preflights run before either reconstruction. The supplied
            # reader retains its smaller limits and its own subsequent read hook.
            reader.preflight(key)
        size = self.preflight(connection, key)
        with self.temporary(6 * size):
            # Keep scratch through both reconstructions, including cached read hooks.
            if reader is not None:
                reader.read(key)
            row = connection.execute("""SELECT i.kind,r.content_json,r.provenance_json,r.operational_status,
                r.scientific_disposition FROM revisions r JOIN identities i USING(record_id)
                WHERE r.record_id=? AND r.revision=?""", key).fetchone()
            # Assessment text stays untouched until its codec's guarded A–F pass.
            # In particular, selected reads verify direct bytes before content errors.
            candidate = _candidate(row[0], row[1])
            content = None if candidate else _json(row[1])
            if row[0] == "tool_assessment":
                controls = ToolAssessmentEnvelopeLimits()
                # The enclosing provenance object adds exactly one level; all
                # creator text plus details still fits its unchanged codec ceiling.
                framing = _object_bytes(actor=2, created_at=2, details=0)
                if len(row[2]) > controls.max_metadata_chars + framing:
                    raise ToolAssessmentLimitError("max_metadata_chars: stored creator ceiling exceeded")
                provenance = _json(row[2], maximum_depth=controls.max_provenance_depth + 1)
            else:
                provenance = _json(row[2])
            if ((not candidate and type(content) is not dict)
                    or type(provenance) is not dict or set(provenance) != {"actor", "created_at", "details"}):
                raise ToolAssessmentValidationError("metadata: invalid content/provenance shell")
            creator = _shell(CreationProvenance, actor=provenance["actor"], created_at=provenance["created_at"],
                             _details_json=_canonical(provenance["details"]))
            # Reject normalization before releasing raw metadata to any codec.
            _provenance(creator)
            records = tuple(RecordReference(*link) for link in connection.execute("""SELECT target_id,target_revision,
                relationship,target_kind FROM record_links WHERE record_id=? AND revision=? ORDER BY ordinal""", key))
            artifacts = tuple(ArtifactReference(*link) for link in connection.execute("""SELECT digest,size
                FROM artifact_links WHERE record_id=? AND revision=? ORDER BY ordinal""", key))
            return _shell(RecordEnvelope, record_id=key[0], revision=key[1], kind=row[0], _content_json=row[1],
                provenance=creator, record_references=records, artifact_references=artifacts,
                operational_status=row[3], scientific_disposition=row[4])


def _codec_input(record):
    """Copy bounded raw mixed-member shells without carrying instance serializer overrides.

    Older unchanged codecs call generic serializers internally. Their private input
    must therefore contain only fixed exact raw fields, while retaining original
    content, timestamps and projections for subsequent rejection rather than repair.
    Assessment codecs receive their original retained envelope directly instead.
    """
    _json(_raw(record, "_content_json"))
    provenance = _raw(record, "provenance")
    fields, _ = _provenance_fields(provenance)
    _json(fields[2])
    creator = _shell(CreationProvenance, actor=fields[0], created_at=fields[1], _details_json=fields[2])
    records = tuple(_shell(RecordReference, **{name: _raw(ref, name) for name in
        ("record_id", "revision", "relationship", "target_kind")}) for ref in _raw(record, "record_references"))
    artifacts = tuple(_shell(ArtifactReference, digest=_raw(ref, "digest"), size=_raw(ref, "size"))
                      for ref in _raw(record, "artifact_references"))
    return _shell(RecordEnvelope, **{name: _raw(record, name) for name in
        ("record_id", "revision", "kind", "_content_json", "operational_status", "scientific_disposition")},
        provenance=creator, record_references=records, artifact_references=artifacts)


def _owned(record):
    """Detach checked raw fields with class-owned constructors rather than instance serializers."""
    references = tuple(RecordReference(*(_raw(ref, name) for name in
        ("record_id", "revision", "relationship", "target_kind"))) for ref in _raw(record, "record_references"))
    artifacts = tuple(ArtifactReference(_raw(ref, "digest"), _raw(ref, "size"))
                      for ref in _raw(record, "artifact_references"))
    return RecordEnvelope(_raw(record, "record_id"), _raw(record, "revision"), _raw(record, "kind"),
        _json(_raw(record, "_content_json")), _provenance(_raw(record, "provenance")), references, artifacts,
        _raw(record, "operational_status"), _raw(record, "scientific_disposition"))


def _prepare(submission, decoder=None):
    """Bound, decode originals in order and detach an assessment-aware mixed request.

    Generic callers omit decoder; they receive bounded generic storage validation,
    never inferred typed admission. Control parsing and reconstruction share six
    temporary enclosing representations; permanent request charges survive them.
    No transaction or fingerprint is created here, but its measured size is retained.
    """
    budget = _Budget()
    records = _raw(submission, "records")
    if type(records) is not tuple or len(records) > MAX_METADATA_RECORDS:
        raise ToolAssessmentLimitError("root_envelopes: processing ceiling exceeded")
    # Reject repeated root identities before cache keys could hide their occurrences.
    identities = set()
    for record in records:
        if type(record) is not RecordEnvelope:
            raise ToolAssessmentValidationError("records: expected exact RecordEnvelope")
        identity = _raw(record, "record_id")
        _text(identity)
        if identity in identities:
            raise ToolAssessmentValidationError("records: repeated root identity")
        identities.add(identity)
    # All cheap root lengths/counts precede any protected parse or request copy.
    sizes = [budget.envelope(record) for record in records]
    identity = _raw(submission, "submission_id")
    _identifier(identity, "submission_id")
    provenance = _raw(submission, "provenance")
    _, provenance_size = _provenance_fields(provenance)
    heads = _raw(submission, "_expected_heads_json")
    _text(heads)
    budget.reserve(_text(identity) + _text(heads) + sum(_text(item) for item in _provenance_fields(provenance)[0]))
    control_size = _object_bytes(submission_id=_scalar(identity), provenance=provenance_size,
                                expected_heads=len(heads))
    request_size = _object_bytes(fingerprint_version=1, submission=_object_bytes(
        submission_id=_scalar(identity), provenance=provenance_size, expected_heads=len(heads),
        records=2 + max(0, len(sizes) - 1) + sum(sizes)))
    budget.request_size = request_size
    # Canonical request retention and its ASCII hashing representation are separate.
    budget.reserve(2 * request_size)
    values = tuple(budget.decode(record, decoder) for record in records) if decoder is not None else ()
    owned_values = []
    for record, size in zip(records, sizes):
        with budget.temporary(6 * size):
            owned_values.append(_owned(record))
    owned = tuple(owned_values)
    with budget.temporary(6 * control_size):
        expectations = _json(heads)
        if type(expectations) is not dict:
            raise ToolAssessmentValidationError("expected_heads: expected ordinary object")
        for name, revision in expectations.items():
            _identifier(name, "expected_heads identity")
            _integer(revision, "expected head", 0)
        identities = {record.record_id for record in owned}
        if not owned or len(identities) != len(owned) or set(expectations) != identities:
            raise ToolAssessmentValidationError("records/expected_heads: nonempty unique matching identities required")
        result = _shell(Submission, submission_id=identity, provenance=_provenance(provenance),
                        records=owned, _expected_heads_json=heads)
    return result, values, budget
