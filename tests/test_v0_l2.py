"""Consequential continuous-runner tests. Native/service doubles are explicit.

Real JSON-RPC fixtures live here and in test_app_server; production process
survival with live scientific continuation is opt-in test_v0_l2_native.
"""
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.test_context_usage import params
from tests.test_review_repairs import context_fixture, make_project
from research_pipeline import codex, collaboration, context_usage, isolation, jobs, workspace


def handoff(task, artifact=None, job_ids=()):
    artifact = artifact or '/project/' + task['workspace'] + '/NOTE.md'
    sections = {'Objective': task['objective'], 'Parent question': str(task['parent_task']),
        'Phase': task['phase'], 'Role': task['role'], 'Completed': 'Derived a public finite sum.',
        'Artifacts': f'[Calculation]({artifact})', 'Assumptions': 'Exact integer arithmetic.',
        'Unresolved': 'Generalization remains preliminary.', 'Next action': 'Check the cubic law.',
        'Interrupted computation': 'None; owned jobs survive context closure.',
        'Resume or reconsider': 'Resume the same calculation.',
        'Jobs': 'Purpose: check sum; outputs/checkpoints in workspace. Inspect job_status, '
                'collect job_wait, stop job_cancel. IDs: ' + ', '.join(job_ids),
        'Review history': 'Challenged a cubic formula independently.',
        'Objections': 'Finite checks alone do not prove the formula for every n.'}
    return f'Logical researcher: {task["task_id"]}\n' + '\n'.join(f'## {k}\n{v}\n' for k,v in sections.items())


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime=collaboration.Coordinator.initialize(make_project(Path(self.tmp.name)),isolation.Config())
        self.launched=[]
        self.progress=asyncio.Event()
        self.recovered=asyncio.Event()
        self.missing=False
        self.invalid=False
        self.bad_handoff=False
        self.race_threshold=False
        self.fail_successor=False
        self.fail_close=False
        self.patchers=[patch.object(self.runtime,'attach',self.attach),
                       patch.object(self.runtime,'validate_inventory',return_value=True)]
        for p in self.patchers: p.start(); self.addCleanup(p.stop)

    async def asyncTearDown(self):
        await self.runtime.block_and_cleanup('Engineering fixture pause')
        await self.runtime.close()

    async def attach(self,task_id):
        if self.fail_successor and self.launched:
            raise isolation.RuntimeUnavailable('Injected successor failure')
        cid='context-'+uuid.uuid4().hex
        self.launched.append(cid)
        ctx=context_fixture(self.runtime,cid,cleanup=not self.fail_close,task_id=task_id)
        science, publication_baseline, changes=self.runtime.science_intake(task_id)
        ctx.update(baseline=science,publication_baseline=publication_baseline)
        ctx['record'].update(native_thread_id='native-'+cid,input_changes=sorted(changes),science_changes=changes,
                             predecessor=self.runtime.state['tasks'][task_id].get('last_context_id'))
        outer=self
        task=self.runtime.state['tasks'][task_id]
        class BackendDouble:
            def __init__(self):
                self.active_turn_id=None
                self.turn_ready=asyncio.Event()
                self.waiting=None
                self.count=0
                self.science_turns=0
                self.closed=False
            async def turn(self,text):
                self.count+=1
                self.active_turn_id='turn-'+str(self.count)
                self.turn_ready.set()
                if not outer.missing:
                    raw=params(length=10000,window=None if outer.invalid else 212000,
                               total=100*self.count,thread=ctx['record']['native_thread_id'],turn=self.active_turn_id)
                    outer.runtime.observe_context(cid,raw)
                if 'Measurement intake' in text:
                    for job_id in list(task.get('pending_job_inspections',[])):
                        outer.runtime.job_inspected(task,job_id)
                    outer.recovered.set()
                elif 'threshold' in text or 'Repair this' in text:
                    outer.runtime.draft(ctx,task['workspace']+'/NOTE.md','# Science\nSum of squares is 285 for n=9.\n')
                    outer.runtime.draft(ctx,workspace.handoff_path(task_id),'bad' if outer.bad_handoff else handoff(task,
                        job_ids=[r['job_id'] for r in outer.runtime.state['jobs'].values() if r['task_id']==task_id]))
                else:
                    self.science_turns+=1
                    if outer.race_threshold and len(outer.launched)==1 and self.science_turns==1:
                        outer.runtime.observe_context(cid,params(thread=ctx['record']['native_thread_id']), 'injected-test')
                        self.active_turn_id=None
                        return {'id':self.active_turn_id,'status':'completed'}
                    outer.progress.set()
                    if self.science_turns >= 2 or len(outer.launched)>1:
                        self.waiting=asyncio.get_running_loop().create_future()
                        return await self.waiting
                self.active_turn_id=None
                return {'id':'turn-'+str(self.count),'status':'completed'}
            async def interrupt(self,turn_id):
                if self.waiting and not self.waiting.done():
                    self.waiting.set_result({'id':turn_id,'status':'interrupted'})
                self.active_turn_id=None
            async def close(self):
                self.closed=True
                if self.waiting and not self.waiting.done():
                    self.waiting.set_exception(isolation.RuntimeUnavailable('Fixture context closed'))
                return {'confirmed':not outer.fail_close,'reason':'Explicit backend double'}
        self.runtime.clients[cid]=BackendDouble()
        return cid

    async def wait_for(self,predicate):
        async def wait():
            while not predicate(): await asyncio.sleep(.001)
        await asyncio.wait_for(wait(),2)

    async def start_runner(self,task_id='primary'):
        runner=asyncio.create_task(self.runtime.run_task(task_id))
        self.runtime.turns[task_id]=runner
        return runner

    async def trigger(self,task_id):
        cid=self.runtime.state['tasks'][task_id]['context_id']
        record=self.runtime.state['contexts'][cid]
        self.runtime.observe_context(cid,params(thread=record['native_thread_id']),provenance='injected-test')
        return cid

    async def test_roles_continue_two_turns_then_one_fresh_context_with_same_identity(self):
        for role in ('primary','researcher','opponent','verifier'):
            with self.subTest(role=role):
                task=self.runtime.state['tasks']['primary']
                task.update(role=role,phase='review' if role in ('opponent','verifier') else 'research')
                self.runtime.state['admission_block']=None
                self.launched.clear()
                self.progress.clear()
                runner=await self.start_runner()
                await self.wait_for(lambda: self.launched and self.runtime.clients[self.launched[0]].science_turns==2)
                original={k:deepcopy(task[k]) for k in ('task_id','objective','workspace','parent_task','role','phase','slot')}
                cid=await self.trigger('primary')
                # Repeated observations latch the same transition.
                await self.trigger('primary')
                await self.wait_for(lambda: len(self.launched)==2 and self.runtime.clients[self.launched[-1]].science_turns==1)
                successor=task['context_id']
                old=self.runtime.state['contexts'][cid]
                self.assertTrue(old['cleanup_ok'])
                self.assertNotEqual(old['native_thread_id'],self.runtime.state['contexts'][successor]['native_thread_id'])
                self.assertEqual({k:task[k] for k in original},original)
                self.assertNotIn('threshold_observation',self.runtime.state['contexts'][successor])
                packet=self.runtime.successor_documents('primary')['validated_handoff']
                self.assertIn('Finite checks alone',packet['content'])
                self.assertIn('document_id',packet)
                self.assertGreater(context_usage.task_usage(self.runtime.state,'primary')['observed_cumulative']['totalTokens'],300)
                self.assertEqual(old['successor_context_id'],successor)
                await self.runtime.block_and_cleanup('Engineering fixture pause')
                await asyncio.wait_for(runner,2)
                self.assertNotIn('context_error',task)
                self.assertEqual(self.runtime.state['scientific_status'],'preliminary')
                # Separate sequential role scenarios, no new allocations.
                self.runtime.state['contexts'].clear(); self.runtime.contexts.clear()
                self.runtime.state['documents'].clear(); task['last_context_id']=None
                task['operational_state']='working'

    async def test_completion_and_threshold_in_same_turn_produce_one_successor(self):
        self.race_threshold=True
        runner=await self.start_runner()
        await self.wait_for(lambda: len(self.launched)==2 and self.runtime.clients[self.launched[-1]].science_turns==1)
        first, second=self.launched
        self.assertTrue(self.runtime.clients[second].science_turns)
        self.assertTrue(self.runtime.contexts[first]['record']['rollover_attempted'])
        self.assertTrue(self.runtime.contexts[first]['record']['cleanup_ok'])
        await self.runtime.block_and_cleanup('Engineering fixture pause')
        await asyncio.wait_for(runner,2)
        self.assertEqual(len(self.launched),2)

    async def test_failed_interrupt_is_operational_failure_with_confirmed_closure(self):
        runner=await self.start_runner()
        await self.wait_for(lambda: self.launched and self.runtime.clients[self.launched[0]].science_turns==2)
        cid=self.launched[0]
        client=self.runtime.clients[cid]
        client.interrupt=AsyncMock(side_effect=isolation.RuntimeUnavailable('interrupt RPC failed'))
        await self.trigger('primary')
        await asyncio.wait_for(runner,2)
        self.assertTrue(client.closed)
        self.assertEqual(len(self.launched),1)
        self.assertIn('interrupt RPC failed',self.runtime.state['tasks']['primary']['context_error'])
        self.assertTrue(self.runtime.contexts[cid]['record']['cleanup_ok'])

    async def test_handoff_rejects_wrong_identity_phase_and_unsafe_artifacts(self):
        import os
        ctx=context_fixture(self.runtime)
        task=self.runtime.state['tasks']['primary']
        self.runtime.draft(ctx,'work/NOTE.md','# Preliminary calculation')
        good=handoff(task)
        variants=(good.replace('Logical researcher: primary','Logical researcher: foreign'),
                  good.replace('## Phase\nresearch','## Phase\nreview'),
                  good.replace('## Assumptions','## Missing assumptions'),
                  good.replace('/project/work/NOTE.md','/project/work/absent.md'))
        for text in variants:
            self.runtime.draft(ctx,'handoffs/primary.md',text)
            with self.assertRaises((ValueError, OSError)): self.runtime.validate_context_handoff('first')
        self.runtime.draft(ctx,'handoffs/primary.md',good)
        note=ctx['drafts']/'work/NOTE.md'
        for kind in ('symlink','fifo','oversized'):
            note.unlink()
            if kind=='symlink': note.symlink_to(self.runtime.project/'starting_evidence/RESEARCH_QUESTIONS.md')
            elif kind=='fifo': os.mkfifo(note)
            else:
                with note.open('wb') as stream: stream.truncate(16*1024*1024+1)
            with self.assertRaises((ValueError, OSError)): self.runtime.validate_context_handoff('first')
        note.unlink()
        task['objective']='# Public objective\n## Subquestion\nProve a finite-sum identity.'
        note.write_text('# Useful saved science')
        quoted=handoff(task).replace(task['objective'],'\n'.join('> '+line for line in task['objective'].splitlines()))
        self.runtime.draft(ctx,'handoffs/primary.md',quoted)
        self.assertEqual(self.runtime.validate_context_handoff('first'),['work/NOTE.md'])

    async def test_handoff_self_navigation_keeps_science_and_immutable_versions(self):
        ctx=context_fixture(self.runtime)
        task=self.runtime.state['tasks']['primary']
        self.runtime.draft(ctx,'work/BEFORE.md',
            '# Preliminary analysis\nFor x squared, each trapezoidal panel has excess h cubed / 6.')
        science=handoff(task,artifact='../work/BEFORE.md')
        # Reproduces the native handoff: useful science plus a navigation link
        # back to the current handoff, rather than self-reference as evidence.
        for target in ('primary.md', '/project/handoffs/primary.md', 'primary%2Emd#jobs'):
            text=science.replace('## Assumptions',
                f'[Current handoff]({target})\n\n## Assumptions')
            self.runtime.draft(ctx,'handoffs/primary.md',text)
            self.assertEqual(self.runtime.validate_context_handoff('first'),['work/BEFORE.md'])
        await self.runtime.close_context('first')
        self.assertEqual(self.runtime.validate_context_handoff('first',final=True),['work/BEFORE.md'])
        validated=ctx['record']['validated_handoff']
        self.assertEqual(set(validated['artifact_versions']),{'work/BEFORE.md'})
        self.assertEqual(set(validated['artifact_evidence']),{'work/BEFORE.md'})
        document_id=validated['artifact_versions']['work/BEFORE.md']
        self.assertIn(b'panel has excess',self.runtime.documents.raw('primary',document_id))

    async def test_handoff_self_navigation_alone_cannot_replace_saved_science(self):
        ctx=context_fixture(self.runtime)
        task=self.runtime.state['tasks']['primary']
        for target in ('primary.md', '/project/handoffs/primary.md', 'primary%2Emd#jobs'):
            self.runtime.draft(ctx,'handoffs/primary.md',handoff(task,artifact=target))
            with self.assertRaisesRegex(workspace.InputError,'at least one saved scientific artifact'):
                self.runtime.validate_context_handoff('first')
        await self.runtime.close_context('first')
        with self.assertRaisesRegex(workspace.InputError,'at least one saved scientific artifact'):
            self.runtime.validate_context_handoff('first',final=True)
        self.assertNotIn('validated_handoff',ctx['record'])

    async def test_misplaced_researcher_handoff_is_repaired_at_required_destination(self):
        await self.check_misplaced_handoff_repair('researcher')

    async def test_misplaced_opponent_handoff_is_repaired_at_required_destination(self):
        await self.check_misplaced_handoff_repair('opponent')

    async def check_misplaced_handoff_repair(self, role):
        task_id='task-'+uuid.uuid4().hex
        self.runtime.add_task(task_id, 'Check the public finite sum.', 'primary', role=role)
        task=self.runtime.state['tasks'][task_id]
        required=workspace.handoff_path(task_id)
        runner=await self.start_runner(task_id)
        await self.wait_for(lambda: task['context_id'] and
            self.runtime.clients[task['context_id']].science_turns==2)
        cid=task['context_id']
        ctx=self.runtime.contexts[cid]
        client=self.runtime.clients[cid]
        original_turn=client.turn
        checkpoints=[]

        async def misplaced_turn(text):
            result=await original_turn(text)
            if 'threshold' in text or 'Repair this' in text:
                checkpoints.append(text)
                if len(checkpoints)==1 or required not in text:
                    # Native failure: draft saves succeeded at a workspace
                    # path, leaving no canonical handoff directory at all.
                    self.runtime.draft(ctx,task['workspace']+'/HANDOFF.md',handoff(task))
                    (ctx['drafts']/required).unlink()
                    (ctx['drafts']/'handoffs').rmdir()
            return result

        client.turn=misplaced_turn
        await self.trigger(task_id)
        await self.wait_for(lambda: task.get('context_error') or
            task['context_id'] and task['context_id']!=cid)
        self.assertNotIn('context_error',task)
        self.assertEqual(len(checkpoints),2)
        self.assertIn(required,checkpoints[0])
        self.assertIn(required,ctx['record']['handoff_validation_error'])
        validated=ctx['record']['validated_handoff']
        self.assertEqual(validated['path'],required)
        self.assertEqual(set(validated['artifact_versions']),{task['workspace']+'/NOTE.md'})
        self.assertTrue(ctx['record']['cleanup_ok'])
        packet=self.runtime.successor_documents(task_id)['validated_handoff']
        self.assertIn('Finite checks alone',packet['content'])
        intake_prompt=codex.prompt(workspace.read_intake(self.runtime.project),task,[])
        self.assertIn(required,intake_prompt)
        self.assertIn('project-relative',intake_prompt)
        await self.runtime.block_and_cleanup('Engineering fixture pause')
        await asyncio.wait_for(runner,2)

    async def test_missing_telemetry_and_failed_checkpoint_preserve_truthful_failure(self):
        self.missing=True
        runner=await self.start_runner()
        await asyncio.wait_for(runner,2)
        task=self.runtime.state['tasks']['primary']
        self.assertIn('Reliable context telemetry unavailable',task['context_error'])
        self.assertEqual(task['operational_state'],'failed')
        self.assertTrue(self.runtime.state['contexts'][self.launched[0]]['cleanup_ok'])
        self.assertFalse((self.runtime.project/'COMPLETE').exists())
        self.assertFalse((self.runtime.project/'STOP').exists())

    async def test_invalid_measurement_interrupts_then_supported_recovery(self):
        runner=await self.start_runner()
        await self.wait_for(lambda: self.launched and self.runtime.clients[self.launched[0]].science_turns==2)
        cid=self.launched[0]
        self.recovered.clear()
        self.runtime.observe_context(cid,params(thread='native-'+cid,window=None))
        self.assertEqual(self.runtime.state['tasks']['primary']['operational_state'],'telemetry_recovery')
        await asyncio.wait_for(self.recovered.wait(),2)
        await self.wait_for(lambda: self.runtime.clients[cid].science_turns==3)
        self.assertEqual(len(self.launched),1)
        self.assertEqual(self.runtime.contexts[cid]['record']['measurement']['status'],'measured')
        await self.runtime.block_and_cleanup('Engineering pause')
        await asyncio.wait_for(runner,2)

    async def failure_case(self):
        runner=await self.start_runner()
        await self.wait_for(lambda: self.launched and self.runtime.clients[self.launched[0]].science_turns==2)
        cid=await self.trigger('primary')
        await asyncio.wait_for(runner,2)
        self.assertEqual(self.runtime.state['tasks']['primary']['operational_state'],'failed')
        self.assertEqual(self.runtime.state['scientific_status'],'preliminary')
        self.assertEqual(len(self.launched),1)
        self.assertTrue(list((self.runtime.contexts[cid]['drafts']).rglob('NOTE.md')))
        return self.runtime.state['contexts'][cid]

    async def test_unusable_handoff_repair_fails_without_successor(self):
        self.bad_handoff=True
        record=await self.failure_case()
        self.assertIn('handoff_validation_error',record)
        self.assertTrue(record['cleanup_ok'])
        self.assertTrue(record['document_ids'])

    async def test_successor_failure_keeps_validated_science(self):
        self.fail_successor=True
        record=await self.failure_case()
        self.assertIn('validated_handoff',record)
        self.assertTrue(record['cleanup_ok'])

    async def test_unconfirmed_closure_never_starts_successor(self):
        self.fail_close=True
        record=await self.failure_case()
        self.assertFalse(record['cleanup_ok'])
        self.assertIsNotNone(self.runtime.state['tasks']['primary']['context_id'])
        self.assertIn('unconfirmed',self.runtime.state['admission_block'])
        self.fail_close=False

    async def test_snapshot_failure_keeps_cleanup_and_science_without_successor(self):
        with patch.object(self.runtime.documents,'capture',side_effect=workspace.InputError('snapshot failure')):
            record=await self.failure_case()
        self.assertTrue(record['cleanup_ok'])
        self.assertIn('snapshot failure',record['job_handoff_error'])

    async def test_measurement_and_checkpoint_block_admission_inside_job_lock(self):
        task=self.runtime.state['tasks']['primary']
        task.update(context_id='native',inventory_verified=True)
        for state in ('telemetry_recovery','checkpointing','rollover_pending','failed'):
            task['operational_state']=state
            with self.assertRaisesRegex(jobs.JobError,'lifecycle'):
                await self.runtime.jobs.run('primary','native',['true'],'/project/work',7200)
        self.assertFalse(self.runtime.state['jobs'])
        task.update(operational_state='working',pending_job_inspections=['owned'])
        with self.assertRaisesRegex(jobs.JobError,'reconciliation'):
            await self.runtime.jobs.run('primary','native',['true'],'/project/work',7200)

    async def test_assignment_waiting_for_job_lock_rechecks_rollover_state(self):
        ctx=context_fixture(self.runtime)
        async with self.runtime.jobs.lock:
            assigning=asyncio.create_task(self.runtime.control(ctx,'delegate','work/ASSIGNMENT.md'))
            await asyncio.sleep(0)
            self.runtime.state['tasks']['primary']['operational_state']='checkpointing'
        with self.assertRaisesRegex(jobs.JobError,'lifecycle'):
            await assigning
        self.assertEqual(len(self.runtime.state['tasks']),1)

    async def test_duplicate_and_injected_usage_cannot_cover_later_inferences(self):
        cid=await self.attach('primary')
        record=self.runtime.contexts[cid]['record']
        record['native_inference_count']=1
        sample=params(thread=record['native_thread_id'])
        self.runtime.observe_context(cid,sample)
        self.assertEqual(record['measured_inference_count'],1)
        record['native_inference_count']=4
        self.runtime.observe_context(cid,sample)
        self.runtime.observe_context(cid,sample,provenance='injected-test')
        self.assertEqual(record['measured_inference_count'],1)
        self.assertEqual(record['native_measurement_count'],1)

    async def publication_after_rollover(self, human_edit=False, incorporate=False,
                                        change_after_ack=False, edit_again=False, another_rollover=False,
                                        human_reverts=False):
        # Keep another writer attached so predecessor publication is deferred
        # through actual runner rollover and successor scientific updates.
        child_id='task-'+uuid.uuid4().hex
        self.runtime.add_task(child_id,'Independent work','primary')
        unrelated=context_fixture(self.runtime,'unrelated',task_id=child_id)
        self.runtime.draft(unrelated,self.runtime.state['tasks'][child_id]['workspace']+'/RESULT.md',
                           '# Independent result\nA separate useful check.')
        (self.runtime.project/'work/NOTE.md').write_text('# Initial science')
        runner=await self.start_runner()
        await self.wait_for(lambda: self.launched and self.runtime.clients[self.launched[0]].science_turns==2)
        human='# Human correction\nRestrict the claim.'
        if human_edit=='before_attach':
            (self.runtime.project/'work/NOTE.md').write_text(human)
        first=await self.trigger('primary')
        await self.wait_for(lambda: len(self.launched)==2 and self.runtime.clients[self.launched[-1]].science_turns==1)
        if another_rollover:
            await self.trigger('primary')
            await self.wait_for(lambda: len(self.launched)==3 and self.runtime.clients[self.launched[-1]].science_turns==1)
        successor=self.runtime.contexts[self.launched[-1]]
        self.assertTrue(self.runtime.contexts[first]['record']['publication_pending'])
        self.assertEqual((self.runtime.project/'work/NOTE.md').read_text(),
                         human if human_edit=='before_attach' else '# Initial science')
        latest='# Successor science\nA cubic finite-difference argument extends the finite check.'
        if incorporate:
            latest+='\nHuman correction incorporated: restrict the claim to the checked domain.'
        latest_handoff=handoff(self.runtime.state['tasks']['primary']).replace(
            'Check the cubic law.','Continue checking the derived finite-difference identity.')
        self.runtime.draft(successor,'work/NOTE.md',latest)
        self.runtime.draft(successor,'handoffs/primary.md',latest_handoff)
        if human_edit=='before_attach':
            intake=self.runtime.successor_documents('primary')
            self.assertIn('work/NOTE.md',intake['input_changes'])
            self.assertIn('work/NOTE.md',intake['science_changes'])
            self.assertEqual(successor['baseline']['work/NOTE.md'],
                             intake['science_changes']['work/NOTE.md']['sha256'])
        elif human_edit:
            (self.runtime.project/'work/NOTE.md').write_text(human)
        if human_reverts:
            human='# Initial science'
            (self.runtime.project/'work/NOTE.md').write_text(human)
        if incorporate:
            digest=self.runtime.state['contexts'][successor['record']['context_id']]['science_changes']['work/NOTE.md']['sha256']
            await self.runtime.control(successor,'incorporate_edit','work/NOTE.md',sha256=digest)
            self.assertEqual((self.runtime.project/'work/NOTE.md').read_text(),human)
            if change_after_ack:
                latest+='\nA revision not covered by the incorporation acknowledgement.'
                self.runtime.draft(successor,'work/NOTE.md',latest)
            if edit_again:
                human+='\nA further human correction supersedes the acknowledged version.'
                (self.runtime.project/'work/NOTE.md').write_text(human)
        self.assertTrue(await self.runtime.block_and_cleanup('Engineering fixture pause'))
        await asyncio.wait_for(runner,2)
        self.assertEqual((self.runtime.project/'handoffs/primary.md').read_text(),latest_handoff)
        earlier=self.runtime.contexts[first]['record']
        self.assertEqual(earlier['publication_conflicts'],[])
        self.assertIn('work/NOTE.md',earlier['publication_superseded'])
        if human_edit and (not incorporate or change_after_ack or edit_again):
            self.assertEqual((self.runtime.project/'work/NOTE.md').read_text(),
                             human)
            conflicts=successor['record']['publication_conflicts']
            self.assertEqual([c['path'] for c in conflicts],['work/NOTE.md'])
            self.assertIn(latest,(self.runtime.project/conflicts[0]['proposal']).read_text())
        else:
            self.assertEqual((self.runtime.project/'work/NOTE.md').read_text(),latest)
            self.assertEqual(successor['record']['publication_conflicts'],[])
            self.assertFalse((self.runtime.project/'handoffs/proposed').exists())
            if incorporate:
                preserved=successor['record']['preserved_human_edits']
                self.assertEqual(len(preserved),1)
                self.assertIn(human,(self.runtime.project/preserved[0]).read_text())
            else:
                self.assertFalse((self.runtime.project/'handoffs/preserved').exists())
            self.assertIn('Successor science',(self.runtime.project/'work/FOLDER_CONTENT.md').read_text())
        snapshots=[doc for doc in self.runtime.state['documents'].values()
                   if doc['source_id']==first and doc['path']=='work/NOTE.md']
        self.assertEqual(len(snapshots),1)
        self.assertIn('285',self.runtime.documents.raw('primary',snapshots[0]['document_id']).decode())

    async def test_pause_publishes_latest_successor_notes_and_handoff(self):
        await self.publication_after_rollover()

    async def test_pause_preserves_real_human_edit_and_latest_successor_proposal(self):
        await self.publication_after_rollover(human_edit=True)

    async def test_human_edit_before_successor_attachment_remains_protected(self):
        await self.publication_after_rollover(human_edit='before_attach')

    async def test_unresolved_human_edit_survives_multiple_pending_successors(self):
        await self.publication_after_rollover(human_edit='before_attach',another_rollover=True)

    async def test_unresolved_human_edit_is_not_cleared_by_return_to_original_content(self):
        await self.publication_after_rollover(human_edit='before_attach',human_reverts=True)

    async def test_explicit_incorporation_publishes_revision_and_preserves_human_version(self):
        await self.publication_after_rollover(human_edit='before_attach',incorporate=True)

    async def test_later_draft_change_requires_new_incorporation_acknowledgement(self):
        await self.publication_after_rollover(human_edit='before_attach',incorporate=True,change_after_ack=True)

    async def test_human_edit_after_acknowledgement_remains_canonical(self):
        await self.publication_after_rollover(human_edit='before_attach',incorporate=True,edit_again=True)
    async def test_invalid_descendant_batch_does_not_suppress_valid_predecessor_science(self):
        child_id='task-'+uuid.uuid4().hex
        self.runtime.add_task(child_id,'Independent work','primary')
        context_fixture(self.runtime,'other',task_id=child_id)
        first=context_fixture(self.runtime,'first')
        self.runtime.draft(first,'work/NOTE.md','# Useful predecessor science')
        await self.runtime.close_context('first')
        second=context_fixture(self.runtime,'second')
        second['record']['predecessor']='first'
        self.runtime.draft(second,'work/NOTE.md','# Unusable successor batch')
        unsafe=second['drafts']/'starting_evidence/forbidden.md'
        unsafe.parent.mkdir()
        unsafe.write_text('invalid scoped destination')
        self.assertTrue(await self.runtime.block_and_cleanup('Engineering pause'))
        self.assertEqual((self.runtime.project/'work/NOTE.md').read_text(),'# Useful predecessor science')
        self.assertIn('publication_error',second['record'])
        self.assertEqual(first['record']['publication_conflicts'],[])

    async def test_two_logical_agents_and_real_fixture_process_survive_one_rollover(self):
        # Actual local process; backend, service ownership and reconciliation are
        # explicit doubles. The native gate is required for production isolation.
        import sys
        import time
        child_id = 'task-' + uuid.uuid4().hex
        child = self.runtime.add_task(child_id, 'Independent finite-sum check', 'primary')
        primary = await self.start_runner()
        secondary = await self.start_runner(child_id)
        await self.wait_for(lambda: len(self.launched)==2 and all(
            self.runtime.clients[c].science_turns for c in self.launched))
        task = self.runtime.state['tasks']['primary']
        first = task['context_id']
        other = child['context_id']
        work = self.runtime.project/'work'
        process = await asyncio.create_subprocess_exec(sys.executable, '-u', '-c',
            "from pathlib import Path; import time; Path('ready').touch(); "
            "exec(\"while not Path('release').exists(): time.sleep(.01)\"); "
            "Path('answer').write_text(str(sum(i*i for i in range(10))))", cwd=work)
        self.addAsyncCleanup(process.wait)
        try:
            await self.wait_for(lambda: (work/'ready').exists())
            began = time.monotonic()
            job = {'job_id':uuid.uuid4().hex,'task_id':'primary','origin_context_id':first,
                'state':'running','cleanup_ok':False,'launch_count':1,'slot':task['slot'],
                'runtime_seconds':7200,'admitted_monotonic':began,'deadline':began+7200,
                'service':{'fixture_pid':process.pid},'argv':['public-local-process'],
                'cwd':'/project/work'}
            self.runtime.state['jobs'][job['job_id']] = job
            original = deepcopy(job)
            with patch.object(self.runtime.jobs, '_reconcile', AsyncMock()) as reconcile:
                await self.trigger('primary')
                await self.wait_for(lambda: len(self.launched)==3 and task['context_id']!=first and
                    self.runtime.clients[task['context_id']].science_turns==1)
                self.assertIsNone(process.returncode)
                self.assertEqual(job,original)
                self.assertEqual(child['context_id'],other)
                self.assertFalse(self.runtime.state['contexts'][other]['cleanup_ok'])
                self.assertTrue(any(call.args[0]['job_id']==job['job_id'] for call in reconcile.call_args_list))
                self.assertFalse(task.get('pending_job_inspections'))
                # Unrelated context continues useful fixture work while the same
                # process/job remains active; no extra admission is made.
                self.runtime.draft(self.runtime.contexts[other],child['workspace']+'/CONTINUING.md',
                    '# Independent check\nThe finite difference of the cubic sum equals n squared.')
                (work/'release').touch()
                await asyncio.wait_for(process.wait(),2)
                job.update(state='completed',cleanup_ok=True,stdout=(work/'answer').read_text())
                self.runtime.jobs.changed(job)
                result=await self.runtime.jobs.wait('primary',job['job_id'])
                self.assertEqual(result['stdout'],'285')
                self.assertEqual(result['deadline'],original['deadline'])
                self.assertEqual(result['service'],original['service'])
                self.assertEqual(result['launch_count'],1)
                self.assertEqual(len(self.runtime.state['jobs']),1)
        finally:
            if process.returncode is None: process.kill()
            await process.wait()
            for job in self.runtime.state['jobs'].values():
                job.update(state='completed',cleanup_ok=True)
        await self.runtime.block_and_cleanup('Engineering fixture pause')
        await asyncio.gather(primary,secondary)

    async def test_exact_handoff_delivered_past_listing_page_and_tamper_rejected(self):
        ctx=context_fixture(self.runtime)
        task=self.runtime.state['tasks']['primary']
        self.runtime.draft(ctx,'work/NOTE.md','# Calculation\n285')
        self.runtime.draft(ctx,'handoffs/primary.md',handoff(task))
        for i in range(45): self.runtime.draft(ctx,f'work/z{i:02}.md','# Other science')
        self.runtime.validate_context_handoff('first')
        await self.runtime.close_context('first')
        self.runtime.validate_context_handoff('first',final=True)
        task['context_id']='next'
        self.runtime.contexts['next']={'record':{'input_changes':[]}}
        try:
            packet=self.runtime.successor_documents('primary')['validated_handoff']
            self.assertNotIn(packet['document_id'],[d['document_id'] for d in self.runtime.documents.list('primary')['documents']])
            self.assertIn('285',self.runtime.documents.raw('primary',packet['artifact_versions']['work/NOTE.md']).decode())
            path=self.runtime.documents.root/(packet['document_id']+'.md')
            path.chmod(0o600);path.write_text('changed')
            with self.assertRaisesRegex(jobs.JobError,'integrity'): self.runtime.successor_documents('primary')
        finally:
            self.runtime.contexts.pop('next');task['context_id']=None


