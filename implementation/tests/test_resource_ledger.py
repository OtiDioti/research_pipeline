"""Real schema3 hierarchical/protected capacity, identity and detached inspection tests."""

import copy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.backup import create_backup, restore_backup
from research_pipeline.resources import (
    MAX_QUANTITY, ResourceRequest, ResourceCapacityError, ResourceConflictError,
    ResourceValidationError, ResourceInspectionLimits, ResourceInspectionLimitError,
    ResourceSnapshot, ResourceReceipt, canonical,
)
from research_pipeline.store import RecordStore, StoreClosedError
from tests.resource_fixtures import (
    LIMITS, allocation, changed, policy, pools, populate, reservation,
    root_request, scope, vector,
)
from tests.test_store import record, request


class ResourceLedgerTests(unittest.TestCase):
    """Verify observable accounting on complete real project/run/task/attempt fixtures."""

    def setUp(self):
        """Create an isolated schema3 store and independently funded attempts."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        self.declarations, self.receipts = populate(self.store, attempts=2)

    def snapshot(self):
        """Capture all rows and balances using the bounded public inspection API."""
        return self.store.inspect_resources(limits=LIMITS)

    def balance(self, snapshot, account, purpose, kind="tool_calls"):
        """Select a dimensioned observed balance without depending on internal state."""
        row = next(r for r in snapshot.to_dict()["balances"] if r["account_id"] == account and r["purpose"] == purpose)
        return next(d for d in row["dimensions"] if d["dimension_id"] == "dim_" + kind)

    def test_no_double_charge_independent_handoffs_and_successor_capacity(self):
        """Two attempts consume distinct task handoff budgets while ancestors charge only delegations."""
        before = self.snapshot()
        self.assertEqual(self.balance(before, "project", "total")["available_for_local_use"], "810")
        self.assertEqual(self.balance(before, "task", "handoff")["available_for_local_use"], "0")
        self.assertEqual(self.balance(before, "run", "handoff")["delegated_to_children"], "40")
        req = reservation("first_handoff", purpose="handoff", maxima=vector(model_calls=1, model_input_tokens=1, model_output_tokens=2),
                          call_bounds={"max_input_tokens_per_call": 1, "max_output_tokens_per_call": 2})
        receipt = self.store.reserve_resources(req)
        self.assertEqual(self.store.reserve_resources(req), receipt)
        after = self.snapshot()
        for account, purpose in (("project", "total"), ("run", "handoff"), ("task", "handoff")):
            for key in ("ceiling", "delegated_to_children", "direct_reserved", "available_for_local_use"):
                self.assertEqual(self.balance(before, account, purpose, "model_output_tokens")[key],
                                 self.balance(after, account, purpose, "model_output_tokens")[key])
        self.assertEqual(self.balance(after, "project", "total", "model_output_tokens")["subtree_reserved"], "2")
        self.assertEqual(self.balance(after, "attempt2", "handoff", "model_output_tokens")["available_for_local_use"], "20")
        with self.assertRaises(ResourceCapacityError):
            self.store.allocate_resources(allocation("attempt", "successor", "task"))
        self.assertEqual(self.snapshot(), after)

    def test_retry_conflicts_all_variants_and_reused_entity_receipt_ids(self):
        """Retries preserve original outcomes; changed declarations and aliases cannot mint receipts."""
        work = reservation()
        work_receipt = self.store.reserve_resources(work)
        before = self.snapshot()
        for item, receipt in zip([*self.declarations, work], [*self.receipts, work_receipt]):
            kind = item.to_dict()["kind"]
            method = {"create_account": self.store.create_resource_account, "allocate": self.store.allocate_resources,
                      "reserve": self.store.reserve_resources}[kind]
            self.assertEqual(method(item), receipt)
            self.assertEqual(ResourceReceipt.from_dict(receipt.to_dict()), receipt)
            with self.assertRaises(ResourceConflictError):
                method(changed(item, owner_id="other"))
            alias = item.to_dict()
            alias["operation_id"] += "_alias"
            with self.assertRaises(ResourceConflictError):
                method(ResourceRequest.from_dict(alias))
            alias["receipt_id"] += "_alias"
            with self.assertRaises(ResourceConflictError):
                method(ResourceRequest.from_dict(alias))
        run = self.declarations[1]
        for key, new in (("max_input_tokens_per_call", 2), ("max_output_tokens_per_call", 4)):
            doc = run.to_dict()
            doc["payload"]["run_policy"]["handoff_call_bounds"][key] = new
            with self.assertRaises(ResourceConflictError):
                self.store.allocate_resources(ResourceRequest.from_dict(doc))
        self.assertEqual(self.snapshot(), before)

    def test_invalid_policies_reject_without_effects(self):
        """Malformed bounds and independent one-unit provisioning shortfalls leave no operation."""
        original = policy()
        variants = []
        for i, o in ((5, 10), (6, 9)):
            variants.append(policy(handoff_minimum=vector(model_calls=2, model_input_tokens=i, model_output_tokens=o, local_time=1, local_storage=1)))
        variants += [policy(context_capacity_tokens=7), policy(per_call_output_tokens=4),
                     policy(handoff_call_bounds=None), policy(handoff_call_bounds={}),
                     policy(handoff_minimum=vector(model_calls=2, model_input_tokens=6, model_output_tokens=10, local_time=0, local_storage=1)),
                     policy(closeout_minimum=vector(local_time=1, local_storage=0)),
                     policy(verification_minimum=vector())]
        for key in ("max_input_tokens_per_call", "max_output_tokens_per_call"):
            for value in (True, -1, MAX_QUANTITY + 1, "5"):
                candidate = copy.deepcopy(original)
                candidate["handoff_call_bounds"][key] = value
                variants.append(candidate)
        for index, run_policy in enumerate(variants):
            before = self.snapshot()
            with self.subTest(index=index), self.assertRaises(ResourceValidationError):
                self.store.allocate_resources(allocation("run", "bad" + str(index), "project", run_policy=run_policy))
            self.assertEqual(self.snapshot(), before)
        for purpose in ("handoff", "closeout", "verification"):
            limits = pools(closeout=10)
            limits[purpose] = vector()
            before = self.snapshot()
            with self.assertRaises(ResourceCapacityError):
                self.store.allocate_resources(allocation("run", "unfunded", "project", purpose_limits=limits))
            self.assertEqual(self.snapshot(), before)

    def test_protected_free_minimum_after_handoff_and_closeout(self):
        """Ordinary/verification admission checks free handoff and run persistence capacity separately."""
        first = reservation("handoff", purpose="handoff", maxima=vector(model_calls=2, model_input_tokens=6, model_output_tokens=11),
                            call_bounds={"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5})
        self.store.reserve_resources(first)
        for purpose in ("ordinary", "verification"):
            with self.assertRaisesRegex(ResourceCapacityError, "handoff"):
                self.store.reserve_resources(reservation("blocked_" + purpose, purpose=purpose))
        self.store.reserve_resources(reservation("other_attempt", account="attempt2"))
        self.store.reserve_resources(reservation("close", account="run", purpose="closeout", maxima=vector(local_storage=10)))
        with self.assertRaisesRegex(ResourceCapacityError, "closeout"):
            self.store.reserve_resources(reservation("blocked_close", account="attempt2"))

    def test_actual_reservation_bounds_are_mandatory_independent_and_exact(self):
        """Provisioning envelopes never fill absent reservation bounds or impose extra ceilings."""
        before = self.snapshot()
        variants = [(vector(model_calls=1, model_input_tokens=3, model_output_tokens=5), None),
                    (vector(tool_calls=1), {"max_input_tokens_per_call": 0, "max_output_tokens_per_call": 1}),
                    (vector(model_input_tokens=1), None), (vector(model_output_tokens=1), None), (vector(), None)]
        for maxima, bounds in variants:
            with self.assertRaises(ResourceValidationError):
                self.store.reserve_resources(reservation("bad", maxima=maxima, call_bounds=bounds))
            self.assertEqual(self.snapshot(), before)
        # Input bound exceeds the provisioning input bound, yet its own envelope
        # fits C/P and cumulative capacity. This is deliberately admissible.
        valid = reservation("different", purpose="handoff", maxima=vector(model_calls=1, model_input_tokens=6, model_output_tokens=2),
                            call_bounds={"max_input_tokens_per_call": 6, "max_output_tokens_per_call": 2})
        receipt = self.store.reserve_resources(valid)
        self.assertEqual(self.store.get_resource_operation(valid.operation_id), receipt)

    def test_invalid_hierarchy_owner_dimensions_purposes_and_overhead(self):
        """Cross-owner, reparenting, incomplete units and unsupported purpose paths fail atomically."""
        candidates = [allocation("attempt", "new", "run"), allocation("run", "new", "attempt"),
                      allocation("attempt", "new", "task", owner_id="other"),
                      allocation("attempt", "new", "missing"),
                      allocation("attempt", "new", "task", purpose_limits=pools(closeout=1)),
                      allocation("attempt", "new", "task", purpose_limits=pools(handoff=0))]
        for item in candidates:
            before = self.snapshot()
            with self.assertRaises((ResourceValidationError, ResourceCapacityError)):
                self.store.allocate_resources(item)
            self.assertEqual(self.snapshot(), before)
        for account, purpose in (("project", "ordinary"), ("run", "ordinary"), ("task", "handoff"),
                                 ("attempt", "closeout"), ("run", "handoff")):
            with self.assertRaises(ResourceValidationError):
                self.store.reserve_resources(reservation("invalid_purpose", account=account, purpose=purpose))
        for payload in ({"owner_id": "other"}, {"maxima": vector(30)}, {"maxima": vector(0)[:-1]}):
            with self.assertRaises((ResourceValidationError, ResourceCapacityError)):
                self.store.reserve_resources(reservation("invalid", **payload))
        with self.assertRaises(ResourceValidationError):
            allocation("attempt", "new", "task", run_policy=policy())

    def test_scope_identity_exact_references_and_declared_reference_roles(self):
        """Stable scopes ignore revisions; exact references retain order and must resolve matching kinds."""
        self.store.submit(request("project_revision", [record("project", 2, "project")], {"project": 1}))
        root = root_request(scope=scope("project", revision=2)).to_dict()
        root["operation_id"], root["receipt_id"], root["payload"]["account_id"] = "other_root", "other_receipt", "other_account"
        with self.assertRaises(ResourceConflictError):
            self.store.create_resource_account(ResourceRequest.from_dict(root))
        for identity, revision, kind in (("absent", 1, "project"), ("project", 3, "project"), ("task", 1, "project")):
            doc = copy.deepcopy(root)
            doc["payload"]["scope"]["reference"].update(record_id=identity, revision=revision, target_kind=kind)
            with self.assertRaises(ResourceValidationError):
                self.store.create_resource_account(ResourceRequest.from_dict(doc))
        doc = reservation("referenced").to_dict()
        ref = {"record_id": "project", "revision": 1, "relationship": "resource_policy", "target_kind": "project"}
        doc["policy_references"] = [ref, ref]
        self.store.reserve_resources(ResourceRequest.from_dict(doc))
        doc["policy_references"][0] = {**ref, "relationship": "resource_evidence"}
        with self.assertRaises(ResourceValidationError):
            ResourceRequest.from_dict(doc)
        self.snapshot()

    def test_detached_unknown_balances_limits_and_exact_restore(self):
        """Observations are immutable, complete, bounded and preserve policy/liability after restore."""
        before = self.snapshot()
        work = reservation()
        receipt = self.store.reserve_resources(work)
        after = self.snapshot()
        self.assertNotEqual(before.snapshot_id, after.snapshot_id)
        self.assertEqual(ResourceSnapshot.from_dict(after.to_dict()), after)
        data = after.to_dict()
        data["accounts"][0]["owner_id"] = "forged"
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(self.balance(before, "attempt", "ordinary")["actual_usage"], "0")
        self.assertIsNone(self.balance(after, "attempt", "ordinary")["actual_usage"])
        self.assertEqual(self.balance(after, "attempt", "ordinary")["known_spent"], "0")
        for limits in (ResourceInspectionLimits(1, 100, 10000000), ResourceInspectionLimits(100, 1, 10000000),
                       ResourceInspectionLimits(100, 100, 1)):
            with self.assertRaises(ResourceInspectionLimitError):
                self.store.inspect_resources(limits=limits)
        backup = self.parent / "backup"
        create_backup(self.store, backup)
        with restore_backup(backup, self.parent / "restored") as restored:
            self.assertEqual(restored.inspect_resources(limits=LIMITS), after)
            self.assertEqual(restored.get_resource_operation(work.operation_id), receipt)
            self.assertEqual((self.parent / "restored/metadata.sqlite3").read_bytes(), (backup / "snapshot.sqlite3").read_bytes())
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.inspect_resources(limits=LIMITS), after)
            self.assertEqual(reopened.reserve_resources(work), receipt)
        for method in (lambda: self.store.create_resource_account(root_request()), lambda: self.store.allocate_resources(self.declarations[1]),
                       lambda: self.store.reserve_resources(work), lambda: self.store.get_resource_operation("missing"),
                       lambda: self.store.inspect_resources(limits=LIMITS)):
            with self.assertRaises(StoreClosedError):
                method()

    def test_surplus_and_zero_input_provisioning_persist_as_declared(self):
        """Valid surplus and zero-per-call-input policies survive actual run admission unchanged."""
        variants = [policy(handoff_minimum=vector(model_calls=2, model_input_tokens=12, model_output_tokens=14,
                                                local_time=2, local_storage=2)),
                    policy(handoff_call_bounds={"max_input_tokens_per_call": 0, "max_output_tokens_per_call": 5},
                           handoff_minimum=vector(model_calls=2, model_input_tokens=1, model_output_tokens=10,
                                                 local_time=1, local_storage=1))]
        for index, declared in enumerate(variants):
            item = allocation("run", "extra_run" + str(index), "project", run_policy=declared)
            result = self.store.allocate_resources(item)
            normalized = item.to_dict()["payload"]["run_policy"]
            state = self.snapshot().to_dict()
            account = next(a for a in state["accounts"] if a["account_id"] == item.to_dict()["payload"]["account_id"])
            self.assertEqual(account["policy"], normalized)
            self.assertEqual(self.store.allocate_resources(item), result)

    def test_monitored_money_and_branch_delegation_share_root_units(self):
        """Additional scaled currency budgets and a real branch path obey the same capacity rules."""
        root = self.parent / "monetary"
        money = {"dimension_id": "usd", "kind": "monetary", "unit": "currency_quantum", "currency": "USD", "scale": 1000}

        def monetary(item, amount):
            """Extend every complete vector in this declaration with the same explicit money unit."""
            doc = item.to_dict()
            p = doc["payload"]
            vectors = []
            if doc["kind"] == "create_account":
                p["dimensions"].append(money)
                vectors.append(p["ceiling"])
            elif doc["kind"] == "allocate":
                vectors.extend(p["purpose_limits"].values())
                if p["run_policy"] is not None:
                    for purpose in ("verification", "handoff", "closeout"):
                        p["run_policy"][purpose + "_minimum"].append({"dimension_id": "usd", "quantity": 0})
                    p["run_policy"]["monetary_services"] = [{"dimension_id": "usd", "service_id": "declared_service",
                        "mode": "monitored_target", "statement": "No external hard bound is asserted"}]
            else:
                vectors.append(p["maxima"])
            for value in vectors:
                value.append({"dimension_id": "usd", "quantity": amount if value is not p.get("purpose_limits", {}).get("closeout") else 0})
            return ResourceRequest.from_dict(doc)

        with RecordStore.create(root, schema_version=3) as store:
            store.submit(request("scopes", [record("project", kind="project"), record("task", kind="task_specification")]))
            store.create_resource_account(monetary(root_request(), 1000))
            run = monetary(allocation("run", "run", "project"), 100)
            for invalid in ([], [{"dimension_id": "other", "service_id": "service", "mode": "monitored_target", "statement": "Declared"}]):
                doc = run.to_dict()
                doc["payload"]["run_policy"]["monetary_services"] = invalid
                with self.assertRaises(ResourceValidationError):
                    store.allocate_resources(ResourceRequest.from_dict(doc))
            doc = run.to_dict()
            doc["payload"]["run_policy"]["monetary_services"][0]["mode"] = "hard_limit"
            with self.assertRaises(ResourceValidationError):
                ResourceRequest.from_dict(doc)
            store.allocate_resources(run)
            for item in (allocation("branch", "branch", "run"), allocation("task", "task", "branch"), allocation("attempt", "attempt", "task")):
                store.allocate_resources(monetary(item, 100))
            work = monetary(reservation(), 100)
            receipt = store.reserve_resources(work)
            self.assertEqual(store.reserve_resources(work), receipt)
            with self.assertRaises(ResourceCapacityError):
                store.reserve_resources(monetary(reservation("extra_money"), 1))
            with self.assertRaises(ResourceValidationError):
                store.reserve_resources(reservation("missing_currency"))
            observed = store.inspect_resources(limits=LIMITS).to_dict()
            ordinary = next(b for b in observed["balances"] if b["account_id"] == "attempt" and b["purpose"] == "ordinary")
            self.assertEqual(next(d for d in ordinary["dimensions"] if d["dimension_id"] == "usd")["available_for_local_use"], "0")

    def test_aggregate_overflow_rejects_and_exact_integer_capacity_is_admissible(self):
        """Valid maximum operands retain exact products, while overflowing allocation expressions fail."""
        root = self.parent / "integer-boundary"
        with RecordStore.create(root, schema_version=3) as store:
            store.submit(request("scopes", [record("project", kind="project")]))
            store.create_resource_account(root_request(ceiling=vector(MAX_QUANTITY)))
            before = store.inspect_resources(limits=LIMITS)
            overflowing = pools(closeout=10)
            overflowing["ordinary"] = vector(MAX_QUANTITY)
            with self.assertRaises(ResourceValidationError):
                store.allocate_resources(allocation("run", "overflow", "project", purpose_limits=overflowing))
            for i, o in ((2**62, 1), (1, 2**62)):
                declared = policy(context_capacity_tokens=MAX_QUANTITY, per_call_output_tokens=MAX_QUANTITY,
                    handoff_call_bounds={"max_input_tokens_per_call": i, "max_output_tokens_per_call": o},
                    handoff_minimum=vector(model_calls=2, model_input_tokens=MAX_QUANTITY,
                                          model_output_tokens=MAX_QUANTITY, local_time=1, local_storage=1))
                with self.assertRaises(ResourceValidationError):
                    store.allocate_resources(allocation("run", "overflow", "project", run_policy=declared))
                self.assertEqual(store.inspect_resources(limits=LIMITS), before)
            minimum = vector(model_calls=MAX_QUANTITY, model_input_tokens=MAX_QUANTITY,
                             model_output_tokens=MAX_QUANTITY, local_time=1, local_storage=1)
            declared = policy(context_capacity_tokens=2, per_call_output_tokens=1,
                handoff_call_bounds={"max_input_tokens_per_call": 1, "max_output_tokens_per_call": 1}, handoff_minimum=minimum)
            limits = {"ordinary": vector(), "verification": vector(tool_calls=1), "handoff": minimum,
                      "closeout": vector(local_time=1, local_storage=1)}
            item = allocation("run", "boundary", "project", run_policy=declared, purpose_limits=limits)
            result = store.allocate_resources(item)
            self.assertEqual(store.allocate_resources(item), result)
            snapshot = store.inspect_resources(limits=LIMITS)
            self.assertEqual(self.balance(snapshot, "project", "total", "model_calls")["available_for_local_use"], "0")

    def test_rehashed_detached_snapshot_rejects_noncanonical_and_incoherent_data(self):
        """A caller cannot legitimize unknown fields, coerced numbers or altered balances by rehashing."""
        original = self.snapshot().to_dict()
        variants = []
        doc = copy.deepcopy(original)
        doc["schema_identity"]["version"] = 3.0
        variants.append(doc)
        doc = copy.deepcopy(original)
        doc["balances"][0]["dimensions"][0]["known_spent"] = "1"
        variants.append(doc)
        doc = copy.deepcopy(original)
        doc["accounts"][0]["unknown"] = None
        variants.append(doc)
        doc = copy.deepcopy(original)
        doc["operations"][0]["receipt"]["sequence"] = True
        variants.append(doc)
        for doc in variants:
            body = {key: value for key, value in doc.items() if key != "snapshot_id"}
            doc["snapshot_id"] = hashlib.sha256(canonical(body).encode("ascii")).hexdigest()
            with self.assertRaises(ResourceValidationError):
                ResourceSnapshot.from_dict(doc)

    def test_malformed_handoff_bounds_cannot_bypass_admission_through_frozen_objects(self):
        """Every malformed bounds wire form fails before effects even on forged frozen requests."""
        valid = allocation("run", "malformed", "project").to_dict()
        documents = []
        doc = copy.deepcopy(valid)
        del doc["payload"]["run_policy"]["handoff_call_bounds"]
        documents.append(canonical(doc))
        bounds_cases = [None, [], "bounds", {}, {"max_input_tokens_per_call": 3},
                        {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5, "unknown": 1}]
        for key, values in (("max_input_tokens_per_call", (True, False, -1, MAX_QUANTITY + 1, "3", 3.0)),
                            ("max_output_tokens_per_call", (True, False, -1, 0, MAX_QUANTITY + 1, "5", 5.0))):
            for value in values:
                bound = {"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5}
                bound[key] = value
                bounds_cases.append(bound)
        for bound in bounds_cases:
            doc = copy.deepcopy(valid)
            doc["payload"]["run_policy"]["handoff_call_bounds"] = bound
            documents.append(canonical(doc))
        for key, value in (("max_input_tokens_per_call", 3), ("max_output_tokens_per_call", 5)):
            field = '"' + key + '":' + str(value)
            documents.append(canonical(valid).replace(field, field + ',' + field))
        before = self.snapshot()
        metadata = (self.root / "metadata.sqlite3").read_bytes()
        for index, text in enumerate(documents):
            forged = object.__new__(ResourceRequest)
            object.__setattr__(forged, "_json", text)
            with self.subTest(index=index), self.assertRaises(ResourceValidationError):
                self.store.allocate_resources(forged)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual((self.root / "metadata.sqlite3").read_bytes(), metadata)
