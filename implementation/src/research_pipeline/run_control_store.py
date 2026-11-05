"""Connection-owned durable control history and bounded metadata-only recovery."""

from contextlib import contextmanager
import hashlib

from research_pipeline import run_control as control, operating_authority as authority
from research_pipeline import operating_authority_store as operating, reports
from research_pipeline.domain import (
    RecordEnvelope, RecordReference, CreationProvenance,
    Submission, SubmissionReceipt, _identifier, _integer,
)
from research_pipeline.report_capture import _text_length, _integer_length
from research_pipeline.schema import validate_request_kinds
from research_pipeline.run_control import (
    RunControlValidationError, RunControlIntegrityError, RunControlLimitError,
    RunControlStateError, RunControlPermissionError,
)


def _fault(boundary):
    """Expose deterministic snapshot and post-commit test seams without a public bypass."""


@contextmanager
def _errors():
    """Translate shared bounded-reader errors without disguising storage failures as denial."""
    try:
        yield
    except authority.AuthorityLimitError:
        raise RunControlLimitError('control aggregate authority allowance exceeded') from None
    except authority.AuthorityIntegrityError:
        raise RunControlIntegrityError('inconsistent stored authority metadata') from None


def _stored(raw, maximum):
    """Decode only preflighted canonical stored JSON, sanitizing corruption diagnostics."""
    try:
        value = control.strict_json(raw, maximum)
        if control.canonical(value) != raw:
            raise ValueError
        return value
    except RunControlLimitError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise RunControlIntegrityError('malformed stored control JSON') from None


class _Reader(operating._Reader):
    """Reuse aggregate authority accounting while preserving control's independent JSON depth."""

    def __init__(self, store, connection, limits):
        """Initialize one transaction's shared reader and validated lifecycle caches."""
        super().__init__(store, connection, limits.metadata)
        self.control_limits = limits
        self.controls = {}
        self.prefixes = {}
        self.visiting = set()
        self.bindings = set()
        self.envelope_shapes = {}
        self.receipt_sizes = {}

    def check_result_size(self, size):
        """Bound nested authority results before construction independently of control output."""
        if size > self.limits.max_result_bytes:
            raise authority.AuthorityLimitError('authority detached result byte limit exceeded')

    def preflight(self, key, *, maximum=None):
        """Check actual role-specific SQL content lengths before any saved member is decoded."""
        if key not in self.preflighted or maximum is not None:
            lengths = self.connection.execute('SELECT ' + _text_length('content_json') +
                ' FROM revisions WHERE record_id=? AND revision=?', key).fetchone()
            operating._length(lengths)
            maximum = maximum if maximum is not None else (control.SMALL_BYTES if key[0].startswith('run-control-obligation-') else
                       control.TRANSITION_BYTES if key[0].startswith('run-control-') else
                       self.limits.max_record_bytes)
            if lengths[0] > min(maximum, self.limits.max_record_bytes):
                raise RunControlLimitError('stored control member content byte limit exceeded')
        return super().preflight(key)

    def _before_envelope(self, key, row, content, provenance, links, artifacts):
        """Measure complete enclosing fields before the shared reader constructs an envelope."""
        size = operating._object_bytes(record_id=control._string_size(key[0]), revision=len(str(key[1])),
            kind=control._string_size(row[0]), content=control.bounded_size(content, self.limits.max_record_bytes),
            provenance=control.bounded_size(provenance, self.limits.max_record_bytes),
            record_references=operating._array_bytes(operating._reference_bytes(
                ref.record_id, ref.revision, ref.relationship, ref.target_kind) for ref in links),
            artifact_references=operating._array_bytes(operating._object_bytes(digest=66, size=len(str(ref.size))) for ref in artifacts),
            operational_status=operating._fragment_bytes(row[3]), scientific_disposition=operating._fragment_bytes(row[4]))
        maximum = control.TRANSITION_BYTES if key[0].startswith('run-control-') else authority.ENVELOPE_BYTES
        if size > min(maximum, self.limits.max_record_bytes):
            raise authority.AuthorityLimitError('stored enclosing envelope byte limit exceeded')

    def read(self, key):
        """Reserve detached parse/measurement scratch for uncached envelope reconstruction."""
        retained = self.preflight(key)
        if key in self.envelopes:
            return self.envelopes[key]
        with self.temporary(retained * 3):
            return super().read(key)

    def digest(self, envelope):
        """Hash already validated transaction-local envelopes with charged detached/ASCII copies."""
        key = envelope.record_id, envelope.revision
        size = self.envelope_sizes[key]
        with self.temporary(size * 3):
            return hashlib.sha256(control.canonical(envelope.to_dict()).encode('ascii')).hexdigest()

    def retain_typed(self, envelope):
        """Charge each actual typed reconstruction even when its record identity was already counted."""
        self.reserve(len(envelope._content_json))
        self.typed.add((envelope.record_id, envelope.revision))

    def output(self, value):
        """Charge authority's detached validation and canonical output copies under this same reader."""
        size = len(value._json)
        self.check_result_size(size)
        with self.temporary(size * 2):
            return super().output(value)

    def _stored_json(self, raw):
        """Use control's wrapper depth while keeping stored canonical and byte checks strict."""
        return _stored(raw, self.limits.max_record_bytes)

    def _envelope_size(self, envelope):
        """Apply control's independent wrapper bound through the shared reconstruction path."""
        try:
            size, nodes, depth = control._measure_json(envelope.to_dict(), self.limits.max_record_bytes)
            self.envelope_shapes[(envelope.record_id, envelope.revision)] = nodes, depth
            return size
        except RunControlLimitError:
            raise authority.AuthorityLimitError('control envelope byte limit exceeded') from None


def _reserve_result(reader, size, maximum):
    """Reserve an independent detached result before its constructor or wire copy runs."""
    if size > min(maximum, reader.control_limits.max_result_bytes):
        raise RunControlLimitError('control detached result byte limit exceeded')
    reader.reserve(size)


