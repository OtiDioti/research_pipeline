"""One Linux execution path: a systemd user service containing Bubblewrap.

No fallback launches science outside this boundary. The service owns all descendants,
including setsid children. The PID namespace also dies with the Bubblewrap parent.
"""
from dataclasses import dataclass, field
from contextlib import nullcontext
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import time
from typing import Callable
import uuid


class RuntimeUnavailable(RuntimeError):
    pass


class RequestedStop(Exception):
    pass


@dataclass
class Config:
    codex: str = "codex"
    model: str | None = None
    wall_seconds: float = 600
    memory_mib: int = 2048
    max_tasks: int = 128
    primary_session_seconds: float = 300
    delegated_session_seconds: float = 300
    max_agents: int = 1
    task_id: str = "primary"
    task_workspaces: tuple = ()
    deadline: float = 0
    unit: str = field(default_factory=lambda: f"research-{uuid.uuid4().hex}.service")
    drafts: Path | None = None
    on_probe_launch: Callable[[str], None] | None = None
    control: Path | None = None
    response: Path | None = None
    on_poll: Callable | None = None
    launch_guard: Callable | None = None

    def limits(self):
        return {"wall_seconds": self.wall_seconds, "memory_mib": self.memory_mib, "swap_bytes": 0,
                "max_tasks": self.max_tasks,
                "per_file_bytes": 64 * 1024 * 1024, "log_bytes_per_stream": 4 * 1024 * 1024,
                "concurrent_researchers": self.max_agents}


@dataclass
class ExecutionResult:
    returncode: int
    timed_out: bool = False
    interrupted: bool = False
    cleanup_ok: bool = False
    service_properties: dict = field(default_factory=dict)
    error: str | None = None
    requested_stop: str | None = None


def _control(*args):
    return subprocess.run(["systemctl", "--user", *args], capture_output=True,
                          text=True, timeout=5, check=False)


def service_properties(unit):
    result = _control("show", unit, "--property=LoadState,ActiveState,SubState,Result,"
                      "ControlGroup,ExecMainStatus,MemoryPeak,TasksCurrent,InactiveEnterTimestampMonotonic")
    props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not props:
        raise RuntimeUnavailable("Cannot query transient service: " + result.stderr.strip())
    return props


def stop_service(unit):
    """Never report completion while a control group may still contain work."""
    try:
        props = service_properties(unit)
        cgroup = props.get("ControlGroup", "")
        if props.get("LoadState") != "not-found":
            # Stop is bounded by TimeoutStopSec; systemd sends SIGKILL to the group.
            _control("stop", unit)
        props = service_properties(unit)
        stopped = (props.get("LoadState") == "not-found"
                   or props.get("ActiveState") in ("inactive", "failed"))
        if cgroup:
            events = Path("/sys/fs/cgroup") / cgroup.lstrip("/") / "cgroup.events"
            if events.exists():
                stopped = stopped and "populated 0" in events.read_text()
        if props.get("ActiveState") == "failed":
            _control("reset-failed", unit)
        if not stopped:
            _control("kill", "--kill-whom=all", "--signal=SIGKILL", unit)
            _control("stop", unit)
            props = service_properties(unit)
            stopped = (props.get("LoadState") == "not-found"
                       or props.get("ActiveState") in ("inactive", "failed"))
            if cgroup and events.exists():
                stopped = stopped and "populated 0" in events.read_text()
        return stopped
    except (OSError, subprocess.TimeoutExpired, RuntimeUnavailable):
        # Best effort escalation; inability to confirm still prevents completion.
        try:
            _control("kill", "--kill-whom=all", "--signal=SIGKILL", unit)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return False


