"""Bounded detached lifecycle source facts; consistency never establishes permission.

Only the connection-owned capture module can establish commitment. These closed
codecs also accept uncommitted observations, with independent processing budgets.
"""

from dataclasses import dataclass, fields
import hashlib

from research_pipeline import lifecycle_report_binding as binding
from research_pipeline import run_control as control, reports
from research_pipeline.domain import (
    DomainValidationError, ArtifactReference, RecordEnvelope, RecordReference,
    SubmissionReceipt, _identifier, _integer, _timestamp,
)
from research_pipeline.snapshot import DetachedSnapshot, SnapshotLimitError, _commit


class LifecycleSourceArgumentError(ValueError):
    """An explicit argument or independently supplied allowance has an invalid type/value."""


class LifecycleSourceValidationError(DomainValidationError):
    """Detached source content is malformed, contradictory, or retained noncanonically."""


class LifecycleSourceLimitError(ValueError):
    """A named stage exceeds an explicit independent processing allowance."""


class LifecycleSourceIntegrityError(ValueError):
    """Persisted source, evidence, or original submission metadata is inconsistent."""


class LifecycleSourceStateError(ValueError):
    """Fresh capture cannot establish an admissible source state or actual capture time."""


@dataclass(frozen=True, kw_only=True)
class LifecycleScientificCaptureLimits:
    """Bound complete scientific closure and its representation work, excluding planner files."""
    max_roots: int
    max_records: int
    max_references: int
    max_record_bytes: int
    max_metadata_bytes: int
    max_artifacts: int
    max_file_bytes: int
    max_total_bytes: int
    max_work_bytes: int

    def __post_init__(self):
        """Reject invalid allowances immediately; consumers independently revalidate them."""
        _scalars(self, LifecycleScientificCaptureLimits)


@dataclass(frozen=True, kw_only=True)
class LifecycleResourceCaptureLimits:
    """Authorize complete replay counts, SQL rows, references, representations, and work."""
    max_accounts: int
    max_operations: int
    max_rows: int
    max_references: int
    max_record_bytes: int
    max_metadata_bytes: int
    max_result_bytes: int
    max_work_bytes: int

    def __post_init__(self):
        """Reject invalid explicit resource budgets without inspecting a payload or store."""
        _scalars(self, LifecycleResourceCaptureLimits)


@dataclass(frozen=True, kw_only=True)
class LifecycleSourceLimits:
    """Independent control, binding, capture, artifact, codec and enclosing-wrapper ceilings."""
    control: control.RunControlLimits
    binding: binding.LifecycleReportBindingLimits
    scientific: LifecycleScientificCaptureLimits
    resources: LifecycleResourceCaptureLimits
    max_artifacts: int
    max_artifact_bytes: int
    max_artifact_total_bytes: int
    max_input_bytes: int
    max_source_bytes: int
    max_submission_bytes: int
    max_result_bytes: int
    max_work_bytes: int
    max_nodes: int
    max_depth: int

    def __post_init__(self):
        """Validate all independent nested allowances before any content can be consumed."""
        _scalars(self, LifecycleSourceLimits)
        _nested(self)


def _scalars(value, cls):
    """Validate exact limit classes and ordinary SQLite-range integers without coercion."""
    if type(value) is not cls:
        raise LifecycleSourceArgumentError('expected exact source limits')
    result = {}
    zero = {'max_references', 'max_artifacts', 'max_accounts', 'max_operations',
            'max_rows', 'max_total_bytes', 'max_artifact_total_bytes', 'max_nodes', 'max_depth'}
    wide = {'max_work_bytes', 'max_file_bytes', 'max_total_bytes',
            'max_artifact_bytes', 'max_artifact_total_bytes'}
    for field in fields(cls):
        name = field.name
        if name in ('control', 'binding', 'scientific', 'resources'):
            continue
        try:
            number = object.__getattribute__(value, name)
        except AttributeError:
            raise LifecycleSourceArgumentError('missing source allowance') from None
        maximum = (96 if name == 'max_depth' else 2**63 - 1 if name in wide else
                   64 * 1024 * 1024 if name.endswith('_bytes') else 1048576)
        if type(number) is not int or not (0 if name in zero else 1) <= number <= maximum:
            raise LifecycleSourceArgumentError('invalid source allowance')
        result[name] = number
    return result


def _nested(value):
    """Detach inherited and source-specific limits, including bypass-mutated nested instances."""
    try:
        c = control.checked_limits(value.control)
        b = binding.LifecycleReportBindingLimits(**dict(zip(
            ('max_input_bytes', 'max_packet_bytes', 'max_work_bytes', 'max_nodes', 'max_depth'),
            binding._allowances(value.binding))))
        s = LifecycleScientificCaptureLimits(**_scalars(value.scientific, LifecycleScientificCaptureLimits))
        r = LifecycleResourceCaptureLimits(**_scalars(value.resources, LifecycleResourceCaptureLimits))
    except (ValueError, AttributeError, TypeError):
        raise LifecycleSourceArgumentError('invalid nested source allowance') from None
    return dict(control=c, binding=b, scientific=s, resources=r)


