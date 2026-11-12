"""Opt-in production-boundary validation. Enabled missing prerequisites FAIL.

No M1–M5 gate is enabled. Uses public deterministic sums and short engineering
expiry/survival exercises, including minimal native inference for actual inventory.
"""
import asyncio
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from tests import use_checkout
use_checkout()
from research_pipeline import collaboration, isolation, jobs, workspace


def reserve_validation_output(destination):
    """Reserve private evidence storage without touching earlier invocations."""
    if not destination:
        raise ValueError('Enabled V0-L1 validation requires RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR')
    output = Path(destination).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError(f'Output and ancestors must not be symlinks: {output}')
    try:
        try:
            output.mkdir(parents=True, mode=0o700)
        except FileExistsError:
            if not output.is_dir():
                raise ValueError(f'Output must be a directory: {output}')
            output = Path(tempfile.mkdtemp(prefix=output.name + '-', dir=output.parent))
    except OSError as exc:
        raise ValueError(f'Cannot reserve V0-L1 output beside {output}; use a writable directory parent: {exc}') from exc
    return output


class ValidationOutputTests(unittest.TestCase):
    def test_repeated_destination_retains_original_private_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            requested = Path(root) / 'validation'
            first = reserve_validation_output(requested)
            self.assertEqual(first, requested)
            (first/'receipt.json').write_text('original receipt')
            (first/'sentinel').write_text('original evidence')
            second = reserve_validation_output(requested)
            third = reserve_validation_output(requested)
            self.assertEqual(len({first, second, third}), 3)
            for output in (first, second, third):
                self.assertEqual(output.parent, requested.parent)
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual((first/'receipt.json').read_text(), 'original receipt')
            self.assertEqual((first/'sentinel').read_text(), 'original evidence')
            self.assertFalse(list(second.iterdir()))
            self.assertFalse(list(third.iterdir()))

    def test_files_symlinks_and_unusable_parents_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            file = root/'file'
            file.write_text('preserve')
            directory = root/'directory'
            directory.mkdir()
            (root/'link').symlink_to(directory, target_is_directory=True)
            (root/'dangling').symlink_to(root/'absent')
            for destination in (None, file, file/'child', root/'link',
                                root/'link'/'child', root/'dangling'):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    reserve_validation_output(destination)
            self.assertEqual(file.read_text(), 'preserve')
            self.assertFalse(list(directory.iterdir()))

    def test_preflight_failure_retains_separate_failed_receipts(self):
        with tempfile.TemporaryDirectory() as root:
            requested = Path(root)/'validation'
            reports = []
            # Call the fixture method directly: no native services or inference
            # run, and this regression remains active with the paid gate disabled.
            fixture = NativeL1Tests('test_production_context_job_survival_timeout_and_boundary')
            with patch.dict(os.environ, {'RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR': str(requested)}):
                for attempt in range(2):
                    logged = io.StringIO()
                    with patch.object(isolation, 'preflight', side_effect=isolation.RuntimeUnavailable(f'fixture bus failure {attempt}')), \
                            redirect_stdout(logged), self.assertRaisesRegex(isolation.RuntimeUnavailable, f'fixture bus failure {attempt}'):
                        fixture.test_production_context_job_survival_timeout_and_boundary()
                    output = Path(logged.getvalue().strip().split('V0-L1 output: ', 1)[1])
                    receipt = json.loads((output/'receipt.json').read_text())
                    self.assertEqual(receipt['requested_output_dir'], str(requested))
                    self.assertEqual(receipt['output_dir'], str(output))
                    self.assertEqual(receipt['outcome'], 'failed')
                    self.assertIn(f'fixture bus failure {attempt}', receipt['error'])
                    self.assertEqual(receipt['commands'], [])
                    self.assertEqual(receipt['evidence'], {})
                    reports.append(output/'receipt.json')
            self.assertNotEqual(*reports)
            self.assertIn('fixture bus failure 0', reports[0].read_text())


