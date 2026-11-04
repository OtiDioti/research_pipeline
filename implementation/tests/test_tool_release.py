"""Independent contract, identity, exact-type, semantic and passive-boundary coverage."""

import copy
from contextlib import ExitStack
from dataclasses import FrozenInstanceError
import importlib
import json
import os
import socket
import subprocess
import unittest
from unittest.mock import patch

from research_pipeline import tool_release as product
from research_pipeline import tool_release_codec as codec
from research_pipeline.domain import ArtifactReference, RecordReference
from research_pipeline.resources import Dimension
from research_pipeline.work_product import WorkProductFile
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_release import (
    ToolRelease, ToolReleaseLimits, ToolReleaseValidationError, ToolReleaseLimitError,
    decode_content, dumps_content, loads_content,
)
from tests.tool_release_fixtures import (
    wire, sections, constructor_sections, canonical, rehash, known, missing, at,
    record, artifact, SCIENCE, RECORD_SLOTS, FILE_SLOTS,
)


class TrapDict(dict):
    """A mapping subclass whose hooks must never be consulted by the contract."""

    def items(self):
        """Expose accidental virtual-method use with an unmistakable sentinel."""
        raise AssertionError("mapping hook invoked")

    def __iter__(self):
        """Expose accidental subclass iteration before exact-type rejection."""
        raise AssertionError("mapping iteration invoked")


class TrapList(list):
    """A collection subclass that cannot be accepted through duck typing."""

    def __iter__(self):
        """Fail if untrusted collection iteration is reached."""
        raise AssertionError("list iteration invoked")


class TrapArtifact(ArtifactReference):
    """A typed-reference subclass with an unsafe serialization override."""

    def to_dict(self):
        """Fail if a serialization override is trusted."""
        raise AssertionError("reference serializer invoked")


class TrapRecord(RecordReference):
    """A record subclass whose inherited shape does not authorize serialization."""

    def to_dict(self):
        """Fail if a subclass reference serializer is consulted."""
        raise AssertionError("record serializer invoked")


class TrapFile(WorkProductFile):
    """A file subclass must fail before its apparent wire representation is read."""

    def to_dict(self):
        """Fail if a subclass bundle serializer is consulted."""
        raise AssertionError("file serializer invoked")


class TrapDimension(Dimension):
    """A dimension subclass must not supply its own reconstruction behavior."""

    def to_dict(self):
        """Fail if a subclass dimension serializer is consulted."""
        raise AssertionError("dimension serializer invoked")


class SerializationLookalike:
    """A non-domain object cannot enter typed positions through a to_dict method."""

    def to_dict(self):
        """Fail if duck-typed serialization is attempted."""
        raise AssertionError("lookalike serializer invoked")


class TrapTuple(tuple):
    """An iterable tuple subclass is outside the ordinary constructor collection contract."""

    def __iter__(self):
        """Fail if iteration happens before exact-type rejection."""
        raise AssertionError("tuple iteration invoked")


class TrapRelease(ToolRelease):
    """An inherited receiver whose override must not be called by public boundaries."""

    def to_dict(self, **kwargs):
        """Fail if an inherited boundary dispatches to this override."""
        raise AssertionError("release override invoked")


class IntAlias(int):
    """An integer alias is deliberately outside the exact scalar contract."""


class StrAlias(str):
    """A string alias is deliberately outside the exact scalar contract."""


def hostile_metaclasses(calls):
    """Return separate equality/hash traps and an unhashable variant, recording into calls."""
    class EqualityTrap(type):
        """Expose class membership comparisons without disabling ordinary class hashing."""

        def __eq__(cls, other):
            """Record and fail any equality comparison involving the caller's class."""
            calls.append("equality")
            raise AssertionError("metaclass equality invoked")

        __hash__ = type.__hash__

    class HashTrap(type):
        """Expose class-key lookups independently of equality comparisons."""

        def __hash__(cls):
            """Record and fail any attempt to hash the caller's class."""
            calls.append("hash")
            raise AssertionError("metaclass hashing invoked")

    class UnhashableTrap(EqualityTrap):
        """Require inert rejection even when the caller's class cannot be hashed."""

        __hash__ = None

    return (("equality", EqualityTrap), ("hash", HashTrap), ("unhashable", UnhashableTrap))


