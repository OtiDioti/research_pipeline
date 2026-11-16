"""Codex CLI driver: one ``codex app-server`` per session, speaking JSON-RPC over stdio.

The session is an ephemeral thread started with the session instructions as
developer instructions. Messages during a turn use ``turn/steer``; otherwise
``turn/start``. Context use comes from ``thread/tokenUsage/updated``
notifications, which Codex sends with tokens and window after every model call.

Codex's own sandbox is switched off (``danger-full-access``) because the session
runs inside our confinement. Its own discovery is off: no AGENTS.md files from
the project, the human's personal ``config.toml`` and ``AGENTS.md`` show as empty
files inside the confinement, and native subagents, plugins, apps and skills are
disabled, so that every spawn goes through the controller. Codex's ``thread/start``
reply lists the instruction files it loaded, and ``mcpServerStatus/list`` its MCP
servers: both are checked before the opening message.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from research_pipeline.drivers.base import MCP_SERVER, Session, SessionError
from research_pipeline.quota import Window, exchange

# Native features that would bypass the controller (subagents), wait for a human (user input) or bring
# in the human's own setup (project AGENTS.md files, plugins, apps, skills).
_OVERRIDES = (
    'features.multi_agent=false',
    'features.apps=false',
    'features.plugins=false',
    'features.skip_host_skill_discovery=true',
    'features.multi_agent_v2={enabled=false,disable_native_tools=true}',
    'agents.enabled=false',
    'tools.experimental_request_user_input.enabled=false',
    'project_doc_max_bytes=0',
    'web_search="live"',
)
# Files of the human's own setup in Codex's home folder (masked in project sessions).
_PERSONAL_FILES = ('config.toml', 'AGENTS.md', 'AGENTS.override.md')


def _home() -> Path:
    """Codex's home folder: its login, settings and caches."""
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')


def _toml_table(values: dict[str, str]) -> str:
    """An inline TOML table of strings (JSON string escapes are valid TOML basic strings)."""
    return '{' + ','.join(f'{key}={json.dumps(value)}' for key, value in values.items()) + '}'


