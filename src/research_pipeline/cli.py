"""Command line: ``research-pipeline run [PROJECT]``, ``status PROJECT`` and ``stats PROJECT``.

``run`` opens the web page's workbench (:mod:`research_pipeline.workbench`): every
project of this machine in its sidebar, where one is selected, created or added.
Each project starts a new investigation, resumes a paused or interrupted one, or
reopens a finished one there; its setup page first helps make the folder ready
(before the first start, even in a folder that does not exist yet) and then offers
every option. The page also starts new phases, reopens and switches between them.
The terminal prints the transcripts. A second ``run`` while the page's server runs
opens the page in the browser and exits.

``run PROJECT`` also adds that folder to the list and shows it at once; the options
for one project (the models, limits, ``--start``, ``--tui``, ``--no-web``) need it,
and given on a later ``run`` they replace the stored ones. ``--tui`` shows the
terminal app for that project instead of the printed transcripts. With
``--no-web`` there is no page: the folder must be ready already, and ``run`` runs
its latest phase (reopening it if its objectives changed since its end). ``stats``
prints the key numbers of the web page's Stats view (:mod:`research_pipeline.stats`),
read-only.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from agent_toolkit import DRIVERS, Spec
from agent_toolkit.handoff import check_threshold
from agent_toolkit.records import locked

from research_pipeline.controller import Controller
from research_pipeline.phases import Home, load_state, summaries
from research_pipeline.project import Project, ProjectError
from research_pipeline.state import ACTIVE, FINISHED, Options
from research_pipeline.stats import Statistics, summary
from research_pipeline.web import ResearchDashboard
from research_pipeline.workbench import ResearchWorkbench, home

#: The options of ``run`` that concern one project: they need PROJECT.
FOR_PROJECT = (
    "primary",
    "reviewer",
    "librarian",
    "setup",
    "writer",
    "backends",
    "max_agents",
    "reference",
    "short_limit",
    "weekly_limit",
    "context_threshold",
    "idle_limit",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-pipeline", description="Run autonomous research investigations.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="open the projects' web page, to start, resume or reopen investigations")
    run.add_argument(
        "project",
        type=Path,
        nargs="?",
        help="a project folder to add to the page's list and show at once (unless --no-web, it may be set up "
        "first); the options for one project need it",
    )
    run.add_argument(
        "--primary",
        help="CLI, model and effort of the primary researcher: BACKEND:MODEL:EFFORT "
        "(chosen on the setup page; required on the first run with --no-web)",
    )
    run.add_argument(
        "--reviewer",
        help="CLI, model and effort of the final Reviewer: BACKEND:MODEL:EFFORT "
        "(chosen on the setup page; required on the first run with --no-web)",
    )
    run.add_argument(
        "--librarian",
        help="CLI, model and effort of the Librarian, who keeps the library: BACKEND:MODEL:EFFORT "
        "(chosen on the setup page; required on the first run with --no-web)",
    )
    run.add_argument(
        "--setup",
        help="CLI, model and effort of the setup assistant, which helps make the folder ready on the setup page: "
        "BACKEND:MODEL:EFFORT (default codex:gpt-6.1-sol:high; also chosen on the page)",
    )
    run.add_argument(
        "--writer",
        help="CLI, model and effort of the Writer, who writes the reports for you and checks them: "
        "BACKEND:MODEL:EFFORT (default claude:claude-opus-5-5:high; also chosen on the page)",
    )
    run.add_argument(
        "--backends",
        help="comma-separated CLIs agents may choose for subagents "
        f"(default: those of the primary and Reviewer; known: {', '.join(DRIVERS)})",
    )
    run.add_argument(
        "--max-agents",
        type=int,
        help="agent sessions open at the same time, idle ones included (default 6, at least 2)",
    )
    run.add_argument(
        "--reference",
        action="append",
        type=Path,
        help="read-only folder of another project agents may consult (repeatable)",
    )
    run.add_argument("--short-limit", type=float, help="%% left of a short usage window that pauses a CLI (default 15)")
    run.add_argument(
        "--weekly-limit",
        type=float,
        help="%% left of a weekly window that pauses a CLI until you resume it (default 15)",
    )
    run.add_argument(
        "--context-threshold", type=float, help="context fill that triggers a handoff (default 0.55, at most 0.8)"
    )
    run.add_argument(
        "--idle-limit",
        type=float,
        metavar="MINUTES",
        help="minutes an idle session waits before it saves its handoff and closes (default 58; 0: never)",
    )
    run.add_argument(
        "--no-durable-state",
        dest="durable",
        action="store_false",
        default=None,
        help="write the state without forcing it to disk (faster on network filesystems)",
    )
    run.add_argument("--tui", action="store_true", help="show the terminal app instead of printing the transcript")
    run.add_argument(
        "--no-web", dest="web", action="store_false", help="no web page (and no setup page: the folder must be ready)"
    )
    run.add_argument("--start", action="store_true", help="skip the setup page and start at once")
    run.add_argument(
        "--web-port", type=int, metavar="PORT", help="the web page's port (default: 8780, or the next free one)"
    )
    run.add_argument(
        "--web-no-open", action="store_true", help="print the web page's address instead of opening the browser"
    )
    status = commands.add_parser("status", help="show the state of an investigation")
    status.add_argument("project", type=Path)
    stats = commands.add_parser("stats", help="summarise an investigation's statistics (read-only)")
    stats.add_argument("project", type=Path)
    stats.add_argument(
        "--phase", metavar="N", default=None, help="a phase's number, or 'all' (default: the latest phase)"
    )
    return parser


def options_from(args: argparse.Namespace, stored: Options | None) -> Options:
    """Merge explicit command-line options into the stored (or default) ones.

    Raise ValueError for an invalid CLI choice (BACKEND:MODEL:EFFORT, with an effort the CLI accepts) or a
    context threshold outside (0, 0.8].
    """
    options = Options(**vars(stored)) if stored else Options()
    for name in ("primary", "reviewer", "librarian", "setup", "writer"):
        value = getattr(args, name)
        if value:
            Spec.parse(value, f"--{name}")
            setattr(options, name, value)
    if args.backends:
        options.backends = [name.strip() for name in args.backends.split(",") if name.strip()]
    elif stored is None and options.primary and options.reviewer:
        options.backends = sorted({Spec.parse(options.primary).backend, Spec.parse(options.reviewer).backend})
    for name, attribute in (
        ("max_agents", "max_agents"),
        ("short_limit", "short_limit"),
        ("weekly_limit", "weekly_limit"),
        ("context_threshold", "threshold"),
        ("idle_limit", "idle_limit"),
    ):
        if getattr(args, name) is not None:
            setattr(options, attribute, getattr(args, name))
    if args.reference:
        options.references = [str(path.resolve()) for path in args.reference]
    if args.durable is not None:
        options.durable = args.durable
    check_threshold(options.threshold, "--context-threshold")
    if options.idle_limit < 0:
        raise ValueError("--idle-limit must be 0 (never) or a number of minutes")
    return options


async def headless(controller: Controller) -> int:
    """Run without the terminal app: print the transcript; Ctrl+C shuts down cleanly, twice forces."""
    forward = controller.show  # e.g. the web app's notifications

    def show(kind: str, agent: str, text: str) -> None:
        marker = {"tool": "·", "notice": "→", "human": "YOU", "controller": "CONTROLLER", "alert": "ALERT"}.get(
            kind, ""
        )
        print(f"[{datetime.now():%H:%M:%S}] {agent} {marker}".rstrip() + f"\n{text.rstrip()}\n", flush=True)
        forward(kind, agent, text)

    controller.show = show
    task = asyncio.ensure_future(controller.run())
    loop = asyncio.get_running_loop()

    def interrupt() -> None:
        if controller.request == "shutdown":
            task.cancel()
        else:
            print("Shutting down cleanly (agents hand off first); press Ctrl+C again to force.", flush=True)
            controller.shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, interrupt)
    try:
        return await task
    except asyncio.CancelledError:
        return 130


async def run(controller: Controller, tui: bool) -> int:
    """Run the controller in the terminal app, or without it (printing the transcript)."""
    if not tui:
        return await headless(controller)
    from research_pipeline.view import TerminalApp

    return await TerminalApp(controller).run()


async def printed(controller: Controller, project: str) -> int:
    """Run ``controller`` (of the page), printing its transcript under the project's name."""
    forward = controller.show  # the web app's notifications

    def show(kind: str, agent: str, text: str) -> None:
        marker = {"tool": "·", "notice": "→", "human": "YOU", "controller": "CONTROLLER", "alert": "ALERT"}.get(
            kind, ""
        )
        heading = f"[{datetime.now():%H:%M:%S}] {project} · {agent} {marker}".rstrip(" ·")
        print(f"{heading}\n{text.rstrip()}\n", flush=True)
        forward(kind, agent, text)

    controller.show = show
    return await controller.run()


