"""Bounded offline lifecycle intent consistency; never persistence or work authority."""

from dataclasses import dataclass
import hashlib
import json
import math

from research_pipeline import run_control as control
from research_pipeline.domain import DomainValidationError, RecordEnvelope

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_PACKET_BYTES = 16 * 1024 * 1024
MAX_WORK_BYTES = 2 * 1024 * 1024 * 1024
MAX_NODES = 3 * 131072 + 8
MAX_DEPTH = 49

__all__ = [
    'LifecycleReportBindingArgumentError', 'LifecycleReportBindingValidationError',
    'LifecycleReportBindingLimitError', 'LifecycleReportBindingLimits',
    'LifecycleReportBinding', 'bind_lifecycle_report', 'dumps_binding', 'loads_binding',
    'binding_digest', 'MAX_INPUT_BYTES', 'MAX_PACKET_BYTES', 'MAX_WORK_BYTES',
    'MAX_NODES', 'MAX_DEPTH',
]

_FORMAT = 'research_pipeline.lifecycle_report_binding'
_MEMBERS = ('preparation', 'transition', 'obligation')
_FIELDS = ('format version preparation preparation_digest transition transition_digest '
           'obligation obligation_digest ordinary_work_allowed recheck_required')
_ENVELOPE_FIELDS = ('record_id revision kind content provenance record_references '
                    'artifact_references operational_status scientific_disposition')


class LifecycleReportBindingArgumentError(ValueError):
    """A public argument has the wrong exact type or an invalid explicit allowance."""


class LifecycleReportBindingValidationError(DomainValidationError):
    """Packet content is malformed, contradictory, or retained noncanonically."""


class LifecycleReportBindingLimitError(ValueError):
    """Processing exceeds an independent caller or structural hard ceiling."""


@dataclass(frozen=True, kw_only=True)
class LifecycleReportBindingLimits:
    """Authorize independent input, packet, workspace, value-node and nesting costs."""
    max_input_bytes: int
    max_packet_bytes: int
    max_work_bytes: int
    max_nodes: int
    max_depth: int

    def __post_init__(self):
        """Reject invalid allowances immediately; consumers also recheck bypass mutation."""
        _allowances(self)


def _allowances(value):
    """Validate exact limits before payload access and detach five ordinary integers."""
    if type(value) is not LifecycleReportBindingLimits:
        raise LifecycleReportBindingArgumentError('expected exact binding limits')
    result = []
    for name, minimum, maximum in (
            ('max_input_bytes', 1, MAX_INPUT_BYTES), ('max_packet_bytes', 1, MAX_PACKET_BYTES),
            ('max_work_bytes', 1, MAX_WORK_BYTES), ('max_nodes', 0, MAX_NODES),
            ('max_depth', 0, MAX_DEPTH)):
        try:
            number = object.__getattribute__(value, name)
        except AttributeError:
            raise LifecycleReportBindingArgumentError('missing binding allowance') from None
        if type(number) is not int or not minimum <= number <= maximum:
            raise LifecycleReportBindingArgumentError('invalid binding allowance')
        result.append(number)
    return tuple(result)


