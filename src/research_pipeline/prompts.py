"""Everything the controller says to agents: session instructions, opening messages and notices.

Session instructions are the role prompt, from the Markdown files in ``prompts/``
(one shared part, one part per role), followed by the human's ``AGENTS.md``. They
stay in force for the whole session. Notices are short and start with
``[controller]``, ``[human]`` for the human's messages, or ``[from <id>]`` for
messages between a parent and its subagents, as the instructions announce.
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit.protocol import Prompts

from research_pipeline.project import Project
from research_pipeline.state import Agent, Options

TITLES = {'primary': 'primary researcher', 'subagent': 'research subagent', 'reviewer': 'independent Reviewer'}
# What "finishing" means for each role, for the nudge.
_FINISH = {'primary': 'propose complete (or stop) when the questions are answered',
           'subagent': 'write RESULT.md and call submit_result',
           'reviewer': 'write your review and call verdict'}
# Longer human files are shortened in instructions and opening messages (the agent can read them in full).
_EXCERPT = 20_000
#: The role prompt files; every placeholder must be filled.
PROMPTS = Prompts('research_pipeline')


def instructions(agent: Agent, project: Project, options: Options) -> str:
    """The session instructions of ``agent``: its role prompt, then the human's AGENTS.md (PROJECT.md §3)."""
    extra = {'primary': ', and in STATUS.md, REPORT.md and the root FOLDER_CONTENT.md',
             'reviewer': ', and in reviews/'}.get(agent.role, '')
    text = PROMPTS.fill('common', agent.role, id=agent.id, title=TITLES[agent.role], project=project.root,
                        folder=project.agent_dir(agent.id), extra=extra, backends=', '.join(options.backends),
                        parent=agent.parent or '')
    human = _section('Instructions from the human', project.root / 'AGENTS.md', level='#')
    return f'{text}\n\n{human}\n' if human else text + '\n'


def _section(title: str, path: Path, level: str = '##') -> str | None:
    """A file's content as a titled section, or None if it is missing or empty."""
    try:
        text = path.read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return None
    if not text:
        return None
    if len(text) > _EXCERPT:
        text = text[:_EXCERPT] + f'\n\n[… shortened; read {path} for the rest]'
    return f'{level} {title} ({path.name})\n\n{text}'


