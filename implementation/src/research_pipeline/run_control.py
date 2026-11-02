"""Detached prepared-control facts and pending report intent, never execution authority."""

from dataclasses import dataclass
import hashlib
import json
import math

from research_pipeline import operating_authority as authority, reports
from research_pipeline.domain import (
    DomainValidationError, RecordEnvelope, RecordReference, CreationProvenance,
    SubmissionReceipt, _identifier, _integer, _validate_json_string,
)
from research_pipeline.snapshot import _commit

REQUEST_BYTES = 2 * 1024 * 1024
TRANSITION_BYTES = 4 * 1024 * 1024
SMALL_BYTES = 256 * 1024
SUBMISSION_BYTES = 8 * 1024 * 1024
RESULT_BYTES = 64 * 1024 * 1024
JSON_DEPTH = 48
JSON_NODES = 131072
DISPOSITIONS = ('prepared', 'paused', 'stopped', 'cancelled', 'abandoned')
ACTIONS = ('prepare', 'checkpoint', 'milestone', 'pause', 'continue', 'stop', 'cancel', 'abandon')
FORMATS = ('research_pipeline.run_control_transition', 'research_pipeline.run_report_obligation')


class RunControlValidationError(DomainValidationError):
    """A new detached control contract is malformed or forged."""


class RunControlIntegrityError(ValueError):
    """Stored control facts, projections, or their history disagree."""


class RunControlLimitError(ValueError):
    """Complete control evidence exceeds a hard or independent caller allowance."""


class RunControlStateError(ValueError):
    """A transition, immutable binding, pending gate, or reserved owner conflicts."""


class RunControlPermissionError(ValueError):
    """Current externally configured authority cannot authorize preparation or continuation."""


def canonical(value):
    """Encode validated documents in the shared compact sorted ASCII representation."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _string_size(value):
    """Count canonical ASCII string bytes without allocating an escaped copy."""
    _validate_json_string(value, 'control string')
    size = 2
    for char in value:
        number = ord(char)
        size += (2 if char in '"\\\b\f\n\r\t' else
                 6 if number < 32 or 127 <= number <= 65535 else
                 12 if number > 65535 else 1)
    return size


def _measure_json(value, maximum):
    """Measure bytes, value nodes and container depth before retaining a canonical document."""
    stack, ancestors, nodes, size = [(value, 0, False)], set(), 0, 0
    deepest = 0
    while stack:
        item, depth, leaving = stack.pop()
        if leaving:
            ancestors.remove(id(item))
            continue
        nodes += 1
        if nodes > JSON_NODES:
            raise RunControlValidationError('control JSON node limit exceeded')
        kind = type(item)
        if kind in (dict, list):
            deepest = max(deepest, depth + 1)
            if depth >= JSON_DEPTH or id(item) in ancestors:
                raise RunControlValidationError('control JSON depth or cycle violation')
            if len(item) > JSON_NODES - nodes:
                raise RunControlValidationError('control JSON node limit exceeded')
            ancestors.add(id(item))
            stack.append((item, depth, True))
            size += 2 + max(0, len(item) - 1)
            if kind is dict:
                for key in item:
                    if type(key) is not str:
                        raise RunControlValidationError('control object keys require strings')
                    size += _string_size(key) + 1
                children = item.values()
            else:
                children = item
            stack.extend((child, depth + 1, False) for child in children)
        elif kind is str:
            size += _string_size(item)
        elif item is None:
            size += 4
        elif kind is bool:
            size += 4 if item else 5
        elif kind is int:
            size += len(str(item))
        elif kind is float and math.isfinite(item):
            size += len(canonical(item))
        else:
            raise RunControlValidationError('unsupported control JSON scalar')
        if size > maximum:
            raise RunControlLimitError('control canonical byte limit exceeded')
    return size, nodes, deepest


def bounded_size(value, maximum):
    """Preflight cycles, scalar types, containers, nodes and exact escaping before encoding."""
    return _measure_json(value, maximum)[0]


def _pairs(pairs):
    """Reject duplicate keys at every parsed nesting level."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise RunControlValidationError('duplicate control JSON field')
        result[key] = value
    return result


def _constant(value):
    """Reject nonfinite parser constants without echoing input."""
    raise RunControlValidationError('nonfinite control JSON number')


