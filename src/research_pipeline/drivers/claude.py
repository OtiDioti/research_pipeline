"""Claude Code driver: one ``claude -p`` process per session, speaking stream-json both ways.

The role prompt is appended to Claude Code's system prompt. Every message is a
stream-json user message: written during a turn, Claude Code takes it into that
turn at its next step; written while idle, it starts a new turn. Context use comes
from the usage of each top-level model call; the context window from each turn's
result. Claude Code's own sandbox is off (the session runs inside our
confinement), permissions are bypassed for the same reason, and its subagent and
background-task features are disabled so that work goes through the controller.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from research_pipeline.drivers.base import Session

#: Built-in tools offered to agents; the controller's tools come through MCP.
TOOLS = 'Bash,Read,Edit,Write,Glob,Grep,NotebookEdit,WebSearch,WebFetch,TodoWrite'
# Usage fields that together are a call's prompt plus its output.
_CONTEXT_FIELDS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
# Quiet, self-contained sessions: no background tasks, memory, CLAUDE.md discovery or self-updates.
_QUIET = {'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS': '1', 'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1',
          'CLAUDE_CODE_DISABLE_CLAUDE_MDS': '1', 'CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING': '1',
          'DISABLE_AUTOUPDATER': '1'}


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

    def command(self) -> list[str]:
        mcp = self.launch.mcp
        servers = {'mcpServers': {'research': {'type': 'stdio', 'command': mcp.command[0], 'args': mcp.command[1:],
                                               'env': mcp.env}}}
        settings = {'disableAllHooks': True, 'sandbox': {'enabled': False}}
        args = ['claude', '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
                '--no-session-persistence', '--append-system-prompt', self.launch.instructions,
                '--setting-sources', '', '--settings', json.dumps(settings),
                '--strict-mcp-config', '--mcp-config', json.dumps(servers),
                '--tools', TOOLS, '--disallowed-tools', 'Task,Agent', '--permission-mode', 'bypassPermissions']
        if self.launch.model:
            args += ['--model', self.launch.model]
        if self.launch.effort:
            args += ['--effort', self.launch.effort]
        return args

    def environment(self) -> dict[str, str]:
        return clean_environment()

    def state_paths(self) -> list[Path]:
        home = Path.home()
        configured = os.environ.get('CLAUDE_CONFIG_DIR')
        return [Path(configured)] if configured else [home / '.claude', home / '.claude.json', home / '.cache' / 'claude']

    async def begin(self) -> None:
        await self.deliver(self.launch.message)

    async def deliver(self, text: str) -> None:
        self.busy = True
        await self.write({'type': 'user', 'message': {'role': 'user', 'content': text}})

    def receive(self, message: dict) -> None:
        kind = message.get('type')
        if kind == 'system' and message.get('subtype') == 'init':
            self.model_name = message.get('model')
        elif kind == 'assistant' and message.get('parent_tool_use_id') is None:
            body = message.get('message') or {}
            usage = body.get('usage')
            if isinstance(usage, dict):
                self.tokens = sum(value for key in _CONTEXT_FIELDS if isinstance(value := usage.get(key), int))
                self.emit('context', tokens=self.tokens, window=self.window)
            for block in body.get('content') or []:
                if not isinstance(block, dict):
                    continue
                if block.get('type') == 'text' and block.get('text', '').strip():
                    self.emit('text', text=block['text'])
                elif block.get('type') == 'tool_use' and not block.get('name', '').startswith('mcp__research__'):
                    self.emit('tool', text=f'{block.get("name")}({json.dumps(block.get("input", {}))[:200]})')
        elif kind == 'result':
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