def _result_size(transition, obligation, receipt_size, value):
    """Measure result framing using validated reference fragments and a preflighted receipt size."""
    request = value['request']
    return operating._object_bytes(format=len('"research_pipeline.run_control_commit_result"'), version=1,
        operation_id=control._string_size(request['operation_id']),
        transition=operating._reference_bytes(transition.record_id, transition.revision, 'run_control', 'event'),
        transition_digest=66, obligation=operating._reference_bytes(obligation.record_id, 1, 'required_report', 'event'),
        obligation_digest=66, disposition=control._string_size(value['disposition']),
        report_state=len('"pending_capture"'), report_source=4, report_plan_id=4,
        ordinary_work_allowed=5, recheck_required=4, receipt=receipt_size)


def _receipt_size(operation, provenance_size, members, event_size=19, timestamp_size=29):
    """Bound original receipt construction, including SQLite event and timestamp upper bounds."""
    return operating._object_bytes(submission_id=control._string_size(operation), fingerprint=66,
        event_id=event_size, committed_at=timestamp_size, provenance=provenance_size,
        revisions=operating._array_bytes(operating._array_bytes((control._string_size(identity), len(str(revision))))
            for identity, revision in members))


def _result(transition, obligation, receipt, value, *, digests):
    """Construct already-reserved immutable original evidence with a permanently closed work gate."""
    return control.RunControlCommitResult({'format': 'research_pipeline.run_control_commit_result', 'version': 1,
        'operation_id': receipt.submission_id,
        'transition': control.reference(transition.record_id, transition.revision, 'run_control'),
        'transition_digest': digests[0],
        'obligation': control.reference(obligation.record_id, 1, 'required_report'),
        'obligation_digest': digests[1], 'disposition': value['disposition'],
        'report_state': 'pending_capture', 'report_source': None, 'report_plan_id': None,
        'ordinary_work_allowed': False, 'recheck_required': True, 'receipt': receipt.to_dict()})


def _submission(transition, obligation, request):
    """Form the sole two-member lifecycle batch with exact CAS and shared provenance."""
    return Submission(request['operation_id'], transition.provenance, (transition, obligation),
        {transition.record_id: transition.revision - 1, obligation.record_id: 0})


def _operation(reader, operation_id):
    """Reconcile actual two-member membership, projections, audit, fingerprint and original receipt.

    This local cache certifies the original batch only; callers additionally validate
    its immutable preparation/predecessor prefix. No current heads or trust enter recovery.
    """
    from research_pipeline.store import SubmissionConflictError
    if operation_id in reader.controls:
        return reader.controls[operation_id]
    connection = reader.connection
    lengths = connection.execute('SELECT ' + _text_length('request_json') + ',' + _text_length('fingerprint') +
        ' FROM submissions WHERE submission_id=?', (operation_id,)).fetchone()
    if lengths is None:
        return None
    operating._length(lengths)
    if lengths[0] > control.SUBMISSION_BYTES:
        raise RunControlLimitError('original control submission byte limit exceeded')
    if lengths[1] != 64:
        raise RunControlIntegrityError('invalid original fingerprint')
    # Actual members and top-level envelope discriminators identify lifecycle
    # operations. Descriptive nested strings never confer controller ownership.
    count = connection.execute('SELECT count(*) FROM revisions WHERE submission_id=?', (operation_id,)).fetchone()[0]
    if count > reader.limits.max_records:
        raise RunControlLimitError('operation membership exceeds record allowance')
    cursor = connection.execute('SELECT ' + ','.join((_text_length('record_id'), _integer_length('revision', 1), _integer_length('ordinal'))) +
        ' FROM revisions WHERE submission_id=? ORDER BY ordinal', (operation_id,))
    for row in cursor:
        size = operating._length(row)
        if size > reader.limits.max_record_bytes:
            raise RunControlLimitError('member metadata byte limit exceeded')
        reader.reserve(size)
    members = list(connection.execute('SELECT record_id,revision,ordinal FROM revisions WHERE submission_id=? ORDER BY ordinal', (operation_id,)))
    lifecycle = any(type(member[0]) is str and member[0].startswith('run-control-') for member in members)
    for index, member in enumerate(members):
        try:
            _identifier(member[0], 'member')
            _integer(member[1], 'revision', 1)
        except ValueError:
            raise RunControlIntegrityError('invalid lifecycle membership') from None
        lifecycle |= member[0].startswith('run-control-')
        reader.preflight(member[:2], maximum=(control.TRANSITION_BYTES if index == 0 else control.SMALL_BYTES)
            if lifecycle and count == 2 else None)
    columns = (_integer_length('event_id', 1), _text_length('committed_at'), _text_length('provenance_json'),
               _text_length('event_type'), _text_length('submission_id'))
    audit = connection.execute('SELECT ' + ','.join(columns) + ' FROM audit_events WHERE submission_id=?', (operation_id,)).fetchone()
    size = operating._length(audit)
    if size > reader.limits.max_record_bytes:
        raise RunControlLimitError('audit metadata byte limit exceeded')
    reader.reserve(size + audit[2])
    # Fetch and parse only after role-specific content and membership preflight.
    # Raw, decoded, reconstructed submission and codec scratch copies are distinct.
    reader.reserve(sum(lengths) + lengths[0])
    raw, fingerprint = connection.execute('SELECT request_json,fingerprint FROM submissions WHERE submission_id=?', (operation_id,)).fetchone()
    with reader.temporary(lengths[0]):
        saved = _stored(raw, control.SUBMISSION_BYTES)
    saved_submission = saved.get('submission') if type(saved) is dict else None
    saved_members = saved_submission.get('records') if type(saved_submission) is dict else None
    if type(saved_members) is list:
        lifecycle |= any(type(item) is dict and (
            type(item.get('record_id')) is str and item['record_id'].startswith('run-control-') or
            type(item.get('content')) is dict and item['content'].get('format') in control.FORMATS)
            for item in saved_members)
    if not lifecycle:
        for member in members:
            envelope = reader.read(member[:2])
            with reader.temporary(len(envelope._content_json)):
                lifecycle |= envelope.content.get('format') in control.FORMATS
    if not lifecycle:
        raise SubmissionConflictError('operation identity belongs to another submission type')
    if count != 2 or [member[2] for member in members] != [0, 1]:
        raise RunControlIntegrityError('lifecycle requires two ordered actual members')
    reader.reserve(2 * lengths[0])
    with reader.temporary(lengths[0] * 6):
        try:
            authority.exact(saved, 'fingerprint_version submission')
            if type(saved['fingerprint_version']) is not int or saved['fingerprint_version'] != 1:
                raise ValueError
            members_wire = saved['submission']['records']
            if type(members_wire) is not list or len(members_wire) != 2:
                raise ValueError
            for index, member_wire in enumerate(members_wire):
                control.bounded_size(member_wire, min(control.TRANSITION_BYTES, reader.limits.max_record_bytes))
                control.bounded_size(member_wire['content'], control.TRANSITION_BYTES if index == 0 else control.SMALL_BYTES)
            submitted = Submission.from_dict(saved['submission'])
            if len(submitted.records) != 2 or submitted.submission_id != operation_id:
                raise ValueError
            transition, obligation = submitted.records
            value = control.decode_transition(transition).to_dict()
            control.paired_obligation(value, transition, obligation)
            obligation_head = reader.head(obligation.record_id)
            obligation_count = connection.execute('SELECT count(*) FROM revisions WHERE record_id=?', (obligation.record_id,)).fetchone()[0]
            if obligation_head != {'record_id': obligation.record_id, 'revision': 1, 'kind': 'event'} or obligation_count != 1:
                raise ValueError
            if (submitted.provenance != transition.provenance or
                    submitted.expected_heads != {transition.record_id: transition.revision - 1, obligation.record_id: 0} or
                    saved['submission'] != submitted.to_dict() or hashlib.sha256(raw.encode('ascii')).hexdigest() != fingerprint or
                    members != [(record.record_id, record.revision, ordinal) for ordinal, record in enumerate(submitted.records)]):
                raise ValueError
            event_id, timestamp, provenance, event_type, sid = connection.execute('''SELECT event_id,committed_at,
                provenance_json,event_type,submission_id FROM audit_events WHERE submission_id=?''', (operation_id,)).fetchone()
            provenance = _stored(provenance, reader.limits.max_record_bytes)
            if event_type != 'submission_committed' or sid != operation_id or provenance != submitted.provenance.to_dict():
                raise ValueError
            for expected in submitted.records:
                key = expected.record_id, expected.revision
                actual = reader.read(key)
                if actual.to_dict() != expected.to_dict() or reader.submission_ids[key] != operation_id:
                    raise ValueError
                for ref in actual.record_references:
                    reader.shallow(ref)
            receipt_size = _receipt_size(operation_id, audit[2], [member[:2] for member in members], audit[0], control._string_size(timestamp))
            reader.reserve(receipt_size)
            _reserve_result(reader, _result_size(transition, obligation, receipt_size, value), control.SMALL_BYTES)
            receipt = SubmissionReceipt(operation_id, fingerprint, event_id, timestamp,
                CreationProvenance.from_dict(provenance), tuple(member[:2] for member in members))
            if receipt.committed_at != timestamp:
                raise ValueError
            result = _result(transition, obligation, receipt, value,
                digests=(reader.digest(transition), reader.digest(obligation)))
        except RunControlLimitError:
            raise
        except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as error:
            if isinstance(error, (authority.AuthorityLimitError, authority.AuthorityIntegrityError)):
                raise
            raise RunControlIntegrityError('inconsistent original lifecycle submission') from None
    found = transition, value, obligation, receipt, result
    reader.receipt_sizes[operation_id] = receipt_size
    reader.controls[operation_id] = found
    return found


