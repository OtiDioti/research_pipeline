"""Opt-in production L2 continuity. Native science and injected occupancy are separate.

Each invocation reserves private evidence; enabled missing host prerequisites FAIL.
Role scenarios are sequential, with the unchanged two-agent/one-job shared grant.
The fixture supplies a reproducible public computation through the native MCP path;
native researchers must derive and interpret it without prescribed conclusions.
"""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
import uuid

from tests import use_checkout
use_checkout()
from tests.test_v0_l1_native import reserve_validation_output
from research_pipeline import collaboration, context_usage, isolation, jobs, workspace


@unittest.skipUnless(os.environ.get('RESEARCH_PIPELINE_V0_L2_NATIVE') == '1',
                     'V0-L2 production validation opt-in disabled')
class NativeL2Tests(unittest.TestCase):
    def test_native_science_continues_all_roles_and_admitted_computation(self):
        destination = os.environ.get('RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR')
        if not destination:
            self.fail('Enabled V0-L2 validation requires RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR')
        output = reserve_validation_output(destination)
        print(f'V0-L2 output: {output}', flush=True)
        receipt = {'validation': 'V0-L2 native science with labelled injected occupancy',
                   'requested_output_dir': str(destination), 'output_dir': str(output),
                   'outcome': 'failed', 'scenarios': [], 'commands': [],
                   'limitations': ['Threshold crossings are injected, not filled native windows.',
                                  'No L3 weekly reserve, L4 decision protocol, L5 recovery or M5 acceptance.']}

        async def scenario(role):
            entry = {'role': role, 'outcome': 'failed'}
            receipt['scenarios'].append(entry)
            project = output / role
            (project/'starting_evidence').mkdir(parents=True)
            (project/'starting_evidence/RESEARCH_QUESTIONS.md').write_text(
                'Public problem: independently derive the composite trapezoidal error for f(x)=x^2 '
                'on [0,1]. Check the n dependence and distinguish finite numerical observations '
                'from an analytical proof. Explain assumptions and limitations. Preliminary science only.')
            (project/'AGENTS.md').write_text('Public test science only; no external publication. '
                'Do not delegate or launch any computation: the engineering fixture supplies one '
                'controlled numerical job to primary. Use draft tools for reasoning and job tools '
                'to inspect/wait/collect existing work. No scientific COMPLETE or STOP authority.')
            before = workspace.fingerprints(project)
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            entry['project'] = str(project)
            async def until(predicate, description, seconds=180):
                async def poll():
                    while True:
                        errors = {k:t['context_error'] for k,t in runtime.state['tasks'].items() if t.get('context_error')}
                        if errors:
                            self.fail(f'{description}: {errors}')
                        result = predicate()
                        if result:
                            return result
                        await asyncio.sleep(.1)
                try:
                    return await asyncio.wait_for(poll(), seconds)
                except asyncio.TimeoutError as exc:
                    raise AssertionError('Operational fixture synchronization failed: '+description) from exc

            def draft(task_id, filename):
                task = runtime.state['tasks'][task_id]
                cid = task['context_id']
                if not cid: return None
                path = runtime.contexts[cid]['drafts']/task['workspace']/filename
                return path if path.is_file() and path.stat().st_size > 120 else None

            async def call(cid, tool, **arguments):
                client = runtime.clients[cid]
                result = await client.request('mcpServer/tool/call', {'threadId': client.thread_id,
                    'server':'research_jobs','tool':tool,'arguments':arguments}, timeout=30)
                receipt['commands'].append({'context_id':cid,'tool':tool,'arguments':arguments,'result':result})
                self.assertFalse(result.get('isError'), result)
                structured = result.get('structuredContent')
                if isinstance(structured,dict): return structured.get('result',structured)
                return json.loads('\n'.join(c['text'] for c in result.get('content',[]) if c.get('type')=='text'))

            try:
                with workspace.acquire_project_lock(project):
                    await runtime.start()
                    entry['allocation'] = runtime.state['allocation']
                    self.assertEqual(runtime.state['limits'], {'memory_mib':2048,'swap_bytes':0,
                        'max_tasks':128,'max_agents':2,'max_jobs':1})
                    other_id = 'task-'+uuid.uuid4().hex
                    target_id = 'primary' if role == 'primary' else other_id
                    unrelated_id = other_id if role == 'primary' else 'primary'
                    runtime.add_task(other_id, 'Independent public trapezoidal analysis.', 'primary',
                                     role='researcher' if role=='primary' else role)
                    for task_id, task in runtime.state['tasks'].items():
                        task['objective'] = (
                            'Derive the composite trapezoidal error for x^2 on [0,1] independently. '
                            'Use write_draft to save substantial analytical reasoning in your workspace/BEFORE.md '
                            'and a valid handoff with exact metadata. Do not launch jobs or delegate. '
                            'If an existing owned job appears, inspect and wait for it; do not duplicate it. '
                            'On receiving a validated predecessor handoff in a fresh context, read its exact '
                            'artifact versions using control(read_document), continue the reasoning and '
                            'save substantial further analysis in workspace/AFTER.md. '
                            'For primary, collect and interpret the supplied numerical job stdout before AFTER.md. '
                            'For the opponent, document independent objections/limitations in BEFORE.md and '
                            '## Review history and ## Objections in the handoff; revisit them in AFTER.md. '
                            'For an unrelated task without a predecessor, continue with a useful independent '
                            'limiting-case analysis in workspace/CONTINUING.md. Never infer scientific completion.')
                        if task_id == unrelated_id:
                            task['objective'] += (
                                ' Continue working alongside the other logical task. After control(check) '
                                'shows that the OTHER task has last_context_id and a fresh context_id, '
                                'save a further substantive independent check in workspace/DURING.md. '
                                'Do not write DURING.md before observing that successor.')
                        runtime.turns[task_id] = asyncio.create_task(runtime.run_task(task_id))
                    before_note = await until(lambda: draft(target_id,'BEFORE.md'), 'native analytical work before rollover')
                    entry['before_science'] = {'path':str(before_note),'text':before_note.read_text()}
                    await until(lambda: draft(unrelated_id,'BEFORE.md'), 'independent native analytical work')
                    await until(lambda: all(t['operational_state']=='working' for t in runtime.state['tasks'].values()),
                                'measured scientific admission')
                    task = runtime.state['tasks'][target_id]
                    first = task['context_id']
                    first_record = runtime.state['contexts'][first]
                    self.assertEqual(first_record['native_measurement']['status'],'measured')
                    entry['native_before'] = first_record['native_measurement']
                    original_task = {k:task[k] for k in ('task_id','objective','parent_task','workspace','role','phase','slot')}
                    unrelated_context = runtime.state['tasks'][unrelated_id]['context_id']
                    computation = None
                    if role == 'primary':
                        script = """from pathlib import Path
import json, time
Path('job-ready').write_text('admitted once')
Path('checkpoint.txt').write_text('awaiting fixture release before public quadrature')
while not Path('release-job').exists(): time.sleep(.05)
rows=[]
for n in (4,8,16,32,64):
    value=(.5+(sum((k/n)**2 for k in range(1,n))))/n
    rows.append(dict(n=n, trapezoidal=value, error=value-1/3, scaled_error=(value-1/3)*n*n))
Path('quadrature.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows),flush=True)
"""
                        computation = await call(first,'job_run',argv=['/usr/bin/python3','-u','-c',script],
                            cwd='/project/'+task['workspace'],runtime_seconds=7200)
                        await until(lambda: (project/task['workspace']/'job-ready').exists(),'real job readiness',15)
                        entry['original_job'] = computation
                    # The only injection point is this trusted harness, never a model tool.
                    injected = {'threadId':first_record['native_thread_id'],
                        'turnId':runtime.clients[first].active_turn_id or first_record['native_measurement']['turn_id'],
                        'tokenUsage':deepcopy(first_record['telemetry'])}
                    injected['tokenUsage']['last']['totalTokens'] = 122000
                    injected['tokenUsage']['modelContextWindow'] = 212000
                    entry['injected_threshold'] = runtime.observe_context(first,injected,'injected-test-55-percent')
                    successor = await until(lambda: task['context_id'] if task['context_id'] and task['context_id']!=first else None,
                                            'automatic fresh native successor')
                    await until(lambda: runtime.state['contexts'][successor].get('native_thread_id'), 'native successor thread')
                    second_record = runtime.state['contexts'][successor]
                    self.assertTrue(first_record['cleanup_ok'])
                    self.assertNotEqual(first_record['native_thread_id'],second_record['native_thread_id'])
                    self.assertEqual({k:task[k] for k in original_task},original_task)
                    self.assertEqual(runtime.state['tasks'][unrelated_id]['context_id'],unrelated_context)
                    self.assertFalse(runtime.state['contexts'][unrelated_context]['cleanup_ok'])
                    entry['validated_handoff'] = first_record['validated_handoff']
                    entry['handoff_text'] = runtime.documents.raw(target_id,first_record['validated_handoff']['document_id']).decode()
                    if role == 'opponent':
                        self.assertIn('## Objections',entry['handoff_text'])
                        self.assertIn('## Review history',entry['handoff_text'])
                    if computation:
                        actual = await runtime.jobs.inspect(target_id,computation['job_id'])
                        preserved = ('job_id','origin_context_id','service','deadline','runtime_seconds','slot','launch_count')
                        self.assertEqual({k:actual[k] for k in preserved},{k:computation[k] for k in preserved})
                        self.assertEqual(actual['state'],'running')
                        properties = await isolation.service_properties(actual['service']['unit'])
                        self.assertEqual(properties['InvocationID'],actual['service']['invocation_id'])
                        self.assertEqual(properties['ActiveState'],'active')
                        self.assertTrue(properties['ControlGroup'].startswith(runtime.allocation.slots[task['slot']]['cgroup']+'/'))
                        self.assertFalse((project/'handoffs/primary.md').exists())
                        entry['job_survival_before_release']={'record':actual,'observed_service':properties}
                        concurrent_note = await until(lambda: draft(unrelated_id,'DURING.md'),
                            'unrelated science after successor attachment while computation survives')
                        entry['concurrent_science'] = {'path':str(concurrent_note),'text':concurrent_note.read_text()}
                        (project/task['workspace']/'release-job').write_text('fresh native context and coexistence observed')
                    after = await until(lambda: draft(target_id,'AFTER.md'),'native scientific continuation after rollover')
                    entry['after_science'] = {'path':str(after),'text':after.read_text()}
                    self.assertEqual(second_record['intake_handoff_id'],first_record['validated_handoff']['document_id'])
                    self.assertTrue(any(document_id in second_record.get('document_reads',{})
                        for document_id in first_record['validated_handoff']['artifact_versions'].values()),
                        'Successor did not read predecessor artifact versions')
                    self.assertEqual(second_record['native_measurement']['status'],'measured')
                    entry['native_after']=second_record['native_measurement']
                    if computation:
                        await until(lambda: second_record.get('job_inspections',{}).get(computation['job_id'],{}).get('state') == 'completed',
                                    'successor inspection/collection of original job')
                        actual = await runtime.jobs.inspect(target_id,computation['job_id'])
                        self.assertEqual(actual['state'],'completed',actual)
                        self.assertTrue(actual['cleanup_ok'])
                        self.assertEqual(len(runtime.state['jobs']),1,'Duplicated scientific computation')
                        self.assertEqual(actual['launch_count'],1)
                        self.assertTrue((project/task['workspace']/'quadrature.json').is_file())
                        entry['collected_job']=actual
                    entry['logical_usage']={k:context_usage.task_usage(runtime.state,k) for k in runtime.state['tasks']}
                    self.assertEqual(workspace.fingerprints(project),before)
                    entry['outcome']='passed'
            except BaseException as exc:
                entry['error']=f'{type(exc).__name__}: {exc}'
                raise
            finally:
                try:
                    entry['cleanup_ok']=await runtime.block_and_cleanup('Explicit engineering demonstration pause')
                    entry['contexts']=runtime.state['contexts']
                    entry['cleanup']=runtime.state.get('cleanup')
                    self.assertTrue(entry['cleanup_ok'],'Production cleanup unconfirmed')
                    self.assertFalse((project/'COMPLETE').exists())
                    self.assertFalse((project/'STOP').exists())
                finally:
                    await runtime.close()
                    jobs.atomic(output/'receipt.json',receipt)

        async def exercise():
            isolation.preflight()  # Authorized existing bus only; missing is a failure.
            for role in ('primary','researcher','opponent'):
                await scenario(role)
        try:
            asyncio.run(exercise())
            receipt['outcome']='passed'
        except BaseException as exc:
            receipt['error']=f'{type(exc).__name__}: {exc}'
            raise
        finally:
            jobs.atomic(output/'receipt.json',receipt)


