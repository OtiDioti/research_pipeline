"""Synchronized process, full CLI, and evidence-link regressions for L1 review."""
import asyncio
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.quota_fixture import sufficient
from research_pipeline import cli, collaboration, isolation, jobs, verification, workspace


def context_fixture(runtime, context_id='first', outcome=None, cleanup=True, task_id='primary'):
    root = runtime.project / '.research_pipeline/contexts' / context_id
    (root / 'drafts').mkdir(parents=True)
    record = {'context_id': context_id, 'task_id': task_id, 'state': 'attached', 'cleanup_ok': False}
    ctx = {'record': record, 'root': root, 'drafts': root/'drafts', 'private': ExitStack(),
           'baseline': workspace.science_fingerprints(runtime.project, task_id),
           'lifecycle_event': asyncio.Event(),
           'server': type('Server', (), {'close': lambda self: None, 'wait_closed': AsyncMock()})()}
    runtime.contexts[context_id] = ctx
    runtime.state['contexts'][context_id] = record
    runtime.state['tasks'][task_id]['context_id'] = context_id
    runtime.clients[context_id] = type('Client', (), {
        'turn': AsyncMock(return_value=outcome or {'id': 'turn', 'status': 'completed'}),
        'close': AsyncMock(return_value={'confirmed': cleanup, 'reason': 'engineering context double'})})()
    return ctx


def make_project(root):
    project = root / 'project'
    (project/'starting_evidence').mkdir(parents=True)
    (project/'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Public test inputs only.')
    return project


class CLIOutcomeTests(unittest.TestCase):
    def run_cli(self, outcome, cleanup):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            async def attach(runtime, task_id):
                sufficient(runtime)
                context_fixture(runtime, outcome=outcome, cleanup=cleanup)
                return 'first'
            with patch.object(collaboration.Coordinator, 'start', AsyncMock()), \
                 patch.object(collaboration.Coordinator, 'attach', attach), \
                 patch.object(collaboration.Coordinator, 'validate_inventory', return_value=True):
                code = cli.main(['start', str(project)])
            state = collaboration.load_state(project)
            return code, state

    def test_normally_ended_turn_with_unconfirmed_cleanup_is_cli_failure(self):
        code, state = self.run_cli({'id': 'turn', 'status': 'completed'}, cleanup=False)
        self.assertEqual(code, 1)
        self.assertFalse(state['cleanup_ok'])
        self.assertEqual(state['state'], 'cleanup_unconfirmed')
        self.assertFalse(state['contexts']['first']['cleanup_ok'])
        self.assertIn('telemetry unavailable', state['tasks']['primary']['context_error'])
        self.assertTrue(state['admission_block'])

    def test_failed_and_interrupted_turns_retain_native_outcome_and_fail_cli(self):
        for status in ('failed', 'interrupted'):
            with self.subTest(status=status):
                outcome = {'id': 'turn', 'status': status, 'error': {'message': 'native outcome detail'}}
                code, state = self.run_cli(outcome, cleanup=True)
                self.assertEqual(code, 1)
                self.assertEqual(state['state'], 'failed')
                self.assertTrue(state['cleanup_ok'])
                self.assertEqual(state['contexts']['first']['turn_outcome'], outcome)
                self.assertIn(status, state['tasks']['primary']['context_error'])
                self.assertIn('native outcome detail', state['tasks']['primary']['context_error'])

    def test_completed_turn_without_telemetry_is_operational_failure(self):
        code, state = self.run_cli({'id': 'turn', 'status': 'completed'}, cleanup=True)
        self.assertEqual(code, 1)
        self.assertTrue(state['cleanup_ok'])
        self.assertEqual(state['state'], 'failed')
        self.assertIn('telemetry unavailable', state['tasks']['primary']['context_error'])


class PublicationProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_finished_job_drafts_wait_for_the_successor_context_to_close(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            sufficient(runtime)
            context_fixture(runtime, context_id='successor')
            batch = project/'.research_pipeline/jobs/batch/drafts'
            (batch/'outputs').mkdir(parents=True)
            (batch/'outputs/JOB.md').write_text('# Retained computation notes')
            job = {'job_id': 'b'*32, 'task_id': 'primary', 'state': 'completed',
                   'cleanup_ok': True, 'drafts': str(batch), 'science_baseline': {}}
            runtime.state['jobs'][job['job_id']] = job
            runtime.jobs.publish(job)
            self.assertTrue(job['publication_pending'])
            self.assertFalse((project/'outputs/JOB.md').exists())
            await runtime.close_context('successor')
            self.assertFalse(job['publication_pending'])
            self.assertEqual((project/'outputs/JOB.md').read_text(), '# Retained computation notes')
            await runtime.close()

    async def test_surviving_writer_defers_all_publication_through_symlink_and_fifo_replacements(self):
        # Fixed engineering process: handshake on each replacement, no timing race,
        # inference, or claim that this is production service isolation evidence.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            sufficient(runtime)
            (project/'work/swap').mkdir()
            (project/'work/swap/NOTE.md').write_text('# Original')
            outside = root/'outside'
            outside.mkdir()
            (outside/'NOTE.md').write_text('# Outside private sentinel')
            ctx = context_fixture(runtime)
            (ctx['drafts']/'work/swap').mkdir(parents=True)
            (ctx['drafts']/'work/swap/NOTE.md').write_text('# Saved context draft')
            worker = await asyncio.create_subprocess_exec(sys.executable, '-u', '-c', r'''
from pathlib import Path
import os, sys
project, outside = map(Path, sys.argv[1:])
swap = project/'work/swap'
held = project/'work/held'
for line in sys.stdin:
    action = line.strip()
    if action == 'symlink':
        swap.rename(held)
        swap.symlink_to(outside, target_is_directory=True)
    elif action == 'fifo':
        swap.unlink()
        swap.mkdir()
        os.mkfifo(swap/'NOTE.md')
    elif action == 'restore':
        (swap/'NOTE.md').unlink()
        swap.rmdir()
        held.rename(swap)
    elif action == 'exit':
        break
    print(action, flush=True)
''', str(project), str(outside), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            async def command(action):
                worker.stdin.write((action+'\n').encode())
                await worker.stdin.drain()
                self.assertEqual((await asyncio.wait_for(worker.stdout.readline(), 3)).decode().strip(), action)
            job_id = 'a'*32
            batch = project/'.research_pipeline/jobs'/job_id/'drafts'
            (batch/'outputs').mkdir(parents=True)
            (batch/'outputs/JOB.md').write_text('# Job draft')
            record = {'job_id': job_id, 'task_id': 'primary', 'state': 'running', 'cleanup_ok': False,
                      'drafts': str(batch), 'science_baseline': ctx['baseline']}
            runtime.state['jobs'][job_id] = record
            original_publish = workspace.publish_drafts
            original_indexes = workspace.refresh_indexes
            def guarded_publish(*args, **kwargs):
                self.assertIsNotNone(worker.returncode, 'Host publication raced the live process')
                return original_publish(*args, **kwargs)
            def guarded_indexes(*args, **kwargs):
                self.assertIsNotNone(worker.returncode, 'Host indexing raced the live process')
                return original_indexes(*args, **kwargs)
            try:
                with patch.object(workspace, 'publish_drafts', side_effect=guarded_publish) as publish, \
                     patch.object(workspace, 'refresh_indexes', side_effect=guarded_indexes) as indexes:
                    await command('symlink')
                    await asyncio.wait_for(runtime.close_context('first'), 2)
                    self.assertTrue(ctx['record']['publication_pending'])
                    # Even terminal job publication waits for other active writers.
                    runtime.jobs.publish(record)
                    self.assertTrue(record['publication_pending'])
                    await command('fifo')
                    runtime.finalize_publications()
                    publish.assert_not_called()
                    indexes.assert_not_called()
                    self.assertEqual((outside/'NOTE.md').read_text(), '# Outside private sentinel')
                    self.assertFalse((outside/'FOLDER_CONTENT.md').exists())
                    await command('restore')
                    worker.stdin.write(b'exit\n')
                    await worker.stdin.drain()
                    await asyncio.wait_for(worker.communicate(), 3)
                    record.update(state='completed', cleanup_ok=True)
                    runtime.finalize_publications()
                    self.assertFalse(ctx['record']['publication_pending'])
                    self.assertFalse(record['publication_pending'])
                    self.assertEqual((project/'work/swap/NOTE.md').read_text(), '# Saved context draft')
                    self.assertTrue((project/'outputs/JOB.md').exists())
                    self.assertTrue((project/'work/swap/FOLDER_CONTENT.md').exists())
            finally:
                if worker.returncode is None:
                    worker.kill()
                    await worker.communicate()
                await runtime.close()


class ReadReplacementTests(unittest.TestCase):
    def test_note_mount_sources_stay_pinned_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            collaboration.Coordinator.initialize(project, isolation.Config())
            note = project/'work/NOTE.md'
            note.write_text('# Original canonical note')
            outside = Path(temp)/'private.md'
            outside.write_text('# Outside private sentinel')
            with ExitStack() as mounts:
                command = isolation.bubblewrap_command(project, ['true'], mount_stack=mounts)
                destination = command.index('/project/work/NOTE.md')
                source = Path(command[destination-1])
                self.assertTrue(source.is_relative_to(project/'.research_pipeline'))
                self.assertEqual(source.stat().st_mode & 0o777, 0o400)
                note.write_text('# Modified after mount preparation')
                note.rename(project/'work/old.md')
                note.symlink_to(outside)
                self.assertEqual(source.read_text(), '# Original canonical note')
            self.assertFalse(source.exists())

    def test_note_mount_sources_work_without_controller_proc_access(self):
        # A nondumpable producer models the controller's restricted /proc files.
        # The independent consumer models a systemd-launched mount process.
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            collaboration.Coordinator.initialize(project, isolation.Config())
            (project/'work/NOTE.md').write_text('# Protected note')
            producer = subprocess.Popen([sys.executable, '-u', '-c', r'''
from contextlib import ExitStack
import ctypes, json, os, sys
from pathlib import Path
from research_pipeline import isolation
assert ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) == 0
with ExitStack() as mounts, open(Path(sys.argv[1])/'work/NOTE.md') as original:
    argv = isolation.bubblewrap_command(Path(sys.argv[1]), ['true'], mount_stack=mounts)
    source = argv[argv.index('/project/work/NOTE.md')-1]
    print(json.dumps({'source': source, 'fd': f'/proc/{os.getpid()}/fd/{original.fileno()}'}), flush=True)
    sys.stdin.readline()
''', str(project)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                paths = json.loads(producer.stdout.readline())
                with self.assertRaises(PermissionError):
                    Path(paths['fd']).read_text()
                consumer = subprocess.run([sys.executable, '-c',
                    'from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text())',
                    paths['source']], capture_output=True, text=True, timeout=5)
                self.assertEqual(consumer.returncode, 0, consumer.stderr)
                self.assertEqual(consumer.stdout.strip(), '# Protected note')
                _, error = producer.communicate('\n', timeout=5)
                self.assertEqual(producer.returncode, 0, error)
                self.assertFalse(Path(paths['source']).exists())
            finally:
                if producer.poll() is None:
                    producer.kill()
                producer.communicate(timeout=5)

    def test_descriptor_read_pins_parent_and_refuses_synchronized_fifo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'swap').mkdir()
            (root/'swap/NOTE.md').write_text('# Original')
            (root/'outside').mkdir()
            (root/'outside/NOTE.md').write_text('# Secret')
            process = subprocess.Popen([sys.executable, '-u', '-c', r'''
from pathlib import Path
import os, sys
root = Path(sys.argv[1])
for line in sys.stdin:
    if line.strip() == 'symlink':
        (root/'swap').rename(root/'held')
        (root/'swap').symlink_to(root/'outside', target_is_directory=True)
    elif line.strip() == 'fifo':
        (root/'swap').unlink()
        (root/'held').rename(root/'swap')
        (root/'swap/NOTE.md').unlink()
        os.mkfifo(root/'swap/NOTE.md')
    print('ready', flush=True)
''', str(root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            def replace(action):
                process.stdin.write(action+'\n'); process.stdin.flush()
                # External watchdog bounds this process if the controller regresses.
                import selectors
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(3))
                self.assertEqual(process.stdout.readline().strip(), 'ready')
            opened = os.open
            replaced = False
            def pin_then_replace(path, flags, *args, **kwargs):
                nonlocal replaced
                fd = opened(path, flags, *args, **kwargs)
                if path == 'swap' and not replaced:
                    replaced = True
                    replace('symlink')
                return fd
            try:
                with patch.object(os, 'open', side_effect=pin_then_replace):
                    self.assertEqual(workspace.file_digest(root/'swap/NOTE.md'), hashlib.sha256(b'# Original').hexdigest())
                replace('fifo')
                self.assertEqual(workspace.file_digest(root/'swap/NOTE.md'), 'special')
                with self.assertRaises(workspace.InputError):
                    workspace.read_input_unbounded(root/'swap/NOTE.md')
            finally:
                process.terminate(); process.wait(timeout=3)
                process.stdin.close(); process.stdout.close()


class AssignmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_delegation_rebases_canonical_links_and_copies_recursive_draft_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            sufficient(runtime)
            ctx = context_fixture(runtime)
            (project/'work/data.csv').write_text('x,y\n1,2\n')
            text = '\n'.join('## '+field+'\n'+(
                '[Data](data.csv) and [Notes](notes.md#method)' if field == 'Artifacts' else 'Independent public calculation.')
                for field in verification.ASSIGNMENT_FIELDS)
            (ctx['drafts']/'work').mkdir()
            (ctx['drafts']/'work/ASSIGNMENT.md').write_text(text)
            (ctx['drafts']/'work/notes.md').write_text('# Method\n[Details](details.md)\n[Data](data.csv)')
            (ctx['drafts']/'work/details.md').write_text('# Details\n[Data](data.csv)\n[Web](https://example.org/paper#equation)')
            try:
                with patch.object(runtime, 'run_task', AsyncMock()):
                    result = await runtime.control(ctx, 'delegate', 'work/ASSIGNMENT.md')
                    await runtime.turns[result['task_id']]
                task = runtime.state['tasks'][result['task_id']]
                assignment = task['workspace']+'/ASSIGNMENT.md'
                installed = (project/assignment).read_text()
                self.assertIn('](/project/work/data.csv)', installed)
                self.assertIn('#method)', installed)
                to_check = [(assignment, installed)]
                visited = set()
                while to_check:
                    rel, body = to_check.pop()
                    if rel in visited:
                        continue
                    visited.add(rel)
                    for target in verification.LINK.findall(body):
                        dependency = verification.link_path(project, rel, target)
                        if dependency is None:
                            continue
                        self.assertTrue((project/dependency).is_file(), dependency)
                        if Path(dependency).suffix == '.md':
                            self.assertIn(task['workspace']+'/inputs/', dependency)
                            to_check.append((dependency, (project/dependency).read_text()))
                self.assertEqual(len(visited), 3)
                self.assertEqual((ctx['drafts']/'work/ASSIGNMENT.md').read_text(), text)
                self.assertIn(task['workspace']+'/inputs', task['frozen_inputs'])
            finally:
                await runtime.close()

    async def test_missing_link_refuses_delegation_without_allocating_task(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            runtime = collaboration.Coordinator.initialize(project, isolation.Config())
            sufficient(runtime)
            ctx = context_fixture(runtime)
            (ctx['drafts']/'work').mkdir()
            text = '\n'.join('## '+field+'\n'+('[Lost](missing.csv)' if field == 'Artifacts' else 'Public calculation.')
                             for field in verification.ASSIGNMENT_FIELDS)
            (ctx['drafts']/'work/ASSIGNMENT.md').write_text(text)
            with self.assertRaises(FileNotFoundError):
                await runtime.control(ctx, 'delegate', 'work/ASSIGNMENT.md')
            self.assertEqual(set(runtime.state['tasks']), {'primary'})
            self.assertFalse([p for p in (project/'work/tasks').iterdir() if p.is_dir()])
            await runtime.close()
