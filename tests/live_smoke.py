"""Live smoke run (PROJECT.md §9, item 2): a small public investigation through the real CLIs.

Not part of the unit tests: it uses real model sessions and costs usage. Run it with

    uv run python -m tests.live_smoke [--primary codex:gpt-6.1-sol:low] [--reviewer claude:haiku:low]

It shows spawning across CLIs, a rejected then accepted result, a job, handoffs
forced by a lowered context threshold, a quota pause (a short window of one CLI is
reported exhausted for a minute, on top of the real readings), optionally a human
pause with edits while paused (``--pause-at``), and the Reviewer exchange ending in
COMPLETE or STOP. The science and the agreement are the agents'
own; only the threshold and the one quota reading are artificial. The transcript
and a final summary are printed; the project is kept under ~/.cache for inspection.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import shutil
import time

from agent_sessions import DRIVERS, quota

from research_pipeline import controller as controller_module
from research_pipeline.controller import Controller
from research_pipeline.state import Options

ROOT = Path.home() / '.cache' / 'research-pipeline-smoke'
QUESTION = """# Research question

Compute the integral I = ∫₀¹ x² e^(−x) dx exactly, and confirm the exact value numerically to at least
10 significant digits with an independent method.
"""
PROCEDURE = """# Instructions for this investigation

This is a short engineering smoke test of the research platform; keep the science brief but rigorous.
Follow this procedure:

1. Derive the exact value yourself.
2. Delegate the numerical confirmation to one subagent with spawn, on backend {sub}, model {sub_model} and
   effort {sub_effort}, asking it to run its computation with run_job.
3. Reject the subagent's first result once, asking it to state the absolute error against your exact value;
   accept its second result if it is sound.
4. Write REPORT.md and propose complete.
"""


class SimulatedQuota:
    """Real quota readings, except that ``backend``'s short window reads exhausted for ``seconds`` once."""

    def __init__(self, backend: str, after: float, seconds: float):
        self.backend, self.start, self.end = backend, time.time() + after, time.time() + after + seconds

    def __call__(self, backend: str) -> list[quota.Window]:
        windows = quota.read(DRIVERS[backend])
        if backend == self.backend and self.start <= time.time() < self.end:
            print(f'[smoke] reporting {backend} short window as exhausted until {self.end - time.time():.0f} s',
                  flush=True)
            windows = [w for w in windows if w.weekly] + [quota.Window(backend, 300, 95.0, self.end)]
        return windows


async def human_pause(controller: Controller, at: float) -> None:
    """Pause like the human at ``at`` seconds, edit files while paused, then resume."""
    await asyncio.sleep(at)
    print('[smoke] human pause requested', flush=True)
    controller.toggle_pause()
    for _ in range(600):
        await asyncio.sleep(1)
        if controller.state.status == 'paused':
            break
    else:
        print('[smoke] the pause did not complete within 10 minutes', flush=True)
        return
    root = controller.project.root
    (root / 'FEEDBACK.md').write_text('Please also state the value to 12 significant digits in REPORT.md.\n')
    status = root / 'STATUS.md'
    status.write_text(status.read_text() + '\nHuman note (edited while paused): keep the report short.\n')
    print('[smoke] edited FEEDBACK.md and STATUS.md while paused; resuming', flush=True)
    controller.toggle_pause()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--primary', default='codex:gpt-6.1-sol:low', help='BACKEND:MODEL:EFFORT')
    parser.add_argument('--reviewer', default='claude:haiku:low', help='BACKEND:MODEL:EFFORT')
    parser.add_argument('--sub', default='claude', help='backend the subagent must use')
    parser.add_argument('--sub-model', default='haiku')
    parser.add_argument('--sub-effort', default='low')
    parser.add_argument('--threshold', type=float, default=0.06)
    parser.add_argument('--quota-after', type=float, default=240, help='seconds before the simulated quota hold')
    parser.add_argument('--pause-at', type=float, help='seconds before a human pause and resume (default: none)')
    parser.add_argument('--limit', type=float, default=3600, help='seconds before giving up')
    args = parser.parse_args()

    root = ROOT / datetime.now().strftime('%Y%m%d-%H%M%S')
    (root / 'starting_evidence').mkdir(parents=True)
    (root / 'starting_evidence' / 'RESEARCH_QUESTIONS.md').write_text(QUESTION)
    (root / 'AGENTS.md').write_text(PROCEDURE.format(sub=args.sub, sub_model=args.sub_model, sub_effort=args.sub_effort))
    print(f'[smoke] project: {root}', flush=True)

    def show(kind: str, agent: str, text: str) -> None:
        marker = {'tool': '·', 'notice': '→', 'human': 'YOU', 'controller': 'CONTROLLER', 'alert': 'ALERT'}.get(kind, '')
        text = text if len(text) < 1500 else text[:1500] + ' […]'
        print(f'[{datetime.now():%H:%M:%S}] {agent} {marker}'.rstrip() + f'\n{text.rstrip()}\n', flush=True)

    controller_module.QUOTA_INTERVAL = 20
    options = Options(primary=args.primary, reviewer=args.reviewer, backends=sorted({'codex', 'claude'}),
                      max_agents=3, threshold=args.threshold)
    controller = Controller(root, options, read_quota=SimulatedQuota(args.sub, args.quota_after, 60), show=show)
    pausing = asyncio.ensure_future(human_pause(controller, args.pause_at)) if args.pause_at else None
    try:
        await asyncio.wait_for(controller.run(), args.limit)
    except asyncio.TimeoutError:
        print('[smoke] time limit reached: shutting down', flush=True)
    if pausing:
        pausing.cancel()
    state = controller.state
    print('\n[smoke] ===== SUMMARY =====')
    print(f'status: {state.status}; outcome: {state.outcome}')
    for agent in state.agents.values():
        print(f'  {agent.id:20} {str(agent.spec):24} {agent.status:10} sessions={agent.sessions} '
              f'rejections={agent.rejections}')
    for job in state.jobs.values():
        print(f'  {job.id} ({job.owner}): {job.status}, exit {job.exit_code}')
    print(controller.project.git('log', '--oneline'))
    print(f'project kept at {root}')


if __name__ == '__main__':
    shutil.which('bwrap') or exit('bwrap is required')
    asyncio.run(main())