def _run(reader, request, preparation, *, current=False):
    """Validate the explicitly selected generic run and stable project; never advance implicitly."""
    envelope = reader.read((request['run_id'], request['run_revision']))
    if envelope.kind != 'run' or not any(ref.target_kind == 'project' and ref.record_id == preparation['project']['record_id']
            for ref in envelope.record_references):
        raise RunControlStateError('selected run lacks the prepared project reference')
    for ref in envelope.record_references:
        if ref.target_kind == 'project' and ref.record_id == preparation['project']['record_id']:
            reader.shallow(ref)
    if current and reader.head(request['run_id'])['revision'] != request['run_revision']:
        raise RunControlStateError('preparation or continuation requires the explicitly selected current run revision')


def _binding_matches(preparation, decision):
    """Compare exact dossier pins and full approved scope without inventing account availability."""
    binding = decision['binding']
    return (binding['project'] == preparation['project'] and
        all(binding['dossier'][name] == preparation[name] for name in ('initial_corpus', 'current_corpus', 'context')) and
        decision['scope'] == preparation['operating_scope'] and decision['authority_domain'] == preparation['authority_domain'])


def _historical_authorization(reader, transition, preparation, receipt):
    """Verify historical authorization through the shared reserved decoder, without current trust or bytes."""
    auth = transition['authorization']
    if auth is None:
        return
    columns = (_integer_length('a.event_id', 1), _text_length('a.submission_id'),
        _text_length('a.committed_at'), _text_length('s.fingerprint'))
    sql = ''' FROM audit_events a JOIN submissions s USING(submission_id)
        WHERE a.event_id<? ORDER BY a.event_id DESC LIMIT 1'''
    lengths = reader.connection.execute('SELECT ' + ','.join(columns) + sql, (receipt.event_id,)).fetchone()
    expected_watermark = dict.fromkeys(('event_id', 'submission_id', 'committed_at', 'fingerprint'))
    if lengths is not None:
        reader.reserve(operating._length(lengths))
        row = reader.connection.execute('SELECT a.event_id,a.submission_id,a.committed_at,s.fingerprint' + sql,
            (receipt.event_id,)).fetchone()
        expected_watermark = dict(zip(expected_watermark, row))
    if auth['watermark'] != expected_watermark:
        raise RunControlIntegrityError('authorization watermark differs from its pre-write audit prefix')
    pin = auth['decision']
    selected = reader.connection.execute('''SELECT CASE WHEN typeof(r.revision)='integer' THEN r.revision ELSE NULL END
        FROM revisions r JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND a.event_id<?
        ORDER BY r.revision DESC LIMIT 1''', (pin['reference']['record_id'], receipt.event_id)).fetchone()
    if selected is None or type(selected[0]) is not int or selected[0] != pin['reference']['revision']:
        raise RunControlIntegrityError('authorization was not the latest decision at its recorded watermark')
    key = authority.pin(pin['reference'])
    reader.history_count(key)
    envelope = reader.read(key)
    signed, decision = reader.decode_authority(envelope)
    found = operating._operation(reader, decision['operation_id'])
    if (found is None or found[1] != signed or reader.digest(envelope) != pin['envelope_digest'] or
            decision['outcome'] != 'approve' or not _binding_matches(preparation, decision) or
            not decision['valid_from'] <= auth['evaluated_at'] < decision['valid_until']):
        raise RunControlIntegrityError('stored authorization differs from prepared binding')
    if key not in reader.bindings:
        if key[1] > reader.limits.max_decisions:
            raise RunControlLimitError('historical authority prefix exceeds decision allowance')
        previous = None
        for revision in range(1, key[1] + 1):
            selected_key = key[0], revision
            reader.history_count(selected_key)
            selected_envelope = reader.read(selected_key)
            selected_signed, selected_decision = reader.decode_authority(selected_envelope)
            selected_operation = operating._operation(reader, selected_decision['operation_id'])
            if selected_operation is None or selected_operation[1] != selected_signed:
                raise RunControlIntegrityError('historical authority operation mismatch')
            if previous is not None and (
                    selected_decision['predecessor']['envelope_digest'] != reader.digest(previous[0]) or
                    selected_decision['outcome'] != 'approve' and selected_decision['binding'] != previous[1]['binding']):
                raise RunControlIntegrityError('historical authority predecessor mismatch')
            previous = selected_envelope, selected_decision
        # Resolve exact immutable metadata, not current watched heads or artifact
        # bytes. The signed binding includes all selected dossier digests.
        bound, _, _, _ = operating._resolve(reader,
            RecordReference.from_dict(decision['binding']['project']), decision['scope'])
        if bound.to_dict() != decision['binding']:
            raise RunControlIntegrityError('prepared dossier metadata differs from signed evidence')
        reader.bindings.add(key)


