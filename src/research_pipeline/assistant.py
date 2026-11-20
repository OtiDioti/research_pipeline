"""The setup assistant: an agent that helps the human prepare a phase on the web page (docs/SETUP.md).

``kind`` 'setup' makes a folder ready before the first start (the first phase);
the same agent, with its own prompt and requests, helps prepare a new phase
(``kind`` 'phase') or the reopening of a phase that ended (``kind`` 'reopen'), and
may then also write AGENTS.md, on request (:data:`PHASE_TOOLS`).

It is optional: everything it does, the human can do on the page by hand. It
takes one request at a time (organise the material, first ideas with or
without a grill, answers, draft now, a free message) through an
:class:`agent_toolkit.Relay`, which carries its work across sessions through a
handoff note. It reads the whole folder and may search the web, but writes
nothing itself except that note: it places material, writes OBJECTIVES.md and
asks its multiple-choice questions through its tools (:data:`SETUP_TOOLS`),
answered here by the deterministic code of :mod:`research_pipeline.material`.

The usage quota of its CLI is read before every request; a request is refused
while it is at a limit. What the page shows of it (the conversation, its open
questions) is kept in ``.research/setup/<phase>/`` with the note, so a restarted
program continues where it was; the folder is removed when the phase starts,
leaving only the CLI logs in ``.research/logs/``.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
import uuid
from collections.abc import Callable
from string import Template

from agent_toolkit import CAPABILITIES, ContextExhausted, Launch, Relay, SessionError, SetupError, Spec, handoff_server
from agent_toolkit import quota as quota_module
from agent_toolkit.protocol import sections
from agent_toolkit.records import atomic_write
from agent_toolkit.tools import ToolBridge, ToolRefused

from research_pipeline import material
from research_pipeline.project import Project
from research_pipeline.prompts import PROMPTS
from research_pipeline.tools import PHASE_TOOLS, SETUP_TOOLS

#: The agent's id, in its CLI logs and messages.
NAME = "setup"
#: The default choice of CLI, model and effort: setting up is analytical work.
DEFAULT_SPEC = "codex:gpt-6.1-sol:high"


def request_text(name: str, kind: str = "setup", **facts) -> str:
    """One of the messages in prompts/<kind>-requests.md, filled."""
    return Template(sections(PROMPTS.text(f"{kind}-requests"))[name]).substitute(facts)


class Assistant:
    """The setup agent of one folder, and what the page shows of it."""

    def __init__(
        self,
        project: Project,
        spec: str,
        *,
        threshold: float,
        short_limit: float,
        weekly_limit: float,
        drivers: dict,
        read_quota: Callable[[str], list[quota_module.Window]] | None = None,
        kind: str = "setup",
        facts: Callable[[], dict[str, str]] = dict,
    ):
        """``kind`` 'setup' (the first phase), 'phase' (a new one) or 'reopen' (one that ended), for ``project``'s
        phase; ``facts`` adds to its opening message and prompt (e.g. a reopening's ``outcome`` and ``talks``)."""
        self.project, self.drivers = project, drivers
        self.kind, self.facts = kind, facts
        self.threshold, self.short_limit, self.weekly_limit = threshold, short_limit, weekly_limit
        self.read_quota = read_quota or (lambda backend: quota_module.read(self.drivers[backend]))
        self.folder = project.research / NAME / str(project.phase)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.note = self.folder / "HANDOFF.md"
        stored = self._load()
        self.conversation: list[dict] = stored.get("conversation", [])
        self.questions: dict | None = stored.get("questions")
        self.spec = spec or stored.get("spec") or DEFAULT_SPEC  # --setup wins over the page's last choice
        self.busy = False
        self.problem = ""  # why its last request failed ('' : none)
        self.sessions = stored.get("sessions", 0)
        self.briefed = stored.get("briefed", False)  # the human sent their first ideas
        self.bridge = ToolBridge()
        self.tools: dict = {}
        self.relay: Relay | None = None
        self._task: asyncio.Task | None = None

    # What the page shows ----------------------------------------------------------------------

    @property
    def state(self) -> str:
        return "busy" if self.busy else "unavailable" if self.problem else "idle"

    @property
    def detail(self) -> str:
        if self.busy:
            return "working on your request…"
        return self.problem or "ready when you are"

    def say(self, sender: str, text: str) -> None:
        """Add a line to the conversation (``sender``: 'human', 'assistant' or 'program')."""
        self.conversation.append({"time": time.time(), "sender": sender, "text": text})
        self._save()

    # Requests -----------------------------------------------------------------------------------

    def set_spec(self, spec: str) -> None:
        """Run the next sessions on ``spec``; a live session ends (its successor starts from the note)."""
        Spec.parse(spec, "the assistant", self.drivers)
        if self.busy:
            raise ValueError("the assistant is working: change its CLI once it has answered")
        if self.relay is not None:
            self.relay.close()
            self.relay = None
        self.spec, self.problem = spec, ""
        self._save()

    async def request(self, message: str, shown: str) -> str:
        """Send ``message`` to the agent as one request; ``shown`` is what the conversation shows of it.

        Refused (ValueError) while it works on another request or its CLI is at a usage limit.
        """
        if self.busy:
            raise ValueError("the assistant is still working on your last request")
        await self._check_quota()
        self.questions = None  # a new request settles any open questions
        self.say("human", shown)
        self.busy, self.problem = True, ""
        self._task = asyncio.create_task(self._run(message))
        return "Sent to the assistant."

    async def wait(self) -> None:
        """Until the current request is answered (tests, and closing)."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    async def close(self, finished: bool = False) -> None:
        """End its session; ``finished`` (at the start): also remove what it kept for the page."""
        await self.wait()
        if self.relay is not None:
            relay, self.relay = self.relay, None
            await asyncio.to_thread(relay.close)
        await self.bridge.close()
        if finished:
            shutil.rmtree(self.folder, ignore_errors=True)

    async def _check_quota(self) -> None:
        backend = Spec.parse(self.spec, "the assistant", self.drivers).backend
        try:
            windows = await asyncio.to_thread(self.read_quota, backend)
        except OSError:
            return  # unreadable: the request goes ahead (only a reading can show a limit)
        short, weekly = quota_module.check(windows, self.short_limit, self.weekly_limit)
        if short or weekly:
            raise ValueError(
                f"the usage quota of {backend} is at its limit ({', '.join(map(str, short + weekly))}): "
                "choose another CLI for the assistant, or place and write by hand meanwhile"
            )

    async def _run(self, message: str) -> None:
        try:
            if self.relay is None:
                await self.bridge.start()
                tools = SETUP_TOOLS if self.kind == "setup" else PHASE_TOOLS
                self.tools = self.bridge.offer(NAME, tools, self._on_tool, name=NAME)
                self.relay = self._relay()
            relay = self.relay

            def compose(fresh: bool, note: str | None) -> str:
                opening = self.text("opening", state=self._state())
                parts = [opening] if fresh else []
                if note:
                    parts.append(self.text("note", note=note))
                return "\n\n".join([*parts, message])

            await asyncio.to_thread(relay.ask, compose)
        except ContextExhausted:
            self.problem = "its context filled up during one request: send a shorter one"
        except SetupError as error:  # the message names the personal setup to remove
            self.problem = str(error)
        except (SessionError, OSError, ValueError) as error:
            self.problem = f"its session failed: {error}"
        finally:
            self.busy = False
            if self.problem:
                self.say("program", f"The assistant could not answer: {self.problem}. Everything also works by hand.")
            self._save()

    def _relay(self) -> Relay:
        spec = Spec.parse(self.spec, "the assistant", self.drivers)
        handoff, folder = handoff_server.server(self.note)

        def launch() -> Launch:
            self.sessions += 1
            self.project.logs.mkdir(parents=True, exist_ok=True)
            return Launch(
                agent=NAME,
                cwd=self.project.root,
                instructions=PROMPTS.fill(
                    self.kind,
                    project=self.project.root,
                    template=PROMPTS.text("objectives-template"),
                    **self._facts(),
                ),
                model=spec.model,
                effort=spec.effort,
                tools=CAPABILITIES,
                mcp=handoff | self.tools,
                writable=(folder,),
                log=self.project.logs / f"{NAME}-{self.sessions}.jsonl",
            )

        return Relay(
            self.drivers[spec.backend],
            launch,
            note=self.note,
            threshold=self.threshold,
            handoff_request=lambda reason: self.text("handoff", reason=reason),
            note_missing=self.text("handoff-missing"),
            on_turn=self._turned,
            on_warning=lambda text: self.say("program", f"The assistant's session: {text}."),
            pending=self.note.is_file(),
        )

    def _turned(self, reply, answer: bool) -> None:
        """Show the agent's final message of a request (turns spent handing off are not shown)."""
        if answer and reply.text.strip():
            self.say("assistant", reply.text.strip())

    # Its tools ----------------------------------------------------------------------------------

    def text(self, name: str, **facts) -> str:
        """One of this assistant's request messages, filled (see :func:`request_text`)."""
        return request_text(name, self.kind, **(self._facts() | facts))

    def _facts(self) -> dict[str, str]:
        """What its prompt and requests name: the phase, its folder and objectives, and the kind's own facts."""
        project = self.project
        own = {
            "number": str(project.phase),
            "phase": project.folder,
            "objectives": project.relative(project.objectives),
        }
        return own | self.facts()

    def _on_tool(self, tool: str, args: dict) -> str:
        try:
            if tool == "write_objectives":
                return material.write_objectives(self.project, str(args.get("text") or ""))
            if tool == "write_agents_md":
                self.project.write(self.project.root / "AGENTS.md", str(args.get("text") or "").rstrip() + "\n")
                return "Wrote AGENTS.md."
            if tool == "place":
                return material.place(self.project, list(args.get("entries") or []), list(args.get("folders") or []))
            return self._ask(list(args.get("questions") or []))
        except ValueError as error:
            raise ToolRefused(str(error)) from None

    def _ask(self, questions: list) -> str:
        items = []
        for number, item in enumerate(questions, 1):
            if not isinstance(item, dict):
                raise ValueError(f"question {number} must be an object: question, header, options")
            options = [
                {"label": str(option.get("label") or "").strip(), "description": str(option.get("description") or "")}
                for option in item.get("options") or []
                if isinstance(option, dict)
            ]
            if not str(item.get("question") or "").strip() or not 2 <= len(options) <= 4:
                raise ValueError(f"question {number} needs its text and 2 to 4 options")
            if not all(option["label"] for option in options):
                raise ValueError(f"question {number}: every option needs a label")
            items.append(
                {
                    "question": str(item["question"]).strip(),
                    "header": str(item.get("header") or f"Q{number}").strip()[:24],
                    "multi": bool(item.get("multi")),
                    "options": options,
                }
            )
        if not 1 <= len(items) <= 4:
            raise ValueError("ask 1 to 4 questions at a time")
        self.questions = {"id": uuid.uuid4().hex[:12], "items": items}
        self._save()
        return "The human sees your questions. End your turn now: their answers come as your next request."

    # The state it keeps ---------------------------------------------------------------------------

    def _state(self) -> str:
        """The folder as a fresh session needs it: loose and placed material, and the objectives."""
        lines = [
            f"- {entry['path']}{'/' if entry['folder'] else ''} ({entry['state']})"
            + (f" — {entry['description']}" if entry["description"] else "")
            for entry in material.entries(self.project)
        ]
        texts = [(self.project.relative(self.project.objectives), self.project.objectives)]
        shown = "".join(
            f"\n\n{name}:\n\n"
            + ((path.read_text(encoding="utf-8").strip() if path.is_file() else "") or "(not written yet)")
            for name, path in texts
        )
        return "Material:\n" + ("\n".join(lines) or "(none yet)") + shown

    def _load(self) -> dict:
        try:
            return json.loads((self.folder / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        state = {
            "conversation": self.conversation[-500:],
            "questions": self.questions,
            "spec": self.spec,
            "sessions": self.sessions,
            "briefed": self.briefed,
        }
        atomic_write(self.folder / "state.json", json.dumps(state, indent=1), root=self.project.root, durable=False)


def answers_text(questions: dict, answers: list) -> str:
    """The human's answers to a round of questions, as the assistant reads them."""
    lines = []
    for number, (item, answer) in enumerate(zip(questions["items"], answers, strict=False), 1):
        chosen = [str(choice) for choice in (answer or {}).get("choices") or []]
        other = str((answer or {}).get("other") or "").strip()
        given = "; ".join([*chosen, *([f"other: {other}"] if other else [])]) or "(no answer)"
        lines.append(f"{number}. {item['header']}: {item['question']}\n   → {given}")
    return "\n".join(lines)
