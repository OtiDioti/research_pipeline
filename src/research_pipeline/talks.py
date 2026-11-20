"""Talks: talk-only sessions with the primary and the Reviewer of a phase that does not run (PROJECT.md §4).

After COMPLETE or a confirmed STOP the controller stays open, and so does a later
``run`` on a finished phase whose objectives did not change. A message from the
human to the phase's primary or Reviewer then starts a *talk session*. The human
can also talk, at any time, with the primary and the Reviewer of any other phase
that has started (ended or paused), while this one runs. The agent answers from
its work, starting from its last handoff note and its key files, with every
native capability but nothing writable in the project, and no controller tool but
``write_talk_note``. The work stays as it was.

Each agent's talk runs as an :class:`agent_toolkit.Relay`: at the context
threshold, the idle limit or a shutdown the session saves a *talk note* in
``.research/phases/<N>/talks/<agent>.md`` (never its HANDOFF.md), and the next
talk session starts from the handoff plus that note. Talks are kept only in the
phase's activity log, like any message; reopening a phase removes its notes, and
its reopened primary gets nothing of them.
"""

from __future__ import annotations

import asyncio
import shutil
from string import Template
from typing import TYPE_CHECKING

from agent_toolkit import CAPABILITIES, ContextExhausted, Launch, Relay, SessionError, SetupError
from agent_toolkit.activity import ActivityLog
from agent_toolkit.protocol import sections
from agent_toolkit.records import atomic_write

from research_pipeline import prompts
from research_pipeline.phases import load_state
from research_pipeline.project import Project
from research_pipeline.prompts import PROMPTS
from research_pipeline.state import FINISHED, Agent, State
from research_pipeline.tools import WRITE_TALK_NOTE

if TYPE_CHECKING:
    from research_pipeline.controller import Controller

#: The agents the human can talk with.
TALKERS = ("primary", "reviewer")
#: The MCP server of a talk session (the same name as the investigation's tools).
SERVER = "research"


def message(name: str, **facts) -> str:
    """One of the messages in prompts/talk-messages.md, filled."""
    return Template(sections(PROMPTS.text("talk-messages"))[name]).substitute(facts)


def situation(state: State, full: bool = False) -> str:
    """What a phase that does not run is, for its talkers: ended (``full``: and how), or paused."""
    if state.status in FINISHED:
        return f"has ended ({state.outcome if full and state.outcome else state.status.upper()})"
    return "is paused: its work may continue later"