def _history(reader, identity, *, through=None):
    """Validate a complete current stream or immutable original prefix with cached ordered pairs."""
    from research_pipeline.store import SubmissionConflictError
    key = identity, through
    if key in reader.prefixes:
        return reader.prefixes[key]
    if key in reader.visiting:
        raise RunControlIntegrityError('cyclic previous-run history')
    reader.visiting.add(key)
    try:
        if through is None:
            head = reader.head(identity)
            if head is None:
                return []
            count = reader.connection.execute('SELECT count(*) FROM revisions WHERE record_id=?', (identity,)).fetchone()[0]
            if head['kind'] != 'event' or count != head['revision']:
                raise RunControlIntegrityError('control stream head/count mismatch')
            through = head['revision']
        limits = reader.control_limits
        if through > min(limits.max_transitions, limits.max_pending_reports, 1024):
            raise RunControlLimitError('complete control history or pending count exceeds allowance')
        result, previous, preparation = [], None, None
        for revision in range(1, through + 1):
            record_key = identity, revision
            reader.history_count(record_key)
            envelope = reader.read(record_key)
            with reader.temporary(len(envelope._content_json)):
                content = envelope.content
                found = _operation(reader, content['request']['operation_id'])
                del content
            transition = found[1] if found is not None else None
            if found is None or found[0] != envelope:
                raise RunControlIntegrityError('control history operation mismatch')
            scratch = reader.envelope_sizes[record_key] * 6
            with reader.temporary(scratch):
                control.validate_successor(previous, transition)
            request = transition['request']
            if revision > control.capacity(request['action']):
                raise RunControlIntegrityError('control history exceeded reserved terminal capacity')
            if revision == 1:
                preparation = request['preparation']
                _anchors(reader, preparation)
                prior = preparation['previous_run']
                if prior is not None:
                    linked = _history(reader, prior['reference']['record_id'], through=prior['reference']['revision'])
                    original = linked[0][1]['request']['preparation']
                    if (reader.digest(linked[-1][0]) != prior['envelope_digest'] or
                            original['project']['record_id'] != preparation['project']['record_id'] or
                            original['allocation']['allocation_id'] == preparation['allocation']['allocation_id']):
                        raise RunControlIntegrityError('replacement linkage differs from declared history')
            _run(reader, request, preparation)
            _historical_authorization(reader, transition, preparation, found[3])
            if request['action'] == 'continue':
                # No public acknowledgment route exists in this foundation.
                raise RunControlIntegrityError('stored continuation bypasses pending mandatory reports')
            result.append(found)
            previous = envelope, transition
        reader.prefixes[key] = result
        return result
    except (KeyError, TypeError, RunControlValidationError, RunControlStateError, authority.AuthorityValidationError,
            authority.AuthorityReadinessError, SubmissionConflictError):
        raise RunControlIntegrityError('invalid stored control history') from None
    finally:
        reader.visiting.remove(key)


def _row(reader, table, columns, where, arguments, *, integers=(), nullable=()):
    """Preflight a fixed selected metadata row before fetching any variable-sized values."""
    names = columns.split()
    expressions = [_integer_length(name, 0 if name == 'ordinal' else 1) if name in integers else _text_length(name, nullable=name in nullable) for name in names]
    lengths = reader.connection.execute('SELECT ' + ','.join(expressions) + ' FROM ' + table + ' WHERE ' + where, arguments).fetchone()
    size = operating._length(lengths)
    if any(length > 65536 for name, length in zip(names, lengths) if name in ('request_json', 'result_json')):
        raise RunControlLimitError('resource request or receipt byte limit exceeded')
    if size > reader.limits.max_record_bytes:
        raise RunControlLimitError('resource anchor metadata byte limit exceeded')
    reader.reserve(size * 3)
    return reader.connection.execute('SELECT ' + ','.join(names) + ' FROM ' + table + ' WHERE ' + where, arguments).fetchone()


