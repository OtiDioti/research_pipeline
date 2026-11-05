"""Connection-owned first lifecycle sources, durable objects and original-ID recovery.

BEGIN IMMEDIATE spans origin verification, complete resource replay, scientific
closure, artifact verification/durability and source insertion. Historical recovery
never consults current policy, recaptures evidence, or opens artifact objects.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib

from research_pipeline import lifecycle_report_source as source
from research_pipeline import lifecycle_report_binding as binding
from research_pipeline import run_control as control, run_control_store as controls
from research_pipeline import operating_authority as authority, operating_authority_store as operating
from research_pipeline import reports, resource_ledger as ledger, resources
from research_pipeline.domain import RecordEnvelope, RecordReference, ArtifactReference, CreationProvenance, Submission, SubmissionReceipt
from research_pipeline.report_capture import _text_length, _integer_length, _require_schema, _verify_bindings
from research_pipeline.snapshot import (
    SnapshotLimits, SnapshotSelection, RootSelector, SnapshotLimitError,
    SnapshotIntegrityError, _classification, _json_parts, _strict_json,
)
from research_pipeline.schema import validate_request_kinds
from research_pipeline.lifecycle_report_source import (
    LifecycleSourceArgumentError, LifecycleSourceValidationError, LifecycleSourceLimitError,
    LifecycleSourceIntegrityError, LifecycleSourceStateError,
)


def _fault(boundary):
    """Expose deterministic first-read, capture, object and commit failure/synchronization seams."""


@contextmanager
def _errors():
    """Translate inherited logical failures while preserving real storage and artifact failures."""
    try:
        yield
    except (control.RunControlLimitError, authority.AuthorityLimitError, SnapshotLimitError,
            resources.ResourceInspectionLimitError, reports.ReportLimitError,
            binding.LifecycleReportBindingLimitError):
        raise LifecycleSourceLimitError('source inherited processing ceiling exceeded') from None
    except (control.RunControlIntegrityError, authority.AuthorityIntegrityError,
            SnapshotIntegrityError, resources.ResourceIntegrityError, reports.ReportIntegrityError,
            resources.ResourceValidationError, reports.ReportScopeError,
            LifecycleSourceValidationError, binding.LifecycleReportBindingValidationError):
        raise LifecycleSourceIntegrityError('inconsistent stored source evidence') from None


def _store(store):
    """Require the exact connection owner before consulting its schema or handle state."""
    from research_pipeline.store import RecordStore
    if type(store) is not RecordStore:
        raise LifecycleSourceArgumentError('expected exact RecordStore')
    _require_schema(store)


class _Workspace:
    """Retain logical wrapper reservations until their simultaneous representations leave scope."""

    def __init__(self, limits):
        """Initialize one transaction's outer representation allowance, independent of nested budgets."""
        self.limits, self.used = limits, 0

    def reserve(self, size, stage, *, maximum=None):
        """Authorize 64 times exact wrapper size before its constructor or canonical copies."""
        if size < 0 or maximum is not None and size > maximum:
            raise LifecycleSourceLimitError(stage + ' framing ceiling exceeded')
        self.reserve_charge(64 * size, stage)

    def reserve_charge(self, charge, stage):
        """Retain an already scaled charge until operation completion; failure leaves usage intact."""
        if charge < 0 or self.used + charge > self.limits.max_work_bytes:
            raise LifecycleSourceLimitError(stage + ' workspace ceiling exceeded')
        self.used += charge


def _length(row):
    """Sum scalar length preflight results, rejecting missing joins or incorrect SQL types."""
    if row is None or any(type(n) is not int or n < 0 for n in row):
        raise LifecycleSourceIntegrityError('invalid source metadata storage type')
    return sum(row)


def _row(reader, table, columns, where, args, *, integers=(), nullable=(), repeat=1):
    """Charge every selected fixed SQL column before fetching a variable-sized metadata row."""
    names = columns.split()
    expressions = [_integer_length(n, 0 if n.split('.')[-1] in ('ordinal', 'size') else 1) if n in integers
                   else _text_length(n, nullable=n in nullable) for n in names]
    lengths = reader.connection.execute('SELECT ' + ','.join(expressions) + ' FROM ' + table + ' WHERE ' + where, args).fetchone()
    size = _length(lengths)
    if size > reader.limits.max_record_bytes:
        raise LifecycleSourceLimitError('source SQL record ceiling exceeded')
    reader.reserve(size * repeat)
    return reader.connection.execute('SELECT ' + ','.join(names) + ' FROM ' + table + ' WHERE ' + where, args).fetchone()


def _stored(text, limits, *, maximum):
    """Decode preflighted stored canonical bytes with bounded lexical and representation work."""
    if len(text) > maximum:
        raise LifecycleSourceLimitError('source stored submission ceiling exceeded')
    try:
        value, raw = source._parse(text, limits)
        size = source._measure(value, maximum, limits)
        if 8 * raw + 64 * size > limits.max_work_bytes:
            raise LifecycleSourceLimitError('source stored JSON workspace ceiling exceeded')
        if control.canonical(value) != text:
            raise LifecycleSourceIntegrityError('noncanonical stored source JSON')
        return value
    except LifecycleSourceValidationError:
        raise LifecycleSourceIntegrityError('invalid stored source JSON') from None


