"""Independent-handle authority races, real process/close loss, backup and resource preservation."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from research_pipeline import operating_authority as a
from research_pipeline.backup import create_backup, restore_backup
from research_pipeline.store import RecordStore, RevisionConflictError
from research_pipeline.snapshot import SnapshotSelection, RootSelector
from research_pipeline.view_plan import plan_readable_snapshot
from tests.operating_fixtures import TIME, KEY, REVOKER_KEY, LIMITS, policy, revoker_policy, scope, empty, short_note, prepare, decision, sign
from tests.test_vault import child_environment
from tests.test_store import record, request
from tests import resource_fixtures as resources
from tests.snapshot_fixtures import limits as snapshot_limits


class OperatingRecoveryTests(unittest.TestCase):
    """Exercise actual durable stores without delegating acceptance authority to advisory tests."""

    def setUp(self):
        """Create an isolated schema-3 runtime for concurrent handles, resource history and backup."""
        temporary = TemporaryDirectory(prefix="authority-recovery-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)

    def approve_setup(self):
        """Commit an incomplete dossier and its independently signed setup-only approval."""
        empty(self.store)
        binding = prepare(self.store, scope())
        signed = sign(decision(binding, scope()))
        receipt = self.store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
        return binding, signed, receipt

    def inspect(self, store, trust):
        """Evaluate the actual current stream with explicit policy and trusted time."""
        return store.inspect_operating_eligibility("synthetic", "project", purpose="setup", policy=trust, evaluated_at=TIME, limits=LIMITS).to_dict()

    def test_competing_successors_and_identical_delivery(self):
        """Independent write transactions produce one CAS winner or the same original receipt for duplicate delivery."""
        binding, signed, _ = self.approve_setup()
        prior = a.encode_envelope(signed)
        for duplicate in (False, True):
            revision = prior.revision + 1
            choices = [sign(decision(binding, scope(), revision=revision, previous=prior,
                                     operation="race" + str(revision) + str(i))) for i in range(2)]
            if duplicate:
                choices[1] = choices[0]
            barrier = threading.Barrier(2, timeout=10)
            results, failures = [], []

            def writer(index):
                """Deliver unchanged signed bytes from a fresh thread-owned store connection."""
                try:
                    with RecordStore.open(self.root) as store:
                        barrier.wait()
                        results.append((index, store.commit_operating_decision(choices[index], policy=policy(), evaluated_at=TIME, limits=LIMITS)))
                except BaseException as error:
                    failures.append(error)

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(20)
                self.assertFalse(thread.is_alive())
            if duplicate:
                self.assertEqual(failures, [])
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0][1], results[1][1])
            else:
                self.assertEqual(len(results), 1)
                self.assertEqual(len(failures), 1)
                self.assertIsInstance(failures[0], RevisionConflictError)
            prior = a.encode_envelope(choices[results[0][0]])
        self.assertEqual(self.store.head(prior.record_id), 3)

    def test_revocation_and_inspection_share_one_snapshot(self):
        """A reader established before a competing reduction sees one complete approval snapshot, then revocation."""
        binding, signed, _ = self.approve_setup()
        reduced = sign(decision(binding, revision=2, previous=a.encode_envelope(signed), outcome="revoke", operation="revoke"))
        established, inserted = threading.Event(), threading.Event()
        results, failures = {}, []

        def read_seam(point):
            """Wait after the real audit SELECT establishes the old SQLite read snapshot."""
            if point == "snapshot_established":
                established.set()
                if not inserted.wait(10):
                    raise AssertionError("writer never reached actual insertion")

        def write_seam(point):
            """Observe actual successor insertion before SQLite waits to commit against the reader."""
            if point == "after_first_revision":
                inserted.set()

        def reader():
            """Inspect using an independent handle confined to its reader thread."""
            try:
                with RecordStore.open(self.root) as store:
                    results["inspection"] = self.inspect(store, policy())
            except BaseException as error:
                failures.append(error)

        def writer():
            """Append only after the reader has established its real transaction snapshot."""
            try:
                if not established.wait(10):
                    raise AssertionError("reader snapshot not established")
                with RecordStore.open(self.root) as store:
                    results["reduction"] = store.commit_operating_decision(reduced, policy=policy(), evaluated_at=TIME, limits=LIMITS)
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
        with patch("research_pipeline.operating_authority_store._fault", read_seam), patch("research_pipeline.store._fault", write_seam):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(20)
                self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results["inspection"]["status"], "eligible_setup")
        self.assertEqual(results["inspection"]["decision"]["revision"], 1)
        self.assertEqual(self.inspect(self.store, policy())["status"], "revoked")

    def test_backup_restore_current_trust_and_non_authoritative_views(self):
        """Restore checks current trust; valid historical projections preserve notices and exclude secrets."""
        binding, signed, original = self.approve_setup()
        backup = self.parent / "backup"
        create_backup(self.store, backup)
        reduced = sign(decision(binding, revision=2, previous=a.encode_envelope(signed), outcome="revoke", operation="later-revocation"))
        self.store.commit_operating_decision(reduced, policy=policy(), evaluated_at=TIME, limits=LIMITS)
        with restore_backup(backup, self.parent / "restored") as restored:
            self.assertEqual(self.inspect(restored, policy())["status"], "eligible_setup")
            self.assertEqual(self.inspect(restored, None)["status"], "missing_trust")
            self.assertEqual(self.inspect(restored, policy(capabilities=[]))["status"], "policy_denied")
            self.assertEqual(self.inspect(restored, a.OperatorPolicy("synthetic", []))["status"], "missing_trust")
            self.assertIsNone(restored.get_operating_operation("later-revocation", limits=LIMITS))
            self.assertEqual(restored.get_operating_operation("approve", limits=LIMITS), original)
            history = restored.inspect_operating_history("synthetic", "project", policy=None, limits=LIMITS).to_dict()
            self.assertEqual(len(history["decisions"]), 1)
            self.assertEqual(history["decisions"][0]["signature_status"], "unavailable")
        selection = SnapshotSelection(RootSelector("project", 1),
            (RootSelector(signed.to_dict()["decision"]["decision_id"], 1),))
        plan = plan_readable_snapshot(self.store.capture_snapshot(selection, limits=snapshot_limits()))
        rendered = b"\n".join(item.data for item in plan.generated_files)
        self.assertIn(b"## Operating decision\n\nOperating decision status: historical; unverified. ", rendered)
        self.assertIn(b"historical; unverified", rendered)
        self.assertIn(b"An approval is not current permission", rendered)
        self.assertNotIn(KEY, rendered)
        for path in backup.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY, path.read_bytes())
        self.assertNotIn(KEY, (self.root / "metadata.sqlite3").read_bytes())

    def test_resource_liabilities_and_predecessor_records_unchanged(self):
        """Approval and independent reduction leave every resource row and predecessor envelope unchanged."""
        empty(self.store)
        self.store.submit(request("task", [record("task", kind="task_specification")]))
        self.store.create_resource_account(resources.root_request())
        for item in (resources.allocation("run", "run", "project"), resources.allocation("task", "task", "run"),
                     resources.allocation("attempt", "attempt", "task")):
            self.store.allocate_resources(item)
        self.store.reserve_resources(resources.reservation())
        self.store.observe_resource_usage(resources.observation("lost", event="acknowledgment_loss"))
        tables = ("resource_operations", "resource_accounts", "resource_allocations", "resource_reservations", "resource_record_links")

        def state():
            """Snapshot complete resource rows, including uncertain liabilities and immutable request history."""
            return {table: self.store._connection.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall() for table in tables}

        before = state()
        project = self.store.get_revision("project", 1)
        corpus = self.store.get_revision("corpus", 1)
        binding = prepare(self.store, scope())
        signed = sign(decision(binding, scope()))
        self.store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
        self.assertEqual(state(), before)
        prior = self.store.get_revision(signed.to_dict()["decision"]["decision_id"], 1)
        reduced = sign(decision(binding, revision=2, previous=prior, outcome="revoke", operation="reduce",
            principal_id="revoker", key_id="revoker1"), REVOKER_KEY)
        self.store.commit_operating_decision(reduced, policy=revoker_policy(), evaluated_at=TIME, limits=LIMITS)
        self.assertEqual(state(), before)
        self.assertEqual(self.store.get_revision(prior.record_id, 1), prior)
        self.assertEqual(self.store.get_revision("project", 1), project)
        self.assertEqual(self.store.get_revision("corpus", 1), corpus)

    def test_abrupt_process_reopen_and_actual_close_acknowledgment_loss(self):
        """Actual process exits before/after commit and actual close loss reconcile solely by original operation ID."""
        empty(self.store)
        signed = sign(decision(prepare(self.store, scope()), scope()))
        saved = self.parent / "signed.json"
        saved.write_text(a.dumps_signed_decision(signed))
        program = '''
import os, sys
from pathlib import Path
from research_pipeline import operating_authority as a
from research_pipeline.store import RecordStore
import research_pipeline.store as module
from tests.operating_fixtures import TIME, LIMITS, policy

def fault(point):
    """Exit without cleanup at the selected actual storage boundary."""
    if point == sys.argv[3]: os._exit(73)
module._fault = fault
with RecordStore.open(sys.argv[1]) as store:
    store.commit_operating_decision(a.loads_signed_decision(Path(sys.argv[2]).read_bytes()), policy=policy(), evaluated_at=TIME, limits=LIMITS)
'''
        for boundary in ("before_metadata", "after_first_revision", "after_commit"):
            result = subprocess.run([sys.executable, "-B", "-c", program, str(self.root), str(saved), boundary],
                env=child_environment(), cwd=self.parent, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 73, result.stderr)
            with RecordStore.open(self.root) as reopened:
                recovered = reopened.get_operating_operation("approve", limits=LIMITS)
                self.assertEqual(recovered is not None, boundary == "after_commit")
        original = self.store.get_operating_operation("approve", limits=LIMITS)

        class CheckedClose:
            """Delegate to the actual SQLite handle and lose only its final close acknowledgment."""

            def __init__(self, connection):
                """Retain the real connection for a single actual close."""
                self.connection = connection

            def close(self):
                """Perform the real close before reporting injected acknowledgment loss."""
                self.connection.close()
                raise OSError("synthetic checked-close acknowledgment loss")

        handle = RecordStore.open(self.root)
        self.assertEqual(handle.commit_operating_decision(signed, policy=None, evaluated_at=None, limits=LIMITS), original)
        handle._connection = CheckedClose(handle._connection)
        with self.assertRaises(OSError):
            handle.close()
        handle._connection = None
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.get_operating_operation("approve", limits=LIMITS), original)