def _lexical_preflight(text, maximum):
    """Count UTF-8 bytes and JSON values before parsing, excluding quoted object keys.

    This bounded scanner recognizes token boundaries and escaped quotes only;
    the strict parser still owns JSON syntax, duplicate keys and scalar validity.
    """
    size = 0
    for char in text:
        number = ord(char)
        if 0xD800 <= number <= 0xDFFF:
            raise RunControlValidationError('invalid control Unicode')
        size += 1 if number < 128 else 2 if number < 2048 else 3 if number < 65536 else 4
        if size > maximum:
            raise RunControlLimitError('control input byte limit exceeded')
    stack, nodes, quoted, escaped, scalar = [], 0, False, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char.isspace():
            scalar = False
            continue
        if char in ',:':
            scalar = False
            if stack and stack[-1][0] == '{':
                stack[-1][1] = char == ','
            continue
        if char in ']}':
            scalar = False
            if stack:
                stack.pop()
            continue
        key = bool(stack and stack[-1][0] == '{' and stack[-1][1])
        if char == '"':
            quoted = True
            scalar = False
            nodes += not key
        elif char in '[{':
            nodes += 1
            stack.append([char, char == '{'])
            scalar = False
            if len(stack) > JSON_DEPTH:
                raise RunControlValidationError('control JSON depth limit exceeded')
        elif not scalar:
            nodes += 1
            scalar = True
        if nodes > JSON_NODES:
            raise RunControlValidationError('control JSON node limit exceeded')


def strict_json(text, maximum):
    """Reject byte, depth and value-node overflow before strict JSON reconstruction."""
    try:
        if type(text) is bytes:
            if len(text) > maximum:
                raise RunControlLimitError('control input byte limit exceeded')
            text = text.decode('utf-8')
        if type(text) is not str:
            raise RunControlValidationError('control input requires JSON text')
        _lexical_preflight(text, maximum)
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        bounded_size(value, maximum)
        return value
    except RunControlLimitError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise RunControlValidationError('invalid control JSON') from None


def _identity(prefix, value):
    """Derive a namespace identity from an exact existing domain identifier."""
    try:
        _identifier(value, 'identity')
    except DomainValidationError:
        raise RunControlValidationError('invalid control identity') from None
    return prefix + hashlib.sha256(value.encode('utf-8')).hexdigest()


def control_id(run_id):
    """Return the sole control stream identity for a logical generic run."""
    return _identity('run-control-', run_id)


def obligation_id(operation_id):
    """Return the immutable obligation identity for one lifecycle operation."""
    return _identity('run-control-obligation-', operation_id)


def report_operation_id(operation_id):
    """Reserve a future report operation identity without creating report facts."""
    return _identity('run-control-report-', operation_id)


def reference(identity, revision, role, kind='event'):
    """Build a complete exact reference for deterministic control projections."""
    return RecordReference(identity, revision, role, kind).to_dict()


def _pin(value, role, kind='event', expected=None):
    """Validate a complete digest pin and, when supplied, its exact identity/revision."""
    authority.exact(value, 'reference envelope_digest')
    authority.reference(value['reference'], role, kind)
    authority.digest(value['envelope_digest'])
    if expected is not None and authority.pin(value['reference']) != expected:
        raise RunControlValidationError('control pin identity mismatch')


def _unavailable(value):
    """Require the existing explicit unknown declaration, never an omitted value."""
    reports._declared(value, unknown=True)


