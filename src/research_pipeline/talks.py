"""Talks after the end: talk-only sessions with the primary and the Reviewer (docs/FINISHING.md, PROJECT.md §4).

After COMPLETE or a confirmed STOP the controller stays open, and so does a
later ``run`` on a finished project whose human files did not change. A message
from the human to the primary or the Reviewer then starts a *talk session*: the
agent answers from its work, starting from its last handoff note and its key
files, with every native capability but nothing writable in the project, and
no controller tool but ``write_talk_note``. The finished work stays frozen as
it was catalogued.

Each agent's talk runs as an :class:`agent_toolkit.Relay`: at the context
threshold, the idle limit or a shutdown the session saves a *talk note* in
``.research/talks/<agent>.md`` (never its frozen HANDOFF.md), and the next talk
session starts from the handoff plus that note. Talks are kept only in the
activity log, like any message; reopening the investigation removes the notes,
and the reopened primary gets nothing of them.
"""

from __future__ import annotations

import asyncio
import shutil
from string import Template
from typing import TYPE_CHECKING

from agent_toolkit import CAPABILITIES, ContextExhausted, Launch, Relay, SessionError, SetupError
from agent_toolkit.protocol import sections
from agent_toolkit.records import atomic_write

from research_pipeline import prompts
from research_pipeline.prompts import PROMPTS
from research_pipeline.state import FINISHED, Agent
from research_pipeline.tools import WRITE_TALK_NOTE

if TYPE_CHECKING:
    from research_pipeline.controller import Controller

#: The agents the human can talk with after the end.
TALKERS = ("primary", "reviewer")
#: The MCP server of a talk session (the same name as the investigation's tools).
SERVER = "research"


def message(name: str, **facts) -> str:
    """One of the messages in prompts/talk-messages.md, filled."""
    return Template(sections(PROMPTS.text("talk-messages"))[name]).substitute(facts)


