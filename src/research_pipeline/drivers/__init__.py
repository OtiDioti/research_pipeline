"""CLI drivers: one persistent-session class per agent CLI, all sharing :mod:`.base`.

Adding a CLI means writing one :class:`~.base.Session` subclass, registering it
here, and (optionally) adding a usage probe in :mod:`research_pipeline.quota`.
"""
from research_pipeline.drivers.base import Launch, McpServer, Session, SessionError
from research_pipeline.drivers.claude import ClaudeSession
from research_pipeline.drivers.codex import CodexSession

#: Session class of each backend name usable in BACKEND[:MODEL[:EFFORT]].
DRIVERS: dict[str, type[Session]] = {'codex': CodexSession, 'claude': ClaudeSession}

__all__ = ['DRIVERS', 'Launch', 'McpServer', 'Session', 'SessionError', 'ClaudeSession', 'CodexSession']
