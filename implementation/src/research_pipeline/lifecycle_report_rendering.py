"""Pure bounded rendering of detached first-capture facts, never storage authentication."""

from dataclasses import dataclass

from research_pipeline import lifecycle_report_source as source
from research_pipeline import lifecycle_report_binding as binding, reports
from research_pipeline.domain import DomainValidationError
from research_pipeline.lifecycle_report_source import LifecycleSourceLimits, LifecycleSourceObservation


class LifecycleRenderArgumentError(ValueError):
    """A public argument or independent renderer/source allowance is invalid."""


class LifecycleRenderValidationError(DomainValidationError):
    """Retained detached content is malformed, noncanonical or semantically contradictory."""


class LifecycleRenderLimitError(ValueError):
    """A preallocation stage exceeds an independent or original retained allowance."""


@dataclass(frozen=True, kw_only=True)
class LifecycleRenderLimits:
    """Authorize source consumption, simultaneous representation work and complete output bytes."""
    source: LifecycleSourceLimits
    max_work_bytes: int
    max_output_file_bytes: int
    max_output_total_bytes: int

    def __post_init__(self):
        """Reject invalid construction; each rendering call independently checks all fields again."""
        _checked_limits(self)


def _checked_limits(value):
    """Detach exact renderer and nested source allowances before looking at any observation."""
    if type(value) is not LifecycleRenderLimits:
        raise LifecycleRenderArgumentError('expected exact renderer limits')
    scalars = []
    for name in ('max_work_bytes', 'max_output_file_bytes', 'max_output_total_bytes'):
        try:
            number = object.__getattribute__(value, name)
        except AttributeError:
            raise LifecycleRenderArgumentError('missing renderer allowance') from None
        maximum = 2**63 - 1 if name == 'max_work_bytes' else 64 * 1024 * 1024
        if type(number) is not int or not 1 <= number <= maximum:
            raise LifecycleRenderArgumentError('invalid renderer allowance')
        scalars.append(number)
    try:
        checked_source = source._limits(object.__getattribute__(value, 'source'))
    except (AttributeError, source.LifecycleSourceArgumentError):
        raise LifecycleRenderArgumentError('invalid source allowances') from None
    return checked_source, *scalars


class _Reservation:
    """Hold monotonically increasing logical representation charges for one rendering call."""

    def __init__(self, maximum):
        """Start with no charges under the independently validated render-work ceiling."""
        self.maximum, self.used = maximum, 0

    def add(self, amount, stage):
        """Reserve a named incremental representation before its protected allocations; never refund."""
        if self.used + amount > self.maximum:
            raise LifecycleRenderLimitError(stage + ' renderer workspace ceiling exceeded')
        self.used += amount


def _utf8_size(text, maximum):
    """Measure raw UTF-8 without an encoded copy, rejecting invalid Unicode and the first excess."""
    if len(text) > maximum:
        raise LifecycleRenderLimitError('raw input byte ceiling exceeded')
    size = 0
    for char in text:
        number = ord(char)
        if 0xD800 <= number <= 0xDFFF:
            raise LifecycleRenderValidationError('invalid retained Unicode')
        size += 1 if number < 128 else 2 if number < 2048 else 3 if number < 65536 else 4
        if size > maximum:
            raise LifecycleRenderLimitError('raw input byte ceiling exceeded')
    return size


def _member(value, *path):
    """Inspect required primitive containers without trusting alleged shape or reconstructing domains."""
    for key in path:
        if type(value) is not dict or key not in value:
            raise LifecycleRenderValidationError('invalid reservation input shape')
        value = value[key]
    return value


def _reconstruction_work(value, limits):
    """Measure resources and request-derived replay counts before any domain constructor or hash."""
    original = _member(value, 'binding', 'transition', 'content', 'request', 'report', 'limits',
                       'snapshot', 'max_metadata_bytes')
    if type(original) is not int or not 1 <= original < 2**63:
        raise LifecycleRenderValidationError('invalid original scientific allowance')
    metadata = min(limits.scientific.max_metadata_bytes, original)
    resources = _member(value, 'resources')
    if type(resources) is not dict:
        raise LifecycleRenderValidationError('invalid resource reservation input')
    size = source._measure(resources, limits.max_source_bytes, limits)
    accounts = operations = 0
    if 'operations' in resources:
        items = resources['operations']
        if type(items) is not list:
            raise LifecycleRenderValidationError('invalid resource operations input')
        for item in items:
            kind = _member(item, 'request', 'kind')
            if type(kind) is not str:
                raise LifecycleRenderValidationError('invalid resource operation kind')
            operations += 1
            accounts += kind in ('create_account', 'allocate')
    # Occurrences cannot be discounted using possibly forged declaration rows or
    # duplicate operation IDs. The accepted validator subsequently checks membership.
    scientific_work = 64 * metadata + 4096
    resource_work = 256 * (size + 1) + 262144 * (accounts + 1) * (operations + 1)
    return scientific_work, resource_work


