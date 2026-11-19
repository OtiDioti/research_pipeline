"""The web page's preparation steps: the setup page before the first start, and a reopening after the end.

It is :meth:`ResearchDashboard.preparation <research_pipeline.web.ResearchDashboard.preparation>`'s
content (agent_toolkit.web's preparation contract):

- for a folder no investigation has started in: two steps, *Material* (add files,
  place them in starting_evidence/, remove and restore them) and *Objectives*
  (write starting_evidence/OBJECTIVES.md), then the launch options. The checks
  Start waits for are :meth:`Project.unready <research_pipeline.project.Project.unready>`'s,
  the same as the command line's;
- for an investigation that ended (COMPLETE or STOP), offered again while the
  program stays open for talks: *Material* again, *Instructions* (FEEDBACK.md,
  OBJECTIVES.md and AGENTS.md, one tab each), then the files changed since the end
  (each can be reverted), the checks and the launch options, and Reopen. Reopen
  waits until a file of the human's changed, the folder is ready, the Librarian
  has placed the final work and the assistant is idle (docs/FINISHING.md).

The assistant (:mod:`research_pipeline.assistant`) helps with both on request; a
reopening's assistant also reads the talks since the end, kept for it in
``.research/setup/TALKS.md``.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from agent_toolkit.activity import ActivityLog

from research_pipeline import material
from research_pipeline.assistant import Assistant, answers_text
from research_pipeline.project import Project
from research_pipeline.prompts import PROMPTS
from research_pipeline.state import Options
from research_pipeline.talks import TALKERS

if TYPE_CHECKING:
    from research_pipeline.controller import Controller

#: The documents of a reopening, with their tabs' titles.
REOPEN_DOCUMENTS = (
    ("FEEDBACK.md", "Feedback"),
    ("starting_evidence/OBJECTIVES.md", "Objectives"),
    ("AGENTS.md", "AGENTS.md"),
)


def version(text: str) -> str:
    """The version of a document's text, which an editor's save names (see :meth:`Preparation.act`)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class Preparation:
    """The preparation steps of one folder, with its assistant: before the first start, or after an end."""

    def __init__(
        self,
        project: Project,
        options: Options,
        drivers: dict,
        read_quota: Callable | None = None,
        controller: Controller | None = None,
    ):
        """``controller``: the investigation that ended, to prepare its reopening (None: the first setup)."""
        self.project, self.drivers, self.controller = project, drivers, controller
        self.reopening = controller is not None
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
            kind="reopen" if controller else "setup",
            reopening=controller.state.reopenings + 1 if controller else 0,
            facts=self._facts,
        )

    def text(self, path: str) -> str:
        """The text of a document (relative to the project), '' if it does not exist."""
        file = self.project.root / path
        return file.read_text(encoding="utf-8", errors="replace") if file.is_file() else ""

    def view(self) -> dict:
        """The preparation, as agent_toolkit.web.dashboard documents it."""
        project, assistant = self.project, self.assistant
        objectives = self.text("starting_evidence/OBJECTIVES.md")
        loose = project.stray_entries()
        evidence = project.evidence_problems()
        written = bool(objectives.strip())
        checks = [
            {
                "label": "The objectives are written",
                "ok": written,
                "detail": "starting_evidence/OBJECTIVES.md" if written else "write them in the Objectives step",
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
        if not self.reopening:
            view["steps"] = [
                material_step,
                {
                    "id": "objectives",
                    "title": "Objectives",
                    "kind": "document",
                    "help": "Say what the investigation should answer or build. Start from your ideas, let the "
                    "assistant grill you with questions if you like, and edit the draft.",
                    "done": written,
                },
            ]
            view["documents"] = [self._document("starting_evidence/OBJECTIVES.md", "OBJECTIVES.md")]
        else:
            controller = self.controller
            assert controller is not None
            changes = self.changes()
            pending = controller.state.shelving if controller.closing else []
            checks += [
                {
                    "label": "A file of yours changed since the end",
                    "ok": bool(changes),
                    "detail": "" if changes else "e.g. this reopening's section of FEEDBACK.md",
                },
                {
                    "label": "The Librarian has placed the final work",
                    "ok": not controller.closing,
                    "detail": f"still placing: {', '.join(pending)}" if controller.closing else "",
                },
                {
                    "label": "The assistant is idle",
                    "ok": not assistant.busy,
                    "detail": "it is answering your last request" if assistant.busy else "",
                },
            ]
            material_step["help"] = (
                "Add new material and place it in starting_evidence/, or remove what no longer belongs "
                "(nothing is lost); by hand or with the assistant."
            )
            view["title"] = f"Reopen the investigation in {project.root.name} ({controller.state.status.upper()})"
            view["start"] = "Reopen"
            view["steps"] = [
                material_step,
                {
                    "id": "instructions",
                    "title": "Instructions",
                    "kind": "document",
                    "help": "Say what the reopened investigation should do: this reopening's section of "
                    "FEEDBACK.md, changed objectives, standing instructions in AGENTS.md. Let the assistant grill "
                    "you and write them, or edit them yourself.",
                    "done": bool(changes),
                    "prompt": "What should the reopened investigation do? What the talks settled, what to redo or "
                    "extend, what to keep…",
                },
            ]
            view["documents"] = [self._document(path, title) for path, title in REOPEN_DOCUMENTS]
            view["changes"] = changes
        view["checks"] = checks
        view["ready"] = all(check["ok"] for check in checks) and not project.unready()
        return view

    def changes(self) -> list[dict]:
        """The human's files changed since the end, as the page lists them (reused while nothing changed)."""
        controller = self.controller
        assert controller is not None
        fingerprint = self.project.human_fingerprint()
        if self._changes is None or self._changes[0] != fingerprint:
            baseline, commit = controller.state.human, controller.state.end_commit
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
                for path in controller.human_changes()
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
            return self._save(str(args.get("path") or "starting_evidence/OBJECTIVES.md"), args)
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
        names = [name for name, _ in REOPEN_DOCUMENTS] if self.reopening else ["starting_evidence/OBJECTIVES.md"]
        if path not in names:
            raise ValueError(f"{path} is not edited here")
        if str(args.get("version") or "") != version(self.text(path)):
            raise ValueError(
                f"{Path(path).name} changed meanwhile (the assistant may have rewritten it): load it again"
            )
        text = str(args.get("text") or "")
        if path == "starting_evidence/OBJECTIVES.md":
            return material.write_objectives(self.project, text)
        self.project.write(self.project.root / path, text if text.endswith("\n") or not text else text + "\n")
        return f"Wrote {path}."

    def _revert(self, path: str | None) -> str:
        """Revert one changed file (``path``), or every one that can be (None)."""
        if not self.reopening:
            raise ValueError("there is nothing to revert before the first start")
        controller = self.controller
        assert controller is not None
        self._changes = None
        changes = self.changes()
        if path is not None and path not in {change["path"] for change in changes}:
            raise ValueError(f"{path}: not changed since the end")
        chosen = [c for c in changes if c["revert"] and (path is None or c["path"] == path)]
        done = []
        for change in sorted(chosen, key=lambda change: change["change"] != "added"):  # set aside before restoring
            if change["change"] == "added" and not (self.project.root / change["path"]).exists():
                continue  # gone with a folder an earlier revert emptied
            state = controller.state
            done.append(material.revert(self.project, state.end_commit, change["path"] in state.human, change["path"]))
        self._changes = None
        return " ".join(done) or "Nothing could be reverted."

    async def _request(self, message: str, shown: str) -> str:
        """Send a request to the assistant; a reopening's tells it first when the talks changed."""
        if self.reopening:
            talks = self._write_talks()
            if talks != self._talks and self._talks:
                message = self.assistant.text("talks", talks=self._talks_file()) + "\n\n" + message
            self._talks = talks
        return await self.assistant.request(message, shown)

    def _facts(self) -> dict[str, str]:
        """What a reopening's assistant is told of the end: the outcome, and where the talks are."""
        if not self.reopening:
            return {}
        assert self.controller is not None
        self._talks = self._write_talks()
        return {"outcome": self.controller.state.outcome or "", "talks": self._talks_file()}

    def _talks_file(self) -> str:
        return self.project.relative(self.assistant.folder / "TALKS.md")

    def _write_talks(self) -> str:
        """Write the talks with the primary and the Reviewer since the end for the assistant; return them."""
        assert self.controller is not None
        since = self.controller.state.ended or 0.0
        log = ActivityLog(self.project.research / "activity")
        lines = []
        for entry in log.read(None, limit=2000):
            if entry["agent"] not in TALKERS or entry["time"] < since or entry["kind"] != "message":
                continue
            if entry["sender"] not in ("human", "self"):
                continue
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["time"]))
            who = "The human" if entry["sender"] == "human" else entry["agent"]
            text = entry["text"].strip().removeprefix("[human] ")
            lines.append(
                f"## {stamp} — {who}{' to ' + entry['agent'] if entry['sender'] == 'human' else ''}\n\n{text}\n"
            )
        talks = "# Talks since the end\n\n" + ("\n".join(lines) or "(none yet)\n")
        self.assistant.folder.mkdir(parents=True, exist_ok=True)
        self.project.write(self.assistant.folder / "TALKS.md", talks)
        return talks