def _preparation(value, request):
    """Validate immutable dossier, resource declarations and optional replacement linkage."""
    authority.exact(value, 'authority_domain purpose project initial_corpus current_corpus context start_baseline operating_scope allocation previous_run')
    _identifier(value['authority_domain'], 'authority domain')
    authority.enum(value['purpose'], ('setup', 'main_research'))
    for name, kind in (('project', 'project'), ('initial_corpus', 'corpus_manifest'), ('current_corpus', 'corpus_manifest')):
        authority.reference(value[name], 'project_setup' if name == 'project' else name, kind)
    if value['initial_corpus']['revision'] != 1 or value['initial_corpus']['record_id'] != value['current_corpus']['record_id']:
        raise RunControlValidationError('control corpus baseline mismatch')
    if value['context'] != authority.absent():
        authority.reference(value['context'], 'context', 'research_context')
    if 'record_id' in value['start_baseline']:
        authority.reference(value['start_baseline'], 'start_baseline', 'work_product_manifest')
    else:
        _unavailable(value['start_baseline'])
    scope = authority.OperatingScope(value['operating_scope']).to_dict()
    if scope != value['operating_scope'] or scope['purpose'] != value['purpose']:
        raise RunControlValidationError('control operating scope mismatch')
    allocation = authority.exact(value['allocation'], 'allocation_id project_account run_account')
    _identifier(allocation['allocation_id'], 'allocation identity')
    for name, kind in (('project_account', 'project'), ('run_account', 'run')):
        account = allocation[name]
        if 'account_id' not in account:
            _unavailable(account)
            continue
        authority.exact(account, 'account_id operation_id anchor')
        _identifier(account['account_id'], 'account identity')
        _identifier(account['operation_id'], 'account operation')
        authority.reference(account['anchor'], 'resource_scope', kind)
        expected = authority.pin(value['project']) if kind == 'project' else (request['run_id'], request['run_revision'])
        if authority.pin(account['anchor']) != expected:
            raise RunControlValidationError('account anchor differs from preparation')
    if 'account_id' in allocation['run_account'] and 'account_id' not in allocation['project_account']:
        raise RunControlValidationError('known run account requires project account')
    if value['previous_run'] is not None:
        _pin(value['previous_run'], 'previous_run')
        if value['previous_run']['reference']['record_id'] == control_id(request['run_id']):
            raise RunControlValidationError('replacement must use a different logical run')


def transition_disposition(previous, action):
    """Apply the sole pure lifecycle table; evidence updates preserve terminal states."""
    if action == 'prepare' and previous is None:
        return 'prepared'
    if previous in DISPOSITIONS and action in ('checkpoint', 'milestone'):
        return previous
    rules = {'pause': (('prepared',), 'paused'), 'continue': (('paused',), 'prepared'),
             'stop': (('prepared', 'paused'), 'stopped'),
             'cancel': (('prepared', 'paused', 'stopped'), 'cancelled'),
             'abandon': (('prepared', 'paused', 'stopped'), 'abandoned')}
    if action in rules and previous in rules[action][0]:
        return rules[action][1]
    raise RunControlStateError('illegal control transition')


def capacity(action):
    """Leave separate durable metadata slots for pause, stop, then terminal cancellation."""
    return {'pause': 1022, 'stop': 1023, 'cancel': 1024, 'abandon': 1024}.get(action, 1021)


def scientific_outcome(request, disposition):
    """Keep attributed scientific labels separate from operational reductions and disposition."""
    label = request['report']['declarations']['outcome']['label']
    reason = request['operational_reason']
    if request['action'] == 'prepare' and label != 'not_yet_assessed':
        raise RunControlStateError('preparation requires an unassessed scientific outcome')
    if label == 'objective_met' and (disposition in ('cancelled', 'abandoned') or
            reason is not None and reason['code'] in ('failure', 'resource_limit', 'authority_unavailable', 'model_forbidden')):
        raise RunControlStateError('scientific outcome conflicts with control evidence')