def _anchors(reader, preparation):
    """Validate two original record-scoped resource anchors without replaying or mutating the ledger."""
    from research_pipeline import resources, resource_ledger as ledger
    allocation = preparation['allocation']
    declared = preparation['operating_scope']['resources']
    project = None
    project_sequence = None
    for name, kind in (('project_account', 'project'), ('run_account', 'run')):
        anchor = allocation[name]
        if 'account_id' not in anchor:
            continue
        if reader.store._schema_version not in (3, 4):
            raise RunControlStateError('schema 2 requires explicitly unavailable resource accounts')
        raw = _row(reader, 'resource_operations', 'sequence operation_id receipt_id request_json fingerprint result_json committed_at',
            'operation_id=?', (anchor['operation_id'],), integers=('sequence',))
        try:
            request = resources.loads_request(raw[3])
            value = request.to_dict()
            receipt = resources.loads_receipt(raw[5])
            receipt_value = receipt.to_dict()
            authority.timestamp(raw[6])
            watermark = receipt_value['scientific_watermark_event_id']
            if watermark and reader.connection.execute('SELECT 1 FROM audit_events WHERE event_id=?', (watermark,)).fetchone() is None:
                raise RunControlIntegrityError('resource receipt names a missing scientific watermark')
            if (resources.canonical(value) != raw[3] or resources.canonical(receipt_value) != raw[5] or
                    request.fingerprint != raw[4] or value['operation_id'] != raw[1] or value['receipt_id'] != raw[2] or
                    ledger._receipt(value, raw[4], raw[0], raw[6], receipt_value['scientific_watermark_event_id']) != receipt):
                raise ValueError
            payload = value['payload']
            if (value['kind'] != ('create_account' if kind == 'project' else 'allocate') or
                    payload['account_id'] != anchor['account_id'] or
                    payload['scope'] != {'type': 'record', 'kind': kind, 'reference': anchor['anchor']}):
                raise RunControlStateError('resource account does not match exact preparation anchor')
            if kind == 'project':
                account = {'account_id': payload['account_id'], 'operation_id': raw[1], 'owner_id': payload['owner_id'],
                    'scope': payload['scope'], 'parent_account_id': None, 'dimensions': payload['dimensions'],
                    'limits': payload['ceiling'], 'policy': payload['policy']}
                project = account
                project_sequence = raw[0]
            else:
                if (project is None or raw[0] <= project_sequence or payload['parent_account_id'] != project['account_id'] or
                        payload['owner_id'] != project['owner_id'] or payload['allocation_id'] != allocation['allocation_id']):
                    raise RunControlStateError('run allocation or project owner mismatch')
                account = {'account_id': payload['account_id'], 'operation_id': raw[1], 'owner_id': payload['owner_id'],
                    'scope': payload['scope'], 'parent_account_id': project['account_id'], 'dimensions': project['dimensions'],
                    'limits': payload['purpose_limits'], 'policy': payload['run_policy']}
                expected = {'allocation_id': payload['allocation_id'], 'operation_id': raw[1],
                    'parent_account_id': project['account_id'], 'account_id': payload['account_id'], 'purpose_limits': payload['purpose_limits']}
                actual = _row(reader, 'resource_allocations', ledger._ALLOCATION_COLUMNS,
                    'allocation_id=?', (allocation['allocation_id'],))
                if actual != ledger._allocation_row(expected):
                    raise RunControlIntegrityError('resource allocation projection mismatch')
                if account['limits'] != declared['purpose_limits'] or account['policy'] != declared['run_policy']:
                    raise RunControlStateError('run resource declaration differs from scope')
            if account['dimensions'] != declared['dimensions']:
                raise RunControlStateError('resource dimensions differ from scope')
            actual = _row(reader, 'resource_accounts', ledger._ACCOUNT_COLUMNS,
                'account_id=?', (anchor['account_id'],), nullable=('parent_account_id',))
            if actual != ledger._account_row(account):
                raise RunControlIntegrityError('resource account projection mismatch')
            expected_links = ledger._link_rows(value)
            count = reader.connection.execute('SELECT count(*) FROM resource_record_links WHERE operation_id=?', (raw[1],)).fetchone()[0]
            if count != len(expected_links):
                raise RunControlIntegrityError('resource anchor link count mismatch')
            reader.reference_count(count)
            for ordinal, expected in enumerate(expected_links):
                actual = _row(reader, 'resource_record_links', ledger._LINK_COLUMNS,
                    'operation_id=? AND ordinal=?', (raw[1], ordinal), integers=('ordinal', 'target_revision'))
                if actual != tuple(expected):
                    raise RunControlIntegrityError('resource anchor link projection mismatch')
                ref = RecordReference(*actual[2:])
                reader.shallow(ref)
                metadata = reader.connection.execute('SELECT ' + _integer_length('a.event_id', 1) + ''' FROM revisions r
                    JOIN audit_events a USING(submission_id) WHERE r.record_id=? AND r.revision=?''',
                    (ref.record_id, ref.revision)).fetchone()
                reader.reserve(operating._length(metadata))
                event_id = reader.connection.execute('''SELECT a.event_id FROM revisions r JOIN audit_events a USING(submission_id)
                    WHERE r.record_id=? AND r.revision=?''', (ref.record_id, ref.revision)).fetchone()[0]
                if event_id > receipt_value['scientific_watermark_event_id']:
                    raise RunControlIntegrityError('resource anchor link is newer than its receipt watermark')
        except (RunControlStateError, RunControlLimitError, authority.AuthorityLimitError, authority.AuthorityIntegrityError):
            raise
        except (ValueError, KeyError, TypeError):
            raise RunControlIntegrityError('malformed resource anchor operation') from None


def _authorize(reader, request, preparation, policy, evaluated_at, original=None):
    """Reevaluate actual latest authority inside the same write transaction before pending denial."""
    try:
        authority.timestamp(evaluated_at)
    except authority.AuthorityValidationError:
        raise RunControlPermissionError('current authority requires valid explicit evaluation time') from None
    if evaluated_at < request['transitioned_at']:
        raise RunControlPermissionError('current evaluation precedes transition time')
    evaluated = operating._evaluate_eligibility(reader, preparation['authority_domain'], preparation['project']['record_id'],
        purpose=preparation['purpose'], policy=policy, evaluated_at=evaluated_at)
    reader.reserve(len(evaluated._json) * 2)
    result = evaluated.to_dict()
    if not result['eligible']:
        raise RunControlPermissionError('current authority status: ' + result['status'])
    expected = request['expected_authority']
    actual = result['history_signatures'][-1]
    selected = reader.envelopes[authority.pin(result['decision'])]
    reader.reserve(len(selected._content_json))
    decision = selected.content['decision']
    if (expected['reference'] != result['decision'] or expected['envelope_digest'] != actual['envelope_digest'] or
            not _binding_matches(preparation, decision)):
        raise RunControlPermissionError('current authority differs from prepared scope or expected decision')
    if original is not None and result['policy_fingerprint'] != original['authorization']['policy_fingerprint']:
        raise RunControlPermissionError('continuation changes prepared public policy')
    return {'decision': expected, 'evaluated_at': result['evaluated_at'],
            'policy_fingerprint': result['policy_fingerprint'], 'watermark': result['watermark']}


