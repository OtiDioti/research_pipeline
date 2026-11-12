"""Live document consumption and cleanup retry; backend boundaries are explicit doubles."""
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.test_review_repairs import context_fixture, make_project
from tests.test_v0_l1 import owner
from research_pipeline import cli, collaboration, documents, isolation, job_server, jobs


class PendingDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = make_project(Path(self.tmp.name))
        self.runtime = collaboration.Coordinator.initialize(self.project, isolation.Config())
        self.context = context_fixture(self.runtime)
        self.directory_fds = []
        self.addCleanup(self.tmp.cleanup)

    async def asyncTearDown(self):
        with patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed': True, 'reason': 'fixture cleanup'})):
            await self.runtime.block_and_cleanup('engineering fixture finished')
        await self.runtime.close()
        for fd in self.directory_fds:
            os.close(fd)

    async def adapter(self, ctx):
        if 'token' not in ctx:
            ctx['token'] = 'test-token-' + ctx['record']['context_id']
            rpc = ctx['root']/'rpc'
            rpc.mkdir()
            ctx['server'] = await isolation.control_server(lambda r,w: self.runtime.handle_rpc(ctx,r,w), rpc)
        fd = os.open(ctx['root']/'rpc', os.O_RDONLY | os.O_DIRECTORY)
        self.directory_fds.append(fd)
        return job_server.Adapter({'token': ctx['token'], 'socket': f'/proc/self/fd/{fd}/control.sock'})

    def active_job(self):
        began = time.monotonic()
        root = self.project/'.research_pipeline/jobs/fixture'
        root.mkdir()
        record = {'job_id': 'b'*32, 'task_id': 'primary', 'origin_context_id': 'first',
                  'state': 'running', 'cleanup_ok': False, 'launch_count': 1, 'slot': 0,
                  'argv': ['engineering-survivor'], 'reason': 'explicit engineering fixture',
                  'deadline': began + 180, 'admitted_monotonic': began,
                  'result_path': str(root/'result.json'), 'service': owner()}
        self.runtime.state['jobs'][record['job_id']] = record
        return record

    async def test_successor_reads_predecessor_handoff_while_waiting_for_same_job(self):
        job = self.active_job()
        handoff = '# Handoff\n## Next action\nCollect the SAME job; do not restart the finite sum.\n'
        self.runtime.draft(self.context, 'handoffs/primary.md', handoff)
        original = {key: job[key] for key in ('job_id', 'deadline', 'service', 'slot', 'launch_count')}
        await self.runtime.close_context('first')
        self.assertTrue(self.context['record']['publication_pending'])
        self.assertFalse((self.project/'handoffs/primary.md').exists())

        @contextmanager
        def auth(project):
            root = project/'.research_pipeline/test-auth'
            root.mkdir()
            yield root
        backend = type('Client', (), {'start': AsyncMock(), 'new_thread': AsyncMock(return_value='successor-native'),
            'request': AsyncMock(return_value={'data': [{'name': 'research_jobs', 'tools': {
                tool.name: tool.model_dump(by_alias=True) for tool in await job_server.create_server(None).list_tools()}}]}),
            'close': AsyncMock(return_value={'confirmed': True, 'reason': 'protocol boundary double'})})()
        service = type('Service', (), {'ownership': owner('successor.service')})()
        with patch('research_pipeline.codex.private_auth', auth), \
             patch.object(isolation.RunningService, 'start', AsyncMock(return_value=service)), \
             patch('research_pipeline.app_server.Client', return_value=backend):
            successor_id = await self.runtime.successor('primary')
        successor = self.runtime.contexts[successor_id]
        adapter = await self.adapter(successor)
        listed = await adapter.call('control', action='documents')
        handoff_doc = next(doc for doc in listed['documents'] if doc['path'] == 'handoffs/primary.md')
        self.assertIn(handoff_doc['document_id'], backend.new_thread.call_args.args[2])

        subscribed = asyncio.Event()
        wait = self.runtime.jobs.wait
        async def wait_ready(*args, **kwargs):
            subscribed.set()
            return await wait(*args, **kwargs)
        with patch.object(self.runtime.jobs, 'wait', wait_ready):
            pending = asyncio.create_task(adapter.call('job_wait', job_id=job['job_id']))
            try:
                await asyncio.wait_for(subscribed.wait(), 2)
                consumed = await adapter.call('control', action='read_document', path=handoff_doc['document_id'])
                self.assertIn('Collect the SAME job', consumed['content'])
                self.assertEqual(consumed['content'], handoff)
                self.assertFalse(pending.done())
                self.assertEqual({key: job[key] for key in original}, original)
                self.assertEqual(job['state'], 'running')
                # The fixture completes its one computation after consuming its handoff.
                job.update(state='completed', cleanup_ok=True, stdout='sum=285', returncode=0)
                self.runtime.jobs.changed(job)
                collected = await asyncio.wait_for(pending, 2)
                self.assertEqual(collected['stdout'], 'sum=285')
                self.assertEqual({key: collected[key] for key in original}, original)
            finally:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

        # Snapshot content/version stays stable even if a retained source batch is
        # later edited by a human; no model can modify the private snapshot store.
        (self.context['drafts']/'handoffs/primary.md').write_text('# Changed retained source')
        again = await adapter.call('control', action='read_document', path=handoff_doc['document_id'])
        self.assertEqual(again['content'], handoff)
        self.assertEqual(again['sha256'], hashlib.sha256(handoff.encode()).hexdigest())
        self.assertEqual(len(self.runtime.state['jobs']), 1)
        self.assertFalse((self.project/'handoffs/primary.md').exists())

    async def parent_consumes_report(self, role, filename):
        task_id = 'task-' + 'a'*32
        task = self.runtime.add_task(task_id, 'Public independent calculation', 'primary', role)
        child = context_fixture(self.runtime, 'child', task_id=task_id)
        report_path = task['workspace']+'/'+filename
        report = '# Public result\nFinite sum: 285. Assumptions: integer arithmetic.\n'
        self.runtime.draft(child, report_path, report)
        self.context['record']['state'] = 'turn_running'
        adapter = await self.adapter(self.context)
        await self.runtime.close_context('child')
        self.assertFalse((self.project/report_path).exists())
        self.assertTrue(child['record']['publication_pending'])
        status = await adapter.call('control', action='tasks')
        document = next(doc for doc in status['documents'] if doc['path'] == report_path)
        consumed = await adapter.call('control', action='read_document', path=document['document_id'])
        value = int(consumed['content'].split('Finite sum: ')[1].split('.')[0])
        self.assertEqual(value, 285)
        await adapter.call('write_draft', path='outputs/SYNTHESIS.md',
                           content=f'# Preliminary synthesis\nConsumed {filename} version {consumed["sha256"]}: sum={value}.\n')
        self.assertEqual(self.context['record']['state'], 'turn_running')
        self.assertFalse(self.context['record']['cleanup_ok'])
        self.assertFalse((self.project/'outputs/SYNTHESIS.md').exists())
        await self.runtime.close_context('first')
        self.assertIn('sum=285', (self.project/'outputs/SYNTHESIS.md').read_text())
        self.assertEqual((self.project/report_path).read_text(), report)

    async def test_live_primary_consumes_completed_delegate_result(self):
        await self.parent_consumes_report('researcher', 'RESULT.md')

    async def test_live_primary_consumes_completed_verifier_check(self):
        await self.parent_consumes_report('verifier', 'CHECK.md')

    async def test_stopped_job_documents_are_readable_before_context_publication(self):
        job = self.active_job()
        root = Path(job['result_path']).parent/'drafts'
        (root/'outputs').mkdir(parents=True)
        (root/'outputs/COMPUTATION.md').write_text('# Retained computation notes')
        job.update(state='completed', cleanup_ok=True, drafts=str(root), science_baseline={})
        self.runtime.jobs.publish(job)
        self.assertTrue(job['publication_pending'])
        self.assertFalse((self.project/'outputs/COMPUTATION.md').exists())
        adapter = await self.adapter(self.context)
        listed = await adapter.call('control', action='documents')
        doc = next(doc for doc in listed['documents'] if doc['source_kind'] == 'job')
        read = await adapter.call('control', action='read_document', path=doc['document_id'])
        self.assertEqual(read['content'], '# Retained computation notes')

    async def test_scoped_paged_reads_reject_foreign_ids_paths_and_tampering(self):
        task_id = 'task-' + 'c'*32
        self.runtime.add_task(task_id, 'Independent checker', 'primary', 'verifier')
        child = context_fixture(self.runtime, 'child', task_id=task_id)
        text = '# Private parent handoff\n' + '\U0001f52c observed value\n'*2000
        self.runtime.draft(self.context, 'handoffs/primary.md', text)
        await self.runtime.close_context('first')
        document = self.runtime.documents.list('primary')['documents'][0]
        adapter = await self.adapter(child)
        self.assertEqual((await adapter.call('control', action='documents'))['documents'], [])
        for identifier in (document['document_id'], '../run.json', '/home/researcher/.codex/auth.json'):
            with self.assertRaises(jobs.JobError):
                await adapter.call('control', action='read_document', path=identifier)
        offset, pages = 0, []
        while offset is not None:
            page = self.runtime.documents.read('primary', document['document_id'], offset)
            self.assertLessEqual(len(page['content']), documents.PAGE_CHARACTERS)
            pages.append(page['content'])
            offset = page['next_offset']
        self.assertEqual(''.join(pages), text)
        for offset in (-1, True, 1.5):
            with self.assertRaises(jobs.JobError):
                self.runtime.documents.read('primary', document['document_id'], offset)
        retained = self.runtime.documents.root/(document['document_id']+'.md')
        retained.chmod(0o600)
        retained.write_text('tampered')
        with self.assertRaisesRegex(jobs.JobError, 'integrity'):
            self.runtime.documents.read('primary', document['document_id'])

    async def test_unsafe_batches_cannot_expose_operational_or_external_files(self):
        for kind in ('outside_scope', 'symlink', 'fifo'):
            ctx = self.context if kind == 'outside_scope' else context_fixture(self.runtime, kind)
            if kind == 'outside_scope':
                bad = ctx['drafts']/'starting_evidence/SECRET.md'
                bad.parent.mkdir()
                bad.write_text('must not be exposed')
            else:
                bad = ctx['drafts']/'work/LEAK.md'
                bad.parent.mkdir()
                if kind == 'symlink':
                    outside = Path(self.tmp.name)/'secret.md'
                    outside.write_text('outside private sentinel')
                    bad.symlink_to(outside)
                else:
                    os.mkfifo(bad)
            await self.runtime.close_context(ctx['record']['context_id'])
            self.assertIn('document_snapshot_error', ctx['record'])
            self.assertEqual(self.runtime.documents.list('primary')['documents'], [])
            self.assertTrue(self.runtime.documents.list('primary')['document_errors'])


class CleanupRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_then_success_finalizes_record_attachment_resources_and_drafts(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            ctx = context_fixture(runtime, cleanup=False)
            ctx['record'].update(service=owner('context.service'), unit='context.service')
            released = []
            ctx['private'].callback(lambda: released.append('private resources closed'))
            runtime.draft(ctx, 'handoffs/primary.md', '# Saved handoff\nResume the public calculation.')
            first = await runtime.close_context('first')
            self.assertFalse(first['confirmed'])
            self.assertFalse(ctx['record']['cleanup_ok'])
            self.assertEqual(runtime.state['tasks']['primary']['context_id'], 'first')
            self.assertNotIn('first', runtime.clients)
            self.assertFalse(released)
            self.assertFalse(runtime.documents.list('primary')['documents'])
            with patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed': True, 'reason': 'owned cgroup now empty'})) as stop:
                self.assertTrue(await runtime.block_and_cleanup('Human pause retry'))
                stop.assert_awaited_once_with(ctx['record']['service'])
                self.assertTrue(await runtime.block_and_cleanup('Duplicate pause'))
                stop.assert_awaited_once()
            task = runtime.state['tasks']['primary']
            self.assertIsNone(task['context_id'])
            self.assertEqual(task['last_context_id'], 'first')
            self.assertEqual(released, ['private resources closed'])
            self.assertEqual(ctx['record']['state'], 'closed')
            self.assertTrue(ctx['record']['cleanup_ok'])
            self.assertFalse(ctx['record']['publication_pending'])
            self.assertTrue(jobs.science_quiescent(runtime.state))
            self.assertTrue(runtime.state['cleanup_ok'])
            self.assertEqual(runtime.state['state'], 'paused')
            self.assertTrue(runtime.state['admission_block'])
            self.assertIn('public calculation', (project/'handoffs/primary.md').read_text())
            self.assertTrue(runtime.documents.list('primary')['documents'])
            self.assertTrue(collaboration.load_state(project)['contexts']['first']['cleanup_ok'])
            await runtime.close()

    async def test_failed_retry_keeps_resources_reserved_and_drafts_hidden(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            ctx = context_fixture(runtime, cleanup=False)
            ctx['record'].update(service=owner('context.service'), unit='context.service')
            released = []
            ctx['private'].callback(lambda: released.append(True))
            runtime.draft(ctx, 'handoffs/primary.md', '# Not yet safe to snapshot')
            await runtime.close_context('first')
            with patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed': False, 'reason': 'still uncertain'})):
                self.assertFalse(await runtime.block_and_cleanup('Human pause retry'))
            self.assertFalse(runtime.state['cleanup_ok'])
            self.assertFalse(ctx['record']['cleanup_ok'])
            self.assertFalse(released)
            self.assertEqual(runtime.state['tasks']['primary']['context_id'], 'first')
            self.assertFalse(runtime.documents.list('primary')['documents'])
            self.assertFalse((project/'handoffs/primary.md').exists())
            ctx['private'].close()  # no real service exists in this engineering double
            await runtime.close()


class CleanupRetryCLITests(unittest.TestCase):
    def test_successful_explicit_cleanup_retry_does_not_leave_cli_in_failure_state(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            run_task = collaboration.Coordinator.run_task
            async def attach(runtime, task_id):
                ctx = context_fixture(runtime, cleanup=False)
                ctx['record'].update(service=owner('context.service'), unit='context.service')
                runtime.draft(ctx, 'handoffs/primary.md', '# Scientific continuation preserved')
                return 'first'
            async def run_then_retry(runtime, task_id):
                await run_task(runtime, task_id)
                self.assertFalse(runtime.state['contexts']['first']['cleanup_ok'])
                await runtime.block_and_cleanup('Explicit pause after failed cleanup')
            with patch.object(collaboration.Coordinator, 'start', AsyncMock()), \
                 patch.object(collaboration.Coordinator, 'attach', attach), \
                 patch.object(collaboration.Coordinator, 'run_task', run_then_retry), \
                 patch.object(collaboration.Coordinator, 'validate_inventory', return_value=True), \
                 patch.object(isolation, 'stop_owned', AsyncMock(return_value={'confirmed': True, 'reason': 'owned cgroup now empty'})):
                self.assertEqual(cli.main(['start', str(project)]), 0)
            state = collaboration.load_state(project)
            self.assertTrue(state['cleanup_ok'])
            self.assertTrue(state['contexts']['first']['cleanup_ok'])
            self.assertIsNone(state['tasks']['primary']['context_id'])
            self.assertEqual(state['state'], 'paused')
            self.assertTrue((project/'handoffs/primary.md').exists())
