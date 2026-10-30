"""Pure attributed contracts: strict syntax, detached declarations and exact envelope links."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json
import unittest

from research_pipeline import scientific
from research_pipeline.assessment import (
    IndependenceDeclaration, SubstantiveAssessment, SupportRouteAssessment, Review, Issue,
    decode_content, decode_envelope, dumps_content, loads_content, encode_envelope,
)
from research_pipeline.domain import (
    ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope, RecordReference,
)
from research_pipeline.scientific import NotTypedContentError
from tests.test_scientific import mutate_containers


FORMAT = "research_pipeline.assessment_content"
TEXT = "  ∀ x ∈ ℝ: 𝒜(x) ≥ ε\n  " + r"literal \u03b1"
MODES = ("answer_blind_reconstruction", "proof_blind_reconstruction", "candidate_aware_audit")


def forge(value, name, replacement):
    """Produce an independently forged frozen value to exercise defensive boundaries."""
    result = deepcopy(value)
    object.__setattr__(result, name, replacement)
    return result


class SerializedLookalike:
    """Mimic only serialization to detect class checks lost at dictionary boundaries."""

    def __init__(self, document):
        """Retain a valid wire document without implementing its required domain class."""
        self.document = deepcopy(document)

    def to_dict(self):
        """Return valid-looking data that must not substitute for an exact typed value."""
        return deepcopy(self.document)


class AssessmentTests(unittest.TestCase):
    """Exercise synthetic declarations without a store, target records or artifact bytes."""

    def setUp(self):
        """Prepare complete ordered values, explicit documents and independently expected links."""
        self.provenance = CreationProvenance("author", "2026-10-30T12:00:00Z", {"source": ["synthetic"]})
        self.candidate = RecordReference("candidate", 2, "candidate_claim", "claim")
        self.context = RecordReference("different-context", 3, "target_context", "research_context")
        self.manifest = RecordReference("manifest", 1, "context_manifest", "work_product_manifest")
        self.policy = RecordReference("policy", 4, "authorization_policy", "decision")
        self.check1 = RecordReference("check", 1, "reported_evidence", "evidence")
        self.check2 = RecordReference("tool", 2, "reported_tool_execution", "tool_execution")
        self.route1 = RecordReference("route", 1, "assessed_route", "justification")
        self.route2 = RecordReference("route", 2, "assessed_route", "justification")
        self.affected = RecordReference("check", 1, "affected_record", "evidence")
        self.affected2 = RecordReference("review", 1, "affected_record", "review")
        self.support = RecordReference("check", 1, "supporting_evidence", "evidence")
        self.support2 = RecordReference("check", 2, "supporting_evidence", "evidence")
        self.a, self.b = ArtifactReference("a" * 64, 1), ArtifactReference("b" * 64, 2)
        self.independence = IndependenceDeclaration(MODES[0], MODES[2], [TEXT, TEXT], ["sources"],
            ["lemmas"], ["method"], ["implementation"], ["communications"], ["not verified"])
        self.assessment = SubstantiveAssessment("under_review", "supported_within_scope",
            ["numerical", "analytical"], "requires_reassessment", "unassessed", TEXT,
            [TEXT], ["existence obligation"], ["conditional"])
        self.route = SupportRouteAssessment(self.route1, "sufficient", TEXT, ["premises remain"], ["reported"])
        self.other_route = SupportRouteAssessment(self.route2, "invalid", "invalid support", [], [])
        self.review = Review(self.candidate, self.context, "Descriptive reviewer name", self.independence,
            self.manifest, self.policy, [self.check2, self.check1], self.assessment,
            [self.route, self.other_route], ["open"], [TEXT], [self.a, self.b], "synthetic")
        self.issue = Issue(TEXT, [self.affected, self.affected2], "synthetic objection", "blocking",
            "compare declarations", "open", TEXT, ["unverified"], [self.support, self.support2],
            [self.b, self.a], "unverified")
        self.values = (self.independence, self.assessment, self.route, self.review, self.issue)
        self.documents = (
            dict(requested_mode=MODES[0], reported_mode=MODES[2], shared_formulation=[TEXT, TEXT],
                 shared_sources=["sources"], shared_lemmas=["lemmas"], shared_method=["method"],
                 shared_implementation=["implementation"], shared_communications=["communications"],
                 limitations=["not verified"]),
            dict(work_stage="under_review", scientific_disposition="supported_within_scope",
                 support_types=["numerical", "analytical"], applicability="requires_reassessment",
                 novelty="unassessed", rationale=TEXT, conditions=[TEXT], obligations=["existence obligation"],
                 limitations=["conditional"]),
            dict(justification=self.route1.to_dict(), outcome="sufficient", rationale=TEXT,
                 outstanding_conditions=["premises remain"], limitations=["reported"]),
        )
        self.review_document = dict(format=FORMAT, version=1, kind="review",
            candidate_claim=self.candidate.to_dict(), target_context=self.context.to_dict(),
            reviewer="Descriptive reviewer name", independence=self.documents[0],
            context_manifest=self.manifest.to_dict(), authorization_policy=self.policy.to_dict(),
            reported_checks=[self.check2.to_dict(), self.check1.to_dict()], assessment=self.documents[1],
            route_assessments=[self.documents[2], dict(justification=self.route2.to_dict(), outcome="invalid",
                rationale="invalid support", outstanding_conditions=[], limitations=[])],
            open_obligations=["open"], limitations=[TEXT], artifacts=[self.a.to_dict(), self.b.to_dict()], origin="synthetic")
        self.issue_document = dict(format=FORMAT, version=1, kind="issue", disputed_point=TEXT,
            affected_records=[self.affected.to_dict(), self.affected2.to_dict()],
            objection_or_counterexample="synthetic objection", severity="blocking",
            proposed_discriminating_action="compare declarations", disposition="open", rationale=TEXT,
            limitations=["unverified"], supporting_evidence=[self.support.to_dict(), self.support2.to_dict()],
            artifacts=[self.b.to_dict(), self.a.to_dict()], origin="unverified")
        self.documents += (self.review_document, self.issue_document)
        self.links = ((self.candidate, self.context, self.manifest, self.policy,
                       self.check2, self.check1, self.route1, self.route2),
                      (self.affected, self.affected2, self.support, self.support2))

    def envelope(self, value):
        """Build a pure attributed envelope using exact identities that need not exist."""
        return encode_envelope("report", 5, value, self.provenance)

    def test_complete_documents_and_round_trips(self):
        """Check every field and nested value through dictionary, JSON, UTF-8 and envelope APIs."""
        for value, document in zip(self.values, self.documents):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(value.to_dict(), document)
                self.assertEqual(type(value).from_dict(document), value)
                self.assertEqual(type(value).from_dict(json.loads(json.dumps(document))), value)
                if type(value) not in (Review, Issue):
                    continue
                self.assertEqual(decode_content(document), value)
                encoded = dumps_content(value)
                self.assertEqual(encoded, json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
                self.assertTrue(encoded.isascii())
                self.assertEqual(loads_content(encoded), value)
                self.assertEqual(loads_content(encoded.encode("utf-8")), value)
                self.assertEqual(loads_content(json.dumps(document, ensure_ascii=False).encode("utf-8")), value)
                envelope = self.envelope(value)
                self.assertEqual(envelope.content, document)
                self.assertEqual((envelope.record_id, envelope.revision), ("report", 5))
                self.assertEqual(envelope.kind, document["kind"])
                self.assertEqual(envelope.provenance, self.provenance)
                self.assertIsNot(envelope.provenance, self.provenance)
                self.assertIsNone(envelope.operational_status)
                self.assertIsNone(envelope.scientific_disposition)
                self.assertEqual(decode_envelope(RecordEnvelope.from_dict(envelope.to_dict())), value)
                self.assertIsNot(decode_envelope(envelope), value)
        for value, links, artifacts in zip((self.review, self.issue), self.links, ((self.a, self.b), (self.b, self.a))):
            self.assertEqual(self.envelope(value).record_references, links)
            self.assertEqual(self.envelope(value).artifact_references, artifacts)

    def test_required_arguments_and_explicit_empty_collections(self):
        """Every constructor field is required; only affected_records forbids an empty array."""
        for value in self.values:
            arguments = {field.name: getattr(value, field.name) for field in fields(value)}
            for name in arguments:
                with self.subTest(value=type(value).__name__, missing=name):
                    partial = arguments.copy()
                    del partial[name]
                    with self.assertRaises(TypeError):
                        type(value)(**partial)
            for name, item in arguments.items():
                if type(item) is tuple:
                    with self.subTest(value=type(value).__name__, empty=name):
                        if name == "affected_records":
                            with self.assertRaisesRegex(DomainValidationError, name):
                                replace(value, **{name: []})
                        else:
                            changed = replace(value, **{name: []})
                            self.assertEqual(getattr(changed, name), ())
                            self.assertEqual(type(value).from_dict(changed.to_dict()), changed)

    def test_all_independent_codes_and_disagreements(self):
        """Each declared dimension varies independently, retaining obligations and exact context."""
        cases = (
            (self.independence, "requested_mode", MODES), (self.independence, "reported_mode", MODES),
            (self.assessment, "work_stage", ("exploring", "frozen_candidate", "under_review", "archived")),
            (self.assessment, "scientific_disposition", ("provisional", "supported_within_scope", "disputed",
                "support_withdrawn", "refuted_within_scope", "superseded")),
            (self.assessment, "applicability", ("applicable", "requires_reassessment", "inapplicable", "unresolved")),
            (self.assessment, "novelty", ("unassessed", "known_equivalent_identified", "search_found_no_equivalent",
                "researcher_assessed_contribution")),
            (self.route, "outcome", ("sufficient", "invalid", "stale", "inapplicable", "incomplete", "unresolved")),
            (self.issue, "severity", ("informational", "nonblocking", "blocking")),
            (self.issue, "disposition", ("open", "under_investigation", "resolved", "dismissed")),
            (self.review, "origin", ("synthetic", "unverified")), (self.issue, "origin", ("synthetic", "unverified")),
        )
        for value, name, codes in cases:
            for code in codes:
                with self.subTest(field=name, code=code):
                    changed = replace(value, **{name: code})
                    document = value.to_dict()
                    document[name] = code
                    self.assertEqual(changed.to_dict(), document)
                    self.assertEqual(type(value).from_dict(document), changed)
                    if type(changed) is IndependenceDeclaration:
                        content = replace(self.review, independence=changed)
                    elif type(changed) is SubstantiveAssessment:
                        content = replace(self.review, assessment=changed)
                    elif type(changed) is SupportRouteAssessment:
                        content = replace(self.review, route_assessments=[changed])
                    else:
                        content = changed
                    self.assertEqual(loads_content(dumps_content(content)), content)
                    self.assertEqual(decode_envelope(self.envelope(content)), content)
            for invalid in ("unknown", "", True, 1, None, [], " " + codes[0]):
                with self.subTest(field=name, invalid=invalid), self.assertRaisesRegex(DomainValidationError, name):
                    replace(value, **{name: invalid})
        support = ["source_based", "formal", "numerical", "symbolic", "analytical", "heuristic"]
        self.assertEqual(replace(self.assessment, support_types=support).to_dict()["support_types"], support)
        for code in support:
            with self.subTest(support_type=code):
                changed = replace(self.assessment, support_types=[code])
                self.assertEqual(SubstantiveAssessment.from_dict(changed.to_dict()), changed)
                self.assertEqual(changed.obligations, ("existence obligation",))
        for invalid in ("unknown", "Formal", " formal", ["formal"], 1):
            with self.subTest(support_type=invalid), self.assertRaisesRegex(DomainValidationError, "support_types"):
                replace(self.assessment, support_types=[invalid])
        changed = replace(self.review, reviewer="Another reviewer", route_assessments=[replace(self.route, outcome="invalid")])
        decoded = decode_envelope(self.envelope(changed))
        self.assertEqual(decoded.assessment.scientific_disposition, "supported_within_scope")
        self.assertEqual(decoded.assessment.obligations, ("existence obligation",))
        self.assertEqual(decoded.route_assessments[0].justification, self.route.justification)
        self.assertEqual(self.review.route_assessments[0].outcome, "sufficient")
        self.assertEqual(decoded.target_context, self.context)
        self.assertEqual(decode_envelope(self.envelope(replace(self.review, route_assessments=[]))).route_assessments, ())

    def test_mutation_isolation_and_frozen_assignment(self):
        """Mutating inputs, nested originals or returned trees cannot alter retained values."""
        for value, expected in zip(self.values, self.documents):
            with self.subTest(value=type(value).__name__):
                arguments = {field.name: list(getattr(value, field.name)) if type(getattr(value, field.name)) is tuple
                             else deepcopy(getattr(value, field.name)) for field in fields(value)}
                constructed = type(value)(**arguments)
                for item in arguments.values():
                    if type(item) is list:
                        item.clear()
                self.assertEqual(constructed.to_dict(), expected)
                document = deepcopy(expected)
                decoded = type(value).from_dict(document)
                mutate_containers(document)
                mutate_containers(decoded.to_dict())
                self.assertEqual(decoded.to_dict(), expected)
                with self.assertRaises(FrozenInstanceError):
                    setattr(decoded, fields(value)[0].name, None)
        nested = deepcopy(self.review)
        copied = replace(nested)
        object.__setattr__(nested.independence, "shared_sources", ["changed"])
        object.__setattr__(nested.assessment, "rationale", "changed")
        object.__setattr__(nested.candidate_claim, "record_id", "changed")
        object.__setattr__(nested.route_assessments[0].justification, "record_id", "changed")
        object.__setattr__(nested.artifacts[0], "size", 999)
        self.assertEqual(copied.to_dict(), self.review_document)
        for value in (self.review, self.issue):
            envelope = self.envelope(value)
            mutate_containers(envelope.to_dict())
            mutate_containers(envelope.content)
            mutate_containers(decode_envelope(envelope).to_dict())
            self.assertEqual(decode_envelope(envelope), value)
        provenance = deepcopy(self.provenance)
        envelope = encode_envelope("report", 1, self.review, provenance)
        object.__setattr__(provenance, "actor", "changed")
        self.assertEqual(envelope.provenance, self.provenance)

    def test_exact_fields_at_every_object_depth(self):
        """Remove or add each nested/top-level key; no familiar field is optional or extensible."""
        for value, expected in zip(self.values, self.documents):
            for path in self.object_paths(expected):
                original = self.at_path(expected, path)
                for name in (*original.keys(), "unexpected"):
                    document = deepcopy(expected)
                    target = self.at_path(document, path)
                    if name == "unexpected":
                        target[name] = "extra"
                    else:
                        del target[name]
                    with self.subTest(kind=type(value).__name__, path=path, key=name), self.assertRaises(DomainValidationError):
                        type(value).from_dict(document)

    @staticmethod
    def object_paths(value, path=()):
        """Enumerate all dictionary locations in a fixture, including reference/artifact objects."""
        if type(value) is dict:
            yield path
            for name, child in value.items():
                yield from AssessmentTests.object_paths(child, (*path, name))
        elif type(value) is list:
            for index, child in enumerate(value):
                yield from AssessmentTests.object_paths(child, (*path, index))

    @staticmethod
    def at_path(value, path):
        """Select a fixture subtree for independent malformed-document probes."""
        for key in path:
            value = value[key]
        return value

    def test_array_types_and_descriptive_text(self):
        """Require ordinary arrays/constructor sequences and preserve scalar text without trimming."""
        for value in self.values:
            for field in fields(value):
                item = getattr(value, field.name)
                if type(item) is tuple:
                    for invalid in (None, "text", {}, set(), iter(())):
                        with self.subTest(field=field.name, invalid=type(invalid).__name__), self.assertRaisesRegex(DomainValidationError, field.name):
                            replace(value, **{field.name: invalid})
                    for invalid in ((), None, "text", {}):
                        document = value.to_dict()
                        document[field.name] = invalid
                        with self.subTest(wire=field.name, invalid=invalid), self.assertRaisesRegex(DomainValidationError, field.name):
                            type(value).from_dict(document)
                if type(item) is str or (type(item) is tuple and item and type(item[0]) is str):
                    for invalid in (None, True, 3, b"text", "", " \n\t", "\ud800", "\udfff", "\ud834\udd1e"):
                        replacement = [invalid] if type(item) is tuple else invalid
                        with self.subTest(field=field.name, invalid=repr(invalid)), self.assertRaisesRegex(DomainValidationError, field.name):
                            replace(value, **{field.name: replacement})
        self.assertEqual(self.review.independence.shared_formulation, (TEXT, TEXT))
        self.assertEqual(loads_content(dumps_content(self.review)).assessment.conditions, (TEXT,))

    def test_duplicate_rules_and_valid_role_revision_reuse(self):
        """Uniqueness is collection-local and uses exact targets or digest, never judgments."""
        cases = ((self.assessment, "support_types", ["formal", "formal"]),
                 (self.review, "reported_checks", [self.check1, replace(self.check2, record_id="check", revision=1)]),
                 (self.review, "route_assessments", [self.route, replace(self.route, outcome="invalid", rationale="different")]),
                 (self.issue, "affected_records", [self.affected, replace(self.affected, target_kind="issue")]),
                 (self.issue, "supporting_evidence", [self.support, self.support]),
                 (self.review, "artifacts", [self.a, replace(self.a, size=9)]),
                 (self.issue, "artifacts", [self.b, self.b]))
        for value, name, invalid in cases:
            with self.subTest(field=name), self.assertRaisesRegex(DomainValidationError, name):
                replace(value, **{name: invalid})
        for value, name, references in ((self.review, "reported_checks", [self.check1, replace(self.check1, revision=2)]),
                (self.issue, "affected_records", [self.affected, replace(self.affected, revision=2)])):
            changed = replace(value, **{name: references})
            self.assertEqual(decode_envelope(self.envelope(changed)), changed)
        self.assertEqual(self.issue.affected_records[0].record_id, self.issue.supporting_evidence[0].record_id)
        self.assertEqual(self.envelope(self.issue).record_references, self.links[1])

    def test_reference_roles_kinds_and_exact_scalar_rules(self):
        """All references need a supported kind, exact role, opaque identity and integer revision."""
        for value in self.values:
            expected = value.to_dict()
            for path in self.object_paths(expected):
                reference = self.at_path(expected, path)
                if "record_id" not in reference:
                    continue
                for name, invalids in (("relationship", ("wrong_role", None)),
                        ("target_kind", (None, "unknown")),
                        ("record_id", ("../path", "", "with space", "é", 1)),
                        ("revision", (True, 1.0, "1", 0, -1, 2**63))):
                    for invalid in invalids:
                        document = deepcopy(expected)
                        self.at_path(document, path)[name] = invalid
                        with self.subTest(path=path, field=name, invalid=invalid), self.assertRaisesRegex(DomainValidationError, str(path[0])):
                            type(value).from_dict(document)
                if path[0] != "affected_records":
                    document = deepcopy(expected)
                    self.at_path(document, path)["target_kind"] = "run"
                    with self.subTest(path=path), self.assertRaisesRegex(DomainValidationError, str(path[0])):
                        type(value).from_dict(document)
        for kind in ("research_context", "claim", "justification", "evidence", "task_specification",
                     "project", "run", "corpus_manifest", "branch", "source", "work_product_manifest",
                     "tool_release", "tool_assessment", "issue", "review", "promotion_eligibility",
                     "decision", "attempt", "tool_execution", "event"):
            changed = replace(self.issue, affected_records=[replace(self.affected, target_kind=kind)])
            self.assertEqual(decode_content(changed.to_dict()), changed)

    def test_artifacts_are_exact_addresses_never_paths(self):
        """Reject malformed digests/sizes, arbitrary paths and locator extensions for both records."""
        for value in (self.review, self.issue):
            for invalid in ("/tmp/evidence.txt", {"path": "/tmp/evidence.txt"},
                            {"digest": "../file", "size": 1}, {"digest": "A" * 64, "size": 1},
                            {"digest": "a" * 63, "size": 1}, {"digest": 1, "size": 1},
                            *({"digest": "a" * 64, "size": size} for size in (True, 1.0, "1", -1, 2**63))):
                document = value.to_dict()
                document["artifacts"] = [invalid]
                with self.subTest(invalid=invalid), self.assertRaisesRegex(DomainValidationError, "artifacts"):
                    decode_content(document)
            with self.assertRaisesRegex(DomainValidationError, "artifacts"):
                replace(value, artifacts=["/tmp/evidence.txt"])

    def test_forged_nested_values_and_wrong_classes(self):
        """Parents revalidate exact nested classes and detach even mutable bypassed containers."""
        cases = (
            (self.review, "independence", forge(self.independence, "shared_sources", [None])),
            (self.review, "assessment", forge(self.assessment, "work_stage", "approved")),
            (self.review, "route_assessments", [forge(self.route, "outcome", "approved")]),
            (self.review, "candidate_claim", forge(self.candidate, "revision", True)),
            (self.review, "reported_checks", [forge(self.check1, "target_kind", None)]),
            (self.review, "artifacts", [forge(self.a, "size", True)]),
            (self.issue, "affected_records", [forge(self.affected, "revision", "1")]),
            (self.issue, "supporting_evidence", [forge(self.support, "record_id", "../file")]),
            (self.issue, "artifacts", [forge(self.b, "digest", "/tmp/file")]),
            (self.route, "justification", forge(self.route1, "relationship", "wrong")),
        )
        for value, name, invalid in cases:
            with self.subTest(field=name), self.assertRaisesRegex(DomainValidationError, name):
                replace(value, **{name: invalid})
            forged = forge(value, name, invalid)
            with self.assertRaisesRegex(DomainValidationError, name):
                forged.to_dict()
            if type(value) in (Review, Issue):
                with self.assertRaisesRegex(DomainValidationError, name):
                    dumps_content(forged)
                with self.assertRaisesRegex(DomainValidationError, name):
                    self.envelope(forged)
        nested_fields = ((self.review, "independence", self.independence),
                         (self.review, "assessment", self.assessment),
                         (self.review, "candidate_claim", self.candidate),
                         (self.review, "route_assessments", [self.route]),
                         (self.review, "reported_checks", [self.check1]),
                         (self.review, "artifacts", [self.a]),
                         (self.issue, "affected_records", [self.affected]),
                         (self.issue, "supporting_evidence", [self.support]))
        for value, name, valid in nested_fields:
            collection = type(valid) is list
            item = valid[0] if collection else valid
            subclass = type("Derived", (type(item),), {"__doc__": "Test subclass excluded by exact-class contracts."})
            derived = subclass(**{field.name: getattr(item, field.name) for field in fields(item)})
            for wrong in (None, object(), item.to_dict(), derived, SerializedLookalike(item.to_dict())):
                invalid = [wrong] if collection else wrong
                with self.subTest(field=name, wrong=type(wrong).__name__):
                    with self.assertRaisesRegex(DomainValidationError, name):
                        replace(value, **{name: invalid})
                    forged = forge(value, name, invalid)
                    with self.assertRaisesRegex(DomainValidationError, name):
                        forged.to_dict()
                    with self.assertRaisesRegex(DomainValidationError, name):
                        dumps_content(forged)
                    with self.assertRaisesRegex(DomainValidationError, name):
                        self.envelope(forged)
        missing = deepcopy(self.independence)
        object.__delattr__(missing, "reported_mode")
        with self.assertRaisesRegex(DomainValidationError, "independence") as caught:
            replace(self.review, independence=missing)
        self.assertIsNotNone(caught.exception.__cause__)
        mutable = forge(self.independence, "shared_sources", ["source"])
        copied = replace(self.review, independence=mutable)
        mutable.shared_sources.append("mutation")
        self.assertEqual(copied.independence.shared_sources, ("source",))

    def test_public_boundaries_reject_forged_top_levels_and_attribution(self):
        """Serialization and envelopes revalidate top-level objects and malformed provenance."""
        for invalid in (None, {}, self.independence, object()):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaisesRegex(DomainValidationError, "content"):
                    dumps_content(invalid)
                with self.assertRaisesRegex(DomainValidationError, "content"):
                    self.envelope(invalid)
                with self.assertRaisesRegex(DomainValidationError, "envelope"):
                    decode_envelope(invalid)
        for value in (self.review, self.issue):
            invalid = forge(value, "origin", "authenticated")
            with self.assertRaisesRegex(DomainValidationError, "origin"):
                dumps_content(invalid)
            with self.assertRaisesRegex(DomainValidationError, "origin"):
                self.envelope(invalid)
            subclass = type("Derived", (type(value),), {"__doc__": "Unsupported derived content value."})
            derived = subclass(**{field.name: getattr(value, field.name) for field in fields(value)})
            with self.assertRaisesRegex(DomainValidationError, "content"):
                dumps_content(derived)
        for provenance in (None, self.provenance.to_dict(), forge(self.provenance, "actor", "../bad"),
                           forge(self.provenance, "_details_json", "{"),
                           forge(self.provenance, "_details_json", '{"bad":NaN}')):
            with self.subTest(provenance=repr(provenance)), self.assertRaisesRegex(DomainValidationError, "provenance"):
                encode_envelope("report", 1, self.review, provenance)
        for name, invalid in (("record_id", "../bad"), ("revision", True)):
            args = dict(record_id="report", revision=1, content=self.review, provenance=self.provenance)
            args[name] = invalid
            with self.assertRaisesRegex(DomainValidationError, name):
                encode_envelope(**args)

    def test_headers_cross_codec_and_generic_preservation(self):
        """Formats never imply one another; generic envelopes preserve unsupported documents."""
        for value in (self.review, self.issue):
            document = value.to_dict()
            del document["format"]
            with self.assertRaises(NotTypedContentError):
                decode_content(document)
            for name, invalids in (("format", (None, "unknown", scientific._FORMAT)),
                                  ("version", (True, 1.0, "1", 0, 2, None)),
                                  ("kind", (None, "claim", "unknown", 1))):
                for invalid in invalids:
                    document = value.to_dict()
                    document[name] = invalid
                    with self.subTest(field=name, invalid=invalid), self.assertRaises(DomainValidationError) as caught:
                        decode_content(document)
                    self.assertNotIsInstance(caught.exception, NotTypedContentError)
            with self.assertRaises(DomainValidationError):
                scientific.decode_content(value.to_dict())
            with self.assertRaises(DomainValidationError):
                scientific.decode_envelope(self.envelope(value))
            other = Issue if type(value) is Review else Review
            with self.assertRaises(DomainValidationError):
                other.from_dict(value.to_dict())
            unsupported = value.to_dict()
            unsupported["version"] = 99
            unsupported["future"] = {"uninterpreted": [True]}
            envelope = RecordEnvelope("generic", 1, unsupported["kind"], unsupported, self.provenance)
            restored = RecordEnvelope.from_dict(envelope.to_dict())
            self.assertEqual(restored.content, unsupported)
            with self.assertRaisesRegex(DomainValidationError, "version"):
                decode_envelope(restored)
        context = scientific.ResearchContext("scope", [], [], [], [], [], [], [], [], [], [])
        with self.assertRaisesRegex(DomainValidationError, "format"):
            decode_content(context.to_dict())
        with self.assertRaisesRegex(DomainValidationError, "format"):
            decode_envelope(scientific.encode_envelope("scope", 1, context, self.provenance))

    def test_json_syntax_unicode_encodings_and_duplicate_keys(self):
        """Strict JSON rejects duplicates, trailing data, nonfinite numbers and malformed Unicode."""
        encoded = dumps_content(self.review)
        invalids = ["", "{", encoded + " {}", "[]", "null", "true", "1", '"text"',
                    '{"format":"x","format":"y"}',
                    '{"nested":{"same":1,"same":2}}',
                    '{"nested":[{"same":1,"same":2}]}',
                    '{"number":NaN}', '{"number":Infinity}', '{"number":-Infinity}', '{"number":1e999}',
                    b"\xff", encoded.encode("utf-16"), encoded.encode("utf-32"), b"\xef\xbb\xbf" + encoded.encode(),
                    '{"text":"\\ud800"}', '{"text":"\\udfff"}', '{"text":"\ud800"}',
                    encoded.encode("utf-16-le"), encoded.encode("utf-32-be")]
        for invalid in invalids:
            with self.subTest(invalid=repr(invalid)[:90]), self.assertRaises(DomainValidationError):
                loads_content(invalid)
        for invalid in (None, bytearray(encoded.encode()), {}, 1):
            with self.assertRaisesRegex(DomainValidationError, "assessment content"):
                loads_content(invalid)
        with self.assertRaisesRegex(DomainValidationError, "duplicate JSON key"):
            loads_content('{"a":{"b":0,"b":1}}')
        with self.assertRaises(DomainValidationError) as caught:
            loads_content(b"\xff")
        self.assertIsInstance(caught.exception.__cause__, UnicodeError)
        changed = replace(self.review, reviewer="𝒜")
        self.assertIn(r"\ud835\udc9c", dumps_content(changed))
        self.assertEqual(loads_content(dumps_content(changed)), changed)

    def test_python_trees_cycles_depth_and_ordinary_types(self):
        """Strict dictionary boundaries reject unsupported types, recursion and nonfinite values."""
        cyclic = {}
        cyclic["self"] = cyclic
        deep = {}
        for _ in range(1500):
            deep = {"nested": deep}
        for invalid in (None, [], cyclic, deep, {"bad": float("nan")}, {"bad": float("inf")},
                        {"bad": object()}, {1: "key"}, {"bad": b"bytes"}, {"bad": (1,)}, {"bad": {1}}):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(DomainValidationError):
                decode_content(invalid)
        with self.assertRaises(DomainValidationError):
            loads_content('{"nested":' + '[' * 1500 + '0' + ']' * 1500 + '}')
        for base, value in ((dict, self.review_document), (list, ["text"]), (str, TEXT), (int, 1)):
            subclass = type("Derived", (base,), {"__doc__": "Nonordinary input excluded from the codec."})
            invalid = subclass(value)
            with self.subTest(base=base.__name__), self.assertRaises(DomainValidationError):
                if base is dict:
                    decode_content(invalid)
                elif base is list:
                    replace(self.review, limitations=invalid)
                elif base is str:
                    replace(self.review, reviewer=invalid)
                else:
                    document = self.review.to_dict()
                    document["candidate_claim"]["revision"] = invalid
                    decode_content(document)

    def test_every_envelope_projection_mismatch(self):
        """Missing, added, repeated, relabeled, reordered or substituted links never get repaired."""
        for value in (self.review, self.issue):
            envelope = self.envelope(value)
            for field in ("record_references", "artifact_references"):
                links = getattr(envelope, field)
                if field == "record_references":
                    substitute = replace(links[0], record_id="substituted")
                    variants = [(replace(links[0], relationship="other"), *links[1:]),
                                (replace(links[0], target_kind="run"), *links[1:]),
                                (replace(links[0], revision=99), *links[1:])]
                else:
                    substitute = ArtifactReference("c" * 64, 4)
                    variants = [(replace(links[0], size=99), *links[1:])]
                variants += [links[1:], (*links, substitute), (substitute, *links[1:]),
                             (*links, links[0]), tuple(reversed(links))]
                for variant in variants:
                    document = envelope.to_dict()
                    document[field] = [item.to_dict() for item in variant]
                    changed = RecordEnvelope.from_dict(document)
                    with self.subTest(kind=envelope.kind, field=field, variant=variant), self.assertRaisesRegex(DomainValidationError, field):
                        decode_envelope(changed)
            for state, invalid in (("operational_status", "completed"), ("scientific_disposition", "supported_within_scope")):
                with self.assertRaisesRegex(DomainValidationError, state):
                    decode_envelope(forge(envelope, state, invalid))
            changed = forge(envelope, "kind", "issue" if type(value) is Review else "review")
            with self.assertRaisesRegex(DomainValidationError, "kind"):
                decode_envelope(changed)
            changed = forge(envelope, "record_references", [object()])
            with self.assertRaisesRegex(DomainValidationError, "envelope"):
                decode_envelope(changed)
            changed = forge(envelope, "provenance", forge(self.provenance, "actor", "../bad"))
            with self.assertRaises(DomainValidationError):
                decode_envelope(changed)
            document = envelope.to_dict()
            document["content"]["artifacts"].reverse()
            with self.assertRaisesRegex(DomainValidationError, "artifact_references"):
                decode_envelope(RecordEnvelope.from_dict(document))

    def test_favorable_reports_and_completed_tasks_do_not_promote_claims(self):
        """Reported support, blind modes and completed work leave separate canonical states intact."""
        claim = scientific.Claim("Synthetic candidate", "declaration", [],
            RecordReference("candidate-context", 1, "context", "research_context"), [], [], ["existence obligation"])
        candidate = scientific.encode_envelope("candidate", 2, claim, self.provenance)
        before = candidate.to_dict()
        task = RecordEnvelope("task", 1, "task_specification", {"result": "reported success"},
                              self.provenance, operational_status="completed")
        blind = IndependenceDeclaration(MODES[0], MODES[0], [], [], [], [], [], [], [])
        favorable = replace(self.review, independence=blind,
                            assessment=replace(self.assessment, applicability="applicable"))
        first = encode_envelope("review-one", 1, favorable, self.provenance)
        dissent = replace(favorable, reviewer="Second reviewer",
                          route_assessments=[replace(self.route, outcome="invalid")],
                          assessment=replace(self.assessment, scientific_disposition="disputed"))
        second = encode_envelope("review-two", 1, dissent, self.provenance)
        self.assertEqual(decode_envelope(first), favorable)
        self.assertEqual(decode_envelope(second), dissent)
        self.assertEqual(first.record_references[0], second.record_references[0])
        self.assertEqual(decode_envelope(first).route_assessments[0].outstanding_conditions, ("premises remain",))
        self.assertEqual(decode_envelope(first).assessment.obligations, ("existence obligation",))
        self.assertNotEqual(favorable.target_context.record_id, claim.context.record_id)
        self.assertEqual(candidate.to_dict(), before)
        self.assertEqual(candidate.scientific_disposition, "provisional")
        self.assertEqual(task.operational_status, "completed")
        self.assertIsNone(task.scientific_disposition)
        for envelope in (first, second):
            self.assertIsNone(envelope.operational_status)
            self.assertIsNone(envelope.scientific_disposition)

    def test_envelope_nested_classes_cannot_be_erased_by_serialization(self):
        """Reject forged domain subclasses/lookalikes even when they serialize to valid fields."""
        for value in (self.review, self.issue):
            envelope = self.envelope(value)
            for name in ("provenance", "record_references", "artifact_references"):
                original = getattr(envelope, name)
                collection = type(original) is tuple
                item = original[0] if collection else original
                subclass = type("Derived", (type(item),), {"__doc__": "Unsupported derived domain value."})
                derived = subclass.from_dict(item.to_dict())
                for wrong in (derived, SerializedLookalike(item.to_dict())):
                    changed = forge(envelope, name, (wrong, *original[1:]) if collection else wrong)
                    # Generic serialization loses the nested class: typed decoding must check first.
                    self.assertEqual(changed.to_dict(), envelope.to_dict())
                    with self.subTest(kind=envelope.kind, field=name, wrong=type(wrong).__name__):
                        with self.assertRaisesRegex(DomainValidationError, name):
                            decode_envelope(changed)
                        if name == "provenance":
                            with self.assertRaisesRegex(DomainValidationError, "provenance"):
                                encode_envelope("report", 1, value, wrong)
            subclass = type("DerivedEnvelope", (RecordEnvelope,), {"__doc__": "Unsupported derived envelope."})
            with self.assertRaisesRegex(DomainValidationError, "envelope"):
                decode_envelope(subclass.from_dict(envelope.to_dict()))