def _original(reader, operation, limits, work):
    """Verify a complete original batch, including unrelated members and all actual projections.

    Full request bytes, actual member counts/order, audit fields and every member
    projection pass scalar SQL preflight before submission reconstruction. This is
    also used for scientific source bindings; no legacy unbounded fallback exists.
    """
    connection = reader.connection
    lengths = connection.execute('SELECT ' + _text_length('request_json') + ',' + _text_length('fingerprint') +
        ' FROM submissions WHERE submission_id=?', (operation,)).fetchone()
    if lengths is None:
        return None
    size = _length(lengths)
    if lengths[0] > min(limits.max_submission_bytes, reader.limits.max_record_bytes):
        raise LifecycleSourceLimitError('original submission byte ceiling exceeded')
    if lengths[1] != 64:
        raise LifecycleSourceIntegrityError('invalid original submission fingerprint')
    count = connection.execute('SELECT count(*) FROM revisions WHERE submission_id=?', (operation,)).fetchone()[0]
    if type(count) is not int or count < 1:
        raise LifecycleSourceIntegrityError('original submission has no actual members')
    if count > reader.limits.max_records:
        raise LifecycleSourceLimitError('original submission member count ceiling exceeded')
    columns = (_text_length('record_id'), _integer_length('revision', 1), _integer_length('ordinal'))
    for row in connection.execute('SELECT ' + ','.join(columns) + ' FROM revisions WHERE submission_id=? ORDER BY ordinal', (operation,)):
        contribution = _length(row)
        if contribution > reader.limits.max_record_bytes:
            raise LifecycleSourceLimitError('original member metadata ceiling exceeded')
        reader.reserve(contribution)
    members = []
    for index, row in enumerate(connection.execute('SELECT record_id,revision,ordinal FROM revisions WHERE submission_id=? ORDER BY ordinal', (operation,))):
        if row[2] != index:
            raise LifecycleSourceIntegrityError('noncontiguous original member ordinals')
        reader.preflight(row[:2])
        members.append(row)
    if len(members) != count:
        raise LifecycleSourceIntegrityError('original member count changed')
    audit = _row(reader, 'audit_events', 'event_id submission_id event_type committed_at provenance_json',
                 'submission_id=?', (operation,), integers=('event_id',), repeat=2)
    reader.reserve(size * 3)
    # The batch is temporary, but canonical request and reconstructed member
    # envelopes coexist during comparisons. Reserve their whole wrapper first.
    work.reserve(lengths[0], 'original submission', maximum=limits.max_submission_bytes)
    raw, fingerprint = connection.execute('SELECT request_json,fingerprint FROM submissions WHERE submission_id=?', (operation,)).fetchone()
    saved = _stored(raw, limits, maximum=limits.max_submission_bytes)
    try:
        control.authority.exact(saved, 'fingerprint_version submission')
        if type(saved['fingerprint_version']) is not int or saved['fingerprint_version'] != 1:
            raise ValueError
        wire = saved['submission']
        if type(wire['records']) is not list or len(wire['records']) != count:
            raise ValueError
        for member in wire['records']:
            source._measure(member, reader.limits.max_record_bytes, limits)
        submitted = Submission.from_dict(wire)
        if (submitted.submission_id != operation or submitted.to_dict() != wire or
                hashlib.sha256(raw.encode('ascii')).hexdigest() != fingerprint or
                audit[1:3] != (operation, 'submission_committed') or
                control.canonical(submitted.provenance.to_dict()) != audit[4] or
                members != [(r.record_id, r.revision, i) for i, r in enumerate(submitted.records)]):
            raise ValueError
        for expected in submitted.records:
            actual = reader.read((expected.record_id, expected.revision))
            if actual.to_dict() != expected.to_dict() or reader.submission_ids[(actual.record_id, actual.revision)] != operation:
                raise ValueError
            for ref in actual.record_references:
                reader.shallow(ref)
            for ref in actual.artifact_references:
                registration = _row(reader, 'artifacts', 'digest size', 'digest=?', (ref.digest,), integers=('size',))
                if registration != (ref.digest, ref.size):
                    raise ValueError
        receipt_size = controls._receipt_size(operation, len(audit[4]), [r[:2] for r in members],
            len(str(audit[0])), control._string_size(audit[3]))
        reader.reserve(receipt_size)
        work.reserve(receipt_size, 'original receipt', maximum=limits.max_result_bytes)
        receipt = SubmissionReceipt(operation, fingerprint, audit[0], audit[3], submitted.provenance,
                                    tuple(row[:2] for row in members))
        if receipt.committed_at != audit[3]:
            raise ValueError
    except (LifecycleSourceLimitError, authority.AuthorityLimitError, control.RunControlLimitError):
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise LifecycleSourceIntegrityError('inconsistent original source submission') from None
    return submitted, receipt


def _origin(reader, operation, limits, *, through=None):
    """Resolve accepted binding only from persisted original envelopes and required control prefix."""
    from research_pipeline.store import RecordNotFoundError
    found = controls._operation(reader, operation)
    if found is None:
        raise RecordNotFoundError('control operation not found')
    history = controls._history(reader, found[0].record_id, through=through)
    if not history or found[0].revision > len(history):
        raise LifecycleSourceIntegrityError('selected intent absent from captured control prefix')
    first = history[0][0]
    # The initial transition deliberately occurs twice. Both full envelopes count.
    skeleton = binding._wrapper(None, None, None)
    size = source._measure(skeleton, limits.binding.max_packet_bytes, limits) - 12 + sum(
        reader.envelope_sizes[(e.record_id, e.revision)] for e in (first, found[0], found[2]))
    if size > limits.binding.max_packet_bytes or 64 * size > limits.binding.max_work_bytes:
        raise LifecycleSourceLimitError('binding wrapper ceiling exceeded')
    reader.reserve(size * 3)
    packet = binding.bind_lifecycle_report(first.to_dict(), found[0].to_dict(), found[2].to_dict(), limits=limits.binding)
    digest = binding.binding_digest(packet, limits=limits.binding)
    return found, history, packet.to_dict(limits=limits.binding), digest


def _captured(inspection):
    """Pin the actual final transition in a validated captured control inspection."""
    return {'reference': inspection['head'],
            'envelope_digest': control.envelope_digest(RecordEnvelope.from_dict(inspection['transitions'][-1]['envelope']))}


def _result_document(event, receipt):
    """Assemble an already reserved immutable source-result wrapper without opening artifacts."""
    value = event.content
    return {'format': source.FORMATS[2], 'version': 1, 'operation_id': receipt.submission_id,
        'control_operation_id': value['request']['control_operation_id'],
        'binding_digest': value['request']['binding_digest'],
        'source_event': control.reference(event.record_id, 1, 'lifecycle_report_source'),
        **{key: value[key] for key in ('source_artifact', 'snapshot_id', 'observed_at',
                                      'scientific_watermark', 'resource_sequence', 'captured_control')},
        'receipt': receipt.to_dict(), 'ordinary_work_allowed': False, 'recheck_required': True}


def _result_size(event_content, operation, event_id, receipt_size):
    """Measure full result framing before construction, using an actual or bounded receipt size."""
    return operating._object_bytes(format=control._string_size(source.FORMATS[2]), version=1,
        operation_id=control._string_size(source._identity(operation)), control_operation_id=control._string_size(operation),
        binding_digest=66, source_event=operating._reference_bytes(event_id, 1, 'lifecycle_report_source', 'event'),
        source_artifact=operating._fragment_bytes(event_content['source_artifact']), snapshot_id=66,
        observed_at=control._string_size(event_content['observed_at']),
        scientific_watermark=operating._fragment_bytes(event_content['scientific_watermark']),
        resource_sequence=operating._fragment_bytes(event_content['resource_sequence']),
        captured_control=operating._fragment_bytes(event_content['captured_control']), receipt=receipt_size,
        ordinary_work_allowed=5, recheck_required=4)


