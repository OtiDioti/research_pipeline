"""Real enforcement checks. Skips mean the host has not passed live acceptance."""
import os
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from tests import use_checkout

use_checkout()
from research_pipeline import cli, isolation, workspace


def live_enabled():
    return any(os.environ.get(f'RESEARCH_PIPELINE_M{n}_LIVE') == '1' for n in (1, 2))


def fixture(root):
    for name in ('starting_evidence', 'sources', 'work', 'outputs', 'handoffs', '.research_pipeline'):
        (root / name).mkdir()
    (root / 'starting_evidence/sentinel').write_text('protected')
    (root / 'AGENTS.md').write_text('protected')
    (root / 'RESEARCH_STATUS.md').write_text('protected')
    (root / 'work/protected.md').write_text('# Protected canonical note')
    (root / '.research_pipeline/private').write_text('hidden operational state')

class PreflightResourceTests(unittest.TestCase):
    """Service/environment doubles test rejection, not real resource enforcement."""

    def test_live_acceptance_cannot_skip_missing_user_bus(self):
        for milestone in (1, 2):
            with patch.dict(os.environ, {f"RESEARCH_PIPELINE_M{milestone}_LIVE": "1"}, clear=True):
                with self.assertRaisesRegex(AssertionError, "user bus unavailable"):
                    ServiceIsolationTests.setUpClass()

    def test_live_acceptance_cannot_skip_missing_bubblewrap(self):
        with patch.dict(os.environ, {"RESEARCH_PIPELINE_M1_LIVE": "1"}), \
             patch.object(shutil, "which", return_value=None):
            case = BubblewrapBoundaryTests("test_actual_mount_boundary_and_permitted_computation")
            with self.assertRaisesRegex(AssertionError, "Bubblewrap missing"):
                case.test_actual_mount_boundary_and_permitted_computation()

    def test_preflight_requires_memory_zero_swap_and_tasks_without_cpu_controller(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            cgroups = root / '.research_pipeline/cgroups'
            group = cgroups / 'probe'
            group.mkdir(parents=True)
            settings = {'memory.max': str(128 * 1024 * 1024),
                        'memory.swap.max': '0', 'pids.max': '32'}
            for name, value in settings.items():
                (group / name).write_text(value)
            # Mirrors the demonstrated host: memory/pids delegated, no cpu.max.
            config = isolation.Config(wall_seconds=8, memory_mib=128, max_tasks=32,
                                      deadline=time.monotonic() + 8)
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
                capabilities = isolation.preflight(config, root)
                self.assertEqual(capabilities['observed_cgroup_limits'],
                                 {'memory_max': settings['memory.max'],
                                  'memory_swap_max': '0', 'pids_max': '32'})
                for name, valid in settings.items():
                    for invalid in (None, 'max', '1048576'):
                        with self.subTest(resource=name, value=invalid):
                            setting = group / name
                            if invalid is None:
                                setting.unlink()
                            else:
                                setting.write_text(invalid)
                            with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'Cannot verify cgroup'):
                                isolation.preflight(config, root)
                            setting.write_text(valid)


class BubblewrapBoundaryTests(unittest.TestCase):
    def test_actual_mount_boundary_and_permitted_computation(self):
        if not shutil.which('bwrap'):
            if live_enabled():
                self.fail('Bubblewrap missing during enabled live acceptance')
            self.skipTest('Bubblewrap missing; filesystem enforcement unverified')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'project'
            root.mkdir()
            fixture(root)
            control, response = (root / '.research_pipeline' / name for name in ('control', 'response'))
            control.mkdir()
            response.mkdir()
            outside = Path(temp) / 'host-private-sentinel'
            outside.write_text('not mounted')
            script = isolation.PROBE + f'\nassert not Path({str(outside)!r}).exists()\n'
            script += """
for p in (Path('/run/research-control/forbidden'), Path('/run/research-checkpoint-helper.py')):
    try: p.write_text('changed')
    except OSError: pass
    else: raise AssertionError('checkpoint control or helper is writable')
Path('/run/research-checkpoint/probe').write_text('writable')
subprocess.run(['/usr/bin/python3', '/run/research-checkpoint-helper.py', '--check'], check=True)
"""
            result = subprocess.run(isolation.bubblewrap_command(root, ['/usr/bin/python3', '-c', script],
                                                                 control=control, response=response),
                                    capture_output=True, text=True, timeout=5)
            if result.returncode and any(s in result.stderr for s in ('Operation not permitted', 'No permissions', 'namespace')):
                if live_enabled():
                    self.fail('Bubblewrap namespaces unavailable: ' + result.stderr.strip())
                self.skipTest('Bubblewrap namespaces unavailable: ' + result.stderr.strip())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'starting_evidence/sentinel').read_text(), 'protected')
            self.assertEqual((root / 'outputs/value').read_text(), '285')
            self.assertEqual(outside.read_text(), 'not mounted')
            self.assertEqual((response / 'probe').read_text(), 'writable')


class ServiceIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('XDG_RUNTIME_DIR') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
            if live_enabled():
                raise AssertionError('Required systemd user bus unavailable during enabled live acceptance')
            raise unittest.SkipTest('Required systemd user bus is not available; cgroup/lifetime acceptance incomplete')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            config = isolation.Config(wall_seconds=8, memory_mib=128, max_tasks=32,
                                      deadline=time.monotonic() + 8)
            # An available but broken runtime is a failure, not a skip.
            cls.capabilities = isolation.preflight(config, root)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)

    def run_code(self, code, wall=4, memory=128, tasks=32):
        config = isolation.Config(wall_seconds=wall, memory_mib=memory, max_tasks=tasks,
                                  deadline=time.monotonic() + wall)
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

    def test_requested_stop_with_closed_streams_kills_detached_descendant(self):
        """Scientific-worker fixture, no model: ignored saving and closed pipes."""
        began = time.monotonic()
        config = isolation.Config(wall_seconds=5, deadline=began + 5,
                                  memory_mib=128, max_tasks=32)
        script = ("import subprocess,time,os; "
                  f"subprocess.Popen(['/usr/bin/python3','-c',{self.CHILD!r}],"
                  "start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                  "time.sleep(.3); os.close(1); os.close(2); time.sleep(30)")
        result = isolation.run_isolated(config, self.root, ["/usr/bin/python3", "-c", script],
                                       poll=lambda: "pause" if time.monotonic() - began > .8 else None)
        self.assertEqual(result.requested_stop, "pause")
        self.assertTrue(result.cleanup_ok)
        self.assertFalse(result.timed_out)
        self.assertLess(time.monotonic() - began, 5)
        self.assert_child_stopped()

    def test_cooperative_scientific_worker_prepares_before_service_cleanup(self):
        self.cooperative_worker("pause")

    def test_rollover_scientific_worker_prepares_before_descendant_cleanup(self):
        self.cooperative_worker("rollover")

    def cooperative_worker(self, reason):
        """Actual helper/mount/service handshake; explicitly not Codex science."""
        from tests.test_continuity import HANDOFF
        activation = uuid.uuid4().hex
        state = {"run_id": uuid.uuid4().hex, "activation_id": activation,
                 "ownership_nonce": uuid.uuid4().hex, "state": "running"}
        session = self.root / ".research_pipeline/sessions" / activation
        control, response, drafts = (session / name for name in ("control", "response", "drafts"))
        for directory in (control, response, drafts):
            directory.mkdir(parents=True)
        config = isolation.Config(wall_seconds=8, deadline=time.monotonic() + 8,
                                  memory_mib=128, max_tasks=32, control=control,
                                  response=response, drafts=drafts)
        intake = workspace.Intake(self.root, "Worker fixture.", "", [], {})
        baseline = workspace.science_fingerprints(self.root)
        controller = cli.CheckpointControl(self.root, state, config, intake, session, baseline, [])
        config.on_poll, config.launch_guard = controller.poll, controller.launch_guard
        request = {"version": 1, **workspace.owner_fields(state), "reason": reason,
                   "request_id": uuid.uuid4().hex, "requested_at": cli.now()}
        script = f"""
from pathlib import Path
import subprocess, time
control = Path('/run/research-control/request.json')
subprocess.Popen(['/usr/bin/python3', '-c', {self.CHILD!r}], start_new_session=True)
drafts = Path('/run/research-drafts')
(drafts / 'work').mkdir()
(drafts / 'handoffs').mkdir()
(drafts / 'work/PLAN.md').write_text('# Saved worker plan')
(drafts / 'handoffs/primary.md').write_text({HANDOFF!r})
Path('/project/work/data.csv').write_text('n,value\\n1,2\\n')
for path in (Path('/run/research-control/forbidden'),
             Path('/run/research-checkpoint-helper.py')):
    try: path.write_text('changed')
    except OSError: pass
    else: raise AssertionError('trusted checkpoint control was writable')
print('worker ready', flush=True)
while not control.exists(): time.sleep(.02)
subprocess.run(['/usr/bin/python3', '/run/research-checkpoint-helper.py'], check=True)
"""
        output = bytearray()
        def capture(channel, data):
            output.extend(data)
            if b"worker ready" in output and not (control / "request.json").exists():
                workspace.atomic_text(control / "request.json", json.dumps(request))
        with patch.object(cli, "SAVING_GRACE", 3):
            result = isolation.run_isolated(config, self.root, ["/usr/bin/python3", "-c", script],
                                           on_event=capture)
        self.assertTrue(result.cleanup_ok, output.decode(errors="replace"))
        self.assertFalse(result.timed_out, output.decode(errors="replace"))
        self.assertIn("checkpoint_prepared", state)
        self.assertTrue(workspace.read_control(control / "ack.json")["accepted"])
        self.assertFalse((self.root / "work/PLAN.md").exists())
        workspace.load_prepared(self.root, state)
        workspace.finalize_science(self.root, state, intake, session, drafts, baseline, [])
        self.assertEqual((self.root / "work/PLAN.md").read_text(), "# Saved worker plan")
        self.assertIn("checkpoint", state)
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
