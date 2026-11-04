"""Complete passive assessment content behavior and adverse exact-type boundaries.

Process-global patches use stock unittest's serial methods within the existing
isolated module worker; no scheduling declaration or shared resource is needed.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import unittest
from unittest.mock import patch

from research_pipeline.domain import ArtifactReference, RecordReference
from research_pipeline.scientific import NotTypedContentError
from research_pipeline.tool_assessment import (
    ToolAssessment, ToolAssessmentLimits, ToolAssessmentValidationError as Invalid,
    decode_content, dumps_content, loads_content,
)
from tests.tool_assessment_fixtures import (
    PROSE, DIMENSIONS, assessment, wire, constructor_fields, canonical, known, missing,
    evidence, record, artifact, forged, object_paths, at,
)


def trap(*args, **kwargs):
    """Expose accidental caller hook dispatch or passive boundary violations."""
    raise AssertionError("protected operation invoked")


class EqualityMeta(type):
    """Detect class equality dispatch independently of class hash dispatch."""

    def __eq__(cls, other):
        """Fail if an untrusted class is compared rather than checked by identity."""
        return trap()

    __hash__ = type.__hash__


class HashMeta(type):
    """Detect untrusted class hashing independently of equality."""

    def __hash__(cls):
        """Fail if an untrusted class is used as a dispatch dictionary key."""
        return trap()


class ToolAssessmentTests(unittest.TestCase):
    """Verify complete supplied reports, closed schema and defensive consumption."""

    def test_substantive_variants_round_trip_and_independent_dimensions(self):
        """Keep permission, checks, qualification and withdrawn history independent."""
        for outcome in ("fail", "inconclusive", "unperformed"):
            with self.subTest(outcome=outcome):
                value = wire(outcome)
                content = decode_content(value)
                self.assertEqual(ToolAssessment(**constructor_fields(value)), content)
                self.assertEqual(loads_content(dumps_content(content).encode()), content)
                self.assertEqual(content.to_dict(), value)
                self.assertEqual(content.assessment_id, "assessment")
                self.assertEqual(value["execution_permission"]["status"], "revoked")
                self.assertEqual(value["qualification"]["operational_interface"]["outcome"], "pass")
                self.assertEqual(value["qualification"]["software_behavior"]["outcome"], "pass")
                self.assertEqual(value["lifecycle"]["status"], "withdrawn")
                self.assertEqual(value["scope"]["intended_uses"]["value"], [PROSE])
                self.assertIn('"reported_at":{"reason":null,"state":"known","value":"2026-10-30T12:34:56.12Z"}', dumps_content(content))

    def test_literal_text_normalization_and_full_value_equality(self):
        """Normalize legal external spelling only; full authored values determine equality."""
        value = wire()
        external = json.dumps(value, ensure_ascii=False, indent=2)
        self.assertEqual(loads_content(external), assessment())
        self.assertEqual(dumps_content(loads_content(external)), canonical(value))
        value["limitations"]["value"].append("Another limitation.")
        changed = decode_content(value)
        self.assertEqual(changed.assessment_id, assessment().assessment_id)
        self.assertNotEqual(changed, assessment())
        self.assertIs(ToolAssessment.__eq__(assessment(), object()), NotImplemented)
        with self.assertRaises(TypeError):
            hash(changed)

    def test_frozen_snapshot_and_mutation_isolation(self):
        """Caller containers/pins and returned trees never remain dependencies of snapshots."""
        fields = constructor_fields()
        pin = fields["target"]["release"]
        content = ToolAssessment(**fields)
        object.__setattr__(pin, "revision", 999)
        fields["scope"]["intended_uses"]["value"].clear()
        returned = content.to_dict()
        returned["environment"]["dependencies"]["value"].clear()
        self.assertEqual(content.to_dict(), wire())
        self.assertEqual(set(vars(content)), {"_json"})
        with self.assertRaises(FrozenInstanceError):
            content._json = "{}"
        with self.assertRaises(FrozenInstanceError):
            content.assessment_id = "other"

    def test_constructor_collections_and_reference_boundary_are_distinct(self):
        """Typed constructors accept tuples/pins while wire decoders require lists/complete objects."""
        fields = constructor_fields()
        fields["environment"]["records"]["value"] = tuple(fields["environment"]["records"]["value"])
        self.assertEqual(ToolAssessment(**fields), assessment())
        fields["target"]["release"] = wire()["target"]["release"]
        with self.assertRaises(Invalid):
            ToolAssessment(**fields)
        for replacement in (RecordReference("tool", 2, "assessed_release", "tool_release"),
                            {"record_id": "tool", "revision": 2, "relationship": "assessed_release"}):
            value = wire()
            value["target"]["release"] = replacement
            with self.assertRaises(Invalid):
                decode_content(value)
        value = wire()
        value["environment"]["records"]["value"] = tuple(value["environment"]["records"]["value"])
        with self.assertRaises(Invalid):
            decode_content(value)

    def test_every_populated_object_is_closed(self):
        """Reject omitted and added fields at every object, including nested pins and facts."""
        original = wire()
        for path in object_paths(original):
            for operation in ("omit", "add"):
                with self.subTest(path=path, operation=operation):
                    value = deepcopy(original)
                    target = at(value, path)
                    if operation == "omit":
                        del target[next(iter(target))]
                    else:
                        target["extension"] = None
                    with self.assertRaises((Invalid, NotTypedContentError)):
                        decode_content(value)

    def test_every_reference_role_and_kind_is_restricted(self):
        """Check each populated slot independently, retaining complete occurrence coverage."""
        original = wire()
        for path in object_paths(original):
            item = at(original, path)
            if set(item) != {"record_id", "revision", "relationship", "target_kind"}:
                continue
            for field, replacement in (("relationship", "wrong_role"), ("target_kind", "claim"),
                                       ("target_kind", None), ("revision", True), ("revision", 0)):
                with self.subTest(path=path, field=field, replacement=replacement):
                    value = deepcopy(original)
                    at(value, path)[field] = replacement
                    with self.assertRaises(Invalid):
                        decode_content(value)

    def test_all_explicit_closed_vocabularies_and_local_successes(self):
        """Accept every fixed code where its stated local prerequisites are satisfied."""
        cases = [(("attribution", "origin"), "synthetic unverified"),
                 (("environment", "kind"), "local remote composite unknown unavailable"),
                 (("environment", "observability"), "pinned_description reported_version_only opaque unknown unavailable"),
                 (("issues", "value", 0, "category"), "operational_interface software_behavior scientific_applicability observability other"),
                 (("execution_permission", "status"), "unassessed permitted denied revoked restricted unknown"),
                 (("lifecycle", "status"), "unassessed active restricted suspended withdrawn superseded unknown"),
                 (("lifecycle", "reason_category"), "unassessed routine_revision operational_restriction software_defect scientific_defect observability_limit other unknown")]
        for path, words in cases:
            for code in (*words.split(), "unsupported"):
                with self.subTest(path=path, code=code):
                    value = wire()
                    value["environment"]["reported_version"] = known("reported v1")
                    at(value, path[:-1])[path[-1]] = code
                    if code == "unsupported":
                        with self.assertRaises(Invalid):
                            decode_content(value)
                    else:
                        self.assertEqual(at(decode_content(value).to_dict(), path), code)
        for dimension in DIMENSIONS:
            for outcome in ("unperformed", "pass", "fail", "inconclusive"):
                value = wire()
                value["qualification"][dimension]["outcome"] = outcome
                value["qualification"][dimension]["evidence"] = missing()
                self.assertEqual(decode_content(value).to_dict(), value)
        for mode in ("answer_blind_reconstruction", "proof_blind_reconstruction", "candidate_aware_audit"):
            value = wire()
            value["reviews"]["value"][0]["independence"]["reported_mode"] = known(mode)
            self.assertEqual(decode_content(value).to_dict(), value)

    def test_evidence_categories_and_independent_nested_attribution(self):
        """Require category pins/statements while retaining absent nested authors with reasons."""
        for basis in ("assessor_assertion", "builder_self_test", "reported_tool_execution", "independent_review"):
            value = wire()
            supplied = evidence("supplied", basis)
            supplied["attribution"] = {"actor": missing(), "reported_at": missing(), "origin": "unverified"}
            value["issues"]["value"][0]["evidence"] = known([supplied])
            self.assertEqual(decode_content(value).to_dict(), value)
            supplied["records"] = known([])
            supplied["artifacts"] = known([])
            if basis == "assessor_assertion":
                decode_content(value)
                supplied["statement"] = missing()
            with self.assertRaises(Invalid):
                decode_content(value)
        for kind in ("source", "work_product_manifest", "evidence"):
            value = wire()
            supplied = value["issues"]["value"][0]["evidence"]["value"][0]
            supplied["records"] = known([record("assertion", "reported_assertion", kind)])
            decode_content(value)
        value = wire()
        supplied = value["checks"]["value"][0]["evidence"]["value"][0]
        supplied["records"] = known([record("builder", "builder_self_test", "evidence")])
        decode_content(value)

    def test_reasoned_facts_never_coerce_missing_to_empty(self):
        """Reject missing reasons, known-null payloads, blank prose and inferred timestamps."""
        for bad in ({"state": "unknown", "value": [], "reason": "Missing"},
                    {"state": "unavailable", "value": None, "reason": " \n"},
                    {"state": "known", "value": None, "reason": None},
                    {"state": "known", "value": [], "reason": "Missing"},
                    {"state": "omitted", "value": None, "reason": "Missing"}):
            value = wire()
            value["limitations"] = bad
            with self.assertRaises(Invalid):
                decode_content(value)
        for field, bad in (("actor", ""), ("reported_at", ""), ("reported_at", "2026-02-30T00:00:00Z"),
                           ("reported_at", "2026-10-30T00:00:00+00:00")):
            value = wire()
            value["attribution"][field] = known(bad)
            with self.assertRaises(Invalid):
                decode_content(value)
        value = wire()
        value["limitations"] = known([" "])
        with self.assertRaises(Invalid):
            decode_content(value)

    def test_environment_and_unique_names_consistency(self):
        """Enforce pins/version/remote limitations and the three explicit uniqueness rules."""
        mutations = [(("environment", "limitations"), known([])),
                     (("environment", "configuration", "value"), [{"name": "n", "value": "a"}, {"name": "n", "value": "b"}])]
        for path, bad in mutations:
            value = wire()
            at(value, path[:-1])[path[-1]] = bad
            with self.assertRaises(Invalid):
                decode_content(value)
        for name, key in (("dependencies", "name"), ("checks", "check_id")):
            value = wire()
            fact = value["environment"][name] if name == "dependencies" else value[name]
            fact["value"].append(deepcopy(fact["value"][0]))
            with self.assertRaisesRegex(Invalid, "duplicate " + key):
                decode_content(value)
        for visibility in ("pinned_description", "reported_version_only"):
            value = wire()
            env = value["environment"]
            env["observability"] = visibility
            env["records"], env["artifacts"] = missing(), known([])
            with self.assertRaises(Invalid):
                decode_content(value)
            env["reported_version"] = known("reported")
            if visibility == "pinned_description":
                env["artifacts"] = known([artifact("environment")])
            decode_content(value)
        value = wire()
        value["environment"]["limitations"] = missing()
        decode_content(value)

    def test_check_outcome_local_requirements_and_no_inference(self):
        """Pass/fail need supplied results/basis; unperformed cannot carry observations or evidence."""
        for outcome in ("pass", "fail"):
            for name in ("scope", "method", "expected", "observed", "evidence"):
                value = wire()
                check = value["checks"]["value"][0]
                check["outcome"], check[name] = outcome, missing()
                with self.assertRaises(Invalid):
                    decode_content(value)
        value = wire()
        check = value["checks"]["value"][0]
        check["basis"] = "assessor_assertion"
        with self.assertRaisesRegex(Invalid, "declared basis"):
            decode_content(value)
        for observed, supplied in ((known("not observed"), known([])), (missing(), known([evidence("extra")]))):
            value = wire()
            check = value["checks"]["value"][0]
            check.update(outcome="unperformed", observed=observed, evidence=supplied)
            with self.assertRaises(Invalid):
                decode_content(value)
        value = wire()
        check = value["checks"]["value"][0]
        check.update(outcome="inconclusive", observed=missing(), evidence=missing(), scope=missing(), method=missing())
        decode_content(value)
        for key in ("dimension", "basis", "outcome"):
            value = wire()
            value["checks"]["value"][0][key] = "unsupported"
            with self.assertRaises(Invalid):
                decode_content(value)

    def test_decision_review_and_lifecycle_local_requirements(self):
        """Conditional rationale/scope/history rules do not require scientific sufficiency."""
        paths = [("reviews", "value", 0), ("execution_permission",),
                 *(("qualification", name) for name in DIMENSIONS), ("lifecycle",)]
        for path in paths:
            value = wire()
            at(value, path)["rationale"] = missing()
            with self.assertRaises(Invalid):
                decode_content(value)
        for path in [("reviews", "value", 0), *(("qualification", name) for name in DIMENSIONS)]:
            value = wire()
            at(value, path)["scope"] = known([])
            with self.assertRaises(Invalid):
                decode_content(value)
        for status in ("permitted", "restricted"):
            value = wire()
            value["execution_permission"].update(status=status, scope=known([]))
            with self.assertRaises(Invalid):
                decode_content(value)
        value = wire()
        value["lifecycle"].update(status="superseded", replacement=missing(), superseded_by=missing())
        with self.assertRaises(Invalid):
            decode_content(value)
        value["lifecycle"]["superseded_by"] = known(record("future", "superseded_by_assessment", "tool_assessment"))
        decode_content(value)
        value = wire()
        value["lifecycle"]["replacement"]["value"]["release"]["revision"] = 2
        with self.assertRaisesRegex(Invalid, "assessed exact revision"):
            decode_content(value)
        value["lifecycle"]["replacement"]["value"]["release"]["revision"] = 4
        decode_content(value)  # Equal release_id on a distinct revision is legal.

    def test_global_reference_conflicts_and_repeated_reports(self):
        """Validate late duplicate candidates without rejecting legal repeated occurrences."""
        value = wire()
        value["lifecycle"]["evidence"]["value"][0]["artifacts"]["value"][-1]["size"] += 1
        with self.assertRaisesRegex(Invalid, "conflicting sizes"):
            decode_content(value)
        value = wire()
        value["environment"]["dependencies"]["value"][0]["records"]["value"][0].update(record_id="tool", target_kind="source")
        with self.assertRaisesRegex(Invalid, "conflicting target kinds"):
            decode_content(value)
        value = wire()
        value["reviews"]["value"].append(deepcopy(value["reviews"]["value"][0]))
        decode_content(value)

    def test_aliases_cycles_equal_independent_containers_and_repeated_pins(self):
        """Reject shared mutable positions before copying while permitting immutable pin reuse."""
        for typed in (False, True):
            value = constructor_fields() if typed else wire()
            value["scope"]["tested_scope"] = value["scope"]["intended_uses"]
            with self.assertRaisesRegex(Invalid, "shared container"):
                ToolAssessment(**value) if typed else decode_content(value)
            value = constructor_fields() if typed else wire()
            value["limitations"]["value"].append(value)
            with self.assertRaisesRegex(Invalid, "cyclic"):
                ToolAssessment(**value) if typed else decode_content(value)
        fields = constructor_fields()
        pins = fields["environment"]["records"]["value"]
        pins[2] = pins[0]
        self.assertEqual(ToolAssessment(**fields), assessment())
        fields["scope"]["tested_scope"] = deepcopy(fields["scope"]["intended_uses"])
        ToolAssessment(**fields)

    def test_hostile_subclasses_metaclasses_and_unadvanced_generator(self):
        """Reject aliases before iteration, conversion, serialization or metaclass dispatch."""
        for meta in (EqualityMeta, HashMeta):
            for base, payload in ((dict, {}), (list, []), (tuple, ()), (str, "data"), (int, 1)):
                hostile = meta("Hostile", (base,), {"__doc__": "Inert rejection probe.",
                                "__iter__": trap, "items": trap, "__str__": trap, "to_dict": trap})
                value = wire()
                value["limitations"] = hostile(payload)
                with self.assertRaises(Invalid):
                    decode_content(value)
            for base in (ArtifactReference, RecordReference, ToolAssessment, ToolAssessmentLimits):
                hostile = meta("Hostile", (base,), {"__doc__": "Inert typed rejection probe.", "to_dict": trap})
                instance = object.__new__(hostile)
                with self.assertRaises(Invalid):
                    if base is ToolAssessment:
                        dumps_content(instance)
                    elif base is ToolAssessmentLimits:
                        decode_content({}, limits=instance)
                    else:
                        fields = constructor_fields()
                        fields["target"]["release"] = instance
                        ToolAssessment(**fields)
        iterator = (trap() for _ in range(1))
        value = wire()
        value["limitations"] = iterator
        with self.assertRaises(Invalid):
            decode_content(value)
        self.assertRaises(AssertionError, next, iterator)

    def test_json_grammar_scalars_duplicates_and_discriminator_precedence(self):
        """Reject malformed external values before semantic reconstruction, retaining -0 normalization."""
        for text in ('{"a":1,"\\u0061":2}', '{"a":{"b":1,"b":2}}', "true", "1.0", "NaN", "Infinity",
                     "-1", "9223372036854775808", '"\\ud800"', '"\\udc00"', '[1,]', '{"a":1,}', b'\xff'):
            with self.subTest(text=text):
                with self.assertRaises(Invalid):
                    loads_content(text)
        for bad in (True, 1.0, 0, 2, "1"):
            value = wire()
            value["version"] = bad
            with self.assertRaises(Invalid):
                decode_content(value)
        for field in ("format", "kind", "assessment_id"):
            value = wire()
            value[field] = "unsupported value"
            with self.assertRaises(Invalid):
                decode_content(value)
        with self.assertRaises(NotTypedContentError):
            decode_content({})
        with self.assertRaises(Invalid):
            decode_content({"bad": True})
        value = wire()
        value["environment"]["artifacts"]["value"][0]["size"] = 0
        value["lifecycle"]["evidence"]["value"][0]["artifacts"]["value"][-1]["size"] = 0
        text = canonical(value).replace('"size":0', '"size":-0')
        self.assertEqual(loads_content(text).to_dict(), value)

    def test_all_retained_consumers_reject_forgery_and_missing_fields(self):
        """Revalidate canonical content through properties, equality and every public consumer."""
        original = assessment()
        for text in (None, b"{}", "{}", " " + original._json, original._json + "\n", original._json.replace('"version":1', '"version":true')):
            value = forged(original, _json=text)
            for consume in (ToolAssessment.to_dict, dumps_content, lambda x: x.assessment_id,
                            lambda x: ToolAssessment.__eq__(x, object()), lambda x: ToolAssessment.__eq__(original, x)):
                with self.subTest(text=type(text), consume=consume):
                    with self.assertRaises((Invalid, NotTypedContentError)):
                        consume(value)
        value = object.__new__(ToolAssessment)
        with self.assertRaises(Invalid):
            value.to_dict()
        changed = wire()
        changed["attribution"]["actor"] = known("Someone else")
        coherent = forged(original, _json=canonical(changed))
        self.assertEqual(coherent.to_dict(), changed)  # Local consistency cannot authenticate authorship.
        self.assertNotEqual(coherent, original)
        with patch.object(ToolAssessment, "to_dict", trap):
            self.assertRaises(AssertionError, dumps_content, original)

    def test_no_supplied_serializer_hooks_are_used(self):
        """Ignore exact instance serializer overrides and consume only validated raw fields."""
        fields = constructor_fields()
        pin = fields["target"]["release"]
        object.__setattr__(pin, "to_dict", trap)
        with patch.object(RecordReference, "to_dict", trap), patch.object(ArtifactReference, "to_dict", trap):
            self.assertEqual(ToolAssessment(**fields).to_dict(), wire())
        content = assessment()
        object.__setattr__(content, "to_dict", trap)
        self.assertEqual(loads_content(dumps_content(content)), content)

    def test_passive_construction_and_conversion_never_consult_external_state(self):
        """Host APIs and shell-like authored text remain inert after imports."""
        value, fields = wire(), constructor_fields()
        targets = [("builtins.open", trap), ("os.getenv", trap), ("os.getcwd", trap),
                   ("os.stat", trap), ("socket.socket", trap), ("subprocess.Popen", trap),
                   ("time.time", trap), ("sqlite3.connect", trap)]
        from contextlib import ExitStack
        with ExitStack() as stack:
            for target, replacement in targets:
                stack.enter_context(patch(target, replacement))
            content = ToolAssessment(**fields)
            self.assertEqual(decode_content(value), content)
            self.assertEqual(loads_content(dumps_content(content)), content)

    def test_constructor_raw_pin_forgeries_and_exact_scalar_aliases(self):
        """Reject missing/bypassed pin fields, scalar subclasses, booleans and nonfinite values inertly."""
        for slot, pin_class, field in (("target", RecordReference, "revision"),
                                       ("artifact", ArtifactReference, "size")):
            for bad in (True, False, 1.5, float("inf"), float("nan"), -1, 2**63):
                fields = constructor_fields()
                pin = fields["target"]["release"] if slot == "target" else fields["environment"]["artifacts"]["value"][0]
                object.__setattr__(pin, field, bad)
                with self.assertRaises(Invalid):
                    ToolAssessment(**fields)
            fields = constructor_fields()
            pin = object.__new__(pin_class)
            if slot == "target":
                fields["target"]["release"] = pin
            else:
                fields["environment"]["artifacts"]["value"][0] = pin
            with self.assertRaises(Invalid):
                ToolAssessment(**fields)
            fields = constructor_fields()
            pin = fields["target"]["release"] if slot == "target" else fields["environment"]["artifacts"]["value"][0]
            object.__delattr__(pin, field)
            with self.assertRaises(Invalid):
                ToolAssessment(**fields)
        for base, scalar in ((str, "assessment"), (int, 1)):
            alias = type("ScalarAlias", (base,), {"__doc__": "Scalar coercion trap.", "__str__": trap, "__int__": trap})
            value = wire()
            value["assessment_id" if base is str else "version"] = alias(scalar)
            with self.assertRaises(Invalid):
                decode_content(value)
        alias = type("KeyAlias", (str,), {"__doc__": "Dictionary-key alias probe.", "__eq__": trap, "__hash__": str.__hash__})
        with self.assertRaises(Invalid):
            decode_content({alias("format"): "research_pipeline.tool_assessment_content"})

    def test_lookalikes_and_exact_class_consumption(self):
        """Reject serialization lookalikes and subclass decoders without invoking their methods."""
        lookalike = type("Lookalike", (), {"__doc__": "Untrusted serialization/iteration lookalike.",
                                          "to_dict": trap, "from_dict": trap, "__iter__": trap, "__str__": trap})()
        for consume in (lambda: decode_content(lookalike), lambda: loads_content(lookalike),
                        lambda: dumps_content(lookalike), lambda: ToolAssessment.to_dict(lookalike)):
            with self.assertRaises(Invalid):
                consume()
        fields = constructor_fields()
        fields["target"]["release"] = lookalike
        with self.assertRaises(Invalid):
            ToolAssessment(**fields)
        for meta in (EqualityMeta, HashMeta):
            subclass = meta("AssessmentAlias", (ToolAssessment,), {"__doc__": "Classmethod receiver probe."})
            with self.assertRaises(Invalid):
                subclass.from_dict(wire())
            with self.assertRaises(Invalid):
                subclass(**constructor_fields())
            self.assertIs(ToolAssessment.__eq__(assessment(), object.__new__(subclass)), NotImplemented)

    def test_shared_wire_pins_lists_and_constructor_tuples_are_rejected(self):
        """Alias rejection applies to pin dictionaries and all ordered container positions."""
        value = wire()
        records = value["environment"]["records"]["value"]
        records[2] = records[0]
        with self.assertRaisesRegex(Invalid, "shared container"):
            decode_content(value)
        for as_tuple in (False, True):
            fields = constructor_fields()
            shared = ("same",) if as_tuple else ["same"]
            fields["scope"]["intended_uses"] = known(shared)
            fields["scope"]["tested_scope"] = known(shared)
            with self.assertRaisesRegex(Invalid, "shared container"):
                ToolAssessment(**fields)

    def test_remaining_review_modes_and_evidence_code_paths(self):
        """Exercise each review outcome and both independence modes without added implications."""
        for outcome in ("unperformed", "pass", "fail", "inconclusive"):
            value = wire()
            value["reviews"]["value"][0]["outcome"] = outcome
            self.assertEqual(decode_content(value).to_dict(), value)
        for name in ("requested_mode", "reported_mode"):
            for mode in ("answer_blind_reconstruction", "proof_blind_reconstruction", "candidate_aware_audit", "invalid"):
                value = wire()
                value["reviews"]["value"][0]["independence"][name] = known(mode)
                if mode == "invalid":
                    with self.assertRaises(Invalid):
                        decode_content(value)
                else:
                    decode_content(value)
        value = wire()
        value["reviews"]["value"][0]["outcome"] = "invalid"
        with self.assertRaises(Invalid):
            decode_content(value)
        value = wire()
        value["issues"]["value"][0]["evidence"]["value"][0]["basis"] = "invalid"
        with self.assertRaises(Invalid):
            decode_content(value)
        for dimension in DIMENSIONS:
            value = wire()
            value["qualification"][dimension]["outcome"] = "invalid"
            with self.assertRaises(Invalid):
                decode_content(value)