def _metadata(reader, operation, limits, work):
    """Reconcile S before fresh guards, preserving independent limit failures from inherited history readers."""
    from research_pipeline.store import SubmissionConflictError
    sid = source._identity(operation)
    found = _original(reader, sid, limits, work)
    if found is None:
        return None
    submitted, receipt = found
    if (len(submitted.records) != 1 or submitted.records[0].kind != 'event' or
            submitted.records[0].content.get('format') != source.FORMATS[1]):
        raise SubmissionConflictError('source operation identity belongs to another submission')
    event = submitted.records[0]
    value = event.content
    try:
        control.authority.exact(value, 'format version request snapshot_id observed_at scientific_watermark resource_sequence captured_control source_artifact')
        control.authority.exact(value['request'], 'control_operation_id binding_digest')
        if value['request']['control_operation_id'] != operation:
            raise SubmissionConflictError('source operation identity belongs to another control intent')
        expected_id = reports.source_id(control.report_operation_id(operation))
        if (type(value['version']) is not int or value['version'] != 1 or
                event.record_id != expected_id or event.revision != 1 or
                submitted.expected_heads != {expected_id: 0} or
                submitted.provenance != event.provenance or
                event.provenance.to_dict() != {'actor': 'lifecycle-source-controller', 'created_at': value['observed_at'], 'details': {}} or
                event.operational_status is not None or event.scientific_disposition is not None):
            raise LifecycleSourceIntegrityError('source original envelope mismatch')
        if (reader.head(expected_id) != {'record_id': expected_id, 'revision': 1, 'kind': 'event'} or
                reader.connection.execute('SELECT count(*) FROM revisions WHERE record_id=?', (expected_id,)).fetchone()[0] != 1):
            raise LifecycleSourceIntegrityError('source event must be one immutable revision')
        captured = value['captured_control']
        intent, history, packet, digest = _origin(reader, operation, limits, through=captured['reference']['revision'])
        if (digest != value['request']['binding_digest'] or
                captured['reference'] != control.reference(history[-1][0].record_id, history[-1][0].revision, 'run_control') or
                captured['envelope_digest'] != reader.digest(history[-1][0])):
            raise LifecycleSourceIntegrityError('source original binding or captured control mismatch')
        prior = _row(reader, 'audit_events a LEFT JOIN submissions s USING(submission_id)',
            'a.event_id a.submission_id a.committed_at s.fingerprint', 'a.event_id=?',
            (receipt.event_id - 1,), integers=('a.event_id',))
        if dict(zip(('event_id', 'submission_id', 'committed_at', 'fingerprint'), prior)) != value['scientific_watermark']:
            raise LifecycleSourceIntegrityError('source actual preceding audit tuple mismatch')
        if history[-1][3].event_id > prior[0]:
            raise LifecycleSourceIntegrityError('captured control follows source watermark')
        keys = [(r.record_id, r.revision) for r in event.record_references]
        if keys != sorted(set(keys)) or any(r.relationship != 'lifecycle_source_revision' or r.target_kind is None for r in event.record_references):
            raise LifecycleSourceIntegrityError('source event closure links mismatch')
        required = reports._scientific_roots(source._intent(packet))
        prep = packet['preparation']['content']['request']['preparation']
        required += [prep['initial_corpus'], prep['current_corpus'], captured['reference']]
        if 'record_id' in prep['start_baseline']:
            required.append(prep['start_baseline'])
        if not {reports.pin(ref) for ref in required} <= set(keys):
            raise LifecycleSourceIntegrityError('source event omits original required roots')
        artifacts = event.artifact_references
        if not artifacts or artifacts[0].to_dict() != value['source_artifact']:
            raise LifecycleSourceIntegrityError('source event artifact projection mismatch')
        digests = [r.digest for r in artifacts]
        if len(set(digests)) != len(digests) or digests[1:] != sorted(digests[1:]):
            raise LifecycleSourceIntegrityError('source artifact links are not distinct and ordered')
        if artifacts[0].size > min(limits.max_source_bytes, packet['transition']['content']['request']['report']['limits']['max_source_bytes']):
            raise LifecycleSourceLimitError('source original artifact framing ceiling exceeded')
        receipt_size = source._measure(receipt.to_dict(), limits.max_result_bytes, limits)
        work.reserve(_result_size(value, operation, event.record_id, receipt_size), 'source result', maximum=limits.max_result_bytes)
        result = source.LifecycleSourceCommitResult(_result_document(event, receipt), limits=limits)
        return result, event, receipt, packet
    except (LifecycleSourceLimitError, LifecycleSourceIntegrityError, SubmissionConflictError,
            control.RunControlLimitError, authority.AuthorityLimitError,
            binding.LifecycleReportBindingLimitError):
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise LifecycleSourceIntegrityError('invalid committed source metadata') from None


class _ScientificBudget:
    """Narrow shared capture work without serializing caller allowances as original intent."""

    def __init__(self, limits):
        """Retain already detached caller limits for private scientific preconstruction hooks."""
        self.limits = limits

    def effective(self, original):
        """Reserve Ws before shared capture and return narrower operational SnapshotLimits."""
        caller = self.limits.scientific
        maximum = min(caller.max_metadata_bytes, original.max_metadata_bytes)
        if 64 * maximum + 4096 > caller.max_work_bytes:
            raise LifecycleSourceLimitError('scientific workspace ceiling exceeded')
        values = original.to_dict()
        for name in values:
            if name != 'max_files':
                values[name] = min(values[name], getattr(caller, name))
        return SnapshotLimits(**values)

    def preflight_record(self, connection, key, references, limits):
        """Check actual stored types, lengths, counts and joins before scientific payload fetching."""
        expressions = [_text_length(n, nullable=n in ('r.operational_status', 'r.scientific_disposition'))
            for n in ('i.kind', 'r.content_json', 'r.provenance_json', 'r.operational_status',
                      'r.scientific_disposition', 'r.submission_id', 'a.committed_at', 's.fingerprint')]
        expressions += [_integer_length('r.revision', 1), _integer_length('r.ordinal'), _integer_length('a.event_id', 1)]
        row = connection.execute('SELECT ' + ','.join(expressions) + ''' FROM revisions r
            LEFT JOIN identities i USING(record_id) LEFT JOIN submissions s USING(submission_id)
            LEFT JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?''', key).fetchone()
        if _length(row) > limits.max_record_bytes:
            raise LifecycleSourceLimitError('scientific SQL record ceiling exceeded')
        total = 0
        for table, columns in (('record_links', (_text_length('target_id'), _integer_length('target_revision', 1),
                _text_length('relationship'), _text_length('target_kind', nullable=True))),
                ('artifact_links', (_text_length('digest'), _integer_length('size')))):
            count = connection.execute('SELECT count(*) FROM ' + table + ' WHERE record_id=? AND revision=?', key).fetchone()[0]
            total += count
            if total > references:
                raise LifecycleSourceLimitError('scientific SQL reference ceiling exceeded')
            for row in connection.execute('SELECT ' + ','.join(columns) + ' FROM ' + table + ' WHERE record_id=? AND revision=?', key):
                _length(row)

    def envelope(self, connection, key, raw, limits):
        """Measure complete envelope framing before domain reconstruction or escaped wire copies."""
        kind, operational, scientific = connection.execute('''SELECT i.kind,r.operational_status,r.scientific_disposition
            FROM revisions r JOIN identities i USING(record_id) WHERE r.record_id=? AND r.revision=?''', key).fetchone()
        parsed = []
        for text in raw[:2]:
            try:
                value, _ = binding._parse(text, (limits.max_record_bytes, limits.max_record_bytes,
                    self.limits.scientific.max_work_bytes, self.limits.max_nodes, min(64, self.limits.max_depth)))
            except binding.LifecycleReportBindingLimitError:
                raise LifecycleSourceLimitError('scientific nested JSON ceiling exceeded') from None
            if control.canonical(value) != text:
                raise LifecycleSourceIntegrityError('noncanonical scientific JSON')
            parsed.append(value)
        content, provenance = parsed
        # Count/length/type preflight already authorized these ordered scalar rows.
        links = [dict(zip(('record_id', 'revision', 'relationship', 'target_kind'), row)) for row in
            connection.execute('SELECT target_id,target_revision,relationship,target_kind FROM record_links WHERE record_id=? AND revision=? ORDER BY ordinal', key)]
        artifacts = [dict(zip(('digest', 'size'), row)) for row in connection.execute(
            'SELECT digest,size FROM artifact_links WHERE record_id=? AND revision=? ORDER BY ordinal', key)]
        size = operating._object_bytes(record_id=control._string_size(key[0]), revision=len(str(key[1])),
            kind=control._string_size(kind), content=len(raw[0]), provenance=len(raw[1]),
            record_references=source._measure(links, limits.max_record_bytes, self.limits),
            artifact_references=source._measure(artifacts, limits.max_record_bytes, self.limits),
            operational_status=operating._fragment_bytes(operational),
            scientific_disposition=operating._fragment_bytes(scientific))
        if size > limits.max_record_bytes:
            raise LifecycleSourceLimitError('scientific complete envelope ceiling exceeded')
        wire = {'record_id': key[0], 'revision': key[1], 'kind': kind, 'content': content,
            'provenance': provenance, 'record_references': links, 'artifact_references': artifacts,
            'operational_status': operational, 'scientific_disposition': scientific}
        source._measure(wire, limits.max_record_bytes, self.limits)
        return RecordEnvelope.from_dict(wire)

    def record_entry(self, envelope, raw, commit, fetched, maximum):
        """Measure escaped nested JSON and complete entry before allocating envelope JSON text."""
        from research_pipeline.store import _decode_typed_envelope
        wire = envelope.to_dict()
        escaped = 2
        for part in _json_parts(wire):
            escaped += control._string_size(part) - 2
            if escaped > maximum:
                raise LifecycleSourceLimitError('scientific escaped envelope ceiling exceeded')
        classification = _classification(envelope, _decode_typed_envelope)
        size = operating._object_bytes(record_id=control._string_size(envelope.record_id), revision=len(str(envelope.revision)),
            content_json=control._string_size(raw[0]), provenance_json=control._string_size(raw[1]),
            envelope_json=escaped, classification=source._measure(classification, maximum, self.limits),
            commit=source._measure(commit, maximum, self.limits), fetched_bytes=len(str(fetched)))
        if size > maximum:
            raise LifecycleSourceLimitError('scientific complete record entry ceiling exceeded')

    def snapshot_plan(self, selection, resolutions, schema, watermark, records, artifacts, original, fetched, maximum):
        """Measure repeated scope and full original-limit wrapper before constructing result arrays."""
        from research_pipeline.snapshot import _SCOPE_POLICY
        def measure(value):
            """Measure one existing fragment without copying its enclosing representation."""
            return source._measure(value, maximum, self.limits)
        requested = selection.to_dict()
        roots = {(r['record_id'], r['revision']) for r in resolutions}
        closure = operating._array_bytes(operating._object_bytes(
            record_id=control._string_size(key[0]), revision=len(str(key[1])))
            for key in records if key not in roots)
        reasons = operating._array_bytes(operating._object_bytes(digest=66,
            occurrences=measure(a['occurrences'])) for a in artifacts.values())
        scope_size = operating._object_bytes(**{k: measure(v) for k, v in _SCOPE_POLICY.items()},
            requested=measure(requested), resolutions=measure(resolutions), closure_only=closure,
            artifact_reasons=reasons)
        size = operating._object_bytes(format=len('"research_pipeline.snapshot.v1"'),
            selection=measure(requested), resolutions=measure(resolutions), schema=measure(schema),
            watermark=measure(watermark), records=operating._array_bytes(measure(r) for r in records.values()),
            artifacts=operating._array_bytes(measure(a) for a in artifacts.values()),
            limits=measure(original.to_dict()), metadata_fetched_bytes=len(str(fetched)),
            scope=scope_size, snapshot_id=66)
        if size > maximum:
            raise LifecycleSourceLimitError('scientific complete snapshot framing ceiling exceeded')

    def snapshot(self, document, maximum):
        """Check exact full snapshot framing with original embedded limits before hashing/copying."""
        size = source._measure(document, maximum, self.limits)
        size += len(',"snapshot_id":') + 66
        if size > maximum:
            raise LifecycleSourceLimitError('scientific complete snapshot framing ceiling exceeded')


