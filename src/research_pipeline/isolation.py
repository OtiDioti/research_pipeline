"""One Linux execution path: a systemd user service containing Bubblewrap.

No fallback launches science outside this boundary. The service owns all descendants,
including setsid children. The PID namespace also dies with the Bubblewrap parent.
"""
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import time
import uuid


class RuntimeUnavailable(RuntimeError):
    pass


@dataclass
class Config:
    codex: str = "codex"
    model: str | None = None
    wall_seconds: float = 600
    memory_mib: int = 2048
    max_tasks: int = 128
    deadline: float = 0
    unit: str = field(default_factory=lambda: f"research-{uuid.uuid4().hex}.service")

    def limits(self):
        return {"wall_seconds": self.wall_seconds, "memory_mib": self.memory_mib, "swap_bytes": 0,
                "max_tasks": self.max_tasks,
                "per_file_bytes": 64 * 1024 * 1024, "log_bytes_per_stream": 4 * 1024 * 1024,
                "concurrent_researchers": 1}


@dataclass
class ExecutionResult:
    returncode: int
    timed_out: bool = False
    interrupted: bool = False
    cleanup_ok: bool = False
    service_properties: dict = field(default_factory=dict)
    error: str | None = None


def _control(*args):
    return subprocess.run(["systemctl", "--user", *args], capture_output=True,
                          text=True, timeout=5, check=False)


def service_properties(unit):
    result = _control("show", unit, "--property=LoadState,ActiveState,SubState,Result,"
                      "ControlGroup,ExecMainStatus,MemoryPeak,TasksCurrent")
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
        stopped = props.get("ActiveState") in ("inactive", "failed")
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
            stopped = props.get("ActiveState") in ("inactive", "failed")
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


def bubblewrap_command(project, argv, codex=None, auth_home=None):
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
    for name in ("sources", "work", "outputs"):
        args += ["--bind", str(project / name), f"/project/{name}"]
    args += ["--tmpfs", "/project/.research_pipeline", "--remount-ro", "/project/.research_pipeline"]
    if codex:
        # Standalone Codex distribution, including its sibling exec helper binaries.
        args += ["--ro-bind", str(Path(codex).parent), "/opt/codex"]
    if auth_home:
        args += ["--bind", str(auth_home), "/home/researcher/.codex"]
    return args + ["--chdir", "/project/work", "--", *argv]


def run_isolated(config, project, argv, stdin="", on_event=lambda channel, data: None,
                 auth_home=None):
    remaining = config.deadline - time.monotonic()
    if remaining <= 0:
        return ExecutionResult(124, timed_out=True, cleanup_ok=True)
    command = ["systemd-run", "--user", "--quiet", "--wait", "--pipe",
               "--service-type=exec", f"--unit={config.unit}",
               "--property=KillMode=control-group", "--property=TimeoutStopSec=2s",
               "--property=SendSIGKILL=yes", "--property=NoNewPrivileges=yes",
               f"--property=RuntimeMaxSec={max(0.001, remaining):.3f}s",
               f"--property=MemoryMax={config.memory_mib}M",
               "--property=MemorySwapMax=0",
               f"--property=TasksMax={config.max_tasks}",
               "--property=LimitFSIZE=67108864", "--",
               *bubblewrap_command(project, argv, config.codex if auth_home else None, auth_home)]
    process = None
    result = ExecutionResult(4)
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        payload = memoryview(stdin.encode())
        for stream, channel in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, channel)
        if payload:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        else:
            process.stdin.close()
        while selector.get_map():
            if time.monotonic() >= config.deadline:
                result.timed_out = True
                break
            for key, _ in selector.select(min(0.2, max(0, config.deadline - time.monotonic()))):
                stream = key.fileobj
                if key.data == "stdin":
                    try:
                        sent = os.write(stream.fileno(), payload[:65536])
                        payload = payload[sent:]
                    except BrokenPipeError:
                        payload = payload[:0]
                    if not payload:
                        selector.unregister(stream)
                        stream.close()
                else:
                    data = os.read(stream.fileno(), 65536)
                    if data:
                        on_event(key.data, data)
                    else:
                        selector.unregister(stream)
                        stream.close()
        if not result.timed_out:
            try:
                result.returncode = process.wait(timeout=max(0.001, config.deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                result.timed_out = True
    except KeyboardInterrupt:
        result.interrupted = True
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        selector.close()
        try:
            result.service_properties = service_properties(config.unit)
            if result.service_properties.get("Result") == "timeout":
                result.timed_out = True
        except (OSError, subprocess.TimeoutExpired, RuntimeUnavailable):
            pass
        result.cleanup_ok = stop_service(config.unit)
        if process:
            if process.poll() is None:
                # Kill only the local systemd-run client; stop_service owns the jobs.
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()
    if result.timed_out:
        result.returncode = 124
    if result.interrupted:
        result.returncode = 130
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
        for name in ("starting_evidence", "sources", "work", "outputs", ".research_pipeline"):
            (probe / name).mkdir()
        (probe / "starting_evidence/sentinel").write_text("protected")
        (probe / "AGENTS.md").write_text("protected")
        (probe / "RESEARCH_STATUS.md").write_text("protected")
        probe_config = Config(wall_seconds=min(10, config.wall_seconds), memory_mib=config.memory_mib,
                              max_tasks=config.max_tasks,
                              deadline=min(config.deadline, time.monotonic() + 10))
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
            result = run_isolated(probe_config, probe, ["/usr/bin/python3", "-c", script], on_event=capture)
            if sentinel.read_text() != "host-private":
                raise RuntimeUnavailable("Outside-workspace sentinel changed")
        finally:
            sentinel.unlink()
        if result.timed_out and time.monotonic() >= config.deadline:
            raise TimeoutError("Wall budget exhausted during the isolated runtime probe")
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
