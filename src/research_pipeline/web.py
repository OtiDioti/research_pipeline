"""The investigation in the browser (``research-pipeline run PROJECT --web``): its agent tree as a live graph.

Built on :mod:`agent_toolkit.web`. The setup page offers every launch option,
prefilled from the command line and the stored (last used) options; the running
page shows every agent that ever worked on the project, its jobs, documents and
the websites and sources it used, and passes the human's actions on to
:meth:`Controller.act <research_pipeline.controller.Controller.act>`.
"""
from __future__ import annotations

from pathlib import Path
import re
import time

from agent_toolkit import DRIVERS
from agent_toolkit.activity import ActivityLog
from agent_toolkit.web import Dashboard, Field, SettingsError, edge, node, validate

from research_pipeline.controller import Controller
from research_pipeline.project import INDEX, Project
from research_pipeline.state import ENDED, Agent, Options

#: How the page colours an agent, by status (paused agents by their pause reason, see :data:`PAUSED`).
COLOURS = {'handing_off': 'handing_off', 'submitted': 'submitted', 'resting': 'idle', 'accepted': 'finished',
           'finished': 'finished', 'cancelled': 'cancelled'}
PAUSED = {'quota': 'held', 'held': 'paused', 'human': 'paused', 'failure': 'failed'}
#: Job statuses as the page colours them.
JOBS = {'running': 'working', 'finished': 'finished', 'cancelled': 'cancelled'}
#: Documents first in an agent's "Task & notes", in this order.
FIRST = ('TASK.md', 'HANDOFF.md', 'RESULT.md', 'PARENT_FEEDBACK.md', 'STATUS.md', 'REPORT.md')
URL = re.compile(r'https?://[^\s\'"<>)\]]+')
SOURCE = re.compile(r'\bsources/[\w./-]+')
#: Transcript entries worth a notification.
NOTEWORTHY = re.compile(r'quota|failed|could not|paused|resumed|investigation is|stalled|verdict|review round|'
                        r'waiting for you|cancelled', re.IGNORECASE)
#: Seconds the listing of agents' folders is reused before being read again.
LISTING_TTL = 3.0