class _ResourceBudget:
    """Preflight the complete ledger's SQL cells and reserve the accepted replay workspace."""

    def __init__(self, limits, original):
        """Combine independent caller and embedded capture ceilings without changing projection intent."""
        self.limits, self.original = limits, original
        self.bytes = self.rows = self.references = 0
        self.maximum = min(limits.resources.max_metadata_bytes, original['max_metadata_bytes'])

    def scan(self, connection, table, columns, *, integers=(), nullable=(), repeat=1, where='', args=()):
        """Count every consumed scalar and repeated planned row before any payload fetch."""
        names = columns.split()
        expressions = [_integer_length(n, 0 if n.split('.')[-1] in ('ordinal', 'size') else 1) if n in integers
                       else _text_length(n, nullable=n in nullable) for n in names]
        for row in connection.execute('SELECT ' + ','.join(expressions) + ' FROM ' + table + where, args):
            size = _length(row)
            if any(length > 65536 for name, length in zip(names, row)
                   if name.split('.')[-1] in ('request_json', 'result_json')):
                raise LifecycleSourceLimitError('resource inherited request/receipt ceiling exceeded')
            if size > self.limits.resources.max_record_bytes:
                raise LifecycleSourceLimitError('resource SQL record ceiling exceeded')
            self.bytes += size * repeat
            self.rows += repeat
            if self.rows > self.limits.resources.max_rows or self.bytes > self.maximum:
                raise LifecycleSourceLimitError('resource SQL rows/metadata ceiling exceeded')

    def membership(self, connection, *, sequence=None, replay=False, probe_operations=None):
        """Reconcile bounded original declarations/ordered links before any target query or replay.

        Fresh replay consumes all rows a second time. Historical verification has
        its own separately charged later reads and never includes later operations.
        """
        r = self.limits.resources
        where = '' if sequence is None else ' WHERE sequence<=?'
        args = () if sequence is None else (sequence,)
        operations = connection.execute('SELECT count(*) FROM resource_operations' + where, args).fetchone()[0]
        if operations > min(r.max_operations, self.original['max_operations']):
            raise LifecycleSourceLimitError('resource complete replay counts ceiling exceeded')
        if sequence is not None and operations != sequence:
            raise LifecycleSourceIntegrityError('incomplete historical resource sequence')
        columns = 'sequence operation_id receipt_id request_json fingerprint result_json committed_at'
        repeat = 2 if replay else 1
        self.scan(connection, 'resource_operations', columns, integers=('sequence',),
                  repeat=repeat, where=where, args=args)
        suffix = '' if sequence is None else ' WHERE operation_id IN (SELECT operation_id FROM resource_operations WHERE sequence<=?)'
        tables = (('accounts', ledger._ACCOUNT_COLUMNS), ('allocations', ledger._ALLOCATION_COLUMNS),
                  ('reservations', ledger._RESERVATION_COLUMNS), ('record_links', ledger._LINK_COLUMNS))
        for key, names in tables:
            if key in ('accounts', 'record_links'):
                count = connection.execute('SELECT count(*) FROM resource_' + key + suffix, args).fetchone()[0]
                maximum = (min(r.max_accounts, self.original['max_accounts']) if key == 'accounts' else r.max_references)
                if count > maximum:
                    raise LifecycleSourceLimitError('resource stored membership counts ceiling exceeded')
            self.scan(connection, 'resource_' + key, names, repeat=repeat, where=suffix, args=args,
                      integers=('ordinal', 'target_revision') if key == 'record_links' else (),
                      nullable=('parent_account_id',) if key == 'accounts' else ())
        if 256 * (self.bytes + 1) > r.max_work_bytes:
            raise LifecycleSourceLimitError('resource metadata workspace ceiling exceeded')
        membership = source._ResourceMembership(r, self.original)
        mismatched = False
        for row in connection.execute('SELECT ' + ','.join(columns.split()) + ' FROM resource_operations' + where + ' ORDER BY sequence', args):
            try:
                request, _ = binding._parse(row[3], (min(65536, r.max_record_bytes),
                    min(65536, r.max_record_bytes), r.max_work_bytes,
                    self.limits.max_nodes, min(16, self.limits.max_depth)))
                membership.add(request)
                if request['operation_id'] != row[1] or control.canonical(request) != row[3]:
                    mismatched = True
            except binding.LifecycleReportBindingLimitError:
                raise LifecycleSourceLimitError('resource request lexical ceiling exceeded') from None
            except LifecycleSourceLimitError:
                raise
            except (ValueError, TypeError, KeyError, AttributeError):
                raise LifecycleSourceIntegrityError('invalid resource request membership') from None
        self.references = membership.references
        # Full work can already be independently exceeded before comparing corrupt
        # projections; target probe charges below can only increase this bound.
        membership.work(self.bytes)
        if mismatched:
            raise LifecycleSourceIntegrityError('resource original request identity mismatch')
        try:
            for key, names in tables:
                actual = connection.execute('SELECT ' + ','.join(names.split()) +
                    ' FROM resource_' + key + suffix + ' ORDER BY 1' + (',2' if key == 'record_links' else ''), args)
                if key == 'record_links':
                    if list(actual) != sorted(membership.links):
                        raise LifecycleSourceIntegrityError('resource original references mismatch')
                else:
                    membership.reconcile(key, ((row[0], row[1]) for row in actual))
        except source.LifecycleSourceValidationError:
            raise LifecycleSourceIntegrityError('resource declaration membership mismatch') from None
        for operation, ordinal, identity, revision, relationship, kind in membership.links:
            if probe_operations is not None and operation not in probe_operations:
                continue
            before = self.rows
            self.scan(connection, 'revisions r LEFT JOIN identities i USING(record_id) LEFT JOIN audit_events a USING(submission_id)',
                'i.kind a.event_id', integers=('a.event_id',),
                where=' WHERE r.record_id=? AND r.revision=?', args=(identity, revision))
            if self.rows == before:
                raise LifecycleSourceIntegrityError('missing resource reference target')
        membership.work(self.bytes)

    def preflight(self, connection):
        """Authorize auxiliary reads and verified request membership before complete shared replay."""
        self.scan(connection, 'migration_history', 'migration_id source_schema target_schema source_backup_id source_manifest_json provenance_json',
            integers=('migration_id', 'source_schema', 'target_schema'), repeat=2)
        self.scan(connection, 'artifacts', 'digest size', integers=('size',))
        self.scan(connection, 'sqlite_master', 'sql', where=' WHERE sql IS NOT NULL')
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        if type(version) is not int or version not in (3, 4):
            raise LifecycleSourceIntegrityError('resource schema mismatch')
        self.rows += 1
        self.bytes += len(str(version))
        operations = connection.execute('SELECT count(*) FROM resource_operations').fetchone()[0]
        # Nonzero watermark probes return one integer; reserve their upper count
        # before receipts are decoded; membership adds its separately charged reads.
        self.rows += operations
        self.bytes += operations
        if self.rows > self.limits.resources.max_rows or self.bytes > self.maximum:
            raise LifecycleSourceLimitError('resource auxiliary rows/metadata ceiling exceeded')
        self.membership(connection, replay=True)
        if connection.execute('SELECT count(*) FROM pragma_foreign_key_check').fetchone()[0]:
            raise LifecycleSourceIntegrityError('resource replay foreign key violation')

    def result(self, body):
        """Bound the complete resource snapshot before its constructor and retained canonical copies."""
        maximum = min(self.maximum, self.limits.resources.max_result_bytes)
        size = source._measure(body, maximum, self.limits) + len(',"snapshot_id":') + 66
        if size > maximum or self.bytes + size > self.maximum:
            raise LifecycleSourceLimitError('resource complete wrapper ceiling exceeded')
        self.complete_size = size

    def projection(self, projected, balances, scope, operations, request, snapshot):
        """Measure the selected-project wrapper before retaining it alongside the complete replay."""
        maximum = min(self.maximum, self.limits.resources.max_result_bytes)
        def measure(value):
            """Measure existing replay fragments without allocating another canonical copy."""
            return source._measure(value, maximum, self.limits)
        size = operating._object_bytes(format=len('"research_pipeline.report_resources"'), version=1,
            project=measure(request['project']), run=measure(request['run']),
            resource_sequence=len(str(snapshot['resource_sequence'])), complete_snapshot_id=66,
            operations=measure(operations), **{k: measure(v) for k, v in projected.items()},
            balances=measure(balances), scope=measure(scope), limits=measure(request['limits']['resources']))
        if size > maximum or self.bytes + self.complete_size + size > self.maximum:
            raise LifecycleSourceLimitError('resource selected projection wrapper ceiling exceeded')


