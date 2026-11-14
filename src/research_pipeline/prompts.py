"""Everything the controller says to agents: role instructions, opening messages and notices.

Role instructions come from the Markdown files in ``prompts/`` (one shared part,
one part per role). Notices are short and always start with ``[controller]`` (or
``[human]`` for the human's messages), as the instructions announce.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from string import Template

from research_pipeline.project import Project
from research_pipeline.state import Agent, Options

TITLES = {'primary': 'primary researcher', 'subagent': 'research subagent', 'reviewer': 'independent Reviewer'}
# What "finishing" means for each role, for the nudge.
_FINISH = {'primary': 'propose complete (or stop) when the questions are answered',
           'subagent': 'write RESULT.md and call submit_result',
           'reviewer': 'write your review and call verdict'}
# Opening sections: longer human files are shortened (the agent can read them in full).
_EXCERPT = 20_000


def _template(name: str) -> str:
    return files('research_pipeline').joinpath('prompts', name).read_text(encoding='utf-8')


def instructions(agent: Agent, project: Project, options: Options) -> str:
    """The role prompt given to every session of ``agent`` as system/developer instructions."""
    extra = {'primary': ', and in STATUS.md, REPORT.md and the root FOLDER_CONTENT.md',
             'reviewer': ', and in reviews/'}.get(agent.role, '')
    text = _template('common.md') + _template(f'{agent.role}.md')
    return Template(text).safe_substitute(
        id=agent.id, title=TITLES[agent.role], project=project.root, folder=project.agent_dir(agent.id),
        extra=extra, backends=', '.join(options.backends), parent=agent.parent or '')


def _section(title: str, path: Path) -> str | None:
    """A file's content as an opening section, or None if it is missing or empty."""
    try:
        text = path.read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return None
    if not text:
        return None
    if len(text) > _EXCERPT:
        text = text[:_EXCERPT] + f'\n\n[… shortened; read {path} for the rest]'
    return f'## {title} ({path.name})\n\n{text}'


def opening(agent: Agent, project: Project, options: Options, notices: list[str]) -> str:
    """The first message of a session: the agent's task, its handoff if any, and pending notices."""
    folder = project.agent_dir(agent.id)
    parts = [f'[controller] This is session {agent.sessions} of {agent.id}.']
    if agent.role == 'primary':
        parts += filter(None, [
            _section('Research questions', project.questions),
            _section('Instructions from the human', project.root / 'AGENTS.md'),
            _section('Feedback from the human', project.root / 'FEEDBACK.md')])
        parts.append('## Starting evidence\n\n' + project.inventory())
        if options.references:
            parts.append('## Read-only reference projects (unverified evidence)\n\n'
                         + '\n'.join(f'- {path}' for path in options.references))
    elif agent.role == 'subagent':
        parts += filter(None, [_section(f'Your task from {agent.parent}', folder / 'TASK.md'),
                               _section('Feedback from your parent on earlier results', folder / 'PARENT_FEEDBACK.md')])
    handoff = _section('Your handoff from the previous session', folder / 'HANDOFF.md')
    if handoff:
        parts.append(handoff + '\n\nContinue from this handoff. Check running jobs and subagents before redoing work.')
    elif agent.role != 'reviewer':
        parts.append('Start by writing a short plan and a first HANDOFF.md, then begin the work.')
    parts += notices
    return '\n\n'.join(parts)


# Notices ------------------------------------------------------------------------------


def handoff_request(reason: str, detail: str = '') -> str:
    why = {'context': f'Your context is {detail} full.',
           'pause': 'The human paused the investigation.',
           'quota': f'The usage quota of {detail} is nearly exhausted, so its agents pause.'}.get(reason, detail)
    return (f'[controller] {why} Finish your current step, update HANDOFF.md in your folder and end your turn; '
            'a fresh session will continue from it.')


def handoff_reminder(fill: str) -> str:
    return (f'[controller] Reminder: your context is {fill} full. Update HANDOFF.md now and end your turn; '
            'a fresh session will continue from it.')


HANDOFF_MISSING = ('[controller] HANDOFF.md has not been updated since the handoff was requested. '
                   'Update it now, then end your turn.')


def nudge(role: str) -> str:
    return ('[controller] You ended your turn, but none of your subagents or jobs is running and nothing is '
            f'pending for you. Continue your work, or {_FINISH[role]}.')


def result_submitted(child: str, path: str) -> str:
    return (f'[controller] Subagent {child} submitted its result: {path}. Read it critically, then accept it, '
            'or reject it with feedback (it then continues), or cancel it.')


def job_ended(description: str) -> str:
    return f'[controller] A job ended.\n{description}'


def human_changed(paths: list[str]) -> str:
    listing = '\n'.join(f'- {path}' for path in paths[:50])
    return (f'[controller] The human changed these files:\n{listing}\n'
            'Read them, assess what they change for the investigation, adapt the plan and keep unaffected work.')


def quota_paused(agent_id: str, backend: str) -> str:
    return (f'[controller] Subagent {agent_id} is paused because the usage quota of {backend} is low. This is '
            'temporary and operational, not a scientific blocker: it resumes automatically. Continue other work, '
            'or end your turn to wait; do not stop the investigation for this.')


def stray_entries(names: list[str]) -> str:
    return ('[controller] Unexpected entries appeared at the project\'s top level (agents cannot write there, so '
            f'probably a job did): {", ".join(names)}. If they come from your work, move them into your folder '
            'with a job (e.g. mv); otherwise leave them to the human.')


def human_message(text: str) -> str:
    return f'[human] {text.strip()}'


def review_request(kind: str, round_: int, detail: str) -> str:
    what = ('proposes COMPLETE. Its report is REPORT.md; its status is STATUS.md'
            if kind == 'complete' else f'proposes to STOP, giving this reason: {detail}')
    return (f'[controller] Review round {round_}: the primary researcher {what}. Its work is in agents/primary/ '
            'and the folders it links to; earlier reviews are in reviews/. Examine the results, write your review '
            f'to reviews/ and call verdict(review, agree).')


def verdict_delivered(kind: str, round_: int, review: str, agree: bool) -> str:
    if kind == 'complete':
        return (f'[controller] The Reviewer disagrees with COMPLETE (round {round_}). Read {review}, address its '
                'objections, then propose complete again, or stop.')
    stance = 'agrees that stopping is justified' if agree else 'challenges your STOP'
    return (f'[controller] The Reviewer {stance} (round {round_}): read {review}. Decide: confirm with '
            'stop(reason, final=True), or continue the research.')


def reopened(outcome: str, paths: list[str]) -> str:
    changes = ('\n'.join(f'- {path}' for path in paths[:50]) or '- nothing') + '\n'
    return (f'[controller] The investigation was reopened after it ended ({outcome}). Changes since then:\n'
            f'{changes}Reassess the affected results and continue; keep unaffected work. Reviews are in reviews/.')


def resumed(paths: list[str]) -> str:
    return ('[controller] The human edited these files while the investigation was paused:\n'
            + '\n'.join(f'- {path}' for path in paths[:50])
            + '\nTreat the edits as authoritative input: read them and assess their implications.')
