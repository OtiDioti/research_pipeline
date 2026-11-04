"""Independent envelope accounting, stage precedence and finite provenance work.

Global operation sentinels are scoped to serial methods in an existing isolated
module worker. No scheduling changes or parallel-test dependencies are introduced.
"""

from copy import deepcopy
from dataclasses import fields
import json
import unittest
from unittest.mock import patch

from research_pipeline import tool_assessment_envelope as envelope_module, tool_release_codec
from research_pipeline.domain import CreationProvenance, RecordReference, ArtifactReference
from research_pipeline.tool_assessment import (
    ToolAssessment, ToolAssessmentLimits, ToolAssessmentLimitError as Limit,
    ToolAssessmentValidationError as Invalid,
)
from research_pipeline.tool_assessment_envelope import (
    ToolAssessmentEnvelopeLimits as Limits, encode_envelope, decode_envelope,
)
from tests.tool_assessment_fixtures import (
    assessment, creator, wire, forged, metadata_chars, canonical, requirements,
)
from tests.test_tool_assessment import trap


class ToolAssessmentEnvelopeBoundsTests(unittest.TestCase):
    """Validate independent supplied/derived bounds before protected allocations and snapshots."""

    def setUp(self):
        """Prepare complete inputs and independent exact counts before patching protected operations."""
        self.content = assessment()
        self.creator = creator()
        self.envelope = encode_envelope("assessment", 1, self.content, self.creator)
        self.required = {"max_metadata_chars": metadata_chars(self.envelope),
                         "max_projection_references": len(self.envelope.record_references) + len(self.envelope.artifact_references),
                         "max_provenance_depth": 3}

    def conversions(self, limits):
        """Exercise both public envelope directions with the same external envelope limits."""
        return (lambda: encode_envelope("assessment", 1, self.content, self.creator, envelope_limits=limits),
                lambda: decode_envelope(self.envelope, envelope_limits=limits))

    def test_all_three_ceilings_equality_deficit_and_combined(self):
        """Use independent complete metadata, projection occurrence and provenance-depth counts."""
        for name, amount in self.required.items():
            for convert in self.conversions(Limits(**{name: amount})):
                convert()
            for convert in self.conversions(Limits(**{name: amount - 1})):
                with self.subTest(name=name):
                    with self.assertRaisesRegex(Limit, name):
                        convert()
        for convert in self.conversions(Limits(**self.required)):
            convert()

    def test_supplied_tuple_guard_precedes_any_element_inspection(self):
        """Count every tuple element, including duplicate artifacts, before exact nested type checks."""
        oversized = forged(self.envelope, record_references=(object(),) * 1025,
                           artifact_references=(), _content_json="invalid JSON")
        with patch.object(envelope_module, "_supplied_fields", side_effect=trap):
            with self.assertRaisesRegex(Limit, "max_projection_references"):
                decode_envelope(oversized)
        with patch.object(envelope_module, "_supplied_fields", wraps=envelope_module._supplied_fields) as spy:
            decode_envelope(self.envelope, envelope_limits=Limits(max_projection_references=self.required["max_projection_references"]))
            self.assertEqual(spy.call_count, 1)
        duplicated = forged(self.envelope, artifact_references=(self.envelope.artifact_references[0],) * 1025)
        with self.assertRaisesRegex(Limit, "max_projection_references"):
            decode_envelope(duplicated)

    def test_complete_supplied_metadata_precedes_content_parse_and_scalar_syntax(self):
        """Complete text quota wins over later invalid syntax or malformed retained content."""
        amount = self.required["max_metadata_chars"]
        with patch.object(tool_release_codec.json, "loads", side_effect=trap):
            with self.assertRaisesRegex(Limit, "max_metadata_chars"):
                decode_envelope(self.envelope, envelope_limits=Limits(max_metadata_chars=amount - 1))
        with patch.object(tool_release_codec.json, "loads", wraps=json.loads) as spy:
            decode_envelope(self.envelope, envelope_limits=Limits(max_metadata_chars=amount))
            self.assertGreater(spy.call_count, 1)
        bad_reference = forged(self.envelope.record_references[0], revision=0)
        envelope = forged(self.envelope, record_references=(bad_reference,) + self.envelope.record_references[1:],
                          _content_json="invalid JSON")
        with self.assertRaisesRegex(Limit, "max_metadata_chars"):
            decode_envelope(envelope, envelope_limits=Limits(max_metadata_chars=amount - 1))
        with self.assertRaisesRegex(Invalid, "envelope"):
            decode_envelope(envelope)
        for value in (forged(self.creator, _details_json="x" * 262145),
                      forged(self.creator, actor="x" * 262145)):
            with patch.object(envelope_module, "_parse", side_effect=trap):
                with self.assertRaisesRegex(Limit, "max_metadata_chars"):
                    encode_envelope("assessment", 1, self.content, value)

    def test_derived_count_and_metadata_guards_precede_real_snapshots_and_reference_creation(self):
        """Short supplied projections cannot conceal oversized derived projections or metadata."""
        short = forged(self.envelope, record_references=(), artifact_references=())
        for name in ("max_metadata_chars", "max_projection_references"):
            limits = Limits(**{name: self.required[name] - 1})
            for protected in (CreationProvenance, RecordReference, ArtifactReference):
                method = "__init__" if protected is CreationProvenance else "__post_init__"
                with patch.object(protected, method, side_effect=trap):
                    for convert in (lambda: encode_envelope("assessment", 1, self.content, self.creator, envelope_limits=limits),
                                    lambda: decode_envelope(short, envelope_limits=limits)):
                        with self.assertRaisesRegex(Limit, name):
                            convert()
                original = getattr(protected, method)
                with patch.object(protected, method, autospec=True, side_effect=original) as spy:
                    encode_envelope("assessment", 1, self.content, self.creator,
                                    envelope_limits=Limits(**{name: self.required[name]}))
                    self.assertGreater(spy.call_count, 0)

    def test_provenance_depth_precedes_its_actual_json_loads_and_not_content_loads(self):
        """Sentinels distinguish the guarded provenance parser from the earlier content parser."""
        original = json.loads
        text = self.creator._details_json

        def guarded(data, *args, **kwargs):
            """Allow bounded content parsing, detecting any premature provenance parse."""
            if data == text:
                return trap()
            return original(data, *args, **kwargs)
        for convert in self.conversions(Limits(max_provenance_depth=2)):
            with patch.object(envelope_module.json, "loads", side_effect=guarded):
                with self.assertRaisesRegex(Limit, "max_provenance_depth"):
                    convert()
        for convert in self.conversions(Limits(max_provenance_depth=3)):
            with patch.object(envelope_module.json, "loads", wraps=original) as spy:
                convert()
                self.assertTrue(any(call.args[0] == text for call in spy.call_args_list))

    def test_supplied_and_derived_projection_budgets_are_independent(self):
        """A valid full envelope fits its quota once; mismatched projections are never repaired."""
        limits = Limits(**self.required)
        self.assertEqual(decode_envelope(self.envelope, envelope_limits=limits), self.content)
        smaller = forged(self.envelope, record_references=self.envelope.record_references[:-1])
        with self.assertRaisesRegex(Invalid, "projections"):
            decode_envelope(smaller, envelope_limits=limits)
        with self.assertRaisesRegex(Limit, "max_projection_references"):
            decode_envelope(smaller, envelope_limits=Limits(max_projection_references=self.required["max_projection_references"] - 1))

    def test_hard_metadata_equality_and_over_bound_forgery(self):
        """Use full retained JSON text, allowing metadata strings larger than content text ceilings."""
        minimal = creator({"padding": ""})
        envelope = encode_envelope("assessment", 1, self.content, minimal)
        padding = 262144 - metadata_chars(envelope)
        provenance = creator({"padding": "x" * padding})
        envelope = encode_envelope("assessment", 1, self.content, provenance)
        self.assertEqual(metadata_chars(envelope), 262144)
        self.assertEqual(decode_envelope(envelope), self.content)
        for consume in (lambda: encode_envelope("assessment", 1, self.content, provenance, envelope_limits=Limits(max_metadata_chars=262143)),
                        lambda: decode_envelope(envelope, envelope_limits=Limits(max_metadata_chars=262143))):
            with self.assertRaisesRegex(Limit, "max_metadata_chars"):
                consume()
        oversized = forged(provenance, _details_json=provenance._details_json + " ")
        with patch.object(envelope_module, "_provenance", side_effect=trap):
            with self.assertRaisesRegex(Limit, "max_metadata_chars"):
                encode_envelope("assessment", 1, self.content, oversized)

    def test_hard_projection_maximum_counts_repeated_records(self):
        """Distribute 1024 legal occurrences over finite lists without deduplicating records."""
        value = wire()
        value["lifecycle"]["evidence"]["value"][0]["artifacts"]["value"].pop()
        lists = [value["environment"]["records"]["value"],
                 value["environment"]["dependencies"]["value"][0]["records"]["value"],
                 value["checks"]["value"][0]["definition_records"]["value"],
                 value["checks"]["value"][1]["definition_records"]["value"]]
        remaining = 1024 - requirements(value)["max_references"]
        for items in lists:
            count = min(256 - len(items), remaining)
            items.extend(deepcopy(items[0]) for _ in range(count))
            remaining -= count
        self.assertEqual(remaining, 0)
        content = ToolAssessment.from_dict(value)
        envelope = encode_envelope("assessment", 1, content, self.creator)
        self.assertEqual(len(envelope.record_references) + len(envelope.artifact_references), 1024)
        self.assertEqual(decode_envelope(envelope), content)
        with self.assertRaisesRegex(Limit, "max_projection_references"):
            decode_envelope(envelope, envelope_limits=Limits(max_projection_references=1023))

    def test_feasible_maximal_provenance_depth_and_escape_aware_brackets(self):
        """Reach depth 24; reject forged depth 25 before parsing, ignoring brackets inside strings."""
        nested = {"literal": '[{\\"}]'}
        for _ in range(23):
            nested = {"child": nested}
        provenance = creator(nested)
        envelope = encode_envelope("assessment", 1, self.content, provenance)
        self.assertEqual(decode_envelope(envelope), self.content)
        with self.assertRaisesRegex(Limit, "max_provenance_depth"):
            decode_envelope(envelope, envelope_limits=Limits(max_provenance_depth=23))
        over = forged(provenance, _details_json='{"child":' + provenance._details_json + '}')
        with patch.object(CreationProvenance, "__init__", side_effect=trap):
            with self.assertRaisesRegex(Limit, "max_provenance_depth"):
                encode_envelope("assessment", 1, self.content, over)
        root_only = creator({})
        encode_envelope("assessment", 1, self.content, root_only, envelope_limits=Limits(max_provenance_depth=1))
        with self.assertRaisesRegex(Limit, "max_provenance_depth"):
            encode_envelope("assessment", 1, self.content, root_only, envelope_limits=Limits(max_provenance_depth=0))

    def test_derived_provenance_work_bounds_with_wide_memberships_and_tokens(self):
        """Measured nodes/strings/memberships are at most charged ASCII n, not attainable equalities."""
        details = {"members": [{"index": i, "flag": True} for i in range(1500)],
                   "wide": "😀" * 3000, "integer": -123456789012345678901234567890,
                   "float": 1e100, "escapes": '[\\"]{}'}
        provenance = creator(details)
        text = provenance._details_json
        counts = {"nodes": 0, "members": 0, "chars": 0}

        def measure(item):
            """Independently count generic JSON work without applying content scalar rules."""
            counts["nodes"] += 1
            if type(item) is str:
                counts["chars"] += len(item)
            elif type(item) is dict:
                counts["members"] += len(item)
                for key, value in item.items():
                    measure(key)
                    measure(value)
            elif type(item) is list:
                counts["members"] += len(item)
                for value in item:
                    measure(value)
        measure(details)
        for count in counts.values():
            self.assertLess(count, len(text))
        envelope = encode_envelope("assessment", 1, self.content, provenance)
        self.assertEqual(decode_envelope(envelope), self.content)
        self.assertEqual(envelope.provenance.details, details)

    def test_envelope_limits_validation_order_and_bypass_mutations(self):
        """Validate content controls then envelope controls before payload receiver access."""
        for field in fields(Limits):
            for bad in (True, 1.5, -1, field.default + 1, "1"):
                with self.assertRaises(Invalid):
                    Limits(**{field.name: bad})
                bypass = Limits()
                object.__setattr__(bypass, field.name, bad)
                with self.assertRaisesRegex(Invalid, field.name):
                    decode_envelope(object(), envelope_limits=bypass)
            bypass = Limits()
            object.__delattr__(bypass, field.name)
            with self.assertRaises(Invalid):
                decode_envelope(object(), envelope_limits=bypass)
        with self.assertRaisesRegex(Invalid, "limits: expected exact ToolAssessmentLimits"):
            decode_envelope(object(), limits=object(), envelope_limits=object())
        with self.assertRaisesRegex(Invalid, "envelope_limits"):
            decode_envelope(object(), envelope_limits=object())
        for name in ("max_metadata_chars", "max_projection_references"):
            with self.assertRaisesRegex(Limit, name):
                decode_envelope(self.envelope, envelope_limits=Limits(**{name: 0}))

    def test_stage_precedence_multiple_simultaneous_faults(self):
        """Earlier bounds/stages win over later schema, provenance, identity and projection errors."""
        envelope = forged(self.envelope, record_references=(object(),) * 1025,
                          _content_json="not JSON", provenance=object())
        with self.assertRaisesRegex(Limit, "max_projection_references"):
            decode_envelope(envelope)
        envelope = forged(self.envelope, operational_status="active")
        with self.assertRaisesRegex(Invalid, "both states"):
            decode_envelope(envelope, envelope_limits=Limits(max_projection_references=0))
        # C closed schema precedes D derived bounds and E malformed provenance.
        value = wire()
        value["target"]["release"]["relationship"] = "wrong"
        envelope = forged(self.envelope, record_references=(), artifact_references=(),
                          _content_json=canonical(value), provenance=forged(self.creator, _details_json="{"))
        with self.assertRaisesRegex(Invalid, "reference role"):
            decode_envelope(envelope, envelope_limits=Limits(max_projection_references=0))
        envelope = forged(self.envelope, record_references=(), artifact_references=(),
                          provenance=forged(self.creator, _details_json="{"))
        with self.assertRaisesRegex(Limit, "max_projection_references"):
            decode_envelope(envelope, envelope_limits=Limits(max_projection_references=0))

    def test_smaller_content_limits_forwarded_and_envelope_limits_not_remembered(self):
        """Never expand external ceilings or retain them as content/envelope dependencies."""
        needed = requirements(wire())
        limits = ToolAssessmentLimits(**{**needed, "max_wire_bytes": 0})
        envelope_limits = Limits(**self.required)
        envelope = encode_envelope("assessment", 1, self.content, self.creator, limits=limits, envelope_limits=envelope_limits)
        self.assertEqual(decode_envelope(envelope, limits=limits, envelope_limits=envelope_limits), self.content)
        object.__setattr__(envelope_limits, "max_metadata_chars", 0)
        self.assertEqual(decode_envelope(envelope), self.content)
        with self.assertRaisesRegex(Limit, "max_metadata_chars"):
            decode_envelope(envelope, envelope_limits=envelope_limits)

    def test_raw_field_order_before_later_missing_attributes(self):
        """An earlier metadata length/type violation wins over later absent raw fields."""
        provenance = object.__new__(CreationProvenance)
        with self.assertRaisesRegex(Limit, "max_metadata_chars"):
            encode_envelope("assessment", 1, self.content, provenance, envelope_limits=Limits(max_metadata_chars=0))
        pin = object.__new__(RecordReference)
        object.__setattr__(pin, "record_id", "x" * 262145)
        envelope = forged(self.envelope, record_references=(pin,), artifact_references=())
        with self.assertRaisesRegex(Limit, "max_metadata_chars"):
            decode_envelope(envelope)
        pin = object.__new__(ArtifactReference)
        object.__setattr__(pin, "digest", "x" * 262145)
        envelope = forged(self.envelope, record_references=(), artifact_references=(pin,))
        with self.assertRaisesRegex(Limit, "max_metadata_chars"):
            decode_envelope(envelope)
