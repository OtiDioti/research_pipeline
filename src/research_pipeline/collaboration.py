"""One research-owned runtime for single and multiple logical tasks.

Contexts attach to stable allocation slots. Measured rollover replaces contexts
while jobs and logical tasks survive. Scientific terminal decisions await L4.
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

from . import app_server, codex, context_usage, documents, isolation, jobs, quota, references, staleness, verification, workspace

SCHEMA_VERSION = 6


def load_state(project):
    value = jobs.read(project / '.research_pipeline/run.json', max_bytes=64 * 1024 * 1024)
    if not value or value.get('schema_version') != SCHEMA_VERSION:
        raise workspace.InputError('Unsupported operational state; V0-L3 requires a fresh schema-6 runtime. Historical science is preserved; no migration is supported.')
    if (not all(isinstance(value.get(key), dict) for key in
                ('limits', 'tasks', 'contexts', 'jobs', 'quota', 'pending_staleness'))
            or 'admission_block' not in value):
        raise workspace.InputError('Corrupt schema-6 runtime state; retain it for owned-process reconciliation')
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
                 'boot_id': isolation.boot_identity(), 'limitations': [
                     'L3 has no scientific terminal decisions or stopped-state resumption.',
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
        if action in ('check', 'tasks'):
            return {'admission_block': self.state['admission_block'], 'tasks': self.state['tasks'],
                    'account_quota': self.state['quota'],
                    'secondary_staleness': self.state['pending_staleness'] if reader == 'primary' else {},
                    'jobs': await self.jobs.inspect(reader),
                    'science_changes': ctx['record'].get('science_changes', {}),
                    **self.documents.list(reader)}
        if action == 'incorporate_edit':
            task = self.state['tasks'][reader]
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
        if action not in ('delegate', 'verify'):
            raise jobs.JobError('Unsupported legacy/terminal control; scientific opposition and terminal decisions require V0-L4')
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

    async def rollover(self, task_id, context_id):
        task = self.state['tasks'][task_id]
        record = self.contexts[context_id]['record']
        if record.get('rollover_attempted'):
            raise isolation.RuntimeUnavailable('Repeated rollover attempt refused')
        record['rollover_attempted'] = True
        task['operational_state'] = 'checkpointing'
        owned = await self.reconciled_jobs(task_id)
        checkpoint = (
            'Context reached the measured 55% threshold. Save useful science and repair the concise handoff now. '
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
            while not self.state['admission_block']:
                await self.measured_intake(context_id)
                while not self.state['admission_block']:
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
            if not self.state['admission_block'] or self.state['state'] not in ('stopping', 'paused', 'quota_stopped', 'quota_unavailable'):
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
            if attached and attached in self.contexts and not self.shutdown_task:
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
        for key, (record, drafts, original_baseline, policy, _) in batches.items():
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
        self.state.update(admission_block=self.state['admission_block'] or reason, state='stopping')
        self.quota_ready.set()
        for ctx in self.contexts.values():
            ctx['lifecycle_event'].set()
        if self.shutdown_task is None:
            self.shutdown_task = asyncio.create_task(self.block_and_cleanup(reason, outcome=outcome))

    def observe_quota(self, context_id, payload, *, full=False, provenance='native', now=None, epoch=None):
        if context_id != self.quota_transport or context_id is None:
            return None  # secondary and retired-primary notifications have no authority
        record = self.state['quota']
        sample = quota.observe(record, payload, full=full, provenance=provenance, now=now, epoch=epoch)
        if full:
            record['transport_unavailable'] = False
        if record.get('cutoff'):
            self.state.setdefault('stop_origin', 'quota')
            self.schedule_shutdown(
                f"Weekly quota STOP: observed {record['cutoff']['remaining_percent']}% remaining <= 15%", 'quota_stopped')
        elif (full or record.get('preflight_ok') and not record.get('transport_unavailable')) and not self.state['admission_block']:
            error = quota.admission_error(self.state, now=now, epoch=epoch)
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

    async def block_and_cleanup(self, reason, outcome='paused'):
        # Latch before any cleanup/checkpoint operation; failed saves cannot bypass it.
        self.state['admission_block'] = self.state['admission_block'] or reason
        self.quota_ready.set()
        async with self.cleanup_lock:
            if (self.state.get('stop_origin') == 'quota' and self.state.get('cleanup_ok')
                    and self.state.get('finalization_ok')):
                return True  # inspection/pause cannot replace an acknowledged STOP
            self.state['state'] = 'stopping'
            return await self._block_and_cleanup(reason, outcome)

    async def _block_and_cleanup(self, reason, outcome):
        if self.state.get('stop_origin') == 'quota':
            outcome = 'quota_stopped'
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
            failures = any(r.get(k) for r in (*self.state['contexts'].values(), *self.state['jobs'].values())
                           for k in ('persistence_error', 'publication_error', 'document_snapshot_error',
                                     'job_handoff_error', 'preservation_error'))
            saved = saved and not failures and not self.state.get('persistence_error')
            self.state['finalization_ok'] = saved
            self.save()
            if outcome == 'quota_stopped' and confirmed and saved:
                workspace.atomic_text(self.project / 'STOP_ACK', text)
        except (OSError, ValueError) as exc:
            self.state['persistence_error'] = str(exc)
            self.state['finalization_ok'] = False
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
        self.stack.close()
