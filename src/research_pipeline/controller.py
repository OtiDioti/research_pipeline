"""The controller: a deterministic program that runs one investigation (PROJECT.md §3–§7).

It owns the agent tree and makes every operational decision; it never makes a
scientific one. In outline:

- **Sessions.** Each running agent has one persistent CLI session (a driver from
  the shared package :mod:`agent_toolkit`) inside its confinement. Messages reach agents
  live, during their turn; queued messages are delivered when a session starts.
- **Tools.** Agents act through the MCP tools of :mod:`research_pipeline.mcp_server`,
  which arrive here through :mod:`research_pipeline.channel` and are handled by
  the ``_tool_*`` methods.
- **Handoffs.** At the context threshold an agent is asked to update HANDOFF.md and
  end its turn; its session is then replaced by a fresh one. The request is
  repeated every further 25 points of context; an agent is never killed for it.
  The rules are those every agent controller shares (:mod:`agent_toolkit.handoff`).
- **Idle and stalled agents.** An agent that ends its turn with nothing running or
  pending for it is nudged once; if it ends its turn idle again without using a
  tool, it has stalled: its parent is told, or the human alerted for the primary,
  or the proposal under review is withdrawn for the Reviewer.
- **Finishing.** The primary proposes COMPLETE or STOP, and its session closes; the
  Reviewer examines the proposal; COMPLETE needs its agreement, STOP is the
  primary's decision after the Reviewer's challenge. The verdict wakes the primary.
- **Quota, pause, shutdown, crash.** Per-CLI usage limits pause that CLI's agents
  (or all, if it is the primary's); the holds come from the shared usage guard
  (:class:`agent_toolkit.quota.Guard`). A human pause hands every agent off and stops
  jobs; a shutdown hands every agent off and leaves jobs running. After a shutdown
  or a crash, agents restart from their handoffs and running jobs are reattached.

All state changes happen on one asyncio loop, serialised by one lock: driver
events, tool calls and the background loops never interleave halfway.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from typing import Callable

from agent_toolkit import CAPABILITIES, DRIVERS, Launch, McpServer, Session, SessionError, SetupError, Spec, quota
from agent_toolkit.handoff import HandoffWatch
from agent_toolkit.quota import Guard
from agent_toolkit.records import Busy, atomic_write, exclusive

from research_pipeline import jobs as joblib
from research_pipeline import prompts
from research_pipeline.channel import serve
from research_pipeline.project import EMPTY_INDEX, INDEX, Project, ProjectError
from research_pipeline.state import ENDED, FINISHED, LIVE, Agent, Job, Options, State

#: Seconds between usage-quota reads.
QUOTA_INTERVAL = 120
#: Seconds between checks of jobs, retries and the human's files.
WATCH_INTERVAL = 2
#: Seconds between checks of the human's files.
HUMAN_INTERVAL = 10
#: Delays before restarting an agent whose session failed; after these, the human must resume it.
RETRY_DELAYS = (30, 120, 600)
#: Seconds a session may continue its turn after submitting, before it is closed anyway.
CLOSE_GRACE = 120
#: Name under which every agent's CLI attaches the controller's MCP tool server.
MCP_SERVER = 'research'
#: Tools each role may call (mirrors research_pipeline.mcp_server.ROLE_TOOLS).
_COMMON = {'spawn', 'agents', 'message', 'accept', 'reject', 'cancel', 'run_job', 'job_status', 'job_cancel'}
ROLE_TOOLS = {'primary': _COMMON | {'complete', 'stop'}, 'subagent': _COMMON | {'submit_result'},
              'reviewer': _COMMON | {'verdict'}}

#: Transcript callback: ``show(kind, agent_id, text)`` with kind 'agent', 'tool', 'notice', 'human', 'controller'
#: or 'alert' (something the human must act on).
Show = Callable[[str, str, str], None]


class ToolError(Exception):
    """A tool call the controller refuses; its message is returned to the agent."""


class Controller:
    """Runs one investigation in one project folder until it ends or the human shuts it down."""

    def __init__(self, root: Path, options: Options | None = None, *, drivers=DRIVERS,
                 read_quota: Callable[[str], list[quota.Window]] | None = None, show: Show | None = None):
        """``options`` override the stored launch options (None: keep them; a first run needs them).

        ``drivers`` and ``read_quota`` (backend name -> usage windows; by default read
        by that backend's driver) can be replaced in tests.
        """
        self.project = Project(root)
        self.launch_options = options
        self.drivers = drivers
        # The limits and the holds come from the state once it is loaded (see _load).
        self.guard = Guard(0, 0, read_quota or (lambda backend: quota.read(self.drivers[backend])))
        self.show: Show = show or (lambda kind, agent, text: None)
        self.state: State = State()
        self.sessions: dict[str, Session] = {}
        self.watches: dict[str, HandoffWatch] = {}  # agent id -> the handoff rules of its current session
        self.tokens: dict[str, str] = {}             # agent id -> token of its current session
        self.processes: dict[str, subprocess.Popen] = {}  # job id -> process started by this controller
        self.channel = f'research-pipeline-{secrets.token_hex(8)}'
        self.request: str | None = None              # 'shutdown' once the human asked to exit
        self.lock: asyncio.Lock | None = None
        self.done: asyncio.Event | None = None
        self._human_checked = 0.0
        self._quota_due = 0.0
        self._strays: set[str] = set()              # unexpected top-level entries already reported

    # Running ------------------------------------------------------------------------------

    async def run(self) -> int:
        """Run until the investigation ends or the human shuts down; return an exit status."""
        self.lock, self.done = asyncio.Lock(), asyncio.Event()
        self.project.research.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            try:  # held for as long as this controller runs (see research_pipeline.cli.controller_running)
                stack.enter_context(exclusive(self.project.lock_file, 'Another controller is already running this project.'))
            except Busy as busy:
                raise ProjectError(str(busy)) from None
            self.project.prepare()
            self.state = self._load()
            server = await serve(self.channel, self._tool_request)
            loops = [asyncio.create_task(self._watch_loop()), asyncio.create_task(self._quota_loop())]
            try:
                async with self.lock:
                    await self._begin()
                await self.done.wait()
            finally:
                for task in loops:
                    task.cancel()
                await asyncio.gather(*loops, return_exceptions=True)
                for agent_id in list(self.sessions):  # after a forced exit, agents restart from handoffs next time
                    await self._close(agent_id)
                server.close()
                self._save()
        return 0

    @property
    def windows(self) -> list[quota.Window]:
        """The latest usage readings, for the terminal app."""
        return self.guard.windows

    @property
    def label(self) -> str:
        """One-word state of the investigation, with any quota holds."""
        holds = ', '.join(f'{backend} {hold["kind"]}' for backend, hold in self.state.holds.items())
        return self.state.status + (f' (held: {holds})' if holds else '')

    def say(self, text: str) -> None:
        """The human's chat message, for the primary (from the terminal app)."""
        if text.strip():
            asyncio.ensure_future(self._locked(self._say(text)))

    def toggle_pause(self) -> None:
        """Pause a running investigation, or resume a paused one (from the terminal app)."""
        asyncio.ensure_future(self._locked(self._toggle()))

    def shutdown(self) -> None:
        """Hand every agent off cleanly, then stop the controller; jobs keep running (from the terminal app)."""
        self.request = 'shutdown'
        asyncio.ensure_future(self._locked(self._shutdown()))

    def release(self) -> None:
        """Resume what only the human may resume while the investigation runs (from the terminal app).

        That is: CLIs held by a weekly or unreadable quota, and agents whose automatic
        retries are exhausted. Unlike the pause toggle, this never stops jobs.
        """
        asyncio.ensure_future(self._locked(self._release()))

    @property
    def releasable(self) -> bool:
        """True if something waits for the human's :meth:`release`."""
        return self.state.status == 'running' and (
            any(hold['kind'] != 'short' for hold in self.state.holds.values())
            or any(a.status == 'paused' and a.pause_reason == 'failure' and a.retry_at is None
                   for a in self.state.agents.values()))

    async def _locked(self, coroutine) -> None:
        """Run ``coroutine`` under the lock; report (never propagate) an unexpected error."""
        async with self.lock:
            try:
                await coroutine
            except Exception as error:
                self.show('controller', '', f'Internal error (the investigation continues): {error!r}')

    def _load(self) -> State:
        """Load the stored state, or create it on a first run; apply new launch options."""
        if self.project.state_file.exists():
            state = State.load(self.project.state_file)
            if self.launch_options:
                state.options = self.launch_options
        else:
            state = State(options=self.launch_options or Options())
        options = state.options
        unknown = set(options.backends) - set(self.drivers)
        try:
            primary = Spec.parse(options.primary, '--primary', self.drivers)
            reviewer = Spec.parse(options.reviewer, '--reviewer', self.drivers)
        except ValueError as error:
            raise ProjectError(str(error)) from None
        if not options.backends:
            raise ProjectError('--backends must name at least one CLI for subagents')
        if unknown:
            raise ProjectError(f'Unknown backend(s): {", ".join(sorted(unknown))}; known: {", ".join(self.drivers)}')
        if options.max_agents < 2:
            raise ProjectError('--max-agents must be at least 2: the primary and the Reviewer.')
        for agent_id, spec in (('primary', primary), ('reviewer', reviewer)):
            agent = state.agents.setdefault(agent_id, Agent(agent_id, agent_id, None, spec.backend, spec.model,
                                                            spec.effort,
                                                            status='paused' if agent_id == 'primary' else 'resting',
                                                            pause_reason='start'))
            agent.backend, agent.model, agent.effort = spec.backend, spec.model, spec.effort
        self.guard.short_limit, self.guard.weekly_limit = options.short_limit, options.weekly_limit
        self.guard.holds = state.holds  # the guard keeps its holds in the stored state
        return state

    async def _begin(self) -> None:
        """Start, resume or reopen the investigation."""
        state = self.state
        clean = state.status in ('paused', 'pausing') or state.status in FINISHED
        for agent in state.agents.values():  # sessions of a previous controller ended with it
            if agent.status in LIVE:
                agent.status, agent.pause_reason = 'paused', 'restart'
            agent.closing = False
            agent.handoff_reason = agent.closing_since = None
        changed = self.project.uncommitted()
        if not state.agents['primary'].sessions:  # the first run
            self._commit('controller: investigation started')
        elif state.status in FINISHED:
            outcome = state.status.upper()
            self._commit('human: changes before reopening')
            state.status, state.proposal = 'running', None
            primary = state.agents['primary']
            primary.status, primary.pause_reason = 'paused', 'reopen'
            primary.notices.append(prompts.reopened(outcome, changed))
            self.show('controller', 'primary', f'Reopened after {outcome}.')
        elif clean and changed:
            self._commit('controller: changes made while paused or shut down (by the human or by running jobs)')
            self._announce_changes(changed)
        elif changed:
            self._commit('controller: work recovered after a restart')
        state.status = 'running'
        state.human = state.human or self.project.human_fingerprint()
        state.holds.clear()  # running again is the human's resume: holds are re-read now
        await self._check_quota()
        await self._resume_agents()
        self._save()

    # Sessions -----------------------------------------------------------------------------

    def _live(self) -> list[Agent]:
        return [agent for agent in self.state.agents.values() if agent.status in LIVE]

    def _scope(self, agent: Agent) -> tuple[Path, ...]:
        """What the agent's confinement leaves writable (PROJECT.md §2)."""
        root = self.project.root
        scope = [self.project.agent_dir(agent.id), root / 'sources', root / 'tools']
        if agent.role == 'primary':
            scope.append(root / INDEX)
            if not self._under_review():  # talk-only during a review (PROJECT.md §4)
                scope += [root / 'STATUS.md', root / 'REPORT.md']
        elif agent.role == 'reviewer':
            scope.append(self.project.reviews)
        return tuple(scope)

    async def _start_session(self, agent: Agent) -> None:
        """Start a fresh session for ``agent``, opening with its task, handoff and pending notices."""
        await self._close(agent.id)  # e.g. a rejected subagent whose last turn is still closing
        folder = self.project.agent_dir(agent.id)
        folder.mkdir(parents=True, exist_ok=True)
        if not (folder / INDEX).exists():
            first = '- [TASK.md](TASK.md) — The task from my parent.\n' if (folder / 'TASK.md').exists() else ''
            atomic_write(folder / INDEX, EMPTY_INDEX + first, root=self.project.root)
        agent.sessions += 1
        agent.started = time.time()
        notices, agent.notices = agent.notices, []
        token = secrets.token_hex(16)
        launch = Launch(
            agent=agent.id, cwd=folder, instructions=prompts.instructions(agent, self.project, self.state.options),
            message=prompts.opening(agent, self.project, self.state.options, notices),
            model=agent.model, effort=agent.effort, tools=CAPABILITIES,
            mcp={MCP_SERVER: McpServer([sys.executable, '-m', 'research_pipeline.mcp_server'],
                                       {'RP_CHANNEL': self.channel, 'RP_AGENT': agent.id, 'RP_TOKEN': token,
                                        'RP_ROLE': agent.role})},
            writable=self._scope(agent), hidden=(self.project.research,),
            log=self.project.logs / f'{agent.id}-{agent.sessions}.jsonl')
        session = self.drivers[agent.backend](launch, self._on_event)
        agent.status, agent.pause_reason, agent.retry_at, agent.closing = 'running', None, None, False
        agent.handoff_reason = agent.closing_since = None
        # A new session's context use is unknown until its CLI reports it.
        agent.nudged, agent.tokens, agent.window = False, None, None
        # Its handoff rules: a context handoff is called off if the CLI compacts below the threshold.
        self.watches[agent.id] = HandoffWatch(self.state.options.threshold, folder / 'HANDOFF.md',
                                              cancel_on_recovery=True)
        self.sessions[agent.id], self.tokens[agent.id] = session, token
        try:
            await session.start()
        except Exception as error:
            self.sessions.pop(agent.id, None)
            self.tokens.pop(agent.id, None)
            agent.notices = notices + agent.notices
            await session.close()
            # Personal setup would load again on every retry: only the human can fix it.
            await self._failed(agent, f'{agent.id}: its session could not start: {error}.',
                               retry=not isinstance(error, SetupError))
            return
        self.show('controller', agent.id, f'Session {agent.sessions} started ({agent.spec}).')
        self._save()

    async def _close(self, agent_id: str) -> None:
        """Close an agent's session, if it has one."""
        self.tokens.pop(agent_id, None)
        self.watches.pop(agent_id, None)
        session = self.sessions.pop(agent_id, None)
        if session:
            await session.close()

    async def _failed(self, agent: Agent, reason: str, retry: bool = True) -> None:
        """An agent's session ended unexpectedly: pause it and schedule a restart from its handoff.

        Without ``retry`` (or once the automatic retries are used up) it waits for the human's Ctrl+R.
        """
        reason_paused = {'pause': 'human', 'shutdown': 'human', 'quota': 'quota'}.get(agent.handoff_reason)
        agent.status, agent.pause_reason = 'paused', reason_paused or 'failure'
        agent.handoff_reason = None
        if agent.pause_reason == 'failure':
            agent.failures += 1
            if not retry:
                agent.retry_at = None
                self.show('controller', agent.id, f'{reason} Fix this, then press Ctrl+R to retry.')
            elif agent.failures <= len(RETRY_DELAYS):
                delay = RETRY_DELAYS[agent.failures - 1]
                agent.retry_at = time.time() + delay
                self.show('controller', agent.id, f'{reason} Restarting from its handoff in {delay} s.')
            else:
                agent.retry_at = None
                self.show('controller', agent.id, f'{reason} It failed {agent.failures} times: press Ctrl+R to retry.')
        await self._pause_progress()
        self._save()

    async def _resume_agents(self, reasons: set[str] | None = None) -> None:
        """Start paused agents (only those paused for ``reasons``, if given) that may run now."""
        state = self.state
        if state.status != 'running':
            return
        order = {'primary': 0, 'reviewer': 1, 'subagent': 2}
        for agent in sorted(state.agents.values(), key=lambda a: (order[a.role], a.sessions)):
            if agent.status != 'paused' or (reasons and agent.pause_reason not in reasons):
                continue
            pending = self._under_review()
            if agent.role == 'reviewer' and not pending:
                agent.status = 'resting'
                continue
            if self._blocked(agent.backend):
                agent.pause_reason = 'quota'
                continue
            if len(self._live()) >= state.options.max_agents:
                agent.pause_reason = 'slots'
                continue
            if pending and agent.role == 'reviewer' and not any('Review round' in n for n in agent.notices):
                agent.notices.append(prompts.review_request(state.proposal['kind'], state.proposal['round'],
                                                            state.proposal['detail']))
            if pending and agent.role == 'primary':
                agent.notices.append(prompts.talk_only(state.proposal['round']))
            resumed_from_quota = agent.pause_reason == 'quota'
            await self._start_session(agent)
            parent = state.agents.get(agent.parent or '')
            if resumed_from_quota and agent.status == 'running' and parent and parent.status not in ENDED:
                await self._notify(parent, f'[controller] Subagent {agent.id} has resumed after its quota pause.')

    # Driver events --------------------------------------------------------------------------

    def _on_event(self, session: Session, kind: str, data: dict) -> None:
        """Driver callback: queue the event for handling under the lock, in arrival order."""
        asyncio.ensure_future(self._locked(self._event(session, kind, data)))

    async def _event(self, session: Session, kind: str, data: dict) -> None:
        agent_id = session.launch.agent
        if self.sessions.get(agent_id) is not session:
            return  # from a session that has already been replaced or closed
        agent = self.state.agents[agent_id]
        if kind == 'text':
            agent.activity = data['text'].strip().splitlines()[0][:200] if data['text'].strip() else agent.activity
            self.show('agent', agent_id, data['text'])
        elif kind == 'tool':
            agent.activity, agent.nudged = data['text'][:200], False
            if data.get('server') != MCP_SERVER:  # the controller's own tools are shown when it handles them
                self.show('tool', agent_id, data['text'])
        elif kind == 'context':
            await self._context(agent, data.get('tokens'), data.get('window'))
        elif kind == 'turn_ended' and data.get('failed') and not agent.closing:
            # A failed turn (e.g. an API outage) restarts the agent from its handoff after a delay.
            await self._close(agent_id)
            await self._failed(agent, f'{agent_id}: its turn failed.')
        elif kind == 'turn_ended':
            await self._turn_ended(agent, data.get('text') or '')
            self._save()
        elif kind == 'exited':
            self.sessions.pop(agent_id, None)
            self.tokens.pop(agent_id, None)
            await session.close()
            if agent.closing:
                agent.closing = False
                self._save()
            else:
                await self._failed(agent, f'{agent_id}: {data.get("reason", "its session ended")}.')
        await self._after_change()

    async def _context(self, agent: Agent, tokens: int | None, window: int | None) -> None:
        """New context reading: trigger the handoff at the threshold and repeat it every further 25 points.

        Context use is only what the session's CLI reports. Until it has reported both tokens and
        window, the fill is unknown and triggers nothing; it is never estimated.
        """
        watch = self.watches.get(agent.id)
        if watch is None:
            return
        action = watch.reading(tokens, window)
        agent.tokens, agent.window = watch.tokens, watch.window
        if agent.closing:
            return
        if action == 'request' and agent.status == 'running':
            await self._request_handoff(agent, 'context', f'{watch.fill:.0%}')
        elif action == 'recovered' and agent.status == 'handing_off':
            agent.status, agent.handoff_reason = 'running', None  # compacted below the threshold: the cycle restarts
        elif action == 'remind' and agent.status == 'handing_off':
            await self._send(agent, prompts.handoff_reminder(f'{watch.fill:.0%}'))

    async def _turn_ended(self, agent: Agent, text: str) -> None:
        """An agent ended its turn (``text`` is its final message)."""
        agent.failures = 0
        watch = self.watches.get(agent.id)
        if watch is not None and watch.unmeasured():
            # Without readings no handoff can be triggered: the agent continues, and the human is told once.
            self.show('alert', agent.id, f'{agent.id}: its CLI has not reported context use after a full turn, '
                                         'so its handoffs cannot be triggered in this session.')
        if agent.closing:  # it submitted a result, a verdict or a proposal: its session ends with this turn
            agent.closing = False
            await self._close(agent.id)
            return
        if agent.status == 'handing_off':
            await self._check_handoff(agent)
        elif agent.notices:
            await self._flush(agent)
        elif self.state.status == 'running' and self._idle(agent):
            if agent.nudged:  # told it was idle, and it ended its turn idle again without using a tool
                await self._stalled(agent, text)
            else:
                agent.nudged = True
                await self._send(agent, prompts.nudge(agent.role, self._awaiting(agent)))

    def _idle(self, agent: Agent) -> bool:
        """True unless the agent is waiting: for a running or paused subagent, a running job or a review."""
        busy_children = [c for c in self.state.children(agent.id) if c.status in LIVE or c.status == 'paused']
        waiting = agent.role == 'primary' and self._under_review()
        return not busy_children and not self.state.running_jobs(agent.id) and not waiting

    def _awaiting(self, agent: Agent) -> list[str]:
        """The agent's subagents whose submitted results await its decision."""
        return [child.id for child in self.state.children(agent.id) if child.status == 'submitted']

    async def _stalled(self, agent: Agent, text: str) -> None:
        """An idle agent stopped working (PROJECT.md §3, "Waiting, idle and stalled agents")."""
        last = text.strip() or '(no final message)'
        if agent.role == 'subagent':  # it keeps its session; its parent decides
            self.show('controller', agent.id, 'Stalled: its parent is told.')
            await self._notify(self.state.agents[agent.parent], prompts.stalled(agent.id, last))
        elif agent.role == 'primary':  # it keeps its session; the human's reply continues it
            self.show('alert', 'primary', f'The primary has stopped and is waiting for you. Its last message:\n{last}')
        else:  # the Reviewer: without a verdict, the proposal under review is withdrawn
            proposal, self.state.proposal = self.state.proposal, None
            agent.status = 'resting'
            await self._close(agent.id)
            if proposal and not proposal.get('reviewed'):
                self._commit(f'reviewer: stalled in round {proposal["round"]}; proposal withdrawn')
                self.show('controller', 'reviewer', f'Stalled without a verdict: round {proposal["round"]} is withdrawn.')
                await self._review_ended(prompts.review_withdrawn(proposal['kind'], proposal['round']))

    # Messages ---------------------------------------------------------------------------------

    async def _send(self, agent: Agent, text: str) -> None:
        """Deliver ``text`` to the agent's live session now, or keep it for its next session."""
        session = self.sessions.get(agent.id)
        if session is None:
            agent.notices.append(text)
            return
        try:
            await session.send(text)
        except (SessionError, OSError, asyncio.TimeoutError):
            agent.notices.append(text)
            return
        self.show('notice', agent.id, text)

    async def _notify(self, agent: Agent, text: str) -> None:
        """Queue a notice; deliver it at once if the agent is working (not while it hands off)."""
        agent.notices.append(text)
        if agent.status == 'running' and not agent.closing:
            await self._flush(agent)

    async def _flush_running(self, agent: Agent) -> None:
        if agent.status == 'running' and not agent.closing:
            await self._flush(agent)

    async def _flush(self, agent: Agent) -> None:
        if agent.notices and agent.id in self.sessions:
            pending, agent.notices = agent.notices, []
            await self._send(agent, '\n\n'.join(pending))

    async def _wake(self, agent: Agent, notice: str) -> None:
        """Deliver ``notice``; an agent resting without a session (the primary in review, the Reviewer) restarts."""
        if agent.status == 'resting':
            agent.notices.append(notice)
            agent.status, agent.pause_reason = 'paused', 'wake'
            await self._resume_agents({'wake'})
        else:
            await self._notify(agent, notice)

    async def _review_ended(self, notice: str) -> None:
        """Bring the primary back after a review with ``notice`` (a verdict, or the withdrawn proposal).

        A primary the human woke during the review has a talk-only session; it is
        replaced, so that the fresh session has its full write scope again.
        """
        primary = self.state.agents['primary']
        if primary.status in LIVE:
            await self._close(primary.id)
            primary.status, primary.closing = 'resting', False
        await self._wake(primary, notice)

    async def _say(self, text: str) -> None:
        """The human's message reaches the primary, waking it if it rests during a review (talk-only)."""
        self.show('human', 'primary', text)
        await self._wake(self.state.agents['primary'], prompts.human_message(text))
        self._save()

    def _announce_changes(self, paths: list[str]) -> None:
        """Tell the primary, and the owners of changed agent folders, what changed while paused or shut down."""
        notice = prompts.resumed(paths)
        owners = {path.split('/')[1] for path in paths if path.startswith('agents/') and path.count('/') >= 2}
        for agent_id in {'primary', *owners} & set(self.state.agents):
            self.state.agents[agent_id].notices.append(notice)
        self.show('controller', 'primary', 'Changed while paused (by the human or by running jobs):\n'
                  + '\n'.join(paths[:20]))

    # Handoffs ---------------------------------------------------------------------------------

    async def _request_handoff(self, agent: Agent, reason: str, detail: str = '') -> None:
        """Ask a working agent to update HANDOFF.md and end its turn."""
        watch = self.watches.get(agent.id)
        if agent.status == 'handing_off':
            if reason != 'context':  # a pause or a quota hold decides what follows the handoff
                agent.handoff_reason = reason
                if watch is not None:
                    watch.request(reason)
            return
        if agent.status != 'running' or agent.closing or watch is None:
            return
        watch.request(reason)
        agent.status, agent.handoff_reason = 'handing_off', reason
        self.show('controller', agent.id, f'Handoff requested ({reason}).')
        await self._send(agent, prompts.handoff_request(reason, detail))

    async def _check_handoff(self, agent: Agent) -> None:
        """At a turn's end during a handoff: replace or pause the session once HANDOFF.md is updated."""
        watch = self.watches.get(agent.id)
        saved = watch is not None and watch.saved()
        if not saved and watch is not None and watch.ask_again():
            await self._send(agent, prompts.HANDOFF_MISSING)
            return
        if not saved:  # it stopped working without updating it: its successor starts from the last one
            self.show('controller', agent.id, 'HANDOFF.md was not updated; continuing from the existing one.')
        problems = self.project.check_layout(agent)
        if problems:
            agent.notices.append(_layout_notice(problems))
        reason = agent.handoff_reason
        self._commit(f'{agent.id}: handoff ({reason})')
        await self._close(agent.id)
        agent.handoff_reason = None
        if reason == 'context' and self.state.status == 'running' and not self._blocked(agent.backend):
            await self._start_session(agent)
        else:
            agent.status = 'paused'
            agent.pause_reason = 'quota' if reason == 'quota' or self._blocked(agent.backend) else 'human'
            self.show('controller', agent.id, f'Paused ({agent.pause_reason}).')
            parent = self.state.agents.get(agent.parent or '')
            if agent.pause_reason == 'quota' and parent and parent.status not in ENDED:
                await self._notify(parent, prompts.quota_paused(agent.id, agent.backend))
            await self._pause_progress()

    # Tools ----------------------------------------------------------------------------------

    async def _tool_request(self, request: dict) -> str:
        """Handle one tool call from an agent's MCP server (see :mod:`research_pipeline.channel`)."""
        async with self.lock:
            agent_id, tool = request.get('agent'), request.get('tool')
            if not agent_id or self.tokens.get(agent_id) != request.get('token'):
                return 'Error: this session has ended; its tools no longer work.'
            caller = self.state.agents[agent_id]
            if caller.status not in LIVE or caller.closing:
                return 'Error: your session is closing; end your turn now.'
            if tool not in ROLE_TOOLS[caller.role]:
                return f'Error: {tool} is not available to the {caller.role}.'
            self.show('tool', agent_id, f'{tool}({_brief(request.get("args") or {})})')
            try:
                reply = await getattr(self, f'_tool_{tool}')(caller, **(request.get('args') or {}))
            except ToolError as refusal:
                reply = f'Refused: {refusal}'
            except TypeError as error:
                reply = f'Error: invalid arguments for {tool}: {error}'
            caller.nudged = False
            if caller.notices and caller.status == 'running' and caller.id in self.sessions:
                reply += '\n\n' + '\n\n'.join(caller.notices)  # pending notices ride along with any reply
                caller.notices = []
            await self._after_change()
            self._save()
            return reply

    def _path(self, caller: Agent, path: str, *bases: Path, folder: bool = False) -> Path:
        """Resolve a path an agent gave: absolute, or relative to the first of ``bases`` where it exists.

        ``bases`` default to the agent's folder. The result must be an existing file (or folder,
        if ``folder``) inside the project, and outside ``.research/``, which agents cannot see.
        """
        if not str(path).strip():
            raise ToolError('a path is required')
        given = Path(str(path)).expanduser()
        candidates = [given] if given.is_absolute() else [base / given for base in
                                                          bases or (self.project.agent_dir(caller.id),)]
        for candidate in candidates:
            resolved = candidate.resolve()
            visible = self.project.inside(resolved) and not resolved.is_relative_to(self.project.research)
            if visible and (resolved.is_dir() if folder else resolved.is_file()):
                return resolved
        raise ToolError(f'{path} is not an existing {"folder" if folder else "file"} in the project')

    def _child(self, caller: Agent, agent_id: str) -> Agent:
        child = self.state.agents.get(agent_id)
        if child is None or child.parent != caller.id:
            raise ToolError(f'{agent_id} is not one of your subagents; yours: '
                            + (', '.join(c.id for c in self.state.children(caller.id)) or 'none'))
        return child

    def _settled(self, caller: Agent) -> None:
        """Refuse to finish while the caller's subagents or jobs still run or await its decision."""
        open_children = [c.id for c in self.state.children(caller.id) if c.status not in ENDED]
        running = [job.id for job in self.state.running_jobs(caller.id)]
        if open_children or running:
            raise ToolError('first settle your subagents (accept, reject or cancel each: '
                            f'{", ".join(open_children) or "none"}) and jobs (wait or cancel: '
                            f'{", ".join(running) or "none"})')

    def _layout_ok(self, caller: Agent) -> None:
        problems = self.project.check_layout(caller)
        if problems:
            raise ToolError(_layout_notice(problems))

    def _under_review(self) -> bool:
        """True while a COMPLETE or STOP proposal awaits the Reviewer's verdict."""
        return bool(self.state.proposal and not self.state.proposal.get('reviewed'))

    def _talk_only(self, caller: Agent) -> None:
        """Refuse new work by the primary while its proposal is under review (PROJECT.md §4)."""
        if caller.role == 'primary' and self._under_review():
            raise ToolError(f'your proposal (round {self.state.proposal["round"]}) is with the Reviewer: until its '
                            'verdict you may only talk, so spawn and run_job are refused')

    def _admit(self, backend: str) -> None:
        """Refuse a new session while ``backend`` is held or every slot is taken."""
        if self.state.status != 'running':
            raise ToolError(f'the investigation is {self.state.status}; no new work can start now')
        if self._blocked(backend):
            held = self.state.holds.get(backend) or self.state.holds[self.state.agents['primary'].backend]
            raise ToolError(f'{backend} agents are temporarily paused by the usage quota ({held["detail"]}); '
                            'the controller resumes them automatically. Use another backend, or try later')
        live, cap = len(self._live()), self.state.options.max_agents
        if live >= cap:
            raise ToolError(f'{live}/{cap} agents are already working; no more subagents can be started now')

    async def _tool_spawn(self, caller: Agent, task: str, backend: str, model: str, effort: str,
                          name: str = '') -> str:
        self._talk_only(caller)
        allowed = self.state.options.backends
        if backend not in allowed:
            raise ToolError(f'backend {backend!r} is not allowed; allowed: {", ".join(allowed)}')
        if not model.strip() or not effort.strip():
            raise ToolError(f'a model and an effort are required, e.g. {caller.spec}')
        try:  # the backend's driver must accept the effort (a typo would only fail the session's start)
            Spec(backend, model.strip(), effort.strip()).validate('the subagent', self.drivers)
        except ValueError as error:
            raise ToolError(str(error)) from None
        brief = self._path(caller, task, self.project.agent_dir(caller.id), self.project.root)
        if not brief.read_text(encoding='utf-8', errors='replace').strip():
            raise ToolError(f'{task} must be a non-empty Markdown file: the subagent\'s brief')
        self._admit(backend)
        self._continued(caller)
        child = Agent(self._new_id(name), 'subagent', caller.id, backend, model.strip(), effort.strip())
        folder = self.project.agent_dir(child.id)
        folder.mkdir(parents=True)
        atomic_write(folder / 'TASK.md', brief.read_text(encoding='utf-8', errors='replace'), root=self.project.root)
        self.state.agents[child.id] = child
        await self._start_session(child)
        if child.status != 'running':
            return (f'Created subagent {child.id}, but its session could not start; the controller retries it or '
                    'asks the human.')
        return (f'Started subagent {child.id} ({child.spec}); its folder is agents/{child.id}/. '
                'You will be told when it submits its result; meanwhile, continue any work that does not '
                'depend on it.')

    def _continued(self, caller: Agent) -> None:
        """New work by the primary after a STOP challenge means it chose to continue: the STOP lapses."""
        proposal = self.state.proposal
        if caller.role == 'primary' and proposal and proposal['kind'] == 'stop' and proposal.get('challenged'):
            self.state.proposal = None

    def _index_entry(self, agent: Agent, name: str, description: str) -> None:
        """Describe a file the controller put in an agent's folder, so the agent's index stays complete."""
        index = self.project.agent_dir(agent.id) / INDEX
        text = index.read_text(encoding='utf-8') if index.exists() else EMPTY_INDEX
        if name not in text:
            atomic_write(index, f'{text.rstrip()}\n- [{name}]({name}) — {description}\n', root=self.project.root)

    def _new_id(self, name: str) -> str:
        base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40] or 'agent'
        base = 'agent' if base in ('primary', 'reviewer') else base
        candidate, number = base, 1
        while candidate in self.state.agents or self.project.agent_dir(candidate).exists():
            number += 1
            candidate = f'{base}-{number}'
        return candidate

    async def _tool_agents(self, caller: Agent) -> str:
        lines = []
        for child in self.state.children(caller.id):
            session = self.sessions.get(child.id)
            status = ('working' if session and session.busy else 'idle') if child.status == 'running' else child.status
            fill = f', context {child.fill:.0%}' if child.fill is not None else ''
            lines.append(f'- {child.id} ({child.spec}): {status}{fill}. {child.activity}'.rstrip())
        return '\n'.join(lines) or 'You have no subagents.'

    async def _tool_message(self, caller: Agent, agent: str, text: str) -> str:
        """Deliver a message to the caller's parent or one of its subagents (PROJECT.md §3, "Messages")."""
        target = self.state.agents.get(agent)
        if target is None or not (target.parent == caller.id or caller.parent == target.id):
            contacts = [c.id for c in self.state.children(caller.id)] + ([caller.parent] if caller.parent else [])
            raise ToolError(f'{agent} is neither your parent nor one of your subagents; you can message: '
                            + (', '.join(contacts) or 'nobody'))
        if not text.strip():
            raise ToolError('the message is empty')
        if target.status in ENDED:
            raise ToolError(f'{agent} has ended ({target.status})')
        if target.status == 'submitted':
            raise ToolError(f'{agent} has submitted its result: accept it, reject it with feedback, or cancel it')
        notice = prompts.agent_message(caller.id, text)
        await self._notify(target, notice)
        self.show('notice', agent, f'from {caller.id}: {text.strip()}')
        if notice in target.notices:  # no running session to take it now
            return f'{agent} has no running session; it receives your message when its next session starts.'
        return f'Message delivered to {agent}.'

    async def _tool_accept(self, caller: Agent, agent: str) -> str:
        child = self._child(caller, agent)
        if child.status != 'submitted':
            raise ToolError(f'{agent} has not submitted a result (it is {child.status})')
        child.status = 'accepted'
        self._commit(f'{caller.id}: accepted the result of {agent}')
        return f'Accepted the result of {agent}.'

    async def _tool_reject(self, caller: Agent, agent: str, feedback: str) -> str:
        child = self._child(caller, agent)
        if child.status != 'submitted':
            raise ToolError(f'{agent} has not submitted a result (it is {child.status})')
        if not feedback.strip():
            raise ToolError('feedback is required: say what is missing or wrong')
        if self.state.status != 'running':
            raise ToolError(f'the investigation is {self.state.status}; try again after it resumes')
        child.rejections += 1
        record = self.project.agent_dir(child.id) / 'PARENT_FEEDBACK.md'
        previous = record.read_text(encoding='utf-8') if record.exists() else '# Feedback from my parent\n'
        atomic_write(record, f'{previous}\n## Rejection {child.rejections}\n\n{feedback.strip()}\n', root=self.project.root)
        self._index_entry(child, 'PARENT_FEEDBACK.md', 'Feedback from my parent on rejected results.')
        child.notices.append(f'[controller] {caller.id} rejected your result (rejection {child.rejections}); '
                             'its feedback is above. Continue the task and submit again.')
        # An operational hold only delays the restart: the rejection itself always stands.
        if self._blocked(child.backend) or len(self._live()) >= self.state.options.max_agents:
            child.status = 'paused'
            child.pause_reason = 'quota' if self._blocked(child.backend) else 'slots'
            why = ('its CLI is paused by the usage quota' if child.pause_reason == 'quota'
                   else 'every agent slot is taken')
            return (f'Rejected the result of {agent}. It will continue with your feedback automatically as soon as '
                    f'it can run ({why}; this is temporary). Meanwhile, continue any work that does not depend on '
                    'it.')
        await self._start_session(child)
        return f'Rejected the result of {agent}; it continues with your feedback.'

    async def _tool_cancel(self, caller: Agent, agent: str) -> str:
        child = self._child(caller, agent)
        if child.status in ENDED:
            raise ToolError(f'{agent} has already ended ({child.status})')
        await self._cancel_tree(child)
        self._commit(f'{caller.id}: cancelled {agent}')
        await self._resume_agents({'slots'})
        return f'Cancelled {agent}, its subagents and its jobs.'

    async def _cancel_tree(self, agent: Agent) -> None:
        for member in [agent, *self.state.descendants(agent.id)]:
            if member.status in ENDED:
                continue
            await self._close(member.id)
            for job in self.state.running_jobs(member.id):
                await self._stop_job(job)
            member.status, member.closing = 'cancelled', False

    async def _tool_run_job(self, caller: Agent, command: str, timeout_seconds: float, cwd: str = '') -> str:
        self._talk_only(caller)
        if self.state.status != 'running':
            raise ToolError(f'the investigation is {self.state.status}; jobs cannot start now')
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError):
            raise ToolError('timeout_seconds must be a number of seconds') from None
        if not command.strip() or not timeout > 0:
            raise ToolError('a command and a positive timeout_seconds are required')
        folder = self._path(caller, cwd or '.', self.project.agent_dir(caller.id), self.project.root, folder=True)
        self._continued(caller)
        self.state.job_counter += 1
        job = Job(f'job-{self.state.job_counter}', caller.id, command, str(folder), timeout, time.time())
        try:
            self.processes[job.id] = joblib.start(self.project.root, job, read_only=[self.project.evidence],
                                                  hidden=[self.project.research])
        except OSError as error:
            raise ToolError(f'the job could not start: {error}') from None
        self.state.jobs[job.id] = job
        return (f'Started {job.id} (timeout {timeout:g} s); output in agents/{caller.id}/jobs/{job.id}/. '
                'You will be told when it ends; meanwhile, continue any work that does not depend on it.')

    def _job(self, caller: Agent, job_id: str) -> Job:
        job = self.state.jobs.get(job_id)
        if job is None or job.owner != caller.id:
            raise ToolError(f'{job_id} is not one of your jobs')
        return job

    async def _tool_job_status(self, caller: Agent, job: str) -> str:
        return joblib.describe(self.project.root, self._job(caller, job))

    async def _tool_job_cancel(self, caller: Agent, job: str) -> str:
        record = self._job(caller, job)
        if record.status != 'running':
            raise ToolError(f'{job} is not running ({record.status})')
        await self._stop_job(record)
        return joblib.describe(self.project.root, record)

    async def _stop_job(self, job: Job) -> None:
        """Stop a job's processes and reap the process this controller started, if any."""
        await asyncio.to_thread(joblib.cancel, job)
        process = self.processes.pop(job.id, None)
        if process is not None:
            await asyncio.to_thread(process.wait)

    async def _tool_submit_result(self, caller: Agent, result: str = 'RESULT.md') -> str:
        path = self._path(caller, result, self.project.agent_dir(caller.id), self.project.root)
        if not path.read_text(encoding='utf-8', errors='replace').strip():
            raise ToolError(f'{result} must be a non-empty Markdown file')
        self._settled(caller)
        self._layout_ok(caller)
        self._commit(f'{caller.id}: result submitted')
        caller.status, caller.closing, caller.closing_since = 'submitted', True, time.time()
        parent = self.state.agents[caller.parent]
        await self._notify(parent, prompts.result_submitted(caller.id, self.project.relative(path)))
        return f'Your result was submitted to {caller.parent}. End your turn now; this session then closes.'

    async def _propose(self, caller: Agent, kind: str, detail: str) -> str:
        """Submit a COMPLETE or STOP proposal to the Reviewer; the primary's session closes until the verdict."""
        if self._under_review():
            raise ToolError(f'your previous proposal (round {self.state.proposal["round"]}) is still with the Reviewer')
        self._settled(caller)
        self._layout_ok(caller)
        watch = self.watches.get(caller.id)
        if watch is None or not watch.saved_this_session():
            raise ToolError('first update HANDOFF.md in your folder (a brief handoff suffices): your session closes '
                            'while the Reviewer works, and you restart from it')
        self.state.rounds += 1
        self.state.proposal = {'kind': kind, 'round': self.state.rounds, 'detail': detail,
                               'challenged': False, 'reviewed': False}
        self._commit(f'primary: proposes {kind.upper()} (round {self.state.rounds})')
        caller.status, caller.closing, caller.closing_since = 'resting', True, time.time()
        await self._start_review()
        return (f'Your {kind.upper()} proposal is with the Reviewer (round {self.state.rounds}). End your turn now: '
                'your session closes, and you restart from HANDOFF.md when the verdict arrives.')

    async def _tool_complete(self, caller: Agent, report: str = 'REPORT.md') -> str:
        path = self._path(caller, report, self.project.root, self.project.agent_dir(caller.id))
        if not path.read_text(encoding='utf-8', errors='replace').strip():
            raise ToolError(f'{report} must be a non-empty report')
        return await self._propose(caller, 'complete', self.project.relative(path))

    async def _tool_stop(self, caller: Agent, reason: str, final: bool = False) -> str:
        if not reason.strip():
            raise ToolError('a reason is required')
        proposal = self.state.proposal
        if final:
            if not (proposal and proposal['kind'] == 'stop' and proposal.get('challenged')):
                raise ToolError('the Reviewer must challenge a STOP first: call stop(reason) without final')
            self._settled(caller)
            await self._finish('stopped', reason.strip())
            return 'The investigation is stopped.'
        return await self._propose(caller, 'stop', reason.strip())

    async def _start_review(self) -> None:
        """Hand the current proposal to the Reviewer (now, or once its CLI may run)."""
        proposal = self.state.proposal
        self.show('controller', 'reviewer', f'Review round {proposal["round"]}: {proposal["kind"].upper()}.')
        await self._wake(self.state.agents['reviewer'],
                         prompts.review_request(proposal['kind'], proposal['round'], proposal['detail']))

    async def _tool_verdict(self, caller: Agent, review: str, agree: bool) -> str:
        proposal = self.state.proposal
        if not proposal or proposal.get('reviewed'):
            raise ToolError('there is no proposal awaiting your verdict')
        path = self._path(caller, review, self.project.reviews, self.project.root, self.project.agent_dir(caller.id))
        if not path.is_relative_to(self.project.reviews):
            raise ToolError('the review must be a Markdown file in reviews/')
        self._settled(caller)
        self._layout_ok(caller)
        agree = agree if isinstance(agree, bool) else str(agree).lower() in ('true', '1', 'yes')
        proposal['reviewed'], proposal['review'] = True, self.project.relative(path)
        self._commit(f'reviewer: verdict on {proposal["kind"].upper()} round {proposal["round"]} '
                     f'({"agree" if agree else "disagree"})')
        self.show('controller', 'reviewer', f'Verdict: {"agree" if agree else "disagree"} ({proposal["review"]}).')
        caller.status, caller.closing, caller.closing_since = 'resting', True, time.time()
        if proposal['kind'] == 'complete' and agree:
            await self._finish('complete', f'the Reviewer agreed ({proposal["review"]})')
            return 'Verdict recorded: the investigation is COMPLETE.'
        if proposal['kind'] == 'complete':
            self.state.proposal = None
        else:
            proposal['challenged'] = True
        await self._review_ended(prompts.verdict_delivered(proposal['kind'], proposal['round'], proposal['review'],
                                                           agree))
        return 'Verdict delivered to the primary. End your turn now; you will be called for the next round.'

    # Finishing ----------------------------------------------------------------------------------

    async def _finish(self, outcome: str, detail: str) -> None:
        """End the investigation: stop every agent and job, record the outcome and commit."""
        state = self.state
        state.status, state.proposal = outcome, None
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        state.outcome = f'{outcome.upper()} on {stamp}: {detail}'
        for agent_id in list(self.sessions):
            await self._close(agent_id)
        for agent in state.agents.values():
            agent.closing = False
            if agent.status not in ENDED and agent.role != 'reviewer':
                agent.status = 'finished' if agent.role == 'primary' else 'cancelled'
            elif agent.role == 'reviewer':
                agent.status = 'resting'
        for job in state.running_jobs():
            await self._stop_job(job)
        status_file = self.project.root / 'STATUS.md'
        text = status_file.read_text(encoding='utf-8') if status_file.exists() else '# Status\n'
        atomic_write(status_file, f'{text.rstrip()}\n\n## Outcome (recorded by the controller)\n\n{state.outcome}\n',
                     root=self.project.root)
        self._commit(f'controller: investigation {outcome.upper()}')
        self.show('controller', 'primary', f'The investigation is {outcome.upper()}: {detail}')
        self._save()
        self.done.set()

    # Pause, resume and shutdown ------------------------------------------------------------------

    async def _toggle(self) -> None:
        if self.state.status == 'running' and not self._live() and self.releasable:
            await self._release()  # nothing works: "Resume" means lifting what holds the agents
        elif self.state.status == 'running':
            await self._pause()
        elif self.state.status in ('pausing', 'paused'):
            await self._resume()

    async def _pause(self, reason: str = 'pause') -> None:
        """The human's pause (or shutdown): every working agent hands off, then :meth:`_pause_progress` completes it."""
        self.state.status = 'pausing'
        self.show('controller', 'primary', ('Shutting down' if reason == 'shutdown' else 'Pausing')
                  + ': every working agent hands off first.')
        for agent in self._live():
            await self._request_handoff(agent, reason)
        for agent in self.state.agents.values():
            if agent.status == 'paused' and agent.pause_reason in ('slots', 'wake', 'quota', 'failure'):
                agent.pause_reason = 'human' if agent.pause_reason == 'failure' else agent.pause_reason
        await self._pause_progress()

    async def _pause_progress(self) -> None:
        """Complete a pause once no agent is working any more: a pause stops the jobs, a shutdown keeps them."""
        state = self.state
        if state.status != 'pausing' or self._live():
            return
        for agent_id in [a for a in self.sessions if state.agents[a].closing]:
            state.agents[agent_id].closing = False
            await self._close(agent_id)
        shutdown = self.request == 'shutdown'
        if not shutdown:  # jobs survive a shutdown: the next run reattaches them
            for job in state.running_jobs():
                await self._stop_job(job)
                state.agents[job.owner].notices.append(
                    f'[controller] {job.id} was stopped by the human\'s pause; run it again if it is still needed.')
        state.status = 'paused'
        self._commit('controller: shut down by the human' if shutdown else 'controller: paused by the human')
        if not shutdown:
            self.show('controller', 'primary', 'Paused. Agent files may now be edited; press Resume to continue.')
        self._save()
        if shutdown:
            self.done.set()

    async def _resume(self) -> None:
        """The human's resume: report what changed meanwhile, re-read quota and restart paused agents."""
        state = self.state
        self.request = None  # resuming cancels a shutdown still waiting for handoffs
        if state.status == 'paused':
            changed = self.project.uncommitted()
            if changed:
                self._commit('controller: changes made while paused (by the human or by running jobs)')
                self._announce_changes(changed)
        for agent in self._live():  # a pause cancelled while agents were still handing off
            if agent.handoff_reason in ('pause', 'shutdown'):
                agent.handoff_reason = 'context'
                if agent.id in self.watches:
                    self.watches[agent.id].reason = 'context'
        state.status = 'running'
        self.guard.release()  # the human's resume lifts weekly and unreadable holds: the quota is read again
        self.show('controller', 'primary', 'Resumed.')
        await self._check_quota()
        await self._resume_agents()
        self._save()

    async def _release(self) -> None:
        """Lift weekly/unreadable quota holds and retry agents whose automatic retries are exhausted."""
        state = self.state
        if state.status != 'running':
            return
        self.guard.release()
        for agent in state.agents.values():
            if agent.status == 'paused' and agent.pause_reason == 'failure' and agent.retry_at is None:
                agent.failures, agent.pause_reason = 0, 'retry'
        self.show('controller', 'primary', 'Released held CLIs and failed agents; re-reading the usage quota.')
        await self._check_quota()
        await self._resume_agents({'quota', 'retry', 'slots'})
        self._save()

    async def _after_change(self) -> None:
        """Follow-ups once agents may have left the live set: complete a pause, fill free slots."""
        await self._pause_progress()
        await self._resume_agents({'slots'})

    async def _shutdown(self) -> None:
        """Hand every working agent off, then end the controller; jobs keep running."""
        if self.state.status == 'running':
            await self._pause('shutdown')
        elif self.state.status != 'pausing':
            self.done.set()

    # Usage quota ---------------------------------------------------------------------------------

    def _blocked(self, backend: str) -> bool:
        """True if agents on ``backend`` must not run: their CLI, or the primary's, is held."""
        return backend in self.state.holds or self.state.agents['primary'].backend in self.state.holds

    def _backends_in_use(self) -> set[str]:
        agents = [a for a in self.state.agents.values() if a.status not in ENDED]
        return ({a.backend for a in agents} | set(self.state.options.backends)
                | {self.state.agents['primary'].backend, self.state.agents['reviewer'].backend})

    async def _quota_loop(self) -> None:
        while True:
            await asyncio.sleep(WATCH_INTERVAL)
            if time.time() >= self._quota_due:
                readings = await self._read_quota()
                await self._locked(self._apply_quota(readings))

    async def _read_quota(self) -> dict[str, list | Exception]:
        """Read every CLI in use, outside the lock (probes take seconds)."""
        self._quota_due = time.time() + QUOTA_INTERVAL
        return await asyncio.to_thread(self.guard.read, self._backends_in_use())

    async def _check_quota(self) -> None:
        """Read and apply the quota now (called with the lock held)."""
        await self._apply_quota(await self._read_quota())

    async def _apply_quota(self, readings: dict[str, list | Exception]) -> None:
        """Hold or release CLIs according to their usage windows (PROJECT.md §6, "Quota")."""
        for change, backend, hold in self.guard.apply(readings):
            if change == 'held':
                self.show('controller', 'primary', f'Usage quota: {backend} held ({hold["kind"]}: {hold["detail"]}).')
                await self._hold(backend)
            else:
                self.show('controller', 'primary', f'Usage quota: {backend} available again.')
        await self._resume_agents({'quota', 'slots'})
        self._save()

    async def _hold(self, backend: str) -> None:
        """Hand off and pause every working agent that ``backend``'s hold affects."""
        for agent in self._live():
            if self._blocked(agent.backend):
                await self._request_handoff(agent, 'quota', backend)

    # Background checks -----------------------------------------------------------------------------

    async def _watch_loop(self) -> None:
        while True:
            await asyncio.sleep(WATCH_INTERVAL)
            await self._locked(self._watch())

    async def _watch(self) -> None:
        """Jobs that ended, failed agents due a retry, overdue closings and the human's files."""
        state, now = self.state, time.time()
        for job in state.running_jobs():
            if joblib.poll(self.project.root, job, self.processes.get(job.id)):
                self.processes.pop(job.id, None)
                owner = state.agents[job.owner]
                self.show('controller', job.owner, f'{job.id} ended: {job.status}.')
                if owner.status not in ENDED:
                    await self._notify(owner, prompts.job_ended(joblib.describe(self.project.root, job)))
                self._save()
        for agent in state.agents.values():
            if (agent.status == 'paused' and agent.pause_reason == 'failure' and agent.retry_at is not None
                    and now >= agent.retry_at):
                agent.retry_at = None
                agent.pause_reason = 'retry'
                await self._resume_agents({'retry'})
            if agent.closing and agent.closing_since and now > agent.closing_since + CLOSE_GRACE:
                agent.closing = False
                await self._close(agent.id)
        if now >= self._human_checked + HUMAN_INTERVAL:
            self._human_checked = now
            await self._check_human()
        await self._after_change()

    async def _check_human(self) -> None:
        """Tell the primary when the human's own files changed (PROJECT.md §6, "Human edits")."""
        current = self.project.human_fingerprint()
        changed = Project.changed(self.state.human, current)
        if changed:
            self.state.human = current
            self.show('controller', 'primary', 'The human changed: ' + ', '.join(changed[:10]))
            await self._notify(self.state.agents['primary'], prompts.human_changed(changed))
            self._save()

    # Persistence ------------------------------------------------------------------------------------

    def _save(self) -> None:
        self.state.save(self.project.state_file, durable=self.state.options.durable)

    def _commit(self, message: str) -> None:
        """Commit the project; changes to the human's files are reported first (PROJECT.md §2)."""
        current = self.project.human_fingerprint()
        changed = Project.changed(self.state.human, current)
        primary = self.state.agents['primary']
        if changed:
            self.state.human = current
            primary.notices.append(prompts.human_changed(changed))
            self.show('controller', 'primary', 'The human\'s files changed: ' + ', '.join(changed[:10]))
        strays = set(self.project.stray_entries()) - self._strays
        if strays:
            self._strays |= strays
            primary.notices.append(prompts.stray_entries(sorted(strays)))
            self.show('controller', 'primary', 'Unexpected top-level entries: ' + ', '.join(sorted(strays)))
        if primary.notices and primary.status == 'running':
            asyncio.ensure_future(self._locked(self._flush_running(primary)))  # after the current step
        self.project.write_agents_index(list(self.state.agents.values()))
        for owner in {job.owner for job in self.state.jobs.values()}:
            joblib.write_index(self.project.root, owner, list(self.state.jobs.values()))
        try:
            self.project.commit(message)
        except ProjectError as error:
            self.show('controller', 'primary', f'Commit failed: {error}')


def _layout_notice(problems: list[str]) -> str:
    return ('[controller] Fix these layout problems first:\n' + '\n'.join(f'- {p}' for p in problems))


def _brief(args: dict) -> str:
    """Tool arguments shortened for the transcript."""
    return ', '.join(f'{key}={str(value)[:60]!r}' for key, value in args.items())