def _resources(connection, schema, packet, limits):
    """Return selected-project facts and the complete prefix's private latest date.

    Replay on the coherent connection uses existing bounds; schema 2 returns its
    exact unavailable projection and no date without querying resource storage.
    """
    if schema == 2:
        return reports.unavailable('Schema 2: resource accounting unavailable; explicit migration to schema 3 is required.'), None
    intent = source._intent(packet)
    original = intent['limits']['resources']
    budget = _ResourceBudget(limits, original)
    effective = resources.ResourceInspectionLimits(max(1, min(original['max_accounts'], limits.resources.max_accounts)),
        max(1, min(original['max_operations'], limits.resources.max_operations)), budget.maximum)
    complete = ledger._inspect(connection, effective, _source_budget=budget).to_dict()
    # The existing replay workspace covers this constant-storage reduction.
    # Prefix membership includes private operations, but only a scalar escapes;
    # sequence order does not imply monotonic receipt timestamps.
    complete_resource_time = None
    for operation in complete['operations']:
        date = operation['receipt']['committed_at']
        if complete_resource_time is None or date > complete_resource_time:
            complete_resource_time = date
    result = reports._project_resources(complete, intent, _source_budget=budget)
    del complete
    source._resource_preflight(result, limits, original)
    reports._validate_resources(result, intent, 3)
    return result, complete_resource_time


def _resource_read_preflight(connection, projection, limits):
    """Charge historical reads and reconcile original request membership before account maps/queries."""
    budget = _ResourceBudget(limits, projection['limits'])
    sequence = projection['resource_sequence']
    budget.scan(connection, 'resource_accounts a JOIN resource_operations o ON a.operation_id=o.operation_id',
        'a.account_id a.parent_account_id a.scope_json', nullable=('a.parent_account_id',),
        where=' WHERE o.sequence<=?', args=(sequence,))
    budget.scan(connection, 'resource_operations', 'sequence result_json', integers=('sequence',),
        where=' WHERE sequence<=?', args=(sequence,))
    for item in projection['operations']:
        operation = item['request']['operation_id']
        budget.scan(connection, 'resource_operations', 'sequence operation_id receipt_id request_json fingerprint result_json committed_at',
            integers=('sequence',), where=' WHERE operation_id=?', args=(operation,))
        budget.scan(connection, 'resource_record_links', ledger._LINK_COLUMNS,
            integers=('ordinal', 'target_revision'), where=' WHERE operation_id=?', args=(operation,))
    for key, columns in (('accounts', ledger._ACCOUNT_COLUMNS), ('allocations', ledger._ALLOCATION_COLUMNS),
                         ('reservations', ledger._RESERVATION_COLUMNS)):
        identity = columns.split()[0]
        for item in projection[key]:
            budget.scan(connection, 'resource_' + key, columns,
                nullable=('parent_account_id',) if key == 'accounts' else (),
                where=' WHERE ' + identity + '=?', args=(item[identity],))
        if key != 'accounts':
            budget.scan(connection, 'resource_' + key + ' r JOIN resource_operations o ON r.operation_id=o.operation_id',
                'r.' + identity + ' r.account_id', where=' WHERE o.sequence<=?', args=(sequence,))
    budget.membership(connection, sequence=sequence,
                      probe_operations={item['request']['operation_id'] for item in projection['operations']})
    return budget


