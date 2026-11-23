"""Whether the CLIs a phase needs can run now: its primary's, Reviewer's and Librarian's.

Asked of agent_toolkit's CLI status (installed, logged in, confinable by bwrap; no model call, about a
second), for a project shown without a controller: its *Resume phase N* and *Open for
talks* wait while one of them cannot run, with the reason on hover. The web page
asks again (:meth:`Readiness.refresh`) at most every :data:`FRESH` seconds while it
shows the project, so logging in elsewhere frees the button by itself; pressing it
checks once more first (:meth:`Readiness.check`).
"""

from __future__ import annotations

import asyncio
import time

from agent_toolkit import Spec

from research_pipeline.state import Options

#: The roles whose CLIs a phase cannot run without.
ROLES = ("primary", "reviewer", "librarian")
#: Seconds a check is reused while the page shows the project.
FRESH = 30.0


class Readiness:
    """The last check of the CLIs a phase needs, kept fresh while the page asks."""

    def __init__(self, drivers: dict):
        self.drivers = drivers
        self.reason = ""  # why they cannot run ('' : they can, or not checked yet)
        self._checked = 0.0  # when (monotonic), 0: never
        self._task: asyncio.Task | None = None

    async def check(self, options: Options) -> str:
        """Check now; return (and keep) why the CLIs of ``options``' roles cannot run ('' : they can)."""
        backends = []
        for role in ROLES:
            try:
                backend = Spec.parse(getattr(options, role), role, self.drivers).backend
            except ValueError:
                continue  # an unset or unknown choice is the settings' own problem
            if backend not in backends:
                backends.append(backend)
        reasons = await asyncio.gather(*(asyncio.to_thread(self.drivers[backend].status) for backend in backends))
        self.reason, self._checked = "; ".join(reason for reason in reasons if reason), time.monotonic()
        return self.reason

    def refresh(self, options: Options) -> None:
        """Check in the background if the last check is older than :data:`FRESH` seconds (or there is none)."""
        if time.monotonic() - self._checked < FRESH or self._task is not None and not self._task.done():
            return
        self._checked = time.monotonic()  # one check at a time, even while it runs
        self._task = asyncio.ensure_future(self.check(options))