def _request(value):
    """Validate all lifecycle inputs without resolving stored facts or external trust."""
    authority.exact(value, 'format version operation_id run_id run_revision revision predecessor action actor transitioned_at preparation expected_authority operational_reason report')
    for name in ('operation_id', 'run_id', 'actor'):
        _identifier(value[name], name)
    for name in ('run_revision', 'revision'):
        _integer(value[name], name, 1)
    authority.timestamp(value['transitioned_at'])
    authority.enum(value['action'], ACTIONS)
    if value['revision'] == 1:
        if value['predecessor'] is not None or value['action'] != 'prepare':
            raise RunControlValidationError('initial control requires preparation without predecessor')
    else:
        if value['action'] == 'prepare':
            raise RunControlValidationError('preparation requires initial revision')
        _pin(value['predecessor'], 'supersedes', expected=(control_id(value['run_id']), value['revision'] - 1))
    if value['action'] == 'prepare':
        _preparation(value['preparation'], value)
    elif value['preparation'] is not None:
        raise RunControlValidationError('only prepare carries preparation')
    if value['action'] in ('prepare', 'continue'):
        _pin(value['expected_authority'], 'operating_decision', 'decision')
    elif value['expected_authority'] is not None:
        raise RunControlValidationError('descriptive transition cannot carry authorization')
    reason = value['operational_reason']
    if value['action'] in ('pause', 'stop', 'cancel', 'abandon'):
        authority.exact(reason, 'code detail')
        authority.enum(reason['code'], ('requested', 'checkpoint', 'resource_limit', 'authority_unavailable', 'model_forbidden', 'failure', 'completed', 'abandoned'))
        authority.text_value(reason['detail'])
        if value['action'] == 'abandon' and reason['code'] != 'abandoned' or value['action'] == 'cancel' and reason['code'] == 'completed':
            raise RunControlValidationError('incompatible control reason')
    elif reason is not None:
        raise RunControlValidationError('unexpected control reason')
    report = authority.exact(value['report'], 'selection declarations limits')
    bounded_size(report, SMALL_BYTES)
    reports._tree(report)
    reports._references(report['selection'], 'report_selection', maximum=128, unique_identity=True)
    reports._declarations(report['declarations'])
    if reports._limits(report['limits']) != report['limits']:
        raise RunControlValidationError('report limits must be canonical')
    scientific_outcome(value, {'cancel': 'cancelled', 'abandon': 'abandoned'}.get(value['action']))
    return value


def _transition(value):
    """Validate local transition structure; predecessor disposition needs paired history."""
    authority.exact(value, 'format version request disposition prepared_from authorization obligation')
    request = RunControlRequest(value['request']).to_dict()
    authority.enum(value['disposition'], DISPOSITIONS)
    if request['action'] not in ('checkpoint', 'milestone'):
        expected = {'prepare': 'prepared', 'continue': 'prepared', 'pause': 'paused', 'stop': 'stopped', 'cancel': 'cancelled', 'abandon': 'abandoned'}[request['action']]
        if value['disposition'] != expected:
            raise RunControlValidationError('incorrect derived disposition')
    scientific_outcome(request, value['disposition'])
    if value['prepared_from'] is not None:
        authority.reference(value['prepared_from'], 'prepared_from', 'event')
    authority.reference(value['obligation'], 'required_report', 'event')
    prepared = None if request['action'] == 'prepare' else reference(control_id(request['run_id']), 1, 'prepared_from')
    if value['prepared_from'] != prepared:
        raise RunControlValidationError('incorrect preparation reference')
    auth = value['authorization']
    if request['action'] in ('prepare', 'continue'):
        authority.exact(auth, 'decision evaluated_at policy_fingerprint watermark')
        _pin(auth['decision'], 'operating_decision', 'decision')
        if auth['decision'] != request['expected_authority']:
            raise RunControlValidationError('authorization differs from expected decision')
        authority.timestamp(auth['evaluated_at'])
        authority.digest(auth['policy_fingerprint'])
        _commit(auth['watermark'], watermark=True)
        if auth['evaluated_at'] < request['transitioned_at']:
            raise RunControlValidationError('evaluation precedes transition')
    elif auth is not None:
        raise RunControlValidationError('unexpected authorization')
    if value['obligation'] != reference(obligation_id(request['operation_id']), 1, 'required_report'):
        raise RunControlValidationError('incorrect obligation reference')
    return value


def obligation_document(transition):
    """Derive the single pending obligation, reserving identities without report records."""
    request = transition['request']
    operation = request['operation_id']
    report_operation = report_operation_id(operation)
    return {'format': FORMATS[1], 'version': 1, 'operation_id': operation, 'run_id': request['run_id'],
            'run_revision': request['run_revision'], 'transition': reference(control_id(request['run_id']), request['revision'], 'run_control'),
            'report_operation_id': report_operation, 'report_source_id': reports.source_id(report_operation),
            'report_manifest_id': reports.manifest_id(request['run_id']), 'report_revision': request['revision'],
            'kind': {'prepare': 'initial', 'continue': 'checkpoint'}.get(request['action'], request['action']),
            'required_at': request['transitioned_at'], 'selection': request['report']['selection']}


