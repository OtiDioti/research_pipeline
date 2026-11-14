"""What every CLI driver shares: one confined, persistent CLI process speaking JSON lines.

A :class:`Session` is one agent session. The controller starts it with a
:class:`Launch` (instructions, opening message, MCP server, write scope), sends
it messages with :meth:`Session.send` — delivered live during a turn, or starting
a new turn when the agent is idle — and closes it at a handoff or at the end.

The base class owns everything that does not depend on the CLI: confinement, the
process, reading and logging JSON lines, and reporting events. A CLI driver
implements four hooks: :meth:`~Session.command`, :meth:`~Session.begin`,
:meth:`~Session.deliver` and :meth:`~Session.receive`. Adding a CLI means writing
one such subclass and registering it in :data:`research_pipeline.drivers.DRIVERS`.

Events reach the controller as ``on_event(session, kind, data)`` with these kinds:

- ``text``: the agent wrote something (``data['text']``);
- ``tool``: the agent used a tool (``data['text']`` summarises it);
- ``context``: context use changed (``data['tokens']``, ``data['window']``, either may be None);
- ``turn_ended``: the agent ended its turn (``data['text']`` is its final message; ``data['failed']``
  is true if the turn failed, e.g. on an API error);
- ``exited``: the CLI process ended without being closed (``data['reason']``).
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable

from research_pipeline import confine

#: Longest JSON line accepted from a CLI, in bytes.
LINE_LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True)
class McpServer:
    """How the CLI should start our MCP tool server: its command line and environment."""
    command: list[str]
    env: dict[str, str]


@dataclass(frozen=True)
class Launch:
    """Everything a session needs to start."""
    agent: str                 # logical agent id, for messages
    cwd: Path                  # the agent's folder
    instructions: str          # system/developer instructions: the role prompt
    message: str               # the opening user message
    model: str | None          # None: the CLI's default
    effort: str | None         # None: the CLI's default
    mcp: McpServer
    writable: tuple[Path, ...]  # the agent's write scope (the CLI's own state paths are added)
    log: Path                  # file receiving every JSON line, both directions


class SessionError(RuntimeError):
    """The CLI refused a request or ended unexpectedly."""


class Session:
    """One persistent agent session of one CLI, inside its confinement."""

    #: Backend name, as used in BACKEND[:MODEL[:EFFORT]].
    backend = ''

    def __init__(self, launch: Launch, on_event: Callable[[Session, str, dict], None]):
        self.launch = launch
        self.on_event = on_event
        self.busy = False            # a turn is in progress
        self.closing = False
        self.process: asyncio.subprocess.Process | None = None
        self._tasks: list[asyncio.Task] = []
        self._stderr: deque[str] = deque(maxlen=20)
        self._log = None

    # CLI-specific hooks -----------------------------------------------------------------

    def command(self) -> list[str]:
        """The CLI's command line (before confinement)."""
        raise NotImplementedError

    def environment(self) -> dict[str, str]:
        """The CLI's environment; by default the controller's own."""
        return dict(os.environ)

    def state_paths(self) -> list[Path]:
        """Folders and files the CLI itself must write (login, settings, caches)."""
        return []

    async def begin(self) -> None:
        """Run the CLI's handshake and send the opening message."""
        raise NotImplementedError

    async def deliver(self, text: str) -> None:
        """Deliver a user message: during the current turn if one is running, else as a new turn."""
        raise NotImplementedError

    def receive(self, message: dict) -> None:
        """Handle one JSON message from the CLI, emitting events."""
        raise NotImplementedError

    def ended(self) -> None:
        """The CLI process has ended: release anything still waiting for it (optional hook)."""

    # Shared transport -------------------------------------------------------------------

    async def start(self) -> None:
        """Start the confined CLI process and send the opening message."""
        argv = confine.command(self.command(), writable=[*self.launch.writable, *self.state_paths()],
                               cwd=self.launch.cwd)
        self.launch.log.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(self.launch.log, 'a', encoding='utf-8')
        self.process = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=self.environment(), limit=LINE_LIMIT, start_new_session=True)
        self._tasks = [asyncio.create_task(self._read()), asyncio.create_task(self._drain())]
        await self.begin()

    async def send(self, text: str) -> None:
        """Send a message to the agent (see :meth:`deliver`)."""
        if self.closing or not self.process or self.process.returncode is not None:
            raise SessionError('the session has ended')
        await self.deliver(text)

    async def close(self) -> None:
        """End the session: stop the CLI and everything it started (its confinement ends with it)."""
        self.closing = True
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 10)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._log:
            self._log.close()
            self._log = None

    async def write(self, message: dict) -> None:
        """Send one JSON message to the CLI."""
        line = json.dumps(message)
        self._record('>', line)
        self.process.stdin.write(line.encode() + b'\n')
        await self.process.stdin.drain()

    def emit(self, kind: str, **data) -> None:
        self.on_event(self, kind, data)

    def _record(self, direction: str, line: str) -> None:
        if self._log:
            self._log.write(f'{direction} {line.rstrip()}\n')
            self._log.flush()

    async def _read(self) -> None:
        """Read the CLI's output until it ends; report an unexpected end."""
        while line := await self.process.stdout.readline():
            text = line.decode('utf-8', errors='replace')
            self._record('<', text)
            try:
                message = json.loads(text)
            except ValueError:
                continue  # not a protocol line (e.g. a warning printed to stdout)
            if isinstance(message, dict):
                try:
                    self.receive(message)
                except Exception as error:  # a surprising message must not stop the session
                    self._record('!', f'cannot handle message: {error!r}')
        code = await self.process.wait()
        self.busy = False
        self.ended()
        if not self.closing:
            detail = ' | '.join(self._stderr) or 'no error output'
            self.emit('exited', reason=f'{self.backend} exited with status {code}: {detail[-600:]}')

    async def _drain(self) -> None:
        """Keep the CLI's error output, so it never blocks and the last lines explain failures."""
        while line := await self.process.stderr.readline():
            text = line.decode('utf-8', errors='replace').rstrip()
            if text:
                self._stderr.append(text)
                self._record('E', text)