async def workbench(args: argparse.Namespace, project: Project | None, options: Options | None) -> int:
    """Serve the workbench until Ctrl+C (or the terminal app closes), then shut every project down cleanly."""
    from agent_toolkit.web import WebApp

    stop = asyncio.Event()
    tui = project.root if project is not None and args.tui else None

    async def runner(controller: Controller, dashboard: ResearchDashboard) -> int:
        web.tap(controller, dashboard)
        try:
            if dashboard.project == tui:
                from research_pipeline.view import TerminalApp

                status = await TerminalApp(controller).run()
                stop.set()  # closing the terminal app ends the program
                return status
            if tui is not None:  # the terminal app owns the terminal: the other projects run quietly
                return await controller.run()
            return await printed(controller, workbench.name(dashboard.project))
        except ProjectError as error:
            print(f"research-pipeline: {error}", file=sys.stderr, flush=True)
            web.show("alert", "", str(error), dashboard)
            return 2

    workbench = ResearchWorkbench(home(), runner=runner)
    web = WebApp(workbench, port=args.web_port, open_browser=not args.web_no_open)
    task, interrupts = asyncio.current_task(), 0

    def interrupt() -> None:
        nonlocal interrupts
        interrupts += 1
        if interrupts == 1:
            stop.set()  # first: printing fails once the terminal is gone
            print("Shutting down cleanly (agents hand off first); press Ctrl+C again to force.", flush=True)
        elif task is not None:
            task.cancel()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, interrupt)
    try:
        if project is not None and options is not None:
            workbench.options[str(project.root)] = options
            dashboard = await workbench.select(workbench.remember(project.root))
            assert isinstance(dashboard, ResearchDashboard)
            if args.start:
                await start_now(dashboard)
        print(f"Web app: {await web.serve()}", flush=True)
        print("Pick or create a project on the page (Ctrl+C quits).", flush=True)
        await stop.wait()
        await workbench.close()  # each project's agents hand off
        return 0
    except asyncio.CancelledError:
        for dashboard in workbench.dashboards.values():  # forced: agents restart from their handoffs next time
            if isinstance(dashboard, ResearchDashboard) and dashboard.task is not None:
                dashboard.task.cancel()
        return 130
    finally:
        await web.close()