class ResearchDashboard(Dashboard):
    """The investigation's view, settings and controls for the web app."""

    program = 'research_pipeline'
    port = 8780

    def __init__(self, root: Path, options: Options, drivers=DRIVERS, **controller_options):
        """Prefill the setup page from ``options``; ``controller_options`` go to the :class:`Controller` (tests)."""
        super().__init__(root)
        self.options, self.drivers, self.controller_options = options, drivers, controller_options
        self.paths = Project(self.project)
        self.controller: Controller | None = None
        self.used: dict[str, dict[str, set]] = {}  # agent -> {'sites': URLs, 'sources': paths} from its tool calls
        self._listing: tuple[float, dict] = (0.0, {})
        for entry in ActivityLog(self.paths.research / 'activity').read(None, limit=200_000):
            self._remember(entry)

    # Settings ----------------------------------------------------------------------------------

    def fields(self) -> list[Field]:
        backends = list(self.drivers)
        return [
            Field('primary', 'Primary researcher', 'spec', 'Leads the investigation.', options=backends),
            Field('reviewer', 'Reviewer', 'spec', 'Reviews a proposal to finish.', options=backends),
            Field('backends', 'CLIs for subagents', 'multiselect', 'The CLIs agents may choose for their subagents.',
                  options=backends),
            Field('max_agents', 'Agents at once', 'integer', 'Agents with a live session at the same time.', min=1,
                  max=16, step=1, live=True),
            Field('threshold', 'Handoff threshold', 'number', 'Context fill at which an agent hands off.',
                  min=0.05, max=0.8, step=0.01, live=True),
            Field('short_limit', 'Short-window limit', 'number', 'Usage left in a short window that pauses its CLI.',
                  min=0, max=50, step=1, unit='%', live=True),
            Field('weekly_limit', 'Weekly limit', 'number', 'Usage left in a weekly window that pauses its CLI '
                  'until you resume it.', min=0, max=50, step=1, unit='%', live=True),
            Field('references', 'Reference folders', 'paths', 'Read-only folders of other projects agents may consult.',
                  group='advanced'),
            Field('durable', 'Durable state', 'bool', 'Force every state write to disk (off: faster on network '
                  'filesystems).', group='advanced')]

    def values(self) -> dict:
        options = self.controller.state.options if self.controller else self.options
        return {name: getattr(options, name) for name in ('primary', 'reviewer', 'backends', 'max_agents', 'threshold',
                                                         'short_limit', 'weekly_limit', 'references', 'durable')}

    async def start(self, values: dict) -> None:
        values = validate(self.fields(), values, self.drivers)
        missing = {name: 'required' for name in ('primary', 'reviewer', 'backends') if not values.get(name)}
        if missing:
            raise SettingsError(missing)
        self.options = Options(**{**vars(self.options), **values})
        self.controller = Controller(self.project, self.options, drivers=self.drivers, **self.controller_options)
        self.controller.activity.listeners.append(self._entry)

    async def configure(self, values: dict) -> None:
        values = validate([item for item in self.fields() if item.live], values, self.drivers)
        try:
            await self._running().configure(values)
        except ValueError as error:
            raise SettingsError({'': str(error)}) from None

    # The running view -----------------------------------------------------------------------------

    def snapshot(self) -> dict:
        controller = self._running()
        state = controller.state
        nodes, edges = [], []
        listing = self._documents()
        for agent in state.agents.values():
            documents = listing.get(agent.id, [])
            nodes.append(self._agent(controller, agent, documents))
            if agent.parent:
                edges.append(edge(agent.parent, agent.id, 'child'))
                verdict = ('submitted' if agent.status == 'submitted' else 'accepted' if agent.status == 'accepted'
                           else 'rejected' if agent.rejections and agent.status not in ENDED else None)
                if verdict:
                    edges.append(edge(agent.id, agent.parent, 'result', verdict))
            for path in documents:
                nodes.append(node(f'file:{path}', 'file', Path(path).name, owners=[agent.id], path=path))
            used = self.used.get(agent.id, {})
            for url in sorted(used.get('sites', ())):
                nodes.append(node(f'site:{url}', 'site', url.split('/')[2], owners=[agent.id], url=url))
            for path in sorted(used.get('sources', ())):
                nodes.append(node(f'file:{path}', 'file', Path(path).name, owners=[agent.id], path=path))
        if state.verdict and 'reviewer' in state.agents:
            edges.append(edge('reviewer', 'primary', 'result', state.verdict))
        for job in state.jobs.values():
            nodes.append(node(f'job:{job.id}', 'job', job.id, owners=[job.owner], status=JOBS.get(job.status, 'failed'),
                              detail=f'{job.status}: {job.command.strip()[:200]}',
                              path=str(self.paths.agent_dir(job.owner) / 'jobs' / job.id / 'stdout.log')))
        merged: dict[str, dict] = {}
        for item in nodes:  # a source used by two agents appears once, owned by both
            if item['id'] in merged and item['kind'] != 'agent':
                merged[item['id']]['owners'] = sorted({*merged[item['id']]['owners'], *item['owners']})
            else:
                merged[item['id']] = item
        nodes = list(merged.values())
        edges += [edge(owner, item['id'], 'owns') for item in nodes if item['kind'] != 'agent' for owner in item['owners']]
        return {'graph': {'nodes': nodes, 'edges': edges}, 'status': self._status(controller), 'settings': self.live()}

    def _agent(self, controller: Controller, agent: Agent, documents: list[str]) -> dict:
        session = controller.sessions.get(agent.id)
        if agent.status == 'running':
            colour = detail = 'working' if session and session.busy else 'idle'
        elif agent.status == 'paused':
            colour, detail = PAUSED.get(agent.pause_reason, 'waiting'), f'paused ({agent.pause_reason})'
        else:
            colour, detail = COLOURS.get(agent.status, 'idle'), agent.status
        return node(agent.id, 'agent', agent.id, parent=agent.parent, role=agent.role, status=colour, detail=detail,
                    backend=agent.backend, model=agent.model, effort=agent.effort, fill=agent.fill,
                    tokens=agent.tokens, window=agent.window, threshold=controller.state.options.threshold,
                    activity=agent.activity, sessions=agent.sessions, ended=agent.status in ENDED,
                    actions=controller.actions(agent), documents=documents)

    def _status(self, controller: Controller) -> dict:
        state = controller.state
        working = sum(agent.status in ('running', 'handing_off') for agent in state.agents.values())
        summary = f'{working}/{state.options.max_agents} agents working'
        if state.proposal:
            summary += f' · {state.proposal["kind"].upper()} proposal, round {state.proposal["round"]}'
        if state.outcome:
            summary = state.outcome
        held = state.status in ('paused', 'pausing')
        controls = [{'action': 'pause', 'label': 'Resume' if held else 'Pause', 'confirm': None}]
        if controller.releasable:
            controls.append({'action': 'release', 'label': 'Resume held', 'confirm': None})
        controls.append({'action': 'shutdown', 'label': 'Shut down',
                         'confirm': 'Working agents hand off, then the program ends (jobs keep running). Shut down?'})
        return {'program': self.program, 'project': self.project.name, 'state': state.status, 'summary': summary,
                'quota': [{'backend': window.backend, 'minutes': window.minutes, 'left': round(100 - window.used, 1),
                           'resets_at': window.resets_at, 'held': window.backend in state.holds}
                          for window in controller.windows],
                'controls': controls, 'composer': {'target': 'primary', 'label': 'Message the primary researcher'}}

    def _documents(self) -> dict[str, list[str]]:
        """Each agent's documents (its folder's files, the primary's STATUS/REPORT, the reviews), reused briefly."""
        stamp, listing = self._listing
        if time.monotonic() - stamp < LISTING_TTL:
            return listing
        listing = {}
        for agent in self._running().state.agents.values():
            folder = self.paths.agent_dir(agent.id)
            found = [path for path in folder.glob('*') if path.is_file() and path.name != INDEX] if folder.is_dir() else []
            if agent.role == 'primary':
                found += [self.project / name for name in ('STATUS.md', 'REPORT.md') if (self.project / name).is_file()]
            if agent.role == 'reviewer':
                found += [path for path in self.paths.reviews.glob('*.md') if path.name != INDEX]
            order = {name: rank for rank, name in enumerate(FIRST)}
            listing[agent.id] = [str(path) for path in sorted(found, key=lambda path: (order.get(path.name, 99),
                                                                                       path.name))]
        self._listing = (time.monotonic(), listing)
        return listing

    # The human's actions -----------------------------------------------------------------------------

    async def act(self, action: str, target: str | None, args: dict) -> str | None:
        controller = self._running()
        if target is None:  # the top bar's controls, and the message box's default recipient
            if action == 'pause':
                controller.toggle_pause()
                return 'pausing' if controller.state.status == 'running' else 'resuming'
            if action == 'release':
                controller.release()
                return 'releasing held CLIs and agents'
            if action == 'shutdown':
                controller.shutdown()
                return 'shutting down'
            if action != 'message':
                raise ValueError(f'{action} is not available')
            target = 'primary'
        return await controller.act(action, target, str(args.get('text', '')))

    def history(self, agent: str | None, limit: int, before: float | None) -> list[dict]:
        return ActivityLog(self.paths.research / 'activity').read(agent, limit, before)

    def notice(self, kind: str, source: str, text: str) -> dict | None:
        if kind == 'alert':
            return {'level': 'alert', 'text': text}
        if kind == 'controller' and NOTEWORTHY.search(text):
            ended = 'investigation is' in text
            return {'level': 'alert' if ended else 'info', 'text': text}
        return None

    # Helpers --------------------------------------------------------------------------------------------

    def _running(self) -> Controller:
        if self.controller is None:
            raise ValueError('the investigation has not started yet')
        return self.controller

    def _entry(self, entry: dict) -> None:
        """A new activity entry: remember what it used, and pass it to the page."""
        self._remember(entry)
        self.publish(entry)

    def _remember(self, entry: dict) -> None:
        """Note the websites and sources an agent's tool call used."""
        if entry.get('kind') != 'tool':
            return
        used = self.used.setdefault(entry['agent'], {'sites': set(), 'sources': set()})
        used['sites'].update(url.rstrip('.,;') for url in URL.findall(entry.get('text', '')))
        for relative in SOURCE.findall(entry.get('text', '')):
            path = self.project / relative.rstrip('.,;')
            if path.is_file() and path.name != INDEX:
                used['sources'].add(str(path))
