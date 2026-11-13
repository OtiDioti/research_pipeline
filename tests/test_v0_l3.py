"""L3 admission/cleanup races and warning delivery. Doubles are explicitly local."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.quota_fixture import PAYLOAD, sufficient
from tests.test_context_usage import params
from tests.test_quota import payload
from tests.test_review_repairs import context_fixture, make_project
from tests.test_v0_l1 import owner
from research_pipeline import app_server, cli, codex, collaboration, isolation, jobs, quota, staleness, workspace


class L3Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = collaboration.Coordinator.initialize(make_project(Path(self.tmp.name)), isolation.Config())
        self.state = self.runtime.state

    async def asyncTearDown(self):
        await self.runtime.block_and_cleanup('Engineering fixture cleanup')
        await self.runtime.close()

    def primary(self):
        sufficient(self.runtime)
        ctx = context_fixture(self.runtime)
        ctx['record']['native_thread_id'] = 'native-primary'
        self.runtime.quota_transport = 'first'
        return ctx

    def secondary(self, now=0):
        task = self.runtime.add_task('task-'+'a'*32, 'Public independent check', 'primary', 'opponent')
        ctx = context_fixture(self.runtime, 'secondary', task_id=task['task_id'])
        ctx['record'].update(native_thread_id='native-secondary', staleness=staleness.attach(now))
        self.runtime.observe_context('secondary', params(length=10000, thread='native-secondary'), now=now)
        return ctx

    async def test_no_preflight_blocks_tasks_contexts_jobs_and_inference(self):
        with self.assertRaisesRegex(jobs.JobError, 'quota'):
            self.runtime.add_task('task-'+'a'*32, 'No admission', 'primary')
        with self.assertRaisesRegex(jobs.JobError, 'quota'):
            await self.runtime.attach('secondary')
        with self.assertRaisesRegex(jobs.JobError, 'quota'):
            await self.runtime.jobs.run('primary', 'absent', ['true'], '/project/work', 20)
        ctx = context_fixture(self.runtime)
        with self.assertRaisesRegex(jobs.JobError, 'quota'):
            await self.runtime.native_turn('first', 'No inference')
        self.runtime.clients['first'].turn.assert_not_awaited()
        self.assertEqual(len(self.state['contexts']), 1)
        self.assertFalse(self.state['jobs'])
        self.assertFalse((self.runtime.project/'STOP').exists())

    async def test_cutoff_between_turn_scheduling_and_dispatch_prevents_native_turn(self):
        self.primary()
        client = self.runtime.clients['first']
        client.read_quota = AsyncMock(return_value=PAYLOAD)
        scheduled = asyncio.Event()
        create_task = asyncio.create_task
        def schedule_with_ready_cutoff(coro, *args, **kwargs):
            if not scheduled.is_set():
                scheduled.set()
                # Model an already-ready notification ahead of the newly queued
                # inference coroutine, without changing the event-loop clock.
                asyncio.get_running_loop().call_soon(
                    self.runtime.observe_quota, 'first', payload(85))
            return create_task(coro, *args, **kwargs)
        with patch.object(asyncio,'create_task',side_effect=schedule_with_ready_cutoff):
            with self.assertRaisesRegex(jobs.JobError,'STOP'):
                await self.runtime.native_turn('first','No inference after queued cutoff',responsive=False)
        self.assertTrue(scheduled.is_set())
        client.turn.assert_not_awaited()
        self.assertTrue(await self.runtime.shutdown_task)

    async def test_only_primary_events_control_shared_allowance_and_stop_latches(self):
        self.primary()
        self.secondary()
        await self.runtime.context_event('secondary', {'method': 'account/rateLimits/updated', 'params': payload(99)})
        self.assertFalse(self.state['admission_block'])
        # Primary transport reports account consumption, regardless of which role used it.
        await self.runtime.context_event('first', {'method': 'account/rateLimits/updated', 'params': payload(85)})
        self.assertTrue(self.state['admission_block'])  # synchronous, before yielding to shutdown
        shutdown = self.runtime.shutdown_task
        first = deepcopy(self.state['quota']['cutoff'])
        self.runtime.observe_quota('first', payload(1), full=True)
        self.assertIs(self.runtime.shutdown_task, shutdown)
        self.assertEqual(self.state['quota']['cutoff'], first)
        self.assertTrue(await shutdown)
        self.assertEqual(self.state['state'], 'quota_stopped')
        self.assertEqual(self.state['scientific_status'], 'preliminary')
        self.assertEqual((self.runtime.project/'STOP').read_bytes(), (self.runtime.project/'STOP_ACK').read_bytes())
        for client in self.runtime.clients.values():
            client.turn.assert_not_awaited()
        self.assertFalse((self.runtime.project/'COMPLETE').exists())
        self.assertTrue(all(r['cleanup_ok'] for r in self.state['contexts'].values()))
        for action in (lambda: self.runtime.add_task('task-'+'b'*32, 'No reopen', 'primary'),
                       lambda: workspace.validate_fresh(self.runtime.project, True)):
            with self.assertRaises(ValueError): action()

    async def test_polling_reads_only_current_primary_transport(self):
        self.primary()
        self.secondary()
        observed = asyncio.Event()
        async def read():
            observed.set()
            return PAYLOAD
        primary = self.runtime.clients['first']
        secondary = self.runtime.clients['secondary']
        primary.read_quota = AsyncMock(side_effect=read)
        secondary.read_quota = AsyncMock(return_value=payload(99))
        with patch.object(quota,'POLL_SECONDS',0):
            polling = asyncio.create_task(self.runtime.monitor_quota())
            try:
                await asyncio.wait_for(observed.wait(),2)
            finally:
                polling.cancel()
                await asyncio.gather(polling,return_exceptions=True)
        self.assertGreaterEqual(primary.read_quota.await_count,1)
        secondary.read_quota.assert_not_awaited()
        self.assertFalse(self.state['admission_block'])

    async def test_missing_read_is_operational_failure_without_quota_marker(self):
        self.primary()
        self.runtime.clients['first'].read_quota = AsyncMock(return_value={})
        with self.assertRaisesRegex(jobs.JobError, 'quota'):
            await self.runtime.refresh_quota('first')
        self.assertTrue(await self.runtime.shutdown_task)
        self.assertEqual(self.state['state'], 'quota_unavailable')
        self.assertNotIn('cutoff', self.state['quota'])
        self.assertFalse((self.runtime.project/'STOP').exists())

    async def test_invalid_read_and_serialization_failure_cannot_disable_cleanup(self):
        self.primary()
        ctx = self.runtime.contexts['first']
        self.runtime.clients['first'].read_quota = AsyncMock(return_value=payload(float('nan')))
        with patch.object(self.runtime,'save',side_effect=ValueError('runtime record serialization rejected')):
            with self.assertRaises(jobs.JobError):
                await self.runtime.refresh_quota('first')
            self.assertFalse(await self.runtime.shutdown_task)
        self.assertTrue(ctx['record']['cleanup_ok'])
        self.assertTrue(self.state['cleanup_ok'])
        self.assertFalse(self.state['finalization_ok'])
        self.assertFalse((self.runtime.project/'STOP').exists())

    async def test_invalid_weekly_notification_blocks_operation_without_observed_cutoff(self):
        self.primary()
        self.runtime.observe_quota('first',payload(-1),full=False)
        self.assertTrue(self.state['admission_block'])
        self.assertNotIn('cutoff',self.state['quota'])
        self.assertTrue(await self.runtime.shutdown_task)
        self.assertEqual(self.state['state'],'quota_unavailable')
        self.assertFalse((self.runtime.project/'STOP').exists())

    async def test_primary_transport_replacement_blocks_until_fresh_read_and_ignores_retired_events(self):
        self.primary()
        await self.runtime.close_context('first')
        self.assertIn('transport', quota.admission_error(self.state))
        next_ctx = context_fixture(self.runtime, 'next')
        self.runtime.quota_transport = 'next'
        self.runtime.observe_quota('first', payload(99), full=False)
        self.assertFalse(self.state['admission_block'])
        self.runtime.clients['next'].read_quota = AsyncMock(return_value=payload(35))
        await self.runtime.refresh_quota('next')
        self.assertIsNone(quota.admission_error(self.state))
        self.runtime.observe_quota('next', payload(85), full=False)
        with self.assertRaisesRegex(jobs.JobError, 'STOP'):
            await self.runtime.native_turn('next', 'No post-cutoff save turn', responsive=False)
        self.runtime.clients['next'].turn.assert_not_awaited()
        await self.runtime.shutdown_task
        self.assertTrue(next_ctx['record']['cleanup_ok'])

    async def test_secondary_turn_waits_through_primary_transport_gap_without_retiring_work(self):
        self.primary()
        secondary = self.secondary()
        await self.runtime.close_context('first')
        client = self.runtime.clients['secondary']
        client.turn.return_value = {'id':'secondary-turn','status':'completed'}
        with patch.object(self.runtime,'validate_inventory',return_value=True):
            work = asyncio.create_task(self.runtime.native_turn('secondary','Continue existing work'))
            await asyncio.sleep(0)
            self.assertFalse(work.done())
            client.turn.assert_not_awaited()
            self.assertFalse(secondary['record']['cleanup_ok'])
            self.assertFalse(self.state['admission_block'])
            context_fixture(self.runtime,'next')
            self.runtime.quota_transport = 'next'
            async def successor_read():
                self.runtime.observe_quota('next',{'rateLimits':{'limitId':None,'planType':'pro'}})
                self.assertFalse(self.state['admission_block'])
                self.assertFalse(work.done())
                return PAYLOAD
            self.runtime.clients['next'].read_quota = AsyncMock(side_effect=successor_read)
            await self.runtime.refresh_quota('next')
            self.assertEqual((await asyncio.wait_for(work,2))['status'],'completed')
            client.turn.assert_awaited_once()
        self.assertFalse(secondary['record']['cleanup_ok'])
        self.assertNotIn('context_error',self.state['tasks'][secondary['record']['task_id']])

    async def test_secondary_dispatch_waits_when_primary_closes_after_turn_is_scheduled(self):
        self.primary()
        secondary = self.secondary()
        task_id = secondary['record']['task_id']
        task = self.state['tasks'][task_id]
        client = self.runtime.clients['secondary']
        root = self.runtime.project/'.research_pipeline/jobs/secondary'
        root.mkdir()
        job = {'job_id':'b'*32,'task_id':task_id,'origin_context_id':'secondary',
               'state':'running','cleanup_ok':False,'result_path':str(root/'result.json'),
               'deadline':time.monotonic()+7200,'service':owner(),'launch_count':1}
        self.state['jobs'][job['job_id']] = job
        original = deepcopy(job)
        scheduled, waiting, resumed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        preflight_started, release_preflight = asyncio.Event(), asyncio.Event()
        turn_end = asyncio.get_running_loop().create_future()
        create_task = asyncio.create_task
        wait_quota_ready = self.runtime.wait_quota_ready
        closing = preflight = None
        async def observe_wait():
            if self.state['quota'].get('transport_unavailable'):
                waiting.set()
            await wait_quota_ready()
        def schedule_with_primary_closure(coro, *args, **kwargs):
            nonlocal closing
            if coro.cr_code.co_name == 'dispatch_turn' and not scheduled.is_set():
                scheduled.set()
                # Run real primary closure ahead of this queued secondary turn,
                # after native_turn's initial admission wait already returned.
                closing = create_task(self.runtime.close_context('first'))
            return create_task(coro, *args, **kwargs)
        async def turn(text):
            if 'Measurement intake' in text:
                self.runtime.observe_context('secondary',params(length=10001,thread='native-secondary'))
                return {'id':'intake','status':'completed'}
            resumed.set()
            return await turn_end
        async def close():
            if not turn_end.done():
                turn_end.set_result({'id':'continuing','status':'interrupted'})
            return {'confirmed':True}
        client.turn = AsyncMock(side_effect=turn)
        client.close = AsyncMock(side_effect=close)
        cancel = AsyncMock(wraps=self.runtime.jobs.cancel)
        with patch.object(asyncio,'create_task',side_effect=schedule_with_primary_closure), \
             patch.object(self.runtime,'wait_quota_ready',side_effect=observe_wait), \
             patch.object(self.runtime,'validate_inventory',return_value=True), \
             patch.object(self.runtime.jobs,'cancel',cancel), \
             patch.object(isolation,'stop_owned',AsyncMock(return_value={'confirmed':True})):
            runner = create_task(self.runtime.run_task(task_id))
            self.runtime.turns[task_id] = runner
            waiting_task = create_task(waiting.wait())
            try:
                done, _ = await asyncio.wait((runner,waiting_task),timeout=2,
                                             return_when=asyncio.FIRST_COMPLETED)
                self.assertNotIn('context_error',task)
                self.assertIn(waiting_task,done,'Scheduled secondary did not wait for quota transport replacement')
                await closing
                client.turn.assert_not_awaited()
                self.assertEqual(job,original)
                cancel.assert_not_awaited()
                context_fixture(self.runtime,'next')
                self.runtime.quota_transport = 'next'
                async def read():
                    preflight_started.set()
                    await release_preflight.wait()
                    return PAYLOAD
                self.runtime.clients['next'].read_quota = AsyncMock(side_effect=read)
                preflight = create_task(self.runtime.refresh_quota('next'))
                await asyncio.wait_for(preflight_started.wait(),2)
                client.turn.assert_not_awaited()
                self.assertFalse(runner.done())
                self.assertEqual(job,original)
                release_preflight.set()
                await preflight
                await asyncio.wait_for(resumed.wait(),2)
                self.assertEqual(task['operational_state'],'working')
                self.assertEqual(task['context_id'],'secondary')
                self.assertFalse(secondary['record']['cleanup_ok'])
                self.assertFalse(runner.done())
                self.assertFalse(self.state['admission_block'])
                self.assertIsNone(self.runtime.shutdown_task)
                self.assertEqual(job,original)
                cancel.assert_not_awaited()
            finally:
                release_preflight.set()
                waiting_task.cancel()
                await self.runtime.block_and_cleanup('Explicit secondary scheduling fixture cleanup')
                await asyncio.gather(*(t for t in (runner,waiting_task,closing,preflight) if t),
                                     return_exceptions=True)

    async def test_queued_assignment_sees_cutoff_inside_job_lock(self):
        ctx = self.primary()
        await self.runtime.jobs.lock.acquire()
        assignment = asyncio.create_task(self.runtime.control(ctx, 'delegate', 'work/ASSIGNMENT.md'))
        await asyncio.sleep(0)
        self.runtime.observe_quota('first', payload(85))
        self.runtime.jobs.lock.release()
        with self.assertRaisesRegex(jobs.JobError, 'STOP'):
            await assignment
        await self.runtime.shutdown_task
        self.assertEqual(list(self.state['tasks']), ['primary'])

    async def test_cutoff_during_job_reservation_prevents_command_release(self):
        self.primary()
        self.state['tasks']['primary']['inventory_verified'] = True
        self.runtime.allocation.slots = [{'unit':'test-slot.slice','cgroup':'/test/slot'}]*2
        released = []
        original_atomic = jobs.atomic
        def atomic(path, value):
            if path.name == 'launch.json': released.append(value)
            return original_atomic(path, value)
        async def capture(unit, group):
            self.runtime.observe_quota('first', payload(85))
            return owner(unit)
        with patch.object(isolation, 'command', AsyncMock(return_value='')), \
             patch.object(isolation, 'capture_ownership', side_effect=capture), \
             patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed':True})), \
             patch.object(jobs, 'atomic', side_effect=atomic):
            job = await self.runtime.jobs.run('primary','first',['true'],'/project/work',7200)
            self.assertEqual(job['state'],'cancelled')
            self.assertTrue(job['cleanup_ok'])
            self.assertFalse(released)
            self.assertTrue(await self.runtime.shutdown_task)
        self.assertEqual(len(self.state['jobs']),1)
        self.assertEqual(job['deadline'],job['admitted_monotonic']+7200)

    async def test_cutoff_resolves_active_nonresponsive_checkpoint_without_waiting_for_turn_end(self):
        self.primary()
        client = self.runtime.clients['first']
        client.read_quota = AsyncMock(return_value=PAYLOAD)
        ready = asyncio.Event()
        result = asyncio.get_running_loop().create_future()
        async def turn(text):
            ready.set()
            return await result
        async def close():
            if not result.done():
                result.set_exception(isolation.RuntimeUnavailable('Owned context closed'))
            return {'confirmed':True}
        client.turn = turn
        client.close = close
        client.active_turn_id = 'checkpoint-turn'
        client.interrupt = AsyncMock(side_effect=isolation.RuntimeUnavailable('No interrupt response'))
        work = asyncio.create_task(self.runtime.native_turn('first','Save checkpoint',responsive=False))
        await asyncio.wait_for(ready.wait(),2)
        self.runtime.observe_quota('first',payload(85))
        self.assertTrue(await asyncio.wait_for(self.runtime.shutdown_task,2))
        with self.assertRaisesRegex(isolation.RuntimeUnavailable,'closed'):
            await asyncio.wait_for(work,2)
        self.assertTrue(self.state['cleanup_ok'])

    async def test_warnings_leave_running_job_and_original_deadline_unchanged(self):
        self.primary()
        self.secondary()
        root = self.runtime.project/'.research_pipeline/jobs/local'
        root.mkdir()
        job = {'job_id':'b'*32,'task_id':'primary','state':'running','cleanup_ok':False,
               'result_path':str(root/'result.json'),'deadline':time.monotonic()+7200,
               'service':owner(),'launch_count':1}
        self.state['jobs'][job['job_id']] = job
        before = deepcopy(job)
        self.runtime.check_staleness(8100,'injected-clock')
        self.assertEqual(job,before)
        self.assertFalse(self.state['admission_block'])
        with patch.object(isolation,'stop_owned',AsyncMock(return_value={'confirmed':True})):
            await self.runtime.block_and_cleanup('Explicit engineering cleanup after warning assertions')

    async def test_secondary_warnings_survive_primary_rollover_and_delivery_races_without_stopping(self):
        self.primary()
        secondary = self.secondary()
        client = self.runtime.clients['first']
        client.active_turn_id = 'busy-turn'
        client.steer = AsyncMock(side_effect=isolation.RuntimeUnavailable('completed turn race'))
        warnings = self.runtime.check_staleness(8100, 'injected-clock')
        self.assertEqual([n['scheduled_seconds'] for n in warnings], [2700, 5400, 8100])
        self.assertNotIn('staleness', self.state['contexts']['first'])
        await self.runtime.deliver_staleness()
        pending = self.state['pending_staleness']['secondary']
        self.assertIn('race', pending['delivery_error'])
        self.assertFalse(self.state['admission_block'])
        self.assertFalse(secondary['record']['cleanup_ok'])
        await self.runtime.close_context('first')
        successor = context_fixture(self.runtime, 'next')
        successor['record']['input_changes'] = []
        self.assertIn('secondary', self.runtime.successor_documents('primary')['secondary_staleness'])
        result = await self.runtime.control(successor, 'check')
        self.assertEqual(result['secondary_staleness']['secondary']['elapsed_seconds'], 8100)
        self.runtime.quota_transport = 'next'
        self.runtime.clients['next'].read_quota = AsyncMock(return_value=PAYLOAD)
        await self.runtime.refresh_quota('next')
        client = self.runtime.clients['next']
        client.active_turn_id = 'fresh-turn'
        client.steer = AsyncMock(return_value={'turnId': 'fresh-turn'})
        await self.runtime.deliver_staleness()
        self.assertEqual(pending['delivered']['context_id'], 'next')
        self.assertFalse(self.state['admission_block'])
        self.runtime.observe_context('secondary', params(length=9999, thread='native-secondary'), now=8101)
        self.assertFalse(self.state['pending_staleness'])
        self.assertIn('changed', pending['superseded'])
        self.assertFalse(self.runtime.check_staleness(10800))
        self.assertEqual(len(self.runtime.check_staleness(10801)), 1)

    async def test_late_warning_responses_leave_primary_secondary_and_job_active(self):
        from tests import test_app_server
        primary = self.primary()
        secondary = self.secondary()
        # Real local JSON-RPC process; service/cgroup and job ownership here
        # remain explicit engineering doubles, not native production evidence.
        client = await test_app_server.ProtocolTests.fixture(self,'delayed-steer')
        self.runtime.clients['first'] = client
        primary['record']['native_thread_id'] = client.thread_id
        work = asyncio.create_task(client.turn('Remain active during delayed warning delivery'))
        await asyncio.wait_for(client.turn_ready.wait(),2)
        original_request = client.request
        async def short_steer_request(method, arguments, timeout=15):
            return await original_request(method,arguments,timeout=.01 if method == 'turn/steer' else timeout)
        client.request = short_steer_request
        root = self.runtime.project/'.research_pipeline/jobs/local'
        root.mkdir()
        job = {'job_id':'b'*32,'task_id':'primary','state':'running','cleanup_ok':False,
               'result_path':str(root/'result.json'),'deadline':time.monotonic()+7200,
               'service':owner(),'launch_count':1}
        self.state['jobs'][job['job_id']] = job
        before = deepcopy(job)
        self.runtime.check_staleness(2700,'injected-clock')
        notice = self.state['pending_staleness']['secondary']
        try:
            for late_error in (False, True):
                with self.subTest(late_error=late_error):
                    await self.runtime.deliver_staleness()
                    self.assertIn('timeout',notice['delivery_error'])
                    self.assertNotIn('delivered',notice)
                    # Release the old response before this new correlated reply:
                    # its successful round trip proves the reader survived.
                    await client.request('fixture/release-steer',{'error':late_error})
                    self.assertIsNone(client.failure)
                    self.assertFalse(work.done())
                    self.assertEqual(client.active_turn_id,'turn-double')
                    self.assertFalse(primary['record']['cleanup_ok'])
                    self.assertFalse(secondary['record']['cleanup_ok'])
                    self.assertEqual(job,before)
                    self.assertFalse(self.state['admission_block'])
                    self.assertIsNone(self.runtime.shutdown_task)
                    self.assertIs(self.state['pending_staleness']['secondary'],notice)
        finally:
            with patch.object(isolation,'stop_owned',AsyncMock(return_value={'confirmed':True})):
                await self.runtime.block_and_cleanup('Explicit local protocol fixture cleanup')
            await asyncio.gather(work,return_exceptions=True)

    async def test_quota_stop_preserves_edited_index_when_primary_draft_batch_is_invalid(self):
        ctx = self.primary()
        edited = '# Human navigation\n\n- A human addition that must survive STOP.\n'
        index = self.runtime.project/'work/FOLDER_CONTENT.md'
        index.write_text(edited)
        # Invalid scientific destinations prevent ordinary publication, including
        # its usual index preservation. STOP must preserve edits independently.
        forbidden = ctx['drafts']/'starting_evidence/FORBIDDEN.md'
        forbidden.parent.mkdir()
        forbidden.write_text('# Invalid draft destination')
        self.runtime.observe_quota('first',payload(85))
        self.assertFalse(await self.runtime.shutdown_task)
        self.assertTrue(self.state['cleanup_ok'])
        self.assertIn('publication_error',ctx['record'])
        preserved = list((self.runtime.project/'handoffs/preserved').rglob('*.md'))
        self.assertTrue(any(path.read_text() ==
            '<!-- Preserved human version: work/FOLDER_CONTENT.md -->\n\n' + edited for path in preserved))
        self.assertIn('Preserved edited index',index.read_text())
        self.assertTrue((self.runtime.project/'STOP').exists())
        self.assertFalse((self.runtime.project/'STOP_ACK').exists())

    async def test_save_snapshot_and_interrupt_failures_do_not_disable_cleanup_or_issue_ack(self):
        ctx = self.primary()
        client = self.runtime.clients['first']
        client.active_turn_id = 'busy'
        client.interrupt = AsyncMock(side_effect=isolation.RuntimeUnavailable('interrupt failed'))
        self.runtime.draft(ctx, 'work/PARTIAL.md', '# Useful partial calculation')
        with patch.object(self.runtime.documents, 'capture', side_effect=OSError('snapshot disk full')):
            self.runtime.observe_quota('first', payload(85))
            self.assertFalse(await self.runtime.shutdown_task)
        self.assertTrue(self.state['cleanup_ok'])
        self.assertFalse(self.state['finalization_ok'])
        self.assertTrue(ctx['record']['cleanup_ok'])
        self.assertIn('interrupt failed', ctx['record']['interrupt_error'])
        self.assertTrue((ctx['drafts']/'work/PARTIAL.md').exists())
        self.assertTrue((self.runtime.project/'STOP').exists())
        self.assertFalse((self.runtime.project/'STOP_ACK').exists())

    async def test_failed_stop_writes_and_uncertain_cleanup_retain_reason_and_reservations(self):
        self.primary()
        client = self.runtime.clients['first']
        client.close = AsyncMock(return_value={'confirmed': False, 'reason': 'Ownership unconfirmed'})
        original = workspace.atomic_text
        def fail_stop(path, text):
            if path.name == 'STOP': raise OSError('stop disk full')
            return original(path, text)
        with patch.object(workspace, 'atomic_text', side_effect=fail_stop):
            self.runtime.observe_quota('first', payload(85))
            self.assertFalse(await self.runtime.shutdown_task)
        self.assertEqual(self.state['stop_origin'], 'quota')
        self.assertEqual(self.state['state'], 'cleanup_unconfirmed')
        self.assertEqual(self.state['tasks']['primary']['context_id'], 'first')
        self.assertTrue(self.state['stop_persistence_errors'])
        self.assertFalse((self.runtime.project/'STOP_ACK').exists())

    async def test_stop_preserves_human_status_and_ack_write_failure_is_saved_truthfully(self):
        self.primary()
        status = self.runtime.project/'RESEARCH_STATUS.md'
        status.write_text('# Human scientific correction\nDo not overwrite.')
        original = workspace.atomic_text
        def fail_ack(path, text):
            if path.name == 'STOP_ACK': raise OSError('ack disk failure')
            return original(path, text)
        with patch.object(workspace,'atomic_text',side_effect=fail_ack):
            self.runtime.observe_quota('first',payload(85))
            self.assertFalse(await self.runtime.shutdown_task)
        self.assertEqual(status.read_text(),'# Human scientific correction\nDo not overwrite.')
        saved = collaboration.load_state(self.runtime.project)
        self.assertTrue(saved['cleanup_ok'])
        self.assertFalse(saved['finalization_ok'])
        self.assertIn('ack disk failure',saved['persistence_error'])
        self.assertTrue(saved['stop_status_preserved_human_edit'])
        self.assertFalse((self.runtime.project/'STOP_ACK').exists())

    async def test_real_owned_process_tree_stops_and_partial_output_survives_failed_saving(self):
        ctx = self.primary()
        root = self.runtime.project/'work'
        script = r'''import subprocess, sys, time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
Path('child.pid').write_text(str(child.pid))
Path('partial.txt').write_text('useful partial process output')
print('ready',flush=True)
try: time.sleep(120)
finally: child.terminate(); child.wait()
'''
        process = await asyncio.create_subprocess_exec(sys.executable, '-u', '-c', script, cwd=root,
            start_new_session=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            self.assertEqual(await asyncio.wait_for(process.stdout.readline(), 3), b'ready\n')
            child_pid = int((root/'child.pid').read_text())
            async def stop():
                os.killpg(process.pid, signal.SIGTERM)
                await process.communicate()
                # Zombies are terminated, awaiting their namespace/host reaper.
                stat = Path(f'/proc/{child_pid}/stat')
                async def terminated():
                    while stat.exists():
                        try:
                            if stat.read_text().split()[2] == 'Z': return
                        except FileNotFoundError:
                            return
                        await asyncio.sleep(.01)
                await asyncio.wait_for(terminated(), 2)
                return {'confirmed': True, 'reason': 'Local owned process group terminated; NOT native cgroup evidence'}
            self.runtime.clients['first'].close = stop
            with patch.object(self.runtime, 'save', side_effect=OSError('runtime record disk full')):
                self.runtime.observe_quota('first', payload(85))
                self.assertFalse(await self.runtime.shutdown_task)
            self.assertIsNotNone(process.returncode)
            self.assertTrue(self.state['cleanup_ok'], self.state)
            self.assertEqual((root/'partial.txt').read_text(), 'useful partial process output')
            self.assertFalse((self.runtime.project/'STOP_ACK').exists())
        finally:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                await process.communicate()


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_cutoff_during_job_inspection_prevents_thread_start(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = collaboration.Coordinator.initialize(make_project(Path(temp)),isolation.Config())
            inspected, release = asyncio.Event(), asyncio.Event()
            @contextmanager
            def auth(project):
                yield project/'.research_pipeline'
            async def inspect(task_id):
                inspected.set()
                await release.wait()
                return {'jobs':[]}
            backend = type('Client',(),{'start':AsyncMock(),'read_quota':AsyncMock(return_value=PAYLOAD),
                'new_thread':AsyncMock(return_value='native-test'),'request':AsyncMock(return_value={}),
                'close':AsyncMock(return_value={'confirmed':True}),'failure':None})()
            service = type('Service',(),{'ownership':{'fixture':True}})()
            try:
                with patch.object(codex,'private_auth',auth), \
                     patch.object(isolation,'bubblewrap_command',return_value=['--chdir','/home/researcher']), \
                     patch.object(isolation.RunningService,'start',AsyncMock(return_value=service)), \
                     patch.object(app_server,'Client',return_value=backend), \
                     patch.object(runtime.jobs,'inspect',side_effect=inspect), \
                     patch.object(codex,'validate_mcp_inventory',AsyncMock(return_value=[])):
                    attach = asyncio.create_task(runtime.attach('primary'))
                    await asyncio.wait_for(inspected.wait(),2)
                    runtime.observe_quota(runtime.quota_transport,payload(85))
                    release.set()
                    with self.assertRaisesRegex(jobs.JobError,'STOP'):
                        await asyncio.wait_for(attach,2)
                    backend.new_thread.assert_not_awaited()
                    self.assertTrue(await runtime.shutdown_task)
                    self.assertFalse(runtime.clients)
            finally:
                release.set()
                await runtime.block_and_cleanup('Explicit startup fixture cleanup')
                await runtime.close()

    async def test_cli_awaits_central_shutdown_and_reports_cutoff_and_save_failure(self):
        from contextlib import redirect_stdout
        import io
        for fail_save in (False, True):
            with self.subTest(fail_save=fail_save), tempfile.TemporaryDirectory() as temp:
                project = make_project(Path(temp))
                async def startup(runtime):
                    sufficient(runtime)
                    ctx = context_fixture(runtime)
                    ctx['record']['native_thread_id'] = 'native-fixture'
                    runtime.quota_transport = 'first'
                    client = runtime.clients['first']
                    client.read_quota = AsyncMock(return_value=PAYLOAD)
                    done = asyncio.get_running_loop().create_future()
                    async def turn(text):
                        runtime.observe_quota('first',payload(85),provenance='injected-cli-fixture')
                        return await done
                    async def close():
                        if not done.done():
                            done.set_exception(isolation.RuntimeUnavailable('Central fixture shutdown'))
                        return {'confirmed':True}
                    client.turn, client.close = turn, close
                    runtime.state['state'] = 'running'
                original = workspace.atomic_text
                def write(path, text):
                    if fail_save and path.name == 'STOP': raise OSError('STOP write failure')
                    return original(path, text)
                output = io.StringIO()
                with redirect_stdout(output), patch.object(collaboration.Coordinator,'start',startup), \
                     patch.object(workspace,'atomic_text',side_effect=write):
                    code = await asyncio.wait_for(cli.run(project,isolation.Config()),3)
                state = collaboration.load_state(project)
                self.assertEqual(code,1 if fail_save else 0)
                self.assertTrue(state['cleanup_ok'])
                self.assertEqual(state['finalization_ok'],not fail_save)
                self.assertIn('quota STOP',output.getvalue())
                self.assertNotIn('context_error',state['tasks']['primary'])
                self.assertEqual((project/'STOP_ACK').exists(),not fail_save)

    async def test_real_attach_preflight_before_thread_and_failed_admission_closes_transport(self):
        for data, allowed in ((PAYLOAD, True), ({}, False), (payload(85), False)):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as temp:
                runtime = collaboration.Coordinator.initialize(make_project(Path(temp)), isolation.Config())
                order = []
                @contextmanager
                def auth(project):
                    yield project/'.research_pipeline'
                async def read():
                    order.append('quota')
                    return data
                async def thread(*args):
                    order.append('thread')
                    return 'native-test'
                backend = type('Client', (), {'start': AsyncMock(), 'read_quota': AsyncMock(side_effect=read),
                    'new_thread': AsyncMock(side_effect=thread), 'request': AsyncMock(return_value={}),
                    'close': AsyncMock(return_value={'confirmed': True}), 'failure': None})()
                service = type('Service', (), {'ownership': {'fixture': True}})()
                try:
                    with patch.object(isolation, 'preflight'), patch.object(codex, 'verify_backend'), \
                         patch.object(runtime.allocation, 'create', AsyncMock(return_value={})), \
                         patch.object(codex, 'private_auth', auth), \
                         patch.object(isolation, 'bubblewrap_command', return_value=['--chdir','/home/researcher']), \
                         patch.object(isolation.RunningService, 'start', AsyncMock(return_value=service)), \
                         patch.object(app_server, 'Client', return_value=backend), \
                         patch.object(codex, 'validate_mcp_inventory', AsyncMock(return_value=[])):
                        if allowed:
                            await runtime.start()
                            self.assertEqual(order, ['quota','thread'])
                            self.assertEqual(len(runtime.clients), 1)
                            predecessor = runtime.state['tasks']['primary']['context_id']
                            await runtime.close_context(predecessor)
                            backend.read_quota.side_effect = None
                            backend.read_quota.return_value = payload(85)
                            with self.assertRaises(jobs.JobError):
                                await runtime.successor('primary')
                            await runtime.shutdown_task
                            self.assertEqual(order,['quota','thread'])
                            self.assertEqual(backend.new_thread.await_count,1)
                            self.assertEqual(runtime.state['stop_origin'],'quota')
                            self.assertEqual(runtime.state['state'],'quota_stopped')
                        else:
                            with self.assertRaises(jobs.JobError): await runtime.start()
                            await runtime.shutdown_task
                            self.assertEqual(order, ['quota'])
                            self.assertFalse(runtime.clients)
                            backend.close.assert_awaited_once()
                            self.assertEqual((runtime.project/'STOP').exists(), bool(runtime.state['quota'].get('cutoff')))
                finally:
                    await runtime.block_and_cleanup('Engineering fixture finished')
                    await runtime.close()


class PolicyConfigTests(unittest.TestCase):
    def test_human_interval_validation_and_terminal_marker_preservation(self):
        self.assertEqual(isolation.Config().secondary_staleness_seconds, 2700)
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError): isolation.Config(secondary_staleness_seconds=value).limits()
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            for name in ('STOP', 'STOP_ACK', 'COMPLETE', 'COMPLETE_ACK'):
                path = project/name
                path.write_text('Human preserved terminal explanation')
                with self.assertRaises(workspace.InputError): workspace.validate_fresh(project, True)
                self.assertEqual(path.read_text(), 'Human preserved terminal explanation')
                path.unlink()
