"""The Writer: reports for the human, written from the agents' work and checked against it (PROJECT.md §4, "Reports").

The agents write their results for each other; the Writer turns a phase's work (or
every phase's, for the project's report) into a report the human reads: a LaTeX
document compiled to a PDF, in ``reports/phase-<N>/`` or ``reports/project/``,
following the human's writing rules in WRITING.md (created from a starter at the
first start, see :func:`research_pipeline.reports.prepare`). It runs on the human's request from the web
page, and once a phase ends if the ``report_at_end`` option is on; a report that
exists is revised, unless the human asks for a fresh one.

One request runs as a cycle (:meth:`Writer.run`): the Writer works in its session
(an :class:`agent_toolkit.Relay`, so it continues across sessions from its handoff
note) until it ends a turn. If it asked a primary something (``ask_primary``,
answered by a talk session, see :meth:`Talks.ask <research_pipeline.talks.Talks.ask>`),
the answers come as its next request. If it submitted the report (``submit_report``),
a fresh checker session (never the Writer's, so that it is not anchored on its
reading) compares the report with the work and ends with ``report_clean`` or
``report_findings``; findings go back to the Writer, until the check is clean or
:data:`MAX_ROUNDS` rounds are spent, when what is left is shown to the human. A turn
that does neither answered the human (or asked them something): the cycle ends.

Once a check of the report came back clean, the Writer's chat offers a *Check
changes* switch (off unless the human turns it on): a cycle the human's message
starts checks what the Writer submits only while it is on; otherwise the submitted
report stands, and the node says it changed since its last check. The report's first
version and a fresh one (*Rewrite report*) are always checked, as are the page's
*Write report* and *Update report*.

A request waits, between its steps, while the quota of its CLI is held (the Writer's
session saves its note and ends first), and continues once it is released.

Both are hosted by the controller (:class:`research_pipeline.reports.Writers`), like the
talks, and appear on the page as nodes of the phase's graph (the project's in every
phase's), which the human writes to;
what they do is kept in the phase's activity log (the project's in the library's).
The controller commits after each cycle.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import time
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING

from agent_toolkit import CAPABILITIES, ContextExhausted, Launch, Relay, SessionError, SetupError, Spec, handoff_server
from agent_toolkit.activity import ActivityLog
from agent_toolkit.protocol import sections
from agent_toolkit.records import atomic_write
from agent_toolkit.tools import ToolRefused
from agent_toolkit.web import node, switch

from research_pipeline.phases import load_state
from research_pipeline.prompts import PROMPTS
from research_pipeline.tools import CHECKER_TOOLS, WRITER_TOOLS

if TYPE_CHECKING:
    from research_pipeline.controller import Controller

#: Checks of one request before what is left goes to the human.
MAX_ROUNDS = 3
#: The page's nodes of a phase's Writer and checker, and of the project's.
WRITER, CHECKER = "writer", "checker"
PROJECT_WRITER, PROJECT_CHECKER = "project-writer", "project-checker"
NODES = (WRITER, CHECKER, PROJECT_WRITER, PROJECT_CHECKER)
#: The Writer's chat switch once its report was checked clean: whether the changes the human asks for are checked.
CHECK = switch("check", "Check changes", "When on, the checker checks the report again after the changes you ask for")
#: The MCP server their tools are offered under (the investigation's name).
SERVER = "research"


def text(name: str, **facts) -> str:
    """One of the messages in prompts/writer-requests.md, filled."""
    return Template(sections(PROMPTS.text("writer-requests"))[name]).substitute(facts)


def unavailable() -> str:
    """Why reports cannot be written on this machine ('' if they can)."""
    return (
        "" if shutil.which("latexmk") else "LaTeX is not installed (latexmk): the Writer compiles its reports with it"
    )


class Writer:
    """The Writer of one report, a phase's (``phase``) or the project's (None), with its checker."""

    def __init__(self, controller: Controller, phase: int | None):
        self.controller, self.phase = controller, phase
        project = controller.project
        self.key = "project" if phase is None else f"phase-{phase}"
        self.ids = (PROJECT_WRITER, PROJECT_CHECKER) if phase is None else (WRITER, CHECKER)
        self.folder = project.research / "writer" / self.key  # its handoff notes and what the page shows
        self.out = project.reports / self.key
        self.checks = self.out / "checks"
        self.note, self.checker_note = self.folder / "HANDOFF.md", self.folder / "CHECKER.md"
        stored = self._load()
        # A cycle a shutdown interrupted does not resume: the human asks again (the Writer continues from its note).
        self.status = "failed" if stored.get("status") == "failed" else "idle"
        self.detail = stored.get("detail", "")
        self.sessions = int(stored.get("sessions", 0))
        self.checked = int(stored.get("checked", 0))  # checks so far: the findings files' numbers
        self.validated = bool(stored.get("validated"))  # a check of this report came back clean
        self.check = True  # whether the running cycle checks what the Writer submits
        self.started = float(stored.get("started") or time.time())
        self.relay: Relay | None = None
        self.task: asyncio.Task | None = None
        self.submitted = False
        self.verdict: tuple[str, str] | None = None  # the checker's: ('clean', '') or ('findings', its file)
        self.pending: list[tuple[int, asyncio.Task]] = []  # the questions it asked primaries, with their phase
        self.quota = asyncio.Event()  # set when the controller's quota holds change
        self.closing = False  # the controller closes: a request waiting for its quota stops

    # What the page shows -------------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self.task is not None and not self.task.done()

    @property
    def target(self) -> str:
        return "the project's report" if self.phase is None else f"the report of phase {self.phase}"

    def nodes(self) -> list[dict]:
        """The Writer's and the checker's nodes on the page (agent_toolkit.web's node contract)."""
        try:
            spec = Spec.parse(self.controller.state.options.writer)
            chosen = {"backend": spec.backend, "model": spec.model, "effort": spec.effort}
        except ValueError:  # none chosen
            chosen = {"backend": "", "model": "", "effort": ""}
        colour = {"writing": "working", "waiting": "waiting", "checking": "idle", "held": "held", "failed": "failed"}
        checking = self.status == "checking"
        report = self.out / "report.pdf"
        common = chosen | {"ended": False, "tag": None}
        writer = node(
            self.ids[0],
            "agent",
            "Writer" if self.phase is not None else "Writer (project)",
            parent=None,
            role="writer",
            status=colour.get(self.status, "idle"),
            detail=self.detail or self.status,
            activity=self.detail,
            sessions=self.sessions,
            actions=["message"],
            switches=[CHECK] if self.validated else [],
            documents=[self.controller.project.relative(report)] if report.is_file() else [],
            **common,
        )
        checker = node(
            self.ids[1],
            "agent",
            "Checker",
            parent=self.ids[0],
            role="reviewer",
            status="working" if checking else "idle",
            detail="checking the report" if checking else "checks each submitted report",
            activity="",
            sessions=self.checked,
            actions=[],
            documents=[],
            **common,
        )
        return [writer, checker]

    # Requests -----------------------------------------------------------------------------------------

    async def start(self, fresh: bool = False) -> str:
        """Write the report (``fresh``: anew), or revise the one that exists; refused while it works."""
        if self.busy:
            raise ValueError(f"the Writer is still working on {self.target}")
        await self._check_cli()
        name = "fresh" if fresh and self.written else "revise" if self.written else "write"
        if name == "fresh":
            self.validated = False  # a new report: checked again before changes may skip the checker
        self.log.add(self.ids[0], "message", text(name), sender="controller")
        self.task = asyncio.create_task(self.run(text(name)))
        return f"The Writer {'rewrites' if fresh else 'writes'} {self.target}."

    async def message(self, words: str, check: bool = False) -> str:
        """The human's message: into its running work, else a new request (a question, or a change to make).

        ``check``: the *Check changes* switch; a new request checks what the Writer submits only if it is on,
        or if no check of the report came back clean yet.
        """
        if not words.strip():
            raise ValueError("the message is empty")
        notice = f"[human] {words.strip()}"
        if self.busy:
            if self.relay is None:
                raise ValueError("the Writer is starting: write again in a moment")
            self.log.add(self.ids[0], "message", notice, sender="human")
            self.relay.post(notice)
            return "The Writer receives your message during its work."
        await self._check_cli()
        self.log.add(self.ids[0], "message", notice, sender="human")
        self.task = asyncio.create_task(self.run(notice, check=check or not self.validated))
        return "Sent to the Writer."

    async def close(self) -> None:
        """Wait for its running cycle (one waiting for its quota stops), then end its session, which saves its
        handoff note first."""
        self.closing = True
        self.quota.set()
        if self.task is not None:
            await asyncio.gather(self.task, return_exceptions=True)
        if self.relay is not None:
            relay, self.relay = self.relay, None
            with contextlib.suppress(SessionError, OSError):  # else its next session starts from the last saved note
                await asyncio.to_thread(relay.hand_off, "the controller is closing")
            await asyncio.to_thread(relay.close)
            self.controller.bridge.withdraw(f"{self.key}-writer")

    @property
    def written(self) -> bool:
        return (self.out / "report.tex").is_file()

    @property
    def log(self) -> ActivityLog:
        """Where what it does is kept: its phase's activity log, or the library's for the project's report."""
        return self.controller.library_log if self.phase is None else self.controller.talks.log(self.phase)

    # The cycle ----------------------------------------------------------------------------------------

    async def run(self, request: str, check: bool = True) -> None:
        """Run ``request``, then check each report the Writer submits (unless not ``check``), as the module says."""
        rounds, message, previous = 0, request, ""
        self.check = check
        try:
            while message:
                self.submitted = False
                if not await self._unheld():
                    break
                self._status("writing", "working on the report")
                reply = await self._ask(self._writer(), message, self.ids[0])
                message = ""
                if self.pending:
                    self._status("waiting", "waiting for a primary's answer")
                    message = await self._answers()
                    continue
                if not self.submitted:
                    break  # it answered the human, or asked them something
                if not self.check:
                    self._status("idle", f"{self.target} changed since its last check (Check changes was off)")
                    break
                if rounds:
                    previous = previous and text("previous", file=previous, reply=reply.strip() or "(none)")
                rounds += 1
                if not await self._unheld():
                    break
                self._status("checking", f"the checker compares the report with the work (round {rounds})")
                verdict = await self._check(rounds, previous)
                if verdict[0] == "clean":
                    self.validated = True
                    self._status("idle", f"{self.target} is written and checked")
                    break
                if rounds >= MAX_ROUNDS or verdict[0] == "none":
                    left = f"see {verdict[1]}" if verdict[1] else "the checker ended without a verdict"
                    self._status("idle", f"{self.target} has discrepancies left after {rounds} checks: {left}")
                    self.controller.show("alert", self.ids[0], f"The Writer: {self.detail}.")
                    break
                previous = verdict[1]
                findings = (self.controller.project.root / verdict[1]).read_text(encoding="utf-8", errors="replace")
                message = text("findings", round=rounds, rounds=MAX_ROUNDS, file=verdict[1], findings=findings)
            if self.status in ("writing", "waiting"):  # it answered the human, or asked them something
                self._status("idle", "waiting for your next message" if self.written else "no report yet")
        except (ContextExhausted, SetupError, SessionError, OSError, ValueError) as error:
            self._status("failed", f"its session failed: {error}")
            self.controller.show("alert", self.ids[0], f"The Writer's session failed: {error}")
        finally:
            self._commit()

    async def _ask(self, relay: Relay, message: str, agent_id: str) -> str:
        """One request to ``relay``'s agent; its reply's text."""

        def compose(fresh: bool, note: str | None) -> str:
            parts = [self._opening()] if fresh and agent_id == self.ids[0] else []
            if note:
                parts.append(text("note", note=note))
            return "\n\n".join([*parts, message])

        reply = await asyncio.to_thread(relay.ask, compose)
        return reply.text

    async def _answers(self) -> str:
        """The answers to the Writer's questions to primaries, as its next request."""
        asked, self.pending = self.pending, []
        parts = []
        for phase, task in asked:
            try:
                parts.append(text("answer", phase=phase, answer=await task))
            except ValueError as error:
                parts.append(f"[controller] {error}")
        return "\n\n".join(parts)

    async def _check(self, round_: int, previous: str) -> tuple[str, str]:
        """One check by a fresh checker: ('clean', ''), ('findings', its file) or ('none', '') without a verdict."""
        self.checked += 1
        self.verdict = None
        relay = self._checker(self.checked)
        try:
            request = text("check", target=self.target, round=round_, rounds=MAX_ROUNDS, previous=previous)
            await self._ask(relay, request, self.ids[1])
            if self.verdict is None:  # once more: it must end with one of its two tools
                await self._ask(relay, "[controller] End your check: call report_clean or report_findings.", "")
        finally:
            await asyncio.to_thread(relay.close)
            self.controller.bridge.withdraw(f"{self.key}-checker")
        return self.verdict or ("none", "")

    # Sessions -----------------------------------------------------------------------------------------

    def _writer(self) -> Relay:
        if self.relay is None:
            tools = self.controller.bridge.offer(f"{self.key}-writer", WRITER_TOOLS, self._writer_tool, name=SERVER)
            self.relay = self._relay(self.ids[0], self.note, "writer", tools, (self.out,), self._next_session)
        return self.relay

    def _checker(self, number: int) -> Relay:
        tools = self.controller.bridge.offer(f"{self.key}-checker", CHECKER_TOOLS, self._checker_tool, name=SERVER)
        self.checks.mkdir(parents=True, exist_ok=True)
        self.checker_note.unlink(missing_ok=True)  # every check starts afresh
        return self._relay(self.ids[1], self.checker_note, "checker", tools, (self.checks,), lambda: number)

    def _relay(self, agent_id: str, note: Path, prompt: str, tools: dict, writable: tuple, number) -> Relay:
        controller, project = self.controller, self.controller.project
        spec = Spec.parse(controller.state.options.writer, "the Writer", controller.drivers)
        handoff, notes = handoff_server.server(note)
        self.out.mkdir(parents=True, exist_ok=True)
        facts = self._facts() | {"checks": f"/{project.relative(self.checks)}", "round": str(self.checked)}
        loop = asyncio.get_running_loop()

        def launch() -> Launch:
            return Launch(
                agent=agent_id,
                cwd=self.out,
                instructions=PROMPTS.fill(prompt, **facts),
                model=spec.model,
                effort=spec.effort,
                tools=CAPABILITIES,
                mcp=handoff | tools,
                writable=(*writable, notes),
                # The program's records stay hidden, but the Writer's own folder of them (its notes).
                hidden=tuple(path for path in project.research.iterdir() if path.is_dir() and path.name != "writer"),
                environment=project.environment,
                log=project.logs / f"{self.key}-{agent_id}-{number()}.jsonl",
            )

        def event(kind: str, data: dict) -> None:  # from the relay's thread
            loop.call_soon_threadsafe(self._event, agent_id, kind, data)

        def warn(words: str) -> None:  # from the relay's thread
            loop.call_soon_threadsafe(controller.show, "controller", agent_id, words)

        return Relay(
            controller.drivers[spec.backend],
            launch,
            note=note,
            threshold=controller.state.options.threshold,
            handoff_request=lambda reason: text("handoff", reason=reason),
            note_missing=text("handoff-missing"),
            on_event=event,
            on_warning=warn,
            pending=note.is_file(),
        )

    def _next_session(self) -> int:
        self.sessions += 1
        self._save()
        return self.sessions

    def _event(self, agent_id: str, kind: str, data: dict) -> None:
        self.log.event(agent_id, kind, data)
        if kind == "text" and data["text"].strip():
            self.controller.show("agent", agent_id, data["text"])

    async def _unheld(self) -> bool:
        """Before each step of a request: while its CLI's quota is held, its session saves its note and ends, and
        the request waits; False if the controller closes meanwhile (the request then stops)."""
        backend = self._backend()
        if not self.controller._blocked(backend):
            return True
        self.controller.show("controller", self.ids[0], f"The Writer waits: the usage quota of {backend} is held.")
        if self.relay is not None and self.relay.session_id:
            with contextlib.suppress(SessionError, OSError):  # else its next session starts from the last saved note
                await asyncio.to_thread(self.relay.hand_off, f"the usage quota of {backend} is held")
        self._status("held", f"waiting for the usage quota of {backend}")
        while self.controller._blocked(backend) and not self.closing:
            self.quota.clear()
            await self.quota.wait()
        if self.closing:
            self._status("idle", "stopped while waiting for the usage quota: ask again")
            return False
        return True

    def _backend(self) -> str:
        return Spec.parse(self.controller.state.options.writer, "the Writer", self.controller.drivers).backend

    async def _check_cli(self) -> None:
        """Refuse a request its CLI cannot serve (one whose quota is held waits instead, see :meth:`_unheld`)."""
        reason = unavailable() or await asyncio.to_thread(self.controller.drivers[self._backend()].status)
        if reason:
            raise ValueError(f"the Writer cannot run now: {reason}")

    # Its tools ----------------------------------------------------------------------------------------

    def _writer_tool(self, tool: str, args: dict) -> str:
        if tool == "submit_report":
            pdf, tex = self.out / "report.pdf", self.out / "report.tex"
            if not tex.is_file() or not pdf.is_file() or pdf.stat().st_mtime < tex.stat().st_mtime:
                raise ToolRefused("compile the report first: report.pdf is missing or older than report.tex")
            self.submitted = True
            if not self.check:
                return text("submitted-unchecked")
            return "Submitted: an independent checker compares it with the work. End your turn now."
        phase, question = args.get("phase"), str(args.get("question") or "").strip()
        if not isinstance(phase, int) or not question:
            raise ToolRefused("give the phase's number and your question")
        if load_state(self.controller.project.at(phase)) is None:
            raise ToolRefused(f"phase {phase} has not started")
        task = asyncio.ensure_future(self.controller.talks.ask(phase, text("question", question=question)))
        self.pending.append((phase, task))
        return f"Asked the primary of phase {phase}. End your turn now: its answer comes as your next request."

    def _checker_tool(self, tool: str, args: dict) -> str:
        if tool == "report_clean":
            self.verdict = ("clean", "")
            return "Recorded: the report is clean. End your turn now."
        given = str(args.get("file") or "").strip()
        root = self.controller.project.root
        candidates = [root / given.lstrip("/"), self.out / given, Path(given)]  # from the root, its folder, or absolute
        path = next((item.resolve() for item in candidates if given and item.is_file()), self.out)
        if not path.is_relative_to(self.checks.resolve()) or not path.read_text(errors="replace").strip():
            raise ToolRefused(f"write your findings to a file in {self.controller.project.relative(self.checks)}/")
        self.verdict = ("findings", self.controller.project.relative(path))
        return "Recorded: the Writer gets your findings. End your turn now."

    # What it keeps ------------------------------------------------------------------------------------

    def _facts(self) -> dict[str, str]:
        project = self.controller.project
        if self.phase is None:
            sources = (
                "every phase's report in /reports/phase-<N>/ (write a missing one's part from that phase's "
                "result), and the phases' results in /phases/<N>/ where the reports disagree or something "
                "is missing; the human's documents in /starting_evidence/."
            )
        else:
            phase = project.at(self.phase)
            sources = (
                f"the phase's objectives (/{project.relative(phase.objectives)}), its result "
                f"(/{project.relative(phase.result)}) and status (/{project.relative(phase.status_file)}), its "
                f"agents' folders (/{phase.folder}/agents/: their results, notes, derivations, data and figures, "
                f"and the notation file /{phase.folder}/agents/primary/NOTATION.md), its reviews "
                f"(/{phase.folder}/reviews/); the human's documents in /starting_evidence/; and the earlier "
                "phases' reports in /reports/, for what this phase builds on."
            )
        return {
            "project": str(project.root),
            "target": self.target,
            "folder": f"/{project.relative(self.out)}" if self.out.exists() else f"/reports/{self.key}",
            "sources": sources,
        }

    def _opening(self) -> str:
        facts = self._facts()
        report = text("a-report" if self.written else "no-report")
        return text("opening", target=facts["target"], folder=facts["folder"], report=report)

    def _status(self, status: str, detail: str) -> None:
        self.status, self.detail = status, detail
        self._save()

    def _commit(self) -> None:
        project = self.controller.project
        if self.out.exists():
            project.list_at_top(
                "reports", "The Writer's reports for the human: one folder per phase, and the project's."
            )
            index = self.out.parent / "FOLDER_CONTENT.md"
            text_ = index.read_text(encoding="utf-8") if index.is_file() else "# Folder contents\n\n"
            if f"[{self.key}]({self.key})" not in text_:
                atomic_write(
                    index, f"{text_.rstrip()}\n- [{self.key}]({self.key}) — {self.target}.\n", root=project.root
                )
        self.controller._commit(f"writer: {self.target} ({self.status}: {self.detail})")

    def _load(self) -> dict:
        try:
            return json.loads((self.folder / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        state = {
            "status": self.status,
            "detail": self.detail,
            "sessions": self.sessions,
            "checked": self.checked,
            "validated": self.validated,
            "spec": self.controller.state.options.writer,  # for the stats
            "started": self.started,
        }
        atomic_write(self.folder / "state.json", json.dumps(state, indent=1), root=self.controller.project.root)
