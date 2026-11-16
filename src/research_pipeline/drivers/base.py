"""What every CLI driver shares: one confined, persistent CLI process speaking JSON lines.

A :class:`Session` is one agent session. The controller starts it with a
:class:`Launch` (instructions, opening message, MCP server, write scope), sends
it messages with :meth:`Session.send` — delivered live during a turn, or starting
a new turn when the agent is idle — and closes it at a handoff or at the end.

The base class owns everything that does not depend on the CLI: confinement, the
process, reading and logging JSON lines, matching replies to requests, the check
that a session loaded nothing of the human's own setup, and reporting events. A
CLI driver is one subclass, the only place where knowledge of its CLI lives. It
implements four hooks — :meth:`~Session.command`, :meth:`~Session.begin`,
:meth:`~Session.deliver` and :meth:`~Session.receive` — and, where its CLI needs
them, :meth:`~Session.environment`, :meth:`~Session.state_paths`,
:meth:`~Session.masked_paths` and :meth:`~Session.read_usage`. Adding a CLI means
writing one such subclass and registering it in
:data:`research_pipeline.drivers.DRIVERS`.

Events reach the controller as ``on_event(session, kind, data)`` with these kinds:

- ``text``: the agent wrote something (``data['text']``);
- ``tool``: the agent used a tool (``data['text']`` summarises it);
- ``context``: context use changed (``data['tokens']``, ``data['window']``, either may be None), always
  as the CLI itself reports it, never estimated;
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
from typing import Callable, Hashable, Iterable

from research_pipeline import confine
from research_pipeline.quota import Window

#: Longest JSON line accepted from a CLI, in bytes.
LINE_LIMIT = 64 * 1024 * 1024
#: Seconds to wait for the CLI's reply to a request (starting a session includes starting MCP servers).
REPLY_TIMEOUT = 120
#: Name under which every CLI attaches the controller's MCP tool server.
MCP_SERVER = 'research'


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
    instructions: str          # system/developer instructions: the role prompt and the human's AGENTS.md
    message: str               # the opening user message
    model: str                 # the CLI's model, always explicit
    effort: str                # its reasoning effort, always explicit
    mcp: McpServer
    writable: tuple[Path, ...]  # the agent's write scope (the CLI's own state paths are added)
    hidden: tuple[Path, ...]   # folders the session must not see (the controller's own state)
    log: Path                  # file receiving every JSON line, both directions


class SessionError(RuntimeError):
    """The CLI refused a request or ended unexpectedly."""


class SetupError(SessionError):
    """The CLI loaded part of the human's own setup, which project sessions must not use (PROJECT.md §3)."""


class Session:
    """One persistent agent session of one CLI, inside its confinement."""

    #: Backend name, as used in BACKEND:MODEL:EFFORT.
    backend = ''

    def __init__(self, launch: Launch, on_event: Callable[[Session, str, dict], None]):
        self.launch = launch
        self.on_event = on_event
        self.busy = False            # a turn is in progress
        self.closing = False
        self.process: asyncio.subprocess.Process | None = None
        self._tasks: list[asyncio.Task] = []
        self._stderr: deque[str] = deque(maxlen=20)
        self._replies: dict[Hashable, asyncio.Future] = {}
        self._log = None

    # CLI-specific hooks -----------------------------------------------------------------

    def command(self) -> list[str]:
        """The CLI's command line (before confinement), with its own discovery switched off."""
        raise NotImplementedError

    def environment(self) -> dict[str, str]:
        """The CLI's environment; by default the controller's own."""
        return dict(os.environ)

    def state_paths(self) -> list[Path]:
        """Folders and files the CLI itself must write (login, settings, caches)."""
        return []

    def masked_paths(self) -> list[Path]:
        """Files of the human's own CLI setup that the confinement shows as empty files."""
        return []

    async def begin(self) -> None:
        """Run the CLI's handshake, call :meth:`check_setup` with what it loaded, and send the opening message."""
        raise NotImplementedError

    async def deliver(self, text: str) -> None:
        """Deliver a user message: during the current turn if one is running, else as a new turn."""
        raise NotImplementedError

    def receive(self, message: dict) -> None:
        """Handle one JSON message from the CLI: emit events, or pass a reply to :meth:`reply`."""
        raise NotImplementedError

    @classmethod
    def read_usage(cls) -> list[Window]:
        """The CLI's usage windows, read without any model call; a CLI without a probe is not guarded."""
        return []

    # Shared transport -------------------------------------------------------------------

    async def start(self) -> None:
        """Start the confined CLI process and run :meth:`begin`."""
        argv = confine.session(self.command(), cwd=self.launch.cwd,
                               writable=[*self.launch.writable, *self.state_paths()],
                               hidden=self.launch.hidden, masked=self.masked_paths())
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

    async def exchange(self, key: Hashable, message: dict, timeout: float = REPLY_TIMEOUT) -> dict:
        """Send ``message`` and return the reply the driver passes to :meth:`reply` under ``key``.

        Raise SessionError if the CLI ends first, and asyncio.TimeoutError after ``timeout`` seconds.
        """
        future = asyncio.get_running_loop().create_future()
        self._replies[key] = future
        try:
            await self.write(message)
            return await asyncio.wait_for(future, timeout)
        finally:
            self._replies.pop(key, None)

    def reply(self, key: Hashable, message: dict) -> None:
        """Hand a reply from the CLI to the :meth:`exchange` waiting for ``key`` (if any still waits)."""
        future = self._replies.get(key)
        if future and not future.done():
            future.set_result(message)

    def check_setup(self, *, instructions: Iterable[str] = (), skills: Iterable[str] = (),
                    mcp_servers: Iterable[str] = ()) -> None:
        """Refuse a session whose CLI reports having loaded anything of the human's own setup.

        Drivers call this from :meth:`begin` with what their CLI says it loaded:
        instruction files, skills and MCP servers. The controller provides all of a
        session's instructions and its only MCP server (:data:`MCP_SERVER`), so
        anything else is personal setup (PROJECT.md §3).
        """
        personal = ([f'instruction file {path}' for path in instructions] + [f'skill {name}' for name in skills]
                    + [f'MCP server {name}' for name in mcp_servers if name != MCP_SERVER])
        if personal:
            raise SetupError(f'{self.backend} loaded the human\'s own setup ({"; ".join(personal)}); remove it '
                             'from that CLI\'s configuration, or report a driver that fails to switch it off')

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
        self._abandon_replies()
        if not self.closing:
            detail = ' | '.join(self._stderr) or 'no error output'
            self.emit('exited', reason=f'{self.backend} exited with status {code}: {detail[-600:]}')

    def _abandon_replies(self) -> None:
        """Fail every exchange still waiting: the CLI is gone and will never reply."""
        for future in self._replies.values():
            if not future.done():
                future.set_exception(SessionError(f'{self.backend} ended before replying'))

    async def _drain(self) -> None:
        """Keep the CLI's error output, so it never blocks and the last lines explain failures."""
        while line := await self.process.stderr.readline():
            text = line.decode('utf-8', errors='replace').rstrip()
            if text:
                self._stderr.append(text)
                self._record('E', text)
