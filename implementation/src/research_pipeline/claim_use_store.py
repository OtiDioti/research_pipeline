"""Connection-owned claim-use planning, propagation and coherent bounded metadata reads.

No helper owns a write transaction or commits. Exact historical pins are never
repointed. Only explicit premise-use edges carry deductive support dependencies.
"""

from collections import deque
import sqlite3
from dataclasses import dataclass, field

from research_pipeline.claim_use import (
    ClaimUse, ClaimUseInspection, ClaimUseHistoryPage, ClaimUseInspectionLimits,
    ClaimUseLimitError, ClaimUseIntegrityError, FORMAT, WRITE_LIMITS, _links,
    decode_envelope, _check_count,
)
from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope,
    RecordReference, Submission,
    _identifier, _integer, _MAX_INTEGER,
)
from research_pipeline.assessment import Review, Issue
from research_pipeline.scientific import Claim, ResearchContext, Justification, Evidence
from research_pipeline.snapshot import (
    SnapshotLimits, SnapshotLimitError, SnapshotIntegrityError, _bounded_json, _canonical,
    _strict_json, _check_json_depth,
)


def require_schema(store):
    """Require registration schema 4, 5 or 6 without upgrading older metadata."""
    from research_pipeline.store import StoreLayoutError
    store._require_open()
    if store._schema_version not in (4, 5, 6):
        raise StoreLayoutError("claim-use registration and inspection require explicit migration to schema 4")


def _raw(value, name):
    """Read a retained field without caller dispatch; missing fields are domain errors."""
    try:
        return object.__getattribute__(value, name)
    except AttributeError as error:
        raise DomainValidationError(f"{name}: missing retained field") from error


def relevant_request(submission, *, policy=False, context=False):
    """Validate retained shells and select legacy work or active policy/context members."""
    if type(submission) is not Submission:
        raise DomainValidationError("submission: expected exact Submission")
    records = _raw(submission, "records")
    if type(records) is not tuple:
        raise DomainValidationError("records: expected exact retained tuple")
    found = False
    for record in records:
        if type(record) is not RecordEnvelope:
            raise DomainValidationError("records: expected exact RecordEnvelope")
        kind, text = _raw(record, "kind"), _raw(record, "_content_json")
        if type(kind) is not str or type(text) is not str:
            raise DomainValidationError("record: malformed retained kind/content")
        if kind in ("review", "issue", "promotion_eligibility") or FORMAT in text or (policy and kind == "decision") or (context and kind == "research_context"):
            found = True
    return found


def _checked_shell(value, cls, fields):
    """Copy only exact fixed scalar fields into a private shell, ignoring instance overrides.

    Semantic validation remains with ordinary normalization and typed codecs. This
    guard establishes safe values before any traversal, measurement or serialization.
    Field specifications map names to an exact type and whether None is permitted.
    """
    if type(value) is not cls:
        raise DomainValidationError(f"metadata: expected exact {cls.__name__}")
    result = object.__new__(cls)
    for name, (kind, nullable) in fields.items():
        item = _raw(value, name)
        if not (nullable and item is None) and type(item) is not kind:
            raise DomainValidationError(f"{name}: malformed retained scalar")
        if kind is int and type(item) is int and not -_MAX_INTEGER <= item <= _MAX_INTEGER:
            raise DomainValidationError(f"{name}: integer outside metadata range")
        object.__setattr__(result, name, item)
    return result


def _creator_shell(value):
    """Detach exact provenance strings before measuring or parsing retained details."""
    return _checked_shell(value, CreationProvenance,
                          {n: (str, False) for n in ("actor", "created_at", "_details_json")})


def _request_shell(submission):
    """Detach freshness-relevant retained shells without invoking caller-controlled hooks."""
    result = _checked_shell(submission, Submission,
                            {"submission_id": (str, False), "_expected_heads_json": (str, False)})
    object.__setattr__(result, "provenance", _creator_shell(_raw(submission, "provenance")))
    records = []
    occurrences = 0
    for original in _raw(submission, "records"):
        record = _checked_shell(original, RecordEnvelope, {
            "record_id": (str, False), "revision": (int, False), "kind": (str, False),
            "_content_json": (str, False), "operational_status": (str, True),
            "scientific_disposition": (str, True)})
        object.__setattr__(record, "provenance", _creator_shell(_raw(original, "provenance")))
        for name, cls, fields in (
                ("record_references", RecordReference, {"record_id": (str, False), "revision": (int, False),
                                                       "relationship": (str, False), "target_kind": (str, True)}),
                ("artifact_references", ArtifactReference, {"digest": (str, False), "size": (int, False)})):
            members = _raw(original, name)
            if type(members) is not tuple:
                raise DomainValidationError(f"{name}: expected exact retained tuple")
            occurrences += len(members)
            _check_count(occurrences, WRITE_LIMITS["references"], "references")
            object.__setattr__(record, name, tuple(_checked_shell(item, cls, fields) for item in members))
        records.append(record)
    object.__setattr__(result, "records", tuple(records))
    return result


def preflight(store, submission):
    """Return safe retained shells after applicable schema-4/5/6 admission bounds.

    Older schemas retain generic normalization and original-receipt reconciliation;
    only fresh admission in prepare requires schema 4. Assessment originals must
    first pass their independent preparation, before entering this boundary.
    """
    legacy = relevant_request(submission)
    if store._schema_version not in (4, 5, 6) or not (legacy or (
            store._schema_version in (5, 6) and relevant_request(
                submission, policy=True, context=store._schema_version == 6))):
        return submission
    if not legacy:
        # Existence only bypasses *new* policy/context preflight. It neither acknowledges
        # nor compares a request; the owning write transaction does both later.
        identity = _raw(submission, "submission_id")
        _identifier(identity, "submission_id")
        from research_pipeline.store import _database_error
        try:
            used = store._connection.execute("SELECT 1 FROM submissions WHERE submission_id=?", (identity,)).fetchone()
        except sqlite3.Error as error:
            raise _database_error(error) from error
        if used:
            return submission
    _check_count(len(_raw(submission, "records")), WRITE_LIMITS["records"], "records")
    submission = _request_shell(submission)
    size = (len(submission.submission_id) + len(submission._expected_heads_json)
            + sum(len(_raw(submission.provenance, n)) for n in ("actor", "created_at", "_details_json")))
    _check_count(size, WRITE_LIMITS["request_bytes"], "request_bytes")
    occurrences = 0
    artifacts = {}
    for record in submission.records:
        record_size = (len(record._content_json) + len(record.record_id) + len(record.kind)
                       + sum(len(_raw(record.provenance, n)) for n in ("actor", "created_at", "_details_json"))
                       + sum(len(r.record_id) + len(r.relationship) + len(r.target_kind or "")
                             for r in record.record_references)
                       + sum(len(a.digest) for a in record.artifact_references))
        _check_count(record_size, WRITE_LIMITS["record_bytes"], "record_bytes")
        size += record_size
        for artifact in record.artifact_references:
            artifacts[artifact.digest] = artifact.size
        _check_count(len(artifacts), WRITE_LIMITS["artifacts"], "artifacts")
        _check_count(sum(artifacts.values()), WRITE_LIMITS["artifact_bytes"], "artifact_bytes")
        try:
            bounded(record.to_dict(), WRITE_LIMITS["record_bytes"], "record_bytes")
        except (TypeError, ValueError, RecursionError) as error:
            if isinstance(error, DomainValidationError):
                raise
            raise DomainValidationError("record: malformed retained JSON") from error
        occurrences += len(record.record_references) + len(record.artifact_references)
        _check_count(size, WRITE_LIMITS["request_bytes"], "request_bytes")
        _check_count(occurrences, WRITE_LIMITS["references"], "references")
    try:
        text = bounded({"fingerprint_version": 1, "submission": submission.to_dict()},
                       WRITE_LIMITS["request_bytes"], "request_bytes")
    except (TypeError, ValueError, RecursionError) as error:
        if isinstance(error, DomainValidationError):
            raise
        raise DomainValidationError("submission: malformed retained JSON") from error
    try:
        _check_json_depth(text)
    except SnapshotIntegrityError as error:
        raise DomainValidationError(f"claim-use request nesting: {error}") from error
    _check_count(6 * len(text), WRITE_LIMITS["metadata_bytes"], "metadata_bytes")
    return submission


def bounded(value, maximum, dimension):
    """Bound complete canonical serialization, translating the shared incremental guard."""
    try:
        return _bounded_json(value, maximum, dimension)
    except SnapshotLimitError as error:
        raise ClaimUseLimitError(f"{dimension}: {error}") from error


