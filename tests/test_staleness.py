"""Explicit-clock checks: raw length only, independent contexts, warnings only."""
import unittest
from tests import use_checkout
use_checkout()
from research_pipeline import staleness


def measured(length):
    return {'status': 'measured', 'length': length}


class StalenessTests(unittest.TestCase):
    def test_first_sample_does_not_postpone_attachment_or_warning_multiples(self):
        clock = staleness.attach(100)
        self.assertFalse(staleness.measure(clock, measured(10001), 2799))
        self.assertFalse(staleness.due(clock, 2700, 2799))
        self.assertEqual([n['scheduled_seconds'] for n in staleness.due(clock, 2700, 2800)], [2700])
        self.assertFalse(staleness.due(clock, 2700, 2801))
        notices = staleness.due(clock, 2700, 8201)
        self.assertEqual([n['scheduled_seconds'] for n in notices], [5400, 8100])
        self.assertEqual([n['elapsed_seconds'] for n in notices], [8101, 8101])
        self.assertEqual(clock['changed_monotonic'], 100)

    def test_raw_increase_decrease_even_below_occupancy_floor_reset(self):
        clock = staleness.attach(0)
        staleness.measure(clock, measured(10000), 1)
        for now, length in ((20, 10001), (40, 10000), (60, 9999)):
            self.assertTrue(staleness.measure(clock, measured(length), now))
            self.assertEqual(clock['changed_monotonic'], now)
            self.assertFalse(staleness.due(clock, 30, now + 29))
            self.assertEqual(len(staleness.due(clock, 30, now + 30)), 1)

    def test_unchanged_cumulative_window_and_turn_changes_do_not_reset(self):
        clock = staleness.attach(0)
        for now in (1, 29, 30, 59):
            self.assertFalse(staleness.measure(clock, {**measured(10000), 'window': now,
                'turn_id': str(now), 'raw': {'total': {'totalTokens': 1000 * now}}}, now))
        self.assertEqual(len(staleness.due(clock, 30, 60)), 2)
        self.assertEqual(clock['changed_monotonic'], 0)

    def test_independent_fresh_successors_and_missing_telemetry(self):
        a, b = staleness.attach(0), staleness.attach(5)
        staleness.measure(a, measured(100), 1)
        staleness.measure(b, measured(100), 6)
        staleness.measure(a, measured(101), 20)
        self.assertFalse(staleness.due(a, 30, 35))
        self.assertEqual(len(staleness.due(b, 30, 35)), 1)
        staleness.measure(b, {'status': 'missing'}, 36)
        self.assertFalse(staleness.due(b, 30, 65))
        self.assertEqual(b['changed_monotonic'], 5)
        staleness.measure(b, measured(100), 66)
        self.assertEqual(len(staleness.due(b, 30, 66)), 1)
        successor = staleness.attach(66)
        staleness.measure(successor, measured(100), 67)
        self.assertFalse(staleness.due(successor, 30, 95))
        self.assertEqual(len(staleness.due(successor, 30, 96)), 1)
