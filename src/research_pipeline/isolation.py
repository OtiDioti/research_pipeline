"""Production Linux boundary: persistent capped slices and owned transient services.

Scientific processes only launch through systemd and Bubblewrap. No PID-based
recovery, namespace-only fallback, or inferred successful cleanup.
"""
import asyncio
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import uuid


class RuntimeUnavailable(RuntimeError):
    pass


@dataclass
class Config:
    codex: str = 'codex'
    model: str | None = None
    memory_mib: int = 2048
    max_tasks: int = 128
    max_agents: int = 2
    max_jobs: int = 1
    task_id: str = 'primary'
    task_workspaces: tuple = ()
    frozen_inputs: tuple = ()
    reference_mounts: tuple = ()
    reference_catalog: Path | None = None
    tool_context: Path | None = None
    drafts: Path | None = None

    def limits(self):
        for key in ('memory_mib', 'max_tasks', 'max_agents', 'max_jobs'):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(f'{key} must be a positive integer')
        if self.max_tasks < self.max_agents or self.memory_mib < self.max_agents:
            raise ValueError('Each logical agent needs a nonempty fixed allocation')
        return {k: getattr(self, k) for k in ('memory_mib', 'max_tasks', 'max_agents', 'max_jobs')} | {'swap_bytes': 0}


def boot_identity():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


async def command(*argv, timeout=8):
    """An operational bound, never a scientific lifetime."""
    process = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise RuntimeUnavailable(f'{argv[0]} failed ({process.returncode}): {stderr.decode(errors="replace")[:2048]}')
    return stdout.decode(errors='replace')


async def service_properties(unit):
    raw = await command('systemctl', '--user', 'show', unit, '--property=LoadState,ActiveState,SubState,Result,ControlGroup,InvocationID,ExecMainStatus,MemoryMax,MemorySwapMax,TasksMax')
    props = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    if not props or 'LoadState' not in props:
        raise RuntimeUnavailable(f'No service state for {unit}')
    return props


def cgroup_path(group):
    if not group.startswith('/') or '..' in Path(group).parts:
        raise RuntimeUnavailable('Invalid cgroup path')
    return Path('/sys/fs/cgroup') / group.lstrip('/')


def group_empty(group):
    path = cgroup_path(group)
    try:
        return 'populated 0' in (path / 'cgroup.events').read_text().splitlines()
    except FileNotFoundError:
        return not path.exists()


async def capture_ownership(unit, slice_group):
    props = await service_properties(unit)
    group, invocation = props.get('ControlGroup'), props.get('InvocationID')
    if (props['LoadState'] == 'not-found' or not invocation or set(invocation) == {'0'}
            or not group or not group.startswith(slice_group + '/')
            or Path(group).name != unit):
        raise RuntimeUnavailable(f'Service ownership unavailable for {unit}')
    return {'unit': unit, 'invocation_id': invocation, 'cgroup': group, 'boot_id': boot_identity()}


async def stop_owned(owner):
    """Verify immutable identity *before* any stop, and population afterwards."""
    try:
        if not owner or owner['boot_id'] != boot_identity():
            return {'confirmed': False, 'reason': 'Missing ownership or boot identity changed'}
        props = await service_properties(owner['unit'])
        if props['LoadState'] == 'not-found':
            clean = group_empty(owner['cgroup'])
            return {'confirmed': clean, 'reason': 'Unit absent; recorded cgroup empty' if clean else 'Recorded cgroup still populated'}
        if (props.get('ActiveState') in ('inactive', 'failed') and not props.get('InvocationID')
                and not props.get('ControlGroup') and group_empty(owner['cgroup'])):
            return {'confirmed': True, 'reason': 'Inactive unit and original cgroup empty; no signal issued'}
        if props.get('InvocationID') != owner['invocation_id'] or props.get('ControlGroup') not in (owner['cgroup'], ''):
            return {'confirmed': False, 'reason': 'Unit invocation/cgroup identity mismatch; no stop issued'}
        await command('systemctl', '--user', 'stop', owner['unit'])
        props = await service_properties(owner['unit'])
        same = props['LoadState'] == 'not-found' or props.get('InvocationID') in (owner['invocation_id'], '')
        clean = same and (props['LoadState'] == 'not-found' or props.get('ActiveState') in ('inactive', 'failed')) and group_empty(owner['cgroup'])
        return {'confirmed': clean, 'reason': 'Owned service and cgroup stopped' if clean else 'Termination unconfirmed', 'properties': props}
    except (KeyError, OSError, RuntimeUnavailable, asyncio.TimeoutError) as exc:
        return {'confirmed': False, 'reason': f'Cleanup observation failed: {exc}'}