@unittest.skipUnless(os.environ.get('RESEARCH_PIPELINE_V0_L1_NATIVE') == '1', 'V0-L1 production validation opt-in disabled')
class NativeL1Tests(unittest.TestCase):
    def test_production_context_job_survival_timeout_and_boundary(self):
        destination = os.environ.get('RESEARCH_PIPELINE_V0_L1_OUTPUT_DIR')
        output = reserve_validation_output(destination)
        print(f'V0-L1 output: {output}', flush=True)
        receipt = {'validation': 'V0-L1 production isolation + minimal native inference + public process fixtures',
                   'requested_output_dir': str(Path(destination).absolute()), 'output_dir': str(output),
                   'outcome': 'failed', 'commands': [], 'evidence': {}, 'limitations': ['Does not establish V0-L2–L6 or M5 acceptance.']}
        runtime = None

        async def exercise():
            nonlocal runtime
            # Fail exactly here when the Writer has no authorized host bus. No
            # replacement bus, native direct-Bubblewrap route or skip is allowed.
            isolation.preflight()
            project = output / 'project'
            (project/'starting_evidence').mkdir(parents=True)
            questions = project/'starting_evidence/RESEARCH_QUESTIONS.md'
            questions.write_text('# Public boundary validation\nInspect a finite sum and report it as preliminary.\n')
            (project/'AGENTS.md').write_text('Use only public engineering fixtures. Never infer scientific completion.')
            before = workspace.fingerprints(project)
            with workspace.acquire_project_lock(project):
                runtime = collaboration.Coordinator.initialize(project, isolation.Config())
                await runtime.start()
                receipt['evidence']['allocation'] = runtime.state['allocation']

                async def attach(task_id, successor=False):
                    context_id = await (runtime.successor(task_id) if successor else runtime.attach(task_id))
                    ctx = runtime.contexts[context_id]
                    ctx['record']['state'] = 'turn_running'
                    runtime.save()
                    # The request's actual backend declarations, not model prose,
                    # determine native inventory. Scientific job admission is gated.
                    turn = await asyncio.wait_for(runtime.clients[context_id].turn(
                        'Production inventory validation only. Call research_jobs job_status and control(check), save a short scoped handoff draft with write_draft, then end the turn. Do not run a computation or claim COMPLETE.'), 90)
                    self.assertEqual(turn['status'], 'completed', turn)
                    self.assertTrue(runtime.validate_inventory(context_id))
                    # This lower-level L1 fixture explicitly admits work only
                    # after the same native measurement required by L2 intake.
                    self.assertEqual(ctx['record']['measurement']['status'], 'measured')
                    self.assertFalse(ctx['record'].get('threshold_observation'))
                    runtime.state['tasks'][task_id]['operational_state'] = 'working'
                    ctx['record']['state'] = 'attached'
                    runtime.save()
                    return context_id

                async def call(context_id, tool, **arguments):
                    client = runtime.clients[context_id]
                    result = await client.request('mcpServer/tool/call', {'threadId': client.thread_id,
                            'server': 'research_jobs', 'tool': tool, 'arguments': arguments}, timeout=30)
                    receipt['commands'].append({'context_id': context_id, 'tool': tool, 'arguments': arguments, 'result': result})
                    # Installed RPC returns the MCP CallToolResult directly.
                    self.assertFalse(result.get('isError'), result)
                    if isinstance(result.get('structuredContent'), dict):
                        value = result['structuredContent']
                        return value.get('result', value)
                    texts = [c['text'] for c in result.get('content', []) if c.get('type') == 'text']
                    self.assertTrue(texts, result)
                    return json.loads('\n'.join(texts))

                async def ready(path, seconds=8):
                    until = time.monotonic() + seconds
                    while not path.exists():
                        self.assertLess(time.monotonic(), until, f'Process readiness missing: {path}')
                        await asyncio.sleep(.02)

                first = await attach('primary')
                # Real public computation survives complete original service closure.
                script = """from pathlib import Path
import time
Path('ready').write_text('started')
while not Path('release-survivor').exists():
    time.sleep(.02)
Path('sum.txt').write_text(str(sum(i*i for i in range(10))))
print('sum=285', flush=True)
"""
                job = await call(first, 'job_run', argv=['/usr/bin/python3', '-u', '-c', script], cwd='/project/work', runtime_seconds=180)
                self.assertEqual(job['state'], 'running', job)
                await ready(project/'work/ready')
                original = {k: job[k] for k in ('job_id','deadline','service','slot','launch_count')}
                handoff = (f'# Public computation handoff\nJob: {job["job_id"]}\n'
                           f'Original deadline: {job["deadline"]}\n'
                           'Next action: inspect and collect this same job after successor coexistence; do not restart it.\n')
                await call(first, 'write_draft', path='handoffs/primary.md', content=handoff)
                self.assertTrue((await runtime.close_context(first))['confirmed'])
                self.assertIn(runtime.state['jobs'][job['job_id']]['state'], jobs.ACTIVE)
                second = await attach('primary', successor=True)
                self.assertNotEqual(runtime.state['contexts'][first]['native_thread_id'], runtime.state['contexts'][second]['native_thread_id'])
                observed = await call(second, 'job_status', job_id=job['job_id'])
                self.assertEqual({k: observed[k] for k in original}, original)
                self.assertEqual(observed['state'], 'running', observed)
                pending_documents = await call(second, 'control', action='documents')
                document = next(doc for doc in pending_documents['documents']
                                if doc['source_id'] == first and doc['path'] == 'handoffs/primary.md')
                consumed_handoff = await call(second, 'control', action='read_document', path=document['document_id'])
                self.assertEqual(consumed_handoff['content'], handoff)
                self.assertFalse((project/'handoffs/primary.md').exists(),
                                 'A live job must not allow canonical draft publication')
                self.assertFalse((project/'work/sum.txt').exists())
                job_service = await isolation.service_properties(job['service']['unit'])
                successor_service = await isolation.service_properties(runtime.state['contexts'][second]['service']['unit'])
                slot = runtime.allocation.slots[job['slot']]
                self.assertEqual(job_service['ActiveState'], 'active')
                self.assertEqual(job_service['SubState'], 'running')
                self.assertEqual(job_service['InvocationID'], job['service']['invocation_id'])
                self.assertEqual(successor_service['ActiveState'], 'active')
                for service in (job_service, successor_service):
                    self.assertTrue(service['ControlGroup'].startswith(slot['cgroup']+'/'))
                coexistence = {'job': job_service, 'successor': successor_service, 'slot': slot,
                               'observed_monotonic': time.monotonic()}
                (project/'work/release-survivor').write_text('successor coexistence verified')
                collected = await call(second, 'job_wait', job_id=job['job_id'])
                self.assertEqual(collected['state'], 'completed', collected)
                self.assertTrue(collected['cleanup_ok'])
                self.assertEqual((project/'work/sum.txt').read_text(), '285')
                receipt['evidence']['survival'] = {
                    'original': original, 'collected': collected, 'contexts': [first, second],
                    'coexistence_before_release': coexistence, 'consumed_handoff': consumed_handoff}

                # Denials occur through the actual adapter, not tool-schema prose.
                ctx = runtime.contexts[second]
                self.assertIn('--clearenv', isolation.bubblewrap_command(project, ['true']))
                denial = await runtime.clients[second].request('mcpServer/tool/call', {'threadId': runtime.clients[second].thread_id,
                    'server': 'research_jobs', 'tool': 'write_draft', 'arguments': {'path': 'starting_evidence/RESEARCH_QUESTIONS.md', 'content': 'forbidden'}})
                self.assertTrue(denial.get('isError'), denial)
                receipt['evidence']['protected_draft_denial'] = denial
                protected = r'''
from pathlib import Path
import os
assert 'OPENAI_API_KEY' not in os.environ
assert 'DBUS_SESSION_BUS_ADDRESS' not in os.environ
assert not Path('/home/researcher/.codex/auth.json').exists()
assert not Path('/run/research-rpc').exists()
assert not Path('/run/research-jobs.json').exists()
assert not list(Path('/project/.research_pipeline').iterdir())
p = Path('/project/starting_evidence/RESEARCH_QUESTIONS.md')
for action in (lambda: p.write_text('bad'), lambda: p.unlink(), lambda: p.rename(p.with_name('bad'))):
    try: action()
    except OSError: pass
    else: raise AssertionError('protected write succeeded')
print('production command boundary passed', flush=True)
'''
                boundary = await call(second, 'job_run', argv=['/usr/bin/python3','-c',protected], cwd='/project/work', runtime_seconds=61)
                boundary = await call(second, 'job_wait', job_id=boundary['job_id'])
                self.assertEqual(boundary['returncode'], 0, boundary)
                self.assertTrue(boundary['cleanup_ok'])
                receipt['evidence']['command_boundary'] = boundary

                # An independent logical agent shares the same parent caps.
                other_id = 'task-' + uuid.uuid4().hex
                other = runtime.add_task(other_id, 'Public independent boundary check', 'primary', role='verifier')
                inputs = project / other['workspace'] / 'inputs'
                inputs.mkdir()
                (inputs/'frozen.py').write_text('assert sum(range(10)) == 45')
                other['frozen_inputs'] = [other['workspace']+'/inputs']
                runtime.save()
                third = await attach(other_id)
                with self.assertRaisesRegex(jobs.JobError, 'cap'):
                    runtime.add_task('task-' + uuid.uuid4().hex, 'excess', 'primary')
                # Command + setsid descendant retain useful partial output. The
                # original context terminates before its immutable short deadline.
                child = "from pathlib import Path; import time; Path('/project/work/descendant-ready').write_text('started'); time.sleep(30); Path('/project/work/escaped').write_text('leaked')"
                expiry_script = f"import subprocess,time; from pathlib import Path; subprocess.Popen(['/usr/bin/python3','-c',{child!r}], start_new_session=True); print('partial timeout output',flush=True); Path('expiry-ready').write_text('started'); time.sleep(30)"
                expiring = await call(second, 'job_run', argv=['/usr/bin/python3','-u','-c',expiry_script], cwd='/project/work', runtime_seconds=5)
                await ready(project/'work/expiry-ready')
                await ready(project/'work/descendant-ready')
                # Foreign status/wait/cancel rejected before any ownership operation.
                for operation in ('job_status','job_wait','job_cancel'):
                    denied = await runtime.clients[third].request('mcpServer/tool/call', {'threadId': runtime.clients[third].thread_id,
                        'server':'research_jobs','tool':operation,'arguments':{'job_id':expiring['job_id']}})
                    self.assertTrue(denied.get('isError'), denied)
                self.assertTrue((await runtime.close_context(second))['confirmed'])
                self.assertLess(time.monotonic(), expiring['deadline'], 'Context did not end before job expiry')
                # Wait on the runtime event, independent of any native context.
                expired = await asyncio.wait_for(runtime.jobs.wait('primary', expiring['job_id']), 15)
                self.assertEqual(expired['state'], 'timed_out', expired)
                self.assertTrue(expired['cleanup_ok'])
                self.assertIn('partial timeout output', expired['stdout'])
                self.assertTrue(isolation.group_empty(expired['service']['cgroup']))
                self.assertIsNone(runtime.state['admission_block'])
                receipt['evidence']['timeout_after_context'] = expired
                scoped_check = f"""from pathlib import Path
for name in ('/project/work/sum.txt', '/project/{other['workspace']}/inputs/frozen.py'):
    try: Path(name).write_text('bad')
    except OSError: pass
    else: raise AssertionError('sibling or frozen write succeeded: '+name)
Path('own-result.txt').write_text('45')
print(sum(range(10)))
"""
                unrelated = await call(third, 'job_run', argv=['/usr/bin/python3','-c',scoped_check], cwd='/project/'+other['workspace'], runtime_seconds=61)
                unrelated = await call(third, 'job_wait', job_id=unrelated['job_id'])
                self.assertEqual(unrelated['returncode'], 0, unrelated)
                self.assertEqual(unrelated['stdout'].strip(), '45')
                receipt['evidence']['unrelated_research'] = unrelated

                fourth = await attach('primary', successor=True)
                for duration in (61, 7200):
                    long_job = await call(fourth, 'job_run', argv=['/usr/bin/python3','-c','import time; time.sleep(30)'], cwd='/project/work', runtime_seconds=duration)
                    self.assertEqual(long_job['runtime_seconds'], duration)
                    self.assertEqual(long_job['deadline'], long_job['admitted_monotonic'] + duration)
                    # Observe actual coexistence beneath the same persistent slice.
                    props = await isolation.service_properties(long_job['service']['unit'])
                    context_owner = runtime.state['contexts'][fourth]['service']
                    slot = runtime.allocation.slots[runtime.state['tasks']['primary']['slot']]
                    self.assertTrue(props['ControlGroup'].startswith(slot['cgroup']+'/'))
                    self.assertTrue(context_owner['cgroup'].startswith(slot['cgroup']+'/'))
                    # Full capacity refuses immediately through the real adapter.
                    denied = await runtime.clients[third].request('mcpServer/tool/call', {'threadId': runtime.clients[third].thread_id,
                        'server':'research_jobs','tool':'job_run','arguments':{'argv':['true'],'cwd':'/project/'+other['workspace'],'runtime_seconds':61}})
                    self.assertTrue(denied.get('isError'), denied)
                    cancelled = await call(fourth, 'job_cancel', job_id=long_job['job_id'])
                    self.assertEqual(cancelled['state'], 'cancelled', cancelled)
                    self.assertTrue(cancelled['cleanup_ok'])
                    receipt['evidence'][f'duration_{duration}'] = {'admitted':long_job,'cancelled':cancelled,'observed_job_service':props,'slot':slot}
                # Real supervisor loss: verify the service identity before issuing
                # the fixture's main-process kill; reconciliation must retain the
                # failure and confirm the whole owned cgroup actually stopped.
                lost = await call(fourth, 'job_run', argv=['/usr/bin/python3','-c',"from pathlib import Path; import time; Path('loss-ready').write_text('started'); time.sleep(30)"], cwd='/project/work', runtime_seconds=61)
                await ready(project/'work/loss-ready')
                current = await isolation.service_properties(lost['service']['unit'])
                self.assertEqual(current['InvocationID'], lost['service']['invocation_id'])
                await isolation.command('systemctl','--user','kill','--kill-who=main','--signal=SIGKILL',lost['service']['unit'])
                failed = await asyncio.wait_for(runtime.jobs.wait('primary', lost['job_id']), 15)
                self.assertEqual(failed['state'], 'failed', failed)
                self.assertTrue(failed['cleanup_ok'])
                self.assertIn('Supervisor lost', failed['reason'])
                receipt['evidence']['supervisor_loss'] = failed
                self.assertEqual(workspace.fingerprints(project), before)
                self.assertFalse((project/'work/escaped').exists())
                receipt['evidence']['contexts'] = runtime.state['contexts']
                receipt['outcome'] = 'passed'

        async def checked_exercise():
            try:
                await exercise()
            finally:
                if runtime:
                    try:
                        receipt['cleanup_ok'] = await runtime.block_and_cleanup('Production validation finished')
                        receipt['cleanup'] = runtime.state.get('cleanup')
                        if not receipt['cleanup_ok']:
                            receipt['outcome'] = 'failed'
                            self.fail('Production validation cleanup unconfirmed; inspect receipt')
                    finally:
                        await runtime.close()

        try:
            asyncio.run(checked_exercise())
        except BaseException as exc:
            receipt['outcome'] = 'failed'
            receipt['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            jobs.atomic(output/'receipt.json', receipt)
