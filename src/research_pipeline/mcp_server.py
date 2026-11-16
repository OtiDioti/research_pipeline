"""The MCP tool server each agent's CLI starts: it forwards every tool call to the controller.

It runs inside the agent's confinement, as a child of the CLI, and reaches the
controller through :mod:`research_pipeline.channel`. It offers only the tools of
the agent's role (PROJECT.md §7). The docstrings below are what agents read as
tool descriptions. Configuration comes from the environment: ``RP_CHANNEL``,
``RP_AGENT``, ``RP_TOKEN`` and ``RP_ROLE``.

Run as ``python -m research_pipeline.mcp_server``.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from research_pipeline import channel


def _call(tool: str, **args) -> str:
    """Forward one tool call to the controller and return its reply."""
    request = {'agent': os.environ['RP_AGENT'], 'token': os.environ['RP_TOKEN'], 'tool': tool, 'args': args}
    try:
        return channel.call(os.environ['RP_CHANNEL'], request)
    except OSError as error:
        return f'Error: the research controller is unreachable ({error}). Try again shortly.'


def spawn(task: str, backend: str, model: str, effort: str, name: str = '') -> str:
    """Start a subagent on a task, to solve a subproblem separately or in parallel.

    task: path of a Markdown brief you wrote (objective, how it serves your question, relevant
    evidence and tools, expected result). backend, model, effort: the subagent's CLI, model and
    reasoning effort, all required. name: short id such as 'convergence-check'. You are told
    when it submits its result.
    """
    return _call('spawn', task=task, backend=backend, model=model, effort=effort, name=name)


def agents() -> str:
    """List your subagents with their status and context use."""
    return _call('agents')


def message(agent: str, text: str) -> str:
    """Message your parent or one of your own subagents; it receives the text during its turn.

    Messages are not stored: the recipient notes what matters. A subagent that has submitted
    its result receives none; accept, reject or cancel it instead.
    """
    return _call('message', agent=agent, text=text)


def accept(agent: str) -> str:
    """Accept the result a subagent submitted; it then ends."""
    return _call('accept', agent=agent)


def reject(agent: str, feedback: str) -> str:
    """Reject a subagent's submitted result; it continues with your feedback (what is missing or wrong)."""
    return _call('reject', agent=agent, feedback=feedback)


def cancel(agent: str) -> str:
    """Cancel a subagent and everything it started."""
    return _call('cancel', agent=agent)


def run_job(command: str, timeout_seconds: float, cwd: str = '') -> str:
    """Run a shell command as a job that survives your session; you are told when it ends.

    Use it for anything longer than a minute. timeout_seconds: required, any length (hours are
    fine). cwd: folder to run in (default: your folder). Output goes to your jobs/ folder.
    """
    return _call('run_job', command=command, timeout_seconds=timeout_seconds, cwd=cwd)


def job_status(job: str) -> str:
    """Show a job's status and the last lines of its output."""
    return _call('job_status', job=job)


def job_cancel(job: str) -> str:
    """Stop a job and all its processes."""
    return _call('job_cancel', job=job)


def submit_result(result: str = 'RESULT.md') -> str:
    """Submit your result (a Markdown file in your folder) to your parent; your session then ends."""
    return _call('submit_result', result=result)


def complete(report: str = 'REPORT.md') -> str:
    """Propose COMPLETE: every current question is adequately answered (or shown unanswerable) in REPORT.md.

    An independent Reviewer then examines the work; COMPLETE needs its agreement.
    """
    return _call('complete', report=report)


def stop(reason: str, final: bool = False) -> str:
    """Propose to STOP (continuing needs human intervention or is not justified), with your reason.

    The Reviewer first challenges it. Afterwards call stop(reason, final=True) to confirm, or simply continue.
    """
    return _call('stop', reason=reason, final=final)


def verdict(review: str, agree: bool) -> str:
    """Deliver your review (a Markdown file in reviews/) and whether you agree with the proposal."""
    return _call('verdict', review=review, agree=agree)


_COMMON = [spawn, agents, message, accept, reject, cancel, run_job, job_status, job_cancel]
#: Tools offered to each role.
ROLE_TOOLS = {'primary': _COMMON + [complete, stop],
              'subagent': _COMMON + [submit_result],
              'reviewer': _COMMON + [verdict]}


def main() -> None:
    server = FastMCP('research')
    for tool in ROLE_TOOLS[os.environ['RP_ROLE']]:
        server.add_tool(tool)
    server.run('stdio')


if __name__ == '__main__':
    main()