def opening(agent: Agent, project: Project, options: Options, notices: list[str]) -> str:
    """The first message of a session: the agent's task, its handoff if any, and pending notices."""
    folder = project.agent_dir(agent.id)
    parts = [f'[controller] This is session {agent.sessions} of {agent.id}.']
    if agent.role == 'primary':
        parts += filter(None, [_section('Research questions', project.questions),
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
           'shutdown': 'The human is shutting the controller down.',
           'quota': f'The usage quota of {detail} is nearly exhausted, so its agents pause.',
           'hold': 'The human paused you; your subagents and jobs keep working, and their news waits for you.',
           'refresh': 'The human asked you to continue in a fresh session.'}.get(reason, detail)
    return (f'[controller] {why} Finish your current step, update HANDOFF.md in your folder and end your turn; '
            'a fresh session will continue from it.')


def handoff_reminder(fill: str) -> str:
    return (f'[controller] Reminder: your context is {fill} full. Update HANDOFF.md now and end your turn; '
            'a fresh session will continue from it.')


HANDOFF_MISSING = ('[controller] HANDOFF.md has not been updated since the handoff was requested. '
                   'Update it now, then end your turn.')


def nudge(role: str, awaiting: list[str]) -> str:
    """For an agent that ended its turn with nothing running or pending for it."""
    if awaiting:
        return (f'[controller] You ended your turn, but results await your decision: {", ".join(awaiting)}. '
                'Accept each, reject it with feedback, or cancel it; then continue your work.')
    return ('[controller] You ended your turn, but none of your subagents or jobs is running and nothing is '
            f'pending for you. Continue your work, or {_FINISH[role]}.')


def stalled(child: str, last: str) -> str:
    """For the parent of a subagent that ended its turn idle again after its nudge."""
    return (f'[controller] Subagent {child} has stopped working: it ended its turn twice with nothing running or '
            f'pending, without using a tool. Its last message:\n{last}\n'
            f'Message it with what it needs (message), or cancel it.')


def agent_message(sender: str, text: str) -> str:
    return f'[from {sender}] {text.strip()}'


def result_submitted(child: str, path: str) -> str:
    return (f'[controller] Subagent {child} submitted its result: {path}. Read it critically, then accept it, '
            'or reject it with feedback (it then continues), or cancel it.')


def job_ended(description: str) -> str:
    return f'[controller] A job ended.\n{description}'


def human_changed(paths: list[str]) -> str:
    listing = '\n'.join(f'- {path}' for path in paths[:50])
    agents_md = ('\nThe new AGENTS.md reaches every agent\'s instructions at its next session; tell running '
                 'subagents what they need now.' if 'AGENTS.md' in paths else '')
    return (f'[controller] The human changed these files:\n{listing}\n'
            f'Read them, assess what they change for the investigation, adapt the plan and keep unaffected work.'
            f'{agents_md}')


def quota_paused(agent_id: str, backend: str) -> str:
    return (f'[controller] Subagent {agent_id} is paused because the usage quota of {backend} is low. This is '
            'temporary and operational, not a scientific blocker: it resumes automatically. Continue any work '
            'that does not depend on it, and end your turn only if nothing remains; do not stop the '
            'investigation for this.')


def stray_entries(names: list[str]) -> str:
    return ('[controller] Unexpected entries appeared at the project\'s top level (agents cannot write there, so '
            f'probably a job did): {", ".join(names)}. If they come from your work, move them into your folder '
            'with a job (e.g. mv); otherwise leave them to the human.')


def human_message(text: str) -> str:
    return f'[human] {text.strip()}'


def human_to_child(child: str, text: str) -> str:
    return f'[human → {child}] The human wrote to your subagent {child}: {text.strip()}'


def human_paused(child: str) -> str:
    return (f'[controller] The human paused your subagent {child}: it waits until the human resumes it. Its messages '
            'to you and its result wait as well.')


def human_resumed(child: str) -> str:
    return f'[controller] The human resumed your subagent {child}; it continues from its handoff.'


def human_cancelled(child: str) -> str:
    return (f'[human] The human cancelled your subagent {child}, with its subagents and jobs. Continue without its '
            'result, or start another subagent if the work is still needed.')


def review_request(kind: str, round_: int, detail: str) -> str:
    what = ('proposes COMPLETE. Its report is REPORT.md; its status is STATUS.md'
            if kind == 'complete' else f'proposes to STOP, giving this reason: {detail}')
    return (f'[controller] Review round {round_}: the primary researcher {what}. Its work is in agents/primary/ '
            'and the folders it links to; earlier reviews are in reviews/. Examine the results, write your review '
            f'to reviews/ and call verdict(review, agree).')


def talk_only(round_: int) -> str:
    """For a primary woken by the human while its proposal is with the Reviewer."""
    return (f'[controller] Your proposal (round {round_}) is with the Reviewer. You were woken to answer the human: '
            'until the verdict, spawn and run_job are refused and STATUS.md and REPORT.md are read-only. The '
            'verdict will be delivered to you.')


def verdict_delivered(kind: str, round_: int, review: str, agree: bool) -> str:
    if kind == 'complete':
        return (f'[controller] The Reviewer disagrees with COMPLETE (round {round_}). Read {review}, address its '
                'objections, then propose complete again, or stop.')
    stance = 'agrees that stopping is justified' if agree else 'challenges your STOP'
    return (f'[controller] The Reviewer {stance} (round {round_}): read {review}. Decide: confirm with '
            'stop(reason, final=True), or continue the research.')


def review_withdrawn(kind: str, round_: int) -> str:
    """For the primary when the Reviewer stalled without a verdict."""
    return (f'[controller] The Reviewer stopped without a verdict on your {kind.upper()} proposal (round {round_}), '
            'so the proposal is withdrawn. Continue the research, propose again, or stop.')


def reopened(outcome: str, paths: list[str]) -> str:
    changes = ('\n'.join(f'- {path}' for path in paths[:50]) or '- nothing') + '\n'
    return (f'[controller] The investigation was reopened after it ended ({outcome}). Changes since then:\n'
            f'{changes}Reassess the affected results and continue; keep unaffected work. Reviews are in reviews/.')


def resumed(paths: list[str]) -> str:
    """For agents whose files changed while the investigation was paused or the controller was off."""
    return ('[controller] These files changed while the investigation was paused or the controller was off, by '
            'the human or by running jobs:\n' + '\n'.join(f'- {path}' for path in paths[:50])
            + '\nRead them: the human\'s edits are authoritative input; your jobs\' files are their output.')