def _reserved_source(connection, identity):
    """Check conservative source ownership using an exact canonical token without decoding histories."""
    token = '"report_source_id":' + control.canonical(identity)
    return connection.execute('''SELECT 1 FROM revisions WHERE record_id GLOB 'run-control-obligation-*'
        AND typeof(content_json)='text' AND instr(content_json,?)>0 LIMIT 1''', (token,)).fetchone() is not None


def _managed_manifest(connection, identity):
    """Map the shared run digest directly to conservative control ownership."""
    if not identity.startswith('run-report-'):
        return False
    return connection.execute('SELECT 1 FROM identities WHERE record_id=?',
        ('run-control-' + identity[len('run-report-'):],)).fetchone() is not None


def guard_fresh(connection, operation_id, records=()):
    """Reject fresh public writes into lifecycle and controlled-report reservations after reconciliation."""
    if operation_id.startswith(('run-control-report-', 'run-control-source-')):
        raise RunControlStateError('report operation identity is reserved for controlled reporting')
    for record in records:
        if (record.record_id.startswith('run-control-') or record.content.get('format') in control.FORMATS + (
                'research_pipeline.lifecycle_source_observation', 'research_pipeline.lifecycle_source_event',
                'research_pipeline.lifecycle_source_commit_result', 'research_pipeline.lifecycle_source_inspection') or
                _managed_manifest(connection, record.record_id) or _reserved_source(connection, record.record_id)):
            raise RunControlStateError('record identity or format is owned by run control')


def guard_report(connection, request):
    """Reject fresh managed legacy reports before capture, rendering or object placement."""
    guard_fresh(connection, request['operation_id'])
    if (_managed_manifest(connection, reports.manifest_id(request['run']['record_id'])) or
            _reserved_source(connection, reports.source_id(request['operation_id']))):
        raise RunControlStateError('controlled run reports require the future obligation lifecycle')


def _fresh_reservations(reader, request):
    """Reserve S/O submissions, E/X events and the initial manifest before creating an obligation."""
    connection = reader.connection
    operation = control.report_operation_id(request['operation_id'])
    source = control._identity('run-control-source-', request['operation_id'])
    output = control._identity('run-control-output-', request['operation_id'])
    if (connection.execute('SELECT 1 FROM submissions WHERE submission_id=?', (source,)).fetchone() is not None or
            connection.execute('SELECT 1 FROM identities WHERE record_id=?', (output,)).fetchone() is not None or
            connection.execute('SELECT 1 FROM submissions WHERE submission_id=?', (operation,)).fetchone() is not None or
            connection.execute('SELECT 1 FROM identities WHERE record_id=?', (reports.source_id(operation),)).fetchone() is not None):
        raise RunControlStateError('future report identity already occupied')
    if request['action'] == 'prepare' and connection.execute('SELECT 1 FROM identities WHERE record_id=?',
            (reports.manifest_id(request['run_id']),)).fetchone() is not None:
        raise RunControlStateError('preparation cannot adopt an existing legacy report stream')


def _fresh_envelope(reader, value, *, actor, obligation=False):
    """Preflight enclosing bytes, nodes, depth and link occurrences before fresh event allocation."""
    request = value if obligation else value['request']
    content_size, content_nodes, content_depth = control._measure_json(
        value, control.SMALL_BYTES if obligation else control.TRANSITION_BYTES)
    timestamp = request['required_at'] if obligation else request['transitioned_at']
    identity = control.obligation_id(request['operation_id']) if obligation else control.control_id(request['run_id'])
    revision = 1 if obligation else request['revision']
    provenance_size = operating._object_bytes(actor=control._string_size(actor),
        created_at=control._string_size(timestamp), details=2)
    def references():
        """Yield validated references without retaining a projection collection."""
        if obligation:
            yield value['transition']
            yield from value['selection']
        else:
            yield from control._transition_references(value)
    count = sum(1 for _ in references())
    reader.reference_count(count)
    # Fixed envelope/provenance fields contribute 12 nodes; each projected
    # reference contributes its object and four values, including repeated roles.
    nodes, depth = content_nodes + 12 + 5 * count, max(content_depth + 1, 3)
    if nodes > control.JSON_NODES or depth > control.JSON_DEPTH:
        raise RunControlLimitError('fresh enclosing envelope JSON node or depth limit exceeded')
    link_size = operating._array_bytes(operating._fragment_bytes(ref) for ref in references())
    size = operating._object_bytes(record_id=control._string_size(identity), revision=len(str(revision)),
        kind=len('"event"'), content=content_size, provenance=provenance_size,
        record_references=link_size, artifact_references=2, operational_status=4, scientific_disposition=4)
    if size > min(control.TRANSITION_BYTES, reader.limits.max_record_bytes):
        raise RunControlLimitError('fresh enclosing envelope byte limit exceeded')
    reader.reserve(size)
    # Validation's typed JSON and nested round trips, then envelope canonicalization,
    # own scratch bytes independently of the retained envelope and original document.
    with reader.temporary(content_size * 4 + link_size + provenance_size):
        (control.RunReportObligation if obligation else control.RunControlTransition)(value)
        envelope = RecordEnvelope(identity, revision, 'event', value,
            CreationProvenance(actor, timestamp, {}),
            tuple(RecordReference.from_dict(ref) for ref in references()), ())
    reader.envelope_sizes[(identity, revision)] = size
    reader.envelope_shapes[(identity, revision)] = nodes, depth
    return envelope