def _limits(value):
    """Reconstruct all limits at each public boundary, before argument or payload inspection."""
    scalars = _scalars(value, LifecycleSourceLimits)
    return LifecycleSourceLimits(**scalars, **_nested(value))


QUALIFICATIONS = [
    'This is a committed source observation, not a rendered or published report.',
    'The observation records the actual first-capture snapshot; it does not reconstruct state at the selected transition time.',
    'Original declarations and known gaps remain attributed input; missing execution, job, charge, and scientific interpretation evidence is not inferred.',
    'All required report obligations remain pending and ordinary work remains prohibited.',
    'Historical authority evidence does not establish current permission.',
]
FORMATS = tuple('research_pipeline.lifecycle_source_' + name for name in
                ('observation', 'event', 'commit_result', 'inspection'))


def _measure(value, maximum, limits):
    """Share allocation-free occurrence/framing measurement without changing binding allowances."""
    try:
        return binding._measure(value, maximum, limits.max_nodes, limits.max_depth)[0]
    except binding.LifecycleReportBindingLimitError:
        raise LifecycleSourceLimitError('source canonical/node/depth ceiling exceeded') from None
    except (ValueError, TypeError, UnicodeError):
        raise LifecycleSourceValidationError('invalid source JSON tree') from None


def _parse(data, limits):
    """Reserve raw UTF-8 input and lexical work before strict duplicate-free JSON decoding."""
    try:
        return binding._parse(data, (limits.max_input_bytes, limits.max_source_bytes,
            limits.max_work_bytes, limits.max_nodes, limits.max_depth))
    except binding.LifecycleReportBindingLimitError:
        raise LifecycleSourceLimitError('source input/lexical workspace ceiling exceeded') from None
    except ValueError:
        raise LifecycleSourceValidationError('invalid source JSON') from None


def _hash(value):
    """Hash an already measured canonical ASCII representation using the existing convention."""
    return hashlib.sha256(control.canonical(value).encode('ascii')).hexdigest()


def _identity(operation):
    """Validate the original control ID and derive the distinct immutable source submission ID."""
    if type(operation) is not str:
        raise LifecycleSourceArgumentError('expected ordinary control operation identity')
    try:
        _identifier(operation, 'control operation')
    except ValueError:
        raise LifecycleSourceArgumentError('invalid control operation identity') from None
    return control._identity('run-control-source-', operation)


def _digest(value):
    """Validate an exact lowercase SHA-256 argument without exposing its value in diagnostics."""
    try:
        control.authority.digest(value)
    except (ValueError, TypeError):
        raise LifecycleSourceArgumentError('invalid expected binding digest') from None


def _intent(packet):
    """Extract only common scope inputs; this is neither a ReportRequest nor a continuation."""
    preparation = packet['preparation']['content']['request']['preparation']
    selected = packet['transition']['content']['request']
    return {'project': preparation['project'], 'run': control.reference(
        selected['run_id'], selected['run_revision'], 'run', 'run'),
        'context': preparation['context'], **selected['report']}


def _categories(packet, inspection, resources):
    """Preserve category occurrences and original intent separately from later bookkeeping roots."""
    from research_pipeline.resource_ledger import references
    preparation = packet['preparation']['content']['request']['preparation']
    baseline = preparation['start_baseline']
    return {'scientific': reports._scientific_roots(_intent(packet)),
            'dossier': [preparation['initial_corpus'], preparation['current_corpus']],
            'saved_baseline': [baseline] if 'record_id' in baseline else [],
            'control_history': [inspection['head']],
            'resource_evidence': [ref for item in resources.get('operations', [])
                                  for ref in references(item['request'])]}


def _artifact_inventory(references, limits):
    """Check distinct required artifacts before opening bytes; conflicting sizes always reject."""
    inventory = {}
    total = 0
    for reference in references:
        control.authority.exact(reference, 'digest size')
        ref = ArtifactReference(**reference)
        if ref.digest in inventory:
            if inventory[ref.digest] != ref.size:
                raise LifecycleSourceValidationError('conflicting source artifact sizes')
            continue
        inventory[ref.digest] = ref.size
        total += ref.size
        if (len(inventory) > limits.max_artifacts or ref.size > limits.max_artifact_bytes or
                total > limits.max_artifact_total_bytes):
            raise LifecycleSourceLimitError('source artifact inventory ceiling exceeded')
    return inventory


