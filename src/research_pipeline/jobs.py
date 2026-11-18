"""Long computations run by the controller for agents (PROJECT.md §6, "Jobs").

A job runs in its own confinement (:func:`agent_toolkit.confine.job`): the
filesystem as the controller sees it, except that the protected paths are
read-only and the hidden ones invisible. It is its own process session, outside
every agent's session, so it survives the agent's handoffs, quota pauses and a
shutdown of the controller. Its timeout is enforced by coreutils ``timeout``
inside the job itself, so it holds even while the controller is down. A small
wrapper writes the exit status to a file, so a restarted controller can tell how
a job ended.

Each job keeps its files in ``agents/<owner>/jobs/<job-id>/``: ``command.txt``,
``stdout.log``, ``stderr.log`` and ``exit_code``.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path

from agent_toolkit import confine
from agent_toolkit.records import atomic_write, create

from research_pipeline.state import Job

#: Exit status of ``timeout`` when it stopped the command (124) or had to kill it (137).
TIMEOUT_CODES = (124, 137)
# Runs the command under `timeout`, then records its exit status even after a controller crash.
_WRAPPER = 'timeout --kill-after=10 "$1" bash -c "$2"; echo $? > "$3"'


def folder(project_root: Path, job: Job) -> Path:
    return Path(project_root) / "agents" / job.owner / "jobs" / job.id


def start(
    project_root: Path, job: Job, *, read_only: Iterable[Path] = (), hidden: Iterable[Path] = ()
) -> subprocess.Popen:
    """Launch ``job`` in its confinement; record its process identity on it and return the process.

    The recorded process is the confinement's own (bwrap), the leader of the job's
    process session: it lives exactly as long as the job and exits with its status.
    """
    where = folder(project_root, job)
    # The job's folder is in its owner's folder, which the owner can write: the controller's own files there
    # are never written through a symlink, nor outside the project.
    atomic_write(
        where / "command.txt", f"# cwd: {job.cwd}\n# timeout: {job.timeout:g} s\n{job.command}\n", root=project_root
    )
    argv = confine.job(
        ["bash", "-c", _WRAPPER, "research-job", f"{job.timeout:g}", job.command, str(where / "exit_code")],
        cwd=Path(job.cwd),
        read_only=read_only,
        hidden=hidden,
    )
    with (
        create(where / "stdout.log", root=project_root) as stdout,
        create(where / "stderr.log", root=project_root) as stderr,
    ):
        process = subprocess.Popen(
            argv, cwd=job.cwd, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True
        )
    job.pid, job.ticks = process.pid, _ticks(process.pid)
    return process


def poll(project_root: Path, job: Job, process: subprocess.Popen | None) -> bool:
    """Update a running ``job`` from its process or files; return True if it has just ended."""
    if job.status != "running":
        return False
    if process is not None:
        if process.poll() is None:
            return False
    elif _alive(job.pid, job.ticks):
        return False
    exit_file = folder(project_root, job) / "exit_code"
    try:
        code = int(exit_file.read_text().strip())
    except (OSError, ValueError):
        code = None
    job.exit_code, job.ended = code, time.time()
    if code is None:
        job.status = "lost"  # ended without its wrapper finishing (e.g. killed from outside)
    elif code in TIMEOUT_CODES and job.ended >= job.deadline - 1:
        job.status = "timeout"
    else:
        job.status = "finished" if code == 0 else "failed"
    return True


def cancel(job: Job, status: str = "cancelled") -> None:
    """Stop every process of ``job``'s session and mark it ``status``."""
    if job.status == "running" and job.pid:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            members = _session_members(job.pid, job.ticks)
            for pid in members:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, sig)
            if not members:
                break
            deadline = time.time() + 5
            while sig == signal.SIGTERM and time.time() < deadline and _session_members(job.pid, job.ticks):
                time.sleep(0.1)
    job.status, job.ended = status, time.time()


def write_index(project_root: Path, owner: str, jobs: list[Job]) -> None:
    """Maintain ``agents/<owner>/jobs/FOLDER_CONTENT.md``: one line per job of that agent."""
    folder = Path(project_root) / "agents" / owner / "jobs"
    if not folder.is_dir():
        return
    lines = ["# Folder contents", "", "Jobs run by the controller for this agent (maintained by the controller).", ""]
    for job in sorted(jobs, key=lambda job: int(job.id.rsplit("-", 1)[-1])):
        if job.owner == owner:
            first = job.command.strip().splitlines()[0][:100] if job.command.strip() else ""
            lines.append(f"- [{job.id}]({job.id}) — {job.status}: `{first}`")
    atomic_write(folder / "FOLDER_CONTENT.md", "\n".join(lines) + "\n", root=project_root)


def describe(project_root: Path, job: Job, lines: int = 30) -> str:
    """A job's status and the end of its output, for the job_status tool and notices."""
    where = folder(project_root, job)
    elapsed = (job.ended or time.time()) - job.started
    parts = [
        f"Job {job.id}: {job.status}"
        + (f" (exit {job.exit_code})" if job.exit_code is not None else "")
        + f" after {elapsed:.0f} s of {job.timeout:g} s; files in {where}"
    ]
    for name in ("stdout.log", "stderr.log"):
        try:
            tail = (where / name).read_text(errors="replace").splitlines()[-lines:]
        except OSError:
            tail = []
        if tail:
            parts.append(f"--- last lines of {name} ---\n" + "\n".join(tail)[-4000:])
    return "\n".join(parts)


# Process identity -----------------------------------------------------------------


def _stat(pid: int) -> list[str] | None:
    """Fields of /proc/<pid>/stat after the command name (index 0 is the state), or None."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    return text[text.rindex(")") + 2 :].split()


def _ticks(pid: int) -> int | None:
    fields = _stat(pid)
    return int(fields[19]) if fields else None


def _alive(pid: int | None, ticks: int | None) -> bool:
    """True if the recorded session leader still runs (and is the same process, not a reused PID)."""
    fields = _stat(pid) if pid else None
    return bool(fields) and fields[0] != "Z" and (ticks is None or int(fields[19]) == ticks)


def _session_members(leader: int, ticks: int | None) -> list[int]:
    """All live processes in the job's session; nothing if the leader is gone and the session reused."""
    members = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            fields = _stat(int(entry.name))
            if fields and fields[0] != "Z" and int(fields[3]) == leader:
                members.append(int(entry.name))
    if leader in members and not _alive(leader, ticks):
        return []  # the PID was reused by an unrelated session
    return members
