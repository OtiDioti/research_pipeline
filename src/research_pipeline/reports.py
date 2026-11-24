"""The reports of a project: the human's WRITING.md, and the Writers of one controller (research_pipeline.writer).

A controller hosts a :class:`Writers`: one :class:`~research_pipeline.writer.Writer` per
report asked for (a phase's, or the project's), created on request, at its phase's end, or
when the page shows a phase whose report was asked for before. It runs the report of a
phase that ends (:meth:`Writers.at_end`), tells waiting requests when the quota holds
change, and closes them with the controller.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from research_pipeline.phases import load_state
from research_pipeline.prompts import PROMPTS
from research_pipeline.state import FINISHED
from research_pipeline.writer import CHECKER, PROJECT_CHECKER, PROJECT_WRITER, WRITER, Writer

if TYPE_CHECKING:
    from research_pipeline.controller import Controller

#: The human's writing rules, at the project's top level.
WRITING = "WRITING.md"


def prepare(project) -> None:
    """Give the project the human's WRITING.md, from the built-in rules, if it has none; list it at the top."""
    path = project.root / WRITING
    if not path.exists():
        project.write(path, PROMPTS.text("writing-starter"))
    project.list_at_top(WRITING, "The human's writing rules for the reports in reports/, which the Writer follows.")


class Writers:
    """The Writers of one controller: one per report asked for, each with its checker."""

    def __init__(self, controller: Controller):
        self.controller = controller
        self.writers: dict[int | None, Writer] = {}

    def get(self, phase: int | None) -> Writer:
        if phase is not None and load_state(self.controller.project.at(phase)) is None:
            raise ValueError(f"phase {phase} has not started: there is nothing to report yet")
        if phase == self.controller.project.phase and self.controller.state.status not in FINISHED:
            raise ValueError(f"phase {phase} is at work: its report is written once it ends")
        if phase not in self.writers:
            self.writers[phase] = Writer(self.controller, phase)
        return self.writers[phase]

    def nodes(self, phase: int) -> list[dict]:
        """The nodes of phase ``phase``'s graph: its Writer's and the project's, once each has been asked for."""
        research = self.controller.project.research / "writer"
        for key, folder in ((phase, f"phase-{phase}"), (None, "project")):
            if key not in self.writers and (research / folder).is_dir():
                self.writers[key] = Writer(self.controller, key)
        return [item for key in (phase, None) if key in self.writers for item in self.writers[key].nodes()]

    def owner(self, node: str, phase: int) -> Writer | None:
        """The Writer a node of phase ``phase``'s graph belongs to (None: not a Writer's)."""
        key = None if node in (PROJECT_WRITER, PROJECT_CHECKER) else phase if node in (WRITER, CHECKER) else -1
        return self.writers.get(key) if key != -1 else None  # type: ignore[arg-type]

    async def at_end(self) -> None:
        """Once the phase has ended and its work is shelved: its report, if the option is on and it is not current."""
        controller = self.controller
        if not controller.state.options.report_at_end:
            return
        writer = self.get(controller.project.phase)
        report = writer.out / "report.pdf"
        if writer.busy or report.is_file() and report.stat().st_mtime >= (controller.state.ended or 0):
            return
        try:
            await writer.start()
        except ValueError as error:
            controller.show("alert", WRITER, f"No report of phase {controller.project.phase}: {error}.")

    @property
    def held(self) -> bool:
        """True while a request waits for its CLI's quota (then the human may release a weekly hold, even after
        the end)."""
        return any(writer.status == "held" for writer in self.writers.values())

    def quota_changed(self) -> None:
        """The controller's quota holds changed: requests waiting for theirs look again."""
        for writer in self.writers.values():
            writer.quota.set()

    async def close(self) -> None:
        await asyncio.gather(*(writer.close() for writer in self.writers.values()))
