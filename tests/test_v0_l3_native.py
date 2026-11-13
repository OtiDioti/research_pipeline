"""Opt-in L3 production demonstration. Never substitute injected admission quota.

Actual account reads, native context lengths and owned service observations are
separate from labelled clock/threshold observations. Public fixture science only.
"""
import asyncio
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
import uuid

from tests import use_checkout
use_checkout()
from tests.test_v0_l1_native import reserve_validation_output
from research_pipeline import collaboration, isolation, jobs, workspace


@contextmanager
def secondary_turn_barrier(runtime, task_id, ready):
    """Hold fixture dispatch between measured turns; keep the native context owned."""
    original = runtime.native_turn
    parked, release = asyncio.Event(), asyncio.Event()

    async def turn(context_id, *args, **kwargs):
        record = runtime.state['contexts'][context_id]
        if (record['task_id'] == task_id and ready()
                and record.get('measurement', {}).get('status') == 'measured'):
            parked.set()
            await release.wait()
        return await original(context_id, *args, **kwargs)

    runtime.native_turn = turn
    try:
        yield parked
    finally:
        release.set()
        runtime.native_turn = original


@unittest.skipUnless(os.environ.get('RESEARCH_PIPELINE_V0_L3_NATIVE') == '1',
                     'V0-L3 production validation opt-in disabled')
