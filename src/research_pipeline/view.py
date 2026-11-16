"""The terminal app: transcript, agent tree, status, a chat box to the primary and the human's controls.

Built on the terminal app all controllers share (:mod:`agent_sessions.console`).
The transcript shows what agents write, the tools they use, the controller's
notices and your messages; F2 cycles through single agents, F3 shows them all again.
"""
from __future__ import annotations

from prompt_toolkit.layout import Dimension
from prompt_toolkit.document import Document
from prompt_toolkit.widgets import Frame, TextArea

from agent_sessions.console import Entry, TerminalApp as SharedApp

from research_pipeline.controller import Controller
from research_pipeline.state import ENDED, LIVE

#: Transcript label of each kind of entry.
LABELS = {'agent': '', 'tool': '·', 'notice': '→', 'human': 'YOU', 'controller': 'CONTROLLER', 'alert': 'ALERT'}


def describe(controller: Controller) -> list[str]:
    """One line per agent: identity, CLI, status, context fill and latest activity."""
    lines = []
    agents = sorted(controller.state.agents.values(), key=lambda a: (a.status in ENDED, a.id != 'primary', a.id))
    for agent in agents:
        session = controller.sessions.get(agent.id)
        status = agent.status
        if status == 'running':
            status = 'working' if session and session.busy else 'idle'
        elif status == 'paused' and agent.pause_reason:
            status = f'paused ({agent.pause_reason})'
        fill = f'{agent.fill:4.0%}' if agent.fill is not None and agent.status in LIVE else '   –'
        lines.append(f'{agent.id[:22]:22} {str(agent.spec)[:24]:24} {status[:18]:18} ctx {fill}  {agent.activity[:90]}')
    return lines


class TerminalApp(SharedApp):
    """The investigation's app: every agent's transcript, the agent tree, and the human's controls."""

    HIGHLIGHTED = frozenset({'controller', 'notice', 'human', 'alert'})
    CHAT_TITLE = 'Message to the primary researcher'
    HELP = ('Enter send · Alt+Enter newline · F2 next agent · F3 all agents · Ctrl+P pause/resume · '
            'Ctrl+R resume held agents · Ctrl+Q/F10 exit (jobs keep running) · Ctrl+C force exit')
    SHUTDOWN_NOTICE = 'Shutting down cleanly: working agents hand off first; jobs keep running.'

    def __init__(self, controller: Controller, input=None, output=None):
        self.view: str | None = None  # agent shown alone; None: all agents
        self.agents = TextArea(read_only=True, wrap_lines=False, height=Dimension(min=3, max=10))
        super().__init__(controller, input=input, output=output)

    def transcript_title(self) -> str:
        return 'Transcript · ' + (self.view or 'all agents')

    def panes(self) -> list:
        return [Frame(self.agents, title='Agents')]

    def bind(self, keys) -> None:
        keys.add('c-r')(lambda event: self.control.release())
        keys.add('f2')(lambda event: self.cycle())
        keys.add('f3')(lambda event: self.select(None))

    def header(self, entry: Entry) -> str:
        return f'[{entry.time}] {entry.source} {LABELS[entry.kind]}'.rstrip()

    def visible(self, entry: Entry) -> bool:
        return self.view is None or entry.source == self.view

    def refresh(self) -> None:
        self.agents.buffer.set_document(Document('\n'.join(describe(self.control))), bypass_readonly=True)

    def held(self) -> bool:
        control = self.control
        waiting = control.releasable and not any(a.status in LIVE for a in control.state.agents.values())
        return control.state.status in ('paused', 'pausing') or waiting

    def status(self) -> str:
        control, state = self.control, self.control.state
        live = sum(agent.status in LIVE for agent in state.agents.values())
        proposal = state.proposal
        review = f' | {proposal["kind"].upper()} proposal, round {proposal["round"]}' if proposal else ''
        windows = ', '.join(map(str, control.windows)) or 'not read yet'
        options = state.options
        hint = ' | Ctrl+R resumes held agents' if control.releasable else ''
        return (f'{control.label.upper()} | {live}/{options.max_agents} agents working{review}{hint}\n'
                f'Quota: {windows} (pause at {options.short_limit:g}%, stop at {options.weekly_limit:g}% left) | '
                f'hand off at {options.threshold:.0%} context')

    def cycle(self) -> None:
        """Show the next agent alone."""
        ids = sorted(self.control.state.agents)
        self.select(ids[(ids.index(self.view) + 1) % len(ids)] if self.view in ids else ids[0] if ids else None)

    def select(self, agent: str | None) -> None:
        self.view, self.dirty, self.follow = agent, True, True
