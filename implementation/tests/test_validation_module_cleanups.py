"""Compare shared module-cleanup transitions with stock unittest in fresh candidates."""

import json
import os
import selectors
import subprocess
import sys
import time
import unittest

from tests.validation_fixtures import CandidateFixture, PASSING, four_cpu_sample


PENDING = 'pending process-global unittest module cleanups'
UNKNOWN = 'unavailable or unrecognized unittest module cleanup state'
IDS = ['tests.test_example.Example.test_body', 'tests.test_peer.Example.test_body']

# This oracle observes stock callbacks only; fixture execution and exception
# selection belong entirely to unittest, independently of validator accounting.
STOCK_ORACLE = '''import io, json, os, sys, unittest
from pathlib import Path
root = Path(sys.argv[1])
os.environ['CLEANUP_TRACE'] = sys.argv[2]
sys.path[:0] = [str(root / 'implementation/src'), str(root / 'implementation')]
class ObservedResult(unittest.TextTestResult):
    """Record genuine stock callbacks and details without replacing fixture execution."""
    def __init__(self, *args, **kwargs):
        """Initialize a separate observation ledger beside ordinary result counters."""
        super().__init__(*args, **kwargs)
        self.events = []
        self.successes = []
    def startTest(self, test):
        """Observe a real start after delegating stock testsRun accounting."""
        super().startTest(test)
        self.events.append(dict(id=test.id(), kind='start', detail=''))
    def stopTest(self, test):
        """Observe a genuine stop, never synthesizing fixture completions."""
        super().stopTest(test)
        self.events.append(dict(id=test.id(), kind='stop', detail=''))
    def addSuccess(self, test):
        """Credit only actual successful leaves."""
        super().addSuccess(test)
        self.successes.append(test.id())
        self.events.append(dict(id=test.id(), kind='success', detail=''))
    def addError(self, test, err):
        """Retain stock-selected fixture exceptions and their complete tracebacks."""
        super().addError(test, err)
        self.events.append(dict(id=test.id(), kind='error', detail=self.errors[-1][1]))
    def addSkip(self, test, reason):
        """Retain stock fixture skips without inventing leaf callbacks."""
        super().addSkip(test, reason)
        self.events.append(dict(id=test.id(), kind='skip', detail=reason))
def identities(suite):
    """Read ordinary stock tree IDs before the runner consumes the original suite."""
    for node in suite:
        if isinstance(node, unittest.TestSuite):
            yield from identities(node)
        else:
            yield node.id()
loader = unittest.TestLoader()
suite = loader.discover(str(root / 'implementation/tests'), pattern='test_*.py',
                        top_level_dir=str(root / 'implementation'))
ids = list(identities(suite))
result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=ObservedResult).run(suite)
summary = dict(ids=ids, events=result.events, successful_ids=result.successes,
               ok=result.wasSuccessful(), discovery_errors=loader.errors,
               counts=dict(discovered=len(ids), testsRun=result.testsRun,
                           successful=len(result.successes), skipped=len(result.skipped),
                           expected_failures=len(result.expectedFailures), failures=len(result.failures),
                           errors=len(result.errors), unexpected_successes=len(result.unexpectedSuccesses)))
print('Stock summary: ' + json.dumps(summary, sort_keys=True))
'''