def _fresh_submission(reader, transition, obligation, value):
    """Preflight full wrapper shape and bytes, then reserve batch copies before construction."""
    request = value['request']
    provenance_size = operating._object_bytes(actor=control._string_size(request['actor']),
        created_at=control._string_size(request['transitioned_at']), details=2)
    heads_size = 2 + 1 + sum(control._string_size(identity) + 1 + len(str(revision))
        for identity, revision in ((transition.record_id, transition.revision - 1), (obligation.record_id, 0)))
    size = operating._object_bytes(submission_id=control._string_size(request['operation_id']),
        provenance=provenance_size, expected_heads=heads_size,
        records=operating._array_bytes(reader.envelope_sizes[(record.record_id, record.revision)]
            for record in (transition, obligation)))
    wrapper_size = operating._object_bytes(fingerprint_version=1, submission=size)
    if wrapper_size > control.SUBMISSION_BYTES:
        raise RunControlLimitError('fresh complete submission byte limit exceeded')
    transition_nodes, transition_depth = reader.envelope_shapes[(transition.record_id, transition.revision)]
    obligation_nodes, obligation_depth = reader.envelope_shapes[(obligation.record_id, obligation.revision)]
    # Submission/provenance/records/heads add ten nodes; the saved wrapper adds
    # its object and version. Records sit three containers below that wrapper.
    wrapper_nodes = transition_nodes + obligation_nodes + 12
    wrapper_depth = max(4, transition_depth + 3, obligation_depth + 3)
    if wrapper_nodes > control.JSON_NODES or wrapper_depth > control.JSON_DEPTH:
        raise RunControlLimitError('fresh complete submission JSON node or depth limit exceeded')
    # Submission owns copied envelopes and its canonical wrapper until insertion.
    # The wire tree is released below; constructor and fingerprint bytes are scratch.
    reader.reserve(size + wrapper_size * 2)
    with reader.temporary(size * 2 + wrapper_size):
        submitted = _submission(transition, obligation, request)
        saved = {'fingerprint_version': 1, 'submission': submitted.to_dict()}
        canonical = control.canonical(saved)
        fingerprint = hashlib.sha256(canonical.encode('ascii')).hexdigest()
    del saved
    reader.metadata_bytes -= wrapper_size
    return submitted, canonical, fingerprint


def commit_run_control(store, request, *, policy, evaluated_at, limits):
    """Reconcile first, then atomically append one transition and its pending report obligation.

    Preparation/continuation alone consult current policy. Descriptive reductions
    need no external artifacts. Lost acknowledgment requires this same original ID.
    """
    from research_pipeline.store import SubmissionConflictError, RevisionConflictError, _fault as store_fault
    limits = control.checked_limits(limits)
    if type(request) is not control.RunControlRequest or type(getattr(request, '_json', None)) is not str:
        raise RunControlValidationError('expected exact retained control request')
    request_size = len(request._json)
    if request_size > control.REQUEST_BYTES:
        raise RunControlLimitError('control request byte limit exceeded')
    reader = _Reader(store, None, limits)
    with _errors():
        reader.reserve(request_size * 2)
        with reader.temporary(request_size * 2):
            request_value = control.document(request, control.RunControlRequest)
    policy_error = False
    try:
        policy = authority.policy_snapshot(policy)
    except authority.AuthorityValidationError:
        policy, policy_error = None, True
    operating._require_store(store)
    operation = request_value['operation_id']
    with _errors(), store._transaction(write=True, reconciliation_id='operation_id ' + operation) as connection:
        reader.connection = connection
        original = _operation(reader, operation)
        if original is not None:
            if original[1]['request'] != request_value:
                raise SubmissionConflictError('operation identity has a different lifecycle request')
            _history(reader, original[0].record_id, through=original[0].revision)
            return original[4]
        guard_fresh(connection, operation)
        history = _history(reader, control.control_id(request_value['run_id']))
        if len(history) != request_value['revision'] - 1:
            raise RevisionConflictError('control expected head conflict')
        previous = None if not history else (history[-1][0], history[-1][1])
        if previous is not None and request_value['predecessor']['envelope_digest'] != reader.digest(previous[0]):
            raise RevisionConflictError('control predecessor digest conflict')
        disposition = control.transition_disposition(None if previous is None else previous[1]['disposition'], request_value['action'])
        count = len(history) + 1
        if count > min(control.capacity(request_value['action']), limits.max_transitions, limits.max_pending_reports):
            raise RunControlLimitError('control history or pending terminal capacity exceeded')
        preparation = request_value['preparation'] if not history else history[0][1]['request']['preparation']
        _run(reader, request_value, preparation, current=request_value['action'] in ('prepare', 'continue'))
        if request_value['action'] == 'prepare':
            _anchors(reader, preparation)
            prior = preparation['previous_run']
            if prior is not None:
                linked = _history(reader, prior['reference']['record_id'], through=prior['reference']['revision'])
                prior_preparation = linked[0][1]['request']['preparation']
                if (reader.digest(linked[-1][0]) != prior['envelope_digest'] or prior_preparation['project']['record_id'] != preparation['project']['record_id'] or
                        prior_preparation['allocation']['allocation_id'] == preparation['allocation']['allocation_id']):
                    raise RunControlStateError('replacement requires same project and different allocation')
        authorization = None
        if request_value['action'] in ('prepare', 'continue'):
            if policy_error:
                raise RunControlPermissionError('current policy is unavailable')
            authorization = _authorize(reader, request_value, preparation, policy, evaluated_at,
                None if not history else history[0][1])
            if request_value['action'] == 'continue' and history:
                raise RunControlStateError('continuation requires zero pending mandatory reports')
        _fresh_reservations(reader, request_value)
        value = {'format': control.FORMATS[0], 'version': 1, 'request': request_value, 'disposition': disposition,
            'prepared_from': None if not history else control.reference(control.control_id(request_value['run_id']), 1, 'prepared_from'),
            'authorization': authorization, 'obligation': control.reference(control.obligation_id(operation), 1, 'required_report')}
        with reader.temporary(0 if previous is None else reader.envelope_sizes[(previous[0].record_id, previous[0].revision)] * 6):
            control.validate_successor(previous, value)
        # Reserve all new immutable representations before constructors retain them.
        transition_size = control.bounded_size(value, control.TRANSITION_BYTES)
        obligation_value = control.obligation_document(value)
        obligation_size = control.bounded_size(obligation_value, control.SMALL_BYTES)
        reader.reserve(transition_size + obligation_size)
        transition = _fresh_envelope(reader, value, actor=request_value['actor'])
        obligation = _fresh_envelope(reader, obligation_value, actor=request_value['actor'], obligation=True)
        submitted, canonical, fingerprint = _fresh_submission(reader, transition, obligation, value)
        # Both proposed members are legitimate mutual targets; existing target
        # helper rereads and ordered occurrences remain charged before _check_batch.
        proposed = {(record.record_id, record.revision) for record in submitted.records}
        for envelope in submitted.records:
            for ref in envelope.record_references:
                if (ref.record_id, ref.revision) not in proposed:
                    reader.shallow(ref, repeated=True)
            head = reader.head(envelope.record_id)
            if head is not None:
                reader.reserve(len(str(head['revision'])) + len(head['kind']))
        validate_request_kinds(submitted, store._schema_version)
        store._check_batch(connection, submitted)
        receipt_size = _receipt_size(operation, control.bounded_size(submitted.provenance.to_dict(), control.SMALL_BYTES),
            [(record.record_id, record.revision) for record in submitted.records])
        reader.reserve(receipt_size)
        _reserve_result(reader, _result_size(transition, obligation, receipt_size, value), control.SMALL_BYTES)
        _fault('before_insert')
        with reader.temporary(receipt_size * 3 + sum(reader.envelope_sizes[(item.record_id, item.revision)] * 2
                for item in submitted.records)):
            receipt = store._insert_submission(connection, submitted, canonical, fingerprint)
        with reader.temporary(receipt_size):
            actual_receipt_size = operating._fragment_bytes(receipt.to_dict())
        reader.metadata_bytes -= 2 * (receipt_size - actual_receipt_size)
        with reader.temporary(_result_size(transition, obligation, actual_receipt_size, value) * 3):
            result = _result(transition, obligation, receipt, value,
                digests=(reader.digest(transition), reader.digest(obligation)))
        if len(result._json) > limits.max_result_bytes:
            raise RunControlLimitError('control result exceeds independent allowance')
    # Transaction exit precedes acknowledgment seams. Never claim a later failure
    # rolled back these records or automatically deliver under a different ID.
    try:
        store_fault('after_commit')
        _fault('after_commit')
    except Exception as error:
        error.add_note('Run control acknowledgment uncertain; recover original operation_id ' + operation)
        raise
    return result