def _obligation(value):
    """Validate reserved identities and local intent without asserting historical pairing."""
    authority.exact(value, 'format version operation_id run_id run_revision transition report_operation_id report_source_id report_manifest_id report_revision kind required_at selection')
    for name in ('operation_id', 'run_id'):
        _identifier(value[name], name)
    for name in ('run_revision', 'report_revision'):
        _integer(value[name], name, 1)
    authority.timestamp(value['required_at'])
    authority.enum(value['kind'], ('initial', 'checkpoint', 'milestone', 'pause', 'stop', 'cancel', 'abandon'))
    authority.reference(value['transition'], 'run_control', 'event')
    operation = report_operation_id(value['operation_id'])
    if (value['report_operation_id'] != operation or value['report_source_id'] != reports.source_id(operation) or
            value['report_manifest_id'] != reports.manifest_id(value['run_id']) or
            value['transition'] != reference(control_id(value['run_id']), value['report_revision'], 'run_control') or
            (value['kind'] == 'initial') != (value['report_revision'] == 1)):
        raise RunControlValidationError('inconsistent obligation derivation')
    reports._references(value['selection'], 'report_selection', maximum=128, unique_identity=True)
    return value


def _closed_gate(value):
    """Reject any public result that purports to permit ordinary work."""
    if value['ordinary_work_allowed'] is not False or value['recheck_required'] is not True:
        raise RunControlValidationError('control evidence never permits ordinary work')


def _commit_result(value):
    """Validate immutable two-member receipt evidence and its always-pending report state."""
    authority.exact(value, 'format version operation_id transition transition_digest obligation obligation_digest disposition report_state report_source report_plan_id ordinary_work_allowed recheck_required receipt')
    _identifier(value['operation_id'], 'operation identity')
    authority.reference(value['transition'], 'run_control', 'event')
    identity = value['transition']['record_id']
    if not identity.startswith('run-control-'):
        raise RunControlValidationError('result requires a canonical control identity')
    authority.digest(identity[len('run-control-'):])
    authority.reference(value['obligation'], 'required_report', 'event')
    for name in ('transition_digest', 'obligation_digest'):
        authority.digest(value[name])
    authority.enum(value['disposition'], DISPOSITIONS)
    _closed_gate(value)
    receipt = SubmissionReceipt.from_dict(value['receipt'])
    if (receipt.to_dict() != value['receipt'] or receipt.submission_id != value['operation_id'] or
            tuple(receipt.revisions) != (authority.pin(value['transition']), authority.pin(value['obligation'])) or
            value['obligation'] != reference(obligation_id(value['operation_id']), 1, 'required_report') or
            value['report_state'] != 'pending_capture' or value['report_source'] is not None or value['report_plan_id'] is not None):
        raise RunControlValidationError('inconsistent original control result')
    return value


def _inspection(value):
    """Validate a complete detached ordered history and each cross-record obligation pair."""
    authority.exact(value, 'format version run_id head disposition transitions pending_obligations watermark ordinary_work_allowed recheck_required')
    _identifier(value['run_id'], 'logical run')
    if value['head'] is not None:
        authority.reference(value['head'], 'run_control', 'event')
    _closed_gate(value)
    _commit(value['watermark'], watermark=True)
    transitions = authority.array(value['transitions'], 1024)
    obligations = authority.array(value['pending_obligations'], 1024)
    if len(transitions) != len(obligations):
        raise RunControlValidationError('incomplete pending obligation list')
    previous = None
    for index, (entry, pending) in enumerate(zip(transitions, obligations), 1):
        authority.exact(entry, 'envelope receipt')
        envelope = RecordEnvelope.from_dict(entry['envelope'])
        if envelope.to_dict() != entry['envelope']:
            raise RunControlValidationError('inspection requires complete canonical envelopes')
        transition = decode_transition(envelope).to_dict()
        request = transition['request']
        obligation = RecordEnvelope.from_dict(pending)
        paired_obligation(transition, envelope, obligation)
        receipt = SubmissionReceipt.from_dict(entry['receipt'])
        if receipt.to_dict() != entry['receipt'] or obligation.to_dict() != pending:
            raise RunControlValidationError('inspection requires complete canonical receipt and obligation')
        if (request['run_id'] != value['run_id'] or request['revision'] != index or
                receipt.submission_id != request['operation_id'] or receipt.provenance != envelope.provenance or
                tuple(receipt.revisions) != ((envelope.record_id, envelope.revision), (obligation.record_id, 1))):
            raise RunControlValidationError('inspection receipt or stream mismatch')
        validate_successor(previous, transition)
        previous = (envelope, transition)
    expected_head = None if previous is None else reference(control_id(value['run_id']), len(transitions), 'run_control')
    if value['head'] != expected_head or value['disposition'] != (None if previous is None else previous[1]['disposition']):
        raise RunControlValidationError('inspection head differs from complete history')
    return value


