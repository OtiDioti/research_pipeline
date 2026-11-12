"""One research-owned runtime for single and multiple logical tasks.

Contexts attach to stable allocation slots. Only explicit trusted cleanup stops
jobs. L1 exposes manual successor attachment, not automatic rollover or terminal
scientific decisions.
"""
import asyncio
from contextlib import ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import time
import uuid

from . import app_server, codex, documents, isolation, jobs, references, verification, workspace

SCHEMA_VERSION = 4


def load_state(project):
    value = jobs.read(project / '.research_pipeline/run.json', max_bytes=64 * 1024 * 1024)
    if not value or value.get('schema_version') != SCHEMA_VERSION:
        raise workspace.InputError('Unsupported operational state; V0-L1 requires a fresh schema-4 runtime. Historical science is preserved; no migration is supported.')
    if not all(isinstance(value.get(key), dict) for key in ('limits', 'tasks', 'contexts', 'jobs')) or 'admission_block' not in value:
        raise workspace.InputError('Corrupt schema-4 runtime state; retain it for owned-process reconciliation')
    return value


class Coordinator:
    def __init__(self, project, config, state, intake):
        self.project, self.config, self.state, self.intake = project, config, state, intake
        self.allocation = isolation.Allocation(state['run_id'], state['limits'])
        self.jobs = jobs.JobManager(project, state, self.save, self.allocation)
        self.contexts = {}
        self.clients = {}
        self.turns = {}
        self.lifecycle_lock = asyncio.Lock()
        self.stack = ExitStack()
        self.monitor_task = None
        self.job_monitor = None
        self.rpc_tasks = set()
        self.documents = documents.Documents(project, state)
        self.jobs.on_quiescent = self.finalize_publications
        self.jobs.on_stopped = self.snapshot_job_documents

    def save(self):
        workspace.write_state(self.project, self.state)

    @classmethod
    def initialize(cls, project, config, preserve_existing=False):
        workspace.validate_fresh(project, preserve_existing)
        intake = workspace.read_intake(project)
        config.limits()
        (project / '.research_pipeline').mkdir(mode=0o700, exist_ok=True)
        for name in workspace.MANAGED:
            (project / name).mkdir(exist_ok=preserve_existing)
        (project / 'work/tasks').mkdir(exist_ok=True)
        workspace.initial_status(project)
        workspace.refresh_indexes(project, expected={} if preserve_existing else None)
        state = {'schema_version': SCHEMA_VERSION, 'run_id': uuid.uuid4().hex,
                 'limits': config.limits(), 'admission_block': None, 'state': 'starting',
                 'scientific_status': 'preliminary', 'contexts': {}, 'tasks': {}, 'jobs': {}, 'documents': {},
                 'boot_id': isolation.boot_identity(), 'limitations': [
                     'L1 has no automatic measured rollover, weekly reserve, scientific terminal decisions or stopped-state resumption.',
                     'Model spending is not capped; telemetry is observed, never a refreshed allocation.',
                     'Outbound network is available without destination filtering; 64 MiB per-file limit is not aggregate disk quota.']}
        runtime = cls(project, config, state, intake)
        runtime.add_task('primary', intake.questions, None)
        runtime.save()
        return runtime

    def add_task(self, task_id, objective, parent, role='researcher', frozen_inputs=()):
        if self.state['admission_block']:
            raise jobs.JobError('New tasks blocked: ' + self.state['admission_block'])
        occupied = {t['slot'] for t in self.state['tasks'].values() if not t.get('released')}
        slot = next((i for i in range(self.config.max_agents) if i not in occupied), None)
        if slot is None:
            raise jobs.JobError('Simultaneous logical-agent allocation cap reached')
        workspace.task_directory(task_id)
        task = {'task_id': task_id, 'workspace': workspace.task_directory(task_id),
                'objective': objective, 'parent_task': parent, 'role': role, 'slot': slot,
                'context_id': None, 'inventory_verified': False, 'frozen_inputs': list(frozen_inputs)}
        self.state['tasks'][task_id] = task
        workspace.safe_path(self.project, task['workspace']).mkdir(parents=True, exist_ok=True)
        self.save()
        return task

    async def start(self):
        isolation.preflight()
        codex.verify_backend(self.config)
        self.state['allocation'] = await self.allocation.create()
        self.save()
        self.job_monitor = asyncio.create_task(self.jobs.monitor())
        self.monitor_task = asyncio.create_task(self.monitor())
        self.state['state'] = 'running'
        self.save()

    async def attach(self, task_id):
        async with self.lifecycle_lock:
            if self.state['admission_block']:
                raise jobs.JobError('Context admissions blocked: ' + self.state['admission_block'])
            task = self.state['tasks'][task_id]
            if task['context_id']:
                raise jobs.JobError('Predecessor context has not been confirmed closed')
            if task.get('released'):
                raise jobs.JobError('Logical allocation was released')
            # Backend config/rule/skill discovery is excluded. No scientific directory
            # may install configuration for a successor backend.
            for _, dirs, files, _ in os.fwalk(self.project, follow_symlinks=False):
                for name in ('.codex', '.agents'):
                    if name in dirs or name in files:
                        raise workspace.InputError(f'Backend configuration in science is unsupported: {name}')
                dirs[:] = [name for name in dirs if name != '.research_pipeline']
            previous_inputs = self.intake.fingerprints
            self.intake = workspace.read_intake(self.project)
            context_id = uuid.uuid4().hex
            root = self.project / '.research_pipeline/contexts' / context_id
            root.mkdir(parents=True)
            (root / 'rpc').mkdir()
            drafts = root / 'drafts'
            drafts.mkdir()
            config = replace(self.config, task_id=task_id, drafts=drafts,
                             frozen_inputs=tuple(task['frozen_inputs']),
                             task_workspaces=tuple(t['workspace'] for k, t in self.state['tasks'].items() if k != 'primary'))
            references.configure(config, self.project, root, self.intake)
            task['reference_catalog'] = str(config.reference_catalog)
            task['reference_mounts'] = config.reference_mounts
            token = secrets.token_hex(32)
            jobs.atomic(root / 'context.json', {'token': token})
            record = {'context_id': context_id, 'task_id': task_id,
                      'unit': f'research-context-{context_id}.service', 'state': 'starting',
                      'cleanup_ok': False, 'launch_attempted': False,
                      'input_changes': workspace.changed_files(previous_inputs, self.intake.fingerprints), 'predecessor': task.get('last_context_id')}
            self.state['contexts'][context_id] = record
            task.update(context_id=context_id, inventory_verified=False)
            self.save()
            private = ExitStack()
            ctx = {'record': record, 'root': root, 'token': token, 'drafts': drafts,
                   'baseline': workspace.science_fingerprints(self.project, task_id),
                   'private': private, 'inventory_ready': asyncio.Event(), 'config': config}
            self.contexts[context_id] = ctx
            async def rpc(reader, writer):
                current = asyncio.current_task()
                self.rpc_tasks.add(current)
                try:
                    # Admissions continue to a durable outcome after disconnect.
                    await self.handle_rpc(ctx, reader, writer)
                finally:
                    self.rpc_tasks.discard(current)
            ctx['server'] = await isolation.control_server(rpc, root / 'rpc')
            try:
                ctx['auth'] = private.enter_context(codex.private_auth(self.project))
                argv = isolation.bubblewrap_command(self.project, codex.build_command(config),
                       codex=config.codex, auth_home=ctx['auth'], drafts=drafts,
                       task_id=task_id, task_workspaces=config.task_workspaces,
                       frozen_inputs=config.frozen_inputs, reference_mounts=config.reference_mounts,
                       reference_catalog=config.reference_catalog, job_context=root / 'context.json',
                       mount_stack=private)
                # Start from an empty home so no project configuration is discovered
                # during app-server startup. Threads use explicitly untrusted projects.
                argv[argv.index('--chdir') + 1] = '/home/researcher'
                record['launch_attempted'] = True
                self.save()
                service = await isolation.RunningService.start(self.allocation, task['slot'], record['unit'], argv)
                record['service'] = service.ownership
                self.save()
                async def event(value):
                    if value['method'] == 'thread/tokenUsage/updated':
                        record['telemetry'] = value['params']['tokenUsage']
                        self.save()
                    if value['method'] == 'item/completed':
                        item = value.get('params', {}).get('item', {})
                        if item.get('type') in ('commandExecution', 'collabAgentToolCall'):
                            raise isolation.RuntimeUnavailable('Forbidden native execution/collaboration event')
                client = app_server.Client(service, event)
                self.clients[context_id] = client
                await client.start()
                record['native_thread_id'] = await client.new_thread(f'/project/{task["workspace"]}', self.config.model,
                            codex.prompt(self.intake, task, (await self.jobs.inspect(task_id))['jobs'],
                                         self.documents.list(task_id)))
                mcp = await client.request('mcpServerStatus/list', {'threadId': record['native_thread_id'], 'serverName': 'research_jobs'})
                ctx['mcp_tools'] = await codex.validate_mcp_inventory(mcp)
                jobs.atomic(root / 'mcp-tools.json', mcp)
                record['state'] = 'attached'
                self.save()
                return context_id
            except BaseException as exc:
                record.update(state='failed', reason=str(exc))
                await self.close_context(context_id, locked=True)
                raise

    def validate_inventory(self, context_id):
        ctx = self.contexts[context_id]
        record = ctx['record']
        with codex.native_tool_trace(ctx['auth'], ctx['root']):
            pass
        catalogs = codex.native_catalog_observations(ctx['root'], record['native_thread_id'])
        if not catalogs:
            return False
        for catalog in catalogs:
            codex.validate_tool_catalog(catalog)
        self.state['tasks'][record['task_id']]['inventory_verified'] = True
        if not record.get('native_inventory_verified'):
            record['native_inventory_verified'] = True
            ctx['inventory_ready'].set()
            self.save()
        return True

    async def handle_rpc(self, ctx, reader, writer):
        try:
            await self.dispatch_rpc(ctx, reader, writer)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def dispatch_rpc(self, ctx, reader, writer):
        try:
            raw = await asyncio.wait_for(reader.readline(), 15)
            if len(raw) > 1024 * 1024:
                raise jobs.JobError('RPC request too large')
            value = json.loads(raw)
            task_id = ctx['record']['task_id']
            context_id = ctx['record']['context_id']
            task = self.state['tasks'][task_id]
            if (not secrets.compare_digest(value.get('token', ''), ctx['token'])
                    or task['context_id'] != context_id or ctx['record']['state'] not in ('attached', 'turn_running')):
                raise jobs.JobError('Revoked or foreign context attachment')
            operation, arguments = value.get('operation'), value.get('arguments', {})
            if operation == 'job_run':
                await asyncio.wait_for(ctx['inventory_ready'].wait(), 15)
                result = await self.jobs.run(task_id, context_id, **arguments)
            elif operation == 'job_status':
                result = await self.jobs.inspect(task_id, **arguments)
            elif operation == 'job_wait':
                subscription = asyncio.create_task(self.jobs.wait(task_id, **arguments))
                disconnect = asyncio.create_task(reader.read(1))
                try:
                    done, _ = await asyncio.wait((subscription, disconnect), return_when=asyncio.FIRST_COMPLETED)
                    if subscription not in done:
                        return
                    result = subscription.result()
                finally:
                    subscription.cancel()
                    disconnect.cancel()
                    await asyncio.gather(subscription, disconnect, return_exceptions=True)
            elif operation == 'job_cancel':
                result = await self.jobs.cancel(task_id, **arguments)
            elif operation == 'write_draft':
                result = self.draft(ctx, **arguments)
            elif operation == 'control':
                result = await self.control(ctx, **arguments)
            else:
                raise jobs.JobError('Unsupported controlled operation')
            response = {'result': result}
        except (ValueError, KeyError, TypeError, OSError, asyncio.TimeoutError, isolation.RuntimeUnavailable) as exc:
            response = {'error': f'{type(exc).__name__}: {exc}'}
        try:
            writer.write((json.dumps(response, allow_nan=False) + '\n').encode())
            await writer.drain()
        except (ConnectionError, BrokenPipeError):
            pass

    def draft(self, ctx, path, content):
        task_id = ctx['record']['task_id']
        rel = Path(path)
        if (not isinstance(content, str) or len(content.encode()) > 256 * 1024
                or not rel.parts or rel.suffix != '.md' or rel.name == 'FOLDER_CONTENT.md'
                or any(p.startswith('.') for p in rel.parts)
                or not workspace.allowed_science(path, task_id, self.state['tasks'][task_id]['frozen_inputs'])):
            raise jobs.JobError('Draft must be scoped scientific Markdown at most 256 KiB')
        target = workspace.safe_path(ctx['drafts'], path)
        target.parent.mkdir(parents=True, exist_ok=True)
        workspace.atomic_text(target, content)
        return {'draft': path, 'bytes': len(content.encode())}

    async def control(self, ctx, action='check', path=None, parent='primary', offset=0):
        reader = ctx['record']['task_id']
        if action == 'documents':
            return self.documents.list(reader, offset)
        if action == 'read_document':
            return self.documents.read(reader, path, offset)
        if action in ('check', 'tasks'):
            return {'admission_block': self.state['admission_block'], 'tasks': self.state['tasks'],
                    'jobs': await self.jobs.inspect(reader), **self.documents.list(reader)}
        if action not in ('delegate', 'verify'):
            raise jobs.JobError('Unsupported legacy/terminal control; scientific opposition and terminal decisions require V0-L4')
        if ctx['record']['task_id'] != 'primary' or parent not in self.state['tasks']:
            raise jobs.JobError('Only primary may assign a scientific task with a known parent')
        if self.state['admission_block']:
            raise jobs.JobError('Admissions blocked')
        if not isinstance(path, str) or not workspace.allowed_science(path):
            raise jobs.JobError('Assignment must be primary scientific Markdown')
        task_id = 'task-' + uuid.uuid4().hex
        task_root = workspace.task_directory(task_id)
        # freeze and job admission cannot race. Changing outputs are not stable evidence.
        async with self.jobs.lock:
            if any(r['state'] in jobs.ACTIVE for r in self.state['jobs'].values()):
                raise jobs.JobError('Finish or cancel active computations before freezing assignment evidence')
            # Check capacity before freezing files.
            occupied = sum(not t.get('released') for t in self.state['tasks'].values())
            if occupied >= self.config.max_agents:
                raise jobs.JobError('Simultaneous logical-agent cap reached')
            if action == 'verify':
                packet, sections = verification.freeze(self.project, path, ctx['drafts'], f'{task_root}/inputs/check', verification.PACKET_FIELDS, None)
                frozen = [f'{task_root}/inputs']
                objective = 'Independently challenge frozen claim and scope: ' + sections['Claim and scope'] + f". Read /project/{packet['packet']}. Preserve an evidence-based CHECK.md; this is not terminal opposition."
            else:
                text, sections = verification.prepare_assignment(
                    self.project, path, ctx['drafts'], f'{task_root}/inputs/assignment')
                objective = sections['Objective'] + f'. Read /project/{task_root}/ASSIGNMENT.md.'
                assignment = workspace.safe_path(self.project, f'{task_root}/ASSIGNMENT.md')
                assignment.parent.mkdir(parents=True, exist_ok=True)
                workspace.atomic_text(assignment, text)
                frozen = [f'{task_root}/ASSIGNMENT.md', f'{task_root}/inputs']
            task = self.add_task(task_id, objective, parent, 'verifier' if action == 'verify' else 'researcher', frozen)
            if action == 'verify':
                task['frozen_packet'] = packet
            self.save()
        # Launch in background: the primary and other control subscriptions stay responsive.
        self.turns[task_id] = asyncio.create_task(self.run_task(task_id))
        return {'task_id': task_id, 'workspace': task_root}

    async def run_task(self, task_id):
        context_id = None
        try:
            context_id = await self.attach(task_id)
            ctx = self.contexts[context_id]
            if self.state['admission_block']:
                return
            ctx['record']['state'] = 'turn_running'
            self.save()
            result = await self.clients[context_id].turn('Continue the assigned scientific task. Save an early handoff and useful evidence in scoped drafts. End this turn with an honest account of remaining work.')
            ctx['record']['turn_outcome'] = result
            if result.get('status') != 'completed':
                raise isolation.RuntimeUnavailable(
                    f"Native turn {result.get('status', 'missing status')}: {json.dumps(result.get('error'))}")
            if not self.validate_inventory(context_id):
                raise isolation.RuntimeUnavailable('Native request inventory unavailable for completed context')
            ctx['record']['state'] = 'turn_ended'
        except Exception as exc:
            self.state['tasks'][task_id]['context_error'] = f'{type(exc).__name__}: {exc}'
        finally:
            if context_id:
                await self.close_context(context_id)
            self.save()

    async def close_context(self, context_id, locked=False):
        if not locked:
            async with self.lifecycle_lock:
                return await self.close_context(context_id, locked=True)
        ctx = self.contexts[context_id]
        record = ctx['record']
        if record.get('cleanup_ok') is True:
            return record['cleanup']
        task = self.state['tasks'][record['task_id']]
        # Revoke admissions before closing the connection; surviving jobs are untouched.
        record['state'] = 'closing'
        task['inventory_verified'] = False
        try:
            self.save()
        except OSError as exc:
            record['persistence_error'] = str(exc)
        ctx['server'].close()
        await ctx['server'].wait_closed()
        client = self.clients.pop(context_id, None)
        if client:
            cleanup = await client.close()
        elif not record.get('launch_attempted', True):
            cleanup = {'confirmed': True, 'reason': 'No context launch attempted'}
        else:
            if not record.get('service'):
                try:
                    record['service'] = await isolation.capture_ownership(record['unit'], self.allocation.slots[task['slot']]['cgroup'])
                    self.save()
                except (OSError, isolation.RuntimeUnavailable):
                    pass
            cleanup = await isolation.stop_owned(record.get('service'))
        record.update(cleanup=cleanup, cleanup_ok=cleanup['confirmed'], state='closed' if cleanup['confirmed'] else 'cleanup_unconfirmed')
        if cleanup['confirmed']:
            task.update(last_context_id=context_id, context_id=None)
            record['publication_pending'] = True
            self.documents.capture(record, 'context', ctx['drafts'], task['frozen_inputs'])
            try:
                # Live outputs are observations, not immutable checkpoint hashes.
                job_handoff = await self.jobs.inspect(record['task_id'])
                job_handoff['active_details'] = [jobs.public(r) for r in self.state['jobs'].values()
                    if r['task_id'] == record['task_id'] and r['state'] in jobs.ACTIVE]
                jobs.atomic(ctx['root'] / 'job-handoff.json', job_handoff)
            except (OSError, ValueError) as exc:
                record['job_handoff_error'] = str(exc)
            finally:
                ctx['private'].close()
            self.finalize_publications()
        else:
            self.state['admission_block'] = self.state['admission_block'] or 'Context cleanup unconfirmed'
        try:
            self.save()
        except OSError as exc:
            record['persistence_error'] = str(exc)
        return cleanup

    def snapshot_job_documents(self, record):
        self.documents.capture(record, 'job', Path(record['drafts']),
                               self.state['tasks'][record['task_id']].get('frozen_inputs', ()))

    def finalize_publications(self):
        """No await: admissions cannot interleave with quiescent path-based writes."""
        if not jobs.science_quiescent(self.state):
            return
        changed = False
        for job in self.state['jobs'].values():
            if job.get('publication_pending'):
                self.jobs.publish(job)
                changed = True
        for ctx in self.contexts.values():
            record = ctx['record']
            if not record.get('publication_pending'):
                continue
            try:
                conflicts, _ = workspace.publish_drafts(
                    self.project, ctx['drafts'], ctx['baseline'], [], record['task_id'],
                    self.state['tasks'][record['task_id']]['frozen_inputs'])
                record['publication_conflicts'] = conflicts
                workspace.refresh_indexes(self.project, expected=ctx['baseline'], task_id=record['task_id'])
            except (OSError, ValueError) as exc:
                record['publication_error'] = str(exc)
            record['publication_pending'] = False
            changed = True
        if changed:
            self.save()

    async def successor(self, task_id):
        task = self.state['tasks'][task_id]
        if task['context_id'] is not None:
            raise jobs.JobError('Predecessor context closure unconfirmed')
        return await self.attach(task_id)

    async def block_and_cleanup(self, reason):
        # Latch before any cleanup/checkpoint operation; failed saves cannot bypass it.
        self.state.update(admission_block=self.state['admission_block'] or reason, state='stopping')
        try:
            self.save()
        except OSError as exc:
            self.state['persistence_error'] = str(exc)
        outcomes = {}
        for context_id in list(self.clients):
            try:
                outcomes[context_id] = await self.close_context(context_id)
            except Exception as exc:
                outcomes[context_id] = {'confirmed': False, 'reason': str(exc)}
        for record in self.state['contexts'].values():
            if not record.get('cleanup_ok') and record['context_id'] not in outcomes:
                context_id = record['context_id']
                if context_id in self.contexts:
                    try:
                        outcomes[context_id] = await self.close_context(context_id)
                    except Exception as exc:
                        outcomes[context_id] = {'confirmed': False, 'reason': str(exc)}
                else:
                    cleanup = await isolation.stop_owned(record.get('service'))
                    outcomes[context_id] = cleanup
                    record.update(cleanup=cleanup, cleanup_ok=cleanup['confirmed'],
                                  state='closed' if cleanup['confirmed'] else 'cleanup_unconfirmed')
                    if cleanup['confirmed']:
                        task = self.state['tasks'][record['task_id']]
                        if task['context_id'] == context_id:
                            task.update(last_context_id=context_id, context_id=None)
        for job_id, record in self.state['jobs'].items():
            if record['state'] in jobs.ACTIVE:
                try:
                    cancelled = await self.jobs.cancel(record['task_id'], job_id)
                    outcomes[job_id] = cancelled.get('cleanup', {'confirmed': False})
                except Exception as exc:
                    outcomes[job_id] = {'confirmed': False, 'reason': str(exc)}
        confirmed = all(o['confirmed'] for o in outcomes.values()) and jobs.science_quiescent(self.state)
        self.state.update(state='paused' if confirmed else 'cleanup_unconfirmed', cleanup_ok=confirmed, cleanup=outcomes)
        try:
            self.finalize_publications()
            self.save()
        except OSError as exc:
            self.state['persistence_error'] = str(exc)
            return False
        return confirmed

    async def monitor(self):
        while True:
            pause = jobs.read(self.project / '.research_pipeline/pause.json')
            if pause and pause.get('run_id') == self.state['run_id']:
                await self.block_and_cleanup('Human pause requested')
                return
            for context_id, client in list(self.clients.items()):
                record = self.contexts[context_id]['record']
                if client.failure:
                    record['protocol_error'] = str(client.failure)
                    await self.close_context(context_id)
                    continue
                if record.get('native_thread_id') and record['state'] == 'turn_running':
                    try:
                        self.validate_inventory(context_id)
                    except Exception as exc:
                        record['inventory_error'] = str(exc)
                        await self.block_and_cleanup('Production tool inventory validation failed')
                        return
            await asyncio.sleep(.1)

    async def close(self):
        for task in (self.monitor_task, self.job_monitor):
            if task:
                task.cancel()
        await asyncio.gather(*(t for t in (self.monitor_task, self.job_monitor) if t), return_exceptions=True)
        for task in self.turns.values():
            task.cancel()
        await asyncio.gather(*self.turns.values(), return_exceptions=True)
        self.stack.close()
