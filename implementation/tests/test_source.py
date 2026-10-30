"""Strict bounded Source declarations, exact lineage and inert codecs on synthetic values."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from research_pipeline.domain import ArtifactReference, DomainValidationError, RecordEnvelope, RecordReference
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.source import (
    DeclaredText, SourceProvenance, SourceDeclaration, SourceRestrictions, SourceArtifact,
    ToolSetting, SourceLocation, LocationMapping, SourceExtraction, SourceReading,
    SourceStatement, RelatedSource, Source, decode_content, dumps_content, loads_content,
    encode_envelope, decode_envelope,
)
from research_pipeline.store import RecordStore, _decode_typed_envelope
from tests.test_assessment import forge, SerializedLookalike
from tests.test_assessment_store import mixed_graph, decoded
from tests.test_store import CREATOR
from tests.test_typed_store import ref
from tests.test_work_product import manifest


TEXT = "  Supplied α: 𝒜 ∈ ℝ\n  "


def known(value=TEXT):
    """Return a literal known declaration without trimming synthetic Unicode text."""
    return DeclaredText(value, None)


def unknown():
    """Explain absent synthetic metadata without inventing an upstream fact."""
    return DeclaredText(None, "Not supplied in synthetic data")


def acquisition():
    """Describe supplied inert bytes with explicit unknown retrieval locations."""
    return SourceProvenance("supplied_artifact", known("Synthetic supplier"),
                            known("2026-10-30T12:00:00.1Z"), known("supplied/input"),
                            unknown(), unknown(), "partial", [TEXT])


def source(artifacts=None):
    """Build multi-original synthetic lineage with partial reading and all statement/reference roles."""
    a, b, c = artifacts or (ArtifactReference("a" * 64, 12), ArtifactReference("b" * 64, 3),
                            ArtifactReference("c" * 64, 7))
    provenance = acquisition()
    originals = [SourceArtifact("original", "originals/α.tex", a, known("text/plain"), 0o640, provenance),
                 SourceArtifact("license", "originals/LICENSE", b, unknown(), None, provenance),
                 SourceArtifact("copy", "copy.tex", a, unknown(), 0o600, provenance)]
    output = SourceArtifact("text", "derived/α.txt", c, known("text/plain"), None, provenance)
    extraction = SourceExtraction("supplied-extraction", ["original", "license"], known("supplied test data"),
                                  unknown(), [ToolSetting("mode", known("inert"))], [output],
                                  [LocationMapping("page", "bytes")], ["No parser was executed", TEXT])
    locations = [SourceLocation("page", "original", "page", "p. α", None, None),
                 SourceLocation("bytes", "text", "byte", "supplied text offsets", 0, c.size),
                 SourceLocation("upstream", None, "equation", "(𝒜.1)", None, None),
                 SourceLocation("line", "original", "line", "declared lines", 1, 900)]
    checks = [ref("evidence", "reported_evidence", "evidence"),
              ref("tool", "reported_tool_execution", "tool_execution")]
    reading = SourceReading("selected_material", ["page"],
                            ref("report", "reading_report", "work_product_manifest"),
                            "reported_partial", checks, known("Synthetic reader"), ["Not a read paper"])
    statements = [SourceStatement("quoted", "source_statement", TEXT, known(), ["upstream"], [], []),
                  SourceStatement("interpretation", "interpretation", "Declared interpretation", unknown(), [], [], []),
                  SourceStatement("checked", "referenced_check", "Reported check", known(), ["bytes"], checks, [TEXT])]
    declaration = SourceDeclaration("unknown", "Not supplied; no permission implied")
    return Source("work-alpha", unknown(), known("edition α"), known(), [known("Author α"), unknown()],
                  provenance, SourceRestrictions(declaration, declaration, declaration, declaration),
                  originals, [extraction], locations, reading, statements,
                  [RelatedSource(ref("related", "related_source", "source"), "Related declared work")], None, [TEXT])


def uninspected():
    """Return a metadata-only capture with no artifacts, report, locations or invented reading."""
    return replace(source(), originals=[], extractions=[], locations=[], statements=[], related_sources=[],
                   reading=SourceReading("uninspected", [], None, "unreported", [], unknown(), []))


def dictionaries(value, path=()):
    """Yield paths to every nested wire dictionary for systematic strict-field tests."""
    if type(value) is dict:
        yield path
        for key, child in value.items():
            yield from dictionaries(child, (*path, key))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from dictionaries(child, (*path, index))


def at_path(value, path):
    """Return a nested synthetic wire container using a known test-generated path."""
    for key in path:
        value = value[key]
    return value


class SourceCodecTests(unittest.TestCase):
    """Exercise pure contracts without reading artifacts, opening locators or inferring facts."""

    def test_complete_roundtrip_projections_and_independent_identities(self):
        """Preserve all declarations, exact repeated roles, first-byte projections and distinct revisions."""
        value = source()
        document = value.to_dict()
        self.assertEqual(set(document), {item.name for item in fields(Source)} | {"format", "version", "kind"})
        self.assertEqual(document["format"], "research_pipeline.source_content")
        self.assertEqual(document["version"], 1)
        self.assertEqual(document["kind"], "source")
        encoded = dumps_content(value)
        self.assertEqual(encoded, json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        for data in (encoded, encoded.encode(), json.dumps(document, ensure_ascii=False).encode()):
            self.assertEqual(loads_content(data), value)
        value = replace(value, supersedes=ref("capture", "supersedes", "source", 7),
                        reading=replace(value.reading, report=ref("report", "reading_report", "work_product_manifest", 23)))
        item = encode_envelope("capture", 8, value, CREATOR)
        self.assertEqual(decode_envelope(item), value)
        self.assertEqual(_decode_typed_envelope(item), value)
        self.assertEqual(item.record_references, (value.supersedes, value.related_sources[0].reference,
                         value.reading.report, *value.reading.checks, *value.statements[-1].checks))
        self.assertEqual(item.artifact_references, (value.originals[0].artifact, value.originals[1].artifact,
                                                  value.extractions[0].outputs[0].artifact))
        self.assertEqual(value.upstream_version.value, "edition α")
        self.assertEqual(value.provenance.occurred_at.value, "2026-10-30T12:00:00.1Z")
        self.assertIsNone(item.operational_status)
        self.assertIsNone(item.scientific_disposition)
        self.assertEqual(value.title.value, TEXT)

    def test_every_nested_field_required_and_extras_rejected(self):
        """Systematically remove/add each nested field, including generic references' optional defaults."""
        document = source().to_dict()
        for path in dictionaries(document):
            for key in (*at_path(document, path), "unexpected"):
                with self.subTest(path=path, key=key):
                    altered = deepcopy(document)
                    node = at_path(altered, path)
                    if key == "unexpected":
                        node[key] = None
                    else:
                        del node[key]
                    with self.assertRaises(DomainValidationError):
                        decode_content(altered)

    def test_required_constructors_collection_bounds_and_nested_reconstruction(self):
        """Every Source value requires every argument, bounds collections and reconstructs strict nested classes."""
        value = source()
        examples = (value, value.title, value.provenance, value.restrictions.access,
                    value.restrictions, value.originals[0], value.extractions[0].settings[0],
                    value.locations[0], value.extractions[0].mappings[0], value.extractions[0],
                    value.reading, value.statements[0], value.related_sources[0])
        for example in examples:
            cls = type(example)
            self.assertEqual(cls.from_dict(example.to_dict()), example)
            arguments = {item.name: getattr(example, item.name) for item in fields(cls)}
            for field in fields(cls):
                with self.subTest(cls=cls.__name__, field=field.name):
                    omitted = dict(arguments)
                    del omitted[field.name]
                    with self.assertRaises(TypeError):
                        cls(**omitted)
                    member = getattr(example, field.name)
                    if type(member) is tuple:
                        with self.assertRaises(DomainValidationError):
                            replace(example, **{field.name: [member[0] if member else None] * 1025})
                        wire = example.to_dict()
                        wire[field.name] = tuple(wire[field.name])
                        with self.assertRaises(DomainValidationError):
                            cls.from_dict(wire)
        missing = object.__new__(DeclaredText)
        object.__setattr__(missing, "value", "known")
        with self.assertRaisesRegex(DomainValidationError, "title"):
            replace(value, title=missing)
        for revision in (True, 1.0, "1", 0, 2**63):
            bad = forge(value.reading.report, "revision", revision)
            with self.assertRaises(DomainValidationError):
                replace(value.reading, report=bad)
        for relationship, kind in (("input_record", "work_product_manifest"), ("reading_report", None),
                                   ("reading_report", "source")):
            with self.assertRaises(DomainValidationError):
                replace(value.reading, report=ref("report", relationship, kind))
        for changes in ({"method": "fetch"}, {"outcome": "success"}):
            with self.assertRaises(DomainValidationError):
                replace(value.provenance, **changes)
        for changes in ({"tool": None}, {"tool_version": "unknown"}):
            with self.assertRaises(DomainValidationError):
                replace(value.extractions[0], **changes)

    def test_strict_json_and_headers(self):
        """Reject duplicate keys, coercion, nonordinary values, encoding failures, cycles and trailing data."""
        document = uninspected().to_dict()
        for field, values in (("version", [True, 1.0, "1", 0, 2, None]),
                              ("format", [None, 3, "unknown"]), ("kind", ["claim", None, 1])):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(DomainValidationError):
                    decode_content({**document, field: value})
        missing = dict(document)
        del missing["format"]
        with self.assertRaises(NotTypedContentError):
            decode_content(missing)
        encoded = dumps_content(source())
        for data in (encoded + "{}", '{"format":1,"format":2}',
                     encoded.replace('"unknown_reason":null', '"unknown_reason":null,"unknown_reason":null', 1),
                     b'\xff', '"\ud800"', '{"a":NaN}', '[', '[' * 2000 + ']' * 2000, 3, bytearray(b'{}')):
            with self.subTest(data=str(data)[:60]), self.assertRaises(DomainValidationError):
                loads_content(data)
        for value in ([], None, {**document, "authors": tuple(document["authors"])},
                      {**document, "limitations": [float("inf")]}, {**document, "title": {"value": "\ud800", "unknown_reason": None}}):
            with self.assertRaises(DomainValidationError):
                decode_content(value)
        cycle = dict(document)
        cycle["cycle"] = cycle
        with self.assertRaises(DomainValidationError):
            decode_content(cycle)

    def test_text_counts_numbers_and_unknowns(self):
        """Exercise Source-only bounds, explicit unknowns and exact integer rejection at their boundaries."""
        self.assertEqual(known("unknown").value, "unknown")
        self.assertEqual(known("x" * 16384).value, "x" * 16384)
        for args in ((None, None), ("x", "why"), ("", None), (" ", None), (None, ""), ("x" * 16385, None), (True, None)):
            with self.assertRaises(DomainValidationError):
                DeclaredText(*args)
        self.assertEqual(len(replace(uninspected(), limitations=["x"] * 1024).limitations), 1024)
        for changes in ({"limitations": ["x"] * 1025}, {"authors": []}, {"work_id": "x" * 129},
                        {"work_id": "bad/path"}, {"authors": (x for x in [unknown()])}):
            with self.assertRaises(DomainValidationError):
                replace(uninspected(), **changes)
        artifact = source().originals[0]
        self.assertEqual(replace(artifact, original_mode=0o7777).original_mode, 0o7777)
        for mode in (-1, 0o10000, True, 1.0, "1"):
            with self.assertRaises(DomainValidationError):
                replace(artifact, original_mode=mode)
        self.assertEqual(len(replace(artifact, path="a" * 4096).path), 4096)
        with self.assertRaises(DomainValidationError):
            replace(artifact, path="a" * 4097)
        for integer in (True, 1.0, "1", 2**63, -1):
            for key in ("start", "end"):
                with self.assertRaises(DomainValidationError):
                    replace(source().locations[1], **{key: integer})
            forged = forge(artifact.artifact, "size", integer)
            with self.assertRaises(DomainValidationError):
                replace(artifact, artifact=forged)
        for method in ("supplied_local", "supplied_artifact"):
            with self.assertRaises(DomainValidationError):
                replace(acquisition(), method=method, supplied_locator=unknown())
        for stamp in ("2026-02-30T00:00:00Z", "2026-10-30", "2026-10-30T00:00:00+00:00"):
            with self.assertRaises(DomainValidationError):
                replace(acquisition(), occurred_at=known(stamp))

    def test_all_declaration_coverage_and_reproduction_codes(self):
        """All supported codes round-trip independently; checks never automatically change coverage."""
        value = source()
        for coverage in ("uninspected", "metadata_only", "abstract_only", "selected_material", "whole_document"):
            for reproduction in ("unreported", "not_attempted", "reported_failed", "reported_partial", "reported_succeeded"):
                reading = replace(value.reading, coverage=coverage, reproduction=reproduction,
                                  locations=[] if coverage == "uninspected" else ["page"])
                item = replace(value, reading=reading)
                self.assertEqual(loads_content(dumps_content(item)), item)
        for method in ("supplied_local", "supplied_artifact", "reported_retrieval", "unknown"):
            for outcome in ("available", "partial", "unavailable", "unknown"):
                fact = replace(acquisition(), method=method, outcome=outcome, occurred_at=unknown())
                self.assertEqual(SourceProvenance.from_dict(fact.to_dict()), fact)
        for field, statuses in (("access", ("available", "limited", "unavailable", "unknown")),
                                ("reuse", ("permitted", "restricted", "prohibited", "unknown")),
                                ("confidentiality", ("public", "confidential", "restricted", "unknown")),
                                ("external_processing", ("permitted", "restricted", "prohibited", "unknown"))):
            for status in statuses:
                restrictions = replace(value.restrictions, **{field: SourceDeclaration(status, TEXT)})
                self.assertEqual(SourceRestrictions.from_dict(restrictions.to_dict()), restrictions)
            with self.assertRaises(DomainValidationError):
                replace(value.restrictions, **{field: SourceDeclaration("invalid", TEXT)})
        for changes in ({"coverage": "uninspected"}, {"coverage": "selected_material", "locations": []},
                        {"checks": []}, {"coverage": "read"}, {"reproduction": "success"},
                        {"checks": [value.reading.checks[0]] * 2},
                        {"checks": [ref("evidence", "reported_evidence", None)]}):
            with self.assertRaises(DomainValidationError):
                replace(value.reading, **changes)
        for changes in ({"locations": []}, {"checks": value.reading.checks}, {"category": "claim"}):
            with self.assertRaises(DomainValidationError):
                replace(value.statements[0], **changes)
        with self.assertRaises(DomainValidationError):
            replace(value.statements[-1], checks=[])

    def test_inventory_aliases_sizes_and_total_count(self):
        """Repeated bytes at distinct paths are valid; IDs, paths and sizes stay globally coherent."""
        value = source()
        a = value.originals[0]
        for path in ("copy.tex", "COPY.TEX", "originals", "originals/α.tex/child", "../x", "CON", "x\\y", "/x", "a/../b", "a."):
            with self.subTest(path=path), self.assertRaises(DomainValidationError):
                replace(value, originals=[*value.originals, replace(a, artifact_id="new", path=path)])
        with self.assertRaises(DomainValidationError):
            replace(value, originals=[*value.originals, replace(a, path="other")])
        with self.assertRaises(DomainValidationError):
            replace(value, originals=[*value.originals, replace(a, artifact_id="new", path="other",
                    artifact=ArtifactReference(a.artifact.digest, a.artifact.size + 1))])
        originals = [replace(a, artifact_id=f"a{i}", path=f"file{i}") for i in range(1024)]
        self.assertEqual(len(replace(uninspected(), originals=originals).originals), 1024)
        extraction = replace(value.extractions[0], original_inputs=["a0"], mappings=[], warnings=["No mapping"])
        with self.assertRaises(DomainValidationError):
            replace(uninspected(), originals=originals, extractions=[extraction])

    def test_location_and_lineage_resolution_failures(self):
        """Reject dangling IDs, reversed/cross-output mappings and ranges without inferring line counts."""
        value = source()
        extraction = value.extractions[0]
        for changes in ({"original_inputs": ["text"]}, {"original_inputs": ["missing"]},
                        {"mappings": [LocationMapping("bytes", "page")]},
                        {"mappings": [LocationMapping("upstream", "bytes")]},
                        {"mappings": [LocationMapping("missing", "bytes")]}):
            with self.assertRaises(DomainValidationError):
                replace(value, extractions=[replace(extraction, **changes)])
        for changes in ({"original_inputs": []}, {"original_inputs": ["original"] * 2}, {"outputs": []},
                        {"mappings": [], "warnings": []}, {"mappings": list(extraction.mappings) * 2},
                        {"settings": list(extraction.settings) * 2}):
            with self.assertRaises(DomainValidationError):
                replace(extraction, **changes)
        other = replace(extraction, extraction_id="other", outputs=[replace(extraction.outputs[0], artifact_id="other", path="other")],
                        mappings=[LocationMapping("page", "bytes")])
        with self.assertRaises(DomainValidationError):
            replace(value, extractions=[extraction, other])
        for changes in ({"artifact_id": "missing"}, {"end": 100}):
            with self.assertRaises(DomainValidationError):
                replace(value, locations=[value.locations[0], replace(value.locations[1], **changes), *value.locations[2:]])
        for changes in ({"start": 1, "end": 1}, {"artifact_id": None}, {"start": -1}):
            with self.assertRaises(DomainValidationError):
                replace(value.locations[1], **changes)
        for kind in ("page", "section", "equation", "theorem"):
            self.assertEqual(replace(value.locations[2], kind=kind).label, "(𝒜.1)")
        for changes in ({"start": 1}, {"end": 1}, {"kind": "paragraph"}):
            with self.assertRaises(DomainValidationError):
                replace(value.locations[0], **changes)
        for changes in ({"reading": replace(value.reading, locations=["missing"])},
                        {"locations": list(value.locations) * 2}, {"statements": list(value.statements) * 2},
                        {"extractions": list(value.extractions) * 2}):
            with self.assertRaises(DomainValidationError):
                replace(value, **changes)

    def test_detachment_forged_values_and_envelope_coherence(self):
        """Mutable input/output containers and bypassed frozen nested classes cannot escape validation."""
        value = source()
        authors = [known()]
        detached = replace(value, authors=authors)
        authors.clear()
        wire = detached.to_dict()
        wire["authors"][0]["value"] = "changed"
        self.assertEqual(detached.authors[0].value, TEXT)
        with self.assertRaises(FrozenInstanceError):
            detached.work_id = "other"
        for name, invalid in (("title", SerializedLookalike(value.title.to_dict())), ("authors", [None]),
                              ("reading", forge(value.reading, "checks", [forge(value.reading.checks[0], "revision", True)])),
                              ("originals", [forge(value.originals[0], "artifact", SerializedLookalike(value.originals[0].artifact.to_dict()))]),
                              ("provenance", forge(value.provenance, "occurred_at", known("bad")))):
            with self.subTest(name=name), self.assertRaises(DomainValidationError):
                dumps_content(forge(value, name, invalid))
        item = encode_envelope("capture", 1, value, CREATOR)
        for name in ("record_references", "artifact_references"):
            links = getattr(item, name)
            for altered in ([], links[1:], links[::-1], (*links, links[0])):
                with self.assertRaises(DomainValidationError):
                    decode_envelope(forge(item, name, altered))
        for name, invalid in (("kind", "claim"), ("operational_status", "completed"),
                              ("scientific_disposition", "provisional"), ("provenance", None)):
            with self.assertRaises(DomainValidationError):
                decode_envelope(forge(item, name, invalid))
        for revision, identity, previous in ((1, "capture", 1), (2, "other", 1), (3, "capture", 1), (2, "capture", 2)):
            bad = replace(value, supersedes=ref(identity, "supersedes", "source", previous))
            with self.assertRaises(DomainValidationError):
                encode_envelope("capture", revision, bad, CREATOR)
            malformed = RecordEnvelope("capture", revision, "source", bad.to_dict(), CREATOR,
                                       [bad.supersedes, *item.record_references], item.artifact_references)
            with self.assertRaises(DomainValidationError):
                decode_envelope(malformed)
        for revision in (1, 2):
            bad = replace(value, related_sources=[RelatedSource(ref("capture", "related_source", "source", revision), TEXT)])
            with self.assertRaises(DomainValidationError):
                encode_envelope("capture", 3, bad, CREATOR)
        with self.assertRaises(DomainValidationError):
            replace(value, related_sources=list(value.related_sources) * 2)

    def test_exhaustive_eight_kind_reference_partition(self):
        """Freeze every existing constrained/shallow role and add Source without strengthening old edges."""
        expected = {
            "research_context": (set(), set()), "claim": ({"context"}, set()),
            "justification": ({"context", "premise", "conclusion", "evidence"}, set()),
            "evidence": ({"context", "target_claim"}, {"input_record"}),
            "review": ({"candidate_claim", "target_context", "reported_evidence", "assessed_route"},
                       {"context_manifest", "authorization_policy", "reported_tool_execution"}),
            "issue": ({"supporting_evidence"}, {"affected_record"}),
            "work_product_manifest": ({"context", "linked_claim", "supersedes"},
                                      {"task", "branch", "run", "linked_source", "build_dependency"}),
            "source": ({"supersedes", "reading_report", "reported_evidence"}, {"related_source", "reported_tool_execution"}),
        }
        product = replace(manifest(), context=ref("ctx", "context", "research_context"),
                          linked_claims=[ref("c", "linked_claim", "claim")], supersedes=ref("m", "supersedes", "work_product_manifest"),
                          task=ref("t", "task", "task_specification"), branch=ref("b", "branch", "branch"),
                          run=ref("r", "run", "run"), linked_sources=[ref("s", "linked_source", "source")],
                          build_dependencies=[ref("d", "build_dependency", "source")])
        values = {}
        for item in mixed_graph(ArtifactReference("a" * 64, 1)):
            values.setdefault(item.kind, decoded(item))
        values["work_product_manifest"] = product
        values["source"] = replace(source(), supersedes=ref("capture", "supersedes", "source"))
        actual = {kind: tuple({ref.relationship for ref in group} for group in RecordStore._typed_references(value))
                  for kind, value in values.items()}
        self.assertEqual(actual, expected)

    def test_inert_import(self):
        """Import Source in a fresh interpreter with filesystem writes and networking forbidden by audit."""
        program = '''
import sys

def audit(event, args):
    """Reject effects during import while allowing Python's ordinary read-only module loading."""
    if event.startswith(("socket.", "subprocess.")) or event in ("os.mkdir", "os.remove", "os.rename"):
        raise AssertionError(event)
    if event == "open" and ((isinstance(args[1], str) and any(c in args[1] for c in "wax+")) or args[2] & 3):
        raise AssertionError("write during import")
sys.addaudithook(audit)
import research_pipeline.source
'''
        result = subprocess.run([sys.executable, "-B", "-c", program], capture_output=True, text=True, timeout=60,
                                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
        self.assertEqual(result.returncode, 0, result.stderr)