class Talks:
    """The talk sessions of one controller after the end."""

    def __init__(self, controller: Controller):
        self.controller = controller
        self.folder = controller.project.research / "talks"
        self.relays: dict[str, Relay] = {}
        self.tasks: dict[str, asyncio.Task] = {}  # agent id -> its running answer or handoff
        self.sessions: dict[str, int] = {}  # agent id -> talk sessions started (for their logs)

    def open(self, agent: Agent) -> bool:
        """True if the human can talk with ``agent`` now: the investigation has ended, and it is a talker."""
        return self.controller.state.status in FINISHED and agent.id in TALKERS

    def busy(self, agent_id: str) -> bool:
        task = self.tasks.get(agent_id)
        return task is not None and not task.done()

    async def message(self, agent: Agent, text: str) -> str:
        """The human's ``text`` to ``agent``: into its running answer, else as a new request of its talk."""
        controller = self.controller
        if controller._blocked(agent.backend):
            hold = controller.state.holds[agent.backend]
            raise ValueError(
                f"the usage quota of {agent.backend} is held ({hold['detail']}): write again once it resets"
            )
        notice = prompts.human_message(text)
        controller.activity.add(agent.id, "message", notice, sender="human")
        relay = self._relay(agent)
        if self.busy(agent.id):
            relay.post(notice)
            return f"{agent.id} receives your message during its answer."
        self.tasks[agent.id] = asyncio.create_task(self._ask(agent, relay, notice))
        return f"{agent.id} answers (talk only: the investigation has ended)."

    async def check_idle(self) -> None:
        """Close talk sessions idle past the idle limit, each after saving its talk note (unless its CLI is held)."""
        limit = self.controller.state.options.idle_limit * 60
        for agent_id, relay in self.relays.items():
            if limit and relay.session_id and not self.busy(agent_id) and relay.idle >= limit:
                ask = not self.controller._blocked(self.controller.state.agents[agent_id].backend)
                self.tasks[agent_id] = asyncio.create_task(self._hand_off(agent_id, relay, "idle", ask))

    async def close(self, notes: bool = True) -> None:
        """End every talk session, each saving its talk note first if ``notes`` (at a shutdown)."""
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        for agent_id, relay in self.relays.items():
            if notes and relay.session_id:
                ask = not self.controller._blocked(self.controller.state.agents[agent_id].backend)
                await self._hand_off(agent_id, relay, "the human is shutting the controller down", ask)
            await asyncio.to_thread(relay.close)
            self.controller.bridge.withdraw(_offer(agent_id))
        self.relays.clear()

    async def discard(self) -> None:
        """At reopening: end the talks and remove their notes; the investigation continues without them."""
        await self.close(notes=False)
        shutil.rmtree(self.folder, ignore_errors=True)

    # Sessions ---------------------------------------------------------------------------------------

    def _relay(self, agent: Agent) -> Relay:
        relay = self.relays.get(agent.id)
        if relay is not None:
            return relay
        controller, project = self.controller, self.controller.project
        self.folder.mkdir(parents=True, exist_ok=True)
        note = self.folder / f"{agent.id}.md"

        def save(tool: str, args: dict) -> str:
            atomic_write(note, str(args.get("note") or "").strip() + "\n", root=project.root)
            return "Saved your talk note."

        tools = controller.bridge.offer(_offer(agent.id), [WRITE_TALK_NOTE], save, name=SERVER)

        def launch() -> Launch:
            number = self.sessions[agent.id] = self.sessions.get(agent.id, 0) + 1
            return Launch(
                agent=agent.id,
                cwd=project.agent_dir(agent.id),
                instructions=prompts.talk_instructions(agent, project, self.controller.state.status),
                model=agent.model,
                effort=agent.effort,
                tools=CAPABILITIES,
                mcp=tools,
                hidden=(project.research,),
                log=project.logs / f"{agent.id}-talk-{number}.jsonl",
            )

        loop = asyncio.get_running_loop()

        def warn(text: str) -> None:  # from the relay's thread
            loop.call_soon_threadsafe(controller.show, "controller", agent.id, f"{agent.id}'s talk session: {text}.")

        def event(kind: str, data: dict) -> None:  # from the relay's thread
            loop.call_soon_threadsafe(self._event, agent.id, kind, data)

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
        self.relays[agent.id] = relay
        return relay

    async def _ask(self, agent: Agent, relay: Relay, notice: str) -> None:
        def compose(fresh: bool, note: str | None) -> str:
            parts = [self._opening(agent)] if fresh else []
            if note:
                parts.append(message("note", note=note))
            return "\n\n".join([*parts, notice])

        try:
            await asyncio.to_thread(relay.ask, compose)
        except ContextExhausted:
            self.controller.show("alert", agent.id, f"{agent.id}'s talk filled its context: ask a shorter question.")
        except (SetupError, SessionError, OSError) as error:
            self.controller.show("alert", agent.id, f"{agent.id}'s talk session failed: {error}")

    async def _hand_off(self, agent_id: str, relay: Relay, reason: str, ask: bool) -> None:
        try:
            await asyncio.to_thread(relay.hand_off, reason, ask)
        except (SessionError, OSError) as error:
            self.controller.show("controller", agent_id, f"{agent_id}'s talk session ended without its note: {error}")

    def _opening(self, agent: Agent) -> str:
        """What a fresh talk session starts from: the outcome, its last handoff and its key files."""
        project = self.controller.project
        handoff = project.agent_dir(agent.id) / "HANDOFF.md"
        text = handoff.read_text(encoding="utf-8", errors="replace").strip() if handoff.is_file() else "(none)"
        if agent.id == "primary":
            files = message("primary-files")
        else:
            reviews = sorted(path.name for path in project.reviews.glob("*.md") if path.name != "FOLDER_CONTENT.md")
            files = message("reviewer-files", review=f"reviews/{reviews[-1]}" if reviews else "none")
        return message("opening", outcome=self.controller.state.outcome or "", handoff=text, files=files)

    def _event(self, agent_id: str, kind: str, data: dict) -> None:
        """A talk session's driver event, on the controller's loop: shown and kept like any agent's."""
        controller = self.controller
        agent = controller.state.agents[agent_id]
        controller.activity.event(agent_id, kind, data)
        if kind == "text" and data["text"].strip():
            agent.activity = data["text"].strip().splitlines()[0][:200]
            controller.show("agent", agent_id, data["text"])
        elif kind == "tool":
            agent.activity = data["text"][:200]
            if data.get("server") != SERVER:
                controller.show("tool", agent_id, data["text"])
        elif kind == "context":
            agent.tokens, agent.window = data.get("tokens"), data.get("window")


def _offer(agent_id: str) -> str:
    """The name a talk session's tools are offered under (apart from the agent's own investigation sessions)."""
    return f"{agent_id}-talk"
