"""Claude Code driver: one ``claude -p`` process per session, speaking stream-json both ways.

The session instructions are appended to Claude Code's system prompt. Every
message is a stream-json user message: written during a turn, Claude Code takes
it into that turn at its next step; written while idle, it starts a new turn.

Before the opening message, two control requests (answered without a model call)
report what the session holds: ``get_context_usage`` gives the context window,
the starting fill, the instruction files and the skills it loaded, and
``mcp_status`` names its MCP servers. During every turn, the usage of each
top-level model call gives the tokens, and each turn's result repeats the window.

Claude Code's own sandbox is off (the session runs inside our confinement), and
permissions are bypassed for the same reason. Its own discovery is off: no
settings files, CLAUDE.md, skills or MCP servers of the human's, and no subagent
or background-task features, so that all work goes through the controller.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path

from research_pipeline.drivers.base import MCP_SERVER, Session, SessionError
from research_pipeline.quota import WEEK_MINUTES, Window, exchange

#: Built-in tools offered to agents; the controller's tools come through MCP. (Without the Skill tool,
#: no skills are loaded.)
TOOLS = 'Bash,Read,Edit,Write,Glob,Grep,NotebookEdit,WebSearch,WebFetch,TodoWrite'
# Usage fields that together are a call's prompt plus its output.
_CONTEXT_FIELDS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
# Quiet, self-contained sessions: no background tasks, memory, CLAUDE.md discovery or self-updates.
_QUIET = {'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS': '1', 'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1',
          'CLAUDE_CODE_DISABLE_CLAUDE_MDS': '1', 'CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING': '1',
          'DISABLE_AUTOUPDATER': '1'}
# A print-mode process speaking stream-json both ways, keeping nothing after it ends.
_STREAM = ['claude', '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
           '--no-session-persistence']


def clean_environment() -> dict[str, str]:
    """The controller's environment without an enclosing Claude Code session's variables."""
    return {key: value for key, value in os.environ.items()
            if not (key.startswith('CLAUDE') and key != 'CLAUDE_CONFIG_DIR')} | _QUIET


class ClaudeSession(Session):
    """A Claude Code print-mode session with stream-json input and output."""

    backend = 'claude'

    def __init__(self, launch, on_event):
        super().__init__(launch, on_event)
        self.model_name: str | None = None
        self.window: int | None = None
        self.tokens: int | None = None
        self._serial = 0

    def command(self) -> list[str]:
        mcp = self.launch.mcp
        servers = {'mcpServers': {MCP_SERVER: {'type': 'stdio', 'command': mcp.command[0], 'args': mcp.command[1:],
                                               'env': mcp.env}}}
        settings = {'disableAllHooks': True, 'sandbox': {'enabled': False}}
        return [*_STREAM, '--append-system-prompt', self.launch.instructions,
                '--setting-sources', '', '--settings', json.dumps(settings),
                '--strict-mcp-config', '--mcp-config', json.dumps(servers),
                '--tools', TOOLS, '--disallowed-tools', 'Task,Agent', '--permission-mode', 'bypassPermissions',
                '--model', self.launch.model, '--effort', self.launch.effort]

    def environment(self) -> dict[str, str]:
        return clean_environment()

    def state_paths(self) -> list[Path]:
        configured = os.environ.get('CLAUDE_CONFIG_DIR')
        home = Path.home()
        return [Path(configured)] if configured else [home / '.claude', home / '.claude.json', home / '.cache' / 'claude']

    async def begin(self) -> None:
        usage = await self.control('get_context_usage', detail='full')
        servers = await self.control('mcp_status')
        self.window = usage['maxTokens']
        self.tokens = usage.get('totalTokens')
        self.emit('context', tokens=self.tokens, window=self.window)
        skills = (usage.get('skills') or {}).get('skillFrontmatter') or []
        self.check_setup(instructions=[file['path'] for file in usage.get('memoryFiles') or []],
                         skills=[skill['name'] for skill in skills if skill.get('source') != 'built-in'],
                         mcp_servers=[server['name'] for server in servers.get('mcpServers') or []])
        await self.deliver(self.launch.message)

    async def control(self, subtype: str, **fields) -> dict:
        """Send a control request and return its response; raise SessionError if Claude Code refuses it."""
        self._serial += 1
        key = f'control-{self._serial}'
        reply = await self.exchange(key, {'type': 'control_request', 'request_id': key,
                                          'request': {'subtype': subtype, **fields}})
        response = reply.get('response') or {}
        if response.get('subtype') != 'success':
            raise SessionError(f'Claude Code refused {subtype}: {response.get("error", response)}')
        return response.get('response') or {}

    async def deliver(self, text: str) -> None:
        self.busy = True
        await self.write({'type': 'user', 'message': {'role': 'user', 'content': text}})

    def receive(self, message: dict) -> None:
        kind = message.get('type')
        if kind == 'control_response':
            self.reply((message.get('response') or {}).get('request_id'), message)
        elif kind == 'system' and message.get('subtype') == 'init':
            self.model_name = message.get('model')
        elif kind == 'assistant' and message.get('parent_tool_use_id') is None:
            self._assistant(message.get('message') or {})
        elif kind == 'result':
            self._result(message)

    def _assistant(self, body: dict) -> None:
        """One top-level model call: its context use, its text and the tools it used."""
        usage = body.get('usage')
        if isinstance(usage, dict):
            self.tokens = sum(value for key in _CONTEXT_FIELDS if isinstance(value := usage.get(key), int))
            self.emit('context', tokens=self.tokens, window=self.window)
        for block in body.get('content') or []:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'text' and block.get('text', '').strip():
                self.emit('text', text=block['text'])
            elif block.get('type') == 'tool_use' and not block.get('name', '').startswith(f'mcp__{MCP_SERVER}__'):
                self.emit('tool', text=f'{block.get("name")}({json.dumps(block.get("input", {}))[:200]})')

    def _result(self, message: dict) -> None:
        """The end of a turn: the context window it reports, and whether it failed."""
        self.busy = False
        models = message.get('modelUsage') if isinstance(message.get('modelUsage'), dict) else {}
        entry = models.get(self.model_name) or (next(iter(models.values())) if len(models) == 1 else None)
        if isinstance(entry, dict) and isinstance(entry.get('contextWindow'), int):
            self.window = entry['contextWindow']
            self.emit('context', tokens=self.tokens, window=self.window)
        failed = bool(message.get('is_error'))
        if failed:
            self.emit('text', text=f'[turn failed: {str(message.get("result") or message.get("subtype"))[:300]}]')
        self.emit('turn_ended', text=str(message.get('result') or ''), failed=failed)

    @classmethod
    def read_usage(cls) -> list[Window]:
        """Claude Code's five-hour and weekly windows, from a ``get_usage`` control request (no model call)."""
        reply = exchange(_STREAM, [({'type': 'control_request', 'request_id': 'usage',
                                     'request': {'subtype': 'get_usage'}},
                                    lambda message: message.get('type') == 'control_response')],
                         env=clean_environment())
        usage = reply.get('response', {}).get('response') or {}
        limits = usage.get('rate_limits') if usage.get('rate_limits_available') else None
        windows = []
        for name, value in (limits or {}).items():
            if (isinstance(value, dict) and isinstance(value.get('utilization'), (int, float))
                    and name.startswith(('five_hour', 'seven_day'))):
                resets = value.get('resets_at')
                windows.append(Window(cls.backend, 300 if name.startswith('five_hour') else WEEK_MINUTES,
                                      float(value['utilization']),
                                      datetime.fromisoformat(resets).timestamp() if resets else None))
        return windows
