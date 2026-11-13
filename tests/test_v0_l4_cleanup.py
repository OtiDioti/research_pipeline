"""Scientific finalization failures and real local process groups, NOT native proof."""
import asyncio
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import sys
import time
from unittest.mock import AsyncMock, patch

from tests.test_v0_l4 import DecisionFixture
from tests.test_v0_l2 import handoff
from tests.test_quota import payload
from research_pipeline import cli, collaboration, isolation, jobs, workspace


class CleanupTests(DecisionFixture):
    async def agreed(self, intent='COMPLETE'):
        proposal = await self.propose(intent, ('answered',) if intent == 'COMPLETE' else ('unresolved',))
        await self.review(proposal, agree=intent == 'COMPLETE')
        return proposal

    async def assert_failed_finalization(self, proposal):
        await self.finalize(proposal)
        self.assertFalse(await self.runtime.shutdown_task)
        self.assertFalse(self.state.get('terminal_committed'))
        self.assertFalse(self.state['finalization_ok'])
        self.assertTrue(self.primary['record']['cleanup_ok'])
        self.assertFalse((self.project/'COMPLETE_ACK').exists())
        self.assertFalse((self.project/'STOP_ACK').exists())

    async def test_missing_handoff_after_final_request_still_cleans_and_no_ack(self):
        proposal = await self.agreed('STOP')
        await self.finalize(proposal)
        (self.primary['drafts']/'handoffs/primary.md').unlink()
        self.assertFalse(await self.runtime.shutdown_task)
        self.assertTrue(self.primary['record']['cleanup_ok'])
        self.assertIn('handoff', self.state['terminal_error'])
        self.assertIn('unpromising', (self.project/'STOP').read_text())
        self.assertIn('"cleanup_confirmed": true', (self.project/'STOP').read_text())
        self.assertFalse((self.project/'STOP_ACK').exists())
        self.assertEqual(self.state['state'], 'failed')

    async def test_snapshot_failure_still_interrupts_all_contexts(self):
        proposal = await self.agreed()
        with patch.object(self.runtime.documents, 'capture', side_effect=OSError('snapshot disk full')):
            await self.assert_failed_finalization(proposal)
        self.assertTrue(all(r['cleanup_ok'] for r in self.state['contexts'].values()))

    async def test_retirement_checkpoint_failure_still_stops_context_and_retains_slot(self):
        task = self.runtime.add_task('task-' + 'a'*32, 'Unfinished delegate', 'primary')
        from tests.test_review_repairs import context_fixture
        ctx = context_fixture(self.runtime, 'delegate', task_id=task['task_id'])
        with patch.object(self.runtime, 'save', side_effect=OSError('checkpoint disk full')):
            result = await self.runtime.control(self.primary, 'retire_task', task['task_id'])
            self.assertEqual(result['status'], 'retirement_pending')
            await asyncio.gather(*self.runtime.lifecycle_tasks)
        self.assertTrue(ctx['record']['cleanup_ok'])
        self.assertFalse(task.get('released'))
        self.assertIn('checkpoint disk full', task['persistence_error'])

    async def test_failed_preferred_native_checkpoint_does_not_disable_retirement_cleanup(self):
        task = self.runtime.add_task('task-' + 'a'*32, 'Unfinished delegate', 'primary')
        from tests.test_review_repairs import context_fixture
        ctx = context_fixture(self.runtime, 'delegate', task_id=task['task_id'])
        self.runtime.draft(ctx, task['workspace']+'/NOTE.md', '# Useful partial finding')
        self.save_handoff(ctx)
        runner = asyncio.create_task(asyncio.sleep(0))
        self.runtime.turns[task['task_id']] = runner
        await runner
        with patch.object(self.runtime, 'native_turn', AsyncMock(side_effect=isolation.RuntimeUnavailable('checkpoint interrupted'))) as turn:
            await self.runtime.control(self.primary, 'retire_task', task['task_id'])
            await asyncio.gather(*self.runtime.lifecycle_tasks)
            turn.assert_awaited_once()
        self.assertTrue(ctx['record']['cleanup_ok'])
        self.assertFalse(task.get('released'))
        self.assertIn('checkpoint interrupted', task['retirement_checkpoint_error'])

    async def test_runtime_state_save_failure_still_stops_process_owners(self):
        proposal = await self.agreed('STOP')
        # Request is durably accepted before the injected checkpoint failure.
        await self.finalize(proposal)
        with patch.object(self.runtime, 'save', side_effect=OSError('runtime state disk full')):
            self.assertFalse(await self.runtime.shutdown_task)
        self.assertTrue(self.primary['record']['cleanup_ok'])
        self.assertFalse((self.project/'STOP_ACK').exists())
        self.assertIn('unpromising', (self.project/'STOP').read_text())

    async def test_status_write_failure_never_acknowledges(self):
        proposal = await self.agreed()
        original = workspace.atomic_text
        def write(path, text):
            if path.name == 'RESEARCH_STATUS.md':
                raise OSError('status disk full')
            return original(path, text)
        with patch.object(workspace, 'atomic_text', side_effect=write):
            await self.assert_failed_finalization(proposal)
        self.assertIn('status disk full', str(self.state['terminal_persistence_errors']))

    async def test_marker_write_failure_never_acknowledges(self):
        proposal = await self.agreed()
        original = workspace.atomic_text
        def write(path, text):
            if path.name == 'COMPLETE': raise OSError('marker disk full')
            return original(path, text)
        with patch.object(workspace, 'atomic_text', side_effect=write):
            await self.assert_failed_finalization(proposal)
        self.assertFalse((self.project/'COMPLETE').exists())
        await self.runtime.block_and_cleanup('Later human pause')
        self.assertEqual(self.state['state'], 'failed')
        self.assertFalse(self.state.get('terminal_committed'))

    async def test_ack_write_failure_is_truthful_and_cleanup_remains_confirmed(self):
        proposal = await self.agreed()
        original = workspace.atomic_text
        def write(path, text):
            if path.name == 'COMPLETE_ACK': raise OSError('ack disk full')
            return original(path, text)
        with patch.object(workspace, 'atomic_text', side_effect=write):
            await self.assert_failed_finalization(proposal)
        self.assertIn('ack disk full', self.state['persistence_error'])

    async def test_quota_cutoff_preempts_pending_scientific_finalization(self):
        proposal = await self.agreed()
        await self.finalize(proposal)
        self.runtime.observe_quota('first', payload(85), provenance='injected-L4-cutoff-fixture')
        self.assertTrue(await self.runtime.shutdown_task, self.state)
        self.assertEqual(self.state['stop_origin'], 'quota')
        self.assertEqual(self.state['state'], 'quota_stopped')
        self.assertFalse((self.project/'COMPLETE_ACK').exists())
        self.assertEqual((self.project/'STOP').read_bytes(), (self.project/'STOP_ACK').read_bytes())
        self.assertIn('No post-cutoff inference', (self.project/'STOP').read_text())

    async def test_missing_quota_telemetry_during_finalization_remains_operational(self):
        proposal = await self.agreed()
        await self.finalize(proposal)
        self.runtime.observe_quota('first', {}, full=True, provenance='injected-L4-telemetry-loss')
        self.assertTrue(await self.runtime.shutdown_task)
        self.assertEqual(self.state['state'], 'quota_unavailable')
        self.assertTrue(self.state['cleanup_ok'])
        self.assertEqual(self.state['requested_scientific_intent'], 'COMPLETE')
        self.assertFalse((self.project/'COMPLETE').exists())
        self.assertFalse((self.project/'STOP').exists())
        self.assertFalse(self.state.get('terminal_committed'))

    async def test_backend_operational_failure_preempts_pending_scientific_stop(self):
        proposal = await self.agreed('STOP')
        await self.finalize(proposal)
        self.runtime.schedule_shutdown('Backend production protocol failed', 'failed')
        self.assertTrue(await self.runtime.shutdown_task)
        self.assertEqual(self.state['state'], 'failed')
        self.assertTrue(self.state['cleanup_ok'])
        self.assertFalse((self.project/'STOP_ACK').exists())
        self.assertIn('"actual_outcome": "failed"', (self.project/'STOP').read_text())

    async def test_cli_operational_failure_is_unsuccessful_and_preserves_stop_rationale(self):
        async def run(task_id):
            if task_id != 'primary':
                return
            proposal = await self.agreed('STOP')
            await self.finalize(proposal)
            self.runtime.schedule_shutdown('Backend production protocol failed', 'failed')
        output = io.StringIO()
        with patch.object(collaboration.Coordinator, 'initialize', return_value=self.runtime), \
             patch.object(self.runtime, 'start', AsyncMock()), \
             patch.object(self.runtime, 'run_task', side_effect=run), redirect_stdout(output):
            code = await cli.run(self.project, self.runtime.config)
        self.assertEqual(code, 1)
        self.assertIn('outcome=failed', output.getvalue())
        self.assertIn('finalization confirmed=False', output.getvalue())
        self.assertIn('unpromising', output.getvalue())
        self.assertFalse((self.project/'STOP_ACK').exists())

    async def test_quota_cutoff_interrupts_opposition_without_waiting_for_review(self):
        proposal = await self.propose()
        opponent = self.opponent_context()
        self.runtime.observe_quota('first', payload(85), provenance='injected-L4-cutoff-fixture')
        self.assertTrue(await self.runtime.shutdown_task)
        self.assertTrue(opponent['record']['cleanup_ok'])
        self.assertNotIn('review', proposal)
        self.assertFalse((self.project/'COMPLETE').exists())

    async def test_final_quiescent_revision_requires_reassessment(self):
        proposal = await self.agreed()
        await self.finalize(proposal)
        # A writer finishes with changed code after the request, before commitment.
        (self.project/'work/check.py').write_text('assert False\n')
        self.assertFalse(await self.runtime.shutdown_task)
        self.assertEqual(self.state['state'], 'reassessment_required')
        self.assertTrue(self.state['cleanup_ok'])
        self.assertFalse((self.project/'COMPLETE').exists())
        self.assertFalse((self.project/'STOP').exists())

    async def test_human_status_edit_is_preserved_and_prevents_unqualified_success(self):
        proposal = await self.agreed()
        path = self.project/'RESEARCH_STATUS.md'
        path.write_text('# Human corrected interpretation\nKeep this exactly.')
        await self.assert_failed_finalization(proposal)
        self.assertEqual(path.read_text(), '# Human corrected interpretation\nKeep this exactly.')

    async def test_backend_interrupt_failure_does_not_override_confirmed_service_termination(self):
        proposal = await self.agreed()
        client = self.runtime.clients['first']
        client.active_turn_id = 'active'
        client.interrupt = AsyncMock(side_effect=isolation.RuntimeUnavailable('interrupt RPC lost'))
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state)
        self.assertTrue(self.state['cleanup_ok'])
        self.assertIn('interrupt RPC lost', self.primary['record']['interrupt_error'])

    async def test_backend_close_failure_falls_back_to_owned_service_cleanup(self):
        proposal = await self.agreed()
        self.runtime.clients['first'].close = AsyncMock(side_effect=isolation.RuntimeUnavailable('backend close failed'))
        with patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed': True, 'reason': 'owned service stopped'})) as stop:
            await self.finalize(proposal)
            self.assertTrue(await self.runtime.shutdown_task, self.state)
            stop.assert_awaited_once()

    async def test_unconfirmed_owner_retains_uncertainty_without_ack(self):
        proposal = await self.agreed('STOP')
        self.runtime.clients['first'].close = AsyncMock(return_value={'confirmed': False, 'reason': 'ownership uncertain'})
        await self.finalize(proposal)
        self.assertFalse(await self.runtime.shutdown_task)
        self.assertFalse(self.state['cleanup_ok'])
        self.assertEqual(self.state['tasks']['primary']['context_id'], 'first')
        self.assertFalse((self.project/'STOP_ACK').exists())

    async def test_matching_terminal_marker_required_by_saved_inspection_and_pause(self):
        proposal = await self.agreed()
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task)
        saved = collaboration.load_state(self.project)
        self.assertTrue(saved['terminal_committed'])
        self.assertEqual(await cli.pause_async(self.project), 0)
        self.assertEqual(collaboration.load_state(self.project)['state'], 'complete')
        (self.project/'COMPLETE_ACK').write_text('mismatched acknowledgement')
        saved = collaboration.load_state(self.project)
        self.assertFalse(saved['terminal_committed'])
        self.assertFalse(saved['finalization_ok'])
        self.assertIn('no matching marker', saved['terminal_error'])

    async def test_real_agent_job_descendants_and_partial_output_survive_failed_saving(self):
        proposal = await self.agreed('STOP')
        processes = []
        children = []
        # Two actual owned local process groups represent context and durable job.
        # They do not substitute for production cgroup/native acceptance.
        script = """import subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
Path('child.pid').write_text(str(child.pid))
Path('partial.txt').write_text('retained useful partial output')
print('ready', flush=True)
time.sleep(120)
"""
        async def start(name):
            root = self.project/'work'/name
            root.mkdir()
            process = await asyncio.create_subprocess_exec(sys.executable, '-u', '-c', script,
                cwd=root, start_new_session=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            processes.append(process)
            self.assertEqual(await asyncio.wait_for(process.stdout.readline(), 3), b'ready\n')
            children.append(int((root/'child.pid').read_text()))
            return process, root
        async def stop(process):
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGTERM)
                await process.communicate()
            return {'confirmed': True, 'reason': 'Local process group terminated; NOT native cgroup proof'}
        try:
            agent, agent_root = await start('agent-process')
            job, job_root = await start('job-process')
            self.runtime.clients['first'].close = lambda: stop(agent)
            record = {'job_id': 'fixture', 'task_id': 'primary', 'state': 'running',
                      'cleanup_ok': False, 'result_path': str(job_root/'result.json'),
                      'deadline': time.monotonic()+7200, 'service': {'fixture': 'local-job'}}
            self.state['jobs']['fixture'] = record
            jobs.atomic(job_root/'result.json', {'stdout': 'partial stdout retained'})
            self.runtime.draft(self.primary, 'handoffs/primary.md',
                               handoff(self.state['tasks']['primary'], job_ids=['fixture']))
            await self.finalize(proposal)
            async def stop_job(owner):
                return await stop(job)
            with patch.object(isolation, 'stop_owned', side_effect=stop_job), \
                 patch.object(self.runtime, 'save', side_effect=OSError('state disk full')):
                self.assertFalse(await self.runtime.shutdown_task)
            self.assertTrue(self.state['cleanup_ok'], self.state.get('cleanup'))
            for process in processes:
                self.assertIsNotNone(process.returncode)
            for pid in children:
                path = Path(f'/proc/{pid}/stat')
                self.assertTrue(not path.exists() or path.read_text().split()[2] == 'Z')
            for root in (agent_root, job_root):
                self.assertEqual((root/'partial.txt').read_text(), 'retained useful partial output')
            self.assertEqual(record['stdout'], 'partial stdout retained')
            self.assertFalse((self.project/'STOP_ACK').exists())
        finally:
            for process in processes:
                if process.returncode is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.communicate()
