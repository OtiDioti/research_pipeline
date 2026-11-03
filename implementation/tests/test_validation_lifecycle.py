"""Bounded fresh-process failure regressions for validator-owned workers and descendants."""

import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import unittest

from tests.validation_fixtures import CandidateFixture, PASSING


class LifecycleTests(CandidateFixture, unittest.TestCase):
    """Verify failures dominate green totals and leave no owned processes or private space."""

    def worker_source(self, body):
        """Create a test that records its process identity and private directory externally."""
        evidence = self.parent / 'worker.json'
        source = f'''import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
class Worker(unittest.TestCase):
    """Record real worker effects before a controlled lifecycle fault."""
    def test_body(self):
        """Publish cleanup evidence before executing the regression body."""
        Path({str(evidence)!r}).write_text(json.dumps(dict(pid=os.getpid(), temporary=tempfile.gettempdir())))
'''
        source += ''.join('        ' + line + '\n' for line in body.splitlines())
        self.write('test_example.py', source)
        return evidence

    def assert_removed(self, evidence):
        """Check recorded worker identity and private directory are absent after validation."""
        record = json.loads(evidence.read_text())
        self.assertFalse(Path('/proc') .joinpath(str(record['pid'])).exists(), record)
        self.assertFalse(Path(record['temporary']).exists(), record)

    def test_crash_and_passing_report_nonzero_exit(self):
        """A real os._exit crash and nonzero exit after valid end both fail without replay."""
        evidence = self.worker_source('os.write(1, b"CRASH EVIDENCE\\n")\nos._exit(23)')
        output = self.validate(1)
        self.assertIn('exited abnormally', output)
        self.assertIn('CRASH EVIDENCE', output)
        self.assertIn('Uncertain-effect IDs', output)
        self.assert_removed(evidence)
        self.write('test_example.py', PASSING)
        output = self.validate(1, prelude='''
original_send = v.send_frame
def exit_after_end(descriptor, frame):
    """Send valid complete evidence and then exit unsuccessfully."""
    original_send(descriptor, frame)
    if frame['type'] == 'end':
        v.os._exit(24)
v.send_frame = exit_after_end
''')
        self.assertIn('exited abnormally', output)

    def test_deadline_and_inherited_descendant_cleanup(self):
        """A blocked worker and its real subprocess obey the whole-invocation deadline."""
        child_file = self.parent / 'descendant'
        evidence = self.worker_source(f'''child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
Path({str(child_file)!r}).write_text(str(child.pid))
while True:
    time.sleep(1)''')
        output = self.validate(1, prelude='v.INVOCATION_SECONDS = 0.5', timeout=12)
        self.assertIn('deadline exceeded', output)
        self.assert_removed(evidence)
        self.assertFalse(Path('/proc', child_file.read_text()).exists())

    def test_orphan_holding_output(self):
        """A passing worker cannot leave a live child retaining captured stdout/stderr."""
        child_file = self.parent / 'descendant'
        evidence = self.worker_source(f'''child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
Path({str(child_file)!r}).write_text(str(child.pid))''')
        output = self.validate(1, timeout=12)
        self.assertTrue('descendants' in output, output)
        self.assert_removed(evidence)
        self.assertFalse(Path('/proc', child_file.read_text()).exists())

    def test_dead_worker_with_live_child(self):
        """A worker crash cannot strand a grandchild even before its protocol completes."""
        child_file = self.parent / 'descendant'
        evidence = self.worker_source(f'''child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
Path({str(child_file)!r}).write_text(str(child.pid))
os._exit(31)''')
        output = self.validate(1, timeout=12)
        self.assertIn('Execution failure:', output)
        self.assert_removed(evidence)
        self.assertFalse(Path('/proc', child_file.read_text()).exists())

    def test_interruptions(self):
        """SIGINT and SIGTERM enter the same cleanup path while a sequential child is blocked."""
        for signum in (signal.SIGINT, signal.SIGTERM):
            evidence = self.worker_source('while True:\n    time.sleep(1)')
            evidence.unlink(missing_ok=True)
            command, environment = self.command(sequential=True)
            process = subprocess.Popen(command, env=environment, cwd=self.parent,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 10
                while not evidence.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(evidence.exists(), 'worker never reached interruption gate')
                process.send_signal(signum)
                stdout, stderr = process.communicate(timeout=12)
                self.assertEqual(process.returncode, 1, stdout + stderr)
                self.assertIn(signal.Signals(signum).name, stdout + stderr)
                self.assert_removed(evidence)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=12)

    def finalization_prelude(self, api, boundary, fault):
        """Inject one late fault in a fresh API process and verify scoped restoration.

        Boundaries are owned-directory removal, final output/flush, subreaper
        restoration, or the gap between caller handler updates. Faults send an
        actual signal or expire only the private deadline; caller state is checked.
        """
        return f'''
api_name, boundary, fault = {api!r}, {boundary!r}, {fault!r}
current = None
fired = False
original_init = v.Invocation.__init__
def remember_invocation(self, deadline, **kwargs):
    """Retain the real invocation solely for deterministic finalization injection."""
    global current
    original_init(self, deadline, **kwargs)
    current = self
v.Invocation.__init__ = remember_invocation
def inject():
    """Fault once, only after real worker success and completed cleanup supervision."""
    global fired
    if fired:
        return
    assert current.cleaned
    assert current.workers
    assert all(worker['status'] == 0 and worker['quiescent'] and
               worker['ledger'].end and worker['ledger'].counts['successful'] == 1
               for worker in current.workers)
    fired = True
    print('FINALIZATION INJECTION: ' + boundary + ' after successful workers', file=sys.stdout)
    if fault == 'deadline':
        current.deadline = v.time.monotonic() - 1
    else:
        v.os.kill(v.os.getpid(), getattr(v.signal, fault))
original_rmtree = v.shutil.rmtree
def remove_owned(path, *args, **kwargs):
    """Deliver cleanup faults before removing the exact owned private directory."""
    if boundary == 'cleanup' and current and any(worker['temporary'] == path for worker in current.workers):
        assert current.cleaning
        inject()
    return original_rmtree(path, *args, **kwargs)
v.shutil.rmtree = remove_owned
original_prctl = v.prctl
def restore_subreaper(option, *args):
    """Inject while restoration still has protected invocation signal handlers."""
    if boundary == 'restore' and option == 36 and current and current.cleaned:
        assert current.cleaning
        inject()
    return original_prctl(option, *args)
v.prctl = restore_subreaper
original_signal = v.signal.signal
if boundary == 'handlers':
    original_signal(v.signal.SIGINT, v.signal.default_int_handler)
    original_signal(v.signal.SIGTERM, v.signal.SIG_DFL)
def restore_handler(signum, handler):
    """Deliver once after caller INT is installed but before TERM is restored."""
    previous = original_signal(signum, handler)
    if (boundary == 'handlers' and not fired and current and current.cleaned
            and signum == v.signal.SIGINT and handler is v.signal.default_int_handler):
        assert v.signal.getsignal(v.signal.SIGINT) is v.signal.default_int_handler
        assert v.signal.getsignal(v.signal.SIGTERM) == current.interrupt
        assert current.cleaning
        assert all(not v.Path(worker['temporary']).exists() and
                   not v.Path('/proc', str(worker['pid'])).exists()
                   for worker in current.workers)
        inject()
    return previous
v.signal.signal = restore_handler
class FinalReport:
    """Forward caller output while injecting at a deterministic final write or flush."""
    def write(self, text):
        """Keep genuine report evidence before delivering a one-shot late fault."""
        written = sys.stdout.write(text)
        marker = 'Total wall measurement:' if api_name == 'run_validation' else 'Counts:'
        if boundary == 'report' and text.startswith(marker):
            inject()
        return written
    def flush(self):
        """Exercise the public final check after successful report flushing."""
        sys.stdout.flush()
        if boundary == 'flush' and current and current.cleaned:
            inject()
original_api = getattr(v, api_name)
def call_api(root, stream, *, sequential=False):
    """Translate either API's ordinary result after verifying restored caller state."""
    handlers = {{signum: v.signal.getsignal(signum) for signum in (v.signal.SIGINT, v.signal.SIGTERM)}}
    mask = v.signal.pthread_sigmask(v.signal.SIG_BLOCK, set())
    before = v.ctypes.c_int()
    original_prctl(37, v.ctypes.byref(before))
    result = original_api(root, FinalReport(), sequential=sequential)
    after = v.ctypes.c_int()
    original_prctl(37, v.ctypes.byref(after))
    assert before.value == after.value, 'subreaper not restored'
    assert handlers == {{signum: v.signal.getsignal(signum) for signum in handlers}}, 'handlers not restored'
    assert mask == v.signal.pthread_sigmask(v.signal.SIG_BLOCK, set()), 'mask not restored'
    assert fired, 'finalization boundary was not reached'
    assert not current.cleaning, 'signal protection not cleared'
    assert all(not v.Path(worker['temporary']).exists() for worker in current.workers)
    assert type(result) is (int if api_name == 'run_validation' else bool)
    assert result == (1 if api_name == 'run_validation' else False), result
    print('FINALIZATION RESTORED AND REMOVED', file=sys.stdout)
    return result if api_name == 'run_validation' else int(not result)
v.run_validation = call_api
'''

    def assert_finalization_failure(self, api, boundary, fault, sequential):
        """Require late failure with truthful completed evidence, restoration and no worker leak."""
        evidence = self.worker_source('pass')
        output = self.validate(1, sequential=sequential,
                               prelude=self.finalization_prelude(api, boundary, fault))
        self.assertIn('deadline exceeded' if fault == 'deadline' else fault, output)
        self.assertIn('FINALIZATION INJECTION: ' + boundary + ' after successful workers', output)
        self.assertIn('FINALIZATION RESTORED AND REMOVED', output)
        self.assertIn('successful=1', output)
        inventories = self.inventories(output)
        self.assertEqual(inventories['completed'], ['tests.test_example.Worker.test_body'])
        self.assertEqual(inventories['accounted'], inventories['completed'])
        self.assertEqual(self.dispositions(output), [dict(ordinal=0,
            id='tests.test_example.Worker.test_body', kind='completed', events=['success'])])
        self.assertNotIn('Uncertain-effect IDs:', output)
        self.assert_removed(evidence)
        return output

    def test_cancellation_during_successful_cleanup(self):
        """Both signals latch during removal and invalidate each API in either scheduling mode."""
        for api in ('run_validation', 'run_suite'):
            for sequential in (False, True):
                for fault in ('SIGINT', 'SIGTERM'):
                    with self.subTest(api=api, sequential=sequential, fault=fault):
                        self.assert_finalization_failure(api, 'cleanup', fault, sequential)

    def test_deadline_during_successful_cleanup(self):
        """An elapsed deadline cannot excuse cleanup or permit a successful API return."""
        for api in ('run_validation', 'run_suite'):
            for sequential in (False, True):
                with self.subTest(api=api, sequential=sequential):
                    self.assert_finalization_failure(api, 'cleanup', 'deadline', sequential)

    def test_deadline_during_final_reporting_and_flush(self):
        """Public final checks include final measurements and the caller's final flush."""
        for api, boundary in (('run_validation', 'report'), ('run_validation', 'flush'), ('run_suite', 'flush')):
            for sequential in (False, True):
                with self.subTest(api=api, boundary=boundary, sequential=sequential):
                    output = self.assert_finalization_failure(api, boundary, 'deadline', sequential)
                    if api == 'run_validation':
                        self.assertIn('Coordinator measurement:', output)
                        self.assertIn('Total wall measurement:', output)

    def test_cancellation_during_final_output(self):
        """Reporting retains scoped signal handlers and restores caller state on late cancellation."""
        for api in ('run_validation', 'run_suite'):
            for fault in ('SIGINT', 'SIGTERM'):
                with self.subTest(api=api, fault=fault):
                    self.assert_finalization_failure(api, 'report', fault, False)

    def test_fault_during_scoped_restoration(self):
        """The post-context check catches a deferred signal or deadline expiry during restoration."""
        for api in ('run_validation', 'run_suite'):
            for fault in ('SIGINT', 'SIGTERM', 'deadline'):
                with self.subTest(api=api, fault=fault):
                    self.assert_finalization_failure(api, 'restore', fault, True)

    def test_cancellation_between_caller_handler_updates(self):
        """Real INT/TERM in the inter-handler window fail both APIs after complete restoration."""
        for api in ('run_validation', 'run_suite'):
            for sequential in (False, True):
                for fault in ('SIGINT', 'SIGTERM'):
                    with self.subTest(api=api, sequential=sequential, fault=fault):
                        self.assert_finalization_failure(api, 'handlers', fault, sequential)

    def test_caller_signal_mask_and_pending_term_preserved(self):
        """Successful fresh APIs preserve unrelated masks and caller-owned pending TERM."""
        for api in ('run_validation', 'run_suite'):
            for sequential in (False, True):
                for pending_term in (False, True):
                    with self.subTest(api=api, sequential=sequential, pending_term=pending_term):
                        evidence = self.worker_source('pass')
                        prelude = f'''
api_name, pending_term = {api!r}, {pending_term!r}
original_api = getattr(v, api_name)
def call_api(root, stream, *, sequential=False):
    """Own a blocked-signal fixture and consume its TERM before restoring its mask."""
    blocked = {{v.signal.SIGUSR1}}
    if pending_term:
        blocked.add(v.signal.SIGTERM)
    original_mask = v.signal.pthread_sigmask(v.signal.SIG_BLOCK, blocked)
    expected_mask = original_mask | blocked
    handlers = {{signum: v.signal.getsignal(signum) for signum in (v.signal.SIGINT, v.signal.SIGTERM)}}
    before = v.ctypes.c_int()
    v.prctl(37, v.ctypes.byref(before))
    try:
        if pending_term:
            v.os.kill(v.os.getpid(), v.signal.SIGTERM)
            assert v.signal.SIGTERM in v.signal.sigpending()
        result = original_api(root, stream, sequential=sequential)
        assert type(result) is (int if api_name == 'run_validation' else bool)
        assert result == (0 if api_name == 'run_validation' else True), result
        assert v.signal.pthread_sigmask(v.signal.SIG_BLOCK, set()) == expected_mask
        assert handlers == {{signum: v.signal.getsignal(signum) for signum in handlers}}
        after = v.ctypes.c_int()
        v.prctl(37, v.ctypes.byref(after))
        assert before.value == after.value
        if pending_term:
            assert v.signal.SIGTERM in v.signal.sigpending(), 'caller pending TERM consumed'
        print('CALLER MASK AND PENDING SIGNAL PRESERVED')
        return result if api_name == 'run_validation' else int(not result)
    finally:
        if pending_term:
            v.signal.sigtimedwait({{v.signal.SIGTERM}}, 0)
        v.signal.pthread_sigmask(v.signal.SIG_SETMASK, original_mask)
v.run_validation = call_api
'''
                        output = self.validate(sequential=sequential, prelude=prelude)
                        self.assertIn('CALLER MASK AND PENDING SIGNAL PRESERVED', output)
                        self.assertIn('successful=1', output)
                        inventories = self.inventories(output)
                        self.assertEqual(inventories['completed'], ['tests.test_example.Worker.test_body'])
                        self.assertEqual(inventories['accounted'], inventories['completed'])
                        self.assertNotIn('Uncertain-effect IDs:', output)
                        self.assert_removed(evidence)

    def test_second_signal_during_restoration(self):
        """Restoration completes after repeated cancellation and preserves both signal diagnostics."""
        for api in ('run_validation', 'run_suite'):
            with self.subTest(api=api):
                evidence = self.worker_source('pass')
                prelude = self.finalization_prelude(api, 'cleanup', 'SIGINT') + '''
previous_prctl = v.prctl
def second_signal(option, *args):
    """Deliver TERM after cleanup's INT, while subreaper restoration is protected."""
    if option == 36 and current and current.cleaned:
        assert current.cleaning
        assert current.cancelled == v.signal.SIGINT
        v.os.kill(v.os.getpid(), v.signal.SIGTERM)
    return previous_prctl(option, *args)
v.prctl = second_signal
'''
                output = self.validate(1, prelude=prelude)
                self.assertIn('SIGINT', output)
                self.assertIn('SIGTERM', output)
                self.assertIn('FINALIZATION RESTORED AND REMOVED', output)
                self.assertIn('successful=1', output)
                self.assertEqual(self.inventories(output)['completed'], ['tests.test_example.Worker.test_body'])
                self.assert_removed(evidence)

    def test_restoration_errors_do_not_abandon_remaining_state(self):
        """Ordinary errors and BaseExceptions fail APIs, retain obligations and attempt every handoff."""
        for api in ('run_validation', 'run_suite'):
            for action in ('subreaper', 'handler', 'mask'):
                for error_type in ('OSError', 'KeyboardInterrupt'):
                    with self.subTest(api=api, action=action, error_type=error_type):
                        evidence = self.worker_source('pass')
                        prelude = f'''
api_name, action = {api!r}, {action!r}
original_api = getattr(v, api_name)
original_init = v.Invocation.__init__
original_prctl, original_signal = v.prctl, v.signal.signal
original_mask = v.signal.pthread_sigmask
current = None
attempted = []
fired = False
def remember(self, *args, **kwargs):
    """Retain the invocation to verify failed obligations without rerunning work."""
    global current
    original_init(self, *args, **kwargs)
    current = self
v.Invocation.__init__ = remember
def fail_once(name):
    """Record real restoration attempts and fail the selected operation once."""
    global fired
    attempted.append(name)
    if name == action and not fired:
        fired = True
        raise {error_type}()
def restore_subreaper(option, argument):
    """Model an unsuccessful subreaper restoration before its OS operation."""
    if option == 36 and current and current.cleaned:
        fail_once('subreaper')
    return original_prctl(option, argument)
def restore_handler(signum, handler):
    """Fail INT restoration while leaving the later TERM action observable."""
    if current and current.cleaned:
        fail_once('handler' if signum == v.signal.SIGINT else 'term')
    return original_signal(signum, handler)
def restore_mask(how, mask):
    """Model unmask failure after checking latch-only protection was cleared."""
    if how == v.signal.SIG_SETMASK and current and current.cleaned:
        assert not current.cleaning
        fail_once('mask')
    return original_mask(how, mask)
v.prctl, v.signal.signal, v.signal.pthread_sigmask = restore_subreaper, restore_handler, restore_mask
def call_api(root, stream, *, sequential=False):
    """Assert failure and retained obligations, then recover only the harness's scoped state."""
    handlers = {{signum: v.signal.getsignal(signum) for signum in (v.signal.SIGINT, v.signal.SIGTERM)}}
    mask = original_mask(v.signal.SIG_BLOCK, set())
    before = v.ctypes.c_int()
    original_prctl(37, v.ctypes.byref(before))
    try:
        result = original_api(root, stream, sequential=sequential)
        assert type(result) is (int if api_name == 'run_validation' else bool)
        assert result == (1 if api_name == 'run_validation' else False)
        assert attempted == ['subreaper', 'handler', 'term', 'mask'], attempted
        assert not current.cleaning
        assert current.old_subreaper == (before.value if action == 'subreaper' else None)
        assert current.signals == ({{v.signal.SIGINT: handlers[v.signal.SIGINT]}} if action == 'handler' else {{}})
        assert current.old_signal_mask == (mask if action == 'mask' else None)
        assert current.cleanup_errors
        print('ALL RESTORATION ACTIONS ATTEMPTED')
        return result if api_name == 'run_validation' else int(not result)
    finally:
        v.prctl, v.signal.signal, v.signal.pthread_sigmask = original_prctl, original_signal, original_mask
        current.restore()
        current.restore()  # Completed restoration is harmless to repeat.
        assert not current.cleaning
        assert original_mask(v.signal.SIG_BLOCK, set()) == mask
        assert handlers == {{signum: v.signal.getsignal(signum) for signum in handlers}}
        after = v.ctypes.c_int()
        original_prctl(37, v.ctypes.byref(after))
        assert before.value == after.value
v.run_validation = call_api
'''
                        output = self.validate(1, prelude=prelude)
                        self.assertIn('ALL RESTORATION ACTIONS ATTEMPTED', output)
                        self.assertIn(error_type, output)
                        self.assertIn('successful=1', output)
                        self.assertNotIn('Uncertain-effect IDs:', output)
                        self.assert_removed(evidence)

    def test_signal_facilities_required_before_scoped_installation(self):
        """Missing mask/pending facilities reject execution before changing any scoped state."""
        for name in ('pthread_sigmask', 'sigpending', 'sigtimedwait'):
            with self.subTest(facility=name):
                output = self.validate(1, prelude=f'''
delattr(v.signal, {name!r})
def forbidden_prctl(*args):
    """Detect any lifecycle installation after a missing prerequisite."""
    raise AssertionError('scoped state was touched')
v.prctl = forbidden_prctl
''')
                self.assertIn('signal mask/pending-wait facilities required', output)
                self.assertNotIn('scoped state was touched', output)
                self.assertNotIn('Counts:', output)

    def test_coordinator_exception_cleanup(self):
        """An exception after fork terminates the owned child rather than orphaning it."""
        evidence = self.worker_source('while True:\n    time.sleep(1)')
        output = self.validate(1, prelude=f'''
def broken_supervise(invocation, workers):
    """Wait for a real test body then inject a coordinator fault."""
    deadline = v.time.monotonic() + 5
    while not v.Path({str(evidence)!r}).exists() and v.time.monotonic() < deadline:
        v.time.sleep(0.01)
    raise RuntimeError('coordinator fault')
v.supervise_wave = broken_supervise
''')
        self.assertIn('coordinator fault', output)
        self.assert_removed(evidence)

    def test_output_pressure_and_global_limits(self):
        """Descriptor and subprocess output drains concurrently; both aggregate channels are bounded."""
        self.worker_source('os.write(1, b"a" * 100000)\nos.write(2, b"b" * 100000)')
        output = self.validate()
        self.assertIn('a' * 100000, output)
        self.assertIn('b' * 100000, output)
        for descriptor, channel in ((1, 'stdout'), (2, 'stderr')):
            self.worker_source(f'os.write({descriptor}, b"x" * 100000)')
            prelude = '''
original_init = v.Invocation.__init__
def small_bounds(self, deadline, **kwargs):
    """Lower a private supervision bound for a tiny output regression."""
    original_init(self, deadline, output_limit=32768)
v.Invocation.__init__ = small_bounds
'''
            output = self.validate(1, prelude=prelude)
            self.assertIn('channel=' + channel, output)
            self.assertIn('limit=32768', output)

    def test_protocol_faults_and_cleanup_failure_precedence(self):
        """Truncated/oversized frames and failed private cleanup override otherwise passing tests."""
        for injected in ("v.os.write(descriptor, b'\\x00\\x00')", "v.os.write(descriptor, b'\\xff\\xff\\xff\\xff')"):
            output = self.validate(1, prelude=f'''
def broken_send(descriptor, frame):
    """Emit a corrupt first frame and terminate."""
    {injected}
    v.os._exit(0)
v.send_frame = broken_send
''')
            self.assertIn('protocol frame', output)
        evidence = self.worker_source('pass')
        output = self.validate(1, prelude='''
def denied_cleanup(path):
    """Model a private-directory removal failure."""
    raise PermissionError('fixture cleanup denied')
v.shutil.rmtree = denied_cleanup
''')
        self.assertIn('fixture cleanup denied', output)
        self.assertIn('successful=1', output)
        # Recover only the exact owned directory deliberately left by this fault.
        shutil.rmtree(json.loads(evidence.read_text())['temporary'])

    def test_preexisting_children_and_hook_threads(self):
        """Unsafe callers and discovery hooks fail before executing/replaying test bodies."""
        output = self.validate(1, prelude='''
child = v.subprocess.Popen([v.sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
import atexit
atexit.register(lambda: (child.terminate(), child.wait()))
''')
        self.assertIn('pre-existing children', output)
        self.write('test_example.py', PASSING + '''
import threading
stop = threading.Event()
def load_tests(loader, tests, pattern):
    """Leave a daemon thread to demonstrate an unsupported discovery effect."""
    threading.Thread(target=stop.wait, daemon=True).start()
    return tests
''')
        self.assertIn('live threads', self.validate(1))

    def test_parent_death_signal_in_inherited_group(self):
        """A separate subreaper harness verifies direct-worker death without leaking an orphan."""
        evidence = self.worker_source('while True:\n    time.sleep(1)')
        command, environment = self.command()
        program = '''import ctypes, json, os, signal, subprocess, sys, time
from pathlib import Path
libc = ctypes.CDLL(None, use_errno=True)
assert libc.prctl(36, 1, 0, 0, 0) == 0
command = json.loads(sys.argv[1])
evidence = Path(sys.argv[2])
coordinator = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
worker = None
try:
    deadline = time.monotonic() + 10
    while not evidence.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert evidence.exists(), 'worker readiness missing'
    record = json.loads(evidence.read_text())
    worker = record['pid']
    assert os.getpgid(worker) == os.getpgrp() == os.getpgid(coordinator.pid)
    coordinator.kill()
    coordinator.communicate(timeout=5)
    while time.monotonic() < deadline:
        pid, status = os.waitpid(worker, os.WNOHANG)
        if pid:
            assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL, status
            worker = None
            break
        time.sleep(0.01)
    assert worker is None, 'worker survived coordinator death'
    print('PARENT-DEATH VERIFIED')
finally:
    if coordinator.poll() is None:
        coordinator.kill()
    coordinator.communicate(timeout=5)
    if worker is not None:
        os.kill(worker, signal.SIGKILL)
        os.waitpid(worker, 0)
'''
        result = subprocess.run([sys.executable, '-B', '-c', program, json.dumps(command), str(evidence)],
                                env=environment, cwd=self.parent, capture_output=True, text=True, timeout=20)
        try:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PARENT-DEATH VERIFIED', result.stdout)
        finally:
            if evidence.exists():
                # Abrupt coordinator death cannot run directory cleanup. This
                # fixture harness owns and removes the exact recorded directory.
                shutil.rmtree(json.loads(evidence.read_text())['temporary'])

    def test_term_escalation_and_discovery_child_cleanup(self):
        """TERM-resistant workers escalate to KILL; discovery children fail without replay."""
        evidence = self.worker_source('import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True:\n    time.sleep(1)')
        output = self.validate(1, prelude='v.INVOCATION_SECONDS = 0.5', timeout=12)
        self.assertIn('deadline exceeded', output)
        self.assert_removed(evidence)
        child_file = self.parent / 'hook-child'
        self.write('test_example.py', PASSING + f'''
import subprocess, sys
from pathlib import Path
def load_tests(loader, tests, pattern):
    """Leave a child during discovery to test ownership rejection and cleanup."""
    child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
    Path({str(child_file)!r}).write_text(str(child.pid))
    return tests
''')
        output = self.validate(1)
        self.assertIn('pre-existing children', output)
        self.assertFalse(Path('/proc', child_file.read_text()).exists())

    def test_aggregate_output_across_workers(self):
        """Two individually small streams still exceed one shared invocation allowance."""
        from tests.validation_fixtures import four_cpu_sample
        prelude = four_cpu_sample() + '''
original_init = v.Invocation.__init__
def small_bounds(self, deadline, **kwargs):
    """Lower the aggregate bound while preserving production scheduling."""
    original_init(self, deadline, output_limit=32768)
v.Invocation.__init__ = small_bounds
'''
        for descriptor, channel in ((1, 'stdout'), (2, 'stderr')):
            source = f'''import os, unittest
class Output(unittest.TestCase):
    """Emit fewer bytes than the shared bound from each concurrent unit."""
    def test_body(self):
        """Use descriptor output that Python-only redirection would miss."""
        os.write({descriptor}, b'x' * 20000)
'''
            self.write('test_example.py', source)
            self.write('test_peer.py', source)
            output = self.validate(1, prelude=prelude)
            self.assertIn('channel=' + channel, output)
            self.assertIn('limit=32768', output)
