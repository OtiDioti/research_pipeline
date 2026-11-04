"""Private finite codec adapters and public ceilings for passive tool assessments."""

from dataclasses import dataclass, fields

from research_pipeline.domain import DomainValidationError
from research_pipeline import tool_release_codec as _release


class ToolAssessmentValidationError(DomainValidationError):
    """An assessment declaration or retained envelope violates its local contract."""


class ToolAssessmentLimitError(ToolAssessmentValidationError):
    """A named independent assessment processing ceiling was exceeded."""


@dataclass(frozen=True, slots=True)
class ToolAssessmentLimits:
    """External processing ceilings; exact integers from zero through each default."""

    max_wire_bytes: int = 1048576
    max_canonical_bytes: int = 1048576
    max_string_chars: int = 16384
    max_collection_items: int = 256
    max_references: int = 1024
    max_nodes: int = 32768
    max_depth: int = 24
    max_reconstruction_units: int = 262144

    def __post_init__(self):
        """Reject invalid constructor ceilings, including subclass receivers."""
        _checked_limits(self)


def _adapt(operation, *args, **kwargs):
    """Reuse one predecessor guard, translating only its expected validation failures."""
    try:
        return operation(*args, **kwargs)
    except _release.ToolReleaseLimitError as error:
        raise ToolAssessmentLimitError(str(error)) from error
    except _release.ToolReleaseValidationError as error:
        raise ToolAssessmentValidationError(str(error)) from error


def _raw_attribute(value, name):
    """Read a fixed retained field without invoking supplied serializers."""
    return _adapt(_release.raw_attribute, value, name)


def _checked_limits(value):
    """Create fresh defaults or revalidate every field of an exact limits instance."""
    if value is None:
        return ToolAssessmentLimits()
    if type(value) is not ToolAssessmentLimits:
        raise ToolAssessmentValidationError("limits: expected exact ToolAssessmentLimits")
    for field in fields(ToolAssessmentLimits):
        number = _raw_attribute(value, field.name)
        if type(number) is not int or not 0 <= number <= field.default:
            raise ToolAssessmentValidationError(f"{field.name}: invalid processing ceiling")
    return value


def _check_limit(limits, name, amount):
    """Check a validated independent ceiling and report its name on excess."""
    if amount > _raw_attribute(limits, name):
        raise ToolAssessmentLimitError(f"{name}: processing ceiling exceeded")


def _preflight(value, limits, *, typed=False):
    """Bound the entire virtual wire tree before schema traversal or copying."""
    return _adapt(_release.preflight, value, limits, typed=typed)


def _parse(data, limits, *, retained=False):
    """Bound UTF-8 or retained JSON and scan before allocating a decoded tree."""
    return _adapt(_release.parse, data, limits, retained=retained)


def _detached(value):
    """Copy a previously bounded schema-checked tree without serializer dispatch."""
    return _adapt(_release.detached, value)


def _canonical(value):
    """Emit canonical ASCII JSON only after its complete width has been guarded."""
    return _adapt(_release.canonical, value)