@dataclass(frozen=True, init=False)
class _Document:
    """Retain canonical detached JSON for exact closed control document classes."""
    _json: str

    def __init__(self, document):
        """Preflight and validate before retaining a canonical snapshot."""
        object.__setattr__(self, '_json', _normalize(type(self), document))

    def to_dict(self):
        """Revalidate forged retained state and return an isolated mutable tree."""
        try:
            maximum = _CONTRACTS[type(self)][1]
            value = strict_json(self._json, maximum)
            normalized = _normalize(type(self), value)
            if normalized != self._json:
                raise RunControlValidationError('noncanonical retained control state')
            return value
        except RunControlLimitError:
            raise
        except (KeyError, AttributeError, TypeError, ValueError):
            raise RunControlValidationError('invalid detached control value') from None

    @classmethod
    def from_dict(cls, document):
        """Construct an exact supported document from its complete wire fields."""
        return cls(document)


@dataclass(frozen=True, init=False)
class RunControlRequest(_Document):
    """Explicit lifecycle proposal with separate generic-run and control revisions."""


@dataclass(frozen=True, init=False)
class RunControlTransition(_Document):
    """Prepared-control history fact, structurally decodable without current permission."""


@dataclass(frozen=True, init=False)
class RunReportObligation(_Document):
    """Durable ordered intent for a future report, with no capture or publication claim."""


@dataclass(frozen=True, init=False)
class RunControlCommitResult(_Document):
    """Original immutable receipt and pending obligation evidence, never a resume token."""


@dataclass(frozen=True, init=False)
class RunControlInspection(_Document):
    """Complete historical control and pending evidence without restart readiness."""


_CONTRACTS = {
    RunControlRequest: ('run_control_request', REQUEST_BYTES, _request),
    RunControlTransition: ('run_control_transition', TRANSITION_BYTES, _transition),
    RunReportObligation: ('run_report_obligation', SMALL_BYTES, _obligation),
    RunControlCommitResult: ('run_control_commit_result', SMALL_BYTES, _commit_result),
    RunControlInspection: ('run_control_inspection', RESULT_BYTES, _inspection),
}


def _normalize(cls, value):
    """Apply independent wrapper and nested validation without extending authority's registry."""
    try:
        name, maximum, validator = _CONTRACTS[cls]
        bounded_size(value, maximum)
        if type(value) is not dict or value.get('format') != 'research_pipeline.' + name or type(value.get('version')) is not int or value['version'] != 1:
            raise RunControlValidationError('unsupported control format/version')
        validator(value)
        return canonical(value)
    except RunControlLimitError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        raise RunControlValidationError('invalid control contract') from None


def document(value, cls):
    """Consume only the exact requested class and revalidate bypassable retained state."""
    if type(value) is not cls:
        raise RunControlValidationError('expected exact control class')
    return value.to_dict()


def _declaration_references(value):
    """Traverse validated declaration keys in sorted order, preserving every array occurrence."""
    if type(value) is dict:
        if set(value) == {'record_id', 'revision', 'relationship', 'target_kind'}:
            yield value
        else:
            for key in sorted(value):
                yield from _declaration_references(value[key])
    elif type(value) is list:
        for item in value:
            yield from _declaration_references(item)