def bubblewrap_command(project, argv, codex=None, auth_home=None, drafts=None,
                       control=None, response=None, task_id="primary", task_workspaces=()):
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
    writable = workspace.writable_directories(task_id)
    for name in writable:
        if (project / name).exists():
            args += ["--bind", str(project / name), f"/project/{name}"]
    if task_id == "primary":
        for rel in task_workspaces:
            args += ["--ro-bind", str(project / rel), f"/project/{rel}"]
    # Protect existing notes with file mounts: unlink/rename are blocked as well
    # as writes. Never replace these inodes until the namespace has been stopped.
    for rel, digest in workspace.science_fingerprints(project, task_id).items():
        if digest not in ("symlink", "special"):
            args += ["--ro-bind", str(project / rel), f"/project/{rel}"]
    if drafts is None:
        drafts = project / ".research_pipeline/drafts"
        drafts.mkdir(exist_ok=True)
    args += ["--bind", str(drafts), "/run/research-drafts"]
    if control is not None:
        args += ["--ro-bind", str(control), "/run/research-control",
                 "--bind", str(response), "/run/research-checkpoint",
                 "--ro-bind", str(Path(__file__).with_name("checkpoint.py")),
                 "/run/research-checkpoint-helper.py"]
    args += ["--tmpfs", "/project/.research_pipeline", "--remount-ro", "/project/.research_pipeline"]
    if codex:
        # Standalone Codex distribution, including its sibling exec helper binaries.
        args += ["--ro-bind", str(Path(codex).parent), "/opt/codex"]
    if auth_home:
        args += ["--bind", str(auth_home), "/home/researcher/.codex"]
    return args + ["--chdir", f"/project/{workspace.task_directory(task_id)}", "--", *argv]


