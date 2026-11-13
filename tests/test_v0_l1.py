"""Consequential L1 admission/ownership tests. Service doubles are NOT native proof."""
import asyncio
from contextlib import ExitStack, redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.quota_fixture import sufficient
from research_pipeline import cli, codex, collaboration, isolation, job_server, jobs, verification, workspace


def owner(unit='research-job-abc.service'):
    return {'unit': unit, 'invocation_id': 'a' * 32, 'cgroup': '/test/slot/' + unit,
            'boot_id': isolation.boot_identity()}


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        (self.project / 'starting_evidence').mkdir(parents=True)
        (self.project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Study public finite sums.')
        (self.project / 'AGENTS.md').write_text('Use public data.')
        self.config = isolation.Config()
        self.runtime = collaboration.Coordinator.initialize(self.project, self.config)
        sufficient(self.runtime)
        self.manager = self.runtime.jobs
        self.state = self.runtime.state
        self.runtime.allocation.slots = [{'unit': 'test-slot.slice', 'cgroup': '/test/slot'}] * 2
        self.task = self.state['tasks']['primary']
        self.task.update(context_id='first', inventory_verified=True)
        self.launches = []
        async def launch(*argv, **kwargs):
            records = list(self.state['jobs'].values())
            if records:
                saved = collaboration.load_state(self.project)['jobs'][records[-1]['job_id']]
                self.assertEqual(saved['state'], 'reserved')
                self.assertEqual(saved['launch_count'], 1)
            self.launches.append(argv)
            return ''
        self.command = patch.object(isolation, 'command', side_effect=launch).start()
        async def capture(unit, slice_group):
            return owner(unit)
        patch.object(isolation, 'capture_ownership', side_effect=capture).start()
        patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed': True, 'reason': 'engineering service double'})).start()
        patch.object(isolation, 'service_properties', AsyncMock(return_value={
            'LoadState': 'loaded', 'ActiveState': 'active', 'InvocationID': 'a'*32,
            'ControlGroup': '/test/slot/test.service', 'Result': 'success'})).start()
        self.addCleanup(patch.stopall)

    async def asyncTearDown(self):
        # Admission/service doubles have no actual namespaces; release their
        # private mount snapshots once the fixture ends.
        for mounts in self.manager.mount_stacks.values():
            mounts.close()
        self.manager.mount_stacks.clear()

    async def launch(self, duration=61, **kwargs):
        return await self.manager.run('primary', self.task['context_id'], ['python3', '-c', 'print(285)'], '/project/work', duration, **kwargs)

    async def test_long_timeouts_are_explicit_and_unchanged_after_replacement(self):
        for seconds in (61, 7200):
            record = await self.launch(seconds)
            self.assertEqual(record['deadline'], record['admitted_monotonic'] + seconds)
            original = {k: record[k] for k in ('deadline', 'job_id', 'service', 'launch_count', 'slot')}
            self.task['context_id'] = 'successor'
            observed = await self.manager.inspect('primary', record['job_id'])
            self.assertEqual({k: observed[k] for k in original}, original)
            await self.manager.cancel('primary', record['job_id'])
        self.assertEqual(len(self.launches), 2)
        self.assertIn('RuntimeMaxSec=', str(self.launches[1]))
        self.assertEqual(self.config.limits(), {'memory_mib': 2048, 'max_tasks': 128, 'max_agents': 2, 'max_jobs': 1, 'swap_bytes': 0})

    async def test_invalid_duration_owner_cwd_or_argv_never_launches(self):
        for invalid in (None, True, '61', 0, -1, float('nan'), float('inf'), 1e300, 1e-300):
            with self.subTest(runtime=invalid), self.assertRaises((ValueError, OverflowError)):
                await self.launch(invalid)
        for cwd in ('/tmp', '/project/starting_evidence', '/project/work/../outputs', '/project/work/missing', '/project/work/tasks'):
            with self.subTest(cwd=cwd), self.assertRaises(ValueError):
                await self.manager.run('primary', 'first', ['true'], cwd, 61)
        (self.project / 'work/link').symlink_to(self.project / 'outputs')
        with self.assertRaises(ValueError):
            await self.manager.run('primary', 'first', ['true'], '/project/work/link', 61)
        for argv in ([], 'true', [1], ['a\0b']):
            with self.assertRaises(ValueError):
                await self.manager.run('primary', 'first', argv, '/project/work', 61)
        with self.assertRaisesRegex(jobs.JobError, 'attachment'):
            await self.manager.run('primary', 'stale', ['true'], '/project/work', 61)
        self.task['inventory_verified'] = False
        with self.assertRaisesRegex(jobs.JobError, 'inventory'):
            await self.launch()
        self.assertFalse(self.state['jobs'])
        self.assertFalse(self.launches)

    async def test_capacity_counts_surviving_and_uncertain_jobs(self):
        first = await self.launch()
        self.task['context_id'] = 'successor'
        other = 'task-' + 'b'*32
        task = self.runtime.add_task(other, 'Independent public check', 'primary')
        task.update(context_id='other', inventory_verified=True)
        for state in jobs.ACTIVE:
            self.state['jobs'][first['job_id']]['state'] = state
            with self.assertRaisesRegex(jobs.JobError, 'capacity'):
                await self.manager.run(other, 'other', ['true'], '/project/' + task['workspace'], 7200)
        with self.assertRaisesRegex(jobs.JobError, 'cap'):
            self.runtime.add_task('task-'+'c'*32, 'excess', 'primary')
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(task['slot'], 1)
        self.assertEqual(self.task['slot'], 0)

    async def test_inspect_wait_cancel_all_enforce_logical_owner(self):
        record = await self.launch()
        for operation in (self.manager.inspect, self.manager.wait, self.manager.cancel):
            with self.assertRaisesRegex(jobs.JobError, 'logical owner'):
                await operation('task-'+'b'*32, record['job_id'])
        await self.manager.cancel('primary', record['job_id'])
        result = await self.manager.wait('primary', record['job_id'])
        self.assertEqual(result['state'], 'cancelled')
        self.assertTrue(result['cleanup_ok'])

    async def test_event_wait_disconnect_and_successor_collection_do_not_restart(self):
        first = await self.launch()
        waiting = asyncio.create_task(self.manager.wait('primary', first['job_id']))
        await asyncio.sleep(0)
        self.assertFalse(waiting.done())
        waiting.cancel()
        await asyncio.gather(waiting, return_exceptions=True)
        self.task['context_id'] = 'successor'
        successor = asyncio.create_task(self.manager.wait('primary', first['job_id']))
        await asyncio.sleep(0)
        await self.manager.cancel('primary', first['job_id'])
        result = await asyncio.wait_for(successor, 1)
        self.assertEqual(result['deadline'], first['deadline'])
        self.assertEqual(result['launch_count'], 1)
        self.assertEqual(len(self.launches), 1)

    async def test_lost_launch_ack_reserves_once_and_no_implicit_retry(self):
        self.command.side_effect = isolation.RuntimeUnavailable('systemd bus response lost')
        record = await self.launch()
        self.assertEqual(record['state'], 'cleanup_unconfirmed')
        self.assertEqual(record['launch_count'], 1)
        with self.assertRaisesRegex(jobs.JobError, 'capacity'):
            await self.launch()
        with patch.object(isolation, 'capture_ownership', side_effect=isolation.RuntimeUnavailable('missing service')):
            await self.manager.reconcile(self.state['jobs'][record['job_id']])
        self.assertFalse(self.state['jobs'][record['job_id']]['cleanup_ok'])
        self.assertEqual((await self.manager.wait('primary', record['job_id']))['state'], 'cleanup_unconfirmed')
        self.assertEqual(self.command.await_count, 1)

    async def test_supervisor_failure_is_visible_and_failed_cleanup_retains_capacity(self):
        record = await self.launch()
        with patch.object(isolation, 'service_properties', return_value={
            'LoadState': 'loaded', 'ActiveState': 'failed', 'InvocationID': 'a'*32, 'Result': 'signal'}), \
             patch.object(isolation, 'stop_owned', return_value={'confirmed': False, 'reason': 'bus unavailable'}):
            await self.manager.reconcile(self.state['jobs'][record['job_id']])
        result = self.state['jobs'][record['job_id']]
        self.assertEqual(result['state'], 'cleanup_unconfirmed')
        self.assertIn('Supervisor lost', result['reason'])
        with self.assertRaises(jobs.JobError):
            await self.launch()
        with patch.object(isolation, 'stop_owned', return_value={'confirmed': True, 'reason': 'owned group stopped'}):
            await self.manager.cancel('primary', record['job_id'])
        self.assertTrue(result['cleanup_ok'])

    async def test_result_cleanup_and_timeout_are_distinct_and_partial_outputs_survive(self):
        record = await self.launch()
        jobs.atomic(Path(record['result_path']), {'job_id': record['job_id'], 'finished': True,
                   'returncode': -9, 'stdout': 'useful partial output', 'stderr': 'diagnostic'})
        with patch.object(isolation, 'service_properties', return_value={
            'LoadState': 'loaded', 'ActiveState': 'failed', 'InvocationID': 'a'*32, 'Result': 'timeout'}):
            await self.manager.reconcile(self.state['jobs'][record['job_id']])
        result = await self.manager.wait('primary', record['job_id'])
        self.assertEqual(result['state'], 'timed_out')
        self.assertEqual(result['stdout'], 'useful partial output')
        self.assertTrue(result['cleanup_ok'])
        self.assertIsNone(self.state['admission_block'])
        self.assertEqual((await self.launch())['launch_count'], 1)

    async def test_supervision_query_and_invocation_failures_never_free_capacity(self):
        first = await self.launch()
        for response in (isolation.RuntimeUnavailable('bus lost'),
                         {'LoadState': 'loaded', 'ActiveState': 'active', 'InvocationID': 'foreign'}):
            with patch.object(isolation, 'service_properties', side_effect=response if isinstance(response, Exception) else None,
                              return_value=response):
                await self.manager.reconcile(self.state['jobs'][first['job_id']])
            self.assertEqual(self.state['jobs'][first['job_id']]['state'], 'cleanup_unconfirmed')
        with self.assertRaises(jobs.JobError):
            await self.launch()

    async def test_job_namespace_excludes_credentials_control_and_protected_writes(self):
        record = await self.launch()
        root = Path(record['result_path']).parent
        argv = jobs.read(root / 'request.json')['argv']
        self.assertIn('--clearenv', argv)
        self.assertIn('--unshare-pid', argv)
        self.assertIn('/run/research-job.json', argv)
        self.assertNotIn('/run/research-rpc', argv)
        self.assertNotIn('/opt/codex', argv)
        self.assertNotIn('auth.json', str(argv))
        self.assertNotIn('DBUS_SESSION_BUS_ADDRESS', str(argv))
        self.assertNotIn('/run/research-jobs.json', argv)
        self.assertIn('--tmpfs', argv)
        self.assertIn('/project/.research_pipeline', argv)
        self.assertNotIn(str(self.project / 'starting_evidence'), [argv[i+1] for i,a in enumerate(argv) if a == '--bind'])
        tool = jobs.read(root / 'tools.json')
        self.assertEqual(tool['activation'], record['job_id'])
        self.assertEqual(tool['deadline'], record['deadline'])
        self.assertNotEqual(tool['activation'], self.task['context_id'])

    async def test_block_is_latched_before_cleanup_even_if_cleanup_fails(self):
        record = await self.launch()
        async def stop(service):
            self.assertEqual(collaboration.load_state(self.project)['admission_block'], 'Human pause')
            return {'confirmed': False, 'reason': 'query failed'}
        with patch.object(isolation, 'stop_owned', side_effect=stop):
            self.assertFalse(await self.runtime.block_and_cleanup('Human pause'))
        with self.assertRaisesRegex(jobs.JobError, 'blocked'):
            await self.launch()
        self.assertEqual(self.state['state'], 'cleanup_unconfirmed')
        self.assertFalse(self.state['jobs'][record['job_id']]['cleanup_ok'])

    async def test_context_closure_preserves_jobs_and_releases_only_attachment(self):
        first = await self.launch()
        context = {'context_id': 'first', 'task_id': 'primary', 'service': owner('context.service'), 'state': 'attached'}
        root = self.project / '.research_pipeline/contexts/first'
        (root / 'drafts').mkdir(parents=True)
        server = type('Server', (), {'close': lambda self: None, 'wait_closed': AsyncMock()})()
        private = ExitStack()
        self.runtime.contexts['first'] = {'record': context, 'root': root, 'drafts': root/'drafts',
                         'server': server, 'private': private, 'baseline': workspace.science_fingerprints(self.project)}
        self.state['contexts']['first'] = context
        result = await self.runtime.close_context('first')
        self.assertTrue(result['confirmed'])
        self.assertIsNone(self.task['context_id'])
        self.assertEqual(self.state['jobs'][first['job_id']]['state'], 'running')
        self.assertFalse(self.state['jobs'][first['job_id']]['cleanup_ok'])
        self.assertEqual(self.state['jobs'][first['job_id']]['deadline'], first['deadline'])
        self.assertEqual(self.task['slot'], 0)
        await self.runtime.close_context('first')  # idempotent confirmed closure
        self.assertEqual(self.state['contexts']['first']['state'], 'closed')

    async def test_unconfirmed_predecessor_blocks_successor(self):
        with self.assertRaisesRegex(jobs.JobError, 'closure unconfirmed'):
            await self.runtime.successor('primary')
        self.task['context_id'] = None
        self.state['admission_block'] = 'cleanup uncertain'
        with self.assertRaisesRegex(jobs.JobError, 'blocked'):
            await self.runtime.successor('primary')

    async def test_scoped_drafts_human_edits_and_batch_validation(self):
        root = self.project / '.research_pipeline/drafts'
        root.mkdir()
        ctx = {'record': {'task_id': 'primary'}, 'drafts': root}
        note = self.project / 'work/NOTE.md'
        note.write_text('# Original')
        baseline = workspace.science_fingerprints(self.project)
        self.runtime.draft(ctx, 'work/NOTE.md', '# Proposed')
        note.write_text('# Human correction')
        for path in ('starting_evidence/RESEARCH_QUESTIONS.md', 'AGENTS.md', 'work/../../outside.md',
                     '.research_pipeline/run.md', 'work/tasks/task-'+'a'*32+'/NOTE.md', 'outputs/a.txt'):
            with self.assertRaises(ValueError):
                self.runtime.draft(ctx, path, 'bad')
        conflicts, _ = workspace.publish_drafts(self.project, root, baseline, [])
        self.assertEqual(note.read_text(), '# Human correction')
        self.assertEqual(conflicts[0]['path'], 'work/NOTE.md')
        self.assertTrue((self.project / conflicts[0]['proposal']).is_file())

    async def test_unstable_jobs_cannot_be_frozen_and_legacy_terminal_actions_rejected(self):
        ctx = {'record': {'task_id': 'primary'}, 'drafts': self.project / 'work'}
        for action in ('respond', 'close', 'complete', 'stop', 'rollover'):
            with self.assertRaisesRegex(jobs.JobError, 'V0-L4'):
                await self.runtime.control(ctx, action)
        await self.launch()
        with self.assertRaisesRegex(jobs.JobError, 'active computations'):
            await self.runtime.control(ctx, 'verify', 'work/PACKET.md')

    async def test_preparation_failure_proves_no_launch_and_does_not_occupy_capacity(self):
        with patch.object(self.manager, 'prepare', side_effect=OSError('unavailable mount')):
            failed = await self.launch()
        self.assertEqual(failed['state'], 'failed')
        self.assertTrue(failed['cleanup_ok'])
        self.assertEqual(failed['launch_count'], 0)
        self.assertFalse(self.launches)
        self.assertEqual((await self.launch())['state'], 'running')

    async def test_successful_cleanup_is_not_relabelled_when_publication_fails(self):
        first = await self.launch()
        jobs.atomic(Path(first['result_path']), {'job_id': first['job_id'], 'finished': True, 'returncode': 0,
                   'finished_monotonic': first['admitted_monotonic'] + 1, 'termination_cause': 'completed'})
        with patch.object(workspace, 'publish_drafts', side_effect=workspace.InputError('unsafe draft batch')):
            await self.manager.reconcile(self.state['jobs'][first['job_id']])
        result = await self.manager.wait('primary', first['job_id'])
        self.assertEqual(result['state'], 'completed')
        self.assertTrue(result['cleanup_ok'])
        self.assertIn('unsafe draft', result['publication_error'])

    async def test_snapshot_failure_does_not_disable_owned_process_cleanup(self):
        first = await self.launch()
        with patch.object(self.runtime, 'save', side_effect=OSError('disk full')), \
             patch.object(self.manager, 'save', side_effect=OSError('disk full')), \
             patch.object(isolation, 'stop_owned', return_value={'confirmed': True, 'reason': 'owned cgroup stopped'}) as stop:
            self.assertFalse(await self.runtime.block_and_cleanup('Human pause'))
            stop.assert_awaited_once()
        self.assertEqual(self.state['jobs'][first['job_id']]['state'], 'cancelled')
        self.assertTrue(self.state['jobs'][first['job_id']]['cleanup_ok'])
        self.assertIn('disk full', self.state['persistence_error'])

    async def test_actual_unix_rpc_wait_disconnect_and_stale_attachment(self):
        first = await self.launch()
        root = self.project / '.research_pipeline/rpc-fixture'
        root.mkdir()
        context = {'record': {'context_id': 'first', 'task_id': 'primary', 'state': 'attached'},
                   'token': 'test-token', 'inventory_ready': asyncio.Event()}
        context['inventory_ready'].set()
        server = await isolation.control_server(lambda r,w: self.runtime.handle_rpc(context,r,w), root)
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        async def rpc(token, operation, **arguments):
            reader, writer = await asyncio.open_unix_connection(f'/proc/self/fd/{directory_fd}/control.sock')
            writer.write((json.dumps({'token': token, 'operation': operation, 'arguments': arguments})+'\n').encode())
            await writer.drain()
            return reader, writer
        try:
            reader, writer = await rpc('foreign', 'job_status')
            self.assertIn('Revoked or foreign', (await reader.readline()).decode())
            writer.close(); await writer.wait_closed()
            reader, writer = await rpc('test-token', 'job_wait', job_id=first['job_id'])
            writer.close(); await writer.wait_closed()
            await asyncio.sleep(.02)
            self.assertEqual(self.state['jobs'][first['job_id']]['state'], 'running')
            self.task['context_id'] = 'successor'
            reader, writer = await rpc('test-token', 'job_cancel', job_id=first['job_id'])
            self.assertIn('Revoked or foreign', (await reader.readline()).decode())
            writer.close(); await writer.wait_closed()
            self.assertEqual(self.state['jobs'][first['job_id']]['state'], 'running')
        finally:
            server.close()
            await server.wait_closed()
            os.close(directory_fd)
            await self.manager.cancel('primary', first['job_id'])

    async def test_rollover_reconciles_an_admission_already_settling_under_job_lock(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def settling(*argv, **kwargs):
            entered.set()
            await release.wait()
            self.launches.append(argv)
            return ''
        self.command.side_effect = settling
        admission = asyncio.create_task(self.launch(7200))
        await entered.wait()
        self.task['operational_state'] = 'rollover_pending'
        reconcile = asyncio.create_task(self.runtime.reconciled_jobs('primary'))
        await asyncio.sleep(0)
        self.assertFalse(reconcile.done(), 'Successor must wait for admitted launch outcome')
        release.set()
        job = await admission
        observed = await reconcile
        self.assertEqual(observed[0]['job_id'], job['job_id'])
        self.assertEqual(observed[0]['deadline'], job['deadline'])
        self.assertEqual(observed[0]['launch_count'], 1)
        self.assertEqual(len(self.launches), 1)
        with self.assertRaisesRegex(jobs.JobError, 'lifecycle'):
            await self.launch(7200)
        await self.manager.cancel('primary', job['job_id'])

    async def test_admission_block_during_launch_prevents_command_release(self):
        async def block_before_ack(*argv, **kwargs):
            self.state['admission_block'] = 'Human pause'
            return ''
        self.command.side_effect = block_before_ack
        record = await self.launch()
        self.assertEqual(record['state'], 'cancelled')
        self.assertTrue(record['cleanup_ok'])
        self.assertFalse((Path(record['result_path']).parent/'launch.json').exists())

    async def test_parent_or_slot_creation_failure_blocks_context_and_job_admission(self):
        with patch.object(isolation, 'preflight'), patch.object(codex, 'verify_backend'), \
             patch.object(self.runtime.allocation, 'create', side_effect=isolation.RuntimeUnavailable('TasksMax delegation unavailable')):
            with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'TasksMax'):
                await self.runtime.start()
        self.assertFalse(self.runtime.clients)
        self.assertFalse(self.state['jobs'])
        self.assertIsNone(self.runtime.job_monitor)

    async def test_completed_job_stays_completed_after_delayed_reconciliation_and_cleanup(self):
        first = await self.launch()
        finished = first['admitted_monotonic'] + 1
        jobs.atomic(Path(first['result_path']), {
            'job_id': first['job_id'], 'finished': True, 'returncode': 0,
            'stdout': 'completed before the deadline', 'finished_monotonic': finished,
            'termination_cause': 'completed'})
        with patch.object(jobs.time, 'monotonic', return_value=first['deadline'] + 100), \
             patch.object(isolation, 'service_properties', return_value={
                 'LoadState':'loaded', 'ActiveState':'failed', 'InvocationID':'a'*32, 'Result':'timeout'}):
            await self.manager.reconcile(self.state['jobs'][first['job_id']])
        result = await self.manager.wait('primary', first['job_id'])
        self.assertEqual(result['state'], 'completed')
        self.assertTrue(result['cleanup_ok'])
        self.assertEqual(result['finished_monotonic'], finished)
        self.assertEqual(result['termination_cause'], 'completed')
        self.assertEqual(result['deadline'], first['deadline'])

    async def test_supervisor_expiry_is_not_dependent_on_service_result_or_observation_clock(self):
        first = await self.launch()
        jobs.atomic(Path(first['result_path']), {
            'job_id': first['job_id'], 'finished': True, 'returncode': -9,
            'finished_monotonic': first['deadline'], 'termination_cause': 'expired'})
        await self.manager.reconcile(self.state['jobs'][first['job_id']])
        result = await self.manager.wait('primary', first['job_id'])
        self.assertEqual(result['state'], 'timed_out')
        self.assertTrue(result['cleanup_ok'])


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_never_stops_foreign_invocation_or_boot(self):
        for props, saved in [({'LoadState': 'loaded', 'InvocationID': 'foreign', 'ControlGroup': '/elsewhere'}, owner()),
                              ({}, {**owner(), 'boot_id': 'old-boot'})]:
            with patch.object(isolation, 'service_properties', AsyncMock(return_value=props)), \
                 patch.object(isolation, 'command', AsyncMock()) as command:
                result = await isolation.stop_owned(saved)
                self.assertFalse(result['confirmed'])
                command.assert_not_awaited()

    async def test_cleanup_requires_group_empty_and_observable_state(self):
        saved = owner()
        props = {'LoadState': 'loaded', 'InvocationID': saved['invocation_id'],
                 'ControlGroup': saved['cgroup'], 'ActiveState': 'inactive'}
        for empty in (False, True):
            with patch.object(isolation, 'service_properties', AsyncMock(return_value=props)), \
                 patch.object(isolation, 'command', AsyncMock()), patch.object(isolation, 'group_empty', return_value=empty):
                self.assertEqual((await isolation.stop_owned(saved))['confirmed'], empty)
        with patch.object(isolation, 'service_properties', side_effect=isolation.RuntimeUnavailable('bus')):
            self.assertFalse((await isolation.stop_owned(saved))['confirmed'])

    async def test_absent_unit_still_requires_original_group_empty(self):
        with patch.object(isolation, 'service_properties', return_value={'LoadState': 'not-found'}), \
             patch.object(isolation, 'group_empty', return_value=False), patch.object(isolation, 'command', AsyncMock()) as command:
            self.assertFalse((await isolation.stop_owned(owner()))['confirmed'])
            command.assert_not_awaited()


    async def test_requested_cgroup_limits_must_be_observed_before_use(self):
        allocation = isolation.Allocation('a'*32, isolation.Config().limits())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, value in [('memory.max', '2147483648'), ('memory.swap.max','1'), ('pids.max','128')]:
                (root/name).write_text(value)
            with patch.object(isolation, 'command', AsyncMock(return_value='')), \
                 patch.object(isolation, 'service_properties', return_value={'ActiveState':'active','ControlGroup':'/fixture'}), \
                 patch.object(isolation, 'cgroup_path', return_value=root):
                with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'limits not applied'):
                    await allocation._slice('test.slice', 2147483648, 128)
                (root/'memory.swap.max').write_text('0')
                observed = await allocation._slice('test.slice', 2147483648, 128)
                self.assertEqual(observed['limits'], ['2147483648', '0', '128'])

    async def test_capture_checks_slice_membership_and_invocation(self):
        props = {'LoadState': 'loaded', 'ControlGroup': '/foreign/service', 'InvocationID': 'x'}
        with patch.object(isolation, 'service_properties', return_value=props):
            with self.assertRaises(isolation.RuntimeUnavailable):
                await isolation.capture_ownership('service', '/test/slot')

    async def test_mcp_schemas_require_duration_and_only_fixed_tools(self):
        tools = {t.name: t.model_dump(by_alias=True) for t in await job_server.create_server(None).list_tools()}
        self.assertEqual(set(tools), {'job_run','job_status','job_wait','job_cancel','write_draft','control'})
        self.assertIn('runtime_seconds', tools['job_run']['inputSchema']['required'])
        await codex.validate_mcp_inventory({'data': [{'name': 'research_jobs', 'tools': tools}]})
        for status in ({'data': []}, {'data': [{'name': 'research_jobs', 'tools': {}}]},
                       {'data': [{'name': 'research_jobs', 'tools': tools}], 'nextCursor': 'more'}):
            with self.assertRaises(isolation.RuntimeUnavailable):
                await codex.validate_mcp_inventory(status)

    def test_actual_catalog_missing_controlled_or_unknown_execution_fails_closed(self):
        expected = [{'name': 'mcp__research_jobs__'+name} for name in ('job_run','job_wait','job_status','job_cancel','write_draft','control')]
        codex.validate_tool_catalog(expected + [{'name':'functions.exec', 'description': 'JavaScript code mode orchestration'}])
        for extra in ('exec_command', 'spawn_agent', 'python', 'unknown_tool'):
            with self.assertRaises(isolation.RuntimeUnavailable):
                codex.validate_tool_catalog(expected + [{'name': extra}])
        with self.assertRaises(isolation.RuntimeUnavailable):
            codex.validate_tool_catalog(expected[:-1])

    def test_configuration_has_no_scientific_timer_or_exec_backend(self):
        with patch.object(jobs, 'adapter_mounts', return_value=['/usr']):
            args = codex.build_command(isolation.Config())
        self.assertIn('app-server', args)
        self.assertNotIn('exec', args)
        self.assertNotIn('RuntimeMaxSec', str(args))
        self.assertNotIn('tool_timeout_sec=20', str(args))
        for option in ('--wall-seconds', '--primary-session-seconds', '--delegated-session-seconds', '--job-runtime-seconds'):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.main(['start', '/tmp/fixture', option, '60'])
        self.assertEqual(isolation.Config().max_agents, 2)

    def test_preflight_does_not_repair_or_bypass_missing_host_prerequisites(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'user bus'):
                isolation.preflight()
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': '/fixture', 'DBUS_SESSION_BUS_ADDRESS': 'fixture'}), \
             patch.object(isolation.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'bwrap'):
                isolation.preflight()

    def test_systemd_grant_is_shared_and_only_jobs_have_runtime_max(self):
        allocation = isolation.Allocation('a'*32, isolation.Config().limits())
        allocation.slots = [{'unit': 'research-slot.slice'}]
        context = allocation.launch(0, 'context.service', ['app-server'])
        job = allocation.launch(0, 'job.service', ['supervisor'], deadline=time.monotonic()+7200)
        self.assertIn('--property=Slice=research-slot.slice', context)
        self.assertIn('--property=Slice=research-slot.slice', job)
        self.assertNotIn('RuntimeMaxSec', str(context))
        self.assertIn('RuntimeMaxSec', str(job))
        self.assertIn('--property=KillMode=control-group', job)
        self.assertIn('--property=Restart=no', job)


class ScientificFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        (self.project/'starting_evidence').mkdir()
        (self.project/'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Public sum.')

    def test_preserve_existing_requires_explicit_opt_in_and_refuses_orphan_runtime(self):
        (self.project/'work').mkdir()
        (self.project/'work/NOTE.md').write_text('# Human prior science')
        with self.assertRaises(workspace.InputError):
            workspace.validate_fresh(self.project)
        workspace.validate_fresh(self.project, True)
        for name in ('contexts', 'jobs', 'documents'):
            orphan = self.project/'.research_pipeline'/name
            orphan.mkdir(parents=True)
            with self.assertRaises(workspace.InputError):
                workspace.validate_fresh(self.project, True)
            orphan.rmdir()
        self.assertEqual((self.project/'work/NOTE.md').read_text(), '# Human prior science')

    def test_unsupported_operational_versions_rejected_without_migration(self):
        (self.project/'.research_pipeline').mkdir()
        for version in (None, 1, 2, 3, 4, 5, 7):
            jobs.atomic(self.project/'.research_pipeline/run.json', {'schema_version': version})
            with self.assertRaisesRegex(workspace.InputError, 'Unsupported operational state'):
                collaboration.load_state(self.project)

    def test_frozen_independent_packet_is_version_scoped_and_immutable(self):
        (self.project/'work').mkdir()
        (self.project/'work/check.py').write_text('assert sum(range(10)) == 45')
        fields = verification.PACKET_FIELDS
        text = '\n'.join('## '+field+'\n'+('[Code](check.py)' if field == 'Sources and artifacts' else 'Public deterministic check.') for field in fields)
        (self.project/'work/PACKET.md').write_text(text)
        drafts = self.project/'drafts'
        drafts.mkdir()
        packet, _ = verification.freeze(self.project, 'work/PACKET.md', drafts, 'work/tasks/check/inputs/check', fields, None)
        frozen = self.project / next(e['path'] for e in packet['evidence'] if e['source'] == 'work/check.py')
        before = frozen.read_bytes()
        (self.project/'work/check.py').write_text('changed original')
        self.assertEqual(frozen.read_bytes(), before)
        self.assertEqual(len(packet['version']), 64)
        argv = isolation.bubblewrap_command(self.project, ['true'], frozen_inputs=['work/tasks/check/inputs'])
        self.assertIn(str(self.project/'work/tasks/check/inputs'), argv)
        idx = argv.index(str(self.project/'work/tasks/check/inputs'))
        self.assertEqual(argv[idx-1], '--ro-bind')
