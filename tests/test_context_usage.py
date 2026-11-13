"""Deterministic native-shape fixtures, not paid inference or quota evidence."""
import unittest
from tests import use_checkout
use_checkout()
from research_pipeline import context_usage as usage


def params(length=122000, window=212000, total=900000, thread='native', turn='turn'):
    def counters(n):
        return dict(totalTokens=n, inputTokens=n, cachedInputTokens=0,
                    outputTokens=0, reasoningOutputTokens=0, cacheWriteInputTokens=0)
    return {'threadId': thread, 'turnId': turn, 'tokenUsage': {
        'last': counters(length), 'total': counters(total), 'modelContextWindow': window}}


class UsageTests(unittest.TestCase):
    def test_controller_basis_boundary_windows_and_unclamped_overshoot(self):
        for length, window, expected, reached in ((121999,212000,54.9995,False),
                (122000,212000,55,True),(122001,212000,55.0005,True),
                (5500,10000,55,True),(424000,212000,206,True), (0,212000,0,False)):
            result = usage.normalize(params(length, window)['tokenUsage'])
            self.assertAlmostEqual(result['occupancy_percent'], expected)
            self.assertEqual(result['threshold_reached'], reached)

    def test_malformed_and_missing_are_not_guessed(self):
        for length, window in ((True,10),(-1,10),(1,None),(1,False),(1,0),(1,float('inf')),(1,12.0)):
            with self.subTest(length=length, window=window), self.assertRaises(ValueError):
                usage.normalize(params(length,window)['tokenUsage'])
        for value in (None,{}, {'last':None}):
            with self.assertRaises(ValueError): usage.normalize(value)

    def test_independent_contexts_latched_trigger_and_cumulative_not_summed(self):
        records = [{'task_id': role, 'native_thread_id': role} for role in ('primary','researcher','opponent','verifier')]
        state = {'contexts': dict(enumerate(records))}
        for record in records:
            usage.observe(record, params(length=10000,total=900000,thread=record['task_id']))
        for record in records:
            usage.observe(record, params(thread=record['task_id']))
            trigger = record['threshold_observation'].copy()
            usage.observe(record, params(length=100,thread=record['task_id']))
            self.assertEqual(record['threshold_observation'],trigger)
            self.assertEqual(usage.task_usage(state,record['task_id'])['observed_cumulative']['totalTokens'],900000)
        fresh = {'task_id':'primary','native_thread_id':'fresh'}
        state['contexts']['fresh'] = fresh
        usage.observe(fresh,params(length=10,total=200,thread='fresh'))
        self.assertNotIn('threshold_observation',fresh)
        self.assertEqual(usage.task_usage(state,'primary')['observed_cumulative']['totalTokens'],900200)
        old = records[1].copy()
        usage.observe(records[0],params(total=900001,thread='primary'))
        self.assertEqual(records[1],old)

    def test_invalid_status_accounting_and_injection_are_explicit(self):
        record={'task_id':'primary','native_thread_id':'native'}
        usage.observe(record, params(length=10,total=900000))
        usage.observe(record, params(total=999999), 'injected-test')
        self.assertEqual(record['cumulative_usage']['totalTokens'],900000)
        usage.observe(record,params(window=None))
        self.assertEqual(record['measurement']['status'],'unreliable')
        usage.observe(record,params(total=1))
        self.assertTrue(record['accounting_incomplete'])
        self.assertEqual(record['cumulative_usage']['totalTokens'],900000)
        with self.assertRaises(ValueError): usage.observe(record,params(thread='foreign'))