class InferenceGapTests(unittest.IsolatedAsyncioTestCase):
    """Real local JSON-RPC + native-schema trace fixtures; no paid inference.

    A continuing turn emits multiple tool items, then loses RPC usage updates
    while native inference starts continue. No scripted turn completion releases
    the runner: recovery must interrupt it through the actual RPC reader.
    """
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime=collaboration.Coordinator.initialize(make_project(Path(self.tmp.name)),isolation.Config())
        self.ctx=context_fixture(self.runtime)
        self.ctx['auth']=self.runtime.project/'.research_pipeline/trace-home'
        self.ctx['auth'].mkdir()
        self.ctx['inventory_ready']=asyncio.Event()

    async def asyncTearDown(self):
        await self.runtime.block_and_cleanup('Engineering protocol fixture pause')
        await self.runtime.close()

    async def start_fixture(self,mode):
        import sys
        from research_pipeline import app_server
        script=r'''
import json, sys
from pathlib import Path
home, mode = Path(sys.argv[1]), sys.argv[2]
bundle=home/'native-trace/fixture'
(bundle/'payloads').mkdir(parents=True)
thread='native-fixture'
(bundle/'manifest.json').write_text(json.dumps(dict(schema_version=2,root_thread_id=thread,rollout_id=thread)))
count=0
turn_number=0
active=None

def send(method,params):
    print(json.dumps(dict(method=method,params=params)),flush=True)

def inference():
    global count
    count+=1
    relative=f'payloads/{count}.json'
    tools=[dict(type='function',name='mcp__research_jobs__'+name,description='Controlled fixture')
           for name in ('job_run','job_status','job_wait','job_cancel','write_draft','control')]
    (bundle/relative).write_text(json.dumps(dict(model='protocol-double',input=[],tools=tools)))
    event=dict(schema_version=2,thread_id=thread,rollout_id=thread,
        payload=dict(type='inference_started',thread_id=thread,
                     request_payload=dict(kind=dict(type='inference_request'),path=relative)))
    with (bundle/'trace.jsonl').open('a') as stream: stream.write(json.dumps(event)+'\n')

def usage():
    def counters(n):
        return dict(totalTokens=n,inputTokens=n,cachedInputTokens=0,
                    outputTokens=0,reasoningOutputTokens=0,cacheWriteInputTokens=0)
    send('thread/tokenUsage/updated',dict(threadId=thread,turnId=active,tokenUsage=dict(
        last=counters(10000),total=counters(100*count),modelContextWindow=212000)))

def tool(n,completed=True):
    item=dict(type='mcpToolCall',id=f'tool-{n}',server='research_jobs',tool='job_wait' if not completed else 'control',arguments={})
    send('item/started',dict(threadId=thread,turnId=active,item=item))
    if completed: send('item/completed',dict(threadId=thread,turnId=active,item=item))

for line in sys.stdin:
    request=json.loads(line)
    if 'id' not in request: continue
    method=request['method']
    if method=='thread/start':
        result=dict(thread=dict(id=thread))
    elif method=='turn/start':
        turn_number+=1
        active=f'turn-{turn_number}'
        inference()
        print(json.dumps(dict(id=request['id'],result=dict(turn=dict(id=active)))),flush=True)
        if turn_number==2:
            usage()
            tool(1)
            if mode!='idle':
                inference()  # second inference, first missing RPC usage report
                tool(2)
                inference()  # proves the previous inference ended unmeasured
            tool(3,completed=False)
            continue  # stays alive until real turn/interrupt or context closure
        if turn_number!=3 or mode not in ('lost','late-lost'): usage()
        if turn_number>=4:
            tool(4,completed=False)
            continue
        send('turn/completed',dict(threadId=thread,turn=dict(id=active,status='completed')))
        active=None
        continue
    elif method=='turn/interrupt':
        if mode in ('late','late-lost'):
            usage()  # arrives after the gap is latched, before interrupted completion
        send('turn/completed',dict(threadId=thread,turn=dict(id=active,status='interrupted')))
        active=None
        result={}
    else:
        result={}
    print(json.dumps(dict(id=request['id'],result=result)),flush=True)
'''
        process=await asyncio.create_subprocess_exec(sys.executable,'-u','-c',script,str(self.ctx['auth']),mode,
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        class Service:
            async def close(self):
                if process.returncode is None: process.kill()
                await process.wait()
                return {'confirmed':True,'reason':'Local protocol fixture reaped'}
        service=Service()
        service.process=process
        client=app_server.Client(service,lambda event:self.runtime.context_event('first',event))
        self.runtime.clients['first']=client
        self.addAsyncCleanup(client.close)
        self.interruption_states=[]
        self.recovery_event_states=[]
        turn=client.turn
        async def checked_turn(text):
            if text.startswith('Measurement intake') and self.ctx['record'].get('measurement_gap'):
                self.recovery_event_states.append(self.ctx['lifecycle_event'].is_set())
            return await turn(text)
        client.turn=checked_turn
        interrupt=client.interrupt
        async def checked_interrupt(turn_id):
            self.interruption_states.append(self.runtime.state['tasks']['primary']['operational_state'])
            with self.assertRaisesRegex(jobs.JobError,'lifecycle'):
                await self.runtime.jobs.run('primary','first',['true'],'/project/work',61)
            return await interrupt(turn_id)
        client.interrupt=checked_interrupt
        await client.start()
        self.ctx['record']['native_thread_id']=await client.new_thread('/project/work')
        self.runtime.monitor_task=asyncio.create_task(self.runtime.monitor())
        with patch.object(self.runtime,'attach',AsyncMock(return_value='first')):
            # attach is only awaited once: these scenarios exercise recovery in
            # this same context, not successor launch.
            runner=asyncio.create_task(self.runtime.run_task('primary'))
            self.runtime.turns['primary']=runner
            await asyncio.sleep(0)
        return runner,process

    async def until(self,predicate):
        async def poll():
            while not predicate(): await asyncio.sleep(.01)
        await asyncio.wait_for(poll(),3)

    async def test_missing_usage_during_multi_tool_turn_interrupts_and_recovers(self):
        runner,process=await self.start_fixture('recover')
        record=self.ctx['record']
        await self.until(lambda: record.get('measured_inference_count')==6)
        self.assertIsNone(process.returncode)
        self.assertFalse(runner.done())
        self.assertEqual(record['measurement_gap']['native_inference_count'],4)
        self.assertEqual(record['measurement_gap']['measured_inference_count'],2)
        self.assertEqual(record['measurement']['status'],'measured')
        self.assertEqual(self.runtime.state['tasks']['primary']['operational_state'],'working')
        self.assertNotIn('context_error',self.runtime.state['tasks']['primary'])
        self.assertEqual(self.interruption_states,['telemetry_recovery'])
        await self.runtime.block_and_cleanup('Explicit engineering pause')
        await asyncio.wait_for(runner,2)
        self.assertEqual(process.returncode,-9)

    async def test_missing_usage_during_multi_tool_turn_fails_if_recovery_stays_unmeasured(self):
        runner,process=await self.start_fixture('lost')
        await asyncio.wait_for(runner,3)
        task=self.runtime.state['tasks']['primary']
        self.assertEqual(task['operational_state'],'failed')
        self.assertEqual(self.interruption_states,['telemetry_recovery'])
        self.assertIn('Reliable context telemetry unavailable',task['context_error'])
        self.assertTrue(self.ctx['record']['cleanup_ok'])
        self.assertIsNotNone(process.returncode)
        self.assertEqual(self.runtime.state['scientific_status'],'preliminary')
        self.assertFalse((self.runtime.project/'STOP').exists())
        self.assertFalse((self.runtime.project/'COMPLETE').exists())

    async def test_late_usage_before_interrupted_completion_still_runs_recovery(self):
        runner,process=await self.start_fixture('late')
        record=self.ctx['record']
        await self.until(lambda: record.get('measured_inference_count')==6)
        await asyncio.sleep(.2)  # ordinary post-recovery wait must not be re-interrupted
        self.assertIsNone(process.returncode)
        self.assertFalse(runner.done())
        self.assertEqual(self.interruption_states,['telemetry_recovery'])
        self.assertEqual(record['measurement_gap']['native_inference_count'],4)
        self.assertEqual(self.recovery_event_states,[True])
        self.assertEqual(record['measurement']['status'],'measured')
        self.assertFalse(self.ctx['lifecycle_event'].is_set())
        self.assertEqual(self.runtime.state['tasks']['primary']['operational_state'],'working')
        await self.runtime.block_and_cleanup('Explicit engineering pause')
        await asyncio.wait_for(runner,2)

    async def test_late_usage_does_not_replace_a_missing_recovery_measurement(self):
        runner,process=await self.start_fixture('late-lost')
        await asyncio.wait_for(runner,3)
        self.assertEqual(self.interruption_states,['telemetry_recovery'])
        self.assertEqual(self.recovery_event_states,[True])
        self.assertIn('Reliable context telemetry unavailable',
                      self.runtime.state['tasks']['primary']['context_error'])
        self.assertTrue(self.ctx['record']['cleanup_ok'])
        self.assertIsNotNone(process.returncode)

    async def test_idle_job_wait_does_not_expire_a_valid_measurement(self):
        runner,process=await self.start_fixture('idle')
        record=self.ctx['record']
        await self.until(lambda: record.get('measured_inference_count')==2)
        await asyncio.sleep(.35)  # several actual monitor polls; no new inference
        self.assertFalse(runner.done())
        self.assertIsNone(process.returncode)
        self.assertNotIn('measurement_gap',record)
        self.assertEqual(self.interruption_states,[])
        self.assertEqual(record['measurement']['status'],'measured')
        self.assertEqual(self.runtime.state['tasks']['primary']['operational_state'],'working')
        await self.runtime.block_and_cleanup('Explicit engineering pause')
        await asyncio.wait_for(runner,2)

    async def test_lost_native_boundary_evidence_is_visible_and_cannot_reset_coverage(self):
        runner,process=await self.start_fixture('idle')
        await self.until(lambda:self.ctx['record'].get('measured_inference_count')==2)
        trace=self.ctx['auth']/'native-trace/fixture/trace.jsonl'
        trace.write_text(trace.read_text().splitlines()[0]+'\n')
        await asyncio.wait_for(runner,3)
        await self.until(lambda:self.runtime.state.get('cleanup_ok'))
        self.assertIn('evidence regressed',self.ctx['record']['inventory_error'])
        self.assertEqual(self.ctx['record']['native_inference_count'],2)
        self.assertTrue(self.ctx['record']['cleanup_ok'])
        self.assertIsNotNone(process.returncode)
        self.assertEqual(self.runtime.state['scientific_status'],'preliminary')
        self.assertFalse((self.runtime.project/'STOP').exists())
