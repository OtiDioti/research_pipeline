"""Durable, logical-owner jobs. The research runtime owns admission and services.

The model-side MCP process owns neither allocations nor computations. Files retain
intent and outcomes; a Unix RPC connection waits for events without model polling.
"""
import asyncio
from contextlib import ExitStack
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid

from . import isolation, workspace


class JobError(ValueError):
    pass


ACTIVE = {'reserved', 'running', 'stopping', 'cleanup_unconfirmed'}
TRUSTED_PYTHON_FLAGS = ('-P', '-s')


def atomic(path, value):
    workspace.atomic_text(path, json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n')


def read(path, max_bytes=1024 * 1024):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            import stat
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return None
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def public(record):
    return {key: value for key, value in record.items() if key != 'science_baseline'}


def status_summary(record):
    fields = ('job_id', 'task_id', 'origin_context_id', 'state', 'cleanup_ok',
              'runtime_seconds', 'deadline', 'returncode', 'launch_count', 'slot', 'reason')
    return {key: record[key] for key in fields if key in record}


def science_quiescent(state):
    """Path-based publication requires every owned writer to be confirmed stopped."""
    return all(record.get('cleanup_ok') is True
               for record in (*state['contexts'].values(), *state['jobs'].values()))


def adapter_mounts():
    spec = importlib.util.find_spec('mcp')
    if spec is None:
        raise isolation.RuntimeUnavailable('Controlled jobs require the declared mcp dependency')
    return sorted({sys.base_prefix, sys.prefix, str(Path(spec.origin).parent.parent)})


def duration(value):
    if type(value) not in (int, float) or value <= 0 or value >= (2**64 - 1) / 1_000_000 or not math.isfinite(value):
        raise JobError('runtime_seconds is required and must be positive and finite')
    # systemd times are unsigned microseconds; reject overflow, never clamp.
    if value >= (2**64 - 1) / 1_000_000 or not math.isfinite(time.monotonic() + value):
        raise JobError('runtime_seconds cannot be represented by the service supervisor')
    return value


class JobManager:
    def __init__(self, project, state, save, allocation):
        self.project, self.state, self.save, self.allocation = project, state, save, allocation
        self.lock = asyncio.Lock()
        self.events = {}
        self.mount_stacks = {}
        self.on_quiescent = None
        self.on_stopped = None
        self.root = project / '.research_pipeline/jobs'
        self.root.mkdir(exist_ok=True)

    def owned(self, task_id, job_id):
        record = self.state['jobs'].get(job_id)
        if not record or record['task_id'] != task_id:
            raise JobError('Unknown job or job belongs to another logical owner')
        return record

    def changed(self, record):
        self.save()
        event = self.events.pop(record['job_id'], None)
        if event:
            event.set()

    async def run(self, task_id, context_id, argv, cwd, runtime_seconds):
        runtime = duration(runtime_seconds)
        async with self.lock:
            if self.state['admission_block']:
                raise JobError('Admissions blocked: ' + self.state['admission_block'])
            task = self.state['tasks'][task_id]
            if task.get('operational_state', 'working') != 'working' or task.get('pending_job_inspections'):
                raise JobError('Task lifecycle/owned-job reconciliation blocks new computations')
            if task.get('context_id') != context_id or not task.get('inventory_verified'):
                raise JobError('Context attachment or production tool inventory unverified')
            if sum(r['state'] in ACTIVE for r in self.state['jobs'].values()) >= self.state['limits']['max_jobs']:
                raise JobError('Concurrent job capacity exhausted; no queue and no command launched')
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and '\0' not in a for a in argv):
                raise JobError('Expected a nonempty argv array')
            if not isinstance(cwd, str) or not cwd.startswith('/project/'):
                raise JobError('cwd must be in the logical owner workspace')
            rel = cwd.removeprefix('/project/')
            path = workspace.safe_path(self.project, rel)
            excluded = task.get('frozen_inputs', []) + (['work/tasks'] if task_id == 'primary' else [f'{task["workspace"]}/inputs', f'{task["workspace"]}/ASSIGNMENT.md'])
            if (not any(Path(rel).is_relative_to(p) for p in workspace.writable_directories(task_id))
                    or any(Path(rel).is_relative_to(p) for p in excluded) or not path.is_dir()):
                raise JobError('cwd must be an existing writable directory in the logical owner workspace')
            if len(json.dumps(argv).encode()) > 256 * 1024:
                raise JobError('Command argv exceeds 256 KiB')
            began = time.monotonic()
            if began + runtime == began:
                raise JobError('runtime_seconds is below clock precision')
            job_id = uuid.uuid4().hex
            record = {'job_id': job_id, 'task_id': task_id, 'origin_context_id': context_id,
                      'argv': argv, 'cwd': cwd, 'state': 'reserved', 'cleanup_ok': False,
                      'admitted_monotonic': began, 'admitted_epoch': time.time(),
                      'runtime_seconds': runtime, 'deadline': began + runtime,
                      'boot_id': isolation.boot_identity(), 'slot': task['slot'],
                      'unit': f'research-job-{job_id}.service', 'launch_count': 0,
                      'reason': 'Reserved before launch; launch outcome not yet established'}
            root = self.root / job_id
            root.mkdir()
            record['result_path'] = str(root / 'result.json')
            self.state['jobs'][job_id] = record
            self.changed(record)  # durable reservation before preparation or launch
            attempted = False
            try:
                self.prepare(record, task, root)
                record['launch_count'] = 1
                self.changed(record)
                args = ['/usr/bin/env', '-i', 'PATH=/usr/local/bin:/usr/bin:/bin',
                        f'PYTHONPATH={Path(__file__).parent.parent}', sys.executable, *TRUSTED_PYTHON_FLAGS,
                        '-m', 'research_pipeline.jobs', '--supervise', str(root / 'request.json')]
                launch_args = self.allocation.launch(task['slot'], record['unit'], args, deadline=record['deadline'])
                attempted = True
                await isolation.command(*launch_args)
                record['service'] = await isolation.capture_ownership(record['unit'], self.allocation.slots[task['slot']]['cgroup'])
                self.changed(record)  # ownership is saved before permitting the command
                if self.state['admission_block']:
                    cleanup = await isolation.stop_owned(record['service'])
                    record.update(state='cancelled' if cleanup['confirmed'] else 'cleanup_unconfirmed',
                                  cleanup_ok=cleanup['confirmed'], cleanup=cleanup,
                                  reason='Admissions blocked before command release; command not started')
                    if cleanup['confirmed']:
                        self.close_mounts(record)
                    self.changed(record)
                    if self.on_quiescent:
                        self.on_quiescent()
                    return public(record)
                atomic(root / 'launch.json', {'job_id': job_id})
                record.update(state='running', reason='Owned computation service running')
            except Exception as exc:
                # A failed/lost launch ack never authorizes a retry or frees capacity.
                record.update(state='cleanup_unconfirmed' if attempted else 'timed_out' if time.monotonic() >= record['deadline'] else 'failed',
                              cleanup_ok=not attempted,
                              reason=f'Admission/launch outcome uncertain: {type(exc).__name__}: {exc}' if attempted else
                                     f'Preparation failed before service launch: {type(exc).__name__}: {exc}')
                if not attempted:
                    self.close_mounts(record)
            self.changed(record)
            if self.on_quiescent:
                self.on_quiescent()
            return public(record)

    def prepare(self, record, task, root):
        tool = {'version': 1, 'activation': record['job_id'], 'task': record['task_id'],
                'job_id': record['job_id'], 'project': '/project', 'workspace': task['workspace'],
                'drafts': '/run/research-drafts', 'excluded': task.get('frozen_inputs', []) +
                (['work/tasks'] if record['task_id'] == 'primary' else [f'{task["workspace"]}/inputs', f'{task["workspace"]}/ASSIGNMENT.md']),
                'deadline': record['deadline'], 'control': '/run/no-context-control'}
        atomic(root / 'tools.json', tool)
        atomic(root / 'job.json', {**record, 'activation': record['job_id']})
        # A separate draft batch prevents a live command racing context publication.
        drafts = root / 'drafts'
        drafts.mkdir()
        mounts = self.mount_stacks[record['job_id']] = ExitStack()
        argv = isolation.bubblewrap_command(self.project, record['argv'], drafts=drafts,
                    task_id=record['task_id'], task_workspaces=tuple(self.state['tasks'][k]['workspace'] for k in self.state['tasks'] if k != 'primary'),
                    frozen_inputs=task.get('frozen_inputs', []),
                    reference_catalog=Path(task['reference_catalog']) if task.get('reference_catalog') else None,
                    reference_mounts=task.get('reference_mounts', []), tool_context=root / 'tools.json',
                    job_record=root / 'job.json', mount_stack=mounts)
        argv[argv.index('--chdir') + 1] = record['cwd']
        atomic(root / 'request.json', {'record': record, 'argv': argv})
        record['drafts'] = str(drafts)
        record['science_baseline'] = workspace.science_fingerprints(self.project, record['task_id'])

    async def reconcile(self, record):
        async with self.lock:
            return await self._reconcile(record)

    async def _reconcile(self, record):
        if record['state'] not in ACTIVE:
            return
        try:
            if record['boot_id'] != isolation.boot_identity():
                raise isolation.RuntimeUnavailable('Job boot identity changed; reconciliation required')
            if not record.get('service'):
                record['service'] = await isolation.capture_ownership(record['unit'], self.allocation.slots[record['slot']]['cgroup'])
                self.changed(record)
            owner = record['service']
            props = await isolation.service_properties(owner['unit'])
            if (props['LoadState'] != 'not-found' and props.get('InvocationID') != owner['invocation_id']
                    and not (props.get('ActiveState') in ('inactive', 'failed') and not props.get('InvocationID')
                             and not props.get('ControlGroup') and isolation.group_empty(owner['cgroup']))):
                raise isolation.RuntimeUnavailable('Job invocation identity changed')
            result = read(Path(record['result_path']))
            if result and result.get('job_id') != record['job_id']:
                raise isolation.RuntimeUnavailable('Supervisor result identity mismatch')
            ended = props['LoadState'] == 'not-found' or props.get('ActiveState') in ('inactive', 'failed')
            if result and result.get('finished') or ended:
                cleanup = await isolation.stop_owned(owner)
                updates = {k: result[k] for k in (
                    'stdout', 'stderr', 'stdout_clipped', 'stderr_clipped', 'returncode',
                    'supervisor_error', 'finished_monotonic', 'termination_cause') if result and k in result}
                finished = result.get('finished_monotonic') if result and result.get('finished') else None
                cause = result.get('termination_cause') if result else None
                if (cause == 'completed' and type(finished) in (int, float)
                        and record['admitted_monotonic'] <= finished < record['deadline']):
                    outcome = 'completed' if result.get('returncode') == 0 else 'failed'
                elif cause == 'expired' or props.get('Result') == 'timeout':
                    outcome = 'timed_out'
                elif cause == 'cancelled':
                    outcome = 'cancelled'
                else:
                    outcome = 'failed'
                record.update(**updates, state=outcome if cleanup['confirmed'] else 'cleanup_unconfirmed',
                              cleanup_ok=cleanup['confirmed'], cleanup=cleanup,
                              reason='Service timeout; partial outputs retained' if outcome == 'timed_out' else
                                     f'Supervisor failed: {result["supervisor_error"]}' if result and result.get('supervisor_error') else
                                     'Command outcome and service cleanup observed' if result and result.get('finished') else 'Supervisor lost; command outcome unavailable',
                              finished_epoch=time.time())
                if cleanup['confirmed']:
                    self.close_mounts(record)
                    self.publish(record)
                self.changed(record)
                if self.on_quiescent:
                    self.on_quiescent()
        except (OSError, ValueError, isolation.RuntimeUnavailable, asyncio.TimeoutError) as exc:
            if record.get('cleanup_ok') is True:
                record['persistence_error'] = str(exc)
                raise
            reason = f'Job supervision/cleanup unconfirmed: {exc}'
            if record['state'] != 'cleanup_unconfirmed' or record['reason'] != reason:
                record.update(state='cleanup_unconfirmed', cleanup_ok=False, reason=reason)
                self.changed(record)

    def close_mounts(self, record):
        mounts = self.mount_stacks.pop(record['job_id'], None)
        if mounts:
            mounts.close()

    def publish(self, record):
        if not record.get('drafts'):
            return
        record['publication_pending'] = True
        if record.get('cleanup_ok') is True and self.on_stopped:
            self.on_stopped(record)
        # The coordinator publishes job and context batches together, under the
        # same logical-owner human-edit and successor ordering checks.
        if self.on_quiescent:
            self.on_quiescent()

    async def inspect(self, task_id, job_id=None):
        if job_id:
            record = self.owned(task_id, job_id)
            await self.reconcile(record)
            return public(record)
        records = [r for r in self.state['jobs'].values() if r['task_id'] == task_id]
        ordered = [r for r in records if r['state'] in ACTIVE] + [r for r in reversed(records) if r['state'] not in ACTIVE]
        return {'jobs': [status_summary(r) for r in ordered[:32]],
                'jobs_total': len(records), 'jobs_omitted': max(0, len(records)-32),
                'occupied': sum(r['state'] in ACTIVE for r in self.state['jobs'].values()),
                'max_jobs': self.state['limits']['max_jobs']}

    async def wait(self, task_id, job_id):
        record = self.owned(task_id, job_id)
        while record['state'] in {'reserved', 'running', 'stopping'}:
            event = self.events.setdefault(job_id, asyncio.Event())
            await event.wait()
        return public(record)

    async def cancel(self, task_id, job_id):
        async with self.lock:
            record = self.owned(task_id, job_id)
            if record['state'] not in ACTIVE:
                return public(record)
            record.update(state='stopping', reason='Cancellation requested; termination not yet confirmed')
            try:
                self.changed(record)
            except OSError as exc:
                record['persistence_error'] = str(exc)
            cleanup = await isolation.stop_owned(record.get('service'))
            # Capture bounded partial output even when SIGKILL prevented finalization.
            result = read(Path(record['result_path'])) or {}
            for key in ('stdout', 'stderr', 'stdout_clipped', 'stderr_clipped', 'returncode',
                        'supervisor_error', 'finished_monotonic', 'termination_cause'):
                if key in result:
                    record[key] = result[key]
            record.update(state='cancelled' if cleanup['confirmed'] else 'cleanup_unconfirmed',
                          cleanup_ok=cleanup['confirmed'], cleanup=cleanup,
                          reason='Cancellation confirmed; partial outputs retained' if cleanup['confirmed'] else cleanup['reason'])
            if cleanup['confirmed']:
                self.close_mounts(record)
                self.publish(record)
            self.changed(record)
            if self.on_quiescent:
                self.on_quiescent()
            return public(record)

    async def monitor(self):
        while True:
            for record in list(self.state['jobs'].values()):
                await self.reconcile(record)
            await asyncio.sleep(.1)  # trusted service observation; no model turns


