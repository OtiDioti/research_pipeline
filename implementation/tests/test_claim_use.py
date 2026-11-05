"""Strict passive claim-use codec behavior, detachment and independent ceilings."""

from dataclasses import replace
import json
import unittest
from research_pipeline.claim_use import (
    ClaimUse, ClaimUsePremise, ClaimUseRoute, ClaimUseInspectionLimits, ClaimUseLimitError,
    WRITE_LIMITS, decode_content, dumps_content, loads_content, decode_envelope, encode_envelope,
)
from research_pipeline.domain import DomainValidationError, RecordEnvelope
from research_pipeline.scientific import NotTypedContentError
from tests.claim_use_fixtures import binding, ref, PROVENANCE, LIMITS


class ClaimUseTests(unittest.TestCase):
    """Pure exact-contract tests do not interpret reported sufficiency or authority."""

    def test_roundtrip_detached_ordered_projection(self):
        """Required arrays and conjunctions survive all codecs with no shared mutable trees."""
        original = binding()
        wire = original.to_dict()
        self.assertEqual(loads_content(dumps_content(original)), original)
        self.assertEqual(decode_content(wire), original)
        envelope = encode_envelope("use", 1, original, PROVENANCE)
        self.assertEqual(decode_envelope(envelope), original)
        self.assertEqual([r.relationship for r in envelope.record_references],
                         ["candidate_claim", "target_context", "support_route", "premise", "support_assessment",
                          "support_route", "premise", "support_assessment", "authorization_policy"])
        wire["routes"].clear()
        self.assertEqual(len(original.routes), 2)
        self.assertIsNone(envelope.scientific_disposition)
        self.assertEqual(envelope.artifact_references, ())

    def test_upstream_projection_preserves_occurrences(self):
        """Upstream pins follow each premise and remain different from support discovery."""
        value = binding(upstream="parent")
        envelope = encode_envelope("use", 1, value, PROVENANCE)
        self.assertEqual([r.relationship for r in envelope.record_references][3:6],
                         ["premise", "premise_use", "support_assessment"])
        self.assertEqual(decode_envelope(envelope), value)

    def test_bad_headers_required_arrays_and_forbidden_authority(self):
        """Missing format differs from malformed content; no field implies authorization."""
        original = binding().to_dict()
        missing = dict(original)
        del missing["format"]
        with self.assertRaises(NotTypedContentError):
            decode_content(missing)
        for field, value in (("version", True), ("version", 2), ("format", "other"),
                             ("kind", "promotion_eligibility"), ("routes", ()),
                             ("issues", None), ("policies", []), ("eligible", True),
                             ("generation", 1), ("approval", "approved"), ("disposition", "supported")):
            with self.subTest(field=field, value=value), self.assertRaises(DomainValidationError):
                decode_content({**original, field: value})
        for field in original:
            value = dict(original)
            del value[field]
            with self.assertRaises(DomainValidationError):
                decode_content(value)

    def test_malformed_json_unicode_cycles_and_depth(self):
        """Duplicate keys, invalid scalars and excessive nesting fail instead of being repaired."""
        for text in ('{"format":1,"format":2}', '{"x":NaN}', b'\xff', '"\\ud800"', '['*65+'0'+']'*65):
            with self.subTest(text=repr(text)[:80]), self.assertRaises(DomainValidationError):
                loads_content(text)
        value = binding().to_dict()
        value["limitations"] = [float("inf")]
        with self.assertRaises(DomainValidationError):
            decode_content(value)
        value["limitations"] = [value]
        with self.assertRaises(DomainValidationError):
            decode_content(value)

    def test_exact_roles_and_duplicates(self):
        """Wrong-kind/role pins and duplicate semantic collections cannot hide in codecs."""
        value = binding()
        for field, reference in (("candidate_claim", ref("candidate", "premise", "claim")),
                                 ("target_context", ref("scope", "target_context", "claim"))):
            with self.assertRaises(DomainValidationError):
                replace(value, **{field: reference})
        for field, values in (("routes", [value.routes[0]]*2), ("policies", list(value.policies)*2),
                              ("issues", [ref("i", "relevant_issue", "issue")]*2)):
            with self.assertRaises(DomainValidationError):
                replace(value, **{field: values})
        with self.assertRaises(DomainValidationError):
            replace(value.routes[0], assessments=[])
        with self.assertRaises(DomainValidationError):
            replace(value.routes[0], assessments=list(value.routes[0].assessments)*2)
        with self.assertRaises(DomainValidationError):
            ClaimUsePremise(ref("a", "premise", "claim"), ref("u", "premise_use", "claim"))

    def test_projection_mismatch_and_forged_instances(self):
        """Decoders compare complete ordered links rather than repairing the envelope."""
        value = binding()
        envelope = encode_envelope("use", 1, value, PROVENANCE)
        for references in (envelope.record_references[:-1], tuple(reversed(envelope.record_references))):
            doc = envelope.to_dict()
            doc["record_references"] = [r.to_dict() for r in references]
            with self.assertRaises(DomainValidationError):
                decode_envelope(RecordEnvelope.from_dict(doc))
        forged = binding()
        object.__setattr__(forged, "policies", ())
        with self.assertRaises(DomainValidationError):
            dumps_content(forged)

    def test_route_and_premise_equalities_and_overflow(self):
        """Exact route/premise ceilings admit equality and reject the next occurrence."""
        base = binding()
        routes = [replace(base.routes[0], justification=ref(f"r{i}", "support_route", "justification"))
                  for i in range(16)]
        self.assertEqual(len(replace(base, routes=routes).routes), 16)
        with self.assertRaisesRegex(ClaimUseLimitError, "routes"):
            replace(base, routes=[*routes, replace(routes[0], justification=ref("extra", "support_route", "justification"))])
        route = replace(base.routes[0], premises=[ClaimUsePremise(ref(f"p{i}", "premise", "claim"), None)
                                                for i in range(256)])
        self.assertEqual(len(replace(base, routes=[route]).routes[0].premises), 256)
        with self.assertRaisesRegex(ClaimUseLimitError, "premises"):
            replace(route, premises=[*route.premises, route.premises[0]])
        with self.assertRaises(TypeError):
            WRITE_LIMITS["routes"] = 100

    def test_direct_reference_ceiling_equality_and_overflow(self):
        """The direct occurrence bound counts all assessment pins before serialization."""
        value = binding()
        route = replace(value.routes[0], premises=[], assessments=[
            ref(f"a{i}", "support_assessment", "review") for i in range(508)])
        exact = replace(value, routes=[route])
        self.assertEqual(len(encode_envelope("use", 1, exact, PROVENANCE).record_references), 512)
        with self.assertRaisesRegex(ClaimUseLimitError, "direct_references"):
            replace(value, routes=[replace(route, assessments=[*route.assessments,
                ref("extra", "support_assessment", "review")])])

    def test_required_positive_inspection_limits(self):
        """Read bounds are ordinary positive integers with independent immutable ceilings."""
        for field in ClaimUseInspectionLimits.__dataclass_fields__:
            for invalid in (True, 0, -1, 1.0, 2**63):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(DomainValidationError):
                    replace(LIMITS, **{field: invalid})
