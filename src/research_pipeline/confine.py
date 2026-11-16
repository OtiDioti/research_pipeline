"""Confinement: every agent session and every job runs inside one bubblewrap (``bwrap``) boundary.

Two shapes share the mechanism (PROJECT.md §2):

- :func:`session`, for an agent's CLI session: the whole filesystem is visible
  read-only, and only the agent's write scope and its CLI's state folder are
  writable. ``/tmp`` is private, and the boundary ends with its parent, so
  everything a session started ends with it.
- :func:`job`, for a long computation: the filesystem is as the controller sees
  it, except for the read-only paths. A job outlives the controller that started
  it.

Both have their own process namespace. Hidden folders (the controller's
``.research/``) appear empty, and masked files (the human's personal CLI setup)
appear as empty, read-only regular files. The network stays on; the CLIs' own sandboxes are switched
off by their drivers. bwrap can only mount over paths that exist, so paths that
do not exist are skipped: there is nothing there to protect, hide or mask.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Iterable

#: The empty regular file shown in place of masked files (a device such as /dev/null is not
#: accepted by every CLI as a configuration file). It is emptied again at every use.
EMPTY = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'research-pipeline' / 'empty'


class ConfinementError(RuntimeError):
    """bubblewrap is unavailable."""


def session(argv: list[str], *, cwd: Path, writable: Iterable[Path], hidden: Iterable[Path] = (),
            masked: Iterable[Path] = ()) -> list[str]:
    """``argv`` confined as an agent session: read-only everywhere except the ``writable`` paths."""
    options = ['--ro-bind', '/', '/', '--dev', '/dev', '--tmpfs', '/dev/shm', '--tmpfs', '/tmp', '--die-with-parent']
    for path in _existing(writable):
        options += ['--bind', str(path), str(path)]
    return _wrap(argv, options, cwd=cwd, hidden=hidden, masked=masked)


def job(argv: list[str], *, cwd: Path, read_only: Iterable[Path] = (), hidden: Iterable[Path] = ()) -> list[str]:
    """``argv`` confined as a job: the filesystem as the controller sees it, except ``read_only`` and ``hidden``."""
    options = ['--dev-bind', '/', '/']  # the host's devices too (e.g. GPUs), as for any computation
    for path in _existing(read_only):
        options += ['--ro-bind', str(path), str(path)]
    return _wrap(argv, options, cwd=cwd, hidden=hidden)


def _wrap(argv: list[str], options: list[str], *, cwd: Path, hidden: Iterable[Path] = (),
          masked: Iterable[Path] = ()) -> list[str]:
    """The full bwrap command line: the shape's ``options``, then hiding and masking, then ``argv``."""
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise ConfinementError('bubblewrap (bwrap) is required: install it with your package manager.')
    options = list(options)
    for folder in _existing(hidden):
        options += ['--tmpfs', str(folder)]
    masked = _existing(masked)
    if masked:
        EMPTY.parent.mkdir(parents=True, exist_ok=True)
        EMPTY.write_bytes(b'')
    for file in masked:
        options += ['--ro-bind', str(EMPTY), str(file)]
    return [bwrap, *options, '--proc', '/proc', '--unshare-pid', '--chdir', str(cwd), '--', *argv]


def _existing(paths: Iterable[Path]) -> list[Path]:
    """The paths that exist, without duplicates, in their given order."""
    return [path for path in dict.fromkeys(Path(p) for p in paths) if path.exists()]