class SupervisorInterrupted(Exception):
    pass


def supervise(path):
    """Trusted service supervisor on Linux, outside the scientific PID namespace.

    systemd's independent RuntimeMaxSec and cgroup kill remain if this worker dies.
    Only bounded stdout/stderr are retained; ordinary scientific files persist.
    """
    request = read(path)
    record, argv = request['record'], request['argv']
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    clipped = {'stdout': False, 'stderr': False}
    process = None
    supervisor_error = None
    finished_monotonic = None
    termination_cause = None
    selector = selectors.DefaultSelector()
    def persist(finished=False):
        atomic(path.parent / 'result.json', {'job_id': record['job_id'], 'finished': finished,
            'returncode': process.poll() if process else None, 'supervisor_error': supervisor_error,
            'finished_monotonic': finished_monotonic, 'termination_cause': termination_cause,
            **{key: value.decode(errors='replace') for key, value in buffers.items()},
            **{key + '_clipped': value for key, value in clipped.items()}})
    def stop(signum, frame):
        raise SupervisorInterrupted('expired' if signum == signal.SIGALRM
                                    or time.monotonic() >= record['deadline'] else 'cancelled')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, max(.000001, record['deadline'] - time.monotonic()))
    try:
        persist()
        # Hold the service alive until the runtime has captured and saved its
        # invocation/cgroup. Very short commands cannot outrun ownership capture.
        while (read(path.parent / 'launch.json') or {}).get('job_id') != record['job_id']:
            time.sleep(.01)
        if time.monotonic() >= record['deadline']:
            termination_cause = 'expired'
            return
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        for key in buffers:
            stream = getattr(process, key)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, key)
        persist()
        while process.poll() is None or selector.get_map():
            for key, _ in selector.select(.05):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                space = max(0, 8192 - len(buffers[key.data]))
                buffers[key.data].extend(data[:space])
                clipped[key.data] |= len(data) > space
                persist()
        finished_monotonic = time.monotonic()
        termination_cause = 'completed' if finished_monotonic < record['deadline'] else 'expired'
        # Completion evidence must survive delayed result writes or observation.
        signal.setitimer(signal.ITIMER_REAL, 0)
    except SupervisorInterrupted as exc:
        termination_cause = str(exc)
    except OSError as exc:
        supervisor_error = f'{type(exc).__name__}: {exc}'
        termination_cause = 'supervisor_error'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
        selector.close()
        if finished_monotonic is None:
            finished_monotonic = time.monotonic()
        # Service cleanup is verified separately; this file never asserts it.
        persist(True)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--supervise':
        raise SystemExit('Private supervisor requires an owned request')
    supervise(Path(sys.argv[2]))
