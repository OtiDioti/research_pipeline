"""Real tiny candidate suites exercise automatic scheduling and intact sequential semantics."""

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from tests.validation_fixtures import (
    CandidateFixture, PASSING, four_cpu_sample, wait_for_pid_announcements,
)


class PidReadinessTests(CandidateFixture, unittest.TestCase):
    """Control publication steps deterministically against the real shared observer."""

    def test_incomplete_publication_cannot_release_workers(self):
        """Empty files, numeric prefixes and unframed PIDs cannot advance the controller."""
        paths = [self.parent / name for name in ('0', '1')]
        for path in paths:
            path.write_bytes(b'')
        # A directory entry outside the expected paths has no readiness meaning.
        (self.parent / 'unrelated').write_bytes(b'not a PID\n')
        release = self.parent / 'release'
        stages = [(b'1', b'4'), (b'123', b'456'),
                  (b'123\n', b'456'), (b'123\n', b'456\n')]
        published = []

        def publish_next(interval):
            """Replace polling sleep with one publication step, refusing extra polling."""
            self.assertEqual(interval, 0.01)
            self.assertFalse(release.exists())
            self.assertLess(len(published), len(stages), 'unexpected additional poll')
            stage = stages[len(published)]
            for path, record in zip(paths, stage):
                path.write_bytes(record)
            published.append(stage)

        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch('tests.validation_fixtures.time.sleep', side_effect=publish_next), \
                mock.patch('tests.validation_fixtures.time.monotonic', return_value=0):
            pids = wait_for_pid_announcements(process, paths, deadline=1)
            # Only returning from the actual observer permits this continuation.
            self.assertEqual(published, stages)
            self.assertEqual(pids, [123, 456])
            self.assertFalse(release.exists())
            release.touch()
        self.assertTrue(release.exists())

    def test_unfinished_publication_expires_at_absolute_deadline(self):
        """A missing record and an unframed numeric PID stay pending until expiry."""
        paths = [self.parent / name for name in ('0', '1')]
        paths[0].write_bytes(b'123')
        now = [10]

        def reach_deadline(interval):
            """Advance the controlled clock once instead of sleeping or retrying forever."""
            self.assertEqual(interval, 0.01)
            self.assertEqual(now[0], 10, 'unexpected additional poll')
            now[0] = 11

        def current_time():
            """Expose only the explicitly advanced monotonic test clock."""
            return now[0]

        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch('tests.validation_fixtures.time.sleep', side_effect=reach_deadline), \
                mock.patch('tests.validation_fixtures.time.monotonic', side_effect=current_time):
            with self.assertRaisesRegex(AssertionError, 'PID readiness deadline expired'):
                wait_for_pid_announcements(process, paths, deadline=11)
        self.assertEqual(now[0], 11)

    def test_process_exit_before_readiness_fails(self):
        """Neither a zero nor nonzero exit can excuse an incomplete announcement."""
        path = self.parent / '0'
        path.write_bytes(b'123')
        for status in (0, 23):
            with self.subTest(status=status):
                process = mock.Mock()
                process.poll.side_effect = [None, None, status]
                with mock.patch('tests.validation_fixtures.time.sleep') as sleep, \
                        mock.patch('tests.validation_fixtures.time.monotonic', return_value=0):
                    with self.assertRaisesRegex(AssertionError, f'exited with status {status}'):
                        wait_for_pid_announcements(process, [path], deadline=1)
                    sleep.assert_called_once_with(0.01)

    def test_final_process_and_deadline_checks_prevent_return(self):
        """Complete records still cannot pass after subprocess exit or deadline expiry."""
        path = self.parent / '0'
        path.write_bytes(b'123\n')
        for status, ticks, diagnostic in ((0, [0], 'exited with status 0'),
                                           (None, [0, 1], 'deadline expired')):
            with self.subTest(diagnostic=diagnostic):
                process = mock.Mock()
                process.poll.side_effect = [None, status]
                with mock.patch('tests.validation_fixtures.time.monotonic', side_effect=ticks), \
                        mock.patch('tests.validation_fixtures.time.sleep') as sleep:
                    with self.assertRaisesRegex(AssertionError, diagnostic):
                        wait_for_pid_announcements(process, [path], deadline=1)
                    sleep.assert_not_called()

    def test_malformed_completed_records_fail_with_path(self):
        """Completed nonpositive, non-ASCII or extra-content records fail without retry."""
        path = self.parent / '0'
        process = mock.Mock()
        process.poll.return_value = None
        for record in (b'\n', b'0\n', b'-1\n', b' 12\n', b'12\r\n',
                       b'12\n\n', b'12x\n', '１２\n'.encode(), b'\xff\n'):
            with self.subTest(record=record):
                path.write_bytes(record)
                with mock.patch('tests.validation_fixtures.time.monotonic', return_value=0), \
                        mock.patch('tests.validation_fixtures.time.sleep', side_effect=AssertionError(
                            'unexpected polling after completed record')) as sleep:
                    with self.assertRaisesRegex(AssertionError, 'malformed completed PID') as failure:
                        wait_for_pid_announcements(process, [path], deadline=1)
                    self.assertIn(str(path), str(failure.exception))
                    sleep.assert_not_called()

    def test_read_errors_are_not_pending_publication(self):
        """An existing unreadable-as-a-file path propagates its real filesystem error."""
        path = self.parent / '0'
        path.mkdir()
        process = mock.Mock()
        process.poll.return_value = None
        with self.assertRaises(IsADirectoryError):
            wait_for_pid_announcements(process, [path], deadline=time.monotonic() + 1)


