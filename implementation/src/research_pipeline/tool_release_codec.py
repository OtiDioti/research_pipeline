"""Private bounded traversal and JSON guards for passive tool-release declarations."""

from dataclasses import dataclass, fields
import json

from research_pipeline.domain import ArtifactReference, RecordReference, DomainValidationError
from research_pipeline.resources import Dimension
from research_pipeline.work_product import WorkProductFile


class ToolReleaseValidationError(DomainValidationError):
    """A release declaration has invalid syntax, types, fields or internal consistency."""


class ToolReleaseLimitError(ToolReleaseValidationError):
    """A named external processing ceiling was exceeded before protected work."""


@dataclass(frozen=True, slots=True)
class ToolReleaseLimits:
    """Independent processing ceilings; zero is legal and maxima cannot be enlarged."""

    max_wire_bytes: int = 1048576
    max_canonical_bytes: int = 1048576
    max_string_chars: int = 16384
    max_collection_items: int = 256
    max_references: int = 1024
    max_nodes: int = 32768
    max_depth: int = 24
    max_reconstruction_units: int = 262144

    def __post_init__(self):
        """Reject aliases, negatives and values above the fixed per-field hard maxima."""
        checked_limits(self)


def checked_limits(value):
    """Return fresh defaults or revalidate an exact limits object, including bypass mutations."""
    if value is None:
        return ToolReleaseLimits()
    if type(value) is not ToolReleaseLimits:
        raise ToolReleaseValidationError("limits: expected exact ToolReleaseLimits")
    for field in fields(ToolReleaseLimits):
        number = raw_attribute(value, field.name)
        if type(number) is not int or not 0 <= number <= field.default:
            raise ToolReleaseValidationError(f"{field.name}: invalid processing ceiling")
    return value


def raw_attribute(value, name):
    """Read an exact object's retained field without dispatching serialization methods."""
    try:
        return object.__getattribute__(value, name)
    except AttributeError as error:
        raise ToolReleaseValidationError(f"missing retained field: {name}") from error


_LAYOUTS = (
    (ArtifactReference, ("digest", "size")),
    (RecordReference, ("record_id", "revision", "relationship", "target_kind")),
    (WorkProductFile, ("path", "artifact")),
    (Dimension, ("dimension_id", "kind", "unit", "currency", "scale")),
)


def _layout_for_type(kind):
    """Return an exact supported class's virtual fields, or None, without invoking hooks."""
    # Class equality and hashing can invoke caller-controlled metaclass methods.
    for expected_class, layout in _LAYOUTS:
        if kind is expected_class:
            return layout
    return None


def raw_fields(value):
    """Project fixed virtual fields, rejecting unsupported classes before attribute access."""
    layout = _layout_for_type(type(value))
    if layout is None:
        raise ToolReleaseValidationError("unsupported exact value type")
    return {name: raw_attribute(value, name) for name in layout}


def check_limit(limits, name, amount):
    """Fail with the independent ceiling name, without echoing untrusted content."""
    if amount > getattr(limits, name):
        raise ToolReleaseLimitError(f"{name}: processing ceiling exceeded")


def scalar_size(code):
    """Return one Unicode scalar's canonical ASCII JSON width, rejecting lone surrogates."""
    if 0xD800 <= code <= 0xDFFF:
        raise ToolReleaseValidationError("text: unpaired Unicode surrogate")
    if code in (8, 9, 10, 12, 13, 34, 92):
        return 2
    # ensure_ascii also escapes U+007F, despite it being an ASCII character.
    if code < 32 or 127 <= code <= 65535:
        return 6
    return 12 if code > 65535 else 1


class _Counts:
    """Accumulate bounded occurrence counts and canonical bytes in one traversal."""

    def __init__(self, limits):
        """Start empty counters using independently validated external ceilings."""
        self.limits = limits
        self.nodes = self.units = self.canonical = 0

    def add(self, *, nodes=0, chars=0, size=0):
        """Charge occurrences and decoded characters before allocating reconstructed content."""
        self.nodes += nodes
        check_limit(self.limits, "max_nodes", self.nodes)
        self.units += nodes + chars
        check_limit(self.limits, "max_reconstruction_units", self.units)
        self.canonical += size
        check_limit(self.limits, "max_canonical_bytes", self.canonical)

    def string(self, value):
        """Check a scalar string and count its complete escaped representation, including quotes."""
        check_limit(self.limits, "max_string_chars", len(value))
        self.add(nodes=1, chars=len(value), size=2)
        for character in value:
            self.add(size=scalar_size(ord(character)))