def _derived_size(value, projection):
    """Bound allocation-free canonical traversal by the authorized fixed projection representation."""
    try:
        # Every node consumes at least one representation byte. Fixed wrappers add
        # at most four levels to the source's maximum 96 container levels.
        return binding._measure(value, projection, projection, 100)[0]
    except binding.LifecycleReportBindingLimitError:
        raise LifecycleRenderLimitError('derived representation ceiling exceeded') from None


def render_lifecycle_report(observation: LifecycleSourceObservation, *,
                            limits: LifecycleRenderLimits) -> dict[str, bytes]:
    """Return fresh report.md/continuation.json bytes after complete detached revalidation.

    This pure operation proves structural consistency only. All limits are required;
    malformed arguments/content and exceeded allowances have distinct errors. No
    store, policy, clock, artifact or execution hook is consulted or authorized.
    """
    checked, work, file_limit, total_limit = _checked_limits(limits)
    if type(observation) is not LifecycleSourceObservation:
        raise LifecycleRenderArgumentError('expected exact lifecycle source observation')
    try:
        retained = object.__getattribute__(observation, '_json')
    except AttributeError:
        raise LifecycleRenderValidationError('missing retained source content') from None
    if type(retained) is not str:
        raise LifecycleRenderValidationError('invalid retained source content type')
    reservation = _Reservation(work)
    raw = _utf8_size(retained, checked.max_input_bytes)
    reservation.add(4096 + 8 * raw, 'raw')
    stage = 'source parsing'
    try:
        value, measured_raw = source._parse(retained, checked)
        assert measured_raw == raw
        stage = 'source measurement'
        size = source._measure(value, min(checked.max_source_bytes, checked.max_result_bytes), checked)
        stage = 'source reservation'
        scientific_work, resource_work = _reconstruction_work(value, checked)
        reservation.add(64 * size + scientific_work + resource_work, 'source')
        if scientific_work > checked.scientific.max_work_bytes:
            raise LifecycleRenderLimitError('scientific reconstruction workspace ceiling exceeded')
        if resource_work > checked.resources.max_work_bytes:
            raise LifecycleRenderLimitError('resource reconstruction workspace ceiling exceeded')
        stage = 'source reconstruction'
        value, canonical = source._normalize(value, LifecycleSourceObservation, checked, raw)
        if canonical != retained:
            raise LifecycleRenderValidationError('noncanonical retained source content')
    except source.LifecycleSourceArgumentError:
        raise LifecycleRenderArgumentError(stage + ': invalid argument') from None
    except source.LifecycleSourceLimitError:
        raise LifecycleRenderLimitError(stage + ': ceiling exceeded') from None
    except source.LifecycleSourceValidationError:
        raise LifecycleRenderValidationError(stage + ': invalid detached content') from None

    # Fixed-schema projection is linear in retained records/references. This
    # reservation covers repeated fragments, traversal sets, wrappers and empty
    # overhead, even where Python happens to share immutable representations.
    projection = 256 * size + 65536
    reservation.add(projection, 'projection')
    identities, groups, continuation = reports._lifecycle_projection(value, checked.scientific)
    identity_size = _derived_size(identities, projection)
    group_size = _derived_size(groups, projection)
    continuation_size = _derived_size(continuation, projection)
    markdown_size = 0
    for frame in reports._markdown_frames(identities, groups, opening=reports._LIFECYCLE_OPENING,
                                         navigation='', footer=reports._LIFECYCLE_FOOTER):
        markdown_size += (_utf8_size(frame, 2**63 - 1) if type(frame) is str else
                          _derived_size(frame, projection) + 6)
    json_size = continuation_size + 1
    original = value['binding']['transition']['content']['request']['report']['limits']
    if max(size, markdown_size, json_size) > min(file_limit, original['max_output_file_bytes']):
        raise LifecycleRenderLimitError('complete output file ceiling exceeded')
    if size + markdown_size + json_size > min(total_limit, original['max_output_total_bytes']):
        raise LifecycleRenderLimitError('complete output bundle ceiling exceeded')
    reservation.add(8 * (identity_size + group_size + continuation_size) +
                    4 * (markdown_size + json_size) + 2 * size + 4096, 'output')
    try:
        outputs = reports._serialize_outputs(identities, groups, continuation,
            opening=reports._LIFECYCLE_OPENING, navigation='', footer=reports._LIFECYCLE_FOOTER,
            maximum=min(file_limit, original['max_output_file_bytes']))
    except reports.ReportLimitError:
        raise AssertionError('output encoding exceeded its preflight measurement') from None
    if len(outputs['report.md']) != markdown_size or len(outputs['continuation.json']) != json_size:
        raise AssertionError('output encoding disagrees with preflight measurement')
    return outputs