def _scientific_preflight(value, limits, original):
    """Bound fetched metadata and canonical record sizes independently before detached reconstruction."""
    s = limits.scientific
    maximum = min(s.max_metadata_bytes, original['max_metadata_bytes'])
    if 64 * maximum + 4096 > s.max_work_bytes:
        raise LifecycleSourceLimitError('scientific workspace ceiling exceeded')
    size = _measure(value, maximum, limits)
    if size + value['metadata_fetched_bytes'] > maximum:
        raise LifecycleSourceLimitError('scientific metadata ceiling exceeded')
    if value['limits'] != original:
        raise LifecycleSourceValidationError('scientific original limits mismatch')
    if (len(value['records']) > min(s.max_records, original['max_records']) or
            len(value['artifacts']) > min(s.max_artifacts, original['max_artifacts']) or
            len(value['selection']['roots']) + 1 > min(s.max_roots, original['max_roots'])):
        raise LifecycleSourceLimitError('scientific counts ceiling exceeded')
    refs = total = 0
    for record in value['records']:
        _integer(record['fetched_bytes'], 'scientific fetched bytes', 1)
        if record['fetched_bytes'] > min(s.max_record_bytes, original['max_record_bytes']):
            raise LifecycleSourceLimitError('scientific fetched record ceiling exceeded')
        _measure(record, min(s.max_record_bytes, original['max_record_bytes']), limits)
        # Nested envelope JSON is another decoding boundary, even inside canonical
        # outer strings. Independent lexical checks precede domain reconstruction.
        try:
            envelope, _ = binding._parse(record['envelope_json'], (
                min(s.max_record_bytes, original['max_record_bytes']), maximum,
                s.max_work_bytes, limits.max_nodes, min(65, limits.max_depth)))
        except binding.LifecycleReportBindingLimitError:
            raise LifecycleSourceLimitError('scientific nested JSON ceiling exceeded') from None
        refs += len(envelope['record_references']) + len(envelope['artifact_references'])
        if refs > min(s.max_references, original['max_references']):
            raise LifecycleSourceLimitError('scientific references ceiling exceeded')
    for artifact in value['artifacts']:
        total += artifact['size']
        if (artifact['size'] > min(s.max_file_bytes, original['max_file_bytes']) or
                total > min(s.max_total_bytes, original['max_total_bytes'])):
            raise LifecycleSourceLimitError('scientific artifact bytes ceiling exceeded')


class _ResourceMembership:
    """Bound request-declared identities and references without performing resource accounting."""

    def __init__(self, limits, original):
        """Track unique declarations under caller and original account/operation ceilings."""
        self.limits, self.original = limits, original
        self.operations = set()
        self.declarations = {key: {} for key in ('accounts', 'allocations', 'reservations')}
        self.balances = set()
        self.links = []
        self.references = 0

    def add(self, request):
        """Validate one bounded request, authorize occurrences, and retain only structural membership."""
        from research_pipeline import resources, resource_ledger as ledger
        # Count occurrences before any helper concatenates reference lists. A
        # projection with deleted links cannot authorize request-driven queries.
        for key in ('policy_references', 'evidence_references'):
            if type(request[key]) is not list:
                raise LifecycleSourceValidationError('invalid resource reference list')
        scope = request['payload'].get('scope')
        self.references += (len(request['policy_references']) + len(request['evidence_references']) +
                            int(scope is not None and scope.get('type') == 'record'))
        if self.references > self.limits.max_references:
            raise LifecycleSourceLimitError('resource request references ceiling exceeded')
        validated = resources.ResourceRequest.from_dict(request)
        if validated._json != control.canonical(request):
            raise LifecycleSourceValidationError('noncanonical resource request')
        operation = request['operation_id']
        if operation in self.operations:
            raise LifecycleSourceValidationError('duplicate resource operation membership')
        self.operations.add(operation)
        if len(self.operations) > min(self.limits.max_operations, self.original['max_operations']):
            raise LifecycleSourceLimitError('resource request operations ceiling exceeded')
        kind, payload = request['kind'], request['payload']
        declarations = []
        if kind in ('create_account', 'allocate'):
            declarations.append(('accounts', payload['account_id']))
            purposes = ('total',) if payload['scope']['kind'] == 'project' else resources.PURPOSES
            self.balances.update((payload['account_id'], purpose) for purpose in purposes)
        if kind == 'allocate':
            declarations.append(('allocations', payload['allocation_id']))
        if kind == 'reserve':
            declarations.append(('reservations', payload['reservation_id']))
        for key, identity in declarations:
            if identity in self.declarations[key]:
                raise LifecycleSourceValidationError('duplicate resource declaration membership')
            self.declarations[key][identity] = operation
        if len(self.declarations['accounts']) > min(self.limits.max_accounts, self.original['max_accounts']):
            raise LifecycleSourceLimitError('resource request accounts ceiling exceeded')
        self.links.extend(ledger._link_rows(request))

    def reconcile(self, key, rows):
        """Require unique identity/owner pairs to equal request declarations before shared replay."""
        actual = {}
        for identity, operation in rows:
            if identity in actual:
                raise LifecycleSourceValidationError('duplicate resource projection membership')
            actual[identity] = operation
        if actual != self.declarations[key]:
            raise LifecycleSourceValidationError('resource declaration membership mismatch')

    def work(self, size):
        """Authorize full replay using request-derived account and operation counts, including empty overhead."""
        required = (256 * (size + 1) + 262144 * (len(self.declarations['accounts']) + 1) *
                    (len(self.operations) + 1))
        if required > self.limits.max_work_bytes:
            raise LifecycleSourceLimitError('resource replay workspace ceiling exceeded')


