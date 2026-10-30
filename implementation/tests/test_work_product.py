"""Strict immutable work-product values, portable names and exact envelope coherence."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json
import unittest

from research_pipeline.domain import ArtifactReference, DomainValidationError, RecordEnvelope, RecordReference
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.store import RecordStore, _decode_typed_envelope
from research_pipeline.work_product import (
    WorkProductFile, WorkProductManifest, decode_content, decode_envelope,
    dumps_content, loads_content, encode_envelope,
)
from tests import test_assessment as assessment_tests
from tests.test_assessment import forge, SerializedLookalike
from tests.test_assessment_store import mixed_graph
from tests.test_scientific import mutate_containers
from tests.test_store import CREATOR
from tests.test_typed_store import ref


TEXT = "  Declared α: 𝒜 ∈ ℝ\n  "
KINDS = ("note", "derivation", "calculation", "notebook", "checkpoint", "reading_report",
         "end_of_run_report", "figure", "program", "context_packet")


def manifest(artifact=None):
    """Make a minimal manifest with all nullable and empty declarations explicitly supplied."""
    artifact = ArtifactReference("a" * 64, 7) if artifact is None else artifact
    return WorkProductManifest("note", TEXT, "Explicit purpose", [" Author α ", "𝒜"],
                               None, None, None, None, [], [], None, [],
                               [WorkProductFile("notes/α.txt", artifact)], "notes/α.txt", [])


class WorkProductTests(unittest.TestCase):
    """Exercise declarations without storage, target existence or any filesystem interpretation."""

    def setUp(self):
        """Prepare every reference role and independently spell out wire content and projections."""
        self.a, self.b = ArtifactReference("a" * 64, 7), ArtifactReference("b" * 64, 2)
        self.links = (
            ref("task", "task", "task_specification"), ref("branch", "branch", "branch"),
            ref("context", "context", "research_context"), ref("run", "run", "run"),
            ref("claim", "linked_claim", "claim"), ref("claim", "linked_claim", "claim", 2),
            ref("source", "linked_source", "source"), ref("source", "linked_source", "source", 2),
            ref("product", "supersedes", "work_product_manifest"),
            ref("claim", "build_dependency", "claim"), ref("run", "build_dependency", "run"))
        self.value = replace(manifest(self.a), task=self.links[0], branch=self.links[1],
                             context=self.links[2], run=self.links[3], linked_claims=self.links[4:6],
                             linked_sources=self.links[6:8], supersedes=self.links[8],
                             build_dependencies=self.links[9:], limitations=[TEXT, TEXT],
                             files=[WorkProductFile("notes/α.txt", self.a),
                                    WorkProductFile("data/raw.bin", self.b), WorkProductFile("copy.txt", self.a)])
        self.document = dict(format="research_pipeline.work_product_content", version=1,
                             kind="work_product_manifest", product_kind="note", title=TEXT,
                             purpose="Explicit purpose", authors=[" Author α ", "𝒜"],
                             task=self.links[0].to_dict(), branch=self.links[1].to_dict(),
                             context=self.links[2].to_dict(), run=self.links[3].to_dict(),
                             linked_claims=[link.to_dict() for link in self.links[4:6]],
                             linked_sources=[link.to_dict() for link in self.links[6:8]],
                             supersedes=self.links[8].to_dict(),
                             build_dependencies=[link.to_dict() for link in self.links[9:]],
                             files=[dict(path="notes/α.txt", artifact=dict(digest="a" * 64, size=7)),
                                    dict(path="data/raw.bin", artifact=dict(digest="b" * 64, size=2)),
                                    dict(path="copy.txt", artifact=dict(digest="a" * 64, size=7))],
                             entry_file="notes/α.txt", limitations=[TEXT, TEXT])

    def test_complete_documents_projections_and_all_product_kinds(self):
        """All ten kinds preserve explicit declarations, repeated bytes and independent expected link order."""
        self.assertEqual(self.value.to_dict(), self.document)
        for kind in KINDS:
            value = replace(self.value, product_kind=kind)
            document = {**self.document, "product_kind": kind}
            self.assertEqual(decode_content(document), value)
            encoded = dumps_content(value)
            self.assertEqual(encoded, json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            self.assertTrue(encoded.isascii())
            for data in (encoded, encoded.encode(), json.dumps(document, ensure_ascii=False).encode()):
                self.assertEqual(loads_content(data), value)
            envelope = encode_envelope("product", 2, value, CREATOR)
            self.assertEqual(envelope.content, document)
            self.assertEqual(envelope.record_references, self.links)
            self.assertEqual(envelope.artifact_references, (self.a, self.b))
            self.assertIsNone(envelope.operational_status)
            self.assertIsNone(envelope.scientific_disposition)
            self.assertEqual(envelope.provenance, CREATOR)
            self.assertEqual(decode_envelope(envelope), value)
            self.assertEqual(decode_envelope(RecordEnvelope.from_dict(envelope.to_dict())), value)

    def test_required_arguments_and_null_empty_declarations(self):
        """Every constructor argument is mandatory, including optional references and explicit empty lists."""
        for value in (self.value, self.value.files[0]):
            args = {item.name: getattr(value, item.name) for item in fields(value)}
            for name in args:
                partial = args.copy()
                del partial[name]
                with self.subTest(missing=name), self.assertRaises(TypeError):
                    type(value)(**partial)
        value = manifest()
        self.assertEqual(decode_envelope(encode_envelope("new", 1, value, CREATOR)), value)
        self.assertEqual(encode_envelope("new", 1, value, CREATOR).record_references, ())
        for name in ("authors", "files"):
            with self.assertRaisesRegex(DomainValidationError, name):
                replace(value, **{name: []})

    def test_detached_inputs_outputs_and_nested_values(self):
        """Lists, nested frozen objects, wire trees and returned content cannot mutate retained declarations."""
        args = {item.name: deepcopy(getattr(self.value, item.name)) for item in fields(self.value)}
        for name, value in args.items():
            if type(value) is tuple:
                args[name] = list(value)
        value = WorkProductManifest(**args)
        object.__setattr__(args["context"], "record_id", "changed")
        object.__setattr__(args["files"][0].artifact, "size", 999)
        object.__setattr__(args["files"][1], "path", "changed")
        for item in args.values():
            if type(item) is list:
                item.clear()
        self.assertEqual(value.to_dict(), self.document)
        document = deepcopy(self.document)
        decoded = decode_content(document)
        mutate_containers(document)
        mutate_containers(decoded.to_dict())
        self.assertEqual(decoded.to_dict(), self.document)
        envelope = encode_envelope("product", 2, value, CREATOR)
        mutate_containers(envelope.content)
        mutate_containers(decode_envelope(envelope).to_dict())
        self.assertEqual(decode_envelope(envelope), value)
        with self.assertRaises(FrozenInstanceError):
            value.title = "changed"
        with self.assertRaises(FrozenInstanceError):
            value.files[0].path = "changed"

    def test_strict_fields_at_every_nested_level(self):
        """Every nested key is required, including target_kind; extra fields have no extension semantics."""
        for path in assessment_tests.AssessmentTests.object_paths(self.document):
            original = assessment_tests.AssessmentTests.at_path(self.document, path)
            for name in (*original, "extra"):
                document = deepcopy(self.document)
                target = assessment_tests.AssessmentTests.at_path(document, path)
                if name == "extra":
                    target[name] = "unexpected"
                else:
                    del target[name]
                with self.subTest(path=path, name=name), self.assertRaises(DomainValidationError):
                    decode_content(document)

    def test_types_text_and_integer_contracts(self):
        """Only ordinary sequences and nonblank scalar text are accepted; integers never coerce booleans."""
        for item in fields(self.value):
            value = getattr(self.value, item.name)
            if type(value) is tuple:
                for invalid in (None, "text", {}, set(), iter(())):
                    with self.subTest(field=item.name), self.assertRaisesRegex(DomainValidationError, item.name):
                        replace(self.value, **{item.name: invalid})
                for invalid in ((), {}, None, "text"):
                    document = deepcopy(self.document)
                    document[item.name] = invalid
                    with self.assertRaises(DomainValidationError):
                        decode_content(document)
        for name in ("title", "purpose", "entry_file"):
            for invalid in ("", " \n ", None, True, 1, [], "bad\ud800"):
                with self.subTest(field=name), self.assertRaises(DomainValidationError):
                    replace(self.value, **{name: invalid})
        for name in ("authors", "limitations"):
            for invalid in ("", " ", 1, None, "\udfff"):
                with self.assertRaisesRegex(DomainValidationError, name):
                    replace(self.value, **{name: [invalid]})
        for invalid in (True, 1.0, "1", -1, None, 2**63):
            for path, name in ((("files", 0, "artifact"), "size"), (("task",), "revision")):
                document = deepcopy(self.document)
                assessment_tests.AssessmentTests.at_path(document, path)[name] = invalid
                with self.assertRaises(DomainValidationError):
                    decode_content(document)
        for invalid in (None, 1, True, "Note", " note", "unsupported"):
            with self.assertRaisesRegex(DomainValidationError, "product_kind"):
                replace(self.value, product_kind=invalid)

    def test_reference_roles_uniqueness_and_declared_kinds(self):
        """Roles require exact declared kinds; duplicates fail per collection, with cross-role reuse allowed."""
        for name in ("task", "branch", "context", "run", "supersedes", "linked_claims", "linked_sources", "build_dependencies"):
            collection = type(getattr(self.value, name)) is tuple
            reference = getattr(self.value, name)[0] if collection else getattr(self.value, name)
            for invalid in (replace(reference, target_kind=None), replace(reference, relationship="other"),
                            forge(reference, "target_kind", "unsupported"), reference.to_dict()):
                with self.subTest(name=name), self.assertRaisesRegex(DomainValidationError, name):
                    replace(self.value, **{name: [invalid] if collection else invalid})
            if name != "build_dependencies":
                with self.assertRaisesRegex(DomainValidationError, name):
                    changed = replace(reference, target_kind="event")
                    replace(self.value, **{name: [changed] if collection else changed})
            if collection:
                with self.assertRaisesRegex(DomainValidationError, "repeated exact target"):
                    replace(self.value, **{name: [reference, reference]})
                changed = replace(self.value, **{name: [reference, replace(reference, revision=3)]})
                self.assertEqual(len(getattr(changed, name)), 2)
        self.assertEqual(self.value.linked_claims[0].record_id, self.value.build_dependencies[0].record_id)

    def test_portable_path_rejections_before_normalization(self):
        """Reject traversal, drives, devices, controls and compatibility forms before any filesystem operation."""
        invalids = ["", "/a", "a/", "a//b", ".", "..", "a/./b", "a/../b", "a\\b",
                    "C:/a", "C:a", "https://host/file", "file:stream", "a\x00b", "a\nb", "a\x7fb",
                    "a\u200db", "a\u202eb", "a\ud800", "a.", "a ", "dir./a", "dir /a",
                    "a<b", "a>b", 'a"b', "a|b", "a?b", "a*b", "Ｃ：file", "a／b", "a＼b",
                    "．", "．．", "a\u00a0", "a．", "a？b", "a＊b"]
        for stem in ("con", "PRN", "Aux", "NUL", "clock$", "CONIN$", "conout$", "com1", "LPT9", "COM¹", "lpt²", "ＣＯＮ"):
            invalids.extend((stem, stem + ".txt", "dir/" + stem + " .txt"))
        for path in invalids:
            with self.subTest(path=repr(path)), self.assertRaisesRegex(DomainValidationError, "path"):
                WorkProductFile(path, self.a)

    def test_valid_paths_and_exact_entry_membership_preserve_spelling(self):
        """Safe non-ASCII and non-normalized spellings survive unchanged; entry lookup never uses alias keys."""
        for path in ("Dir/a.txt", "Dir/b.txt", "résumé/𝒜.txt", "cafe\u0301.txt", "Straße", "com0", "lpt10", "x..y", " leading.txt", "\u1680"):
            value = replace(manifest(), files=[WorkProductFile(path, self.a)], entry_file=path)
            self.assertEqual(loads_content(dumps_content(value)).files[0].path, path)
        for path in ("NOTES/α.txt", "missing.txt"):
            with self.assertRaisesRegex(DomainValidationError, "entry_file"):
                replace(manifest(), entry_file=path)
        path = "cafe\u0301.txt"
        with self.assertRaisesRegex(DomainValidationError, "entry_file"):
            replace(manifest(), files=[WorkProductFile(path, self.a)], entry_file="café.txt")
        value = replace(manifest(), files=[WorkProductFile("Dir/a", self.a), WorkProductFile("Dir/b", self.a)], entry_file="Dir/a")
        self.assertEqual(len(value.files), 2)

    def test_path_alias_prefix_and_directory_spelling_conflicts(self):
        """Component comparisons reject ambiguous files and shared directories in either insertion order."""
        pairs = (("a", "a"), ("a", "A"), ("a", "a/b"), ("a", "A/b"),
                 ("Dir/a", "dir/b"), ("Dir/sub/a", "Dir/SUB/b"),
                 ("Straße", "STRASSE"), ("café.txt", "cafe\u0301.txt"),
                 ("é/a", "e\u0301/b"), ("Ａ/b", "a/c"), ("a/ß", "a/ss/c"))
        for pair in pairs:
            for paths in (pair, pair[::-1]):
                with self.subTest(paths=paths), self.assertRaises(DomainValidationError) as caught:
                    replace(manifest(), files=[WorkProductFile(path, self.a) for path in paths], entry_file=paths[0])
                for path in paths:
                    self.assertIn(repr(path), str(caught.exception))
        # Textual prefixes alone do not imply file/directory conflicts.
        value = replace(manifest(), files=[WorkProductFile("a", self.a), WorkProductFile("ab/c", self.a)], entry_file="a")
        self.assertEqual(len(value.files), 2)

    def test_conflicting_sizes_and_forged_values(self):
        """Nested classes and frozen fields are reconstructed at constructors, serialization and envelope conversion."""
        with self.assertRaisesRegex(DomainValidationError, "conflicting size"):
            replace(manifest(), files=[WorkProductFile("a", self.a), WorkProductFile("b", replace(self.a, size=8))], entry_file="a")
        bad_file = forge(self.value.files[0], "path", "../bad")
        bad_artifact = forge(self.a, "size", True)
        for invalid in (bad_file, self.value.files[0].to_dict(), SerializedLookalike(self.value.files[0].to_dict()),
                        forge(self.value.files[0], "artifact", bad_artifact),
                        forge(self.value.files[0], "artifact", SerializedLookalike(self.a.to_dict()))):
            with self.assertRaisesRegex(DomainValidationError, "files"):
                replace(self.value, files=[invalid])
        cases = (("files", [bad_file]), ("authors", []), ("title", ""),
                 ("task", forge(self.links[0], "revision", True)),
                 ("task", SerializedLookalike(self.links[0].to_dict())))
        for name, invalid in cases:
            forged = forge(self.value, name, invalid)
            for action in (lambda: forged.to_dict(), lambda: dumps_content(forged),
                           lambda: encode_envelope("product", 2, forged, CREATOR)):
                with self.subTest(name=name), self.assertRaisesRegex(DomainValidationError, name):
                    action()
        for invalid in (None, {}, SerializedLookalike(self.document)):
            with self.assertRaises(DomainValidationError):
                dumps_content(invalid)
            with self.assertRaises(DomainValidationError):
                decode_envelope(invalid)
        missing = deepcopy(self.value.files[0])
        object.__delattr__(missing, "artifact")
        with self.assertRaises(DomainValidationError) as caught:
            missing.to_dict()
        self.assertIsNotNone(caught.exception.__cause__)

    def test_envelope_rejects_every_projection_substitution(self):
        """Missing, surplus, duplicate, reordered and relabeled envelope links never get repaired."""
        envelope = encode_envelope("product", 2, self.value, CREATOR)
        for name in ("record_references", "artifact_references"):
            links = getattr(envelope, name)
            changes = ((), links[:-1], links + (links[0],), tuple(reversed(links)))
            if name == "record_references":
                changes += ((replace(links[0], relationship="other"), *links[1:]),
                            (replace(links[0], record_id="other"), *links[1:]))
            else:
                changes += ((replace(links[0], digest="c" * 64), *links[1:]),)
            for changed in changes:
                with self.subTest(name=name), self.assertRaisesRegex(DomainValidationError, name):
                    decode_envelope(forge(envelope, name, changed))
            with self.assertRaises(DomainValidationError):
                decode_envelope(forge(envelope, name, [SerializedLookalike(links[0].to_dict())]))
        for name, invalid in (("kind", "source"), ("operational_status", "completed"),
                              ("scientific_disposition", "provisional"), ("revision", True),
                              ("provenance", SerializedLookalike(CREATOR.to_dict()))):
            with self.assertRaises(DomainValidationError):
                decode_envelope(forge(envelope, name, invalid))
        with self.assertRaises(DomainValidationError):
            encode_envelope("product", 2, self.value, forge(CREATOR, "actor", "../bad"))

    def test_optional_supersession_is_envelope_local(self):
        """Creation forbids supersession; appends allow null or exactly the same identity's prior revision."""
        for revision in (1, 2, 9):
            value = manifest()
            self.assertEqual(decode_envelope(encode_envelope("product", revision, value, CREATOR)), value)
        for revision, identity, target in ((1, "product", 1), (2, "other", 1), (3, "product", 1),
                                           (2, "product", 2), (2, "product", 3)):
            value = replace(manifest(), supersedes=ref(identity, "supersedes", "work_product_manifest", target))
            self.assertEqual(decode_content(value.to_dict()), value)
            with self.assertRaisesRegex(DomainValidationError, "supersedes"):
                encode_envelope("product", revision, value, CREATOR)
            envelope = RecordEnvelope("product", revision, "work_product_manifest", value.to_dict(), CREATOR,
                                      [value.supersedes], [self.a])
            with self.assertRaisesRegex(DomainValidationError, "supersedes"):
                decode_envelope(envelope)

    def test_headers_json_unicode_and_nonordinary_trees(self):
        """Malformed headers, duplicates, nonfinite numbers, cycles, depth and nonscalar Unicode fail explicitly."""
        document = deepcopy(self.document)
        del document["format"]
        with self.assertRaises(NotTypedContentError):
            decode_content(document)
        for name, invalids in (("format", (None, "unknown", "research_pipeline.scientific_content")),
                              ("version", (True, 1.0, "1", 0, 2)), ("kind", (None, "note", 1))):
            for invalid in invalids:
                with self.assertRaises(DomainValidationError) as caught:
                    decode_content({**self.document, name: invalid})
                self.assertNotIsInstance(caught.exception, NotTypedContentError)
        encoded = dumps_content(self.value)
        for data in ("", "{", encoded + "{}", "[]", "null", '{"format":1,"format":2}',
                     '{"nested":[{"a":1,"a":2}]}', '{"n":NaN}', '{"n":Infinity}', '{"n":1e999}',
                     b"\xff", encoded.encode("utf-16"), encoded.encode("utf-32"),
                     '{"text":"\\ud800"}', '{"text":"\udfff"}', bytearray(b"{}"),
                     '{"deep":' + '[' * 1500 + '0' + ']' * 1500 + '}'):
            with self.subTest(data=repr(data)[:70]), self.assertRaises(DomainValidationError):
                loads_content(data)
        with self.assertRaises(DomainValidationError) as caught:
            loads_content(b"\xff")
        self.assertIsInstance(caught.exception.__cause__, UnicodeError)
        cyclic = {}
        cyclic["self"] = cyclic
        deep = {}
        for _ in range(1500):
            deep = {"nested": deep}
        for invalid in (cyclic, deep, {"bad": float("nan")}, {1: "key"}, {"bad": b"bytes"},
                        {"bad": (1,)}, {"bad": object()}, None):
            with self.assertRaises(DomainValidationError):
                decode_content(invalid)
        for base, name, value in ((str, "title", TEXT), (list, "authors", [TEXT])):
            derived = type("Derived", (base,), {"__doc__": "Nonordinary input must fail."})(value)
            with self.assertRaises(DomainValidationError):
                replace(self.value, **{name: derived})

    def test_all_supported_build_kinds_are_explicit_descriptive_references(self):
        """Every domain kind can be a declared build input without introducing execution semantics."""
        kinds = ("research_context", "claim", "justification", "evidence", "task_specification",
                 "project", "run", "corpus_manifest", "branch", "source", "work_product_manifest",
                 "tool_release", "tool_assessment", "issue", "review", "promotion_eligibility",
                 "decision", "attempt", "tool_execution", "event")
        dependencies = [ref("input-" + str(index), "build_dependency", kind)
                        for index, kind in enumerate(kinds)]
        value = replace(manifest(), build_dependencies=dependencies)
        self.assertEqual(loads_content(dumps_content(value)).build_dependencies, tuple(dependencies))
        self.assertEqual(encode_envelope("product", 1, value, CREATOR).record_references, tuple(dependencies))

    def test_exhaustive_typed_and_shallow_traversal_table(self):
        """Keep all seven kinds' explicit edge partitions, including nullable Evidence and shallow Review manifests."""
        graph = {item.record_id: item for item in mixed_graph(self.a)}
        expected = {
            "context": ((), ()),
            "candidate": ((ref("context", "context", "research_context"),), ()),
            "route": ((ref("route-context", "context", "research_context"),
                       ref("candidate", "premise", "claim"), ref("candidate", "conclusion", "claim"),
                       ref("evidence", "evidence", "evidence")), ()),
            "evidence": ((ref("context", "context", "research_context"), ref("candidate", "target_claim", "claim")),
                         (ref("task", "input_record", None), ref("evidence", "input_record", "evidence"))),
            "review-a": ((ref("candidate", "candidate_claim", "claim"),
                          ref("target-context", "target_context", "research_context"),
                          ref("evidence", "reported_evidence", "evidence"),
                          ref("route", "assessed_route", "justification"),
                          ref("alternative", "assessed_route", "justification")),
                         (ref("manifest", "context_manifest", "work_product_manifest"),
                          ref("policy", "authorization_policy", "decision"),
                          ref("tool", "reported_tool_execution", "tool_execution"))),
            "issue": ((ref("evidence", "supporting_evidence", "evidence"),),
                      (ref("review-b", "affected_record", "review"), ref("issue-peer", "affected_record", "issue"),
                       ref("issue", "affected_record", "issue"))),
        }
        for identity, partition in expected.items():
            with self.subTest(identity=identity):
                self.assertEqual(RecordStore._typed_references(_decode_typed_envelope(graph[identity])), partition)
        self.assertEqual(RecordStore._typed_references(self.value),
                         ((self.links[2], *self.links[4:6], self.links[8]),
                          (self.links[0], self.links[1], self.links[3], *self.links[6:8], *self.links[9:])))
        self.assertEqual(RecordStore._typed_references(manifest()), ((), ()))