class NativeL3Tests(unittest.TestCase):
    def test_native_primary_quota_stop_and_secondary_warnings(self):
        destination = os.environ.get('RESEARCH_PIPELINE_V0_L3_OUTPUT_DIR')
        if not destination:
            self.fail('Enabled V0-L3 validation requires RESEARCH_PIPELINE_V0_L3_OUTPUT_DIR')
        output = reserve_validation_output(destination)
        print(f'V0-L3 output: {output}', flush=True)
        receipt = {'validation': 'V0-L3 production telemetry/ownership with labelled quota and clock injections',
            'requested_output_dir': str(destination), 'output_dir': str(output),
            'outcome': 'failed', 'scenarios': [], 'commands': [],
            'limitations': ['Clock intervals and cutoff are injected; native admission allowance is never injected.',
                            'No scientific terminal decision, L4/L5/full lifecycle or M5 acceptance.']}

        async def scenario(role):
            barriers = ExitStack()
            entry = {'role': role, 'outcome': 'failed'}
            receipt['scenarios'].append(entry)
            project = output/role
            (project/'starting_evidence').mkdir(parents=True)
            (project/'starting_evidence/RESEARCH_QUESTIONS.md').write_text(
                'Public test: independently derive the composite trapezoidal error for x squared on [0,1]. '
                'Distinguish a mathematical argument from finite numerical evidence. Preliminary science only.')
            (project/'AGENTS.md').write_text('Public engineering fixture. Do not delegate or launch jobs; '
                'the fixture supplies one controlled numerical computation. Save useful reasoning with write_draft '
                'and a valid handoff. Native roles retain scientific judgment; do not claim COMPLETE or scientific STOP.')
            before = workspace.fingerprints(project)
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            async def until(predicate, description, seconds=180):
                async def poll():
                    while True:
                        errors = {k:t['context_error'] for k,t in runtime.state['tasks'].items() if t.get('context_error')}
                        if errors or runtime.state['admission_block']:
                            self.fail(f'{description}: {errors}; {runtime.state["admission_block"]}')
                        result = predicate()
                        if result: return result
                        await asyncio.sleep(.1)
                try:
                    return await asyncio.wait_for(poll(), seconds)
                except asyncio.TimeoutError as exc:
                    raise AssertionError('Operational fixture synchronization failed: '+description) from exc

            def note(task_id, filename):
                task = runtime.state['tasks'][task_id]
                cid = task['context_id']
                if not cid: return None
                path = runtime.contexts[cid]['drafts']/task['workspace']/filename
                return path if path.is_file() and path.stat().st_size > 120 else None

            async def call(cid, tool, **arguments):
                client = runtime.clients[cid]
                result = await client.request('mcpServer/tool/call', {'threadId':client.thread_id,
                    'server':'research_jobs','tool':tool,'arguments':arguments}, timeout=30)
                receipt['commands'].append({'context_id':cid,'tool':tool,'arguments':arguments,'result':result})
                self.assertFalse(result.get('isError'), result)
                value = result.get('structuredContent')
                if isinstance(value, dict): return value.get('result', value)
                return json.loads('\n'.join(c['text'] for c in result.get('content',[]) if c.get('type')=='text'))

            try:
                with workspace.acquire_project_lock(project):
                    runtime.state['tasks']['primary']['objective'] += (
                        ' Save substantial independent analytical work in work/BEFORE.md and a valid handoff. '
                        'On a fresh successor with validated handoff, read immutable artifact versions, continue '
                        'the reasoning and save work/AFTER.md. Inspect the supplied job without duplication. '
                        'Secondary staleness warnings are observations for your judgment, not scientific failure.')
                    await runtime.start()  # actual authorized quota read before thread/inference
                    self.assertFalse(runtime.state['quota'].get('cutoff'))
                    self.assertEqual(runtime.state['quota']['native_observation']['provenance'], 'native')
                    entry['real_preflight'] = deepcopy(runtime.state['quota'])
                    entry['allocation'] = runtime.state['allocation']
                    first = runtime.state['tasks']['primary']['context_id']
                    secondary_id = 'task-'+uuid.uuid4().hex
                    secondary = runtime.add_task(secondary_id,
                        'Independently derive and challenge the public trapezoidal error argument. '
                        'Save substantial reasoning in your workspace/BEFORE.md and a valid scoped handoff. '
                        'If opponent, preserve ## Review history and ## Objections. No computations or assignments.',
                        'primary', role)
                    parked = barriers.enter_context(secondary_turn_barrier(
                        runtime, secondary_id, lambda: note(secondary_id, 'BEFORE.md')))
                    for task_id in ('primary',secondary_id):
                        runtime.turns[task_id] = asyncio.create_task(runtime.run_task(task_id))
                    await until(lambda: note('primary','BEFORE.md'), 'primary public analytical work')
                    await until(lambda: note(secondary_id,'BEFORE.md'), 'independent secondary public work')
                    await until(parked.is_set, 'secondary held between measured native turns')
                    entry['secondary_dispatch_barrier'] = (
                        'Engineering synchronization: secondary context remains owned; its next turn waits '
                        'until primary successor intake. No context telemetry or job deadline is changed.')
                    await until(lambda: all(t['operational_state']=='working' for t in runtime.state['tasks'].values()),
                                'measured native admission')
                    secondary_cid = secondary['context_id']
                    entry['native_before'] = {cid:deepcopy(r.get('native_measurement'))
                        for cid,r in runtime.state['contexts'].items()}
                    job = await call(first,'job_run',argv=['/usr/bin/python3','-u','-c', '''from pathlib import Path
import json, subprocess, sys, time
rows=[]
for n in (4,8,16,32):
    value=(.5+sum((k/n)**2 for k in range(1,n)))/n
    rows.append(dict(n=n,value=value,error=value-1/3))
Path('quadrature.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows),flush=True)
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(7200)'])
Path('descendant.pid').write_text(str(child.pid))
Path('job-ready').write_text('partial numerical fixture output saved; waiting for quota interruption')
while True: time.sleep(.1)
'''],cwd='/project/work',runtime_seconds=7200)
                    self.assertNotIn('error', job, job)
                    await until(lambda: (project/'work/job-ready').exists(), 'controlled computation and descendant readiness', 20)
                    entry['job_before'] = deepcopy(job)
                    self.assertEqual(job['launch_count'], 1)
                    # Controlled clock injection never advances the job deadline clock.
                    clock = runtime.state['contexts'][secondary_cid]['staleness']
                    entry['injected_clock_warnings'] = deepcopy(runtime.check_staleness(
                        clock['changed_monotonic']+2700, 'injected-native-demo-clock'))
                    self.assertTrue(entry['injected_clock_warnings'])
                    await runtime.deliver_staleness()
                    entry['delivery_before_rollover'] = deepcopy(runtime.state['pending_staleness'])
                    # The secondary stays between measured turns across rollover.
                    # Emit a second labelled warning at successor intake.
                    original_documents = runtime.successor_documents
                    def documents(task_id):
                        if task_id == 'primary' and runtime.state['tasks'][task_id].get('last_context_id'):
                            clock = runtime.state['contexts'][secondary_cid]['staleness']
                            runtime.check_staleness(clock['changed_monotonic']+5400, 'injected-successor-intake-clock')
                            entry['successor_intake_warnings'] = deepcopy(runtime.state['pending_staleness'])
                        return original_documents(task_id)
                    runtime.successor_documents = documents
                    record = runtime.state['contexts'][first]
                    injected = {'threadId':record['native_thread_id'],
                        'turnId':runtime.clients[first].active_turn_id or record['native_measurement']['turn_id'],
                        'tokenUsage':deepcopy(record['telemetry'])}
                    injected['tokenUsage']['last']['totalTokens'] = 122000
                    injected['tokenUsage']['modelContextWindow'] = 212000
                    entry['injected_rollover'] = runtime.observe_context(first,injected,'injected-native-demo-55-percent')
                    task = runtime.state['tasks']['primary']
                    successor = await until(lambda: task['context_id'] if task['context_id'] and task['context_id']!=first else None,
                        'fresh primary attachment')
                    # Intake (180s operational bound) precedes ordinary science.
                    # Allow another 180s for the fixture artifact, without imposing
                    # a scientific turn/session lifetime on the runtime.
                    after = await until(lambda: note('primary','AFTER.md'),
                        'native continuation and warning intake', seconds=360)
                    self.assertIn(secondary_cid, entry['successor_intake_warnings'])
                    barriers.close()
                    self.assertTrue(record['cleanup_ok'])
                    self.assertNotEqual(record['native_thread_id'],runtime.state['contexts'][successor]['native_thread_id'])
                    self.assertEqual(secondary['context_id'],secondary_cid)
                    actual = await runtime.jobs.inspect('primary',job['job_id'])
                    self.assertEqual(actual['state'],'running',actual)
                    for key in ('job_id','service','deadline','runtime_seconds','slot','launch_count'):
                        self.assertEqual(actual[key],job[key])
                    entry['job_after_rollover'] = actual
                    entry['job_live_service'] = await isolation.service_properties(actual['service']['unit'])
                    entry['native_continuation'] = {'path':str(after),'text':after.read_text()}
                    entry['native_before_cutoff'] = deepcopy(runtime.state['quota']['native_observation'])
                    primary_cid = runtime.quota_transport
                    # Native preflight remains a prerequisite; injection cannot admit a run.
                    entry['injected_cutoff'] = runtime.observe_quota(primary_cid,
                        {'rateLimits':{'limitId':'injected-demo','secondary':{
                            'windowDurationMins':10080,'usedPercent':85}}},
                        provenance='injected-native-demo-cutoff')
                    self.assertTrue(runtime.state['admission_block'])
                    self.assertTrue(await runtime.shutdown_task, runtime.state)
                    self.assertEqual(runtime.state['state'],'quota_stopped')
                    self.assertTrue(runtime.state['cleanup_ok'])
                    self.assertTrue(runtime.state['finalization_ok'])
                    self.assertTrue((project/'STOP_ACK').exists())
                    self.assertFalse((project/'COMPLETE').exists())
                    self.assertTrue((project/'work/quadrature.json').exists())
                    self.assertEqual(workspace.fingerprints(project),before)
                    entry['outcome'] = 'passed'
            except BaseException as exc:
                entry['error'] = f'{type(exc).__name__}: {exc}'
                raise
            finally:
                barriers.close()  # release dispatch on every failure before owned cleanup
                try:
                    entry['cleanup_ok'] = await runtime.block_and_cleanup('Explicit engineering fixture cleanup')
                    entry['contexts'] = runtime.state['contexts']
                    entry['tasks'] = runtime.state['tasks']
                    entry['jobs'] = runtime.state['jobs']
                    entry['quota'] = runtime.state['quota']
                    entry['cleanup'] = runtime.state.get('cleanup')
                    self.assertTrue(entry['cleanup_ok'],'Production cleanup/finalization unconfirmed')
                finally:
                    await runtime.close()
                    jobs.atomic(output/'receipt.json',receipt)

        async def exercise():
            isolation.preflight()  # existing authorized user bus only; no fallback
            for role in ('researcher','opponent'):
                await scenario(role)
        try:
            asyncio.run(exercise())
            receipt['outcome'] = 'passed'
        except BaseException as exc:
            receipt['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            jobs.atomic(output/'receipt.json',receipt)


class NativeReceiptTests(unittest.TestCase):
    def test_enabled_missing_prerequisite_fails_and_preserves_unique_receipts(self):
        from contextlib import redirect_stdout
        import io
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            fixture = NativeL3Tests('test_native_primary_quota_stop_and_secondary_warnings')
            with patch.dict(os.environ, {'RESEARCH_PIPELINE_V0_L3_OUTPUT_DIR':str(Path(temp)/'requested')}):
                for attempt in range(2):
                    output = io.StringIO()
                    with redirect_stdout(output), patch.object(isolation,'preflight',side_effect=
                            isolation.RuntimeUnavailable(f'authorized bus absent {attempt}')):
                        with self.assertRaisesRegex(isolation.RuntimeUnavailable,'authorized bus absent'):
                            fixture.test_native_primary_quota_stop_and_secondary_warnings()
                    path = Path(output.getvalue().split('V0-L3 output: ')[1].strip())/'receipt.json'
                    paths.append(path)
                    report = json.loads(path.read_text())
                    self.assertEqual(report['outcome'],'failed')
                    self.assertIn(str(attempt),report['error'])
                    self.assertFalse(report['scenarios'])
                    self.assertFalse(report['commands'])
            self.assertNotEqual(*paths)