def _resource_preflight(value, limits, original):
    """Measure complete projections, reconcile request membership, then authorize shared accounting."""
    r = limits.resources
    size = _measure(value, min(r.max_result_bytes, r.max_metadata_bytes, original['max_metadata_bytes']), limits)
    if 256 * (size + 1) > r.max_work_bytes:
        raise LifecycleSourceLimitError('resource metadata workspace ceiling exceeded')
    if 'operations' not in value:
        # The inherited validator checks the exact schema-2 unavailable value.
        _ResourceMembership(r, original).work(size)
        return
    rows = 0
    for key in ('operations', 'accounts', 'allocations', 'reservations',
                'reservation_usage', 'breaches', 'balances'):
        if type(value[key]) is not list:
            raise LifecycleSourceValidationError('invalid resource projection array')
        rows += len(value[key])
        if rows > r.max_rows:
            raise LifecycleSourceLimitError('resource rows ceiling exceeded')
        for row in value[key]:
            _measure(row, r.max_record_bytes, limits)
    if (len(value['operations']) > min(r.max_operations, original['max_operations']) or
            len(value['accounts']) > min(r.max_accounts, original['max_accounts'])):
        raise LifecycleSourceLimitError('resource counts ceiling exceeded')
    membership = _ResourceMembership(r, original)
    from research_pipeline.resources import ResourceReceipt
    for item in value['operations']:
        control.authority.exact(item, 'request receipt')
        for key in ('request', 'receipt'):
            _measure(item[key], min(65536, r.max_record_bytes), limits)
        membership.add(item['request'])
        ResourceReceipt.from_dict(item['receipt'])
    # Authorize independently derived work even if supplied declarations are
    # inconsistent. Missing rows must never lower the account multiplier.
    membership.work(size)
    for key, identity in (('accounts', 'account_id'), ('allocations', 'allocation_id'),
                          ('reservations', 'reservation_id')):
        membership.reconcile(key, ((item[identity], item['operation_id']) for item in value[key]))
    usage = [item['reservation_id'] for item in value['reservation_usage']]
    balances = [(item['account_id'], item['purpose']) for item in value['balances']]
    if (len(usage) != len(set(usage)) or set(usage) != set(membership.declarations['reservations']) or
            len(balances) != len(set(balances)) or set(balances) != membership.balances):
        raise LifecycleSourceValidationError('resource derived row membership mismatch')


def _control_preflight(value, limits):
    """Bound complete captured control and repeated wrappers before inherited validation."""
    c = limits.control
    size = _measure(value, c.max_result_bytes, limits)
    if size > c.metadata.max_metadata_bytes:
        raise LifecycleSourceLimitError('control retained metadata ceiling exceeded')
    if (len(value['transitions']) > c.max_transitions or
            len(value['pending_obligations']) > c.max_pending_reports):
        raise LifecycleSourceLimitError('control history ceiling exceeded')
    references = 0
    for envelope in (item for pair in zip(
            (t['envelope'] for t in value['transitions']), value['pending_obligations']) for item in pair):
        _measure(envelope, c.metadata.max_record_bytes, limits)
        references += len(envelope['record_references']) + len(envelope['artifact_references'])
    if (2 * len(value['transitions']) > c.metadata.max_records or
            len(value['transitions']) > c.metadata.max_history_revisions):
        raise LifecycleSourceLimitError('control records/history ceiling exceeded')
    if references > c.metadata.max_references:
        raise LifecycleSourceLimitError('control references ceiling exceeded')


def _capture_lower_bound(scientific, inspection, operations, complete_resource_time=None):
    """Return the latest factual date in validated, bounded capture fragments.

    The optional private scalar covers the complete resource prefix during fresh
    capture; detached callers know only retained operations. This pure reduction
    neither copies collections nor interprets narrative or policy validity dates.
    """
    latest = scientific['watermark']['committed_at']
    for record in scientific['records']:
        latest = max(latest, record['commit']['committed_at'])
    for transition in inspection['transitions']:
        latest = max(latest, transition['envelope']['content']['request']['transitioned_at'],
                     transition['receipt']['committed_at'])
    # Sequence order establishes membership, never monotonic wall-clock time.
    for operation in operations:
        latest = max(latest, operation['receipt']['committed_at'])
    if complete_resource_time is not None:
        latest = max(latest, complete_resource_time)
    return latest