class CodexSession(Session):
    """A Codex app-server session."""

    backend = 'codex'

    def __init__(self, launch, on_event):
        super().__init__(launch, on_event)
        self.thread: str | None = None
        self.turn: str | None = None
        self._serial = 0
        self._last_message = ''

    def command(self) -> list[str]:
        mcp = self.launch.mcp
        server = (f'{{command={json.dumps(mcp.command[0])},args={json.dumps(mcp.command[1:])},'
                  f'env={_toml_table(mcp.env)},default_tools_approval_mode="approve",startup_timeout_sec=60}}')
        args = ['codex', '-c', f'mcp_servers.{MCP_SERVER}={server}']
        for value in (*_OVERRIDES, f'model={json.dumps(self.launch.model)}',
                      f'model_reasoning_effort={json.dumps(self.launch.effort)}'):
            args += ['-c', value]
        return args + ['app-server']

    def state_paths(self) -> list[Path]:
        return [_home()]

    def masked_paths(self) -> list[Path]:
        return [_home() / name for name in _PERSONAL_FILES]

    async def begin(self) -> None:
        await self.request('initialize', {'clientInfo': {'name': 'research_pipeline', 'version': '0.1'},
                                          'capabilities': {'experimentalApi': False}})
        await self.write({'method': 'initialized'})
        thread = await self.request('thread/start', {
            'cwd': str(self.launch.cwd), 'sandbox': 'danger-full-access', 'approvalPolicy': 'never',
            'ephemeral': True, 'developerInstructions': self.launch.instructions})
        self.thread = thread['thread']['id']
        self.check_setup(instructions=thread.get('instructionSources') or [],
                         mcp_servers=await self._mcp_servers())
        await self._start_turn(self.launch.message)

    async def _mcp_servers(self) -> list[str]:
        """Names of the MCP servers this Codex session has (a paginated listing)."""
        names, cursor = [], None
        while True:
            page = await self.request('mcpServerStatus/list', {'cursor': cursor} if cursor else {})
            names += [server.get('name', '') for server in page.get('data') or []]
            cursor = page.get('nextCursor')
            if not cursor:
                return names

    async def deliver(self, text: str) -> None:
        if self.busy and self.turn:
            try:
                await self.request('turn/steer', {'threadId': self.thread, 'expectedTurnId': self.turn,
                                                  'input': [{'type': 'text', 'text': text}]})
                return
            except SessionError:
                pass  # the turn ended meanwhile: start a new one
        await self._start_turn(text)

    async def _start_turn(self, text: str) -> None:
        self.busy = True
        result = await self.request('turn/start', {'threadId': self.thread,
                                                   'input': [{'type': 'text', 'text': text}]})
        self.turn = result.get('turn', {}).get('id', self.turn)

    async def request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and return its result; raise SessionError on an error reply."""
        self._serial += 1
        reply = await self.exchange(self._serial, {'id': self._serial, 'method': method, 'params': params})
        if 'error' in reply:
            raise SessionError(f'Codex refused {method}: {reply["error"].get("message", reply["error"])}')
        return reply.get('result') or {}

    def receive(self, message: dict) -> None:
        if 'id' in message and 'method' not in message:  # a reply to one of our requests
            self.reply(message['id'], message)
            return
        method, params = message.get('method'), message.get('params') or {}
        if 'id' in message:  # a request from Codex (e.g. an approval); none is expected without approvals
            asyncio.ensure_future(self.write({'id': message['id'], 'error': {
                'code': -32601, 'message': f'{method} is not supported by research_pipeline'}}))
            return
        if method == 'turn/started':
            self.busy, self.turn = True, params.get('turn', {}).get('id', self.turn)
        elif method == 'turn/completed':
            self._turn_completed(params.get('turn') or {})
        elif method == 'item/completed':
            self._item(params.get('item') or {})
        elif method == 'thread/tokenUsage/updated':
            usage = params.get('tokenUsage') or {}
            self.emit('context', tokens=(usage.get('last') or {}).get('totalTokens'),
                      window=usage.get('modelContextWindow'))
        elif method == 'error':
            self.emit('text', text=f'[Codex error: {json.dumps(params)[:300]}]')

    def _turn_completed(self, turn: dict) -> None:
        """The end of the current turn (the end of an older, replaced turn is ignored)."""
        if turn.get('id') not in (None, self.turn):
            return
        self.busy = False
        failed = turn.get('status') == 'failed'
        if failed:
            self.emit('text', text=f'[turn failed: {(turn.get("error") or {}).get("message", "unknown error")}]')
        self.emit('turn_ended', text=self._last_message, failed=failed)

    def _item(self, item: dict) -> None:
        """Report one completed item: a message or a tool use."""
        kind = item.get('type')
        if kind == 'agentMessage':
            self._last_message = item.get('text', '')
            self.emit('text', text=self._last_message)
        elif kind == 'commandExecution':
            self.emit('tool', text=f'$ {item.get("command", "")}'[:300] + f'  → exit {item.get("exitCode")}')
        elif kind == 'mcpToolCall' and item.get('server') != MCP_SERVER:  # the controller reports its own tools
            self.emit('tool', text=f'{item.get("tool", "tool")}({json.dumps(item.get("arguments", {}))[:200]})')
        elif kind == 'fileChange':
            paths = [change.get('path', '') for change in item.get('changes', []) if isinstance(change, dict)]
            self.emit('tool', text='edit ' + ', '.join(paths)[:300])
        elif kind == 'webSearch':
            self.emit('tool', text=f'web search: {item.get("query", "")}'[:300])
        elif kind not in (None, 'userMessage', 'reasoning', 'mcpToolCall'):
            self.emit('tool', text=str(kind))

    @classmethod
    def read_usage(cls) -> list[Window]:
        """Codex's usage windows, through a short-lived app-server (``account/rateLimits/read``, no model call)."""
        reply = exchange(['codex', 'app-server'], [
            ({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'research_pipeline', 'version': '0'}}},
             lambda message: message.get('id') == 1),
            ({'method': 'initialized'}, None),
            ({'id': 2, 'method': 'account/rateLimits/read'}, lambda message: message.get('id') == 2)])
        if 'result' not in reply:
            raise OSError('Codex refused the usage read')
        buckets = (reply['result'].get('rateLimitsByLimitId') or {}).values()
        return [Window(cls.backend, window['windowDurationMins'], float(window['usedPercent']), window.get('resetsAt'))
                for bucket in buckets for window in (bucket.get('primary'), bucket.get('secondary'))
                if isinstance(window, dict) and window.get('windowDurationMins')]
