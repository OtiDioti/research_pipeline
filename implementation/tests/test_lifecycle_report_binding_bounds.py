"""Independent accounting, exact types, retained-state checks and allocation-stage sentinels."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from research_pipeline import lifecycle_report_binding as b, run_control as c
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference
from research_pipeline.operating_authority import OperatingScope
from tests import lifecycle_binding_fixtures as f


class BindingSubclass(b.LifecycleReportBinding):
    """Unsupported public subclass used to test every construction and consumption route."""


class LimitsSubclass(b.LifecycleReportBindingLimits):
    """Unsupported allowance subclass, including bypass-created instances."""


class IntSubclass(int):
    """Nonordinary integer that must never authorize allocation."""


class DictSubclass(dict):
    """Nonordinary mapping that must not enter the wire boundary."""


class StrSubclass(str):
    """Nonordinary raw input or nested string that must not be coerced."""


class ListSubclass(list):
    """Nonordinary nested sequence that must not be traversed."""


def forged(cls, **attributes):
    """Create bypass-mutated retained objects to test hostile exact-class state."""
    value = object.__new__(cls)
    for name, content in attributes.items():
        object.__setattr__(value, name, content)
    return value


class LifecycleBindingBoundsTests(unittest.TestCase):
    """Measure independently and observe rejection before dependent allocations."""

    @classmethod
    def setUpClass(cls):
        """Capture real originals and small canonical packets outside all mocked boundaries."""
        cls.members = f.captured()
        cls.packet = f.packet(cls.members[0])
        cls.text = f.canonical(cls.packet)
        cls.size = len(cls.text)
        cls.nodes, cls.depth = f.counts(cls.packet)
        cls.value = b.LifecycleReportBinding(cls.packet, limits=f.LIMITS)

    def calls(self, *, packet=None, value=None, raw=None, members=None):
        """Return each public boundary as a callable taking its explicit allowances."""
        packet = self.packet if packet is None else packet
        value = self.value if value is None else value
        raw = self.text if raw is None else raw
        members = self.members[0] if members is None else members
        return (
            lambda limits: b.LifecycleReportBinding(packet, limits=limits),
            lambda limits: b.LifecycleReportBinding.from_dict(packet, limits=limits),
            lambda limits: b.bind_lifecycle_report(*members, limits=limits),
            lambda limits: b.loads_binding(raw, limits=limits),
            lambda limits: b.dumps_binding(value, limits=limits),
            lambda limits: value.to_dict(limits=limits),
            lambda limits: b.binding_digest(value, limits=limits),
        )

    def test_independent_exact_packet_node_depth_and_work_allowances(self):
        """Each allowance succeeds at exact measured equality and fails one unit below."""
        for field, number in (('max_packet_bytes', self.size), ('max_nodes', self.nodes), ('max_depth', self.depth)):
            for call in self.calls():
                with self.subTest(field=field, call=call):
                    call(replace(f.LIMITS, **{field: number}))
                    with self.assertRaises(b.LifecycleReportBindingLimitError):
                        call(replace(f.LIMITS, **{field: number - 1}))
        for index, call in enumerate(self.calls()):
            work = (64 if index < 3 else 72) * self.size
            with self.subTest(work=work, boundary=index):
                call(replace(f.LIMITS, max_work_bytes=work))
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    call(replace(f.LIMITS, max_work_bytes=work - 1))
        for field in ('max_nodes', 'max_depth'):
            for call in self.calls():
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    call(replace(f.LIMITS, **{field: 0}))

    def test_raw_utf8_whitespace_and_expansion_boundaries(self):
        """R counts all UTF-8 bytes while P independently counts canonical ASCII expansion."""
        packet = f.packet(self.members[1])
        canonical = f.canonical(packet)
        raw = '\n  ' + json.dumps(packet, ensure_ascii=False, indent=2) + '\n'
        raw_bytes = raw.encode('utf-8')
        self.assertGreater(len(raw_bytes), len(raw))
        for data in (raw, raw_bytes):
            exact = replace(f.LIMITS, max_input_bytes=len(raw_bytes),
                            max_packet_bytes=len(canonical), max_work_bytes=8 * len(raw_bytes) + 64 * len(canonical))
            self.assertEqual(b.dumps_binding(b.loads_binding(data, limits=exact), limits=f.LIMITS), canonical)
            for name in ('max_input_bytes', 'max_packet_bytes', 'max_work_bytes'):
                with self.subTest(field=name, input_type=type(data)), self.assertRaises(b.LifecycleReportBindingLimitError):
                    b.loads_binding(data, limits=replace(exact, **{name: getattr(exact, name) - 1}))
        raw = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
        self.assertLess(len(raw.encode()), len(canonical))
        with self.assertRaises(b.LifecycleReportBindingLimitError):
            b.loads_binding(raw, limits=replace(f.LIMITS, max_packet_bytes=len(canonical) - 1))
        for call in self.calls()[3:]:
            call(replace(f.LIMITS, max_input_bytes=self.size))
            with self.assertRaises(b.LifecycleReportBindingLimitError):
                call(replace(f.LIMITS, max_input_bytes=self.size - 1))
        # Dictionary inputs have R=0 and need no raw-input budget beyond the valid minimum.
        for call in self.calls()[:3]:
            call(replace(f.LIMITS, max_input_bytes=1))

    def test_complete_wrapper_and_alias_accounting(self):
        """Complete fixed overhead and two aliases count as serialized occurrences, never deduplicated."""
        preparation, transition, obligation = self.members[0]
        self.assertIs(preparation, transition)
        skeleton = {**self.packet, 'preparation': None, 'transition': None, 'obligation': None}
        member_sizes = [len(f.canonical(item)) for item in (preparation, transition, obligation)]
        self.assertEqual(self.size, len(f.canonical(skeleton)) - 12 + sum(member_sizes))
        member_counts = [f.counts(item) for item in (preparation, transition, obligation)]
        self.assertEqual(self.nodes, sum(n for n, _ in member_counts) + 8)
        self.assertEqual(self.depth, max(d for _, d in member_counts) + 1)
        for allowance in (sum(member_sizes), max(member_sizes), self.size - len(f.canonical(preparation))):
            self.assertGreaterEqual(allowance, max(member_sizes))
            with self.assertRaises(b.LifecycleReportBindingLimitError):
                b.bind_lifecycle_report(preparation, transition, obligation,
                    limits=replace(f.LIMITS, max_packet_bytes=allowance))
        # Empty containers contribute two bytes and one node; enclosing containers
        # still contribute their own nesting even with no scalar descendants.
        for tree in ({}, [], {'empty': []}, {'a': {}, 'b': [], 'c': None, 'd': False}):
            expected = (len(f.canonical(tree)), *f.counts(tree))
            self.assertEqual(b._measure(tree, 1000, 100, 10), expected)

    def test_invalid_limits_precede_payload_access_everywhere(self):
        """Every entry revalidates forged allowances before wrong payload types or retained state."""
        malformed = forged(b.LifecycleReportBinding, _json=object())
        calls = self.calls(packet=object(), value=malformed, raw=object(), members=(object(),) * 3)
        invalid = [None, object(), forged(LimitsSubclass), forged(b.LifecycleReportBindingLimits)]
        for name in vars(f.LIMITS):
            attributes = dict(vars(f.LIMITS))
            del attributes[name]
            invalid.append(forged(b.LifecycleReportBindingLimits, **attributes))
        for name, maximum in (('max_input_bytes', b.MAX_INPUT_BYTES), ('max_packet_bytes', b.MAX_PACKET_BYTES),
                              ('max_work_bytes', b.MAX_WORK_BYTES), ('max_nodes', b.MAX_NODES), ('max_depth', b.MAX_DEPTH)):
            for number in (True, 1.0, IntSubclass(1), -1, maximum + 1, None):
                invalid.append(forged(b.LifecycleReportBindingLimits, **{**vars(f.LIMITS), name: number}))
                with self.subTest(field=name, value=number), self.assertRaises(b.LifecycleReportBindingArgumentError):
                    b.LifecycleReportBindingLimits(**{**vars(f.LIMITS), name: number})
            if name.endswith('bytes'):
                invalid.append(forged(b.LifecycleReportBindingLimits, **{**vars(f.LIMITS), name: 0}))
        for limits in invalid:
            for call in calls:
                with self.assertRaises(b.LifecycleReportBindingArgumentError):
                    call(limits)
            with self.assertRaises(b.LifecycleReportBindingArgumentError):
                BindingSubclass.from_dict({}, limits=limits)
        with self.assertRaises(b.LifecycleReportBindingArgumentError):
            LimitsSubclass(**vars(f.LIMITS))

    def test_exact_public_types_and_required_signatures(self):
        """All consumers, constructors and classmethods reject subclasses and require keyword budgets."""
        for bad in (None, [], object(), DictSubclass(self.packet), self.value):
            for factory in (b.LifecycleReportBinding, b.LifecycleReportBinding.from_dict):
                with self.assertRaises(b.LifecycleReportBindingArgumentError):
                    factory(bad, limits=f.LIMITS)
            with self.assertRaises(b.LifecycleReportBindingArgumentError):
                b.bind_lifecycle_report(bad, *self.members[0][1:], limits=f.LIMITS)
        for bad in (bytearray(self.text.encode()), StrSubclass(self.text), {}, None):
            with self.assertRaises(b.LifecycleReportBindingArgumentError):
                b.loads_binding(bad, limits=f.LIMITS)
        for factory in (BindingSubclass, BindingSubclass.from_dict):
            with self.assertRaises(b.LifecycleReportBindingArgumentError):
                factory(self.packet, limits=f.LIMITS)
        subclass = forged(BindingSubclass, _json=self.text)
        for bad in (subclass, object(), self.packet):
            for consume in (b.dumps_binding, b.binding_digest, b.LifecycleReportBinding.to_dict):
                with self.assertRaises(b.LifecycleReportBindingArgumentError):
                    consume(bad, limits=f.LIMITS)
        with self.assertRaises(b.LifecycleReportBindingArgumentError):
            subclass.to_dict(limits=f.LIMITS)
        for call in (lambda: b.LifecycleReportBinding(self.packet),
                     lambda: b.LifecycleReportBinding.from_dict(self.packet),
                     lambda: b.bind_lifecycle_report(*self.members[0]),
                     lambda: b.loads_binding(self.text), lambda: b.dumps_binding(self.value),
                     lambda: b.binding_digest(self.value), lambda: self.value.to_dict(),
                     lambda: b.loads_binding(self.text, f.LIMITS),
                     lambda: b.loads_binding(self.text, limits=f.LIMITS, extra=True),
                     lambda: b.LifecycleReportBindingLimits()):
            with self.assertRaises(TypeError):
                call()

    def test_nested_forged_types_cycles_and_numbers(self):
        """Wire trees cannot invoke object conversions or accept classes, cycles, nonfinite or huge numbers."""
        cycle = {}
        cycle['cycle'] = cycle
        objects = [forged(cls) for cls in (RecordEnvelope, CreationProvenance, OperatingScope, RecordReference)]
        for bad in (*objects, object(), DictSubclass(), ListSubclass(), StrSubclass('x'), (1,),
                    cycle, float('nan'), float('inf'), -float('inf'), 2**100000, -(2**63) - 1, '\ud800'):
            changed = deepcopy(self.packet)
            changed['preparation']['provenance']['details'] = bad
            with self.subTest(type=type(bad)), self.assertRaises(b.LifecycleReportBindingValidationError):
                b.LifecycleReportBinding(changed, limits=f.LIMITS)
        for key in (1, StrSubclass('x'), '\ud800'):
            changed = deepcopy(self.packet)
            changed[key] = None
            with self.assertRaises(b.LifecycleReportBindingValidationError):
                b.LifecycleReportBinding(changed, limits=f.LIMITS)

    def test_strict_raw_json(self):
        """Reject duplicates, malformed JSON/UTF-8, lone surrogates and nonfinite syntax."""
        for data in (b'\xff', b'\xed\xa0\x80', '\ud800', 'null', '[]', '{', self.text + 'null',
                     '{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}',
                     self.text.replace('"version":1', '"version":1,"version":1', 1),
                     self.text.replace('"version":1', '"version":NaN', 1),
                     self.text.replace('"version":1', '"version":Infinity', 1),
                     self.text.replace('"version":1', '"version":1e9999', 1),
                     self.text.replace('"version":1', '"version":"\\ud800"', 1),
                     self.text.replace('"version":1', '"version":"\\udc00"', 1)):
            with self.subTest(input_type=type(data)), self.assertRaises(b.LifecycleReportBindingValidationError):
                b.loads_binding(data, limits=f.LIMITS)
        # A valid surrogate pair is accepted as its supplementary scalar; the
        # real selected narrative fixture contains such an escaped pair.
        later = f.canonical(f.packet(self.members[1]))
        self.assertIn('\\ud835\\udc9c', later)
        b.loads_binding(later, limits=f.LIMITS)

    def test_all_retained_consumers_revalidate(self):
        """Frozen instances provide no validity cache or alternative unbounded content interface."""
        contradictory = deepcopy(self.packet)
        contradictory['ordinary_work_allowed'] = True
        noncanonical = json.dumps(self.packet, sort_keys=False)
        for text in (None, b'{}', StrSubclass(self.text), '{}', '{', self.text + ' ',
                     noncanonical, f.canonical(contradictory)):
            value = forged(b.LifecycleReportBinding, _json=text)
            for consume in (b.dumps_binding, b.binding_digest, b.LifecycleReportBinding.to_dict):
                with self.subTest(consumer=consume.__name__), self.assertRaises(b.LifecycleReportBindingValidationError):
                    consume(value, limits=f.LIMITS)
        value = forged(b.LifecycleReportBinding)
        with self.assertRaises(b.LifecycleReportBindingValidationError):
            value.to_dict(limits=f.LIMITS)
        for consume in (b.dumps_binding, b.binding_digest, b.LifecycleReportBinding.to_dict):
            with self.assertRaises(b.LifecycleReportBindingLimitError):
                consume(self.value, limits=replace(f.LIMITS, max_input_bytes=self.size - 1))
            oversized = forged(b.LifecycleReportBinding, _json=' ' * (self.size + 1))
            with self.assertRaises(b.LifecycleReportBindingLimitError):
                consume(oversized, limits=replace(f.LIMITS, max_input_bytes=self.size))

    def test_raw_overflow_precedes_json_parser(self):
        """Raw bytes, UTF-8 length, lexical nodes/depth and 8R rejection cannot call json.loads."""
        cases = ((self.text, replace(f.LIMITS, max_input_bytes=self.size - 1)),
                 (self.text.encode(), replace(f.LIMITS, max_input_bytes=self.size - 1)),
                 ('"α"', replace(f.LIMITS, max_input_bytes=3)),
                 (self.text, replace(f.LIMITS, max_nodes=self.nodes - 1)),
                 (self.text, replace(f.LIMITS, max_depth=self.depth - 1)),
                 (self.text, replace(f.LIMITS, max_work_bytes=8 * self.size - 1)))
        with patch.object(b.json, 'loads', side_effect=AssertionError('parser called before raw reservation')):
            for data, limits in cases:
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    b.loads_binding(data, limits=limits)
        # Equality uses the real parser and real downstream constructors.
        self.assertEqual(b.loads_binding(self.text, limits=replace(f.LIMITS, max_nodes=self.nodes,
                         max_depth=self.depth, max_input_bytes=self.size)).to_dict(limits=f.LIMITS), self.packet)

    def allocation_guards(self):
        """Forbid nested constructors, container encoding and hashing before successful preflight."""
        stack = ExitStack()
        for owner, name in ((RecordEnvelope, 'from_dict'), (RecordReference, 'from_dict'), (RecordReference, '__init__'),
                            (c.RunControlRequest, '__init__'), (c.RunControlTransition, '__init__'), (c.RunReportObligation, '__init__'),
                            (OperatingScope, '__init__')):
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError('nested allocation before preflight')))
        original = c.canonical

        def scalar_only(value):
            """Allow only constant-sized float measurement before the full reserve."""
            if type(value) in (dict, list):
                raise AssertionError('container encoding before preflight')
            return original(value)

        stack.enter_context(patch.object(c, 'canonical', scalar_only))
        stack.enter_context(patch.object(b.hashlib, 'sha256', side_effect=AssertionError('hash before preflight')))
        return stack

    def test_packet_and_work_preflight_precedes_nested_allocations(self):
        """Complete wrapper/representation overflow fails before all dependent allocation seams."""
        for limits in (replace(f.LIMITS, max_packet_bytes=self.size - 1),
                       replace(f.LIMITS, max_work_bytes=64 * self.size - 1),
                       replace(f.LIMITS, max_nodes=self.nodes - 1),
                       replace(f.LIMITS, max_depth=self.depth - 1)):
            with self.allocation_guards():
                for call in self.calls()[:3]:
                    with self.assertRaises(b.LifecycleReportBindingLimitError):
                        call(limits)
        with self.allocation_guards():
            with self.assertRaises(b.LifecycleReportBindingLimitError):
                b.loads_binding(self.text, limits=replace(f.LIMITS, max_work_bytes=72 * self.size - 1))
        for call in self.calls()[:3]:
            call(replace(f.LIMITS, max_work_bytes=64 * self.size, max_packet_bytes=self.size))

    def test_inherited_fragment_ceilings(self):
        """Envelope, request, intent, scope and obligation ceilings are checked before codecs."""
        envelopes = [self.packet[name] for name in ('preparation', 'transition', 'obligation')]
        requests = [item['content']['request'] for item in envelopes[:2]]
        for field, maximum in (('TRANSITION_BYTES', max(len(f.canonical(item)) for item in envelopes)),
                               ('REQUEST_BYTES', max(len(f.canonical(item)) for item in requests)),
                               ('SMALL_BYTES', max(len(f.canonical(item['report'])) for item in requests)),
                               ('JSON_NODES', max(f.counts(item)[0] for item in envelopes)),
                               ('JSON_DEPTH', max(f.counts(item)[1] for item in envelopes))):
            with self.subTest(fragment=field), patch.object(c, field, maximum - 1), self.allocation_guards():
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    b.LifecycleReportBinding(self.packet, limits=f.LIMITS)
            with patch.object(c, field, maximum):
                b.LifecycleReportBinding(self.packet, limits=f.LIMITS)
        scope = requests[0]['preparation']['operating_scope']
        for name, maximum in (('JSON_DEPTH', f.counts(scope)[1]), ('JSON_NODES', f.counts(scope)[0])):
            with patch.object(c.authority, name, maximum - 1), self.allocation_guards():
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    b.LifecycleReportBinding(self.packet, limits=f.LIMITS)
            with patch.object(c.authority, name, maximum):
                b.LifecycleReportBinding(self.packet, limits=f.LIMITS)
        changed = deepcopy(self.packet)
        changed['obligation']['content']['oversized'] = 'x' * c.SMALL_BYTES
        with self.allocation_guards(), self.assertRaises(b.LifecycleReportBindingLimitError):
            b.LifecycleReportBinding(changed, limits=f.LIMITS)
        changed = deepcopy(self.packet)
        deep = []
        for _ in range(32):
            deep = [deep]
        changed['transition']['content']['request']['report'] = deep
        with self.allocation_guards(), self.assertRaises(b.LifecycleReportBindingLimitError):
            b.LifecycleReportBinding(changed, limits=f.LIMITS)

    def test_expected_projection_before_reference_construction(self):
        """Short malicious projections cannot bypass virtual complete-envelope byte/node ceilings."""
        changed = deepcopy(self.packet)
        for name in ('preparation', 'transition', 'obligation'):
            changed[name]['record_references'] = []
        maximum_bytes = max(len(f.canonical(self.packet[name])) for name in ('preparation', 'transition', 'obligation'))
        maximum_nodes = max(f.counts(self.packet[name])[0] for name in ('preparation', 'transition', 'obligation'))
        for constant, maximum in (('TRANSITION_BYTES', maximum_bytes), ('JSON_NODES', maximum_nodes)):
            with patch.object(c, constant, maximum - 1), self.allocation_guards():
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    b.LifecycleReportBinding(changed, limits=f.LIMITS)
            # Valid complete projections construct successfully at the same equality.
            with patch.object(c, constant, maximum):
                b.LifecycleReportBinding(self.packet, limits=f.LIMITS)

    def test_larger_allowances_never_change_identity(self):
        """Fresh processing budgets are not retained identity or provenance."""
        small = replace(f.LIMITS, max_input_bytes=self.size, max_packet_bytes=self.size,
                        max_work_bytes=72 * self.size, max_nodes=self.nodes, max_depth=self.depth)
        value = b.LifecycleReportBinding(self.packet, limits=small)
        self.assertEqual(b.dumps_binding(value, limits=small), b.dumps_binding(value, limits=f.LIMITS))
        self.assertEqual(b.binding_digest(value, limits=small), b.binding_digest(value, limits=f.LIMITS))
        self.assertEqual(vars(value), {'_json': self.text})

    def test_global_hard_ceilings_with_small_scoped_constants(self):
        """Hard ceilings independently constrain processing without allocating oversized fixtures."""
        cases = (('MAX_PACKET_BYTES', 'max_packet_bytes', self.size),
                 ('MAX_WORK_BYTES', 'max_work_bytes', 64 * self.size),
                 ('MAX_NODES', 'max_nodes', self.nodes), ('MAX_DEPTH', 'max_depth', self.depth))
        for constant, field, number in cases:
            with self.subTest(constant=constant):
                with patch.object(b, constant, number):
                    limits = replace(f.LIMITS, **{field: number})
                    b.LifecycleReportBinding(self.packet, limits=limits)
                with patch.object(b, constant, number - 1):
                    limits = replace(f.LIMITS, **{field: number - 1})
                    with self.allocation_guards(), self.assertRaises(b.LifecycleReportBindingLimitError):
                        b.LifecycleReportBinding(self.packet, limits=limits)
        with patch.object(b, 'MAX_INPUT_BYTES', self.size):
            b.loads_binding(self.text, limits=replace(f.LIMITS, max_input_bytes=self.size))
        with patch.object(b, 'MAX_INPUT_BYTES', self.size - 1):
            limits = replace(f.LIMITS, max_input_bytes=self.size - 1)
            with patch.object(b.json, 'loads', side_effect=AssertionError('raw hard ceiling bypassed')):
                with self.assertRaises(b.LifecycleReportBindingLimitError):
                    b.loads_binding(self.text, limits=limits)
        # Invalid UTF-8 cannot take precedence over the required raw reservation.
        with self.assertRaises(b.LifecycleReportBindingLimitError):
            b.loads_binding(b'\xff', limits=replace(f.LIMITS, max_work_bytes=7))