def _resource_originals(reader, projection, observed_at, limits):
    """Verify saved relevant requests/receipts, normalized immutable rows and complete membership.

    Later operations are excluded by their original sequence. No current balances
    or current resource snapshot is reconstructed, and later artifact availability
    is irrelevant. Original receipt account IDs select the saved project subtree.
    Every historical normalized scope is validated before hierarchy traversal;
    malformed metadata fails through the sanitized public integrity boundary.
    Every validated receipt in the saved prefix must precede or equal observed_at,
    including omitted private operations; violations raise IntegrityError without
    exposing their payloads or scanning operations beyond the saved sequence.
    """
    if 'operations' not in projection:
        return
    connection = reader.connection
    selected = {a['account_id'] for a in projection['accounts']}
    _resource_read_preflight(connection, projection, limits)
    sequence = projection['resource_sequence']
    # Validate all historical scopes, including children and siblings, before
    # traversal so malformed metadata reaches the sanitized integrity boundary.
    # The sequence cutoff excludes later operations and their balance state.
    all_accounts = {}
    for aid, parent, scope_json in connection.execute('''SELECT a.account_id,a.parent_account_id,a.scope_json
            FROM resource_accounts a JOIN resource_operations o ON a.operation_id=o.operation_id WHERE o.sequence<=?''', (sequence,)):
        all_accounts[aid] = (parent, resources.ScopeReference(resources.strict_json(scope_json)).to_dict())
    actual_selected = set()
    for aid in all_accounts:
        current, visited = aid, set()
        while all_accounts[current][0] is not None:
            if current in visited or all_accounts[current][0] not in all_accounts:
                raise LifecycleSourceIntegrityError('saved resource hierarchy mismatch')
            visited.add(current)
            current = all_accounts[current][0]
        scope = all_accounts[current][1]
        if scope['type'] == 'record' and scope['kind'] == 'project' and scope['reference']['record_id'] == projection['project']['record_id']:
            actual_selected.add(aid)
    if actual_selected != selected:
        raise LifecycleSourceIntegrityError('incomplete saved relevant account membership')
    expected = {item['request']['operation_id']: item for item in projection['operations']}
    actual_operations = set()
    for seq, result_json in connection.execute('SELECT sequence,result_json FROM resource_operations WHERE sequence<=? ORDER BY sequence', (sequence,)):
        receipt = resources.ResourceReceipt.from_dict(resources.strict_json(result_json)).to_dict()
        if receipt['sequence'] != seq:
            raise LifecycleSourceIntegrityError('saved resource sequence mismatch')
        # Reuse the charged prefix scan before filtering private accounts. A
        # detached projection cannot establish omitted receipt dates on its own.
        if receipt['committed_at'] > observed_at:
            raise LifecycleSourceIntegrityError('saved source predates resource prefix receipt')
        if receipt['account_id'] in selected:
            actual_operations.add(receipt['operation_id'])
    if actual_operations != set(expected):
        raise LifecycleSourceIntegrityError('incomplete saved relevant operation membership')
    for operation, item in expected.items():
        row = connection.execute('SELECT sequence,operation_id,receipt_id,request_json,fingerprint,result_json,committed_at FROM resource_operations WHERE operation_id=?', (operation,)).fetchone()
        request, receipt = item['request'], item['receipt']
        request_json, receipt_json = control.canonical(request), control.canonical(receipt)
        if row != (receipt['sequence'], operation, request['receipt_id'], request_json,
                   hashlib.sha256(request_json.encode('ascii')).hexdigest(), receipt_json, receipt['committed_at']):
            raise LifecycleSourceIntegrityError('saved resource original request/receipt mismatch')
        actual = list(connection.execute('SELECT ' + ','.join(ledger._LINK_COLUMNS.split()) + ' FROM resource_record_links WHERE operation_id=? ORDER BY ordinal', (operation,)))
        if actual != ledger._link_rows(request):
            raise LifecycleSourceIntegrityError('saved resource original references mismatch')
        reader.reference_count(len(actual))
        for ref in ledger.references(request):
            stored = _row(reader, 'revisions r LEFT JOIN identities i USING(record_id) LEFT JOIN audit_events a USING(submission_id)',
                'i.kind a.event_id', 'r.record_id=? AND r.revision=?', reports.pin(ref), integers=('a.event_id',))
            if stored[0] != ref['target_kind'] or stored[1] > receipt['scientific_watermark_event_id']:
                raise LifecycleSourceIntegrityError('resource reference exceeds original receipt watermark')
    for key, columns, projector in (('accounts', ledger._ACCOUNT_COLUMNS, ledger._account_row),
                                    ('allocations', ledger._ALLOCATION_COLUMNS, ledger._allocation_row),
                                    ('reservations', ledger._RESERVATION_COLUMNS, ledger._reservation_row)):
        identity = columns.split()[0]
        if key != 'accounts':
            actual_members = {row[0] for row in connection.execute('SELECT r.' + identity + ',r.account_id FROM resource_' +
                key + ' r JOIN resource_operations o ON r.operation_id=o.operation_id WHERE o.sequence<=?', (sequence,))
                if row[1] in selected}
            if actual_members != {item[identity] for item in projection[key]}:
                raise LifecycleSourceIntegrityError('incomplete normalized resource membership')
        for item in projection[key]:
            row = connection.execute('SELECT ' + ','.join(columns.split()) + ' FROM resource_' + key + ' WHERE ' + identity + '=?', (item[identity],)).fetchone()
            if row != projector(item):
                raise LifecycleSourceIntegrityError('saved normalized resource row mismatch')


def _observation_size(packet, inspection, scientific, resource, categories, bindings, observed_at, limits):
    """Measure complete repeated source wrapper before assembling or hashing its retained document."""
    baseline = packet['preparation']['content']['request']['preparation']['start_baseline']
    fragments = {name: source._measure(value, limits.max_source_bytes, limits) for name, value in
        (('binding', packet), ('control', inspection), ('scientific', scientific), ('resources', resource),
         ('baseline', baseline), ('root_categories', categories), ('source_bindings', bindings),
         ('qualifications', source.QUALIFICATIONS))}
    verified_size = operating._array_bytes(operating._object_bytes(digest=66, size=len(str(a['size'])))
                                           for a in scientific['artifacts'])
    return operating._object_bytes(format=control._string_size(source.FORMATS[0]), version=1,
        **fragments, binding_digest=66, observed_at=control._string_size(observed_at),
        verified_artifacts=verified_size, snapshot_id=66, ordinary_work_allowed=5, recheck_required=4)


