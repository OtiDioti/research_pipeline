"""Real observation/settlement interruption and synchronized serial transaction outcomes."""

import json
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline import resource_ledger
from research_pipeline.resources import ResourceRequest, canonical
from research_pipeline.store import RecordStore, StoreClosedError, StoreDatabaseError
from tests.resource_fixtures import LIMITS, observation, populate, reconciliation, reservation, vector
from tests.test_vault import child_environment


def apply_usage(store, item):
    """Invoke the public method for a saved operation without regenerating any identity."""
    return {"observe": store.observe_resource_usage, "reconcile": store.reconcile_resource_usage,
            "reserve": store.reserve_resources}[item.to_dict()["kind"]](item)


class UsageRecoveryTests(unittest.TestCase):
    """Use actual SQLite writes, authorizers, process exits and bounded synchronization without sleeps."""

    def setUp(self):
        """Keep each fault/race in an independent disposable runtime."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)

    def case(self, name, kind):
        """Create a fully reserved attempt and return one pending mutation ready for fault injection."""
        root = self.parent / name
        with RecordStore.create(root, schema_version=3) as store:
            populate(store)
            store.reserve_resources(reservation(maxima=vector(tool_calls=25)))
            if kind == "reconcile":
                store.observe_resource_usage(observation("complete", event="authoritative_completion", usage=vector(tool_calls=6)))
        item = observation(usage=vector(None, tool_calls=4)) if kind == "observe" else reconciliation()
        doc = item.to_dict()
        doc["evidence_references"] = [{"record_id": "project", "revision": 1,
            "relationship": "resource_evidence", "target_kind": "project"}]
        return root, ResourceRequest.from_dict(doc)

    def test_faults_and_real_commit_rollback_denials(self):
        """Both mutation kinds preserve original IDs across rollback, lost COMMIT acknowledgment and denial."""
        for kind in ("observe", "reconcile"):
            for point in ("before_writes", "after_writes", "after_commit", "deny_commit", "deny_rollback"):
                with self.subTest(kind=kind, point=point):
                    root, item = self.case(kind + point, kind)
                    with RecordStore.open(root) as store:
                        before = store.inspect_resources(limits=LIMITS)

                        def authorizer(action, first, second, database, source):
                            """Deny actual SQLite transaction completion for the selected boundary."""
                            denied = (point == "deny_commit" and first == "COMMIT"
                                      or point == "deny_rollback" and first == "ROLLBACK")
                            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and denied else sqlite3.SQLITE_OK

                        def fail(boundary):
                            """Interrupt real writes or the acknowledgment after successful COMMIT."""
                            if boundary == point or point == "deny_rollback" and boundary == "after_writes":
                                raise KeyboardInterrupt(point)

                        store._connection.set_authorizer(authorizer)
                        expected = StoreDatabaseError if point == "deny_commit" else KeyboardInterrupt
                        with patch.object(resource_ledger, "_fault", side_effect=fail), self.assertRaises(expected):
                            apply_usage(store, item)
                        if point == "deny_rollback":
                            with self.assertRaises(StoreClosedError):
                                store.get_resource_operation(item.operation_id)
                        else:
                            store._connection.set_authorizer(None)
                    with RecordStore.open(root) as store:
                        receipt = store.get_resource_operation(item.operation_id)
                        self.assertEqual(receipt is not None, point == "after_commit")
                        if receipt is None:
                            self.assertEqual(store.inspect_resources(limits=LIMITS), before)
                            receipt = apply_usage(store, item)
                        self.assertEqual(apply_usage(store, item), receipt)
                        self.assertEqual(receipt.to_dict()["request_fingerprint"], item.fingerprint)

    def test_checked_close_acknowledgment_loss(self):
        """A real checked close failure leaves both original observation and settlement receipts durable."""
        class CheckedClose:
            """Delegate real SQLite work and lose only the acknowledgment after actual close."""

            def __init__(self, connection):
                """Retain the real committed SQLite connection."""
                self.connection = connection

            def close(self):
                """Close first, then inject the checked-close acknowledgment failure."""
                self.connection.close()
                raise OSError("close acknowledgment lost")

        for kind in ("observe", "reconcile"):
            root, item = self.case(kind, kind)
            store = RecordStore.open(root)
            receipt = apply_usage(store, item)
            store._connection = CheckedClose(store._connection)
            with self.assertRaises(OSError):
                store.close()
            store._connection = None
            with RecordStore.open(root) as reopened:
                self.assertEqual(reopened.get_resource_operation(item.operation_id), receipt)
                self.assertEqual(apply_usage(reopened, item), receipt)

    def test_abrupt_exit_and_genuinely_spilled_hot_journals(self):
        """Each kind survives abrupt boundaries; spilled uncommitted pages recover before live replay."""
        program = '''
import os, sys
from research_pipeline import resource_ledger
from research_pipeline.resources import loads_request
from research_pipeline.store import RecordStore
from tests.test_resource_usage_recovery import apply_usage
store = RecordStore.open(sys.argv[1])
item = loads_request(sys.argv[2])
def crash(point):
    """Exit after the chosen actual boundary, without exception cleanup."""
    if point == sys.argv[3]:
        os._exit(74)
resource_ledger._fault = crash
if sys.argv[4] == "spill":
    store._connection.execute("PRAGMA cache_size=1")
    store._connection.execute("PRAGMA cache_spill=ON")
apply_usage(store, item)
'''
        for kind in ("observe", "reconcile"):
            for point in ("before_writes", "after_writes", "after_commit", "spill"):
                root, item = self.case(kind + point, kind)
                if point == "spill":
                    doc = item.to_dict()
                    doc["provenance"]["details"] = {"large": "x" * 50000}
                    item = ResourceRequest.from_dict(doc)
                with RecordStore.open(root) as store:
                    before = store.inspect_resources(limits=LIMITS)
                original_bytes = (root / "metadata.sqlite3").read_bytes()
                result = subprocess.run([sys.executable, "-B", "-c", program, str(root), canonical(item.to_dict()),
                                         "after_writes" if point == "spill" else point, point],
                                        env=child_environment(), capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 74, result.stderr)
                if point == "spill":
                    journal = root / "metadata.sqlite3-journal"
                    self.assertTrue(journal.exists())
                    self.assertNotEqual(journal.read_bytes()[:8], b"\0" * 8)
                    self.assertNotEqual((root / "metadata.sqlite3").read_bytes(), original_bytes)
                    validator = resource_ledger.validate_ledger

                    def check_recovery(connection):
                        """Require restored original bytes before application-level live validation begins."""
                        self.assertEqual((root / "metadata.sqlite3").read_bytes(), original_bytes)
                        self.assertFalse(journal.exists())
                        return validator(connection)

                    with patch.object(resource_ledger, "validate_ledger", side_effect=check_recovery):
                        with RecordStore.open(root):
                            pass
                with RecordStore.open(root) as store:
                    receipt = store.get_resource_operation(item.operation_id)
                    self.assertEqual(receipt is not None, point == "after_commit")
                    if receipt is None:
                        self.assertEqual(store.inspect_resources(limits=LIMITS), before)
                        receipt = apply_usage(store, item)
                    self.assertEqual(apply_usage(store, item), receipt)
                self.assertFalse((root / "metadata.sqlite3-journal").exists())

    def test_consistent_inspection_during_observation_and_settlement_writes(self):
        """One read snapshot sees the old complete state while another connection has actual pending writes."""
        for kind in ("observe", "reconcile"):
            root, item = self.case(kind, kind)
            with RecordStore.open(root) as store:
                before = store.inspect_resources(limits=LIMITS)
                read, written = threading.Event(), threading.Event()
                failures = []

                def seam(point):
                    """Synchronize inspection's established snapshot with the uncommitted mutation."""
                    if point == "inspection_after_counts":
                        read.set()
                        if not written.wait(10):
                            raise AssertionError("writer never reached writes")
                    elif point == "after_writes":
                        written.set()

                def writer():
                    """Use a separate connection on its owning thread and report all failures."""
                    try:
                        with RecordStore.open(root) as handle:
                            if not read.wait(10):
                                raise AssertionError("reader never established snapshot")
                            apply_usage(handle, item)
                    except BaseException as error:
                        failures.append(error)
                        written.set()

                with patch.object(resource_ledger, "_fault", side_effect=seam):
                    thread = threading.Thread(target=writer)
                    thread.start()
                    try:
                        observed = store.inspect_resources(limits=LIMITS)
                    finally:
                        thread.join(15)
                self.assertFalse(thread.is_alive())
                self.assertFalse(failures, failures)
                self.assertEqual(observed, before)
                self.assertNotEqual(store.inspect_resources(limits=LIMITS), before)

    def race(self, root, first_request, second_request):
        """Serialize contending independent processes with pipe acknowledgments at actual writes/BEGIN."""
        program = '''
import json, sys
from research_pipeline import resource_ledger
from research_pipeline.resources import loads_request, ResourceCapacityError, ResourceConflictError
from research_pipeline.store import RecordStore
from tests.test_resource_usage_recovery import apply_usage
store = RecordStore.open(sys.argv[1])
item = loads_request(sys.argv[2])
def seam(point):
    """Hold the first real writer until the parent observes the contender's BEGIN."""
    if point == "after_writes" and sys.argv[3] == "first":
        print("written", flush=True)
        assert sys.stdin.readline().strip() == "release"
def trace(sql):
    """Acknowledge the second writer entering SQLite's actual BEGIN IMMEDIATE."""
    if sql == "BEGIN IMMEDIATE" and sys.argv[3] == "second":
        print("begin", flush=True)
resource_ledger._fault = seam
store._connection.set_trace_callback(trace)
print("ready", flush=True)
assert sys.stdin.readline().strip() == "go"
try:
    print(json.dumps(apply_usage(store, item).to_dict(), sort_keys=True), flush=True)
except (ResourceCapacityError, ResourceConflictError) as error:
    print(type(error).__name__, flush=True)
finally:
    store.close()
'''
        def ack(child):
            """Read a bounded synchronization acknowledgment rather than depend on scheduling sleeps."""
            if not select.select([child.stdout], [], [], 15)[0]:
                raise AssertionError("child acknowledgment timed out")
            return child.stdout.readline().strip()

        children = []
        try:
            for name, item in (("first", first_request), ("second", second_request)):
                children.append(subprocess.Popen([sys.executable, "-B", "-c", program, str(root), canonical(item.to_dict()), name],
                    env=child_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            first, second = children
            self.assertEqual(ack(first), "ready")
            self.assertEqual(ack(second), "ready")
            first.stdin.write("go\n")
            first.stdin.flush()
            self.assertEqual(ack(first), "written")
            second.stdin.write("go\n")
            second.stdin.flush()
            self.assertEqual(ack(second), "begin")
            first.stdin.write("release\n")
            first.stdin.flush()
            out1, error1 = first.communicate(timeout=15)
            out2, error2 = second.communicate(timeout=15)
            self.assertEqual(first.returncode, 0, error1)
            self.assertEqual(second.returncode, 0, error2)
            return json.loads(out1), out2.strip()
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)

    def test_duplicate_conflicting_receipts_and_settlement_predecessor_races(self):
        """Exact concurrent retries return one receipt; external receipt aliases and stale settlements conflict."""
        for mode in ("duplicate", "source_alias", "operation_conflict", "settlement_duplicate", "settlement_predecessor"):
            kind = "reconcile" if mode.startswith("settlement") else "observe"
            root, first = self.case(mode, kind)
            doc = first.to_dict()
            if mode in ("source_alias", "settlement_predecessor"):
                doc.update(operation_id="competing", receipt_id="competing_receipt")
            elif mode == "operation_conflict":
                doc["payload"]["evidence"]["statement"] = "Changed evidence"
            second = ResourceRequest.from_dict(doc)
            receipt, output = self.race(root, first, second)
            if mode.endswith("duplicate"):
                self.assertEqual(json.loads(output), receipt)
            else:
                self.assertEqual(output, "ResourceConflictError")
            with RecordStore.open(root) as store:
                self.assertEqual(store.get_resource_operation(first.operation_id).to_dict(), receipt)
                store.inspect_resources(limits=LIMITS)

    def test_settlement_vs_competing_reservation_admission(self):
        """A waiting replacement observes committed settlement and consumes only independently freed capacity."""
        root, settlement = self.case("settlement_race", "reconcile")
        replacement = reservation("replacement", maxima=vector(tool_calls=19))
        settled, output = self.race(root, settlement, replacement)
        admitted = json.loads(output)
        self.assertLess(settled["sequence"], admitted["sequence"])
        with RecordStore.open(root) as store:
            data = store.inspect_resources(limits=LIMITS).to_dict()
            row = next(b for b in data["balances"] if b["account_id"] == "attempt" and b["purpose"] == "ordinary")
            tool = next(d for d in row["dimensions"] if d["dimension_id"] == "dim_tool_calls")
            self.assertEqual((tool["known_spent"], tool["direct_reserved"], tool["available_for_local_use"]), ("6", "19", "0"))