def _children(value, typed):
    """Yield exact container children or constructor-only virtual fields; reject aliases inertly."""
    kind = type(value)
    layout = _layout_for_type(kind) if typed else None
    if layout is not None:
        for name in layout:
            yield name, True
            yield raw_attribute(value, name), False
    elif kind is dict:
        for key, child in value.items():
            yield key, True
            yield child, False
    elif kind is list or (typed and kind is tuple):
        for child in value:
            yield child, False
    else:
        raise ToolReleaseValidationError("unsupported exact value type")


def preflight(value, limits, *, typed=False):
    """Bound a tree's virtual wire form before copying; reject cycles and aliases inertly.

    Only depth-sized iterator frames are retained. Repeated acyclic aliases are
    visited and charged again, because each occurrence appears in the wire form.
    Classify exact types by identity before length, iteration or field access.
    Return base reconstruction units for subsequent schema-specific path charges.
    """
    counts = _Counts(limits)
    active = set()
    stack = [(iter(((value, False),)), None)]
    while stack:
        iterator, owner = stack[-1]
        try:
            item, key = next(iterator)
        except StopIteration:
            stack.pop()
            if owner is not None:
                active.remove(owner)
            continue
        kind = type(item)
        layout = _layout_for_type(kind) if typed else None
        if key and kind is not str:
            raise ToolReleaseValidationError("object keys must be ordinary strings")
        if kind is str:
            counts.string(item)
        elif item is None:
            counts.add(nodes=1, size=4)
        elif kind is int:
            if not 0 <= item <= 2**63 - 1:
                raise ToolReleaseValidationError("integer outside nonnegative signed-64 range")
            counts.add(nodes=1, size=len(str(item)))
        elif kind is dict or kind is list or (typed and kind is tuple) or layout is not None:
            if id(item) in active:
                raise ToolReleaseValidationError("cyclic container")
            depth = len(stack)
            check_limit(limits, "max_depth", depth)
            mapping = kind is dict or layout is not None
            length = len(layout) if layout is not None else len(item)
            check_limit(limits, "max_collection_items", length)
            counts.add(nodes=1, size=2 + max(0, length - 1) + (length if mapping else 0))
            active.add(id(item))
            stack.append((_children(item, typed), id(item)))
        else:
            raise ToolReleaseValidationError("unsupported exact value type")
    return counts.units


def detached(value):
    """Copy a bounded, schema-checked tree to wire values using identity-only class dispatch."""
    kind = type(value)
    if _layout_for_type(kind) is not None:
        value = raw_fields(value)
        kind = dict
    if kind is dict:
        return {key: detached(child) for key, child in value.items()}
    if kind is list or kind is tuple:
        return [detached(child) for child in value]
    return value


def canonical(value):
    """Serialize only previously sized and validated content to canonical ASCII JSON."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _pairs(pairs):
    """Reject duplicate decoded keys at every depth of the bounded stdlib parse."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ToolReleaseValidationError("duplicate JSON field")
        result[key] = value
    return result


def _hex_quad(data, offset):
    """Decode one fixed-size JSON Unicode escape without allocating a variable token."""
    token = data[offset:offset + 4]
    if len(token) != 4 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise ToolReleaseValidationError("invalid JSON Unicode escape")
    return int(token, 16)