def _observation(value, limits):
    """Validate source intent, exact baseline types and retained factual chronology.

    Called after enclosing measurement/work reservation, this rejects detached
    contradictions without consulting storage, current time or policy. Scientific
    scope closure receives the validated scientific occurrence inventory and the
    effective caller/original record and reference bounds, independently of the
    distinct snapshot-pin ceiling enforced before reconstruction.
    """
    control.authority.exact(value, 'format version binding binding_digest observed_at control scientific resources baseline root_categories source_bindings verified_artifacts qualifications snapshot_id ordinary_work_allowed recheck_required')
    packet = binding.LifecycleReportBinding(value['binding'], limits=limits.binding)
    if binding.binding_digest(packet, limits=limits.binding) != value['binding_digest']:
        raise LifecycleSourceValidationError('source binding digest mismatch')
    packet = value['binding']
    selected = packet['transition']['content']['request']
    original = selected['report']['limits']
    if _measure(value, limits.max_source_bytes, limits) > original['max_source_bytes']:
        raise LifecycleSourceLimitError('source original byte ceiling exceeded')
    _control_preflight(value['control'], limits)
    inspection = control.RunControlInspection(value['control']).to_dict()
    revision = selected['revision']
    if (not inspection['transitions'] or inspection['run_id'] != selected['run_id'] or
            revision > len(inspection['transitions']) or
            inspection['transitions'][0]['envelope'] != packet['preparation'] or
            inspection['transitions'][revision - 1]['envelope'] != packet['transition'] or
            inspection['pending_obligations'][revision - 1] != packet['obligation']):
        raise LifecycleSourceValidationError('source binding absent from captured history')
    _scientific_preflight(value['scientific'], limits, original['snapshot'])
    scientific = DetachedSnapshot(value['scientific']).to_dict()
    if scientific['watermark'] != inspection['watermark']:
        raise LifecycleSourceValidationError('source scientific/control watermark mismatch')
    if (_timestamp(value['observed_at']) != value['observed_at'] or
            value['observed_at'] < scientific['watermark']['committed_at'] or
            any(value['observed_at'] < t['envelope']['content']['request']['transitioned_at']
                for t in inspection['transitions'])):
        raise LifecycleSourceValidationError('source capture timestamp precedes captured facts')
    intent = _intent(packet)
    _resource_preflight(value['resources'], limits, original['resources'])
    reports._validate_resources(value['resources'], intent, scientific['schema']['version'])
    if value['observed_at'] < _capture_lower_bound(scientific, inspection,
                                                  value['resources'].get('operations', ())):
        raise LifecycleSourceValidationError('source capture timestamp precedes captured facts')
    if any(item['receipt']['scientific_watermark_event_id'] > scientific['watermark']['event_id']
           for item in value['resources'].get('operations', [])):
        raise LifecycleSourceValidationError('resource watermark exceeds scientific capture')
    categories = _categories(packet, inspection, value['resources'])
    if control.canonical(categories) != control.canonical(value['root_categories']):
        raise LifecycleSourceValidationError('source root categories mismatch')
    pins = list(dict.fromkeys(reports.pin(ref) for refs in categories.values() for ref in refs))
    selection = {'project': dict(zip(('record_id', 'revision'), pins[0])),
                 'roots': [dict(zip(('record_id', 'revision'), pin)) for pin in pins[1:]]}
    if selection != scientific['selection'] or list(selection.values())[0] != scientific['resolutions'][0]:
        raise LifecycleSourceValidationError('source exact selection mismatch')
    # Snapshot max_roots counts distinct pins; declarations retain repetitions.
    # This locally derived occurrence inventory is covered by source work/size
    # reservations and matches _check_scope's scientific roots exactly.
    reports._check_scope(intent, scientific, value['resources'], closure_bounds=(
        len(categories['scientific']),
        min(limits.scientific.max_records, original['snapshot']['max_records']),
        min(limits.scientific.max_references, original['snapshot']['max_references'])))
    baseline = packet['preparation']['content']['request']['preparation']['start_baseline']
    # Both fragments are already measured within the enclosing 64P reservation.
    # Canonical JSON preserves scalar types without a second saved-work grammar.
    if control.canonical(value['baseline']) != control.canonical(baseline):
        raise LifecycleSourceValidationError('source baseline mismatch')
    envelopes = reports._envelopes(scientific)
    if 'record_id' in baseline:
        from research_pipeline.work_product import decode_envelope
        decode_envelope(envelopes[reports.pin(baseline)])
    for transition, obligation in zip(inspection['transitions'], inspection['pending_obligations']):
        for envelope in (transition['envelope'], obligation):
            actual = envelopes.get(reports.pin(envelope))
            if actual is None or actual.to_dict() != envelope:
                raise LifecycleSourceValidationError('captured history differs from scientific closure')
    bindings = value['source_bindings']
    if type(bindings) is not list or len(bindings) != len(scientific['records']):
        raise LifecycleSourceValidationError('source membership length mismatch')
    seen, events, submissions, by_pin = set(), {}, {}, {}
    for entry, record in zip(bindings, scientific['records']):
        control.authority.exact(entry, 'record_id revision event_id ordinal')
        _identifier(entry['record_id'], 'source binding record')
        _integer(entry['revision'], 'source binding revision', 1)
        if reports.pin(entry) != reports.pin(record):
            raise LifecycleSourceValidationError('source membership order mismatch')
        for key, minimum in (('event_id', 1), ('ordinal', 0)):
            if type(entry[key]) is not int or not minimum <= entry[key] < 2**63:
                raise LifecycleSourceValidationError('invalid source membership scalar')
        if entry['event_id'] > scientific['watermark']['event_id']:
            raise LifecycleSourceValidationError('source member exceeds captured watermark')
        membership = entry['event_id'], entry['ordinal']
        commit = record['commit']
        sid = commit['submission_id']
        if (membership in seen or events.setdefault(entry['event_id'], commit) != commit or
                submissions.setdefault(sid, entry['event_id']) != entry['event_id']):
            raise LifecycleSourceValidationError('contradictory source membership/audit bindings')
        seen.add(membership)
        by_pin[reports.pin(entry)] = entry, commit
        if sid == scientific['watermark']['submission_id'] and entry['event_id'] != scientific['watermark']['event_id']:
            raise LifecycleSourceValidationError('source binding differs from scientific watermark')
    previous_event = 0
    for transition, obligation in zip(inspection['transitions'], inspection['pending_obligations']):
        receipt = transition['receipt']
        if receipt['event_id'] <= previous_event:
            raise LifecycleSourceValidationError('control audit order mismatch')
        previous_event = receipt['event_id']
        for ordinal, envelope in enumerate((transition['envelope'], obligation)):
            entry, commit = by_pin[reports.pin(envelope)]
            if (entry['event_id'] != receipt['event_id'] or entry['ordinal'] != ordinal or
                    commit != {k: receipt[k] for k in ('submission_id', 'committed_at', 'fingerprint')}):
                raise LifecycleSourceValidationError('control receipt differs from captured original member')
    from research_pipeline.resource_ledger import references
    for item in value['resources'].get('operations', []):
        for ref in references(item['request']):
            if (envelopes[reports.pin(ref)].kind != ref['target_kind'] or
                    by_pin[reports.pin(ref)][0]['event_id'] > item['receipt']['scientific_watermark_event_id']):
                raise LifecycleSourceValidationError('resource reference exceeds original receipt watermark')
    verified = [{'digest': a['digest'], 'size': a['size']} for a in scientific['artifacts']]
    if type(value['verified_artifacts']) is not list:
        raise LifecycleSourceValidationError('invalid verified artifact inventory')
    _artifact_inventory(value['verified_artifacts'], limits)
    if value['verified_artifacts'] != verified:
        raise LifecycleSourceValidationError('verified artifact inventory mismatch')
    if value['qualifications'] != QUALIFICATIONS:
        raise LifecycleSourceValidationError('source qualifications mismatch')
    if _hash({k: v for k, v in value.items() if k != 'snapshot_id'}) != value['snapshot_id']:
        raise LifecycleSourceValidationError('source snapshot identity mismatch')