async def start_now(dashboard: ResearchDashboard) -> None:
    """``--start``: start the project with its prefilled settings, or resume its phase, without the page."""
    if dashboard.stage == "setup":
        await dashboard.start(dashboard.values())
        return
    state = load_state(dashboard.paths.at(dashboard.selected))
    if dashboard.controller is None and state is not None and state.status not in FINISHED:
        dashboard.resume(dashboard.selected)


def for_project(args: argparse.Namespace) -> list[str]:
    """The options given that concern one project (they need PROJECT)."""
    named = [f"--{name.replace('_', '-')}" for name in FOR_PROJECT if getattr(args, name) not in (None, [])]
    named += ["--no-durable-state"] if args.durable is not None else []
    named += [
        flag for flag, given in (("--start", args.start), ("--tui", args.tui), ("--no-web", not args.web)) if given
    ]
    return named


def open_page(args: argparse.Namespace) -> int:
    """``run``: serve the workbench, or open the page of the one already running."""
    flags = for_project(args)
    if args.project is None and flags:
        raise ValueError(f"{', '.join(flags)} need a PROJECT folder (or set them on the page)")
    project = Project(args.project) if args.project is not None else None
    if project is not None:
        project.check_location()
    running = ResearchWorkbench(home()).server()
    if running is not None:
        if flags:
            raise ValueError(f"the page already runs at {running}: set {', '.join(flags)} there, or quit it first")
        if project is not None:
            project.root.mkdir(parents=True, exist_ok=True)
            running += f"#/projects/{ResearchWorkbench(home()).remember(project.root)}"
        print(f"research_pipeline already runs: {running}", flush=True)
        if not args.web_no_open:
            webbrowser.open(running)
        return 0
    options = None
    if project is not None:
        project.root.mkdir(parents=True, exist_ok=True)  # a new folder is set up on the page
        state = load_state(latest(project))
        options = options_from(args, state.options if state else None)
    return asyncio.run(workbench(args, project, options))


