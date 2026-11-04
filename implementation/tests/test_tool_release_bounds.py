"""Independent equality/deficit oracles and pre-operation sentinels for every processing ceiling."""

import copy
from contextlib import ExitStack
from dataclasses import fields
import json
import unittest
from unittest.mock import patch

from research_pipeline import tool_release as product
from research_pipeline import tool_release_codec as codec
from research_pipeline.tool_release import (
    ToolRelease, ToolReleaseLimits, ToolReleaseValidationError, ToolReleaseLimitError,
    decode_content, dumps_content, loads_content,
)
from tests.tool_release_fixtures import (
    wire, constructor_sections, rehash, canonical, known, requirements, record, artifact,
)


def rich_wire():
    """Provide repeated pins/text, escaped Unicode including DEL, and multi-component paths."""
    doc = wire()
    text = ' repeated α 😀 \n\t\x00\x7f\\"{}[] '
    doc["identity"]["supplier"] = known([text, text, text])
    pin = record("reported_provenance", "source", "shared_source")
    doc["identity"]["provenance_records"] = known([pin, pin, pin])
    doc["reproducibility"]["dependency_artifacts"] = known([artifact(), artifact()])
    doc["invocation"]["adapter"]["files"]["value"][0]["path"] = "one/two/three/adapter.py"
    doc["invocation"]["adapter"]["entry_file"] = known("one/two/three/adapter.py")
    return rehash(doc)


