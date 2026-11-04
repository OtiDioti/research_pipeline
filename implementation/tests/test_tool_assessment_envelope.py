"""Complete literal projections, raw envelope validation and passive detachment.

Stock serial unittest methods and existing module-worker isolation contain global
patches; inputs are fresh per test and no mutable fixture is shared with peers.
"""

from contextlib import ExitStack
import unittest
from unittest.mock import patch

from research_pipeline.domain import ArtifactReference, RecordReference, CreationProvenance, RecordEnvelope
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_assessment import ToolAssessment, ToolAssessmentValidationError as Invalid
from research_pipeline.tool_assessment_envelope import (
    ToolAssessmentEnvelopeLimits, encode_envelope, decode_envelope,
)
from tests.tool_assessment_fixtures import (
    wire, assessment, creator, forged, canonical, expected_records, expected_artifacts, known, artifact,
)
from tests.test_tool_assessment import trap, EqualityMeta, HashMeta


class ToolAssessmentEnvelopeTests(unittest.TestCase):
    """Require exact complete projections without trusting nested dataclass equality or serializers."""

    def setUp(self):
        """Construct independent synthetic inputs before any passive-operation sentinels."""
        self.content = assessment()
        self.creator = creator()
        self.envelope = encode_envelope("assessment", 1, self.content, self.creator)

    def test_complete_literal_projection_oracles_and_null_states(self):
        """Every slot projects in authored occurrence order; artifact digests select their first occurrence."""
        self.assertEqual([item.to_dict() for item in self.envelope.record_references], expected_records())
        self.assertEqual([item.to_dict() for item in self.envelope.artifact_references], expected_artifacts())
        self.assertEqual(self.envelope.kind, "tool_assessment")
        self.assertIsNone(self.envelope.operational_status)
        self.assertIsNone(self.envelope.scientific_disposition)
        self.assertNotEqual(self.creator.actor, wire()["attribution"]["actor"]["value"])
        self.assertEqual(decode_envelope(self.envelope), self.content)
        self.assertIsNot(decode_envelope(self.envelope), self.content)
        self.assertEqual(self.envelope.content["target"]["release_id"], "sha256:" + "a" * 64)

    def test_record_projection_omission_addition_substitution_relabel_duplicate_and_reordering(self):
        """Refuse each projection disagreement independently, retaining repeated occurrences exactly."""
        records = self.envelope.record_references
        changes = [records[1:], records + (records[0],),
                   (RecordReference("another", 2, "assessed_release", "tool_release"),) + records[1:],
                   (RecordReference("tool", 2, "replacement_release", "tool_release"),) + records[1:],
                   records[:3] + records[4:],
                   (records[1], records[0]) + records[2:]]
        for changed in changes:
            with self.subTest(records=changed[:2]):
                with self.assertRaisesRegex(Invalid, "projections"):
                    decode_envelope(forged(self.envelope, record_references=changed))
        for index, reference in enumerate(records):
            changed = list(records)
            changed[index] = forged(reference, revision=reference.revision + 1)
            with self.assertRaisesRegex(Invalid, "projections"):
                decode_envelope(forged(self.envelope, record_references=tuple(changed)))

    def test_artifact_projection_omission_addition_substitution_size_duplicate_and_reordering(self):
        """Refuse artifact changes separately, including a later duplicate that must not be projected."""
        artifacts = self.envelope.artifact_references
        changes = [artifacts[1:], artifacts + (ArtifactReference(**artifact("extra")),),
                   (ArtifactReference(**artifact("substitute")),) + artifacts[1:],
                   (forged(artifacts[0], size=artifacts[0].size + 1),) + artifacts[1:],
                   artifacts + (artifacts[0],), (artifacts[1], artifacts[0]) + artifacts[2:]]
        for changed in changes:
            with self.subTest(artifacts=changed[:2]):
                with self.assertRaisesRegex(Invalid, "projections"):
                    decode_envelope(forged(self.envelope, artifact_references=changed))

    def test_metadata_identity_revision_kind_and_states(self):
        """Require explicit stable identity, positive exact revisions, correct kind and null states."""
        for changes in ({"record_id": "different"}, {"revision": True}, {"revision": 0},
                        {"kind": "tool_release"}, {"operational_status": "active"},
                        {"scientific_disposition": "provisional"}, {"record_id": "bad id"}):
            with self.subTest(changes=changes):
                with self.assertRaises(Invalid):
                    decode_envelope(forged(self.envelope, **changes))
        for record_id, revision in (("different", 1), ("assessment", True), ("assessment", 0), ("assessment", 2**63)):
            with self.assertRaises(Invalid):
                encode_envelope(record_id, revision, self.content, self.creator)
        self.assertEqual(encode_envelope("assessment", 2, self.content, self.creator).content, wire())

    def test_retained_content_semantics_precede_identity_and_projections(self):
        """Check complete semantic/canonical content before later projection disagreements."""
        value = wire()
        value["execution_permission"]["rationale"] = {"state": "unknown", "value": None, "reason": "Missing"}
        envelope = forged(self.envelope, record_id="different", record_references=(), _content_json=canonical(value))
        with self.assertRaisesRegex(Invalid, "execution_permission.rationale"):
            decode_envelope(envelope)
        for text in (" " + self.envelope._content_json, self.envelope._content_json + "\n", b"{}", None):
            with self.assertRaises(Invalid):
                decode_envelope(forged(self.envelope, _content_json=text))
        with self.assertRaises(NotTypedContentError):
            decode_envelope(forged(self.envelope, _content_json="{}"))
        value = wire()
        value["lifecycle"]["evidence"]["value"][0]["artifacts"]["value"][-1]["size"] += 1
        with self.assertRaisesRegex(Invalid, "conflicting sizes"):
            decode_envelope(forged(self.envelope, _content_json=canonical(value)))

    def test_provenance_generic_scalars_and_retained_canonical_contradictions(self):
        """Allow generic booleans/signed integers/floats while rejecting normalization opportunities."""
        provenance = creator({"truth": True, "negative": -2, "finite": 1.25, "null": None,
                              "strings": ['[{}]"\\', "😀"], "array": [False, 0]})
        envelope = encode_envelope("assessment", 1, self.content, provenance)
        self.assertEqual(envelope.provenance.details, provenance.details)
        bad_texts = (' {}', '{"z":0,"a":1}', '{"a":1,"a":1}', '{"a":1,"\\u0061":2}',
                     '{"n":NaN}', '{"n":1e999}', '[]', '{"s":"\\ud800"}', '{"s":"😀"}',
                     '{"s":"\\u0061"}', '{"s":"\\ud83d\\ude00","\\ud83d\\ude00":0,"😀":1}',
                     '{"a":9223372036854775808' + '0' * 5000 + '}', '{"a":[}', '')
        for text in bad_texts:
            with self.subTest(text=text[:40]):
                bad = forged(provenance, _details_json=text)
                for consume in (lambda: encode_envelope("assessment", 1, self.content, bad),
                                lambda: decode_envelope(forged(envelope, provenance=bad))):
                    with self.assertRaises(Invalid):
                        consume()
        for date in ("2026-10-30T12:35:00Z", "2026-02-30T00:00:00.000000Z", "", None):
            with self.assertRaises(Invalid):
                decode_envelope(forged(envelope, provenance=forged(provenance, created_at=date)))

    def test_missing_retained_fields_and_forged_reference_scalar_types(self):
        """Read exact raw fields and reject bypassed missing/null/alias/range mutations."""
        for source, fields in ((self.envelope, ("record_id", "revision", "kind", "provenance", "record_references",
                                               "artifact_references", "operational_status", "scientific_disposition", "_content_json")),
                               (self.creator, ("actor", "created_at", "_details_json"))):
            for name in fields:
                damaged = forged(source)
                object.__delattr__(damaged, name)
                with self.assertRaises(Invalid):
                    decode_envelope(damaged if source is self.envelope else forged(self.envelope, provenance=damaged))
        for name, bads in (("record_id", (None, 1, "bad id")), ("revision", (True, 0, 1.0, 2**63)),
                           ("relationship", (None, "bad role")), ("target_kind", (None, "bad_kind"))):
            for bad in bads:
                reference = forged(self.envelope.record_references[0], **{name: bad})
                with self.assertRaises(Invalid):
                    decode_envelope(forged(self.envelope, record_references=(reference,) + self.envelope.record_references[1:]))
        for name, bads in (("digest", (None, "A" * 64, "x")), ("size", (True, -1, 1.0, 2**63))):
            for bad in bads:
                reference = forged(self.envelope.artifact_references[0], **{name: bad})
                with self.assertRaises(Invalid):
                    decode_envelope(forged(self.envelope, artifact_references=(reference,) + self.envelope.artifact_references[1:]))

    def test_exact_classes_and_projection_tuples_without_untrusted_hooks(self):
        """Reject hostile envelope/provenance/pin/limit subclasses and unbounded collections inertly."""
        for meta in (EqualityMeta, HashMeta):
            for base in (RecordEnvelope, CreationProvenance, RecordReference, ArtifactReference,
                         ToolAssessment, ToolAssessmentEnvelopeLimits):
                subclass = meta("Hostile", (base,), {"__doc__": "Hostile exact-type probe.",
                                                   "to_dict": trap, "__iter__": trap})
                instance = object.__new__(subclass)
                with self.assertRaises(Invalid):
                    if base is RecordEnvelope:
                        decode_envelope(instance)
                    elif base is CreationProvenance:
                        encode_envelope("assessment", 1, self.content, instance)
                    elif base is ToolAssessment:
                        encode_envelope("assessment", 1, instance, self.creator)
                    elif base is ToolAssessmentEnvelopeLimits:
                        decode_envelope(self.envelope, envelope_limits=instance)
                    elif base is RecordReference:
                        decode_envelope(forged(self.envelope, record_references=(instance,)))
                    else:
                        decode_envelope(forged(self.envelope, artifact_references=(instance,)))
        for name in ("record_references", "artifact_references"):
            for bad in ([], [object()], (trap() for _ in range(1)), None):
                with self.assertRaises(Invalid):
                    decode_envelope(forged(self.envelope, **{name: bad}))

    def test_detachment_and_supplied_pin_mutation_after_decoding(self):
        """Fresh provenance/references/content isolate all earlier reports from later bypass mutation."""
        envelope = self.envelope
        self.assertIsNot(envelope.provenance, self.creator)
        self.assertIsNot(envelope.record_references[1], envelope.record_references[3])
        decoded = decode_envelope(envelope)
        object.__setattr__(self.creator, "actor", "other")
        self.assertEqual(envelope.provenance.actor, "archivist")
        object.__setattr__(envelope.record_references[0], "revision", 99)
        object.__setattr__(envelope.artifact_references[0], "size", 999)
        object.__setattr__(envelope.provenance, "actor", "changed")
        self.assertEqual(decoded, self.content)
        self.assertEqual(decoded.to_dict(), wire())
        with self.assertRaises(Invalid):
            decode_envelope(envelope)

    def test_coherent_detached_forgery_is_local_data_not_authentication(self):
        """A consistent forged canonical report can round-trip without proving any reporter identity."""
        value = wire()
        value["attribution"]["actor"] = known("Alleged authority")
        content = forged(self.content, _json=canonical(value))
        envelope = encode_envelope("assessment", 1, content, self.creator)
        self.assertEqual(decode_envelope(envelope).to_dict(), value)
        self.assertIsNone(envelope.operational_status)
        self.assertIsNone(envelope.scientific_disposition)

    def test_no_nested_serializers_or_discarded_envelope_on_decode(self):
        """Only raw fixed attributes are consumed; decoding never creates an unnecessary envelope."""
        for value in (self.envelope, self.creator, self.content, *self.envelope.record_references, *self.envelope.artifact_references):
            object.__setattr__(value, "to_dict", trap)
        with patch.object(CreationProvenance, "to_dict", trap), patch.object(RecordReference, "to_dict", trap), patch.object(ArtifactReference, "to_dict", trap):
            self.assertEqual(decode_envelope(self.envelope), self.content)
            encode_envelope("assessment", 1, self.content, self.creator)
        with patch.object(RecordEnvelope, "__init__", side_effect=trap):
            self.assertEqual(decode_envelope(self.envelope), self.content)

    def test_passive_envelopes_and_programmer_assertions_remain_visible(self):
        """After imports, no host/store/process access occurs and unexpected assertions propagate."""
        import research_pipeline.store
        targets = ("builtins.open", "os.getenv", "os.getcwd", "os.stat", "time.time",
                   "socket.socket", "subprocess.Popen", "sqlite3.connect", "research_pipeline.store.RecordStore.__init__")
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, trap))
            envelope = encode_envelope("assessment", 1, self.content, self.creator)
            self.assertEqual(decode_envelope(envelope), self.content)
        with patch.object(CreationProvenance, "__init__", side_effect=trap):
            with self.assertRaises(AssertionError):
                decode_envelope(self.envelope)

    def test_metadata_scalar_aliases_and_missing_supplied_reference_fields(self):
        """Exact raw metadata types reject scalar/metaclass aliases without conversion hooks."""
        for meta in (EqualityMeta, HashMeta):
            text_type = meta("MetadataText", (str,), {"__doc__": "Untrusted text alias.", "__str__": trap})
            int_type = meta("MetadataInt", (int,), {"__doc__": "Untrusted integer alias.", "__int__": trap})
            for changes in ({"record_id": text_type("assessment")}, {"kind": text_type("tool_assessment")},
                            {"revision": int_type(1)}):
                with self.assertRaises(Invalid):
                    decode_envelope(forged(self.envelope, **changes))
            for field, value in (("actor", text_type("archivist")), ("created_at", text_type(self.creator.created_at)),
                                 ("_details_json", text_type("{}"))):
                with self.assertRaises(Invalid):
                    decode_envelope(forged(self.envelope, provenance=forged(self.creator, **{field: value})))
        for name in ("record_id", "revision", "relationship", "target_kind"):
            reference = forged(self.envelope.record_references[0])
            object.__delattr__(reference, name)
            with self.assertRaises(Invalid):
                decode_envelope(forged(self.envelope, record_references=(reference,)))
        for name in ("digest", "size"):
            reference = forged(self.envelope.artifact_references[0])
            object.__delattr__(reference, name)
            with self.assertRaises(Invalid):
                decode_envelope(forged(self.envelope, artifact_references=(reference,)))
