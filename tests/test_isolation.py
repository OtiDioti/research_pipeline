"""Real enforcement checks. Skips mean the host has not passed live acceptance."""
import os
import sys
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

from tests import use_checkout, job_driver

use_checkout()
from research_pipeline import cli, isolation, references, workspace, tools, jobs


def live_enabled():
    return any(os.environ.get(f'RESEARCH_PIPELINE_M{n}_LIVE') == '1' for n in (1, 2, 3, 4))


def fixture(root):
    for name in ('starting_evidence', 'sources', 'work', 'outputs', 'handoffs', '.research_pipeline'):
        (root / name).mkdir()
    (root / 'starting_evidence/sentinel').write_text('protected')
    (root / 'AGENTS.md').write_text('protected')
    (root / 'RESEARCH_STATUS.md').write_text('protected')
    (root / 'work/protected.md').write_text('# Protected canonical note')
    (root / '.research_pipeline/private').write_text('hidden operational state')


# No inference or credentials: exercise the installed native runtimes together.
# The model catalog requires code mode; feature-list checks alone missed its
# disabled host, and CPU-sized runtime pools overflowed a 64-task research slot.
CODEX_RUNTIME_PROBE = r'''
import json, struct, subprocess, time
from pathlib import Path
processes = []
try:
    for argv in (['/opt/codex/codex', 'app-server'], ['/opt/codex/codex-exec-server']):
        processes.append(subprocess.Popen(argv, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    backend = processes[0]
    backend.stdin.write(b'{"id":1,"method":"initialize","params":{"clientInfo":{"name":"runtime-probe","version":"1"}}}\n')
    backend.stdin.flush()
    assert json.loads(backend.stdout.readline())['id'] == 1
    host = subprocess.Popen(['/opt/codex/codex-code-mode-host'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(host)
    def receive():
        header = host.stdout.read(4)
        assert len(header) == 4, 'code-mode host closed stdout'
        size = struct.unpack('<I', header)[0]
        assert size <= 65536, size
        return json.loads(host.stdout.read(size))
    def send(message):
        encoded = json.dumps(message).encode()
        host.stdin.write(struct.pack('<I', len(encoded)) + encoded)
        host.stdin.flush()
        return receive()
    ready = send({'type':'connection/hello', 'supportedVersions':[1],
                  'requiredCapabilities':[], 'optionalCapabilities':[]})
    assert ready['type'] == 'connection/ready', ready
    opened = send({'type':'operation/request', 'id':1,
                   'request':{'method':'session/open', 'sessionId':'probe'}})
    assert opened['result']['status'] == 'ok', opened
    started = send({'type':'operation/request', 'id':2, 'request':{
        'method':'session/execute', 'sessionId':'probe', 'request':{
            'tool_call_id':'probe', 'source':'text(6 * 7)', 'enabled_tools':[],
            'yield_time_ms':1000, 'max_output_tokens':1000}}})
    assert started['result']['status'] == 'ok', started
    completed = receive()
    result = completed['result']['value']['Result']
    assert result['error_text'] is None, result
    assert result['content_items'] == [{'type':'input_text', 'text':'42'}], result
    # Let the idle exec server finish startup before counting its worker pool.
    time.sleep(.2)
    assert all(p.poll() is None for p in processes), 'native runtime exited'
    threads = sum(len(list(p.glob('task/*'))) for p in Path('/proc').glob('[0-9]*'))
    assert threads <= 64, f'native runtime exhausted the 64-task slot: {threads}'
    subprocess.run(['/usr/bin/python3', '-c', 'assert 6 * 7 == 42'], check=True, timeout=2)
    print(f'code-mode runtime check passed; namespace tasks={threads}', flush=True)
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
        p.communicate(timeout=3)
'''


def native_codex(case):
    binary = shutil.which('codex')
    if not binary:
        if live_enabled():
            case.fail('Codex missing during enabled live acceptance')
        case.skipTest('Codex missing; native runtime startup unverified')
    return str(Path(binary).resolve())


