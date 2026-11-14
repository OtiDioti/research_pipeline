"""The terminal app: transcript, agent tree, status, a chat box to the primary and the human's controls.

Adapted from project_manager's terminal app. The transcript shows what agents
write, the tools they use, the controller's notices and your messages; F2 cycles
through single agents, F3 shows them all again.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import os

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, HSplit, Layout, VSplit, Window
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Button, Frame, Label, TextArea

from research_pipeline.controller import Controller
from research_pipeline.state import ENDED, LIVE

#: Transcript label of each kind of entry.
LABELS = {'agent': '', 'tool': '·', 'notice': '→', 'human': 'YOU', 'controller': 'CONTROLLER'}
#: Characters of transcript kept; the oldest entries are dropped first.
LIMIT = 400_000


class Highlight(Lexer):
    """Bold cyan for the controller's lines and notices, so they stand out from the agents' text."""

    def __init__(self, lines: frozenset[int]):
        self.lines = lines

    def lex_document(self, document):
        return lambda number: [('class:notice' if number in self.lines else '', document.lines[number])]


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


class TerminalApp:
    """Owns the terminal layout and runs the controller beside it; :meth:`run` returns the exit status."""

    def __init__(self, controller: Controller, input=None, output=None):
        """Build the layout around ``controller``; ``input``/``output`` are for tests."""
        self.control = controller
        controller.show = self.add
        self.entries: list[tuple[str, str, str, str]] = []  # (time, kind, agent, text)
        self.view: str | None = None          # agent shown alone; None: all agents
        self.dirty, self.follow = False, True
        self.finished = None                  # exit status once the controller has finished
        self.log = TextArea(read_only=True, scrollbar=True, wrap_lines=True, focus_on_click=True)
        self.agents = TextArea(read_only=True, wrap_lines=False, height=Dimension(min=3, max=10))
        self.chat = TextArea(height=3, multiline=True, wrap_lines=True, focus_on_click=True)
        self.pause = Button('Pause', handler=self.toggle_pause, width=12)
        self.close = Button('Shutdown & Exit', handler=self.shutdown, width=19)
        body = HSplit([
            Frame(self.log, title=lambda: 'Transcript · ' + (self.view or 'all agents')),
            Frame(self.agents, title='Agents'),
            Frame(HSplit([Label(self.status), VSplit([self.pause, self.close, Window()])]), title='Status'),
            Frame(self.chat, title='Message to the primary researcher'),
            Label('Enter send · Alt+Enter newline · F2 next agent · F3 all agents · Ctrl+P pause/resume · '
                  'Ctrl+R resume held agents · Ctrl+Q/F10 shutdown · Ctrl+C force exit'),
        ])
        keys = KeyBindings()
        keys.add('enter', filter=has_focus(self.chat))(lambda event: self.send())
        keys.add('escape', 'enter', filter=has_focus(self.chat))(lambda event: self.chat.buffer.insert_text('\n'))
        keys.add('c-p')(lambda event: self.toggle_pause())
        keys.add('c-r')(lambda event: self.control.release())
        keys.add('c-q')(lambda event: self.shutdown())
        keys.add('f10')(lambda event: self.shutdown())
        keys.add('f2')(lambda event: self.cycle())
        keys.add('f3')(lambda event: self.select(None))
        keys.add('c-c')(lambda event: self.app.exit(result=130))
        keys.add('tab')(lambda event: event.app.layout.focus_next())
        keys.add('s-tab')(lambda event: event.app.layout.focus_previous())
        keys.add('pageup')(lambda event: self.scroll(-10))
        keys.add('pagedown')(lambda event: self.scroll(10))
        keys.add('c-end')(lambda event: self.scroll(None))
        self.app = Application(layout=Layout(body, focused_element=self.chat), key_bindings=keys, full_screen=True,
                               mouse_support=True, refresh_interval=0.5, before_render=self.render,
                               style=Style.from_dict({'notice': 'bold ansicyan', 'frame.label': 'bold'}),
                               input=input, output=output)

    async def run(self) -> int:
        """Run the app and the controller together; return the exit status (130: forced exit)."""
        task = asyncio.ensure_future(self.control.run())
        task.add_done_callback(self.ended)
        try:
            result = await self.app.run_async()
        finally:
            if not task.done():
                task.cancel()  # agents restart from their handoffs next time; jobs keep running
                await asyncio.gather(task, return_exceptions=True)
        if result == 130:
            os._exit(130)
        return result

    def ended(self, task: asyncio.Task) -> None:
        """Exit after a shutdown; otherwise keep the transcript open for review until Close."""
        if task.cancelled():
            return
        error = task.exception()
        if error is None and self.control.request == 'shutdown':
            self.app.exit(result=0)
            return
        self.finished = 2 if error else 0
        self.add('controller', '', (f'Error: {error}. ' if error else '') + 'Finished; review the transcript, then press Close.')

    def add(self, kind: str, agent: str, text: str) -> None:
        """Append a transcript entry; called by the controller."""
        self.entries.append((datetime.now().strftime('%H:%M:%S'), kind, agent, text.rstrip()))
        while sum(len(entry[3]) for entry in self.entries) > LIMIT:
            self.entries.pop(0)
        self.dirty = True
        try:
            self.app.invalidate()
        except Exception:
            pass  # not running yet

    def render(self, app=None) -> None:
        """Rebuild the transcript when it changed, the agent list and the button labels."""
        if self.dirty:
            blocks, highlighted, line = [], set(), 0
            for stamp, kind, agent, text in self.entries:
                if self.view and agent != self.view:
                    continue
                block = f'[{stamp}] {agent} {LABELS[kind]}'.rstrip() + f'\n{text}'
                if kind in ('controller', 'notice', 'human'):
                    highlighted.update(range(line, line + block.count('\n') + 1))
                blocks.append(block)
                line += block.count('\n') + 2
            content = '\n\n'.join(blocks)
            self.log.lexer = Highlight(frozenset(highlighted))
            cursor = len(content) if self.follow else min(self.log.buffer.cursor_position, len(content))
            self.log.buffer.set_document(Document(content, cursor), bypass_readonly=True)
            self.dirty = False
        self.agents.buffer.set_document(Document('\n'.join(describe(self.control))), bypass_readonly=True)
        control = self.control
        waiting = control.releasable and not any(a.status in LIVE for a in control.state.agents.values())
        self.pause.text = 'Resume' if control.state.status in ('paused', 'pausing') or waiting else 'Pause'
        self.close.text = 'Close' if self.finished is not None else 'Shutdown & Exit'

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

    def send(self) -> None:
        self.control.say(self.chat.text)
        self.chat.buffer.set_document(Document(''), bypass_readonly=True)

    def toggle_pause(self) -> None:
        self.control.toggle_pause()

    def shutdown(self) -> None:
        """Close a finished app, or shut down cleanly (the app exits once agents have handed off)."""
        if self.finished is not None:
            self.app.exit(result=self.finished)
        else:
            self.add('controller', '', 'Shutting down cleanly: working agents hand off first.')
            self.control.shutdown()

    def cycle(self) -> None:
        """Show the next agent alone."""
        ids = sorted(self.control.state.agents)
        self.select(ids[(ids.index(self.view) + 1) % len(ids)] if self.view in ids else ids[0] if ids else None)

    def select(self, agent: str | None) -> None:
        self.view, self.dirty, self.follow = agent, True, True

    def scroll(self, lines: int | None) -> None:
        """Scroll the transcript by ``lines``, or follow its end again (None)."""
        self.follow = lines is None
        self.app.layout.focus(self.log)
        if lines is None:
            self.log.buffer.cursor_position = len(self.log.text)
        elif lines < 0:
            self.log.buffer.cursor_up(count=-lines)
        else:
            self.log.buffer.cursor_down(count=lines)