class ModuleCleanupTests(CandidateFixture, unittest.TestCase):
    """Keep cleanup registrations in disposable modules and compare three fresh processes."""

    def install_modules(self, *, setup='', cleanup_example='', cleanup_peer='', hook=False,
                        teardown=''):
        """Write two ordinary owners and external tracing helpers for one cleanup scenario.

        Optional statements raise from the first setup/teardown or either cleanup;
        a hook variant registers the first callback during discovery instead of import.
        """
        self.write('helpers.py', '''import os

def note(value):
    """Append a transition to the private external trace selected by this process."""
    with open(os.environ['CLEANUP_TRACE'], 'a') as stream:
        stream.write(value + '\\n')
''')
        for label, cleanup in (('example', cleanup_example), ('peer', cleanup_peer)):
            source = f'''import unittest
from tests.helpers import note
note('import-{label}')
def cleanup():
    """Log once before an optional cleanup exception chosen by the scenario."""
    note('cleanup-{label}')
    {cleanup or 'pass'}
def setUpModule():
    """Record stock setup and optionally suppress this owner's leaf."""
    note('setup-{label}')
    {setup if label == 'example' and setup else 'pass'}
def tearDownModule():
    """Record stock teardown before any optional fixture failure."""
    note('teardown-{label}')
    {teardown if label == 'example' and teardown else 'pass'}
'''
            source += PASSING.replace('self.assertEqual(2 + 2, 4)',
                                      f"note('body-{label}')\n        self.assertEqual(2 + 2, 4)")
            if hook and label == 'example':
                source += '''
def load_tests(loader, tests, pattern):
    """Register once during stock discovery and return its exact original suite."""
    note('hook-example')
    unittest.addModuleCleanup(cleanup)
    return tests
'''
            else:
                source += '\nunittest.addModuleCleanup(cleanup)\n'
            self.write('test_' + label + '.py', source)

    def trace_path(self, name):
        """Create a fresh owner-private trace outside candidate source, failing on reuse."""
        path = self.parent / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        return path

    def stock(self, trace):
        """Run one standard discovery/traversal and collect expected failures as data."""
        before = self.snapshot()
        _, environment = self.command()
        process = subprocess.run([sys.executable, '-B', '-c', STOCK_ORACLE,
                                  str(self.root), str(trace)], cwd=self.parent, env=environment,
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(self.snapshot(), before)
        summaries = [json.loads(line[len('Stock summary: '):]) for line in process.stdout.splitlines()
                     if line.startswith('Stock summary: ')]
        self.assertEqual(len(summaries), 1, process.stdout)
        self.assertEqual(summaries[0]['discovery_errors'], [])
        return summaries[0]

    def result_events(self, output):
        """Read genuine result callbacks without relying on consolidated count totals."""
        return [json.loads(line[len('Result event: '):]) for line in output.splitlines()
                if line.startswith('Result event: ')]

    def normalized_events(self, events):
        """Compare callback identities/categories and selected exceptions across runner frames."""
        return [(event['id'], event['kind'], event['detail'].strip().splitlines()[-1]
                 if event['detail'] else '') for event in events]

    def assert_exclusive(self, output, reason=PENDING):
        """Require exactly one intact execution worker with the conservative unit budget."""
        waves = [line for line in output.splitlines() if line.startswith('Wave ')]
        self.assertEqual(len(waves), 1, output)
        self.assertIn('Wave 1: A=4 T=1 C=0 concurrency=1 mask=None', waves[0])
        self.assertIn(reason, waves[0])
        measurements = [line for line in output.splitlines() if line.startswith('Unit measurement: ')]
        self.assertEqual(len(measurements), 1, output)

    def compare(self, name, expected_trace, *, executed=IDS, disposition='completed', hook=False):
        """Compare stock, explicit sequential and automatic observations on fresh evidence.

        Assert counts, fixture details, every inventory and real callbacks separately;
        failing fixture scenarios remain data until their expected outcomes are checked.
        """
        stock_trace = self.trace_path(name + '-stock')
        oracle = self.stock(stock_trace)
        self.assertEqual(stock_trace.read_text().splitlines(), expected_trace)
        self.assertEqual(oracle['ids'], IDS)
        self.assertEqual(oracle['successful_ids'], executed)
        outputs = []
        for mode, sequential in (('sequential', True), ('automatic', False)):
            trace = self.trace_path(name + '-' + mode)
            prelude = four_cpu_sample() + f"\nv.os.environ['CLEANUP_TRACE'] = {str(trace)!r}\n"
            # Verify object identity at the existing worker boundary without
            # replacing planning, accounting, fixture execution or transport.
            prelude += '''
original_plan = v.plan_suite
original_launch = v.launch_worker
def observe_plan(suite, *args, **kwargs):
    """Remember the original discovered object while delegating all planning."""
    global discovered_suite
    discovered_suite = suite
    return original_plan(suite, *args, **kwargs)
def observe_launch(invocation, root, suite, *args, **kwargs):
    """Require the exact discovered object at exclusive admission."""
    if suite is not discovered_suite:
        raise AssertionError('exclusive worker reconstructed the discovered suite')
    return original_launch(invocation, root, suite, *args, **kwargs)
v.plan_suite = observe_plan
v.launch_worker = observe_launch
'''
            output = self.validate(0 if oracle['ok'] else 1, sequential=sequential, prelude=prelude)
            outputs.append(output)
            self.assertEqual(trace.read_text().splitlines(), expected_trace)
            self.assert_exclusive(output)
            if sequential:
                self.assertIn('explicit --sequential', output)
            if hook:
                self.assertIn('discovery hooks: tests.test_example', output)
            counts = [line for line in output.splitlines() if line.startswith('Counts: ')]
            self.assertEqual(len(counts), 1, output)
            self.assertEqual(dict((key, int(value)) for key, value in
                                  (field.split('=') for field in counts[0][len('Counts: '):].split())),
                             oracle['counts'])
            self.assertEqual(self.inventories(output), dict(discovered=IDS, started=executed,
                                                          completed=executed, accounted=IDS))
            events = self.result_events(output)
            self.assertEqual(self.normalized_events(events), self.normalized_events(oracle['events']))
            leaves = [event for event in events if event['ordinal'] is not None]
            self.assertEqual([(event['id'], event['kind']) for event in leaves],
                             [(identity, kind) for identity in executed
                              for kind in ('start', 'success', 'stop')])
            dispositions = self.dispositions(output)
            self.assertEqual([item['id'] for item in dispositions], IDS)
            self.assertEqual([item['kind'] for item in dispositions],
                             ['completed' if identity in executed else disposition for identity in IDS])
            fixtures = [event for event in events if event['ordinal'] is None]
            self.assertEqual(self.normalized_events(fixtures), self.normalized_events(
                [event for event in oracle['events'] if event['id'] not in IDS]))
            for event in fixtures:
                if event['kind'] == 'error':
                    self.assertIn('Traceback (most recent call last):', event['detail'])
                    self.assertIn('test_example.py' if event['detail'].strip().endswith(
                        ('setup error', 'teardown failure')) else 'test_peer.py', event['detail'])
        self.assertEqual(self.dispositions(outputs[0]), self.dispositions(outputs[1]))
        return oracle

    def passing_trace(self, hook=False):
        """Return the concrete cross-module LIFO sequence, including optional discovery hook."""
        return (['import-example'] + (['hook-example'] if hook else []) +
                ['import-peer', 'setup-example', 'body-example', 'teardown-example',
                 'cleanup-peer', 'cleanup-example', 'setup-peer', 'body-peer', 'teardown-peer'])

    def test_import_cleanups_exact_once_and_repeated_fresh_processes(self):
        """Later-imported cleanup runs first at earlier teardown in every fresh mode."""
        self.install_modules()
        for repetition in range(2):
            oracle = self.compare('passing-' + str(repetition), self.passing_trace())
            self.assertTrue(oracle['ok'])
            self.assertEqual(oracle['counts']['successful'], 2)

    def test_multiple_cleanup_errors_drain_and_select_first(self):
        """Both failing callbacks run once but stock reports only the first LIFO exception."""
        self.install_modules(cleanup_example="raise ValueError('earlier cleanup failure')",
                             cleanup_peer="raise RuntimeError('selected cleanup failure')")
        oracle = self.compare('errors', self.passing_trace())
        self.assertFalse(oracle['ok'])
        self.assertEqual(oracle['counts']['successful'], 2)
        self.assertEqual(oracle['counts']['errors'], 1)
        errors = [event for event in oracle['events'] if event['kind'] == 'error']
        self.assertEqual(self.normalized_events(errors),
                         [('tearDownModule (tests.test_example)', 'error',
                           'RuntimeError: selected cleanup failure')])

    def test_failed_setup_drains_pending_stack_with_stock_dispositions(self):
        """Setup skip/error and cleanup faults preserve suppressed leaves and error dominance."""
        for name, setup, cleanup, disposition, categories in (
                ('skip', "raise unittest.SkipTest('setup skip')", '', 'fixture-skipped', ['skip']),
                ('error', "raise RuntimeError('setup error')", '', 'fixture-blocked', ['error']),
                ('skip-cleanup-error', "raise unittest.SkipTest('setup skip')",
                 "raise RuntimeError('selected cleanup failure')", 'fixture-blocked', ['skip', 'error'])):
            with self.subTest(name=name):
                self.install_modules(setup=setup, cleanup_peer=cleanup)
                trace = ['import-example', 'import-peer', 'setup-example', 'cleanup-peer',
                         'cleanup-example', 'setup-peer', 'body-peer', 'teardown-peer']
                oracle = self.compare(name, trace, executed=IDS[1:], disposition=disposition)
                fixtures = [event for event in oracle['events'] if event['id'] not in IDS]
                self.assertEqual([event['kind'] for event in fixtures], categories)
                self.assertEqual([event['id'] for event in fixtures],
                                 ['setUpModule (tests.test_example)'] * len(categories))
                self.assertEqual(oracle['ok'], name == 'skip')

    def test_cleanup_skip_preserves_mixed_success(self):
        """A cleanup SkipTest retains both genuine successes and the stock fixture skip."""
        self.install_modules(cleanup_peer="raise unittest.SkipTest('cleanup skip')")
        oracle = self.compare('cleanup-skip', self.passing_trace())
        self.assertTrue(oracle['ok'])
        self.assertEqual(oracle['counts']['skipped'], 1)
        self.assertIn(('tearDownModule (tests.test_example)', 'skip', 'cleanup skip'),
                      self.normalized_events(oracle['events']))

    def test_teardown_error_still_drains_stack(self):
        """A teardown exception cannot suppress pending cleanups or erase completed leaves."""
        self.install_modules(teardown="raise RuntimeError('teardown failure')")
        oracle = self.compare('teardown-error', self.passing_trace())
        self.assertFalse(oracle['ok'])
        self.assertEqual(oracle['counts']['errors'], 1)
        self.assertEqual(oracle['counts']['successful'], 2)

    def test_discovery_hook_registration_observed_after_discovery(self):
        """One hook registers on the live stack and keeps both independent fallback reasons."""
        self.install_modules(hook=True)
        self.compare('hook', self.passing_trace(hook=True), hook=True)

    def test_predicate_exact_list_contract_and_live_state(self):
        """Unknown representations are conservative without calling their truth or iteration."""
        program = '''import importlib.util, sys, types, unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('predicate_validator', sys.argv[1])
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
truth_calls = []
class FalseUnknown:
    """Represent unsupported false-valued state with observable truth/iteration calls."""
    def __bool__(self):
        """Expose false-valued state while recording any forbidden truth conversion."""
        truth_calls.append('unknown')
        return False
    def __iter__(self):
        """Fail if introspection attempts iteration."""
        raise AssertionError('unknown iteration invoked')
class FalseList(list):
    """Expose an empty list subclass whose methods must not be consulted."""
    def __bool__(self):
        """Record if list subclasses are incorrectly treated as recognized state."""
        truth_calls.append('subclass')
        return False
    def __iter__(self):
        """Fail if a subclass is traversed."""
        raise AssertionError('subclass iteration invoked')
original = unittest.case._module_cleanups
with patch.object(unittest.case, '_module_cleanups', []):
    assert v._module_cleanup_fallback_reason() is None
    unittest.case._module_cleanups.append(object())
    assert v._module_cleanup_fallback_reason() == 'pending process-global unittest module cleanups'
    unittest.case._module_cleanups.pop()
    assert v._module_cleanup_fallback_reason() is None
for value in (None, (), FalseUnknown(), FalseList(), FalseList([object()])):
    with patch.object(unittest.case, '_module_cleanups', value):
        assert v._module_cleanup_fallback_reason().startswith(
            'unavailable or unrecognized unittest module cleanup state')
assert truth_calls == []
with patch.object(unittest.case, '_module_cleanups', []):
    del unittest.case._module_cleanups
    assert v._module_cleanup_fallback_reason().startswith(
        'unavailable or unrecognized unittest module cleanup state')
with patch.object(sys, 'implementation', types.SimpleNamespace(name='unsupported')):
    assert v._module_cleanup_fallback_reason().startswith(
        'unavailable or unrecognized unittest module cleanup state')
class InterruptedState:
    """Raise lifecycle exceptions on access rather than disguising them as unknown state."""
    def __getattr__(self, name):
        """Propagate the exception selected by the isolated test."""
        raise failure
for failure in (KeyboardInterrupt(), v.ValidationError('invocation deadline exceeded')):
    with patch.object(unittest, 'case', InterruptedState()):
        try:
            v._module_cleanup_fallback_reason()
        except BaseException as error:
            assert error is failure
        else:
            raise AssertionError('lifecycle exception swallowed')
assert unittest.case._module_cleanups is original
print('predicate cases passed')
'''
        before = self.snapshot()
        _, environment = self.command()
        result = subprocess.run([sys.executable, '-B', '-c', program, str(self.script)],
                                cwd=self.parent, env=environment, capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('predicate cases passed', result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_pending_cleanup_does_not_bypass_inventory_errors(self):
        """A pending stack cannot excuse a hook that duplicates discovered objects."""
        self.install_modules()
        self.write('test_example.py', (self.tests / 'test_example.py').read_text() + '''
def load_tests(loader, tests, pattern):
    """Deliberately duplicate the same stock objects to exercise inventory rejection."""
    return unittest.TestSuite([tests, tests])
''')
        for sequential in (False, True):
            trace = self.trace_path('invalid-inventory-' + str(sequential))
            output = self.validate(1, sequential=sequential, prelude=four_cpu_sample() +
                                   f"\nv.os.environ['CLEANUP_TRACE'] = {str(trace)!r}\n")
            self.assertIn('Repeated inventory object occurrence', output)
            self.assertNotIn('Wave ', output)
            self.assertEqual(trace.read_text().splitlines(), ['import-example', 'import-peer'])

    def test_empty_discovery_with_pending_cleanup_creates_no_worker(self):
        """Empty discovery fails coverage without draining pending callbacks speculatively."""
        evidence = self.parent / 'unexpected-cleanup'
        self.write('test_example.py', f'''import unittest
from pathlib import Path
def cleanup():
    """Leave evidence only if a callback executes without any discovered test."""
    Path({str(evidence)!r}).write_text('unexpected cleanup')
unittest.addModuleCleanup(cleanup)
''')
        for sequential in (False, True):
            output = self.validate(1, sequential=sequential, prelude=four_cpu_sample())
            self.assertIn('discovered=0 testsRun=0 successful=0', output)
            self.assertNotIn('Wave ', output)
            self.assertNotIn('Unit measurement: ', output)
            self.assertFalse(evidence.exists())
            self.assertEqual(self.inventories(output), dict.fromkeys(
                ('discovered', 'started', 'completed', 'accounted'), []))

    def test_unknown_state_fallback_with_healthy_stock_fixtures(self):
        """An injected limitation serializes healthy stock state without corrupting fixtures."""
        self.write('test_peer.py', PASSING)
        prelude = four_cpu_sample() + '''
def unknown_state():
    """Report unavailable introspection while leaving stock fixture machinery healthy."""
    return 'unavailable or unrecognized unittest module cleanup state: injected limitation'
v._module_cleanup_fallback_reason = unknown_state
'''
        output = self.validate(prelude=prelude)
        self.assert_exclusive(output, UNKNOWN)
        self.assertEqual(self.inventories(output), dict.fromkeys(
            ('discovered', 'started', 'completed', 'accounted'), IDS))
        self.assertEqual([(event['id'], event['kind']) for event in self.result_events(output)],
                         [(identity, kind) for identity in IDS for kind in ('start', 'success', 'stop')])

    def test_empty_stack_retains_real_concurrent_overlap(self):
        """Both ordinary owners must reach private gates before either is released."""
        fifo = self.parent / 'ready'
        os.mkfifo(fifo, 0o600)
        ready_fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, ready_fd)
        releases = [self.parent / ('release-' + str(index)) for index in range(2)]
        for index, module in enumerate(('test_example.py', 'test_peer.py')):
            self.write(module, f'''import os, time
from pathlib import Path
''' + PASSING.replace('self.assertEqual(2 + 2, 4)', f'''
        with open({str(fifo)!r}, 'w') as stream:
            stream.write('{index}:' + str(os.getpid()) + '\\n')
            stream.flush()
        deadline = time.monotonic() + 10
        while not Path({str(releases[index])!r}).exists():
            if time.monotonic() >= deadline:
                self.fail('overlap gate was not released')
            time.sleep(0.01)
        self.assertEqual(2 + 2, 4)'''))
        before = self.snapshot()
        command, environment = self.command(prelude=four_cpu_sample())
        process = subprocess.Popen(command, cwd=self.parent, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            data = b''
            with selectors.DefaultSelector() as selector:
                selector.register(ready_fd, selectors.EVENT_READ)
                deadline = time.monotonic() + 10
                while data.count(b'\n') < 2:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        if process.poll() is None:
                            process.terminate()
                        stdout, stderr = process.communicate(timeout=12)
                        self.fail('both workers must reach their gates: ' + stdout + stderr)
                    for _, _ in selector.select(0.1):
                        data += os.read(ready_fd, 65536)
            rows = [line.split(':') for line in data.decode().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual({row[0] for row in rows}, {'0', '1'})
            self.assertEqual(len({int(row[1]) for row in rows}), 2)
            self.assertTrue(all(not path.exists() for path in releases))
            for path in releases:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(descriptor)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            waves = [line for line in stdout.splitlines() if line.startswith('Wave ')]
            self.assertEqual(len(waves), 1, stdout)
            self.assertIn('A=4 T=2 C=1 concurrency=2', waves[0])
            self.assertIn('fallback=[]', waves[0])
            self.assertNotIn(PENDING, stdout)
            self.assertNotIn(UNKNOWN, stdout)
            self.assertEqual(self.inventories(stdout), dict.fromkeys(
                ('discovered', 'started', 'completed', 'accounted'), IDS))
            self.assertEqual([(event['id'], event['kind']) for event in self.result_events(stdout)],
                             [(identity, kind) for identity in IDS
                              for kind in ('start', 'success', 'stop')])
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=12)
            self.assertEqual(self.snapshot(), before)
