"""Command line: ``research-pipeline run PROJECT`` and ``research-pipeline status PROJECT``.

``run`` starts a new investigation, resumes a paused or interrupted one, or reopens
a finished one. Options given on a later ``run`` replace the stored ones.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import fcntl
from pathlib import Path
import signal
import sys

from research_pipeline.controller import Controller
from agent_sessions import DRIVERS

from research_pipeline.project import Project, ProjectError
from research_pipeline.state import LIVE, Options, Spec, State


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='research-pipeline', description='Run autonomous research investigations.')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='start, resume or reopen an investigation')
    run.add_argument('project', type=Path, help='project folder (with starting_evidence/RESEARCH_QUESTIONS.md)')
    run.add_argument('--primary', help='CLI, model and effort of the primary researcher: BACKEND:MODEL:EFFORT '
                                       '(required on the first run)')
    run.add_argument('--reviewer', help='CLI, model and effort of the final Reviewer: BACKEND:MODEL:EFFORT '
                                        '(required on the first run)')
    run.add_argument('--backends', help='comma-separated CLIs agents may choose for subagents '
                                        f'(default: those of the primary and Reviewer; known: {", ".join(DRIVERS)})')
    run.add_argument('--max-agents', type=int, help='agents working at the same time (default 4)')
    run.add_argument('--reference', action='append', type=Path,
                     help='read-only folder of another project agents may consult (repeatable)')
    run.add_argument('--short-limit', type=float, help='%% left of a short usage window that pauses a CLI (default 15)')
    run.add_argument('--weekly-limit', type=float, help='%% left of a weekly window that stops a CLI (default 15)')
    run.add_argument('--context-threshold', type=float, help='context fill that triggers a handoff (default 0.55)')
    run.add_argument('--no-tui', action='store_true', help='print the transcript instead of the terminal app')
    status = commands.add_parser('status', help='show the state of an investigation')
    status.add_argument('project', type=Path)
    return parser


def options_from(args: argparse.Namespace, stored: Options | None) -> Options:
    """Merge explicit command-line options into the stored (or default) ones."""
    options = Options(**vars(stored)) if stored else Options()
    for name in ('primary', 'reviewer'):
        value = getattr(args, name)
        if value:
            Spec.parse(value, f'--{name}')
            setattr(options, name, value)
    if args.backends:
        options.backends = [name.strip() for name in args.backends.split(',') if name.strip()]
    elif stored is None and options.primary and options.reviewer:
        options.backends = sorted({Spec.parse(options.primary).backend, Spec.parse(options.reviewer).backend})
    for name, attribute in (('max_agents', 'max_agents'), ('short_limit', 'short_limit'),
                            ('weekly_limit', 'weekly_limit'), ('context_threshold', 'threshold')):
        if getattr(args, name) is not None:
            setattr(options, attribute, getattr(args, name))
    if args.reference:
        options.references = [str(path.resolve()) for path in args.reference]
    if not 0 < options.threshold <= 1:
        raise ValueError('--context-threshold must be between 0 and 1')
    return options


async def headless(controller: Controller) -> int:
    """Run without the terminal app: print the transcript; Ctrl+C shuts down cleanly, twice forces."""
    def show(kind: str, agent: str, text: str) -> None:
        marker = {'tool': '·', 'notice': '→', 'human': 'YOU', 'controller': 'CONTROLLER', 'alert': 'ALERT'}.get(kind, '')
        print(f'[{datetime.now():%H:%M:%S}] {agent} {marker}'.rstrip() + f'\n{text.rstrip()}\n', flush=True)

    controller.show = show
    task = asyncio.ensure_future(controller.run())
    loop = asyncio.get_running_loop()

    def interrupt() -> None:
        if controller.request == 'shutdown':
            task.cancel()
        else:
            print('Shutting down cleanly (agents hand off first); press Ctrl+C again to force.', flush=True)
            controller.shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, interrupt)
    try:
        return await task
    except asyncio.CancelledError:
        return 130


def controller_running(project: Project) -> bool:
    """Whether a controller is running ``project``: it holds the project's lock for as long as it runs."""
    try:
        with open(project.lock_file) as lock:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except FileNotFoundError:
        return False
    except BlockingIOError:
        return True
    return False


def show_status(project: Project) -> int:
    """Print the stored state; live agents have sessions only while a controller is running."""
    if not project.state_file.exists():
        print(f'No investigation in {project.root}.')
        return 1
    state = State.load(project.state_file)
    running = controller_running(project)
    print(f'Investigation: {state.status}' + (f' — {state.outcome}' if state.outcome else ''))
    print('Controller: ' + ('running' if running else 'not running'))
    if state.proposal:
        print(f'Proposal: {state.proposal["kind"].upper()} round {state.proposal["round"]}'
              + (' (reviewed)' if state.proposal.get('reviewed') else ''))
    for backend, hold in state.holds.items():
        print(f'Held: {backend} ({hold["kind"]}: {hold["detail"]})')
    print('\nAgents:')
    for agent in state.agents.values():
        reason = f' ({agent.pause_reason})' if agent.status == 'paused' and agent.pause_reason else ''
        print(f'  {agent.id:24} {agent.role:9} {str(agent.spec):28} {agent.status}{reason}'
              + (' [no live session: controller not running]' if agent.status in LIVE and not running else ''))
    running = state.running_jobs()
    if running:
        print('\nRunning jobs:')
        for job in running:
            print(f'  {job.id:10} {job.owner:20} {job.command[:60]}')
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project = Project(args.project)
    if args.command == 'status':
        return show_status(project)
    try:
        stored = State.load(project.state_file).options if project.state_file.exists() else None
        options = options_from(args, stored)
        controller = Controller(project.root, options)
        if args.no_tui:
            return asyncio.run(headless(controller))
        from research_pipeline.view import TerminalApp
        return asyncio.run(TerminalApp(controller).run())
    except (ProjectError, ValueError) as error:
        print(f'research-pipeline: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
