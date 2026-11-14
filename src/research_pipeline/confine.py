"""Confinement: every agent session runs inside one bubblewrap (``bwrap``) boundary.

The whole filesystem is visible read-only. Only the agent's own write scope and
its CLI's state folder are writable. ``/tmp`` is private to the session, and the
session has its own process namespace, so everything it started ends with it.
The network stays on. One mechanism serves every CLI (PROJECT.md §2); the CLIs'
own sandboxes are switched off by their drivers.
"""
from __future__ import annotations

from pathlib import Path
import shutil


class ConfinementError(RuntimeError):
    """bubblewrap is unavailable."""


def command(argv: list[str], *, writable: list[Path], cwd: Path) -> list[str]:
    """Return ``argv`` wrapped in bwrap, with only ``writable`` paths (that exist) writable."""
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise ConfinementError('bubblewrap (bwrap) is required: install it with your package manager.')
    wrapped = [bwrap, '--ro-bind', '/', '/', '--dev', '/dev', '--tmpfs', '/dev/shm', '--proc', '/proc',
               '--tmpfs', '/tmp', '--unshare-pid', '--die-with-parent']
    for path in dict.fromkeys(Path(p) for p in writable):
        if path.exists():  # bwrap can only bind what exists; callers create files they want writable
            wrapped += ['--bind', str(path), str(path)]
    return wrapped + ['--chdir', str(cwd), '--', *argv]
