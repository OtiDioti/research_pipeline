"""Real transaction contention, original-ID recovery, process loss and hot journals."""

import json
import select
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline import resource_ledger
from research_pipeline.resources import ResourceCapacityError, ResourceRequest, canonical
from research_pipeline.store import RecordStore, StoreClosedError, StoreDatabaseError
from tests.resource_fixtures import LIMITS, populate, reservation, vector
from tests.test_vault import child_environment


class ResourceRecoveryTests(unittest.TestCase):
    """Use real SQLite synchronization and explicit process acknowledgments, never sleeps."""

    def setUp(self):
        """Create a fully funded attempt in an isolated schema3 runtime."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_independent_handles_contend_for_final_capacity(self):
        """A second BEGIN waits for actual first writes; only one full-capacity reservation commits."""
        first_written, second_begin, release = threading.Event(), threading.Event(), threading.Event()
        results, failures = [], []

        def seam(point):
            """Hold only the first writer after its real metadata writes."""
            if point == "after_writes" and threading.current_thread().name == "resource-first":
                first_written.set()
                if not release.wait(10):
                    raise AssertionError("first writer release was not acknowledged")

        def worker(identity):
            """Open an independent handle on its own thread and report actual admission outcome."""
            try:
                with RecordStore.open(self.root) as store:
                    if identity == "second":
                        def trace(sql):
                            """Acknowledge the competing real BEGIN immediately before SQLite executes it."""
                            if sql == "BEGIN IMMEDIATE":
                                second_begin.set()
                        store._connection.set_trace_callback(trace)
                    try:
                        results.append(store.reserve_resources(reservation(identity, maxima=vector(tool_calls=25))))
                    except ResourceCapacityError:
                        results.append("capacity")
            except BaseException as error:
                failures.append(error)

        with patch.object(resource_ledger, "_fault", side_effect=seam):
            first = threading.Thread(target=worker, args=("first",), name="resource-first")
            second = threading.Thread(target=worker, args=("second",))
            first.start()
            try:
                self.assertTrue(first_written.wait(10))
                second.start()
                self.assertTrue(second_begin.wait(10))
            finally:
                release.set()
                first.join(10)
                if second.ident is not None:
                    second.join(10)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
        self.assertFalse(failures, failures)
        self.assertEqual(results.count("capacity"), 1)
        snapshot = self.store.inspect_resources(limits=LIMITS).to_dict()
        self.assertEqual(len(snapshot["reservations"]), 1)
        row = next(r for r in snapshot["balances"] if r["account_id"] == "attempt" and r["purpose"] == "ordinary")
        tool = next(d for d in row["dimensions"] if d["dimension_id"] == "dim_tool_calls")
        self.assertEqual((tool["direct_reserved"], tool["available_for_local_use"]), ("25", "0"))

    def test_independent_process_capacity_and_identical_operation_races(self):
        """Pipes arrange real competing process transactions for distinct and identical requests."""
        program = '''
import json, sys
from research_pipeline import resource_ledger
from research_pipeline.store import RecordStore
from research_pipeline.resources import loads_request, ResourceCapacityError
store = RecordStore.open(sys.argv[1])
request = loads_request(sys.argv[2])
def seam(point):
    """Hold real first writes until the parent acknowledges the competing transaction."""
    if point == "after_writes" and sys.argv[3] == "first":
        print("written", flush=True)
        assert sys.stdin.readline().strip() == "release"
def trace(sql):
    """Acknowledge the second process entering the actual BEGIN IMMEDIATE."""
    if sql == "BEGIN IMMEDIATE" and sys.argv[3] == "second":
        print("begin", flush=True)
resource_ledger._fault = seam
store._connection.set_trace_callback(trace)
print("ready", flush=True)
assert sys.stdin.readline().strip() == "go"
try:
    result = store.reserve_resources(request)
    print(json.dumps(result.to_dict(), sort_keys=True), flush=True)
except ResourceCapacityError:
    print("capacity", flush=True)
finally:
    store.close()
'''
        def read_ack(child):
            """Bound pipe acknowledgments so a failed child cannot hang the test indefinitely."""
            if not select.select([child.stdout], [], [], 15)[0]:
                raise AssertionError("child acknowledgment timed out")
            return child.stdout.readline().strip()

        for identical in (False, True):
            root = self.parent / str(identical)
            with RecordStore.create(root, schema_version=3) as store:
                populate(store)
            first_request = reservation("first", maxima=vector(tool_calls=25))
            second_request = first_request if identical else reservation("second", maxima=vector(tool_calls=25))
            children = []
            try:
                for name, item in (("first", first_request), ("second", second_request)):
                    children.append(subprocess.Popen([sys.executable, "-B", "-c", program, str(root), canonical(item.to_dict()), name],
                        env=child_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                first, second = children
                self.assertEqual(read_ack(first), "ready")
                self.assertEqual(read_ack(second), "ready")
                first.stdin.write("go\n")
                first.stdin.flush()
                self.assertEqual(read_ack(first), "written")
                second.stdin.write("go\n")
                second.stdin.flush()
                self.assertEqual(read_ack(second), "begin")
                first.stdin.write("release\n")
                first.stdin.flush()
                out1, error1 = first.communicate(timeout=15)
                out2, error2 = second.communicate(timeout=15)
                self.assertEqual(first.returncode, 0, error1)
                self.assertEqual(second.returncode, 0, error2)
                receipt = json.loads(out1)
                if identical:
                    self.assertEqual(json.loads(out2), receipt)
                else:
                    self.assertEqual(out2.strip(), "capacity")
                with RecordStore.open(root) as store:
                    self.assertEqual(len(store.inspect_resources(limits=LIMITS).to_dict()["reservations"]), 1)
                    self.assertEqual(store.get_resource_operation(first_request.operation_id).to_dict(), receipt)
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=10)

    def test_consistent_inspection_under_a_competing_writer(self):
        """Inspection captures a complete old state while a real writer has uncommitted new rows."""
        read, written = threading.Event(), threading.Event()
        failures = []
        before = self.store.inspect_resources(limits=LIMITS)

        def seam(point):
            """Coordinate the reader snapshot and writer's real pending commitment."""
            if point == "inspection_after_counts":
                read.set()
                if not written.wait(10):
                    raise AssertionError("writer did not reach real writes")
            elif point == "after_writes":
                written.set()

        def writer():
            """Commit independently after inspection has established its read snapshot."""
            try:
                with RecordStore.open(self.root) as store:
                    if not read.wait(10):
                        raise AssertionError("reader did not start")
                    store.reserve_resources(reservation())
            except BaseException as error:
                failures.append(error)
                written.set()

        with patch.object(resource_ledger, "_fault", side_effect=seam):
            thread = threading.Thread(target=writer)
            thread.start()
            observed = self.store.inspect_resources(limits=LIMITS)
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures, failures)
        self.assertEqual(observed, before)
        self.assertNotEqual(self.store.inspect_resources(limits=LIMITS), before)

    def test_faults_before_writes_after_real_writes_and_after_commit(self):
        """Rollback and lost acknowledgment preserve distinct original-operation outcomes."""
        for point in ("before_writes", "after_writes", "after_commit"):
            item = reservation(point)
            before = self.store.inspect_resources(limits=LIMITS)

            def fail(boundary):
                """Interrupt the selected real resource boundary."""
                if boundary == point:
                    raise KeyboardInterrupt(point)

            with patch.object(resource_ledger, "_fault", side_effect=fail), self.assertRaises(KeyboardInterrupt):
                self.store.reserve_resources(item)
            with RecordStore.open(self.root) as reopened:
                result = reopened.get_resource_operation(item.operation_id)
                if point == "after_commit":
                    self.assertIsNotNone(result)
                    self.assertEqual(reopened.reserve_resources(item), result)
                else:
                    self.assertIsNone(result)
                    self.assertEqual(reopened.inspect_resources(limits=LIMITS), before)
                    self.assertIsNotNone(reopened.reserve_resources(item))

    def test_real_commit_and_rollback_denials(self):
        """SQLite authorizers exercise actual failures and resource-specific reconciliation diagnostics."""
        def deny_commit(action, first, second, database, source):
            """Deny a real COMMIT while permitting SQLite rollback."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and first == "COMMIT" else sqlite3.SQLITE_OK

        self.store._connection.set_authorizer(deny_commit)
        with self.assertRaisesRegex(StoreDatabaseError, "operation_id"):
            self.store.reserve_resources(reservation("denied_commit"))
        self.store._connection.set_authorizer(None)
        self.assertIsNone(self.store.get_resource_operation("op_denied_commit"))

        def deny_rollback(action, first, second, database, source):
            """Deny actual ROLLBACK so the store must invalidate its connection."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and first == "ROLLBACK" else sqlite3.SQLITE_OK

        def fail(boundary):
            """Interrupt only after all normalized rows were really inserted."""
            if boundary == "after_writes":
                raise KeyboardInterrupt("rollback denied")

        self.store._connection.set_authorizer(deny_rollback)
        with patch.object(resource_ledger, "_fault", side_effect=fail), self.assertRaises(KeyboardInterrupt):
            self.store.reserve_resources(reservation("denied_rollback"))
        with self.assertRaises(StoreClosedError):
            self.store.get_resource_operation("op_denied_rollback")
        with RecordStore.open(self.root) as store:
            self.assertIsNone(store.get_resource_operation("op_denied_rollback"))

    def test_checked_close_failure_after_commit_preserves_liability(self):
        """A failed close acknowledgment after real close cannot retroactively roll back a receipt."""
        class CheckedClose:
            """Forward every SQLite operation, failing only after the real connection has closed."""

            def __init__(self, connection):
                """Retain the actual connection rather than simulating transaction success."""
                self.connection = connection

            def __getattr__(self, name):
                """Delegate transaction behavior directly to SQLite."""
                return getattr(self.connection, name)

            def close(self):
                """Perform the actual close before injecting lost close acknowledgment."""
                self.connection.close()
                raise OSError("checked close failed")

        handle = RecordStore.open(self.root)
        item = reservation("close")
        result = handle.reserve_resources(item)
        handle._connection = CheckedClose(handle._connection)
        with self.assertRaises(OSError):
            handle.close()
        # The actual SQLite connection is already closed; avoid a second artificial failure.
        handle._connection = None
        with RecordStore.open(self.root) as store:
            self.assertEqual(store.get_resource_operation(item.operation_id), result)
            self.assertEqual(store.reserve_resources(item), result)

    def test_process_loss_before_and_after_commit(self):
        """Abrupt exits retain either no operation after rollback or the original committed liability."""
        for point in ("before_writes", "after_writes", "after_commit"):
            item = reservation(point)
            program = '''
import os, sys
from research_pipeline import resource_ledger
from research_pipeline.resources import loads_request
from research_pipeline.store import RecordStore
def crash(boundary):
    """Exit at a real operation boundary without Python exception cleanup."""
    if boundary == sys.argv[3]:
        os._exit(74)
resource_ledger._fault = crash
with RecordStore.open(sys.argv[1]) as store:
    store.reserve_resources(loads_request(sys.argv[2]))
'''
            result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root), canonical(item.to_dict()), point],
                                    env=child_environment(), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 74, result.stderr)
            with RecordStore.open(self.root) as store:
                receipt = store.get_resource_operation(item.operation_id)
                self.assertEqual(receipt is not None, point == "after_commit")
                if receipt is not None:
                    self.assertEqual(store.reserve_resources(item), receipt)

    def test_hot_journal_recovery_precedes_live_invariant_validation(self):
        """Spill actual large resource writes, prove unrecovered main-file inconsistency, then recover."""
        item = reservation("hot").to_dict()
        item["provenance"]["details"] = {"large": "x" * 50000}
        normalized = ResourceRequest.from_dict(item)
        before = self.store.inspect_resources(limits=LIMITS)
        self.store.close()
        original_bytes = (self.root / "metadata.sqlite3").read_bytes()
        program = '''
import os, sys
from research_pipeline import resource_ledger
from research_pipeline.resources import loads_request
from research_pipeline.store import RecordStore
def crash(point):
    """Exit after SQLite spilled real inserts beyond a deliberately small private test cache."""
    if point == "after_writes":
        os._exit(75)
resource_ledger._fault = crash
store = RecordStore.open(sys.argv[1])
store._connection.execute("PRAGMA cache_size=1")
store._connection.execute("PRAGMA cache_spill=ON")
store.reserve_resources(loads_request(sys.argv[2]))
'''
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root), canonical(normalized.to_dict())],
                                env=child_environment(), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 75, result.stderr)
        journal = self.root / "metadata.sqlite3-journal"
        self.assertTrue(journal.exists())
        self.assertNotEqual(journal.read_bytes()[:8], b"\0" * 8)
        self.assertNotEqual((self.root / "metadata.sqlite3").read_bytes(), original_bytes)
        immutable = sqlite3.connect((self.root / "metadata.sqlite3").as_uri() + "?immutable=1&mode=ro", uri=True)
        try:
            with self.assertRaises((ValueError, sqlite3.Error)):
                resource_ledger.validate_ledger(immutable)
        finally:
            immutable.close()
        with RecordStore.open(self.root) as store:
            self.assertEqual(store.inspect_resources(limits=LIMITS), before)
            self.assertIsNone(store.get_resource_operation(normalized.operation_id))
            self.assertIsNotNone(store.reserve_resources(normalized))
        self.assertFalse(journal.exists())