def _transition_references(value):
    """Project exact ordered evidence links; authorization does not duplicate its decision pin."""
    request = value['request']
    if request['predecessor'] is not None:
        yield request['predecessor']['reference']
    if value['prepared_from'] is not None:
        yield value['prepared_from']
    yield reference(request['run_id'], request['run_revision'], 'run', 'run')
    preparation = request['preparation']
    if preparation is not None:
        yield from (preparation[name] for name in ('project', 'initial_corpus', 'current_corpus'))
        for name in ('context', 'start_baseline'):
            if 'record_id' in preparation[name]:
                yield preparation[name]
        if preparation['previous_run'] is not None:
            yield preparation['previous_run']['reference']
        for name in ('project_account', 'run_account'):
            if 'account_id' in preparation['allocation'][name]:
                yield preparation['allocation'][name]['anchor']
    if request['expected_authority'] is not None:
        yield request['expected_authority']['reference']
    yield from request['report']['selection']
    yield from _declaration_references(request['report']['declarations'])
    yield value['obligation']



def _transition_links(value):
    """Materialize the ordered projection after callers have counted its occurrences."""
    return tuple(RecordReference.from_dict(item) for item in _transition_references(value))


def encode_transition(transition):
    """Project a validated transition into its exact event envelope with empty direct artifacts."""
    value = document(transition, RunControlTransition)
    request = value['request']
    return RecordEnvelope(control_id(request['run_id']), request['revision'], 'event', value,
        CreationProvenance(request['actor'], request['transitioned_at'], {}), _transition_links(value), ())


def _envelope_document(envelope):
    """Revalidate forged retained envelope JSON before any unbounded content accessor runs."""
    if type(envelope) is not RecordEnvelope:
        raise RunControlValidationError('expected exact control envelope')
    try:
        if type(envelope.provenance) is not CreationProvenance:
            raise ValueError
        provenance = envelope.provenance
        if type(envelope.record_references) is not tuple or len(envelope.record_references) > JSON_NODES // 5:
            raise ValueError
        if type(envelope.artifact_references) is not tuple or any(type(ref) is not RecordReference for ref in envelope.record_references) or envelope.artifact_references:
            raise ValueError
        value = {'record_id': envelope.record_id, 'revision': envelope.revision, 'kind': envelope.kind,
            'content': strict_json(envelope._content_json, TRANSITION_BYTES),
            'provenance': {'actor': provenance.actor, 'created_at': provenance.created_at,
                'details': strict_json(provenance._details_json, SMALL_BYTES)},
            'record_references': [ref.to_dict() for ref in envelope.record_references], 'artifact_references': [],
            'operational_status': envelope.operational_status, 'scientific_disposition': envelope.scientific_disposition}
        bounded_size(value, TRANSITION_BYTES)
        if RecordEnvelope.from_dict(value).to_dict() != value:
            raise ValueError
        return value
    except RunControlLimitError:
        raise
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise RunControlValidationError('invalid control envelope') from None


def envelope_digest(envelope):
    """Hash the complete canonical envelope using the authority digest convention."""
    return hashlib.sha256(canonical(_envelope_document(envelope)).encode('ascii')).hexdigest()


def decode_transition(envelope):
    """Validate the complete local envelope projection; this does not certify historical admission."""
    if type(envelope) is not RecordEnvelope:
        raise RunControlValidationError('expected exact control envelope')
    try:
        stored = _envelope_document(envelope)
        value = RunControlTransition(stored['content'])
        if encode_transition(value).to_dict() != stored:
            raise ValueError
        return value
    except RunControlLimitError:
        raise
    except (ValueError, TypeError, AttributeError):
        raise RunControlValidationError('invalid transition envelope projection') from None


def encode_obligation(obligation, *, actor):
    """Project pending intent using the originating actor, supplied separately from the wire document."""
    value = document(obligation, RunReportObligation)
    try:
        _identifier(actor, 'actor')
        return RecordEnvelope(obligation_id(value['operation_id']), 1, 'event', value,
            CreationProvenance(actor, value['required_at'], {}),
            tuple(RecordReference.from_dict(item) for item in [value['transition'], *value['selection']]), ())
    except (ValueError, TypeError):
        raise RunControlValidationError('invalid obligation actor') from None


def decode_obligation(envelope):
    """Check local structure using its validated actor; pairing checks the originating actor separately."""
    if type(envelope) is not RecordEnvelope:
        raise RunControlValidationError('expected exact obligation envelope')
    try:
        stored = _envelope_document(envelope)
        value = RunReportObligation(stored['content'])
        if encode_obligation(value, actor=envelope.provenance.actor).to_dict() != stored:
            raise ValueError
        return value
    except RunControlLimitError:
        raise
    except (ValueError, TypeError, AttributeError):
        raise RunControlValidationError('invalid obligation envelope projection') from None


