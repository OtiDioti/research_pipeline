"""V0-L4 foreground runtime and ordinary-file controls."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time

from . import collaboration, isolation, jobs, references, workspace
from .budget import budget_report


def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return result


def inspect_project(project):
    project = Path(os.path.abspath(project))
    state = collaboration.load_state(project)
    return {**state, 'budget_report': budget_report(state),
            'observation': 'Saved observations; live service ownership must be reconciled before any execution or cleanup'}


async def run(project, config, preserve_existing=False):
    project = Path(os.path.abspath(project))
    with workspace.acquire_project_lock(project):
        runtime = collaboration.Coordinator.initialize(project, config, preserve_existing)
        loop = asyncio.get_running_loop()
        foreground = asyncio.current_task()
        loop.add_signal_handler(signal.SIGTERM, foreground.cancel)
        try:
            await runtime.start()
            runtime.turns['primary'] = asyncio.create_task(runtime.run_task('primary'))
            # Logical runners continue across turns and measured context replacements.
            # Only pause or operational failure ends this L2 runtime.
            while True:
                if runtime.state['admission_block']:
                    break
                for observer in (runtime.monitor_task, runtime.job_monitor, runtime.quota_monitor_task):
                    if observer and observer.done() and not observer.cancelled() and observer.exception():
                        raise observer.exception()
                pending = [t for t in runtime.turns.values() if not t.done()]
                active = any(r['state'] in jobs.ACTIVE for r in runtime.state['jobs'].values())
                if not pending and not active:
                    break
                await asyncio.sleep(.1)
            # Observe errors from task wrappers; no unhandled background exceptions.
            if runtime.shutdown_task:
                await runtime.shutdown_task
            await asyncio.gather(*runtime.turns.values())
            runtime.state['cleanup_ok'] = jobs.science_quiescent(runtime.state)
            failed_contexts = any(t.get('context_error') for t in runtime.state['tasks'].values())
            if not runtime.state['admission_block']:
                runtime.state.update(
                    state='failed' if failed_contexts else 'idle',
                    reason='Native context failed or was interrupted; inspect retained turn outcomes.'
                    if failed_contexts else
                    'Contexts ended; retained science remains preliminary. No scientific terminal decision was made.')
            if not runtime.state['cleanup_ok']:
                runtime.state.update(state='cleanup_unconfirmed', reason='Owned context/job cleanup is unconfirmed.')
            runtime.save()
            if runtime.state.get('stop_origin') == 'quota':
                print(f"quota STOP: {runtime.state['admission_block']}; "
                      f"cleanup confirmed={runtime.state['cleanup_ok']}; "
                      f"finalization confirmed={runtime.state.get('finalization_ok', False)}; "
                      'saving/cleanup may consume further quota')
            elif runtime.state.get('cleanup_outcome') == 'quota_unavailable':
                print('weekly quota telemetry unavailable; research admission refused; no observed cutoff')
            elif runtime.state.get('requested_scientific_intent'):
                print(f"scientific {runtime.state['requested_scientific_intent']}: "
                      f"outcome={runtime.state['state']}; cleanup confirmed={runtime.state['cleanup_ok']}; "
                      f"finalization confirmed={collaboration.terminal_acknowledged(project, runtime.state)}; "
                      f"details={runtime.state.get('terminal_error') or runtime.state.get('persistence_error') or runtime.state.get('terminal_note')}")
                if (runtime.state['requested_scientific_intent'] == 'STOP'
                        and not runtime.state.get('terminal_committed')):
                    print(runtime.state['opposition']['history'][-1]['final_request']['text'])
            return 0 if (not failed_contexts and runtime.state['cleanup_ok']
                         and runtime.state.get('finalization_ok', True)
                         and runtime.state['state'] not in
                         ('failed', 'reassessment_required', 'cleanup_unconfirmed', 'quota_unavailable')) else 1
        except BaseException as exc:
            runtime.state['runtime_error'] = f'{type(exc).__name__}: {exc}'
            if not collaboration.terminal_acknowledged(project, runtime.state):
                runtime.schedule_shutdown('Runtime interrupted or failed: ' + str(exc), 'failed')
            if runtime.shutdown_task:
                await runtime.shutdown_task
            else:
                await runtime.block_and_cleanup('Runtime interrupted or failed')
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, KeyboardInterrupt):
                return 130
            raise
        finally:
            await runtime.close()
            loop.remove_signal_handler(signal.SIGTERM)


def start(project, config, preserve_existing=False):
    try:
        return asyncio.run(run(project, config, preserve_existing))
    except (asyncio.CancelledError, KeyboardInterrupt):
        return 130


async def pause_async(project):
    project = Path(os.path.abspath(project))
    state = collaboration.load_state(project)
    jobs.atomic(project / '.research_pipeline/pause.json', {'run_id': state['run_id'], 'reason': 'Human pause'})
    until = time.monotonic() + 30  # operational acknowledgement bound only
    while time.monotonic() < until:
        state = collaboration.load_state(project)
        if state.get('admission_block') and state.get('cleanup_ok') is True:
            print(f"{state['state']}: all owned contexts/jobs confirmed stopped; partial artifacts retained")
            return 0 if state.get('finalization_ok', True) else 1
        # An idle/crashed foreground must not be replaced before ownership cleanup.
        try:
            with workspace.acquire_project_lock(project):
                state = collaboration.load_state(project)
                if state.get('terminal_committed') and state.get('cleanup_ok') and state.get('finalization_ok'):
                    print(f"{state['state']}: committed terminal outcome preserved")
                    return 0
                state.update(admission_block=state.get('admission_block') or 'Human pause', state='stopping')
                workspace.write_state(project, state)
                outcomes = {}
                for record in [*state['contexts'].values(), *state['jobs'].values()]:
                    if record.get('cleanup_ok') is True:
                        continue
                    outcome = await isolation.stop_owned(record.get('service'))
                    outcomes[record.get('context_id', record.get('job_id'))] = outcome
                    record['cleanup_ok'] = outcome['confirmed']
                    record['cleanup'] = outcome
                    record['state'] = ('closed' if 'context_id' in record else 'cancelled') if outcome['confirmed'] else 'cleanup_unconfirmed'
                confirmed = all(o['confirmed'] for o in outcomes.values())
                stopped = ('quota_stopped' if state.get('stop_origin') == 'quota' else
                           'failed' if state.get('requested_scientific_intent') else 'paused')
                state.update(state=stopped if confirmed else 'cleanup_unconfirmed', cleanup_ok=confirmed, cleanup=outcomes)
                workspace.write_state(project, state)
                if not confirmed:
                    raise workspace.InputError('Pause failed: ownership/cleanup unconfirmed; see retained per-process evidence')
                print(f'{stopped}: confirmed owned-process cleanup; inspect artifacts for missing handoffs')
                return 0 if state.get('finalization_ok', stopped == 'paused') else 1
        except workspace.ProjectBusy:
            pass
        await asyncio.sleep(.1)
    raise workspace.InputError('Pause acknowledgement timed out; request retained, termination unconfirmed')


def pause(project):
    return asyncio.run(pause_async(project))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Research-owned V0-L4 runtime')
    sub = parser.add_subparsers(dest='command', required=True)
    launch = sub.add_parser('start')
    launch.add_argument('project', type=Path)
    launch.add_argument('--codex', default='codex')
    launch.add_argument('--model')
    launch.add_argument('--preserve-existing', action='store_true')
    launch.add_argument('--secondary-staleness-seconds', type=positive_int, default=2700)
    for name, default in [('memory-mib', 2048), ('max-tasks', 128), ('max-agents', 2), ('max-jobs', 1)]:
        launch.add_argument('--' + name, type=positive_int, default=default)
    show = sub.add_parser('inspect')
    show.add_argument('project', type=Path)
    show.add_argument('--json', action='store_true')
    suspend = sub.add_parser('pause')
    suspend.add_argument('project', type=Path)
    restart = sub.add_parser('resume', help='explicitly unsupported until V0-L5; existing science is preserved')
    restart.add_argument('project', type=Path)
    for name, option in [('redirect', '--questions-file'), ('feedback', '--file')]:
        command = sub.add_parser(name)
        command.add_argument('project', type=Path)
        command.add_argument(option, dest='source', required=True, type=Path)
    refs = sub.add_parser('reference')
    actions = refs.add_subparsers(dest='action', required=True)
    references.add_read_commands(actions, host=True)
    for action in ('add', 'remove'):
        command = actions.add_parser(action)
        command.add_argument('project', type=Path)
        command.add_argument('alias')
        if action == 'add':
            command.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            state = inspect_project(args.project)
            print(json.dumps(state, indent=2))
            return 0
        if args.command == 'pause':
            return pause(args.project)
        if args.command == 'resume':
            raise workspace.InputError('Stopped-state resume/reopening is unsupported until V0-L5. Preserve historical science; do not migrate old operational state.')
        if args.command in ('redirect', 'feedback', 'reference'):
            project = Path(os.path.abspath(args.project))
            with workspace.acquire_project_lock(project):
                if args.command == 'reference':
                    if args.action not in ('add', 'remove'):
                        print(json.dumps(references.dispatch(references.load_catalog(project), args), indent=2))
                        return 0
                    if (project / '.research_pipeline/run.json').exists():
                        saved = collaboration.load_state(project)
                        if any(not r.get('cleanup_ok') for r in [*saved['contexts'].values(), *saved['jobs'].values()]):
                            raise workspace.InputError('Confirm owned-process cleanup with pause before changing reference authorization')
                    if not references.ALIAS.fullmatch(args.alias):
                        raise workspace.InputError('Invalid reference alias')
                    registry = references.load_registry(project)
                    if args.action == 'add':
                        root = references.validate_reference_root(project, args.path)
                        references.reference_entries(root)
                        previous = registry['references'].get(args.alias)
                        if previous and previous != str(root):
                            raise workspace.InputError('Alias already authorizes another root; remove it first')
                        registry['references'][args.alias] = str(root)
                    else:
                        if args.alias not in registry['references']:
                            raise workspace.InputError('Reference alias is not authorized')
                        del registry['references'][args.alias]
                    workspace.atomic_text(project / references.REGISTRY, json.dumps(registry, indent=2) + '\n')
                    print(json.dumps({'references': references.load_catalog(project)}, indent=2))
                else:
                    text = workspace.read_input(args.source)
                    target = project / ('HUMAN_FEEDBACK.md' if args.command == 'feedback' else 'starting_evidence/RESEARCH_QUESTIONS.md')
                    workspace.atomic_text(target, text)
            return 0
        config = isolation.Config(codex=args.codex, model=args.model, memory_mib=args.memory_mib,
                    max_tasks=args.max_tasks, max_agents=args.max_agents, max_jobs=args.max_jobs,
                    secondary_staleness_seconds=args.secondary_staleness_seconds)
        return start(args.project, config, args.preserve_existing)
    except (OSError, ValueError, isolation.RuntimeUnavailable) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
