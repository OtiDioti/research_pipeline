"""The controller's side of the Librarian: shelving, its two tools, and its turns (PROJECT.md §2–§4, §7).

When an agent's work is finished, :meth:`Librarian.shelve` catalogues its folder
(:mod:`research_pipeline.library`), which is frozen from then on, and asks the
Librarian to place it. Nothing moves: the Librarian writes Markdown pages in
``library/`` through ``write_page``, and ``shelved(folder)`` is refused until its
pages reach every catalogued file of that folder and no link leads nowhere
(:mod:`research_pipeline.links`). The Librarian serves every phase: its record and
pending requests are the project's (:class:`research_pipeline.phases.Home`), and
requests name agents by folder (agent ids repeat across phases). The controller
of the phase that runs wires this service in: it supplies the state, delivers
notices and commits.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from agent_toolkit.records import atomic_write

from research_pipeline import links, prompts
from research_pipeline.library import CATALOG, Catalogue, render
from research_pipeline.phases import Home
from research_pipeline.project import CATALOG_PAGES, LIBRARIAN, Project
from research_pipeline.state import ENDED, FINISHED, Agent, State
from research_pipeline.tools import ToolError

__all__ = ["LIBRARIAN", "Librarian"]

#: At most this many files or links are listed in a refusal or notice.
LISTED = 30

Notify = Callable[[Agent, str], Awaitable[None]]


class Librarian:
    """Shelving requests, the Librarian's tools and the checks of its pages."""

    def __init__(
        self,
        project: Project,
        state: Callable[[], State],
        home: Callable[[], Home],
        notify: Notify,
        commit: Callable[[str], str | None],
    ):
        self.project = project
        self.state = state  # the running phase's state (replaced when it loads), the Librarian's record included
        self.home = home  # what the phases share: the Librarian's pending requests
        self.notify = notify
        self.commit = commit
        self.catalogue = Catalogue(project.research / "library.json")
        self._reported: set[str] = set()  # broken links already reported after a turn

    @property
    def agent(self) -> Agent:
        return self.state().agents[LIBRARIAN]

    def handlers(self) -> dict[str, Callable[..., Awaitable[str]]]:
        """The Librarian's tools, by name, for the controller's dispatch."""
        return {"write_page": self.write_page, "shelved": self.shelved}

    # Shelving -------------------------------------------------------------------------------------

    def folder(self, agent: Agent) -> str:
        """The agent's folder, relative to the project: its name in the catalogue and in shelving requests."""
        return self.project.relative(self.project.agent_dir(agent.id))

    def pending(self) -> list[str]:
        """The running phase's folders still awaiting the Librarian."""
        mine = self.project.folder + "/"
        return [folder for folder in self.home().shelving if folder.startswith(mine)]

    async def shelve(self, agents: list[Agent], commit: str | None) -> None:
        """Catalogue and freeze each agent's folder as committed in ``commit``, and ask the Librarian to place it."""
        state, home = self.state(), self.home()
        for agent in agents:
            about = f"{agent.role}, {agent.status}, phase {self.project.phase}"
            shelf = self.catalogue.shelve(self.project, self.project.agent_dir(agent.id), about, commit)
            self.catalogue.save(state.options.durable)
            if shelf.folder not in home.shelving:
                home.shelving.append(shelf.folder)
            await self.notify(self.agent, prompts.shelving_request(shelf.folder, about, commit, len(shelf.files)))
        with contextlib.suppress(ValueError, OSError):  # rendered again, and reported if it fails, at every commit
            self.write_catalog()  # committed with the next commit

    def frozen(self) -> list[Path]:
        """The folders no job may write: shelved ones, except those of the running phase's agents still at work."""
        live = {self.folder(agent) for agent in self.state().agents.values() if agent.status not in ENDED}
        return [self.project.root / folder for folder in self.catalogue.shelves if folder not in live]

    def write_catalog(self) -> None:
        """Render ``library/CATALOG.md`` and ``library/catalog/`` (the controller does this at every commit)."""
        state = self.state()
        finished = state.status in FINISHED
        working = {
            self.folder(agent): f"{agent.role}, {agent.status}"
            for agent in state.agents.values()
            if agent.role != "librarian"
            and agent.status not in ENDED
            and not (finished and self.folder(agent) in self.catalogue.shelves)
            and self.project.agent_dir(agent.id).is_dir()
        }
        library = self.project.library
        files = render(self.project, self.catalogue, working)
        for path, text in files.items():
            target = library / path
            if not (target.is_file() and target.read_text(encoding="utf-8", errors="replace") == text):
                atomic_write(target, text, root=self.project.root, durable=state.options.durable)

    # The Librarian's tools -----------------------------------------------------------------------

    async def write_page(self, caller: Agent, path: str, text: str) -> str:
        """Write (or, with empty text, remove) a Markdown page of ``library/``."""
        library = self.project.library
        relative = str(path).strip().removeprefix("library/")
        page = Path(os.path.normpath(library / relative))
        if not relative or Path(relative).is_absolute() or not page.is_relative_to(library) or page == library:
            raise ToolError(f"{path}: a page's path is relative to library/ and stays inside it")
        if page.suffix.lower() != ".md":
            raise ToolError(f"{path}: pages are Markdown, so the path must end in .md")
        if page == library / CATALOG or page.is_relative_to(library / CATALOG_PAGES):
            raise ToolError(f"library/{CATALOG} and library/{CATALOG_PAGES}/ are written by the controller")
        if any(part.startswith(".") for part in page.relative_to(library).parts):
            raise ToolError(f"{path}: hidden files and folders are not pages")
        if page.is_dir():
            raise ToolError(f"{path} is a folder")
        name = self.project.relative(page)
        if not text.strip():
            if not page.exists() and not page.is_symlink():
                raise ToolError(f"{name} does not exist")
            page.unlink()
            folder = page.parent
            while folder != library and not any(folder.iterdir()):
                folder.rmdir()
                folder = folder.parent
            return f"Removed {name}."
        try:
            atomic_write(page, text, root=library, durable=self.state().options.durable)
        except ValueError as error:
            raise ToolError(str(error)) from None
        broken = self._broken([page])
        return f"Wrote {name}." + (
            "\nIts links that lead nowhere:\n" + "\n".join(f"- {link}" for link in broken) if broken else ""
        )

    async def shelved(self, caller: Agent, folder: str) -> str:
        """The Librarian reports the work of ``folder`` placed: refused until its pages reach every file of it."""
        pending = self.home().shelving
        agent = str(folder).strip().strip("/")
        if agent not in pending:
            raise ToolError(f"no shelving request for {agent} is pending; pending: {', '.join(pending) or 'none'}")
        report = self.check()
        files = self.catalogue.shelves[agent].files if agent in self.catalogue.shelves else {}
        missing = [path for path in files if not report.covers(self.project.root / path)]
        problems = [f"reachable from no page: {path}" for path in missing[:LISTED]]
        if len(missing) > LISTED:
            problems.append(f"… and {len(missing) - LISTED} more files of {agent}")
        problems += [f"leads nowhere: {link}" for link in self._listed(report)]
        problems += self.project.check_layout(caller)
        if problems:
            raise ToolError(f"{agent} is not shelved yet:\n" + "\n".join(f"- {problem}" for problem in problems))
        pending.remove(agent)
        self.commit(f"librarian: shelved {agent}")
        if pending:
            return f"Shelved {agent}. Still pending: {', '.join(pending)}."
        return f"Shelved {agent}. Nothing else is pending: end your turn."

    # Its turns ------------------------------------------------------------------------------------

    def turn_ended(self) -> str | None:
        """After each of the Librarian's turns: commit the pages it changed; a notice of new broken links, if any."""
        controller = (f"library/{CATALOG}", f"library/{CATALOG_PAGES}/")
        if [path for path in self.project.uncommitted("library") if not path.startswith(controller)]:
            self.commit("librarian: library pages updated")
        broken = self._listed(self.check())
        if not broken:
            self._reported = set()
            return None
        if set(broken) == self._reported:
            return None  # reported already: it is not woken again for the same links
        self._reported = set(broken)
        return prompts.broken_links(broken)

    def check(self) -> links.Report:
        """The links of the Librarian's pages (the catalogue's aside: it reaches every file by itself)."""
        library = self.project.library
        pages = [
            path
            for path in sorted(library.rglob("*.md"))
            if path != library / CATALOG
            and not path.is_relative_to(library / CATALOG_PAGES)
            and path.is_file()
            and not any(part.startswith(".") for part in path.relative_to(library).parts)
        ]
        return links.check(pages, self.project.root, self._by_name())

    def _broken(self, pages: list[Path]) -> list[str]:
        return self._listed(links.check(pages, self.project.root, self._by_name()))

    def _listed(self, report: links.Report) -> list[str]:
        """The report's broken links as 'page: link', at most :data:`LISTED`."""
        return [f"{self.project.relative(page)}: {target}" for page, target in report.broken[:LISTED]]

    def _by_name(self) -> Callable[[str], list[Path]]:
        """Find project files by name (for wikilinks), shortest path first, as Obsidian does; listed once."""
        found: dict[str, list[Path]] | None = None

        def lookup(name: str) -> list[Path]:
            nonlocal found
            if found is None:
                found = {}
                for relative in sorted(self.project.files(), key=lambda path: (path.count("/"), path)):
                    found.setdefault(Path(relative).name, []).append(self.project.root / relative)
            return found.get(name, [])

        return lookup