def _scan_string(data, offset, counts):
    """Scan a quoted token without constructing it; combine legal surrogate-pair escapes."""
    offset += 1
    length = 0
    counts.add(nodes=1, size=2)
    while offset < len(data):
        code = ord(data[offset])
        offset += 1
        if code == 34:
            return offset
        if code < 32:
            raise ToolReleaseValidationError("unescaped JSON control character")
        if code == 92:
            if offset == len(data):
                break
            escape = data[offset]
            offset += 1
            if escape == "u":
                code = _hex_quad(data, offset)
                offset += 4
                if 0xD800 <= code <= 0xDBFF:
                    if data[offset:offset + 2] != "\\u":
                        raise ToolReleaseValidationError("unpaired JSON surrogate")
                    low = _hex_quad(data, offset + 2)
                    if not 0xDC00 <= low <= 0xDFFF:
                        raise ToolReleaseValidationError("unpaired JSON surrogate")
                    code = 65536 + ((code - 0xD800) << 10) + low - 0xDC00
                    offset += 6
            elif escape in '"\\/bfnrt':
                code = ord({'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}.get(escape, escape))
            else:
                raise ToolReleaseValidationError("invalid JSON escape")
        length += 1
        check_limit(counts.limits, "max_string_chars", length)
        counts.add(chars=1, size=scalar_size(code))
    raise ToolReleaseValidationError("unterminated JSON string")


def lexical_preflight(data, limits):
    """Check JSON grammar and allocation bounds with a depth-sized state stack before loads.

    Frames contain container kind, next grammar state and member count. No decoded
    tokens or pending-child lists are built. Duplicate names are checked by loads.
    """
    counts = _Counts(limits)
    stack = [["root", "value", 0]]
    offset = 0
    while offset < len(data):
        char = data[offset]
        if char in " \t\r\n":
            offset += 1
            continue
        frame = stack[-1]
        kind, state, length = frame
        if state == "done":
            raise ToolReleaseValidationError("trailing JSON content")
        if state in ("comma", "key_or_end", "value_or_end") and char == ("}" if kind == "object" else "]"):
            stack.pop()
            offset += 1
            continue
        if state == "comma":
            if char != ",":
                raise ToolReleaseValidationError("expected JSON comma")
            counts.add(size=1)
            frame[1] = "key" if kind == "object" else "value"
            offset += 1
            continue
        if state in ("key", "key_or_end"):
            if char != '"':
                raise ToolReleaseValidationError("expected JSON object key")
            frame[2] += 1
            check_limit(limits, "max_collection_items", frame[2])
            offset = _scan_string(data, offset, counts)
            frame[1] = "colon"
            continue
        if state == "colon":
            if char != ":":
                raise ToolReleaseValidationError("expected JSON colon")
            counts.add(size=1)
            frame[1] = "value"
            offset += 1
            continue
        if kind == "array":
            frame[2] += 1
            check_limit(limits, "max_collection_items", frame[2])
        frame[1] = "done" if kind == "root" else "comma"
        if char in "[{":
            check_limit(limits, "max_depth", len(stack))
            check_limit(limits, "max_collection_items", 0)
            counts.add(nodes=1, size=2)
            stack.append(["object" if char == "{" else "array", "key_or_end" if char == "{" else "value_or_end", 0])
            offset += 1
        elif char == '"':
            offset = _scan_string(data, offset, counts)
        elif data.startswith("null", offset):
            counts.add(nodes=1, size=4)
            offset += 4
        elif "0" <= char <= "9" or char == "-":
            start = offset + (1 if char == "-" else 0)
            end = start
            while end < len(data) and "0" <= data[end] <= "9":
                end += 1
                if end - start > 19:
                    raise ToolReleaseValidationError("integer token outside signed-64 range")
            token = data[start:end]
            if (not token or (len(token) > 1 and token[0] == "0")
                    or int(token) > 2**63 - 1 or (char == "-" and token != "0")):
                raise ToolReleaseValidationError("invalid or out-of-range JSON integer")
            # JSON -0 decodes to the ordinary integer zero; its canonical width
            # is one, while the external wire guard still charges the minus sign.
            counts.add(nodes=1, size=len(token))
            offset = end
        else:
            raise ToolReleaseValidationError("expected null, nonnegative integer, string or container")
    if len(stack) != 1 or stack[0][1] != "done":
        raise ToolReleaseValidationError("incomplete JSON document")


def parse(data, limits, *, retained=False):
    """Reject input aliases inertly, then bound, scan and parse exact UTF-8 bytes or text.

    Retained canonical input must be exact str and uses the canonical byte ceiling.
    """
    kind = type(data)
    if (kind is not str and kind is not bytes) or (retained and kind is not str):
        raise ToolReleaseValidationError("JSON input: expected ordinary str or bytes")
    ceiling = "max_canonical_bytes" if retained else "max_wire_bytes"
    check_limit(limits, ceiling, len(data))
    try:
        if type(data) is bytes:
            data = data.decode("utf-8")
        else:
            size = 0
            for character in data:
                code = ord(character)
                if 0xD800 <= code <= 0xDFFF:
                    raise ToolReleaseValidationError("JSON input: Unicode surrogate")
                size += 1 if code < 128 else 2 if code < 2048 else 3 if code < 65536 else 4
                check_limit(limits, ceiling, size)
        lexical_preflight(data, limits)
        return json.loads(data, object_pairs_hook=_pairs)
    except ToolReleaseValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ToolReleaseValidationError("cannot decode tool-release JSON") from error