def _result(value, limits):
    """Validate immutable source-only identities, original one-member receipt and audit order."""
    control.authority.exact(value, 'format version operation_id control_operation_id binding_digest source_event source_artifact snapshot_id observed_at scientific_watermark resource_sequence captured_control receipt ordinary_work_allowed recheck_required')
    operation = value['control_operation_id']
    if value['operation_id'] != _identity(operation):
        raise LifecycleSourceValidationError('source submission identity mismatch')
    for key in ('binding_digest', 'snapshot_id'):
        control.authority.digest(value[key])
    event = control.reference(reports.source_id(control.report_operation_id(operation)), 1,
                              'lifecycle_report_source')
    control.authority.reference(value['source_event'], 'lifecycle_report_source', 'event')
    if value['source_event'] != event:
        raise LifecycleSourceValidationError('source event identity mismatch')
    control.authority.exact(value['source_artifact'], 'digest size')
    ArtifactReference(**value['source_artifact'])
    _commit(value['scientific_watermark'], watermark=True)
    if value['scientific_watermark']['event_id'] is None:
        raise LifecycleSourceValidationError('source requires nonempty scientific watermark')
    if _timestamp(value['observed_at']) != value['observed_at']:
        raise LifecycleSourceValidationError('noncanonical source date')
    sequence = value['resource_sequence']
    if sequence is not None and (type(sequence) is not int or not 0 <= sequence < 2**63):
        raise LifecycleSourceValidationError('invalid source resource sequence')
    captured = value['captured_control']
    control.authority.exact(captured, 'reference envelope_digest')
    control.authority.reference(captured['reference'], 'run_control', 'event')
    control.authority.digest(captured['envelope_digest'])
    _measure(value['receipt'], limits.control.metadata.max_record_bytes, limits)
    receipt = SubmissionReceipt.from_dict(value['receipt'])
    if (receipt.to_dict() != value['receipt'] or receipt.submission_id != value['operation_id'] or
            receipt.revisions != ((event['record_id'], 1),) or
            receipt.provenance.to_dict() != {'actor': 'lifecycle-source-controller',
                'created_at': value['observed_at'], 'details': {}} or
            receipt.event_id != value['scientific_watermark']['event_id'] + 1 or
            value['observed_at'] < value['scientific_watermark']['committed_at'] or
            receipt.committed_at < value['observed_at']):
        raise LifecycleSourceValidationError('source receipt/provenance/watermark mismatch')


