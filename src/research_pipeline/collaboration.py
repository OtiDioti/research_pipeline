"""One research-owned runtime for single and multiple logical tasks.

Contexts attach to stable allocation slots. Measured rollover replaces contexts
while jobs and logical tasks survive. Terminal review is bound to frozen evidence.
"""
import asyncio
from contextlib import ExitStack
from dataclasses import replace
import json
import hashlib
import os
from pathlib import Path
import secrets
import time
import uuid

from . import app_server, codex, context_usage, decisions, documents, isolation, jobs, quota, references, staleness, verification, workspace

SCHEMA_VERSION = 7


def terminal_acknowledged(project, state):
    marker = state.get('terminal_marker')
    digest = state.get('terminal_sha256')
    return (state.get('terminal_committed') is True and marker in ('COMPLETE', 'STOP')
            and isinstance(digest, str)
            and workspace.file_digest(project / marker) == digest
            and workspace.file_digest(project / (marker + '_ACK')) == digest)


def load_state(project):
    value = jobs.read(project / '.research_pipeline/run.json', max_bytes=64 * 1024 * 1024)
    if not value or value.get('schema_version') != SCHEMA_VERSION:
        raise workspace.InputError('Unsupported operational state; V0-L4 requires a fresh schema-7 runtime. Historical science is preserved; no migration is supported.')
    if (not all(isinstance(value.get(key), dict) for key in
                ('limits', 'tasks', 'contexts', 'jobs', 'quota', 'pending_staleness', 'opposition'))
            or 'admission_block' not in value):
        raise workspace.InputError('Corrupt schema-7 runtime state; retain it for owned-process reconciliation')
    if value.get('terminal_committed') and not terminal_acknowledged(project, value):
        value.update(finalization_ok=False, terminal_committed=False,
                     terminal_error='Saved terminal intent has no matching marker/acknowledgement; finalization unconfirmed')
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
        self.decision_lock = asyncio.Lock()
        self.lifecycle_tasks = set()
        self.stack = ExitStack()
        self.monitor_task = None
        self.job_monitor = None
        self.quota_monitor_task = None
        self.shutdown_task = None
        self.cleanup_lock = asyncio.Lock()
        self.warning_delivery_task = None
        self.quota_transport = None
        self.quota_ready = asyncio.Event()
        baseline = workspace.science_fingerprints(project)
        self.status_baseline = baseline.get('RESEARCH_STATUS.md')
        self.index_baseline = {path: digest for path, digest in baseline.items()
                               if Path(path).name == 'FOLDER_CONTENT.md'}
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
                 'quota': {}, 'secondary_staleness_seconds': config.secondary_staleness_seconds,
                 'pending_staleness': {}, 'staleness_history': [],
                 'opposition': {'opponent_id': None, 'current': None, 'history': []},
                 'boot_id': isolation.boot_identity(), 'limitations': [
                     'Stopped-state resumption/reopening requires L5.',
                     'Model spending is not capped; telemetry is observed, never a refreshed allocation.',
                     'Outbound network is available without destination filtering; 64 MiB per-file limit is not aggregate disk quota.']}
        runtime = cls(project, config, state, intake)
        runtime.add_task('primary', intake.questions, None, role='primary', initial=True)
        runtime.save()
        return runtime

    def require_quota(self):
        error = quota.admission_error(self.state)
        if error:
            raise jobs.JobError(error)

    async def wait_quota_ready(self):
        if self.state['quota'].get('transport_unavailable') and not self.state['admission_block']:
            await self.quota_ready.wait()
        self.require_quota()

    async def attach_admitted(self, task_id):
        while True:
            if task_id != 'primary':
                await self.wait_quota_ready()
            try:
                return await self.attach(task_id)
            except jobs.JobError:
                # A primary close may win the lifecycle lock after our cached
                # check. Wait outside that lock; do not retire unrelated work.
                if (task_id == 'primary' or self.state['admission_block']
                        or not self.state['quota'].get('transport_unavailable')):
                    raise

    def add_task(self, task_id, objective, parent, role='researcher', frozen_inputs=(), *, initial=False):
        # Only the nonexecuting initial primary allocation precedes preflight.
        if not initial:
            self.require_quota()
        if role not in ('primary', 'researcher', 'verifier', 'opponent'):
            raise jobs.JobError('Unknown scientific role')
        if self.state['admission_block']:
            raise jobs.JobError('New tasks blocked: ' + self.state['admission_block'])
        occupied = {t['slot'] for t in self.state['tasks'].values() if not t.get('released')}
        slot = next((i for i in range(self.config.max_agents) if i not in occupied), None)
        if slot is None:
            raise jobs.JobError('Simultaneous logical-agent allocation cap reached')
        workspace.task_directory(task_id)
        task = {'task_id': task_id, 'workspace': workspace.task_directory(task_id),
                'objective': objective, 'parent_task': parent, 'role': role, 'slot': slot,
                'phase': 'review' if role in ('opponent', 'verifier') else 'research',
                'operational_state': 'working', 'context_id': None,
                'inventory_verified': False, 'frozen_inputs': list(frozen_inputs)}
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
        await self.attach('primary')
        self.quota_monitor_task = asyncio.create_task(self.monitor_quota())
        self.state['state'] = 'running'
        self.save()

    def science_intake(self, task_id):
        """Compare canonical science with the logical context's expected state."""
        current = workspace.science_fingerprints(self.project, task_id)
        previous = self.contexts.get(self.state['tasks'][task_id].get('last_context_id'))
        if not previous:
            return current, dict(current), {}
        record = previous['record']
        expected = dict(previous['baseline'])
        published = set()
        publications = [record] + [
            job for job in self.state['jobs'].values()
            if job.get('publication_context_id') == record['context_id']]
        for publication in publications:
            if publication.get('publication_pending') or 'publication_conflicts' not in publication:
                continue
            excluded = {item['path'] for item in publication['publication_conflicts']}
            excluded.update(publication.get('publication_superseded', ()))
            for identifier in publication.get('document_ids', ()):
                document = self.state['documents'][identifier]
                if document['path'] not in excluded:
                    expected[document['path']] = document['sha256']
                    published.add(document['path'])
        protected = {
            path: change['previous_sha256']
            for path, change in record.get('science_changes', {}).items()
            if path not in published}
        for path in workspace.changed_files(expected, current):
            if (Path(path).name != 'FOLDER_CONTENT.md'
                    and not path.startswith(('handoffs/proposed/', 'handoffs/preserved/'))):
                protected.setdefault(path, expected.get(path))
        changes = {
            path: {'previous_sha256': digest, 'sha256': current.get(path)}
            for path, digest in protected.items()}
        baseline = dict(current)
        for path, change in changes.items():
            baseline[path] = change['previous_sha256']
        return current, baseline, changes

    async def attach(self, task_id):
        async with self.lifecycle_lock:
            if task_id != 'primary':
                self.require_quota()
            if self.state['admission_block']:
                raise jobs.JobError('Context admissions blocked: ' + self.state['admission_block'])
            task = self.state['tasks'][task_id]
            if task['context_id']:
                raise jobs.JobError('Predecessor context has not been confirmed closed')
            if task.get('released'):
                raise jobs.JobError('Logical allocation was released')
            if task.get('retirement_requested'):
                raise jobs.JobError('Task is retiring; context admission blocked')
            # Backend config/rule/skill discovery is excluded. No scientific directory
            # may install configuration for a successor backend.
            for _, dirs, files, _ in os.fwalk(self.project, follow_symlinks=False):
                for name in ('.codex', '.agents'):
                    if name in dirs or name in files:
                        raise workspace.InputError(f'Backend configuration in science is unsupported: {name}')
                dirs[:] = [name for name in dirs if name != '.research_pipeline']
            predecessor = self.state['contexts'].get(task.get('last_context_id'), {})
            previous_inputs = predecessor.get('input_fingerprints', self.intake.fingerprints)
            self.intake = workspace.read_intake(self.project)
            science, publication_baseline, science_changes = self.science_intake(task_id)
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
                      'input_changes': sorted(set(workspace.changed_files(previous_inputs, self.intake.fingerprints))
                                              | science_changes.keys()),
                      'science_changes': science_changes,
                      'input_fingerprints': self.intake.fingerprints,
                      'predecessor': task.get('last_context_id')}
            self.state['contexts'][context_id] = record
            task.update(context_id=context_id, inventory_verified=False)
            self.save()
            private = ExitStack()
            ctx = {'record': record, 'root': root, 'token': token, 'drafts': drafts,
                   'baseline': science, 'publication_baseline': publication_baseline,
                   'private': private, 'inventory_ready': asyncio.Event(), 'config': config,
                   'lifecycle_event': asyncio.Event()}
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
                client = app_server.Client(service, lambda value: self.context_event(context_id, value))
                self.clients[context_id] = client
                if task_id == 'primary':
                    self.quota_transport = context_id
                    self.state['quota']['transport_unavailable'] = True
                await client.start()
                if task_id == 'primary':
                    await self.refresh_quota(context_id)
                self.require_quota()
                if task.get('retirement_requested'):
                    raise jobs.JobError('Task retired during context admission')
                owned_jobs = (await self.jobs.inspect(task_id))['jobs']
                instructions = codex.prompt(self.intake, task, owned_jobs, self.successor_documents(task_id))
                # Reconciliation can suspend; no await may separate this
                # admission check from dispatching the native thread RPC.
                self.require_quota()
                record['native_thread_id'] = await client.new_thread(f'/project/{task["workspace"]}', self.config.model,
                                                                     instructions)
                mcp = await client.request('mcpServerStatus/list', {'threadId': record['native_thread_id'], 'serverName': 'research_jobs'})
                ctx['mcp_tools'] = await codex.validate_mcp_inventory(mcp)
                jobs.atomic(root / 'mcp-tools.json', mcp)
                record['state'] = 'attached'
                if task_id != 'primary':
                    record['staleness'] = staleness.attach(time.monotonic())
                self.require_quota()
                self.save()
                return context_id
            except BaseException as exc:
                record.update(state='failed', reason=str(exc))
                await self.close_context(context_id, locked=True)
                raise

    async def context_event(self, context_id, value):
        if value['method'] == 'account/rateLimits/updated':
            if context_id == self.quota_transport:
                self.observe_quota(context_id, value.get('params', {}), full=False)
            return
        if value['method'] == 'thread/tokenUsage/updated':
            # Capture the inference boundary at receipt time, before applying this
            # sample. This is file inspection only; the RPC reader must not wait
            # for lifecycle RPCs whose responses require that same reader.
            self.validate_inventory(context_id, check_measurement=False)
            self.observe_context(context_id, value['params'])
        if value['method'] == 'item/completed':
            item = value.get('params', {}).get('item', {})
            if item.get('type') in ('commandExecution', 'collabAgentToolCall'):
                raise isolation.RuntimeUnavailable('Forbidden native execution/collaboration event')

    def validate_inventory(self, context_id, check_measurement=True):
        ctx = self.contexts[context_id]
        record = ctx['record']
        with codex.native_tool_trace(ctx['auth'], ctx['root']):
            pass
        catalogs = codex.native_catalog_observations(ctx['root'], record['native_thread_id'])
        if not catalogs:
            if record.get('native_inventory_verified'):
                raise isolation.RuntimeUnavailable('Previously observed native inference evidence disappeared')
            return False
        for catalog in catalogs:
            codex.validate_tool_catalog(catalog)
        count = json.loads((ctx['root'] / 'native-tools.json').read_text())['inference_starts']
        previous = record.get('native_inference_count', 0)
        if count < previous:
            raise isolation.RuntimeUnavailable('Native inference evidence regressed; measurement coverage is uncertain')
        record['native_inference_count'] = count
        # The current inference may still be generating or waiting on a tool.
        # Starting another inference proves that its predecessor has ended.
        # No new start during job_wait means no wall-clock measurement expiry.
        if check_measurement and count > record.get('measured_inference_count', 0) + 1:
            if record.get('measurement', {}).get('status') == 'measured':
                record['measurement'] = {
                    'status': 'missing', 'error': 'Native inference advanced without a usage observation',
                    'native_inference_count': count,
                    'measured_inference_count': record.get('measured_inference_count', 0)}
                record['measurement_gap'] = dict(record['measurement'])
                record['accounting_incomplete'] = True
                task = self.state['tasks'][record['task_id']]
                if task['operational_state'] not in ('checkpointing', 'failed'):
                    task['operational_state'] = 'telemetry_recovery'
                ctx['lifecycle_event'].set()
                self.save()
        if count != previous:
            self.save()
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
                if not self.validate_inventory(context_id):
                    raise isolation.RuntimeUnavailable('Native inference evidence unavailable for job admission')
                result = await self.jobs.run(task_id, context_id, **arguments)
            elif operation == 'job_status':
                result = await self.jobs.inspect(task_id, **arguments)
                self.job_inspected(task, arguments.get('job_id'))
                ctx['record'].setdefault('job_inspections', {})[str(arguments.get('job_id'))] = {'operation': operation, 'state': result.get('state')}
                self.save()
            elif operation == 'job_wait':
                subscription = asyncio.create_task(self.jobs.wait(task_id, **arguments))
                disconnect = asyncio.create_task(reader.read(1))
                try:
                    done, _ = await asyncio.wait((subscription, disconnect), return_when=asyncio.FIRST_COMPLETED)
                    if subscription not in done:
                        return
                    result = subscription.result()
                    self.job_inspected(task, arguments.get('job_id'))
                    ctx['record'].setdefault('job_inspections', {})[str(arguments.get('job_id'))] = {'operation': operation, 'state': result.get('state')}
                    self.save()
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
        if self.state['admission_block'] or (
                self.state['tasks'][task_id].get('retirement_requested')
                and self.state['tasks'][task_id]['operational_state'] != 'checkpointing'):
            raise jobs.JobError('Draft admission blocked by lifecycle')
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

    async def control(self, ctx, action='check', path=None, parent='primary', offset=0, sha256=None):
        reader = ctx['record']['task_id']
        if action == 'documents':
            return self.documents.list(reader, offset)
        if action == 'read_document':
            result = self.documents.read(reader, path, offset)
            ctx['record'].setdefault('document_reads', {})[path] = {'offset': offset, 'next_offset': result['next_offset']}
            self.save()
            return result
        if action in ('history', 'read_history'):
            if reader not in ('primary', self.state['opposition']['opponent_id']):
                raise jobs.JobError('Decision history is scoped to primary and the designated opponent')
            if action == 'history':
                return self.opposition_summary(offset)
            return self.read_history(path, parent, offset)
        if action in ('check', 'tasks'):
            self.documents.check_offset(offset)
            task_ids = list(self.state['tasks'])
            page = task_ids[offset:offset + 16]
            return {'admission_block': self.state['admission_block'],
                    'tasks': {i: self.task_summary(self.state['tasks'][i]) for i in page},
                    'tasks_total': len(task_ids), 'tasks_offset': offset,
                    'tasks_next_offset': offset + len(page) if offset + len(page) < len(task_ids) else None,
                    'opposition': self.opposition_summary(),
                    'capacity_blockers': [t['task_id'] for t in self.state['tasks'].values()
                                          if not t.get('released')],
                    'account_quota': self.state['quota'],
                    'secondary_staleness': self.state['pending_staleness'] if reader == 'primary' else {},
                    'jobs': await self.jobs.inspect(reader),
                    'science_changes': ctx['record'].get('science_changes', {}),
                    **self.documents.list(reader)}
        if action == 'incorporate_edit':
            task = self.state['tasks'][reader]
            if (self.state['admission_block']
                    or task['context_id'] != ctx['record']['context_id']
                    or ctx['record']['state'] not in ('attached', 'turn_running')):
                raise jobs.JobError('Task lifecycle or revoked attachment blocks incorporation')
            if reader == 'primary' and isinstance(path, str) and not workspace.allowed_science(path):
                return self.incorporate_retired_evidence(ctx, path, parent, sha256)
            if (not isinstance(path, str)
                    or not workspace.allowed_science(path, reader, task['frozen_inputs'])):
                raise jobs.JobError('Incorporation requires a changed scientific path owned by this task')
            canonical = workspace.safe_path(self.project, path)
            observed = hashlib.sha256(verification.read_bytes(canonical, None)).hexdigest() if canonical.exists() else None
            if sha256 != observed:
                raise jobs.JobError('Human version changed; reread current canonical science before incorporation')
            changes = ctx['record'].setdefault('science_changes', {})
            baseline = ctx.get('publication_baseline', ctx['baseline']).get(path)
            if path not in changes and observed == baseline:
                raise jobs.JobError('No unresolved canonical change at this path')
            revision = verification.read_bytes(workspace.safe_path(ctx['drafts'], path), None)
            changes.setdefault(path, {'previous_sha256': baseline})['sha256'] = observed
            ctx['record']['input_changes'] = sorted(set(ctx['record'].get('input_changes', ())) | {path})
            acknowledgement = {'human_sha256': observed, 'draft_sha256': hashlib.sha256(revision).hexdigest()}
            ctx['record'].setdefault('incorporated_edits', {})[path] = acknowledgement
            self.save()
            return {'path': path, **acknowledgement}
        if action in ('finish_task', 'retire_task', 'propose_complete', 'propose_stop',
                      'submit_review', 'finalize_complete', 'finalize_stop'):
            async with self.decision_lock:
                self.require_quota()
                if (self.state['tasks'][reader]['operational_state'] != 'working'
                        or self.state['tasks'][reader]['context_id'] != ctx['record']['context_id']
                        or ctx['record']['state'] not in ('attached', 'turn_running')):
                    raise jobs.JobError('Task lifecycle or revoked attachment blocks decision controls')
                if action == 'submit_review':
                    return self.submit_review(ctx, path, sha256)
                if action == 'finish_task':
                    if self.state['tasks'][reader]['role'] not in ('researcher', 'verifier'):
                        raise jobs.JobError('Only delegated researchers/verifiers finish tasks')
                    text = self.scoped_text(ctx, path)
                    decisions.nonempty(text, 'delegated result')
                    self.validate_context_handoff(ctx['record']['context_id'])
                    self.state['tasks'][reader]['result_path'] = path
                    return self.queue_retirement(reader, 'Finished delegated work; primary must integrate result')
                if reader != 'primary':
                    raise jobs.JobError('Only primary may propose or finalize scientific decisions or retire tasks')
                if action == 'retire_task':
                    if path not in self.state['tasks'] or path == 'primary':
                        raise jobs.JobError('Retirement requires an existing secondary task ID')
                    return self.queue_retirement(path, 'Primary retired unfinished work; inspect retained handoff', checkpoint=True)
                if action.startswith('propose_'):
                    return await self.propose_decision(ctx, path, 'COMPLETE' if action == 'propose_complete' else 'STOP')
                return self.request_finalization(ctx, path, sha256,
                                                 'COMPLETE' if action == 'finalize_complete' else 'STOP')
        if action not in ('delegate', 'verify'):
            raise jobs.JobError('Unsupported legacy/terminal control; use V0-L4 proposal/review/finalization actions')
        if ctx['record']['task_id'] != 'primary' or parent not in self.state['tasks']:
            raise jobs.JobError('Only primary may assign a scientific task with a known parent')
        if self.state['admission_block'] or self.state['tasks'][reader].get('operational_state') != 'working':
            raise jobs.JobError('Admissions blocked by lifecycle')
        if not isinstance(path, str) or not workspace.allowed_science(path):
            raise jobs.JobError('Assignment must be primary scientific Markdown')
        task_id = 'task-' + uuid.uuid4().hex
        task_root = workspace.task_directory(task_id)
        # freeze and job admission cannot race. Changing outputs are not stable evidence.
        async with self.jobs.lock:
            self.require_quota()
            task = self.state['tasks'][reader]
            if (self.state['admission_block'] or task.get('operational_state') != 'working'
                    or ('context_id' in ctx['record'] and task['context_id'] != ctx['record']['context_id'])):
                raise jobs.JobError('Task lifecycle blocks assignment admission')
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

    def scoped_text(self, ctx, path):
        task_id = ctx['record']['task_id']
        if (not isinstance(path, str) or Path(path).suffix != '.md'
                or not workspace.allowed_science(path, task_id, self.state['tasks'][task_id]['frozen_inputs'])):
            raise jobs.JobError('Submission requires scoped scientific Markdown')
        return verification.read_bytes(workspace.safe_path(ctx['drafts'], path), None).decode('utf-8')

    def current_proposal(self, version=None):
        opposition = self.state['opposition']
        proposal = next((p for p in opposition['history'] if p['id'] == opposition['current']), None)
        if not proposal or proposal.get('invalidated') or version is not None and version != proposal['version']:
            raise jobs.JobError('Missing, invalidated or stale scientific proposal')
        return proposal

    def opposition_summary(self, offset=0):
        self.documents.check_offset(offset)
        opposition = self.state['opposition']
        history = list(reversed(opposition['history']))
        page = history[offset:offset + decisions.HISTORY_PAGE_SIZE]
        return {'opponent_id': opposition['opponent_id'], 'current': opposition['current'],
                'current_proposal': decisions.summary(history[0]) if history else None,
                'history': [decisions.summary(p) for p in page], 'history_total': len(history),
                'offset': offset, 'next_offset': offset + len(page) if offset + len(page) < len(history) else None}

    def read_history(self, identifier, part, offset):
        self.documents.check_offset(offset)
        proposal = next((p for p in self.state['opposition']['history'] if p['id'] == identifier), None)
        if not proposal or part not in ('proposal', 'review', 'final'):
            raise jobs.JobError('Use a known proposal ID and parent=proposal, review or final')
        text = (proposal.get('final_request', {}).get('text') if part == 'final'
                else proposal.get(part + '_text'))
        if text is None:
            raise jobs.JobError('Decision history part has not been submitted')
        content = text[offset:offset + documents.PAGE_CHARACTERS]
        end = offset + len(content)
        return {'id': identifier, 'part': part, 'version': proposal['version'],
                'sha256': hashlib.sha256(text.encode()).hexdigest(),
                'content': content, 'offset': offset, 'characters_total': len(text),
                'next_offset': end if end < len(text) else None}

    @staticmethod
    def task_summary(task):
        keys = ('task_id', 'workspace', 'parent_task', 'role', 'slot', 'phase',
                'operational_state', 'context_id', 'last_context_id', 'released',
                'inventory_verified', 'result_path')
        result = {k: task[k] for k in keys if k in task}
        result['objective'] = task['objective'][:1024]
        result['objective_truncated'] = len(task['objective']) > 1024
        result['handoff'] = workspace.handoff_path(task['task_id'])
        for key in ('context_error', 'retirement_error', 'retirement_requested'):
            if task.get(key):
                result[key] = task[key][:1024]
        result['incorporated_evidence_total'] = len(task.get('incorporated_evidence', {}))
        return result

    def evidence_drafts(self, path, *, reader=None):
        """Publication order: a context integrates its jobs; successors replace ancestors."""
        candidates = {}
        def include(identifier, drafts, task_id):
            if reader is not None and task_id != reader:
                return
            task = self.state['tasks'][task_id]
            if workspace.allowed_science(path, task_id, task['frozen_inputs']):
                candidate = workspace.safe_path(Path(drafts), path)
                if candidate.exists():
                    candidates[identifier] = candidate
        for ctx in self.contexts.values():
            context_id = ctx['record']['context_id']
            for job in self.state['jobs'].values():
                if job.get('origin_context_id') == context_id and job.get('drafts'):
                    include('job:' + job['job_id'], job['drafts'], job['task_id'])
            include('context:' + context_id, ctx['drafts'], ctx['record']['task_id'])
        for job in self.state['jobs'].values():
            if job.get('origin_context_id') not in self.contexts and job.get('drafts'):
                include('job:' + job['job_id'], job['drafts'], job['task_id'])
        return candidates

    def effective_bytes(self, path, *, check_edits=False, reader=None):
        if reader is not None and not workspace.allowed_science(
                path, reader, self.state['tasks'][reader]['frozen_inputs']):
            # Shared paths and supplied frozen inputs expose canonical bytes,
            # never another logical task's unpublished context/job drafts.
            return verification.read_bytes(verification.scientific_path(self.project, path), None)
        incorporation = (self.state['tasks']['primary'].get('incorporated_evidence', {}).get(path)
                         if reader is None else None)
        if incorporation:
            # This changes evidence selection only. It never publishes into the
            # retired owner's workspace or modifies its drafts/snapshots.
            raw = verification.read_bytes(verification.scientific_path(self.project, path), None)
            account = self.effective_bytes(incorporation['account_path'], check_edits=True)
            if (hashlib.sha256(raw).hexdigest() != incorporation['human_sha256']
                    or hashlib.sha256(account).hexdigest() != incorporation['account_sha256']):
                raise jobs.JobError('Incorporate current human edit before review: ' + path
                                    + ' (source or primary account changed)')
            return raw
        candidates = self.evidence_drafts(path, reader=reader)
        if candidates:
            identifier, source = next(reversed(candidates.items()))
            if check_edits:
                self.validate_draft_provenance(path, identifier, source)
        else:
            source = verification.scientific_path(self.project, path)
        return verification.read_bytes(source, None)

    def incorporate_retired_evidence(self, ctx, path, account_path, sha256):
        """Primary-owned acknowledgement of corrected, published delegate evidence."""
        primary = self.state['tasks']['primary']
        document = None
        for candidate in reversed(list(self.state['documents'].values())):
            if candidate['path'] != path:
                continue
            owner = self.state['tasks'][candidate['task_id']]
            record = self.state['contexts' if candidate['source_kind'] == 'context' else 'jobs'][candidate['source_id']]
            if (owner['role'] in ('researcher', 'verifier') and owner.get('released')
                    and owner.get('context_id') is None and record.get('cleanup_ok') is True
                    and not record.get('publication_pending') and 'publication_conflicts' in record
                    and not any(c['path'] == path for c in record['publication_conflicts'])
                    and path not in record.get('publication_superseded', ())):
                document = candidate
                break
        if document is None:
            raise jobs.JobError('Incorporation requires science owned by this task, or published evidence of a confirmed-retired delegate')
        self.documents.raw('primary', document['document_id'])
        raw = verification.read_bytes(verification.scientific_path(self.project, path), None)
        observed = hashlib.sha256(raw).hexdigest()
        if sha256 != observed:
            raise jobs.JobError('Human version changed; reread current canonical science before incorporation')
        if observed == document['sha256'] and path not in primary.get('incorporated_evidence', {}):
            raise jobs.JobError('No unresolved canonical change at this path')
        # scoped_text requires an actual saved primary draft; foreign paths,
        # protected inputs and canonical-only accounts cannot confer authority.
        account = self.scoped_text(ctx, account_path)
        decisions.nonempty(account, 'primary incorporation account')
        self.effective_bytes(account_path, check_edits=True)
        acknowledgement = {
            'task_id': document['task_id'], 'document_id': document['document_id'],
            'human_sha256': observed, 'account_path': account_path,
            'account_sha256': hashlib.sha256(account.encode()).hexdigest(),
            'context_id': ctx['record']['context_id']}
        primary.setdefault('incorporated_evidence', {})[path] = acknowledgement
        self.save()
        return {'path': path, **acknowledgement}

    def validate_draft_provenance(self, path, identifier, source):
        """A retained draft cannot replace a human revision without incorporation."""
        if source.suffix != '.md':
            return
        kind, source_id = identifier.split(':', 1)
        if kind == 'context':
            ctx = self.contexts[source_id]
            record = ctx['record']
            baseline = ctx.get('publication_baseline', ctx['baseline'])
            policy = record
        else:
            record = self.state['jobs'][source_id]
            ctx = self.contexts.get(record.get('origin_context_id'))
            if ctx is None:
                raise jobs.JobError('Retained job draft provenance unavailable: ' + path)
            baseline = ctx.get('publication_baseline', ctx['baseline'])
            policy = ctx['record']
        observed = workspace.file_digest(verification.scientific_path(self.project, path))
        digest = workspace.file_digest(source)
        # Successful publication advances this writer's expected canonical version.
        # Its old attachment baseline does not describe later human corrections.
        published = (record.get('cleanup_ok') is True and not record.get('publication_pending')
                     and 'publication_conflicts' in record
                     and path not in record.get('publication_superseded', ())
                     and not any(c['path'] == path for c in record['publication_conflicts'])
                     and any(self.state['documents'][i]['path'] == path
                             and self.state['documents'][i]['sha256'] == digest
                             for i in record.get('document_ids', ())))
        expected = digest if published else baseline.get(path)
        if observed == expected and (published or path not in policy.get('science_changes', {})):
            return
        if policy.get('incorporated_edits', {}).get(path) != {
                'human_sha256': observed, 'draft_sha256': digest}:
            raise jobs.JobError('Incorporate current human edit before review: ' + path)

    def decision_document(self, document_id):
        """Keep the snapshot immutable without letting it conceal source corrections."""
        raw = self.documents.raw('primary', document_id)
        document = self.state['documents'][document_id]
        path = document['path']
        if (path not in self.state['tasks']['primary'].get('incorporated_evidence', {})
                and not self.evidence_drafts(path)
                and workspace.file_digest(verification.scientific_path(self.project, path)) != document['sha256']):
            raise jobs.JobError('Incorporate current human edit before review: ' + path
                                + ' (retained draft provenance unavailable)')
        self.effective_bytes(path, check_edits=True)
        return raw

    def reviewed_observation(self, path, *, reader=None):
        return {'effective': hashlib.sha256(self.effective_bytes(path, reader=reader)).hexdigest(),
                'canonical': workspace.file_digest(verification.scientific_path(self.project, path)),
                'incorporation': (self.state['tasks']['primary'].get('incorporated_evidence', {}).get(path)
                                  if reader is None else None),
                'drafts': {identifier: workspace.file_digest(candidate)
                           for identifier, candidate in self.evidence_drafts(path, reader=reader).items()}}

    def validate_reviewed_versions(self, proposal):
        try:
            intake = workspace.read_intake(self.project)
            if intake.fingerprints != proposal['intake_fingerprints']:
                raise jobs.JobError('Authoritative questions/instructions/evidence/feedback changed')
            observations = [(None, p, v) for p, v in proposal['observations'].items()]
            reviewer = self.state['opposition']['opponent_id']
            observations += [(reviewer, p, v) for p, v in proposal.get('review_observations', {}).items()]
            for reader, path, old in observations:
                current = self.reviewed_observation(path, reader=reader)
                # Identical publication is harmless even before its writer's
                # bookkeeping settles. Otherwise recheck provenance so restoring
                # a pre-publication version cannot conceal a later human edit.
                if current['canonical'] != old['effective']:
                    self.effective_bytes(path, check_edits=True, reader=reader)
                if (current['effective'] != old['effective']
                        or current['incorporation'] != old.get('incorporation')
                        or current['canonical'] not in (old['canonical'], old['effective'])
                        or any(current['drafts'].get(k) != digest for k, digest in old['drafts'].items())
                        or any(digest != old['effective'] for k, digest in current['drafts'].items()
                               if k not in old['drafts'])):
                    raise jobs.JobError('Reviewed evidence changed: ' + path)
            entries = list(proposal['packet']['evidence'])
            entries += proposal.get('review_packet', {}).get('evidence', [])
            for entry in entries:
                if workspace.file_digest(workspace.safe_path(self.project, entry['path'])) != entry['sha256']:
                    raise jobs.JobError('Frozen packet integrity failure')
        except (OSError, ValueError) as exc:
            proposal.update(invalidated=str(exc), phase='invalidated')
            self.save()
            raise jobs.JobError('Scientific reassessment required: ' + str(exc)) from exc

    async def propose_decision(self, ctx, path, intent):
        text = self.scoped_text(ctx, path)
        value = decisions.proposal(text, intent)
        opposition = self.state['opposition']
        opponent_id = opposition['opponent_id']
        opponent = self.state['tasks'].get(opponent_id)
        runner = self.turns.get(opponent_id)
        if opponent and (not opponent.get('released') or runner and not runner.done()):
            raise jobs.JobError('Opponent still reviewing/retiring; inspect tasks before another proposal')
        async with self.jobs.lock:
            self.require_quota()
            if (self.state['tasks']['primary']['context_id'] != ctx['record']['context_id']
                    or self.state['tasks']['primary']['operational_state'] != 'working'
                    or ctx['record']['state'] not in ('attached', 'turn_running')):
                raise jobs.JobError('Task lifecycle or revoked attachment blocks proposal admission')
            blockers = [t for t in self.state['tasks'].values() if not t.get('released')]
            occupied = {t['slot'] for t in blockers}
            slot = next((i for i in range(self.config.max_agents) if i not in occupied), None)
            if slot is None:
                raise jobs.JobError('No slot for independent opposition; finish/retire delegates: '
                                    + ', '.join(t['task_id'] for t in blockers))
            active = [r['job_id'] for r in self.state['jobs'].values() if r['state'] in jobs.ACTIVE]
            if active:
                raise jobs.JobError('Finish or cancel active computations before freezing evidence: ' + ', '.join(active))
            intake = workspace.read_intake(self.project)
            opponent_id = opponent_id or 'task-' + uuid.uuid4().hex
            identifier = uuid.uuid4().hex
            destination = workspace.task_directory(opponent_id) + '/inputs/' + identifier
            extras = ['starting_evidence/RESEARCH_QUESTIONS.md']
            extras += [p for p in ('AGENTS.md', 'HUMAN_FEEDBACK.md') if (self.project / p).exists()]
            for target in verification.LINK.findall(text):
                if target.startswith('document:'):
                    document_id = target.removeprefix('document:')
                    self.decision_document(document_id)
                    document = self.state['documents'][document_id]
                    if (document['path'] in self.state['tasks']['primary'].get('incorporated_evidence', {})
                            or hashlib.sha256(self.effective_bytes(document['path'])).hexdigest() != document['sha256']):
                        # Present the current incorporated revision alongside the
                        # explicitly requested historical bytes, not in their place.
                        extras.append(document['path'])
                else:
                    source = verification.link_path(self.project, path, target)
                    if source is not None:
                        extras.append(source)
            # Freeze the primary's attributed account as well as the corrected
            # source, even when a proposal links only the old immutable snapshot.
            for source in list(extras):
                incorporation = self.state['tasks']['primary'].get('incorporated_evidence', {}).get(source)
                if incorporation:
                    extras.append(incorporation['account_path'])
            packet, _ = verification.freeze(self.project, path, ctx['drafts'], destination,
                decisions.PROPOSAL_FIELDS, None, extra=extras,
                resolve_document=self.decision_document,
                document_origin=lambda i: self.state['documents'][i]['path'],
                resolve_source=lambda source: self.effective_bytes(source, check_edits=True))
            sources = {e['source'] for e in packet['evidence']}
            for question in value['coverage']:
                if not set(question['evidence']).issubset(sources):
                    raise jobs.JobError('Coverage must reference explicitly frozen evidence sources')
            observations = {}
            for source in sources:
                if source.startswith('document:'):
                    source = self.state['documents'][source.removeprefix('document:')]['path']
                observations[source] = self.reviewed_observation(source)
            proposal = {'id': identifier, 'intent': intent, 'version': packet['version'], 'packet': packet,
                        'coverage': value['coverage'], 'intake_fingerprints': intake.fingerprints,
                        'observations': observations, 'previous': opposition['current'],
                        'phase': 'review_pending', 'proposal_text': text}
            if not opponent:
                opponent = self.add_task(opponent_id,
                    'Independently challenge terminal proposals, consequential results and stopping rationale. '
                    'Perform proportionate independent reasoning/reproduction; never approve mere plans.',
                    'primary', 'opponent', [workspace.task_directory(opponent_id) + '/inputs'])
                opposition['opponent_id'] = opponent_id
            else:
                opponent['slot'] = slot
                opponent.update(released=False, operational_state='working')
                opponent.pop('retirement_requested', None)
            opposition['current'] = identifier
            opposition['history'].append(proposal)
            self.save()
        self.turns[opponent_id] = asyncio.create_task(self.run_task(opponent_id))
        return {'status': 'review_pending', 'opponent_id': opponent_id, 'proposal': decisions.summary(proposal)}

    def submit_review(self, ctx, path, version):
        opposition = self.state['opposition']
        if ctx['record']['task_id'] != opposition['opponent_id']:
            raise jobs.JobError('Only the designated logical opponent may submit opposition')
        if not isinstance(version, str):
            raise jobs.JobError('Explicit proposal version sha256 is required')
        proposal = self.current_proposal(version)
        if proposal.get('review'):
            raise jobs.JobError('Review already delivered; primary must present a new proposal')
        self.validate_reviewed_versions(proposal)
        text = self.scoped_text(ctx, path)
        prior = {o['id'] for p in opposition['history'] if p.get('review')
                 for o in p['review']['objections']}
        review = decisions.review(text, proposal, prior)
        artifacts = self.validate_context_handoff(ctx['record']['context_id'])
        if any(r['state'] in jobs.ACTIVE for r in self.state['jobs'].values()):
            raise jobs.JobError('Finish or cancel computations before submitting stable review evidence')
        reader = ctx['record']['task_id']
        def resolve_document(identifier):
            self.documents.raw(reader, identifier)  # retain sibling-document isolation
            return self.decision_document(identifier)
        fields = decisions.REVIEW_FIELDS + (('Stopping rationale', 'Further work')
                                           if proposal['intent'] == 'STOP' else ())
        packet, _ = verification.freeze(self.project, path, ctx['drafts'],
            workspace.task_directory(reader) + '/inputs/reviews/' + proposal['id'], fields, None,
            extra=artifacts, resolve_document=resolve_document,
            document_origin=lambda i: self.state['documents'][i]['path'],
            resolve_source=lambda p: self.effective_bytes(p, check_edits=True, reader=reader))
        sources = {self.state['documents'][e['source'].removeprefix('document:')]['path']
                   if e['source'].startswith('document:') else e['source']
                   for e in packet['evidence']}
        proposal.update(review=review, review_text=text, review_path=path,
                        review_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        review_packet=packet,
                        review_observations={p: self.reviewed_observation(p, reader=reader) for p in sources},
                        review_context_id=ctx['record']['context_id'], phase='review_delivered')
        self.save()
        return self.queue_retirement(opposition['opponent_id'], 'Review delivered; retain objections for next proposal')

    def queue_retirement(self, task_id, reason, checkpoint=False):
        task = self.state['tasks'][task_id]
        if task.get('retirement_requested') or task.get('released'):
            raise jobs.JobError('Task already retiring or released')
        task.update(retirement_requested=reason, retirement_checkpoint=checkpoint, operational_state='retiring')
        context_id = task.get('context_id')
        if context_id in self.contexts:
            self.contexts[context_id]['lifecycle_event'].set()
        try:
            self.save()
        except (OSError, ValueError) as exc:
            task['persistence_error'] = str(exc)
        work = asyncio.create_task(self.retire_task(task_id))
        self.lifecycle_tasks.add(work)
        work.add_done_callback(self.lifecycle_tasks.discard)
        return {'status': 'retirement_pending', 'task_id': task_id}

    async def retire_task(self, task_id):
        task = self.state['tasks'][task_id]
        try:
            runner = self.turns.get(task_id)
            if runner and not runner.done():
                try:
                    await asyncio.wait_for(asyncio.shield(runner), 20)
                except Exception as exc:
                    task['retirement_turn_error'] = str(exc)
            context_id = task.get('context_id')
            if (task.get('retirement_checkpoint') and runner and runner.done()
                    and context_id and not self.state['admission_block']):
                try:
                    owned = await self.reconciled_jobs(task_id)
                    task['operational_state'] = 'checkpointing'
                    await self.native_turn(context_id, self.checkpoint_prompt(task, owned,
                        'Primary is retiring this unfinished task.'), responsive=False, timeout=90)
                    self.validate_context_handoff(context_id)
                except Exception as exc:
                    task['retirement_checkpoint_error'] = str(exc)
                finally:
                    task['operational_state'] = 'retiring'
            # Reconcile an admission that was already settling before retirement.
            async with self.jobs.lock:
                owned = [r for r in self.state['jobs'].values() if r['task_id'] == task_id]
            errors = [task['retirement_checkpoint_error']] if task.get('retirement_checkpoint_error') else []
            for record in owned:
                if record['state'] in jobs.ACTIVE:
                    try:
                        await self.jobs.cancel(task_id, record['job_id'])
                    except Exception as exc:
                        errors.append(str(exc))
            context_id = task.get('context_id')
            if context_id:
                client = self.clients.get(context_id)
                if getattr(client, 'active_turn_id', None):
                    try:
                        await asyncio.wait_for(client.interrupt(client.active_turn_id), 5)
                    except Exception as exc:
                        self.state['contexts'][context_id]['interrupt_error'] = str(exc)
                try:
                    await self.close_context(context_id)
                except Exception as exc:
                    errors.append(str(exc))
            records = [r for r in (*self.state['contexts'].values(), *self.state['jobs'].values())
                       if r['task_id'] == task_id]
            if not all(r.get('cleanup_ok') is True for r in records):
                raise jobs.JobError('Task cleanup unconfirmed; allocation retained')
            if errors:
                raise jobs.JobError('Task preservation failed; allocation retained: ' + '; '.join(errors))
            # A forced retirement without a usable handoff stays observable and
            # cannot later support successful scientific finalization.
            last = task.get('last_context_id')
            if last:
                self.validate_context_handoff(last, final=True)
            else:
                raise jobs.JobError('Missing context handoff; allocation retained')
            task.update(released=True, operational_state='idle')
        except Exception as exc:
            task['retirement_error'] = str(exc)
        try:
            self.save()
        except (OSError, ValueError) as exc:
            task['persistence_error'] = str(exc)

    def request_finalization(self, ctx, path, version, intent):
        if not isinstance(version, str):
            raise jobs.JobError('Explicit proposal version sha256 is required')
        proposal = self.current_proposal(version)
        if proposal['intent'] != intent or not proposal.get('review'):
            raise jobs.JobError('A current delivered opponent challenge is required')
        self.validate_reviewed_versions(proposal)
        opponent = self.state['tasks'][self.state['opposition']['opponent_id']]
        if not opponent.get('released'):
            raise jobs.JobError('Opponent preservation/cleanup still pending or failed')
        if intent == 'COMPLETE' and (proposal['review']['outcome'] != 'agree_complete'
                                            or not decisions.eligible(proposal['review'])):
            raise jobs.JobError('Substantive opposition prevents COMPLETE; revise evidence or propose STOP')
        text = self.scoped_text(ctx, path)
        value = decisions.final(text, proposal, self.state['tasks'], opponent['task_id'])
        self.validate_context_handoff(ctx['record']['context_id'])
        proposal.update(final_request={'path': path, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                                       'text': text, 'record': value}, phase='finalization_pending')
        self.state['requested_scientific_intent'] = intent
        if intent == 'STOP':
            self.state['stop_origin'] = 'scientific'
        self.schedule_shutdown('Primary scientific ' + intent + ': ' + value.get('reason', 'see frozen decision'),
                               'complete' if intent == 'COMPLETE' else 'scientific_stopped')
        return {'status': 'finalization_pending', 'version': version,
                'acknowledgement': 'No success until confirmed cleanup, preservation and version reassessment'}

    def observe_context(self, context_id, params, provenance='native', *, now=None):
        ctx = self.contexts[context_id]
        record = ctx['record']
        previous = record.get('native_measurement', {})
        sample = context_usage.observe(record, params, provenance)
        if 'staleness' in record:
            if staleness.measure(record['staleness'], sample, time.monotonic() if now is None else now):
                self.supersede_staleness(context_id, 'Measured context length changed')
        if (provenance == 'native' and sample['status'] == 'measured'
                and (sample['raw'] != previous.get('raw') or sample['turn_id'] != previous.get('turn_id'))):
            record['native_measurement_count'] = record.get('native_measurement_count', 0) + 1
            # A burst of trace events can arrive before the reader drains an
            # earlier usage report. Never credit that report to all later starts.
            record['measured_inference_count'] = min(
                record.get('native_inference_count', 0),
                record.get('measured_inference_count', 0) + 1)
        if record.get('threshold_observation') or sample['status'] != 'measured':
            task = self.state['tasks'][record['task_id']]
            if task['operational_state'] not in ('checkpointing', 'failed', 'telemetry_recovery'):
                task['operational_state'] = 'rollover_pending' if record.get('threshold_observation') else 'telemetry_recovery'
            ctx['lifecycle_event'].set()
        self.save()
        return sample

    def job_inspected(self, task, job_id):
        pending = task.get('pending_job_inspections', [])
        if job_id in pending:
            pending.remove(job_id)
            self.save()

    def successor_documents(self, task_id):
        result = self.documents.list(task_id)
        if task_id == 'primary' or task_id == self.state['opposition']['opponent_id']:
            result['opposition'] = self.opposition_summary()
        if task_id == 'primary':
            result['secondary_staleness'] = self.state['pending_staleness']
        task = self.state['tasks'][task_id]
        predecessor = task.get('last_context_id')
        result['input_changes'] = self.contexts[task['context_id']]['record']['input_changes']
        result['science_changes'] = self.contexts[task['context_id']]['record'].get('science_changes', {})
        if predecessor:
            record = self.state['contexts'][predecessor]
            validated = record.get('validated_handoff')
            if validated:
                # Exact ID and full text: default listing pagination cannot hide intake.
                result['validated_handoff'] = {**validated, 'content': self.documents.raw(
                    task_id, validated['document_id']).decode('utf-8')}
                result['owned_job_reconciliation'] = task.get('reconciled_jobs', [])
                self.contexts[task['context_id']]['record']['intake_handoff_id'] = validated['document_id']
        return result

    async def native_turn(self, context_id, text, responsive=True, timeout=None):
        ctx, client = self.contexts[context_id], self.clients[context_id]
        if context_id == self.quota_transport:
            await self.refresh_quota(context_id)
        await self.wait_quota_ready()
        if ctx['record']['task_id'] == 'primary':
            text += '\nSecondary inactivity observations (primary chooses response): ' + json.dumps(self.state['pending_staleness'])
        record = ctx['record']
        before = record.get('native_observation_count', 0)
        if record.get('native_inventory_verified'):
            self.validate_inventory(context_id, check_measurement=False)
        starts_before = record.get('native_inference_count', 0)
        measurements_before = record.get('native_measurement_count', 0)
        record['state'] = 'turn_running'
        self.save()
        async def dispatch_turn():
            # Primary replacement or a quota notification can win scheduling.
            # Wait through replacement, then check quota immediately before RPC.
            await self.wait_quota_ready()
            return await client.turn(text)
        work = asyncio.create_task(dispatch_turn())
        signal = asyncio.create_task(ctx['lifecycle_event'].wait()) if responsive else None
        started = time.monotonic()
        wait_phase, wait_bound = 'turn completion', timeout
        try:
            if signal:
                done, _ = await asyncio.wait((work, signal), return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
                if not done:
                    raise asyncio.TimeoutError
                if signal in done and not work.done():
                    # Never run lifecycle RPCs from the reader callback.
                    wait_phase, wait_bound = 'turn readiness before interruption', 15
                    await asyncio.wait_for(client.turn_ready.wait(), 15)
                    if not work.done() and client.active_turn_id:
                        await client.interrupt(client.active_turn_id)
                    wait_phase = 'interruption completion'
                    result = await asyncio.wait_for(asyncio.shield(work), 15)
                else:
                    result = await work
            else:
                result = await asyncio.wait_for(asyncio.shield(work), timeout) if timeout else await work
            record['turn_outcome'] = result
            if self.state['admission_block']:
                return result
            if result.get('status') != 'completed' and not (
                    responsive and ctx['lifecycle_event'].is_set() and result.get('status') == 'interrupted'):
                raise isolation.RuntimeUnavailable(f'Native turn outcome: {json.dumps(result)}')
            if not self.validate_inventory(context_id, check_measurement=False):
                raise isolation.RuntimeUnavailable('Native request inventory unavailable')
            starts = record.get('native_inference_count', 0) - starts_before
            measurements = record.get('native_measurement_count', 0) - measurements_before
            if (starts > 0 and result.get('status') == 'completed'
                    and starts == measurements
                    and record.get('native_measurement', {}).get('status') == 'measured'
                    and record.get('native_measurement', {}).get('turn_id') == result.get('id')):
                # A fully measured bounded recovery turn establishes a new
                # frontier after earlier lost notifications, without carrying
                # stale observation credit into future inferences.
                record['measured_inference_count'] = record['native_inference_count']
                record['measurement'] = record['native_measurement']
            elif starts > 0 and result.get('status') == 'completed':
                record['measurement'] = {'status': 'missing', 'error': 'Completed turn has an unmeasured native inference'}
                record['accounting_incomplete'] = True
            if record.get('native_observation_count', 0) == before:
                record['measurement'] = {'status': 'missing', 'error': 'No native usage observation at turn boundary'}
                record['accounting_incomplete'] = True
            if record.get('measurement', {}).get('status') != 'measured':
                task = self.state['tasks'][record['task_id']]
                if task['operational_state'] not in ('checkpointing', 'failed'):
                    task['operational_state'] = 'telemetry_recovery'
                ctx['lifecycle_event'].set()
                self.save()
            return result
        except asyncio.TimeoutError as exc:
            record['operational_timeout'] = {
                'phase': wait_phase, 'bound_seconds': wait_bound,
                'elapsed_seconds': time.monotonic() - started,
                'turn_id': getattr(client, 'active_turn_id', None)}
            self.save()
            raise isolation.RuntimeUnavailable(
                f'Operational {wait_phase} bound exceeded ({wait_bound} seconds); '
                f'context {context_id}; no scientific terminal decision') from exc
        finally:
            if signal:
                signal.cancel()
                await asyncio.gather(signal, return_exceptions=True)
            if not work.done():
                work.cancel()
            await asyncio.gather(work, return_exceptions=True)

    async def measured_intake(self, context_id):
        task = self.state['tasks'][self.contexts[context_id]['record']['task_id']]
        task['operational_state'] = 'telemetry_recovery'
        await self.native_turn(context_id,
            'Measurement intake/recovery only. Read the supplied validated handoff and current inputs. '
            'Call job_status for each reconciled owned job before any replacement. Preserve work at risk '
            'using write_draft, but do not rewrite already saved science or handoffs just to acknowledge intake. '
            'Defer scientific next actions to the ordinary work turn after intake. '
            'No new jobs or assignments. End this focused intake turn promptly.',
            responsive=False, timeout=180)
        record = self.contexts[context_id]['record']
        if record.get('measurement', {}).get('status') != 'measured':
            raise isolation.RuntimeUnavailable('Reliable context telemetry unavailable after bounded intake/recovery')
        task['operational_state'] = 'rollover_pending' if record.get('threshold_observation') else 'working'
        self.contexts[context_id]['lifecycle_event'].clear()
        self.save()

    async def reconciled_jobs(self, task_id):
        # Include settling admissions under the same job lock; summaries are bounded.
        async with self.jobs.lock:
            records = [r for r in self.state['jobs'].values() if r['task_id'] == task_id]
            for record in records:
                if record['state'] in jobs.ACTIVE:
                    await self.jobs._reconcile(record)
            return [jobs.public(r) for r in records]

    def validate_context_handoff(self, context_id, final=False):
        ctx = self.contexts[context_id]
        record = ctx['record']
        task_id = record['task_id']
        task = self.state['tasks'][task_id]
        rel = workspace.handoff_path(task_id)
        versions = {self.state['documents'][i]['path']: i for i in record.get('document_ids', [])}
        artifact_evidence = {}
        def resolve(path):
            raw = read_artifact(path)
            if not raw.strip():
                raise workspace.InputError('Handoff artifact is empty: ' + path)
            artifact_evidence[path] = {'sha256': hashlib.sha256(raw).hexdigest(),
                'document_id': path.removeprefix('document:') if path.startswith('document:') else versions.get(path),
                'kind': 'immutable_document' if path.startswith('document:') or path in versions else 'ordinary_file_observation'}
            return raw
        def read_artifact(path):
            if path.startswith('document:'):
                return self.documents.raw(task_id, path.removeprefix('document:'))
            if final and path in versions:
                return self.documents.raw(task_id, versions[path])
            proposed = workspace.safe_path(ctx['drafts'], path)
            if not final and proposed.exists():
                if not workspace.allowed_science(path, task_id, task['frozen_inputs']):
                    raise workspace.InputError('Foreign draft artifact')
                return verification.read_bytes(proposed, None)
            return verification.read_bytes(verification.scientific_path(self.project, path), None)
        if final:
            if record.get('job_handoff_error'):
                raise workspace.InputError('Operational job handoff unavailable: ' + record['job_handoff_error'])
            if rel not in versions or record.get('document_snapshot_error'):
                raise workspace.InputError('Final handoff snapshot unavailable')
            text = self.documents.raw(task_id, versions[rel]).decode('utf-8')
        else:
            try:
                text = verification.read_bytes(workspace.safe_path(ctx['drafts'], rel), None).decode('utf-8')
            except FileNotFoundError as exc:
                raise workspace.InputError(
                    f'Missing handoff draft: {rel}. Save it with write_draft at that exact '
                    'project-relative path; missing parent directories are created automatically.') from exc
        active = [r for r in self.state['jobs'].values() if r['task_id'] == task_id and r['state'] in jobs.ACTIVE]
        artifacts = workspace.validate_handoff(self.project, text, task_id=task_id, task=task,
            resolve_artifact=resolve, owned_jobs=active)
        if final:
            record['validated_handoff'] = {**self.state['documents'][versions[rel]], 'artifacts': artifacts,
                'artifact_versions': {path: versions[path] for path in artifacts if path in versions},
                'artifact_evidence': artifact_evidence}
            self.save()
        return artifacts

    def checkpoint_prompt(self, task, owned, reason):
        task_id = task['task_id']
        return (
            reason + ' Save useful science and repair the concise handoff now. '
            'No new computations or assignments. Use write_draft and document reads/job_status only. '
            f'Save the handoff with write_draft(path="{workspace.handoff_path(task_id)}", content=...). '
            'This is an authorized project-relative destination, not relative to your workspace. '
            'Missing parent directories are created automatically. Link artifacts relative to handoffs/. '
            'Use exact Objective, Parent question, Phase and Role sections from this metadata '
            '(prefix every Objective line with > if it contains Markdown headings): '
            + json.dumps({k: task[k] for k in ('task_id', 'objective', 'parent_task', 'phase', 'role')})
            + '. Include all ordinary required handoff sections, plus ## Jobs with purpose, outputs/checkpoints '
            'and job_status/job_wait/job_cancel guidance for every surviving job. Operational command/cwd/deadline '
            'metadata is retained by runtime, so refer to these exact job IDs: ' + json.dumps(owned)
            + '. Opponents also preserve nonempty ## Review history and ## Objections (including resolved objections). '
            'Link saved scientific artifacts, using document:ID for earlier immutable versions. End this checkpoint turn.')

    async def rollover(self, task_id, context_id):
        task = self.state['tasks'][task_id]
        record = self.contexts[context_id]['record']
        if record.get('rollover_attempted'):
            raise isolation.RuntimeUnavailable('Repeated rollover attempt refused')
        record['rollover_attempted'] = True
        task['operational_state'] = 'checkpointing'
        owned = await self.reconciled_jobs(task_id)
        checkpoint = self.checkpoint_prompt(task, owned, 'Context reached the measured 55% threshold.')
        for attempt in range(2):
            await self.native_turn(context_id, checkpoint, responsive=False, timeout=90)
            try:
                self.validate_context_handoff(context_id)
                break
            except (OSError, ValueError) as exc:
                record['handoff_validation_error'] = str(exc)
                if attempt:
                    raise
                checkpoint = 'Repair this unusable handoff using existing science only: ' + str(exc) + chr(10) + checkpoint
        cleanup = await self.close_context(context_id)
        if not cleanup['confirmed']:
            raise isolation.RuntimeUnavailable('Predecessor context closure unconfirmed')
        self.validate_context_handoff(context_id, final=True)
        successor = await self.successor(task_id)
        record['successor_context_id'] = successor
        if self.state['contexts'][successor]['native_thread_id'] == record['native_thread_id']:
            raise isolation.RuntimeUnavailable('Successor reused predecessor native thread')
        self.save()
        return successor

    async def run_task(self, task_id):
        context_id = None
        task = self.state['tasks'][task_id]
        try:
            context_id = task.get('context_id') or await self.attach_admitted(task_id)
            while not self.state['admission_block'] and not task.get('retirement_requested'):
                await self.measured_intake(context_id)
                while not self.state['admission_block'] and not task.get('retirement_requested'):
                    record = self.contexts[context_id]['record']
                    if (task['operational_state'] == 'telemetry_recovery'
                            or record.get('measurement', {}).get('status') != 'measured'):
                        await self.measured_intake(context_id)
                        continue
                    if record.get('threshold_observation'):
                        context_id = await self.rollover(task_id, context_id)
                        break
                    task['operational_state'] = 'working'
                    await self.native_turn(context_id,
                        'Continue the same scientific task from current artifacts. Make useful progress, '
                        'inspect existing jobs before replacements, save evidence and update the handoff. '
                        'A normal turn ending leaves this logical task active.')
        except Exception as exc:
            if not task.get('retirement_requested') and (
                    not self.state['admission_block'] or self.state['state'] not in
                    ('stopping', 'paused', 'quota_stopped', 'quota_unavailable', 'complete', 'scientific_stopped')):
                task.update(operational_state='failed', context_error=f'{type(exc).__name__}: {exc}')
                if task_id == 'primary':
                    self.schedule_shutdown('Primary deterministic control path failed: ' + str(exc), 'failed')
                for job_id, record in list(self.state['jobs'].items()):
                    if record['task_id'] == task_id and record['state'] in jobs.ACTIVE:
                        try:
                            await self.jobs.cancel(task_id, job_id)
                        except Exception as cleanup_exc:
                            task['job_cleanup_error'] = str(cleanup_exc)
        finally:
            # Attach may fail after creating a partial successor; it owns its cleanup.
            if self.shutdown_task:
                await asyncio.shield(self.shutdown_task)
            attached = task.get('context_id') or context_id
            if attached and attached in self.contexts and not self.shutdown_task and not task.get('retirement_requested'):
                try:
                    await self.close_context(attached)
                except Exception as exc:
                    task['context_cleanup_error'] = str(exc)
                    self.state['admission_block'] = self.state['admission_block'] or 'Context cleanup/preservation failed'
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
        if context_id == self.quota_transport:
            self.quota_transport = None
            self.state['quota']['transport_unavailable'] = True
            self.quota_ready.clear()
        self.supersede_staleness(context_id, 'Context closed/replaced')
        # Revoke admissions before closing the connection; surviving jobs are untouched.
        record['state'] = 'closing'
        task['inventory_verified'] = False
        try:
            self.save()
        except (OSError, ValueError) as exc:
            record['persistence_error'] = str(exc)
        try:
            ctx['server'].close()
            await ctx['server'].wait_closed()
        except Exception as exc:
            record['rpc_close_error'] = str(exc)
        client = self.clients.pop(context_id, None)
        if client:
            try:
                cleanup = await client.close()
            except Exception as exc:
                record['backend_close_error'] = str(exc)
                cleanup = await isolation.stop_owned(record.get('service'))
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
            try:
                self.documents.capture(record, 'context', ctx['drafts'], task['frozen_inputs'])
                # Live outputs are observations, not immutable checkpoint hashes.
                job_handoff = await self.jobs.inspect(record['task_id'])
                job_handoff['active_details'] = [jobs.public(r) for r in self.state['jobs'].values()
                    if r['task_id'] == record['task_id'] and r['state'] in jobs.ACTIVE]
                jobs.atomic(ctx['root'] / 'job-handoff.json', job_handoff)
                record['job_handoff_path'] = (ctx['root'] / 'job-handoff.json').relative_to(self.project).as_posix()
            except (OSError, ValueError) as exc:
                record['job_handoff_error'] = str(exc)
            finally:
                ctx['private'].close()
            try:
                self.finalize_publications()
            except (OSError, ValueError) as exc:
                record['persistence_error'] = str(exc)
        else:
            self.state['admission_block'] = self.state['admission_block'] or 'Context cleanup unconfirmed'
        try:
            self.save()
        except (OSError, ValueError) as exc:
            record['persistence_error'] = str(exc)
        return cleanup

    def snapshot_job_documents(self, record):
        self.documents.capture(record, 'job', Path(record['drafts']),
                               self.state['tasks'][record['task_id']].get('frozen_inputs', ()))

    def resolve_publication_conflicts(self, record, policy, paths):
        """Retain conflict history, resolving only exact incorporated publications."""
        ancestors = set()
        context_id = policy.get('context_id')
        while context_id in self.state['contexts']:
            ancestors.add(context_id)
            context_id = self.state['contexts'][context_id].get('predecessor')
        for earlier in (*self.state['contexts'].values(), *self.state['jobs'].values()):
            if earlier is record or earlier['task_id'] != record['task_id']:
                continue
            origin = earlier.get('context_id', earlier.get('publication_context_id', earlier.get('origin_context_id')))
            if origin not in ancestors:
                continue
            for conflict in earlier.get('publication_conflicts', ()):
                path = conflict['path']
                acknowledgement = policy.get('incorporated_edits', {}).get(path)
                if (path in paths and acknowledgement and not conflict.get('resolution')
                        and workspace.file_digest(workspace.safe_path(self.project, path)) == acknowledgement['draft_sha256']):
                    conflict['resolution'] = {
                        'source_id': record.get('context_id', record.get('job_id')),
                        'sha256': acknowledgement['draft_sha256'],
                        'human_sha256': acknowledgement['human_sha256']}

    def finalize_publications(self):
        """No await: admissions cannot interleave with quiescent path-based writes."""
        if not jobs.science_quiescent(self.state):
            return
        changed = False
        # Jobs have private batches too, but share their logical task's unresolved
        # human edits. A fresh job baseline cannot acknowledge those edits.
        batches = {}
        superseded = {}
        intake_changes = {}
        sources = [('context', ctx['record'], ctx['drafts'],
                    ctx.get('publication_baseline', ctx['baseline']), ctx['record'])
                   for ctx in self.contexts.values()]
        for record in self.state['jobs'].values():
            task = self.state['tasks'][record['task_id']]
            policy = self.state['contexts'].get(task.get('last_context_id'),
                     self.state['contexts'].get(record.get('origin_context_id'), {}))
            sources.append(('job', record, Path(record['drafts']) if record.get('drafts') else None,
                            record.get('science_baseline', {}), policy))
        for kind, record, drafts, baseline, policy in sources:
            if not record.get('publication_pending'):
                continue
            key = (kind, record['context_id'] if kind == 'context' else record['job_id'])
            try:
                task_id = record['task_id']
                if (policy.get('context_id') in self.contexts
                        and policy['context_id'] == self.state['tasks'][task_id].get('last_context_id')):
                    # Observe before any batch writes. Jobs may have captured a
                    # human correction after attachment in their own baseline.
                    # Intake compares the logical context's baseline and known
                    # publications, so those corrections still need incorporation.
                    if task_id not in intake_changes:
                        _, _, intake_changes[task_id] = self.science_intake(task_id)
                    policy['science_changes'] = intake_changes[task_id]
                    policy['input_changes'] = sorted(set(policy.get('input_changes', ()))
                                                     | policy['science_changes'].keys())
                paths = {
                    rel for rel, _, _ in workspace.draft_proposals(
                        self.project, drafts, record['task_id'],
                        self.state['tasks'][record['task_id']]['frozen_inputs'])}
                batches[key] = (record, drafts, baseline, policy, paths)
            except (OSError, ValueError) as exc:
                record['publication_error'] = str(exc)
                record['publication_pending'] = False
                changed = True

        # Validate before selecting descendants. Context drafts are the scientist's
        # synthesis of jobs from that context; successor jobs may replace ancestor
        # context drafts. Earlier immutable snapshots remain available.
        for key, (record, _, _, _, paths) in batches.items():
            context_id = record.get('context_id', record.get('origin_context_id'))
            context = self.state['contexts'].get(context_id, {})
            ancestor = context_id if key[0] == 'context' else context.get('predecessor')
            while ancestor in self.state['contexts']:
                earlier = self.state['contexts'][ancestor]
                if earlier['task_id'] != record['task_id']:
                    break
                for prior, (prior_record, _, _, _, prior_paths) in batches.items():
                    prior_context = prior_record.get('context_id', prior_record.get('origin_context_id'))
                    if prior != key and prior_context == ancestor:
                        superseded.setdefault(prior, set()).update(paths & prior_paths)
                ancestor = earlier.get('predecessor')
        index_contexts = {}
        for key, (record, drafts, original_baseline, policy, paths) in batches.items():
            try:
                baseline = dict(original_baseline)
                incorporated = []
                unresolved = set(policy.get('science_changes', {}))
                for path, acknowledgement in policy.get('incorporated_edits', {}).items():
                    revision_path = workspace.safe_path(drafts, path)
                    if not revision_path.exists():
                        continue
                    revision = verification.read_bytes(revision_path, None)
                    if (hashlib.sha256(revision).hexdigest() == acknowledgement['draft_sha256']
                            and acknowledgement['human_sha256'] == policy['science_changes'][path]['sha256']):
                        baseline[path] = acknowledgement['human_sha256']
                        incorporated.append(path)
                        unresolved.discard(path)
                conflicts, preserved = workspace.publish_drafts(
                    self.project, drafts, baseline, incorporated, record['task_id'],
                    self.state['tasks'][record['task_id']]['frozen_inputs'],
                    superseded=superseded.get(key, ()), unresolved=unresolved)
                record['publication_conflicts'] = conflicts
                record['preserved_human_edits'] = preserved
                record['publication_superseded'] = sorted(superseded.get(key, ()))
                published = (paths - {c['path'] for c in conflicts}
                             - superseded.get(key, set()))
                self.resolve_publication_conflicts(record, policy, published & set(incorporated))
                if key[0] == 'job':
                    record['publication_context_id'] = policy.get('context_id')
                ctx = self.contexts.get(policy.get('context_id'))
                if ctx:
                    index_contexts.setdefault(record['task_id'], ctx)
            except (OSError, ValueError) as exc:
                record['publication_error'] = str(exc)
            record['publication_pending'] = False
            changed = True
        # Regenerate navigation once after all versions are settled. Repeated
        # refreshes against a shared old baseline would preserve our own index
        # updates as purported human edits.
        for task_id, ctx in index_contexts.items():
            try:
                self.index_baseline.update(workspace.refresh_indexes(
                    self.project, expected=self.index_baseline, task_id=task_id))
            except (OSError, ValueError) as exc:
                ctx['record']['publication_error'] = str(exc)
        if changed:
            self.save()

    async def successor(self, task_id):
        task = self.state['tasks'][task_id]
        if task['context_id'] is not None:
            raise jobs.JobError('Predecessor context closure unconfirmed')
        task['reconciled_jobs'] = await self.reconciled_jobs(task_id)
        task['pending_job_inspections'] = [r['job_id'] for r in task['reconciled_jobs'] if r['state'] in jobs.ACTIVE]
        task['operational_state'] = 'telemetry_recovery'
        return await self.attach_admitted(task_id)

    def schedule_shutdown(self, reason, outcome):
        # This runs in the RPC reader too: no lifecycle RPCs or awaits here.
        if terminal_acknowledged(self.project, self.state):
            return
        if outcome in ('failed', 'quota_unavailable'):
            self.state['operational_failure'] = {'reason': reason, 'outcome': outcome}
        self.state.update(admission_block=self.state['admission_block'] or reason, state='stopping')
        self.quota_ready.set()
        for ctx in self.contexts.values():
            ctx['lifecycle_event'].set()
        if self.shutdown_task is None:
            self.shutdown_task = asyncio.create_task(self.block_and_cleanup(reason, outcome=outcome))

    def observe_quota(self, context_id, payload, *, full=False, provenance='native', now=None, epoch=None):
        if self.state.get('terminal_committed'):
            return None
        if context_id != self.quota_transport or context_id is None:
            return None  # secondary and retired-primary notifications have no authority
        record = self.state['quota']
        sample = quota.observe(record, payload, full=full, provenance=provenance, now=now, epoch=epoch)
        if full:
            record['transport_unavailable'] = False
        if record.get('cutoff'):
            self.state['stop_origin'] = 'quota'
            self.schedule_shutdown(
                f"Weekly quota STOP: observed {record['cutoff']['remaining_percent']}% remaining <= 15%", 'quota_stopped')
        elif (full or record.get('preflight_ok') and not record.get('transport_unavailable')) and (
                not self.state['admission_block'] or self.state.get('requested_scientific_intent')):
            error = quota.admission_error({**self.state, 'admission_block': None}, now=now, epoch=epoch)
            if error:
                record['admission_error'] = error
                self.schedule_shutdown(error + '; no observed quota cutoff', 'quota_unavailable')
        if full and not quota.admission_error(self.state, now=now, epoch=epoch):
            self.quota_ready.set()
        try:
            self.save()
        except (OSError, ValueError) as exc:
            self.state['persistence_error'] = str(exc)
        return sample

    async def refresh_quota(self, context_id):
        if context_id != self.quota_transport:
            raise isolation.RuntimeUnavailable('Primary quota transport unavailable')
        try:
            payload = await self.clients[context_id].read_quota()
        except Exception as exc:
            if context_id == self.quota_transport:
                self.state['quota'].update(read_error=str(exc), status='unavailable')
                self.schedule_shutdown('Weekly quota read failed; no observed quota cutoff', 'quota_unavailable')
            raise
        self.observe_quota(context_id, payload, full=True)
        self.require_quota()

    async def monitor_quota(self):
        while not self.state['admission_block']:
            await asyncio.sleep(quota.POLL_SECONDS)
            context_id = self.quota_transport
            # Expected primary replacement is bounded by existing attach/RPC bounds.
            if context_id and context_id in self.clients:
                try:
                    await self.refresh_quota(context_id)
                except Exception:
                    if self.state['admission_block']:
                        return
                    raise

    def supersede_staleness(self, context_id, reason):
        notice = self.state['pending_staleness'].pop(context_id, None)
        if notice:
            notice.update(superseded=reason, superseded_epoch=time.time())

    def check_staleness(self, now=None, provenance='monotonic-clock'):
        now = time.monotonic() if now is None else now
        emitted = []
        for context_id, ctx in self.contexts.items():
            record = ctx['record']
            clock = record.get('staleness')
            if (not clock or record.get('cleanup_ok') or record['state'] not in ('attached', 'turn_running')
                    or record.get('measurement', {}).get('status') != 'measured'):
                continue
            for observation in staleness.due(clock, self.state['secondary_staleness_seconds'], now):
                notice = {**observation, 'task_id': record['task_id'], 'context_id': context_id,
                          'provenance': provenance, 'emitted_epoch': time.time(),
                          'message': 'Measured secondary context length unchanged; primary chooses the response. '
                                     'A long computation may legitimately cause this warning; no scientific failure is asserted.'}
                self.state['staleness_history'].append(notice)
                self.state['pending_staleness'][context_id] = notice
                emitted.append(notice)
        if emitted:
            self.save()
        return emitted

    async def deliver_staleness(self):
        context_id = self.state['tasks']['primary'].get('context_id')
        client = self.clients.get(context_id)
        turn_id = getattr(client, 'active_turn_id', None)
        if (not turn_id or quota.admission_error(self.state)
                or self.state['tasks']['primary']['operational_state'] != 'working'):
            return
        notices = [n for n in self.state['pending_staleness'].values() if not n.get('delivered')]
        if not notices:
            return
        try:
            await client.steer(turn_id, 'Secondary inactivity observations; choose an appropriate response: '
                               + json.dumps(notices))
            for notice in notices:
                notice['delivered'] = {'context_id': context_id, 'turn_id': turn_id,
                                       'epoch': time.time(), 'basis': 'native turn/steer RPC accepted; no scientific acknowledgement claimed'}
        except Exception as exc:
            # Completion/replacement races leave observations pending.
            for notice in notices:
                notice['delivery_error'] = str(exc)
        self.save()

    def save_quota_stop(self, confirmed):
        """Operational record only. Never manufacture scientific handoffs/findings."""
        text = '# Runtime quota STOP\n\n' + json.dumps({
            'origin': 'quota', 'first_cutoff': self.state['quota']['cutoff'],
            'cleanup_confirmed': confirmed, 'cleanup': self.state.get('cleanup'),
            'contexts': self.state['contexts'], 'jobs': self.state['jobs'],
            'limitations': 'No post-cutoff inference or opponent review. Existing drafts, partial outputs and '
                'immutable documents are retained where observed; handoff usability is not assumed. '
                'Saving/cleanup may consume additional quota; exactly 15% remaining is not guaranteed. '
                'Explicit launch and quota preflight are necessary; STOP resumption is unsupported until L5.'
        }, indent=2) + '\n'
        note = (f'handoffs/quota-stop-{self.state["run_id"]}.md' if confirmed
                else '.research_pipeline/quota-stop.md')
        self.state['stop_note'] = note
        failures = []
        for path in (note, 'STOP'):
            try:
                workspace.atomic_text(workspace.safe_path(self.project, path), text)
            except (OSError, ValueError) as exc:
                failures.append(f'{path}: {exc}')
        if confirmed:
            try:
                current = workspace.science_fingerprints(self.project).get('RESEARCH_STATUS.md')
                published_status = {d['sha256'] for d in self.state['documents'].values()
                                    if d['task_id'] == 'primary' and d['path'] == 'RESEARCH_STATUS.md'}
                if current == self.status_baseline or current in published_status:
                    status_path = self.project / 'RESEARCH_STATUS.md'
                    status = workspace.read_input_unbounded(status_path)
                    status += (f'\n\n## Runtime quota STOP\n\nObserved '
                        f'{self.state["quota"]["cutoff"]["remaining_percent"]}% weekly remaining. '
                        f'Owned cleanup confirmed={confirmed}. No opponent review or scientific decision. '
                        f'See [operational handoff]({note}) for observations, retained artifacts, saving '
                        'limitations and unfinished jobs. Saving/cleanup may consume more quota. '
                        'Resumption remains unsupported until L5.\n')
                    workspace.atomic_text(status_path, status)
                    self.status_baseline = hashlib.sha256(status.encode()).hexdigest()
                else:
                    self.state['stop_status_preserved_human_edit'] = True
                self.index_baseline.update(workspace.refresh_indexes(
                    self.project, expected=self.index_baseline))
            except (OSError, ValueError) as exc:
                failures.append(f'status/index: {exc}')
        else:
            self.state['stop_status_deferred_cleanup'] = True
        if failures:
            self.state['stop_persistence_errors'] = failures
        return text, not failures

    def save_scientific_terminal(self, confirmed, update_status=True):
        """Keep intent and opposition readable even if checkpoint/publication fails."""
        proposal = self.state['opposition']['history'][-1]
        intent = proposal['intent']
        note = f'handoffs/decision-{proposal["id"]}.md'
        text = f'# Scientific {intent}\n\n' + proposal['final_request']['text'] + (
            '\n\n## Frozen proposal\n\n' + proposal['proposal_text']
            + '\n\n## Opponent challenge\n\n' + proposal['review_text']
            + '\n\n## Actual runtime preservation and interruption\n\n```json\n'
            + json.dumps({'origin': 'scientific', 'version': proposal['version'],
                'actual_outcome': self.state['state'],
                'cleanup_confirmed': confirmed, 'cleanup': self.state.get('cleanup'),
                'tasks': self.state['tasks'], 'jobs': self.state['jobs'],
                'contexts': self.state['contexts'],
                'documents': self.state['documents'],
                'errors': {k: self.state.get(k) for k in ('persistence_error', 'terminal_error')},
                'continuation': 'Explicit resume/reopening requires L5; do not duplicate retained work.'},
                indent=2) + '\n```\n')
        self.state['terminal_note'] = note
        failures = []
        # STOP preserves its explanation before cleanup; COMPLETE is written only
        # after all checks. Neither early record claims successful finalization.
        for path in (note, intent):
            try:
                workspace.atomic_text(workspace.safe_path(self.project, path), text)
            except (OSError, ValueError) as exc:
                failures.append(f'{path}: {exc}')
        if confirmed and update_status:
            try:
                current = workspace.file_digest(self.project / 'RESEARCH_STATUS.md')
                published = {d['sha256'] for d in self.state['documents'].values()
                             if d['task_id'] == 'primary' and d['path'] == 'RESEARCH_STATUS.md'}
                if current != self.status_baseline and current not in published:
                    raise workspace.InputError('Human RESEARCH_STATUS.md edit preserved; incorporation required')
                status = workspace.read_input_unbounded(self.project / 'RESEARCH_STATUS.md')
                status += f'\n\n## Scientific {intent}\n\nSee [decision and opposition]({note}). ' \
                    'This record includes reasons, recovery attempts, unresolved work, artifacts, ' \
                    'actual cleanup and continuation guidance. Scientific acceptance by the human remains separate.\n'
                workspace.atomic_text(self.project / 'RESEARCH_STATUS.md', status)
                self.status_baseline = hashlib.sha256(status.encode()).hexdigest()
                self.index_baseline.update(workspace.refresh_indexes(self.project, expected=self.index_baseline))
            except (OSError, ValueError) as exc:
                failures.append(f'status/index: {exc}')
        if failures:
            self.state['terminal_persistence_errors'] = failures
        return text, not failures

    async def block_and_cleanup(self, reason, outcome='paused'):
        # Latch before any cleanup/checkpoint operation; failed saves cannot bypass it.
        self.state['admission_block'] = self.state['admission_block'] or reason
        self.quota_ready.set()
        async with self.cleanup_lock:
            if (terminal_acknowledged(self.project, self.state) and self.state.get('cleanup_ok')
                    and self.state.get('finalization_ok')):
                return True  # inspection/pause cannot replace an acknowledged outcome
            self.state['state'] = 'stopping'
            return await self._block_and_cleanup(reason, outcome)

    async def _block_and_cleanup(self, reason, outcome):
        if outcome == 'paused' and self.state.get('requested_scientific_intent'):
            outcome = 'failed'  # unacknowledged scientific finalization is not an ordinary pause
        if self.state.get('stop_origin') == 'quota':
            outcome = 'quota_stopped'
        elif self.state.get('operational_failure'):
            outcome = self.state['operational_failure']['outcome']
        elif outcome == 'scientific_stopped':
            try:
                self.save_scientific_terminal(False)
            except (OSError, ValueError) as exc:
                self.state['persistence_error'] = str(exc)
        try:
            self.save()
        except (OSError, ValueError) as exc:
            self.state['persistence_error'] = str(exc)
        outcomes = {}
        async def stop_jobs():
            # Wait for settling admissions before enumerating. Their release gate
            # already sees the synchronous block, so no command can escape.
            async with self.jobs.lock:
                identifiers = list(self.state['jobs'])
            for job_id in identifiers:
                record = self.state['jobs'][job_id]
                if record['state'] in jobs.ACTIVE:
                    try:
                        cancelled = await self.jobs.cancel(record['task_id'], job_id)
                        outcomes[job_id] = cancelled.get('cleanup', {'confirmed': False})
                    except Exception as exc:
                        outcomes[job_id] = record.get('cleanup', {'confirmed': False, 'reason': str(exc)})
                        record['preservation_error'] = str(exc)
        job_cleanup = asyncio.create_task(stop_jobs())
        for context_id in list(self.clients):
            try:
                client = self.clients.get(context_id)
                if getattr(client, 'active_turn_id', None):
                    try:
                        await asyncio.wait_for(client.interrupt(client.active_turn_id), 5)
                    except Exception as exc:
                        self.state['contexts'][context_id]['interrupt_error'] = str(exc)
                outcomes[context_id] = await self.close_context(context_id)
            except Exception as exc:
                record = self.state['contexts'][context_id]
                outcomes[context_id] = record.get('cleanup', {'confirmed': False, 'reason': str(exc)})
                record['preservation_error'] = str(exc)
        for record in self.state['contexts'].values():
            if not record.get('cleanup_ok') and record['context_id'] not in outcomes:
                context_id = record['context_id']
                if context_id in self.contexts:
                    try:
                        outcomes[context_id] = await self.close_context(context_id)
                    except Exception as exc:
                        outcomes[context_id] = {'confirmed': False, 'reason': str(exc)}
                else:
                    try:
                        cleanup = await isolation.stop_owned(record.get('service'))
                    except Exception as exc:
                        cleanup = {'confirmed': False, 'reason': str(exc)}
                    outcomes[context_id] = cleanup
                    record.update(cleanup=cleanup, cleanup_ok=cleanup['confirmed'],
                                  state='closed' if cleanup['confirmed'] else 'cleanup_unconfirmed')
                    if cleanup['confirmed']:
                        task = self.state['tasks'][record['task_id']]
                        if task['context_id'] == context_id:
                            task.update(last_context_id=context_id, context_id=None)
        await job_cleanup
        confirmed = all(o['confirmed'] for o in outcomes.values()) and jobs.science_quiescent(self.state)
        if self.state.get('stop_origin') == 'quota':
            outcome = 'quota_stopped'
        elif self.state.get('operational_failure'):
            outcome = self.state['operational_failure']['outcome']
        self.state.update(state=outcome if confirmed else 'cleanup_unconfirmed', cleanup_ok=confirmed,
                          cleanup=outcomes, cleanup_outcome=outcome)
        try:
            self.finalize_publications()
        except (OSError, ValueError) as exc:
            self.state['persistence_error'] = str(exc)
        try:
            saved = True
            text = None
            if outcome == 'quota_stopped':
                text, saved = self.save_quota_stop(confirmed)
            elif (outcome in ('failed', 'quota_unavailable')
                  and self.state.get('requested_scientific_intent') == 'STOP'):
                # Preserve the requested rationale while explicitly reporting the
                # actual operational failure. This never authorizes STOP_ACK.
                text, saved = self.save_scientific_terminal(confirmed, update_status=False)
            elif outcome in ('complete', 'scientific_stopped'):
                proposal = self.current_proposal()
                try:
                    self.validate_reviewed_versions(proposal)
                    for task in self.state['tasks'].values():
                        last = task.get('last_context_id')
                        if not last:
                            raise workspace.InputError('Missing final context handoff: ' + task['task_id'])
                        self.validate_context_handoff(last, final=True)
                    review_ctx = self.contexts[proposal['review_context_id']]
                    if hashlib.sha256(self.scoped_text(review_ctx, proposal['review_path']).encode()).hexdigest() != proposal['review_sha256']:
                        raise workspace.InputError('Opponent review changed after submission')
                    primary_ctx = self.contexts[self.state['tasks']['primary']['last_context_id']]
                    final = proposal['final_request']
                    if hashlib.sha256(self.scoped_text(primary_ctx, final['path']).encode()).hexdigest() != final['sha256']:
                        raise workspace.InputError('Primary final request changed')
                    if any(any(not c.get('resolution') for c in r.get('publication_conflicts', ()))
                           or r.get('retirement_error')
                           for r in (*self.state['contexts'].values(), *self.state['jobs'].values(),
                                     *self.state['tasks'].values())):
                        raise workspace.InputError('Unresolved publication/retirement failure')
                    if confirmed:
                        text, saved = self.save_scientific_terminal(True)
                    else:
                        saved = False
                except (OSError, ValueError) as exc:
                    proposal['finalization_error'] = str(exc)
                    self.state.update(state='reassessment_required' if proposal.get('invalidated') else 'failed',
                                      terminal_error=str(exc))
                    saved = False
                    if outcome == 'scientific_stopped':
                        self.save_scientific_terminal(confirmed, update_status=False)
            failures = any(r.get(k) for r in (*self.state['contexts'].values(), *self.state['jobs'].values())
                           for k in ('persistence_error', 'publication_error', 'document_snapshot_error',
                                     'job_handoff_error', 'preservation_error'))
            saved = saved and not failures and not self.state.get('persistence_error')
            if not saved and outcome in ('complete', 'scientific_stopped') and self.state['state'] != 'reassessment_required':
                self.state['state'] = 'failed' if confirmed else 'cleanup_unconfirmed'
            self.state['finalization_ok'] = saved
            self.save()
            if outcome in ('quota_stopped', 'scientific_stopped', 'complete') and confirmed and saved:
                marker = 'COMPLETE' if outcome == 'complete' else 'STOP'
                self.state.update(terminal_committed=True,
                                  terminal_marker=marker, terminal_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                  scientific_status='complete' if outcome == 'complete' else self.state['scientific_status'])
                self.save()
                workspace.atomic_text(self.project / (marker + '_ACK'), text)
        except (OSError, ValueError) as exc:
            self.state['persistence_error'] = str(exc)
            self.state['finalization_ok'] = False
            self.state['terminal_committed'] = False
            if outcome in ('complete', 'scientific_stopped'):
                self.state['state'] = 'failed' if confirmed else 'cleanup_unconfirmed'
            try:
                self.save()
            except (OSError, ValueError):
                pass  # in-memory failure and terminal diagnostics remain truthful
            return False
        return confirmed and saved

    async def monitor(self):
        while True:
            if self.state['admission_block']:
                return
            pause = jobs.read(self.project / '.research_pipeline/pause.json')
            if pause and pause.get('run_id') == self.state['run_id']:
                self.schedule_shutdown('Human pause requested', 'paused')
                await self.shutdown_task
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
                        self.schedule_shutdown('Production tool inventory validation failed', 'failed')
                        await self.shutdown_task
                        return
            self.check_staleness()
            if self.warning_delivery_task is None or self.warning_delivery_task.done():
                if self.warning_delivery_task:
                    self.warning_delivery_task.result()
                self.warning_delivery_task = asyncio.create_task(self.deliver_staleness())
            await asyncio.sleep(.1)

    async def close(self):
        if self.shutdown_task:
            await self.shutdown_task
        observers = (self.monitor_task, self.job_monitor, self.quota_monitor_task, self.warning_delivery_task)
        for task in observers:
            if task:
                task.cancel()
        await asyncio.gather(*(t for t in observers if t), return_exceptions=True)
        for task in self.turns.values():
            task.cancel()
        await asyncio.gather(*self.turns.values(), return_exceptions=True)
        await asyncio.gather(*self.lifecycle_tasks, return_exceptions=True)
        self.stack.close()
