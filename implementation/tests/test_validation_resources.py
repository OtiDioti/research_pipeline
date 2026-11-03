"""Pure resource and protocol regression cases; no host limits or affinity are changed."""

import json
import struct
import unittest
from unittest.mock import patch

from tests.validation_fixtures import load_validator

v = load_validator()


class ResourceTests(unittest.TestCase):
    """Verify resource arithmetic and exposed Linux hierarchy interpretation."""

    def test_formula(self):
        """Cover empty/small work, odd/even units and conservative quota fractions."""
        for available in (1, 2, 3, 4, 64):
            for remaining in (0, 1, 2, 3, 4, 5, 85, 1000):
                with self.subTest(A=available, T=remaining):
                    self.assertEqual(v.concurrency_budget(available, remaining),
                                     min(remaining // 2, max(0, available - 2)))
        for quota, period, expected in [('50000', '100000', 1), ('250000', '100000', 2),
                                         ('max', '100000', None), ('-1', '100000', None)]:
            self.assertEqual(v.quota_bound(quota, period), expected)
        for quota, period in [('0', '1'), ('-2', '1'), ('1', '0'), ('x', '1')]:
            with self.assertRaises(ValueError):
                v.quota_bound(quota, period)

    def hierarchy(self, files, *, membership='0::/a/b\n', mount='1 0 0:1 / /cg rw - cgroup2 cgroup rw\n'):
        """Resolve a fixture filesystem, retaining absent and unreadable distinctions."""
        def read(path):
            """Return explicit fixture text or an ordinary filesystem failure."""
            value = files.get(path)
            if value is None:
                raise FileNotFoundError(path)
            if isinstance(value, Exception):
                raise value
            return value
        return v.cgroup_constraints(membership, mount, read)

    def v2_files(self):
        """Supply a fully delegated fixture with restrictive ancestor quota and cpusets."""
        files = {}
        for directory in ('/cg', '/cg/a', '/cg/a/b'):
            files[directory + '/cgroup.controllers'] = 'cpu cpuset'
            files[directory + '/cgroup.subtree_control'] = 'cpu cpuset'
            files[directory + '/cpu.max'] = 'max 100000'
            files[directory + '/cpuset.cpus.effective'] = '0-7'
        files['/cg/a/cpu.max'] = '250000 100000'
        files['/cg/a/cpuset.cpus.effective'] = '2-5'
        return files

    def test_v2_ancestors(self):
        """Ancestor quotas and cpusets constrain a less-restricted leaf."""
        bounds, masks, limitations, _ = self.hierarchy(self.v2_files())
        self.assertEqual(bounds, [('/cg/a', 2)])
        self.assertEqual(set.intersection(*masks), {2, 3, 4, 5})
        self.assertEqual(limitations, [])

    def test_disabled_cpu_and_absent_root(self):
        """A listed but never delegated CPU controller does not imply an unknown quota."""
        files = self.v2_files()
        for directory in ('/cg', '/cg/a', '/cg/a/b'):
            files[directory + '/cgroup.subtree_control'] = 'cpuset'
            del files[directory + '/cpu.max']
        self.assertEqual(self.hierarchy(files)[2], [])
        files = self.v2_files()
        del files['/cg/cpu.max']
        self.assertEqual(self.hierarchy(files)[2], [])

    def test_unknown_limits(self):
        """Malformed, missing active and inaccessible constraints are explicit unknowns."""
        for value in (None, '0 100000', 'max 0', 'not quota', PermissionError('denied')):
            files = self.v2_files()
            files['/cg/a/cpu.max'] = value
            self.assertTrue(self.hierarchy(files)[2])
        files = self.v2_files()
        files['/cg/a/cpuset.cpus.effective'] = '5-2'
        self.assertTrue(self.hierarchy(files)[2])

    def test_v1_separate_mounts_and_inheritance(self):
        """Resolve separate v1 mounts and empty inherited cpusets, including escaped paths."""
        files = {'/cpu space/cpu.cfs_quota_us': '-1', '/cpu space/cpu.cfs_period_us': '100000',
                 '/cpu space/a/cpu.cfs_quota_us': '150000', '/cpu space/a/cpu.cfs_period_us': '100000',
                 '/sets/cpuset.cpus': '1-4', '/sets/a/cpuset.cpus': ''}
        bounds, masks, limitations, _ = self.hierarchy(files, membership='2:cpu,cpuacct:/a\n3:cpuset:/a\n',
            mount='1 0 0:1 / /cpu\\040space rw - cgroup cgroup rw,cpu,cpuacct\n'
                  '2 0 0:2 / /sets rw - cgroup cgroup rw,cpuset\n')
        self.assertEqual(bounds, [('/cpu space/a', 1)])
        self.assertEqual(masks, [{1, 2, 3, 4}])
        self.assertEqual(limitations, [])

    def test_hidden_and_ambiguous_mounts(self):
        """Hidden ancestry and multiple possible mounts cannot advertise unrestricted CPUs."""
        files = self.v2_files()
        self.assertTrue(self.hierarchy(files, mount='1 0 0:1 /a /cg rw - cgroup2 cgroup rw\n')[2])
        self.assertTrue(self.hierarchy(files, mount=('1 0 0:1 / /cg rw - cgroup2 cgroup rw\n' * 2))[2])
        self.assertTrue(self.hierarchy(files, mount='')[2])

    def test_ranges_and_unknown_sampling(self):
        """Range parsing is strict and unknown quotas force a one-CPU sample."""
        self.assertEqual(v.parse_cpu_set('0-2,5,7-8'), {0, 1, 2, 5, 7, 8})
        for value in ('', '2-1', '-1', '1,,2', '0-100000000', 'a', '1-2-3'):
            with self.assertRaises(ValueError):
                v.parse_cpu_set(value)
        with patch.object(v, 'cgroup_constraints', return_value=([], [], ['unknown quota'], [])):
            self.assertEqual(v.sample_resources()['A'], 1)
        with patch.object(v.os, 'sched_getaffinity', side_effect=OSError('unavailable')):
            sample = v.sample_resources()
            self.assertIsNone(sample['allowed'])
            self.assertTrue(any('affinity unavailable' in item for item in sample['limitations']))


class ProtocolTests(unittest.TestCase):
    """Reject corrupt worker evidence independently of process execution."""

    def setUp(self):
        """Create two real discovered leaves with known ordered identities."""
        self.tests = [unittest.FunctionTestCase(lambda: None, description=str(index)) for index in range(2)]
        self.leaves = [dict(ordinal=index, id=f'fixture.C.test_{index}', owner='fixture', class_name='fixture.C',
                            test=test, cls=type(test)) for index, test in enumerate(self.tests)]
        self.ledger = v.EventLedger(0, 123, self.leaves, [2], True)
        self.hello = dict(type='hello', version=1, unit=0, pid=123,
                          digest=v.inventory_digest([item['id'] for item in self.leaves]), affinity=[2])

    def event(self, seq, kind, ordinal=0, **changes):
        """Construct explicit protocol inputs with independently specified transitions."""
        value = dict(type='event', seq=seq, kind=kind, ordinal=ordinal,
                     id=f'fixture.C.test_{ordinal}', phase='', scope='', subtest='', detail='')
        value.update(changes)
        return value

    def end(self):
        """Build a final report from independently observable completed ledger events."""
        return dict(type='end', counters=dict(self.ledger.counts), started=list(self.ledger.started),
                    completed=list(self.ledger.completed), execution_seconds=0.1)

    def test_complete_and_trailing(self):
        """Accept exact-once completion and reject any frame after the one end report."""
        self.ledger.accept(self.hello)
        for ordinal in range(2):
            for kind in ('start', 'success', 'stop'):
                self.ledger.accept(self.event(len(self.ledger.events), kind, ordinal))
        self.ledger.accept(self.end())
        self.ledger.finish()
        self.assertEqual(self.ledger.counts['successful'], 2)
        with self.assertRaises(v.ValidationError):
            self.ledger.accept(self.end())

    def test_bad_identity_and_schema(self):
        """Reject wrong unit, digest, PID, mask, field types and extra fields."""
        for field, value in [('unit', 1), ('pid', 124), ('digest', 'bad'), ('affinity', [3]),
                             ('version', True), ('extra', 1)]:
            ledger = v.EventLedger(0, 123, self.leaves, [2])
            with self.assertRaises(v.ValidationError):
                ledger.accept(dict(self.hello, **{field: value}))

    def test_duplicate_unknown_and_missing_events(self):
        """Unknown IDs, duplicate starts, premature callbacks and missing stops fail closed."""
        cases = [[self.event(0, 'stop')], [self.event(0, 'start', id='unknown')],
                 [self.event(0, 'start', ordinal=99)],
                 [self.event(0, 'start'), self.event(1, 'start')],
                 [self.event(1, 'start')], [self.event(0, 'start'), self.event(1, 'stop')]]
        for events in cases:
            self.ledger = v.EventLedger(0, 123, self.leaves, [2])
            self.ledger.accept(self.hello)
            with self.assertRaises(v.ValidationError):
                for event in events:
                    self.ledger.accept(event)
        self.ledger = v.EventLedger(0, 123, self.leaves, [2])
        self.ledger.accept(self.hello)
        self.ledger.accept(self.event(0, 'start'))
        with self.assertRaises(v.ValidationError):
            self.ledger.accept(self.end())

    def test_inconsistent_counters_and_stock_order(self):
        """Worker totals cannot override actual events or stock discovery order."""
        self.ledger.accept(self.hello)
        for kind in ('start', 'success', 'stop'):
            self.ledger.accept(self.event(len(self.ledger.events), kind, 1))
        with self.assertRaises(v.ValidationError):
            self.ledger.accept(self.event(3, 'start', 0))
        end = self.end()
        end['counters']['successful'] += 1
        with self.assertRaises(v.ValidationError):
            self.ledger.accept(end)
        self.ledger.accept(self.end())
        with self.assertRaises(v.ValidationError):
            self.ledger.finish()

    def test_fixture_accounting(self):
        """Fixture skips explain unstarted leaves without false starts or success credit."""
        self.ledger.accept(self.hello)
        frame = dict(type='event', seq=0, kind='skip', ordinal=None, id='setUpClass (fixture.C)',
                     phase='setUpClass', scope='fixture.C', subtest='', detail='skip reason')
        self.ledger.accept(frame)
        self.ledger.accept(self.end())
        self.ledger.finish()
        self.assertEqual(self.ledger.counts['testsRun'], 0)
        self.assertEqual(self.ledger.counts['successful'], 0)
        self.assertEqual(self.ledger.counts['skipped'], 1)
        self.assertEqual([item['kind'] for item in self.ledger.dispositions()], ['fixture-skipped'] * 2)

    def test_unordered_setup_has_no_inferred_coverage(self):
        """Custom setup skips/errors retain evidence but cannot account for unstarted leaves."""
        for phase, scope in (('setUpClass', 'fixture.C'), ('setUpModule', 'fixture')):
            for kind in ('skip', 'error'):
                with self.subTest(phase=phase, kind=kind):
                    self.ledger = v.EventLedger(0, 123, self.leaves, [2], ordered=False)
                    self.ledger.accept(self.hello)
                    frame = dict(type='event', seq=0, kind=kind, ordinal=None,
                                 id=f'{phase} ({scope})', phase=phase, scope=scope,
                                 subtest='', detail='original fixture diagnostic')
                    self.ledger.accept(frame)
                    self.ledger.accept(self.end())
                    expected = dict.fromkeys(v.COUNT_NAMES, 0)
                    expected['skipped' if kind == 'skip' else 'errors'] = 1
                    self.assertEqual(self.ledger.counts, expected)
                    self.assertEqual(self.ledger.events, [frame])
                    self.assertEqual(self.ledger.started, [])
                    self.assertEqual(self.ledger.completed, [])
                    self.assertEqual(self.ledger.fixture_dispositions, {})
                    self.assertIsNone(self.ledger.last_setup)
                    self.assertEqual(self.ledger.dispositions(), [
                        dict(ordinal=leaf['ordinal'], id=leaf['id'], kind='not-run', events=[])
                        for leaf in self.leaves])
                    with self.assertRaises(v.ValidationError) as raised:
                        self.ledger.finish()
                    self.assertIn('Unexplained not-run leaves:', str(raised.exception))
                    for leaf in self.leaves:
                        self.assertIn(leaf['id'], str(raised.exception))

    def test_frames(self):
        """Reject truncated/oversized JSON, duplicate keys, non-finite values and extra ends."""
        reader = v.FrameReader(self.ledger)
        raw = json.dumps(self.hello).encode()
        packet = struct.pack('!I', len(raw)) + raw
        for byte in packet:
            reader.feed(bytes([byte]), 10000)
        self.assertEqual(self.ledger.hello, self.hello)
        with self.assertRaises(v.ValidationError):
            reader.finish()
        for data in (struct.pack('!I', 10001), struct.pack('!I', 0),
                     struct.pack('!I', 17) + b'{"a":1,"a":2}    ',
                     struct.pack('!I', 9) + b'{"x":NaN}'):
            reader = v.FrameReader(v.EventLedger(0, 123, self.leaves, [2]))
            with self.assertRaises(v.ValidationError):
                reader.feed(data, 100)
        reader = v.FrameReader(v.EventLedger(0, 123, self.leaves, [2]))
        reader.feed(packet[:-1], 10000)
        with self.assertRaisesRegex(v.ValidationError, 'Truncated'):
            reader.finish()


class InventoryTests(unittest.TestCase):
    """Exercise fail-closed discovery inventories without executing any test bodies."""

    def leaf(self, name='test_body'):
        """Build an ordinary test with a concrete fixture owner and a stable ID."""
        class Example(unittest.TestCase):
            """A tiny ordinary case used only as an inventory object."""
            def test_body(self):
                """Pass when explicitly executed by a separate regression."""
                pass
        return Example(name)

    def plan(self, suite):
        """Plan with an unrelated candidate root so loaded repository helpers are irrelevant."""
        return v.plan_suite(suite, v.Path('/absent-candidate'))

    def test_cycles_duplicates_and_counts(self):
        """Reject repeated objects, equal IDs, cycles and misleading custom counts."""
        first = self.leaf()
        for suite in (unittest.TestSuite([first, first]), unittest.TestSuite([self.leaf(), self.leaf()])):
            with self.assertRaises(v.ValidationError):
                self.plan(suite)
        cycle = unittest.TestSuite()
        cycle.addTest(cycle)
        with self.assertRaisesRegex(v.ValidationError, 'cycle'):
            self.plan(cycle)
        class WrongCount(unittest.TestSuite):
            """Expose a stable list but a false count."""
            def countTestCases(self):
                """Deliberately contradict the actual leaf inventory."""
                return 0
        with self.assertRaisesRegex(v.ValidationError, 'countTestCases'):
            self.plan(WrongCount([first]))

    def test_custom_case_and_function_fallback(self):
        """Custom execution and FunctionTestCase retain intact sequential execution."""
        leaf = self.leaf()
        leaf.run = lambda result: result
        _, _, reasons = self.plan(unittest.TestSuite([leaf]))
        self.assertTrue(any('custom case' in reason for reason in reasons))
        _, _, reasons = self.plan(unittest.TestSuite([unittest.FunctionTestCase(lambda: None)]))
        self.assertTrue(any('custom case' in reason for reason in reasons))

    def test_missing_stop_and_subtest_skip(self):
        """Successful subtest observations do not themselves credit a successful parent."""
        leaves, _, _ = self.plan(unittest.TestSuite([self.leaf()]))
        ledger = v.EventLedger(0, 123, leaves, None)
        ledger.accept(dict(type='hello', version=1, unit=0, pid=123,
                           digest=v.inventory_digest([leaves[0]['id']]), affinity=[]))
        for seq, kind in enumerate(('start', 'subtest_success', 'subtest_skip', 'stop')):
            ledger.accept(dict(type='event', seq=seq, kind=kind, ordinal=0, id=leaves[0]['id'],
                               phase='', scope='', subtest='subtest (value=1)' if kind.startswith('subtest_') else '',
                               detail='reason' if kind == 'subtest_skip' else ''))
        self.assertEqual(ledger.counts['testsRun'], 1)
        self.assertEqual(ledger.counts['successful'], 0)
        self.assertEqual(ledger.counts['skipped'], 1)
