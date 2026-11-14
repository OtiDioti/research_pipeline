"""Codex CLI driver: one ``codex app-server`` per session, speaking JSON-RPC over stdio.

The session is an ephemeral thread started with the role prompt as developer
instructions. Messages during a turn use ``turn/steer``; otherwise ``turn/start``.
Context use comes from ``thread/tokenUsage/updated`` notifications, which Codex
sends during the turn. Codex's own sandbox is switched off (``danger-full-access``)
because the session runs inside our confinement, and its native subagents are
disabled so that every spawn goes through the controller.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from research_pipeline.drivers.base import Session, SessionError

#: Seconds to wait for a reply to a JSON-RPC request (thread/start includes starting the MCP server).
REQUEST_TIMEOUT = 120
# Native features that would bypass the controller (subagents), wait for a human (user input) or bring
# in the user's personal setup (plugins, apps, skills), which would make investigations depend on it.
_OVERRIDES = (
    'features.multi_agent=false',
    'features.apps=false',
    'features.plugins=false',
    'features.skip_host_skill_discovery=true',
    'features.multi_agent_v2={enabled=false,disable_native_tools=true}',
    'agents.enabled=false',
    'tools.experimental_request_user_input.enabled=false',
    'web_search="live"',
)


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
        self._pending: dict[int, asyncio.Future] = {}
        self._last_message = ''

    def command(self) -> list[str]:
        mcp = self.launch.mcp
        server = (f'{{command={json.dumps(mcp.command[0])},args={json.dumps(mcp.command[1:])},'
                  f'env={_toml_table(mcp.env)},default_tools_approval_mode="approve",startup_timeout_sec=60}}')
        args = ['codex', '-c', f'mcp_servers.research={server}']
        for value in _OVERRIDES:
            args += ['-c', value]
        if self.launch.model:
            args += ['-c', f'model={json.dumps(self.launch.model)}']
        if self.launch.effort:
            args += ['-c', f'model_reasoning_effort={json.dumps(self.launch.effort)}']
        return args + ['app-server']

    def state_paths(self) -> list[Path]:
        return [Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')]

    async def begin(self) -> None:
        await self.request('initialize', {'clientInfo': {'name': 'research_pipeline', 'version': '0.1'},
                                          'capabilities': {'experimentalApi': False}})
        await self.write({'method': 'initialized'})
        result = await self.request('thread/start', {
            'cwd': str(self.launch.cwd), 'sandbox': 'danger-full-access', 'approvalPolicy': 'never',
            'ephemeral': True, 'developerInstructions': self.launch.instructions})
        self.thread = result['thread']['id']
        await self._start_turn(self.launch.message)

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
        future = asyncio.get_running_loop().create_future()
        self._pending[self._serial] = future
        await self.write({'id': self._serial, 'method': method, 'params': params})
        try:
            reply = await asyncio.wait_for(future, REQUEST_TIMEOUT)
        finally:
            self._pending.pop(self._serial, None)
        if 'error' in reply:
            raise SessionError(f'Codex refused {method}: {reply["error"].get("message", reply["error"])}')
        return reply.get('result') or {}

    def receive(self, message: dict) -> None:
        if 'id' in message and 'method' not in message:  # a reply to one of our requests
            future = self._pending.get(message['id'])
            if future and not future.done():
                future.set_result(message)
            return
        method, params = message.get('method'), message.get('params') or {}
        if 'id' in message:  # a request from Codex (e.g. an approval); none is expected without approvals
            asyncio.ensure_future(self.write({'id': message['id'], 'error': {
                'code': -32601, 'message': f'{method} is not supported by research_pipeline'}}))
            return
        if method == 'turn/started':
            self.busy, self.turn = True, params.get('turn', {}).get('id', self.turn)
        elif method == 'turn/completed':
            turn = params.get('turn') or {}
            if turn.get('id') not in (None, self.turn):
                return  # the end of an older turn
            self.busy = False
            failed = turn.get('status') == 'failed'
            if failed:
                error = (turn.get('error') or {}).get('message', 'unknown error')
                self.emit('text', text=f'[turn failed: {error}]')
            self.emit('turn_ended', text=self._last_message, failed=failed)
        elif method == 'item/completed':
            self._item(params.get('item') or {})
        elif method == 'thread/tokenUsage/updated':
            usage = params.get('tokenUsage') or {}
            self.emit('context', tokens=(usage.get('last') or {}).get('totalTokens'),
                      window=usage.get('modelContextWindow'))
        elif method == 'error':
            self.emit('text', text=f'[Codex error: {json.dumps(params)[:300]}]')

    def ended(self) -> None:
        """Fail every request still waiting for a reply: the app-server is gone."""
        for future in self._pending.values():
            if not future.done():
                future.set_exception(SessionError('Codex ended before replying'))

    def _item(self, item: dict) -> None:
        """Report one completed item: a message or a tool use."""
        kind = item.get('type')
        if kind == 'agentMessage':
            self._last_message = item.get('text', '')
            self.emit('text', text=self._last_message)
        elif kind == 'commandExecution':
            self.emit('tool', text=f'$ {item.get("command", "")}'[:300] + f'  → exit {item.get("exitCode")}')
        elif kind == 'mcpToolCall' and item.get('server') != 'research':  # the controller reports its own tools
            self.emit('tool', text=f'{item.get("tool", "tool")}({json.dumps(item.get("arguments", {}))[:200]})')
        elif kind == 'fileChange':
            paths = [change.get('path', '') for change in item.get('changes', []) if isinstance(change, dict)]
            self.emit('tool', text='edit ' + ', '.join(paths)[:300])
        elif kind == 'webSearch':
            self.emit('tool', text=f'web search: {item.get("query", "")}'[:300])
        elif kind not in (None, 'userMessage', 'reasoning', 'mcpToolCall'):
            self.emit('tool', text=str(kind))
