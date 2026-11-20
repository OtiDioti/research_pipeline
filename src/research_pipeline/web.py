"""The investigation in the browser (``research-pipeline run PROJECT``, unless ``--no-web``): its phases and agents.

Built on :mod:`agent_toolkit.web`. Before the first start, the setup page first
helps make the folder ready for the first phase (:mod:`research_pipeline.preparation`:
material and objectives, with the setup assistant), always, even for a folder that
is ready already. It then offers every launch option, prefilled from the command
line and the stored (last used) options.

While the program runs, the page's sidebar lists the phases (:mod:`research_pipeline.phases`):
the one running, and every other. The page shows the selected phase's agent graph
(:mod:`research_pipeline.graph`): the running phase's live, with the human's
actions passed on to :meth:`Controller.act <research_pipeline.controller.Controller.act>`;
another phase's as it was left, whose primary and Reviewer the human can talk with.
*New phase* prepares a new phase, and a phase that ended can be prepared for
reopening; their Start (or Reopen), like a paused phase's Resume, hands the running
controller over (:meth:`Controller.hand_over <research_pipeline.controller.Controller.hand_over>`)
once its phase has ended or is paused, and :meth:`ResearchDashboard.restarted`
gives the command line the next phase's controller.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from agent_toolkit import DRIVERS
from agent_toolkit.activity import ActivityLog
from agent_toolkit.web import Dashboard, Field, SettingsError, validate

from research_pipeline import graph
from research_pipeline.controller import Controller
from research_pipeline.fields import NAMES, fields, phase_fields
from research_pipeline.phases import NOT_STARTED, Home, load_state, summaries
from research_pipeline.preparation import Preparation
from research_pipeline.project import INDEX, LIBRARIAN, Project
from research_pipeline.state import FINISHED, Options, State

URL = re.compile(r'https?://[^\s\'"<>)\]]+')
SOURCE = re.compile(r"\blibrary/[\w./-]+")
#: Transcript entries worth a notification.
NOTEWORTHY = re.compile(
    r"quota|failed|could not|paused|resumed|investigation is|is complete|is stopped|stalled|verdict|review round|"
    r"waiting for you|cancelled|reopened",
    re.IGNORECASE,
)
#: How the sidebar colours a phase, by status.
PHASE_COLOURS = {
    NOT_STARTED: "waiting",
    "running": "working",
    "pausing": "paused",
    "paused": "paused",
    "complete": "finished",
    "stopped": "cancelled",
}
#: The phases' sidebar section.
SECTION = "phases"


class ResearchDashboard(Dashboard):
    """The investigation's phases, view, settings and controls for the web app."""

    program = "research_pipeline"
    port = 8780

    def __init__(self, root: Path, options: Options, drivers=DRIVERS, **controller_options):
        """Prefill the setup page from ``options``; ``controller_options`` go to the :class:`Controller` (tests)."""
        super().__init__(root)
        self.options, self.drivers, self.controller_options = options, drivers, controller_options
        self.paths = Project(self.project)
        self.controller: Controller | None = None
        home = Home.load(self.paths.home_file)
        self.selected = home.active or home.latest or 1  # the phase the page shows
        # The phase the page's Start, Reopen or Resume hands over to, with its options (None: the stored ones).
        self.target: tuple[int, Options | None] | None = None
        self.used: dict[str, dict[str, set]] = {}  # '<phase>/<agent>' -> {"sites", "pages"} from its tool calls
        self._listing: tuple[float, int, dict] = (0.0, 0, {})
        # The preparation of the selected phase, if it has one: the first phase's before the first start, a new
        # phase's, or the reopening of one that ended.
        self.preparing = (
            None
            if self.paths.started
            else Preparation(self.paths, options, drivers, read_quota=controller_options.get("read_quota"))
        )
        for number in {phase.number for phase in home.phases} | {self.selected}:
            for entry in ActivityLog(self.paths.at(number).activity).read(None, limit=200_000):
                self._remember(number, entry)
        for entry in ActivityLog(self.paths.library_activity).read(None, limit=200_000):
            self._remember(None, entry)

    # Settings ----------------------------------------------------------------------------------

    def fields(self) -> list[Field]:
        return phase_fields(list(range(1, self.selected))) + fields(list(self.drivers))

    def values(self) -> dict:
        state = self._state(self.selected)
        options = state.options if state else self.controller.state.options if self.controller else self.options
        phase = self._home().phase(self.selected)
        return {
            "title": phase.title if phase else f"Phase {self.selected}",
            "builds_on": str(phase.builds_on) if phase and phase.builds_on else "none",
        } | {name: getattr(options, name) for name in NAMES}

    async def start(self, values: dict) -> None:
        values = validate(self.fields(), values, self.drivers)
        title, builds_on = str(values.pop("title", "") or "").strip(), str(values.pop("builds_on", "none"))
        missing = {
            name: "required" for name in ("primary", "reviewer", "librarian", "backends") if not values.get(name)
        }
        if missing:
            raise SettingsError(missing)
        preparing, number = self.preparing, self.selected
        if self.controller is not None:  # a new phase, or a reopening, while another controller runs
            if preparing is None or self.target is not None:
                raise SettingsError({"": "there is nothing to start"})
            view = preparing.view()
            if not view["ready"]:
                waiting = [check["label"] for check in view["checks"] if not check["ok"]]
                raise SettingsError({"": "Not ready: " + ("; ".join(waiting) or "the folder is not ready")})
        elif preparing is not None:  # the first start: the same checks as the command line's
            problems = self.paths.at(number).unready()
            if problems:
                raise SettingsError({"": "The folder is not ready: " + " ".join(problems)})
        if preparing is not None:
            values["setup"] = preparing.assistant.spec
            await preparing.close(finished=True)
            self.preparing = None
        self._name(number, title, None if builds_on == "none" else int(builds_on))
        state = self._state(number)
        base = state.options if state else self.controller.state.options if self.controller else self.options
        options = Options(**{**vars(base), **values})
        if self.controller is None:
            self.options = options
            self._control(number, options, reopen=False)  # after an end, only the page's Reopen reopens
        else:
            self._switch(number, options)

    async def restarted(self) -> bool:
        """After the controller ended: True, with the next one, if the page's Start, Reopen or Resume ended it."""
        if self.target is None:
            return False
        (number, options), self.target = self.target, None
        self._control(number, options, reopen=True)
        return True

    async def close(self) -> None:
        """End the assistant's session of a preparation still open (it keeps what the page shows of it)."""
        if self.preparing is not None:
            await self.preparing.close()

    def _control(self, number: int, options: Options | None, reopen: bool) -> None:
        controller = Controller(
            self.project, options, phase=number, drivers=self.drivers, reopen=reopen, **self.controller_options
        )
        for phase, log in controller.logs.items():
            log.listeners.append(lambda entry, phase=phase: self._entry(phase, entry))
        controller.library_log.listeners.append(lambda entry: self._entry(None, entry))
        self.controller, self.selected = controller, number

    def _switch(self, number: int, options: Options | None) -> None:
        """Hand the running controller over to phase ``number``'s, once its phase has ended or is paused."""
        controller = self._running()
        if controller.state.status not in FINISHED and controller.state.status != "paused":
            raise ValueError(f"phase {controller.project.phase} is {controller.state.status}: pause it first")
        self.target = (number, options)
        controller.hand_over()

    async def configure(self, values: dict) -> None:
        values = validate([item for item in self.fields() if item.live], values, self.drivers)
        if self._shown() is None:
            raise SettingsError({"": f"phase {self.selected} does not run: its settings apply when it starts"})
        try:
            await self._running().configure(values)
        except ValueError as error:
            raise SettingsError({"": str(error)}) from None

    # Phases --------------------------------------------------------------------------------------

    async def select(self, section: str, item: str) -> dict:
        number = self._phase(section, item)
        if self.preparing is not None and self.preparing.project.phase != number:
            await self.preparing.close()
            self.preparing = None
        self.selected = number
        return {"view": "prepare" if self._state(number) is None else "graph", "text": ""}

    async def add(self, section: str) -> dict:
        if section != SECTION:
            raise ValueError(f"there is no section {section}")
        home = self._home()
        unstarted = [phase.number for phase in home.phases if self._state(phase.number) is None]
        if unstarted:  # one new phase at a time
            await self.select(section, str(unstarted[0]))
            return {"view": "prepare", "text": f"Phase {unstarted[0]} is not started yet: prepare it."}
        phase = home.add()
        self.paths.at(phase.number).create_phase()
        home.save(self.paths.home_file)
        await self.select(section, str(phase.number))
        return {"view": "prepare", "text": f"Added phase {phase.number}: write its objectives, then start it."}

    def _phase(self, section: str, item: str) -> int:
        if section != SECTION:
            raise ValueError(f"there is no section {section}")
        if not item.isdigit() or self._home().phase(int(item)) is None:
            raise ValueError(f"there is no phase {item}")
        return int(item)

    def _sidebar(self) -> list[dict]:
        live = self._shown() or self.controller
        items = []
        for summary in summaries(self.paths, self._home()):
            status = summary.status
            if live is not None and live.project.phase == summary.number:
                status = live.state.status  # fresher than its stored state
            detail = status.upper() if status in FINISHED else status
            items.append(
                {
                    "id": str(summary.number),
                    "label": f"{summary.number}. {summary.title}",
                    "detail": detail + (f" · builds on {summary.builds_on}" if summary.builds_on else ""),
                    "status": PHASE_COLOURS.get(status, "idle"),
                    "running": status in ("running", "pausing")
                    and live is not None
                    and live.project.phase == summary.number,
                    "selected": summary.number == self.selected,
                }
            )
        return [{"id": SECTION, "title": "Phases", "items": items, "add": {"label": "New phase"}}]

    def _name(self, number: int, title: str, builds_on: int | None) -> None:
        """Register phase ``number`` (if new) with its title and the phase it builds on."""
        home = self._home()
        phase = home.phase(number)
        if phase is None:
            phase = home.add()
        phase.title = title or phase.title
        phase.builds_on = builds_on if builds_on and builds_on < number else None
        home.save(self.paths.home_file)

    def _home(self) -> Home:
        """What the phases share: the running controller's (it saves it too), else as stored."""
        return self.controller.home if self.controller is not None else Home.load(self.paths.home_file)

    # Preparation ---------------------------------------------------------------------------------

    def preparation(self) -> dict | None:
        if self.target is not None:  # handing over: nothing to prepare meanwhile
            return None
        if self.preparing is None and self.controller is not None and self.controller.lock is not None:
            number = self.selected
            state = self._state(number)
            kind = "phase" if state is None else "reopen" if state.status in FINISHED else None
            if kind is not None:
                phase = self._home().phase(number)
                self.preparing = Preparation(
                    self.paths.at(number),
                    state.options if state else self.controller.state.options,
                    self.drivers,
                    read_quota=self.controller_options.get("read_quota"),
                    kind=kind,
                    title=phase.title if phase else "",
                    state=lambda: self._state(number),
                    checks=lambda: self._checks(number),
                )
        return self.preparing.view() if self.preparing is not None else None

    def _checks(self, number: int) -> list[dict]:
        """What a phase's Start or Reopen waits for beyond its folder: no other phase runs, the Librarian is done."""
        controller = self._running()
        running = controller.project.phase != number and controller.state.status in ("running", "pausing")
        pending = [folder for folder in controller.home.shelving if folder.startswith(f"phases/{number}/")]
        checks = [
            {
                "label": "No other phase runs",
                "ok": not running,
                "detail": f"phase {controller.project.phase} is {controller.state.status}: pause it first"
                if running
                else "",
            }
        ]
        if self._state(number) is not None:
            checks.append(
                {
                    "label": "The Librarian has placed the phase's final work",
                    "ok": not pending,
                    "detail": f"still placing: {', '.join(pending)}" if pending else "",
                }
            )
        return checks

    async def prepare(self, action: str, args: dict) -> str | None:
        if self.preparing is None:
            raise ValueError("there is nothing to prepare now: edit the files directly")
        return await self.preparing.act(action, args)

    def upload(self, path: str) -> Path:
        if self.preparing is None:
            raise ValueError("there is nothing to prepare now: put files in starting_evidence/ directly")
        return self.preparing.upload(path)

    # The phase shown ------------------------------------------------------------------------------

    def snapshot(self) -> dict:
        controller, number = self._running(), self.selected
        shown = self._shown()
        home = self._home()
        state = shown.state if shown else self._state(number) or State()
        documents = self._documents(number, state)
        view = graph.build(
            state,
            documents,
            self.used,
            number,
            sessions=shown.sessions if shown else {},
            actions=shown.actions if shown else self._talk_actions,
            librarian=None if shown else home.librarian,
            paths=self.paths.at(number),
        )
        status = graph.status(
            self,
            controller,
            number,
            state,
            live=shown is not None,
            preparable=state.status in FINISHED,
        )
        return {"graph": view, "status": status, "settings": self.live(), "sidebar": self._sidebar()}

    def _talk_actions(self, agent) -> list[str]:
        """What the human may do to an agent of a phase that does not run: talk with its primary or Reviewer."""
        return ["message"] if agent.id in ("primary", "reviewer") else []

    def _documents(self, number: int, state: State) -> dict[str, list[str]]:
        """Each agent's documents in phase ``number``, reused briefly."""
        stamp, phase, listing = self._listing
        if phase == number and time.monotonic() - stamp < graph.LISTING_TTL:
            return listing
        listing = graph.documents(self.paths.at(number), state)
        self._listing = (time.monotonic(), number, listing)
        return listing

    # The human's actions -----------------------------------------------------------------------------

    async def act(self, action: str, target: str | None, args: dict) -> str | None:
        controller, shown = self._running(), self._shown()
        if target is None:  # the top bar's controls
            if action == "resume_phase":
                state = self._state(self.selected)
                if shown is not None or state is None or state.status != "paused":
                    raise ValueError(f"phase {self.selected} is not paused")
                self._switch(self.selected, None)
                return f"switching to phase {self.selected}"
            if action in ("pause", "release") and shown is None:
                raise ValueError(f"phase {self.selected} does not run")
            if action == "pause":
                controller.toggle_pause()
                return "pausing" if controller.state.status == "running" else "resuming"
            if action == "release":
                controller.release()
                return "releasing held CLIs and agents"
            if action == "shutdown":
                controller.shutdown()
                return "shutting down"
            raise ValueError(f"{action} is not available")
        if shown is None:  # another phase: talks with its primary and Reviewer only
            if action != "message":
                raise ValueError(f"phase {self.selected} does not run: you can only talk with its primary and Reviewer")
            return await controller.talk(self.selected, target, str(args.get("text", "")))
        return await controller.act(action, target, str(args.get("text", "")))

    def history(self, agent: str | None, limit: int, before: float | None) -> list[dict]:
        phase = ActivityLog(self.paths.at(self.selected).activity)
        library = ActivityLog(self.paths.library_activity)
        if agent == LIBRARIAN:
            return library.read(agent, limit, before)
        if agent is not None:
            return phase.read(agent, limit, before)
        entries = phase.read(None, limit, before) + library.read(None, limit, before)
        return sorted(entries, key=lambda entry: entry["time"])[-limit:]

    def notice(self, kind: str, source: str, text: str) -> dict | None:
        if kind == "alert":
            return {"level": "alert", "text": text}
        if kind == "controller" and NOTEWORTHY.search(text):
            ended = bool(re.search(r"is (COMPLETE|STOPPED)", text))
            return {"level": "alert" if ended else "info", "text": text}
        return None

    # Helpers --------------------------------------------------------------------------------------------

    def _running(self) -> Controller:
        if self.controller is None:
            raise ValueError("the investigation has not started yet")
        return self.controller

    def _shown(self) -> Controller | None:
        """The running controller, if the page shows its phase and it runs (its state is loaded)."""
        controller = self.controller
        if controller is None or controller.lock is None or controller.project.phase != self.selected:
            return None
        return controller

    def _state(self, number: int) -> State | None:
        """Phase ``number``'s state: the running controller's (live), else as stored (None before its start)."""
        controller = self.controller
        if controller is not None and controller.lock is not None and controller.project.phase == number:
            return controller.state
        return load_state(self.paths.at(number))

    def _entry(self, phase: int | None, entry: dict) -> None:
        """A new activity entry (of ``phase``, or the Librarian's): remember what it used; pass it to the page."""
        self._remember(phase, entry)
        if phase is None or phase == self.selected:
            self.publish(entry)

    def _remember(self, phase: int | None, entry: dict) -> None:
        """Note the websites and library pages an agent's tool call used (``phase`` None: the Librarian's)."""
        if entry.get("kind") != "tool":
            return
        key = entry["agent"] if phase is None else f"{phase}/{entry['agent']}"
        used = self.used.setdefault(key, {"sites": set(), "pages": set()})
        used["sites"].update(url.rstrip(".,;") for url in URL.findall(entry.get("text", "")))
        for relative in SOURCE.findall(entry.get("text", "")):
            path = self.project / relative.rstrip(".,;")
            if path.is_file() and path.name != INDEX:
                used["pages"].add(str(path))