def _measure(value, maximum, nodes_limit, depth_limit):
    """Count canonical bytes and serialized occurrences with bounded iterator frames.

    Only the ancestor path detects cycles: shared noncyclic objects count again.
    No copied tree, encoded container, or collection-sized traversal stack is made.
    """
    frames, ancestors = [], set()
    size = nodes = deepest = 0
    item = value
    while True:
        nodes += 1
        if nodes > nodes_limit:
            raise LifecycleReportBindingLimitError('binding value-node ceiling exceeded')
        kind = type(item)
        if kind in (dict, list):
            depth = len(frames) + 1
            deepest = max(deepest, depth)
            if depth > depth_limit:
                raise LifecycleReportBindingLimitError('binding container-depth ceiling exceeded')
            if id(item) in ancestors:
                raise LifecycleReportBindingValidationError('cyclic binding JSON')
            if len(item) > nodes_limit - nodes:
                raise LifecycleReportBindingLimitError('binding value-node ceiling exceeded')
            size += 2 + max(0, len(item) - 1)
            ancestors.add(id(item))
            frames.append((item, iter(item.items() if kind is dict else item)))
        elif kind is str:
            if len(item) + 2 > maximum - size:
                raise LifecycleReportBindingLimitError('binding canonical byte ceiling exceeded')
            size += control._string_size(item)
        elif item is None:
            size += 4
        elif kind is bool:
            size += 4 if item else 5
        elif kind is int:
            if not -(2**63) <= item < 2**63:
                raise LifecycleReportBindingValidationError('binding integer outside storage range')
            size += len(str(item))
        elif kind is float and math.isfinite(item):
            size += len(control.canonical(item))
        else:
            raise LifecycleReportBindingValidationError('unsupported binding JSON value')
        if size > maximum:
            raise LifecycleReportBindingLimitError('binding canonical byte ceiling exceeded')
        while frames:
            parent, iterator = frames[-1]
            try:
                child = next(iterator)
            except StopIteration:
                ancestors.remove(id(parent))
                frames.pop()
                continue
            if type(parent) is dict:
                key, item = child
                if type(key) is not str:
                    raise LifecycleReportBindingValidationError('binding keys require ordinary strings')
                if len(key) + 3 > maximum - size:
                    raise LifecycleReportBindingLimitError('binding canonical byte ceiling exceeded')
                size += control._string_size(key) + 1
                if size > maximum:
                    raise LifecycleReportBindingLimitError('binding canonical byte ceiling exceeded')
            else:
                item = child
            break
        else:
            return size, nodes, deepest


def _scan(text, nodes_limit, depth_limit):
    """Bound complete-input tokens and container nesting before strict JSON parsing.

    Quoted object keys are not value nodes. Syntax remains the strict parser's job;
    malformed input cannot use an unchecked suffix to allocate a large parse tree.
    """
    stack, nodes = [], 0
    quoted = escaped = scalar = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char in ' \t\r\n':
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
            quoted, scalar = True, False
            nodes += not key
        elif char in '[{':
            nodes += 1
            if len(stack) >= depth_limit:
                raise LifecycleReportBindingLimitError('binding lexical depth ceiling exceeded')
            stack.append([char, char == '{'])
            scalar = False
        elif not scalar:
            nodes += 1
            scalar = True
        if nodes > nodes_limit:
            raise LifecycleReportBindingLimitError('binding lexical node ceiling exceeded')