class Allocation:
    def __init__(self, run_id, limits):
        self.limits = limits
        self.parent = f'research{run_id}.slice'
        self.slots = []
        self.parent_group = None

    async def _slice(self, unit, memory, tasks):
        # StartTransientUnit creates established systemd slice units, no custom daemon.
        await command('busctl', '--user', 'call', 'org.freedesktop.systemd1',
                      '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
                      'StartTransientUnit', 'ssa(sv)a(sa(sv))', unit, 'fail', '4',
                      'MemoryMax', 't', str(memory), 'MemorySwapMax', 't', '0',
                      'TasksMax', 't', str(tasks), 'CollectMode', 's', 'inactive-or-failed', '0')
        # StartTransientUnit returns a job; verify the applied controls, not just ack.
        until = time.monotonic() + 5
        while True:
            props = await service_properties(unit)
            group = props.get('ControlGroup')
            if props.get('ActiveState') == 'active' and group:
                path = cgroup_path(group)
                actual = [(path / f).read_text().strip() for f in ('memory.max', 'memory.swap.max', 'pids.max')]
                if actual != [str(memory), '0', str(tasks)]:
                    raise RuntimeUnavailable(f'Slice limits not applied: {unit}: {actual}')
                return {'unit': unit, 'cgroup': group, 'limits': actual}
            if time.monotonic() >= until:
                raise RuntimeUnavailable(f'Slice did not become active: {unit}')
            await asyncio.sleep(.02)

    async def create(self):
        self.parent_group = await self._slice(self.parent, self.limits['memory_mib'] * 1024**2, self.limits['max_tasks'])
        count = self.limits['max_agents']
        for number in range(count):
            self.slots.append(await self._slice(f'research{self.parent.removeprefix("research").removesuffix(".slice")}-slot{number}.slice',
                              self.limits['memory_mib'] // count * 1024**2, self.limits['max_tasks'] // count))
        return {'parent': self.parent_group, 'slots': self.slots}

    def properties(self, slot, deadline=None):
        props = [f'Slice={self.slots[slot]["unit"]}', 'KillMode=control-group',
                 'TimeoutStopSec=2s', 'SendSIGKILL=yes', 'Restart=no',
                 'NoNewPrivileges=yes', 'LimitFSIZE=67108864']
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if not math.isfinite(remaining) or remaining <= 0:
                raise RuntimeUnavailable('Job expired before service launch')
            props.extend([f'RuntimeMaxSec={remaining:.6f}s', 'RemainAfterExit=yes'])
        return [f'--property={p}' for p in props]

    def launch(self, slot, unit, argv, *, deadline=None, pipe=False):
        return ['systemd-run', '--user', '--quiet', '--service-type=exec', f'--unit={unit}',
                *(['--pipe', '--wait'] if pipe else []),
                *self.properties(slot, deadline), '--', *argv]


async def control_server(callback, directory):
    """Bind through a directory fd so long project paths fit sockaddr_un.

    The actual socket remains in this private ordinary directory; the adapter
    connects via its short Bubblewrap mount. No abstract/network socket is used.
    """
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(f'/proc/self/fd/{fd}/control.sock')
        os.chmod(directory / 'control.sock', 0o600)
        sock.setblocking(False)
        return await asyncio.start_unix_server(callback, sock=sock, limit=1024 * 1024 + 1)
    except BaseException:
        sock.close()
        raise
    finally:
        os.close(fd)


class RunningService:
    """Duplex context transport; jobs are separate services in the same slot."""
    def __init__(self, allocation, slot, unit, process, ownership):
        self.allocation, self.slot, self.unit = allocation, slot, unit
        self.process, self.ownership = process, ownership

    @classmethod
    async def start(cls, allocation, slot, unit, argv):
        process = await asyncio.create_subprocess_exec(*allocation.launch(slot, unit, argv, pipe=True),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    limit=1024 * 1024 + 1)
        ownership = None
        try:
            until = time.monotonic() + 8
            while time.monotonic() < until:
                if process.returncode is not None:
                    raise RuntimeUnavailable('Context service exited before ownership capture')
                try:
                    ownership = await capture_ownership(unit, allocation.slots[slot]['cgroup'])
                    return cls(allocation, slot, unit, process, ownership)
                except RuntimeUnavailable:
                    await asyncio.sleep(.02)
            raise RuntimeUnavailable('Context service ownership not established')
        except BaseException as exc:
            if ownership:
                await stop_owned(ownership)
            if process.returncode is None:
                process.kill()
            _, stderr = await process.communicate()
            if isinstance(exc, Exception):
                raise RuntimeUnavailable(f'{exc}; startup stderr: {stderr.decode(errors="replace")[:2048]}') from exc
            raise

    async def close(self):
        result = await stop_owned(self.ownership)
        if self.process.returncode is None:
            # Only the controller's own transport child; this is not science cleanup.
            self.process.kill()
        await self.process.wait()
        return result


def preflight():
    if not os.environ.get('XDG_RUNTIME_DIR') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise RuntimeUnavailable('systemd user bus unavailable: XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS must already be set in the authorized host environment')
    for name in ('bwrap', 'systemd-run', 'systemctl', 'busctl'):
        if not shutil.which(name):
            raise RuntimeUnavailable(f'Required Linux runtime is missing: {name}')
    if not Path('/sys/fs/cgroup/cgroup.controllers').is_file():
        raise RuntimeUnavailable('cgroup v2 is required')


def bubblewrap_command(project, argv, codex=None, auth_home=None, drafts=None,
                       control=None, response=None, task_id="primary", task_workspaces=(),
                       frozen_inputs=(), reference_mounts=(), reference_catalog=None,
                       tool_context=None, job_context=None, job_record=None, mount_stack=None):
    from . import workspace
    args = ["bwrap", "--die-with-parent", "--unshare-user", "--unshare-pid",
            "--unshare-ipc", "--unshare-uts", "--cap-drop", "ALL", "--new-session",
            "--clearenv", "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
            "--setenv", "HOME", "/home/researcher", "--setenv", "CODEX_HOME", "/home/researcher/.codex",
            "--setenv", "TMPDIR", "/tmp", "--setenv", "LANG", "C.UTF-8"]
    # Explicit runtime mounts, never / or the host home. Networking is intentionally
    # available for public literature and the authenticated research backend.
    for name in ("/usr", "/bin", "/sbin", "/lib", "/lib64"):
        if Path(name).exists():
            args += ["--ro-bind", name, name]
    args += ["--dir", "/etc"]
    for name in ("/etc/ssl", "/etc/ca-certificates", "/etc/resolv.conf", "/etc/hosts",
                 "/etc/nsswitch.conf", "/etc/ld.so.cache", "/etc/alternatives"):
        if Path(name).exists():
            args += ["--ro-bind", str(Path(name).resolve()), name]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
             "--tmpfs", "/run", "--dir", "/home/researcher/.codex",
             "--ro-bind", str(project), "/project"]
    if tool_context is not None:
        args += ["--ro-bind", str(tool_context), "/run/research-tools.json",
                 "--ro-bind", str(Path(__file__).with_name("tools.py")),
                 "/run/research-tools.py"]
    if job_context is not None:
        from .jobs import adapter_mounts
        args += ["--ro-bind", str(job_context), "/run/research-jobs.json",
                 "--ro-bind", str(job_context.parent / "rpc"), "/run/research-rpc",
                 "--ro-bind", str(Path(__file__).parent.parent), "/opt/research-src"]
        for source in adapter_mounts():
            args += ["--ro-bind", source, source]
    if job_record is not None:
        args += ["--ro-bind", str(job_record), "/run/research-job.json"]
    if reference_catalog is not None:
        args += ["--tmpfs", "/references",
                 "--ro-bind", str(reference_catalog), "/run/research-references.json",
                 "--ro-bind", str(Path(__file__).with_name("references.py")),
                 "/run/research-references.py"]
        for source, destination in reference_mounts:
            args += (["--ro-bind", str(source), destination] if source is not None
                     else ["--dir", destination])
        # Empty alias directories and the mount container must also be read-only.
        args += ["--remount-ro", "/references"]
    writable = workspace.writable_directories(task_id)
    for name in writable:
        if (project / name).exists():
            args += ["--bind", str(project / name), f"/project/{name}"]
    if task_id == "primary":
        if (project / "work/tasks").is_dir():
            args += ["--ro-bind", str(project / "work/tasks"), "/project/work/tasks"]
        for rel in task_workspaces:
            args += ["--ro-bind", str(project / rel), f"/project/{rel}"]
    for rel in frozen_inputs:
        path = workspace.safe_path(project, rel)
        args += ["--ro-bind", str(path), f"/project/{rel}"]
    # Protect existing notes with file mounts: unlink/rename are blocked as well
    # as writes. Copy from safely opened files into private mount sources: a
    # separate systemd service cannot dereference the controller's /proc fd paths.
    # Retain these snapshots until confirmed service cleanup.
    snapshots = None
    for number, (rel, digest) in enumerate(workspace.science_fingerprints(project, task_id).items()):
        if digest not in ("symlink", "special"):
            source = str(project / rel)
            if mount_stack is not None:
                if snapshots is None:
                    snapshots = Path(mount_stack.enter_context(tempfile.TemporaryDirectory(
                        prefix='note-mounts-', dir=project / '.research_pipeline')))
                target = snapshots / str(number)
                with workspace.open_regular(project / rel) as stream, target.open('xb') as saved:
                    shutil.copyfileobj(stream, saved)
                target.chmod(0o400)
                source = str(target)
            args += ["--ro-bind", source, f"/project/{rel}"]
    if drafts is not None:
        args += ["--bind", str(drafts), "/run/research-drafts"]
    if control is not None:
        args += ["--ro-bind", str(control), "/run/research-control",
                 "--bind", str(response), "/run/research-checkpoint",
                 "--ro-bind", str(Path(__file__).with_name("checkpoint.py")),
                 "/run/research-checkpoint-helper.py"]
    args += ["--tmpfs", "/project/.research_pipeline", "--remount-ro", "/project/.research_pipeline"]
    if codex:
        # Standalone Codex distribution, including its sibling exec helper binaries.
        # CPU-sized Tokio pools in Codex and its exec server can exhaust a task
        # slot before V8 starts. Bound backend overhead without raising TasksMax.
        args += ["--setenv", "TOKIO_WORKER_THREADS", "1",
                 "--ro-bind", str(Path(codex).parent), "/opt/codex"]
    if auth_home:
        args += ["--bind", str(auth_home), "/home/researcher/.codex",
                 "--setenv", "CODEX_ROLLOUT_TRACE_ROOT", "/home/researcher/.codex/native-trace"]
    return args + ["--chdir", f"/project/{workspace.task_directory(task_id)}", "--", *argv]