class DiscoveryExecutionTests(CandidateFixture, unittest.TestCase):
    """Compare complete inventories and actual fixture effects across both modes."""

    def test_new_modules_classes_methods(self):
        """Ordinary additions join discovery automatically with identical sequential accounting."""
        for addition in ('', '\nclass More(Example):\n    pass\n',
                         '\nclass More(Example):\n    def test_extra(self):\n        self.assertTrue(True)\n'):
            self.write('test_future.py', PASSING + addition)
            automatic = self.validate()
            sequential = self.validate(sequential=True)
            self.assertEqual(self.inventories(automatic), self.inventories(sequential))
            self.assertEqual(self.dispositions(automatic), self.dispositions(sequential))
        self.assertEqual(len(self.inventories(automatic)['completed']), 4)
        self.assertIn('explicit --sequential', sequential)

    def test_inherited_fixture_owner_and_full_lifecycle(self):
        """Inherited methods use concrete-class module fixtures and exactly-once cleanups."""
        evidence = self.parent / 'calls'
        self.write('helpers.py', f'''import unittest
from pathlib import Path
EVIDENCE = Path({str(evidence)!r})
def note(value):
    """Append an external fixture lifecycle observation."""
    with EVIDENCE.open('a') as stream:
        stream.write(value + '\\n')
class Base(unittest.TestCase):
    """Inherited test methods belong to the concrete subclass's fixture owner."""
    def test_a(self):
        """Exercise an inherited method."""
        note('body-a')
    def test_b(self):
        """Exercise another inherited method."""
        note('body-b')
''')
        self.write('test_example.py', '''import unittest
from tests import helpers

def setUpModule():
    """Register module cleanup and record setup."""
    helpers.note('module-setup')
    unittest.addModuleCleanup(helpers.note, 'module-cleanup')
def tearDownModule():
    """Record module teardown."""
    helpers.note('module-teardown')
class Concrete(helpers.Base):
    """Own the inherited methods' class fixtures."""
    @classmethod
    def setUpClass(cls):
        """Register class cleanup and record setup."""
        helpers.note('class-setup')
        cls.addClassCleanup(helpers.note, 'class-cleanup')
    @classmethod
    def tearDownClass(cls):
        """Record class teardown."""
        helpers.note('class-teardown')
    def setUp(self):
        """Register per-case cleanup."""
        helpers.note('setup')
        self.addCleanup(helpers.note, 'cleanup')
    def tearDown(self):
        """Record per-case teardown."""
        helpers.note('teardown')
''')
        expected = ['module-setup', 'class-setup', 'setup', 'body-a', 'teardown', 'cleanup',
                    'setup', 'body-b', 'teardown', 'cleanup', 'class-teardown', 'class-cleanup',
                    'module-teardown', 'module-cleanup']
        for sequential in (False, True):
            evidence.unlink(missing_ok=True)
            output = self.validate(sequential=sequential)
            self.assertEqual(evidence.read_text().splitlines(), expected)
            self.assertEqual(len(self.inventories(output)['completed']), 2)
            self.assertIn('tests.test_example.Concrete.test_a', output)

    def test_hooks_and_custom_wrapper_intact(self):
        """A load_tests hook and stock-backed wrapper execute exactly once without reconstruction."""
        evidence = self.parent / 'hook'
        self.write('test_example.py', PASSING + f'''
from pathlib import Path
class Wrapper(unittest.TestSuite):
    """Record an effect surrounding intact stock execution."""
    def run(self, result, debug=False):
        """Write external wrapper evidence and delegate."""
        with Path({str(evidence)!r}).open('a') as stream:
            stream.write('wrapper\\n')
        return super().run(result, debug)
def load_tests(loader, tests, pattern):
    """Record discovery exactly once and retain its original objects."""
    with Path({str(evidence)!r}).open('a') as stream:
        stream.write('hook\\n')
    return Wrapper([tests])
''')
        output = self.validate()
        self.assertEqual(evidence.read_text().splitlines(), ['hook', 'wrapper'])
        self.assertIn('discovery hooks', output)
        self.assertIn('custom suite', output)

    def test_opaque_duplicate_and_omitted_inventory(self):
        """Opaque iteration, duplicate IDs and custom early stops cannot pass silently."""
        cases = [
            ('''class Opaque(unittest.TestSuite):
    """Hide stock iteration behind custom behavior."""
    def __iter__(self):
        """Expose an opaque iterator."""
        return iter(self._tests)
def load_tests(loader, tests, pattern):
    """Return an unsupported opaque suite."""
    return Opaque([tests])
''', 'opaque'),
            ('''def load_tests(loader, tests, pattern):
    """Duplicate a test object rather than running it exactly once."""
    return unittest.TestSuite([tests, tests])
''', 'Repeated inventory object'),
            ('''class Stop(unittest.TestSuite):
    """Omit all known leaves during execution."""
    def run(self, result, debug=False):
        """Return without running the discovered test."""
        return result
def load_tests(loader, tests, pattern):
    """Keep a stable but deliberately unexecuted inventory."""
    return Stop([tests])
''', 'not-run')]
        for source, diagnostic in cases:
            self.write('test_example.py', PASSING + source)
            self.assertIn(diagnostic, self.validate(1))

    def test_custom_partial_fixture_skip_cannot_conceal_omission(self):
        """Custom partial traversal cannot infer class/module coverage from a setup skip."""
        skipped = '''import unittest
class Skipped(unittest.TestCase):
    """Expose two leaves whose shared setup prevents any test callbacks."""
    def test_a(self):
        """Fail if the setup skip is lost."""
        self.fail('skipped body ran')
    def test_b(self):
        """Remain inventoried even though the custom runner omits this object."""
        self.fail('omitted body ran')
'''
        hook = '''
class Partial(unittest.TestSuite):
    """Inventory all original objects but execute only a temporary stock subset."""
    def run(self, result, debug=False):
        """Run the passing peer and first skipped leaf, omitting the second leaf."""
        return unittest.TestSuite(self._tests[:2]).run(result, debug)
def load_tests(loader, tests, pattern):
    """Retain discovered object identities without copying or repeating leaves."""
    leaves = [test for group in tests for test in group]
    EXTRA_LEAVES
    return Partial(leaves)
'''
        for scope in ('class', 'module'):
            if scope == 'class':
                source = PASSING + skipped + '''
    @classmethod
    def setUpClass(cls):
        """Suppress both class leaves through one fixture outcome."""
        raise unittest.SkipTest('partial class skip')
'''
                source += hook.replace('EXTRA_LEAVES', '')
                owner = 'tests.test_example'
            else:
                self.write('skipped_owner.py', skipped + '''
def setUpModule():
    """Suppress this module while leaving the other concrete owner successful."""
    raise unittest.SkipTest('partial module skip')
''')
                source = PASSING + '\nfrom tests import skipped_owner\n' + hook.replace(
                    'EXTRA_LEAVES', 'leaves.extend(test for group in loader.loadTestsFromModule(skipped_owner) for test in group)')
                owner = 'tests.skipped_owner'
            self.write('test_example.py', source)
            for sequential in (False, True):
                with self.subTest(scope=scope, sequential=sequential):
                    output = self.validate(1, sequential=sequential)
                    self.assertIn('successful=1 skipped=1', output)
                    self.assertIn('partial ' + scope + ' skip', output)
                    inventories = self.inventories(output)
                    passing_id = 'tests.test_example.Example.test_body'
                    missing = [owner + '.Skipped.test_' + suffix for suffix in ('a', 'b')]
                    self.assertEqual(inventories['discovered'], [passing_id, *missing])
                    for name in ('started', 'completed', 'accounted'):
                        self.assertEqual(inventories[name], [passing_id])
                    self.assertEqual(self.dispositions(output), [
                        dict(ordinal=0, id=passing_id, kind='completed', events=['success']),
                        *[dict(ordinal=index, id=identity, kind='not-run', events=[])
                          for index, identity in enumerate(missing, 1)]])
                    diagnostic = next(line for line in output.splitlines()
                                      if 'Unexplained not-run leaves:' in line)
                    for identity in missing:
                        self.assertIn(identity, diagnostic)
                    events = [json.loads(line[len('Result event: '):]) for line in output.splitlines()
                              if line.startswith('Result event: ')]
                    self.assertEqual([(event['id'], event['kind']) for event in events
                                      if event['ordinal'] is not None],
                                     [(passing_id, kind) for kind in ('start', 'success', 'stop')])
                    fixtures = [json.loads(line[len('Fixture event: '):]) for line in output.splitlines()
                                if line.startswith('Fixture event: ')]
                    self.assertEqual(len(fixtures), 1)
                    self.assertEqual(fixtures[0]['affected_ids'], [])

    def test_serial_declarations(self):
        """Module, package, helper and inherited class declarations serialize the whole suite."""
        self.write('test_peer.py', PASSING)
        variants = [('test_example.py', PASSING + '\nVALIDATION_SERIAL = True\n'),
                    ('helpers.py', 'VALIDATION_SERIAL = True\n'),
                    ('__init__.py', 'VALIDATION_SERIAL = True\n'),
                    ('helpers.py', 'import unittest\nclass Base(unittest.TestCase):\n    VALIDATION_SERIAL = True\n')]
        for name, source in variants:
            self.write('__init__.py', '')
            self.write('helpers.py', '')
            self.write('test_example.py', 'from tests import helpers\n' + PASSING)
            if 'class Base' in source:
                self.write('test_example.py', 'from tests import helpers\n' + PASSING.replace('unittest.TestCase', 'helpers.Base'))
            self.write(name, source)
            output = self.validate()
            self.assertIn('VALIDATION_SERIAL:', output)
            self.assertIn('concurrency=1', output)
        for malformed in ('1', 'None', '"yes"'):
            self.write('helpers.py', 'VALIDATION_SERIAL = ' + malformed)
            self.write('test_example.py', 'from tests import helpers\n' + PASSING)
            self.assertIn('Malformed VALIDATION_SERIAL', self.validate(1))

    def test_fixture_skips_and_errors(self):
        """Explain setup skips/errors and retain cleanup errors without false leaf completion."""
        # A preceding passing owner makes transport sequence numbers differ across
        # modes; fixture disposition references must still compare identically.
        self.write('test_aaa.py', PASSING)
        for scope in ('Module', 'Class'):
            for outcome in ('skip', 'error'):
                raising = "raise unittest.SkipTest('fixture skip')" if outcome == 'skip' else "raise RuntimeError('fixture error')"
                fixture = (f'def setUpModule():\n    {raising}\n' if scope == 'Module' else
                           f'class Blocked(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n        {raising}\n')
                methods = 'def test_a(self):\n    self.fail("never")\ndef test_b(self):\n    self.fail("never")\n'
                if scope == 'Module':
                    source = 'import unittest\n' + fixture + 'class Blocked(unittest.TestCase):\n'
                else:
                    source = 'import unittest\n' + fixture
                source += ''.join('    ' + line + '\n' for line in methods.splitlines())
                self.write('test_example.py', source)
                automatic = self.validate(0 if outcome == 'skip' else 1)
                sequential = self.validate(0 if outcome == 'skip' else 1, sequential=True)
                self.assertEqual(self.inventories(automatic), self.inventories(sequential))
                self.assertEqual(self.dispositions(automatic), self.dispositions(sequential))
                self.assertIn('testsRun=1 successful=1', automatic)
                self.assertIn('fixture-' + ('skipped=2' if outcome == 'skip' else 'blocked=2'), automatic)
                self.assertEqual(len(self.inventories(automatic)['accounted']), 3)
        self.write('test_example.py', '''import unittest
def fail():
    """Raise a cleanup error."""
    raise RuntimeError('cleanup fault')
class Blocked(unittest.TestCase):
    """Keep setup and multiple cleanup diagnostics."""
    @classmethod
    def setUpClass(cls):
        """Register failing cleanups before setup fails."""
        cls.addClassCleanup(fail)
        cls.addClassCleanup(fail)
        raise RuntimeError('setup fault')
    def test_a(self):
        """Never start after failed setup."""
        self.fail('never')
''')
        output = self.validate(1)
        self.assertIn('errors=3', output)
        self.assertIn('setup fault', output)
        self.assertIn('cleanup fault', output)

    def test_result_categories_and_subtests(self):
        """Preserve all unittest result categories and multiple events on a genuine leaf."""
        self.write('test_example.py', PASSING + '''
@unittest.skip('class skip')
class Skipped(unittest.TestCase):
    """A decorated class produces ordinary skipped leaves."""
    def test_skipped(self):
        """Never execute."""
        self.fail('never')
class Outcomes(unittest.TestCase):
    """Exercise each callback category in a tiny suite."""
    @unittest.skip('method skip')
    def test_skip(self):
        """Never execute."""
        self.fail('never')
    @unittest.expectedFailure
    def test_expected(self):
        """Retain expected failure without success credit."""
        self.fail('expected')
    @unittest.expectedFailure
    def test_unexpected(self):
        """Report unexpected success as validation failure."""
        pass
    def test_subtests(self):
        """Preserve parameters and all subtest outcome categories."""
        for value in ('pass', 'fail', 'error', 'skip'):
            with self.subTest(value=value):
                if value == 'fail':
                    self.fail('subtest assertion')
                elif value == 'error':
                    raise RuntimeError('subtest exception')
                elif value == 'skip':
                    self.skipTest('subtest reason')
    def test_errors(self):
        """A body error and two cleanup errors remain three events on one leaf."""
        def fail():
            """Raise a cleanup error."""
            raise RuntimeError('cleanup error')
        self.addCleanup(fail)
        self.addCleanup(fail)
        raise RuntimeError('body error')
''')
        automatic = self.validate(1)
        sequential = self.validate(1, sequential=True)
        self.assertEqual(self.inventories(automatic), self.inventories(sequential))
        self.assertEqual(self.dispositions(automatic), self.dispositions(sequential))
        self.assertIn('successful=1 skipped=3 expected_failures=1 failures=1 errors=4 unexpected_successes=1', automatic)
        self.assertIn("value='fail'", automatic)
        self.assertIn('subtest reason', automatic)

    def test_teardown_and_cleanup_faults(self):
        """Teardown faults preserve completed leaves and retain fixture error events."""
        self.write('test_example.py', PASSING + '''
def tearDownModule():
    """Raise an actual module teardown failure."""
    raise RuntimeError('module teardown')
Example.tearDownClass = classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError('class teardown')))
''')
        output = self.validate(1)
        self.assertIn('testsRun=1 successful=1', output)
        self.assertIn('errors=2', output)
        self.assertEqual(self.inventories(output)['completed'], self.inventories(output)['accounted'])

    def test_repeated_owner_layout(self):
        """Recurrent module ownership retains original order instead of regrouping fixtures."""
        self.write('owner_a.py', PASSING)
        self.write('owner_b.py', PASSING)
        self.write('test_example.py', '''import unittest
from tests import owner_a, owner_b
def load_tests(loader, tests, pattern):
    """Supply repeated concrete owner layout with distinct leaf IDs."""
    class Last(owner_a.Example):
        """Another concrete class owned by module A."""
        pass
    Last.__module__ = owner_a.__name__
    return unittest.TestSuite([owner_a.Example('test_body'), owner_b.Example('test_body'), Last('test_body')])
''')
        output = self.validate()
        self.assertIn('repeated fixture owner', output)
        ids = self.inventories(output)
        self.assertEqual(ids['discovered'], ids['completed'])
        self.assertEqual(len(ids['completed']), 3)

    def test_affinity_unavailable_and_forbidden_options(self):
        """Unavailable affinity selects one intact child while CLI abbreviations remain rejected."""
        self.write('test_peer.py', PASSING)
        output = self.validate(prelude='''
def sample():
    """Model absent affinity without changing host settings."""
    return dict(A=8, allowed=None, bounds=[], limitations=['affinity unavailable'], observations=[])
v.sample_resources = sample
''')
        self.assertIn('C=1 concurrency=1 mask=None', output)
        self.assertIn('affinity unavailable', output)
        for option in ('--seq', '--root', '--skip-tests'):
            command, environment = self.command()
            result = subprocess.run([*command, option], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')

    def test_custom_execution_order_and_missing_stop(self):
        """Retain a supported wrapper's order separately and reject fabricated incomplete execution."""
        self.write('test_example.py', PASSING + '''
class Other(Example):
    """A second discovered concrete case."""
    pass
class Reverse(unittest.TestSuite):
    """Keep a stable stock inventory but deliberately execute its children in reverse."""
    def run(self, result, debug=False):
        """Execute known objects in the wrapper's chosen order."""
        for child in reversed(self._tests):
            child(result)
        return result
def load_tests(loader, tests, pattern):
    """Return an intact supported custom wrapper."""
    return Reverse(list(tests))
''')
        output = self.validate()
        inventories = self.inventories(output)
        self.assertEqual(inventories['discovered'], inventories['completed'])
        execution = next(json.loads(line[len('Execution order: '):]) for line in output.splitlines()
                         if line.startswith('Execution order: '))
        self.assertEqual(execution['completed'], list(reversed(inventories['discovered'])))
        self.write('test_example.py', PASSING + '''
def incomplete(self, result):
    """Deliberately omit a stop callback despite reporting success."""
    result.startTest(self)
    result.addSuccess(self)
Example.run = incomplete
''')
        self.assertIn('missing stopTest', self.validate(1))

    def test_case_setup_teardown_and_module_cleanup(self):
        """Multiple case/fixture faults retain genuine callback counts and missing-leaf reasons."""
        self.write('test_example.py', PASSING + '''
def fail():
    """Raise a per-case cleanup fault."""
    raise RuntimeError('case cleanup')
def setup(self):
    """A setup skip still executes registered case cleanups."""
    self.addCleanup(fail)
    self.skipTest('case setup skip')
Example.setUp = setup
''')
        output = self.validate(1)
        self.assertIn('testsRun=1 successful=0 skipped=1', output)
        self.assertIn('errors=1', output)
        self.assertEqual(self.inventories(output)['discovered'], self.inventories(output)['completed'])
        self.write('test_peer.py', PASSING)
        self.write('test_example.py', PASSING + '''
def cleanup():
    """Retain a module cleanup error after failed setup."""
    raise RuntimeError('module cleanup')
def setUpModule():
    """Fail module setup after registering a real cleanup."""
    unittest.addModuleCleanup(cleanup)
    raise RuntimeError('module setup')
''')
        output = self.validate(1)
        self.assertIn('errors=2', output)
        self.assertIn('fixture-blocked=1', output)
        self.assertIn('testsRun=1 successful=1', output)



class ConcurrencyTests(CandidateFixture, unittest.TestCase):
    """Use explicit IPC gates to demonstrate overlap, exclusion and deterministic reporting."""

    def test_real_overlap_isolation_and_reordered_completion(self):
        """Two ready children coexist, isolate mutable resources and report in discovery order."""
        fifo = self.parent / 'ready'
        os.mkfifo(fifo, 0o600)
        ready_fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, ready_fd)
        parent_mask = sorted(os.sched_getaffinity(0))
        for index, module in enumerate(('test_example.py', 'test_peer.py')):
            self.write(module, f'''import os, socket, sqlite3, subprocess, sys, tempfile, time, unittest
from pathlib import Path
GLOBAL = []
class Isolated(unittest.TestCase):
    """Use private real SQLite/socket/global resources while held at an external gate."""
    def test_body(self):
        """Announce readiness after creating isolated resources, then await the controller."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(GLOBAL, [])
            GLOBAL.append({index})
            connection = sqlite3.connect(root / 'store.db')
            self.addCleanup(connection.close)
            connection.execute('create table evidence (value integer)')
            connection.execute('insert into evidence values (?)', ({index},))
            previous = os.getcwd()
            try:
                os.chdir(root)
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind('same.sock')
                    inherited = subprocess.check_output([sys.executable, '-B', '-c',
                        'import os; print(sorted(os.sched_getaffinity(0)))'], text=True).strip()
                    self.assertEqual(inherited, str(sorted(os.sched_getaffinity(0))))
                    self.assertEqual(os.getpgrp(), {os.getpgrp()})
                    with open({str(fifo)!r}, 'w') as stream:
                        stream.write(str({index}) + ':' + temporary + ':' + str(os.getpid()) + '\\n')
                        stream.flush()
                    deadline = time.monotonic() + 10
                    while not Path({str(self.parent / ('release-' + str(index)))!r}).exists():
                        if time.monotonic() > deadline:
                            self.fail('external overlap controller did not release gate')
                        time.sleep(0.01)
                    self.assertEqual(connection.execute('select value from evidence').fetchone(), ({index},))
                    print('BODY-{index}')
            finally:
                os.chdir(previous)
''')
        for first in (1, 0):
            for index in (0, 1):
                (self.parent / f'release-{index}').unlink(missing_ok=True)
            before = self.snapshot()
            command, environment = self.command(prelude=four_cpu_sample())
            process = subprocess.Popen(command, env=environment, cwd=self.parent,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                data = b''
                with selectors.DefaultSelector() as selector:
                    selector.register(ready_fd, selectors.EVENT_READ)
                    deadline = time.monotonic() + 10
                    while data.count(b'\n') < 2:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            process.terminate() if process.poll() is None else None
                            stdout, stderr = process.communicate(timeout=12)
                            self.fail('both workers must reach the gate: ' + stdout + stderr)
                        for _, _ in selector.select(0.1):
                            data += os.read(ready_fd, 65536)
                rows = [line.split(':') for line in data.decode().splitlines()]
                self.assertEqual({row[0] for row in rows}, {'0', '1'})
                self.assertEqual(len({row[1] for row in rows}), 2)
                self.assertEqual(len({row[2] for row in rows}), 2)
                # Both announcements happened while neither release existed: this
                # proves overlap without a performance or elapsed-speed assertion.
                (self.parent / f'release-{first}').touch()
                other = 1 - first
                # Wait for the first worker to exit, forcing opposite completion orders.
                pid = int(next(row[2] for row in rows if row[0] == str(first)))
                while Path(f'/proc/{pid}').exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f'/proc/{pid}').exists())
                (self.parent / f'release-{other}').touch()
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stdout + stderr)
                self.assertLess(stdout.index('BODY-0'), stdout.index('BODY-1'))
                self.assertEqual(self.inventories(stdout)['discovered'], self.inventories(stdout)['completed'])
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(sorted(os.sched_getaffinity(0)), parent_mask)
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=10)

    def test_serial_metadata_excludes_all_peers(self):
        """An exceptional declaration gives the entire suite one exclusive process."""
        lock = self.parent / 'lock'
        evidence = self.parent / 'serial'
        source = f'''import os, unittest
from pathlib import Path
class Exclusive(unittest.TestCase):
    """A real exclusive-create resource must never conflict with an ordinary peer."""
    def test_body(self):
        """Hold a shared external resource and record worker identity."""
        descriptor = os.open({str(lock)!r}, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with Path({str(evidence)!r}).open('a') as stream:
                stream.write(str(os.getpid()) + '\\n')
        finally:
            os.close(descriptor)
            os.unlink({str(lock)!r})
'''
        self.write('test_example.py', 'VALIDATION_SERIAL = True\n' + source)
        self.write('test_peer.py', source)
        output = self.validate()
        self.assertEqual(len(set(evidence.read_text().splitlines())), 1)
        self.assertIn('concurrency=1', output)

    def test_wave_drain_recomputes_remaining_resources(self):
        """A complete four-unit wave drains before a changed sample admits the one-unit tail."""
        evidence = self.parent / 'waves'
        evidence.mkdir()
        for index in range(5):
            name = 'test_example.py' if index == 0 else f'test_wave_{index}.py'
            self.write(name, f'''import os, unittest
from pathlib import Path
class Example(unittest.TestCase):
    """Record unit completion externally."""
    def test_body(self):
        """Expose actual worker identity to the next wave's sample."""
        Path({str(evidence / str(index))!r}).write_text(str(os.getpid()))
''')
        prelude = four_cpu_sample() + f'''
samples = 0
def changing_sample():
    """Require prior workers gone before reducing available CPUs for the tail."""
    global samples
    samples += 1
    if samples > 1:
        files = list(v.Path({str(evidence)!r}).iterdir())
        assert len(files) == 4, files
        assert all(not v.Path('/proc', path.read_text()).exists() for path in files)
    return dict(A=4 if samples == 1 else 2, allowed=actual, bounds=[], limitations=[], observations=[])
v.sample_resources = changing_sample
'''
        output = self.validate(prelude=prelude)
        self.assertIn('Wave 1: A=4 T=5 C=2 concurrency=4', output)
        self.assertIn('Wave 2: A=2 T=1 C=0 concurrency=1', output)
        self.assertEqual(len(self.inventories(output)['completed']), 5)

    def write_gated_workers(self, fault=None):
        """Build two bounded external-gate workers and return their observation paths.

        The explicit test-only faults leave worker zero's announcement unfinished;
        crash additionally starts an inherited descendant and awaits a control gate.
        Complete setup acknowledgements certify written cleanup evidence and fault
        setup only: they never grant permission to release either worker.
        """
        ready = self.parent / 'announcements'
        ready.mkdir()
        release = self.parent / 'release'
        setup = self.parent / 'setup'
        setup.mkdir()
        evidence = [self.parent / f'worker-{index}.json' for index in (0, 1)]
        crash = self.parent / 'crash'
        for index, name in enumerate(('test_example.py', 'test_peer.py')):
            unfinished = index == 0 and fault in ('unfinished', 'crash')
            crashing = index == 0 and fault == 'crash'
            ending = '' if unfinished else '\n'
            self.write(name, f'''import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
class Gated(unittest.TestCase):
    """Wait for an external controller after announcing a live worker."""
    def test_body(self):
        """Publish cleanup/setup records, then await release boundedly or crash on control."""
        descendant = None
        if {crashing!r}:
            descendant = subprocess.Popen([sys.executable, '-B', '-c',
                                           'import time; time.sleep(60)'])
        # Only a newline completes readiness; the fault deliberately omits it.
        Path({str(ready / str(index))!r}).write_text(str(os.getpid()) + {ending!r})
        Path({str(evidence[index])!r}).write_text(json.dumps(dict(
            pid=os.getpid(), temporary=tempfile.gettempdir(),
            descendant=descendant.pid if descendant is not None else None)))
        # Setup acknowledgement certifies prior evidence writes, never release.
        Path({str(setup / str(index))!r}).write_text(str(os.getpid()) + '\\n')
        deadline = time.monotonic() + 10
        while not Path({str(release)!r}).exists():
            if {crashing!r} and Path({str(crash)!r}).exists():
                os._exit(31)
            if time.monotonic() > deadline:
                self.fail('external gate was not released')
            time.sleep(0.01)
''')
        return ([ready / str(index) for index in (0, 1)], release,
                [setup / str(index) for index in (0, 1)], evidence, crash)

    def finish_gated_validator(self, process, before, evidence):
        """Reap within twelve seconds, retain failure diagnostics and verify owned cleanup.

        Unfinished validators receive SIGTERM so their existing Invocation.cleanup
        owns descendant termination and directory removal. Evidence is read only
        after subprocess termination; streams close even when cleanup fails.
        """
        active_error = sys.exc_info()[1]
        try:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=12)
            output = stdout + stderr
            if active_error is not None:
                active_error.add_note(output)
            self.assertEqual(self.snapshot(), before, 'validator mutated candidate source')
            for path in evidence:
                record = json.loads(path.read_text())
                for pid in (record['pid'], record['descendant']):
                    if pid is not None:
                        self.assertFalse(Path('/proc', str(pid)).exists(), (record, output))
                self.assertFalse(Path(record['temporary']).exists(), (record, output))
            return output
        finally:
            process.stdout.close()
            process.stderr.close()

    def test_pipe_gated_overlap(self):
        """Prove two live, nondead workers await complete PID readiness without sockets."""
        paths, release, _, evidence, _ = self.write_gated_workers()
        before = self.snapshot()
        command, environment = self.command(prelude=four_cpu_sample())
        process = subprocess.Popen(command, env=environment, cwd=self.parent,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            pids = wait_for_pid_announcements(process, paths, deadline=time.monotonic() + 10)
            self.assertEqual(len(set(pids)), 2)
            self.assertTrue(all(Path('/proc', str(pid)).exists() for pid in pids))
            for pid in pids:
                status = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[0]
                self.assertNotIn(status, ('Z', 'X', 'x'))
            # Both bodies require this external gate, which has not been opened.
            self.assertFalse(release.exists())
            release.touch()
            stdout, stderr = process.communicate(timeout=12)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            inventories = self.inventories(stdout)
            self.assertEqual(inventories['discovered'], inventories['completed'])
            expected = ['tests.test_example.Gated.test_body', 'tests.test_peer.Gated.test_body']
            for name, inventory in inventories.items():
                self.assertEqual(inventory, expected, name)
        finally:
            self.finish_gated_validator(process, before, evidence)

    def assert_gated_readiness_failure(self, fault):
        """Exercise a real unfinished/crashing worker, asserting failure and complete cleanup."""
        paths, release, setup, evidence, crash = self.write_gated_workers(fault)
        before = self.snapshot()
        command, environment = self.command(prelude=four_cpu_sample())
        process = subprocess.Popen(command, env=environment, cwd=self.parent,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            pids = wait_for_pid_announcements(process, setup, deadline=time.monotonic() + 10)
            self.assertEqual(len(set(pids)), 2)
            # Complete control acknowledgements establish that these records and
            # the deliberately unfinished announcement have already been written.
            records = [json.loads(path.read_text()) for path in evidence]
            self.assertEqual([record['pid'] for record in records], pids)
            self.assertTrue(all(Path('/proc', str(pid)).exists() for pid in pids))
            self.assertEqual(paths[0].read_bytes(), str(pids[0]).encode('ascii'))
            self.assertFalse(release.exists())
            if fault == 'crash':
                self.assertIsNotNone(records[0]['descendant'])
                self.assertTrue(Path('/proc', str(records[0]['descendant'])).exists())
                crash.touch()
                diagnostic = 'validator exited with status'
                deadline = time.monotonic() + 10
            else:
                diagnostic = 'PID readiness deadline expired'
                # Start this short bound only after both setup acknowledgements.
                deadline = time.monotonic() + 0.15
            with self.assertRaisesRegex(AssertionError, diagnostic):
                wait_for_pid_announcements(process, paths, deadline=deadline)
            self.assertFalse(release.exists())
        finally:
            output = self.finish_gated_validator(process, before, evidence)
        self.assertNotEqual(process.returncode, 0, output)
        self.assertFalse(release.exists())
        self.assertIn('successful=0', output)
        self.assertEqual(self.inventories(output)['completed'], [])
        self.assertTrue(all('success' not in item['events'] for item in self.dispositions(output)), output)
        self.assertIn('exited abnormally' if fault == 'crash' else 'SIGTERM', output)

    def test_unfinished_pid_publication_cleanup(self):
        """Never completing a PID record fails readiness and cleans both held workers."""
        self.assert_gated_readiness_failure('unfinished')

    def test_crash_during_pid_publication_cleanup(self):
        """A controlled crash before PID completion cleans its descendant and held peer."""
        self.assert_gated_readiness_failure('crash')
