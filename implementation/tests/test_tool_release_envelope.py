"""Exact projections, retained forgery rejection, detachment and passive boundaries."""

from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch

from research_pipeline.domain import ArtifactReference, CreationProvenance, RecordEnvelope, RecordReference
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_release import ToolRelease, ToolReleaseValidationError
from research_pipeline.tool_release_envelope import encode_envelope, decode_envelope
from tests.tool_release_fixtures import canonical, constructor_sections, known, missing, rehash
from tests.tool_release_envelope_fixtures import (
    complete_wire, creator, expected_artifacts, expected_records, forged, release,
)


def fail_hook(*args, **kwargs):
    """Fail if a rejected alias dispatches any caller-controlled operation."""
    raise AssertionError("untrusted hook dispatched")


class HostileMeta(type):
    """Detect class membership/hash dispatch rather than identity-only type checking."""

    __eq__ = fail_hook
    __hash__ = fail_hook


def hostile(base, value=None):
    """Create an alias whose length, iteration, comparison and serialization are forbidden."""
    cls = HostileMeta("Alias", (base,), {
        "__len__": fail_hook, "__iter__": fail_hook, "__eq__": fail_hook,
        "__hash__": fail_hook, "__str__": fail_hook, "__int__": fail_hook,
        "to_dict": fail_hook, "__getattribute__": fail_hook,
    })
    return cls(value) if value is not None else object.__new__(cls)


