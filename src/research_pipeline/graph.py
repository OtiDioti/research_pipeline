"""One phase as the web page shows it: its agent graph and its top bar (agent_toolkit.web's snapshot contract).

The running phase is shown live (its sessions, the human's actions on its agents);
any other phase as it was left, from its stored state, with only talks with its
primary and Reviewer. The Librarian, which serves every phase, is shown in each.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from agent_toolkit import Session
from agent_toolkit.web import edge, node

from research_pipeline.project import INDEX, LIBRARIAN, Project
from research_pipeline.state import ENDED, FINISHED, Agent, State

if TYPE_CHECKING:
    from research_pipeline.controller import Controller
    from research_pipeline.web import ResearchDashboard

#: How the page colours an agent, by status (paused agents by their pause reason, see :data:`PAUSED`).
COLOURS = {
    "handing_off": "handing_off",
    "submitted": "submitted",
    "resting": "idle",
    "accepted": "finished",
    "finished": "finished",
    "cancelled": "cancelled",
}
PAUSED: dict[str | None, str] = {"quota": "held", "held": "paused", "human": "paused", "failure": "failed"}
#: Job statuses as the page colours them.
JOBS = {"running": "working", "finished": "finished", "cancelled": "cancelled"}
#: Documents first in an agent's "Task & notes", in this order.
FIRST = ("TASK.md", "HANDOFF.md", "RESULT.md", "PARENT_FEEDBACK.md", "OBJECTIVES.md", "STATUS.md", "REPORT.md")
#: Seconds the listing of agents' folders is reused before being read again.
LISTING_TTL = 3.0


def build(
    state: State,
    documents: dict[str, list[str]],
    used: dict[str, dict[str, set]],
    number: int,
    *,
    sessions: dict[str, Session],
    actions: Callable[[Agent], list[str]],
    librarian: Agent | None,
    paths: Project,
) -> dict:
    """The graph of phase ``number``: its agents (and ``librarian``, if not among them), jobs, files and sites."""
    agents = list(state.agents.values())
    if librarian is not None and LIBRARIAN not in state.agents:
        agents.append(librarian)
    nodes, edges = [], []
    for agent in agents:
        listed = documents.get(agent.id, [])
        nodes.append(_agent(agent, listed, sessions.get(agent.id), actions(agent), state.options.threshold))
        if agent.parent:
            edges.append(edge(agent.parent, agent.id, "child"))
            verdict = (
                "submitted"
                if agent.status == "submitted"
                else "accepted"
                if agent.status == "accepted"
                else "rejected"
                if agent.rejections and agent.status not in ENDED
                else None
            )
            if verdict:
                edges.append(edge(agent.id, agent.parent, "result", verdict))
        for path in listed:
            nodes.append(node(f"file:{path}", "file", Path(path).name, owners=[agent.id], path=path))
        mine = used.get(agent.id if agent.id == LIBRARIAN else f"{number}/{agent.id}", {})
        for url in sorted(mine.get("sites", ())):
            nodes.append(node(f"site:{url}", "site", url.split("/")[2], owners=[agent.id], url=url))
        for path in sorted(mine.get("pages", ())):
            nodes.append(node(f"file:{path}", "file", Path(path).name, owners=[agent.id], path=path))
    if state.verdict and "reviewer" in state.agents:
        edges.append(edge("reviewer", "primary", "result", state.verdict))
    for job in state.jobs.values():
        nodes.append(
            node(
                f"job:{job.id}",
                "job",
                job.id,
                owners=[job.owner],
                status=JOBS.get(job.status, "failed"),
                detail=f"{job.status}: {job.command.strip()[:200]}",
                path=str(paths.agent_dir(job.owner) / "jobs" / job.id / "stdout.log"),
            )
        )
    merged: dict[str, dict] = {}
    for item in nodes:  # a source used by two agents appears once, owned by both
        if item["id"] in merged and item["kind"] != "agent":
            merged[item["id"]]["owners"] = sorted({*merged[item["id"]]["owners"], *item["owners"]})
        else:
            merged[item["id"]] = item
    nodes = list(merged.values())
    edges += [edge(owner, item["id"], "owns") for item in nodes if item["kind"] != "agent" for owner in item["owners"]]
    return {"nodes": nodes, "edges": edges}


def _agent(agent: Agent, documents: list[str], session: Session | None, actions: list[str], threshold: float) -> dict:
    if agent.status == "running":
        colour = detail = "working" if session and session.busy else "idle"
    elif agent.status == "paused":
        colour, detail = PAUSED.get(agent.pause_reason, "waiting"), f"paused ({agent.pause_reason})"
    else:
        colour, detail = COLOURS.get(agent.status, "idle"), agent.status
    if session and agent.status != "running":
        detail += ", session kept"  # it waits in its session (which occupies a slot) until the idle limit
    return node(
        agent.id,
        "agent",
        agent.id,
        parent=agent.parent,
        role=agent.role,
        status=colour,
        detail=detail,
        backend=agent.backend,
        model=agent.model,
        effort=agent.effort,
        fill=agent.fill,
        tokens=agent.tokens,
        window=agent.window,
        threshold=threshold,
        activity=agent.activity,
        sessions=agent.sessions,
        ended=agent.status in ENDED,
        actions=actions,
        documents=documents,
    )


def status(
    dashboard: ResearchDashboard, controller: Controller, number: int, state: State, *, live: bool, preparable: bool
) -> dict:
    """The top bar for phase ``number``: the running one's controls (``live``), else what can be done with it."""
    running = controller.state
    name = f"Phase {number}"
    summary = f"{len(controller.sessions)}/{state.options.max_agents} sessions" if live else ""
    if state.proposal:
        summary += f" · {state.proposal['kind'].upper()} proposal, round {state.proposal['round']}"
    if state.outcome:
        summary = state.outcome
    started = bool(state.agents)
    ended = state.status in FINISHED
    if live:
        held = state.status in ("paused", "pausing")
        controls = (
            [{"action": "prepare", "label": "Prepare reopening", "confirm": None}]
            if ended and preparable
            else []
            if ended
            else [{"action": "pause", "label": "Resume" if held else "Pause", "confirm": None}]
        )
        if controller.releasable:
            controls.append({"action": "release", "label": "Resume held", "confirm": None})
        composer = (
            f"Talk with {name}'s primary researcher (it has ended)" if ended else f"Message {name}'s primary researcher"
        )
    else:
        controls = (
            [{"action": "prepare", "label": "Prepare reopening", "confirm": None}]
            if ended
            else [{"action": "resume_phase", "label": f"Resume {name.lower()}", "confirm": None}]
            if state.status == "paused"
            else [{"action": "prepare", "label": f"Prepare {name.lower()}", "confirm": None}]
            if not started
            else []
        )
        summary = summary or ("not started" if not started else state.status)
        composer = f"Talk with {name}'s primary researcher (talk only: it does not run)"
    finished = running.status in FINISHED
    controls.append(
        {
            "action": "shutdown",
            "label": "Quit" if finished else "Shut down",
            "confirm": "The talks save their notes, then the program ends. Quit?"
            if finished
            else "Every agent saves its handoff, then the program ends (jobs keep running). Shut down?",
        }
    )
    return {
        "program": dashboard.program,
        "project": dashboard.project.name,
        "state": f"{name.lower()}: {state.status if started else 'not started'}",
        "summary": summary,
        "quota": [
            {
                "backend": window.backend,
                "minutes": window.minutes,
                "left": round(100 - window.used, 1),
                "resets_at": window.resets_at,
                "held": window.backend in running.holds,
            }
            for window in controller.windows
        ],
        "controls": controls,
        "composer": {"target": "primary", "label": composer},
    }


def documents(paths: Project, state: State) -> dict[str, list[str]]:
    """Each agent's documents (its folder's files, the primary's objectives, status and report, the reviews)."""
    listing = {}
    agents = [*state.agents.values()]
    if LIBRARIAN not in state.agents:
        agents.append(Agent(LIBRARIAN, "librarian", None, "", "", ""))
    for agent in agents:
        folder = paths.agent_dir(agent.id)
        found = [path for path in folder.glob("*") if path.is_file() and path.name != INDEX] if folder.is_dir() else []
        if agent.role == "primary":
            found += [path for path in (paths.objectives, paths.status_file, paths.report) if path.is_file()]
        if agent.role == "reviewer":
            found += [path for path in paths.reviews.glob("*.md") if path.name != INDEX]
        if agent.role == "librarian":
            found += [path for path in paths.library.glob("*.md") if path.name != INDEX]
        order = {name: rank for rank, name in enumerate(FIRST)}
        listing[agent.id] = [
            str(path) for path in sorted(found, key=lambda path: (order.get(path.name, 99), path.name))
        ]
    return listing