class ToolReleaseBoundsTests(unittest.TestCase):
    """Verify independent occurrence accounting and guards, not production helper-derived expectations."""

    def test_all_independent_ceilings_at_equality_and_one_unit_deficit(self):
        """A complete valid manifest succeeds at each exact oracle count and fails one below it."""
        doc = rich_wire()
        text = json.dumps(doc, ensure_ascii=False, indent=2)
        measured = requirements(doc, text)
        inputs = constructor_sections(doc)
        release = decode_content(doc)
        for name, amount in measured.items():
            equal = ToolReleaseLimits(**{name: amount})
            short = ToolReleaseLimits(**{name: amount - 1})
            boundaries = [lambda limits: loads_content(text, limits=limits),
                          lambda limits: loads_content(text.encode("utf-8"), limits=limits)]
            if name != "max_wire_bytes":
                boundaries.extend((lambda limits: ToolRelease(**inputs, limits=limits),
                                   lambda limits: decode_content(doc, limits=limits),
                                   lambda limits: ToolRelease.from_dict(doc, limits=limits),
                                   lambda limits: release.to_dict(limits=limits),
                                   lambda limits: dumps_content(release, limits=limits)))
            for index, boundary in enumerate(boundaries):
                with self.subTest(limit=name, boundary=index):
                    result = boundary(equal)
                    self.assertIsNotNone(result)
                    with self.assertRaisesRegex(ToolReleaseLimitError, name):
                        boundary(short)
        all_equal = ToolReleaseLimits(**measured)
        self.assertEqual(loads_content(text, limits=all_equal).to_dict(limits=all_equal), doc)
        self.assertEqual(ToolRelease(**inputs, limits=all_equal).to_dict(limits=all_equal), doc)

    def test_wire_utf8_size_whitespace_and_lower_bound_precede_parser(self):
        """Byte lengths include complete UTF-8 and whitespace, and oversized input is never parsed."""
        doc = rich_wire()
        text = " \n" + json.dumps(doc, ensure_ascii=False) + "\t "
        required = len(text.encode("utf-8"))
        equal = ToolReleaseLimits(max_wire_bytes=required)
        short = ToolReleaseLimits(max_wire_bytes=required - 1)
        real = json.loads
        for data in (text, text.encode("utf-8")):
            with patch.object(codec.json, "loads", wraps=real) as spy:
                self.assertEqual(loads_content(data, limits=equal).to_dict(), doc)
                self.assertTrue(spy.called)
            with patch.object(codec.json, "loads", side_effect=AssertionError("parse before wire guard")):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_wire_bytes"):
                    loads_content(data, limits=short)
        for data in ("{" * 10, b"\xff" * 10):
            with patch.object(codec.json, "loads", side_effect=AssertionError("parser")):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_wire_bytes"):
                    loads_content(data, limits=ToolReleaseLimits(max_wire_bytes=9))
        with self.assertRaisesRegex(ToolReleaseValidationError, "surrogate"):
            loads_content('"\ud800"')

    def test_lexical_guards_before_stdlib_parser_with_success_controls(self):
        """Canonical bytes, strings, collections, nodes and depth are guarded during lexical scanning."""
        doc = rich_wire()
        text = canonical(doc)
        measured = requirements(doc)
        real = json.loads
        for name in ("max_canonical_bytes", "max_string_chars", "max_collection_items", "max_nodes", "max_depth"):
            for data in (text, text.encode("utf-8")):
                with self.subTest(limit=name, bytes=type(data) is bytes):
                    with patch.object(codec.json, "loads", wraps=real) as spy:
                        self.assertEqual(loads_content(data, limits=ToolReleaseLimits(**{name: measured[name]})).to_dict(), doc)
                        self.assertTrue(spy.called)
                    with patch.object(codec.json, "loads", side_effect=AssertionError("parser reached")):
                        with self.assertRaisesRegex(ToolReleaseLimitError, name):
                            loads_content(data, limits=ToolReleaseLimits(**{name: measured[name] - 1}))
        # A base-work deficit must also stop the parser, independently of the
        # additional schema-specific path-prefix charge tested below.
        base_units = measured["max_reconstruction_units"] - (3 + 10 + 10)
        with patch.object(codec.json, "loads", side_effect=AssertionError("parser reached")):
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_reconstruction_units"):
                loads_content(text, limits=ToolReleaseLimits(max_reconstruction_units=base_units - 1))
        with patch.object(codec.json, "loads", side_effect=AssertionError("parser reached")):
            for data in ('["\\ud800"]', '[' + '1' * 10000 + ']', '[1.0]', '[NaN]', '[' * 25 + '0' + ']' * 25):
                with self.assertRaises(ToolReleaseValidationError):
                    loads_content(data)

    def test_complete_canonical_accounting_precedes_any_serialization(self):
        """Full metadata, fixed-width identities, escapes and empty framing fit before json.dumps."""
        doc = rich_wire()
        count = len(canonical(doc))
        inputs, release = constructor_sections(doc), decode_content(doc)
        real = json.dumps
        boundaries = (lambda limits: ToolRelease(**inputs, limits=limits), lambda limits: decode_content(doc, limits=limits),
                      lambda limits: release.to_dict(limits=limits), lambda limits: dumps_content(release, limits=limits),
                      lambda limits: loads_content(canonical_text, limits=limits))
        canonical_text = canonical(doc)
        for boundary in boundaries:
            with patch.object(codec.json, "dumps", wraps=real) as spy:
                boundary(ToolReleaseLimits(max_canonical_bytes=count))
                self.assertTrue(spy.called)
            with patch.object(codec.json, "dumps", side_effect=AssertionError("serialization reached")):
                with self.assertRaisesRegex(ToolReleaseLimitError, "max_canonical_bytes"):
                    boundary(ToolReleaseLimits(max_canonical_bytes=count - 1))
        framing = {name: doc[name] for name in ("format", "version", "kind", "release_id", "adapter_identity", "configuration_identity")}
        self.assertGreater(len(canonical(framing)), 3 * 71)
        with self.assertRaisesRegex(ToolReleaseLimitError, "max_canonical_bytes"):
            ToolRelease(**inputs, limits=ToolReleaseLimits(max_canonical_bytes=count - len(canonical(framing))))

    def test_del_canonical_bytes_at_every_public_boundary(self):
        """Charge each DEL escape before protected work, preserving full content at equality."""
        tree_operations = ((codec.json, "dumps"), (product, "detached"))
        parse_operations = ((codec.json, "loads"), (codec.json, "dumps"))
        for count in (1, 7):
            label = "\x7f" * count
            doc = wire()
            doc["identity"]["release_label"] = known(label)
            doc = rehash(doc)
            # Prepare all fixtures and stdlib oracles before patching the shared json module.
            inputs = constructor_sections(doc)
            text = canonical(doc)
            literal_text = text.replace("\\u007f", "\x7f")
            representations = (("escaped", text), ("literal", literal_text))
            wire_inputs = [(name, data) for name, value in representations
                           for data in (value, value.encode("utf-8"))]
            release = decode_content(doc)
            required = len(text.encode("ascii"))
            equal = ToolReleaseLimits(max_canonical_bytes=required)
            short = ToolReleaseLimits(max_canonical_bytes=required - 1)
            boundaries = [
                ("constructor", lambda limits: ToolRelease(**inputs, limits=limits), tree_operations),
                ("decode_content", lambda limits: decode_content(doc, limits=limits), tree_operations),
                ("from_dict", lambda limits: ToolRelease.from_dict(doc, limits=limits), tree_operations),
                ("to_dict", lambda limits: release.to_dict(limits=limits), parse_operations),
                ("dumps_content", lambda limits: dumps_content(release, limits=limits), parse_operations),
            ]
            for spelling, data in wire_inputs:
                boundaries.append((
                    f"loads_content {spelling} {type(data).__name__}",
                    lambda limits, data=data: loads_content(data, limits=limits), parse_operations,
                ))
            for name, boundary, operations in boundaries:
                with self.subTest(del_count=count, boundary=name):
                    with ExitStack() as stack:
                        spies = [stack.enter_context(patch.object(module, operation,
                                                                  wraps=getattr(module, operation)))
                                 for module, operation in operations]
                        result = boundary(equal)
                        for (_, operation), spy in zip(operations, spies):
                            self.assertTrue(spy.called, operation)
                    # Public result inspection can parse/serialize again; keep it outside spies.
                    if type(result) is ToolRelease:
                        actual = result.to_dict(limits=equal)
                        self.assertEqual(dumps_content(result, limits=equal), text)
                    elif type(result) is dict:
                        actual = result
                        self.assertEqual(canonical(result), text)
                    else:
                        self.assertEqual(result, text)
                        actual = json.loads(result)
                    self.assertEqual(actual, doc)
                    self.assertEqual(actual["identity"]["release_label"], known(label))
                    with ExitStack() as stack:
                        for module, operation in operations:
                            stack.enter_context(patch.object(
                                module, operation, side_effect=AssertionError(operation + " reached")))
                        with self.assertRaisesRegex(ToolReleaseLimitError, "max_canonical_bytes"):
                            boundary(short)

    def test_reference_and_path_work_precede_reconstruction_and_normalization(self):
        """Aggregate repeated references and path-prefix work are complete before protected helpers."""
        doc = rich_wire()
        measured = requirements(doc)
        inputs, release, text = constructor_sections(doc), decode_content(doc), canonical(doc)
        boundaries = (lambda limits: ToolRelease(**inputs, limits=limits), lambda limits: decode_content(doc, limits=limits),
                      lambda limits: loads_content(text, limits=limits), lambda limits: release.to_dict(limits=limits),
                      lambda limits: dumps_content(release, limits=limits))
        for name in ("max_references", "max_reconstruction_units"):
            for module, helper in ((product, "detached"), (product, "_references_and_dimensions"),
                                   (product.work_product, "_validate_paths"), (product.work_product, "_path")):
                real = getattr(module, helper)
                for boundary in boundaries:
                    with self.subTest(limit=name, helper=helper):
                        with patch.object(module, helper, wraps=real) as spy:
                            boundary(ToolReleaseLimits(**{name: measured[name]}))
                            self.assertTrue(spy.called)
                        with patch.object(module, helper, side_effect=AssertionError("protected reconstruction reached")):
                            with self.assertRaisesRegex(ToolReleaseLimitError, name):
                                boundary(ToolReleaseLimits(**{name: measured[name] - 1}))

    def test_aliases_count_each_occurrence_and_cycles_reject_incrementally(self):
        """Repeated acyclic dictionaries/list text count again; ancestor cycles cannot reach copying."""
        doc = rich_wire()
        pin = doc["identity"]["provenance_records"]["value"][0]
        doc["identity"]["provenance_records"]["value"] = [pin, pin, pin]
        expected = rehash(doc)
        doc.update({name: expected[name] for name in ("release_id", "adapter_identity", "configuration_identity")})
        equal = ToolReleaseLimits(**requirements(doc))
        self.assertEqual(decode_content(doc, limits=equal).to_dict(), doc)
        for name in ("max_references", "max_nodes", "max_reconstruction_units"):
            amount = requirements(doc)[name]
            with self.assertRaisesRegex(ToolReleaseLimitError, name):
                decode_content(doc, limits=ToolReleaseLimits(**{name: amount - 1}))
        for cycle in ("dict", "list"):
            doc = wire()
            if cycle == "dict":
                doc["identity"]["readme"] = doc
            else:
                values = []
                values.append(values)
                doc["identity"]["supplier"] = known(values)
            with patch.object(codec, "detached", side_effect=AssertionError("copy reached")), patch.object(product, "detached", side_effect=AssertionError("copy reached")):
                with self.assertRaisesRegex(ToolReleaseValidationError, "cyclic"):
                    decode_content(doc)

    def test_independent_limits_not_embedded_retained_or_relaxed(self):
        """Wire limits apply only to external JSON; forged snapshots and limits are revalidated."""
        doc = wire()
        release = decode_content(doc)
        zero_wire = ToolReleaseLimits(max_wire_bytes=0)
        self.assertEqual(ToolRelease(**constructor_sections(doc), limits=zero_wire), release)
        self.assertEqual(decode_content(doc, limits=zero_wire), release)
        self.assertEqual(release.to_dict(limits=zero_wire), doc)
        self.assertEqual(dumps_content(release, limits=zero_wire), canonical(doc))
        with self.assertRaisesRegex(ToolReleaseLimitError, "max_wire_bytes"):
            loads_content(canonical(doc), limits=zero_wire)
        for field in fields(ToolReleaseLimits):
            limits = ToolReleaseLimits(**{field.name: 0})
            if field.name != "max_wire_bytes":
                with self.assertRaisesRegex(ToolReleaseLimitError, field.name):
                    decode_content(doc, limits=limits)
        limits = ToolReleaseLimits()
        made = ToolRelease(**constructor_sections(doc), limits=limits)
        object.__setattr__(limits, "max_nodes", 0)
        self.assertEqual(made.to_dict(), doc)
        forged = object.__new__(ToolRelease)
        object.__setattr__(forged, "_json", canonical(doc))
        for name, amount in requirements(doc).items():
            if name != "max_wire_bytes":
                with self.assertRaisesRegex(ToolReleaseLimitError, name):
                    forged.to_dict(limits=ToolReleaseLimits(**{name: amount - 1}))
        doc["limits"] = {"max_nodes": 99999999}
        with self.assertRaises(ToolReleaseValidationError):
            decode_content(doc)

    def test_raw_container_and_empty_framing_guards_before_schema(self):
        """Even malformed empty containers and object keys are charged before missing-field checks."""
        for value, name, ceiling in (({}, "max_nodes", 0), ({}, "max_depth", 0), ({}, "max_canonical_bytes", 1),
                                      ({"key": []}, "max_string_chars", 2), ({"a": [], "b": []}, "max_collection_items", 1)):
            with self.assertRaisesRegex(ToolReleaseLimitError, name):
                decode_content(value, limits=ToolReleaseLimits(**{name: ceiling}))
        with patch.object(codec.json, "loads", side_effect=AssertionError("parser reached")):
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_nodes"):
                loads_content('[[],[],[]]', limits=ToolReleaseLimits(max_nodes=3))
        # Existing schema permits deliberate empty lists, but no arbitrary empty
        # extension dictionary. The framing guard still counts both before schema.
        doc = wire()
        doc["identity"]["readme"] = "x" * 16385
        forged = object.__new__(ToolRelease)
        object.__setattr__(forged, "_json", canonical(doc))
        for consume in (lambda: forged.tool_id, lambda: forged.release_id, lambda: forged == forged):
            with self.assertRaisesRegex(ToolReleaseLimitError, "max_string_chars"):
                consume()
