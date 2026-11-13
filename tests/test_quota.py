"""Consequential weekly normalization, sparse updates and freshness boundaries."""
from copy import deepcopy
import unittest

from tests import use_checkout
use_checkout()
from research_pipeline import quota


def payload(used=20, position='secondary', duration=10080, **fields):
    return {'rateLimits': {'limitId': 'codex', position: {
        'usedPercent': used, 'windowDurationMins': duration, **fields}}}


class QuotaTests(unittest.TestCase):
    def observe(self, record, data, full=True, now=100, epoch=1000):
        return quota.observe(record, data, full=full, now=now, epoch=epoch)

    def error(self, record, now=100, epoch=1000):
        return quota.admission_error({'quota': record}, now=now, epoch=epoch)

    def test_above_exact_below_and_unrounded_reserve(self):
        for used, cutoff in ((84, False), (84.999999, False), (85, True), (85.000001, True), (100, True), (110, True)):
            with self.subTest(used=used):
                record = {}
                self.observe(record, payload(used))
                self.assertEqual(bool(record.get('cutoff')), cutoff)
                self.assertEqual(self.error(record) is not None, cutoff)

    def test_only_real_weekly_window_in_either_position(self):
        for position in ('primary', 'secondary'):
            record = {}
            self.observe(record, payload(position=position))
            self.assertIsNone(self.error(record))
            for duration in (None, 300, 1440, 10079, 10081, '10080'):
                self.observe(record, payload(10, position, duration))
                self.assertIsNotNone(self.error(record))
                self.assertNotIn('cutoff', record)

    def test_invalid_weekly_telemetry_never_grants_allowance(self):
        for used in (None, True, -1, '20', float('nan'), float('inf'), {}, []):
            record = {}
            self.observe(record, payload(used))
            self.assertIsNotNone(self.error(record))
            self.assertFalse(record.get('cutoff'))
        record = {}
        self.observe(record, {})
        self.assertIsNotNone(self.error(record))

    def test_most_restrictive_bucket_including_incomplete_other_bucket(self):
        record = {}
        data = {'rateLimits': payload(10)['rateLimits'], 'rateLimitsByLimitId': {
            'codex': payload(10)['rateLimits'], 'other': payload(86, 'primary')['rateLimits'],
            'missing': {}}}
        self.observe(record, data)
        self.assertFalse(record['complete'])
        self.assertEqual(record['remaining_percent'], 14)
        self.assertEqual(record['cutoff']['bucket_id'], 'other')
        self.assertIn('STOP', self.error(record))

    def test_incomplete_full_read_blocks_but_partial_omission_preserves_age_and_bucket(self):
        record = {}
        self.observe(record, {'rateLimitsByLimitId': {'a': payload(50)['rateLimits'], 'b': payload(70)['rateLimits']}})
        original = deepcopy(record['buckets'])
        self.observe(record, {'rateLimits': {'limitId': 'a', 'primary': {'usedPercent': 99, 'windowDurationMins': 300},
                                              'secondary': None}}, full=False, now=159)
        self.assertEqual(record['remaining_percent'], 30)
        for key in ('a', 'b'):
            self.assertEqual(record['buckets'][key]['windows']['secondary'], original[key]['windows']['secondary'])
        self.assertIsNone(self.error(record, now=159))
        self.assertIn('expired', self.error(record, now=160))
        self.observe(record, {'rateLimitsByLimitId': {'a': payload(10)['rateLimits'], 'b': {}}}, now=160)
        self.assertIsNotNone(self.error(record, now=160))
        self.assertFalse(record.get('cutoff'))

    def test_sparse_weekly_update_inherits_duration_but_does_not_remove_cutoff(self):
        record = {}
        self.observe(record, payload(20))
        self.observe(record, {'rateLimits': {'limitId': 'codex', 'secondary': {'usedPercent': 85}}}, full=False, now=110)
        first = deepcopy(record['cutoff'])
        self.observe(record, payload(1, resetsAt=9000), now=120)
        self.assertEqual(record['cutoff'], first)
        self.assertIn('STOP', self.error(record, now=120))
        self.observe(record, {}, full=False, now=130)
        self.assertEqual(record['cutoff'], first)

    def test_reset_needs_observed_refresh_never_infers_replenishment(self):
        record = {}
        self.observe(record, payload(20, resetsAt=1010))
        self.assertIsNone(self.error(record))
        self.assertIn('expired', self.error(record, now=110, epoch=1010))
        self.assertEqual(record['remaining_percent'], 80)
        self.observe(record, payload(40, resetsAt=7000), now=110, epoch=1010)
        self.assertIsNone(self.error(record, now=110, epoch=1010))

    def test_explicit_native_usage_denial_is_not_recovered_from_percentages(self):
        record = {}
        self.observe(record, {**payload(20), 'ordinaryUsageAllowed': False})
        self.assertIn('denies', self.error(record))
        self.observe(record, payload(1), full=False, now=110)
        self.assertIn('denies', self.error(record, now=110))
        self.observe(record, payload(1), now=120)
        self.assertIn('denies', self.error(record, now=120))

    def test_metadata_only_notification_without_limit_id_does_not_invalidate_or_renew_weekly_basis(self):
        record = {}
        self.observe(record, payload(20))
        original = deepcopy(record['buckets'])
        self.observe(record, {'rateLimits': {'limitId':None, 'planType':'pro', 'secondary':None}},
                     full=False, now=150)
        self.assertEqual(record['buckets'],original)
        self.assertIsNone(self.error(record,now=159))
        self.assertIn('expired',self.error(record,now=160))

    def test_injected_cutoff_and_native_basis_remain_separate(self):
        record = {}
        self.observe(record, payload(20))
        native = deepcopy(record['native_observation'])
        quota.observe(record, payload(85), full=False, provenance='injected-test-cutoff', now=101, epoch=1001)
        self.assertEqual(record['native_observation'], native)
        self.assertEqual(record['cutoff']['provenance'], 'injected-test-cutoff')