def _event(observation, artifact, limits, work):
    """Preflight and build the sole source event; no manifest or later output is created."""
    operation = observation['binding']['transition']['content']['request']['operation_id']
    identity = reports.source_id(control.report_operation_id(operation))
    captured = _captured(observation['control'])
    content = {'format': source.FORMATS[1], 'version': 1,
        'request': {'control_operation_id': operation, 'binding_digest': observation['binding_digest']},
        'snapshot_id': observation['snapshot_id'], 'observed_at': observation['observed_at'],
        'scientific_watermark': observation['scientific']['watermark'],
        'resource_sequence': observation['resources'].get('resource_sequence'),
        'captured_control': captured, 'source_artifact': artifact.to_dict()}
    provenance = {'actor': 'lifecycle-source-controller', 'created_at': observation['observed_at'], 'details': {}}
    content_size = source._measure(content, limits.max_submission_bytes, limits)
    provenance_size = source._measure(provenance, limits.max_submission_bytes, limits)
    # DetachedSnapshot has already validated sorted unique records, exact nested
    # envelope bytes and complete distinct artifact inventory.
    record_size = operating._array_bytes(operating._reference_bytes(r['record_id'], r['revision'],
        'lifecycle_source_revision', _strict_json(r['envelope_json'], maximum_depth=65)['kind'])
        for r in observation['scientific']['records'])
    evidence = observation['verified_artifacts']
    if any(a['digest'] == artifact.digest for a in evidence):
        raise LifecycleSourceIntegrityError('source artifact cannot also be its own evidence')
    artifact_size = operating._array_bytes(operating._object_bytes(digest=66, size=len(str(a['size'])))
        for a in (artifact.to_dict(), *evidence))
    size = operating._object_bytes(record_id=control._string_size(identity), revision=1,
        kind=len('"event"'), content=content_size, provenance=provenance_size,
        record_references=record_size, artifact_references=artifact_size,
        operational_status=4, scientific_disposition=4)
    work.reserve(size, 'source event', maximum=limits.max_submission_bytes)
    links = tuple(RecordReference(r['record_id'], r['revision'], 'lifecycle_source_revision',
        _strict_json(r['envelope_json'], maximum_depth=65)['kind']) for r in observation['scientific']['records'])
    artifacts = (artifact, *(ArtifactReference(**a) for a in evidence))
    event = RecordEnvelope(identity, 1, 'event', content, CreationProvenance.from_dict(provenance), links, artifacts)
    return event, size


def _submission(event, event_size, operation, limits, work):
    """Reserve full fingerprint-version wrapper before constructing the one-member CAS submission."""
    sid = source._identity(operation)
    provenance_size = source._measure(event.provenance.to_dict(), limits.max_submission_bytes, limits)
    size = operating._object_bytes(submission_id=control._string_size(sid), provenance=provenance_size,
        records=event_size + 2, expected_heads=2 + control._string_size(event.record_id) + 2)
    wrapper = operating._object_bytes(fingerprint_version=1, submission=size)
    work.reserve(wrapper, 'source submission', maximum=limits.max_submission_bytes)
    submitted = Submission(sid, event.provenance, (event,), {event.record_id: 0})
    canonical = control.canonical({'fingerprint_version': 1, 'submission': submitted.to_dict()})
    if len(canonical) != wrapper:
        raise LifecycleSourceIntegrityError('source submission framing mismatch')
    return submitted, canonical, hashlib.sha256(canonical.encode('ascii')).hexdigest()


def _read_work(limits, work, *, retained_size=0):
    """Retain one streaming slot and 74*S source representations through all later wrapper checks."""
    chunk = 1024 * 1024
    required = chunk + (74 * retained_size if retained_size else 0)
    if retained_size > min(limits.max_input_bytes, limits.max_source_bytes, limits.max_result_bytes):
        raise LifecycleSourceLimitError('source artifact read framing ceiling exceeded')
    work.reserve_charge(required, 'source artifact read')


def commit_lifecycle_source(store, control_operation_id: str, *, expected_binding_digest: str,
                            limits: source.LifecycleSourceLimits) -> source.LifecycleSourceCommitResult:
    """Commit the first coherent source for persisted control intent, or reconcile its exact original.

    Processing budgets are never request identity. The original binding is rebuilt
    from persisted history; no caller packet authenticates itself. Artifact durability
    precedes metadata insertion inside one BEGIN IMMEDIATE transaction. No obligation
    is discharged, current policy evaluated, report rendered, or external work replayed.
    A sampled clock before any captured factual date, including the complete
    resource prefix, raises StateError before source artifact or metadata placement.
    """
    from research_pipeline.store import SubmissionConflictError, RevisionConflictError, _fault as store_fault
    limits = source._limits(limits)
    sid = source._identity(control_operation_id)
    source._digest(expected_binding_digest)
    _store(store)
    work = _Workspace(limits)
    with _errors(), store._transaction(write=True, reconciliation_id='source operation_id ' + sid) as connection:
        reader = controls._Reader(store, connection, limits.control)
        # Original-ID reconciliation precedes capture and clock checks: an exact
        # retry recovers fixed original facts even after clocks or state change.
        saved = _metadata(reader, control_operation_id, limits, work)
        if saved is not None:
            if saved[1].content['request']['binding_digest'] != expected_binding_digest:
                raise SubmissionConflictError('source operation has different original binding input')
            return saved[0]
        _fault('after_first_read')
        found, history, packet, digest = _origin(reader, control_operation_id, limits)
        if digest != expected_binding_digest:
            raise SubmissionConflictError('expected binding differs from persisted original intent')
        event_id = reports.source_id(control.report_operation_id(control_operation_id))
        if reader.head(event_id) is not None:
            raise RevisionConflictError('reserved source event identity is occupied')
        watermark = reader.watermark()
        inspection = controls._inspection(reader, found[1]['request']['run_id'], history, watermark).to_dict()
        resource, complete_resource_time = _resources(connection, store._schema_version, packet, limits)
        _fault('between_resource_and_scientific')
        categories = source._categories(packet, inspection, resource)
        keys = list(dict.fromkeys(reports.pin(ref) for refs in categories.values() for ref in refs))
        original = found[1]['request']['report']['limits']
        if len(keys) > min(limits.scientific.max_roots, original['snapshot']['max_roots']):
            raise LifecycleSourceLimitError('scientific original roots ceiling exceeded')
        selection = SnapshotSelection(RootSelector(*keys[0]), tuple(RootSelector(*key) for key in keys[1:]))
        scientific = store._capture_snapshot(connection, selection, SnapshotLimits(**original['snapshot']),
                                             _source_budget=_ScientificBudget(limits)).to_dict()
        if scientific['watermark'] != watermark or reader.watermark() != watermark:
            raise LifecycleSourceIntegrityError('capture audit watermark changed inside transaction')
        if any(item['receipt']['scientific_watermark_event_id'] > watermark['event_id'] for item in resource.get('operations', [])):
            raise LifecycleSourceIntegrityError('resource receipt exceeds captured scientific watermark')
        bindings = _verify_bindings(store, connection, scientific, _source_context=(reader, limits, work))
        if len(scientific['artifacts']) + 1 > limits.max_artifacts:
            raise LifecycleSourceLimitError('source complete artifact count ceiling exceeded')
        source._artifact_inventory(({'digest': a['digest'], 'size': a['size']} for a in scientific['artifacts']), limits)
        verified = [{'digest': a['digest'], 'size': a['size']} for a in scientific['artifacts']]
        _read_work(limits, work)
        for ref in verified:
            store._artifacts.verify(ArtifactReference(**ref))
        _fault('after_evidence_verification')
        observed_at = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
        if observed_at < source._capture_lower_bound(scientific, inspection,
                resource.get('operations', ()), complete_resource_time):
            raise LifecycleSourceStateError('capture clock precedes captured facts')
        size = _observation_size(packet, inspection, scientific, resource, categories, bindings, observed_at, limits)
        work.reserve(size, 'source observation', maximum=min(limits.max_source_bytes, limits.max_result_bytes, original['max_source_bytes']))
        body = {'format': source.FORMATS[0], 'version': 1, 'binding': packet, 'binding_digest': digest,
            'observed_at': observed_at, 'control': inspection, 'scientific': scientific, 'resources': resource,
            'baseline': packet['preparation']['content']['request']['preparation']['start_baseline'],
            'root_categories': categories, 'source_bindings': bindings, 'verified_artifacts': verified,
            'qualifications': source.QUALIFICATIONS, 'ordinary_work_allowed': False, 'recheck_required': True}
        body['snapshot_id'] = source._hash(body)
        observation = source.LifecycleSourceObservation(body, limits=limits)
        canonical = source.dumps_observation(observation, limits=limits)
        if len(canonical) != size:
            raise LifecycleSourceIntegrityError('source observation framing mismatch')
        artifact = ArtifactReference(hashlib.sha256(canonical.encode('ascii')).hexdigest(), size)
        source._artifact_inventory((artifact.to_dict(), *verified), limits)
        event, event_size = _event(body, artifact, limits, work)
        submitted, request_json, fingerprint = _submission(event, event_size, control_operation_id, limits, work)
        # SQLite signed event IDs need at most 19 digits; canonical UTC commit
        # timestamps need 29 JSON bytes. This is an upper reservation, not a date.
        receipt_size = controls._receipt_size(sid, source._measure(event.provenance.to_dict(), limits.max_result_bytes, limits),
            [(event.record_id, 1)])
        work.reserve(receipt_size, 'source receipt', maximum=limits.max_result_bytes)
        work.reserve(_result_size(event.content, control_operation_id, event.record_id, receipt_size),
            'source result', maximum=limits.max_result_bytes)
        _fault('before_artifacts')
        placed = store.put_artifact(canonical.encode('ascii'))
        if placed != artifact:
            raise LifecycleSourceIntegrityError('source object placement identity mismatch')
        _fault('after_artifacts')
        validate_request_kinds(submitted, store._schema_version)
        store._check_batch(connection, submitted)
        _fault('before_insert')
        receipt = store._insert_submission(connection, submitted, request_json, fingerprint)
        _fault('after_insert')
        result = source.LifecycleSourceCommitResult(_result_document(event, receipt), limits=limits)
    try:
        store_fault('after_commit')
        _fault('after_commit')
    except Exception as error:
        error.add_note('Source acknowledgment uncertain; recover original control operation_id ' + control_operation_id)
        raise
    return result