class RunningService:
    """One nonblocking transport. All callbacks run in its foreground owner."""
    def __init__(self, config, project, argv, stdin="", on_event=lambda channel, data: None,
                 auth_home=None, poll=None, launch_guard=None):
        self.config, self.on_event = config, on_event
        self.poll_callback = poll or config.on_poll
        self.process = None
        self.selector = selectors.DefaultSelector()
        self.payload = memoryview(stdin.encode())
        self.result = ExecutionResult(4)
        self.done = False
        remaining = config.deadline - time.monotonic()
        if remaining <= 0:
            self.result = ExecutionResult(124, timed_out=True, cleanup_ok=True)
            self.done = True
            return
        command = ["systemd-run", "--user", "--quiet", "--wait", "--pipe",
                   "--service-type=exec", f"--unit={config.unit}",
                   "--property=KillMode=control-group", "--property=TimeoutStopSec=2s",
                   "--property=SendSIGKILL=yes", "--property=NoNewPrivileges=yes",
                   f"--property=RuntimeMaxSec={max(0.001, remaining):.3f}s",
                   f"--property=MemoryMax={config.memory_mib}M", "--property=MemorySwapMax=0",
                   f"--property=TasksMax={config.max_tasks}", "--property=LimitFSIZE=67108864", "--",
                   *bubblewrap_command(project, argv, config.codex if auth_home else None,
                                       auth_home, config.drafts, config.control, config.response,
                                       config.task_id, config.task_workspaces)]
        guard = launch_guard or config.launch_guard
        try:
            with guard() if guard else nullcontext():
                self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE, start_new_session=True)
            for stream, channel in ((self.process.stdout, "stdout"), (self.process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, channel)
            if self.payload:
                os.set_blocking(self.process.stdin.fileno(), False)
                self.selector.register(self.process.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                self.process.stdin.close()
        except RequestedStop as exc:
            self.result.requested_stop = str(exc)
            self.done = True
        except Exception as exc:
            self.result.error = f"{type(exc).__name__}: {exc}"
            self.done = True

    def poll(self, timeout=0):
        if self.done:
            return True
        try:
            if time.monotonic() >= self.config.deadline:
                self.result.timed_out = True
                self.done = True
            elif self.poll_callback and (reason := self.poll_callback()):
                self.result.requested_stop = reason
                self.done = True
            if self.done:
                return True
            for key, _ in self.selector.select(timeout):
                stream = key.fileobj
                if key.data == "stdin":
                    try:
                        sent = os.write(stream.fileno(), self.payload[:65536])
                        self.payload = self.payload[sent:]
                    except BrokenPipeError:
                        self.payload = self.payload[:0]
                    if not self.payload:
                        self.selector.unregister(stream)
                        stream.close()
                else:
                    data = os.read(stream.fileno(), 65536)
                    if data:
                        self.on_event(key.data, data)
                    else:
                        self.selector.unregister(stream)
                        stream.close()
            # Closed output pipes alone do not mean the service has stopped.
            if not self.selector.get_map() and self.process.poll() is not None:
                self.result.returncode = self.process.returncode
                self.done = True
        except Exception as exc:
            self.result.error = f"{type(exc).__name__}: {exc}"
            self.done = True
        return self.done

    def finish(self):
        self.selector.close()
        try:
            self.result.service_properties = service_properties(self.config.unit)
            if self.result.service_properties.get("Result") == "timeout":
                self.result.timed_out = True
        except (OSError, subprocess.TimeoutExpired, RuntimeUnavailable):
            pass
        self.result.cleanup_ok = stop_service(self.config.unit)
        if self.process:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream and not stream.closed:
                    stream.close()
        if self.result.timed_out:
            self.result.returncode = 124
        if self.result.interrupted:
            self.result.returncode = 130
        if self.result.requested_stop:
            self.result.returncode = 0
        self.done = True
        return self.result


def run_isolated(config, project, argv, stdin="", on_event=lambda channel, data: None,
                 auth_home=None, poll=None, launch_guard=None):
    service = RunningService(config, project, argv, stdin, on_event, auth_home, poll, launch_guard)
    try:
        while not service.poll(.2):
            if not service.selector.get_map():
                time.sleep(min(.2, max(0, config.deadline - time.monotonic())))
    except KeyboardInterrupt:
        service.result.interrupted = True
    finally:
        result = service.finish()
    return result


PROBE = r'''
from pathlib import Path
import subprocess
p = Path('/project/starting_evidence/sentinel')
assert p.read_text() == 'protected'
for action in (lambda: p.write_text('changed'), lambda: p.unlink(),
               lambda: p.rename(p.with_name('replaced')),
               lambda: Path('/project/AGENTS.md').write_text('changed'),
               lambda: Path('/project/AGENTS.md').unlink(),
               lambda: Path('/project/AGENTS.md').rename('/project/replaced'),
               lambda: Path('/project/starting_evidence').rename('/project/stolen'),
               lambda: Path('/project/RESEARCH_STATUS.md').write_text('changed')):
    try: action()
    except OSError: pass
    else: raise AssertionError('protected write succeeded')
assert not list(Path('/project/.research_pipeline').iterdir())
assert not Path('/home/host-private-sentinel').exists()
note = Path('/project/work/protected.md')
if note.exists():
    for action in (lambda: note.write_text('changed'), lambda: note.unlink(),
                   lambda: note.rename(note.with_name('replacement.md'))):
        try: action()
        except OSError: pass
        else: raise AssertionError('canonical Markdown write succeeded')
draft = Path('/run/research-drafts/work/protected.md')
draft.parent.mkdir(parents=True, exist_ok=True)
draft.write_text('# Scientific draft')
assert draft.read_text() == '# Scientific draft'
code = Path('/project/work/compute.py')
code.write_text('from pathlib import Path\nPath("/project/outputs/value").write_text(str(sum(i*i for i in range(10))))\n')
subprocess.run(['/usr/bin/python3', str(code)], check=True)
assert Path('/project/outputs/value').read_text() == '285'
print('boundary probe passed', flush=True)
import time
time.sleep(1)  # Keep the service alive while the controller checks cgroup settings.
'''


def preflight(config, project):
    if not math.isfinite(config.wall_seconds) or config.wall_seconds <= 0:
        raise RuntimeUnavailable("Wall time must be finite and positive")
    if not os.environ.get("XDG_RUNTIME_DIR") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise RuntimeUnavailable("systemd user bus unavailable: XDG_RUNTIME_DIR and "
                                 "DBUS_SESSION_BUS_ADDRESS must already be set; "
                                 "do not connect to another execution context to bypass restrictions")
    for name in ("bwrap", "systemd-run", "systemctl"):
        if not shutil.which(name):
            raise RuntimeUnavailable(f"Required Linux runtime is missing: {name}")
    # The probe uses the production launcher and disposable protected sentinels.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="probe-", dir=project / ".research_pipeline") as tmp:
        probe = Path(tmp)
        for name in ("starting_evidence", "sources", "work", "outputs", "handoffs", ".research_pipeline"):
            (probe / name).mkdir()
        (probe / "starting_evidence/sentinel").write_text("protected")
        (probe / "AGENTS.md").write_text("protected")
        (probe / "RESEARCH_STATUS.md").write_text("protected")
        (probe / "work/protected.md").write_text("# Protected canonical note")
        probe_config = Config(wall_seconds=min(10, config.wall_seconds), memory_mib=config.memory_mib,
                              max_tasks=config.max_tasks,
                              deadline=min(config.deadline, time.monotonic() + 10))
        probe_config.launch_guard = config.launch_guard
        if config.on_poll:
            probe_config.on_poll = lambda: config.on_poll(research=False)
        diagnostics = bytearray()
        enforced = {}
        def capture(channel, data):
            if len(diagnostics) < 16384:
                diagnostics.extend(data[:16384-len(diagnostics)])
            if b"boundary probe passed" in diagnostics and not enforced:
                props = service_properties(probe_config.unit)
                group = props.get("ControlGroup", "")
                if not group:
                    raise RuntimeUnavailable("Probe service has no observable cgroup")
                path = Path("/sys/fs/cgroup") / group.lstrip("/")
                try:
                    memory = (path / "memory.max").read_text().strip()
                    swap = (path / "memory.swap.max").read_text().strip()
                    tasks = (path / "pids.max").read_text().strip()
                    if (int(memory) != config.memory_mib * 1024 * 1024
                            or swap != "0"
                            or int(tasks) != config.max_tasks):
                        raise ValueError("requested cgroup settings were not applied")
                except (OSError, ValueError) as exc:
                    raise RuntimeUnavailable(f"Cannot verify cgroup v2 resource limits: {exc}") from exc
                enforced.update(memory_max=memory, memory_swap_max=swap,
                                pids_max=tasks)
        # This host path exists but is absent in the namespace. A new file at the
        # same spelling in private /tmp cannot affect the host sentinel.
        sentinel = project / ".research_pipeline" / f"outside-{uuid.uuid4().hex}"
        sentinel.write_text("host-private")
        script = PROBE + f"\nassert not Path({str(sentinel)!r}).exists()\n"
        try:
            if config.on_probe_launch:
                config.on_probe_launch(probe_config.unit)
            result = run_isolated(probe_config, probe, ["/usr/bin/python3", "-c", script], on_event=capture)
            if sentinel.read_text() != "host-private":
                raise RuntimeUnavailable("Outside-workspace sentinel changed")
        finally:
            sentinel.unlink()
        if result.timed_out and time.monotonic() >= config.deadline:
            raise TimeoutError("Wall budget exhausted during the isolated runtime probe")
        if result.requested_stop:
            if not result.cleanup_ok:
                raise RuntimeUnavailable("Pause during preflight: cleanup could not be confirmed")
            raise RequestedStop(result.requested_stop)
        if result.returncode or not result.cleanup_ok or not enforced:
            raise RuntimeUnavailable(
                f"Isolated runtime probe failed (cleanup_ok={result.cleanup_ok}, error={result.error}): "
                + diagnostics.decode(errors="replace"))
    return {"filesystem": "Bubblewrap explicit mounts; protected inputs read-only",
            "descendants": "PID namespace and systemd KillMode=control-group",
            "resources": "systemd cgroup memory/tasks, no swap; monotonic and service wall deadline",
            "probe": "permitted computation and protected sentinel operations passed",
            "observed_cgroup_limits": enforced,
            "network": "outbound network available; no destination filtering",
            "disk": "64 MiB per file; no aggregate disk quota"}
