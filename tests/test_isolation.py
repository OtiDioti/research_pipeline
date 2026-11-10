"""Real enforcement checks. Skips mean the host has not passed live acceptance."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tests import use_checkout

use_checkout()
from research_pipeline import isolation


def fixture(root):
    for name in ('starting_evidence', 'sources', 'work', 'outputs', '.research_pipeline'):
        (root / name).mkdir()
    (root / 'starting_evidence/sentinel').write_text('protected')
    (root / 'AGENTS.md').write_text('protected')
    (root / 'RESEARCH_STATUS.md').write_text('protected')
    (root / '.research_pipeline/private').write_text('hidden operational state')

class PreflightResourceTests(unittest.TestCase):
    """Service/environment doubles test rejection, not real resource enforcement."""

    def test_live_acceptance_cannot_skip_missing_user_bus(self):
        with patch.dict(os.environ, {"RESEARCH_PIPELINE_M1_LIVE": "1"}, clear=True):
            with self.assertRaisesRegex(AssertionError, "user bus unavailable"):
                ServiceIsolationTests.setUpClass()

    def test_live_acceptance_cannot_skip_missing_bubblewrap(self):
        with patch.dict(os.environ, {"RESEARCH_PIPELINE_M1_LIVE": "1"}), \
             patch.object(shutil, "which", return_value=None):
            case = BubblewrapBoundaryTests("test_actual_mount_boundary_and_permitted_computation")
            with self.assertRaisesRegex(AssertionError, "Bubblewrap missing"):
                case.test_actual_mount_boundary_and_permitted_computation()

    def test_preflight_requires_verified_zero_swap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            cgroups = root / '.research_pipeline/cgroups'
            group = cgroups / 'probe'
            group.mkdir(parents=True)
            (group / 'memory.max').write_text(str(128 * 1024 * 1024))
            (group / 'pids.max').write_text('32')
            (group / 'cpu.max').write_text('50000 100000')
            config = isolation.Config(wall_seconds=8, memory_mib=128, max_tasks=32,
                                      cpu_percent=50, deadline=time.monotonic() + 8)
            def path(value):
                return cgroups if value == '/sys/fs/cgroup' else Path(value)
            def execute(config, project, argv, on_event):
                on_event('stdout', b'boundary probe passed\n')
                return isolation.ExecutionResult(0, cleanup_ok=True)
            with patch.dict(os.environ, {'XDG_RUNTIME_DIR': 'test-double',
                                         'DBUS_SESSION_BUS_ADDRESS': 'test-double'}), \
                 patch.object(isolation.shutil, 'which', return_value='/test-double'), \
                 patch.object(isolation, 'Path', side_effect=path), \
                 patch.object(isolation, 'service_properties', return_value={'ControlGroup': '/probe'}), \
                 patch.object(isolation, 'run_isolated', side_effect=execute):
                for swap in ('max', '1048576', None, '0'):
                    with self.subTest(swap=swap):
                        setting = group / 'memory.swap.max'
                        if swap is None:
                            setting.unlink()
                        else:
                            setting.write_text(swap)
                        if swap == '0':
                            capabilities = isolation.preflight(config, root)
                            self.assertEqual(capabilities['observed_cgroup_limits']['memory_swap_max'], '0')
                        else:
                            with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'Cannot verify cgroup'):
                                isolation.preflight(config, root)


class BubblewrapBoundaryTests(unittest.TestCase):
    def test_actual_mount_boundary_and_permitted_computation(self):
        if not shutil.which('bwrap'):
            if os.environ.get('RESEARCH_PIPELINE_M1_LIVE') == '1':
                self.fail('Bubblewrap missing during enabled live acceptance')
            self.skipTest('Bubblewrap missing; filesystem enforcement unverified')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'project'
            root.mkdir()
            fixture(root)
            outside = Path(temp) / 'host-private-sentinel'
            outside.write_text('not mounted')
            script = isolation.PROBE + f'\nassert not Path({str(outside)!r}).exists()\n'
            result = subprocess.run(isolation.bubblewrap_command(root, ['/usr/bin/python3', '-c', script]),
                                    capture_output=True, text=True, timeout=5)
            if result.returncode and any(s in result.stderr for s in ('Operation not permitted', 'No permissions', 'namespace')):
                if os.environ.get('RESEARCH_PIPELINE_M1_LIVE') == '1':
                    self.fail('Bubblewrap namespaces unavailable: ' + result.stderr.strip())
                self.skipTest('Bubblewrap namespaces unavailable: ' + result.stderr.strip())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'starting_evidence/sentinel').read_text(), 'protected')
            self.assertEqual((root / 'outputs/value').read_text(), '285')
            self.assertEqual(outside.read_text(), 'not mounted')


class ServiceIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('XDG_RUNTIME_DIR') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
            if os.environ.get('RESEARCH_PIPELINE_M1_LIVE') == '1':
                raise AssertionError('Required systemd user bus unavailable during enabled live acceptance')
            raise unittest.SkipTest('Required systemd user bus is not available; cgroup/lifetime acceptance incomplete')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            config = isolation.Config(wall_seconds=8, memory_mib=128, max_tasks=32,
                                      cpu_percent=50, deadline=time.monotonic() + 8)
            # An available but broken runtime is a failure, not a skip.
            cls.capabilities = isolation.preflight(config, root)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)

    def run_code(self, code, wall=4, memory=128, tasks=32):
        config = isolation.Config(wall_seconds=wall, memory_mib=memory, max_tasks=tasks,
                                  cpu_percent=50, deadline=time.monotonic() + wall)
        output = bytearray()
        def capture(channel, data):
            output.extend(data[:max(0, 65536-len(output))])
        result = isolation.run_isolated(config, self.root, ['/usr/bin/python3', '-c', code], on_event=capture)
        self.assertTrue(result.cleanup_ok, output.decode(errors='replace'))
        props = isolation.service_properties(config.unit)
        self.assertIn(props.get('ActiveState'), ('inactive', 'failed'))
        return result, output

    def test_actual_protected_inputs_and_computation(self):
        result, output = self.run_code(isolation.PROBE)
        self.assertEqual(result.returncode, 0, output.decode(errors='replace'))
        self.assertTrue(self.capabilities['observed_cgroup_limits'])

    def test_swap_is_disabled(self):
        # Production preflight reads the running service's actual cgroup setting.
        self.assertEqual(self.capabilities['observed_cgroup_limits']['memory_swap_max'], '0')

    def test_backend_failure_and_compute_failure_preserve_artifacts(self):
        result, _ = self.run_code("from pathlib import Path; Path('/project/work/partial.md').write_text('# Partial'); raise RuntimeError('failed computation')")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / 'work/partial.md').exists())

    CHILD = "from pathlib import Path; import time; p=Path('/project/work/heartbeat');\nwhile True: p.write_text(str(time.monotonic())); time.sleep(.03)"

    def child_code(self, wait):
        return ("import subprocess,time; "
                f"subprocess.Popen(['/usr/bin/python3','-c',{self.CHILD!r}],start_new_session=True); "
                f"time.sleep({wait})")

    def assert_child_stopped(self):
        heartbeat = self.root / 'work/heartbeat'
        self.assertTrue(heartbeat.exists(), 'Child never started; cleanup not exercised')
        before = heartbeat.read_bytes()
        time.sleep(.15)
        self.assertEqual(heartbeat.read_bytes(), before, 'Detached child survived')

    def test_normal_exit_kills_detached_descendant(self):
        result, _ = self.run_code(self.child_code(.3))
        self.assertEqual(result.returncode, 0)
        self.assert_child_stopped()

    def test_deadline_kills_detached_descendant(self):
        started = time.monotonic()
        result, _ = self.run_code(self.child_code(30), wall=1)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - started, 8)
        self.assert_child_stopped()

    def test_interruption_kills_detached_descendant(self):
        timer = threading.Timer(.7, lambda: os.kill(os.getpid(), signal.SIGINT))
        timer.start()
        try:
            result, _ = self.run_code(self.child_code(30))
        finally:
            timer.cancel()
            timer.join()
        self.assertTrue(result.interrupted)
        self.assert_child_stopped()

    def test_memory_and_file_limits(self):
        result, _ = self.run_code("x = bytearray(256 * 1024 * 1024)", memory=64)
        self.assertNotEqual(result.returncode, 0, 'Memory cap was not enforced')
        result, _ = self.run_code("f=open('/project/work/large','wb'); [f.write(b'x'*1048576) for _ in range(65)]; f.close()")
        self.assertNotEqual(result.returncode, 0, 'Per-file cap was not enforced')
        self.assertLessEqual((self.root / 'work/large').stat().st_size, 64 * 1024 * 1024)

    def test_task_limit(self):
        script = """import subprocess
children=[]
try:
    for _ in range(50):
        children.append(subprocess.Popen(['/usr/bin/sleep','20']))
except OSError:
    print('task cap reached', flush=True)
else:
    raise AssertionError('task cap was not enforced')
finally:
    for child in children: child.terminate()
    for child in children: child.wait()
"""
        result, output = self.run_code(script, tasks=16)
        self.assertEqual(result.returncode, 0, output.decode(errors='replace'))
        self.assertIn(b'task cap reached', output)