def _inspection(value, limits):
    """Validate metadata-only intent/commit state without certifying artifact byte availability."""
    control.authority.exact(value, 'format version control_operation_id binding_digest obligation state result artifact_verification ordinary_work_allowed recheck_required')
    operation = value['control_operation_id']
    _identity(operation)
    control.authority.digest(value['binding_digest'])
    _measure(value['obligation'], limits.control.metadata.max_record_bytes, limits)
    envelope = binding._envelope(value['obligation'])
    obligation = control.decode_obligation(envelope).to_dict()
    if (obligation['operation_id'] != operation or value['artifact_verification'] != 'not_checked' or
            value['state'] not in ('durable_intent', 'committed_source')):
        raise LifecycleSourceValidationError('source inspection intent mismatch')
    if value['state'] == 'durable_intent':
        if value['result'] is not None:
            raise LifecycleSourceValidationError('durable intent has no committed result')
    else:
        _normalize(value['result'], LifecycleSourceCommitResult, limits)
        if any(value['result'][key] != value[key] for key in ('control_operation_id', 'binding_digest')):
            raise LifecycleSourceValidationError('inspection original request mismatch')
        result = value['result']
        captured = result['captured_control']['reference']
        transition = obligation['transition']
        if (captured['record_id'] != transition['record_id'] or
                captured['revision'] < transition['revision'] or
                result['source_event']['record_id'] != obligation['report_source_id'] or
                result['observed_at'] < obligation['required_at']):
            raise LifecycleSourceValidationError('inspection captured obligation mismatch')


def _normalize(value, cls, limits, raw_size=0):
    """Reserve 8R + 64P before semantic reconstruction, hashing, serialization or retention."""
    maximum = min(limits.max_result_bytes, limits.max_source_bytes) if cls is LifecycleSourceObservation else limits.max_result_bytes
    size = _measure(value, maximum, limits)
    if 8 * raw_size + 64 * size > limits.max_work_bytes:
        raise LifecycleSourceLimitError('source canonical workspace ceiling exceeded')
    try:
        name, validator = _CONTRACTS[cls]
        if (type(value) is not dict or value['format'] != 'research_pipeline.lifecycle_source_' + name or
                type(value['version']) is not int or value['version'] != 1 or
                value['ordinary_work_allowed'] is not False or value['recheck_required'] is not True):
            raise LifecycleSourceValidationError('invalid source wrapper or work gate')
        validator(value, limits)
        return value, control.canonical(value)
    except (binding.LifecycleReportBindingLimitError, control.RunControlLimitError, SnapshotLimitError,
            reports.ReportLimitError):
        raise LifecycleSourceLimitError('source inherited validation ceiling exceeded') from None
    except LifecycleSourceLimitError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        raise LifecycleSourceValidationError('invalid lifecycle source content') from None


def _retain(cls, text):
    """Retain only prevalidated canonical JSON; identity equality and non-content repr remain."""
    value = object.__new__(cls)
    object.__setattr__(value, '_json', text)
    return value


def _consume(value, cls, limits):
    """Revalidate every retained consumption, including absent or bypass-mutated private JSON."""
    if type(value) is not cls:
        raise LifecycleSourceArgumentError('expected exact source detached class')
    try:
        text = object.__getattribute__(value, '_json')
    except AttributeError:
        raise LifecycleSourceValidationError('missing retained source content') from None
    if type(text) is not str:
        raise LifecycleSourceValidationError('invalid retained source content type')
    document, raw_size = _parse(text, limits)
    result = _normalize(document, cls, limits, raw_size)
    if result[1] != text:
        raise LifecycleSourceValidationError('noncanonical retained source content')
    return result


@dataclass(frozen=True, init=False, repr=False, eq=False)
class LifecycleSourceObservation:
    """Detached complete first-capture observation; local consistency is not commitment."""
    _json: str

    def __init__(self, document: dict, *, limits: LifecycleSourceLimits):
        """Validate the complete observation under explicit independent allowances."""
        checked = _limits(limits)
        if type(self) is not LifecycleSourceObservation or type(document) is not dict:
            raise LifecycleSourceArgumentError('expected exact observation and dictionary')
        object.__setattr__(self, '_json', _normalize(document, LifecycleSourceObservation, checked)[1])

    @classmethod
    def from_dict(cls, document: dict, *, limits: LifecycleSourceLimits):
        """Construct an exact observation from bounded complete wire data."""
        checked = _limits(limits)
        if cls is not LifecycleSourceObservation or type(document) is not dict:
            raise LifecycleSourceArgumentError('expected exact observation class and dictionary')
        return _retain(cls, _normalize(document, cls, checked)[1])

    def to_dict(self, *, limits: LifecycleSourceLimits):
        """Return fresh complete data after revalidating retained bytes and all semantics."""
        return _consume(self, LifecycleSourceObservation, _limits(limits))[0]


