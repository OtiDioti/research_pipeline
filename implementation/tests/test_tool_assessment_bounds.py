"""Independent content accounting and preallocation guard ordering.

Protected-operation patches run serially inside the validator's existing isolated
module worker, so other test modules never observe their process-global changes.
"""

from dataclasses import fields
import json
import unittest
from unittest.mock import patch

from research_pipeline import tool_assessment as content_module, tool_release_codec
from research_pipeline.tool_assessment import (
    ToolAssessment, ToolAssessmentLimits as Limits, ToolAssessmentLimitError as Limit,
    ToolAssessmentValidationError as Invalid, decode_content, loads_content, dumps_content,
)
from research_pipeline.tool_assessment_envelope import encode_envelope, decode_envelope
from tests.tool_assessment_fixtures import (
    assessment, wire, constructor_fields, requirements, canonical, creator, forged,
)
from tests.test_tool_assessment import trap


class ToolAssessmentBoundsTests(unittest.TestCase):
    """Check all independent ceilings through exact public boundaries with real operation sentinels."""

    def setUp(self):
        """Prepare synthetic inputs and independent measurements before installing spies."""
        self.wire = wire()
        self.content = assessment()
        self.text = canonical(self.wire)
        self.needed = requirements(self.wire)
        self.fields = constructor_fields(self.wire)
        self.envelope = encode_envelope("assessment", 1, self.content, creator())

    def consumers(self, limits, *, external=True):
        """Return operations covering every applicable constructor, decoder and retained boundary."""
        result = [lambda: ToolAssessment(**self.fields, limits=limits),
                  lambda: ToolAssessment.from_dict(self.wire, limits=limits),
                  lambda: decode_content(self.wire, limits=limits),
                  lambda: self.content.to_dict(limits=limits),
                  lambda: dumps_content(self.content, limits=limits),
                  lambda: encode_envelope("assessment", 1, self.content, creator(), limits=limits),
                  lambda: decode_envelope(self.envelope, limits=limits)]
        if external:
            result.extend((lambda: loads_content(self.text, limits=limits),
                           lambda: loads_content(self.text.encode(), limits=limits)))
        return result

    def test_all_eight_ceilings_equality_deficit_and_combined(self):
        """Independent fixture accounting sets exact legal ceilings and one-unit deficits."""
        for name, amount in self.needed.items():
            exact = Limits(**{name: amount})
            deficient = Limits(**{name: amount - 1})
            consumers = (lambda x: [lambda: loads_content(self.text, limits=x),
                                    lambda: loads_content(self.text.encode(), limits=x)]) if name == "max_wire_bytes" else self.consumers
            for operation in consumers(exact):
                with self.subTest(name=name, boundary=operation, case="equal"):
                    operation()
            for operation in consumers(deficient):
                with self.subTest(name=name, boundary=operation, case="deficit"):
                    with self.assertRaisesRegex(Limit, name):
                        operation()
        for operation in self.consumers(Limits(**self.needed)):
            operation()

    def test_wire_zero_applies_only_to_external_loads_and_is_not_retained(self):
        """Honor smaller caller limits without remembering them or applying wire quota internally."""
        limits = Limits(max_wire_bytes=0)
        for operation in self.consumers(limits, external=False):
            operation()
        with self.assertRaisesRegex(Limit, "max_wire_bytes"):
            loads_content(self.text, limits=limits)
        content = decode_content(self.wire, limits=limits)
        object.__setattr__(limits, "max_nodes", 0)
        self.assertEqual(content.to_dict(), self.wire)
        with self.assertRaisesRegex(Limit, "max_nodes"):
            content.to_dict(limits=limits)

    def test_lexical_deficits_precede_actual_json_loads_with_equality_spies(self):
        """Guard complete external JSON allocations using actual stdlib parser sentinels."""
        for name in ("max_wire_bytes", "max_canonical_bytes", "max_string_chars", "max_collection_items",
                     "max_nodes", "max_depth", "max_reconstruction_units"):
            amount = self.needed[name]
            with self.subTest(name=name):
                with patch.object(tool_release_codec.json, "loads", side_effect=trap):
                    with self.assertRaisesRegex(Limit, name):
                        loads_content(self.text, limits=Limits(**{name: amount - 1}))
                with patch.object(tool_release_codec.json, "loads", wraps=json.loads) as spy:
                    loads_content(self.text, limits=Limits(**{name: amount}))
                    self.assertGreater(spy.call_count, 0)

    def test_complete_canonical_deficit_precedes_actual_json_dumps(self):
        """Count headers, framing, escapes, keys and empties before any canonical serializer runs."""
        amount = self.needed["max_canonical_bytes"]
        for consume in (lambda limits: ToolAssessment(**self.fields, limits=limits),
                        lambda limits: decode_content(self.wire, limits=limits),
                        lambda limits: self.content.to_dict(limits=limits)):
            with patch.object(tool_release_codec.json, "dumps", side_effect=trap):
                with self.assertRaisesRegex(Limit, "max_canonical_bytes"):
                    consume(Limits(max_canonical_bytes=amount - 1))
            with patch.object(tool_release_codec.json, "dumps", wraps=json.dumps) as spy:
                consume(Limits(max_canonical_bytes=amount))
                self.assertGreater(spy.call_count, 0)

    def test_reference_guard_precedes_detachment_and_reference_construction(self):
        """Charge every record and artifact occurrence, including later deduplicated candidates."""
        amount = self.needed["max_references"]
        for protected in ("_detached", "RecordReference", "ArtifactReference"):
            # Replacing a type would change schema identity dispatch. Patch its
            # real initializer instead to observe protected domain construction.
            target = getattr(content_module, protected)
            if protected == "_detached":
                patcher = patch.object(content_module, protected, side_effect=trap)
                success = patch.object(content_module, protected, wraps=target)
            else:
                patcher = patch.object(target, "__post_init__", side_effect=trap)
                success = patch.object(target, "__post_init__", autospec=True, side_effect=target.__post_init__)
            with patcher:
                with self.assertRaisesRegex(Limit, "max_references"):
                    decode_content(self.wire, limits=Limits(max_references=amount - 1))
            with success as spy:
                decode_content(self.wire, limits=Limits(max_references=amount))
                self.assertGreater(spy.call_count, 0)

    def test_independent_accounting_del_supplementary_empty_and_wire_whitespace(self):
        """Include DEL escapes, supplementary scalars, repeated keys/text and empty framing."""
        for text in (json.dumps(self.wire, ensure_ascii=False, indent=3), self.text.replace("\\u007f", "\x7f"),
                     self.text.replace("\\ud83d\\ude00", "😀")):
            amount = len(text.encode("utf-8"))
            self.assertEqual(loads_content(text, limits=Limits(max_wire_bytes=amount)), self.content)
            with patch.object(tool_release_codec.json, "loads", side_effect=trap):
                with self.assertRaisesRegex(Limit, "max_wire_bytes"):
                    loads_content(text, limits=Limits(max_wire_bytes=amount - 1))
        for value in ({}, {"": []}, {"x": [None, "", {}, []]}, {"x": "\x7f😀"}):
            needed = requirements(value)
            for name in ("max_canonical_bytes", "max_nodes", "max_reconstruction_units", "max_depth"):
                with self.subTest(value=value, name=name):
                    with self.assertRaisesRegex(Limit, name):
                        decode_content(value, limits=Limits(**{name: needed[name] - 1}))
        with self.assertRaisesRegex(Invalid, "surrogate"):
            loads_content('"\ud800"')

    def test_limit_exactness_zero_hard_maxima_and_bypass_revalidation(self):
        """Reject missing, subclass, bool, float, negative and enlarged external ceilings first."""
        self.assertEqual(Limits(), Limits(**{field.name: field.default for field in fields(Limits)}))
        for field in fields(Limits):
            for bad in (True, 1.0, -1, field.default + 1, "1"):
                with self.subTest(field=field.name, bad=bad):
                    with self.assertRaises(Invalid):
                        Limits(**{field.name: bad})
                    bypass = Limits()
                    object.__setattr__(bypass, field.name, bad)
                    with self.assertRaisesRegex(Invalid, field.name):
                        dumps_content(object(), limits=bypass)
            bypass = Limits()
            object.__delattr__(bypass, field.name)
            with self.assertRaises(Invalid):
                decode_content({}, limits=bypass)
            zero = Limits(**{field.name: 0})
            with self.assertRaisesRegex(Limit, field.name):
                loads_content(self.text, limits=zero)
        with self.assertRaisesRegex(Invalid, "max_wire_bytes"):
            loads_content(object(), limits=forged(Limits(), max_wire_bytes=-1, max_nodes=-1))

    def test_guard_precedence_and_smaller_limits_forwarded(self):
        """Limits precede receivers; tree bounds precede missing format and semantic faults."""
        with self.assertRaisesRegex(Invalid, "limits"):
            ToolAssessment.to_dict(object(), limits=object())
        with self.assertRaisesRegex(Limit, "max_nodes"):
            decode_content({}, limits=Limits(max_nodes=0))
        invalid = wire()
        invalid["target"]["release"]["relationship"] = "wrong"
        with self.assertRaisesRegex(Limit, "max_references"):
            decode_content(invalid, limits=Limits(max_references=0))
        with self.assertRaisesRegex(Limit, "max_canonical_bytes"):
            self.content.to_dict(limits=Limits(max_canonical_bytes=self.needed["max_canonical_bytes"] - 1))
        # Every internal reconstruction must preserve this valid combined smaller set.
        limits = Limits(**self.needed)
        original = content_module._checked_limits
        with patch.object(content_module, "_checked_limits", wraps=original) as spy:
            loads_content(self.text, limits=limits)
            self.assertTrue(all(call.args[0] is limits for call in spy.call_args_list))

    def test_predecessor_error_translation_preserves_causes_and_assertions(self):
        """Assessment wrappers translate predecessor failures without changing predecessor behavior."""
        from research_pipeline import tool_assessment_codec as codec
        with self.assertRaises(Limit) as caught:
            codec._preflight({}, Limits(max_nodes=0))
        self.assertIs(type(caught.exception.__cause__), tool_release_codec.ToolReleaseLimitError)
        self.assertIn("max_nodes", str(caught.exception))
        with self.assertRaises(Invalid) as caught:
            codec._parse(b"\xff", Limits())
        self.assertIs(type(caught.exception.__cause__), tool_release_codec.ToolReleaseValidationError)
        with patch.object(tool_release_codec, "checked_limits", side_effect=trap):
            self.assertEqual(decode_content(self.wire), self.content)
        for operation in ("preflight", "parse", "detached", "canonical", "raw_attribute"):
            with patch.object(tool_release_codec, operation, side_effect=trap):
                with self.assertRaises(AssertionError):
                    decode_content(self.wire) if operation != "parse" else loads_content(self.text)