def paired_obligation(transition, envelope, obligation):
    """Require cross-record derivation and complete provenance equality, beyond local decoding."""
    value = decode_obligation(obligation).to_dict()
    if value != obligation_document(transition) or obligation.provenance != envelope.provenance:
        raise RunControlIntegrityError('obligation differs from originating transition')


def validate_successor(previous, transition):
    """Validate history-dependent disposition, time, run selection and predecessor digest."""
    request = transition['request']
    prior = None if previous is None else previous[1]
    if transition_disposition(None if prior is None else prior['disposition'], request['action']) != transition['disposition']:
        raise RunControlStateError('disposition does not follow predecessor')
    scientific_outcome(request, transition['disposition'])
    if prior is not None:
        earlier = prior['request']
        if (request['run_id'] != earlier['run_id'] or request['revision'] != earlier['revision'] + 1 or
                request['predecessor']['envelope_digest'] != envelope_digest(previous[0]) or
                request['transitioned_at'] < earlier['transitioned_at'] or request['run_revision'] < earlier['run_revision']):
            raise RunControlStateError('control predecessor, time or selected run revision mismatch')


@dataclass(frozen=True)
class RunControlLimits:
    """Independent explicit history, pending, metadata and result budgets; never truncate."""
    metadata: authority.AuthorityLimits
    max_transitions: int
    max_pending_reports: int
    max_result_bytes: int

    def __post_init__(self):
        """Revalidate exact nested limits and ordinary integers before any database access."""
        try:
            if type(self) is not RunControlLimits:
                raise ValueError
            authority.checked_limits(self.metadata)
            for name in ('max_transitions', 'max_pending_reports', 'max_result_bytes'):
                number = getattr(self, name)
                _integer(number, name, 1 if name == 'max_result_bytes' else 0)
                if number > (RESULT_BYTES if name == 'max_result_bytes' else 1024):
                    raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise RunControlValidationError('invalid explicit control limits') from None


def checked_limits(value):
    """Detach forged or mutable nested budgets before opening a store transaction."""
    if type(value) is not RunControlLimits:
        raise RunControlValidationError('expected exact RunControlLimits')
    try:
        return RunControlLimits(authority.checked_limits(value.metadata), value.max_transitions, value.max_pending_reports, value.max_result_bytes)
    except (ValueError, TypeError, AttributeError):
        raise RunControlValidationError('invalid explicit control limits') from None


def dumps_request(value):
    """Serialize an exact revalidated RunControlRequest as canonical ASCII JSON."""
    return canonical(document(value, RunControlRequest))


def loads_request(value):
    """Decode bounded strict JSON into a detached RunControlRequest."""
    return RunControlRequest(strict_json(value, REQUEST_BYTES))


def dumps_transition(value):
    """Serialize an exact revalidated RunControlTransition as canonical ASCII JSON."""
    return canonical(document(value, RunControlTransition))


def loads_transition(value):
    """Decode bounded strict JSON into a detached RunControlTransition."""
    return RunControlTransition(strict_json(value, TRANSITION_BYTES))


def dumps_obligation(value):
    """Serialize an exact revalidated RunReportObligation as canonical ASCII JSON."""
    return canonical(document(value, RunReportObligation))


def loads_obligation(value):
    """Decode bounded strict JSON into a detached RunReportObligation."""
    return RunReportObligation(strict_json(value, SMALL_BYTES))


def dumps_commit_result(value):
    """Serialize an exact revalidated RunControlCommitResult as canonical ASCII JSON."""
    return canonical(document(value, RunControlCommitResult))


def loads_commit_result(value):
    """Decode bounded strict JSON into a detached RunControlCommitResult."""
    return RunControlCommitResult(strict_json(value, SMALL_BYTES))


def dumps_inspection(value):
    """Serialize an exact revalidated RunControlInspection as canonical ASCII JSON."""
    return canonical(document(value, RunControlInspection))


def loads_inspection(value):
    """Decode bounded strict JSON into a detached RunControlInspection."""
    return RunControlInspection(strict_json(value, RESULT_BYTES))
