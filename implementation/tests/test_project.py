"""Strict detached project codecs and attributed proposal prerequisites without effects."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from research_pipeline.domain import ArtifactReference, DomainValidationError, RecordEnvelope
from research_pipeline.project import (
    AttributedText, IntakeLink, IntakeDeclaration, IntakeRequirement, ProceduralJudgment,
    ReadinessProposal, ProjectSetup, decode_content, dumps_content, loads_content,
    encode_envelope, decode_envelope, setup_presentation,
)
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.store import RecordStore, _decode_typed_envelope
from research_pipeline.work_product import decode_content as decode_product
from tests.test_assessment import forge, SerializedLookalike
from tests.test_corpus import inspection, location
from tests.test_source import known, unknown, dictionaries, at_path, TEXT
from tests.test_store import CREATOR
from tests.test_typed_store import ref
from tests.test_work_product import manifest


def attributed(text=TEXT):
    """Keep synthetic objective/intent text separate from its unauthenticated attribution."""
    return AttributedText(known(text), known("Synthetic researcher"))


def judgment(status="not_assessed"):
    """Explain an explicitly supplied procedural assessment without claiming scientific support."""
    return ProceduralJudgment(status, "Synthetic declared procedural judgment only", known())


def readiness(status="insufficient_materials", evidence=()):
    """Declare proposal status/reasons, with affirmation only when explicitly requested by this fixture."""
    assessment = judgment("affirmed" if status == "proposed_ready" else "not_assessed")
    return ReadinessProposal(status, ["Explicit synthetic proposal, no authorization"], known(), evidence,
                             assessment, assessment)


def declaration(identity="seed-note", locations=(), links=()):
    """Describe supplied text with a literal origin; locations are separately and explicitly selected."""
    return IntakeDeclaration(identity, "definition", TEXT, "supplied_observation", known("Supplied note"),
                             known(), locations, links, ["Unverified", "Unverified"])


def setup():
    """Represent an empty setup with explained unknown intent and no invented scientific brief."""
    return ProjectSetup(attributed(), AttributedText(unknown(), unknown()), AttributedText(unknown(), unknown()),
                        ref("corpus", "initial_corpus", "corpus_manifest"),
                        ref("corpus", "current_corpus", "corpus_manifest"), None, None, None,
                        inspection(), [], [], readiness(), [], None, "Initial setup", unknown())


def dossier():
    """Supply a coherent local proposed-ready snapshot; target admission remains a separate store obligation."""
    links = [IntakeLink(ref("target-" + kind, role, kind), "Declared relationship α") for role, kind in (
        ("intake_context", "research_context"), ("intake_claim", "claim"),
        ("intake_justification", "justification"), ("intake_evidence", "evidence"),
        ("intake_review", "review"), ("intake_issue", "issue"), ("intake_work_product", "work_product_manifest"))]
    return replace(setup(), objective=attributed("Investigate f(x) = x"), researcher_intent=attributed("Clarify scope"),
                   context=ref("context", "context", "research_context"),
                   brief=ref("brief", "research_brief", "work_product_manifest"),
                   intake_report=ref("intake", "intake_report", "work_product_manifest"),
                   inspection=replace(inspection("selected_material", [location()]), attribution=known()),
                   declarations=[declaration(locations=[location()], links=links),
                                 replace(declaration("conflict"), category="contradiction", origin="unknown_origin", origin_detail=unknown())],
                   remaining=[IntakeRequirement("policy", "policy_proposal", "research_admission", attributed())],
                   readiness=readiness("proposed_ready", ["seed-note"]), limitations=[TEXT, TEXT])


class ProjectCodecTests(unittest.TestCase):
    """Test strict wire, local readiness and projections, independently of storage or scientific interpretation."""

    def test_roundtrips_projection_and_presentation(self):
        """All fields, Unicode, repetitions and exact ordered occurrences survive the public codecs."""
        for value, presentation in ((setup(), "awaiting_materials"), (dossier(), "awaiting_authorization")):
            wire = value.to_dict()
            self.assertEqual(set(wire), {f.name for f in fields(value)} | {"format", "version", "kind"})
            self.assertEqual((wire["format"], wire["version"], wire["kind"]), ("research_pipeline.project_content", 1, "project"))
            encoded = dumps_content(value)
            self.assertEqual(encoded, json.dumps(wire, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            for raw in (encoded, encoded.encode(), json.dumps(wire, ensure_ascii=False).encode()):
                self.assertEqual(loads_content(raw), value)
            envelope = encode_envelope("project", 1, value, CREATOR)
            expected = [value.initial_corpus, value.current_corpus]
            expected.extend(r for r in (value.context, value.brief, value.intake_report) if r is not None)
            expected.extend(loc.source for loc in value.inspection.locations)
            for item in value.declarations:
                expected.extend(loc.source for loc in item.locations)
                expected.extend(link.reference for link in item.links)
            self.assertEqual(envelope.record_references, tuple(expected))
            self.assertEqual(envelope.artifact_references, ())
            self.assertEqual(RecordStore._typed_references(value), (tuple(expected), ()))
            self.assertEqual(_decode_typed_envelope(envelope), value)
            self.assertEqual(decode_envelope(envelope), value)
            self.assertIsNone(envelope.operational_status)
            self.assertIsNone(envelope.scientific_disposition)
            self.assertEqual(setup_presentation(value), presentation)
            successor = replace(value, supersedes=ref("project", "supersedes", "project"))
            self.assertEqual(encode_envelope("project", 2, successor, CREATOR).record_references,
                             (successor.supersedes, *expected))
        for status in ("not_assessed", "incomplete_intake"):
            self.assertEqual(setup_presentation(replace(setup(), readiness=readiness(status))), "setup_incomplete")
        self.assertEqual(decode_content(replace(setup(), intake_report=dossier().intake_report).to_dict()).context, None)

    def test_every_nested_field_required_and_no_extensions(self):
        """Remove every nested required field and add unknown fields, including all nullable declarations."""
        wire = dossier().to_dict()
        for path in dictionaries(wire):
            for key in (*at_path(wire, path), "unexpected"):
                changed = deepcopy(wire)
                container = at_path(changed, path)
                if key == "unexpected":
                    container[key] = None
                else:
                    del container[key]
                with self.subTest(path=path, key=key), self.assertRaises(DomainValidationError):
                    decode_content(changed)
        with self.assertRaises(NotTypedContentError):
            decode_content({})
        for name in ("title", "objective", "researcher_intent"):
            value = replace(setup(), **{name: AttributedText(unknown(), unknown())})
            self.assertEqual(decode_content(value.to_dict()), value)

    def test_frozen_detachment_and_forgery(self):
        """Constructors, serialization and presentation reject bypassed or lookalike nested values."""
        value = dossier()
        with self.assertRaises(FrozenInstanceError):
            value.revision_reason = "changed"
        wire = value.to_dict()
        copy = decode_content(wire)
        wire["declarations"][0]["text"] = "changed"
        self.assertEqual(copy, value)
        input_list = [declaration()]
        copied = replace(setup(), declarations=input_list)
        input_list.clear()
        self.assertEqual(len(copied.declarations), 1)
        for name, invalid in (("readiness", None), ("title", SerializedLookalike(value.title)),
                              ("initial_corpus", forge(value.initial_corpus, "revision", True)),
                              ("declarations", [forge(value.declarations[0], "text", " ")]),
                              ("inspection", forge(value.inspection, "coverage", "all"))):
            for operation in (lambda: replace(value, **{name: invalid}),
                              lambda: dumps_content(forge(value, name, invalid)),
                              lambda: setup_presentation(forge(value, name, invalid))):
                with self.subTest(name=name), self.assertRaises(DomainValidationError):
                    operation()
        class Derived(AttributedText):
            """A subclass is intentionally not an exact supported nested value."""
        with self.assertRaises(DomainValidationError):
            replace(setup(), title=Derived(known(), known()))
        for cls, instance in ((AttributedText, value.title), (IntakeLink, value.declarations[0].links[0]),
                              (IntakeDeclaration, value.declarations[0]), (IntakeRequirement, value.remaining[0]),
                              (ProceduralJudgment, value.readiness.substantive_relevance),
                              (ReadinessProposal, value.readiness)):
            self.assertEqual(cls.from_dict(instance.to_dict()), instance)
            field = fields(cls)[0].name
            with self.assertRaises(DomainValidationError):
                forge(instance, field, None).to_dict()

    def test_strict_json_headers_unicode_and_numeric_types(self):
        """Malformed JSON, duplicate keys, nonfinite/coerced values and excessive depth never become content."""
        encoded = dumps_content(setup())
        bad_json = [b'\xff', '', '{} {}', '{', encoded + ' trailing',
                    encoded.replace('"version":1', '"version":1,"version":1'),
                    encoded.replace('"value":', '"value":null,"value":', 1),
                    '[' * 2000 + '0' + ']' * 2000, '"\ud800"']
        for token in ('NaN', 'Infinity', '-Infinity', '1e999', 'true', '1.0', '"1"', '0', '2', '9223372036854775808'):
            bad_json.append(encoded.replace('"version":1', '"version":' + token))
        for raw in bad_json:
            with self.subTest(raw=str(raw)[:60]), self.assertRaises(DomainValidationError):
                loads_content(raw)
        for field, invalid in (("format", "unknown"), ("format", None), ("kind", "corpus_manifest"),
                               ("revision_reason", "\ud800"), ("revision_reason", float('inf'))):
            changed = setup().to_dict()
            changed[field] = invalid
            with self.assertRaises(DomainValidationError):
                decode_content(changed)
        cyclic = setup().to_dict()
        cyclic["limitations"].append(cyclic)
        with self.assertRaises(DomainValidationError):
            decode_content(cyclic)
        for raw in (bytearray(encoded.encode()), None, [], 1):
            with self.assertRaises(DomainValidationError):
                loads_content(raw)

    def test_vocabulary_origins_unique_members_and_roles(self):
        """Explicit enums and exact roles preserve unknown origins while forbidding inferred or duplicate links."""
        for category in ("definition", "assumption", "convention", "existing_work", "proposed_question",
                         "proposed_baseline", "contradiction", "gap", "unprocessed_remainder", "brief_choice"):
            self.assertEqual(replace(declaration(), category=category).category, category)
        for origin in ("supplied_observation", "new_proposal", "unknown_origin"):
            detail = unknown() if origin == "unknown_origin" else known()
            value = replace(declaration(locations=[location()]), origin=origin, origin_detail=detail)
            self.assertEqual(IntakeDeclaration.from_dict(value.to_dict()), value)
            with self.assertRaises(DomainValidationError):
                replace(value, origin_detail=known() if origin == "unknown_origin" else unknown())
        for kind in ("material", "prerequisite", "policy_proposal", "resource_proposal"):
            for stage in ("intake", "research_admission"):
                self.assertEqual(IntakeRequirement("r", kind, stage, attributed()).stage, stage)
        for status in ("not_assessed", "affirmed", "not_affirmed"):
            self.assertEqual(judgment(status).status, status)
        for changes in ({"status": "ready"}, {"explanation": " "}, {"status": "affirmed", "attribution": unknown()}):
            with self.assertRaises(DomainValidationError):
                replace(judgment(), **changes)
        for changes in ({"category": "claim"}, {"origin": "supplied"}, {"locations": [location(), location()]},
                        {"links": [dossier().declarations[0].links[0]] * 2}):
            with self.assertRaises(DomainValidationError):
                replace(declaration(), **changes)
        for role, kind in (("intake_project", "project"), ("intake_decision", "decision"),
                           ("intake_claim", None), ("intake_claim", "evidence")):
            with self.assertRaises(DomainValidationError):
                IntakeLink(ref("target", role, kind), "Declared")
        for changes in ({"declarations": [declaration()] * 2}, {"remaining": [dossier().remaining[0]] * 2},
                        {"declarations": [declaration(locations=[location()])]},
                        {"readiness": readiness("not_assessed", ["absent"])},
                        {"initial_corpus": ref("corpus", "initial_corpus", "corpus_manifest", 2)},
                        {"current_corpus": ref("other", "current_corpus", "corpus_manifest")},
                        {"brief": dossier().brief}):
            with self.assertRaises(DomainValidationError):
                replace(setup(), **changes)
        for name, role, kind in (("initial_corpus", "initial_corpus", "corpus_manifest"),
                                 ("current_corpus", "current_corpus", "corpus_manifest"),
                                 ("context", "context", "research_context"), ("brief", "research_brief", "work_product_manifest"),
                                 ("intake_report", "intake_report", "work_product_manifest"), ("supersedes", "supersedes", "project")):
            for wrong in (ref("corpus", "wrong", kind), ref("corpus", role, "source"), ref("corpus", role, None)):
                with self.assertRaises(DomainValidationError):
                    replace(dossier(), **{name: wrong})

    def test_every_proposed_ready_prerequisite(self):
        """No missing local prerequisite can produce awaiting_authorization; explicit future work can remain."""
        value = dossier()
        bad = [{name: AttributedText(unknown(), known())} for name in ("title", "objective", "researcher_intent")]
        bad += [{name: None} for name in ("brief", "intake_report", "context")]
        bad += [{"inspection": replace(value.inspection, attribution=unknown())},
                {"inspection": inspection(), "declarations": [declaration()]},
                {"declarations": [declaration()]},
                {"readiness": replace(value.readiness, attribution=unknown())},
                {"remaining": [replace(value.remaining[0], stage="intake")]}]
        for name in ("substantive_relevance", "assignment_usability"):
            for status in ("not_assessed", "not_affirmed"):
                bad.append({"readiness": replace(value.readiness, **{name: judgment(status)})})
        for changes in bad:
            with self.subTest(fields=list(changes)), self.assertRaises(DomainValidationError):
                replace(value, **changes)
        for changes in ({"reasons": []}, {"evidence_declarations": []}, {"evidence_declarations": ["seed-note"] * 2}):
            with self.assertRaises(DomainValidationError):
                replace(value.readiness, **changes)
        explicit_unknown = replace(value.declarations[0], origin="unknown_origin", origin_detail=unknown())
        self.assertEqual(setup_presentation(replace(value, declarations=[explicit_unknown])), "awaiting_authorization")

    def test_bounds_and_pre_reconstruction_collection_checks(self):
        """Exact text/ID/revision and collection maxima work; excessive collections fail before member copying."""
        self.assertEqual(len(replace(setup(), revision_reason="x" * 16384).revision_reason), 16384)
        for text in ("x" * 16385, " ", "", True, "\udfff"):
            for instance, field in ((setup(), "revision_reason"), (declaration(), "text"),
                                    (judgment(), "explanation"), (dossier().declarations[0].links[0], "relation")):
                with self.assertRaises(DomainValidationError):
                    replace(instance, **{field: text})
        for identity in ("x" * 129, "é", "-x", "", True):
            with self.assertRaises(DomainValidationError):
                replace(declaration(), declaration_id=identity)
        self.assertEqual(replace(declaration(), declaration_id="x" * 128).declaration_id, "x" * 128)
        self.assertEqual(replace(setup(), current_corpus=ref("corpus", "current_corpus", "corpus_manifest", 2**63-1)).current_corpus.revision, 2**63-1)
        for revision in (True, 1.0, "1", 0, 2**63):
            with self.assertRaises(DomainValidationError):
                replace(setup(), current_corpus=forge(setup().current_corpus, "revision", revision))
        instances = [(setup(), "limitations", ["x"] * 1024),
                     (setup(), "declarations", [declaration(f"d{i}") for i in range(1024)]),
                     (setup(), "remaining", [replace(dossier().remaining[0], requirement_id=f"r{i}") for i in range(1024)]),
                     (declaration(), "locations", [location(name=f"l{i}") for i in range(1024)]),
                     (declaration(), "links", [IntakeLink(ref(f"w{i}", "intake_work_product", "work_product_manifest"), "x") for i in range(1024)]),
                     (declaration(), "limitations", ["x"] * 1024),
                     (readiness(), "reasons", ["x"] * 1024),
                     (readiness(), "evidence_declarations", [f"d{i}" for i in range(1024)])]
        for instance, field, maximum in instances:
            self.assertEqual(len(getattr(replace(instance, **{field: maximum}), field)), 1024)
            with self.assertRaisesRegex(DomainValidationError, "at most 1024"):
                replace(instance, **{field: [None] * 1025})
            wire = instance.to_dict()
            wire[field] = [None] * 1025
            with self.assertRaisesRegex(DomainValidationError, "at most 1024"):
                type(instance).from_dict(wire)
        locs = [location(name=f"l{i}") for i in range(1024)]
        value = replace(setup(), inspection=inspection("selected_material", locs),
                        declarations=[declaration(f"d{i}", locs) for i in range(3)])
        self.assertEqual(1024 + sum(len(d.locations) for d in value.declarations), 4096)
        with self.assertRaisesRegex(DomainValidationError, "4096"):
            replace(value, declarations=[*value.declarations, declaration("extra", [locs[0]])])
        links = instances[4][2]
        linked = replace(setup(), declarations=[declaration(f"d{i}", links=links) for i in range(4)])
        self.assertEqual(sum(len(d.links) for d in linked.declarations), 4096)
        with self.assertRaisesRegex(DomainValidationError, "4096"):
            replace(linked, declarations=[*linked.declarations, declaration("extra", links=links[:1])])

    def test_exact_envelope_null_states_and_local_history(self):
        """Both directions reject projection repair, state promotion and non-immediate same-project predecessors."""
        value = dossier()
        envelope = encode_envelope("project", 1, value, CREATOR)
        refs = envelope.record_references
        for refs2 in (refs[1:], (*refs, refs[0]), refs[::-1], (replace(refs[0], relationship="wrong"), *refs[1:])):
            with self.assertRaises(DomainValidationError):
                decode_envelope(forge(envelope, "record_references", refs2))
        for field, invalid in (("kind", "source"), ("operational_status", "completed"),
                               ("scientific_disposition", "provisional"), ("provenance", None),
                               ("artifact_references", [ArtifactReference("a" * 64, 1)])):
            with self.assertRaises(DomainValidationError):
                decode_envelope(forge(envelope, field, invalid))
        for revision, predecessor in ((2, None), (1, ref("project", "supersedes", "project")),
                                      (3, ref("project", "supersedes", "project")),
                                      (2, ref("other", "supersedes", "project")),
                                      (2, ref("project", "supersedes", "project", 2))):
            changed = replace(value, supersedes=predecessor)
            with self.assertRaises(DomainValidationError):
                encode_envelope("project", revision, changed, CREATOR)
            wire = envelope.to_dict()
            wire.update(revision=revision, content=changed.to_dict(),
                        record_references=([predecessor.to_dict()] if predecessor else []) + [r.to_dict() for r in refs])
            with self.assertRaises(DomainValidationError):
                decode_envelope(RecordEnvelope.from_dict(wire))

    def test_additive_product_labels(self):
        """New labels extend the existing version-1 vocabulary without changing old wire values."""
        for label in ("note", "derivation", "calculation", "notebook", "checkpoint", "reading_report",
                      "end_of_run_report", "figure", "program", "context_packet", "intake_report", "research_brief"):
            value = replace(manifest(ArtifactReference("a" * 64, 1)), product_kind=label)
            self.assertEqual(decode_product(value.to_dict()), value)

    def test_codecs_and_presentation_have_no_effects(self):
        """A fresh-process audit forbids I/O after imports, including store access, sockets and subprocesses."""
        program = '''
import sys

def audit(event, args):
    """Allow import reads only; never writes, network or processes."""
    if event.startswith(("socket.", "subprocess.")) or event in ("os.mkdir", "os.remove", "os.rename"):
        raise AssertionError(event)
    if event == "open" and ((isinstance(args[1], str) and any(c in args[1] for c in "wax+")) or args[2] & 3):
        raise AssertionError("write during import")
sys.addaudithook(audit)
from research_pipeline.project import *
from tests.test_project import dossier
from tests.test_store import CREATOR

def deny(event, args):
    """Forbid every filesystem open during pure construction and conversion."""
    if event == "open": raise AssertionError("codec filesystem access")
sys.addaudithook(deny)
v = dossier()
e = encode_envelope("project", 1, loads_content(dumps_content(decode_content(v.to_dict()))), CREATOR)
assert decode_envelope(e) == v
assert setup_presentation(v) == "awaiting_authorization"
'''
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-B", "-c", program], capture_output=True, text=True, timeout=60,
                                env={**os.environ, "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root)))})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pure_dossier_checks_every_location_and_document_role(self):
        """Cached metadata checks enforce current-entry originals and conditional document sets on every use."""
        from research_pipeline.project import _validate_dossier
        from tests.test_corpus import inventory, entry, missing
        from tests.test_source import source
        value = dossier()
        captured = source()
        corpus = inventory([entry(selected=captured.originals[:1]), entry("license", selected=captured.originals[1:2]), missing()])
        document = replace(manifest(), context=value.context,
                           linked_sources=[ref("capture", "linked_source", "source")],
                           build_dependencies=[ref("corpus", "build_dependency", "corpus_manifest")])
        values = {("corpus", 1): corpus, ("capture", 1): captured,
                  ("brief", 1): replace(document, product_kind="research_brief"),
                  ("intake", 1): replace(document, product_kind="intake_report")}
        _validate_dossier(value, values)
        for name in ("bytes", "upstream", "missing"):
            loc = location(name=name)
            bad = replace(value, inspection=replace(value.inspection, locations=[location(), loc]),
                          declarations=[declaration(locations=[location(), loc])])
            with self.assertRaisesRegex(DomainValidationError, "source_location target capture@1"):
                _validate_dossier(bad, values)
        for entry_id in ("license", "missing", "absent"):
            loc = location(entry_id)
            bad = replace(value, inspection=replace(value.inspection, locations=[location(), loc]),
                          declarations=[declaration(locations=[loc])])
            with self.assertRaises(DomainValidationError):
                _validate_dossier(bad, values)
        for role in ("brief", "intake"):
            for changes in ({"product_kind": "note"}, {"context": None}, {"linked_sources": []},
                            {"build_dependencies": []},
                            {"linked_sources": [ref("absent", "linked_source", "source")]},
                            {"build_dependencies": [*document.build_dependencies, ref("absent", "build_dependency", "source")]},
                            {"build_dependencies": [*document.build_dependencies, ref("other", "build_dependency", "research_context")]}):
                invalid = {**values, (role, 1): replace(values[(role, 1)], **changes)}
                with self.assertRaises(DomainValidationError):
                    _validate_dossier(value, invalid)
        # Extra shallow project dependencies remain inert, even without a cached value.
        extra = replace(values[("brief", 1)], build_dependencies=[*document.build_dependencies,
                        ref("opaque", "build_dependency", "project")])
        _validate_dossier(value, {**values, ("brief", 1): extra})
        # One cached manifest cannot satisfy two different incoming product roles.
        shared = replace(value, intake_report=ref("brief", "intake_report", "work_product_manifest"))
        with self.assertRaisesRegex(DomainValidationError, "product_kind intake_report"):
            _validate_dossier(shared, values)

    def test_pure_project_history_keeps_baseline_and_monotonic_selection(self):
        """Full snapshots may retain or advance corpus selections but cannot reset or regress them."""
        from research_pipeline.project import _validate_successor
        base = setup()
        _validate_successor(base, None)
        later = replace(base, current_corpus=ref("corpus", "current_corpus", "corpus_manifest", 3),
                        supersedes=ref("project", "supersedes", "project"))
        _validate_successor(later, base)
        _validate_successor(replace(later, supersedes=ref("project", "supersedes", "project", 2)), later)
        with self.assertRaisesRegex(DomainValidationError, "current_corpus target corpus@1"):
            _validate_successor(replace(base, supersedes=ref("project", "supersedes", "project", 2)), later)
        rebound = replace(base, initial_corpus=ref("other", "initial_corpus", "corpus_manifest"),
                          current_corpus=ref("other", "current_corpus", "corpus_manifest"))
        with self.assertRaisesRegex(DomainValidationError, "initial_corpus target other@1"):
            _validate_successor(rebound, base)
