"""Strict usage evidence, cumulative settlement, exact overflow and sticky admission boundaries."""

import copy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.backup import create_backup, restore_backup
from research_pipeline.resources import (
    MAX_QUANTITY, UNCERTAINTY_EVENTS, ResourceCapacityError, ResourceConflictError,
    ResourceInspectionLimits, ResourceInspectionLimitError,
    ResourceRequest, ResourceSnapshot, ResourceValidationError, canonical,
    dumps_request, loads_request, dumps_receipt, loads_receipt,
)
from research_pipeline.store import RecordStore
from tests.resource_fixtures import (
    LIMITS, allocation, changed, observation, populate,
    reconciliation, reservation, root_request, scope, vector,
)
from tests.test_store import record, request


class ResourceUsageTests(unittest.TestCase):
    """Assert public accounting outcomes without treating synthetic evidence as provider authority."""

    def setUp(self):
        """Create independently funded attempts and an original ten-tool-call commitment."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        populate(self.store, attempts=2)
        self.work = reservation(maxima=vector(tool_calls=10))
        self.original_receipt = self.store.reserve_resources(self.work)

    def snapshot(self):
        """Return the complete detached public observation."""
        return self.store.inspect_resources(limits=LIMITS).to_dict()

    def usage(self, reservation_id="reservation_work", kind="tool_calls"):
        """Select one original reservation's derived dimension and status."""
        row = next(r for r in self.snapshot()["reservation_usage"] if r["reservation_id"] == reservation_id)
        dimension = next(d for d in row["dimensions"] if d["dimension_id"] == "dim_" + kind)
        return row, dimension

    def balance(self, account="attempt", purpose="ordinary", kind="tool_calls"):
        """Resolve a public dimension row and its local/root admission indicators."""
        row = next(r for r in self.snapshot()["balances"] if r["account_id"] == account and r["purpose"] == purpose)
        return row, next(d for d in row["dimensions"] if d["dimension_id"] == "dim_" + kind)

    def test_partial_and_explicit_final_settlement_preserve_delegation(self):
        """M=10,K=4 charges 4+6, then final K=6 charges 6+0 with unchanged parent allocation."""
        original = self.snapshot()
        partial = observation(usage=vector(None, tool_calls=4))
        result = self.store.observe_resource_usage(partial)
        self.assertEqual(self.store.observe_resource_usage(partial), result)
        row, usage = self.usage()
        self.assertEqual(row["status"], "unresolved")
        self.assertEqual((usage["observed_quantity"], usage["known_spent"], usage["remaining_reserved"], usage["charged_total"]), ("4", "4", "6", "10"))
        self.assertIsNone(usage["actual_usage"])
        self.assertIsNone(self.usage(kind="local_storage")[1]["observed_quantity"])
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion", usage=vector(tool_calls=6)))
        self.assertEqual(self.usage()[1]["remaining_reserved"], "4")
        settled = self.store.reconcile_resource_usage(reconciliation())
        self.assertEqual(self.store.reconcile_resource_usage(reconciliation()), settled)
        row, usage = self.usage()
        self.assertEqual(row["status"], "authoritative")
        self.assertEqual((usage["known_spent"], usage["remaining_reserved"], usage["charged_total"], usage["actual_usage"]), ("6", "0", "6", "6"))
        self.assertEqual(row["latest_observation_operation_id"], "op_complete")
        self.assertEqual(row["latest_receipt_operation_id"], "op_complete")
        self.assertEqual(row["latest_reconciliation_operation_id"], "op_settlement")
        self.assertEqual(self.balance()[1]["available_for_local_use"], "19")
        self.assertTrue(self.balance()[0]["usage_complete"])
        for account, purpose in (("task", "ordinary"), ("run", "ordinary"), ("project", "total")):
            old = next(r for r in original["balances"] if r["account_id"] == account and r["purpose"] == purpose)
            new = self.balance(account, purpose)[0]
            self.assertEqual([d["delegated_to_children"] for d in old["dimensions"]],
                             [d["delegated_to_children"] for d in new["dimensions"]])
        self.assertEqual(original["reservations"], self.snapshot()["reservations"])

    def test_every_uncertainty_and_narrative_retains_liability_and_knowledge(self):
        """Loss, timeout, cancellation, expiry, error and narrative neither erase known usage nor settle."""
        self.store.observe_resource_usage(observation(usage=vector(None, tool_calls=4)))
        for event in (*UNCERTAINTY_EVENTS, "worker_narrative"):
            with self.subTest(event=event):
                self.store.observe_resource_usage(observation(event, event=event))
                row, usage = self.usage()
                self.assertEqual(row["latest_observation_operation_id"], "op_" + event)
                self.assertEqual(row["latest_receipt_operation_id"], "op_partial")
                self.assertEqual((usage["known_spent"], usage["remaining_reserved"], usage["charged_total"]), ("4", "6", "10"))
        with self.assertRaises(ResourceCapacityError):
            self.store.reserve_resources(reservation("replacement", maxima=vector(tool_calls=16)))
        self.store.reserve_resources(reservation("independent", maxima=vector(tool_calls=15)))

    def test_conservative_unknown_charge_and_later_measured_refinement(self):
        """Conservative settlement charges M without inventing measured zero; only newer completion refines."""
        conservative = reconciliation("conservative", mode="conservative", observation_operation_id=None)
        self.store.reconcile_resource_usage(conservative)
        row, usage = self.usage()
        self.assertEqual(row["status"], "conservative")
        self.assertEqual((usage["known_spent"], usage["remaining_reserved"], usage["conservative_excess"]), ("0", "0", "10"))
        self.assertIsNone(usage["observed_quantity"])
        self.assertIsNone(usage["actual_usage"])
        self.assertFalse(self.balance()[0]["usage_complete"])
        self.assertEqual(self.balance()[1]["unknown_reservation_ids"], ["reservation_work"])
        self.store.observe_resource_usage(observation(usage=vector(None, tool_calls=4)))
        self.assertEqual(self.usage()[1]["conservative_excess"], "6")
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion", usage=vector(tool_calls=6)))
        with self.assertRaises(ResourceConflictError):
            self.store.reconcile_resource_usage(reconciliation())
        self.store.reconcile_resource_usage(reconciliation(previous="op_conservative"))
        self.assertEqual(self.usage()[1]["charged_total"], "6")
        self.assertEqual(self.store.reconcile_resource_usage(conservative).to_dict()["operation_id"], "op_conservative")

    def test_authoritative_zero_replacements_and_permanent_attempt_allocation(self):
        """Measured zero frees direct liability but cannot refund a task's delegation for a new attempt."""
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion", usage=vector()))
        self.assertEqual(self.balance()[1]["available_for_local_use"], "15")
        self.store.observe_resource_usage(observation("uncertain", event="timeout"))
        self.store.reconcile_resource_usage(reconciliation())
        self.assertEqual(self.usage()[1]["actual_usage"], "0")
        self.store.reserve_resources(reservation("replacement", maxima=vector(tool_calls=25)))
        with self.assertRaises(ResourceCapacityError):
            self.store.allocate_resources(allocation("attempt", "successor", "task"))

    def test_stale_foreign_redundant_and_unavailable_settlement_evidence(self):
        """Explicit latest evidence and predecessor checks reject stale or redundant new identities."""
        invalid = [reconciliation(), reconciliation(mode="conservative"),
                   reconciliation(observation_operation_id=None), reconciliation(previous="op_missing")]
        self.store.observe_resource_usage(observation())
        invalid += [reconciliation(observation_operation_id="op_partial")]
        before = self.snapshot()
        for candidate in invalid:
            with self.assertRaises(ResourceConflictError):
                self.store.reconcile_resource_usage(candidate)
        self.assertEqual(self.snapshot(), before)
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion"))
        self.store.reconcile_resource_usage(reconciliation("conservative", mode="conservative", observation_operation_id="op_complete"))
        with self.assertRaises(ResourceConflictError):
            self.store.reconcile_resource_usage(reconciliation(previous="op_conservative"))
        self.store.observe_resource_usage(observation("new_complete", event="authoritative_completion"))
        self.store.reconcile_resource_usage(reconciliation(previous="op_conservative", observation_operation_id="op_new_complete"))
        for mode in ("authoritative", "conservative"):
            with self.assertRaises(ResourceConflictError):
                self.store.reconcile_resource_usage(reconciliation("redundant", mode=mode, previous="op_settlement", observation_operation_id="op_new_complete"))

    def test_late_receipts_reopen_liability_and_breach_is_sticky(self):
        """A late increase after measured completion preserves both claims and restores unresolved liability."""
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion", usage=vector(tool_calls=6)))
        self.store.reconcile_resource_usage(reconciliation())
        self.store.observe_resource_usage(observation("same_total", usage=vector(None, tool_calls=6)))
        self.assertEqual(self.snapshot()["breaches"], [])
        self.store.observe_resource_usage(observation("timeout", event="timeout"))
        self.assertEqual(self.usage()[0]["status"], "authoritative")
        late = observation("late", usage=vector(None, tool_calls=7))
        result = self.store.observe_resource_usage(late)
        self.assertEqual(self.usage()[0]["status"], "unresolved")
        self.assertEqual((self.usage()[1]["known_spent"], self.usage()[1]["remaining_reserved"]), ("7", "3"))
        breaches = self.snapshot()["breaches"]
        self.assertEqual(breaches[0]["reason"], "post_settlement_usage")
        self.assertEqual((breaches[0]["observed"], breaches[0]["limit"]), ("7", "6"))
        self.assertTrue(self.balance("attempt2")[0]["admission_blocked"])
        self.assertFalse(self.balance("attempt2")[0]["breach"])
        self.assertEqual(self.store.observe_resource_usage(late), result)
        self.assertEqual(self.store.reserve_resources(self.work), self.original_receipt)
        for purpose in ("ordinary", "verification", "handoff"):
            with self.assertRaisesRegex(ResourceCapacityError, "project"):
                self.store.reserve_resources(reservation("blocked", account="attempt2", purpose=purpose))
        with self.assertRaises(ResourceCapacityError):
            self.store.allocate_resources(allocation("run", "sibling", "project"))
        self.store.observe_resource_usage(observation("late_complete", event="authoritative_completion", usage=vector(tool_calls=7)))
        self.store.reconcile_resource_usage(reconciliation("late_settled", previous="op_settlement", observation_operation_id="op_late_complete"))
        self.assertEqual(self.snapshot()["breaches"], breaches)
        self.assertTrue(self.balance()[0]["admission_blocked"])
        self.assertEqual(self.usage()[1]["actual_usage"], "7")

    def test_excess_propagates_exactly_and_unrelated_project_remains_usable(self):
        """Over-allocation usage propagates as child overrun through purpose and project ceilings."""
        self.store.observe_resource_usage(observation("overrun", usage=vector(None, tool_calls=1100)))
        data = self.snapshot()
        facts = {(f["account_id"], f["purpose"], f["reason"]) for f in data["breaches"]}
        for account, purpose in (("attempt", "ordinary"), ("task", "ordinary"), ("run", "ordinary"), ("project", "total")):
            self.assertIn((account, purpose, "ceiling_excess"), facts)
        self.assertEqual(self.balance("task")[1]["child_overrun"], "1075")
        self.assertEqual(self.balance("project", "total")[1]["available_for_local_use"], "-215")
        self.store.submit(request("other_scope", [record("other_project", kind="project")]))
        doc = root_request(account_id="other_project", scope=scope("project", "other_project")).to_dict()
        doc.update(operation_id="other_root", receipt_id="other_root_receipt")
        self.store.create_resource_account(ResourceRequest.from_dict(doc))
        self.store.allocate_resources(allocation("run", "other_run", "other_project"))
        self.assertFalse(self.balance("other_project", "total")[0]["admission_blocked"])

    def test_conservative_late_increase_never_releases_capacity(self):
        """A bounded late bill raises the conservative charge even when it exceeds its original maximum."""
        self.store.reconcile_resource_usage(reconciliation(mode="conservative", observation_operation_id=None))
        self.store.observe_resource_usage(observation("late", usage=vector(None, tool_calls=12)))
        row, usage = self.usage()
        self.assertEqual(row["status"], "conservative")
        self.assertEqual((usage["known_spent"], usage["conservative_excess"], usage["charged_total"], usage["remaining_reserved"]), ("12", "0", "12", "0"))
        self.assertIsNone(usage["actual_usage"])
        self.assertTrue(self.balance()[0]["admission_blocked"])

    def test_call_samples_and_nested_telemetry_are_evidence_not_added_usage(self):
        """Only individual samples establish call/context breaches; telemetry and repeats add no charges."""
        self.store.reserve_resources(reservation("model", maxima=vector(model_calls=2, model_input_tokens=6, model_output_tokens=10),
            call_bounds={"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5}))
        item = observation("sample", "reservation_model", usage=vector(model_calls=2, model_input_tokens=6, model_output_tokens=10),
            telemetry={"cached_input_tokens": 5, "reasoning_output_tokens": 7},
            call_observation={"call_id": "call_one", "input_tokens": 4, "output_tokens": 6})
        self.store.observe_resource_usage(item)
        self.store.observe_resource_usage(observation("repeated", "reservation_model", **{k: v for k, v in item.to_dict()["payload"].items() if k not in ("evidence", "reservation_id")}))
        self.assertEqual(self.usage("reservation_model", "model_output_tokens")[1]["known_spent"], "10")
        facts = self.snapshot()["breaches"]
        self.assertEqual({f["reason"] for f in facts}, {"per_call_bound", "context_bound", "run_output_bound"})
        context = next(f for f in facts if f["reason"] == "context_bound")
        self.assertEqual((context["dimension_id"], context["observed"], context["limit"]), ("dim_model_input_tokens", "10", "8"))
        self.assertTrue(all(f["trigger_operation_id"] == "op_sample" for f in facts))

    def test_aggregate_overflow_receipts_reopen_and_exact_restore(self):
        """Pre-admitted work retains individually bounded bills whose measured sum exceeds B."""
        self.store.reserve_resources(reservation("second"))
        receipts = []
        for identity, rid in (("large_first", "reservation_work"), ("large_second", "reservation_second")):
            item = observation(identity, rid, event="authoritative_completion", usage=vector(tool_calls=MAX_QUANTITY))
            receipts.append((item, self.store.observe_resource_usage(item)))
            self.store.reconcile_resource_usage(reconciliation(identity + "_settled", rid, observation_operation_id=item.operation_id))
        self.assertEqual(self.balance()[1]["known_spent"], str(2 * MAX_QUANTITY))
        self.assertEqual(self.balance()[1]["actual_usage"], str(2 * MAX_QUANTITY))
        self.assertEqual(self.balance()[1]["available_for_local_use"], str(25 - 2 * MAX_QUANTITY))
        self.assertIn("aggregate_known_overflow", {f["reason"] for f in self.snapshot()["breaches"]})
        observed = self.store.inspect_resources(limits=LIMITS)
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.inspect_resources(limits=LIMITS), observed)
            for item, receipt in receipts:
                self.assertEqual(reopened.observe_resource_usage(item), receipt)
            create_backup(reopened, self.parent / "overflow_backup")
        with restore_backup(self.parent / "overflow_backup", self.parent / "restored") as restored:
            self.assertEqual(restored.inspect_resources(limits=LIMITS), observed)
            for item, receipt in receipts:
                self.assertEqual(restored.get_resource_operation(item.operation_id), receipt)
            self.assertEqual((self.parent / "restored/metadata.sqlite3").read_bytes(),
                             (self.parent / "overflow_backup/snapshot.sqlite3").read_bytes())

    def test_strict_codecs_fields_bounds_and_forged_objects(self):
        """Both new variants reject unknown/duplicate fields, coercions, invalid Unicode and forged JSON."""
        for item in (observation(), reconciliation()):
            self.assertEqual(loads_request(dumps_request(item)), item)
            for section in (None, "payload", "provenance"):
                for missing in (False, True):
                    doc = item.to_dict()
                    target = doc if section is None else doc[section]
                    if missing:
                        del target[next(iter(target))]
                    else:
                        target["unknown"] = 0
                    with self.assertRaises(ResourceValidationError):
                        ResourceRequest.from_dict(doc)
            with self.assertRaises(ResourceValidationError):
                loads_request(dumps_request(item).replace('"owner_id":"owner"', '"owner_id":"owner","owner_id":"owner"'))
            doc = item.to_dict()
            doc["payload"]["owner_id"] = True
            forged = object.__new__(ResourceRequest)
            object.__setattr__(forged, "_json", canonical(doc))
            method = self.store.observe_resource_usage if doc["kind"] == "observe" else self.store.reconcile_resource_usage
            with self.assertRaises(ResourceValidationError):
                method(forged)
            with self.assertRaises(ResourceValidationError):
                method(object())
        for bad in (True, -1, MAX_QUANTITY + 1, 1.5, "1", float("inf")):
            with self.subTest(bad=bad), self.assertRaises(ResourceValidationError):
                observation(usage=vector(tool_calls=bad))
            with self.assertRaises(ResourceValidationError):
                observation(telemetry={"cached_input_tokens": bad, "reasoning_output_tokens": None})
            with self.assertRaises(ResourceValidationError):
                observation(call_observation={"call_id": "call", "input_tokens": bad, "output_tokens": 0})
        for bad in ("", "x" * 4097, "\ud800"):
            with self.assertRaises(ResourceValidationError):
                reconciliation(reason=bad)
        variants = [dict(usage=vector(None)), dict(usage=vector(None), event="authoritative_completion"),
                    dict(event="timeout"), dict(event="worker_narrative", usage=vector()),
                    dict(evidence={"source_kind": "provider", "source_id": "src", "source_receipt_id": "id", "statement": "claim"}),
                    dict(telemetry={"cached_input_tokens": None}), dict(call_observation={"call_id": "call", "input_tokens": 1})]
        for updates in variants:
            # Event helpers intentionally choose valid shapes; force the raw incompatible payload below.
            doc = observation().to_dict()
            doc["payload"].update(updates)
            with self.subTest(updates=updates), self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
        for key in ("usage", "evidence", "telemetry", "call_observation"):
            doc = observation(call_observation={"call_id": "call", "input_tokens": 0, "output_tokens": 0}).to_dict()
            target = doc["payload"][key]
            if key == "usage":
                target[0]["unknown"] = 1
            else:
                target["unknown"] = 1
            with self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
        with self.assertRaises(ResourceValidationError):
            self.store.observe_resource_usage(reconciliation())
        with self.assertRaises(ResourceValidationError):
            self.store.reconcile_resource_usage(observation())

    def test_semantic_conflicts_leave_no_operation_and_source_identity_is_global(self):
        """Wrong attribution, foreign units, decreasing totals and aliased external receipts never write."""
        original = observation(usage=vector(None, tool_calls=4))
        receipt = self.store.observe_resource_usage(original)
        self.assertEqual(loads_receipt(dumps_receipt(receipt)), receipt)
        candidates = [observation("bad", usage=vector(None, tool_calls=3)),
                      changed(original, owner_id="other"), observation("bad", account_id="attempt2"),
                      observation("bad", reservation_id="missing"), observation("bad", usage=vector()[:-1]),
                      observation("bad", usage=vector(model_input_tokens=1)),
                      observation("bad", usage=vector(None, tool_calls=4), telemetry={"cached_input_tokens": 0, "reasoning_output_tokens": None}),
                      observation("bad", usage=vector(None, tool_calls=4), call_observation={"call_id": "call", "input_tokens": 0, "output_tokens": 0})]
        foreign = vector()
        foreign[0]["dimension_id"] = "foreign"
        candidates.append(observation("bad", usage=foreign))
        for field in ("operation_id", "receipt_id"):
            doc = original.to_dict()
            doc[field] = "new_identity"
            candidates.append(ResourceRequest.from_dict(doc))
        doc = original.to_dict()
        doc.update(operation_id="new_op", receipt_id="new_result")
        candidates.append(ResourceRequest.from_dict(doc))
        self.store.reserve_resources(reservation("other"))
        doc["payload"]["reservation_id"] = "reservation_other"
        candidates.append(ResourceRequest.from_dict(doc))
        before = self.snapshot()
        for candidate in candidates:
            with self.subTest(candidate=candidate.to_dict()), self.assertRaises((ResourceConflictError, ResourceValidationError)):
                self.store.observe_resource_usage(candidate)
        self.assertEqual(self.snapshot(), before)
        for quantity in (None, 4):
            self.store.observe_resource_usage(observation("retained" + str(quantity), usage=vector(None, tool_calls=quantity, local_time=0)))
            self.assertEqual(self.usage()[1]["observed_quantity"], "4")
        self.assertEqual(self.usage(kind="local_time")[1]["observed_quantity"], "0")

    def test_detached_rehashed_usage_breaches_and_pointers_are_reconstructed(self):
        """A recomputed outer hash cannot bless altered derived facts, pointers or admission flags."""
        self.store.observe_resource_usage(observation("over", usage=vector(tool_calls=26)))
        snapshot = self.store.inspect_resources(limits=LIMITS)
        self.assertEqual(snapshot.to_dict()["version"], 2)
        self.assertEqual(ResourceSnapshot.from_dict(snapshot.to_dict()), snapshot)
        paths = [("reservation_usage", 0, "latest_observation_operation_id"),
                 ("reservation_usage", 0, "status"), ("breaches", 0, "trigger_operation_id"),
                 ("breaches", 0, "observed"), ("balances", 0, "admission_blocked")]
        for path in paths:
            doc = snapshot.to_dict()
            target = doc
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = False if path[-1] == "admission_blocked" else "altered"
            doc["snapshot_id"] = hashlib.sha256(canonical({k: v for k, v in doc.items() if k != "snapshot_id"}).encode()).hexdigest()
            with self.assertRaises(ResourceValidationError):
                ResourceSnapshot.from_dict(doc)
        for collection, field in (("reservation_usage", "charged_total"), ("balances", "known_spent")):
            doc = snapshot.to_dict()
            doc[collection][0]["dimensions"][0][field] = "000"
            doc["snapshot_id"] = hashlib.sha256(canonical({k: v for k, v in doc.items() if k != "snapshot_id"}).encode()).hexdigest()
            with self.assertRaises(ResourceValidationError):
                ResourceSnapshot.from_dict(doc)

    def test_all_dimensions_settle_and_scientific_closure_is_unchanged(self):
        """Measured model/tool/local totals settle independently without advancing scientific outgoing closure."""
        from tests.snapshot_fixtures import selection, limits
        selected = selection("task")
        before = self.store.capture_snapshot(selected, limits=limits())
        maxima = vector(model_calls=2, model_input_tokens=6, model_output_tokens=10,
                        tool_calls=5, local_time=7, local_compute=8, local_storage=9)
        self.store.reserve_resources(reservation("all", maxima=maxima,
            call_bounds={"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5}))
        actual = vector(model_calls=1, model_input_tokens=3, model_output_tokens=5,
                        tool_calls=4, local_time=6, local_compute=7, local_storage=8)
        self.store.observe_resource_usage(observation("all_complete", "reservation_all", event="authoritative_completion",
            usage=actual, telemetry={"cached_input_tokens": 2, "reasoning_output_tokens": 4},
            call_observation={"call_id": "exact_call", "input_tokens": 3, "output_tokens": 5}))
        self.assertEqual(self.store.capture_snapshot(selected, limits=limits()), before)
        self.store.reconcile_resource_usage(reconciliation("all_settled", "reservation_all", observation_operation_id="op_all_complete"))
        for entry in actual:
            _, usage = self.usage("reservation_all", entry["dimension_id"][4:])
            self.assertEqual(usage["known_spent"], str(entry["quantity"]))
            self.assertEqual(usage["actual_usage"], str(entry["quantity"]))
            self.assertEqual(usage["remaining_reserved"], "0")
        self.assertEqual(self.snapshot()["breaches"], [])
        self.assertEqual(self.store.capture_snapshot(selected, limits=limits()), before)
        self.store.observe_resource_usage(observation("breach", usage=vector(tool_calls=1001)))
        self.assertTrue(self.snapshot()["breaches"])
        self.assertEqual(self.store.capture_snapshot(selected, limits=limits()), before)

    def test_multiple_settled_handoffs_and_closeout_spending_still_protect_minima(self):
        """Settlement cannot reset spent handoff/closeout capacity or borrow another attempt's pool."""
        for identity, account, output in (("first_handoff", "attempt", 11), ("second_handoff", "attempt2", 10)):
            maximum = vector(model_calls=2, model_input_tokens=6, model_output_tokens=output)
            self.store.reserve_resources(reservation(identity, account=account, purpose="handoff", maxima=maximum,
                call_bounds={"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5}))
            item = observation(identity, "reservation_" + identity, account_id=account,
                               event="authoritative_completion", usage=maximum)
            # Reservation and observation identities are distinct even with the same original work label.
            doc = item.to_dict()
            doc.update(operation_id="observed_" + identity, receipt_id="observed_receipt_" + identity)
            self.store.observe_resource_usage(ResourceRequest.from_dict(doc))
            self.store.reconcile_resource_usage(reconciliation("settled_" + identity, "reservation_" + identity,
                account_id=account, observation_operation_id="observed_" + identity))
        for purpose in ("ordinary", "verification"):
            with self.assertRaisesRegex(ResourceCapacityError, "handoff"):
                self.store.reserve_resources(reservation("blocked_" + purpose, purpose=purpose))
        self.store.reserve_resources(reservation("other_attempt", account="attempt2"))
        parent = self.balance("task", "handoff", "model_output_tokens")[1]
        self.assertEqual((parent["delegated_to_children"], parent["known_spent"], parent["subtree_reserved"]), ("40", "21", "0"))
        self.store.reserve_resources(reservation("close", account="run", purpose="closeout", maxima=vector(local_storage=10)))
        self.store.observe_resource_usage(observation("close_complete", "reservation_close", account_id="run",
            event="authoritative_completion", usage=vector(local_storage=10)))
        self.store.reconcile_resource_usage(reconciliation("close_settled", "reservation_close", account_id="run",
            observation_operation_id="op_close_complete"))
        with self.assertRaisesRegex(ResourceCapacityError, "closeout"):
            self.store.reserve_resources(reservation("blocked_close", account="attempt2"))
        self.assertEqual(self.snapshot()["breaches"], [])

    def test_observation_evidence_matrix_and_complete_new_wire_bounds(self):
        """Every source/event pair, nested duplicate and finite new request boundary has a strict meaning."""
        events = ("partial_usage", "authoritative_completion", *UNCERTAINTY_EVENTS, "worker_narrative")
        for event in events:
            for source in ("controller_receipt", "controller_status", "worker_narrative"):
                doc = observation(event, event=event).to_dict()
                evidence = doc["payload"]["evidence"]
                evidence["source_kind"] = source
                evidence["source_receipt_id"] = "external" if source == "controller_receipt" else None
                allowed = (source == "controller_receipt" and event in events[:2]
                           or source == "controller_status" and event in UNCERTAINTY_EVENTS
                           or source == "worker_narrative" and event == "worker_narrative")
                if allowed:
                    ResourceRequest.from_dict(doc)
                else:
                    with self.assertRaises(ResourceValidationError):
                        ResourceRequest.from_dict(doc)
        for item in (observation(), reconciliation()):
            original = item.to_dict()
            doc = copy.deepcopy(original)
            doc["provenance"]["details"] = {"padding": ""}
            size = len(dumps_request(ResourceRequest.from_dict(doc)))
            doc["provenance"]["details"]["padding"] = "x" * (65536 - size)
            self.assertEqual(len(dumps_request(ResourceRequest.from_dict(doc))), 65536)
            doc["provenance"]["details"]["padding"] += "x"
            with self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
            nested = 0
            for _ in range(14):
                nested = {"nested": nested}
            doc = copy.deepcopy(original)
            doc["provenance"]["details"] = nested
            ResourceRequest.from_dict(doc)
            doc["provenance"]["details"] = {"extra": nested}
            with self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
        item = observation(call_observation={"call_id": "call", "input_tokens": 0, "output_tokens": 0})
        for field in ('"source_id":"synthetic_source"', '"cached_input_tokens":null',
                      '"call_id":"call"', '"quantity":0'):
            with self.assertRaises(ResourceValidationError):
                loads_request(dumps_request(item).replace(field, field + "," + field, 1))
        for event in (*UNCERTAINTY_EVENTS, "worker_narrative"):
            for updates in ({"usage": vector()},
                            {"telemetry": {"cached_input_tokens": 0, "reasoning_output_tokens": None}},
                            {"call_observation": {"call_id": "call", "input_tokens": 0, "output_tokens": 0}}):
                with self.assertRaises(ResourceValidationError):
                    observation(event, event=event, **updates)
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion"))
        for updates in ({"owner_id": "other"}, {"account_id": "attempt2"}, {"reservation_id": "missing"}):
            with self.assertRaises(ResourceConflictError):
                self.store.reconcile_resource_usage(reconciliation(**updates))
        for mode in ("refund", "amend", True):
            with self.assertRaises(ResourceValidationError):
                reconciliation(mode=mode)

    def test_expanded_inspection_bytes_and_balance_formula(self):
        """Expanded usage/breach projections count toward final byte limits and explain exact signed availability."""
        self.store.observe_resource_usage(observation("over", usage=vector(tool_calls=1001)))
        self.store.reconcile_resource_usage(reconciliation(mode="conservative", observation_operation_id="op_over"))
        doc = self.snapshot()
        size = len(canonical(doc))
        self.assertEqual(self.store.inspect_resources(limits=ResourceInspectionLimits(1000, 10000, size)).to_dict(), doc)
        with self.assertRaisesRegex(ResourceInspectionLimitError, "complete inspection"):
            self.store.inspect_resources(limits=ResourceInspectionLimits(1000, 10000, size - 1))
        for balance in doc["balances"]:
            for dimension in balance["dimensions"]:
                expected = int(dimension["ceiling"]) - sum(int(dimension[key]) for key in (
                    "delegated_to_children", "child_overrun", "direct_known_spent", "direct_conservative_excess", "direct_reserved"))
                self.assertEqual(dimension["available_for_local_use"], str(expected))
