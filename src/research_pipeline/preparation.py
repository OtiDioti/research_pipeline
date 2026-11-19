"""The web setup's preparation steps: what the setup page shows and does before the first start (docs/SETUP.md).

It is :meth:`ResearchDashboard.preparation <research_pipeline.web.ResearchDashboard.preparation>`'s
content (agent_toolkit.web's preparation contract) for a folder no investigation
has started in: two steps, *Material* (add files, place them in
starting_evidence/, remove and restore them) and *Objectives* (write
starting_evidence/OBJECTIVES.md),
then the launch options. The setup assistant (:mod:`research_pipeline.assistant`)
helps with both on request; the checks Start waits for are
:meth:`Project.unready <research_pipeline.project.Project.unready>`'s, the same
as the command line's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from research_pipeline import material
from research_pipeline.assistant import Assistant, answers_text, request_text
from research_pipeline.project import Project
from research_pipeline.prompts import PROMPTS
from research_pipeline.state import Options


def version(text: str) -> str:
    """The version of the objectives' text, which an editor's save names (see :meth:`Preparation.act`)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class Preparation:
    """The preparation steps of one folder, with its setup assistant."""

    def __init__(self, project: Project, options: Options, drivers: dict, read_quota: Callable | None = None):
        self.project, self.drivers = project, drivers
        self.assistant = Assistant(
            project,
            options.setup,
            threshold=options.threshold,
            short_limit=options.short_limit,
            weekly_limit=options.weekly_limit,
            drivers=drivers,
            read_quota=read_quota,
        )

    def objectives(self) -> str:
        path = self.project.objectives
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    def view(self) -> dict:
        """The preparation, as agent_toolkit.web.dashboard documents it."""
        project, text = self.project, self.objectives()
        loose = project.stray_entries()
        evidence = project.evidence_problems()
        written = bool(text.strip())
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
        assistant = self.assistant
        return {
            "steps": [
                {
                    "id": "material",
                    "title": "Material",
                    "kind": "files",
                    "help": "Add papers, notes, data and code, then give each a place in starting_evidence/ "
                    "and a one-line description, by hand or with the assistant. Remove what does not belong: "
                    "nothing is lost.",
                    "done": not loose and not evidence,
                },
                {
                    "id": "objectives",
                    "title": "Objectives",
                    "kind": "document",
                    "help": "Say what the investigation should answer or build. Start from your ideas, let the "
                    "assistant grill you with questions if you like, and edit the draft.",
                    "done": written,
                },
            ],
            "files": {
                "target": material.TARGET,
                "entries": material.entries(project),
                "folders": material.folders(project),
                "removed": material.removed(project),
            },
            "document": {
                "path": "starting_evidence/OBJECTIVES.md",
                "text": text,
                "version": version(text),
                "template": PROMPTS.text("objectives-template") + "\n",
            },
            "assistant": {
                "spec": assistant.spec,
                "options": list(self.drivers),
                "state": assistant.state,
                "detail": assistant.detail,
            },
            "conversation": assistant.conversation[-200:],
            "questions": assistant.questions,
            "checks": checks,
            "ready": all(check["ok"] for check in checks) and not project.unready(),
        }

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
            if str(args.get("version") or "") != version(self.objectives()):
                raise ValueError("OBJECTIVES.md changed meanwhile (the assistant may have rewritten it): load it again")
            return material.write_objectives(project, str(args.get("text") or ""))
        if action == "assistant":
            assistant.set_spec(str(args.get("spec") or ""))
            return "The assistant's CLI is changed."
        if action == "organise":
            loose = [entry for entry in material.entries(project) if entry["state"] == "loose"]
            if not loose:
                raise ValueError("nothing is loose")
            listing = "\n".join(f"- {entry['path']}{'/' if entry['folder'] else ''}" for entry in loose)
            return await assistant.request(request_text("organise", loose=listing), "Place the loose material.")
        if action == "ideas":
            ideas = str(args.get("text") or "").strip()
            if not ideas:
                raise ValueError("write your ideas first")
            name = "ideas-grill" if args.get("grill") else "ideas-draft"
            return await assistant.request(request_text(name, ideas=ideas), ideas)
        if action == "answer":
            questions = assistant.questions
            if not questions or args.get("id") != questions["id"]:
                raise ValueError("these questions are no longer open")
            answers = answers_text(questions, list(args.get("answers") or []))
            return await assistant.request(request_text("answers", answers=answers), answers)
        if action == "draft":
            return await assistant.request(request_text("draft"), "Enough questions: draft the objectives now.")
        if action == "message":
            text = str(args.get("text") or "").strip()
            if not text:
                raise ValueError("the message is empty")
            return await assistant.request(request_text("message", text=text), text)
        raise ValueError(f"{action} is not a preparation step")

    def upload(self, path: str) -> Path:
        return material.upload_target(self.project, path)

    async def close(self, finished: bool = False) -> None:
        await self.assistant.close(finished)
