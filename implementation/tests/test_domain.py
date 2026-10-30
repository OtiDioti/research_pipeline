"""Behavioral tests for domain-independent immutable envelope values."""

from dataclasses import FrozenInstanceError
import json
import unittest

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope, RecordReference,
)


class DomainTests(unittest.TestCase):
    """Exercise validation, detached serialization, exact links and independent states."""

    def setUp(self):
        """Prepare attributed synthetic graph research without fixture-specific schemas."""
        self.provenance = CreationProvenance("graph-author", "2026-10-30T12:34:56Z", {"source": ["synthetic"]})

    def envelope(self, **changes):
        """Construct a graph context with selected field overrides for behavioral cases."""
        fields = dict(record_id="Graph_A", revision=1, kind="research_context",
                      content={"vertices": ["a", "b"], "edges": [["a", "b"]]}, provenance=self.provenance)
        fields.update(changes)
        return RecordEnvelope(**fields)

    def test_all_kinds_and_exact_references_round_trip(self):
        """Round-trip five kinds and exact ordered relationships through actual JSON."""
        references = [RecordReference("Graph_A", 2, "Uses-context", "research_context"),
                      RecordReference("Graph_A", 1, "compares_with")]
        artifact = ArtifactReference("a" * 64, 2**63 - 1)
        for kind in ("research_context", "claim", "justification", "evidence", "task_specification"):
            with self.subTest(kind=kind):
                record = self.envelope(kind=kind, record_references=references,
                                       artifact_references=[artifact],
                                       scientific_disposition="provisional" if kind == "claim" else None,
                                       operational_status="completed" if kind == "task_specification" else None)
                restored = RecordEnvelope.from_dict(json.loads(json.dumps(record.to_dict())))
                self.assertEqual(restored, record)
                self.assertEqual(restored.record_references, tuple(references))
                self.assertEqual(restored.record_references[0].revision, 2)
                self.assertEqual(restored.record_references[0].relationship, "Uses-context")
        for value in (self.provenance, *references, artifact):
            self.assertEqual(type(value).from_dict(value.to_dict()), value)
        self.assertEqual(self.envelope(content={}).content, {})
        self.assertEqual(self.envelope(revision=2**63 - 1).revision, 2**63 - 1)

    def test_nested_mutation_isolation_and_frozen_attributes(self):
        """Isolate caller trees, returned trees and constructor reference lists."""
        details = {"notes": [{"quoted": "supported"}]}
        provenance = CreationProvenance("actor", "2026-10-30T00:00:00.1Z", details)
        content = {"graph": {"vertices": [1, 2]}}
        references = [RecordReference("context", 1, "uses")]
        artifacts = [ArtifactReference("b" * 64, 0)]
        record = self.envelope(content=content, provenance=provenance,
                               record_references=references, artifact_references=artifacts)
        original = record.to_dict()
        content["graph"]["vertices"].append(3)
        details["notes"][0]["quoted"] = "changed"
        references.clear()
        artifacts.clear()
        record.content["graph"]["vertices"].clear()
        provenance.details["notes"].clear()
        returned = record.to_dict()
        returned["content"]["graph"]["vertices"].append(4)
        returned["provenance"]["details"]["notes"][0].clear()
        returned["record_references"][0]["revision"] = 3
        returned["artifact_references"][0]["size"] = 10
        self.assertEqual(record.to_dict(), original)
        self.assertEqual(RecordEnvelope.from_dict(original), record)
        for value, attribute in ((record, "revision"), (provenance, "actor"),
                                 (record.record_references[0], "revision"),
                                 (record.artifact_references[0], "size")):
            with self.subTest(attribute=attribute), self.assertRaises(FrozenInstanceError):
                setattr(value, attribute, "changed")

    def test_canonical_mappings_preserve_lists_and_scalar_types(self):
        """Mapping order is irrelevant, while list order and JSON scalar types matter."""
        self.assertEqual(self.envelope(content={"z": {"b": 2, "a": 1}, "a": []}),
                         self.envelope(content={"a": [], "z": {"a": 1, "b": 2}}))
        self.assertEqual(CreationProvenance("a", "2026-01-01T00:00:00Z", {"b": 2, "a": 1}),
                         CreationProvenance("a", "2026-01-01T00:00:00.000000Z", {"a": 1, "b": 2}))
        self.assertNotEqual(self.envelope(content={"v": [1, 2]}), self.envelope(content={"v": [2, 1]}))
        for first, second in ((1, 1.0), (1, True), (1.0, True)):
            self.assertNotEqual(self.envelope(content={"v": first}), self.envelope(content={"v": second}))
        ref = RecordReference("target", 1, "uses")
        duplicated = self.envelope(record_references=[ref, ref])
        self.assertEqual(duplicated.record_references, (ref, ref))

    def test_descriptive_assertions_never_promote_claims(self):
        """Completed work and quoted support remain separate from canonical disposition."""
        claim = self.envelope(kind="claim", scientific_disposition="provisional",
                              content={"statement": "The graph is connected", "status": "supported",
                                       "endorsement": {"scientific_disposition": "endorsed"}})
        for state in ("proposed", "ready", "blocked", "active", "completed", "cancelled", "abandoned"):
            task = self.envelope(kind="task_specification", operational_status=state,
                                 record_references=[RecordReference(claim.record_id, 1, "investigates", "claim")])
            self.assertIsNone(task.scientific_disposition)
            self.assertEqual(claim.scientific_disposition, "provisional")
        for disposition in (None, "supported", "endorsed", "supported_within_scope", "", [], True):
            with self.subTest(disposition=disposition), self.assertRaises(DomainValidationError):
                self.envelope(kind="claim", scientific_disposition=disposition)
        for fields in (dict(kind="task_specification"),
                       dict(kind="task_specification", operational_status="succeeded"),
                       dict(kind="task_specification", operational_status="completed", scientific_disposition="provisional"),
                       dict(kind="claim", scientific_disposition="provisional", operational_status="completed"),
                       dict(operational_status="ready"), dict(scientific_disposition="provisional")):
            with self.subTest(fields=fields), self.assertRaises(DomainValidationError):
                self.envelope(**fields)

    def test_identity_kind_and_integer_boundaries(self):
        """Reject coercion and malformed opaque identifiers across their public uses."""
        for value in ("", "../x", "a/b", "_x", " x", "x ", "é", "x" * 129, 3, None, True):
            with self.subTest(value=value):
                for construct in (lambda: self.envelope(record_id=value),
                                  lambda: CreationProvenance(value, "2026-01-01T00:00:00Z"),
                                  lambda: RecordReference("a", 1, value)):
                    with self.assertRaises(DomainValidationError):
                        construct()
        self.assertNotEqual(self.envelope(record_id="A"), self.envelope(record_id="a"))
        self.assertEqual(self.envelope(record_id="A" * 128).record_id, "A" * 128)
        for value in (0, -1, True, 1.0, "1", None, 2**63):
            with self.subTest(revision=value), self.assertRaises(DomainValidationError):
                RecordReference("a", value, "uses")
            with self.assertRaises(DomainValidationError):
                self.envelope(revision=value)
        for value in ("Claim", "project", "", None, [], True):
            with self.subTest(kind=value), self.assertRaises(DomainValidationError):
                self.envelope(kind=value)
            if value is not None:
                with self.assertRaises(DomainValidationError):
                    RecordReference("a", 1, "uses", value)
        for value in (-1, True, 1.0, "0", None, 2**63):
            with self.subTest(size=value), self.assertRaises(DomainValidationError):
                ArtifactReference("a" * 64, value)
        for digest in ("../outside", "A" * 64, "g" * 64, "a" * 63, "a" * 65, "a" * 63 + "\n", None, 3):
            with self.subTest(digest=digest), self.assertRaises(DomainValidationError):
                ArtifactReference(digest, 0)

    def test_timestamps_are_explicit_valid_utc_and_normalized(self):
        """Accept the documented UTC subset and reject impossible or implicit times."""
        for source, normalized in (("2024-02-29T12:30:00Z", "2024-02-29T12:30:00.000000Z"),
                                   ("0001-01-01T00:00:00.12Z", "0001-01-01T00:00:00.120000Z")):
            self.assertEqual(CreationProvenance("a", source).created_at, normalized)
        for value in (None, "2026-02-29T00:00:00Z", "2026-01-01T24:00:00Z",
                      "2026-01-01T00:00:60Z", "2026-01-01T00:00:00+00:00",
                      "2026-01-01 00:00:00Z", "2026-01-01T00:00:00.1234567Z", "now", ""):
            with self.subTest(value=value), self.assertRaisesRegex(DomainValidationError, "created_at"):
                CreationProvenance("a", value)

    def test_strict_json_and_depth_diagnostics(self):
        """Reject unsupported nested values, cycles and serialization limits in both snapshots."""
        cyclic = []
        cyclic.append(cyclic)
        mapping = {}
        mapping["self"] = mapping
        deep = {}
        for _ in range(1100):
            deep = {"child": deep}
        bad_values = [(), set(), b"bytes", object(), {1: "key"}, float("nan"), float("inf"),
                      float("-inf"), cyclic, mapping, deep]
        for value in bad_values:
            with self.subTest(type=type(value).__name__):
                with self.assertRaisesRegex(DomainValidationError, "content"):
                    self.envelope(content={"nested": [value]})
                with self.assertRaisesRegex(DomainValidationError, "details"):
                    CreationProvenance("a", "2026-01-01T00:00:00Z", {"nested": [value]})
        for value in ([], "{}", None):
            with self.assertRaises(DomainValidationError):
                self.envelope(content=value)
        allowed = {"v": [None, False, True, -3, 2.5, "unicode é"]}
        self.assertEqual(self.envelope(content=allowed).content, allowed)

    def test_surrogate_keys_and_values_are_rejected_before_snapshotting(self):
        """Reject colliding keys and all surrogate strings through each snapshot entry point."""
        scalar = chr(0x1F600)
        pair = chr(0xD83D) + chr(0xDE00)
        cases = [("collision", {scalar: 1, pair: 2}, True)]
        for name, text in (("pair", pair), ("high", chr(0xD800)), ("low", chr(0xDFFF))):
            cases.extend([(name + "_key", {text: 1}, True),
                          (name + "_value", {"text": text}, False)])
        for name, invalid, key_violation in cases:
            for nested in (False, True):
                payload = {"nested": [invalid]} if nested else invalid
                content_data = self.envelope().to_dict()
                content_data["content"] = payload
                provenance_data = self.provenance.to_dict()
                provenance_data["details"] = payload
                envelope_data = self.envelope().to_dict()
                envelope_data["provenance"] = provenance_data
                constructors = (
                    ("content", "constructor", lambda: self.envelope(content=payload)),
                    ("content", "from_dict", lambda: RecordEnvelope.from_dict(content_data)),
                    ("details", "constructor", lambda: CreationProvenance(
                        self.provenance.actor, self.provenance.created_at, payload)),
                    ("details", "from_dict", lambda: CreationProvenance.from_dict(provenance_data)),
                    ("details", "envelope_from_dict", lambda: RecordEnvelope.from_dict(envelope_data)),
                )
                for field, route, construct in constructors:
                    with self.subTest(case=name, nested=nested, field=field, route=route):
                        with self.assertRaises(DomainValidationError) as caught:
                            construct()
                        path = field + ("['nested'][0]" if nested else "")
                        path += " key " if key_violation else "['text']"
                        self.assertIn(path, str(caught.exception))
                        self.assertIn("Unicode scalar", str(caught.exception))

    def test_supplementary_unicode_and_literal_escapes_round_trip(self):
        """Preserve all fields and Unicode strings through detached trees and actual JSON."""
        scalar = chr(0x1F600)
        literal = r"\ud83d\ude00"
        payload = {scalar: 1, literal: 2, "nested": [{scalar: ["é", scalar, literal]}],
                   "other": {"count": 3, "unchanged": True}}
        self.assertEqual(json.loads(r'"\ud83d\ude00"'), scalar)
        provenance = CreationProvenance(self.provenance.actor, self.provenance.created_at, payload)
        record = self.envelope(content=payload, provenance=provenance)
        for value, field in ((provenance, "details"), (record, "content")):
            with self.subTest(field=field):
                self.assertEqual(getattr(value, field), payload)
                self.assertEqual(value.to_dict()[field], payload)
                self.assertEqual(type(value).from_dict(value.to_dict()), value)
                decoded = json.loads(json.dumps(value.to_dict()))
                self.assertEqual(decoded[field], payload)
                restored = type(value).from_dict(decoded)
                self.assertEqual(restored, value)
                self.assertEqual(getattr(restored, field), payload)
        self.assertEqual(RecordEnvelope.from_dict(record.to_dict()).provenance.details, payload)

    def test_serialized_fields_and_nested_reference_validation(self):
        """Reject unknown/missing fields and malformed nested serialization without dropping data."""
        for value in (self.provenance, RecordReference("a", 1, "uses"), ArtifactReference("a" * 64, 0), self.envelope()):
            with self.subTest(type=type(value).__name__):
                data = value.to_dict()
                data["unknown"] = 1
                with self.assertRaisesRegex(DomainValidationError, "unknown"):
                    type(value).from_dict(data)
                with self.assertRaisesRegex(DomainValidationError, "missing"):
                    type(value).from_dict({})
        for field, value in (("provenance", {}), ("provenance", self.provenance),
                             ("record_references", [{}]), ("record_references", [None]),
                             ("record_references", ()), ("artifact_references", [{"digest": "a" * 64, "size": 0, "path": "/tmp"}])):
            data = self.envelope().to_dict()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(DomainValidationError):
                RecordEnvelope.from_dict(data)
        for field, value in (("provenance", {}), ("record_references", [{}]),
                             ("artifact_references", [None]), ("record_references", "target")):
            with self.subTest(field=field), self.assertRaises(DomainValidationError):
                self.envelope(**{field: value})