def controller_running(project: Project) -> bool:
    """Whether a controller is running ``project``: it holds the project's lock for as long as it runs."""
    return locked(project.lock_file)


def latest(project: Project) -> Project:
    """The project bound to its latest phase (the first, before any)."""
    return project.at(Home.load(project.home_file).latest or 1)


def show_status(project: Project) -> int:
    """Print the phases and the latest one's stored state; live agents have sessions only while a controller runs."""
    home = Home.load(project.home_file)
    project = latest(project)
    state = load_state(project)
    if state is None:
        print(f"No investigation in {project.root}.")
        return 1
    running = controller_running(project)
    print("Phases:")
    for item in summaries(project, home):
        print(f"  {item.line()}" + (" ← run last" if item.number == home.active else ""))
    print(f"\nPhase {project.phase}: {state.status}" + (f" — {state.outcome}" if state.outcome else ""))
    print("Controller: " + ("running" if running else "not running"))
    if state.proposal:
        print(
            f"Proposal: {state.proposal['kind'].upper()} round {state.proposal['round']}"
            + (" (reviewed)" if state.proposal.get("reviewed") else "")
        )
    if home.shelving:
        print(f"Shelving pending (for the Librarian): {', '.join(home.shelving)}")
    for backend, hold in state.holds.items():
        print(f"Held: {backend} ({hold['kind']}: {hold['detail']})")
    print("\nAgents:")
    for agent in state.agents.values():
        reason = f" ({agent.pause_reason})" if agent.status == "paused" and agent.pause_reason else ""
        print(
            f"  {agent.id:24} {agent.role:9} {str(agent.spec):28} {agent.status}{reason}"
            + (" [no live session: controller not running]" if agent.status in ACTIVE and not running else "")
        )
    running = state.running_jobs()
    if running:
        print("\nRunning jobs:")
        for job in running:
            print(f"  {job.id:10} {job.owner:20} {job.command[:60]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "stats":
        try:
            print(summary(Statistics(args.project), args.phase), end="")
        except (ValueError, OSError) as error:
            print(f"research-pipeline: {error}", file=sys.stderr)
            return 2
        return 0
    if args.command == "status":
        return show_status(Project(args.project))
    try:
        if args.web:
            return open_page(args)
        if args.project is None:
            raise ValueError("--no-web needs a PROJECT folder")
        project = latest(Project(args.project))
        state = load_state(project)
        options = options_from(args, state.options if state else None)
        problems = project.unready() if project.root.is_dir() else [f"{project.root} does not exist."]
        if problems:
            raise ProjectError(" ".join(problems) + " Run without --no-web to set the folder up on its setup page.")
        return asyncio.run(run(Controller(project.root, options, phase=project.phase), args.tui))
    except KeyboardInterrupt:
        return 130
    except (ProjectError, ValueError, OSError) as error:
        print(f"research-pipeline: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