class Talks:
    """The talk sessions one controller hosts: with its own phase after the end, and with other phases."""

    def __init__(self, controller: Controller):
        self.controller = controller
        self.relays: dict[str, Relay] = {}  # '<phase>/<agent>' -> its talk
        self.tasks: dict[str, asyncio.Task] = {}  # its running answer or handoff
        self.sessions: dict[str, int] = {}  # talk sessions started (for their logs)
        self.agents: dict[str, Agent] = {}  # the talkers of other phases, from their stored states

    def open(self, agent: Agent) -> bool:
        """True if the human can talk with ``agent`` of this phase now: it has ended, and it is a talker."""
        return self.controller.state.status in FINISHED and agent.id in TALKERS

    def busy(self, key: str) -> bool:
        task = self.tasks.get(key)
        return task is not None and not task.done()

    async def message(self, agent: Agent, text: str) -> str:
        """The human's ``text`` to ``agent`` of this phase, which has ended."""
        controller = self.controller
        return await self._message(controller.project, agent, controller.state, text)

    async def message_phase(self, phase: int, agent_id: str, text: str) -> str:
        """The human's ``text`` to the primary or the Reviewer of another phase."""
        project = self.controller.project
        if phase == project.phase:
            raise ValueError(f"phase {phase} is this controller's own")
        state = load_state(project.at(phase))
        if state is None:
            raise ValueError(f"phase {phase} has not started")
        if agent_id not in TALKERS or agent_id not in state.agents:
            raise ValueError(f"only the primary and the Reviewer of phase {phase} can be talked to")
        agent = self.agents.setdefault(f"{phase}/{agent_id}", state.agents[agent_id])
        return await self._message(project.at(phase), agent, state, text)

    async def check_idle(self) -> None:
        """Close talk sessions idle past the idle limit, each after saving its talk note (unless its CLI is held)."""
        limit = self.controller.state.options.idle_limit * 60
        for key, relay in self.relays.items():
            if limit and relay.session_id and not self.busy(key) and relay.idle >= limit:
                ask = not self.controller._blocked(self._agent(key).backend)
                self.tasks[key] = asyncio.create_task(self._hand_off(key, relay, "idle", ask))

    async def close(self, notes: bool = True) -> None:
        """End every talk session, each saving its talk note first if ``notes``."""
        await self._close(list(self.relays), notes)

    async def discard(self) -> None:
        """At this phase's reopening: end its talks and remove their notes; it continues without them."""
        mine = f"{self.controller.project.phase}/"
        await self._close([key for key in self.relays if key.startswith(mine)], notes=False)
        shutil.rmtree(self.controller.project.talks, ignore_errors=True)

    async def _close(self, keys: list[str], notes: bool) -> None:
        await asyncio.gather(*(self.tasks[key] for key in keys if key in self.tasks), return_exceptions=True)
        for key in keys:
            relay = self.relays.pop(key)
            if notes and relay.session_id:
                ask = not self.controller._blocked(self._agent(key).backend)
                await self._hand_off(key, relay, "the human is shutting the controller down", ask)
            await asyncio.to_thread(relay.close)
            self.controller.bridge.withdraw(_offer(key))

    # Sessions ---------------------------------------------------------------------------------------

    async def _message(self, project: Project, agent: Agent, state: State, text: str) -> str:
        """The human's ``text`` to ``agent`` of ``project``'s phase: into its running answer, else a new request."""
        controller, key = self.controller, f"{project.phase}/{agent.id}"
        if controller._blocked(agent.backend):
            hold = controller.state.holds[agent.backend]
            raise ValueError(
                f"the usage quota of {agent.backend} is held ({hold['detail']}): write again once it resets"
            )
        notice = prompts.human_message(text)
        self._log(project.phase).add(agent.id, "message", notice, sender="human")
        relay = self._relay(project, agent, situation(state))
        if self.busy(key):
            relay.post(notice)
            return f"{agent.id} receives your message during its answer."
        self.tasks[key] = asyncio.create_task(self._ask(project, agent, relay, notice, situation(state, full=True)))
        return f"{agent.id} of phase {project.phase} answers (talk only: the phase does not run)."

    def _relay(self, project: Project, agent: Agent, where: str) -> Relay:
        key = f"{project.phase}/{agent.id}"
        relay = self.relays.get(key)
        if relay is not None:
            return relay
        controller = self.controller
        project.talks.mkdir(parents=True, exist_ok=True)
        note = project.talks / f"{agent.id}.md"

        def save(tool: str, args: dict) -> str:
            atomic_write(note, str(args.get("note") or "").strip() + "\n", root=project.root)
            return "Saved your talk note."

        tools = controller.bridge.offer(_offer(key), [WRITE_TALK_NOTE], save, name=SERVER)

        def launch() -> Launch:
            number = self.sessions[key] = self.sessions.get(key, 0) + 1
            return Launch(
                agent=agent.id,
                cwd=project.agent_dir(agent.id),
                instructions=prompts.talk_instructions(agent, project, where),
                model=agent.model,
                effort=agent.effort,
                tools=CAPABILITIES,
                mcp=tools,
                hidden=(project.research,),
                log=project.session_log(agent.id, number, "talk"),
            )

        loop = asyncio.get_running_loop()
        label = self._label(project.phase, agent.id)

        def warn(text: str) -> None:  # from the relay's thread
            loop.call_soon_threadsafe(controller.show, "controller", label, f"{label}'s talk session: {text}.")

        def event(kind: str, data: dict) -> None:  # from the relay's thread
            loop.call_soon_threadsafe(self._event, key, kind, data)

        relay = Relay(
            controller.drivers[agent.backend],
            launch,
            note=note,
            threshold=controller.state.options.threshold,
            handoff_request=lambda reason: message("handoff", reason=reason),
            note_missing=message("handoff-missing"),
            on_warning=warn,
            on_event=event,
            pending=note.is_file(),
        )
        self.relays[key] = relay
        return relay

    async def _ask(self, project: Project, agent: Agent, relay: Relay, notice: str, where: str) -> None:
        label = self._label(project.phase, agent.id)

        def compose(fresh: bool, note: str | None) -> str:
            parts = [self._opening(project, agent, where)] if fresh else []
            if note:
                parts.append(message("note", note=note))
            return "\n\n".join([*parts, notice])

        try:
            await asyncio.to_thread(relay.ask, compose)
        except ContextExhausted:
            self.controller.show("alert", label, f"{label}'s talk filled its context: ask a shorter question.")
        except (SetupError, SessionError, OSError) as error:
            self.controller.show("alert", label, f"{label}'s talk session failed: {error}")

    async def _hand_off(self, key: str, relay: Relay, reason: str, ask: bool) -> None:
        try:
            await asyncio.to_thread(relay.hand_off, reason, ask)
        except (SessionError, OSError) as error:
            self.controller.show("controller", key, f"{key}'s talk session ended without its note: {error}")

    def _opening(self, project: Project, agent: Agent, where: str) -> str:
        """What a fresh talk session starts from: where its phase stands, its last handoff and its key files."""
        handoff = project.agent_dir(agent.id) / "HANDOFF.md"
        text = handoff.read_text(encoding="utf-8", errors="replace").strip() if handoff.is_file() else "(none)"
        report, status = project.relative(project.report), project.relative(project.status_file)
        if agent.id == "primary":
            files = message("primary-files", report=report, status=status)
        else:
            reviews = sorted(path.name for path in project.reviews.glob("*.md") if path.name != "FOLDER_CONTENT.md")
            folder = project.relative(project.reviews)
            files = message(
                "reviewer-files",
                reviews=folder,
                review=f"{folder}/{reviews[-1]}" if reviews else "none",
                report=report,
            )
        return message("opening", phase=project.phase, situation=where, handoff=text, files=files)

    def _event(self, key: str, kind: str, data: dict) -> None:
        """A talk session's driver event, on the controller's loop: shown and kept like any agent's."""
        controller = self.controller
        phase, agent_id = key.split("/", 1)
        agent = self._agent(key)
        self._log(int(phase)).event(agent_id, kind, data)
        label = self._label(int(phase), agent_id)
        if kind == "text" and data["text"].strip():
            agent.activity = data["text"].strip().splitlines()[0][:200]
            controller.show("agent", label, data["text"])
        elif kind == "tool":
            agent.activity = data["text"][:200]
            if data.get("server") != SERVER:
                controller.show("tool", label, data["text"])
        elif kind == "context":
            agent.tokens, agent.window = data.get("tokens"), data.get("window")

    def _agent(self, key: str) -> Agent:
        phase, agent_id = key.split("/", 1)
        if int(phase) == self.controller.project.phase:
            return self.controller.state.agents[agent_id]
        return self.agents[key]

    def _log(self, phase: int) -> ActivityLog:
        controller = self.controller
        if phase not in controller.logs:
            project = controller.project.at(phase)
            controller.logs[phase] = ActivityLog(project.activity, root=project.root)
        return controller.logs[phase]

    def _label(self, phase: int, agent_id: str) -> str:
        """How the transcript names a talker: by its id in this phase, with its phase in another."""
        return agent_id if phase == self.controller.project.phase else f"{agent_id} (phase {phase})"


def _offer(key: str) -> str:
    """The name a talk session's tools are offered under (apart from the agents' own sessions)."""
    return f"{key.replace('/', '-')}-talk"