class NativeReceiptTests(unittest.TestCase):
    def test_enabled_preflight_failure_preserves_distinct_receipts(self):
        from contextlib import redirect_stdout
        import io
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            requested = Path(temp)/'l2-receipt'
            fixture = NativeL2Tests('test_native_science_continues_all_roles_and_admitted_computation')
            paths = []
            with patch.dict(os.environ, {'RESEARCH_PIPELINE_V0_L2_OUTPUT_DIR':str(requested)}):
                for attempt in range(2):
                    logged = io.StringIO()
                    with redirect_stdout(logged), patch.object(isolation,'preflight',side_effect=
                            isolation.RuntimeUnavailable(f'authorized bus absent {attempt}')):
                        with self.assertRaisesRegex(isolation.RuntimeUnavailable,'authorized bus absent'):
                            fixture.test_native_science_continues_all_roles_and_admitted_computation()
                    path = Path(logged.getvalue().strip().split('V0-L2 output: ')[1])/'receipt.json'
                    paths.append(path)
                    report = json.loads(path.read_text())
                    self.assertEqual(report['outcome'],'failed')
                    self.assertEqual(report['commands'],[])
                    self.assertEqual(report['scenarios'],[])
                    self.assertIn(str(attempt),report['error'])
            self.assertNotEqual(*paths)
            self.assertIn('absent 0',paths[0].read_text())