@dataclass(frozen=True, init=False, repr=False, eq=False)
class LifecycleSourceCommitResult:
    """Immutable original metadata for the source-only submission, with no availability claim."""
    _json: str

    def __init__(self, document: dict, *, limits: LifecycleSourceLimits):
        """Validate source-only receipt, identities, dates and permanently closed work gate."""
        checked = _limits(limits)
        if type(self) is not LifecycleSourceCommitResult or type(document) is not dict:
            raise LifecycleSourceArgumentError('expected exact source result and dictionary')
        object.__setattr__(self, '_json', _normalize(document, LifecycleSourceCommitResult, checked)[1])

    @classmethod
    def from_dict(cls, document: dict, *, limits: LifecycleSourceLimits):
        """Construct an exact result without reading or certifying source artifact bytes."""
        checked = _limits(limits)
        if cls is not LifecycleSourceCommitResult or type(document) is not dict:
            raise LifecycleSourceArgumentError('expected exact result class and dictionary')
        return _retain(cls, _normalize(document, cls, checked)[1])

    def to_dict(self, *, limits: LifecycleSourceLimits):
        """Revalidate the retained original result before returning a detached copy."""
        return _consume(self, LifecycleSourceCommitResult, _limits(limits))[0]


@dataclass(frozen=True, init=False, repr=False, eq=False)
class LifecycleSourceInspection:
    """Metadata-only durable intent or reconciled committed-source state; artifacts are unchecked."""
    _json: str

    def __init__(self, document: dict, *, limits: LifecycleSourceLimits):
        """Validate the complete intent/result wrapper within independent caller bounds."""
        checked = _limits(limits)
        if type(self) is not LifecycleSourceInspection or type(document) is not dict:
            raise LifecycleSourceArgumentError('expected exact source inspection and dictionary')
        object.__setattr__(self, '_json', _normalize(document, LifecycleSourceInspection, checked)[1])

    @classmethod
    def from_dict(cls, document: dict, *, limits: LifecycleSourceLimits):
        """Construct an exact metadata-only inspection without artifact access."""
        checked = _limits(limits)
        if cls is not LifecycleSourceInspection or type(document) is not dict:
            raise LifecycleSourceArgumentError('expected exact inspection class and dictionary')
        return _retain(cls, _normalize(document, cls, checked)[1])

    def to_dict(self, *, limits: LifecycleSourceLimits):
        """Revalidate complete retained metadata, including any nested original result."""
        return _consume(self, LifecycleSourceInspection, _limits(limits))[0]


_CONTRACTS = {LifecycleSourceObservation: ('observation', _observation),
              LifecycleSourceCommitResult: ('commit_result', _result),
              LifecycleSourceInspection: ('inspection', _inspection)}


def dumps_observation(value, *, limits):
    """Return revalidated canonical ASCII observation JSON with the retained-input charge."""
    return _consume(value, LifecycleSourceObservation, _limits(limits))[1]


def loads_observation(data, *, limits):
    """Decode strict bounded str/bytes into an observation, never a store commitment."""
    checked = _limits(limits)
    if type(data) not in (str, bytes):
        raise LifecycleSourceArgumentError('source decoder requires ordinary str or bytes')
    document, raw = _parse(data, checked)
    return _retain(LifecycleSourceObservation, _normalize(document, LifecycleSourceObservation, checked, raw)[1])


def dumps_commit_result(value, *, limits):
    """Return revalidated canonical ASCII original-result JSON without artifact access."""
    return _consume(value, LifecycleSourceCommitResult, _limits(limits))[1]


def loads_commit_result(data, *, limits):
    """Decode bounded source-result JSON, rejecting ambiguous fields and noncanonical semantics."""
    checked = _limits(limits)
    if type(data) not in (str, bytes):
        raise LifecycleSourceArgumentError('source decoder requires ordinary str or bytes')
    document, raw = _parse(data, checked)
    return _retain(LifecycleSourceCommitResult, _normalize(document, LifecycleSourceCommitResult, checked, raw)[1])


def dumps_inspection(value, *, limits):
    """Return revalidated canonical ASCII metadata-only inspection JSON."""
    return _consume(value, LifecycleSourceInspection, _limits(limits))[1]


def loads_inspection(data, *, limits):
    """Decode bounded inspection JSON without establishing persistence or byte availability."""
    checked = _limits(limits)
    if type(data) not in (str, bytes):
        raise LifecycleSourceArgumentError('source decoder requires ordinary str or bytes')
    document, raw = _parse(data, checked)
    return _retain(LifecycleSourceInspection, _normalize(document, LifecycleSourceInspection, checked, raw)[1])
