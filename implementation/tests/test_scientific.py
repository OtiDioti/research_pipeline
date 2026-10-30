"""Structural scientific contracts, strict codecs and exact ordered envelope coherence."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json
import unittest

from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope, RecordReference,
)
from research_pipeline.scientific import (
    Claim, Evidence, Justification, NamedAssumption, NotTypedContentError, ResearchContext,
    decode_content, decode_envelope, dumps_content, encode_envelope, loads_content,
)


FORMAT = "research_pipeline.scientific_content"
TEXT = "  ∀ x ∈ ℝ: 𝒜(x) ≥ ε\n  " + r"literal \u03b1"


def mutate_containers(value):
    """Change every nested dict/list in a returned or supplied tree to expose aliases."""
    if type(value) is dict:
        for child in list(value.values()):
            mutate_containers(child)
        value.clear()
    elif type(value) is list:
        for child in value:
            mutate_containers(child)
        value.append("mutation")


class ScientificTests(unittest.TestCase):
    """Exercise pure synthetic values without stores, target lookup or scientific execution."""

    def setUp(self):
        """Prepare all fields, multiple ordered roles and independent expected link tuples."""
        self.provenance = CreationProvenance("author", "2026-10-30T12:00:00Z", {"source": ["synthetic"]})
        self.context_ref = RecordReference("scope", 2, "context", "research_context")
        self.p1 = RecordReference("claim-A", 1, "premise", "claim")
        self.p2 = RecordReference("claim-B", 3, "premise", "claim")
        self.c1 = RecordReference("claim-A", 1, "conclusion", "claim")
        self.c2 = RecordReference("claim-C", 1, "conclusion", "claim")
        self.e1 = RecordReference("evidence-A", 1, "evidence", "evidence")
        self.e2 = RecordReference("evidence-B", 2, "evidence", "evidence")
        self.t1 = RecordReference("claim-A", 1, "target_claim", "claim")
        self.t2 = RecordReference("claim-B", 3, "target_claim", "claim")
        self.i1 = RecordReference("evidence-A", 1, "input_record", "evidence")
        self.i2 = RecordReference("task", 4, "input_record", None)
        self.a = ArtifactReference("a" * 64, 3)
        self.b = ArtifactReference("b" * 64, 7)
        self.assumption = NamedAssumption("A", TEXT)
        self.context = ResearchContext(
            TEXT, ["f(x) = x", TEXT], ["x denotes an element"], ["dimensionless"],
            ["ordered labels"], ["x ∈ ℝ"], ["boundary unspecified"], ["initial x = 0"],
            ["ε > 0", "N finite"], ["synthetic declaration"], ["N → ∞", "ε → 0"])
        self.claim = Claim(TEXT, "descriptive category", ["∀ x", "∀ x"], self.context_ref,
                           [self.assumption], ["ε small"], ["check scope"])
        self.route = Justification(self.context_ref, [self.p1, self.p2], [self.assumption],
                                   "declared route", [self.c1, self.c2], [self.e1, self.e2], ["not assessed"])
        self.evidence = Evidence([self.a, self.b], self.context_ref, TEXT, [self.t1, self.t2],
                                 "synthetic method", [self.i1, self.i2], [self.b, self.a],
                                 [TEXT], "declared observation", ["uncertainty unknown"], ["not executed"], "synthetic")
        self.values = (self.context, self.claim, self.route, self.evidence)
        self.expected_links = (
            ((), ()), ((self.context_ref,), ()),
            ((self.context_ref, self.p1, self.p2, self.c1, self.c2, self.e1, self.e2), ()),
            ((self.context_ref, self.t1, self.t2, self.i1, self.i2), (self.a, self.b, self.b, self.a)),
        )

    def envelope(self, value):
        """Encode a synthetic exact revision with explicit provenance for coherence cases."""
        return encode_envelope("evidence-A" if type(value) is Evidence else "record", 1, value, self.provenance)

    def test_complete_fields_and_round_trips(self):
        """Assert full documents and all public round trips, including canonical JSON bytes."""
        expected = (
            dict(question=TEXT, equations=["f(x) = x", TEXT], definitions=["x denotes an element"],
                 units=["dimensionless"], conventions=["ordered labels"], mathematical_domains=["x ∈ ℝ"],
                 boundary_conditions=["boundary unspecified"], initial_conditions=["initial x = 0"],
                 parameter_regime=["ε > 0", "N finite"], approximations=["synthetic declaration"],
                 limit_ordering=["N → ∞", "ε → 0"]),
            dict(statement=TEXT, category="descriptive category", quantifiers=["∀ x", "∀ x"],
                 context=self.context_ref.to_dict(), assumptions=[{"label": "A", "statement": TEXT}],
                 approximation_qualifications=["ε small"], open_obligations=["check scope"]),
            dict(context=self.context_ref.to_dict(), premises=[self.p1.to_dict(), self.p2.to_dict()],
                 required_assumptions=[{"label": "A", "statement": TEXT}], method="declared route",
                 conclusions=[self.c1.to_dict(), self.c2.to_dict()], evidence=[self.e1.to_dict(), self.e2.to_dict()],
                 limitations=["not assessed"]),
            dict(artifacts=[self.a.to_dict(), self.b.to_dict()], context=self.context_ref.to_dict(),
                 target_property=TEXT, target_claims=[self.t1.to_dict(), self.t2.to_dict()], method="synthetic method",
                 input_records=[self.i1.to_dict(), self.i2.to_dict()], input_artifacts=[self.b.to_dict(), self.a.to_dict()],
                 tested_scope=[TEXT], result="declared observation", uncertainty_details=["uncertainty unknown"],
                 failure_details=["not executed"], origin="synthetic"),
        )
        for value, payload, kind, links in zip(self.values, expected,
                ("research_context", "claim", "justification", "evidence"), self.expected_links):
            with self.subTest(kind=kind):
                document = dict(format=FORMAT, version=1, kind=kind, **payload)
                self.assertEqual(value.to_dict(), document)
                self.assertEqual(type(value).from_dict(document), value)
                self.assertEqual(decode_content(document), value)
                encoded = dumps_content(value)
                self.assertEqual(encoded, json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
                self.assertTrue(encoded.isascii())
                self.assertEqual(loads_content(encoded), value)
                self.assertEqual(loads_content(encoded.encode("utf-8")), value)
                envelope = self.envelope(value)
                self.assertEqual(envelope.record_references, links[0])
                self.assertEqual(envelope.artifact_references, links[1])
                self.assertEqual(envelope.content, document)
                self.assertEqual(envelope.provenance, self.provenance)
                self.assertEqual(envelope.record_id, "evidence-A" if kind == "evidence" else "record")
                self.assertEqual(envelope.revision, 1)
                self.assertEqual(envelope.kind, kind)
                self.assertIsNone(envelope.operational_status)
                self.assertEqual(envelope.scientific_disposition, "provisional" if kind == "claim" else None)
                self.assertEqual(decode_envelope(RecordEnvelope.from_dict(envelope.to_dict())), value)
                self.assertIsNot(decode_envelope(envelope), value)
        self.assertEqual(NamedAssumption.from_dict(self.assumption.to_dict()), self.assumption)

    def test_explicit_empties_and_required_constructor_arguments(self):
        """Empty declarations round-trip while every omitted constructor argument fails."""
        for value in self.values:
            changes = {field.name: [] for field in fields(value)
                       if type(getattr(value, field.name)) is tuple and field.name not in ("artifacts", "conclusions")}
            empty = replace(value, **changes)
            self.assertEqual(loads_content(dumps_content(empty)), empty)
            for name in changes:
                self.assertEqual(empty.to_dict()[name], [])
            arguments = {field.name: getattr(value, field.name) for field in fields(value)}
            for name in arguments:
                with self.subTest(kind=type(value).__name__, omitted=name), self.assertRaises(TypeError):
                    type(value)(**{key: item for key, item in arguments.items() if key != name})
        for value, name in ((self.route, "conclusions"), (self.evidence, "artifacts")):
            with self.assertRaisesRegex(DomainValidationError, name):
                replace(value, **{name: []})
        for name in ("label", "statement"):
            with self.assertRaises(TypeError):
                NamedAssumption(**{name: "A"})

    def test_scope_and_independent_alternatives_remain_distinct(self):
        """Preserve regimes, limit order, conjunctive premises and separate cyclic routes."""
        alternative_context = replace(self.context, parameter_regime=["ε = 0"], limit_ordering=["ε → 0", "N → ∞"])
        self.assertNotEqual(alternative_context, self.context)
        self.assertEqual(decode_envelope(self.envelope(alternative_context)), alternative_context)
        alternate = replace(self.route, premises=[RecordReference("other", 8, "premise", "claim")])
        self.assertNotEqual(alternate, self.route)
        for route in (self.route, alternate, replace(self.route, premises=[])):
            self.assertEqual(loads_content(dumps_content(route)), route)
        self.assertEqual(self.route.premises, (self.p1, self.p2))
        self.assertEqual((self.route.premises[0].record_id, self.route.premises[0].revision),
                         (self.route.conclusions[0].record_id, self.route.conclusions[0].revision))
        self.assertEqual(decode_envelope(self.envelope(self.evidence)).input_records[0].record_id, "evidence-A")

    def test_mutation_isolation_of_all_collections_and_returned_trees(self):
        """All caller lists and nested input/output containers are detached from frozen values."""
        for original in (*self.values, self.assumption):
            with self.subTest(kind=type(original).__name__):
                arguments = {field.name: list(getattr(original, field.name))
                             if type(getattr(original, field.name)) is tuple else getattr(original, field.name)
                             for field in fields(original)}
                value = type(original)(**arguments)
                for item in arguments.values():
                    if type(item) is list:
                        item.clear()
                self.assertEqual(value, original)
                source = original.to_dict()
                restored = type(original).from_dict(source)
                mutate_containers(source)
                self.assertEqual(restored, original)
                mutate_containers(restored.to_dict())
                self.assertEqual(restored.to_dict(), original.to_dict())
                if type(original) is not NamedAssumption:
                    envelope = self.envelope(original)
                    mutate_containers(envelope.to_dict())
                    mutate_containers(envelope.content)
                    self.assertEqual(decode_envelope(envelope), original)
        for value in (*self.values, self.assumption, self.context_ref, self.a):
            for field in fields(value):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field.name, None)

    def test_missing_extra_and_null_fields_at_every_schema(self):
        """Require every top-level and nested wire field, including nullable target_kind."""
        for original in (*self.values, self.assumption):
            for name in original.to_dict():
                data = original.to_dict()
                del data[name]
                with self.subTest(kind=type(original).__name__, missing=name), self.assertRaises(DomainValidationError):
                    type(original).from_dict(data)
                data = original.to_dict()
                data[name] = None
                with self.subTest(kind=type(original).__name__, null=name), self.assertRaises(DomainValidationError):
                    type(original).from_dict(data)
            data = original.to_dict()
            data["extra"] = "unrecognized"
            with self.assertRaisesRegex(DomainValidationError, "unknown"):
                type(original).from_dict(data)
        for field, index in (("context", None), ("artifacts", 0), ("input_records", 1), ("input_artifacts", 0)):
            source = self.evidence.to_dict()
            nested = source[field] if index is None else source[field][index]
            for name in (*nested, "extra"):
                data = deepcopy(source)
                target = data[field] if index is None else data[field][index]
                if name == "extra":
                    target[name] = 1
                else:
                    del target[name]
                with self.subTest(role=field, field=name), self.assertRaisesRegex(DomainValidationError, field):
                    decode_content(data)
        for role, original in (("assumptions", self.claim), ("required_assumptions", self.route)):
            for name in ("label", "statement", "extra"):
                data = original.to_dict()
                if name == "extra":
                    data[role][0][name] = 1
                else:
                    del data[role][0][name]
                with self.assertRaisesRegex(DomainValidationError, role):
                    decode_content(data)

    def test_text_types_unicode_and_nonblank_requirements(self):
        """Reject coercions, blank statements and surrogates in every scientific text field."""
        for value in (*self.values, self.assumption):
            for field in fields(value):
                item = getattr(value, field.name)
                is_texts = type(item) is tuple and item and type(item[0]) is str
                if type(item) is not str and not is_texts:
                    continue
                for bad in (None, True, 1, 1.5, [], {}, "", " \n\t", "x\ud800", "\ud83d\ude00"):
                    with self.subTest(kind=type(value).__name__, field=field.name, bad=repr(bad)):
                        with self.assertRaises(DomainValidationError):
                            replace(value, **{field.name: [bad] if is_texts else bad})
        self.assertEqual(loads_content(dumps_content(self.context)).question, TEXT)
        data = self.context.to_dict()
        data["question"] = "😀"
        self.assertEqual(loads_content(json.dumps(data)).question, "😀")
        self.assertEqual(replace(self.claim, assumptions=[NamedAssumption("a", TEXT), self.assumption]).assumptions[0].label, "a")

    def test_collection_types_and_members(self):
        """Only ordinary lists/tuples construct collections; wire arrays must be JSON lists."""
        for value in self.values:
            for field in fields(value):
                items = getattr(value, field.name)
                if type(items) is not tuple:
                    continue
                for bad in (None, "text", {}, {"item"}, iter(items), 1, True):
                    with self.subTest(field=field.name, bad=type(bad).__name__), self.assertRaisesRegex(DomainValidationError, field.name):
                        replace(value, **{field.name: bad})
                for bad in (None, {}, True, "wrong" if type(items[0]) is not str else 3):
                    with self.assertRaisesRegex(DomainValidationError, field.name):
                        replace(value, **{field.name: [bad]})
                for bad in (tuple(value.to_dict()[field.name]), {}, None, "array"):
                    data = value.to_dict()
                    data[field.name] = bad
                    with self.assertRaises(DomainValidationError):
                        type(value).from_dict(data)
        for bad in ({}, None, "context"):
            for value in (self.claim, self.route, self.evidence):
                with self.assertRaisesRegex(DomainValidationError, "context"):
                    replace(value, context=bad)

    def test_local_labels_and_duplicate_role_targets(self):
        """Reject repeated local labels/targets while preserving revisions and cross-role uses."""
        for value, name in ((self.claim, "assumptions"), (self.route, "required_assumptions")):
            with self.assertRaisesRegex(DomainValidationError, "label"):
                replace(value, **{name: [self.assumption, NamedAssumption("A", "different")]})
        for bad in ("", "../A", " A", "A ", "é", "a/b", "_a", "a" * 129, None, True):
            with self.assertRaisesRegex(DomainValidationError, "label"):
                NamedAssumption(bad, "statement")
        for value, role in ((self.route, "premises"), (self.route, "conclusions"), (self.route, "evidence"),
                            (self.evidence, "target_claims"), (self.evidence, "input_records")):
            item = getattr(value, role)[0]
            with self.subTest(role=role), self.assertRaisesRegex(DomainValidationError, role):
                replace(value, **{role: [item, item]})
            changed = replace(item, revision=item.revision + 1)
            valid = replace(value, **{role: [item, changed]})
            self.assertEqual(decode_envelope(self.envelope(valid)), valid)
        with self.assertRaisesRegex(DomainValidationError, "input_records"):
            replace(self.evidence, input_records=[self.i1, replace(self.i1, target_kind=None)])

    def test_record_roles_expected_kinds_and_nested_scalar_validation(self):
        """Every semantic role validates exact labels, constrained kinds, IDs and revisions."""
        cases = [(value, "context", None) for value in (self.claim, self.route, self.evidence)]
        cases += [(self.route, name, 0) for name in ("premises", "conclusions", "evidence")]
        cases += [(self.evidence, name, 0) for name in ("target_claims", "input_records")]
        for value, role, index in cases:
            for field, invalids in (
                ("record_id", ("a/b", "_a", "a ", "é", "a" * 129, 1, None)),
                ("revision", (0, -1, True, 1.0, "1", None, 2**63)),
                ("relationship", ("wrong_role", None, 3, "")),
                ("target_kind", ("unsupported", [], 1, True))):
                for bad in invalids:
                    data = value.to_dict()
                    target = data[role] if index is None else data[role][index]
                    target[field] = bad
                    with self.subTest(role=role, field=field, bad=bad), self.assertRaisesRegex(DomainValidationError, role):
                        decode_content(data)
            if role != "input_records":
                for bad in (None, "task_specification"):
                    data = value.to_dict()
                    target = data[role] if index is None else data[role][index]
                    target["target_kind"] = bad
                    with self.assertRaisesRegex(DomainValidationError, role):
                        decode_content(data)
        for kind in (None, "research_context", "claim", "justification", "evidence", "task_specification"):
            valid = replace(self.evidence, input_records=[replace(self.i1, target_kind=kind)])
            self.assertEqual(loads_content(dumps_content(valid)), valid)

    def test_artifact_roles_duplicates_and_sizes(self):
        """Artifact boundaries retain cross-role duplicates and reject ambiguous byte sizes."""
        self.assertEqual(self.envelope(self.evidence).artifact_references, (self.a, self.b, self.b, self.a))
        for role in ("artifacts", "input_artifacts"):
            for second in (self.a, replace(self.a, size=4)):
                with self.assertRaisesRegex(DomainValidationError, role):
                    replace(self.evidence, **{role: [self.a, second]})
            for field, values in (("digest", ("A" * 64, "../x", "a" * 63, None, 1)),
                                  ("size", (None, True, 1.0, "3", -1, 2**63))):
                for bad in values:
                    data = self.evidence.to_dict()
                    data[role][0][field] = bad
                    with self.assertRaisesRegex(DomainValidationError, role):
                        decode_content(data)
        with self.assertRaisesRegex(DomainValidationError, "conflicting size"):
            replace(self.evidence, input_artifacts=[replace(self.a, size=4)])
        valid = replace(self.evidence, artifacts=[ArtifactReference("c" * 64, 0)], input_artifacts=[])
        self.assertEqual(decode_envelope(self.envelope(valid)), valid)

    def test_discriminator_version_kind_and_generic_boundary(self):
        """Legacy or unsupported documents remain generic without gaining typed validity."""
        for value in self.values:
            for field, invalids in (("format", ("other", "", 1, True, [], None)),
                                    ("version", (0, 2, -1, True, 1.0, "1", None)),
                                    ("kind", ("task_specification", "unknown", "Claim", [], True, None))):
                for bad in invalids:
                    data = value.to_dict()
                    data[field] = bad
                    with self.assertRaisesRegex(DomainValidationError, field) as caught:
                        decode_content(data)
                    self.assertNotIsInstance(caught.exception, NotTypedContentError)
            data = value.to_dict()
            del data["format"]
            with self.assertRaises(NotTypedContentError):
                decode_content(data)
        for content in ({"statement": "legacy"}, dict(self.claim.to_dict(), version=2),
                        dict(self.claim.to_dict(), format="future.format")):
            envelope = RecordEnvelope("legacy", 1, "claim", content, self.provenance,
                                      [self.context_ref, self.context_ref], scientific_disposition="provisional")
            self.assertEqual(RecordEnvelope.from_dict(envelope.to_dict()), envelope)
            self.assertEqual(envelope.record_references, (self.context_ref, self.context_ref))
            with self.assertRaises(DomainValidationError):
                decode_envelope(envelope)
        for value in self.values:
            for other in self.values:
                if type(value) is not type(other):
                    with self.assertRaises(DomainValidationError):
                        type(value).from_dict(other.to_dict())

    def test_strict_json_syntax_encodings_duplicates_and_depth(self):
        """Reject malformed JSON, alternative encodings, duplicates, nonfinite and deep input."""
        valid = dumps_content(self.claim)
        invalid = ("{", valid + " {}", "[]", "null", "true", "42", '"text"',
                   valid[:-1] + ',"version":1}', valid.replace('"revision":2', '"revision":2,"revision":2'),
                   valid.replace('"label":"A"', '"label":"A","label":"A"'),
                   valid.replace('"version":1', '"version":NaN'),
                   valid.replace('"version":1', '"version":Infinity'),
                   valid.replace('"version":1', '"version":-Infinity'),
                   valid.replace('"version":1', '"version":1e9999'),
                   valid.replace('"category":"descriptive category"', '"category":"\\ud800"'),
                   valid.replace('"category":"descriptive category"', '"category":"\ud800"'),
                   '{"nested":' + '[' * 1200 + '0' + ']' * 1200 + '}',
                   b"\xff", valid.encode("utf-16"), valid.encode("utf-32"), b"\xed\xa0\x80")
        for data in invalid:
            with self.subTest(data=repr(data)[:90]), self.assertRaises(DomainValidationError):
                loads_content(data)
        with self.assertRaises(DomainValidationError) as caught:
            loads_content(b"\xff")
        self.assertIsInstance(caught.exception.__cause__, UnicodeError)
        with self.assertRaises(DomainValidationError) as caught:
            loads_content("{")
        self.assertIsInstance(caught.exception.__cause__, json.JSONDecodeError)
        with self.assertRaisesRegex(DomainValidationError, "duplicate JSON key"):
            loads_content(valid.replace('"label":"A"', '"label":"A","label":"B"'))

    def test_python_trees_cycles_depth_and_unsupported_types(self):
        """Direct decoders validate entire trees before field reconstruction without coercion."""
        cycle = []
        cycle.append(cycle)
        mapping = {}
        mapping["self"] = mapping
        deep = {}
        for _ in range(1200):
            deep = {"child": deep}
        for bad in ((), set(), b"bytes", object(), {1: "key"}, {"\ud800": 1},
                    float("nan"), float("inf"), cycle, mapping, deep):
            for value in (*self.values, self.assumption):
                data = value.to_dict()
                data["extra"] = bad
                with self.subTest(kind=type(value).__name__, bad=type(bad).__name__), self.assertRaises(DomainValidationError):
                    type(value).from_dict(data)
        for bad in (None, [], True, "{}", 1):
            with self.assertRaises(DomainValidationError):
                decode_content(bad)
            for value in (*self.values, self.assumption):
                with self.assertRaises(DomainValidationError):
                    type(value).from_dict(bad)
        for bad in (None, {}, [], bytearray(b"{}"), 1):
            with self.assertRaises(DomainValidationError):
                loads_content(bad)
            with self.assertRaises(DomainValidationError):
                dumps_content(bad)
            with self.assertRaises(DomainValidationError):
                encode_envelope("id", 1, bad, self.provenance)
            with self.assertRaises(DomainValidationError):
                decode_envelope(bad)

    def test_exact_envelope_link_tampering_for_every_kind(self):
        """Reject missing, extra, substituted, repeated, relabeled or reordered stored links."""
        for value in self.values:
            original = self.envelope(value).to_dict()
            records = original["record_references"]
            variants = [records + [self.context_ref.to_dict()]]
            if records:
                variants.extend([records[1:], records + [records[0]],
                                 [dict(records[0], record_id="substitute"), *records[1:]],
                                 [dict(records[0], revision=99), *records[1:]],
                                 [dict(records[0], relationship="wrong"), *records[1:]],
                                 [dict(records[0], target_kind=None), *records[1:]]])
            if len(records) > 1:
                variants.extend([list(reversed(records)), [records[0], *reversed(records[1:])]])
            for changed in variants:
                data = dict(original, record_references=changed)
                with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(DomainValidationError, "record_references"):
                    decode_envelope(RecordEnvelope.from_dict(data))
            artifacts = original["artifact_references"]
            changes = [artifacts + [self.a.to_dict()]]
            if artifacts:
                changes.extend([artifacts[1:], [dict(artifacts[0], digest="c" * 64), *artifacts[1:]],
                                [dict(artifacts[0], size=99), *artifacts[1:]],
                                [artifacts[1], artifacts[0], *artifacts[2:]]])
            for changed in changes:
                with self.assertRaisesRegex(DomainValidationError, "artifact_references"):
                    decode_envelope(RecordEnvelope.from_dict(dict(original, artifact_references=changed)))
            other = self.evidence if type(value) is ResearchContext else self.context
            data = dict(original, content=other.to_dict())
            with self.assertRaisesRegex(DomainValidationError, "kind"):
                decode_envelope(RecordEnvelope.from_dict(data))

    def test_content_only_tampering_and_revalidation(self):
        """Changing content roles alone cannot silently rebuild links or discard generic state."""
        for value in (self.claim, self.route, self.evidence):
            data = self.envelope(value).to_dict()
            data["content"]["context"]["revision"] += 1
            with self.assertRaisesRegex(DomainValidationError, "record_references"):
                decode_envelope(RecordEnvelope.from_dict(data))
        data = self.envelope(self.evidence).to_dict()
        data["content"]["input_artifacts"].reverse()
        with self.assertRaisesRegex(DomainValidationError, "artifact_references"):
            decode_envelope(RecordEnvelope.from_dict(data))
        for value, attribute, bad in ((self.claim, "scientific_disposition", "supported"),
                                      (self.context, "operational_status", "completed")):
            envelope = self.envelope(value)
            object.__setattr__(envelope, attribute, bad)
            with self.assertRaisesRegex(DomainValidationError, attribute):
                decode_envelope(envelope)
        for field, bad in (("record_id", "../id"), ("revision", True), ("provenance", {})):
            arguments = dict(record_id="id", revision=1, content=self.claim, provenance=self.provenance)
            arguments[field] = bad
            with self.assertRaises(DomainValidationError):
                encode_envelope(**arguments)

    def test_narrative_authority_and_task_completion_remain_separate(self):
        """Approval/execution prose confers neither supported claims nor authenticated origin."""
        narrative = "Execution complete; approved, endorsed and supported (a narrative assertion)."
        claim = replace(self.claim, statement=narrative, category="approved")
        evidence = replace(self.evidence, method=narrative, result=narrative, origin="unverified")
        self.assertEqual(self.envelope(claim).scientific_disposition, "provisional")
        self.assertEqual(decode_envelope(self.envelope(evidence)).origin, "unverified")
        task = RecordEnvelope("task", 1, "task_specification", {"result": narrative}, self.provenance,
                              operational_status="completed")
        self.assertEqual(RecordEnvelope.from_dict(task.to_dict()).operational_status, "completed")
        self.assertIsNone(task.scientific_disposition)
        with self.assertRaises(NotTypedContentError):
            decode_envelope(task)
        for bad in ("authentic", "executed", "verified", "Synthetic", "", None, True):
            with self.assertRaisesRegex(DomainValidationError, "origin"):
                replace(evidence, origin=bad)