class PreflightResourceTests(unittest.TestCase):
    """Service/environment doubles test rejection, not real resource enforcement."""

    def test_cleanup_deadline_exhaustion_does_not_grant_escalation_time(self):
        with patch.object(isolation.time, "monotonic", return_value=100), \
             patch.object(isolation.subprocess, "run") as run:
            self.assertFalse(isolation.stop_service("research-deadline.service", deadline=100))
            run.assert_not_called()

    def test_cleanup_controls_share_remaining_deadline(self):
        def control(argv, **kwargs):
            self.assertLessEqual(kwargs["timeout"], .25)
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        with patch.object(isolation.time, "monotonic", return_value=100), \
             patch.object(isolation.subprocess, "run", side_effect=control) as run:
            self.assertFalse(isolation.stop_service("research-deadline.service", deadline=100.25))
            self.assertEqual(run.call_count, 2)  # query and best-effort kill share the deadline

    def test_live_acceptance_cannot_skip_missing_user_bus(self):
        for milestone in (1, 2, 3, 4):
            with patch.dict(os.environ, {f"RESEARCH_PIPELINE_M{milestone}_LIVE": "1"}, clear=True):
                with self.assertRaisesRegex(AssertionError, "user bus unavailable"):
                    ServiceIsolationTests.setUpClass()

    def test_live_acceptance_cannot_skip_missing_bubblewrap(self):
        for milestone in (1, 2, 3, 4):
            with patch.dict(os.environ, {f"RESEARCH_PIPELINE_M{milestone}_LIVE": "1"}, clear=True), \
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
    def test_native_code_mode_runtime_fits_task_slot(self):
        binary = native_codex(self)
        if not shutil.which('bwrap'):
            if live_enabled():
                self.fail('Bubblewrap missing during enabled live acceptance')
            self.skipTest('Bubblewrap missing; native runtime startup unverified')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            result = subprocess.run(isolation.bubblewrap_command(
                root, ['/usr/bin/python3', '-c', CODEX_RUNTIME_PROBE], codex=binary),
                capture_output=True, text=True, timeout=12)
            if result.returncode and any(s in result.stderr for s in
                                         ('Operation not permitted', 'No permissions', 'namespace')):
                if live_enabled():
                    self.fail('Bubblewrap namespaces unavailable: ' + result.stderr)
                self.skipTest('Bubblewrap namespaces unavailable: ' + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('code-mode runtime check passed', result.stdout)

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
            prior = Path(temp) / 'prior'
            (prior / 'outputs').mkdir(parents=True)
            (prior / 'outputs/value.md').write_text('# Preliminary source\nreference-needle: n > 0\n')
            (prior / 'FOLDER_CONTENT.md').write_text('# Immutable source index\n')
            (prior / '.research_pipeline').mkdir()
            (prior / '.research_pipeline/private').write_text('not authorized')
            workspace.atomic_text(root / references.REGISTRY, json.dumps({
                'version': 1, 'references': {'prior': str(prior)}}))
            config = isolation.Config(deadline=time.monotonic() + 5)
            references.configure(config, root, control.parent, workspace.Intake(root, '', '', [], {}))
            source_before = {p.relative_to(prior).as_posix(): workspace.file_digest(p)
                             for p in prior.rglob('*') if p.is_file()}
            protected_before = workspace.fingerprints(root)
            script = isolation.PROBE + f'\nassert not Path({str(outside)!r}).exists()\n'
            script += """
for p in (Path('/run/research-control/forbidden'), Path('/run/research-checkpoint-helper.py')):
    try: p.write_text('changed')
    except OSError: pass
    else: raise AssertionError('checkpoint control or helper is writable')
Path('/run/research-checkpoint/probe').write_text('writable')
subprocess.run(['/usr/bin/python3', '/run/research-checkpoint-helper.py', '--check'], check=True)
import json
ref = Path('/references/prior')
assert (ref / 'outputs/value.md').read_text().startswith('# Preliminary')
assert not (ref / '.research_pipeline').exists()
for p in (ref / 'outputs/value.md', ref / 'FOLDER_CONTENT.md',
          Path('/run/research-references.json'), Path('/run/research-references.py')):
    for action in (lambda: p.write_text('changed'), lambda: p.unlink(),
                   lambda: p.rename(p.with_name('replacement'))):
        try: action()
        except OSError: pass
        else: raise AssertionError('reference or retrieval control changed')
for p in (ref / 'outputs/created', ref / 'created', Path('/references/unauthorized')):
    try: p.write_text('changed')
    except OSError: pass
    else: raise AssertionError('reference creation succeeded')
found = subprocess.run(['/usr/bin/python3', '/run/research-references.py',
                        'search', 'reference-needle'], check=True, capture_output=True, text=True)
assert json.loads(found.stdout)['matches'][0]['line'] == 2
read = subprocess.run(['/usr/bin/python3', '/run/research-references.py',
                       'read', 'prior', 'outputs/value.md'], check=True, capture_output=True, text=True)
assert json.loads(read.stdout)['sha256']
"""
            result = subprocess.run(isolation.bubblewrap_command(root, ['/usr/bin/python3', '-c', script],
                                        control=control, response=response,
                                        reference_mounts=config.reference_mounts,
                                        reference_catalog=config.reference_catalog),
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
            self.assertEqual(source_before, {p.relative_to(prior).as_posix(): workspace.file_digest(p)
                                            for p in prior.rglob('*') if p.is_file()})
            self.assertEqual(protected_before, workspace.fingerprints(root))


    def test_actual_task_boundary_and_live_delivery_visibility(self):
        if not shutil.which('bwrap'):
            if live_enabled():
                self.fail('Bubblewrap missing during enabled live acceptance')
            self.skipTest('Bubblewrap missing; task boundary unverified')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            child_id, sibling_id = 'task-' + 'a'*32, 'task-' + 'b'*32
            child_rel = workspace.task_directory(child_id)
            sibling_rel = workspace.task_directory(sibling_id)
            for rel in (child_rel, sibling_rel):
                (root / rel).mkdir(parents=True)
                (root / rel / 'RESULT.md').write_text('# Preliminary old result')
                (root / rel / 'code.py').write_text('protected native code')
            drafts = root / '.research_pipeline/child-drafts'
            drafts.mkdir()
            script = f"""
from pathlib import Path
own = Path('/project/{child_rel}')
for target in ('/project/work/protected.md', '/project/outputs/original.py',
               '/project/AGENTS.md', '/project/starting_evidence/sentinel',
               '/project/{sibling_rel}/code.py', '/project/{sibling_rel}/RESULT.md'):
    p = Path(target)
    for operation in (lambda: p.write_text('hostile'), lambda: p.unlink(),
                      lambda: p.rename(p.with_name('stolen'))):
        try: operation()
        except OSError: pass
        else: raise AssertionError('foreign research writable: ' + target)
(own / 'calculation.py').write_text('print(42)')
import subprocess
assert subprocess.check_output(['/usr/bin/python3', str(own / 'calculation.py')]).strip() == b'42'
p = Path('/run/research-drafts/{child_rel}/RESULT.md')
p.parent.mkdir(parents=True)
p.write_text('# Preliminary new result: correction 0.1; applicability remains uncertain.')
"""
            (root / 'outputs/original.py').write_text('protected parent code')
            command = isolation.bubblewrap_command(root, ['/usr/bin/python3','-c',script],
                                                   task_id=child_id, drafts=drafts)
            child = subprocess.run(command, capture_output=True, text=True, timeout=5)
            if child.returncode and any(t in child.stderr for t in ('Operation not permitted','No permissions','namespace')):
                if live_enabled():
                    self.fail('Bubblewrap task namespaces unavailable: ' + child.stderr)
                self.skipTest('Bubblewrap task namespaces unavailable: ' + child.stderr)
            self.assertEqual(child.returncode, 0, child.stderr)
            reader_code = f"""
from pathlib import Path
import time
p = Path('/project/{child_rel}/RESULT.md')
print('reader ready', flush=True)
end = time.monotonic() + 3
while time.monotonic() < end:
    if 'correction 0.1' in p.read_text():
        print('live delivery visible', flush=True)
        break
    time.sleep(.02)
else: raise AssertionError('reader pinned an obsolete delivery')
for path in (p, p.parent, Path('/project/handoffs/foreign.md')):
    try: path.rename(path.with_name('stolen')) if path.exists() else path.write_text('bad')
    except OSError: pass
    else: raise AssertionError('primary can modify child research or handoffs')
"""
            reader = subprocess.Popen(isolation.bubblewrap_command(root, ['/usr/bin/python3','-c',reader_code],
                                      task_workspaces=('work/tasks',)), stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(reader.stdout.readline().strip(), 'reader ready')
                workspace.publish_drafts(root, drafts, workspace.science_fingerprints(root, child_id), [], child_id)
                stdout, stderr = reader.communicate(timeout=5)
                self.assertEqual(reader.returncode, 0, stderr)
                self.assertIn('live delivery visible', stdout)
            finally:
                if reader.poll() is None:
                    reader.kill()
                    reader.communicate()


    def test_verifier_frozen_code_data_and_original_research_are_read_only(self):
        if not shutil.which('bwrap'):
            if live_enabled():
                self.fail('Bubblewrap missing during enabled live acceptance')
            self.skipTest('Bubblewrap missing; verifier boundary unverified')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            task_id = 'task-' + 'c' * 32
            rel = workspace.task_directory(task_id)
            inputs = rel + '/inputs'
            (root / inputs / 'initial').mkdir(parents=True)
            for name in ('method.py', 'data.csv', 'PACKET.md'):
                (root / inputs / 'initial' / name).write_text('frozen evidence')
            (root / rel / 'CHECK.md').write_text('# Accepted objection')
            (root / 'outputs/original.py').write_text('protected original')
            drafts = root / '.research_pipeline/verifier-drafts'
            drafts.mkdir()
            script = f"""
from pathlib import Path
for target in ('/project/{inputs}/initial/method.py', '/project/{inputs}/initial/data.csv',
               '/project/{inputs}/initial/PACKET.md', '/project/{rel}/CHECK.md',
               '/project/outputs/original.py', '/project/work/protected.md'):
    p = Path(target)
    for action in (lambda: p.write_text('changed'), lambda: p.unlink(),
                   lambda: p.rename(p.with_name('stolen'))):
        try: action()
        except OSError: pass
        else: raise AssertionError('verification evidence writable: ' + target)
for p in (Path('/project/{inputs}/initial/new.py'), Path('/project/{inputs}/new.csv')):
    try: p.write_text('changed')
    except OSError: pass
    else: raise AssertionError('frozen input creation allowed')
own = Path('/project/{rel}/independent.py')
own.write_text('print(42)')
import subprocess
assert subprocess.check_output(['/usr/bin/python3', str(own)]).strip() == b'42'
p = Path('/run/research-drafts/{rel}/REEXAMINATION.md')
p.parent.mkdir(parents=True)
p.write_text('# Independent re-examination')
"""
            command = isolation.bubblewrap_command(root, ['/usr/bin/python3', '-c', script],
                task_id=task_id, frozen_inputs=(inputs,), drafts=drafts)
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            if result.returncode and any(t in result.stderr for t in ('Operation not permitted', 'No permissions', 'namespace')):
                if live_enabled():
                    self.fail('Bubblewrap verifier namespaces unavailable: ' + result.stderr)
                self.skipTest('Bubblewrap verifier namespaces unavailable: ' + result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            protected = (rel + '/CHECK.md',)
            workspace.publish_drafts(root, drafts, workspace.science_fingerprints(root, task_id), [],
                                     task_id, protected)
            self.assertEqual((root / rel / 'CHECK.md').read_text(), '# Accepted objection')
            self.assertTrue((root / rel / 'REEXAMINATION.md').exists())


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

    def tool_config(self, wall):
        from tests.test_tools import tool_fixture
        if not hasattr(self, "tool_prior"):
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            self.tool_prior = Path(temp.name) / "prior"
        prior = self.tool_prior
        if not prior.exists():
            path = tool_fixture(prior / "work/tools/sum")
            (path.parent / "method.py").write_text(
                "from pathlib import Path\nimport subprocess,sys,time\n"
                "if 'fail' in sys.argv:\n Path('partial.csv').write_text('partial result'); raise RuntimeError('runtime failure')\n"
                f"if 'child' in sys.argv:\n subprocess.Popen(['/usr/bin/python3','-c',{self.CHILD!r}], start_new_session=True); time.sleep(.2)\n"
                "if 'wait' in sys.argv: time.sleep(30)\n"
                "if 'verbose' in sys.argv: print('x'*20000)\n"
                "print(sum(i*i for i in range(10)))\n")
        workspace.atomic_text(self.root / references.REGISTRY,
                              json.dumps({"version": 1, "references": {"prior": str(prior)}}))
        config = isolation.Config(wall_seconds=wall, deadline=time.monotonic() + wall,
                                  memory_mib=128, max_tasks=32)
        session = self.root / ".research_pipeline" / uuid.uuid4().hex
        session.mkdir()
        config.drafts, config.control, config.response = (session / n for n in ("drafts", "control", "response"))
        for directory in (config.drafts, config.control, config.response):
            directory.mkdir()
        references.configure(config, self.root, session, workspace.Intake(self.root, "", "", [], {}))
        tools.configure(config, self.root, session, session.name)
        state = {"run_id": uuid.uuid4().hex, "activation_id": session.name,
                 "ownership_nonce": uuid.uuid4().hex, "limits": config.limits()}
        manager = jobs.JobManager(self.root, state, lambda: None)
        manager.configure(config, session, state)
        config.on_poll = lambda: manager.poll()
        return config, prior

    TOOL_SETUP = """
from pathlib import Path
import json, subprocess
helper = ['/usr/bin/python3', '/run/research-tools.py']
def call(*args, ok=True):
    p = subprocess.run(helper + list(args), capture_output=True, text=True)
    assert (p.returncode == 0) == ok, p.stdout + p.stderr
    return p
call('stage','--source','prior','work/tools/sum/tool.json','--name','sum')
use = Path('/run/research-drafts/work/tools/sum/USE.md')
use.parent.mkdir(parents=True, exist_ok=True)
use.write_text('# Intended use\\nFinite standard-library sums only; elementary check, no scientific endorsement.')
rel = 'work/tools/sum/tool.json'
assessment = 'work/tools/sum/USE.md'
call('register',rel,'--assessment',assessment)
"""

    def test_actual_tool_registration_computation_dependency_and_runtime_failures(self):
        config, prior = self.tool_config(8)
        before = {str(p): p.read_bytes() for p in prior.rglob("*") if p.is_file()}
        script = self.TOOL_SETUP + """
for p in (Path('/run/research-tools.py'), Path('/run/research-tools.json')):
    try: p.write_text('changed')
    except OSError: pass
    else: raise AssertionError('tool authority writable')
assert json.loads(call('run',rel).stdout)['stdout'].strip() == '285'
verbose = json.loads(call('run',rel,'--','verbose').stdout)
assert verbose['stdout_clipped'] and len(verbose['stdout']) == 8192
failed = json.loads(call('run',rel,'--','fail',ok=False).stdout)
assert failed['outcome'] == 'failed'
assert Path('/project/work/tools/sum/partial.csv').read_text() == 'partial result'
call('stage','--source','prior','work/tools/sum/tool.json','--name','failed')
p = Path('/project/work/tools/failed/tool.json')
d = json.loads(p.read_text()); d['origin'] = 'agent'; d['checks'][0]['argv'] = ['missing-executable']
p.write_text(json.dumps(d))
use = Path('/run/research-drafts/work/tools/failed/USE.md'); use.parent.mkdir(parents=True)
use.write_text('# Intended use\\nExercise a dependency failure honestly.')
call('register','work/tools/failed/tool.json','--assessment','work/tools/failed/USE.md',ok=False)
record = Path('/run/research-drafts/work/tools/failed/VALIDATION.md').read_text()
assert 'FileNotFoundError' in record
d['checks'][0]['argv'] = ['python3','check.py']; p.write_text(json.dumps(d))
Path('/project/work/tools/failed/check.py').write_text('import unavailable_research_dependency')
call('register','work/tools/failed/tool.json','--assessment','work/tools/failed/USE.md',ok=False)
assert 'ModuleNotFoundError' in Path('/run/research-drafts/work/tools/failed/VALIDATION.md').read_text()
Path('/project/work/tools/failed/check.py').write_text('assert 2 + 2 == 4')
call('register','work/tools/failed/tool.json','--assessment','work/tools/failed/USE.md')
assert json.loads(call('run','work/tools/failed/tool.json').stdout)['stdout'].strip() == '285'
call('stage','--local','work/tasks/foreign/tool.json','--name','bad',ok=False)
call('stage','--source','prior','../private','--name','bad',ok=False)
assert len(json.loads(call('list').stdout)['tools']) == 2
call('run',rel,'--','child')
print('tool checks, reuse, dependency/runtime failures passed', flush=True)
"""
        output = bytearray()
        result = isolation.run_isolated(config, self.root, job_driver(config, ["/usr/bin/python3", "-c", script]),
                                        on_event=lambda channel, data: output.extend(data))
        self.assertTrue(result.cleanup_ok, output.decode(errors="replace"))
        self.assertEqual(result.returncode, 0, output.decode(errors="replace"))
        self.assertEqual(before, {str(p): p.read_bytes() for p in prior.rglob("*") if p.is_file()})
        self.assert_child_stopped()

    def test_tool_descendants_stop_with_timeout_and_whole_service_pause(self):
        for reason in ("timeout", "pause"):
            with self.subTest(reason=reason):
                (self.root / "work/heartbeat").unlink(missing_ok=True)
                # New working-copy name is needed because staging never overwrites.
                config, _ = self.tool_config(3)
                setup = self.TOOL_SETUP.replace("'sum'", repr(reason)).replace(
                    "work/tools/sum/", f"work/tools/{reason}/")
                setup = setup.replace(f"'prior','work/tools/{reason}/tool.json'",
                                      "'prior','work/tools/sum/tool.json'")
                script = setup + "\ncall('run',rel,'--','child','wait')\n"
                output = bytearray()
                began = time.monotonic()
                def poll():
                    config.on_poll()
                    return "pause" if reason == "pause" and time.monotonic() - began > 1.5 else None
                result = isolation.run_isolated(config, self.root, job_driver(config, ["/usr/bin/python3", "-c", script]),
                    poll=poll,
                    on_event=lambda channel, data: output.extend(data))
                self.assertTrue(result.cleanup_ok, output.decode(errors="replace"))
                if reason == "timeout":
                    self.assertTrue(result.timed_out)
                else:
                    self.assertEqual(result.requested_stop, "pause")
                self.assert_child_stopped()

    def test_native_code_mode_runtime_with_enforced_task_slot(self):
        binary = native_codex(self)
        config = isolation.Config(codex=binary, wall_seconds=12,
                                  memory_mib=1024, max_tasks=64,
                                  deadline=time.monotonic() + 12)
        # Empty private home: the probe creates no research session or inference.
        home = self.root / '.research_pipeline/runtime-home'
        home.mkdir()
        output = bytearray()
        result = isolation.run_isolated(
            config, self.root, ['/usr/bin/python3', '-c', CODEX_RUNTIME_PROBE],
            auth_home=home, on_event=lambda channel, data: output.extend(data))
        self.assertTrue(result.cleanup_ok, output.decode(errors='replace'))
        self.assertEqual(result.returncode, 0, output.decode(errors='replace'))
        self.assertIn(b'code-mode runtime check passed', output)

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


    def test_schema3_cli_pause_stops_all_roles_and_detached_compute(self):
        """Real owner, helper, services and CLI pause; explicit non-model backend."""
        # Unlike the paid gate these workers supply engineering fixture artifacts.
        # Only backend identity/auth/command construction are substituted.
        runner = r"""
from contextlib import contextmanager
from pathlib import Path
import sys
from unittest.mock import patch
from tests.test_collaboration import ASSIGNMENT, handoff
from tests.test_verification import PACKET
from research_pipeline import cli, codex, workspace

WORKER = r'''
from pathlib import Path
import json, subprocess, time
root, task_id, handoff_text, assignment, packet = INPUTS
own = Path('/project') / root
heartbeat = str(own / 'heartbeat')
child = "from pathlib import Path; import time; p=Path(%r);\nwhile True: p.write_text(str(time.monotonic())); time.sleep(.03)" % heartbeat
subprocess.Popen(['/usr/bin/python3', '-c', child], start_new_session=True)
drafts = Path('/run/research-drafts')
for rel, text in ((f'handoffs/{task_id}.md', handoff_text),
                  (f'{root}/PLAN.md', '# Engineering fixture saved progress')):
    p = drafts / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
(own / 'reference.csv').write_text('x,value\n1,2\n')
if task_id == 'primary':
    (own / 'method.py').write_text('print(2 - 1.9)')
    for rel, text in (('work/ASSIGNMENT.md', assignment), ('work/PACKET.md', packet)):
        p = drafts / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for operation, rel in (('--delegate', 'work/ASSIGNMENT.md'), ('--verify', 'work/PACKET.md')):
        subprocess.run(['/usr/bin/python3', '/run/research-checkpoint-helper.py', operation, rel], check=True)
print('all fixture work saved', flush=True)
while not Path('/run/research-control/request.json').exists(): time.sleep(.02)
subprocess.run(['/usr/bin/python3', '/run/research-checkpoint-helper.py'], check=True)
'''

def command(config):
    root = workspace.task_directory(config.task_id)
    script = 'INPUTS = ' + repr((root, config.task_id,
        handoff(config.task_id, root + '/reference.csv'), ASSIGNMENT, PACKET)) + '\n' + WORKER
    return ['/usr/bin/python3', '-c', script]

@contextmanager
def auth(project):
    yield None

with patch.object(codex, 'verify_backend', return_value={'version': 'engineering worker'}), \
     patch.object(codex, 'private_auth', auth), patch.object(codex, 'build_command', side_effect=command):
    raise SystemExit(cli.main(['start', sys.argv[1], '--max-agents', '3', '--wall-seconds', '120',
                              '--memory-mib', '768', '--max-tasks', '96']))
"""
        # Start requires a fresh scientific project, unlike the isolation probe fixture.
        project = self.root / 'investigation'
        (project / 'starting_evidence').mkdir(parents=True)
        (project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Engineering pause fixture.')
        end = time.monotonic() + 100
        work_end = end - 25  # Retain time to stop every unit after a failed assertion.
        owner = None
        units = set()
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                owner = subprocess.Popen([sys.executable, '-c', runner, str(project)], stdout=out, stderr=err)
                while time.monotonic() < work_end:
                    path = project / '.research_pipeline/run.json'
                    if path.exists():
                        state = json.loads(path.read_text())
                        for task in state['tasks'].values():
                            activation = task.get('activation') or {}
                            for key, flag in (('service', 'service_attempted'), ('probe_service', 'probe_attempted')):
                                if activation.get(flag):
                                    units.add(activation[key])
                        if len(state['tasks']) == 3 and all(
                                (project / t['workspace'] / 'heartbeat').exists() for t in state['tasks'].values()):
                            break
                    if owner.poll() is not None:
                        err.seek(0)
                        self.fail('Engineering owner exited before three-role pause: ' + err.read().decode())
                    time.sleep(.05)
                else:
                    self.fail('Three actual role services did not start before deadline')
                self.assertEqual({t['role'] for t in state['tasks'].values()}, {'primary', 'researcher', 'verifier'})
                pause = subprocess.run([sys.executable, '-m', 'research_pipeline', 'pause', str(project)],
                                       capture_output=True, text=True, timeout=max(.001, work_end-time.monotonic()))
                self.assertEqual(pause.returncode, 0, pause.stdout + pause.stderr)
                self.assertEqual(owner.wait(timeout=max(.001, work_end-time.monotonic())), 0)
                state = json.loads(path.read_text())
                self.assertEqual(state['state'], 'paused')
                self.assertTrue(state['cleanup_ok'])
                self.assertEqual(len(state['sessions']), 3, 'Pause must prevent successors')
                for task in state['tasks'].values():
                    self.assertTrue(task.get('checkpoint'), task.get('checkpoint_error'))
                    activation = task['activation']
                    session = project / '.research_pipeline/sessions' / activation['activation_id']
                    self.assertTrue(workspace.read_control(session / 'control/ack.json')['accepted'])
                before = [(project / t['workspace'] / 'heartbeat').read_bytes() for t in state['tasks'].values()]
                time.sleep(.15)
                self.assertEqual(before, [(project / t['workspace'] / 'heartbeat').read_bytes() for t in state['tasks'].values()])
                for unit in units:
                    props = isolation.service_properties(unit, deadline=end)
                    self.assertTrue(props.get('LoadState') == 'not-found' or props.get('ActiveState') in ('inactive', 'failed'), props)
                with workspace.acquire_project_lock(project):
                    pass  # Successful pause releases the real foreground lock.
            finally:
                if owner and owner.poll() is None:
                    owner.kill()
                    owner.wait(timeout=max(.001, min(5, end-time.monotonic())))
                path = project / '.research_pipeline/run.json'
                if path.exists():
                    state = json.loads(path.read_text())
                    for entry in [*state.get('sessions', []), *(t.get('activation') or {} for t in state.get('tasks', {}).values())]:
                        for key, flag in (('service', 'service_attempted'), ('probe_service', 'probe_attempted')):
                            if entry.get(flag):
                                units.add(entry[key])
                unclean = [unit for unit in units if not isolation.stop_service(unit, deadline=end)]
                self.assertFalse(unclean, 'Unconfirmed engineering fixture cleanup: ' + ', '.join(unclean))

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