def get_lifecycle_source_operation(store, control_operation_id: str, *,
                                   limits: source.LifecycleSourceLimits) -> source.LifecycleSourceCommitResult | None:
    """Recover authentic original source metadata, or None for no submission, without opening bytes."""
    limits = source._limits(limits)
    sid = source._identity(control_operation_id)
    _store(store)
    with _errors(), store._transaction(reconciliation_id='source operation_id ' + sid) as connection:
        reader = controls._Reader(store, connection, limits.control)
        found = _metadata(reader, control_operation_id, limits, _Workspace(limits))
        return None if found is None else found[0]


def inspect_lifecycle_source(store, control_operation_id: str, *,
                             limits: source.LifecycleSourceLimits) -> source.LifecycleSourceInspection:
    """Inspect persisted intent and reconciled source state, explicitly leaving artifacts unchecked."""
    limits = source._limits(limits)
    sid = source._identity(control_operation_id)
    _store(store)
    work = _Workspace(limits)
    with _errors(), store._transaction(reconciliation_id='source operation_id ' + sid) as connection:
        reader = controls._Reader(store, connection, limits.control)
        saved = _metadata(reader, control_operation_id, limits, work)
        if saved is None:
            found, _, packet, digest = _origin(reader, control_operation_id, limits)
            obligation = found[2]
        else:
            packet = saved[3]
            digest = saved[1].content['request']['binding_digest']
            obligation = reader.read(reports.pin(packet['obligation']))
        result_size = 4 if saved is None else len(saved[0]._json)
        size = operating._object_bytes(format=control._string_size(source.FORMATS[3]), version=1,
            control_operation_id=control._string_size(control_operation_id), binding_digest=66,
            obligation=reader.envelope_sizes[(obligation.record_id, 1)],
            state=control._string_size('durable_intent' if saved is None else 'committed_source'), result=result_size,
            artifact_verification=len('"not_checked"'), ordinary_work_allowed=5, recheck_required=4)
        work.reserve(size, 'source inspection', maximum=limits.max_result_bytes)
        value = {'format': source.FORMATS[3], 'version': 1, 'control_operation_id': control_operation_id,
            'binding_digest': digest, 'obligation': obligation.to_dict(),
            'state': 'durable_intent' if saved is None else 'committed_source',
            'result': None if saved is None else saved[0].to_dict(limits=limits),
            'artifact_verification': 'not_checked', 'ordinary_work_allowed': False, 'recheck_required': True}
        return source.LifecycleSourceInspection(value, limits=limits)


def read_lifecycle_source(store, control_operation_id: str, *,
                          limits: source.LifecycleSourceLimits) -> source.LifecycleSourceObservation:
    """Verify saved source bytes, original evidence and complete-prefix chronology.

    Uses the saved observed_at and resource sequence, without recapturing current
    state; inconsistent historical receipts raise LifecycleSourceIntegrityError.
    """
    from research_pipeline.store import RecordNotFoundError
    limits = source._limits(limits)
    sid = source._identity(control_operation_id)
    _store(store)
    work = _Workspace(limits)
    with _errors(), store._transaction(reconciliation_id='source operation_id ' + sid) as connection:
        reader = controls._Reader(store, connection, limits.control)
        found = _metadata(reader, control_operation_id, limits, work)
        if found is None:
            # Distinguish absent original control from durable intent without bytes.
            _origin(reader, control_operation_id, limits)
            raise RecordNotFoundError('lifecycle source is not committed')
        _, event, _, packet = found
        refs = [a.to_dict() for a in event.artifact_references]
        source._artifact_inventory(refs, limits)
        artifact = event.artifact_references[0]
        _read_work(limits, work, retained_size=artifact.size)
        data = store.read_artifact(artifact)
        try:
            observation = source.loads_observation(data, limits=limits)
        except LifecycleSourceValidationError:
            raise LifecycleSourceIntegrityError('invalid committed source object content') from None
        text = source.dumps_observation(observation, limits=limits)
        if text.encode('ascii') != data:
            raise LifecycleSourceIntegrityError('source object is not byte-for-byte canonical')
        value = observation.to_dict(limits=limits)
        if value['binding'] != packet:
            raise LifecycleSourceIntegrityError('saved observation binding differs from persisted originals')
        rebuilt, _ = _event(value, artifact, limits, work)
        if rebuilt.to_dict() != event.to_dict():
            raise LifecycleSourceIntegrityError('saved observation differs from committed source projections')
        _verify_bindings(store, connection, value['scientific'], expected=value['source_bindings'],
                         _source_context=(reader, limits, work))
        _resource_originals(reader, value['resources'], value['observed_at'], limits)
        for reference in event.artifact_references[1:]:
            store._artifacts.verify(reference)
        return observation
