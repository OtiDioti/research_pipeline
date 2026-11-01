"""Closed resource codec and exact provisioning arithmetic boundaries."""

import copy
from dataclasses import FrozenInstanceError
import unittest

from research_pipeline.resources import (
    Dimension, ResourceRequest, ResourceValidationError, MAX_QUANTITY,
    ResourceInspectionLimits, ScopeReference, dumps_request, loads_request,
    validate_run_policy, validate_call_envelope, by_kind,
)
from tests.resource_fixtures import DIMENSIONS, allocation, policy, vector, root_request, reservation


class ResourceCodecTests(unittest.TestCase):
    """Exercise wire completeness and bounded exact arithmetic without database effects."""

    def test_round_trips_detachment_and_dimension_order(self):
        """Strict wire round trips sort dimensions/vectors while retaining reference array order."""
        for item in (root_request(), allocation("run", "run", "project"), reservation()):
            self.assertEqual(loads_request(dumps_request(item)), item)
            doc = item.to_dict()
            doc["payload"]["owner_id"] = "other"
            self.assertEqual(item.to_dict()["payload"]["owner_id"], "owner")
            with self.assertRaises(FrozenInstanceError):
                item._json = "{}"
        root = root_request().to_dict()
        root["payload"]["dimensions"].reverse()
        root["payload"]["ceiling"].reverse()
        self.assertEqual(ResourceRequest.from_dict(root), root_request())
        for dim in DIMENSIONS:
            self.assertEqual(Dimension.from_dict(dim).to_dict(), dim)
        for kind in ("run", "branch", "attempt"):
            scope = ScopeReference({"type": "controller", "kind": kind, "stable_identity": "scope"})
            self.assertEqual(ScopeReference.from_dict(scope.to_dict()), scope)

    def test_mandatory_closed_handoff_bounds(self):
        """Absent/null/malformed/unknown bounds and all invalid scalar types are rejected."""
        original = allocation("run", "run", "project").to_dict()
        candidates = [None, [], {}, {"max_input_tokens_per_call": 3},
                      {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5, "extra": 0}]
        for key, values in (("max_input_tokens_per_call", (True, False, -1, MAX_QUANTITY + 1, 3.0, "3", None)),
                            ("max_output_tokens_per_call", (True, False, -1, 0, MAX_QUANTITY + 1, 5.0, "5", None))):
            for value in values:
                bounds = {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5}
                bounds[key] = value
                candidates.append(bounds)
        for bounds in candidates:
            doc = copy.deepcopy(original)
            doc["payload"]["run_policy"]["handoff_call_bounds"] = bounds
            with self.subTest(bounds=bounds), self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
        del original["payload"]["run_policy"]["handoff_call_bounds"]
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(original)
        text = dumps_request(allocation("run", "run", "project"))
        for old, new in (('"max_input_tokens_per_call":3', '"max_input_tokens_per_call":3,"max_input_tokens_per_call":3'),
                         ('"max_output_tokens_per_call":5', '"max_output_tokens_per_call":5,"max_output_tokens_per_call":5')):
            with self.assertRaises(ResourceValidationError):
                loads_request(text.replace(old, new))

    def test_exact_context_products_shortfalls_surplus_and_zero_input(self):
        """Provisioning uses N*i/N*o exactly, permits surplus and never infers call bounds."""
        validate_run_policy(policy(), DIMENSIONS)
        for updates in ({"context_capacity_tokens": 7}, {"per_call_output_tokens": 4},
                        {"per_call_output_tokens": 9},
                        {"handoff_minimum": vector(model_calls=2, model_input_tokens=5, model_output_tokens=10, local_time=1, local_storage=1)},
                        {"handoff_minimum": vector(model_calls=2, model_input_tokens=6, model_output_tokens=9, local_time=1, local_storage=1)}):
            with self.subTest(updates=updates), self.assertRaises(ResourceValidationError):
                validate_run_policy(policy(**updates), DIMENSIONS)
        validate_run_policy(policy(handoff_minimum=vector(model_calls=2, model_input_tokens=100, model_output_tokens=100,
                                                         local_time=1, local_storage=1)), DIMENSIONS)
        zero = policy(handoff_call_bounds={"max_input_tokens_per_call": 0, "max_output_tokens_per_call": 5},
                      handoff_minimum=vector(model_calls=2, model_input_tokens=1, model_output_tokens=10, local_time=1, local_storage=1))
        validate_run_policy(zero, DIMENSIONS)
        zero["handoff_minimum"] = vector(model_calls=2, model_input_tokens=0, model_output_tokens=10, local_time=1, local_storage=1)
        with self.assertRaises(ResourceValidationError):
            validate_run_policy(zero, DIMENSIONS)

    def test_exact_integer_boundary_and_independent_product_overflow(self):
        """Individually valid operands cannot overflow either cumulative product unnoticed."""
        values = by_kind(vector(model_calls=MAX_QUANTITY, model_input_tokens=MAX_QUANTITY,
                                model_output_tokens=MAX_QUANTITY), DIMENSIONS)
        validate_call_envelope(values, {"max_input_tokens_per_call": 1, "max_output_tokens_per_call": 1}, 2, 1)
        for i, o in ((2, 1), (1, 2)):
            with self.subTest(i=i, o=o), self.assertRaises(ResourceValidationError):
                validate_call_envelope(values, {"max_input_tokens_per_call": i, "max_output_tokens_per_call": o}, 3, 2)
        validate_call_envelope(by_kind(vector(model_calls=1, model_input_tokens=0, model_output_tokens=MAX_QUANTITY), DIMENSIONS),
                              {"max_input_tokens_per_call": 0, "max_output_tokens_per_call": MAX_QUANTITY}, MAX_QUANTITY, MAX_QUANTITY)
        with self.assertRaises(ResourceValidationError):
            validate_call_envelope(values, {"max_input_tokens_per_call": MAX_QUANTITY, "max_output_tokens_per_call": 1}, MAX_QUANTITY, MAX_QUANTITY)

    def test_complete_fields_types_depth_unicode_and_forged_values(self):
        """Every request layer is closed; frozen construction and JSON depth cannot bypass checks."""
        original = root_request().to_dict()
        for path in ((), ("payload",), ("provenance",), ("payload", "scope"), ("payload", "policy")):
            for mode in ("extra", "missing"):
                doc = copy.deepcopy(original)
                target = doc
                for key in path:
                    target = target[key]
                if mode == "extra":
                    target["unknown"] = 1
                else:
                    del target[next(iter(target))]
                with self.subTest(path=path, mode=mode), self.assertRaises(ResourceValidationError):
                    ResourceRequest.from_dict(doc)
        for text in ('{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}', '"\\ud800"', '[' * 20 + '0' + ']' * 20):
            with self.assertRaises(ResourceValidationError):
                loads_request(text)
        doc = copy.deepcopy(original)
        doc["provenance"]["details"] = {"x": "x" * 65536}
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)
        for text in ('{}', '{"x":1,"x":2}'):
            forged = object.__new__(ResourceRequest)
            object.__setattr__(forged, "_json", text)
            with self.assertRaises(ResourceValidationError):
                dumps_request(forged)
        for bad in (True, 0, -1, "1", MAX_QUANTITY + 1):
            with self.assertRaises(ResourceValidationError):
                ResourceInspectionLimits(bad, 1, 1)

    def test_dimensions_currency_aliases_units_and_vector_completeness(self):
        """Dimension aliases, ambiguous scales and incomplete vectors cannot become budgets."""
        original = root_request().to_dict()
        candidates = []
        for dimension_updates in ({"unit": "second"}, {"scale": True}, {"currency": "USD"}, {"kind": "unknown"}):
            doc = copy.deepcopy(original)
            doc["payload"]["dimensions"][0].update(dimension_updates)
            candidates.append(doc)
        doc = copy.deepcopy(original)
        doc["payload"]["dimensions"].append(doc["payload"]["dimensions"][0].copy())
        candidates.append(doc)
        for location in ("dimensions", "ceiling"):
            doc = copy.deepcopy(original)
            doc["payload"][location].pop()
            candidates.append(doc)
        for value in (True, -1, MAX_QUANTITY + 1, "1", 1.0):
            doc = copy.deepcopy(original)
            doc["payload"]["ceiling"][0]["quantity"] = value
            candidates.append(doc)
        for doc in candidates:
            with self.subTest(doc=doc), self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
        money = {"dimension_id": "usd", "kind": "monetary", "unit": "currency_quantum", "currency": "USD", "scale": 1000000}
        self.assertEqual(Dimension.from_dict(money).to_dict(), money)
        for change in ({"scale": 0}, {"scale": 10**9 + 1}, {"currency": "usd"}, {"unit": "dollar"}):
            with self.assertRaises(ResourceValidationError):
                Dimension.from_dict({**money, **change})
        doc = copy.deepcopy(original)
        doc["payload"]["dimensions"] += [money, {**money, "dimension_id": "usd_alias", "scale": 100}]
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)

    def test_exact_request_size_depth_reference_and_statement_boundaries(self):
        """Inclusive finite bounds accept equality and reject one extra byte/container/reference."""
        doc = root_request().to_dict()
        doc["provenance"]["details"] = {"padding": ""}
        empty = dumps_request(ResourceRequest.from_dict(doc))
        doc["provenance"]["details"]["padding"] = "x" * (65536 - len(empty))
        self.assertEqual(len(dumps_request(ResourceRequest.from_dict(doc))), 65536)
        doc["provenance"]["details"]["padding"] += "x"
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)
        doc = root_request().to_dict()
        nested = 0
        for _ in range(14):
            nested = {"nested": nested}
        doc["provenance"]["details"] = nested
        ResourceRequest.from_dict(doc)
        doc["provenance"]["details"] = {"extra": nested}
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)
        doc = root_request().to_dict()
        ref = {"record_id": "policy", "revision": 1, "relationship": "resource_policy", "target_kind": "evidence"}
        doc["policy_references"] = [ref] * 32
        ResourceRequest.from_dict(doc)
        doc["policy_references"].append(ref)
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)
        doc = root_request().to_dict()
        doc["payload"]["policy"]["statement"] = "x" * 4096
        ResourceRequest.from_dict(doc)
        doc["payload"]["policy"]["statement"] += "x"
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)