def get_run_control_operation(store, operation_id, *, limits):
    """Recover exact original metadata and required prefix without current trust, heads or artifacts."""
    limits = control.checked_limits(limits)
    control.report_operation_id(operation_id)
    operating._require_store(store)
    with _errors(), store._transaction() as connection:
        reader = _Reader(store, connection, limits)
        found = _operation(reader, operation_id)
        if found is None:
            return None
        _history(reader, found[0].record_id, through=found[0].revision)
        return found[4]


def inspect_run_control(store, run_id, *, limits):
    """Return complete current historical/pending evidence; neither clock nor trust is consulted."""
    limits = control.checked_limits(limits)
    identity = control.control_id(run_id)
    operating._require_store(store)
    with _errors(), store._transaction() as connection:
        reader = _Reader(store, connection, limits)
        watermark = reader.watermark()
        _fault('snapshot_established')
        history = _history(reader, identity)
        return _inspection(reader, run_id, history, watermark)


def _inspection(reader, run_id, history, watermark):
    """Build bounded historical inspection on the caller's connection without recapture."""
    identity = control.control_id(run_id)
    limits = reader.control_limits
    size = operating._object_bytes(format=len('"research_pipeline.run_control_inspection"'), version=1,
        run_id=control._string_size(run_id), head=4 if not history else operating._reference_bytes(identity, len(history), 'run_control', 'event'),
        disposition=4 if not history else control._string_size(history[-1][1]['disposition']),
        transitions=operating._array_bytes(operating._object_bytes(envelope=reader.envelope_sizes[(item[0].record_id, item[0].revision)],
            receipt=reader.receipt_sizes[item[3].submission_id]) for item in history),
        pending_obligations=operating._array_bytes(reader.envelope_sizes[(item[2].record_id, 1)] for item in history),
        watermark=operating._fragment_bytes(watermark), ordinary_work_allowed=5, recheck_required=4)
    # Count all output value nodes and wrapper depth from validated fragments
    # before constructing either result array or the detached inspection.
    base_nodes = 15 + (4 if history else 0)
    for item in history:
        transition_nodes, transition_depth = reader.envelope_shapes[(item[0].record_id, item[0].revision)]
        obligation_nodes, obligation_depth = reader.envelope_shapes[(item[2].record_id, 1)]
        receipt_nodes = 16  # receipt object, provenance and two two-scalar member arrays
        base_nodes += 1 + transition_nodes + receipt_nodes + obligation_nodes
        if transition_depth + 3 > control.JSON_DEPTH or obligation_depth + 2 > control.JSON_DEPTH:
            raise RunControlLimitError('control inspection JSON depth limit exceeded')
    if base_nodes > control.JSON_NODES:
        raise RunControlLimitError('control inspection JSON node limit exceeded')
    _reserve_result(reader, size, control.RESULT_BYTES)
    with reader.temporary(size * 5):
        result = control.RunControlInspection({'format': 'research_pipeline.run_control_inspection', 'version': 1,
            'run_id': run_id, 'head': None if not history else control.reference(identity, len(history), 'run_control'),
            'disposition': None if not history else history[-1][1]['disposition'],
            'transitions': [{'envelope': item[0].to_dict(), 'receipt': item[3].to_dict()} for item in history],
            'pending_obligations': [item[2].to_dict() for item in history], 'watermark': watermark,
            'ordinary_work_allowed': False, 'recheck_required': True})
    if len(result._json) > limits.max_result_bytes:
        raise RunControlLimitError('control inspection exceeds independent allowance')
    return result