class ToolReleaseEnvelopeTests(unittest.TestCase):
    """Exercise both exact public conversions without any store or target inspection."""

    def setUp(self):
        """Prepare complete typed inputs before installing operation sentinels."""
        self.release = release()
        self.provenance = creator()
        self.envelope = encode_envelope("affine_tool", 87, self.release, self.provenance)

    def test_local_remote_composite_complete_order_and_identities(self):
        """All seven record slots and all artifact slots preserve concrete independent order."""
        for kind in ("local_program", "remote_service", "composite_workflow"):
            with self.subTest(kind=kind):
                value = release(kind)
                envelope = encode_envelope("affine_tool", 87, value, self.provenance)
                self.assertIs(type(envelope), RecordEnvelope)
                self.assertEqual(envelope.record_references, expected_records())
                self.assertEqual(envelope.artifact_references, expected_artifacts())
                self.assertEqual(envelope.content, complete_wire(kind))
                self.assertEqual(envelope.record_id, "affine_tool")
                self.assertEqual(envelope.revision, 87)
                self.assertEqual(envelope.kind, "tool_release")
                self.assertIsNone(envelope.operational_status)
                self.assertIsNone(envelope.scientific_disposition)
                self.assertEqual(envelope.provenance.to_dict(), self.provenance.to_dict())
                decoded = decode_envelope(envelope)
                self.assertIs(type(decoded), ToolRelease)
                self.assertIsNot(decoded, value)
                self.assertEqual(decoded.to_dict(), complete_wire(kind))
                for name in ("release_id", "adapter_identity", "configuration_identity"):
                    self.assertEqual(decoded.to_dict()[name], value.to_dict()[name])
                self.assertNotEqual(envelope.provenance.actor, envelope.content["identity"]["declared_by"]["value"])

    def test_missing_facts_remain_distinct_and_do_not_erase_activity(self):
        """Unknown/unavailable/known-empty slots project nothing while declared effects persist."""
        doc = complete_wire("composite_workflow")
        doc["identity"]["provenance_records"] = missing()
        doc["identity"]["implementation"]["source_records"] = missing("unavailable")
        doc["effects_authority"]["child_tools"] = known([])
        doc["reproducibility"]["dependency_artifacts"] = missing()
        value = ToolRelease(**constructor_sections(doc))
        envelope = encode_envelope("affine_tool", 1, value, self.provenance)
        decoded = decode_envelope(envelope).to_dict()
        self.assertEqual(decoded, value.to_dict())
        self.assertEqual(envelope.record_references, expected_records()[7:])
        self.assertEqual(envelope.artifact_references, expected_artifacts()[:4])
        self.assertEqual(decoded["identity"]["provenance_records"]["state"], "unknown")
        self.assertEqual(decoded["identity"]["implementation"]["source_records"]["state"], "unavailable")
        self.assertEqual(decoded["effects_authority"]["child_tools"], known([]))
        self.assertEqual(decoded["effects_authority"]["model_activity"]["state"], "declared")
        self.assertEqual(decoded["effects_authority"]["delegated_activity"]["state"], "declared")
        self.assertEqual(decoded["effects_authority"]["filesystem_write"], doc["effects_authority"]["filesystem_write"])

    def test_generic_wrong_projections_are_rejected_without_repair(self):
        """Normally constructed generic envelopes can omit, add, reorder or substitute pins."""
        records, artifacts = self.envelope.record_references, self.envelope.artifact_references
        cases = [
            (records[1:], artifacts), (records + records[:1], artifacts),
            (records[2:3] + records[:2] + records[3:], artifacts),
            (records, artifacts[1:]), (records, artifacts + artifacts[:1]),
            (records, artifacts[::-1]),
        ]
        for field, value in (("record_id", "changed"), ("revision", 4),
                             ("relationship", "build_dependency"), ("target_kind", "project")):
            pin = records[0].to_dict()
            pin[field] = value
            cases.append(((RecordReference(**pin),) + records[1:], artifacts))
        cases.extend((records, (ArtifactReference(digest, size),) + artifacts[1:])
                     for digest, size in (("0" * 64, 1), (artifacts[0].digest, 2)))
        for pins, blobs in cases:
            with self.subTest(records=pins, artifacts=blobs):
                envelope = RecordEnvelope("affine_tool", 87, "tool_release", self.envelope.content,
                                          self.provenance, pins, blobs)
                with self.assertRaisesRegex(ToolReleaseValidationError, "projections"):
                    decode_envelope(envelope)
        # Reusing the very same exact reference object is a legal repeated occurrence.
        repeated = (records[0], records[0]) + records[2:]
        self.assertEqual(decode_envelope(forged(self.envelope, record_references=repeated)), self.release)

    def test_wrong_metadata_states_and_stable_identity(self):
        """Reject retained metadata changes and require explicit positive signed-64 revisions."""
        for name, value in (("kind", "source"), ("record_id", "other"),
                            ("operational_status", "ready"), ("scientific_disposition", "provisional"),
                            ("revision", 0), ("revision", 2**63), ("revision", True)):
            with self.subTest(field=name, value=value), self.assertRaises(ToolReleaseValidationError):
                decode_envelope(forged(self.envelope, **{name: value}))
        for identity, revision in (("other", 1), ("bad/id", 1), ("affine_tool", 0),
                                   ("affine_tool", -1), ("affine_tool", True), ("affine_tool", 2**63)):
            with self.assertRaises(ToolReleaseValidationError):
                encode_envelope(identity, revision, self.release, self.provenance)
        envelope = encode_envelope("affine_tool", 2**63 - 1, self.release, self.provenance)
        self.assertEqual(decode_envelope(envelope), self.release)

    def test_content_stale_hashes_semantic_contradictions_and_canonicality(self):
        """Both boundaries reject stale, rehashed-invalid and noncanonical retained snapshots."""
        stale = complete_wire()
        stale["identity"]["display_name"] = "changed without rehash"
        bad_size = complete_wire()
        bad_size["reproducibility"]["dependency_artifacts"]["value"][0] = {
            **bad_size["reproducibility"]["dependency_artifacts"]["value"][0], "size": 999}
        bad_kind = complete_wire()
        bad_kind["reproducibility"]["dependency_records"]["value"][0]["target_kind"] = "project"
        contradiction = complete_wire()
        contradiction["effects_authority"]["model_activity"]["providers"] = known(["hidden_provider"])
        texts = [canonical(stale), canonical(rehash(bad_size)), canonical(rehash(bad_kind)),
                 canonical(rehash(contradiction)), " " + self.release._json,
                 self.release._json.replace('"version":1', '"version":1,"version":1'),
                 self.release._json.replace('"version":1', '"version":true'), "{", '"\\ud800"']
        for identity in ("release_id", "adapter_identity", "configuration_identity"):
            changed = complete_wire()
            changed[identity] = "sha256:" + "0" * 64
            texts.append(canonical(changed))
        for text in texts:
            with self.subTest(text=text[:60]):
                with self.assertRaises(ToolReleaseValidationError):
                    encode_envelope("affine_tool", 1, forged(self.release, _json=text), self.provenance)
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, _content_json=text))
        for text in ("{}", '{"description":"generic"}'):
            with self.assertRaises(NotTypedContentError):
                decode_envelope(forged(self.envelope, _content_json=text))
        # Content semantic failures precede stable-ID mismatch and stale hashes.
        with self.assertRaisesRegex(ToolReleaseValidationError, "conflicting sizes"):
            decode_envelope(forged(self.envelope, record_id="other", _content_json=canonical(bad_size)))

    def test_coherent_detached_forgery_is_locally_valid_not_authenticated(self):
        """Changing and independently rehashing a declaration cannot prove persisted authenticity."""
        doc = complete_wire()
        doc["identity"]["display_name"] = "Unverified replacement declaration"
        text = canonical(rehash(doc))
        changed = decode_envelope(forged(self.envelope, _content_json=text))
        self.assertNotEqual(changed.release_id, self.release.release_id)
        self.assertEqual(changed.to_dict()["identity"]["display_name"], "Unverified replacement declaration")
        self.assertEqual(encode_envelope("affine_tool", 87, forged(self.release, _json=text), self.provenance).content,
                         changed.to_dict())

    def test_provenance_generic_scalars_and_malformed_retained_snapshots(self):
        """Generic JSON retains booleans, signed numbers/floats and Unicode; malformed snapshots fail."""
        self.assertEqual(self.envelope.provenance.details, self.provenance.details)
        cases = [("actor", "bad/id"), ("created_at", "2026-02-30T00:00:00.000000Z"),
                 ("created_at", "2026-11-04T10:00:00Z"), ("created_at", "\ud800"),
                 ("_details_json", '{"a":1,"a":2}'), ("_details_json", '{"a":NaN}'),
                 ("_details_json", '{"a":Infinity}'), ("_details_json", '{"a":1e999}'),
                 ("_details_json", '{"a":"\\ud800"}'), ("_details_json", '{"α":1}'),
                 ("_details_json", '{ "a": 1 }'), ("_details_json", '{"z":1,"a":2}'),
                 ("_details_json", "[]"), ("_details_json", "null"), ("_details_json", "{"),
                 ("_details_json", '{"a":' + '[' * 1100 + '0' + ']' * 1100 + '}')]
        for name, value in cases:
            provenance = forged(self.provenance, **{name: value})
            with self.subTest(field=name, value=value[:50]):
                with self.assertRaises(ToolReleaseValidationError):
                    encode_envelope("affine_tool", 1, self.release, provenance)
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, provenance=provenance))

    def test_retained_types_missing_fields_and_cycles_reject_without_hooks(self):
        """Aliases, lookalikes, generators and cyclic replacements fail before user operations."""
        cycle = []
        cycle.append(cycle)
        bad_values = [hostile(str, "x"), [], {}, cycle, object(), (item for item in ()),
                      True, 1, 1.0, b"bytes"]
        for value in bad_values:
            for field in ("record_id", "kind", "_content_json"):
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, **{field: value}))
            with self.assertRaises(ToolReleaseValidationError):
                encode_envelope("affine_tool", 1, forged(self.release, _json=value), self.provenance)
            for field in ("actor", "created_at", "_details_json"):
                provenance = forged(self.provenance, **{field: value})
                with self.assertRaises(ToolReleaseValidationError):
                    encode_envelope("affine_tool", 1, self.release, provenance)
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, provenance=provenance))
        for value in ([], hostile(tuple, ()), (item for item in ()), cycle):
            for field in ("record_references", "artifact_references"):
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, **{field: value}))
        for value in (hostile(ToolRelease), object(), {}):
            with self.assertRaises(ToolReleaseValidationError):
                encode_envelope("affine_tool", 1, value, self.provenance)
        for value in (hostile(RecordEnvelope), object(), {}):
            with self.assertRaises(ToolReleaseValidationError):
                decode_envelope(value)
        for value in (hostile(CreationProvenance), object(), {}):
            with self.assertRaises(ToolReleaseValidationError):
                encode_envelope("affine_tool", 1, self.release, value)
            with self.assertRaises(ToolReleaseValidationError):
                decode_envelope(forged(self.envelope, provenance=value))
        for original in (self.release, self.envelope, self.provenance):
            for name in vars(original):
                value = forged(original)
                object.__delattr__(value, name)
                with self.subTest(missing=name), self.assertRaises(ToolReleaseValidationError):
                    if type(value) is ToolRelease:
                        encode_envelope("affine_tool", 1, value, self.provenance)
                    elif type(value) is CreationProvenance:
                        decode_envelope(forged(self.envelope, provenance=value))
                    else:
                        decode_envelope(value)
                if type(value) is CreationProvenance:
                    with self.assertRaises(ToolReleaseValidationError):
                        encode_envelope("affine_tool", 1, self.release, value)

    def test_forged_reference_fields_exact_scalar_ranges_and_missing_values(self):
        """All reference scalars are revalidated before Python equality can mask aliases."""
        for field, original, cls in (("record_references", self.envelope.record_references, RecordReference),
                                     ("artifact_references", self.envelope.artifact_references, ArtifactReference)):
            for value in (hostile(cls), object(), {}, []):
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, **{field: (value,) + original[1:]}))
            for name, scalar in vars(original[0]).items():
                replacements = [None, [], {}, object(), hostile(type(scalar), scalar)]
                replacements += [True, 1.0, -1, 2**63] if type(scalar) is int else ["bad/field", "\ud800"]
                for replacement in replacements:
                    pin = forged(original[0], **{name: replacement})
                    with self.subTest(field=name), self.assertRaises(ToolReleaseValidationError):
                        decode_envelope(forged(self.envelope, **{field: (pin,) + original[1:]}))
                pin = forged(original[0])
                object.__delattr__(pin, name)
                with self.assertRaises(ToolReleaseValidationError):
                    decode_envelope(forged(self.envelope, **{field: (pin,) + original[1:]}))
        for value in (hostile(int, 87), 87.0, True):
            with self.assertRaises(ToolReleaseValidationError):
                encode_envelope("affine_tool", value, self.release, self.provenance)
            with self.assertRaises(ToolReleaseValidationError):
                decode_envelope(forged(self.envelope, revision=value))
        with self.assertRaises(ToolReleaseValidationError):
            encode_envelope(hostile(str, "affine_tool"), 87, self.release, self.provenance)

    def test_raw_access_ignores_instance_serializers_and_properties(self):
        """Exact receivers can shadow methods; conversion reads only retained fields."""
        value = forged(self.release, to_dict=fail_hook)
        provenance = forged(self.provenance, to_dict=fail_hook)
        envelope = forged(self.envelope, to_dict=fail_hook, provenance=provenance)
        for pin in envelope.record_references + envelope.artifact_references:
            object.__setattr__(pin, "to_dict", fail_hook)
        with patch.object(RecordEnvelope, "content", property(fail_hook)), \
                patch.object(CreationProvenance, "details", property(fail_hook)), \
                patch.object(ToolRelease, "to_dict", fail_hook), \
                patch.object(RecordReference, "to_dict", fail_hook), \
                patch.object(ArtifactReference, "to_dict", fail_hook):
            made = encode_envelope("affine_tool", 87, value, provenance)
            decoded = decode_envelope(envelope)
        self.assertEqual(made.content, self.release.to_dict())
        self.assertEqual(decoded, self.release)

    def test_detachment_caller_pins_provenance_envelope_and_decoded_trees(self):
        """Only directly bypass-mutated objects change; earlier snapshots remain independent."""
        sections = constructor_sections(complete_wire())
        pin = sections["identity"]["provenance_records"]["value"][0]
        value = ToolRelease(**sections)
        sections["identity"]["display_name"] = "changed"
        object.__setattr__(pin, "record_id", "mutated")
        self.assertEqual(value.to_dict(), complete_wire())
        details = {"data": [1]}
        provenance = CreationProvenance("creator", "2026-11-04T00:00:00Z", details)
        details["data"].append(2)
        envelope = encode_envelope("affine_tool", 1, value, provenance)
        decoded = decode_envelope(envelope)
        second = encode_envelope("affine_tool", 1, decoded, envelope.provenance)
        object.__setattr__(provenance, "_details_json", "bad")
        object.__setattr__(envelope.record_references[0], "record_id", "changed")
        object.__setattr__(envelope.provenance, "actor", "bad/actor")
        detached = decoded.to_dict()
        detached["identity"]["display_name"] = "changed result"
        self.assertEqual(decoded.to_dict(), complete_wire())
        self.assertEqual(second.content, complete_wire())
        self.assertEqual(second.provenance.details, {"data": [1]})
        self.assertEqual(second.record_references, expected_records())
        self.assertEqual(value.to_dict(), complete_wire())
        with self.assertRaises(ToolReleaseValidationError):
            decode_envelope(envelope)
        with self.assertRaises(ToolReleaseValidationError):
            encode_envelope("affine_tool", 1, value, provenance)
        # Generic envelopes retain supplied pins, but decoding retains only content.
        generic = RecordEnvelope("affine_tool", 1, "tool_release", second.content, second.provenance,
                                 second.record_references, second.artifact_references)
        prior = decode_envelope(generic)
        object.__setattr__(generic.artifact_references[0], "size", 99)
        self.assertEqual(prior.to_dict(), complete_wire())
        with self.assertRaises(ToolReleaseValidationError):
            decode_envelope(generic)

    def test_passive_boundaries_never_read_host_or_invoke_descriptions(self):
        """Filesystem, environment, subprocess, network and dynamic invocation stay untouched."""
        values = [release(kind) for kind in ("local_program", "remote_service", "composite_workflow")]
        targets = ("builtins.open", "builtins.__import__", "os.open", "os.stat", "os.getenv",
                   "subprocess.Popen", "subprocess.run", "os.system", "socket.socket",
                   "builtins.eval", "builtins.exec", "importlib.import_module")
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=fail_hook))
            stack.enter_context(patch.object(os._Environ, "__getitem__", side_effect=fail_hook))
            for value in values:
                envelope = encode_envelope("affine_tool", 1, value, self.provenance)
                decoded = decode_envelope(envelope)
                self.assertEqual(decoded, value)

    def test_assertion_failures_are_not_hidden(self):
        """Programming/sentinel assertions propagate instead of becoming validation failures."""
        with patch.object(ToolRelease, "from_dict", side_effect=AssertionError("visible")):
            with self.assertRaisesRegex(AssertionError, "visible"):
                decode_envelope(self.envelope)
