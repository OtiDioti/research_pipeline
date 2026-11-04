"""Independent envelope ceilings and protected-operation witnesses for both conversions."""

from dataclasses import fields
import unittest
from unittest.mock import patch

from research_pipeline import domain, tool_release as content_product
from research_pipeline import tool_release_envelope as product
from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordEnvelope, RecordReference
from research_pipeline.tool_release import ToolRelease, ToolReleaseLimits, ToolReleaseLimitError, ToolReleaseValidationError
from research_pipeline.tool_release_envelope import ToolReleaseEnvelopeLimits, encode_envelope, decode_envelope
from tests.test_tool_release_envelope import fail_hook, hostile
from tests.tool_release_fixtures import canonical, constructor_sections, known, record, requirements, wire
from tests.tool_release_envelope_fixtures import complete_wire, creator, forged, metadata_chars, release, unlinked_release


class ToolReleaseEnvelopeBoundsTests(unittest.TestCase):
    """Exercise each independent ceiling before actual reconstruction/copy/serialization work."""

    def setUp(self):
        """Build complete valid inputs and independent counts before installing sentinels."""
        self.release = release()
        self.provenance = creator()
        self.envelope = encode_envelope("affine_tool", 9, self.release, self.provenance)
        self.amounts = {"max_metadata_chars": metadata_chars(self.envelope),
                        "max_projection_references": 15 + 5}
        self.assertEqual(len(self.envelope.record_references) + len(self.envelope.artifact_references), 20)

    def conversions(self, limits=None, envelope=None):
        """Provide both consumption boundaries using already prepared inputs."""
        return (
            lambda ceilings: encode_envelope("affine_tool", 9, self.release, self.provenance,
                                             limits=limits, envelope_limits=ceilings),
            lambda ceilings: decode_envelope(self.envelope if envelope is None else envelope,
                                             limits=limits, envelope_limits=ceilings),
        )

    def test_independent_equality_and_one_unit_deficits_before_protected_work(self):
        """Each deficit precedes reachable provenance, references, snapshots and serialization."""
        operations = ((product, "_provenance"), (product, "_pairs"),
                      (CreationProvenance, "__init__"), (RecordReference, "__post_init__"),
                      (ArtifactReference, "__post_init__"), (RecordEnvelope, "__init__"),
                      (domain, "_snapshot"), (domain.json, "dumps"),
                      (content_product, "_references_and_dimensions"))
        for name, amount in self.amounts.items():
            equal = ToolReleaseEnvelopeLimits(**{name: amount})
            short = ToolReleaseEnvelopeLimits(**{name: amount - 1})
            for boundary in self.conversions():
                for owner, operation in operations:
                    with self.subTest(limit=name, operation=operation, boundary=boundary):
                        original = getattr(owner, operation)
                        with patch.object(owner, operation, autospec=True, side_effect=original) as spy:
                            boundary(equal)
                            self.assertTrue(spy.called, operation)
                        with patch.object(owner, operation, side_effect=fail_hook):
                            with self.assertRaisesRegex(ToolReleaseLimitError, name):
                                boundary(short)
        equal = ToolReleaseEnvelopeLimits(**self.amounts)
        for boundary in self.conversions():
            boundary(equal)
            for name, amount in self.amounts.items():
                with self.assertRaisesRegex(ToolReleaseLimitError, name):
                    boundary(ToolReleaseEnvelopeLimits(**{**self.amounts, name: amount - 1}))

    def test_count_uses_occurrences_and_details_uses_full_serialized_text(self):
        """Repeated record pins count separately; digest deduplication and escaped details count exactly."""
        self.assertGreater(len(self.envelope.record_references), len(set(self.envelope.record_references)))
        self.assertEqual(self.amounts["max_projection_references"], 20)
        text = canonical(self.provenance.details)
        self.assertEqual(text, self.provenance._details_json)
        self.assertIn('\\ud83d\\ude00', text)
        self.assertIn('\\u03b1', text)
        self.assertEqual(self.amounts["max_metadata_chars"],
                         len("affine_tooltool_releaseenvelope_creator2026-11-04T10:00:00.000000Z") + len(text)
                         + sum(len(pin.record_id + pin.relationship + pin.target_kind) for pin in self.envelope.record_references)
                         + 5 * 64)
        # Every supplied occurrence counts, even duplicate artifact digests.
        envelope = forged(self.envelope, artifact_references=self.envelope.artifact_references * 2)
        with patch.object(product, "parse", side_effect=fail_hook):
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_projection_references"):
                decode_envelope(envelope, envelope_limits=ToolReleaseEnvelopeLimits(max_projection_references=20))

    def test_supplied_and_expected_envelopes_are_bounded_independently(self):
        """Small supplied projections cannot evade a larger content-derived ceiling or double-charge it."""
        for boundary in self.conversions():
            boundary(ToolReleaseEnvelopeLimits(**self.amounts))
        shortened = forged(self.envelope, record_references=self.envelope.record_references[:1])
        for name, amount in self.amounts.items():
            with self.subTest(limit=name), patch.object(CreationProvenance, "__init__", side_effect=fail_hook):
                with self.assertRaisesRegex(ToolReleaseLimitError, name):
                    decode_envelope(shortened, envelope_limits=ToolReleaseEnvelopeLimits(**{name: amount - 1}))
        with self.assertRaisesRegex(ToolReleaseValidationError, "projections"):
            decode_envelope(shortened)

    def test_hard_metadata_maximum_with_bounded_provenance_padding(self):
        """A complete valid envelope reaches exactly 262144 retained metadata characters."""
        empty = CreationProvenance("creator", "2026-11-04T00:00:00Z", {"padding": ""})
        base = encode_envelope("affine_tool", 9, self.release, empty)
        padding = 262144 - metadata_chars(base)
        provenance = CreationProvenance("creator", "2026-11-04T00:00:00Z", {"padding": "x" * padding})
        envelope = encode_envelope("affine_tool", 9, self.release, provenance)
        self.assertEqual(metadata_chars(envelope), 262144)
        self.assertEqual(decode_envelope(envelope), self.release)
        short = ToolReleaseEnvelopeLimits(max_metadata_chars=262143)
        for boundary in (lambda: encode_envelope("affine_tool", 9, self.release, provenance, envelope_limits=short),
                         lambda: decode_envelope(envelope, envelope_limits=short)):
            with patch.object(CreationProvenance, "__init__", side_effect=fail_hook):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_metadata_chars"):
                    boundary()

    def test_hard_projection_maximum_distributed_over_legal_collections(self):
        """1024 ordered record occurrences fit content ceilings without flattening an oversized collection."""
        doc = wire(kind="remote_service")
        doc["identity"]["provenance_records"] = known([record("reported_provenance", "source", "s")] * 256)
        doc["identity"]["implementation"]["source_records"] = known([record("implementation_source", "source", "s")] * 256)
        doc["evidence_limitations"]["evidence"] = known([record("reported_evidence", "evidence", "e")] * 256)
        doc["reproducibility"]["dependency_records"] = known([record("build_dependency", "source", "s")] * 256)
        doc["evidence_limitations"]["qualification_reports"] = known([])
        doc["evidence_limitations"]["issues"] = known([])
        doc["evidence_limitations"]["self_tests"] = known([])
        doc["invocation"]["adapter"]["files"] = known([])
        doc["invocation"]["adapter"]["entry_file"] = known(None)
        value = ToolRelease(**constructor_sections(doc))
        envelope = encode_envelope("affine_tool", 1, value, self.provenance)
        self.assertEqual(len(envelope.record_references), 1024)
        self.assertEqual(envelope.artifact_references, ())
        self.assertEqual([pin.relationship for pin in envelope.record_references],
                         ["reported_provenance"] * 256 + ["implementation_source"] * 256
                         + ["reported_evidence"] * 256 + ["build_dependency"] * 256)
        self.assertEqual(requirements(value.to_dict())["max_references"], 1024)
        self.assertEqual(decode_envelope(envelope), value)
        short = ToolReleaseEnvelopeLimits(max_projection_references=1023)
        for boundary in (lambda: encode_envelope("affine_tool", 1, value, self.provenance, envelope_limits=short),
                         lambda: decode_envelope(envelope, envelope_limits=short)):
            with patch.object(RecordReference, "__post_init__", side_effect=fail_hook):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_projection_references"):
                    boundary()

    def test_oversized_supplied_tuples_and_strings_exit_before_traversal_or_parse(self):
        """Small content cannot disguise huge forged metadata or supplied tuple membership."""
        # No element is even an exact reference: the length guard must win first.
        small = encode_envelope("affine_tool", 1, unlinked_release(), self.provenance)
        self.assertEqual(small.record_references + small.artifact_references, ())
        envelope = forged(small, record_references=(object(),) * 1025)
        with patch.object(product, "_reference_fields", side_effect=fail_hook), \
                patch.object(product, "parse", side_effect=fail_hook):
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_projection_references"):
                decode_envelope(envelope)
        for field in ("record_id", "kind"):
            envelope = forged(small, **{field: "x" * 262145})
            with patch.object(product, "parse", side_effect=fail_hook), \
                    patch.object(domain, "_identifier", side_effect=fail_hook):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_metadata_chars"):
                    decode_envelope(envelope)
        for field in ("actor", "created_at", "_details_json"):
            provenance = forged(self.provenance, **{field: "x" * 262145})
            with patch.object(product, "parse", side_effect=fail_hook), \
                    patch.object(domain, "_identifier", side_effect=fail_hook):
                for boundary in (lambda: encode_envelope("affine_tool", 1, self.release, provenance),
                                 lambda: decode_envelope(forged(small, provenance=provenance))):
                    with self.assertRaisesRegex(ToolReleaseLimitError, "max_metadata_chars"):
                        boundary()
        for collection, field in (("record_references", "record_id"), ("record_references", "relationship"),
                                  ("record_references", "target_kind"), ("artifact_references", "digest")):
            originals = getattr(self.envelope, collection)
            pin = forged(originals[0], **{field: "x" * 262145})
            envelope = forged(self.envelope, **{collection: (pin,) + originals[1:]})
            with patch.object(product, "parse", side_effect=fail_hook):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_metadata_chars"):
                    decode_envelope(envelope)

    def test_limits_constructor_aliases_and_bypass_mutations_precede_payload(self):
        """Both supplied limits objects are revalidated, including missing fields and hostile aliases."""
        for cls, keyword in ((ToolReleaseEnvelopeLimits, "envelope_limits"), (ToolReleaseLimits, "limits")):
            for field in fields(cls):
                self.assertEqual(getattr(cls(**{field.name: 0}), field.name), 0)
                for invalid in (-1, True, 1.0, hostile(int, 1), field.default + 1, None):
                    with self.subTest(limit=field.name), self.assertRaises(ToolReleaseValidationError):
                        cls(**{field.name: invalid})
                    value = cls()
                    object.__setattr__(value, field.name, invalid)
                    for boundary in (lambda: encode_envelope(None, None, None, None, **{keyword: value}),
                                     lambda: decode_envelope(None, **{keyword: value})):
                        with patch.object(product, "_base_metadata", side_effect=fail_hook):
                            with self.assertRaisesRegex(ToolReleaseValidationError, field.name):
                                boundary()
                value = cls()
                object.__delattr__(value, field.name)
                with self.assertRaisesRegex(ToolReleaseValidationError, field.name):
                    decode_envelope(None, **{keyword: value})
                with self.assertRaisesRegex(ToolReleaseValidationError, field.name):
                    encode_envelope(None, None, None, None, **{keyword: value})
            for value in ({}, object(), hostile(cls)):
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(None, **{keyword: value})
                with self.assertRaises(ToolReleaseValidationError):
                    encode_envelope(None, None, None, None, **{keyword: value})
        with self.assertRaises(ToolReleaseValidationError):
            ToolReleaseEnvelopeLimits.__post_init__(hostile(ToolReleaseEnvelopeLimits))

    def test_zero_projection_bound_and_limit_objects_are_not_retained(self):
        """An empty projection is legal at zero; limits never become a wire field or retained dependency."""
        value = unlinked_release()
        limits = ToolReleaseLimits(max_wire_bytes=0)
        ceiling = ToolReleaseEnvelopeLimits(max_projection_references=0)
        envelope = encode_envelope("affine_tool", 1, value, self.provenance, limits=limits, envelope_limits=ceiling)
        decoded = decode_envelope(envelope, limits=limits, envelope_limits=ceiling)
        self.assertEqual(envelope.record_references + envelope.artifact_references, ())
        object.__setattr__(ceiling, "max_metadata_chars", 0)
        object.__setattr__(limits, "max_nodes", 0)
        self.assertEqual(decoded, value)
        self.assertEqual(decode_envelope(envelope), value)
        for boundary in self.conversions():
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_metadata_chars"):
                boundary(ToolReleaseEnvelopeLimits(max_metadata_chars=0))

    def test_existing_content_limits_equal_and_one_below_before_reconstruction(self):
        """All retained content ceilings, aggregate pins and path work propagate without wire-byte changes."""
        doc = complete_wire()
        doc["invocation"]["adapter"]["files"]["value"][0]["path"] = "one/two/three/a.py"
        doc["invocation"]["adapter"]["entry_file"] = known("one/two/three/a.py")
        value = ToolRelease(**constructor_sections(doc))
        envelope = encode_envelope("affine_tool", 9, value, self.provenance)
        amounts = requirements(value.to_dict())
        for name, amount in amounts.items():
            equal = ToolReleaseLimits(**{name: amount})
            short = ToolReleaseLimits(**{name: amount - 1})
            for boundary in (lambda limits: encode_envelope("affine_tool", 9, value, self.provenance, limits=limits),
                             lambda limits: decode_envelope(envelope, limits=limits)):
                with self.subTest(limit=name):
                    boundary(equal)
                    if name == "max_wire_bytes":
                        boundary(ToolReleaseLimits(max_wire_bytes=0))
                        continue
                    for owner, operation in ((CreationProvenance, "__init__"), (content_product, "_references_and_dimensions"),
                                              (content_product.work_product, "_validate_paths"), (domain, "_snapshot")):
                        original = getattr(owner, operation)
                        with patch.object(owner, operation, autospec=True, side_effect=original) as spy:
                            boundary(equal)
                            self.assertTrue(spy.called)
                        with patch.object(owner, operation, side_effect=fail_hook):
                            with self.assertRaisesRegex(ToolReleaseLimitError, name):
                                boundary(short)

    def test_initial_metadata_errors_win_before_malformed_content(self):
        """Supplied metadata and projection bounds precede content and provenance parsing."""
        bad = forged(self.envelope, _content_json="not JSON",
                     provenance=forged(self.provenance, _details_json="{"))
        for name in self.amounts:
            with self.assertRaisesRegex(ToolReleaseLimitError, name):
                decode_envelope(bad, envelope_limits=ToolReleaseEnvelopeLimits(**{name: 0}))
        with patch.object(product.json, "loads", side_effect=fail_hook):
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_metadata_chars"):
                decode_envelope(forged(self.envelope, record_id="x" * 262145))