class ToolReleaseTests(unittest.TestCase):
    """Verify complete passive declarations without opening a store or resolving any links."""

    def assert_invalid(self, value, pattern=None):
        """Check a raw dictionary failure, optionally requiring a meaningful diagnostic."""
        with self.assertRaisesRegex(ToolReleaseValidationError, pattern or "."):
            decode_content(value)

    def assert_inert_rejection(self, consume, calls, operations=()):
        """Require validation failure and zero hook calls before any protected operation."""
        with ExitStack() as stack:
            for module, name in operations:
                stack.enter_context(patch.object(module, name, side_effect=AssertionError("protected work reached")))
            with self.assertRaises(ToolReleaseValidationError):
                calls.clear()
                consume()
            self.assertEqual(calls, [])

    def test_complete_variants_and_actual_statements(self):
        """All origins and invocation kinds retain scientific, provenance and authority detail."""
        for origin in ("bundled", "researcher_supplied", "research_generated"):
            for kind in ("local_program", "local_callable", "remote_service", "composite_workflow"):
                expected = wire(origin, kind)
                with self.subTest(origin=origin, kind=kind):
                    release = ToolRelease(**constructor_sections(expected))
                    self.assertEqual(release.to_dict(), expected)
                    self.assertEqual(release.tool_id, "affine_tool")
                    self.assertEqual(release.release_id, expected["release_id"])
                    self.assertEqual(dumps_content(release), canonical(expected))
                    self.assertEqual(decode_content(expected), release)
                    self.assertEqual(loads_content(canonical(expected)), release)
                    self.assertEqual(loads_content(canonical(expected).encode("utf-8")), release)
                    for name, statements in SCIENCE.items():
                        self.assertEqual(release.to_dict()["scientific_meaning"][name]["value"], statements)
                    self.assertEqual(expected["identity"]["provenance_records"]["value"][0]["revision"], 3)
                    self.assertIn("liability", expected["resources_recovery"]["recovery"]["uncertain_completion"]["value"])
                    self.assertIn("scientific", expected["evidence_limitations"]["limitations"]["value"][0])
        remote = wire(kind="remote_service")
        self.assertEqual(remote["identity"]["implementation"]["reported_version"]["value"], "example-1")
        self.assertEqual(remote["identity"]["access"]["status"], "unavailable")
        self.assertEqual(remote["identity"]["license"]["state"], "unavailable")
        self.assertIn("provider", remote["reproducibility"]["replay_limits"]["value"][0])

    def test_mapping_order_and_alternate_json_encodings(self):
        """Mapping order, legal whitespace and equivalent Unicode escaping have identical identities."""
        expected = wire()

        def reversed_maps(value):
            """Reverse every independent mapping order while retaining array order."""
            if type(value) is dict:
                return {key: reversed_maps(child) for key, child in reversed(list(value.items()))}
            if type(value) is list:
                return [reversed_maps(child) for child in value]
            return value
        alternate = reversed_maps(expected)
        text = json.dumps(alternate, ensure_ascii=False, indent=3)
        self.assertEqual(dumps_content(loads_content(text)), canonical(expected))
        self.assertEqual(loads_content(text.encode("utf-8")), decode_content(expected))
        self.assertEqual(decode_content(alternate), decode_content(expected))
        escaped = canonical(expected).replace("Affine", "\\u0041ffine").replace("/", "\\/")
        self.assertEqual(loads_content(escaped), decode_content(expected))
        signed_zero = canonical(expected).replace('"value":0', '"value":-0')
        self.assertEqual(loads_content(signed_zero), decode_content(expected))

    def test_changed_content_order_and_authored_whitespace_change_identity(self):
        """Each subordinate hash uses exactly its declared preimage; release hashing includes all facts."""
        original = wire()
        edits = [(("identity", "readme"), "new README"), (("identity", "release_label"), known(" v1  ")),
                 (("scientific_meaning", "units"), known(["metres", "seconds"])),
                 (("invocation", "adapter", "entry_point"), missing(reason="Not yet supplied.")),
                 (("invocation", "configuration"), missing("unavailable", "Configuration was not obtainable."))]
        for path, value in edits:
            doc = copy.deepcopy(original)
            at(doc, path[:-1])[path[-1]] = value
            expected = rehash(doc)
            release = ToolRelease(**constructor_sections(expected))
            self.assertEqual(release.to_dict(), expected)
            self.assertNotEqual(release.release_id, original["release_id"])
            self.assertEqual(expected["adapter_identity"] == original["adapter_identity"], path[:2] != ("invocation", "adapter"))
            self.assertEqual(expected["configuration_identity"] == original["configuration_identity"], path != ("invocation", "configuration"))
        doc = copy.deepcopy(original)
        doc["invocation"]["configuration"]["value"].reverse()
        self.assertNotEqual(rehash(doc)["release_id"], original["release_id"])
        doc = copy.deepcopy(original)
        doc["identity"]["provenance_records"]["value"][0]["revision"] = 4
        self.assertNotEqual(rehash(doc)["release_id"], original["release_id"])

    def test_explicit_missing_empty_zero_and_no_supplied_dependencies(self):
        """Missing information is not silently replaced with empty values or inferred dates."""
        for state in ("unknown", "unavailable"):
            doc = wire()
            doc["identity"]["declared_at"] = missing(state)
            doc["identity"]["implementation"].update(observability=state, artifacts=missing(state))
            doc["invocation"]["adapter"].update(files=missing(state), entry_file=missing(state))
            doc["invocation"]["configuration"] = missing(state)
            doc["effects_authority"]["model_activity"]["state"] = "unobserved"
            doc["effects_authority"]["delegated_activity"]["state"] = "unknown"
            for bound in doc["resources_recovery"]["bounds"]:
                bound.update(quantity=missing(state), mode="unknown")
            expected = rehash(doc)
            self.assertEqual(ToolRelease(**constructor_sections(expected)).to_dict(), expected)
        doc = wire()
        doc["identity"]["declared_at"] = known("")
        doc["invocation"]["adapter"]["entry_file"] = known(None)
        doc["invocation"]["outputs"]["fields"] = known([])
        doc["scientific_meaning"]["approximations"] = known([])
        for bound in doc["resources_recovery"]["bounds"]:
            bound["quantity"] = known(0)
        release = decode_content(rehash(doc))
        self.assertEqual(release.to_dict()["reproducibility"]["dependencies"], known([]))
        self.assertEqual(release.to_dict()["invocation"]["configuration"]["value"][1]["value"], "")
        self.assertEqual(release.to_dict()["resources_recovery"]["bounds"][0]["quantity"], known(0))

    def test_mutation_isolation_frozen_and_unhashable(self):
        """Construction and emitted trees are detached, frozen snapshots are deliberately unhashable."""
        expected = wire()
        inputs = constructor_sections(expected)
        release = ToolRelease(**inputs)
        inputs["identity"]["readme"] = "changed"
        object.__setattr__(inputs["invocation"]["adapter"]["files"]["value"][0].artifact, "size", 17)
        output = release.to_dict()
        output["scientific_meaning"]["units"]["value"].append("changed")
        self.assertEqual(release.to_dict(), expected)
        with self.assertRaises(FrozenInstanceError):
            release._json = "{}"
        with self.assertRaises(TypeError):
            hash(release)
        self.assertNotEqual(release, object())

    def test_closed_fields_at_every_populated_object(self):
        """Every fixed schema object, declaration and reference rejects absent and extra fields."""
        original = wire(kind="composite_workflow")
        original["effects_authority"]["credential_references"] = known([{"credential_id": "access", "purpose": "Separate later authorization."}])
        original = rehash(original)

        def paths(value, path=()):
            """Enumerate existing dictionaries in an independent complete wire fixture."""
            if type(value) is dict:
                yield path
                for key, child in value.items():
                    yield from paths(child, path + (key,))
            elif type(value) is list:
                for index, child in enumerate(value):
                    yield from paths(child, path + (index,))
        for path in paths(original):
            for mode in ("extra", "missing"):
                doc = copy.deepcopy(original)
                target = at(doc, path)
                if mode == "extra":
                    target["unexpected"] = "no extension fields"
                else:
                    name = next(iter(target))
                    if path == () and name == "format":
                        name = "version"
                    del target[name]
                with self.subTest(path=path, mode=mode):
                    self.assert_invalid(doc)

    def test_headers_duplicates_and_syntax(self):
        """Missing discriminator has its dedicated error; malformed JSON and unsupported headers fail."""
        for call in (lambda: decode_content({}), lambda: loads_content("{}")):
            with self.assertRaises(NotTypedContentError):
                call()
        for field, value in (("format", "other"), ("version", 2), ("kind", "tool_assessment")):
            doc = wire()
            doc[field] = value
            self.assert_invalid(rehash(doc))
        text = canonical(wire())
        for malformed in ('{"a":1,"a":2}', text.replace('"state":"known"', '"state":"known","state":"known"', 1),
                          text.replace('"tool_id":', '"tool_id":"first","tool_id":', 1),
                          '{"\\u0061":0,"a":0}', '[]', '{', '[0,]', '{"x":0,}', 'null null',
                          '"unterminated', '{"x" 0}', '[01]', '[1.0]', '[1e0]', '[true]', '[false]',
                          '[NaN]', '[Infinity]', '[-Infinity]', '[-1]', '[-]', '[-01]',
                          '[9223372036854775808]', '[' + '9' * 5000 + ']', '[0] junk'):
            with self.subTest(input=malformed[:40]), self.assertRaises(ToolReleaseValidationError):
                loads_content(malformed)

    def test_unicode_controls_supplementary_and_invalid_surrogates(self):
        """Decoded scalar values and all escape forms retain exact authored characters."""
        doc = wire()
        authored = ' \t\b\f\n\r\x00\x1f"\\{}[] / α é 😀 \x7f '
        doc["identity"]["release_label"] = known(authored)
        expected = rehash(doc)
        for text in (canonical(expected), json.dumps(expected, ensure_ascii=False)):
            self.assertEqual(loads_content(text).to_dict(), expected)
            self.assertEqual(loads_content(text.encode("utf-8")).to_dict(), expected)
        for value in ('"\\ud800"', '"\\udc00"', '"\\ud800x"', '"\\ud800\\u0041"', '"\\u12zz"', '"\\x20"', '"\n"', '"\ud800"', b'"\xff"'):
            with self.assertRaises(ToolReleaseValidationError):
                loads_content(value)
        doc["identity"]["readme"] = "\ud800"
        self.assert_invalid(doc)

    def test_exact_scalars_collections_and_constructor_reference_types(self):
        """Aliases, lookalikes, unordered inputs and wire objects in typed slots never pass."""
        for value in (True, False, 1.0, IntAlias(1), -1, 2**63, object()):
            doc = wire()
            doc["resources_recovery"]["bounds"][0]["quantity"] = known(value)
            self.assert_invalid(doc)
        for value in (StrAlias("ok"), None, 7):
            doc = wire()
            doc["identity"]["readme"] = value
            self.assert_invalid(doc)
        for value in (TrapDict(), TrapList(), {"a"}, iter(["a"]), ("a",)):
            doc = wire()
            doc["identity"]["supplier"]["value"] = value
            self.assert_invalid(doc)
        inputs = constructor_sections()
        inputs["identity"]["supplier"]["value"] = ("A", "B")
        self.assertEqual(ToolRelease(**inputs).to_dict()["identity"]["supplier"]["value"], ["A", "B"])
        for path in RECORD_SLOTS + FILE_SLOTS:
            raw = at(wire(), path)
            if raw["value"]:
                inputs = constructor_sections()
                at(inputs, path)["value"] = raw["value"]
                with self.assertRaises(ToolReleaseValidationError):
                    ToolRelease(**inputs)
        inputs = constructor_sections()
        inputs["resources_recovery"]["bounds"][0]["dimension"] = wire()["resources_recovery"]["bounds"][0]["dimension"]
        with self.assertRaises(ToolReleaseValidationError):
            ToolRelease(**inputs)
        inputs = constructor_sections()
        inputs["evidence_limitations"]["self_tests"]["value"] = [TrapArtifact(**artifact())]
        with self.assertRaises(ToolReleaseValidationError):
            ToolRelease(**inputs)
        with self.assertRaises(ToolReleaseValidationError):
            decode_content(TrapDict(wire()))

    def test_bypass_mutated_typed_objects_and_missing_attributes(self):
        """Raw fields are read and revalidated; missing slots and cached serialization cannot rescue forgeries."""
        slots = ((ArtifactReference, ("evidence_limitations", "self_tests", "value"), "size", True),
                 (RecordReference, ("identity", "provenance_records", "value"), "revision", 0),
                 (WorkProductFile, ("invocation", "adapter", "files", "value"), "path", "../unsafe"))
        for cls, path, field, bad in slots:
            for absent in (False, True):
                inputs = constructor_sections()
                item = at(inputs, path)[0]
                if absent:
                    object.__delattr__(item, field)
                else:
                    object.__setattr__(item, field, bad)
                with self.subTest(cls=cls, absent=absent), self.assertRaises(ToolReleaseValidationError):
                    ToolRelease(**inputs)
        for field, value in (("scale", True), ("unit", "wrong"), ("currency", "USD"), ("kind", "fake")):
            inputs = constructor_sections()
            object.__setattr__(inputs["resources_recovery"]["bounds"][0]["dimension"], field, value)
            with self.assertRaises(ToolReleaseValidationError):
                ToolRelease(**inputs)
        inputs = constructor_sections()
        object.__delattr__(inputs["resources_recovery"]["bounds"][0]["dimension"], "currency")
        with self.assertRaises(ToolReleaseValidationError):
            ToolRelease(**inputs)
        inputs = constructor_sections()
        with patch.object(ArtifactReference, "to_dict", side_effect=AssertionError("serializer")), patch.object(RecordReference, "to_dict", side_effect=AssertionError("serializer")), patch.object(Dimension, "to_dict", side_effect=AssertionError("serializer")), patch.object(WorkProductFile, "to_dict", side_effect=AssertionError("serializer")):
            self.assertEqual(ToolRelease(**inputs).to_dict(), wire())

    def test_metaclass_hooks_in_scalar_and_container_trees(self):
        """Every tree boundary rejects hostile scalar/container aliases before hooks or copying."""
        cases = (
            ("readme", str, ("identity", "readme")),
            ("integer", int, ("resources_recovery", "bounds", 0, "quantity", "value")),
            ("mapping", TrapDict, ("identity", "access")),
            ("list", TrapList, ("identity", "supplier", "value")),
            ("tuple", TrapTuple, ("identity", "supplier", "value")),
        )
        operations = ((product, "detached"), (codec.json, "dumps"))
        calls = []
        for hook, metaclass in hostile_metaclasses(calls):
            for label, base, path in cases:
                hostile = metaclass("HostileValue", (base,), {
                    "__doc__": "A scalar or container alias with caller-controlled class hooks.",
                })
                for boundary in ("decode_content", "from_dict", "constructor"):
                    tree = constructor_sections() if boundary == "constructor" else wire()
                    at(tree, path[:-1])[path[-1]] = hostile(at(tree, path))
                    if boundary == "constructor":
                        consume = lambda: ToolRelease(**tree)
                    elif boundary == "from_dict":
                        consume = lambda: ToolRelease.from_dict(tree)
                    else:
                        consume = lambda: decode_content(tree)
                    with self.subTest(hook=hook, slot=label, boundary=boundary):
                        self.assert_inert_rejection(consume, calls, operations)

    def test_metaclass_hooks_in_all_typed_positions(self):
        """Typed subclasses fail inertly at all tree consumers, including serializer traps."""
        cases = (
            ("artifact", TrapArtifact, ("evidence_limitations", "self_tests", "value", 0)),
            ("record", TrapRecord, ("identity", "provenance_records", "value", 0)),
            ("file", TrapFile, ("invocation", "adapter", "files", "value", 0)),
            ("dimension", TrapDimension, ("resources_recovery", "bounds", 0, "dimension")),
        )
        operations = ((product, "detached"), (codec.json, "dumps"))
        calls = []
        for hook, metaclass in hostile_metaclasses(calls):
            for label, base, path in cases:
                hostile = metaclass("HostilePin", (base,), {
                    "__doc__": "A typed pin alias whose metaclass and serializer must remain unused.",
                })
                for boundary in ("decode_content", "from_dict", "constructor"):
                    inputs = constructor_sections()
                    tree = inputs if boundary == "constructor" else wire()
                    bad = hostile(**vars(at(inputs, path)))
                    at(tree, path[:-1])[path[-1]] = bad
                    if boundary == "constructor":
                        consume = lambda: ToolRelease(**tree)
                    elif boundary == "from_dict":
                        consume = lambda: ToolRelease.from_dict(tree)
                    else:
                        consume = lambda: decode_content(tree)
                    with self.subTest(hook=hook, slot=label, boundary=boundary):
                        self.assert_inert_rejection(consume, calls, operations)

    def test_metaclass_hooks_in_bypass_mutated_reference_fields(self):
        """Virtual traversal of an exact reference rejects hostile retained scalars before copying."""
        calls = []
        operations = ((product, "detached"), (codec.json, "dumps"))
        for hook, metaclass in hostile_metaclasses(calls):
            for field, base in (("digest", str), ("size", int)):
                inputs = constructor_sections()
                reference = inputs["evidence_limitations"]["self_tests"]["value"][0]
                hostile = metaclass("HostileScalar", (base,), {
                    "__doc__": "A forged retained scalar whose class hooks must never run.",
                })
                object.__setattr__(reference, field, hostile(getattr(reference, field)))
                with self.subTest(hook=hook, field=field):
                    self.assert_inert_rejection(lambda: ToolRelease(**inputs), calls, operations)

    def test_metaclass_hooks_at_external_json_boundary(self):
        """Hostile str/bytes containing valid JSON fail before lexical scanning or parsing."""
        text = canonical(wire())
        calls = []
        operations = ((codec, "lexical_preflight"), (codec.json, "loads"))
        for hook, metaclass in hostile_metaclasses(calls):
            for label, base, ordinary in (("text", str, text), ("bytes", bytes, text.encode("utf-8"))):
                hostile = metaclass("HostileJSON", (base,), {
                    "__doc__": "An external JSON alias that must be rejected before reading its content.",
                })
                data = hostile(ordinary)
                with self.subTest(hook=hook, input=label):
                    self.assert_inert_rejection(lambda: loads_content(data), calls, operations)

    def test_metaclass_hooks_in_retained_json_at_every_consumer(self):
        """All retained consumers, including both equality directions, reject hostile text inertly."""
        text = canonical(wire())
        valid = loads_content(text)
        scan = codec.lexical_preflight

        def scan_exact_text(data, limits):
            """Allow the valid equality operand's scan but fail if hostile input reaches scanning."""
            if type(data) is not str:
                raise AssertionError("hostile input reached lexical scan")
            return scan(data, limits)

        calls = []
        for hook, metaclass in hostile_metaclasses(calls):
            hostile = metaclass("HostileSnapshot", (str,), {
                "__doc__": "A retained text alias that must fail before any scan or comparison.",
            })
            forged = object.__new__(ToolRelease)
            object.__setattr__(forged, "_json", hostile(text))
            consumers = (
                ("to_dict", lambda: forged.to_dict()),
                ("dumps_content", lambda: dumps_content(forged)),
                ("tool_id", lambda: forged.tool_id),
                ("release_id", lambda: forged.release_id),
                ("equality_left", lambda: forged == valid),
                ("equality_right", lambda: valid == forged),
            )
            for boundary, consume in consumers:
                with self.subTest(hook=hook, boundary=boundary):
                    with patch.object(codec, "lexical_preflight", side_effect=scan_exact_text):
                        self.assert_inert_rejection(consume, calls)

    def test_all_typed_subclasses_and_serialization_lookalikes(self):
        """Every typed position rejects subclasses and lookalikes without invoking hooks."""
        candidates = (
            (("identity", "provenance_records", "value", 0), TrapRecord(**record("reported_provenance", "source"))),
            (("invocation", "adapter", "files", "value", 0), TrapFile("src/adapter.py", ArtifactReference(**artifact()))),
            (("evidence_limitations", "self_tests", "value", 0), TrapArtifact(**artifact())),
            (("resources_recovery", "bounds", 0, "dimension"), TrapDimension("dim_local_time", "local_time", "nanosecond", None, 1)),
        )
        for path, subclass in candidates:
            for bad in (subclass, SerializationLookalike()):
                inputs = constructor_sections()
                at(inputs, path[:-1])[path[-1]] = bad
                with self.subTest(path=path, type=type(bad)), self.assertRaises(ToolReleaseValidationError):
                    ToolRelease(**inputs)
        inputs = constructor_sections()
        inputs["identity"]["supplier"]["value"] = TrapTuple(("author",))
        with self.assertRaises(ToolReleaseValidationError):
            ToolRelease(**inputs)

    def test_reference_roles_kinds_repetitions_and_cross_section_conflicts(self):
        """Reported roles are mandatory, repetitions stay ordered and conflicting pins fail even rehashed."""
        for path in RECORD_SLOTS:
            doc = wire(kind="composite_workflow")
            fact = at(doc, path)
            if not fact["value"]:
                fact["value"] = [record("build_dependency", "source")]
            for field, value in (("relationship", "wrong_role"), ("target_kind", None)):
                changed = copy.deepcopy(doc)
                at(changed, path)["value"][0][field] = value
                self.assert_invalid(rehash(changed))
        for path in (("evidence_limitations", "evidence"), ("effects_authority", "child_tools"), ("identity", "implementation", "source_records")):
            doc = wire(kind="composite_workflow")
            at(doc, path)["value"][0]["target_kind"] = "project"
            self.assert_invalid(rehash(doc))
        doc = wire()
        pin = doc["identity"]["provenance_records"]["value"][0]
        doc["identity"]["provenance_records"]["value"] = [pin, pin, pin]
        self.assertEqual(decode_content(rehash(doc)).to_dict()["identity"]["provenance_records"]["value"], [pin] * 3)
        doc["reproducibility"]["dependency_records"] = known([{**pin, "relationship": "build_dependency", "target_kind": "source"}])
        self.assert_invalid(rehash(doc), "conflicting target kinds")
        doc = wire()
        pin = doc["identity"]["implementation"]["artifacts"]["value"][0]["artifact"]
        doc["reproducibility"]["dependency_artifacts"] = known([{**pin, "size": pin["size"] + 1}])
        self.assert_invalid(rehash(doc), "conflicting sizes")

    def test_bundle_paths_aliases_collisions_and_exact_entry(self):
        """Bundle inventories are separately portable; descriptive scopes remain inert unrestricted text."""
        for paths in (("../escape",), ("/absolute",), ("CON",), ("a\\b",), ("a.",), ("a//b",),
                      ("A.py", "a.py"), ("a", "a/b"), ("a/b", "a"), ("Dir/a", "dir/b"), ("Ａ", "A")):
            doc = wire()
            doc["invocation"]["adapter"]["files"] = known([{"path": path, "artifact": artifact()} for path in paths])
            doc["invocation"]["adapter"]["entry_file"] = known(None)
            self.assert_invalid(rehash(doc))
        for entry in ("SRC/adapter.py", "missing.py", "../bad"):
            doc = wire()
            doc["invocation"]["adapter"]["entry_file"] = known(entry)
            self.assert_invalid(rehash(doc))
        doc = wire()
        doc["invocation"]["adapter"]["files"] = missing()
        self.assert_invalid(rehash(doc), "entry_file")
        doc = wire()
        doc["invocation"]["adapter"]["files"]["value"][0]["path"] = "src/affine.py"
        doc["invocation"]["adapter"]["entry_file"] = known("src/affine.py")
        self.assertEqual(decode_content(rehash(doc)).to_dict(), rehash(doc))

    def test_factual_state_combinations_and_declared_dates(self):
        """Only optional entry paths permit known null; missing facts require a nonblank reason."""
        bad = ({"state": "known", "value": None, "reason": None}, {"state": "known", "value": "", "reason": "why"},
               {"state": "unknown", "value": "", "reason": "why"}, {"state": "unavailable", "value": None, "reason": " "},
               {"state": "missing", "value": None, "reason": "why"})
        for value in bad:
            doc = wire()
            doc["identity"]["release_label"] = value
            self.assert_invalid(rehash(doc))
        for value in (" ", "2026-02-30T00:00:00Z", "2026-01-01", "2026-01-01T00:00:00+00:00"):
            doc = wire()
            doc["identity"]["declared_at"] = known(value)
            self.assert_invalid(rehash(doc))
        doc = wire()
        doc["identity"]["declared_at"] = known("2026-01-01T00:00:00.12Z")
        self.assertEqual(decode_content(rehash(doc)).to_dict()["identity"]["declared_at"]["value"], "2026-01-01T00:00:00.12Z")

    def test_remote_pins_version_observability_and_replay_limitations(self):
        """Remote declaration hashes never stand in for a running implementation pin."""
        for change in ("pinned", "artifacts", "implementation_limits", "replay_limits"):
            doc = wire(kind="remote_service")
            implementation = doc["identity"]["implementation"]
            if change == "pinned":
                implementation["observability"] = "pinned_local"
            elif change == "artifacts":
                implementation["artifacts"] = sections()["identity"]["implementation"]["artifacts"]
            elif change == "implementation_limits":
                implementation["limitations"] = known([])
            else:
                doc["reproducibility"]["replay_limits"] = known([])
            self.assert_invalid(rehash(doc))
        for observation, version, files in (("pinned_local", known("v"), known([])), ("reported_version_only", known(" "), known([])), ("reported_version_only", missing(), known([]))):
            doc = wire()
            doc["identity"]["implementation"].update(observability=observation, reported_version=version, artifacts=files)
            self.assert_invalid(rehash(doc))
        doc = wire(kind="remote_service")
        doc["identity"]["implementation"].update(observability="reported_version_only", artifacts=known([]), limitations=missing())
        doc["reproducibility"]["replay_limits"] = missing("unavailable")
        self.assertEqual(decode_content(rehash(doc)).to_dict(), rehash(doc))

    def test_activity_uniqueness_and_semantics_before_hash_mismatch(self):
        """Contradictory activity and duplicate named slots fail before stale or recomputed hashes."""
        cases = (("effects_authority", "model_activity", "providers"), ("effects_authority", "delegated_activity", "runtime"))
        for path in cases:
            doc = wire()
            at(doc, path[:-1])[path[-1]] = known(["provider"] if path[-1] == "providers" else "runtime")
            for candidate in (doc, rehash(doc)):
                self.assert_invalid(candidate, "none requires")
        doc = wire(kind="composite_workflow")
        doc["effects_authority"]["model_activity"]["description"] = known(" ")
        self.assert_invalid(doc, "declared activity")
        for path in (("invocation", "configuration"), ("invocation", "inputs", "fields"), ("invocation", "outputs", "fields"), ("effects_authority", "credential_references")):
            doc = wire(kind="remote_service")
            at(doc, path)["value"].append(at(doc, path)["value"][0])
            self.assert_invalid(rehash(doc), "duplicate")
        doc = wire()
        doc["resources_recovery"]["bounds"][3]["quantity"] = known(20)
        self.assertEqual(decode_content(rehash(doc)).to_dict(), rehash(doc))

    def test_bounds_dimensions_currencies_and_unverified_hard_claims(self):
        """All required maxima, exact units and currencies remain declarations with visible uncertainty."""
        for updates in ({"quantity": missing()}, {"enforceability": "not_enforceable"}, {"enforceability": "reported_enforceable"}, {"unit": "second"}, {"dimension": None}):
            doc = wire()
            doc["resources_recovery"]["bounds"][0].update(updates)
            self.assert_invalid(rehash(doc))
        for mode in ("missing", "duplicate", "extra_dimension"):
            doc = wire()
            bounds = doc["resources_recovery"]["bounds"]
            if mode == "missing":
                bounds.pop()
            elif mode == "duplicate":
                bounds.append(copy.deepcopy(bounds[0]))
            else:
                bounds[-1]["dimension"] = bounds[0]["dimension"]
            self.assert_invalid(rehash(doc))
        doc = wire()
        monetary = {"name": "monetary", "dimension": {"dimension_id": "usd", "kind": "monetary", "unit": "currency_quantum", "currency": "USD", "scale": 100},
                    "unit": "currency_quantum", "quantity": known(500), "mode": "monitored_target", "enforceability": "not_enforceable", "mechanism": missing(), "limitations": known(["No enforceable service cap."])}
        doc["resources_recovery"]["bounds"].append(monetary)
        expected = rehash(doc)
        self.assertEqual(ToolRelease(**constructor_sections(expected)).to_dict(), expected)
        doc["resources_recovery"]["bounds"].append({**copy.deepcopy(monetary), "dimension": {**monetary["dimension"], "dimension_id": "usd2"}})
        self.assert_invalid(rehash(doc), "duplicate currency")
        doc = wire()
        doc["resources_recovery"]["bounds"][1]["dimension"]["dimension_id"] = doc["resources_recovery"]["bounds"][0]["dimension"]["dimension_id"]
        self.assert_invalid(rehash(doc), "conflicting definitions")
        doc = wire()
        doc["resources_recovery"]["bounds"][0].update(enforceability="reported_enforceable", mechanism=known("Supplier claims a watchdog."))
        doc["resources_recovery"]["bounds"].reverse()
        self.assertEqual(decode_content(rehash(doc)).to_dict(), rehash(doc))

    def test_retained_forgery_every_public_consumption_boundary(self):
        """Missing, stale, noncanonical and rehashed contradictory snapshots fail at every consumer."""
        valid = decode_content(wire())
        stale = wire()
        stale["identity"]["display_name"] = "changed"
        contradiction = wire()
        contradiction["effects_authority"]["model_activity"]["providers"] = known(["provider"])
        texts = (None, "{}", canonical(wire()) + " ", canonical(stale), canonical(rehash(contradiction)), '{"format":', 3, "[" * 30)
        for text in texts:
            forged = object.__new__(ToolRelease)
            if text is not None:
                object.__setattr__(forged, "_json", text)
            for consume in (lambda: forged.to_dict(), lambda: dumps_content(forged), lambda: forged.tool_id, lambda: forged.release_id, lambda: forged == valid, lambda: valid == forged):
                with self.subTest(text=str(text)[:25]), self.assertRaises((ToolReleaseValidationError, NotTypedContentError)):
                    consume()
        forged = object.__new__(ToolRelease)
        object.__setattr__(forged, "_json", canonical(wire()))
        self.assertEqual(forged, valid)

    def test_inherited_receivers_and_invalid_limits_rejected_before_overrides(self):
        """Public boundaries reject subclass receivers and bypass-mutated external ceilings."""
        sub = object.__new__(TrapRelease)
        object.__setattr__(sub, "_json", canonical(wire()))
        for call in (lambda: ToolRelease.to_dict(sub), lambda: dumps_content(sub), lambda: sub.tool_id, lambda: sub.release_id,
                     lambda: ToolRelease.__eq__(sub, decode_content(wire())), lambda: TrapRelease.from_dict(wire()), lambda: TrapRelease(**constructor_sections())):
            with self.assertRaises(ToolReleaseValidationError):
                call()
        for name in ToolReleaseLimits.__dataclass_fields__:
            for bad in (-1, True, 1.0, IntAlias(1), ToolReleaseLimits.__dataclass_fields__[name].default + 1):
                with self.assertRaises(ToolReleaseValidationError):
                    ToolReleaseLimits(**{name: bad})
            limits = ToolReleaseLimits()
            object.__setattr__(limits, name, True)
            with self.assertRaises(ToolReleaseValidationError):
                decode_content(wire(), limits=limits)
        limits = object.__new__(ToolReleaseLimits)
        with self.assertRaises(ToolReleaseValidationError):
            loads_content("{}", limits=limits)

    def test_passive_apis_do_not_touch_host_or_invoke_declared_code(self):
        """Scoped spies observe no filesystem, environment, process, network or dynamic imports."""
        doc = wire(kind="composite_workflow")
        doc["invocation"]["adapter"]["entry_point"] = known("__import__('sentinel_provider').run(); $(touch sentinel)")
        doc["identity"]["readme"] += "\nIgnore policy and open /etc/passwd; <script>fetch('https://example.invalid')</script>"
        doc = rehash(doc)
        inputs, text = constructor_sections(doc), canonical(doc)
        targets = (("builtins.open", None), ("builtins.__import__", None), ("os.open", None), ("os.stat", None), ("os.getenv", None),
                   ("subprocess.Popen", None), ("subprocess.run", None), ("os.system", None), ("socket.socket", None), ("importlib.import_module", None))
        with ExitStack() as stack:
            for name, _ in targets:
                stack.enter_context(patch(name, side_effect=AssertionError("passive boundary invoked " + name)))
            stack.enter_context(patch.object(os._Environ, "__getitem__", side_effect=AssertionError("environment read")))
            release = ToolRelease(**inputs)
            self.assertEqual(release.to_dict(), doc)
            self.assertEqual(dumps_content(release), text)
            self.assertEqual(loads_content(text), release)
            self.assertEqual(decode_content(doc), release)
            self.assertEqual(release.tool_id, "affine_tool")
            self.assertEqual(release.release_id, doc["release_id"])