def _pairs(pairs):
    """Reject duplicate JSON fields at every level without reporting their contents."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise LifecycleReportBindingValidationError('duplicate binding JSON field')
        result[key] = value
    return result


def _constant(value):
    """Reject nonfinite JSON literals before they enter a detached tree."""
    raise LifecycleReportBindingValidationError('nonfinite binding JSON number')


def _parse(data, allowance):
    """Check raw UTF-8 length and reserve 8R before decoding, scanning and parsing."""
    input_limit, _, work_limit, nodes_limit, depth_limit = allowance
    if len(data) > input_limit:
        raise LifecycleReportBindingLimitError('binding input byte ceiling exceeded')
    raw_size = len(data)
    if type(data) is str:
        raw_size = 0
        for char in data:
            number = ord(char)
            if 0xD800 <= number <= 0xDFFF:
                raise LifecycleReportBindingValidationError('invalid binding Unicode')
            raw_size += 1 if number < 128 else 2 if number < 2048 else 3 if number < 65536 else 4
            if raw_size > input_limit:
                raise LifecycleReportBindingLimitError('binding input byte ceiling exceeded')
    if 8 * raw_size > work_limit:
        raise LifecycleReportBindingLimitError('binding raw workspace ceiling exceeded')
    try:
        text = data.decode('utf-8') if type(data) is bytes else data
        _scan(text, nodes_limit, depth_limit)
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        return value, raw_size
    except LifecycleReportBindingLimitError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise LifecycleReportBindingValidationError('invalid binding JSON') from None


def _wrapper(preparation, transition, obligation):
    """Assemble fixed wrapper overhead with equal-length digest placeholders only."""
    return {'format': _FORMAT, 'version': 1, 'preparation': preparation,
            'transition': transition, 'obligation': obligation,
            'preparation_digest': '0' * 64, 'transition_digest': '0' * 64,
            'obligation_digest': '0' * 64, 'ordinary_work_allowed': False,
            'recheck_required': True}


def _projected_references(content, obligation):
    """Stream projection inputs before any RecordReference can be constructed.

    The accepted _transition_references generator constructs the run reference.
    Spell out that fixed prefix as wire data for preflight, and reuse its declaration
    traversal. The accepted decoder later verifies the actual full projection.
    """
    if obligation:
        yield content['transition']
        yield from content['selection']
        return
    request = content['request']
    if request['predecessor'] is not None:
        yield request['predecessor']['reference']
    if content['prepared_from'] is not None:
        yield content['prepared_from']
    yield {'record_id': request['run_id'], 'revision': request['run_revision'],
           'relationship': 'run', 'target_kind': 'run'}
    preparation = request['preparation']
    if preparation is not None:
        for name in ('project', 'initial_corpus', 'current_corpus'):
            yield preparation[name]
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
    yield from control._declaration_references(request['report']['declarations'])
    yield content['obligation']


def _projection_preflight(envelope, obligation):
    """Meter expected complete envelopes even when supplied projections are too short."""
    content = envelope['content']
    request = content if obligation else content['request']
    # Identity hashing is deferred: every derived identity has a fixed ASCII size.
    skeleton = {'record_id': ('run-control-obligation-' if obligation else 'run-control-') + '0' * 64,
        'revision': 1 if obligation else request['revision'], 'kind': 'event', 'content': content,
        'provenance': {'actor': envelope['provenance']['actor'] if obligation else request['actor'],
                       'created_at': request['required_at'] if obligation else request['transitioned_at'], 'details': {}},
        'record_references': [], 'artifact_references': [],
        'operational_status': None, 'scientific_disposition': None}
    size, nodes, depth = _measure(skeleton, control.TRANSITION_BYTES, control.JSON_NODES, control.JSON_DEPTH)
    count = 0
    for ref in _projected_references(content, obligation):
        ref_size, ref_nodes, ref_depth = _measure(ref, control.TRANSITION_BYTES, control.JSON_NODES, control.JSON_DEPTH)
        size += ref_size + bool(count)
        nodes += ref_nodes
        depth = max(depth, 2 + ref_depth)
        count += 1
        # For canonical references this is content_nodes + 12 + 5 * count;
        # using actual sizes also keeps malformed projection inputs bounded.
        if size > control.TRANSITION_BYTES or nodes > control.JSON_NODES or depth > control.JSON_DEPTH:
            raise LifecycleReportBindingLimitError('binding projected envelope ceiling exceeded')


def _fragments(value):
    """Enforce inherited structural ceilings before invoking nested domain codecs."""
    for name in _MEMBERS:
        envelope = value[name]
        _measure(envelope, control.TRANSITION_BYTES, control.JSON_NODES, control.JSON_DEPTH)
        content = envelope['content']
        _measure(content, control.SMALL_BYTES if name == 'obligation' else control.TRANSITION_BYTES,
                 control.JSON_NODES, control.JSON_DEPTH)
        _measure(envelope['provenance']['details'], control.SMALL_BYTES, control.JSON_NODES, control.JSON_DEPTH)
        if name != 'obligation':
            request = content['request']
            _measure(request, control.REQUEST_BYTES, control.JSON_NODES, control.JSON_DEPTH)
            _measure(request['report'], control.SMALL_BYTES, control.JSON_NODES, 32)
            preparation = request['preparation']
            if type(preparation) is dict and 'operating_scope' in preparation:
                _measure(preparation['operating_scope'], control.authority.RESULT_BYTES,
                         control.authority.JSON_NODES, control.authority.JSON_DEPTH)
    for name in _MEMBERS:
        _projection_preflight(value[name], name == 'obligation')


def _envelope(value):
    """Require complete canonical wire fields, including formerly optional defaults."""
    control.authority.exact(value, _ENVELOPE_FIELDS)
    control.authority.exact(value['provenance'], 'actor created_at details')
    envelope = RecordEnvelope.from_dict(value)
    if control.canonical(envelope.to_dict()) != control.canonical(value):
        raise LifecycleReportBindingValidationError('noncanonical binding envelope')
    return envelope


def _semantics(value, derive):
    """Validate local pairing using accepted contracts; hashes do not authenticate facts."""
    control.authority.exact(value, _FIELDS)
    if (value['format'] != _FORMAT or type(value['version']) is not int or value['version'] != 1 or
            value['ordinary_work_allowed'] is not False or value['recheck_required'] is not True):
        raise LifecycleReportBindingValidationError('invalid binding wrapper')
    preparation = _envelope(value['preparation'])
    original = control.decode_transition(preparation).to_dict()
    transition = _envelope(value['transition'])
    selected = control.decode_transition(transition).to_dict()
    obligation = _envelope(value['obligation'])
    control.decode_obligation(obligation)
    first, request = original['request'], selected['request']
    if first['action'] != 'prepare' or first['revision'] != 1:
        raise LifecycleReportBindingValidationError('binding requires original preparation')
    control.validate_successor(None, original)
    if (request['run_id'] != first['run_id'] or request['run_revision'] < first['run_revision'] or
            request['transitioned_at'] < first['transitioned_at'] or
            first['revision'] > control.capacity(first['action']) or
            request['revision'] > control.capacity(request['action'])):
        raise LifecycleReportBindingValidationError('binding original selection mismatch')
    if request['revision'] == 1:
        if control.canonical(value['preparation']) != control.canonical(value['transition']):
            raise LifecycleReportBindingValidationError('binding initial copies disagree')
    else:
        if request['operation_id'] == first['operation_id']:
            raise LifecycleReportBindingValidationError('binding operation identity reused')
        if request['revision'] == 2:
            control.validate_successor((preparation, original), selected)
        # Higher revisions omit the intervening prefix. The prepared_from link is
        # an identity reference, not a cryptographic commitment to that history.
    if request['action'] == 'continue' and selected['authorization']['policy_fingerprint'] != original['authorization']['policy_fingerprint']:
        raise LifecycleReportBindingValidationError('binding continuation policy mismatch')
    control.paired_obligation(selected, transition, obligation)
    if obligation.content != control.obligation_document(selected):
        raise LifecycleReportBindingValidationError('binding obligation mismatch')
    result = dict(value) if derive else value
    for name, envelope in zip(_MEMBERS, (preparation, transition, obligation)):
        digest = control.envelope_digest(envelope)
        if derive:
            result[name + '_digest'] = digest
        else:
            control.authority.digest(value[name + '_digest'])
            if digest != value[name + '_digest']:
                raise LifecycleReportBindingValidationError('binding envelope digest mismatch')
    return result


def _normalize(value, allowance, raw_size=0, *, derive=False):
    """Reserve the complete published charge before sequential semantic reconstruction."""
    try:
        _, packet_limit, work_limit, nodes_limit, depth_limit = allowance
        size, _, _ = _measure(value, packet_limit, nodes_limit, depth_limit)
        if 8 * raw_size + 64 * size > work_limit:
            raise LifecycleReportBindingLimitError('binding workspace ceiling exceeded')
        # This fixed conservative representation reserve is independent of cache
        # hits and allocator details. No intermediate validation history is retained.
        _fragments(value)
        sizes = [_measure(value[name], control.TRANSITION_BYTES, control.JSON_NODES, control.JSON_DEPTH)[0]
                 for name in _MEMBERS]
        skeleton_size = _measure(_wrapper(None, None, None), MAX_PACKET_BYTES, MAX_NODES, MAX_DEPTH)[0]
        result = _semantics(value, derive)
        # Exact closed wrappers have three null slots (12 bytes); every envelope
        # occurrence is charged, even when preparation and transition are aliases.
        if size != skeleton_size - 12 + sum(sizes):
            raise LifecycleReportBindingValidationError('noncanonical binding wrapper size')
        return result, control.canonical(result)
    except (LifecycleReportBindingArgumentError, LifecycleReportBindingLimitError):
        raise
    except control.RunControlLimitError:
        raise LifecycleReportBindingLimitError('inherited binding structural ceiling exceeded') from None
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        raise LifecycleReportBindingValidationError('invalid lifecycle binding content') from None


def _retain(text):
    """Retain an already validated string without a second public accounting pass."""
    value = object.__new__(LifecycleReportBinding)
    object.__setattr__(value, '_json', text)
    return value


def _consume(value, allowance):
    """Revalidate exact retained state and require byte-for-byte canonical identity."""
    if type(value) is not LifecycleReportBinding:
        raise LifecycleReportBindingArgumentError('expected exact lifecycle binding')
    try:
        text = object.__getattribute__(value, '_json')
    except AttributeError:
        raise LifecycleReportBindingValidationError('missing retained binding content') from None
    if type(text) is not str:
        raise LifecycleReportBindingValidationError('invalid retained binding content type')
    document, raw_size = _parse(text, allowance)
    document, normalized = _normalize(document, allowance, raw_size)
    if text != normalized:
        raise LifecycleReportBindingValidationError('noncanonical retained binding content')
    return document, normalized


@dataclass(frozen=True, init=False, repr=False, eq=False)
class LifecycleReportBinding:
    """Detached local intent packet retaining only private canonical JSON, never authority."""
    _json: str

    def __init__(self, document: dict, *, limits: LifecycleReportBindingLimits):
        """Validate a complete wire dictionary under explicit independent allowances."""
        allowance = _allowances(limits)
        if type(self) is not LifecycleReportBinding or type(document) is not dict:
            raise LifecycleReportBindingArgumentError('expected exact binding and dictionary')
        _, text = _normalize(document, allowance)
        object.__setattr__(self, '_json', text)

    @classmethod
    def from_dict(cls, document: dict, *, limits: LifecycleReportBindingLimits) -> 'LifecycleReportBinding':
        """Construct only the exact binding class from a complete detached wire dictionary."""
        allowance = _allowances(limits)
        if cls is not LifecycleReportBinding or type(document) is not dict:
            raise LifecycleReportBindingArgumentError('expected exact binding class and dictionary')
        return _retain(_normalize(document, allowance)[1])

    def to_dict(self, *, limits: LifecycleReportBindingLimits) -> dict:
        """Revalidate retained state and return an isolated tree within fresh allowances."""
        allowance = _allowances(limits)
        return _consume(self, allowance)[0]


def bind_lifecycle_report(preparation: dict, transition: dict, obligation: dict, *,
                          limits: LifecycleReportBindingLimits) -> LifecycleReportBinding:
    """Bind three complete envelope dictionaries, deriving hashes after all preflights."""
    allowance = _allowances(limits)
    if any(type(value) is not dict for value in (preparation, transition, obligation)):
        raise LifecycleReportBindingArgumentError('binding factory requires exact dictionaries')
    return _retain(_normalize(_wrapper(preparation, transition, obligation), allowance, derive=True)[1])


def dumps_binding(value: LifecycleReportBinding, *, limits: LifecycleReportBindingLimits) -> str:
    """Return revalidated canonical ASCII JSON using fresh retained-input allowances."""
    allowance = _allowances(limits)
    return _consume(value, allowance)[1]


def loads_binding(data: str | bytes, *, limits: LifecycleReportBindingLimits) -> LifecycleReportBinding:
    """Decode strict bounded UTF-8 JSON and retain canonical local intent only."""
    allowance = _allowances(limits)
    if type(data) not in (str, bytes):
        raise LifecycleReportBindingArgumentError('binding decoder requires ordinary str or bytes')
    value, raw_size = _parse(data, allowance)
    return _retain(_normalize(value, allowance, raw_size)[1])


def binding_digest(value: LifecycleReportBinding, *, limits: LifecycleReportBindingLimits) -> str:
    """Hash the revalidated complete canonical packet; this is identity, not authenticity."""
    allowance = _allowances(limits)
    return hashlib.sha256(_consume(value, allowance)[1].encode('ascii')).hexdigest()
