"""Explicit lock-order evidence for competing control successors on independent handles."""

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c
from research_pipeline.store import RecordStore, RevisionConflictError
from tests import run_control_fixtures as f


class ControlSerializationTests(unittest.TestCase):
    """Hold the first actual SQLite write until the second writer attempts BEGIN IMMEDIATE."""

    def test_pause_cancel_both_orders_and_competing_checkpoints(self):
        """Each lock order admits exactly one successor and preserves both initial/pending obligations."""
        with TemporaryDirectory(prefix='control-serialization-') as temporary:
            for index, actions in enumerate((('pause', 'cancel'), ('cancel', 'pause'), ('checkpoint', 'checkpoint'))):
                with self.subTest(actions=actions):
                    root = Path(temporary) / str(index)
                    with RecordStore.create(root) as store:
                        request = f.populate(store)
                        original = f.commit(store, request)
                    choices = [f.successor(request, original, action, operation='successor-' + str(i)) for i, action in enumerate(actions)]
                    inserted, attempted = threading.Event(), threading.Event()
                    results, failures = {}, {}

                    def fault(point):
                        """Keep the first write lock until SQLite observes the competing BEGIN."""
                        if point == 'after_first_revision' and threading.current_thread().name == 'first-control':
                            inserted.set()
                            if not attempted.wait(10):
                                raise AssertionError('second writer never attempted BEGIN')

                    def writer(number):
                        """Use a thread-owned real connection and record its durable result or conflict."""
                        try:
                            with RecordStore.open(root) as handle:
                                if number:
                                    if not inserted.wait(10):
                                        raise AssertionError('first writer never inserted')

                                    def trace(sql):
                                        """Signal the actual competing SQLite write-lock request."""
                                        if sql == 'BEGIN IMMEDIATE':
                                            attempted.set()

                                    handle._connection.set_trace_callback(trace)
                                results[number] = f.commit(handle, choices[number])
                        except BaseException as error:
                            failures[number] = error

                    threads = [threading.Thread(target=writer, args=(i,), name='first-control' if i == 0 else 'second-control') for i in range(2)]
                    with patch('research_pipeline.store._fault', fault):
                        for thread in threads:
                            thread.start()
                        for thread in threads:
                            thread.join(30)
                            self.assertFalse(thread.is_alive())
                    self.assertEqual(set(results), {0})
                    self.assertEqual(set(failures), {1})
                    self.assertIsInstance(failures[1], RevisionConflictError)
                    with RecordStore.open(root) as store:
                        inspected = store.inspect_run_control('run', limits=f.LIMITS).to_dict()
                        self.assertEqual(len(inspected['pending_obligations']), 2)
                        self.assertEqual(inspected['disposition'], {'pause': 'paused', 'cancel': 'cancelled', 'checkpoint': 'prepared'}[actions[0]])
                        self.assertIsNone(store.head(c.obligation_id('successor-1')))
                        self.assertEqual(store.get_run_control_operation('prepare', limits=f.LIMITS), original)