def _cause_key(reader, cause):
    """Encode an active policy/context cause within remaining scratch before retaining its key.

    Callers charge attempted cause occurrences separately, before deduplication.
    Reusing this bounded canonical text avoids a second unaccounted encoding; the
    legacy path keeps its original accounting and cause shapes unchanged.
    """
    remaining = (reader.caps["metadata_bytes"] - reader.counts["metadata_bytes"]) // 6
    if reader.aggregate is not None:
        remaining = min(remaining, (reader.aggregate.caps["metadata_bytes"]
                                   - reader.aggregate.counts["metadata_bytes"]) // 6)
    text = bounded(cause, remaining, "metadata_bytes")
    reader.charge("metadata_bytes", 6 * len(text))
    return text


def pin(reference):
    """Return the exact target triple independent of its incoming semantic role."""
    return reference.record_id, reference.revision, reference.target_kind


def keypin(key, kind="promotion_eligibility"):
    """Return a detached exact pin for audit facts without suggesting authority."""
    return dict(record_id=key[0], revision=key[1], target_kind=kind)


class Reader:
    """Finite connection-owned metadata reader shared by admission and freshness planning.

    A cutoff is used only by chronological integrity checking. It exposes the
    state before that event, plus its explicit proposed batch, without replaying it.
    The history hook deliberately preserves ordinary scientific admission rules.
    """

    def __init__(self, store, connection, proposed=(), limits=None, cutoff=None, *, overlay=None, aggregate=None, policy=None, context=None):
        """Retain independent caches/counters, optionally viewing a private prospective plan.

        Overlay readers charge proposed values on demand as persisted metadata would
        be charged. Their work also accrues to the owning write's aggregate account.
        The private policy/context selections match the event's activation semantics;
        Legacy feature selections preserve preceding output and accounting exactly.
        """
        self.store, self.connection, self.cutoff = store, connection, cutoff
        self.policy_active = store._schema_version in (5, 6) if policy is None else policy
        self.context_active = store._schema_version == 6 if context is None else context
        self.overlay, self.aggregate = overlay, aggregate
        self.caps = dict(WRITE_LIMITS)
        if limits is not None:
            limits.__post_init__()
            for name in ("bindings", "records", "references", "assertion_revisions", "metadata_bytes"):
                self.caps[name] = getattr(limits, "max_" + name)
        self.counts = {name: 0 for name in self.caps}
        self.seen_records, self.typed_keys, self.assertions = set(), set(), set()
        self.policies = set()
        self.policy_values = {}
        self.contexts = set()
        self.context_values = {}
        self.binding_keys = set()
        self.cache = {}
        self.values = {}
        self.proposed = {(r.record_id, r.revision): r for r in proposed}
        self.proposed_heads = {r.record_id: r.revision for r in proposed}
        self.artifacts = {}
        self.histories = {}
        if overlay is None:
            for key, record in self.proposed.items():
                self.record(key)
                self.charge("references", len(record.record_references) + len(record.artifact_references))
                size = len(record._content_json) + len(record.provenance._details_json)
                _check_count(size, self.caps["record_bytes"], "record_bytes")
                bounded(record.to_dict(), self.caps["record_bytes"], "record_bytes")
                self.charge("metadata_bytes", 6 * size)
                self.cache[key] = record

    def charge(self, dimension, amount=1):
        """Charge examined occurrences independently of target cache hits; fail closed."""
        self.counts[dimension] += amount
        _check_count(self.counts[dimension], self.caps[dimension], dimension)
        # Distinct nodes are unioned through record()/binding() across roots;
        # occurrence and byte work always accumulate, including repeated reads.
        if self.aggregate is not None and dimension not in ("records", "bindings"):
            self.aggregate.charge(dimension, amount)

    def binding(self, key):
        """Count distinct visited exact binding nodes across all phases of one operation."""
        if key not in self.binding_keys:
            self.charge("bindings")
            self.binding_keys.add(key)
            if self.aggregate is not None:
                self.aggregate.binding(key)

    def record(self, key):
        """Count distinct exact metadata targets, including shallow and proposed members."""
        if key not in self.seen_records:
            self.charge("records")
            self.seen_records.add(key)
            if self.aggregate is not None:
                self.aggregate.record(key)

    def rows(self, sql, args=(), dimension="index_rows"):
        """Preflight and stream a caller-supplied indexed range, charging its sentinel before payloads.

        Callers supply complete temporal predicates and index-compatible ordering;
        both passes use exactly that range. Rejected occurrences still consume work.
        """
        remaining = self.caps[dimension] - self.counts[dimension]
        projection, source = sql.strip()[7:].split("FROM", 1)
        columns = [c.strip() for c in projection.split(",")]
        expressions = ",".join(f"typeof({c}),length(CAST({c} AS BLOB))" for c in columns)
        count = 0
        # Reserve complete scalar/UTF-8 link representations before fetching
        # variable text, including rejected-context candidates and corrupt rows.
        for sizes in self.connection.execute("SELECT " + expressions + " FROM" + source + " LIMIT ?",
                                             (*args, remaining + 1)):
            self.charge(dimension)
            count += 1
            size = 0
            for i, column in enumerate(columns):
                name = column.rsplit(".", 1)[-1]
                expected = "integer" if (name.endswith("revision") or name.endswith("ordinal")
                                         or name in ("event_id", "registration_event")) else "text"
                if sizes[2*i] != expected or type(sizes[2*i+1]) is not int:
                    raise ClaimUseIntegrityError("invalid freshness index scalar types")
                size += sizes[2*i+1]
            _check_count(size, self.caps["record_bytes"], "record_bytes")
            self.charge("metadata_bytes", 8 * size)
        fetched = 0
        for row in self.connection.execute(sql + " LIMIT ?", (*args, count)):
            fetched += 1
            yield row
        if fetched != count:
            raise ClaimUseIntegrityError("index count changed within owned snapshot")

    def read(self, key, *, classify=True):
        """Reconstruct exact metadata after scalar/link preflight, including private proposed values.

        Proposed values reserve framing and reconstruction work against the same
        budgets as persisted rows; cache hits never alter a root's initial charge.
        Classification is enabled by default for existing readers. Private shallow
        policy reads disable it, retaining exact envelope validation and constraining
        stored reconstruction by both local and aggregate remaining metadata budgets.
        Limit and integrity failures retain claim-use error translations.
        """
        from research_pipeline.store import RecordNotFoundError
        self.record(key)
        if key in self.cache:
            return self.cache[key]
        if self.overlay is not None and key in self.proposed:
            return self._proposed_record(key)
        row = self.connection.execute("""SELECT typeof(r.revision),typeof(r.content_json),
            typeof(r.provenance_json),typeof(i.kind),a.event_id,
            length(CAST(r.content_json AS BLOB)),length(CAST(r.provenance_json AS BLOB))
            FROM revisions r JOIN identities i USING(record_id) JOIN audit_events a USING(submission_id)
            WHERE r.record_id=? AND r.revision=?""", key).fetchone()
        if row is None or (self.cutoff is not None and row[4] >= self.cutoff):
            raise RecordNotFoundError(f"record {key[0]}@{key[1]}: absent")
        if row[:4] != ("integer", "text", "text", "text"):
            raise ClaimUseIntegrityError("invalid stored metadata scalar types")
        if any(type(n) is not int or n < 0 for n in row[5:]):
            raise ClaimUseIntegrityError("invalid stored UTF-8 metadata lengths")
        _check_count(sum(row[5:]), self.caps["record_bytes"], "record_bytes")
        remaining = self.caps["metadata_bytes"] - self.counts["metadata_bytes"]
        if classify is False and self.aggregate is not None:
            remaining = min(remaining, self.aggregate.caps["metadata_bytes"]
                            - self.aggregate.counts["metadata_bytes"])
        limits = SnapshotLimits(1, self.caps["records"], self.caps["references"],
                                8 * self.caps["record_bytes"], max(1, remaining),
                                256, 1024, self.caps["record_bytes"], self.caps["metadata_bytes"])
        try:
            record, entry, size, refs = self.store._snapshot_record(
                self.connection, key, limits, remaining // 6,
                self.caps["references"] - self.counts["references"],
                **({"_classify": False} if classify is False else {}))
        except SnapshotLimitError as error:
            dimension = "references" if "references" in str(error) else "record_bytes/metadata_bytes"
            raise ClaimUseLimitError(f"{dimension}: {error}") from error
        except SnapshotIntegrityError as error:
            raise ClaimUseIntegrityError(str(error)) from error
        _check_count(len(entry["envelope_json"]), self.caps["record_bytes"], "record_bytes")
        self.charge("metadata_bytes", 6 * (size + len(entry["envelope_json"])))
        self.charge("references", refs)
        self.cache[key] = record
        return record

    def _proposed_record(self, key):
        """Cache one checked proposed envelope with persisted-equivalent framing and work charges.

        The enclosing read already counted this exact key. Reserve future commit
        metadata at its full width; exceeding any ceiling raises ClaimUseLimitError.
        """
        envelope = self.proposed[key]
        provenance = _canonical(envelope.provenance.to_dict())
        _check_count(len(envelope._content_json) + len(provenance), self.caps["record_bytes"], "record_bytes")
        # Mirror _snapshot_record's fetched metadata and repeated reconstruction
        # charges, reserving the future commit's full timestamp/fingerprint width.
        size = 2 * (len(envelope.kind) + len(envelope._content_json) + len(provenance)
                    + len(envelope.operational_status or "") + len(envelope.scientific_disposition or "")
                    + len(self.overlay.submission_id) + 27 + 64 + len(key[0]) + len(str(key[1])))
        for ordinal, ref in enumerate(envelope.record_references):
            size += len(ref.relationship) + len(ref.record_id) + len(str(ref.revision)) + len(ref.target_kind or "") + len(str(ordinal))
        for ordinal, ref in enumerate(envelope.artifact_references):
            size += len(ref.digest) + len(str(ref.size)) + len(str(ordinal))
        self.charge("references", len(envelope.record_references) + len(envelope.artifact_references))
        self.charge("metadata_bytes", 6 * size)
        text = bounded(envelope.to_dict(), self.caps["record_bytes"], "record_bytes")
        self.charge("metadata_bytes", 6 * len(text))
        self.cache[key] = envelope
        return envelope

    def typed(self, reference, expected):
        """Resolve an exact constrained role without authenticating shallow declarations."""
        from research_pipeline.store import ReferenceResolutionError, _decode_typed_envelope
        key = reference.record_id, reference.revision
        envelope = self.read(key)
        if envelope.kind != reference.target_kind:
            raise ReferenceResolutionError(f"{reference.relationship}: wrong kind for {key}")
        if key not in self.values:
            self.retain_typed(envelope)
            try:
                self.values[key] = _decode_typed_envelope(envelope)
            except ClaimUseLimitError:
                raise
            except DomainValidationError as error:
                raise ReferenceResolutionError(f"{reference.relationship} {key}: unsupported typed content: {error}") from error
        if type(self.values[key]) is not expected:
            raise ReferenceResolutionError(f"{reference.relationship} {key}: expected typed {expected.__name__}")
        return self.values[key]

    def shallow(self, reference):
        """Check exact existence and declared kind without fetching content or outgoing links."""
        from research_pipeline.store import ReferenceResolutionError
        key = reference.record_id, reference.revision
        self.record(key)
        self.charge("references")
        if key in self.proposed:
            kind = self.proposed[key].kind
        else:
            row = self.connection.execute("""SELECT i.kind,a.event_id FROM revisions r
                JOIN identities i USING(record_id) JOIN audit_events a USING(submission_id)
                WHERE r.record_id=? AND r.revision=?""", key).fetchone()
            kind = row[0] if row and (self.cutoff is None or row[1] < self.cutoff) else None
        if kind is None or (reference.target_kind is not None and kind != reference.target_kind):
            raise ReferenceResolutionError(f"{reference.relationship} {key}: absent or wrong kind")
        return kind

    def retain_typed(self, envelope):
        """Charge retained codec/canonicalization scratch before another decoding operation."""
        key = envelope.record_id, envelope.revision
        if key not in self.typed_keys:
            self.charge("metadata_bytes", 6 * len(envelope._content_json))
            self.typed_keys.add(key)

    def history(self, envelope, value):
        """Leave scientific history semantics to ordinary admission, without dossier rules."""
        return None

    def history_count(self, key):
        """Account passive Tool predecessor work without replacing its independent budget."""
        self.record(key)

    def head(self, identity, *, proposed=True):
        """Seek the visible head, optionally excluding the proposed successor overlay."""
        if proposed and identity in self.proposed_heads:
            return self.proposed_heads[identity]
        if self.cutoff is None:
            row = self.connection.execute("SELECT head FROM identities WHERE record_id=?", (identity,)).fetchone()
        else:
            row = self.connection.execute("""SELECT revision FROM claim_use_revision_events INDEXED BY claim_use_revision_event
                WHERE record_id=? AND event_id<? ORDER BY event_id DESC,revision DESC LIMIT 1""", (identity, self.cutoff)).fetchone()
        return row[0] if row else None

    def policy(self, key):
        """Resolve one exact shallow Decision declaration without interpreting its graph.

        A generic JSON object, including {}, is valid. Metadata reconstruction and
        strict canonical envelope checking are required; attachments are not read.
        Recognized format markers remain ordinary attributed JSON, with no
        scientific or operating-policy decoding. Scratch is reserved before strict
        policy parsing and envelope validation; deficient budgets fail closed.
        The independent revision ceiling counts each exact resolution once here
        and counts independent prospective-root resolutions in the write account.
        """
        from research_pipeline.store import ReferenceResolutionError
        if key not in self.policies:
            self.charge("policy_revisions")
            self.policies.add(key)
        self.charge("references")
        # Classification can dispatch codecs before policy-validation scratch is
        # reserved, and policy declarations require only shallow exact metadata.
        envelope = self.read(key, classify=False)
        if envelope.kind != "decision":
            raise ReferenceResolutionError(f"policy {key}: expected Decision")
        if key in self.policy_values:
            return self.policy_values[key]
        self.retain_typed(envelope)
        try:
            content = _strict_json(envelope._content_json)
            if type(content) is not dict or _canonical(content) != envelope._content_json:
                raise ValueError("noncanonical Decision JSON object")
            # Reconstructing verifies states and exact envelope scalar contracts,
            # without typed scientific or operating-policy dispatch.
            if RecordEnvelope.from_dict(envelope.to_dict()) != envelope:
                raise ValueError("incoherent Decision envelope")
        except (ValueError, TypeError, RecursionError) as error:
            raise ReferenceResolutionError(f"policy {key}: malformed declaration: {error}") from error
        self.policy_values[key] = content
        return content

    def context(self, key):
        """Resolve an exact supported target scope from metadata, never attachment bytes.

        Count distinct required context revisions independently of assertions and
        policies. Reserve codec scratch before the scientific decoder and cache
        only canonical, complete envelopes with coherent ordered projections.
        Independent prospective readers also charge the aggregate write account.
        """
        from research_pipeline.store import ReferenceResolutionError
        from research_pipeline.scientific import decode_envelope as decode_context
        if key not in self.contexts:
            self.charge("context_revisions")
            self.contexts.add(key)
        self.charge("references")
        envelope = self.read(key, classify=False)
        if envelope.kind != "research_context":
            raise ReferenceResolutionError(f"target context {key}: expected ResearchContext")
        if key in self.context_values:
            return self.context_values[key]
        # Another role may already have decoded this envelope through typed().
        # This independent semantic cache still allocates its own codec and
        # canonicalization representations, so shared typed_keys cannot discount it.
        self.charge("metadata_bytes", 6 * len(envelope._content_json))
        try:
            value = decode_context(envelope)
            if type(value) is not ResearchContext or _canonical(value.to_dict()) != envelope._content_json:
                raise DomainValidationError("noncanonical or unsupported ResearchContext")
        except DomainValidationError as error:
            raise ReferenceResolutionError(f"target context {key}: complete impact requires coherent content: {error}") from error
        self.context_values[key] = value
        return value

    def assertion(self, key):
        """Require coherent local assertion content under a separate exact-revision ceiling."""
        from research_pipeline.store import ReferenceResolutionError, _decode_typed_envelope
        if key not in self.assertions:
            self.charge("assertion_revisions")
            self.assertions.add(key)
        envelope = self.read(key)
        if envelope.kind not in ("review", "issue"):
            raise ReferenceResolutionError(f"assertion {key}: expected Review or Issue")
        if key not in self.values:
            self.retain_typed(envelope)
            try:
                self.values[key] = _decode_typed_envelope(envelope)
            except ClaimUseLimitError:
                raise
            except DomainValidationError as error:
                raise ReferenceResolutionError(f"assertion {key}: complete impact requires supported coherent content: {error}") from error
        if type(self.values[key]) not in (Review, Issue):
            raise ReferenceResolutionError(f"assertion {key}: unsupported assertion content")
        return self.values[key]

    def assertion_history(self, identity):
        """Union exact stored/proposed history under the same occurrence and scalar work charges.

        The event-index range excludes later rows before examination. Removed
        targets remain discoverable; prospective event widths are reserved
        conservatively so immediate persistence cannot make a baseline more costly.
        """
        if identity in self.histories:
            return self.histories[identity]
        keys = []
        temporal = " AND event_id<?" if self.cutoff is not None else ""
        args = (identity, self.cutoff) if self.cutoff is not None else (identity,)
        for row in self.rows("""SELECT revision,event_id FROM claim_use_revision_events
                INDEXED BY claim_use_revision_event WHERE record_id=?""" + temporal +
                " ORDER BY event_id,revision", args, "assertion_revisions"):
            key = identity, row[0]
            self.assertions.add(key)
            keys.append(key)
        for key in self.proposed:
            if key[0] == identity and key not in keys:
                # A proposed history row will become an indexed revision/event
                # pair. Reserve its scalar scan work at the future event's full width.
                self.charge("assertion_revisions")
                self.charge("metadata_bytes", 8 * (len(str(key[1])) + len(str(_MAX_INTEGER))))
                self.assertions.add(key)
                keys.append(key)
        self.histories[identity] = keys
        return keys

    def registered(self, key):
        """Check explicit registration membership; generic promotion documents confer no support."""
        if self.overlay is not None and key in self.overlay.bindings:
            return True
        row = self.connection.execute("""SELECT registration_event FROM claim_use_bindings
            WHERE use_id=? AND binding_revision=?""", key).fetchone()
        return row is not None and (self.cutoff is None or row[0] < self.cutoff)

    def current(self, identity):
        """Return the latest transition visible before this operation's event."""
        if self.overlay is not None and identity in self.overlay.transitions:
            revision, generation, _ = self.overlay.transitions[identity]
            return revision, generation, _MAX_INTEGER
        if self.cutoff is None:
            return self.connection.execute("""SELECT binding_revision,generation,last_event
                FROM claim_use_current WHERE use_id=?""", (identity,)).fetchone()
        return self.connection.execute("""SELECT binding_revision,generation,event_id
            FROM claim_use_generations INDEXED BY claim_use_generation_use_event
            WHERE use_id=? AND event_id<? ORDER BY event_id DESC LIMIT 1""", (identity, self.cutoff)).fetchone()

    def verify_artifacts(self, envelopes):
        """Verify only required typed direct bytes on new registration under independent limits."""
        for envelope in envelopes:
            for artifact in envelope.artifact_references:
                self.charge("references")
                if artifact.digest in self.artifacts:
                    continue
                self.charge("artifacts")
                self.charge("artifact_bytes", artifact.size)
                self.artifacts[artifact.digest] = artifact.size
        for digest, size in self.artifacts.items():
            from research_pipeline.domain import ArtifactReference
            self.store._artifacts.verify(ArtifactReference(digest, size))


@dataclass
class Plan:
    """Private deterministic write plan applied through the owner's single audit event.

    submission_id supplies prospective transition attribution before a receipt is
    allocated; bindings, projections and coalesced transitions form the read overlay.
    """

    reader: Reader
    submission_id: str
    bindings: dict = field(default_factory=dict)
    dependencies: dict = field(default_factory=dict)
    upstreams: dict = field(default_factory=dict)
    transitions: dict = field(default_factory=dict)


def dependencies(reader, key, value):
    """Derive immutable ordered exact anchors, retaining roles, context and occurrences.

    Shallow roles stay shallow. Only target_context produces the context watch;
    other scope roles stay immutable descriptive pins. Context-scoped Review anchors
    cannot invalidate an unrelated context merely because a claim identity is shared.
    """
    result, upstreams = [], []
    scope = pin(value.target_context)[:2]

    def add(reference, role, context=("", 0), route=-1, premise=-1):
        """Record each semantic occurrence; no target deduplication hides work."""
        reader.charge("references")
        reader.charge("index_rows")
        result.append((len(result), *pin(reference), role, *context, route, premise))

    candidate = reader.typed(value.candidate_claim, Claim)
    if reader.context_active:
        reader.context(pin(value.target_context)[:2])
    else:
        reader.typed(value.target_context, ResearchContext)
    add(value.candidate_claim, "candidate", scope)
    add(value.target_context, "context")
    for i, route in enumerate(value.routes):
        justification = reader.typed(route.justification, Justification)
        if pin(value.candidate_claim) not in [pin(r) for r in justification.conclusions]:
            from research_pipeline.store import ReferenceResolutionError
            raise ReferenceResolutionError("support_route: does not conclude the exact candidate")
        if [pin(p.claim) for p in route.premises] != [pin(p) for p in justification.premises]:
            from research_pipeline.store import ReferenceResolutionError
            raise ReferenceResolutionError("support_route: complete ordered premise conjunction must match")
        add(route.justification, "route", scope, i)
        add(justification.context, "route_context", route=i)
        for j, premise in enumerate(route.premises):
            claim = reader.typed(premise.claim, Claim)
            add(premise.claim, "premise", scope, i, j)
            add(claim.context, "premise_context", route=i, premise=j)
            if pin(claim.context)[:2] != scope:
                add(premise.claim, "premise_origin", pin(claim.context)[:2], i, j)
            if premise.upstream_use is not None:
                add(premise.upstream_use, "upstream", route=i, premise=j)
                reader.charge("index_rows")
                upstreams.append((i, j, premise.upstream_use.record_id, premise.upstream_use.revision))
        for evidence_ref in justification.evidence:
            evidence = reader.typed(evidence_ref, Evidence)
            add(evidence_ref, "evidence", route=i)
            for reference in (evidence.context, *evidence.target_claims, *evidence.input_records):
                add(reference, "evidence_declared", route=i)
        for assessment in route.assessments:
            review = reader.typed(assessment, Review)
            if (pin(review.candidate_claim) != pin(value.candidate_claim)
                    or pin(review.target_context) != pin(value.target_context)
                    or pin(route.justification) not in [pin(r.justification) for r in review.route_assessments]
                    or pin(review.authorization_policy) not in [pin(p) for p in value.policies]):
                from research_pipeline.store import ReferenceResolutionError
                raise ReferenceResolutionError("support_assessment: exact candidate/context/route/policy pairing required")
            add(assessment, "assessment_watch", route=i)
            for reference in reader.store._typed_references(review)[0] + reader.store._typed_references(review)[1]:
                if reference.relationship in ("candidate_claim", "assessed_route"):
                    add(reference, "assessment_anchor", scope, i)
                else:
                    add(reference, "assessment_declared", route=i)
    for reference in value.issues:
        issue = reader.typed(reference, Issue)
        add(reference, "issue_watch")
        for affected in (*issue.affected_records, *issue.supporting_evidence):
            add(affected, "issue_declared")
    for reference in value.policies:
        if reader.policy_active:
            reader.policy(pin(reference)[:2])
        else:
            reader.shallow(reference)
        add(reference, "policy_declared")
    return result, upstreams


def support_graph(plan):
    """Iteratively validate explicit upstream support, separate visited and active paths.

    Every root has its own ancestry candidates: even an acyclic use graph must not
    discharge a candidate with a premise returning to that exact candidate.
    """
    from research_pipeline.store import ReferenceResolutionError
    reader = plan.reader
    cache = dict(plan.bindings)
    visited = set()
    for root in sorted(plan.bindings):
        active = set()
        stack = [(root, False, (), 1)]
        while stack:
            key, leaving, candidates, depth = stack.pop()
            if leaving:
                active.remove(key)
                continue
            _check_count(depth, reader.caps["support_depth"], "support_depth")
            if key in active:
                raise ReferenceResolutionError("explicit upstream-use support cycle")
            if key not in visited:
                reader.binding(key)
                visited.add(key)
            if key not in cache:
                if not reader.registered(key):
                    raise ReferenceResolutionError(f"premise_use {key}: not a registered ClaimUse binding")
                cache[key] = reader.typed(RecordReference(*key, "premise_use", "promotion_eligibility"), ClaimUse)
            value = cache[key]
            candidate = pin(value.candidate_claim)
            ancestors = (*candidates, candidate)
            active.add(key)
            stack.append((key, True, (), depth))
            for route in reversed(value.routes):
                for premise in reversed(route.premises):
                    reader.charge("references")
                    if pin(premise.claim) in ancestors:
                        raise ReferenceResolutionError("undischarged premise returns to its exact support candidate")
                    if premise.upstream_use is not None:
                        upstream = premise.upstream_use.record_id, premise.upstream_use.revision
                        if upstream not in cache:
                            if upstream not in plan.bindings and not reader.registered(upstream):
                                raise ReferenceResolutionError(f"premise_use {upstream}: unregistered generic support")
                            cache[upstream] = reader.typed(premise.upstream_use, ClaimUse)
                        if pin(cache[upstream].candidate_claim) != pin(premise.claim):
                            raise ReferenceResolutionError("premise_use: upstream candidate differs from exact premise")
                        stack.append((upstream, False, ancestors, depth + 1))
    return cache


def impact(reader, keys):
    """Expand exact assertion association links only; descriptive graph links are not support.

    An Issue association cycle terminates with a visited set. Review anchors carry
    exact target context; all other issue targets are shallow exact anchors.
    """
    anchors = set()
    visited = set()
    todo = list(keys)
    while todo:
        key = todo.pop()
        if key in visited:
            continue
        visited.add(key)
        value = reader.assertion(key)
        anchors.add((*key, "review" if type(value) is Review else "issue", "", 0))
        if type(value) is Review:
            scope = pin(value.target_context)[:2]
            anchors.add((*pin(value.candidate_claim), *scope))
            for route in value.route_assessments:
                reader.charge("references")
                anchors.add((*pin(route.justification), *scope))
        else:
            for reference in value.affected_records:
                reader.charge("references")
                if reference.target_kind in ("review", "issue"):
                    todo.append((reference.record_id, reference.revision))
                else:
                    reader.shallow(reference)
                    anchors.add((*pin(reference), "", 0))
        _check_count(len(anchors), reader.caps["references"], "references")
    return anchors, visited


def matches(dependency, anchor):
    """Match exact targets and optional context, preserving shallow issue impact anchors."""
    return dependency[1:4] == anchor[:3] and (anchor[3:] == ("", 0) or dependency[5:7] == anchor[3:])


def observed(reader, deps, *, binding_keys):
    """Discover complete current assertion associations through bounded reverse-link indexes.

    Historical links seed identity watches; a successor changing scope is exposed,
    with attribution, without replacing any bound historical pin. Proposed matching
    links reserve the same reverse-index scalar work as their persisted counterparts.
    binding_keys contains exact registered roots/upstreams already visited by the
    caller; each is both a queue seed and an Issue relevance anchor. Independent
    reader ceilings reject incomplete discovery rather than truncating the view.
    """
    found, expanded = set(), set()
    bound_routes = set()
    candidate = None
    for dependency in deps:
        if dependency[4] == "candidate":
            candidate = dependency[1:4]
        elif dependency[4] == "route" and candidate is not None:
            bound_routes.add((candidate, dependency[1:4], dependency[5:7]))
    binding_anchors = {(*key, "promotion_eligibility") for key in binding_keys}
    queue = deque((d[1], d[2]) for d in deps)
    queue.extend(sorted(a[:2] for a in binding_anchors))
    visited = set()
    while queue:
        target = queue.popleft()
        if target in visited:
            continue
        visited.add(target)
        temporal = " AND l.event_id<?" if reader.cutoff is not None else ""
        args = (*target, reader.cutoff) if reader.cutoff is not None else target
        for identity, revision, kind, event in reader.rows("""SELECT l.record_id,l.revision,i.kind,l.event_id
                FROM claim_use_association_links l INDEXED BY claim_use_association_target
                CROSS JOIN identities i ON i.record_id=l.record_id
                WHERE l.target_id=? AND l.target_revision=?""" + temporal +
                " ORDER BY l.event_id,l.relationship,l.record_id,l.revision,l.ordinal", args):
            if kind in ("review", "issue"):
                found.add(identity)
        # Proposed links mirror every indexed occurrence, including records whose
        # kind will be rejected after the stored scalar preflight. Only attributed
        # assertion kinds enter association expansion.
        for key, envelope in reader.proposed.items():
            for ref in envelope.record_references:
                reader.charge("references")
                if (ref.record_id, ref.revision) == target and ref.relationship in (
                        "candidate_claim", "assessed_route", "affected_record"):
                    reader.charge("index_rows")
                    reader.charge("metadata_bytes", 8 * (len(key[0]) + len(str(key[1]))
                                  + len(envelope.kind) + len(str(_MAX_INTEGER))))
                    if envelope.kind in ("review", "issue"):
                        found.add(key[0])
        for identity in sorted(found - expanded):
            expanded.add(identity)
            for key in reader.assertion_history(identity):
                if key not in visited:
                    queue.append(key)
    relevant = []
    for identity in sorted(found | {d[1] for d in deps if d[4] in ("assessment_watch", "issue_watch")}):
        keys = reader.assertion_history(identity)
        anchors, _ = impact(reader, keys)
        watch = any(d[1] == identity and d[4] in ("assessment_watch", "issue_watch") for d in deps)
        if (watch or any(matches(d, a) for d in deps for a in anchors)
                or any(a[:3] in binding_anchors for a in anchors)):
            head = reader.head(identity)
            if head is not None:
                value = reader.assertion((identity, head))
                relevant.append(dict(pin=keypin((identity, head), "review" if type(value) is Review else "issue"),
                                     content=value.to_dict(), attributed=True,
                                     still_assesses_bound_route=(None if type(value) is Issue else any(
                                         candidate == pin(value.candidate_claim)
                                         and scope == pin(value.target_context)[:2]
                                         and any(pin(r.justification) == route for r in value.route_assessments)
                                         for candidate, route, scope in bound_routes))))
    return relevant


def prepare(store, connection, submission, *, decoded=(), cutoff=None, verify=True, policy=None, context=None):
    """Prepare registrations, affected transitions and complete baseline views before insertion.

    Same-batch forward edges resolve through proposed values. Rebinding an upstream
    never repoints downstream pins; propagation follows historical binding nodes.
    Exact registered bindings are Issue anchors independently of dependency rows;
    indexed membership and prospective rows consume bounded work before propagation.
    Unsupported schemas reject fresh root discriminators only here, after the
    owner's original-request reconciliation. No helper starts a transaction.
    Independent private policy/context selections preserve pre-activation preparation,
    output and accounting during chronological verification, never a public switch.
    """
    from research_pipeline.store import ReferenceResolutionError
    policy_active = store._schema_version in (5, 6) if policy is None else policy
    context_active = store._schema_version == 6 if context is None else context
    if not relevant_request(submission, policy=policy_active, context=context_active):
        return None
    if store._schema_version not in (4, 5, 6):
        if any(r.content.get("format") == FORMAT for r in submission.records):
            require_schema(store)
        return None
    if not any(r.kind in ("review", "issue") or (policy_active and r.kind == "decision") or (context_active and r.kind == "research_context") or r.content.get("format") == FORMAT
               or (r.kind == "promotion_eligibility" and connection.execute(
                   "SELECT 1 FROM claim_use_current WHERE use_id=?", (r.record_id,)).fetchone() is not None)
               for r in submission.records):
        return None
    reader = Reader(store, connection, submission.records, cutoff=cutoff, policy=policy_active, context=context_active)
    plan = Plan(reader, submission_id=submission.submission_id)
    assertions = []
    for record in submission.records:
        key = record.record_id, record.revision
        current = reader.current(record.record_id) if record.kind == "promotion_eligibility" else None
        recognized = record.content.get("format") == FORMAT
        if current is not None and not recognized:
            raise ReferenceResolutionError("registered ClaimUse identity cannot be replaced by opaque or other content")
        if recognized:
            value = decode_envelope(record)
            if (current is None and record.revision != 1) or (current is not None and record.revision != current[0] + 1):
                raise ReferenceResolutionError("ClaimUse first registration needs a new identity at revision 1; append only to registered identities")
            if current is None and reader.head(record.record_id) != record.revision:
                raise ReferenceResolutionError("generic identity cannot become a registered ClaimUse")
            plan.bindings[key] = value
        if record.kind in ("review", "issue"):
            reader.assertion(key)  # generic writes require coherent local assertions too
            assertions.append(key)
    if plan.bindings:
        subset = Submission(submission.submission_id, submission.provenance,
                            [reader.proposed[k] for k in plan.bindings],
                            {k[0]: submission.expected_heads[k[0]] for k in plan.bindings})
        vals = tuple(plan.bindings.values())
        envelopes, values = store._check_typed_targets(connection, subset, vals, authority_reader=reader)
        reader.values.update(values)
        for key, value in sorted(plan.bindings.items()):
            plan.dependencies[key], plan.upstreams[key] = dependencies(reader, key, value)
        support_graph(plan)
        if verify:
            reader.verify_artifacts((*submission.records, *envelopes.values()))
    # New generic assertions keep shallow scientific admission. Typed requests use
    # this reader additionally at their owner's ordinary target-admission seam.
    affected = {}
    for changed in assertions:
        anchors, _ = impact(reader, reader.assertion_history(changed[0]))
        candidates = {}
        # Event ranges precede the complete index suffix: later history must be
        # excluded by the seek, before either pass examines or charges candidates.
        temporal = " AND d.registration_event<?" if cutoff is not None else ""
        for anchor in sorted(anchors):
            if anchor[2] == "promotion_eligibility":
                key = anchor[:2]
                membership_temporal = " AND registration_event<?" if cutoff is not None else ""
                direct = [row[:2] for row in reader.rows("""SELECT use_id,binding_revision,registration_event
                    FROM claim_use_bindings WHERE use_id=? AND binding_revision=?""" + membership_temporal,
                    (*key, cutoff) if cutoff is not None else key)]
                if key in plan.bindings:
                    reader.charge("index_rows")
                    reader.charge("metadata_bytes", 8 * (len(key[0]) + len(str(key[1]))
                                                         + len(str(_MAX_INTEGER))))
                    direct.append(key)
                for binding_key in direct:
                    # Membership, not the generic record kind, establishes an
                    # affected use. Charge every occurrence before cause deduplication.
                    reader.charge("causes")
                    cause = dict(type="binding_affected", assertion=keypin(changed, reader.proposed[changed].kind),
                                 binding=keypin(binding_key))
                    text = _cause_key(reader, cause) if policy_active else _canonical(cause)
                    affected.setdefault(binding_key, {})[text] = cause
            for row in reader.rows("""SELECT d.use_id,d.binding_revision,d.ordinal,d.target_id,d.target_revision,
                    d.target_kind,d.role,d.context_id,d.context_revision,d.route_ordinal,d.premise_ordinal,d.registration_event
                    FROM claim_use_dependencies d INDEXED BY claim_use_dependency_target
                    WHERE d.target_id=? AND d.target_revision=? AND d.target_kind=?
                    """ + temporal + " ORDER BY d.registration_event,d.use_id,d.binding_revision,d.ordinal",
                                   (*anchor[:3], cutoff) if cutoff is not None else anchor[:3]):
                dep = row[2:-1]
                if matches(dep, anchor):
                    candidates.setdefault(row[:2], []).append(dep)
        for role in ("assessment_watch", "issue_watch"):
            for row in reader.rows("""SELECT d.use_id,d.binding_revision,d.ordinal,d.target_id,d.target_revision,
                    d.target_kind,d.role,d.context_id,d.context_revision,d.route_ordinal,d.premise_ordinal,d.registration_event
                    FROM claim_use_dependencies d INDEXED BY claim_use_dependency_watch
                    WHERE d.target_id=? AND d.target_kind=? AND d.role=?
                    """ + temporal + " ORDER BY d.registration_event,d.use_id,d.binding_revision,d.ordinal",
                                   (changed[0], reader.proposed[changed].kind, role, cutoff) if cutoff is not None
                                   else (changed[0], reader.proposed[changed].kind, role)):
                candidates.setdefault(row[:2], []).append(row[2:-1])
        for key, deps in plan.dependencies.items():
            matched = [d for d in deps if any(matches(d, a) for a in anchors)
                       or (d[1] == changed[0] and d[4] in ("assessment_watch", "issue_watch"))]
            if matched:
                candidates.setdefault(key, []).extend(matched)
        for key, deps in candidates.items():
            for dep in sorted(deps if policy_active else set(deps)):
                reader.charge("causes")
                cause = dict(type="assertion_changed", assertion=keypin(changed, reader.proposed[changed].kind),
                             dependency=dict(ordinal=dep[0], target=keypin(dep[1:3], dep[3]), role=dep[4],
                                             context=None if not dep[5] else keypin(dep[5:7], "research_context"),
                                             route_ordinal=dep[7], premise_ordinal=dep[8]))
                if policy_active:
                    cause["binding"] = keypin(key)
                text = _cause_key(reader, cause) if policy_active else _canonical(cause)
                affected.setdefault(key, {})[text] = cause
    if policy_active:
        _policy_impact(plan, affected)
        if context_active:
            _context_impact(plan, affected)
        _propagate_origins(plan, affected)
    else:
        queue = deque(sorted(affected))
        visited = set()
        while queue:
            key = queue.popleft()
            if key in visited:
                continue
            visited.add(key)
            reader.binding(key)
            edges = []
            temporal = " AND u.registration_event<?" if cutoff is not None else ""
            for identity, revision, event in reader.rows("""SELECT u.use_id,u.binding_revision,u.registration_event
                    FROM claim_use_upstreams u INDEXED BY claim_use_upstream_target
                    WHERE u.upstream_id=? AND u.upstream_revision=?""" + temporal +
                    " ORDER BY u.registration_event,u.use_id,u.binding_revision,u.route_ordinal,u.premise_ordinal",
                    (*key, cutoff) if cutoff is not None else key):
                edges.append((identity, revision))
            edges.extend(k for k, rows in plan.upstreams.items() for r in rows if r[2:] == key)
            for downstream in edges:
                reader.charge("causes")
                cause = dict(type="upstream_affected", upstream_binding=keypin(key))
                affected.setdefault(downstream, {})[_canonical(cause)] = cause
                queue.append(downstream)
    for key in sorted(set(affected) | set(plan.bindings)):
        old = reader.current(key[0])
        new_key = next((k for k in plan.bindings if k[0] == key[0]), None)
        if (new_key is not None and key != new_key) or (new_key is None and (old is None or old[0] != key[1])):
            continue  # traverse old snapshots, update only the final current binding
        causes = dict(affected.get(key, {}))
        if key in plan.bindings:
            reader.charge("causes")
            cause = dict(type="binding_registered", binding=keypin(key))
            text = _cause_key(reader, cause) if policy_active else _canonical(cause)
            causes[text] = cause
        generation = 1 if old is None else old[1] + 1
        if generation > _MAX_INTEGER:
            raise ClaimUseLimitError("generation: signed-64-bit overflow")
        reader.charge("transitions")
        plan.transitions[key[0]] = (key[1], generation, [causes[k] for k in sorted(causes)])
    bounded({identity: list(values) for identity, values in plan.transitions.items()},
            reader.caps["metadata_bytes"] - reader.counts["metadata_bytes"], "metadata_bytes")
    # A fresh reader per root prevents admission caches from discounting its
    # eventual standalone inspection. All repeated work remains write-accounted.
    limits = ClaimUseInspectionLimits(512, 1024, 8192, 1024, 64*1024*1024, 4*1024*1024)
    roots = sorted(plan.transitions) if policy_active else [key[0] for key in sorted(plan.bindings)]
    for identity in roots:
        baseline = Reader(store, connection, submission.records, limits, cutoff,
                          overlay=plan, aggregate=reader, policy=policy_active, context=context_active)
        _inspection(baseline, identity, limits)
    return plan


def _policy_impact(plan, affected):
    """Seed exact policy-change causes through temporal identity watches, never history scans.

    Only successor Decisions matching explicit policy_declared occurrences matter.
    A preceding head is resolved without the new-head overlay; the bound pin may
    independently be older or the same-batch successor. Every occurrence is charged
    before canonical cause deduplication, including prospective watch occurrences.
    """
    reader = plan.reader
    from research_pipeline.store import ReferenceResolutionError
    visible_maximum = reader.connection.execute("SELECT coalesce(max(event_id),0) FROM audit_events").fetchone()[0]
    for changed, envelope in reader.proposed.items():
        if envelope.kind != "decision" or changed[1] == 1:
            continue
        temporal = " AND d.registration_event<?" if reader.cutoff is not None else " AND d.registration_event<=?"
        boundary = reader.cutoff if reader.cutoff is not None else visible_maximum
        args = (changed[0], "decision", "policy_declared", boundary)
        candidates = reader.rows("""SELECT d.use_id,d.binding_revision,d.ordinal,d.target_revision,d.registration_event
            FROM claim_use_dependencies d INDEXED BY claim_use_dependency_watch
            WHERE d.target_id=? AND d.target_kind=? AND d.role=?""" + temporal +
            " ORDER BY d.registration_event,d.use_id,d.binding_revision,d.ordinal", args)
        previous = None
        def add(key, ordinal, revision):
            """Resolve the three exact policy pins and retain one charged direct occurrence."""
            nonlocal previous
            reader.binding(key)
            reader.charge("references")
            reader.charge("causes")
            if previous is None:
                previous = reader.head(changed[0], proposed=False)
                if previous != changed[1] - 1:
                    raise ReferenceResolutionError("policy successor lacks its visible preceding head")
            bound = changed[0], revision
            reader.policy(bound)
            reader.policy((changed[0], previous))
            reader.policy(changed)
            cause = dict(type="policy_changed", binding=keypin(key), dependency_ordinal=ordinal,
                         bound_policy=keypin(bound, "decision"),
                         previous_policy=keypin((changed[0], previous), "decision"),
                         new_policy=keypin(changed, "decision"))
            affected.setdefault(key, {})[_cause_key(reader, cause)] = cause
        for identity, revision, ordinal, bound_revision, event in candidates:
            add((identity, revision), ordinal, bound_revision)
        for key, deps in plan.dependencies.items():
            for dep in deps:
                reader.charge("references")
                if dep[1] == changed[0] and dep[3:5] == ("decision", "policy_declared"):
                    reader.charge("index_rows")
                    reader.charge("metadata_bytes", 8 * (len(key[0]) + sum(len(str(n)) for n in
                                  (key[1], dep[0], dep[2], _MAX_INTEGER))))
                    add(key, dep[0], dep[2])


def _context_impact(plan, affected):
    """Seed exact target-context-change causes through temporal identity watches, never history scans.

    Only successor ResearchContexts matching explicit context occurrences matter.
    A preceding head is resolved without the new-head overlay; the bound pin may
    independently be older or the same-batch successor. Every occurrence is charged
    before canonical cause deduplication, including prospective watch occurrences.
    """
    reader = plan.reader
    from research_pipeline.store import ReferenceResolutionError
    visible_maximum = reader.connection.execute("SELECT coalesce(max(event_id),0) FROM audit_events").fetchone()[0]
    for changed, envelope in reader.proposed.items():
        if envelope.kind != "research_context" or changed[1] == 1:
            continue
        temporal = " AND d.registration_event<?" if reader.cutoff is not None else " AND d.registration_event<=?"
        boundary = reader.cutoff if reader.cutoff is not None else visible_maximum
        args = (changed[0], "research_context", "context", boundary)
        candidates = reader.rows("""SELECT d.use_id,d.binding_revision,d.ordinal,d.target_revision,d.registration_event
            FROM claim_use_dependencies d INDEXED BY claim_use_dependency_watch
            WHERE d.target_id=? AND d.target_kind=? AND d.role=?""" + temporal +
            " ORDER BY d.registration_event,d.use_id,d.binding_revision,d.ordinal", args)
        previous = None
        def add(key, ordinal, revision):
            """Resolve the three exact context pins and retain one charged direct occurrence."""
            nonlocal previous
            reader.binding(key)
            reader.charge("references")
            reader.charge("causes")
            if previous is None:
                previous = reader.head(changed[0], proposed=False)
                if type(previous) is not int or previous != changed[1] - 1:
                    raise ReferenceResolutionError("context successor lacks its visible preceding head")
            bound = changed[0], revision
            reader.context(bound)
            reader.context((changed[0], previous))
            reader.context(changed)
            cause = dict(type="target_context_changed", binding=keypin(key), dependency_ordinal=ordinal,
                         bound_context=keypin(bound, "research_context"),
                         previous_context=keypin((changed[0], previous), "research_context"),
                         new_context=keypin(changed, "research_context"))
            affected.setdefault(key, {})[_cause_key(reader, cause)] = cause
        for identity, revision, ordinal, bound_revision, event in candidates:
            add((identity, revision), ordinal, bound_revision)
        for key, deps in plan.dependencies.items():
            for dep in deps:
                reader.charge("references")
                if dep[1] == changed[0] and dep[3:5] == ("research_context", "context"):
                    reader.charge("index_rows")
                    reader.charge("metadata_bytes", 8 * (len(key[0]) + sum(len(str(n)) for n in
                                  (key[1], dep[0], dep[2], _MAX_INTEGER))))
                    add(key, dep[0], dep[2])


def _propagate_origins(plan, affected):
    """Propagate bounded origin-cause deltas through cached exact historical upstream edges.

    A node can receive another origin after its first expansion (for example in a
    diamond). Each newly retained origin must therefore travel onward; a boolean
    visited set would lose causes. Immediate edge reasons are retained but never
    replace or multiply complete paths. Registration alone is not an invalidation.
    """
    reader = plan.reader
    queue = deque((key, tuple(causes.items())) for key, causes in sorted(affected.items()))
    edges = {}
    while queue:
        key, delta = queue.popleft()
        reader.binding(key)
        if key not in edges:
            temporal = " AND u.registration_event<?" if reader.cutoff is not None else ""
            args = (*key, reader.cutoff) if reader.cutoff is not None else key
            outgoing = [row[:2] for row in reader.rows("""SELECT u.use_id,u.binding_revision,u.registration_event
                FROM claim_use_upstreams u INDEXED BY claim_use_upstream_target
                WHERE u.upstream_id=? AND u.upstream_revision=?""" + temporal +
                " ORDER BY u.registration_event,u.use_id,u.binding_revision,u.route_ordinal,u.premise_ordinal", args)]
            for downstream, rows in plan.upstreams.items():
                for row in rows:
                    reader.charge("references")
                    if row[2:] == key:
                        reader.charge("index_rows")
                        reader.charge("metadata_bytes", 8 * (len(downstream[0]) + sum(len(str(n)) for n in
                                      (downstream[1], row[0], row[1], _MAX_INTEGER))))
                        outgoing.append(downstream)
            edges[key] = outgoing
        for downstream in edges[key]:
            reader.charge("references")
            destination = affected.setdefault(downstream, {})
            reason = dict(type="upstream_affected", upstream_binding=keypin(key))
            reader.charge("causes")
            destination[_cause_key(reader, reason)] = reason
            added = []
            for text, cause in delta:
                reader.charge("causes")
                reader.charge("metadata_bytes", 6 * len(text))
                if text not in destination:
                    destination[text] = cause
                    added.append((text, cause))
            if added:
                queue.append((downstream, tuple(added)))


def index_submission(connection, submission, receipt):
    """Index every schema-4/5/6 submission's original revisions and selected link occurrences.

    The caller supplies the actual receipt inside its owning transaction, after
    all revisions and links exist. This metadata-only helper never commits; any
    failure rolls back with the submission, including non-freshness writers.
    """
    for record in submission.records:
        key = record.record_id, record.revision
        connection.execute("INSERT INTO claim_use_revision_events VALUES (?,?,?)", (*key, receipt.event_id))
        connection.execute("""INSERT INTO claim_use_association_links
            SELECT record_id,revision,ordinal,?,relationship,target_id,target_revision
            FROM record_links WHERE record_id=? AND revision=?
            AND relationship IN ('candidate_claim','assessed_route','affected_record')""", (receipt.event_id, *key))


def apply(connection, plan, receipt):
    """Apply a complete checked plan after the owner's revisions and sole event exist.

    Failure escapes to the owning transaction, rolling back records and freshness
    together. Dependency/upstream temporal keys use the actual owning receipt's
    event. No successful receipt can precede these updates.
    """
    if plan is None:
        return
    for key in sorted(plan.bindings):
        connection.execute("INSERT INTO claim_use_bindings VALUES (?,?,?)", (*key, receipt.event_id))
        for row in plan.dependencies[key]:
            connection.execute("INSERT INTO claim_use_dependencies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (*key, *row, receipt.event_id))
        for row in plan.upstreams[key]:
            connection.execute("INSERT INTO claim_use_upstreams VALUES (?,?,?,?,?,?,?)", (*key, *row, receipt.event_id))
    for identity, (revision, generation, causes) in sorted(plan.transitions.items()):
        connection.execute("INSERT INTO claim_use_generations VALUES (?,?,?,?,?,?,?)",
                           (identity, generation, revision, receipt.submission_id, receipt.event_id,
                            "requires_reassessment", _canonical(causes)))
        connection.execute("""INSERT INTO claim_use_current VALUES (?,?,?,'requires_reassessment',?)
            ON CONFLICT(use_id) DO UPDATE SET binding_revision=excluded.binding_revision,
            generation=excluded.generation,status=excluded.status,last_event=excluded.last_event""",
                           (identity, revision, generation, receipt.event_id))


def _limits(limits):
    """Reconstruct exact required public read limits before acquiring a snapshot."""
    if type(limits) is not ClaimUseInspectionLimits:
        raise DomainValidationError("limits: expected exact ClaimUseInspectionLimits")
    return ClaimUseInspectionLimits(**{name: getattr(limits, name)
                                      for name in ClaimUseInspectionLimits.__dataclass_fields__})


def _dependencies(reader, key):
    """Read one immutable binding's ordered dependency rows under index and byte limits."""
    if reader.overlay is not None and key in reader.overlay.dependencies:
        rows = reader.overlay.dependencies[key]
        for row in rows:
            reader.charge("index_rows")
            reader.charge("metadata_bytes", 8 * sum(len(str(item)) for item in row))
        return rows
    rows = []
    for row in reader.rows("""SELECT ordinal,target_id,target_revision,target_kind,role,
            context_id,context_revision,route_ordinal,premise_ordinal FROM claim_use_dependencies
            WHERE use_id=? AND binding_revision=? ORDER BY ordinal""", key):
        if row[0] != len(rows):
            raise ClaimUseIntegrityError("noncontiguous binding dependency ordinals")
        rows.append(row)
    return rows


def _transition(reader, identity, generation):
    """Preflight and reconstruct a canonical structured immutable transition."""
    if reader.overlay is not None and identity in reader.overlay.transitions:
        revision, planned_generation, causes = reader.overlay.transitions[identity]
        if generation != planned_generation:
            raise ClaimUseIntegrityError("prospective generation mismatch")
        reader.charge("metadata_bytes", 6 * len(_canonical(causes)))
        # The event is not allocated until insertion. Reserve its maximum signed
        # width only in this private view; never persist a fabricated receipt.
        return dict(use_id=identity, generation=generation, binding_revision=revision,
                    submission_id=reader.overlay.submission_id, event_id=_MAX_INTEGER,
                    status="requires_reassessment", causes=causes)
    row = reader.connection.execute("""SELECT typeof(causes_json),length(CAST(causes_json AS BLOB))
        FROM claim_use_generations WHERE use_id=? AND generation=?""", (identity, generation)).fetchone()
    if row is None or row[0] != "text":
        raise ClaimUseIntegrityError("missing or malformed generation transition")
    reader.charge("metadata_bytes", 6 * row[1])
    row = reader.connection.execute("""SELECT binding_revision,submission_id,event_id,status,causes_json
        FROM claim_use_generations WHERE use_id=? AND generation=?""", (identity, generation)).fetchone()
    causes = _strict_json(row[4])
    if type(causes) is not list or _canonical(causes) != row[4]:
        raise ClaimUseIntegrityError("noncanonical structured transition causes")
    return dict(use_id=identity, generation=generation, binding_revision=row[0],
                submission_id=row[1], event_id=row[2], status=row[3], causes=causes)


def inspect(store, use_id, *, limits):
    """Return one coherent metadata-only current binding and attributed assertion observation.

    Attachment availability is intentionally not checked. Historical assessment,
    issue and upstream pins remain exact when their identities acquire new heads.
    """
    require_schema(store)
    _identifier(use_id, "use_id")
    limits = _limits(limits)
    with store._transaction() as connection:
        reader = Reader(store, connection, limits=limits)
        return _inspection(reader, use_id, limits)


def _upstreams(reader, key):
    """Read exact ordered upstream occurrences from the stored or prospective binding."""
    if reader.overlay is not None and key in reader.overlay.upstreams:
        rows = reader.overlay.upstreams[key]
        for row in rows:
            reader.charge("index_rows")
            reader.charge("metadata_bytes", 8 * sum(len(str(item)) for item in row))
        return rows
    return list(reader.rows("""SELECT route_ordinal,premise_ordinal,upstream_id,upstream_revision
        FROM claim_use_upstreams WHERE use_id=? AND binding_revision=? ORDER BY route_ordinal,premise_ordinal""", key))


def _inspection(reader, use_id, limits):
    """Prepare the complete bounded current view in the caller's connection and account.

    A private overlay supplies proposed exact bindings and the coalesced transition;
    historical upstream pins still resolve by exact revision, never current heads.
    Every visited binding is itself an exact Issue observation anchor, including
    roots with no routes and historical upstream bindings whose heads have changed.
    The same traversal, limitations, output and scratch charges govern public reads
    and pre-insertion baseline admission. Neither path owns a transaction here.
    Policy declarations use shallow exact reads without format-driven classification.
    Active target contexts use the scientific scope codec and retain complete bound
    and observed declarations; neither grants transfer or active-context authority.
    """
    from research_pipeline.store import RecordNotFoundError, _fault
    current = reader.current(use_id)
    if current is None:
        raise RecordNotFoundError(f"claim use {use_id}: missing or unregistered")
    root = use_id, current[0]
    todo, seen, bindings, deps = [root], set(), [], []
    policy_occurrences = []
    context_occurrences = []
    limitations = ["Positive scientific authorization is unavailable; eligible is always false.",
                    "Attribution, independence and execution are unverified.",
                    "Policy and provenance references are declarations, never verified authority."]
    while todo:
        key = todo.pop()
        if key in seen:
            continue
        seen.add(key)
        reader.binding(key)
        if not reader.registered(key):
            raise ClaimUseIntegrityError("upstream pin lacks explicit binding registration")
        envelope = reader.read(key)
        value = reader.typed(RecordReference(*key, "premise_use", "promotion_eligibility"), ClaimUse)
        own_deps = _dependencies(reader, key)
        derived, upstream_rows = dependencies(reader, key, value)
        if own_deps != derived:
            raise ClaimUseIntegrityError("current binding dependency projection mismatch")
        stored_upstreams = _upstreams(reader, key)
        if stored_upstreams != upstream_rows:
            raise ClaimUseIntegrityError("current binding upstream projection mismatch")
        deps.extend(own_deps)
        if reader.policy_active:
            for dep in own_deps:
                reader.charge("references")
                if dep[4] == "policy_declared":
                    policy_occurrences.append((key, dep[0], dep[1], dep[2]))
        if reader.context_active:
            for dep in own_deps:
                reader.charge("references")
                if dep[4] == "context":
                    context_occurrences.append((key, dep[0], dep[1], dep[2]))
        bindings.append(dict(binding=keypin(key), envelope=envelope.to_dict(), content=value.to_dict()))
        candidate = reader.typed(value.candidate_claim, Claim)
        if pin(candidate.context) != pin(value.target_context):
            limitations.append(f"Unresolved context transfer for candidate in {key[0]}@{key[1]}.")
        for route in value.routes:
            justification = reader.typed(route.justification, Justification)
            if pin(justification.context) != pin(value.target_context):
                limitations.append(f"Unresolved context transfer for route {route.justification.record_id}.")
            for premise in route.premises:
                claim = reader.typed(premise.claim, Claim)
                if pin(claim.context) != pin(value.target_context):
                    limitations.append(f"Unresolved context transfer for premise {premise.claim.record_id}.")
                if premise.upstream_use is None:
                    limitations.append(f"Premise support unrecorded for {premise.claim.record_id}@{premise.claim.revision}.")
                else:
                    upstream_key = premise.upstream_use.record_id, premise.upstream_use.revision
                    upstream = reader.typed(premise.upstream_use, ClaimUse)
                    if pin(upstream.target_context) != pin(value.target_context):
                        limitations.append(f"Unresolved context transfer from upstream {upstream_key[0]}@{upstream_key[1]}.")
                    todo.append(upstream_key)
        limitations.extend(value.limitations)
    _fault("claim_use_inspection_after_binding")
    observations = observed(reader, deps, binding_keys=seen)
    transition = _transition(reader, use_id, current[1])
    binding = next(b for b in bindings if b["binding"] == keypin(root))
    value = reader.values[root]
    result = dict(format="research_pipeline.claim_use_inspection", version=1, use_id=use_id,
                  binding_revision=current[0], generation=current[1], status="requires_reassessment",
                  requires_reassessment=True, eligible=False,
                  mechanical_freshness=dict(status="requires_reassessment", last_transition=transition,
                                            reasons=transition["causes"]),
                  authorized_disposition=dict(available=False, eligible=False),
                  binding=binding, candidate=value.candidate_claim.to_dict(), context=value.target_context.to_dict(),
                  routes=[r.to_dict() for r in value.routes],
                  historical_pins=dict(assessments=[r.to_dict() for route in value.routes for r in route.assessments],
                                       issues=[r.to_dict() for r in value.issues], policies=[r.to_dict() for r in value.policies]),
                  upstream_bindings=sorted((b for b in bindings if b is not binding),
                                           key=lambda b: (b["binding"]["record_id"], b["binding"]["revision"])),
                  observed_assertions=observations, limitations=sorted(set(limitations)),
                  attachment_availability="not_checked_metadata_only")
    if reader.policy_active:
        policies, reasons = [], {}
        for cause in transition["causes"]:
            reader.charge("causes")
            reasons[_cause_key(reader, cause)] = cause
        for key, ordinal, identity, revision in sorted(policy_occurrences):
            reader.charge("references")
            reader.policy((identity, revision))
            head = reader.head(identity)
            if type(head) is not int or head < revision:
                raise ClaimUseIntegrityError("visible policy head is absent or older than bound pin")
            content = reader.policy((identity, head))
            common = dict(binding=keypin(key), dependency_ordinal=ordinal,
                          bound_policy=keypin((identity, revision), "decision"),
                          observed_policy=keypin((identity, head), "decision"))
            # The checked canonical declaration is already retained. Reserve its
            # repeated output occurrence before attaching it, without encoding an
            # otherwise redundant scratch copy merely to measure its size.
            reader.charge("metadata_bytes", 6 * len(reader.read((identity, head), classify=False)._content_json))
            policies.append(dict(**common, observed_content=content, attributed=True, superseded=head > revision))
            if head > revision:
                reader.charge("causes")
                cause = dict(type="policy_pin_superseded", **common)
                reasons[_cause_key(reader, cause)] = cause
        result["version"] = 2
        result["observed_policies"] = policies
        registration = reader.connection.execute("SELECT event_watermark FROM claim_use_origin WHERE singleton=1").fetchone()
        if registration is None or type(registration[0]) is not int:
            raise ClaimUseIntegrityError("missing or malformed registration origin")
        maximum = reader.connection.execute("SELECT coalesce(max(event_id),0) FROM audit_events").fetchone()[0]
        watermark = _policy_origin(reader.connection, registration[0], maximum)
        result["policy_freshness"] = dict(available=True, activation_event_watermark=watermark)
        result["mechanical_freshness"]["reasons"] = [reasons[k] for k in sorted(reasons)]
    if reader.context_active:
        contexts, reasons = [], {}
        for cause in result["mechanical_freshness"]["reasons"]:
            reader.charge("causes")
            reasons[_cause_key(reader, cause)] = cause
        for key, ordinal, identity, revision in sorted(context_occurrences):
            # Occurrences remain work even when exact scope resolutions are cached.
            reader.charge("context_observations")
            bound = reader.context((identity, revision))
            head = reader.head(identity)
            if type(head) is not int or head < revision:
                raise ClaimUseIntegrityError("visible target context head is absent or older than bound pin")
            observed_context = reader.context((identity, head))
            common = dict(binding=keypin(key), dependency_ordinal=ordinal,
                          bound_context=keypin((identity, revision), "research_context"),
                          observed_context=keypin((identity, head), "research_context"))
            # Both complete scope representations consume work and result capacity,
            # including repeated content when bound and observed are the same pin.
            for context_key in ((identity, revision), (identity, head)):
                reader.charge("metadata_bytes", 6 * len(reader.read(context_key, classify=False)._content_json))
            contexts.append(dict(**common, bound_content=bound.to_dict(),
                                 observed_content=observed_context.to_dict(), attributed=True,
                                 superseded=head > revision))
            if head > revision:
                reader.charge("causes")
                cause = dict(type="target_context_pin_superseded", **common)
                reasons[_cause_key(reader, cause)] = cause
        result["version"] = 3
        result["observed_target_contexts"] = contexts
        registration = reader.connection.execute("SELECT event_watermark FROM claim_use_origin WHERE singleton=1").fetchone()
        maximum = reader.connection.execute("SELECT coalesce(max(event_id),0) FROM audit_events").fetchone()[0]
        policy_watermark = _policy_origin(reader.connection, registration[0], maximum)
        watermark = _context_origin(reader.connection, policy_watermark, maximum)
        result["target_context_freshness"] = dict(available=True, activation_event_watermark=watermark)
        result["mechanical_freshness"]["reasons"] = [reasons[k] for k in sorted(reasons)]
    remaining = (reader.caps["metadata_bytes"] - reader.counts["metadata_bytes"]) // 6
    if reader.aggregate is not None:
        remaining = min(remaining, (reader.aggregate.caps["metadata_bytes"]
                                   - reader.aggregate.counts["metadata_bytes"]) // 6)
    maximum = min(limits.max_result_bytes, remaining)
    text = bounded(result, maximum, "metadata_bytes" if maximum < limits.max_result_bytes else "result_bytes")
    reader.charge("metadata_bytes", 6 * len(text))
    return ClaimUseInspection(text)


def history(store, use_id, *, after_generation=0, limit=256, limits):
    """Return a complete bounded generation page with an explicit next cursor when needed."""
    from research_pipeline.store import RecordNotFoundError
    require_schema(store)
    _identifier(use_id, "use_id")
    _integer(after_generation, "after_generation", 0)
    _integer(limit, "limit", 1)
    if limit > 256:
        raise DomainValidationError("limit: must be at most 256")
    limits = _limits(limits)
    with store._transaction() as connection:
        reader = Reader(store, connection, limits=limits)
        if reader.current(use_id) is None:
            raise RecordNotFoundError(f"claim use {use_id}: missing or unregistered")
        generations = [r[0] for r in connection.execute("""SELECT generation FROM claim_use_generations
            WHERE use_id=? AND generation>? ORDER BY generation LIMIT ?""", (use_id, after_generation, limit+1))]
        result = [_transition(reader, use_id, g) for g in generations[:limit]]
        remaining = (reader.caps["metadata_bytes"] - reader.counts["metadata_bytes"]) // 6
        maximum = min(limits.max_result_bytes, remaining)
        text = bounded(dict(format="research_pipeline.claim_use_history", version=1, use_id=use_id,
                            transitions=result, next_cursor=(generations[limit-1] if len(generations) > limit else None)),
                       maximum, "metadata_bytes" if maximum < limits.max_result_bytes else "result_bytes")
        reader.charge("metadata_bytes", 6 * len(text))
        return ClaimUseHistoryPage(text)


def _validate_temporal_projections(connection):
    """Stream exact navigation/source correspondence independently of admission budgets.

    Lifetime metadata verification necessarily visits all history, without typed
    decoding or retaining a lifetime Python container. Navigation rows never become
    authority: original revisions, links and audit events determine expected rows.
    """
    from itertools import zip_longest
    comparisons = (
        ("SELECT record_id,revision,event_id FROM claim_use_revision_events ORDER BY record_id,revision",
         """SELECT r.record_id,r.revision,a.event_id FROM revisions r
            CROSS JOIN audit_events a USING(submission_id) ORDER BY r.record_id,r.revision"""),
        ("""SELECT record_id,revision,ordinal,event_id,relationship,target_id,target_revision
            FROM claim_use_association_links ORDER BY record_id,revision,ordinal""",
         """SELECT l.record_id,l.revision,l.ordinal,a.event_id,l.relationship,l.target_id,l.target_revision
            FROM record_links l CROSS JOIN revisions r USING(record_id,revision)
            CROSS JOIN audit_events a USING(submission_id)
            WHERE l.relationship IN ('candidate_claim','assessed_route','affected_record')
            ORDER BY l.record_id,l.revision,l.ordinal"""),
    )
    for actual, expected in comparisons:
        for stored, source in zip_longest(connection.execute(actual), connection.execute(expected)):
            if stored != source:
                raise ClaimUseIntegrityError("temporal navigation projection mismatch")
    for table in ("claim_use_dependencies", "claim_use_upstreams"):
        if connection.execute(f"""SELECT 1 FROM {table} d LEFT JOIN claim_use_bindings b
            USING(use_id,binding_revision) WHERE d.registration_event IS NOT b.registration_event LIMIT 1""").fetchone():
            raise ClaimUseIntegrityError("dependency/upstream registration event mismatch")


def _verify_transition(connection, identity, revision, generation, sid, event, causes):
    """Compare a stored transition to bounded canonical plan output without recharging admission.

    Preflight exact scalar types and UTF-8 lengths before fetching variable text.
    Equality to the expected canonical causes checks both content and canonical
    form, without parsing or charging the completed chronological plan again.
    """
    expected = (revision, sid, event, "requires_reassessment", _canonical(causes))
    columns = ("binding_revision", "submission_id", "event_id", "status", "causes_json")
    sizes = ",".join(f"typeof({name}),length(CAST({name} AS BLOB))" for name in columns)
    row = connection.execute("SELECT " + sizes + " FROM claim_use_generations WHERE use_id=? AND generation=?",
                             (identity, generation)).fetchone()
    expected_sizes = tuple(item for value in expected for item in
                           ("integer" if type(value) is int else "text", len(str(value).encode("utf-8"))))
    if row != expected_sizes:
        raise ClaimUseIntegrityError("generation scalar types or canonical cause length mismatch")
    row = connection.execute("SELECT " + ",".join(columns) +
                             " FROM claim_use_generations WHERE use_id=? AND generation=?",
                             (identity, generation)).fetchone()
    if row != expected:
        raise ClaimUseIntegrityError("generation identity, sequence or cause projection mismatch")


def validate(store, connection):
    """Check exact projections chronologically without admission, writes or live artifact reads.

    Per-event bounded plans detect missing as well as extra transitions. Total
    lifetime history is streamed and is not subject to a lifetime generation cap.
    Independent per-record/binding verification accounts never recharge a completed
    admission plan. Independent origins select preceding registration, policy and
    context interpretation without fabricating transitions at activation boundaries.
    """
    from research_pipeline.store import RecordNotFoundError, ReferenceResolutionError
    _validate_temporal_projections(connection)
    origin_rows = list(connection.execute("SELECT singleton,event_watermark FROM claim_use_origin LIMIT 2"))
    if len(origin_rows) != 1 or origin_rows[0][0] != 1 or type(origin_rows[0][1]) is not int or origin_rows[0][1] < 0:
        raise ClaimUseIntegrityError("invalid freshness origin")
    origin = origin_rows[0][1]
    migration = connection.execute("SELECT source_schema FROM migration_history WHERE target_schema=4").fetchone()
    if migration is None and origin != 0:
        raise ClaimUseIntegrityError("fresh schema-4 origin must be zero")
    maximum = connection.execute("SELECT coalesce(max(event_id),0) FROM audit_events").fetchone()[0]
    if origin > maximum:
        raise ClaimUseIntegrityError("freshness origin exceeds scientific event watermark")
    if store._schema_version == 6:
        # Older schemas retain their exact validation contract; schema 6 also
        # requires every nonzero activation boundary to name an actual event.
        if type(origin_rows[0][0]) is not int or (migration is not None and migration != (3,)):
            raise ClaimUseIntegrityError("invalid registration activation boundary")
        if origin and connection.execute("SELECT 1 FROM audit_events WHERE event_id=?", (origin,)).fetchone() is None:
            raise ClaimUseIntegrityError("registration activation watermark lacks scientific event")
    policy_origin = _policy_origin(connection, origin, maximum) if store._schema_version in (5, 6) else None
    context_origin = _context_origin(connection, policy_origin, maximum) if store._schema_version == 6 else None
    if connection.execute("SELECT 1 FROM claim_use_bindings WHERE registration_event<=? LIMIT 1", (origin,)).fetchone():
        raise ClaimUseIntegrityError("pre-origin generic document was registered")
    count_bindings, count_transitions = 0, 0
    for event, sid in connection.execute("SELECT event_id,submission_id FROM audit_events WHERE event_id>? ORDER BY event_id", (origin,)):
        policy_active = policy_origin is not None and event > policy_origin
        context_active = context_origin is not None and event > context_origin
        selected = connection.execute("""SELECT 1 FROM revisions r JOIN identities i USING(record_id)
            WHERE r.submission_id=? AND (i.kind IN ('review','issue','promotion_eligibility')
            OR (? AND i.kind='decision') OR (? AND i.kind='research_context')) LIMIT 1""", (sid, policy_active, context_active)).fetchone()
        if selected is None:
            plan = None
        else:
            row = connection.execute("SELECT typeof(request_json),length(CAST(request_json AS BLOB)) FROM submissions WHERE submission_id=?", (sid,)).fetchone()
            if row is None or row[0] != "text":
                raise ClaimUseIntegrityError("invalid freshness submission request")
            _check_count(row[1], WRITE_LIMITS["request_bytes"], "request_bytes")
            text = connection.execute("SELECT request_json FROM submissions WHERE submission_id=?", (sid,)).fetchone()[0]
            doc = _strict_json(text)
            submission = Submission.from_dict(doc["submission"])
            if _canonical({"fingerprint_version": 1, "submission": submission.to_dict()}) != text:
                raise ClaimUseIntegrityError("noncanonical freshness request")
            try:
                plan = prepare(store, connection, submission, cutoff=event, verify=False,
                               policy=policy_active, context=context_active)
            except (RecordNotFoundError, ReferenceResolutionError) as error:
                if not context_active:
                    raise
                # New context admission errors are corruption when reconstructing
                # already committed history; preserve preceding feature errors.
                raise ClaimUseIntegrityError(f"event {event}: incoherent required freshness metadata: {error}") from error
            if plan is not None:
                # Preparation already consumed its complete admission account.
                # Each stored-record comparison has an independent bounded reader,
                # without proposed cache, overlay or aggregate parent.
                for proposed in submission.records:
                    comparison = Reader(store, connection)
                    # This independent phase compares exact envelopes, not scope
                    # semantics. Unwatched generic contexts must not gain a codec
                    # requirement merely by entering chronological selection.
                    if context_active and proposed.kind == "research_context":
                        actual = comparison.read((proposed.record_id, proposed.revision), classify=False)
                    else:
                        actual = comparison.read((proposed.record_id, proposed.revision))
                    if actual != proposed:
                        raise ClaimUseIntegrityError("stored revision differs from canonical freshness submission")
        expected_bindings = {} if plan is None else plan.bindings
        actual_bindings = list(connection.execute("SELECT use_id,binding_revision FROM claim_use_bindings WHERE registration_event=? ORDER BY use_id,binding_revision", (event,)))
        if actual_bindings != sorted(expected_bindings):
            raise ClaimUseIntegrityError(f"event {event}: registration projection mismatch")
        for key in actual_bindings:
            verification = Reader(store, connection)
            actual_deps = _dependencies(verification, key)
            actual_upstreams = _upstreams(verification, key)
            if actual_deps != plan.dependencies[key] or actual_upstreams != plan.upstreams[key]:
                raise ClaimUseIntegrityError("derived dependency/upstream projection mismatch")
        transitions = {} if plan is None else plan.transitions
        actual_ids = [r[0] for r in connection.execute("SELECT use_id FROM claim_use_generations WHERE event_id=? ORDER BY use_id", (event,))]
        if actual_ids != sorted(transitions):
            raise ClaimUseIntegrityError(f"event {event}: missing or extra generation transition")
        for identity, (revision, generation, causes) in transitions.items():
            _verify_transition(connection, identity, revision, generation, sid, event, causes)
        count_bindings += len(actual_bindings)
        count_transitions += len(actual_ids)
    if (connection.execute("SELECT count(*) FROM claim_use_bindings").fetchone()[0] != count_bindings
            or connection.execute("SELECT count(*) FROM claim_use_generations").fetchone()[0] != count_transitions):
        raise ClaimUseIntegrityError("orphan freshness binding or transition")
    for identity, revision, generation, status, event in connection.execute("SELECT * FROM claim_use_current"):
        head = connection.execute("SELECT head,kind FROM identities WHERE record_id=?", (identity,)).fetchone()
        last = connection.execute("""SELECT binding_revision,generation,status,event_id FROM claim_use_generations
            WHERE use_id=? ORDER BY generation DESC LIMIT 1""", (identity,)).fetchone()
        if head != (revision, "promotion_eligibility") or last != (revision, generation, status, event):
            raise ClaimUseIntegrityError("registered head/current generation projection mismatch")
    missing = connection.execute("""SELECT 1 FROM claim_use_bindings b LEFT JOIN claim_use_current c USING(use_id)
        WHERE c.use_id IS NULL LIMIT 1""").fetchone()
    if missing or connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ClaimUseIntegrityError("missing current projection or invalid freshness foreign key")
    if policy_origin is not None:
        _validate_activation(store, connection, policy_origin)
    if context_origin is not None:
        _validate_activation(store, connection, context_origin, context=True)


def _policy_origin(connection, registration_origin, maximum):
    """Validate the independent policy activation singleton and attributed migration boundary."""
    rows = list(connection.execute("SELECT singleton,event_watermark FROM claim_use_policy_origin LIMIT 2"))
    if (len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] != 1
            or type(rows[0][1]) is not int or not registration_origin <= rows[0][1] <= maximum):
        raise ClaimUseIntegrityError("invalid policy freshness origin")
    origin = rows[0][1]
    migration = connection.execute("SELECT source_schema FROM migration_history WHERE target_schema=5").fetchone()
    if migration is None:
        if origin != 0:
            raise ClaimUseIntegrityError("fresh schema-5 policy origin must be zero")
    elif migration != (4,):
        raise ClaimUseIntegrityError("policy activation requires matching 4-to-5 migration")
    if origin and connection.execute("SELECT 1 FROM audit_events WHERE event_id=?", (origin,)).fetchone() is None:
        raise ClaimUseIntegrityError("policy activation watermark lacks scientific event")
    return origin


def _context_origin(connection, policy_origin, maximum):
    """Validate the independent target-context activation singleton and attributed migration boundary."""
    rows = list(connection.execute("SELECT singleton,event_watermark FROM claim_use_context_origin LIMIT 2"))
    if (len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] != 1
            or type(rows[0][1]) is not int or not policy_origin <= rows[0][1] <= maximum):
        raise ClaimUseIntegrityError("invalid target-context freshness origin")
    origin = rows[0][1]
    migration = connection.execute("SELECT source_schema FROM migration_history WHERE target_schema=6").fetchone()
    if migration is None:
        if origin != 0:
            raise ClaimUseIntegrityError("fresh schema-6 context origin must be zero")
    elif migration != (5,):
        raise ClaimUseIntegrityError("target-context activation requires matching 5-to-6 migration")
    if origin and connection.execute("SELECT 1 FROM audit_events WHERE event_id=?", (origin,)).fetchone() is None:
        raise ClaimUseIntegrityError("target-context activation watermark lacks scientific event")
    return origin


def _validate_activation(store, connection, watermark, *, context=False):
    """Stream independent policy or context boundary inspections without inventing transitions.

    Seeking the first later event avoids watermark-plus-one overflow and excludes
    every later revision/registration from each activation account. No lifetime
    Python collection or aggregate admission account spans these independent roots.
    Policy activation always disables context interpretation, even on schema 6;
    context activation enables both features for an independent version-3 view.
    """
    from research_pipeline.store import RecordNotFoundError, ReferenceResolutionError
    row = connection.execute("SELECT event_id FROM audit_events WHERE event_id>? ORDER BY event_id LIMIT 1",
                             (watermark,)).fetchone()
    cutoff = row[0] if row else None
    limits = ClaimUseInspectionLimits(512, 1024, 8192, 1024, 64*1024*1024, 4*1024*1024)
    for identity, in connection.execute("""SELECT use_id FROM claim_use_bindings
            WHERE registration_event<=? GROUP BY use_id ORDER BY use_id""", (watermark,)):
        reader = Reader(store, connection, limits=limits, cutoff=cutoff, policy=True, context=context)
        try:
            _inspection(reader, identity, limits)
        except (RecordNotFoundError, ReferenceResolutionError) as error:
            if not context:
                raise
            # Activation is an integrity check of an unpublished copy, not fresh
            # reference admission. The publisher must retain its incomplete marker.
            raise ClaimUseIntegrityError(f"context activation: incoherent required metadata: {error}") from error
