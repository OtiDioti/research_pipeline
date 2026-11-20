"""The web page's preparation of a phase: the first one, a new one, or the reopening of one that ended.

It is :meth:`ResearchDashboard.preparation <research_pipeline.web.ResearchDashboard.preparation>`'s
content (agent_toolkit.web's preparation contract), for one phase (``kind``):

- 'setup', the first phase of a folder no investigation has started in: two steps,
  *Material* (add files, place them in starting_evidence/, remove and restore them)
  and *Objectives* (write the phase's OBJECTIVES.md), then the launch options. The
  checks Start waits for are :meth:`Project.unready <research_pipeline.project.Project.unready>`'s,
  the same as the command line's;
- 'phase', a new phase: *Material* again, *Objectives* (its OBJECTIVES.md, and
  AGENTS.md in a second tab), then its title, the phase it builds on and the launch
  options. Start waits until the folder is ready, the assistant is idle and no
  other phase runs;
- 'reopen', a phase that ended (COMPLETE or STOP): *Material* again,
  *Instructions* (its OBJECTIVES.md and AGENTS.md), then the files changed since
  its end (each can be reverted), the checks and the launch options, and Reopen.
  Reopen waits until the phase's objectives changed, the folder is ready, the
  Librarian has placed the phase's final work, the assistant is idle and no other
  phase runs (docs/FINISHING.md).

The assistant (:mod:`research_pipeline.assistant`) helps with each on request; a
reopening's assistant also reads the talks since the phase's end, and a new
phase's those with the earlier phases, kept for it in its folder's TALKS.md.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path

from agent_toolkit.activity import ActivityLog

from research_pipeline import material, phases
from research_pipeline.assistant import Assistant, answers_text
from research_pipeline.phases import Home, load_state
from research_pipeline.project import Project
from research_pipeline.prompts import PROMPTS
from research_pipeline.state import Options, State
from research_pipeline.talks import TALKERS

#: Further checks the page supplies (e.g. that no other phase runs), as agent_toolkit.web's checks.
Checks = Callable[[], list[dict]]


def version(text: str) -> str:
    """The version of a document's text, which an editor's save names (see :meth:`Preparation.act`)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class Preparation:
    """The preparation of one phase (``project``'s), with its assistant."""

    def __init__(
        self,
        project: Project,
        options: Options,
        drivers: dict,
        read_quota: Callable | None = None,
        *,
        kind: str = "setup",
        title: str = "",
        state: Callable[[], State | None] | None = None,
        checks: Checks = list,
    ):
        """``kind``: 'setup', 'phase' or 'reopen' (see the module); ``title``: the phase's.

        ``state`` gives the phase's state as it is now (a reopening's: how and when it
        ended); ``checks`` the further checks Start waits for.
        """
        self.project, self.drivers, self.kind, self.title = project, drivers, kind, title
        self.reopening = kind == "reopen"
        self.state = state or (lambda: load_state(project))
        self.checks = checks
        self._talks = ""  # the talks last written for the assistant
        self._changes: tuple[dict[str, str], list[dict]] | None = None  # the human's fingerprint, its changes
        self.assistant = Assistant(
            project,
            options.setup,
            threshold=options.threshold,
            short_limit=options.short_limit,
            weekly_limit=options.weekly_limit,
            drivers=drivers,
            read_quota=read_quota,
            kind=kind,
            facts=self._facts,
        )

    @property
    def objectives(self) -> str:
        """The phase's OBJECTIVES.md, relative to the project."""
        return self.project.relative(self.project.objectives)

    @property
    def documents(self) -> list[tuple[str, str]]:
        """The documents the human edits, with their tabs' titles."""
        if self.kind == "setup":
            return [(self.objectives, "OBJECTIVES.md")]
        return [(self.objectives, "Objectives"), ("AGENTS.md", "AGENTS.md")]

    def text(self, path: str) -> str:
        """The text of a document (relative to the project), '' if it does not exist."""
        file = self.project.root / path
        return file.read_text(encoding="utf-8", errors="replace") if file.is_file() else ""

    def view(self) -> dict:
        """The preparation, as agent_toolkit.web.dashboard documents it."""
        project, assistant = self.project, self.assistant
        objectives = self.text(self.objectives)
        loose = project.stray_entries()
        evidence = project.evidence_problems()
        written = bool(objectives.strip())
        checks = [
            {
                "label": "The objectives are written",
                "ok": written,
                "detail": self.objectives if written else "write them in the Objectives step",
            },
            {
                "label": "No loose material at the top level",
                "ok": not loose,
                "detail": ", ".join(loose) if loose else "",
            },
            {
                "label": "Everything in starting_evidence/ is described",
                "ok": not evidence,
                "detail": " ".join(evidence),
            },
        ]
        material_step = {
            "id": "material",
            "title": "Material",
            "kind": "files",
            "help": "Add papers, notes, data and code, then give each a place in starting_evidence/ "
            "and a one-line description, by hand or with the assistant. Remove what does not belong: "
            "nothing is lost.",
            "done": not loose and not evidence,
        }
        view = {
            "files": {
                "target": material.TARGET,
                "entries": material.entries(project),
                "folders": material.folders(project),
                "removed": material.removed(project),
            },
            "assistant": {
                "spec": assistant.spec,
                "options": list(self.drivers),
                "state": assistant.state,
                "detail": assistant.detail,
                "ideas": not assistant.questions and not (assistant.briefed if self.reopening else written),
            },
            "conversation": assistant.conversation[-200:],
            "questions": assistant.questions,
        }
        objectives_step = {
            "id": "objectives",
            "title": "Objectives",
            "kind": "document",
            "help": "Say what the investigation should answer or build. Start from your ideas, let the "
            "assistant grill you with questions if you like, and edit the draft.",
            "done": written,
        }
        if self.kind != "setup":
            checks.append(
                {
                    "label": "The assistant is idle",
                    "ok": not assistant.busy,
                    "detail": "it is answering your last request" if assistant.busy else "",
                }
            )
            material_step["help"] = (
                "Add new material and place it in starting_evidence/, or remove what no longer belongs "
                "(nothing is lost); by hand or with the assistant."
            )
        if self.kind == "phase":
            number = project.phase
            view["title"] = f"Prepare phase {number}: {self.title}" if self.title else f"Prepare phase {number}"
            view["start"] = f"Start phase {number}"
            objectives_step["help"] = (
                "Say what this phase should answer or build, building on the earlier phases. Let the assistant "
                "grill you and draft it, or write it yourself; AGENTS.md (every phase's) is in the second tab."
            )
            objectives_step["prompt"] = "Where should the new phase go? What to build on, what to leave behind…"
        if self.kind == "reopen":
            state = self.state()
            changes = self.changes()
            changed = self.objectives in {change["path"] for change in changes}
            checks.insert(
                0,
                {
                    "label": "The phase's objectives changed since its end",
                    "ok": changed,
                    "detail": "" if changed else f"only a change of {self.objectives} reopens it",
                },
            )
            outcome = state.status.upper() if state else ""
            view["title"] = f"Reopen phase {project.phase}: {self.title} ({outcome})"
            view["start"] = "Reopen"
            objectives_step |= {
                "id": "instructions",
                "title": "Instructions",
                "help": "Say what the reopened phase should do, as changed objectives (and, if you like, standing "
                "instructions in AGENTS.md). Let the assistant grill you and write them, or edit them yourself.",
                "done": changed,
                "prompt": "What should the reopened phase do? What the talks settled, what to redo or extend, what "
                "to keep…",
            }
            view["changes"] = changes
        view["steps"] = [material_step, objectives_step]
        view["documents"] = [self._document(path, title) for path, title in self.documents]
        checks += self.checks()
        view["checks"] = checks
        view["ready"] = all(check["ok"] for check in checks) and not project.unready()
        return view

    def changes(self) -> list[dict]:
        """The human's files changed since the phase's end, as the page lists them (reused while nothing changed)."""
        state = self.state()
        if state is None:
            return []
        fingerprint = self.project.human_fingerprint()
        if self._changes is None or self._changes[0] != fingerprint:
            baseline, commit = state.human, state.end_commit
            listed = [
                {
                    "path": path,
                    "change": "added"
                    if path not in baseline
                    else "removed"
                    if not (self.project.root / path).exists()
                    else "modified",
                    "revert": material.reverting(self.project, commit, path in baseline, path),
                }
                for path in self.project.human_changes(baseline, commit)
            ]
            self._changes = (fingerprint, listed)
        return self._changes[1]

    async def act(self, action: str, args: dict) -> str:
        """Do one of agent_toolkit.web's PREPARE_ACTIONS; raise ValueError with a message for the human."""
        project, assistant = self.project, self.assistant
        if action == "rescan":
            return "Rescanned."
        if action == "import":
            return material.import_paths(project, [str(path) for path in args.get("paths") or []])
        if action == "place":
            return material.place(project, list(args.get("entries") or []), list(args.get("folders") or []))
        if action == "remove":
            return material.remove(project, str(args.get("path") or ""))
        if action == "restore":
            return material.restore(project, str(args.get("id") or ""))
        if action == "save":
            return self._save(str(args.get("path") or self.objectives), args)
        if action in ("revert", "discard"):
            return self._revert(None if action == "discard" else str(args.get("path") or ""))
        if action == "assistant":
            assistant.set_spec(str(args.get("spec") or ""))
            return "The assistant's CLI is changed."
        if action == "organise":
            loose = [entry for entry in material.entries(project) if entry["state"] == "loose"]
            if not loose:
                raise ValueError("nothing is loose")
            listing = "\n".join(f"- {entry['path']}{'/' if entry['folder'] else ''}" for entry in loose)
            return await self._request(assistant.text("organise", loose=listing), "Place the loose material.")
        if action == "ideas":
            ideas = str(args.get("text") or "").strip()
            if not ideas:
                raise ValueError("write your ideas first")
            name = "ideas-grill" if args.get("grill") else "ideas-draft"
            sent = await self._request(assistant.text(name, ideas=ideas), ideas)
            assistant.briefed = True
            return sent
        if action == "answer":
            questions = assistant.questions
            if not questions or args.get("id") != questions["id"]:
                raise ValueError("these questions are no longer open")
            answers = answers_text(questions, list(args.get("answers") or []))
            return await self._request(assistant.text("answers", answers=answers), answers)
        if action == "draft":
            shown = "Enough questions: write it now."
            return await self._request(assistant.text("draft"), shown)
        if action == "message":
            text = str(args.get("text") or "").strip()
            if not text:
                raise ValueError("the message is empty")
            return await self._request(assistant.text("message", text=text), text)
        raise ValueError(f"{action} is not a preparation step")

    def upload(self, path: str) -> Path:
        return material.upload_target(self.project, path)

    async def close(self, finished: bool = False) -> None:
        await self.assistant.close(finished)

    # Helpers ------------------------------------------------------------------------------------------

    def _document(self, path: str, title: str) -> dict:
        text = self.text(path)
        template = PROMPTS.text("objectives-template") + "\n" if path.endswith("OBJECTIVES.md") else ""
        return {"path": path, "title": title, "text": text, "version": version(text), "template": template}

    def _save(self, path: str, args: dict) -> str:
        if path not in [name for name, _ in self.documents]:
            raise ValueError(f"{path} is not edited here")
        if str(args.get("version") or "") != version(self.text(path)):
            raise ValueError(
                f"{Path(path).name} changed meanwhile (the assistant may have rewritten it): load it again"
            )
        text = str(args.get("text") or "")
        if path == self.objectives:
            return material.write_objectives(self.project, text)
        self.project.write(self.project.root / path, text if text.endswith("\n") or not text else text + "\n")
        return f"Wrote {path}."

    def _revert(self, path: str | None) -> str:
        """Revert one changed file (``path``), or every one that can be (None)."""
        state = self.state()
        if not self.reopening or state is None:
            raise ValueError("there is nothing to revert here")
        self._changes = None
        changes = self.changes()
        if path is not None and path not in {change["path"] for change in changes}:
            raise ValueError(f"{path}: not changed since the end")
        chosen = [c for c in changes if c["revert"] and (path is None or c["path"] == path)]
        done = []
        for change in sorted(chosen, key=lambda change: change["change"] != "added"):  # set aside before restoring
            if change["change"] == "added" and not (self.project.root / change["path"]).exists():
                continue  # gone with a folder an earlier revert emptied
            done.append(material.revert(self.project, state.end_commit, change["path"] in state.human, change["path"]))
        self._changes = None
        return " ".join(done) or "Nothing could be reverted."

    async def _request(self, message: str, shown: str) -> str:
        """Send a request to the assistant; a reopening's or a new phase's tells it first when the talks changed."""
        if self.kind != "setup":
            talks = self._write_talks()
            if talks != self._talks and self._talks:
                message = self.assistant.text("talks", talks=self._talks_file()) + "\n\n" + message
            self._talks = talks
        return await self.assistant.request(message, shown)

    def _facts(self) -> dict[str, str]:
        """What the assistant is told: a reopening's outcome, a new phase's earlier phases, and where the talks are.

        The talks themselves are written before each request (see :meth:`_request`).
        """
        if self.kind == "setup":
            return {}
        if self.reopening:
            state = self.state()
            return {"outcome": (state.outcome if state else "") or "", "talks": self._talks_file()}
        earlier = [item for item in self._phases() if item.number < self.project.phase]
        return {"phases": phases.listing(earlier), "talks": self._talks_file()}

    def _phases(self) -> list[phases.Summary]:
        return phases.summaries(self.project, Home.load(self.project.home_file))

    def _talks_file(self) -> str:
        return self.project.relative(self.assistant.folder / "TALKS.md")

    def _write_talks(self) -> str:
        """Write the talks for the assistant (this phase's since its end, or every earlier phase's); return them."""
        if self.reopening:
            numbers = [self.project.phase]
        else:
            numbers = [item.number for item in self._phases() if item.number < self.project.phase]
        lines = []
        for number in numbers:
            project, state = self.project.at(number), load_state(self.project.at(number))
            if state is None or state.ended is None:
                continue
            log = ActivityLog(project.activity)
            for entry in log.read(None, limit=2000):
                if entry["agent"] not in TALKERS or entry["time"] < state.ended or entry["kind"] != "message":
                    continue
                if entry["sender"] not in ("human", "self"):
                    continue
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["time"]))
                who = "The human" if entry["sender"] == "human" else entry["agent"]
                to = f" to {entry['agent']}" if entry["sender"] == "human" else ""
                text = entry["text"].strip().removeprefix("[human] ")
                lines.append(f"## {stamp}, phase {number} — {who}{to}\n\n{text}\n")
        heading = "# Talks since the phase's end" if self.reopening else "# Talks with the earlier phases"
        talks = f"{heading}\n\n" + ("\n".join(lines) or "(none yet)\n")
        self.assistant.folder.mkdir(parents=True, exist_ok=True)
        self.project.write(self.assistant.folder / "TALKS.md", talks)
        return talks
