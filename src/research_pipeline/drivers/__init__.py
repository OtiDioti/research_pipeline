"""CLI drivers: one persistent-session class per agent CLI, all sharing :mod:`.base`.

Each driver module is the only place that knows its CLI. Adding a CLI means
writing one :class:`~.base.Session` subclass and registering it here.
"""
from research_pipeline.drivers.base import MCP_SERVER, Launch, McpServer, Session, SessionError, SetupError
from research_pipeline.drivers.claude import ClaudeSession
from research_pipeline.drivers.codex import CodexSession

#: Session class of each backend name usable in BACKEND:MODEL:EFFORT.
DRIVERS: dict[str, type[Session]] = {'codex': CodexSession, 'claude': ClaudeSession}

__all__ = ['DRIVERS', 'MCP_SERVER', 'Launch', 'McpServer', 'Session', 'SessionError', 'SetupError', 'ClaudeSession',
           'CodexSession']
